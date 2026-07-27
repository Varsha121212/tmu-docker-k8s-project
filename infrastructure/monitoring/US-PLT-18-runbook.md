# US-PLT-18 Runbook: Prometheus and Grafana dashboards

Prerequisite: US-PLT-03 (all five services expose `/metrics`), US-PLT-11
(metrics-server/Ingress), US-PLT-23 (Docker already installed on
`registry-monitoring`), cluster `Ready`.

**Design decision (confirmed before this runbook was written):**
`registry-monitoring` (172.16.200.23) is not a cluster member — no route to
pod IPs or Service ClusterIPs. Prometheus/Grafana run there per SDD 10.1 and
this project's own R13 risk mitigation (don't silently move them
in-cluster). The bridge for Kubernetes-side targets is **NodePort Services**
(same mechanism the Ingress already uses at `:30080`) for the app services
and kube-state-metrics, and direct node-IP scraping of kubelet's cAdvisor
endpoint for pod/node CPU+memory. See `infrastructure/monitoring/prometheus.yml`'s
own header comment for the full reasoning.

**`kubectl` only works from `vm-master`**, same constraint as every prior
story. Node Exporter steps run on all six VMs directly over SSH — not
through `kubectl`.

**Files in this story:** `deploy/kubernetes/{21-identity,22-catalog,
23-inventory,24-cart,25-order}.yaml` (each gained one NodePort Service),
`deploy/kubernetes/31-monitoring-rbac.yaml`,
`deploy/kubernetes/32-kube-state-metrics.yaml` (new),
`infrastructure/monitoring/prometheus.yml`,
`infrastructure/monitoring/grafana-dashboard.json` (new, on your laptop —
copied to `registry-monitoring` in Part C/D below).

## Part A — Node Exporter on all six VMs

Run on **each of the six VMs** (`vm-master`, `vm-worker-1`, `vm-worker-2`,
`registry-monitoring`, `vm-baseline-app`, `vm-baseline-db`) individually:

```sh
sudo apt-get update
sudo apt-get install -y prometheus-node-exporter
sudo systemctl enable --now prometheus-node-exporter
sudo systemctl status prometheus-node-exporter --no-pager   # expect "active (running)"
```

Firewall — **only needed on `vm-baseline-app` and `vm-baseline-db`**
(fresh `ufw` setup on those two; SDD's literal wording is "9100 restricted
to monitoring VM," tighter than the whole-subnet trust used elsewhere):

```sh
# on vm-baseline-app and vm-baseline-db only
sudo ufw allow from 172.16.200.23 to any port 9100 proto tcp
sudo ufw status verbose
```

`vm-master`/`vm-worker-1`/`vm-worker-2` already trust the whole
`172.16.200.0/24` subnet on all ports (US-PLT-09's own `ufw` setup) — verify
this is still true rather than assume it:

```sh
# on vm-master, vm-worker-1, vm-worker-2
sudo ufw status verbose
```

If it doesn't show the whole-subnet rule for some reason, add the same
restricted-to-monitoring-VM rule as above rather than opening it wider than
needed.

**`registry-monitoring` scraping its own Node Exporter needs its own rule
too — do not skip this one.** Prometheus runs inside a Docker container on
this VM, so its request to `172.16.200.23:9100` doesn't stay on loopback the
way a plain `curl localhost:9100` does — it traverses Docker's bridge
network (`172.17.0.0/16` by default) and re-enters via the host's real
interface, which `ufw`'s `INPUT` chain does filter. With no rule for port
`9100` on this VM and a default-deny incoming policy, that traffic is
dropped, which surfaces later (Part E) as the `registry-monitoring`
node-exporter target showing `DOWN` with `context deadline exceeded` — a
timeout, not an immediate refusal, which is what a dropped (not rejected)
packet looks like. Confirmed for real hitting exactly this on the first run
of this story. Fix, scoped to the Docker bridge subnet specifically (not
the whole VPN subnet — only local containers on this VM need this path;
confirm the actual subnet first rather than assuming `172.17.0.0/16`, since
it's Docker's default but not guaranteed):

```sh
docker network inspect bridge --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
# if that errors with "permission denied ... docker.sock", prefix with sudo
sudo ufw allow from 172.17.0.0/16 to any port 9100 proto tcp
sudo ufw status verbose
```

Verify each of the six directly:

```sh
curl -s http://localhost:9100/metrics | grep node_cpu_seconds_total | head -3
```

## Part B — kube-state-metrics, RBAC, and the scrape token

Run **on your laptop**, from the repo root, sync the updated manifests:

```sh
scp -r deploy/kubernetes/. student@172.16.200.20:~/deploy-kubernetes/
```

Run **on `vm-master`**, inside `~/deploy-kubernetes`. Before applying,
check the current `kube-state-metrics` release tag (the placeholder in
`32-kube-state-metrics.yaml` is deliberately not a real version — see that
file's own header comment) at
`https://github.com/kubernetes/kube-state-metrics/releases` and substitute
it:

```sh
sed -i 's/CHECK_LATEST_TAG/<real tag, e.g. v2.13.0>/' 32-kube-state-metrics.yaml
kubectl apply -f 31-monitoring-rbac.yaml
kubectl apply -f 32-kube-state-metrics.yaml
kubectl apply -f 21-identity.yaml -f 22-catalog.yaml -f 23-inventory.yaml -f 24-cart.yaml -f 25-order.yaml
kubectl get pods -n kube-system -l app=kube-state-metrics
kubectl get svc -n kube-system kube-state-metrics-nodeport
```

Generate the long-lived bearer token Prometheus needs for kubelet's
cAdvisor endpoint. **This is a static token, not auto-refreshing** —
acceptable for this project's timeframe, not something worth building an
auto-renewal mechanism for. If the API server enforces a shorter max
expiration than requested, this command still succeeds but the token will
expire sooner than asked — if Prometheus's `kubelet-cadvisor` targets later
show `401`/`403`, that's the first thing to check, not a sign the whole
approach is broken:

```sh
kubectl create token prometheus-scraper -n kube-system --duration=8760h > prometheus-scraper.token
cat prometheus-scraper.token   # copy this value, or scp the file itself in the next step
```

Copy the token off `vm-master` to your laptop, then on to
`registry-monitoring` (no direct SSH trust between the two VMs has been set
up in this project, so route through your laptop the same way every other
cross-VM file transfer in this project has):

```sh
# on your laptop
scp student@172.16.200.20:~/deploy-kubernetes/prometheus-scraper.token .
scp prometheus-scraper.token student@172.16.200.23:~/
```

## Part C — Prometheus on `registry-monitoring`

Run **on your laptop**, from the repo root, sync the config:

```sh
scp infrastructure/monitoring/prometheus.yml student@172.16.200.23:~/
```

Run **on `registry-monitoring`**. Check the remote-write receiver flag
before starting the container — this has changed across Prometheus
versions, don't assume the flag named in `prometheus.yml`'s header comment
is still current:

```sh
sudo docker run --rm prom/prometheus --help | grep -i remote-write
```

Then start Prometheus, bind-mounting the config and the token (same
bind-mount-not-named-volume pattern as US-PLT-23's registry container):

```sh
sudo mkdir -p /srv/monitoring/prometheus
sudo mv ~/prometheus.yml /srv/monitoring/prometheus/prometheus.yml
sudo mv ~/prometheus-scraper.token /srv/monitoring/prometheus/prometheus-scraper.token
sudo docker run -d \
  --name prometheus \
  --restart unless-stopped \
  -p 9090:9090 \
  -v /srv/monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml \
  -v /srv/monitoring/prometheus/prometheus-scraper.token:/etc/prometheus/prometheus-scraper.token \
  prom/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --web.enable-remote-write-receiver
```

(Replace `--web.enable-remote-write-receiver` with whatever flag the
`--help` check above actually showed, if different.)

Firewall (this VM already has `ufw` active from US-PLT-12/23). This rule
covers external access (your laptop, k6's remote-write) — it does **not**
cover Grafana reaching Prometheus, see the callout in Part D below, same
Docker-bridge-vs-`ufw` issue as the node-exporter self-scrape fix above:

```sh
sudo ufw allow from 172.16.200.0/24 to any port 9090 proto tcp
sudo ufw status verbose
```

Verify:

```sh
curl -s http://localhost:9090/-/healthy
```

From **your laptop**, over the VPN, open `http://172.16.200.23:9090/targets`
in a browser — this is the real AC#1 evidence, checked properly in Part F
below.

## Part D — Grafana on `registry-monitoring`

Run **on your laptop**, sync the dashboard JSON:

```sh
scp infrastructure/monitoring/grafana-dashboard.json student@172.16.200.23:~/
```

Run **on `registry-monitoring`**:

```sh
sudo mkdir -p /srv/monitoring/grafana
sudo mv ~/grafana-dashboard.json /srv/monitoring/grafana/grafana-dashboard.json
sudo docker run -d \
  --name grafana \
  --restart unless-stopped \
  -p 3000:3000 \
  -v /srv/monitoring/grafana:/var/lib/grafana/dashboards \
  grafana/grafana
sudo ufw allow from 172.16.200.0/24 to any port 3000 proto tcp
```

From **your laptop**, over the VPN, open `http://172.16.200.23:3000`
(default login `admin`/`admin`, you'll be prompted to change it):

1. **Add a data source**: Configuration → Data sources → Prometheus. URL:
   `http://172.16.200.23:9090` (Grafana's own container reaches the host's
   published port via the VM's real IP, since these are two independent
   `docker run` containers, not a shared Compose network). **Same
   Docker-bridge-vs-`ufw` issue as the node-exporter self-scrape fix in
   Part A** — Grafana's request to `172.16.200.23:9090` also arrives from
   the Docker bridge subnet, not `172.16.200.0/24`, so the rule added in
   Part C (scoped to the VPN subnet, for external/laptop access) doesn't
   cover it. If "Save & test" fails with an `i/o timeout`, add:
   ```sh
   sudo ufw allow from 172.17.0.0/16 to any port 9090 proto tcp
   ```
   then retry. Expect a green confirmation once that's in place.
2. **Import the dashboard**: Dashboards → New → Import → Upload JSON file →
   select the copy at `/var/lib/grafana/dashboards/grafana-dashboard.json`
   (or paste its contents directly) → pick the Prometheus data source just
   added.

## Part E — AC#1: confirm all targets Up

From **your laptop**, over the VPN, at `http://172.16.200.23:9090/targets`:

Confirm every target group shows state `UP`:
- `prometheus` (self)
- `node-exporter` — **all six** VMs, explicitly including `vm-baseline-app`
  and `vm-baseline-db` (this is the literal AC#1 wording this story exists
  to satisfy — don't stop checking once the three cluster-side ones are Up)
- `kubelet-cadvisor` — the three cluster nodes
- `kube-state-metrics`
- `bookstore-services` — all five app services

If any `kubelet-cadvisor` target shows `401`/`403`: the token likely
expired or wasn't generated with sufficient RBAC — re-check Part B.

## Part F — AC#2: Grafana panels update live during a load test

Run **on your laptop**, from the repo root, reusing US-PLT-15's proven
script rather than writing a new one, with k6's built-in Prometheus
remote-write output:

```sh
k6 run --out experimental-prometheus-rw \
  -e K6_PROMETHEUS_RW_SERVER_URL=http://172.16.200.23:9090/api/v1/write \
  tests/load/catalog-hpa-load-test-arrival-rate-tall-fast.js
```

While it runs, watch the imported dashboard in Grafana
(`http://172.16.200.23:3000`).

**Confirmed for real on the first run (dashboard already corrected to
match):** k6's remote-write output only exports `k6_vus`,
`k6_http_reqs_total`, and a fixed set of `_p99`-suffixed trend stats
(`k6_http_req_duration_p99`, etc.) plus `k6_http_req_failed_rate` — **not**
a `_bucket` histogram and **not** separate p50/p95 series. The dashboard's
original guesses (`k6_http_req_duration_seconds_bucket` via
`histogram_quantile`, `k6_http_req_failed_total`) were wrong and showed
"No data" on the first real run; fixed to `k6_http_req_duration_p99`
(plotted directly, not through `histogram_quantile`) and
`k6_http_req_failed_rate * 100` (already a ratio gauge, not a counter to
`rate()`). Full list of every `k6_*` metric this k6 version writes is
queryable any time at `http://172.16.200.23:9090/api/v1/label/__name__/values`
(searches the label index, unaffected by the instant-query staleness that
makes a plain `{__name__=~"k6_.*"}` query return empty once the test has
finished).

**Deliberate scope decision, not an oversight:** AC#2's literal wording asks
for "p95 latency," and this k6 version's default remote-write output only
provides p99 (no `_bucket` histogram, no separate p50/p95 series without
extra k6 config). Confirmed working with real data on the first run —
**user decided to keep p99 and not pursue p95** (would need
`K6_PROMETHEUS_RW_TREND_STATS` with an unconfirmed exact syntax for a
latency percentile one step off, for no real demonstration difference).
Logged as a deliberate substitution against the literal AC text, same
"flag it, don't silently smooth it over" pattern as US-PLT-11's AC#2 and
US-PLT-15's Grafana-clause caveats — those were "not built yet, closed
later"; this one is "built, a close-enough substitute chosen on purpose,
not going to be revisited."

Confirm, across the run:
- Load and outcome: VUs/RPS climb and fall with the k6 staircase; p99
  latency and error rate % show real (not "No data") series once the
  dashboard fix above is applied.
- Resources: `catalog` pods' CPU visibly climbing.
- Scalability: desired/current/available replicas step 1→2→3→4 and back,
  correlated with the CPU panel — this is the literal evidence that closes
  **US-PLT-11's AC#2 and US-PLT-15's AC#1 Grafana-clause caveats**, both
  left open pending this story. Note that closure explicitly once confirmed
  — don't let it pass unnoticed.

**Evidence capture — tried, then deliberately dropped, not an oversight:**
Grafana's built-in "Export as image" needs the `grafana-image-renderer`
plugin. Tried installing it in-process (`grafana cli plugins install
grafana-image-renderer` + restart) — the plugin downloaded but this
Grafana version (`13.1.1`) never logged loading it (no "renderer" mention
anywhere in the startup log after restart), so it silently didn't take
effect. The officially-supported fallback (a separate
`grafana/grafana-image-renderer` container on a shared Docker network,
pointed at via `GF_RENDERING_SERVER_URL`) would have worked but requires
recreating the Grafana container and losing its current
datasource/dashboard state (never persisted to a volume) for a
feature that isn't actually required — **user decided to stop here and
use plain browser screenshots instead**, the same method already used for
every other story's `evidence/` folder throughout this project (e.g.
`evidence/hpa/`). That already captures the same dashboard state and is
sufficient for AC#2's "exportable for the final report" — not pursuing the
image-renderer setup further.

## Part G — confirm nothing regressed

Re-run the full customer journey through the Ingress from a real browser
(register/log in, browse, add to cart, checkout, order history) — same
closing check as every prior story.

## What's still open after this runbook

- US-PLT-19 (NetworkPolicies) — not started. Once it lands, double check it
  doesn't accidentally block the NodePort scrape paths added in this story
  (NodePort traffic arrives at a node's own IP, not through the pod
  network's normal ingress path, so a naive default-deny NetworkPolicy
  could behave differently than expected here — verify, don't assume).
- The `prometheus-scraper` token is static; if it expires before the final
  demo, regenerate it (Part B) and restart the Prometheus container so it
  re-reads the mounted file.
- k6 remote-write metric names in the dashboard are unverified until Part F
  is actually run once for real.
