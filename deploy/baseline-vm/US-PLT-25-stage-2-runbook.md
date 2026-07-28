# US-PLT-25 Runbook: Stage 2 baseline comparison metrics (P1-P3)

Target: `vm-baseline-app` (172.16.200.24), Stage 2 Compose stack (already
deployed, US-PLT-21). Load generator: your laptop, same k6 script as
Stage 1 (`tests/load/baseline-p1-p3.js`, renamed from
`stage1-baseline-p1-p3.js` — same script, same dataset, same request mix,
only `BASE_URL` differs, per PMP 17.4's fairness control).

## Part A — Optional: clean deployment/setup time re-measurement

Stage 1's deployment time (4 min 30 sec) was a deliberately clean, isolated
re-timed run. Stage 2's actual US-PLT-21 deploy wasn't — it included live
debugging of the frontend healthcheck bug, so that elapsed time isn't a fair
comparison number. If you want a real one (recommended, for a fair
Stage 1-vs-2 comparison — otherwise this metric stays a known gap for
Stage 2): images are already pulled/retagged locally, so this only measures
orchestration/migration/seed time, not a fresh pull:

```sh
cd ~/deploy-docker
docker compose down          # keeps named volumes - no data loss, confirm after with `docker volume ls`
# start the stopwatch now
docker compose up -d
# stop the stopwatch once this returns healthy for all 8:
watch -n2 docker compose ps
```
Record the elapsed time, then confirm nothing was lost:
```sh
curl http://172.16.200.24/api/books    # still 16 books
```

## Part B — P1/P2/P3 load scenarios

Same cadence as Stage 1: each scenario 3x when time permits, same
load-generator, same script, same dataset (Stage 2's catalog was seeded
fresh during US-PLT-21 — 16 books, content-equivalent to Stage 1's, not the
literal same row IDs, which is the expected/accepted fairness compromise
already used for Stage 1 too).

```sh
k6 run -e SCENARIO=p1 --out experimental-prometheus-rw \
  -e K6_PROMETHEUS_RW_SERVER_URL=http://172.16.200.23:9090/api/v1/write \
  tests/load/baseline-p1-p3.js
```
(swap `SCENARIO=p1` for `p2`/`p3`; `BASE_URL` defaults to
`http://172.16.200.24`, no override needed for Stage 2.)

While each run is in progress, watch `http://172.16.200.23:3000`'s
**Baseline VM Observability** dashboard (already correctly scoped from
US-PLT-22 — no changes needed) and screenshot it. Sample
`top -bn1 | head -15` / `free -h` / `df -h /` on `vm-baseline-app` partway
through each run, same as Stage 1.

**Note the environment difference from Stage 1 while sampling:** Stage 2 now
runs 8 containers (postgres, redis, 5 services, frontend) on the same 2
vCPU/4 GB instead of Stage 1's single monolith process + Nginx — expect
higher idle/baseline memory just from that, independent of load level (this
was predicted before Stage 2 was even deployed; now it's something to
actually confirm from real data).

## Part C — Evidence

Save under `evidence/baseline-comparison/stage2-p1-p3/{p1,p2,p3}-run/` —
same naming convention as Stage 1's (`p1-run1.json`, `p1-run1-graph.png`,
`p1-run1-vm-output.png`, etc.).

Report back once all runs are done and I'll draft
`evidence/baseline-comparison/US-PLT-22-stage2-metrics.md` from the saved
evidence, same format as the Stage 1 writeup.
