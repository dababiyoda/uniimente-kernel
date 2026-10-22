"""Crash-recovery #3 (review of 8cb4043): a body that ran the pre-salt code asked attempt 1's FIRST and only
reconciliation question with the unsalted dispatch scope (attempt 0 was DONE, so no earlier question exists).
After the upgrade, the founder's answer to that question is about attempt 1 and must be recorded, not thrown
away with 'the retained reconciliation answered an earlier attempt'."""
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def test_a_legacy_unsalted_first_question_for_attempt_one_is_applied_not_asked_again(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    mid = "m:legacy"
    ws = workspace(home, mid)
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[note_check("note", ws / "note.txt", "hello")],
        strategies=[write_strategy("write-note", "note.txt", "hello", ["note"])],
        capabilities=["fs.read", "fs.write"],
        closure={"kind": "infinite", "ladder": [["note"]], "cadence_seconds": 60})))
    clock = Clock()
    with Body(home, clock=clock) as body:
        real, calls = body.registry.adapters["fs.write"], []

        def adapter(params, ctx):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError("power lost mid-effect")       # attempt 1 dies mid-effect
            return real(params, ctx)
        body.registry.adapters["fs.write"] = adapter

        # Emulate the pre-salt code (21107aa, and #178 before 1a92b99): every RECONCILIATION is asked with the
        # dispatch's own, unsalted outcome.scope_digest, whatever the attempt.
        original = body.engine._request

        def legacy_request(m, *, kind, scope_digest, action_id, **kw):
            if kind == "RECONCILIATION":
                [unc] = [e.payload for e in body.journal.replay("mission.action")
                         if e.payload["action_id"] == action_id and e.payload["status"] == "UNCERTAIN"]
                scope_digest = unc["scope_digest"]
            return original(m, kind=kind, scope_digest=scope_digest, action_id=action_id, **kw)
        body.engine._request = legacy_request

        body.boot()
        for _ in range(4):
            body.tick(); clock.advance(120)
        (ws / "note.txt").write_text("damaged")                   # the check drifts: attempt 1 is dispatched
        for _ in range(4):
            body.tick(); clock.advance(120)
        acts = [(e.payload["attempt"], e.payload["status"]) for e in body.journal.replay("mission.action")]
        assert acts == [(0, "DONE"), (1, "UNCERTAIN")]
        [legacy] = [r for r in body.engine.book.open_requests() if r["kind"] == "RECONCILIATION"]
        del body.engine._request                                  # the upgrade: today's code from here on

        drop(home, signed(key, body_id, "DECISION", {"request_id": legacy["request_id"],
                                                     "answer": "reconcile_not_executed",
                                                     "reason": "inspected the retained evidence"}, now=clock.now))
        for _ in range(3):
            body.tick(); clock.advance(120)

        unblocked = [e.payload["why"] for e in body.journal.replay("mission.unblocked")]
        assert "the retained reconciliation answered an earlier attempt; asking for this one" not in unblocked, \
            "the founder's answer about attempt 1 was thrown away with a false explanation"
        reconciled = [e.payload for e in body.journal.replay("mission.action")
                      if e.payload["status"] == "RECONCILED_NOT_EXECUTED" and e.payload["attempt"] == 1]
        assert reconciled, "the founder's answer to attempt 1's only question was never recorded"
        asked = [e.payload["request_id"] for e in body.journal.replay("decision.requested")
                 if e.payload["kind"] == "RECONCILIATION"]
        assert asked == [legacy["request_id"]], "a second reconciliation question about the same dispatch"
