# US-PLT-26 Runbook: Stage 3 baseline comparison metrics (P1-P3)

Target: the kubeadm cluster via Ingress (`http://172.16.200.20:30080`).
Load generator: your laptop, same k6 script as Stage 1/2
(`tests/load/baseline-p1-p3.js`), only `BASE_URL` differs.

## Part A — Preflight

Confirm Catalog's HPA is at a clean starting state before treating any of
these runs as a baseline — already checked once (currently **1** replica,
no leftover scale-up from US-PLT-15's testing), but re-confirm since time
has passed:
```sh
kubectl get hpa catalog-hpa -n bookstore
```
If it's not at 1, wait for it to settle (HPA's default scale-down
stabilization window) before starting, so P1's "warm-up" result isn't
measuring an already-scaled cluster.

**Re-import the Grafana dashboard** — its p99-latency/error-rate panels had
the identical cardinality-fragmentation bug already found and fixed once in
the baseline dashboard (US-PLT-22); fixed in
`infrastructure/monitoring/grafana-dashboard.json` proactively before
running this, since this same script will trigger the exact same issue.
Re-upload it the same way as before (Dashboards → Import → same file, same
UID — updates in place):
```sh
scp infrastructure/monitoring/grafana-dashboard.json student@172.16.200.23:~/
ssh student@172.16.200.23 "sudo mv ~/grafana-dashboard.json /srv/monitoring/grafana/grafana-dashboard.json"
```
Then in Grafana (`http://172.16.200.23:3000`): Dashboards → New → Import →
Upload → select the file → same Prometheus data source.

## Part B — P1/P2/P3 load scenarios

Same cadence: each scenario 3x when time permits.

```sh
k6 run -e SCENARIO=p1 -e BASE_URL=http://172.16.200.20:30080 \
  --out experimental-prometheus-rw \
  -e K6_PROMETHEUS_RW_SERVER_URL=http://172.16.200.23:9090/api/v1/write \
  tests/load/baseline-p1-p3.js
```
(swap `SCENARIO=p1` for `p2`/`p3` — `BASE_URL` must be set explicitly every
time here, unlike Stage 1/2, since the script's default points at the
baseline VM.)

While each run is in progress, watch the **Stage 3 Kubernetes
Observability** dashboard and screenshot it. Also run
`kubectl get hpa catalog-hpa -n bookstore -w` in a second terminal during
P3 specifically (the only scenario with enough VUs to plausibly approach
the 65% CPU target).

**Real architectural difference to expect and record, not suppress:**
unlike Stage 1/2, Catalog can autoscale mid-run. If P3's 25 VUs pushes it
past its HPA target and it scales to 2+ replicas, that's genuine Stage 3
behavior worth recording as its own finding (elasticity under the same load
Stage 1/2 handled with fixed capacity) — don't disable or work around the
HPA to force a fixed-replica comparison; that would misrepresent what
Stage 3 actually does under this load.

Sample `kubectl top pods -n bookstore` and `kubectl top nodes` partway
through each run, same purpose as Stage 1/2's `top`/`free`/`df` samples.

## Part C — Evidence

Save under `evidence/baseline-comparison/stage3-p1-p3/{p1,p2,p3}-run/`,
same naming convention as Stage 1/2.

Report back once done and I'll draft
`evidence/baseline-comparison/US-PLT-22-stage3-metrics.md`.
