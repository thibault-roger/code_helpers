# %% [markdown]
# # Teradata — User Access Control
#
# How to create users and scope their access to specific databases, tables,
# views, and columns.  All statements are standard Teradata SQL DDL — run them
# in BTEQ, Teradata Studio, DBeaver, or via `client.execute()`.
#
# ## Mental model
#
# Teradata access is **additive only** — there is no DENY.
# A user gets the union of every privilege granted directly to them plus every
# privilege granted to any role they hold.  You cannot selectively block a
# privilege that was inherited from a role.
#
# Three building blocks:
#   1. **PROFILE** — account settings template (password policy, spool/temp space)
#   2. **ROLE**    — named set of object privileges (SELECT, INSERT, …)
#   3. **USER**    — login identity; assigned a profile and one or more roles
#
# Recommended pattern: profile → role → user
#   - Define resource limits once in a profile.
#   - Define object privileges once per role.
#   - Assign profiles and roles to users; never grant privileges directly to users.
#   - This makes auditing and changes trivially easy.

# %% [markdown]
# ## 1. Profiles — resource limits & password policy
#
# A profile centralises settings that would otherwise need to be repeated on
# every CREATE USER statement.  Assign it at user-creation time; it can be
# changed later without recreating the user.

# %%
# ── Create a profile ─────────────────────────────────────────────────────────
CREATE_PROFILE = """
CREATE PROFILE analyst_profile AS
    -- Space limits (bytes; 1 GB = 1e9)
    SPOOL           = 10e9,    -- scratch space for query intermediates
    TEMPORARY       = 2e9,     -- GTT / volatile table space

    -- Password policy
    PASSWORD        = (
        EXPIRE      = 90,      -- days before forced reset
        MINCHAR     = 10,
        MAXCHAR     = 20,
        DIGIT       = 1,
        SPECCHAR    = 1,
        MAXLOGONATTEMPTS = 5,
        LOCKEDUSERS ALLOWED
    );
"""

# ── Assign profile to an existing user ───────────────────────────────────────
ASSIGN_PROFILE = """
MODIFY USER my_user AS PROFILE = analyst_profile;
"""


# %% [markdown]
# ## 2. Roles — reusable privilege bundles
#
# Always grant object privileges to roles, not directly to users.
# A role can be assigned to many users, and revoking the role from a user
# instantly removes all privileges it carried.
#
# Privilege reference for SELECT:
#   SELECT, INSERT, UPDATE, DELETE, EXECUTE (stored proc/macro),
#   CREATE TABLE, DROP TABLE, SHOW, DUMP, RESTORE, …

# %%
# ── Create roles ──────────────────────────────────────────────────────────────
CREATE_ROLES = """
-- Read-only role: full SELECT on one database
CREATE ROLE role_sales_reader;
GRANT SELECT ON sales_db TO role_sales_reader;

-- Analyst role: read a subset of tables + write to a staging area
CREATE ROLE role_sales_analyst;
GRANT SELECT ON sales_db.orders        TO role_sales_analyst;
GRANT SELECT ON sales_db.customers     TO role_sales_analyst;
GRANT SELECT ON sales_db.products      TO role_sales_analyst;
GRANT INSERT, UPDATE ON staging_db.analyst_output TO role_sales_analyst;

-- Admin role for a single database (not a system admin)
CREATE ROLE role_sales_db_admin;
GRANT ALL ON sales_db TO role_sales_db_admin WITH GRANT OPTION;
"""
# WITH GRANT OPTION lets the holder re-grant the same privilege to others.
# Use sparingly — it creates a chain of grants that is hard to audit.


# %% [markdown]
# ## 3. Users — login identities
#
# Key parameters:
# - PERM SPACE: permanent space the user's own objects can consume (set to 0
#   for analysts who never create permanent tables).
# - DEFAULT DATABASE: the schema resolved when a query omits a qualifier.
# - PROFILE: links the account to the resource/password settings above.

# %%
# ── Create a user ────────────────────────────────────────────────────────────
CREATE_USER = """
CREATE USER analyst_alice
    FROM        dbc                    -- parent user/database that "owns" this account
    AS
    PASSWORD    = 'Change_Me_2024!'
    PERM SPACE  = 0                    -- 0 = cannot create permanent objects
    DEFAULT DATABASE = sales_db
    PROFILE     = analyst_profile;
"""

# ── Assign roles ──────────────────────────────────────────────────────────────
GRANT_ROLES = """
GRANT role_sales_analyst TO analyst_alice;

-- A user can hold multiple roles simultaneously
GRANT role_sales_reader  TO analyst_alice;
"""

# ── Activate roles in a session (user must run this after login) ──────────────
SET_ROLE = """
SET ROLE role_sales_analyst;       -- activate one role
SET ROLE ALL;                      -- activate all granted roles (most common default)
"""
# Roles are NOT automatically active after login unless DEFAULT ROLE is configured.
# To avoid confusion, set ALL as the default:
SET_DEFAULT_ROLE = """
MODIFY USER analyst_alice AS DEFAULT ROLE = ALL;
"""


# %% [markdown]
# ## 4. Column-level access
#
# Grant SELECT on specific columns only.  The user can query only those columns;
# querying any other column raises a permission error.
#
# Constraint: column-level grants and table-level grants coexist additively.
# If the user also holds a role with full SELECT on the table, the column
# restriction is bypassed by the broader privilege.  Column grants are only
# meaningful when the user has NO table-level SELECT.

# %%
COLUMN_GRANTS = """
-- Allow analyst to see customer name and region, but NOT email or phone
GRANT SELECT (customer_id, full_name, region)
    ON sales_db.customers
    TO role_sales_analyst;

-- Practical use: hide PII columns
GRANT SELECT (order_id, order_date, revenue)
    ON sales_db.orders
    TO role_sales_analyst;
    -- email, phone_number, card_last4 are NOT in the grant → inaccessible
"""


# %% [markdown]
# ## 5. Views — row-level and column-level scoping
#
# Views are the standard Teradata mechanism for row-level security.
# Teradata has no native row-level security policy object (unlike Oracle VPD).
#
# Pattern:
#   1. The raw tables live in a secured database (e.g. raw_db) — users have NO
#      direct access to raw_db.
#   2. A "views" database (e.g. views_db) exposes filtered views of raw_db.
#   3. Users are granted SELECT on views_db only.
#
# This gives you full control over what rows and columns are visible without
# any in-query filter that a user could bypass.

# %%
VIEWS_FOR_SCOPING = """
-- ── Column scoping view ───────────────────────────────────────────────────
-- Hide PII columns by simply omitting them from the SELECT list.
REPLACE VIEW views_db.v_customers AS
SELECT
    customer_id,
    full_name,
    region,
    signup_date,
    tier
    -- email, phone, card_last4 intentionally excluded
FROM raw_db.customers;


-- ── Row scoping view ──────────────────────────────────────────────────────
-- Each team sees only their own region's orders.
REPLACE VIEW views_db.v_orders_north AS
SELECT *
FROM raw_db.orders
WHERE region = 'North';


-- ── Dynamic row scoping (SESSION USER) ───────────────────────────────────
-- Filter rows based on who is running the query.
-- Requires a lookup table that maps Teradata usernames to allowed values.
REPLACE VIEW views_db.v_orders_by_owner AS
SELECT o.*
FROM raw_db.orders o
JOIN security_db.user_region_map m
    ON m.td_username = USER          -- USER = current Teradata session username
    AND m.region     = o.region;

-- Grant access to the view, NOT to the underlying table
GRANT SELECT ON views_db.v_orders_north    TO role_sales_analyst;
GRANT SELECT ON views_db.v_orders_by_owner TO role_sales_analyst;
"""
# Constraint: SESSION USER filtering only works if users log in with their own
# credentials.  Shared service accounts break row-level filtering by ownership.


# %% [markdown]
# ## 6. Revoking access
#
# REVOKE removes a privilege.  Use CASCADE if the privilege was granted WITH
# GRANT OPTION and the holder re-granted it downstream.

# %%
REVOKE = """
-- Revoke a role from a user
REVOKE role_sales_analyst FROM analyst_alice;

-- Revoke a specific privilege from a role
REVOKE INSERT, UPDATE ON staging_db.analyst_output FROM role_sales_analyst;

-- Revoke all privileges on a database from a role
REVOKE ALL ON sales_db FROM role_sales_reader;

-- Cascade revoke — also removes downstream grants made by analyst_alice
REVOKE SELECT ON sales_db.orders FROM analyst_alice CASCADE;
"""


# %% [markdown]
# ## 7. Inspect existing grants
#
# Teradata stores all grants in the DBC (Data Base Computer) catalog views.

# %%
INSPECT = """
-- All privileges held by a specific user (direct + via roles)
SELECT *
FROM DBC.AllRightsV
WHERE Grantee = 'analyst_alice'
ORDER BY DatabaseName, TableName, ColumnName;

-- All role assignments
SELECT *
FROM DBC.RoleMembers
WHERE Grantee = 'analyst_alice';

-- All privileges granted to a role
SELECT *
FROM DBC.AllRightsV
WHERE Grantee = 'role_sales_analyst'
ORDER BY DatabaseName, TableName;

-- Space used vs allocated for a user
SELECT
    UserName,
    PermSpace / 1e9   AS perm_gb,
    SpoolSpace / 1e9  AS spool_gb,
    TempSpace / 1e9   AS temp_gb
FROM DBC.UsersV
WHERE UserName = 'analyst_alice';
"""


# %% [markdown]
# ## 8. Full worked example
#
# Scenario: give analyst_alice read access to three tables in sales_db,
# write access to her own staging area, and no visibility of PII columns.

# %%
FULL_EXAMPLE = """
-- 1. Create databases
CREATE DATABASE staging_alice FROM dbc AS PERM = 5e9;

-- 2. Profile (reuse if it exists)
CREATE PROFILE analyst_profile AS
    SPOOL = 10e9, TEMPORARY = 2e9,
    PASSWORD = (EXPIRE = 90, MINCHAR = 10, MAXLOGONATTEMPTS = 5);

-- 3. Role with scoped privileges
CREATE ROLE role_analyst_alice;
GRANT SELECT (order_id, order_date, revenue, region)
    ON sales_db.orders                 TO role_analyst_alice;
GRANT SELECT (customer_id, full_name, region, tier)
    ON sales_db.customers              TO role_analyst_alice;
GRANT SELECT ON sales_db.products      TO role_analyst_alice;
GRANT INSERT, UPDATE, DELETE
    ON staging_alice.work_table        TO role_analyst_alice;

-- 4. User
CREATE USER analyst_alice
    FROM dbc AS
    PASSWORD = 'Temp_P@ss_2024'
    PERM SPACE = 0
    DEFAULT DATABASE = sales_db
    PROFILE = analyst_profile;

GRANT role_analyst_alice TO analyst_alice;
MODIFY USER analyst_alice AS DEFAULT ROLE = ALL;

-- Result:
--  ✓ SELECT on 4 columns of orders (not the full row)
--  ✓ SELECT on 4 columns of customers (no PII)
--  ✓ SELECT on all columns of products
--  ✓ INSERT / UPDATE / DELETE on their own staging table
--  ✗ Cannot see any other table in sales_db
--  ✗ Cannot create permanent objects (PERM = 0)
--  ✗ Cannot access raw_db, security_db, or any other database
"""


# %% [markdown]
# ## Key constraints & gotchas
#
# | Constraint | Detail |
# |-----------|--------|
# | **No DENY** | Privileges are purely additive. A broad role privilege always wins over a narrow column grant. |
# | **No native RLS policy** | Row filtering requires views or application-side logic. No equivalent to Oracle VPD. |
# | **Roles are not active by default** | Users must run `SET ROLE ALL` or have `DEFAULT ROLE = ALL` configured. |
# | **Column grants are fragile** | A table-level SELECT from ANY role bypasses column-level restrictions. |
# | **Space is shared from the parent** | PERM / SPOOL / TEMP come from the parent user's allocation (`FROM dbc`). |
# | **Shared accounts break row filtering** | SESSION-USER-based views only work with individual logins. |
# | **WITH GRANT OPTION is hard to audit** | Avoid it except for DB admins; use roles for delegation instead. |
# | **Views need LOCKING modifier for BI tools** | Add `LOCKING ROW FOR ACCESS` to views to avoid lock waits in concurrent reads. |
