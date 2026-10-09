"""
Connection config — read from the environment, identical code locally and in prod.

The application never knows *which* PostgreSQL it talks to. It reads one URL:

  local:  eval "$(python local_server.py env)"
          -> DATABASE_URL=postgres://postgres:localdev@127.0.0.1:5433/app?sslmode=disable
  prod:   injected by your platform / secret manager
          -> DATABASE_URL=postgres://app_user:***@db.prod.internal:5432/app?sslmode=verify-full

If DATABASE_URL is absent, the standard libpq variables are used instead
(PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE, PGSSLMODE) — many managed
platforms inject those rather than a URL.

APP_ENV=prod adds a guard: the connection must use TLS (sslmode=require or stricter).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import parse_qs, quote_plus, urlsplit

from sqlalchemy.engine import make_url

SECURE_SSLMODES = {"require", "verify-ca", "verify-full"}


@dataclass
class PgConfig:
    # repr=False keeps the password out of logs and tracebacks; use safe_url() to print
    url: str = field(repr=False)
    app_env: str = "local"  # local | prod (anything else is treated like local)
    # Rows per COPY chunk (write operations)
    batch_size: int = 50_000
    # Rows per batch when streaming large result sets
    read_chunksize: int = 50_000
    # Seconds to wait for the server to answer before giving up
    connect_timeout: int = 10

    @classmethod
    def from_env(cls) -> "PgConfig":
        url = os.environ.get("DATABASE_URL") or _url_from_libpq_env()
        if not url:
            raise RuntimeError(
                "No database configured. Locally run:\n"
                '    eval "$(python local_server.py env)"\n'
                "In production set DATABASE_URL (or PGHOST/PGUSER/PGPASSWORD/PGDATABASE)."
            )
        cfg = cls(url=url, app_env=os.environ.get("APP_ENV", "local"))
        cfg.validate()
        return cfg

    @property
    def is_prod(self) -> bool:
        return self.app_env == "prod"

    def validate(self) -> None:
        sslmode = parse_qs(urlsplit(self.url).query).get("sslmode", ["prefer"])[0]
        if self.is_prod and sslmode not in SECURE_SSLMODES:
            raise ValueError(
                f"APP_ENV=prod requires sslmode in {sorted(SECURE_SSLMODES)}, got {sslmode!r}"
            )

    def sqlalchemy_url(self) -> str:
        """Same URL with the psycopg 3 driver selected (postgres:// -> postgresql+psycopg://)."""
        _, rest = self.url.split("://", 1)
        return f"postgresql+psycopg://{rest}"

    def safe_url(self) -> str:
        """URL with the password masked — safe to print or log."""
        return make_url(self.sqlalchemy_url()).render_as_string(hide_password=True)


def _url_from_libpq_env() -> str | None:
    host = os.environ.get("PGHOST")
    if not host:
        return None
    user = quote_plus(os.environ.get("PGUSER", "postgres"))
    password = os.environ.get("PGPASSWORD")
    auth = f"{user}:{quote_plus(password)}" if password else user
    port = os.environ.get("PGPORT", "5432")
    database = os.environ.get("PGDATABASE", "postgres")
    sslmode = os.environ.get("PGSSLMODE", "prefer")
    return f"postgres://{auth}@{host}:{port}/{database}?sslmode={sslmode}"
