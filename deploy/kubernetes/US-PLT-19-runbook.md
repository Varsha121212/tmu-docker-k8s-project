# US-PLT-19 Runbook: NetworkPolicies restricting database/cache access

Prerequisite: **US-PLT-24 complete** — `postgres` (`app: postgres`) and
`redis` (`app: redis`) are already running in `bookstore`, bound to their
NFS-backed PVCs. Prerequisite: **Calico confirmed as the CNI** (US-PLT-09/10)
— standard `networking.k8s.io/v1` `NetworkPolicy` objects are enforced by
Calico, not silently ignored the way some CNIs (e.g. plain flannel) would.

**`kubectl` only works from `vm-master`** (same constraint as every prior
story since US-PLT-23). Every `kubectl` command below runs **on
`vm-master`**, inside `~/deploy-kubernetes`.

**Files in this story:** `21-identity.yaml`, `22-catalog.yaml`,
`23-inventory.yaml`, `24-cart.yaml`, `25-order.yaml`, and
`15-migration-jobs.yaml` each gained one new pod-template label
(`netpol: postgres-client` on Identity/Catalog/Inventory/Order and the four
migration Jobs, `netpol: redis-client` on Cart) — no other changes to those
files. New: `33-network-policies.yaml` (the two `NetworkPolicy` objects) and
`US-PLT-19-network-policy-test-pod.yaml` (throwaway, deleted at the end).

**Design recap:** each `NetworkPolicy` selects one backend pod (`app:
postgres` or `app: redis`) and allows Ingress only from pods carrying the
matching `netpol` label, on that backend's own port. Selecting a pod with a
`NetworkPolicy` makes it default-deny for anything not explicitly allowed —
there's no separate "default-deny" object to apply. Scope is Ingress-only
and limited to these two pods; the Ingress controller and US-PLT-18's
NodePort scraping path are untouched.

## Part A — sync to vm-master

Run **on your laptop**, from the repo root.

```sh
scp -r deploy/kubernetes/. student@172.16.200.20:~/deploy-kubernetes/
```

## Part B — apply the updated labels and the new policies

Run **on `vm-master`**, inside `~/deploy-kubernetes`. The Deployments below
already exist (US-PLT-13/14/15/18) — this just adds the new label to each
pod template, causing a rolling update:

```sh
kubectl apply -f 21-identity.yaml
kubectl apply -f 22-catalog.yaml
kubectl apply -f 23-inventory.yaml
kubectl apply -f 24-cart.yaml
kubectl apply -f 25-order.yaml
kubectl apply -f 33-network-policies.yaml
```

Note: `15-migration-jobs.yaml`'s Jobs already ran to completion in
US-PLT-13/24 and are immutable once created — re-applying it is a no-op (or
errors on immutable field changes) with no live pods to relabel. The new
`netpol: postgres-client` label on those Job templates only takes effect
the next time a migration Job is actually re-created (e.g. a future schema
change) — flagged here so it isn't mistaken for something this runbook
needs to force.

Confirm the labels landed and the policies exist:

```sh
kubectl get pods -n bookstore --show-labels
kubectl get networkpolicy -n bookstore
```

Expect `netpol=postgres-client` on the `identity-*`, `catalog-*`,
`inventory-*`, and `order-*` pods, `netpol=redis-client` on the `cart-*`
pod, and both `postgres-allow-authorized`/`redis-allow-authorized` listed.

## Part C — AC#1: confirm authorized traffic still works

From an Identity pod, confirm Postgres is still reachable (reuses the same
`pg_isready`-style check as the Postgres readiness probe):

```sh
kubectl exec -n bookstore deploy/identity -- sh -c \
  "python -c \"import socket; socket.create_connection(('postgres-service', 5432), timeout=3)\" && echo OPEN"
```

From the Cart pod, confirm Redis is still reachable and authenticates:

```sh
kubectl exec -n bookstore deploy/cart -- sh -c \
  "python -c \"import socket; socket.create_connection(('redis-service', 6379), timeout=3)\" && echo OPEN"
```

Both should print `OPEN`. If either times out, check `kubectl describe
networkpolicy <name> -n bookstore` for a typo'd label selector before
assuming anything else is wrong.

## Part D — AC#2: confirm unauthorized traffic is blocked

Apply the throwaway test pod — same namespace as everything else, but
carrying no `netpol` label, so a block here is specifically due to the
missing label, not a namespace difference:

```sh
kubectl apply -f US-PLT-19-network-policy-test-pod.yaml
kubectl wait -n bookstore --for=condition=Ready pod/netpol-test --timeout=60s
kubectl exec -n bookstore netpol-test -- nc -zv -w 3 postgres-service 5432
kubectl exec -n bookstore netpol-test -- nc -zv -w 3 redis-service 6379
```

Expect both `nc` commands to time out or report the connection refused —
**not** `open`. Then delete the test pod (it's diagnostic-only, not part of
the application):

```sh
kubectl delete -f US-PLT-19-network-policy-test-pod.yaml
```

## Part E — full customer-journey regression

Same check as every prior story: register → log in → browse → add to cart
→ checkout → order history, through the Ingress from a real browser
(`http://172.16.200.20:30080`). Confirms the new labels/policies didn't
break real Identity/Catalog/Inventory/Order → Postgres or Cart → Redis
traffic.

## What's still open after this runbook

- Nothing — this is Period 4's last story. Once Parts C/D/E all pass,
  Period 4 is 33/33 points.
