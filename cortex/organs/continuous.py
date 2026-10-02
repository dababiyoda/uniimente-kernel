"""Continuous linear optimization through the founder-attached formed ``lp.optimize``.

The cortex-dialect payload key ``linear_program`` names a linear program in the same
shape Capability Genesis formed:

    {"variables": [{"name": str, "lower"?: num|null, "upper"?: num|null}, ...],
     "objective": {"sense": "min"|"max", "coefficients": {name: num}},
     "constraints": [{"op": "<="|">="|"==", "coefficients": {name: num}, "rhs": num,
                      "name"?: str}, ...]}

The organ recruits the formed GREG function ``lp.optimize`` (HiGHS via SciPy or GLOP via
OR-Tools, digest re-pinned before every call). The engine is never trusted: an optimum
is accepted only with primal feasibility, dual feasibility and zero duality gap, checked
by GREG in exact fractions; an engine's "infeasible"/"unbounded" is decided by GREG's
own follow-up solves (elastic program, ray) or withheld when the program is too large
to prove. This complements the CP-SAT organ, whose fragment is integer-only.

Truthful negatives mirror the graph organ: DEPENDENCY_UNAVAILABLE for a missing,
detached or changed package (the body's genesis trigger), INCONCLUSIVE with the claim
withheld on a certificate failure, MALFORMED_INPUT naming the exact reason for a
request outside the competence envelope.
"""
from __future__ import annotations

import time
from typing import Mapping

from ..contracts import Expenditure, OrganResult
from .formed import FormedFunctionError, fail, formed_failure, proof_for

ORGAN_ID = "cortex.optimization.continuous@0.1.0"
VERSION = "0.1.0"
FUNCTION = "lp.optimize"
_FALSIFICATION = ("a feasible point with objective beyond the dual bound, multipliers that fail "
                  "stationarity or sign, or a certified infeasible program for which a point meets "
                  "every limit")


class ContinuousOptimizationOrgan:
    """One linear program in, one duality-certified answer out — or a truthful negative."""

    organ_id = ORGAN_ID
    version = VERSION

    def __init__(self, formed: Mapping[str, tuple] | None = None):
        # function -> (callable | None, why_if_none); see cortex/organs/formed.py
        self.formed = dict(formed or {})

    def run(self, problem, geometry, budget) -> OrganResult:
        started = time.perf_counter()
        program = problem.payload.get("linear_program")
        if not isinstance(program, Mapping):
            return fail(ORGAN_ID, VERSION, "INSUFFICIENT_EVIDENCE",
                        "no structured linear program supplied", started)
        call, why = self.formed.get(FUNCTION, (None, "no attached formed function"))
        dependencies = (f"formed:{FUNCTION}",)
        if call is None:
            return fail(ORGAN_ID, VERSION, "DEPENDENCY_UNAVAILABLE",
                        f"{FUNCTION}: {why}; Capability Genesis can form it from an installed package and "
                        f"the founder can attach it", started, function=FUNCTION)
        cpu = max(1, min(20, int(getattr(budget, "max_latency_s", 20) or 20)))
        try:
            out = call(dict(program), cpu)
        except FormedFunctionError as exc:
            return formed_failure(ORGAN_ID, VERSION, exc, started, function=FUNCTION,
                                  dependencies=dependencies)
        answer, calls = out["answer"], out["solver_calls"]
        mechanism = answer.pop("_mechanism")
        dependencies = (f"formed:{FUNCTION}",
                        f"package:{mechanism['distribution']}=={mechanism['version']}")
        if not answer.get("certified"):
            # The engine reported infeasible/unbounded and GREG could not prove it here: withheld.
            why = answer.get("why", "the engine's claim is unproven")
            proof = proof_for(FUNCTION, answer, mechanism, _FALSIFICATION,
                              mechanism.get("request_shape", {}))
            proof["engine_claim"] = {"status": answer.get("status"), "why": why,
                                     "label": "unproven; not asserted by this organ"}
            return OrganResult(
                organ_id=ORGAN_ID, organ_version=VERSION, state="INCONCLUSIVE", answer=None, proof=proof,
                uncertainty="no certified result", notes=(f"claim withheld: {why}",),
                expenditure=Expenditure(seconds=time.perf_counter() - started, solver_calls=calls),
                dependencies=dependencies, origin="solver")
        answer = {"kind": "linear_program", **answer}
        proof = proof_for(FUNCTION, answer, mechanism, _FALSIFICATION,
                          mechanism.get("request_shape", {}))
        return OrganResult(
            organ_id=ORGAN_ID, organ_version=VERSION, state="OK", answer=answer, proof=proof,
            assumptions=(),
            uncertainty="exact given the input; optimality rests on a duality certificate GREG checks in "
                        "exact arithmetic, sharing no code with the engine",
            expenditure=Expenditure(seconds=time.perf_counter() - started, solver_calls=calls),
            dependencies=dependencies, origin="solver")
