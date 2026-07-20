"""Phase 6 tests: AI Influencer Company Foundry + Rabbit Hole Engine.

Adversarial suite: undisclosed synthetic identity, missing editorial
rules, unratified charters, post-ratification edits, doors to nowhere,
cycles, multiple exits, stale/weak-evidence nodes, engagement-farming
false closure, and the organ kill condition.
"""
import os
from datetime import datetime, timezone, timedelta

import pytest

from compiler.ucl_compiler import compile_constitution
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.ledger import EvidenceLedger
from provenance.commit_witness import WitnessSigner

from foundry.company import (CompanyFoundry, FoundryError, MediaCompanyCharter,
                             REQUIRED_EDITORIAL_RULES)
from foundry.distribution import DistributionLoop
from foundry.territory import ContentNode, TerritoryGraph, TerritoryError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GOOD = lambda p: {"observed_outcome": "artifact live on declared account",
                  "result_class": "positive"}


def make_territory(ledger=None) -> TerritoryGraph:
    t = TerritoryGraph("financial-sovereignty", ledger=ledger)
    t.add(ContentNode(
        node_id="entry", question="Where does your paycheck actually go?",
        artifact="essay", capability_taught="read your own cash flow",
        evidence_level=0.9, evidence_refs=["sha256:" + "a" * 64],
        next_doors=["cashflow"]), entry=True)
    t.add(ContentNode(
        node_id="cashflow", question="What survives a bad month?",
        artifact="tool", capability_taught="build a budget that survives bad months",
        evidence_level=0.85, evidence_refs=["sha256:" + "b" * 64],
        next_doors=["exit"]))
    t.add(ContentNode(
        node_id="exit", question="What do you build with the surplus?",
        artifact="course", capability_taught="govern a small venture",
        evidence_level=0.8, evidence_refs=["sha256:" + "c" * 64],
        owned_exit=True, owned_ground="hub.uniimente.internal/newsletter"))
    return t


def make_charter(**kw) -> MediaCompanyCharter:
    defaults = dict(
        name="ledgerline-media", persona="Ledgerline",
        synthetic_disclosure=True,
        visual_canon={"palette": "ink-and-brass", "wordmark": "LEDGERLINE"},
        editorial_rules=list(REQUIRED_EDITORIAL_RULES),
        narrative_world="a city where every promise is written down",
        owned_hub="hub.uniimente.internal", subscriber_list="ledgerline-subscribers",
        products=["cashflow-toolkit"], community="ledgerline-commons")
    defaults.update(kw)
    return MediaCompanyCharter(**defaults)


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
                            declared_capabilities=["media.publish"],
                            budget_ceiling_usd=5.0,
                            consequence_class="external_contact")
    return gate, ledger, actor


# ---------- territory structure ----------

def test_valid_territory_validates():
    assert make_territory().validate() == []


def test_door_to_nowhere_refused():
    t = make_territory()
    t.node("cashflow").next_doors.append("ghost")
    assert any("door to nowhere" in p for p in t.validate())


def test_unreachable_node_refused():
    t = make_territory()
    t.add(ContentNode(node_id="island", question="q", artifact="a",
                      capability_taught="c", evidence_level=0.9))
    assert any("unreachable" in p for p in t.validate())


def test_cycle_refused():
    t = make_territory()
    t.node("exit").next_doors.append("entry")
    assert any("cycle" in p for p in t.validate())


def test_exactly_one_owned_exit():
    t = make_territory()
    t.node("cashflow").owned_exit = True
    t.node("cashflow").owned_ground = "hub"
    assert any("exactly ONE owned exit" in p for p in t.validate())
    t2 = make_territory()
    t2.node("exit").owned_exit = False
    assert any("exactly ONE owned exit" in p for p in t2.validate())


def test_owned_exit_requires_owned_ground():
    with pytest.raises(TerritoryError, match="owned ground"):
        TerritoryGraph("t").add(ContentNode(
            node_id="x", question="q", artifact="a", capability_taught="c",
            evidence_level=0.9, owned_exit=True))


def test_production_node_floor():
    t = make_territory()
    assert any("< minimum 50" in p for p in t.validate(production=True))


# ---------- the correction layer ----------

def test_stale_node_not_publishable():
    t = make_territory()
    t.node("cashflow").expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    ok, why = t.publishable("cashflow")
    assert not ok and "expired" in why
    assert [n.node_id for n in t.stale_nodes()] == ["cashflow"]


def test_weak_evidence_not_publishable():
    t = make_territory()
    t.node("cashflow").evidence_level = 0.4
    ok, why = t.publishable("cashflow")
    assert not ok and "below publish floor" in why


def test_correction_is_public_and_append_only():
    compiled = compile_constitution(ROOT)
    ledger = EvidenceLedger(compiled.constitution_hash)
    t = make_territory(ledger)
    t.correct("cashflow", correction="rate data superseded",
              new_evidence_level=0.9, new_evidence_refs=["sha256:" + "d" * 64])
    node = t.node("cashflow")
    assert node.evidence_level == 0.9
    assert node.correction_history[0]["previous_evidence_level"] == 0.85
    events = [r.payload for r in ledger.by_type("event")]
    assert any(e["type"] == "foundry.node_corrected" for e in events)


def test_retirement_is_public_and_blocks_publish():
    compiled = compile_constitution(ROOT)
    ledger = EvidenceLedger(compiled.constitution_hash)
    t = make_territory(ledger)
    t.retire("cashflow", reason="claim no longer defensible")
    ok, why = t.publishable("cashflow")
    assert not ok and "retired" in why
    assert any(r.payload["type"] == "foundry.node_retired"
               for r in ledger.by_type("event"))


# ---------- charter law ----------

def test_undisclosed_synthetic_identity_refused():
    problems = make_charter(synthetic_disclosure=False).validate()
    assert any("machines everywhere, always" in p for p in problems)


def test_missing_editorial_rules_refused():
    rules = [r for r in REQUIRED_EDITORIAL_RULES if r != "no_outrage_optimization"]
    problems = make_charter(editorial_rules=rules).validate()
    assert any("no_outrage_optimization" in p for p in problems)


def test_company_without_product_refused():
    problems = make_charter(products=[]).validate()
    assert any("an account, not a company" in p for p in problems)


def test_uniimente_never_legal_operator():
    problems = make_charter(legal_operator="UNIIMENTE").validate()
    assert any("never a legal operator" in p for p in problems)


def test_revenue_must_route_to_treasury():
    problems = make_charter(revenue_routes_to_treasury=False).validate()
    assert any("treasury" in p for p in problems)


# ---------- foundry: ratification + gate-mediated publish ----------

def test_unratified_company_does_not_speak(stack):
    gate, ledger, actor = stack
    foundry = CompanyFoundry(ledger)
    h = foundry.submit_charter(make_charter(), make_territory(ledger))
    with pytest.raises(FoundryError, match="not ratified"):
        foundry.publish(h, "entry", gate=gate, actor=actor.passport_id,
                        executor=GOOD, platform="platform:declared-account")


def test_edited_charter_is_unratified(stack):
    gate, ledger, actor = stack
    foundry = CompanyFoundry(ledger)
    h = foundry.submit_charter(make_charter(), make_territory(ledger))
    foundry.ratifier.decide(h, ratified=True, reason="reviewed")
    foundry.company(h).charter.persona = "Someone Else"   # post-ratification edit
    with pytest.raises(FoundryError, match="edited charter is an unratified charter"):
        foundry.publish(h, "entry", gate=gate, actor=actor.passport_id,
                        executor=GOOD, platform="platform:declared-account")


def test_ratified_publish_closes_full_gate_pipeline(stack):
    gate, ledger, actor = stack
    foundry = CompanyFoundry(ledger)
    h = foundry.submit_charter(make_charter(), make_territory(ledger))
    foundry.ratifier.decide(h, ratified=True, reason="reviewed against canon")
    rec = foundry.publish(h, "entry", gate=gate, actor=actor.passport_id,
                          executor=GOOD, platform="platform:declared-account")
    assert rec.state == "recorded"
    assert rec.witness_id and rec.receipt_hash
    assert rec.outcome["external_observation"] == "artifact live on declared account"
    # the payload discloses the synthetic identity
    assert any(r.payload.get("proof") for r in ledger.by_type("receipt"))


def test_stale_node_refused_before_gate(stack):
    gate, ledger, actor = stack
    foundry = CompanyFoundry(ledger)
    territory = make_territory(ledger)
    territory.node("entry").expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    h = foundry.submit_charter(make_charter(), territory)
    foundry.ratifier.decide(h, ratified=True, reason="reviewed")
    with pytest.raises(FoundryError, match="expired"):
        foundry.publish(h, "entry", gate=gate, actor=actor.passport_id,
                        executor=GOOD, platform="platform:declared-account")


def test_invalid_territory_refused_at_charter():
    compiled = compile_constitution(ROOT)
    ledger = EvidenceLedger(compiled.constitution_hash)
    t = TerritoryGraph("broken")   # no entry node
    with pytest.raises(FoundryError, match="territory invalid"):
        CompanyFoundry(ledger).submit_charter(make_charter(), t)


# ---------- distribution loop: informed return, false closure, kill ----------

def test_distribution_closes_on_owned_relationships_and_behavior():
    loop = DistributionLoop("ledgerline-media")
    w = loop.open_window("2026-W29")
    w.record_impressions(10_000)
    w.record_qualified_visit(300)
    w.record_owned_relationship(40)
    w.record_returning_visitor(100)
    w.record_useful_action("used_tool", 25)
    w.record_useful_action("cited_source", 5)
    result = loop.evaluate(w)
    assert result.overall == "CLOSED"
    assert w.informed_return() == pytest.approx(0.3)


def test_impressions_without_relationships_is_falsely_closed():
    loop = DistributionLoop("ledgerline-media")
    w = loop.open_window("2026-W30")
    w.record_impressions(1_000_000)     # the vanity spike
    result = loop.evaluate(w)
    assert result.overall == "FALSELY_CLOSED"
    assert "investigate_false_closure" in result.required_actions
    assert "regress_change" in result.required_actions


def test_watch_time_is_not_a_useful_action():
    w = DistributionLoop("x").open_window("w")
    with pytest.raises(ValueError, match="not a useful action"):
        w.record_useful_action("watch_minutes", 500)


def test_kill_condition_growth_without_behavior_change():
    loop = DistributionLoop("ledgerline-media")
    for i, wid in enumerate(["w1", "w2"]):
        w = loop.open_window(wid)
        w.record_impressions(10_000 * (i + 1))   # impressions growing
    assert loop.kill_condition_met()
    # behavior change in the latest window clears the condition
    loop.windows[-1].record_useful_action("used_tool")
    assert not loop.kill_condition_met()
