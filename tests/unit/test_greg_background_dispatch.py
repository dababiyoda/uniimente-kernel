"""Directive 2026-10-28 section 38 (S38-A): a long worker must not freeze every other mission.

The Body's main loop (Body.run, what `greg run` runs) commissioned a worker inside its turn: AuthorityOffice.act called
the provider and waited for it, so every other mission, the inbox and the heartbeat stopped for as long as the worker
ran. Here the main loop runs in a thread with a real clock. Mission A commissions a worker (a scripted test double that
holds until the test releases it); mission B is an ordinary internal write. B must close while A's worker still holds,
and A's outcome is recorded exactly once after it is released.

The founder key is a per-test Ed25519 key, not Alfonso's; the worker is a scripted test double, not a frontier worker.
"""
from __future__ import annotations

import os
import sys
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


class GatedLock:
    """The Body's turn lock, except that the test's own thread can be made to wait at one acquire: it lets a test
    decide which thread takes the turn lock next, instead of leaving it to the scheduler."""

    def __init__(self):
        self._lock, self.gate, self.owner = threading.Lock(), None, threading.get_ident()

    def acquire(self, *args, **kwargs):
        gate = self.gate
        if gate is not None and threading.get_ident() == self.owner:
            assert gate.wait(WAIT), "the gate never opened"
        return self._lock.acquire(*args, **kwargs)

    def release(self):
        self._lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()


def worker_mission(home, repo, order, provider, priority):
    spec = templates.code_change(repo=str(repo), objective="add sub()", order=order, provider=provider,
                                 allowed_paths=["pkg/*", "tests/*"], budget_usd=1.0,
                                 workspace_root=Layout(home).workspace)
    spec["priority"] = priority
    return spec


def test_a_mission_stepped_after_its_own_background_outcome_landed_mid_turn_reads_the_recorded_state(
        tmp_path, monkeypatch):
    """Integrator intake review of #273, item 1. The turn sorts the missions once, then steps them in order; while it
    hands mission A's worker off, mission B's earlier dispatch can record its outcome (and rebuild the book) on its
    own thread. B is then no longer busy and is stepped in the same turn: it must be stepped from the state the
    ledger now holds (its commission recorded, its spend booked), not from the copy taken before that record."""
    data = tmp_path / "data"
    (data / "a").mkdir(parents=True)
    (data / "b").mkdir()
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    a_worker, b_worker = HoldingWorker(GOOD), HoldingWorker(GOOD)
    b_worker.release = a_worker.holding          # B's worker returns the moment A's worker starts
    monkeypatch.setitem(workers.PROVIDERS, "scripted-a", a_worker)
    monkeypatch.setitem(workers.PROVIDERS, "scripted-b", b_worker)
    a = worker_mission(home, make_repo(data / "a"), "add-sub-a", "scripted-a", 10)
    b = worker_mission(home, make_repo(data / "b"), "add-sub-b", "scripted-b", 0)
    with Body(home) as body:
        body._turn = turn = GatedLock()
        body.engine.background = background = Background(turn, clock=body.clock, stop_check=body._stop_flag)
        b_recorded = threading.Event()
        original = body.engine._record_outcome

        def records(m, *args, **kwargs):
            out = original(m, *args, **kwargs)
            if m.mission_id == b["mission_id"]:
                b_recorded.set()
            return out
        monkeypatch.setattr(body.engine, "_record_outcome", records)
        dispatch = background.dispatch

        def gated(mission_id, *args, **kwargs):
            # While A's worker is handed off, the turn waits for B's outcome to be recorded on B's thread first.
            turn.gate = b_recorded if mission_id == a["mission_id"] else None
            try:
                return dispatch(mission_id, *args, **kwargs)
            finally:
                turn.gate = None
        monkeypatch.setattr(background, "dispatch", gated)
        admitted, act = [], body.engine.office.act

        def admits(**kwargs):
            admitted.append((kwargs["mission_id"], kwargs["manifest"].capability_id, kwargs["spent_usd"]))
            return act(**kwargs)
        monkeypatch.setattr(body.engine.office, "act", admits)
        stepped_from, step = [], body.engine._step

        def steps(m, now):
            # What the ledger holds for this mission's spend when it is stepped (no dispatch here is unreconciled).
            booked = round(sum(float(e.payload.get("cost_usd") or 0.0) for e in body.journal.replay("mission.action")
                               if e.payload.get("mission_id") == m.mission_id), 9)
            stepped_from.append((m.mission_id, m.committed_usd, booked, abs(m.committed_usd - booked) < 1e-9))
            return step(m, now)
        monkeypatch.setattr(body.engine, "_step", steps)

        drop(home, signed(key, body_id, "MISSION", b))
        body.tick()
        assert b_worker.holding.wait(WAIT), "B's worker was never commissioned"
        drop(home, signed(key, body_id, "MISSION", a))
        turn_two = body.tick()                   # A is handed off; B's outcome lands; B is stepped in this turn
        assert b_recorded.is_set()
        stepped_b = [s for s in turn_two["missions"] if s["mission_id"] == b["mission_id"]]
        a_worker.release.set()
        wait_for(lambda: a["mission_id"] not in background.running, "A's dispatch to end")
        for _ in range(4):
            body.tick()
        assert background.join(WAIT) == []
        commissions = [e.payload for e in body.journal.replay("mission.action")
                       if e.payload.get("capability") == "worker.commission"]
        intents = [e.payload for e in body.journal.replay("mission.dispatching")
                   if e.payload["mission_id"] == b["mission_id"]]
        recovered = [e.payload for e in body.journal.replay("mission.action")
                     if e.payload.get("mission_id") == b["mission_id"]
                     and e.payload.get("route") == "standing_reconciliation"]
        achieved = [e.payload["mission_id"] for e in body.journal.replay("mission.achieved")]
        assert b_worker.calls == 1 and a_worker.calls == 1
        # Every step starts from the mission as the ledger holds it at that moment, B's own commission included.
        assert all(same for *_, same in stepped_from), [x for x in stepped_from if not x[-1]]
        assert [c["status"] for c in commissions if c["mission_id"] == b["mission_id"]] == ["DONE"], (stepped_b,
                                                                                                         commissions)
        body.engine.book.rebuild()
        settled = body.engine.book.missions[b["mission_id"]].committed_usd
        assert settled > 0, "the commission's spend is booked"
        # B's next act was admitted against the spend the ledger held when it was stepped, not a stale copy's.
        assert [s for mid, aid, s in admitted if mid == b["mission_id"] and aid == "fs.write"] == [settled], (
            stepped_b, admitted, settled)
        assert len(intents) == 2 and recovered == [], (stepped_b, intents, recovered)
        assert {a["mission_id"], b["mission_id"]} <= set(achieved), (stepped_b, achieved)
        assert body.ledger.verify_chain()[0]


class SleepingWorker(workers.ScriptWorker):
    """A test double of a governed worker: its child (a real process under greg.workers.supervised_run, without the
    bubblewrap envelope) sleeps until something stops it. ``polls`` False is a worker that ignores its stop predicate,
    so only killing its process group ends it."""

    name = "sleeping-test-double"

    def __init__(self, pidfile, *, polls=True):
        super().__init__()
        self.pidfile, self.polls, self.calls = pidfile, polls, 0

    def run(self, order, cwd, *, stop_check=None, egress=None):
        self.calls += 1
        script = f"import os, time\nopen({str(self.pidfile)!r}, 'w').write(str(os.getpid()))\ntime.sleep(600)\n"
        try:
            proc = workers.supervised_run([sys.executable, "-c", script], timeout=600, cwd=cwd, env={},
                                          stop_check=stop_check if self.polls else None)
        except workers.WorkerInterrupted as exc:
            return workers.WorkerReport(self.name, "sleeper", -1, 0.0, 0.0, error=str(exc), interrupted=True)
        return workers.WorkerReport(self.name, "sleeper", proc.returncode, 0.0, 0.0,
                                    error=f"exited {proc.returncode}")

    def child(self):
        wait_for(lambda: self.pidfile.exists() and self.pidfile.read_text(), "the worker's child to start")
        return int(self.pidfile.read_text())


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:                                   # a zombie the supervisor has not reaped yet is not running
        with open(f"/proc/{pid}/stat") as stat:
            return stat.read().split()[2] != "Z"
    except OSError:
        return False


def sleeping_mission(tmp_path, monkeypatch, *, polls=True):
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    worker = SleepingWorker(tmp_path / "child.pid", polls=polls)
    monkeypatch.setitem(workers.PROVIDERS, "sleeping", worker)
    spec = worker_mission(home, repo, "sleep", "sleeping", 0)
    drop(home, signed(key, body_id, "MISSION", spec))
    return home, key, body_id, worker, spec["mission_id"]


def worker_outcomes(journal, mission_id):
    return [e.payload["status"] for e in journal.replay("mission.action")
            if e.payload.get("mission_id") == mission_id and e.payload.get("capability") == "worker.commission"]


def started_off_turn(body, worker, mission_id):
    body.engine.background = Background(body._turn, clock=body.clock, stop_check=body._stop_flag)
    body.tick()
    pid = worker.child()
    assert mission_id in body.engine.background.running and alive(pid)
    return pid


def test_a_body_closing_on_an_error_stops_and_records_its_running_worker_before_the_ledger_closes(
        tmp_path, monkeypatch):
    """Integrator intake review of #273, item 2: whatever ends the body, an error included, every worker it runs off
    its turn is stopped and its outcome recorded before the ledger closes; no worker child outlives the body."""
    home, _, _, worker, mid = sleeping_mission(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="the body failed"):
        with Body(home) as body:
            pid = started_off_turn(body, worker, mid)
            raise RuntimeError("the body failed")
    assert not alive(pid), "the worker's child outlived the body"
    assert not body.engine.background.running and body.ledger is None
    with observe(home, actor="spiffe://uniimente.internal/test/background") as journal:
        assert worker_outcomes(journal, mid) == ["UNCERTAIN"], "recorded once, as an interrupted worker"
        assert journal.ledger.verify_chain()[0]


def test_a_worker_that_ignores_its_stop_has_its_process_group_killed_when_the_body_closes(tmp_path, monkeypatch):
    """Item 2: a worker that stopped polling its stop predicate does not hold the body open: after the join timeout
    its process group is killed, and its outcome is still recorded before the ledger closes."""
    from greg import body as body_module
    monkeypatch.setattr(body_module, "STOP_JOIN_SECONDS", 1)
    home, _, _, worker, mid = sleeping_mission(tmp_path, monkeypatch, polls=False)
    began = time.monotonic()
    with Body(home) as body:
        pid = started_off_turn(body, worker, mid)
    assert time.monotonic() - began < WAIT
    assert not alive(pid) and not body.engine.background.running
    with observe(home, actor="spiffe://uniimente.internal/test/background") as journal:
        assert len(worker_outcomes(journal, mid)) == 1 and worker_outcomes(journal, mid) != ["DONE"]


@pytest.mark.parametrize("command", ["cancel", "supersede", "detach"])
def test_a_founder_cancel_or_detach_while_the_worker_runs_interrupts_it(tmp_path, monkeypatch, command):
    """Item 3: commands keep being ingested while a worker runs off the turn. A cancel of its mission or a detach of
    worker.commission withdraws the authority it runs under: the worker is stopped, the interruption recorded once,
    and its outcome is UNCERTAIN (reconciled, never re-run blind)."""
    home, key, body_id, worker, mid = sleeping_mission(tmp_path, monkeypatch)
    with Body(home) as body:
        pid = started_off_turn(body, worker, mid)
        drop(home, signed(key, body_id, *{
            "cancel": ("LIFECYCLE", {"mission_id": mid, "state": "ABANDONED"}),
            "supersede": ("LIFECYCLE", {"mission_id": mid, "state": "SUPERSEDED"}),
            "detach": ("CAPABILITY_DETACH", {"capability_id": "worker.commission"})}[command]))
        body.tick()
        wait_for(lambda: mid not in body.engine.background.running, "the interrupted dispatch to record its outcome")
        assert not alive(pid)
        body.tick()
        interrupted = [e.payload for e in body.journal.replay("mission.dispatch_interrupted")]
        assert [(i["mission_id"], i["capability"]) for i in interrupted] == [(mid, "worker.commission")]
        assert worker_outcomes(body.journal, mid) == ["UNCERTAIN"] and worker.calls == 1


def test_a_pause_while_the_worker_runs_does_not_interrupt_the_admitted_act(tmp_path, monkeypatch):
    """Item 3: a mission pause or a BODY_PAUSE changes what is admitted next, never an act the Gate already admitted,
    as when they waited for an inline worker to return. Whether a pause should interrupt is an open founder ruling."""
    home, key, body_id, worker, mid = sleeping_mission(tmp_path, monkeypatch)
    with Body(home) as body:
        pid = started_off_turn(body, worker, mid)
        drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": "PAUSED"}))
        drop(home, signed(key, body_id, "BODY_PAUSE", {}))
        body.tick()
        body.tick()
        assert alive(pid) and mid in body.engine.background.running
        assert list(body.journal.replay("mission.dispatch_interrupted")) == []
        os.kill(pid, 9)                     # end the test's sleeper; the dispatch records what the worker returned
        wait_for(lambda: mid not in body.engine.background.running, "the dispatch to record its outcome")


class CountingLock(GatedLock):
    """The turn lock, counting the acquires of every thread but the test's: a dispatch thread acquires it once when it
    starts and once more when its adapter has returned (to record what the adapter did)."""

    def __init__(self):
        super().__init__()
        self.others = 0
        self.second = threading.Event()

    def acquire(self, *args, **kwargs):
        if threading.get_ident() != self.owner:
            self.others += 1
            if self.others >= 2:
                self.second.set()
        return super().acquire(*args, **kwargs)


def test_a_cancel_ingested_after_the_adapter_returned_is_not_recorded_as_an_interruption(tmp_path, monkeypatch):
    """#273 re-review A. The worker's adapter has returned and its dispatch waits for the turn to record it; a turn that
    runs meanwhile ingests the founder's LIFECYCLE ABANDONED. Nothing interrupted the worker, so no
    mission.dispatch_interrupted is recorded and the commission's outcome is the one the adapter returned. Before the
    fix the ledger said "interrupted while its worker ran" and then recorded the commission DONE."""
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    worker = HoldingWorker(GOOD)
    monkeypatch.setitem(workers.PROVIDERS, "scripted", worker)
    spec = worker_mission(home, repo, "add-sub", "scripted", 0)
    mid = spec["mission_id"]
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body._turn = turn = CountingLock()
        body.engine.background = background = Background(turn, clock=body.clock, stop_check=body._stop_flag)
        body.tick()
        assert worker.holding.wait(WAIT) and mid in background.running
        turn.acquire()                                   # a turn is running
        try:
            worker.release.set()
            assert turn.second.wait(WAIT), "the adapter never returned"   # it waits for the turn to record it
            drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": "ABANDONED"}))
            body._tick()                                 # this turn ingests the cancel
        finally:
            turn.release()
        wait_for(lambda: mid not in background.running, "the dispatch to record its outcome")
        interrupted = [e.payload for e in body.journal.replay("mission.dispatch_interrupted")]
        assert interrupted == [], "an adapter that already returned was recorded as interrupted"
        assert worker_outcomes(body.journal, mid) == ["DONE"]


def test_a_cancel_the_worker_finished_before_seeing_is_reconciled_not_recorded_done(tmp_path, monkeypatch):
    """#273 re-review A, the other order (a guard, not a fail-first test: worker.commission already re-checks its stop
    after the provider returns): the interruption is recorded while the adapter still runs, but the worker finishes
    before it polls its stop. Its outcome is UNCERTAIN (reconciled), never DONE after its interruption."""
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    worker = HoldingWorker(GOOD)                          # a test double that never polls its stop
    monkeypatch.setitem(workers.PROVIDERS, "scripted", worker)
    spec = worker_mission(home, repo, "add-sub", "scripted", 0)
    mid = spec["mission_id"]
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.engine.background = background = Background(body._turn, clock=body.clock, stop_check=body._stop_flag)
        body.tick()
        assert worker.holding.wait(WAIT)
        drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": "ABANDONED"}))
        body.tick()                                      # the interruption is recorded; the worker has not seen it
        assert [e.payload["mission_id"] for e in body.journal.replay("mission.dispatch_interrupted")] == [mid]
        worker.release.set()
        wait_for(lambda: mid not in background.running, "the dispatch to record its outcome")
        assert worker_outcomes(body.journal, mid) == ["UNCERTAIN"]


def test_nothing_is_written_after_body_stopped_names_an_unfinished_dispatch(tmp_path, monkeypatch):
    """#273 re-review B. An adapter that ignores its stop and runs no supervised child outlives the STOP join and the
    kill; body.stopped names it unfinished. The Body then closes its ledger without waiting for it again, so when it
    returns nothing it would record lands after body.stopped; the restart reconciles it."""
    from greg import background as background_module
    from greg import body as body_module
    monkeypatch.setattr(body_module, "STOP_JOIN_SECONDS", 1)
    monkeypatch.setattr(background_module, "KILL_GRACE_SECONDS", 1)
    home, worker, long_id = missions_ready(tmp_path, monkeypatch)
    body = Body(home)
    loop = threading.Thread(target=body.run, kwargs={"tick_seconds": 0.05}, daemon=True)
    loop.start()

    def stopped_recorded():
        with observe(home, actor="spiffe://uniimente.internal/test/background") as journal:
            return any(True for _ in journal.replay("body.stopped"))
    try:
        assert worker.holding.wait(WAIT), "the worker was never commissioned"
        body.stop_requested = True
        wait_for(stopped_recorded, "body.stopped")
        # The stuck adapter returns now, while the body is closing: before the fix close() waited for it again and
        # it recorded its outcome after body.stopped.
        worker.release.set()
        loop.join(WAIT)
        assert not loop.is_alive(), "the body did not stop"
    finally:
        worker.release.set()
    time.sleep(1.5)                                      # let the late dispatch try to record
    with observe(home, actor="spiffe://uniimente.internal/test/background") as journal:
        events = list(journal.replay(""))
        stopped = [i for i, e in enumerate(events) if e.type == "greg.body.stopped"]
        assert stopped, "body.stopped was not recorded"
        assert events[stopped[-1]].payload.get("dispatches_unfinished") == [long_id]
        after = [e.type for e in events[stopped[-1] + 1:]]
        assert after == [], f"written after body.stopped: {after}"
        assert journal.ledger.verify_chain()[0]


def test_a_closing_body_kills_only_the_children_its_own_dispatches_started(tmp_path):
    """#273 re-review D: kill_live_workers is scoped to the closing Body's dispatch threads."""
    mine, other = threading.Event(), threading.Event()
    pids = {}

    def start(name, done):
        proc = workers.subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
        workers._live(proc.pid)
        pids[name] = proc
        done.wait(WAIT)
    threads = {name: threading.Thread(target=start, args=(name, ev), daemon=True)
               for name, ev in (("mine", mine), ("other", other))}
    for t in threads.values():
        t.start()
    wait_for(lambda: len(pids) == 2, "both children to start")
    try:
        killed = workers.kill_live_workers({threads["mine"].ident})
        assert killed == [pids["mine"].pid]
        pids["mine"].wait(WAIT)
        assert pids["other"].poll() is None, "another body's child was killed"
    finally:
        for name, proc in pids.items():
            workers._dead(proc.pid)
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        mine.set()
        other.set()


def test_a_background_error_is_not_contained_by_a_paused_body(tmp_path, monkeypatch):
    """#273 re-review C: a paused body contains a failure of its own turn work, never a background dispatch's error,
    which kills the process as an inline dispatch's error did."""
    home, worker, long_id = missions_ready(tmp_path, monkeypatch)
    with Body(home) as body:
        body.engine.background = background = Background(body._turn, clock=body.clock, stop_check=body._stop_flag)
        background.failed.append(RuntimeError("recording failed off the turn"))
        monkeypatch.setattr(body, "paused", lambda: True)
        with pytest.raises(RuntimeError, match="recording failed off the turn"):
            body._contained(body.tick)
