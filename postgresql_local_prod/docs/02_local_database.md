# 02 — Your local database, step by step

By the end of this page you will have a real PostgreSQL server running on your laptop,
with tables and 200,000 rows in it, and you will know what each command did.

**Learning path:** [01 Concepts](01_concepts.md) → **02 Local database** →
[03 Python code](03_python_code.md) → [04 Migrations](04_migrations.md) →
[05 Remote database](05_remote_database.md) · [06 Troubleshooting](06_troubleshooting.md)

All commands are run from the `postgresql_local_prod/` folder.

---

## Step 0 — One-time installation

```bash
cd postgresql_local_prod

# 1. A Python virtual environment (an isolated set of packages for this project)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
#    your prompt now starts with (.venv); repeat `source` in every new terminal

# 2. Python packages — includes `pgserver`, which contains the PostgreSQL programs
pip install -r requirements.txt

# 3. Atlas, the migration tool (a standalone program, not a pip package)
brew install ariga/tap/atlas       # macOS with Homebrew
# or: curl -sSf https://atlasgo.sh | sh

# 4. Check
python -c "import pgserver; print('pgserver ok')"
atlas version
make --version                     # `make` runs the shortcuts defined in the Makefile
```

> **What is `make`?** The [`Makefile`](../Makefile) gives short names to longer commands.
> `make db-start` runs `python local_server.py start`. You can always open the Makefile to
> see the real command behind a shortcut — nothing is hidden.

---

## Step 1 — Start the server

```bash
make db-start
```

The **first** time, you'll see a lot of output. Here it is, annotated:

```
The database cluster will be initialized with locale "C".      ┐
creating subdirectories ... ok                                  │ 1. initdb: creates the
selecting default max_connections ... 100                       │    data directory .pgdata/
running bootstrap script ... ok                                 │    (only the first time)
Success. You can now start the database server using: ...       ┘
waiting for server to start.... done                            ┐ 2. pg_ctl start: launches the
server started                                                  ┘    server in the background
Created database app                                            ┐ 3. creates the two databases
Created database atlas_dev                                      ┘    we need (first time only)
PostgreSQL 16.2 ready on 127.0.0.1:5433
Load the connection env vars with:  eval "$(python local_server.py env)"
```

What happened, in order (see `start()` in [`local_server.py`](../local_server.py)):

1. **`initdb`** created the folder `.pgdata/`, which holds everything: data files,
   configuration (`postgresql.conf`), the log (`server.log`). It also created the
   superuser `postgres` with the password `localdev`, and required a password for every
   connection — like a real server.
2. The script appended a few settings to `.pgdata/postgresql.conf`:
   ```
   listen_addresses = '127.0.0.1'   # only accept connections from this computer
   port = 5433                      # 5433, not 5432, to avoid clashing with another install
   unix_socket_directories = ''     # network connections only, like a remote server
   timezone = 'UTC'                 # same as production servers
   ```
3. **`pg_ctl start`** launched the server. It now runs **in the background**: closing
   the terminal does not stop it.
4. It created the databases `app` (your data) and `atlas_dev` (Atlas's empty scratchpad).

Run `make db-start` again: it detects everything exists and just says it's ready.
It is always safe to run.

> `.pgdata/` is ignored by git ([`.gitignore`](../.gitignore)): your local data is yours,
> it is never committed or shared.

---

## Step 2 — Is it running? Can I connect?

```bash
make db-status
```
```
running   127.0.0.1:5433   PostgreSQL 16.2
data dir  /…/postgresql_local_prod/.pgdata
binaries  /…/site-packages/pgserver/pginstall/bin
```

```bash
make db-check          # runs check_connection.py against the local server
```
```
APP_ENV      local
URL          postgresql+psycopg://postgres:***@127.0.0.1:5433/app?sslmode=disable

-- server --------------------------------------------------
version      16.2
host:port    127.0.0.1:5433
database     app
user         postgres
TLS          off

-- settings that change query results ---------------------
timezone     UTC
collation    C

-- rights --------------------------------------------------
superuser    True
can create tables in public: True  (only the migration user needs this)

-- extensions ----------------------------------------------
installed    plpgsql 1.0

-- atlas ---------------------------------------------------
applied      none (Atlas has never run migrate apply here)

OK — connected. Python code and Atlas will connect the same way.
```

[`check_connection.py`](../check_connection.py) is your best friend: it says **where**
you are connected and **what** that database looks like. It only reads. You will run
the same script against the remote database in [05](05_remote_database.md).

---

## Step 3 — The connection variables

The `make` shortcuts set the variables for you. To use Python or Atlas **directly** in
your terminal, load them yourself:

```bash
make -s db-env             # just PRINTS them
```
```
export DATABASE_URL='postgres://postgres:localdev@127.0.0.1:5433/app?sslmode=disable'
export ATLAS_DEV_URL='postgres://postgres:localdev@127.0.0.1:5433/atlas_dev?sslmode=disable'
export APP_ENV=local
```
```bash
eval "$(make -s db-env)"   # EXECUTES those lines: they are now set in this terminal
echo "$DATABASE_URL"
```

> The local password `localdev` is not a secret: the server only accepts connections
> from your own computer. Remote passwords are a different story ([05](05_remote_database.md)).

---

## Step 4 — Create the tables

The server is empty. Tables are created **only** by migrations (explained in
[04](04_migrations.md)); for now just apply the existing ones:

```bash
make migrate-apply
```
```
Migrating to version 20261008195351 (1 migrations in total):
  -- migrating version 20261008195351
    -> CREATE TABLE "public"."customers" ( ... );
    -> CREATE TABLE "public"."sales_orders" ( ... );
    ...
  -- ok (7.9ms)
  -- 1 migration
  -- 17 sql statements
```

Atlas read the files in [`atlas/migrations/`](../atlas/migrations/), saw that none had
run on this database, ran them, and wrote down that it did (in `atlas_schema_revisions`).
Run it again: `No migration files to execute`.

---

## Step 5 — Look inside with psql

`psql` is PostgreSQL's SQL console. It came with pgserver.

```bash
make db-psql
```
```
psql (16.2)
Type "help" for help.

app=#
```

You are connected to the `app` database (`app=#` is the prompt). Useful commands —
the ones starting with `\` are psql shortcuts, the others are SQL and **end with `;`**:

| Type | What it shows |
|---|---|
| `\l` | the databases on this server |
| `\dn` | the schemas in this database |
| `\dt` | the tables |
| `\d sales_orders` | columns, types, indexes, constraints of a table |
| `SELECT count(*) FROM sales_orders;` | any SQL |
| `\x` | toggle vertical display (for wide rows) |
| `\q` | quit |

```
app=# \dt
            List of relations
 Schema |     Name     | Type  |  Owner
--------+--------------+-------+----------
 public | customers    | table | postgres
 public | sales_orders | table | postgres

app=# \d sales_orders
                         Table "public.sales_orders"
      Column      |           Type           | Nullable |           Default
------------------+--------------------------+----------+------------------------------
 order_id         | bigint                   | not null |
 customer_id      | integer                  | not null |
 order_date       | date                     | not null |
 shipped_at       | timestamp with time zone |          |
 amount           | numeric(10,2)            | not null |
 status           | character varying(50)    | not null | 'pending'::character varying
 is_international | boolean                  | not null | false
Indexes:
    "sales_orders_pkey" PRIMARY KEY, btree (order_id)
    "sales_orders_order_date_idx" btree (order_date)
Check constraints:
    "sales_orders_amount_non_negative" CHECK (amount >= 0::numeric)
Foreign-key constraints:
    "sales_orders_customer_fk" FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT
```

> Prefer a graphical tool? DBeaver, DataGrip, pgAdmin or the VS Code "PostgreSQL"
> extension all work: host `127.0.0.1`, port `5433`, database `app`, user `postgres`,
> password `localdev`, SSL off.

---

## Step 6 — Put data in it

```bash
make demo
```
```
APP_ENV=local  ->  postgresql+psycopg://postgres:***@127.0.0.1:5433/app?sslmode=disable
Schema version (Atlas): ('20261008195351', 'init')
Loaded 1,000 customers and 200,000 orders via COPY
shape: (3, 3)
┌────────────┬────────┬───────────────┐
│ month      ┆ orders ┆ revenue       │
╞════════════╪════════╪═══════════════╡
│ 2024-01-01 ┆ 11187  ┆ 2818331.26    │
│ ...                                 │
Streamed 200,000 rows in batches of 50,000
Rejected as expected: sales_orders_customer_fk
```

[`demo.py`](../demo.py) empties the tables, generates fake data and loads it. It is
explained line by line in [03](03_python_code.md). Data matters: in [04](04_migrations.md)
you'll see migrations that work on an empty table and **fail** on a full one.

---

## Step 7 — Stop, restart, reset

```bash
make db-stop      # stop the server. Data stays in .pgdata/
make db-start     # start again: your tables and rows are still there
make db-reset     # ⚠ DELETE .pgdata/ entirely and start a brand-new empty server
```

```
             make db-start                       make db-stop
 (nothing) ──────────────▶ RUNNING ◀──────────────────────────▶ STOPPED
  first time:                 │            make db-start           │
  initdb + start              │                                    │
                              └──── make db-reset (delete + new) ◀─┘
```

- After **restarting your computer** the server is stopped: `make db-start`.
- **Broke something?** `make db-reset && make migrate-apply && make demo` gives you a
  clean, filled database in a few seconds. That is the whole point of a local database:
  failing costs nothing.

---

## Customising (optional)

Set these **before** the first `make db-start` (or before a `make db-reset`):

| Variable | Default | Why change it |
|---|---|---|
| `LOCAL_PG_PORT` | `5433` | the port is already used by something else |
| `LOCAL_PG_LOCALE` | `C` | to match production's collation (sorting rules) — see [05](05_remote_database.md#step-4--check-the-connection-and-compare-with-local) |
| `PG_BIN_DIR` | pgserver's programs | use another PostgreSQL install (see below) |
| `LOCAL_PG_DATA` | `./.pgdata` | keep the data elsewhere |

Example: `LOCAL_PG_PORT=5440 make db-reset`

### Using a different PostgreSQL version (conda)

pgserver ships PostgreSQL **16**. If production runs another major version (15, 17…)
or you need extensions pgserver doesn't include (`pg_trgm`, `pgcrypto`, …), install
PostgreSQL with conda (no admin rights) and point the script at it:

```bash
conda install -c conda-forge postgresql=17
export PG_BIN_DIR="$CONDA_PREFIX/bin"
make db-reset          # a data directory is tied to one major version: start fresh
```

Everything else in this guide stays the same.

Next: [03 — The Python code, explained](03_python_code.md)
