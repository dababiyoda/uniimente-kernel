# P8 cycle 4: pre-registration (2026-10-15)

**Status:** pre-registered. `freeze.json` and this file were committed before the cycle ran. Cycle 4 is the first cycle run under the committed-freeze rule (`af258bf`): it refuses to report if any frozen input differs.

## What is fixed

| Item | Value |
|---|---|
| Target | `constraint_release`: the search policy (`CR_DEFAULT_CONFIG`) of `develop_constraint_release` 1.2.0 |
| Why this target | Admission v3 (seeds 1200-1229) still measured headroom: random restart won 13-10 against the incumbent (not significant). |
| Closed space | `developmental.CR_CONFIG_SPACE`, unchanged since cycle 3. A candidate is data: `mu`, `offspring`, `tournament` (choices) and four probabilities. Choices are compared type-strictly. |
| Split | named `cycle-4`: train seeds 7400-7459 (60), held-out seeds 7500-7589 (90), inside P8's reserved range and disjoint from every admission seed, the immune target's seeds and cycle 3's split. 350 identities are excluded. |
| Settings | generations 5, population 8, search seed 20261008 (as cycle 3) |
| Rule | verbatim in `freeze.json` (`inputs.rule`), with its constants: trigger 25% failure against random restart on train; a candidate advances only if its train loss beats the incumbent's by more than 1%; adversarial gate: every output verifies and no stress set (`lean`: budget 16; `fewval`: validation cut to four cases) worsens by more than 5%; RETAIN only if the one-sided sign test over the 90 held-out items gives p < 0.05 and lower mean loss |
| Seals | train `sha256:614a4b09...`, held-out `sha256:befd0a31...` (evaluator code, score function, rule, outcomes, inputs) |
| Trusted code | 10 files, each hashed in `freeze.json` |
| Run | once, in a clean worktree at the commit that adds this file, pinned to one CPU core |

## Disclosures

- **This is the second cycle on this target.** Cycle 3 (2026-10-14, split `cycle-3`) was REJECTED at the adversarial gate: its candidate was 20% better on train, but 6.3% worse on the four-case validation stress.
  - A RETAIN here would be one success in two attempts on the target.
  - The README will report the held-out p-value beside its two-attempt Bonferroni threshold (0.025). That threshold is for reading only: the frozen rule decides.
- **The cycle may not trigger.** Cycle 3's train split failed at exactly the 25% threshold. If fewer than 25% of cycle 4's train items fail, the record says NO_RECURRING_FAILURE and nothing is searched.
- **Never applied.** A RETAIN produces a PROPOSED_NOT_APPLIED proposal. Adopting it is a reviewed change and the founder's decision.
  - Adoption would bump `develop_constraint_release`'s version and its pin in `EVOLVABLE_CONFIG_PINS`, so admission v3's verdict would stop routing until re-admission on fresh seeds.
