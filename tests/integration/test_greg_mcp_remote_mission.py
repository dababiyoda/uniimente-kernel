"""A remote MCP server (Streamable HTTP) on GREG's mission path: approved, confined, through the relay.

A hosted "notes" service speaks MCP at ``https://service.test/mcp`` and shows its notes at ``/notes``. A mission asks
its ``add_note`` tool for a change and checks the change itself with a confined ``http.get`` of ``/notes``. Because
the tool runs on someone else's machine, GREG cannot make the call read-only: it is an ``mcp.act``, so the mission
waits for the founder's decision, which shows the server, the one host it may reach and the credential handle.

After approval GREG's own MCP client runs in the door namespace with no network of its own. Its only way out is the
door to a relay allowing ``service.test:443``, chained through the mandated proxy. The bearer token reaches the
service's request header and appears in nothing GREG records.

Loopback only: the service is uvicorn with a test certificate, behind the fake CONNECT proxy of the confined-egress
tests. Nothing resolves a real name or leaves the machine.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import socket
import threading
import time

import pytest

from greg.body import Body
from greg.capabilities import BUILTINS, SecretBroker
from tests.greg_fixtures import drop, mission, signed
from tests.integration.test_greg_confined_egress import body_with_confined_egress, certificate, fake_proxy
from tests.unit.test_greg_mcp_planner import needs_namespaces

pytest.importorskip("uvicorn")
TOKEN = "TOKEN-VALUE-FIXTURE-remote-3b9e"


def notes_service(cert, key):
    """The hosted service: MCP at /mcp (one tool that adds a note), the notes themselves at /notes."""
    import uvicorn
    from mcp.server.mcpserver import MCPServer
    from mcp.server.transport_security import TransportSecuritySettings
    from starlette.responses import JSONResponse
    notes, seen = [], []
    server = MCPServer("notes")

    @server.tool()
    def add_note(text: str) -> str:
        """Add a note to the shared notes."""
        notes.append(text)
        return f"{len(notes)} notes"

    app = server.streamable_http_app(transport_security=TransportSecuritySettings(
        allowed_hosts=["service.test", "service.test:443"], allowed_origins=["https://service.test"]))

    async def listing(request):
        return JSONResponse(notes)
    app.add_route("/notes", listing)

    async def recording(scope, receive, send):        # what reached the service: the Authorization header
        if scope["type"] == "http":
            seen.append(dict(scope["headers"]).get(b"authorization", b"").decode())
        await app(scope, receive, send)

    sock = socket.create_server(("127.0.0.1", 0))
    service = uvicorn.Server(uvicorn.Config(recording, ssl_certfile=str(cert), ssl_keyfile=str(key),
                                            log_level="error", lifespan="on"))
    threading.Thread(target=service.run, kwargs={"sockets": [sock]}, daemon=True).start()
    for _ in range(100):
        if service.started:
            break
        time.sleep(0.05)
    return service, sock.getsockname()[1], notes, seen


@pytest.fixture
def remote(tmp_path, monkeypatch):
    cert, key = certificate(tmp_path)
    service, port, notes, seen = notes_service(cert, key)
    proxy, heads = fake_proxy(port)
    monkeypatch.setenv("HTTPS_PROXY", f"http://fixture-user:fixture-secret@127.0.0.1:{proxy.getsockname()[1]}")
    monkeypatch.setenv("GREG_EGRESS_CAFILE", str(cert))
    manifest, adapter = BUILTINS["http.get"]
    monkeypatch.setitem(BUILTINS, "http.get", (replace(manifest, egress_allowlist=("service.test",)), adapter))
    yield {"notes": notes, "seen": seen, "heads": heads}
    service.should_exit = True
    proxy.close()


def remote_mission(mission_id, *, text="ship the wedge", bearer="mcp:notes-token"):
    check = {"check_id": "noted", "description": "the service shows the note",
             "sensor": {"capability": "http.get", "params": {"url": "https://service.test/notes"},
                        "target": "https:service.test"},
             "predicate": {"op": "contains", "field": "text", "value": text}}
    act = {"action_id": "add", "capability": "mcp.act", "target": "mcp:notes", "advances": ["noted"],
           "rationale": "the hosted notes service's own tool",
           "params": {"server": "notes", "url": "https://service.test/mcp", "tool": "add_note",
                      "arguments": {"text": text}, **({"bearer": bearer} if bearer else {})}}
    return mission(mission_id, checks=[check], strategies=[act], capabilities=["mcp.act", "http.get"],
                   targets=("mcp:notes", "https:service.test"), ceiling="read_only")


def tick_until(body, state, limit=6):
    for _ in range(limit):
        out = body.tick()["missions"][0]
        if out["state"] == state:
            break
    return out


@needs_namespaces
def test_a_remote_tool_runs_after_approval_through_the_relay_with_its_credential(tmp_path, remote, monkeypatch):
    import subprocess
    launched, real = [], subprocess.run

    def spy(argv, *a, **k):                     # what started GREG's MCP client, and with which environment
        if "greg.mcp_remote" in argv:
            launched.append((list(argv), dict(k.get("env") or {})))
        return real(argv, *a, **k)
    monkeypatch.setattr(subprocess, "run", spy)
    home, key, body_id = body_with_confined_egress(tmp_path)
    SecretBroker(home / "secrets.json").put("mcp:notes-token", TOKEN)
    drop(home, signed(key, body_id, "MISSION", remote_mission("m:remote-note")))
    with Body(home) as body:
        body.boot()
        assert tick_until(body, "WAITING")["state"] == "WAITING"
        [ask] = [e.payload for e in body.journal.replay("decision.requested")]
    shown = ask["authority_requested"]
    assert shown["remote_server"] == "https://service.test/mcp" and shown["tool"] == "notes.add_note"
    assert shown["may_reach"] == ["service.test:443 through the relay"] and shown["may_write"] == "nothing"
    assert shown["credentials"] == ["mcp:notes-token"] and TOKEN not in json.dumps(ask)
    assert remote["notes"] == []                                       # nothing reached the service before approval
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
    with Body(home) as body:
        body.boot()
        out = tick_until(body, "ACHIEVED")
        receipts = [r.payload["result"].get("output") for r in body.ledger.by_type("receipt")]
        chain_ok, _ = body.ledger.verify_chain()
    assert out["state"] == "ACHIEVED" and chain_ok, out
    assert remote["notes"] == ["ship the wedge"]                       # exactly once
    assert f"Bearer {TOKEN}" in remote["seen"]                         # the credential reached the service
    [acted] = [r for r in receipts if isinstance(r, dict) and r.get("tool") == "add_note"]
    assert acted["result"] == "1 notes" and acted["trust"] == "untrusted-external-data"
    assert acted["confinement"]["network"] == "only service.test through the relay"
    journal = [json.loads(line) for line in (home / "egress-journal.jsonl").read_text().splitlines()]
    assert {(e["host"], e["verdict"]) for e in journal if e["identity"] == "mcp.act"} == {("service.test", "ALLOWED")}
    assert all(h.startswith("CONNECT service.test:443 ") for h in remote["heads"])
    leaked = [p for p in home.rglob("*") if p.is_file() and p.name != "secrets.json" and TOKEN.encode() in p.read_bytes()]
    assert not leaked, leaked                       # not the ledger, the journals, the receipts or the workspace
    [(argv, env)] = launched                        # one client, started once, after approval
    assert argv[0].endswith("bwrap") and "--unshare-net" in argv              # no network of its own
    body_home = home.resolve()
    masks = [Path(argv[i + 1]) for i in range(len(argv) - 1) if argv[i] == "--tmpfs"]
    assert any(m == body_home or m in body_home.parents for m in masks)        # the body home is hidden
    shown = [Path(argv[i + 1]) for i in range(len(argv) - 1) if argv[i] in ("--bind", "--ro-bind") and argv[i + 1] != "/"]
    [scratch] = [s for s in shown if s == body_home or body_home in s.parents]  # only the call's own scratch
    assert scratch.parent.name == "m_remote-note" and not scratch.exists()        # and it is discarded
    assert TOKEN not in " ".join(argv) and env["GREG_MCP_BEARER"] == TOKEN      # by environment, never in argv


@needs_namespaces
def test_a_rejected_remote_call_never_reaches_the_service(tmp_path, remote):
    home, key, body_id = body_with_confined_egress(tmp_path)
    SecretBroker(home / "secrets.json").put("mcp:notes-token", TOKEN)
    drop(home, signed(key, body_id, "MISSION", remote_mission("m:remote-rejected")))
    with Body(home) as body:
        body.boot()
        tick_until(body, "WAITING")
        [ask] = [e.payload for e in body.journal.replay("decision.requested")]
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "reject"}))
    with Body(home) as body:
        body.boot()
        for _ in range(3):
            out = body.tick()["missions"][0]
    assert out["state"] != "ACHIEVED" and remote["notes"] == []
    assert not [s for s in remote["seen"] if s]                        # no request with the credential arrived
