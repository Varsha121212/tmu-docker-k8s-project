# US-PLT-27: Stage 1-vs-2-vs-3 comparison analysis

**Synthesizes:** `US-PLT-22-stage1-metrics.md`, `US-PLT-25-stage2-metrics.md`,
`US-PLT-26-stage3-metrics.md` (all in this directory),
`evidence/self-healing/US-PLT-16-self-healing-metrics.md`,
`evidence/rolling-update/US-PLT-17-rolling-update-metrics.md`. No new test
execution was performed for this story — this document cross-reads evidence
already captured and verified under US-PLT-16/17/22/25/26.

**Traces to:** PMP §17.1 (Comparison Questions), §17.2 (Metrics and
Collection), §17.4 (Fairness and Analysis Controls); D9 (Comparison analysis
deliverable); BO-06.

---

## 1. Fairness controls cross-check (AC#1)

PMP §17.4 requires: *same load-generator VM/script/dataset size/request
mix/duration; exact versions and image digests recorded; cache state
reset-or-documented; warm-up performed; similar time periods with no
competing workload.* Cross-checked across all three stages below — any
control that did not hold consistently is stated explicitly, not smoothed
over.

| Control | Stage 1 | Stage 2 | Stage 3 | Held consistently? |
|---|---|---|---|---|
| Load-generator | Laptop, native k6 | Laptop, native k6 | Laptop, native k6 | ✅ Yes |
| Script | `tests/load/baseline-p1-p3.js` | Same file | Same file | ✅ Yes (renamed from `stage1-baseline-p1-p3.js` once reused, history preserved) |
| Request mix / duration | P1 5VU/3min, P2 10VU/5min, P3 25VU/8min | Same | Same | ✅ Yes |
| Repeats | 3× per scenario | 3× per scenario | 3× per scenario (P2 additionally re-run after 2 fixes) | ✅ Yes, same repeat count feeding the reported medians |
| Warm-up (P1) excluded from P2/P3 comparison | ✅ | ✅ | ✅ | ✅ Yes |
| No competing workload | ✅ back-to-back, one session | ✅ | ✅ | ✅ Yes |
| Dataset | 16-book catalog, live since Period 3 (not reset) | 16-book catalog, reseeded fresh (content-equivalent, not same row IDs) | 16-book catalog, live since Period 4 (not reset) | ⚠️ **Partial.** Same content, but Stage 1/3 reused already-live state while Stage 2 was reseeded from scratch. Row-ID-level identity was never a project requirement, so this is judged an accepted, disclosed compromise rather than a defect. |
| Cache state | Postgres/Redis live since Period 3, not flushed | Fresh containers/volumes from `docker compose up` | Live since Period 4, not flushed | ⚠️ **Not uniform**, and not independently re-verified per run beyond what each stage's own writeup states — documented here rather than assumed identical. |
| Versions/digests recorded | Monolith `14e619e6`; no image (no containers) | Identity `0.1.1-af12e77` (redeployed 31 Jul), 4 other backend services `0.1.1-a08a02d`, frontend `0.0.0-57a1e9e` | Identity `0.1.1-af12e77`, 4 other backend services `0.1.1-a08a02d`, frontend `0.0.0-57a1e9e` | ✅ Recorded for all three; Stage 2 and Stage 3 now run the identical Identity image (see §1.2). |
| Similar time periods | 27 Jul | 28 Jul | 28 Jul | ✅ Close enough (adjacent days, same sprint window) |

### 1.1 Hardware-topology confound (already flagged in US-PLT-25, restated here as the cross-stage control it actually is)

- **Stage 1**: monolith alone on `vm-baseline-app` (2 vCPU/4 GB); Postgres/Redis
  on a **separate, dedicated** `vm-baseline-db` (its own 2 vCPU/4 GB).
  Combined footprint: **4 vCPU/8 GB across two VMs**.
- **Stage 2**: fully self-contained on `vm-baseline-app` alone — data tier +
  5 services + frontend share **one 2 vCPU/4 GB VM total**.
- **Stage 3**: a 3-node kubeadm cluster, but resource allocation is governed
  by **per-pod requests/limits** (e.g. Catalog 100m CPU/pod, Identity 300m
  CPU limit), not a whole-VM budget — a structurally different allocation
  model from both VM stages, on top of the cluster's own aggregate capacity
  being much larger than either baseline VM's.

This means "Stage 2 uses more CPU than Stage 1" and "Stage 3's Identity pod
hits its CPU limit" are not measuring the same kind of ceiling. Any resource
comparison below is a comparison of *what each platform's allocation model
produces*, not a clean isolation of "orchestration overhead" from "hardware
budget" — PMP §17.1's own Q6 asks exactly this question, and the honest
answer is that hardware topology is a third, uncontrolled axis alongside
platform and architecture.

### 1.2 Identity code-version asymmetry between Stage 2 and Stage 3 — found, then closed

Stage 2's original evidence was captured against Identity `0.1.1-a08a02d` —
the **pre-fix** build, with `PasswordHasher()` at argon2-cffi's
unbounded-memory default and no concurrency cap. Stage 3's P2 data reported
in `US-PLT-26-stage3-metrics.md` was **entirely post-fix** (`0.1.1-af12e77`,
`threading.Semaphore(4)` added) — the pre-fix Stage 3 crash-loop data was
deliberately excluded from the reported medians. At the time this analysis
was first written, **Stage 2 had never been redeployed with the fixed
image after US-PLT-26 found the bug.**

**Resolved 31 Jul 2026.** Identity was redeployed on Stage 2 to
`0.1.1-af12e77` — the identical image Stage 3 runs — and P2 was re-measured
3x (`evidence/baseline-comparison/stage2-p1-p3/p2-run-identity-postfix/`,
full writeup in `US-PLT-25-stage2-metrics.md`). The result: **the fix
produced no measurable change on Stage 2** (RPS/avg/p95 all within
run-to-run noise of the original pre-fix figures). This is itself
informative, not just a formality — it confirms the semaphore fix's
"throughput trade-off" is not an inherent cost of the code change, it only
manifests where a per-container CPU *limit* also exists (Stage 3's 300m
ceiling). Compose has no such limit, so the same concurrency cap never
bound anything beyond the 2 vCPU ceiling that was already saturated before
the fix. Stage 2's originally-reported P2 figures are therefore retained as
representative — they are not stale, superseded numbers, they're numbers
that happen to still hold true under the current, patched code. **Section
3.1 below now reports the Stage 2-vs-3 P2 comparison as genuinely
like-for-like**, since both stages run identical Identity code.

### 1.3 Deployment/setup time is not fairness-controlled across all three stages

- Stage 1: **4 min 30 sec**, live-timed, **application layer only** (OS,
  Python 3.12, Nginx were already installed from US-PLT-20 and untouched).
- Stage 2: **42 sec**, live-timed, but measured **starting from
  already-pulled, locally-cached images** (from US-PLT-21) — closer to a
  container restart than a fresh deploy. Docker's own installation onto
  `vm-baseline-app` was new work Stage 1 never had to do, and is not folded
  into this number.
- Stage 3: **not captured**. The cluster and manifests have been live since
  Period 4 (24 Jul); no re-timed teardown/redeploy was performed for this
  exercise, since doing so would have meant a genuinely disruptive rebuild of
  a live application layer.

**Conclusion for AC#1:** deployment/setup time cannot be reported as a
like-for-like three-way number. Stage 1-vs-2 is at least disclosed as
scope-asymmetric (§1.3 above, repeated in §2). Stage 3 has no comparable
figure at all — this is an open gap in the evidence set, not a fabricated
estimate (per D10/US-PLT-28's own standard against inventing figures).

---

## 2. Stage 1-vs-2: "a complete deployment-model comparison" (AC#2)

Per PMP §17.4's own wording, Stage 1-vs-2 is reported here as a complete
comparison across deployment/setup time, CPU/memory/disk, request rate,
average/p95 latency, and error rate — with the hardware-topology and
dataset-reseed caveats from §1 carried forward rather than dropped.

### 2.1 Deployment/setup time

| | Stage 1 | Stage 2 |
|---|---|---|
| Time | 4 min 30 sec | 42 sec |
| Scope | Full app-layer redeploy (rebuild venv, transfer code, rebuild frontend) | Container orchestration/startup only, from already-cached images |

**Not directly comparable** — different scope, explicitly flagged in
US-PLT-25's own writeup and repeated here per PMP §17.4's instruction not to
overclaim from an unlike-for-like measurement. What *is* fair to say: Stage
2's number demonstrates that once images exist, `docker compose up`
orchestrates an 8-container stack in under a minute — a genuinely fast
inner-loop restart, not a claim about cold-deploy speed.

### 2.2 Request rate, latency, error rate (P1–P3, median of 3 runs)

| Scenario | Metric | Stage 1 | Stage 2 |
|---|---|---|---|
| P1 (5 VU, catalogue) | RPS | 4.84 | 4.21 |
| | Avg latency | 31.09 ms | 182.22 ms (outlier-driven — median 35-42ms) |
| | p95 latency | 47.25 ms | 978.40 ms |
| | Error rate | 0% | 0% |
| P2 (10 VU, mixed incl. login) | RPS | 12.43 | 8.31 |
| | Avg latency | 401.58 ms | 793.61 ms |
| | p95 latency | 1232.04 ms | 2129.14 ms |
| | Error rate | 0% | 0% |
| P3 (25 VU, catalogue-heavy) | RPS | 24.06 | 24.15 |
| | Avg latency | 36.50 ms | 32.50 ms |
| | p95 latency | 56.38 ms | 55.50 ms |
| | Error rate | 0% | 0% |

### 2.3 Resources

| Scenario | Stage 1 CPU (VM) | Stage 2 CPU (VM) | Stage 1 Mem | Stage 2 Mem |
|---|---|---|---|---|
| P1 | ~8.4%, 91.7% idle | ~12%, 88% idle | ~38% (1.49/3.92 GiB) | ~47.5% (1.86/3.92 GiB) |
| P2 | **100%, 0% idle** | **100%, 0% idle** | ~49% (1.9/3.92 GiB) | ~57.7% (2.26/3.92 GiB) |
| P3 | ~8.6%, 91.3% idle | ~30%, 69.6% idle | ~38% | similar to Stage 2's P1 |

Disk stayed flat (~15%) across all Stage 1 runs; not a bottleneck in either
stage at this load.

### 2.4 Findings, stated only where the data supports them

1. **P2's CPU saturation replicates identically in both stages** — the
   Argon2 password-hashing cost (a deliberate security property, not a bug)
   drives both a 2 vCPU VM to 0% idle at only 10 VUs. This is a
   platform-independent finding: container boundaries did not change the
   underlying CPU cost of the hashing work itself.
2. **Idle/baseline memory is measurably higher in Stage 2 at every load
   level** (~47.5% vs ~38% at P1, ~57.7% vs ~49% at P2) — an
   architecture-driven cost of running 5 separate service processes plus
   Postgres, Redis, and a frontend container instead of one shared monolith
   process. This holds regardless of the hardware-topology confound, since
   it is a difference in process count, not compute ceiling.
3. **P3's raw CPU cost is ~3.5x higher in Stage 2 for the identical
   catalogue-only workload** (30% vs 8.6%) — real container/networking
   overhead (client → frontend nginx → catalog container → Postgres
   container, vs Stage 1's single process with a direct DB connection).
   Despite this, **end-to-end P3 latency is nearly identical between stages**
   (32.50ms vs 36.50ms avg) — there is enough idle headroom at this load
   level that the extra per-request overhead does not reach the customer.
4. **P1's average/p95 gap is a small-sample outlier effect, not a systemic
   slowdown** — median latency across all 3 Stage 2 P1 runs was 35-42ms,
   close to Stage 1's P1 *average* of 31ms; the average/p95 figures are
   pulled up by a handful of very slow individual requests per run (max
   1.8-2.9s), consistent with (not fully proven as) cold/low-concurrency
   connection setup across the extra container hops. This is explicitly
   **not** claimed as proven root cause.
5. **Zero errors in both stages across all 9 runs** — under sustained CPU
   saturation (P2), both stages queued rather than failed. This is a
   reliability finding independent of the resource-cost findings above.

**What is and is not concluded:** Stage 2 pays a real, measurable
architecture cost for decomposition (memory footprint, per-request container
hops) even on identical request volume, and does so on half the aggregate
compute of Stage 1's combined app+data footprint (§1.1). It is **not**
concluded that Stage 2 is "worse" in an unqualified sense — P2/P3 end-to-end
latency remained close to Stage 1's despite that cost, and the deployment
speed and resource figures both carry the scope/topology caveats already
disclosed above.

---

## 3. Stage 2-vs-3: isolating "the operational value added by Kubernetes orchestration" (AC#3)

Reported **separately** from §2, per PMP §17.4's explicit instruction, and
built specifically around signals Stage 1/2 have no equivalent for: HPA
replica scaling, self-healing recovery time, and rolling-update behavior —
plus the resource-overhead picture, kept distinct from the orchestration-value
signals rather than blended with them.

### 3.1 Request rate, latency, error rate (P1–P3, median of 3 runs, Stage 2 vs Stage 3)

| Scenario | Metric | Stage 2 | Stage 3 |
|---|---|---|---|
| P1 (5 VU, catalogue) | RPS | 4.21 | 4.82 |
| | Avg latency | 182.22 ms | 35.76 ms |
| | p95 latency | 978.40 ms | 57.60 ms |
| | Error rate | 0% | 0% |
| P2 (10 VU, mixed incl. login) | RPS | 8.31 | **2.23** |
| | Avg latency | 793.61 ms | **3914.67 ms** |
| | p95 latency | 2129.14 ms | **11062.13 ms** (max 15827.77 ms) |
| | Error rate | 0% | 0% |
| P3 (25 VU, catalogue-heavy) | RPS | 24.15 | 24.03 |
| | Avg latency | 32.50 ms | 38.13 ms |
| | p95 latency | 55.50 ms | 76.13 ms |
| | Error rate | 0% | 0% |

**P1 and P3 favor Stage 3** — Stage 3 does not show Stage 2's P1
outlier-latency problem at all, and P3 latency is close between the two
stages despite Stage 3's very different resource-allocation model. **P2
strongly favors Stage 2, and per §1.2 this is now a genuinely like-for-like
comparison** — both stages run the identical Identity image
(`0.1.1-af12e77`), and re-measuring Stage 2 against it produced no material
change from the figures above. The P2 gap is therefore attributable to the
two platforms' different resource-allocation models, not a code-version
mismatch: Stage 2 has no per-container CPU ceiling, so it stays bound only
by the shared VM's real 2 vCPU capacity; Stage 3's Identity pod is pinned to
an explicit 300m CPU *limit* that the semaphore's 4 concurrently-permitted
hashes compete over, while the cluster's other nodes sit at only 8-22%
utilized (§3.2 below). This is a configuration ceiling, not a capacity
problem — raising Identity's CPU limit or adding a replica would likely
close most of this gap, per the follow-up already flagged in
`US-PLT-26-stage3-metrics.md`.

### 3.2 Resource overhead (distinct from orchestration-value signals below)

| | Stage 2 | Stage 3 |
|---|---|---|
| Idle/baseline memory (P1) | ~47.5% of 3.92 GiB | Not directly comparable — per-pod requests/limits, not a shared VM budget |
| P3 CPU vs Stage 1 (identical workload) | ~3.5x higher | Catalog requests only 100m CPU/pod; HPA absorbs load by adding replicas rather than raising per-pod ceiling |
| P2 Identity resource behavior | Full VM CPU saturation (0% idle), shared with 4 other services | Identity pod at 301m CPU, pinned to its own 300m limit, **while cluster nodes sat at only 8-22% utilized** |

The Stage 3 P2 resource picture is the more informative one: it is a
**per-pod limit bottleneck coexisting with abundant idle cluster capacity**,
not a capacity problem. Stage 2 has no equivalent per-container ceiling in
this project's Compose config, so this exact failure mode — a healthy
cluster with one service artificially starved by its own limit — is
structurally something only the Kubernetes deployment could surface.

### 3.3 A genuine operational-value finding: Kubernetes' resource limits surfaced a defect Compose's lack of the same limits let pass

Stage 3's first P2 attempt crashed completely (`OOMKilled`, 0% of
2543-2718 login requests succeeded, `BackOff` x17-18 over 16 minutes),
root-caused to `PasswordHasher()`'s unbounded 64 MiB/hash default combined
with FastAPI's uncapped background-thread concurrency
(`apps/services/identity/app/core/security.py`). **Stage 2 ran this exact
same defect under the exact same P2 load and did not crash** — Compose's
default configuration in this project does not enforce a per-container
memory ceiling, so the identical unbounded-memory-growth bug degraded Stage
2 as CPU saturation (queuing, not failure) rather than a hard kill.

This is a legitimate, evidence-backed example of "operational value added by
orchestration" distinct from raw resource overhead, per PMP §17.4's own
framing: **Kubernetes' resource limits, precisely because they are strict,
turned a latent defect into a visible, fixable failure during formal testing
— rather than a bug that would only have surfaced later, in production,
under less controlled conditions.** The cost of that same strictness is the
throughput trade-off in §3.1's P2 row — and per §1.2's re-measurement, that
cost is specifically attributable to Stage 3's CPU *limit* interacting with
the fix, not to the concurrency cap itself (Stage 2 ran the identical fix
under identical load with no comparable cost, since it has no per-container
CPU limit for the cap to collide with). Both halves of this trade-off are
reported together deliberately, per AC#4's instruction below.

### 3.4 HPA replica scaling (Stage 3-only signal)

Confirmed via the Grafana "Scalability (HPA correlation)" panel and
`kubectl get hpa catalog-hpa -n bookstore -w`: **Catalog scaled 1→3 replicas
during P3**, CPU utilization vs. the 65% target oscillating roughly 10-50%
as load ramped and eased across the 3 repeats. Neither Stage 1 nor Stage 2
has any equivalent mechanism — both are architecturally fixed-capacity for
the duration of a run. Despite Catalog's starting resource footprint being a
small fraction of either VM stage's whole-machine budget (100m CPU/pod
request vs. a shared 2 vCPU VM), **P3 end-to-end latency landed close to
both other stages** (76ms p95 vs. Stage 1's 56ms / Stage 2's 55ms) — evidence
the HPA did its job rather than merely being present but ineffective.

### 3.5 Self-healing recovery time (Stage 3-only signal)

A deleted `catalog` pod was replaced and reached `1/1 Ready` in **12.27s**
(two independent measurements — external Ingress-level availability checks
and `kubectl`'s own pod `AGE` — agreeing to within 1 second), well under the
120s AC threshold, and rescheduled onto a **different worker node** than the
deleted pod (confirming a genuine cross-node reschedule). Full evidence:
`evidence/self-healing/US-PLT-16-self-healing-metrics.md`.

Neither Stage 1 nor Stage 2 has an orchestrator-driven equivalent — Stage
1's only failure-recovery mechanism is systemd's `Restart=on-failure` (never
exercised in this project, no comparable timing exists), and Stage 2's
Compose `restart: unless-stopped` policy was never exercised or measured
either. This is reported as a Stage-3-only capability, **not** as "Kubernetes
recovers faster than Stage 1/2" — no comparable Stage 1/2 recovery-time
measurement exists to support that specific claim, and none is manufactured
here.

### 3.6 Rolling update / rollback (Stage 3-only signal)

`catalog` rolled `0.1.1-a08a02d` → `0.2.0-9bfb373` and back via
`kubectl rollout undo`, both confirmed via `kubectl rollout status` plus the
live pod image. Availability-checked throughout: the original run recorded
3 isolated failed requests total (1 during rollout, 2 during rollback, each
a few-second blip, not a sustained outage) — the runbook's "zero failures"
prediction was wrong and is corrected here rather than left standing. Root
cause was confirmed against the Ingress controller's own logs (`connect()
failed (111: Connection refused)`, a pod already stopped accepting
connections before its removal had propagated to nginx's upstream list) —
not merely theorized. A `lifecycle.preStop: sleep 5` hook was added and the
cycle re-verified: failures dropped from 3 to 1, with the one remaining
failure confirmed to be on the leg that structurally could not yet have the
fix. Full evidence: `evidence/rolling-update/US-PLT-17-rolling-update-metrics.md`.

Neither Stage 1 nor Stage 2 has a rolling-update mechanism in this project —
Stage 1 deploys are a stop/rebuild/start cycle with a real outage window
(not measured as a formal scenario), and Stage 2's `docker compose up`
recreates containers without a surge/drain sequence. This is again reported
as a Stage-3-only capability rather than a comparative claim against
unmeasured Stage 1/2 numbers.

---

## 4. PMP §17.1's six comparison questions, answered directly

1. **VM monolith vs. Compose microservices — deployment effort, startup
   time, response performance, resource use, given both architecture and
   platform differ:** §2 in full. Deployment/setup time is not
   like-for-like (§1.3). Response performance is close at low/high
   concurrency (P1/P3) with a real, disclosed outlier effect at P1; P2 is
   worse in both absolute terms and RPS for Stage 2, on half the aggregate
   compute Stage 1 had (§1.1). Resource use is measurably higher for Stage 2
   at idle and under moderate load (§2.3-2.4).
2. **How does the Kubernetes deployment distribute resource usage and
   respond under increasing catalogue load:** §3.2/§3.4 — Catalog's
   per-pod CPU stays low and the HPA absorbs load by adding replicas (1→3
   under P3) rather than pushing per-pod CPU toward saturation.
3. **Does HPA reduce overload symptoms by adding replicas:** Yes — §3.4;
   P3 latency stayed close to both other stages despite Catalog's far
   smaller starting resource footprint, and the HPA's replica count is
   directly observed scaling in response to load, not merely configured.
4. **How quickly does Kubernetes recover a failed pod compared with
   manual/process-manager recovery on the VM:** Kubernetes' side is
   measured precisely (12.27s, §3.5). **No comparable Stage 1/2 number
   exists** — this question is answered only half; Stage 1/2's
   recovery-time gap is an acknowledged open item (§5), not a fabricated
   comparison.
5. **What operational complexity and resource overhead does Kubernetes
   introduce:** Resource overhead is visible directly in the Identity
   CPU-limit finding (§3.2-3.3) — a per-pod ceiling that Compose's default
   config doesn't enforce, with both a cost (throughput under P2) and a
   benefit (surfaced a real defect) attributable to that same strictness.
   Operational complexity itself (setup/runbook effort) was not formally
   scored in this project's evidence set; the multi-phase runbooks for
   US-PLT-09/12/13 vs. the comparatively short US-PLT-20/21 runbooks are
   suggestive but not a measured metric, so no numeric complexity comparison
   is made here.
6. **Which differences are platform-caused vs. architecture-change-caused:**
   Explicitly not fully separable with this evidence set — §1.1 documents
   hardware topology as a third, uncontrolled axis alongside platform and
   architecture. Findings believed architecture-driven (idle memory
   overhead, §2.4 item 2) are distinguished from findings believed
   platform-driven (HPA elasticity, self-healing, rolling updates, §3.4-3.6).
   P2's Stage 2-vs-3 gap (§3.1/§1.2), originally left ambiguous pending a
   like-for-like re-measurement, is now resolved as platform-driven — both
   stages run identical Identity code, so the gap traces to Stage 3's
   per-pod CPU limit, a configuration choice of the Kubernetes deployment,
   not a code difference.

---

## 5. Claims made only where the data supports them (AC#4)

Per PMP §17.4's explicit instruction not to claim Kubernetes is faster
unless the measurements support it, and to state plainly that orchestration
benefits can be real even where raw resource overhead is higher:

**Supported claims:**
- Stage 3 provides HPA-driven elasticity, self-healing pod replacement
  (12.27s), and rolling-update/rollback with bounded, brief request
  disruption (§3.4-3.6) — none of which Stage 1 or Stage 2 can do at all,
  independent of any latency/throughput number.
- Stage 2 pays a measurable resource cost for decomposition (idle memory,
  P3 CPU) even where end-to-end latency does not show it (§2.4).
- Kubernetes' per-pod resource limits — a form of overhead/rigidity — is
  also what surfaced a real, previously-unknown production-readiness defect
  (Identity OOMKill) during formal testing rather than later (§3.3). This is
  reported as a genuine operational benefit **and** its throughput cost is
  reported in the same section, not separated to make either side look
  better in isolation.

**Claims explicitly NOT made:**
- "Kubernetes is faster than Stage 1/2" — P2's numbers alone would suggest
  the opposite for Stage 3 vs. both other stages, and even P1/P3's Stage-3
  wins are not asserted as a general throughput/latency verdict given the
  P2 counter-evidence and the code-version asymmetry in §1.2.
- "Kubernetes recovers faster than manual/systemd recovery" — no Stage 1/2
  recovery-time measurement exists to compare against (§4, Q4); the 12.27s
  figure is reported as an absolute result against its own 120s AC
  threshold only.
- "Stage 2/3's resource overhead proves decomposition was the wrong choice"
  — no such conclusion is drawn; the overhead is reported as a real,
  disclosed cost, alongside the operational capabilities (§3.3-3.6) that
  Stage 1 structurally cannot provide regardless of resource cost.

---

## 6. Open items / limitations carried into this analysis

- **Stage 3 deployment/setup time was never captured** (§1.3) — a genuine
  gap in the evidence set, not resolved here.
- ~~**Stage 2's Identity image was never redeployed with the OOMKill
  fix**~~ — **Resolved 31 Jul 2026** (§1.2): Identity redeployed to
  `0.1.1-af12e77` on Stage 2, P2 re-measured 3x, no material change from the
  original figures. The Stage 2-vs-3 P2 comparison (§3.1) is now
  like-for-like.
- **P1's Stage 2 outlier-latency mechanism (§2.4 item 4) is not proven**,
  only narrowed to "a few very slow requests," consistent with but not
  confirmed as connection-setup cost.
- **Operational complexity (Q5) was not formally scored** — no metric for
  it exists in this project's evidence set, so no numeric claim is made.
- **Cache/dataset reset was not uniform across the three stages** (§1) —
  documented rather than treated as controlled.

## 7. Evidence index

```
evidence/baseline-comparison/US-PLT-22-stage1-metrics.md
evidence/baseline-comparison/US-PLT-25-stage2-metrics.md
evidence/baseline-comparison/US-PLT-26-stage3-metrics.md
evidence/baseline-comparison/{stage1,stage2,stage3}-p1-p3/
evidence/self-healing/US-PLT-16-self-healing-metrics.md
evidence/rolling-update/US-PLT-17-rolling-update-metrics.md
```
