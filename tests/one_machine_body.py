"""Test harness ONLY: the real GREG body loop in its own process, for the one-machine test.

Usage: python -m tests.one_machine_body HOME WORKER_SCRIPT [SPEED]

* ``Body.run`` is the same loop ``greg run`` starts under a supervisor; nothing is mocked.
* One worker provider is declared: ``local-cli``, a ``CliAgentWorker`` over the deterministic
  test double ``tests/one_machine_worker.py``. It is never presented as a frontier worker. It is
  unreviewed, so it runs only on a body the founder initialized with ``worker_confinement:
  supervised``; on a default body the envelope refuses it before dispatch.
* The wall clock runs SPEED times faster than real time (default 60) so mission cadences of
  30 s take half a second, and it never runs backwards across a restart: it starts at the
  later of now and the last heartbeat. The monotonic clock is the real one.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time

from greg import workers
from greg.body import Body, Layout


def accelerated_clock(home: Path, speed: float):
    start = datetime.now(timezone.utc)
    beat = Layout(home).heartbeat
    if beat.exists():
        try:
            last = datetime.fromisoformat(json.loads(beat.read_text())["at"].replace("Z", "+00:00"))
            start = max(start, last + timedelta(seconds=1))
        except (ValueError, KeyError):
            pass
    origin = time.monotonic()
    return lambda: start + timedelta(seconds=(time.monotonic() - origin) * speed)


def main(argv: list[str]) -> int:
    home, script = Path(argv[0]), Path(argv[1])
    speed = float(argv[2]) if len(argv) > 2 else 60.0
    workers.PROVIDERS["local-cli"] = workers.CliAgentWorker("local-cli", [sys.executable, str(script)], stdin=True)
    return Body(home, clock=accelerated_clock(home, speed)).run(tick_seconds=0.5)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
