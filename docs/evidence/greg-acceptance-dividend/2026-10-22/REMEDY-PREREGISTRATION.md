# R1-A floor 4 remedy: pre-registration (written before any implementation)

Parent: `PREREGISTRATION.md` (commit `57b5c17`), whose floor 4 (appraisal wall time on the honest one_machine path
at most +10%) FAILED on `8a1051b` (+137.1% required, +128.4% supervised; README "Floor 4 failed"). The README names
one candidate remedy, not built: start the discrimination (base) run concurrently with the acceptance run, so an
appraisal waits about max(acceptance, base) instead of their sum. This file fixes how that remedy is judged before it
exists. Nothing in the parent pre-registration is changed or re-scored.

## Hypothesis

H-R: running the base run concurrently with the acceptance run lowers appraisal wall time on O1 without changing any
verdict, any finding class or the number of test executions per appraisal.

## Mechanism constraints (a remedy that breaks one is not the remedy)

1. Both processes start and are supervised from one thread (no `fork` from a second thread, no `preexec_fn` in a
   thread): a non-blocking start, then one supervision loop over both.
2. Each process keeps its own confinement exactly as today: envelope, or under `supervised` Landlock confined to its
   own tree; neither can write the other's tree; the confinement records are unchanged.
3. The base run's bound is unchanged: `fails_on_base` = min(order timeout, 10 + 4 x acceptance seconds), enforced once
   the acceptance run has finished; `passes_on_base` = the order timeout. STOP, timeouts and the output ceiling apply to
   both; a killed process leaves no descendants (process-group kill, as today).
4. A base run whose result is not used (the acceptance failed, or a bound-artifact or re-derivation check refused) is
   killed and recorded as not judged; it never decides a verdict. The base run still starts only for a patch that
   scope and the evaluator freeze have not refused.
5. Floor 3 stays: at most one extra test execution per appraisal.

## Measurement (identical to parent floor 4)

`run_evaluation.py --timing`: case O1, median of 5 `worker.appraise` calls, regimes `required` and `supervised`, run
back to back on this host (4 CPUs) against the baseline tree `5d54c96` in the same session. Primary metric: median
appraisal wall time, new vs baseline, percent. Also reported: absolute seconds, and the same against `8a1051b`/the
pre-remedy head (sequential design) so the remedy's own effect is visible.

## Equivalence check

The full hostile and honest matrix (`run_evaluation.py`, all cases, both regimes) on the remedy tree must give the
same verdicts and the same per-appraisal execution counts as `rows-new.json`, case by case. Any difference is
reported as a failure of the remedy, not re-scored.

## Decision rule

- Floor 4 is judged exactly as pre-registered: at most +10% vs baseline. If it still fails, it is reported FAILED with
  the new numbers; the remedy is kept only if it lowers wall time and passes the equivalence check and constraints.
- If the remedy fails the equivalence check or any constraint, it is reverted (history kept) and recorded as a
  negative result.
- Inference about larger suites or other hosts is labelled inference.
