# Makefile — local PostgreSQL (no Docker) + Atlas migrations
#
# Local targets always load the LOCAL connection (even if your shell has a prod
# DATABASE_URL exported), so `make migrate-apply` can never hit production.
# Production targets use whatever DATABASE_URL / ATLAS_DEV_URL your shell provides.
#
# Usage:
#   make db-start                     start the local server (first run: initdb)
#   make migrate-diff name=add_x      schema.pg.hcl changed -> new migration file
#   make migrate-apply                apply pending migrations locally
#   make demo                         run demo.py against the local database
#   SOURCE_URL=... make rehearse      copy a remote DB locally + apply pending migrations to the copy
#   make migrate-plan-prod            dry-run against prod (DATABASE_URL from env)
#
# Step-by-step guides: docs/ (start with docs/01_concepts.md)

PY    ?= python
LOCAL  = eval "$$($(PY) local_server.py env)"

.PHONY: db-start db-stop db-status db-env db-psql db-reset db-check db-clone rehearse \
        fake-prod-start fake-prod-stop fake-prod-env \
        migrate-diff migrate-new migrate-apply migrate-status migrate-down migrate-rm migrate-rebase \
        migrate-validate migrate-hash \
        migrate-plan-prod migrate-apply-prod migrate-status-prod check-prod demo

# ── Local server ────────────────────────────────────────────────────────────
db-start:
	$(PY) local_server.py start

db-stop:
	$(PY) local_server.py stop

db-status:
	$(PY) local_server.py status

# Print the export lines; use as:  eval "$(make -s db-env)"
db-env:
	@$(PY) local_server.py env

db-psql:
	$(PY) local_server.py psql

# Delete ALL local data and start from an empty server
db-reset:
	$(PY) local_server.py reset

# Can we connect? What does the server look like? (read-only)
db-check:
	@$(LOCAL) && $(PY) check_connection.py

# Replace the local app DB with a copy of a remote one (schema + Atlas history).
#   SOURCE_URL='postgres://readonly:***@db.prod:5432/app?sslmode=require' make db-clone
db-clone:
	@test -n "$$SOURCE_URL" || (echo "usage: SOURCE_URL=<remote url> make db-clone" && exit 1)
	$(PY) local_server.py clone

# Clone the remote, then apply the pending migrations to the copy: a dress
# rehearsal of `migrate-apply-prod` that cannot harm the remote database.
rehearse: db-clone migrate-status migrate-apply

# ── Fake "prod": a 2nd local server to practise the remote workflow ────────
FAKEPROD = LOCAL_PG_DATA=.pgdata-fakeprod LOCAL_PG_PORT=5434 $(PY) local_server.py

fake-prod-start:
	$(FAKEPROD) start

fake-prod-stop:
	$(FAKEPROD) stop

# Use as:  eval "$(make -s fake-prod-env)"   (DATABASE_URL -> the fake prod)
fake-prod-env:
	@$(FAKEPROD) env | grep -v APP_ENV

# ── Migrations (local) ──────────────────────────────────────────────────────
migrate-diff:
	@test -n "$(name)" || (echo "usage: make migrate-diff name=<short_description>" && exit 1)
	@$(LOCAL) && cd atlas && atlas migrate diff $(name) --env local

migrate-apply:
	@$(LOCAL) && cd atlas && atlas migrate apply --env local

migrate-status:
	@$(LOCAL) && cd atlas && atlas migrate status --env local

# Hand-written migration (data backfill, CONCURRENTLY index, …): creates an empty file
migrate-new:
	@test -n "$(name)" || (echo "usage: make migrate-new name=<short_description>" && exit 1)
	cd atlas && atlas migrate new $(name)

# Undo the last N applied migrations LOCALLY (Atlas refuses if data would be lost)
migrate-down:
	@$(LOCAL) && cd atlas && atlas migrate down $(or $(n),1) --env local

# Delete a migration file that was never applied outside your local DB
migrate-rm:
	@test -n "$(version)" || (echo "usage: make migrate-rm version=<version>" && exit 1)
	@$(LOCAL) && cd atlas && atlas migrate rm $(version) --env local

# Renumber a file that arrived "out of order" after a git merge to the latest version
migrate-rebase:
	@test -n "$(version)" || (echo "usage: make migrate-rebase version=<version>" && exit 1)
	@$(LOCAL) && cd atlas && atlas migrate rebase $(version) --env local

# Checksums (atlas.sum) + replay every migration on the empty dev database.
# Free alternative to `atlas migrate lint` (Atlas Pro since v0.38).
migrate-validate:
	@$(LOCAL) && cd atlas && atlas migrate validate --env local && echo "migrations valid"

# Only after a deliberate manual edit of a NOT-yet-applied migration file
migrate-hash:
	cd atlas && atlas migrate hash

# ── Migrations (production) ─────────────────────────────────────────────────
# Require an explicit prod connection in the environment.
migrate-plan-prod:
	@test -n "$$DATABASE_URL" || (echo "DATABASE_URL is not set" && exit 1)
	cd atlas && atlas migrate apply --env prod --dry-run

migrate-apply-prod:
	@test -n "$$DATABASE_URL" || (echo "DATABASE_URL is not set" && exit 1)
	cd atlas && atlas migrate apply --env prod

migrate-status-prod:
	@test -n "$$DATABASE_URL" || (echo "DATABASE_URL is not set" && exit 1)
	cd atlas && atlas migrate status --env prod

check-prod:
	@test -n "$$DATABASE_URL" || (echo "DATABASE_URL is not set" && exit 1)
	$(PY) check_connection.py

# ── Demo ────────────────────────────────────────────────────────────────────
demo:
	@$(LOCAL) && $(PY) demo.py
