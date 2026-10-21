# P8 second-target survey (step E, 2026-10-21)

**Scope.** The founder directive asks for a second target among the "already available, properly licensed targets", chosen "by relevance to GREG's actual capability deficits, evaluability, and information value — not by which target seems easiest to pass." Nothing here was built or run; the survey is independent of the immune-8 pilot's outcome.

## What P8 needs from a target

Each target needs:

- a genome method that runs from a configuration (`solve_with(config, data)`) and a sandbox entry (`evolution_sandbox.TARGETS`);
- a **closed declared configuration space** of method parameters only. Score, tolerance and penalty constants are evaluation state and are refused (`evolution.PROTECTED`);
- a verifier that accepts any configuration in that space;
- a simple trigger baseline, a sealed score and stress derivations;
- a generator or dataset whose licence is clear in the repository, with fresh, unexposed instances.

## Data licences

The bundled natural datasets are not cleared for this use, so they are excluded:

- M4 weekly series (`forecast_quantile`);
- fpp3 `bank_calls`;
- NYC 2015 pickups;
- SNDlib networks.

Their rights are a founder decision under the directive. What remains is the repository's own synthetic generators, which carry no third-party data.

## Every candidate

The deficit column is the latest admission verdict against the declared competitor (`scripts/mind_status.py`, admission records v1-v4).

| # | Target (layer) | Deficit | Configurable now? | Wrong answers in the loss | Evaluability | Information value |
|---|---|---|---|---|---|---|
| 1 | **`develop_repair`** (L4 developmental repair) | NICHE. Loses **7-23** to the adaptive centralized replanner (v2) and 12-18 in v1. Developmental repair and recovery is a named section-4 layer obligation | No. Protocol parameters `WAVE_PERIOD`, `EXPIRY_WAVES`, `REPEATS` and `RETRACT_REPEATS` are module constants, echoed into the certificate. `repair_verify` checks the outcome (pointers, claims, trace), not these constants, so it already accepts any setting | **Finite**: a false restoration claim scores quality - 1.5. The +inf failure that blocks immune does not arise | Synthetic generator (`repair_instance`), exact score and verifier. Stress derivations come naturally: higher message loss, crash or stale controllers | **High.** A different layer (L4). Finite losses test whether the frozen rule can retain a gain when wrong answers are rankable. It also targets a measured loss to a competitor |
| 2 | **`basal_breaker`** (L1 reliability control) | NICHE. Ties the consecutive-failure breaker **16-14** (v1) | No. `CB_WINDOW` and `CB_ALPHA` are constants checked by `breaker_verify` | Finite: a wrong answer is one unit below the fallback | Cheap synthetic generator, exact cost | **Medium-high.** It strengthens the Spider-Web reliability/recovery control point. The near-tie leaves the headroom uncertain, which is itself informative |
| 3 | **`immune_detect` on its native regimes** (L2) | NICHE. The genome's real niche is the multimodal, annular and non-convex regimes (11-5, 16-0 and 14-2 against 5-NN in the builder measurement). On the Gaussian regime P8 uses, it lost **5-25** to Hotelling (v1) | Yes (the immune space), but P8 draws only Gaussian instances (`immune_split`) | **+inf**: the same structural blocker as immune-7 and immune-8 | Synthetic generators exist (7_410_000-7_430_000 streams) and are unexposed beyond the admission seeds | **Medium.** More relevant than the Gaussian target, which evolves a detector on the one regime where a textbook method dominates it. The same rule blocker applies |
| 4 | `collective_physarum` (L2) | NICHE. Loses 8-16 to the multi-start Steiner heuristics (v3) | No | Finite (abstain floor) | Exact objective, synthetic | Medium: section-31 item 8 (collective competence) |
| 5 | `basal_hysteresis` (L1) | NICHE. Loses 1-11 to the Wonham HMM filter | No (`HY_MAX_CONFIRM`) | Finite | Cheap | Low-medium. The admitted `basal_bayes_filter` already covers this geometry better |
| 6 | `collective_quorum` (L2) | NICHE. 4-2 with 24 ties against the competitor | No | Finite | Cheap | Low: little measured headroom |
| 7 | `constraint_release` (L4), a second cycle | Cycle 6 RETAINed (not adopted). Random restart is at least as good (80-89) | Yes (existing target) | Finite | Proven harness | It replicates the same target. It is **not** a second target, and it would test the cycle-6 proposal's region again |
| 8 | `forecast_quantile` (L3) | DEFAULT | Yes | Finite | **Excluded:** 0 unused M4 series, and M4 rights are uncleared | n/a |
| 9 | `collective_flock`, `basal_pid` | SUPERSEDED: flock 0-30 (v1) and 0-29 (v3); PID 0-30 (v2) | No | Finite | Cheap | Low. The gap is algorithmic (a centralized planner; a simulation-optimised PI), not a parameter setting |

## Ranking

The ranking orders relevance first, then information value, then evaluability:

1. `develop_repair`
2. `basal_breaker`
3. immune native regimes
4. `collective_physarum`
5. `basal_hysteresis`
6. `collective_quorum`

`constraint_release` is listed only as a replication. `forecast_quantile` is excluded.

## Recommendation

**Build `develop_repair` as P8's second target, in its own design lane, with its own declared pilot.**

**Why it ranks first:**

- It is a measured capability deficit on a layer the founder named: repair, recovery and structural adaptation under a preserved target.
- Its losses are finite, so the frozen RULE can rank wrong answers. A pass or fail there will say something about the search and the rule, rather than repeating immune's lesson that a single infinite loss decides everything.
- Its generator is the repository's own.

**The residual work before any pilot,** in this order. Each step needs tests and nothing is run on fresh seeds before its declaration:

1. **A configuration hook.** Add `repair_solve_with(config, data)`, with the incumbent equal to today's constants, byte-identical on the development seeds.
2. **Keep the verifier outcome-based.** `repair_verify` checks the outcome, not the constants. Add a test that it accepts every configuration in the declared space and still refutes false claims.
3. **A declared space of protocol parameters only.** `ACTION_COST`, `WRONG_PENALTY` and `MAX_LOSS` are evaluation state and stay outside it.
4. **Target wiring.** Add a sandbox entry, a trigger baseline (`repair_no_repair` or the replanner), and stress derivations (higher message loss; crash or stale controllers).
5. **A genome version bump and a pin in `EVOLVABLE_CONFIG_PINS`.**
6. **A data-exposure audit** of `repair_instance` seeds across both lineages, like `EXPOSURE-AUDIT.md`.

**What not to do:**

- Do not pick `basal_breaker` merely because a 16-14 tie looks easy to beat.
- Do not move immune to its native regimes until the founder decides whether `RULE` should count wrong answers separately (immune-7 option 4). Under the current rule every immune design inherits the +inf blocker.
