"""Shared construction of the canonical Kernel stack for Foundry systems that wrap it.

The Foundry does not re-implement authority, events or proof: #5, #6, #7, #8,
#15 and #30 exercise the Kernel's own modules (events/spine.py,
provenance/proof.py, greg/founder.py, policy/consequence_gate.py) through this
one builder, so there is a single owner per concern.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def gate_stack(ledger_path: Path | None = None):
    from compiler.ucl_compiler import compile_constitution
    from identity.machine_passport import PassportRegistry
    from policy.consequence_gate import ConsequenceGate
    from provenance.commit_witness import WitnessSigner
    from provenance.ledger import EvidenceLedger
    compiled = compile_constitution(str(ROOT))
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash, str(ledger_path) if ledger_path else None)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    return gate, passports, ledger


def proposal(actor_id: str, **overrides):
    from policy.engine import Proposal
    fields = dict(actor=actor_id, legal_principal="alfonso_lopez", action_class="draft.publish",
                  objective="foundry.exercise", payload={"text": "governed draft"}, target="sandbox:outbox",
                  consequence_class="external_contact", evidence_confidence=0.9,
                  evidence_refs=["sha256:" + "a" * 64], estimated_cost_usd=0.0,
                  requested_capability="draft.publish", expected_outcome="draft queued")
    fields.update(overrides)
    return Proposal(**fields)


def agent(passports, *, capabilities=("draft.publish",), budget=5.0):
    return passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                           legal_principal="alfonso_lopez", declared_capabilities=list(capabilities),
                           budget_ceiling_usd=budget, consequence_class="external_contact")


def grant_problems(gate, grant, *, action_class: str, objective: str, target: str, payload: dict) -> list[str]:
    """Why ``gate`` would not honour ``grant`` for this exact effect (empty when it would).

    A dict is not authority. A rail or storefront honours only a grant held in the registry of the
    Consequence Gate that governs it: registered there and unaltered, unrevoked, unused, unexpired, issued
    for this objective, action and counterparty, and bound to exactly this effect (case and amount). The
    Gate re-checks all of it at its commit boundary; this is the same rule, stated before money moves."""
    from datetime import datetime, timezone
    from provenance.commit_witness import sha256_obj
    if gate is None:
        return ["no Consequence Gate governs this rail, so it honours no grant"]
    if not isinstance(grant, dict) or not grant.get("grant_id"):
        return ["no grant"]
    issued = gate.grants.get(grant["grant_id"])
    if issued is None or issued != grant:
        return ["not a grant the governing Consequence Gate issued (unregistered or altered)"]
    meta = gate.grants.get_meta(grant["grant_id"])
    problems = []
    if issued.get("revoked"):
        problems.append("the grant is revoked")
    if meta.get("single_use") and meta.get("used"):
        problems.append("the single-use grant is already used")
    if datetime.now(timezone.utc) >= datetime.fromisoformat(issued["expires_at"].replace("Z", "+00:00")):
        problems.append("the grant is expired")
    if issued.get("objective") != objective:
        problems.append(f"the grant was issued for {issued.get('objective')!r}, not {objective!r}")
    if action_class not in issued.get("permitted_actions", []) or target not in issued.get("counterparties", []):
        problems.append(f"the grant does not permit {action_class} toward {target}")
    if meta.get("bound_effect_hash") != sha256_obj({"payload": payload, "target": target, "action_class": action_class}):
        problems.append("the grant is bound to a different effect (case or amount)")
    return problems


def run_under_grant(gate, grant, *, action_class: str, objective: str, target: str, payload: dict,
                    consequence_class: str, evidence_refs: list, expected_outcome: str, executor):
    """Perform one consequential act through ``gate`` under ``grant`` (identity, policy, witness, commit-time
    revalidation, dispatch claim, receipt, single use). The proposal names exactly the effect the grant binds."""
    from policy.engine import Proposal
    p = Proposal(actor=grant["grantee"], legal_principal=grant["legal_actor"], action_class=action_class,
                 objective=objective, payload=payload, target=target, consequence_class=consequence_class,
                 evidence_confidence=0.9, evidence_refs=list(evidence_refs) or ["sha256:" + "a" * 64],
                 estimated_cost_usd=float(grant.get("spending_limit_usd", 0.0)), requested_capability=action_class,
                 expected_outcome=expected_outcome)
    return gate.run(p, executor=executor, standing_grant=grant)
