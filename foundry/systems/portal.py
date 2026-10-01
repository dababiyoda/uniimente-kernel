"""#31 Versioned owned pages, served privately by GREG's existing console.

Canonical bytes and provenance declarations are retained using existing stores.
Production happens through foundry.apply; the console serves only bytes named
in successful canonical Gate receipts. No public deployment or rights proof.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from foundry.systems import cas, media, versions
from greg.artifacts import ArtifactStore
from greg.capabilities import CapabilityError

VERSION = "owned-page/1"


def _render(value):
    title, body = html.escape(value["title"]), html.escape(value["body"])
    refs = "".join("<li>" + html.escape(r) + "</li>" for r in value["source_refs"])
    return (f"<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{title}</title><main><h1>{title}</h1><p>{body}</p>"
            f"<details><summary>Sources and declared rights</summary><ul>{refs}</ul>"
            f"<p>{html.escape(value['rights'])}</p><p>Declarations are not independent rights verification.</p></details>"
            "</main></html>").encode()


def build(root, value, reason, expected_parent="__head__"):
    value = media.canon(value)
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1024:
        raise ValueError("bounded page version reason required")
    name = value["canon_id"]
    # Reuse #3's object naming/CAS conflict checks and GREG's byte store.
    versions._ref(Path(root) / "versions", name)
    objects = ArtifactStore(Path(root) / "artifacts")
    canon_address, _ = objects.put(media._json(value))
    address, _ = objects.put(_render(value))
    record = versions.commit(Path(root) / "versions", name,
                             {"version": VERSION, "canon": canon_address, "page": address},
                             reason=reason, evidence=value["source_refs"], expected_parent=expected_parent)
    return {"kind": "owned-page", "name": name, "version": record["n"], "address": address,
            "version_address": record["address"], "canon": canon_address, "title": value["title"],
            "publicly_served": False, "authority_created": False}


def retrieve(root, name, n=None):
    if n is not None and (type(n) is not int or n < 1):
        raise ValueError("positive page version required")
    history = versions.history(Path(root) / "versions", name)
    if not history:
        raise versions.VersionError("owned page is missing")
    chosen = history[0] if n is None else next((r for r in history if r["n"] == n), None)
    if chosen is None:
        raise versions.VersionError("owned page version is missing")
    document = versions.content(Path(root) / "versions", name, chosen["n"])
    if set(document) != {"version", "canon", "page"} or document["version"] != VERSION:
        raise ValueError("unknown owned page contract")
    objects = ArtifactStore(Path(root) / "artifacts")
    value = media.canon(json.loads(objects.read(document["canon"])))
    content = objects.read(document["page"])
    if value["canon_id"] != name or content != _render(value):
        raise ValueError("owned page diverges from canonical content")
    return {"intact": True, "kind": "owned-page", "name": name, "version": chosen["n"],
            "address": document["page"], "version_address": chosen["address"], "canon": document["canon"],
            "title": value["title"], "html": content.decode(),
            "provenance": {"source_refs": value["source_refs"], "rights": value["rights"],
                           "status": "declared_not_independently_verified"}, "authority_created": False}


def observed(root, name, n=None):
    try:
        result = retrieve(root, name, n)
        return {k: v for k, v in result.items() if k != "html"}
    except (CapabilityError, versions.VersionError, cas.IntegrityError, ValueError, KeyError, FileNotFoundError) as exc:
        return {"intact": False, "name": name, "reason": type(exc).__name__, "authority_created": False}


QUERY_OPS = {"inspect": lambda a, r: observed(r, a["name"], a.get("version")),
             "retrieve": lambda a, r: retrieve(r, a["name"], a.get("version"))}
APPLY_OPS = {"build": lambda a, r: build(r, a["canon"], a["reason"], a.get("expected_parent", "__head__"))}
