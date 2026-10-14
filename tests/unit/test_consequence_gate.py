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


# ---------- #21: unknown or stale evidence fails closed, at evaluation and at commit ----------
# Re-expressed from refs/remotes/pr/21:tests/gate/test_gate_hostile.py::test_04_stale_evidence_refused
# against the canonical evidence contract (contracts/evidence.schema.json) and the one Gate.

def _packet(*, captured_ago=timedelta(minutes=5), fresh_for=None, **overrides):
    import uuid
    now = datetime.now(timezone.utc)
    stamp = lambda dt: dt.isoformat().replace("+00:00", "Z")  # noqa: E731
    packet = {
        "packet_id": str(uuid.uuid4()), "captured_at": stamp(now - captured_ago),
        "captured_by": "spiffe://uniimente.internal/organ/evidence-browser",
        "source": {"uri": "https://example.com/report", "retrieval_path": "GET /report",
                   "source_authority": "primary"},
        "raw_content_hash": "sha256:" + "c" * 64, "raw_content_location": "vault://reports/1",
        "claims": [], "instruction_shaped_content": {"detected": False, "quarantined": True}}
    if fresh_for is not None:
        packet["fresh_until"] = stamp(now - captured_ago + fresh_for)
    packet.update(overrides)
    return packet


def _evidence_gate(stack, *packets):
    gate, passports, ledger, actor, compiled = stack
    register = {p["packet_id"]: p for p in packets}
    return ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger, signer=gate.signer,
                           evidence=register), register


def test_04_stale_evidence_refused(stack):
    stale = _packet(captured_ago=timedelta(hours=2), fresh_for=timedelta(hours=1))
    gate, _ = _evidence_gate(stack, stale)
    _, _, ledger, actor, _ = stack
    calls = []
    rec = authorized_run(gate, make_proposal(actor.passport_id, evidence_refs=[stale["packet_id"]]),
                         executor=lambda p: calls.append(p) or GOOD(p))
    assert rec.state == "refused" and calls == []
    assert any("stale" in r for r in rec.refusal_reasons)
    assert ledger.verify_chain()[0]


def test_unknown_evidence_id_fails_closed(stack):
    gate, _ = _evidence_gate(stack, _packet())
    actor = stack[3]
    rec = authorized_run(gate, make_proposal(actor.passport_id, evidence_refs=["sha256:" + "a" * 64]),
                         executor=GOOD)
    assert rec.state == "refused"
    assert any("unknown evidence id" in r for r in rec.refusal_reasons)


def test_evidence_older_than_its_class_allows_is_stale_without_fresh_until(stack):
    old = _packet(captured_ago=timedelta(days=8))                 # external_contact allows 7 days
    gate, _ = _evidence_gate(stack, old)
    rec = authorized_run(gate, make_proposal(stack[3].passport_id, evidence_refs=[old["packet_id"]]),
                         executor=GOOD)
    assert rec.state == "refused" and any("stale" in r for r in rec.refusal_reasons)


def test_evidence_going_stale_in_the_commit_window_refuses_at_commit(stack):
    packet = _packet(fresh_for=timedelta(hours=1))
    gate, register = _evidence_gate(stack, packet)
    sign = gate.signer.sign

    def expire(witness):     # the freshness deadline passes between evaluation and commit
        register[packet["packet_id"]] = {**packet, "fresh_until": packet["captured_at"]}
        return sign(witness)

    gate.signer.sign = expire
    calls = []
    rec = authorized_run(gate, make_proposal(stack[3].passport_id, evidence_refs=[packet["packet_id"]]),
                         executor=lambda p: calls.append(p) or GOOD(p))
    assert rec.state == "refused" and calls == []
    assert any(r.startswith("commit-time policy refusal: evidence") and "stale" in r for r in rec.refusal_reasons)


@pytest.mark.parametrize("bad", [
    {"captured_at": "2026-10-14T00:00:00"},                      # no timezone
    {"captured_at": "2999-01-01T00:00:00Z"},                     # captured in the future
    {"packet_id": "not-the-ref"},                                # register key and packet disagree
    {"claims": "not a list"},                                    # contract-invalid
])
def test_ambiguous_evidence_packets_fail_closed(stack, bad):
    packet = _packet()
    ref = packet["packet_id"]
    gate, register = _evidence_gate(stack)
    register[ref] = {**packet, **bad}
    rec = authorized_run(gate, make_proposal(stack[3].passport_id, evidence_refs=[ref]), executor=GOOD)
    assert rec.state == "refused"


def test_fresh_contract_valid_evidence_passes(stack):
    packet = _packet(fresh_for=timedelta(days=1))
    gate, _ = _evidence_gate(stack, packet)
    rec = authorized_run(gate, make_proposal(stack[3].passport_id, evidence_refs=[packet["packet_id"]]),
                         executor=GOOD)
    assert rec.state == "recorded"


def test_fresh_until_is_optional_in_the_evidence_contract():
    import json, jsonschema
    schema = json.load(open(os.path.join(ROOT, "contracts", "evidence.schema.json")))
    checker = jsonschema.FormatChecker()
    jsonschema.validate(_packet(), schema, format_checker=checker)                   # existing producers
    jsonschema.validate(_packet(fresh_for=timedelta(hours=1)), schema, format_checker=checker)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_packet(fresh_until="tomorrow"), schema, format_checker=checker)


# ---------- #12: a child grant is a strict subset of its parent ----------
# Re-expressed from refs/remotes/pr/12:sdk-python/tests/test_capability.py test_child_grant_must_be_subset
# and test_child_grant_subset_ok, retargeted at the one GrantIssuer.

def _parent(gate, actor_id, **kw):
    kw.setdefault("estimated_cost_usd", 3.0)
    return gate.grants.issue_single_action(proposal=make_proposal(actor_id, **kw), policy_version="1.0.0")


def _child(gate, actor_id, parent_id, **kw):
    p = make_proposal(actor_id, context={"parent_grant": parent_id}, **kw)
    return gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")


def test_child_grant_must_be_subset(stack):
    gate, passports, ledger, actor, _ = stack
    parent = _parent(gate, actor.passport_id)
    for kw, why in (({"requested_capability": "funds.transfer"}, "permitted_actions"),
                    ({"estimated_cost_usd": 3.01}, "spending limit"),
                    ({"target": "sandbox:elsewhere"}, "counterparties"),
                    ({"legal_principal": "another_principal"}, "legal actor")):
        with pytest.raises(ValueError, match=why) as refused:      # GrantRefused is a ValueError
            _child(gate, actor.passport_id, parent["grant_id"], **kw)
        assert type(refused.value).__name__ == "GrantRefused"


def test_child_grant_subset_ok(stack):
    gate, passports, ledger, actor, _ = stack
    parent = _parent(gate, actor.passport_id)
    child = _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=1.0)
    assert child["parent_grant"] == parent["grant_id"]
    assert child["permitted_actions"] == ["draft.publish"] and child["spending_limit_usd"] == 1.0
    assert child["expires_at"] <= parent["expires_at"]
    from adapters.contract_validation import validate_contract
    validate_contract(child, "capability-grant")


@pytest.mark.parametrize("state", ["unknown", "revoked", "expired", "consumed"])
def test_child_of_an_unknown_revoked_expired_or_consumed_parent_is_refused(stack, state):
    gate, passports, ledger, actor, _ = stack
    parent = _parent(gate, actor.passport_id)
    parent_id = parent["grant_id"]
    if state == "unknown":
        parent_id = "not-issued-here"
    elif state == "revoked":
        gate.grants.revoke(parent_id, reason="adversarial", revoker="alfonso")
    elif state == "expired":
        parent["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    else:
        gate.grants.mark_used(parent_id)
    with pytest.raises(ValueError, match="parent grant"):
        _child(gate, actor.passport_id, parent_id, estimated_cost_usd=1.0)


def test_child_inherits_parent_prohibitions_and_cannot_take_a_prohibited_action(stack):
    gate, passports, ledger, actor, _ = stack
    parent = _parent(gate, actor.passport_id)
    parent["prohibited"] = ["draft.publish"]
    with pytest.raises(ValueError, match="prohibited by the parent"):
        _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=1.0)
    parent["prohibited"] = ["material_debt"]
    child = _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=1.0)
    assert child["prohibited"] == ["material_debt"]
