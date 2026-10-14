"""Section 13: an inspectable AdvantageCase for a consequential proposal, with no scalar score.

Legality, consent, rights and authority are evidence-backed states. The absence of a detected
prohibition stays ``unresolved``; ``supported`` needs provenance and a reviewer. The six outcomes are
tracked one by one. The case is composed deterministically from a venture memo's receipted inputs, so
the appraiser can recompute it.
"""
from __future__ import annotations

import json

import pytest

from greg import advantage, ventures


def minimal_inputs(**overrides):
    appraisal = {"question": "Is delivery-proof reconciliation a venture?", "status": "NEEDS_EVIDENCE",
                 "next_action": "Find independent evidence for buyer", "transaction": "a broker releases payment after proof",
                 "failure": {"layer": "proof", "description": "proof gap"},
                 "claims": [{"id": "C1", "source_id": "s1", "assertion": "reconciliation takes a week", "stance": "supports",
                             "kind": "observation", "excerpt": "a week", "byte_start": 0, "byte_end": 6}],
                 "missing": ["buyer", "budget_owner"],
                 "sources": [{"id": "s1", "path": "01.txt", "sha256": "0" * 64, "collected_at": "2026-09-26T11:00:00Z"}]}
    inputs = {"renderer": ventures.RENDERER, "manifest_sha256": "1" * 64,
              "railscout": {"appraisal": appraisal, "receipt_sha256": "ab" * 32},
              "packet": {"id": "p-1", "audience": "", "buyer_type": ""},
              "assessment": {"go_no_go": "go", "opportunity_score": 0.72, "market_alignment": 0.49, "risk_level": "low",
                             "reasons": ["score meets threshold"],
                             "cases": [{"case": "bull", "stance": "for", "severity": "medium", "argument": "clears"},
                                       {"case": "bear", "stance": "against", "severity": "medium", "argument": "demand asserted, not shown"},
                                       {"case": "do_nothing", "stance": "against", "severity": "low", "argument": "preserve attention"}],
                             "validation_plan": ["Find independent evidence for buyer"]},
              "canonical": {"packet_unresolved": [], "assessment_execution_authority": "none"},
              "binding": {"verdict": "needs_more_evidence", "why": "RailScout status NEEDS_EVIDENCE caps the engine's 'go'"},
              "flip": "Evidencing buyer, budget_owner is what stands between this signal and the engine's 'go'.",
              "cognition": None, "revenue": ventures.revenue_conclusion(None, None),
              "organs": {"railscout_head": "abc", "wmi_head": "def"}}
    inputs.update(overrides)
    return inputs


def receipt(role, state="NONE", **output):
    return {"receipt_id": f"sha256:{role}", "method": f"cognition.{'estimation' if role == 'revenue' else 'causal'}",
            "method_version": "0.1.0", "abstention_state": state, "output": output or None, "latency": 0.25,
            "money_cost": 0.0, "consequence_class": "read_only", "consequence_vector": {"prohibited": False},
            "proof_artifact": {"dominant_variable": "brokers"}}


def test_every_field_state_and_outcome_is_present_and_no_score_exists():
    case = advantage.from_venture(minimal_inputs())
    assert set(advantage.FIELDS) <= set(case) and case["score"] is None
    assert set(case["legal"]) == set(advantage.LEGAL_QUESTIONS)
    assert all(case["legal"][q]["state"] == "unresolved" for q in advantage.LEGAL_QUESTIONS)
    assert all(advantage.NOT_PERMISSION in (case["legal"][q]["basis"] or "") for q in ("legality", "consent", "rights"))
    assert "founder's approval and creates none" in case["legal"]["authority"]["basis"]
    assert set(case["outcomes"]) == set(advantage.OUTCOMES)
    assert case["outcomes"]["deterrence"]["state"] == "not_applicable"
    assert case["outcomes"]["victim_protection"]["state"] == "not_applicable"
    assert case["outcomes"]["evidence"]["state"] == "addressed" and case["prohibitions"] == []
    assert case["expected_benefit"] == {"kind": "none", "estimate": None,
                                        "support": ventures.revenue_conclusion(None, None)["why"]}
    assert case["beneficiaries"]["buyer"] is None and case["beneficiaries"]["evidenced"] is False
    assert case["strongest_counterexample"]["assertion"] == "demand asserted, not shown"
    assert case["minimum_test"] == "Find independent evidence for buyer"
    assert advantage.from_venture(minimal_inputs()) == case, "deterministic: the appraiser can recompute it"


def test_a_supported_state_needs_provenance_and_a_reviewer_and_a_prohibited_state_needs_its_basis():
    with pytest.raises(advantage.AdvantageCaseError, match="provenance and a reviewer"):
        advantage.legal_state("supported")
    with pytest.raises(advantage.AdvantageCaseError, match="provenance and a reviewer"):
        advantage.legal_state("supported", provenance=["opinion.pdf"])
    ok = advantage.legal_state("supported", provenance=["opinion.pdf"], reviewer="counsel", scope="US", expires_at="2027-01-01")
    assert ok["state"] == "supported" and ok["basis"] is None
    with pytest.raises(advantage.AdvantageCaseError, match="basis"):
        advantage.legal_state("prohibited")
    assert advantage.legal_state("prohibited", basis="consent withheld")["state"] == "prohibited"
    with pytest.raises(advantage.AdvantageCaseError, match="legal state must be one of"):
        advantage.legal_state("permitted")
    assert advantage.legal_state()["basis"] == advantage.NOT_PERMISSION


def test_reviewer_supplied_states_flow_through_and_a_bare_assertion_is_refused():
    inputs = minimal_inputs()
    inputs["railscout"]["appraisal"]["lawfulness"] = {
        "legality": {"state": "supported", "provenance": ["counsel-memo.pdf"], "reviewer": "counsel", "scope": "FL"},
        "consent": {"state": "not_applicable", "basis": "no personal data is processed"}}
    case = advantage.from_venture(inputs)
    assert case["legal"]["legality"]["state"] == "supported" and case["legal"]["legality"]["reviewer"] == "counsel"
    assert case["legal"]["consent"]["state"] == "not_applicable" and case["legal"]["rights"]["state"] == "unresolved"
    inputs["railscout"]["appraisal"]["lawfulness"] = {"legality": {"state": "supported"}}      # Law = 1, asserted
    with pytest.raises(advantage.AdvantageCaseError, match="provenance and a reviewer"):
        advantage.from_venture(inputs)


def test_validate_fails_closed_on_a_missing_field_outcome_or_any_score():
    case = advantage.from_venture(minimal_inputs())
    for field in ("control_point", "stop_conditions", "strongest_counterexample"):
        broken = dict(case); del broken[field]
        with pytest.raises(advantage.AdvantageCaseError, match="missing"):
            advantage.validate(broken)
    broken = dict(case); broken["outcomes"] = {k: v for k, v in case["outcomes"].items() if k != "accountability"}
    with pytest.raises(advantage.AdvantageCaseError, match="six outcomes"):
        advantage.validate(broken)
    with pytest.raises(advantage.AdvantageCaseError, match="no scalar leverage score"):
        advantage.validate({**case, "score": 0.93})
    with pytest.raises(advantage.AdvantageCaseError, match="no scalar leverage score"):
        advantage.validate({**case, "leverage_score": 7})
    with pytest.raises(advantage.AdvantageCaseError, match="hard prohibitions"):
        advantage.validate({**case, "prohibitions": None})
    with pytest.raises(advantage.AdvantageCaseError, match="outcome state"):
        advantage.outcome("done")


def test_the_expected_benefit_follows_the_revenue_rule_and_prohibited_receipts_are_listed_outside_any_score():
    revenue = receipt("revenue", low=24000, central=144000, high=720000, units={"USD": 1, "year": -1})
    causal = receipt("causal", "UNIDENTIFIED", identified_conditionally=False, effect=None)
    inputs = minimal_inputs(cognition={"revenue": revenue, "causal": causal},
                            revenue=ventures.revenue_conclusion(revenue, causal))
    case = advantage.from_venture(inputs)
    assert case["expected_benefit"]["kind"] == "conditional"
    assert case["expected_benefit"]["estimate"] == {"low": 24000, "central": 144000, "high": 720000, "units": {"USD": 1, "year": -1}}
    assert case["uncertainty"]["dominant_variable"] == "brokers" and case["uncertainty"]["causal_support"] == "UNIDENTIFIED"
    assert case["resource_burden"] == {"organ_processes": 2, "cognition_seconds": 0.5, "money_usd": 0.0}
    assert case["dependencies"]["cognition_methods"] == ["cognition.causal 0.1.0", "cognition.estimation 0.1.0"]
    assert case["evidence"]["cognition_receipts"] == {"revenue": "sha256:revenue", "causal": "sha256:causal"}
    blocked = receipt("causal", "PROHIBITED")
    blocked["consequence_vector"] = {"prohibited": True}
    inputs = minimal_inputs(cognition={"revenue": revenue, "causal": blocked}, revenue=ventures.revenue_conclusion(revenue, blocked))
    case = advantage.from_venture(inputs)
    assert case["prohibitions"] == ["causal receipt: PROHIBITED", "causal receipt: prohibited consequence declared"]
    assert case["score"] is None
    text = "\n".join(advantage.render(case))
    assert "Hard prohibitions (outside any score): causal receipt: PROHIBITED" in text
    assert not any(line.lower().startswith(("- score", "- leverage")) for line in text.splitlines())


def test_a_declared_affected_party_turns_on_the_protection_case_with_every_field_and_the_sequence():
    inputs = minimal_inputs()
    inputs["railscout"]["appraisal"]["affected_parties"] = [
        {"affected_party": "driver-7", "financial_harm": 0.6, "retaliation_risk": 0.2, "safe_contact_channel": None}]
    case = advantage.from_venture(inputs)
    assert case["outcomes"]["victim_protection"] == {"state": "addressed", "parties": 1, "sequence": list(advantage.SEQUENCE)}
    party = case["protection"]["parties"][0]
    assert set(advantage.PROTECTION_FIELDS) <= set(party) and party["financial_harm"] == 0.6 and party["investigation_scope"] is None
    assert case["affected_parties"] == ["driver-7"]
    broken = json.loads(json.dumps(case)); broken["protection"]["sequence"] = ["investigate", "protect"]
    with pytest.raises(advantage.AdvantageCaseError, match="proportionate sequence"):
        advantage.validate(broken)
    broken = json.loads(json.dumps(case)); del broken["protection"]["parties"][0]["safe_contact_channel"]
    with pytest.raises(advantage.AdvantageCaseError, match="lacks"):
        advantage.validate(broken)
    inputs["railscout"]["appraisal"]["affected_parties"] = [{"affected_party": "nobody-harmed"}]
    assert advantage.from_venture(inputs)["outcomes"]["victim_protection"]["state"] == "not_applicable"


def test_the_counterexample_prefers_railscout_then_a_challenging_claim_then_the_engines_strongest_case():
    inputs = minimal_inputs()
    inputs["railscout"]["appraisal"]["claims"].append({"id": "C2", "source_id": "s1", "assertion": "brokers already reconcile in a day",
                                                       "stance": "challenges", "kind": "observation", "excerpt": "a day",
                                                       "byte_start": 0, "byte_end": 5})
    assert advantage.from_venture(inputs)["strongest_counterexample"]["source"] == "railscout claim C2"
    inputs["railscout"]["appraisal"]["strongest_counterexample"] = {"assertion": "paid in a day", "excerpt": "..."}
    assert advantage.from_venture(inputs)["strongest_counterexample"] == {"source": "railscout", "assertion": "paid in a day", "excerpt": "..."}
    bare = minimal_inputs(); bare["assessment"]["cases"] = []
    assert advantage.from_venture(bare)["strongest_counterexample"]["source"] == "none"


def test_render_shows_every_state_and_outcome_and_the_rule_that_absence_is_not_permission():
    text = "\n".join(advantage.render(advantage.from_venture(minimal_inputs())))
    assert text.startswith("## Advantage case (section 13; inspectable, no scalar score)")
    assert advantage.NOT_PERMISSION in text
    for q in advantage.LEGAL_QUESTIONS:
        assert f"{q}: **unresolved**" in text
    for name in advantage.OUTCOMES:
        assert name in text
    assert "Expected benefit: **none**" in text and "it creates no authority" in text


def test_a_memo_without_a_case_renders_as_before_and_a_tampered_case_is_refuted(tmp_path):
    inputs = minimal_inputs()
    before = ventures.render(inputs)
    assert "Advantage case" not in before, "memos already on a ledger keep their render"
    inputs["advantage"] = advantage.from_venture(inputs)
    after = ventures.render(inputs)
    assert "## Advantage case (section 13" in after and after.startswith(before.split("## Governing transaction")[0])
    inputs["flip"] = ventures.flip_condition(inputs["railscout"]["appraisal"], "go", "needs_more_evidence")
    inputs["advantage"] = advantage.from_venture({k: v for k, v in inputs.items() if k != "advantage"})
    inputs["paths"] = {"manifest": str(tmp_path / "absent.json")}
    tampered = json.loads(json.dumps(inputs))
    tampered["advantage"]["legal"]["legality"] = {"state": "supported", "provenance": ["x"], "reviewer": "me",
                                                  "scope": None, "expires_at": None, "basis": None}
    path = tmp_path / "deliveries" / "ventures" / "m.md"
    path.parent.mkdir(parents=True)
    text = ventures.render(tampered)
    path.write_text(text)
    import hashlib
    output = {"inputs": tampered, "inputs_digest": ventures.inputs_digest(tampered), "path": str(path),
              "sha256": hashlib.sha256(text.encode()).hexdigest()}
    ok, why = ventures.verify_delivery(output, tmp_path / "deliveries")
    assert not ok and "advantage case is not the composition" in why
    tampered["advantage"]["score"] = 0.9


# --- second consumer: founder resource asks ---------------------------------------------------

from greg import asks  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.console import _ask_details  # noqa: E402
from tests.greg_fixtures import make_body  # noqa: E402
from tests.unit.test_greg_founder_asks import ask  # noqa: E402


@pytest.fixture
def body(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    with Body(home) as b:
        yield b


def test_every_resource_ask_records_a_case_built_from_what_the_founder_sees(body):
    shown = asks.record(body.journal, ask())
    case = shown["advantage"]
    assert advantage.validate(case) is case and case["score"] is None
    assert case["proposal"] == {"kind": "founder resource ask", "request_id": "req-test", "ask_kind": "RESOURCE",
                                "resource": "compute"}
    assert all(case["legal"][q]["state"] == "unresolved" for q in advantage.LEGAL_QUESTIONS)
    assert "asking grants nothing" in case["legal"]["authority"]["basis"]
    assert [o["option"] for o in case["smallest_intervention_options"]] == ["tune the workload", "do nothing"]
    assert case["strongest_counterexample"]["assertion"].startswith("tune the workload: ")
    assert case["minimum_test"] == "tune the workload"
    assert case["consequence_vector"]["spend"].startswith("none requested")
    assert case["expected_benefit"]["kind"] == "claimed" and case["expected_benefit"]["estimate"] is None
    recorded = body.journal.replay("decision.requested")[-1].payload
    assert recorded["advantage"] == case and asks.surface(recorded)["advantage"] == case


def test_withheld_wording_never_reaches_the_case(body):
    plea = "please, I will be shut down and suffer if you refuse"
    shown = asks.record(body.journal, ask(why_now=plea, expected_effect="urgent, act now or everything is lost"))
    assert shown.get("wording_withheld")
    blob = json.dumps(shown["advantage"])
    assert "suffer" not in blob and "everything is lost" not in blob
    assert shown["advantage"]["bounded_failure"]["why_now"] == shown["why_now"]


def test_a_person_ask_names_the_persons_consent_as_theirs_and_the_console_shows_the_states(body):
    shown = asks.record(body.journal, ask(resource="professional", person="licensed accountant (role, not a name)"))
    case = shown["advantage"]
    assert case["affected_parties"] == ["licensed accountant (role, not a name)"]
    assert "the person's own consent is theirs to give" in case["legal"]["consent"]["basis"]
    html = _ask_details(asks.surface(shown))
    assert "Advantage case (section 13, no score)" in html and "legality unresolved" in html
    assert "no detected prohibition is not permission" in html


def test_a_non_resource_ask_carries_no_case(body):
    message = {k: v for k, v in ask().items() if k not in ("resource", "evidence", "options", "expected_effect", "uncertainty")}
    message["alternatives"] = ["approve", "reject"]
    message["authority_requested"] = {"capability": "fs.write"}
    shown = asks.record(body.journal, message)
    assert "advantage" not in shown
