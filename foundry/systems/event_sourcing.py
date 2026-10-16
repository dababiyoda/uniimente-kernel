"""#5 Event sourcing on the Kernel's EventSpine: every consequential transition is an
immutable, hash-chained event; state is a projection rebuilt by replay.

The exercise records one Signal -> assessment -> approval -> capability ->
action -> outcome chain on a file-backed ledger, rebuilds the projection from a
fresh process-level open, shows idempotent re-emission, refuses a reused id
with different content, and refuses to replay a tampered ledger.
"""
from __future__ import annotations

import json
from pathlib import Path

CHAIN = ("signal.observed", "assessment.created", "approval.granted", "capability.issued", "action.executed",
         "outcome.measured")


def _spine(path: Path):
    from events.spine import EventSpine
    from provenance.ledger import EvidenceLedger
    return EventSpine(EvidenceLedger("sha256:" + "0" * 64, str(path)))


def _event(kind: str, n: int, **payload):
    from events.spine import Event, SPIFFE_PREFIX
    return Event(type=f"venture.{kind.split('.')[1]}_{kind.split('.')[0]}", source=SPIFFE_PREFIX + "foundry/exercise",
                 actor="alfonso", legal_principal="alfonso_lopez", payload={"step": kind, "n": n, **payload},
                 event_id=f"evt-{n:02d}", occurred_at=f"2026-09-27T00:00:{n:02d}Z")


def project(spine) -> dict:
    """Venture state rebuilt purely from events."""
    state = {"stage": None, "history": []}
    for event in spine.replay("venture."):
        state["stage"] = event.payload["step"]
        state["history"].append(event.payload["step"])
    return state


def emit_chain(path: Path) -> dict:
    spine = _spine(path)
    for n, kind in enumerate(CHAIN, 1):
        spine.emit(_event(kind, n))
    return project(spine)


QUERY_OPS = {"project": lambda a, r: project(_spine(Path(r) / "ledger.jsonl"))}
APPLY_OPS = {"emit": lambda a, r: (_spine(Path(r) / "ledger.jsonl").emit(_event(a["kind"], int(a["n"]), **a.get("payload", {}))),
                                   {"emitted": a["kind"]})[1]}


def exercise(root) -> dict:
    from events.spine import EventError
    path = Path(root) / "ledger.jsonl"
    first = _spine(path)
    for n, kind in enumerate(CHAIN, 1):
        first.emit(_event(kind, n))
    before = project(first)
    first.ledger.close()                                      # the writer process ends
    reopened = _spine(path)                                   # a new process opening the same ledger
    after = project(reopened)
    duplicate = reopened.emit(_event(CHAIN[0], 1))            # same id, same content: no new fact
    try:
        reopened.emit(_event(CHAIN[0], 1, tampered=True))
        reuse_refused = False
    except EventError:
        reuse_refused = True
    reopened.ledger.close()
    lines = path.read_text().splitlines()
    record = json.loads(lines[2])
    record["payload"]["payload"]["step"] = "approval.forged"
    lines[2] = json.dumps(record)
    path.write_text("\n".join(lines) + "\n")
    try:
        _spine(path)
        tamper_refused = False
    except Exception:
        tamper_refused = True
    return {"replayed_history": after["history"], "replay_equals_live": before == after,
            "duplicate_is_noop": duplicate is None, "reused_id_refused": reuse_refused,
            "tampered_ledger_refused": tamper_refused}
