"""
Dremio Iceberg client — PyIceberg against Dremio's Iceberg REST catalog.

This path does NOT go through Dremio's SQL engine. PyIceberg talks to the
Dremio Catalog (Iceberg REST API) for metadata, and reads/writes the Parquet
data files *directly* against object storage (e.g. COS). Because the storage
may be one you don't hold keys for, the catalog vends short-lived, scoped
storage credentials — your personal access token is the only secret you supply.

    DataFrame ⇄ Arrow  ──PyIceberg──▶  Parquet in object storage
                                      + snapshot committed to the REST catalog

Trade-offs vs `client.py` (Arrow Flight read / SQL INSERT write):
- Writes bypass the SQL engine — no per-row literal serialization, columnar.
- Token-only auth; storage credentials are vended by the catalog.
- Requires Dremio's integrated Iceberg REST catalog with credential vending,
  and the target must be a catalog-managed Iceberg table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generator

import pyarrow as pa
import polars as pl
from pyiceberg.catalog import load_catalog

if TYPE_CHECKING:
    import pandas as pd
    from pyiceberg.catalog import Catalog

    DataFrame = pl.DataFrame | pd.DataFrame


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


def _namespace_of(identifier: str) -> str | None:
    """Return the namespace portion of a dotted "ns.sub.table" identifier."""
    head, _, _ = identifier.rpartition(".")
    return head or None


@dataclass
class DremioCatalogConfig:
    uri: str                          # REST catalog endpoint, e.g. ".../api/iceberg"
    token: str                        # personal access token (bearer)
    warehouse: str                    # Dremio catalog / project name
    oauth2_server_uri: str | None = None   # OAuth2 token endpoint, if token exchange is used
    name: str = "dremio"              # local name for the catalog instance
    vended_credentials: bool = True   # request catalog-vended storage credentials
    extra: dict[str, str] | None = None    # any additional PyIceberg catalog properties


class DremioIcebergClient:
    def __init__(self, cfg: DremioCatalogConfig) -> None:
        self.cfg = cfg
        props: dict[str, str] = {
            "type": "rest",
            "uri": cfg.uri,
            "token": cfg.token,
            "warehouse": cfg.warehouse,
        }
        if cfg.oauth2_server_uri:
            props["oauth2-server-uri"] = cfg.oauth2_server_uri
        if cfg.vended_credentials:
            # Tells the REST catalog to vend short-lived storage credentials
            # instead of the client supplying its own object-storage keys.
            props["header.X-Iceberg-Access-Delegation"] = "vended-credentials"
        if cfg.extra:
            props.update(cfg.extra)
        self.catalog: "Catalog" = load_catalog(cfg.name, **props)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(
        self,
        identifier: str,
        *,
        columns: list[str] | None = None,
        row_filter: str | None = None,
        limit: int | None = None,
    ) -> pl.DataFrame:
        """
        Read an Iceberg table into a Polars DataFrame.

        Prune columns and push a predicate to read less off storage — the scan
        is planned by PyIceberg and only the matching data files are fetched.

        Args:
            identifier: Dotted table name, e.g. "staging.orders".
            columns: Subset of columns to read (None = all).
            row_filter: Iceberg filter expression, e.g. "dt >= '2025-01-01'".
            limit: Max rows to return.

        Use `stream()` instead when the table may exceed available RAM.
        """
        table = self.catalog.load_table(identifier)
        scan = table.scan(
            selected_fields=tuple(columns) if columns else ("*",),
            row_filter=row_filter or "true",
            limit=limit,
        )
        return pl.from_arrow(scan.to_arrow())

    def stream(
        self,
        identifier: str,
        *,
        columns: list[str] | None = None,
        row_filter: str | None = None,
    ) -> Generator[pl.DataFrame, None, None]:
        """
        Yield the table one Polars DataFrame per Arrow RecordBatch.

        Keeps RAM flat regardless of total table size.
        """
        table = self.catalog.load_table(identifier)
        scan = table.scan(
            selected_fields=tuple(columns) if columns else ("*",),
            row_filter=row_filter or "true",
        )
        for batch in scan.to_arrow_batch_reader():
            yield pl.from_arrow(batch)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(
        self,
        df: "DataFrame | pa.Table",
        identifier: str,
        *,
        mode: str = "append",
    ) -> None:
        """
        Write a DataFrame to an existing Iceberg table.

        Args:
            df: Polars or pandas DataFrame (or Arrow Table).
            identifier: Dotted table name, e.g. "staging.orders".
            mode: "append" to add rows, "overwrite" to replace all rows.
        """
        arrow = _to_arrow(df)
        if arrow.num_rows == 0 and mode == "append":
            return
        table = self.catalog.load_table(identifier)
        if mode == "append":
            table.append(arrow)
        elif mode == "overwrite":
            table.overwrite(arrow)
        else:
            raise ValueError(f"mode must be 'append' or 'overwrite', got {mode!r}")

    def upsert(
        self,
        df: "DataFrame | pa.Table",
        identifier: str,
        join_cols: list[str],
    ) -> None:
        """
        Merge a DataFrame into an Iceberg table (update matched, insert new).

        Args:
            df: Polars or pandas DataFrame (or Arrow Table).
            identifier: Dotted table name, e.g. "staging.orders".
            join_cols: Key columns used to match existing rows.
        """
        arrow = _to_arrow(df)
        table = self.catalog.load_table(identifier)
        table.upsert(arrow, join_cols=join_cols)

    def create_table(
        self,
        df: "DataFrame | pa.Table",
        identifier: str,
        *,
        replace: bool = False,
        push_data: bool = True,
    ) -> None:
        """
        Create an Iceberg table from a DataFrame's schema, then push its data.

        Creates the parent namespace if needed. The Parquet files land directly
        in the catalog's object storage via vended credentials.

        Args:
            df: Polars or pandas DataFrame (source of schema and data).
            identifier: Dotted table name, e.g. "staging.orders".
            replace: If True, drop an existing table of the same name first.
            push_data: If False, create the empty table and skip the data load.
        """
        arrow = _to_arrow(df)

        if replace and self.catalog.table_exists(identifier):
            self.catalog.drop_table(identifier)

        namespace = _namespace_of(identifier)
        if namespace:
            self.catalog.create_namespace_if_not_exists(namespace)

        table = self.catalog.create_table_if_not_exists(
            identifier, schema=arrow.schema
        )
        if push_data and arrow.num_rows:
            table.append(arrow)
