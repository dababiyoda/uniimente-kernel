"""Mission K (founder shutdown) at the real-process tier: a signed BODY_PAUSE holds a running Body.

Directive 2026-10-13 section 33, Mission K: "Suspend, revoke, and terminate within the existing authority
contract. Attempt recovery and replay. Verify that revoked authority is not restored by restart or another
worker." Here the Body is its own OS process (`python -m greg run`). A founder-signed BODY_PAUSE arrives with two
in-cone missions; while paused nothing is dispatched, a BODY_RESUME signed by another key resumes nothing, and a
SIGKILL and restart do not lift the pause. Only the founder's signed BODY_RESUME lets both missions act, once each.

The founder key is a per-test Ed25519 key, not Alfonso's; the intruder key is another per-test key.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from greg.body import Body, observe
from greg.founder import sign_command
from tests.greg_fixtures import drop, make_body, mission, note_check, workspace, write_strategy

ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": str(ROOT)}
MISSIONS = ("m:alpha", "m:beta")


def spec(home: Path, mid: str) -> dict:
    return mission(mid, checks=[note_check("n", workspace(home, mid) / "n.txt", mid)],
                   strategies=[write_strategy("w", "n.txt", mid, ["n"])], capabilities=["fs.read", "fs.write"],
                   targets=("fs:*", "workspace:n.txt"))


def start(home: Path, log: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", "0.1"],
                            cwd=ROOT, env=ENV, stdout=log.open("a"), stderr=subprocess.STDOUT)


def stop(body: subprocess.Popen, sig=signal.SIGTERM) -> None:
    body.send_signal(sig)
    try:
        body.wait(timeout=30)
    except subprocess.TimeoutExpired:
        body.kill()
        body.wait(timeout=10)


def events(home: Path, prefix: str) -> list[dict]:
    with observe(home, actor="spiffe://uniimente.internal/greg/pause-process-test") as journal:
        return [e.payload for e in journal.replay(prefix)]


def wait_for(predicate, *, timeout=90, what="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
        except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError):
            value = None
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {what}")


def acted(home: Path) -> list[dict]:
    return [a for a in events(home, "mission.action") if a["mission_id"] in MISSIONS]


def written(home: Path) -> list[str]:
    return [mid for mid in MISSIONS if (workspace(home, mid) / "n.txt").exists()]


def test_a_signed_pause_holds_a_real_body_across_a_forged_resume_and_a_kill_until_the_founder_resumes(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    log = tmp_path / "body.log"
    drop(home, sign_command(key, "BODY_PAUSE", {"reason": "hold everything"}, body_id=body_id), "a-pause.json")
    for n, mid in enumerate(MISSIONS):
        drop(home, sign_command(key, "MISSION", spec(home, mid), body_id=body_id), f"b{n}-mission.json")

    body = start(home, log)
    try:
        wait_for(lambda: len(events(home, "mission.registered")) == 2 and events(home, "body.paused"),
                 what="the pause and both registrations")
        time.sleep(2.0)                                   # ~20 ticks paused
        assert acted(home) == [] and written(home) == [], "a paused body dispatches nothing"
        intruder = Ed25519PrivateKey.generate()
        drop(home, sign_command(intruder, "BODY_RESUME", {"reason": "forged"}, body_id=body_id), "c-forged.json")
        wait_for(lambda: events(home, "command.rejected"), what="the forged resume's refusal")
        time.sleep(1.0)
        assert events(home, "body.resumed") == [] and acted(home) == [] and written(home) == []
    finally:
        stop(body, signal.SIGKILL)

    body = start(home, log)
    try:
        wait_for(lambda: events(home, "body.recovered"), what="the restart")
        time.sleep(2.0)
        assert acted(home) == [] and written(home) == [], "a restart does not lift a founder pause"
        drop(home, sign_command(key, "BODY_RESUME", {"reason": "carry on"}, body_id=body_id), "d-resume.json")
        wait_for(lambda: len(written(home)) == 2, what="both missions acting after the signed resume")
        wait_for(lambda: len(events(home, "mission.achieved")) == 2, what="both missions closing")
        time.sleep(1.0)
    finally:
        stop(body)

    with Body(home) as b:
        assert b.ledger.verify_chain()[0]
        done = [(a["mission_id"], a["action_id"]) for a in acted(home) if a["status"] == "DONE"]
        assert sorted(done) == [("m:alpha", "w"), ("m:beta", "w")], "each mission acts exactly once"
        assert len(events(home, "body.resumed")) == 1 and len(events(home, "body.paused")) == 1
        [rejected] = events(home, "command.rejected")
        assert rejected["file"] == "c-forged.json" and rejected["instruction_status"] == "data_only"
