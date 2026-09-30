"""Real computer use: a mission observes a page only a browser can see, and nothing leaks.

Two real local servers: one serves a page whose required text exists only after its
JavaScript runs; the other is a hostile beacon the page tries to reach by hostname and by
IP literal. The browser is the installed Chrome/Chromium; the test skips (never fakes) when
no browser can run here.
"""
from functools import partial
import http.server
import socket
import threading
import urllib.request

import pytest

from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, _VisibleText
from tests.greg_fixtures import Clock, make_body, mission, signed, drop
from tests.unit.test_greg_missions import events, run

PAGE = """<html><head><title>GREG render probe</title></head><body><p id="x">static text</p>
<script>document.getElementById('x').textContent = 'rendered by javascript';
fetch('http://beacon.example.com:{beacon}/by-name').catch(() => {{}});
fetch('http://127.0.0.1:{beacon}/by-ip-literal').catch(() => {{}});</script></body></html>"""


def _port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def web(tmp_path):
    hits, beacon, site = [], _port(), tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(PAGE.format(beacon=beacon))

    class Beacon(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(204)
            self.end_headers()

        def log_message(self, *a):
            pass

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    servers = [http.server.ThreadingHTTPServer(("127.0.0.1", beacon), Beacon),
               http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(site)))]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{servers[1].server_address[1]}/index.html"
    manifest, adapter = BUILTINS["browser.render"]
    ok, why = manifest.available()
    if not ok:
        pytest.skip(f"no runnable browser: {why}")
    try:
        adapter({"url": url}, InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=manifest))
    except CapabilityError as exc:
        pytest.skip(f"browser present but cannot run here: {exc}")
    hits.clear()
    yield url, hits
    for server in servers:
        server.shutdown()


def _render_mission(url, target):
    check = {"check_id": "rendered", "description": "the page shows its JavaScript-rendered text",
             "sensor": {"capability": "browser.render", "params": {"url": url}, "target": target},
             "predicate": {"op": "contains", "field": "text", "value": "rendered by javascript"}}
    return mission("m:web", checks=[check], strategies=[], capabilities=["browser.render"],
                   targets=("web:127.0.0.1",), ceiling="read_only")


def test_a_mission_observes_javascript_rendered_truth_and_the_page_cannot_phone_home(tmp_path, web):
    url, hits = web
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _render_mission(url, "web:127.0.0.1")))
    missions, _ = run(home, Clock(), ticks=3)
    assert missions["m:web"].status == "ACHIEVED"
    observed = events(home, "mission.observed")[-1]
    assert observed["passed"] and observed["receipt"]  # through the Gate, with a retained receipt
    assert hits == []  # neither the hostname beacon nor the IP-literal beacon was reached
    # Negative control: the same visible-text extraction over the raw HTML (what a plain HTTP
    # fetch sees) shows only the static text; the required truth exists only after JavaScript ran.
    parser = _VisibleText()
    parser.feed(urllib.request.urlopen(url).read().decode())
    assert parser.parts == ["static text"]


def test_the_signed_target_must_name_the_host_the_browser_contacts(tmp_path, web):
    url, hits = web
    home, key, body_id, _ = make_body(tmp_path)
    spec = _render_mission(url, "web:example.com")
    spec["light_cone"]["targets"] = ["web:*"]
    drop(home, signed(key, body_id, "MISSION", spec))
    missions, _ = run(home, Clock(), ticks=2)
    assert missions["m:web"].status != "ACHIEVED"
    detail = events(home, "mission.observed")[-1]["detail"]
    assert "does not name the host '127.0.0.1'" in detail and hits == []


def test_browser_refuses_plain_http_beyond_this_machine(tmp_path):
    manifest, adapter = BUILTINS["browser.render"]
    ctx = InvocationContext(workspace=tmp_path, read_roots=(), secrets=None, manifest=manifest)
    for url in ("http://example.com/", "file:///etc/passwd", "javascript:alert(1)"):
        with pytest.raises(CapabilityError, match="https"):
            adapter({"url": url}, ctx)
