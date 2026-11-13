# Section 14 antifragility — pre-registered, run twice — 2026-10-15

Directive section 14 says: "bounded stress, coupled to a verified learning mechanism, produces a subsequent measurable
improvement relative to an appropriate control, after counting stress and repair costs". It also says: "Freeze an
untouched holdout and compare the improved system against its pre-stress version and a no-learning control. ...
Reject improvement caused by test leakage or evaluator weakening."

**The verdict is NO_GAIN, twice.** GREG has not shown antifragility here. The first run did find a real defect, and
the defect is fixed.

## Order of work

1. `PREREGISTRATION.md`, `workload.json` (digest `sha256:03eca9ca…`) and `experiment.py` were committed before any
   holdout run (`12c8eb1`).
2. Run 1, on that commit.
3. The defect run 1 exposed was fixed (`320cbaf`).
4. Run 2: the same frozen workload, verdict rule and tolerances.

No tolerance, seed, threshold or verdict rule was changed after a run. One measurement in the harness changed
between the runs, and it is disclosed under run 1.

## Run 1, before the fix (`run1-before-the-fix.json`)

| Measure | Value |
|---|---|
| Holdout passes PRE / LEARN / CONTROL | 44 / 44 / 44 of 60 |
| Verdict | **NO_GAIN** |
| Stress missions | 12 |
| Settled outcomes | **7, all correct** |
| Stress missions that actually failed | **5** |

**The defect.** Some missions still failed their signed check after every admissible strategy had run. Those
missions were blocked and never appraised, and settlement credits only appraised closures. So the competence
ledger heard only successes. Live negative evidence from real missions could therefore never demote a method. The
demotion rule (#179) could fire only in a test that patched the ledger directly.

**The disclosed harness change.** In run 1 the harness counted damage from settled failures, so its JSON reports
`damage_failed_missions: 0` while 5 of the 12 missions had failed. That zero is the defect itself showing through.
The harness now counts damage from `mission.achieved`, which does not depend on settlement.

## The fix (`320cbaf`; `tests/unit/test_greg_failure_closure.py`)

- **`greg/missions.py`.** When every admissible strategy ran and the signed checks still fail on re-observation,
  the mission records `mission.unmet` (a failure closure), once per `actions_done`. A mission waiting on a
  precondition does not close.
- **`greg/body.py`.** The separate-process appraiser judges failure closures the same way it judges holds.
- **`greg/appraisal.py`.** A failure closure is verified in reverse:
  - every named check must fail on its receipt's bytes;
  - every named check must still fail when the world is re-read;
  - otherwise the verdict is REFUTED, because a forged failure would demote a good method.

  The verdict is `VERIFIED_UNMET`, so nothing that reads `VERIFIED` (precedents, SOPs, track record) mistakes it
  for a success.
- **`greg/cognition/settlement.py`.**
  - Settlement reads `VERIFIED_UNMET` too.
  - A claim's identity is now its signed sensor parameters. A compiled answer's inner request carries a
    budget-dependent latency, so re-observations of one failure had hashed differently and would have settled
    several times.

## Run 2, after the fix (`run2-after-the-fix.json`)

| Measure | Value |
|---|---|
| Holdout passes PRE / LEARN / CONTROL | 44 / 44 / 44 of 60 |
| Verdict | **NO_GAIN** |
| Damage: failed stress missions | 5 of 12 |
| Settled outcomes | 12, 5 of them failures, each settled once |
| Recovery cost (missions until demotion) | never reached |
| Median holdout latency per instance | PRE ≈0.32-0.50 s; LEARN and CONTROL ≈0.50-0.72 s (reading the stressed journal) |
| Strata with fewer passes, or a quality regression over 10× | none |

## Why there was still no gain

Each of the following is a property of the canonical Mind. None was weakened to obtain a result.

1. **The demotion rule needs most outcomes to fail.** It needs at least 10 settled outcomes with a 95% Wilson upper
   bound on correctness below one half. The swarm failed 5 of 12 HIGH-stratum missions; 7 of 12 correct is not a
   demotion.
2. **There was no admissible alternative.** The frozen admission index marks `cognition.blackbox` SUPERSEDED. Even
   a demoted swarm would still have served, which the test
   `test_real_failed_missions_now_demote_the_method_that_failed` shows with 11 real failures.
3. **Competence is not conditioned on scale.** Settled counts are summed per method across strata. The swarm's
   real weakness is the HIGH stratum (2 of 6 on ackley, griewank and rastrigin, against 6, 5 and 6 of 6 at LOW).
   A ledger that does not separate the strata cannot learn it.

These three are the residual `CapabilityDeficit` for section 14 antifragility. Item 3 is the one that would turn
this exact stress into a measurable gain, and it needs its own pre-registration.

## Verification

- `failure-closure-tests.log`: `tests/unit/test_greg_failure_closure.py`, 7 passed.
- `mutants.log`: 61 of 61 caught (`check_cognition_residual_mutants.py`), 6 of them for this change:
  - a failed mission never closes;
  - settlement hears successes only;
  - a re-observed failure settles again;
  - a forged failure is taken on its word;
  - a failure the world no longer shows is accepted;
  - a verified failure reads as a success.
- `full-suite.log`: the full suite on `320cbaf`: 4097 passed, 5 failed, 25 skipped. The five are the environmental Landlock tests; they fail identically at the base here and pass in CI.

## Limits (declared in `PREREGISTRATION.md` before the runs)

- 6 seeds per stratum: counts are reported, not confidence intervals.
- One learning mechanism and two methods.
- Synthetic objectives, with no external outcome.
- The pilot informed the tolerances; the holdout seeds are disjoint from it.

Nothing was sent, spent or activated. Every key is a per-test key. Authority delta: none. A failure closure grants
nothing; it can only lower a method's rank. VEPMC: 0.
