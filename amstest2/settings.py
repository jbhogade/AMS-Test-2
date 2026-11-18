"""
Django settings for the AMS-Test-2 project.

AMS-Test-2 - Asset Management System, Django-only rebuild of AMS-Test.

#-------------- Start Code for : DATABASE (SQL SERVER DEFAULT) ----------------
MS SQL Server is the DEFAULT data store (same engine as the original
AMS-Test). All business data lives in the AMS-TEST-2 database.

Connection settings are resolved in this order:
  1. Environment variables  (AMS_DB_NAME / AMS_DB_HOST / AMS_DB_PORT /
     AMS_DB_USER / AMS_DB_PASSWORD / AMS_DB_DRIVER)
  2. db-config.bat in the project folder (written by Setup-SQL-Server.bat,
     and loaded automatically by run-django.bat)
  3. Defaults: AMS-TEST-2 @ localhost,1433, user sa

First run:  python manage.py migrate   (Django creates all tables)
            python manage.py seed_admins
Requires "ODBC Driver 18 for SQL Server" + pip install mssql-django pyodbc
(Setup-SQL-Server.bat does all of this for you).

Fallback: set AMS_DB=sqlite (or AMS_DB=SQLITE) to run on the file-based
SQLite database db.sqlite3 instead - handy for quick demos without a
SQL Server instance. Copy-Data-SQLite-to-SQLServer.bat moves SQLite data
into SQL Server later.

Connection trouble? Run the built-in diagnostics:
    python manage.py dbdoctor        (or double-click Test-SQL-Connection.bat)
It tests the connection step by step (ODBC driver, network, login, database)
and prints concrete fixes for every common error.

Database already holds tables (e.g. you restored the old AMS-Test backup
over AMS-TEST-2)? Plain `python manage.py migrate` now detects that, runs
the schema sync (dbrepair) automatically and never fails with error 2714
"There is already an object named 'ams_company'". The manual command still
exists:
    python manage.py dbrepair        (or double-click Repair-Database.bat)
It adds missing tables/columns and marks every migration applied, without
touching existing rows. A missing AMS-TEST-2 database is created by
migrate automatically as well (ODBC error 4060).
#-------------- End of the code : DATABASE (SQL SERVER DEFAULT) ----------------
"""

import os
from pathlib import Path

from . import dbconfig

BASE_DIR = dbconfig.BASE_DIR

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "ams-test-2-django-rebuild-signing-key-change-me-in-production"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("AMS_DEBUG", "1") == "1"

ALLOWED_HOSTS = ["*"]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ams",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "amstest2.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "ams.context.context_injector",
            ],
        },
    },
]

WSGI_APPLICATION = "amstest2.wsgi.application"

#-------------- Start Code for : DATABASE (SQL SERVER DEFAULT) ----------------
# SQL Server by default; AMS_DB=sqlite falls back to the file db.sqlite3.
# The full resolution logic (env vars -> db-config.bat -> defaults, named
# instances, Windows Authentication, ODBC driver auto-fallback) lives in
# amstest2/dbconfig.py and is shared with the dbdoctor diagnostics command.
#-------------- End of the code : DATABASE (SQL SERVER DEFAULT) ----------------

_DB = dbconfig.resolve_db()

if _DB["engine"] == "mssql":
    _OPTIONS = {
        "extra_params": _DB["extra_params"],
        # Login timeout in seconds: fail fast with a clear error instead of
        # hanging for minutes when the server is unreachable.
        "connection_timeout": dbconfig.CONNECT_TIMEOUT,
    }
    if _DB["driver"]:
        # Pinned driver (AMS_DB_DRIVER was set) - used verbatim.
        _OPTIONS["driver"] = _DB["driver"]
    # No explicit driver otherwise: mssql-django then defaults to
    # "ODBC Driver 18 for SQL Server" and automatically retries with
    # "ODBC Driver 17 for SQL Server" if 18 is not installed.
    #
    # PORT may be None (named instance like localhost\SQLEXPRESS):
    # mssql-django omits the port then and the SQL Server Browser service
    # resolves the instance. An empty USER activates Windows Authentication.
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": _DB["db_name"],
            "USER": _DB["user"],
            "PASSWORD": _DB["password"],
            "HOST": _DB["host"],
            "PORT": _DB["port"] or "",
            "OPTIONS": _OPTIONS,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": _DB["db_name"],
        }
    }

# Password validation.
# The first hasher is Django's default (used for all new/changed passwords).
# The second one verifies hashes imported from the original AMS-Test
# database (ams_users.password_hash / password_salt) so every imported
# user can log in with the OLD password; Django silently upgrades the
# stored hash to the default hasher on the first successful login.

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "ams.hashers.AmsLegacyHasher",
]

AUTH_PASSWORD_VALIDATORS = []

# Internationalization - IST matches the original portal's users

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Fonts) and user uploads (logo / banner)

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Leading slash is required so FileField.url is absolute ("/media/company/x.png");
# a relative "media/..." URL breaks on nested pages like /system-admin/.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Redirect after login / logout (the portal's login.html gate)

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"

# Session lifetime mirrors the original JWT expiry (480 minutes = 8 hours)

SESSION_COOKIE_AGE = 480 * 60
SESSION_SAVE_EVERY_REQUEST = True

# Raise the body limit so large CSV imports / logo uploads go through

DATA_UPLOAD_MAX_MEMORY_SIZE = 32_000_000
FILE_UPLOAD_MAX_MEMORY_SIZE = 32_000_000

# X-Frame options: the System Admin hub loads panels via htmx (no iframes),
# but print windows open standalone pages - allow same-origin framing only.

X_FRAME_OPTIONS = "SAMEORIGIN"
