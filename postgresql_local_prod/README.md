# PostgreSQL — Local (no Docker) → Remote / Production

Develop against a **real PostgreSQL server on your laptop** — no Docker, no admin
rights — then run **the same code and the same Atlas migrations** on a remote
(production) PostgreSQL. The only thing that changes between the two is one
environment variable: `DATABASE_URL`.

```
                 ┌──────────────── same code (config.py / client.py) ────────────────┐
 local laptop    │  DATABASE_URL=postgres://…@127.0.0.1:5433/app  ── PostgreSQL 16 (pip install pgserver)
 remote / prod   │  DATABASE_URL=postgres://…@db.company:5432/app ── PostgreSQL (company / cloud)
                 └─────────── same migrations (atlas/migrations/*.sql) ──────────────┘
```

---

## 📚 Learning path — start here

New to databases, PostgreSQL or migrations? Read in order; every step shows the real
output you should see.

| # | Guide | You will learn |
|---|---|---|
| 01 | [Concepts](docs/01_concepts.md) | server vs client, local vs remote, connection URLs, environment variables, migrations, Atlas — in plain words |
| 02 | [Your local database](docs/02_local_database.md) | install, start/stop/reset the local server, look inside with `psql`, load data — and what each command does under the hood |
| 03 | [The Python code](docs/03_python_code.md) | `config.py`, `client.py`, `demo.py` explained; write your own scripts that run locally *and* remotely |
| 04 | [Migrations](docs/04_migrations.md) | change the schema, **break migrations locally on purpose**, fix them, rehearse on a copy of the remote, ship to prod |
| 05 | [The remote database](docs/05_remote_database.md) | get access, build and store the URL safely, check the connection, migrate and run scripts remotely, switch back to local |
| 06 | [Troubleshooting](docs/06_troubleshooting.md) | every error message we met, and its fix |

---

## ⚡ Quick start (5 minutes)

```bash
cd postgresql_local_prod
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install ariga/tap/atlas         # or: curl -sSf https://atlasgo.sh | sh

make db-start          # start a real PostgreSQL on 127.0.0.1:5433 (first time: creates .pgdata/)
make db-check          # where am I connected? what does the server look like?
make migrate-apply     # create the tables from atlas/migrations/
make demo              # load 200k fake orders, query them
make db-psql           # SQL console (\dt to list tables, \q to quit)
make db-stop           # stop the server — data is kept
```

Then, against a remote database ([guide 05](docs/05_remote_database.md)):

```bash
cp env.example .env.prod            # fill in the remote URL (never committed)
set -a; source .env.prod; set +a    # load it in this terminal
make check-prod                     # connect + compare with local
python example_script.py            # same script as locally
```

---

## Why a real PostgreSQL locally — and which one?

Atlas generates **PostgreSQL-specific** SQL and needs a PostgreSQL "dev database" to
compute it. A stand-in like SQLite or DuckDB would force a second set of migrations
that production never runs, and would behave differently (types, constraints, SQL
functions). So the local database must be real PostgreSQL. Docker-free options:

| Option | Real PostgreSQL? | Install | Admin rights | Works with Atlas | When to use |
|---|---|---|---|---|---|
| **pgserver** (`pip install pgserver`) — *default here* | ✅ PG 16.2 in a pip wheel | pip | No | ✅ | default: zero friction, lives in your venv |
| **conda-forge `postgresql`** | ✅ any major version | `conda install -c conda-forge postgresql=17` | No | ✅ | match prod's major version, or need contrib extensions |
| **Homebrew / Postgres.app / EDB installer** | ✅ | system installer | usually yes | ✅ | your machine allows it |
| **PGlite** (`py-pglite`, Postgres compiled to WASM) | ✅ (in-memory) | pip + Node.js | No | ⚠️ single connection — unreliable for Atlas | fast throw-away DBs in unit tests only |
| **SQLite / DuckDB** | ❌ other engines | pip | No | ❌ different dialect | not a PostgreSQL stand-in |

[`local_server.py`](local_server.py) works with the first three: it only needs the
`initdb` / `pg_ctl` / `psql` programs (pgserver's by default, or any folder given in
`PG_BIN_DIR`). It runs the server on TCP `127.0.0.1` with password authentication and
UTC — the same connection shape as a remote server. Details: [guide 02](docs/02_local_database.md).

---

## 🗂 What's in this folder

| File | What it is | Explained in |
|---|---|---|
| [`Makefile`](Makefile) | short commands: `db-*` (local server), `migrate-*` (local migrations), `*-prod` (remote), `rehearse`, `fake-prod-*` | every guide |
| [`local_server.py`](local_server.py) | start / stop / reset the local PostgreSQL, print its URLs, clone a remote DB for rehearsals | [02](docs/02_local_database.md), [03](docs/03_python_code.md#local_serverpy--the-local-servers-remote-control) |
| [`config.py`](config.py) | reads `DATABASE_URL` / `APP_ENV` — the local/remote switch | [03](docs/03_python_code.md#configpy--where-am-i-connecting) |
| [`client.py`](client.py) | `PostgresClient`: Polars/pandas reads, streaming, fast COPY writes | [03](docs/03_python_code.md#clientpy--talking-to-the-database) |
| [`check_connection.py`](check_connection.py) | "can I connect, and what's there?" with human-readable error hints | [02](docs/02_local_database.md#step-2--is-it-running-can-i-connect), [05](docs/05_remote_database.md#step-4--check-the-connection-and-compare-with-local) |
| [`example_script.py`](example_script.py) | template for your own scripts (local and remote) | [03](docs/03_python_code.md#example_scriptpy--the-template-for-your-scripts) |
| [`demo.py`](demo.py) | loads fake data and exercises every client method (local only) | [03](docs/03_python_code.md#demopy--the-guided-tour-local-only) |
| [`atlas/atlas.hcl`](atlas/atlas.hcl) | Atlas environments `local` and `prod` | [04](docs/04_migrations.md#before-you-start-the-atlas-toolbox) |
| [`atlas/schema.pg.hcl`](atlas/schema.pg.hcl) | the schema you want (source of truth) | [04](docs/04_migrations.md#before-you-start-the-atlas-toolbox) |
| [`atlas/migrations/`](atlas/migrations/) | versioned SQL + `atlas.sum` fingerprints (commit them) | [04](docs/04_migrations.md) |
| [`remote_roles.sql`](remote_roles.sql) | the two users to create on a remote database (`migrator`, `app_user`) | [05](docs/05_remote_database.md#step-1--ask-for-the-right-information) |
| [`env.example`](env.example) | template for the remote settings file (`.env.prod`, git-ignored) | [05](docs/05_remote_database.md#step-3--store-the-urls-safely) |
| [`requirements.txt`](requirements.txt) | Python dependencies | [02](docs/02_local_database.md#step-0--one-time-installation) |

---

## The golden rules

1. **Configuration comes from the environment**, never from the code: `DATABASE_URL`, `APP_ENV`.
2. **Tables are created and changed only by Atlas migrations** — never from Python.
3. **Break things locally first**, with data in the tables; `make db-reset` is free.
4. **Rehearse on a copy of the remote** before migrating it (`make rehearse`).
5. **Two remote users:** `migrator` for migrations, `app_user` for code.
6. **Always know where you are connected:** `make db-check` / `make check-prod`.
