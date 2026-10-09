# 03 — The Python code, explained

This page walks through every Python file in the folder: what it does, why it is
written that way, and how to write your own scripts that work **both locally and
against a remote database** without changing a line.

**Learning path:** [01 Concepts](01_concepts.md) → [02 Local database](02_local_database.md) →
**03 Python code** → [04 Migrations](04_migrations.md) →
[05 Remote database](05_remote_database.md) · [06 Troubleshooting](06_troubleshooting.md)

---

## The map

```
                         reads DATABASE_URL, APP_ENV
 your script ──uses──▶ config.py  (PgConfig)  ──────────▶ "where am I connecting?"
     │
     └──uses──▶ client.py (PostgresClient) ──▶ SQLAlchemy ──▶ psycopg ──▶ PostgreSQL
                    read_polars / read_pandas / stream_polars / write_polars / execute

 example_script.py   a template to copy for your own scripts
 demo.py             loads fake data and shows every client method   (local only)
 check_connection.py "can I connect? what's on the other side?"     (read-only)
 local_server.py     starts/stops the LOCAL server (not used by your scripts)
```

| File | You run it… | Touches data? |
|---|---|---|
| [`local_server.py`](../local_server.py) | through `make db-*` | creates/deletes the **local** server only |
| [`config.py`](../config.py) | never directly (imported) | no |
| [`client.py`](../client.py) | never directly (imported) | yes, through your calls |
| [`check_connection.py`](../check_connection.py) | `make db-check` / `python check_connection.py` | read-only |
| [`demo.py`](../demo.py) | `make demo` | **empties** and refills tables (refuses when `APP_ENV=prod`) |
| [`example_script.py`](../example_script.py) | `python example_script.py` | reads + inserts 3 example customers |

---

## `config.py` — where am I connecting?

The whole "local vs remote" switch lives here, in ~20 lines.

```python
@dataclass
class PgConfig:
    url: str = field(repr=False)   # repr=False: printing the config never shows the password
    app_env: str = "local"
    batch_size: int = 50_000       # rows per chunk when writing
    read_chunksize: int = 50_000   # rows per batch when streaming
    connect_timeout: int = 10      # give up after 10 s if the server doesn't answer
```

### `PgConfig.from_env()`

```python
url = os.environ.get("DATABASE_URL") or _url_from_libpq_env()
```

1. Look for `DATABASE_URL`.
2. If absent, try to build one from `PGHOST`, `PGUSER`, `PGPASSWORD`, … (some
   platforms give you those instead of a URL).
3. If there is nothing at all, stop with a message telling you what to do:
   ```
   RuntimeError: No database configured. Locally run:
       eval "$(python local_server.py env)"
   ```
4. `validate()`: if `APP_ENV=prod`, the URL **must** encrypt the connection
   (`sslmode=require`, `verify-ca` or `verify-full`), otherwise:
   ```
   ValueError: APP_ENV=prod requires sslmode in ['require', 'verify-ca', 'verify-full'], got 'disable'
   ```
   This prevents sending production passwords and data unencrypted by mistake.

### Two small helpers

```python
cfg.sqlalchemy_url()  # postgres://…  ->  postgresql+psycopg://…   (SQLAlchemy's format)
cfg.safe_url()        # postgresql+psycopg://postgres:***@127.0.0.1:5433/app?...  (safe to print)
```

**Why it matters:** no file in this project contains a host or a password. The same
code runs everywhere; the terminal decides where it points.

---

## `client.py` — talking to the database

### Creating the client

```python
with PostgresClient(PgConfig.from_env()) as client:
    ...
# leaving the `with` block closes all connections, even if an error happened
```

Inside, `__init__` creates a SQLAlchemy **engine**:

```python
create_engine(cfg.sqlalchemy_url(), pool_pre_ping=True,
              connect_args={"connect_timeout": cfg.connect_timeout})
```

- The engine keeps a **pool** of open connections and reuses them (opening a
  connection to a remote server takes time).
- `pool_pre_ping=True` checks a connection is still alive before using it. Remote
  networks drop idle connections; without this you'd get random "connection closed"
  errors.
- `connect_timeout` makes an unreachable server fail after 10 s instead of hanging.

### Reading: `read_polars` / `read_pandas`

```python
df = client.read_polars(
    "SELECT * FROM sales_orders WHERE status = :status AND order_date >= :since",
    {"status": "shipped", "since": "2024-06-01"},
)
```

`:status` and `:since` are **placeholders**; the values travel separately from the SQL.

> ⚠️ **Never build SQL with f-strings** from values:
> `f"... WHERE full_name = '{name}'"` breaks on `O'Brien` and lets a malicious value
> rewrite your query (*SQL injection*). Placeholders are always safe.

`read_pandas` is identical but returns a pandas DataFrame.

Both load the **whole result in memory**. Let PostgreSQL do the heavy work (filters,
`GROUP BY`, joins) so only the small result comes back to Python:

```python
# good: 12 rows come back
client.read_polars("SELECT date_trunc('month', order_date) AS m, sum(amount) FROM sales_orders GROUP BY 1")
# wasteful: 200,000 rows come back, then you aggregate in Python
client.read_polars("SELECT * FROM sales_orders")
```

### Reading a lot: `stream_polars`

```python
for batch in client.stream_polars("SELECT * FROM sales_orders", batch_size=50_000):
    batch.write_parquet(f"export_{i}.parquet")   # each batch is a Polars DataFrame
```

`stream_results=True` opens a **server-side cursor**: PostgreSQL keeps the result and
sends 50,000 rows at a time. Your memory use stays flat whether the table has 1 million
or 1 billion rows. Use it for exports and big transformations.

### Writing a lot: `write_polars` / `write_pandas`

```python
client.write_polars(df, "sales_orders")      # returns the number of rows written
```

Step by step:

1. **Checks the table exists.** If not:
   ```
   LookupError: public.nope does not exist. Add it to atlas/schema.pg.hcl and run
   `make migrate-diff name=...` then `make migrate-apply`.
   ```
   Tables are created by migrations only, never from Python (see [04](04_migrations.md)).
   This is deliberate: `pandas.to_sql` / `polars.write_database` would silently create
   a table with *guessed* types — on your laptop only — and local and prod would drift.
2. **Matches columns by name.** Table columns missing from the DataFrame get their
   default value (e.g. `created_at` → `now()`).
3. **Uses `COPY`**, PostgreSQL's bulk-load command: each chunk of 50,000 rows is turned
   into CSV in memory and streamed to the server. It is many times faster than one
   `INSERT` per row — the 200,000 orders in `demo.py` load in under a second.
4. **One transaction for all chunks.** If row 150,000 is invalid, *nothing* is written:
   no half-loaded tables.

If a row breaks a rule of the table, PostgreSQL rejects the whole write:

```python
from psycopg.errors import IntegrityError
try:
    client.write_polars(df, "sales_orders")
except IntegrityError as exc:
    print(exc.diag.constraint_name)    # e.g. sales_orders_customer_fk
```

### Small changes: `execute`

```python
client.execute("UPDATE sales_orders SET status = 'shipped' WHERE order_id = :id", {"id": 42})
```

For `INSERT` / `UPDATE` / `DELETE` statements, committed immediately. Not for
`CREATE`/`ALTER`/`DROP`: those go in migrations.

---

## `example_script.py` — the template for your scripts

```python
cfg = PgConfig.from_env()                       # 1. where (from the terminal)
print(f"Connected to: {cfg.safe_url()}")        #    always print WHERE you are
with PostgresClient(cfg) as client:             # 2. open, auto-close
    recent = client.read_polars("... WHERE order_date >= :since", {"since": "2024-12-01"})  # 3. read
    client.execute("INSERT ... ON CONFLICT (customer_id) DO NOTHING", {...})              # 4. small write
    client.write_polars(to_insert, "customers")                                           # 5. bulk write
```

Run it locally:

```bash
eval "$(make -s db-env)"
python example_script.py
```
```
Connected to: postgresql+psycopg://postgres:***@127.0.0.1:5433/app?sslmode=disable
shape: (5, 3)
┌─────────────┬────────┬───────────────┐
│ customer_id ┆ orders ┆ revenue       │
╞═════════════╪════════╪═══════════════╡
│ 968         ┆ 31     ┆ 9220.03       │
│ …                                     │
Inserted 2 new customer(s)
```

Run it a second time: `Inserted 0 new customer(s)` — it is written to be **re-runnable**
(it skips rows that already exist). Make your scripts re-runnable too: on a remote
database, "it crashed halfway, I ran it again" must not create duplicates.

Run it against a remote database: **same command**, different terminal setup
(see [05](05_remote_database.md#step-6--run-your-python-code-against-the-remote)).

---

## `demo.py` — the guided tour (local only)

| Section | What it shows |
|---|---|
| `synthetic_data()` | builds 1,000 customers and 200,000 orders with NumPy/Polars (fixed seed: same data every run) |
| Atlas version query | the app can see which migration version the database is at |
| `if cfg.is_prod: return` | **stops before deleting anything** when `APP_ENV=prod` |
| `TRUNCATE` | empties both tables (that's why it's local only) |
| `write_polars` ×2 | COPY load |
| monthly revenue query | aggregation done by PostgreSQL, with a `:excluded` placeholder |
| `read_pandas` join | same thing with pandas |
| `stream_polars` | counts rows batch by batch |
| the "bad" row | an order for customer 999999, which doesn't exist → the foreign key rejects it |

---

## `check_connection.py` — before anything else

Run it whenever you point at a new database. It connects with the **same config** as
your scripts and reports server version, user, TLS, timezone, collation, rights,
extensions and Atlas version (output shown in [02](02_local_database.md#step-2--is-it-running-can-i-connect)).
When the connection fails it translates the error:

```
CONNECTION FAILED:
  connection timeout expired

Likely cause: The host did not answer at all (packets are dropped).
  - remote databases are often only reachable from the company network: VPN on?
  - a firewall / security group may need to allow your IP
```

---

## `local_server.py` — the local server's remote control

You use it through `make`, but it's ~250 readable lines:

| Command | Function | Does |
|---|---|---|
| `make db-start` | `start()` | `_initdb()` the first time, `pg_ctl start`, create `app` + `atlas_dev` |
| `make db-stop` | `stop()` | `pg_ctl stop -m fast` (data kept) |
| `make db-status` | `status()` | is the server running, which version, where |
| `make -s db-env` | `env()` | prints the `export …` lines |
| `make db-psql` | `psql()` | opens the SQL console on `app` |
| `make db-reset` | `reset()` | stop + delete `.pgdata/` + start |
| `make db-clone` | `clone()` | replace local `app` with a copy of `$SOURCE_URL` (see [04](04_migrations.md)) |

It never touches a remote database except to **read** from it during `clone`.

---

## Mistakes to avoid

| ❌ Don't | ✅ Do |
|---|---|
| `create_engine("postgresql://user:pass@prod-host/app")` in a script | `PgConfig.from_env()` |
| `f"WHERE id = {user_input}"` | `"WHERE id = :id", {"id": user_input}` |
| `df.to_pandas().to_sql("new_table", …)` to create a table | add the table to `schema.pg.hcl`, make a migration |
| `client.execute("ALTER TABLE …")` | a migration |
| `SELECT *` on a huge table then filter in Python | filter in SQL, or `stream_polars` |
| assume you're on local | print `cfg.safe_url()` / run `check_connection.py` |

Next: [04 — Migrations: break them locally, ship them safely](04_migrations.md)
