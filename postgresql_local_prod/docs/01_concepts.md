# 01 — Concepts: what is going on, in plain words

Read this first if words like *server*, *port*, *connection URL*, *environment variable*
or *migration* feel fuzzy. Nothing to run here — just the mental model that makes
every later command obvious.

**Learning path:** **01 Concepts** → [02 Local database](02_local_database.md) →
[03 Python code](03_python_code.md) → [04 Migrations](04_migrations.md) →
[05 Remote database](05_remote_database.md) · [06 Troubleshooting](06_troubleshooting.md)

---

## 1. A database is a *program that runs*, not a file

With SQLite or a CSV, "the database" is a file that your Python code opens directly.
PostgreSQL is different: it is a **server** — a program running in the background,
waiting for **clients** to connect and send SQL.

```
   CLIENTS (they talk)                                   SERVER (it stores and answers)
 ┌────────────────────┐
 │ your Python code   │──┐
 └────────────────────┘  │     network connection    ┌──────────────────────────────┐
 ┌────────────────────┐  │     (host + port)         │  PostgreSQL server process   │
 │ Atlas (migrations) │──┼──────────────────────────▶│                              │
 └────────────────────┘  │                           │  reads/writes its files in   │
 ┌────────────────────┐  │                           │  a "data directory"          │
 │ psql (SQL console) │──┘                           └──────────────────────────────┘
 └────────────────────┘
```

Consequences you will meet:

- The server must be **started** before anything can connect (`make db-start`), and it
  keeps running until **stopped** (`make db-stop`) or until your computer restarts.
- Several clients can be connected **at the same time** (your script, Atlas, `psql`).
- The data lives in the server's **data directory** (locally: `.pgdata/`). You never
  edit those files yourself — you always go through the server.

## 2. Local vs remote: the same software, a different address

| | Local database | Remote database |
|---|---|---|
| Where the server runs | On your laptop | On another machine (company server, cloud) |
| Address (**host**) | `127.0.0.1` (= "this computer") | e.g. `db.company.com` |
| **Port** (door number on that host) | `5433` (our choice) | usually `5432` (PostgreSQL default) |
| Who owns it | You. Break it, reset it, no one cares | Shared. Real data, real users |
| Encryption (TLS) | Not needed (nothing leaves your laptop) | Required (data crosses a network) |
| Your rights | Superuser: you can do anything | Limited user(s), given by an admin |
| Purpose | Develop, experiment, **fail safely** | Run the real thing |

**The key idea of this folder:** both are *real PostgreSQL*. Your code cannot tell them
apart. The only thing that changes is the **address** you give it.

> Why not Docker? Normally you would run PostgreSQL in a Docker container. Here Docker
> isn't available, so [`local_server.py`](../local_server.py) runs real PostgreSQL
> programs that were installed by `pip install pgserver` — no admin rights needed.

## 3. Inside a server: databases, schemas, tables

```
server  (127.0.0.1:5433)
├── database  app            <- your application's data
│   ├── schema  public
│   │   ├── table  customers
│   │   └── table  sales_orders
│   └── schema  atlas_schema_revisions
│       └── table  atlas_schema_revisions   <- Atlas's notebook: "which migrations ran here"
├── database  atlas_dev      <- EMPTY scratch database Atlas uses for calculations
└── database  postgres       <- default admin database, ignore it
```

- A **database** is an isolated container; a connection always targets exactly one.
- A **schema** is a folder inside a database (`public` is the default one).
- A **table** has columns (with types and rules) and rows (the data).

## 4. The connection URL: one line that says *where* and *who*

Every client needs the same information, packed into one URL:

```
postgres://postgres:localdev@127.0.0.1:5433/app?sslmode=disable
└──┬───┘   └──┬───┘ └──┬───┘ └───┬───┘ └┬─┘ └┬┘ └──────┬──────┘
 scheme      user  password    host    port  db      options
```

| Part | Meaning | Local | Remote example |
|---|---|---|---|
| user / password | who you are | `postgres` / `localdev` | `app_user` / given by the admin |
| host | which machine | `127.0.0.1` | `db.company.com` |
| port | which door on that machine | `5433` | `5432` |
| db | which database in the server | `app` | `app` |
| `sslmode` | encrypt the connection? | `disable` | `require` or `verify-full` |

> If the password contains `@ : / # ? %`, it must be *URL-encoded*, otherwise the URL
> is misread (see [05](05_remote_database.md#step-2--build-the-connection-url)).

## 5. Environment variables: how the URL reaches the code

The URL contains a password, and it differs between local and remote. So it is **never
written in the code**. Instead, it is put in an **environment variable** — a named value
that your terminal passes to every program it starts.

```bash
export DATABASE_URL='postgres://...'   # set it in THIS terminal
echo "$DATABASE_URL"                   # show it
python demo.py                         # demo.py reads os.environ["DATABASE_URL"]
unset DATABASE_URL                     # remove it
```

Things beginners trip on:

- A variable lives **only in the terminal where you set it**. A new terminal tab starts
  without it.
- `eval "$(python local_server.py env)"` = "run the command, and execute what it prints".
  It prints `export DATABASE_URL=...` lines, so after `eval` your terminal has them set.
- Whatever `DATABASE_URL` holds decides **which database you are touching**. Always know
  where you point — `python check_connection.py` tells you.

This project uses three variables:

| Variable | Used by | Meaning |
|---|---|---|
| `DATABASE_URL` | Python code **and** Atlas | the database to work on |
| `ATLAS_DEV_URL` | Atlas only | an **empty** scratch database (always the local `atlas_dev`) |
| `APP_ENV` | Python code | `local` or `prod`; `prod` enables safety checks (TLS required) |

## 6. How Python talks to PostgreSQL: a stack of layers

```
 Polars / pandas DataFrame        you work here
          │
 SQLAlchemy  (engine, pool)       manages connections, sends SQL safely
          │
 psycopg 3  ("driver")            speaks PostgreSQL's network protocol
          │   network (host:port)
 PostgreSQL server                runs the SQL, returns rows
```

You will see two spellings of the URL: `postgres://...` (understood by Atlas, psql and
psycopg) and `postgresql+psycopg://...` (SQLAlchemy's way to say "PostgreSQL, using the
psycopg driver"). [`config.py`](../config.py) converts one into the other, so you only
ever set `postgres://...`.

## 7. Schema vs data, and why we need *migrations*

- **Data** = rows. Your code adds and changes them all day (`INSERT`, `UPDATE`, …).
- **Schema** = the structure: which tables, columns, types, rules (`CREATE TABLE`,
  `ALTER TABLE`, …).

The schema must be **identical** on your laptop, your colleague's laptop and production.
Changing it by hand ("I'll just run an `ALTER TABLE` on prod") is how databases drift
apart and break. So schema changes are written as **migration files**: small, numbered
SQL scripts, committed to git, applied **in order**, **once**, on **every** database.

```
migrations/
  20261008195351_init.sql           creates the tables
  20261009101500_add_discount.sql   adds a column
  20261012093000_add_status_check.sql
```

Each database remembers which files it already ran (table `atlas_schema_revisions`),
so applying is always "run the ones that are missing".

## 8. Atlas: the tool that writes and applies migrations

Atlas is a command-line program (not a Python package). You use it in two ways:

1. **You describe the schema you want** in [`atlas/schema.pg.hcl`](../atlas/schema.pg.hcl)
   ("table `sales_orders` has a column `discount`").
2. **Atlas writes the migration** (`atlas migrate diff`): it compares "what the existing
   migration files produce" with "what the HCL describes" and writes the SQL for the
   difference. To do this it *replays* the files in the empty scratch database
   (`ATLAS_DEV_URL`) — that's why `atlas_dev` must exist and stay empty.
3. **Atlas applies migrations** (`atlas migrate apply`) to the database in `DATABASE_URL`,
   running only the files not yet recorded there.

```
 schema.pg.hcl ──(migrate diff, uses atlas_dev)──▶ new file in migrations/
                                                          │
                                   (migrate apply) ───────┼──▶ local database   (first)
                                                          └──▶ remote database  (later, same files)
```

The configuration that tells Atlas where things are is [`atlas/atlas.hcl`](../atlas/atlas.hcl):
an environment named `local` and one named `prod`, both reading `DATABASE_URL`.

## 9. Transactions: all or nothing

A **transaction** groups several SQL statements so that either **all** succeed or
**none** happen. PostgreSQL can even undo table changes (`ALTER TABLE`) this way.
Atlas runs each migration file in a transaction, so a failing migration leaves the
database exactly as it was before — which is what makes "try it and fail" safe.

## 10. Glossary

| Term | Meaning |
|---|---|
| **Server / instance / cluster** | The running PostgreSQL program and its data directory |
| **Client** | Any program connecting to the server (Python, Atlas, psql) |
| **Host / port** | Machine address / door number where the server listens |
| **Role / user** | An account on the server (`postgres`, `app_user`, `migrator`) |
| **Superuser** | A role allowed to do everything (you, locally) |
| **DDL** | SQL that changes structure: `CREATE`, `ALTER`, `DROP` |
| **DML** | SQL that changes rows: `INSERT`, `UPDATE`, `DELETE` |
| **Migration** | A versioned SQL file that changes the schema |
| **Dev database** | Empty scratch database Atlas uses to compute SQL (`atlas_dev`) |
| **Rehearsal** | Applying pending migrations to a *copy* of the remote database first |
| **TLS / sslmode** | Encryption of the connection; mandatory for remote databases |
| **psql** | PostgreSQL's interactive SQL console (`make db-psql`) |

Next: [02 — Run your local database](02_local_database.md)
