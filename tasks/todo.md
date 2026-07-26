# US-PLT-03: Application metrics instrumentation

**Story:** As a DevOps engineer, I want each service to expose request count,
latency, and error metrics on `/metrics`, so that Prometheus can scrape
application-level observability data.

**Traces to:** FR-OPS-02, PMP increment I8, section 14.1
**Points:** 3
**Why now:** Surfaced as a hard prerequisite while planning US-PLT-18
(Prometheus/Grafana) — AC#1's "application" target and AC#2's RPS/p95-latency/
error-rate panels have nothing to scrape without this. User chose to do
US-PLT-03 first, then US-PLT-18.

## Plan

- [ ] Add `prometheus-fastapi-instrumentator>=8.0` to the `dependencies` list
      in each of the five services' `pyproject.toml`
      (`apps/services/{identity,catalog,inventory,cart,order}/pyproject.toml`),
      and bump each service's `version` `0.1.0` → `0.1.1` (a real behavior
      change — new endpoint — not a no-op bump). `frontend` is untouched;
      it has no `/metrics` requirement.
- [ ] In each service's `app/main.py` (all five are currently byte-identical
      apart from the title/router import), add, after `app.include_router(...)`
      and before the `/health/live` route:
      ```python
      from prometheus_fastapi_instrumentator import Instrumentator

      Instrumentator(excluded_handlers=["/health/live", ".*/health/ready$"]).instrument(app).expose(
          app, endpoint="/metrics", include_in_schema=False
      )
      ```
      Excluding the two health-check paths is a deliberate design choice, not
      scope creep: each is polled every 10–20s by k8s probes regardless of
      real traffic, and leaving them in would show a constant phantom
      baseline RPS on every panel this story exists to make meaningful
      (AC#2's "RPS... during a load test").
- [ ] No Dockerfile changes needed — all five already `pip install .`, which
      reads the dependency straight from `pyproject.toml`.
- [ ] No Ingress change needed — `30-ingress.yaml` already has no rule
      matching `/metrics` (its own header comment already anticipated this
      story). Verify this holds, don't just assume it still does.
- [ ] Run `deploy/docker/scripts/build-scan-push.sh identity catalog inventory
      cart order` (skip `frontend`, unaffected) with
      `REGISTRY=172.16.200.23:5000` (the registry-monitoring VM registry,
      per US-PLT-23) to build, Trivy-scan, and push all five new images.
      New tag will be `0.1.1-<new-short-commit>` once the code change is
      committed.
- [ ] Update the `image:` tag in `deploy/kubernetes/{21-identity,22-catalog,
      23-inventory,24-cart,25-order}.yaml` to the new `0.1.1-<sha>` tag for
      each service (`frontend` and `26/27-seed-*` jobs untouched).
- [ ] Write `deploy/kubernetes/US-PLT-03-runbook.md` following the
      established pattern: sync to `vm-master`, `kubectl apply`, then:
      1. Confirm all five pods roll to `Running` on the new image tag
         (`kubectl get pods -n bookstore -o wide` showing the new tag).
      2. From `vm-master`, curl each service's ClusterIP `:8000/metrics`
         directly (Service DNS, e.g. `catalog-service.bookstore.svc.cluster.local:8000/metrics`)
         and confirm `http_requests_total`, `http_request_duration_seconds_bucket`,
         and per-status-code series are present — AC#1.
      3. Generate a small amount of real traffic against each service (a
         few real customer-journey calls through the Ingress, same URLs used
         in every prior story's closing check), re-curl `/metrics`, and
         confirm the counters actually incremented — proves live data, not
         a static/empty registration.
      4. From the laptop, over the VPN, confirm `/metrics` is **not**
         reachable through the external Ingress
         (`http://172.16.200.20:30080/metrics` and any per-service-prefixed
         variant) — expect a 404, since no Ingress rule matches it — AC#2.
      5. Re-run the full customer journey through the Ingress from a real
         browser (same closing check as every prior story) to confirm the
         instrumentation change didn't regress anything for real traffic.
- [ ] Update `documents/backlog/sprint-plan.md` (Period 4 table: US-PLT-03 →
      done; points tally) and add a narrative update entry.
- [ ] Add a `MEMORY.md` entry: library choice (`prometheus-fastapi-
      instrumentator` over a hand-rolled `prometheus_client` middleware —
      standard, widely-used library gives request-count/duration-
      histogram/status-code metrics out of the box, matching AC#1 exactly
      with minimal code), the health-check-exclusion design reasoning above,
      and the version-bump convention.

## Review

*(filled in after execution)*
