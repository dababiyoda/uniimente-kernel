# Genome admission v10: pre-registration (2026-11-05)

**Status:** pre-registered. This file is committed before `freeze.json`, and both are committed before any held-out
instance is generated. The run refuses to report if any frozen input differs.

v10 builds the three directive-named families that the coverage record
(`docs/collaboration/MIND-COVERAGE-2026-10-21.md`, section 31 item 1) still listed with no executor after v9:
**active inference, global workspace and ecology bidding**. Three lanes built them in parallel from the integration
head `d35d92a5` (branches `claude/v10-lane-A`, `-B`, `-C`, kept unchanged as lineage). The lead merged them on
`claude/v10-meta-wave` and edited `greg/cognition/reserved.py` and its drift test to name the new executors. All
development used seeds 0-9 only. Seed claim: board #96, issuecomment-6648588568.

## What is fixed before the run

| Item | Value |
|---|---|
| Run id | `2026-11-05-v10` |
| Held-out seeds | 1900-1929 (`--heldout-start 1900`) |
| Families | the three below, all new at 1.0.0 |
| Rule | `RULE` verbatim, unchanged since v2; `decide()`, `COST_RATIO` 1.25 and `ALPHA` 0.05 unchanged |
| Smoke | one canonical-path smoke per family on its first held-out seed; a failure blocks DEFAULT |
| Code | the harness's import closure and all of `greg/cognition`, at the commit that adds `freeze.json`, hashed in it |
| Run | once, in a clean detached worktree at the freeze commit, pinned to one core. A crash is recorded, never retried |
| Machine | starts only when the 1-minute load is below 1.5; start and end load recorded |

**Why 1900-1929 are fresh:** no genome-admission freeze, #179 freeze, antifragility run or P8 split uses them (the
516 exposure records at `d35d92a5` contain no overlapping seed or range; confirmed independently by the integration
owner). They are not P8-reserved (7000-9199) and not a declared development range. The harness's spent-seed and
reused-instance checks run again at freeze time.

## Families (3)

| Family | Layer | Coverage item closed if executed | Baseline | Competitor | Dev result (seeds 0-9, not part of the rule) |
|---|---|---|---|---|---|
| `meta_active_inference` | 5 | active inference | cheapest-first fixed test order to a threshold | horizon-2 Bayesian decision theory on pure expected loss (the candidate without its information-gain term) | vs baseline 10-0-0; vs competitor 0-8-2; would be SUPERSEDED |
| `meta_global_workspace` | 5 | global workspace (partial: within one problem) | independent specialists, no communication | sequential token-ring sharing of the same decisions on the same bus | vs baseline 10-0-0; vs competitor 1-3-6; would be DEFAULT (latency 1.23x, at the 1.25x limit) |
| `collective_ecology_bidding` | 2 | ecology bidding | whole budget to the best warm-up species, split evenly | certainty-equivalent allocator (the same planner fed posterior means) | vs baseline 8-2-0 (p 0.055); vs competitor 4-6-0; would be EXPERIMENTAL |

Every benchmark is synthetic: exact-DP fault diagnosis (mathematical), spin glasses split among specialists with
exhaustive truth (mathematical), and a declared simulated world with hidden per-context success rates (simulated).

## Disclosures (part of this pre-registration)

**Changes made after a development result was seen:**
- **Lane B (global workspace):** the docstring declared, before any arm ran, a rule picking the competitor as the
  best of three bandwidth-matched schemes (prioritised min-sum BP, round-robin BP, snapshot round-robin blackboard).
  It picked prioritised BP (mean -2.251). The lane then added a fourth scheme, the sequential token ring (-0.089), and
  made it the competitor. This makes the comparison harder for the candidate. A finding was also recorded without
  changing the candidate: on a 4000-bit, 50-round bus the synchronous workspace oscillates on 8 of 10 dev instances.
- **Lane C (ecology bidding):** the declared competitor was contextual Thompson sampling, which scored 0.735 and lost
  3-7 to the candidate. A same-seed diagnostic of three allocators sharing the planner (certainty equivalent 0.797,
  UCB-style optimism 0.789, Thompson 0.735) led the lane to switch to certainty equivalence, the strongest. This makes
  the comparison harder for the candidate. Thompson sampling is kept as `ecology_thompson`.
- **Lane A (active inference):** no change. The competitor was chosen by a rule declared before any run (lowest dev
  regret among three Bayesian policies, measured on the competitors alone).

No generator, candidate parameter, baseline or score was changed after any development result in any lane.

**Competitors that are ablations of the candidate:** lanes A and C compare the candidate with itself minus the
mechanism under test (the epistemic term; the reputation-kept optimism). A positive verdict therefore means the
mechanism adds value over the same planner, not that it beats a structurally different method.

**Scope:** the global workspace arbitrates among the block specialists of one problem, not among GREG's
intelligences on a mixed suite; the reserved record keeps the latter open.

## What the outcome changes, and what it cannot

- **DEFAULT or NICHE** makes a genome routable at 1.0.0. It attaches nothing; attaching is the founder's decision.
- **SUPERSEDED, EXPERIMENTAL or REJECTED** excludes a genome from routing and is reported as prominently.
- **No retry and no redesign under this run id.** A losing candidate is not changed and re-run here.
- **Synthetic only:** no verdict says anything about a natural workload.
