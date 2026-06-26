"""
Dremio client — Arrow Flight for reads, SQL for writes.

Arrow Flight is Dremio's native columnar protocol and is excellent for
high-volume *reads*. Dremio's Flight server does NOT implement do_put, so
writes go through SQL `INSERT INTO ... VALUES`, batched per statement.

- Parallel endpoint reading across Dremio data fragments
- Chunk streaming for constant-memory reads
- Streaming sink to Parquet via PyArrow writer
- SQL INSERT writes (batched); create a table from a DataFrame schema
- For bulk ingestion prefer COPY INTO from a registered source, or the
  Iceberg REST path in `iceberg_client.py` (writes straight to object storage)
"""

from __future__ import annotations

import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Generator

import pyarrow as pa
import pyarrow.flight as flight
import pyarrow.parquet as pq
import polars as pl

if TYPE_CHECKING:
    import pandas as pd

    # Accepted DataFrame inputs for write/create_table.
    DataFrame = pl.DataFrame | pd.DataFrame


# ----------------------------------------------------------------------
# DataFrame / type helpers
# ----------------------------------------------------------------------


def _to_arrow(df: "DataFrame | pa.Table") -> pa.Table:
    """
    Normalize a Polars or pandas DataFrame (or Arrow Table) to a pa.Table.

    Duck-typed so pandas stays an optional dependency: Polars exposes
    ``.to_arrow()``, pandas does not.
    """
    if isinstance(df, pa.Table):
        return df
    to_arrow = getattr(df, "to_arrow", None)
    if callable(to_arrow):
        return to_arrow()  # Polars
    return pa.Table.from_pandas(df, preserve_index=False)  # pandas


def _arrow_to_dremio_type(dtype: pa.DataType) -> str:
    """Map an Arrow data type to the closest Dremio SQL column type."""
    if pa.types.is_boolean(dtype):
        return "BOOLEAN"
    if pa.types.is_integer(dtype):
        # Dremio has no 8/16-bit ints; INT covers up to int32, BIGINT for int64.
        return "BIGINT" if dtype.bit_width >= 64 else "INT"
    if pa.types.is_float32(dtype):
        return "FLOAT"
    if pa.types.is_floating(dtype):
        return "DOUBLE"
    if pa.types.is_decimal(dtype):
        return f"DECIMAL({dtype.precision}, {dtype.scale})"
    if pa.types.is_date(dtype):
        return "DATE"
    if pa.types.is_time(dtype):
        return "TIME"
    if pa.types.is_timestamp(dtype):
        return "TIMESTAMP"
    if pa.types.is_binary(dtype) or pa.types.is_large_binary(dtype):
        return "VARBINARY"
    if pa.types.is_string(dtype) or pa.types.is_large_string(dtype):
        return "VARCHAR"
    raise TypeError(f"No Dremio SQL type mapping for Arrow type: {dtype}")


def _quote_path(destination: str) -> str:
    """
    Turn a "space/folder/table" path into a quoted SQL identifier.

    e.g. "my_space/staging/orders" -> '"my_space"."staging"."orders"'
    """
    return ".".join(f'"{part}"' for part in destination.split("/"))


def _sql_literal(value: object) -> str:
    """
    Render a Python scalar as a Dremio SQL literal for use in INSERT VALUES.

    Note the datetime check precedes date: datetime is a subclass of date.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, datetime.datetime):
        return f"TIMESTAMP '{value.isoformat(sep=' ')}'"
    if isinstance(value, datetime.date):
        return f"DATE '{value.isoformat()}'"
    if isinstance(value, datetime.time):
        return f"TIME '{value.isoformat()}'"
    if isinstance(value, (bytes, bytearray)):
        return "x'" + value.hex() + "'"
    # Strings (and any fallback): single-quote escaped per SQL.
    return "'" + str(value).replace("'", "''") + "'"


@dataclass
class DremioConfig:
    host: str
    port: int = 32010
    username: str = ""
    password: str = ""
    tls: bool = True
    # Write: rows packed into a single INSERT ... VALUES statement
    insert_batch_size: int = 1_000
    # Read: parallel threads for multi-endpoint queries
    max_workers: int = 8


class DremioClient:
    def __init__(self, cfg: DremioConfig) -> None:
        self.cfg = cfg
        scheme = "grpc+tls" if cfg.tls else "grpc"
        self._client = flight.FlightClient(f"{scheme}://{cfg.host}:{cfg.port}")
        token = self._client.authenticate_basic_token(cfg.username, cfg.password)
        self._opts = flight.FlightCallOptions(headers=[token])

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(self, query: str) -> pl.DataFrame:
        """
        Parallel read across all Dremio endpoints (data fragments).

        Dremio may split a query result across multiple endpoints. This method
        fetches all of them concurrently and concatenates the result.

        Use `stream()` instead when the dataset may exceed available RAM.
        """
        info = self._client.get_flight_info(
            flight.FlightDescriptor.for_command(query.encode()),
            self._opts,
        )

        def _fetch(endpoint: flight.FlightEndpoint) -> pa.Table:
            reader = self._client.do_get(endpoint.ticket, self._opts)
            return reader.read_all()

        with ThreadPoolExecutor(max_workers=self.cfg.max_workers) as pool:
            futures = {pool.submit(_fetch, ep): ep for ep in info.endpoints}
            tables = [f.result() for f in as_completed(futures)]

        return pl.from_arrow(pa.concat_tables(tables))

    def stream(self, query: str) -> Generator[pl.DataFrame, None, None]:
        """
        Generator that yields one Polars DataFrame per Arrow RecordBatch.

        Keeps RAM flat regardless of total dataset size — each batch is
        typically ~65k rows depending on Dremio's output batch config.

        Example:
            for chunk in client.stream('SELECT * FROM "space"."table"'):
                process(chunk)
        """
        info = self._client.get_flight_info(
            flight.FlightDescriptor.for_command(query.encode()),
            self._opts,
        )
        for endpoint in info.endpoints:
            reader = self._client.do_get(endpoint.ticket, self._opts)
            for batch, _ in reader:
                yield pl.from_arrow(batch)

    def stream_to_parquet(
        self,
        query: str,
        output_path: str,
        compression: str = "snappy",
    ) -> int:
        """
        Stream query results directly to a Parquet file.

        Never loads the full dataset into RAM — writes each RecordBatch as
        it arrives. Returns the total number of rows written.

        Args:
            query: SQL query to execute.
            output_path: Destination Parquet file path.
            compression: Parquet compression codec (snappy, zstd, lz4, none).

        Returns:
            Total row count written.
        """
        writer: pq.ParquetWriter | None = None
        total_rows = 0
        try:
            for chunk in self.stream(query):
                arrow_batch = chunk.to_arrow()
                if writer is None:
                    writer = pq.ParquetWriter(
                        output_path, arrow_batch.schema, compression=compression
                    )
                writer.write_table(arrow_batch)
                total_rows += len(arrow_batch)
        finally:
            if writer:
                writer.close()
        return total_rows

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def execute(self, sql: str) -> None:
        """
        Run a SQL statement that returns no rows (DDL/DML).

        Useful for CREATE / DROP / TRUNCATE / INSERT. Flight executes the
        statement when the result stream is drained, so we read and discard it.
        """
        info = self._client.get_flight_info(
            flight.FlightDescriptor.for_command(sql.encode()),
            self._opts,
        )
        for endpoint in info.endpoints:
            reader = self._client.do_get(endpoint.ticket, self._opts)
            reader.read_all()  # drain to force execution; result is empty

    def write(
        self,
        df: "DataFrame | pa.Table",
        destination: str,
        *,
        insert_batch_size: int | None = None,
    ) -> None:
        """
        Write a Polars or pandas DataFrame to an existing Dremio table via SQL.

        Dremio's Arrow Flight server does not support do_put ingestion, so this
        issues `INSERT INTO ... VALUES` statements, packing `insert_batch_size`
        rows per statement to bound statement size. The destination table must
        already exist — use `create_table()` to create it first.

        This is the simplest, most portable write path but not the fastest: each
        row is serialized to a SQL literal. For bulk loads prefer `COPY INTO`
        from a registered source, or `iceberg_client.py` (writes Parquet
        straight to object storage via the Iceberg REST catalog).

        Args:
            df: Polars or pandas DataFrame to write.
            destination: Dremio path, e.g. "my_space/output_table".
            insert_batch_size: Rows per INSERT statement (defaults to config).
        """
        table = _to_arrow(df)
        if table.num_rows == 0:
            return

        sql_path = _quote_path(destination)
        column_names = table.column_names
        columns = ", ".join(f'"{name}"' for name in column_names)
        rows_per_stmt = insert_batch_size or self.cfg.insert_batch_size

        rows = table.to_pylist()
        for offset in range(0, len(rows), rows_per_stmt):
            values = ",\n    ".join(
                "(" + ", ".join(_sql_literal(row[name]) for name in column_names) + ")"
                for row in rows[offset : offset + rows_per_stmt]
            )
            self.execute(f"INSERT INTO {sql_path} ({columns})\nVALUES\n    {values}")

    def create_table(
        self,
        df: "DataFrame | pa.Table",
        destination: str,
        *,
        replace: bool = False,
        push_data: bool = True,
    ) -> None:
        """
        Create a Dremio table from a DataFrame's schema, then push its data.

        Infers a `CREATE TABLE` DDL from the DataFrame's Arrow schema, executes
        it, and (by default) streams the rows in via Arrow Flight `do_put`.

        The destination must live in a writable source (data-lake source such
        as S3/ADLS/HDFS/NAS, backed by Iceberg) — Dremio cannot create tables
        in read-only sources or in the semantic layer ("Spaces").

        Args:
            df: Polars or pandas DataFrame (source of both schema and data).
            destination: Dremio path, e.g. "my_source/staging/orders".
            replace: If True, DROP the table first when it already exists.
            push_data: If False, create an empty table and skip the data load.

        Example:
            client.create_table(df, "my_source/staging/orders", replace=True)
        """
        table = _to_arrow(df)
        sql_path = _quote_path(destination)

        if replace:
            self.execute(f"DROP TABLE IF EXISTS {sql_path}")

        columns = ",\n    ".join(
            f'"{field.name}" {_arrow_to_dremio_type(field.type)}'
            for field in table.schema
        )
        self.execute(f"CREATE TABLE {sql_path} (\n    {columns}\n)")

        if push_data and table.num_rows:
            self.write(table, destination)
