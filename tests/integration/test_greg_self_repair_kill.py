"""A hard kill in the middle of a self-repair (power loss, OOM): the reopened body finishes the repair once.

The body runs in its own process with a journal hook that SIGKILLs it immediately after one chosen repair fact is
written: after the repair deficit opens, after the replacement is verified, or after it is registered but before it is
attached. In one more case the kill lands in the middle of the next ledger append, leaving half a line on disk.
Nothing is cleaned up; the test process then reopens the same home with a working builder and ticks. The repair must
complete exactly once (no second repair deficit, no duplicate registration of the replacement), the original mission
must hold again, and the ledger chain must verify. Torn bytes are kept in a sidecar file, never discarded.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest

from greg import builders
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_genesis_builder import GOOD
from tests.unit.test_greg_self_repair import BUGGY, _holding

ROOT = Path(__file__).resolve().parents[2]

CRASHING_BODY = r'''
import os, signal, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from greg import builders
from greg.body import Body
from greg.journal import Journal
from tests.greg_fixtures import Clock
from tests.unit.test_greg_genesis_builder import GOOD
from tests.unit.test_greg_self_repair import BUGGY

home, data, point, start = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], datetime.fromisoformat(sys.argv[5])
torn = sys.argv[6] == "torn"
original = Journal.record
repairing = {"on": False}


def record(self, kind, payload, **kw):
    event = original(self, kind, payload, **kw)
    if kind == "deficit.opened" and payload.get("repair"):
        repairing["on"] = True
    if repairing["on"] and kind == point and (point != "capability.state" or payload.get("state") == "REGISTERED"):
        if torn:                                   # the next append was half on disk when the power went
            with open(self.ledger.path, "ab") as fh:
                fh.write(b'{"record_type": "event", "payload": {"kind": "capability.state", "pay')
        os.kill(os.getpid(), signal.SIGKILL)       # power loss: no flush, no close, no cleanup
    return event


Journal.record = record
clock = Clock(start)
body = Body(home, clock=clock, builder=builders.StaticBuilder(BUGGY, BUGGY, GOOD, identity="static-test")).open()
body.boot()
for _ in range(4):
    clock.advance(30)
    body.tick()
doc = data / "FIRST_MISSION.md"
doc.write_text(doc.read_text() + "".join(f"- [x] done step {i} with a longer description\n" for i in range(12)))
for _ in range(8):
    clock.advance(120)
    body.tick()
print("NO_KILL")
'''


@pytest.mark.parametrize("point,torn", [("deficit.opened", False), ("genesis.verified", False),
                                        ("capability.registered", False), ("capability.registered", True)])
def test_a_body_killed_mid_repair_finishes_the_repair_once_after_restart(tmp_path, point, torn):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _holding(data)))
    start = datetime.now(timezone.utc)               # the signed command was issued now; the body clock may not precede it
    crashed = subprocess.run([sys.executable, "-c", CRASHING_BODY, str(ROOT), str(home), str(data), point,
                              start.isoformat(), "torn" if torn else "whole"], cwd=ROOT, capture_output=True, text=True, timeout=300,
                             env={**os.environ, "PYTHONPATH": str(ROOT)})
    assert crashed.returncode == -signal.SIGKILL, crashed.stdout[-2000:] + crashed.stderr[-2000:]

    clock = Clock(start + timedelta(hours=2))
    with Body(home, clock=clock, builder=builders.StaticBuilder(GOOD, GOOD, GOOD, identity="static-test")) as body:
        sidecars = list(Path(body.ledger.path).parent.glob(Path(body.ledger.path).name + ".unacknowledged-*"))
        recovered = [r.payload for r in body.ledger.records if r.record_type == "recovery"]
        repairs_before = [e.payload for e in body.journal.replay("deficit.opened") if e.payload.get("repair")]
        assert len(repairs_before) == 1, repairs_before                 # the kill happened inside the repair
        states = []
        for _ in range(6):
            clock.advance(120)
            states.append(body.tick()["missions"][0]["state"])
        repairs = [e.payload for e in body.journal.replay("deficit.opened") if e.payload.get("repair")]
        resolved = [e.payload for e in body.journal.replay("deficit.resolved")
                    if e.payload["deficit_id"] == repairs[0]["deficit_id"]]
        registered = [e.payload["manifest"]["capability_id"] for e in body.journal.replay("capability.registered")]
        attached = [e.payload for e in body.journal.replay("capability.state") if e.payload["state"] == "ATTACHED"]
        last = [e.payload for e in body.journal.replay("mission.observed")
                if e.payload["check_id"] == "open-items-counted"][-1]
        chain_ok, detail = body.ledger.verify_chain()
        broken = repairs[0]["repair"]["capability_id"]
        replacement = attached[-1]["capability_id"]
        assert body.registry.state[broken] == "QUARANTINED"
        assert body.registry.state[replacement] == "ATTACHED"
    assert len(repairs) == 1, repairs                                      # resumed, not started over
    assert len(resolved) == 1 and resolved[0].get("capability_id") == replacement
    assert len(registered) == len(set(registered)), registered             # nothing registered twice
    assert replacement != broken and attached[-1]["deficit_id"] == repairs[0]["deficit_id"]
    assert states[-1] == "HOLDING" and last["passed"] is True, states
    assert chain_ok, detail
    if torn:                                                               # kept as evidence, not silently dropped
        assert len(sidecars) == 1 and sidecars[0].read_bytes().startswith(b'{"record_type"')
        assert [r["kind"] for r in recovered] == ["unacknowledged_tail_quarantined"]
    else:
        assert not sidecars and not recovered
