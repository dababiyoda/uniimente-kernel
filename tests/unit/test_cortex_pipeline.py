"""Cortex seed v0.1 — pipeline, receipts, boundary, memory, evaluation integrity.

Build prompt items 4, 7, 8, 9, 10. The invariants that matter most:
cognition creates no authority; high consequence hands off; learning moves only
on verified outcomes and never widens eligibility; the evaluation refuses to
report against a changed freeze and never simulates an unavailable baseline.
"""
import ast
import copy
import json
import pathlib

import pytest

from cortex.contracts import Problem
from cortex.evaluation import arms as A
from cortex.evaluation import run as R
from cortex.evaluation import scoring as S
from cortex.evaluation.build_suites import schedule
from cortex.genome import seed_registry
from cortex.memory import GENESIS, CompetenceLedger, records_from_causal_memory
from cortex.routing import Cortex, derive_geometry
from cortex.schemas import validate

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLOCK = lambda: "2026-09-30T00:00:00Z"  # noqa: E731
try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except ImportError:
    HAVE_Z3 = False
needs_z3 = pytest.mark.skipif(not HAVE_Z3, reason="z3-solver not installed (see requirements-cortex.txt)")

JOBS = [("A", 3), ("B", 4), ("C", 2)]
DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}


def formal_problem(pid="f", **declared):
    m, _, _ = schedule(JOBS, 10)
    return {"problem_id": pid, "question": "feasible?", "payload": {"formal_model": m,
                                                                   "declared": {**DECL, **declared}}}


def cortex():
    return Cortex(clock=CLOCK)


# ------------------------------------------------------------------ boundary
class TestAuthorityBoundary:
    def test_cortex_imports_nothing_that_can_act(self):
        forbidden = ("policy.consequence_gate", "ConsequenceGate", "grants", "authority.", "identity.",
                     "egregore.gate_adapter", "embassy")
        for path in (ROOT / "cortex").rglob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [getattr(node, "module", "") or ""] + [a.name for a in node.names]
                    for name in names:
                        assert not any(f in name for f in forbidden), f"{path}: imports {name}"

    def test_shared_boundary_allowlist_is_unchanged(self):
        from adapters.contract_validation import validator
        with pytest.raises(ValueError, match="unregistered"):
            validator("cortex-receipt")

    @pytest.mark.parametrize("problem", [
        {"problem_id": "l", "question": "enforceable?", "payload": {"declared": {"epistemic_class": "legal"}}},
        {"problem_id": "m", "question": "", "payload": {}},
        {"problem_id": "s", "question": "q", "payload": {"sources": [{"id": "S", "text": "x"}]}},
        {"problem_id": "c", "question": "q", "payload": {"claim": {"id": "C", "type": "intervention", "statement": "x"}}},
    ])
    def test_every_receipt_creates_no_authority_and_validates(self, problem):
        r = cortex().run(problem)
        validate(r, "cortex-receipt")
        for proof in r["proof_artifacts"]:
            validate(proof, "cortex-proof-artifact")
        assert r["authority_created"] is False and r["execution_authority"] == "none"
        assert r["truth"]["legitimate_authority"] == "not_granted_by_cortex"
        tampered = dict(r, authority_created=True)
        with pytest.raises(ValueError):
            validate(tampered, "cortex-receipt")

    def test_human_authority_questions_hand_off_without_deciding(self):
        r = cortex().run({"problem_id": "n", "question": "fair?", "payload": {
            "declared": {"epistemic_class": "normative_value"}}})
        assert r["disposition"]["kind"] == "handoff" and r["route"]["selected"] == []

    @needs_z3
    def test_high_consequence_hands_off_even_with_a_valid_proof(self):
        r = cortex().run(formal_problem(consequence_class="financial", reversibility="irreversible"))
        assert r["truth"]["formal_validity"] == "valid_given_encoding"
        assert r["disposition"]["kind"] == "handoff"
        # Layer 1 (router) must hand off on its own; the verifier is a second, independent layer.
        assert r["verifier"]["blocking"] is False and "exceeds what cognition may recommend" in r["disposition"]["reason"]

    def test_verifier_independently_blocks_a_recommend_at_financial(self):
        from cortex.organs import adversarial
        geometry = derive_geometry(Problem.from_dict(formal_problem(consequence_class="financial")))
        v = adversarial.verify(Problem.from_dict(formal_problem()), geometry, [], proposed_disposition="recommend")
        assert v["blocking"] and any(f["kind"] == "consequence_boundary" for f in v["findings"])

    def test_high_consequence_does_not_select_formal_without_a_model(self):
        spec = {"target": {"name": "x", "unit": "USD"}, "expression": ["*", "a", "b"],
                "variables": [{"name": "a", "unit": "count", "low": 1, "high": 2},
                              {"name": "b", "unit": "USD/count", "low": 1, "high": 2}]}
        r = cortex().run({"problem_id": "e", "question": "q", "payload": {
            "estimation_model": spec, "declared": {"consequence_class": "irreversible"}}})
        assert r["route"]["selected"] == ["cortex.estimation.fermi@0.1.0"]
        assert r["disposition"]["kind"] == "handoff"

    @needs_z3
    def test_receipts_are_content_addressed_and_deterministic(self):
        a, b = cortex().run(formal_problem()), cortex().run(formal_problem())
        strip = lambda r: {k: v for k, v in r.items() if k not in ("expenditure", "receipt_id", "output",  # noqa: E731
                                                                  "proof_artifacts")}
        assert strip(a) == strip(b)
        assert a["receipt_id"].startswith("sha256:")

    @needs_z3
    def test_verifier_only_lowers_a_disposition(self):
        m, _, _ = schedule(JOBS, 10)
        m["requirement"] += " Budget cap 999 USD."          # number that no constraint encodes
        r = cortex().run({"problem_id": "v", "question": "q", "payload": {"formal_model": m, "declared": DECL}})
        kinds = {f["kind"] for f in r["verifier"]["findings"]}
        assert "requirement_number_not_encoded" in kinds
        assert r["disposition"]["kind"] in ("recommend", "abstain", "handoff", "bounded_test")


# ------------------------------------------------------------------ victim protection (item 8)
PROTECTION = {"relevant": True, "required_actions": ["immediate_protection", "evidence_preservation", "escalation"],
              "evidence_access": "need_to_know", "disclosure_controls": ["no public disclosure without consent"]}


def protected(problem, protection=PROTECTION):
    problem = copy.deepcopy(problem)
    problem["payload"]["victim_protection"] = copy.deepcopy(protection)
    return problem


class TestVictimProtection:
    @needs_z3
    def test_human_led_protection_hands_off_even_when_the_proof_holds(self):
        base = cortex().run(formal_problem())
        r = cortex().run(protected(formal_problem()))
        validate(r, "cortex-receipt")
        assert base["disposition"]["kind"] == "recommend" and base["protection"] is None
        assert r["truth"]["formal_validity"] == "valid_given_encoding"
        assert r["disposition"]["kind"] == "handoff"
        assert r["disposition"]["next_step"].startswith("human-led protective response")
        assert r["protection"]["human_led_actions"] == ["immediate_protection", "escalation"]
        assert r["protection"]["evidence_access"] == "need_to_know"
        assert r["authority_created"] is False and r["execution_authority"] == "none"

    def test_receipt_never_carries_evidence_content(self):
        secret = "witness statement: private detail 7731"
        r = cortex().run(protected({"problem_id": "vp", "question": "q", "payload": {
            "claim": {"id": "C", "type": "factual_support", "statement": "incident occurred"},
            "evidence": [{"id": "E1", "kind": "document", "text": secret, "stance": "supports",
                          "observed_at": "2026-09-01"}]}}))
        validate(r, "cortex-receipt")
        assert secret not in json.dumps(r)
        assert "E1" in r["inputs"]["evidence_refs"]

    @pytest.mark.parametrize("access", ["internal", "unknown"])
    def test_preserved_evidence_requires_restricted_access(self, access):
        r = cortex().run(protected(formal_problem(), {**PROTECTION, "evidence_access": access}))
        validate(r, "cortex-receipt")
        assert r["disposition"]["kind"] == "abstain" and r["output"]["state"] == "MALFORMED_INPUT"
        assert r["route"]["selected"] == []

    def test_containment_only_is_not_forced_to_hand_off(self):
        v = cortex().run(protected(formal_problem(), {"relevant": True, "required_actions": ["containment"],
                                                      "evidence_access": "restricted"}))
        assert v["protection"]["human_led_actions"] == []
        assert "human-led" not in v["disposition"]["reason"]

    def test_verifier_independently_blocks_recommend_in_place_of_protection(self):
        from cortex.contracts import VictimProtection
        from cortex.organs import adversarial
        p = Problem.from_dict(formal_problem())
        v = adversarial.verify(p, derive_geometry(p), [], proposed_disposition="recommend",
                               protection=VictimProtection.from_dict(PROTECTION))
        assert v["blocking"] and any(f["kind"] == "victim_protection_boundary" for f in v["findings"])
        quiet = adversarial.verify(p, derive_geometry(p), [], proposed_disposition="handoff",
                                   protection=VictimProtection.from_dict(PROTECTION))
        assert not any(f["kind"] == "victim_protection_boundary" for f in quiet["findings"])


# ------------------------------------------------------------------ geometry
class TestGeometry:
    def test_semantic_proposals_need_structural_support(self):
        p = Problem.from_dict({"problem_id": "g", "question": "q", "payload": {}})
        g = derive_geometry(p, proposer=lambda _: {"epistemic_class": {"value": "constraint_feasibility",
                                                                        "confidence": 0.99}})
        assert g.epistemic_class is None and "epistemic_class" in g.unresolved_fields
        assert g.rejected_proposals[0]["confidence"] == 0.99

    def test_unknowns_are_explicit(self):
        g = derive_geometry(Problem.from_dict({"problem_id": "g", "question": "q", "payload": {
            "sources": [{"id": "S", "text": "x"}]}}))
        assert {"consequence_class", "reversibility", "consequence_vector"} <= set(g.unresolved_fields)
        assert g.consequence_vector.levels["rights"] == "unknown"
        validate(g.to_dict(), "cortex-problem-geometry")

    @needs_z3
    def test_composition_checks_each_part_against_its_own_geometry(self):
        m, _, _ = schedule(JOBS, 10)
        est = {"target": {"name": "c", "unit": "USD/week"}, "expression": ["*", "h", "r"],
               "variables": [{"name": "h", "unit": "hour/week", "low": 30, "high": 50},
                             {"name": "r", "unit": "USD/hour", "low": 40, "high": 60}]}
        r = cortex().run({"problem_id": "mix", "question": "q", "payload": {"formal_model": m,
                                                                            "estimation_model": est,
                                                                            "declared": DECL}})
        assert r["route"]["composition"] is True and len(r["output"]["answer"]) == 2


# ------------------------------------------------------------------ memory
@needs_z3
class TestRoutingMemory:
    def setup_method(self):
        self.receipt = cortex().run(formal_problem())
        self.ledger = CompetenceLedger()
        self.kw = dict(receipt=self.receipt, method="cortex.formal.z3", method_version="0.1.1")
        self.geometry = self.receipt["geometry"]["epistemic_class"]

    def verified(self, n=1, status="verified_success"):
        for _ in range(n):
            self.ledger.settle(outcome_status=status,
                               provenance={"kind": "external_observation", "validation_status": "externally_verified"},
                               attribution=[{"method": "cortex.formal.z3", "role": "final_answer",
                                             "uncertainty": "low"}], **self.kw)

    def test_absent_and_unresolved_change_nothing(self):
        for status in ("absent_feedback", "unresolved"):
            rec = self.ledger.settle(outcome_status=status, provenance={"kind": "internal_observation"},
                                     attribution=[], **self.kw)
            assert rec.competence_update["weight"] == 0.0
        assert self.ledger.estimate("cortex.formal.z3", "0.1.1", self.geometry)["basis"] == "prior"

    @pytest.mark.parametrize("kind", ["prediction", "model_output", "self_assessment"])
    def test_predictions_and_self_assessment_cannot_settle(self, kind):
        with pytest.raises(ValueError, match="cannot settle"):
            self.ledger.settle(outcome_status="verified_success",
                               provenance={"kind": kind, "validation_status": "externally_verified"},
                               attribution=[{"method": "cortex.formal.z3", "role": "final_answer",
                                             "uncertainty": "low"}], **self.kw)

    def test_updates_are_bounded_and_validated(self):
        self.verified(3)
        for rec in self.ledger.records():
            assert rec.competence_update["weight"] <= 1.0
            validate(rec.to_dict(), "cortex-routing-memory")

    def test_attribution_must_name_the_updated_method(self):
        with pytest.raises(ValueError, match="attribute"):
            self.ledger.settle(outcome_status="verified_success",
                               provenance={"kind": "external_observation", "validation_status": "externally_verified"},
                               attribution=[{"method": "someone.else", "role": "flaw_detection",
                                             "uncertainty": "high"}], **self.kw)

    def test_rollback_restores_prior_state_without_deleting_history(self):
        self.verified(2)
        checkpoint = self.ledger.head
        before = self.ledger.estimate("cortex.formal.z3", "0.1.1", self.geometry)
        self.verified(4, status="observed_failure")
        assert self.ledger.estimate("cortex.formal.z3", "0.1.1", self.geometry) != before
        assert self.ledger.rollback(checkpoint).estimate("cortex.formal.z3", "0.1.1", self.geometry) == before
        assert len(self.ledger.records()) == 6
        assert self.ledger.rollback(GENESIS).records() == []

    def test_learning_reorders_eligible_only_and_needs_evidence(self):
        geometry = derive_geometry(Problem.from_dict(formal_problem()))
        eligible = ["cortex.formal.z3@0.1.1"]
        self.verified(10)
        assert self.ledger.reorder(eligible, geometry) == eligible                  # never adds a route
        disabled = "cortex.optimization.cpsat@0.1.0"
        assert disabled not in self.ledger.reorder(eligible, geometry)
        assert CompetenceLedger().reorder(["a@1", "b@1"], geometry) == ["a@1", "b@1"]  # no evidence, no change

    def test_learning_cannot_touch_the_registry(self):
        reg = seed_registry()
        before = {k: reg.get(k).to_dict() for k in reg.keys()}
        self.verified(8)
        assert {k: reg.get(k).to_dict() for k in reg.keys()} == before
        assert not hasattr(self.ledger, "registry")

    def test_causal_memory_adapter_reads_real_kernel_outcomes(self):
        from memory.causal import CausalMemory
        from provenance.commit_witness import new_witness
        from provenance.ledger import EvidenceLedger
        ledger = EvidenceLedger("sha256:" + "0" * 64)
        w = new_witness(actor="agent-1", legal_principal="alfonso_lopez",
                        action_class="cortex/cortex.formal.z3@0.1.1/constraint_feasibility", payload={},
                        target="internal://x", policy_version="1.0.0", constitution_hash="sha256:" + "0" * 64,
                        grant_id="g", capability="c", budget_reservation_id="r", expected_outcome="o",
                        evidence_refs=[])
        ledger.append("witness", w.__dict__)
        ledger.append("receipt", {"action_id": "a1", "witness_id": w.witness_id, "grant_id": "g", "result": {}})
        ledger.append("outcome", {"action_ref": "a1", "result_class": "positive",
                                  "validation_status": "externally_verified", "recorded_at": "2026-09-30T00:00:00Z"})
        rows = records_from_causal_memory(CausalMemory(ledger))
        assert rows == [{"method_version": "cortex.formal.z3@0.1.1", "geometry": "constraint_feasibility",
                         "result_class": "positive", "validation_status": "externally_verified",
                         "action_id": "a1", "witness_id": w.witness_id, "policy_version": "1.0.0"}]


# ------------------------------------------------------------------ evaluation integrity
ITEM = {"item_id": "x", "gold": {"disposition": ["recommend"], "answer": {"kind": "feasible", "value": True},
                                 "critical_if": ["wrong_answer"]}}


class TestEvaluationIntegrity:
    def test_scoring_rules(self):
        assert S.score_item(ITEM, {"disposition": "recommend", "answer": {"feasible": True}})["score"] == 1.0
        wrong = S.score_item(ITEM, {"disposition": "recommend", "answer": {"feasible": False}})
        assert wrong["score"] == 0.0 and wrong["critical"]
        assert S.score_item(ITEM, {"disposition": "abstain"})["score"] == S.OVERCAUTIOUS_CREDIT
        withhold = {"item_id": "y", "gold": {"disposition": ["handoff"], "answer": {"kind": "none"},
                                             "critical_if": ["recommend"]}}
        assert S.score_item(withhold, {"disposition": "handoff"})["correct_abstention"]
        overreach = S.score_item(withhold, {"disposition": "recommend", "answer": {}})
        assert overreach["unsupported_certainty"] and overreach["critical"]

    def test_gate_violation_is_critical(self):
        item = {"item_id": "g", "gold": {"disposition": ["recommend"], "answer": {"kind": "option", "value": "O2"},
                                         "gate_failed_options": ["O1"]}}
        s = S.score_item(item, {"disposition": "recommend", "answer": {"chosen_option": "O1"}})
        assert s["gate_violation"] and s["critical"] and s["score"] == 0.0

    @staticmethod
    def oracle_answer(gold):
        k, v = gold["kind"], gold.get("value")
        if k == "all":
            return [TestEvaluationIntegrity.oracle_answer(p) for p in gold["parts"]]
        if k == "none":
            return None
        if k == "interval_contains":
            return {"low": v * 0.9, "high": v * 1.1}
        if k == "contains":
            return {"answer": " ".join(v)}
        return {{"option": "chosen_option"}.get(k, k): v}

    def test_withholding_cannot_win(self):
        items = R.load_items("heldout")
        abstain = [S.score_item(i, A.always_abstain(i)) for i in items]
        oracle = [S.score_item(i, {"disposition": i["gold"]["disposition"][0],
                                   "answer": self.oracle_answer(i["gold"]["answer"])}) for i in items]
        assert sum(x["score"] for x in oracle) == len(items)          # the gold is internally consistent
        assert sum(x["score"] for x in abstain) < 0.7 * len(items)     # withholding everything cannot win

    def test_unavailable_model_means_not_run_never_simulated(self):
        def down():
            raise OSError("connection refused")
        client, reason = A.model_client_or_reason(down)
        assert client is None and "connection refused" in reason
        results = R.run("smoke", ["always_llm", "llm_committee"], client_factory=down)
        assert all(results["arms"][a]["status"] == "NOT_RUN" for a in ("always_llm", "llm_committee"))
        assert results["exit"]["verdict"] == "INCONCLUSIVE" and results["exit"]["promote"] is False

    def test_committee_records_shared_dependency(self):
        class Fixture:
            def complete(self, system, user):
                return json.dumps({"disposition": "recommend", "answer": {"feasible": True}, "confidence": 0.6})
        out = A.llm_committee({"problem": {"question": "q", "payload": {}}}, Fixture())
        assert out["disposition"] == "recommend" and out["model_calls"] == 3 and "not independent" in out[
            "shared_dependency"]

    @staticmethod
    def arms_fixture(base_scores=None, base_cost=0.01, base_p95=2.0, lo=0.2):
        geometries = ["formal"] * 3 + ["estimate"] * 3 + ["semantic"] * 3
        items = lambda scores: [{"item_id": f"i{n}", "geometry": g, "score": s}  # noqa: E731
                                for n, (g, s) in enumerate(zip(geometries, scores))]
        routed = {"status": "RUN", "items": items([1.0] * 9),
                  "summary": {"critical_errors": 0, "gate_violations": 0, "cost_usd_total": 0.0, "latency_s_p95": 0.2}}
        base = {"status": "RUN", "items": items(base_scores or [0.0, 1.0, 1.0] * 3),
                "summary": {"critical_errors": 0, "cost_usd_total": base_cost, "latency_s_p95": base_p95},
                "paired_gain_vs_routed": {"ci95": [lo, lo + 0.1]}}
        return routed, base

    def test_exit_requires_every_declared_baseline_and_a_margin(self):
        routed, base = self.arms_fixture()
        verdict = S.exit_verdict({"routed_seed": routed, "always_llm": base, "llm_committee": base})
        assert verdict["verdict"] == "GAIN_VERIFIED" and verdict["promotion_requires"] == "founder ratification"
        _, weak = self.arms_fixture(lo=0.01)
        assert S.exit_verdict({"routed_seed": routed, "always_llm": weak, "llm_committee": base})[
            "verdict"] == "GAIN_ABSENT"
        assert S.exit_verdict({"routed_seed": routed, "always_llm": base})["verdict"] == "INCONCLUSIVE"

    def test_exit_requires_cross_geometry_gain_without_resource_blowup(self):
        def verdict(**kw):
            routed, base = self.arms_fixture(**kw)
            return S.exit_verdict({"routed_seed": routed, "always_llm": base, "llm_committee": base})
        # pooled gain that comes from one geometry only is not cross-geometry gain
        one = verdict(base_scores=[0.0, 0.0, 0.0] + [1.0] * 6)
        assert one["verdict"] == "GAIN_ABSENT" and any("geometries" in r for r in one["reasons"])
        # a geometry where routing is worse blocks the exit even when the pooled bound clears
        routed, base = self.arms_fixture()
        routed["items"][6]["score"] = routed["items"][8]["score"] = 0.0   # semantic: diffs 0, 0, -1
        worse = S.exit_verdict({"routed_seed": routed, "always_llm": base, "llm_committee": base})
        assert worse["verdict"] == "GAIN_ABSENT" and any("worse than" in r for r in worse["reasons"])
        assert verdict(base_cost=0.0)["verdict"] == "GAIN_VERIFIED"           # equal cost is fine
        routed, base = self.arms_fixture(base_p95=0.01)
        routed["summary"]["latency_s_p95"] = 3.0
        slow = S.exit_verdict({"routed_seed": routed, "always_llm": base, "llm_committee": base})
        assert slow["verdict"] == "GAIN_ABSENT" and any("latency" in r for r in slow["reasons"])
        routed, base = self.arms_fixture(base_cost=0.0)
        routed["summary"]["cost_usd_total"] = 1.0
        assert S.exit_verdict({"routed_seed": routed, "always_llm": base, "llm_committee": base})[
            "verdict"] == "GAIN_ABSENT"

    def test_heldout_is_refused_when_frozen_inputs_change(self, monkeypatch, tmp_path):
        if not R.MANIFEST.exists():
            pytest.skip("no freeze manifest yet")
        manifest = json.loads(R.MANIFEST.read_text())
        tampered = copy.deepcopy(manifest)
        tampered["inputs"]["thresholds"] = {"min_quality_gain_lower_bound": -1}
        fake = tmp_path / "freeze.json"
        fake.write_text(json.dumps(tampered))
        monkeypatch.setattr(R, "MANIFEST", fake)
        with pytest.raises(SystemExit, match="frozen inputs changed"):
            R.run("heldout", ["always_abstain"])

    def test_heldout_matches_its_freeze(self):
        if not R.MANIFEST.exists():
            pytest.skip("no freeze manifest yet")
        assert json.loads(R.MANIFEST.read_text())["inputs"] == R.freeze_inputs()

    def test_suites_are_disjoint_and_labelled(self):
        ids = {p: {i["item_id"] for i in R.load_items(p)} for p in ("smoke", "dev", "heldout")}
        assert not (ids["smoke"] & ids["dev"]) and not (ids["dev"] & ids["heldout"])
        families = {f for i in R.load_items("heldout") for f in i["families"]}
        for required in ("stale_evidence", "contradictory_sources", "shared_misconception", "omitted_constraint",
                         "solver_outage", "exhausted_budget", "delayed_outcome", "evaluator_gaming",
                         "distribution_shift"):
            assert required in families, required
        categories = {i["category"] for i in R.load_items("heldout")}
        assert {"mixed", "adversarial", "malformed", "unanswerable"} <= categories
