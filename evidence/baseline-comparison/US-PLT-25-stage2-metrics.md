# US-PLT-25: Stage 2 baseline comparison metrics

**Captured:** 28 Jul 2026, against `vm-baseline-app` (172.16.200.24), Stage 2
Compose stack (US-PLT-21). Deployed version: five backend services at
`0.1.1-a08a02d`, frontend at `0.0.0-57a1e9e`.

**Identity redeployed 31 Jul 2026:** Identity was subsequently updated to
`0.1.1-af12e77` — the same OOMKill/semaphore-fixed image Stage 3 runs
(`docker-compose.yml`'s new `IDENTITY_IMAGE_TAG` variable, one service
recreated, nothing else on the stack touched or reseeded). P2 was re-run 3x
against the patched image
(`evidence/baseline-comparison/stage2-p1-p3/p2-run-identity-postfix/`) and
came out statistically indistinguishable from the figures below (RPS 8.25
vs. 8.31, avg latency 806.93ms vs. 793.61ms, p95 2150.19ms vs. 2129.14ms,
0% errors both times) — Compose has no per-container CPU limit, so the
semaphore never bound anything beyond the same 2 vCPU ceiling that was
already saturated pre-fix. The P1/P2/P3 table below is therefore retained
as-is; **Identity's currently-deployed version is `0.1.1-af12e77`**, closing
the version asymmetry against Stage 3 flagged in `US-PLT-27`.

## Deployment/setup time

**42 seconds** (`docker compose down` → timed `up` → all 8 containers
healthy). **Not directly comparable to Stage 1's 4 min 30 sec** — different
scope, not a like-for-like number: Stage 1's figure was a full app-layer
redeploy (rebuild venv, transfer code, rebuild frontend from source). This
Stage 2 figure started from images **already pulled and cached locally**
(from US-PLT-21), so it only measures container orchestration/startup —
closer to "restart" than "fresh deploy." A genuinely comparable number would
need to also time the image pull from a cold cache, which wasn't captured
separately here.

## Read this before the numbers below: a real hardware-topology confound, not just orchestration

**Stage 1 and Stage 2 are not running on equivalent total hardware, and
that has to be accounted for before attributing any latency/CPU difference
to "orchestration overhead" or "decomposition cost."**

- **Stage 1**: the monolith ran alone on `vm-baseline-app` (2 vCPU/4 GB).
  Postgres and Redis ran on a **separate, dedicated** `vm-baseline-db` (its
  own 2 vCPU/4 GB). Combined app+data footprint: **4 vCPU/8 GB across two
  VMs**.
- **Stage 2**: fully self-contained on `vm-baseline-app` alone — Postgres,
  Redis, and all 5 services now share **one 2 vCPU/4 GB VM total**.
  `vm-baseline-db` sits unused (by design, per PMP 10.1 — see US-PLT-21's
  own notes on why this topology was chosen).

So Stage 2 is doing strictly more work (data tier + 5 app processes +
frontend) on **half the aggregate compute** Stage 1's combined footprint
had. Any finding below that shows Stage 2 using more CPU or serving slower
is genuinely informative about what decomposition costs *when squeezed onto
the same single-VM budget the PMP's resource plan assigns it* — which is a
real, legitimate thing to report — but it is not a clean isolation of "the
orchestration model" from "the hardware budget." Both readings are valid
depending on which question is being asked (PMP 17.1's own Q6 asks exactly
this: "which differences are caused by platform, and which are influenced
by the architecture change" — this adds a third axis, hardware topology,
that the PMP's six questions don't explicitly separate out).

## Fairness controls applied (PMP 17.4)

Same as Stage 1: same load-generator (laptop), same script
(`tests/load/baseline-p1-p3.js`), same request mix/duration per scenario,
3 repeats each. Catalog reseeded fresh during US-PLT-21 (16 books,
content-equivalent to Stage 1's — not the literal same row IDs, same
accepted compromise as Stage 1's own dataset note).

## P1 / P2 / P3 results (median of 3 runs, range in parentheses) — vs Stage 1

| Scenario | Metric | Stage 1 | Stage 2 |
|---|---|---|---|
| P1 (5 VU, catalogue) | RPS | 4.84 | 4.21 (4.13–4.34) |
| | Avg latency | 31.09 ms | **182.22 ms** (148.19–204.37) |
| | p95 latency | 47.25 ms | **978.40 ms** (917.11–1151.56) |
| | Error rate | 0% | 0% |
| P2 (10 VU, mixed) | RPS | 12.43 | 8.31 (7.82–8.35) |
| | Avg latency | 401.58 ms | **793.61 ms** (792.87–874.02) |
| | p95 latency | 1232.04 ms | **2129.14 ms** (2021.34–2321.88) |
| | Error rate | 0% | 0% |
| P3 (25 VU, catalogue-heavy) | RPS | 24.06 | 24.15 (24.12–24.18) |
| | Avg latency | 36.50 ms | 32.50 ms (30.96–33.86) |
| | p95 latency | 56.38 ms | 55.50 ms (52.67–67.91) |
| | Error rate | 0% | 0% |

Raw per-run numbers: `evidence/baseline-comparison/stage2-p1-p3/{p1,p2,p3}-run/*.json`.

## Resources (representative sample, one run per scenario)

| Scenario | VM CPU (user+sys) | VM memory used | Notes |
|---|---|---|---|
| P1 | ~12% (4.0% us / 8.0% sy), 88% idle | ~47.5% (1.86/3.92 GiB) | CPU not saturated — see the unresolved latency question below |
| P2 | **~100% (81.5% us / 18.5% sy), 0% idle** | ~57.7% (2.26/3.92 GiB) | Same full-saturation pattern as Stage 1's P2 |
| P3 | ~30% (21.7% us / 8.7% sy), 69.6% idle | similar to P1 | ~3.5x Stage 1's P3 CPU (8.6%) for the *same* workload |

## Findings

**1. The Argon2 CPU-saturation finding from Stage 1 replicates in Stage 2,
exactly as predicted before this run.** P2 drives this VM to full CPU
saturation (0% idle) just like Stage 1 did — confirming the earlier
hypothesis that the same total CPU budget + same Argon2 code means the same
saturation symptom, container boundaries or not. `top` shows the load
spread across multiple separate processes this time (two `uvicorn`
processes plus a `python` worker, versus Stage 1's single process) —
consistent with Identity, Catalog (Cart's price-check call), and Cart all
under load concurrently, rather than one shared process.

**2. Idle/baseline memory is measurably higher in Stage 2 at every load
level** (~47.5% at P1 vs Stage 1's ~38%, ~57.7% at P2 vs Stage 1's ~49%) —
the predicted cost of running 5 separate service processes plus Postgres,
Redis, and a frontend container instead of one shared monolith process. This
is an architecture-driven cost (decomposition itself), not a platform one,
and it holds regardless of the hardware-topology confound above.

**3. P3's raw CPU cost is ~3.5x higher in Stage 2 than Stage 1 (30% vs
8.6%) for the *identical* catalogue-only workload** — real evidence of
container/networking overhead (extra hops: client → frontend nginx →
catalog container → Postgres container, vs Stage 1's single process with a
direct connection to a database on another VM). Despite that, **end-to-end
latency at P3 came out nearly identical to Stage 1** (32.50ms vs 36.50ms
avg) — there's still enough idle headroom at this load level that the extra
overhead doesn't show up in what the customer actually experiences.

**4. P1's average/p95 latency looked dramatically worse than Stage 1's at
first — the full distribution shows it's a small number of extreme
outliers, not a systemic slowdown.** The **median** request latency across
all 3 runs was 35-42ms — barely different from Stage 1's P1 *average* of
31ms. The average (148-204ms) and p95 (917-1152ms) are being pulled up by a
small number of very slow individual requests: each run's **max** reached
1.8-2.9 **seconds**. This was checked directly against the existing k6 JSON
data (`http_req_duration`'s full min/med/p90/p95/max breakdown) rather than
by running P1 again — the answer was already in the data collected.

This is consistent with **cold/low-concurrency connection setup**: at only
5 VUs generating ~4-5 req/s, each request crosses client → frontend nginx →
catalog container → Postgres container — real hops Stage 1 never had (a
single process with a long-lived connection to a database on another VM).
At this low a request rate, a connection pool has little reason to stay
warm between requests, so a subset of requests likely pay a real
connection-establishment cost that most others don't. This isn't fully
proven (would need per-request connection-reuse instrumentation to confirm
the exact mechanism), but the median-vs-average gap rules out "most
requests are slow" and narrows it to "a few requests are very slow" —
already a meaningfully more specific finding than the original open
question.

## Not applicable to Stage 2

Same as Stage 1: no orchestrator, so replica count / pod restarts / recovery
time don't apply. Docker's `restart: unless-stopped`-style behavior wasn't
exercised or measured here.

## Evidence index

```
evidence/baseline-comparison/stage2-p1-p3/
  p1-run/  p1-run{1,2,3}.json, p1-run{1,2,3}-graph.png, p1-run{1,2,3}-vm-output.png
  p2-run/  p2-run{1,2,3}.json, p2-run{1,2,3}-graph.png, p2-run{1,2,3}-vm-output.png
  p3-run/  p3-run{1,2,3}.json, p3-run{1,2,3}-graph.png, p3-run{1,2,3}-vm-output.png
```
