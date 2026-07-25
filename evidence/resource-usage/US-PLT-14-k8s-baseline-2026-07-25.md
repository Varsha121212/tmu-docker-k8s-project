# Kubernetes resource-usage baseline — post US-PLT-14

**Captured:** 25 Jul 2026, from `vm-master`, immediately after US-PLT-14's
probes/resource requests-limits rollout and liveness-probe verification
(Part E of `deploy/kubernetes/US-PLT-14-runbook.md`).

**Cluster state at capture time:** idle — no k6/load test running, no
concurrent user traffic beyond the manual verification steps just
performed in Parts C/D. This is a baseline/idle snapshot, not a
loaded-system measurement. Useful as the "before" side of any future
Stage 2 (Compose) vs Stage 3 (Kubernetes) resource comparison (PMP
section 17.2) and as the pre-HPA (US-PLT-15) baseline for catalog
specifically (still 1 replica here).

## Configured requests/limits (SDD 10.3, applied by US-PLT-14)

Confirmed via `kubectl describe pod` matches the SDD table exactly for
catalog (spot-checked; same pattern applied to all 8 workloads):
```
Limits:   cpu: 500m   memory: 256Mi
Requests: cpu: 100m   memory: 128Mi
```

## `kubectl top pods -n bookstore` (idle)

| Pod | CPU (cores) | Memory |
|---|---|---|
| cart | 2m | 46Mi |
| catalog | 2m | 65Mi |
| frontend (×2) | 1m each | 2Mi each |
| identity | 2m | 63Mi |
| inventory | 2m | 62Mi |
| order (×2) | 2m each | 64Mi / 65Mi |
| postgres-0 | 4m | 30Mi |
| redis | 9m | 4Mi |

Every pod is sitting far under its configured request, let alone its
limit, at idle — expected, and a useful "headroom exists" data point
before US-PLT-15's HPA/load-test work begins.

## `kubectl top nodes` (idle)

| Node | CPU (cores) | CPU % | Memory | Memory % |
|---|---|---|---|---|
| vm-master | 155m | 7% | 1851Mi | 48% |
| vm-worker-1 | 110m | 5% | 1653Mi | 43% |
| vm-worker-2 | 86m | 4% | 1732Mi | 45% |

Memory % is already fairly high relative to CPU % on all three nodes at
idle — worth watching as HPA (US-PLT-15) and Prometheus/Grafana
(US-PLT-18) add more workloads in Period 4; if memory pressure becomes a
real constraint later, this snapshot is the "before" reference point.
