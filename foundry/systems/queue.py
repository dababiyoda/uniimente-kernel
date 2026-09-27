"""#24 Message queue: durable, at-least-once delivery between organs.

File-backed queue per topic: ``publish`` appends; ``receive`` leases a message
for a visibility timeout; ``ack`` completes it; an unacked lease expires and the
message is redelivered; after ``max_deliveries`` it moves to the dead-letter
topic with its failure history. ``IdempotentConsumer`` records processed message
ids so redelivery never repeats an effect. All state survives process restart.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path


class Queue:
    def __init__(self, root: Path, topic: str, *, visibility: float = 30.0, max_deliveries: int = 3):
        self.dir = Path(root) / topic
        self.dir.mkdir(parents=True, exist_ok=True)
        self.topic, self.visibility, self.max_deliveries = topic, visibility, max_deliveries
        self.state_path = self.dir / "state.json"

    def _state(self) -> dict:
        return json.loads(self.state_path.read_text()) if self.state_path.exists() else {"messages": {}, "order": []}

    def _save(self, state: dict) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, sort_keys=True))
        tmp.replace(self.state_path)

    def publish(self, body: dict, *, message_id: str | None = None) -> str:
        state = self._state()
        mid = message_id or str(uuid.uuid4())
        if mid in state["messages"]:
            return mid  # publishing the same id twice is a no-op
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
        state["messages"][message_id]["acked"] = True
        self._save(state)

    def fail(self, message_id: str, error: str, now: float) -> None:
        state = self._state()
        m = state["messages"][message_id]
        m["errors"].append(error)
        m["lease_until"] = now  # visible again immediately
        if m["deliveries"] >= self.max_deliveries:
            m["acked"] = True
            dead = Queue(self.dir.parent, f"{self.topic}.dead")
            dead.publish({"original": m["body"], "errors": m["errors"]}, message_id=message_id)
        self._save(state)

    def depth(self) -> int:
        return sum(1 for m in self._state()["messages"].values() if not m["acked"])


class IdempotentConsumer:
    def __init__(self, root: Path, name: str):
        self.path = Path(root) / f"consumer-{name}.json"
        self.done = set(json.loads(self.path.read_text())) if self.path.exists() else set()

    def handle(self, message: dict, effect) -> bool:
        if message["id"] in self.done:
            return False
        effect(message["body"])
        self.done.add(message["id"])
        self.path.write_text(json.dumps(sorted(self.done)))
        return True


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
