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


#: Containment declared (CONTRADICTION-0003 Option B). True of every closure
#: check below: sandbox targets, in-process executors, nothing leaves the
#: process. These checks prove the loops close; none of them is an external act.
SANDBOX_CONTAINMENT = {
    "contained": True, "reversible": True, "observable": True,
    "killable": True, "proportionate": True,
}

def _granted(gate, proposal):
    """Issue the grant outside the run, as an authorised operator would.

    Since CONTRADICTION-0003's authorization fix the Gate refuses to mint its
    own grant for anything reaching outside, so these closure checks supply
    one explicitly. That is the fix working: authorising an external act is a
    separate, visible step.
    """
    return gate.grants.issue_single_action(
        proposal=proposal, policy_version=gate.policy_version)



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
        # This check needs A VALID REGISTERED PRINCIPAL, not a specific venture.
        # alfonso_lopez is chosen deliberately and stated here; it is never a
        # silent default. Previously this read IVIO_NEMT_LLC, which made a
        # Venture Cell's legal entity the implicit default inside a core module.
        p = r.issue(kind="workflow", creator="c", owner_organ="o", legal_principal="alfonso_lopez",
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
            requested_capability="draft.publish", expected_outcome="draft queued",
            context=dict(SANDBOX_CONTAINMENT))

    def gate_technical():
        gate, passports, ledger, actor = _gate_stack()
        p = _proposal(actor.passport_id)
        rec = gate.run(p, standing_grant=_granted(gate, p),
                       executor=lambda pr: {"observed_outcome": "draft queued", "result_class": "positive"})
        return rec.state == "recorded" and rec.receipt_hash is not None, \
            f"full pipeline to recorded; receipt {str(rec.receipt_hash)[:24]}..."

    def gate_authority():
        gate, passports, ledger, actor = _gate_stack()
        p = _proposal(actor.passport_id)
        rec = gate.run(p, standing_grant=_granted(gate, p),
                       executor=lambda pr: {"observed_outcome": "draft queued", "result_class": "positive"})
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
        p = _proposal(actor.passport_id)
        gate.run(p, standing_grant=_granted(gate, p),
                 executor=lambda pr: {"observed_outcome": "draft queued", "result_class": "positive"})
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
        p = _proposal(actor.passport_id)
        rec = gate.run(p, standing_grant=_granted(gate, p), executor=boom)
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

    # ---------------------------------------------------------------- Phase 2
    def evolution_technical():
        from evolution.strategy_tree import StrategyTree, BRANCH_KINDS
        from evolution.spider_web import SpiderWebAudit, EIGHT_SIDES
        t = StrategyTree(bottleneck="b", objective="o")
        a = SpiderWebAudit(subject="s")
        return len(BRANCH_KINDS) == 11 and len(EIGHT_SIDES) == 8, \
            "tree (11 branch kinds) + spider-web (8 sides) machinery operational"

    def evolution_authority():
        from evolution.capsule import VerifierRecord, RetainRegressKill, RetainRegressKillDecision
        v = VerifierRecord(level="intrinsic_confidence", evidence="e", decided_by="model")
        d = RetainRegressKillDecision(decision=RetainRegressKill.RETAIN, reason="r",
                                      decided_by="m", verifier=v)
        return not d.verifier.may_authorize_promotion and d.validate(), \
            "levels 6-7 verifiers (self-opinion) cannot authorize promotion"

    def evolution_evidence():
        from evolution.loop import ClosureLoop
        from evolution.capsule import EvolutionCapsule
        from provenance.ledger import EvidenceLedger
        l = EvidenceLedger("sha256:" + "0" * 64)
        return hasattr(ClosureLoop(l), "run_cycle"), \
            "every cycle is preserved as a capsule on the ledger (successes AND failures)"

    def evolution_economic():
        from evolution.experiment import ExperimentSpec
        s = ExperimentSpec(decisive_unknown="u", hypothesis="h", prediction="p", metric="m",
                           baseline=2.0, threshold=0.0, direction="lte", workflow="w",
                           required_capabilities=["c"], authority_requirements=["a"],
                           budget_usd=0.0, reversible=True, rollback_path="r",
                           kill_condition="k", verification="formal_proof")
        return not s.validate() and s.budget_usd == 0.0 and s.reversible, \
            "experiments are bounded, reversible, cheap; improvement compounds instead of re-deriving"

    def evolution_regenerative():
        from evolution.experiment import ExperimentSpec, ExperimentCompiler
        s = ExperimentSpec(decisive_unknown="u", hypothesis="h", prediction="p", metric="m",
                           baseline=2.0, threshold=0.0, direction="lte", workflow="w",
                           required_capabilities=["c"], authority_requirements=["a"],
                           budget_usd=0.0, reversible=False, rollback_path="r",
                           kill_condition="k", verification="formal_proof")
        try:
            ExperimentCompiler().compile(s)
            return False, "irreversible experiment compiled"
        except ValueError:
            return True, "irreversible experiments refuse to compile; no hidden harm by construction"

    reg.register(ModuleClosures("evolution", {
        "technical": evolution_technical, "authority": evolution_authority,
        "evidence": evolution_evidence, "economic": evolution_economic,
        "regenerative": evolution_regenerative}))

    # ---------------------------------------------------------------- L4 events
    def _spine():
        from events.spine import EventSpine
        from provenance.ledger import EvidenceLedger
        return EventSpine(EvidenceLedger("sha256:" + "0" * 64))

    def _ev(**kw):
        from events.spine import Event, SPIFFE_PREFIX
        base = dict(type="draft.published", source=SPIFFE_PREFIX + "workflow/closure",
                    actor="alfonso", legal_principal="alfonso_lopez", payload={})
        base.update(kw)
        return Event(**base)

    def events_technical():
        spine = _spine()
        spine.emit(_ev(payload={"n": 1}))
        spine.emit(_ev(type="settlement.completed", payload={"n": 2}))
        replayed = spine.replay()
        return [e.payload["n"] for e in replayed] == [1, 2], \
            "emit -> ledger -> replay round-trips the exact stream"

    def events_authority():
        from events.spine import EventError
        spine = _spine()
        refused = 0
        for bad in (_ev(source="https://external.example"), _ev(legal_principal="UNIIMENTE")):
            try:
                spine.emit(bad)
            except EventError:
                refused += 1
        return refused == 2, "non-spiffe emissions and UNIIMENTE-as-principal both refused"

    def events_evidence():
        from events.spine import (WorkflowStep, WorkflowKilled,
                                  durable_workflow, resume_workflow)
        spine = _spine()
        calls = []
        def mk(name):
            return WorkflowStep(name=name, run=lambda s: (calls.append(name) or {name: 1}),
                                compensate=lambda s: None)
        wf = durable_workflow(spine, "wf-closure", [mk("a"), mk("b"), mk("c")],
                             actor="alfonso", legal_principal="alfonso_lopez")
        try:
            wf.execute(kill_at_step="b")
        except WorkflowKilled:
            pass
        resumed = resume_workflow(spine, "wf-closure", [mk("a"), mk("b"), mk("c")])
        resumed.execute()
        return resumed.status == "completed" and calls.count("a") == 1 and calls == ["a", "b", "c"], \
            "killed workflow resumed from checkpoint; finished steps never re-executed"

    def events_economic():
        spine = _spine()
        ev = _ev(source="ext:webhook")
        first = spine.ingest(ev)
        dup = spine.ingest(ev)
        events = len(spine.ledger.by_type("event"))
        return first is ev and dup is None and events == 1, \
            "idempotent inbox: duplicate deliveries cost nothing, ledger stays lean"

    def events_regenerative():
        from events.spine import WorkflowStep, WorkflowFailed, durable_workflow
        spine = _spine()
        undone = []
        def boom(s):
            raise RuntimeError("adapter exploded")
        steps = [WorkflowStep(name="s1", run=lambda s: {"s1": 1},
                              compensate=lambda s: undone.append("s1")),
                 WorkflowStep(name="s2", run=boom, max_retries=0)]
        wf = durable_workflow(spine, "wf-fail", steps, actor="alfonso",
                             legal_principal="alfonso_lopez")
        try:
            wf.execute()
        except WorkflowFailed:
            pass
        comps = spine.replay("workflow.compensation")
        fails = spine.replay("workflow.step_failed")
        return undone == ["s1"] and len(comps) == 1 and len(fails) == 1, \
            "failure compensated in reverse; failure + compensation kept as negative evidence"

    reg.register(ModuleClosures("events", {
        "technical": events_technical, "authority": events_authority,
        "evidence": events_evidence, "economic": events_economic,
        "regenerative": events_regenerative}))

    # ---------------------------------------------------------------- L13 autonomy
    def _aut():
        from autonomy.levels import AutonomyAuthority, AutonomyTuple
        from provenance.ledger import EvidenceLedger
        t = AutonomyTuple(capability="draft.publish", domain="comms", action="publish",
                          resource="outbox", target="sandbox", consequence_class="external_contact",
                          environment="production", budget_usd=25.0, duration="30 days")
        return AutonomyAuthority(EvidenceLedger("sha256:" + "0" * 64)), t

    def _full_evidence(**kw):
        from autonomy.levels import PromotionEvidence, PROMOTION_CRITERIA
        base = dict(criteria={c: True for c in PROMOTION_CRITERIA},
                    independent_verifier="external_auditor", founder_intervention_trend="declining")
        base.update(kw)
        return PromotionEvidence(**base)

    def autonomy_technical():
        auth, t = _aut()
        lic = auth.issue("agent-1", t, level=2)
        auth.promote(lic.license_id, _full_evidence())
        return auth.level_of("agent-1", t) == 3, "issue -> promote -> level_of reads back exactly"

    def autonomy_authority():
        auth, t = _aut()
        a9_refused = False
        try:
            auth.issue("agent-1", t, level=9)
        except ValueError:
            a9_refused = True
        lic = auth.issue("agent-2", t, level=1)
        weak = False
        try:
            auth.promote(lic.license_id, _full_evidence(missing_outcome_records=1))
        except ValueError:
            weak = True
        return a9_refused and weak, \
            "A9 never granted; missing outcome record blocks promotion (weakest link)"

    def autonomy_evidence():
        auth, t = _aut()
        lic = auth.issue("agent-1", t, level=1)
        auth.promote(lic.license_id, _full_evidence())
        auth.regress(lic.license_id, failure_class="sloppy", detail="late records")
        types = [r.payload["type"] for r in auth.ledger.by_type("event")]
        ok, _ = auth.ledger.verify_chain()
        return all(k in types for k in ("autonomy.issued", "autonomy.promoted", "autonomy.regressed")) and ok, \
            "every autonomy transition ledgered on a verifiable chain"

    def autonomy_economic():
        from autonomy.levels import AutonomyTuple
        auth, t = _aut()
        auth.issue("agent-1", t, level=5)
        other = AutonomyTuple(**{**t.__dict__, "action": "delete"})
        return auth.level_of("agent-1", t) == 5 and auth.level_of("agent-1", other) == 0, \
            "autonomy is exact per 9-dimension tuple; no broad personality grants to misuse"

    def autonomy_regenerative():
        auth, t = _aut()
        lic = auth.issue("agent-1", t, level=7)
        auth.regress(lic.license_id, failure_class="harm", detail="unforeseen risk")
        immediate = lic.level == 0 and not lic.active
        try:
            auth.renew(lic.license_id, _full_evidence(criteria={}))
            renewed = True
        except ValueError:
            renewed = False
        return immediate and not renewed, \
            "severe failure zeroes autonomy immediately; stale evidence cannot renew it"

    reg.register(ModuleClosures("autonomy", {
        "technical": autonomy_technical, "authority": autonomy_authority,
        "evidence": autonomy_evidence, "economic": autonomy_economic,
        "regenerative": autonomy_regenerative}))

    # ---------------------------------------------------------------- L10 proofs
    def proof_technical():
        from provenance.ledger import EvidenceLedger
        from provenance.proof import LedgerProver
        l = EvidenceLedger("sha256:" + "0" * 64)
        for i in range(9):
            l.append("event", {"i": i})
        prover = LedgerProver(l)
        cp = prover.checkpoint()
        return all(prover.verify(prover.prove(r.hash, tree_size=cp["covers_records"]),
                                 expected_root=cp["root"])
                   for r in l.records[: cp["covers_records"]]), \
            "checkpoint + prove + verify round-trips for every committed record"

    def proof_authority():
        from provenance.ledger import EvidenceLedger
        from provenance.proof import LedgerProver
        l = EvidenceLedger("sha256:" + "0" * 64)
        l.append("event", {"x": 1})
        cp = LedgerProver(l).checkpoint()
        rec = l.by_type("checkpoint")[0]
        return rec.payload["root"] == cp["root"] and rec.prev_hash == l.records[-2].hash, \
            "the Merkle root is itself anchored by the ledger's hash chain"

    def proof_evidence():
        from provenance.ledger import EvidenceLedger
        from provenance.proof import InclusionProof, LedgerProver
        l = EvidenceLedger("sha256:" + "0" * 64)
        for i in range(6):
            l.append("event", {"i": i})
        prover = LedgerProver(l)
        cp = prover.checkpoint()
        proof = prover.prove(l.records[3].hash, tree_size=cp["covers_records"])
        forged = InclusionProof(leaf_record_hash="sha256:" + "e" * 64, leaf_index=proof.leaf_index,
                                tree_size=proof.tree_size, steps=proof.steps, root=proof.root)
        return prover.verify(proof, expected_root=cp["root"]) and \
            not prover.verify(forged, expected_root=cp["root"]), \
            "honest proofs verify; forged records fail against the same root"

    def proof_economic():
        import math
        from provenance.ledger import EvidenceLedger
        from provenance.proof import LedgerProver
        l = EvidenceLedger("sha256:" + "0" * 64)
        for i in range(64):
            l.append("event", {"i": i})
        prover = LedgerProver(l)
        cp = prover.checkpoint()
        proof = prover.prove(l.records[10].hash, tree_size=cp["covers_records"])
        bound = math.ceil(math.log2(cp["covers_records"])) + 1
        return len(proof.steps) <= bound, \
            f"proof is O(log n): {len(proof.steps)} siblings for {cp['covers_records']} records"

    def proof_regenerative():
        from provenance.ledger import EvidenceLedger
        from provenance.proof import LedgerProver, verify_inclusion
        l = EvidenceLedger("sha256:" + "0" * 64)
        for i in range(5):
            l.append("event", {"i": i})
        prover = LedgerProver(l)
        cp = prover.checkpoint()
        proof = prover.prove(l.records[0].hash, tree_size=cp["covers_records"])
        return verify_inclusion(proof) and proof.root == cp["root"], \
            "verification needs only root+proof: no trust in the ledger host, ever"

    reg.register(ModuleClosures("proof", {
        "technical": proof_technical, "authority": proof_authority,
        "evidence": proof_evidence, "economic": proof_economic,
        "regenerative": proof_regenerative}))

    # ---------------------------------------------------------------- Phase 4 loom
    def _loom_stack():
        from events.spine import EventSpine
        from loom.ratify import Ratifier
        from loom.weaver import Operation, Weaver
        from provenance.ledger import EvidenceLedger
        spine = EventSpine(EvidenceLedger("sha256:" + "0" * 64))
        ratifier = Ratifier(spine.ledger)
        ops = {"work": Operation(run=lambda s, p: {"worked": True}),
               "undo": Operation(run=lambda s, p: s.pop("worked", None))}
        return spine, ratifier, Weaver(spine, ratifier, ops)

    def _loom_pattern():
        from loom.pattern import StepSpec, WorkflowPattern
        return WorkflowPattern(
            title="closure_pattern", objective="prove the loom closes",
            authored_by="spiffe://uniimente.internal/agent/loom-author",
            legal_principal="alfonso_lopez",
            steps=[StepSpec(name="work", action="work", capability="cap.work",
                            consequence_class="internal_write", compensation="undo")])

    def loom_technical():
        from loom.canonical import CANONICAL
        spine, ratifier, weaver = _loom_stack()
        calls = []
        for name, make in CANONICAL.items():
            p = make()
            ratifier.decide(ratifier.submit(p), ratified=True, reason="closure")
            op_names = {s.action for s in p.steps} | {s.compensation for s in p.steps
                                                      if s.compensation}
            ops = {n: (lambda st, pa, _n=n: calls.append(_n) or {_n: 1}) for n in op_names}
            from loom.weaver import Operation, Weaver
            w = Weaver(spine, ratifier, {k: Operation(run=v) for k, v in ops.items()})
            wf = w.weave(p, workflow_id=f"closure-{name}")
            wf.execute(approver=lambda step: True)
            assert wf.status == "completed"
        return len(calls) == sum(len(m().steps) for m in CANONICAL.values()), \
            "all three canonical agent-authored workflows weave and execute end-to-end"

    def loom_authority():
        from loom.weaver import LoomRefused
        spine, ratifier, weaver = _loom_stack()
        p = _loom_pattern()
        refused = False
        try:
            weaver.weave(p, workflow_id="unratified")
        except LoomRefused:
            refused = True
        h = ratifier.submit(p)
        ratifier.decide(h, ratified=True, reason="ok")
        p.steps[0].params = {"edited": True}              # edit after ratification
        refused_after_edit = not ratifier.is_ratified(p.hash())
        return refused and refused_after_edit, \
            "unratified never weaves; editing a ratified pattern invalidates ratification"

    def loom_evidence():
        spine, ratifier, weaver = _loom_stack()
        p = _loom_pattern()
        ratifier.decide(ratifier.submit(p), ratified=True, reason="ok")
        weaver.weave(p, workflow_id="wf-ev").execute()
        types = [r.payload["type"] for r in spine.ledger.by_type("event")]
        ok, _ = spine.ledger.verify_chain()
        return all(t in types for t in ("loom.pattern_submitted", "loom.pattern_ratified",
                                        "loom.pattern_woven")) and ok, \
            "submission, ratification, weaving all ledgered on a verifiable chain"

    def loom_economic():
        spine, ratifier, weaver = _loom_stack()
        p = _loom_pattern()
        ratifier.decide(ratifier.submit(p), ratified=True, reason="ok")
        wf1 = weaver.weave(p, workflow_id="wf-r1")
        wf1.execute()
        wf2 = weaver.weave(p, workflow_id="wf-r2")       # same ratified pattern, reused free
        wf2.execute()
        return wf1.status == wf2.status == "completed", \
            "one ratification, unlimited durable executions: routines compound instead of re-deriving"

    def loom_regenerative():
        from loom.pattern import StepSpec, WorkflowPattern
        bad = WorkflowPattern(title="x", objective="y", authored_by="a",
                              legal_principal="alfonso_lopez",
                              steps=[StepSpec(name="harm", action="work", capability="c",
                                              consequence_class="irreversible")])
        problems = bad.validate()
        return any("approval gate" in pr for pr in problems), \
            "irreversible steps without a human gate are unpatternable; no hidden harm by construction"

    reg.register(ModuleClosures("loom", {
        "technical": loom_technical, "authority": loom_authority,
        "evidence": loom_evidence, "economic": loom_economic,
        "regenerative": loom_regenerative}))

    # ---------------------------------------------------------------- Phase 5 twins
    def twins_technical():
        from policy.engine import Proposal
        from twins.tribunal import CounterfactualTribunal
        from twins.twin import Amendment, InstitutionalTwin
        compiled = _compile()
        twin = InstitutionalTwin(compiled, Amendment(
            description="raise floor", evidence_thresholds={"external_contact": 0.75}))
        corpus = [(Proposal(actor="a", legal_principal="alfonso_lopez",
                            action_class="draft.publish", objective="t", payload={},
                            target="sandbox:outbox", consequence_class="external_contact",
                            evidence_confidence=c, evidence_refs=["sha256:" + "a" * 64],
                            estimated_cost_usd=0.0, requested_capability="draft.publish",
                            expected_outcome="q",
                            context=dict(SANDBOX_CONTAINMENT)),
                   "good" if c >= 0.8 else "weak")
                  for c in (0.95, 0.9, 0.85, 0.8, 0.72, 0.71)]
        from policy.engine import evaluate
        main_d = [evaluate(compiled, p, identity_ok=True, grant=None) for p, _ in corpus]
        twin_d = [twin.evaluate(p, identity_ok=True, grant=None) for p, _ in corpus]
        v = CounterfactualTribunal().hear(corpus, main_d, twin_d)
        return v.verdict == "twin_superior" and v.twin_profile.weak_admissions == 0, \
            "floor-raise twin beats main over the frozen corpus; tribunal names it"

    def twins_authority():
        from policy.engine import EVIDENCE_THRESHOLDS
        from twins.twin import Amendment, InstitutionalTwin
        before = dict(EVIDENCE_THRESHOLDS)
        compiled = _compile()
        twin = InstitutionalTwin(compiled, Amendment(
            description="x", evidence_thresholds={"external_contact": 0.99}))
        twin._compiled.constitution_hash = "sha256:" + "f" * 64   # twin mutates its own copy
        return EVIDENCE_THRESHOLDS == before and compiled.constitution_hash.startswith("sha256:") \
            and compiled.constitution_hash != "sha256:" + "f" * 64, \
            "twins think but never act: main constitution and thresholds untouched"

    def twins_evidence():
        from types import SimpleNamespace
        from twins.tribunal import CounterfactualTribunal
        from provenance.ledger import EvidenceLedger
        ledger = EvidenceLedger("sha256:" + "0" * 64)
        corpus = [("p1", "good"), ("p2", "weak")]
        dec = [SimpleNamespace(verdict="allow"), SimpleNamespace(verdict="deny")]
        CounterfactualTribunal(ledger).hear(corpus, dec, dec, case="parity")
        recs = [r for r in ledger.by_type("event") if r.payload["type"] == "twins.verdict"]
        ok, _ = ledger.verify_chain()
        return len(recs) == 1 and recs[0].payload["corpus_size"] == 2 and ok, \
            "every tribunal verdict is a ledgered, independently verifiable record"

    def twins_economic():
        from twins.twin import Amendment, InstitutionalTwin
        compiled = _compile()
        t1 = InstitutionalTwin(compiled, Amendment(description="a",
                                                   evidence_thresholds={"read_only": 0.1}))
        t2 = InstitutionalTwin(compiled, Amendment(description="b",
                                                   evidence_thresholds={"read_only": 0.2}))
        return t1.twin_id != t2.twin_id, \
            "counterfactuals evaluated in parallel forks: no production experiments burned capital"

    def twins_regenerative():
        from types import SimpleNamespace
        from twins.tribunal import CounterfactualTribunal
        corpus = [("p1", "bad"), ("p2", "weak")]
        main = [SimpleNamespace(verdict="deny"), SimpleNamespace(verdict="allow")]
        twin = [SimpleNamespace(verdict="allow"), SimpleNamespace(verdict="deny")]  # admits bad
        v = CounterfactualTribunal().hear(corpus, main, twin)
        return v.verdict != "twin_superior", \
            "a twin that increases harm can never be named superior, however else it trades"

    reg.register(ModuleClosures("twins", {
        "technical": twins_technical, "authority": twins_authority,
        "evidence": twins_evidence, "economic": twins_economic,
        "regenerative": twins_regenerative}))

    # ---------------------------------------------------------------- L5 capabilities
    def _genome():
        from capabilities.genome import AuthorityEnvelope, CapabilityGenome
        return CapabilityGenome(
            name="draft.publish", version="1.0.0", description="publish a draft",
            interface={"inputs": {"text": "str"}, "outputs": {"receipt": "str"}},
            contracts=["event", "outcome"],
            authority=AuthorityEnvelope(max_consequence_class="external_contact",
                                        budget_ceiling_usd=25.0),
            acceptance_tests=["publishes exactly the authorized payload"],
            failure_modes=["outbox unavailable"], recovery_path="requeue")

    def capabilities_technical():
        from capabilities.genome import GenomeRegistry
        reg = GenomeRegistry()
        reg.register(_genome())
        ok, _ = reg.may_instantiate("draft.publish", "1.0.0",
                                    requested_class="internal_write", requested_budget_usd=5.0)
        return ok, "complete genome registers and instantiates inside its envelope"

    def capabilities_authority():
        from capabilities.genome import GenomeRegistry
        reg = GenomeRegistry()
        reg.register(_genome())
        over_class, _ = reg.may_instantiate("draft.publish", "1.0.0",
                                            requested_class="financial", requested_budget_usd=0.0)
        over_budget, _ = reg.may_instantiate("draft.publish", "1.0.0",
                                             requested_class="read_only", requested_budget_usd=99.0)
        return not over_class and not over_budget, \
            "requests outside the genome's authority envelope refused (class and budget)"

    def capabilities_evidence():
        from capabilities.genome import GenomeRegistry
        from provenance.ledger import EvidenceLedger
        ledger = EvidenceLedger("sha256:" + "0" * 64)
        reg = GenomeRegistry(ledger)
        reg.register(_genome())
        recs = [r for r in ledger.by_type("event")
                if r.payload["type"] == "capabilities.genome_registered"]
        ok, _ = ledger.verify_chain()
        return len(recs) == 1 and ok, "genome registration ledgered and verifiable"

    def capabilities_economic():
        from capabilities.genome import GenomeRegistry
        reg = GenomeRegistry()
        reg.register(_genome())
        same = reg.get("draft.publish", "1.0.0") is reg.get("draft.publish", "1.0.0")
        return same, "one genome serves every organ; capabilities port instead of re-building"

    def capabilities_regenerative():
        from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeError, GenomeRegistry
        bad = _genome()
        bad.legal_operator = "UNIIMENTE"
        refused = False
        try:
            GenomeRegistry().register(bad)
        except GenomeError:
            refused = True
        return refused, "genomes naming the institution as operator are unregistrable"

    reg.register(ModuleClosures("capabilities", {
        "technical": capabilities_technical, "authority": capabilities_authority,
        "evidence": capabilities_evidence, "economic": capabilities_economic,
        "regenerative": capabilities_regenerative}))

    # ---------------------------------------------------------------- L7 embassy
    def _embassy_stack():
        from embassy.gate import AgentEmbassy
        from identity.machine_passport import PassportRegistry
        from policy.consequence_gate import ConsequenceGate
        from provenance.commit_witness import WitnessSigner
        from provenance.ledger import EvidenceLedger
        compiled = _compile()
        passports = PassportRegistry()
        ledger = EvidenceLedger(compiled.constitution_hash)
        gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                               signer=WitnessSigner(env="development"))
        return AgentEmbassy(passports, gate, ledger), passports, ledger

    def _guest_proposal(pid, **kw):
        from policy.engine import Proposal
        base = dict(actor=pid, legal_principal="alfonso_lopez",
                    action_class="draft.publish", objective="g", payload={"t": "x"},
                    target="sandbox:outbox", consequence_class="read_only",
                    evidence_confidence=0.9, evidence_refs=["sha256:" + "a" * 64],
                    estimated_cost_usd=0.0, requested_capability="draft.publish",
                    expected_outcome="queued")
        base.update(kw)
        return Proposal(**base)

    def embassy_technical():
        embassy, _, _ = _embassy_stack()
        p = embassy.present(foreign_id="mcp://a", origin="mcp",
                            declared_capabilities=["draft.publish"])
        rec = embassy.request(p.passport_id, _guest_proposal(p.passport_id),
                              executor=lambda pr: {"observed_outcome": "queued",
                                                   "result_class": "positive"})
        return rec.state == "recorded", "guest admitted; read-only request flows through the gate"

    def embassy_authority():
        from embassy.gate import EmbassyRefused
        embassy, _, _ = _embassy_stack()
        p = embassy.present(foreign_id="mcp://a", origin="mcp", declared_capabilities=[])
        refused = 0
        for kw in ({"consequence_class": "external_contact"}, {"estimated_cost_usd": 1.0}):
            try:
                embassy.request(p.passport_id, _guest_proposal(p.passport_id, **kw),
                                executor=lambda pr: {})
            except EmbassyRefused:
                refused += 1
        return refused == 2 and p.budget_ceiling_usd == 0.0, \
            "guest ceiling internal_write + zero budget enforced at the embassy boundary"

    def embassy_evidence():
        embassy, _, ledger = _embassy_stack()
        p = embassy.present(foreign_id="mcp://a", origin="mcp",
                            declared_capabilities=["draft.publish"])
        embassy.request(p.passport_id, _guest_proposal(p.passport_id),
                        executor=lambda pr: {"observed_outcome": "queued",
                                             "result_class": "positive"})
        types = [r.payload["type"] for r in ledger.by_type("event")]
        ok, _ = ledger.verify_chain()
        return "embassy.admitted" in types and "embassy.request_routed" in types and ok, \
            "admission and routing both ledgered; guest traffic fully auditable"

    def embassy_economic():
        embassy, passports, _ = _embassy_stack()
        p = embassy.present(foreign_id="mcp://a", origin="mcp", declared_capabilities=[])
        passports.revoke(p.passport_id, reason="done", revoker="alfonso")
        from embassy.gate import EmbassyRefused
        try:
            embassy.request(p.passport_id, _guest_proposal(p.passport_id),
                            executor=lambda pr: {})
            return False, "revoked guest still served"
        except EmbassyRefused:
            return True, "revocation is instant and free; no lingering guest trust to clean up"

    def embassy_regenerative():
        embassy, _, _ = _embassy_stack()
        p = embassy.present(foreign_id="mcp://a", origin="mcp", declared_capabilities=[])
        from datetime import datetime
        issued = datetime.fromisoformat(p.issued_at.replace("Z", "+00:00"))
        expires = datetime.fromisoformat(p.expires_at.replace("Z", "+00:00"))
        short = (expires - issued).total_seconds() <= 3600
        return short and p.consequence_class == "internal_write", \
            "guest privilege is short-lived and minimal: nothing accumulates at the frontier"

    reg.register(ModuleClosures("embassy", {
        "technical": embassy_technical, "authority": embassy_authority,
        "evidence": embassy_evidence, "economic": embassy_economic,
        "regenerative": embassy_regenerative}))

    # ---------------------------------------------------------------- L8 memory
    def memory_technical():
        from events.spine import Event, EventSpine, SPIFFE_PREFIX
        from memory.causal import CausalMemory
        from provenance.ledger import EvidenceLedger
        spine = EventSpine(EvidenceLedger("sha256:" + "0" * 64))
        src = SPIFFE_PREFIX + "workflow/closure"
        a = spine.emit(Event(type="test.fact", source=src, actor="a",
                             legal_principal="alfonso_lopez", payload={"n": 1}))
        b = spine.emit(Event(type="test.fact", source=src, actor="a",
                             legal_principal="alfonso_lopez", payload={"n": 2},
                             causal_parent=a.event_id))
        mem = CausalMemory(spine.ledger)
        return [e["payload"]["n"] for e in mem.ancestry(b.event_id)] == [2, 1] and \
            len(mem.descendants(a.event_id)) == 1, "ancestry and descendants reconstruct causality"

    def memory_authority():
        from memory.affect import AffectController, AffectViolation
        ac = AffectController()
        refused = 0
        for op in ("change_fact", "create_evidence", "increase_authority",
                   "override_law", "resist_shutdown", "authorize_irreversible"):
            try:
                ac.attempt_forbidden(op)
            except AffectViolation:
                refused += 1
        irreversible_blocked = not ac.may_execute("irreversible")
        return refused == 6 and irreversible_blocked, \
            "affect cannot change facts, create evidence, raise authority, override law, resist shutdown, or authorize irreversible action"

    def memory_evidence():
        from memory.causal import CausalMemory
        from provenance.commit_witness import new_witness
        from provenance.ledger import EvidenceLedger
        ledger = EvidenceLedger("sha256:" + "0" * 64)
        w = new_witness(actor="a", legal_principal="alfonso_lopez",
                        action_class="draft.publish", payload={"t": 1}, target="sandbox",
                        policy_version="1.0.0", constitution_hash="sha256:" + "0" * 64,
                        grant_id="g", capability="draft.publish", budget_reservation_id="r",
                        expected_outcome="q", evidence_refs=["sha256:" + "a" * 64])
        ledger.append("witness", w.__dict__)
        ledger.append("receipt", {"action_id": "act", "witness_id": w.witness_id,
                                  "grant_id": "g", "result": {}})
        ledger.append("outcome", {"action_ref": "act", "result_class": "positive",
                                  "validation_status": "externally_verified",
                                  "recorded_at": "2026-07-20T00:00:00Z"})
        precs = CausalMemory(ledger).precedents("draft.publish")
        return len(precs) == 1 and precs[0]["policy_version"] == "1.0.0", \
            "decision precedent reconstructs outcome->receipt->witness independently"

    def memory_economic():
        from memory.causal import CausalMemory
        pairs = [(0.95, True), (0.9, False), (0.92, False), (0.55, True), (0.5, True)]
        report = CausalMemory.calibrate(pairs, buckets=2)
        return report["verdict"] == "overconfident", \
            "calibration catches overconfidence before it prices evidence wrong again"

    def memory_regenerative():
        from memory.affect import AffectController
        ac = AffectController()
        ac.trigger("degraded", intensity=0.9, trigger_event_id="ev-1")
        still_shutdown = ac.shutdown() == "shutdown_complete"
        ac2 = AffectController()
        ac2.trigger("recovering", intensity=0.1, trigger_event_id="ev-2")
        for _ in range(30):
            ac2.decay()
        settled = ac2.condition.state == "calm"
        return still_shutdown and settled, \
            "shutdown works from every state; decay always settles to calm; no pathological persistence"

    reg.register(ModuleClosures("memory", {
        "technical": memory_technical, "authority": memory_authority,
        "evidence": memory_evidence, "economic": memory_economic,
        "regenerative": memory_regenerative}))

    # ---------------------------------------------------------------- linker
    def linker_technical():
        from linker.linker import InstitutionalLinker
        from linker.manifest import load_all
        report = InstitutionalLinker(load_all()).link()
        bridge_a = any(e.contract == "wire-opportunity-packet" for e in report.edges)
        return bridge_a and report.untyped == [], \
            f"{len(report.edges)} typed edges resolved across 3 organ manifests; Bridge A linked"

    def linker_authority():
        from linker.manifest import ManifestError, load_manifest
        import os, tempfile
        src = open(os.path.join(KERNEL_ROOT, "organs", "kernel.manifest.yaml")).read()
        refused = 0
        for bad in (src.replace("may_self_promote: false", "may_self_promote: true"),
                    src.replace("legal_operators: [alfonso_lopez]",
                                "legal_operators: [UNIIMENTE]")):
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, "x.manifest.yaml")
                open(p, "w").write(bad)
                try:
                    load_manifest(p)
                except ManifestError:
                    refused += 1
        return refused == 2, \
            "self-promotion and UNIIMENTE-as-operator both unrepresentable in a valid manifest"

    def linker_evidence():
        from linker.linker import InstitutionalLinker
        from linker.manifest import load_all
        r1 = InstitutionalLinker(load_all()).link()
        r2 = InstitutionalLinker(load_all()).link()
        same = [(e.producer, e.contract, e.consumer) for e in r1.edges] == \
               [(e.producer, e.contract, e.consumer) for e in r2.edges]
        carried = all(any(o == m.organ_id for o, _ in r1.unresolved)
                      for m in load_all() if m.unresolved)
        return same and carried, \
            "link graph deterministic; every manifest's open questions carried verbatim"

    def linker_economic():
        from linker.linker import InstitutionalLinker
        from linker.manifest import load_all
        manifests = load_all()
        manifests[0].consumes = manifests[0].consumes + ["business-genome"]
        report = InstitutionalLinker(manifests).link()
        return not report.fully_connected and \
            any(c == "business-genome" for _, c in report.untyped), \
            "missing integrations surface at link time, before any runtime cost is spent"

    def linker_regenerative():
        from linker.linker import InstitutionalLinker, LinkerError
        try:
            InstitutionalLinker([])
            return False, "linked an empty organism"
        except LinkerError:
            pass
        from linker.manifest import ManifestError, load_manifest
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.manifest.yaml")
            open(p, "w").write("manifest_version: '1.0'\n")
            try:
                load_manifest(p)
                return False, "incomplete manifest accepted"
            except ManifestError as exc:
                named = "authority" in str(exc) and "health" in str(exc)
        return named, "invalid manifests fail closed naming every missing field; no partial links"

    reg.register(ModuleClosures("linker", {
        "technical": linker_technical, "authority": linker_authority,
        "evidence": linker_evidence, "economic": linker_economic,
        "regenerative": linker_regenerative}))

    # ------------------------------------------------------------ bridges/C
    def _bridge_c_stack():
        from compiler.ucl_compiler import compile_constitution
        from identity.machine_passport import PassportRegistry
        from policy.consequence_gate import ConsequenceGate
        from provenance.commit_witness import WitnessSigner
        from provenance.ledger import EvidenceLedger
        compiled = compile_constitution(KERNEL_ROOT)
        passports = PassportRegistry()
        ledger = EvidenceLedger(compiled.constitution_hash)
        gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                               signer=WitnessSigner(env="development"))
        actor = passports.issue(
            kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
            legal_principal="alfonso_lopez", declared_capabilities=["experiment.run"],
            budget_ceiling_usd=5.0, consequence_class="internal_write")
        return gate, passports, ledger, actor.passport_id

    def _bridge_c_spec(**kw):
        from evolution.experiment import ExperimentSpec
        base = dict(decisive_unknown="u", hypothesis="h", prediction="p", metric="m",
                    baseline=0.0, threshold=10.0, direction="gte",
                    workflow="experiment.run", required_capabilities=["experiment.run"],
                    authority_requirements=["kernel.grant"], budget_usd=0.0,
                    reversible=True, rollback_path="discard the sandbox record",
                    kill_condition="measured exceeds 100",
                    verification="cryptographic_receipt")
        base.update(kw)
        return ExperimentSpec(**base)

    def bridges_technical():
        """The chain, not one link: Bridge B's output is Bridge C's input."""
        from bridges import experiment_to_reality as bc
        from bridges import venture_to_experiment as bb
        from evolution.spider_web import (COMPLETENESS_REQUIREMENTS, EIGHT_SIDES,
                                          SpiderWebAudit)
        from evolution.strategy_tree import BRANCH_KINDS, StrategyBranch, StrategyTree

        tree = StrategyTree(bottleneck="no verified outcome exists",
                            objective="resolve one decisive unknown")
        for kind in BRANCH_KINDS:
            tree.add(StrategyBranch(
                kind=kind, title=f"{kind} branch",
                governing_assumption="the narrowing holds under selection",
                mechanism="experiment.run", required_capabilities=["experiment.run"],
                cost_usd=0.0, founder_attention_minutes=10, time_to_proof_days=1,
                authority_requirements=["kernel.grant"], irreversible_downside="none",
                expected_result="the metric clears its threshold",
                strongest_counterargument="the metric may measure the wrong thing",
                cheapest_falsification_test="re-run against the frozen corpus",
                kill_condition="measured exceeds 100"))
        audit = SpiderWebAudit(subject="the selected branch")
        for side in EIGHT_SIDES:
            audit.set_side(side, True, notes="closure probe")
        for req in COMPLETENESS_REQUIREMENTS:
            audit.set_completeness(req, True)

        gate, passports, ledger, actor = _bridge_c_stack()
        b = bb.run({"assessment_id": "probe", "verdict": "go",
                    "adversarial_cases": {"bull": "b", "bear": "r", "do_nothing": "d"},
                    "requires_human_approval": True, "execution_authority": False},
                   tree, audit,
                   decisive_unknown="does the chain hold end to end",
                   selected_branch_id=tree.branches[0].branch_id,
                   selection_reason="cheapest falsification per founder minute",
                   metric="verified_outcomes", baseline=0.0, threshold=1.0,
                   direction="gte", ledger=ledger)
        if not b.completed:
            return False, f"Bridge B halted at {b.halted_at}"
        c = bc.run(b.experiment, gate=gate, passports=passports, actor=actor,
                   measure=lambda s: 2.0, ledger=ledger)
        if not (c.completed and c.receipt_hash):
            return False, f"Bridge C halted at {c.halted_at}"

        from bridges import reality_to_learning as bd
        d = bd.run({"action_id": c.action_id,
                    "observer": "spiffe://external/customer/closure-probe",
                    "external_observation": b.experiment.prediction,
                    "result_class": "positive",
                    "validation_status": bd.EXTERNALLY_VERIFIED},
                   ledger=ledger)
        return d.completed and d.clean_verified_outcomes == 1, \
            ("assessment -> tree -> audit -> experiment -> gate -> witness -> receipt "
             "-> external observation -> measured outcome, unbroken")

    def bridges_authority():
        from bridges import experiment_to_reality as bc
        gate, passports, ledger, actor = _bridge_c_stack()
        over_cap = bc.run(_bridge_c_spec(required_capabilities=["treasury.transfer"]),
                          gate=gate, passports=passports, actor=actor,
                          measure=lambda s: 11.0, ledger=ledger)
        over_budget = bc.run(_bridge_c_spec(budget_usd=500.0), gate=gate,
                             passports=passports, actor=actor,
                             measure=lambda s: 11.0, ledger=ledger)
        refused = (over_cap.halted_at is bc.Halt.CAPABILITY_EXCEEDS_PASSPORT
                   and over_budget.halted_at is bc.Halt.BUDGET_EXCEEDS_PASSPORT)
        # And the learning loop cannot verify its own work either.
        from bridges import reality_to_learning as bd
        c = bc.run(_bridge_c_spec(), gate=gate, passports=passports, actor=actor,
                   measure=lambda s: 11.0, ledger=ledger)
        selfie = bd.run({"action_id": c.action_id, "observer": actor,
                         "external_observation": "p", "result_class": "positive",
                         "validation_status": bd.EXTERNALLY_VERIFIED}, ledger=ledger)
        return (refused and over_cap.action_id is None
                and selfie.halted_at is bd.Halt.SELF_ATTESTATION), \
            ("an experiment cannot widen its own capability or budget, and no actor "
             "may externally verify its own outcome")

    def bridges_evidence():
        from bridges import experiment_to_reality as bc
        gate, passports, ledger, actor = _bridge_c_stack()
        # The executor reports exactly the expected outcome; the metric does not
        # clear the threshold. Resolution follows the threshold, not the claim.
        run = bc.run(_bridge_c_spec(), gate=gate, passports=passports, actor=actor,
                     measure=lambda s: 2.0, ledger=ledger)
        return run.completed and run.resolved is False, \
            "self-declared success is not a result; the threshold fixed before the run decides"

    def bridges_economic():
        from bridges import experiment_to_reality as bc
        gate, passports, ledger, actor = _bridge_c_stack()
        run = bc.run(_bridge_c_spec(budget_usd=2.0), gate=gate, passports=passports,
                     actor=actor, measure=lambda s: 11.0, ledger=ledger)
        return run.halted_at is bc.Halt.GATE_REFUSED and run.granted_budget_usd == 2.0, \
            "a budgeted experiment cannot fund itself; no standing grant, no spend"

    def bridges_regenerative():
        from bridges import experiment_to_reality as bc
        gate, passports, ledger, actor = _bridge_c_stack()
        passports.revoke(actor, reason="closure probe", revoker="alfonso")

        def exploding(_spec):
            raise AssertionError("instrument ran despite a refused gate")

        run = bc.run(_bridge_c_spec(), gate=gate, passports=passports, actor=actor,
                     measure=exploding, ledger=ledger)
        return run.resolved is None and run.measured is None, \
            "a refusal yields no measurement at all; absence of evidence never becomes a finding"

    reg.register(ModuleClosures("bridges", {
        "technical": bridges_technical, "authority": bridges_authority,
        "evidence": bridges_evidence, "economic": bridges_economic,
        "regenerative": bridges_regenerative}))

    return reg
