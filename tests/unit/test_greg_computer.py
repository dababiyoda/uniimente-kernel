"""browser.session against a real local web application in real Chromium (no mocks).

The page is served on loopback by this test; the browser, DOM and screenshots are real.
"""
from __future__ import annotations

import http.server
import json
from pathlib import Path
import threading

import pytest

from greg import computer
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker

pytest.importorskip("playwright")
try:
    computer.chromium()
except CapabilityError:
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
