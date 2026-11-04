"""Owned pages travel through GREG receipts and its existing real loopback server."""
from copy import deepcopy
import http.client
import threading
from urllib.parse import quote

import pytest

from foundry.systems import portal, versions
from greg.artifacts import ArtifactStore
from greg.body import Body
from greg.capabilities import CapabilityError
from greg.console import Console, owned_pages, serve
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace
from tests.unit.test_greg_media import canon


def test_owned_page_versions_canon_provenance_and_tamper_refusal(tmp_path):
    first = portal.build(tmp_path, canon(), "initial owned page")
    changed = canon(); changed["body"] = "<script>changed</script>"
    second = portal.build(tmp_path, changed, "correct source", first["version_address"])
    assert second["version"] == 2
    assert portal.retrieve(tmp_path, canon()["canon_id"], 1)["address"] == first["address"]
    current = portal.retrieve(tmp_path, canon()["canon_id"])
    assert "&lt;script&gt;" in current["html"] and "<script>" not in current["html"]
    assert current["provenance"]["source_refs"] == changed["source_refs"]
    with pytest.raises(versions.VersionError, match="stale"):
        portal.build(tmp_path, canon(), "stale update", first["version_address"])
    ArtifactStore(tmp_path / "artifacts").path(second["address"]).write_bytes(b"substituted")
    assert portal.observed(tmp_path, canon()["canon_id"])["intact"] is False


def test_actual_console_serves_only_canonical_receipted_bytes_and_rejects_host_and_corruption(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    value = canon()
    check = {"check_id": "owned", "description": "owned page has intact canonical bytes",
             "sensor": {"capability": "foundry.query", "target": "foundry:portal",
                        "params": {"system": 31, "op": "inspect", "args": {"name": value["canon_id"]}}},
             "predicate": {"op": "equals", "field": "result.intact", "value": True}}
    strategy = {"action_id": "page", "capability": "foundry.apply", "target": "foundry:portal",
                "params": {"system": 31, "op": "build", "args": {"canon": value, "reason": "signed owned page"}},
                "advances": ["owned"], "rationale": "serve private canonical content in the existing console"}
    spec = mission("m:owned", checks=[check], strategies=[strategy],
                   capabilities=["foundry.query", "foundry.apply"], targets=("foundry:*",), ceiling="internal_write")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick(); clock.advance(30)
        assert body.appraise("m:owned")["verdict"] == "VERIFIED"
    console = Console(home)
    pages = owned_pages(console)
    assert len(pages) == 1 and pages[0]["name"] == value["canon_id"]
    # Filesystem presence without a successful Gate receipt cannot add a page.
    unsigned = {**value, "canon_id": "unsigned", "title": "Unreceipted page"}
    portal.build(workspace(home, "m:owned") / "foundry" / "system-31", unsigned, "unreceipted fixture")
    assert len(owned_pages(console)) == 1
    server = serve(console, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    def get(path, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=15)
        conn.request("GET", path, headers={"Host": host} if host else {})
        response = conn.getresponse(); data = response.read(); status = response.status
        conn.close()
        return status, data
    try:
        url = "/owned/" + quote("m:owned", safe="") + "/" + value["canon_id"]
        assert get("/owned")[0] == 200
        code, content = get(url)
        assert code == 200 and value["title"].encode() in content
        assert get(url, "attacker.invalid")[0] == 403
        assert get("/owned/m%3Aowned/unsigned")[0] == 404
        assert get(url + "?version=invalid")[0] == 400
        root = workspace(home, "m:owned") / "foundry" / "system-31"
        address = portal.retrieve(root, value["canon_id"])["address"]
        ArtifactStore(root / "artifacts").path(address).write_bytes(b"substituted")
        assert get(url)[0] == 404
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
