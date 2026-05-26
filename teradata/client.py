"""
Teradata client — pandas & Polars read/write via SQLAlchemy.

Uses the teradatasqlalchemy dialect so that both pandas (to_sql / read_sql)
and Polars (read_database / write_database) share a single connection layer.

Connection guide
----------------
logmech values:
  TD2      Native Teradata password auth (default)
  LDAP     LDAP / Active Directory
  TDNEGO   Auto-negotiate (tries Kerberos, then TD2)
  KRB5     Kerberos

tmode values:
  TERA     Teradata session mode (default, BTEQ-compatible)
  ANSI     ANSI-compliant; treats division by zero as NULL instead of error
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generator, Literal
from urllib.parse import quote_plus

import pandas as pd
import polars as pl
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@dataclass
class TeradataConfig:
    host: str
    username: str
    password: str
    # Default database/schema — used as the schema argument in write operations
    database: str = ""
    logmech: str = "TD2"   # TD2 | LDAP | TDNEGO | KRB5
    tmode: str = "TERA"    # TERA | ANSI
    # Rows per INSERT batch (write operations)
    batch_size: int = 10_000
    # Rows per chunk when streaming large result sets
    read_chunksize: int = 50_000

    def sqlalchemy_url(self) -> str:
        """Build the SQLAlchemy connection URL for teradatasqlalchemy."""
        user = quote_plus(self.username)
        pwd = quote_plus(self.password)
        base = f"teradatasql://{user}:{pwd}@{self.host}"
        if self.database:
            base += f"/{self.database}"
        return f"{base}?logmech={self.logmech}&tmode={self.tmode}"


class TeradataClient:
    """
    Thin wrapper around a SQLAlchemy / teradatasqlalchemy engine.

    Supports pandas and Polars for both reads and writes.  For very large
    datasets use stream_pandas / stream_polars to keep RAM consumption flat.

    Usage — context manager (recommended):
        with TeradataClient(cfg) as client:
            df = client.read_polars("SELECT * FROM my_db.my_table")

    Usage — manual lifecycle:
        client = TeradataClient(cfg)
        df = client.read_pandas("SELECT ...")
        client.close()
    """

    def __init__(self, cfg: TeradataConfig) -> None:
        self.cfg = cfg
        self._engine: Engine = create_engine(cfg.sqlalchemy_url())

    def close(self) -> None:
        self._engine.dispose()

    def __enter__(self) -> "TeradataClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_pandas(self, query: str) -> pd.DataFrame:
        """
        Execute a SQL query and return the full result as a pandas DataFrame.

        For datasets that may exceed available RAM, use stream_pandas() instead.

        Example:
            df = client.read_pandas(
                "SELECT order_id, customer, revenue FROM sales_db.orders"
                " WHERE order_date >= '2024-01-01'"
            )
        """
        with self._engine.connect() as conn:
            return pd.read_sql(text(query), conn)

    def read_polars(self, query: str) -> pl.DataFrame:
        """
        Execute a SQL query and return the full result as a Polars DataFrame.

        Uses Polars' native read_database with the SQLAlchemy engine —
        no pandas round-trip required.

        Example:
            df = client.read_polars("SELECT * FROM sales_db.orders SAMPLE 10000")
        """
        with self._engine.connect() as conn:
            return pl.read_database(query, connection=conn)

    def stream_pandas(
        self,
        query: str,
        chunksize: int | None = None,
    ) -> Generator[pd.DataFrame, None, None]:
        """
        Stream query results in fixed-size chunks as pandas DataFrames.

        Each chunk is yielded and immediately eligible for garbage collection,
        so total RAM stays proportional to chunksize, not to the full result set.

        Example — stream a large table to Parquet partitions:
            for i, chunk in enumerate(
                client.stream_pandas("SELECT * FROM sales_db.events", chunksize=100_000)
            ):
                chunk.to_parquet(f"/data/events_part_{i:04d}.parquet", index=False)
        """
        rows = chunksize or self.cfg.read_chunksize
        with self._engine.connect() as conn:
            yield from pd.read_sql(text(query), conn, chunksize=rows)

    def stream_polars(
        self,
        query: str,
        chunksize: int | None = None,
    ) -> Generator[pl.DataFrame, None, None]:
        """
        Stream query results in fixed-size chunks as Polars DataFrames.

        Converts each pandas chunk to Polars via the Arrow bridge
        (zero-copy for most numeric and string columns).

        Example:
            total = 0
            for chunk in client.stream_polars("SELECT * FROM sales_db.events"):
                total += chunk.filter(pl.col("status") == "completed").height
        """
        for chunk in self.stream_pandas(query, chunksize):
            yield pl.from_pandas(chunk)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_pandas(
        self,
        df: pd.DataFrame,
        table: str,
        schema: str | None = None,
        if_exists: Literal["fail", "replace", "append"] = "append",
        chunksize: int | None = None,
    ) -> None:
        """
        Write a pandas DataFrame to a Teradata table.

        Uses SQLAlchemy's to_sql — handles DDL creation ("replace" drops and
        recreates the table; "append" inserts into an existing one).

        Args:
            df:        DataFrame to write.
            table:     Target table name (without schema).
            schema:    Target database/schema. Defaults to cfg.database.
            if_exists: "fail" | "replace" | "append"
                         fail    — raise if table exists
                         replace — drop, recreate, and insert
                         append  — insert into existing table
            chunksize: Rows per INSERT batch. Defaults to cfg.batch_size.

        Example:
            client.write_pandas(df_orders, table="orders", schema="staging_db")
        """
        df.to_sql(
            name=table,
            con=self._engine,
            schema=schema or self.cfg.database or None,
            if_exists=if_exists,
            index=False,
            chunksize=chunksize or self.cfg.batch_size,
        )

    def write_polars(
        self,
        df: pl.DataFrame,
        table: str,
        schema: str | None = None,
        if_exists: Literal["fail", "replace", "append"] = "append",
        chunksize: int | None = None,
    ) -> None:
        """
        Write a Polars DataFrame to a Teradata table.

        Converts to pandas internally before writing — Teradata has no native
        Arrow / ADBC driver, so the pandas bridge is the most reliable path.

        Args:
            df:        Polars DataFrame to write.
            table:     Target table name (without schema).
            schema:    Target database/schema. Defaults to cfg.database.
            if_exists: "fail" | "replace" | "append"
            chunksize: Rows per INSERT batch. Defaults to cfg.batch_size.

        Example:
            client.write_polars(df_summary, table="monthly_summary", schema="reports_db")
        """
        self.write_pandas(
            df.to_pandas(),
            table=table,
            schema=schema,
            if_exists=if_exists,
            chunksize=chunksize,
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def execute(self, sql: str) -> None:
        """
        Execute a DDL or DML statement (no result set returned).

        Useful for CREATE / DROP / TRUNCATE / COLLECT STATISTICS.

        Example:
            client.execute("DROP TABLE staging_db.orders")
            client.execute("COLLECT STATISTICS ON prod_db.orders COLUMN order_date")
        """
        with self._engine.begin() as conn:
            conn.execute(text(sql))
