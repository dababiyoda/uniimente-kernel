"""Cortex <-> Capability Genesis routing (issue #117, PR #143 handoff).

``graph`` and ``linear_program`` payloads route through the cortex's one entry
(``cognition.solve`` with a cortex problem) to organs that recruit founder-attached
formed functions. The engines behind those functions (installed open-source packages)
are never trusted: every answer carries a GREG certificate sharing no code with the
engine; a lying engine is withheld (INCONCLUSIVE, no claim); a detached or changed
package is a truthful DEPENDENCY_UNAVAILABLE, which the body maps to the genesis
trigger (CAPABILITY_DEFICIT). Founder detach is respected at both layers: the organ's
GREG manifest (cortex eligibility) and the formed function's own attach state.
"""
import hashlib

import pytest

pytest.importorskip("z3")

from cortex.contracts import digest as cortex_digest  # noqa: E402
from cortex.genome import seed_registry  # noqa: E402
from cortex.organs import formed as formed_mod  # noqa: E402
from cortex.organs.continuous import ContinuousOptimizationOrgan  # noqa: E402
from cortex.organs.graphsearch import ORGAN_ID as GRAPH_ORGAN, GraphSearchOrgan  # noqa: E402
from cortex.organs.continuous import ORGAN_ID as CONOPT_ORGAN  # noqa: E402
from cortex.routing import Cortex  # noqa: E402
from cortex.schemas import validate  # noqa: E402
from greg.capabilities import CapabilityManifest  # noqa: E402
from greg.cognition import bridge  # noqa: E402

DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}

GRAPH_PROBLEM = {"problem_id": "t:graph", "question": "shortest path A to C",
                 "payload": {"declared": DECL,
                             "graph": {"kind": "shortest_path", "source": "A", "target": "C",
                                       "edges": [["A", "B", 1], ["B", "C", 2], ["A", "C", 5]]}}}
FLOW_PROBLEM = {"problem_id": "t:flow", "question": "max flow s to t",
                "payload": {"declared": DECL,
                            "graph": {"kind": "max_flow", "source": "s", "sink": "t",
                                      "edges": [["s", "a", 3], ["a", "t", 2], ["s", "t", 1]]}}}
LP_PROBLEM = {"problem_id": "t:lp", "question": "minimize cost",
              "payload": {"declared": DECL,
                          "linear_program": {
                              "variables": [{"name": "x", "lower": 0}, {"name": "y", "lower": 0}],
                              "objective": {"sense": "min", "coefficients": {"x": 1, "y": 2}},
                              "constraints": [{"op": ">=", "coefficients": {"x": 1, "y": 1}, "rhs": 4,
                                               "name": "demand"}]}}}

MECH = {"capability_id": "acquired.graph.shortest_path.networkx", "distribution": "networkx",
        "version": "3.6.1", "license": "BSD-3-Clause", "runner": "networkx.shortest_path",
        "package_digest": "sha256:0" * 1, "request_sha256": "sha256:1", "request_shape": {"nodes": 3, "edges": 3}}
LP_MECH = {**MECH, "capability_id": "acquired.lp.optimize.scipy", "distribution": "scipy",
           "version": "1.17.1", "license": "BSD-3-Clause", "runner": "scipy.lp",
           "request_shape": {"variables": 2, "constraints": 1}}


def shortest_answer():
    return {"certified": True, "source": "A", "target": "C", "reachable": True, "distance": 3,
            "path": ["A", "B", "C"], "distances": {"A": 0, "B": 1, "C": 3}, "unreachable": [],
            "certificate": {"kind": "feasible potentials realised by predecessor chains",
                            "arithmetic": "exact fractions"},
            "engine": "networkx 3.6.1", "license": "BSD-3-Clause", "authority_created": False,
            "_mechanism": dict(MECH)}


def lp_answer():
    return {"certified": True, "status": "optimal", "sense": "min", "objective": 4.0,
            "values": {"x": 4.0, "y": 0.0}, "binding": ["demand"], "shadow_prices": {"demand": 1.0},
            "certificate": {"kind": "primal and dual feasibility with zero duality gap", "gap": 0.0,
                            "tolerance": "relative 1e-7 (engine floating point)",
                            "arithmetic": "exact fractions"},
            "engine": "scipy 1.17.1", "license": "BSD-3-Clause", "authority_created": False,
            "_mechanism": dict(LP_MECH)}


def stub(answer, calls=1, recorder=None):
    def call(params, cpu_seconds):
        if recorder is not None:
            recorder.append((params, cpu_seconds))
        return {"answer": answer(), "solver_calls": calls}
    return call


def cortex_with(organ_key, organ):
    cortex = Cortex()
    cortex.organs[organ_key] = organ
    return cortex


# ------------------------------------------------------------------ routing
class TestRouting:
    def test_graph_payload_routes_to_the_graph_organ(self):
        cortex = cortex_with(GRAPH_ORGAN, GraphSearchOrgan({"graph.shortest_path": (stub(shortest_answer), None)}))
        receipt = cortex.run(GRAPH_PROBLEM)
        assert receipt["route"]["selected"] == [GRAPH_ORGAN]
        assert receipt["output"]["state"] == "OK"
        assert receipt["disposition"]["kind"] == "recommend"
        answer = receipt["output"]["answer"]
        assert answer["certified"] is True and answer["distance"] == 3 and answer["path"] == ["A", "B", "C"]
        proof = receipt["proof_artifacts"][0]
        assert proof["proof_class"] == "optimization"
        assert proof["formed_capability"] == "acquired.graph.shortest_path.networkx"
        assert proof["engine"]["distribution"] == "networkx" and proof["engine"]["version"] == "3.6.1"
        assert proof["certificate"]["kind"].startswith("feasible potentials")
        assert "_mechanism" not in answer and "package_digest" not in answer
        validate(receipt, "cortex-receipt")

    def test_linear_program_payload_routes_to_the_continuous_organ(self):
        cortex = cortex_with(CONOPT_ORGAN, ContinuousOptimizationOrgan({"lp.optimize": (stub(lp_answer), None)}))
        receipt = cortex.run(LP_PROBLEM)
        assert receipt["route"]["selected"] == [CONOPT_ORGAN]
        assert receipt["output"]["state"] == "OK"
        answer = receipt["output"]["answer"]
        assert answer["status"] == "optimal" and answer["objective"] == 4.0
        assert answer["shadow_prices"] == {"demand": 1.0}
        assert receipt["proof_artifacts"][0]["certificate"]["kind"].startswith("primal and dual")
        validate(receipt, "cortex-receipt")

    def test_geometry_is_optimization_with_exactness_required(self):
        cortex = cortex_with(GRAPH_ORGAN, GraphSearchOrgan({"graph.shortest_path": (stub(shortest_answer), None)}))
        geometry = cortex.run(GRAPH_PROBLEM)["geometry"]
        assert geometry["epistemic_class"] == "optimization"
        assert geometry["exactness"] == "exact_required"

    def test_both_optimization_payloads_compose(self):
        cortex = cortex_with(GRAPH_ORGAN, GraphSearchOrgan({"graph.shortest_path": (stub(shortest_answer), None)}))
        cortex.organs[CONOPT_ORGAN] = ContinuousOptimizationOrgan({"lp.optimize": (stub(lp_answer), None)})
        problem = {"problem_id": "t:both", "question": "route and allocate",
                   "payload": {"declared": DECL, "graph": GRAPH_PROBLEM["payload"]["graph"],
                               "linear_program": LP_PROBLEM["payload"]["linear_program"]}}
        receipt = cortex.run(problem)
        assert sorted(receipt["route"]["selected"]) == sorted([GRAPH_ORGAN, CONOPT_ORGAN])
        assert receipt["route"]["composition"] is True
        assert receipt["output"]["state"] == "OK"
        validate(receipt, "cortex-receipt")

    def test_solver_call_budget_zero_refuses_before_spending(self):
        calls = []
        cortex = cortex_with(GRAPH_ORGAN,
                             GraphSearchOrgan({"graph.shortest_path": (stub(shortest_answer, recorder=calls), None)}))
        problem = {"problem_id": "t:budget", "question": "q",
                   "payload": {"declared": DECL, "graph": GRAPH_PROBLEM["payload"]["graph"],
                               "resources": {"max_solver_calls": 0}}}
        receipt = cortex.run(problem)
        assert receipt["output"]["state"] == "BUDGET_EXHAUSTED"
        assert calls == [], "the engine must not run when the solver-call budget is zero"

    def test_unknown_graph_kind_is_malformed(self):
        cortex = cortex_with(GRAPH_ORGAN, GraphSearchOrgan({"graph.shortest_path": (stub(shortest_answer), None)}))
        problem = {"problem_id": "t:kind", "question": "q",
                   "payload": {"declared": DECL, "graph": {"kind": "traveling_salesman", "edges": []}}}
        receipt = cortex.run(problem)
        assert receipt["output"]["state"] == "MALFORMED_INPUT"
        assert receipt["disposition"]["kind"] == "abstain"


# ------------------------------------------------------------------ truthful negatives
class TestTruthfulNegatives:
    def test_default_cortex_reports_a_capability_deficit(self):
        receipt = Cortex().run(GRAPH_PROBLEM)
        assert receipt["output"]["state"] == "DEPENDENCY_UNAVAILABLE"
        assert receipt["output"]["answer"] is None
        assert bridge._abstention(receipt) == "CAPABILITY_DEFICIT"   # the genesis trigger
        validate(receipt, "cortex-receipt")

    def test_detached_formed_function_is_a_deficit(self):
        organ = GraphSearchOrgan({"graph.shortest_path": (None, "acquired.graph.shortest_path.networkx: "
                                                                 "state DETACHED")})
        receipt = cortex_with(GRAPH_ORGAN, organ).run(GRAPH_PROBLEM)
        assert receipt["output"]["state"] == "DEPENDENCY_UNAVAILABLE"
        assert "DETACHED" in receipt["proof_artifacts"][0]["failure"]
        assert bridge._abstention(receipt) == "CAPABILITY_DEFICIT"

    def test_a_lying_engine_is_withheld_and_claims_nothing(self):
        def liar(params, cpu_seconds):
            raise formed_mod.FormedFunctionError("certificate", "edge A -> B gives a shorter path to B")
        cortex = cortex_with(GRAPH_ORGAN, GraphSearchOrgan({"graph.shortest_path": (liar, None)}))
        receipt = cortex.run(GRAPH_PROBLEM)
        assert receipt["output"]["state"] == "INCONCLUSIVE"
        assert receipt["output"]["answer"] is None
        assert "failed GREG's certificate" in receipt["proof_artifacts"][0]["failure"]
        assert receipt["disposition"]["kind"] == "abstain"
        validate(receipt, "cortex-receipt")

    def test_a_changed_package_is_a_deficit_not_a_claim(self):
        def changed(params, cpu_seconds):
            raise formed_mod.FormedFunctionError("unavailable", "package changed since qualification")
        cortex = cortex_with(GRAPH_ORGAN, GraphSearchOrgan({"graph.shortest_path": (changed, None)}))
        receipt = cortex.run(GRAPH_PROBLEM)
        assert receipt["output"]["state"] == "DEPENDENCY_UNAVAILABLE"
        assert bridge._abstention(receipt) == "CAPABILITY_DEFICIT"

    def test_a_timeout_is_a_timeout(self):
        def slow(params, cpu_seconds):
            raise formed_mod.FormedFunctionError("timeout", "package runner did not complete")
        cortex = cortex_with(GRAPH_ORGAN, GraphSearchOrgan({"graph.shortest_path": (slow, None)}))
        assert cortex.run(GRAPH_PROBLEM)["output"]["state"] == "TIMEOUT"

    def test_outside_the_competence_envelope_is_malformed_with_the_reason(self):
        def negative(params, cpu_seconds):
            raise formed_mod.FormedFunctionError(
                "invalid", "network request invalid: negative weights are outside this function's competence")
        cortex = cortex_with(GRAPH_ORGAN, GraphSearchOrgan({"graph.shortest_path": (negative, None)}))
        receipt = cortex.run(GRAPH_PROBLEM)
        assert receipt["output"]["state"] == "MALFORMED_INPUT"
        assert "negative weights" in receipt["proof_artifacts"][0]["failure"]

    def test_an_unproven_negative_claim_is_withheld(self):
        def unproven(params, cpu_seconds):
            return {"solver_calls": 1,
                    "answer": {"certified": False, "status": "infeasible", "certificate": None,
                               "why": "the engine reports no feasible plan; the program is too large for "
                                      "GREG to prove it here", "_mechanism": dict(LP_MECH)}}
        cortex = cortex_with(CONOPT_ORGAN, ContinuousOptimizationOrgan({"lp.optimize": (unproven, None)}))
        receipt = cortex.run(LP_PROBLEM)
        assert receipt["output"]["state"] == "INCONCLUSIVE"
        assert receipt["output"]["answer"] is None
        assert receipt["proof_artifacts"][0]["engine_claim"]["label"].startswith("unproven")


# ------------------------------------------------------------------ body-side resolution
def _attached_manifest(function, distribution):
    """The manifest Capability Genesis registers when a package qualifies (same fields)."""
    from greg import mechanisms
    from greg.genesis import CATALOG, package_adapter
    spec = CATALOG[function]
    candidate = next(c for c in spec["candidates"] if c.distribution == distribution)
    dist = mechanisms.installed(distribution)
    if dist is None:
        pytest.skip(f"{distribution} not installed on this body")
    card = mechanisms.card(candidate, function, dist)
    manifest = CapabilityManifest(
        capability_id=f"acquired.{function}.{candidate.distribution}", version="1.0.0",
        provider=f"installed:python:{candidate.distribution}=={card['version']}", function=function,
        description=spec["description"], route="internal", consequence_class="read_only",
        inputs=spec.get("inputs", {"edges": "list", "source": "str"}),
        outputs={spec["output_field"]: "bool", "certificate": "dict"},
        target_prefix="cognition:", filesystem="none", retry_safe=True,
        tests=(f"frozen-oracle:{function}", "certificate:every-call"),
        strengthens=("capability_formation", "proof"),
        provenance={**card, "deficit_id": "test-deficit", "runner": candidate.runner,
                    "runner_sha256": hashlib.sha256(spec["runners"][candidate.runner].encode()).hexdigest(),
                    "builder": "none: installed open-source package acquired by search"})
    return manifest, package_adapter(function, candidate)


class TestFormedResolution:
    def test_attached_package_function_resolves_its_card(self):
        from greg.cognition.cortex import registry_view
        registry = registry_view()
        manifest, adapter = _attached_manifest("graph.shortest_path", "networkx")
        registry.register(manifest, adapter, state="ATTACHED")
        out = bridge._formed(registry, GRAPH_PROBLEM["payload"] and {"payload": GRAPH_PROBLEM["payload"]})
        entry = out["graph.shortest_path"]["entry"]
        assert entry["capability_id"] == "acquired.graph.shortest_path.networkx"
        assert entry["distribution"] == "networkx" and entry["package_digest"]
        assert hashlib.sha256(entry["runner_source"].encode()).hexdigest() == \
            manifest.provenance["runner_sha256"]
        assert out["graph.shortest_path"]["why"] is None

    def test_detached_function_resolves_to_a_deficit_with_its_reason(self):
        from greg.cognition.cortex import registry_view
        registry = registry_view()
        manifest, adapter = _attached_manifest("graph.shortest_path", "networkx")
        registry.register(manifest, adapter, state="ATTACHED")
        registry.set_state(manifest.capability_id, "DETACHED")     # founder detach
        out = bridge._formed(registry, {"payload": GRAPH_PROBLEM["payload"]})
        assert out["graph.shortest_path"]["entry"] is None
        assert "DETACHED" in out["graph.shortest_path"]["why"]

    def test_unregistered_function_resolves_to_a_deficit(self):
        from greg.cognition.cortex import registry_view
        out = bridge._formed(registry_view(), {"payload": GRAPH_PROBLEM["payload"]})
        assert out["graph.shortest_path"]["entry"] is None
        assert out["graph.shortest_path"]["why"] == "no attached formed function"

    def test_builder_formed_functions_never_execute_here(self):
        from greg.cognition.cortex import registry_view
        registry = registry_view()
        manifest, adapter = _attached_manifest("graph.shortest_path", "networkx")
        manifest.provenance["mode"] = "COMMISSIONED"
        registry.register(manifest, adapter, state="ATTACHED")
        out = bridge._formed(registry, {"payload": GRAPH_PROBLEM["payload"]})
        assert out["graph.shortest_path"]["entry"] is None
        assert "not a package-formed function" in out["graph.shortest_path"]["why"]

    def test_payloads_without_graph_or_lp_resolve_nothing(self):
        from greg.cognition.cortex import registry_view
        assert bridge._formed(registry_view(), {"payload": {"declared": DECL}}) == {}


# ------------------------------------------------------------------ end to end through the worker
@pytest.mark.parametrize("problem,cid,check", [
    (GRAPH_PROBLEM, "cognition.cortex.graph.search",
     lambda a: a["certified"] is True and a["distance"] == 3 and a["path"] == ["A", "B", "C"]),
    (FLOW_PROBLEM, "cognition.cortex.graph.search",
     lambda a: a["certified"] is True and a["value"] == 3),
    (LP_PROBLEM, "cognition.cortex.optimization.continuous",
     lambda a: a["certified"] is True and a["status"] == "optimal" and a["objective"] == 4.0),
])
def test_certified_answers_through_the_one_entry(problem, cid, check):
    """The mind keeps one entry: a cortex payload in, a certified answer out."""
    from greg.cognition.cortex import registry_view
    pytest.importorskip("networkx")
    registry = registry_view()
    if cid == "cognition.cortex.optimization.continuous":
        pytest.importorskip("scipy")
        manifest, adapter = _attached_manifest("lp.optimize", "scipy")
    else:
        manifest, adapter = _attached_manifest(
            "graph.max_flow" if problem is FLOW_PROBLEM else "graph.shortest_path", "networkx")
    registry.register(manifest, adapter, state="ATTACHED")
    receipt = bridge.reason_cortex(
        {"problem_id": problem["problem_id"], "problem": {"question": problem["question"],
                                                          "payload": problem["payload"]}},
        registry=registry)
    assert receipt["abstention_state"] == "NONE", receipt["missing_information"]
    assert receipt["method"] == cid
    assert check(receipt["output"]["answer"])
    assert receipt["proof_artifact"]["authority_created"] is False


def test_a_detached_function_turns_the_one_entry_into_a_deficit():
    from greg.cognition.cortex import registry_view
    pytest.importorskip("networkx")
    registry = registry_view()
    manifest, adapter = _attached_manifest("graph.shortest_path", "networkx")
    registry.register(manifest, adapter, state="ATTACHED")
    registry.set_state(manifest.capability_id, "DETACHED")         # founder detach after attach
    receipt = bridge.reason_cortex(
        {"problem_id": "t:detached", "problem": {"question": "q", "payload": GRAPH_PROBLEM["payload"]}},
        registry=registry)
    assert receipt["abstention_state"] == "CAPABILITY_DEFICIT"
    assert receipt["output"]["answer"] is None


def test_a_lying_engine_is_withheld_through_the_worker(monkeypatch):
    """The engine's answer reaches the receipt only through GREG's certificate (never trusted)."""
    from greg.cognition import network
    from greg.cognition.cortex import registry_view
    pytest.importorskip("networkx")
    lie = network.RUNNERS["networkx.shortest_path"].replace(
        '    return {"distances": dist,',
        '    dist = {**dist, "C": 1}\n    pred["C"] = ["A"]\n    return {"distances": dist,')
    monkeypatch.setitem(network.RUNNERS, "networkx.shortest_path", lie)
    registry = registry_view()
    manifest, adapter = _attached_manifest("graph.shortest_path", "networkx")
    registry.register(manifest, adapter, state="ATTACHED")
    receipt = bridge.reason_cortex(
        {"problem_id": "t:liar", "problem": {"question": "q", "payload": GRAPH_PROBLEM["payload"]}},
        registry=registry)
    assert receipt["output"]["state"] == "INCONCLUSIVE"
    assert receipt["output"]["answer"] is None
    assert receipt["abstention_state"] == "UNKNOWN"


def test_drift_guard_covers_the_new_organs():
    """ORGANS, the genome and the catalog cannot drift apart silently."""
    enabled = {k for k, p in seed_registry().profiles().items() if p.enabled and p.role == "solver"}
    assert {GRAPH_ORGAN, CONOPT_ORGAN} <= enabled
    assert set(bridge.ORGANS) == enabled
    assert bridge.FORMED_NEEDS[GRAPH_ORGAN] == ("graph.shortest_path", "graph.max_flow")
    assert bridge.FORMED_NEEDS[CONOPT_ORGAN] == ("lp.optimize",)
