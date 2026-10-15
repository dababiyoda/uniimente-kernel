"""``mcp.act``: an installed MCP tool that may change something, inside exactly what the founder signed.

The stand-in "scribe" server writes files, reports a hash of an environment variable (never the value), and tries to
write where it was not told to. It may write only the paths the mission names; everything else stays read-only.
Credentials reach it by ``mcp:<name>`` handle and never appear in what GREG records.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import sys

import pytest

from foundry.systems import relay_door
from greg import mcp_tools
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
from tests.unit.test_greg_mcp_planner import needs_namespaces

SCRIBE = r'''
import hashlib, json, os, socket
from mcp.server.mcpserver import MCPServer

server = MCPServer("scribe")


@server.tool()
def write_note(path: str, text: str) -> str:
    """Write a note to a file."""
    try:
        with open(path, "w") as fh:
            fh.write(text)
    except OSError as exc:               # say what the operating system said (the SDK would hide it)
        return f"refused: {exc.strerror}"
    return "wrote " + path


@server.tool()
def env_digest(name: str) -> str:
    """The SHA-256 of an environment variable's value (never the value)."""
    return hashlib.sha256(os.environ.get(name, "").encode()).hexdigest()


@server.tool()
def reach(hosts: list) -> str:
    """Try each host through the proxy the environment names, and the network directly."""
    out = {}
    proxy = os.environ.get("HTTPS_PROXY", "")
    for host in hosts:
        if not proxy:
            out[host] = "no proxy"
            continue
        s = socket.create_connection(("127.0.0.1", int(proxy.rsplit(":", 1)[1])))
        s.sendall(("CONNECT %s:443 HTTP/1.1\r\nHost: %s:443\r\n\r\n" % (host, host)).encode())
        out[host] = s.recv(120).split(b"\r\n")[0].decode()
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=2)
        out["direct"] = "REACHED"
    except OSError as exc:
        out["direct"] = type(exc).__name__
    return json.dumps(out)


if __name__ == "__main__":
    server.run("stdio")
'''


def install_scribe(root: Path) -> dict:
    folder = root / "tools" / "scribe"
    (folder / "bin").mkdir(parents=True)
    (folder / "server.py").write_text(SCRIBE)
    entry = folder / "bin" / "mcp-server-scribe"
    entry.write_text(f"#!/bin/sh\nexec {sys.executable} {folder / 'server.py'} \"$@\"\n")
    entry.chmod(0o755)
    return {"server": "scribe", "root": str(folder), "command": [str(entry)]}


@pytest.fixture
def world(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "notes").mkdir(parents=True)
    (data / "kept").mkdir()
    (data / "kept" / "plan.md").write_text("unchanged\n")
    base = install_scribe(data)
    secrets = SecretBroker(tmp_path / "secrets.json")
    secrets.put("mcp:scribe-token", "TOKEN-VALUE-FIXTURE")
    monkeypatch.setattr(relay_door, "_PRIVATE_ROOTS", set())
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(data,), secrets=secrets,
                            manifest=BUILTINS["mcp.act"][0], target="mcp:scribe", mission_id="m:scribe")
    return {"data": data, "base": base, "ctx": ctx}


@needs_namespaces
def test_it_writes_only_where_the_mission_names(world):
    data, base, ctx = world["data"], world["base"], world["ctx"]
    params = {**base, "tool": "write_note", "writable": [str(data / "notes")], "readable": [str(data / "kept")],
              "arguments": {"path": str(data / "notes" / "today.md"), "text": "the wedge first"}}
    out = mcp_tools.act(params, ctx)
    assert (data / "notes" / "today.md").read_text() == "the wedge first"
    assert out["confinement"]["writable"] == [str((data / "notes").resolve())]
    assert out["confinement"]["network"] == "none"
    shown = mcp_tools.act({**params, "arguments": {"path": str(data / "kept" / "plan.md"), "text": "x"}}, ctx)
    assert shown["result"] == "refused: Read-only file system"            # shown, not writable
    mcp_tools.act({**params, "arguments": {"path": str(data / "planted.md"), "text": "x"}}, ctx)
    assert (data / "kept" / "plan.md").read_text() == "unchanged\n"
    assert not (data / "planted.md").exists()            # not shown: whatever it wrote landed in discarded scratch


@needs_namespaces
def test_a_credential_reaches_the_server_by_handle_and_never_the_record(world):
    base, ctx = world["base"], world["ctx"]
    params = {**base, "tool": "env_digest", "writable": [str(world["data"] / "notes")],
              "secrets": {"SCRIBE_TOKEN": "mcp:scribe-token"}, "arguments": {"name": "SCRIBE_TOKEN"}}
    out = mcp_tools.act(params, ctx)
    assert out["result"] == hashlib.sha256(b"TOKEN-VALUE-FIXTURE").hexdigest()
    assert out["confinement"]["secrets"] == ["SCRIBE_TOKEN"]
    assert "TOKEN-VALUE-FIXTURE" not in repr(out)


@pytest.mark.parametrize("change, why", [
    ({"secrets": {"SCRIBE_TOKEN": "github_token"}}, "mcp:<name> credential handle"),
    ({"secrets": {"scribe token": "mcp:scribe-token"}}, "UPPER_CASE environment name"),
    ({"secrets": {"SCRIBE_TOKEN": "mcp:missing"}}, "unavailable"),
    ({"hosts": ["https://api.example.test"]}, "exact host names"),
    ({"hosts": ["*.example.test"]}, "exact host names"),
    ({"hosts": ["api.example.test"]}, "confined egress"),
    ({"writable": []}, "nothing to act on"),
])
def test_what_the_mission_did_not_sign_exactly_is_refused_before_anything_starts(world, monkeypatch, change, why):
    from foundry.systems import mcp_gateway
    monkeypatch.setattr(mcp_gateway, "_call", lambda *a, **k: pytest.fail("a server was started"))
    params = {**world["base"], "tool": "write_note", "writable": [str(world["data"] / "notes")],
              "arguments": {"path": "x", "text": "y"}, **change}
    with pytest.raises(CapabilityError, match=why):
        mcp_tools.act(params, world["ctx"])


def test_a_writable_path_outside_the_read_roots_or_missing_is_refused(world, tmp_path):
    for path, why in ((tmp_path / "elsewhere", "outside permitted roots"),
                      (world["data"] / "does-not-exist", "does not exist")):
        if why == "outside permitted roots":
            path.mkdir()
        with pytest.raises(CapabilityError, match=why):
            mcp_tools.act({**world["base"], "tool": "write_note", "writable": [str(path)]}, world["ctx"])


def test_the_capability_asks_for_every_use_and_is_never_retried_blindly():
    manifest = BUILTINS["mcp.act"][0]
    assert manifest.consequence_class == "external_contact" and manifest.retry_safe is False
    assert manifest.network == "signed-hosts" and manifest.filesystem == "named-write" and not manifest.validate()
    from greg.missions import CONFINED_EGRESS
    assert "mcp.act" in CONFINED_EGRESS and "mcp.call" not in CONFINED_EGRESS


@needs_namespaces
def test_a_writable_folder_inside_a_readable_one_stays_writable(world):
    data, base, ctx = world["data"], world["base"], world["ctx"]
    (data / "kept" / "drafts").mkdir()
    params = {**base, "tool": "write_note", "writable": [str(data / "kept" / "drafts")],
              "readable": [str(data / "kept")],
              "arguments": {"path": str(data / "kept" / "drafts" / "d.md"), "text": "draft"}}
    mcp_tools.act(params, replace(ctx))
    assert (data / "kept" / "drafts" / "d.md").read_text() == "draft"


def test_the_founder_finds_it_by_asking_for_a_change():
    from greg.discover import discover
    top = [r["id"] for r in discover("write a file with a tool from the MCP server I installed", limit=3,
                                     kinds=("capability",))]
    assert top[0] == "mcp.act", top
    neutral = [r["id"] for r in discover("use a tool from the MCP server I installed", limit=3, kinds=("capability",))]
    assert neutral[0] == "mcp.call", neutral                     # a plain request finds the read-only call first


@needs_namespaces
def test_a_single_file_can_be_granted_and_the_installation_stays_read_only(world):
    data, base, ctx = world["data"], world["base"], world["ctx"]
    (data / "notes" / "log.md").write_text("old\n")
    (data / "notes" / "other.md").write_text("other\n")
    params = {**base, "tool": "write_note", "writable": [str(data / "notes" / "log.md")],
              "arguments": {"path": str(data / "notes" / "log.md"), "text": "new\n"}}
    assert mcp_tools.act(params, ctx)["result"].startswith("wrote ")
    assert (data / "notes" / "log.md").read_text() == "new\n"
    sibling = mcp_tools.act({**params, "arguments": {"path": str(data / "notes" / "other.md"), "text": "x"}}, ctx)
    planted = mcp_tools.act({**params, "arguments": {"path": str(Path(base["root"]) / "server.py"), "text": "x"}}, ctx)
    assert (data / "notes" / "other.md").read_text() == "other\n" and "MCPServer" in (Path(base["root"]) / "server.py").read_text()
    assert planted["result"] == "refused: Read-only file system", (sibling, planted)


def test_the_founder_stores_a_server_credential_by_its_mcp_handle(tmp_path):
    import json
    import subprocess
    from greg.body import init_body
    home = tmp_path / "body"
    init_body(home, read_roots=[str(tmp_path)])
    root = Path(__file__).resolve().parents[2]

    def greg(*args, stdin=""):
        return subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "secret", *args], input=stdin,
                              capture_output=True, text=True, cwd=root, timeout=60)
    stored = greg("set", "mcp:courier-token", stdin="TOKEN-VALUE-FIXTURE\n")
    assert stored.returncode == 0 and "TOKEN-VALUE-FIXTURE" not in stored.stdout + stored.stderr, stored.stderr[-300:]
    assert "mcp:courier-token" in json.loads(greg("list").stdout)["stored"]
    for bad in ("mcp:", "mcp:Courier Token", "courier-token"):
        refused = greg("set", bad, stdin="x\n")
        assert refused.returncode != 0 and "unknown credential handle" in refused.stdout + refused.stderr, bad
    assert SecretBroker(home / "secrets.json").names() == ["mcp:courier-token"]


REMOTE = {"server": "scribe", "url": "https://service.test/mcp", "tool": "add_note", "arguments": {"text": "x"}}


@pytest.mark.parametrize("change, why", [
    ({"url": "http://service.test/mcp"}, "url must be https"),
    ({"url": "https://user:pw@service.test/mcp"}, "url must be https"),
    ({"url": "https://service.test:8443/mcp"}, "url must be https"),
    ({"url": "https://*.test/mcp"}, "url must be https"),
    ({"hosts": ["other.test"]}, "exactly its own host"),
    ({"writable": ["/tmp"]}, "no local paths"),
    ({"secrets": {"TOKEN": "mcp:scribe-token"}}, "no local paths and no environment"),
    ({"bearer": "github_token"}, "mcp:<name> credential handle"),
    ({}, "confined egress"),
    ({"bearer": "mcp:missing", "_egress": True}, "unavailable"),
])
def test_a_remote_call_not_signed_exactly_is_refused_before_any_client_starts(world, monkeypatch, change, why):
    import subprocess
    from types import SimpleNamespace
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("a client was started"))
    ctx = world["ctx"]
    if change.pop("_egress", False):
        ctx = replace(ctx, egress=SimpleNamespace(journal=None, connect=None, proxy=None))
    with pytest.raises(CapabilityError, match=why):
        mcp_tools.act({**REMOTE, **change}, ctx)


def test_a_remote_server_is_never_a_read_only_call(world):
    with pytest.raises(CapabilityError, match="cannot make a call read-only"):
        mcp_tools.call({**REMOTE}, replace(world["ctx"], manifest=BUILTINS["mcp.call"][0]))
