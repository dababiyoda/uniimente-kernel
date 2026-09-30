"""Deterministic founder-facing demo. Every operation is SIMULATED / SANDBOX.

Run begin, inspect and approve in separate Python processes against the same file.
The public test key below authenticates only this synthetic actor and cannot
represent real Alfonso approval. No production adapter/key/environment is read.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from egregore.contracts import digest
from egregore.goal_chase_sandbox import SyntheticFounder, open_sandbox, goal, action, observation, decision

DEMO_KEY = b"PUBLIC-SYNTHETIC-DEMO-KEY-NO-REAL-AUTHORITY-2026"
T0 = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)


def begin(chase, founder):
    specs = [goal(now=T0),
             goal("sandbox:GOAL-002", now=T0, priority=60,
                  actions=[action(capability="missing.function")]),
             goal("sandbox:GOAL-003", now=T0, priority=40),
             goal("sandbox:GOAL-004", now=T0, priority=20, state="DEFERRED")]
    specs[0]["statement"] = (
        "Build the first persistent Infinite Goal Chase closure: compare synthetic "
        "capability-development routes, obtain a bounded founder decision, and reconcile "
        "a simulated prototype that supports harder future aspirations")
    specs[0]["founder_intent_lineage"].append("INTENT-IGC-2026-09-05")
    specs[0]["actions"][0]["bottleneck"] = "Qualify routes to persistent capability development"
    specs[0]["actions"][1]["bottleneck"] = "Founder boundary for a simulated capability experiment"
    specs[1]["statement"] = "Find the missing competency needed for the next Infinite Goal Chase generation"
    specs[2]["statement"] = "Await evidence that a developmental mechanism works beyond this sandbox"
    specs[3]["statement"] = (
        "Preserve the far-future Infinite Goal Chase horizon: advanced scientific capabilities, "
        "robotics, automated laboratories, manufacturing, distributed physical embodiments, "
        "and future facilities")
    specs[3]["dependencies"] = ["sandbox:GOAL-001", "sandbox:GOAL-002", "sandbox:GOAL-003"]
    specs[3]["review_trigger"] = "Founder review after prerequisite capabilities and evidence exist"
    specs[3]["constraints"].append("FUTURE horizon only; no present capability or permission implied")
    for spec in specs:
        chase.register(founder.sign("GOAL", spec, now=T0))
    for i in (1, 2):
        chase.observe(observation(f"sandbox:GOAL-00{i}", now=T0, oid=f"sandbox:OBS-00{i}"))
    chase.tick("sandbox:begin")
    chase.tick("sandbox:quiet")


def report(chase):
    snapshot = chase.snapshot()
    return {"reality_status": "SIMULATED / SANDBOX", "snapshot": snapshot,
            "snapshot_hash": digest(snapshot), "pending_messages": chase.pending_messages(),
            "metrics": chase.metrics(), "ledger_head": chase.spine.ledger.head,
            "real_world_closures": 0,
            "closure_claim": "Requires acceptance-suite and independent fresh-process evidence"}


def render(result, phase):
    metrics = result["metrics"]
    lines = ["SIMULATED / SANDBOX — UNIIMENTE HEARTBEAT", f"Phase: {phase}",
             f"Goals preserved: {len(result['snapshot'])}"]
    for gid, state in result["snapshot"].items():
        lines.append(f"{gid}: {state['state']} / completed: {', '.join(state['reconciled']) or 'none'}")
        lines.append(f"  Goal: {state['statement']}")
    for message in result["pending_messages"]:
        lines += ["Needs Alfonso (synthetic demo):", f"  {message['why_now']}",
                  f"  Completed: {', '.join(message['what_has_already_been_done'])}",
                  f"  Recommendation: simulate a ${message['budget_requested_cents'] / 100:.2f} cap",
                  f"  Alternative: {message['alternatives'][0]}",
                  f"  Deadline: {message['deadline']}", "  No external action has occurred"]
    if not result["pending_messages"]:
        lines.append("No founder decision pending. Awaiting the next useful trigger.")
    lines += [f"Founder interruptions: {metrics['founder_interruptions']}",
              f"Duplicate escalations suppressed: {metrics['duplicate_suppressed']}",
              f"Unauthorized external effects: {metrics['unauthorized_external_effects']}",
              f"Unreconciled actions: {metrics['unreconciled_actions']}"]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger")
    parser.add_argument("--phase", choices=("begin", "inspect", "approve", "reject"), required=True)
    parser.add_argument("--output")
    parser.add_argument("--expected-snapshot-hash")
    args = parser.parse_args()
    founder = SyntheticFounder(DEMO_KEY)
    now = T0 if args.phase == "begin" else T0 + timedelta(minutes=5)
    with open_sandbox(args.ledger, founder=founder, clock=lambda: now) as chase:
        if args.expected_snapshot_hash and digest(chase.snapshot()) != args.expected_snapshot_hash:
            raise RuntimeError("fresh-process state differs from pre-exit state")
        if args.phase == "begin":
            begin(chase, founder)
        elif args.phase in ("approve", "reject"):
            pending = chase.pending_messages()
            if pending:
                body = decision(pending[0], answer="APPROVE" if args.phase == "approve" else "REJECT")
                envelope = founder.sign("DECISION", body, now=now)
                chase.decide(envelope)
                chase.decide(envelope)  # duplicate delivery must not duplicate work
                chase.tick("sandbox:" + args.phase)
                chase.tick("sandbox:after-decision-quiet")
        result = report(chase)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(render(result, args.phase))


if __name__ == "__main__":
    main()
