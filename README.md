# Asset Management System (Web Portal) - AMS-Test-2

A complete **Django-only rebuild of AMS-Test** with a new design system, hybrid
htmx interactivity, and **MS SQL Server as the default data store** (SQLite
available as a fallback). A one-shot importer moves all data from the old
AMS-Test database into this project.

A web portal for recording company **assets**, **mobiles**, **SIM cards**,
**consumables**, **spare parts**, **equipment accessories** and the people who
hold them - with full lifecycle, printable forms, reports and role-gated access.

> **AMS-Test-2 is the live-testing project** backed by database `AMS-TEST-2`
> (MS SQL Server, default) or `db.sqlite3` (SQLite fallback). Masters and
> business records start empty. Login accounts are seeded.

## Seeded login accounts

| Username | Password | Role |
|---|---|---|
| `operator.sys` | `Sr#Ops@2026` | Supreme Root - system administration, Access Rights, Role Access |
| `testadmin` | `Admin@#$12345` | Super Root - the everyday admin account |

Change these passwords on first real use (My Profile > Change Password).

## Quick start (Windows)

1. Install Python 3.11+ (python.org, tick "Add to PATH") and
   [Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server).
2. Double-click **`Setup-AMS-Test-2.bat`** - it asks where the data should
   live (**MS SQL Server = default**, or SQLite for a quick demo), creates a
   `venv`, installs everything, creates/migrates the database and seeds the
   two logins.
3. Double-click **`run-django.bat`** - starts the portal at
   **http://127.0.0.1:8000/**. The banner shows the active data store.

Manual (any OS):

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on Linux)
pip install -r requirements.txt
python manage.py migrate         # SQL Server must be reachable (see below)
python manage.py seed_admins
python manage.py runserver
```

To force SQLite in the manual path: `set AMS_DB=sqlite` (Windows) or
`export AMS_DB=sqlite` (Linux/macOS) before `migrate` / `runserver`.

## SQL Server - the default data store

All business data lives in the **`AMS-TEST-2` database on MS SQL Server**
(same engine as the original AMS-Test). Connection settings are resolved in
this order:

1. Environment variables (`AMS_DB_NAME`, `AMS_DB_HOST`, `AMS_DB_PORT`,
   `AMS_DB_USER`, `AMS_DB_PASSWORD`, `AMS_DB_DRIVER`)
2. `db-config.bat` in the project folder (written by the setup scripts and
   loaded automatically by `run-django.bat`; `settings.py` also parses it so
   starting Django directly works too)
3. Defaults: `AMS-TEST-2` @ `localhost,1433`, user `sa`

Two ways to bring SQL Server up - pick whichever fits your environment.

### A. One-click helper (recommended)

Run `Setup-SQL-Server.bat` once (or `Setup-AMS-Test-2.bat` and answer `Y`).
It will:

1. Prompt for SQL Server host, port, login user (default `sa`) and password.
2. Create the empty `AMS-TEST-2` database by running
   `sqlserver\01-create-database.sql` via `sqlcmd`.
3. Create the virtualenv, install `mssql-django` + `pyodbc`.
4. **Write `db-config.bat`** with `AMS_DB=mssql` + the connection details so
   the choice persists for every future `run-django.bat`.
5. Run `python manage.py migrate` so Django creates every table.
6. Run `python manage.py seed_admins` to create the two login accounts.

### B. Manual setup

```bat
REM 1. Create the empty database (run ONCE on the SQL Server machine)
sqlcmd -S localhost -U sa -P <password> -i sqlserver\01-create-database.sql

REM 2. Configure env vars
set AMS_DB=mssql
set AMS_DB_HOST=localhost
set AMS_DB_PORT=1433
set AMS_DB_USER=sa
set AMS_DB_PASSWORD=<your-sa-password>

REM 3. Install deps + create tables + seed
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_admins
python manage.py runserver
```

### C. DBA pre-creates all tables (no `migrate` at runtime)

If a DBA needs to pre-create the schema before the app connects, run
`sqlserver\02-create-all-tables.sql` in SSMS. It creates the
`AMS-TEST-2` database plus every table Django would create, with all
foreign keys, indexes, DEFAULT and UNIQUE constraints, and pre-records
the migrations in `django_migrations` so `python manage.py migrate` is
a no-op afterwards. The script is idempotent (every CREATE TABLE is
wrapped in `IF OBJECT_ID ... IS NULL`).

```bat
REM 1. Pre-create database + tables (DBA runs this in SSMS or via sqlcmd)
sqlcmd -S localhost -U sa -P <password> -i sqlserver\02-create-all-tables.sql

REM 2. Then in your app directory:
set AMS_DB=mssql
set AMS_DB_PASSWORD=<your-sa-password>
pip install -r requirements.txt
python manage.py migrate              REM no-op; tables already exist
python manage.py seed_admins
python manage.py runserver
```

### Connection settings

| Variable                   | Default (SQL Server)                 | Purpose                              |
| -------------------------- | ------------------------------------ | ------------------------------------ |
| `AMS_DB`                   | `mssql` (default)                    | set `sqlite` to fall back to SQLite |
| `AMS_DB_NAME`              | `AMS-TEST-2`                         | Database name                        |
| `AMS_DB_HOST`              | `localhost`                          | SQL Server host - may include a named instance, e.g. `localhost\SQLEXPRESS` |
| `AMS_DB_PORT`              | `1433`                               | SQL Server port - leave **empty** for a named instance (the SQL Server Browser service resolves the port) |
| `AMS_DB_USER`              | `sa`                                 | Login user - ignored with Windows Authentication |
| `AMS_DB_PASSWORD`          | (empty)                              | Login password - ignored with Windows Authentication |
| `AMS_DB_DRIVER`            | (auto)                               | ODBC driver name. Leave unset = mssql-django uses Driver 18 and **automatically falls back to Driver 17** when 18 is missing |
| `AMS_DB_TRUSTED_CONNECTION`| (unset)                              | set `yes` for **Windows Authentication** (no user/password needed) |
| `AMS_DB_EXTRA_PARAMS`      | (unset)                              | Extra ODBC keywords appended verbatim, e.g. `Encrypt=optional` for very old servers |

"ODBC Driver 18 for SQL Server" must be installed on the machine that
runs the portal (Driver 17 works too - see troubleshooting).
`TrustServerCertificate=yes` is set for local dev.

### Files for SQL Server + import

```
sqlserver/
├── 01-create-database.sql      <- creates the empty AMS-TEST-2 database
└── 02-create-all-tables.sql    <- creates database + every table (DBA path)
Setup-SQL-Server.bat             <- one-click Windows helper (path A above)
Test-SQL-Connection.bat          <- one-click connection diagnostics (dbdoctor)
Repair-Database.bat              <- one-click schema repair (dbrepair) - fixes
                                    migrate error 2714 after restoring a backup
Copy-Data-SQLite-to-SQLServer.bat <- moves records entered in SQLite into SQL Server
Import-From-AMS-Test.bat         <- one-click import of ALL old AMS-Test data
db-config.bat                    <- written by the setup scripts; stores the
                                    database choice + SQL Server connection
```

## Troubleshooting connection errors (start here)

Double-click **`Test-SQL-Connection.bat`** (or run
`python manage.py dbdoctor`). It checks every layer in order and prints a
concrete fix for the first layer that fails:

```
Step 1  Resolved configuration - what settings.py actually uses
Step 2  ODBC driver            - pyodbc + installed MS drivers
Step 3  Network                - TCP port reachability / SQL Browser probe
Step 4  SQL login              - raw ODBC connect (exact Django string)
Step 5  Database + Django      - AMS-TEST-2 exists, tables count, Django OK
```

Setup-SQL-Server.bat runs the same doctor (with `--create-database`) before
migrating, so a broken connection is caught with a clear message instead of
a cryptic migrate error. Both setup scripts also auto-run
**`Repair-Database.bat`'s `dbrepair` command** when `migrate` reports that
tables already exist, and there is a dedicated **`Repair-Database.bat`**
for the "I restored a backup" case.

Common errors and their fixes:

| Error you see | Cause | Fix |
| --- | --- | --- |
| `Data source name not found ...` / `Can't open lib` | ODBC driver missing | Install [ODBC Driver 18](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server); if only Driver 17 is present, set `AMS_DB_DRIVER=ODBC Driver 17 for SQL Server` |
| `TCP Provider: error code 0x274D` / `No connection could be made` / timeout on Step 3 | Server unreachable | Start the SQL Server service; enable **TCP/IP** in SQL Server Configuration Manager (Express ships with it DISABLED); open port 1433 in the firewall; check host/port |
| Error `18456` `Login failed for user 'sa'` | SQL auth off / sa disabled / wrong password | SSMS > server Properties > Security > enable **SQL Server and Windows Authentication mode**; enable the sa login; or simply use Windows Authentication (leave the login blank in setup) |
| Error `4060` `Cannot open database "AMS-TEST-2"` | Database missing | `migrate` now **creates the missing database automatically** (via the master login) and continues; the manual ways still work: `python manage.py dbdoctor --create-database` or run `sqlserver\01-create-database.sql` via sqlcmd/SSMS |
| `Login failed for user 'NT AUTHORITY\\...'` (Windows auth) | Your Windows account has no SQL login | SSMS > Security > Logins > New Login (Windows account) with dbcreator rights, or connect as `sa` |
| SSL / certificate errors | TLS handshake | `TrustServerCertificate=yes` is already set; for very old servers/OS add `set AMS_DB_EXTRA_PARAMS=Encrypt=optional` |
| Named instance not found / `SQL Server Browser` error | Browser service off | Start **SQL Server Browser** (Configuration Manager > set Automatic), or give the instance a static TCP port and set `AMS_DB_PORT` |
| Error `2714` / `42S01` `There is already an object named 'ams_company' in the database` during `migrate` | The database already contains tables but the migration bookkeeping does not match (typical after restoring the old AMS-Test backup over AMS-TEST-2) | **Just run `python manage.py migrate` again** - it detects the situation, runs the dbrepair sync automatically and then finishes cleanly. Manual equivalent: double-click **`Repair-Database.bat`** (or `python manage.py dbrepair`) - see the next section |

### migrate fails: "There is already an object named ..." (error 2714)

This is the expected result of **restoring a database backup** (e.g. the old
AMS-TEST `.bak`) over `AMS-TEST-2`, or of pre-creating the tables and losing
the `django_migrations` records. The connection is fine - Django just tries
to re-create tables that already exist.

**Since this build, `python manage.py migrate` self-heals.** The project
ships its own `migrate` command (`ams/management/commands/migrate.py`) that
wraps Django's standard one: when it detects that a pending migration would
create a table that ALREADY exists, it runs the `dbrepair` sync first and
only then migrates - the error 2714 can no longer happen, no matter whether
you run it in VS Code's terminal, a .bat helper or a script. You will see a
banner ("migrate pre-flight: the database already contains tables ...") and
the five repair phases, then `No migrations to apply`. Set
`AMS_NO_AUTOHEAL=1` to get the stock Django behaviour back.

Still prefer the manual way, or want a preview first? **`dbrepair` does the
whole job**:

```
Repair-Database.bat                  (double-click)
   or:  python manage.py dbrepair --dry-run     (preview first)
       python manage.py dbrepair               (apply)
```

It walks five phases:

1. Compares every Django model table/column with the live database.
2. Creates missing tables with the exact DDL `migrate` would use.
3. Adds missing columns to existing tables - a NOT NULL column without a
   default is added as **nullable** when the table already holds rows, so
   no data can be lost or blocked.
4. Adds missing unique constraints (best effort; duplicate old data is
   reported, not forced).
5. Marks every migration as applied, so a following `migrate` reports
   `No migrations to apply`.

Existing rows are never deleted or overwritten; leftover columns/tables of
the old schema are listed and kept. Afterwards run `python manage.py
seed_admins` (the two portal logins), then start the portal.

If the restored rows live in the old column layout, the repair output lists
them under "columns not used by this project" - import the business data
into the new schema with **`Import-From-AMS-Test.bat`**.

### You restored the old AMS-TEST backup over AMS-TEST-2 (step by step)

The situation: SSMS restore of the old AMS-TEST `.bak` over the
`AMS-TEST-2` database, then `python manage.py migrate` printed error 2714.
The fix is now automatic, but the restored rows live in the OLD column
layout, so one extra command brings your data into the new schema:

```
REM inside the AMS-Test-2 folder (VS Code terminal or cmd)
python manage.py migrate          REM auto-syncs the existing tables, then:
                                  REM "No migrations to apply"
python manage.py import_legacy --legacy-host localhost --legacy-user sa \
        --legacy-password <sa-password> --legacy-name AMS-TEST-2
python manage.py seed_admins
run-django.bat
```

`import_legacy` reads the old layout (typed columns + `data_json`), keeps
old login passwords working (`AmsLegacyHasher`) and decodes the logo/banner
back to picture files under `media\company\`. Cleaner alternative: restore
the old backup under its own name `AMS-TEST`, create a fresh `AMS-TEST-2`
(let `migrate` build it), and point `import_legacy --legacy-name AMS-TEST`
at the old database - that path never touches your backup.

### Using VS Code

Everything works from the integrated terminal (no double-clicking needed):

```
cd AMS-Test-2
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate          REM self-healing; creates tables (and the
                                  REM missing database) automatically
python manage.py seed_admins
python manage.py runserver        REM http://127.0.0.1:8000/
```

The project ships `.vscode\tasks.json` and `.vscode\launch.json`:

* **Tasks** (Terminal > Run Task): `Run portal (runserver)`, `Migrate
  database`, `Repair database (dbrepair)`, `Seed admin accounts`, `Test SQL
  connection (dbdoctor)`, `Import from old AMS-Test`.
* **Run and Debug**: the `AMS-Test-2: runserver` configuration starts the
  portal with the debugger attached (F5) - breakpoints in `ams/views/*`
  work out of the box.

Settings resolution does not depend on `db-config.bat` being loaded into
the shell: `amstest2/dbconfig.py` reads that file itself, so plain
`python manage.py ...` in VS Code always targets the same SQL Server as
the double-click scripts.

### Named instances (SQL Server Express) and Windows Authentication

Most default installs of SQL Server Express are `localhost\SQLEXPRESS` with
TCP/IP off and Windows-only authentication. The setup scripts handle both:

```bat
REM Named instance - leave the PORT question blank:
set AMS_DB_HOST=localhost\SQLEXPRESS
set AMS_DB_PORT=

REM Windows Authentication - leave the LOGIN USER question blank:
set AMS_DB_TRUSTED_CONNECTION=yes
REM (Setup-SQL-Server.bat writes this for you when you leave the login blank)
```

For named instances the SQL Server Browser service must be running, or you
can give the instance a static port (Configuration Manager > Protocols >
TCP/IP > IP Addresses > TCP Port) and set `AMS_DB_PORT` instead.

## Importing your data from the old AMS-Test

The original AMS-Test stored every record in the SQL Server database
**`AMS-TEST`** (typed columns + a full JSON copy per row, written by its
C# API). `Import-From-AMS-Test.bat` copies all of it into `AMS-TEST-2`:

- **Masters**: sites, departments, designations, asset categories/types/makes,
  accessories, vendors (+ supplies), SIM operators/plans, consumable
  categories, units of measure, spare part categories, print terms.
- **People**: employees with department / site / **manager chains**, exit
  dates and reasons, and the immutable **Exit Records** (handover snapshots
  incl. facility checklists).
- **Assets & mobiles**: AMS IDs, Display IDs, legacy-ID flags, categories,
  makes, vendors, costs, dates, IMEI/battery/charger, **accessories issued**
  (matched by name), **replacement chains** (Replaces Old Asset), linked SIMs
  (via the old `simMobileNo`), and the complete per-item **lifecycle history**.
- **SIM cards**: operator/plan links, ICCID, activation dates, holder links,
  Used-In-Mobile links (bidirectional with the mobile side).
- **Lifecycle events**: the per-item `history[]` arrays AND the global
  assignment events are merged and **de-duplicated** (same item + date +
  action + employee is imported once).
- **Stock**: consumables + spare parts with quantities, reorder levels, costs,
  and their full **movement logs** (Restocked/Used, incl. the asset a spare
  part was fitted on).
- **Users**: every account, role, profile fields (contact, DOB, site, linked
  employee, per-user allowed pages) - and **the old passwords keep working**
  (the stored PBKDF2-SHA256 hashes are verified by `ams/hashers.py` and
  transparently upgraded to Django's default on first login).
- **Company Master**: name, slogan, address, HR/head contacts, report
  appearance prefs - and the **logo + banner are restored as real image
  files** (decoded from the old base64 data URLs into `media\company\`).
- **Role Access matrix** and per-user **Access Rights** overrides.
- **Activity log** entries.

### How to run it

1. Set up the new project first (`Setup-AMS-Test-2.bat` -> SQL Server).
2. Double-click **`Import-From-AMS-Test.bat`**. It asks for the OLD
   database connection (host / port / name `AMS-TEST` / login), offers a
   **dry run** first (parse + report, writes nothing), then imports with or
   without wiping what is already in `AMS-TEST-2`.

Command line equivalent:

```bat
python manage.py import_legacy --legacy-host localhost --legacy-port 1433 ^
    --legacy-name AMS-TEST --legacy-user sa --legacy-password *** --dry-run
python manage.py import_legacy --legacy-host localhost --legacy-port 1433 ^
    --legacy-name AMS-TEST --legacy-user sa --legacy-password *** --wipe
```

Options: `--dry-run` (report only), `--wipe` (clear AMS-TEST-2 business
rows first - recommended for the first import), `--skip-users` (keep only
the two seeded logins), `--source-sqlite <file>` (import from a SQLite
mirror of the old database instead of a live SQL Server connection).

### Import behaviour and mapping notes

- Re-running the import is safe: masters / employees / assets / SIMs are
  **upserted**, lifecycle events are de-duplicated against existing rows, and
  append-only logs (movement logs, activity log) are skipped when they
  already contain data. Use `--wipe` to start clean.
- Old assets that were **held by a department** (assignedDepartment - the new
  portal assigns to people) are imported with their department shown in the
  free-text "Actual user" field, e.g. `Dept: IT Store`, so the information is
  visible and searchable.
- Employee **`empId` is imported as the company employee code** (`emp_id`);
  the duplicate `empIdCompany` copy is ignored.
- Old vendor `category` strings become rows of the Vendor Category master
  linked as "Supplies"; arrays in the vendor JSON are honoured too.
- Print form counters (AIF/AHF/MIF/SIF numbers) were session-only in the old
  portal and are not stored in its database - they start fresh here.
- The old SQL Backup document was not carried over (module not rebuilt).

## Where is my data stored? (FAQ)

**How do I know which database the portal is using right now?**

1. When `run-django.bat` starts it prints a banner:
   `Data storage : SQL Server - AMS-TEST-2 @ host,1433` or
   `Data storage : SQLite file db.sqlite3 in this folder`.
2. The Company Master page (System Admin > Company Master) shows the same
   under **Data storage** at the top of the form.

**I entered records but I cannot see them in MS SQL Server. Why?**

Earlier builds defaulted to SQLite and only switched with `AMS_DB=mssql`.
**SQL Server is now the default** (`AMS_DB=mssql` unless `AMS_DB=sqlite` is
set), and the choice is persisted in `db-config.bat` which the setup scripts
write and `run-django.bat` loads on every start.

If MS SQL Server still looks empty:

1. Check the startup banner - it must say `SQL Server - AMS-TEST-2`.
2. Verify you are inspecting the right server/instance and database
   (`AMS-TEST-2`) in SSMS - tables are named `ams_*` plus `django_*`.
3. If you previously entered records in SQLite mode, either run
   `Copy-Data-SQLite-to-SQLServer.bat` (moves SQLite records over) or import
   the old AMS-Test data with `Import-From-AMS-Test.bat`.

To work without a SQL Server deliberately: run `Setup-AMS-Test-2.bat` and
answer `n` (SQLite), or set `AMS_DB=sqlite` in `db-config.bat`.

**Where are records actually kept?**

| What                                  | Where it lives                                                        |
| ------------------------------------- | -------------------------------------------------------------------- |
| Employees, assets, mobiles, SIMs ...  | SQL Server `AMS-TEST-2` tables (`ams_*`) by default, or `db.sqlite3`  |
| User accounts, roles, Role x Page     | Same database (`auth_user`, `ams_userprofile`, `ams_roleaccess`)      |
| Company logo / banner images          | **On disk** in `AMS-Test-2\media\company\` (never inside the DB)      |
| Sessions                              | Same database (`django_session`)                                      |
| Audit log                             | Same database (`ams_activitylog`)                                     |

Note the logo/banner are filesystem files: if you move the portal to another
server, copy the `media\` folder along with the database.

## Architecture

- **Framework**: Django 5 (templates + views, no REST layer, no Node).
- **Interactivity**: hybrid htmx - System Admin hub tabs, Report Master tabs,
  movement-log and detail modals fetch server-rendered partials; everything
  else is classic form POST + redirect (robust without JavaScript).
- **Database**: ORM models, **MS SQL Server default** (`mssql-django`),
  SQLite fallback. Legacy-imported passwords verify via a compatibility
  hasher (`ams/hashers.py`) and upgrade transparently on first login.
- **Sessions**: Django sessions (8-hour lifetime, mirroring the original JWT
  expiry). CSRF protected.
- **Static assets**: vendored locally - htmx 1.9.12, Inter font, print
  stylesheet. No CDN required; works fully offline.

## Folder structure

```
AMS-Test-2/
├── manage.py                  <- Django entry point
├── requirements.txt           <- Django + openpyxl + mssql-django + pyodbc
├── Setup-AMS-Test-2.bat       <- one-time setup (asks: SQL Server or SQLite)
├── Setup-SQL-Server.bat       <- one-time setup (Windows, SQL Server)
├── Test-SQL-Connection.bat    <- database connection diagnostics (dbdoctor)
├── Repair-Database.bat        <- database schema repair (dbrepair)
├── Import-From-AMS-Test.bat   <- one-click import of the old AMS-Test data
├── Copy-Data-SQLite-to-SQLServer.bat <- move SQLite records into SQL Server
├── run-django.bat             <- start the portal (Windows)
├── .vscode/                   <- VS Code tasks + F5 debug configurations
│   ├── tasks.json
│   └── launch.json
├── sqlserver/
│   ├── 01-create-database.sql  <- creates empty AMS-TEST-2 database
│   └── 02-create-all-tables.sql <- creates database + every table (DBA path)
├── amstest2/                  <- project settings (switchable DB)
│   └── settings.py
├── ams/                       <- the application
│   ├── access.py              <- roles, page registry, Role x Page matrix, gates
│   ├── models.py              <- full data model
│   ├── hashers.py             <- verifies old AMS-Test password hashes
│   ├── ids.py                 <- AMS ID / Display ID algorithms (max+1)
│   ├── activity.py            <- audit-trail writer
│   ├── tools.py               <- CSV import/export + openpyxl XLSX export
│   ├── master_registry.py     <- generic lookup-master configs
│   ├── context.py             <- shell context (nav, role, portal name)
│   ├── views/                 <- one module per domain
│   │   ├── auth.py, dashboard.py, masters.py, employees.py,
│   │   ├── assets.py (assets + mobiles), simcards.py, stock.py,
│   │   ├── catalog.py (vendors + accessories), adminpages.py,
│   │   ├── logs.py, reports.py, prints.py, labelprint.py,
│   │   └── distribution.py, account.py
│   ├── templatetags/ams_extras.py
│   └── management/commands/
│       ├── migrate.py         <- self-healing migrate (auto dbrepair sync,
│       │                         auto-creates a missing database)
│       ├── seed_admins.py     <- seeds the two logins + role matrix
│       ├── import_legacy.py   <- imports the old AMS-Test database
│       ├── dbrepair.py        <- schema sync for a restored backup
│       └── dbdoctor.py        <- connection diagnostics with concrete fixes
├── templates/
│   ├── base_shell.html        <- sidebar + topbar shell
│   ├── login.html, dashboard.html, ...
│   ├── partials/              <- htmx fragments + hub panels
│   └── print/                 <- AIF / AHF / MIF / SIF / Gate Pass /
│                                 A4 sticker sheet / report print
├── static/
│   ├── css/ams.css            <- "Graphite Teal" design system + 9 themes
│   ├── css/print.css          <- .pf-* print engine
│   ├── js/htmx.min.js, app.js
│   └── fonts/                 <- Inter woff2 (local)
├── media/                     <- company logo / banner uploads
└── db.sqlite3                 <- created by migrate (SQLite mode)
```

## What is inside (full AMS-Test parity)

- **Employee Master** - AMS IDs (`EMP-<dept>-NNNNNN`), quick-add of
  departments/sites, CSV template/export/import with a per-row Import Report,
  manager auto-linking, Exit with immutable snapshot + facility checklist +
  team re-pointing, Reactivate, Assign Report and Exit Report (Handover Form)
  printing, per-employee holdings view.
- **Asset Master** - Smart IDs: permanent `AMS-<type>-<ddmmyy-hhmmss>-NNNNNN`,
  Display ID `LT00001` (auto or typed-as-legacy), full ID `LT00001HOIT`
  (base + site short + dept short, assigned non-legacy only). Lifecycle:
  Assign / Edit Assign / Reassign (with "Other / Not in User Master..." free
  text), Return, Transfer, Not Working, Retire / Scrap, Replace (with reason +
  permanent links), accessories checklist, per-item history + global
  lifecycle events, CSV template/export/import.
- **Mobile Master** - same engine + IMEI/battery/charger, SIM link
  (`mobileNumber` mirror), SIM picker, Swap (exchange holders, SIM moves with
  holder or stays), Mobile Issue Form (MIF) print.
- **SIM Card Master** - `SIM-NNNNNN`, ICCID, operator/plan (auto-register via
  quick-add), In Store / Issued / Blocked / Retired, Used-In-Mobile picker
  (Personal Mobile supported), linking issues an In-Store phone
  ("Linked from SIM Card Master"), Return / Block / Retire, SIM Card Issue
  Form (SIF) print, CSV.
- **Consumable + Spare Parts Masters** - `CNS-NNNNNN` / `SP-NNNNNN`, Restock /
  Used-Assign with movement log, low-stock badge (`qty <= reorderLevel`),
  per-item movement report, spare parts link to the asset they were fitted on
  (permanent AMS ID + display-ID snapshot at time of use), CSV.
- **Accessory Master** - `ACC-NNNNNN`, quick-add asset types, delete guarded
  while any asset of that type has the accessory issued. **Bulk import / export /
  template** (.xlsx template with sample row + .xlsx/.csv export + .xlsx or .csv
  import with a per-row Import Report); missing Asset Types and Sites are
  auto-created on import; re-importing the same file updates existing rows in
  place (matched by `name` + `asset_type`), so the import is idempotent.
- **Vendor Master** - Supplies multi-select from Vendor Category Master,
  GSTIN, "Used By" delete guard across assets + consumables + spare parts.
  **Bulk import / export / template** (.xlsx template with sample row + .xlsx/
  .csv export + .xlsx or .csv import with a per-row Import Report); missing
  Vendor Categories are auto-created; `categories` column is pipe-separated
  (e.g. `Hardware|Software`); match key is `name` (case-insensitive) so re-imports
  update existing rows in place.
- **Lookup masters** (generic engine): Asset Type (shortform), Asset Category
  (Used On), Asset Make, Site, Department, Designation, SIM Operator, SIM Plan,
  Consumable Category, Unit of Measure, Spare Part Category, Vendor Category,
  Print Terms (2-50 active rules per form). Usage counts + delete guards.
- **System Administrator hub** - htmx tabs for Company, all lookup masters,
  Vendors, Accessories, Access Rights, Role Access, Log Report, Label/Pass
  Print (tab hidden when the role has no access).
- **Company Master** - single record feeding letterheads (logo + rectangular
  banner upload, slogan, HR contact, head of company). Address prints on the
  **Laptop Gate Pass only**.
- **User Master** - accounts with role (rank-guarded: cannot create/edit above
  own role), **required password + Site**, active toggle, Supreme Root never
  deletable, Super Root deletable only by Supreme Root, role hint bar.
- **Access Rights Control Master** (Supreme Root only) - per-user page access
  checklist with None/View/Full, role-locked checkboxes, Select All / Clear All.
- **Role Access Master** (Supreme Root only) - Role x Page matrix
  (None / View / Full), Reset to Suggested Defaults, editable matrix.
- **Log Report** - append-only audit trail (actor, role, page, type, message),
  visibility split (Supreme sees all; Super Root sees everything except
  Supreme-actor entries), filters + CSV/Excel export, Clear (Supreme only).
- **Report Master** - 8 tabs: Asset Lifecycle, Asset Issue Form records,
  Asset Handover Form records, Consumable Restock/Used, Spare Parts
  Restock/Used, Asset Distribution. Filters, Print, CSV + Excel export per tab.
- **Report Appearance** - classic (logo + name) vs banner letterhead, show /
  hide logo / name / slogan; preview; used by every printed document.
- **Label/Pass Print Master** - tile picker grouped by type (Laptop, Desktop,
  Printer, Scanner first, then A-Z, Mobiles last), per-section Copies, Select
  all, search, Excel download, **A4 sticker sheet** (7 columns x 16 rows,
  26mm x 17.6875mm labels, margins 7/4/7/6 mm) and **Laptop Gate Pass**
  (A4 landscape sheet with **8 slips per page** in a 2-column x 4-row grid,
  with 6mm cut spacing between slips so the printed sheet can be cut into
  individual passes. Each slip matches the original AMS-Test simple layout:
  centered "Laptop Gate Pass" title, three body lines - "The Laptop Serial
  No. ..., Asset Code No. ... is issued to", bold **employee name** (Employee
  ID ...), and the company address as the issuing premises, with
  **Stamp & Signature** right-aligned at the bottom. Partial pages are
  padded with blank slots so every printed sheet keeps the full 2x4 grid).
- **Asset Distribution** - Direct (personal) vs Team (subordinate) holdings
  incl. free-text actual users, summary tiles, per-employee detail modal with
  complete lifecycle, CSV/Excel export.
- **Print engine** - server-rendered A4 documents with the `.pf-*` component
  styles: Asset Issue Form (scope direct / team / both, condition checkboxes,
  accessories, remarks with full Display IDs, declaration terms from Print
  Terms Master, signature order Authorised > Issued > Employee), Asset
  Handover Form (exit snapshot, ruled Exit Reason box, clearance checklist,
  signatures Employee > Received By > Authorised By), Mobile/SIM Issue Forms,
  report printing, Gate Pass, sticker labels. All forms get persistent form
  numbers (AIF/AHF/MIF/SIF-NNNNNN).
- **Dashboard** - KPI tiles (total / operational / under maintenance / total
  value), Assets-by-Type bars, status donut, low-stock alerts, recent stock
  movements, recent activity.
- **Settings** - 9 themes (per-user), font size sm/md/lg, portal name +
  default page size + currency note, toast toggle + clear activity log,
  read-only current role card.
- **My Profile** - display name, email, contact, gender, DOB, address,
  change password (min 6 chars, current password verified).

## Roles

`Standard User` (0) < `Viewer (Read-Only)` (1) < `Admin` (2) < `Super Root` (3)
< `Supreme Root` (4)

- Hard gates (override the matrix): Access Rights + Role Access = Supreme Root
  only; Log Report = Super Root + Supreme Root.
- Viewer (Read-Only) = can open pages but every write is blocked
  ("View only - you cannot change records on this page.").
- Site is stored per account (required by User Master) and Super Root /
  Supreme Root always see all records.

## Code comments convention

Every file has clear comment blocks like:

```
#-------------- Start Code for : SECTION NAME ----------------
... code ...
#-------------- End of the code : SECTION NAME ----------------
```

so you can find and edit any section easily.

## Notes and differences vs the original AMS-Test

- Rebuilt **Django-only** (the ASP.NET Core API is not part of this project).
- The SQL Backup module (`sql-backup`) was intentionally not carried over -
  it was hidden/disabled in AMS-Test ("kept in code, hidden for now"); SQLite
  backups = copy `db.sqlite3`.
- The "Viewing As" role simulator had already been removed upstream (15.6);
  only the read-only "Signed-in Role" bar remains, as in the original.
- Business masters start **empty** (blank cut, like AMS-v4-0). Only the two
  login accounts, the Role Access matrix and portal defaults are seeded.
- Auto IDs are always **max+1** (never count+1), as in the original.
