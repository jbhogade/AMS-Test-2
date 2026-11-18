@echo off
REM -------------------------------------------------------------
REM  AMS-Test-2 - start the portal (HTTP on port 8000)
REM
REM  Database mode (default = MS SQL Server):
REM    - db-config.bat (written by Setup-AMS-Test-2.bat /
REM      Setup-SQL-Server.bat) is loaded automatically and decides
REM      the target: AMS_DB=mssql -> SQL Server database AMS-TEST-2.
REM    - AMS_DB=sqlite in db-config.bat -> file db.sqlite3.
REM    - No db-config.bat at all -> SQL Server defaults
REM      (AMS-TEST-2 @ localhost,1433 user sa).
REM
REM  Connection failing? Run Test-SQL-Connection.bat (dbdoctor) -
REM  it checks every layer and prints concrete fixes.
REM  migrate failing with "There is already an object named ..."?
REM  Run Repair-Database.bat (dbrepair) - it syncs an existing
REM  database (e.g. after restoring the old AMS-Test backup).
REM -------------------------------------------------------------
title AMS-Test-2 Portal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Run Setup-AMS-Test-2.bat first, then start this file again.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

REM Load the saved database choice / SQL Server connection, if any
if exist "db-config.bat" call db-config.bat

REM Apply defaults BEFORE the banner block: %VARS% inside a
REM parenthesized block expand at parse time, so defaults must be
REM resolved on plain top-level lines to show up in the banner.
if "%AMS_DB_HOST%"=="" set AMS_DB_HOST=localhost
if "%AMS_DB_NAME%"=="" set AMS_DB_NAME=AMS-TEST-2
if "%AMS_DB_PORT%"=="" if "%AMS_DB_HOST:*\=%"=="%AMS_DB_HOST%" set AMS_DB_PORT=1433

if /I "%AMS_DB%"=="sqlite" goto BANNER_SQLITE

if "%AMS_DB_TRUSTED_CONNECTION%"=="" goto BANNER_MSSQL_SA

echo =============================================================
echo  AMS-Test-2 starting on http://127.0.0.1:8000/
echo  Data storage : SQL Server - %AMS_DB_NAME% @ %AMS_DB_HOST% (Windows Authentication)
echo  (set AMS_DB=sqlite in db-config.bat to use SQLite instead)
echo =============================================================
goto RUN

:BANNER_MSSQL_SA
echo =============================================================
echo  AMS-Test-2 starting on http://127.0.0.1:8000/
if "%AMS_DB_PORT%"=="" (
    echo  Data storage : SQL Server - %AMS_DB_NAME% @ %AMS_DB_HOST% ^(named instance^)
) else (
    echo  Data storage : SQL Server - %AMS_DB_NAME% @ %AMS_DB_HOST%,%AMS_DB_PORT%
)
echo  (login %AMS_DB_USER%; set AMS_DB=sqlite to use SQLite instead)
echo =============================================================
goto RUN

:BANNER_SQLITE
echo =============================================================
echo  AMS-Test-2 starting on http://127.0.0.1:8000/
echo  Data storage : SQLite file db.sqlite3 in this folder
echo  (MS SQL Server is the default - re-run Setup-AMS-Test-2.bat
echo   and choose Y to switch back)
echo =============================================================
goto RUN

:RUN
echo Press Ctrl+C to stop.
python manage.py runserver 0.0.0.0:8000
pause
