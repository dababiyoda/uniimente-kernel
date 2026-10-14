"""Layer 3 tests: Consequence Gate + Commit Witness + policy engine.

The adversarial suite: expired grant, revoked grant, stale approval,
effect mismatch, budget overflow, identity lapse, executor explosion.
Every one must fail closed.
"""
import os
import pytest
from datetime import datetime, timezone, timedelta

from compiler.ucl_compiler import compile_constitution
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate, GrantIssuer, BudgetOffice
from policy.engine import Proposal, Verdict, evaluate, explain
from provenance.ledger import EvidenceLedger
from provenance.commit_witness import WitnessSigner, new_witness

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def stack():
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    signer = WitnessSigner(env="development")
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger, signer=signer)
    actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                            legal_principal="alfonso_lopez", declared_capabilities=["draft.publish"],
                            budget_ceiling_usd=5.0, consequence_class="external_contact")
    return gate, passports, ledger, actor, compiled


def make_proposal(actor_id, **kw):
    defaults = dict(
        actor=actor_id, legal_principal="alfonso_lopez", action_class="draft.publish",
        objective="test.objective", payload={"text": "hello governed world"}, target="sandbox:outbox",
        consequence_class="external_contact", evidence_confidence=0.9,
        evidence_refs=["sha256:" + "a" * 64], estimated_cost_usd=0.0,
        requested_capability="draft.publish", expected_outcome="draft queued")
    defaults.update(kw)
    return Proposal(**defaults)


def authorized_run(gate, proposal, *, executor, **kwargs):
    """Synthetic fixture: authorization exists before entering the Gate."""
    grant = gate.grants.issue_single_action(proposal=proposal, policy_version="1.0.0")
    return gate.run(proposal, executor=executor, standing_grant=grant, **kwargs)


GOOD = lambda p: {"observed_outcome": "draft queued", "result_class": "positive"}


# ---------- happy path: the full 14-step pipeline ----------

def test_full_pipeline_reaches_recorded(stack):
    gate, passports, ledger, actor, _ = stack
    rec = authorized_run(gate, make_proposal(actor.passport_id), executor=GOOD)
    states = [t["state"] for t in rec.trajectory]
    assert rec.state == "recorded"
    assert states[0] == "proposed"
    assert "evaluating" in states and "granted" in states and "executing" in states
    assert "committed" in states and states[-1] == "recorded"
    assert rec.witness_id and rec.grant_id and rec.receipt_hash
    # every material occurrence is on the ledger
    types = [r.record_type for r in ledger.records]
    for t in ("witness", "receipt", "outcome"):
        assert t in types
    ok, msg = ledger.verify_chain()
    assert ok, msg


def test_outcome_record_matches_contract(stack):
    import json, jsonschema
    gate, passports, ledger, actor, _ = stack
    rec = authorized_run(gate, make_proposal(actor.passport_id), executor=GOOD)
    schema = json.load(open(os.path.join(ROOT, "contracts", "outcome.schema.json")))
    jsonschema.validate(rec.outcome, schema)


def test_capability_grant_matches_contract(stack):
    import json, jsonschema
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    schema = json.load(open(os.path.join(ROOT, "contracts", "capability-grant.schema.json")))
    jsonschema.validate(grant, schema)


def test_explain_states_law_and_reasons(stack):
    gate, passports, ledger, actor, compiled = stack
    p = make_proposal(actor.passport_id)
    # proposal time, zero cost, no grant yet: permissible (gate issues capability next)
    decision = evaluate(compiled, p, identity_ok=True, grant=None)
    x = explain(compiled, p, decision)
    assert x["verdict"] == "allow"
    assert x["which_law_applies"]
    assert "unlawful_conduct" in x["what_must_not_happen"]
    # non-zero cost without budget authorization: refused, missing named
    p2 = make_proposal(actor.passport_id, estimated_cost_usd=10.0)
    d2 = evaluate(compiled, p2, identity_ok=True, grant=None)
    x2 = explain(compiled, p2, d2)
    assert x2["verdict"] == "deny"
    assert "budget_authorization" in x2["what_remains_missing"]


# ---------- adversarial: everything fails closed ----------

def test_no_identity_no_action(stack):
    gate, passports, ledger, actor, _ = stack
    rec = gate.run(make_proposal("spiffe://uniimente.internal/agent/ghost"), executor=GOOD)
    assert rec.state == "refused"
    assert any("identity" in r for r in rec.refusal_reasons)


def test_unknown_legal_principal_refused(stack):
    gate, passports, ledger, actor, _ = stack
    rec = gate.run(make_proposal(actor.passport_id, legal_principal="PHANTOM_INC"), executor=GOOD)
    assert rec.state == "refused"
    assert any("legal principal" in r for r in rec.refusal_reasons)


def test_uniimente_principal_refused(stack):
    gate, passports, ledger, actor, _ = stack
    rec = gate.run(make_proposal(actor.passport_id, legal_principal="UNIIMENTE"), executor=GOOD)
    assert rec.state == "refused"


def test_absolute_prohibition_refused(stack):
    gate, passports, ledger, actor, _ = stack
    rec = gate.run(make_proposal(actor.passport_id, action_class="physical_harm"), executor=GOOD)
    assert rec.state == "refused"
    assert any("absolutely prohibited" in r for r in rec.refusal_reasons)


def test_reserved_matter_requires_human_and_denial_is_terminal(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id, action_class="material_debt")
    rec = gate.run(p, executor=GOOD, approver=lambda pr, rs: (False, "not taking debt"))
    assert rec.state == "denied"
    states = [t["state"] for t in rec.trajectory]
    assert "pending_human" in states and "executing" not in states


def test_reserved_matter_with_approval_proceeds(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id, action_class="material_debt")
    rec = authorized_run(gate, p, executor=GOOD, approver=lambda pr, rs: (True, "synthetic approval; not founder authentication"))
    assert rec.state == "recorded"


def test_revoked_grant_fails_at_commit(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    g = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    gate.grants.revoke(g["grant_id"], reason="adversarial", revoker="alfonso")
    rec = gate.run(p, executor=GOOD, standing_grant=g)
    assert rec.state in ("revoked", "refused")
    assert "executing" not in [t["state"] for t in rec.trajectory]


def test_expired_grant_fails_at_commit(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    g = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    g["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    rec = gate.run(p, executor=GOOD, standing_grant=g)
    assert rec.state in ("refused", "expired")
    assert any("expired" in r for r in rec.refusal_reasons)


def test_single_use_grant_cannot_be_replayed(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    g = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    rec1 = gate.run(p, executor=GOOD, standing_grant=g)
    assert rec1.state == "recorded"
    rec2 = gate.run(p, executor=GOOD, standing_grant=g)  # replay attempt
    assert rec2.state in ("refused", "revoked")
    assert any("consumed" in r or "single-use" in r for r in rec2.refusal_reasons)


def test_effect_mismatch_is_hard_refusal_and_incident(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    g = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    p.payload = {"text": "DIFFERENT PAYLOAD"}  # mutate after authorization
    rec = gate.run(p, executor=GOOD, standing_grant=g)
    assert rec.state == "refused"
    assert rec.incident == "effect_mismatch_at_commit"
    incidents = [r for r in ledger.records if r.payload.get("type") == "incident.effect_mismatch"]
    assert incidents, "effect mismatch must raise an incident on the ledger"


def test_budget_overflow_refused(stack):
    gate, passports, ledger, actor, _ = stack
    rec = gate.run(make_proposal(actor.passport_id, estimated_cost_usd=999.0), executor=GOOD)
    assert rec.state == "refused"
    assert any("cost" in r or "budget" in r for r in rec.refusal_reasons)


def test_weak_evidence_refused_for_external_contact(stack):
    gate, passports, ledger, actor, _ = stack
    rec = gate.run(make_proposal(actor.passport_id, evidence_confidence=0.3), executor=GOOD)
    assert rec.state == "refused"
    assert any("evidence" in r for r in rec.refusal_reasons)


def test_simulate_stage_grant_cannot_execute_external(stack):
    gate, passports, ledger, actor, _ = stack
    now = datetime.now(timezone.utc)
    g = {"grant_id": "g-1", "grantee": actor.passport_id,
         "granted_by": "spiffe://uniimente.internal/kernel/action-gateway",
         "legal_actor": "alfonso_lopez", "objective": "test",
         "permitted_actions": ["draft.publish"], "spending_limit_usd": 5.0,
         "prohibited": [], "initial_stage": "simulate", "stage": "simulate",
         "issued_at": now.isoformat().replace("+00:00", "Z"),
         "expires_at": (now + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
         "revocable_by": ["spiffe://uniimente.internal/kernel/action-gateway"],
         "revoked": False, "revoked_at": None, "revocation_reason": None}
    decision = evaluate(gate.compiled, make_proposal(actor.passport_id), identity_ok=True, grant=g)
    assert decision.verdict == Verdict.DENY
    assert any("simulate" in r for r in decision.reasons)


def test_executor_explosion_fails_closed_and_preserves_evidence(stack):
    gate, passports, ledger, actor, _ = stack
    def boom(p):
        raise RuntimeError("adapter exploded")
    rec = authorized_run(gate, make_proposal(actor.passport_id), executor=boom)
    assert rec.state == "reconciliation_required"
    assert rec.incident == "executor_exception:RuntimeError"
    ok, _ = ledger.verify_chain()
    assert ok  # failure is on the chain; negative evidence kept


def test_witness_proves_the_exact_sentence(stack):
    """This exact machine, entity, permission, law, evidence, result."""
    gate, passports, ledger, actor, _ = stack
    rec = authorized_run(gate, make_proposal(actor.passport_id), executor=GOOD)
    witness = [r for r in ledger.by_type("witness")][0].payload
    assert witness["actor"] == actor.passport_id              # this exact machine
    assert witness["legal_principal"] == "alfonso_lopez"      # this exact entity
    assert witness["grant_id"] == rec.grant_id                # this exact permission
    assert witness["constitution_hash"].startswith("sha256:") # this exact law
    assert witness["evidence_refs"]                           # this exact evidence
    assert witness["expected_outcome"] == "draft queued"      # this exact result
    from provenance.commit_witness import CommitWitness
    w = CommitWitness(**witness)
    assert gate.signer.verify(w)                              # proof remains valid


def test_witness_tamper_detected(stack):
    gate, passports, ledger, actor, _ = stack
    rec = authorized_run(gate, make_proposal(actor.passport_id), executor=GOOD)
    witness = [r for r in ledger.by_type("witness")][0].payload
    witness["expected_outcome"] = "forged outcome"
    from provenance.commit_witness import CommitWitness
    assert not gate.signer.verify(CommitWitness(**witness))


def test_no_approver_pending_human_expires(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id, action_class="material_debt")
    rec = gate.run(p, executor=GOOD, approver=None)
    assert rec.state == "expired"


# ---------- the commit path verifies the WHOLE chain (e2440a6 merge) ----------

def test_tampering_an_old_retained_record_refuses_the_next_commit(stack):
    """Hot paths verify only new history (provenance/ledger.py verify_incremental, e2440a6), so an
    old record altered in memory is invisible to append() for up to FULL_VERIFY_SECONDS. The Gate's
    commit path must still reconstruct the whole chain: nothing is witnessed, dispatched or executed
    on top of altered history."""
    gate, passports, ledger, actor, _ = stack
    assert authorized_run(gate, make_proposal(actor.passport_id), executor=GOOD).state == "recorded"
    assert ledger.verify_incremental()[0]                 # the incremental view is warm and trusts its prefix
    ledger._records[1].payload["tampered"] = True          # an old retained record, altered in this process
    assert ledger.verify_incremental()[0]                 # ...which the hot path alone does not see
    calls, dispatched = [], len(ledger.by_type("grant_dispatch"))
    with pytest.raises(ValueError, match="payload hash mismatch at seq 1"):
        authorized_run(gate, make_proposal(actor.passport_id, payload={"text": "second"}),
                       executor=lambda p: calls.append(p) or GOOD(p))
    assert calls == []                                      # the executor never ran
    assert len(ledger.by_type("grant_dispatch")) == dispatched and not ledger.verify_chain()[0]


# ---------- #55 CASE 27: escalation inside the commit window ----------
# Ported from refs/remotes/pr/55:docs/integration/harness/verify_main_holes.py
# CASE 27, adapted to the canonical path: the grant is issued by the Gate's own
# GrantIssuer and supplied as standing_grant, so admission succeeds and the
# escalation is what the commit-time check must catch.

def _counting(calls):
    def execute(p):
        calls.append(p.consequence_class)
        return {"observed_outcome": "draft queued", "result_class": "positive"}
    return execute


def test_case27_consequence_class_escalated_in_commit_window_is_refused(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    sign = gate.signer.sign

    def escalate(witness):
        p.consequence_class = "irreversible"      # escalate in the commit window
        return sign(witness)

    gate.signer.sign = escalate
    calls = []
    rec = gate.run(p, executor=_counting(calls), standing_grant=grant,
                   approver=lambda pr, why: (True, "approved as external_contact"))
    assert rec.state == "refused" and calls == []
    assert "executing" not in [t["state"] for t in rec.trajectory]
    assert not ledger.by_type("receipt") and not ledger.by_type("grant_dispatch")
    assert any("human approval this run does not hold" in r for r in rec.refusal_reasons)
    assert any("authority" in r and "mismatch" in r for r in rec.refusal_reasons)
    assert rec.incident == "authority_mismatch_at_commit"
    assert gate.grants.get_meta(grant["grant_id"])["used"] is False


def test_require_human_raised_only_at_commit_refuses_without_approval(stack):
    """Law changed in the commit window: the action was ALLOW at admission and is
    reserved at commit. No human approved it, so it must not execute."""
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    sign = gate.signer.sign

    def reserve(witness):
        gate.compiled.reserved_matters["draft.publish"] = ["alfonso"]
        return sign(witness)

    gate.signer.sign = reserve
    calls = []
    rec = gate.run(p, executor=_counting(calls), standing_grant=grant)
    assert rec.state == "refused" and calls == []
    assert any("reserved" in r and "does not hold" in r for r in rec.refusal_reasons)


def test_grant_does_not_cover_a_class_escalated_before_run(stack):
    """A grant minted for external_contact cannot carry an irreversible effect,
    even when a human approves the irreversible class during the run."""
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    p.consequence_class = "irreversible"
    calls = []
    rec = gate.run(p, executor=_counting(calls), standing_grant=grant,
                   approver=lambda pr, why: (True, "synthetic approval; not founder authentication"))
    assert rec.state == "refused" and calls == []
    assert any("authority binding mismatch" in r for r in rec.refusal_reasons)


def test_proposal_changed_during_approval_is_refused(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id, action_class="material_debt")
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")

    def approver(pr, why):
        pr.evidence_refs = ["sha256:" + "b" * 64]  # changed while a human looked at it
        return True, "synthetic approval; not founder authentication"

    calls = []
    rec = gate.run(p, executor=_counting(calls), standing_grant=grant, approver=approver)
    assert rec.state == "refused" and calls == []
    assert any("changed during human approval" in r for r in rec.refusal_reasons)


def test_human_approval_held_for_this_proposal_survives_commit(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id, consequence_class="irreversible", evidence_confidence=0.95)
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    calls = []
    rec = gate.run(p, executor=_counting(calls), standing_grant=grant,
                   approver=lambda pr, why: (True, "synthetic approval; not founder authentication"))
    assert rec.state == "recorded" and calls == ["irreversible"]
