# US-PLT-03 Runbook: Application metrics instrumentation

Prerequisite: all five services (`identity`, `catalog`, `inventory`, `cart`,
`order`) were instrumented with `prometheus-fastapi-instrumentator`
(commit `a08a02d`), rebuilt, Trivy-scanned, and pushed to the
`registry-monitoring` VM's registry as `0.1.1-a08a02d` — confirmed already via
`GET /v2/bookstore/<service>/tags/list` on `172.16.200.23:5000`. The five
Deployment manifests (`21-identity.yaml`, `22-catalog.yaml`,
`23-inventory.yaml`, `24-cart.yaml`, `25-order.yaml`) have already been
updated in this repo to reference the new tag.

**Deliberately left unchanged:** `15-migration-jobs.yaml`,
`26-seed-catalog-job.yaml`, `27-seed-inventory-job.yaml` still reference
`0.1.0-c997b06`. Nothing in this story touched migrations or seed scripts —
only `app/main.py`/`pyproject.toml` — and those Jobs already ran to
completion against the current data. Re-pinning them to a tag that changes
nothing about their own behavior isn't necessary; `0.1.0-c997b06` stays
retained in the registry so nothing breaks if any of them were ever re-run.

**`kubectl` only works from `vm-master`**, inside `~/deploy-kubernetes`, same
constraint as every prior story.

**Files in this story:** `21-identity.yaml`, `22-catalog.yaml`,
`23-inventory.yaml`, `24-cart.yaml`, `25-order.yaml` (each gained only an
`image:` tag bump — no other Deployment/Service field changed).

## Part A — sync to vm-master

Run **on your laptop**, from the repo root.

```sh
scp -r deploy/kubernetes/. student@172.16.200.20:~/deploy-kubernetes/
```

## Part B — apply the five updated Deployments

Run **on `vm-master`**, inside `~/deploy-kubernetes`:

```sh
kubectl apply -f 21-identity.yaml -f 22-catalog.yaml -f 23-inventory.yaml -f 24-cart.yaml -f 25-order.yaml
kubectl get pods -n bookstore -o wide
```

Wait until all five services' pods show `Running`/`1/1 Ready` on **new** pod
names (a rolling update replaces the existing pod, it doesn't reuse it).
Confirm the new image actually took effect, not just that the pod restarted:

```sh
kubectl get pods -n bookstore -l app=identity -o jsonpath='{.items[0].spec.containers[0].image}'
kubectl get pods -n bookstore -l app=catalog -o jsonpath='{.items[0].spec.containers[0].image}'
kubectl get pods -n bookstore -l app=inventory -o jsonpath='{.items[0].spec.containers[0].image}'
kubectl get pods -n bookstore -l app=cart -o jsonpath='{.items[0].spec.containers[0].image}'
kubectl get pods -n bookstore -l app=order -o jsonpath='{.items[0].spec.containers[0].image}'
```

Each should print `...:0.1.1-a08a02d`.

## Part C — confirm `/metrics` is present and populated (AC #1)

Run **on `vm-master`**. The runtime image (`python:3.12-slim`) has no `curl`
installed — same reason the Dockerfile's own `HEALTHCHECK` uses Python's
`urllib` instead — so exec in and use the same approach:

```sh
for svc in identity catalog inventory cart order; do
  echo "== $svc =="
  pod=$(kubectl get pods -n bookstore -l app=$svc -o jsonpath='{.items[0].metadata.name}')
  kubectl exec -n bookstore "$pod" -- python -c \
    "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/metrics').read().decode())" \
    | grep -E "^(http_requests_total|http_request_duration_seconds_bucket)" | head -5
done
```

Confirm for each service:
- `http_requests_total` is present (request-count metric — AC #1).
- `http_request_duration_seconds_bucket` is present (duration histogram —
  AC #1).
- Neither shows a `handler="/health/live"` or `handler=".../health/ready"`
  entry — confirms the deliberate probe-traffic exclusion is working, not
  just assumed.

At this point the counters will likely read `0` or be entirely absent for
routes other than the probe paths themselves (nothing but health checks has
hit these pods yet) — expected, not a bug. The next step proves the metric
actually moves under real traffic.

## Part D — confirm the metrics respond to real traffic

Run **on your laptop**, from the repo root, over the VPN (same customer-
journey URLs as every prior story's closing check):

```sh
curl -s http://172.16.200.20:30080/api/books >/dev/null
curl -s http://172.16.200.20:30080/api/books/categories >/dev/null
curl -s http://172.16.200.20:30080/api/books >/dev/null
```

Then re-run catalog's own check from Part C:

```sh
pod=$(kubectl get pods -n bookstore -l app=catalog -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n bookstore "$pod" -- python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/metrics').read().decode())" \
  | grep "handler=\"/api/books\""
```

Confirm `http_requests_total{handler="/api/books",...}` shows a count `>= 3`
(the exact number depends on Ingress path matching, but it must have
increased from Part C's reading) and that
`http_request_duration_seconds_bucket{handler="/api/books",...}` shows real,
non-zero bucket counts — proves this is live instrumentation, not a static
or dead registration.

## Part E — confirm `/metrics` is not reachable externally (AC #2)

Run **on your laptop**, over the VPN:

```sh
curl -i http://172.16.200.20:30080/metrics
```

**Expect `200` with the frontend's HTML, not a `404`** — `30-ingress.yaml`
has no rule matching `/metrics` specifically, but it does have a `path: /`
prefix rule to `frontend-service`, which catches everything not matched by
the more specific `/api/*` rules (the Ingress file's own header comment
already says this: `"/" never shadows "/api/*"` — the same catch-all applies
to any other unmatched path, `/metrics` included). So the request lands on
the frontend's SPA shell, the same response any nonexistent client-side
route would get.

The actual proof AC #2 needs isn't the status code, it's the **body**:
confirm it contains no Prometheus exposition text at all —

```sh
curl -s http://172.16.200.20:30080/metrics | grep -E "^# (HELP|TYPE)|http_requests_total"
```

— should print nothing. A `200`/HTML response with zero Prometheus lines in
the body means no backend service's real `/metrics` data is reachable from
outside the cluster, which is what "not publicly reachable, internal scrape
only" actually requires.

## Part F — confirm nothing regressed for real traffic

Re-run the full customer journey through the Ingress from a real browser
(register/log in, browse, add to cart, checkout, order history) — same
closing check as every prior story. This confirms the instrumentation
middleware wrapping every request didn't introduce a regression (added
latency, broken CORS/error-handling behavior, etc.) for real traffic.

## What's still open after this runbook

- US-PLT-18 (Prometheus/Grafana) itself — not started. This story only makes
  the application-level data available to *scrape*; nothing scrapes it yet.
- US-PLT-19 (NetworkPolicies) — not started.
