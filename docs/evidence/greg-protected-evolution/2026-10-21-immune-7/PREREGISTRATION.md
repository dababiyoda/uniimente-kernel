# P8 cycle 7 (second target, `immune_detect`): DRAFT pre-registration for the session owner (2026-10-21)

**Status: DRAFT. Do not freeze as written.**

- **The design pilot's declared rule judged this target NOT_VIABLE** (`pilot/README.md`): best mean simulated P(RETAIN) 0.216, against a declared threshold of 0.30.
- **Nothing has been frozen or run.** No cycle-7 instance has been generated, and seeds 8600-9199 were never drawn.
- **The split is registered but not current.** `IMMUNE_SPLITS["cycle-7"]` was checked by `immune_split_seeds`, which generates nothing. `IMMUNE_CURRENT_SPLIT` stays `cycle-2`.
- **Three rows are filled only from a freeze:** *Seals*, *Trusted code* and the freeze digest.
- **The design below is the strongest the pilot found, recorded so the decision is concrete.** The session owner chooses among the options in the last section.

## Why a second target

P8's exit condition is repeated held-out gains. Cycle 6 kept one proposal on `constraint_release`; repetition needs another target.

**`forecast_quantile` is not viable.**

- Its finite pool of 241 M4 weekly series has 0 unused series. Cycle 1's split used 201 of them; the development seeds and admission freezes used 120 (overlapping).
- Cycle 1's held-out split is spent.
- New data are blocked: the network policy refuses the sources tried for F8.

**`immune_detect` is the remaining declared target.**

## Hypothesis

On fresh Gaussian negative-selection instances, a configuration of `collective_immune` 1.0.2 found by the frozen search has lower loss than the incumbent `IMMUNE_DEFAULT_CONFIG` (`cfg-68b55c07dbdc`). The loss is -F1, and +inf for any false-alarm violation beyond the binomial 95% limit.

## Pilot results (review seeds 3100-3999; full detail in `pilot/README.md`)

- **The trigger fires on every review train set:** the incumbent is worse than the z-score baseline on 45.8-50.0% of items. The threshold is 25%.
- **Headroom exists.** Full whitening with a single detector scale beat the incumbent 295-165 and 300-157 on 540 fresh items, with 1 false-alarm violation against the incumbent's 3.
- **The frozen search selects alarm-heavy configurations.** Nine simulated cycles picked `alarm_fraction` 0.80-0.95. Their picks win paired items (up to 356-126) but make 4-6 violations per 540.
- **One violation anywhere in the held-out split forces REJECT.** It makes the held-out mean +inf. So P(RETAIN) is capped at about 0.26-0.41 at n 120 and about 0.07-0.17 at n 240.
- **The stress gate is disarmed on this target whenever the incumbent errs on a stress kind.** That happened in all six simulated train sets.

## What is fixed (if the owner proceeds as drafted)

| Item | Value |
|---|---|
| Target | `immune_detect`: `IMMUNE_DEFAULT_CONFIG` of `collective_immune` 1.0.2, pinned in `EVOLVABLE_CONFIG_PINS` |
| Closed space | `collective.IMMUNE_CONFIG_SPACE`, unchanged since cycle 2 |
| Method, score, stress sets, baseline, seal code | byte-identical to cycle 2's commit `ed4ee29` (`test_the_immune_cycle_code_is_unchanged_since_cycle_2`) |
| Split | `cycle-7` in `IMMUNE_SPLITS`: train 8600-8719 (120), held-out 8720-8839 (120). Disjoint from cycle 2, every constraint-release split and canary, every admission seed and every review seed. Inside `P8_RESERVED`, extended to 7000-9199 in `33bd4fd` |
| Settings | generations 5, population 8, search seed 20261021, `mutate-incumbent/1`. This was the pilot's declared choice: the highest P(RETAIN) at 0.05/7 (0.192, against 0.166 for `cover/1` with 120 train items). The pilot simulated with search seed 20261007; the cycle takes a fresh one, as cycle 6 did |
| Rule | `evolution.RULE`, unchanged, verbatim in `freeze.json` |
| Seals | train `TO FILL`, held-out `TO FILL` (from `freeze.json`) |
| Trusted code | `TO FILL`: number of files, schema `greg-protected-evolution-freeze/3`, freeze file sha256 |
| Run | once, in the clean room, at the commit that adds `freeze.json`, pinned to one CPU core |

**Required code change before freezing (one line):** `IMMUNE_CURRENT_SPLIT = "cycle-7"`.

The freeze and the cycle call `spec.split()`, which reads the current split. Make the change in a commit of its own. It is deliberately not made here.

## Multiple attempts

The frozen rule decides at alpha 0.05. The README will report the held-out p-value beside two thresholds; a RETAIN above either is reported as not surviving that correction:

| Threshold | Value | Basis |
|---|---|---|
| Programme-wide | 0.05/7 = 0.00714 | the seventh P8 cycle |
| On this target | 0.05/2 = 0.025 | the second pre-registered cycle on `immune_detect`, after cycle 2 |

## Prediction (from the pilot; not part of the rule)

- **The trigger fires.** The incumbent loses to z-score on about 46-50% of items.
- **P(RETAIN) is about 0.22 at 0.05**, about 0.20 at 0.025 and about 0.19 at 0.00714. These are means over three simulated cycles, ranging from 0.06 to 0.32.
- **The likeliest outcome is REJECT at the held-out gate,** because the candidate makes at least one false-alarm violation among 120 held-out items.

## What RETAIN would mean

- **A proposal, not a change.** RETAIN produces a `PROPOSED_NOT_APPLIED` change to `IMMUNE_DEFAULT_CONFIG`, with rollback to `cfg-68b55c07dbdc`.
- **A canary comes before adoption.** It is the `collective_immune` admission on fresh seeds with the proposed configuration.
- **Adoption is the founder's.** It is a reviewed change, and it must bump the genome version and its pin together.
- **It would count toward "repeated held-out gains"** at the proposal level.

## What REJECT would mean

- **The gate is named.** The record names the gate that rejected, and the cycle-7 held-out split is spent.
- **A REJECT at the held-out gate would not refute the headroom.** The pilot measured that headroom on 540 fresh items. It would mean that the frozen chain (train-mean selection inside this space, with infinite loss for any violation) cannot retain a gain on this target at this power.

## Options for the session owner (decide before any freeze)

1. **Do not run cycle 7 on `immune_detect` (the pilot's declared verdict).** Record the target as NOT_VIABLE under the frozen rule and look for a second target elsewhere.
   - A new target needs a declared evolvable configuration, fresh data and an admission pin.
   - Candidates are other admitted genomes with a closed configuration space and a cheap generator.
2. **Run as drafted.** Accept P(RETAIN) of about 0.2 and spend the split. This is honest but low-power.
3. **Change the target's search space before freezing.**
   - For example, narrow `alarm_fraction` to [0.4, 0.8]; the pilot's low-violation configurations used 0.75-0.79.
   - This uses knowledge from review seeds and changes the genome's declared space, so it needs a fresh declared pilot on unused review seeds before any freeze.
   - It touches no constitutional or evaluation state.
4. **Change the rule.** For example, compare violation counts and F1 separately instead of a mean that is +inf after one violation, and fix the stress gate's blindness when the incumbent is +inf.
   - `RULE` is shared by every target and frozen in every record.
   - Changing it is a reviewed, founder-level change with its own pre-registration. It is not a design choice for one cycle.

## Procedure (only if the owner chooses option 2 or a re-piloted option 3)

1. Commit `IMMUNE_CURRENT_SPLIT = "cycle-7"` and check that the tree is clean.
2. Write the freeze:

       PYTHONPATH=. taskset -c 1 python -m greg.cognition.evolution --target immune_detect \
         --write-freeze docs/evidence/greg-protected-evolution/2026-10-21-immune-7/freeze.json \
         --generations 5 --population 8 --seed 20261021 --search mutate-incumbent/1

3. Fill *Seals* and *Trusted code* from it, and commit both.
4. Run once:

       PYTHONPATH=. taskset -c 1 python -m greg.cognition.evolution --target immune_detect \
         --freeze docs/evidence/greg-protected-evolution/2026-10-21-immune-7/freeze.json \
         --out docs/evidence/greg-protected-evolution/2026-10-21-immune-7/cycle-immune-7.json
