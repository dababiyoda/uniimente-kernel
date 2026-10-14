"""Graph geometry through founder-attached formed functions (issue #117, PR #143 handoff).

The cortex-dialect payload key ``graph`` names a graph problem:

    {"kind": "shortest_path", "edges": [[u, v, w], ...], "directed"?: bool,
     "source": node, "target"?: node}
    {"kind": "max_flow", "edges": [[u, v, capacity], ...], "source": node, "sink": node}

The organ recruits the formed GREG function (``graph.shortest_path`` /
``graph.max_flow``) that Capability Genesis qualified and the founder attached. The
engine behind it (an installed open-source package, digest re-pinned before every call)
is never trusted: an answer is accepted only on GREG's own certificate — feasible
potentials realised by predecessor chains for shortest paths, conservation plus no
residual path plus an equal-capacity cut for maximum flow — which shares no code with
the engine.

Truthful negatives: a missing, detached or changed package is DEPENDENCY_UNAVAILABLE
(the body maps it to the genesis trigger, CAPABILITY_DEFICIT); a certificate failure is
INCONCLUSIVE with the claim withheld; a request outside the function's competence
envelope (negative weights, size caps) is MALFORMED_INPUT naming the exact reason.
"""
from __future__ import annotations

import time
from typing import Any, Mapping

from ..contracts import Expenditure, OrganResult
from .formed import FormedFunctionError, fail, formed_failure, proof_for

ORGAN_ID = "cortex.graph.search@0.2.0"
VERSION = "0.2.0"
FUNCTIONS = {"shortest_path": "graph.shortest_path", "max_flow": "graph.max_flow"}
_FALSIFICATION = {
    "shortest_path": "a path from the source to some node shorter than its certified distance, a node "
                     "claimed unreachable that an input edge reaches, or a predecessor edge absent from "
                     "the input",
    "max_flow": "an augmenting path in the residual graph, a source-sink cut with capacity below the "
                "certified value, or a flow violating capacity or conservation",
}


class GraphSearchOrgan:
    """One graph problem in, one certified answer out — or a truthful negative."""

    organ_id = ORGAN_ID
    version = VERSION

    def __init__(self, formed: Mapping[str, tuple] | None = None):
        # function -> (callable | None, why_if_none); see cortex/organs/formed.py
        self.formed = dict(formed or {})

    def run(self, problem, geometry, budget) -> OrganResult:
        started = time.perf_counter()
        graph = problem.payload.get("graph")
        if not isinstance(graph, Mapping):
            return fail(ORGAN_ID, VERSION, "INSUFFICIENT_EVIDENCE", "no structured graph supplied", started)
        kind = graph.get("kind")
        if kind not in FUNCTIONS:
            return fail(ORGAN_ID, VERSION, "MALFORMED_INPUT",
                        f"graph.kind must be one of {sorted(FUNCTIONS)}", started)
        function = FUNCTIONS[kind]
        call, why = self.formed.get(function, (None, "no attached formed function"))
        dependencies = (f"formed:{function}",)
        if call is None:
            return fail(ORGAN_ID, VERSION, "DEPENDENCY_UNAVAILABLE",
                        f"{function}: {why}; Capability Genesis can form it from an installed package and "
                        f"the founder can attach it", started, function=function)
        params = {k: v for k, v in graph.items() if k != "kind"}
        cpu = max(1, min(20, int(getattr(budget, "max_latency_s", 20) or 20)))
        try:
            out = call(params, cpu)
        except FormedFunctionError as exc:
            return formed_failure(ORGAN_ID, VERSION, exc, started, function=function,
                                  dependencies=dependencies)
        answer, calls = out["answer"], out["solver_calls"]
        mechanism = answer.pop("_mechanism")
        dependencies = (f"formed:{function}",
                        f"package:{mechanism['distribution']}=={mechanism['version']}")
        if not answer.get("certified"):
            # A negative claim GREG could not prove (e.g. too large for follow-up solves): withheld.
            why = answer.get("why", "the engine's claim is unproven")
            proof = proof_for(function, answer, mechanism, _FALSIFICATION[kind],
                              mechanism.get("request_shape", {}))
            proof["engine_claim"] = {"status": answer.get("status"), "why": why,
                                     "label": "unproven; not asserted by this organ"}
            return OrganResult(
                organ_id=ORGAN_ID, organ_version=VERSION, state="INCONCLUSIVE", answer=None, proof=proof,
                uncertainty="no certified result", notes=(f"claim withheld: {why}",),
                expenditure=Expenditure(seconds=time.perf_counter() - started, solver_calls=calls),
                dependencies=dependencies, origin="solver")
        answer = {"kind": kind, **answer}
        proof = proof_for(function, answer, mechanism, _FALSIFICATION[kind],
                          mechanism.get("request_shape", {}))
        return OrganResult(
            organ_id=ORGAN_ID, organ_version=VERSION, state="OK", answer=answer, proof=proof,
            assumptions=(),
            uncertainty="exact given the input; the certificate is GREG's own exact arithmetic and shares "
                        "no code with the engine",
            expenditure=Expenditure(seconds=time.perf_counter() - started, solver_calls=calls),
            dependencies=dependencies, origin="solver")
