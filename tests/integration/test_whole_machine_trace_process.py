"""Mission L at the real-process tier: one mission through all nine links on a running `greg run` Body.

The same founder-signed mission and GOAL as tests/integration/test_whole_machine_trace.py (Goal, Mind, Organs,
Body, Action, Evidence, Outcome, Learning, Updated Goal), but the Body is its own OS process: the founder
approves through `greg decide` (a separate process), evidence after the outcome enters while the Body is stopped
(one ledger writer), and the founder reads the chain with the `greg foundry trace` CLI. The organs are the
stand-ins of tests/unit/test_greg_ventures.py with the real organs' entry points.

The founder key is a per-test Ed25519 key, not Alfonso's.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from egregore.goals import GoalRegistry
from greg import goal_gravity as gg, routing
from greg.body import Body, Layout, ingest_external, observe
from tests.integration.test_whole_machine_trace import WholeWorld
from tests.unit.test_greg_goal_gravity import GOAL, MID, expected_w2_request
from tests.unit.test_greg_ventures import organs  # noqa: F401  (pytest fixture: stand-in organs under data/)

ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": str(ROOT), "GREG_FOUNDER_PASSPHRASE": ""}


def greg(home: Path, *args: str) -> subprocess.CompletedProcess:
    proc = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), *args], cwd=ROOT, env=ENV,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proc


def start(home: Path, log: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", "0.1"],
                            cwd=ROOT, env=ENV, stdout=log.open("a"), stderr=subprocess.STDOUT)


def stop(body: subprocess.Popen) -> None:
    body.send_signal(signal.SIGTERM)
    try:
        body.wait(timeout=30)
    except subprocess.TimeoutExpired:
        body.kill()
        body.wait(timeout=10)


def events(home: Path, prefix: str) -> list[dict]:
    with observe(home, actor="spiffe://uniimente.internal/greg/whole-machine-process-test") as journal:
        return [e.payload for e in journal.replay(prefix)]


def active_node(home: Path, gid: str) -> str | None:
    with observe(home, actor="spiffe://uniimente.internal/greg/whole-machine-process-test") as journal:
        return GoalRegistry(ledger=journal.spine.ledger).state(gid).active_node_id


def wait_for(predicate, *, timeout=120, what="condition"):
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


def done(home: Path) -> dict:
    return {a["action_id"]: a for a in events(home, "mission.action") if a["mission_id"] == MID and a["status"] == "DONE"}


def test_one_mission_runs_all_nine_links_on_a_real_body_process(tmp_path, organs):
    world = WholeWorld(tmp_path, organs)                 # the body home, founder key and the signed specs only
    home, log = world.home, tmp_path / "body.log"
    rid, _ = expected_w2_request(world)
    world.submit("MISSION", world.mission_spec(), "a-mission.json")
    world.submit("GOAL", GOAL(), "b-goal.json")

    body = start(home, log)
    try:
        wait_for(lambda: {"think", "assess", "w"} <= set(done(home)), what="Mind, Organs and the in-cone repair")
        wait_for(lambda: [r for r in events(home, "decision.requested") if r["request_id"] == rid],
                 what="the founder ask for the out-of-cone move")
        greg(home, "decide", rid, "approve", "--reason", "ship it", "--key", str(tmp_path / "founder.pem"),
             "--no-passphrase")
        wait_for(lambda: "w2" in done(home), what="the approved move")
        wait_for(lambda: [a for a in events(home, "mission.appraised")
                          if a["mission_id"] == MID and a["verdict"] == "VERIFIED"], what="the independent appraisal")
    finally:
        stop(body)
    [goal] = [r["goal"] for r in _records(home, GoalRegistry.AUTHORIZED_RECORD)]
    gid = goal["goal_id"]

    ingest_external(home, source="feed://ops", content="check the watch after shipping", channel="ops")
    body = start(home, log)
    try:
        wait_for(lambda: active_node(home, gid) == "n1", what="the goal's recalculated bottleneck")
    finally:
        stop(body)

    actions = done(home)
    assert actions["think"]["capability"] == "cognition.seed.solve"
    assert actions["assess"]["capability"] == "venture.assess"
    assert list((Layout(home).home / "deliveries" / "ventures").glob("venture-*.md"))
    assert (world.ws / "d.txt").read_text() == "shipped"
    with Body(home) as b:
        assert b.ledger.verify_chain()[0]
        assert all(b.ledger.find(a["receipt"]).record_type == "receipt" for a in actions.values())
        assert gg.ledger_closure(b.journal)["ok"]
        knowledge = {r["capability"]: r for r in routing.routing_knowledge(b.journal)}
    for capability in ("cognition.seed.solve", "venture.assess", "fs.write"):
        assert knowledge[capability]["done"] >= 1
    trace = greg(home, "foundry", "trace", "--mission", MID).stdout
    for needle in ("cognition.seed.solve", "venture.assess", "fs.write", rid):
        assert needle in trace


def _records(home: Path, record_type: str) -> list[dict]:
    with observe(home, actor="spiffe://uniimente.internal/greg/whole-machine-process-test") as journal:
        return [r.payload for r in journal.spine.ledger.by_type(record_type)]
