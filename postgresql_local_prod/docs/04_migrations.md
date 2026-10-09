# 04 — Migrations: break them locally, ship them safely

**Learning path:** [01 Concepts](01_concepts.md) → [02 Local database](02_local_database.md) →
[03 Python code](03_python_code.md) → **04 Migrations** →
[05 Remote database](05_remote_database.md) · [06 Troubleshooting](06_troubleshooting.md)

Goal: every schema change is **written, applied, broken and fixed on your laptop**,
then **rehearsed on a copy of the remote database**, and only then applied to
production — where it should be boring.

```
 schema.pg.hcl ──diff──▶ migrations/*.sql ──▶ ① LOCAL DB          (with data — break things here)
   (you edit)            (Atlas writes,       ② REHEARSAL         (copy of remote — catch prod-only surprises)
                          you review)         ③ PROD              (dry-run, apply, status)
```

Every output below was captured from real runs of this folder's tooling.
Commands run from `postgresql_local_prod/`. New to migrations? Read
[01 Concepts §7–9](01_concepts.md#7-schema-vs-data-and-why-we-need-migrations) first.

---

## Before you start: the Atlas toolbox

### The four things Atlas works with

```
atlas/
├── atlas.hcl          ① WHERE: which databases ("environments") Atlas talks to
├── schema.pg.hcl      ② WHAT: the schema you want (you edit this)
└── migrations/        ③ HOW: the SQL steps to get there (Atlas writes, you review, git keeps)
    ├── 20261008195351_init.sql
    └── atlas.sum      ④ fingerprints of every file, to detect tampering
```

…plus, **inside every database**, the table `atlas_schema_revisions` where Atlas notes
which files already ran there.

**① [`atlas.hcl`](../atlas/atlas.hcl)** defines two environments. You pick one with
`--env` (the Makefile does it for you):

```hcl
env "local" {
  src = "file://schema.pg.hcl"      # the desired schema (only needed to generate migrations)
  url = getenv("DATABASE_URL")      # the database to migrate
  dev = getenv("ATLAS_DEV_URL")     # the EMPTY scratch database
  migration { dir = local.migrations }
}
env "prod" {
  url = getenv("DATABASE_URL")      # same files, different database
  dev = getenv("ATLAS_DEV_URL")
  migration { dir = local.migrations }
}
```

Both read `DATABASE_URL`: **the environment variable decides which database is
migrated.** The Makefile protects you: `make migrate-*` targets always load the *local*
URL first; only `make *-prod` targets use whatever `DATABASE_URL` your terminal holds.

**② [`schema.pg.hcl`](../atlas/schema.pg.hcl)** describes tables in Atlas's HCL language.
A cheat sheet of what you can write, and the SQL it becomes:

| HCL | Meaning / SQL |
|---|---|
| `table "customers" { schema = schema.public … }` | `CREATE TABLE public.customers` |
| `column "email" { type = varchar(320) }` | a column. Other types: `integer`, `bigint`, `text`, `numeric(10, 2)`, `boolean`, `date`, `timestamptz`, `jsonb` |
| `null = false` | `NOT NULL` (value required) |
| `default = "pending"` / `default = false` | a fixed default value |
| `default = sql("now()")` | a default computed by PostgreSQL |
| `comment = "…"` | documentation stored in the database |
| `primary_key { columns = [column.order_id] }` | the unique identifier of a row |
| `index "x_idx" { columns = [column.order_date] }` | speeds up searches on that column |
| `index "x_key" { unique = true  columns = [...] }` | no two rows may share the value |
| `foreign_key "fk" { columns = [column.customer_id]  ref_columns = [table.customers.column.customer_id] }` | each order must point to an existing customer |
| `check "name" { expr = "amount >= 0" }` | a rule every row must satisfy |

**③ Migration files** are named `<version>_<name>.sql`. The version is a timestamp
(when the file was created): files run in that order. Open them, they're plain SQL.

**④ `atlas.sum`** holds a fingerprint of each file. Edit a file and Atlas notices:
`You have a checksum error in your migration directory`. That's protection against
accidental edits; `make migrate-hash` re-signs after a *deliberate* edit.

### The commands, and which database each one touches

| Make target | Atlas command | What it does | Database touched |
|---|---|---|---|
| `make migrate-diff name=x` | `migrate diff x` | compares HCL vs migration files, **writes a new file** | `atlas_dev` (scratch) only |
| `make migrate-new name=x` | `migrate new x` | creates an **empty** file for hand-written SQL | none |
| `make migrate-hash` | `migrate hash` | re-signs `atlas.sum` after an edit | none |
| `make migrate-validate` | `migrate validate` | checks fingerprints + replays all files on the scratch DB | `atlas_dev` only |
| `make migrate-status` | `migrate status` | lists what's applied / pending | local `app` (read) |
| `make migrate-apply` | `migrate apply` | runs pending files | local `app` |
| `make migrate-down` | `migrate down` | reverts the last file(s) | local `app` |
| `make migrate-rm version=v` | `migrate rm v` | deletes a file + updates `atlas.sum` | none |
| `make migrate-status-prod` | `migrate status --env prod` | what's applied / pending remotely | **`$DATABASE_URL`** (read) |
| `make migrate-plan-prod` | `migrate apply --dry-run` | prints the SQL that *would* run | **`$DATABASE_URL`** (read) |
| `make migrate-apply-prod` | `migrate apply --env prod` | runs pending files | **`$DATABASE_URL`** ⚠ |

### Reading `migrate status`

```
Migration Status: PENDING                  OK = up to date, PENDING = files waiting
  -- Current Version: 20261008195351       last file applied on this database
  -- Next Version:    20261008200046       first file that would run
  -- Executed Files:  1                    how many files this database has run
  -- Pending Files:   1                    how many are waiting
```

### Reading `migrate apply`

```
Migrating to version 20261008200046 from 20261008195351 (1 migrations in total):
  -- migrating version 20261008200046                 <- one file…
    -> ALTER TABLE "public"."sales_orders" ADD …;     <- …each statement it runs
  -- ok (3.4ms)                                       <- file committed (or an error line: pq: …)
  -------------------------
  -- 1 migration                                       <- summary
  -- 2 sql statements
```

A line starting with `pq:` is PostgreSQL's error message: read it, it says what's wrong.

---

## The 6 rules

1. **`schema.pg.hcl` is the source of truth.** Change it, then `make migrate-diff`. Hand-written
   migrations are allowed (data backfills, `CONCURRENTLY`), but the HCL must still describe the result.
2. **A migration file is editable until it has been applied anywhere other than your own
   local database.** After that it is frozen: fix things with a *new* migration.
3. **Always test on data, not on an empty database.** `migrate validate` replays files on an
   *empty* dev DB — it cannot see rows that violate a new constraint.
4. **Rehearse on a copy of the remote before applying to it** (`make rehearse`).
5. **Production only ever runs `migrate apply`** of committed, reviewed files — after a `--dry-run`.
6. **Never roll back production with `migrate down`; roll forward** with a new migration.

---

## Part 0 — Setup

If you followed [02](02_local_database.md) you're ready. Otherwise:

```bash
pip install -r requirements.txt          # + Atlas CLI: brew install ariga/tap/atlas
make db-start                            # local server on 127.0.0.1:5433
make migrate-apply                       # schema at the latest committed version
make demo                                # load 200k synthetic rows: migrations must survive data
```

---

## Part 1 — The happy path: add a column

Edit `atlas/schema.pg.hcl`, inside `table "sales_orders"`:

```hcl
  column "discount" {
    type    = numeric(10, 2)
    null    = true
    comment = "Discount applied to the order"
  }
```

Generate the migration and **read it** — Atlas writes SQL, you own it:

```bash
make migrate-diff name=add_discount
cat atlas/migrations/*_add_discount.sql
```
```sql
-- Modify "sales_orders" table
ALTER TABLE "public"."sales_orders" ADD COLUMN "discount" numeric(10,2) NULL;
-- Set comment to column: "discount" on table: "sales_orders"
COMMENT ON COLUMN "public"."sales_orders"."discount" IS 'Discount applied to the order';
```

```bash
make migrate-status     # Migration Status: PENDING  -- Pending Files: 1
make migrate-apply      # -- ok ... -- 1 migration -- 2 sql statements
make demo               # your application code still works
```

Commit `schema.pg.hcl`, the new `.sql` file **and** `atlas.sum` together.

---

## Part 2 — Fail locally #1: a migration that only breaks on real rows

Add a mandatory column:

```hcl
  column "channel" {
    type    = varchar(20)
    null    = false
    comment = "Sales channel: web, store, phone"
  }
```

```bash
make migrate-diff name=add_channel
make migrate-validate      # migrations valid   <- passes! (empty dev database)
make migrate-apply
```
```
-- migrating version 20261008200057
  -> ALTER TABLE "public"."sales_orders" ADD COLUMN "channel" character varying(20) NOT NULL;
  pq: column "channel" of relation "sales_orders" contains null values
-- 1 migration with errors
```

What happened, and why it is fine:

- `validate` passed because it replays on the **empty** `atlas_dev` database. Your local
  database has 200k rows → existing rows would get `NULL`. This is rule 3.
- Atlas runs **each file in a transaction**, and PostgreSQL DDL is transactional:
  the failed file was rolled back entirely. `make migrate-status` still shows it as `PENDING`.

**Fix** — the file was never applied anywhere, so you may edit it (rule 2). Use the
*expand → backfill → contract* pattern:

```sql
-- atlas/migrations/<version>_add_channel.sql
-- 1. add the column as NULLable
ALTER TABLE "public"."sales_orders" ADD COLUMN "channel" character varying(20) NULL;
-- 2. backfill existing rows (data migration, written by hand)
UPDATE "public"."sales_orders" SET "channel" = 'web' WHERE "channel" IS NULL;
-- 3. now enforce the constraint
ALTER TABLE "public"."sales_orders" ALTER COLUMN "channel" SET NOT NULL;
COMMENT ON COLUMN "public"."sales_orders"."channel" IS 'Sales channel: web, store, phone';
```

```bash
make migrate-validate   # You have a checksum error ... add_channel.sql was edited
make migrate-hash       # deliberate edit -> re-sign atlas.sum
make migrate-validate   # migrations valid
make migrate-diff name=check   # "The migration directory is synced with the desired state"
make migrate-apply      # -- ok -- 1 migration -- 4 sql statements
```

> The `migrate-diff` "synced" message is your proof that the hand-edited file still
> produces exactly what `schema.pg.hcl` describes.

---

## Part 3 — Hand-written migrations: `CREATE INDEX CONCURRENTLY`

On a big production table, a plain `CREATE INDEX` blocks writes for the whole build.
`CONCURRENTLY` doesn't — but Atlas cannot generate it, and it cannot run in a transaction.

```bash
make migrate-new name=customer_idx      # empty file atlas/migrations/<version>_customer_idx.sql
```

First attempt:

```sql
CREATE INDEX CONCURRENTLY "sales_orders_customer_id_idx" ON "public"."sales_orders" ("customer_id");
```
```bash
make migrate-hash && make migrate-apply
#   pq: CREATE INDEX CONCURRENTLY cannot run inside a transaction block
```

Tell Atlas to run this file without a transaction — directive on the first line, then a blank line:

```sql
-- atlas:txmode none

CREATE INDEX CONCURRENTLY "sales_orders_customer_id_idx" ON "public"."sales_orders" ("customer_id");
```
```bash
make migrate-hash && make migrate-apply     # -- ok
```

> ⚠️ A `txmode none` file is **not** atomic. Keep it to one statement so a failure can't
> leave it half-applied.

**Trap:** you forgot rule 1. The next `make migrate-diff` generates:

```sql
-- Drop index "sales_orders_customer_id_idx" from table: "sales_orders"
DROP INDEX "public"."sales_orders_customer_id_idx";
```

because the HCL doesn't know about the index. Remove that file and declare the index:

```bash
make migrate-rm version=<version_of_that_file>
```
```hcl
  index "sales_orders_customer_id_idx" {
    columns = [column.customer_id]
  }
```
```bash
make migrate-diff name=check   # synced with the desired state, no changes to be made
```

---

## Part 4 — Undo locally

| Situation | Command |
|---|---|
| Revert the last N applied migrations | `make migrate-down` (or `make migrate-down n=2`) |
| Start over completely | `make db-reset && make migrate-apply && make demo` |

`migrate down` computes the reverse SQL with the dev database **and refuses to lose data**:

```
-- checks before reverting version 20261008200057
  -> SELECT NOT EXISTS (SELECT 1 FROM "public"."sales_orders" WHERE "channel" IS NOT NULL) AS "is_empty"
  check assertion "SELECT NOT EXISTS (...)" returned false
```

…while reverting the index (no data involved) just works:

```
-- reverting version 20261008200136
  -> DROP INDEX "public"."sales_orders_customer_id_idx"
-- ok
```

After `migrate down`, the file is pending again: you may now edit it (then
`make migrate-hash`), or delete it (`make migrate-rm version=<version>`) and regenerate
it from a corrected HCL.

---

## Part 5 — Practise the remote workflow with a fake prod

No access to a remote database yet? Start a **second** local server playing "prod"
(port 5434, separate data folder `.pgdata-fakeprod/`):

```bash
make fake-prod-start
eval "$(make -s fake-prod-env)"          # DATABASE_URL now points at the fake prod
make migrate-apply-prod                  # bring it up to date with what's committed
python demo.py                           # give it data
# make prod "different": 37 orders with a status your local data never has
python -c "from client import PostgresClient; from config import PgConfig; \
PostgresClient(PgConfig.from_env()).execute(\"UPDATE sales_orders SET status = 'refunded' WHERE order_id <= 37\")"
```

> In a real project, replace `eval "$(make -s fake-prod-env)"` with the real
> `DATABASE_URL` from your secret store. Everything below is identical.

Open a **new terminal** (so `DATABASE_URL` is unset) for local work.

---

## Part 6 — Fail during rehearsal: a constraint that only prod data violates

Locally, add a constraint on `status`:

```hcl
  check "sales_orders_status_valid" {
    expr = "status IN ('pending', 'shipped', 'cancelled')"
  }
```
```bash
make migrate-diff name=add_status_check
make migrate-apply          # -- ok   (local data only has pending/shipped/cancelled)
```

Locally everything is green. Now rehearse against a copy of the remote.
`make rehearse` = **clone remote → local `app` DB**, then `migrate-status` and
`migrate-apply` on the copy. The remote is only *read* (use a read-only user).

```bash
export SOURCE_URL='postgres://postgres:localdev@127.0.0.1:5434/app?sslmode=disable'  # fake prod
make rehearse
```
```
Cloned schema into local 'app'.
Migration Status: PENDING
  -- Current Version: 20261008200046        <- exactly where the remote is
  -- Pending Files:   3                     <- exactly what prod will run
-- migrating version 20261008200057  -- ok
-- migrating version 20261008200136  -- ok
-- migrating version 20261008200435  -- ok
```

Schema-only rehearsal passes — it validates the *structure* and the migration
history, but has no rows. Rehearse **with data**:

```bash
CLONE_WITH_DATA=1 make rehearse
```
```
WARNING: copying all rows. Never do this with personal / sensitive data.
-- migrating version 20261008200057  -> ... UPDATE "public"."sales_orders" SET "channel" = 'web' ...  -- ok (1.24s)
-- migrating version 20261008200136  -> CREATE INDEX CONCURRENTLY ...                              -- ok
-- migrating version 20261008200435
  -> ALTER TABLE "public"."sales_orders" ADD CONSTRAINT "sales_orders_status_valid" CHECK (...)
  pq: check constraint "sales_orders_status_valid" of relation "sales_orders" is violated by some row
-- 2 migrations ok, 1 with errors
```

The real remote was never touched — it is still at version `...200046`.
Also note the **timing** (`1.24s` for the backfill): on prod volumes this tells you
whether a migration needs a maintenance window.

**Fix** — the file is applied only on your local DB, so it's still editable (rule 2):

After the failed rehearsal, the local `app` DB *is* the clone and the file is still
pending there — nothing to undo. (Had the file been applied on your local DB, you would
run `make migrate-down` first: check with `make migrate-status`.)

```bash
make migrate-rm version=<version of add_status_check>
# business decision: 'refunded' is a valid status -> fix the HCL
#   expr = "status IN ('pending', 'shipped', 'cancelled', 'refunded')"
make migrate-diff name=add_status_check
CLONE_WITH_DATA=1 make rehearse                 # -- 3 migrations -- 6 sql statements   ✅
```

> **Rehearsing with data when prod data is sensitive:** don't copy prod. Clone a
> **staging** database (`SOURCE_URL=<staging>`), or clone prod schema-only and load
> realistic synthetic data that covers the edge cases (here: every `status` value —
> `SELECT DISTINCT status FROM sales_orders` on prod is a cheap, safe check).

---

## Part 7 — Apply to production

Pre-flight checklist:

- [ ] Files merged to the main branch, `make migrate-validate` green in CI
- [ ] `make migrate-diff name=check` says *synced* (HCL and files agree)
- [ ] `make rehearse` green against the target (with data, or staging data)
- [ ] Long-running statements identified from rehearsal timings; `CONCURRENTLY` for big indexes
- [ ] Backup / PITR available on the prod side

Then, from a shell (or CI job) where `DATABASE_URL` is the production URL with the
**migration** role (how to get and load it: [05 Remote database](05_remote_database.md)):

```bash
export DATABASE_URL='postgres://migrator:***@db.prod:5432/app?sslmode=verify-full'
make migrate-status-prod     # what's pending
make migrate-plan-prod       # --dry-run: prints the SQL, executes nothing
make migrate-apply-prod
make migrate-status-prod     # Migration Status: OK -- Already at latest version
```

Real output (fake prod):

```
Migrating to version 20261008200435 from 20261008200046 (3 migrations in total):
  -- migrating version 20261008200057
    -> ALTER TABLE "public"."sales_orders" ADD COLUMN "channel" character varying(20) NULL;
    -> UPDATE "public"."sales_orders" SET "channel" = 'web' WHERE "channel" IS NULL;
    ...
  -- 3 migrations
  -- 6 sql statements
Migration Status: OK
  -- Current Version: 20261008200435
  -- Executed Files:  5
  -- Pending Files:   0
```

### If it fails in production anyway

- Each file is its own transaction (default `--tx-mode file`): files before the
  failing one **stay applied**, the failing one is **rolled back** and stays pending.
  `make migrate-status-prod` tells you exactly where you are.
- Want all-or-nothing for a release? `atlas migrate apply --env prod --tx-mode all`
  (not compatible with `txmode none` files).
- Fix the cause **locally**, rehearse again, ship. If the failing file was applied
  successfully *somewhere else* (staging, a colleague's prod-like env), don't edit it:
  add a new migration. Otherwise you may fix the file (it never applied anywhere).
- Never "fix" prod by hand with `psql` — the schema drifts from the files. If you
  truly had to, bring the files back in line and use `atlas migrate set` to record it.

---

## Part 8 — Working in a team

Two people create migrations on separate branches. After merging, a teammate's file can
have an **older timestamp** than one you already applied:

```bash
make migrate-apply
# Error: migration file 20261008200100_add_country.sql was added out of order.
make migrate-rebase version=20261008200100    # renumbered to "now"
make migrate-apply    # -- ok
```

> ⚠️ **Silent variant:** if the merged file is older than **every** migration already
> applied to that database, Atlas does *not* raise this error — it ignores the file:
> `make migrate-status` says `OK`, `Pending Files: 0`. Guard against it after every
> merge: the `Executed Files` count must equal the number of `.sql` files in
> `atlas/migrations/` (`ls atlas/migrations/*.sql | wc -l`). If not, `make migrate-rebase`.

`atlas.sum` also produces a **git conflict** when two branches add migrations — that is a
feature: resolve by keeping both files, then `make migrate-hash` (and `make migrate-rebase`
if Atlas reports an out-of-order file).

---

## Part 9 — Production database that predates Atlas (baseline)

If prod already has tables, generate a *baseline* migration describing them and tell Atlas
it's already applied there:

```bash
export DATABASE_URL='<prod url, read-only is enough for inspect>'
atlas schema inspect -u "$DATABASE_URL" > atlas/schema.pg.hcl 2>/dev/null
eval "$(make -s db-env)"                       # local: DATABASE_URL + ATLAS_DEV_URL
make migrate-diff name=baseline                # -> <version>_baseline.sql
# then, against prod (DATABASE_URL = prod again):
cd atlas
atlas migrate apply --env prod --baseline <version>      # "No migration files to execute"
atlas migrate status --env prod                          # Current Version: <version>
```

Locally the baseline file is applied normally (it creates the tables). Note that the
free Atlas edition skips triggers, functions and procedures during `inspect` — add
those as hand-written migrations if you have any.

---

## Cheat sheet

| I want to… | Command |
|---|---|
| Create a migration from HCL changes | `make migrate-diff name=<what>` |
| Write SQL by hand (backfill, CONCURRENTLY) | `make migrate-new name=<what>` → edit → `make migrate-hash` |
| Apply / see status locally | `make migrate-apply` / `make migrate-status` |
| Check files are intact & replay | `make migrate-validate` |
| Check HCL and files agree | `make migrate-diff name=check` → *synced* |
| Undo locally | `make migrate-down [n=2]` · `make db-reset && make migrate-apply` |
| Delete a never-shipped migration | `make migrate-rm version=<version>` |
| Fix out-of-order after merge | `make migrate-rebase version=<version>` |
| Rehearse on a remote copy | `SOURCE_URL=... make rehearse` (`CLONE_WITH_DATA=1` for rows) |
| Ship to prod | `make migrate-plan-prod` → `make migrate-apply-prod` → `make migrate-status-prod` |
| Practise without a remote | `make fake-prod-start` · `eval "$(make -s fake-prod-env)"` |

Clean up after practising: `make fake-prod-stop && rm -rf .pgdata-fakeprod`, and
`git checkout atlas/ && git clean -fd atlas/migrations` to drop the tutorial migrations.

Next: [05 — Working with the remote database](05_remote_database.md)
