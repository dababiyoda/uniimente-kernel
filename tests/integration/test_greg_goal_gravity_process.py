"""Mission F (Goal Gravity) at the real-process tier: a founder-signed GOAL on a running `greg run` Body.

Directive 2026-10-13 section 33, Mission F: "A dormant goal is awakened by relevant evidence. GREG recognizes
the change, recalculates the active bottleneck, performs permitted preparation, and presents only the
consequential decision needing Alfonso. The system must distinguish a meaningful trigger from irrelevant noise."

The in-process proof is tests/unit/test_greg_goal_gravity.py::test_mission_F_end_to_end. Here the Body is its own
OS process (`python -m greg run`, exactly what the supervisor runs), killed with SIGKILL and restarted, and the
founder answers through `greg decide` in a separate process. External evidence enters while the Body is stopped,
because the ledger has one writer (greg.body.ingest_external); a running Body learns of the world only through
its own sensors.

The founder key is a per-test Ed25519 key, not Alfonso's. Passing proves the mechanism on this tree at the
BODY tier; it is not founder acceptance or evidence of any external effect.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from egregore.attention import ANSWER_RECORD, ASK_RECORD
from egregore.goals import GoalRegistry
from egregore.gravity import GoalGravityLoop
from greg import goal_gravity as gg
from greg.authority import AuthorityOffice
from greg.body import Body, ingest_external, observe
from greg.founder import sign_command
from provenance.ledger import sha256_json
from tests.greg_fixtures import drop, make_body, mission, note_check, workspace, write_strategy
from tests.unit.test_greg_goal_gravity import GOAL, MID

ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": str(ROOT), "GREG_FOUNDER_PASSPHRASE": ""}


def mission_spec(ws: Path) -> dict:
    return mission(MID, checks=[note_check("c", ws / "c.txt", "ok"), note_check("d", ws / "d.txt", "shipped")],
                   strategies=[write_strategy("w", "c.txt", "ok", ["c"]), write_strategy("w2", "d.txt", "shipped", ["d"])],
                   capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"),
                   closure={"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400})


def w2_request(ws: Path) -> str:
    s = next(s for s in mission_spec(ws)["strategies"] if s["action_id"] == "w2")
    scope = AuthorityOffice.scope_digest(mission_id=MID, capability_id="fs.write", params=s["params"],
                                         target=s["target"], consequence_class="internal_write", cost_usd=0.0)
    return "req-" + sha256_json({"mission": MID, "kind": "APPROVAL", "scope": scope})[7:31]


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
    with observe(home, actor="spiffe://uniimente.internal/greg/goal-process-test") as journal:
        return [e.payload for e in journal.replay(prefix)]


def records(home: Path, record_type: str) -> list[dict]:
    with observe(home, actor="spiffe://uniimente.internal/greg/goal-process-test") as journal:
        return [r.payload for r in journal.spine.ledger.by_type(record_type)]


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


def pulls(home: Path) -> int:
    return len([e for e in events(home, "mission.schedule") if e.get("mission_id") == MID and "cause" in e])


def w2_asks(home: Path) -> list[str]:
    return [r["request_id"] for r in events(home, "decision.requested") if r.get("action_id") == "w2"]


def test_a_goal_on_a_real_body_process_wakes_on_meaning_not_noise_and_asks_once_across_a_kill(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    ws, log = workspace(home, MID), tmp_path / "body.log"
    rid = w2_request(ws)
    drop(home, sign_command(key, "MISSION", mission_spec(ws), body_id=body_id), "a-mission.json")
    drop(home, sign_command(key, "GOAL", GOAL(), body_id=body_id), "b-goal.json")

    body = start(home, log)
    try:
        # Permitted preparation inside the cone, through the Gate; one ask for the consequential out-of-cone move.
        wait_for(lambda: (ws / "c.txt").read_text() == "ok", what="the in-cone repair")
        wait_for(lambda: w2_asks(home), what="the founder ask for d")
        [goal] = [r["goal"] for r in records(home, GoalRegistry.AUTHORIZED_RECORD)]
    finally:
        stop(body, signal.SIGKILL)                       # an abrupt death, not a clean stop

    body = start(home, log)
    try:
        wait_for(lambda: len(events(home, "body.recovered")) >= 1, what="the restart")
        time.sleep(2.0)                                  # ~20 ticks after the kill with the ask still open
        assert w2_asks(home) == [rid], "the restart asks nothing new"
        assert not (ws / "d.txt").exists(), "the awaited move never runs before the signed approve"
        decide = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "decide", rid, "approve",
                                 "--reason", "ship it", "--key", str(tmp_path / "founder.pem"), "--no-passphrase"],
                                cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=60)
        assert decide.returncode == 0, decide.stderr[-2000:]
        wait_for(lambda: (ws / "d.txt").read_text() == "shipped", what="the approved move")
        time.sleep(1.0)
    finally:
        stop(body)

    # Evidence arrives while the Body is stopped (one ledger writer): first noise, then meaning.
    (ws / "c.txt").write_text("damaged")
    before = pulls(home)
    ingest_external(home, source="feed://weather", content="sunny tomorrow", channel="weather")
    body = start(home, log)
    try:
        wait_for(lambda: len(events(home, "body.booted")) >= 3, what="the second restart")
        time.sleep(2.0)
        assert pulls(home) == before and (ws / "c.txt").read_text() == "damaged", "noise wakes nothing"
    finally:
        stop(body)
    ingest_external(home, source="feed://ops", content="c.txt looks broken", channel="ops")
    body = start(home, log)
    try:
        wait_for(lambda: (ws / "c.txt").read_text() == "ok", what="the repair the relevant evidence pulled")
        assert pulls(home) > before
    finally:
        stop(body)

    with Body(home) as b:                                # the Body is stopped: one writer again
        assert b.ledger.verify_chain()[0]
        actions = [e.payload for e in b.journal.replay("mission.action") if e.payload["mission_id"] == MID]
        assert len([a for a in actions if a["action_id"] == "w2" and a["status"] == "DONE"]) == 1
        assert w2_asks(home) == [rid], "exactly one founder ask across two kills, two stops and an approval"
        assert b.ledger.by_type(ASK_RECORD) == [] and b.ledger.by_type(ANSWER_RECORD) == []   # no side channel
        assert all(r.payload["turn"]["executed"] == [] for r in b.ledger.by_type(GoalGravityLoop.TURN_RECORD))
        closure = gg.ledger_closure(b.journal)
        assert closure["ok"], closure
        assert not b.journal.replay("goal_gravity.fault")
        assert GoalRegistry(ledger=b.ledger).state(goal["goal_id"]).active_node_id == "n1"   # recalculated
