# IntelligenceGenome admission: native benchmarks for the executable operation-contract families, 2026-10-14

Runner `cortex/evaluation/genome_admission/run.py`; freeze `freeze-v1.json` (seeds 1001-1040, every parameter
declared before the run); results `results.json`. Each family's real solver (`greg/cognition/solvers.py`) is
scored per item against a simple baseline and, where one exists, the strongest reasonable competitor.

| Family | Layer | Status | vs baseline W/L | vs competitor W/L | Note |
|---|---|---|---|---|---|
| probabilistic (Beta posterior) | 3 | DEFAULT_FOR_GEOMETRY | 29/10 (clipped MLE) | 26/13 (Jeffreys) | small-sample prediction |
| control (PID kp=2 ki=1) | 1 | DEFAULT_FOR_GEOMETRY | 40/0 (bang-bang) | 40/0 (P-only) | IAE 1.73 vs 8.08 / 7.10 |
| micro (set-point band) | 1 | DEFAULT_FOR_GEOMETRY | 38/2 (single-threshold reflex) | - | fewer switches, comfort kept |
| sequential (backward induction) | 3 | DEFAULT_FOR_GEOMETRY | 14/0 (greedy) | - | |
| information (value of information) | 3 | DEFAULT_FOR_GEOMETRY | 26/0 (never acquire) | 14/0 (always acquire) | |
| game (minimax LP) | 3 | DEFAULT_FOR_GEOMETRY | 40/0 (uniform) | 33/0 (pure maximin) | |
| graph (Dijkstra) | 3 | DEFAULT_FOR_GEOMETRY | 8/0 (fewest hops) | - | 32 ties |
| exact (rational arithmetic) | 3 | DEFAULT_FOR_GEOMETRY | 40/0 (float) | - | |
| **pattern (z-score)** | 1 | **REJECTED** | 6/23 (IQR) | 1/24 (median/MAD) | masked by contamination; MAD is the acquisition target |
| **collective (quorum)** | 2 | **REJECTED** | 5/16 (most accurate observer) | 7/11 (majority) | baseline knows observer accuracy; quorum abstains |
| **evolutionary (DE on a quadratic)** | 2/4 | **REJECTED** | 0/40 (analytic minimum) | - | the declared geometry has a closed form |
| **simulation (Monte Carlo mean)** | 3 | **REJECTED** | 0/40 (analytic) | - | the declared geometry has a closed form |

Structural (not benchmarked here): `search` ALIAS of graph; `estimation`, `formal`, `optimization`
SUPERSEDED_BY_CANONICAL_ORGAN (cortex Fermi / Z3 / CP-SAT); `causal` NOT_BENCHMARKED (randomized estimate equals
the naive difference; observational identification belongs to the cortex organ, P6 F2/F2b evidence); `semantic`
NOT_RUN (no local model); `human` ROUTE_ONLY; `evidence`, `protection` NOT_BENCHMARKED (no ground-truth suite yet).

Rejection is an asset: four families as implemented are worse than a simpler method on their own declared
geometry. Their code stays (history, fallback, research); routing must not prefer them there.
