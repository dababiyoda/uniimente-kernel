"""Directive section 27: "I want X" becomes a governed draft; founder-only gates clear only on founder answers."""
from __future__ import annotations

import pytest

from egregore.contracts import ContractError
from tests.unit.test_goal_gravity import AUTH_REF, T0, T1, T2, T3, governor, make_loop, stack  # noqa: F401

AUTHORITY = {"authorized_by": "alfonso_lopez", "authorization_ref": AUTH_REF, "legal_principal": "alfonso_lopez",
             "max_consequence_class": "internal_write"}
SECTION_27 = ("desired_future_state", "current_position", "critical_assumptions", "active_node", "active_gate",
              "single_bottleneck_metric", "relevant_environmental_signals", "available_capabilities",
              "missing_capabilities", "next_autonomous_work", "next_prepared_work", "founder_required_decisions",
              "evidence_state", "review_trigger")


def gate_items(turn):
    return [i for i in turn.routing["immediate"] + turn.routing["batched"] if i["category"] == "authorization"]


def test_a_statement_becomes_a_draft_with_every_field_and_no_authority(stack):
    loop = make_loop(stack)
    draft = loop.intake.draft("I want a profitable robotics company within three years", now=T0)
    assert set(draft["fields"]) == set(SECTION_27)
    assert draft["fields"]["current_position"] == "unresolved" and draft["fields"]["critical_assumptions"] == "unresolved"
    assert set(draft["authority"].values()) == {"unresolved"}
    assert loop.registry.goals() == []   # a draft is not a goal
    with pytest.raises(ContractError):
        loop.intake.authorize_draft(draft["draft_id"], authority={}, now=T0)
    with pytest.raises(ContractError):
        loop.intake.authorize_draft(draft["draft_id"], authority={**AUTHORITY, "legal_principal": "unresolved"}, now=T0)


def test_the_authorized_draft_walks_two_founder_gates_and_reports_all_fourteen_fields(stack):
    loop = make_loop(stack)
    draft = loop.intake.draft("I want a profitable robotics company within three years", now=T0)
    goal_id = loop.intake.authorize_draft(draft["draft_id"], authority=AUTHORITY, now=T0)
    loop.registry.wake(goal_id, reason="new goal", now=T1)
    t1 = loop.turn(trigger_id="t1", now=T1, resources=governor(), evidence_confidence=0.9)
    [g0] = gate_items(t1)
    assert g0["evidence_on_accept"]["method"] == "human_decision" and t1.processed[0]["active_node_id"] == "G0"
    status = loop.status(goal_id, now=T1)
    for key in ("desired_state", "current_position", "critical_assumptions", "active_node", "active_gate",
                "single_bottleneck_metric", "relevant_environmental_signals", "available_capabilities",
                "missing_capabilities", "next_autonomous_work", "prepared_work", "founder_required_decisions",
                "evidence_state", "review_trigger"):
        assert key in status
    assert status["critical_assumptions"][0].startswith("UNRESOLVED") and g0["item_id"] in status["founder_required_decisions"]
    loop.founder_answer(g0["item_id"], decision="accept", actor="alfonso_lopez", note="yes, that is the destination", now=T2)
    loop.registry.wake(goal_id, reason="answered", now=T2)
    t2 = loop.turn(trigger_id="t2", now=T2, resources=governor(), evidence_confidence=0.9)
    assert t2.processed[0]["active_node_id"] == "G1"
    [g1] = gate_items(t2)
    assert g1["item_id"] != g0["item_id"] and "accepts a backcast plan" in g1["title"]
    # The draft goal never completes by itself: the plan gate needs a founder answer too.
    assert loop.registry.state(goal_id).status != "completed"
