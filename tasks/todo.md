# Stage 2 / Stage 3 baseline comparison metrics (P1-P3)

**Not a numbered backlog story** — per `sprint-plan.md`'s Period 5 notes,
running P1-P3 against Stage 2/3 is "test execution time," the same bucket as
the acceptance-test suite and the comparison writeup itself. Doing it now,
before US-PLT-16/17's destructive tests, so the "normal/moderate load"
baseline reflects steady state, not a just-recovered/just-rolled-out
cluster — same "capture clean data before the environment gets perturbed"
logic that put US-PLT-22 ahead of US-PLT-21, just without a hard deadline.

## Prep done already
- [x] Renamed `tests/load/stage1-baseline-p1-p3.js` → `baseline-p1-p3.js`
      (`git mv`, history preserved) — script was always stage-neutral via
      `BASE_URL`, just misleadingly named. Updated references in
      `US-PLT-22-runbook.md`, `US-PLT-22-stage1-metrics.md`.
- [x] Checked Catalog HPA's current state before assuming a clean baseline:
      `kube_horizontalpodautoscaler_status_current_replicas{horizontalpodautoscaler="catalog-hpa"}`
      = **1** — clean, no leftover scale-up from US-PLT-15 testing.
- [x] Proactively fixed the identical p99/error-rate cardinality-fragmentation
      bug (found and fixed in `grafana-dashboard-baseline.json` during
      US-PLT-22) in the **original** Stage 3 dashboard
      (`infrastructure/monitoring/grafana-dashboard.json`, panels 13/14) —
      about to trigger it for real with this same script against Stage 3,
      no reason to hit it twice. Needs re-import in Grafana (same UID,
      updates in place).

## Plan
- [x] Stage 2 runbook (`deploy/baseline-vm/stage2-baseline-p1-p3-runbook.md`)
      written — reuses `grafana-dashboard-baseline.json` unchanged, plus an
      optional clean deployment-time re-measurement (Stage 2's US-PLT-21
      deploy included live bug debugging, so that elapsed time isn't a fair
      comparison number).
- [x] Stage 3 runbook (`deploy/kubernetes/stage3-baseline-p1-p3-runbook.md`)
      written — targets `http://172.16.200.20:30080` (Ingress), reuses the
      now-fixed `grafana-dashboard.json`. Explicit note: unlike Stage 1/2,
      Catalog has an HPA - if P3's 25 VUs pushes it to scale, that's real
      Stage 3 behavior to record, not a confound to suppress or avoid.
- [ ] Evidence: `evidence/baseline-comparison/{stage2,stage3}-p1-p3/`, same
      `{p1,p2,p3}-run/` substructure as Stage 1's.
- [x] Stage 2 writeup: `US-PLT-22-stage2-metrics.md` done. Real findings:
      Argon2 CPU-saturation finding replicates in Stage 2 (P2, same as
      Stage 1); idle/baseline memory measurably higher at every load level
      (more processes); P3's raw CPU ~3.5x Stage 1's for identical
      workload but latency ends up nearly the same (enough idle headroom
      to absorb it); P1's latency is dramatically worse (~6x avg, ~20x
      p95) with CPU *not* saturated - flagged honestly as unconfirmed
      (two plausible contributors given, neither proven). **Prominent
      caveat added up top, not buried in a table:** Stage 1 had Postgres/
      Redis on a separate dedicated VM (4 vCPU/8GB combined app+data);
      Stage 2 squeezes everything onto one 2 vCPU/4GB VM - any
      "Stage 2 is slower" reading is partly a hardware-topology confound,
      not purely orchestration overhead (PMP 17.1 Q6).
- [x] Deployment-time re-measurement (Part A): **42 seconds** (user ran it).
      Flagged as not directly comparable to Stage 1's 4m30s — this run
      started from already-cached local images (from US-PLT-21), so it
      measures orchestration/restart time only, not a cold pull+deploy.
- [x] P1's outlier question resolved from existing data, no re-run needed:
      checked full `http_req_duration` breakdown (min/med/p90/p95/max) per
      run - median was 35-42ms across all 3 runs, barely different from
      Stage 1's P1 average (31ms). The average/p95 gap is driven by a
      small number of extreme outliers (max 1.8-2.9 seconds per run), not
      a systemic slowdown - consistent with cold/low-concurrency
      connection setup at only ~4-5 req/s, though not fully proven.
      Writeup updated with the refined finding.
- [x] Stage 3 P1 x3 done, clean (no issues).
- **Real bug found during Stage 3 P2 run1: Identity OOMKilled, sustained
  crash-loop for the whole test window.** `kubectl describe pod` confirmed
  `Reason: OOMKilled, Exit Code: 137`, `BackOff (x18 over 16m)` - not a
  single crash, a persistent loop. Root cause traced to real code, not
  guessed: `apps/services/identity/app/core/security.py`'s
  `PasswordHasher()` uses argon2-cffi's default `memory_cost=65536 KiB`
  (64 MiB) *per hash operation* - a few concurrent logins' hashing buffers
  alone approached the old 256Mi container limit. Directly violates
  NFR-08 ("no pod is OOMKilled... under normal load") - P2 literally *is*
  PMP 15.4's "Normal" load scenario, not an edge case.
  **Fix (confirmed with user via AskUserQuestion): raise the K8s memory
  limit, not weaken Argon2.** `deploy/kubernetes/21-identity.yaml`:
  128Mi/256Mi -> 256Mi/512Mi request/limit. Kubernetes-manifest-only,
  doesn't touch the shared Identity image (ADR-007) - Stage 2 completely
  unaffected, same "smallest blast radius" precedent as the frontend
  healthcheck fix. Rejected: reducing Argon2's `memory_cost` - would also
  affect Stage 2 (shared image) and is a real security trade-off (weakens
  GPU/ASIC brute-force resistance), not just an infra tweak.
  User applying the fix and re-running all 3 P2 repeats fresh (run1's data
  is invalid - crash-loop artifact, not real measurement).
- [ ] Stage 3 P2 x3 (re-run pending, post-fix) and P3 x3 (not started).
- [ ] Stage 3 writeup: `US-PLT-22-stage3-metrics.md` (pending all runs) -
      must include the OOMKill finding prominently, same as Stage 2's
      hardware-topology caveat was surfaced up top, not buried.
      Full three-way comparison analysis (PMP 17.4) deferred to
      report-drafting time, not done here.
- [ ] Update `MEMORY.md` once both stages are captured.

---

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

## Execution log

- Part D blocked initially: `student` wasn't in the `docker` group (same
  class of finding already logged from US-PLT-18) — fixed with
  `usermod -aG docker student` + a fresh session, added to the runbook's
  Part B for next time rather than patching each command with `sudo`.
- Part E: all migrate-*/seed-* jobs exited 0, all app services healthy
  except `frontend`, which showed `Up ... (unhealthy)` despite
  `docker logs` showing the full customer journey already working for
  real (register/login/cart/checkout/order-history, real 200/201s).
  Diagnosed live rather than assumed cosmetic: `ss -tln` inside the
  container showed nginx listening only on `0.0.0.0:8080` (no IPv6), and
  the Dockerfile's `HEALTHCHECK` used unqualified `http://localhost:8080/`
  - this image's Alpine resolver resolves `localhost` to `::1` first,
    which nginx never listens on. Confirmed with a forced-IPv4
  `wget http://127.0.0.1:8080/` succeeding instantly (exit 0) where
  `localhost` failed every time (`FailingStreak: 76` — a real, persistent
  failure, not a startup-timing fluke). Pre-existing since Period 2, never
  caught before because nothing in Compose `depends_on: frontend`'s
  health, so it never actually blocked anything.
  **Fixed, Stage 2 only** (user's explicit choice, confirmed via
  AskUserQuestion): Kubernetes' `httpGet` probes bypass this path entirely
  (kubelet hits the pod IP directly, not through the container's own
  `wget`), so Stage 3 was never affected and wasn't touched — redeploying
  there would have meant risk to an already-working system for a bug it
  never had. User committed the one-line Dockerfile fix
  (`localhost`→`127.0.0.1`, commit `57a1e9e`) before rebuilding, so the
  image's commit-hash tag stays honest (`build-scan-push.sh` tags by
  current `git rev-parse HEAD`, not by working-tree state). Rebuilt/
  Trivy-scanned/pushed `bookstore/frontend:0.0.0-57a1e9e`, pulled/retagged
  on the VM, `FRONTEND_IMAGE_TAG` updated, `docker compose up -d frontend`
  — confirmed `Up ... (healthy)`, all 8 services healthy.

## Review

**Done and verified — US-PLT-21 complete, Period 5 at 6/11 points.**

Full customer journey (register → browse → cart → checkout → order history)
confirmed working against the VM-hosted Compose stack via real nginx access
logs (200/201s throughout) — AC#1 met. Both stages now measured on
identical hardware (`vm-baseline-app`, 2 vCPU/4 GB) — AC#2 met.
`vm-baseline-db` was never touched (Stage 2 is fully self-contained, its own
Postgres/Redis containers, per PMP 10.1's own stated plan). Versions
recorded: five backend services at `0.1.1-a08a02d`, frontend at
`0.0.0-57a1e9e` (post-fix), full digests in the runbook's Part G.

One real pre-existing bug found and fixed along the way (frontend
HEALTHCHECK's `localhost`→IPv6 resolution issue, see execution log above and
`MEMORY.md`) — Stage 2 only, Kubernetes was never affected and wasn't
touched, confirmed with the user before proceeding. One proactive fix made
before deployment: `docker-compose.yml`'s shared `${IMAGE_TAG}` across all
six services was split into a separate `${FRONTEND_IMAGE_TAG}`, avoiding a
repeat of the identical single-shared-tag bug already caught once in the
Kubernetes deployment (US-PLT-13/24).

`documents/backlog/sprint-plan.md` and `MEMORY.md` updated. Next in Period
5: US-PLT-16 (self-healing validation) and US-PLT-17 (rolling
update/rollback), both Kubernetes-side. The `switch-to-stage1.sh`/
`switch-to-stage2.sh` pair flagged in the "Final demo storyline" is now
buildable (Stage 2 is real on this VM) but not yet started — worth raising
before Period 5 wraps up.
