# Catalog HPA — Run 1 (extreme load), 25 Jul 2026

**Captured:** 25 Jul 2026, from `vm-master` (`kubectl get hpa`/`kubectl top
pods`, two side-by-side sessions) and the laptop (k6 summary), while
running `tests/load/catalog-hpa-load-test.js` at its **original** default
of a flat 80 VUs (`constant-vus`, no ramp — since tuned down, see
`tests/load/catalog-hpa-load-test.js`'s header comment and
`deploy/kubernetes/US-PLT-15-runbook.md` Part D).

**Why this run is labeled "extreme load" rather than the primary evidence
run:** 80 concurrent VUs with no think-time drove CPU utilization far past
the 65% target almost immediately (up to 430%) and caused 53.52% of k6's
requests to fail with `request timeout` — well past the `http_req_failed
<1%` threshold. This proves the HPA scale-up/scale-down *mechanism* works,
but at a load level far beyond what "crossing 65%" requires, with
collateral request failures that shouldn't be read as an app latency/
error-rate finding. Kept as evidence of the mechanism under stress; a
second, tuned run (`ramping-vus`, default 25 VUs) is the intended primary
evidence for a clean threshold crossing — see the runbook.

**Screenshots (save alongside this file in `evidence/hpa/`):**
- `US-PLT-15-run1-k6-summary.png` — k6 end-of-run summary
- `US-PLT-15-run1-hpa-scaleup.png` — `kubectl get hpa -w` showing the
  1→4 replica transition and CPU% climbing
- `US-PLT-15-run1-hpa-scaledown-toppods.png` — `kubectl get hpa -w`
  continued (4→1 replica transition after load stopped) alongside
  `kubectl top pods`

## k6 summary (80 VUs, 6 minutes, constant-vus)

```
checks_total........: 89743
checks_succeeded....: 46.47% (41705)
checks_failed.......: 53.52% (48038)

THRESHOLDS
http_req_failed
  ✗ 'rate<0.01' rate=53.52%

http_req_duration...: avg=321.33ms min=5.65ms med=28.81ms max=1m0s
                       p(90)=602.04ms p(95)=1s
http_req_failed.....: 53.52% (48038 out of 89743)
http_reqs...........: 89743  248.171338/s

vus.................: 51 min=51 max=80
vus_max..............: 80  min=80 max=80

running (6m01.6s), 00/80 VUs, 89743 complete and 0 interrupted iterations
ERRO[0361] thresholds on metrics 'http_req_failed' have been crossed
```

Failures were all `request timeout` errors against `/api/books*` endpoints
via the Ingress (`172.16.200.20:30080`) — consistent with request queueing/
CPU-limit throttling once aggregate load exceeded the 4-replica ceiling's
combined 500m×4 = 2000m CPU limit capacity, not a connection or DNS error.

## HPA transition (`kubectl get hpa catalog-hpa -n bookstore -w`)

| Age | CPU (TARGETS) | REPLICAS |
|---|---|---|
| 26m | 3%/65%, 2%/65% | 1 |
| 27m–28m | 38%/65%, 13%/65%, 2%/65% | 1 |
| 28m | 272%/65% | 1 |
| 29m | 107%/65%, 2%/65% | **4** (first tick at max) |
| 29m–33m | 213–430%/65% (multiple ticks) | 4 |
| 33m–34m | 2–9%/65% | 4 (holding through stabilization window) |
| 38m | 2–3%/65% | **1** (scaled back down) |

Scale-up from 1→4 happened within roughly one minute of CPU% first
exceeding the target. Scale-down back to 1 held at the peak for several
minutes after CPU% dropped (consistent with the default 300s/5-minute
scale-down stabilization window) before actually stepping down at the
`38m` mark.

## `kubectl top pods -n bookstore -l app=catalog`

**During load** (4 pods already scaled up):

| Pod | CPU (cores) | Memory |
|---|---|---|
| catalog-...-58m8w | 2m | 67Mi |
| catalog-...-72hxr | 2m | 72Mi |
| catalog-...-phsgd | 2m | 67Mi |
| catalog-...-zmsdv | 2m | 76Mi |

**After scale-down** (1 pod remaining):

| Pod | CPU (cores) | Memory |
|---|---|---|
| catalog-...-72hxr | 3m | 72Mi |

**Note on the during-load reading:** these per-pod snapshots read
suspiciously low (2m) given the HPA panel was reporting 400%+ utilization
(i.e. 400m+/pod) around the same general window. Not fully resolved, but
plausible given the timeout pattern above: with the majority of requests
stuck waiting up to k6's 60s timeout, pods may have been alternating
between brief CPU-throttled bursts and idle gaps, and `kubectl top`'s
point-in-time sample could easily have landed in a lull. The idle baseline
in `evidence/resource-usage/US-PLT-14-k8s-baseline-2026-07-25.md` also
shows catalog at 2m CPU with zero load at all, which shows 2m is this
pod's true floor — it doesn't by itself explain the gap against a
same-moment 400%+ HPA reading, so treat this specific pairing as
suggestive, not a fully nailed-down explanation.

## Conclusion

- HPA scale-up mechanism (AC #1, mechanism half): **proven**.
- HPA scale-down mechanism (AC #2): **proven**.
- R07 (HPA-not-triggering risk): **closed** — real `TARGETS` values
  throughout, HPA never sat at `<unknown>`.
- Load level was excessive for a clean demonstration — see Run 2 (tuned
  `ramping-vus`, default 25 VUs) for the primary evidence of a controlled
  threshold crossing without collateral request failures.
- AC #1's "Grafana shows the correlation" clause remains open pending
  US-PLT-18.
