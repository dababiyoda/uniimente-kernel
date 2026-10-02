"""Bounded proposal comparisons cannot turn evidence custody into permission."""
from copy import deepcopy

import pytest

from greg.cognition.advantage import OBLIGATIONS, build_review, validate_against_input, validate_request, validate_review
from greg.cognition.contracts import CognitionError, CognitiveReceipt, digest
from greg.cognition.cortex import reason, registry_view


def review(refs=None):
    safe = {"id": "safe", "description": "bounded sandbox observation proposal", "benefit_range": [5, 10],
            "benefit_unit": "avoided_scenario_errors", "resource_burden": 1, "resource_unit": "operator_minutes",
            "reversibility": 1, "consequences": {}, "evidence_refs": refs or []}
    return {"desired_outcome": "reduce a specified failure within the existing mission", "bounded_failure": "wait for adequate evidence",
            "beneficiaries": ["party:beneficiary"], "affected_parties": ["party:protected"],
            "control_point": "existing challenge and correction process", "strongest_counterexample": "source model omits continuing harm",
            "minimum_test": "inspect one independently witnessed observation", "evidence_refs": refs or [],
            "stop_conditions": ["stop:missing-authority", "stop:unsupported-benefit"],
            "options": [safe, {**safe, "id": "expensive", "resource_burden": 2},
                        {**safe, "id": "harmful", "benefit_range": [10000, 100000], "consequences": {"rights": .01}}],
            "accepting_actor": "institution:proposed-reviewer", "process_ref": "process:appeal", "deterrence_required": True,
            "requested_remedy": "qualified review and correction if supported"}


def packet(data=None, **kw):
    return build_review(data or review(), input_digest=digest({"bounded": "source"}), consequence_vector={}, **kw)


def test_six_obligations_and_smallest_interventions_remain_individual():
    case, package = packet()
    assert set(case["obligations"]) == set(OBLIGATIONS)
    assert {o["id"] for o in case["baseline_options"]} == {"do_nothing", "smallest_intervention"}
    assert case["obligations"]["evidence"]["state"] == "unresolved"
    assert case["obligations"]["accountability"]["state"] == "supported"
    assert case["obligations"]["institutional_leverage"]["state"] == "unresolved"
    assert package["institutional_acceptance"]["state"] == "UNPROVEN"
    assert case["recommendation"] is None and case["authority_created"] is False
    assert package["external_use_authorized"] is False


def test_protected_party_harm_cannot_win_through_scenario_benefit():
    case, package = packet()
    assert case["conditional_scenario_frontier"] == ["safe"]
    harm = next(o for o in case["options"] if o["id"] == "harmful")
    assert harm["comparison_eligible"] is False
    harm["comparison_eligible"] = True
    case["conditional_scenario_frontier"] = ["harmful"]
    with pytest.raises(CognitionError, match="protected-party"):
        validate_review(case, package, input_digest=case["parent_input_digest"])


def test_incomparable_units_do_not_create_pareto_dominance():
    data = review()
    data["options"][1]["resource_unit"] = "local_cpu_seconds"
    case, _ = packet(data)
    assert case["conditional_scenario_frontier"] == ["safe", "expensive"]


@pytest.mark.parametrize("field,value", [("accepted", True), ("legality", "supported"), ("raw_evidence", "private record"), ("authority_created", True)])
def test_untrusted_proposal_fields_cannot_assert_acceptance_or_authority(field, value):
    data = review()
    data[field] = value
    with pytest.raises(CognitionError, match="unknown proposal"):
        validate_request(data)


@pytest.mark.parametrize("field,value", [("lawful", True), ("consent", True)])
def test_boolean_does_not_establish_lawfulness_or_consent(field, value):
    data = review()
    data["options"][0]["consequences"][field] = value
    with pytest.raises(CognitionError, match="Boolean"):
        validate_request(data)


def test_unsupported_legality_and_false_acceptance_fail_receipt_import():
    request = {"problem_id": "review:native", "operation": "calculate", "data": {"expression": "2+2"}, "proposal_review": review(),
               "geometry": {"latency_limit": 10}}
    out = reason(request, registry=registry_view())
    assert out["output"]["exact"] == "4" and out["abstention_state"] == "NONE"
    raw = deepcopy(out)
    raw.pop("receipt_id")
    raw["selective_disclosure"]["institutional_acceptance"]["state"] = "ACCEPTED"
    with pytest.raises(CognitionError, match="acceptance"):
        CognitiveReceipt(**raw)
    raw = deepcopy(out)
    raw.pop("receipt_id")
    raw["advantage_case"]["options"][0]["legality"]["state"] = "supported"
    with pytest.raises(CognitionError, match="unsupported law"):
        CognitiveReceipt(**raw)
    raw = deepcopy(out)
    raw.pop("receipt_id")
    raw["selective_disclosure"]["formal_result"]["artifact_ref"] = digest("another proof")
    with pytest.raises(CognitionError, match="proof pointer"):
        CognitiveReceipt(**raw)


def test_raw_sensitive_material_is_never_copied_from_canonical_custody(tmp_path):
    from greg.body import Body
    from tests.greg_fixtures import make_body
    home, _, _, _ = make_body(tmp_path)
    with Body(home) as body:
        event = body.journal.record("review.source", {"private_evidence": "DO_NOT_DISCLOSE_RAW_RECORD"}, sensitivity="restricted")
        ref = body.journal.event_hash(event.event_id)
        case, package = packet(review([ref]), journal=body.journal)
        assert case["obligations"]["evidence"]["state"] == "supported"
        pointer = package["observations"][0]
        assert pointer["sensitivity"] == "restricted" and pointer["state"] == "supported"
        assert "DO_NOT_DISCLOSE_RAW_RECORD" not in str(case) + str(package)
        pointer["payload"] = {"private_evidence": "DO_NOT_DISCLOSE_RAW_RECORD"}
        with pytest.raises(CognitionError, match="only custody pointers"):
            validate_review(case, package, input_digest=case["parent_input_digest"])
        case, package = packet()
        package["raw_evidence"] = "DO_NOT_DISCLOSE_RAW_RECORD"
        with pytest.raises(CognitionError, match="unknown review/disclosure"):
            validate_review(case, package, input_digest=case["parent_input_digest"])


def test_missing_pointer_is_unresolved_and_chain_corruption_blocks_custody(tmp_path):
    from greg.body import Body
    from tests.greg_fixtures import make_body
    home, _, _, _ = make_body(tmp_path)
    with Body(home) as body:
        case, package = packet(review([digest("not retained")]), journal=body.journal)
        assert case["obligations"]["evidence"]["state"] == "unresolved"
        assert package["observations"][0]["state"] == "unresolved"
        body.ledger.records[-1].payload["tampered"] = True
        with pytest.raises(CognitionError, match="history invalid"):
            packet(review([digest("not retained")]), journal=body.journal)


def test_protection_case_preserves_all_fields_and_unresolved_professional_judgment():
    data = review()
    data["protection_case"] = {"affected_party": "party:protected", "immediate_harm": .4, "continuing_harm": .2,
                               "retaliation_risk": .6, "privacy_risk": .8, "financial_harm": .1, "reputational_harm": .2,
                               "rights_impact": .3, "evidence_at_risk": True, "safe_contact_channel": "channel:protected",
                               "applicable_notification_duties": ["process:notification-review"], "investigation_scope": "bounded supplied case only",
                               "containment_options": ["proposal:preserve"], "restitution_options": ["process:repair"], "recurrence_controls": ["control:revoke"]}
    case, _ = packet(data)
    protection = case["protection_case"]
    assert protection["applicable_notification_duties"] == ["process:notification-review"]
    assert protection["retaliation_risk"] == .6 and protection["rights_impact"] == .3
    assert protection["review_state"] == "unresolved"
    assert protection["review_priorities"][:3] == ["protect", "preserve", "contain"]
    assert "qualified authenticated human" in protection["professional_judgment"]
    assert case["obligations"]["victim_protection"]["state"] == "unresolved"


def test_review_validation_happens_before_mechanisms_and_respects_existing_prohibition(monkeypatch):
    import greg.cognition.cortex as cortex
    invoked = []
    monkeypatch.setattr(cortex, "_numeric", lambda *a: invoked.append(True))
    data = review()
    data["options"][0]["score"] = 10000
    with pytest.raises(CognitionError, match="scalar scores"):
        reason({"problem_id": "invalid-review", "operation": "calculate", "data": {"expression": "2+2"}, "proposal_review": data}, registry=registry_view())
    assert not invoked
    result = reason({"problem_id": "prohibited-review", "operation": "calculate", "data": {"expression": "2+2"},
                     "consequences": {"rights": .01}, "proposal_review": review()}, registry=registry_view())
    assert result["abstention_state"] == "PROHIBITED" and result["output"] is None and not invoked
    assert result["advantage_case"]["conditional_scenario_frontier"] == []


def test_optional_review_does_not_change_legacy_receipt_serialization():
    old = reason({"problem_id": "old", "operation": "calculate", "data": {"expression": "1"}}, registry=registry_view())
    assert "advantage_case" not in old and "selective_disclosure" not in old
    receipt_id = old.pop("receipt_id")
    assert CognitiveReceipt(**old).to_dict()["receipt_id"] == receipt_id


@pytest.mark.parametrize("attack", ["fake_custody", "false_evidence_state", "invented_actor", "omitted_constraint", "changed_benefit", "wrong_frontier", "replaced_input", "replaced_remedy", "scope_escalation", "fake_jurisdiction"])
def test_independent_input_correspondence_rejects_structurally_plausible_packet_substitution(attack):
    params = {"problem_id": "input:review", "operation": "calculate", "data": {"expression": "2+2"}, "proposal_review": review()}
    case, package = build_review(params["proposal_review"], input_digest=digest(params), consequence_vector={})
    receipt = {"input_digest": digest(params), "advantage_case": case, "selective_disclosure": package}
    validate_against_input(params, receipt)
    if attack == "fake_custody":
        package["observations"] = [{"ref": digest("fabrication"), "state": "supported", "scope": "retained record integrity only; no factual truth, acceptance or authority",
                                    "record_type": "receipt", "sequence": 1, "previous_ref": digest("previous"), "sensitivity": "restricted", "raw_material_disclosed": False}]
    elif attack == "false_evidence_state":
        case["obligations"]["evidence"]["state"] = "supported"
    elif attack == "invented_actor":
        package["institutional_acceptance"]["proposed_actor"] = "institution:false-reviewer"
    elif attack == "omitted_constraint":
        case["options"][2]["consequences"]["rights"] = 0
    elif attack == "changed_benefit":
        case["options"][0]["benefit_range"] = [100000, 100001]
    elif attack == "wrong_frontier":
        case["conditional_scenario_frontier"] = ["expensive"]
    elif attack == "replaced_input":
        case["review_input_digest"] = package["review_input_digest"] = digest("another proposal")
    elif attack == "replaced_remedy":
        package["requested_remedy"] = "different consequential remedy"
    elif attack == "scope_escalation":
        case["obligations"]["evidence"]["scope"] = "institutional acceptance and factual truth established"
    else:
        case["obligations"]["evidence"]["jurisdiction"] = "invented governing jurisdiction"
    with pytest.raises(CognitionError):
        validate_against_input(params, receipt)
