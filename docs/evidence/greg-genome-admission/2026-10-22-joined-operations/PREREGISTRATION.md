# Operation re-admission on the joined tree: pre-registration (2026-10-22)

**Status:** pre-registered. This file is committed before `freeze.json`, and `freeze.json` is committed before any
held-out instance is generated. `freeze.json` is the machine-checked half; `--run` refuses to report if any frozen
input differs.

## Why this run exists

On the joined tree (`claude/greg-full-machine-completion-whgiee` at `ea90b4b4`) the evidence index routes `control`,
`game` and `information` as UNEVALUATED, though the 2026-10-21 run (`2026-10-21-operations`, pre-registered at
`462bd98`, seeds 2600-2629) found each DEFAULT_FOR_GEOMETRY on exactly the joined solver closures:

> DEFAULT_FOR_GEOMETRY cannot be bound to its code: 1 non-literal update(s) of the dispatch table at the run's
> commit, and the run recorded no runtime dispatch that confirms it; needs re-admission

`SOLVERS` in `greg/cognition/solvers.py` takes non-literal updates, so a positive operation verdict binds only when
its run recorded the function `SOLVERS` held at runtime (round-2 review of #179, N4;
`greg.cognition.compiler.operation_status`). That rule is unchanged here. The runner did not record a runtime
dispatch; commit `6c4b7712` adds that record to the runner and nothing else. `probabilistic` routes EXPERIMENTAL on
the 2026-10-21 run and is re-measured for replication.

## What is fixed before the run

| Item | Value |
|---|---|
| Run id | `2026-10-22-joined-operations` |
| Runner | `cortex/evaluation/genome_admission/run_operations.py` at `6c4b7712` (unchanged protocol; it now records `solver_closures`, the solver function every candidate call reached, and freezes the expected dispatch in `inputs.solver_closures`) |
| Families | `control`, `game`, `information`, `probabilistic` |
| Held-out seeds | 5920-5949 (n = 30). Inside the window 5100-5999 reserved for this re-admission (`docs/opus-maximus/FOUNDER_INTENT_COVERAGE_MATRIX.md`); 4000-4999 belong to another session, 3000-3999 and 7000 upward are reserved. The runner's `refusals()` returns none for them: development 0-9, P8-reserved 7000-9199, every admission freeze (`spent_seeds()`, none in 5100-5999) and #155's draws (1001-1040, 2001-2040, 3001-3040). The data-exposure ledger records no exposure whose seed ranges meet 5100-5999. A scan of every tracked file at `6c4b7712` (JSON integers and pairs under keys naming seed, held, split, range or train; Python `range(` literals; `seed=` literals; seed/held/split text ranges) found 36 cross-geometry suite items in 5100-5999 (`crossgeo-heldout-v0.2.json`, `crossgeo-heldout-v0.3.json`; highest 5917), so the window starts above them, and one text range, the immune-8 exposure audit's search span 4000-6999, which names no use. The same scan of `wip/p6-joined`, `wip/trackb-join`, `wip/join-168` and the integration branch found nothing else in 5920-5949. |
| Rule (routes) | the canonical genome-admission `RULE`, verbatim in `freeze.json` (`inputs.rule`) |
| #155 rule (does not route) | #155's `status()` on the same rows, recorded per family as `rule_155_status` |
| Generators, arms, geometry | as the 2026-10-21 run: #155's generators and arms verbatim, `GEOMETRY` compute_limit 100000, latency_limit 10.0 |
| Verification | every solver answer behind a candidate output passes `greg.cognition.verification.verify`; a refuted output is scored wrong, below abstaining |
| Statistics | paired one-sided exact sign tests, alpha 0.05, ties within 1e-9; median wall-clock latency |
| Canonical path | one held-out instance per family through `greg.cognition.cortex.reason` in an evaluation-only registry view; a smoke that is not STRUCTURALLY_VERIFIED demotes DEFAULT to NICHE. Nothing is attached on any body |
| Runtime dispatch | per family, the set of `(path, function)` that `SOLVERS[family]` held at each candidate call. Exactly one function is recorded under `solver_closures`; two or none record `null` (no confirmation); a function other than the frozen one is recorded as reached, and the index binds nothing |
| Run | once, from a clean detached worktree at the freeze commit (`/home/user/wt-ops-run`), pinned to one CPU core (`taskset -c 2`), Python 3.11.17 (the 2026-10-21 run used 3.13.16). A crash is recorded, never retried; any repair needs a new run id and new seeds |

## Expectations, stated before the run (not evidence)

- From the 2026-10-21 run on seeds 2600-2629 at the same closures: control 28-2 and 30-0, game 30-0 and 22-0-8,
  information 16-0-14 and 14-0-16, all DEFAULT_FOR_GEOMETRY; probabilistic EXPERIMENTAL (16-11-3, p = 0.22).
- Development seeds 0-9 at `6c4b7712` (`--dev`): control and game DEFAULT; information NICHE_CAPABILITY (4-0-6 against
  always-acquire, p = 0.0625 at n = 10); probabilistic EXPERIMENTAL.
- Any of DEFAULT_FOR_GEOMETRY, NICHE_CAPABILITY, EXPERIMENTAL, SUPERSEDED or REJECTED is an acceptable recorded
  outcome for every family. A non-replication is reported with the same prominence as a replication and is not re-run.

## What the outcome changes, and what it cannot

- A positive verdict with a confirmed runtime dispatch routes the family at the measured solver closure. It attaches
  nothing; attaching is the founder's decision. The arms are #155's, weaker than the genome library's strongest
  competitors (`pid_simopt`, `game_lp_dual`, `bayes_interval`): this is not a strongest-competitor admission.
- EXPERIMENTAL, SUPERSEDED or REJECTED excludes the family from routing until a later re-admission.
- The 2026-10-21 run and every earlier run stay in the index history unchanged.
