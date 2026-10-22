# Portfolio questions in plain words, answered by a constructed capability (2026-10-21)

This is the fifth leap under `INTENT-20261013-FRONTIER-LEAP-RECOMBINE`. It is read against `INTENT-20261019-UPWARD-ASCENT` (#190): a convergence has to deliver an integrated capability, not only preserved material. It is stacked on #188.

One agent wrote, attacked and reviewed this change. That is not independent peer review.

## Original deficit

`selection.closure` (#187) answered which offers or projects to take when some need others first. It could only be reached two ways:

- through hand-written mission JSON;
- through the Mind's compiled question.

The founder's words could not reach it. "Which offers should I build?" is the decision a founder makes most often, and the console had no path for it.

## Effect

The founder types a portfolio in controlled words, for example:

> Which offers should I build? Offer1 earns 5. Offer2 earns $6. Platform costs 6. Audit costs 3. Pilot earns 3. Lab costs 5. Offer1 needs Platform. Offer2 needs Platform and Audit. Pilot requires Lab.

GREG reads the words without a model and proposes a read-only mission. Capability Genesis then builds the answering capability, and the founder attaches each piece it forms:

1. Genesis acquires and qualifies the max-flow engine, and the founder attaches it.
2. Genesis constructs and verifies `selection.closure` over that engine, and the founder attaches it.
3. The mission closes with a certified answer:
   - **Take:** Audit, Offer1, Offer2, Platform.
   - **Profit:** 2.
   - **Left out:** Pilot, because it would need Lab, which costs more than Pilot earns.

Any sentence GREG cannot read stops the plan and is named back to the founder. So does a prerequisite that has no value, a fractional amount, a value stated twice, or a portfolio where nothing earns anything.

**Falsified if** any of these happens:

- an unread sentence is dropped silently;
- a cost is read as earnings;
- a prerequisite with no value is accepted;
- the planner routes the words anywhere else;
- the answer appears before both founder attaches;
- the answer is not certified.

## Matched baseline (why the construction earns its place)

The baseline is a standalone greedy rule: take any profitable item whose unmet prerequisites it pays for on its own. This is what a person does without the construction. The reproducible run is `baseline.py`, and its output is `results.json`.

| Family (2,000 instances each) | Greedy is wrong | Profit greedy leaves behind |
|---|---|---|
| Uniform random (the oracle's generator) | 1.6% | 0.9% |
| Shared fixed costs: 1–3 costs, 2–5 offers each needing 1–3 of them | **38.0%** | **38.6%** |
| The example above | yes | all of it: greedy takes nothing (0); optimum 2 |

**The honest reading:** the advantage is concentrated where offers share costly prerequisites. That is the situation of a founder deciding which products to build on a shared platform. On unstructured portfolios the greedy rule is usually right.

## Mechanisms reused (nothing new as architecture)

| Mechanism | Where |
|---|---|
| Controlled-language front ends (sentence split, unread sentences stop the plan) | `greg/templates.py` `read_network_words` and `read_plan_words` pattern |
| Template route, ahead of any model | `greg/planner.py` `template_route` |
| The constructed mission and its light cone | `greg/templates.py` `constructed_question` |
| Picard's reduction with GREG's funding certificate | `greg/recombine.py` `selection-via-maxflow` (#187) |
| The founder attach path | `CAPABILITY_ATTACH`, `greg/body.py` |

The only new code is the residual: a parser (`read_portfolio_words`), a template (`portfolio_in_words`) and one planner branch.

## Authority envelope

- The mission is read-only, with a $0 budget, and it has no `auto_attach`.
- Genesis installs nothing.
- Every formed capability waits for the founder's signed attach.
- The answer creates no authority (`authority_created: false`).
- Nothing is bought, hired or started.

Authority delta: none.

## Evidence

- `tests/unit/test_greg_portfolio_words.py`: 10 tests.
  - The exact reading.
  - Lenient forms: `$`, thousands commas, unit words, "depends on", lists.
  - Six refusals.
  - The planner proposal.
  - Coexistence with the network and plan languages.
  - The full words-to-certified-answer run on a real body, through two founder attaches.
- Mutants: group `portfolio words` in `scripts/ci/check_cortex_mutants.py`. All 4 are caught. The file has 120 patterns, and none is stale.
- Neighbouring suites: every test file that touches `planner` or `templates` (34 files) gave 667 passed and 2 skipped locally.

## Known limits

- Names are single tokens: `Offer1`, or `Site-Redesign`, not "the site redesign".
- Amounts are whole numbers in one unit the founder chooses. Fractions are refused, not rounded.
- There is no budget cap. "Spend at most 10" is a knapsack-shaped constraint that maximum-weight closure does not express. That is the next residual, and is recorded here as open.
- Classification: BUILDABLE (built and tested here). VEPMC: 0. No external effect was produced.
