# US-PLT-16 Runbook: Self-healing validation

**Story:** As a system administrator, I want to demonstrate that a deleted
stateless application pod is automatically replaced, so that the project
provides evidence of Kubernetes self-healing.

**Acceptance Criteria:**
- AC#1: Given continuous low-rate availability checks against a stateless
  service, when one of its pods is deleted, then Kubernetes creates a
  replacement and the service returns to healthy within 120 seconds.
- AC#2: Given the recovery window is exceeded, when measured, then the
  deviation is logged as a defect with root-cause analysis rather than
  silently accepted.

**Traces to:** NFR-AVAIL-01, AT-08, section 15.2. Depends on US-PLT-14
(readiness/liveness probes — already applied to every workload) and
US-PLT-13 (Deployments/Services already live in the `bookstore` namespace).
No manifest changes needed — this story only *exercises* infrastructure
that already exists.

**Target: `catalog`.** Chosen because it's already this project's reference
workload for probe/HPA stories (US-PLT-14/15), it's genuinely stateless (no
attached storage — Postgres access only, no volume mount), and it currently
runs at **`replicas: 1`** (`22-catalog.yaml`) — deleting its one pod removes
100% of catalog capacity, which is the clearest possible self-healing signal:
the availability check *will* show real failed requests during the gap, and
recovery time is unambiguous (first successful check after the last failed
one), unlike a multi-replica service where the Service would quietly route
around the dead pod and mask the recovery window entirely.

**R14 note (destructive-test risk, sprint-plan.md):** this test is
non-destructive to data (Catalog's Postgres schema and rows are untouched —
only the running pod is deleted) and fully self-recovering by design (the
Deployment's ReplicaSet controller replaces the pod automatically, no manual
rollback command needed). The one real failure mode to rehearse for is the
replacement pod failing to schedule or reach Ready at all (e.g. worker
resource pressure) — Part E below gives the diagnostic commands for that
case, and Part F gives the AC#2 path if it happens. Rehearse this whole
runbook once well before the live demo, per R14's stated mitigation.

**`kubectl` only works from `vm-master`** (same constraint as every prior
story since US-PLT-23).

## Part A — confirm a clean baseline before touching anything

Run **on `vm-master`**, inside `~/deploy-kubernetes`:

```sh
kubectl get pods -n bookstore -l app=catalog -o wide
kubectl get hpa catalog-hpa -n bookstore
```

Confirm exactly **one** `catalog` pod, `Running`/`1/1 Ready`, and the HPA
shows `REPLICAS: 1` (no leftover scale-up from a prior HPA test — same check
US-PLT-25/26 already established as standard prep). If the HPA shows more
than 1 replica, wait for it to settle back to 1 first (up to 5 minutes,
stabilization window) — starting from a known single-pod baseline is what
makes the recovery-time measurement unambiguous.

## Part B — start continuous low-rate availability checks

Run **on your laptop**, from a plain shell (Git Bash/WSL — needs `curl`,
reachable over the VPN the same way every prior browser/k6 check has been).
This hits the exact endpoint kubelet itself uses for the readiness probe
(`/api/books/health/ready`, routed through the Ingress the same way a real
client would reach it — `172.16.200.20:30080/api/books`), at roughly 1
request/second. This is deliberately **not** a load test (no concurrency, no
ramping) — AC#1 asks for "continuous low-rate availability checks," a
liveness signal, not a stress scenario; that's what US-PLT-15's k6 scripts
already cover.

```sh
mkdir -p evidence/self-healing
while true; do
  ts=$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 \
    http://172.16.200.20:30080/api/books/health/ready)
  echo "$ts $code"
  sleep 1
done | tee evidence/self-healing/US-PLT-16-availability-check.log
```

Leave this running in its own terminal for the rest of the runbook — don't
stop it until Part E confirms recovery. A `curl` that times out or refuses
the connection prints `000`, not a crash of the loop, so the log stays
continuous across the outage window instead of silently going blank.

## Part C — watch the pod transition live

Run **on `vm-master`**, in a second terminal session:

```sh
kubectl get pods -n bookstore -l app=catalog -w
```

Leave this running too — it's the second, independent view of the same
event the log file is capturing from the outside.

## Part D — delete the pod

Run **on `vm-master`**, in a third terminal session, inside
`~/deploy-kubernetes`:

```sh
POD=$(kubectl get pods -n bookstore -l app=catalog -o jsonpath='{.items[0].metadata.name}')
echo "Deleting: $POD"
kubectl delete pod "$POD" -n bookstore
```

This is the actual trigger event. Note the wall-clock time you ran this
command (or just rely on the availability-check log's own timestamps — the
first `000`/non-`200` line after this point marks the start of the outage
window).

## Part E — observe recovery, then measure the window

Watch Part C's `-w` output: the deleted pod moves to `Terminating`, then a
**new pod with a different generated name** appears (`ContainerCreating` →
`Running`), then its readiness gate flips true (`1/1 Ready` in the base
`kubectl get pods` columns, not just `-w`'s `Running` phase — a pod can be
`Running` before its readiness probe passes, and only a `1/1` pod is
actually receiving traffic from the Service).

Once Part C shows the new pod `1/1 Running`, stop Part B's loop (Ctrl+C) and
measure the recovery window directly from the log:

```sh
grep -v ' 200$' evidence/self-healing/US-PLT-16-availability-check.log | tail -5
```

Compute: (timestamp of the **first** non-`200` line) to (timestamp of the
**last** non-`200` line, i.e. the last failure before checks return to
steady `200`). That span is the actual measured outage/recovery duration —
compare it against the 120-second AC#1 threshold.

Also capture, for the evidence record:
```sh
kubectl get pods -n bookstore -l app=catalog -o wide
kubectl describe pod -n bookstore -l app=catalog | grep -A5 Events
```

Save the full `-w` transcript (copy from the terminal) and the availability
log under `evidence/self-healing/`, alongside a short
`US-PLT-16-self-healing-metrics.md` write-up (recovery duration, replacement
pod name, whether the 120s threshold was met).

## Part F — if the 120-second window is exceeded (AC#2)

If the measured window from Part E is **greater than 120 seconds**, this is
not something to round down or omit from the evidence — AC#2 exists
specifically to require this outcome be logged as a defect with a real root
cause, not silently accepted as "close enough." In that case:

1. Don't delete/reset anything yet — first capture `kubectl describe pod`
   for the replacement pod (readiness probe `initialDelaySeconds`/
   `periodSeconds`/`failureThreshold` from `22-catalog.yaml` predict a
   worst-case detection lag of `5 + 10*3 = 35s` after the container itself
   becomes ready — if the actual gap is much larger than that, the extra
   time is scheduling/image-pull/container-start latency, not the probe
   configuration, and `kubectl describe pod`'s Events table will show which).
2. Check `kubectl get events -n bookstore --sort-by=.lastTimestamp` for
   scheduling failures (`FailedScheduling`, insufficient CPU/memory on
   either worker) or image pull issues (`ErrImagePull`/`ImagePullBackOff`)
   around the deletion timestamp.
3. Record the finding (measured duration, root cause, evidence) in this
   runbook's own Review section and in `documents/backlog/sprint-plan.md` —
   same standard as every other real defect this project has already found
   and logged (e.g. the Identity OOMKill finding, `MEMORY.md` 2026-07-28).
   A failed 120s threshold is a legitimate, reportable result for this
   story, not a blocker to fix before the story can be called done — AC#2's
   entire purpose is to make that outcome visible rather than hidden.

If the window **is** within 120 seconds (the expected case, since a single
pod recreate against an already-cached image should be well under it), skip
straight to Part G.

## Part G — confirm nothing else regressed

Run the full customer journey (register/log in, browse, add to cart,
checkout, order history) through the Ingress from a real browser — same
closing check as every prior Kubernetes story — to confirm the pod
delete/recreate cycle didn't leave anything in a bad state.

```sh
kubectl get pods -n bookstore
```
Confirm every other workload is still `Running`/`Ready` and wasn't touched —
this test only ever targeted `catalog`.

## What's still open after this runbook

- US-PLT-17 (rolling update and rollback) — the other Period 5 story, not
  covered here.
- If Part F's AC#2 path is triggered for real, the resulting defect write-up
  becomes new follow-up work, not closed by this runbook alone.
