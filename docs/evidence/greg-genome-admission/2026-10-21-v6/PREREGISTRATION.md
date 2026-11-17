# Genome admission v6: pre-registration (2026-10-21)

**Status:** pre-registered. This file is committed before `freeze.json`, and both are committed before any held-out
instance is generated. The run refuses to report if any frozen input differs.

It promotes one lane draft, kept unchanged as lineage:
`docs/evidence/greg-genome-admission/2026-10-21-v6-draft-repair.md`. No other v6 draft exists on any local branch, so
there is one freeze over both families.

Freeze command, at the commit that contains this file:
`python -m greg.cognition.genomes.admission --freeze 2026-10-21-v6 --only develop_repair develop_repair_hybrid --heldout-start 1500`.
Run command, once, from a clean checkout of the freeze commit, under `taskset -c 1`:
`python -m greg.cognition.genomes.admission --run 2026-10-21-v6`.

## Fixed items

| Item | Value |
|---|---|
| Held-out seeds | 1500-1529 |
| Rule | `RULE` verbatim, unchanged; `decide()`, `COST_RATIO` 1.25 and `ALPHA` 0.05 are also unchanged |
| Code | the harness's import closure, all of `greg/cognition`, the extras and the dependency versions, hashed in `freeze.json` |
| Run | once, in a clean detached worktree, pinned to one core, on a quiet machine |

Checks behind seeds 1500-1529, made 2026-10-21 on branch `lane/repair-hybrid` (base `10e438d3`):

- **Ledger:** `scripts/data_exposure_ledger.py` `exposed()` returns no record for 1500-1529 under `develop_repair`
  or `greg.cognition.genomes.developmental:repair_instance`. No exposure record of any generator in the ledger,
  #158 or #179 lineage, touches 1500-1529.
- **Freezes:** no committed `docs/evidence/greg-genome-admission/*/freeze.json` uses them. Existing held-out seeds
  span 1000-1429.
- **Other branches:** no local branch carries a v6 draft or a `--heldout-start 15xx`.
- **Reserved ranges:** the seeds are outside `DEV_SEEDS` (0-9) and `P8_RESERVED` (7000-9199). They are also outside
  the review ranges this generator has spent: 3000-3999 (repair-1 pilot) and 4000-4639 (the hybrid's exploratory
  run).
- **The harness's own `spent_seeds` check** refuses spent seeds at freeze time and should be relied on.

## Families (2)

Both families draw from `repair_instance`. One freeze can therefore score both on identical held-out instances.

| Family | Version | Why it is in v6 | Baseline | Competitor |
|---|---|---|---|---|
| `develop_repair` | 1.1.2 | **Re-admission.** Its frozen verdict, NICHE_CAPABILITY in v1 and v2, was measured at 1.1.0 and 1.1.1 and is stale for 1.1.2 (P8 target step A: the constants became data; default outputs byte-identical on dev seeds 0-9) | no repair | central replanner |
| `develop_repair_hybrid` | 1.0.0 | **New** (`greg/cognition/genomes/developmental_hybrid.py`) | `develop_repair` 1.1.2 (local rules alone) | central replanner |

## Design knowledge, disclosed

This is everything known before the freeze. None of it is admission evidence.

- **`develop_repair` 1.1.2:**
  - The repair-1 pilot measured it on 1,000 review items (3000-3999): 0 false claims on the 640-item pool, and
    0-320 against the replanner where the controller is reliable.
  - Admission v2 (1.1.1) had 7-23 against the replanner.
- **`develop_repair_hybrid` 1.0.0:** the exploratory run (`docs/evidence/greg-repair-hybrid/2026-10-21-exploratory/`,
  seeds 4000-4639, declared at `c3156edb`):
  - **Against its baseline:** 503-137 against the local rules.
  - **Against its competitor:** 145-369-126 against the replanner (sign test p = 0.14), with 0 false claims
    against the replanner's 37.
  - **By subregion against the replanner:** 0-320-0 where the controller is reliable, 108-49-0 crashed and
    **37-126 stale**.
  - **Latency.** The hybrid replays the planner once per step, so its median latency is about 0.1 s against the
    replanner's about 0.001 s.
  - **What the rule implies.** It cannot reach DEFAULT on latency, so it needs a significant win over the
    replanner. At 30 items, about 15 of them unreliable, that is uncertain. NICHE_CAPABILITY or EXPERIMENTAL are
    plausible outcomes, and either is reported as prominently as a positive one.
- **Dev-only expectation (not part of the rule).** `admission --dev develop_repair_hybrid` on seeds 0-9 gives
  EXPERIMENTAL:
  - against the local rules: 8-2, p = 0.055;
  - against the replanner: 3 wins, 7 ties, 0 losses, p = 0.125;
  - median latency 0.115 s against 0.029 s (baseline) and 0.001 s (replanner);
  - wrong answers: 0 against the replanner's 2.
- **Two P8-loss caveats.**
  - `RULE` counts wrong answers per arm. The replanner's stale false claims count against it there, not as +inf.
  - On 30 held-out items roughly 7-8 are stale, so the replanner's expected wrong count is about 2. Zero is
    possible.
- **No parameter of either genome was changed after any review result was seen.**

## What the outcome changes, and what it cannot

- A DEFAULT or NICHE verdict makes a genome routable at its version. It does not attach it; attaching is the
  founder's decision (the hybrid's Genesis path is exercised in
  `tests/unit/test_genomes_developmental_hybrid.py`).
- SUPERSEDED, EXPERIMENTAL and REJECTED verdicts exclude a genome from routing.
- Every benchmark here is simulated. A positive verdict says nothing yet about a real network or controller.
