"""
Local PostgreSQL server — no Docker, no admin rights.

Runs a *real* PostgreSQL server (same engine as production) from a project-local
data directory, using the binaries that ship inside the `pgserver` pip wheel.

Why not just `pgserver.get_server()`?
--------------------------------------
pgserver's helper is great for embedding Postgres inside one Python process, but:
  * it stops the server when that Python process exits — Atlas runs as a separate
    CLI, so the server must outlive the script that started it;
  * it listens on a unix socket with `trust` auth — production uses TCP + password.

So this script only borrows pgserver's *binaries* and drives `initdb` / `pg_ctl`
itself, listening on 127.0.0.1 with scram-sha-256 password auth — the same
connection shape as production. Any other PostgreSQL install (conda-forge,
Homebrew, Postgres.app) works too: point PG_BIN_DIR at its `bin/` folder.

Commands
--------
  python local_server.py start    # initdb on first run, start server, create databases
  python local_server.py stop     # fast shutdown (data is kept)
  python local_server.py status   # is it running? which version?
  python local_server.py env      # print `export DATABASE_URL=...` lines (eval-able)
  python local_server.py psql     # open an interactive psql shell on the app database
  python local_server.py reset    # stop + delete the data directory + start fresh
  python local_server.py clone    # replace local app DB with a copy of $SOURCE_URL (rehearsal)

Environment variables (all optional)
------------------------------------
  PG_BIN_DIR          Folder with initdb/pg_ctl/psql   (default: pgserver's bundled binaries)
  LOCAL_PG_DATA       Data directory                   (default: ./.pgdata next to this file)
  LOCAL_PG_PORT       TCP port on 127.0.0.1            (default: 5433, avoids clashing with 5432)
  LOCAL_PG_USER       Superuser name                   (default: postgres)
  LOCAL_PG_PASSWORD   Superuser password, local only   (default: localdev)
  LOCAL_PG_DB         Application database             (default: app)
  LOCAL_PG_DEV_DB     Empty scratch database for Atlas (default: atlas_dev)
  LOCAL_PG_LOCALE     Locale for initdb                (default: C — match prod, see README)
  SOURCE_URL          `clone` only: database to copy from (use a read-only user)
  CLONE_WITH_DATA     `clone` only: 1 = copy rows too  (default: schema only)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _default_bin_dir() -> Path:
    if os.environ.get("PG_BIN_DIR"):
        return Path(os.environ["PG_BIN_DIR"])
    try:
        from pgserver._commands import POSTGRES_BIN_PATH
    except ImportError:
        sys.exit(
            "pgserver is not installed: `pip install pgserver`, or set PG_BIN_DIR."
        )
    return Path(POSTGRES_BIN_PATH)


@dataclass
class LocalServer:
    bin_dir: Path = field(default_factory=_default_bin_dir)
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("LOCAL_PG_DATA", HERE / ".pgdata"))
    )
    port: int = int(os.environ.get("LOCAL_PG_PORT", "5433"))
    user: str = os.environ.get("LOCAL_PG_USER", "postgres")
    password: str = os.environ.get("LOCAL_PG_PASSWORD", "localdev")
    app_db: str = os.environ.get("LOCAL_PG_DB", "app")
    dev_db: str = os.environ.get("LOCAL_PG_DEV_DB", "atlas_dev")
    locale: str = os.environ.get("LOCAL_PG_LOCALE", "C")
    host: str = "127.0.0.1"

    # ------------------------------------------------------------------
    # URLs — the only thing that differs between local and production
    # ------------------------------------------------------------------

    def url(self, database: str) -> str:
        # Plain libpq-style URL: understood by Atlas, psql, psycopg and (after
        # adding the +psycopg driver) SQLAlchemy — see config.py.
        return (
            f"postgres://{self.user}:{self.password}@{self.host}:{self.port}"
            f"/{database}?sslmode=disable"
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if not (self.data_dir / "PG_VERSION").exists():
            self._initdb()
        if self.is_running():
            print(f"Already running on {self.host}:{self.port} ({self.data_dir})")
        else:
            self._run(
                "pg_ctl",
                "-D",
                str(self.data_dir),
                "-l",
                str(self.data_dir / "server.log"),
                "-w",
                "start",
            )
        for db in (self.app_db, self.dev_db):
            self._ensure_database(db)
        print(f"PostgreSQL {self.server_version()} ready on {self.host}:{self.port}")
        print(
            'Load the connection env vars with:  eval "$(python local_server.py env)"'
        )

    def stop(self) -> None:
        if not self.is_running():
            print("Not running.")
            return
        self._run("pg_ctl", "-D", str(self.data_dir), "-m", "fast", "-w", "stop")

    def reset(self) -> None:
        self.stop()
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)
            print(f"Deleted {self.data_dir}")
        self.start()

    def is_running(self) -> bool:
        if not (self.data_dir / "PG_VERSION").exists():
            return False
        result = subprocess.run(
            [str(self.bin_dir / "pg_ctl"), "-D", str(self.data_dir), "status"],
            capture_output=True,
        )
        return result.returncode == 0

    def status(self) -> None:
        if self.is_running():
            print(
                f"running   {self.host}:{self.port}   PostgreSQL {self.server_version()}"
            )
            print(f"data dir  {self.data_dir}")
            print(f"binaries  {self.bin_dir}")
        else:
            print("stopped")

    def env(self) -> None:
        print(f"export DATABASE_URL='{self.url(self.app_db)}'")
        print(f"export ATLAS_DEV_URL='{self.url(self.dev_db)}'")
        print("export APP_ENV=local")

    def psql(self) -> None:
        os.execve(
            str(self.bin_dir / "psql"),
            ["psql", self.url(self.app_db)],
            {**os.environ, "PGPASSWORD": self.password},
        )

    def server_version(self) -> str:
        return self._sql("postgres", "SHOW server_version").strip()

    def clone(self) -> None:
        """
        Replace the local app database with a copy of a remote one (rehearsal).

        Reads the source from the SOURCE_URL env var (kept out of argv / shell
        history). By default copies the SCHEMA only, plus the rows of Atlas's
        revision table so `migrate status` shows exactly what the remote has
        applied. Set CLONE_WITH_DATA=1 to copy all rows too — only for
        non-sensitive, reasonably small databases (e.g. staging).
        """
        source = os.environ.get("SOURCE_URL")
        if not source:
            sys.exit(
                "Set SOURCE_URL to the database to copy (e.g. staging or prod, read-only user)."
            )
        with_data = os.environ.get("CLONE_WITH_DATA") == "1"
        if not self.is_running():
            self.start()

        target = self.url(self.app_db)
        self._sql("postgres", f'DROP DATABASE IF EXISTS "{self.app_db}" WITH (FORCE)')
        self._sql("postgres", f'CREATE DATABASE "{self.app_db}"')

        if with_data:
            print(
                "WARNING: copying all rows. Never do this with personal / sensitive data."
            )
            self._dump_restore(source, target)
        else:
            self._dump_restore(source, target, "--schema-only")
            # Atlas history rows, so `migrate status` matches the remote exactly.
            # A remote that was never migrated has no history table yet: skip.
            if self._has_atlas_history(source):
                self._dump_restore(
                    source,
                    target,
                    "--data-only",
                    "--table=atlas_schema_revisions.atlas_schema_revisions",
                )
            else:
                print("Remote has no Atlas history yet (never migrated).")
        print(
            f"Cloned {'schema + data' if with_data else 'schema'} into local '{self.app_db}'."
        )
        print("Next: make migrate-status   then   make migrate-apply")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _initdb(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # initdb reads the superuser password from a file (never from argv)
        with tempfile.NamedTemporaryFile("w", delete=False) as pwfile:
            pwfile.write(self.password)
        try:
            self._run(
                "initdb",
                "-D",
                str(self.data_dir),
                "--username",
                self.user,
                "--pwfile",
                pwfile.name,
                "--auth",
                "scram-sha-256",  # password auth even on localhost, like prod
                "--encoding",
                "UTF8",
                "--locale",
                self.locale,
            )
        finally:
            os.unlink(pwfile.name)

        # Server settings that make local behave like a typical managed prod instance.
        # postgresql.conf is read top-to-bottom; the last occurrence wins.
        with open(self.data_dir / "postgresql.conf", "a") as conf:
            conf.write(
                "\n# --- added by local_server.py ---\n"
                f"listen_addresses = '{self.host}'\n"
                f"port = {self.port}\n"
                "unix_socket_directories = ''\n"  # TCP only, as in prod
                "timezone = 'UTC'\n"
                "log_timezone = 'UTC'\n"
            )

    def _ensure_database(self, name: str) -> None:
        exists = self._sql(
            "postgres", f"SELECT 1 FROM pg_database WHERE datname = '{name}'"
        )
        if not exists.strip():
            self._sql("postgres", f'CREATE DATABASE "{name}"')
            print(f"Created database {name}")

    def _sql(self, database: str, sql: str) -> str:
        result = subprocess.run(
            [str(self.bin_dir / "psql"), self.url(database), "-XtAc", sql],
            env={**os.environ, "PGPASSWORD": self.password},
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def _run(self, exe: str, *args: str) -> None:
        subprocess.run([str(self.bin_dir / exe), *args], check=True)

    def _has_atlas_history(self, source: str) -> bool:
        # pg_tables is readable by every user, unlike the table itself
        result = subprocess.run(
            [
                str(self.bin_dir / "psql"),
                source,
                "-XtAc",
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'atlas_schema_revisions'"
                " AND tablename = 'atlas_schema_revisions'",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() == "1"

    def _dump_restore(self, source: str, target: str, *dump_args: str) -> None:
        # pg_dump | pg_restore, streamed (nothing written to disk). pg_dump must be
        # the same major version as the source server or newer. Filters go to
        # pg_dump only: pg_restore restores everything in the stream it receives.
        no_acl = ["--no-owner", "--no-privileges"]  # local superuser owns everything
        dump = subprocess.Popen(
            [
                str(self.bin_dir / "pg_dump"),
                source,
                "--format=custom",
                *no_acl,
                *dump_args,
            ],
            stdout=subprocess.PIPE,
        )
        restore = subprocess.run(
            [
                str(self.bin_dir / "pg_restore"),
                "--exit-on-error",
                *no_acl,
                "-d",
                target,
            ],
            stdin=dump.stdout,
        )
        dump.stdout.close()
        if dump.wait() or restore.returncode:
            sys.exit(
                "Clone failed (see errors above). Common causes: pg_dump older than the "
                "source server, or an extension that exists remotely but not locally."
            )


def main() -> None:
    commands = {"start", "stop", "status", "env", "psql", "reset", "clone"}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(f"usage: python local_server.py {{{'|'.join(sorted(commands))}}}")
    getattr(LocalServer(), sys.argv[1])()


if __name__ == "__main__":
    main()
