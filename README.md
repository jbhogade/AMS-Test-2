# Asset Management System (Web Portal) - AMS-Test-2

A complete **Django-only rebuild of AMS-Test** with a new design system, hybrid
htmx interactivity, and a switchable database (SQLite default / SQL Server ready).

A web portal for recording company **assets**, **mobiles**, **SIM cards**,
**consumables**, **spare parts**, **equipment accessories** and the people who
hold them - with full lifecycle, printable forms, reports and role-gated access.

> **AMS-Test-2 is the live-testing project** backed by database `AMS-TEST-2`
> (SQL Server mode) or `db.sqlite3` (default). Masters and business records
> start empty. Login accounts are seeded.

## Seeded login accounts

| Username | Password | Role |
|---|---|---|
| `operator.sys` | `Sr#Ops@2026` | Supreme Root - system administration, Access Rights, Role Access |
| `testadmin` | `Admin@#$12345` | Super Root - the everyday admin account |

Change these passwords on first real use (My Profile > Change Password).

## Quick start (Windows)

1. Install Python 3.11+ (python.org, tick "Add to PATH").
2. Double-click **`Setup-AMS-Test-2.bat`** - it creates a `venv`, installs
   Django + openpyxl, migrates the database and seeds the two logins.
3. Double-click **`run-django.bat`** - starts the portal at
   **http://127.0.0.1:8000/**.

Manual (any OS):

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on Linux)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_admins
python manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in.

## Switching to SQL Server (same engine as the original AMS-Test)

Two ways to bring up SQL Server - pick whichever fits your environment.

### A. One-click helper (recommended)

Run `Setup-SQL-Server.bat` once. It will:

1. Prompt for SQL Server host, port, login user (default `sa`) and password.
2. Create the empty `AMS-TEST-2` database by running
   `sqlserver\01-create-database.sql` via `sqlcmd`.
3. Create the virtualenv, install `mssql-django` + `pyodbc`.
4. Set `AMS_DB=mssql` and the connection env vars for the rest of the session.
5. Run `python manage.py migrate` so Django creates every table.
6. Run `python manage.py seed_admins` to create the two login accounts.

After it finishes, just run `run-django.bat` to start the portal.

> Note: `run-django.bat` reads the `AMS_DB` env var. If you close the
> command window the vars are lost - re-run `Setup-SQL-Server.bat` (it
> is idempotent and skips steps that are already done) or set them once
> at the system level via "Edit the system environment variables".

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

### Connection defaults (override with env vars)

| Variable             | Default                              | Purpose                              |
| -------------------- | ------------------------------------ | ----------------------------------- |
| `AMS_DB`             | `sqlite`                             | `mssql` to switch to SQL Server     |
| `AMS_DB_NAME`        | `AMS-TEST-2`                         | Database name                        |
| `AMS_DB_HOST`        | `localhost`                          | SQL Server host                      |
| `AMS_DB_PORT`        | `1433`                               | SQL Server port                      |
| `AMS_DB_USER`        | `sa`                                 | Login user                           |
| `AMS_DB_PASSWORD`    | (empty)                              | Login password                       |
| `AMS_DB_DRIVER`     | `ODBC Driver 18 for SQL Server`     | ODBC driver name                     |

"ODBC Driver 18 for SQL Server" must be installed on the machine that
runs the portal. `TrustServerCertificate=yes` is set for local dev.

### Files added for SQL Server

```
sqlserver/
├── 01-create-database.sql      <- creates the empty AMS-TEST-2 database
└── 02-create-all-tables.sql    <- creates database + every table (DBA path)
Setup-SQL-Server.bat             <- one-click Windows helper (path A above)
Copy-Data-SQLite-to-SQLServer.bat <- moves records entered in SQLite into SQL Server
db-config.bat                    <- written by Setup-SQL-Server.bat; makes SQL
                                    Server mode persist across run-django.bat runs
```

## Where is my data stored? (FAQ)

**How do I know which database the portal is using right now?**

1. When `run-django.bat` starts it prints a banner:
   `Data storage : SQL Server - AMS-TEST-2 @ host,1433` or
   `Data storage : SQLite file db.sqlite3 in this folder`.
2. The Company Master page (System Admin > Company Master) shows the same
   under **Data storage** at the top of the form.

**I entered records but I cannot see them in MS SQL Server. Why?**

The portal stores data in **SQLite** (the file `db.sqlite3` in the project
folder) unless SQL Server mode is active. SQL Server mode requires the
`AMS_DB=mssql` environment variable. Previously that variable only lived
for the session in which `Setup-SQL-Server.bat` ran - after closing the
window, `run-django.bat` silently fell back to SQLite, so all new records
went to `db.sqlite3` and MS SQL Server stayed empty.

**Fix - two steps:**

1. Run `Setup-SQL-Server.bat` once. It now **writes `db-config.bat`** with
   your connection details, and `run-django.bat` loads that file on every
   start, so SQL Server mode persists. The startup banner confirms it.
2. If you already entered records while in SQLite mode, run
   `Copy-Data-SQLite-to-SQLServer.bat` once. It exports everything from
   `db.sqlite3`, creates missing tables in `AMS-TEST-2`, loads the records,
   re-seeds the logins, and archives the old SQLite file as
   `db.sqlite3.bak`.

To go back to SQLite deliberately: run `Setup-AMS-Test-2.bat` (it removes
`db-config.bat`), or delete `db-config.bat` manually.

**Where are records actually kept?**

| What                                  | Where it lives                                                        |
| ------------------------------------- | -------------------------------------------------------------------- |
| Employees, assets, mobiles, SIMs ...  | The active database: SQL Server `AMS-TEST-2` tables (`ams_*`) or `db.sqlite3` |
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
- **Database**: ORM models with a switchable engine (SQLite / SQL Server).
  Passwords use Django's PBKDF2-SHA256 (same hasher family as the original).
- **Sessions**: Django sessions (8-hour lifetime, mirroring the original JWT
  expiry). CSRF protected.
- **Static assets**: vendored locally - htmx 1.9.12, Inter font, print
  stylesheet. No CDN required; works fully offline.

## Folder structure

```
AMS-Test-2/
├── manage.py                  <- Django entry point
├── requirements.txt           <- Django + openpyxl + mssql-django + pyodbc
├── Setup-AMS-Test-2.bat       <- one-time setup (Windows, SQLite)
├── Setup-SQL-Server.bat       <- one-time setup (Windows, SQL Server)
├── run-django.bat             <- start the portal (Windows)
├── sqlserver/
│   ├── 01-create-database.sql  <- creates empty AMS-TEST-2 database
│   └── 02-create-all-tables.sql <- creates database + every table (DBA path)
├── amstest2/                  <- project settings (switchable DB)
│   └── settings.py
├── ams/                       <- the application
│   ├── access.py              <- roles, page registry, Role x Page matrix, gates
│   ├── models.py              <- full data model
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
│   └── management/commands/seed_admins.py
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
  while any asset of that type has the accessory issued.
- **Vendor Master** - Supplies multi-select from Vendor Category Master,
  GSTIN, "Used By" delete guard across assets + consumables + spare parts.
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
  26mm x 17.6875mm labels, margins 7/4/7/6 mm) and **Laptop Gate Pass** cards
  (serial, Asset Code No., employee, company address, stamp & signature).
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
