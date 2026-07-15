#!/bin/bash
# Stage 2 Compose Postgres bootstrap (SDD section 8.4, ADR-005: least-privilege
# per-service DB accounts). Executed once automatically by the official
# postgres image's /docker-entrypoint-initdb.d mechanism against a fresh named
# volume - every *_PASSWORD variable below comes from the postgres service's
# own environment (wired from deploy/docker/.env via docker-compose.yml), so
# `docker compose up` from a clean state needs no manual SQL editing.
#
# Unlike Stage 1's baseline-vm/db/init.sql (one shared bookstore_monolith role
# across all four schemas), each Stage 2 service gets its own migrator +
# runtime role scoped to only its own schema - the decomposition (US-PLT-04)
# is the point this separation starts mattering. Cart has no role here -
# Redis is its only data store (SDD 7.4, 8.3).
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE SCHEMA IF NOT EXISTS identity;
    CREATE SCHEMA IF NOT EXISTS catalog;
    CREATE SCHEMA IF NOT EXISTS inventory;
    CREATE SCHEMA IF NOT EXISTS orders;

    CREATE ROLE identity_migrator WITH LOGIN PASSWORD '${IDENTITY_MIGRATOR_PASSWORD}';
    CREATE ROLE identity_app WITH LOGIN PASSWORD '${IDENTITY_APP_PASSWORD}';
    ALTER SCHEMA identity OWNER TO identity_migrator;
    GRANT USAGE ON SCHEMA identity TO identity_app;
    ALTER DEFAULT PRIVILEGES FOR ROLE identity_migrator IN SCHEMA identity
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO identity_app;
    ALTER DEFAULT PRIVILEGES FOR ROLE identity_migrator IN SCHEMA identity
        GRANT USAGE, SELECT ON SEQUENCES TO identity_app;

    CREATE ROLE catalog_migrator WITH LOGIN PASSWORD '${CATALOG_MIGRATOR_PASSWORD}';
    CREATE ROLE catalog_app WITH LOGIN PASSWORD '${CATALOG_APP_PASSWORD}';
    ALTER SCHEMA catalog OWNER TO catalog_migrator;
    GRANT USAGE ON SCHEMA catalog TO catalog_app;
    ALTER DEFAULT PRIVILEGES FOR ROLE catalog_migrator IN SCHEMA catalog
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO catalog_app;
    ALTER DEFAULT PRIVILEGES FOR ROLE catalog_migrator IN SCHEMA catalog
        GRANT USAGE, SELECT ON SEQUENCES TO catalog_app;

    CREATE ROLE inventory_migrator WITH LOGIN PASSWORD '${INVENTORY_MIGRATOR_PASSWORD}';
    CREATE ROLE inventory_app WITH LOGIN PASSWORD '${INVENTORY_APP_PASSWORD}';
    ALTER SCHEMA inventory OWNER TO inventory_migrator;
    GRANT USAGE ON SCHEMA inventory TO inventory_app;
    ALTER DEFAULT PRIVILEGES FOR ROLE inventory_migrator IN SCHEMA inventory
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO inventory_app;
    ALTER DEFAULT PRIVILEGES FOR ROLE inventory_migrator IN SCHEMA inventory
        GRANT USAGE, SELECT ON SEQUENCES TO inventory_app;

    CREATE ROLE order_migrator WITH LOGIN PASSWORD '${ORDER_MIGRATOR_PASSWORD}';
    CREATE ROLE order_app WITH LOGIN PASSWORD '${ORDER_APP_PASSWORD}';
    ALTER SCHEMA orders OWNER TO order_migrator;
    GRANT USAGE ON SCHEMA orders TO order_app;
    ALTER DEFAULT PRIVILEGES FOR ROLE order_migrator IN SCHEMA orders
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO order_app;
    ALTER DEFAULT PRIVILEGES FOR ROLE order_migrator IN SCHEMA orders
        GRANT USAGE, SELECT ON SEQUENCES TO order_app;
EOSQL
