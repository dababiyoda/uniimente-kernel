"""Venture rehearsal: the First Mission's deliverable taken through GREG's governed commerce loop, as a FIXTURE.

The First Mission ends with a private dossier and its canon (title, body, sources, declared rights). This module
turns that canon into ONE signed mission that exercises the Mind-line company path on the Foundry bridge:

  assemble    #49 media company: charter with the required editorial rules and disclosure, canon, territory, offer
  deliver     #54 offers: a FIXTURE buyer's signed order is fulfilled against the offer version it names
  accept      #54 offers: the FIXTURE buyer's signed acceptance binds the exact delivery receipt hash
  reconcile   #49: the accepted delivery is posted to the company's FIXTURE books and must balance to the cent

Every success check is a read-only Foundry sensor, so the independent appraisal re-observes the same stores and
refutes a book or receipt edited after the fact.

What it is not: the buyer is a deterministic fixture key, not a person; the consideration is a fixture amount in a
fixture ledger account, and no payment rail is called (``money_moved`` stays false); nothing is published (the owned
page is loopback-only). It demonstrates that GREG's pieces cooperate on a commercial transaction; it is not
evidence that anyone would buy anything. External revenue stays a hypothesis until a real customer acts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

FIXTURE = "FIXTURE"
FIXTURE_BUYER_SEED = bytes([41]) * 32          # deterministic, published: it can authenticate no one
AT = "2026-10-14T12:00:00Z"


def _buyer():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(FIXTURE_BUYER_SEED)


def _sign(message: dict) -> dict:
    from foundry.systems import community
    from greg.founder import public_bytes
    key = _buyer()
    message = {**message, "public_key": public_bytes(key.public_key()).hex()}
    return {**message, "signature": key.sign(community.canonical(message)).hex()}


def territory() -> dict:
    """A three-door fixture territory ending at the owned exit where the offer lives."""
    nodes = []
    for node, doors, exit_ in (("entry", ["deep"], False), ("deep", ["offer"], False), ("offer", [], True)):
        nodes.append({"node_id": node, "question": f"Fixture question at {node}", "artifact": f"sha256:{node}",
                      "capability_taught": node, "evidence_level": 0.9, "evidence_refs": ["fixture:evidence"],
                      "next_doors": doors, "owned_exit": exit_, "owned_ground": "owned:hub" if exit_ else ""})
    return {"name": "owned", "entry": "entry", "nodes": nodes}


def company_spec(canon: dict, *, price_cents: int = 1200) -> dict:
    from foundry.company import REQUIRED_EDITORIAL_RULES
    from foundry.systems import media
    canon = media.canon(dict(canon))
    if not isinstance(price_cents, int) or isinstance(price_cents, bool) or not 1 <= price_cents <= 1_000_000:
        raise ValueError("fixture price is a whole number of cents from 1 to 1,000,000")
    return {"charter": {"name": "owned", "persona": f"{FIXTURE}: disclosed synthetic company for a rehearsal",
                        "synthetic_disclosure": True, "visual_canon": {"style": "owned graphic"},
                        "editorial_rules": list(REQUIRED_EDITORIAL_RULES), "narrative_world": "Founder rehearsal",
                        "owned_hub": "loopback:owned", "subscriber_list": "fixture:list",
                        "products": ["offer"], "community": "owned"},
            "canon": canon, "territory": territory(),
            "offers": [{"id": "offer", "price_cents": price_cents, "currency": "USD",
                        "description": f"{FIXTURE}: private delivery of '{canon['title'][:120]}'"}]}


def plan(canon: dict, *, price_cents: int = 1200) -> dict:
    """Dry-run the loop in a scratch folder to pin the fixture order and acceptance the signed mission will carry."""
    from foundry.systems import media_company, offers
    spec = company_spec(canon, price_cents=price_cents)
    with tempfile.TemporaryDirectory(prefix="greg-venture-plan-") as scratch:
        root = Path(scratch)
        media_company.assemble(root / "system-49", spec)
        ref = offers.discover(root / "system-54", "offer")
        order = _sign({"version": offers.VERSION, "mode": "fixture", "id": "fixture-order-1", "offer": "offer",
                       "offer_version": ref["offer_version"], "version_address": ref["version_address"],
                       "price_cents": ref["price_cents"], "currency": ref["currency"], "at": AT})
        delivery = offers.fulfill(root / "system-54", order)
        acceptance = _sign({"version": offers.VERSION, "mode": "fixture", "id": delivery["receipt"]["id"],
                            "receipt_hash": delivery["receipt_hash"], "verdict": "accept", "at": AT})
    return {"spec": spec, "order": order, "acceptance": acceptance, "price_cents": price_cents}


def latest_canon(deliver_root: Path) -> tuple[dict, str]:
    """The canon of the newest First Mission dossier, rebuilt from its retained JSON; refuses when there is none."""
    folder = Path(deliver_root) / "first-mission"
    dossiers = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime) if folder.is_dir() else []
    if not dossiers:
        raise FileNotFoundError("no First Mission dossier yet: run the Founder's First Mission first")
    data = dossiers[-1].read_bytes()
    doc = json.loads(data)
    digest = hashlib.sha256(data).hexdigest()
    titles = "; ".join(c["title"][:140] for c in doc.get("selected", []))
    canon = {"canon_id": f"venture-{digest[:12]}", "title": ("Opportunity dossier: " + doc["objective"]["title"])[:250],
             "body": (f"{doc['objective']['outcome']} Selected work: {titles}. {doc.get('lesson', '')}")[:4000],
             "source_refs": [f"dossier sha256:{digest}"] + [f"{k} {v}" for k, v in doc["sources"].items()],
             "rights": "Founder's own repository content; private rehearsal; not published."}
    return canon, str(dossiers[-1])


def venture_rehearsal(*, canon: dict, price_cents: int = 1200, run: str = "rehearsal", horizon_days: float = 1,
                      founder_expression: str | None = None) -> dict:
    pinned = plan(canon, price_cents=price_cents)
    digest = hashlib.sha256(json.dumps([pinned["spec"]["canon"]["canon_id"], price_cents, run]).encode()).hexdigest()[:10]
    mission_id = f"m:venture-rehearsal-{digest}"
    checks, strategies = [], []
    for check_id, system, field, value, what in (
            ("assembled", 49, "result.intact", True, "the fixture company is assembled and intact"),
            ("delivered", 54, "result.delivered", 1, "one fixture order is delivered against its offer version"),
            ("accepted", 54, "result.accepted", 1, "the fixture buyer's signed acceptance binds the delivery receipt"),
            ("reconciled", 49, "result.fixture_finance.totals.revenue", price_cents,
             "the fixture books post exactly the accepted consideration")):
        checks.append({"check_id": check_id, "description": what,
                       "sensor": {"capability": "foundry.query", "target": "foundry:venture",
                                  "params": {"system": system, "op": "inspect"}},
                       "predicate": {"op": "equals", "field": field, "value": value}})
    for action_id, system, op, args, advances, why in (
            ("assemble", 49, "assemble", {"spec": pinned["spec"]}, "assembled",
             "charter, canon, territory and offer under the required editorial rules"),
            ("deliver", 54, "fulfill", {"order": pinned["order"]}, "delivered", "fulfill the FIXTURE buyer's signed order"),
            ("accept", 54, "accept", {"acceptance": pinned["acceptance"]}, "accepted",
             "record the FIXTURE buyer's signed acceptance of the exact delivery"),
            ("reconcile", 49, "reconcile", {}, "reconciled", "post the accepted consideration to the FIXTURE books")):
        strategies.append({"action_id": action_id, "capability": "foundry.apply", "target": "foundry:venture",
                           "params": {"system": system, "op": op, "args": args}, "advances": [advances],
                           "rationale": why + "; no rail is called and nothing is published"})
    from greg.templates import _horizon
    return {"mission_id": mission_id,
            "founder_expression": founder_expression or (
                f"[{FIXTURE}] Rehearse selling and delivering my First Mission dossier through GREG's company loop."),
            "intended_effect": f"{FIXTURE} commerce loop: offer, signed order, delivery, signed acceptance and books "
                               "reconciled to the cent, each re-observed by the appraisal; no money moves",
            "priority": 40, "closure": {"kind": "bounded"}, "success_checks": checks, "strategies": strategies,
            "light_cone": {"capabilities": ["foundry.apply", "foundry.query"], "targets": ["foundry:venture"],
                           "max_consequence_class": "internal_write", "budget_usd": 0,
                           "horizon": _horizon(horizon_days)}}


def books(home: Path, mission_id: str) -> dict | None:
    """Read-only view of a rehearsal's fixture books for Mission Control (re-derived, never cached)."""
    from foundry.systems import accounting
    root = Path(home) / "workspace" / mission_id.replace(":", "_") / "foundry" / "system-49" / "fixture-books"
    if not root.is_dir():
        return None
    try:
        return {"mission_id": mission_id, "mode": FIXTURE, "money_moved": False, **accounting.trial_balance(root)}
    except Exception as exc:    # a corrupted book is shown as such, never hidden
        return {"mission_id": mission_id, "mode": FIXTURE, "money_moved": False, "error": type(exc).__name__}
