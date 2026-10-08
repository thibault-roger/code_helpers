"""
PostgreSQL client — pandas & Polars read/write via SQLAlchemy 2 + psycopg 3.

The exact same code runs against the local server (local_server.py) and the
production database: only DATABASE_URL changes (see config.py).

Design rules
------------
* The client never creates or alters tables. Schema is owned by Atlas
  (atlas/schema.pg.hcl -> atlas/migrations/), so local and prod can't drift
  because some script auto-created a table with guessed types.
* Writes use PostgreSQL COPY (the fastest bulk-load path) in a single
  transaction: either every chunk lands or none does.
* Reads can stream with a server-side cursor so RAM stays flat on large tables.
"""

from __future__ import annotations

import io
from collections.abc import Generator, Mapping
from typing import Any

import pandas as pd
import polars as pl
from psycopg import sql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from config import PgConfig


class PostgresClient:
    """
    Thin wrapper around a SQLAlchemy engine using the psycopg 3 driver.

    Usage — context manager (recommended):
        with PostgresClient(PgConfig.from_env()) as client:
            df = client.read_polars("SELECT * FROM sales_orders WHERE status = :s", {"s": "open"})
    """

    def __init__(self, cfg: PgConfig) -> None:
        self.cfg = cfg
        # pool_pre_ping: transparently replace connections dropped by a proxy /
        # PgBouncer / failover — common in prod, harmless locally.
        # connect_timeout: fail after N seconds instead of hanging when a remote
        # host is unreachable (VPN off, firewall) — see check_connection.py.
        self._engine: Engine = create_engine(
            cfg.sqlalchemy_url(),
            pool_pre_ping=True,
            connect_args={"connect_timeout": cfg.connect_timeout},
        )

    def close(self) -> None:
        self._engine.dispose()

    def __enter__(self) -> "PostgresClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_polars(
        self, query: str, params: Mapping[str, Any] | None = None
    ) -> pl.DataFrame:
        """
        Execute a SQL query and return the full result as a Polars DataFrame.

        Always pass values through `params` (`:name` placeholders), never f-strings.

        Example:
            df = client.read_polars(
                "SELECT * FROM sales_orders WHERE order_date >= :since", {"since": "2024-01-01"}
            )
        """
        with self._engine.connect() as conn:
            return pl.read_database(
                text(query),
                connection=conn,
                execute_options={"parameters": params or {}},
            )

    def read_pandas(
        self, query: str, params: Mapping[str, Any] | None = None
    ) -> pd.DataFrame:
        """Execute a SQL query and return the full result as a pandas DataFrame."""
        with self._engine.connect() as conn:
            return pd.read_sql(text(query), conn, params=dict(params or {}))

    def stream_polars(
        self,
        query: str,
        params: Mapping[str, Any] | None = None,
        batch_size: int | None = None,
    ) -> Generator[pl.DataFrame, None, None]:
        """
        Stream query results in fixed-size Polars batches.

        `stream_results=True` opens a server-side cursor, so PostgreSQL sends rows
        on demand instead of the driver buffering the whole result in memory.

        Example:
            for batch in client.stream_polars("SELECT * FROM sales_orders"):
                batch.write_parquet(...)
        """
        rows = batch_size or self.cfg.read_chunksize
        with self._engine.connect().execution_options(stream_results=True) as conn:
            yield from pl.read_database(
                text(query),
                connection=conn,
                iter_batches=True,
                batch_size=rows,
                execute_options={"parameters": params or {}},
            )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_polars(
        self,
        df: pl.DataFrame,
        table: str,
        schema: str = "public",
        batch_size: int | None = None,
    ) -> int:
        """
        Bulk-insert a Polars DataFrame into an EXISTING table using COPY.

        Columns are matched by name; table columns missing from `df` get their
        DEFAULT. Raises if the table does not exist — create it with an Atlas
        migration, not from Python.

        Returns the number of rows written.
        """
        if not inspect(self._engine).has_table(table, schema=schema):
            raise LookupError(
                f"{schema}.{table} does not exist. Add it to atlas/schema.pg.hcl and run "
                "`make migrate-diff name=...` then `make migrate-apply`."
            )

        copy_stmt = sql.SQL(
            "COPY {}.{} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)"
        ).format(
            sql.Identifier(schema),
            sql.Identifier(table),
            sql.SQL(", ").join(map(sql.Identifier, df.columns)),
        )
        rows = batch_size or self.cfg.batch_size
        with self._engine.begin() as conn:  # one transaction for all chunks
            cursor = conn.connection.driver_connection.cursor()
            for chunk in df.iter_slices(rows):
                # CSV in memory; nulls -> empty unquoted field -> NULL for COPY csv
                buf = io.BytesIO()
                chunk.write_csv(buf)
                with cursor.copy(copy_stmt) as copy:
                    copy.write(buf.getvalue())
        return df.height

    def write_pandas(
        self,
        df: pd.DataFrame,
        table: str,
        schema: str = "public",
        batch_size: int | None = None,
    ) -> int:
        """Bulk-insert a pandas DataFrame (converted to Polars via Arrow, then COPY)."""
        return self.write_polars(pl.from_pandas(df), table, schema, batch_size)

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def execute(self, statement: str, params: Mapping[str, Any] | None = None) -> None:
        """Run a DML statement (UPDATE / DELETE / …) in its own transaction.

        Keep DDL out of here — schema changes belong in Atlas migrations.
        """
        with self._engine.begin() as conn:
            conn.execute(text(statement), dict(params or {}))
