"""A self-repair runs once per incident (review of #201, finding DOC-2).

Reproduced on #196 ``e6c5058c``: a signed ``auto_attach`` mission hashed a directory. ``sha256sum`` exited 1 twice,
self-repair quarantined it, re-verified it and re-attached the same binary, and the next fault repaired the same
incident again. Its quarantine key came back with a new ``at`` and ``Journal.record`` raised EventError on that tick
and on every tick after, so the crash-loop breaker held the body and the founder was never asked. A second defect
let a repair fire after one new fault: the streak counted the observation made at the repair's own instant.

In-process Body with a per-test founder key, not Alfonso's (SANDBOX). The stand-in ``sha256sum`` is a shell script
that runs the real binary on files and exits with a chosen code on a directory or a missing path.
"""
from __future__ import annotations

import shutil
import stat

import pytest

from greg import genesis as genesis_mod
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed

REAL = shutil.which("sha256sum", path="/usr/bin:/bin")
pytestmark = pytest.mark.skipif(REAL is None, reason="sha256sum not installed")


def _stand_in(tmp_path, *, directory: int, missing: int):
    """A sha256sum that answers files truly (so it passes Genesis's oracle) and fails on what it cannot read."""
    folder = tmp_path / "bin"
    folder.mkdir()
    script = folder / "sha256sum"
    script.write_text(f'#!/bin/sh\n[ -d "$2" ] && exit {directory}\n[ -e "$2" ] || exit {missing}\n'
                      f'exec {REAL} "$@"\n')
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return str(script)


def _body(tmp_path, monkeypatch, binary):
    monkeypatch.setattr(genesis_mod, "installed_binary", lambda name: binary if name == "sha256sum" else None)
    home, key, body_id, data = make_body(tmp_path)
    target = data / "evidence"
    target.mkdir()
    check = {"check_id": "digest", "description": "evidence digest known",
             "sensor": {"function": "hash.sha256", "params": {"path": str(target)}, "target": "fs:evidence"},
             "predicate": {"op": "equals", "field": "sha256", "value": "0" * 64}}
    spec = mission("m:dir", checks=[check], strategies=[], capabilities=["fs.read", "acquired.hash.sha256.*"],
                   ceiling="read_only", auto_attach=True)
    spec["closure"] = {"kind": "infinite", "cadence_seconds": 60}
    drop(home, signed(key, body_id, "MISSION", spec))
    return home, target


def _ticks(body, clock, n):
    states = []
    for _ in range(n):
        clock.advance(900)
        states.append(body.tick()["missions"][0]["state"])
    return states


def _payloads(body, kind):
    return [e.payload for e in body.journal.replay(kind)]


def test_a_failure_one_repair_did_not_cure_asks_the_founder_and_never_crashes(tmp_path, monkeypatch):
    # The review's trigger, one check. Here the streak fix alone already reaches the founder ask before a second
    # repair can fire, so this test fails only with both fixes removed; the once-per-incident rule is pinned by the
    # two-check test below (independent review of #214, finding 1).
    home, _ = _body(tmp_path, monkeypatch, _stand_in(tmp_path, directory=1, missing=1))
    clock = Clock()
    with Body(home, clock=clock) as body:
        states = _ticks(body, clock, 12)          # raised EventError on the fourth tick before the fix
        assert states.count("REPAIRED") == 1, states
        quarantines = [q for q in _payloads(body, "capability.state") if q["state"] == "QUARANTINED"]
        assert len(quarantines) == 1 and "sha256sum exited 1" in quarantines[0]["why"]
        asks = [r for r in _payloads(body, "decision.requested") if r["mission_id"] == "m:dir"]
        assert [r["kind"] for r in asks] == ["SENSOR_FAILURE"], asks
    with Body(home, clock=clock) as body:          # the record survives a restart: still one repair, no crash
        _ticks(body, clock, 6)
        assert len([q for q in _payloads(body, "capability.state") if q["state"] == "QUARANTINED"]) == 1


def test_a_new_fault_right_after_a_repair_is_not_a_second_strike(tmp_path, monkeypatch):
    home, target = _body(tmp_path, monkeypatch, _stand_in(tmp_path, directory=3, missing=4))
    clock = Clock()
    with Body(home, clock=clock) as body:
        states = []
        while "REPAIRED" not in states and len(states) < 6:
            states += _ticks(body, clock, 1)
        assert states[-1] == "REPAIRED", states
        target.rmdir()                             # the next reading fails differently: exit 4, a new incident
        after = _ticks(body, clock, 1)
        # one new fault plus the pre-repair reading at the repair's instant used to make a streak of two, so the
        # fresh capability was quarantined again on its first reading; now the unmeasured readings reach the founder.
        # The sensor-failure streak counts the earlier readings too, so in this engine a second, different fault is
        # asked about before it could ever be repaired (independent review of #214, finding 2)
        assert after != ["REPAIRED"], after
        whys = [q["why"] for q in _payloads(body, "capability.state") if q["state"] == "QUARANTINED"]
        assert len(whys) == 1 and "exited 3" in whys[0], whys
        asks = [r["kind"] for r in _payloads(body, "decision.requested") if r["mission_id"] == "m:dir"]
        assert asks == ["SENSOR_FAILURE"], asks


def test_beside_a_measured_failure_the_same_incident_is_still_repaired_once(tmp_path, monkeypatch):
    # A second check fails on a real reading, so the unreadable one is not the only failure and the sensor-failure
    # ask never fires: only the once-per-incident rule stops a second repair, whose record the journal refuses.
    binary = _stand_in(tmp_path, directory=1, missing=1)
    monkeypatch.setattr(genesis_mod, "installed_binary", lambda name: binary if name == "sha256sum" else None)
    home, key, body_id, data = make_body(tmp_path)
    target = data / "evidence"
    target.mkdir()
    (data / "notes.txt").write_text("nothing decided yet\n")
    checks = [{"check_id": "digest", "description": "evidence digest known",
               "sensor": {"function": "hash.sha256", "params": {"path": str(target)}, "target": "fs:evidence"},
               "predicate": {"op": "equals", "field": "sha256", "value": "0" * 64}},
              note_check("decided", data / "notes.txt", "decision recorded")]
    spec = mission("m:two", checks=checks, strategies=[], capabilities=["fs.read", "acquired.hash.sha256.*"],
                   ceiling="read_only", auto_attach=True)
    spec["closure"] = {"kind": "infinite", "cadence_seconds": 60}
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        states = _ticks(body, clock, 12)          # raised EventError on the second repair before the fix
        assert states.count("REPAIRED") == 1, states
        assert len([q for q in _payloads(body, "capability.state") if q["state"] == "QUARANTINED"]) == 1
        assert [r for r in _payloads(body, "decision.requested") if r["mission_id"] == "m:two"], states
