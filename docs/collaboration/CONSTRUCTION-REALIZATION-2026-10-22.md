# A construction's answer can settle as wrong in the world — 2026-10-22

Branch `wip/construction-realization` (base `32196c39`). Prerequisite for a positive construction dividend; no
dividend is claimed here. Authority delta: none.

## Gap

Capability Genesis constructions (`greg/recombine.py`: `selection.closure`, `selection.budgeted`,
`assignment.staffing`, `assignment.matching`, `project.crash`) answer with a certificate that re-proves the answer
from the declared inputs. Their settled outcome (`settlement.measured_outcomes`, construction branch) was therefore
always correct, so settled competence, the inhibition rule and the Fisher choice between eligible fits
(`compiler._settled_preference`) could never move away from a construction. Realized outcomes existed only for
forecasts.

## Mechanism (existing paths, no second ledger)

- `REALIZATION` (signed founder command, `greg/body.py`) -> `settlement.record_realization`. On a retained,
  certified, Genesis-registered construction answer (`settlement._constructed`) it now takes one finite number: the
  realized value of the objective the answer promised. `settlement.OBJECTIVES` names that objective per function
  (`profit` max, `staffed` max, `size` max, `cost` min; an impossible-deadline answer promises nothing and is refused).
- The fact is a `cognition.realization` event with `kind: "objective"`, keyed once by the ledger receipt. A repeat of
  the same value returns the kept fact; a different value is recorded beside it with `conflicts_with`, and that claim
  is then scored as neither (removed from competence; `reconcile` invalidates its settlement, history retained).
- `measured_outcomes` binds the realization to the construction outcome whose observation named that receipt (any
  re-observation of the same signed claim), checks the fact's promise against the answer it was bound to, and sets
  `correct = certificate passed AND world kept the promise`. Both stay on the record: `certificate_correct` and a
  `world` block (promised, realized, tolerance, met, source, realization events). `reconcile` writes the revision as
  usual; the earlier certificate-only settlement event is kept and superseded.
- The compiler is unchanged: `_settled_counts`, `_settled_inhibition` and `_settled_preference` (one-sided Fisher,
  Holm, n >= 10 on both sides) read the revised competence.

## Rule (declared, not tuned)

Wrong in the world: the realized objective is worse than promised by more than
`REALIZATION_RELATIVE_TOLERANCE x max(|promised|, 1)` with the constant 0.05, below the promise for a maximum,
above it for a minimum. Doing better is not a failure. The tolerance is a code constant, recomputed by the
projection, never supplied by the realization. A per-mission declared tolerance is not built: the mission schema
is `additionalProperties: false` and that change was out of scope.

What it means: evidence about the method on that geometry (pooled per method, as `_settled_counts` already pools).
What it does not mean: that the certificate was false. A certificate proves the answer given the declared inputs;
the world can disagree because the inputs did not describe it. A realization creates no authority and changes no
mission or capability state.

## Tests (`tests/unit/test_greg_construction_realization.py`; all four fail on `32196c39`)

1. Short of the promise by more than tolerance settles wrong; within tolerance settles correct; reconcile keeps both
   facts and is replay-safe.
2. A repeat is idempotent; a different value is a conflict scored as neither.
3. Refused on an unknown receipt, on an unanswered (CAPABILITY_DEFICIT) compile receipt, on non-numeric values
   (`"2"`, `True`, NaN, inf, `[2]`, `None`) and on an unknown source.
4. End to end on a real body: `cognition.flow_maxflow` answers 10 network missions (10/10), the constructed
   `selection.closure` answers 10 portfolio missions, 6 of whose realizations fall short. A compile on a request
   carrying both shapes' inputs then chooses `flow_maxflow` by the Fisher rule (construction 4/10 vs 10/10, Holm p
   < 0.05; inhibition does not act at 4/10), and a signed mission follows it. **Ablation** (realization projection
   disabled): the construction stands at 10/10 and keeps the choice.

## Limits

- The realized values in the tests are synthetic test inputs, not real-world outcomes.
- The end-to-end test fixes frozen evidence (`flow_maxflow` read as EXPERIMENTAL) so the construction ranks first,
  and makes two fits eligible by joining two shapes' inputs in one request. It tests the routing mechanism, not a
  natural competition between methods on one geometry.
- Only construction answers take objective realizations; catalogued optimisation receipts (e.g. `flow_maxflow`'s
  `flow_value`) do not yet. `awaiting_realization` still lists forecasts only.
- No positive dividend is claimed until a pre-registered run on real realized data.
