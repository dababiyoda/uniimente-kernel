# Portfolio under a spending cap: `selection.budgeted` (2026-10-21)

This is the sixth leap under `INTENT-20261013-FRONTIER-LEAP-RECOMBINE`, read against `INTENT-20261019-UPWARD-ASCENT`. It closes the residual recorded in #191, and is stacked on #191.

One agent wrote, attacked and reviewed this change. That is not independent peer review.

## Original deficit

`selection.closure` answers "which offers should I build" only when money for the shared costs is unlimited. A founder usually has a cap: "I can spend 5." A cap turns the best closure into a precedence-constrained knapsack (Johnson & Niemi 1983). That problem is NP-hard, so one minimum cut no longer answers it and no single engine call proves the answer.

## Effect

The founder writes, for example:

> Big earns 9. Plant costs 7. Small1 earns 3. Small2 earns 3. Kit costs 2. Big needs Plant. Small1 needs Kit. Small2 needs Kit. Spend at most 5.

GREG answers: take Kit, Small1 and Small2, for a profit of 4. Big is left out because it needs Plant, which the cap cannot fund. The answer carries a proof tree that GREG checks itself.

The uncapped answer would be every item, for a profit of 6. It spends 9, which is above the cap.

**Falsified if** any of these happens:

- an answer overspends;
- an answer takes an item without its prerequisites;
- an answer earns less than some plan within the cap;
- an answer is accepted without a complete, re-checked proof tree;
- a stated budget is ignored.

## Mechanism (extraction → mutation → recombination)

- **Kept primitive.** Picard's closure: the qualified max-flow engine through `selection.closure`, used as a relaxation. Within any branch, the best closure that ignores the cap bounds every capped plan in that branch.
- **Recombined with.** Land & Doig branch-and-bound on the costs. Each branch either takes a cost or leaves it out. A cost that is left out removes everything that needs it. A cost that is taken gets a premium value larger than all other values combined, so it is forced into the branch's closure.
- **Mutation: the search tree is the certificate.** Every node keeps its own funding flow. `certify_budgeted` re-derives each node's problem from the original items and re-proves each bound with `certify_selection`. It also checks two more things:
  - Each branch has exactly the two children "taken" and "not taken".
  - Each leaf is closed by a fact: it has no plan, its best plan fits the cap, or its bound is no more than the answer.
- **Framework residual: a head reduction may search in rounds** (`Reduction.rounds`, `composed_adapter.in_rounds`).
  - Each round is one isolated engine batch, and every answer below the head is still re-certified.
  - Rounds are allowed only at the head of a chain, and `chain()` refuses a chain with rounds anywhere else.
  - A search that needs more than 2,048 closure problems is refused before anything is claimed.

## Matched baseline

The baseline heuristic is "trim the uncapped plan": take the best plan without the cap, then repeatedly drop the cost whose removal keeps the most profit, until the plan fits. It is reproducible with `baseline.py`, and the output is in `results.json`.

| Family | Cap binding | Heuristic wrong | Profit heuristic leaves behind |
|---|---|---|---|
| Shared fixed costs under a cap, 2,000 instances, budget uniform from 0 to total cost | 1,259 | **11.9%** | **8.6%** |

The honest reading: trimming is usually right. Where it is wrong, it costs real money, and it never tells you whether it was right. The construction always does, through its proof.

## Evidence

- `tests/unit/test_greg_budgeted_selection.py`: 7 tests.
  - The cap flips the choice, and the proof tree has 3 nodes.
  - Refutations, each raising its own error:
    - an overspending plan;
    - an unclosed plan;
    - a worse claimed plan;
    - a branch that was never explored;
    - a bound whose funding proof was removed;
    - a real branch closed falsely;
    - a duplicated branch;
    - a branch closed by its bound that earns more than the answer;
    - an unknown leaf kind.
  - The oracle agrees on 15 seeds.
  - The chain reaches the engine through the closure, and a nested rounds reduction is refused.
  - An oversized proof is refused.
  - The words with a budget become `selection.budgeted`.
  - A signed mission builds the capability in a real body: qualification passes through the engine, and the mission closes with profit 4 after 2 engine-answered closure problems.
- Brute-force agreement through the certified path: 720 oracle cases (60 seeds), 0 mismatches. The largest proof tree had 5 nodes.
- Mutants: group `budgeted selection` in `scripts/ci/check_cortex_mutants.py`. All 6 are caught, and the file's 126 patterns have none stale.
- Regression: every test file that touches reductions, Genesis, the planner, templates or the compiler (91 files) gave 1,662 passed and 10 failed. The failures:
  - Nine are the `test_foundry_systems` / `test_mission_g` environment failures, which also fail on the bare bases here.
  - One parametrized case of `test_greg_cognition` (CP-SAT optimization, untouched by this change) failed once under the full load. It passed in isolation, three times in a row in its own file, and alongside the new tests.

## Authority envelope

The mission is read-only, with a $0 budget. Its spending cap is part of the question, not a spend authorization. Genesis installs nothing. Each formed capability waits for the founder's attach, or for a signed read-only `auto_attach`. Answers report `authority_created: false`. Authority delta: none.

## Known limits

- Worst-case exponential in the number of costs. It is capped and refused, never silently truncated.
- Integer values only.
- One budget, applied to costs only.
- Classification: BUILDABLE. VEPMC: 0.
