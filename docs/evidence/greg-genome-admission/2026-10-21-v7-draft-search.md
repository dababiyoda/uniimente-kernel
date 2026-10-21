# Genome admission v7: DRAFT pre-registration, search families (not frozen)

**Status: DRAFT for the session owner.** Nothing here is frozen. No `freeze.json` exists for it and no held-out
instance of these generators has been generated. Other lanes may also draft v7 sections; they must become **one** v7
freeze over every family (or freezes with disjoint seeds). Seeds must not be spent twice.

To freeze, the owner merges the drafts into `docs/evidence/greg-genome-admission/<run-id>/PREREGISTRATION.md` and runs
`admission --freeze <run-id> --only ... search_beam search_ida_star search_mcts --heldout-start 1600` at a commit that
contains it. The run happens exactly once.

## Proposed fixed items

| Item | Proposed value |
|---|---|
| Held-out seeds | 1600-1629 (shared v7 freeze) |
| Rule | `RULE` verbatim; `decide()`, `COST_RATIO` 1.25 and `ALPHA` 0.05 unchanged |
| Code | the harness's import closure, all of `greg/cognition`, extras and dependency versions, hashed in `freeze.json` |
| Run | once, in a clean detached worktree, pinned to one core, on a quiet machine |

Freshness of 1600-1629, checked 2026-10-21 on branch `lane/absent-search` (base `ae5c55fe`):

- **Freezes:** committed admission freezes use 1000-1029, 1100-1129, 1200-1229, 1300-1329, 1400-1429 and 1500-1529.
- **Ledger:** `scripts/data_exposure_ledger.py` `exposed()` returns no record for 1600-1629 under `search_ida_star`,
  `search_beam` or `search_mcts`. These generators are new; their only exposure is development seeds 0-9.
- **Reserved:** outside `DEV_SEEDS` (0-9), `P8_RESERVED` (7000-9199), #179's ranges (1001-1040, 2001-2040, 5001-5040,
  6501-6840) and the declared review ranges (3000-4999, 9300-9439).
- The harness's `spent_seeds` and `reused_instances` checks run again at freeze time and should be relied on.

## Families (3), all new at 1.0.0 (`greg/cognition/genomes/search.py`)

### `search_ida_star` (L3.search.iterative_deepening)

- **Geometry:** optimal plans for 3x3 and 4x4 sliding-tile puzzles under a declared memory budget of 100,000 stored
  positions, shared by every arm. This is the native geometry of IDA* (Korf 1985): a deep implicit graph where
  frontier-storing searches run out of memory.
- **Candidate:** IDA* with Manhattan distance plus linear conflicts (incremental), stdlib only.
- **Baseline:** breadth-first search under the same memory budget; it abstains when its stored positions would exceed
  the budget.
- **Competitor:** A* with the candidate's own heuristic and a closed list, under the same budget. **Why the
  strongest:** no sliding-puzzle solver is installed and no GREG genome searches implicit state graphs.
  `search_astar`/`grid_dijkstra` need an explicit grid. A* with the same admissible heuristic is the textbook
  rival: optimal, fewer expansions, faster in Python whenever memory suffices.
- **Truth:** the optimal plan length by the verifier's code, never the solver's: a breadth-first table of all 181,440
  solvable 3x3 positions; on 4x4, increasing bounds of a plain-Manhattan exhaustive depth-first search.
- **Scoring:** optimal plan scores 1.0 (correct). A valid longer plan scores optimum/length (wrong). An invalid
  plan scores -1 (wrong). Abstention scores 0. Tolerance 1e-9.
- **Subregions:** `3x3`, `4x4`. The generator alternates 3x3, 4x4, 4x4, 3x3, 4x4 by `seed % 5`, so 1600-1629
  gives 12 3x3 and 18 4x4.
- **The decisive assumption:** the memory budget decides the comparison with A*. Without it A* would be at least as
  good and faster. The verdict says nothing about memory-unbounded settings.

### `search_beam` (L3.search.beam)

- **Geometry:** permutation flow-shop sequencing (minimum makespan). Instances are Taillard-style U[1, 99],
  job-correlated and machine-correlated, with 15-50 jobs on 5-20 machines.
- **Candidate:** beam search in NEH's insertion space, Taillard-accelerated. The width is 2,000,000 / (jobs^2 x
  machines), clipped to [4, 64]. The greedy NEH chain is anchored in the beam, so the answer is never worse than
  NEH by construction.
- **Baseline:** NEH (Nawaz, Enscore and Ham 1983), the beam at width 1.
- **Competitor:** OR-Tools CP-SAT on the permutation flow-shop model, warm-started from NEH (one worker, 2 s). It
  returns the better of its best sequence and the warm start. **Why the strongest:** CP-SAT is the strongest
  installed engine, and no GREG genome sequences flow shops. The published state of the art for this objective,
  Iterated Greedy (Ruiz and Stuetzle 2007), is neither installed nor in GREG. It is **not** compared, and a
  positive verdict says nothing about it.
- **Truth:** Taillard's lower bound, an instance property. No optimum is computed.
- **Scoring:** quality = lower bound / recomputed makespan. A valid sequence is correct. An invalid sequence or a
  false makespan is wrong (-1). Abstention scores 0. Tolerance 1e-9, so any makespan difference counts.
- **Subregions:** `small (<= 20 jobs)`, `medium (30 jobs)`, `large (50 jobs)`.

### `search_mcts` (L3.search.mcts)

- **Geometry:** move selection in Hex positions under a declared simulator budget of 60,000 stone placements,
  shared by every arm. Positions come from seeded uniform random play on 6x6 and 7x7 with 17-20 empty cells. A
  position is kept only if:
  - nobody has joined;
  - there is no immediate win or threat;
  - the mover has a winning move;
  - at most half of the mover's moves win;
  - the exact solve finishes within its 3,000,000-node cap.

  The last condition favours easier positions.
- **Candidate:** UCT (UCB1, c = 1.0, not tuned), uniform random playouts, most-visited root child.
- **Baseline:** flat Monte Carlo at the same budget: round-robin playouts per move, best win rate.
- **Competitor:** iterative-deepening alpha-beta with the Shannon-Anshelevich resistance evaluation, the classical
  pre-MCTS Hex design, at the same placement budget with a 10 s cap. **Why the strongest:** no Hex or general game
  engine is installed (no open_spiel or mctx), and no GREG genome plays sequential games beyond small matrix games
  and finite MDPs. This competitor is built in the module, not acquired.
- **Truth:** the exact set of winning moves, by `hex_exact`: bitboard negamax with a transposition table and sound
  immediate-win and forced-block pruning. This is evaluation and verifier code, never the solver's. The tests
  cross-check it against a plain unpruned negamax on reduced positions from dev seeds.
- **Scoring:** a winning move is correct (1). A legal losing move is wrong (0). An illegal move scores -1. A
  candidate move refuted by the verifier's exact check is scored as a false answer (-1).
- **Subregions:** `6x6` (even seeds), `7x7` (odd seeds).

## Development disclosure (seeds 0-9 only; none of this is admission evidence)

`admission --dev FAMILY` outputs, final code (commit `539bbdde`):

| Family | Status if held-out matched | vs baseline (W-L-T, p) | vs competitor (W-L-T, p) | Median latency cand / base / comp (s) | Correct / wrong / abstain (cand; base; comp) |
|---|---|---|---|---|---|
| `search_ida_star` | DEFAULT_FOR_GEOMETRY | 8-0-2, p = 0.0039 | 1-0-9, p = 0.5 | 0.019 / 0.110 / 0.027 | 10/0/0; 2/0/8; 9/0/1 |
| `search_beam` | **EXPERIMENTAL** | 3-0-7, p = 0.125 | 3-0-7, p = 0.125 | 0.605 / 0.012 / 2.066 | 10/0/0 all arms; mean quality 0.871 vs 0.866 vs 0.866 |
| `search_mcts` | **EXPERIMENTAL** | **1-1-8, p = 0.75** | 4-1-5, p = 0.19 | 0.076 / 0.043 / 6.42 | 9/1/0; 8/2/0; 6/4/0 |

**Subregions on dev:**
- **IDA*:**
  - 3x3: 2-0-2 against BFS, 0-0-4 against A*.
  - 4x4: 6-0-0 against BFS, 1-0-5 against A* (A* exceeded the memory budget once).
- **Beam:**
  - small: 2-0-2 against both arms;
  - medium: 0-0-2;
  - large: 1-0-3.
- **MCTS:**
  - 6x6: 0-0-5 against flat MC, 2-0-3 against alpha-beta;
  - 7x7: 1-1-3 against flat MC, 2-1-2 against alpha-beta.

**Negative expectations, stated first:**
- **`search_mcts` is expected to be EXPERIMENTAL.** On these positions flat Monte Carlo is about as good as UCT: 1-1
  on dev, and 10-10 correct on an earlier 14-16-empty variant. UCT's edge over its simplest baseline is not
  established at this budget and size. Plausible reasons: positions from random play are lopsided, the budget is
  large relative to 17-20 empties, and the boards are small. A larger board would need a stronger exact solver for
  truth. Against alpha-beta, MCTS looked better (4-1) and much faster.
- **`search_beam` is uncertain.** It wins only where the insertion landscape is not flat (3 of 10 on dev; it tied
  every job-correlated instance). By construction it never loses to NEH, and in practice it never lost to the
  competitor either. The CP-SAT competitor never improved its NEH warm start within 2 s on dev, so in practice it
  equals NEH. That makes the competitor test weak; this is disclosed here and is not a strength of the candidate.
  If the held-out win rate matches dev (~30%), about 9-0 gives DEFAULT, because the latency of 0.6 s is within
  1.25x of the competitor's 2 s. Fewer than 5 wins gives EXPERIMENTAL.
- **`search_ida_star` is expected to be DEFAULT, for a constructed reason.** The memory budget, a declared problem
  input, is what makes BFS and A* abstain. On dev, A* failed the budget only once, so the A* comparison rests on
  latency (0.019 s against 0.027 s median, inside 1.25x). On held-out instances with plans in the forties, IDA* can
  exceed its 5 s budget (UNKNOWN). On dev it did not after the change below.

**Changes made after seeing development results, all before any held-out instance existed:**
1. **IDA*:**
   - Linear conflicts became incremental and then memoised per line, after dev showed 4x4 plans of 44-49 timing out
     at 5 s.
   - The 4x4 random walk was shortened from 50-110 to 40-80 moves, after dev seeds 4, 7 and 9 (optima 44, 47, 51)
     timed out or needed 14-81 s for truth.
   - The verifier node cap was lowered from 40 M to 20 M.
2. **Beam:**
   - The first design, a forward beam over partial sequences with bound plus idle-time guidance, lost to NEH on 7
     of 10 dev seeds. It was replaced by the NEH-insertion beam, which lost 1 of 10.
   - The NEH chain was then anchored in the beam (dev seed 8 had lost 954 to 942).
   - The CP-SAT competitor was changed to return its NEH warm start when it finds nothing better. It had returned
     no solution on the 50x20 dev seed 7 within 2 s, which would have handed the candidate a free win.
3. **MCTS:**
   - The positions were changed twice, before the final dev run:
     - 12-16 empties, any position: nearly all arms were correct and many positions were one-move tactics;
     - then 14-16 empties excluding immediate wins and threats: UCT and flat MC both 10/10;
     - then the final 17-20 empties.
   - The budget was raised from 20,000 to 60,000 placements.
   - The exact solver was rewritten on bitboards with forced-block pruning and centre-first ordering for speed.
   - The verifier's exact-check bound was raised from 16 to 20 empty cells, to cover the final benchmark.
4. **Timing probes off the generators:** exact-solver timings used scratch positions from
   `random.Random("scratch-timing:...")`, which no generator draws. The parity cross-check in the tests uses
   `random.Random("parity:...")`. No generator was called with a seed outside 0-9.

No parameter was changed after the final dev run of each family.

## What the outcome changes, and what it cannot

- A DEFAULT or NICHE verdict makes a genome routable at 1.0.0. It does not attach it; attaching is the founder's
  decision.
- EXPERIMENTAL, SUPERSEDED and REJECTED exclude a genome from routing.
- All three benchmarks are mathematical instances: generated problems with truth computed from them. A verdict
  says nothing about real scheduling data, real games or real planning domains.
- Held-out run cost: Hex generation with exact solves took up to about 60 s per seed on dev, and the alpha-beta arm
  up to 10 s per instance. Expect roughly 30-60 minutes for `search_mcts`.
- The coverage record `docs/collaboration/MIND-COVERAGE-2026-10-21.json` is a generated snapshot at `239a87f`. It is
  not edited in this lane. A rebuild after merge should move the three items from ABSENT to INTEGRATED.
