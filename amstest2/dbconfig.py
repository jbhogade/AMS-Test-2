"""
#-------------- Start Code for : DATABASE CONFIG RESOLUTION ----------------

Single source of truth for resolving the database connection of AMS-Test-2.

Used by amstest2/settings.py (to build DATABASES) and by the
`python manage.py dbdoctor` diagnostics command (to report exactly what
Django will use and to test the same connection).

Resolution order for every value:
  1. Real environment variables   (set in the shell / system)
  2. db-config.bat in the project folder (written by the setup scripts)
  3. Built-in defaults

Choices:
  - MS SQL Server is the DEFAULT store (AMS_DB=mssql or unset).
  - AMS_DB=sqlite selects the file db.sqlite3 instead.

SQL Server extras (all optional):
  AMS_DB_NAME                database name          (default AMS-TEST-2)
  AMS_DB_HOST                host or NAMED INSTANCE (default localhost).
                             A named instance may be written as
                             "localhost\\SQLEXPRESS" or ".\\SQLEXPRESS".
  AMS_DB_PORT                TCP port (default 1433). Leave EMPTY for a
                             named instance - the SQL Server Browser
                             service resolves the port automatically.
  AMS_DB_USER                login user (default sa).
                             Windows Authentication is used when
                             AMS_DB_TRUSTED_CONNECTION=yes is set.
  AMS_DB_PASSWORD            login password
  AMS_DB_DRIVER              pin an exact ODBC driver, e.g.
                             "ODBC Driver 17 for SQL Server". Leave unset
                             to let mssql-django pick Driver 18 and fall
                             back to Driver 17 automatically when 18 is
                             not installed.
  AMS_DB_TRUSTED_CONNECTION  "yes" = Windows Authentication (the sa /
                             password settings are ignored)
  AMS_DB_EXTRA_PARAMS        extra ODBC connection-string keywords
                             appended verbatim, e.g. "Encrypt=optional"
#-------------- End of the code for : DATABASE CONFIG RESOLUTION --------------
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_DB_NAME = "AMS-TEST-2"
DEFAULT_DB_HOST = "localhost"
# Effective default port is the SQL Server default instance (1433): an
# unset AMS_DB_PORT deliberately produces "SERVER=host" WITHOUT a port,
# so named instances keep working. Keep only for docs/display.
DEFAULT_DB_PORT = "1433"
DEFAULT_DB_USER = "sa"
DEFAULT_DRIVER = "ODBC Driver 18 for SQL Server"
CONNECT_TIMEOUT = 15  # seconds; fail fast instead of hanging


def _read_db_config_bat():
    """Parse db-config.bat (written by Setup-SQL-Server.bat /
    Setup-AMS-Test-2.bat) so the saved connection also works when Django
    is started directly (python manage.py ...) instead of through
    run-django.bat. Real environment variables always win."""
    cfg = {}
    path = BASE_DIR / "db-config.bat"
    if path.exists():
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                s = line.strip()
                if not s.lower().startswith("set "):
                    continue
                s = s[4:].strip()
                if s.startswith('"') and s.endswith('"'):
                    s = s[1:-1]
                if "=" in s:
                    k, v = s.split("=", 1)
                    cfg[k.strip().upper()] = v.strip()
        except OSError:
            pass
    return cfg


_DB_CFG = _read_db_config_bat()


def _db_env(name, default=None):
    """Environment variable, then db-config.bat, then default."""
    v = os.environ.get(name)
    if v is None or v == "":
        v = _DB_CFG.get(name.upper(), "")
    if v is None or v == "":
        return default
    return v


def _truthy(v):
    return str(v).strip().lower() in ("1", "y", "yes", "true", "on")


def resolve_db():
    """Resolve the active database configuration.

    Returns a dict with:
      engine      "mssql" or "sqlite"
      db_name     database name (mssql) / file path (sqlite)
      host        SQL Server host (may contain \\InstanceName)
      port        TCP port string, or None when unset (named instance)
      user        login user, or "" with Windows Authentication
      password    login password (never log it)
      driver      pinned ODBC driver name, or None (auto: 18 -> 17)
      trusted     True when Windows Authentication is requested
      extra_params  extra ODBC keywords appended to the connection string
    """
    engine_raw = os.environ.get("AMS_DB") or _DB_CFG.get("AMS_DB", "") or "mssql"
    engine = "sqlite" if engine_raw.strip().lower() in ("sqlite", "sqlite3") else "mssql"

    if engine == "sqlite":
        return {
            "engine": "sqlite",
            "db_name": str(BASE_DIR / "db.sqlite3"),
            "host": None, "port": None, "user": None, "password": None,
            "driver": None, "trusted": False, "extra_params": "",
        }

    trusted = _truthy(_db_env("AMS_DB_TRUSTED_CONNECTION", ""))
    host = _db_env("AMS_DB_HOST", DEFAULT_DB_HOST)
    # Port semantics (important for named instances):
    #   unset / empty  -> None -> "SERVER=host" with NO port. The ODBC
    #                     driver then uses the DEFAULT instance (port 1433
    #                     effectively) or the SQL Server Browser resolves a
    #                     "host\\INSTANCE" server name. Appending ",1433"
    #                     to a named instance would be an INVALID target.
    #   explicit value -> "SERVER=host,port"
    port = _db_env("AMS_DB_PORT", None)
    port = str(port).strip() if port else None
    user = "" if trusted else _db_env("AMS_DB_USER", DEFAULT_DB_USER)
    password = "" if trusted else _db_env("AMS_DB_PASSWORD", "")
    driver = _db_env("AMS_DB_DRIVER", "") or None
    extra = "TrustServerCertificate=yes"
    extra_cfg = _db_env("AMS_DB_EXTRA_PARAMS", "")
    if extra_cfg:
        extra += ";" + extra_cfg

    return {
        "engine": "mssql",
        "db_name": _db_env("AMS_DB_NAME", DEFAULT_DB_NAME),
        "host": host,
        "port": port or None,
        "user": user,
        "password": password,
        "driver": driver,
        "trusted": trusted,
        "extra_params": extra,
    }


def pyodbc_connection_string(info=None):
    """Build the ODBC connection string exactly the way mssql-django does,
    so dbdoctor tests the same connection Django will use."""
    if info is None:
        info = resolve_db()
    server = info["host"] if not info["port"] else f"{info['host']},{info['port']}"
    driver = info["driver"] or DEFAULT_DRIVER
    parts = [f"DRIVER={{{driver}}}", f"SERVER={server}", f"DATABASE={info['db_name']}"]
    if info["trusted"] or not info["user"]:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append(f"UID={info['user']}")
        parts.append(f"PWD={info['password']}")
    parts.append(info["extra_params"])
    return ";".join(p for p in parts if p)
