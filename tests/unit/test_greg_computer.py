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


# -- the method gate: the request, not a step's marker, decides whether a session acts on the world ----------------

SHOP = b"""<html><head><title>Shop</title></head><body><h1>Shop</h1>
<form method=POST action=/order><input id=qty name=qty value=1><button id=buy>Buy</button></form>
<form method=POST action=/search><input id=q name=q value=widgets><button id=find>Find</button></form>
<button id=put onclick="fetch('/api/cart',{method:'PUT',body:'x'}).catch(()=>{}).finally(()=>done('put'))">p</button>
<button id=worker onclick="var w=new Worker('/worker.js');w.onmessage=()=>done('worker')">w</button>
<button id=sock onclick="var s=new WebSocket(location.origin.replace('http','ws')+'/live');
s.onopen=s.onerror=()=>done('sock')">s</button>
<p id=done></p><script>function done(t){document.getElementById('done').textContent=t}</script></body></html>"""
APP = b"""<html><head><title>App</title></head><body><p id=x>loading</p><script>
fetch('/api/state',{method:'PUT',body:'x'}).catch(()=>{});
navigator.sendBeacon('/beacon','x');
fetch('/api/state',{method:'DELETE'}).catch(()=>{});
fetch('/data').then(r=>r.text()).then(t=>{document.getElementById('x').textContent=t});
</script></body></html>"""
SITE = {"/shop": SHOP, "/app": APP, "/data": b"ready",
        "/worker.js": b"fetch('/api/worker',{method:'POST',body:'x'}).catch(()=>{}).finally(()=>postMessage('x'))"}


@pytest.fixture
def counting_site():
    """A loopback site that counts every request it receives by (method, path): any non-GET count is an effect."""
    import collections
    hits = collections.Counter()

    class Counting(http.server.BaseHTTPRequestHandler):
        def _any(self):
            path = self.path.split("?")[0]
            hits[(self.command, path)] += 1
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.command == "POST" and path in ("/order", "/search"):
                body = b"<html><head><title>Done</title></head><body><h1>" + path[1:].encode() + b" done</h1></body></html>"
            else:
                body = SITE.get(path, b"not found")
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript" if path.endswith(".js") else "text/html")
            self.end_headers()
            self.wfile.write(body)
        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _any

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Counting)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", hits
    server.shutdown()


def writes(hits) -> dict:
    return {key: n for key, n in hits.items() if key[0] != "GET"}


def test_a_click_on_an_unmarked_post_form_is_aborted_and_ends_at_the_authority_boundary(tmp_path, counting_site):
    """No step is marked consequential, yet the click submits a POST: before the gate the server received the
    order and the session reported COMPLETED."""
    base, hits = counting_site
    origin = base.split("//")[1]
    out = computer.session({"url": base + "/shop", "session": "order",
                            "steps": [{"op": "click", "selector": "#buy"},
                                      {"op": "extract", "selector": "h1", "as": "after"}]}, ctx(tmp_path))
    assert writes(hits) == {}
    assert out["status"] == "AUTHORITY_BOUNDARY" and f"POST {origin}/order" in out["boundary"]
    assert out["blocked_methods"] == {f"POST {origin}/order": 1}
    assert out["steps"][1]["op"] == "click" and out["steps"][1]["blocked_methods"] == [f"POST {origin}/order"]
    assert "after" not in out["extracted"] and out["steps"][-1]["op"] == "boundary"
    assert computer.session_status({"session": "order"}, ctx(tmp_path))["blocked_methods"] == out["blocked_methods"]


@pytest.mark.parametrize("trigger, written", [
    ([{"op": "press", "selector": "#qty", "key": "Enter"}], ("POST", "/order")),
    ([{"op": "click", "selector": "#put"}, {"op": "wait_for", "selector": "#done:has-text('put')"}], ("PUT", "/api/cart")),
    ([{"op": "click", "selector": "#worker"}, {"op": "wait_for", "selector": "#done:has-text('worker')"}],
     ("POST", "/api/worker")),
    ([{"op": "click", "selector": "#sock"}, {"op": "wait_for", "selector": "#done:has-text('sock')"}],
     ("WEBSOCKET", "/live")),
], ids=["enter-submits-a-form", "page-script-put", "worker-post", "websocket"])
def test_every_write_channel_a_step_can_trigger_is_aborted_and_stops_the_session(tmp_path, counting_site, trigger,
                                                                                  written):
    base, hits = counting_site
    origin = base.split("//")[1]
    out = computer.session({"url": base + "/shop", "session": "channel",
                            "steps": trigger + [{"op": "extract", "selector": "h1", "as": "after"}]}, ctx(tmp_path))
    method, path = written
    assert writes(hits) == {} and hits[("GET", path)] == 0          # a WebSocket handshake never reached the server
    assert out["status"] == "AUTHORITY_BOUNDARY", out["boundary"]
    assert out["blocked_methods"] == {f"{method} {origin}{path}": 1} and "after" not in out["extracted"]


def test_a_step_that_fails_after_a_refused_write_is_reported_as_the_write(tmp_path, counting_site, monkeypatch):
    """A download step whose click submits the order form instead: the download never comes and the step fails,
    but what decides the session is the write it attempted."""
    base, hits = counting_site
    origin = base.split("//")[1]
    monkeypatch.setattr(computer, "STEP_TIMEOUT_MS", 3000)
    out = computer.session({"url": base + "/shop", "session": "fails",
                            "steps": [{"op": "download", "selector": "#buy", "as": "receipt"}]}, ctx(tmp_path))
    assert writes(hits) == {}
    assert out["status"] == "AUTHORITY_BOUNDARY" and f"POST {origin}/order" in out["boundary"]
    assert "receipt" not in out["extracted"] and out["steps"][-1]["op"] == "failure"


def test_a_page_that_writes_while_it_loads_is_refused_and_stops_at_the_open(tmp_path, counting_site):
    base, hits = counting_site
    origin = base.split("//")[1]
    out = computer.session({"url": base + "/app", "session": "app",
                            "steps": [{"op": "wait_for", "selector": "#x:has-text('ready')"},
                                      {"op": "extract", "selector": "#x", "as": "x"}]}, ctx(tmp_path))
    assert writes(hits) == {} and hits[("GET", "/app")] == 1
    assert out["status"] == "AUTHORITY_BOUNDARY", out["boundary"]
    assert out["blocked_methods"] == {f"PUT {origin}/api/state": 1, f"DELETE {origin}/api/state": 1,
                                      f"POST {origin}/beacon": 1}
    charged = [key for s in out["steps"] for key in s.get("blocked_methods", [])]
    assert sorted(charged) == sorted(out["blocked_methods"])         # each charged once, to the step that saw it
    assert out["method_gate"].endswith("a GET with side effects cannot be detected")


def test_a_signed_read_methods_exception_is_honoured_for_that_method_origin_and_path_only(tmp_path, counting_site):
    """A search form that POSTs is a read the founder can sign for; the order form on the same page stays blocked."""
    base, hits = counting_site
    origin = base.split("//")[1]
    out = computer.session({"url": base + "/shop", "session": "search", "read_methods": [f"POST {base}/search"],
                            "steps": [{"op": "click", "selector": "#find"},
                                      {"op": "extract", "selector": "h1", "as": "heading"},
                                      {"op": "goto", "url": "/shop"},
                                      {"op": "click", "selector": "#buy"}]}, ctx(tmp_path))
    assert writes(hits) == {("POST", "/search"): 1}
    assert out["extracted"] == {"heading": "search done"}
    assert out["read_methods"] == [f"POST {origin}/search"] and out["read_methods_used"] == {f"POST {origin}/search": 1}
    assert out["status"] == "AUTHORITY_BOUNDARY" and out["blocked_methods"] == {f"POST {origin}/order": 1}


def test_a_signed_websocket_exception_connects_and_is_recorded(tmp_path, counting_site):
    base, hits = counting_site
    origin = base.split("//")[1]
    out = computer.session({"url": base + "/shop", "session": "live",
                            "read_methods": [f"WEBSOCKET {base.replace('http', 'ws')}/live"],
                            "steps": [{"op": "click", "selector": "#sock"},
                                      {"op": "wait_for", "selector": "#done:has-text('sock')"}]}, ctx(tmp_path))
    assert out["status"] == "COMPLETED", out["boundary"]
    assert hits[("GET", "/live")] == 1 and out["read_methods_used"] == {f"WEBSOCKET {origin}/live": 1}
    assert out["blocked_methods"] == {}


def test_read_methods_never_widen_the_signed_origins_and_name_one_exact_path():
    origins = {("shop.example", 443), ("127.0.0.1", 8080)}
    assert computer._read_methods({"read_methods": ["POST https://shop.example/search",
                                                    "WEBSOCKET ws://127.0.0.1:8080/live"]}, origins) == {
        "POST shop.example:443/search", "WEBSOCKET 127.0.0.1:8080/live"}
    assert computer._read_methods({}, origins) == set()
    for entry in ("POST https://other.example/search",           # an origin the session is not signed for
                  "POST https://shop.example:8443/search",       # another port on a signed host
                  "GET https://shop.example/search",             # reads need no exception
                  "post https://shop.example/search",            # methods are exact
                  "POST https://shop.example/search?q=1",        # one exact path, never a query
                  "POST https://shop.example",                   # no path
                  "WEBSOCKET https://shop.example/live",         # a WebSocket is named by its ws(s) URL
                  "POST ws://shop.example/x",
                  {"method": "POST", "url": "https://shop.example/search"}):
        with pytest.raises(CapabilityError, match="read_methods"):
            computer._read_methods({"read_methods": [entry]}, origins)
    with pytest.raises(CapabilityError, match="at most"):
        computer._read_methods({"read_methods": ["POST https://shop.example/a"] * 21}, origins)
    with pytest.raises(CapabilityError, match="read_methods"):
        computer._read_methods({"read_methods": "POST https://shop.example/search"}, origins)
