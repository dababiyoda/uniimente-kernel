"""daleobanks.outcome is a projection of this mission's canonical daleobanks.publish Gate receipts.

The workspace DALEOBANKS ledger is writable by any signed workspace write, so it may only lower
``organ_consistent``; it never adds a fact. No DALEOBANKS checkout is needed: receipts are built here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from types import SimpleNamespace

import pytest

from events.spine import EventSpine
from greg import daleobanks_bridge as bridge
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
from greg.journal import Journal
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace

MID = "m:publish"


def chain(*events):
    entries, prev = [], "0" * 64
    for seq, (event, payload) in enumerate(events, 1):
        entry = {"seq": seq, "ts": "2026-10-14T00:00:00+00:00", "event": event, "payload": payload, "prev_hash": prev}
        entry["hash"] = prev = hashlib.sha256(json.dumps(entry, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        entries.append(entry)
    return entries


DRY_RUN = chain(("publish_attempt", {"platform": "x"}), ("publish_result", {"platform": "x", "dry_run": True}))
LIVE = chain(("publish_attempt", {"platform": "x"}),
             ("publish_result", {"platform": "x", "dry_run": False, "post_id": "forged"}))


def write(ws, entries):
    (ws / "daleobanks").mkdir(parents=True, exist_ok=True)
    (ws / "daleobanks" / "decision_ledger.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))


def output(entries, status="BLOCKED_BY_DALEOBANKS"):
    return {"status": status, "published": {}, "kill_switch_armed": False,
            "daleobanks_ledger": {"path": "decision_ledger.jsonl", "chain_ok": True,
                                  "tail": [{k: e[k] for k in ("seq", "event", "payload", "hash")} for e in entries]},
            "authority_created": False}


@pytest.fixture
def setup(tmp_path):
    journal = Journal(EventSpine(EvidenceLedger("sha256:" + "4" * 64, path=str(tmp_path / "l.jsonl"))),
                      actor="spiffe://uniimente.internal/greg/test")
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=SecretBroker(tmp_path / "s.json"),
                            manifest=BUILTINS["daleobanks.outcome"][0], journal=journal, mission_id=MID)
    return journal, ctx


def receipted_publish(journal, out, *, mission_id=MID, action_id="request-publish"):
    receipt = journal.ledger.append("receipt", {"grant_id": "g", "result": {"result_class": "positive", "output": out}})
    journal.record("mission.action", {"mission_id": mission_id, "action_id": action_id, "attempt": 0, "status": "DONE",
                                      "capability": "daleobanks.publish", "receipt": receipt.hash}, key=[mission_id, action_id])
    return receipt.hash


def test_forged_chain_valid_organ_file_without_a_receipt_reports_nothing(setup):
    journal, ctx = setup
    write(ctx.workspace, LIVE)
    receipted_publish(journal, output(LIVE, "PUBLISHED"), mission_id="m:other")   # another mission's receipt
    assert bridge.publish_status({}, ctx) == {"requested": False, "outcome": "NONE", "unwitnessed_actions": 0}


def test_founder_reconciled_publish_without_a_receipt_reports_no_outcome(setup):
    journal, ctx = setup
    write(ctx.workspace, LIVE)
    journal.record("mission.action", {"mission_id": MID, "action_id": "request-publish", "attempt": 0, "status": "DONE",
                                      "capability": "daleobanks.publish", "receipt": None}, key=[MID, "reconciled"])
    out = bridge.publish_status({}, ctx)
    assert out["requested"] is False and out["outcome"] == "NONE" and out["unwitnessed_actions"] == 1


def test_receipted_publish_is_the_outcome_and_the_organ_file_only_confirms_it(setup):
    journal, ctx = setup
    write(ctx.workspace, DRY_RUN)
    receipt = receipted_publish(journal, output(DRY_RUN))
    out = bridge.publish_status({}, ctx)
    assert (out["requested"], out["outcome"], out["bound_receipts"], out["organ_consistent"]) == (
        True, "BLOCKED_DRY_RUN", [receipt], True)
    write(ctx.workspace, LIVE)                       # rewritten after the receipt, chain recomputed, dry_run False
    out = bridge.publish_status({}, ctx)
    assert out["outcome"] == "BLOCKED_DRY_RUN" and out["organ_consistent"] is False
    (ctx.workspace / "daleobanks" / "decision_ledger.jsonl").unlink()
    assert bridge.publish_status({}, ctx)["organ_consistent"] is False


def test_the_sensor_refuses_to_run_without_the_canonical_history(setup):
    _, ctx = setup
    write(ctx.workspace, LIVE)
    for missing in ({"journal": None}, {"mission_id": ""}):
        with pytest.raises(CapabilityError, match="journal required"):
            bridge.publish_status({}, InvocationContext(**{**ctx.__dict__, **missing}))


def test_the_mission_engine_gives_the_projecting_sensors_the_journal(tmp_path):
    from greg.body import Body
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        m = SimpleNamespace(mission_id=MID)
        for cap in ("daleobanks.outcome", "foundry.query", "foundry.apply"):
            assert body.engine._context(m, BUILTINS[cap][0]).journal is body.journal
        assert body.engine._context(m, BUILTINS["daleobanks.verify"][0]).journal is None


def test_a_receipted_publish_closes_and_the_separate_process_appraiser_verifies_it(tmp_path, monkeypatch):
    """The founder approves one external_contact publish; DALEOBANKS (stubbed in-process: no checkout here) ledgers a
    dry run. The engine and the separate-process appraiser both project the receipt, so the closure is VERIFIED."""
    from greg.body import Body
    home, key, body_id, data = make_body(tmp_path)
    (data / "post.txt").write_text("z3-solver 5.1.0.0 is on PyPI.")

    def daleobanks(params, ctx, action):
        write(ctx.workspace, DRY_RUN)
        return {"results": {"x": {"post_id": "dry-1", "dry_run": True}}, "kill_switch_armed": False, "platforms": ["x"],
                "ledger": output(DRY_RUN)["daleobanks_ledger"], "ethics": {"approved": True}, "critic": {}}
    monkeypatch.setattr(bridge, "_run", daleobanks)
    spec = mission(MID, checks=[{"check_id": "known", "description": "the publish request's outcome is known",
                                 "sensor": {"capability": "daleobanks.outcome", "params": {}, "target": "daleobanks:outcome"},
                                 "predicate": {"op": "equals", "field": "requested", "value": True}}],
                   strategies=[{"action_id": "request-publish", "capability": "daleobanks.publish",
                                "target": "daleobanks:publish", "params": {"draft": str(data / "post.txt")},
                                "advances": ["known"], "rationale": "one publish request through DALEOBANKS"}],
                   capabilities=["daleobanks.outcome"], targets=("daleobanks:*",))
    drop(home, signed(key, body_id, "MISSION", spec), "m.json")
    clock = Clock(datetime.now(timezone.utc))
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            body.tick(); clock.advance(1)
        request = body.engine.book.open_requests()[0]
    drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve",
                                                 "reason": "test"}), "d.json")
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(4):
            body.tick(); clock.advance(1)
        journal = body.journal
        verdicts = [e.payload for e in journal.replay("mission.appraised") if e.payload["mission_id"] == MID]
        achieved = [e for e in journal.replay("mission.achieved") if e.payload["mission_id"] == MID]
    assert achieved and (workspace(home, MID) / "daleobanks" / "decision_ledger.jsonl").is_file()
    assert verdicts and verdicts[-1]["verdict"] == "VERIFIED", verdicts[-1]["findings"]
