"""Background dispatch: a long worker runs while the Body keeps turning (directive 2026-10-28 section 38, S38-A).

``worker.commission`` runs its provider inside ``AuthorityOffice.act``: the adapter is called between the Gate's
dispatch claim and its receipt, and a frontier worker may run for minutes. Run inline, that one adapter call froze
every other mission, the inbox and the heartbeat for its whole duration.

Here only the adapter leaves the turn. Everything else stays serialized by one lock, the Body's turn lock:

- ``Body.tick`` holds it for the whole turn, as the only writer it ever was;
- a background dispatch holds it while the Gate admits, claims, commits and receipts, and while the engine records
  the outcome (``MissionEngine._record_outcome``); it releases it only while the adapter itself runs.

So the Gate, the AuthorityOffice, the MissionBook and the journal are never entered by two threads at once: only the
adapter body (the provider in its own confined work-order clone) runs beside a turn. The engine does not step a
mission whose dispatch is still running (``busy``), so its write-ahead intent is not mistaken for a body killed
inside a dispatch (``MissionEngine._recover_dispatch``).

Failure semantics are the inline ones:

- a body killed while a background adapter runs leaves exactly what a body killed inside ``office.act`` left (the
  write-ahead intent and the Gate's claim, no receipt), and the restart settles it the same way;
- an error raised by a background dispatch after it was handed off is raised again on the next turn
  (``raise_failed``), so the process dies and the supervisor and the crash breaker see it, as they did inline;
- STOP reaches the adapter through ``stop_check``, a lock-free predicate (``Body._stop_flag``), and the Body joins
  every running dispatch before it records that it stopped;
- the Body going away for any reason (an error included) stops every running adapter and joins it before the ledger
  is closed (``shutdown``); a worker that ignores its stop has its process group killed; a dispatch still running
  after that writes nothing more (the ledger is closed under the turn lock) and is reconciled on restart;
- commands keep being ingested while a worker runs (inline, only a founder STOP was). A founder cancel of the mission
  (LIFECYCLE ABANDONED or SUPERSEDED) or a detach of the capability interrupts the running adapter
  (``interrupt``): the worker is terminated and its outcome is UNCERTAIN, reconciled as any interrupted worker (also
  when the worker finished before it saw the interruption); an adapter that already returned is not interrupted. A
  mission pause, a BODY_PAUSE, a DECISION and a DEVICE_REVOKE do not: they change what is admitted next, never an act
  the Gate already admitted, exactly as when they waited for an inline worker to return. Whether a pause should
  also interrupt a running worker is an open founder ruling.

What a background dispatch does not change: who may act, what is admitted, the budget it is admitted against, what is
receipted, and how an unknown outcome is reconciled.
"""
from __future__ import annotations

import threading

# Capabilities whose adapter may run for minutes, so it runs outside the turn. Everything else stays inline.
BACKGROUND_CAPABILITIES = frozenset({"worker.commission"})
KILL_GRACE_SECONDS = 5   # after its worker's process group is killed, a dispatch records its outcome within this


class Background:
    """Hands a long adapter off the Body's turn; see the module docstring."""

    def __init__(self, lock: threading.Lock, *, clock, stop_check):
        self.lock = lock              # the Body's turn lock, held by the caller of dispatch()
        self.clock = clock
        self._stop = stop_check       # the Body's STOP, lock-free
        self.running: dict[str, dict] = {}   # mission_id -> the dispatch in flight (read and written under lock)
        self.failed: list[BaseException] = []
        self.recorded = 0    # outcomes recorded off the turn so far: a turn that sees it move rebuilds its book
        self.interrupted: dict[str, str] = {}   # mission_id -> why its running adapter must stop (set in a turn)
        self.returned: set[str] = set()   # missions whose adapter has returned; it can no longer be interrupted
        self._flags = threading.Lock()    # makes "adapter returned" and "interrupt requested" mutually exclusive
        self.closing = False   # the Body is going away: every running adapter stops
        self.shut = False      # shutdown() ran: a closing Body does not wait for these dispatches again

    def stop_check(self) -> bool:
        """STOP for every running adapter, read lock-free from inside it."""
        return self.closing or self._stop()

    def stop_for(self, mission_id: str):
        """The stop predicate one dispatch's adapter polls: STOP, the Body closing, or a turn that interrupted this
        mission's dispatch (the founder cancelled the mission or detached the capability while it ran)."""
        return lambda: self.stop_check() or mission_id in self.interrupted

    def interrupt(self, mission_id: str, why: str) -> bool:
        """Ask one running dispatch's adapter to stop (caller holds the lock). True the first time.

        An adapter that has already returned cannot be interrupted: its dispatch is only waiting for the turn to
        record what it did, and recording an interruption there would contradict that record (#273 re-review A)."""
        with self._flags:
            if mission_id not in self.running or mission_id in self.interrupted or mission_id in self.returned:
                return False
            self.interrupted[mission_id] = why
            return True

    def busy(self, mission_id: str) -> dict | None:
        """The dispatch of this mission that is still running, if any (caller holds the lock)."""
        entry = self.running.get(mission_id)
        return None if entry is None else {k: v for k, v in entry.items() if k != "thread"}

    def dispatch(self, mission_id: str, action_id: str, attempt: int, act, finish, *, capability: str | None = None):
        """Run ``act`` (the Gate's whole act) on its own thread; return to the turn once its adapter has started.

        Called with the turn lock held. ``act(wrap)`` must pass its adapter through ``wrap``; ``finish(outcome,
        background)`` records the outcome. If the act ends without running the adapter (the Gate refused, or asks
        first), the turn waits for it and ``finish``'s result is returned, exactly as inline. Otherwise None is
        returned and the mission is busy until ``finish`` has run on the dispatch's thread."""
        handed = threading.Event()
        started = threading.Event()
        result: dict = {}
        lock = self.lock

        def wrap(adapter):
            def run_off_turn(params, ctx):
                started.set()
                lock.release()      # only the adapter runs beside a turn
                handed.set()
                try:
                    return adapter(params, ctx)
                finally:
                    with self._flags:          # from here on no turn may record an interruption of this adapter
                        self.returned.add(mission_id)
                    lock.acquire()  # the Gate's commit and receipt, and the record, are serialized again
            return run_off_turn

        def body():
            with lock:
                try:
                    outcome = act(wrap)
                    result["value"] = finish(outcome, started.is_set())
                except BaseException as exc:   # re-raised in the turn: by the waiting turn, or by the next one
                    result["error"] = exc
                    if started.is_set():
                        self.failed.append(exc)
                finally:
                    if started.is_set():
                        self.recorded += 1
                    self.running.pop(mission_id, None)
                    self.interrupted.pop(mission_id, None)
                    self.returned.discard(mission_id)
                    handed.set()

        thread = threading.Thread(target=body, name=f"greg-dispatch {mission_id} {action_id}#{attempt}", daemon=True)
        self.running[mission_id] = {"action_id": action_id, "attempt": attempt, "thread": thread,
                                    "since": self.clock(), "capability": capability}
        lock.release()
        try:
            thread.start()
            handed.wait()
        finally:
            lock.acquire()
        if mission_id in self.running:
            return None             # the adapter is running; the outcome is recorded when it returns
        if "error" in result:       # it already ended in error: raised in this turn, not the next
            if result["error"] in self.failed:
                self.failed.remove(result["error"])
            raise result["error"]
        return result.get("value")

    def raise_failed(self) -> None:
        """Raise an error a background dispatch hit after it was handed off (caller holds the lock)."""
        if self.failed:
            exc = self.failed.pop(0)
            exc.greg_background_dispatch = True   # never contained by a paused body (Body._contained)
            raise exc

    def join(self, timeout: float | None = None) -> list[str]:
        """Wait, without the turn lock, for every running dispatch to record its outcome; the missions still running
        when the timeout passes are returned."""
        deadline = None if timeout is None else self.clock_monotonic() + timeout
        for entry in list(self.running.values()):
            remaining = None if deadline is None else max(0.0, deadline - self.clock_monotonic())
            entry["thread"].join(remaining)
        return sorted(self.running)

    def shutdown(self, timeout: float) -> list[str]:
        """Stop every running adapter and wait, without the turn lock, for each dispatch to record its outcome.

        Every adapter polls ``stop_check``: a confined worker's supervisor kills its process group within a poll
        (greg.workers.supervised_run). An adapter that does not return within ``timeout`` is one that stopped
        polling; the process groups of the children those dispatches still run are killed
        (greg.workers.kill_live_workers) and the dispatches are given a short last wait. The missions still running
        after that are returned: the Body records them as unfinished and closes its ledger without waiting again, so
        nothing they would write lands after body.stopped; the restart reconciles them (UNCERTAIN)."""
        self.closing = True
        self.shut = True
        unfinished = self.join(timeout)
        if unfinished:
            from greg.workers import kill_live_workers
            kill_live_workers({entry["thread"].ident for entry in list(self.running.values())})
            unfinished = self.join(KILL_GRACE_SECONDS)
        return unfinished

    @staticmethod
    def clock_monotonic() -> float:
        import time
        return time.monotonic()
