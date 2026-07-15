# Online Bookstore — CN8001

Stage 1 of a three-stage project comparing deployment models for the same application: a
traditional VM-hosted modular monolith (this stage) evolving into Docker Compose microservices
(Stage 2) and a kubeadm Kubernetes cluster (Stage 3). Background, requirements and design
rationale live in [documents/](documents/) (BRD, PMP, SDD) and the working backlog in
[documents/backlog/](documents/backlog/).

## Project layout

```
apps/
  monolith/   FastAPI modular monolith (Python 3.14, SQLAlchemy, Alembic, PostgreSQL, Redis)
  frontend/   React + TypeScript + Vite + Tailwind CSS
deploy/
  baseline-vm/db/init.sql   Stage 1 database bootstrap (roles, schemas, grants)
documents/    BRD, PMP, SDD, and the sprint backlog
```

## Prerequisites

- **Python 3.12+** (developed and tested against 3.14 — the SDD currently pins 3.12; this is a
  known, flagged deviation, not yet reconciled in the SDD)
- **Node.js 20+** and npm
- **PostgreSQL 15+**, running locally with `psql`/`pg_isready` available (or add
  `<postgres-install-dir>/bin` to your `PATH`)
- **Redis-compatible server** — Memurai on Windows, Redis elsewhere — running on the default port

## First-time setup

### 1. Database

Run once, as the `postgres` superuser, after replacing the two `CHANGE_ME_*` passwords with
your own:

```sh
psql -U postgres -h localhost -f deploy/baseline-vm/db/init.sql
```

This creates the `bookstore` database, the four business schemas (`identity`, `catalog`,
`inventory`, `orders`), a `migration` schema for Alembic's own bookkeeping, and two roles:
`migration_admin` (schema/table DDL only, used by Alembic) and `bookstore_monolith` (the
runtime app account, CRUD across all four schemas). See SDD section 8.4 for the rationale.

Postgres 15+ revokes schema-creation rights on `public` from non-superusers by default, so the
`migration` schema needs to be created as superuser too:

```sh
psql -U postgres -h localhost -d bookstore -c "CREATE SCHEMA IF NOT EXISTS migration AUTHORIZATION migration_admin;"
```

### 2. Backend environment

```sh
cd apps/monolith
cp .env.example .env
```

Edit `.env` and fill in the same two passwords you chose above, plus a real `JWT_SECRET`:

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`.env` is gitignored — never commit it.

### 3. Backend install + migrate

```sh
cd apps/monolith
python -m venv .venv

# Windows
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m alembic upgrade head

# macOS/Linux
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m alembic upgrade head
```

### 4. Frontend install

```sh
cd apps/frontend
npm install
```

## Running locally

Two terminals:

```sh
# Terminal 1 — backend (from apps/monolith)
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend (from apps/frontend)
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies `/api/*` to `http://localhost:8000`,
so no CORS configuration is needed in dev. Backend API docs are at
http://localhost:8000/docs.

## Running tests

```sh
cd apps/monolith
.venv/Scripts/python.exe -m pytest -v
```

Each test runs inside a transaction that's rolled back afterward, so the suite runs against the
real local Postgres database without leaving data behind.

## Troubleshooting

- **`psql`/`pg_isready` not found** — add PostgreSQL's `bin` directory to your `PATH`
  (e.g. `C:\Program Files\PostgreSQL\18\bin` on Windows), or use the full path to the binary.
- **`permission denied for schema public` when running Alembic** — this means the one-off
  `migration` schema setup command in step 1 above hasn't been run yet.
- **Docker Desktop** is not required for Stage 1 (bare VM / native local dev) — it becomes
  relevant starting in Period 2 of the sprint plan, when the monolith is decomposed into
  containerized microservices.
