"""npm-installed MCP servers, the founder's launch configuration, and a server's own structured answers.

``npm install --prefix <folder> @modelcontextprotocol/server-<name>`` puts the entry point at
``<folder>/node_modules/.bin/mcp-server-<name>``, a symlink into the package. GREG finds it there as it finds a
virtualenv's ``bin``. Some servers need launch arguments (the filesystem server takes the directories it may serve);
the founder writes them in ``greg-mcp.json`` beside the server, and every path is still checked when a mission runs.

The stand-in here is a Python script laid out the way npm lays out a package, so the test needs no Node.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from foundry.systems import relay_door
from greg import mcp_tools
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
from greg.planner import PlannerContext, propose
from tests.unit.test_greg_mcp_planner import needs_namespaces

STUB = r'''#!{python}
import sys
from typing import TypedDict
from mcp.server.mcpserver import MCPServer

server = MCPServer("stub")


class Info(TypedDict):
    path: str
    lines: int
    first: str


@server.tool()
def launch_args() -> str:
    """The arguments the server was started with."""
    return " ".join(sys.argv[1:])


@server.tool()
def file_info(path: str) -> Info:
    """Facts about one file (a declared output schema: the answer arrives as structured content)."""
    with open(path) as fh:
        text = fh.read()
    return {"path": path, "lines": text.count("\n"), "first": text.splitlines()[0] if text else ""}


if __name__ == "__main__":
    server.run("stdio")
'''


def install_npm_style(folder: Path, *, config: dict | str | None = None) -> Path:
    package = folder / "node_modules" / "@example" / "server-stub"
    package.mkdir(parents=True)
    entry = package / "index.py"
    entry.write_text(STUB.replace("{python}", sys.executable))
    entry.chmod(0o755)
    bins = folder / "node_modules" / ".bin"
    bins.mkdir()
    (bins / "mcp-server-stub").symlink_to("../@example/server-stub/index.py")
    if config is not None:
        (folder / "greg-mcp.json").write_text(config if isinstance(config, str) else json.dumps(config))
    return folder


@pytest.fixture
def founder(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "notes").mkdir(parents=True)
    (data / "notes" / "plan.md").write_text("ship the wedge\nthen the rail\n")
    folder = install_npm_style(data / "tools" / "stub", config={"args": [str(data / "notes")],
                                                                 "readable": [str(data / "notes")]})
    monkeypatch.setattr(relay_door, "_PRIVATE_ROOTS", set())
    return {"data": data, "folder": folder}


def test_an_npm_installed_server_and_its_launch_configuration_are_found(founder):
    found = mcp_tools.installed_servers([founder["data"]])
    assert list(found) == ["stub"]
    stub = found["stub"]
    assert stub["root"] == str(founder["folder"].resolve())
    assert stub["command"] == [str(founder["folder"] / "node_modules" / ".bin" / "mcp-server-stub")]
    assert stub["args"] == [str(founder["data"] / "notes")] and stub["readable"] == [str(founder["data"] / "notes")]


@pytest.mark.parametrize("config, error", [("{not json", "not valid JSON"),
                                           ({"args": "one string"}, "must be lists of strings")])
def test_a_broken_launch_configuration_is_reported_not_guessed(tmp_path, config, error):
    install_npm_style(tmp_path / "tools" / "stub", config=config)
    stub = mcp_tools.installed_servers([tmp_path])["stub"]
    assert error in stub["config_error"] and "args" not in stub


@needs_namespaces
def test_the_launch_arguments_reach_the_server_and_its_own_structure_is_kept(founder):
    stub = mcp_tools.installed_servers([founder["data"]])["stub"]
    ctx = InvocationContext(workspace=founder["data"].parent / "ws", read_roots=(founder["data"],),
                            secrets=SecretBroker(founder["data"].parent / "s.json"), manifest=BUILTINS["mcp.call"][0],
                            target="mcp:stub", mission_id="m:stub")
    base = {"server": "stub", "root": stub["root"], "command": [*stub["command"], *stub["args"]],
            "readable": stub["readable"]}
    assert mcp_tools.call({**base, "tool": "launch_args"}, ctx)["result"] == str(founder["data"] / "notes")
    info = mcp_tools.call({**base, "tool": "file_info",
                           "arguments": {"path": str(founder["data"] / "notes" / "plan.md")}}, ctx)
    assert info["result"] == {"path": str(founder["data"] / "notes" / "plan.md"), "lines": 2,
                              "first": "ship the wedge"}                  # the server's own structure, not None
    assert json.loads(info["text"])["lines"] == 2


@needs_namespaces
def test_words_reach_an_npm_server_with_its_launch_configuration(founder, tmp_path):
    ctx = PlannerContext(read_roots=(str(founder["data"]),), capabilities=[], workspace=tmp_path / "ws")
    out = propose(f"Use the stub server for the file info of {founder['data'] / 'notes' / 'plan.md'}", ctx)
    assert out["status"] == "PROPOSED", out
    params = out["spec"]["success_checks"][0]["sensor"]["params"]
    assert params["tool"] == "file_info" and params["command"][-1] == str(founder["data"] / "notes")
    assert str(founder["data"] / "notes") in params["readable"]


def test_a_launch_configuration_cannot_widen_what_a_mission_may_read(founder, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(founder["data"],),
                            secrets=SecretBroker(tmp_path / "s.json"), manifest=BUILTINS["mcp.call"][0],
                            target="mcp:stub", mission_id="m:stub")
    stub = mcp_tools.installed_servers([founder["data"]])["stub"]
    with pytest.raises(CapabilityError, match="outside permitted roots"):
        mcp_tools.call({"server": "stub", "root": stub["root"], "command": stub["command"], "tool": "launch_args",
                        "readable": [str(outside)]}, ctx)
