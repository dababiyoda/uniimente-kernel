"""#8 capability security and #30 the Consequence Gate, exercised on the Kernel's own gate.

#8: a grant is bound to one proposal (capability x action x target x budget x
deadline). Presenting it for a different target, a larger cost, after
revocation or a second time is refused before anything executes.

#30: every external consequence crosses one pipeline (evaluate -> grant ->
commit-time revalidation -> execute -> witness -> receipt -> outcome). An
exploding executor fails closed with evidence preserved; the commit witness
proves the exact action; the ledger chain verifies.

Sandbox targets only: nothing here reaches the outside world.
"""
from __future__ import annotations

from foundry.systems.kernel_stack import agent, gate_stack, proposal

GOOD = lambda p: {"observed_outcome": "draft queued", "result_class": "positive"}


def _states(record) -> list[str]:
    return [t["state"] for t in record.trajectory]


def capability_security() -> dict:
    gate, passports, ledger = gate_stack()
    actor = agent(passports)
    p = proposal(actor.passport_id)
    grant = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    other_target = gate.run(proposal(actor.passport_id, target="sandbox:other"), executor=GOOD, standing_grant=grant)
    overspend = gate.run(proposal(actor.passport_id, estimated_cost_usd=999.0), executor=GOOD)
    used = gate.run(p, executor=GOOD, standing_grant=grant)
    replay = gate.run(p, executor=GOOD, standing_grant=grant)
    p2 = proposal(actor.passport_id, payload={"text": "second"})
    g2 = gate.grants.issue_single_action(proposal=p2, policy_version="1.0.0")
    gate.grants.revoke(g2["grant_id"], reason="founder revoked", revoker="alfonso")
    revoked = gate.run(p2, executor=GOOD, standing_grant=g2)
    return {"other_target": other_target.state, "other_target_executed": "executing" in _states(other_target),
            "overspend": overspend.state, "first_use": used.state, "replay": replay.state,
            "replay_executed": "executing" in _states(replay), "revoked": revoked.state,
            "revoked_executed": "executing" in _states(revoked)}


def consequence_gate() -> dict:
    from provenance.commit_witness import WitnessSigner  # noqa: F401  (witness verified through the gate)
    gate, passports, ledger = gate_stack()
    actor = agent(passports)
    p = proposal(actor.passport_id)
    g = gate.grants.issue_single_action(proposal=p, policy_version="1.0.0")
    ok = gate.run(p, executor=GOOD, standing_grant=g)
    boom_p = proposal(actor.passport_id, payload={"text": "explodes"})
    boom_g = gate.grants.issue_single_action(proposal=boom_p, policy_version="1.0.0")
    def explode(_):
        raise RuntimeError("executor exploded")
    boom = gate.run(boom_p, executor=explode, standing_grant=boom_g)
    weak = gate.run(proposal(actor.passport_id, evidence_confidence=0.3), executor=GOOD)
    no_identity = gate.run(proposal("passport:nobody"), executor=GOOD)
    chain_ok, _ = ledger.verify_chain()
    kinds = sorted({r.record_type for r in ledger.records})
    return {"pipeline": _states(ok), "recorded": ok.state, "witnessed": bool(ok.witness_id and ok.receipt_hash),
            "explosion": boom.state, "explosion_evidence_kept": any(r.record_type == "outcome" for r in ledger.records),
            "weak_evidence": weak.state, "no_identity": no_identity.state, "chain_ok": chain_ok,
            "ledger_record_types": kinds}


QUERY_OPS = {"demonstrate": lambda a, r: consequence_gate()}
APPLY_OPS: dict = {}


def exercise(root) -> dict:
    return consequence_gate()
