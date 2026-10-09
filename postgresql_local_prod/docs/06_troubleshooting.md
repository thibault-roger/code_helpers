# 06 — Troubleshooting

Find your error message below (use your browser's search). Most messages are quoted
exactly as you will see them.

**Learning path:** [01 Concepts](01_concepts.md) → [02 Local database](02_local_database.md) →
[03 Python code](03_python_code.md) → [04 Migrations](04_migrations.md) →
[05 Remote database](05_remote_database.md) · **06 Troubleshooting**

**First reflex, always:** `make db-check` (local) or `make check-prod` (remote). It tells
you where you are connected and translates connection errors.

---

## The local server

| Message / symptom | Why | Fix |
|---|---|---|
| `pgserver is not installed: pip install pgserver, or set PG_BIN_DIR.` | the virtual environment isn't active, or packages not installed | `source .venv/bin/activate` then `pip install -r requirements.txt` |
| `Connection refused` on `127.0.0.1:5433` | the server isn't running (e.g. after a reboot) | `make db-start` |
| `could not bind IPv4 address "127.0.0.1": Address already in use` (in `.pgdata/server.log`) | another program uses port 5433 | `LOCAL_PG_PORT=5440 make db-reset` (5434 is used by the fake prod) |
| server won't start after a crash / power loss | a stale lock file | read `.pgdata/server.log`; if no `postgres` process runs (`ps aux \| grep postgres`), delete `.pgdata/postmaster.pid` and `make db-start` |
| `initdb: error: cannot be run as root` | PostgreSQL refuses to run as root (some containers / CI) | run as a normal user |
| `make: command not found` | `make` isn't installed | macOS: `xcode-select --install`; or run the commands from the [Makefile](../Makefile) by hand |
| `make db-psql` opens nothing / `psql: command not found` elsewhere | psql comes from pgserver, it's not on your PATH | always go through `make db-psql` |
| I want to start over | — | `make db-reset && make migrate-apply && make demo` |

---

## Connecting to a remote database

`check_connection.py` prints a *Likely cause* for these:

| Message | Likely cause | Fix |
|---|---|---|
| `connection timeout expired` | the host doesn't answer: VPN off, firewall, IP not allow-listed | connect the VPN; ask the admin to allow your IP |
| `failed to resolve host 'db…'` / `could not translate host name` | typo in the host, or company DNS needs the VPN | check the host; VPN |
| `Connection refused` | right machine, wrong port, or server down | check the port (often 5432) |
| `password authentication failed for user "…"` | wrong user/password, or special characters not URL-encoded | `python -c "from urllib.parse import quote; print(quote('p@ss', safe=''))"` |
| `database "…" does not exist` | wrong name after the last `/` in the URL | ask the exact database name |
| `no pg_hba.conf entry for host …` | the server refuses this user / IP / unencrypted connection | try `sslmode=require`; otherwise the admin must allow you |
| `server does not support SSL, but SSL was required` | `sslmode=require` against a server without TLS (e.g. your local one) | local: `sslmode=disable` |
| certificate errors with `verify-full` | missing / wrong CA file | add `&sslrootcert=/path/to/ca.pem` to the URL |
| `permission denied for schema …` / `permission denied for table …` | you're connected as a user without rights for that action (e.g. `app_user` running a migration) | migrations: use the **migrator** URL; otherwise ask for the grant |
| the URL looks cut off after `&` or `#` | the env file value isn't quoted | `DATABASE_URL='…'` with single quotes |

---

## Python

| Message | Why | Fix |
|---|---|---|
| `RuntimeError: No database configured.` | no `DATABASE_URL` in this terminal | local: `eval "$(make -s db-env)"`; remote: `set -a; source .env.prod; set +a` |
| `ValueError: APP_ENV=prod requires sslmode in [...], got 'disable'` | prod settings with an unencrypted URL | add `sslmode=require` (real remote) or `APP_ENV='local'` (fake prod) |
| `LookupError: public.x does not exist. Add it to atlas/schema.pg.hcl…` | writing to a table no migration created — or migrations not applied on this database | create it via a migration ([04](04_migrations.md)); or `make migrate-apply` |
| `psycopg.errors.ForeignKeyViolation … violates foreign key constraint` | a row points to something that doesn't exist | load the parent rows first (e.g. customers before orders) |
| `psycopg.errors.CheckViolation` / `UniqueViolation` / `NotNullViolation` | a row breaks a table rule | fix the data; the whole write was cancelled (nothing half-written) |
| `ModuleNotFoundError: No module named 'config'` | script run from another folder | run from `postgresql_local_prod/` |
| my script modified the wrong database | `DATABASE_URL` pointed elsewhere | read the `Connected to:` line; one terminal per target ([05 Step 8](05_remote_database.md#step-8--back-to-local-and-never-mixing-them-up)) |

---

## Atlas / migrations

| Message | Why | Fix |
|---|---|---|
| `pq: column "x" of relation "y" contains null values` | new `NOT NULL` column on a table that has rows | add as NULL → backfill → `SET NOT NULL` ([04 Part 2](04_migrations.md#part-2--fail-locally-1-a-migration-that-only-breaks-on-real-rows)) |
| `pq: check constraint "x" … is violated by some row` | existing data breaks the new rule | fix the data or the rule ([04 Part 6](04_migrations.md#part-6--fail-during-rehearsal-a-constraint-that-only-prod-data-violates)) |
| `pq: CREATE INDEX CONCURRENTLY cannot run inside a transaction block` | file needs to run outside a transaction | first line `-- atlas:txmode none`, blank line, then `make migrate-hash` |
| `cannot set txmode directive to "none" in "…" when txmode "all" is set globally` | `--tx-mode all` with a `txmode none` file | apply without `--tx-mode all` |
| `You have a checksum error in your migration directory. … was edited` | a migration file changed after it was signed | deliberate, never-shipped file: `make migrate-hash`; otherwise undo your edit (`git checkout`) and write a new migration |
| `migration file … was added out of order` | a merged file is older than one already applied | `make migrate-rebase version=<that version>` |
| `migrate status` says OK but a merged file never ran | file older than **every** applied one is silently skipped | compare `Executed Files` with `ls atlas/migrations/*.sql \| wc -l`; `make migrate-rebase` |
| `connected database is not clean: found schema "public". baseline version or allow-dirty is required` | applying to a database that has tables but no Atlas history | existing remote: baseline ([04 Part 9](04_migrations.md#part-9--production-database-that-predates-atlas-baseline)); local: `make db-reset` |
| `migrate diff` complains the dev database is not clean | something wrote into `atlas_dev`, which must stay empty | `make db-reset` |
| `check assertion "SELECT NOT EXISTS (…)" returned false` on `migrate down` | reverting would delete data, Atlas refuses | `make db-reset && make migrate-apply`, or write a new migration |
| `migration file add_x not found` with `migrate rm` | `rm` wants the **version** (the number) | `make migrate-rm version=20261008200057` |
| next `migrate diff` generates a `DROP …` you didn't ask for | a hand-written migration isn't reflected in `schema.pg.hcl` | delete that file (`make migrate-rm`), describe the object in the HCL, diff again → *synced* |
| `'atlas migrate lint' is available only to Atlas Pro users` | lint is a paid feature since v0.38 | `make migrate-validate` (free), or `atlas login` |
| `This version will soon be deprecated` | old Atlas CLI | `brew upgrade atlas` or `curl -sSf https://atlasgo.sh \| sh` |

---

## Rehearsal (`make rehearse` / `make db-clone`)

| Message | Why | Fix |
|---|---|---|
| `Set SOURCE_URL to the database to copy` | no source given | `SOURCE_URL='postgres://…' make rehearse` |
| `pg_dump: error: aborting because of server version mismatch` | the remote runs a newer PostgreSQL than pgserver's 16 | install the matching version with conda, `PG_BIN_DIR=…` ([02](02_local_database.md#using-a-different-postgresql-version-conda)) |
| `Clone failed` after an error mentioning an extension | the remote uses an extension your local server doesn't have | same: conda/Homebrew PostgreSQL that includes it |
| my local data disappeared after `rehearse` | expected: rehearse **replaces** the local `app` database with the copy | `make db-reset && make migrate-apply && make demo` |

---

## Still stuck?

1. `make db-check` / `make check-prod` — where am I, as whom?
2. `make migrate-status` / `make migrate-status-prod` — which version is this database at?
3. Local server problems: read `.pgdata/server.log` (the end of the file).
4. Reset local and replay: `make db-reset && make migrate-apply && make demo`.
