# Genome admission v8: pre-registration (2026-10-22)

**Status:** pre-registered. This file is committed before `freeze.json`, and both are committed before any held-out
instance is generated. The run refuses to report if any frozen input differs.

v8 builds the families that the coverage record (`docs/collaboration/MIND-COVERAGE-2026-10-21.md`) still listed as
ABSENT after v7. Five lanes built them in parallel from #158 `c04b0f18`; each lane's branch is kept unchanged as
lineage (`claude/v8-lane-A` … `claude/v8-lane-E`). The lead merged them on `claude/v8-wave` and made two benchmark
changes at merge review, disclosed below. All development used seeds 0-9 only.

## What is fixed before the run

| Item | Value |
|---|---|
| Run id | `2026-10-22-v8` |
| Held-out seeds | 1700-1729 (`--heldout-start 1700`) |
| Families | the 15 listed below, all new at 1.0.0 |
| Rule | `RULE` verbatim, unchanged since v2; `decide()`, `COST_RATIO` 1.25 and `ALPHA` 0.05 unchanged |
| Code | the harness's import closure, all of `greg/cognition`, the extras and dependency versions, each hashed in `freeze.json` |
| Arms and statistics | as in v4-v7 |
| Run | once, in a clean detached worktree at the commit that adds `freeze.json`, pinned to one core. A crash is recorded, never retried |
| Machine | starts only after every design lane has finished and the 1-minute load is below 1.5; start and end load recorded |

**Why 1700-1729 are fresh:**
- No genome-admission freeze uses them. Admission held-out spans already used are 1000-1029 and 1100-1129 through 1600-1629.
- No #179 freeze uses them; its ranges are 1001-1040, 2001-2040, 3001-3040, 5001-5040 and 6501-6840.
- They are not P8-reserved (7000-9199) and not in a declared development range.
- All 15 generators are new. Before this freeze, the exposure ledger shows only their development seeds 0-9.
- The harness's spent-seed and reused-instance checks run again at freeze time.

## Families (15)

| Family | Layer | Coverage item closed if admitted | Baseline | Competitor | Dev-only expectation (not part of the rule) |
|---|---|---|---|---|---|
| `game_repeated_sustain` | 3 | repeated games | one-shot deviation check at the given δ | 5000-period simulation + bisection | DEFAULT on latency (ties the simulation) |
| `game_nash_bargaining` | 3 | bargaining models | best vertex | SciPy SLSQP on the log-product | SUPERSEDED (SLSQP ties and is faster) |
| `game_stackelberg_commit` | 3 | credible commitment | best pure commitment | HiGHS multiple LPs (changed at merge, see below) | ties the competitor; verdict rests on latency |
| `prove_resolution` | 3 | theorem proving | truth table (≤ 18 atoms) | Z3 | see the scoring disclosure below |
| `mdl_model_select` | 3 | compression / minimum description | maximum degree | BIC | NICHE or EXPERIMENTAL |
| `convex_qp_dual` | 3 | convex optimization | dual projected gradient | SciPy trust-constr | EXPERIMENTAL against the baseline |
| `control_robust_tube` | 3 | robust control | nominal MPC, open loop | min-max open-loop vertex LP | EXPERIMENTAL; the competitor optimises the score's objective |
| `basal_cusum_detect` | 1 | local sensing (signal level) | calibrated window z-test | Shiryaev–Roberts | EXPERIMENTAL or REJECTED (ties) |
| `basal_hamming_correct` | 1 | local error correction | no correction | exhaustive Bayes decoder | NICHE |
| `evo_novelty_search` | 3 | novelty search | objective hill climbing | MAP-Elites, same descriptor | DEFAULT or NICHE (wins only on deceptive mazes) |
| `hyper_select_lowlevel` | 3 | hyperheuristics | first-fit decreasing | random-selection hyper-heuristic | DEFAULT on parity, at risk of tying |
| `develop_differentiate` | 4 | differentiation (role specialisation) | random roles | centralised greedy MIS (charged 2 × radius rounds) | DEFAULT |
| `forecast_judgment_pool` | 5 | judgmental forecasting | simple mean | per-event median | DEFAULT only if 7:3 holds |
| `forecast_scenarios` | 3 | scenario forecasts | persistence with Gaussian bands | K Monte Carlo paths from the same model | DEFAULT plausible; the baseline is the risk |
| `forecast_recalibration` | 3 | (calibration; not a coverage item) | raw judgments | Platt scaling | SUPERSEDED (0-10 on dev) |

## Disclosures (part of this pre-registration)

**Changes made after a development result was seen**, recorded in each genome's notes and here:
- **Lane A** (strategic) changed three generators before its final dev run. None of the changes came from the candidate's verdict against the competitor:
  - bargaining solutions that always fell at a vertex;
  - Stackelberg coordination games that were always pure-optimal;
  - repeated-game payoffs widened from 0-20 to 0-99, because ties had made those games degenerate.
- **Lane D** (search and meta) made three changes:
  - raised the maze evaluation budget from 40 to 400 per step, because every arm was failing every maze;
  - replaced a generational novelty search, which ended in the trap on 5 of 7 deceptive mazes, with (μ+λ) survival (Gomes et al. 2015);
  - tightened the differentiation high-diameter threshold so that class is not empty.
- **Merge review** (the lead), before any held-out seed existed:
  - **Stackelberg.** The competitor is now HiGHS multiple LPs. The lane's Nash-commitment competitor was replaced because commitment value is never below the Nash value, so wins against it were guaranteed by theory. On dev the result moved from 2-0 to 0-0-10.
  - **CUSUM.** The declared ARL0 was 200-1000, shorter than the 200-800-sample streams. Every detector false-alarmed on most instances, so the benchmark could not separate them. It is now 5000-20000, and dev mean quality moved from −153 to −97 with CUSUM tying Shiryaev–Roberts.

**Scoring that favours one arm's form of evidence.** `prove_resolution` scores as follows:

| Answer | Score |
|---|---|
| Correct verdict with an independently checked proof or countermodel | 1 |
| Correct verdict with no checkable object | 0.5 |
| Abstain | 0 |
| Wrong verdict | −1 |

Z3 returns verdicts without a checkable proof object under this contract. So every win the prover has over Z3 comes from this declared preference for a checkable object, not from deciding better. The README will report the verdict-only comparison next to the rule's verdict. A positive verdict means "GREG's route to a checkable resolution proof", never "a stronger decider than Z3".

**Competitors weak or strong by construction:**
- `develop_differentiate`'s centralised competitor is charged 2 × component radius rounds. The LOCAL model allows unbounded message sizes, which favours centralised gathering.
- `control_robust_tube`'s competitor optimises the score's own objective, worst-case cost.
- `game_repeated_sustain`'s formula is exact once the punishment is fixed. Its work is the equilibrium enumeration.

## What the outcome changes, and what it cannot

- **DEFAULT or NICHE** makes a genome routable at 1.0.0. It attaches nothing; attaching is the founder's decision.
- **SUPERSEDED, EXPERIMENTAL or REJECTED** excludes a genome from routing. These verdicts are reported as prominently as positive ones, and the coverage item stays BENCHMARKED.
- **Scope of the instances.** Every instance is mathematical or simulated. A verdict says nothing about a natural workload.
- **Known routing gap.** The Competency Compiler routes bin-packing requests to the admitted `binpack_cpsat` even above its 150-item abstention limit (found by lane D). That is a compiler defect. It is outside this admission and recorded for the compiler backlog.
