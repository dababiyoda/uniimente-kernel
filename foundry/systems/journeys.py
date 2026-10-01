"""#34/#50 Observed content sequences and evidence-governed journey routing.

Imported events retain source references and evidence tier. Associations are
measured within a declared lookback; they are not causal attribution. No
impression-based revenue estimates, model-generated conversions or live contact.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
import json
from pathlib import Path
import sqlite3

from foundry.systems.community import canonical, identifier, instant
from foundry.territory import ContentNode, TerritoryGraph

KINDS = {"view", "subscribe", "purchase", "refund", "used_tool", "joined_community"}
TIERS = {"fixture", "observed"}
FIELDS = {"id", "at", "subject", "kind", "node", "source_ref", "tier", "amount_cents", "currency", "receipt"}
MAX_EVENTS = 4096


def store(root):
    root = Path(root)
    return root.parent / "system-34" if root.name == "system-50" else root


def validate(event):
    if not isinstance(event, dict) or set(event) != FIELDS:
        raise ValueError("invalid observed journey event fields")
    for key in ("id", "subject", "node"):
        identifier(event[key])
    instant(event["at"])
    if event["kind"] not in KINDS or event["tier"] not in TIERS:
        raise ValueError("invalid event kind/evidence tier")
    if not isinstance(event["source_ref"], str) or not 1 <= len(event["source_ref"]) <= 512:
        raise ValueError("observed source reference required")
    if type(event["amount_cents"]) is not int or not 0 <= event["amount_cents"] <= 10**12:
        raise ValueError("money must be bounded integer minor units")
    if event["kind"] in {"purchase", "refund"}:
        if not isinstance(event["currency"], str) or len(event["currency"]) != 3 or not event["currency"].isupper():
            raise ValueError("currency required for money event")
        if not isinstance(event["receipt"], str) or not 1 <= len(event["receipt"]) <= 512:
            raise ValueError("purchase/refund receipt reference required")
    elif event["amount_cents"] or event["currency"] is not None or event["receipt"] is not None:
        raise ValueError("non-money events cannot manufacture revenue")
    return event


def _connect(root):
    root = store(root); root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "journeys.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
    return db


def _events(db):
    events = [validate(json.loads(row[0])) for row in db.execute("SELECT body FROM events")]
    return sorted(events, key=lambda e: (instant(e["at"]), e["id"]))


def ingest(root, events):
    if not isinstance(events, list) or len(events) > 128:
        raise ValueError("bounded observed event batch required")
    db = _connect(root)
    try:
        with db:
            existing = {e["id"]: e for e in _events(db)}
            added = 0
            for event in events:
                validate(event)
                if event["id"] in existing:
                    if canonical(existing[event["id"]]) != canonical(event):
                        raise ValueError("observed event id reused with different content")
                    continue
                if event["kind"] in {"purchase", "refund"} and any(
                        e["tier"] == event["tier"] and e["kind"] == event["kind"] and e["currency"] == event["currency"] and
                        e["receipt"] == event["receipt"] for e in existing.values()):
                    raise ValueError("money receipt already recorded")
                existing[event["id"]] = event
                db.execute("INSERT INTO events VALUES (?,?)", (event["id"], canonical(event).decode()))
                added += 1
            if len(existing) > MAX_EVENTS:
                raise ValueError("observed event quota")
        return {"added": added, "events": len(existing), "scope": "source-declared observations; not independently verified"}
    finally:
        db.close()


def report(root, tier, lookback_hours=720):
    if tier not in TIERS or type(lookback_hours) is not int or not 1 <= lookback_hours <= 8760:
        raise ValueError("declared evidence tier and bounded lookback required")
    db = _connect(root)
    try:
        events = [e for e in _events(db) if e["tier"] == tier]
    finally:
        db.close()
    subjects = defaultdict(list)
    for e in events:
        subjects[e["subject"]].append(e)
    paths, money, unlinked = {}, defaultdict(int), 0
    for subject, history in subjects.items():
        for i, event in enumerate(history):
            start = instant(event["at"]) - timedelta(hours=lookback_hours)
            prior = [v for v in history[:i + (event["kind"] == "view")] if v["kind"] == "view" and instant(v["at"]) >= start]
            sequence = tuple(v["node"] for v in prior)
            if not sequence:
                if event["kind"] != "view":
                    unlinked += 1
                continue
            row = paths.setdefault(sequence, {"subjects": set(), "subscribers": set(), "customers": set(), "useful": set()})
            row["subjects"].add(subject)
            if event["kind"] == "subscribe":
                row["subscribers"].add(subject)
            elif event["kind"] == "purchase":
                row["customers"].add(subject)
            elif event["kind"] in {"used_tool", "joined_community"}:
                row["useful"].add(subject)
            if event["kind"] in {"purchase", "refund"}:
                money[event["currency"]] += event["amount_cents"] * (-1 if event["kind"] == "refund" else 1)
    views = [e for e in events if e["kind"] == "view"]
    viewers = {e["subject"] for e in views}
    subscribers = set().union(*(row["subscribers"] for row in paths.values()))
    customers = set().union(*(row["customers"] for row in paths.values()))
    return {"tier": tier, "events": len(events), "viewers": len(viewers),
            "paths": [{"sequence": list(path), **{k: len(v) for k, v in row.items()}}
                      for path, row in sorted(paths.items())],
            "subscribers": len(subscribers), "customers": len(customers),
            "subscriber_conversion": len(subscribers) / len(viewers) if viewers else None,
            "customer_conversion": len(customers) / len(viewers) if viewers else None,
            "linked_net_receipt_cents": dict(money), "unlinked_outcomes": unlinked,
            "lookback_hours": lookback_hours,
            "claim": "temporal association in source-declared events; not causal attribution or verified settlement"}


def route(root, subject, tier, territory, now):
    identifier(subject)
    if tier not in TIERS:
        raise ValueError("declared evidence tier required")
    when = instant(now)
    if not isinstance(territory, dict) or set(territory) != {"name", "entry", "nodes"} or len(territory["nodes"]) > 300:
        raise ValueError("bounded existing TerritoryGraph specification required")
    graph = TerritoryGraph(territory["name"])
    for value in territory["nodes"]:
        node = dict(value)
        if node.get("expires_at"):
            node["expires_at"] = instant(node["expires_at"])
        graph.add(ContentNode(**node), entry=node["node_id"] == territory["entry"])
    problems = graph.validate()
    if problems:
        raise ValueError("invalid territory: " + str(problems))
    db = _connect(root)
    try:
        seen = [e for e in _events(db) if e["subject"] == subject and e["tier"] == tier and e["kind"] == "view" and instant(e["at"]) <= when]
    finally:
        db.close()
    current = seen[-1]["node"] if seen else graph.entry_node_id
    graph.node(current)
    candidates = graph.node(current).next_doors if seen else [current]
    visited = {e["node"] for e in seen}
    allowed = [n for n in candidates if n not in visited and graph.publishable(n, when)[0]]
    return {"subject": subject, "tier": tier, "from": current, "next": allowed,
            "observed_events": [e["id"] for e in seen], "territory_hash": graph.hash(),
            "contact_performed": False, "authority_created": False}


QUERY_OPS = {"report": lambda a, r: report(r, a["tier"], a.get("lookback_hours", 720)),
             "route": lambda a, r: route(r, a["subject"], a["tier"], a["territory"], a["now"])}
APPLY_OPS = {"ingest": lambda a, r: ingest(r, a["events"])}
