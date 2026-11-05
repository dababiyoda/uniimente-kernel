"""Directive 2026-10-28 section 38 (S38-A): a long worker must not freeze every other mission.

The Body's main loop (Body.run, what `greg run` runs) commissioned a worker inside its turn: AuthorityOffice.act called
the provider and waited for it, so every other mission, the inbox and the heartbeat stopped for as long as the worker
ran. Here the main loop runs in a thread with a real clock. Mission A commissions a worker (a scripted test double that
holds until the test releases it); mission B is an ordinary internal write. B must close while A's worker still holds,
and A's outcome is recorded exactly once after it is released.

The founder key is a per-test Ed25519 key, not Alfonso's; the worker is a scripted test double, not a frontier worker.
"""
from __future__ import annotations

import threading
import time

import pytest

from greg import templates, workers
from greg.background import Background
from greg.body import Body, Layout, observe
from tests.greg_fixtures import drop, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_workers import GOOD, ScriptedWorker, acceptance_envelope, make_repo  # noqa: F401

WAIT = 30


class HoldingWorker(ScriptedWorker):
    """Applies its edits, then holds until the test releases it (a worker that runs for minutes)."""

    def __init__(self, edits):
        super().__init__(edits)
        self.holding, self.release = threading.Event(), threading.Event()

    def run(self, order, cwd):
        self.holding.set()
        if not self.release.wait(WAIT):
            raise AssertionError("the test never released the worker")
        return super().run(order, cwd)


def wait_for(predicate, what: str, timeout: float = WAIT):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    pytest.fail(f"timed out waiting for {what}")


def missions_ready(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    worker = HoldingWorker(GOOD)
    monkeypatch.setitem(workers.PROVIDERS, "scripted", worker)
    long = templates.code_change(repo=str(repo), objective="add sub()", order="add-sub", provider="scripted",
                                 allowed_paths=["pkg/*", "tests/*"], budget_usd=1.0,
                                 workspace_root=Layout(home).workspace)
    long["priority"] = 10                                   # stepped first: its worker is dispatched first
    note = workspace(home, "m:quick") / "c.txt"
    quick = mission("m:quick", checks=[note_check("c", note, "ok")],
                    strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read", "fs.write"])
    drop(home, signed(key, body_id, "MISSION", long))
    drop(home, signed(key, body_id, "MISSION", quick))
    return home, worker, long["mission_id"]


def facts(home):
    with observe(home, actor="spiffe://uniimente.internal/test/background") as journal:
        return {"achieved": [e.payload["mission_id"] for e in journal.replay("mission.achieved")],
                "commissions": [e.payload for e in journal.replay("mission.action")
                                if e.payload.get("capability") == "worker.commission"],
                "chain": journal.ledger.verify_chain()[0]}


def test_a_long_worker_does_not_freeze_the_other_missions(tmp_path, monkeypatch):
    home, worker, long_id = missions_ready(tmp_path, monkeypatch)
    body = Body(home)
    loop = threading.Thread(target=body.run, kwargs={"tick_seconds": 0.05}, daemon=True)
    loop.start()
    try:
        worker.holding.wait(WAIT)
        assert worker.holding.is_set(), "the worker was never commissioned"
        # The worker holds: the quick mission is stepped, written and observed meanwhile.
        wait_for(lambda: "m:quick" in facts(home)["achieved"], "the quick mission to close while the worker holds")
        assert facts(home)["commissions"] == [], "nothing is recorded for a dispatch that is still running"
        beat = Layout(home).heartbeat.read_text()
        assert '"WORKING"' in beat and long_id in beat, "the heartbeat names the mission whose worker runs"
        worker.release.set()
        wait_for(lambda: long_id in facts(home)["achieved"], "the long mission to close after its worker returns")
    finally:
        worker.release.set()
        body.stop_requested = True
        loop.join(WAIT)
    seen = facts(home)
    assert not loop.is_alive() and worker.calls == 1
    assert [c["status"] for c in seen["commissions"]] == ["DONE"], "recorded once, after it returned"
    assert seen["chain"]


def test_an_error_after_the_hand_off_kills_the_next_turn_as_it_did_inline(tmp_path, monkeypatch):
    """A background dispatch that fails while recording its outcome is not swallowed: the next turn raises it, so the
    process dies and the supervisor's crash breaker counts it; the write-ahead intent stays for the restart."""
    home, worker, long_id = missions_ready(tmp_path, monkeypatch)
    with Body(home) as body:
        body.engine.background = Background(body._turn, clock=body.clock, stop_check=body._stop_flag)
        original = body.engine._record_outcome

        def fails(m, *args, **kwargs):
            if m.mission_id == long_id:
                raise RuntimeError("recording failed")
            return original(m, *args, **kwargs)
        monkeypatch.setattr(body.engine, "_record_outcome", fails)
        worker.release.set()
        body.tick()                                      # dispatches; the scripted worker returns at once
        wait_for(lambda: long_id not in body.engine.background.running, "the dispatch to end")
        with pytest.raises(RuntimeError, match="recording failed"):
            body.tick()
        intents = [e.payload for e in body.journal.replay("mission.dispatching") if e.payload["mission_id"] == long_id]
        assert intents and facts_in(body)["commissions"] == []


def facts_in(body):
    return {"commissions": [e.payload for e in body.journal.replay("mission.action")
                            if e.payload.get("capability") == "worker.commission"]}
