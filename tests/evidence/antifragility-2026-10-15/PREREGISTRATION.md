# Antifragility experiment — pre-registered before any holdout run (directive section 14)

Section 14: "Antifragility: bounded stress, coupled to a verified learning mechanism, produces a subsequent
measurable improvement relative to an appropriate control, after counting stress and repair costs ... Use bounded
sandbox disturbances to test antifragility. Freeze an untouched holdout and compare the improved system against its
pre-stress version and a no-learning control. Count damage, recovery costs, latency, and regressions. Reject
improvement caused by test leakage or evaluator weakening."

This file, the frozen workload (`workload.json`) and the harness (`experiment.py`) are committed before the holdout
is run. A rule is never changed after a run; a miss is recorded as a miss.

## The mechanism under test

The learning mechanism is the converged Mind's **live negative evidence**:
- Settled outcomes of signed missions, appraised VERIFIED (`greg.cognition.settlement.measured_outcomes`), are
  counted per method.
- With at least 10 settled outcomes whose 95% Wilson upper bound on correctness is below one half, the compiler
  demotes the method: it is ranked after every other fit, never deleted (`compiler._settled_inhibition`, #179).

Nothing else in the routing path learns from these missions.

## The workload

- **Two real black-box minimisers** fit the same request: `cognition.swarm` (particle swarm, the default) and
  `cognition.blackbox` (SciPy differential evolution). The founder attaches both.
- **The objectives:** sphere, ackley, griewank, rosenbrock and rastrigin, with bounds [-5.12, 5.12] and the optimum
  shifted by U(-2, 2) per seed.
- **Two strata of scale:**
  - LOW: 10 dimensions, budget 5,000 evaluations;
  - HIGH: 20 dimensions, budget 10,000.
- **A pilot (seeds 0-5, disclosed)** found that the swarm is much better at LOW (sphere ≈3e-11 against ≈1e-3) and
  much worse at HIGH on four of the five functions (sphere ≈15 against ≈0.15). It is a natural latent weakness,
  not an injected fault. The pilot informed the tolerances below.
- **Success is `fitness ≤ τ`,** read from the receipt. GREG's verifier recomputes the objective independently.

  | Function | τ |
  |---|---|
  | sphere | 0.5 |
  | ackley | 2.0 |
  | griewank | 0.3 |
  | rosenbrock | 200 |
  | rastrigin | 60 |

  The same τ applies in both strata.

## The arms

- **Stress (a bounded sandbox disturbance):** 12 HIGH-stratum signed missions (seeds 500-511, cycling the five
  functions) run on one body. Their outcomes settle through the real path.
- **Holdout:** seeds 1000-1005 × 5 functions × 2 strata = 60 instances, disjoint from the pilot and the stress. They
  are evaluated by direct compile calls, so holdout outcomes never feed learning, under three arms:
  1. **PRE:** the pre-stress system (no settled outcomes);
  2. **LEARN:** the post-stress system (the stress body's settled outcomes);
  3. **CONTROL:** no learning (the same stressed history, with inhibition disabled).

## Measured

Per stratum (scale × function):
- passes;
- the median fitness;
- the median wall time;
- the method selected.

Also measured:
- **damage:** failed stress missions;
- **recovery cost:** the stress missions settled before the demotion takes effect.

## Verdict rule (fixed now)

**ANTIFRAGILE_EVIDENCE** only if every one of these holds:
1. LEARN passes more holdout instances than PRE and than CONTROL;
2. no stratum passes fewer under LEARN than under PRE;
3. no stratum's median fitness under LEARN is more than 10 times its PRE median.

The stress damage and recovery cost are reported beside the verdict.

The other verdicts:
- **IMPROVED_WITH_REGRESSION:** the aggregate improves, but a stratum regresses. That is learning and recovery,
  not antifragility.
- **NO_GAIN:** the aggregate does not improve.

## Limits declared now

- **Size:** 6 seeds per stratum, so counts are reported, not confidence intervals.
- **Scope:** one learning mechanism and two methods.
- **Source of the instances:** synthetic objectives, with no external outcome.
- **The pilot:** it informed the tolerances; the holdout seeds are disjoint from it.
