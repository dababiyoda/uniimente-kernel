"""Layer 5 Competency Compiler on the canonical cognition entry (directive sections 8-12)."""
import json

import pytest

pytest.importorskip("ortools")
pytest.importorskip("networkx")

from cortex.evaluation.composition_lift import run_v2 as R  # noqa: E402
from greg.cognition import compiler  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402
from greg.cognition.genomes.flow import maxflow_instance  # noqa: E402

RECEIPT_FIELDS = {"problem_id", "geometry", "subgeometry", "consequence_class", "methods_considered",
                  "methods_rejected", "method_or_composition_selected", "selection_level",
                  "conditional_competence_basis", "inputs_digest", "assumptions", "evidence_refs", "transformations",
                  "intermediate_receipts", "proof_artifacts", "uncertainty", "abstentions", "dissent", "cost",
                  "latency_s", "resource_use", "translation_checks", "verification_method", "result",
                  "confidence_type", "authority_state", "outcome_link", "later_appraisal"}


@pytest.fixture
def registry():
    r = registry_view()
    for cid in R.EVAL_ATTACH:
        r.set_state(cid, "ATTACHED")
    return r


@pytest.fixture(autouse=True)
def no_index(tmp_path, monkeypatch):
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    return tmp_path / "index.json"


def compile_(registry, geometry, data, **extra):
    return reason({"problem_id": "p", "compile": {"geometry": geometry, "data": data, **extra}}, registry=registry)


def test_receipt_carries_every_directive_field_and_creates_no_authority(registry):
    r = compile_(registry, {"geometry": "optimization", "graph_structure": True}, maxflow_instance(3)[0])
    assert RECEIPT_FIELDS <= set(r) and r["authority_created"] is False
    assert r["authority_state"] == "EXISTING_KERNEL_GATE_REQUIRED"
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == "cognition.flow_maxflow"
    assert r["confidence_type"] == "optimality_certificate" and r["intermediate_receipts"]


def test_legal_or_value_questions_route_to_qualified_human_judgment_without_a_vote(registry):
    for geometry in ({"geometry": "legal"}, {"geometry": "normative"}, {"human_judgment_required": True},
                     {"geometry": "optimization", "rights_impact": True}):
        r = compile_(registry, geometry, maxflow_instance(3)[0])
        assert r["state"] == "HUMAN_JUDGMENT_REQUIRED" and not r["intermediate_receipts"]
        packet = r["result"]
        assert "majority" in packet["decision_authority"] and "refuse" in packet["refusal_rights"]


def test_prohibited_harm_is_refused_before_optimisation(registry):
    for consequence in ({"rights": 0.1}, {"lawful": False}, {"consent": False}):
        r = compile_(registry, {"geometry": "optimization"}, maxflow_instance(3)[0], consequence=consequence)
        assert r["state"] == "PROHIBITED" and not r["methods_considered"]


def test_high_consequence_raises_requirements_and_does_not_route_to_a_formal_organ(registry):
    data = {"factors": [{"name": "a", "low": 1, "central": 2, "high": 3}]}
    r = compile_(registry, {"geometry": "estimate", "consequence_class": "financial"}, data)
    assert r["method_or_composition_selected"] == "cognition.estimation"
    assert any("Kernel Gate" in q for q in r["requirements"])
    assert any(t["operator_id"] == "consequence_raises_requirements" for t in r["transformations"])


def test_a_geometry_no_method_serves_becomes_a_genesis_ready_deficit(registry):
    r = compile_(registry, {"geometry": "optimization", "subgeometry": "protein folding"}, {"sequence": "ACDE"})
    deficit = r["capability_deficit"]
    assert r["state"] == "CAPABILITY_DEFICIT" and deficit["verification"]["verified"] is True
    assert deficit["search_order"][0] == "attached" and "genesis" in deficit["route"]


def test_frozen_negative_evidence_changes_routing(registry, no_index):
    data = maxflow_instance(3)[0]
    assert compile_(registry, {"geometry": "optimization"}, data)["method_or_composition_selected"] == \
        "cognition.flow_maxflow"
    no_index.write_text(json.dumps({"genomes": {"flow_maxflow": {"status": "REJECTED"}}, "recipes": {},
                                    "routing": {}}))
    r = compile_(registry, {"geometry": "optimization"}, data)
    assert r["state"] == "CAPABILITY_DEFICIT"
    assert {"method": "cognition.flow_maxflow", "why": "frozen admission status REJECTED"} in r["methods_rejected"]


def test_a_composition_without_verified_lift_yields_to_its_cheaper_constituent(registry, no_index):
    no_index.write_text(json.dumps({"genomes": {}, "routing": {},
                                    "recipes": {"graph_then_allocate": {"lift": False,
                                                                        "prefer": "flow_reinforce_greedy"}}}))
    r = compile_(registry, {"geometry": "optimization"}, R.f3(3)["payload"])
    assert any(x["method"] == "composition:graph_then_allocate" and "no lift" in x["why"]
               for x in r["methods_rejected"])


def test_plan_only_records_operator_transformations(registry):
    r = compile_(registry, {"geometry": "optimization", "graph_structure": True, "consequence_class": "irreversible"},
                 R.f3(3)["payload"], execute=False)
    assert r["state"] == "PLANNED" and not r["intermediate_receipts"]
    ops = {t["operator_id"] for t in r["transformations"]}
    assert {"bottleneck", "reversibility", "consequence_raises_requirements", "premortem"} <= ops


def test_unknown_geometry_fields_are_refused_and_unknowns_stay_unknown(registry):
    with pytest.raises(Exception):
        compile_(registry, {"geometry": "optimization", "omniscience": True}, {})
    g = compiler.CompetencyGeometry.parse({"geometry": "prediction"})
    assert g.known() == {"geometry": "prediction"} and g.forecast_horizon is None
