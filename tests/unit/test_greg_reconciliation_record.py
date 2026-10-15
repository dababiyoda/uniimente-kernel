"""A founder reconciliation settles an uncertain act without breaking anything that reads the action history.

Found independently by the ten-step proof (2026-10-15) and by PR #178: after a SIGKILL mid-worker and a
founder "not executed" reconciliation, Mission Control and the morning report crashed with
``KeyError: 'capability'``. #178's canonical fix makes the settlement record name the dispatched capability
(route ``founder_reconciliation``) and makes routing count one outcome per attempt. These tests hold that fix,
and the resilience readers to the same one-outcome rule (they still counted the interruption twice).
"""
from greg import capabilities, resilience, routing
from greg.body import Body, morning_projection
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def _interrupted_then_reconciled(tmp_path, monkeypatch, answer):
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:reconcile")
    spec = mission("m:reconcile", checks=[note_check("note", ws / "note.txt", "hello")],
                   strategies=[write_strategy("write-note", "note.txt", "hello", ["note"])],
                   capabilities=["fs.read", "fs.write"])
    manifest, real = capabilities.BUILTINS["fs.write"]
    calls = []

    def dies_once(params, ctx):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("power lost mid-effect")
        return real(params, ctx)
    monkeypatch.setitem(capabilities.BUILTINS, "fs.write", (manifest, dies_once))
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    for _ in range(3):
        body.tick()
        clock.advance(60)
    asked = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "RECONCILIATION"]
    assert len(asked) == 1 and len(calls) == 1, "one question, no blind retry"
    drop(home, signed(key, body_id, "DECISION", {"request_id": asked[0]["request_id"], "answer": answer}))
    for _ in range(4):
        body.tick()
        clock.advance(60)
    return home, body, calls


def test_a_settlement_carries_the_uncertain_acts_identity_and_the_morning_report_still_renders(tmp_path, monkeypatch):
    home, body, calls = _interrupted_then_reconciled(tmp_path, monkeypatch, "reconcile_not_executed")
    try:
        acts = [e.payload for e in body.journal.replay("mission.action") if e.payload["action_id"] == "write-note"]
        assert [a["status"] for a in acts] == ["UNCERTAIN", "RECONCILED_NOT_EXECUTED", "DONE"] and len(calls) == 2
        settlement = acts[1]
        assert settlement["capability"] == "fs.write" and settlement["receipt"] is None and settlement["at"]
        assert settlement["route"] == "founder_reconciliation" and settlement["dispatch_route"] == acts[0]["route"]
        # one interruption is one failed act for the capability, not two
        assert routing.track_record(body.journal)["fs.write"]["failed"] == 1
        assert sum(resilience.failed(e.payload) for e in resilience._acts(body.journal)) == 1
    finally:
        body.close()
    report = morning_projection(home)                      # crashed with KeyError: 'capability' before the fix
    assert any(a["status"] == "RECONCILED_NOT_EXECUTED" and a["capability"] == "fs.write"
               for a in report["q3_what_i_did"])


def test_an_older_short_settlement_record_on_disk_does_not_break_the_readers(tmp_path, monkeypatch):
    home, body, _ = _interrupted_then_reconciled(tmp_path, monkeypatch, "reconcile_not_executed")
    try:   # the shape every settlement had before 2026-10-15: no capability, route, receipt or time
        body.journal.record("mission.action", {"mission_id": "m:reconcile", "action_id": "write-note", "attempt": 0,
                                               "status": "DONE", "reasons": ["founder reconciliation: reconcile_executed"],
                                               "cost_usd": 0.0}, key=["legacy-settlement"])
        routing.track_record(body.journal)
        resilience.common_causes(body.journal)
    finally:
        body.close()
    report = morning_projection(home)
    assert any(a["capability"] is None and a["status"] == "DONE" for a in report["q3_what_i_did"])
    assert "fs.write" in report["q10_retain"]              # the receipted write is retained; the unreceipted one adds nothing
