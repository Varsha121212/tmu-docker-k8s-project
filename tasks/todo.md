# US-PLT-19: NetworkPolicies restricting database/cache access

**Story:** As a system administrator, I want Calico NetworkPolicies that
restrict PostgreSQL and Redis access to only the authorized service pods,
so that the database and cache are not reachable by unauthorized workloads
or the public Ingress.

**Traces to:** BRULE-10, SDD section 13.3, PT-13, NFR-SEC-01
**Points:** 3 — last story in Period 4 (33/33 pts once done).
**Prerequisites (already done):** US-PLT-24 (Postgres/Redis running in
`bookstore`), US-PLT-09/10 (Calico confirmed as CNI, so standard
`NetworkPolicy` objects are enforced, not silently ignored).

## Design decision

A `NetworkPolicy` that selects a pod (via `podSelector`) switches that pod
to default-deny for any traffic direction listed in `policyTypes` — traffic
not matching an explicit rule is dropped. No separate "default-deny" object
is needed alongside the "allow" rules; one policy per workload, each with
its own allow list, gives both in one object.

Scope is **Ingress-only**, limited to the Postgres and Redis pods
specifically — not a namespace-wide default-deny — matching the AC's literal
wording ("PostgreSQL and Redis access... not reachable by unauthorized
workloads") rather than reopening a broader zero-trust redesign that would
also need new allow rules for the Ingress controller and the US-PLT-18
NodePort scraping path.

Which pods are "authorized": from `02-secrets.yaml.example`'s
`DATABASE_URL`/`REDIS_URL` values — Identity, Catalog, Inventory, and Order
connect to `postgres-service:5432`; Cart connects only to
`redis-service:6379` (SDD 7.4/8.3 — Cart has no database). The four
Alembic migration Jobs (`15-migration-jobs.yaml`) also need Postgres access
transiently.

Rather than selecting on the existing `app: <service>` label (which is
also each Service's own selector — reusing it on the migration Jobs would
make Postgres/Redis's Services attempt to route DB traffic to job pods,
which don't listen on 5432/6379), add a dedicated label,
`netpol: postgres-client` / `netpol: redis-client`, to the pods that need
DB access, orthogonal to `app`.

## Plan

### Kubernetes-side manifests (agent writes, user applies)

- [x] Add `netpol: postgres-client` to the pod template labels in
      `21-identity.yaml`, `22-catalog.yaml`, `23-inventory.yaml`,
      `25-order.yaml` (Deployments) and to all four Jobs in
      `15-migration-jobs.yaml`.
- [x] Add `netpol: redis-client` to the pod template labels in
      `24-cart.yaml`.
- [x] New `deploy/kubernetes/33-network-policies.yaml`:
      - `postgres-allow-authorized`: `podSelector: {app: postgres}`,
        `policyTypes: [Ingress]`, ingress allowed from
        `podSelector: {netpol: postgres-client}` on `port: 5432/TCP`.
      - `redis-allow-authorized`: `podSelector: {app: redis}`,
        `policyTypes: [Ingress]`, ingress allowed from
        `podSelector: {netpol: redis-client}` on `port: 6379/TCP`.
      (No `namespaceSelector` needed — a bare `podSelector` in a
      `NetworkPolicy.spec.ingress[].from` only matches pods in the policy's
      own namespace, and everything here lives in `bookstore`.)
- [x] New `deploy/kubernetes/US-PLT-19-network-policy-test-pod.yaml` — a
      throwaway pod with no `netpol` label (same disposable-manifest
      pattern as `infrastructure/kubeadm/network-test-pods.yaml` from
      US-PLT-10), used for the negative test below, applied then deleted.

### Runbook + verification (`deploy/kubernetes/US-PLT-19-runbook.md`, user
executes on the live cluster per this project's collaboration pattern)

- [x] Runbook written (`deploy/kubernetes/US-PLT-19-runbook.md`) — notes
      that `15-migration-jobs.yaml` doesn't need (can't be) re-applied
      since its Jobs already ran to completion; re-applies
      `21/22/23/24/25.yaml` and `33-network-policies.yaml`.
- [ ] AC#1 (positive): from an Identity pod, confirm `psql`/`pg_isready`
      (or a quick `nc -zv postgres-service 5432`) still succeeds; from the
      Cart pod, confirm `redis-cli -a $REDIS_PASSWORD -h redis-service
      ping` still returns `PONG`.
- [ ] AC#2 (negative): apply the throwaway test pod (unlabeled), confirm
      `nc -zv postgres-service 5432` and `nc -zv redis-service 6379` from
      inside it both time out/refuse; delete the test pod afterward.
- [ ] Full customer-journey regression (register → browse → cart →
      checkout → order history) to confirm the allow-rules didn't break
      real app-to-DB/cache traffic.
- [ ] Update `documents/backlog/sprint-plan.md` (Period 4 table + points
      tally: 33/33) and project `MEMORY.md`.

## Review

**Done and verified — Period 4 complete at 33/33 points.**

Part B: `netpol: postgres-client` landed on `identity`/`catalog`/
`inventory`/`order` pods, `netpol: redis-client` on `cart`, both
`postgres-allow-authorized`/`redis-allow-authorized` NetworkPolicies
present with the correct `POD-SELECTOR` — confirmed via `kubectl get pods
--show-labels` / `kubectl get networkpolicy`.

Part C (AC#1, positive): a Python socket connection from the live
`identity` pod to `postgres-service:5432` and from the live `cart` pod to
`redis-service:6379` both succeeded — authorized traffic unaffected.

Part D (AC#2, negative): the throwaway unlabeled `netpol-test` pod, applied
in the same `bookstore` namespace specifically to prove the block is
label-driven and not a namespace artifact, timed out on both `nc -zv
postgres-service 5432` and `nc -zv redis-service 6379`. Deleted afterward.

Part E: full customer-journey regression (register → browse → cart →
checkout → order history) through the Ingress passed with no regressions.

No infrastructure bugs found this time — the first Period 4 story to close
clean on the first pass, unlike US-PLT-13/18 which each surfaced real bugs
against the live VMs. `documents/backlog/sprint-plan.md` and the project's
`MEMORY.md` updated to reflect Period 4's completion.
