@echo off
REM -------------------------------------------------------------
REM  AMS-Test-2 - start the portal (HTTP on port 8000)
REM
REM  Database mode:
REM    - If db-config.bat exists (written by Setup-SQL-Server.bat),
REM      it is loaded automatically and the portal uses SQL Server.
REM    - Without it, the portal uses SQLite (db.sqlite3).
REM -------------------------------------------------------------
title AMS-Test-2 Portal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo Run Setup-AMS-Test-2.bat (SQLite) or Setup-SQL-Server.bat (SQL Server)
    echo first, then start this file again.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

REM Load the saved SQL Server connection, if any
if exist "db-config.bat" call db-config.bat

if /I "%AMS_DB%"=="mssql" (
    echo =============================================================
    echo  AMS-Test-2 starting on http://127.0.0.1:8000/
    echo  Data storage : SQL Server - %AMS_DB_NAME% @ %AMS_DB_HOST%,%AMS_DB_PORT%
    echo                 (login %AMS_DB_USER% - from db-config.bat)
    echo =============================================================
) else (
    echo =============================================================
    echo  AMS-Test-2 starting on http://127.0.0.1:8000/
    echo  Data storage : SQLite file db.sqlite3 in this folder
    echo  (To use SQL Server instead, run Setup-SQL-Server.bat once)
    echo =============================================================
)
echo Press Ctrl+C to stop.
python manage.py runserver 0.0.0.0:8000
pause
