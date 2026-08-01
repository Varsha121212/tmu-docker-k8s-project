# Post-Gate-6 addendum: Stage 2 Identity redeploy + P2 re-measurement

**Story:** Close the Identity code-version asymmetry `US-PLT-27` flagged
between Stage 2 and Stage 3's P2 data, so the Stage 2-vs-3 P2 comparison in
the final report is genuinely like-for-like rather than confounded by one
stage running pre-fix code.

**Traces to:** `US-PLT-27-comparison-analysis.md` §1.2/§6 (open item),
`US-PLT-28` §9.4 (future work item). Real work performed after Period 5
(Gate 6) was already marked complete — no formal story number assigned yet.

## Plan
- [x] `deploy/docker/docker-compose.yml` — added `IDENTITY_IMAGE_TAG`
      (mirrors the existing `FRONTEND_IMAGE_TAG` precedent), so Identity
      alone can run a different tag than the other four backend services.
- [x] Commands given for user to run: sync compose file to
      `vm-baseline-app`, add `IDENTITY_IMAGE_TAG=0.1.1-af12e77` to `.env`,
      pull/retag the image (already built/pushed during `US-PLT-26`),
      `docker compose up -d identity` (only Identity + its migration job
      recreated, nothing else touched or reseeded).
- [x] User ran P2 3x against the patched image, evidence saved to
      `evidence/baseline-comparison/stage2-p1-p3/p2-run-identity-postfix/`.
- [x] Compared new numbers against the original pre-fix P2 figures: RPS 8.25
      vs 8.31, avg 806.93ms vs 793.61ms, p95 2150.19ms vs 2129.14ms, 0%
      errors both — statistically indistinguishable.
- [x] User's explicit choice: keep the original P2 figures as reported
      (not worth a table swap for a difference this small), but disclose
      the version patch everywhere Identity's version is cited — raised and
      resolved a real correctness concern (see `MEMORY.md`, 31 Jul entry)
      about not silently presenting the new run as if it were the original.
- [x] `US-PLT-25-stage2-metrics.md` — version note added, numbers unchanged.
- [x] `US-PLT-27-comparison-analysis.md` — §1.2, §3.1, §3.3, §4 Q6, §6
      updated: asymmetry marked resolved, P2 gap now explained as Stage 3's
      CPU-limit configuration rather than a code-version confound.
- [x] `documents/report/US-PLT-28-final-report-draft.md` — matching updates
      (Executive Summary, OBJ-08 table, §7.2, §8.1, §8.4, §8.5 Q6, §9.2);
      "re-measure Stage 2 P2" removed from §9.4 Future Work (done).
- [x] `MEMORY.md` updated.

## Review

**Done and verified.** The re-measurement itself is a genuine finding, not
just a formality: it confirms the P2 throughput/latency gap between Stage 2
and Stage 3 traces to Stage 3's per-pod 300m CPU limit interacting with the
concurrency-cap fix, not to the fix itself — Stage 2 ran the identical fix
under identical load with no comparable cost, since Compose enforces no
per-container CPU limit for the cap to collide with. This resolves §1.2 of
`US-PLT-27` and the matching open item in the final report.

Not yet done: formalizing this as a numbered backlog story
(`user-stories.md`/`sprint-plan.md`) if the team wants Period 6 tracked
explicitly — flagged, not actioned, since it wasn't asked for.

---

# US-PLT-28: Final academic report draft

**Story:** As the project team, I want a complete draft of the final
academic report assembled from the project's actual evidence trail, so
that Gate 6's "complete report draft" milestone and OBJ-09 are met with a
document that reflects what actually happened, not a retrospectively
sanitized success narrative.

**Traces to:** D10, OBJ-09, PMP §7.2 (Gate 6 schedule line), Gate 7 (later,
separate scope). Depends on US-PLT-27 (done) and, practically, on
AT-01–AT-12 (still not a backlog story). **Points:** 8 — largest in the
backlog, flagged as a split candidate; delivered as one continuous pass per
user's own pacing choice.

## Plan
- [x] Clarified four open decisions with the user before writing anything
      (AskUserQuestion): output format (Markdown draft first, .docx
      transcription later), author names/student IDs (leave placeholders —
      can't fabricate for an academic submission), academic citations
      (leave numbered placeholder slots — can't fabricate sources), pacing
      (one continuous pass across all chapters).
- [x] Extracted `CN8001_report_template.docx`'s exact required structure,
      formatting rules (Heading 1/2/3, Calibri 11, 1.5 spacing,
      chapter.section figure/table numbering, 40-page main-body limit),
      and citation-order requirement directly from the `.docx` XML (grep
      can't reach binary files).
- [x] Extracted PMP §17.1/17.2/17.4, BRD's full objectives/success-criteria/
      requirements tables, and SDD's full design/ADR content the same way,
      to ground every chapter in the actual accepted project documents
      rather than a paraphrase.
- [x] Read the remainder of `MEMORY.md` (offset 899 through end, ~1,400
      lines not yet in context this session) end to end, plus
      `tasks/lessons.md` in full, to build a complete defect inventory
      before writing the Post Analysis chapter — not just the five defect
      categories AC#1 names as a minimum.
- [x] Drafted all chapters per the template's structure: front matter
      (title/scope-note/executive-summary/acknowledgements/certification/
      TOC), Introduction, Objectives, Background, Theory and Design,
      Alternative Designs, Measurement and Testing Procedures, Measurement
      Results, Post Analysis, Conclusions, Appendices, References.
- [x] Verified every quantitative claim in the draft traces to a real
      evidence artifact already in `evidence/` — no invented, estimated,
      or rounded-for-narrative-convenience figures (AC#2).
- [x] Built a 13-entry defect log (§8.6) covering at minimum the five
      US-PLT-20 VM bugs, the frontend healthcheck IPv6 bug, the Argon2
      CPU-saturation finding, the Identity OOMKill/semaphore fix and its
      CPU-limit second-order finding, and the rolling-update `Connection
      refused`/`preStop` fix (AC#1's stated minimum), plus additional
      defects (Trivy CVE risk acceptance, containerd schema mismatch, the
      Kubernetes frontend crash-loop, the seed-job race condition)
      referenced in Appendix A.
- [x] Stated the report's own scope explicitly (Report Scope Note,
      up front): written report + evidence appendices in scope; live
      presentation delivery, the demo switch-over script pair, and Gate 7's
      correction pass explicitly out of scope (AC#3).
- [x] `documents/report/US-PLT-28-final-report-draft.md` written (~11,400
      words).
- [x] Cleaned up scratch `.docx`-extraction text files from `documents/`
      (should have used the scratchpad directory — corrected before they
      were left behind).
- [x] `sprint-plan.md` updated (status table, Period 5 update note,
      capacity check, cross-period summary table — Period 5 now fully
      complete).
- [x] `MEMORY.md` updated.

## Review

**Done and verified against all three acceptance criteria.** The draft is
markdown-first (per user's choice), structured to match
`CN8001_report_template.docx` exactly, with a formatting note at the top
flagging the still-outstanding .docx transcription pass as a distinct,
later step — not silently implied as already done.

Two real gaps were deliberately left visible rather than quietly filled:
**author names/student IDs and academic citations remain marked
placeholders** — the BRD/PMP's own placeholder convention was reused for
names, and numbered `[1]`–`[5]` citation slots with explicit `TODO` markers
were used for sources, since inventing either would be fabrication in an
academic submission, not a shortcut. Both were the user's own explicit
choice when asked, not a default picked to fill it fastest.

Cross-checking the whole project's `MEMORY.md` history (not just the most
recent stories still in this session's active context) against AC#1's
"at minimum" defect list surfaced that the minimum list itself undersells
how many real defects this project actually found and fixed — the final
defect log (§8.6) has 13 entries, plus several more referenced in
Appendix A, everything traced to a dated `MEMORY.md` entry or an
`evidence/` artifact.

Full draft: `documents/report/US-PLT-28-final-report-draft.md`.
`documents/backlog/sprint-plan.md` updated — **Period 5 (Gate 6) is now
fully complete, 30/30 committed points, all 8 stories verified.** The
period's own final overcommit ratio (~2.0–3.0x against its 10–15 point
capacity range) is reported as-is in the sprint plan rather than smoothed
over now that the work is done — consistent with this project's standing
practice of treating the sprint plan as an honest signal, not a flattering
retrospective. `MEMORY.md` updated.

---

# US-PLT-27: Stage 1-vs-2-vs-3 comparison analysis

**Story:** As the project team, I want the three stages' already-captured
P1–P3 evidence (US-PLT-22/25/26) synthesized into the deployment-model
comparison PMP §17.4 requires, so that the project's central research
question is actually answered in writing, not left as three separate
evidence folders nobody has cross-read.

**Traces to:** PMP §17.4, D9, BO-06, Gate 6. Depends on US-PLT-22/25/26 (all
done). **Points:** 3 — synthesis/analytical writing only, no new test
execution or infrastructure work.

## Plan
- [x] Read PMP §17.1 (six comparison questions), §17.2 (metrics table),
      §17.4 (fairness controls) directly from the `.docx` (grep can't reach
      binary files) to work from the exact required wording, not a
      paraphrase.
- [x] Cross-read all five source evidence files (US-PLT-16/17/22/25/26) end
      to end before writing anything.
- [x] Cross-check fairness controls (AC#1) across all three stages
      explicitly, rather than assuming US-PLT-22/25/26 each independently
      satisfying PMP §17.4 within their own stage means the controls held
      *across* stages too.
- [x] Write Stage 1-vs-2 as "a complete deployment-model comparison" (AC#2).
- [x] Write Stage 2-vs-3 separately, isolating orchestration-only signals
      (HPA, self-healing, rolling update) from resource-overhead signals
      (AC#3).
- [x] State only claims the data actually supports; explicitly list claims
      NOT made, per PMP §17.4's "don't claim Kubernetes is faster unless the
      data shows it" instruction (AC#4).
- [x] `evidence/baseline-comparison/US-PLT-27-comparison-analysis.md`
      written.
- [x] `sprint-plan.md` updated (status table, Period 5 update note, capacity
      check, cross-period summary table).
- [x] `MEMORY.md` updated.

## Review

**Done and verified — no new test execution, all findings traced to
already-captured evidence.** Cross-checking the fairness controls (rather
than assuming them) surfaced two real, previously-undocumented gaps:

1. **Stage 2's Identity image was never redeployed with the OOMKill fix**
   found during US-PLT-26. Stage 2's P2 dataset (`0.1.1-a08a02d`) reflects
   the pre-fix, unbounded-concurrency Argon2 code; Stage 3's P2 dataset is
   entirely post-fix (`0.1.1-af12e77`, semaphore-capped). This means the
   Stage 2-vs-3 P2 comparison (Stage 2 far outperforms Stage 3 on RPS/
   latency) is **not** a clean orchestration-only comparison — a real share
   of that gap is the semaphore fix's own throughput trade-off, measured
   against a Stage 2 baseline that was never re-run under the same fix.
   Flagged explicitly in the analysis rather than presented as a clean
   Stage-2-wins-P2 result.
2. **Stage 3's deployment/setup time was never captured** at all (no
   re-timed teardown/redeploy was performed, unlike Stage 1's 4m30s and
   Stage 2's 42s) — the three-way deployment-time comparison PMP §17.2 asks
   for is genuinely two-way in the evidence that exists, not three-way.
   Left as an open gap, not filled with an estimate.

One genuine operational-value finding worth carrying into the final report
(US-PLT-28): **Kubernetes' per-pod resource limits — a form of overhead —
are what surfaced the Identity OOMKill defect during formal testing at
all.** Stage 2 ran the identical unbounded-memory-growth bug under the
identical P2 load and did not crash, because Compose's config in this
project enforces no equivalent per-container memory ceiling; it degraded as
CPU saturation instead. Reported as a real benefit of orchestration
strictness, with its own throughput cost (§3.1/§3.3 of the write-up)
reported alongside it, not hidden.

Per PMP §17.4's explicit instruction, **no "Kubernetes is faster" claim is
made anywhere in the write-up** — P1/P3 favor Stage 3, P2 favors Stage 2 (with
the code-version caveat above), and a dedicated section lists exactly which
claims the data does and does not support.

Full write-up: `evidence/baseline-comparison/US-PLT-27-comparison-analysis.md`.
`documents/backlog/sprint-plan.md` updated — **Period 5 now 22/30 points,
US-PLT-28 (final report draft) the only story remaining.** `MEMORY.md`
updated.

---

# US-PLT-17: Rolling update and rollback

**Story:** As a system administrator, I want to deploy a new image version
using a rolling update with a documented rollback command, so that releases
have no full outage and can be safely reverted.

**Traces to:** BO-05, AT-09, SDD §15.3. (`user-stories.md` cites `NFR-06`,
which doesn't exist anywhere in the BRD — checked directly against the
`.docx`, since grep can't reach binary files. Flagged, not yet corrected in
`user-stories.md`.) **Points:** 3.

**Target: `catalog`**, continuing the reference-workload choice from
US-PLT-14/15/16. Visible version marker = the image tag itself (a "label,"
per AT-09's literal "v2 label or response" wording) — an earlier plan to
also expose the version through the `/api/books/health/ready` response body
was proposed, then dropped after the user correctly pointed out it
introduced a redundant version channel (`ARG`→`ENV`) alongside
`pyproject.toml`, which is already the single source of truth
`build-scan-push.sh` reads from.

## Plan
- [x] `apps/services/catalog/pyproject.toml` — version `0.1.1` → `0.2.0`.
- [x] `deploy/kubernetes/22-catalog.yaml` — explicit
      `strategy.rollingUpdate.maxSurge: 1 / maxUnavailable: 0` (matches the
      existing default at replicas:1, now readable without redoing the
      rounding math).
- [x] Catalog test suite re-run: 12/12 pass, unaffected by the version bump.
- [x] Runbook written: `deploy/kubernetes/US-PLT-17-runbook.md` — two-commit
      build/push/retag pattern (avoids the tag/commit-hash mismatch already
      caught once in US-PLT-21), continuous availability-check log reused
      from US-PLT-16 covering both the rollout and the rollback in one
      unbroken log, `kubectl rollout status`/`rollout history` for direct
      pass/fail signals, and an explicit flag about the manifest/live-state
      drift `rollout undo` leaves behind.
- [x] User executed the runbook (commit → build/push → sync → rollout →
      rollback).
- [x] Evidence saved under `evidence/rolling-update/`.
- [x] `sprint-plan.md` updated.

## Review

**Done and verified.** Catalog rolled `0.1.1-a08a02d` → `0.2.0-9bfb373` via
`kubectl apply -f 22-catalog.yaml`, confirmed via `kubectl rollout status`
("successfully rolled out") and `kubectl get pods -o jsonpath` showing the
new image on the only Ready pod. `kubectl rollout undo` then reverted to
`0.1.1-a08a02d`, confirmed the same way. Both ACs met.

**Honest correction, then root-caused and fixed:** the runbook predicted
zero failed requests given `maxUnavailable:0`; the actual log showed 3
failed requests total (1 during the rollout, 2 during the rollback), each
an isolated few-second blip, not a sustained outage — so both ACs ("no
*sustained* outage") still passed on the original run, but the "zero
failures" framing was wrong. Checked directly against the Ingress
controller's own logs (not just theorized): **confirmed** — three
`connect() failed (111: Connection refused)` errors against a pod that had
already stopped accepting connections before its removal finished
propagating to nginx. Added a `lifecycle.preStop: sleep 5` hook to
`22-catalog.yaml` and re-ran the full rollout/rollback cycle to verify:
failures dropped from 3 to 1, and the surviving failure was confirmed (via
Ingress logs again) to be on the leg that structurally couldn't have the
fix yet (the old `0.1.1` pod being replaced doesn't carry `preStop` in its
own template) — the leg that *did* have the fix (`0.2.0`'s pod, torn down
during the second rollback) showed zero failures despite a visibly longer
(~6-7s vs ~2s) teardown, matching the 5s sleep taking effect.

**Deliberate open item:** `22-catalog.yaml` still declares `0.2.0-9bfb373`
while the live Deployment is back on `0.1.1-a08a02d` (post Part-J rollback)
— user's explicit choice to leave the manifest as "the target to
re-promote to" rather than edit it back to match live state. Flagged
prominently in the metrics write-up so it isn't silently forgotten and
someone doesn't `kubectl apply` this file later without checking what it'll
actually do.

Full write-up: `evidence/rolling-update/US-PLT-17-rolling-update-metrics.md`.
`documents/backlog/sprint-plan.md` updated — **Period 5 (Gate 6) is now
fully complete, 19/19 points, all 6 stories verified.** `MEMORY.md` updated.

---

# US-PLT-16: Self-healing validation

**Story:** As a system administrator, I want to demonstrate that a deleted
stateless application pod is automatically replaced, so that the project
provides evidence of Kubernetes self-healing.

**Traces to:** NFR-AVAIL-01, AT-08, section 15.2. Depends on US-PLT-14
(probes, done) and US-PLT-13 (Deployments/Services, done). No manifest
changes — this story exercises infrastructure that already exists.
**Points:** 2.

**Target: `catalog`** (single replica, stateless, already this project's
reference workload for probe/HPA stories) — see the runbook's own header
for the full reasoning on why a single-replica target gives the clearest,
least-ambiguous recovery-time signal.

## Plan
- [x] Runbook written: `deploy/kubernetes/US-PLT-16-runbook.md` — confirm
      clean 1-replica baseline, start a continuous ~1req/s availability
      check against `/api/books/health/ready` through the Ingress (logged
      to `evidence/self-healing/`), delete the pod, watch the replacement
      come up via `kubectl get pods -w`, measure the outage window from the
      availability log, compare against the 120s AC#1 threshold, and (AC#2)
      a documented root-cause path if that threshold is ever exceeded.
- [x] User executed the runbook against the real cluster (`vm-master` +
      laptop, over the VPN).
- [x] Evidence saved under `evidence/self-healing/` (availability-check log,
      `kubectl get pods -w` transcript, two screenshots, metrics write-up).
- [x] `sprint-plan.md` updated.

## Review

**Done and verified.** Pod `catalog-dd84dd546-fk2cg` deleted on `vm-master`;
replacement (`catalog-dd84dd546-cqjxz`) rescheduled onto a **different
worker node** (`vm-worker-2` → `vm-worker-1`) and reached `1/1 Ready` in
**12.27s**, measured independently two ways that agree within kubectl's
1-second AGE resolution: (1) the external availability-check log
(first non-`200` at 19:59:32.551Z, first recovered `200` at 19:59:44.821Z),
and (2) `kubectl get pods -w`'s own `AGE` column showing `1/1 Running` at
`12s`. Well under AC#1's 120s threshold (~10x margin) — AC#2's defect-log
path was never triggered. Full customer journey re-confirmed working
through the Ingress afterward (Part G); every other workload's `RESTARTS`
stayed at 0, confirming the test didn't disturb anything outside `catalog`.
One non-defect observation logged for completeness: `ingress-nginx`
returned one `502` then steady `503`s during the gap — normal
zero-ready-endpoints behavior, not an application error.

Full write-up: `evidence/self-healing/US-PLT-16-self-healing-metrics.md`.
`documents/backlog/sprint-plan.md` updated (Period 5 now 16/19 pts,
US-PLT-17 the only story remaining). `MEMORY.md` updated.

---

# US-PLT-25 / US-PLT-26: Stage 2 / Stage 3 baseline comparison metrics (P1-P3)

**Correction (28 Jul):** originally treated as non-story "test execution
time" per Period 5's own framing (see below) — the user caught this as a
real gap, the same class as US-PLT-20/21/22/23/24 (real work happening
without a backlog entry). Formally added as **US-PLT-25** (Stage 2, 3 pts)
and **US-PLT-26** (Stage 3, 5 pts) in `user-stories.md` and `sprint-plan.md`
— see those files' own change-control notes. Period 5 capacity check
updated from "under capacity by design" to a **~1.3-1.9x overcommit flag**
(19 pts committed vs 10-15 capacity), the honest consequence of surfacing
this work rather than leaving it invisible.

Original framing, kept for context: this was initially executed as "test
execution time," the same bucket as the acceptance-test suite and the
comparison writeup itself, done before US-PLT-16/17's destructive tests so
the "normal/moderate load" baseline reflects steady state, not a
just-recovered/just-rolled-out cluster — same "capture clean data before
the environment gets perturbed" logic that put US-PLT-22 ahead of US-PLT-21,
just without a hard deadline.

## Review

**Done — all three stages' P1-P3 baseline data now captured.**
`evidence/baseline-comparison/US-PLT-22-stage1-metrics.md`,
`US-PLT-25-stage2-metrics.md`, `US-PLT-26-stage3-metrics.md`. Headline
findings across the exercise: the Argon2 CPU-saturation finding from Stage 1
replicated in Stage 2 exactly as predicted; Stage 2 pays a real,
architecture-driven memory/CPU overhead cost for decomposition even when
latency doesn't show it; Stage 3 uncovered a genuine, previously-undiscovered
production-readiness defect (Identity's OOMKill crash-loop under literally
PMP 15.4's own "Normal load" scenario, violating NFR-08) that was
root-caused to real code (not guessed), fixed with a concurrency semaphore
rather than weakening Argon2's security parameters, and the fix's own
side-effect (severe queuing latency, not a crash) was then measured and
reported rather than declared "done" after the crash stopped. This whole
arc — real bug found via formal load testing, root-caused, fixed correctly,
re-measured, side-effect of the fix also reported honestly — is exactly
what this kind of testing exists to produce, and is strong report material
in its own right, not just baseline numbers for a comparison table.

Next: US-PLT-16 (self-healing) and US-PLT-17 (rolling update/rollback),
both against the now-more-battle-tested Kubernetes cluster.

## Prep done already
- [x] Renamed `tests/load/stage1-baseline-p1-p3.js` → `baseline-p1-p3.js`
      (`git mv`, history preserved) — script was always stage-neutral via
      `BASE_URL`, just misleadingly named. Updated references in
      `US-PLT-22-stage-1-runbook.md`, `US-PLT-22-stage1-metrics.md`.
- [x] Checked Catalog HPA's current state before assuming a clean baseline:
      `kube_horizontalpodautoscaler_status_current_replicas{horizontalpodautoscaler="catalog-hpa"}`
      = **1** — clean, no leftover scale-up from US-PLT-15 testing.
- [x] Proactively fixed the identical p99/error-rate cardinality-fragmentation
      bug (found and fixed in `grafana-dashboard-baseline.json` during
      US-PLT-22) in the **original** Stage 3 dashboard
      (`infrastructure/monitoring/grafana-dashboard.json`, panels 13/14) —
      about to trigger it for real with this same script against Stage 3,
      no reason to hit it twice. Needs re-import in Grafana (same UID,
      updates in place).

## Plan
- [x] Stage 2 runbook (`deploy/baseline-vm/US-PLT-25-stage-2-runbook.md`)
      written — reuses `grafana-dashboard-baseline.json` unchanged, plus an
      optional clean deployment-time re-measurement (Stage 2's US-PLT-21
      deploy included live bug debugging, so that elapsed time isn't a fair
      comparison number).
- [x] Stage 3 runbook (`deploy/kubernetes/US-PLT-26-stage-3-runbook.md`)
      written — targets `http://172.16.200.20:30080` (Ingress), reuses the
      now-fixed `grafana-dashboard.json`. Explicit note: unlike Stage 1/2,
      Catalog has an HPA - if P3's 25 VUs pushes it to scale, that's real
      Stage 3 behavior to record, not a confound to suppress or avoid.
- [ ] Evidence: `evidence/baseline-comparison/{stage2,stage3}-p1-p3/`, same
      `{p1,p2,p3}-run/` substructure as Stage 1's.
- [x] Stage 2 writeup: `US-PLT-25-stage2-metrics.md` done. Real findings:
      Argon2 CPU-saturation finding replicates in Stage 2 (P2, same as
      Stage 1); idle/baseline memory measurably higher at every load level
      (more processes); P3's raw CPU ~3.5x Stage 1's for identical
      workload but latency ends up nearly the same (enough idle headroom
      to absorb it); P1's latency is dramatically worse (~6x avg, ~20x
      p95) with CPU *not* saturated - flagged honestly as unconfirmed
      (two plausible contributors given, neither proven). **Prominent
      caveat added up top, not buried in a table:** Stage 1 had Postgres/
      Redis on a separate dedicated VM (4 vCPU/8GB combined app+data);
      Stage 2 squeezes everything onto one 2 vCPU/4GB VM - any
      "Stage 2 is slower" reading is partly a hardware-topology confound,
      not purely orchestration overhead (PMP 17.1 Q6).
- [x] Deployment-time re-measurement (Part A): **42 seconds** (user ran it).
      Flagged as not directly comparable to Stage 1's 4m30s — this run
      started from already-cached local images (from US-PLT-21), so it
      measures orchestration/restart time only, not a cold pull+deploy.
- [x] P1's outlier question resolved from existing data, no re-run needed:
      checked full `http_req_duration` breakdown (min/med/p90/p95/max) per
      run - median was 35-42ms across all 3 runs, barely different from
      Stage 1's P1 average (31ms). The average/p95 gap is driven by a
      small number of extreme outliers (max 1.8-2.9 seconds per run), not
      a systemic slowdown - consistent with cold/low-concurrency
      connection setup at only ~4-5 req/s, though not fully proven.
      Writeup updated with the refined finding.
- [x] Stage 3 P1 x3 done, clean (no issues).
- **Real bug found during Stage 3 P2 run1: Identity OOMKilled, sustained
  crash-loop for the whole test window.** `kubectl describe pod` confirmed
  `Reason: OOMKilled, Exit Code: 137`, `BackOff (x18 over 16m)` - not a
  single crash, a persistent loop. Root cause traced to real code, not
  guessed: `apps/services/identity/app/core/security.py`'s
  `PasswordHasher()` uses argon2-cffi's default `memory_cost=65536 KiB`
  (64 MiB) *per hash operation* - a few concurrent logins' hashing buffers
  alone approached the old 256Mi container limit. Directly violates
  NFR-08 ("no pod is OOMKilled... under normal load") - P2 literally *is*
  PMP 15.4's "Normal" load scenario, not an edge case.
  **Fix (confirmed with user via AskUserQuestion): raise the K8s memory
  limit, not weaken Argon2.** `deploy/kubernetes/21-identity.yaml`:
  128Mi/256Mi -> 256Mi/512Mi request/limit. Kubernetes-manifest-only,
  doesn't touch the shared Identity image (ADR-007) - Stage 2 completely
  unaffected, same "smallest blast radius" precedent as the frontend
  healthcheck fix. Rejected: reducing Argon2's `memory_cost` - would also
  affect Stage 2 (shared image) and is a real security trade-off (weakens
  GPU/ASIC brute-force resistance), not just an infra tweak.
  User applying the fix and re-running all 3 P2 repeats fresh (run1's data
  is invalid - crash-loop artifact, not real measurement).
- [x] Semaphore fix (`threading.Semaphore(4)` around Argon2 calls in
      `apps/services/identity/app/core/security.py`) confirmed with user
      via AskUserQuestion after the first fix (raising memory 256Mi->512Mi
      alone) was tested and shown insufficient - pod OOMKilled again at
      512Mi, proving unbounded concurrency was the real problem, not
      headroom. 11 identity tests pass; verified live with a 6-concurrent
      curl burst (all 200, memory stayed ~62Mi) before re-running k6.
      Committed (af12e77), rebuilt/pushed `identity:0.1.1-af12e77`,
      redeployed, confirmed 0 restarts.
- [x] Stage 3 P2 x3 (post-fix) and P3 x3 done. **Real, non-obvious result:
      fixing the crash didn't make P2 normal - it traded a total outage
      for severe queuing latency.** RPS collapsed to 2.23 (vs Stage 1's
      12.43), p95 hit 11 seconds (max 15.8s), 0% errors throughout.
      `kubectl top pods` showed identity at 301m CPU (at its 300m limit)
      while `kubectl top nodes` showed the cluster at only 8-22%
      utilized - a per-pod CPU-limit bottleneck coexisting with abundant
      idle cluster capacity, not a capacity problem. Directly validates
      the earlier HPA-for-Identity discussion (user's question) with real
      data rather than leaving it purely hypothetical.
      P3: Catalog HPA genuinely scaled 1->3 during the run (Grafana +
      `kubectl get hpa -w` both confirm) - recorded as real Stage 3
      elasticity, not suppressed, per the runbook's own instruction.
      P1/P3 both track Stage 1/2 closely; Stage 3 doesn't show Stage 2's
      P1 outlier-tax problem at all.
- [x] Stage 3 writeup: `US-PLT-26-stage3-metrics.md` done - OOMKill finding
      and the post-fix CPU-limit finding both surfaced prominently up top,
      same treatment as Stage 2's hardware-topology caveat.
      Full three-way comparison analysis (PMP 17.4) deferred to
      report-drafting time, not done here.
- [ ] Update `MEMORY.md` once both stages are captured.

---

# US-PLT-21: Deploy Stage 2 Compose stack to the baseline VM for comparison

**Story:** As the project team, I want the Stage 2 Docker Compose stack
deployed to `vm-baseline-app` — the same VM used for the Stage 1 baseline —
after Stage 1 baseline evidence is captured there, so that the Stage
1-vs-Stage 2 comparison measures the orchestration-model difference on
identical hardware, not confounded by different host specs.

**Traces to:** PMP 10.1, 17.4. Depends on US-PLT-20 (done) and US-PLT-22
(done — Stage 1 evidence archived, safe to proceed).
**Points:** 3 — Compose stack itself already proven (Period 2, local Docker
Desktop); remaining work is VM-specific configuration only.

## Design decisions (stated here so they can be corrected before I build the
runbook around them — flag if any of these are wrong)

1. **Single-VM, self-contained topology — `vm-baseline-db` is NOT reused.**
   Checked `deploy/docker/docker-compose.yml`: it already brings its own
   `postgres`/`redis` containers with a fresh named volume and its own
   `init-db-roles.sh` bootstrap (ADR-005 per-service roles) — fully
   self-contained, exactly as tested in Period 2. PMP 10.1 itself names only
   `vm-baseline-app` as host for "Stage 2 Docker Compose microservices."
   Re-plumbing the compose file to point at an external Postgres on
   `vm-baseline-db` would be new, unproven work for no stated benefit —
   `vm-baseline-db` simply goes unused once Stage 2 deploys, which is fine.
2. **Registry pull, not a local rebuild.** Confirmed live against
   `registry-monitoring` (172.16.200.23:5000, reachable): five backend
   services are at `0.1.1-a08a02d`, `frontend` at `0.0.0-1c39d25` (the
   Trivy-remediated OpenSSL fix from US-PLT-23). Pull + retag locally to
   the exact tags the compose file expects, so `docker compose up` (no
   `--build`) uses the already-present images rather than rebuilding from
   source — matches the story's own "registry access from the VM" scope.
3. **Fixed a real pre-existing bug before using it:** `docker-compose.yml`
   reused one shared `${IMAGE_TAG}` across all six services, but frontend's
   tag numbering (`0.0.x`) is genuinely independent of the backend five's
   (`0.1.x`) — the identical single-shared-tag mistake already caught once
   in Kubernetes (US-PLT-13/24, see `MEMORY.md`). Fixed with a separate
   `${FRONTEND_IMAGE_TAG}` variable rather than a local re-tag workaround
   (CLAUDE.md: find root causes, no temporary fixes).
4. **Docker install on `vm-baseline-app` is new baseline work** — nothing
   there today but Python 3.12/venv/Nginx (US-PLT-20). This is the
   asymmetry already flagged in US-PLT-22's deployment-time writeup.
5. **Stop, don't delete, Stage 1.** `bookstore-monolith` (systemd) and the
   host Nginx both need to stop — Compose's `frontend` container claims host
   port 80 too. Stop/disable only; leave the venv/build/systemd unit intact
   so Stage 1 can be started again later for the live demo (per
   `sprint-plan.md`'s "Final demo storyline" — Stage 1 has to come back for
   the exam, and a `switch-to-stage1.sh`/`switch-to-stage2.sh` pair is
   already flagged there as a near-term follow-up once this story lands).
6. **Fresh secrets for Stage 2**, not reused from Stage 1 — different
   deployment, independent security domain, same practice as every prior
   VM story.
7. **Docker's `insecure-registries` trust config** needed in
   `/etc/docker/daemon.json` before `docker pull` from a non-TLS registry
   works — the Docker-daemon equivalent of the containerd `certs.d` trust
   config already done for the k8s nodes in US-PLT-23.

## Plan

### Compose file (agent writes/fixes)
- [x] `deploy/docker/docker-compose.yml` — `FRONTEND_IMAGE_TAG` fix (done
      above, before anything else touches this file).

### Runbook (agent writes, user executes against the real VM)
- [x] `deploy/baseline-vm/US-PLT-21-runbook.md` written (Parts A-G below):
  - Part A: stop Stage 1 (`systemctl stop bookstore-monolith`, stop Nginx),
    confirm port 80 free.
  - Part B: install Docker + Compose plugin on `vm-baseline-app`; configure
    `insecure-registries` for `172.16.200.23:5000`.
  - Part C: copy `deploy/docker/` to the VM; write a fresh `.env` (new
    generated secrets, `IMAGE_TAG=0.1.1-a08a02d`,
    `FRONTEND_IMAGE_TAG=0.0.0-1c39d25`).
  - Part D: pull all six images from the registry, retag locally to match
    what compose expects, confirm no `build:` gets triggered.
  - Part E: `docker compose up -d`, confirm all migration/seed jobs exit 0
    and all services reach healthy.
  - Part F: full customer-journey walkthrough (register → browse → cart →
    checkout → order history) against `http://172.16.200.24/` — AC#1.
  - Part G: record versions (image digests, commit hash) for the fairness
    control (PMP 17.4) — AC#2.

### Evidence + writeup
- [ ] Screenshot/confirm the full journey; save under
      `evidence/baseline-comparison/` alongside US-PLT-22's Stage 1 evidence.
- [ ] Update `documents/backlog/sprint-plan.md` (Period 5 table) and
      project `MEMORY.md`.
- [ ] Flag (not yet build, unless asked) the `switch-to-stage1.sh`/
      `switch-to-stage2.sh` follow-up now that Stage 2 is real on this VM.

## Execution log

- Part D blocked initially: `student` wasn't in the `docker` group (same
  class of finding already logged from US-PLT-18) — fixed with
  `usermod -aG docker student` + a fresh session, added to the runbook's
  Part B for next time rather than patching each command with `sudo`.
- Part E: all migrate-*/seed-* jobs exited 0, all app services healthy
  except `frontend`, which showed `Up ... (unhealthy)` despite
  `docker logs` showing the full customer journey already working for
  real (register/login/cart/checkout/order-history, real 200/201s).
  Diagnosed live rather than assumed cosmetic: `ss -tln` inside the
  container showed nginx listening only on `0.0.0.0:8080` (no IPv6), and
  the Dockerfile's `HEALTHCHECK` used unqualified `http://localhost:8080/`
  - this image's Alpine resolver resolves `localhost` to `::1` first,
    which nginx never listens on. Confirmed with a forced-IPv4
  `wget http://127.0.0.1:8080/` succeeding instantly (exit 0) where
  `localhost` failed every time (`FailingStreak: 76` — a real, persistent
  failure, not a startup-timing fluke). Pre-existing since Period 2, never
  caught before because nothing in Compose `depends_on: frontend`'s
  health, so it never actually blocked anything.
  **Fixed, Stage 2 only** (user's explicit choice, confirmed via
  AskUserQuestion): Kubernetes' `httpGet` probes bypass this path entirely
  (kubelet hits the pod IP directly, not through the container's own
  `wget`), so Stage 3 was never affected and wasn't touched — redeploying
  there would have meant risk to an already-working system for a bug it
  never had. User committed the one-line Dockerfile fix
  (`localhost`→`127.0.0.1`, commit `57a1e9e`) before rebuilding, so the
  image's commit-hash tag stays honest (`build-scan-push.sh` tags by
  current `git rev-parse HEAD`, not by working-tree state). Rebuilt/
  Trivy-scanned/pushed `bookstore/frontend:0.0.0-57a1e9e`, pulled/retagged
  on the VM, `FRONTEND_IMAGE_TAG` updated, `docker compose up -d frontend`
  — confirmed `Up ... (healthy)`, all 8 services healthy.

## Review

**Done and verified — US-PLT-21 complete, Period 5 at 6/11 points.**

Full customer journey (register → browse → cart → checkout → order history)
confirmed working against the VM-hosted Compose stack via real nginx access
logs (200/201s throughout) — AC#1 met. Both stages now measured on
identical hardware (`vm-baseline-app`, 2 vCPU/4 GB) — AC#2 met.
`vm-baseline-db` was never touched (Stage 2 is fully self-contained, its own
Postgres/Redis containers, per PMP 10.1's own stated plan). Versions
recorded: five backend services at `0.1.1-a08a02d`, frontend at
`0.0.0-57a1e9e` (post-fix), full digests in the runbook's Part G.

One real pre-existing bug found and fixed along the way (frontend
HEALTHCHECK's `localhost`→IPv6 resolution issue, see execution log above and
`MEMORY.md`) — Stage 2 only, Kubernetes was never affected and wasn't
touched, confirmed with the user before proceeding. One proactive fix made
before deployment: `docker-compose.yml`'s shared `${IMAGE_TAG}` across all
six services was split into a separate `${FRONTEND_IMAGE_TAG}`, avoiding a
repeat of the identical single-shared-tag bug already caught once in the
Kubernetes deployment (US-PLT-13/24).

`documents/backlog/sprint-plan.md` and `MEMORY.md` updated. Next in Period
5: US-PLT-16 (self-healing validation) and US-PLT-17 (rolling
update/rollback), both Kubernetes-side. The `switch-to-stage1.sh`/
`switch-to-stage2.sh` pair flagged in the "Final demo storyline" is now
buildable (Stage 2 is real on this VM) but not yet started — worth raising
before Period 5 wraps up.
