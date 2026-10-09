# 05 — Working with the remote database

You've built and tested everything locally. This page takes you, step by step, from
"someone gave me access to a remote PostgreSQL" to "my migrations and scripts run on
it", and back to local — without ever confusing the two.

**Learning path:** [01 Concepts](01_concepts.md) → [02 Local database](02_local_database.md) →
[03 Python code](03_python_code.md) → [04 Migrations](04_migrations.md) →
**05 Remote database** · [06 Troubleshooting](06_troubleshooting.md)

> **No remote database yet?** Practise everything on this page with the *fake prod*
> (a second local server): `make fake-prod-start`, then use
> `postgres://postgres:localdev@127.0.0.1:5434/app?sslmode=disable` as the remote URL.
> The outputs below come from exactly that setup, configured like a real remote
> (separate users, no superuser).

---

## What changes, what doesn't

| | Local | Remote |
|---|---|---|
| Code (`*.py`), migrations (`atlas/`) | same | same |
| `DATABASE_URL` | printed by `make -s db-env` | **you build it** from what the admin gives you |
| Where the URL is kept | nowhere (generated on demand) | a **private** `.env.*` file or a secret manager — never git |
| Users | `postgres` superuser for everything | **two users**: `migrator` (Atlas) and `app_user` (your code) |
| Encryption | `sslmode=disable` | `sslmode=require` (or `verify-full`) |
| `APP_ENV` | `local` | `prod` → TLS enforced, `demo.py` refuses to delete data |
| Make targets | `make migrate-*`, `make db-*` | `make migrate-*-prod`, `make check-prod` |
| Starting/stopping the server | you (`make db-start`) | not your job — it's always on |
| Mistakes | `make db-reset`, nobody notices | real data, real users: **rehearse first** ([04](04_migrations.md#part-6--fail-during-rehearsal-a-constraint-that-only-prod-data-violates)) |

---

## Step 1 — Ask for the right information

Send this to whoever runs the remote database (DBA, platform team, cloud console):

> Hello, for project X I need access to a PostgreSQL database. Could you give me:
> 1. **host** and **port**
> 2. **database name**
> 3. two users, ideally created with [`remote_roles.sql`](../remote_roles.sql):
>    `migrator` (owns the tables, used only to run migrations) and `app_user`
>    (read/write rows only, used by the application) — and their passwords
> 4. the **SSL/TLS** requirement (`require`? `verify-full` + CA certificate file?)
> 5. **how to reach it** from my laptop: VPN? IP allow-list?
> 6. the **PostgreSQL version** and the **extensions** available
> 7. optionally a **read-only** user, to copy the schema for rehearsals

Why two users? Your Python code runs all day with `app_user`; it **cannot** `DROP`
or `ALTER` anything, so a bug or a leaked password can't destroy the schema. Only
migrations — reviewed, rehearsed, run on purpose — use `migrator`. This was tested:

```
-- as app_user
CREATE TABLE hack (a int);      ERROR:  permission denied for schema public
DROP TABLE customers CASCADE;   ERROR:  must be owner of table customers
INSERT INTO customers ...;      INSERT 0 1        (reading/writing rows works)
```

---

## Step 2 — Build the connection URL

```
postgres://app_user:S3cr%40t@db.company.com:5432/app?sslmode=require
           └──user┘ └─pass─┘ └────host─────┘ └port┘ └db┘ └──TLS────┘
```

**Special characters in the password** (`@ : / # ? % &` and spaces) must be
*URL-encoded*, or the URL is misread. Encode it with Python:

```bash
python -c "from urllib.parse import quote; print(quote('S3cr@t', safe=''))"
# S3cr%40t
```

**`sslmode`** — how strictly to encrypt:

| Value | Encrypts? | Checks the server's identity? | Use |
|---|---|---|---|
| `disable` | no | no | local server only |
| `require` | yes | no | minimum for remote |
| `verify-ca` | yes | certificate signed by a trusted authority | better |
| `verify-full` | yes | + host name matches the certificate | best |

`verify-ca` / `verify-full` need the authority's certificate file, given by the admin:
`...?sslmode=verify-full&sslrootcert=/path/to/ca.pem`.

You get **two URLs**: one with `migrator`, one with `app_user`.

---

## Step 3 — Store the URLs safely

Copy the template, one file per user. The repository's `.gitignore` excludes `.env`
and `.env.*`, so these files can never be committed by accident.

```bash
cp env.example .env.prod             # the application user
cp env.example .env.prod-migrator    # the migration user
```

Edit each one — **keep the single quotes** (`&` or `#` in a URL would otherwise be
cut by the shell):

```bash
# .env.prod
DATABASE_URL='postgres://app_user:S3cr%40t@db.company.com:5432/app?sslmode=require'
APP_ENV='prod'
ATLAS_DEV_URL='postgres://postgres:localdev@127.0.0.1:5433/atlas_dev?sslmode=disable'
```

```bash
# .env.prod-migrator   (same, with the migrator user)
DATABASE_URL='postgres://migrator:An0ther%21@db.company.com:5432/app?sslmode=require'
APP_ENV='prod'
ATLAS_DEV_URL='postgres://postgres:localdev@127.0.0.1:5433/atlas_dev?sslmode=disable'
```

Load a file into the **current terminal**:

```bash
set -a; source .env.prod; set +a
#  set -a  = "export every variable defined from now on"
#  source  = run the file's lines in this terminal
#  set +a  = back to normal
```

> ✋ Never paste a remote password into a command line you share, a notebook you
> commit, or a chat. If a password leaks, ask for a new one.
> Companies often have a secret manager (Vault, AWS Secrets Manager, 1Password CLI…);
> the principle is the same — it fills `DATABASE_URL` for you.

---

## Step 4 — Check the connection (and compare with local)

Use a **dedicated terminal** for remote work (see [Step 8](#step-8--back-to-local-and-never-mixing-them-up)).

```bash
set -a; source .env.prod; set +a
make check-prod
```
```
APP_ENV      local                    <- fake prod has no TLS, see note below
URL          postgresql+psycopg://app_user:***@127.0.0.1:5434/app?sslmode=disable

-- server --------------------------------------------------
version      16.2
host:port    127.0.0.1:5434
database     app
user         app_user
TLS          off                      <- a real remote must say "on"

-- settings that change query results ---------------------
timezone     UTC
collation    C

-- rights --------------------------------------------------
superuser    False
can create tables in public: False  (only the migration user needs this)

-- extensions ----------------------------------------------
installed    plpgsql 1.0

-- atlas ---------------------------------------------------
applied      1 migration(s), latest version 20261008195351

OK — connected. Python code and Atlas will connect the same way.
```

(Output from the fake prod. It has no TLS, so when practising put `APP_ENV='local'`
in the env file: with `APP_ENV='prod'` and `sslmode=disable` the configuration is
refused — by design:
`ValueError: APP_ENV=prod requires sslmode in ['require', 'verify-ca', 'verify-full'], got 'disable'`.
On a real remote, keep `APP_ENV='prod'`, and `TLS` says `on`.)

**Compare with `make db-check` (local)** — differences here are differences in behaviour:

| Line | If local and remote differ… |
|---|---|
| `version` major (16 vs 17) | SQL that works locally may not work remotely. Match it: [02 — conda](02_local_database.md#using-a-different-postgresql-version-conda) |
| `timezone` | timestamps shown/parsed differently. Use `timestamptz` columns and UTC everywhere |
| `collation` | text sorts differently (`ORDER BY name`), `C` vs `en_US.UTF-8`. Set `LOCAL_PG_LOCALE` to the remote value and `make db-reset` |
| `extensions` | a migration with `CREATE EXTENSION x` fails where `x` isn't available. pgserver only has `plpgsql` and `vector` |

Connection failed? The script explains the most common causes (VPN, firewall, password,
TLS) — see also [06 Troubleshooting](06_troubleshooting.md#connecting-to-a-remote-database).

---

## Step 5 — Bring the remote schema up to date (migrations)

Migrations need the **migrator** URL. The whole procedure — with rehearsal on a copy
first — is in [04, Parts 5–7](04_migrations.md#part-7--apply-to-production). In short:

```bash
set -a; source .env.prod-migrator; set +a

make migrate-status-prod
```
```
Migration Status: PENDING
  -- Current Version: No migration applied yet     <- brand-new database
  -- Next Version:    20261008195351
  -- Executed Files:  0
  -- Pending Files:   1
```
```bash
SOURCE_URL="$DATABASE_URL" make rehearse    # copy remote schema locally, apply there first
make migrate-plan-prod                      # print the SQL, run nothing
make migrate-apply-prod                     # run it for real
make migrate-status-prod
```
```
Migration Status: OK
  -- Current Version: 20261008195351
  -- Next Version:    Already at latest version
  -- Executed Files:  1
  -- Pending Files:   0
```

> `rehearse` replaces your **local** `app` database with the copy (the remote is only
> read). Afterwards `make db-reset && make migrate-apply && make demo` restores your
> usual local data.

The remote **already has tables** that weren't created by Atlas? Don't apply `init` on
top of them — adopt them with a *baseline*: [04 Part 9](04_migrations.md#part-9--production-database-that-predates-atlas-baseline).

---

## Step 6 — Run your Python code against the remote

With the **app_user** URL, the same scripts run unchanged:

```bash
set -a; source .env.prod; set +a
python example_script.py
```
```
Connected to: postgresql+psycopg://app_user:***@db.company.com:5432/app?sslmode=require
shape: (5, 3)
…
Inserted 2 new customer(s)
```

Habits for remote runs:

- **Read the `Connected to:` line** before anything else. Wrong place? `Ctrl+C`.
- Try new scripts locally first, then remotely on a **small** scope (a `LIMIT`, one day of data).
- Make writes **re-runnable** (`ON CONFLICT DO NOTHING`, skip existing ids) — network
  hiccups happen, and re-running must not duplicate rows.
- `demo.py` is a local tool: with `APP_ENV=prod` it stops before deleting anything.

---

## Step 7 — Graphical tools and notebooks

- **DBeaver / DataGrip / pgAdmin / VS Code**: same host, port, database, user, password
  as in the URL; enable SSL ("require"), add the CA file for `verify-full`.
- **Jupyter**: start Jupyter *from a terminal where you loaded the env file*, then in a cell:
  ```python
  from client import PostgresClient
  from config import PgConfig
  client = PostgresClient(PgConfig.from_env())
  print(client.cfg.safe_url())
  ```
  Never write the URL in a notebook cell: notebooks get committed and shared.

---

## Step 8 — Back to local, and never mixing them up

A terminal keeps its variables until it closes. The simplest rule:

> **One terminal (or tab) per target.** Name the remote tab "PROD".

To switch a terminal back to local:

```bash
unset DATABASE_URL APP_ENV ATLAS_DEV_URL SOURCE_URL
eval "$(make -s db-env)"
make db-check          # says 127.0.0.1:5433, user postgres
```

Built-in safety nets:

| Net | Protects against |
|---|---|
| `make migrate-*` (no `-prod`) always loads the **local** URL itself | migrating prod when you meant local |
| `make *-prod` refuse to run without `DATABASE_URL` | running "prod" commands with nothing configured |
| `APP_ENV=prod` requires TLS | sending prod passwords/data unencrypted |
| `app_user` has no DDL rights | a script dropping or altering tables |
| `demo.py` stops when `APP_ENV=prod` | truncating real tables |

---

## Step 9 — Automating it (CI/CD), optional

Once the manual flow is familiar, a pipeline can run it on every merge. The pipeline
machine needs no Docker either: it starts the local server for Atlas's scratch
database and for the rehearsal. **An example to adapt** (GitHub Actions):

```yaml
# .github/workflows/migrations.yml
name: migrations
on:
  push:
    branches: [main]
jobs:
  migrate:
    runs-on: ubuntu-latest
    environment: production          # require a manual approval in the repo settings
    defaults:
      run:
        working-directory: postgresql_local_prod
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: curl -sSf https://atlasgo.sh | sh
      - run: make db-start                         # local server = Atlas scratch DB + rehearsal target
      - run: make migrate-validate                 # files intact, replay OK
      - run: make rehearse                         # copy prod schema, apply pending migrations to the copy
        env:
          SOURCE_URL: ${{ secrets.PROD_READONLY_URL }}
      - run: make migrate-plan-prod migrate-apply-prod migrate-status-prod
        env:
          DATABASE_URL: ${{ secrets.PROD_MIGRATOR_URL }}
          ATLAS_DEV_URL: postgres://postgres:localdev@127.0.0.1:5433/atlas_dev?sslmode=disable
```

The secrets are stored in the CI system, never in the repository.

---

## Local ↔ remote parity checklist

| Check | Why it matters | How |
|---|---|---|
| **Same major version** | syntax and behaviour differ between 14/15/16/17 | `version` in `check_connection.py`; match with conda via `PG_BIN_DIR` |
| **Extensions** | pgserver has only `plpgsql` and `vector` — no `pgcrypto`, `pg_trgm`, `uuid-ossp`, `citext`… | create them in a migration (`CREATE EXTENSION IF NOT EXISTS …`); conda/Homebrew locally if you need contrib. `gen_random_uuid()` is built in since PG 13 |
| **Users & rights** | locally superuser, remotely not | test scripts with an `app_user`-like role on the fake prod ([`remote_roles.sql`](../remote_roles.sql)) |
| **TLS** | local is unencrypted | `APP_ENV=prod` enforces `sslmode` |
| **Timezone** | local is UTC | `timestamptz` + UTC remotely too |
| **Collation** | text sorting, `LIKE`, unique text indexes | compare `collation` lines; `LOCAL_PG_LOCALE` + `make db-reset` |
| **Connection pooler** (PgBouncer) | transaction pooling breaks session state and prepared statements | keep `pool_pre_ping=True`; with PgBouncer add `"prepare_threshold": None` to `connect_args` in `client.py` |
| **Data volume** | fast on 200k rows, slow on 200M | rehearse with data, read the timings, `EXPLAIN (ANALYZE, BUFFERS)` |

Next: [06 — Troubleshooting](06_troubleshooting.md)
