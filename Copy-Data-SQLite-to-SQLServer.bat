@echo off
REM -------------------------------------------------------------
REM  AMS-Test-2 - copy data from SQLite into SQL Server (one-time)
REM
REM  If you have been running the portal WITHOUT SQL Server active
REM  (i.e. in SQLite mode), every record you entered lives in the
REM  file db.sqlite3 next to this script - NOT in MS SQL Server.
REM
REM  This script moves that data into AMS-TEST-2:
REM    1. Exports all records from db.sqlite3 to ams-data.json
REM    2. Creates any missing tables in AMS-TEST-2 (migrate)
REM    3. Clears placeholder rows (flush - e.g. the pre-seeded logins)
REM    4. Loads the records into SQL Server (loaddata)
REM    5. Re-seeds the two login accounts (idempotent)
REM    6. Renames db.sqlite3 to db.sqlite3.bak so SQLite mode
REM       cannot "look" like the live database anymore
REM
REM  Requires db-config.bat (run Setup-SQL-Server.bat first).
REM -------------------------------------------------------------
title AMS-Test-2 - Copy SQLite data to SQL Server
cd /d "%~dp0"

echo =============================================================
echo   AMS-Test-2 - move data from SQLite to SQL Server
echo =============================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo Run Setup-AMS-Test-2.bat or Setup-SQL-Server.bat first.
    pause
    exit /b 1
)

if not exist "db-config.bat" (
    echo db-config.bat not found.
    echo Run Setup-SQL-Server.bat once to configure SQL Server, then
    echo run this script again.
    pause
    exit /b 1
)

if not exist "db.sqlite3" (
    echo There is no db.sqlite3 here - nothing to copy.
    echo Your portal is probably already running on SQL Server.
    pause
    exit /b 0
)

call venv\Scripts\activate.bat

echo Step 1 of 6 - exporting records from db.sqlite3 ...
python manage.py dumpdata --natural-foreign --natural-primary ^
    -e contenttypes -e auth.permission -e sessions -e admin.logentry ^
    -o ams-data.json --indent 2
if errorlevel 1 (
    echo Export failed. Nothing was changed.
    pause
    exit /b 1
)

REM Switch to SQL Server for steps 2-5
call db-config.bat
echo.
echo Step 2 of 6 - creating missing tables in AMS-TEST-2 (%AMS_DB_HOST%) ...
python manage.py migrate
if errorlevel 1 (
    echo Could not connect to SQL Server / migrate failed.
    echo ams-data.json is kept - fix the connection and re-run.
    pause
    exit /b 1
)

echo.
echo Step 3 of 6 - clearing any placeholder rows in AMS-TEST-2 ...
REM (flush removes rows such as the pre-seeded logins so loaddata cannot
REM  collide on primary keys; the table structure is kept)
python manage.py flush --noinput
if errorlevel 1 (
    echo Flush failed. ams-data.json is kept - check the error and re-run.
    pause
    exit /b 1
)

echo.
echo Step 4 of 6 - loading records into SQL Server ...
python manage.py loaddata ams-data.json
if errorlevel 1 (
    echo Load failed. ams-data.json is kept - check the error and re-run.
    pause
    exit /b 1
)

echo.
echo Step 5 of 6 - restoring migration markers + seeding logins ...
REM (flush empties django_migrations too - `migrate --fake` re-records
REM  them so future `migrate` calls stay no-ops; seed_admins is idempotent)
python manage.py migrate --fake
python manage.py seed_admins

echo.
echo Step 6 of 6 - archiving db.sqlite3 ...
move /y "db.sqlite3" "db.sqlite3.bak" >nul
echo Done. SQLite file kept as db.sqlite3.bak (safe to delete later).

del "ams-data.json"

echo.
echo =============================================================
echo   Data moved to SQL Server successfully.
echo   Run run-django.bat - the console will show
echo   "Data storage: SQL Server - AMS-TEST-2" on startup, and the
echo   Company Master page shows the same under "Data storage".
echo =============================================================
pause
