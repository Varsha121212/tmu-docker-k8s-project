# US-PLT-14 Runbook: Readiness/liveness probes and resource requests/limits

Prerequisite: **US-PLT-13 complete** — all six workloads already `Running`
in the `bookstore` namespace via `~/deploy-kubernetes` on `vm-master`.
This story only edits the 8 files below (no new objects, no new
Deployments/StatefulSets) — every command here re-applies an existing
manifest to trigger a rolling update on its existing workload.

**`kubectl` only works from `vm-master`** (same constraint as every prior
story since US-PLT-23). Every `kubectl` command below runs **on
`vm-master`**, inside `~/deploy-kubernetes`.

**Files in this story:** `20-frontend.yaml`, `21-identity.yaml`,
`22-catalog.yaml`, `23-inventory.yaml`, `24-cart.yaml`, `25-order.yaml`,
`11-postgres-statefulset.yaml`, `13-redis-workload.yaml`, all under
`deploy/kubernetes/` in the repo on your laptop. None of these existed
with probes/resources on `vm-master` until Part A below re-syncs them —
same gap pattern already found in US-PLT-24/US-PLT-13, avoided here by
syncing first.

**What changed and why**, in case you're comparing diffs: each container
spec gained a `readinessProbe` (hits a real dependency-checking endpoint
— DB/Redis — per SDD 10.5, so a pod that can't reach its database is
kept out of its Service's endpoints, not just "process started"), a
`livenessProbe` (hits the cheap no-dependency `/health/live` endpoint, so
a downstream DB outage can't falsely trigger a restart loop on services
that didn't cause it), and `resources.requests`/`limits` from SDD 10.3's
table. Exact numbers and endpoint paths are in the story's plan, not
repeated here — read the diff on each file if you want the specifics.

**Expect brief service interruption during this rollout**, more than a
typical image-tag bump: `postgres` (StatefulSet, single replica, no
alternate pod to fail over to) and `redis` (Deployment with
`strategy: Recreate`, chosen specifically because ReadWriteOnce doesn't
allow two pods on the same volume) each go through a real stop-then-start
of the one pod that exists. The five stateless app Deployments use the
default RollingUpdate, so they stay available throughout — apply `redis`
and `postgres` at a moment when you're not mid-checkout, and expect
`kubectl top`/curl checks against the frontend to show a short gap right
after those two, not the app Deployments.

## Part A — sync to vm-master

Run **on your laptop**, from the repo root.

```sh
scp -r deploy/kubernetes/. student@172.16.200.20:~/deploy-kubernetes/
```
Same trailing-`/.` form as every prior sync (`tasks/lessons.md`) —
without it, `scp` nests the whole `kubernetes/` directory one level
deeper inside the destination instead of refreshing the files already
there.

## Part B — apply, in dependency order

Run **on `vm-master`**, inside `~/deploy-kubernetes`. Postgres and Redis
first (their probes/resources land before anything depends on their
rollout finishing), then the five app services, matching US-PLT-13's own
apply order:

```sh
kubectl apply -f 11-postgres-statefulset.yaml
kubectl rollout status statefulset/postgres -n bookstore

kubectl apply -f 13-redis-workload.yaml
kubectl rollout status deployment/redis -n bookstore

kubectl apply -f 20-frontend.yaml
kubectl rollout status deployment/frontend -n bookstore

kubectl apply -f 21-identity.yaml
kubectl rollout status deployment/identity -n bookstore

kubectl apply -f 22-catalog.yaml
kubectl rollout status deployment/catalog -n bookstore

kubectl apply -f 23-inventory.yaml
kubectl rollout status deployment/inventory -n bookstore

kubectl apply -f 24-cart.yaml
kubectl rollout status deployment/cart -n bookstore

kubectl apply -f 25-order.yaml
kubectl rollout status deployment/order -n bookstore

kubectl get pods -n bookstore -o wide
```
Expect the same pod counts as US-PLT-13 (frontend ×2, order ×2, everything
else ×1) — `rollout status` for each blocking until that workload's own
new pod(s) are actually `Ready`, not just `Running`, is the first live
proof the readiness probe is wired up (a `Running`-but-not-`Ready` pod
would hang here instead of returning immediately).

## Part C — verify readiness gating (AC #1)

Run **on `vm-master`**. Pick one app Deployment (`catalog` is a good
choice — it's the one with the most going on, DB dependency and about to
get an HPA in US-PLT-15):

```sh
kubectl get endpoints catalog-service -n bookstore
```
Note the IP(s) listed — these are exactly the pods currently receiving
traffic through the Service. Then force a rollout and watch readiness
gate it in real time:
```sh
kubectl rollout restart deployment/catalog -n bookstore
kubectl get pods -n bookstore -l app=catalog -w
```
Watch the new pod go `0/1` → `1/1`. While it's `0/1`, run in a second
session:
```sh
kubectl get endpoints catalog-service -n bookstore
```
The old (still-ready) pod's IP should still be the only one listed until
the new pod passes its readiness probe — proof the Service really does
withhold traffic from a not-yet-ready pod, not just that the YAML says
`readinessProbe`.

## Part D — verify liveness restarts on real probe failure (AC #2)

**`kill -STOP 1` from `kubectl exec` does not work here — confirmed for
real, don't repeat this attempt.** Linux gives a PID namespace's PID 1
special signal immunity: a process *inside* that same namespace can only
deliver a signal to its own PID 1 if PID 1 has installed a handler for
it, and the only signal exempted from this rule is `SIGKILL`. `uvicorn`
installs no `SIGSTOP` handler, so the kernel silently drops it —
confirmed by checking `/proc/1/status` before and after: `State` stayed
`S (sleeping)` the entire time despite `Name`/`Pid` proving the exec
session was correctly targeting the real process. `kill -KILL 1` would
"work," but only proves `restartPolicy: Always` restarts a crashed
container, which is true with or without a liveness probe at all — it
does not prove the AC's actual claim, that the *probe* is what triggers
the restart.

Instead, make the probe itself fail — this exercises the exact mechanism
the AC describes. Run **on `vm-master`**:

```sh
kubectl patch deployment identity -n bookstore --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/health/live-does-not-exist"}]'
kubectl get pods -n bookstore -l app=identity -w
```
Let it run ~90 seconds. The new pod's `RESTARTS` should climb repeatedly
— nothing makes the broken path recover on its own, so it keeps
crash-restarting rather than settling. Confirm the causal chain, not
just the restart count:
```sh
kubectl describe pod -n bookstore -l app=identity
```
Look for `Liveness probe failed: HTTP probe failed with statuscode: 404`
events immediately before `Killing`/`Started` — this is the evidence the
AC actually asks for (probe failure *causes* the restart), not just that
a restart happened for some reason. Once confirmed, revert the probe path:
```sh
kubectl patch deployment identity -n bookstore --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe/httpGet/path","value":"/health/live"}]'
kubectl rollout status deployment/identity -n bookstore
```

## Part E — verify resource requests/limits are real

Run **on `vm-master`**:
```sh
kubectl describe pod -n bookstore -l app=catalog | grep -A4 "Limits\|Requests"
kubectl top pods -n bookstore
kubectl top nodes
```
Confirm the requests/limits shown match the SDD 10.3 table for that
workload, and that current usage sits comfortably under the limits during
normal (non-load-test) operation — a pod already pegged at its limit
here would be a red flag before US-PLT-15's HPA work even starts.

## Part F — full journey regression check

Run from a real browser on your laptop, over the VPN, through the
Ingress (same URL as US-PLT-13's own closing check) — register/log in,
browse, add to cart, checkout, view order history. This is the same
journey US-PLT-13 already proved; the point here is confirming this
story's rolling updates (especially the Postgres/Redis restarts in Part
B) didn't regress anything, not proving the journey from scratch.

## What's still open after this runbook

- No HPA on catalog — US-PLT-15.
- No self-healing pod-delete demonstration recorded yet (different from
  this story's liveness-restart test) — US-PLT-16.
- No NetworkPolicy — US-PLT-19.
- `/metrics` doesn't exist on any service yet — US-PLT-03; Prometheus
  scraping and Grafana dashboards — US-PLT-18.
