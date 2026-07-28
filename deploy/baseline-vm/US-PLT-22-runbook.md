# US-PLT-22 Runbook: Capture Stage 1 baseline comparison metrics

Target: `vm-baseline-app` (172.16.200.24, Stage 1 monolith + Nginx) and
`vm-baseline-db` (172.16.200.25, PostgreSQL + Redis). Load generator: your
own laptop (native k6, already installed per US-PLT-15/18).

**Why now, and why before US-PLT-21:** once US-PLT-21 redeploys
`vm-baseline-app` to the Stage 2 Compose stack, Stage 1 stops existing on
this VM and this measurement window is gone for good (PMP 10.1's own stated
precondition for reusing the VM). Run every part of this runbook before
touching anything for US-PLT-21.

Run each numbered step yourself; paste back the output if anything errors.

## Part A — Preflight: confirm Stage 1 is healthy and monitored

1. Confirm the monolith is up and serving real data:
   ```sh
   curl http://172.16.200.24/api/books
   ```
   Expect 16 seeded books, JSON.

2. From your laptop, over the VPN, confirm Prometheus already has both
   baseline VMs' Node Exporter targets `UP` (US-PLT-18 — should already be
   true, this just re-confirms nothing regressed):
   `http://172.16.200.23:9090/targets` → `node-exporter` group →
   `vm-baseline-app` and `vm-baseline-db` both `UP`.

3. Record the version being measured — on `vm-baseline-app`:
   ```sh
   cd ~/monolith && git rev-parse HEAD 2>/dev/null || echo "no .git on VM - record the commit used to build the deployed tarball instead"
   ```
   (The VM copy is unpacked from a tarball, not a git clone — if this prints
   nothing, instead record, on your own machine, `git rev-parse HEAD` from
   the repo root at the moment you build/package the redeploy in Part B.)

4. Document cache/data state (PMP 17.4's "reset or document cache state"
   control) — this is **not** a clean-slate environment:
   ```sh
   sudo -u postgres psql -d bookstore -c "SELECT count(*) FROM catalog.books;"
   ```
   Note the row count and that Postgres/Redis have been live since Period 3
   testing (US-PLT-20) — carried forward as-is, not reset, since resetting
   real seeded data isn't part of this story's scope.

5. Confirm no competing workload is running against either VM right now
   (no other SSH sessions mid-deploy, no other load test in flight) — PMP
   17.4's "similar time period, no competing workload" control.

## Part B — Deployment/setup time (re-timed app-layer redeploy)

**What this measures and what it deliberately doesn't:** this times a fresh
redeploy of the *application layer* only — the VM's OS, Python runtime, and
Nginx are already installed and stay untouched, exactly as they'll still be
untouched when US-PLT-21 later reuses this VM for Stage 2. It does **not**
include installing Docker, which Stage 2's own deployment/setup-time number
*will* have to include as new baseline work on this VM — flag that asymmetry
in the writeup rather than let the two numbers look directly comparable when
they aren't (PMP 17.4: don't overclaim from an unlike-for-like measurement).

1. Back up the current `.env` before removing anything — it holds the real
   generated DB passwords/JWT secret from US-PLT-20 and you want to reuse
   them, not regenerate:
   ```sh
   cp ~/monolith/.env ~/monolith.env.bak
   ```

2. **Start the stopwatch now.** Stop the service and remove the old
   deployed code/build:
   ```sh
   sudo systemctl stop bookstore-monolith
   rm -rf ~/monolith
   sudo rm -rf /var/www/bookstore/*
   ```

3. From your Windows machine, rebuild the frontend fresh and repackage the
   monolith (same commands as US-PLT-20 Phase 2 step 2 — record
   `git rev-parse HEAD` here as this run's version if Part A step 3 found no
   `.git` on the VM):
   ```sh
   cd apps/frontend
   npm run build
   cd ../..
   tar --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' \
       --exclude='.import_linter_cache' -czf monolith.tar.gz -C apps monolith
   scp monolith.tar.gz student@172.16.200.24:~/
   scp -r apps/frontend/dist student@172.16.200.24:~/frontend-dist
   ```

4. On `vm-baseline-app`, unpack, rebuild the venv, and restore `.env`:
   ```sh
   tar -xzf monolith.tar.gz
   cd monolith
   python3.12 -m venv .venv
   .venv/bin/pip install -e .
   cp ~/monolith.env.bak .env
   chmod 600 .env
   ```

5. Migrations and seed data (both idempotent — expect "no changes"/no-op,
   this is proving repeatability again, not loading new data):
   ```sh
   .venv/bin/alembic upgrade head
   .venv/bin/python scripts/seed_catalog.py
   .venv/bin/python scripts/seed_inventory.py
   ```

6. Frontend into the web root:
   ```sh
   sudo mkdir -p /var/www/bookstore
   sudo cp -r ~/frontend-dist/* /var/www/bookstore/
   sudo chown -R www-data:www-data /var/www/bookstore
   ```

7. Restart the service:
   ```sh
   sudo systemctl start bookstore-monolith
   sudo systemctl status bookstore-monolith    # expect active (running)
   ```

8. **Stop the stopwatch the moment this returns 200 with real data** — this
   also doubles as the "application startup/readiness" sub-metric (PMP
   17.2), timed from step 7's start command to this first success:
   ```sh
   curl http://172.16.200.24/api/books
   ```

9. Record: total elapsed time (step 2 → step 8), and the elapsed time for
   just step 7 → step 8 (startup/readiness alone) if you noted an
   intermediate timestamp. Walk the full customer journey once
   (register → browse → cart → checkout → order history) to confirm the
   redeploy didn't silently break anything before moving to load testing.

## Part C0 — one-time: import the baseline-VM dashboard

The existing Grafana dashboard (`grafana-dashboard.json`, US-PLT-18) is
explicitly titled "Stage 3 Kubernetes Observability" and most of its rows
(Scalability, Resilience, per-pod resources, PVC status) only have data for
the Kubernetes cluster — they'd sit blank for every Stage 1 screenshot. A
second, reusable dashboard was built instead, scoped to what a VM-hosted
stage actually has: `infrastructure/monitoring/grafana-dashboard-baseline.json`.
It's used for both this story and, later, US-PLT-21's Stage 2 comparison —
build it once now.

From **your laptop**:
```sh
scp infrastructure/monitoring/grafana-dashboard-baseline.json student@172.16.200.23:~/
```

On **`registry-monitoring`**:
```sh
sudo mv ~/grafana-dashboard-baseline.json /srv/monitoring/grafana/grafana-dashboard-baseline.json
```
(reuses the bind-mounted directory the Grafana container already has from
US-PLT-18 — no container restart needed for a new file to appear there.)

From **your laptop**, in Grafana (`http://172.16.200.23:3000`): Dashboards →
New → Import → Upload JSON file → select the copy under
`/var/lib/grafana/dashboards/grafana-dashboard-baseline.json` (or paste its
contents directly) → pick the existing Prometheus data source.

**If you already imported an earlier copy of this file** (the p99
latency/error-rate panels were fixed after a real run showed a dozen
identically-labeled lines instead of one — k6 tags each trend/rate stat by
request URL/method/status/scenario, and this script deliberately varies the
request, so the bare metric name fragmented into one series per combination):
re-import the corrected file the same way — Grafana treats a same-`uid`
import as an update to the existing dashboard, not a duplicate.

**Known limitation, carried over from the existing dashboard, not fixed by
this one:** the "Load and outcome" row's k6 metrics (`k6_vus`,
`k6_http_reqs_total`, `k6_http_req_duration_p99`, `k6_http_req_failed_rate`)
aren't tagged by stage at the Prometheus level — they show whichever k6 run
is currently in flight, regardless of which stage it targeted. Only run one
stage's load test at a time, and the screenshot's own timestamp (not the
panel) is what proves it was a Stage 1 run.

## Part C — P1/P2/P3 load scenarios

Run each scenario **3 times when time permits** (PMP 15.4) — report the
median for primary metrics, keep the range. Same load-generator (your
laptop), same script, same dataset, same request mix and duration across all
repeats and across P1/P2/P3 (PMP 17.4 fairness control).

For each scenario and each repeat:

```sh
k6 run -e SCENARIO=p1 --out experimental-prometheus-rw ^
  -e K6_PROMETHEUS_RW_SERVER_URL=http://172.16.200.23:9090/api/v1/write ^
  tests/load/baseline-p1-p3.js
```
(renamed from `stage1-baseline-p1-p3.js` once reused for Stage 2/Stage 3 —
same script, only `BASE_URL` changes per stage; swap `SCENARIO=p1` for `p2` /
`p3` — durations are 3 min / 5 min / 8 min respectively, VUs 5 / 10 / 25,
both already the script's defaults.)

While each run is in progress:
- Watch `http://172.16.200.23:3000` (Grafana), the new **Baseline VM
  Observability** dashboard — Environment summary, Load and outcome, and
  Resources/Storage-network rows. Screenshot each run.
- On `vm-baseline-app` and `vm-baseline-db`, sample resource use partway
  through the run (`top -bn1 | head -15`, `free -h`, `df -h /`) — Node
  Exporter/Grafana already shows this over time, but a raw sample is useful
  corroborating evidence.

After each run finishes, k6 prints its own summary to the terminal — copy it
(or redirect with `--summary-export=` to a JSON file) and save it under
`evidence/baseline-comparison/stage1-p1-p3/` (see naming convention below).

**Naming convention** (mirrors `evidence/hpa/`'s per-run folders):
```
evidence/baseline-comparison/stage1-p1-p3/
  p1-run1/  p1-run2/  p1-run3/
  p2-run1/  p2-run2/  p2-run3/
  p3-run1/  p3-run2/  p3-run3/
```
Each folder: the k6 summary (text or `--summary-export` JSON) and the
Grafana screenshot(s) taken during that run.

## Part D — Writeup

Once all runs are captured, I'll (agent) draft
`evidence/baseline-comparison/US-PLT-22-stage1-metrics.md` from your saved
evidence — a median/range table per PMP 17.2's metric list, explicit `N/A`
entries for replica count / pod restarts / recovery time (no orchestrator in
Stage 1), and the deployment/setup-time asymmetry note from Part B. Report
back once Parts A–C are done and I'll write it and update
`documents/backlog/sprint-plan.md` / `MEMORY.md`.
