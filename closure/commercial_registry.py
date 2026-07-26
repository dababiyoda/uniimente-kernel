"""Five-closure extension for Media Foundry, Business Foundry, and Treasury.

Commercial organs remain outside the constitutional registry implementation.
They register into it through this explicit extension, preserving one core
Kernel while allowing bounded organs to be added, removed, or quarantined.
"""
from __future__ import annotations

import os

from closure.framework import ClosureRegistry, ModuleClosures

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVREF = ["sha256:" + "e" * 64]
LIVE = lambda p: {"observed_outcome": "artifact live on declared account", "result_class": "positive"}
PAY = lambda p: {"observed_outcome": "payment settled", "result_class": "positive"}
SHIP = lambda p: {"observed_outcome": "offer delivered", "result_class": "positive"}


def _compile():
    from compiler.ucl_compiler import compile_constitution
    return compile_constitution(KERNEL_ROOT)


def _foundry_stack():
    from foundry.company import CompanyFoundry, MediaCompanyCharter, REQUIRED_EDITORIAL_RULES
    from foundry.territory import ContentNode, TerritoryGraph
    from identity.machine_passport import PassportRegistry
    from policy.consequence_gate import ConsequenceGate
    from provenance.commit_witness import WitnessSigner
    from provenance.ledger import EvidenceLedger

    compiled = _compile()
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez", declared_capabilities=["media.publish"],
        budget_ceiling_usd=5.0, consequence_class="external_contact")
    territory = TerritoryGraph("closure-territory", ledger=ledger)
    territory.add(ContentNode(
        node_id="entry", question="q1", artifact="essay", capability_taught="c1",
        evidence_level=0.9, evidence_refs=["sha256:" + "a" * 64],
        next_doors=["mid"]), entry=True)
    territory.add(ContentNode(
        node_id="mid", question="q2", artifact="tool", capability_taught="c2",
        evidence_level=0.85, evidence_refs=["sha256:" + "b" * 64],
        next_doors=["exit"]))
    territory.add(ContentNode(
        node_id="exit", question="q3", artifact="service", capability_taught="c3",
        evidence_level=0.8, evidence_refs=["sha256:" + "c" * 64],
        owned_exit=True, owned_ground="hub"))
    charter = MediaCompanyCharter(
        name="closure-media", persona="Closure", synthetic_disclosure=True,
        visual_canon={"palette": "institutional"},
        editorial_rules=list(REQUIRED_EDITORIAL_RULES), narrative_world="proof",
        owned_hub="hub", subscriber_list="subs", products=["audit"], community="commons")
    foundry = CompanyFoundry(ledger)
    charter_hash = foundry.submit_charter(charter, territory)
    return foundry, charter_hash, gate, ledger, actor


def _business_stack():
    from business.genome import BusinessGenome, BusinessGenomeCompiler
    from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
    from identity.machine_passport import PassportRegistry
    from loom.ratify import Ratifier
    from policy.consequence_gate import ConsequenceGate
    from provenance.commit_witness import WitnessSigner
    from provenance.ledger import EvidenceLedger

    compiled = _compile()
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez",
        declared_capabilities=["business.charge", "business.deliver"],
        budget_ceiling_usd=1000.0, consequence_class="financial")
    registry = GenomeRegistry(ledger)
    registry.register(CapabilityGenome(
        name="workflow.audit", version="1.0.0", description="audit report",
        interface={"inputs": {"workflow_id": "str"}, "outputs": {"report": "dict"}},
        contracts=["event", "outcome"],
        authority=AuthorityEnvelope(max_consequence_class="internal_write",
                                    budget_ceiling_usd=10.0),
        acceptance_tests=["report lists every gate decision"],
        failure_modes=["ledger unavailable"], recovery_path="retry from checkpoint"))
    compiler = BusinessGenomeCompiler(
        genome_registry=registry, ratifier=Ratifier(ledger), ledger=ledger)

    def genome(**overrides):
        values = dict(
            name="closure-audit-business", problem="agents without auditability",
            buyer="operations lead", offer="operated audit with receipts",
            price_usd=500.0, distribution="territory exit", conversion="sample",
            fulfillment="operated service", retention="quarterly re-audit",
            marginal_cost_usd=120.0, demand_evidence_refs=EVREF,
            required_capabilities=[("workflow.audit", "1.0.0")],
            required_workflows=[], legal_restrictions=["no unowned systems"],
            regenerative_effect="hardens the gate corpus",
            kill_condition="zero paid audits over two windows",
            falsification_test="ten offers in ninety days; zero acceptances kills")
        values.update(overrides)
        return BusinessGenome(**values)

    return compiler, genome, gate, ledger, actor


def _treasury():
    from capital.treasury import RegenerativeTreasury
    from provenance.ledger import EvidenceLedger
    compiled = _compile()
    ledger = EvidenceLedger(compiled.constitution_hash)
    return RegenerativeTreasury(ledger), ledger


def register_commercial_closures(registry: ClosureRegistry) -> ClosureRegistry:
    """Extend a canonical registry in-place and return it."""

    def foundry_technical():
        foundry, h, gate, _, actor = _foundry_stack()
        foundry.ratifier.decide(h, ratified=True, reason="closure check")
        record = foundry.publish(h, "entry", gate=gate, actor=actor.passport_id,
                                 executor=LIVE, platform="platform:declared")
        return record.state == "recorded" and bool(record.receipt_hash), \
            "ratified company publishes through the full Gate pipeline"

    def foundry_authority():
        from foundry.company import FoundryError
        foundry, h, gate, _, actor = _foundry_stack()
        try:
            foundry.publish(h, "entry", gate=gate, actor=actor.passport_id,
                            executor=LIVE, platform="platform:declared")
            return False, "unratified charter published"
        except FoundryError:
            pass
        foundry.ratifier.decide(h, ratified=True, reason="reviewed")
        foundry.company(h).charter.persona = "edited-after-ratification"
        try:
            foundry.publish(h, "entry", gate=gate, actor=actor.passport_id,
                            executor=LIVE, platform="platform:declared")
            return False, "edited charter published"
        except FoundryError:
            return True, "unratified and post-ratification-edited charters cannot speak"

    def foundry_evidence():
        foundry, h, _, ledger, _ = _foundry_stack()
        territory = foundry.company(h).territory
        territory.correct("mid", correction="superseded", new_evidence_level=0.9)
        territory.retire("mid", reason="no longer defensible")
        events = [r.payload.get("type") for r in ledger.by_type("event")]
        ok = "foundry.node_corrected" in events and "foundry.node_retired" in events
        return ok and not territory.publishable("mid")[0], \
            "corrections and retirement are preserved and prevent publication"

    def foundry_economic():
        from foundry.distribution import DistributionLoop
        loop = DistributionLoop("closure-media")
        window = loop.open_window("w1")
        window.record_impressions(1000)
        window.record_owned_relationship(10)
        window.record_returning_visitor(20)
        window.record_useful_action("used_tool", 8)
        result = loop.evaluate(window)
        return result.overall == "CLOSED" and window.informed_return() > 0, \
            "rented attention converts into owned relationships and capability"

    def foundry_regenerative():
        from foundry.distribution import DistributionLoop
        loop = DistributionLoop("closure-media")
        for value in (1000, 2000):
            window = loop.open_window(str(value))
            window.record_impressions(value)
        result = loop.evaluate(loop.windows[-1])
        return result.overall == "FALSELY_CLOSED" and loop.kill_condition_met(), \
            "impressions without behavior change are false closure and trigger termination"

    registry.register(ModuleClosures("foundry", {
        "technical": foundry_technical, "authority": foundry_authority,
        "evidence": foundry_evidence, "economic": foundry_economic,
        "regenerative": foundry_regenerative}))

    def business_technical():
        from business.commercial_loop import CommercialLoop
        compiler, genome, gate, ledger, actor = _business_stack()
        loop = CommercialLoop(compiler.compile(genome()), gate=gate, ledger=ledger)
        case = loop.open_case("acme")
        loop.present_offer(case.case_id)
        loop.take_payment(case.case_id, actor=actor.passport_id, executor=PAY,
                          evidence_confidence=0.9, evidence_refs=EVREF)
        loop.deliver(case.case_id, actor=actor.passport_id, executor=SHIP,
                     evidence_confidence=0.9, evidence_refs=EVREF)
        loop.verify_outcome(case.case_id, verified_by="external_receipt",
                            detail="buyer accepted")
        loop.resolve(case.case_id, retained=True, reason="subscribed")
        return loop.evaluate().overall == "CLOSED", \
            "problem-to-payment-to-accepted-outcome loop closes in order"

    def business_authority():
        from business.commercial_loop import CommercialLoop, CommercialLoopError
        compiler, genome, gate, ledger, actor = _business_stack()
        loop = CommercialLoop(compiler.compile(genome()), gate=gate, ledger=ledger)
        case = loop.open_case("acme")
        loop.present_offer(case.case_id)
        try:
            loop.take_payment(case.case_id, actor=actor.passport_id, executor=PAY,
                              evidence_confidence=0.5, evidence_refs=EVREF)
            return False, "weak-evidence payment happened"
        except CommercialLoopError:
            pass
        try:
            loop.deliver(case.case_id, actor=actor.passport_id, executor=SHIP,
                         evidence_confidence=0.9, evidence_refs=EVREF)
            return False, "delivery happened without payment"
        except CommercialLoopError:
            return True, "weak payment evidence and out-of-order delivery fail closed"

    def business_evidence():
        from business.genome import GenomeCompileError
        compiler, genome, _, ledger, _ = _business_stack()
        try:
            compiler.compile(genome(kill_condition=""))
            return False, "killless genome compiled"
        except GenomeCompileError:
            refusals = [r.payload for r in ledger.by_type("event")
                        if r.payload.get("type") == "business.genome_refused"]
            return bool(refusals), "genome refusal is preserved as negative evidence"

    def business_economic():
        from business.genome import GenomeCompileError
        compiler, genome, _, _, _ = _business_stack()
        try:
            compiler.compile(genome(price_usd=100.0, marginal_cost_usd=120.0))
            return False, "negative-margin genome compiled"
        except GenomeCompileError as exc:
            return "donation with paperwork" in str(exc), \
                "price must cover marginal cost before compilation"

    def business_regenerative():
        from business.commercial_loop import CommercialLoop, CommercialLoopError
        compiler, genome, gate, ledger, _ = _business_stack()
        loop = CommercialLoop(compiler.compile(genome()), gate=gate, ledger=ledger)
        loop.trigger_kill(evidence="two windows, zero paid audits")
        try:
            loop.open_case("late-buyer")
            return False, "terminated business accepted new work"
        except CommercialLoopError:
            kills = [r.payload for r in ledger.by_type("event")
                     if r.payload.get("type") == "business.terminated"]
            return bool(kills), "precommitted termination executes and remains evidence"

    registry.register(ModuleClosures("business", {
        "technical": business_technical, "authority": business_authority,
        "evidence": business_evidence, "economic": business_economic,
        "regenerative": business_regenerative}))

    def treasury_technical():
        treasury, _ = _treasury()
        tiers = treasury.waterfall
        allocation = treasury.allocate(600.0, {
            tiers[0]: 300.0, tiers[1]: 200.0, tiers[10]: 100.0})
        return sum(allocation.values()) == 600.0 and treasury.trial_balance() == 0.0, \
            "policy waterfall allocates surplus with a zero trial balance"

    def treasury_authority():
        treasury, ledger = _treasury()
        tiers = treasury.waterfall
        allocation = treasury.allocate(350.0, {
            tiers[0]: 300.0, tiers[1]: 200.0, tiers[10]: 100.0})
        stops = [r.payload for r in ledger.by_type("event")
                 if r.payload.get("type") == "treasury.waterfall_stopped"]
        return tiers[10] not in allocation and bool(stops), \
            "an underfunded higher tier blocks lower allocations"

    def treasury_evidence():
        treasury, ledger = _treasury()
        treasury.record_debt(kind="attention_drain", severity=0.5,
                             description="manual triage")
        events = [r.payload for r in ledger.by_type("event")
                  if r.payload.get("type") == "treasury.debt_recorded"]
        return bool(events) and set(events[0]["blocks"]) == {
            "autonomy_promotion", "budget_expansion", "replication"}, \
            "debt evidence names every blocked institutional move"

    def treasury_economic():
        from capital.treasury import TreasuryError
        treasury, _ = _treasury()
        treasury.post(debit="operating_cash", credit="revenue",
                      amount_usd=500.0, memo="sale")
        try:
            treasury.post(debit="a", credit="b", amount_usd=-1.0, memo="hide")
            return False, "negative posting accepted"
        except TreasuryError:
            return treasury.trial_balance() == 0.0, \
                "double entry holds and sign games fail closed"

    def treasury_regenerative():
        treasury, _ = _treasury()
        debt = treasury.record_debt(kind="externalized_risk", severity=0.4,
                                    description="risk shifted")
        before = all(treasury.blocks(action)[0] for action in
                     ("autonomy_promotion", "budget_expansion", "replication"))
        treasury.repay_debt(debt.debt_id,
                            evidence="risk reconciled and regression test added")
        after = any(treasury.blocks(action)[0] for action in
                    ("autonomy_promotion", "budget_expansion", "replication"))
        return before and not after, \
            "open debt blocks expansion; evidence-based repair unblocks it"

    registry.register(ModuleClosures("treasury", {
        "technical": treasury_technical, "authority": treasury_authority,
        "evidence": treasury_evidence, "economic": treasury_economic,
        "regenerative": treasury_regenerative}))

    return registry
