"""Founder Attention Router (target I): interrupt only where attention has leverage.

Items are routed as immediate, batched or suppressed by urgency class and
estimated marginal value of the founder's attention. Open asks are deduped.
Every ask carries a no-cost option, evidence references, options and an
effort estimate; an ask without a no-cost option is suppressed as a
manipulation guard. Answers are recorded; a refusal updates the goal's
preferences so the same unchanged route is never re-proposed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from .contracts import canonical_copy, digest, require_text
from .goals import GoalRegistry, iso, parse_time

URGENCY = ("emergency", "high", "normal", "low")
KINDS = ("decision", "information", "confirmation")
ANSWERS = ("accept", "refuse", "defer", "never_use_tactic", "change")


@dataclass(frozen=True)
class AttentionItem:
    item_id: str
    goal_id: str
    kind: str
    urgency: str
    marginal_value: float
    title: str
    question: str
    options: tuple[dict[str, Any], ...]
    recommendation: str
    evidence_refs: tuple[str, ...]
    effort_estimate: str
    category: str
    route_hash: str | None
    tactic: str | None
    created_at: str

    @classmethod
    def build(cls, *, goal_id: str, kind: str, urgency: str, marginal_value: float, title: str, question: str,
              options: Sequence[Mapping[str, Any]], recommendation: str, evidence_refs: Sequence[str],
              effort_estimate: str, category: str, created_at: str | datetime, route_hash: str | None = None,
              tactic: str | None = None) -> "AttentionItem":
        if kind not in KINDS:
            raise ValueError(f"unknown attention kind {kind!r}")
        if urgency not in URGENCY:
            raise ValueError(f"unknown urgency {urgency!r}")
        if isinstance(marginal_value, bool) or not 0.0 <= float(marginal_value) <= 1.0:
            raise ValueError("marginal_value must be between 0 and 1")
        opts = tuple(canonical_copy(dict(o)) for o in options)
        for o in opts:
            require_text("option.label", o.get("label", ""))
            if "cost" not in o:
                raise ValueError("every option must state its cost (may be 'none')")
        body = {"goal_id": goal_id, "kind": kind, "urgency": urgency, "title": require_text("title", title),
                "question": require_text("question", question), "options": list(opts),
                "recommendation": require_text("recommendation", recommendation),
                "category": require_text("category", category), "route_hash": route_hash, "tactic": tactic}
        return cls(item_id=digest({"kind": "egregore-attention", **body}), goal_id=goal_id, kind=kind, urgency=urgency,
                   marginal_value=float(marginal_value), title=body["title"], question=body["question"], options=opts,
                   recommendation=body["recommendation"], evidence_refs=tuple(evidence_refs),
                   effort_estimate=require_text("effort_estimate", effort_estimate), category=body["category"],
                   route_hash=route_hash, tactic=tactic, created_at=iso(parse_time(created_at)))

    @property
    def has_no_cost_option(self) -> bool:
        return any(str(o.get("cost", "")).lower() in ("none", "0", "zero", "no cost") for o in self.options)

    def to_dict(self) -> dict[str, Any]:
        return {"item_id": self.item_id, "goal_id": self.goal_id, "kind": self.kind, "urgency": self.urgency,
                "marginal_value": self.marginal_value, "title": self.title, "question": self.question,
                "options": [canonical_copy(o) for o in self.options], "recommendation": self.recommendation,
                "evidence_refs": list(self.evidence_refs), "effort_estimate": self.effort_estimate,
                "category": self.category, "route_hash": self.route_hash, "tactic": self.tactic,
                "created_at": self.created_at, "manufactured_urgency": False, "execution_authority": "none"}


@dataclass(frozen=True)
class AttentionPolicy:
    immediate_value_threshold: float = 0.8
    batch_value_threshold: float = 0.3
    max_immediate_per_turn: int = 3
    require_no_cost_option: bool = True


@dataclass(frozen=True)
class Routing:
    immediate: tuple[AttentionItem, ...]
    batched: tuple[AttentionItem, ...]
    suppressed: tuple[tuple[str, str], ...]
    routed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {"immediate": [i.to_dict() for i in self.immediate], "batched": [i.to_dict() for i in self.batched],
                "suppressed": [list(s) for s in self.suppressed], "routed_at": self.routed_at}


class FounderAttentionRouter:
    ASK_RECORD = "egregore.founder_ask"
    ANSWER_RECORD = "egregore.founder_answer"

    def __init__(self, *, ledger: Any, registry: GoalRegistry, policy: AttentionPolicy | None = None,
                 source: str = "spiffe://uniimente.internal/egregore/goal-gravity"):
        self.ledger = ledger
        self.registry = registry
        self.policy = policy or AttentionPolicy()
        self.source = require_text("source", source)
        self._open: dict[str, dict[str, Any]] = {}
        self._answers: dict[str, dict[str, Any]] = {}
        for record in getattr(ledger, "records", ()):
            rtype = getattr(record, "record_type", None)
            if rtype == self.ASK_RECORD:
                item = record.payload["item"]
                self._open[item["item_id"]] = item
            elif rtype == self.ANSWER_RECORD:
                self._answers[record.payload["item_id"]] = record.payload
                self._open.pop(record.payload["item_id"], None)

    @property
    def execution_authority(self) -> str:
        return "none"

    def open_asks(self) -> list[dict[str, Any]]:
        return [canonical_copy(v) for v in self._open.values()]

    def route(self, items: Sequence[AttentionItem], *, now: datetime | str, channel: str = "immediate") -> Routing:
        routed_at = iso(parse_time(now))
        immediate: list[AttentionItem] = []
        batched: list[AttentionItem] = []
        suppressed: list[tuple[str, str]] = []
        seen: set[str] = set()
        ordered = sorted(items, key=lambda i: (URGENCY.index(i.urgency), -i.marginal_value, i.item_id))
        for item in ordered:
            if item.item_id in seen or item.item_id in self._open:
                suppressed.append((item.item_id, "duplicate of an open or already-routed ask"))
                continue
            if item.item_id in self._answers:
                suppressed.append((item.item_id, "already answered by founder"))
                continue
            if self.policy.require_no_cost_option and not item.has_no_cost_option:
                suppressed.append((item.item_id, "manipulation guard: no no-cost option offered"))
                continue
            seen.add(item.item_id)
            if item.urgency == "emergency":
                immediate.append(item)
            elif item.marginal_value >= self.policy.immediate_value_threshold and len(immediate) < self.policy.max_immediate_per_turn:
                immediate.append(item)
            elif item.marginal_value >= self.policy.batch_value_threshold or item.urgency == "high":
                batched.append(item)
            else:
                suppressed.append((item.item_id, "below attention value threshold; retained in ledger only"))
        for item, lane in [(i, "immediate") for i in immediate] + [(i, "batched") for i in batched]:
            payload = {"source": self.source, "item": item.to_dict(), "lane": lane, "routed_at": routed_at,
                       "disposition": "pending_founder; no external channel contacted"}
            self.ledger.append(self.ASK_RECORD, payload)
            self._open[item.item_id] = item.to_dict()
        return Routing(tuple(immediate), tuple(batched), tuple(suppressed), routed_at)

    def answer(self, item_id: str, *, decision: str, actor: str, note: str, now: datetime | str) -> dict[str, Any]:
        """Record a founder answer. An answer is a record; it is not the work and not a grant."""
        if decision not in ANSWERS:
            raise ValueError(f"unknown answer {decision!r}")
        item = self._open.get(item_id)
        if item is None:
            raise ValueError("unknown or already answered ask")
        answered_at = iso(parse_time(now))
        payload = {"source": self.source, "item_id": item_id, "goal_id": item["goal_id"], "decision": decision,
                   "actor": require_text("actor", actor), "note": require_text("note", note),
                   "answered_at": answered_at, "authority_note": "answer recorded; grants nothing by itself"}
        self.ledger.append(self.ANSWER_RECORD, payload)
        self._answers[item_id] = payload
        self._open.pop(item_id, None)
        if decision == "refuse" and item.get("route_hash"):
            self.registry.record_refusal(item["goal_id"], route_hash=item["route_hash"], actor=actor, reason=note, now=now)
        elif decision == "never_use_tactic" and item.get("tactic"):
            self.registry.record_preference(item["goal_id"], kind="never_use_tactic", value=item["tactic"],
                                            actor=actor, reason=note, now=now)
        return canonical_copy(payload)
