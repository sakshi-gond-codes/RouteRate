"""
Database configuration helper used by setup.bat / setup.sh.

  1. Asks for the MySQL login (or reuses an existing .env)
  2. Tests the connection and checks the server version
  3. Creates the database with utf8mb4 if it does not exist
  4. Writes .env with a random Django secret key

Run again with --reconfigure to change the login.
Non-interactive (CI):  DB_USER=... DB_PASSWORD=... python scripts/configure.py --non-interactive
"""
import argparse
import getpass
import os
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"

try:
    import pymysql
except ImportError:
    print("[ERROR] PyMySQL is not installed. Run: pip install -r requirements.txt")
    sys.exit(1)


def read_env(path):
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return values


def ask(label, default=""):
    shown = f" [{default}]" if default else ""
    answer = input(f"  {label}{shown}: ").strip()
    return answer or default


def connect(cfg, database=None):
    return pymysql.connect(host=cfg["DB_HOST"], port=int(cfg["DB_PORT"]), user=cfg["DB_USER"],
                           password=cfg["DB_PASSWORD"], database=database, connect_timeout=8, charset="utf8mb4")


def explain(exc):
    code = exc.args[0] if exc.args else None
    if code == 1045:
        return "Access denied: the MySQL username or password is wrong."
    if code in (2003, 2002):
        return ("Could not reach MySQL. Make sure the MySQL server is installed and running "
                "(Windows: Services > MySQL80 > Start) and that host/port are correct.")
    if code == 1044:
        return "This MySQL user is not allowed to create databases. Use root or ask for CREATE privilege."
    return f"MySQL error: {exc}"


def check_version(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT VERSION()")
        version = cur.fetchone()[0]
    numbers = [int(n) for n in re.findall(r"\d+", version)[:2]]
    is_maria = "mariadb" in version.lower()
    ok = (numbers >= [10, 5]) if is_maria else (numbers >= [8, 0])
    label = "MariaDB" if is_maria else "MySQL"
    print(f"  Connected to {label} {version.split('-')[0]}")
    if not ok:
        print(f"  [WARNING] Django 5 needs MySQL 8.0+ or MariaDB 10.5+. Your {label} may be too old.")


def write_env(cfg):
    lines = [
        "# Created by scripts/configure.py - safe to edit",
        f"DJANGO_SECRET_KEY={cfg['DJANGO_SECRET_KEY']}",
        f"DJANGO_DEBUG={cfg.get('DJANGO_DEBUG', 'True')}",
        f"DJANGO_ALLOWED_HOSTS={cfg.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')}",
        f"TIME_ZONE={cfg.get('TIME_ZONE', 'UTC')}",
        "",
        f"DB_NAME={cfg['DB_NAME']}",
        f"DB_USER={cfg['DB_USER']}",
        f"DB_PASSWORD={cfg['DB_PASSWORD']}",
        f"DB_HOST={cfg['DB_HOST']}",
        f"DB_PORT={cfg['DB_PORT']}",
        "",
    ]
    ENV_FILE.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reconfigure", action="store_true", help="Ask for the MySQL login again")
    parser.add_argument("--non-interactive", action="store_true", help="Use DB_* environment variables")
    args = parser.parse_args()

    cfg = read_env(ENV_FILE)
    defaults = {"DB_HOST": "127.0.0.1", "DB_PORT": "3306", "DB_USER": "root", "DB_PASSWORD": "", "DB_NAME": "routerate"}

    if args.non_interactive:
        for key, default in defaults.items():
            cfg[key] = os.getenv(key, cfg.get(key, default))
        attempts = 1
    elif cfg.get("DB_USER") and not args.reconfigure:
        print(f"  Using existing .env (user '{cfg['DB_USER']}', database '{cfg.get('DB_NAME', 'routerate')}').")
        print("  To change it, run:  .venv\\Scripts\\python scripts\\configure.py --reconfigure")
        attempts = 1
    else:
        attempts = 3
    for key, default in defaults.items():
        cfg.setdefault(key, default)
    cfg.setdefault("DJANGO_SECRET_KEY", "")
    if not cfg["DJANGO_SECRET_KEY"] or "change-me" in cfg["DJANGO_SECRET_KEY"]:
        cfg["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(50)

    interactive = attempts == 3
    try:
        if not interactive and not args.non_interactive:
            connect(cfg).close()          # does the saved .env still work?
    except pymysql.MySQLError as exc:
        print(f"  [ERROR] {explain(exc)}")
        if sys.stdin.isatty():
            print("  The saved login did not work. Let's enter it again.\n")
            interactive, attempts = True, 3
    for attempt in range(attempts):
        if interactive:
            print("  Enter your MySQL details (press Enter to accept the value in brackets).")
            cfg["DB_HOST"] = ask("MySQL host", cfg["DB_HOST"])
            cfg["DB_PORT"] = ask("MySQL port", cfg["DB_PORT"])
            cfg["DB_USER"] = ask("MySQL username", cfg["DB_USER"])
            cfg["DB_PASSWORD"] = getpass.getpass("  MySQL password (hidden while typing): ")
            cfg["DB_NAME"] = ask("Database name to create/use", cfg["DB_NAME"])
        try:
            conn = connect(cfg)
        except pymysql.MySQLError as exc:
            print(f"  [ERROR] {explain(exc)}")
            if interactive and attempt < attempts - 1:
                print("  Please try again.\n")
                continue
            return 1
        break

    if not re.fullmatch(r"[A-Za-z0-9_]+", cfg["DB_NAME"]):
        print("  [ERROR] Database name may only contain letters, numbers and underscores.")
        return 1
    try:
        check_version(conn)
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{cfg['DB_NAME']}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"  Database '{cfg['DB_NAME']}' is ready.")
    except pymysql.MySQLError as exc:
        print(f"  [ERROR] {explain(exc)}")
        return 1
    finally:
        conn.close()

    write_env(cfg)
    print("  Saved settings to .env")
    return 0


if __name__ == "__main__":
    sys.exit(main())
