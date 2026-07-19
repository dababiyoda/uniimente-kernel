"""Layer 7 acceptance tests: the Agent Embassy.

Foreign agents present at the embassy and receive short-lived, minimum-
privilege guest passports. Every guest request routes through the
Consequence Gate; anything beyond the guest ceiling is refused at the
embassy, before the gate is even consulted.
"""
import os
import pytest

from compiler.ucl_compiler import compile_constitution
from embassy.gate import AgentEmbassy, EmbassyRefused, GUEST_TTL_CEILING_S
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from policy.engine import Proposal
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _stack():
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    embassy = AgentEmbassy(passports, gate, ledger)
    return embassy, passports, ledger


def _proposal(actor_id, **kw):
    base = dict(actor=actor_id, legal_principal="alfonso_lopez",
                action_class="draft.publish", objective="guest draft",
                payload={"text": "hello"}, target="sandbox:outbox",
                consequence_class="read_only", evidence_confidence=0.9,
                evidence_refs=["sha256:" + "a" * 64], estimated_cost_usd=0.0,
                requested_capability="draft.publish", expected_outcome="queued")
    base.update(kw)
    return Proposal(**base)


class TestAdmission:
    def test_guest_gets_minimum_privilege_passport(self):
        embassy, _, _ = _stack()
        p = embassy.present(foreign_id="mcp://partner-agent", origin="mcp",
                            declared_capabilities=["read_packet"])
        assert p.kind == "connector"
        assert p.budget_ceiling_usd == 0.0
        assert p.consequence_class == "internal_write"
        assert p.authority is None                       # identity != authority

    def test_guest_ttl_clamped(self):
        embassy, _, _ = _stack()
        p = embassy.present(foreign_id="a2a://x", origin="a2a",
                            declared_capabilities=[], requested_ttl_s=999_999)
        from datetime import datetime
        issued = datetime.fromisoformat(p.issued_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(p.expires_at.replace("Z", "+00:00"))
        assert (expires - issued).total_seconds() <= GUEST_TTL_CEILING_S

    def test_admission_ledgered(self):
        embassy, _, ledger = _stack()
        embassy.present(foreign_id="mcp://a", origin="mcp", declared_capabilities=[])
        types = [r.payload["type"] for r in ledger.by_type("event")]
        assert "embassy.admitted" in types


class TestRequests:
    def test_read_only_guest_request_flows_through_gate(self):
        embassy, _, ledger = _stack()
        p = embassy.present(foreign_id="mcp://a", origin="mcp",
                            declared_capabilities=["draft.publish"])
        rec = embassy.request(p.passport_id, _proposal(p.passport_id),
                              executor=lambda pr: {"observed_outcome": "queued",
                                                   "result_class": "positive"})
        assert rec.state == "recorded"
        types = [r.payload["type"] for r in ledger.by_type("event")]
        assert "embassy.request_routed" in types

    def test_external_contact_refused_at_embassy(self):
        embassy, _, _ = _stack()
        p = embassy.present(foreign_id="mcp://a", origin="mcp",
                            declared_capabilities=["draft.publish"])
        with pytest.raises(EmbassyRefused, match="ceiling"):
            embassy.request(p.passport_id,
                            _proposal(p.passport_id, consequence_class="external_contact"),
                            executor=lambda pr: {})

    def test_cost_bearing_request_refused(self):
        embassy, _, _ = _stack()
        p = embassy.present(foreign_id="mcp://a", origin="mcp", declared_capabilities=[])
        with pytest.raises(EmbassyRefused, match="zero budget"):
            embassy.request(p.passport_id,
                            _proposal(p.passport_id, estimated_cost_usd=1.0),
                            executor=lambda pr: {})

    def test_revoked_guest_cannot_request(self):
        embassy, passports, _ = _stack()
        p = embassy.present(foreign_id="mcp://a", origin="mcp", declared_capabilities=[])
        passports.revoke(p.passport_id, reason="guest misbehaved", revoker="alfonso")
        with pytest.raises(EmbassyRefused, match="identity invalid"):
            embassy.request(p.passport_id, _proposal(p.passport_id),
                            executor=lambda pr: {})
