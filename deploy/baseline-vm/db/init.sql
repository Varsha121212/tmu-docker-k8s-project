-- Stage 1 baseline database setup (SDD section 8: one PostgreSQL instance, four schemas, ADR-005 least-privilege accounts).
-- Run ONCE as the postgres superuser, e.g.:
--   psql -U postgres -h localhost -f deploy/baseline-vm/db/init.sql
-- or paste into pgAdmin's Query Tool against the default "postgres" maintenance DB.
--
-- Replace both CHANGE_ME_* passwords below before running. Do not commit real passwords anywhere.

CREATE DATABASE bookstore;

\connect bookstore

-- migration_admin: schema/table DDL only (Alembic). Not used by the running application (SDD 8.4).
CREATE ROLE migration_admin WITH LOGIN PASSWORD 'CHANGE_ME_MIGRATIONS';

-- bookstore_monolith: Stage 1 runtime account, CRUD across all four schemas (SDD 8.4).
CREATE ROLE bookstore_monolith WITH LOGIN PASSWORD 'CHANGE_ME_APP';

CREATE SCHEMA IF NOT EXISTS identity  AUTHORIZATION migration_admin;
CREATE SCHEMA IF NOT EXISTS catalog   AUTHORIZATION migration_admin;
CREATE SCHEMA IF NOT EXISTS inventory AUTHORIZATION migration_admin;
CREATE SCHEMA IF NOT EXISTS orders    AUTHORIZATION migration_admin;

-- Alembic's own bookkeeping table (alembic_version) lives here instead of "public",
-- since Postgres 15+ revokes CREATE on public from non-owners by default.
CREATE SCHEMA IF NOT EXISTS migration AUTHORIZATION migration_admin;

GRANT USAGE ON SCHEMA identity, catalog, inventory, orders TO bookstore_monolith;

-- Tables are created by migration_admin (Alembic); grant the runtime role CRUD on
-- whatever migration_admin creates from now on, automatically, without re-running GRANTs per migration.
ALTER DEFAULT PRIVILEGES FOR ROLE migration_admin IN SCHEMA identity, catalog, inventory, orders
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bookstore_monolith;
ALTER DEFAULT PRIVILEGES FOR ROLE migration_admin IN SCHEMA identity, catalog, inventory, orders
    GRANT USAGE, SELECT ON SEQUENCES TO bookstore_monolith;
