@echo off
REM -------------------------------------------------------------
REM  AMS-Test-2 - test the database connection (diagnostics)
REM
REM  Runs the dbdoctor command: resolves the saved connection
REM  (db-config.bat), then checks layer by layer:
REM    ODBC driver -> network/port -> SQL login -> database -> Django
REM  Every failure is printed with a concrete fix (TCP/IP disabled,
REM  Windows-only auth, missing driver, SQL Browser, firewall, ...).
REM
REM  Safe to run at any time - it changes nothing unless you pass
REM  --create-database to the command line version.
REM -------------------------------------------------------------
title AMS-Test-2 - Database Connection Doctor
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Run Setup-AMS-Test-2.bat first, then run this test again.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

if exist "db-config.bat" call db-config.bat

python manage.py dbdoctor
echo.
pause
