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

## Stage 2 — Docker Compose (microservices)

Period 2 of the sprint plan decomposes the monolith into five standalone services
(`apps/services/{identity,catalog,inventory,cart,order}`) plus the frontend, all built as
containers and run together via `deploy/docker/docker-compose.yml`. This section covers the
local registry, Trivy scanning, and the build/scan/push workflow — all run from **Git Bash**,
since the scripts under `deploy/docker/scripts/` are bash, not PowerShell/cmd.

### Prerequisites

- **Docker Desktop**, running, with the Docker Engine reachable from Git Bash (`docker ps`
  should succeed with no extra setup — Docker Desktop on Windows adds `docker` to `PATH`
  automatically).
- **Git Bash** (ships with Git for Windows) — used to run every script in this section. Running
  them from PowerShell or cmd.exe will not work directly, since they're POSIX shell scripts.
- **Trivy**, for image vulnerability scanning (see install steps below).

### Installing Trivy on Windows

Trivy isn't bundled with Docker Desktop and has to be installed separately. Either of these
work; both put `trivy` on `PATH` for new shells:

```sh
# via winget
winget install AquaSecurity.Trivy

# or via Chocolatey
choco install trivy
```

After installing, **close and reopen Git Bash** so the updated `PATH` takes effect, then confirm:

```sh
trivy --version
```

### Starting the local registry

`deploy/docker/scripts/start-registry.sh` starts a plain `registry:2` container bound to
`localhost:5000`, used for the build → scan → push workflow below (a stand-in for the eventual
dedicated registry VM per the PMP resource plan — this one is explicitly local-only, per SDD 9.1).
It's idempotent: safe to run every time, it no-ops if the registry is already running.

```sh
bash deploy/docker/scripts/start-registry.sh
```

Verify it's up:

```sh
docker ps --filter name=bookstore-registry
```

To see what's actually stored in the registry (not just what Docker has cached locally — those
are different things), query its HTTP API directly:

```sh
curl http://localhost:5000/v2/_catalog                       # list repositories
curl http://localhost:5000/v2/bookstore/catalog/tags/list     # list tags for one repo
```

### Building, scanning, and pushing images

Run from the **repository root** in Git Bash:

```sh
bash deploy/docker/scripts/build-scan-push.sh                 # all six images
bash deploy/docker/scripts/build-scan-push.sh catalog cart     # or just specific services
```

For each service this: builds the image, runs `trivy image` against it (report saved to
`evidence/trivy/<service>-<tag>.json`), and pushes to `localhost:5000` only if there are zero
unresolved **Critical**-severity findings. Tags follow `<semver>-<short-commit>` (SDD 9.1) —
the commit hash comes from `git rev-parse --short HEAD`, so run this from inside the repo, not a
copied/zipped checkout, or the tag falls back to `<semver>-nogit` (still works, but loses the
commit traceability the convention exists for).

### Verifying a genuine registry pull (not just push)

A `docker push` succeeding doesn't by itself prove a *pull* would work — and because pushed and
locally-built images share identical layers, a `docker pull` right after a build will often just
report `Already exists` without transferring anything, which isn't a meaningful test either. To
prove the round-trip for real, delete every local reference first so nothing can be silently
reused, then pull:

```sh
TAG="0.1.0-<short-commit>"
docker rmi "bookstore/catalog:${TAG}" "localhost:5000/bookstore/catalog:${TAG}"
docker images | grep catalog          # confirm it's gone locally

docker pull "localhost:5000/bookstore/catalog:${TAG}"
docker run --rm -d --name catalog-pulltest -p 18001:8000 \
  -e DATABASE_URL="postgresql+psycopg://x:x@localhost/x" \
  -e MIGRATION_DATABASE_URL="postgresql+psycopg://x:x@localhost/x" \
  -e JWT_SECRET="pulltest-secret" \
  "localhost:5000/bookstore/catalog:${TAG}"
curl http://localhost:18001/health/live      # expect {"status":"live"}
docker rm -f catalog-pulltest
```

The four other backend services follow the same pattern with their own required env vars (see
each service's `app/core/config.py` for what's required vs. optional). `frontend` can't be
smoke-tested standalone this way — its nginx config proxies `/api/*` to the other services by
Compose service name, so it fails fast (`host not found in upstream "identity"`) when run in
isolation. That's expected, not a bug: verify it instead as part of a full `docker compose up`
(below), and confirm the running container's image digest matches what was pushed:

```sh
docker inspect bookstore-frontend-1 --format '{{.Image}}'
docker image inspect localhost:5000/bookstore/frontend:<tag> --format '{{.Id}}'
# both should print the same sha256 digest
```

### Running the full Compose stack

```sh
cd deploy/docker
docker compose up --build
```

Brings up Postgres, Redis, one-shot Alembic migration jobs per service, one-shot seed jobs
(`seed-catalog`, `seed-inventory` — idempotent, safe to re-run), all five application services,
and the frontend, in health-check-gated dependency order. Once healthy, the app is at
**http://localhost** (frontend on host port 80).

Note: `docker compose up` **builds locally by default** — it does not pull from the registry
started above, even though the registry is populated. The registry and the Compose stack are
verified independently in this workflow; wiring Compose to pull from the registry (via
`pull_policy: always` and a registry-qualified `image:`) is a later-stage concern once deploying
to shared infrastructure, not required for Gate 3.

A `docker-compose.override.yml` in the same directory adds a host-mapped Postgres port (5433)
purely for local `pgAdmin` access — it's explicitly not part of the intended network design and
should not be carried forward into any VM/Kubernetes deployment.
