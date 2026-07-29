# US-PLT-17 Runbook: Rolling update and rollback

**Story:** As a system administrator, I want to deploy a new image version
using a rolling update with a documented rollback command, so that releases
have no full outage and can be safely reverted.

**Acceptance Criteria:**
- AC#1: Given a new immutable image tag with a visibly different version
  marker, when the Deployment is updated, then the rollout completes with
  no sustained outage and the new version serves traffic.
- AC#2: Given a rollout needs to be reverted, when `kubectl rollout undo` is
  executed, then the previous version is restored and serving traffic.

**Traces to:** BO-05, AT-09 ("Deploy a visible v2 label or response.
Rollout completes; no sustained outage; rollback documented."), SDD §15.3.
(`user-stories.md` currently cites `NFR-06` — checked directly against the
BRD `.docx`; no such ID exists there, the BRD's NFR scheme is
category-prefixed (`NFR-AVAIL-01` etc.) and none matches this story. Stale
reference, not corrected yet — flagged here rather than silently treated as
real.)

**Target: `catalog`**, same continuity choice as US-PLT-16. **Visible
version marker = the image tag itself** (a "label," per AT-09's own
either/or wording), not an application-level response field — the code
change needed to expose a version via the API was deliberately dropped
after review; `pyproject.toml`'s `version` field is the single source of
truth, and it already flows into the immutable image tag via the existing
`build-scan-push.sh` (`version_for()` reads `pyproject.toml` directly, tags
as `<version>-<short-commit>`). "New version serves traffic" is evidenced
by correlating `kubectl`'s own report of which image tag every Ready pod is
running against the same unbroken availability-check log used for the
"no outage" proof — not by response content.

**Code already changed this story (committed separately, see Part A):**
`apps/services/catalog/pyproject.toml` version `0.1.1` → `0.2.0`;
`deploy/kubernetes/22-catalog.yaml` gained an explicit
`strategy.rollingUpdate.maxSurge: 1 / maxUnavailable: 0` block. At
`replicas: 1` this matches Kubernetes' own default rounding (25% of 1), so
behavior isn't changing — it's now just readable without redoing that math.
`maxUnavailable: 0` is what actually matters for AC#1: the old pod is never
torn down until the new one is Ready, so **the availability-check log below
is expected to show zero failures**, not just a short acceptable gap like
US-PLT-16's pod-delete test. Any failure in that log during the rollout is
itself a real finding to investigate, not noise to round away.

**`kubectl` only works from `vm-master`.**

## Part A — commit, build, push (two-commit pattern — don't skip the ordering)

Run **on your laptop**, from the repo root. This has to happen in this
order because `build-scan-push.sh` tags images by `git rev-parse HEAD`, not
by working-tree state — building before committing (or committing the
image-tag update in the *same* commit whose hash it needs to reference)
produces a tag that doesn't match what's actually in the image, the exact
mistake already caught and documented in this project once before
(US-PLT-21, see `MEMORY.md`).

```sh
git add apps/services/catalog/pyproject.toml deploy/kubernetes/22-catalog.yaml
git commit -m "feat: bump catalog to 0.2.0, pin explicit RollingUpdate strategy"
```

Build, scan, and push **only** catalog (no need to rebuild the other five
images for this story):
```sh
REGISTRY=172.16.200.23:5000 ./deploy/docker/scripts/build-scan-push.sh catalog
```
Watch for the Trivy gate passing (no unresolved Critical) and the final
`Pushed. Digest: ...` line. Capture the new tag into a variable so the rest
of this runbook doesn't need retyped placeholders:
```sh
export NEW_TAG="0.2.0-$(git rev-parse --short HEAD)"
echo "$NEW_TAG"
```

Now point the manifest at the tag that was actually just built and pushed,
and commit that as its own follow-up change (same reasoning as above — this
commit's hash doesn't need to match anything, it's just recording which
already-built image to deploy):
```sh
sed -i "s#image: 172.16.200.23:5000/bookstore/catalog:.*#image: 172.16.200.23:5000/bookstore/catalog:${NEW_TAG}#" deploy/kubernetes/22-catalog.yaml
grep image deploy/kubernetes/22-catalog.yaml
git add deploy/kubernetes/22-catalog.yaml
git commit -m "chore: point catalog Deployment at ${NEW_TAG}"
```

## Part B — sync to vm-master

Still **on your laptop**:
```sh
scp -r deploy/kubernetes/. student@172.16.200.20:~/deploy-kubernetes/
```

## Part C — confirm the pre-rollout baseline

Run **on `vm-master`**, inside `~/deploy-kubernetes`:
```sh
kubectl get deployment catalog -n bookstore -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
kubectl rollout history deployment/catalog -n bookstore
kubectl get pods -n bookstore -l app=catalog
```
Confirm the image still shows the **old** tag (`0.1.1-a08a02d` or whatever
is currently live) and exactly one `1/1 Running` pod — same clean-baseline
discipline as every prior load/chaos test in this project.

## Part D — start the continuous availability check

Run **on your laptop**, in its own terminal, from the repo root. Same
technique as US-PLT-16 — reuses `/api/books/health/ready` through the
Ingress, ~1 request/second, status code only:

```sh
mkdir -p evidence/rolling-update
while true; do
  ts=$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 \
    http://172.16.200.20:30080/api/books/health/ready)
  echo "$ts $code"
  sleep 1
done | tee evidence/rolling-update/US-PLT-17-availability-check.log
```
Leave running through Parts E **and** G (the rollout **and** the rollback)
— don't stop and restart it between the two, the same continuous log
covers both AC#1 and AC#2.

## Part E — watch the rollout live

Run **on `vm-master`**, in a second terminal:
```sh
kubectl get pods -n bookstore -l app=catalog -w
```
Expect, in order: the existing pod stays `1/1 Running` unchanged; a second
pod appears (`Pending` → `ContainerCreating` → `Running` `0/1`); once it
flips `1/1 Ready`, **only then** does the first pod move to `Terminating`.
Seeing two `1/1 Running` pods briefly overlap is the visible proof of
`maxSurge:1/maxUnavailable:0` actually working — if the old pod disappears
*before* the new one is ready instead, that's a real finding to stop and
investigate, not something to note and continue past.

## Part F — trigger the rollout

Run **on `vm-master`**, in a third terminal, inside `~/deploy-kubernetes`
(the file synced in Part B already has the new tag baked in):
```sh
kubectl apply -f 22-catalog.yaml
kubectl rollout status deployment/catalog -n bookstore --timeout=120s
```
`rollout status` blocks until the rollout finishes or the timeout is hit —
its own exit code is a direct pass/fail signal, don't rely on eyeballing
Part E's `-w` output alone.

Once it returns, confirm AC#1's two clauses directly:
```sh
# No sustained outage - expect this to print nothing at all:
grep -v ' 200$' evidence/rolling-update/US-PLT-17-availability-check.log

# New version serving traffic - expect only the new tag, one entry:
kubectl get pods -n bookstore -l app=catalog -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

kubectl rollout history deployment/catalog -n bookstore
```
If the `grep -v` line prints **anything**, that's a failed AC#1 — capture
the failing timestamps and correlate them against Part E's pod transcript
before deciding whether this is a probe-tuning gap or something else, same
root-cause discipline as US-PLT-16's AC#2 path.

## Part G — roll back

Still **on `vm-master`** — leave Part D's availability-check loop running
(don't stop it, this is the same continuous log covering AC#2 too):
```sh
kubectl rollout undo deployment/catalog -n bookstore
kubectl rollout status deployment/catalog -n bookstore --timeout=120s
```

Once it completes, confirm AC#2:
```sh
grep -v ' 200$' evidence/rolling-update/US-PLT-17-availability-check.log

kubectl get pods -n bookstore -l app=catalog -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

kubectl rollout history deployment/catalog -n bookstore
```
The image should now show the **old** tag again (`0.1.1-a08a02d`), still
zero new failures in the availability log across the entire rollback too.

Stop Part D's loop (Ctrl+C) once this is confirmed.

## Part H — a real gotcha to know about, not to fix reflexively

After `kubectl rollout undo`, the **live** Deployment is back on the old
image, but the **manifest file** (`22-catalog.yaml`, both on `vm-master`
and in git) still declares the new tag — `rollout undo` is an imperative
change to the live object, it doesn't edit the declarative source. If
`kubectl apply -f 22-catalog.yaml` is run again later without updating the
file first, it will silently redeploy the new tag and effectively undo the
rollback. This is expected GitOps-adjacent drift, not a bug to patch here —
just something to know before touching this Deployment again. Decide (and
note in the Review below) whether to leave the manifest pointed at the new
tag as "the target to re-promote to later," or edit it back to match the
rolled-back live state — either is defensible, don't leave the choice
implicit.

## Part I — confirm nothing else regressed

Run the full customer journey (register/log in, browse, add to cart,
checkout, order history) through the Ingress from a real browser, plus:
```sh
kubectl get pods -n bookstore
```
Confirm every other workload is still `Running`/`Ready`, untouched by this
test — same closing check as every prior Kubernetes story.

## Evidence to save

Under `evidence/rolling-update/`: the full availability-check log (covers
both the rollout and the rollback), the `kubectl get pods -w` transcript
from Part E, `kubectl rollout history` output, and a short
`US-PLT-17-rolling-update-metrics.md` write-up (same shape as
`US-PLT-16-self-healing-metrics.md`) — AC#1 and AC#2 each stated as
pass/fail with the log evidence backing each.

---

## Addendum: `preStop` hardening (added after the first real run)

The first execution of Parts A-I passed both ACs, but the availability log
showed 3 isolated failed requests (1 during the rollout, 2 during the
rollback) rather than the predicted zero. Checked directly against the
Ingress controller's own logs
(`kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller`):
the rollback blip is **confirmed** — three `connect() failed (111:
Connection refused)` errors, all against the pod that had just been
terminated, meaning nginx's own upstream list hadn't yet caught up with
that pod's removal. `22-catalog.yaml` gained a `lifecycle.preStop` hook
(`sleep 5`) to close this gap — it delays SIGTERM to the app process just
long enough for the Endpoints removal to finish propagating, so the
terminating pod keeps draining in-flight connections during that window
instead of refusing them outright.

**Important: this fix only takes effect on a pod that already has it in
its own template.** The upcoming rollout (`0.1.1`, no `preStop`, currently
live → `0.2.0`, has `preStop`) will still show the *old* bug pattern on
that leg, because the pod being torn down (`0.1.1`) doesn't have the hook.
The fix is only actually exercised the next time a pod that already has
`preStop` gets terminated — i.e. the rollback that follows.

### Part J — apply, then roll back again, to actually exercise the fix

Run **on your laptop**, from the repo root:
```sh
git add deploy/kubernetes/22-catalog.yaml
git commit -m "fix: add preStop drain hook to catalog to close a confirmed connection-refused gap"
scp -r deploy/kubernetes/. student@172.16.200.20:~/deploy-kubernetes/
```

Run **on `vm-master`**, inside `~/deploy-kubernetes` — start a fresh
availability-check log covering both legs:
```sh
mkdir -p evidence/rolling-update
```
(On your laptop, in its own terminal, same as Part D:)
```sh
while true; do
  ts=$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 \
    http://172.16.200.20:30080/api/books/health/ready)
  echo "$ts $code"
  sleep 1
done | tee evidence/rolling-update/US-PLT-17-prestop-verify.log
```

Leg 1 — apply the `preStop`-carrying manifest (expect the same old
`Connection refused` pattern here, since the pod being killed is the
current `0.1.1` one without the hook — this leg is not the test):
```sh
kubectl apply -f 22-catalog.yaml
kubectl rollout status deployment/catalog -n bookstore --timeout=120s
kubectl get pods -n bookstore -l app=catalog -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'
```

Leg 2 — **this is the real test.** Roll back again — this terminates the
`0.2.0` pod that *does* have `preStop`:
```sh
kubectl rollout undo deployment/catalog -n bookstore
kubectl rollout status deployment/catalog -n bookstore --timeout=120s
kubectl get pods -n bookstore -l app=catalog -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'
```

Stop the availability-check loop, then compare:
```sh
grep -v ' 200$' evidence/rolling-update/US-PLT-17-prestop-verify.log
```
If Leg 2's portion of the log (timestamps after the `rollout undo`) shows
zero failures where the original run showed 2, that's confirmation the fix
works. If it still shows failures, check the Ingress controller's logs
again the same way as before — `Connection refused` would mean the fix
didn't close the gap (5s wasn't enough, or another mechanism is at play);
a different error would point somewhere new. Either way, update
`US-PLT-17-rolling-update-metrics.md` with the result rather than leaving
the original "3 failures" finding as the last word without noting whether
the follow-up fix actually worked.

Note: after Part J, the live image is back on `0.1.1-a08a02d` again (Leg 2
is a rollback) — the same manifest/live-state drift from Part H applies
again, now with `preStop` included in what the manifest declares either
way.
