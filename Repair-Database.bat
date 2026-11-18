@echo off
REM -------------------------------------------------------------
REM  AMS-Test-2 - repair an existing database (Windows, one-click)
REM
REM  Fixes the migrate error
REM    42S01 / 2714 "There is already an object named 'ams_company'
REM    in the database"
REM
REM  This happens when AMS-TEST-2 already contains tables but the
REM  migration bookkeeping does not match - e.g. after restoring the
REM  old AMS-Test backup over the database, or after a DBA pre-created
REM  the tables. `migrate` can only CREATE tables; dbrepair also adds
REM  missing columns to existing tables and marks every migration as
REM  applied. Existing rows are never deleted or overwritten.
REM
REM  Equivalent command line:
REM    python manage.py dbrepair            (add --dry-run to preview)
REM -------------------------------------------------------------
title AMS-Test-2 - Database Schema Repair
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Run Setup-AMS-Test-2.bat first, then run this repair again.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

if exist "db-config.bat" call db-config.bat

python manage.py dbrepair
if errorlevel 1 (
    echo.
    echo The repair finished with problems - see the [FAIL] items above.
    echo Fix them and run Repair-Database.bat again (it is safe to
    echo run repeatedly).
    pause
    exit /b 1
)

echo.
echo --- Confirming migrate is now a no-op -------------------------
python manage.py migrate

echo.
echo --- Seeding the two login accounts ----------------------------
python manage.py seed_admins

echo.
echo =============================================================
echo  Repair complete. Start the portal with run-django.bat.
echo  Old AMS-Test data restored into this database? Run
echo  Import-From-AMS-Test.bat to bring the rows into the new
echo  schema (dbrepair keeps them untouched, it never drops data).
echo =============================================================
pause
