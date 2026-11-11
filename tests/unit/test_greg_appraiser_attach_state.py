"""The separate appraiser runs nothing in the name of a capability that is not ATTACHED.

Founder directive re-issued 2026-11-04, behaviour B: "Grant revocation is separate: the Kernel must deny affected
execution immediately. Epistemic requalification cannot restore permission." A founder detach has to stop the
capability on every path. The appraiser (greg/appraisal.py) reaches a sensor without the authority office: it
re-reads the world with the sensor's own adapter, with no grant and no receipt. Before this change it never looked
at attach state, so a closure still waiting for its appraisal when the founder detached the sensor (an ordinary
stop or a kill between the closure and its appraisal, an appraisal retried after a run that gave no verdict, an
appraisal asked for on demand) was re-observed by the detached capability. It also re-derived a delivery with the
machinery of a detached delivering capability.

What must hold now:

- a sensor that is not ATTACHED on the ledger the appraiser reads is not run, whatever state it is in;
- the closure is then not VERIFIED (nor VERIFIED_UNMET): the appraisal is recorded UNAVAILABLE, the word the body
  already records when the appraiser judged nothing, with the appraiser's own finding "the world could not be
  re-measured" and the capability and state that stopped it;
- that is not failure evidence: the mission keeps its state, no receipt is touched, autonomy and the corrections
  ledger hear nothing;
- it is recorded once, not every tick, and uses none of the appraiser's retry attempts;
- a later founder re-attach lets the closure be appraised again, once per attach;
- an adapter that is not the one this body holds registered for a reviewed built-in is not run, and neither is a
  sensor that is not read-only.

Every test through ``Body.tick`` runs the real separate appraiser process on the body's own request. The child is
instrumented only to write down which adapters and delivery re-derivations it ran (``COUNTING_CHILD``), because a
call inside another process cannot be counted from here. In-process tests say so. The founder key is a per-test
Ed25519 key, not Alfonso's (SANDBOX).
"""
from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path
import subprocess

import pytest

import greg.appraisal as appraisal
from greg import autonomy, routing
from greg.body import APPRAISAL_ATTEMPTS, Body
from greg.capabilities import BUILTINS
from greg.templates import engineering_brief
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_briefs import github, repo  # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parents[2]
MID = "m:note"

# The body's appraiser child, unchanged except that every built-in adapter and every delivery re-derivation notes
# its own call in a file before it runs. It reads the same request on stdin and prints the same verdict.
COUNTING_CHILD = '''
import importlib, json, sys
import greg.appraisal as appraisal
from greg.capabilities import BUILTINS

LOG = sys.argv[1]


def note(line):
    with open(LOG, "a") as out:
        out.write(line + "\\n")


def counted(cid, real):
    def adapter(params, ctx):
        note("adapter " + cid)
        return real(params, ctx)
    return adapter


for cid, (manifest, adapter) in list(BUILTINS.items()):
    BUILTINS[cid] = (manifest, counted(cid, adapter))
load = importlib.import_module


def counting_load(name, *args, **kwargs):
    module = load(name, *args, **kwargs)
    for cid, owner in appraisal.DELIVERING.items():
        if owner == name and not getattr(module.verify_delivery, "counted", False):
            real = module.verify_delivery

            def verify(*a, _cid=cid, _real=real, **k):
                note("delivery " + _cid)
                return _real(*a, **k)
            verify.counted = True
            module.verify_delivery = verify
    return module


importlib.import_module = counting_load
print(json.dumps(appraisal.appraise(json.loads(sys.stdin.read(1 << 20))), sort_keys=True))
'''


class Child:
    """What the body's appraiser children did: one request per run, and every adapter or delivery they ran."""

    def __init__(self, tmp_path, monkeypatch):
        self.log, self.requests, self.fail_next = tmp_path / "appraiser-ran.log", [], 0
        stub = tmp_path / "counting_appraiser.py"
        stub.write_text(COUNTING_CHILD)
        spawn = subprocess.run

        def run(argv, *args, **kwargs):
            if list(argv[1:]) == ["-m", "greg.appraisal"]:     # the body's appraiser child, and nothing else
                self.requests.append(json.loads(kwargs["input"]))
                if self.fail_next:                              # a run that gives no verdict (killed, crashed)
                    self.fail_next -= 1
                    return subprocess.CompletedProcess(argv, 137, "", "killed")
                argv = [argv[0], str(stub), str(self.log)]
            return spawn(argv, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", run)

    @property
    def ran(self) -> list[str]:
        return self.log.read_text().split("\n")[:-1] if self.log.exists() else []


@pytest.fixture
def child(tmp_path, monkeypatch):
    return Child(tmp_path, monkeypatch)


def facts(body, kind, mid=MID):
    return [e.payload for e in body.journal.replay(kind) if e.payload.get("mission_id") == mid]


def note_mission(tmp_path, *, sensors=("fs.read",)):
    """A real body with one signed mission: write note.txt, then read it back (and, optionally, list its folder)."""
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, MID) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    checks = [note_check("c", note, "final")]
    if "fs.list" in sensors:
        checks.append({"check_id": "listed", "description": "the folder holds the note",
                       "sensor": {"capability": "fs.list", "params": {"path": str(note.parent)}, "target": "fs:folder"},
                       "predicate": {"op": "count_gte", "field": "entries", "value": 1}})
    drop(home, signed(key, body_id, "MISSION", mission(
        MID, checks=checks, strategies=[write_strategy("w", "note.txt", "final", ["c"])],
        capabilities=[*sensors, "fs.write"])))
    return home, key, body_id, note


def close_then_stop(home, clock, *, closure="mission.achieved", mid=MID, ticks=8, step=1.0):
    """Run the mission to its closure and stop the body in that same turn, as ``greg stop --local`` does while the
    engine is stepping: ``Body.tick`` returns before ``_close_out``, so the closure waits for its appraisal."""
    with Body(home, clock=clock) as body:
        engine_tick = body.engine.tick

        def tick_then_stop(now, **kw):
            out = engine_tick(now, **kw)
            if facts(body, closure, mid):
                body.layout.stop_file.touch()
            return out

        body.engine.tick = tick_then_stop
        result = {}
        for _ in range(ticks):
            result = body.tick()
            clock.advance(step)
            if result.get("stopped"):
                break
        assert result.get("stopped") is True
        assert facts(body, closure, mid) and not facts(body, "mission.appraised", mid)
    (Path(home) / "STOP").unlink()                    # the founder starts the body again


def detach(home, key, body_id, cid="fs.read"):
    drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": cid}))


def attach(home, key, body_id, cid="fs.read"):
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))


def change(note, how):
    if how == "changed":
        note.write_text("changed after the detach")
    elif how == "deleted":
        note.unlink()


def not_failure_evidence(body, mid=MID):
    """Nothing reads the appraisal as a failure: the mission's state, its receipts, autonomy, corrections, routing."""
    from greg import corrections
    assert body.engine.book.missions[mid].status == "ACHIEVED"
    assert not facts(body, "mission.unmet", mid)
    assert autonomy.failures(body.journal) == []
    assert not [c for c in corrections.Index(body.journal).causes(body.clock()) if c["class"] == "APPRAISAL_REFUTED"]
    assert all(row["refuted"] == 0 for row in routing.track_record(body.journal).values())


# -- the founder's detach stops the sensor on the appraiser's path too ----------------------------------------------

@pytest.mark.parametrize("how", ["unchanged", "changed", "deleted"])
def test_a_detached_sensor_is_not_run_and_the_closure_is_not_verified(tmp_path, child, how):
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        receipts = len(body.ledger.by_type("receipt"))
        change(note, how)
        body.tick()
        assert body.registry.state["fs.read"] == "DETACHED"
        assert child.ran == [], "the appraiser ran a capability the founder detached"
        [appraised] = facts(body, "mission.appraised")
        # the same answer whatever the world did after the detach: nothing read it
        assert appraised["verdict"] == "UNAVAILABLE"
        assert appraised["checks"]["world_reobserved"] is False
        assert all(appraised["checks"][k] for k in ("founder_signature_verified", "closure_evidence_bound",
                                                    "checks_rederived_from_receipts", "exactly_once"))
        assert appraised["findings"] == ["c: the world could not be re-measured (fs.read is DETACHED; only an "
                                         "ATTACHED capability runs, and the appraiser runs none that is not)"]
        assert appraised["unmeasured_checks"] == ["c"] and list(appraised["not_run"]) == ["fs.read"]
        assert len(body.ledger.by_type("receipt")) == receipts          # no evidence added, changed or removed
        assert not facts(body, "mission.appraisal_unavailable")         # not a failed run: no retry attempt used
        not_failure_evidence(body)
        # the founder reads it where he reads every appraisal: the morning report, with its reason
        from greg.tribunal import morning_report
        [reported] = [a for a in morning_report(body.journal, body.engine)["appraisals"] if a["mission_id"] == MID]
        assert reported["verdict"] == "UNAVAILABLE" and reported["findings"] == appraised["findings"]
    from greg.console import Console
    from greg.mission_control import projection, render_view
    console = Console(home)
    assert [(a["mission_id"], a["verdict"]) for a in projection(console)["appraisals"]] == [(MID, "UNAVAILABLE")]
    assert "UNAVAILABLE" in render_view(console, "proof", {})            # and on Mission Control's Proof view


@pytest.mark.parametrize("how, verdict", [("unchanged", "VERIFIED"), ("changed", "REFUTED")])
def test_an_attached_sensor_is_still_re_run_and_judged(tmp_path, child, how, verdict):
    """Control, on the same route with no detach: the appraiser re-reads the world, as before."""
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    with Body(home, clock=clock) as body:
        change(note, how)
        body.tick()
        assert child.ran == ["adapter fs.read"]
        [appraised] = facts(body, "mission.appraised")
        assert appraised["verdict"] == verdict
        assert "not_run" not in appraised and "unmeasured_checks" not in appraised
        assert appraised["checks"]["world_reobserved"] is (how == "unchanged")


@pytest.mark.parametrize("state", ["QUARANTINED", "VERIFIED", "DISCOVERED"])
def test_a_sensor_in_any_state_but_attached_is_not_run(tmp_path, child, state):
    """Only ATTACHED runs. No production path quarantines a re-observable built-in today (Genesis quarantines what
    it formed, and the appraiser re-runs built-ins only), so the state is recorded here the way Genesis records it."""
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    with Body(home, clock=clock) as body:
        body.journal.record("capability.state", {
            "capability_id": "fs.read", "state": state, "why": "failed in service: test",
            "by": "self-repair (repeated capability fault)"}, key=["fs.read", "test", state])
    with Body(home, clock=clock) as body:
        assert body.registry.state["fs.read"] == state
        note.write_text("changed")
        body.tick()
        assert child.ran == []
        [appraised] = facts(body, "mission.appraised")
        assert appraised["verdict"] == "UNAVAILABLE"
        assert appraised["findings"][0].startswith(f"c: the world could not be re-measured (fs.read is {state}; ")
        not_failure_evidence(body)


def test_a_detach_recorded_by_one_process_stops_the_appraisal_of_the_next(tmp_path, child):
    """Restart between the detach and the appraisal: the body that read the DETACH stopped before it appraised, so
    the next process knows the detach from the ledger alone."""
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        body.engine.tick = lambda now, **kw: (body.layout.stop_file.touch(), [])[1]   # stopped again, mid-turn
        assert body.tick().get("stopped") is True
        assert body.registry.state["fs.read"] == "DETACHED" and not facts(body, "mission.appraised")
    (home / "STOP").unlink()
    with Body(home, clock=clock) as body:
        body.tick()
        assert child.ran == []
        assert [a["verdict"] for a in facts(body, "mission.appraised")] == ["UNAVAILABLE"]


def test_an_appraisal_retried_after_a_run_without_a_verdict_honours_a_detach_in_between(tmp_path, child):
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    child.fail_next = 1
    with Body(home, clock=clock) as body:
        body.tick()                                   # the appraiser was killed: one unavailable attempt
        assert [u["attempt"] for u in facts(body, "mission.appraisal_unavailable")] == [1]
        assert not facts(body, "mission.appraised")
        detach(home, key, body_id)
        clock.advance(1)
        body.tick()                                   # the retry, after the founder's detach
        assert child.ran == []
        [appraised] = facts(body, "mission.appraised")
        assert appraised["verdict"] == "UNAVAILABLE" and list(appraised["not_run"]) == ["fs.read"]
        assert len(facts(body, "mission.appraisal_unavailable")) == 1     # the detach is not a failed run


def test_an_appraisal_asked_for_on_demand_does_not_run_a_detached_sensor(tmp_path, child):
    """``Body.appraise`` outside the tick (greg/rehearsal.py, scripts/verify_one_machine.py call it)."""
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick()
            clock.advance(1)
        assert [a["verdict"] for a in facts(body, "mission.appraised")] == ["VERIFIED"]
        assert child.ran == ["adapter fs.read"]
        detach(home, key, body_id)
        body.tick()
        note.write_text("changed after the detach")
        again = body.appraise(MID)
        assert child.ran == ["adapter fs.read"]                          # nothing ran after the detach
        assert again["verdict"] == "UNAVAILABLE" and list(again["not_run"]) == ["fs.read"]
        assert [a["verdict"] for a in facts(body, "mission.appraised")] == ["VERIFIED"]   # the record stands


def test_a_failure_closure_is_not_certified_on_a_sensor_that_was_not_run(tmp_path, child):
    """VERIFIED_UNMET says the failure still holds in the world. With its sensor detached nothing re-read it."""
    home, key, body_id, data = make_body(tmp_path)
    status = data / "status.txt"
    status.write_text("not yet")
    drop(home, signed(key, body_id, "MISSION", mission(
        MID, checks=[note_check("status", status, "shipped")],
        strategies=[write_strategy("nudge", "nudge.txt", "nudged", ["status"])], capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    close_then_stop(home, clock, closure="mission.unmet", ticks=12, step=600.0)
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        [unmet] = body.journal.replay("mission.unmet")
        body.tick()
        assert child.ran == []
        [appraised] = facts(body, "mission.appraised")
        assert appraised["verdict"] == "UNAVAILABLE" and appraised["closure_event"] == unmet.event_id
        assert appraised["findings"][0].startswith("status: the world could not be re-measured (fs.read is DETACHED")
        # the founder attaches it again: the same closure is appraised a second time, under its own identity
        attach(home, key, body_id)
        clock.advance(1)
        body.tick()
        verdicts = [(a["verdict"], a["closure_event"]) for a in facts(body, "mission.appraised")]
        assert verdicts == [("UNAVAILABLE", unmet.event_id), ("VERIFIED_UNMET", unmet.event_id)]
        assert child.ran == ["adapter fs.read"]


# -- recorded once; appraised again when the founder attaches it again ----------------------------------------------

def test_a_detached_sensor_is_appraised_once_not_every_tick(tmp_path, child):
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        body.tick()
        after_first = len(body.journal.replay("mission."))
        for _ in range(8):
            clock.advance(60)
            body.tick()
        assert len(child.requests) == 1                          # one appraiser process, not one per tick
        assert len(facts(body, "mission.appraised")) == 1 and not facts(body, "mission.appraisal_unavailable")
        assert len(body.journal.replay("mission.")) == after_first   # no mission fact added by the later ticks
    with Body(home, clock=clock) as body:                        # nor by a restart
        for _ in range(3):
            clock.advance(60)
            body.tick()
        assert len(child.requests) == 1 and len(facts(body, "mission.appraised")) == 1
        assert child.ran == []


def test_a_founder_re_attach_lets_the_closure_be_appraised_again(tmp_path, child):
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        body.tick()
        assert [a["verdict"] for a in facts(body, "mission.appraised")] == ["UNAVAILABLE"]
        attach(home, key, body_id)
        clock.advance(1)
        body.tick()
        assert body.registry.state["fs.read"] == "ATTACHED"
        assert child.ran == ["adapter fs.read"]                  # run once, after the attach
        first, second = facts(body, "mission.appraised")
        assert (first["verdict"], second["verdict"]) == ("UNAVAILABLE", "VERIFIED")
        assert "not_run" not in second and second["checks"]["world_reobserved"] is True
        for _ in range(4):                                       # and not again
            clock.advance(60)
            body.tick()
        assert len(child.requests) == 2 and len(facts(body, "mission.appraised")) == 2
        from greg.sop import verified_appraisals
        assert MID in verified_appraisals(body.journal)          # the latest appraisal is the one readers take


def test_a_re_attach_after_a_restart_is_still_appraised(tmp_path, child):
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        body.tick()
    attach(home, key, body_id)
    with Body(home, clock=clock) as body:
        body.tick()
        assert [a["verdict"] for a in facts(body, "mission.appraised")] == ["UNAVAILABLE", "VERIFIED"]


def test_the_re_reading_after_a_re_attach_is_a_real_one(tmp_path, child):
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        body.tick()
        note.write_text("changed while detached")
        attach(home, key, body_id)
        body.tick()
        second = facts(body, "mission.appraised")[-1]
        assert second["verdict"] == "REFUTED"
        assert second["findings"] == ["c: world no longer matches (contains 'final')"]


def test_every_sensor_that_was_not_run_must_be_attached_before_the_closure_is_appraised_again(tmp_path, child):
    home, key, body_id, note = note_mission(tmp_path, sensors=("fs.read", "fs.list"))
    clock = Clock()
    close_then_stop(home, clock)
    detach(home, key, body_id, "fs.read")
    detach(home, key, body_id, "fs.list")
    with Body(home, clock=clock) as body:
        body.tick()
        [first] = facts(body, "mission.appraised")
        assert first["verdict"] == "UNAVAILABLE" and sorted(first["not_run"]) == ["fs.list", "fs.read"]
        assert first["unmeasured_checks"] == ["c", "listed"] and child.ran == []
        attach(home, key, body_id, "fs.read")
        body.tick()
        assert len(child.requests) == 1                          # fs.list is still detached: nothing to re-read
        attach(home, key, body_id, "git.inspect")               # an attach of a capability no closure waits on
        body.tick()
        assert len(child.requests) == 1
        attach(home, key, body_id, "fs.list")
        body.tick()
        assert len(child.requests) == 2 and sorted(child.ran) == ["adapter fs.list", "adapter fs.read"]
        assert facts(body, "mission.appraised")[-1]["verdict"] == "VERIFIED"


def test_a_sensor_that_was_not_run_does_not_hide_what_another_sensor_re_read(tmp_path, child):
    """UNAVAILABLE means nothing else speaks against the closure. Here the attached sensor re-reads a changed world:
    the closure is REFUTED, still says what was not run, and is not appraised again when that is attached."""
    home, key, body_id, note = note_mission(tmp_path, sensors=("fs.read", "fs.list"))
    clock = Clock()
    close_then_stop(home, clock)
    detach(home, key, body_id, "fs.list")
    with Body(home, clock=clock) as body:
        note.write_text("changed")
        body.tick()
        [appraised] = facts(body, "mission.appraised")
        assert appraised["verdict"] == "REFUTED" and child.ran == ["adapter fs.read"]
        assert list(appraised["not_run"]) == ["fs.list"] and appraised["unmeasured_checks"] == ["listed"]
        assert "c: world no longer matches (contains 'final')" in appraised["findings"]
        attach(home, key, body_id, "fs.list")
        clock.advance(1)
        body.tick()
        assert len(child.requests) == 1 and len(facts(body, "mission.appraised")) == 1


def test_an_attach_followed_by_a_detach_before_the_turn_appraises_nothing(tmp_path, child):
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        body.tick()
        drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "fs.read"}), "1-attach.json")
        drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.read"}), "2-detach.json")
        body.tick()
        assert body.registry.state["fs.read"] == "DETACHED"
        assert len(child.requests) == 1 and child.ran == []


def test_an_appraisal_that_ran_nothing_is_repeated_only_by_an_attach_of_what_it_did_not_run(tmp_path, monkeypatch):
    """The appraiser can also refuse a capability that is ATTACHED (the adapter registered under its id is not the
    reviewed built-in). That answer must not be asked for again every tick either. The appraiser's answer is canned
    here; everything the body does with it is real."""
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    asked = []

    def canned(self, mission_id, *, closure_event=None):
        asked.append(mission_id)
        return {"mission_id": mission_id, "head": self.ledger.head, "verdict": "UNAVAILABLE",
                "checks": {"world_reobserved": False}, "unmeasured_checks": ["c"],
                "not_run": {"fs.read": "the adapter registered as fs.read is not the reviewed built-in"},
                "findings": ["c: the world could not be re-measured (not the reviewed built-in)"]}

    monkeypatch.setattr(Body, "appraise", canned)
    with Body(home, clock=clock) as body:
        for _ in range(5):
            body.tick()
            clock.advance(60)
        assert body.registry.state["fs.read"] == "ATTACHED" and len(asked) == 1
        attach(home, key, body_id, "git.inspect")               # not what the appraisal waits on
        body.tick()
        assert len(asked) == 1
        attach(home, key, body_id, "fs.read")                   # the founder attaches it again: one more appraisal
        for _ in range(4):
            clock.advance(60)
            body.tick()
        assert len(asked) == 2 and len(facts(body, "mission.appraised")) == 2


def test_only_the_appraisers_own_answer_counts_as_one_that_ran_nothing():
    """What the body reads from a child's output or a retained appraisal: a non-empty map under UNAVAILABLE."""
    from greg.body import not_run_by_appraiser      # imported here so the file still collects on the base commit
    why = {"fs.read": "fs.read is DETACHED"}
    assert not_run_by_appraiser({"verdict": "UNAVAILABLE", "not_run": why, "findings": ["c: ..."]}) == why
    assert not_run_by_appraiser({"verdict": "REFUTED", "not_run": why, "findings": ["c: ..."]}) == {}
    assert not_run_by_appraiser({"verdict": "UNAVAILABLE", "findings": ["killed"], "attempts": 3}) == {}
    for malformed in (["fs.read"], "fs.read", {}, None, 1):
        assert not_run_by_appraiser({"verdict": "UNAVAILABLE", "not_run": malformed, "findings": []}) == {}
    for no_verdict in (None, [], "UNAVAILABLE", 0):
        assert not_run_by_appraiser(no_verdict) == {}


def test_an_appraisal_whose_attempts_ran_out_is_not_reopened_by_an_attach(tmp_path, child):
    """Acceptance H.G7 is unchanged: UNAVAILABLE after APPRAISAL_ATTEMPTS runs without a verdict is final."""
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    close_then_stop(home, clock)
    child.fail_next = APPRAISAL_ATTEMPTS
    with Body(home, clock=clock) as body:
        for _ in range(APPRAISAL_ATTEMPTS):
            body.tick()
            clock.advance(1)
        [final] = facts(body, "mission.appraised")
        assert final["verdict"] == "UNAVAILABLE" and final["attempts"] == APPRAISAL_ATTEMPTS and "not_run" not in final
        attach(home, key, body_id)
        body.tick()
        assert len(child.requests) == APPRAISAL_ATTEMPTS and len(facts(body, "mission.appraised")) == 1


def test_a_run_without_a_verdict_after_a_re_attach_is_retried_and_bounded(tmp_path, child):
    """The retry bound still holds for the appraisal a re-attach starts, and its final record has its own identity
    (the same closure already holds an appraisal)."""
    home, key, body_id, data = make_body(tmp_path)
    status = data / "status.txt"
    status.write_text("not yet")
    drop(home, signed(key, body_id, "MISSION", mission(
        MID, checks=[note_check("status", status, "shipped")],
        strategies=[write_strategy("nudge", "nudge.txt", "nudged", ["status"])], capabilities=["fs.read", "fs.write"])))
    clock = Clock()
    close_then_stop(home, clock, closure="mission.unmet", ticks=12, step=600.0)
    detach(home, key, body_id)
    with Body(home, clock=clock) as body:
        body.tick()
        attach(home, key, body_id)
        child.fail_next = APPRAISAL_ATTEMPTS
        for _ in range(APPRAISAL_ATTEMPTS + 3):
            clock.advance(1)
            body.tick()
        first, final = facts(body, "mission.appraised")
        assert (first["verdict"], final["verdict"]) == ("UNAVAILABLE", "UNAVAILABLE")
        assert "not_run" in first and "not_run" not in final and final["attempts"] == APPRAISAL_ATTEMPTS
        assert len(child.requests) == 1 + APPRAISAL_ATTEMPTS     # and no run after the bound


# -- a delivery is not re-derived with a detached capability's machinery ---------------------------------------------

def delivered_brief(tmp_path, repo, clock):
    """A body whose engineering brief was delivered and whose closure waits for its appraisal."""
    home, key, body_id, _ = make_body(tmp_path)
    spec = engineering_brief(local={"kernel": str(repo)}, github=["acme/kernel", "acme/organ"])
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home, clock=clock) as body:
        body.boot()
        clock.advance(30)
        body.tick()
        body.engine.book.rebuild()
        [request] = body.engine.book.open_requests()
        drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve"}))
    close_then_stop(home, clock, mid=spec["mission_id"], step=30.0)
    [brief] = sorted((Path(home) / "deliveries" / "briefs").glob("*.md"))
    return home, key, body_id, spec["mission_id"], brief


def test_a_detached_delivering_capability_is_not_re_derived(tmp_path, child, repo, github):  # noqa: F811
    clock = Clock()
    home, key, body_id, mid, _ = delivered_brief(tmp_path, repo, clock)
    detach(home, key, body_id, "brief.engineering")
    with Body(home, clock=clock) as body:
        body.tick()
        assert "delivery brief.engineering" not in child.ran
        assert child.ran == ["adapter brief.freshness"]          # its attached sensor is still re-read
        [appraised] = facts(body, "mission.appraised", mid)
        assert appraised["verdict"] == "UNAVAILABLE"
        assert appraised["checks"]["deliveries_bound_to_evidence"] is False
        assert appraised["checks"]["world_reobserved"] is True
        assert appraised["findings"] == ["deliver-engineering-brief: the delivery could not be re-derived "
                                         "(brief.engineering is DETACHED; only an ATTACHED capability runs, and the "
                                         "appraiser runs none that is not)"]
        assert list(appraised["not_run"]) == ["brief.engineering"] and "unmeasured_checks" not in appraised
        attach(home, key, body_id, "brief.engineering")
        clock.advance(30)
        body.tick()
        assert child.ran == ["adapter brief.freshness", "adapter brief.freshness", "delivery brief.engineering"]
        assert facts(body, "mission.appraised", mid)[-1]["verdict"] == "VERIFIED"


def test_a_sensor_that_was_not_run_does_not_hide_a_delivery_that_fails_its_re_derivation(
        tmp_path, child, repo, github):  # noqa: F811
    clock = Clock()
    home, key, body_id, mid, brief = delivered_brief(tmp_path, repo, clock)
    detach(home, key, body_id, "brief.freshness")
    brief.write_text(brief.read_text() + "\nappended after delivery\n")
    with Body(home, clock=clock) as body:
        body.tick()
        [appraised] = facts(body, "mission.appraised", mid)
        assert child.ran == ["delivery brief.engineering"]
        assert appraised["verdict"] == "REFUTED" and list(appraised["not_run"]) == ["brief.freshness"]
        assert ("deliver-engineering-brief: delivered file differs from the render of the receipted inputs"
                in appraised["findings"])


def test_a_delivery_that_was_not_re_derived_does_not_hide_what_a_sensor_re_read(
        tmp_path, child, repo, github):  # noqa: F811
    clock = Clock()
    home, key, body_id, mid, brief = delivered_brief(tmp_path, repo, clock)
    detach(home, key, body_id, "brief.engineering")
    brief.unlink()
    with Body(home, clock=clock) as body:
        body.tick()
        [appraised] = facts(body, "mission.appraised", mid)
        assert child.ran == ["adapter brief.freshness"]
        assert appraised["verdict"] == "REFUTED" and list(appraised["not_run"]) == ["brief.engineering"]
        assert appraised["checks"]["world_reobserved"] is False


# -- the appraiser's own rule, in this process (no separate child) --------------------------------------------------

def closed_request(tmp_path):
    """A VERIFIED closure and the request the body would hand its appraiser now."""
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick()
            clock.advance(1)
        assert [a["verdict"] for a in facts(body, "mission.appraised")] == ["VERIFIED"]
        return body.appraisal_request(MID)


def spy_on(monkeypatch, cid="fs.read", manifest=None):
    """Count the calls of the built-in adapter the appraiser would re-run."""
    reviewed, real = BUILTINS[cid]
    calls = []

    def adapter(params, ctx):
        calls.append(params)
        return real(params, ctx)

    monkeypatch.setitem(BUILTINS, cid, (manifest or reviewed, adapter))
    return calls


def test_the_spy_sees_the_attached_sensor_run(tmp_path, monkeypatch):
    """Control for the in-process tests below."""
    request = closed_request(tmp_path)
    calls = spy_on(monkeypatch)
    verdict = appraisal.appraise(request)
    assert len(calls) == 1 and verdict["verdict"] == "VERIFIED"


def test_an_adapter_that_is_not_the_registered_one_is_not_run(tmp_path, monkeypatch):
    """The appraiser re-runs a reviewed built-in, and only if that adapter is the one this body holds registered
    under the id. Something else registered there (here a stand-in) is not run, and neither is the built-in."""
    request = closed_request(tmp_path)
    builtin_calls, stand_in_calls = spy_on(monkeypatch), []
    formed = appraisal._formed_registry

    def registry_with_a_stand_in(journal, workspace):
        registry = formed(journal, workspace)
        registry.adapters["fs.read"] = lambda params, ctx: stand_in_calls.append(params) or {"text": "final"}
        return registry

    monkeypatch.setattr(appraisal, "_formed_registry", registry_with_a_stand_in)
    verdict = appraisal.appraise(request)
    assert builtin_calls == [] and stand_in_calls == []
    assert verdict["verdict"] == "UNAVAILABLE" and verdict["checks"]["world_reobserved"] is False
    assert verdict["findings"] == ["c: the world could not be re-measured (the adapter this body holds registered "
                                   "as fs.read is not the reviewed built-in the appraiser re-runs)"]


def test_a_capability_this_body_does_not_hold_registered_is_not_run(tmp_path, monkeypatch):
    request = closed_request(tmp_path)
    calls = spy_on(monkeypatch)
    formed = appraisal._formed_registry

    def registry_without_it(journal, workspace):
        registry = formed(journal, workspace)
        for held in (registry.state, registry.manifests, registry.adapters):
            del held["fs.read"]
        return registry

    monkeypatch.setattr(appraisal, "_formed_registry", registry_without_it)
    verdict = appraisal.appraise(request)
    assert calls == [] and verdict["verdict"] == "UNAVAILABLE"
    assert verdict["findings"] == ["c: the world could not be re-measured (fs.read is not registered on this body; "
                                   "only an ATTACHED capability runs, and the appraiser runs none that is not)"]


def test_a_sensor_that_was_not_run_does_not_hide_a_check_that_fails_on_the_record(tmp_path, monkeypatch):
    """With the sensor detached, a closure whose founder signature does not verify is REFUTED, not UNAVAILABLE."""
    home, key, body_id, note = note_mission(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick()
            clock.advance(1)
        detach(home, key, body_id)
        body.tick()
        request = body.appraisal_request(MID)
    assert appraisal.appraise(request)["verdict"] == "UNAVAILABLE"
    monkeypatch.setattr(appraisal, "_founder_keys", lambda journal, before, ledger: {})
    verdict = appraisal.appraise(request)
    assert verdict["verdict"] == "REFUTED" and verdict["checks"]["founder_signature_verified"] is False
    assert list(verdict["not_run"]) == ["fs.read"]


def test_a_manifest_that_is_not_the_registered_one_is_not_run_either(tmp_path, monkeypatch):
    request = closed_request(tmp_path)
    calls = spy_on(monkeypatch)
    formed = appraisal._formed_registry

    def registry_with_another_manifest(journal, workspace):
        registry = formed(journal, workspace)
        registry.manifests["fs.read"] = dataclasses.replace(registry.manifests["fs.read"], description="another")
        return registry

    monkeypatch.setattr(appraisal, "_formed_registry", registry_with_another_manifest)
    verdict = appraisal.appraise(request)
    assert calls == [] and verdict["verdict"] == "UNAVAILABLE"


def test_a_sensor_that_is_not_read_only_is_never_re_run(tmp_path, monkeypatch):
    """The appraiser re-reads; it does not act. A sensor whose manifest is not read_only is not run, attached or
    not, and the closure is REFUTED as before (its receipt was never a bound observation)."""
    request = closed_request(tmp_path)
    writing = dataclasses.replace(BUILTINS["fs.read"][0], consequence_class="internal_write", retry_safe=False)
    calls = spy_on(monkeypatch, manifest=writing)
    verdict = appraisal.appraise(request)
    assert calls == []
    assert verdict["verdict"] == "REFUTED" and "not_run" not in verdict
    assert ("c: the world could not be re-measured (fs.read is internal_write; the appraiser re-runs read-only "
            "sensors only)") in verdict["findings"]


def test_every_sensor_the_appraiser_would_re_run_is_read_only_by_the_rule_not_by_the_list():
    """``REOBSERVABLE`` names every ``cognition.*`` built-in but three, so it holds ``cognition.settle``, which
    writes. The rule refuses it; nothing depends on the list being curated."""
    from greg.cognition.cortex import registry_view
    registry = registry_view()
    for cid in registry.manifests:
        registry.set_state(cid, "ATTACHED")
    writing = sorted(cid for cid in appraisal.REOBSERVABLE if BUILTINS[cid][0].consequence_class != "read_only")
    assert writing == ["cognition.settle"]
    for cid in sorted(appraisal.REOBSERVABLE):
        refused = appraisal._never_rerun(cid)
        assert (refused is None) == (BUILTINS[cid][0].consequence_class == "read_only")
        assert appraisal._withheld(registry, cid) is None        # attached, and registered as the built-in itself


def test_the_appraiser_calls_an_adapter_in_one_place_behind_the_rule():
    """A new direct adapter call in greg/appraisal.py is a review decision: this fails until it is listed here."""
    tree = ast.parse((ROOT / "greg" / "appraisal.py").read_text())
    sites = []
    for function in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "adapter":
                sites.append(function.name)
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "BUILTINS" \
                    and isinstance(getattr(node, "ctx", None), ast.Load):
                sites.append(f"BUILTINS in {function.name}")
    assert sorted(sites) == ["BUILTINS in _invocation_receipt_bound", "BUILTINS in _manifest_before",
                             "BUILTINS in _never_rerun", "BUILTINS in _withheld", "BUILTINS in appraise", "appraise"]
    source = (ROOT / "greg" / "appraisal.py").read_text()
    assert source.count("verify_delivery(") == 1                 # and one delivery re-derivation
