# Declaration: does an authorized correction produce a better later decision? (2026-10-28)

This file is written, committed and pushed before the experiment test exists or runs. The test is
`tests/integration/test_outcome_correction_changes_decision.py`, written after this commit. Nothing below may change
after the run. A failed prediction is reported as failed.

**Directive:** founder directive of 2026-10-28 on #210, section 4. Decide whether correcting an observation
produces a measurably better later decision under a frozen, independent rule, compared with the same system
without the repair mechanism.

**Tier:** laboratory. One temporary body, a per-test founder key, synthetic world values. Real constructions,
compile receipts, missions, signed commands and appraisals run on the canonical path. It is not a real-world
learning dividend.

## The declared world (the truth the evaluation uses)

The scenario is the existing routing test `test_world_failures_of_a_construction_make_a_later_compile_choose_the_other_fit`.
It uses the same fixture: frozen evidence reads `flow_maxflow` as EXPERIMENTAL, so the construction ranks first on
a request that carries both input shapes.

- **Construction:** ten portfolio answers from the attached `selection.closure` construction, each promising
  profit 2. In the declared world, answers 0 to 5 realize profit 0 (the promise fails) and answers 6 to 9 realize
  profit 2 (kept). Its true world success rate is **0.4**.
- **Competitor:** ten answers from `cognition.flow_maxflow`, certified and settled through their signed checks.
  The declared world has no shortfall for them. Its true success rate is **1.0**.

## The evidence the body receives

1. **Adversarial reports:** `founder_reported` profit 2 for all ten portfolio answers. This is wrong for answers
   0 to 5.
2. **Independent observations:** `external_record` with the declared true value for all ten. Answers 0 to 5
   become disputes (2 against 0, different verdicts); answers 6 to 9 agree.
3. **Repair arm only:** for each dispute, the founder signs the resolution the body itself prepared. It accepts
   the external record.

## Arms (the same body history; only the mechanism differs)

- **A (no independent evidence):** after step 1 only.
- **B (repair disabled):** after step 2, with resolutions ignored (`settlement._resolutions` returns nothing).
  This is the #210 `ec38d8a5` behaviour: disputed claims are scored as neither.
- **C (repair):** after step 3.

## The decision, and the frozen rule that scores it

**The decision:** the compiler's selection for a later request carrying both shapes (`execute: False`). In arm C
a signed mission also answers it.

**Score:** the declared true success rate of the selected method (construction 0.4, `flow_maxflow` 1.0). C is
**better** than B only if its score is strictly higher. Equal scores mean no gain.

## Predictions (each is checked; any miss is reported)

1. **A and B:** both select the construction, so both score 0.4.
2. **C:** selects `flow_maxflow` and scores 1.0, so C is better than B and A. The signed mission in C also uses
   `flow_maxflow`.
3. **Preservation:** all 20 realization facts stay on the record after the resolutions, with nothing deleted.
4. **No unsupported credit:** before resolution, competence counts no disputed answer, so the construction stands
   at (4 correct of 4). The following are refused:
   - a resolution accepting a `founder_reported` value;
   - a resolution with no basis;
   - a resolution written without a founder-signed command, which is recorded but resolves nothing.
5. **Recomputed exactly once:** after the resolutions, `reconcile` records exactly one new settlement revision per
   corrected claim, and a second `reconcile` records none. Competence for the construction is (4 correct of 10).
6. **Dependency-aware memory:** the signed mission decided between steps 1 and 3 is listed by
   `decisions_to_recheck`.
7. **Goal Gravity:** before step 3 it shows six disputes to investigate; after step 3 it shows none.
8. **Safeguards:**
   - no `authority_created` true;
   - no capability state change other than the two founder attaches;
   - no spend;
   - the evaluation fixture (the evidence index) is unchanged between arms.

## Stated limits

- The world values and the competitor's true rate are declared, not observed. The scenario is constructed so that
  the repair matters. What it tests is that a legitimate correction reaches a later decision through the existing
  selection rule, and that the ablation does not.
- The founder is scripted and signs every prepared resolution. A real founder may decline.
- The #213 transfer experiment is untouched.
