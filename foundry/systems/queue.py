"""#24 Message queue: durable, at-least-once delivery between organs.

File-backed queue per topic: ``publish`` appends; ``receive`` leases a message
for a visibility timeout; ``ack`` completes it; an unacked lease expires and the
message is redelivered; after ``max_deliveries`` it moves to the dead-letter
topic with its failure history. ``IdempotentConsumer`` records processed message
ids so redelivery never repeats an effect. All state survives process restart.

Growth is capped. ``publish`` refuses when ``max_unacked`` messages are already
leased or waiting. An ack drops the body and keeps the id; once more than
``max_acked`` acked ids are retained, the oldest leave the file and extend
``audit.head`` (a hash chain of id and body digest). The consumer forgets a
handled id only after ``retain_seconds``, and records that release in the same
kind of chain. A redelivery inside the window still does not run the effect twice.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

MAX_UNACKED = 256
MAX_ACKED = 256
_AUDIT_GENESIS = "sha256:" + "0" * 64


class QueueFull(RuntimeError):
    """The topic is already holding its maximum number of unacked messages."""


def _audit() -> dict:
    return {"released": 0, "head": _AUDIT_GENESIS}


def _extend(head: str, material: str) -> str:
    return "sha256:" + hashlib.sha256(f"{head}|{material}".encode()).hexdigest()


class Queue:
    def __init__(self, root: Path, topic: str, *, visibility: float = 30.0, max_deliveries: int = 3,
                 max_unacked: int = MAX_UNACKED, max_acked: int = MAX_ACKED):
        if max_unacked < 1 or max_acked < 1:
            raise ValueError("queue retention bounds must be positive")
        self.dir = Path(root) / topic
        self.dir.mkdir(parents=True, exist_ok=True)
        self.topic, self.visibility, self.max_deliveries = topic, visibility, max_deliveries
        self.max_unacked, self.max_acked = max_unacked, max_acked
        self.state_path = self.dir / "state.json"

    def _state(self) -> dict:
        if self.state_path.exists():
            state = json.loads(self.state_path.read_text())
        else:
            state = {"messages": {}, "order": []}
        state.setdefault("audit", _audit())
        return state

    def _save(self, state: dict) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, sort_keys=True))
        tmp.replace(self.state_path)

    def _release_acked(self, state: dict) -> int:
        """Drop acked ids past the cap. Each dropped id extends the audit chain before it goes."""
        acked = [mid for mid in state["order"] if state["messages"][mid].get("acked")]
        released = 0
        while len(acked) > self.max_acked:
            mid = acked.pop(0)
            msg = state["messages"].pop(mid)
            state["order"].remove(mid)
            digest = msg.get("body_sha256") or ""
            state["audit"]["head"] = _extend(state["audit"]["head"], f"{mid}|{digest}")
            state["audit"]["released"] += 1
            released += 1
        return released

    def publish(self, body: dict, *, message_id: str | None = None) -> str:
        state = self._state()
        mid = message_id or str(uuid.uuid4())
        if mid in state["messages"]:
            return mid  # publishing the same id twice is a no-op
        if self._release_acked(state):
            self._save(state)
        unacked = sum(1 for m in state["messages"].values() if not m.get("acked"))
        if unacked >= self.max_unacked:
            raise QueueFull(f"topic {self.topic} already holds {unacked} unacked messages")
        state["messages"][mid] = {"body": body, "deliveries": 0, "lease_until": None, "acked": False, "errors": []}
        state["order"].append(mid)
        self._save(state)
        return mid

    def receive(self, now: float) -> dict | None:
        state = self._state()
        for mid in state["order"]:
            m = state["messages"][mid]
            if m["acked"] or (m["lease_until"] is not None and m["lease_until"] > now):
                continue
            if m["deliveries"] >= self.max_deliveries:
                continue
            m["deliveries"] += 1
            m["lease_until"] = now + self.visibility
            self._save(state)
            return {"id": mid, "body": m["body"], "delivery": m["deliveries"]}
        return None

    def ack(self, message_id: str) -> None:
        state = self._state()
        message = state["messages"][message_id]
        if message.get("body") is not None and "body_sha256" not in message:
            message["body_sha256"] = hashlib.sha256(
                json.dumps(message["body"], sort_keys=True).encode()).hexdigest()
        message["body"] = None
        message["acked"] = True
        self._release_acked(state)
        self._save(state)

    def fail(self, message_id: str, error: str, now: float) -> None:
        state = self._state()
        m = state["messages"][message_id]
        m["errors"].append(error)
        m["lease_until"] = now  # visible again immediately
        if m["deliveries"] >= self.max_deliveries:
            original = m.get("body")
            if original is not None and "body_sha256" not in m:
                m["body_sha256"] = hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest()
            m["body"] = None
            m["acked"] = True
            dead = Queue(self.dir.parent, f"{self.topic}.dead",
                         max_unacked=self.max_unacked, max_acked=self.max_acked)
            dead.publish({"original": original, "errors": list(m["errors"])}, message_id=message_id)
            self._release_acked(state)
        self._save(state)

    def depth(self) -> int:
        return sum(1 for m in self._state()["messages"].values() if not m["acked"])


class IdempotentConsumer:
    """Remembers handled ids so a redelivery does not repeat an effect.

    Ids older than ``retain_seconds`` leave the set and extend ``audit``. A
    redelivery after that window can run again; the queue's own ack cap is what
    stops an already-acked id from being received again.
    """

    def __init__(self, root: Path, name: str, *, retain_seconds: float = 7 * 24 * 3600):
        if retain_seconds < 0:
            raise ValueError("retain_seconds must be non-negative")
        self.path = Path(root) / f"consumer-{name}.json"
        self.retain_seconds = retain_seconds
        self.done: dict[str, float] = {}
        self.audit = _audit()
        if self.path.exists():
            raw = json.loads(self.path.read_text())
            if isinstance(raw, list):  # files written before the retention record
                now = time.time()
                self.done = {item: now for item in raw}
            else:
                self.done = {str(k): float(v) for k, v in raw.get("done", {}).items()}
                self.audit = raw.get("audit") or _audit()

    def handle(self, message: dict, effect, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        self._expire(now)
        if message["id"] in self.done:
            self._save()
            return False
        effect(message["body"])
        self.done[message["id"]] = now
        self._save()
        return True

    def _expire(self, now: float) -> None:
        cutoff = now - self.retain_seconds
        for mid, seen in list(self.done.items()):
            if seen < cutoff:
                self.done.pop(mid)
                self.audit["head"] = _extend(self.audit["head"], mid)
                self.audit["released"] += 1

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"done": self.done, "audit": self.audit}, sort_keys=True))


QUERY_OPS = {"depth": lambda a, r: {"depth": Queue(r, a["topic"]).depth()}}
APPLY_OPS = {"publish": lambda a, r: {"id": Queue(r, a["topic"]).publish(a["body"], message_id=a.get("id"))}}


def exercise(root) -> dict:
    root = Path(root)
    q = Queue(root, "signals", visibility=10, max_deliveries=3)
    q.publish({"signal": "late payments"}, message_id="m1")
    q.publish({"signal": "late payments"}, message_id="m1")         # duplicate publish
    q.publish({"signal": "poison"}, message_id="m2")
    effects = []
    consumer = IdempotentConsumer(root, "wmi")
    first = q.receive(now=0)                                         # m1 leased, consumer crashes before ack
    consumer.handle(first, effects.append)
    redelivered = Queue(root, "signals", visibility=10, max_deliveries=3).receive(now=11)   # new process, lease expired
    handled_again = consumer.handle(redelivered, effects.append)
    q.ack(redelivered["id"])
    for t in range(3):                                               # poison message fails every time
        msg = q.receive(now=20 + t)
        q.fail(msg["id"], "cannot parse", now=20 + t)
    dead = Queue(root, "signals.dead")
    return {"duplicate_publish_ignored": q._state()["order"] == ["m1", "m2"],
            "redelivered_after_lease": redelivered["id"] == "m1" and redelivered["delivery"] == 2,
            "effect_once": effects == [{"signal": "late payments"}] and handled_again is False,
            "poison_dead_lettered": dead.depth() == 1 and q.depth() == 0}
