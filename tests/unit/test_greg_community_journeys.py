"""Portable signed community, observed journeys and canonical GREG integration."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import sqlite3

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from foundry.systems import community, journeys
from greg import foundry_bridge
from greg.body import Body
from greg.capabilities import CapabilityError
from greg.founder import public_bytes
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace
from tests.unit.test_greg_foundry_worker import context


def member_events():
    key = Ed25519PrivateKey.from_private_bytes(bytes([23]) * 32)
    out = []
    for i, (kind, payload) in enumerate((
            ("join", {"handle": "fixture-member"}),
            ("post", {"body": "<script>fixture</script>"}),
            ("edit", {"target": "e1", "body": "A correction"}),
            ("react", {"target": "e1", "reaction": "useful"}),
            ("leave", {}))):
        event = {"version": community.VERSION, "community": "owned", "id": f"e{i}",
                 "at": f"2026-10-01T12:00:0{i}Z", "public_key": public_bytes(key.public_key()).hex(),
                 "kind": kind, "payload": payload,
                 "prev": "sha256:" + hashlib.sha256(community.canonical(out[-1])).hexdigest() if out else None}
        event["signature"] = key.sign(community.canonical(event)).hex()
        out.append(event)
    return out


def event(id, kind, node="entry", at="2026-10-01T12:00:00Z", subject="visitor", tier="fixture", **extra):
    return {"id": id, "at": at, "subject": subject, "kind": kind, "node": node,
            "source_ref": "fixture:local-observation", "tier": tier, "amount_cents": 0,
            "currency": None, "receipt": None, **extra}


def territory():
    nodes = []
    for id, doors, exit in (("entry", ["deep"], False), ("deep", ["offer"], False), ("offer", [], True)):
        nodes.append({"node_id": id, "question": f"Question {id}", "artifact": f"sha256:{id}",
                      "capability_taught": id, "evidence_level": 0.9, "evidence_refs": ["fixture:evidence"],
                      "next_doors": doors, "owned_exit": exit, "owned_ground": "owned:hub" if exit else ""})
    return {"name": "owned", "entry": "entry", "nodes": nodes}


def test_portable_signed_members_posts_and_history_survive_export(tmp_path):
    events = member_events()
    root, restored = tmp_path / "original", tmp_path / "restored"
    assert community.ingest(root, "owned", events)["added"] == 5
    assert community.ingest(root, "owned", events)["added"] == 0
    first = community.export(root, "owned", limit=2)
    assert first["next_offset"] == 2 and first["total"] == 5
    pages = first["events"] + community.export(root, "owned", 2, 2)["events"] + community.export(root, "owned", 4, 2)["events"]
    community.ingest(restored, "owned", pages)
    assert community.export(root, "owned") == community.export(restored, "owned")
    state = community.view(restored, "owned")
    assert state["posts"][0]["body"] == "A correction"
    assert state["posts"][0]["versions"] == ["e1", "e2"]
    assert state["members"][0]["active"] is False
    assert state["authority_created"] is False


def test_forgery_cross_community_replay_chain_reorder_and_html_are_refused(tmp_path):
    events = member_events()
    root = tmp_path / "store"
    community.ingest(root, "owned", events[:2])
    assert "&lt;script&gt;" in community.render(root, "owned")["html"]
    before = community.export(root, "owned")
    forged = deepcopy(events[2]); forged["payload"]["body"] = "forged"
    with pytest.raises(ValueError, match="signature"):
        community.ingest(root, "owned", [forged])
    with pytest.raises(ValueError, match="different community"):
        community.ingest(tmp_path / "wrong", "elsewhere", events)
    with pytest.raises(ValueError, match="chain"):
        community.ingest(root, "owned", [events[3]])
    assert community.export(root, "owned") == before


def test_journeys_measure_sequences_separate_tiers_and_refuse_duplicate_money(tmp_path):
    events = [event("s0", "subscribe", at="2026-10-01T11:00:00Z"),
              event("v1", "view"), event("v2", "view", "deep", at="2026-10-01T12:01:00Z"),
              event("s1", "subscribe", "deep", at="2026-10-01T12:02:00Z"),
              event("p1", "purchase", "offer", at="2026-10-01T12:03:00Z",
                    amount_cents=2300, currency="USD", receipt="fixture:purchase"),
              event("r1", "refund", "offer", at="2026-10-01T12:04:00Z",
                    amount_cents=300, currency="USD", receipt="fixture:refund"),
              event("observer", "view", subject="other", tier="observed")]
    assert journeys.ingest(tmp_path, events)["added"] == 7
    assert journeys.ingest(tmp_path, events)["added"] == 0
    report = journeys.report(tmp_path, "fixture")
    deep = next(p for p in report["paths"] if p["sequence"] == ["entry", "deep"])
    assert (deep["subscribers"], deep["customers"]) == (1, 1)
    assert report["linked_net_receipt_cents"] == {"USD": 2000}
    assert report["unlinked_outcomes"] == 1
    assert journeys.report(tmp_path, "observed")["customers"] == 0
    duplicate = {**events[4], "id": "p2"}
    with pytest.raises(ValueError, match="receipt already"):
        journeys.ingest(tmp_path, [duplicate])
    assert journeys.report(tmp_path, "fixture") == report


def test_future_or_stale_events_do_not_produce_conversion_or_routing(tmp_path):
    events = [event("before", "purchase", at="2026-10-01T11:00:00Z",
                    amount_cents=2300, currency="USD", receipt="fixture:before"),
              event("later", "view")]
    journeys.ingest(tmp_path, events)
    assert journeys.report(tmp_path, "fixture")["customers"] == 0
    route = journeys.route(tmp_path, "visitor", "fixture", territory(), "2026-10-01T12:01:00Z")
    assert route["next"] == ["deep"] and route["observed_events"] == ["later"]
    stale = territory(); stale["nodes"][1]["expires_at"] = "2026-10-01T12:00:00Z"
    assert journeys.route(tmp_path, "visitor", "fixture", stale, "2026-10-01T12:01:00Z")["next"] == []
    assert journeys.route(tmp_path, "visitor", "fixture", territory(), "2026-10-01T10:00:00Z")["next"] == ["entry"]


def test_greg_workers_integrate_shared_journey_store_and_discard_query_writes(tmp_path):
    ctx = context(tmp_path)
    result = foundry_bridge.apply({"system": 32, "op": "ingest", "args": {
        "community": "owned", "events": member_events()}}, ctx)
    assert result["result"]["posts"] == 1
    result = foundry_bridge.apply({"system": 34, "op": "ingest", "args": {
        "events": [event("visit", "view")]}}, ctx)
    query = foundry_bridge.query({"system": 50, "op": "route", "args": {
        "subject": "visitor", "tier": "fixture", "territory": territory(), "now": "2026-10-01T12:01:00Z"}},
        context(tmp_path, "foundry.query"))
    assert query["result"]["next"] == ["deep"]
    assert query["execution"]["persistence"] == "discarded"
    assert not (ctx.workspace / "foundry" / "system-50").exists()


def test_signed_body_owns_community_and_appraisal_refutes_corrupted_signature(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    check = {"check_id": "community", "description": "owned signed community has one post",
             "sensor": {"capability": "foundry.query", "target": "foundry:community",
                        "params": {"system": 32, "op": "summary", "args": {"community": "owned"}}},
             "predicate": {"op": "equals", "field": "result.totals.posts", "value": 1}}
    strategy = {"action_id": "ingest", "capability": "foundry.apply", "target": "foundry:community",
                "params": {"system": 32, "op": "ingest", "args": {"community": "owned", "events": member_events()}},
                "advances": ["community"], "rationale": "retain signed synthetic member events"}
    spec = mission("m:community", checks=[check], strategies=[strategy],
                   capabilities=["foundry.query", "foundry.apply"], targets=("foundry:*",), ceiling="internal_write")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick(); clock.advance(30)
        assert body.appraise("m:community")["verdict"] == "VERIFIED"
        db = sqlite3.connect(workspace(home, "m:community") / "foundry" / "system-32" / "community.sqlite")
        bad = deepcopy(member_events()[1]); bad["payload"]["body"] = "substituted"
        with db:
            db.execute("UPDATE events SET body=? WHERE id='e1'", (json.dumps(bad),))
        db.close()
        assert body.appraise("m:community")["verdict"] == "REFUTED"
