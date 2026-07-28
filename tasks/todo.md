# US-PLT-21: Deploy Stage 2 Compose stack to the baseline VM for comparison

**Story:** As the project team, I want the Stage 2 Docker Compose stack
deployed to `vm-baseline-app` — the same VM used for the Stage 1 baseline —
after Stage 1 baseline evidence is captured there, so that the Stage
1-vs-Stage 2 comparison measures the orchestration-model difference on
identical hardware, not confounded by different host specs.

**Traces to:** PMP 10.1, 17.4. Depends on US-PLT-20 (done) and US-PLT-22
(done — Stage 1 evidence archived, safe to proceed).
**Points:** 3 — Compose stack itself already proven (Period 2, local Docker
Desktop); remaining work is VM-specific configuration only.

## Design decisions (stated here so they can be corrected before I build the
runbook around them — flag if any of these are wrong)

1. **Single-VM, self-contained topology — `vm-baseline-db` is NOT reused.**
   Checked `deploy/docker/docker-compose.yml`: it already brings its own
   `postgres`/`redis` containers with a fresh named volume and its own
   `init-db-roles.sh` bootstrap (ADR-005 per-service roles) — fully
   self-contained, exactly as tested in Period 2. PMP 10.1 itself names only
   `vm-baseline-app` as host for "Stage 2 Docker Compose microservices."
   Re-plumbing the compose file to point at an external Postgres on
   `vm-baseline-db` would be new, unproven work for no stated benefit —
   `vm-baseline-db` simply goes unused once Stage 2 deploys, which is fine.
2. **Registry pull, not a local rebuild.** Confirmed live against
   `registry-monitoring` (172.16.200.23:5000, reachable): five backend
   services are at `0.1.1-a08a02d`, `frontend` at `0.0.0-1c39d25` (the
   Trivy-remediated OpenSSL fix from US-PLT-23). Pull + retag locally to
   the exact tags the compose file expects, so `docker compose up` (no
   `--build`) uses the already-present images rather than rebuilding from
   source — matches the story's own "registry access from the VM" scope.
3. **Fixed a real pre-existing bug before using it:** `docker-compose.yml`
   reused one shared `${IMAGE_TAG}` across all six services, but frontend's
   tag numbering (`0.0.x`) is genuinely independent of the backend five's
   (`0.1.x`) — the identical single-shared-tag mistake already caught once
   in Kubernetes (US-PLT-13/24, see `MEMORY.md`). Fixed with a separate
   `${FRONTEND_IMAGE_TAG}` variable rather than a local re-tag workaround
   (CLAUDE.md: find root causes, no temporary fixes).
4. **Docker install on `vm-baseline-app` is new baseline work** — nothing
   there today but Python 3.12/venv/Nginx (US-PLT-20). This is the
   asymmetry already flagged in US-PLT-22's deployment-time writeup.
5. **Stop, don't delete, Stage 1.** `bookstore-monolith` (systemd) and the
   host Nginx both need to stop — Compose's `frontend` container claims host
   port 80 too. Stop/disable only; leave the venv/build/systemd unit intact
   so Stage 1 can be started again later for the live demo (per
   `sprint-plan.md`'s "Final demo storyline" — Stage 1 has to come back for
   the exam, and a `switch-to-stage1.sh`/`switch-to-stage2.sh` pair is
   already flagged there as a near-term follow-up once this story lands).
6. **Fresh secrets for Stage 2**, not reused from Stage 1 — different
   deployment, independent security domain, same practice as every prior
   VM story.
7. **Docker's `insecure-registries` trust config** needed in
   `/etc/docker/daemon.json` before `docker pull` from a non-TLS registry
   works — the Docker-daemon equivalent of the containerd `certs.d` trust
   config already done for the k8s nodes in US-PLT-23.

## Plan

### Compose file (agent writes/fixes)
- [x] `deploy/docker/docker-compose.yml` — `FRONTEND_IMAGE_TAG` fix (done
      above, before anything else touches this file).

### Runbook (agent writes, user executes against the real VM)
- [x] `deploy/baseline-vm/US-PLT-21-runbook.md` written (Parts A-G below):
  - Part A: stop Stage 1 (`systemctl stop bookstore-monolith`, stop Nginx),
    confirm port 80 free.
  - Part B: install Docker + Compose plugin on `vm-baseline-app`; configure
    `insecure-registries` for `172.16.200.23:5000`.
  - Part C: copy `deploy/docker/` to the VM; write a fresh `.env` (new
    generated secrets, `IMAGE_TAG=0.1.1-a08a02d`,
    `FRONTEND_IMAGE_TAG=0.0.0-1c39d25`).
  - Part D: pull all six images from the registry, retag locally to match
    what compose expects, confirm no `build:` gets triggered.
  - Part E: `docker compose up -d`, confirm all migration/seed jobs exit 0
    and all services reach healthy.
  - Part F: full customer-journey walkthrough (register → browse → cart →
    checkout → order history) against `http://172.16.200.24/` — AC#1.
  - Part G: record versions (image digests, commit hash) for the fairness
    control (PMP 17.4) — AC#2.

### Evidence + writeup
- [ ] Screenshot/confirm the full journey; save under
      `evidence/baseline-comparison/` alongside US-PLT-22's Stage 1 evidence.
- [ ] Update `documents/backlog/sprint-plan.md` (Period 5 table) and
      project `MEMORY.md`.
- [ ] Flag (not yet build, unless asked) the `switch-to-stage1.sh`/
      `switch-to-stage2.sh` follow-up now that Stage 2 is real on this VM.

## Review

(pending — fill in after execution)
