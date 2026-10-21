# P8 cycle 6: pre-registration (2026-10-21)

**Status:** written before `freeze.json`. No cycle-6 instance has been generated. The split was checked by
`cr_split_seeds`, which generates nothing, and both pilots used review seeds 3500-3999 only. The *Seals* and
*Trusted code* rows are filled from `freeze.json` in the commit that adds it, and the cycle runs once at that commit.
The directory name carries the date of the design's first commit (2026-10-16), not of the run.

## Hypothesis

Unchanged from cycle 5. On fresh instances of `develop_constraint_release`'s benchmark family, a configuration of
its search policy found by `cover/1` has lower loss than the incumbent `CR_DEFAULT_CONFIG` of version 1.2.0. The
cycle tests the whole chain: trigger, train gain, adversarial gate, one held-out look. A REJECT names the gate.

## What changed from cycle 5, and why

| Item | Cycle 5 | Cycle 6 | Basis |
|---|---|---|---|
| Train items | 60 (7600-7659) | **120** (7880-7999) | pilot 2's declared rule (`pilot/README.md`); weak evidence, disclosed below |
| Held-out items | 180 (7700-7879) | **240** (8060-8299) | pilot 1: 240 retains more often than 180 under every rule |
| Search seed | 20261016 | **20261021** | fresh |
| Selection | lowest train mean | **unchanged** | pilot 1: best of seven declared rules |
| Search policy, rule, gates, constants, stress sets | | **unchanged** | |
| P8 reserved seeds | 7000-8059 | 7000-8599 | 8060-8599 were used by nothing (`admission.P8_RESERVED`) |

No change reaches the candidate side, the sandbox, the evaluator, the seal code or the rule. `CR_SPLITS` gains
`cycle-6` and `CR_CURRENT_SPLIT` becomes `cycle-6`; earlier splits keep their names and seeds.

## Disclosures

- **The design hypothesis of this cycle was refuted before the freeze.** Cycle 5's REJECT was read as a selection
  failure. Pilot 1 tested seven selection rules and found none better than the unchanged one. A sign-test selection
  rule had been coded before the pilot ran. It is in git history and was reverted, and it is not frozen.
- **What cycle 6 changes is power, not the method.** The pilots say the outcome depends mostly on which train set is
  drawn (P(RETAIN) 0.23 to 0.87 across five review train sets). The only levers left inside the frozen rule are the
  split sizes.
- **Train size has no clear effect.** Pilot 2 favoured 120 by 0.018; cycle 5's pilot favoured 60 by 0.107. Both rest
  on 3 to 9 simulated cycles.
- **This is the fourth pre-registered cycle on this target**, after cycles 3, 4 and 5, all REJECTED.

## What is fixed

| Item | Value |
|---|---|
| Target | `constraint_release`: `CR_DEFAULT_CONFIG` of `develop_constraint_release` 1.2.0, pinned in `EVOLVABLE_CONFIG_PINS` |
| Closed space | `developmental.CR_CONFIG_SPACE`, unchanged since cycle 3 |
| Split | `cycle-6` in `CR_SPLITS`: train seeds 7880-7999 (120), held-out seeds 8060-8299 (240) |
| Settings | generations 5, population 8, search seed 20261021, `cover/1` with `lhs` 0. No selection key: the default, lowest train mean, ties by id |
| Rule | `evolution.RULE`, unchanged, verbatim in `freeze.json` |
| Seals | train `sha256:b8c00aed3043b6c86727af4f331eec1b98d78d51b3d138d107f4b2233fdeca26`, held-out `sha256:dd0176912db1d6002582abd0fef2f810166dd37e4121d8a5ed5cd8c55836bdbb` (from `freeze.json`) |
| Trusted code | the static import closure frozen by `freeze()`: 115 files (schema `greg-protected-evolution-freeze/3`); freeze file `sha256:9378b56e91ba266fffc37d04097a122e653e8e63f7a86a3eb4daa0095dd70d27` |
| Run | once, by `python -m greg.cognition.evolution --freeze F --out O` (the clean room), at the commit that adds `freeze.json`, pinned to one CPU core |

## Multiple attempts

The frozen rule decides with alpha 0.05. The README will report the held-out p-value beside:

- the four-attempt threshold on this target, 0.05/4 = 0.0125;
- the programme-wide threshold, 0.05/6 = 0.00833 (the sixth P8 cycle).

A RETAIN above either threshold is reported as not surviving that correction.

## Prediction (from pilot 2; not part of the rule)

- **The trigger fires.** The incumbent lost to random restart on 46.7-51.7% of the items of each 120-item review
  train set; the threshold is 25%.
- **P(RETAIN) is about 0.63** at alpha 0.05 (mean of six simulated cycles; range 0.11 to 0.97), about 0.50 at 0.0125
  and about 0.46 at 0.00833.
- **These are optimistic.** The pool 3740-3999 measured every pilot's picks, the resampling treats it as the
  population, and the train sets overlap pilot 1's.

## What RETAIN would mean

As cycle 5's pre-registration: a `PROPOSED_NOT_APPLIED` proposal to change `CR_DEFAULT_CONFIG`, rollback to the
incumbent `cfg-111751096c0d`, canary by re-admission on fresh seeds. Nothing is applied; adoption is a reviewed
change and the founder's decision. Section 31 item 7 would be met at the proposal level.

## What REJECT would mean

The record names the gate. Section 31 item 7 stays unmet after six cycles, nothing is applied, and the cycle-6
held-out split is spent. A REJECT at the held-out gate with a restart-heavy candidate would not refute the headroom
that cycle 5's pilot measured on 300 fresh items. It would mean this target cannot clear the frozen rule at the power
these split sizes give. A seventh attempt on this target should not follow without a change in what is searched or
measured.

## Procedure

1. Commit this design (code, tests, pilots, this file) and check the tree is clean.
2. Write the freeze:

       PYTHONPATH=. taskset -c 1 python -m greg.cognition.evolution --target constraint_release \
         --write-freeze docs/evidence/greg-protected-evolution/2026-10-16-cr-6/freeze.json \
         --generations 5 --population 8 --seed 20261021 --search cover/1 --lhs 0

3. Fill *Seals* and *Trusted code* from it and commit both.
4. Run once:

       PYTHONPATH=. taskset -c 1 python -m greg.cognition.evolution --target constraint_release \
         --freeze docs/evidence/greg-protected-evolution/2026-10-16-cr-6/freeze.json \
         --out docs/evidence/greg-protected-evolution/2026-10-16-cr-6/cycle-cr-6.json
