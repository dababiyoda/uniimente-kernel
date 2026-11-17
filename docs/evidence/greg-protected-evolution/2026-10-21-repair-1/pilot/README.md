# repair-1 design pilot: results (step D, 2026-10-21)

**Mechanical verdict, under the rules declared in `../DESIGN.md` (committed at `3369d0c0`, before any repair instance of seeds 3000-3999 was generated): NOT_VIABLE.**

- **Why: the rule's trigger never fires.** The incumbent is worse than `repair_no_repair` on **0 of 120** train items on each of T1, T2 and T3. The declared threshold is 25%.
- **The best mean simulated P(RETAIN) at alpha 0.05 is therefore 0.000.** The declared threshold is 0.30.
- **The pilot completed within its limits:**

| Mode | Configuration evaluations | Wall-clock | Limit |
|---|---|---|---|
| region | 7,160 | 128 s | 20,000 evaluations / 3,600 s |
| simulate | 24,920 | 355 s | 80,000 evaluations / 10,800 s |

  Both ran on cores 2-3.
- **No draft pre-registration is written** (`DESIGN.md` section 9). No freeze was made and no cycle was run.

This pilot is design knowledge only. It is not evidence for any cycle and decides nothing about adoption.

Files: `region.json`, `simulate.json` and `summary.json`. `summary.json` holds `choose()`'s output and the labelled diagnostic table; every number below comes from these files.

## The trigger, and why it cannot fire against this baseline

| Train set | Rule: incumbent worse than no repair | Diagnostic (not the rule): incumbent worse than the replanner |
|---|---|---|
| T1 | 0.0% | 66.7% |
| T2 | 0.0% | 75.0% |
| T3 | 0.0% | 73.3% |

`repair_no_repair` keeps the pre-damage forwarding field and claims nothing. On the pool it restores no source on 344 of 640 items (loss 0, which `describe` counts as an abstention), and its mean loss is -0.074. The incumbent's is -0.953, and the incumbent beats it on **640 of 640** pool items.

The simple baseline never wins anywhere, so the rule finds no "recurring failure". The target's measured deficit is against the **replanner**, which the declaration (following the brief) keeps outside the rule. The development seeds 0-9 showed the same thing in step A, 10 of 10 wins for the incumbent, but that was not a stated design criterion before the declaration.

## Pool (640 fresh items, 3360-3999): the incumbent and its comparators

Error columns give false restoration claims out of 640, with the exact one-sided 95% Clopper-Pearson upper bound.

| Arm | Wrong / 640 (upper 95%) | Mean loss without wrong | vs incumbent (wins-losses) |
|---|---|---|---|
| incumbent (8, 2, 5, 3) | 0 (0.47%) | -0.953 | - |
| no repair (the rule's baseline) | 0 (0.47%) | -0.074 | 0-640 |
| **centralized replanner** (competitor) | **50 (9.78%)** | -0.838 | **467-173** |

**By controller subregion,** the incumbent against the replanner:

- **reliable controller: 0-320.** The replanner restores exactly with fewer messages.
- **unreliable controller: 173-147** (p = 0.081).

The replanner's 50 wrong answers all come from stale views (a recount by controller mode found 50 of 50 `stale`). Under the rule's loss, every one of them is +inf. Its mean loss is therefore +inf, although it wins most paired items.

## Simulated cycles (all six run; the trigger stage fails on all of them)

Every pick moves `wave_period` from 8 to 12: fewer waves mean fewer messages, so a lower action cost.

| Train | Procedure | Pick (wave, expiry, repeats, retract) | Train gain | Wrong on `late`: incumbent / pick | Gate | Pool vs incumbent | Pool wrong |
|---|---|---|---|---|---|---|---|
| T1 | `mutate-incumbent/1` | 12, 2, 5, 2 | 1.63% | 2 / **1** | **fail** (unverified claim) | 591-49 | 0 |
| T2 | `mutate-incumbent/1` | 12, 2, 5, 1 | 1.94% | 1 / 0 | pass | 592-48 | 0 |
| T3 | `mutate-incumbent/1` | 12, 2, 4, 3 | 1.34% | 2 / **4** | **fail** | 574-66 | 0 |
| T1 | `cover/1` | 12, 3, 5, 1 | 1.63% | 2 / 0 | pass | 592-48 | 0 |
| T2 | `cover/1` | 12, 2, 5, 2 | 1.77% | 1 / **1** | **fail** (unverified claim) | 591-49 | 0 |
| T3 | `cover/1` | 12, 2, 4, 3 | 1.34% | 2 / **4** | **fail** | 574-66 | 0 |

- **No arm makes a wrong answer on `lossy`** (+0.2 message loss).
- **The incumbent itself fails the gate's verification on `late`.** It makes 1-2 false restoration claims per 120 items.
- **A pick passes only if it makes zero false claims on `late`.** Two of the six do: (12, 2, 5, 1) on T2, and (12, 3, 5, 1) on T1. Both broadcast a retraction **once**.
- **Whether a pick passes depends on which train set it saw.** The same configuration that passes on one train set was never tested on the others' stress items in this record.
- **The picks also lose the replanner comparison:** 173-467 overall and 0-320 where the controller is reliable, the same counts as the incumbent. The protocol constants cut message cost; they do not change which arm restores a route first.

### Diagnostic only: the same cells with the trigger stage dropped

This table is not the verdict and was not a declared decision rule.

| Procedure | Mean P(RETAIN) at 0.05, n = 120 / 240 / 360 / 480 | At 0.05/7 |
|---|---|---|
| `mutate-incumbent/1` | 0.333 / 0.333 / 0.333 / 0.333 | 0.333 at every n |
| `cover/1` | 0.333 / 0.333 / 0.333 / 0.333 | 0.333 at every n |

For each procedure, one of three picks passes the gate. Once the gate is passed, every pick wins at least 574 of 640 pool items with zero wrong answers, so the resampled held-out step retains at every n.

The diagnostic mean is 0.333, which is above 0.30. That is a thin margin, and it rests on one run per procedure passing a gate decided by 0-2 false claims in 120 items.

### Fixed configurations informed by prior observations (comparators only; never candidates)

| Configuration | Wrong / 640 | vs incumbent | Gate T1 / T2 / T3 | Fixed-protocol P(RETAIN) |
|---|---|---|---|---|
| slow waves (12) | 0 | 582-58 | fail / fail / fail | 0 (the trigger aside: no gate pass) |
| short expiry (expiry 1) | 0 | 0-0, 640 ties | pass / fail / fail | 0 (no pool advantage) |
| slow waves, short expiry (12, 1) | 0 | 582-58 | fail / fail / fail | 0 |
| more repeats (8, 5) | 0 | 103-537 | fail / pass / fail | 0 (loses on the pool) |

On these pool items, a shorter expiry changes no answer. It removes the incumbent's false claims on T1's `late` items only.

## What the pilot established

1. **The rule's trigger cannot fire on this target with the genome's simple baseline.** The incumbent beats no repair on every one of 1,000 fresh items: 360 train and 640 pool. Under the unchanged rule, this target produces `NO_RECURRING_FAILURE` before any search. This is a structural property of the (target, baseline) pair, not a sampling accident.
2. **There is real headroom inside the declared space, and it is message cost.** `wave_period` 12 beats the incumbent on 574-592 of 640 fresh items with zero false claims on the pool. Its train gain, though, is small (1.3-1.9%), just above the rule's 1% gate.
3. **The adversarial `late` set decides everything once the trigger is set aside.**
   - The incumbent makes false restoration claims there: 5 of 360 across the three train sets, an exact upper 95% bound of 2.9% on the pooled rate.
   - A candidate passes only with zero. One-shot retraction (`retract_repeats` 1) is the common factor of both passing picks, and that is unexpected, so it is worth a mechanism check before anyone relies on it.
4. **The deficit the survey named (losing to the replanner) is not addressed by these constants.** Every pick ties the incumbent's 173-467 record against the replanner, and is 0-320 where the controller is reliable. Closing that gap needs a different mechanism, for example the hybrid the genome's notes name (a central plan with the local protocol as fallback). It is not a protocol-constant search.

## Error-rate statement

- **The incumbent, every pick and every informed configuration make zero false claims on the 640 pool items.** The upper 95% bound on each rate is 0.47%. Zero observed errors does not show zero risk.
- **On the `late` stress items the incumbent's rate is 1-2 of 120 per train set.** Under the rule, a RETAIN would require zero candidate false claims on the held-out split. Zero in n bounds the rate at 2.5% (n = 120) to 0.62% (n = 480).

## Mechanical verdict

From `summary.json`:

- `complete` is true;
- the trigger fired on 0 of 3 train sets;
- the best cell mean at 0.05 is 0.0, below 0.30.

**NOT_VIABLE.** There is no choice of held-out size or procedure, and no draft pre-registration is written.

## Reproduce

    D=docs/evidence/greg-protected-evolution/2026-10-21-repair-1/pilot
    PYTHONPATH=. taskset -c 2,3 python scripts/p8_repair1_pilot.py region --out $D/region.json
    PYTHONPATH=. taskset -c 2,3 python scripts/p8_repair1_pilot.py simulate --out $D/simulate.json
    PYTHONPATH=. python scripts/p8_repair1_pilot.py summarise --dir $D --out $D/summary.json

Outputs are deterministic: workers run whole items, and the resampling streams are seeded. The script refuses to overwrite an existing output.
