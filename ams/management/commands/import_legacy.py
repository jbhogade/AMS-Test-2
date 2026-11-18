"""
#-------------- Start Code for : LEGACY IMPORT (import_legacy.py) --------------

One-shot data migration from the ORIGINAL AMS-Test database (SQL Server
database "AMS-TEST", written by its C# API) into AMS-Test-2.

The old schema keeps every record twice: typed columns mirror the important
fields, and data_json holds the FULL original record (camelCase). This
importer reads data_json (authoritative) and falls back to typed columns,
then writes proper relational rows into the new models.

Usage (SQL Server source, the normal case):
    python manage.py import_legacy --legacy-host localhost --legacy-user sa
        --legacy-password *** [--legacy-name AMS-TEST] [--wipe]

Usage (offline mirror / testing):
    python manage.py import_legacy --source-sqlite path\to\ams-test-mirror.db

Options:
    --wipe        delete existing business rows first (keeps django_* tables)
    --dry-run     parse the old database and print a report, write nothing
    --skip-users  do not import user accounts (e.g. keep only the seeded ones)

Imported: sites, departments, designations, asset categories/types/makes,
accessories, vendors (+ supplies), SIM operators/plans, consumable cats/units,
spare part categories, print terms, employees (+ managers), assets & mobiles
(+ accessories M2M, replacement chain, linked SIM), SIM cards, lifecycle
history (per-item history[] + global assignmentEvents, de-duplicated),
consumables + spare parts + their movement logs, exit records, user accounts
(old PBKDF2 hashes stay verifiable via ams.hashers.AmsLegacyHasher), company
profile incl. logo/banner (decoded from base64 data URLs to media/company/),
report prefs, role-access matrix, per-user allowed pages and activity log.
#-------------- End of the code for : LEGACY IMPORT (import_legacy.py) --------
"""

import base64
import json
import re
import uuid
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User

from ams.activity import ensure_profile
from ams.access import RECOMMENDED_MATRIX, PAGE_KEYS
from ams.models import (
    Site, Department, Designation, AssetCategory, AssetType, AssetMake,
    VendorCategory, Vendor, Accessory, SimOperator, SimPlan,
    ConsumableCategory, UnitOfMeasure, SparePartCategory, PrintTerm,
    Employee, ExitRecord, Asset, SimCard, LifecycleEvent,
    Consumable, SparePart, StockMovement, UserProfile, RoleAccess,
    ActivityLog, Company, ReportPrefs, PortalPref, FormCounter,
)

EVENT_TYPE_RULES = [
    ("reassign", "Reassign"), ("assigned", "Assign"), ("assign", "Assign"),
    ("return", "Return"), ("transfer", "Transfer"), ("replace", "Replace"),
    ("retire", "Retire"), ("scrap", "Retire"), ("fault", "Fault"),
    ("repair", "Fault"), ("swap", "Swap"), ("update", "Edit"), ("edit", "Edit"),
]


def classify_event(action):
    a = (action or "").lower()
    for needle, label in EVENT_TYPE_RULES:
        if needle in a:
            return label
    return "Other"


# ---------------------------------------------------------------------------
# SOURCE READERS
# ---------------------------------------------------------------------------

class LegacySource:
    """Reads the old AMS-Test database. Two backends share one interface."""

    def rows(self, table):
        raise NotImplementedError

    def has_table(self, table):
        raise NotImplementedError

    def collections(self):
        """Old v1 format fallback: collection_key -> parsed data_json."""
        out = {}
        if self.has_table("ams_collections"):
            for r in self.rows("ams_collections"):
                key = (r.get("collection_key") or "").strip()
                out[key] = _parse_json(r.get("data_json"))
        return out

    def collection_rows(self, key, table):
        """Prefer the per-entity table (v2 schema); fall back to v1 JSON docs."""
        if self.has_table(table):
            return self.rows(table)
        col = self.collections().get(key)
        return col if isinstance(col, list) else []

    def documents(self):
        """Document collections: roleAccess / reportPrefs / accessRights."""
        docs = {}
        for r in self.collection_rows("documents", "ams_documents"):
            key = (r.get("record_key") or "").strip()
            docs[key] = _parse_json(r.get("data_json"))
        col = self.collections()
        for key in ("roleAccess", "reportPrefs", "accessRights"):
            if key not in docs and isinstance(col.get(key), dict):
                docs[key] = col[key]
        return docs

    def company_row(self):
        rows = self.collection_rows("company", "ams_company")
        if not rows:
            col = self.collections().get("company")
            return col if isinstance(col, dict) else None
        return rows[0]


class PyodbcSource(LegacySource):
    """Live connection to the old AMS-TEST SQL Server database."""

    def __init__(self, host, port, name, user, password, driver, trusted=False):
        import pyodbc  # only required for the SQL Server source

        # A named instance (host\\SQLEXPRESS) or a blank port is resolved
        # by the SQL Server Browser service, so SERVER has no ",port" part.
        server = f"{host},{port}" if port else host
        if trusted or not user:
            # Windows Authentication - no UID/PWD in the connection string.
            cs = (
                f"DRIVER={{{driver}}};SERVER={server};DATABASE={name};"
                f"Trusted_Connection=yes;TrustServerCertificate=yes;"
            )
            shown = f"Windows Authentication @ {server}"
        else:
            cs = (
                f"DRIVER={{{driver}}};SERVER={server};DATABASE={name};"
                f"UID={user};PWD={password};TrustServerCertificate=yes;"
            )
            shown = f"{name} @ {server} as {user}"
        try:
            self.conn = pyodbc.connect(cs, timeout=15)
        except Exception as e:
            raise CommandError(
                f"Could not connect to the legacy AMS-Test database "
                f"({shown}): {e}\n"
                f"Run 'python manage.py dbdoctor' (or Test-SQL-Connection.bat) "
                f"and try the printed fixes for the NEW project first - the "
                f"legacy database uses the same server infrastructure."
            )
        self._tables = None

    def _table_names(self):
        if self._tables is None:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT t.name FROM sys.tables t WHERE t.is_ms_shipped = 0"
            )
            self._tables = {r[0].lower() for r in cur.fetchall()}
        return self._tables

    def has_table(self, table):
        return table.lower() in self._table_names()

    def rows(self, table):
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM dbo.{table}")
        cols = [c[0].lower() for c in cur.description]
        out = []
        for r in cur.fetchall():
            row = {}
            for col, val in zip(cols, r):
                row[col] = val.decode("utf-8", "replace") if isinstance(val, (bytes, bytearray)) else val
            out.append(row)
        return out


class SqliteSource(LegacySource):
    """SQLite mirror of the legacy schema (offline testing / small sites)."""

    def __init__(self, path):
        import sqlite3

        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._tables = {
            r[0].lower()
            for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }

    def has_table(self, table):
        return table.lower() in self._tables

    def rows(self, table):
        return [dict(r) for r in self.conn.execute(f"SELECT * FROM [{table}]")]


# ---------------------------------------------------------------------------
# VALUE COERCION HELPERS
# ---------------------------------------------------------------------------

def _parse_json(v):
    if v in (None, ""):
        return {}
    if isinstance(v, dict):
        return v
    try:
        out = json.loads(v)
        return out if isinstance(out, (dict, list)) else {}
    except (ValueError, TypeError):
        return {}


def s(*vals):
    """First non-empty value as trimmed string."""
    for v in vals:
        if v is None:
            continue
        if isinstance(v, (dict, list)):
            continue
        t = str(v).strip()
        if t:
            return t
    return ""


def b(*vals):
    for v in vals:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        t = s(v).lower()
        if t in ("true", "1", "yes", "y", "on"):
            return True
        if t in ("false", "0", "no", "n", "off"):
            return False
    return None


def dec(*vals):
    for v in vals:
        t = s(v).replace(",", "").replace("\u20b9", "").strip()
        if not t:
            continue
        try:
            return Decimal(t)
        except (InvalidOperation, ValueError):
            continue
    return None


def dt_date(*vals):
    for v in vals:
        t = s(v)
        if not t:
            continue
        t = t.replace("T", " ").split(".")[0].replace("Z", "").strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d-%b-%Y", "%d-%b-%y", "%m/%d/%Y"):
            try:
                return datetime.strptime(t[:10] if fmt == "%Y-%m-%d" else t, fmt).date()
            except ValueError:
                continue
        try:  # last resort: leading ISO part
            return date.fromisoformat(t[:10])
        except ValueError:
            continue
    return None


def dt_time(*vals):
    for v in vals:
        t = s(v)
        if not t:
            continue
        try:
            naive = datetime.fromisoformat(t.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    naive = datetime.strptime(t, fmt)
                    break
                except ValueError:
                    naive = None
            if naive is None:
                continue
        try:
            return timezone.make_aware(naive) if timezone.is_naive(naive) else naive
        except (ValueError, OverflowError):
            return naive
    return None


# ---------------------------------------------------------------------------
# THE COMMAND
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Import all business data from the original AMS-Test database (AMS-TEST) into AMS-Test-2."

    def add_arguments(self, parser):
        parser.add_argument("--legacy-host", default=None)
        parser.add_argument("--legacy-port", default=None,
                            help="leave blank for a named instance (host\\SQLEXPRESS)")
        parser.add_argument("--legacy-name", default="AMS-TEST")
        parser.add_argument("--legacy-user", default=None)
        parser.add_argument("--legacy-password", default=None)
        parser.add_argument("--legacy-driver", default="ODBC Driver 18 for SQL Server")
        parser.add_argument("--legacy-trusted", action="store_true",
                            help="Windows Authentication for the legacy connection "
                                 "(no --legacy-user / --legacy-password)")
        parser.add_argument("--source-sqlite", default=None,
                            help="SQLite mirror of the legacy database instead of a live SQL Server connection")
        parser.add_argument("--wipe", action="store_true",
                            help="delete existing business data before importing")
        parser.add_argument("--dry-run", action="store_true",
                            help="read the old database and report, but write nothing")
        parser.add_argument("--skip-users", action="store_true",
                            help="do not import user accounts / passwords")

    # ---- small helpers shared by all handlers -----------------------------

    def warn(self, msg):
        self.warnings.append(msg)

    def note(self, msg):
        self.stdout.write(msg)

    def handle(self, *args, **opts):
        self.warnings = []
        self.counts = {}
        self.dry_run = opts["dry_run"]

        if opts["source_sqlite"]:
            src = SqliteSource(opts["source_sqlite"])
            self.note(f"Legacy source : SQLite mirror {opts['source_sqlite']}")
        else:
            import os
            host = opts["legacy_host"] or os.environ.get("AMS_LEGACY_DB_HOST") or "localhost"
            trusted = bool(opts.get("legacy_trusted"))
            user = "" if trusted else (
                opts["legacy_user"] or os.environ.get("AMS_LEGACY_DB_USER") or "sa")
            pwd = opts["legacy_password"] or os.environ.get("AMS_LEGACY_DB_PASSWORD") or ""
            port = opts["legacy_port"] or ""
            src = PyodbcSource(host, port, opts["legacy_name"],
                               user, pwd, opts["legacy_driver"], trusted=trusted)
            shown_port = f",{port}" if port else " (named instance)"
            auth = "Windows Auth" if (trusted or not user) else f"user {user}"
            self.note(f"Legacy source : SQL Server {opts['legacy_name']} @ {host}{shown_port} ({auth})")
        self.src = src

        self.note(f"Mode          : {'DRY RUN (no data written)' if self.dry_run else 'IMPORT (inside one transaction)'}")
        self.note("")

        if self.dry_run:
            self._run_import(opts)
        else:
            with transaction.atomic():
                self._run_import(opts)

        self._report()

    # ------------------------------------------------------------------

    def _run_import(self, opts):
        if opts["wipe"] and not self.dry_run:
            self._wipe()
        self.wiped = bool(opts["wipe"]) and not self.dry_run

        self._import_masters()
        self._import_employees()
        self._import_assets_and_mobiles()
        self._import_sim_cards()
        self._import_lifecycle_events()
        self._import_stock()
        self._import_exit_records()
        if not opts["skip_users"]:
            self._import_users()
        self._import_company_and_prefs()
        self._import_role_access_and_rights()
        self._import_activity_log()

        if not self.dry_run:
            # portal defaults + counters table (empty rows are fine)
            PortalPref.objects.get_or_create(key="portal_name", defaults={"value": "Asset Manager"})
            ReportPrefs.get_solo()
            Company.get_solo()

    def _wipe(self):
        self.note("-- Wipe: deleting existing business rows ---------------------")
        # FK-safe order; django_* tables (migrations/contenttypes) untouched.
        for model in (LifecycleEvent, StockMovement, ExitRecord, Asset,
                      SimCard, Consumable, SparePart, Employee, Accessory,
                      Vendor, PrintTerm, SparePartCategory, UnitOfMeasure,
                      ConsumableCategory, SimPlan, SimOperator, AssetMake,
                      AssetType, AssetCategory, Designation, Department,
                      Site, VendorCategory, RoleAccess, ActivityLog,
                      UserProfile, FormCounter, PortalPref, ReportPrefs,
                      Company):
            n = model.objects.all().delete()[0]
            if n:
                self.note(f"   {model.__name__}: {n} rows deleted")
        for u in User.objects.exclude(username__in=()):  # all portal users
            u.delete()

    # ---- naming resolution caches -----------------------------------------

    def _site(self, name):
        return self._by_name("site", name)

    def _dept(self, name):
        return self._by_name("dept", name)

    def _emp(self, ref):
        """Employee by ams_id first, then emp_id, then name."""
        if not ref:
            return None
        ref = str(ref).strip()
        cache = self._emp_cache
        if ref in cache:
            return cache[ref]
        obj = (Employee.objects.filter(ams_id__iexact=ref).first()
               or Employee.objects.filter(emp_id__iexact=ref).first()
               or Employee.objects.filter(name__iexact=ref).first())
        cache[ref] = obj
        return obj

    def _vendor(self, name):
        return self._by_name("vendor", name)

    def _by_name(self, cache_name, name):
        cache = getattr(self, f"_{cache_name}_cache", None)
        if cache is None:
            cache = {}
            setattr(self, f"_{cache_name}_cache", cache)
        if not name:
            return None
        key = str(name).strip()
        if key in cache:
            return cache[key]
        model = {"site": Site, "dept": Department, "vendor": Vendor}[cache_name]
        obj = model.objects.filter(name__iexact=key).first()
        cache[key] = obj
        return obj

    # ==================================================================
    # 1) MASTERS
    # ==================================================================

    def _import_masters(self):
        self.note("-- Masters ----------------------------------------------------")

        # Vendor categories
        n = 0
        for r in self.src.collection_rows("vendorCategories", "ams_vendor_categories"):
            j = _parse_json(r.get("data_json")) or {}
            if not s(r.get("name"), j.get("name")):
                continue
            VendorCategory.objects.update_or_create(
                name=s(r.get("name"), j.get("name")),
                defaults={"description": s(r.get("description"), j.get("description")),
                          "active": b(r.get("active"), j.get("active")) or False},
            )
            n += 1
        self.counts["Vendor categories"] = n

        # Sites
        n = 0
        for r in self.src.collection_rows("sites", "ams_sites"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            Site.objects.update_or_create(
                name=name,
                defaults={"shortform": s(r.get("shortform"), j.get("shortform"))[:4] or "NA",
                          "address": s(r.get("address"), j.get("address")),
                          "active": b(r.get("active"), j.get("active")) or False},
            )
            n += 1
        self.counts["Sites"] = n

        # Departments
        n = 0
        for r in self.src.collection_rows("departments", "ams_departments"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            Department.objects.update_or_create(
                name=name,
                defaults={"shortform": s(r.get("shortform"), j.get("shortform"))[:4] or "NA",
                          "active": b(r.get("active"), j.get("active")) or False},
            )
            n += 1
        self.counts["Departments"] = n

        # Designations
        n = 0
        for r in self.src.collection_rows("designations", "ams_designations"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            Designation.objects.update_or_create(name=name, defaults={"active": b(r.get("active"), j.get("active")) or False})
            n += 1
        self.counts["Designations"] = n

        # Asset categories
        n = 0
        for r in self.src.collection_rows("assetCategories", "ams_asset_categories"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            used_on = s(r.get("used_on"), j.get("usedOn"), j.get("used_on")) or "Both"
            if used_on not in ("Assets", "Mobiles", "Both"):
                used_on = "Both"
            AssetCategory.objects.update_or_create(
                name=name,
                defaults={"used_on": used_on, "active": b(r.get("active"), j.get("active")) or False},
            )
            n += 1
        self.counts["Asset categories"] = n

        # Asset types (category FK by name)
        n = 0
        for r in self.src.collection_rows("assetTypes", "ams_asset_types"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            cat = s(r.get("category"), j.get("category"))
            AssetType.objects.update_or_create(
                name=name,
                defaults={
                    "shortform": s(r.get("shortform"), j.get("shortform"))[:4] or "NA",
                    "category": AssetCategory.objects.filter(name__iexact=cat).first(),
                    "active": b(r.get("active"), j.get("active")) or False,
                },
            )
            n += 1
        self.counts["Asset types"] = n

        # Asset makes (asset_type FK by name)
        n = 0
        for r in self.src.collection_rows("assetMakes", "ams_asset_makes"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            atype = s(r.get("asset_type"), j.get("assetType"), j.get("asset_type"))
            AssetMake.objects.update_or_create(
                name=name, asset_type=AssetType.objects.filter(name__iexact=atype).first(),
                defaults={"active": b(r.get("active"), j.get("active")) or False},
            )
            n += 1
        self.counts["Asset makes"] = n

        # Accessories
        n = 0
        for r in self.src.collection_rows("accessories", "ams_accessories"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            code = s(r.get("acc_code"), j.get("accCode"), j.get("acc_code")) or f"ACC-{uuid.uuid4().hex[:8].upper()}"
            atype = s(r.get("asset_type"), j.get("assetType"), j.get("asset_type"))
            site = s(r.get("site"), j.get("site"))
            Accessory.objects.update_or_create(
                code=code[:16],
                defaults={
                    "name": name,
                    "asset_type": AssetType.objects.filter(name__iexact=atype).first(),
                    "site": self._site(site),
                    "active": b(r.get("active"), j.get("active")) or False,
                },
            )
            n += 1
        self.counts["Accessories"] = n

        # SIM operators + plans
        n = 0
        for r in self.src.collection_rows("simOperators", "ams_sim_operators"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            SimOperator.objects.update_or_create(
                name=name,
                defaults={"helpline": s(r.get("helpline"), j.get("helpline")),
                          "website": s(r.get("website"), j.get("website")),
                          "active": b(r.get("active"), j.get("active")) or False},
            )
            n += 1
        self.counts["SIM operators"] = n

        n = 0
        for r in self.src.collection_rows("simPlans", "ams_sim_plans"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            SimPlan.objects.update_or_create(
                name=name,
                defaults={"plan_type": s(r.get("plan_type"), j.get("planType"), j.get("plan_type")),
                          "description": s(r.get("description"), j.get("description")),
                          "active": b(r.get("active"), j.get("active")) or False},
            )
            n += 1
        self.counts["SIM plans"] = n

        # Consumable categories / units, spare part categories
        n = 0
        for r in self.src.collection_rows("consumableCategories", "ams_consumable_categories"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            ConsumableCategory.objects.update_or_create(
                name=name, defaults={"description": s(r.get("description"), j.get("description")),
                                     "active": b(r.get("active"), j.get("active")) or False})
            n += 1
        self.counts["Consumable categories"] = n

        n = 0
        for r in self.src.collection_rows("consumableUnits", "ams_consumable_units"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            UnitOfMeasure.objects.update_or_create(
                name=name, defaults={"description": s(r.get("description"), j.get("description")),
                                     "active": b(r.get("active"), j.get("active")) or False})
            n += 1
        self.counts["Units of measure"] = n

        n = 0
        for r in self.src.collection_rows("sparePartCategories", "ams_spare_part_categories"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            SparePartCategory.objects.update_or_create(
                name=name, defaults={"description": s(r.get("description"), j.get("description")),
                                     "active": b(r.get("active"), j.get("active")) or False})
            n += 1
        self.counts["Spare part categories"] = n

        # Print terms
        n = 0
        for r in self.src.collection_rows("printTerms", "ams_print_terms"):
            j = _parse_json(r.get("data_json")) or {}
            term_id = s(r.get("term_id"), j.get("termId"), j.get("term_id"))
            text = s(r.get("rule_text"), j.get("text"), j.get("rule_text"))
            if not term_id or not text:
                continue
            used_on = s(r.get("used_on"), j.get("usedOn"), j.get("used_on")) or "All"
            if used_on not in dict(PrintTerm.USED_ON):
                used_on = "All"
            sort_order = dec(r.get("sort_order"), j.get("sortOrder"), j.get("sort_order"))
            PrintTerm.objects.update_or_create(
                term_id=term_id[:12],
                defaults={"text": text[:1000], "used_on": used_on,
                          "sort_order": int(sort_order) if sort_order is not None else 10,
                          "active": b(r.get("active"), j.get("active")) or False},
            )
            n += 1
        self.counts["Print terms"] = n

        # Vendors (single old category string -> M2M supplies)
        n = 0
        for r in self.src.collection_rows("vendors", "ams_vendors"):
            j = _parse_json(r.get("data_json")) or {}
            name = s(r.get("name"), j.get("name"))
            if not name:
                continue
            vendor, _ = Vendor.objects.update_or_create(
                name=name,
                defaults={"contact_person": s(r.get("contact_person"), j.get("contactPerson"), j.get("contact_person")),
                          "phone": s(r.get("phone"), j.get("phone")),
                          "email": s(r.get("email"), j.get("email")),
                          "city": s(r.get("city"), j.get("city")),
                          "gstin": s(r.get("gstin"), j.get("gstin")),
                          "remarks": s(r.get("remarks"), j.get("remarks")),
                          "active": b(r.get("active"), j.get("active")) or False},
            )
            cats = j.get("categories") or j.get("supplies") or []
            if isinstance(cats, str):
                cats = [cats]
            cat_names = [s(c) for c in cats if s(c)]
            legacy_cat = s(r.get("category"), j.get("category"))
            if legacy_cat and legacy_cat not in cat_names:
                cat_names.append(legacy_cat)
            vendor.categories.clear()
            for cn in cat_names:
                vc, _ = VendorCategory.objects.get_or_create(name=cn[:120], defaults={"active": True})
                vendor.categories.add(vc)
            n += 1
        self.counts["Vendors"] = n

    # ==================================================================
    # 2) EMPLOYEES
    # ==================================================================

    def _import_employees(self):
        self.note("-- Employees --------------------------------------------------")
        self._emp_cache = {}
        rows = self.src.collection_rows("employees", "ams_employees")
        n = 0
        for r in rows:
            j = _parse_json(r.get("data_json")) or {}
            ams_id = s(r.get("ams_id"), j.get("amsId"), j.get("ams_id"))
            if not ams_id:
                self.warn(f"employees: row without amsId skipped ({s(r.get('record_key'))})")
                continue
            name = s(j.get("name"), r.get("full_name"),
                     " ".join(p for p in (j.get("firstName"), j.get("middleName"), j.get("lastName")) if s(p)))
            if not name:
                self.warn(f"employees: {ams_id} has no name - skipped")
                continue
            dept = s(r.get("department"), j.get("department"))
            emp, _ = Employee.objects.update_or_create(
                ams_id=ams_id[:32],
                defaults={
                    "emp_id": s(r.get("emp_id"), j.get("empId"), j.get("emp_id"))[:40],
                    "name": name[:160],
                    "department": self._dept(dept),
                    "designation": s(r.get("designation"), j.get("designation"))[:120],
                    "site": self._site(s(r.get("site"), j.get("site"))),
                    "contact": s(r.get("contact"), j.get("contact"))[:40],
                    "email": s(r.get("email"), j.get("email"))[:160],
                    "status": "Inactive" if s(r.get("status"), j.get("status")).lower() == "inactive" else "Active",
                    "exit_date": dt_date(j.get("exitDate"), r.get("exit_date")),
                    "exit_reason": s(j.get("exitReason"), r.get("exit_reason"))[:60],
                    "exit_remarks": s(j.get("exitRemarks"), r.get("exit_remarks")),
                    "reactivated_date": dt_date(j.get("reactivatedDate"), r.get("reactivated_date")),
                    "reactivation_remarks": s(j.get("reactivationRemarks"), r.get("reactivation_remarks")),
                },
            )
            n += 1
        self.counts["Employees"] = n

        # managers (second pass)
        fixed = 0
        for r in rows:
            j = _parse_json(r.get("data_json")) or {}
            ams_id = s(r.get("ams_id"), j.get("amsId"), j.get("ams_id"))
            mgr = s(r.get("manager_ams_id"), j.get("managerAmsId"), j.get("manager_ams_id"))
            if ams_id and mgr:
                emp = Employee.objects.filter(ams_id=ams_id[:32]).first()
                m = self._emp(mgr)
                if emp and m and emp.manager_id != m.id:
                    emp.manager = m
                    emp.save(update_fields=["manager"])
                    fixed += 1
        if fixed:
            self.note(f"   managers linked: {fixed}")

    # ==================================================================
    # 3) ASSETS + MOBILES
    # ==================================================================

    def _import_asset_rows(self, table, kind, label):
        rows = self.src.collection_rows(kind if kind == "assets" else "mobiles", table)
        n = 0
        for r in rows:
            j = _parse_json(r.get("data_json")) or {}
            ams_asset_id = s(j.get("amsAssetId"), r.get("ams_asset_id"))
            if not ams_asset_id:
                rk = s(r.get("record_key")) or f"LEGACY-{uuid.uuid4().hex[:8].upper()}"
                self.warn(f"{label}: missing amsAssetId - using {rk}")
                ams_asset_id = rk[:48]
            atype = s(j.get("type"), r.get("asset_type"))
            cat = s(j.get("category"), r.get("category"))
            make_name = s(j.get("make"), r.get("make"))
            type_obj = AssetType.objects.filter(name__iexact=atype).first()
            cat_obj = AssetCategory.objects.filter(name__iexact=cat).first()
            make_obj = None
            if make_name:
                make_obj = (AssetMake.objects.filter(name__iexact=make_name, asset_type=type_obj).first()
                            or AssetMake.objects.filter(name__iexact=make_name).first())
            # who holds it
            holder = self._emp(s(j.get("assignedTo"), r.get("assigned_to")))
            sub = self._emp(s(j.get("assignedToSubordinate"), r.get("assigned_to_subordinate")))
            sub_text = s(j.get("assignedSubText"), r.get("assigned_sub_text"))
            dept_hold = s(j.get("assignedDeptText"), j.get("assignedDepartment"), r.get("assigned_department"))
            if not holder and dept_hold:
                sub_text = sub_text or f"Dept: {dept_hold}"
            status = s(j.get("status"), r.get("status")) or "In Store"
            defaults = {
                "kind": kind if kind == "assets" else "mobile",
                "display_id": s(j.get("displayId"), r.get("display_id"))[:32],
                "is_legacy_id": b(j.get("isLegacyId")) or False,
                "category": cat_obj,
                "type": type_obj,
                "make": make_obj,
                "name": s(j.get("name"), r.get("name"))[:160],
                "model": s(j.get("model"), r.get("model"))[:120],
                "model_number": s(j.get("modelNumber"), r.get("model_number"))[:120],
                "imei1": s(j.get("imei1"), r.get("imei1"))[:40],
                "imei2": s(j.get("imei2"), r.get("imei2"))[:40],
                "battery_no": s(j.get("batteryNo"), r.get("battery_no"))[:60],
                "charger_no": s(j.get("chargerNo"), r.get("charger_no"))[:60],
                "serial_number": s(j.get("serialNumber"), r.get("serial_number"))[:120],
                "purchase_site": self._site(s(j.get("purchaseSite"), r.get("purchase_site"))),
                "current_site": self._site(s(j.get("currentSite"), r.get("current_site"))),
                "purchase_date": dt_date(j.get("purchaseDate"), r.get("purchase_date")),
                "warranty_end": dt_date(j.get("warrantyEnd"), r.get("warranty_end")),
                "vendor": self._vendor(s(j.get("vendor"), r.get("vendor"))),
                "purchase_cost": dec(j.get("purchaseCost"), r.get("purchase_cost")),
                "remarks": s(j.get("remarks"), r.get("remarks")),
                "status": status[:24],
                "assigned_to": holder,
                "assigned_to_sub": sub,
                "assigned_sub_text": sub_text[:160],
                "assigned_date": dt_date(j.get("assignedDate"), r.get("assigned_date")),
                "return_date": dt_date(j.get("returnDate"), j.get("return_date")),
                "replaces_reason": s(j.get("replacesReason"), r.get("replaces_reason"))[:60],
                "replaces_note": s(j.get("replacesNote"), r.get("replaces_note")),
                "replaces_purchase_date": dt_date(j.get("replacesPurchaseDate"), r.get("replaces_purchase_date")),
            }
            if kind != "assets":
                defaults["kind"] = "mobile"
            try:
                Asset.objects.update_or_create(ams_asset_id=ams_asset_id[:48], defaults=defaults)
                n += 1
            except Exception as e:
                self.warn(f"{label}: {ams_asset_id} failed: {e}")
        self.counts["Assets" if kind == "assets" else "Mobiles"] = n
        return rows

    def _import_assets_and_mobiles(self):
        self.note("-- Assets & Mobiles -------------------------------------------")
        asset_rows = self._import_asset_rows("ams_assets", "assets", "assets")
        mobile_rows = self._import_asset_rows("ams_mobiles", "mobiles", "mobiles")

        # --- second pass: accessories M2M + replacement chain -----------
        acc_links = repl_links = 0
        for rows, kind in ((asset_rows, "assets"), (mobile_rows, "mobiles")):
            for r in rows:
                j = _parse_json(r.get("data_json")) or {}
                ams_asset_id = s(j.get("amsAssetId"), r.get("ams_asset_id"))
                if not ams_asset_id:
                    continue
                a = Asset.objects.filter(ams_asset_id=ams_asset_id[:48]).first()
                if not a:
                    continue
                # accessories are stored as NAME strings in the old portal
                accs = j.get("accessories") or []
                if isinstance(accs, str):
                    accs = [accs] if accs.strip() else []
                want = set()
                for nm in accs:
                    nm = s(nm)
                    if not nm:
                        continue
                    acc = (Accessory.objects.filter(name__iexact=nm).first()
                           or Accessory.objects.filter(code__iexact=nm).first())
                    if acc:
                        want.add(acc.id)
                    else:
                        self.warn(f"asset {ams_asset_id}: accessory '{nm}' not found in new accessories master")
                if want != set(a.accessories.values_list("id", flat=True)):
                    a.accessories.set(want)
                    acc_links += 1
                # replacement chain
                rep_ref = s(j.get("replacesAssetId"), r.get("replaces_asset"))
                if rep_ref:
                    rep = (Asset.objects.filter(ams_asset_id__iexact=rep_ref).first()
                           or Asset.objects.filter(display_id__iexact=rep_ref).first())
                    if rep and a.replaces_asset_id != rep.id:
                        a.replaces_asset = rep
                        a.save(update_fields=["replaces_asset"])
                        repl_links += 1
                # linked SIM (mobiles only; old field simMobileNo)
                if kind == "mobiles":
                    sim_no = s(j.get("simMobileNo"), r.get("sim_mobile_no"))
                    sim = SimCard.objects.filter(mobile_number=sim_no).first() if sim_no else None
                    if sim and a.sim_id != sim.id:
                        a.sim = sim
                        a.save(update_fields=["sim"])
        if acc_links:
            self.note(f"   accessory sets applied: {acc_links}")
        if repl_links:
            self.note(f"   replacement links: {repl_links}")

    # ==================================================================
    # 4) SIM CARDS
    # ==================================================================

    def _import_sim_cards(self):
        self.note("-- SIM cards --------------------------------------------------")
        rows = self.src.collection_rows("simCards", "ams_sim_cards")
        n = 0
        for r in rows:
            j = _parse_json(r.get("data_json")) or {}
            sim_id = s(j.get("simId"), r.get("sim_id"))
            number = s(j.get("mobileNumber"), r.get("mobile_number"))
            if not sim_id or not number:
                self.warn(f"sims: row without simId/mobileNumber skipped ({s(r.get('record_key'))})")
                continue
            plan_name = s(r.get("plan_name"), j.get("plan"))
            linked = s(j.get("linkedMobileId"), r.get("linked_mobile_id"))
            linked_obj = (Asset.objects.filter(ams_asset_id__iexact=linked).first()
                          or Asset.objects.filter(display_id__iexact=linked).first()) if linked else None
            status = s(j.get("status"), r.get("status")) or "In Store"
            try:
                SimCard.objects.update_or_create(
                    sim_id=sim_id[:16],
                    defaults={
                        "mobile_number": number[:24],
                        "iccid": s(j.get("iccid"), r.get("iccid"))[:60],
                        "operator": SimOperator.objects.filter(name__iexact=s(j.get("operator"), r.get("operator"))).first(),
                        "plan": SimPlan.objects.filter(name__iexact=plan_name).first(),
                        "status": status[:10],
                        "site": self._site(s(j.get("site"), r.get("site"))),
                        "activation_date": dt_date(j.get("activationDate"), r.get("activation_date")),
                        "vendor": self._vendor(s(j.get("vendor"), r.get("vendor"))),
                        "cost": dec(j.get("cost"), r.get("cost")),
                        "remarks": s(j.get("remarks"), r.get("remarks")),
                        "assigned_to": self._emp(s(j.get("assignedTo"), r.get("assigned_to"))),
                        "assigned_to_sub": self._emp(s(j.get("assignedToSubordinate"), r.get("assigned_to_subordinate"))),
                        "assigned_sub_text": s(j.get("assignedSubText"), r.get("assigned_sub_text"))[:160],
                        "assigned_date": dt_date(j.get("assignedDate"), r.get("assigned_date")),
                        "linked_mobile": linked_obj,
                        "personal_mobile": b(j.get("personalMobile"), r.get("personal_mobile")) or False,
                        "return_date": dt_date(j.get("returnDate"), j.get("return_date")),
                    },
                )
                n += 1
            except Exception as e:
                self.warn(f"sims: {sim_id} ({number}) failed: {e}")
        self.counts["SIM cards"] = n

        # SIMs exist now - link mobiles to their SIM (old field simMobileNo)
        linked = 0
        for r in self.src.collection_rows("mobiles", "ams_mobiles"):
            j = _parse_json(r.get("data_json")) or {}
            ams_asset_id = s(j.get("amsAssetId"), r.get("ams_asset_id"))
            sim_no = s(j.get("simMobileNo"), r.get("sim_mobile_no"))
            if not ams_asset_id or not sim_no:
                continue
            a = Asset.objects.filter(ams_asset_id=ams_asset_id[:48], kind="mobile").first()
            sim = SimCard.objects.filter(mobile_number=sim_no).first()
            if a and sim and a.sim_id != sim.id:
                a.sim = sim
                a.save(update_fields=["sim"])
                linked += 1
        if linked:
            self.note(f"   mobiles linked to SIMs: {linked}")

    # ==================================================================
    # 5) LIFECYCLE EVENTS (per-item history[] + global assignmentEvents)
    # ==================================================================

    def _add_event(self, item_kind, item_key, item_label, date_val, action,
                   emp, emp_label, emp_dept, status_label, accessories, note,
                   actor_username="", actor_role=""):
        if not date_val:
            date_val = dt_date(date.today().isoformat())
        key = (item_kind, (item_key or "").lower(), str(date_val), (action or "").lower(),
               (emp_label or "").lower(), (status_label or "").lower())
        if key in self._event_keys:
            return False
        self._event_keys.add(key)
        # also skip events already stored from a previous import run
        if not self.dry_run and LifecycleEvent.objects.filter(
            item_kind=item_kind, item_key__iexact=(item_key or ""), date=date_val,
            action__iexact=(action or ""), emp_label__iexact=(emp_label or ""),
            status_label__iexact=(status_label or ""),
        ).exists():
            return False
        LifecycleEvent.objects.create(
            item_kind=item_kind, item_key=(item_key or "")[:48],
            item_label=(item_label or "")[:64], date=date_val,
            action=(action or "")[:60], event_type=classify_event(action),
            emp=emp, emp_label=(emp_label or "")[:160], emp_dept=(emp_dept or "")[:120],
            status_label=(status_label or "")[:40],
            accessories=accessories if isinstance(accessories, list) else ([accessories] if accessories else []),
            note=note or "", actor_username=(actor_username or "")[:60], actor_role=(actor_role or "")[:30],
        )
        return True

    def _import_lifecycle_events(self):
        self.note("-- Lifecycle history ------------------------------------------")
        self._event_keys = set()
        n = 0
        # per-item history[] kept inside each asset/mobile/sim record
        for rows, kind, table in (
            (self.src.collection_rows("assets", "ams_assets"), "asset", "ams_assets"),
            (self.src.collection_rows("mobiles", "ams_mobiles"), "mobile", "ams_mobiles"),
            (self.src.collection_rows("simCards", "ams_sim_cards"), "sim", "ams_sim_cards"),
        ):
            for r in rows:
                j = _parse_json(r.get("data_json")) or {}
                item_key = s(j.get("amsAssetId"), r.get("ams_asset_id")) if kind != "sim" else s(j.get("simId"), r.get("sim_id"))
                if not item_key:
                    continue
                label = s(j.get("displayId"), j.get("id"), r.get("display_id")) if kind != "sim" else item_key
                for h in j.get("history") or []:
                    if not isinstance(h, dict):
                        continue
                    emp = self._emp(s(h.get("empId"), h.get("empAmsId")))
                    accs = h.get("accessories") or []
                    if isinstance(accs, str):
                        accs = [x.strip() for x in accs.split(",") if x.strip()]
                    if self._add_event(kind, item_key, label, dt_date(h.get("date")), s(h.get("action")),
                                       emp, s(h.get("empId")), s(h.get("empDept")),
                                       s(h.get("statusLabel")), accs, s(h.get("note"))):
                        n += 1
        # global assignment events (de-duplicated against history above)
        for r in self.src.collection_rows("assignmentEvents", "ams_assignment_events"):
            j = _parse_json(r.get("data_json")) or {}
            kind = s(r.get("item_kind"), j.get("itemKind")) or "asset"
            if kind not in ("asset", "mobile", "sim"):
                kind = "asset"
            item_key = s(r.get("item_key"), j.get("itemKey"))
            emp = self._emp(s(r.get("assigned_to"), j.get("assignedTo"))) or self._emp(s(r.get("emp_id"), j.get("empId")))
            accs = j.get("accessories") or s(r.get("accessories")) or []
            if isinstance(accs, str):
                accs = [x.strip() for x in accs.split(",") if x.strip()]
            if self._add_event(kind, item_key,
                               s(r.get("item_id_full"), j.get("assetIdFull"), item_key),
                               dt_date(r.get("event_date"), j.get("date")),
                               s(r.get("action"), j.get("action")),
                               emp, s(r.get("emp_id"), j.get("empId"), r.get("emp_name"), j.get("empName")),
                               s(r.get("emp_dept"), j.get("empDept")),
                               s(r.get("status_after"), j.get("statusLabel")),
                               accs, s(r.get("remarks"), j.get("remarks")),
                               s(r.get("actor_username"), j.get("actorUsername")),
                               s(r.get("actor_role"), j.get("actorRole"))):
                n += 1
        self.counts["Lifecycle events"] = n

    # ==================================================================
    # 6) CONSUMABLES / SPARE PARTS / MOVEMENTS
    # ==================================================================

    def _import_stock(self):
        self.note("-- Consumables & Spare parts ----------------------------------")
        n = 0
        for r in self.src.collection_rows("consumables", "ams_consumables"):
            j = _parse_json(r.get("data_json")) or {}
            code = s(j.get("consumableId"), r.get("consumable_id"))
            name = s(j.get("name"), r.get("name"))
            if not code or not name:
                self.warn(f"consumables: row skipped ({s(r.get('record_key'))})")
                continue
            qty = dec(j.get("qty"), r.get("qty"))
            reorder = dec(j.get("reorderLevel"), r.get("reorder_level"))
            Consumable.objects.update_or_create(
                code=code[:16],
                defaults={
                    "name": name[:160],
                    "category": ConsumableCategory.objects.filter(name__iexact=s(j.get("category"), r.get("category"))).first(),
                    "unit": UnitOfMeasure.objects.filter(name__iexact=s(j.get("unit"), r.get("unit"))).first(),
                    "site": self._site(s(j.get("site"), r.get("site"))),
                    "qty": qty if qty is not None else Decimal("0"),
                    "reorder_level": reorder if reorder is not None else Decimal("0"),
                    "restock_date": dt_date(j.get("restockDate"), r.get("restock_date")),
                    "warranty_date": dt_date(j.get("warrantyDate"), r.get("warranty_date")),
                    "unit_cost": dec(j.get("unitCost"), r.get("unit_cost")),
                    "vendor": self._vendor(s(j.get("vendor"), r.get("vendor"))),
                    "remarks": s(j.get("remarks"), r.get("remarks")),
                    "active": b(j.get("active")) or True,
                },
            )
            n += 1
        self.counts["Consumables"] = n

        n = 0
        for r in self.src.collection_rows("spareParts", "ams_spare_parts"):
            j = _parse_json(r.get("data_json")) or {}
            code = s(j.get("partId"), r.get("part_id"))
            name = s(j.get("name"), r.get("name"))
            if not code or not name:
                self.warn(f"spare parts: row skipped ({s(r.get('record_key'))})")
                continue
            qty = dec(j.get("qty"), r.get("qty"))
            reorder = dec(j.get("reorderLevel"), r.get("reorder_level"))
            SparePart.objects.update_or_create(
                code=code[:16],
                defaults={
                    "name": name[:160],
                    "asset_type": AssetType.objects.filter(name__iexact=s(j.get("assetType"), r.get("asset_type"))).first(),
                    "category": SparePartCategory.objects.filter(name__iexact=s(j.get("category"), r.get("category"))).first(),
                    "site": self._site(s(j.get("site"), r.get("site"))),
                    "qty": qty if qty is not None else Decimal("0"),
                    "reorder_level": reorder if reorder is not None else Decimal("0"),
                    "restock_date": dt_date(j.get("restockDate"), r.get("restock_date")),
                    "warranty_date": dt_date(j.get("warrantyDate"), r.get("warranty_date")),
                    "unit_cost": dec(j.get("unitCost"), r.get("unit_cost")),
                    "vendor": self._vendor(s(j.get("vendor"), r.get("vendor"))),
                    "remarks": s(j.get("remarks"), r.get("remarks")),
                    "active": b(j.get("active")) or True,
                },
            )
            n += 1
        self.counts["Spare parts"] = n

        # movement logs (append-only: skipped if this DB already has logs)
        if not self.wiped and not self.dry_run and StockMovement.objects.exists():
            self.note("   movement logs already present - skipped (use --wipe to replace)")
            self.counts["Stock movements"] = 0
            return
        n = 0
        for r in self.src.collection_rows("consumableLog", "ams_consumable_log"):
            j = _parse_json(r.get("data_json")) or {}
            code = s(j.get("consumableId"), r.get("consumable_id"))[:16]
            item = Consumable.objects.filter(code__iexact=code).first()
            if not item:
                self.warn(f"consumable log: no consumable '{code}' - skipped")
                continue
            log_type = s(j.get("type"), r.get("log_type")) or "Used"
            StockMovement.objects.create(
                kind="consumable", item_id=item.id, item_code=item.code,
                name=item.name[:160], site=s(j.get("site"), r.get("site"))[:120],
                type="Restocked" if log_type.lower().startswith("restock") else "Used",
                qty=dec(j.get("qty"), r.get("qty")) or Decimal("0"),
                by=s(j.get("by"), r.get("by_whom"))[:200],
                remarks=s(j.get("remarks"), r.get("remarks")),
                date=dt_date(j.get("date"), r.get("log_date")) or date.today(),
            )
            n += 1
        for r in self.src.collection_rows("sparePartLog", "ams_spare_part_log"):
            j = _parse_json(r.get("data_json")) or {}
            code = s(j.get("partId"), r.get("part_id"))[:16]
            item = SparePart.objects.filter(code__iexact=code).first()
            if not item:
                self.warn(f"spare part log: no spare part '{code}' - skipped")
                continue
            log_type = s(j.get("type"), r.get("log_type")) or "Used"
            asset_ref = s(j.get("assetBaseId"), r.get("asset_base_id"))
            asset_obj = (Asset.objects.filter(ams_asset_id__iexact=asset_ref).first()
                         or Asset.objects.filter(display_id__iexact=asset_ref).first()) if asset_ref else None
            StockMovement.objects.create(
                kind="sparepart", item_id=item.id, item_code=item.code,
                name=item.name[:160], site=s(j.get("site"), r.get("site"))[:120],
                type="Restocked" if log_type.lower().startswith("restock") else "Used",
                qty=dec(j.get("qty"), r.get("qty")) or Decimal("0"),
                by=s(j.get("by"), r.get("by_whom"))[:200],
                remarks=s(j.get("remarks"), r.get("remarks")),
                asset=asset_obj,
                asset_id_snapshot=s(j.get("assetIdSnapshot"), r.get("asset_id_snapshot"))[:64],
                date=dt_date(j.get("date"), r.get("log_date")) or date.today(),
            )
            n += 1
        self.counts["Stock movements"] = n

    # ==================================================================
    # 7) EXIT RECORDS
    # ==================================================================

    def _import_exit_records(self):
        self.note("-- Exit records -----------------------------------------------")
        n = 0
        for r in self.src.collection_rows("exitRecords", "ams_exit_records"):
            j = _parse_json(r.get("data_json")) or {}
            exit_id = s(j.get("exitId"), r.get("exit_id"))
            ams_id = s(j.get("amsId"), r.get("ams_id"))
            emp = self._emp(ams_id)
            if not exit_id or emp is None:
                self.warn(f"exit records: {exit_id or '(no id)'} has no matching employee ({ams_id}) - skipped")
                continue
            exit_date = dt_date(j.get("exitDate"), r.get("exit_date"))
            if exit_date is None:
                self.warn(f"exit records: {exit_id} has no exit date - skipped")
                continue
            ExitRecord.objects.update_or_create(
                exit_id=exit_id[:16],
                defaults={
                    "employee": emp,
                    "ams_id": emp.ams_id,
                    "emp_id": s(j.get("empId"), r.get("emp_id"), emp.emp_id)[:40],
                    "emp_name": s(j.get("empName"), r.get("emp_name"), emp.name)[:160],
                    "emp_dept": s(j.get("empDept"), r.get("emp_dept"))[:120],
                    "emp_designation": s(j.get("empDesignation"), j.get("designation"))[:120],
                    "exit_date": exit_date,
                    "exit_reason": s(j.get("exitReason"), j.get("reason"))[:60],
                    "exit_remarks": s(j.get("exitRemarks"), j.get("remarks")),
                    "facilities_disabled": j.get("facilitiesDisabled") if isinstance(j.get("facilitiesDisabled"), list) else [],
                    "facilities_na": j.get("facilitiesNa") if isinstance(j.get("facilitiesNa"), list) else [],
                    "direct_assets": j.get("directAssets") if isinstance(j.get("directAssets"), list) else [],
                    "direct_mobiles": j.get("directMobiles") if isinstance(j.get("directMobiles"), list) else [],
                    "direct_sims": j.get("directSims") if isinstance(j.get("directSims"), list) else [],
                    "subordinate_assets": j.get("subordinateAssets") if isinstance(j.get("subordinateAssets"), list) else [],
                    "team_transferred_to": j.get("teamTransferredTo"),
                    "reactivated": b(j.get("reactivated")) or False,
                },
            )
            n += 1
        self.counts["Exit records"] = n

    # ==================================================================
    # 8) USERS (Django User + UserProfile; old password hashes)
    # ==================================================================

    def _import_users(self):
        self.note("-- Users ------------------------------------------------------")
        profiles = {s(p.get("record_key"), _parse_json(p.get("data_json")).get("username")): p
                    for p in self.src.collection_rows("users", "ams_user_profiles")}
        cred = {s(u.get("username")): u for u in (self.src.rows("ams_users") if self.src.has_table("ams_users") else [])}
        n = 0
        for username, p in profiles.items():
            if not username:
                continue
            j = _parse_json(p.get("data_json")) or {}
            u_row = cred.get(username, {})
            role = s(p.get("role"), j.get("role"), u_row.get("role")) or "Standard User"
            email = s(p.get("email"), j.get("email"), u_row.get("email"))[:160]
            active = b(p.get("active"), j.get("active"), u_row.get("active"))
            active = True if active is None else active
            user = User.objects.filter(username=username).first()
            if user is None:
                user = User(username=username)
            user.email = email or user.email
            user.is_active = active
            # password: reuse the OLD PBKDF2 hash so the old password works
            p_hash = s(u_row.get("password_hash"))
            p_salt = s(u_row.get("password_salt"))
            if p_hash and p_salt and "$" not in p_hash:
                user.password = f"ams_legacy_pbkdf2$100000${p_salt.upper()}${p_hash.upper()}"
            elif user.pk is None:
                user.set_unusable_password()
            user.save()
            linked_ref = s(p.get("linked_employee"), j.get("linkedEmployee"), u_row.get("linked_employee"))
            prof = ensure_profile(user)
            prof.role = role[:30]
            prof.display_name = s(p.get("display_name"), j.get("displayName"), u_row.get("display_name"))[:200]
            prof.linked_employee = self._emp(linked_ref)
            prof.site = self._site(s(p.get("site"), j.get("site"), u_row.get("site")))
            prof.email = email
            prof.contact_no = s(p.get("contact_no"), j.get("contactNo"))[:50]
            prof.address = s(p.get("address"), j.get("address"))[:500]
            prof.gender = s(p.get("gender"), j.get("gender"))[:10]
            prof.dob = dt_date(p.get("dob"), j.get("dob"))
            allowed = j.get("allowedPages")
            prof.allowed_pages = allowed if isinstance(allowed, list) else None
            prof.save()
            n += 1
        self.counts["Users"] = n
        if cred:
            missing_hash = [u for u, row in cred.items() if not s(row.get("password_hash"))]
            if missing_hash:
                self.warn(f"users without stored hash (cannot log in until re-set): {', '.join(missing_hash)}")

    # ==================================================================
    # 9) COMPANY / REPORT PREFS / (logo + banner from base64 data URLs)
    # ==================================================================

    def _save_data_url(self, data_url, base_name):
        m = re.match(r"^data:image/([a-zA-Z0-9.+-]+);base64,(.*)$", data_url or "", re.S)
        if not m:
            return None
        ext = {"jpeg": "jpg", "svg+xml": "svg"}.get(m.group(1).lower(), m.group(1).lower())
        ext = re.sub(r"[^a-z0-9]", "", ext)[:5] or "png"
        try:
            blob = base64.b64decode(m.group(2))
        except (ValueError, TypeError):
            return None
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        fname = f"company/{base_name}.{ext}"
        path = default_storage.save(fname, ContentFile(blob))
        return path

    def _import_company_and_prefs(self):
        self.note("-- Company / report prefs -------------------------------------")
        row = self.src.company_row()
        if row:
            j = _parse_json(row.get("data_json")) or {}
            comp = Company.get_solo() if not self.dry_run else Company()
            comp.name = s(j.get("companyName"), row.get("name"), j.get("name"))[:200]
            comp.slogan = s(j.get("slogan"), row.get("slogan"))[:200]
            comp.address = s(j.get("address"), row.get("address"))
            comp.hr_admin_contact = s(j.get("hrAdminContact"), row.get("hr_admin_contact"))[:60]
            comp.head_title = s(j.get("headTitle"), row.get("head_title"))[:120]
            comp.head_contact = s(j.get("headContact"), row.get("head_contact"))[:60]
            for field, keys, base in (("logo", ("logoDataUrl", "logo"), "legacy-logo"),
                                      ("banner", ("bannerDataUrl", "banner"), "legacy-banner")):
                data_url = s(j.get(keys[0]), j.get(keys[1]))
                if data_url and not self.dry_run:
                    try:
                        path = self._save_data_url(data_url, base)
                        if path:
                            setattr(comp, field, path)
                        else:
                            self.warn(f"company: {field} data URL could not be decoded")
                    except Exception as e:
                        self.warn(f"company: saving {field} failed: {e}")
            if not self.dry_run:
                comp.save()
            self.counts["Company profile"] = 1
            if self.dry_run:
                self.note(f"   company: {comp.name} (logo/banner data URLs {'found' if s(j.get('logoDataUrl')) else 'not set'})")

        docs = self.src.documents()
        rp = docs.get("reportPrefs")
        if isinstance(rp, dict) and not self.dry_run:
            prefs = ReportPrefs.get_solo()
            prefs.style = s(rp.get("style"))[:10] or "classic"
            prefs.show_logo = b(rp.get("showLogo"), rp.get("show_logo")) or False
            prefs.show_name = b(rp.get("showName"), rp.get("show_name")) or False
            prefs.show_slogan = b(rp.get("showSlogan"), rp.get("show_slogan")) or False
            prefs.save()
            self.counts["Report prefs"] = 1

    # ==================================================================
    # 10) ROLE ACCESS MATRIX + PER-USER PAGE OVERRIDES
    # ==================================================================

    def _import_role_access_and_rights(self):
        self.note("-- Role access / user page rights -----------------------------")
        docs = self.src.documents()
        ra = docs.get("roleAccess")
        n = 0
        if isinstance(ra, dict):
            for role, pages in ra.items():
                if not isinstance(pages, dict):
                    continue
                for page_key, level in pages.items():
                    if page_key not in PAGE_KEYS:
                        continue
                    level = s(level) or "none"
                    if level not in ("none", "view", "full"):
                        level = "none"
                    if not self.dry_run:
                        RoleAccess.objects.update_or_create(page_key=page_key, role=role[:30], defaults={"level": level})
                    n += 1
        if n == 0 and not self.dry_run:
            # nothing in the old DB - keep the recommended matrix seeded
            for key in PAGE_KEYS:
                for role, level in RECOMMENDED_MATRIX.get(key, {}).items():
                    RoleAccess.objects.update_or_create(page_key=key, role=role, defaults={"level": level})
            self.note("   (no roleAccess doc in legacy DB - recommended matrix applied)")
        self.counts["Role access rows"] = n

        ar = docs.get("accessRights")
        if isinstance(ar, dict):
            k = 0
            for username, pages in ar.items():
                if not isinstance(pages, list):
                    continue
                if self.dry_run:
                    k += 1
                    continue
                prof = UserProfile.objects.filter(user__username=s(username)).first()
                if prof:
                    prof.allowed_pages = [s(x) for x in pages if s(x)]
                    prof.save(update_fields=["allowed_pages"])
                    k += 1
            if k:
                self.counts["User page overrides"] = k

    # ==================================================================
    # 11) ACTIVITY LOG
    # ==================================================================

    def _import_activity_log(self):
        self.note("-- Activity log -----------------------------------------------")
        if not self.wiped and not self.dry_run and ActivityLog.objects.exists():
            self.note("   activity log already present - skipped (use --wipe to replace)")
            self.counts["Activity log entries"] = 0
            return
        rows = self.src.collection_rows("activityLog", "ams_activity_log")
        n = 0
        for r in rows:
            j = _parse_json(r.get("data_json")) or {}
            message = s(j.get("message"), r.get("message"))
            if not message:
                continue
            t = s(j.get("type"), r.get("log_type"), j.get("logType")) or "info"
            if t not in ("success", "warning", "danger", "info"):
                t = "info"
            when = dt_time(j.get("time"), r.get("log_time")) or timezone.now()
            ActivityLog.objects.create(
                time=when,
                actor_username=s(j.get("actorUsername"), r.get("actor_username"))[:60],
                actor_role=s(j.get("actorRole"), r.get("actor_role"))[:30],
                page=s(j.get("page"), r.get("page"))[:80],
                type=t, message=message,
            )
            n += 1
        self.counts["Activity log entries"] = n

    # ------------------------------------------------------------------

    def _report(self):
        self.note("")
        self.note("================= IMPORT SUMMARY =================")
        for label, n in self.counts.items():
            self.note(f"  {label:<24} {n}")
        if self.dry_run:
            self.note("  (dry run - nothing was written)")
        if self.warnings:
            self.note(f"  warnings: {len(self.warnings)}")
            for w in self.warnings[:30]:
                self.note(f"    ! {w}")
            if len(self.warnings) > 30:
                self.note(f"    ... and {len(self.warnings) - 30} more")
        self.note("==================================================")
