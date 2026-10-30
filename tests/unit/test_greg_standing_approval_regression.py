"""A standing approval falls on failure evidence; the earned-autonomy fold reports and never grants (WU-09 part A).

Every test runs a real body in a temporary home with a real (test) founder key: signed MISSION and DECISION commands,
the real mission engine, AuthorityOffice and Gate, and the separate appraiser process. The test key is not Alfonso's.
"""
from __future__ import annotations

import contextlib
import io
import json
import operator
from types import SimpleNamespace

import pytest

from greg import autonomy
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def run(home, clock, ticks=4, step=1.0):
    with Body(home, clock=clock) as body:
        for _ in range(ticks):
            body.tick()
            clock.advance(step)


def events(home, kind):
    with Body(home) as body:
        return [e.payload for e in body.journal.replay(kind)]


def runs(home, mid):
    return [a["action_id"] for a in events(home, "mission.action") if a["mission_id"] == mid and a["status"] == "DONE"]


def open_asks(home):
    with Body(home) as body:
        return [(r["action_id"], r["kind"], r["request_id"]) for r in body.engine.book.open_requests()]


def decide(home, key, body_id, rid, answer="approve"):
    drop(home, signed(key, body_id, "DECISION", {"request_id": rid, "answer": answer, "reason": "test decision"}))


def standing(mid, strategies, ws, capabilities=("fs.read",)):
    """A standing mission whose fs.write strategies lie outside its cone: each one runs only on a founder APPROVAL."""
    return mission(mid, checks=[note_check("c", ws / "c.txt", "ok")], strategies=strategies,
                   capabilities=list(capabilities), closure={"kind": "infinite", "cadence_seconds": 60})


def approve_first_ask(home, key, body_id, clock, action_id):
    asks = [a for a in open_asks(home) if a[0] == action_id and a[1] == "APPROVAL"]
    assert len(asks) == 1, open_asks(home)
    decide(home, key, body_id, asks[0][2])
    run(home, clock)
    return asks[0][2]


def engine_turns(home, clock, kind="mission.held", count=1, limit=10):
    """The engine's own turns, without the body's appraisal, until ``count`` closures of ``kind`` are recorded."""
    with Body(home, clock=clock) as body:
        body.ingest_inbox()
        for _ in range(limit):
            if len(body.journal.replay(kind)) >= count:
                return
            body.engine.tick(clock())
            clock.advance(1)
    raise AssertionError(f"fewer than {count} {kind} after {limit} engine turns")


def ineffective_then_drift(tmp_path):
    """w-bad is approved and runs, but the check it advances still fails; w-good is approved and fixes it; then the
    world drifts. Returns the body, the clock and the approval w-bad ran under."""
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:std")
    drop(home, signed(key, body_id, "MISSION", standing("m:std", [
        write_strategy("w-bad", "c.txt", "wrong", ["c"]), write_strategy("w-good", "c.txt", "ok", ["c"])], ws)))
    clock = Clock()
    run(home, clock)
    first = approve_first_ask(home, key, body_id, clock, "w-bad")
    approve_first_ask(home, key, body_id, clock, "w-good")
    assert runs(home, "m:std") == ["w-bad", "w-good"] and (ws / "c.txt").read_text() == "ok"
    (ws / "c.txt").write_text("damaged")
    clock.advance(61)
    run(home, clock)
    return home, key, body_id, clock, ws, first


def test_an_ineffective_run_regresses_its_standing_approval_and_the_scope_is_asked_again(tmp_path):
    home, key, body_id, clock, ws, first = ineffective_then_drift(tmp_path)
    # fail-before: w-bad ran again here under its standing approval, unasked, though it was proven ineffective
    assert runs(home, "m:std") == ["w-bad", "w-good"], "the regressed scope ran without a fresh founder decision"
    asks = [a for a in open_asks(home) if a[0] == "w-bad" and a[1] == "APPROVAL"]
    assert len(asks) == 1 and asks[0][2] != first          # a fresh ask, not the used approval
    [regressed] = events(home, "autonomy.regressed")
    assert regressed["request_id"] == first and regressed["evidence"]["kind"] == "ineffective"
    assert regressed["tuple"] == {"capability": "fs.write", "action_class": "internal_write",
                                  "target_pattern": "workspace:*", "budget_band": "$0"}
    [withdrawn] = [w for w in events(home, "decision.withdrawn") if w["request_id"] == first]
    assert withdrawn["voids_approval"] is True and "asks again" in withdrawn["why"]
    # w-good's approval was not named by any failure: it still stands
    with Body(home) as body:
        good = [rid for rid, r in body.engine.book.requests.items() if r.get("action_id") == "w-good"]
        assert len(good) == 1 and good[0] not in body.engine.book.withdrawn
        row = level(autonomy.report(body.journal), fs_tuple())
    # the report counts the regression against the run it names, which it already counts as ineffective
    assert row["evidence"]["regressed"] == 1 and row["evidence"]["ineffective"] == 1


def test_ablation_without_the_regression_the_ineffective_scope_runs_unasked(tmp_path, monkeypatch):
    monkeypatch.setattr(autonomy, "regress", lambda journal, book, now: [])
    home, *_ = ineffective_then_drift(tmp_path)
    assert runs(home, "m:std") == ["w-bad", "w-good", "w-bad", "w-good"]   # the defect, reproduced
    assert events(home, "autonomy.regressed") == []


def test_an_approval_given_after_the_regression_stands_until_its_own_run_fails(tmp_path):
    home, key, body_id, clock, ws, first = ineffective_then_drift(tmp_path)
    second = approve_first_ask(home, key, body_id, clock, "w-bad")
    # the fresh approval ran it (old evidence did not void it); it failed again, and w-good, still standing, healed
    assert runs(home, "m:std")[2:] == ["w-bad", "w-good"] and (ws / "c.txt").read_text() == "ok"
    regressions = events(home, "autonomy.regressed")
    assert [r["request_id"] for r in regressions] == [first, second]   # its own run failed again: it falls too
    assert regressions[1]["evidence"]["run"] != regressions[0]["evidence"]["run"]


def refuted_or_verified_hold(tmp_path, *, refute: bool):
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:ref")
    drop(home, signed(key, body_id, "MISSION", standing("m:ref", [write_strategy("w", "c.txt", "ok", ["c"])], ws)))
    clock = Clock()
    run(home, clock, ticks=3)
    [(_, _, rid)] = open_asks(home)
    decide(home, key, body_id, rid)
    with Body(home, clock=clock) as body:      # the engine's own turns: the hold is recorded, not yet appraised
        body.ingest_inbox()
        for _ in range(3):
            body.engine.tick(clock())
            clock.advance(1)
        assert [h["mission_id"] for h in body.journal.replay("mission.held") for h in [h.payload]] == ["m:ref"]
    if refute:
        (ws / "c.txt").write_text("damaged")   # the separate appraiser re-reads the world and refutes the hold
    run(home, clock, ticks=1)
    [appraised] = events(home, "mission.appraised")
    assert appraised["verdict"] == ("REFUTED" if refute else "VERIFIED"), appraised
    if not refute:
        (ws / "c.txt").write_text("damaged")   # drift after a verified hold
    clock.advance(61)
    run(home, clock, ticks=3)
    return home, key, body_id, clock, ws, rid


def test_a_refuted_closure_regresses_the_approval_its_runs_used(tmp_path):
    home, *_, rid = refuted_or_verified_hold(tmp_path, refute=True)
    assert runs(home, "m:ref") == ["w"], "the scope ran again after its closure was refuted, without a fresh decision"
    [regressed] = events(home, "autonomy.regressed")
    assert regressed["request_id"] == rid and regressed["evidence"]["kind"] == "refuted"
    assert [a[0] for a in open_asks(home) if a[1] == "APPROVAL"] == ["w"]


def test_a_verified_hold_keeps_its_standing_approval(tmp_path):
    home, *_ = refuted_or_verified_hold(tmp_path, refute=False)
    assert runs(home, "m:ref") == ["w", "w"]                 # earned: the verified scope heals drift unasked
    assert events(home, "autonomy.regressed") == []


def test_an_approval_given_after_a_refuted_regression_stands_until_its_own_run_fails(tmp_path):
    home, key, body_id, clock, ws, rid = refuted_or_verified_hold(tmp_path, refute=True)
    second = approve_first_ask(home, key, body_id, clock, "w")   # the founder approves again; w heals
    assert runs(home, "m:ref") == ["w", "w"]
    assert [a["verdict"] for a in events(home, "mission.appraised")] == ["REFUTED", "VERIFIED"]
    (ws / "c.txt").write_text("damaged")
    clock.advance(61)
    run(home, clock, ticks=3)
    # the old refutation's window ends at its own closure: it does not reach the run the fresh approval allowed
    assert [r["request_id"] for r in events(home, "autonomy.regressed")] == [rid]
    assert runs(home, "m:ref") == ["w", "w", "w"], open_asks(home)
    with Body(home) as body:
        assert second not in body.engine.book.withdrawn


def test_a_refutation_regresses_only_the_approvals_of_runs_inside_its_closure_window(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:two")
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:two", checks=[note_check("c1", ws / "c1.txt", "ok"), note_check("c2", ws / "c2.txt", "ok")],
        strategies=[write_strategy("w1", "c1.txt", "ok", ["c1"]), write_strategy("w2", "c2.txt", "ok", ["c2"])],
        capabilities=["fs.read"], closure={"kind": "infinite", "cadence_seconds": 60})))
    clock = Clock()
    run(home, clock)
    first = approve_first_ask(home, key, body_id, clock, "w1")
    second = approve_first_ask(home, key, body_id, clock, "w2")
    assert runs(home, "m:two") == ["w1", "w2"]
    assert [a["verdict"] for a in events(home, "mission.appraised")] == ["VERIFIED"]
    (ws / "c2.txt").write_text("damaged")              # drift on c2 alone: w2 heals it under its standing approval
    clock.advance(61)
    engine_turns(home, clock, count=2)
    (ws / "c2.txt").write_text("damaged")              # the appraiser re-reads a changed world: that hold is refuted
    run(home, clock, ticks=2)
    assert [a["verdict"] for a in events(home, "mission.appraised")] == ["VERIFIED", "REFUTED"]
    # the refuted window opened at the verified hold: w1's run lies before it, so only w2's approval falls
    assert [r["request_id"] for r in events(home, "autonomy.regressed")] == [second]
    (ws / "c1.txt").write_text("damaged")
    (ws / "c2.txt").write_text("ok")
    clock.advance(61)
    run(home, clock, ticks=4)
    assert runs(home, "m:two") == ["w1", "w2", "w2", "w1"], open_asks(home)   # w1's approval still stands
    with Body(home) as body:
        assert first not in body.engine.book.withdrawn


def failure_landed_unregressed(tmp_path, monkeypatch):
    """w-bad's approved run is recorded ineffective while the body's hook is off; the hook is then restored."""
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:std")
    drop(home, signed(key, body_id, "MISSION", standing("m:std", [
        write_strategy("w-bad", "c.txt", "wrong", ["c"]), write_strategy("w-good", "c.txt", "ok", ["c"])], ws)))
    clock = Clock()
    regress = autonomy.regress
    monkeypatch.setattr(autonomy, "regress", lambda journal, book, now: [])
    run(home, clock)
    first = approve_first_ask(home, key, body_id, clock, "w-bad")
    assert [o["verdict"] for o in events(home, "routing.outcome")] == ["ineffective"]
    monkeypatch.setattr(autonomy, "regress", regress)
    return home, clock, first


def test_a_run_named_by_two_failures_is_regressed_once(tmp_path, monkeypatch):
    home, clock, first = failure_landed_unregressed(tmp_path, monkeypatch)
    found = autonomy.failures
    monkeypatch.setattr(autonomy, "failures", lambda journal: [
        *found(journal), *({**f, "kind": "refuted", "why": "another account of it"} for f in found(journal))])
    with Body(home, clock=clock) as body:
        assert [r["request_id"] for r in autonomy.regress(body.journal, body.engine.book, clock())] == [first]
    assert [r["evidence"]["kind"] for r in events(home, "autonomy.regressed")] == ["ineffective"]


def test_regression_finishes_after_a_crash_between_its_two_records(tmp_path, monkeypatch):
    home, clock, first = failure_landed_unregressed(tmp_path, monkeypatch)
    with Body(home, clock=clock) as body:
        real = body.journal.record

        def dies_before_withdrawal(kind, data, **kw):
            if kind == "decision.withdrawn":
                raise SystemExit("killed between the regression and its withdrawal")
            return real(kind, data, **kw)
        monkeypatch.setattr(body.journal, "record", dies_before_withdrawal)
        with pytest.raises(SystemExit):
            autonomy.regress(body.journal, body.engine.book, clock())
    clock.advance(30)                                      # a later restart, at a later time
    with Body(home, clock=clock) as body:
        done = autonomy.regress(body.journal, body.engine.book, clock())
        assert [r["request_id"] for r in done] == [first]
        assert first in body.engine.book.withdrawn and autonomy.regress(body.journal, body.engine.book, clock()) == []
    [regressed] = events(home, "autonomy.regressed")
    [withdrawn] = [w for w in events(home, "decision.withdrawn") if w["request_id"] == first]
    assert withdrawn["at"] == regressed["at"]


def fs_tuple():
    return {"capability": "fs.write", "action_class": "internal_write", "target_pattern": "workspace:*",
            "budget_band": "$0"}


def level(report, t):
    [row] = [r for r in report["tuples"] if r["tuple"] == t]
    return row


def test_the_earned_level_climbs_to_supervised_canary_and_no_higher_and_grants_nothing(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home) as body:
        empty = autonomy.report(body.journal)
    assert empty["tuples"] == []
    # one tuple with no evidence: a signed strategy that never runs (its check already passes)
    for n in range(autonomy.CANARY_MIN_VERIFIED):
        ws = workspace(home, f"m:climb{n}")
        drop(home, signed(key, body_id, "MISSION", mission(
            f"m:climb{n}", checks=[note_check("c", ws / "c.txt", "ok")],
            strategies=[write_strategy("w", "c.txt", "ok", ["c"]),
                        write_strategy("never", "d.txt", "ok", ["c"], cost_usd=0.5)],   # ranked after the free one
            capabilities=["fs.read", "fs.write"], budget=1.0)), f"{n}.json")
    run(home, clock, ticks=6)
    assert [a["verdict"] for a in events(home, "mission.appraised")] == ["VERIFIED"] * autonomy.CANARY_MIN_VERIFIED
    with Body(home) as body:
        head = body.ledger.head
        report = autonomy.report(body.journal)
        assert body.ledger.head == head                    # read-only: the fold writes nothing
    row = level(report, fs_tuple())
    assert row["level"] == "SUPERVISED_CANARY" and row["evidence"]["verified"] == autonomy.CANARY_MIN_VERIFIED
    assert row["next_level"] == "BOUNDED_AUTONOMY" and "NEEDS_FOUNDER_DECISION" in row["next_needs"]
    never = level(report, {**fs_tuple(), "budget_band": "up to $1"})
    assert never["level"] == "SHADOW" and never["evidence"]["runs"] == 0
    assert {r["level"] for r in report["tuples"]} <= set(autonomy.LEVELS[:3])   # never above the earned ceiling

    # `greg autonomy` is the same fold, from the journal alone
    from greg import cli
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert cli.main(["--home", str(home), "autonomy"]) == 0
    assert json.loads(out.getvalue()) == json.loads(json.dumps(report))

    # an earned level is not authority: the same tuple outside a new mission's cone still asks the founder
    ws = workspace(home, "m:outside")
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:outside", checks=[note_check("c", ws / "c.txt", "ok")],
        strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read"])), "z-outside.json")
    run(home, clock, ticks=3)
    assert runs(home, "m:outside") == [] and [a[:2] for a in open_asks(home)] == [("w", "APPROVAL")]

    # it falls at once: one refuted closure of the same tuple drops it to SHADOW
    ws = workspace(home, "m:fall")
    drop(home, signed(key, body_id, "MISSION", standing("m:fall", [write_strategy("w", "c.txt", "ok", ["c"])], ws,
                                                        capabilities=("fs.read", "fs.write"))), "z-fall.json")
    with Body(home, clock=clock) as body:
        body.ingest_inbox()
        for _ in range(3):
            body.engine.tick(clock())
            clock.advance(1)
    (ws / "c.txt").write_text("damaged")
    run(home, clock, ticks=1)
    assert events(home, "mission.appraised")[-1]["verdict"] == "REFUTED"
    with Body(home) as body:
        row = level(autonomy.report(body.journal), fs_tuple())
    assert row["level"] == "SHADOW" and row["evidence"]["refuted"] == 1
    assert row["evidence"]["verified_since_last_failure"] == 0


def test_wilson_lower_bound_and_bands():
    assert autonomy.wilson_lower(0, 0) == 0.0
    assert 0.5 < autonomy.wilson_lower(5, 5) < 0.6 and autonomy.wilson_lower(4, 4) > 0.5 > autonomy.wilson_lower(3, 3)
    assert [autonomy.budget_band(c) for c in (0, 0.5, 5, 50, 500)] == ["$0", "up to $1", "up to $10", "up to $100",
                                                                       "over $100"]
    assert autonomy.target_pattern("workspace:c.txt") == "workspace:*" and autonomy.target_pattern("x") == "*"


def five_verified_in_cone_runs(tmp_path):
    """Five bounded in-cone missions whose fs.write run the appraiser verifies: the tuple earns SUPERVISED_CANARY."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    for n in range(autonomy.CANARY_MIN_VERIFIED):
        ws = workspace(home, f"m:climb{n}")
        drop(home, signed(key, body_id, "MISSION", mission(
            f"m:climb{n}", checks=[note_check("c", ws / "c.txt", "ok")],
            strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read", "fs.write"])),
            f"{n}.json")
    run(home, clock, ticks=6)
    assert [a["verdict"] for a in events(home, "mission.appraised")] == ["VERIFIED"] * autonomy.CANARY_MIN_VERIFIED
    with Body(home) as body:
        assert level(autonomy.report(body.journal), fs_tuple())["level"] == "SUPERVISED_CANARY"
    return home, key, body_id, clock


def test_an_ineffective_in_cone_run_drops_the_tuple_to_shadow(tmp_path):
    home, key, body_id, clock = five_verified_in_cone_runs(tmp_path)
    # an in-cone run that executes but leaves its check failing: no approval stands, so nothing is regressed
    ws = workspace(home, "m:bad")
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:bad", checks=[note_check("c", ws / "c.txt", "ok")],
        strategies=[write_strategy("w-bad", "c.txt", "wrong", ["c"])], capabilities=["fs.read", "fs.write"])),
        "z-bad.json")
    run(home, clock, ticks=4)
    assert [o["verdict"] for o in events(home, "routing.outcome")] == ["ineffective"]
    assert events(home, "autonomy.regressed") == []
    with Body(home) as body:
        row = level(autonomy.report(body.journal), fs_tuple())
    assert row["evidence"]["ineffective"] == 1 and row["evidence"]["verified_since_last_failure"] == 0
    assert row["level"] == "SHADOW"


def test_supervised_canary_also_needs_the_wilson_bound_after_earlier_refutations(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    refuted = 3
    for n in range(refuted):                    # bounded in-cone missions whose achievement the appraiser refutes
        ws = workspace(home, f"m:early{n}")
        drop(home, signed(key, body_id, "MISSION", mission(
            f"m:early{n}", checks=[note_check("c", ws / "c.txt", "ok")],
            strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read", "fs.write"])),
            f"a{n}.json")
    engine_turns(home, clock, kind="mission.achieved", count=refuted, limit=12)
    for n in range(refuted):
        (workspace(home, f"m:early{n}") / "c.txt").write_text("damaged")
    run(home, clock, ticks=1)
    assert [a["verdict"] for a in events(home, "mission.appraised")] == ["REFUTED"] * refuted
    for n in range(autonomy.CANARY_MIN_VERIFIED):   # then five verified runs of the same tuple, all after them
        ws = workspace(home, f"m:late{n}")
        drop(home, signed(key, body_id, "MISSION", mission(
            f"m:late{n}", checks=[note_check("c", ws / "c.txt", "ok")],
            strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read", "fs.write"])),
            f"b{n}.json")
    run(home, clock, ticks=6)
    with Body(home) as body:
        row = level(autonomy.report(body.journal), fs_tuple())
    evidence = row["evidence"]
    assert (evidence["refuted"], evidence["verified"]) == (refuted, autonomy.CANARY_MIN_VERIFIED)
    assert evidence["verified_since_last_failure"] == autonomy.CANARY_MIN_VERIFIED       # the count alone would do
    assert evidence["wilson_lower"] == round(autonomy.wilson_lower(5, 8), 4) < autonomy.CANARY_MIN_WILSON
    assert row["level"] == "RECOMMENDER" and "Wilson" in row["next_needs"]


@pytest.mark.parametrize("refuted", ["second", "first"])
def test_runs_are_ordered_by_where_they_ran_not_by_when_their_verdicts_landed(tmp_path, monkeypatch, refuted):
    """A standing in-cone mission runs w and holds twice (no approval stands, so nothing is regressed). The appraiser
    is unavailable once on the first hold, so the second hold's verdict is recorded first; the world at each appraisal
    decides each verdict."""
    home, key, body_id, _ = make_body(tmp_path)
    ws = workspace(home, "m:order")
    drop(home, signed(key, body_id, "MISSION", standing("m:order", [write_strategy("w", "c.txt", "ok", ["c"])], ws,
                                                        capabilities=("fs.read", "fs.write"))))
    clock = Clock()
    engine_turns(home, clock)                      # w runs; the first hold
    (ws / "c.txt").write_text("damaged")
    clock.advance(61)
    engine_turns(home, clock, count=2)             # w runs again; the second hold
    with Body(home) as body:
        first, second = [e.event_id for e in body.journal.replay("mission.held")]
    real, missed = Body.appraise, []

    def unavailable_once(self, mid, *, closure_event=None):
        if closure_event == first and not missed:
            missed.append(closure_event)
            return {"mission_id": mid, "head": self.ledger.head, "verdict": "UNAVAILABLE", "checks": {},
                    "findings": ["the appraiser timed out (test)"], "appraiser": "separate process"}
        return real(self, mid, closure_event=closure_event)
    monkeypatch.setattr(Body, "appraise", unavailable_once)
    (ws / "c.txt").write_text("damaged" if refuted == "second" else "ok")
    run(home, clock, ticks=1)                      # the first hold judges nothing yet; the second is judged
    (ws / "c.txt").write_text("ok" if refuted == "second" else "damaged")
    run(home, clock, ticks=1)                      # the first hold's retry is judged after it
    expected = {"first": "REFUTED" if refuted == "first" else "VERIFIED",
                "second": "REFUTED" if refuted == "second" else "VERIFIED"}
    assert [(a["closure_event"], a["verdict"]) for a in events(home, "mission.appraised")] == [
        (second, expected["second"]), (first, expected["first"])]
    with Body(home) as body:
        row = level(autonomy.report(body.journal), fs_tuple())
    assert (row["evidence"]["verified"], row["evidence"]["refuted"]) == (1, 1)
    if refuted == "second":     # the latest run failed: the earlier verified run, judged later, does not lift it
        assert row["evidence"]["verified_since_last_failure"] == 0 and row["level"] == "SHADOW"
    else:                       # the earlier run failed and the later one verified, whatever order the verdicts landed
        assert row["evidence"]["verified_since_last_failure"] == 1 and row["level"] == "RECOMMENDER"


class Position(int):
    """A ledger position that counts every comparison made with it: the fold's work, measured without a clock."""
    compared = 0

    def _counted(op):
        def compare(self, other):
            Position.compared += 1
            return op(int(self), int(other))
        return compare
    __lt__, __le__, __gt__, __ge__, __eq__, __ne__ = map(_counted, (operator.lt, operator.le, operator.gt,
                                                                    operator.ge, operator.eq, operator.ne))
    __hash__ = int.__hash__
    del _counted


class StandingHistory:
    """A standing mission's history as the engine writes it (its registration, then per heal a run, a hold and that
    hold's appraisal, every other one refuted), read as the fold reads the journal: by kind and by position."""

    def __init__(self, heals: int):
        self.events = []
        self.add("mission.registered", {"mission_id": "m"})
        for n in range(heals):
            self.add("mission.action", {"mission_id": "m", "action_id": "w", "status": "DONE", "receipt": f"r{n}",
                                        "scope_digest": "s"})
            hold = self.add("mission.held", {"mission_id": "m"})
            self.add("mission.appraised", {"mission_id": "m", "closure_event": hold.event_id,
                                           "verdict": "REFUTED" if n % 2 else "VERIFIED"})

    def add(self, kind, payload):
        self.events.append(SimpleNamespace(type="greg." + kind, event_id=f"e{len(self.events)}", payload=payload))
        return self.events[-1]

    def replay(self, kind=""):
        return [e for e in self.events if e.type.startswith("greg." + kind)]

    def positions(self, kind=""):
        return {e.event_id: Position(i) for i, e in enumerate(self.replay(kind))}


def test_the_failure_fold_the_body_runs_every_tick_grows_n_log_n_with_a_standing_history():
    def work(heals):
        Position.compared = 0
        found = autonomy.failures(StandingHistory(heals))
        assert [f["run"].payload["receipt"] for f in found] == [f"r{n}" for n in range(1, heals, 2)]
        return Position.compared
    small, large = work(100), work(400)
    # n log n grows about 5x for four times the history; re-sorting per appraisal or rescanning every run per
    # refuted window grows about 16x or more
    assert large < 8 * small, (small, large)
