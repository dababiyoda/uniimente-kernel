"""A dispute becomes a bounded verification task when the body can obtain the deciding evidence (directive on #210,
section 2: contradiction -> investigation -> evidence acquisition -> authorized resolution -> corrected competence).

Settlement lists, as a route for the deciding observation, only capabilities the founder attached that are read-only
and declare ``world.observe.<objective>``. It prepares an unsigned MISSION for one of them; nothing runs until the
founder signs it, and the reading resolves nothing by itself. Values are synthetic test inputs.
"""
from __future__ import annotations

import pytest

from greg.capabilities import CapabilityManifest
from greg.cognition import settlement
from greg.missions import validate_mission
from tests.unit.test_greg_outcome_resolution import report, signed_commands  # noqa: F401  (autouse fixture)
from tests.unit.test_greg_pending_construction_realization import appraise, pending

REAL_SIGNED_REALIZATIONS = settlement._signed_realizations   # before the fixture journals' stand-in replaces it


def observer(cid="world.ledger-reader", *, function="world.observe.profit", consequence="read_only", budget=0.0):
    return CapabilityManifest(
        capability_id=cid, version="1.0.0", provider="installed:test-observer", function=function,
        description="reads the realized profit of an answer from the business ledger", route="internal",
        consequence_class=consequence, inputs={"receipt": "str", "objective": "str"}, outputs={"realized": "float"},
        target_prefix="world:", budget_ceiling_usd=budget, strengthens=("proof",))


def register(journal, manifest, *states):
    journal.record("capability.registered", {"manifest": manifest.to_dict(), "state": "VERIFIED",
                                             "origin": {"kind": "test"}})
    for state in states:
        journal.record("capability.state", {"capability_id": manifest.capability_id, "state": state,
                                            "by": "founder command"})


def unresolvable():
    """Two founder reports that disagree on the verdict: nothing on the record decides it (promise 2)."""
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "founder_reported")
    return journal, receipt


def conflict(journal):
    [row] = [r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective_conflict"]
    return row


def test_with_no_observer_the_request_names_the_missing_capability_and_prepares_nothing():
    journal, _ = unresolvable()
    row = conflict(journal)
    assert row["evidence_request"]["acquirable_by_body"] == []
    assert "world.observe.profit" in row["evidence_request"]["acquisition_limit"]
    assert "prepared_verification" not in row


def test_an_attached_read_only_observer_gets_a_bounded_unsigned_verification_mission():
    journal, receipt = unresolvable()
    register(journal, observer(), "ATTACHED")
    before = len(journal.events)
    row = conflict(journal)
    assert len(journal.events) == before                       # prepared, never recorded
    assert row["evidence_request"]["acquirable_by_body"] == ["world.ledger-reader"]
    assert row["evidence_request"]["acquisition_limit"] is None
    prepared = row["prepared_verification"]
    spec = prepared["mission"]
    validate_mission(spec)                                     # a mission the founder can sign as it stands
    cone = spec["light_cone"]
    assert cone["capabilities"] == ["world.ledger-reader"] and cone["targets"] == ["world:profit"]
    assert cone["max_consequence_class"] == "read_only" and cone["budget_usd"] == 0 and spec["strategies"] == []
    [check] = spec["success_checks"]
    assert check["sensor"]["capability"] == "world.ledger-reader" and check["sensor"]["params"]["receipt"] == receipt
    assert check["sensor"]["params"]["answer_version"] == row["answer_version"]
    assert "at or above 1.9" in spec["intended_effect"]
    assert "founder" in prepared["signing"] and "does not make the reading true" in prepared["after"]
    from greg.gravity import _measured_trust
    trust = _measured_trust(journal)
    assert trust["verifications_prepared"] == 1 and trust["conflicting_construction_claims"] == 1
    # the dispute still credits nothing while the evidence is being acquired
    assert row["competence_claim"].startswith("withheld") and settlement.competence(journal) == {}


@pytest.mark.parametrize("manifest,states", [
    (observer(), ()),                                          # registered and verified, never attached
    (observer(), ("ATTACHED", "DETACHED")),                    # the founder detached it
    (observer(), ("ATTACHED", "QUARANTINED")),                 # quarantined after a fault
    (observer(consequence="external_contact"), ("ATTACHED",)),  # reaches out: not an observation route
    (observer(function="world.observe.cost"), ("ATTACHED",)),  # observes another quantity
    (observer(function="web.fetch"), ("ATTACHED",)),           # a generic fetch does not know which record decides
])
def test_only_an_attached_read_only_observer_of_this_quantity_is_a_route(manifest, states):
    journal, _ = unresolvable()
    register(journal, manifest, *states)
    row = conflict(journal)
    assert row["evidence_request"]["acquirable_by_body"] == [] and "prepared_verification" not in row


def test_a_paid_observer_carries_its_own_ceiling_into_the_cone_and_no_more():
    journal, _ = unresolvable()
    register(journal, observer(budget=0.25), "ATTACHED")
    assert conflict(journal)["prepared_verification"]["mission"]["light_cone"]["budget_usd"] == 0.25


def test_a_dispute_already_decidable_from_the_record_prepares_a_resolution_not_a_verification():
    journal, receipt = pending()
    appraise(journal, "VERIFIED")
    report(journal, receipt, 1, "founder_reported")
    report(journal, receipt, 2, "external_record")
    register(journal, observer(), "ATTACHED")
    row = conflict(journal)
    assert row["resolvable_now"] is True and "prepared_verification" not in row


# --- on a body: the founder signs the prepared verification, the observer runs, the reading feeds a signed report and
# the prepared resolution, and competence is corrected exactly once -------------------------------------------------


def test_on_a_body_the_prepared_verification_runs_and_its_reading_decides_the_dispute(tmp_path, monkeypatch):
    monkeypatch.setattr(settlement, "_signed_realizations", REAL_SIGNED_REALIZATIONS)   # the body's real envelopes
    pytest.importorskip("networkx")
    pytest.importorskip("scipy")
    from tests.greg_fixtures import drop, signed
    from tests.unit.test_greg_construction_realization import PROMISED, Run
    from tests.unit.test_greg_recombine import PORTFOLIO

    calls = []

    def ledger_reader(params, ctx):
        calls.append(params)
        return {"realized": PROMISED, "record": "general ledger, period close 2026-10"}

    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-verify", PORTFOLIO)
        run.realize(record, PROMISED - 2, source="founder_reported")
        run.realize(record, PROMISED, source="founder_reported")
        row = next(r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective_conflict")
        assert row["resolvable_now"] is False and row["evidence_request"]["acquirable_by_body"] == []

        manifest = observer()
        run.body.registry.register(manifest, ledger_reader, state="VERIFIED")
        journal.record("capability.registered", {"manifest": manifest.to_dict(), "state": "VERIFIED",
                                                 "origin": {"kind": "test"}}, key=["observer", "registered"])
        run.command("CAPABILITY_ATTACH", {"capability_id": manifest.capability_id})
        row = next(r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective_conflict")
        spec = row["prepared_verification"]["mission"]
        assert calls == []                                     # nothing ran before the founder signed it

        drop(run.home, signed(run.key, run.body_id, "MISSION", spec))
        for _ in range(8):
            run.body.tick()
            run.clock.advance(31)
            if run.body.engine.book.missions[spec["mission_id"]].status == "ACHIEVED":
                break
        assert run.body.engine.book.missions[spec["mission_id"]].status == "ACHIEVED"
        assert calls and calls[0]["receipt"] == record.hash
        [reading] = [r for r in run.body.ledger.by_type("receipt")
                     if ((r.payload.get("result") or {}).get("output") or {}).get("record", "").startswith("general ledger")]
        assert reading.payload["result"]["output"]["realized"] == PROMISED
        assert run.outcome(record) is None                     # the reading alone resolves nothing

        # the founder reads it and signs an independent report naming the receipt, then the prepared resolution
        run.command("REALIZATION", {"receipt": record.hash, "realized": PROMISED, "source": "external_record",
                                    "note": f"general ledger via {manifest.capability_id}, receipt {reading.hash}"})
        row = next(r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective_conflict")
        assert row["resolvable_now"] is True
        run.command("REALIZATION", {**row["prepared_resolution"]["body"], "note": f"observed: {reading.hash}"})
        outcome = run.outcome(record)
        assert outcome["world"]["state"] == "adjudicated" and outcome["correct"] is True
        def settled():
            return [e.payload for e in journal.replay("cognition.settled") if e.payload.get("receipt") == record.hash]
        before = len(settled())
        settlement.reconcile(journal)
        once = settled()
        assert len(once) == before + 1 and once[-1]["correct"] is True      # the corrected outcome, settled once
        settlement.reconcile(journal)
        run.body.tick()
        assert settled() == once                                            # and never again
        competence = settlement.competence(journal)
        assert sum(r["count"] for r in competence.values()) == 1 and sum(r["correct"] for r in competence.values()) == 1
