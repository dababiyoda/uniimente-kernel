"""``greg mcp token``: a hosted MCP server the founder reaches with a plain bearer token, not OAuth.

The founder pastes the token the service gave them. GREG lists the server's tools with it, once, and keeps the token,
the server's address and those tools under ``mcp:<name>``; nothing is kept when the server refuses the token. Mission
Control then shows the server and its tools as it does an OAuth login, and an approved ``mcp.act`` naming the handle
sends that token to that server and nowhere else.

Loopback only: the service is uvicorn with a test certificate behind the fake CONNECT proxy of the confined-egress
tests, and it refuses any request without the right token.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys

import pytest

from greg import mcp_login
from greg.body import Body
from greg.capabilities import CapabilityError, SecretBroker
from tests.greg_fixtures import drop, signed
from tests.integration.test_greg_confined_egress import body_with_confined_egress, certificate, fake_proxy
from tests.integration.test_greg_mcp_remote_mission import notes_service, remote_mission, tick_until
from tests.unit.test_greg_mcp_planner import needs_namespaces

pytest.importorskip("uvicorn")
TOKEN = "TOKEN-VALUE-FIXTURE-registered-7d1f"


@pytest.fixture
def guarded(tmp_path, monkeypatch):
    """The notes service, whose MCP endpoint answers only requests carrying ``Bearer TOKEN`` (its /notes page is
    public, so the mission's own check reads it with no credential)."""
    cert, key = certificate(tmp_path)
    service, port, notes, seen = notes_service(cert, key)
    app = service.config.app

    async def checking(scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/mcp") and \
                dict(scope["headers"]).get(b"authorization") != f"Bearer {TOKEN}".encode():
            await send({"type": "http.response.start", "status": 401, "headers": [(b"content-length", b"0")]})
            await send({"type": "http.response.body", "body": b""})
            return
        await app(scope, receive, send)
    service.config.app = checking
    service.config.loaded_app = checking
    proxy, heads = fake_proxy(port)
    monkeypatch.setenv("HTTPS_PROXY", f"http://127.0.0.1:{proxy.getsockname()[1]}")
    monkeypatch.setenv("https_proxy", f"http://127.0.0.1:{proxy.getsockname()[1]}")
    monkeypatch.setenv("GREG_EGRESS_CAFILE", str(cert))
    yield {"notes": notes, "seen": seen, "heads": heads, "cert": cert}
    service.should_exit = True
    proxy.close()


def register(broker, token, cafile, name="notes-token"):
    return asyncio.run(mcp_login.register_token(name, "https://service.test/mcp", token, broker, cafile=str(cafile)))


def test_a_token_the_server_accepts_is_kept_with_its_server_and_tools(tmp_path, guarded):
    broker = SecretBroker(tmp_path / "secrets.json")
    out = register(broker, TOKEN, guarded["cert"])
    assert out["handle"] == "mcp:notes-token" and out["kind"] == "registered token" and out["renews_at"] is None
    assert [t["name"] for t in out["tools"]] == ["add_note"] and out["tools"][0]["needs"] == ["text"]
    assert TOKEN not in json.dumps(out)
    stored = mcp_login.record(broker, "mcp:notes-token")
    assert stored["tokens"] == {"access_token": TOKEN} and stored["server"] == "https://service.test/mcp"
    assert not mcp_login.expired(stored)                                 # a pasted token is not renewed or aged out
    assert guarded["notes"] == []                                        # listing changed nothing at the service


def test_a_token_the_server_refuses_is_not_kept(tmp_path, guarded):
    broker = SecretBroker(tmp_path / "secrets.json")
    with pytest.raises(CapabilityError, match="did not accept the token") as refused:
        register(broker, "WRONG-TOKEN-VALUE", guarded["cert"])
    assert "WRONG-TOKEN-VALUE" not in str(refused.value)
    assert mcp_login.record(broker, "mcp:notes-token") is None
    for bad in ("", "two words", "\n"):
        with pytest.raises(CapabilityError, match="one word"):
            register(broker, bad, guarded["cert"])
    with pytest.raises(CapabilityError):
        asyncio.run(mcp_login.register_token("notes", "http://service.test/mcp", TOKEN, broker))   # https only


def test_greg_mcp_token_reads_the_token_from_stdin_never_argv(tmp_path, guarded):
    from greg.body import init_body
    home = tmp_path / "body"
    init_body(home, read_roots=[str(tmp_path)])
    env = {**os.environ, "PYTHONPATH": os.getcwd()}
    done = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "mcp", "token", "notes",
                           "https://service.test/mcp"], input=TOKEN + "\n", capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    shown = json.loads(done.stdout)
    assert shown["handle"] == "mcp:notes" and TOKEN not in done.stdout + done.stderr
    refused = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "mcp", "token", "other",
                              "https://service.test/mcp"], input="WRONG\n", capture_output=True, text=True, env=env)
    assert refused.returncode == 2 and "not registered" in refused.stderr and "Traceback" not in refused.stderr
    assert mcp_login.record(SecretBroker(home / "secrets.json"), "mcp:other") is None


@needs_namespaces
def test_an_approved_call_sends_the_registered_token_to_its_server(tmp_path, guarded, monkeypatch):
    from dataclasses import replace
    from greg.capabilities import BUILTINS
    manifest, adapter = BUILTINS["http.get"]
    monkeypatch.setitem(BUILTINS, "http.get", (replace(manifest, egress_allowlist=("service.test",)), adapter))
    home, key, body_id = body_with_confined_egress(tmp_path)
    register(SecretBroker(home / "secrets.json"), TOKEN, guarded["cert"])
    carried = lambda: guarded["seen"].count(f"Bearer {TOKEN}")          # noqa: E731 (requests that carried the token)
    at_registration = carried()
    drop(home, signed(key, body_id, "MISSION", remote_mission("m:registered")))
    with Body(home) as body:
        body.boot()
        assert tick_until(body, "WAITING")["state"] == "WAITING"
        [ask] = [e.payload for e in body.journal.replay("decision.requested")]
    assert ask["authority_requested"]["credentials"] == ["mcp:notes-token"] and TOKEN not in json.dumps(ask)
    assert guarded["notes"] == [] and carried() == at_registration     # the token is not used before approval
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
    with Body(home) as body:
        body.boot()
        out = tick_until(body, "ACHIEVED")
    assert out["state"] == "ACHIEVED" and guarded["notes"] == ["ship the wedge"], out
    assert carried() > at_registration                                  # the approved call sent the registered token
    leaked = [p for p in home.rglob("*") if p.is_file() and p.name != "secrets.json" and TOKEN.encode() in p.read_bytes()]
    assert not leaked, leaked
