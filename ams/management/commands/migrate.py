"""
#-------------- Start Code for : SELF-HEALING MIGRATE (ams/management/commands/migrate.py)

A thin, drop-in wrapper around Django's standard `migrate` command.
It is invoked for EVERY `python manage.py migrate` call (also from
VS Code's integrated terminal, .bat helpers and scripts) and adds two
pre-flight rescues before handing over to the original command:

  1. AUTO-SYNC (fixes error 2714 / SQLSTATE 42S01)
     "There is already an object named 'ams_company' in the database"

     Happens when the AMS-TEST-2 database already contains tables but
     the django_migrations bookkeeping does not match this project -
     the normal result of restoring the old AMS-Test backup over the
     database, or of pre-creating tables with
     sqlserver/02-create-all-tables.sql and losing the records.

     `migrate` can only CREATE tables; it cannot adopt existing ones.
     So when the pre-flight detects that a pending migration would
     create a table that ALREADY exists, it runs the dbrepair sync
     first (create missing tables, add missing columns, mark every
     migration applied - never touches existing rows) and only then
     runs the standard migrate, which now finds nothing conflicting.

  2. AUTO-CREATE DATABASE (fixes ODBC error 4060)
     "Cannot open database 'AMS-TEST-2' requested by the login"

     On SQL Server the DATABASE itself must exist before migrate can
     run. When the login works but the database is missing, the
     pre-flight creates it (via the master database, same login) and
     migrate continues on a fresh database.

Scenarios and what the pre-flight does:
  * fresh empty database                  -> nothing, straight to migrate
  * fully migrated database               -> nothing (No migrations to apply)
  * database created by the SQL scripts   -> nothing (records already match)
    WITH their django_migrations rows
  * restored old AMS-Test backup over
    AMS-TEST-2 / pre-created tables
    without records                       -> dbrepair sync, then migrate
  * database missing on SQL Server        -> database is created, migrate
  * server unreachable / login wrong      -> nothing; migrate raises its
                                             usual precise error

Every option is passed through unchanged:
    python manage.py migrate
    python manage.py migrate --plan / --check / --fake / --fake-initial
    python manage.py migrate ams 0002 ...
Explicit targets (--plan/--check/--prune/--fake*/app label/migration name)
skip the auto-sync entirely - those callers know exactly what they want.

Set the environment variable AMS_NO_AUTOHEAL=1 to disable the pre-flight
and get the stock Django behaviour back.

Windows users: Repair-Database.bat runs the same sync on demand
(python manage.py dbrepair) - auto-heal and the .bat use ONE code path.
#-------------- End of the code for : SELF-HEALING MIGRATE ----------------
"""

import os
import re

from django.apps import apps
from django.core.management import call_command
from django.core.management.commands.migrate import Command as _DjangoMigrate
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations import CreateModel
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder


class Command(_DjangoMigrate):
    help = _DjangoMigrate.help + (
        " Auto-syncs a database that already contains tables (restored "
        "backup) and auto-creates a missing SQL Server database before "
        "migrating - error 2714 'There is already an object named ...' "
        "can no longer happen. See dbrepair for the manual equivalent."
    )

    # ------------------------------------------------------------ entry
    def handle(self, *args, **options):
        skip_healing = (
            options.get("plan")
            or options.get("check")
            or options.get("prune")
            or options.get("fake")
            or options.get("fake_initial")
            or args  # explicit "migrate ams 0002 ..." - caller knows best
            or os.environ.get("AMS_NO_AUTOHEAL", "").strip() in ("1", "yes", "true")
        )
        if not skip_healing:
            try:
                self._preflight(options.get("database") or DEFAULT_DB_ALIAS)
            except Exception:
                # The pre-flight must NEVER hide a real problem: if anything
                # at all goes wrong here, the standard migrate still runs and
                # raises its usual precise error for the user.
                pass
        return super().handle(*args, **options)

    # ------------------------------------------------------------ step 1
    def _preflight(self, db_alias):
        try:
            connection = connections[db_alias]
        except Exception:
            return

        # ---- can we reach the database at all?
        try:
            with connection.cursor() as cursor:
                live = {t.lower() for t in
                        connection.introspection.table_names(cursor)}
        except Exception as exc:
            self._maybe_create_database(connection, exc)
            return  # unreachable server / wrong login: let migrate speak

        if not live:
            return  # fresh database - migrate will create everything

        # ---- would any PENDING migration collide with an existing table?
        conflict = self._pending_table_conflicts(db_alias, live)
        if not conflict:
            return  # nothing migrate could trip over

        shown = ", ".join(sorted(conflict)[:6]) + \
            (" ..." if len(conflict) > 6 else "")
        self.stdout.write("")
        self.stdout.write("=" * 64)
        self.stdout.write(self.style.WARNING(
            "  migrate pre-flight: the database already contains tables that"
        ))
        self.stdout.write(self.style.WARNING(
            f"  the pending migrations would create: {shown}"
        ))
        self.stdout.write(
            "  (this is the state after restoring the old AMS-Test backup -"
        )
        self.stdout.write(
            "   without the sync, migrate would abort with error 2714"
        )
        self.stdout.write(
            "   \"There is already an object named ... in the database\")"
        )
        self.stdout.write(
            "  Running the dbrepair sync first - existing rows are never"
        )
        self.stdout.write(
            "  deleted or overwritten. Disable with AMS_NO_AUTOHEAL=1."
        )
        self.stdout.write("=" * 64)
        self.stdout.write("")

        call_command("dbrepair")
        self.stdout.write("")
        self.stdout.write("  Sync finished - continuing with the standard"
                          " migrate.")

    # ------------------------------------------------------------ helpers
    def _pending_table_conflicts(self, db_alias, live_tables):
        """Table names that pending migrations would CREATE and that are
        already present in the database - the exact precondition of
        error 2714. Returns a set of colliding table names (lower-case)."""
        connection = connections[db_alias]
        recorder = MigrationRecorder(connection)
        try:
            applied_fn = recorder.applied_migrations
            applied = applied_fn() if callable(applied_fn) else applied_fn
        except Exception:
            applied = {}  # django_migrations missing/unreadable

        loader = MigrationLoader(connection)
        pending = [(key, mig) for key, mig in loader.disk_migrations.items()
                   if key not in applied]
        if not pending:
            return set()

        created = set()
        for (_app, _name), mig in pending:
            for op in mig.operations:
                if not isinstance(op, CreateModel):
                    continue
                try:
                    model = apps.get_model(mig.app_label, op.name)
                except LookupError:
                    continue
                table = model._meta.db_table.lower()
                if table not in created:
                    created.add(table)
        return {t for t in created if t in live_tables}

    def _maybe_create_database(self, connection, exc):
        """SQL Server only: create the configured database when the ODBC
        error says it does not exist (error 4060, 'Cannot open database
        ... requested by the login'). Any other failure is ignored so the
        standard migrate error still reaches the user."""
        if connection.vendor != "mssql":
            return
        from amstest2 import dbconfig

        info = dbconfig.resolve_db()
        if info["engine"] != "mssql":
            return
        text = " ".join(str(a) for a in (getattr(exc, "args", None) or ()))
        if "cannot open database" not in text.lower():
            return
        dbname = info["db_name"]
        if dbname.lower() not in text.lower():
            return
        if not re.match(r"^[A-Za-z0-9_\- ]{1,100}$", dbname):
            return  # never quote something we cannot trust

        try:
            import pyodbc

            server = info["host"] + (f",{info['port']}" if info["port"] else "")
            driver = info["driver"] or dbconfig.DEFAULT_DRIVER
            parts = [f"DRIVER={{{driver}}}", f"SERVER={server}",
                     "DATABASE=master"]
            if info["trusted"] or not info["user"]:
                parts.append("Trusted_Connection=yes")
            else:
                parts.append(f"UID={info['user']}")
                parts.append(f"PWD={info['password']}")
            parts.append(info["extra_params"])
            master = pyodbc.connect(
                ";".join(p for p in parts if p),
                timeout=dbconfig.CONNECT_TIMEOUT)
            try:
                master.autocommit = True  # CREATE DATABASE needs autocommit
                master.execute(
                    f"IF DB_ID(N'{dbname}') IS NULL "
                    f"CREATE DATABASE [{dbname.replace(']', ']]')}]"
                )
            finally:
                master.close()
            self.stdout.write(self.style.SUCCESS(
                f"  Database {dbname} did not exist - created it. "
                f"Continuing with migrate."))
        except Exception:
            # Cannot create it (no rights, server unreachable, ...)? The
            # standard migrate error tells the user exactly why.
            return
