"""
Dremio client — Arrow Flight (recommended for bulk reads/writes).

Optimized for high-volume transfers (>1M rows):
- Parallel endpoint reading across Dremio data fragments
- Chunk streaming for constant-memory reads
- Batched writes to avoid memory spikes
- Streaming sink to Parquet via PyArrow writer
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Generator

import pyarrow as pa
import pyarrow.flight as flight
import pyarrow.parquet as pq
import polars as pl


@dataclass
class DremioConfig:
    host: str
    port: int = 32010
    username: str = ""
    password: str = ""
    tls: bool = True
    # Write: rows per Arrow batch sent over the wire
    batch_size: int = 100_000
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

    def write(self, df: pl.DataFrame, destination: str) -> None:
        """
        Write a Polars DataFrame to Dremio via Arrow Flight.

        Sends data in batches of `cfg.batch_size` rows to avoid large
        in-flight memory allocations.

        Args:
            df: DataFrame to write.
            destination: Dremio path, e.g. "my_space/output_table".
        """
        schema = df.to_arrow().schema
        path_parts = [p.encode() for p in destination.split("/")]
        descriptor = flight.FlightDescriptor.for_path(*path_parts)

        writer, _ = self._client.do_put(descriptor, schema, self._opts)
        try:
            for offset in range(0, len(df), self.cfg.batch_size):
                batch = df.slice(offset, self.cfg.batch_size).to_arrow()
                writer.write_table(batch)
        finally:
            writer.close()
