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
  every running dispatch before it records that it stopped.

What a background dispatch does not change: who may act, what is admitted, the budget it is admitted against, what is
receipted, and how an unknown outcome is reconciled.
"""
from __future__ import annotations

import threading

# Capabilities whose adapter may run for minutes, so it runs outside the turn. Everything else stays inline.
BACKGROUND_CAPABILITIES = frozenset({"worker.commission"})


class Background:
    """Hands a long adapter off the Body's turn; see the module docstring."""

    def __init__(self, lock: threading.Lock, *, clock, stop_check):
        self.lock = lock              # the Body's turn lock, held by the caller of dispatch()
        self.clock = clock
        self.stop_check = stop_check  # lock-free: read from inside a running adapter
        self.running: dict[str, dict] = {}   # mission_id -> the dispatch in flight (read and written under lock)
        self.failed: list[BaseException] = []

    def busy(self, mission_id: str) -> dict | None:
        """The dispatch of this mission that is still running, if any (caller holds the lock)."""
        entry = self.running.get(mission_id)
        return None if entry is None else {k: v for k, v in entry.items() if k != "thread"}

    def dispatch(self, mission_id: str, action_id: str, attempt: int, act, finish):
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
                    self.running.pop(mission_id, None)
                    handed.set()

        thread = threading.Thread(target=body, name=f"greg-dispatch {mission_id} {action_id}#{attempt}", daemon=True)
        self.running[mission_id] = {"action_id": action_id, "attempt": attempt, "thread": thread,
                                    "since": self.clock()}
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
            raise self.failed.pop(0)

    def join(self, timeout: float | None = None) -> list[str]:
        """Wait, without the turn lock, for every running dispatch to record its outcome; the missions still running
        when the timeout passes are returned."""
        deadline = None if timeout is None else self.clock_monotonic() + timeout
        for entry in list(self.running.values()):
            remaining = None if deadline is None else max(0.0, deadline - self.clock_monotonic())
            entry["thread"].join(remaining)
        return sorted(self.running)

    @staticmethod
    def clock_monotonic() -> float:
        import time
        return time.monotonic()
