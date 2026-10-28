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
        return original(self, m, now, set(failing) | set(self.sensor_errors), evidence, **kw)

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
