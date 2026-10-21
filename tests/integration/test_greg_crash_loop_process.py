"""Acceptance H.G5 at the real-process tier: a Body that dies on every tick holds instead of crash-looping.

The Body runs as its own OS process through the canonical main loop (Body.run, what `greg run` runs), with one
extra read-only sensor capability whose adapter kills the process (os._exit) every time a mission observes it, so
every restart dies inside its first tick, as a supervisor would see it. After CRASH_LOOP_BOOTS such deaths, the
next start holds: the sensor is never called again, the process stays up with a HELD heartbeat, and the hold is
the breaker's record, not a founder command. The founder's signed BODY_RESUME lifts it, and the body acts again
(and dies again: the defect it was holding against is still there).

The founder key is a per-test Ed25519 key, not Alfonso's; the capability is a test double.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from greg.body import BREAKER, CRASH_LOOP_BOOTS, Body, Layout, observe
from tests.greg_fixtures import drop, make_body, mission, signed

ROOT = Path(__file__).resolve().parents[2]

DRIVER = '''
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from greg.body import Body
from greg.capabilities import CapabilityManifest

home, calls = Path(sys.argv[2]), Path(sys.argv[3])
MANIFEST = CapabilityManifest(
    capability_id="test.crashy_sensor", version="1.0.0", provider="test", function="test.crashy_sensor",
    description="kills its process whenever it is observed", route="api", consequence_class="read_only",
    inputs={"probe": "str"}, outputs={"ok": "bool"}, strengthens=("proof",), target_prefix="probe:")


def adapter(params, ctx):
    with calls.open("a") as f:
        f.write(f"{os.getpid()}\\n")
        f.flush()
        os.fsync(f.fileno())
    os._exit(70)                               # the process dies inside its tick: no clean stop is recorded


class TestBody(Body):
    def open(self):
        super().open()
        self.registry.register(MANIFEST, adapter, state="ATTACHED")
        return self


sys.exit(TestBody(home).run(tick_seconds=0.1))
'''


def start(tmp_path: Path, home: Path, calls: Path) -> subprocess.Popen:
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    return subprocess.Popen([sys.executable, str(driver), str(ROOT), str(home), str(calls)], cwd=ROOT,
                            stdout=(tmp_path / "body.log").open("a"), stderr=subprocess.STDOUT,
                            env={**os.environ, "PYTHONPATH": str(ROOT)})


def events(home: Path, prefix: str) -> list[dict]:
    with observe(home, actor="spiffe://uniimente.internal/greg/crash-loop-test") as journal:
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


def n_calls(calls: Path) -> int:
    return len(calls.read_text().splitlines()) if calls.exists() else 0


def test_a_body_that_dies_on_every_tick_holds_after_the_limit_until_the_founder_resumes(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    calls = tmp_path / "calls"
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:crashy", checks=[{"check_id": "ok", "description": "the probe reads ok",
                             "sensor": {"capability": "test.crashy_sensor", "params": {"probe": "x"},
                                        "target": "probe:x"},
                             "predicate": {"op": "equals", "field": "ok", "value": True}}],
        strategies=[{"action_id": "noop", "capability": "fs.read", "params": {"path": str(tmp_path / "data")},
                     "target": "fs:data", "advances": ["ok"], "rationale": "never reached"}],
        capabilities=["fs.read", "test.crashy_sensor"], targets=("fs:*", "probe:*"), ceiling="read_only")))

    for n in range(1, CRASH_LOOP_BOOTS + 1):           # the supervisor restarts it; each life dies in its tick
        body = start(tmp_path, home, calls)
        assert body.wait(timeout=60) == 70, f"life {n} should die inside its tick"
        assert n_calls(calls) == n

    body = start(tmp_path, home, calls)                # the next restart holds
    try:
        wait_for(lambda: [p for p in events(home, "body.paused") if p.get("by") == BREAKER], what="the hold")
        wait_for(lambda: json.loads(Layout(home).heartbeat.read_text())["state"] == "HELD", what="a HELD heartbeat")
        time.sleep(2.0)                                 # ~20 ticks held
        assert body.poll() is None, "a held body stays up and observable"
        assert n_calls(calls) == CRASH_LOOP_BOOTS, "a held body ticks no mission"
        drop(home, signed(key, body_id, "BODY_RESUME", {"reason": "try again"}))
        assert body.wait(timeout=60) == 70, "the signed resume lifts the hold, and the defect is still there"
        assert n_calls(calls) == CRASH_LOOP_BOOTS + 1
    finally:
        if body.poll() is None:
            body.send_signal(signal.SIGKILL)
            body.wait(timeout=20)

    with Body(home) as b:
        assert b.ledger.verify_chain()[0]
        [hold] = [e.payload for e in b.journal.replay("body.paused") if e.payload.get("by") == BREAKER]
        assert len(hold["unfinished_boots"]) == CRASH_LOOP_BOOTS and "command_digest" not in hold
        assert len([e for e in b.journal.replay("body.resumed")]) == 1
        assert len([e for e in b.journal.replay("body.booted") if e.payload.get("main_loop")]) == CRASH_LOOP_BOOTS + 1
