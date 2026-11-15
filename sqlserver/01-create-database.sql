-- ===========================================================================
--  AMS-TEST-2  -  Database creation script (recommended path)
--
--  This script creates ONLY the empty AMS-TEST-2 database. After running it,
--  Django creates every table itself via `python manage.py migrate` (using
--  mssql-django). This is the canonical Django + SQL Server workflow.
--
--  Run with:  sqlcmd -S localhost -U sa -P <password> -i 01-create-database.sql
--    or open in SSMS and press F5.
--
--  After running this script:
--    1. pip install mssql-django pyodbc
--    2. set AMS_DB=mssql
--       set AMS_DB_HOST=localhost        (or your SQL Server host)
--       set AMS_DB_USER=sa
--       set AMS_DB_PASSWORD=<your-sa-password>
--    3. python manage.py migrate
--    4. python manage.py seed_admins
--
--  Safe to re-run (idempotent): the CREATE is guarded with IF DB_ID.
-- ===========================================================================

SET NOCOUNT ON;

IF DB_ID (N'AMS-TEST-2') IS NULL
BEGIN
    CREATE DATABASE [AMS-TEST-2];
    PRINT N'Created database AMS-TEST-2';
END
ELSE
    PRINT N'Database AMS-TEST-2 already exists - skipping create';
GO

-- Optional: verify the database exists and print its name
USE [AMS-TEST-2];
GO
PRINT N'Using database: ' + DB_NAME();
GO
