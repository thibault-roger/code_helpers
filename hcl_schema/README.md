# HCL Schema Reader

Parse a `.hcl` table schema file and get back:
1. **Table metadata** — name, description, database, owner, … as a plain dict
2. **Column catalog** — a Polars DataFrame, one row per column
3. **CREATE TABLE SQL** — generated from the schema (bonus utility)

## Usage

```python
from hcl_schema.schema_reader import parse_schema, schema_to_sql

meta, df = parse_schema("examples/sales_orders.hcl")

print(meta)
# {'name': 'sales_orders', 'description': 'Sales orders fact table',
#  'database': 'analytics', 'schema': 'public', 'owner': 'data-team'}

print(df)
# shape: (10, 11)
# ┌──────────────┬───────────┬──────────────┬──────────┬─────────────┬─────────┬─────────────┬────────┬───────────┬───────┐
# │ name         ┆ type      ┆ full_type     ┆ nullable ┆ primary_key ┆ default ┆ description ┆ length ┆ precision ┆ scale │
# ╞══════════════╪═══════════╪══════════════╪══════════╪═════════════╪═════════╪═════════════╪════════╪═══════════╪═══════╡
# │ order_id     ┆ INTEGER   ┆ INTEGER       ┆ false    ┆ true        ┆ null    ┆ …           ┆ null   ┆ null      ┆ null  │
# │ customer_nam ┆ VARCHAR   ┆ VARCHAR(255)  ┆ true     ┆ false       ┆ null    ┆ …           ┆ 255    ┆ null      ┆ null  │
# │ amount       ┆ DECIMAL   ┆ DECIMAL(10,2) ┆ false    ┆ false       ┆ null    ┆ …           ┆ null   ┆ 10        ┆ 2     │
# │ …            ┆ …         ┆ …             ┆ …        ┆ …           ┆ …       ┆ …           ┆ …      ┆ …         ┆ …     │

print(schema_to_sql(meta, df))
# -- Sales orders fact table
# CREATE TABLE analytics.public.sales_orders (
#     order_id INTEGER NOT NULL,
#     customer_name VARCHAR(255),
#     amount DECIMAL(10, 2) NOT NULL,
#     status VARCHAR(50) DEFAULT 'pending' NOT NULL,
#     is_international BOOLEAN DEFAULT FALSE NOT NULL,
#     …
#     PRIMARY KEY (order_id)
# );
```

## HCL file format

```hcl
name        = "my_table"
description = "What this table contains"
database    = "analytics"
schema      = "public"
owner       = "data-team"

column {
  name        = "id"
  type        = "INTEGER"
  nullable    = false
  primary_key = true
  description = "Surrogate key"
}

column {
  name        = "label"
  type        = "VARCHAR"
  length      = 100
  nullable    = false
  default     = "n/a"
  description = "Human-readable label"
  tags        = ["display"]
}

column {
  name      = "amount"
  type      = "DECIMAL"
  precision = 10
  scale     = 2
  nullable  = true
  tags      = ["finance", "sensitive"]
}
```

### Supported column fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Column name |
| `type` | Yes | Base type (see below) |
| `nullable` | No (default `true`) | Whether the column accepts nulls |
| `primary_key` | No (default `false`) | Part of the primary key |
| `default` | No | Default value |
| `description` | No | Human-readable description |
| `tags` | No | List of string tags |
| `length` | For VARCHAR/CHAR | Max character length |
| `precision` | For DECIMAL/NUMERIC | Total significant digits |
| `scale` | For DECIMAL/NUMERIC | Decimal places |

### Supported types

`INTEGER` · `BIGINT` · `SMALLINT` · `FLOAT` · `DOUBLE` · `DECIMAL` · `NUMERIC`
· `VARCHAR` · `CHAR` · `TEXT` · `DATE` · `TIMESTAMP` · `BOOLEAN` · `JSON` · `ARRAY`

## Files

| File | Description |
|------|-------------|
| [`schema_reader.py`](schema_reader.py) | `parse_schema()` and `schema_to_sql()` |
| [`examples/sales_orders.hcl`](examples/sales_orders.hcl) | Full reference schema with 10 columns |

## Setup

```bash
pip install python-hcl2 polars
```
