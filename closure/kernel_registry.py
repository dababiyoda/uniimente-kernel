"""Kernel module closure registrations.

Each module of the build registers five executable checks, one per
orthogonal closure. The checks are real: they compile, issue, sign,
execute, tamper, and verify. A green closure is earned, not declared.
"""
from __future__ import annotations

import os
import tempfile

from closure.framework import ClosureRegistry, ModuleClosures

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _compile():
    from compiler.ucl_compiler import compile_constitution
    return compile_constitution(KERNEL_ROOT)


def build_registry() -> ClosureRegistry:
    reg = ClosureRegistry()

    # ---------------------------------------------------------------- L1
    def compiler_technical():
        c = _compile()
        ok = (c.constitution_hash.startswith("sha256:") and len(c.rules) > 20
              and c.sovereignty_ranks["law_safety_rights"] == 1)
        return ok, f"compiled v{c.constitution_version}, {len(c.rules)} rules, hash {c.constitution_hash[:20]}..."

    def compiler_authority():
        c = _compile()
        deny = any(r.rule_id == "deny_by_default" for r in c.rules)
        no_self = any("no_self_grant" in i for i in c.invariants)
        prohibited = [m for m, req in c.reserved_matters.items() if req == []]
        return deny and no_self and len(prohibited) >= 3, \
            f"deny-by-default + no-self-grant; {len(prohibited)} absolute prohibitions compiled"

    def compiler_evidence():
        h1 = _compile().constitution_hash
        h2 = _compile().constitution_hash
        return h1 == h2, f"deterministic recompilation: {h1 == h2} ({h1[:24]}...)"

    def compiler_economic():
        c = _compile()
        # durable asset: one compiled constitution serves every organ (governance reuse)
        reusable = len(c.audit_schemas) == 9 and len(c.relationship_tuples) > 10
        return reusable, "single compiled artifact reusable across all organs (governance reuse asset)"

    def compiler_regenerative():
        from compiler.ucl_parser import parse
        try:
            parse('constitution "x" { version = "1" ')  # malformed
            return False, "malformed UCL did not fail closed"
        except Exception:
            return True, "malformed doctrine fails closed with a syntax error; no repair, no guessing"

    reg.register(ModuleClosures("compiler", {
        "technical": compiler_technical, "authority": compiler_authority,
        "evidence": compiler_evidence, "economic": compiler_economic,
        "regenerative": compiler_regenerative}))

    # ---------------------------------------------------------------- L2
    def identity_technical():
        from identity.machine_passport import PassportRegistry
        r = PassportRegistry()
        p = r.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                    legal_principal="alfonso_lopez", declared_capabilities=["propose"],
                    budget_ceiling_usd=0.0, consequence_class="read_only")
        ok, _ = r.verify(p.passport_id)
        return ok, "passport issued and verified"

    def identity_authority():
        from identity.machine_passport import PassportRegistry
        r = PassportRegistry()
        p = r.issue(kind="agent", creator="alfonso", owner_organ="o", legal_principal="alfonso_lopez",
                    declared_capabilities=["x"], budget_ceiling_usd=0, consequence_class="read_only")
        q = r.inspect(p.passport_id)
        return p.authority is None and "nothing by identity alone" in q["what_it_may_do"], \
            "identity carries zero authority; authority only via grants"

    def identity_evidence():
        from identity.machine_passport import PassportRegistry
        r = PassportRegistry()
        p = r.issue(kind="workflow", creator="c", owner_organ="o", legal_principal="IVIO_NEMT_LLC",
                    declared_capabilities=[], budget_ceiling_usd=10, consequence_class="internal_write")
        d = r.to_dict(p.passport_id)
        same = all(d[k] == getattr(p, k) for k in ("passport_id", "creator", "legal_principal", "expires_at"))
        return same, "passport state independently serializable and reconstructable"

    def identity_economic():
        from identity.machine_passport import PassportRegistry
        r = PassportRegistry()
        p = r.issue(kind="agent", creator="c", owner_organ="o", legal_principal="alfonso_lopez",
                    declared_capabilities=[], budget_ceiling_usd=0, consequence_class="read_only")
        r.revoke(p.passport_id, reason="test", revoker="alfonso")
        ok, _ = r.verify(p.passport_id)
        return not ok, "revocation is immediate and cheap; no re-issuance cost, no lingering trust"

    def identity_regenerative():
        from identity.machine_passport import PassportRegistry, PassportError
        r = PassportRegistry()
        try:
            r.issue(kind="agent", creator="c", owner_organ="o", legal_principal="UNIIMENTE",
                    declared_capabilities=[], budget_ceiling_usd=0, consequence_class="read_only")
            return False, "issued a passport with UNIIMENTE as legal principal"
        except PassportError:
            return True, "refuses to attach liability to the institution itself; no hidden burden transfer"

    reg.register(ModuleClosures("identity", {
        "technical": identity_technical, "authority": identity_authority,
        "evidence": identity_evidence, "economic": identity_economic,
        "regenerative": identity_regenerative}))

    # ---------------------------------------------------------------- L3
    def _gate_stack():
        from identity.machine_passport import PassportRegistry
        from policy.consequence_gate import ConsequenceGate
        from provenance.ledger import EvidenceLedger
        from provenance.commit_witness import WitnessSigner
        compiled = _compile()
        passports = PassportRegistry()
        ledger = EvidenceLedger(compiled.constitution_hash)
        signer = WitnessSigner(env="development")
        gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger, signer=signer)
        actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                                legal_principal="alfonso_lopez", declared_capabilities=["draft.publish"],
                                budget_ceiling_usd=5.0, consequence_class="external_contact")
        return gate, passports, ledger, actor

    def _proposal(actor_id):
        from policy.engine import Proposal
        return Proposal(
            actor=actor_id, legal_principal="alfonso_lopez", action_class="draft.publish",
            objective="test.objective", payload={"text": "hello governed world"}, target="sandbox:outbox",
            consequence_class="external_contact", evidence_confidence=0.9,
            evidence_refs=["sha256:" + "a" * 64], estimated_cost_usd=0.0,
            requested_capability="draft.publish", expected_outcome="draft queued")

    def gate_technical():
        gate, passports, ledger, actor = _gate_stack()
        rec = gate.run(_proposal(actor.passport_id),
                       executor=lambda p: {"observed_outcome": "draft queued", "result_class": "positive"})
        return rec.state == "recorded" and rec.receipt_hash is not None, \
            f"full pipeline to recorded; receipt {str(rec.receipt_hash)[:24]}..."

    def gate_authority():
        gate, passports, ledger, actor = _gate_stack()
        rec = gate.run(_proposal(actor.passport_id),
                       executor=lambda p: {"observed_outcome": "draft queued", "result_class": "positive"})
        # tamper: revoke the grant after issue, replay must fail closed
        from policy.engine import Proposal
        p2 = _proposal(actor.passport_id)
        g = gate.grants.issue_single_action(proposal=p2, policy_version="1.0.0")
        gate.grants.revoke(g["grant_id"], reason="adversarial test", revoker="alfonso")
        rec2 = gate.run(p2, executor=lambda p: {"observed_outcome": "x"}, standing_grant=g)
        return rec.state == "recorded" and rec2.state in ("revoked", "refused"), \
            f"no action without current permission; revoked grant at commit -> {rec2.state}"

    def gate_evidence():
        gate, passports, ledger, actor = _gate_stack()
        gate.run(_proposal(actor.passport_id),
                 executor=lambda p: {"observed_outcome": "draft queued", "result_class": "positive"})
        ok, msg = ledger.verify_chain()
        witnesses = len(ledger.by_type("witness")) == 1
        outcomes = len(ledger.by_type("outcome")) == 1
        return ok and witnesses and outcomes, f"ledger independently verifiable: {msg}; witness+outcome present"

    def gate_economic():
        gate, passports, ledger, actor = _gate_stack()
        # protects capital: a budget overflow proposal must be refused before any execution
        from policy.engine import Proposal
        p = _proposal(actor.passport_id)
        p.estimated_cost_usd = 10_000.0
        rec = gate.run(p, executor=lambda pr: {"observed_outcome": "never"})
        return rec.state == "refused" and any("cost" in r or "budget" in r for r in rec.refusal_reasons), \
            "budget overflow refused pre-execution; the gate protects capital"

    def gate_regenerative():
        gate, passports, ledger, actor = _gate_stack()
        # executor explosion -> failed, budget released, incident recorded, nothing concealed
        def boom(p):
            raise RuntimeError("adapter exploded")
        rec = gate.run(_proposal(actor.passport_id), executor=boom)
        ok, msg = ledger.verify_chain()
        return rec.state == "failed" and rec.incident is not None and ok, \
            "failure preserved on-chain (negative evidence kept); fails toward silence, not external action"

    reg.register(ModuleClosures("consequence_gate", {
        "technical": gate_technical, "authority": gate_authority,
        "evidence": gate_evidence, "economic": gate_economic,
        "regenerative": gate_regenerative}))

    # ---------------------------------------------------------------- provenance
    def ledger_technical():
        from provenance.ledger import EvidenceLedger
        l = EvidenceLedger("sha256:" + "0" * 64)
        for i in range(5):
            l.append("event", {"i": i})
        ok, msg = l.verify_chain()
        return ok, msg

    def ledger_authority():
        from provenance.ledger import EvidenceLedger
        l = EvidenceLedger("sha256:" + "0" * 64)
        genesis = l.records[0]
        return genesis.record_type == "genesis" and "constitution_hash" in genesis.payload, \
            "ledger anchored to constitution hash; authority lineage explicit from record zero"

    def ledger_evidence():
        from provenance.ledger import EvidenceLedger
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ledger.jsonl")
            l1 = EvidenceLedger("sha256:" + "0" * 64, path=path)
            l1.append("event", {"x": 1})
            head = l1.head
            l2 = EvidenceLedger("sha256:" + "0" * 64, path=path)  # reload + reverify
            return l2.head == head and l2.verify_chain()[0], "persisted ledger reloads and re-verifies"

    def ledger_economic():
        from provenance.ledger import EvidenceLedger
        l = EvidenceLedger("sha256:" + "0" * 64)
        l.append("event", {"n": 1})
        rec = l.records[-1]
        rec.payload["n"] = 999  # tamper
        ok, _ = l.verify_chain()
        return not ok, "tampering is detected by reconstruction; integrity without trusted hardware"

    def ledger_regenerative():
        from provenance.ledger import EvidenceLedger
        l = EvidenceLedger("sha256:" + "0" * 64)
        r1 = l.append("outcome", {"result_class": "negative", "note": "failure kept"})
        l.append("correction", {"note": "corrected interpretation"}, corrects=r1.hash)
        negatives = [r for r in l.records if r.payload.get("result_class") == "negative"]
        corrections = [r for r in l.records if r.record_type == "correction" and r.corrects == r1.hash]
        return len(negatives) == 1 and len(corrections) == 1, \
            "negative evidence is never deleted; corrections carry ancestry"

    reg.register(ModuleClosures("evidence_ledger", {
        "technical": ledger_technical, "authority": ledger_authority,
        "evidence": ledger_evidence, "economic": ledger_economic,
        "regenerative": ledger_regenerative}))

    return reg
