"""Mission G: synthetic customers and money are labelled synthetic and never become external verification.

Directive section 33, Mission G: "Label synthetic customers and synthetic money as synthetic." Constitution:
synthetic customers and money never become external verification. Before (19bbdcb), a CommercialLoop run with
stub executors evaluated to CLOSED and foundry/outcome_bridge.py turned its case into
ExternalOutcome(externally_verified=True) (scratch probe missiong/probe.py); CustomerCase, the #38 rail's
charges and the #37 marketplace's parties, matches and settlements carried no synthetic label.

Now a customer is observed only when the case is opened with an observation from an external system of
record, money is observed only when the Gate's payment receipt carries a live-mode processor observation from
a source that is not an emulator, fixture, test mode or stub, and the bridge refuses anything else.
"""
from __future__ import annotations

import os

import pytest

from business.commercial_loop import CommercialLoop, CommercialLoopError, CustomerCase
from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry
from compiler.ucl_compiler import compile_constitution
from foundry.advantage import AdvantageRefused
from foundry.outcome_bridge import ReconciliationPacket, external_outcome_from_case
from foundry.systems import marketplace
from identity.machine_passport import PassportRegistry
from loom.ratify import Ratifier
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EV = ["sha256:" + "e" * 64]
REF = "sha256:" + "7" * 64
STUB_PAY = lambda p: {"observed_outcome": "payment settled", "result_class": "positive"}   # noqa: E731
SHIP = lambda p: {"observed_outcome": "offer delivered", "result_class": "positive"}       # noqa: E731
PACKET = ReconciliationPacket(500.0, 100.0, 1.0, "sha256:" + "c" * 64, "sha256:" + "d" * 64, "sha256:" + "f" * 64)


@pytest.fixture
def loop():
    from business.genome import BusinessGenome, BusinessGenomeCompiler
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger, signer=WitnessSigner(env="development"))
    actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel", legal_principal="alfonso_lopez",
                            declared_capabilities=["business.charge", "business.deliver"], budget_ceiling_usd=1000.0,
                            consequence_class="financial")
    registry = GenomeRegistry(ledger)
    registry.register(CapabilityGenome(
        name="workflow.audit", version="1.0.0", description="d",
        interface={"inputs": {"workflow_id": "str"}, "outputs": {"report": "dict"}}, contracts=["event"],
        authority=AuthorityEnvelope(max_consequence_class="internal_write", budget_ceiling_usd=10.0),
        acceptance_tests=["x"], failure_modes=["y"], recovery_path="z"))
    compiler = BusinessGenomeCompiler(genome_registry=registry, ratifier=Ratifier(ledger), ledger=ledger)
    genome = BusinessGenome(
        name="n", problem="p", buyer="b", offer="o", price_usd=500.0, distribution="d", conversion="c", fulfillment="f",
        retention="r", marginal_cost_usd=120.0, demand_evidence_refs=EV, required_capabilities=[("workflow.audit", "1.0.0")],
        required_workflows=[], legal_restrictions=["l"], regenerative_effect="e", kill_condition="k", falsification_test="t")
    return CommercialLoop(compiler.compile(genome), gate=gate, ledger=ledger), actor, ledger


def _run(loop, actor, *, pay=STUB_PAY, **open_kw):
    case = loop.open_case("acme", **open_kw)
    loop.present_offer(case.case_id)
    loop.take_payment(case.case_id, actor=actor.passport_id, executor=pay, evidence_confidence=0.9, evidence_refs=EV)
    loop.deliver(case.case_id, actor=actor.passport_id, executor=SHIP, evidence_confidence=0.9, evidence_refs=EV)
    loop.verify_outcome(case.case_id, verified_by="external_receipt", detail="stub")
    loop.resolve(case.case_id, retained=True, reason="r")
    return case


def test_a_stubbed_loop_is_synthetic_and_never_external_verification(loop):
    loop, actor, ledger = loop
    case = _run(loop, actor)          # the probe's exact loop: stub executors, an unobserved buyer
    assert loop.evaluate().overall != "CLOSED", "a synthetic run is not an external close"
    with pytest.raises(AdvantageRefused, match="synthetic"):
        external_outcome_from_case(case, PACKET)
    assert (case.customer_mode, case.money_mode, case.synthetic) == ("synthetic", "synthetic", True)
    events = [r.payload for r in ledger.by_type("event") if str(r.payload.get("type", "")).startswith("business.case_")]
    assert events and all(e["synthetic"] is True and e["money_mode"] == "synthetic" for e in events)


@pytest.mark.parametrize("observation", [
    {"source": "stripe-emulator", "record_ref": REF, "livemode": False},     # the loopback emulator
    {"source": "stripe", "record_ref": REF, "livemode": False},              # Stripe's real test mode
    {"source": "fixture-books", "record_ref": REF, "livemode": True},        # a fixture claiming live mode
    {"source": "stripe", "record_ref": "row-7", "livemode": True},           # no canonical record
])
def test_test_mode_emulator_and_fixture_money_stay_synthetic(loop, observation):
    loop, actor, _ = loop
    observed_customer = {"source": "crm.example", "record_ref": REF}
    case = _run(loop, actor, pay=lambda p: {**STUB_PAY(p), "processor_observation": observation},
                customer_observation=observed_customer)
    assert case.customer_mode == "observed" and case.money_mode == "synthetic"
    assert loop.evaluate().overall != "CLOSED"
    with pytest.raises(AdvantageRefused, match="synthetic"):
        external_outcome_from_case(case, PACKET)


def test_only_live_external_observation_closes_and_verifies(loop):
    loop, actor, _ = loop
    money = {"source": "stripe", "record_ref": "sha256:" + "8" * 64, "livemode": True}
    customer = {"source": "crm.example", "record_ref": REF}
    case = _run(loop, actor, pay=lambda p: {**STUB_PAY(p), "processor_observation": money},
                customer_observation=customer)
    assert not case.synthetic and loop.evaluate().overall == "CLOSED"
    outcome = external_outcome_from_case(case, PACKET)
    assert outcome.externally_verified and {REF, money["record_ref"]} <= set(outcome.receipt_refs)
    # a caller cannot relabel a fixture as an observed customer
    with pytest.raises(CommercialLoopError, match="synthetic"):
        loop.open_case("acme", customer_observation={"source": "fixture", "record_ref": REF})


def test_a_hand_built_case_is_synthetic_by_default_and_cannot_claim_observed_without_records():
    base = dict(case_id="c", business_id="b", buyer="acme", stage="retention_or_termination",
                payment_receipt_hash="sha256:" + "a" * 64, delivery_receipt_hash="sha256:" + "b" * 64,
                outcome_verified_by="external_receipt", outcome_detail="accepted", resolution="retained")
    with pytest.raises(AdvantageRefused, match="synthetic"):
        external_outcome_from_case(CustomerCase(**base), PACKET)
    with pytest.raises(AdvantageRefused, match="without an external observation"):
        external_outcome_from_case(CustomerCase(**base, customer_mode="observed", money_mode="observed"), PACKET)


def test_marketplace_labels_parties_matches_and_settlement_synthetic(tmp_path):
    result = marketplace.exercise(tmp_path)
    assert result["settlement"]["status"] == "settled"
    assert result["settlement"]["money"] == "synthetic" and result["settlement"]["synthetic"] is True
    assert result["synthetic_labels"] == {"parties": ["synthetic"], "matches": [True], "rail_charges": ["synthetic"]}
    assert all(m["synthetic"] for m in marketplace.board(tmp_path)["matches"])
    with pytest.raises(marketplace.MarketError, match="synthetic"):
        marketplace.enroll(tmp_path / "m2", "party:x", "00" * 32,
                           identity_observation={"source": "test-fixture", "record_ref": REF})
