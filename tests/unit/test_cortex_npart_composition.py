"""Bounded n-part composition with cap honesty (cortex 0.4.0).

Register rows A36/B47/B36/A52/B27/B31; founder correction 2026-10-03 (INTENT-0036):
the Competency Compiler recruits the smallest competent mechanism OR COMPOSITION, and
B47 names "recombination beyond two parts" as the known not-yet. Policy 0.4 raises the
composition bound 2 -> 4 (seven route kinds exist; formal_model and schedule_request are
mutually exclusive, so at most seven parts can ever be required) and makes the bound
honest: a part the cap drops is named as cap-dropped, never as "not required by this
payload". Aggregate solver-call demand is refused before spending, not after.

Freeze non-contamination: freeze-v0.3.0.json and the crossgeo freezes are hash-pinned
here; a version bump creates a NEW freeze manifest and never re-freezes in place.
"""
import hashlib
import pathlib

import pytest

pytest.importorskip("z3")

from cortex.evaluation.build_suites import schedule  # noqa: E402
from cortex.organs.continuous import ContinuousOptimizationOrgan  # noqa: E402
from cortex.organs.continuous import ORGAN_ID as CONOPT_ORGAN  # noqa: E402
from cortex.organs.graphsearch import GraphSearchOrgan  # noqa: E402
from cortex.organs.graphsearch import ORGAN_ID as GRAPH_ORGAN  # noqa: E402
from cortex.routing import DETERRENCE, EVIDENCE, FERMI, FORMAL, MAX_COMPOSITION, Cortex  # noqa: E402
from cortex.schemas import validate  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLOCK = lambda: "2026-09-30T00:00:00Z"  # noqa: E731
DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}
JOBS = [("A", 3), ("B", 4), ("C", 2)]

GRAPH_PART = {"kind": "shortest_path", "source": "A", "target": "C",
              "edges": [["A", "B", 1], ["B", "C", 2], ["A", "C", 5]]}
LP_PART = {"variables": [{"name": "x", "lower": 0}, {"name": "y", "lower": 0}],
           "objective": {"sense": "min", "coefficients": {"x": 1, "y": 2}},
           "constraints": [{"op": ">=", "coefficients": {"x": 1, "y": 1}, "rhs": 4, "name": "demand"}]}
EST_PART = {"target": {"name": "c", "unit": "USD/week"}, "expression": ["*", "h", "r"],
            "variables": [{"name": "h", "unit": "hour/week", "low": 30, "high": 50},
                          {"name": "r", "unit": "USD/hour", "low": 40, "high": 60}]}
CLAIM_PART = {"id": "C", "type": "intervention",
              "statement": "raising the detection probability lowers duplicate invoicing",
              "evidence": [{"id": "E1", "kind": "randomized_trial", "effect": -0.4, "se": 0.1}]}
DET_PART = {"actor_role": "vendor submitting invoices", "behavior": "duplicate invoicing",
            "parameters": {"gain_usd": {"low": 2000, "high": 6000}, "p_detect": {"low": 0.05, "high": 0.15},
                           "p_sanction": {"low": 0.5, "high": 0.8},
                           "sanction_usd": {"low": 10000, "high": 30000}},
            "interventions": [{"id": "I_match", "kind": "detection", "cost_usd": 3000,
                               "effects": {"p_detect": {"set": 0.9}}}],
            "seed": 7}


def _shortest_answer():
    return {"certified": True, "source": "A", "target": "C", "reachable": True, "distance": 3,
            "path": ["A", "B", "C"], "distances": {"A": 0, "B": 1, "C": 3}, "unreachable": [],
            "certificate": {"kind": "feasible potentials realised by predecessor chains",
                            "arithmetic": "exact fractions"},
            "engine": "networkx 3.6.1", "license": "BSD-3-Clause", "authority_created": False,
            "_mechanism": {"capability_id": "acquired.graph.shortest_path.networkx", "distribution": "networkx",
                           "version": "3.6.1", "license": "BSD-3-Clause", "runner": "networkx.shortest_path",
                           "package_digest": "sha256:0", "request_sha256": "sha256:1",
                           "request_shape": {"nodes": 3, "edges": 3}}}


def _lp_answer():
    return {"certified": True, "status": "optimal", "sense": "min", "objective": 4.0,
            "values": {"x": 4.0, "y": 0.0}, "binding": ["demand"], "shadow_prices": {"demand": 1.0},
            "certificate": {"kind": "primal and dual feasibility with zero duality gap", "gap": 0.0,
                            "tolerance": "relative 1e-7 (engine floating point)",
                            "arithmetic": "exact fractions"},
            "engine": "scipy 1.17.1", "license": "BSD-3-Clause", "authority_created": False,
            "_mechanism": {"capability_id": "acquired.lp.optimize.scipy", "distribution": "scipy",
                           "version": "1.17.1", "license": "BSD-3-Clause", "runner": "scipy.lp",
                           "package_digest": "sha256:0", "request_sha256": "sha256:1",
                           "request_shape": {"variables": 2, "constraints": 1}}}


def _stub(answer, recorder=None):
    def call(params, cpu_seconds):
        if recorder is not None:
            recorder.append((params, cpu_seconds))
        return {"answer": answer(), "solver_calls": 1}
    return call


def cortex_with_formed(calls=None):
    cortex = Cortex(clock=CLOCK)
    cortex.organs[GRAPH_ORGAN] = GraphSearchOrgan({"graph.shortest_path": (_stub(_shortest_answer, calls), None)})
    cortex.organs[CONOPT_ORGAN] = ContinuousOptimizationOrgan({"lp.optimize": (_stub(_lp_answer, calls), None)})
    return cortex


def formal_part():
    model, _, _ = schedule(JOBS, 10)
    return model


# ------------------------------------------------------------------ n-part composition
class TestBoundedComposition:
    def test_three_parts_compose_with_three_typed_proofs(self):
        receipt = Cortex(clock=CLOCK).run({"problem_id": "n:three", "question": "plan, cost, cause",
                                           "payload": {"declared": DECL, "formal_model": formal_part(),
                                                       "estimation_model": EST_PART, "claim": CLAIM_PART}})
        assert receipt["route"]["selected"] == [FORMAL, FERMI, EVIDENCE]
        assert receipt["route"]["composition"] is True
        assert receipt["route"]["max_parts"] == MAX_COMPOSITION == 4
        assert receipt["route"]["cap_dropped"] == []
        classes = {p["proof_class"] for p in receipt["proof_artifacts"]}
        assert {"formal", "estimation", "evidence_assessment"} <= classes
        assert len(receipt["output"]["per_route"]) == 3
        validate(receipt, "cortex-receipt")

    def test_five_parts_hit_the_cap_and_the_dropped_part_is_named_honestly(self):
        receipt = cortex_with_formed().run({"problem_id": "n:five", "question": "everything at once",
                                            "payload": {"declared": DECL, "formal_model": formal_part(),
                                                        "estimation_model": EST_PART, "graph": GRAPH_PART,
                                                        "linear_program": LP_PART,
                                                        "deterrence_model": DET_PART}})
        route = receipt["route"]
        assert len(route["selected"]) == MAX_COMPOSITION
        assert route["cap_dropped"] == [DETERRENCE], "policy order drops the last eligible part"
        by_route = {a["route"]: a["why_not"] for a in receipt["alternatives"]}
        dropped = by_route[DETERRENCE]
        assert any("dropped by the composition bound" in w for w in dropped), dropped
        assert not any("not required by this payload" in w for w in dropped), \
            "a required, eligible, cap-dropped part must never read as unrequired"
        for key in (GRAPH_ORGAN, CONOPT_ORGAN):
            assert key in route["selected"]
        validate(receipt, "cortex-receipt")

    def test_aggregate_solver_budget_refuses_before_spending(self):
        calls = []
        receipt = cortex_with_formed(calls).run({"problem_id": "n:budget", "question": "q",
                                                 "payload": {"declared": DECL, "formal_model": formal_part(),
                                                             "graph": GRAPH_PART, "linear_program": LP_PART,
                                                             "resources": {"max_solver_calls": 2}}})
        assert receipt["output"]["state"] == "BUDGET_EXHAUSTED"
        assert receipt["disposition"]["kind"] == "abstain"
        assert "at least 3 solver call(s)" in receipt["disposition"]["reason"]
        assert calls == [], "no formed organ may run once the aggregate solver budget refuses"
        assert receipt["output"]["per_route"] == []
        validate(receipt, "cortex-receipt")

    def test_ineligible_part_is_named_by_its_reasons_not_by_the_cap(self):
        # Founder detach (projected through the host registry) makes one required part
        # ineligible; the receipt must name that reason, never the cap and never
        # "not required by this payload".
        from cortex.genome import seed_registry
        registry = seed_registry()
        registry.withhold(FERMI, "state DETACHED")
        receipt = Cortex(registry, clock=CLOCK).run({"problem_id": "n:ineligible", "question": "q",
                                                     "payload": {"declared": DECL, "formal_model": formal_part(),
                                                                 "estimation_model": EST_PART,
                                                                 "claim": CLAIM_PART}})
        assert receipt["route"]["selected"] == [FORMAL, EVIDENCE]
        assert receipt["route"]["cap_dropped"] == []
        by_route = {a["route"]: a["why_not"] for a in receipt["alternatives"]}
        reasons = by_route[FERMI]
        assert any("withheld by host registry" in w for w in reasons), reasons
        assert not any("not required by this payload" in w for w in reasons), reasons
        assert not any("dropped by the composition bound" in w for w in reasons), reasons
        assert "estimation" not in {p["proof_class"] for p in receipt["proof_artifacts"]}
        validate(receipt, "cortex-receipt")


# ------------------------------------------------------------------ freeze non-contamination
class TestFreezeNonContamination:
    PINNED = {
        "freeze-v0.3.0.json": "4a4d2122ae0a511c8c624bf20109f4fdad80d3ec2decd1d35ad1d90a9ec16298",
        "freeze-crossgeo-v0.2.json": "ce9abbc1af4181d30369ac4d794f7ed3d7cd4f20e8417118688ede8850ff6dde",
        "freeze-crossgeo-v0.3.json": "75ca409e9f3aca775e4423d8625c10d0e6bdd24d70d06758711b99fb40ea611d",
    }

    def test_prior_freezes_are_byte_pinned(self):
        for name, want in self.PINNED.items():
            blob = (ROOT / "cortex" / "evaluation" / name).read_bytes()
            assert hashlib.sha256(blob).hexdigest() == want, f"{name} changed; freezes are never rewritten in place"

    def test_the_new_version_has_its_own_fresh_freeze(self):
        new = ROOT / "cortex" / "evaluation" / "freeze-v0.4.0.json"
        assert new.exists(), "a version bump creates a NEW freeze manifest"
        digest = hashlib.sha256(new.read_bytes()).hexdigest()
        assert digest not in set(self.PINNED.values())
