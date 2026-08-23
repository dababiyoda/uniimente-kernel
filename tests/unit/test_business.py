"""Adversarial tests for governed business compilation and closure."""
import os

import pytest

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from compiler.ucl_compiler import compile_constitution
from identity.machine_passport import PassportRegistry
from loom.ratify import Ratifier
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

from business.commercial_loop import CommercialLoop, CommercialLoopError
from business.genome import BusinessGenome, BusinessGenomeCompiler, GenomeCompileError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#: Containment declared (CONTRADICTION-0003 Option B). True of this harness:
#: the executors are in-process test doubles, nothing reaches a real buyer or
#: payment rail, and every effect ends with the test.
SANDBOX_CONTAINMENT = {
    "contained": True, "reversible": True, "observable": True,
    "killable": True, "proportionate": True,
}

EV = ["sha256:" + "e" * 64]
PAY_OK = lambda p: {"observed_outcome": "payment settled", "result_class": "positive"}
SHIP_OK = lambda p: {"observed_outcome": "offer delivered", "result_class": "positive"}


def make_genome(**overrides):
    values = dict(
        name="governed-audit",
        problem="buyers cannot prove what an agent was allowed to do",
        buyer="operations lead",
        offer="operated audit with receipts",
        price_usd=500.0,
        distribution="territory to owned hub",
        conversion="sample to scoped engagement",
        fulfillment="human-reviewed operated service",
        retention="quarterly re-audit",
        marginal_cost_usd=120.0,
        demand_evidence_refs=EV,
        required_capabilities=[("workflow.audit", "1.0.0")],
        required_workflows=[],
        legal_restrictions=["buyer must own the audited system"],
        regenerative_effect="each audit hardens the shared gate corpus",
        kill_condition="zero paid audits across two windows",
        falsification_test="ten offers in ninety days; zero acceptance kills",
    )
    values.update(overrides)
    return BusinessGenome(**values)


@pytest.fixture
def stack():
    constitution = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(constitution.constitution_hash)
    gate = ConsequenceGate(
        compiled=constitution, passports=passports, ledger=ledger,
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
    return gate, ledger, actor, compiler


def test_complete_genome_compiles(stack):
    *_, compiler = stack
    result = compiler.compile(make_genome())
    assert result.genome_hash and result.falsification_deadline > result.compiled_at


@pytest.mark.parametrize("changes,match", [
    ({"kill_condition": ""}, "kill_condition"),
    ({"demand_evidence_refs": []}, "demand"),
    ({"price_usd": 100.0, "marginal_cost_usd": 120.0}, "donation with paperwork"),
    ({"legal_operator": "UNIIMENTE"}, "never a legal operator"),
])
def test_invalid_genomes_fail_closed(stack, changes, match):
    *_, compiler = stack
    with pytest.raises(GenomeCompileError, match=match):
        compiler.compile(make_genome(**changes))


def test_absent_capability_fails_closed(stack):
    *_, compiler = stack
    with pytest.raises(GenomeCompileError, match="does not hold that competence"):
        compiler.compile(make_genome(required_capabilities=[("ghost", "9.9.9")]))


def open_to_offer(stack):
    gate, ledger, actor, compiler = stack
    loop = CommercialLoop(compiler.compile(make_genome()), gate=gate, ledger=ledger)
    case = loop.open_case("acme")
    loop.present_offer(case.case_id)
    return loop, case, actor


def test_no_delivery_before_recorded_payment(stack):
    loop, case, actor = open_to_offer(stack)
    with pytest.raises(CommercialLoopError, match="no delivery before payment"):
        loop.deliver(case.case_id, actor=actor.passport_id, executor=SHIP_OK,
                     evidence_confidence=0.9, evidence_refs=EV,
                 containment=SANDBOX_CONTAINMENT)


def test_weak_evidence_payment_does_not_happen(stack):
    loop, case, actor = open_to_offer(stack)
    with pytest.raises(CommercialLoopError, match="did not happen"):
        loop.take_payment(case.case_id, actor=actor.passport_id, executor=PAY_OK,
                          evidence_confidence=0.5, evidence_refs=EV,
                          containment=SANDBOX_CONTAINMENT)
    assert case.stage == "offer" and case.payment_receipt_hash is None


def test_full_external_closure(stack):
    loop, case, actor = open_to_offer(stack)
    loop.take_payment(case.case_id, actor=actor.passport_id, executor=PAY_OK,
                      evidence_confidence=0.9, evidence_refs=EV,
                 containment=SANDBOX_CONTAINMENT)
    loop.deliver(case.case_id, actor=actor.passport_id, executor=SHIP_OK,
                 evidence_confidence=0.9, evidence_refs=EV,
                 containment=SANDBOX_CONTAINMENT)
    loop.verify_outcome(case.case_id, verified_by="external_receipt",
                        detail="buyer accepted the report")
    loop.resolve(case.case_id, retained=True, reason="quarterly re-audit")
    assert loop.evaluate().overall == "CLOSED"


def test_self_report_does_not_verify_customer_value(stack):
    loop, case, actor = open_to_offer(stack)
    loop.take_payment(case.case_id, actor=actor.passport_id, executor=PAY_OK,
                      evidence_confidence=0.9, evidence_refs=EV,
                 containment=SANDBOX_CONTAINMENT)
    loop.deliver(case.case_id, actor=actor.passport_id, executor=SHIP_OK,
                 evidence_confidence=0.9, evidence_refs=EV,
                 containment=SANDBOX_CONTAINMENT)
    with pytest.raises(CommercialLoopError, match="cannot verify customer value"):
        loop.verify_outcome(case.case_id, verified_by="self_report", detail="great")


def test_kill_condition_blocks_new_work(stack):
    loop, _, _ = open_to_offer(stack)
    loop.trigger_kill(evidence="two windows, zero paid audits")
    with pytest.raises(CommercialLoopError, match="dead business"):
        loop.open_case("late buyer")
