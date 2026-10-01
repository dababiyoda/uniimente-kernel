"""Actual owned-company loop; fixture contracts never masquerade as market evidence."""
from copy import deepcopy
import hashlib
import http.client
import json
import sqlite3
import threading
from urllib.parse import quote

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from foundry.company import REQUIRED_EDITORIAL_RULES
from foundry.systems import accounting, cas, community, journeys, media, media_company, offers, portal, versions
from greg import foundry_bridge
from greg.artifacts import ArtifactStore
from greg.body import Body
from greg.capabilities import CapabilityError
from greg.console import Console, owned_pages, serve
from greg.founder import public_bytes
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace
from tests.unit.test_greg_community_journeys import event, member_events, territory
from tests.unit.test_greg_foundry_worker import context
from tests.unit.test_greg_media import canon


def spec():
    return {"charter": {
        "name": "owned", "persona": "Disclosed synthetic fixture",
        "synthetic_disclosure": True, "visual_canon": {"style": "owned graphic"},
        "editorial_rules": list(REQUIRED_EDITORIAL_RULES), "narrative_world": "Owned fixture",
        "owned_hub": "loopback:owned", "subscriber_list": "fixture:list",
        "products": ["offer"], "community": "owned"},
        "canon": canon(), "territory": territory(),
        "offers": [{"id": "offer", "price_cents": 1200, "currency": "USD",
                    "description": "Canon graphics and tone cues, fixture delivery only"}]}


def peer():
    return Ed25519PrivateKey.from_private_bytes(bytes([29]) * 32)


def sign(key, message):
    message = {**message, "public_key": public_bytes(key.public_key()).hex()}
    return {**message, "signature": key.sign(community.canonical(message)).hex()}


def order(root, id="order-1"):
    ref = offers.discover(root, "offer")
    return sign(peer(), {"version": offers.VERSION, "mode": "fixture", "id": id,
                        "offer": "offer", "offer_version": ref["offer_version"],
                        "version_address": ref["version_address"], "price_cents": ref["price_cents"],
                        "currency": ref["currency"], "at": "2026-10-01T12:02:00Z"})


def acceptance(delivery, verdict="accept", key=None):
    return sign(key or peer(), {"version": offers.VERSION, "mode": "fixture",
                              "id": delivery["receipt"]["id"], "receipt_hash": delivery["receipt_hash"],
                              "verdict": verdict, "at": "2026-10-01T12:03:00Z"})


def test_signed_peer_gets_actual_bytes_accepts_pinned_terms_and_feeds_memory_and_reputation(tmp_path):
    root = tmp_path / "system-49"
    assembled = media_company.assemble(root, spec())
    market = tmp_path / "system-54"
    native = order(market)
    delivery = offers.fulfill(market, native)
    assert delivery["paid"] is False and len(delivery["receipt"]["assets"]) == 5
    for asset in delivery["receipt"]["assets"]:
        assert ArtifactStore(market / "deliveries").read(asset["address"]) == \
               ArtifactStore(tmp_path / "system-35" / "artifacts").read(asset["address"])
    assert offers.fulfill(market, native)["reused"]
    ack = acceptance(delivery)
    offers.accept(market, ack); offers.accept(market, ack)
    assert offers.inspect(market)["accepted"] == 1
    assert journeys.report(tmp_path / "system-34", "fixture")["events"] == 1
    assert journeys.report(tmp_path / "system-34", "observed")["events"] == 0
    assert offers.rated(market, "2026-10-01T12:04:00Z")["mode"] == "fixture"
    assert media_company.reconcile(root)["newly_reconciled"] == ["order-1"]
    assert media_company.reconcile(root)["newly_reconciled"] == []
    state = media_company.observed(root)
    assert state["intact"] and state["fixture_finance"]["totals"]["revenue"] == 1200
    assert state["money_moved"] is False and state["operational_ratification"] is False
    assert media_company.assemble(root, spec()) == assembled


def test_signed_terms_replay_foreign_acceptance_and_corrupt_receipt_are_refused(tmp_path):
    media_company.assemble(tmp_path / "system-49", spec())
    root = tmp_path / "system-54"
    native = order(root)
    tampered = deepcopy(native); tampered["price_cents"] += 1
    with pytest.raises(ValueError, match="signature"):
        offers.fulfill(root, tampered)
    wrong = sign(peer(), {k: v for k, v in {**native, "price_cents": 7}.items()
                          if k not in {"signature", "public_key"}})
    with pytest.raises(ValueError, match="pinned"):
        offers.fulfill(root, wrong)
    delivery = offers.fulfill(root, native)
    with pytest.raises(ValueError, match="buyer"):
        offers.accept(root, acceptance(delivery, key=Ed25519PrivateKey.generate()))
    changed = deepcopy(native); changed["at"] = "2026-10-01T12:02:01Z"
    changed = sign(peer(), {k: v for k, v in changed.items() if k not in {"signature", "public_key"}})
    with pytest.raises(ValueError, match="reused"):
        offers.fulfill(root, changed)
    db = sqlite3.connect(root / "orders.sqlite")
    bad = deepcopy(delivery["receipt"]); bad["consideration"]["amount_cents"] = 999
    with db:
        db.execute("UPDATE orders SET receipt=? WHERE id=?", (json.dumps(bad), native["id"]))
    db.close()
    assert offers.inspect(root)["intact"] is False
    assert media_company.observed(tmp_path / "system-49")["intact"] is False
    with pytest.raises(ValueError, match="pinned order"):
        offers.accept(root, acceptance(delivery))


def test_reputation_deduplicates_peer_offer_not_order_ids_and_delivery_corruption_refutes(tmp_path):
    media_company.assemble(tmp_path / "system-49", spec())
    root = tmp_path / "system-54"
    first = offers.fulfill(root, order(root, "one")); offers.accept(root, acceptance(first))
    score = offers.rated(root, "2026-10-01T12:04:00Z")
    second = offers.fulfill(root, order(root, "two")); offers.accept(root, acceptance(second))
    assert offers.rated(root, "2026-10-01T12:04:00Z") == score
    ArtifactStore(root / "deliveries").path(first["receipt"]["assets"][0]["address"]).write_bytes(b"corrupted")
    assert offers.inspect(root)["intact"] is False


@pytest.mark.parametrize("mutation", ["empty", "substitute", "provenance", "claims"])
def test_hash_valid_but_noncanonical_media_manifest_cannot_close_production(tmp_path, mutation):
    result = media.produce(tmp_path, canon())
    store = ArtifactStore(tmp_path / "artifacts")
    manifest = json.loads(store.read(result["manifest"]))
    if mutation == "empty":
        manifest["assets"] = []
    elif mutation == "substitute":
        address, _ = store.put(b"hash-valid fake media")
        manifest["assets"][0]["address"] = address
        manifest["assets"][0]["bytes"] = 21
    elif mutation == "provenance":
        manifest["canon_id"] = "different"
    else:
        manifest["limitations"] = "cinematic narration; proven revenue"
    address, _ = store.put(media._json(manifest))
    assert media.observed(tmp_path, address)["intact"] is False


def test_company_revisions_require_expected_inputs_and_receipts_bind_even_hash_valid_books(tmp_path):
    root = tmp_path / "system-49"
    original = spec(); media_company.assemble(root, original)
    changed = deepcopy(original); changed["canon"]["body"] = "Revised canon"
    with pytest.raises(ValueError, match="expected"):
        media_company.assemble(root, changed)
    prior = json.loads((root / "assembly.json").read_text())["spec_hash"]
    updated = media_company.assemble(root, changed, prior)
    assert updated["portal"]["version"] == 2 and media_company.observed(root)["intact"]
    delivery = offers.fulfill(tmp_path / "system-54", order(tmp_path / "system-54"))
    offers.accept(tmp_path / "system-54", acceptance(delivery))
    media_company.reconcile(root)
    # A newly valid accounting hash is still not a signed delivery contract.
    path = root / "fixture-books" / "journal.jsonl"
    entry = json.loads(path.read_text())
    entry["memo"] = "fabricated closure"
    entry["hash"] = accounting._hash({k: v for k, v in entry.items() if k != "hash"})
    path.write_text(json.dumps(entry) + "\n")
    assert media_company.observed(root)["intact"] is False
    with pytest.raises(ValueError, match="posting"):
        media_company.reconcile(root)


def test_greg_reaches_owned_policy_and_discovery_without_reading_private_canary(tmp_path):
    query = context(tmp_path, "foundry.query")
    gate = foundry_bridge.query({"system": 30, "op": "demonstrate"}, query)
    assert gate["result"]["recorded"] == "recorded" and gate["result"]["chain_ok"]
    foundry_bridge.apply({"system": 27, "op": "seed_static"}, context(tmp_path))
    discovery = foundry_bridge.query({"system": 27, "op": "discover", "args": {
        "now": "2026-10-01T12:00:00Z", "include_unverified": True}}, query)
    assert discovery["result"]["matches"] and not any(r["grants_access"] for r in discovery["result"]["matches"])
    canary = tmp_path / "private-canary"
    canary.write_text("synthetic secret")
    with pytest.raises(CapabilityError, match="workspace access refused"):
        foundry_bridge.apply({"system": 21, "op": "snapshot", "args": {"state": str(tmp_path)}}, context(tmp_path))
    assert canary.read_text() == "synthetic secret"


def test_signed_body_completes_company_delivery_finance_loop_and_serves_receipted_page(tmp_path):
    # Deterministic dry-run computes the pinned offer/receipt, not a Body proof.
    preview = tmp_path / "preview"
    media_company.assemble(preview / "system-49", spec())
    native = order(preview / "system-54")
    delivered = offers.fulfill(preview / "system-54", native)
    ack = acceptance(delivered)
    home, key, body_id, _ = make_body(tmp_path / "live")
    checks = []
    for id, system, field, value in (
            ("assembled", 49, "result.intact", True), ("delivered", 54, "result.delivered", 1),
            ("accepted", 54, "result.accepted", 1), ("finance", 49, "result.fixture_finance.totals.revenue", 1200)):
        checks.append({"check_id": id, "description": "verified fixture " + id,
                       "sensor": {"capability": "foundry.query", "target": "foundry:company",
                                  "params": {"system": system, "op": "inspect"}},
                       "predicate": {"op": "equals", "field": field, "value": value}})
    strategies = []
    for id, system, op, args, advances in (
            ("a-assemble", 49, "assemble", {"spec": spec()}, "assembled"),
            ("b-deliver", 54, "fulfill", {"order": native}, "delivered"),
            ("c-accept", 54, "accept", {"acceptance": ack}, "accepted"),
            ("d-reconcile", 49, "reconcile", {}, "finance")):
        strategies.append({"action_id": id, "capability": "foundry.apply", "target": "foundry:company",
                           "params": {"system": system, "op": op, "args": args}, "advances": [advances],
                           "rationale": "advance integrated fixture company, not manufacture human acceptance"})
    planned = mission("m:company", checks=checks, strategies=strategies,
                      capabilities=["foundry.query", "foundry.apply"], targets=("foundry:*",), ceiling="internal_write")
    drop(home, signed(key, body_id, "MISSION", planned))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(16):
            body.tick(); clock.advance(30)
        assert body.appraise("m:company")["verdict"] == "VERIFIED"
        console = Console(home)
        pages = owned_pages(console)
        assert any(p["name"] == canon()["canon_id"] for p in pages)
        server = serve(console, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
            conn.request("GET", "/owned/" + quote("m:company", safe="") + "/" + canon()["canon_id"])
            response = conn.getresponse()
            assert response.status == 200 and canon()["title"].encode() in response.read()
            conn.close()
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)
        books = workspace(home, "m:company") / "foundry" / "system-49" / "fixture-books"
        assert accounting.trial_balance(books)["totals"]["revenue"] == 1200
        file = books / "journal.jsonl"
        file.write_text(file.read_text().replace("1200", "999"))
        assert body.appraise("m:company")["verdict"] == "REFUTED"


def test_company_community_counts_active_members_and_imported_fixture_behavior(tmp_path):
    root = tmp_path / "system-49"
    media_company.assemble(root, spec())
    media_company.ingest(root, member_events(), [
        event("v1", "view"), event("v2", "view", at="2026-10-02T12:00:00Z"),
        event("tool", "used_tool", at="2026-10-02T12:01:00Z")])
    state = media_company.observed(root)
    assert state["intact"] and state["members"] == 0
    assert state["distribution"]["informed_return"] == 1
    with pytest.raises(ValueError, match="fixture"):
        media_company.ingest(root, [], [event("real", "view", tier="observed")])


def test_corrupt_portal_version_is_refuted_instead_of_escaping_observation(tmp_path):
    page = portal.build(tmp_path, canon(), "fixture")
    cas._path(tmp_path / "versions", page["version_address"]).write_bytes(b"corrupt")
    assert portal.observed(tmp_path, canon()["canon_id"])["intact"] is False
