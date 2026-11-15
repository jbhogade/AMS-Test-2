"""
Django settings for the AMS-Test-2 project.

AMS-Test-2 - Asset Management System, Django-only rebuild of AMS-Test.

#-------------- Start Code for : DATABASE (SWITCHABLE) ----------------
The portal runs on SQLite by default (zero config, file-based). To run
against SQL Server (same engine as the original AMS-Test) set the
environment variable AMS_DB=mssql before starting Django:

    Windows (cmd):     set AMS_DB=mssql
    Windows (PS):      $env:AMS_DB="mssql"

Then install the SQL Server requirements:
    pip install mssql-django pyodbc
...and make sure "ODBC Driver 18 for SQL Server" is installed. The
database name used is AMS-TEST-2. On first run Django creates and
seeds everything (python manage.py migrate + seed_admins).
#-------------- End of the code : DATABASE (SWITCHABLE) ----------------
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

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

#-------------- Start Code for : DATABASE (SWITCHABLE) ----------------
# SQLite by default. Set AMS_DB=mssql to switch to SQL Server.
#-------------- End of the code : DATABASE (SWITCHABLE) ----------------

if os.environ.get("AMS_DB", "sqlite").lower() in ("mssql", "sqlserver", "sql-server"):
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": os.environ.get("AMS_DB_NAME", "AMS-TEST-2"),
            "USER": os.environ.get("AMS_DB_USER", "sa"),
            "PASSWORD": os.environ.get("AMS_DB_PASSWORD", ""),
            "HOST": os.environ.get("AMS_DB_HOST", "localhost"),
            "PORT": os.environ.get("AMS_DB_PORT", "1433"),
            "OPTIONS": {
                "driver": os.environ.get("AMS_DB_DRIVER", "ODBC Driver 18 for SQL Server"),
                "extra_params": "TrustServerCertificate=yes",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Password validation (Django PBKDF2-SHA256 matches the original portal's hasher)

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
