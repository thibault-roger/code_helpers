"""
HCL table schema reader.

Parses a .hcl schema file and returns:
  - table metadata as a plain dict
  - column catalog as a Polars DataFrame (one row per column)

Also provides a helper to generate a CREATE TABLE SQL statement from the parsed schema.

Expected .hcl format
--------------------
Two layouts are supported:

**Wrapped** (table block — the common case when hcl2 returns a "table" key):

    table {
      name        = "my_table"
      description = "..."
      database    = "analytics"
      schema      = "public"

      column {
        name        = "order_id"
        type        = "INTEGER"
        nullable    = false
        primary_key = true
        description = "Unique order identifier"
      }

      column {
        name      = "amount"
        type      = "DECIMAL"
        precision = 10
        scale     = 2
        nullable  = false
        tags      = ["finance"]
      }
    }

**Flat** (legacy, top-level attributes without a wrapping block):

    name        = "my_table"
    description = "..."

    column { ... }

See examples/sales_orders.hcl for a full reference.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import hcl2
import polars as pl


# ── Supported column fields ──────────────────────────────────────────────────

# These are the fields that can appear inside a `column { ... }` block.
# Any field not listed here is still preserved under an "extra" column.
KNOWN_FIELDS = [
    "name",
    "type",
    "nullable",
    "primary_key",
    "default",
    "description",
    "length",       # VARCHAR(n)
    "precision",    # DECIMAL(p, s)
    "scale",        # DECIMAL(p, s)
    "tags",
]

# ── SQL type templates ───────────────────────────────────────────────────────

_SQL_TYPES: dict[str, str] = {
    "INTEGER":   "INTEGER",
    "INT":       "INTEGER",
    "BIGINT":    "BIGINT",
    "SMALLINT":  "SMALLINT",
    "FLOAT":     "FLOAT",
    "DOUBLE":    "DOUBLE PRECISION",
    "DECIMAL":   "DECIMAL({precision}, {scale})",
    "NUMERIC":   "NUMERIC({precision}, {scale})",
    "VARCHAR":   "VARCHAR({length})",
    "CHAR":      "CHAR({length})",
    "TEXT":      "TEXT",
    "DATE":      "DATE",
    "TIMESTAMP": "TIMESTAMP",
    "BOOLEAN":   "BOOLEAN",
    "BOOL":      "BOOLEAN",
    "JSON":      "JSON",
    "ARRAY":     "ARRAY",
}


# ── Internal helpers ─────────────────────────────────────────────────────────

def _strip(value: Any) -> Any:
    """
    python-hcl2 returns string literals with surrounding quotes preserved,
    e.g.  name = "foo"  →  '"foo"'  (a Python str that starts and ends with '"').
    This function strips those extra quotes recursively for strings and lists.
    """
    if isinstance(value, str) and value.startswith('"') and value.endswith('"') and len(value) >= 2:
        return value[1:-1]
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def _clean(raw: dict) -> dict:
    """Strip hcl2 string artifacts and drop the internal __is_block__ marker."""
    return {
        k: _strip(v)
        for k, v in raw.items()
        if k != "__is_block__"
    }


def _full_type(col: dict) -> str:
    """Build the full SQL type string, e.g. 'VARCHAR(255)', 'DECIMAL(10, 2)'."""
    base = col.get("type", "").upper()
    template = _SQL_TYPES.get(base, base)
    try:
        return template.format(
            length=col.get("length", ""),
            precision=col.get("precision", ""),
            scale=col.get("scale", ""),
        )
    except KeyError:
        return base


# ── Public API ───────────────────────────────────────────────────────────────

def parse_schema(hcl_path: str | Path) -> tuple[dict, pl.DataFrame]:
    """
    Parse a .hcl table schema file.

    Args:
        hcl_path: Path to the .hcl file.

    Returns:
        table_meta: Dict of table-level attributes (name, description, database, …).
        df: Polars DataFrame — one row per column, with these columns:
              name, type, full_type, nullable, primary_key, default,
              description, tags, length, precision, scale
    """
    with open(hcl_path, "r") as f:
        raw = hcl2.load(f)

    # Unwrap a `table { ... }` block if present.
    # hcl2 turns  table { ... }  into  {"table": [{...}]},
    # so we peel off that outer list and work on the inner dict.
    if "table" in raw:
        tables = raw["table"]
        raw = tables[0] if tables else {}

    # Table-level metadata — everything except column blocks and hcl2 internals
    _skip = {"column", "__comments__", "__is_block__"}
    table_meta = {k: _strip(v) for k, v in raw.items() if k not in _skip}

    # Column definitions
    raw_columns: list[dict] = raw.get("column", [])
    if not raw_columns:
        return table_meta, pl.DataFrame()

    rows = []
    for raw_col in raw_columns:
        col = _clean(raw_col)

        # Normalise tags → comma-separated string (or empty string if absent)
        tags = col.get("tags")
        tags_str = ", ".join(tags) if isinstance(tags, list) else (tags or "")

        # Normalise default value to a clean string preserving its semantic type:
        # booleans → "TRUE"/"FALSE", numbers → bare digit string, strings → as-is.
        raw_default = col.get("default")
        if raw_default is None:
            default_str = None
        elif isinstance(raw_default, bool):
            default_str = "TRUE" if raw_default else "FALSE"
        elif isinstance(raw_default, (int, float)):
            default_str = str(raw_default)
        else:
            default_str = str(raw_default)

        rows.append({
            "name":        col.get("name"),
            "type":        (col.get("type") or "").upper(),
            "full_type":   _full_type(col),
            "nullable":    col.get("nullable", True),
            "primary_key": col.get("primary_key", False),
            "default":     default_str,
            "description": col.get("description"),
            "tags":        tags_str or None,
            "length":      col.get("length"),
            "precision":   col.get("precision"),
            "scale":       col.get("scale"),
        })

    df = pl.DataFrame(rows, infer_schema_length=len(rows))
    return table_meta, df


def _sql_default(value: str) -> str:
    """Format a DEFAULT clause for SQL — quote strings, leave booleans/numbers bare."""
    if value in ("TRUE", "FALSE"):
        return f"DEFAULT {value}"
    try:
        float(value)
        return f"DEFAULT {value}"
    except (ValueError, TypeError):
        return f"DEFAULT '{value}'"


def schema_to_sql(table_meta: dict, df: pl.DataFrame) -> str:
    """
    Generate a CREATE TABLE SQL statement from parsed schema data.

    Args:
        table_meta: Dict returned by parse_schema().
        df: DataFrame returned by parse_schema().

    Returns:
        SQL string for CREATE TABLE.
    """
    table_name = table_meta.get("name", "unnamed_table")
    database   = table_meta.get("database")
    schema     = table_meta.get("schema")

    if database and schema:
        qualified = f"{database}.{schema}.{table_name}"
    elif schema:
        qualified = f"{schema}.{table_name}"
    else:
        qualified = table_name

    lines = []
    pk_cols = []

    for row in df.iter_rows(named=True):
        col_name  = row["name"]
        col_type  = row["full_type"]
        nullable  = row["nullable"]
        default   = row["default"]
        is_pk     = row["primary_key"]

        parts = [f"    {col_name}", col_type]

        if default is not None:
            parts.append(_sql_default(default))
        if not nullable:
            parts.append("NOT NULL")

        lines.append(" ".join(parts))

        if is_pk:
            pk_cols.append(col_name)

    if pk_cols:
        lines.append(f"    PRIMARY KEY ({', '.join(pk_cols)})")

    body = ",\n".join(lines)
    sql = f"CREATE TABLE {qualified} (\n{body}\n);"

    description = table_meta.get("description")
    if description:
        sql = f"-- {description}\n{sql}"

    return sql
