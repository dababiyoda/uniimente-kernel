"""Installed MCP servers become reachable from the founder's words and visible in Mission Control.

GREG finds a server the founder installed under its read roots (a folder whose ``bin`` holds
``mcp-server-<name>``), lists its tools exactly as a mission would run it (confined, no network, read-only), and turns
words that name the server and a tool into one ``mcp.call`` mission. Whatever the words do not settle (which server,
which tool, an argument) becomes a question, never a guess.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from greg import mcp_tools
from greg.missions import validate_mission
from greg.planner import PlannerContext, authority_summary, propose

NOTES = r'''
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

server = MCPServer("notes")


@server.tool(annotations=ToolAnnotations(readOnlyHint=True))
def count_lines(path: str) -> str:
    """Count the lines of a text file."""
    with open(path) as fh:
        return f"{sum(1 for _ in fh)} lines"


@server.tool()
def append_line(path: str, line: str) -> str:
    """Append a line to a text file."""
    with open(path, "a") as fh:
        fh.write(line + "\n")
    return "appended"


if __name__ == "__main__":
    server.run("stdio")
'''


def install_notes(root: Path) -> Path:
    """Install the stand-in the way a founder installs a server: its own folder, an mcp-server-<name> entry point."""
    folder = root / "tools" / "notes"
    (folder / "bin").mkdir(parents=True)
    (folder / "server.py").write_text(NOTES)
    entry = folder / "bin" / "mcp-server-notes"
    entry.write_text(f"#!/bin/sh\nexec {sys.executable} {folder / 'server.py'} \"$@\"\n")
    entry.chmod(0o755)
    return folder


def _netns():
    bwrap = shutil.which("bwrap")
    if not bwrap or not sys.platform.startswith("linux"):
        return False
    return subprocess.run([bwrap, "--unshare-user", "--unshare-net", "--ro-bind", "/", "/", "--", "/usr/bin/true"],
                          capture_output=True, timeout=10).returncode == 0


needs_namespaces = pytest.mark.skipif(not _netns(), reason="bubblewrap namespaces unavailable on this host")


@pytest.fixture
def founder(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "plan.md").write_text("one\ntwo\nthree\n")
    folder = install_notes(data)
    ctx = PlannerContext(read_roots=(str(data),), capabilities=[], workspace=tmp_path / "ws")
    return {"data": data, "folder": folder, "ctx": ctx}


def test_an_installed_server_is_found_without_starting_it(founder, tmp_path):
    (founder["data"] / "tools" / "broken" / "bin").mkdir(parents=True)
    (founder["data"] / "tools" / "broken" / "bin" / "mcp-server-broken").write_text("not executable")
    deep = founder["data"] / "a" / "b" / "c" / "d" / "e" / "bin"
    deep.mkdir(parents=True)
    (deep / "mcp-server-deep").write_text("#!/bin/sh\n")
    (deep / "mcp-server-deep").chmod(0o755)
    found = mcp_tools.installed_servers([founder["data"]])
    assert list(found) == ["notes"]                                   # not executable, too deep: not servers
    assert found["notes"] == {"root": str(founder["folder"].resolve()),
                              "command": [str(founder["folder"] / "bin" / "mcp-server-notes")]}
    assert mcp_tools.installed_servers([tmp_path / "nowhere"]) == {}


@needs_namespaces
def test_a_servers_tools_are_listed_with_their_schemas_and_claims(founder):
    tools = {t["name"]: t for t in mcp_tools.server_tools(mcp_tools.installed_servers([founder["data"]])["notes"],
                                                          scratch_parent=founder["ctx"].workspace)}
    assert set(tools) == {"count_lines", "append_line"}
    assert tools["count_lines"]["input_schema"]["required"] == ["path"] and tools["count_lines"]["claims_read_only"]
    assert not tools["append_line"]["claims_read_only"]
    assert list(founder["ctx"].workspace.iterdir()) == []             # its scratch directory is discarded


@needs_namespaces
def test_words_naming_the_server_and_tool_become_one_read_only_mission(founder):
    words = f"Use the notes server to count the lines of {founder['data'] / 'plan.md'}"
    out = propose(words, founder["ctx"])
    assert out["status"] == "PROPOSED" and out["origin"] == "template:mcp-tool", out
    spec = out["spec"]
    validate_mission(spec)
    sensor = spec["success_checks"][0]["sensor"]
    assert sensor["capability"] == "mcp.call" and sensor["target"] == "mcp:notes"
    assert sensor["params"]["tool"] == "count_lines"
    assert sensor["params"]["arguments"] == {"path": str((founder["data"] / "plan.md").resolve())}
    assert sensor["params"]["readable"] == [str((founder["data"] / "plan.md").resolve())]
    assert spec["light_cone"]["max_consequence_class"] == "read_only" and spec["light_cone"]["budget_usd"] == 0.0
    assert spec["founder_expression"] == words
    summary = authority_summary(spec, [])
    assert summary["may_do_without_asking"] == ["observe: mcp.call"] and summary["must_ask_you_first"] == []


@needs_namespaces
@pytest.mark.parametrize("words, question", [
    ("Use the notes server to count the lines", "count_lines needs path"),
    ("Use the notes server to do something useful with {data}/plan.md", "Which of the notes server's tools?"),
    ("Use the notes server to count the lines of /etc/hostname", "GREG may only read under"),
    ("Use the notes server to append a line to {data}/plan.md", "append_line needs"),
])
def test_what_the_words_do_not_settle_becomes_a_question(founder, words, question):
    out = propose(words.format(data=founder["data"]), founder["ctx"])
    assert out["status"] == "NEEDS_INPUT" and question in out["questions"][0], out


def test_with_nothing_installed_the_founder_is_told_how_to_install_one(tmp_path):
    ctx = PlannerContext(read_roots=(str(tmp_path),), capabilities=[], workspace=tmp_path / "ws")
    out = propose("Which MCP tools can you use?", ctx)
    assert out["status"] == "NEEDS_INPUT" and "pip install mcp-server-" in out["questions"][0]


def test_words_about_some_other_server_are_not_taken_for_a_tool(founder):
    out = propose("Restart the web server tonight", founder["ctx"])
    assert out.get("origin") != "template:mcp-tool"


@needs_namespaces
def test_the_model_route_sees_the_installed_servers_and_their_tools(founder):
    from greg.planner import _prompt
    import json
    context = json.loads(_prompt("Use an MCP tool to summarize my plan", founder["ctx"]))
    tools = context["installed_mcp_servers"]["notes"]["tools"]
    assert {t["name"] for t in tools} == {"count_lines", "append_line"}
    assert "installed_mcp_servers" not in json.loads(_prompt("Summarize my plan", founder["ctx"]))


def test_the_founder_can_check_from_a_terminal_what_greg_found(founder, tmp_path):
    import json
    from greg.body import init_body
    home = tmp_path / "body"
    init_body(home, read_roots=[str(founder["data"])])
    out = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "mcp", "list"], capture_output=True,
                         text=True, cwd=Path(__file__).resolve().parents[2], timeout=60)
    assert out.returncode == 0, out.stderr[-500:]
    assert list(json.loads(out.stdout)) == ["notes"]
