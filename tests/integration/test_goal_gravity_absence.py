"""The founder's return scene across a multi-day absence with process-image restarts.

    You disappear from operational involvement for several days. When you return, UNIIMENTE tells you
    what remained active, what executed with receipts, what was prepared, what policy blocked, what is
    unknown and awaits reconciliation, what waits for your decision, what it cost (estimates, not
    settlement), what was retained, and what the institution learned.

Each "day" reopens the same JSONL ledger in a fresh loop, so the report is a fold of durable records
only. Evidence tier: INTEGRATION-TESTED on a synthetic ledger with a test passport, the development
witness key and test-minted grants. Nothing here touched reality; the report says so itself.
"""
from __future__ import annotations

import os
import tempfile

from capabilities.genome import GenomeRegistry
from compiler.ucl_compiler import compile_constitution
from egregore.absence import AbsenceReporter
from egregore.contracts import SignalEnvelope
from egregore.goals import InterventionSpec
from egregore.gravity import GoalGravityLoop
from egregore.resources import ResourceGovernor
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger
from tests.unit.test_goal_gravity import GOOD, brief_move, outreach_move, robotics_goal
from tests.unit.test_goal_gravity_absence import with_moves
from tests.unit.test_goal_gravity_seams import simple_goal

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUTHORIZED = "2026-11-01T09:00:00Z"
DAY1, DAY2, DAY3 = "2026-11-02T09:00:00Z", "2026-11-03T09:00:00Z", "2026-11-04T09:00:00Z"
RETURN = "2026-11-05T09:00:00Z"
NEXT_DAY = "2026-11-06T09:00:00Z"


def _signal(event_id, observed_at, *, domain, tags=(), observations=(), source="feed://test"):
    return SignalEnvelope.build(source=source, source_event_id=event_id, observed_at=observed_at,
                                payload={"domain": domain, "tags": list(tags), "observations": list(observations)},
                                evidence_refs=(f"source:{event_id}",), trust_level="attributed")


def _package(**kw):
    base = dict(intervention_id="assemble-package", description="assemble the founder decision package",
                action_class="package.assemble", requested_capability="package.assemble", consequence_class="internal_write",
                target="sandbox:packages", expected_outcome="package assembled", payload={"kind": "decision"}, tactic="package")
    base.update(kw)
    return InterventionSpec.build(**base)


def _grant(loop, gate, spec, move):
    proposal = loop.classifier.proposal_for(spec, move, evidence_refs=[f"goal:{spec.goal_id}"], evidence_confidence=0.9)
    return gate.grants.issue_single_action(proposal=proposal, policy_version="1.0.0")


def test_founder_return_report_after_a_multi_day_absence_with_restarts():
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    signer = WitnessSigner(env="development")
    actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel", legal_principal="alfonso_lopez",
                            declared_capabilities=["research.brief", "outreach.contact", "package.assemble"],
                            budget_ceiling_usd=5.0, consequence_class="external_contact")
    governor = lambda: ResourceGovernor(max_model_calls=4, max_estimated_cost_usd=0.05)  # noqa: E731
    brief = brief_move(estimated_cost_usd=0.04)
    outreach = outreach_move(estimated_cost_usd=0.5)
    robotics = with_moves(robotics_goal(second_node=False), brief, outreach)
    ext = simple_goal(tag="ext", ceiling="external_contact", move=outreach_move(payload={"template": "ext"}))
    pkg = simple_goal(tag="pkg", move=_package())

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "ledger.jsonl")

        def open_body():
            ledger = EvidenceLedger(compiled.constitution_hash, path=path)
            gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger, signer=signer)
            loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                                   legal_principal="alfonso_lopez", genomes=GenomeRegistry())
            return ledger, gate, loop

        # Before leaving: three authorized goals (declared lineage, not authentication).
        ledger, gate, loop = open_body()
        robotics_id = loop.registry.authorize(robotics, now=AUTHORIZED)
        ext_id = loop.registry.authorize(ext, now=AUTHORIZED)
        pkg_id = loop.registry.authorize(pkg, now=AUTHORIZED)
        ledger.close()

        # Day 1: relevant evidence wakes robotics; the brief executes through the Gate under a pre-existing grant;
        # the external outreach is prepared and one compressed decision is opened. The founder is not here.
        ledger, gate, loop = open_body()
        day1 = loop.turn(trigger_id="host:day1", now=DAY1, resources=governor(), gate=gate, executor=GOOD, evidence_confidence=0.9,
                         grants={"research.brief": _grant(loop, gate, robotics, brief)},
                         signals=[_signal("h1", DAY1, domain="hardware",
                                          observations=[{"subject": "actuator", "attribute": "cost_usd", "value": 410, "confidence": 0.9}])])
        assert [e["goal_id"] for e in day1.executed] == [robotics_id]
        ledger.close()

        # Day 2: the ext goal's external move is dispatched and the carrier dies; the outcome is unknown.
        ledger, gate, loop = open_body()

        def boom(_p):
            raise RuntimeError("carrier timeout")

        day2 = loop.turn(trigger_id="host:day2", now=DAY2, resources=governor(), gate=gate, executor=boom, evidence_confidence=0.9,
                         grants={"outreach.contact": _grant(loop, gate, ext, outreach_move(payload={"template": "ext"}))},
                         signals=[_signal("x1", DAY2, domain="market", tags=["ext"],
                                          observations=[{"subject": "g", "attribute": "metric", "value": 0, "confidence": 0.9}])])
        assert day2.processed[0]["decisions"][0]["evidence_state"] == "unknown"
        ledger.close()

        # Day 3: the pkg goal's grant is bound to another objective; the Gate refuses at admission. The ext goal wakes
        # again and its unknown outcome is surfaced as an emergency information item (external move).
        ledger, gate, loop = open_body()
        wrong = _grant(loop, gate, pkg, _package(intervention_id="assemble-other", description="assemble a different package",
                                                 target="sandbox:other", payload={"kind": "other"}))
        day3 = loop.turn(trigger_id="host:day3", now=DAY3, resources=governor(), gate=gate, executor=GOOD, evidence_confidence=0.9,
                         grants={"package.assemble": wrong},
                         signals=[_signal("p1", DAY3, domain="market", tags=["pkg"],
                                          observations=[{"subject": "g", "attribute": "metric", "value": 0, "confidence": 0.9}]),
                                  _signal("x2", DAY3, domain="market", tags=["ext"],
                                          observations=[{"subject": "g", "attribute": "metric", "value": 0, "confidence": 0.9}])])
        states = {p["goal_id"]: p for p in day3.processed}
        assert states[pkg_id]["decisions"][0]["evidence_state"] == "failed"
        assert states[ext_id]["open_attempts"]
        assert any(i["urgency"] == "emergency" and i["kind"] == "information" for i in day3.routing["immediate"])
        ledger.close()

        # The founder returns. One report over the absence, from the ledger alone.
        ledger, gate, loop = open_body()
        out = loop.return_report(since=DAY1, until=RETURN)
        report = out["report"]
        fa = report["founder_activity"]
        assert fa["away"] is True and fa["answers"] == 0 and fa["goals_authorized"] == 0
        assert report["goals"]["total"] == 3 and report["goals"]["active_in_window"] == 3
        assert report["turns"]["count"] == 3
        # Executed: the brief, with a receipt on the chain; the prepared outreach is not executed.
        assert [e["intervention_id"] for e in report["executed"]] == ["compile-brief"]
        receipt = ledger.find(report["executed"][0]["receipt_hash"])
        assert receipt is not None and receipt.record_type == "receipt"
        assert report["executed"][0]["reconciled"] is True and report["executed"][0]["verification"] is None
        assert {p["intervention_id"] for p in report["prepared"]} >= {"contact-engineers"}
        # Blocked by policy at the Gate, with the Gate's reasons; unknown attempt open and never retried.
        assert [r["intervention_id"] for r in report["refused_by_gate"]] == ["assemble-package"]
        assert report["refused_by_gate"][0]["gate_state"] == "refused"
        assert [o["goal_id"] for o in report["open_attempts_as_of_until"]] == [ext_id]
        # One decision exceeds delegated authority and waits; the emergency item informed and asked for nothing.
        assert any(w["goal_id"] == robotics_id and w["kind"] == "decision" for w in report["decisions_waiting_as_of_until"])
        assert any(i["urgency"] == "emergency" for i in report["information_items_in_window"])
        assert all(any(o["cost"] == "none" for o in w["options"]) for w in report["decisions_waiting_as_of_until"])
        # Money: declared estimates with reconciliation flags, never settlement.
        assert report["money"]["estimated_cost_usd_executed"] == 0.04
        assert report["money"]["estimated_cost_usd_prepared_not_spent"] == 0.5
        assert report["money"]["treasury_or_business_events_on_ledger_all_time"] == 0
        # Retained and learned.
        assert report["retained"]["retentions"] >= 1 and report["retained"]["assets_by_kind"]["evidence"] >= 1
        assert report["learned"]["experiences_integrated"] >= 4 and report["learned"]["independent_verifications"] == 0
        text = " ".join(report["headline"])
        for phrase in ("3 of 3 authorized goal(s) were active", "1 move(s) executed through the Consequence Gate with receipts",
                       "1 refused by the Gate or policy at commit", "1 dispatched move(s) have an unknown outcome",
                       "not a bank statement", "This report requests nothing", "You answered nothing in this window",
                       "executor claims are not verification"):
            assert phrase in text, phrase
        assert report["evidence_tier"]["ledger_chain_intact"] is True
        assert out["recorded"] is True
        ledger.close()

        # Another restart: the same window yields the same report and appends nothing.
        ledger, gate, loop = open_body()
        again = loop.return_report(since=DAY1, until=RETURN)
        assert again["report"] == report and again["recorded"] is False
        assert len(ledger.by_type(AbsenceReporter.REPORT_RECORD)) == 1
        # The wake schedule tells a host when to call next; it runs nothing.
        plan = loop.wake_schedule(now=RETURN)
        assert plan["next_due_at"] is not None and plan["suggested_trigger_id"].startswith("cadence:")
        assert {e["goal_id"] for e in plan["entries"]} == {robotics_id, ext_id, pkg_id}

        # The founder acts: refuses the outreach, resolves the unknown attempt accountably, has the brief verified.
        ask = next(w for w in report["decisions_waiting_as_of_until"] if w["goal_id"] == robotics_id)
        loop.founder_answer(ask["item_id"], decision="refuse", actor="alfonso_lopez", note="not by cold outreach", now=NEXT_DAY)
        resolved = loop.reconcile(ext_id, now=NEXT_DAY, resolutions={
            outreach_move(payload={"template": "ext"}).route_hash: {
                "state": "failed", "reconciled_by": "alfonso_lopez", "evidence_refs": ["carrier:ticket-77"],
                "note": "carrier confirms nothing was sent"}})
        assert resolved["resolved"] and resolved["unresolved"] == []
        loop.verify_outcome(robotics_id, brief.route_hash, verifier="auditor:independent",
                            evidence_refs=[report["executed"][0]["receipt_hash"]], note="brief present", now=NEXT_DAY)
        after = loop.return_report(since=RETURN, until=NEXT_DAY)["report"]
        assert after["founder_activity"]["away"] is False and after["founder_activity"]["answers"] == 1
        assert after["founder_activity"]["accountable_resolutions"] == 1 and after["reconciliations"][0]["to"] == "failed"
        assert after["open_attempts_as_of_until"] == [] and after["verifications"][0]["verdict"] == "confirmed"
        assert ask["item_id"] not in {w["item_id"] for w in after["decisions_waiting_as_of_until"]}
        # The execution itself happened on day 1 and stays in the day-1 window, now reported as verified as of NEXT_DAY.
        whole = loop.return_report(since=DAY1, until=NEXT_DAY, record=False)["report"]
        assert whole["executed"][0]["verification"]["verdict"] == "confirmed" and whole["evidence_tier"]["externally_verified_moves"] == 1
        ok, msg = ledger.verify_chain()
        assert ok, msg
        ledger.close()
