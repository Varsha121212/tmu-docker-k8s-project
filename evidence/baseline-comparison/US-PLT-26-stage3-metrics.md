# US-PLT-26: Stage 3 baseline comparison metrics

**Captured:** 28 Jul 2026, against the kubeadm cluster via Ingress
(`http://172.16.200.20:30080`). Deployed version: `identity` at
`0.1.1-af12e77` (post-fix, see below); all other services at
`0.1.1-a08a02d`/`0.0.0-57a1e9e` (unchanged since US-PLT-21).

## Read this before the numbers below: P2's data reflects a mid-flight fix, not a single stable measurement

**P2 required two real infrastructure/code fixes before it could complete
at all.** The first P2 attempt (`p2-run1` in the original run) crashed
completely — see the "Major finding" section below. What's reported in the
P1/P2/P3 table is **post-fix** data, all 3 repeats run after both fixes
were applied and verified stable. The pre-fix crash data is preserved
separately under `evidence/baseline-comparison/stage3-p1-p3/Ignore-p2-run-crash/`
for reference, not folded into the median/range numbers below.

## Deployment/setup time: not captured for this exercise

Unlike Stage 1/2, no re-timed redeploy was performed for Stage 3 — the
cluster and application manifests have been live since Period 4 (US-PLT-13,
24 Jul), and a comparable number would require a genuinely disruptive full
teardown/redeploy of the application layer, which wasn't undertaken here.
This stays an open gap rather than a fabricated number.

## P1 / P2 / P3 results (median of 3 runs, range in parentheses) — all three stages

| Scenario | Metric | Stage 1 | Stage 2 | Stage 3 |
|---|---|---|---|---|
| P1 (5 VU, catalogue) | RPS | 4.84 | 4.21 | 4.82 (4.81–4.83) |
| | Avg latency | 31.09 ms | 182.22 ms | 35.76 ms (33.35–36.49) |
| | p95 latency | 47.25 ms | 978.40 ms | 57.60 ms (46.64–58.62) |
| | Error rate | 0% | 0% | 0% |
| P2 (10 VU, mixed) | RPS | 12.43 | 8.31 | **2.23** (2.22–2.24) |
| | Avg latency | 401.58 ms | 793.61 ms | **3914.67 ms** (3894.49–3939.50) |
| | Median latency | — | — | 520.02 ms |
| | p95 latency | 1232.04 ms | 2129.14 ms | **11062.13 ms** (11033.16–11079.21) |
| | Max latency | — | — | up to 15827.77 ms |
| | Error rate | 0% | 0% | 0% |
| P3 (25 VU, catalogue-heavy) | RPS | 24.06 | 24.15 | 24.03 (23.98–24.04) |
| | Avg latency | 36.50 ms | 32.50 ms | 38.13 ms (37.41–40.00) |
| | p95 latency | 56.38 ms | 55.50 ms | 76.13 ms (68.99–84.14) |
| | Error rate | 0% | 0% | 0% |

Raw per-run numbers: `evidence/baseline-comparison/stage3-p1-p3/{p1,p2,p3}-run/*.json`.

**P1 and P3 both track Stage 1/2 closely** — Stage 3 doesn't show Stage 2's
P1 outlier-tax problem at all, and P3's numbers sit in the same ballpark as
both other stages despite the very different resource topology.

## Major finding: Identity's resource limits were undersized for its own security requirement, in two separate ways

### Part 1 — OOMKilled crash-loop (found, root-caused, fixed)

The first Stage 3 P2 attempt failed completely: **0% of 2543-2718 login
requests succeeded** across repeated attempts, despite registration working
fine. `kubectl describe pod` confirmed `Reason: OOMKilled, Exit Code: 137`,
with `Warning BackOff (x17-18 over 16 minutes)` — a sustained crash-loop for
the entire test window, not an intermittent blip.

Root-caused against the real code, not guessed: `apps/services/identity/app/core/security.py`
called `PasswordHasher()` with no explicit parameters, so argon2-cffi's
default `memory_cost=65536` KiB (**64 MiB per hash operation**) applied.
Identity's login handler is a synchronous FastAPI `def`, which runs in a
background thread pool with **no concurrency cap** — so memory need scaled
with however many logins happened to land concurrently, not a fixed number.
Even after doubling the container's memory limit (256Mi→512Mi) as a first
attempt, the pod **still** OOMKilled under the same 10-VU load — proving the
real problem wasn't insufficient headroom, it was unbounded concurrency.

**Fix:** a `threading.Semaphore(4)` added around both `hash_password()` and
`verify_password()`, capping concurrent Argon2 operations cluster-wide per
pod at 4 (worst-case ~256 MiB of hashing memory, comfortably under the
512Mi limit). This is a shared-code change (Stage 2/3 both run the same
image per ADR-007) but was chosen deliberately over weakening Argon2's own
parameters, which would have traded away real security margin
(GPU/ASIC brute-force resistance) rather than fixing the actual bug
(unbounded concurrency). Verified via 11 passing unit tests plus a live
6-concurrent-request burst test before re-running the full load test.

### Part 2 — Even after the fix, P2 revealed Identity's CPU limit is also undersized

**This is the real, non-obvious result: fixing the crash didn't make P2
"normal" — it traded a total outage for severe queuing latency.** RPS
collapsed to **2.23** (a fifth of Stage 1's 12.43), and p95 latency reached
**11 seconds** (max 15.8s) — while error rate stayed genuinely 0%. Every
request eventually succeeded; it just took far longer.

`kubectl top pods -n bookstore` during a P2 run showed `identity` at
**301m CPU** — sitting right at (and marginally over) its **300m CPU
limit** — while `kubectl top nodes` showed the actual cluster nodes at only
**8-22% utilized** (`vm-worker-2`: 449m/22%, `vm-worker-1`: 252m/12%,
`vm-master`: 169m/8%). This is a textbook illustration of a per-pod
resource-limit bottleneck coexisting with abundant overall cluster
capacity: the 4 concurrently-permitted Argon2 hashes (each deliberately
CPU-expensive) are fighting over just 0.3 of a CPU core, while the cluster
as a whole has multiple idle cores sitting right next to it.

**This directly validates re-examining Identity's single-replica
configuration** (SDD 10.2) — a question already raised separately and
intentionally not acted on yet (see `MEMORY.md`/`tasks/todo.md` for that
discussion) — this data is now concrete evidence for that case, not just a
hypothesis: more replicas would let concurrent logins queue against
separate 4-slot semaphores instead of one, and would use the cluster's
already-idle CPU that a single 300m-limited pod can't reach on its own.

## P3: Catalog HPA genuinely scaled during this run — recorded, not suppressed

Confirmed via the Grafana "Scalability (HPA correlation)" panel and
`kubectl get hpa catalog-hpa -n bookstore -w`: Catalog scaled from 1 to 3
replicas during P3 testing, CPU utilization vs the 65% target oscillating
between roughly 10-50% as load ramped and eased across repeats. This is
genuine Stage 3-specific elasticity that Stage 1/2 structurally cannot
show — and despite the very different starting resource footprint (Catalog
requests only 100m CPU per pod vs. Stage 1/2's whole-VM budget), P3's
end-to-end latency still landed close to both other stages (76ms p95 vs.
56ms/55ms) — the HPA did its job.

## Resources

| Scenario | Identity CPU/Mem (sample) | Cluster node utilization | Notes |
|---|---|---|---|
| P1 | idle-level, not sampled directly | low | Catalog/Identity both near-idle |
| P2 | **301m CPU (at 300m limit) / 307Mi mem** | 8-22% across all 3 nodes | CPU-limit-bound, not cluster-capacity-bound |
| P3 | low (Identity not exercised) | moderate, Catalog scaled 1→3 | HPA absorbed the load |

Disk usage stayed flat (5-20% range) and network throughput peaked around
50-100 KB/s across VMs/nodes during testing — neither was a bottleneck at
this scale.

## Applicable to Stage 3 (unlike Stage 1/2 — recorded, not N/A here)

- **Replica count**: Catalog 1→3 during P3 (HPA); Identity fixed at 1
  throughout (SDD 10.2), the configuration whose limits this section's
  major finding is about.
- **Pod restarts**: Identity restarted 6 times during each of the two
  pre-fix crash-loop incidents (OOMKill); 0 restarts since the semaphore
  fix was deployed and verified.
- **Recovery time**: not exercised as a formal measurement in this story —
  that's US-PLT-16's own scope, not duplicated here.

## Evidence index

```
evidence/baseline-comparison/stage3-p1-p3/
  p1-run/  p1-run{1,2,3}.json, p1-run{1,2,3}-graph.png, p1-run{1,2,3}-vm-output.png
  p2-run/  p2-run{1,2,3}.json, p2-run{1,2,3}-graph.png, p2-run{1,2,3}-vm-output.png
  p3-run/  p3-run{1,2,3}.json, p3-run{1,2,3}-graph.png, p3-run{1,2,3}-vm-output.png
           p3-run3-graph-HPA.png (Catalog HPA scaling evidence)
  Ignore-p2-run-crash/  pre-fix OOMKill crash data, kept for reference only
```
