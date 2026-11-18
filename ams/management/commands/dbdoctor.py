"""
#-------------- Start Code for : DB DOCTOR (ams/management/commands/dbdoctor.py)

Step-by-step diagnostics for the AMS-Test-2 database connection.

Run:   python manage.py dbdoctor                 (report + targeted fixes)
       python manage.py dbdoctor --create-database
                                       (also creates AMS-TEST-2 if missing)

Windows users can simply double-click  Test-SQL-Connection.bat  instead.

The doctor walks through every layer that can break the connection and
stops at the first failing layer, printing concrete fixes:

  1. Resolved configuration   (what settings.py actually uses)
  2. ODBC driver              (pyodbc present? which drivers are installed?)
  3. Network                  (TCP reachability of host:port, or the SQL
                               Server Browser probe for named instances)
  4. SQL login                (raw ODBC connect with the exact connection
                               string mssql-django builds)
  5. Database                 (AMS-TEST-2 exists? how many ams_ tables?)
  6. Django                   (django.db connection check)

Every failure is translated from the ODBC SQLSTATE / error text into plain
advice (install driver, enable TCP/IP, mixed mode auth, SQL Browser, ...).
#-------------- End of the code for : DB DOCTOR (ams/management/commands/dbdoctor.py) --
"""

import re
import socket

from django.core.management.base import BaseCommand, CommandError

from amstest2 import dbconfig


def ok(label, detail=""):
    print(f"  [OK]   {label}" + (f" - {detail}" if detail else ""))


def fail(label, detail=""):
    print(f"  [FAIL] {label}" + (f" - {detail}" if detail else ""))


def info(label, detail=""):
    print(f"  [..]   {label}" + (f" - {detail}" if detail else ""))


def mask(password):
    return "(Windows Authentication)" if not password else "*" * 8


class Command(BaseCommand):
    help = "Diagnose the AMS-Test-2 database connection and print concrete fixes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-database", action="store_true",
            help="Create the AMS-TEST-2 database if it does not exist "
                 "(connects to master with the same login).",
        )

    # ------------------------------------------------------------------ util
    @staticmethod
    def _sqlstate(exc):
        """Extract the ODBC SQLSTATE from a pyodbc error, e.g. '28000'."""
        for arg in exc.args or []:
            if isinstance(arg, str) and re.match(r"^[0-9A-Z]{5}$", arg):
                return arg
        m = re.search(r"\(([0-9A-Z]{5})[,)]", repr(exc.args or ""))
        return m.group(1) if m else ""

    @staticmethod
    def _is_driver_error(text):
        t = text.lower()
        return (
            "can't open lib" in t
            or "cannot open lib" in t
            or "data source name not found" in t
            or "driver not found" in t
            or "specified driver could not be loaded" in t
            or "odbc driver" in t and "not found" in t
        )

    # ------------------------------------------------------------ step 1
    def _show_config(self, db):
        print("\nStep 1 of 5 - Resolved configuration (amstest2/dbconfig.py)")
        if db["engine"] == "sqlite":
            info("Engine", "SQLite (fallback mode, AMS_DB=sqlite)")
            info("File", db["db_name"])
            return
        auth = "Windows Authentication" if db["trusted"] else f"SQL login '{db['user']}'"
        if db["port"]:
            target = f"{db['host']},{db['port']}"
        elif "\\" in (db["host"] or ""):
            target = f"{db['host']} (named instance, SQL Browser resolves the port)"
        else:
            target = f"{db['host']} (default instance, standard port)"
        info("Engine", f"MS SQL Server (mssql-django), database '{db['db_name']}'")
        info("Server", target)
        info("Login", auth)
        info("ODBC driver", db["driver"] or "auto (Driver 18, falls back to 17 if 18 is missing)")
        if db["extra_params"]:
            info("Extra params", db["extra_params"])

    # ------------------------------------------------------------ step 2
    def _check_driver(self, db):
        print("\nStep 2 of 5 - ODBC driver check")
        try:
            import pyodbc
        except ImportError as e:
            fail("pyodbc is not installed", str(e))
            print("         Fix: pip install pyodbc mssql-django")
            return None
        ok("pyodbc installed", pyodbc.version)
        drivers = pyodbc.drivers()
        ms = [d for d in drivers if "SQL Server" in d]
        if not ms:
            fail("No Microsoft ODBC driver for SQL Server is installed")
            print("         Fix 1: install 'Microsoft ODBC Driver 18 for SQL Server'")
            print("                https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server")
            print("         Fix 2: (offline machines) use the SQL Server Native Client 11")
            print("                and set AMS_DB_DRIVER=SQL Server Native Client 11.0")
            return None
        ok("MS SQL Server ODBC drivers found", ", ".join(ms))
        if db["driver"]:
            if db["driver"] in drivers:
                ok("Pinned driver is installed", db["driver"])
            else:
                fail("Pinned driver is NOT installed", db["driver"])
                print("         Fix: install it, or set AMS_DB_DRIVER to one of:")
                for d in ms:
                    print(f"                set AMS_DB_DRIVER={d}")
        return pyodbc

    # ------------------------------------------------------------ step 3
    def _check_network(self, db):
        print("\nStep 3 of 5 - Network reachability")
        host = db["host"]
        inst = None
        if "\\" in host:
            host, inst = host.split("\\", 1)
        host = host.strip() or "localhost"

        if not inst and not db["port"]:
            # No port and no named instance = the DEFAULT instance. The
            # ODBC driver connects to the standard port in this case, so
            # probe 1433 silently (not an error condition).
            db["port"] = "1433"

        if inst:
            # Named instance: ask the SQL Server Browser service (UDP 1434)
            info("Named instance detected", f"host '{host}', instance '{inst}'")
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(3)
                s.sendto(b"\x02", (host, 1434))  # CLNT_UCAST_EX: list all instances
                data, _ = s.recvfrom(65536)
                s.close()
            except OSError as e:
                fail("SQL Server Browser did not answer on UDP 1434", str(e))
                print("         The Browser service resolves named instances to ports.")
                print("         Fix 1: start it - SQL Server Configuration Manager >")
                print("                SQL Server Browser > Start (and set 'Automatic')")
                print("         Fix 2: or run the instance on a STATIC TCP port (see")
                print("                README 'Troubleshooting') and set AMS_DB_PORT.")
                return False
            text = data.decode("utf-8", "replace")
            found = {}
            for chunk in text.split(";;"):
                pairs = chunk.split(";")
                entry = dict(zip(pairs[0::2], pairs[1::2]))
                name = entry.get("InstanceName")
                if name:
                    found[name.upper()] = entry
            if not found:
                fail("Browser answered but reported no instances")
                return False
            ok("SQL Server Browser answered")
            for name, entry in found.items():
                tcp = entry.get("tcp") or "(TCP disabled)"
                print(f"           - {entry.get('ServerName', host)}\\{name}: TCP port {tcp}")
            if inst.upper() in found:
                entry = found[inst.upper()]
                if not entry.get("tcp"):
                    fail(f"Instance '{inst}' has TCP/IP disabled",
                         "Enable it in SQL Server Configuration Manager > Protocols.")
                    return False
                ok(f"Instance '{inst}' found, TCP port {entry.get('tcp')}")
                print("         Tip: for a faster connection set AMS_DB_PORT=%s" % entry.get("tcp"))
            else:
                fail(f"Instance '{inst}' is not listed on this server", ", ".join(found) or "-")
                return False
            return True

        # Plain host[:port] - TCP connect test
        port = int(db["port"] or "1433")
        try:
            ip = socket.gethostbyname(host)
        except OSError as e:
            fail(f"Cannot resolve host name '{host}'", str(e))
            print("         Fix: check AMS_DB_HOST spelling / DNS.")
            return False
        info(f"Host {host} -> {ip}, testing TCP port {port}")
        try:
            with socket.create_connection((ip, port), timeout=5):
                ok(f"TCP port {port} is reachable")
            return True
        except OSError as e:
            fail(f"TCP port {port} is NOT reachable", str(e))
            print("         Checklist, in order:")
            print("           1. Is the SQL Server service running? (services.msc >")
            print("              'SQL Server (MSSQLSERVER)' or 'SQL Server (SQLEXPRESS)')")
            print("           2. Is TCP/IP enabled? SQL Server Configuration Manager >")
            print("              SQL Server Network Configuration > Protocols > TCP/IP = Enabled")
            print("              (SQL Server Express ships with TCP/IP DISABLED by default!)")
            print("           3. Which port? Configuration Manager > TCP/IP Properties >")
            print("              IP Addresses tab > TCP Port (default 1433; Express often")
            print("              uses a dynamic port unless you set one there)")
            print("           4. Firewall: allow inbound TCP %d for sqlservr.exe" % port)
            print("           5. If you use a NAMED instance, write AMS_DB_HOST=%s\\%s"
                  % (host, "SQLEXPRESS"))
            return False

    # ------------------------------------------------------------ step 4
    def _check_login(self, db):
        print("\nStep 4 of 5 - SQL login (raw ODBC connect)")
        cs = dbconfig.pyodbc_connection_string(db)
        try:
            import pyodbc
        except ImportError:
            fail("skipped - pyodbc missing")
            return None
        info("Connection string", cs.replace(f"PWD={db['password']}", "PWD=********")
             if db["password"] else cs)
        try:
            conn = pyodbc.connect(cs, timeout=dbconfig.CONNECT_TIMEOUT)
        except Exception as e:
            fail("Could not connect", str(e))
            self._explain_login_error(e, db)
            return None
        ok("Connected to SQL Server")
        cur = conn.cursor()
        cur.execute("SELECT @@SERVERNAME, @@VERSION")
        server, ver = cur.fetchone()
        ok("Server", f"{server} ({(ver or '')[:60]}...)")
        conn.close()
        return True

    def _explain_login_error(self, exc, db):
        state = self._sqlstate(exc)
        text = str(exc)
        print(f"         SQLSTATE: {state or '(none)'}")
        t = text.lower()

        if self._is_driver_error(text):
            print("         Fix: the ODBC driver name in use was not found. Install")
            print("              'Microsoft ODBC Driver 18 for SQL Server', or set")
            print("              AMS_DB_DRIVER=ODBC Driver 17 for SQL Server if only 17")
            print("              is installed (see Step 2 list).")
        elif "18456" in t or "login failed for user" in t:
            if db["trusted"]:
                print("         Windows Authentication was rejected. The current Windows")
                print("         account has no SQL Server login. Fix: in SSMS connect as")
                print("         admin > Security > Logins > New Login > Windows account,")
                print("         grant dbcreator + sysadmin - or use SQL auth (sa) instead.")
            else:
                print("         Login failed (error 18456). Checklist:")
                print("           1. Wrong password? Test it in SSMS first.")
                print("           2. 'sa' is disabled by default on many installs: SSMS >")
                print("              Security > Logins > sa > Status > Login = Enabled.")
                print("           3. Server uses WINDOWS-ONLY authentication (the default on")
                print("              SQL Server Express). Enable Mixed Mode: SSMS > server >")
                print("              Properties > Security > 'SQL Server and Windows")
                print("              Authentication mode', restart the SQL Server service.")
                print("           4. Or skip 'sa' entirely: use Windows Authentication by")
                print("              leaving the login blank in Setup-SQL-Server.bat.")
        elif "4060" in t or "cannot open database" in t or "does not exist" in t \
                or "unable to open database" in t:
            print("         The DATABASE does not exist on this server (error 4060).")
            print("         Fix: python manage.py dbdoctor --create-database")
            print("              or run sqlserver\\01-create-database.sql in SSMS/sqlcmd.")
        elif "ssl" in t or "certificate" in t or "tls" in t or "encrypt" in t:
            print("         TLS/certificate problem. TrustServerCertificate=yes is already")
            print("         set; if your server/OS is very old, relax encryption:")
            print("         set AMS_DB_EXTRA_PARAMS=Encrypt=optional  and retry.")
        elif "sql server browser" in t or "instance" in t and "locate" in t:
            print("         Instance lookup failed: start the 'SQL Server Browser' service")
            print("         or switch to host + static port (AMS_DB_HOST / AMS_DB_PORT).")
        elif "timeout" in t or "08001" in state or "hyt00" in state:
            print("         Connection timed out. The port answered the network probe but")
            print("         the handshake stalled - check firewall/antivirus or try the")
            print("         port number from the SQL Server error log directly.")
        else:
            print("         Fix: run SSMS/sqlcmd with the SAME host+login to compare,")
            print("         then re-check Steps 2 and 3 above.")

    # ------------------------------------------------------------ step 5
    def _check_database_and_django(self, db, create_db=False):
        print("\nStep 5 of 5 - Database + Django connection")
        import pyodbc
        cs_master = dbconfig.pyodbc_connection_string(db).replace(
            f"DATABASE={db['db_name']}", "DATABASE=master")
        try:
            conn = pyodbc.connect(cs_master, timeout=dbconfig.CONNECT_TIMEOUT)
        except Exception as e:
            fail("Could not connect to 'master'", str(e))
            return False
        cur = conn.cursor()
        cur.execute("SELECT DB_ID(N'%s')" % db["db_name"].replace("'", ""))
        db_id = cur.fetchone()[0]
        if db_id:
            ok(f"Database '{db['db_name']}' exists")
            cur.execute(
                "SELECT COUNT(*) FROM sys.tables t "
                "JOIN sys.schemas s ON s.schema_id = t.schema_id "
                "WHERE t.name LIKE 'ams[_]%' OR t.name LIKE 'django[_]%'"
            )
            n = cur.fetchone()[0]
            ok("Tables visible in the database", f"{n} ams_/django_ tables"
               + (" (empty - run migrate)" if n == 0 else ""))
            try:
                cur.execute(
                    "SELECT COUNT(*) FROM [django_migrations] WHERE [app] = N'ams'"
                )
                mig = cur.fetchone()[0]
                if n and mig == 0:
                    print("  [WARN] ams_ tables exist but no ams migration records")
                    print("         (typical after restoring a database backup).")
                    print("         migrate will fail with error 2714 'There is")
                    print("         already an object named ...'.")
                    print("         Fix: python manage.py dbrepair")
                    print("              (or double-click Repair-Database.bat)")
            except Exception:
                pass  # django_migrations does not exist yet - fine
        else:
            fail(f"Database '{db['db_name']}' does NOT exist")
            if create_db:
                print("         Creating it now (--create-database) ...")
                cur.execute("IF DB_ID(N'%s') IS NULL EXEC('CREATE DATABASE [%s]')"
                            % (db["db_name"].replace("'", ""), db["db_name"].replace("'", "")))
                conn.commit()
                cur.execute("SELECT DB_ID(N'%s')" % db["db_name"].replace("'", ""))
                if cur.fetchone()[0]:
                    ok("Database created", db["db_name"])
                else:
                    fail("Could not create the database - check permissions")
                    conn.close()
                    return False
            else:
                print("         Fix: run  python manage.py dbdoctor --create-database")
                print("              or double-click Setup-SQL-Server.bat / use")
                print("              sqlserver\\01-create-database.sql in SSMS.")
                conn.close()
                return False
        conn.close()

        try:
            from django.db import connection
            with connection.cursor() as c:
                c.execute("SELECT 1")
            ok("Django database connection works")
            return True
        except Exception as e:
            fail("Django could not open its connection", str(e))
            print("         (The raw ODBC test above succeeded, so this is usually a")
            print("          settings issue - send the full output for analysis.)")
            return False

    # ------------------------------------------------------------ sqlite
    def _check_sqlite(self, db):
        print("\nStep 2 of 2 - SQLite file check")
        from pathlib import Path
        p = Path(db["db_name"])
        if p.exists():
            ok("SQLite file exists", f"{p} ({p.stat().st_size} bytes)")
        else:
            print(f"  [WARN] {p} does not exist yet - it is created by 'migrate'.")
        try:
            import sqlite3
            conn = sqlite3.connect(p)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            ok("SQLite file readable", f"{cur.fetchone()[0]} tables")
            conn.close()
        except Exception as e:
            fail("SQLite file not readable", str(e))
            return False
        return True

    # ------------------------------------------------------------ entry
    def handle(self, *args, **options):
        db = dbconfig.resolve_db()
        print("=" * 62)
        print("  AMS-Test-2 database doctor")
        print("=" * 62)
        self._show_config(db)

        good = False
        if db["engine"] == "sqlite":
            good = self._check_sqlite(db)
        else:
            pyodbc_mod = self._check_driver(db)
            if pyodbc_mod is None:
                good = False
            else:
                net = self._check_network(db)
                if not net:
                    good = False
                else:
                    login = self._check_login(db)
                    if login is None:
                        good = False
                    else:
                        good = self._check_database_and_django(
                            db, create_db=options["create_database"])

        print()
        if good:
            print("RESULT: ALL STEPS PASSED - the connection is ready.")
            print("        Start the portal with run-django.bat, then run")
            print("        'python manage.py migrate' if tables are still missing.")
        else:
            print("RESULT: PROBLEM FOUND - apply the printed fixes and re-run.")
            print("=" * 62)
            # Non-zero exit code so setup .bat scripts can detect the failure
            # (CommandError prints without a traceback and exits with 1).
            raise CommandError("Database connection check failed - see the fixes above.")
        print("=" * 62)
