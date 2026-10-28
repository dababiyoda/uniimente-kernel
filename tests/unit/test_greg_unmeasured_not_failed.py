"""A check GREG could not measure is neither pursued nor certified as failed (directive of 2026-10-22, section VI:
no mission predicate may manufacture certainty from incomplete data; review of #196, findings J1 and J2).

The judge calls a check INSUFFICIENT when the evidence its receipt bound cannot decide it. Alone, such a check sends
the mission to SENSOR_RETRY and, after three unmeasured readings, to the founder. Beside another check that truly
fails, it used to ride along with the measured failure:

- the engine dispatched strategies whose only purpose was the unmeasured check;
- the failure closure named it among the checks "re-observed failing";
- the separate appraiser read the undecided receipt, and an undecided re-reading of the world, as proof of that
  failure, and returned VERIFIED_UNMET.

In-process Body with a test clock and a per-test founder key, not Alfonso's (SANDBOX).
"""
from __future__ import annotations

import pytest

import greg.authority
from greg.body import Body
from greg.missions import MissionEngine
from tests.greg_fixtures import Clock, make_body, mission, note_check, write_strategy
from tests.unit.test_greg_missions import events, run, submit

FILLER = "proof settlement notice delivery party shall net due. " * 400       # about 22 KiB
PHRASE = "RECALL NOTICE"
assert PHRASE not in FILLER


@pytest.fixture
def no_whole_kept(monkeypatch):
    """The body's store refuses every whole output, so a check past the receipt's 16 KiB prefix stays unmeasured
    (an output too large to keep behaves the same way)."""
    monkeypatch.setattr(greg.authority, "OUTPUT_ARTIFACT_BYTES", 64)


def _mixed(data, *, strategies):
    page = data / "page.txt"
    page.write_text(FILLER)                          # the phrase is absent, but only past the receipt's prefix
    status = data / "status.txt"
    status.write_text("not yet")                     # a measured failure
    clean = note_check("clean", page, PHRASE)
    clean["predicate"]["op"] = "not_contains"
    return mission("m:mixed", checks=[clean, note_check("status", status, "shipped")], strategies=strategies,
                   capabilities=["fs.read", "fs.write"])


NUDGE = write_strategy("nudge", "nudge.txt", "nudged", ["status"])        # runs, and status still fails
RETRACT = write_strategy("retract", "retraction.txt", "retracted", ["clean"])


def _actions(home):
    return [(e["action_id"], e["status"]) for e in events(home, "mission.action") if e["mission_id"] == "m:mixed"]


def test_an_unmeasured_check_is_not_pursued_beside_a_measured_failure(tmp_path, no_whole_kept):
    home, key, body_id, data = make_body(tmp_path)
    submit(home, key, body_id, "MISSION", _mixed(data, strategies=[NUDGE, RETRACT]))
    run(home, Clock(), ticks=10, step=600.0)
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:mixed"]
    assert any(e["check_id"] == "clean" and e["detail"].startswith("sensor inconclusive") for e in observed)
    actions = _actions(home)
    assert ("nudge", "DONE") in actions
    assert "retract" not in {a for a, _ in actions}          # before: dispatched for a check never measured
    [unmet] = [e for e in events(home, "mission.unmet") if e["mission_id"] == "m:mixed"]
    assert unmet["failing_checks"] == ["status"]              # before: ["clean", "status"]
    [ask] = [r for r in events(home, "decision.requested") if r.get("mission_id") == "m:mixed"]
    assert ask["kind"] == "NO_STRATEGY" and ask["evidence"]["unmeasured_checks"] == ["clean"]
    assert "could not measure clean" in ask["why_now"]
    appraised = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:mixed"]
    assert appraised[-1]["verdict"] == "VERIFIED_UNMET"      # the measured failure is a verified failure


def test_a_strategy_requiring_an_unmeasured_check_stays_held(tmp_path, no_whole_kept):
    """The engine now pursues measured failures only; a precondition still has to be measured passing."""
    home, key, body_id, data = make_body(tmp_path)
    ship = write_strategy("ship", "ship.txt", "shipped", ["status"], requires=["clean"])
    submit(home, key, body_id, "MISSION", _mixed(data, strategies=[ship]))
    run(home, Clock(), ticks=8, step=600.0)
    assert not _actions(home)                                 # never dispatched on an unproven precondition
    [ask] = [r for r in events(home, "decision.requested") if r.get("mission_id") == "m:mixed"]
    assert ask["evidence"]["held_by_precondition"] == {"ship": ["clean"]}
    assert not [e for e in events(home, "mission.unmet") if e["mission_id"] == "m:mixed"]


def test_the_appraiser_does_not_certify_a_failure_its_receipt_cannot_decide(tmp_path, no_whole_kept, monkeypatch):
    """Defence in depth: the appraiser runs in a separate process and does not trust the engine. Driven by an engine
    that still pursues unmeasured checks (the code before this change), the failure closure names `clean`; the
    appraiser must not verify it."""
    original = MissionEngine._pursue

    def pursue_unmeasured_too(self, m, now, failing, evidence, **kw):
        failing = set(failing) | set(self.sensor_errors)
        self.sensor_errors, self.unread = set(), set()       # the closure no longer knows what it did not measure
        return original(self, m, now, failing, evidence, **kw)

    monkeypatch.setattr(MissionEngine, "_pursue", pursue_unmeasured_too)
    home, key, body_id, data = make_body(tmp_path)
    submit(home, key, body_id, "MISSION", _mixed(data, strategies=[NUDGE, RETRACT]))
    run(home, Clock(), ticks=10, step=600.0)
    [unmet] = [e for e in events(home, "mission.unmet") if e["mission_id"] == "m:mixed"]
    assert unmet["failing_checks"] == ["clean", "status"]
    [appraised] = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:mixed"]
    assert appraised["verdict"] == "REFUTED"                  # before: VERIFIED_UNMET
    assert appraised["checks"]["checks_rederived_from_receipts"] is False
    assert any(f.startswith("clean: receipt bytes cannot decide the predicate, so they prove no failure")
               for f in appraised["findings"])


def test_an_undecided_re_reading_of_the_world_is_not_a_reobserved_failure(tmp_path):
    """fs.list keeps at most 1000 entries and says nothing of the rest, so a re-read list at that limit cannot
    decide a count past it. Before, the appraiser read that undecided re-reading as the failure still holding."""
    home, key, body_id, data = make_body(tmp_path)
    folder = data / "drops"
    folder.mkdir()
    many = {"check_id": "many", "description": "at least 1001 drops",
            "sensor": {"capability": "fs.list", "params": {"path": str(folder)}, "target": "fs:drops"},
            "predicate": {"op": "count_gte", "field": "entries", "value": 1001}}
    submit(home, key, body_id, "MISSION", mission(
        "m:many", checks=[many], strategies=[write_strategy("note", "note.txt", "asked", ["many"])],
        capabilities=["fs.list", "fs.write"]))
    clock = Clock()
    run(home, clock, ticks=6, step=600.0)
    appraised = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:many"]
    assert appraised and appraised[-1]["verdict"] == "VERIFIED_UNMET"     # 0 drops: a decided failure
    for i in range(1500):                                     # the world changes past what fs.list can show
        (folder / f"d{i:04}").touch()
    with Body(home, clock=clock) as body:
        [unmet] = [e for e in body.journal.replay("mission.unmet") if e.payload["mission_id"] == "m:many"]
        verdict = body.appraise("m:many", closure_event=unmet.event_id)
    assert verdict["verdict"] == "REFUTED"                    # before: VERIFIED_UNMET
    assert verdict["checks"]["world_reobserved"] is False
    assert any(f.startswith("many: the world could not be re-measured") for f in verdict["findings"])


# -- review of #209: what else the failure closure must not certify -------------------------------------------------

ABSTAIN = {"problem_id": "qualified:game", "operation": "nonexistent_op", "data": {}}


def _abstaining(data):
    status = data / "status.txt"
    status.write_text("not yet")
    q = {"check_id": "q", "description": "game value is 0",
         "sensor": {"capability": "cognition.solve", "target": "cognition:game", "params": ABSTAIN},
         "predicate": {"op": "equals", "field": "output.value", "value": 0}}
    return mission("m:abst", checks=[q, note_check("status", status, "shipped")],
                   strategies=[write_strategy("nudge", "nudge.txt", "nudged", ["status"]),
                               write_strategy("recompute", "q.txt", "again", ["q"])],
                   capabilities=["fs.read", "fs.write", "cognition.solve"],
                   targets=("fs:*", "workspace:*", "cognition:*"))


def test_an_abstaining_sensor_is_pursued_but_never_certified_as_failed(tmp_path):
    """A cognitive receipt that abstained measured nothing. Its cadence is kept (its strategy still runs; the engine
    never blames it), but the failure closure used to name it "re-observed failing", and the appraiser read the
    missing answer as that failure and returned VERIFIED_UNMET (review of #209, E1)."""
    home, key, body_id, data = make_body(tmp_path)
    submit(home, key, body_id, "MISSION", _abstaining(data))
    run(home, Clock(), ticks=10, step=600.0)
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:abst" and e["check_id"] == "q"]
    assert observed and all(e["detail"].startswith("sensor inconclusive") for e in observed)
    assert ("recompute", "DONE") in [(e["action_id"], e["status"]) for e in events(home, "mission.action")
                                     if e["mission_id"] == "m:abst"]                    # cadence unchanged
    [unmet] = [e for e in events(home, "mission.unmet") if e["mission_id"] == "m:abst"]
    assert unmet["failing_checks"] == ["status"] and unmet["unmeasured_checks"] == ["q"]   # before: ["q", "status"]
    [appraised] = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:abst"]
    assert appraised["verdict"] == "VERIFIED_UNMET", appraised["findings"]


def test_the_appraiser_does_not_certify_a_failure_on_an_abstaining_receipt(tmp_path, monkeypatch):
    """Defence in depth: a closure that still names the abstaining check (the engine before this change) is refuted
    by the separate appraiser, whose re-run of the sensor abstains again and is no re-reading of a failure."""
    original = MissionEngine._pursue

    def forget_unread(self, m, now, failing, evidence, **kw):
        self.unread = set()
        return original(self, m, now, failing, evidence, **kw)

    monkeypatch.setattr(MissionEngine, "_pursue", forget_unread)
    home, key, body_id, data = make_body(tmp_path)
    submit(home, key, body_id, "MISSION", _abstaining(data))
    run(home, Clock(), ticks=10, step=600.0)
    [unmet] = [e for e in events(home, "mission.unmet") if e["mission_id"] == "m:abst"]
    assert unmet["failing_checks"] == ["q", "status"]
    [appraised] = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:abst"]
    assert appraised["verdict"] == "REFUTED"                    # before: VERIFIED_UNMET with no findings
    assert any(f.startswith("q: the receipt abstained") for f in appraised["findings"]), appraised["findings"]
    assert any(f.startswith("q: the world could not be re-measured") for f in appraised["findings"])


def test_a_refused_sensor_is_never_named_a_measured_failure(tmp_path):
    """A read the capability refused (here: outside the body's read roots) keeps its route, since a strategy may
    create what it reads, but it is no reading: the closure used to name it "re-observed failing" and the appraiser
    then refuted the whole closure (review of #209, E4)."""
    home, key, body_id, data = make_body(tmp_path)
    status = data / "status.txt"
    status.write_text("not yet")
    outside = tmp_path / "outside.txt"
    outside.write_text("x")
    spec = mission("m:refu", checks=[note_check("r", outside, "y"), note_check("status", status, "shipped")],
                   strategies=[write_strategy("nudge", "nudge.txt", "nudged", ["status"]),
                               write_strategy("maker", "r.txt", "y", ["r"])],
                   capabilities=["fs.read", "fs.write"])
    submit(home, key, body_id, "MISSION", spec)
    run(home, Clock(), ticks=10, step=600.0)
    [unmet] = [e for e in events(home, "mission.unmet") if e["mission_id"] == "m:refu"]
    assert unmet["failing_checks"] == ["status"] and unmet["unmeasured_checks"] == ["r"]
    [appraised] = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:refu"]
    assert appraised["verdict"] == "VERIFIED_UNMET", appraised["findings"]          # before: REFUTED


def test_three_unmeasured_checks_are_one_round_not_three(tmp_path, no_whole_kept):
    """The SENSOR_FAILURE streak counts observation rounds. It used to count readings, so three checks that could
    not be measured asked the founder on the very first observation, with no retry (review of #209, E3)."""
    home, key, body_id, data = make_body(tmp_path)
    page = data / "page.txt"
    page.write_text(FILLER)
    checks = []
    for i in range(3):
        check = note_check(f"u{i}", page, PHRASE + str(i))
        check["predicate"]["op"] = "not_contains"
        checks.append(check)
    submit(home, key, body_id, "MISSION", mission("m:three", checks=checks,
           strategies=[write_strategy("noop", "noop.txt", "x", ["u0"])], capabilities=["fs.read", "fs.write"]))
    clock, states = Clock(), []
    with Body(home, clock=clock) as body:
        for _ in range(4):
            states.append(body.tick()["missions"][0]["state"])
            clock.advance(600.0)
    assert states[:2] == ["SENSOR_RETRY", "SENSOR_RETRY"], states            # before: BLOCKED on the first tick
    assert "BLOCKED" in states[2:], states
    [ask] = [r for r in events(home, "decision.requested") if r.get("mission_id") == "m:three"]
    assert ask["kind"] == "SENSOR_FAILURE"


def test_preparation_holds_a_strategy_whose_precondition_is_observed_failing(tmp_path):
    """While the founder decides, Goal Gravity preparation pursues only the checks the awaited move does not advance,
    but a precondition is judged against the whole observation: a strategy that requires a check this pass saw failing
    is held, as _step would hold it (review of #209, E2)."""
    from tests.unit.test_greg_goal_gravity import MID, World

    class Requiring(World):
        def mission_spec(self, **kw):
            return mission(MID, checks=[note_check("c", self.ws / "c.txt", "ok"),
                                        note_check("d", self.ws / "d.txt", "shipped")],
                           strategies=[write_strategy("w", "c.txt", "ok", ["c"], requires=["d"]),
                                       write_strategy("w2", "d.txt", "shipped", ["d"])],
                           capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"),
                           closure={"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400}, **kw)

    world = Requiring(tmp_path)
    world.start()
    world.tick(6)
    assert world.book().missions[MID].blocker["action_id"] == "w2"       # awaiting the founder's approval for d
    (world.ws / "c.txt").write_text("damaged")
    world.ingest("ops", "c.txt looks broken")
    world.tick(3, step=30.0)
    assert (world.ws / "c.txt").read_text() == "damaged"                  # before: w ran with d failing
