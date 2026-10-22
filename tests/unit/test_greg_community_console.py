"""Real loopback community serving requires canonical receipt-bound history."""
import http.client
import json
import threading
from urllib.parse import quote

from foundry.systems import community
from greg.body import Body
from greg.console import Console, owned_communities, serve
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace
from tests.unit.test_greg_community_journeys import member_events


def setup_community(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    check = {"check_id": "community", "description": "community history is verified",
             "sensor": {"capability": "foundry.query", "target": "foundry:community",
                        "params": {"system": 32, "op": "summary", "args": {"community": "owned"}}},
             "predicate": {"op": "equals", "field": "result.totals.posts", "value": 1}}
    action = {"action_id": "ingest", "capability": "foundry.apply", "target": "foundry:community",
              "params": {"system": 32, "op": "ingest", "args": {"community": "owned", "events": member_events()}},
              "advances": ["community"], "rationale": "retain portable signed fixture history"}
    spec = mission("m:community", checks=[check], strategies=[action],
                   capabilities=["foundry.query", "foundry.apply"], targets=("foundry:*",), ceiling="internal_write")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(5):
            body.tick(); clock.advance(30)
        assert body.appraise("m:community")["verdict"] == "VERIFIED"
    return home


def test_actual_http_page_export_and_unreceipted_valid_history_denial(tmp_path):
    home = setup_community(tmp_path)
    console = Console(home)
    assert len(owned_communities(console)) == 1
    server = serve(console, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    base = "/" + quote("m:community", safe="") + "/owned"
    def get(path, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
        conn.request("GET", path, headers={"Host": host} if host else {})
        response = conn.getresponse(); status, body = response.status, response.read(); conn.close()
        return status, body
    try:
        status, body = get("/community" + base)
        assert status == 200 and b"<article>" in body
        status, raw = get("/community-export" + base)
        exported = json.loads(raw)
        assert status == 200 and exported["events"] == member_events() and exported["next_offset"] is None
        restore = tmp_path / "restored"
        community.ingest(restore, "owned", exported["events"])
        assert community.export(restore, "owned")["history_hash"] == exported["history_hash"]
        assert get("/community" + base + "?offset=-1")[0] == 400
        assert get("/community" + base, "untrusted.example")[0] == 403
        assert get("/community/unknown/owned")[0] == 404
        # This is a valid signed prefix, but it differs from the successful Gate receipt.
        import sqlite3
        path = workspace(home, "m:community") / "foundry/system-32/community.sqlite"
        db = sqlite3.connect(path)
        with db:
            db.execute("DELETE FROM events WHERE seq=(SELECT MAX(seq) FROM events)")
        db.close()
        assert community.observed(path.parent, "owned")["intact"]
        assert get("/community" + base)[0] == 404
        assert get("/community-export" + base)[0] == 404
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_valid_filesystem_history_without_gate_receipt_is_never_discovered(tmp_path):
    home, *_ = make_body(tmp_path)
    community.ingest(workspace(home, "m:forged") / "foundry/system-32", "owned", member_events())
    assert owned_communities(Console(home)) == []
