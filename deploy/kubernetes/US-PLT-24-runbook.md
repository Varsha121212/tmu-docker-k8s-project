# US-PLT-24 Runbook: Deploy PostgreSQL and Redis to Kubernetes

Prerequisite: cluster `Ready` (US-PLT-09/10/11/12). US-PLT-23 is **not** a
hard prerequisite for this story specifically — `postgres:16-alpine` and
`redis:7-alpine` are public Docker Hub images, no registry/containerd
trust config needed for either.

**`kubectl` only works from `vm-master`** — `kubeadm init` copied
`admin.conf` there; `kubeadm join` doesn't do the same for workers
(confirmed for real during US-PLT-23). Every `kubectl` command in this
runbook runs **on `vm-master`**, over SSH — this is stated explicitly at
the start of each Part below, not just once here, so it doesn't get lost
partway through.

This is the first time the *real* PostgreSQL/Redis storage gets deployed
to Kubernetes — US-PLT-12 only proved the generic NFS PV/PVC mechanism
with a throwaway busybox pod (already deleted, nothing from that story
persists here except the proven pattern and the live NFS export).

**Files in this story:** `00-namespace.yaml`, `02-secrets.yaml.example`
(copy to `02-secrets.yaml`, gitignored), `10-postgres-pv-pvc.yaml`,
`11-postgres-statefulset.yaml`, `12-redis-pv-pvc.yaml`,
`13-redis-workload.yaml`, all under `deploy/kubernetes/` in the repo on
your laptop. **None of these exist on any VM until you copy them there**
— Part B step 0 below does that once, for the whole directory, before
anything gets applied.

## Part A — NFS subdirectories on `registry-monitoring` (172.16.200.23)

Run directly on `registry-monitoring` over SSH — no files to copy, no
`kubectl` involved.

No new `exportfs`/`/etc/exports` change needed — US-PLT-12's export at
`/srv/nfs/k8s` already covers subdirectories. Just add the two this story
needs:
```sh
sudo mkdir -p /srv/nfs/k8s/postgres /srv/nfs/k8s/redis
sudo chown nobody:nogroup /srv/nfs/k8s/postgres /srv/nfs/k8s/redis
sudo chmod 777 /srv/nfs/k8s/postgres /srv/nfs/k8s/redis
```
Same deliberate wide-open-permissions simplification already documented
and accepted in US-PLT-12 — not something to carry into a production
design.

## Part B — namespace and secrets

Step 0 runs **on your laptop**, from the repo root. Everything after
that runs **on `vm-master`**, over SSH.

0. **Prepare the real secrets file locally, then copy everything to
   `vm-master` in one step.**

   First, fill in `02-secrets.yaml` on your laptop (easier to edit here
   than over SSH) — **do not skip the password-consistency requirement
   documented at the top of the template**: each password must appear
   identically in `postgres-credentials` and in every `DATABASE_URL`/
   `MIGRATION_DATABASE_URL` that authenticates as that role.
   ```sh
   cp deploy/kubernetes/02-secrets.yaml.example deploy/kubernetes/02-secrets.yaml
   # edit deploy/kubernetes/02-secrets.yaml, replace every CHANGE_ME_* value
   ```

   Then copy the whole `deploy/kubernetes/` directory (now including the
   real `02-secrets.yaml` you just filled in, plus every manifest this
   story and US-PLT-13 need) to `vm-master`, and separately the
   `init-db-roles.sh` script Part C needs — into the same remote
   directory, for one consistent location. Create the remote directory
   first, then copy the source directory's *contents* into it (the
   trailing `/.` matters — `scp -r deploy/kubernetes dest` without it
   copies the directory itself into `dest` when `dest` already exists,
   producing a wrong, nested `dest/kubernetes/` on any re-run rather than
   refreshing the files directly in `dest`; found for real when this bit
   US-PLT-13's Part A.5 re-sync):
   ```sh
   ssh student@172.16.200.20 "mkdir -p ~/deploy-kubernetes"
   scp -r deploy/kubernetes/. student@172.16.200.20:~/deploy-kubernetes/
   scp deploy/docker/postgres/init-db-roles.sh student@172.16.200.20:~/deploy-kubernetes/
   ```
   Every `kubectl` command below that references a file uses
   `~/deploy-kubernetes/<file>` — that's this remote copy, not the local
   repo path. **If you edit any manifest again later, re-run the `scp -r
   .../. ...` line above to refresh the copy on `vm-master` before
   re-applying it** — the remote copy doesn't update itself, and the
   trailing-`/.` form is safe to re-run any number of times without
   nesting.

1. SSH into `vm-master`, then:
   ```sh
   kubectl apply -f ~/deploy-kubernetes/00-namespace.yaml
   kubectl get namespace bookstore
   ```

2. ```sh
   kubectl apply -f ~/deploy-kubernetes/02-secrets.yaml
   kubectl get secrets -n bookstore
   ```
   Expect `postgres-credentials`, `redis-credentials`, `identity-secrets`,
   `catalog-secrets`, `inventory-secrets`, `cart-secrets`, `order-secrets`
   all listed.

## Part C — PostgreSQL

Run **on `vm-master`**.

1. Generate the `postgres-initdb` ConfigMap from the already-proven
   Compose script (copied to `vm-master` in Part B step 0) — one source
   of truth, not a hand-copied YAML:
   ```sh
   kubectl create configmap postgres-initdb \
     --from-file=init-db-roles.sh=~/deploy-kubernetes/init-db-roles.sh \
     -n bookstore
   ```

2. Storage, then the workload:
   ```sh
   kubectl apply -f ~/deploy-kubernetes/10-postgres-pv-pvc.yaml
   kubectl get pv postgres-pv
   kubectl get pvc postgres-pvc -n bookstore
   ```
   Expect both `Bound` before continuing.
   ```sh
   kubectl apply -f ~/deploy-kubernetes/11-postgres-statefulset.yaml
   kubectl rollout status statefulset/postgres -n bookstore
   ```

## Part D — Redis

Run **on `vm-master`**.

```sh
kubectl apply -f ~/deploy-kubernetes/12-redis-pv-pvc.yaml
kubectl get pv redis-pv
kubectl get pvc redis-pvc -n bookstore
```
Expect both `Bound` before continuing.
```sh
kubectl apply -f ~/deploy-kubernetes/13-redis-workload.yaml
kubectl rollout status deployment/redis -n bookstore
```

## Part E — verification (this is the AC evidence)

Run **on `vm-master`** — these are all `kubectl exec`, no files needed,
but still require the working kubeconfig that only exists there.

Full SDD §12 wording ("create order → restart/recreate DB pod → retrieve
order") can't run literally yet — Order doesn't exist until US-PLT-13.
This proves persistence directly instead; the literal closure happens as
part of US-PLT-13's own end-to-end verification. Same documented-gap
treatment already used for US-PLT-11's AC #2.

0. Pull the real credential values from the Secrets already applied to
   the cluster, into shell variables, once — instead of retyping
   `<placeholder>`-style values by hand on every command below. This
   also sidesteps a real bug the first run of this runbook hit: `<` and
   `>` are live bash redirection operators, not inert placeholder markup
   — a literal copy-paste of `-a <REDIS_PASSWORD>` tries to open a file
   named `REDIS_PASSWORD` for input and fails with a confusing
   `No such file or directory` error. Reading the values back from
   `kubectl` avoids that entirely:
   ```sh
   export POSTGRES_USER=$(kubectl get secret postgres-credentials -n bookstore -o jsonpath='{.data.POSTGRES_USER}' | base64 -d)
   export POSTGRES_DB=$(kubectl get secret postgres-credentials -n bookstore -o jsonpath='{.data.POSTGRES_DB}' | base64 -d)
   export REDIS_PASSWORD=$(kubectl get secret redis-credentials -n bookstore -o jsonpath='{.data.REDIS_PASSWORD}' | base64 -d)
   echo "user=$POSTGRES_USER db=$POSTGRES_DB"   # sanity check both are non-empty before continuing
   ```

1. Roles and schemas exist (AC #1):
   ```sh
   kubectl exec -n bookstore postgres-0 -- psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\du'
   kubectl exec -n bookstore postgres-0 -- psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\dn'
   ```
   Expect `identity_migrator`/`identity_app`/`catalog_migrator`/
   `catalog_app`/`inventory_migrator`/`inventory_app`/`order_migrator`/
   `order_app` (8 roles) and `identity`/`catalog`/`inventory`/`orders`
   (4 schemas, plus the default `public`).

2. PostgreSQL write → delete pod → read-back (AC #2):
   ```sh
   kubectl exec -n bookstore postgres-0 -- psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
     "CREATE TABLE IF NOT EXISTS public.us_plt_24_check(v text); INSERT INTO public.us_plt_24_check VALUES ('us-plt-24-$(date -u +%Y%m%dT%H%M%SZ)');"
   kubectl delete pod postgres-0 -n bookstore
   kubectl wait --for=condition=Ready pod/postgres-0 -n bookstore --timeout=120s
   kubectl exec -n bookstore postgres-0 -- psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT * FROM public.us_plt_24_check;"
   ```
   Paste back the row — must match what was written before the delete.
   Drop the check table afterward:
   ```sh
   kubectl exec -n bookstore postgres-0 -- psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP TABLE public.us_plt_24_check;"
   ```

3. Redis write → delete pod → read-back (AC #2):
   ```sh
   REDIS_POD=$(kubectl get pod -n bookstore -l app=redis -o jsonpath='{.items[0].metadata.name}')
   kubectl exec -n bookstore $REDIS_POD -- redis-cli -a "$REDIS_PASSWORD" SET us-plt-24-check "$(date -u +%Y%m%dT%H%M%SZ)"
   kubectl delete pod $REDIS_POD -n bookstore
   kubectl wait --for=condition=Ready pod -n bookstore -l app=redis --timeout=60s
   NEWPOD=$(kubectl get pod -n bookstore -l app=redis -o jsonpath='{.items[0].metadata.name}')
   kubectl exec -n bookstore $NEWPOD -- redis-cli -a "$REDIS_PASSWORD" GET us-plt-24-check
   ```
   Confirms AOF persistence survived pod deletion via the PVC, not
   in-memory luck. `-a` will print a "Warning: using a password with
   '-a' or '-u' option on the command line interface may not be safe"
   notice to stderr — expected, harmless in this lab context.

## What's still open after this runbook

- No probes, no resource requests/limits on either workload yet — US-PLT-14.
- No NetworkPolicy restricting who can reach `postgres-service`/
  `redis-service` yet — US-PLT-19.
- The literal SDD §12 persistence wording (via a real create-order flow)
  is deferred to US-PLT-13's own end-to-end verification, once Order
  exists.
