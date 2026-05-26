"""
HCL table schema reader.

Parses a .hcl schema file containing one or more labeled `table` blocks and
returns a list of (table_meta, columns_df) tuples — one per table.

Also provides a helper to generate a CREATE TABLE SQL statement from a parsed
(table_meta, df) pair.

Expected .hcl format
--------------------
One or more labeled table blocks in a single file.
Both table and column names are block labels (not inline fields).
Attribute values may be quoted strings or bare identifiers.

    table "orders" {
      schema  = public          # unquoted identifier — also accepted
      comment = "Fact table"

      column "order_id" {
        type    = integer
        null    = false
        comment = "Unique order identifier"
      }

      column "amount" {
        type      = decimal
        precision = 10
        scale     = 2
        null      = false
        tags      = ["finance"]
      }
    }

    table "customers" {
      schema  = public
      comment = "Customer dimension"

      column "customer_id" { ... }
    }

hcl2 parses labeled blocks as:
    {"table": [{"orders": [{...body...}]}, ...]}
    body["column"] → [{"order_id": [{...}]}, {"amount": [{...}]}, ...]

Field name aliases handled automatically:
    null    → nullable
    comment → description  (table and column level)
    type values are normalised to uppercase (text → TEXT, integer → INTEGER …)

See examples/sales_orders.hcl for a full reference.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import hcl2
import polars as pl


# ── Supported column fields ──────────────────────────────────────────────────

# Fields recognised inside a `column "name" { ... }` block.
# `null` and `comment` are the canonical HCL names; they are mapped to
# `nullable` and `description` in the output DataFrame.
KNOWN_FIELDS = [
    "type",
    "null",         # → nullable
    "comment",      # → description
    "primary_key",
    "default",
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
    python-hcl2 encodes values in two ways that need unwrapping:
      - Quoted string literals:   name = "foo"   →  '"foo"'   →  'foo'
      - Bare identifiers:         type = text    →  '${text}' →  'text'
    This function strips both artifacts recursively for strings and lists.
    """
    if isinstance(value, str):
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            return value[1:-1]
        if value.startswith("${") and value.endswith("}"):
            return value[2:-1]
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


# ── Internal helpers ─────────────────────────────────────────────────────────

def _parse_table_body(name: str, body: dict) -> tuple[dict, pl.DataFrame]:
    """
    Build (table_meta, df) from a single table body dict and its label name.

    Column blocks are labeled:  column "col_name" { ... }
    hcl2 yields: body["column"] = [{"col_name": [{...}]}, ...]

    Field aliases applied:
        null    (HCL) → nullable   (output)
        comment (HCL) → description (output)
    """
    _skip = {"column", "primary_key", "__comments__", "__is_block__"}
    table_meta = {k: _strip(v) for k, v in body.items() if k not in _skip}
    # Map comment → description at table level
    if "comment" in table_meta:
        table_meta["description"] = table_meta.pop("comment")
    table_meta["name"] = name  # inject the label as the table name

    # Collect primary-key column names from a table-level primary_key block
    # e.g.  primary_key { columns = [column.order_id] }
    pk_set: set[str] = set()
    for pk_entry in body.get("primary_key", []):
        pk_body = pk_entry[0] if isinstance(pk_entry, list) else pk_entry
        if isinstance(pk_body, dict):
            for ref in pk_body.get("columns", []):
                # refs look like  "${column.col_name}"  after stripping → "column.col_name"
                ref_str = _strip(ref)
                if isinstance(ref_str, str) and "." in ref_str:
                    pk_set.add(ref_str.split(".")[-1])

    # hcl2 parses  column "col_name" { ... }  as:
    #   [{"col_name": [{...body...}]}, ...]
    raw_columns: list[dict] = body.get("column", [])
    if not raw_columns:
        return table_meta, pl.DataFrame()

    rows = []
    for col_entry in raw_columns:
        col_name, col_body_list = next(iter(col_entry.items()))
        col_name = _strip(col_name)
        col_body = col_body_list[0] if isinstance(col_body_list, list) else col_body_list
        col = _clean(col_body)

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

        # `null = false` means NOT nullable; default (field absent) → nullable
        nullable = col.get("null", True)

        rows.append({
            "name":        col_name,
            "type":        (col.get("type") or "").upper(),
            "full_type":   _full_type(col),
            "nullable":    nullable,
            "primary_key": col_name in pk_set,
            "default":     default_str,
            "description": col.get("comment") or col.get("description"),
            "tags":        tags_str or None,
            "length":      col.get("length"),
            "precision":   col.get("precision"),
            "scale":       col.get("scale"),
        })

    df = pl.DataFrame(rows, infer_schema_length=len(rows))
    return table_meta, df


# ── Public API ───────────────────────────────────────────────────────────────

def parse_schema(hcl_path: str | Path) -> list[tuple[dict, pl.DataFrame]]:
    """
    Parse a .hcl file containing one or more labeled `table` blocks.

    Args:
        hcl_path: Path to the .hcl file.

    Returns:
        List of (table_meta, df) tuples — one per table block, in file order.

        table_meta keys: name (from the block label), description, database,
                         schema, and any other top-level attributes.
        df columns:      name, type, full_type, nullable, primary_key, default,
                         description, tags, length, precision, scale
    """
    with open(hcl_path, "r") as f:
        raw = hcl2.load(f)

    # hcl2 parses  table "foo" { ... }  as:
    #   {"table": [{"foo": [{...body...}]}, ...]}
    # Each element of the list is a single-key dict mapping the label to a
    # one-element list containing the body dict.
    results = []
    for entry in raw.get("table", []):
        table_name, body_list = next(iter(entry.items()))
        table_name = _strip(table_name)  # hcl2 keeps quotes on block labels
        body = body_list[0] if isinstance(body_list, list) else body_list
        results.append(_parse_table_body(table_name, body))

    return results


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
