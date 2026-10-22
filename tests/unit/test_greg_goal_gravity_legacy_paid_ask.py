"""A paid APPROVAL recorded before ``move_digest`` existed (a body upgraded from 2cf4bdc with the ask in flight).

6352c68 links a goal's move to the engine's APPROVAL by a spend-free ``move_digest`` and falls back to the
spend-bound scope digest for requests without one. That fallback reproduces finding 9/10 for every paid ask an
older build recorded: any spend after the ask cuts the link. The legacy request still records the spend state it
was asked at (``evidence.budget``), so the move it names can be checked exactly.

The legacy writer is emulated by recording APPROVALs without ``move_digest``, exactly as 2cf4bdc wrote them.
"""
from greg import asks, goal_gravity as gg
from tests.unit.test_greg_goal_gravity import GOAL, MID, PaidWorld, ship_move, fast  # noqa: F401
from tests.unit.test_greg_goal_gravity_paid_moves import PaidRepairWorld, _done, _regress_c_and_prepare


def _as_before_move_digest(mp):
    real = asks.record

    def record(journal, message, *, quoted=()):
        if message.get("kind") == "APPROVAL":
            message = {k: v for k, v in message.items() if k != "move_digest"}
        return real(journal, message, quoted=quoted)
    mp.setattr(asks, "record", record)


def test_a_signed_reject_of_a_paid_goal_ask_recorded_before_the_upgrade_is_remembered_after_spend(
        tmp_path, fast, monkeypatch):
    world = PaidRepairWorld(tmp_path)
    with monkeypatch.context() as mp:            # the pre-upgrade build records the goal's paid ask
        _as_before_move_digest(mp)
        gid, _ = world.start(GOAL(moves=(ship_move(estimated_cost_usd=0.10),)))
        world.tick(6)
    ask = [r for r in world.w2_requests() if (r.get("evidence") or {}).get("goal_id") == gid]
    assert len(ask) == 1 and "move_digest" not in ask[0]
    rid = ask[0]["request_id"]
    spent = world.book().missions[MID].spent_usd
    _regress_c_and_prepare(world)                # upgraded build: preparation spends while the ask is open
    assert world.book().missions[MID].spent_usd > spent
    assert world.projection()["goals"][0]["open_requests"] == [rid]
    world.submit("DECISION", {"request_id": rid, "answer": "reject", "reason": "not this way"})
    world.tick(6)
    assert world.book().missions[MID].failed["w2"].startswith("founder rejected")
    assert world.registry().is_route_refused(gid, ship_move(estimated_cost_usd=0.10).route_hash)


def test_goal_evidence_keeps_a_pre_upgrade_signed_approval_behind_its_executed_paid_move(
        tmp_path, fast, monkeypatch):
    world = PaidWorld(tmp_path)
    with monkeypatch.context() as mp:            # the pre-upgrade build: the loop's own paid ask, then the goal
        _as_before_move_digest(mp)
        world.submit("MISSION", world.mission_spec(), "a-mission.json")
        world.tick(6)
        rid = world.w2_requests()[0]["request_id"]
        world.submit("GOAL", GOAL(moves=(ship_move(estimated_cost_usd=0.10),)), "b-goal.json")
        out = world.tick(3)
    gid = [c for c in out[0]["commands"] if c["status"] == "APPLIED"][0]["result"]["goal_id"]
    assert "move_digest" not in world.w2_requests()[0]
    world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship"})
    world.tick(6)
    assert len(_done(world, "w2")) == 1
    with world.body() as b:
        asks_shown = gg.evidence(b.journal, gid)["asks"]
    assert [a["request_id"] for a in asks_shown] == [rid]
    assert asks_shown[0]["answer"] == "approve" and asks_shown[0]["answer_signature_verified"] is True
