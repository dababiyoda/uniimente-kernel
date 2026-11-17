# Genome admission v7: DRAFT pre-registration, property-based testing (L3), associative memory (L1), cellular-automaton regeneration (L4) (not frozen)

**Status: DRAFT for the session owner.** Nothing here is frozen. No `freeze.json` exists for it, and no held-out
instance of these generators has been generated. Other lanes may propose v7 families on the same seeds; all v7
families must go into **one** v7 freeze (one `--only` list, one `--heldout-start`), or into freezes with disjoint
seeds. The same seeds must not be spent twice.

To freeze, the owner merges the v7 drafts into `docs/evidence/greg-genome-admission/<run-id>/PREREGISTRATION.md` and
runs `python -m greg.cognition.genomes.admission --freeze <run-id> --only <families> --heldout-start 1600` at a commit
that contains it. The run then happens exactly once, from a clean checkout of the freeze commit.

## Proposed fixed items

| Item | Proposed value |
|---|---|
| Held-out seeds | 1600-1629 |
| Rule | `RULE` verbatim, unchanged; `decide()`, `COST_RATIO` 1.25 and `ALPHA` 0.05 are also unchanged |
| Code | the harness's import closure, all of `greg/cognition`, the extras and the dependency versions, hashed in `freeze.json` |
| Run | once, in a clean detached worktree, pinned to one core, on a quiet machine |

Checks behind seeds 1600-1629, made 2026-10-21 on branch `lane/absent-formal` (base `ae5c55fe`):

- No committed `docs/evidence/greg-genome-admission/*/freeze.json` uses them; existing held-out seeds span 1000-1529.
- They are outside `DEV_SEEDS` (0-9) and `P8_RESERVED` (7000-9199).
- The three generators below are new; this lane generated **only** dev seeds 0-9 for them (the `--dev` runs and
  `tests/unit/test_genomes_absent_formal.py`, which asserts `0 <= seed < 10`). No review range was declared or used.
- The harness's own `spent_seeds` check refuses spent seeds at freeze time and should be relied on.

## Families (3), all new at 1.0.0

| Family | Layer | World | Baseline | Competitor | Dev-only expectation (not part of the rule) |
|---|---|---|---|---|---|
| `formal_property_search` | 3 | mathematical | uniform random inputs, same budget | Z3 symbolic search | **EXPERIMENTAL** (2-0-8 vs baseline, p = 0.25); 0-3 vs Z3 |
| `basal_hopfield` | 1 | simulated | no recall (the cue) | exact nearest neighbour | **EXPERIMENTAL** (3-0-7 vs baseline, p = 0.125); 0-7 vs nearest neighbour (p = 0.008) |
| `develop_ca_repair` | 4 | simulated | no repair | Z3 global entailment | **DEFAULT_FOR_GEOMETRY** on cost only (10-0 vs baseline; 0-0-10 ties with Z3, ~56x faster) |

**Negative expectations first.** On dev seeds neither the property-based search nor the associative network shows
a significant edge over its simplest baseline, and both lose to their competitor wherever they differ. The
competitor of each is never beaten on quality on any dev seed, and cannot be beaten on quality by construction in
two of the three (nearest neighbour is the Bayes decoder; global entailment is a superset of local propagation). The
cellular automaton's dev verdict rests entirely on latency: it ties the global solver on every dev seed.

## `formal_property_search` 1.0.0 (L3, `greg/cognition/genomes/formal.py`)

- **Operation:** `find_property_counterexample`. Inputs `function_under_test` {parameters [{name, min, max}],
  body} and `property`, in `verify_modelcheck`'s typed JSON expression language (linear integer arithmetic, `mod`
  by a literal, `min`/`max`, `ite`, comparisons, connectives). Output `{verdict: COUNTEREXAMPLE, counterexample,
  result}`. The genome never claims absence: no counterexample within 2,000 evaluations is `UNKNOWN`.
- **Mechanism:** Hypothesis is not installed here, so its mechanisms are reproduced: seeded generation (30% mined
  constants and their neighbours, 15% domain edges and 0/±1, 10% reuse of another argument, 10% small values, 35%
  uniform), duplicates skipped; greedy shrinking toward zero (at most 200 of the 2,000 evaluations).
- **Baseline:** uniform random inputs over the declared domain with the same 2,000-evaluation budget, no shrinking.
- **Competitor and why:** Z3 (linear integer arithmetic, 4 s): the strongest deployable method on this language,
  which is decidable. It returns a counterexample, a proof that none exists, or abstains. It is expected to dominate.
- **Truth:** by construction. Ten kinds: literal point, literal pair, linear relation, residue class, corner,
  off-by-one comparison, clamp bound, wide region (each a planted change of the result on a known region, with a
  witness re-executed at generation), and two bug-free decoys (a guard that changes nothing, a `max(spec, spec)`
  rewrite). The property is equality with the specification.
- **Scoring:** a counterexample that re-executes (independent recursive interpreter `_mc_eval`): 1, correct. A
  proof of absence on a bug-free function: 1, correct. Silence: 0, abstain. A refuted counterexample or a proof of
  absence on a buggy function: -1, wrong. The genome can therefore never score on a decoy; Z3 scores 1 there.
- **Subregions (from the data):** `equality_guard`, `inequality_guard`, `no_added_guard` (comparison operators the
  body adds beyond the property's).
- **Dev seeds 0-9 (all disclosed):**

  | Seed | Kind | Candidate | Baseline | Z3 |
  |---|---|---|---|---|
  | 0 | clean_decoy | abstain | abstain | proof (1) |
  | 1 | residue | found | found | found |
  | 2 | clamp_bound | found | found | found |
  | 3 | residue | found | found | found |
  | 4 | wide | found | found | found |
  | 5 | linear_relation | **missed** | missed | found |
  | 6 | clean_rewrite | abstain | abstain | proof (1) |
  | 7 | wide | found | found | found |
  | 8 | point_literal | found | **missed** | found |
  | 9 | point_literal | found | **missed** | found |

  Median latency: candidate 2.0 ms, baseline 7.5 ms, Z3 8.1 ms. 0 wrong answers in any arm.
- **Learned on dev and changed:** the subregion function first counted operators by set difference, which put
  every seed in `no_added_guard` (the property's own `==` masked the guard's). It was fixed to a multiset
  difference that excludes the property's root, after the first dev run. A unit-test assertion about shrinking
  (that the shrinker's output is already minimal) was wrong because shrinking is budget-limited; the test was
  corrected, the genome was not. No mechanism weight, budget or generator parameter was changed after any dev result
  was seen.
- **Expected:** the mined-constant dictionary is the only measured edge (literal guards on wide domains, seeds 8-9).
  The linear-relation kind defeats both random arms (seed 5). With 2 of 10 kinds bug-free, Z3 should collect about 6
  uncontested wins on 30 seeds, so if the candidate does beat the baseline significantly the rule's outcome is
  SUPERSEDED (0 wins against Z3), otherwise EXPERIMENTAL. A positive verdict would need Z3 to time out, which it did
  not on any dev seed.

## `basal_hopfield` 1.0.0 (L1, `greg/cognition/genomes/basal_memory.py`)

- **Operation:** `associative_recall`. Inputs `stored_patterns` (binary strings of one length N) and `cue`. Output
  `{recalled, memory_index}`. A network that settles in a state that is not a stored pattern (a spurious mixture)
  answers `UNKNOWN`.
- **Mechanism:** classical Hopfield network: integer Hebbian weights `X^T X`, zero diagonal; asynchronous sign
  updates in a seeded random order with incremental local fields, until a sweep flips nothing (cap 50 sweeps).
- **Baseline:** no recall: the cue is returned as the answer (category wrong unless the cue is a stored pattern).
- **Competitor and why:** exact nearest neighbour by Hamming distance over every stored pattern (NumPy). For
  independent bit flips and a uniform prior it is the Bayes decoder, so it is the accuracy ceiling; and because the
  patterns arrive with the request, building the N x N weights (O(P N^2)) is no cheaper than its O(P N) scan. The
  bounded-memory niche (weights built once, patterns discarded) is outside this stateless request contract and is
  not claimed.
- **Truth:** the hidden index of the source pattern of the cue.
- **Scoring:** quality = fraction of bits equal to the source pattern; correct only on exact recall of it, otherwise
  wrong; abstaining keeps the cue's agreement (so abstaining ties the no-recall baseline).
- **Subregions (from the data):** load below or above 0.138 N (`low_load` / `over_capacity`) x mean bit density
  above 0.55 (`_biased` / `_random`).
- **Generator:** N in {64, 96, 128, 192, 256}; load P/N uniform in 0.02-0.25; P(bit = 1) = 0.5, 0.5, 0.6 or 0.7;
  5-30% of the cue's bits flipped.
- **Dev seeds 0-9 (all disclosed):** the candidate recalled exactly on seeds 0, 2, 3 (all `low_load_random`) and
  abstained (spurious state) on the other 7, including the one `low_load_biased` seed (7, 29% flips). Nearest
  neighbour recalled exactly on all 10. 0 wrong answers by the candidate; the baseline is wrong on all 10. Median
  latency: candidate 1.0 ms, baseline 0.1 ms, nearest neighbour 0.15 ms.
- **Learned on dev and changed:** nothing. (Before the first dev run the verifier's fixed-point check was rewritten
  from a pure-Python loop to a NumPy recomputation from the patterns, for speed; it never ran in the slow form.)
- **Expected:** 6 of 10 dev seeds were over capacity, so the generator's load range is wider than the Hebbian
  rule's capacity; that is declared, not tuned. Expect EXPERIMENTAL (wins over the baseline only at low load,
  abstentions elsewhere), and, if the baseline comparison does reach significance, SUPERSEDED against nearest
  neighbour (significantly worse with no wins). Either outcome is the evaluation the coverage item asked for.

## `develop_ca_repair` 1.0.0 (L4, `greg/cognition/genomes/developmental_ca.py`)

- **Operation:** `regenerate_rule_pattern`. Inputs `eca_rule` (0-255, Wolfram numbering) and `damaged_grid` (rows of
  '0'/'1'/'?'; row t+1 is the rule applied to row t, periodic). Output `{grid, restored, undetermined}`; cells not
  determined stay '?'. Intact cells that contradict the rule give `UNKNOWN`.
- **Mechanism:** a synchronous cellular automaton (radius 1 in space and time): each erased cell intersects the
  values its at most four rule windows allow given its neighbours' current states and takes a value when exactly one
  remains; rounds until nothing changes.
- **Baseline:** no repair (the damaged grid returned; abstain, quality 0).
- **Competitor and why:** the central global solver: Z3 over every rule window at once; each erased cell is restored
  when its opposite value is unsatisfiable (10 s total). It restores every entailed cell, a superset of what local
  propagation reaches, so the candidate cannot beat it on quality; the competitor is the strongest deployable
  "recompute the target" method because it does not need the first row intact.
- **Truth:** the hidden original pattern.
- **Scoring:** (restored cells equal to the original - restored cells that differ) / erased cells; wrong if any
  restored cell differs or an intact cell changes; abstain when nothing is restored.
- **Subregions (from the data):** `first_row_damaged` / `first_row_intact`.
- **Generator:** 17 rules (18, 22, 30, 45, 54, 57, 60, 73, 90, 105, 110, 122, 126, 137, 146, 150, 184), 16-40 cells
  by 12-30 rows from a random first row, 1-4 holes of 2-8 by 2-8 anywhere (the first row included), 0-4% scattered
  erasures.
- **Dev seeds 0-9 (all disclosed):** the candidate and Z3 restored exactly the same cells on all 10 seeds (quality
  1.0 on 9, 0.979 on seed 9, rule 22 with first-row damage, where the same cells stay undetermined for both). Rules
  drawn: 22 (x2), 137 (x2), 126, 122 (x2), 110, 30, 90. 4 seeds had first-row damage. 0 wrong in any arm. Median
  latency: candidate 1.5 ms, baseline 0.13 ms, Z3 84.5 ms.
- **Learned on dev and changed:** nothing.
- **Expected and its weakness:** if held-out matches dev, the rule gives DEFAULT_FOR_GEOMETRY by latency alone (ties
  on quality, candidate far below 1.25x the competitor's median latency). That verdict would say only that, on this
  benchmark, local propagation already reaches every globally entailed cell; it is not evidence that local rules are
  as strong as global inference in general. Instances where they differ (long constraint chains through several
  unknowns, non-permutive rules with a damaged first row) may simply be rare in this generator; on held-out they
  would appear as losses to Z3, never as wins. A unit test asserts on dev seeds that every local restoration is also
  Z3-entailed and equal to the original.

## Data discipline

- Development seeds 0-9 only, for all three generators, in the `--dev` runs and in the unit tests. No other seed of
  these generators was generated, and none of 1000-1629, 3000-4999, 5001-5040, 6501-6840 or 7000-9439.
- Hypothesis is not installed (`pip list`, 2026-10-21); CrossHair is not installed; Z3 5.1.0.0 is.
- `RULE`, `decide()`, `COST_RATIO`, `ALPHA`, every freeze and every existing file under `docs/evidence/` are
  unchanged, apart from the exposure ledger, which the lane regenerated with its script.

## What the outcome changes, and what it cannot

- A DEFAULT or NICHE verdict makes a genome routable at version 1.0.0. It does not attach it; attaching is the
  founder's decision. All three are registered and withheld (`catalog.initial_state` VERIFIED).
- SUPERSEDED, EXPERIMENTAL and REJECTED verdicts exclude a genome from routing, and are reported as prominently as
  positive ones.
- Two benchmarks are simulated worlds and one is a generated mathematical instance. A positive verdict says nothing
  yet about GREG's real code, memories or damaged structures.
