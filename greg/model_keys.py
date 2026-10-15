"""A model vendor that refuses GREG's key: the route is benched until the founder stores a new key.

The router (``greg/models.py``) treats every availability failure alike: it demotes a failing route and tries it
again after a cooldown. That is right for an outage and wrong for a refused key (HTTP 401/403,
``authentication_error``): the same key will be refused again, each retry is another failed authentication at the
vendor, and the founder is never told the key needs replacing.

So the body records which key was refused, as a short fingerprint (the first 12 hex digits of its SHA-256, never the
key), and keeps that route out of the router while it still holds that key: from the refusal on, and again after a
restart, from the record. Storing a new key (``greg secret set anthropic_api_key``) gives the route a different
fingerprint, so the next body tries it. ``summary`` is what the founder sees.
"""
from __future__ import annotations

import hashlib

AUTH = "auth"                                     # greg.models.AUTH, kept here so this module imports nothing frozen
KEY_HANDLES = {"anthropic": "anthropic_api_key", "openai": "openai_api_key"}


def fingerprint(secret) -> str | None:
    return "key:" + hashlib.sha256(secret.encode()).hexdigest()[:12] if isinstance(secret, str) and secret else None


def route_key(route) -> str | None:
    """Which key a paid route holds, as a fingerprint: the confined route keeps it, an in-process SDK client has it."""
    return fingerprint(getattr(route, "_api_key", None) or getattr(getattr(route, "client", None), "api_key", None))


def refusals(events) -> dict:
    """route name -> the refusal, when the route's latest recorded outcome is a refused key."""
    last = {}
    for event in events:
        last[event.get("route")] = event
    return {name: e for name, e in last.items()
            if e.get("outcome") == "failed" and e.get("class") == AUTH and e.get("credential")}


def bench(router, name: str) -> None:
    router.routes = [r for r in router.routes if r.name != name]


def attach(router, journal) -> None:
    """Record refusals with the key's fingerprint and bench the route while it holds that key."""
    keys = {r.name: route_key(r) for r in router.routes}
    for name, refusal in refusals(e.payload for e in journal.replay("model.route")).items():
        if keys.get(name) and refusal["credential"] == keys[name]:
            bench(router, name)

    def record(event):
        if event.get("outcome") == "failed" and event.get("class") == AUTH and keys.get(event["route"]):
            event = {**event, "credential": keys[event["route"]]}
            bench(router, event["route"])
        journal.record("model.route", event, key=[event["route"], event["at"], event["outcome"]])
    router.record = record


def summary(journal, broker) -> list[dict]:
    """The refused keys, newest state per route, and whether the founder has stored a different key since."""
    out = []
    for name, refusal in sorted(refusals(e.payload for e in journal.replay("model.route")).items()):
        handle = KEY_HANDLES.get(refusal.get("provider"))
        try:
            current = fingerprint(broker.resolve(handle, declared=(handle,))) if handle else None
        except Exception:                          # no key stored any more, or the broker refuses: not replaced
            current = None
        out.append({"route": name, "refused_at": refusal["at"], "handle": handle,
                    "replaced": current is not None and current != refusal["credential"]})
    return out
