# Dremio — Data Read & Write in Python

## Connection options

| Method | Speed | Setup | Write support | Use when |
|--------|-------|-------|---------------|----------|
| **Arrow Flight** | Fast | Medium (port 32010) | Yes | Default — bulk reads/writes |
| **REST API** | Slower | Low (just HTTP) | Via SQL only | Quick scripts, no driver |
| SQLAlchemy/ODBC | Medium | High (ODBC driver) | Yes | Legacy integrations |

Arrow Flight is the native Dremio protocol. It transfers data in columnar format (Apache Arrow) with minimal overhead — the right default for any non-trivial volume.

## Files

| File | Description |
|------|-------------|
| [`client.py`](client.py) | Production `DremioClient` — Arrow Flight, parallel reads, batched writes, streaming |
| [`rest_client.py`](rest_client.py) | Lightweight REST API client — no driver required |
| [`requirements.txt`](requirements.txt) | Dependencies |

## Quick start

```python
from dremio.client import DremioClient, DremioConfig

cfg = DremioConfig(host="dremio.company.com", username="user", password="pass")
client = DremioClient(cfg)

# Read — parallel across Dremio fragments
df = client.read('SELECT col_a, col_b FROM "space"."table" WHERE dt >= \'2025-01\'')

# Stream — constant RAM, for datasets larger than memory
for chunk in client.stream('SELECT * FROM "space"."huge_table"'):
    process(chunk)

# Write — batched, into an existing table
client.write(df, "my_space/output_table")

# Create a table from a DataFrame (Polars or pandas) and push the data
client.create_table(df, "my_source/staging/orders", replace=True)

# Stream directly to Parquet — never loads full dataset in RAM
client.stream_to_parquet('SELECT * FROM "space"."huge_table"', "/tmp/output.parquet")
```

## Creating a table from a DataFrame

`create_table()` infers a `CREATE TABLE` from the DataFrame's Arrow schema,
executes it, then streams the rows in via Arrow Flight. It accepts both Polars
and pandas DataFrames (pandas stays an optional dependency — it's only imported
if you pass a pandas object).

```python
import polars as pl
# or: import pandas as pd

df = pl.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"], "amount": [1.5, 2.0, 9.9]})

# Drops the table first if it exists, recreates it, and loads the data
client.create_table(df, "my_source/staging/orders", replace=True)

# Create the empty table only (no data load)
client.create_table(df, "my_source/staging/orders", push_data=False)
```

**Important — where you can create tables.** Dremio only creates physical
tables in a **writable data-lake source** (S3, ADLS, HDFS, NAS … backed by
Iceberg). You cannot create a table in a read-only source or in the semantic
layer (a "Space") — those hold views, not tables. Point `destination` at a
writable source path, e.g. `"my_source/staging/orders"`.

Arrow → Dremio type mapping used:

| Arrow type | Dremio SQL type |
|------------|-----------------|
| bool | `BOOLEAN` |
| int8/16/32 | `INT` |
| int64 | `BIGINT` |
| float32 | `FLOAT` |
| float64 | `DOUBLE` |
| decimal128(p,s) | `DECIMAL(p, s)` |
| date | `DATE` |
| time | `TIME` |
| timestamp | `TIMESTAMP` |
| string | `VARCHAR` |
| binary | `VARBINARY` |

## High-volume checklist

1. **Prune columns** — never `SELECT *` on wide tables
2. **Push predicates** — filter on partition keys in SQL, not in Python
3. **Use `stream()`** instead of `read()` when dataset > available RAM
4. **Use `stream_to_parquet()`** for large intermediate files
5. **Tune `batch_size`** and `max_workers` in `DremioConfig` for your cluster
