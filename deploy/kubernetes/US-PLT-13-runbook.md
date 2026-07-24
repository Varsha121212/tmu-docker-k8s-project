# US-PLT-13 Runbook: Application manifests (frontend + five microservices)

Prerequisite: **US-PLT-23 and US-PLT-24 both complete** — the registry
must be reachable from the cluster and PostgreSQL/Redis must already be
`Ready` in the `bookstore` namespace before anything here can start
(migration Jobs need a live database; every Deployment needs its image
pullable).

**`kubectl` only works from `vm-master`** (confirmed during US-PLT-23 —
`kubeadm join` doesn't copy `admin.conf` to workers the way `kubeadm
init` does for `vm-master`). Every `kubectl` command in this runbook
runs **on `vm-master`**, inside `~/deploy-kubernetes` (the same remote
directory US-PLT-24 already set up — Part A.5 below refreshes it with
this story's files). Stated explicitly at the top of each Part, not just
here, so it doesn't get lost partway through.

**Files in this story:** `01-configmaps.yaml`, `15-migration-jobs.yaml`,
`20-frontend.yaml` … `25-order.yaml`, `26-seed-jobs.yaml`,
`30-ingress.yaml`, all under `deploy/kubernetes/` in the repo on your
laptop (`00-namespace.yaml` and `02-secrets.yaml` were already applied in
US-PLT-24 — reused here, not reapplied). **None of these exist on
`vm-master` with the correct image tags until Part A.5 copies them
there** — the same gap already found and fixed in US-PLT-24's runbook.

No readiness/liveness probes, no resource requests/limits on any workload
here — deliberately deferred to US-PLT-14, the very next story, to keep
this story's own boundary clean (six workload manifests plus
config/secrets wiring, per its own point estimate). One consequence worth
knowing going in: without a readiness probe, Kubernetes' own "Ready"
state just means "container process started," a looser bar than the
AC's spirit implies — acceptable here because US-PLT-14 tightens it
immediately after, not because the gap is being hidden.

## Part A — substitute image tags

Run **on your laptop**, from the repo root — plain text substitution,
no `kubectl` involved yet.

Every manifest below has `<..._IMAGE_TAG>` placeholders. Fill them in
with the real tags from US-PLT-23 Part B's output before applying
anything. (These placeholders are safe as written — each one sits inside
an already-quoted `sed -e "..."` argument, so `<`/`>` here are literal
characters passed to `sed`, not live shell redirection like the bug
found in US-PLT-24's Part E and US-PLT-23's Part D.)

**The six tags are not all the same value.** `identity`/`catalog`/
`inventory`/`cart`/`order` share version `0.1.0`; `frontend` is `0.0.0`
— different version prefix, same commit suffix (confirmed repeatedly
across every scan run in this project: e.g. `0.1.0-c997b06` for the five
services, `0.0.0-c997b06` for frontend). Don't copy one tag into all six
`-e` lines below. Verify the real values first rather than assuming —
same check already used to catch this:
```sh
curl http://172.16.200.23:5000/v2/bookstore/identity/tags/list
curl http://172.16.200.23:5000/v2/bookstore/frontend/tags/list
# ...one per service if you want to confirm all six individually
```

```sh
cd deploy/kubernetes
sed -i \
  -e "s#<IDENTITY_IMAGE_TAG>#0.1.0-XXXXXXX#g" \
  -e "s#<CATALOG_IMAGE_TAG>#0.1.0-XXXXXXX#g" \
  -e "s#<INVENTORY_IMAGE_TAG>#0.1.0-XXXXXXX#g" \
  -e "s#<CART_IMAGE_TAG>#0.1.0-XXXXXXX#g" \
  -e "s#<ORDER_IMAGE_TAG>#0.1.0-XXXXXXX#g" \
  -e "s#<FRONTEND_IMAGE_TAG>#0.0.0-XXXXXXX#g" \
  15-migration-jobs.yaml 20-frontend.yaml 21-identity.yaml 22-catalog.yaml \
  23-inventory.yaml 24-cart.yaml 25-order.yaml 26-seed-jobs.yaml
grep -rn '<.*_IMAGE_TAG>' *.yaml   # expect no output - confirms nothing was missed
cd ../..
```
Replace every `XXXXXXX` above with the real short commit from US-PLT-23
Part B step 3 before running — it's the same commit for all six, only
the version prefix (`0.1.0` vs `0.0.0`) differs.

## Part A.5 — sync to vm-master

Run **on your laptop**, from the repo root.

US-PLT-24 already copied `deploy/kubernetes/` to `vm-master:~/deploy-kubernetes`
— but that copy predates Part A's tag substitution above (it still has
the literal `<..._IMAGE_TAG>` placeholders). Refresh it with the same
trailing-`/.` form used in US-PLT-24's runbook (copies the source
directory's *contents* into the destination, not the directory itself —
**do not drop the `/.`**: since `~/deploy-kubernetes` already exists from
US-PLT-24, `scp -r deploy/kubernetes dest` without it nests the whole
thing one level deeper as `dest/kubernetes/` instead of refreshing the
files already there — hit for real running this step, see
`tasks/lessons.md`):
```sh
scp -r deploy/kubernetes/. student@172.16.200.20:~/deploy-kubernetes/
```
This overwrites files that changed and adds any that are new; existing
files on `vm-master` you haven't touched (like the already-applied
`02-secrets.yaml`) are unaffected. If you already ran the version without
`/.` and ended up with a nested `~/deploy-kubernetes/kubernetes/`, clean
it up first — **on `vm-master`**:
```sh
rm -rf ~/deploy-kubernetes
```
then, **from your laptop**, recreate it and re-sync:
```sh
ssh student@172.16.200.20 "mkdir -p ~/deploy-kubernetes"
scp -r deploy/kubernetes/. student@172.16.200.20:~/deploy-kubernetes/
```

## Part B — config, migrations

Run **on `vm-master`**. SSH in, then:
```sh
cd ~/deploy-kubernetes
```
Every command in Parts B–E below assumes you're in this directory —
that's why they use bare filenames (`01-configmaps.yaml`, not a full
path).

```sh
kubectl apply -f 01-configmaps.yaml
kubectl apply -f 15-migration-jobs.yaml
kubectl wait --for=condition=complete \
  job/migrate-identity job/migrate-catalog job/migrate-inventory job/migrate-order \
  -n bookstore --timeout=180s
kubectl get jobs -n bookstore   # confirm all four COMPLETIONS 1/1
```
If any Job fails, `kubectl logs -n bookstore job/<name>` before retrying —
`backoffLimit: 2` means it's already retried twice on its own; a third
failure needs a real look, not another blind retry.

## Part C — application workloads

Run **on `vm-master`**, still inside `~/deploy-kubernetes`.

Apply each, wait for its rollout, before moving to the next — **stop and
confirm `catalog` specifically before continuing**, since `seed-inventory`
(Part D) depends on it being real, not just "applied":
```sh
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
Expect frontend ×2, identity ×1, catalog ×1, inventory ×1, cart ×1,
order ×2 — all `Running`.

## Part D — seed data

Run **on `vm-master`**, still inside `~/deploy-kubernetes`.

```sh
kubectl apply -f 26-seed-jobs.yaml
kubectl wait --for=condition=complete job/seed-catalog job/seed-inventory -n bookstore --timeout=180s
kubectl get jobs -n bookstore
```
If `seed-inventory` fails specifically, check it can actually reach
`catalog-service` before assuming a code bug:
```sh
kubectl logs -n bookstore job/seed-inventory
```

## Part E — Ingress

Run **on `vm-master`**, still inside `~/deploy-kubernetes`.

```sh
kubectl apply -f 30-ingress.yaml
kubectl get ingress bookstore-ingress -n bookstore
```

## Part F — end-to-end verification (this is the AC evidence)

1. All workloads `Running` — **on `vm-master`**:
   ```sh
   kubectl get pods -n bookstore
   ```

2. Ingress routes `/api/*` **directly to the backend Service**, bypassing
   the frontend pod entirely — the concrete proof the nginx-proxy
   reasoning documented in `20-frontend.yaml` actually holds, not just
   reasoned through. Run from **your laptop** (or `vm-master` — anywhere
   with network access to a node IP works for `curl`):
   ```sh
   curl http://<any-node-ip>:30080/api/books
   ```
   Expect real catalog JSON (16 seeded books), not a proxy error from the
   frontend container.

3. From a real VPN browser on **your laptop** (not `curl` — this needs to
   prove genuine external browser access, same standard US-PLT-11 already
   used):
   ```
   http://<any-node-ip>:30080/
   ```
   Walk the full customer journey: register → browse → add to cart →
   checkout → order history. This is the literal closure of **US-PLT-11's
   deferred AC #2** ("the frontend is deployed... loads via the Ingress
   path") — note in the final report that this was proven with the real
   frontend, not the US-PLT-11 placeholder.

4. Re-run US-PLT-24's persistence check in its *literal* SDD §12 form,
   now that Order exists: place a real order through the UI (laptop
   browser), then, **on `vm-master`**:
   ```sh
   kubectl delete pod postgres-0 -n bookstore
   kubectl wait --for=condition=Ready pod/postgres-0 -n bookstore --timeout=120s
   ```
   then reload the order-history page (laptop browser) and confirm the
   same order is still there.

5. No secret reached source control (US-PLT-13's own AC #2). Run **on
   your laptop, from the repo root** — this is a check of the local git
   working tree, not something that makes sense on `vm-master` (its
   `~/deploy-kubernetes` copy is a plain `scp`'d directory, not a git
   checkout):
   ```sh
   git status deploy/kubernetes/           # 02-secrets.yaml must be untracked/ignored
   git grep -n "PASSWORD\|SECRET\|TOKEN" deploy/kubernetes/
   ```
   Expect matches only inside `.example` files, all `CHANGE_ME_*`
   placeholders — no real value.

## What's still open after this runbook

- No probes, no resource requests/limits — US-PLT-14, immediately next.
- No HPA on catalog — US-PLT-15.
- No NetworkPolicy — US-PLT-19.
- `/metrics` doesn't exist on any service yet — US-PLT-03; Prometheus
  scraping and Grafana dashboards — US-PLT-18.
