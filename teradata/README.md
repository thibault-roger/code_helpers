# Teradata — Read & Write in Python

A `TeradataClient` that lets you move data between Teradata and pandas / Polars DataFrames with a single method call.

---

## Connection options

| Layer | Role | Notes |
|-------|------|-------|
| **teradatasql** | DBAPI2 driver | Official Teradata Python driver |
| **teradatasqlalchemy** | SQLAlchemy dialect | Wraps teradatasql; required for `read_sql` / `to_sql` |
| **SQLAlchemy 2** | Connection abstraction | Used by both pandas and Polars |

Polars has no native ADBC driver for Teradata, so reads go through `pl.read_database` with a SQLAlchemy connection and writes convert to pandas first (`df.to_pandas()` uses the zero-copy Arrow bridge wherever possible).

---

## Files

| File | Description |
|------|-------------|
| [`client.py`](client.py) | `TeradataClient` — read/write for pandas and Polars, chunked streaming |
| [`access_control.py`](access_control.py) | User creation, roles, column/row scoping, views, GRANT/REVOKE reference |
| [`requirements.txt`](requirements.txt) | Dependencies |

---

## Setup

```bash
pip install teradatasql teradatasqlalchemy sqlalchemy pandas polars pyarrow
```

> `teradatasql` ships its own ODBC/native libraries — no separate Teradata driver installation required.

---

## Quick start

```python
from teradata.client import TeradataClient, TeradataConfig

cfg = TeradataConfig(
    host="tdhost.company.com",
    username="my_user",
    password="my_password",
    database="my_db",       # default schema for writes
    logmech="TD2",          # TD2 | LDAP | TDNEGO | KRB5
)

with TeradataClient(cfg) as client:

    # ── Read ─────────────────────────────────────────────────────────
    df_pd = client.read_pandas("SELECT * FROM my_db.orders WHERE status = 'open'")
    df_pl = client.read_polars("SELECT * FROM my_db.orders WHERE status = 'open'")

    # ── Stream large tables (RAM stays flat) ─────────────────────────
    for chunk in client.stream_polars("SELECT * FROM my_db.events", chunksize=100_000):
        process(chunk)

    # ── Write ─────────────────────────────────────────────────────────
    client.write_pandas(df_pd, table="orders_staging", if_exists="replace")
    client.write_polars(df_pl, table="orders_staging", if_exists="append")

    # ── DDL ──────────────────────────────────────────────────────────
    client.execute("COLLECT STATISTICS ON my_db.orders COLUMN order_date")
```

---

## Authentication

| `logmech` | When to use |
|-----------|-------------|
| `TD2` | Default — native Teradata username/password |
| `LDAP` | Active Directory / LDAP identity |
| `TDNEGO` | Auto-negotiate (tries Kerberos, falls back to TD2) |
| `KRB5` | Kerberos — requires a valid TGT (`kinit`) |

---

## `if_exists` behaviour (writes)

| Value | Behaviour |
|-------|-----------|
| `append` | Insert rows into the existing table — table must exist |
| `replace` | Drop, recreate, and insert — SQLAlchemy infers column types |
| `fail` | Raise an error if the table already exists |

> **Tip:** For production loads, pre-create the table with proper Teradata types (PI, partitioning, compression) and always use `if_exists="append"`. Using `"replace"` lets SQLAlchemy generate the DDL which may not match your intended table structure.

---

## Performance checklist

1. **Prune columns** — avoid `SELECT *` on wide tables
2. **Push predicates** — filter in SQL, not Python
3. **Use `stream_pandas` / `stream_polars`** for tables larger than available RAM
4. **Tune `batch_size`** — larger batches (up to ~50k) reduce round-trips on fast networks; smaller batches use less memory
5. **Collect statistics** after bulk loads so the query optimizer has fresh data
