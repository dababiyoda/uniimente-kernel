# `project.crash`: an exact optimality certificate (#217, route A)

**Defect (#217).** GREG's certificate for `project.crash` could call a plan the cheapest when it was not.
- `certify_crash` compared the plan's cost only with the LP objective at the engine's own point.
- That point passed `linear.certify_lp`, whose duality-gap tolerance is relative: `1e-7 × (1 + |primal|)`.
- The crash LP uses absolute start and finish times, so at durations of about 1e8 the tolerance is tens of cost units. A suboptimal vertex therefore passed.

**Fix.** The optimality proof is recomputed from the original project, in exact integers, and no longer rests on the engine's objective.
- **Decode:** `decode_crash` reads the engine's certified LP prices back as a flow from the project's start, along precedences, to the deadline (`_deadline_flow`).
  - The constraint matrix is a network matrix and the costs are integers, so an optimal dual is integral, and each price is rounded.
  - The flow is untrusted at this point.
- **Certify:** `certify_crash` computes, from that flow alone, a lower bound on every on-time plan (`_deadline_bound`). This is Fulkerson's 1961 time-cost duality.
  - Task *i* has normal duration *d*, shortest duration *m*, cost *c* per unit and *t* units of flow through it. The bound is Σ min(*t*·*d*, *t*·*m* + *c*·(*d* − *m*)) − deadline × (total flow).
  - The flow must be nonnegative integers, use only precedence arcs and be conserved at every task.
  - The plan must cost exactly the bound. The docstring of `_deadline_bound` gives the proof that the bound holds for every on-time plan.
- **Encode:** `encode_crash` drops two implied bounds (start ≤ deadline, finish ≥ 0).
  - The duration rows already imply both, so the feasible set is unchanged.
  - Without them, every dual of the program is such a flow. GLOP had placed price on those bounds for zero-duration tasks.
- **Unchanged:** `greg/cognition/linear.py`, which 17 frozen records bind at its current digest. The other reductions' source digests are unchanged too.

## Results

| Check | Before (`917404cf`) | After |
|---|---|---|
| The issue's three points with the optimum's exact prices | all three pass `certify_lp`; costs 15, 30 and 18 all certified | only 15 certified; 30 and 18 refused |
| Probe: suboptimal on-time plans offered with HiGHS's real prices, called cheapest | 0 of 491 (durations +1); 0 of 317 (+1e4); **5 of 387** (+1e6); **242 of 355** (+1e7); **345 of 345** (+1e8) | **0** at every scale |
| Probe: optimal plans refused | 0 | 0 |
| Qualification, 60 seeds (`scripts/qualify_recombine.py`) | 416 engine cases each on SciPy/HiGHS and OR-Tools/GLOP, 0 wrong, 0 refused (2026-10-13 record) | the same: 416 each, 0 wrong, 0 refused; 184 proved without the engine |
| `tests/unit/test_greg_recombine.py` | 13 of this PR's tests fail (`fail-before.txt`) | 39 passed |

- The probe has 40 random projects per scale, each solved once by HiGHS through GREG's own runner (`linear.RUNNERS["scipy.lp"]`). Every other on-time integer plan is then offered with HiGHS's prices, as an engine that drifts to another vertex would offer it.
- Ground truth is exhaustive enumeration (`crash_brute_force`).

## Files

| File | sha256 |
|---|---|
| `false_optimum_probe.py` | `14c3a82e4c31896139a79e231b0ebb957f3a67121c77685a0a28c6f6237420d9` |
| `false-optimum-probe.json` | `de392000dbe9d372a8901b88bd77463cea31b78c333832e74c8fef18ead0ef11` |
| `qualification.json` | `160fc26d8937cce3f2bcf5489b835437f77e6329c3c6fd6a544b66489831e4e7` |
| `fail-before.txt` | `4b90bdbe3f89047365c33ace579eaaa20126c9dac2bc61fdf9254adedc54712e` |

**To reproduce:**

```
git show 917404cf:greg/recombine.py > /tmp/recombine-before.py
python docs/evidence/greg-crash-certificate/2026-10-28/false_optimum_probe.py /tmp/recombine-before.py out.json
python scripts/qualify_recombine.py out-qualification.json 60
```

**Environment:** Python 3.11.17 on Linux x86_64; SciPy 1.17.1, OR-Tools 9.15.6755, NetworkX 3.6.1, NumPy 2.4.6. `crash-via-lp` source digest `19d253c7…`; it was `c7a0db1c…` on 2026-10-13.

## Limits

- **Availability:** at durations near 1e8, GLOP's floating-point plan can finish a task one unit short. GREG's exact plan check refused that before this change and still does.
  - `test_the_real_lp_engines_prices_round_to_an_exact_certificate` allows only this refusal, and no refusal by the flow certificate.
  - The LP engine accepts coefficients up to 1e9, so durations above that never reach an engine.
- **Formed constructions:** `project.crash` constructions formed before this change quarantine on restart, because the reduction's source digest changed. They re-qualify through the frozen oracle.
- **Recorded answers:** a crash answer recorded before this change carries no deadline flow, so the new certifier cannot re-certify it. #213's `recertify` helper re-certifies recorded crash answers and needs a matching change when both are joined.
- **No real projects:** synthetic projects only; no founder project was run. VEPMC 0.
