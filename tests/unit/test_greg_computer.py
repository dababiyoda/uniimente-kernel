"""browser.session against a real local web application in real Chromium (no mocks).

The page is served on loopback by this test; the browser, DOM and screenshots are real.
"""
from __future__ import annotations

import http.server
import json
import os
from pathlib import Path
import threading

import pytest

from greg import computer
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker

pytest.importorskip("playwright")
try:
    computer.chromium()
except CapabilityError as exc:
    if os.environ.get("GREG_REQUIRE_BROWSER") == "1":
        pytest.fail(f"GREG_REQUIRE_BROWSER=1 and {exc}", pytrace=False)
    pytest.skip("no Chromium installed", allow_module_level=True)

PAGES = {
    "/": b"""<html><head><title>Orders</title></head><body>
<form id=f onsubmit="event.preventDefault();document.getElementById('out').textContent='Found '+document.getElementById('q').value+' in '+document.getElementById('region').value">
<input id=q name=q><select id=region><option>us</option><option>eu</option></select>
<button id=go type=submit>Search</button></form><p id=out></p>
<a id=next href="/details">details</a><a id=away href="http://example.invalid/x">away</a>
<img src="http://third.party.invalid/pixel.gif"></body></html>""",
    "/details": b"<html><head><title>Details</title></head><body><h1>Order 42</h1><button id=buy>Buy now</button>"
                b"<input id=user></body></html>",
    "/challenge": b"<html><head><title>Client Challenge</title></head><body>Enter the characters seen</body></html>",
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGES.get(self.path.split("?")[0], b"not found")
        self.send_response(200 if self.path.split("?")[0] in PAGES else 404)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def ctx(tmp_path):
    return InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=SecretBroker(tmp_path / "s.json"),
                             manifest=BUILTINS["browser.session"][0], mission_id="m:test")


def test_multi_step_interaction_changes_page_state_with_per_step_evidence(tmp_path, site):
    steps = [{"op": "fill", "selector": "#q", "value": "widgets"},
             {"op": "select", "selector": "#region", "value": "eu"},
             {"op": "click", "selector": "#go"},
             {"op": "expect_text", "selector": "#out", "value": "Found widgets in eu"},
             {"op": "extract", "selector": "#out", "as": "result"},
             {"op": "click", "selector": "#next"},
             {"op": "extract", "selector": "h1", "as": "heading"}]
    out = computer.session({"url": site + "/", "steps": steps, "session": "orders"}, ctx(tmp_path))
    assert out["status"] == "COMPLETED", out["boundary"]
    assert out["extracted"] == {"result": "Found widgets in eu", "heading": "Order 42"}
    assert all(s.get("screenshot") and Path(s["screenshot"]["path"]).is_file() for s in out["steps"])
    assert out["blocked_requests"].get("third.party.invalid", 0) >= 1          # only the signed host is reachable
    status = computer.session_status({"session": "orders"}, ctx(tmp_path))
    assert status["present"] and status["screenshots_intact"] and status["extracted"]["heading"] == "Order 42"


def test_consequential_step_stops_at_the_authority_boundary_and_is_not_executed(tmp_path, site):
    steps = [{"op": "click", "selector": "#next"},
             {"op": "click", "selector": "#buy", "consequential": True, "why": "places an order"},
             {"op": "extract", "selector": "h1", "as": "never"}]
    out = computer.session({"url": site + "/", "steps": steps, "session": "buy"}, ctx(tmp_path))
    assert out["status"] == "AUTHORITY_BOUNDARY" and "places an order" in out["boundary"]
    assert "never" not in out["extracted"] and out["steps"][-1]["op"] == "boundary"


def test_unprovisioned_credential_is_a_truthful_stop(tmp_path, site):
    steps = [{"op": "click", "selector": "#next"}, {"op": "fill", "selector": "#user", "secret": "shop_login"}]
    out = computer.session({"url": site + "/", "steps": steps, "session": "login"}, ctx(tmp_path))
    assert out["status"] == "AUTHORITY_BOUNDARY" and "shop_login" in out["boundary"]


def test_navigation_outside_the_signed_hosts_is_refused(tmp_path, site):
    out = computer.session({"url": site + "/", "steps": [{"op": "goto", "url": "http://example.invalid/"}],
                            "session": "escape"}, ctx(tmp_path))
    assert out["status"] == "SCOPE"


def test_bot_challenges_are_never_solved(tmp_path, site):
    out = computer.session({"url": site + "/challenge", "steps": [{"op": "fill", "selector": "body", "value": "x"}],
                            "session": "captcha"}, ctx(tmp_path))
    assert out["status"] == "CHALLENGE"
    skipped = computer.session({"url": site + "/challenge", "on_challenge": "skip", "session": "captcha2",
                                "steps": [{"op": "fill", "selector": "body", "value": "x"},
                                          {"op": "goto", "url": "/details"},
                                          {"op": "extract", "selector": "h1", "as": "h"}]}, ctx(tmp_path))
    assert skipped["status"] == "COMPLETED" and skipped["steps"][1]["result"] == "skipped_after_challenge"


def test_plain_http_off_loopback_is_refused(tmp_path):
    with pytest.raises(CapabilityError, match="https"):
        computer.session({"url": "http://example.com/", "steps": [{"op": "screenshot"}]}, ctx(tmp_path))


@pytest.fixture
def listener():
    """Raw sockets on two loopback addresses that the signed session never names: any byte arriving is a leak."""
    import socket
    hits, servers = [], []
    for address in ("127.0.0.1", "127.0.0.2"):
        server = socket.socket()
        server.bind((address, 0))
        server.listen(8)
        servers.append(server)

        def accept(server=server):
            while True:
                try:
                    conn, _ = server.accept()
                except OSError:
                    return
                hits.append(conn.recv(80))
                conn.close()
        threading.Thread(target=accept, daemon=True).start()
    yield hits, [s.getsockname() for s in servers]
    for server in servers:
        server.close()


def test_a_page_cannot_open_websockets_or_reach_other_ports_outside_the_signed_origins(tmp_path, listener):
    """Measured 2026-10-14 before this fix: Playwright's context.route never sees a WebSocket, so a page opened one to an
    unlisted host; and the allowlist compared host names only, so a page on a loopback target reached the body's other
    loopback ports. Both are now refused in the browser and counted."""
    import functools
    hits, ((own, own_port), (other, other_port)) = listener
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(
        "<html><head><title>probe</title></head><body><p id=x>static</p><script>"
        f"try{{new WebSocket('ws://{other}:{other_port}/ws')}}catch(e){{}};"
        f"try{{new WebSocket('ws://{own}:{own_port}/ws')}}catch(e){{}};"
        f"fetch('http://{own}:{own_port}/other-port').catch(()=>{{}});"
        "document.getElementById('x').textContent='ran';</script></body></html>")

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        out = computer.session({"url": f"http://127.0.0.1:{server.server_address[1]}/index.html", "session": "probe",
                                "steps": [{"op": "wait_for", "selector": "#x"},
                                          {"op": "expect_text", "selector": "#x", "value": "ran"}]}, ctx(tmp_path))
    finally:
        server.shutdown()
    assert out["status"] == "COMPLETED", out["boundary"]
    assert hits == []
    assert out["blocked_websockets"] == {other: 1, own: 1}
    assert out["blocked_requests"].get(own, 0) >= 1
    assert out["allowed_origins"] == [f"127.0.0.1:{server.server_address[1]}"]


def test_signed_origins_come_from_the_start_url_absolute_gotos_and_also_hosts():
    url, _, hosts, origins = computer._validate({
        "url": "https://shop.example/a", "also_hosts": ["cdn.example", "api.example:8443"],
        "steps": [{"op": "goto", "url": "https://shop.example:8080/b"}, {"op": "goto", "url": "https://elsewhere.example/"},
                  {"op": "goto", "url": "/relative"}]})
    assert hosts == {"shop.example", "cdn.example", "api.example"}
    assert origins == {("shop.example", 443), ("shop.example", 8080), ("cdn.example", 443), ("api.example", 8443)}
    with pytest.raises(CapabilityError, match="also_hosts"):
        computer._validate({"url": "https://a.example/", "steps": [{"op": "screenshot"}], "also_hosts": ["b:http"]})
