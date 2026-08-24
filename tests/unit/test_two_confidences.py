"""CONTRADICTION-0003, closed and attacked.

One field was carrying two quantities. For routine actions they track together
and nobody notices; for a first canary they are opposite by construction, and
the only way past the Gate was to write a success prediction nobody believed.

Option A splits the field. Option B says what the floor is *for* once they are
separate. These tests pin both, and — more importantly — pin the thing that
would quietly undo them: the engine reading the prediction when it decides.
"""
from __future__ import annotations

import ast
import inspect
import os

import pytest

from policy import engine
from policy.engine import (CONTAINED_CLASSES, CONTAINMENT_REQUIREMENTS,
                           EVIDENCE_THRESHOLDS, Proposal, Verdict, evaluate)
from compiler.ucl_compiler import compile_constitution

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONTAINED = {"contained": True, "reversible": True, "observable": True,
             "killable": True, "proportionate": True}


@pytest.fixture(scope="module")
def compiled():
    return compile_constitution(ROOT)


def _proposal(**kw) -> Proposal:
    base = dict(
        actor="mp-001", legal_principal="alfonso_lopez",
        action_class="draft.publish", objective="t", payload={},
        target="sandbox:outbox", consequence_class="external_contact",
        evidence_confidence=0.9, evidence_refs=["sha256:" + "a" * 64],
        estimated_cost_usd=0.0, requested_capability="draft.publish",
        expected_outcome="queued", context=dict(CONTAINED))
    base.update(kw)
    return Proposal(**base)


# -- Option A: the two quantities are separate ------------------------------

def test_a_low_predicted_success_does_not_block_a_well_evidenced_action(compiled):
    """The bootstrap, broken.

    Before: to act externally you needed confidence >= 0.70; confidence came
    from calibration; calibration came from external outcomes; external
    outcomes required acting externally. The institution could only take
    actions it was already confident about.

    Now a genuinely uncertain experiment can be admitted on the strength of the
    argument for running it — which is what the founder ruled.
    """
    decision = evaluate(compiled,
                        _proposal(evidence_confidence=0.9,
                                  predicted_success_probability=0.05),
                        identity_ok=True, grant=None)

    assert decision.verdict is Verdict.ALLOW
    assert not any("confidence" in r for r in decision.reasons)


def test_a_high_predicted_success_cannot_rescue_a_poorly_evidenced_action(compiled):
    """The inverse, which matters more.

    If the split let a confident-sounding forecast substitute for evidence, it
    would have replaced one bad admission rule with a worse one. The floor
    still binds on evidence and only on evidence.
    """
    decision = evaluate(compiled,
                        _proposal(evidence_confidence=0.2,
                                  predicted_success_probability=0.99),
                        identity_ok=True, grant=None)

    assert decision.verdict is Verdict.DENY
    assert any("evidence confidence" in r for r in decision.reasons)
    assert "sufficient_evidence" in decision.missing


def test_the_floor_itself_did_not_move():
    """No part of this remedy is a discount.

    The tempting edit CONTRADICTION-0003 documents was 0.55 -> 0.71. The second
    most tempting is 0.70 -> 0.50, and it would be much harder to spot.
    """
    assert EVIDENCE_THRESHOLDS["external_contact"] == 0.7
    assert EVIDENCE_THRESHOLDS["financial"] == 0.8
    assert EVIDENCE_THRESHOLDS["irreversible"] == 0.9


def test_the_engine_never_reads_the_prediction_when_deciding():
    """The structural guard, over the AST rather than by reading carefully.

    A single `proposal.predicted_success_probability` in `evaluate` would
    re-fuse the two quantities while every test above still passed, because
    admission would only change in cases nobody wrote a test for. So the
    absence is asserted directly.
    """
    tree = ast.parse(inspect.getsource(engine.evaluate))
    reads = [n for n in ast.walk(tree)
             if isinstance(n, ast.Attribute)
             and n.attr == "predicted_success_probability"]
    assert reads == [], (
        "policy.engine.evaluate reads the predicted success probability. "
        "Admission must depend on evidence_confidence only — the prediction "
        "exists to be scored against reality, not to buy permission.")


def test_the_prediction_is_optional_and_absence_is_not_a_number():
    """Most actions are not experiments and predict nothing."""
    assert _proposal().predicted_success_probability is None


# -- Option B: what the floor is for ----------------------------------------

@pytest.mark.parametrize("prop", sorted(CONTAINMENT_REQUIREMENTS))
def test_every_containment_property_is_individually_required(compiled, prop):
    """Drop exactly one and the action is refused, naming the one dropped."""
    context = dict(CONTAINED)
    del context[prop]

    decision = evaluate(compiled, _proposal(context=context),
                        identity_ok=True, grant=None)

    assert decision.verdict is Verdict.DENY
    assert f"containment:{prop}" in decision.missing


def test_an_undeclared_containment_property_is_refused_not_assumed(compiled):
    """Fails closed. Silence is not assent.

    An action that forgot to declare its kill switch is refused exactly like
    one that has none, because from the Gate's position those are the same
    thing.
    """
    decision = evaluate(compiled, _proposal(context={}),
                        identity_ok=True, grant=None)

    assert decision.verdict is Verdict.DENY
    assert len([m for m in decision.missing if m.startswith("containment:")]) \
        == len(CONTAINMENT_REQUIREMENTS)


def test_a_truthy_value_is_not_accepted_in_place_of_a_declaration(compiled):
    """`"yes"`, `1`, `"no"` — all refused. Only `True` declares.

    A truthiness check would accept the string `"false"`, which is exactly the
    kind of near-miss that turns a real requirement into a formality.
    """
    for sneaky in ("yes", 1, "false", [1], {"a": 1}):
        context = dict(CONTAINED)
        context["killable"] = sneaky
        decision = evaluate(compiled, _proposal(context=context),
                            identity_ok=True, grant=None)
        assert decision.verdict is Verdict.DENY, f"{sneaky!r} was accepted"
        assert "containment:killable" in decision.missing


def test_containment_is_additional_to_the_floor_and_not_a_substitute(compiled):
    """Perfectly contained and poorly evidenced is still refused.

    Option B reinterprets what the floor is protecting; it does not hand out an
    exemption to anything that declares itself safe.
    """
    decision = evaluate(compiled, _proposal(evidence_confidence=0.1),
                        identity_ok=True, grant=None)

    assert decision.verdict is Verdict.DENY
    assert any("evidence confidence" in r for r in decision.reasons)


def test_internal_actions_are_not_asked_to_declare_containment(compiled):
    """A containment form on every log write is a form nobody reads.

    The requirement is scoped to actions that touch the outside world, so that
    declaring it stays a real statement rather than boilerplate.
    """
    decision = evaluate(compiled,
                        _proposal(consequence_class="internal_write",
                                  evidence_confidence=0.9, context={}),
                        identity_ok=True, grant=None)

    assert not any(m.startswith("containment:") for m in decision.missing)
    assert "internal_write" not in CONTAINED_CLASSES


def test_every_class_that_reaches_outside_must_declare_containment():
    """The scope, pinned. Adding a new external class without adding it here
    would silently exempt it."""
    assert set(CONTAINED_CLASSES) == {"external_contact", "financial",
                                      "irreversible"}
    for cls in CONTAINED_CLASSES:
        assert EVIDENCE_THRESHOLDS[cls] >= 0.7


def test_the_founders_seven_criteria_are_all_represented():
    """The ruling named: evidenced, contained, authorized, reversible,
    observable, killable, proportionate.

    Five are this table. `evidenced` is the floor above it. `authorized` is
    enforced in the Gate at step 7, and this docstring first claimed it was
    "already enforced by the grant and identity checks" — which was wrong, and
    was shown to be wrong by
    `test_the_unauthorized_canary_does_not_reach_a_receipt_by_default` within
    the hour. The Gate self-issued a grant when none was supplied.

    The correction is kept visible rather than tidied away, because the way it
    was found is the useful part: the evidence floor had been refusing external
    proposals earlier in the pipeline, so the missing check had never been
    reachable. Removing one conflation exposed another.
    """
    assert set(CONTAINMENT_REQUIREMENTS) == {
        "contained", "reversible", "observable", "killable", "proportionate"}


def test_an_external_action_cannot_be_granted_by_the_run_that_proposes_it(compiled):
    """`authorized`, the seventh criterion, enforced where it belongs.

    Self-issuance is acceptable for internal effects and is authority creation
    for external ones. A run that both proposes and authorises an external act
    has expanded its own sovereignty, which is the one thing the standing rules
    never permit — however well-evidenced and however contained.
    """
    from compiler.ucl_compiler import compile_constitution as _cc  # noqa: F401
    from provenance.ledger import EvidenceLedger
    from provenance.commit_witness import WitnessSigner
    from identity.machine_passport import PassportRegistry
    from policy.consequence_gate import ConsequenceGate

    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports,
                           ledger=ledger, signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez", declared_capabilities=["draft.publish"],
        budget_ceiling_usd=5.0, consequence_class="external_contact")

    record = gate.run(
        _proposal(actor=actor.passport_id, evidence_confidence=0.99),
        executor=lambda p: {"observed_outcome": "queued",
                            "result_class": "positive"})

    assert record.state == "refused"
    assert any("does not issue its own authority" in r
               for r in record.refusal_reasons)

    # Internal effects may still be self-granted: the restriction is scoped to
    # what reaches outside, not applied to everything as a precaution.
    internal = gate.run(
        _proposal(actor=actor.passport_id, consequence_class="internal_write",
                  evidence_confidence=0.9, context={}),
        executor=lambda p: {"observed_outcome": "queued",
                            "result_class": "positive"})
    assert internal.state == "recorded"
