"""The mission book folds only new events, and what it shows equals a fold from the first event.

A body that runs for months cannot afford to re-read every GREG event on every tick. The book
keeps its own fold and adds only what was retained since its last rebuild. These tests pin that
the projection callers see is exactly the one a fresh book (a fold from the beginning) gives:
after every rebuild in the real mission scenarios, after callers change what they were handed,
after history is replaced, and after a fold that stopped part-way.
"""
from dataclasses import asdict

import pytest

from events.spine import EventSpine
from greg.body import Body
from greg.missions import MissionBook
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy
# Real scenarios, re-run below with every rebuild checked against a fold from the beginning.
from tests.unit.test_greg_missions import (  # noqa: F401
    test_bounded_mission_closes_only_on_reobserved_evidence,
    test_founder_critique_excludes_strategy_without_rewriting_history,
    test_ineffective_action_is_a_surprise_and_triggers_replanning,
    test_infinite_mission_climbs_ladder_then_heals_drift,
    test_outside_scope_asks_once_waits_then_follows_founder_decision,
    test_rejection_is_enforced_and_no_strategy_escalates_once,
)
from tests.unit.test_greg_human_work import (  # noqa: F401
    test_a_human_task_asks_for_a_person_and_other_checks_resume_once_it_is_observed,
    test_the_deliverable_closes_the_ask_and_the_mission_without_greg_acting,
)


def view(book):
    """Everything a caller can read from a book, as plain comparable data."""
    return ({mid: asdict(m) for mid, m in book.missions.items()},
            book.requests, book.answers, book.withdrawn, book.open_requests())


def from_the_beginning(journal):
    fresh = MissionBook.__new__(MissionBook)
    fresh.journal, fresh._cursor = journal, None
    _original_rebuild(fresh)
    return fresh


_original_rebuild = MissionBook.rebuild


@pytest.fixture(autouse=True)
def every_rebuild_equals_a_fold_from_the_beginning(monkeypatch):
    checked = []

    def checked_rebuild(self):
        _original_rebuild(self)
        assert view(self) == view(from_the_beginning(self.journal))
        checked.append(1)

    monkeypatch.setattr(MissionBook, "rebuild", checked_rebuild)
    yield
    assert checked, "no rebuild was checked"


def body_with_history(tmp_path, ticks=12):
    """A holding mission that acted, was disturbed and acted again, plus one waiting on a decision."""
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:hold")
    spec = mission("m:hold", checks=[note_check("n", ws / "n.txt", "kept")],
                   strategies=[write_strategy("w", "n.txt", "kept", ["n"])], capabilities=["fs.read", "fs.write"],
                   closure={"kind": "infinite", "cadence_seconds": 60})
    drop(home, signed(key, body_id, "MISSION", spec))
    asks = workspace(home, "m:ask")
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:ask", checks=[note_check("c", asks / "c.txt", "ok")],
        strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read"])))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for i in range(ticks):
            body.tick()
            clock.advance(61)
            if i == ticks // 2:
                (ws / "n.txt").write_text("disturbed")
    return home, clock, (key, body_id)


def test_what_callers_change_on_a_mission_is_gone_at_the_next_rebuild(tmp_path):
    home, clock, founder = body_with_history(tmp_path)
    with Body(home, clock=clock) as body:
        book = body.engine.book
        book.rebuild()
        before = view(from_the_beginning(body.journal))
        for m in book.missions.values():
            m.status, m.blocker, m.spent_usd = "ACHIEVED", {"type": "forged"}, 99.0
            m.failed["w"] = "forged"
            m.spec["strategies"].clear()
            m.approved_scopes.add("forged")
            for data in m.observations.values():
                data["passed"] = not data["passed"]
            for checks in m.pending_effect.values():
                checks.add("forged")
        book.requests.clear()
        book.answers["forged"] = {}
        book.rebuild()
        assert view(book) == before


def test_decision_records_handed_out_are_not_the_ones_the_fold_reads(tmp_path):
    """A decision record is copied once when folded, not on every rebuild (that would cost a copy
    of every decision ever made, every tick). The fold reads its own copy, so a caller that
    changes the one it was given cannot change any mission's state."""
    home, clock, founder = body_with_history(tmp_path)
    with Body(home, clock=clock) as body:
        book = body.engine.book
        drop(home, signed(*founder, "DECISION", {"request_id": book.open_requests()[0]["request_id"],
                                                         "answer": "reject", "reason": "not this way"}))
        body.tick()
        assert book.requests and book.answers
        for table in ("requests", "answers", "withdrawn"):
            for rid, data in getattr(book, table).items():
                assert data is not getattr(book, "_" + table)[rid]
                data["answer"] = data["scope_digest"] = data["action_id"] = "forged"
        _original_rebuild(book)                           # unchecked: the handed-out copies stay changed
        fresh = from_the_beginning(body.journal)
        assert view(book)[0] == view(fresh)[0]            # every mission's state is untouched
        assert all(r["scope_digest"] != "forged" for r in book._requests.values())


def test_replaced_history_is_folded_again_from_the_beginning(tmp_path):
    home, clock, founder = body_with_history(tmp_path)
    with Body(home, clock=clock) as body:
        book = body.engine.book
        book.rebuild()
        full = view(book)
        assert book.requests and any(m.actions_done for m in book.missions.values())
        records = list(body.journal.ledger.records)
        cut = next(i for i, r in enumerate(records) if r.record_type == "event"
                   and r.payload.get("type") in ("greg.mission.action", "greg.decision.requested"))
        body.journal.ledger.records = records[:cut]      # an earlier snapshot of the same history
        book.rebuild()
        assert set(book.missions) == {"m:hold", "m:ask"}
        assert book.requests == {} and all(m.actions_done == 0 for m in book.missions.values())
        body.journal.ledger.records = records             # and back
        book.rebuild()
        assert view(book) == full


def test_a_fold_that_stops_part_way_is_redone_from_the_beginning(tmp_path, monkeypatch):
    home, clock, founder = body_with_history(tmp_path, ticks=0)
    with Body(home, clock=clock) as body:
        book, apply = body.engine.book, MissionBook._apply

        def apply_then_fail(self, event):
            apply(self, event)                            # the action is already counted ...
            if self is book and event.type == "greg.mission.action":
                raise RuntimeError("interrupted")         # ... when the fold stops

        monkeypatch.setattr(MissionBook, "_apply", apply_then_fail)
        with pytest.raises(RuntimeError):                 # m:hold registers, writes its note and is
            for _ in range(3):                            # folded at the next rebuild
                body.tick()
                clock.advance(61)
        monkeypatch.setattr(MissionBook, "_apply", apply)
        book.rebuild()                                    # nothing counted twice
        assert book.missions["m:hold"].actions_done == 1
        assert view(book) == view(from_the_beginning(body.journal))


def test_a_rebuild_reads_only_events_retained_since_the_last_one(tmp_path, monkeypatch):
    home, clock, founder = body_with_history(tmp_path, ticks=30)
    with Body(home, clock=clock) as body:
        copied = []
        copy = EventSpine._event_copy
        monkeypatch.setattr(EventSpine, "_event_copy", staticmethod(lambda p: copied.append(p["type"]) or copy(p)))
        copied.clear()
        _original_rebuild(body.engine.book)               # unchecked: the check itself reads everything
        assert copied == []                               # nothing new: nothing read
        book, apply, folded = body.engine.book, MissionBook._apply, []

        def counted(self, event):
            if self is book:                              # not the fresh books the check builds
                folded.append(event.event_id)
            apply(self, event)

        monkeypatch.setattr(MissionBook, "_apply", counted)
        before = [e.event_id for e in body.journal.replay()]
        clock.advance(61)
        body.tick()
        _original_rebuild(book)
        added = [e.event_id for e in body.journal.replay()][len(before):]
        assert folded == added                            # each new event folded once, nothing older
        assert len(before) > 40 and 0 < len(added) < len(before) / 4


def test_since_continues_where_it_stopped_and_restarts_on_other_history(tmp_path):
    home, clock, founder = body_with_history(tmp_path, ticks=6)
    with Body(home, clock=clock) as body:
        spine = body.journal.spine
        everything = [e.event_id for e in spine.replay("greg.")]
        first, cursor, restarted = spine.since("greg.")
        assert restarted and [e.event_id for e in first] == everything
        none, cursor, restarted = spine.since("greg.", cursor)
        assert none == [] and not restarted
        (workspace(home, "m:hold") / "n.txt").write_text("disturbed")
        clock.advance(61)
        body.tick()
        more, cursor2, restarted = spine.since("greg.", cursor)
        assert more and not restarted
        assert [e.event_id for e in first + more] == [e.event_id for e in spine.replay("greg.")]
        only = spine.since("greg.mission.action", cursor)[0]
        assert only and [e.event_id for e in only] == [e.event_id for e in more if e.type == "greg.mission.action"]
        other = EventSpine(body.journal.ledger)           # another view of the same ledger
        again, _, restarted = other.since("greg.", cursor2)
        assert restarted and [e.event_id for e in again] == [e.event_id for e in spine.replay("greg.")]
        mine = first[0]
        mine.payload["mission_id"] = "forged"             # the events are the caller's own
        assert spine.since("greg.")[0][0].payload == spine.replay("greg.")[0].payload != mine.payload


def test_a_journal_that_can_only_replay_is_folded_whole_every_time(tmp_path):
    """Draft #168's gravity builds a book on a stand-in journal that has only replay()."""
    home, clock, founder = body_with_history(tmp_path)
    with Body(home, clock=clock) as body:
        class ReplayOnly:
            def __init__(self, journal):
                self.replay = journal.replay

        book = MissionBook(ReplayOnly(body.journal))
        assert view(book) == view(from_the_beginning(body.journal))
        clock.advance(61)
        body.tick()
        book.rebuild()
        assert view(book) == view(from_the_beginning(body.journal))
