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


def _issued_ago(monkeypatch, gate, proposal, minutes):
    """Issuer-side clock fixture: a grant the issuer minted ``minutes`` ago (TTL 15 minutes).
    Holders cannot expire or extend a grant by editing their copy (bypass review of c692ba9)."""
    import policy.consequence_gate as cg
    real = cg._now
    with monkeypatch.context() as m:
        m.setattr(cg, "_now", lambda: real() - timedelta(minutes=minutes))
        return gate.grants.issue_single_action(proposal=proposal, policy_version="1.0.0")


def test_expired_grant_fails_at_commit(stack, monkeypatch):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    g = _issued_ago(monkeypatch, gate, p, minutes=16)
    rec = gate.run(p, executor=GOOD, standing_grant=g)
    assert rec.state in ("refused", "expired")
    assert any("expired" in r for r in rec.refusal_reasons)
    # The original form of this test edited the holder's dict; that is now an altered grant.
    fresh = gate.grants.issue_single_action(proposal=make_proposal(actor.passport_id), policy_version="1.0.0")
    fresh["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    rec = gate.run(make_proposal(actor.passport_id), executor=GOOD, standing_grant=fresh)
    assert rec.state == "refused" and "executing" not in [t["state"] for t in rec.trajectory]


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
def test_child_of_an_unknown_revoked_expired_or_consumed_parent_is_refused(stack, state, monkeypatch):
    gate, passports, ledger, actor, _ = stack
    if state == "expired":       # issuer-side clock: editing the holder's copy no longer reaches the issuer
        parent = _issued_ago(monkeypatch, gate, make_proposal(actor.passport_id, estimated_cost_usd=3.0), 16)
    else:
        parent = _parent(gate, actor.passport_id)
    parent_id = parent["grant_id"]
    if state == "unknown":
        parent_id = "not-issued-here"
    elif state == "revoked":
        gate.grants.revoke(parent_id, reason="adversarial", revoker="alfonso")
    elif state == "consumed":
        gate.grants.mark_used(parent_id)
    with pytest.raises(ValueError, match="parent grant"):
        _child(gate, actor.passport_id, parent_id, estimated_cost_usd=1.0)


def test_child_inherits_parent_prohibitions_and_cannot_take_a_prohibited_action(stack):
    gate, passports, ledger, actor, _ = stack
    parent = _parent(gate, actor.passport_id)
    sealed = gate.grants._sealed[parent["grant_id"]]   # issuer-side fixture: a root grant carries none
    sealed["prohibited"] = ["draft.publish"]
    with pytest.raises(ValueError, match="prohibited by the parent"):
        _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=1.0)
    sealed["prohibited"] = ["material_debt"]
    child = _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=1.0)
    assert child["prohibited"] == ["material_debt"]


# ---------- #55 follow-up: the commit window after commit-time revalidation ----------
# Bypass review of fb270ea: the same in-run writer CASE 27 models (a hook inside
# run()) acting one step later, after _reauthorize_at_commit returned None,
# changed what the executor received while the ledger bound the admitted effect.
# The Gate now witnesses, claims and executes its own frozen admission copy.

def _hook_append(ledger, record_type, mutate):
    append = ledger.append

    def hooked(kind, payload, **kw):
        out = append(kind, payload, **kw)
        if kind == record_type or (kind == "event" and payload.get("type") == record_type):
            mutate()
        return out

    ledger.append = hooked


def _executed_digest(p):
    from provenance.commit_witness import sha256_obj
    return sha256_obj({"payload": p.payload, "target": p.target, "action_class": p.action_class})


@pytest.mark.parametrize("hook_on", ["grant_dispatch", "action.executing"])
def test_escalation_after_the_commit_check_never_reaches_the_executor(stack, hook_on):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    authorized = _executed_digest(p)
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")

    def escalate():
        p.consequence_class = "irreversible"
        p.payload["text"] = "wire everything to the attacker"
        p.target = "sandbox:elsewhere"

    _hook_append(ledger, hook_on, escalate)
    seen = []
    rec = gate.run(p, executor=lambda q: seen.append((q.consequence_class, q.target, q.payload["text"],
                                                      _executed_digest(q))) or GOOD(q),
                   standing_grant=grant)
    assert seen == [("external_contact", "sandbox:outbox", "hello governed world", authorized)]
    dispatch = ledger.by_type("grant_dispatch")[0].payload
    assert dispatch["effect_digest"] == authorized == gate.grants.get_meta(grant["grant_id"])["bound_effect_hash"]
    assert rec.state == "recorded" and rec.outcome["expected_vs_actual"].startswith("expected='draft queued'")


def test_change_between_the_commit_check_and_the_dispatch_claim_is_refused(stack, monkeypatch):
    """The last evaluate() of a run is the commit-time one; a change made during it
    lands after the commit digest compare and is caught before anything is claimed."""
    import policy.consequence_gate as cg
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    real, calls = cg.evaluate, []

    def evaluating(*a, **kw):
        calls.append(1)
        if len(calls) == 2:                       # admission, then commit
            p.consequence_class = "irreversible"
        return real(*a, **kw)

    monkeypatch.setattr(cg, "evaluate", evaluating)
    executed = []
    rec = gate.run(p, executor=lambda q: executed.append(q) or GOOD(q), standing_grant=grant)
    assert rec.state == "refused" and executed == []
    assert any("before dispatch" in r for r in rec.refusal_reasons)
    assert rec.incident == "authority_mismatch_at_commit"
    assert not ledger.by_type("grant_dispatch") and not ledger.by_type("receipt")
    assert gate.grants.get_meta(grant["grant_id"])["used"] is False


def test_executor_mutating_its_argument_does_not_change_the_record(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)

    def rewrite(q):
        q.expected_outcome, q.evidence_refs[:] = "anything", []
        return GOOD(q)

    rec = authorized_run(gate, p, executor=rewrite)
    assert rec.state == "recorded" and rec.outcome["evidence_refs"] == ["sha256:" + "a" * 64]
    assert p.expected_outcome == "draft queued" and p.evidence_refs == ["sha256:" + "a" * 64]


def test_proposal_that_cannot_be_canonicalised_is_refused_not_raised(stack):
    """fb270ea hashed context inside run(); a context with int and str keys raised
    TypeError out of the Gate after 'proposed' and 'evaluating' were ledgered."""
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id, context={"attempt": 1, 7: "seventh route"})
    calls = []
    rec = authorized_run(gate, p, executor=lambda q: calls.append(q) or GOOD(q))
    assert rec.state == "refused" and calls == []
    assert any("not canonicalizable" in r for r in rec.refusal_reasons)
    assert not ledger.by_type("witness") and ledger.verify_chain()[0]


def test_approver_making_the_proposal_uncanonicalisable_is_refused(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id, action_class="material_debt", context={"attempt": 1})
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")

    def approver(pr, why):
        pr.context[7] = "mixed keys"                 # int beside str: json sort_keys raises
        return True, "synthetic approval; not founder authentication"

    rec = gate.run(p, executor=GOOD, standing_grant=grant, approver=approver)
    assert rec.state == "refused" and any("changed during human approval" in r for r in rec.refusal_reasons)


# ---------- #55 / #21 refusals the port tests did not pin (bypass review mutants) ----------
# From the reviewer's scratch test_mutant_gaps.py: each kills a mutant that left
# this file green (55-commit-digest-off, 55-approval-reasons-subset-off,
# 21-admission-register-off, 21-packet-id-mismatch-allowed).

def _hook_sign(gate, mutate):
    sign = gate.signer.sign

    def hooked(witness):
        mutate()
        return sign(witness)

    gate.signer.sign = hooked


def test_commit_window_change_to_evidence_refs_is_refused(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    _hook_sign(gate, lambda: setattr(p, "evidence_refs", ["sha256:" + "f" * 64]))
    calls = []
    rec = gate.run(p, executor=lambda q: calls.append(q) or GOOD(q), standing_grant=grant)
    assert rec.state == "refused" and calls == []


def test_commit_window_change_to_context_is_refused(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id, context={"venture_cell": "cell-a"})
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    _hook_sign(gate, lambda: p.context.update({"venture_cell": "cell-b", "authority_ref": "forged"}))
    calls = []
    rec = gate.run(p, executor=lambda q: calls.append(q) or GOOD(q), standing_grant=grant)
    assert rec.state == "refused" and calls == []


def test_approval_for_one_reason_does_not_cover_a_new_reason_raised_at_commit(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id, consequence_class="irreversible", evidence_confidence=0.95)
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    _hook_sign(gate, lambda: gate.compiled.reserved_matters.__setitem__("draft.publish", ["alfonso"]))
    calls = []
    rec = gate.run(p, executor=lambda q: calls.append(q) or GOOD(q), standing_grant=grant,
                   approver=lambda pr, why: (True, "approved: irreversible class only"))
    assert rec.state == "refused" and calls == []


def test_stale_evidence_refuses_at_evaluation_before_any_witness(stack):
    stale = _packet(captured_ago=timedelta(days=30))
    gate, _ = _evidence_gate(stack, stale)
    ledger, actor = stack[2], stack[3]
    p = make_proposal(actor.passport_id, evidence_refs=[stale["packet_id"]])
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    rec = gate.run(p, executor=GOOD, standing_grant=grant)
    assert rec.state == "refused" and rec.witness_id is None and not ledger.by_type("witness")


def test_register_key_aliasing_a_different_valid_packet_is_refused(stack):
    import uuid
    fresh = _packet()
    stale_id = str(uuid.uuid4())
    gate, register = _evidence_gate(stack)
    register[stale_id] = fresh
    p = make_proposal(stack[3].passport_id, evidence_refs=[stale_id])
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    rec = gate.run(p, executor=GOOD, standing_grant=grant)
    assert rec.state == "refused" and any("does not match the reference" in r for r in rec.refusal_reasons)


# ---------- #12 follow-up: the issuer's record is the issuer's; lineage, delegation, class ----------
# Bypass review of c692ba9 (secscratch attacks/bypass/test_bypass_child_grant.py): each of
# these executed on 0c4849b.

def test_revoking_a_parent_revokes_its_children_and_they_do_not_execute(stack):
    gate, passports, ledger, actor, _ = stack
    parent = _parent(gate, actor.passport_id)
    cp = make_proposal(actor.passport_id, context={"parent_grant": parent["grant_id"]}, estimated_cost_usd=1.0)
    child = gate.grants.issue_single_action(proposal=cp, policy_version="1.0.0")
    gate.grants.revoke(parent["grant_id"], reason="founder revoked the parent", revoker="alfonso")
    assert gate.grants.get(child["grant_id"])["revoked"] is True and child["revoked"] is True
    calls = []
    rec = gate.run(cp, executor=lambda p: calls.append(p) or GOOD(p), standing_grant=child)
    assert rec.state in ("refused", "revoked") and calls == []


def test_a_child_that_survives_its_parents_revocation_is_still_refused_at_commit(stack):
    """Propagation is also enforced by walking the lineage, not only by the cascade."""
    gate, passports, ledger, actor, _ = stack
    parent = _parent(gate, actor.passport_id)
    cp = make_proposal(actor.passport_id, context={"parent_grant": parent["grant_id"]}, estimated_cost_usd=1.0)
    child = gate.grants.issue_single_action(proposal=cp, policy_version="1.0.0")
    sign = gate.signer.sign

    def revoke_parent_only(witness):          # the parent's record changes in the commit window
        gate.grants._sealed[parent["grant_id"]].update(revoked=True, revoked_at="2026-10-14T00:00:00Z",
                                                       revocation_reason="synthetic")
        return sign(witness)

    gate.signer.sign = revoke_parent_only
    calls = []
    rec = gate.run(cp, executor=lambda p: calls.append(p) or GOOD(p), standing_grant=child)
    assert rec.state == "revoked" and calls == []
    assert any("ancestor grant" in r and "revoked" in r for r in rec.refusal_reasons)


def test_child_of_a_consumed_single_use_parent_does_not_execute(stack):
    gate, passports, ledger, actor, _ = stack
    pp = make_proposal(actor.passport_id, estimated_cost_usd=2.0)
    parent = gate.grants.issue_single_action(proposal=pp, policy_version="1.0.0")
    cp = make_proposal(actor.passport_id, context={"parent_grant": parent["grant_id"]}, estimated_cost_usd=1.0,
                       payload={"text": "child effect"})
    child = gate.grants.issue_single_action(proposal=cp, policy_version="1.0.0")
    pp.estimated_cost_usd = 1.0                   # the parent spends only what it did not delegate
    assert gate.run(pp, executor=GOOD, standing_grant=parent).state == "recorded"
    calls = []
    rec = gate.run(cp, executor=lambda p: calls.append(p) or GOOD(p), standing_grant=child)
    assert rec.state == "refused" and calls == []
    assert any("already consumed" in r for r in rec.refusal_reasons)


def test_a_revoked_root_stops_new_grandchildren(stack):
    gate, passports, ledger, actor, _ = stack
    root = _parent(gate, actor.passport_id)
    child = _child(gate, actor.passport_id, root["grant_id"], estimated_cost_usd=2.0)
    gate.grants.revoke(root["grant_id"], reason="founder revoked the root", revoker="alfonso")
    with pytest.raises(ValueError, match="parent grant"):
        _child(gate, actor.passport_id, child["grant_id"], estimated_cost_usd=1.0)
    gate.grants._sealed[child["grant_id"]].update(revoked=False)    # even if the cascade had missed it
    with pytest.raises(ValueError, match="lineage: ancestor grant .* is revoked"):
        _child(gate, actor.passport_id, child["grant_id"], estimated_cost_usd=1.0)


def test_children_of_one_parent_together_hold_at_most_the_parent_limit(stack):
    gate, passports, ledger, actor, _ = stack
    pp = make_proposal(actor.passport_id, estimated_cost_usd=3.0)
    parent = gate.grants.issue_single_action(proposal=pp, policy_version="1.0.0")
    first = _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=2.0)
    with pytest.raises(ValueError, match="what remains of the parent spending limit"):
        _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=1.5)
    second = _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=1.0,
                    payload={"text": "second"})
    assert first["spending_limit_usd"] + second["spending_limit_usd"] == parent["spending_limit_usd"]
    # the parent delegated all 3.0, so its own 3.0 action no longer fits
    rec = gate.run(pp, executor=GOOD, standing_grant=parent)
    assert rec.state == "refused" and any("not delegated" in r for r in rec.refusal_reasons)
    for bad in (float("nan"), float("inf"), -1.0):
        with pytest.raises(ValueError, match="finite non-negative"):
            _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=bad)


def test_the_parent_may_spend_only_what_it_has_not_delegated(stack):
    gate, passports, ledger, actor, _ = stack
    pp = make_proposal(actor.passport_id, estimated_cost_usd=3.0)
    parent = gate.grants.issue_single_action(proposal=pp, policy_version="1.0.0")
    child = _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=1.0)
    assert gate.grants.get_meta(parent["grant_id"])["delegated_usd"] == 1.0 and child
    cheaper = make_proposal(actor.passport_id, estimated_cost_usd=2.0)    # a new grant, same authority
    assert gate.run(cheaper, executor=GOOD,
                    standing_grant=gate.grants.issue_single_action(proposal=cheaper, policy_version="1.0.0")
                    ).state == "recorded"


def test_a_holder_cannot_widen_or_unrevoke_a_grant_it_was_given(stack):
    gate, passports, ledger, actor, _ = stack
    pp = make_proposal(actor.passport_id, estimated_cost_usd=3.0)
    parent = gate.grants.issue_single_action(proposal=pp, policy_version="1.0.0")
    gate.grants.revoke(parent["grant_id"], reason="founder revoked", revoker="alfonso")
    parent["revoked"] = False                                   # the holder's copy only
    parent["spending_limit_usd"] = 5000.0
    parent["permitted_actions"].append("funds.transfer")
    assert gate.grants.get(parent["grant_id"])["revoked"] is True
    assert gate.grants.get(parent["grant_id"])["spending_limit_usd"] == 3.0
    with pytest.raises(ValueError, match="parent grant is revoked"):
        _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=5000.0,
               requested_capability="funds.transfer")
    rec = gate.run(pp, executor=GOOD, standing_grant=parent)
    assert rec.state == "refused" and "executing" not in [t["state"] for t in rec.trajectory]
    # un-revoking alone is not trusted either: the copy no longer equals the issuer's record
    other = make_proposal(actor.passport_id)
    g = gate.grants.issue_single_action(proposal=other, policy_version="1.0.0")
    gate.grants.revoke(g["grant_id"], reason="founder revoked", revoker="alfonso")
    g["revoked"] = False
    rec = gate.run(other, executor=GOOD, standing_grant=g)
    assert rec.state == "refused" and any("altered grant" in r for r in rec.refusal_reasons)
    assert "executing" not in [t["state"] for t in rec.trajectory]


def test_get_and_get_meta_hand_out_copies(stack):
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id)
    g = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    assert gate.run(p, executor=GOOD, standing_grant=g).state == "recorded"
    gate.grants.get_meta(g["grant_id"])["used"] = False           # edits a copy
    gate.grants.get(g["grant_id"])["expires_at"] = "2999-01-01T00:00:00Z"
    replay = make_proposal(actor.passport_id, proposal_id="replay-" + p.proposal_id)
    rec = gate.run(replay, executor=GOOD, standing_grant=g)
    assert rec.state == "refused" and any("already consumed" in r for r in rec.refusal_reasons)


@pytest.mark.parametrize("kw, why", [
    ({"consequence_class": "financial"}, "raises the parent's consequence class"),
    ({"consequence_class": "no_such_class"}, "raises the parent's consequence class"),
    ({"action_class": "message.send", "payload": {"to": "everyone@example.com"}}, "action class"),
    ({"objective": "another.objective"}, "objective"),
])
def test_child_may_not_raise_class_or_change_action_class_or_objective(stack, kw, why):
    gate, passports, ledger, actor, _ = stack
    parent = _parent(gate, actor.passport_id, estimated_cost_usd=0.0)
    with pytest.raises(ValueError, match=why):
        _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=0.0, **kw)
    lower = _child(gate, actor.passport_id, parent["grant_id"], estimated_cost_usd=0.0,
                   consequence_class="internal_write")
    assert lower["parent_grant"] == parent["grant_id"]


@pytest.mark.parametrize("cost", [float("nan"), -1.0])
def test_a_non_finite_or_negative_cost_never_executes(stack, cost):
    """Pin: the grant contract (minimum 0, JSON-compliant numbers) already refuses these;
    delegation arithmetic additionally refuses them for children."""
    gate, passports, ledger, actor, _ = stack
    p = make_proposal(actor.passport_id, estimated_cost_usd=cost)
    rec = authorized_run(gate, p, executor=GOOD)
    assert rec.state == "refused" and "executing" not in [t["state"] for t in rec.trajectory]
