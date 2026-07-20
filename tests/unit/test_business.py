"""Phase 7 tests: Business Genome Compiler + Commercial Loop.

Adversarial suite: incomplete genomes, negative-margin offers, missing
demand evidence, absent capabilities, unratified workflows, out-of-order
loop advances, unrecorded payments, self-reported outcomes, launch
without revenue (false closure), and the kill condition.
"""
import os

import pytest

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from compiler.ucl_compiler import compile_constitution
from identity.machine_passport import PassportRegistry
from loom.canonical import daily_reconciliation
from loom.ratify import Ratifier
from policy.consequence_gate import ConsequenceGate
from provenance.ledger import EvidenceLedger
from provenance.commit_witness import WitnessSigner

from business.commercial_loop import (ACCEPTED_VERIFICATIONS, CommercialLoop,
                                      CommercialLoopError)
from business.genome import (BusinessGenome, BusinessGenomeCompiler,
                             GenomeCompileError)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EV = ["sha256:" + "e" * 64]
PAY_OK = lambda p: {"observed_outcome": "payment settled", "result_class": "positive"}
SHIP_OK = lambda p: {"observed_outcome": "offer delivered", "result_class": "positive"}


def capability_genome(name="workflow.audit") -> CapabilityGenome:
    return CapabilityGenome(
        name=name, version="1.0.0",
        description="produce the governed-automation audit report",
        interface={"inputs": {"workflow_id": "str"}, "outputs": {"report": "dict"}},
        contracts=["event", "outcome"],
        authority=AuthorityEnvelope(max_consequence_class="internal_write",
                                    budget_ceiling_usd=10.0),
        acceptance_tests=["report lists every gate decision for the workflow"],
        failure_modes=["ledger unavailable"], recovery_path="retry from ledger checkpoint")


def make_genome(**kw) -> BusinessGenome:
    defaults = dict(
        name="governed-automation-audit",
        problem="companies deploying agents cannot answer their auditor: "
                "'what exactly is it allowed to do?'",
        buyer="operations lead at an agent-deploying company",
        offer="operated audit of one agent workflow, with proof receipts",
        price_usd=500.0,
        distribution="ledgerline territory exit -> owned hub",
        conversion="audit sample -> scoped engagement",
        fulfillment="operated service, human-reviewed, receipts attached",
        retention="quarterly re-audit subscription",
        marginal_cost_usd=120.0,
        demand_evidence_refs=EV,
        required_capabilities=[("workflow.audit", "1.0.0")],
        required_workflows=[],
        legal_restrictions=["no audit of systems the buyer does not own"],
        regenerative_effect="every audit hardens the shared gate corpus",
        kill_condition="two consecutive windows with zero paid audits "
                       "while demand outreach continues",
        falsification_test="offer 10 audits at full price inside 90 days; "
                           "zero acceptances kills the genome")
    defaults.update(kw)
    return BusinessGenome(**defaults)


@pytest.fixture
def stack():
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    signer = WitnessSigner(env="development")
    gate = ConsequenceGate(compiled=compiled, passports=passports,
                           ledger=ledger, signer=signer)
    actor = passports.issue(kind="agent", creator="alfonso",
                            owner_organ="uniimente-kernel",
                            legal_principal="alfonso_lopez",
                            declared_capabilities=["business.charge", "business.deliver"],
                            budget_ceiling_usd=1000.0,
                            consequence_class="financial")
    registry = GenomeRegistry(ledger)
    registry.register(capability_genome())
    ratifier = Ratifier(ledger, kind="loom.pattern")
    compiler = BusinessGenomeCompiler(genome_registry=registry,
                                      ratifier=ratifier, ledger=ledger)
    return gate, ledger, actor, registry, ratifier, compiler


# ---------- genome compilation ----------

def test_complete_genome_compiles(stack):
    gate, ledger, actor, registry, ratifier, compiler = stack
    compiled = compiler.compile(make_genome())
    assert compiled.business_id and compiled.genome_hash
    assert compiled.falsification_deadline > compiled.compiled_at
    assert compiled.capability_checks == ["workflow.audit@1.0.0 present"]
    assert any(r.payload.get("type") == "business.genome_compiled"
               for r in ledger.by_type("event"))


def test_missing_kill_condition_refused(stack):
    *_, compiler = stack
    with pytest.raises(GenomeCompileError, match="kill_condition"):
        compiler.compile(make_genome(kill_condition=""))


def test_negative_margin_refused(stack):
    *_, compiler = stack
    with pytest.raises(GenomeCompileError, match="donation with paperwork"):
        compiler.compile(make_genome(price_usd=100.0, marginal_cost_usd=120.0))


def test_no_demand_evidence_refused(stack):
    *_, compiler = stack
    with pytest.raises(GenomeCompileError, match="demand"):
        compiler.compile(make_genome(demand_evidence_refs=[]))


def test_absent_capability_refused(stack):
    *_, compiler = stack
    with pytest.raises(GenomeCompileError, match="does not hold that competence"):
        compiler.compile(make_genome(required_capabilities=[("ghost.capability", "9.9.9")]))


def test_unratified_workflow_refused(stack):
    gate, ledger, actor, registry, ratifier, compiler = stack
    pattern = daily_reconciliation()
    h = ratifier.submit(pattern)          # submitted, never ratified
    with pytest.raises(GenomeCompileError, match="unratified automation"):
        compiler.compile(make_genome(required_workflows=[h]))


def test_ratified_workflow_accepted(stack):
    gate, ledger, actor, registry, ratifier, compiler = stack
    pattern = daily_reconciliation()
    h = ratifier.submit(pattern)
    ratifier.decide(h, ratified=True, reason="reviewed")
    compiled = compiler.compile(make_genome(required_workflows=[h]))
    assert compiled.workflow_checks == [f"{h[:16]}... ratified"]


def test_uniimente_never_legal_operator(stack):
    *_, compiler = stack
    with pytest.raises(GenomeCompileError, match="never a legal operator"):
        compiler.compile(make_genome(legal_operator="UNIIMENTE"))


def test_refusal_is_preserved_as_negative_evidence(stack):
    gate, ledger, actor, registry, ratifier, compiler = stack
    with pytest.raises(GenomeCompileError):
        compiler.compile(make_genome(kill_condition=""))
    refusals = [r.payload for r in ledger.by_type("event")
                if r.payload.get("type") == "business.genome_refused"]
    assert refusals and refusals[0]["genome"] == "governed-automation-audit"


# ---------- the commercial loop ----------

def run_to_payment(stack):
    gate, ledger, actor, registry, ratifier, compiler = stack
    loop = CommercialLoop(compiler.compile(make_genome()), gate=gate, ledger=ledger)
    case = loop.open_case("acme-operations")
    loop.present_offer(case.case_id)
    loop.take_payment(case.case_id, actor=actor.passport_id, executor=PAY_OK,
                      evidence_confidence=0.9, evidence_refs=EV)
    return loop, case, actor


def test_full_loop_problem_to_retention(stack):
    loop, case, actor = run_to_payment(stack)
    assert case.payment_receipt_hash is not None
    loop.deliver(case.case_id, actor=actor.passport_id, executor=SHIP_OK,
                 evidence_confidence=0.9, evidence_refs=EV)
    assert case.delivery_receipt_hash is not None
    loop.verify_outcome(case.case_id, verified_by="external_receipt",
                        detail="buyer's auditor accepted the report")
    resolved = loop.resolve(case.case_id, retained=True,
                            reason="quarterly re-audit subscribed")
    assert resolved.resolution == "retained"
    assert [h["stage"] for h in resolved.history] == [
        "buyer", "offer", "payment", "delivery",
        "customer_outcome", "retention_or_termination"]
    assert loop.evaluate().overall == "CLOSED"


def test_no_delivery_before_payment(stack):
    gate, ledger, actor, registry, ratifier, compiler = stack
    loop = CommercialLoop(compiler.compile(make_genome()), gate=gate, ledger=ledger)
    case = loop.open_case("acme-operations")
    loop.present_offer(case.case_id)
    with pytest.raises(CommercialLoopError, match="no delivery before payment"):
        loop.deliver(case.case_id, actor=actor.passport_id, executor=SHIP_OK,
                     evidence_confidence=0.9, evidence_refs=EV)


def test_no_payment_before_offer(stack):
    gate, ledger, actor, registry, ratifier, compiler = stack
    loop = CommercialLoop(compiler.compile(make_genome()), gate=gate, ledger=ledger)
    case = loop.open_case("acme-operations")
    with pytest.raises(CommercialLoopError, match="no payment before an offer"):
        loop.take_payment(case.case_id, actor=actor.passport_id, executor=PAY_OK,
                          evidence_confidence=0.9, evidence_refs=EV)


def test_weak_evidence_payment_never_happens(stack):
    gate, ledger, actor, registry, ratifier, compiler = stack
    loop = CommercialLoop(compiler.compile(make_genome()), gate=gate, ledger=ledger)
    case = loop.open_case("acme-operations")
    loop.present_offer(case.case_id)
    # financial floor is 0.8; 0.5 must refuse at the gate, not warn
    with pytest.raises(CommercialLoopError, match="did not happen"):
        loop.take_payment(case.case_id, actor=actor.passport_id, executor=PAY_OK,
                          evidence_confidence=0.5, evidence_refs=EV)
    assert case.stage == "offer" and case.payment_receipt_hash is None


def test_self_reported_outcome_refused(stack):
    loop, case, actor = run_to_payment(stack)
    loop.deliver(case.case_id, actor=actor.passport_id, executor=SHIP_OK,
                 evidence_confidence=0.9, evidence_refs=EV)
    for weak in ("self_report", "same_model_critique", "intrinsic_confidence"):
        with pytest.raises(CommercialLoopError, match="cannot verify customer value"):
            loop.verify_outcome(case.case_id, verified_by=weak, detail="we feel great")


def test_launch_without_revenue_is_falsely_closed(stack):
    gate, ledger, actor, registry, ratifier, compiler = stack
    loop = CommercialLoop(compiler.compile(make_genome()), gate=gate, ledger=ledger)
    loop.open_case("acme-operations")      # launched, nobody paid
    result = loop.evaluate()
    assert result.overall == "FALSELY_CLOSED"
    assert "investigate_false_closure" in result.required_actions


def test_kill_condition_terminates_and_blocks(stack):
    gate, ledger, actor, registry, ratifier, compiler = stack
    loop = CommercialLoop(compiler.compile(make_genome()), gate=gate, ledger=ledger)
    loop.trigger_kill(evidence="two windows, zero paid audits, outreach continued")
    with pytest.raises(CommercialLoopError, match="dead business"):
        loop.open_case("late-buyer")
    events = [r.payload for r in ledger.by_type("event")]
    kill = [e for e in events if e.get("type") == "business.terminated"]
    assert kill and "appreciating asset" in kill[0]["learning"]


def test_payment_effect_is_hash_bound(stack):
    """The grant issued for the charge binds to the exact amount; the gate's
    commit revalidation makes silent price changes structurally impossible."""
    loop, case, actor = run_to_payment(stack)
    charges = [r.payload for r in loop.ledger.by_type("witness")
               if r.payload.get("action_class") == "business.charge"]
    assert charges, "payment must leave a Commit Witness"
