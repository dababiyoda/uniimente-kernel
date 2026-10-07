"""The one founder interface: plain words -> vetted proposal -> founder signature -> body.

The console is exercised over real loopback HTTP; the body applies what it signed.
Model routes use a fake transport here (a live Claude Code draft is retained in
tests/evidence/greg-product/)."""
import json
from http.cookiejar import CookieJar
from pathlib import Path
import re
import subprocess
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

import pytest

from greg import planner
from greg.body import Body, Layout, status
from greg.capabilities import BUILTINS, CapabilityRegistry
from greg.console import Console, serve
from greg.founder import FounderVerifier
from tests.greg_fixtures import Clock, make_body

_SESSIONS = {}


def _owner_client(console, port):
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    with opener.open(console.owner_url(port), timeout=10) as response:
        assert response.geturl().endswith(console.owner_path)
        assert "access=" not in response.geturl()
    _SESSIONS[port] = (opener, console.owner_path)
    return opener


def inventory():
    registry = CapabilityRegistry()
    for manifest, adapter in BUILTINS.values():
        registry.register(manifest, adapter, state="ATTACHED")
    return registry.inventory()


def make_repo(path: Path, remote: str):
    path.mkdir(parents=True)
    run = lambda *a: subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                    check=True, capture_output=True)
    run("init", "-q", "-b", "main")
    (path / "f").write_text("x")
    run("add", "f"); run("commit", "-q", "-m", "c")
    run("remote", "add", "origin", f"git@github.com:{remote}.git")


class FakeModel:
    name = "fake:model"

    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def complete(self, system, user):
        self.prompts.append(user)
        return self.replies.pop(0)


GOOD = {"mission_id": "m:watch", "founder_expression": "model paraphrase", "intended_effect": "the kernel is clean",
        "priority": 40, "closure": {"kind": "infinite", "cadence_seconds": 3600},
        "success_checks": [{"check_id": "clean", "description": "no uncommitted changes",
                            "sensor": {"capability": "git.inspect", "target": "fs:kernel", "params": {"path": "/r/kernel"}},
                            "predicate": {"op": "equals", "field": "dirty", "value": False}}],
        "strategies": [], "light_cone": {"capabilities": ["git.inspect", "fs.write"], "targets": ["fs:*"],
                                         "max_consequence_class": "internal_write", "budget_usd": 50,
                                         "horizon": "2099-01-01T00:00:00Z"}}


# -- planner ----------------------------------------------------------------------------

def test_template_route_discovers_repositories_and_their_github_remotes(tmp_path):
    make_repo(tmp_path / "code" / "kernel", "acme/kernel")
    make_repo(tmp_path / "code" / "organ", "acme/organ")
    ctx = planner.PlannerContext(read_roots=(tmp_path / "code",), capabilities=inventory())
    proposal = planner.propose("Every morning tell me which pull requests are failing checks in kernel", ctx)
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:engineering-brief"
    spec = proposal["spec"]
    assert spec["mission_id"] == "m:engineering-brief-daily" and spec["closure"]["kind"] == "infinite"
    params = spec["strategies"][0]["params"]
    assert [r["name"] for r in params["local"]] == ["kernel"] and params["github"] == ["acme/kernel"]
    assert spec["founder_expression"].startswith("Every morning")          # the founder's own words
    assert spec["provenance"] == {"origin": "template:engineering-brief", "planner": planner.PLANNER}
    summary = planner.authority_summary(spec, inventory())
    assert summary["must_ask_you_first"] and "brief.engineering" in summary["must_ask_you_first"][0]


def test_no_route_is_truthful_when_nothing_fits():
    ctx = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={})
    proposal = planner.propose("Book me a flight to Miami", ctx)
    assert proposal["status"] == "NO_ROUTE" and "no model route" in proposal["why"]


def test_model_draft_is_vetted_clamped_and_attributed():
    ctx = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={}, today="2026-09-26")
    model = FakeModel(["Sure! Here it is:\n```json\n" + json.dumps(GOOD) + "\n```"])
    proposal = planner.propose("Tell me if my kernel checkout gets dirty", ctx, transport=model)
    assert proposal["status"] == "PROPOSED", proposal
    spec = proposal["spec"]
    assert spec["founder_expression"] == "Tell me if my kernel checkout gets dirty"   # never the model's paraphrase
    assert spec["mission_id"] == "m:plan-watch-2026-09-26"
    cone = spec["light_cone"]
    assert cone["max_consequence_class"] == "read_only" and cone["budget_usd"] == 0
    assert cone["capabilities"] == ["git.inspect"] and cone["horizon"] < "2099"
    assert spec["provenance"]["model"] == "fake:model" and spec["provenance"]["clamped"]
    assert spec["provenance"]["prompt_sha256"].startswith("sha256:")


def test_unrunnable_draft_gets_one_repair_round_with_concrete_problems():
    bad = json.loads(json.dumps(GOOD))
    bad["success_checks"][0]["sensor"] = {"capability": "git.inspect", "target": "/r/kernel",
                                          "params": {"command": "status --porcelain"}}
    bad["success_checks"][0]["predicate"] = {"op": "exists", "field": "status_output"}
    model = FakeModel([json.dumps(bad), json.dumps(GOOD)])
    ctx = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={})
    proposal = planner.propose("Tell me if my kernel checkout gets dirty", ctx, transport=model)
    assert proposal["status"] == "PROPOSED" and proposal["spec"]["provenance"]["rounds"] == 2
    problems = proposal["attempts"][0]["problems"]
    assert any("target must start with 'fs:'" in p for p in problems)
    assert any("no inputs named ['command']" in p for p in problems)
    assert any("does not output 'status_output'" in p for p in problems)
    assert "PROBLEMS:" in model.prompts[1]


def test_model_cannot_name_capabilities_that_do_not_exist_or_plan_what_it_cannot():
    ctx = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={})
    invented = json.loads(json.dumps(GOOD))
    invented["strategies"] = [{"action_id": "pay", "capability": "stripe.charge", "target": "fs:x",
                               "advances": ["clean"]}]
    rejected = planner.propose("clean it", ctx, transport=FakeModel([json.dumps(invented)] * 2))
    assert rejected["status"] == "REJECTED" and "stripe.charge" in rejected["why"]
    refused = planner.propose("hack my neighbour", ctx,
                              transport=FakeModel(['{"cannot_plan": "not a lawful goal"}']))
    assert refused["status"] == "NO_ROUTE" and refused["why"] == "not a lawful goal"


def test_claude_code_transport_runs_headless_with_no_tools_and_a_spend_cap():
    seen = {}

    def runner(argv, **kw):
        seen["argv"], seen["input"] = argv, kw["input"]
        return subprocess.CompletedProcess(argv, 0, json.dumps({"is_error": False, "result": json.dumps(GOOD)}), "")

    transport = planner.ClaudeCodeTransport("/usr/bin/claude", max_budget_usd=0.25, runner=runner)
    assert json.loads(transport.complete("system", "user"))["mission_id"] == "m:watch"
    argv = seen["argv"]
    assert argv[argv.index("--tools") + 1] == "" and argv[argv.index("--max-budget-usd") + 1] == "0.25"
    assert "--no-session-persistence" in argv and "--strict-mcp-config" in argv and seen["input"] == "user"


# -- console -----------------------------------------------------------------------------

@pytest.fixture
def running(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    make_repo(data / "kernel", "acme/kernel")
    console = Console(home, key=key)
    server = serve(console, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _owner_client(console, server.server_address[1])
    yield home, key, console, server.server_address[1]
    _SESSIONS.pop(server.server_address[1], None)
    server.shutdown()
    server.server_close()


def _get(port, path, host=None):
    opener, prefix = _SESSIONS[port]
    path = path if path.startswith(prefix) else prefix + path.lstrip("/")
    request = Request(f"http://127.0.0.1:{port}{path}", headers={"Host": host or f"127.0.0.1:{port}"})
    with opener.open(request, timeout=10) as response:
        return response.read().decode()


def _post(port, path, fields, *, host=None, origin=None):
    opener, prefix = _SESSIONS[port]
    path = path if path.startswith(prefix) else prefix + path.lstrip("/")
    headers = {"Host": host or f"127.0.0.1:{port}", "Content-Type": "application/x-www-form-urlencoded"}
    if origin:
        headers["Origin"] = origin
    request = Request(f"http://127.0.0.1:{port}{path}", data=urlencode(fields).encode(), headers=headers)
    with opener.open(request, timeout=30) as response:
        return response.geturl(), response.read().decode()


def test_founder_asks_reviews_signs_and_the_body_applies_it(running):
    home, key, console, port = running
    page = _get(port, "/")
    token = re.search(r"name=csrf value='([^']+)'", page).group(1)
    url, review = _post(port, "/ask", {"csrf": token, "text": "Brief me on the state of my repositories"})
    assert "/proposal/" in url and "What signing lets GREG do" in review and "Must ask you first" in review
    pid = url.rsplit("/", 1)[1]
    _post(port, "/sign", {"csrf": token, "proposal": pid})
    envelopes = list((Layout(home).inbox).glob("*-mission-*.json"))
    assert len(envelopes) == 1
    envelope = json.loads(envelopes[0].read_text())
    config = json.loads(Layout(home).config.read_text())
    with Body(home) as body:
        FounderVerifier(body_id=config["body_id"], enrolled=body.enrolled_keys(), seen_nonce=lambda n: False
                        ).verify(envelope)                           # a real founder signature
    body = Body(home, clock=Clock()).open()                         # the console is not needed for this
    body.boot()
    result = body.tick()
    body.close()
    assert result["commands"][0]["status"] == "APPLIED"
    assert result["missions"][0]["state"] == "WAITING"               # delivery waits for the founder
    home_page = _get(port, "/")
    assert "Decisions waiting for you" in home_page and "Approve" in home_page


def test_console_refuses_foreign_hosts_origins_and_missing_tokens(running):
    home, key, console, port = running
    for call in (lambda: _get(port, "/", host="evil.example"),
                 lambda: _post(port, "/stop", {"csrf": console.csrf, "mode": "local"}, host="evil.example"),
                 lambda: _post(port, "/stop", {"csrf": console.csrf, "mode": "local"}, origin="https://evil.example"),
                 lambda: _post(port, "/stop", {"csrf": "forged", "mode": "local"})):
        with pytest.raises(HTTPError) as err:
            call()
        assert err.value.code == 403
    assert not Layout(home).stop_file.exists()
    _post(port, "/stop", {"csrf": console.csrf, "mode": "local"})
    assert Layout(home).stop_file.exists()                           # local stop needs no key


def test_console_without_a_key_is_read_only(tmp_path):
    home, _, _, _ = make_body(tmp_path)
    console = Console(home, key=None)
    server = serve(console, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    _owner_client(console, port)
    try:
        assert "read-only (start with --key to sign)" in _get(port, "/")
        with pytest.raises(HTTPError) as err:
            _post(port, "/stop", {"csrf": console.csrf, "mode": "signed"})
        assert err.value.code == 403 and not list(Layout(home).inbox.glob("*.json"))
    finally:
        _SESSIONS.pop(port, None)
        server.shutdown()
        server.server_close()


def test_delivery_pages_cannot_escape_the_delivery_folder(running):
    home, key, console, port = running
    folder = Path(json.loads(Layout(home).config.read_text())["deliver_root"]) / "briefs"
    folder.mkdir(parents=True)
    (folder / "2026-09-26-engineering-brief.md").write_text("# brief <script>x</script>")
    page = _get(port, "/delivery/2026-09-26-engineering-brief.md")
    assert "&lt;script&gt;" in page and "<script>x" not in page
    for bad in ("/delivery/..%2F..%2Fbody.json", "/delivery/%2Fetc%2Fpasswd"):
        with pytest.raises(HTTPError) as err:
            _get(port, bad)
        assert err.value.code == 404


def test_loopback_worker_cannot_read_owner_state_or_sign_even_with_known_csrf(running):
    home, _, console, port = running
    original_inbox = list(Layout(home).inbox.glob("*.json"))
    for path in ("/", "/api/state", "/morning", "/proposal/guessed", console.owner_path,
                 console.owner_path + "api/state"):
        with pytest.raises(HTTPError) as failure:
            urlopen(f"http://127.0.0.1:{port}{path}", timeout=10)
        assert failure.value.code == 403
        content = failure.value.read().decode()
        assert console.csrf not in content and console._session not in content
    for action in ("ask", "sign", "decide", "accept", "stop", "discard"):
        for path in ("/" + action, console.owner_path + action):
            request = Request(f"http://127.0.0.1:{port}{path}", data=urlencode({
                "csrf": console.csrf, "mode": "signed", "text": "Brief me on my repositories",
                "request_id": "forged", "proposal": "forged", "event_id": "forged"}).encode())
            with pytest.raises(HTTPError) as failure:
                urlopen(request, timeout=10)
            assert failure.value.code == 403
    assert list(Layout(home).inbox.glob("*.json")) == original_inbox
    assert not Layout(home).stop_file.exists()


def test_owner_bootstrap_is_single_use_scoped_and_not_in_body_events(tmp_path):
    home, key, _, _ = make_body(tmp_path)
    console = Console(home, key=key)
    bootstrap_secret = console._bootstrap
    server = serve(console, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    port = server.server_address[1]
    link = console.owner_url(port)
    try:
        opener = _owner_client(console, port)
        cookie_handler = next(handler for handler in opener.handlers if isinstance(handler, HTTPCookieProcessor))
        cookie = next(iter(cookie_handler.cookiejar))
        assert cookie.path == console.owner_path and cookie.has_nonstandard_attr("HttpOnly")
        assert cookie.get_nonstandard_attr("SameSite") == "Strict"
        assert not cookie_handler.cookiejar._cookies.get("127.0.0.1", {}).get("/")
        with pytest.raises(HTTPError) as failure:
            urlopen(link, timeout=10)
        assert failure.value.code == 403
        page = _get(port, "/")
        assert f"action={console.owner_path}ask" in page
        assert bootstrap_secret not in page and console._session not in page
        _post(port, "/stop", {"csrf": console.csrf, "mode": "signed"})
        envelope = json.loads(next(Layout(home).inbox.glob("*.json")).read_text())
        assert envelope["kind"] == "BODY_STOP"
        assert bootstrap_secret not in json.dumps(envelope) and console._session not in json.dumps(envelope)
    finally:
        _SESSIONS.pop(port, None)
        server.shutdown(); server.server_close(); thread.join(timeout=5)


def test_public_owned_assets_cannot_expose_session_or_execute_owner_forms(running, monkeypatch):
    _, _, console, port = running
    from greg import console as console_module
    malicious = b"<script>fetch('/api/state').then(()=>fetch('/stop',{method:'POST'}))</script><form action=/stop method=post></form>"
    monkeypatch.setattr(console_module, "render_owned_page", lambda *args: malicious)
    with urlopen(f"http://127.0.0.1:{port}/owned/fixture/page", timeout=10) as response:
        policy = response.headers["Content-Security-Policy"]
        content = response.read().decode()
        assert "sandbox;" in policy and "script-src 'none'" in policy and "form-action 'none'" in policy
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers.get("Set-Cookie") is None
        assert console.csrf not in content and console._session not in content and console.owner_path not in content
    with urlopen(f"http://127.0.0.1:{port}/owned", timeout=10) as response:
        assert "name=csrf" not in response.read().decode()
