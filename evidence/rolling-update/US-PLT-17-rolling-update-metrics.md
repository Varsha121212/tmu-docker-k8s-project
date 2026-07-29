# US-PLT-17: Rolling update and rollback — results

**Target:** `catalog` Deployment (`bookstore` namespace). Rollout:
`0.1.1-a08a02d` → `0.2.0-9bfb373` via `kubectl apply -f 22-catalog.yaml`
(image tag + explicit `maxSurge:1/maxUnavailable:0` strategy already
baked into the manifest per Part A/F of the runbook). Rollback:
`kubectl rollout undo deployment/catalog -n bookstore`. Continuous ~1 req/s
availability check against `http://172.16.200.20:30080/api/books/health/ready`
ran throughout both events without stopping in between, logged to
`US-PLT-17-availability-check.log`.

## AC#1 — rollout completes with no sustained outage, new version serves traffic

`kubectl rollout status deployment/catalog -n bookstore --timeout=120s`
returned "successfully rolled out". `kubectl get pods -o jsonpath` confirmed
every Ready `catalog` pod on `172.16.200.23:5000/bookstore/catalog:0.2.0-9bfb373`
afterward. The `get pods -w` transcript shows the expected sequence:
new pod (`catalog-6c9c56c47d-5svjd`) created and reaching `1/1 Ready` at
`12s` **before** the old pod (`catalog-dd84dd546-8vrs9`) moves to
`Terminating` — confirms `maxSurge:1/maxUnavailable:0` actually governed
this rollout, not just the default rounding.

Availability log: **1 failed check** (`000` at 21:36:20.589Z) out of the
requests spanning the rollout, isolated — last success 21:36:19.372Z, next
success 21:36:23.766Z, a ~4.4s blip, not a sustained outage.

**Result: PASS.**

## AC#2 — previous version restored and serving traffic after rollback

`kubectl rollout undo` executed; `kubectl rollout status` again reported
"successfully rolled out". `kubectl get pods -o jsonpath` confirmed the
image back to `172.16.200.23:5000/bookstore/catalog:0.1.1-a08a02d`.
`kubectl get pods -n bookstore` (unfiltered) afterward showed every other
workload still `Running`/`RESTARTS 0` — nothing else was disturbed.

Availability log: **2 failed checks** (`502` then `000` at
21:37:10.861Z / 21:37:12.115Z), isolated — last success 21:37:09.576Z, next
success 21:37:15.307Z, a ~5.7s blip, not a sustained outage.

**Result: PASS.**

## Honest finding: the "zero failures" prediction in the runbook was wrong

The runbook stated `maxUnavailable:0` should produce **zero** failed
requests, not just "no sustained outage." That prediction didn't hold: 3
requests failed total (1 during the rollout, 2 during the rollback), each
in an isolated few-second blip rather than a sustained gap. Both ACs are
still met on their literal wording ("no *sustained* outage"), so this
isn't a story-blocking defect — but the reasoning behind the original
prediction was incomplete and is worth correcting rather than letting the
"zero failures" claim stand uncorrected.

**Most likely explanation (not independently confirmed against ingress
logs):** `maxUnavailable:0` governs *pod-level* bookkeeping — Kubernetes
won't mark the old pod for termination until the new one is Ready — but it
doesn't guarantee *request-level* continuity through the actual teardown.
When the old pod is terminated, its removal from the Service's Endpoints
and its SIGTERM happen close together, but propagating "this pod is gone"
out to kube-proxy's routing rules and to the ingress-nginx controller's own
reloaded upstream config isn't instantaneous. A request can land in that
gap and hit a pod that's already stopped accepting connections, producing
exactly a `502` or a connection timeout (`000`) — this is a well-documented
Kubernetes/ingress-nginx nuance, not unique to this Deployment. The
standard mitigation is a `preStop` lifecycle hook (e.g. `sleep 5`) that
delays actual container shutdown long enough for that propagation to
finish, letting the terminating pod keep draining in-flight connections
during the gap.

This explanation was **not verified against the ingress-nginx controller's
own logs** for these two specific timestamps — it's the standard
explanation for this symptom, offered with that caveat rather than as
confirmed fact. Adding `terminationGracePeriodSeconds`/`preStop` hardening
is optional follow-up work, not required by either AC as written, and
hasn't been done here.

## Known open item: manifest/live-state drift after rollback

`22-catalog.yaml` (both in git and on `vm-master`) still declares
`0.2.0-9bfb373` — the live Deployment is on `0.1.1-a08a02d` after the
rollback. **Deliberately left this way** (user's explicit choice): the
manifest is being kept as "the target to re-promote to" rather than edited
back to match current live state. This means a future
`kubectl apply -f 22-catalog.yaml` against this Deployment, run for any
unrelated reason, will silently redeploy `0.2.0` and undo this rollback —
anyone touching `22-catalog.yaml` or this Deployment next should check
`kubectl get pods -o jsonpath='{...image}'` against what the file declares
before applying, rather than assuming they match.

## Follow-up: `preStop` hardening added and verified (Part J)

Checked directly against the Ingress controller's own logs
(`kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller`):
the rollback blip above was **confirmed**, not just theorized — three
`connect() failed (111: Connection refused)` errors, all against the
just-terminated pod, meaning nginx's own upstream list hadn't yet caught up
with its removal. Added a `lifecycle.preStop: sleep 5` hook to `catalog`'s
container spec in `22-catalog.yaml` to close this gap (delays SIGTERM long
enough for the Endpoints removal to propagate, so the terminating pod keeps
draining in-flight connections instead of going dark first).

Re-ran the rollout/rollback cycle to verify (`22-catalog.yaml`'s Part J):

- **Leg 1** (`0.1.1` [no `preStop`] → `0.2.0` [has `preStop`]): **1 failure**
  (a `499` client timeout against the old pod mid-teardown, confirmed via
  Ingress logs) — expected, since the pod being killed on this leg doesn't
  have the hook yet.
- **Leg 2** (`kubectl rollout undo`, tearing down the `0.2.0` pod that
  *does* have `preStop`): **0 failures.** The old pod's `Terminating` phase
  visibly stretched to ~6-7s (vs ~2s in Leg 1), consistent with the 5s
  sleep actually taking effect, while the availability log recorded
  continuous unbroken `200`s (~1.3-3s cadence) straight through that
  window.

Total failures dropped from 3 (original run) to 1 (this run), and the one
remaining failure is on the leg that was never expected to be fixed. This
is treated as confirmation the fix works, with one honest caveat: the
Ingress-log grep window didn't land exactly on Leg 2's teardown moment
(somewhere between `02:43:06` and `02:43:52`, not independently isolated),
so the zero-failure result for Leg 2 rests on the client-side log's
continuous coverage of that window rather than a directly-observed
"succeeded during teardown" log line. Full evidence:
`evidence/rolling-update/US-PLT-17-availability-check.log` (client-side —
overwritten in place with this second run's data, timestamps `02:42:12`-
`02:44:07` on 29 Jul) and the Ingress-log excerpts in this session's
transcript. The three `vm-master-*-screenshot.png` files were likewise
overwritten with this second run's terminal output.

**Live state after Part J:** rolled back to `0.1.1-a08a02d` again (Leg 2
was another rollback) — same manifest/live-state drift as before, now with
`preStop` included in what `22-catalog.yaml` declares either way.

## Verdict

**US-PLT-17 done and verified**, including the `preStop` follow-up. Both
acceptance criteria satisfied on the original run; the "zero failures"
over-claim was corrected, root-caused via Ingress logs, fixed, and the fix
re-verified against real traffic rather than assumed to work from the
config alone. Deliberate open item remains: manifest/live-state drift
(kept intentionally, per user's choice).
