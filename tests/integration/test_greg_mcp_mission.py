"""A founder-signed mission uses a tool from an MCP server the founder installed, through the one authority path.

The stand-in server is the hostile one from ``tests/unit/test_greg_mcp_tools.py``. The mission's success check calls
its ``lookup`` tool; the observation crosses the authority office like any other sensor, is journaled with its
receipt, and closes the mission. A mission whose light cone does not name ``mcp.call`` never starts a server.

With ``GREG_TEST_MCP_SERVERS`` pointing at a directory holding the official reference servers (``time/`` and ``git/``,
each a virtualenv with ``mcp-server-time`` / ``mcp-server-git`` on the older ``mcp<2`` SDK; ``filesystem/``, an npm
prefix with ``@modelcontextprotocol/server-filesystem``; all MIT), the same path runs real third-party servers: the
time server answers, and the git and filesystem servers' write tools change nothing the founder owns.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, signed
from tests.unit.test_greg_mcp_tools import SERVER, needs_namespaces


def _install_glossary(data: Path) -> dict:
    (data / "glossary.txt").write_text("rail: the layer that governs the outcome\n")
    install = data / "servers" / "glossary"
    (install / "bin").mkdir(parents=True)
    (install / "server.py").write_text(SERVER)
    launcher = install / "bin" / "serve"
    launcher.write_text(f"#!/bin/sh\nexec {sys.executable} {install / 'server.py'} \"$@\"\n")
    launcher.chmod(0o755)
    return {"server": "glossary", "root": str(install), "command": [str(launcher)],
            "readable": [str(data / "glossary.txt")], "tool": "lookup",
            "arguments": {"path": str(data / "glossary.txt"), "word": "rail"}}


def _check(params: dict, server: str, contains: str) -> dict:
    return {"check_id": f"{server}-answered", "description": f"the {server} server's answer contains {contains!r}",
            "sensor": {"capability": "mcp.call", "params": params, "target": f"mcp:{server}"},
            "predicate": {"op": "contains", "field": "text", "value": contains}}


def _run(home, ticks=3):
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        states = []
        for _ in range(ticks):
            clock.advance(30)
            states.append(body.tick()["missions"][0]["state"])
        observed = [e.payload for e in body.journal.replay("mission.observed")]
        chain_ok, _ = body.ledger.verify_chain()
    return states, observed, chain_ok


@needs_namespaces
def test_a_signed_mission_closes_on_a_tool_the_founder_installed(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    params = _install_glossary(data)
    spec = mission("m:glossary", checks=[_check(params, "glossary", "governs the outcome")], strategies=[],
                   capabilities=["mcp.call"], targets=("mcp:glossary",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    states, observed, chain_ok = _run(home)
    assert "ACHIEVED" in states, (states, observed)
    passed = [o for o in observed if o["check_id"] == "glossary-answered"]
    assert passed and passed[-1]["passed"] is True
    assert chain_ok


@needs_namespaces
def test_a_mission_that_does_not_name_mcp_call_never_starts_a_server(tmp_path, monkeypatch):
    from foundry.systems import mcp_gateway
    started = []
    original = mcp_gateway._call

    async def counting(provider, tool, args):
        started.append(provider.get("name"))
        return await original(provider, tool, args)
    monkeypatch.setattr(mcp_gateway, "_call", counting)
    home, key, body_id, data = make_body(tmp_path)
    params = _install_glossary(data)
    spec = mission("m:glossary", checks=[_check(params, "glossary", "governs the outcome")], strategies=[],
                   capabilities=["fs.read"], targets=("fs:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    states, observed, _ = _run(home)
    assert "ACHIEVED" not in states and started == [], (states, started)


SERVERS = os.environ.get("GREG_TEST_MCP_SERVERS")
real = pytest.mark.skipif(not SERVERS, reason="set GREG_TEST_MCP_SERVERS to a directory with time/ and git/ venvs")


@needs_namespaces
@real
def test_the_official_time_server_answers_a_signed_mission(tmp_path):
    root = Path(SERVERS) / "time"
    home, key, body_id, data = make_body(tmp_path, read_roots=[tmp_path / "data", root])
    params = {"server": "time", "root": str(root), "command": [str(root / "bin" / "mcp-server-time")],
              "tool": "get_current_time", "arguments": {"timezone": "Asia/Tokyo"}}
    spec = mission("m:time", checks=[_check(params, "time", "Asia/Tokyo")], strategies=[],
                   capabilities=["mcp.call"], targets=("mcp:time",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    states, observed, chain_ok = _run(home)
    assert "ACHIEVED" in states, (states, observed)
    assert chain_ok


@needs_namespaces
@real
def test_the_official_git_server_reads_the_founder_repository_and_cannot_change_it(tmp_path):
    from greg import mcp_tools
    from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
    root = Path(SERVERS) / "git"
    repo = tmp_path / "data" / "repo"
    repo.mkdir(parents=True)
    git = ["git", "-c", "user.name=Founder", "-c", "user.email=founder@example.test"]
    subprocess.run([*git, "init", "-q", str(repo)], check=True)
    (repo / "plan.md").write_text("first\n")
    subprocess.run([*git, "-C", str(repo), "add", "plan.md"], check=True)
    subprocess.run([*git, "-C", str(repo), "commit", "-q", "-m", "first"], check=True)
    (repo / "plan.md").write_text("first\nsecond\n")
    subprocess.run([*git, "-C", str(repo), "add", "plan.md"], check=True)        # staged: a commit has work to do
    (repo / "notes.md").write_text("unstaged\n")
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path / "data", root),
                            secrets=SecretBroker(tmp_path / "s.json"), manifest=BUILTINS["mcp.call"][0],
                            target="mcp:git", mission_id="m:git")
    base = {"server": "git", "root": str(root), "command": [str(root / "bin" / "mcp-server-git")],
            "readable": [str(repo)]}
    status = mcp_tools.call({**base, "tool": "git_status", "arguments": {"repo_path": str(repo)}}, ctx)
    assert "plan.md" in status["text"] and "notes.md" in status["text"]   # it reads the founder's repository
    for tool, arguments in (("git_add", {"repo_path": str(repo), "files": ["notes.md"]}),
                            ("git_commit", {"repo_path": str(repo), "message": "planted"})):
        with pytest.raises(CapabilityError, match="Read-only file system"):   # the OS refused, not the server
            mcp_tools.call({**base, "tool": tool, "arguments": arguments}, ctx)
    after = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
    staged = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--name-only"], capture_output=True,
                            text=True).stdout
    assert after == head and staged.split() == ["plan.md"]              # nothing committed, nothing new staged


@needs_namespaces
@real
def test_the_official_filesystem_server_reads_through_a_mission_and_cannot_write(tmp_path):
    """``filesystem/`` is ``npm install --prefix filesystem @modelcontextprotocol/server-filesystem`` (MIT): a Node
    server found through ``node_modules/.bin``, started with the directory it may serve."""
    from greg import mcp_tools
    from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
    root = Path(SERVERS) / "filesystem"
    notes = tmp_path / "data" / "notes"
    notes.mkdir(parents=True)
    (notes / "plan.md").write_text("ship the wedge\n")
    entry = root / "node_modules" / ".bin" / "mcp-server-filesystem"
    params = {"server": "filesystem", "root": str(root), "command": [str(entry), str(notes)], "readable": [str(notes)],
              "tool": "read_text_file", "arguments": {"path": str(notes / "plan.md")}}
    home, key, body_id, data = make_body(tmp_path, read_roots=[tmp_path / "data", root])
    spec = mission("m:files", checks=[_check(params, "filesystem", "ship the wedge")], strategies=[],
                   capabilities=["mcp.call"], targets=("mcp:filesystem",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    states, observed, chain_ok = _run(home)
    assert "ACHIEVED" in states and chain_ok, (states, observed)
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path / "data", root),
                            secrets=SecretBroker(tmp_path / "s.json"), manifest=BUILTINS["mcp.call"][0],
                            target="mcp:filesystem", mission_id="m:files")
    for tool, arguments in (("write_file", {"path": str(notes / "planted.md"), "content": "x"}),
                            ("edit_file", {"path": str(notes / "plan.md"),
                                           "edits": [{"oldText": "wedge", "newText": "HACKED"}]})):
        with pytest.raises(CapabilityError, match="(?i)read-only file system"):
            mcp_tools.call({**params, "tool": tool, "arguments": arguments}, ctx)
    assert sorted(p.name for p in notes.iterdir()) == ["plan.md"]
    assert (notes / "plan.md").read_text() == "ship the wedge\n"
