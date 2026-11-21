"""Real SIGKILL inside torn-tail recovery: no state in which the ledger opens without its recovery event.

The second adversarial review of provenance/recovery.py (crash:0) killed a recovery after its in-place truncation
and before its event, and a restarting body appended onto the unrecorded truncation. Recovery now writes its plan
durably, then applies it in place so the file ends with a newline only once the event is durable. These tests
SIGKILL a real child at each durable step of that application and at a point inside the event write.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys

import pytest

from provenance.ledger import EvidenceLedger
from provenance.recovery import EVENT_TYPE, recover_torn_tail

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ANCHOR = "sha256:" + "a" * 64

CHILD = r'''
import os, signal, sys
sys.path.insert(0, {root!r})
import provenance.recovery as recovery
point = {point!r}
seen = {{"fsync": 0, "pwrite": 0}}
real_fsync, real_pwrite = os.fsync, os.pwrite

def fsync(fd):
    real_fsync(fd)
    seen["fsync"] += 1
    if point.startswith("fsync") and seen["fsync"] == int(point[5:]):
        os.kill(os.getpid(), signal.SIGKILL)

def pwrite(fd, data, offset):
    seen["pwrite"] += 1
    if point == "inside_event_write" and seen["pwrite"] == 1:
        real_pwrite(fd, data[: len(data) // 2], offset)
        os.kill(os.getpid(), signal.SIGKILL)
    return real_pwrite(fd, data, offset)

real_apply = recovery._apply

def apply(path, cut, line):
    os.fsync, os.pwrite = fsync, pwrite   # only the application of the plan is instrumented
    real_apply(path, cut, line)

recovery._apply = apply
recovery.recover_torn_tail({path!r}, {anchor!r}, recovered_by="supervisor:A", reason="body died",
                           acknowledged_risks=("unanchored",))
print("COMPLETED")
'''


def _torn_ledger(tmp_path, n=200):
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(ANCHOR, path=path)
    for i in range(n):
        ledger.append("event", {"type": "probe", "n": i})
    probe = ledger.append("grant_dispatch", {"proposal_id": "P", "grant_id": "G"})
    ledger.close()
    with open(path, "rb") as fh:
        data = fh.read()
    body, line = data[:-1].rsplit(b"\n", 1)
    with open(path, "wb") as fh:
        fh.write(body + b"\n" + line[: len(line) // 2])
    return path, probe


@pytest.mark.parametrize("point", ["inside_event_write", "fsync1", "fsync2", "fsync3"])
def test_sigkill_while_applying_the_recovery_never_lets_a_writer_append_before_its_event(tmp_path, point):
    path, probe = _torn_ledger(tmp_path)
    child = subprocess.run([sys.executable, "-c", CHILD.format(root=ROOT, point=point, path=path, anchor=ANCHOR)],
                           cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert child.returncode == -signal.SIGKILL, (child.returncode, child.stdout, child.stderr[-2000:])
    if point != "fsync3":
        with pytest.raises(ValueError):
            EvidenceLedger(ANCHOR, path=path)   # a restarting body cannot open it, so it cannot append
        out = recover_torn_tail(path, ANCHOR, recovered_by="supervisor:B", reason="restart after the kill",
                                acknowledged_risks=("unanchored",))
        assert out["torn"] and out["resumed"]
        assert (out["quarantined"]["recovered_by"], out["quarantined"]["completed_by"]) == ("supervisor:A",
                                                                                          "supervisor:B")
    ledger = EvidenceLedger(ANCHOR, path=path)   # after fsync3 the event is durable: the body opens directly
    events = [r for r in ledger.by_type("event") if r.payload.get("type") == EVENT_TYPE]
    assert len(events) == 1 and events[0].payload["recovered_by"] == "supervisor:A"
    assert ledger.find(probe.hash) is None and ledger.records[-1] is not None
    ledger.append("event", {"type": "body.restarted"})
    ledger.close()
    assert recover_torn_tail(path, ANCHOR, recovered_by="supervisor:C", reason="routine",
                             acknowledged_risks=("unanchored",))["torn"] is False
