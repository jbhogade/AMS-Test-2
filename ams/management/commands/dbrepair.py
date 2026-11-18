"""
#-------------- Start Code for : DB REPAIR (ams/management/commands/dbrepair.py)

Bring an existing AMS-TEST-2 database in line with the Django models,
whatever its current state is, WITHOUT touching existing rows.

Why it exists
-------------
`python manage.py migrate` fails with SQL error 2714 / SQLSTATE 42S01
("There is already an object named 'ams_company' in the database") when
the database already contains tables but the django_migrations bookkeeping
does not match this project. That is the normal result of restoring the
old AMS-Test database backup over AMS-TEST-2, or of pre-creating tables
with sqlserver/02-create-all-tables.sql and then losing the migration
records (a .bak restore wipes them).

`migrate` alone cannot recover from this: it can only CREATE tables, it
cannot add missing columns to tables that already exist, and it refuses
to run at all while its records are missing. dbrepair does the whole job:

  Phase 1  Compare the live database with the Django models
           (tables + columns, engine-agnostic introspection).
  Phase 2  Create missing tables with the exact DDL `migrate` would use
           (schema_editor.create_model, in FK-dependency order).
  Phase 3  Add missing columns with the same operations migrate uses
           (schema_editor.add_field). A NOT NULL column without a default
           is added as nullable when the table already holds rows, so no
           data can ever be lost or blocked.
  Phase 4  Add missing unique constraints / indexes (best effort - a
           constraint that old data would violate is reported, not forced).
  Phase 5  Mark every migration as applied (the `--fake` bookkeeping), so
           a following `migrate` reports "No migrations to apply".

Existing rows are never deleted or overwritten. Columns and tables that
exist in the database but not in the models (leftovers of the old AMS-Test
schema) are only reported, never dropped.

Run:
    python manage.py dbrepair              (repair + record migrations)
    python manage.py dbrepair --dry-run    (show the plan, change nothing)
    python manage.py dbrepair --no-record  (sync the schema only)
    python manage.py dbrepair --app ams    (limit to one app)

Windows users can simply double-click  Repair-Database.bat.

Safe to run repeatedly - a second run finds nothing to do.
#-------------- End of the code for : DB REPAIR (ams/management/commands/dbrepair.py) --
"""

import copy

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, migrations, models
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder


def ok(label, detail=""):
    print(f"  [OK]   {label}" + (f" - {detail}" if detail else ""))


def warn(label, detail=""):
    print(f"  [WARN] {label}" + (f" - {detail}" if detail else ""))


def info(label, detail=""):
    print(f"  [..]   {label}" + (f" - {detail}" if detail else ""))


# Families of Django field classes that share one SQL column type. Used
# ONLY to report schema differences readably ("column is TEXT, the model
# wants NVARCHAR"); no ALTER is ever derived from them.
_INT_FAMILY = {
    "AutoField", "BigAutoField", "SmallIntegerField", "PositiveSmallIntegerField",
    "IntegerField", "PositiveIntegerField", "BigIntegerField",
    "PositiveBigIntegerField", "ForeignKey", "OneToOneField",
}
_CHAR_FAMILY = {
    "CharField", "EmailField", "SlugField", "URLField", "FileField",
    "FilePathField", "ImageField", "JSONField",
}
_STRONG_TYPES = {
    "TextField", "BooleanField", "DateTimeField", "DateField", "TimeField",
    "DecimalField", "FloatField", "UUIDField",
}


def _family(name):
    if name in _INT_FAMILY:
        return "int"
    if name in _CHAR_FAMILY:
        return "char"
    if name in _STRONG_TYPES:
        return name
    return name


def _types_compatible(expected, actual, vendor=""):
    e, a = _family(expected), _family(actual)
    if e == a:
        return True
    # FileField / JSON columns on SQL Server are NVARCHAR(MAX), which the
    # driver reports as TextField - that is the intended storage, not a bug.
    if e == "char" and a in ("char", "TextField"):
        return True
    # SQLite stores booleans in integer columns (data type SMALLINT), so an
    # integer introspection result for a BooleanField is the correct storage.
    if e == "BooleanField" and a in _INT_FAMILY and vendor == "sqlite":
        return True
    return False


# Non-model infrastructure tables that must not be reported as "extra".
_INFRA_TABLES = {"django_migrations"}


class _Plan:
    """Everything that differs between the models and the live database."""

    def __init__(self):
        self.model_count = 0
        self.live_table_count = 0
        self.missing_tables = []     # [model]
        self.missing_columns = []    # [(model, field, needs_nullable_hack)]
        self.pk_missing = []         # [(model, table)]
        self.missing_uniques = []    # [(model, field_names, db_cols, label)]
        self.missing_fks = []        # [(table, column)]
        self.extra_tables = []       # [table]
        self.extra_columns = []      # [(table, column)]
        self.type_warnings = []      # [(table, column, expected, actual)]
        self.model_tables = []       # [models whose table exists in the DB]


class Command(BaseCommand):
    help = (
        "Sync an existing AMS-TEST-2 database with the Django models and "
        "mark all migrations as applied. Recovers from error 2714 "
        "('There is already an object named ...') after restoring an old "
        "database backup. Never deletes or overwrites existing rows."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_count = 0

    def err(self, label, detail=""):
        self.error_count += 1
        print(f"  [FAIL] {label}" + (f" - {detail}" if detail else ""))

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would be done; change nothing.",
        )
        parser.add_argument(
            "--no-record", action="store_true",
            help="Sync the schema only; do not mark migrations as applied.",
        )
        parser.add_argument(
            "--app", default=None, metavar="APP_LABEL",
            help="Limit the repair to one app label (default: all apps).",
        )

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _cols_for(model, field_names):
        """Map field names (as used in unique_together / UniqueConstraint)
        to real column names - FK fields store a '<name>_id' column, so the
        mapping is mandatory for both detection and index creation."""
        cols = []
        for fn in field_names:
            try:
                cols.append(model._meta.get_field(fn).column)
            except Exception:
                cols.append(fn)
        return tuple(cols)

    @staticmethod
    def _constraint_name(table, columns):
        base = f"{table}_{'_'.join(columns)}_uq"[:120]
        return base.replace(".", "_").replace("-", "_").lower()

    def _models_in_fk_order(self, only_app):
        """All managed models (incl. auto-created M2M through tables) in the
        order `migrate` would create them, so CREATE TABLE statements never
        reference a table that does not exist yet (SQL Server requirement)."""
        ordered, seen = [], set()

        def take(model):
            if model is None or model._meta.managed is False or model._meta.proxy:
                return
            if only_app and model._meta.app_label != only_app:
                return
            key = model._meta.db_table.lower()
            if key in seen:
                return
            seen.add(key)
            ordered.append(model)

        try:
            executor = MigrationExecutor(connection)
            targets = executor.loader.graph.leaf_nodes()
            for mig, _backwards in executor.migration_plan(targets):
                for op in mig.operations:
                    if isinstance(op, migrations.CreateModel):
                        try:
                            take(apps.get_model(mig.app_label, op.name))
                        except LookupError:
                            pass
                    elif isinstance(op, migrations.AddField):
                        through = getattr(getattr(op.field, "remote_field", None),
                                          "through", None)
                        if through is not None and through._meta.auto_created:
                            take(through)
        except Exception:  # loader problems must never block the repair
            pass
        for model in apps.get_models(include_auto_created=True):
            take(model)
        return ordered

    # ------------------------------------------------------------ phase 1
    def _build_plan(self, only_app):
        plan = _Plan()
        models_all = self._models_in_fk_order(only_app)
        plan.model_count = len(models_all)

        with connection.cursor() as cursor:
            live = {t.lower(): t
                    for t in connection.introspection.table_names(cursor)}
            live.pop("django_migrations", None)  # bookkeeping, not a model
            plan.live_table_count = len(live)

            for model in models_all:
                table = model._meta.db_table
                key = table.lower()
                if key not in live:
                    plan.missing_tables.append(model)
                    continue
                plan.model_tables.append(model)

                desc = connection.introspection.get_table_description(cursor, live[key])
                cols = {d.name.lower(): d for d in desc}
                constraints = connection.introspection.get_constraints(cursor, live[key])

                # ---- columns of this model
                pk_field = model._meta.pk
                for field in model._meta.concrete_fields:
                    col = field.column
                    if col.lower() not in cols:
                        if field is pk_field:
                            plan.pk_missing.append((model, live[key]))
                        else:
                            plan.missing_columns.append((model, field, False))
                        continue
                    actual = connection.introspection.get_field_type(
                        cols[col.lower()].type_code, cols[col.lower()])
                    actual = (actual or "").rsplit(".", 1)[-1]
                    if actual and not _types_compatible(
                            type(field).__name__, actual, connection.vendor):
                        plan.type_warnings.append(
                            (table, col, type(field).__name__, actual))

                # ---- unique constraints / unique_together
                db_unique = set()
                for c in constraints.values():
                    if (c.get("unique") or c.get("primary_key")) and c.get("columns"):
                        cols_l = [(x or "").lower() for x in c["columns"]]
                        # Constraints on expression indexes (SQLite string-
                        # literal quirk) carry None columns - never treat them
                        # as valid coverage; the cleanup below rebuilds them.
                        if all(cols_l):
                            db_unique.add(tuple(sorted(cols_l)))
                wanted = []  # (field_names, db_cols, label)
                for cols_t in model._meta.unique_together:
                    wanted.append((tuple(cols_t), self._cols_for(model, cols_t),
                                   f"{model.__name__} unique_together {tuple(cols_t)}"))
                for field in model._meta.concrete_fields:
                    if field.unique:
                        wanted.append(((field.column,), (field.column,),
                                       f"{model.__name__}.{field.name} (unique)"))
                for cons in model._meta.constraints:
                    if isinstance(cons, models.UniqueConstraint) and cons.condition is None:
                        wanted.append((tuple(cons.fields),
                                       self._cols_for(model, cons.fields), cons.name))
                for f_names, db_cols, label in wanted:
                    if tuple(sorted(x.lower() for x in db_cols)) not in db_unique:
                        plan.missing_uniques.append((model, f_names, db_cols, label))

                # ---- FK constraints (informational; SQL Server only)
                if connection.vendor == "mssql":
                    fk_cols = set()
                    for c in constraints.values():
                        if c.get("foreign_key") and c.get("columns"):
                            fk_cols.update(x.lower() for x in c["columns"])
                    for field in model._meta.concrete_fields:
                        if field.remote_field is not None and \
                                field.column.lower() not in fk_cols:
                            plan.missing_fks.append((table, field.column))

                # ---- columns in the DB that no model field uses
                model_cols = {f.column.lower() for f in model._meta.concrete_fields}
                for col_lower, _d in cols.items():
                    if col_lower not in model_cols:
                        plan.extra_columns.append((table, col_lower))

            # ---- tables in the DB that no model uses (old AMS-Test leftovers)
            model_tables = {m._meta.db_table.lower() for m in models_all}
            plan.extra_tables = sorted(live[t] for t in live if t not in model_tables)

            # ---- decide the NOT NULL -> nullable fallback per column
            for model, field, _flag in plan.missing_columns:
                table = model._meta.db_table
                needs = False
                if not field.null and not field.has_default():
                    qtable = connection.ops.quote_name(live[table.lower()])
                    cursor.execute(f"SELECT COUNT(*) FROM {qtable}")
                    needs = (cursor.fetchone()[0] or 0) > 0
                if needs:
                    i = plan.missing_columns.index((model, field, False))
                    plan.missing_columns[i] = (model, field, True)
        return plan

    def _print_plan(self, plan):
        print(f"\nPhase 1 of 5 - Comparing the database with the Django models")
        ok("Django models", f"{plan.model_count} tables expected")
        ok("Live database", f"{plan.live_table_count} tables found")
        if plan.missing_tables:
            info(f"Missing tables: {len(plan.missing_tables)}"
                 + (" - will be created" if plan.missing_tables else ""),
                 ", ".join(m._meta.db_table for m in plan.missing_tables[:6])
                 + (" ..." if len(plan.missing_tables) > 6 else ""))
        if plan.missing_columns:
            info(f"Missing columns: {len(plan.missing_columns)} - will be added")
            for model, field, hack in plan.missing_columns[:8]:
                extra = " (nullable - table has rows)" if hack else ""
                print(f"           - {model._meta.db_table}.{field.column}{extra}")
        if plan.pk_missing:
            for model, table in plan.pk_missing:
                self.err(f"Table {table} has no primary key column",
                         f"model {model.__name__} expects '{model._meta.pk.column}'")
            print("         Fix: this table is not usable as-is. Export its data,")
            print("              DROP TABLE it, then re-run dbrepair to recreate it.")
        if plan.missing_uniques:
            info(f"Missing unique constraints: {len(plan.missing_uniques)}"
                 " - will be added (best effort)")
            for _m, _f, db_cols, label in plan.missing_uniques[:6]:
                print(f"           - {label} -> columns {tuple(db_cols)}")
        if plan.missing_fks:
            info(f"Missing FK constraints: {len(plan.missing_fks)}"
                 " - informational only (the portal works without them)")
        if plan.extra_tables:
            info(f"Tables not used by this project (left untouched): "
                 f"{len(plan.extra_tables)}",
                 ", ".join(plan.extra_tables[:6])
                 + (" ..." if len(plan.extra_tables) > 6 else ""))
        if plan.extra_columns:
            info(f"Columns not used by this project (left untouched): "
                 f"{len(plan.extra_columns)}")
            for table, col in plan.extra_columns[:8]:
                print(f"           - {table}.{col}")
        if plan.type_warnings:
            info(f"Column type differences (left untouched): "
                 f"{len(plan.type_warnings)}")
            for table, col, exp, act in plan.type_warnings[:8]:
                print(f"           - {table}.{col}: model wants {exp}, "
                      f"database has {act}")

    # ------------------------------------------------------------ phases
    def _create_tables(self, plan):
        print("\nPhase 2 of 5 - Creating missing tables")
        if not plan.missing_tables:
            ok("Nothing to create - every table exists")
            return 0
        created = 0
        # Auto-created M2M through tables are created together with their
        # owner by schema_editor.create_model(owner). A through table is only
        # created standalone when its owner table ALREADY exists in the
        # database (otherwise the owner creation would fail with 2714).
        missing_keys = {m._meta.db_table.lower() for m in plan.missing_tables}
        deferred_error = None
        try:
            with connection.schema_editor(atomic=False) as editor:
                for model in plan.missing_tables:
                    owner = model._meta.auto_created
                    if owner is not None and owner is not False and \
                            owner._meta.db_table.lower() in missing_keys:
                        # Through table whose owner is also missing: the
                        # owner's create_model creates it - skip here.
                        continue
                    try:
                        editor.create_model(model)
                        n_m2m = len(model._meta.many_to_many)
                        ok(f"CREATE TABLE {model._meta.db_table}",
                           f"{len(model._meta.concrete_fields)} columns"
                           + (f" + {n_m2m} M2M links" if n_m2m else ""))
                        created += 1
                    except Exception as e:
                        self.err(f"Could not CREATE TABLE {model._meta.db_table}",
                                 str(e))
        except Exception as e:
            # SQLite defers some statements (unique indexes) to the schema
            # editor's exit - report them as warnings, not crashes.
            deferred_error = e
        if deferred_error is not None:
            warn("Some follow-up statements failed during this phase",
                 str(deferred_error))
        return created

    def _add_columns(self, plan):
        if not plan.missing_columns:
            print("\nPhase 3 of 5 - Adding missing columns")
            ok("Nothing to add - every model column exists")
            return 0
        added = 0
        # Group the adds per table: SQLite can rebuild a whole table when a
        # column cannot be added with a simple ALTER (NOT NULL / auto_now),
        # which brings in ALL model columns of that table at once - so the
        # column inventory is refreshed after every successful add.
        by_table = {}
        for model, field, hack in plan.missing_columns:
            by_table.setdefault(model._meta.db_table.lower(), []).append(
                (model, field, hack))
        deferred_error = None
        try:
            with connection.cursor() as cursor:
                live_cols = {
                    t: {d.name.lower()
                        for d in connection.introspection.get_table_description(cursor, t)}
                    for t in by_table
                }
                with connection.schema_editor(atomic=False) as editor:
                    print("\nPhase 3 of 5 - Adding missing columns")
                    for table_key, items in by_table.items():
                        for model, field, hack in items:
                            if field.column.lower() in live_cols[table_key]:
                                info(f"{model._meta.db_table}.{field.column} already exists",
                                     "created by an earlier table rebuild - skipped")
                                continue
                            f = copy.deepcopy(field)
                            notes = []
                            if hack:
                                f.null = True
                                f.blank = True
                                notes.append("nullable: the table has rows and the "
                                             "column is NOT NULL without a default - "
                                             "old rows stay NULL")
                            # SQLite: never use Django's add_field here - for NOT
                            # NULL / unique / defaulted fields it REBUILDS the whole
                            # table (_remake_table), which would silently drop
                            # old-schema columns the new models do not know about.
                            # A plain ALTER TABLE ADD COLUMN keeps every row.
                            use_editor = connection.vendor != "sqlite"
                            if not use_editor and getattr(f, "unique", False):
                                f.unique = False
                                notes.append("UNIQUE index follows in phase 4")
                            try:
                                if use_editor:
                                    editor.add_field(model, f)
                                else:
                                    self._sqlite_add_column(cursor, model, f, notes)
                                detail = f.db_type(connection) or ""
                                if notes:
                                    detail += " (" + "; ".join(notes) + ")"
                                ok(f"ALTER TABLE {model._meta.db_table} ADD {f.column}",
                                   detail)
                                added += 1
                                # Refresh the column inventory (a rebuild may have
                                # brought in several columns at once).
                                live_cols[table_key] = {
                                    d.name.lower()
                                    for d in connection.introspection.get_table_description(
                                        cursor, table_key)}
                            except Exception as e:
                                self.err(f"Could not ADD COLUMN "
                                         f"{model._meta.db_table}.{field.column}",
                                         str(e))
        except Exception as e:
            # SQLite defers some statements (unique indexes) to the schema
            # editor's exit - report them as warnings, not crashes.
            deferred_error = e
        if deferred_error is not None:
            warn("Some follow-up statements failed during this phase",
                 str(deferred_error))
        return added

    def _add_uniques(self, plan):
        print("\nPhase 4 of 5 - Unique constraints")
        added = 0
        sqlite_vendor = connection.vendor == "sqlite"
        try:
            with connection.cursor() as cursor:
                if sqlite_vendor:
                    # Always run: a leftover invalid index would otherwise
                    # silently cap the table to a single row.
                    self._drop_broken_uq_sqlite(cursor, plan)
                if not plan.missing_uniques:
                    ok("All unique constraints exist")
                    return 0
                print("     (best effort - duplicate old data is reported, "
                      "not forced)")
                for model, f_names, db_cols, label in plan.missing_uniques:
                    name = self._constraint_name(model._meta.db_table, db_cols)
                    try:
                        if sqlite_vendor:
                            # CREATE UNIQUE INDEX on REAL columns - unlike a
                            # UNIQUE constraint this never rebuilds the table,
                            # so old-schema columns and rows stay untouched.
                            qtable = connection.ops.quote_name(model._meta.db_table)
                            qcols = ", ".join(connection.ops.quote_name(c)
                                              for c in db_cols)
                            cursor.execute(
                                f"CREATE UNIQUE INDEX {connection.ops.quote_name(name)} "
                                f"ON {qtable} ({qcols})")
                        else:
                            cons = models.UniqueConstraint(fields=list(f_names),
                                                           name=name)
                            with connection.schema_editor(atomic=False) as editor:
                                editor.add_constraint(model, cons)
                        ok(f"UNIQUE on {model._meta.db_table} {tuple(db_cols)}", name)
                        added += 1
                    except Exception as e:
                        warn(f"Could not add UNIQUE on {model._meta.db_table} "
                             f"{tuple(db_cols)}"
                             " - duplicate data in old rows probably blocks it",
                             str(e))
                        print("         The portal works without it; create it "
                              "manually after cleaning the duplicates.")
        except Exception as e:
            warn("Unique constraint phase hit an unexpected error", str(e))
        return added

    def _drop_broken_uq_sqlite(self, cursor, plan):
        """SQLite quirk guard: a double-quoted identifier inside CREATE INDEX
        that is not a real column is silently treated as a STRING LITERAL
        (expression index). An earlier dbrepair run may have created such
        indexes from field names instead of column names - drop them so the
        correct ones can be built."""
        for model in plan.model_tables:
            qtable = connection.ops.quote_name(model._meta.db_table)
            try:
                indexes = [r[1] for r in cursor.execute(
                    f"PRAGMA index_list({qtable})").fetchall()]
            except Exception:
                continue
            for idx in indexes:
                if not str(idx).endswith("_uq"):
                    continue
                try:
                    cols = cursor.execute(
                        f"PRAGMA index_info({connection.ops.quote_name(idx)})"
                    ).fetchall()
                except Exception:
                    continue
                if any(r[1] == -2 or r[2] is None for r in cols):
                    try:
                        cursor.execute(
                            f"DROP INDEX {connection.ops.quote_name(idx)}")
                        warn(f"Dropped invalid index '{idx}' (was built on field"
                             " names, not real columns - it will be recreated"
                             " correctly)")
                    except Exception:
                        pass

    @staticmethod
    def _sql_literal(value):
        """Render a Python default value as a SQL literal (SQLite dialect)."""
        import datetime
        from decimal import Decimal
        if value is None:
            return None
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float, Decimal)):
            return str(value)
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            return "'" + str(value).replace("'", "''") + "'"
        return "'" + str(value).replace("'", "''") + "'"

    def _sqlite_add_column(self, cursor, model, field, notes):
        """Plain ALTER TABLE ADD COLUMN for SQLite with careful NOT NULL /
        DEFAULT handling. Unlike Django's add_field this never rebuilds the
        table, so pre-existing rows and old-schema columns are always kept."""
        qtable = connection.ops.quote_name(model._meta.db_table)
        qcol = connection.ops.quote_name(field.column)
        coltype = field.db_type(connection) or "TEXT"
        sql = f"ALTER TABLE {qtable} ADD COLUMN {qcol} {coltype}"
        is_hacked = any("nullable:" in n for n in notes)
        if not field.null and not is_hacked:
            sql += " NOT NULL"
        if field.has_default():
            lit = self._sql_literal(field.get_default())
            if lit is not None:
                sql += f" DEFAULT {lit}"
        cursor.execute(sql)

    def _record_migrations(self, only_app):
        print("\nPhase 5 of 5 - Marking migrations as applied")
        recorder = MigrationRecorder(connection)
        recorder.ensure_schema()
        loader = MigrationLoader(connection)
        applied_fn = recorder.applied_migrations
        applied = applied_fn() if callable(applied_fn) else applied_fn
        relevant = [(a, n) for (a, n) in sorted(loader.graph.nodes)
                    if not only_app or a == only_app]
        recorded = 0
        for app_label, name in relevant:
            if (app_label, name) in applied:
                continue
            recorder.record_applied(app_label, name)
            ok(f"Recorded {app_label} {name}")
            recorded += 1
        if recorded:
            ok(f"Recorded {recorded} of {len(relevant)} migrations as applied",
               "'migrate' will now report: No migrations to apply")
        else:
            ok(f"All {len(relevant)} migrations were already recorded",
               "'migrate' will report: No migrations to apply")

    # ------------------------------------------------------------ entry
    def handle(self, *args, **options):
        dry = options["dry_run"]
        record = not options["no_record"]
        only_app = options["app"]

        from amstest2 import dbconfig
        db = dbconfig.resolve_db()

        print("=" * 62)
        print("  AMS-Test-2 database repair (dbrepair)")
        print("=" * 62)
        if db["engine"] == "mssql":
            target = db["host"] + (f",{db['port']}" if db["port"] else "")
            info("Engine", f"MS SQL Server - {db['db_name']} @ {target}")
        else:
            info("Engine", f"SQLite - {db['db_name']}")
        if dry:
            info("DRY RUN", "nothing will be changed")
        info("Rule", "existing rows are never deleted or overwritten")

        plan = self._build_plan(only_app)
        self._print_plan(plan)

        if dry:
            print("\n" + "=" * 62)
            print("DRY RUN complete - nothing was changed.")
            print("Re-run without --dry-run to apply this plan.")
            print("=" * 62)
            return

        created = self._create_tables(plan)
        added_cols = self._add_columns(plan)
        self._add_uniques(plan)
        if record:
            self._record_migrations(only_app)
        else:
            print("\nPhase 5 of 5 - Marking migrations as applied")
            warn("Skipped (--no-record)",
                 "'migrate' may still report pending migrations")

        print("\n" + "=" * 62)
        print(f"  Summary: {created} table(s) created, {added_cols} column(s) added.")
        if plan.extra_columns or plan.extra_tables:
            print("  Leftovers from the old schema were kept and listed above -")
            print("  nothing was dropped.")
        print()

        if plan.pk_missing or plan.extra_columns or plan.extra_tables:
            print("  RESTORED OLD DATABASE? If this database holds your old")
            print("  AMS-Test rows, the business data may live in the old")
            print("  column layout (the 'not used by this project' items).")
            print("  Import it into the new schema with Import-From-AMS-Test.bat")
            print("  (or: python manage.py import_legacy --wipe).")
            print()

        if self.error_count:
            raise CommandError(
                f"Repair finished with {self.error_count} problem(s) - fix the "
                "[FAIL] items above and re-run dbrepair (it is safe to run "
                "repeatedly).")

        ok("REPAIR COMPLETE")
        print("  Next steps:")
        print("    python manage.py migrate        -> 'No migrations to apply'")
        print("    python manage.py seed_admins    -> ensures the two logins exist")
        print("    python manage.py dbdoctor       -> full connection check")
        print("    run-django.bat                  -> start the portal")
        print("=" * 62)
