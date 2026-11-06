# develop_repair_hybrid 1.0.0: exploratory emergence measurement (2026-10-21)

**Mechanical verdict: PARTIAL. Every declared criterion passes except E2b (paired wins on stale-controller
items).**

This run is EXPLORATORY. It is not admission, not a P8 cycle, and not evidence of general superiority.

- **Declared before measuring.** The declaration (`DECLARATION.md`) and the code were committed at `c3156edb`,
  before any instance of seeds 4000-4639 was generated.
- **Run once.** `review.json` holds the review run: 640 items on core 3, 144 s.
- **Nothing tuned afterwards.** The genome was not changed after the review results were seen.
- **Every number below comes from `review.json` `summary`,** apart from the owner split, which is computed from its
  `items`.

## Arms, all 640 items

Error columns give false restoration claims, with the exact one-sided 95% Clopper-Pearson upper bound.

| Arm | Mean quality | False claims / 640 (upper 95%) | Median unit-actions |
|---|---|---|---|
| **hybrid** | **0.9835** | **0 (0.47%)** | 185 |
| local_only (`develop_repair` 1.1.2) | 0.9523 | 0 (0.47%) | 14,698 |
| central_only (replanner) | 0.7451 | 37 (7.5%) | 129 |
| naive_switch (heartbeat only; no audit, no probe) | 0.8683 | 37 (7.5%) | 153 |
| vouch_only (probe-filtered claims; no fallback) | 0.8304 | 0 (0.47%) | 795 |

Paired comparisons (hybrid wins-ties-losses, one-sided sign test):

| Hybrid vs | Record | p |
|---|---|---|
| local_only | 503-0-137 | 2.5e-50 |
| central_only | 145-369-126 | 0.14 |
| naive_switch | 164-320-156 | 0.35 |
| vouch_only | 464-49-127 | 2.5e-46 |

Under the P8 loss convention (a wrong answer is +inf), central_only and naive_switch have infinite mean loss. The
hybrid, local_only and vouch_only do not.

## By controller condition

| Subregion | n | hybrid | local_only | central_only | naive_switch | vouch_only |
|---|---|---|---|---|---|---|
| reliable | 320 | 0.9996, 0 wrong | 0.9516 | 0.9996, 0 wrong | 0.9996 | 0.9976 |
| crashed | 157 | **0.9789**, 0 wrong | 0.9538 | 0.4609, 0 wrong | 0.9631 | 0.4609 |
| stale | 163 | 0.9561, 0 wrong | 0.9525, 0 wrong | 0.5193, **37 wrong** | 0.5193, **37 wrong** | 0.8581, 0 wrong |

Each cell is mean quality.

| Subregion | Hybrid vs central_only | Hybrid vs local_only | Hybrid vs naive_switch |
|---|---|---|---|
| reliable | 0-320-0 (identical) | 320-0-0 | 0-320-0 |
| crashed | 108-49-0 | 151-0-6 | 127-0-30 |
| stale | **37-0-126** | **32-0-131** | 37-0-126 |

## Criteria (declared at `c3156edb`)

| Id | Result | Evidence |
|---|---|---|
| E1 reliable: losses to central at most 1%, 0 false claims | **pass** | 0-320-0; the audit never fired on a reliable item (0 of 320); outputs and action counts are identical |
| E2a stale: higher mean quality than central; hybrid 0 and central > 0 false claims | **pass** | 0.9561 vs 0.5193; 0 vs 37 |
| E2b stale: more paired wins than losses against central | **FAIL** | 37-126 |
| E3 all items: 0 false claims and fewer than central | **pass** | 0 vs 37 |
| E4 reliable: actions no more than central's and fewer than local's on every item | **pass** | equal to central's on all 320; median 138 against local's 14,610 |
| A1 naive_switch makes false claims on stale items | **pass** | 37 |
| A2 vouch_only makes 0 false claims and has lower stale mean quality than the hybrid | **pass** | 0; 0.8581 vs 0.9561 |
| E5 (reported only) beats local on paired items and central on mean quality | pass | 503-137; 0.9835 vs 0.7451 |

## What the interaction gives that neither component does

- **No component, and no partial recombination, matches the hybrid's full profile.** The hybrid has the highest
  mean quality of the five arms and makes zero false claims. Its message bill is the planner's wherever the
  controller is fresh.
  - The replanner alone makes 37 false claims and collapses under crashes (0.46).
  - The local rules alone pay about 100 times the messages and lose every reliable item.
- **The two ablations show where the gain comes from.**
  - **The audit removes the false claims.** naive_switch, which falls back on the heartbeat alone, keeps all 37
    stale false claims.
  - **The fallback restores the lost function.** vouch_only, which vouches without falling back, has no false
    claims but loses the function the stale or crashed planner dropped: 0.86 on stale items and 0.46 on crashed
    items, against the hybrid's 0.96 and 0.98.
  - **The audit also avoids needless fallback.** On crashed controllers it beats naive_switch 127-30. When every
    failure precedes the crash, the plan audits clean, so the local protocol is never woken.

## Where it fails (kept as evidence; not tuned)

- **Stale controllers that catch up before the budget ends: 126 of 163 stale items.**
  - **Why it happens.** Every stale controller leaves the original route blocked at step 0, so the audit fires at
    step 0 on all 163 stale items. The standby then runs to the end of the budget.
  - **Where the planner catches up (126 items).** Its final field audits clean, and the hybrid uses that exact
    field. It has still paid the local protocol's bill, so it loses 0-126 to central_only.
  - **Where the planner does not catch up (37 items).** The hybrid wins all 37, because central_only's claims are
    false there.
  - **Against local_only.** The same bill, plus planner telemetry, the activation flood and the probes, makes the
    hybrid lose 32-131 to local_only on stale items, although its mean quality there is higher (0.9561 against
    0.9525).
- **This was predicted in the declaration (section 4) and is a property of the design.**
  - A woken standby cannot go back to sleep. `repair_solve_with` and `_local_repair` run from step 0 and cannot be
    paused, so a resumable standby would be new simulation code.
  - The score reads only the final state, so it does not credit the hybrid for restoring function during the
    36-84 steps when the stale plan is broken. Whether that matters is a property of the score, not something
    this run measured.
- **The candidate next mechanism is a standby that returns to dormancy once the plan audits clean again.** It would
  need a resumable local protocol, which is a substrate change. It is not built here and needs its own
  declaration.
- **Crashed controllers: the hybrid loses 6 of 157 items to local_only** and has 0 false claims there.

## Limits

- **Every item is simulated** (`develop_repair`'s TARGET_FORM_001 generator); see `greg/cognition/worlds.py`.
- **The probe is a simulated retransmission model.**
- **The verifier's accounting replay reuses the composition primitives.** The outcome checks (pointers on the
  realized topology, every claim followed to a sink) are independent of the solver's state.
- **Seeds 4000-4639 are now spent for `repair_instance` as exploratory review data.** They must not serve as held-out
  data for this generator.
- **Admission is separate.** It is drafted in `../greg-genome-admission/2026-10-21-v6-draft-repair.md` and is not
  frozen.
