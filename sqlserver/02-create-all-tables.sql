-- ============================================================================
-- AMS-TEST-2  -  SQL Server schema (database + all tables)
-- 
-- Auto-generated from the Django models of AMS-Test-2 (ams/models.py).
-- This script creates the AMS-TEST-2 database and every table Django
-- would create on `python manage.py migrate` against SQL Server.
-- 
-- Run with:  sqlcmd -S localhost -U sa -P <password> -i 02-create-all-tables.sql
--   or open in SSMS and execute (F5).
-- 
-- Safe to re-run: each CREATE TABLE uses IF NOT EXISTS checks.
-- ============================================================================

SET NOCOUNT ON;

-- ----------------------------------------------------------------
-- 1. Create the AMS-TEST-2 database
-- ----------------------------------------------------------------
IF DB_ID (N'AMS-TEST-2') IS NULL
BEGIN
    CREATE DATABASE [AMS-TEST-2];
    PRINT N'Created database AMS-TEST-2';
END
ELSE
    PRINT N'Database AMS-TEST-2 already exists - skipping create';
GO

USE [AMS-TEST-2];
GO


-- ============================================================================
-- Django framework tables (auth / contenttypes / sessions / admin / migrations)
-- Schema matches Django 5.2 standard + mssql-django column types.
-- Each CREATE TABLE is guarded with IF OBJECT_ID so re-running is safe.
-- ============================================================================

IF OBJECT_ID (N'django_migrations', N'U') IS NULL
BEGIN
CREATE TABLE [django_migrations] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [app] nvarchar (255) NOT NULL,
  [name] nvarchar (255) NOT NULL,
  [applied] datetime2 (6) NOT NULL
);
END
GO

IF OBJECT_ID (N'django_content_type', N'U') IS NULL
BEGIN
CREATE TABLE [django_content_type] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [app_label] nvarchar (100) NOT NULL,
  [model] nvarchar (100) NOT NULL,
  CONSTRAINT [UQ_django_content_type_app_label_model_76a6de8a_uniq] UNIQUE ([app_label], [model])
);
END
GO

IF OBJECT_ID (N'auth_permission', N'U') IS NULL
BEGIN
CREATE TABLE [auth_permission] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [content_type_id] bigint NOT NULL,
  [codename] nvarchar (100) NOT NULL,
  [name] nvarchar (255) NOT NULL,
  CONSTRAINT [UQ_auth_permission_content_type_id_codename_01ab375a_uniq] UNIQUE ([content_type_id], [codename]),
  CONSTRAINT [FK_auth_permission_content_type_id_django_content_type] FOREIGN KEY ([content_type_id]) REFERENCES [django_content_type] ([id]) ON DELETE NO ACTION
);
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'auth_permission_content_type_id_2f476e4b' AND object_id = OBJECT_ID(N'auth_permission'))
CREATE INDEX [auth_permission_content_type_id_2f476e4b] ON [auth_permission] ([content_type_id]);
GO

IF OBJECT_ID (N'auth_group', N'U') IS NULL
BEGIN
CREATE TABLE [auth_group] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (150) NOT NULL,
  CONSTRAINT [UQ_auth_group_name_unique] UNIQUE ([name])
);
END
GO

IF OBJECT_ID (N'auth_group_permissions', N'U') IS NULL
BEGIN
CREATE TABLE [auth_group_permissions] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [group_id] bigint NOT NULL,
  [permission_id] bigint NOT NULL,
  CONSTRAINT [UQ_auth_group_permissions_group_id_permission_id_0cd325b0_uniq] UNIQUE ([group_id], [permission_id]),
  CONSTRAINT [FK_auth_group_permissions_group_id_auth_group] FOREIGN KEY ([group_id]) REFERENCES [auth_group] ([id]) ON DELETE NO ACTION,
  CONSTRAINT [FK_auth_group_permissions_permission_id_auth_permission] FOREIGN KEY ([permission_id]) REFERENCES [auth_permission] ([id]) ON DELETE NO ACTION
);
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'auth_group_permissions_group_id_b120cbf9' AND object_id = OBJECT_ID(N'auth_group_permissions'))
CREATE INDEX [auth_group_permissions_group_id_b120cbf9] ON [auth_group_permissions] ([group_id]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'auth_group_permissions_permission_id_84c5c92e' AND object_id = OBJECT_ID(N'auth_group_permissions'))
CREATE INDEX [auth_group_permissions_permission_id_84c5c92e] ON [auth_group_permissions] ([permission_id]);
GO

IF OBJECT_ID (N'auth_user', N'U') IS NULL
BEGIN
CREATE TABLE [auth_user] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [password] nvarchar (128) NOT NULL,
  [last_login] datetime2 (6) NULL,
  [is_superuser] bit NOT NULL,
  [username] nvarchar (150) NOT NULL,
  [first_name] nvarchar (150) NOT NULL,
  [last_name] nvarchar (150) NOT NULL,
  [email] nvarchar (254) NOT NULL,
  [is_staff] bit NOT NULL,
  [is_active] bit NOT NULL,
  [date_joined] datetime2 (6) NOT NULL,
  CONSTRAINT [UQ_auth_user_username_unique] UNIQUE ([username])
);
END
GO

IF OBJECT_ID (N'auth_user_groups', N'U') IS NULL
BEGIN
CREATE TABLE [auth_user_groups] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [user_id] bigint NOT NULL,
  [group_id] bigint NOT NULL,
  CONSTRAINT [UQ_auth_user_groups_user_id_group_id_9435c1d1_uniq] UNIQUE ([user_id], [group_id]),
  CONSTRAINT [FK_auth_user_groups_user_id_auth_user] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE NO ACTION,
  CONSTRAINT [FK_auth_user_groups_group_id_auth_group] FOREIGN KEY ([group_id]) REFERENCES [auth_group] ([id]) ON DELETE NO ACTION
);
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'auth_user_groups_user_id_6a12f856' AND object_id = OBJECT_ID(N'auth_user_groups'))
CREATE INDEX [auth_user_groups_user_id_6a12f856] ON [auth_user_groups] ([user_id]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'auth_user_groups_group_id_977dec4d' AND object_id = OBJECT_ID(N'auth_user_groups'))
CREATE INDEX [auth_user_groups_group_id_977dec4d] ON [auth_user_groups] ([group_id]);
GO

IF OBJECT_ID (N'auth_user_user_permissions', N'U') IS NULL
BEGIN
CREATE TABLE [auth_user_user_permissions] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [user_id] bigint NOT NULL,
  [permission_id] bigint NOT NULL,
  CONSTRAINT [UQ_auth_user_user_permissions_user_id_permission_id_14a6fec6_uniq] UNIQUE ([user_id], [permission_id]),
  CONSTRAINT [FK_auth_user_user_permissions_user_id_auth_user] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE NO ACTION,
  CONSTRAINT [FK_auth_user_user_permissions_permission_id_auth_permission] FOREIGN KEY ([permission_id]) REFERENCES [auth_permission] ([id]) ON DELETE NO ACTION
);
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'auth_user_user_permissions_user_id_a95ead1b' AND object_id = OBJECT_ID(N'auth_user_user_permissions'))
CREATE INDEX [auth_user_user_permissions_user_id_a95ead1b] ON [auth_user_user_permissions] ([user_id]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'auth_user_user_permissions_permission_id_433f0333' AND object_id = OBJECT_ID(N'auth_user_user_permissions'))
CREATE INDEX [auth_user_user_permissions_permission_id_433f0333] ON [auth_user_user_permissions] ([permission_id]);
GO

IF OBJECT_ID (N'django_session', N'U') IS NULL
BEGIN
CREATE TABLE [django_session] (
  [session_key] nvarchar (40) NOT NULL PRIMARY KEY,
  [session_data] nvarchar (max) NOT NULL,
  [expire_date] datetime2 (6) NOT NULL
);
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'django_session_expire_date_a5c626fe' AND object_id = OBJECT_ID(N'django_session'))
CREATE INDEX [django_session_expire_date_a5c626fe] ON [django_session] ([expire_date]);
GO

IF OBJECT_ID (N'django_admin_log', N'U') IS NULL
BEGIN
CREATE TABLE [django_admin_log] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [action_time] datetime2 (6) NOT NULL,
  [user_id] bigint NOT NULL,
  [content_type_id] bigint NULL,
  [object_id] nvarchar (max) NULL,
  [object_repr] nvarchar (200) NOT NULL,
  [action_flag] smallint NOT NULL,
  [change_message] nvarchar (max) NOT NULL,
  CONSTRAINT [FK_django_admin_log_user_id_auth_user] FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE NO ACTION,
  CONSTRAINT [FK_django_admin_log_content_type_id_django_content_type] FOREIGN KEY ([content_type_id]) REFERENCES [django_content_type] ([id]) ON DELETE NO ACTION
);
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'django_admin_log_user_id_c5644b4f' AND object_id = OBJECT_ID(N'django_admin_log'))
CREATE INDEX [django_admin_log_user_id_c5644b4f] ON [django_admin_log] ([user_id]);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'django_admin_log_content_type_id_c4bce8eb' AND object_id = OBJECT_ID(N'django_admin_log'))
CREATE INDEX [django_admin_log_content_type_id_c4bce8eb] ON [django_admin_log] ([content_type_id]);
GO

GO

-- ============================================================================
-- AMS application tables (ams/models.py)
-- Created in dependency order so FK targets exist before referrers.
-- ============================================================================

-- Site  (table: ams_site)
IF OBJECT_ID (N'ams_site', N'U') IS NULL
BEGIN
CREATE TABLE [ams_site] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (120) NOT NULL CONSTRAINT [UQ_ams_site_name] UNIQUE,
  [shortform] nvarchar (4) NOT NULL,
  [address] nvarchar (255) NOT NULL,
  [active] bit NOT NULL
);
END
GO

-- Department  (table: ams_department)
IF OBJECT_ID (N'ams_department', N'U') IS NULL
BEGIN
CREATE TABLE [ams_department] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (120) NOT NULL CONSTRAINT [UQ_ams_department_name] UNIQUE,
  [shortform] nvarchar (4) NOT NULL,
  [active] bit NOT NULL
);
END
GO

-- Designation  (table: ams_designation)
IF OBJECT_ID (N'ams_designation', N'U') IS NULL
BEGIN
CREATE TABLE [ams_designation] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (120) NOT NULL CONSTRAINT [UQ_ams_designation_name] UNIQUE,
  [active] bit NOT NULL
);
END
GO

-- AssetCategory  (table: ams_assetcategory)
IF OBJECT_ID (N'ams_assetcategory', N'U') IS NULL
BEGIN
CREATE TABLE [ams_assetcategory] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (120) NOT NULL CONSTRAINT [UQ_ams_assetcategory_name] UNIQUE,
  [used_on] nvarchar (10) NOT NULL,
  [active] bit NOT NULL
);
END
GO

-- AssetType  (table: ams_assettype)
IF OBJECT_ID (N'ams_assettype', N'U') IS NULL
BEGIN
CREATE TABLE [ams_assettype] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (120) NOT NULL CONSTRAINT [UQ_ams_assettype_name] UNIQUE,
  [shortform] nvarchar (4) NOT NULL,
  [category_id] bigint NULL,
  [active] bit NOT NULL
);
END
GO

-- AssetMake  (table: ams_assetmake)
IF OBJECT_ID (N'ams_assetmake', N'U') IS NULL
BEGIN
CREATE TABLE [ams_assetmake] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (120) NOT NULL,
  [asset_type_id] bigint NULL,
  [active] bit NOT NULL
);
END
GO

-- VendorCategory  (table: ams_vendorcategory)
IF OBJECT_ID (N'ams_vendorcategory', N'U') IS NULL
BEGIN
CREATE TABLE [ams_vendorcategory] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (120) NOT NULL CONSTRAINT [UQ_ams_vendorcategory_name] UNIQUE,
  [description] nvarchar (max) NOT NULL,
  [active] bit NOT NULL
);
END
GO

-- Vendor  (table: ams_vendor)
IF OBJECT_ID (N'ams_vendor', N'U') IS NULL
BEGIN
CREATE TABLE [ams_vendor] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (160) NOT NULL CONSTRAINT [UQ_ams_vendor_name] UNIQUE,
  [contact_person] nvarchar (120) NOT NULL,
  [phone] nvarchar (40) NOT NULL,
  [email] nvarchar (120) NOT NULL,
  [city] nvarchar (120) NOT NULL,
  [gstin] nvarchar (15) NOT NULL,
  [remarks] nvarchar (max) NOT NULL,
  [active] bit NOT NULL
);
END
GO

-- Accessory  (table: ams_accessory)
IF OBJECT_ID (N'ams_accessory', N'U') IS NULL
BEGIN
CREATE TABLE [ams_accessory] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [code] nvarchar (16) NOT NULL CONSTRAINT [UQ_ams_accessory_code] UNIQUE,
  [name] nvarchar (120) NOT NULL,
  [asset_type_id] bigint NULL,
  [site_id] bigint NULL,
  [active] bit NOT NULL
);
END
GO

-- SimOperator  (table: ams_simoperator)
IF OBJECT_ID (N'ams_simoperator', N'U') IS NULL
BEGIN
CREATE TABLE [ams_simoperator] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (120) NOT NULL CONSTRAINT [UQ_ams_simoperator_name] UNIQUE,
  [helpline] nvarchar (60) NOT NULL,
  [website] nvarchar (160) NOT NULL,
  [active] bit NOT NULL
);
END
GO

-- SimPlan  (table: ams_simplan)
IF OBJECT_ID (N'ams_simplan', N'U') IS NULL
BEGIN
CREATE TABLE [ams_simplan] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (120) NOT NULL CONSTRAINT [UQ_ams_simplan_name] UNIQUE,
  [plan_type] nvarchar (120) NOT NULL,
  [description] nvarchar (max) NOT NULL,
  [active] bit NOT NULL
);
END
GO

-- ConsumableCategory  (table: ams_consumablecategory)
IF OBJECT_ID (N'ams_consumablecategory', N'U') IS NULL
BEGIN
CREATE TABLE [ams_consumablecategory] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (120) NOT NULL CONSTRAINT [UQ_ams_consumablecategory_name] UNIQUE,
  [description] nvarchar (max) NOT NULL,
  [active] bit NOT NULL
);
END
GO

-- UnitOfMeasure  (table: ams_unitofmeasure)
IF OBJECT_ID (N'ams_unitofmeasure', N'U') IS NULL
BEGIN
CREATE TABLE [ams_unitofmeasure] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (60) NOT NULL CONSTRAINT [UQ_ams_unitofmeasure_name] UNIQUE,
  [description] nvarchar (max) NOT NULL,
  [active] bit NOT NULL
);
END
GO

-- SparePartCategory  (table: ams_sparepartcategory)
IF OBJECT_ID (N'ams_sparepartcategory', N'U') IS NULL
BEGIN
CREATE TABLE [ams_sparepartcategory] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (120) NOT NULL CONSTRAINT [UQ_ams_sparepartcategory_name] UNIQUE,
  [description] nvarchar (max) NOT NULL,
  [active] bit NOT NULL
);
END
GO

-- PrintTerm  (table: ams_printterm)
IF OBJECT_ID (N'ams_printterm', N'U') IS NULL
BEGIN
CREATE TABLE [ams_printterm] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [term_id] nvarchar (12) NOT NULL CONSTRAINT [UQ_ams_printterm_term_id] UNIQUE,
  [text] nvarchar (max) NOT NULL,
  [used_on] nvarchar (30) NOT NULL,
  [sort_order] int NOT NULL,
  [active] bit NOT NULL
);
END
GO

-- Employee  (table: ams_employee)
IF OBJECT_ID (N'ams_employee', N'U') IS NULL
BEGIN
CREATE TABLE [ams_employee] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [ams_id] nvarchar (32) NOT NULL CONSTRAINT [UQ_ams_employee_ams_id] UNIQUE,
  [emp_id] nvarchar (40) NOT NULL,
  [name] nvarchar (160) NOT NULL,
  [department_id] bigint NULL,
  [designation] nvarchar (120) NOT NULL,
  [site_id] bigint NULL,
  [manager_id] bigint NULL,
  [contact] nvarchar (40) NOT NULL,
  [email] nvarchar (160) NOT NULL,
  [status] nvarchar (10) NOT NULL,
  [exit_date] date NULL,
  [exit_reason] nvarchar (60) NOT NULL,
  [exit_remarks] nvarchar (max) NOT NULL,
  [reactivated_date] date NULL,
  [reactivation_remarks] nvarchar (max) NOT NULL,
  [created_at] datetime2 (6) NOT NULL
);
END
GO

-- ExitRecord  (table: ams_exitrecord)
IF OBJECT_ID (N'ams_exitrecord', N'U') IS NULL
BEGIN
CREATE TABLE [ams_exitrecord] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [exit_id] nvarchar (16) NOT NULL CONSTRAINT [UQ_ams_exitrecord_exit_id] UNIQUE,
  [employee_id] bigint NOT NULL,
  [ams_id] nvarchar (32) NOT NULL,
  [emp_id] nvarchar (40) NOT NULL,
  [emp_name] nvarchar (160) NOT NULL,
  [emp_dept] nvarchar (120) NOT NULL,
  [emp_designation] nvarchar (120) NOT NULL,
  [exit_date] date NOT NULL,
  [exit_reason] nvarchar (60) NOT NULL,
  [exit_remarks] nvarchar (max) NOT NULL,
  [facilities_disabled] nvarchar (max) NOT NULL,
  [facilities_na] nvarchar (max) NOT NULL,
  [direct_assets] nvarchar (max) NOT NULL,
  [direct_mobiles] nvarchar (max) NOT NULL,
  [direct_sims] nvarchar (max) NOT NULL,
  [subordinate_assets] nvarchar (max) NOT NULL,
  [team_transferred_to] nvarchar (max) NULL,
  [reactivated] bit NOT NULL,
  [created_at] datetime2 (6) NOT NULL
);
END
GO

-- SimCard  (table: ams_simcard)
IF OBJECT_ID (N'ams_simcard', N'U') IS NULL
BEGIN
CREATE TABLE [ams_simcard] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [sim_id] nvarchar (16) NOT NULL CONSTRAINT [UQ_ams_simcard_sim_id] UNIQUE,
  [iccid] nvarchar (60) NOT NULL,
  [mobile_number] nvarchar (24) NOT NULL CONSTRAINT [UQ_ams_simcard_mobile_number] UNIQUE,
  [operator_id] bigint NULL,
  [plan_id] bigint NULL,
  [status] nvarchar (10) NOT NULL,
  [site_id] bigint NULL,
  [activation_date] date NULL,
  [vendor_id] bigint NULL,
  [cost] decimal(14, 2) NULL,
  [remarks] nvarchar (max) NOT NULL,
  [assigned_to_id] bigint NULL,
  [assigned_to_sub_id] bigint NULL,
  [assigned_sub_text] nvarchar (160) NOT NULL,
  [assigned_date] date NULL,
  [linked_mobile_id] bigint NULL,
  [personal_mobile] bit NOT NULL,
  [return_date] date NULL,
  [created_at] datetime2 (6) NOT NULL
);
END
GO

-- Asset  (table: ams_asset)
IF OBJECT_ID (N'ams_asset', N'U') IS NULL
BEGIN
CREATE TABLE [ams_asset] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [kind] nvarchar (8) NOT NULL,
  [ams_asset_id] nvarchar (48) NOT NULL CONSTRAINT [UQ_ams_asset_ams_asset_id] UNIQUE,
  [display_id] nvarchar (32) NOT NULL,
  [is_legacy_id] bit NOT NULL,
  [category_id] bigint NULL,
  [type_id] bigint NULL,
  [make_id] bigint NULL,
  [name] nvarchar (160) NOT NULL,
  [model] nvarchar (120) NOT NULL,
  [model_number] nvarchar (120) NOT NULL,
  [imei1] nvarchar (40) NOT NULL,
  [imei2] nvarchar (40) NOT NULL,
  [battery_no] nvarchar (60) NOT NULL,
  [charger_no] nvarchar (60) NOT NULL,
  [sim_id] bigint NULL,
  [serial_number] nvarchar (120) NOT NULL,
  [purchase_site_id] bigint NULL,
  [current_site_id] bigint NULL,
  [purchase_date] date NULL,
  [warranty_end] date NULL,
  [vendor_id] bigint NULL,
  [purchase_cost] decimal(14, 2) NULL,
  [remarks] nvarchar (max) NOT NULL,
  [status] nvarchar (24) NOT NULL,
  [assigned_to_id] bigint NULL,
  [assigned_to_sub_id] bigint NULL,
  [assigned_sub_text] nvarchar (160) NOT NULL,
  [assigned_date] date NULL,
  [return_date] date NULL,
  [replaces_asset_id] bigint NULL,
  [replaces_reason] nvarchar (60) NOT NULL,
  [replaces_note] nvarchar (max) NOT NULL,
  [replaces_purchase_date] date NULL,
  [created_at] datetime2 (6) NOT NULL
);
END
GO

-- LifecycleEvent  (table: ams_lifecycleevent)
IF OBJECT_ID (N'ams_lifecycleevent', N'U') IS NULL
BEGIN
CREATE TABLE [ams_lifecycleevent] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [item_kind] nvarchar (8) NOT NULL,
  [item_key] nvarchar (48) NOT NULL,
  [item_label] nvarchar (64) NOT NULL,
  [date] date NOT NULL,
  [action] nvarchar (60) NOT NULL,
  [event_type] nvarchar (12) NOT NULL,
  [emp_id] bigint NULL,
  [emp_label] nvarchar (160) NOT NULL,
  [emp_dept] nvarchar (120) NOT NULL,
  [status_label] nvarchar (40) NOT NULL,
  [accessories] nvarchar (max) NOT NULL,
  [note] nvarchar (max) NOT NULL,
  [actor_username] nvarchar (60) NOT NULL,
  [actor_role] nvarchar (30) NOT NULL,
  [created_at] datetime2 (6) NOT NULL
);
END
GO

-- Consumable  (table: ams_consumable)
IF OBJECT_ID (N'ams_consumable', N'U') IS NULL
BEGIN
CREATE TABLE [ams_consumable] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [code] nvarchar (16) NOT NULL CONSTRAINT [UQ_ams_consumable_code] UNIQUE,
  [name] nvarchar (160) NOT NULL,
  [category_id] bigint NULL,
  [unit_id] bigint NULL,
  [site_id] bigint NULL,
  [qty] decimal(12, 2) NOT NULL,
  [reorder_level] decimal(12, 2) NOT NULL,
  [restock_date] date NULL,
  [warranty_date] date NULL,
  [unit_cost] decimal(14, 2) NULL,
  [vendor_id] bigint NULL,
  [remarks] nvarchar (max) NOT NULL,
  [active] bit NOT NULL,
  [created_at] datetime2 (6) NOT NULL
);
END
GO

-- SparePart  (table: ams_sparepart)
IF OBJECT_ID (N'ams_sparepart', N'U') IS NULL
BEGIN
CREATE TABLE [ams_sparepart] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [code] nvarchar (16) NOT NULL CONSTRAINT [UQ_ams_sparepart_code] UNIQUE,
  [name] nvarchar (160) NOT NULL,
  [asset_type_id] bigint NULL,
  [category_id] bigint NULL,
  [site_id] bigint NULL,
  [qty] decimal(12, 2) NOT NULL,
  [reorder_level] decimal(12, 2) NOT NULL,
  [restock_date] date NULL,
  [warranty_date] date NULL,
  [unit_cost] decimal(14, 2) NULL,
  [vendor_id] bigint NULL,
  [remarks] nvarchar (max) NOT NULL,
  [active] bit NOT NULL,
  [created_at] datetime2 (6) NOT NULL
);
END
GO

-- StockMovement  (table: ams_stockmovement)
IF OBJECT_ID (N'ams_stockmovement', N'U') IS NULL
BEGIN
CREATE TABLE [ams_stockmovement] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [kind] nvarchar (12) NOT NULL,
  [item_id] int NOT NULL,
  [item_code] nvarchar (16) NOT NULL,
  [name] nvarchar (160) NOT NULL,
  [site] nvarchar (120) NOT NULL,
  [type] nvarchar (10) NOT NULL,
  [qty] decimal(12, 2) NOT NULL,
  [by] nvarchar (200) NOT NULL,
  [remarks] nvarchar (max) NOT NULL,
  [asset_id] bigint NULL,
  [asset_id_snapshot] nvarchar (64) NOT NULL,
  [date] date NOT NULL,
  [actor_username] nvarchar (60) NOT NULL,
  [created_at] datetime2 (6) NOT NULL
);
END
GO

-- UserProfile  (table: ams_userprofile)
IF OBJECT_ID (N'ams_userprofile', N'U') IS NULL
BEGIN
CREATE TABLE [ams_userprofile] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [user_id] bigint NOT NULL CONSTRAINT [UQ_ams_userprofile_user_id] UNIQUE,
  [role] nvarchar (30) NOT NULL,
  [display_name] nvarchar (200) NOT NULL,
  [linked_employee_id] bigint NULL,
  [site_id] bigint NULL,
  [email] nvarchar (160) NOT NULL,
  [contact_no] nvarchar (50) NOT NULL,
  [address] nvarchar (500) NOT NULL,
  [gender] nvarchar (10) NOT NULL,
  [dob] date NULL,
  [remarks] nvarchar (max) NOT NULL,
  [allowed_pages] nvarchar (max) NULL,
  [theme] nvarchar (24) NOT NULL,
  [font_size] nvarchar (4) NOT NULL,
  [page_size] int NOT NULL,
  [toast_enabled] bit NOT NULL
);
END
GO

-- RoleAccess  (table: ams_roleaccess)
IF OBJECT_ID (N'ams_roleaccess', N'U') IS NULL
BEGIN
CREATE TABLE [ams_roleaccess] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [page_key] nvarchar (40) NOT NULL,
  [role] nvarchar (30) NOT NULL,
  [level] nvarchar (6) NOT NULL
);
END
GO

-- ActivityLog  (table: ams_activitylog)
IF OBJECT_ID (N'ams_activitylog', N'U') IS NULL
BEGIN
CREATE TABLE [ams_activitylog] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [time] datetime2 (6) NOT NULL,
  [actor_username] nvarchar (60) NOT NULL,
  [actor_role] nvarchar (30) NOT NULL,
  [page] nvarchar (80) NOT NULL,
  [type] nvarchar (10) NOT NULL,
  [message] nvarchar (max) NOT NULL
);
END
GO

-- Company  (table: ams_company)
IF OBJECT_ID (N'ams_company', N'U') IS NULL
BEGIN
CREATE TABLE [ams_company] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [name] nvarchar (200) NOT NULL,
  [slogan] nvarchar (200) NOT NULL,
  [address] nvarchar (max) NOT NULL,
  [logo] nvarchar (100) NULL,
  [banner] nvarchar (100) NULL,
  [hr_admin_contact] nvarchar (60) NOT NULL,
  [head_title] nvarchar (120) NOT NULL,
  [head_contact] nvarchar (60) NOT NULL
);
END
GO

-- ReportPrefs  (table: ams_reportprefs)
IF OBJECT_ID (N'ams_reportprefs', N'U') IS NULL
BEGIN
CREATE TABLE [ams_reportprefs] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [style] nvarchar (10) NOT NULL,
  [show_logo] bit NOT NULL,
  [show_name] bit NOT NULL,
  [show_slogan] bit NOT NULL
);
END
GO

-- PortalPref  (table: ams_portalpref)
IF OBJECT_ID (N'ams_portalpref', N'U') IS NULL
BEGIN
CREATE TABLE [ams_portalpref] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [key] nvarchar (40) NOT NULL CONSTRAINT [UQ_ams_portalpref_key] UNIQUE,
  [value] nvarchar (200) NOT NULL
);
END
GO

-- FormCounter  (table: ams_formcounter)
IF OBJECT_ID (N'ams_formcounter', N'U') IS NULL
BEGIN
CREATE TABLE [ams_formcounter] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [prefix] nvarchar (8) NOT NULL CONSTRAINT [UQ_ams_formcounter_prefix] UNIQUE,
  [last] int NOT NULL
);
END
GO

-- ============================================================================
-- Many-to-Many junction tables
-- ============================================================================

-- Vendor.categories  ->  ams_vendor_categories
IF OBJECT_ID (N'ams_vendor_categories', N'U') IS NULL
BEGIN
CREATE TABLE [ams_vendor_categories] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [vendor_id] bigint NOT NULL,
  [vendorcategory_id] bigint NOT NULL,
  CONSTRAINT [FK_ams_vendor_categories_vendor_id_ams_vendor] FOREIGN KEY ([vendor_id]) REFERENCES [ams_vendor] ([id]) ON DELETE CASCADE,
  CONSTRAINT [FK_ams_vendor_categories_vendorcategory_id_ams_vendorcategory] FOREIGN KEY ([vendorcategory_id]) REFERENCES [ams_vendorcategory] ([id]) ON DELETE CASCADE,
  CONSTRAINT [UQ_ams_vendor_categories_vendor_id_vendorcategory_id] UNIQUE ([vendor_id], [vendorcategory_id])
);
END
GO

-- Asset.accessories  ->  ams_asset_accessories
IF OBJECT_ID (N'ams_asset_accessories', N'U') IS NULL
BEGIN
CREATE TABLE [ams_asset_accessories] (
  [id] bigint IDENTITY (1, 1) NOT NULL PRIMARY KEY,
  [asset_id] bigint NOT NULL,
  [accessory_id] bigint NOT NULL,
  CONSTRAINT [FK_ams_asset_accessories_asset_id_ams_asset] FOREIGN KEY ([asset_id]) REFERENCES [ams_asset] ([id]) ON DELETE CASCADE,
  CONSTRAINT [FK_ams_asset_accessories_accessory_id_ams_accessory] FOREIGN KEY ([accessory_id]) REFERENCES [ams_accessory] ([id]) ON DELETE CASCADE,
  CONSTRAINT [UQ_ams_asset_accessories_asset_id_accessory_id] UNIQUE ([asset_id], [accessory_id])
);
END
GO

-- ============================================================================
-- DEFAULT constraints (Django field defaults)
-- ============================================================================

BEGIN TRY
  ALTER TABLE [ams_site] ADD CONSTRAINT [DF_ams_site_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_department] ADD CONSTRAINT [DF_ams_department_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_designation] ADD CONSTRAINT [DF_ams_designation_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_assetcategory] ADD CONSTRAINT [DF_ams_assetcategory_used_on] DEFAULT N'Both' FOR [used_on];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_assetcategory] ADD CONSTRAINT [DF_ams_assetcategory_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_assettype] ADD CONSTRAINT [DF_ams_assettype_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_assetmake] ADD CONSTRAINT [DF_ams_assetmake_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_vendorcategory] ADD CONSTRAINT [DF_ams_vendorcategory_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_vendor] ADD CONSTRAINT [DF_ams_vendor_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_accessory] ADD CONSTRAINT [DF_ams_accessory_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_simoperator] ADD CONSTRAINT [DF_ams_simoperator_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_simplan] ADD CONSTRAINT [DF_ams_simplan_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_consumablecategory] ADD CONSTRAINT [DF_ams_consumablecategory_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_unitofmeasure] ADD CONSTRAINT [DF_ams_unitofmeasure_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_sparepartcategory] ADD CONSTRAINT [DF_ams_sparepartcategory_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_printterm] ADD CONSTRAINT [DF_ams_printterm_used_on] DEFAULT N'All' FOR [used_on];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_printterm] ADD CONSTRAINT [DF_ams_printterm_sort_order] DEFAULT 10 FOR [sort_order];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_printterm] ADD CONSTRAINT [DF_ams_printterm_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_employee] ADD CONSTRAINT [DF_ams_employee_status] DEFAULT N'Active' FOR [status];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_exitrecord] ADD CONSTRAINT [DF_ams_exitrecord_reactivated] DEFAULT 0 FOR [reactivated];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_simcard] ADD CONSTRAINT [DF_ams_simcard_status] DEFAULT N'In Store' FOR [status];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_simcard] ADD CONSTRAINT [DF_ams_simcard_personal_mobile] DEFAULT 0 FOR [personal_mobile];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [DF_ams_asset_kind] DEFAULT N'asset' FOR [kind];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [DF_ams_asset_is_legacy_id] DEFAULT 0 FOR [is_legacy_id];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [DF_ams_asset_status] DEFAULT N'In Store' FOR [status];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_lifecycleevent] ADD CONSTRAINT [DF_ams_lifecycleevent_event_type] DEFAULT N'Other' FOR [event_type];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_consumable] ADD CONSTRAINT [DF_ams_consumable_qty] DEFAULT 0 FOR [qty];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_consumable] ADD CONSTRAINT [DF_ams_consumable_reorder_level] DEFAULT 0 FOR [reorder_level];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_consumable] ADD CONSTRAINT [DF_ams_consumable_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_sparepart] ADD CONSTRAINT [DF_ams_sparepart_qty] DEFAULT 0 FOR [qty];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_sparepart] ADD CONSTRAINT [DF_ams_sparepart_reorder_level] DEFAULT 0 FOR [reorder_level];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_sparepart] ADD CONSTRAINT [DF_ams_sparepart_active] DEFAULT 1 FOR [active];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_userprofile] ADD CONSTRAINT [DF_ams_userprofile_role] DEFAULT N'Standard User' FOR [role];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_userprofile] ADD CONSTRAINT [DF_ams_userprofile_theme] DEFAULT N'graphite' FOR [theme];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_userprofile] ADD CONSTRAINT [DF_ams_userprofile_font_size] DEFAULT N'md' FOR [font_size];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_userprofile] ADD CONSTRAINT [DF_ams_userprofile_page_size] DEFAULT 20 FOR [page_size];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_userprofile] ADD CONSTRAINT [DF_ams_userprofile_toast_enabled] DEFAULT 1 FOR [toast_enabled];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_roleaccess] ADD CONSTRAINT [DF_ams_roleaccess_level] DEFAULT N'none' FOR [level];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_activitylog] ADD CONSTRAINT [DF_ams_activitylog_type] DEFAULT N'info' FOR [type];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_reportprefs] ADD CONSTRAINT [DF_ams_reportprefs_style] DEFAULT N'classic' FOR [style];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_reportprefs] ADD CONSTRAINT [DF_ams_reportprefs_show_logo] DEFAULT 1 FOR [show_logo];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_reportprefs] ADD CONSTRAINT [DF_ams_reportprefs_show_name] DEFAULT 1 FOR [show_name];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_reportprefs] ADD CONSTRAINT [DF_ams_reportprefs_show_slogan] DEFAULT 1 FOR [show_slogan];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_formcounter] ADD CONSTRAINT [DF_ams_formcounter_last] DEFAULT 0 FOR [last];
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

-- ============================================================================
-- Foreign key constraints
-- ============================================================================

BEGIN TRY
  ALTER TABLE [ams_assettype] ADD CONSTRAINT [FK_ams_assettype_category_id_ams_assetcategory] FOREIGN KEY ([category_id]) REFERENCES [ams_assetcategory] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_assetmake] ADD CONSTRAINT [FK_ams_assetmake_asset_type_id_ams_assettype] FOREIGN KEY ([asset_type_id]) REFERENCES [ams_assettype] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_accessory] ADD CONSTRAINT [FK_ams_accessory_asset_type_id_ams_assettype] FOREIGN KEY ([asset_type_id]) REFERENCES [ams_assettype] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_accessory] ADD CONSTRAINT [FK_ams_accessory_site_id_ams_site] FOREIGN KEY ([site_id]) REFERENCES [ams_site] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_employee] ADD CONSTRAINT [FK_ams_employee_department_id_ams_department] FOREIGN KEY ([department_id]) REFERENCES [ams_department] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_employee] ADD CONSTRAINT [FK_ams_employee_site_id_ams_site] FOREIGN KEY ([site_id]) REFERENCES [ams_site] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_employee] ADD CONSTRAINT [FK_ams_employee_manager_id_ams_employee] FOREIGN KEY ([manager_id]) REFERENCES [ams_employee] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_exitrecord] ADD CONSTRAINT [FK_ams_exitrecord_employee_id_ams_employee] FOREIGN KEY ([employee_id]) REFERENCES [ams_employee] ([id]) ON DELETE NO ACTION;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_simcard] ADD CONSTRAINT [FK_ams_simcard_operator_id_ams_simoperator] FOREIGN KEY ([operator_id]) REFERENCES [ams_simoperator] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_simcard] ADD CONSTRAINT [FK_ams_simcard_plan_id_ams_simplan] FOREIGN KEY ([plan_id]) REFERENCES [ams_simplan] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_simcard] ADD CONSTRAINT [FK_ams_simcard_site_id_ams_site] FOREIGN KEY ([site_id]) REFERENCES [ams_site] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_simcard] ADD CONSTRAINT [FK_ams_simcard_vendor_id_ams_vendor] FOREIGN KEY ([vendor_id]) REFERENCES [ams_vendor] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_simcard] ADD CONSTRAINT [FK_ams_simcard_assigned_to_id_ams_employee] FOREIGN KEY ([assigned_to_id]) REFERENCES [ams_employee] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_simcard] ADD CONSTRAINT [FK_ams_simcard_assigned_to_sub_id_ams_employee] FOREIGN KEY ([assigned_to_sub_id]) REFERENCES [ams_employee] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_simcard] ADD CONSTRAINT [FK_ams_simcard_linked_mobile_id_ams_asset] FOREIGN KEY ([linked_mobile_id]) REFERENCES [ams_asset] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [FK_ams_asset_category_id_ams_assetcategory] FOREIGN KEY ([category_id]) REFERENCES [ams_assetcategory] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [FK_ams_asset_type_id_ams_assettype] FOREIGN KEY ([type_id]) REFERENCES [ams_assettype] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [FK_ams_asset_make_id_ams_assetmake] FOREIGN KEY ([make_id]) REFERENCES [ams_assetmake] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [FK_ams_asset_sim_id_ams_simcard] FOREIGN KEY ([sim_id]) REFERENCES [ams_simcard] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [FK_ams_asset_purchase_site_id_ams_site] FOREIGN KEY ([purchase_site_id]) REFERENCES [ams_site] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [FK_ams_asset_current_site_id_ams_site] FOREIGN KEY ([current_site_id]) REFERENCES [ams_site] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [FK_ams_asset_vendor_id_ams_vendor] FOREIGN KEY ([vendor_id]) REFERENCES [ams_vendor] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [FK_ams_asset_assigned_to_id_ams_employee] FOREIGN KEY ([assigned_to_id]) REFERENCES [ams_employee] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [FK_ams_asset_assigned_to_sub_id_ams_employee] FOREIGN KEY ([assigned_to_sub_id]) REFERENCES [ams_employee] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_asset] ADD CONSTRAINT [FK_ams_asset_replaces_asset_id_ams_asset] FOREIGN KEY ([replaces_asset_id]) REFERENCES [ams_asset] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_lifecycleevent] ADD CONSTRAINT [FK_ams_lifecycleevent_emp_id_ams_employee] FOREIGN KEY ([emp_id]) REFERENCES [ams_employee] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_consumable] ADD CONSTRAINT [FK_ams_consumable_category_id_ams_consumablecategory] FOREIGN KEY ([category_id]) REFERENCES [ams_consumablecategory] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_consumable] ADD CONSTRAINT [FK_ams_consumable_unit_id_ams_unitofmeasure] FOREIGN KEY ([unit_id]) REFERENCES [ams_unitofmeasure] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_consumable] ADD CONSTRAINT [FK_ams_consumable_site_id_ams_site] FOREIGN KEY ([site_id]) REFERENCES [ams_site] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_consumable] ADD CONSTRAINT [FK_ams_consumable_vendor_id_ams_vendor] FOREIGN KEY ([vendor_id]) REFERENCES [ams_vendor] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_sparepart] ADD CONSTRAINT [FK_ams_sparepart_asset_type_id_ams_assettype] FOREIGN KEY ([asset_type_id]) REFERENCES [ams_assettype] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_sparepart] ADD CONSTRAINT [FK_ams_sparepart_category_id_ams_sparepartcategory] FOREIGN KEY ([category_id]) REFERENCES [ams_sparepartcategory] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_sparepart] ADD CONSTRAINT [FK_ams_sparepart_site_id_ams_site] FOREIGN KEY ([site_id]) REFERENCES [ams_site] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_sparepart] ADD CONSTRAINT [FK_ams_sparepart_vendor_id_ams_vendor] FOREIGN KEY ([vendor_id]) REFERENCES [ams_vendor] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_stockmovement] ADD CONSTRAINT [FK_ams_stockmovement_asset_id_ams_asset] FOREIGN KEY ([asset_id]) REFERENCES [ams_asset] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_userprofile] ADD CONSTRAINT [FK_ams_userprofile_user_id_auth_user] UNIQUE FOREIGN KEY ([user_id]) REFERENCES [auth_user] ([id]) ON DELETE CASCADE;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_userprofile] ADD CONSTRAINT [FK_ams_userprofile_linked_employee_id_ams_employee] FOREIGN KEY ([linked_employee_id]) REFERENCES [ams_employee] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_userprofile] ADD CONSTRAINT [FK_ams_userprofile_site_id_ams_site] FOREIGN KEY ([site_id]) REFERENCES [ams_site] ([id]) ON DELETE SET NULL;
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
  ELSE PRINT N'Warning: ' + ERROR_MESSAGE();
END CATCH
GO

-- ============================================================================
-- Indexes and unique constraints from model Meta
-- ============================================================================

BEGIN TRY
  CREATE INDEX [ams_asset_kind_fa4435_idx] ON [ams_asset] ([kind], [status]);
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

BEGIN TRY
  ALTER TABLE [ams_roleaccess] ADD CONSTRAINT [UQ_ams_roleaccess_page_key_role] UNIQUE ([page_key], [role]);
END TRY
BEGIN CATCH
  IF ERROR_NUMBER() <> 2714 PRINT N'Skip: ' + ERROR_MESSAGE();
END CATCH
GO

-- ============================================================================
-- Mark ALL Django migrations (built-in + AMS) as already applied so
-- `python manage.py migrate` is a true no-op against this database.
-- If you prefer Django to create tables itself, DO NOT run this script;
-- create only the empty database (01-create-database.sql) and `migrate`.
-- ============================================================================

IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'admin' AND [name] = N'0001_initial')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'admin', N'0001_initial', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'admin' AND [name] = N'0002_logentry_remove_auto_add')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'admin', N'0002_logentry_remove_auto_add', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'admin' AND [name] = N'0003_logentry_add_action_flag_choices')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'admin', N'0003_logentry_add_action_flag_choices', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'ams' AND [name] = N'0001_initial')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'ams', N'0001_initial', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'ams' AND [name] = N'0002_asset_accessories')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'ams', N'0002_asset_accessories', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0001_initial')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0001_initial', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0002_alter_permission_name_max_length')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0002_alter_permission_name_max_length', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0003_alter_user_email_max_length')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0003_alter_user_email_max_length', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0004_alter_user_username_opts')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0004_alter_user_username_opts', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0005_alter_user_last_login_null')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0005_alter_user_last_login_null', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0006_require_contenttypes_0002')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0006_require_contenttypes_0002', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0007_alter_validators_add_error_messages')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0007_alter_validators_add_error_messages', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0008_alter_user_username_max_length')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0008_alter_user_username_max_length', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0009_alter_user_last_name_max_length')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0009_alter_user_last_name_max_length', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0010_alter_group_name_max_length')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0010_alter_group_name_max_length', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0011_update_proxy_permissions')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0011_update_proxy_permissions', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'auth' AND [name] = N'0012_alter_user_first_name_max_length')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'auth', N'0012_alter_user_first_name_max_length', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'contenttypes' AND [name] = N'0001_initial')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'contenttypes', N'0001_initial', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'contenttypes' AND [name] = N'0002_remove_content_type_name')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'contenttypes', N'0002_remove_content_type_name', SYSUTCDATETIME());
IF NOT EXISTS (SELECT 1 FROM [django_migrations] WHERE [app] = N'sessions' AND [name] = N'0001_initial')
    INSERT INTO [django_migrations] ([app], [name], [applied]) VALUES (N'sessions', N'0001_initial', SYSUTCDATETIME());
GO

PRINT N'AMS-TEST-2 schema creation complete.';
GO