"""A restore from a backup (greg/recovery.py) holds on every reader of mission truth, not only on the command path.

Two seams of the joined tree (#192 trunk with Track B #189), found by an independent review:
- the restore withdraws an approval the original may have used; Goal Gravity still took it as the founder's answer to
  the goal's move, so the goal's ask was suppressed as "already answered by founder";
- ``Body._after_restore`` refuses a command issued before the restore, but the verified fold admitted a forged
  ``command.accepted`` row carrying such a DECISION, so a decision the original applied after the backup could move
  the restored mission a second time.

The founder key is a per-test Ed25519 key, not Alfonso's.
"""
from __future__ import annotations

from egregore.gravity import GoalGravityLoop
from foundry.systems import seed
from greg import goal_gravity as gg
from greg.body import Body
from greg.founder import FounderAuthError
from greg.missions import MissionBook
from greg.recovery import restore_body
from tests.greg_fixtures import signed
from tests.unit.test_greg_answer_reverification import blocked, smuggle
from tests.unit.test_greg_goal_gravity import World, expected_w2_request, fast  # noqa: F401

import pytest

RESTORED = "issued before this body was restored from a backup"


def test_a_restore_voided_approval_is_not_the_founders_answer_to_the_goal(tmp_path, fast):
    world = World(tmp_path)
    gid, _ = world.start()
    rid, _ = expected_w2_request(world)
    world.tick(6)
    assert [a["request_id"] for a in world.w2_requests()] == [rid]          # the goal's ask for its move, open
    with world.body() as b:
        b.apply(world.sign("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship it"}))
    store = tmp_path / "seed-store"
    made = seed.make_seed(world.home, store)                                # the backup holds the approve, not its run
    world.tick(4)
    assert (world.ws / "d.txt").read_text() == "shipped"                    # the original ships on it, then is lost
    world.home.rename(world.home.parent / "lost-machine")
    world.clock.advance(60)
    report = restore_body(store, made["seed"], world.home, clock=world.clock)
    assert report["voided"]["approvals"] == [rid] and not (world.ws / "d.txt").exists()

    world.clock.advance(1)
    world.submit("BODY_RESUME", {})                                         # the founder declares the original gone
    since = len(world.records(GoalGravityLoop.TURN_RECORD))
    world.ingest("ops", "m:watch d.txt broken")                             # evidence that wakes the goal
    world.tick()                                                            # one tick: the goal turns before the engine
    turns = world.records(GoalGravityLoop.TURN_RECORD)[since:]
    assert turns, "the goal did not turn"
    suppressed = [tuple(s) for t in turns for s in (t["turn"].get("routing") or {}).get("suppressed", [])]
    assert not [s for s in suppressed if s[1] == "already answered by founder"], suppressed
    with world.body() as b:                                                 # every reader of used-up approvals agrees
        book = b.engine.book
        assert rid in book.withdrawn and book.withdrawn[rid].get("voids_approval")
        routed = [i for t in turns for lane in ("immediate", "batched") for i in t["turn"]["routing"].get(lane, [])
                  if i.get("kind") == "decision"]
        assert routed, "the goal's decision about its move was not routed"
        store_ = gg.binding_for(b).store
        store_.begin(gg.founder_facts(b.ledger, body_id=b.config["body_id"]).signed)
        for item in routed:
            assert store_._scope(item) is not None
            assert store_.answer_for(_Item(item)) is None
    fresh = [r["request_id"] for r in world.w2_requests() if r["request_id"] != rid]
    assert fresh, "the goal's ask for its move was not recorded again"
    assert (world.book().requests[fresh[-1]].get("evidence") or {}).get("goal_id") == gid
    assert not (world.ws / "d.txt").exists()                                # nothing runs before a fresh decision


class _Item:
    """The two fields ``BodyAttentionStore.answer_for`` reads, from a routed item's recorded dict."""
    def __init__(self, data: dict):
        self.kind, self._data = data["kind"], data

    def to_dict(self) -> dict:
        return dict(self._data)


def test_a_forged_acceptance_cannot_revive_a_decision_issued_before_the_restore(tmp_path):
    w = blocked(tmp_path)                                                   # the original waits on the founder
    store = tmp_path / "seed-store"
    made = seed.make_seed(w.home, store)                                    # the backup: the ask is still open
    w.clock.advance(60)
    decision = signed(w.key, w.body_id, "DECISION", {"request_id": w.rid, "answer": "approve", "reason": "go"},
                      now=w.clock())
    with Body(w.home, clock=w.clock) as body:                               # after the backup the original applies
        body.apply(decision)                                                # it and writes, then is lost
        body.tick()
    assert (w.ws / "c.txt").read_text() == "ok"
    w.home.rename(w.home.parent / "lost-machine")
    w.clock.advance(60)
    restore_body(store, made["seed"], w.home, clock=w.clock)
    assert not (w.ws / "c.txt").exists()
    with Body(w.home, clock=w.clock) as body:
        w.clock.advance(1)
        with pytest.raises(FounderAuthError, match=RESTORED):
            body.apply(decision)                                            # the command path refuses it
        assert w.rid in [r["request_id"] for r in body.engine.book.open_requests()]   # the ask is open here
        smuggle(body.journal, w.clock(), decision, w.mid)                   # a writer pairs it with an acceptance
        for book in (MissionBook(body.journal), gg.founder_facts(body.ledger).book):
            assert w.rid not in book.answers, "the fold admitted a DECISION the command path refuses"
            assert RESTORED in book.unverified[w.rid]["why"]
        w.clock.advance(1)
        body.apply(signed(w.key, w.body_id, "BODY_RESUME", {}, now=w.clock()))
        for _ in range(4):
            body.tick()
            w.clock.advance(1)
        assert not (w.ws / "c.txt").exists()                                # the original's write is not repeated
        m = body.engine.book.missions[w.mid]
        assert m.status == "ACTIVE" and m.blocker["request_id"] == w.rid and w.rid not in body.engine.book.answers
