"""Mission Control over real HTTP: the five questions, every view, and the First Mission from the front page.

A per-test Ed25519 key stands in for the founder. The console runs in-process on loopback.
"""
import re
import threading
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from greg.body import Body
from greg.console import Console, serve
from greg.mission_control import VIEWS, classify_capability
from tests.greg_fixtures import drop, make_body, signed
from tests.integration.test_greg_first_mission import kernel_copy


def http(port, path, fields=None):
    data = urlencode(fields).encode() if fields is not None else None
    headers = {"Host": f"127.0.0.1:{port}"}
    if data:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    with urlopen(Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers), timeout=30) as r:
        return r.geturl(), r.read().decode()


@pytest.fixture
def running(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    kernel_copy(tmp_path)
    console = Console(home, key=key)
    server = serve(console, port=0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield home, key, body_id, console, port
    server.shutdown()
    server.server_close()


def token(page):
    return re.search(r"name=csrf value='([^']+)'", page).group(1)


def test_front_page_answers_the_five_questions_from_real_state(running):
    home, _, _, console, port = running
    _, page = http(port, "/")
    for q in ("What is GREG?", "What can it actually do right now?", "What is it doing?",
              "What valuable work can I command?", "What needs my authority?"):
        assert q in page
    assert "Prepare the Founder&#x27;s First Mission" in page or "Prepare the Founder's First Mission" in page
    assert "Stop GREG (local stop file)" in page          # shutdown is reachable from the first page
    for key, _ in VIEWS:
        _, view = http(port, f"/mc/{key}")
        assert "GREG Mission Control" in view
    _, classic = http(port, "/classic")
    assert "<h1>GREG</h1>" in classic


def test_capability_classes_are_truthful_projections():
    assert classify_capability({"capability_id": "cognition.dp_knapsack", "state": "VERIFIED"}, {})["class"] == "NEEDS_FOUNDER_ATTACH"
    assert classify_capability({"capability_id": "worker.commission", "state": "ATTACHED"}, {})["class"] == "BLOCKED"
    assert classify_capability({"capability_id": "worker.commission", "state": "ATTACHED"}, {"codex": True})["class"] == "SPENDS_MONEY"
    assert classify_capability({"capability_id": "x", "state": "QUARANTINED"}, {})["class"] == "BLOCKED"
    assert classify_capability({"capability_id": "x", "state": "ATTACHED", "credentials": ["github_token"]}, {})["class"] == "BLOCKED"
    assert classify_capability({"capability_id": "x", "state": "ATTACHED", "health": "available"}, {})["class"] == "RUNNABLE"


def test_first_mission_from_the_front_page_to_a_verified_dossier(running):
    home, key, body_id, console, port = running
    _, page = http(port, "/")
    url, review = http(port, "/first-mission", {"csrf": token(page), "effort_budget": "8"})
    assert "/proposal/" in url and "template:first-mission" in review
    assert "institution.survey" in review and "Never" in review           # the authority summary is shown before signing
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.dp_knapsack"}), "attach.json")
    http(port, "/sign", {"csrf": token(review), "proposal": url.rsplit("/", 1)[1]})
    with Body(home) as body:
        body.boot()
        for _ in range(8):
            if body.tick()["missions"][0]["state"] == "ACHIEVED":
                break
    _, page = http(port, "/")
    assert "First Mission dossiers" in page
    name = re.search(r"/first-mission/([^'\"]+\.md)", page).group(1)
    _, dossier = http(port, f"/first-mission/{name}")
    assert "Where you are trying to go" in dossier and "Next authorized step" in dossier
    _, proof = http(port, "/mc/proof")
    assert "VERIFIED" in proof


def test_refusals_hold_on_mission_control(running):
    _, _, _, console, port = running
    from urllib.error import HTTPError
    with pytest.raises(HTTPError) as bad:                      # no CSRF token
        http(port, "/first-mission", {"effort_budget": "8"})
    assert bad.value.code == 403
    _, page = http(port, "/")
    _, review = http(port, "/first-mission", {"csrf": token(page), "effort_budget": "999"})
    assert "NEEDS_INPUT" in review and "1 to 200" in review
    with pytest.raises(HTTPError) as missing:
        http(port, "/first-mission/../config.json")
    assert missing.value.code == 404
    with pytest.raises(HTTPError) as unknown:
        http(port, "/mc/not-a-view")
    assert unknown.value.code == 404
    readonly = Console(console.home)                             # no key: review works, signing refuses
    with pytest.raises(PermissionError):
        readonly.sign("MISSION", {})


def test_commerce_rehearsal_from_the_ventures_view(running):
    home, key, body_id, console, port = running
    from urllib.error import HTTPError
    _, page = http(port, "/mc/ventures")
    assert "Run the Founder's First Mission first" in page or "Run the Founder&#x27;s First Mission first" in page
    with pytest.raises(HTTPError) as early:                     # no dossier yet: refused, nothing drafted
        http(port, "/venture-rehearsal", {"csrf": token(http(port, "/")[1])})
    assert early.value.code == 409
    _, page = http(port, "/")
    url, review = http(port, "/first-mission", {"csrf": token(page), "effort_budget": "8"})
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.dp_knapsack"}), "attach.json")
    http(port, "/sign", {"csrf": token(review), "proposal": url.rsplit("/", 1)[1]})
    with Body(home) as body:
        body.boot()
        for _ in range(12):
            if body.tick()["missions"][0]["state"] == "ACHIEVED":
                break
    _, page = http(port, "/mc/ventures")
    url, review = http(port, "/venture-rehearsal", {"csrf": token(page)})
    assert "template:venture-rehearsal" in review and "FIXTURE" in review and "$0" in review
    http(port, "/sign", {"csrf": token(review), "proposal": url.rsplit("/", 1)[1]})
    with Body(home) as body:
        body.boot()
        for _ in range(12):
            states = {m["mission_id"]: m["state"] for m in body.tick()["missions"]}
            if all(v == "ACHIEVED" for v in states.values()) and len(states) == 2:
                break
    _, page = http(port, "/mc/ventures")
    assert "1200 cents" in page and "balanced" in page and "FIXTURE" in page
