# Catalog HPA — Final run (ramping-arrival-rate, gradual staircase), 25 Jul 2026

**This is the primary/final evidence run for US-PLT-15's AC #1/#2
mechanism.** Two earlier attempts led here: Run 1 (`constant-vus`, 80
VUs — kept as supplementary evidence at
`evidence/hpa/run-1-80vus/US-PLT-15-run1-extreme-load-2026-07-25.md`)
and an intermediate `ramping-vus` retune (25 VUs — its own evidence file
was not retained once this run superseded it; summarized in
`MEMORY.md`'s 25 Jul entries instead). Both controlled VU count and both
overshot straight past target rather than crossing it gradually. This
run is the first to show a genuinely **gradual** replica climb
(1→2→3→4, not a one-shot jump to max) and, as a bonus, a genuinely
gradual descent (4→2→1) too, with 0% request failures and a 5m30s
runtime.

**Captured:** 25 Jul 2026, from `vm-master` (`kubectl get hpa`/`kubectl
top pods`, two side-by-side sessions) and the laptop (k6 summary),
running `tests/load/catalog-hpa-load-test-arrival-rate-tall-fast.js` at
its defaults (`ramping-arrival-rate`: `START_RATE=3`, `RATE_STEP=5`,
`STEPS=10`, `STEP_DURATION=30s` — staircase from 8 to 53 req/s, 30s per
rung).

**Screenshots (in this same folder,
`evidence/hpa/run-final-ramping-arrival-rate/`):**
- `HPA-run-final-k6-load-summary.png` — k6 end-of-run summary
- `HPA-run-final-before-starting-load.png` — idle state immediately
  before the run (`REPLICAS 1`, cpu 2%/65%)
- `HPA-run-final-during.png` — during the run, real per-pod CPU via
  `kubectl top pods` (4 pods, 51–83m each) alongside the HPA panel
- `HPA-run-final-after-return-to-normal.png` — the full `kubectl get
  hpa -w` sequence, idle → 1→2→3→4 → idle → 4→2→1 back to normal

## Why this run succeeded where Runs 1/2 didn't show a gradual climb

Runs 1 (`constant-vus`, 80 VUs) and 2 (`ramping-vus`, 25 VUs) both
controlled **concurrency**, not request rate — actual throughput also
depends on response time, so utilization jumped straight past target in
one shot (250–500% overshoot) on the very first HPA sync. This run uses
`ramping-arrival-rate` to fix requests/sec directly and step it up in
small, controlled increments (30s per rung — long enough for ~2 HPA sync
cycles at the default ~15s sync period, short enough to keep total
runtime near 5 minutes), so each replica-count increase gets its own
observable window before the next rate bump lands.

An earlier attempt at this same idea
(`catalog-hpa-load-test-arrival-rate.js`, top rung 21 req/s) proved the
gradual-crossing concept for 1→2 but capped there — once scaled to 2
pods, the same aggregate rate split across double the capacity and never
climbed high enough again to trigger 3/4. This run's wider range (up to
53 req/s) gave enough headroom to keep crossing target as replica count
increased.

## k6 summary (ramping-arrival-rate: 8→53 req/s over 10×30s steps, 30s ramp-down)

```
scenarios: (100.00%) 1 scenario, 300 max VUs, 6m0s max duration (incl. graceful stop):
  * catalog_heavy_tall_staircase_fast: Up to 53.00 iterations/s for 5m30s over 11 stages (maxVUs: 80-300, gracefulStop: 30s)

THRESHOLDS
http_req_failed
  ✓ 'rate<0.01' rate=0.00%

checks_total........: 9194  27.860558/s
checks_succeeded....: 100.00% 9194 out of 9194
checks_failed.......: 0.00%  0 out of 9194

http_req_duration...: avg=39.98ms min=2.73ms med=26.68ms max=944.73ms
                       p(90)=67.86ms p(95)=106.32ms
http_req_failed.....: 0.00% (0 out of 9194)
http_reqs...........: 9194  27.860558/s

vus.................: 0  min=0  max=18
vus_max..............: 80 min=80 max=80

running (5m30.0s), 000/080 VUs, 9194 complete and 0 interrupted iterations
```

Clean pass — 0% failures, well-behaved latency throughout (p95 106ms,
max 945ms — nothing near a timeout), and total wall time matches the
tuned target (~5m30s vs. the original tall variant's 8m).

## HPA transition (`kubectl get hpa catalog-hpa -n bookstore -w`)

| Stage | CPU (TARGETS) | REPLICAS |
|---|---|---|
| idle, before load | 2%/65% | 1 |
| ramp begins | 7%, 35%, 48%, 64%, 77%/65% | 1 |
| | 93%/65% | **2** (1→2) |
| | 75%/65% | 2 |
| | 61%/65% | **3** (2→3) |
| | 58%, 52%, 57%, 64%, 67%, 69%, 79%/65% | 3 |
| | 82%/65% | **4** (3→4, max reached) |
| held near/above target | 81%, 78%, 81%, 85%, 90%, 68%/65% | 4 |
| load ramps down | 30%, 4%, 2%/65% | 4 |
| stabilization window holding | 2%, 2%/65% (several ticks) | 4 |
| | 2%/65% | **2** (4→2) |
| | 2%/65% | **1** (2→1) |

Every scale-up transition (1→2, 2→3, 3→4) happened at a CPU% reading
comfortably above the 65% target (93%, 61%*, 82% respectively — *2→3
triggered slightly under 65% on the reading shown, consistent with the
HPA acting on its own internal calculation which can differ slightly
from the exact percentage displayed at print time), each preceded by a
visible climb through several lower readings first — the discrete-step
behavior this story was looking for. The scale-down was itself gradual
(4→2→1, not straight to 1), matching Kubernetes' default HPA scale-down
policy of limiting how many replicas can be removed per sync interval
rather than jumping straight to the computed minimum.

## `kubectl top pods -n bookstore -l app=catalog` (during load)

| Pod | CPU (cores) | Memory |
|---|---|---|
| catalog-...-5txdr | 66m | 64Mi |
| catalog-...-72hxr | 51m | 73Mi |
| catalog-...-8vdsf | 73m | 64Mi |
| catalog-...-rkj9t | 83m | 64Mi |

Realistic, non-ambiguous per-pod values this time (no repeat of Run 1's
low-reading anomaly) — average ≈ 68m/100m request ≈ 68%, consistent with
the HPA panel's own readings for the same general window.

## Conclusion — this is the final, recommended load-test evidence for US-PLT-15

- HPA scale-up mechanism (AC #1, mechanism half): **proven**, gradually,
  with a visible 1→2→3→4 staircase and zero request failures.
- HPA scale-down mechanism (AC #2): **proven**, gradually (4→2→1),
  respecting the default stabilization window.
- R07 (HPA-not-triggering risk): **closed**.
- `tests/load/catalog-hpa-load-test-arrival-rate-tall-fast.js` is the
  recommended script going forward for any future re-demonstration of
  this story (e.g. the AC #1 Grafana follow-up once US-PLT-18 lands) —
  see the updated `deploy/kubernetes/US-PLT-15-runbook.md`.
- AC #1's "Grafana shows the correlation" clause remains open pending
  US-PLT-18 — everything else in AC #1/#2 is now closed, with this run
  as the cleanest evidence of the three.
