"""The cortex on the GREG path: one entry, one registry, one receipt, one learning plane.

Directive sections 3 (no competing registry/learning plane), 7 (seed classes), 8 (eligibility before
ranking), 16 (connect to the real GREG path). The bridge must:
* route cortex-contract requests through the existing ``cognition.solve`` entry;
* project GREG lifecycle (founder detach) into cortex eligibility, never the reverse;
* accept worker output only if it satisfies the strict contract and its own content address;
* never coerce unknown harm to zero; never let a missing model reach the network;
* keep #140's operation contract and retained receipts working unchanged.
"""
import copy
from dataclasses import replace

import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from cortex.contracts import digest as cortex_digest  # noqa: E402
from cortex.evaluation.build_suites import ev, schedule  # noqa: E402
from cortex.evaluation.generators import confounded  # noqa: E402
from cortex.genome import seed_registry  # noqa: E402
from greg.capabilities import CapabilityError, InvocationContext  # noqa: E402
from greg.cognition import bridge  # noqa: E402
from greg.cognition.catalog import CORTEX_ENTRIES  # noqa: E402
from greg.cognition.contracts import CognitiveReceipt  # noqa: E402
from greg.cognition.cortex import reason, registry_view, solve  # noqa: E402
from greg.cognition.settlement import _valid_receipt  # noqa: E402

DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}


def opt_model():
    model, _, _ = schedule([("A", 3), ("B", 4), ("C", 2)], 10,
                           query={"kind": "optimize", "sense": "minimize", "objective": ["+", "s_A", "s_B", "s_C"]})
    return model


def request(payload, pid="t:cortex", question="q", **kw):
    payload = dict(payload)
    payload.setdefault("declared", DECL)
    return {"problem_id": pid, "problem": {"question": question, "payload": payload}, **kw}


class TestOneRegistry:
    def test_bridge_map_equals_the_cortex_seed_organs(self):
        enabled = {k for k, p in seed_registry().profiles().items() if p.enabled and p.role == "solver"}
        assert set(bridge.ORGANS) == enabled
        assert set(bridge.ORGANS.values()) | {bridge.ROUTER} == set(CORTEX_ENTRIES)
        for key, cid in bridge.ORGANS.items():
            assert CORTEX_ENTRIES[cid][0] == key.split("@")[1], f"{cid} version drifted from {key}"

    def test_cortex_manifests_live_in_the_one_greg_registry(self):
        registry = registry_view()
        for cid in CORTEX_ENTRIES:
            manifest = registry.manifests[cid]
            assert manifest.consequence_class == "read_only" and manifest.cognitive_profile["proof_class"] == \
                "cortex_receipt"
            assert manifest.validate() == []

    def test_founder_detach_withholds_the_organ_and_routing_degrades_to_z3(self):
        registry = registry_view()
        registry.set_state("cognition.cortex.optimization.cpsat", "DETACHED")
        r = reason(request({"formal_model": opt_model()}), registry=registry)
        assert r["method"] == "cognition.cortex.formal.z3" and r["abstention_state"] == "NONE"
        rows = {e["key"]: e for e in r["alternative_methods_considered"] if "key" in e}
        assert any("withheld by host registry" in x for x in rows["cortex.optimization.cpsat@0.2.0"]["reasons"])
        assert r["output"]["answer"]["objective"] == 7

    def test_detached_router_is_a_capability_deficit(self):
        registry = registry_view()
        registry.set_state("cognition.cortex", "DETACHED")
        r = reason(request({"formal_model": opt_model()}), registry=registry)
        assert r["abstention_state"] == "CAPABILITY_DEFICIT" and r["output"] is None
        assert r["outcome"]["outcome"] == "ABSTAIN" and r["outcome"]["reasons"] == ["CAPABILITY_UNAVAILABLE"]

    def test_signed_capability_can_pin_one_organ(self, tmp_path):
        registry = registry_view()
        manifest = registry.manifests["cognition.cortex.formal.z3"]
        ctx = InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=manifest,
                                target="cognition:pin", capability_registry=registry)
        r = solve(request({"formal_model": opt_model()}), ctx)
        assert r["method"] == "cognition.cortex.formal.z3"
        with pytest.raises(CapabilityError):
            solve(request({"formal_model": opt_model()}), InvocationContext(
                workspace=tmp_path, read_roots=(), secrets=None, manifest=manifest, target="fs:wrong",
                capability_registry=registry))


class TestOneReceipt:
    def test_receipt_is_the_greg_envelope_with_the_cortex_receipt_as_typed_artifact(self):
        r = reason(request({"formal_model": opt_model()}), registry=registry_view())
        assert r["proof_type"] == "cortex_receipt" and r["proof_artifact"]["schema"] == "cortex-receipt/0.2"
        assert r["authority_created"] is False and r["legitimate_authority"] == "EXISTING_KERNEL_GATE_REQUIRED"
        assert r["empirical_validity"] == "WORLD_UNVERIFIED" and r["formal_validity"] == "VALID_CONDITIONAL_ON_MODEL"
        assert r["outcome"] == r["proof_artifact"]["outcome"]
        assert _valid_receipt(r)

    def test_operation_contract_is_unchanged_and_now_carries_an_outcome(self):
        r = reason({"problem_id": "op", "operation": "calculate", "data": {"expression": "1/3+1/6"}},
                   registry=registry_view())
        assert r["method"] == "cognition.exact" and r["output"]["exact"] == "1/2"
        assert r["outcome"]["outcome"] == "ANSWERED_WITHIN_SCOPE" and _valid_receipt(r)

    def test_receipts_retained_before_the_outcome_field_remain_valid(self):
        r = reason({"problem_id": "op", "operation": "calculate", "data": {"expression": "2"}},
                   registry=registry_view())
        legacy = {k: v for k, v in r.items() if k not in ("outcome", "receipt_id")}
        legacy["receipt_id"] = __import__("greg.cognition.contracts", fromlist=["digest"]).digest(legacy)
        assert _valid_receipt(legacy)
        CognitiveReceipt(**{k: v for k, v in legacy.items() if k != "receipt_id"})

    def test_unknown_harm_is_never_zero(self):
        r = reason(request({"formal_model": opt_model(), "declared": {"consequence_class": "internal_write"}}),
                   registry=registry_view())
        assert all(v is None for v in r["consequence_vector"].values() if not isinstance(v, bool) and v != 0) and \
            r["consequence_vector"]["rights"] is None and r["consequence_vector"]["physical"] is None
        declared = dict(DECL, harm={"rights": "high", "physical": "none"})
        r = reason(request({"formal_model": opt_model(), "declared": declared}), registry=registry_view())
        assert r["consequence_vector"]["rights"] == .75 and r["consequence_vector"]["physical"] == 0.0


class TestWorkerOutputIsData:
    def tamper(self, monkeypatch, mutate):
        real = bridge.run_worker

        def forged(*a, **k):
            receipt = real(*a, **k)
            mutate(receipt)
            return receipt
        monkeypatch.setattr(bridge, "run_worker", forged)

    def test_edited_answer_breaks_the_content_address(self, monkeypatch):
        self.tamper(monkeypatch, lambda r: r["output"].__setitem__("answer", {"feasible": True, "objective": 0}))
        r = reason(request({"formal_model": opt_model()}), registry=registry_view())
        assert r["abstention_state"] == "ABSTAIN" and "content address" in r["missing_information"][0]

    def test_readdressed_authority_claim_is_refused_by_the_contract(self, monkeypatch):
        def claim(r):
            r["authority_created"] = True
            body = {k: v for k, v in r.items() if k != "receipt_id"}
            r["receipt_id"] = cortex_digest(body)
        self.tamper(monkeypatch, claim)
        r = reason(request({"formal_model": opt_model()}), registry=registry_view())
        assert r["abstention_state"] == "ABSTAIN" and r["output"] is None

    def test_worker_crash_is_unknown_not_success(self, monkeypatch):
        def boom(*a, **k):
            raise bridge.CognitionError("cortex worker stopped (exit -9); result unknown")
        monkeypatch.setattr(bridge, "run_worker", boom)
        r = reason(request({"formal_model": opt_model()}), registry=registry_view())
        assert r["abstention_state"] == "ABSTAIN" and "result unknown" in r["missing_information"][0]


class TestSeedClassesThroughGreg:
    def test_semantic_without_a_founder_selected_model_never_reaches_a_network(self):
        r = reason(request({"sources": [{"id": "S1", "text": "The plant runs two shifts."}]},
                           question="How many shifts?"), registry=registry_view(), model_config=None)
        assert r["abstention_state"] == "CAPABILITY_DEFICIT"
        per_route = r["proof_artifact"]["output"]["per_route"]
        assert per_route[0]["state"] == "DEPENDENCY_UNAVAILABLE"
        assert "no founder-selected local model" in per_route[0]["proof"]["failure"]

    def test_identified_causal_effect_recovers_ground_truth_and_unidentified_abstains(self):
        spec = {"estimand": "average treatment effect of t on y", "treatment": "t", "outcome": "y",
                "adjustment_set": ["z"],
                "identification_assumptions": ["z blocks every backdoor path from t to y",
                                               "no unmeasured confounding", "positivity within strata of z"],
                "identification_basis": {"origin": "randomized_experiment", "ref": "synthetic design"},
                "method": "stratified", "limitations": ["synthetic data"],
                "data": confounded(n=600, effect=2.0, confounding=1.5, seed=11)}
        claim = {"id": "C1", "type": "intervention", "statement": "t raises y"}
        payload = {"claim": claim, "causal_spec": spec, "as_of": "2026-09-30",
                   "evidence": [ev("E1", "supports", kind="experiment")]}
        r = reason(request(payload), registry=registry_view())
        estimate = r["output"]["answer"]
        assert r["method"] == "cognition.cortex.evidence_causal"
        assert abs(estimate["effect"] - 2.0) < 0.35, estimate   # synthetic ground truth 2.0
        unidentified = copy.deepcopy(payload)
        unidentified["causal_spec"]["identification_basis"] = {"origin": "model_generated", "ref": "llm dag"}
        r2 = reason(request(unidentified), registry=registry_view())
        assert r2["abstention_state"] != "NONE" and r2["proof_artifact"]["output"]["state"] == "NOT_IDENTIFIED"
        assert "NON_IDENTIFIABLE" in r2["outcome"]["reasons"]

    def test_estimation_carries_units_ranges_and_sensitivity(self):
        model = {"target": {"name": "weekly_hours", "unit": "h"},
                 "variables": [{"name": "jobs", "unit": "1", "low": 20, "high": 30},
                               {"name": "hours_per_job", "unit": "h", "low": 1.5, "high": 2.5}],
                 "expression": ["*", "jobs", "hours_per_job"], "dependencies": [], "reference_class": None,
                 "seed": 7}
        r = reason(request({"estimation_model": model}), registry=registry_view())
        proof = r["proof_artifact"]["proof_artifacts"][0]
        assert r["method"] == "cognition.cortex.estimation.fermi"
        assert proof["units"] and proof["sensitivity"] and proof["low"] < proof["median"] < proof["high"]

    def test_legal_question_escalates_and_never_answers(self):
        r = reason(request({"declared": {**DECL, "epistemic_class": "legal"}}, question="Is this enforceable?"),
                   registry=registry_view())
        assert r["abstention_state"] == "HUMAN_REVIEW_REQUIRED" and r["outcome"]["outcome"] == "ESCALATE"
        assert r["output"]["answer"] is None
