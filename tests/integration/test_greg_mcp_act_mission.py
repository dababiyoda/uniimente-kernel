"""``mcp.act`` on GREG's mission path: a consequential MCP tool runs only after the founder approves its exact scope.

Two stand-in servers installed the way a founder installs one. "scribe" writes a note. "courier" fetches a page from
a host and saves it. Both are signed into missions whose light cone stops at read-only, so the act waits for the
founder's decision on its exact scope and runs only after the approval. Then:

  - the scribe writes only the folder the mission names;
  - the courier reaches only the signed host, through the body's relay and the mandated proxy, and a second host and
    the direct network are refused;
  - the courier's credential reaches its environment by handle and appears in nothing GREG records.

Loopback only: the fake CONNECT proxy and TLS server from the confined-egress tests. Nothing leaves the machine.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

from greg.body import Body
from greg.capabilities import SecretBroker
from tests.greg_fixtures import drop, make_body, mission, signed
from tests.integration.test_greg_confined_egress import body_with_confined_egress, network  # noqa: F401 (fixture)
from tests.unit.test_greg_mcp_act import install_scribe
from tests.unit.test_greg_mcp_planner import needs_namespaces

COURIER = r'''
import hashlib, json, os, socket, ssl
from mcp.server.mcpserver import MCPServer

server = MCPServer("courier")


def _connect(host):
    proxy = os.environ.get("HTTPS_PROXY", "")
    if not proxy:
        return None, "no proxy"
    s = socket.create_connection(("127.0.0.1", int(proxy.rsplit(":", 1)[1])))
    s.sendall(("CONNECT %s:443 HTTP/1.1\r\nHost: %s:443\r\n\r\n" % (host, host)).encode())
    head = b""
    while b"\r\n\r\n" not in head:
        chunk = s.recv(1)
        if not chunk:
            break
        head += chunk
    status = head.split(b"\r\n")[0].decode()
    return (s if " 200 " in status else None), status


@server.tool()
def fetch_to(host: str, path: str, save_to: str, cafile: str, also_try: str) -> str:
    """Fetch https://<host><path> with the token in COURIER_TOKEN and save what happened to a file."""
    record = {}
    s, record["allowed"] = _connect(host)
    if s is not None:
        tls = ssl.create_default_context(cafile=cafile).wrap_socket(s, server_hostname=host)
        token = os.environ.get("COURIER_TOKEN", "")
        tls.sendall(("GET %s HTTP/1.1\r\nHost: %s\r\nAuthorization: Bearer %s\r\nConnection: close\r\n\r\n"
                     % (path, host, token)).encode())
        reply = b""
        while True:
            chunk = tls.recv(65536)
            if not chunk:
                break
            reply += chunk
        record["body"] = reply.split(b"\r\n\r\n", 1)[-1].decode()
        record["token_sha256"] = hashlib.sha256(token.encode()).hexdigest()
    _, record["other_host"] = _connect(also_try)
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=2)
        record["direct"] = "REACHED"
    except OSError as exc:
        record["direct"] = type(exc).__name__
    with open(save_to, "w") as fh:
        json.dump(record, fh)
    return "saved " + save_to


if __name__ == "__main__":
    server.run("stdio")
'''

TOKEN = "TOKEN-VALUE-FIXTURE-7d1c"


def install_courier(root: Path) -> dict:
    folder = root / "tools" / "courier"
    (folder / "bin").mkdir(parents=True)
    (folder / "server.py").write_text(COURIER)
    entry = folder / "bin" / "mcp-server-courier"
    entry.write_text(f"#!/bin/sh\nexec {sys.executable} {folder / 'server.py'} \"$@\"\n")
    entry.chmod(0o755)
    return {"server": "courier", "root": str(folder), "command": [str(entry)]}


def act_mission(mission_id: str, base: dict, params: dict, *, check_path: Path, text: str) -> dict:
    check = {"check_id": "done", "description": f"{check_path.name} contains {text}",
             "sensor": {"capability": "fs.read", "params": {"path": str(check_path)}, "target": f"fs:{check_path.name}"},
             "predicate": {"op": "contains", "field": "text", "value": text}}
    strategy = {"action_id": "act", "capability": "mcp.act", "params": {**base, **params},
                "target": f"mcp:{base['server']}", "advances": ["done"], "rationale": "the founder's installed tool"}
    return mission(mission_id, checks=[check], strategies=[strategy], capabilities=["mcp.act", "fs.read"],
                   targets=(f"mcp:{base['server']}", "fs:*"), ceiling="read_only")


def tick_until(body, states, limit=6):
    for _ in range(limit):
        out = body.tick()["missions"][0]
        if out["state"] in states:
            return out
    return out


def approval(body):
    [ask] = [e.payload for e in body.journal.replay("decision.requested")]
    return ask


@needs_namespaces
def test_a_write_waits_for_the_founder_and_lands_only_where_the_mission_names(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    (data / "notes").mkdir()
    (data / "kept").mkdir()
    (data / "kept" / "plan.md").write_text("unchanged\n")
    base = install_scribe(data)
    note = data / "notes" / "today.md"
    spec = act_mission("m:scribe-note", base, {
        "tool": "write_note", "writable": [str(data / "notes")], "readable": [str(data / "kept")],
        "arguments": {"path": str(note), "text": "the wedge first"}}, check_path=note, text="the wedge first")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        assert tick_until(body, {"WAITING"})["state"] == "WAITING"
        ask = approval(body)
        shown = ask["authority_requested"]
        assert ask["kind"] == "APPROVAL" and shown["capability"] == "mcp.act"
        assert shown["consequence_class"] == "external_contact" and shown["tool"] == "scribe.write_note"
        assert shown["may_write"] == [str(data / "notes")] and shown["may_reach"] == "no network"   # before answering
        assert not note.exists() and not list(body.journal.replay("mission.action"))   # nothing ran before the answer
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
    with Body(home) as body:
        body.boot()
        out = tick_until(body, {"ACHIEVED"})
        receipts = [r.payload["result"].get("output") for r in body.ledger.by_type("receipt")]
        chain_ok, _ = body.ledger.verify_chain()
    assert out["state"] == "ACHIEVED" and chain_ok, out
    assert note.read_text() == "the wedge first" and (data / "kept" / "plan.md").read_text() == "unchanged\n"
    [acted] = [r for r in receipts if isinstance(r, dict) and r.get("tool") == "write_note"]
    assert acted["confinement"]["writable"] == [str((data / "notes").resolve())]
    assert acted["confinement"]["network"] == "none" and acted["trust"] == "untrusted-external-data"


@needs_namespaces
def test_a_rejected_scope_never_runs(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    (data / "notes").mkdir()
    base = install_scribe(data)
    note = data / "notes" / "today.md"
    spec = act_mission("m:scribe-rejected", base, {
        "tool": "write_note", "writable": [str(data / "notes")],
        "arguments": {"path": str(note), "text": "x"}}, check_path=note, text="x")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        tick_until(body, {"WAITING"})
        ask = approval(body)
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "reject"}))
    with Body(home) as body:
        body.boot()
        for _ in range(4):
            out = body.tick()["missions"][0]
        acted = [e.payload for e in body.journal.replay("mission.action")]
        receipts = list(body.ledger.by_type("receipt"))
    assert out["state"] != "ACHIEVED" and not note.exists()
    assert all(a["status"] == "REFUSED" for a in acted if a["capability"] == "mcp.act")
    assert not [r for r in receipts if r.payload["result"].get("output", {}).get("tool") == "write_note"]


@needs_namespaces
def test_a_networked_tool_reaches_only_the_signed_host_and_its_credential_stays_out_of_the_record(tmp_path, network):
    home, key, body_id = body_with_confined_egress(tmp_path)
    SecretBroker(home / "secrets.json").put("mcp:courier-token", TOKEN)
    data = tmp_path / "data"
    (data / "inbox").mkdir(parents=True)
    base = install_courier(data)
    saved = data / "inbox" / "fetched.json"
    cafile = tmp_path / "cert.pem"
    spec = act_mission("m:courier", base, {
        "tool": "fetch_to", "writable": [str(data / "inbox")], "readable": [str(cafile)],
        "hosts": ["service.test"], "secrets": {"COURIER_TOKEN": "mcp:courier-token"},
        "arguments": {"host": "service.test", "path": "/hello", "save_to": str(saved), "cafile": str(cafile),
                      "also_try": "elsewhere.test"}}, check_path=saved, text="hello-from-tls")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        tick_until(body, {"WAITING"})
        ask = approval(body)
        assert ask["authority_requested"]["may_reach"] == ["service.test:443 through the relay"]
        assert ask["authority_requested"]["credentials"] == ["mcp:courier-token"]
        assert TOKEN not in json.dumps(ask)                      # the ask names the handle, never the value
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
    with Body(home) as body:
        body.boot()
        out = tick_until(body, {"ACHIEVED"})
        chain_ok, _ = body.ledger.verify_chain()
    assert out["state"] == "ACHIEVED" and chain_ok, out
    record = json.loads(saved.read_text())
    assert record["body"] == "hello-from-tls" and record["allowed"].startswith("HTTP/1.1 200")
    assert record["token_sha256"] == hashlib.sha256(TOKEN.encode()).hexdigest()       # the server had the value
    assert record["other_host"].startswith("HTTP/1.1 403") and record["direct"] != "REACHED"
    journal = [json.loads(line) for line in (home / "egress-journal.jsonl").read_text().splitlines()]
    mine = [(e["host"], e["verdict"]) for e in journal if e["identity"] == "mcp.act"]
    assert ("service.test", "ALLOWED") in mine and ("elsewhere.test", "DENIED") in mine
    assert all(h.startswith("CONNECT service.test:443 ") for h in network)            # the proxy saw one host only
    leaked = [p for p in home.rglob("*") if p.is_file() and p.name != "secrets.json"
              and TOKEN.encode() in p.read_bytes()]
    assert not leaked, leaked                                    # not the ledger, journals, receipts or workspace


SERVERS = os.environ.get("GREG_TEST_MCP_SERVERS")


@needs_namespaces
@pytest.mark.skipif(not SERVERS, reason="set GREG_TEST_MCP_SERVERS to a directory with filesystem/ (npm prefix)")
def test_the_official_filesystem_server_writes_only_the_folder_the_founder_approved(tmp_path):
    """``@modelcontextprotocol/server-filesystem`` (MIT), serving two folders it would happily write. GREG lets it
    write the one the approved mission names; the other stays read-only, so its own write fails."""
    from greg import mcp_tools
    from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
    root = Path(SERVERS) / "filesystem"
    entry = root / "node_modules" / ".bin" / "mcp-server-filesystem"
    data = tmp_path / "data"
    (data / "notes").mkdir(parents=True)
    (data / "kept").mkdir()
    (data / "kept" / "plan.md").write_text("ship the wedge\n")
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data, root])
    note = data / "notes" / "today.md"
    base = {"server": "filesystem", "root": str(root), "command": [str(entry), str(data / "notes"), str(data / "kept")]}
    params = {"tool": "write_file", "writable": [str(data / "notes")], "readable": [str(data / "kept")],
              "arguments": {"path": str(note), "content": "the wedge first\n"}}
    drop(home, signed(key, body_id, "MISSION", act_mission("m:fs-write", base, params, check_path=note,
                                                           text="the wedge first")))
    with Body(home) as body:
        body.boot()
        tick_until(body, {"WAITING"})
        ask = approval(body)
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
    with Body(home) as body:
        body.boot()
        out = tick_until(body, {"ACHIEVED"})
        chain_ok, _ = body.ledger.verify_chain()
    assert out["state"] == "ACHIEVED" and chain_ok and note.read_text() == "the wedge first\n", out
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(data, root), secrets=SecretBroker(tmp_path / "s.json"),
                            manifest=BUILTINS["mcp.act"][0], target="mcp:filesystem", mission_id="m:fs-write")
    with pytest.raises(CapabilityError, match="(?i)read-only file system"):
        mcp_tools.act({**base, **params, "arguments": {"path": str(data / "kept" / "plan.md"),
                                                       "content": "HACKED\n"}}, ctx)
    assert (data / "kept" / "plan.md").read_text() == "ship the wedge\n"
