# US-PLT-15 Runbook: HPA for Catalog service

Prerequisite: **US-PLT-14 complete** — the `catalog` Deployment already has
`resources.requests.cpu: 100m` applied and running in the `bookstore`
namespace. The HPA below computes utilization as a percentage of that
request; without it, `kubectl get hpa` would sit at `<unknown>` forever
(this is exactly R07, the "HPA does not scale because... limits are wrong"
risk named in the sprint plan).

**`kubectl` only works from `vm-master`** (same constraint as every prior
story since US-PLT-23). Every `kubectl` command below runs **on
`vm-master`**, inside `~/deploy-kubernetes`.

**Files in this story:** `22-catalog.yaml` (gained a `HorizontalPodAutoscaler`
object — no changes to the existing Deployment/Service in that file), plus
several k6 scripts under `tests/load/`, all under the repo on your laptop.
**`tests/load/catalog-hpa-load-test-arrival-rate-tall-fast.js` is the
recommended script** — see Part D for why. The others
(`catalog-hpa-load-test.js`, `-sleep.js`, `-arrival-rate.js`,
`-arrival-rate-tall.js`) are kept as exploratory variants with their own
evidence trail in `evidence/hpa/`, not deleted, in case any future
re-demonstration wants a different load shape.

**Known gap, flagged up front, not discovered partway through:** AC #1's
literal wording ends "...and **Grafana shows the correlation**." Prometheus/
Grafana (US-PLT-18) isn't deployed yet. This runbook fully verifies the
*mechanism* — real CPU load causing real replica scale-up/down — via
`kubectl` directly. The Grafana half of the AC has to stay open until
US-PLT-18 lands; re-run this same load scenario once it does, and confirm
the dashboard shows the same correlation this runbook proves via `kubectl`.
Don't mark this AC's Grafana clause "done" until that follow-up actually
happens.

## Part A — sync to vm-master

Run **on your laptop**, from the repo root.

```sh
scp -r deploy/kubernetes/. student@172.16.200.20:~/deploy-kubernetes/
```
Same trailing-`/.` form as every prior sync (`tasks/lessons.md`) — without
it, `scp` nests the whole `kubernetes/` directory one level deeper inside
the destination instead of refreshing the files already there.

## Part B — apply the HPA and confirm metrics wiring before any load

Run **on `vm-master`**, inside `~/deploy-kubernetes`:

```sh
kubectl apply -f 22-catalog.yaml
kubectl get hpa catalog-hpa -n bookstore
```
Wait up to ~60 seconds (metrics-server's scrape interval) and re-run the
`get hpa` command until the `TARGETS` column shows a real percentage like
`3%/65%`, not `<unknown>/65%`. **Do not start the load test until this
shows a real number** — an `<unknown>` target here means the HPA has no
metrics to act on and the load test that follows would prove nothing
(this is the R07 check called out above, done first while it's cheap to
fix).

## Part C — install k6 on your laptop (if not already present)

k6 needs to run from your laptop, generating real HTTP load against the
cluster over the VPN — same reachability path as every browser-based
customer-journey check in prior stories (`http://172.16.200.20:30080/...`
via the Ingress).

Windows (PowerShell):
```powershell
winget install GrafanaLabs.k6
```
Confirm it's on PATH afterward:
```sh
k6 version
```

## Part D — generate sustained catalog-heavy load and watch it scale up

**Two earlier attempts led here — Run 1's evidence is kept at
`evidence/hpa/run-1-80vus/`; the intermediate retune's evidence wasn't
retained once superseded (summarized in `MEMORY.md` instead):**
- **Run 1** (`catalog-hpa-load-test.js` at its original 80-VU
  `constant-vus` default) drove CPU to 270–430% of target almost
  instantly, jumping straight to `maxReplicas: 4` in one shot and causing
  53.52% of requests to time out. Proved the mechanism, but as a
  stress-to-failure scenario, not a clean demonstration.
- An intermediate retune (`ramping-vus`, 25 VUs) fixed the failures (0%)
  but *still* jumped straight past target (250–500% overshoot) rather
  than climbing gradually — VU count turned out to be the wrong knob,
  since concurrency doesn't map predictably to request rate.
- **The final, recommended run** (`ramping-arrival-rate`, which controls
  requests/sec directly instead of VU count) finally produced a genuinely
  gradual **1→2→3→4** climb and, as a bonus, a gradual **4→2→1**
  descent, with 0% request failures, in 5m30s. Evidence in
  `evidence/hpa/run-final-ramping-arrival-rate/`. This is the version
  described below.

Run **on `vm-master`**, in its own terminal session, to watch replicas and
CPU% update live while the load runs:
```sh
kubectl get hpa catalog-hpa -n bookstore -w
```
In a second `vm-master` session, watch per-pod CPU directly (HPA's own
`TARGETS` column already shows this, but a second independent view is
useful corroborating evidence):
```sh
watch -n 10 kubectl top pods -n bookstore -l app=catalog
```
(if `watch` isn't installed: `sudo apt install -y watch`, or just re-run
`kubectl top pods -n bookstore -l app=catalog` manually every ~10s)

Run **on your laptop**, from the repo root, in a third session:
```sh
k6 run tests/load/catalog-hpa-load-test-arrival-rate-tall-fast.js
```
Default is a staircase from 8 to 53 requests/sec over ten 30-second
steps (`START_RATE=3`, `RATE_STEP=5`, `STEPS=10`, `STEP_DURATION=30s`),
then a 30s ramp-down — against `http://172.16.200.20:30080`, hitting
`/api/books` (list/paginated/filtered) and `/api/books/categories`. If
`REPLICAS` isn't climbing at all, the rate range is too light for the
actual worker hardware; raise the ceiling by increasing `STEPS` or
`RATE_STEP`, e.g.:
```sh
k6 run -e STEPS=14 tests/load/catalog-hpa-load-test-arrival-rate-tall-fast.js
```

**What to look for, in order:**
1. `kubectl get hpa -w`'s `TARGETS` column climbing through several
   readings below 65%, then crossing it — not an instant jump.
2. `REPLICAS` in the same `-w` output stepping up one at a time (1→2,
   then 2→3, then 3→4), each transition preceded by CPU% visibly above
   target — this discrete, gradual pattern (not a single leap to max) is
   the evidence this story was specifically retuned to capture.
3. `kubectl top pods` showing real, non-trivial per-pod CPU values
   (tens of millicores) as corroborating evidence alongside the HPA's own
   reading.

Capture a screenshot or copy of the full `kubectl get hpa -w` transition
(idle → climbing → 4 → descending → idle), plus the k6 summary output —
save both under `evidence/hpa/` (following the
`run-final-ramping-arrival-rate/US-PLT-15-run-final-gradual-2026-07-25.md`
naming precedent).

## Part E — confirm scale-down after load stops

Once the k6 run finishes (or is stopped), keep watching the same `kubectl
get hpa catalog-hpa -n bookstore -w` session. The default scale-down
stabilization window is 300s (5 minutes) — expect `REPLICAS` to hold at its
peak for up to 5 minutes after CPU% drops back down, then step back toward
`1`. This delay is expected behavior (prevents replica thrashing on a brief
load dip), not a bug — don't restart the load test thinking scale-down
"isn't working" if it just hasn't hit the 5-minute mark yet. Don't assume
the drop happens in one step, either — Run 3's evidence shows it can go
`4→2→1` across two ticks rather than straight to `1`, consistent with
Kubernetes' default scale-down policy limiting how many replicas can be
removed per sync interval.

## Part F — confirm the k6 run itself didn't break anything

Run k6's own summary output check: `http_req_failed` rate should be
`<1%` (the configured threshold) — if k6 exits non-zero on a failed
threshold, treat that as a real signal, not a false alarm, and check
whether it was caused by the HPA under-provisioning during a scale-up gap
(new pod not yet Ready) versus a genuine application error.

Then re-run the same full customer journey (register/log in, browse, add
to cart, checkout, order history) through the Ingress from a real browser,
same as US-PLT-13/US-PLT-14's closing checks — confirms the HPA object and
the load test didn't regress anything for real traffic.

## What's still open after this runbook

- AC #1's "Grafana shows the correlation" clause — open until US-PLT-18,
  per the flagged gap above.
- No self-healing pod-delete demonstration recorded yet — US-PLT-16.
- No NetworkPolicy — US-PLT-19.
- `/metrics` doesn't exist on any service yet — US-PLT-03; Prometheus
  scraping and Grafana dashboards — US-PLT-18.
