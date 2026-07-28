# US-PLT-22: Stage 1 baseline comparison metrics

**Captured:** 27 Jul 2026, against `vm-baseline-app` (172.16.200.24) /
`vm-baseline-db` (172.16.200.25), before US-PLT-21 redeploys the same VM to
Stage 2. Deployed version: monolith at commit `14e619e6` (repo HEAD at the
time of the Part B redeploy — no commits landed between then and this
writeup). No image digest — Stage 1 has no container images.

## Fairness controls applied (PMP 17.4)

- Same load-generator: the user's laptop, native k6, for every run.
- Same script (`tests/load/stage1-baseline-p1-p3.js`), same request mix and
  duration per scenario, across all 3 repeats of P1/P2/P3.
- Same dataset: the 16-book catalog seeded in Period 1/3 — **not** reset to a
  clean slate; Postgres/Redis have been live since Period 3 testing and this
  run reused that state as-is, per the runbook's Part A cache-state note.
- All 9 runs (3 scenarios × 3 repeats) executed in one session, back to back,
  with no competing workload on either VM.
- Warm-up (P1) excluded from the P2/P3 measured comparison, per PMP 15.4/17.4
  — reported separately below, not folded into the P2/P3 numbers.

## Deployment/setup time

**4 min 30 sec**, timed live (re-timed app-layer redeploy: stop service →
remove venv/dist → rebuild/repackage → redeploy → first successful
`/api/books` through Nginx). Startup/readiness alone (service start → first
success) was not separately timestamped this run — only the total is
available.

**Scope caveat, not an oversight:** this number covers the *application
layer* only. The VM's OS, Python 3.12 runtime, and Nginx were already
installed (from US-PLT-20) and stayed untouched. US-PLT-21's Stage 2 number
will have to include installing Docker on this same VM — new baseline work
Stage 1's number never had to do. Don't read the two figures as directly
comparable without that asymmetry noted (PMP 17.4: don't overclaim from an
unlike-for-like measurement).

## P1 / P2 / P3 results (median of 3 runs, range in parentheses)

| Scenario | Workload | RPS | Avg latency | p95 latency | Error rate |
|---|---|---|---|---|---|
| P1 — Warm-up | 5 VUs, catalogue browse, 3 min | 4.84 req/s (4.83–4.84) | 31.09 ms (31.06–32.07) | 47.25 ms (45.58–47.81) | 0% (all 3 runs) |
| P2 — Normal | 10 VUs, mixed browse/login/cart, 5 min | 12.43 req/s (12.31–12.52) | 401.58 ms (398.82–407.08) | 1232.04 ms (1231.66–1249.68) | 0% (all 3 runs) |
| P3 — Moderate | 25 VUs, catalogue-heavy, 8 min | 24.06 req/s (24.04–24.13) | 36.50 ms (34.22–37.29) | 56.38 ms (50.90–61.37) | 0% (all 3 runs) |

p95 figures come directly from each run's k6 JSON summary
(`--summary-export`), which computes true percentiles locally — **not** the
Grafana dashboard's p99-only remote-write limitation already logged for
US-PLT-15/18. That limitation still applies to the *live Grafana view*
during a run, but the JSON evidence saved per run genuinely has p95, so PMP
17.2's literal "p95" requirement is met by the JSON artifacts even where the
dashboard screenshot only shows p99.

Raw per-run numbers: `evidence/baseline-comparison/stage1-p1-p3/{p1,p2,p3}-run/*.json`.

## Resources (CPU / memory / disk / network)

Sampled via `top -bn1`/`free -h`/`df -h` on `vm-baseline-app` mid-run (raw
snapshot, one per run — see `*-vm-output.png`), corroborated by the Baseline
VM Observability Grafana dashboard (`*-graph.png`, `storage & network-*.png`).

| Scenario | VM CPU (user+sys) | VM memory used | Disk used | Network throughput (peak) |
|---|---|---|---|---|
| P1 | ~8.4% (4.2% us / 4.2% sy), 91.7% idle | ~38% (1.49 / 3.92 GiB) | 15% (7.2G/51G), unchanged | ~30–40 KB/s |
| P2 | **~100% (69.0% us / 31.0% sy), 0.0% idle** | ~49% (1.9 / 3.92 GiB) | 15%, unchanged | ~50–60 KB/s |
| P3 | ~8.6% (4.3% us / 4.3% sy), 91.3% idle | ~38% | 15%, unchanged | ~60–80 KB/s |

Disk usage stayed flat at 15% (root) across every run — this workload at
this scale doesn't grow disk usage measurably.

## Key finding: Argon2 password hashing, not catalogue reads, is Stage 1's real CPU cost

**Non-obvious result worth recording, not smoothing over:** P3 (25 VUs,
catalogue-only) drove barely more CPU than P1 (5 VUs, same workload type) —
8.6% vs 8.4%, despite 5x the virtual users and 5x the request rate. But P2
(only 10 VUs, adding one login per iteration on top of the same catalogue
browsing) drove this 2 vCPU VM to **full CPU saturation** — 0.0% idle, the
`uvicorn` process alone showing 164.3% CPU (multi-core) in the `top`
snapshot. Catalogue reads are cheap at this scale; Argon2 password
verification on every login is the dominant, deliberately-CPU-expensive cost
(a security property, not a bug — see US-ID-01's Argon2 hashing). This
matters directly for the Stage 1-vs-2-vs-3 report: any conclusion about
"headroom" or "capacity" from this baseline has to account for the fact that
an auth-heavy traffic mix saturates this VM's CPU an order of magnitude
faster than a browse-heavy mix does, independent of request *count*.

Despite full CPU saturation, P2 still recorded **0% errors** across all 3
runs — requests queued and completed slower (400ms avg / 1.2s p95 vs P1/P3's
30-60ms), rather than failing. Worth noting against NFR-02 (500ms avg /
1000ms p95 target): P2's avg (401ms) is within target, but p95 (1232ms)
exceeds the 1000ms target — the first NFR-02 miss recorded in this project,
directly attributable to the CPU-saturation finding above, not a defect to
fix (Stage 1 has no autoscaling to add headroom; this is the baseline's
actual behavior under this specific traffic mix, exactly what the Stage
comparison exists to surface).

## Not applicable to Stage 1 (recorded explicitly, not omitted)

- **Replica count** — no orchestrator; Stage 1 is a single process pair.
- **Pod/process restarts** — none observed or expected; no supervisor beyond
  systemd's `Restart=on-failure`, never triggered during these runs.
- **Recovery time** — no self-healing mechanism exists in Stage 1 to measure;
  this metric applies starting at US-PLT-16 (Kubernetes self-healing).

## Known limitations carried into this evidence

- k6's Prometheus remote-write metrics (`k6_vus`, RPS, p99, error rate on the
  Grafana dashboard) aren't tagged by stage — only "one stage's test running
  at a time" plus each screenshot's own timestamp identifies it as Stage 1,
  not the panel itself.
- The p99/error-rate Grafana panels show an **unweighted average** across
  k6's per-request-type series (different URLs/statuses each get their own
  underlying series) — a blended approximation, not a mathematically
  recomputed global percentile or volume-weighted error rate. The JSON
  summary's `http_req_duration`/`http_req_failed` figures used in the table
  above are k6's own real aggregates and don't have this limitation.
- Deployment/setup time is a single measurement, not a 3-run median (PMP
  15.4's "3 times when time permits" applies to the formal P1–P3 load
  scenarios, not the one-off deploy timing).

## Evidence index

```
evidence/baseline-comparison/stage1-p1-p3/
  p1-run/  p1-run{1,2,3}.json, p1-run{1,2,3}-graph.png, p1-run{1,2,3}-vm-output.png
  p2-run/  p2-run{1,2,3}.json, p2-run{1,2,3}-graph.png, p2-run{1,2,3}-vm-output.png
  p3-run/  p3-run{1,2,3}.json, p3-run{1,2,3}-graph.png, p3-run{1,2,3}-vm-output.png
  storage & network-{1..5}.png  (Storage/network row, sampled across runs)
```
