# US-PLT-16: Self-healing validation — results

**Target:** `catalog` Deployment (`bookstore` namespace), single replica at
test time. Trigger: `kubectl delete pod catalog-dd84dd546-fk2cg -n bookstore`
on `vm-master`, 28 Jul 2026. Continuous ~1 req/s availability check against
`http://172.16.200.20:30080/api/books/health/ready` (the Ingress path,
routing to the same endpoint kubelet's own readiness probe uses) run from
the laptop throughout, logged to `US-PLT-16-availability-check.log`.

## AC#1 — recovery within 120 seconds

| Event | Timestamp (UTC) |
|---|---|
| Last successful check before deletion | 19:59:31.323Z (200) |
| First failed check | 19:59:32.551Z (502) |
| Last failed check | 19:59:43.562Z (503) |
| First recovered check | 19:59:44.821Z (200) |

- **Failure span** (first non-200 → last non-200): **11.011s**
- **Full outage-to-recovery span** (first non-200 → first 200 after): **12.270s**

**Result: PASS.** 12.27s is well within the 120s threshold — no AC#2
defect/root-cause path triggered.

**Corroborating evidence:** `kubectl get pods -n bookstore -l app=catalog -w`
shows the replacement pod (`catalog-dd84dd546-cqjxz`) reaching `1/1 Running`
at `AGE: 12s` — matching the independently-measured 12.27s HTTP-level
recovery window to within kubectl's 1-second AGE resolution. Two
independent measurements (external Ingress-level checks vs. Kubernetes' own
pod age) agreeing this closely is stronger evidence than either alone.

The replacement pod was also scheduled onto **`vm-worker-1`**, while the
deleted pod had been running on `vm-worker-2` — confirms a genuine
cross-node reschedule, not a same-node coincidence.

**Scope caveat:** `kubectl describe pod`'s Events show the container image
was already cached on the target node (`Pulled ... already present on
machine`), so this measures scheduling + container-start + readiness-probe
detection time only — not a cold image-pull scenario, which would add real
time on top of this result.

**Non-defect observation:** the availability log shows one `502` immediately
after deletion, then steady `503`s until recovery. This is normal
`ingress-nginx` behavior when a backend's endpoint list drops to zero (a
stale upstream connection reused once, then a clean "no endpoints" response
thereafter) — not an application-level error, not logged as a defect.

## AC#2 — defect logging if the window is exceeded

Not triggered — the 120s threshold was met with wide margin (12.27s, ~10x
under budget). No defect to log.

## Closing check

Full customer journey (register → browse → cart → checkout → order history)
re-confirmed working through the Ingress after the pod delete/recreate
cycle. `kubectl get pods -n bookstore` (unfiltered) showed every other
workload still `Running` with `RESTARTS 0` — nothing else was disturbed by
this test.

## Verdict

**US-PLT-16 done and verified.** Both acceptance criteria satisfied; no
open follow-up specific to this story.
