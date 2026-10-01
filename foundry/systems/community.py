"""#32 Owned community records with portable member signatures and complete export.

Member public keys identify community participants, never kernel agents or
authority. Every mutation is signed for this community and retained verbatim.
No network, authentication server, real member acquisition or moderation
service is implied by these private, GREG-governed records.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3

from greg.capabilities import CapabilityError
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

VERSION = "owned-community/1"
MAX_EVENTS = 1024
NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}\Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def identifier(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError("invalid bounded community identifier")
    return value


def instant(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("invalid event timestamp")
    at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if at.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return at


def validate(event, community):
    required = {"version", "community", "id", "at", "public_key", "kind", "payload", "prev", "signature"}
    if not isinstance(event, dict) or set(event) != required or event["version"] != VERSION:
        raise ValueError("invalid signed community event")
    identifier(community)
    if event["community"] != community:
        raise ValueError("event belongs to a different community")
    identifier(event["id"]); instant(event["at"])
    if len(canonical(event)) > 16384:
        raise ValueError("community event exceeds size ceiling")
    try:
        key = bytes.fromhex(event["public_key"])
        signature = bytes.fromhex(event["signature"])
        if len(key) != 32 or len(signature) != 64:
            raise ValueError("invalid member key/signature size")
        Ed25519PublicKey.from_public_bytes(key).verify(signature, canonical(
            {k: v for k, v in event.items() if k != "signature"}))
    except (InvalidSignature, TypeError, ValueError) as exc:
        raise ValueError("invalid community member signature") from exc
    return "member:" + hashlib.sha256(key).hexdigest()


def project(events, community):
    members, posts, interactions, ids, heads = {}, {}, [], set(), {}
    for event in events:
        member = validate(event, community)
        if event["id"] in ids:
            raise ValueError("duplicate event in community history")
        ids.add(event["id"])
        if event["prev"] != heads.get(member):
            raise ValueError("member event chain is broken")
        heads[member] = "sha256:" + hashlib.sha256(canonical(event)).hexdigest()
        kind, payload = event["kind"], event["payload"]
        if not isinstance(payload, dict):
            raise ValueError("community payload must be an object")
        if kind == "join":
            if set(payload) != {"handle"} or not isinstance(payload["handle"], str) or not 1 <= len(payload["handle"]) <= 128:
                raise ValueError("join needs a bounded handle")
            if members.get(member, {}).get("active"):
                raise ValueError("member already active")
            members[member] = {"member": member, "public_key": event["public_key"], "handle": payload["handle"], "active": True}
        else:
            if not members.get(member, {}).get("active"):
                raise ValueError("active signed membership required")
            if kind in {"post", "reply", "edit"}:
                fields = {"body"} if kind == "post" else {"body", "target"}
                if set(payload) != fields or not isinstance(payload["body"], str) or not 1 <= len(payload["body"]) <= 8192:
                    raise ValueError("post needs bounded plain text")
                if kind != "post" and payload["target"] not in posts:
                    raise ValueError("interaction target is missing")
                if kind == "edit":
                    target = posts[payload["target"]]
                    if target["member"] != member:
                        raise ValueError("cannot edit another member's post")
                    target["body"] = payload["body"]; target["versions"].append(event["id"])
                else:
                    posts[event["id"]] = {"id": event["id"], "member": member, "body": payload["body"],
                                          "reply_to": payload.get("target"), "versions": [event["id"]]}
            elif kind == "react":
                if set(payload) != {"target", "reaction"} or payload["target"] not in posts or payload["reaction"] not in {"useful", "question", "correction"}:
                    raise ValueError("invalid community reaction")
            elif kind == "leave":
                if payload:
                    raise ValueError("leave has no payload")
                members[member]["active"] = False
            else:
                raise ValueError("unknown community interaction")
        interactions.append({"id": event["id"], "member": member, "kind": kind, "at": event["at"]})
    return {"members": members, "posts": posts, "interactions": interactions}


def _connect(root):
    Path(root).mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(Path(root) / "community.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, body TEXT NOT NULL)")
    return db


def _events(db):
    return [json.loads(row[0]) for row in db.execute("SELECT body FROM events ORDER BY seq")]


def ingest(root, community, events):
    identifier(community)
    if not isinstance(events, list) or len(events) > 128:
        raise ValueError("bounded event batch required")
    db = _connect(root)
    try:
        with db:
            retained = _events(db)
            if retained and retained[0]["community"] != community:
                raise ValueError("store already belongs to another community")
            indexed = {e["id"]: e for e in retained}
            added = []
            for event in events:
                validate(event, community)
                old = indexed.get(event["id"])
                if old is not None:
                    if canonical(old) != canonical(event):
                        raise ValueError("event id reused with different content")
                    continue
                indexed[event["id"]] = event
                added.append(event)
            if len(retained) + len(added) > MAX_EVENTS:
                raise ValueError("community event quota")
            state = project(retained + added, community)
            for event in added:
                db.execute("INSERT INTO events(id,body) VALUES (?,?)", (event["id"], canonical(event).decode()))
        return {"added": len(added), "events": len(retained) + len(added),
                "members": len(state["members"]), "posts": len(state["posts"]), "authority_created": False}
    finally:
        db.close()


def export(root, community, offset=0, limit=32):
    identifier(community)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 32:
        raise ValueError("bounded export page required")
    db = _connect(root)
    try:
        events = _events(db)
        project(events, community)
        page = events[offset:offset + limit]
        return {"version": VERSION, "community": community, "events": page, "total": len(events),
                "next_offset": offset + len(page) if offset + len(page) < len(events) else None,
                "history_hash": "sha256:" + hashlib.sha256(canonical(events)).hexdigest(),
                "scope": "portable signed local records; no kernel authority or proof of real-world identity"}
    finally:
        db.close()


def view(root, community, offset=0, limit=32):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 32:
        raise ValueError("bounded community view page required")
    db = _connect(root)
    try:
        state = project(_events(db), identifier(community))
        return {"members": list(state["members"].values())[offset:offset + limit],
                "posts": list(state["posts"].values())[offset:offset + limit],
                "interactions": state["interactions"][offset:offset + limit],
                "totals": {k: len(v) for k, v in state.items()}, "offset": offset, "limit": limit,
                "authority_created": False}
    finally:
        db.close()


def render(root, community):
    state = view(root, community)
    return {"html": "<!doctype html><meta charset='utf-8'><title>Owned community</title>" +
            "".join("<article><h2>" + html.escape(p["id"]) + "</h2><p>" +
                    html.escape(p["body"]) + "</p></article>" for p in state["posts"]),
            "posts": len(state["posts"]), "publicly_served": False}


def observed(root, community):
    try:
        result = view(root, community)
        return {"intact": True, "totals": result["totals"], "authority_created": False}
    except (ValueError, CapabilityError, sqlite3.DatabaseError) as exc:
        return {"intact": False, "totals": {}, "reason": type(exc).__name__, "authority_created": False}


QUERY_OPS = {"summary": lambda a, r: observed(r, a["community"]), "export": lambda a, r: export(r, a["community"], a.get("offset", 0), a.get("limit", 32)),
             "view": lambda a, r: view(r, a["community"], a.get("offset", 0), a.get("limit", 32)),
             "render": lambda a, r: render(r, a["community"])}
APPLY_OPS = {"ingest": lambda a, r: ingest(r, a["community"], a["events"])}
