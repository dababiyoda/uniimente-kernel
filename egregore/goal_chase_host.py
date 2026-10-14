"""Explicitly started, sandbox-only GoalChase host.

One process may wake on a stable time slot while the founder chat is closed.
All goals, transitions and receipts remain in the existing Kernel ledger. This
module has no authority to contact an account, use real founder credentials,
install a background service or execute arbitrary tools.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from egregore.goal_chase import instant, stamp
from egregore.goal_chase_demo import DEMO_KEY
from egregore.goal_chase_sandbox import SyntheticFounder, open_sandbox


def _utc(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("host clock must include a time zone")
    return now.astimezone(timezone.utc)


def slot_id(now: datetime, period_seconds: int) -> str:
    """Retrying the same time slot reuses exactly one trigger identity."""
    if not isinstance(period_seconds, int) or isinstance(period_seconds, bool) or period_seconds < 1:
        raise ValueError("period_seconds must be a positive integer")
    return f"sandbox:host:{period_seconds}:{int(_utc(now).timestamp()) // period_seconds}"


def inspect_or_tick(
    ledger_path: str | Path,
    *,
    now: datetime,
    period_seconds: int = 60,
    pause_file: str | Path | None = None,
    tick: bool = True,
) -> dict:
    """Project one truthful review; only tick the already registered sandbox.

    An absent ledger is a setup error. Never create an empty history and call it
    a persistent mission. A pause file stops work before opening the host.
    """
    path = Path(ledger_path).resolve()
    if not path.is_file() or not path.stat().st_size:
        raise FileNotFoundError("register a sandbox mission before starting the host")
    now = _utc(now)
    pause = Path(pause_file).resolve() if pause_file is not None else path.with_suffix(path.suffix + ".pause")
    paused = pause.exists()
    trigger = None
    with open_sandbox(path, founder=SyntheticFounder(DEMO_KEY), clock=lambda: now) as chase:
        before = {event.event_id for event in chase.events}
        if tick and not paused:
            trigger = slot_id(now, period_seconds)
            chase.tick(trigger)
        snapshot = chase.snapshot()
        events = [event for event in chase.events if event.event_id not in before]
        negatives = [event for event in chase.events if any(term in event.type for term in
                     ("rejected", "refused", "denied", "conflict", "unavailable", "deficit", "failed"))]
        pending = chase.pending_messages()
        return {
            "reality_status": "SIMULATED / SANDBOX",
            "host_status": "PAUSED" if paused else ("TICKED" if tick else "READ_ONLY"),
            "as_of_utc": stamp(now),
            "trigger_id": trigger,
            "ledger_head": chase.spine.ledger.head,
            "new_event_ids": [event.event_id for event in events],
            "new_event_types": [event.type for event in events],
            "negative_evidence_event_ids": [event.event_id for event in negatives],
            "goals": snapshot,
            "decisions_needed": pending,
            "open_goals": {gid: {"state": goal["state"], "bottleneck": goal["bottleneck"],
                                 "deficits": goal["deficits"], "next_action": goal["next_action"]}
                           for gid, goal in snapshot.items() if goal["state"] != "ACHIEVED"},
            "metrics": chase.metrics(),
            "what_was_not_done": [
                "No real account, external communication, payment or computer-use action is connected.",
                "No live founder authentication or real-world outcome is claimed.",
            ],
            "real_world_verified_outcomes": 0,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", help="existing GoalChase sandbox JSONL ledger")
    parser.add_argument("--mode", choices=("once", "loop", "report"), default="once")
    parser.add_argument("--period-seconds", type=int, default=60)
    parser.add_argument("--pause-file", help="existing marker pauses ticks; remove marker to resume")
    parser.add_argument("--cycles", type=int, default=0, help="loop only: 0 means until stopped")
    parser.add_argument("--at", help="sandbox test clock in RFC3339; omit for UTC wall clock")
    args = parser.parse_args(argv)
    if args.period_seconds < 1 or args.cycles < 0:
        parser.error("period must be positive and cycles nonnegative")
    if args.mode != "loop" and args.cycles:
        parser.error("--cycles applies only to loop mode")
    if args.mode == "loop" and args.at:
        parser.error("--at is for finite sandbox once/report runs")
    count = 0
    try:
        while True:
            now = instant(args.at) if args.at else datetime.now(timezone.utc)
            report = inspect_or_tick(
                args.ledger, now=now, period_seconds=args.period_seconds,
                pause_file=args.pause_file, tick=args.mode != "report",
            )
            print(json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)
            count += 1
            if args.mode != "loop" or (args.cycles and count >= args.cycles):
                break
            # Waking more often than the slot does not create a new action.
            time.sleep(args.period_seconds)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
