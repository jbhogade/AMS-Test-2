@echo off
REM -------------------------------------------------------------
REM  AMS-Test-2 - import all data from the OLD AMS-Test project
REM
REM  The old portal stored its data in the SQL Server database
REM  AMS-TEST (the C# API's backend). This wizard copies every
REM  collection into the new AMS-TEST-2 database:
REM
REM    masters, employees (+ managers), assets & mobiles (+ history,
REM    accessories, replacements), SIM cards, consumables, spare
REM    parts + movement logs, exit records, user accounts (old
REM    passwords keep working), company profile INCLUDING the logo
REM    and banner, report prefs, role access matrix, activity log.
REM
REM  Source options:
REM    - live SQL Server connection (host / login asked below), or
REM    - a SQLite mirror file produced offline (--source-sqlite)
REM
REM  Run this AFTER Setup-AMS-Test-2.bat / Setup-SQL-Server.bat so
REM  the new AMS-TEST-2 tables exist.
REM
REM  NOTE: prompts live on top-level lines (GOTO flow) on purpose -
REM  inside a parenthesized ( ... ) block batch would expand %VARS%
REM  BEFORE the prompts run and silently throw your input away.
REM -------------------------------------------------------------
title AMS-Test-2 - Import from old AMS-Test
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Run Setup-AMS-Test-2.bat first, then run this import again.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

echo =============================================================
echo   Import data from the OLD AMS-Test into AMS-Test-2
echo =============================================================
echo.
echo   Source type:
echo     1 = SQL Server connection  (the old AMS-TEST database)
echo     2 = SQLite mirror file     (offline copy of the old data)
echo.
set /p SRC_TYPE=Source [1/2] (default 1):
if "%SRC_TYPE%"=="" set SRC_TYPE=1

set EXTRA_OPTS=

if "%SRC_TYPE%"=="2" goto SQLITE_SRC

REM -------------------------------------------------------------
REM  SQL Server source - one prompt per line (fresh %VAR% expansion)
REM -------------------------------------------------------------
echo.
set /p LEG_HOST=Old database host or named instance (default: localhost):
if "%LEG_HOST%"=="" set LEG_HOST=localhost

REM  A named instance (host\SQLEXPRESS) has no fixed port; a typed
REM  port would be invalid together with it, so ignore the port then.
set "LEG_INSTANCE="
echo %LEG_HOST% | findstr /C:"\\" >nul
if not errorlevel 1 set LEG_INSTANCE=1

set /p LEG_PORT=Port (default 1433 - leave BLANK for a named instance):

set /p LEG_NAME=Old database name (default: AMS-TEST):
if "%LEG_NAME%"=="" set LEG_NAME=AMS-TEST

set /p LEG_USER=Login user (default: sa - leave BLANK for Windows Authentication):
if not "%LEG_USER%"=="" goto LEG_SQLAUTH

set EXTRA_OPTS=--legacy-host "%LEG_HOST%" --legacy-name "%LEG_NAME%" --legacy-trusted
goto LEG_PORT_APPEND

:LEG_SQLAUTH
set /p LEG_PASS=Login password:
set EXTRA_OPTS=--legacy-host "%LEG_HOST%" --legacy-name "%LEG_NAME%" --legacy-user "%LEG_USER%" --legacy-password "%LEG_PASS%"

:LEG_PORT_APPEND
if not "%LEG_PORT%"=="" if not defined LEG_INSTANCE set EXTRA_OPTS=%EXTRA_OPTS% --legacy-port %LEG_PORT%
if "%LEG_PORT%"=="" if not defined LEG_INSTANCE set EXTRA_OPTS=%EXTRA_OPTS% --legacy-port 1433
goto ASK_DRY

REM -------------------------------------------------------------
REM  SQLite mirror source
REM -------------------------------------------------------------
:SQLITE_SRC
set /p SQLITE_PATH=Path to the SQLite mirror file:
if not exist "%SQLITE_PATH%" (
    echo File not found: %SQLITE_PATH%
    pause
    exit /b 1
)
set EXTRA_OPTS=--source-sqlite "%SQLITE_PATH%"

:ASK_DRY
echo.
echo Dry-run first (parse + report, write nothing)? Recommended.
set /p DRY=Dry run [Y/n]:
if /I "%DRY%"=="N" goto REALRUN

echo.
echo --- DRY RUN ---------------------------------------------------
python manage.py import_legacy %EXTRA_OPTS% --dry-run
echo.
set /p GO=Continue with the real import? [Y/n]:
if /I "%GO%"=="N" (
    echo Nothing was changed. Re-run this script any time.
    pause
    exit /b 0
)

:REALRUN
set /p WIPE=Wipe existing data in AMS-TEST-2 before importing? [Y/n]:
if /I "%WIPE%"=="Y" set EXTRA_OPTS=%EXTRA_OPTS% --wipe

echo.
echo --- Making sure the new tables exist (migrate) ----------------
python manage.py migrate
if errorlevel 1 (
    echo Could not create/reach the AMS-TEST-2 tables. Fix the
    echo connection (Setup-SQL-Server.bat or Test-SQL-Connection.bat)
    echo and re-run.
    pause
    exit /b 1
)

echo.
echo --- Importing -------------------------------------------------
python manage.py import_legacy %EXTRA_OPTS%
if errorlevel 1 (
    echo Import failed - nothing further to do. Read the error above.
    pause
    exit /b 1
)

echo.
echo =============================================================
echo   Import finished.
echo   Start the portal with run-django.bat and log in with the
echo   OLD AMS-Test usernames and passwords (they still work -
echo   passwords were migrated, including operator.sys / testadmin).
echo.
echo   The company logo/banner were restored too: files live in
echo   the media\company folder of this project.
echo =============================================================
pause
