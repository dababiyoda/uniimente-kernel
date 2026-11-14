"""A real body process killed between the Gate's receipt and the mission's record, then a new process.

The unit tests of this behaviour (tests/unit/test_greg_retained_receipt.py, test_greg_retained_receipt_history.py)
close and reopen a Body inside one process, which runs the Body's own shutdown. Here nothing shuts down: a
``greg run`` process is sent SIGKILL by itself at the exact moment it is about to record the action, after the Gate
has written its receipt. A second ``greg run`` process then opens the same home. What it finds is only what reached
the disk.

The kill point is injected by a ``sitecustomize`` module on the child's PYTHONPATH (test code, written into the
test's own directory). It changes no product code: it makes the first attempt to record one kind of fact for this
mission (``mission.action``, or ``mission.compensated``) kill the process, once, and leaves a marker so the restarted
process runs normally.

Each case is also run without the kill. The two must end the same: the same action record, the same Gate records,
the same mission state. The founder key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from greg.body import Body, observe
from tests.greg_fixtures import drop, make_body, mission, note_check, signed, workspace, write_strategy

ROOT = Path(__file__).resolve().parents[2]
MID = "m:killed-process"
REFUSAL = "capability refused: write path 'workspace:elsewhere.txt' does not match the signed target " \
          "'workspace:note.txt'"

INJECTOR = '''
import os, signal
MARK, KIND = os.environ.get("GREG_TEST_KILL_MARK"), os.environ.get("GREG_TEST_KILL_KIND")
if MARK:
    import greg.journal as journal
    real = journal.Journal.record

    def record(self, kind, data, **kw):
        if kind == KIND and data.get("mission_id") == {mid!r} and not os.path.exists(MARK):
            with open(MARK, "w") as mark:
                mark.write(kind)
                mark.flush()
                os.fsync(mark.fileno())
            os.kill(os.getpid(), signal.SIGKILL)      # no shutdown, no flush, no handler: the process is gone
        return real(self, kind, data, **kw)
    journal.Journal.record = record
'''


def start(home: Path, log: Path, inject: Path | None, mark: Path, kind: str = "mission.action") -> subprocess.Popen:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(([str(inject)] if inject else []) + [str(ROOT)]),
           "GREG_FOUNDER_PASSPHRASE": ""}
    if inject:
        env.update(GREG_TEST_KILL_MARK=str(mark), GREG_TEST_KILL_KIND=kind)
    return subprocess.Popen([sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", "0.1"],
                            cwd=ROOT, env=env, stdout=log.open("a"), stderr=subprocess.STDOUT)


def stop(body: subprocess.Popen) -> None:
    body.send_signal(signal.SIGTERM)
    try:
        body.wait(timeout=30)
    except subprocess.TimeoutExpired:
        body.kill()
        body.wait(timeout=10)


def events(home: Path, prefix: str) -> list[dict]:
    with observe(home, actor="spiffe://uniimente.internal/greg/retained-receipt-process-test") as journal:
        return [e.payload for e in journal.replay(prefix) if e.payload.get("mission_id") == MID]


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


def injector(tmp: Path) -> Path:
    inject = tmp / "inject"
    inject.mkdir()
    (inject / "sitecustomize.py").write_text(INJECTOR.format(mid=MID))
    return inject


def kept(home: Path) -> dict:
    """What the home holds once no process has it open: read by a Body that does not tick."""
    with Body(home) as body:
        proposals = {i["proposal_id"] for i in events(home, "mission.dispatching") if i["action_id"] == "w"}
        claims = [r for r in body.ledger.by_type("grant_dispatch") if r.payload["proposal_id"] in proposals]
        grants = {c.payload["grant_id"] for c in claims}
        receipts = [r for r in body.ledger.by_type("receipt") if r.payload["grant_id"] in grants]
        actions = [a for a in events(home, "mission.action") if a["action_id"] == "w"]
        return {"claims": len(claims),
                "receipt_classes": [r.payload["result"]["result_class"] for r in receipts],
                "grants_issued": len([r for r in body.ledger.by_type("event")
                                      if r.payload.get("type") == "greg.authority.grant_issued"
                                      and r.payload.get("proposal_id") in proposals]),
                "actions": [(a["attempt"], a["status"], a["reasons"], a["cost_usd"],
                             [r.hash for r in receipts] == [a["receipt"]]) for a in actions],
                "status": body.engine.book.missions[MID].status,
                "spent_usd": body.engine.book.missions[MID].spent_usd,
                "open_asks": sorted(r["kind"] for r in body.engine.book.open_requests())}


def run(tmp: Path, case: str, kill: bool) -> dict:
    tmp.mkdir()
    home, key, body_id, _ = make_body(tmp)
    note = workspace(home, MID) / "note.txt"
    strategy = write_strategy("w", "note.txt", "draft", ["c"])
    if case == "refused":   # the write names another path than its signed target: fs.write refuses it
        strategy = {**strategy, "params": {"relative_path": "elsewhere.txt", "content": "draft"}}
    drop(home, signed(key, body_id, "MISSION", mission(MID, checks=[note_check("c", note, "draft")],
                                                      strategies=[strategy], capabilities=["fs.read", "fs.write"])))
    log, mark, inject = tmp / "body.log", tmp / "killed.mark", None
    if kill:
        inject = injector(tmp)
        first = start(home, log, inject, mark)
        assert first.wait(timeout=120) == -signal.SIGKILL, log.read_text()[-2000:]
        assert mark.read_text() == "mission.action"
        after_kill = kept(home)
        # the Gate's receipt reached the disk; the mission's record of it did not
        assert after_kill["claims"] == 1 and after_kill["actions"] == []
        assert after_kill["receipt_classes"] == ["negative" if case == "refused" else "positive"]
        assert note.exists() == (case == "done")
    body = start(home, log, inject, mark)                 # a new process on the same home (the marker disarms the kill)
    try:
        wait_for(lambda: [a for a in events(home, "mission.action") if a["action_id"] == "w"], what="the action record")
        if case == "done":
            wait_for(lambda: events(home, "mission.verified") or events(home, "mission.achieved")
                     or [e for e in events(home, "mission.") if e.get("status") == "ACHIEVED"], what="the closure")
        time.sleep(1.5)                                   # more ticks: nothing further may be dispatched for it
    finally:
        stop(body)
    return {**kept(home), "note": note.read_text() if note.exists() else None}


@pytest.mark.parametrize("case", ["refused", "done"])
def test_a_new_process_reads_the_killed_processs_receipt_as_what_it_was(tmp_path, case):
    """Killed after the Gate's receipt and before the action's record. The new process records the action from that
    receipt: a refusal as the refusal it was (same reason, nothing booked, no closure), a completed write as done.
    Nothing is dispatched or granted again, and the end state equals the run that was never killed."""
    control = run(tmp_path / "control", case, kill=False)
    assert control["claims"] == control["grants_issued"] == 1 and len(control["receipt_classes"]) == 1
    if case == "refused":
        assert control["actions"] == [(0, "REFUSED", [REFUSAL], 0.0, True)]
        assert control["receipt_classes"] == ["negative"] and control["note"] is None
        assert control["status"] != "ACHIEVED" and control["spent_usd"] == 0.0
    else:
        assert [(a[0], a[1], a[3], a[4]) for a in control["actions"]] == [(0, "DONE", 0.0, True)]
        assert control["receipt_classes"] == ["positive"] and control["note"] == "draft"
        assert control["status"] == "ACHIEVED"
    killed = run(tmp_path / "killed", case, kill=True)
    if case == "done":     # a reused success says it was reused; everything else is the same record
        assert killed["actions"] == [(0, "DONE", ["retained receipt of a dispatch the body did not record before it "
                                                  "stopped"], 0.0, True)]
        killed, control = ({**r, "actions": [(a[0], a[1], a[3], a[4]) for a in r["actions"]]} for r in (killed, control))
    assert killed == control


# a signed compensation the fs.write adapter refuses: its path does not name its signed target
BROKEN = {"capability": "fs.write", "params": {"relative_path": "other.txt", "content": "original"},
          "target": "workspace:note.txt"}
BROKEN_REASON = "capability refused: write path 'workspace:other.txt' does not match the signed target " \
                "'workspace:note.txt'"


def compensation_run(tmp: Path, kill: bool) -> dict:
    """An executed write whose mission the founder abandons, and whose signed compensation the capability refuses.
    ``kill``: the process is killed after the Gate's negative receipt of that compensation and before the mission
    records it; a new process then opens the home."""
    tmp.mkdir()
    home, key, body_id, _ = make_body(tmp)
    note = workspace(home, MID) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    drop(home, signed(key, body_id, "MISSION", mission(
        MID, checks=[note_check("c", note, "final")],
        strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=BROKEN)],
        capabilities=["fs.read", "fs.write"])))
    log, mark = tmp / "body.log", tmp / "killed.mark"
    inject = injector(tmp) if kill else None
    body = start(home, log, inject, mark, kind="mission.compensated")
    try:
        wait_for(lambda: [a for a in events(home, "mission.action") if a["status"] == "DONE"], what="the write")
        assert note.read_text() == "draft"
        drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": MID, "state": "ABANDONED", "reason": "not wanted"}))
        if kill:
            assert body.wait(timeout=120) == -signal.SIGKILL, log.read_text()[-2000:]
            assert mark.read_text() == "mission.compensated" and events(home, "mission.compensated") == []
            with Body(home) as dead:                      # the Gate kept the capability's refusal; no question yet
                assert [r.payload["result"]["observed_outcome"] for r in dead.ledger.by_type("receipt")
                        if r.payload["result"]["result_class"] == "negative"] == [BROKEN_REASON]
                assert "COMPENSATION" not in [r["kind"] for r in dead.engine.book.open_requests()]
            body = start(home, log, inject, mark, kind="mission.compensated")
        wait_for(lambda: events(home, "mission.compensated"), what="the compensation's record")
        time.sleep(1.5)                                   # more ticks: nothing further may be dispatched for it
    finally:
        stop(body)
    with Body(home) as after:
        return {"compensated": [(c["status"], c["reasons"], after.ledger.find(c["receipt"]).payload["result"][
                    "result_class"]) for c in events(home, "mission.compensated")],
                "asked_about": [(r["action_id"], r["evidence"]["compensation_failed"])
                                for r in after.engine.book.open_requests() if r["kind"] == "COMPENSATION"],
                "negative_receipts": len([r for r in after.ledger.by_type("receipt")
                                          if r.payload["result"]["result_class"] == "negative"]),
                "note": note.read_text(), "status": after.engine.book.missions[MID].status}


def test_a_refused_compensation_killed_before_its_record_still_reaches_the_founder(tmp_path):
    """The reviewer's case, in real processes. Before: the new process recorded the refused compensation DONE over
    the Gate's negative receipt, and the founder was never asked about an effect that was not undone."""
    control = compensation_run(tmp_path / "control", kill=False)
    assert control == {"compensated": [("REFUSED", [BROKEN_REASON], "negative")],
                       "asked_about": [("w", [BROKEN_REASON])], "negative_receipts": 1, "note": "draft",
                       "status": "ABANDONED"}
    killed = compensation_run(tmp_path / "killed", kill=True)
    assert killed["compensated"] != [("DONE", ["retained receipt reused after restart"], "negative")], \
        "a refused compensation is on the record as done"
    assert killed == control
