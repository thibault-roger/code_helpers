-- remote_roles.sql — recommended users for a REMOTE (shared / production) database.
--
-- Locally you are superuser and that is fine. On a remote database, use two roles:
--
--   migrator  owns the tables. ONLY Atlas uses it (migrate apply).
--   app_user  reads and writes rows. Your Python code uses it. It cannot
--             CREATE / ALTER / DROP anything, so a bug or a leaked password
--             can never destroy the schema.
--
-- Who runs this? Whoever administers the remote server (DBA / platform team),
-- once, connected to the application database. Replace `app` with the database
-- name and the passwords with strong generated ones. Tested on PostgreSQL 16.
--
-- Afterwards you get two URLs:
--   migrations: postgres://migrator:***@HOST:5432/app?sslmode=require
--   app:        postgres://app_user:***@HOST:5432/app?sslmode=require

CREATE ROLE migrator LOGIN PASSWORD 'change-me-migrator';
CREATE ROLE app_user LOGIN PASSWORD 'change-me-app';

-- migrator owns the schema: it can CREATE / ALTER / DROP tables (Atlas uses it)
GRANT CONNECT, CREATE ON DATABASE app TO migrator;   -- CREATE: Atlas creates its own schema
ALTER SCHEMA public OWNER TO migrator;

-- app_user can only read and write rows (the application uses it)
GRANT CONNECT ON DATABASE app TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
-- applies to every table/sequence migrator creates FROM NOW ON
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_user;
-- app_user may read which migration version is applied (Atlas creates the
-- atlas_schema_revisions schema on its first run, so grant on future schemas too)
ALTER DEFAULT PRIVILEGES FOR ROLE migrator GRANT USAGE ON SCHEMAS TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator GRANT SELECT ON TABLES TO app_user;
