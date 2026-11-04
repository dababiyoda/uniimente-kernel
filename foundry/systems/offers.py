"""#37/#54 Local machine-readable media offers and signed test transactions.

Actual canon media is delivered and independently re-read. Orders/acceptances
prove key possession and pinned byte contracts, not buyer identity or payment.
All consideration is fixture bookkeeping; there is no payment rail, public
offer activation or external agent authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from foundry.systems import cas, journeys, media, reputation, versions
from foundry.systems.community import canonical, identifier, instant
from greg.artifacts import ArtifactStore
from greg.capabilities import CapabilityError

VERSION = "owned-test-commerce/1"
MAX_ORDERS = 128


def store(root):
    root = Path(root)
    return root.parent / "system-54" if root.name == "system-37" else root


def _media(root):
    return store(root).parent / "system-35"


def _db(root):
    root = store(root); root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "orders.sqlite")
    db.execute("CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, body TEXT NOT NULL, receipt TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS acceptances (id TEXT PRIMARY KEY REFERENCES orders(id), body TEXT NOT NULL)")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def _signed(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields) | {"signature", "public_key"} or len(canonical(value)) > 16384:
        raise ValueError("invalid bounded signed commerce message")
    try:
        key = bytes.fromhex(value["public_key"]); signature = bytes.fromhex(value["signature"])
        if len(key) != 32 or len(signature) != 64:
            raise ValueError("invalid commerce signing material")
        Ed25519PublicKey.from_public_bytes(key).verify(signature, canonical(
            {k: v for k, v in value.items() if k != "signature"}))
    except (InvalidSignature, TypeError, ValueError) as exc:
        raise ValueError("commerce signature does not verify") from exc
    return "peer:" + hashlib.sha256(key).hexdigest()


def publish(root, value, reason, expected_parent="__head__"):
    if not isinstance(value, dict) or set(value) != {"id", "manifest", "price_cents", "currency", "description"}:
        raise ValueError("invalid native offer contract")
    identifier(value["id"])
    if type(value["price_cents"]) is not int or not 1 <= value["price_cents"] <= 10**9:
        raise ValueError("positive bounded integer consideration required")
    if not isinstance(value["currency"], str) or len(value["currency"]) != 3 or not all("A" <= c <= "Z" for c in value["currency"]):
        raise ValueError("declared consideration currency required")
    if not isinstance(value["description"], str) or not 1 <= len(value["description"]) <= 1024:
        raise ValueError("bounded offer description required")
    media.inspect(_media(root), value["manifest"])
    record = versions.commit(store(root) / "catalog", value["id"],
                             {**value, "version": VERSION, "mode": "fixture", "capability": "canon_media_delivery"},
                             reason=reason, evidence=[value["manifest"]], expected_parent=expected_parent)
    return {"offer": value["id"], "version": record["n"], "version_address": record["address"],
            "mode": "fixture", "authority_created": False}


def discover(root, id, n=None):
    identifier(id)
    rows = versions.history(store(root) / "catalog", id)
    if n is not None and (type(n) is not int or n < 1):
        raise ValueError("positive offer version required")
    chosen = rows[0] if rows and n is None else next((r for r in rows if r["n"] == n), None)
    if chosen is None:
        raise ValueError("offer version is missing")
    value = versions.content(store(root) / "catalog", id, chosen["n"])
    if value["version"] != VERSION or value["mode"] != "fixture":
        raise ValueError("unknown offer contract")
    media.inspect(_media(root), value["manifest"])
    return {**value, "offer_version": chosen["n"], "version_address": chosen["address"],
            "grants_access": False, "scope": "local test offer; no verified price/demand or public activation"}


def _delivery(root, receipt):
    if set(receipt) != {"version", "id", "offer", "offer_version", "buyer", "consideration", "manifest", "assets", "at", "mode"}:
        raise ValueError("invalid delivery receipt")
    if receipt["version"] != VERSION or receipt["mode"] != "fixture":
        raise ValueError("unknown test receipt")
    manifest = json.loads(ArtifactStore(_media(root) / "artifacts").read(receipt["manifest"]))
    if receipt["assets"] != manifest["assets"]:
        raise ValueError("delivery assets differ from pinned manifest")
    media.inspect(_media(root), receipt["manifest"])
    files = ArtifactStore(store(root) / "deliveries")
    for asset in receipt["assets"]:
        if files.read(asset["address"]) != ArtifactStore(_media(root) / "artifacts").read(asset["address"]):
            raise ValueError("delivered product differs from its source")
    return True


def _order(root, order):
    fields = {"version", "mode", "id", "offer", "offer_version", "version_address", "price_cents", "currency", "at"}
    buyer = _signed(order, fields)
    identifier(order["id"]); instant(order["at"])
    if type(order["price_cents"]) is not int:
        raise ValueError("order consideration must be integer minor units")
    if order["version"] != VERSION or order["mode"] != "fixture":
        raise ValueError("only local test orders are executable")
    offer = discover(root, order["offer"], order["offer_version"])
    if (order["version_address"], order["price_cents"], order["currency"]) != (
            offer["version_address"], offer["price_cents"], offer["currency"]):
        raise ValueError("order diverges from pinned offer terms")
    source = ArtifactStore(_media(root) / "artifacts")
    manifest = json.loads(source.read(offer["manifest"]))
    receipt = {"version": VERSION, "mode": "fixture", "id": order["id"], "offer": order["offer"],
               "offer_version": order["offer_version"], "buyer": buyer,
               "consideration": {"amount_cents": order["price_cents"], "currency": order["currency"],
                                 "kind": "fixture_only_no_payment"},
               "manifest": offer["manifest"], "assets": manifest["assets"], "at": order["at"]}
    return buyer, offer, receipt


def fulfill(root, order):
    buyer, offer, expected = _order(root, order)
    db = _db(root)
    try:
        with db:
            prior = db.execute("SELECT body,receipt FROM orders WHERE id=?", (order["id"],)).fetchone()
            if prior:
                if canonical(json.loads(prior[0])) != canonical(order):
                    raise ValueError("order id reused with different content")
                receipt = json.loads(prior[1])
                if canonical(receipt) != canonical(expected):
                    raise ValueError("retained receipt differs from pinned order")
                _delivery(root, receipt)
                return {"receipt": receipt, "receipt_hash": "sha256:" + hashlib.sha256(canonical(receipt)).hexdigest(),
                        "reused": True, "paid": False}
            if db.execute("SELECT count(*) FROM orders").fetchone()[0] >= MAX_ORDERS:
                raise ValueError("test order quota")
            source = ArtifactStore(_media(root) / "artifacts")
            manifest = json.loads(source.read(offer["manifest"]))
            destination = ArtifactStore(store(root) / "deliveries")
            for asset in manifest["assets"]:
                destination.put(source.read(asset["address"]))
            receipt = expected
            _delivery(root, receipt)
            db.execute("INSERT INTO orders VALUES (?,?,?)",
                       (order["id"], canonical(order).decode(), canonical(receipt).decode()))
        return {"receipt": receipt, "receipt_hash": "sha256:" + hashlib.sha256(canonical(receipt)).hexdigest(),
                "reused": False, "paid": False}
    finally:
        db.close()


def accept(root, message):
    fields = {"version", "mode", "id", "receipt_hash", "verdict", "at"}
    buyer = _signed(message, fields)
    identifier(message["id"]); instant(message["at"])
    if message["version"] != VERSION or message["mode"] != "fixture" or message["verdict"] not in {"accept", "reject"}:
        raise ValueError("invalid test acceptance")
    db = _db(root)
    try:
        with db:
            row = db.execute("SELECT body,receipt FROM orders WHERE id=?", (message["id"],)).fetchone()
            if not row:
                raise ValueError("unknown test order")
            receipt = json.loads(row[1])
            _, _, canonical_receipt = _order(root, json.loads(row[0]))
            if canonical(receipt) != canonical(canonical_receipt):
                raise ValueError("retained receipt differs from pinned order")
            expected = "sha256:" + hashlib.sha256(canonical(receipt)).hexdigest()
            if receipt["buyer"] != buyer or message["receipt_hash"] != expected:
                raise ValueError("acceptance buyer or receipt differs")
            if instant(message["at"]) < instant(receipt["at"]):
                raise ValueError("acceptance predates delivery")
            if message["verdict"] == "accept":
                _delivery(root, receipt)
            old = db.execute("SELECT body FROM acceptances WHERE id=?", (message["id"],)).fetchone()
            if old and canonical(json.loads(old[0])) != canonical(message):
                raise ValueError("acceptance is already retained")
            if not old:
                db.execute("INSERT INTO acceptances VALUES (?,?)", (message["id"], canonical(message).decode()))
            if message["verdict"] == "accept":
                journeys.ingest(store(root).parent / "system-34", [{
                    "id": "purchase:" + hashlib.sha256(canonical(message)).hexdigest(),
                    "at": message["at"], "subject": buyer, "kind": "purchase", "node": receipt["offer"],
                    "source_ref": expected, "tier": "fixture",
                    "amount_cents": receipt["consideration"]["amount_cents"],
                    "currency": receipt["consideration"]["currency"], "receipt": expected}])
        return {"id": message["id"], "verdict": message["verdict"], "mode": "fixture", "paid": False}
    finally:
        db.close()


def history(root):
    db = _db(root)
    try:
        out = []
        for body, raw, accepted in db.execute(
                "SELECT o.body,o.receipt,a.body FROM orders o LEFT JOIN acceptances a ON a.id=o.id ORDER BY o.id"):
            order, receipt = json.loads(body), json.loads(raw)
            buyer, offer, expected = _order(root, order)
            if canonical(receipt) != canonical(expected):
                raise ValueError("retained receipt differs from pinned order")
            _delivery(root, receipt)
            acceptance = json.loads(accepted) if accepted else None
            if acceptance:
                signer = _signed(acceptance, {"version", "mode", "id", "receipt_hash", "verdict", "at"})
                if signer != buyer or acceptance["receipt_hash"] != "sha256:" + hashlib.sha256(canonical(receipt)).hexdigest() or \
                        acceptance["id"] != order["id"] or acceptance["version"] != VERSION or acceptance["mode"] != "fixture" or \
                        acceptance["verdict"] not in {"accept", "reject"} or instant(acceptance["at"]) < instant(receipt["at"]):
                    raise ValueError("retained acceptance differs")
            out.append({"order": order, "receipt": receipt, "acceptance": acceptance})
        return out
    finally:
        db.close()


def inspect(root):
    try:
        rows = history(root)
        return {"intact": True, "delivered": len(rows), "accepted": sum(
            r["acceptance"] is not None and r["acceptance"]["verdict"] == "accept" for r in rows),
                "mode": "fixture", "paid": False}
    except (CapabilityError, ValueError, KeyError, versions.VersionError, cas.IntegrityError, sqlite3.DatabaseError) as exc:
        return {"intact": False, "delivered": 0, "accepted": 0, "reason": type(exc).__name__, "paid": False}


def rated(root, now):
    instant(now)
    unique = {}
    for row in history(root):
        acceptance, receipt = row["acceptance"], row["receipt"]
        if acceptance:
            key = (receipt["offer"], receipt["buyer"])
            if key in unique and instant(unique[key]["at"]) > instant(acceptance["at"]):
                continue
            unique[key] = {"subject": receipt["offer"], "context": "fixture_delivery", "at": acceptance["at"],
                           "verdict": "VERIFIED" if acceptance["verdict"] == "accept" else "REFUTED",
                           "evidence": [acceptance["receipt_hash"]]}
    return {"mode": "fixture", "scope": "distinct signed peer/offer test deliveries; no real-market reputation",
            **reputation.score(list(unique.values()), now=now)}


QUERY_OPS = {"discover": lambda a, r: discover(r, a["id"], a.get("version")),
             "inspect": lambda a, r: inspect(r), "history": lambda a, r: {"transactions": history(r)},
             "reputation": lambda a, r: rated(r, a["now"])}
APPLY_OPS = {"publish": lambda a, r: publish(r, a["offer"], a["reason"], a.get("expected_parent", "__head__")),
             "fulfill": lambda a, r: fulfill(r, a["order"]),
             "accept": lambda a, r: accept(r, a["acceptance"])}
