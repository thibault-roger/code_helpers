"""
Connection check — "can I reach this database, and what does it look like?"

Run it BEFORE anything else whenever you point the code at a new database
(your local server, staging, production). It uses the exact same config as the
application (config.py), so if this works, the app and Atlas will connect too.

    eval "$(python local_server.py env)"    # local
    python check_connection.py

    export DATABASE_URL='postgres://me:***@db.company.com:5432/app?sslmode=require'
    python check_connection.py               # remote

It only READS: it never changes anything on the server.

What it reports
---------------
  server      PostgreSQL version, host, database, user, TLS on/off
  settings    timezone, collation (they change query results — compare local vs prod!)
  rights      can this user create tables? (needed by Atlas, not by the app)
  extensions  installed extensions (each one must exist in BOTH environments)
  atlas       which migration version is applied

If the connection fails, it translates the driver error into likely causes.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from config import PgConfig

# Substring of the driver error -> explanation for humans
HINTS = {
    "Connection refused": (
        "Nothing is listening at that host/port.\n"
        "  - local: is the server started?  ->  make db-start\n"
        "  - remote: wrong host or port in DATABASE_URL?"
    ),
    "timeout expired": (
        "The host did not answer at all (packets are dropped).\n"
        "  - remote databases are often only reachable from the company network: VPN on?\n"
        "  - a firewall / security group may need to allow your IP"
    ),
    "resolve host": "The host name in DATABASE_URL does not exist (typo? VPN/DNS?).",
    "could not translate host name": "The host name in DATABASE_URL does not exist (typo? VPN/DNS?).",
    "password authentication failed": (
        "Wrong user or password.\n"
        "  - special characters in the password (@ : / # ? %) must be URL-encoded in the URL:\n"
        "    python -c \"from urllib.parse import quote; print(quote('p@ss/word', safe=''))\""
    ),
    "does not exist": "The database (the part after the last '/') or the role does not exist.",
    "no pg_hba.conf entry": (
        "The server refuses connections from your machine / user / without TLS.\n"
        "  - try sslmode=require; otherwise ask the DBA to allow your IP or user"
    ),
    "SSL": (
        "TLS problem.\n"
        "  - local server: use sslmode=disable (it has no certificate)\n"
        "  - remote with verify-full: add sslrootcert=/path/to/ca.pem to the URL"
    ),
}


def explain(error: str) -> str:
    for needle, hint in HINTS.items():
        if needle.lower() in error.lower():
            return hint
    return "Unrecognised error — read the message above, it usually says what is wrong."


def main() -> int:
    try:
        cfg = PgConfig.from_env()
    except (RuntimeError, ValueError) as exc:
        print(f"Configuration problem:\n{exc}")
        return 1

    print(f"APP_ENV      {cfg.app_env}")
    print(f"URL          {cfg.safe_url()}")

    engine = create_engine(
        cfg.sqlalchemy_url(), connect_args={"connect_timeout": cfg.connect_timeout}
    )
    try:
        with engine.connect() as conn:

            def one(query: str):
                return conn.execute(text(query)).scalar()

            ssl = conn.connection.driver_connection.pgconn.ssl_in_use
            print("\n-- server " + "-" * 50)
            print(f"version      {one('SHOW server_version')}")
            print(
                f"host:port    {one('SELECT inet_server_addr()')}:{one('SELECT inet_server_port()')}"
            )
            print(f"database     {one('SELECT current_database()')}")
            print(f"user         {one('SELECT current_user')}")
            print(f"TLS          {'on' if ssl else 'off'}")

            print("\n-- settings that change query results " + "-" * 21)
            print(f"timezone     {one('SHOW timezone')}")
            print(
                "collation    "
                + one(
                    "SELECT datcollate FROM pg_database WHERE datname = current_database()"
                )
            )

            print("\n-- rights " + "-" * 50)
            superuser = one(
                "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
            )
            create = one("SELECT has_schema_privilege('public', 'CREATE')")
            print(f"superuser    {superuser}")
            print(
                f"can create tables in public: {create}  (only the migration user needs this)"
            )

            print("\n-- extensions " + "-" * 46)
            exts = conn.execute(
                text("SELECT extname || ' ' || extversion FROM pg_extension ORDER BY 1")
            ).scalars()
            print("installed    " + ", ".join(exts))

            print("\n-- atlas " + "-" * 51)
            schema = "atlas_schema_revisions"
            exists = one(
                f"SELECT count(*) FROM pg_namespace WHERE nspname = '{schema}'"
            )
            readable = exists and one(
                f"SELECT has_schema_privilege('{schema}', 'USAGE')"
            )
            if not exists:
                print("applied      none (Atlas has never run migrate apply here)")
            elif not readable:
                print(
                    f"applied      ? (this user may not read schema {schema}, see remote_roles.sql)"
                )
            else:
                version, count = conn.execute(
                    text(
                        f"SELECT max(version), count(*) FROM {schema}.atlas_schema_revisions"
                    )
                ).one()
                print(f"applied      {count} migration(s), latest version {version}")
    except OperationalError as exc:
        message = str(exc.orig).strip()
        print(f"\nCONNECTION FAILED:\n  {message}\n\nLikely cause: {explain(message)}")
        return 1
    finally:
        engine.dispose()

    print("\nOK — connected. Python code and Atlas will connect the same way.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
