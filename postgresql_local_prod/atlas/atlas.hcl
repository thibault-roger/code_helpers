# atlas.hcl — one project, two environments, ONE migrations folder.
#
# Both environments read their connection from environment variables, so the
# only difference between local and production is what you export:
#
#   DATABASE_URL   target database   (local: printed by `python local_server.py env`)
#   ATLAS_DEV_URL  EMPTY scratch database Atlas uses to compute and verify SQL.
#                  Normally `docker://postgres/16/dev` — not available here, so we
#                  point it at the `atlas_dev` database of the local server instead.
#
# Usage (run from this folder, or via the Makefile one level up):
#   atlas migrate diff  <name> --env local   # schema.pg.hcl changed -> new migration file
#   atlas migrate apply        --env local   # apply pending migrations locally
#   atlas migrate apply        --env prod    # same files, production database

locals {
  migrations = "file://migrations"
}

env "local" {
  src = "file://schema.pg.hcl"
  url = getenv("DATABASE_URL")
  dev = getenv("ATLAS_DEV_URL")

  migration {
    dir = local.migrations
  }
}

env "prod" {
  # No `src`: production only ever *applies* the committed migration files.
  # Never run `atlas schema apply` against production.
  url = getenv("DATABASE_URL")

  # Needed only by commands that compute SQL (diff, lint). In CI, point it at a
  # throwaway local server (`python local_server.py start`) — never at prod.
  dev = getenv("ATLAS_DEV_URL")

  migration {
    dir = local.migrations
  }
}
