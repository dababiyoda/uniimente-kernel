"""Tests for media charters, territories, publishing, and distribution closure."""
import os
from datetime import datetime, timedelta, timezone

import pytest

from compiler.ucl_compiler import compile_constitution
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

from foundry.company import CompanyFoundry, FoundryError, MediaCompanyCharter, REQUIRED_EDITORIAL_RULES
from foundry.distribution import DistributionLoop
from foundry.territory import ContentNode, TerritoryGraph

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EV = ["sha256:" + "a" * 64]
LIVE = lambda p: {"observed_outcome": "artifact live on declared account", "result_class": "positive"}


def make_territory(*, ledger=None, weak=False, stale=False):
    graph = TerritoryGraph("proof-territory", ledger=ledger)
    expiry = datetime.now(timezone.utc) - timedelta(seconds=1) if stale else None
    graph.add(ContentNode(
        node_id="entry", question="What failed?", artifact="essay",
        capability_taught="identify the failure", evidence_level=0.6 if weak else 0.9,
        evidence_refs=EV, expires_at=expiry, next_doors=["method"]), entry=True)
    graph.add(ContentNode(
        node_id="method", question="How is it repaired?", artifact="tool",
        capability_taught="run the method", evidence_level=0.85,
        evidence_refs=EV, next_doors=["exit"]))
    graph.add(ContentNode(
        node_id="exit", question="What can be done now?", artifact="service",
        capability_taught="apply the method", evidence_level=0.8,
        evidence_refs=EV, owned_exit=True, owned_ground="owned-hub"))
    return graph


#: Containment declared (CONTRADICTION-0003 Option B). True of this harness:
#: the executor is an in-process double and "platform:declared" is not a real
#: platform.
SANDBOX_CONTAINMENT = {
    "contained": True, "reversible": True, "observable": True,
    "killable": True, "proportionate": True,
}


def make_charter(**overrides):
    values = dict(
        name="evidence-company", persona="Synthetic Analyst",
        synthetic_disclosure=True, visual_canon={"palette": "institutional"},
        editorial_rules=list(REQUIRED_EDITORIAL_RULES),
        narrative_world="proof before claims", owned_hub="owned-hub",
        subscriber_list="consented-list", products=["operated audit"],
        community="commons")
    values.update(overrides)
    return MediaCompanyCharter(**values)


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
        legal_principal="alfonso_lopez", declared_capabilities=["media.publish"],
        budget_ceiling_usd=5.0, consequence_class="external_contact")
    return ledger, gate, actor


def test_valid_territory_is_rooted_dag_with_one_exit():
    assert make_territory().validate() == []


def test_missing_disclosure_or_editorial_rule_refused(stack):
    ledger, _, _ = stack
    foundry = CompanyFoundry(ledger)
    with pytest.raises(ValueError, match="synthetic disclosure"):
        foundry.submit_charter(make_charter(synthetic_disclosure=False), make_territory())
    with pytest.raises(ValueError, match="editorial constitution"):
        foundry.submit_charter(make_charter(editorial_rules=[]), make_territory())


def test_unratified_company_cannot_publish(stack):
    ledger, gate, actor = stack
    foundry = CompanyFoundry(ledger)
    h = foundry.submit_charter(make_charter(), make_territory(ledger=ledger))
    with pytest.raises(FoundryError, match="unratified company"):
        foundry.publish(h, "entry", gate=gate, actor=actor.passport_id,
                        executor=LIVE, platform="platform:declared",
                        containment=SANDBOX_CONTAINMENT)


def test_ratified_publish_crosses_gate(stack):
    ledger, gate, actor = stack
    foundry = CompanyFoundry(ledger)
    h = foundry.submit_charter(make_charter(), make_territory(ledger=ledger))
    foundry.ratifier.decide(h, ratified=True, reason="human review")
    record = foundry.publish(h, "entry", gate=gate, actor=actor.passport_id,
                             executor=LIVE, platform="platform:declared",
                        containment=SANDBOX_CONTAINMENT)
    assert record.state == "recorded" and record.receipt_hash


def test_edited_charter_loses_ratification(stack):
    ledger, gate, actor = stack
    foundry = CompanyFoundry(ledger)
    h = foundry.submit_charter(make_charter(), make_territory(ledger=ledger))
    foundry.ratifier.decide(h, ratified=True, reason="human review")
    foundry.company(h).charter.persona = "changed after ratification"
    with pytest.raises(FoundryError, match="edited charter"):
        foundry.publish(h, "entry", gate=gate, actor=actor.passport_id,
                        executor=LIVE, platform="platform:declared",
                        containment=SANDBOX_CONTAINMENT)


@pytest.mark.parametrize("graph,match", [
    (make_territory(weak=True), "below publish floor"),
    (make_territory(stale=True), "evidence expired"),
])
def test_weak_or_stale_nodes_cannot_publish(stack, graph, match):
    ledger, gate, actor = stack
    graph.ledger = ledger
    foundry = CompanyFoundry(ledger)
    h = foundry.submit_charter(make_charter(), graph)
    foundry.ratifier.decide(h, ratified=True, reason="human review")
    with pytest.raises(FoundryError, match=match):
        foundry.publish(h, "entry", gate=gate, actor=actor.passport_id,
                        executor=LIVE, platform="platform:declared",
                        containment=SANDBOX_CONTAINMENT)


def test_correction_and_retirement_are_preserved(stack):
    ledger, _, _ = stack
    graph = make_territory(ledger=ledger)
    graph.correct("method", correction="stronger source", new_evidence_level=0.95)
    graph.retire("method", reason="superseded")
    events = [r.payload.get("type") for r in ledger.by_type("event")]
    assert "foundry.node_corrected" in events
    assert "foundry.node_retired" in events
    assert not graph.publishable("method")[0]


def test_distribution_requires_owned_relationship_and_useful_action():
    loop = DistributionLoop("evidence-company")
    false_window = loop.open_window("false")
    false_window.record_impressions(1000)
    assert loop.evaluate(false_window).overall == "FALSELY_CLOSED"

    real_window = loop.open_window("real")
    real_window.record_impressions(1000)
    real_window.record_owned_relationship(10)
    real_window.record_returning_visitor(20)
    real_window.record_useful_action("used_tool", 8)
    assert loop.evaluate(real_window).overall == "CLOSED"
    assert real_window.informed_return() == 0.4


def test_impression_growth_without_behavior_change_trips_kill():
    loop = DistributionLoop("evidence-company")
    for i, impressions in enumerate((1000, 2000)):
        window = loop.open_window(str(i))
        window.record_impressions(impressions)
    assert loop.kill_condition_met()
