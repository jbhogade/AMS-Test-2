@echo off
REM -------------------------------------------------------------
REM  AMS-Test-2 - one-time setup (Windows, SQLite mode)
REM  Creates a virtualenv, installs requirements, migrates the
REM  database and seeds the two login accounts.
REM
REM  If db-config.bat exists (SQL Server mode from Setup-SQL-Server.bat)
REM  it is removed so the portal goes back to SQLite. Re-run
REM  Setup-SQL-Server.bat any time to switch back to SQL Server.
REM -------------------------------------------------------------
title AMS-Test-2 Setup
cd /d "%~dp0"

if exist "db-config.bat" (
    echo Removing db-config.bat - portal will use SQLite again.
    del "db-config.bat"
)

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.11+ from python.org
    echo and tick "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing requirements...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo Migrating database...
python manage.py migrate

echo Seeding login accounts...
python manage.py seed_admins

echo.
echo =============================================================
echo  Setup complete. Run run-django.bat to start the portal.
echo  Logins:  operator.sys / Sr#Ops@2026   (Supreme Root)
echo           testadmin   / Admin@#$12345  (Super Root)
echo.
echo  This configured SQLite. For SQL Server instead, run:
echo     Setup-SQL-Server.bat
echo =============================================================
pause
