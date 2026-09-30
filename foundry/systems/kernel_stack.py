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
