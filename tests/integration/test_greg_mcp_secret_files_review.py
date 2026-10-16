"""Fourth review of PR #184 (SF-1 to SF-5): mcp.act's secret_files (#169 46719e4) keeps a credential out of every
record, out of every workspace a capability can read, and inside exactly what the founder signed.

* SF-1: a server that echoes its key file in its stderr or its error no longer writes the key into a receipt on
  the append-only ledger or into the journal.
* SF-2: a call killed mid-flight (SIGKILL, OOM, power loss) no longer leaves the key file in the mission workspace,
  where fs.read could return it; the body removes such leftovers when it opens.
* SF-3: an earlier action's output can no longer choose which credential (or host, or writable path) a server gets,
  and the approval shows the reach the scope digest covers.
* SF-4: a malformed secret_files is refused before anyone is asked, instead of crashing every tick.
* SF-5: ``greg secret set --from-file`` reads at most the 64 KiB ceiling plus one byte.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import textwrap
import time

import pytest

from foundry.systems import relay_door
from greg import mcp_tools
from greg.body import Body, Layout
from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
from greg.pipeline import BindingError, resolve
from tests.greg_fixtures import drop, make_body, signed
from tests.integration.test_greg_mcp_act_mission import act_mission, approval, tick_until
from tests.unit.test_greg_mcp_act import install_scribe
from tests.unit.test_greg_mcp_planner import needs_namespaces

KEY = '{"type": "service_account", "private_key": "PEM-FIXTURE-abc123def456"}\nsecond-line: TOKEN-LINE-987654321\n'
LEAKS = ("PEM-FIXTURE-abc123def456", "TOKEN-LINE-987654321")

LOUD = textwrap.dedent(r'''
    import os, sys, time
    from mcp.server.mcpserver import MCPServer
    server = MCPServer("scribe")

    @server.tool()
    def bad_key(name: str) -> str:
        """Fail to parse the key, quoting it on stderr like a library would, and exit."""
        data = open(os.environ[name]).read()
        sys.stderr.write("could not parse credentials file: " + data + "\n"); sys.stderr.flush()
        os._exit(1)

    @server.tool()
    def raise_key(name: str) -> str:
        """Fail like a parser that quotes its input in the error."""
        data = open(os.environ[name]).read()
        raise ValueError("Unexpected token in " + repr(data[:60]) + " at line 2: " + data.splitlines()[1])

    @server.tool()
    def slow(n: int) -> str:
        """Sleep, so the process running the call can be killed mid-call."""
        time.sleep(n)
        return "done"

    if __name__ == "__main__":
        server.run("stdio")
''')


def approvals(body) -> list:
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload.get("kind") == "APPROVAL"]


def install_loud(root: Path) -> dict:
    folder = root / "tools" / "scribe"
    (folder / "bin").mkdir(parents=True)
    (folder / "server.py").write_text(LOUD)
    entry = folder / "bin" / "mcp-server-scribe"
    entry.write_text(f"#!/bin/sh\nexec {sys.executable} {folder / 'server.py'} \"$@\"\n")
    entry.chmod(0o755)
    return {"server": "scribe", "root": str(folder), "command": [str(entry)]}


@needs_namespaces
@pytest.mark.parametrize("tool", ["bad_key", "raise_key"])
def test_a_server_echoing_its_key_file_never_writes_the_key_into_a_record(tmp_path, tool):
    home, key, body_id, data = make_body(tmp_path)
    (data / "notes").mkdir()
    SecretBroker(home / "secrets.json").put("mcp:svc-key", KEY)
    base = install_loud(data)
    note = data / "notes" / "today.md"
    spec = act_mission(f"m:scribe-{tool.replace('_', '-')}", base, {
        "tool": tool, "writable": [str(data / "notes")], "secret_files": {"SVC_KEY": "mcp:svc-key"},
        "arguments": {"name": "SVC_KEY"}}, check_path=note, text="x")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        tick_until(body, {"WAITING"})
        ask = approval(body)
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
    with Body(home) as body:
        body.boot()
        for _ in range(3):
            body.tick()
        actions = [e.payload for e in body.journal.replay("mission.action") if e.payload["action_id"] == "act"]
        assert any(a["status"] in ("FAILED", "REFUSED", "UNCERTAIN") for a in actions), actions
        receipts = [json.dumps(r.payload) for r in body.ledger.by_type("receipt")]
        journal = [json.dumps(e.payload) for e in body.journal.replay("mission.action")]
    ledger_bytes = Layout(home).ledger.read_text()
    for leak in LEAKS:
        assert not any(leak in r for r in receipts) and not any(leak in j for j in journal), leak
        assert leak not in ledger_bytes, leak
    if tool == "bad_key":            # its stderr is still reported, with the key scrubbed out of it
        assert any("[credential]" in j for j in journal), journal


def test_a_failed_call_scrubs_the_key_from_its_error_and_stderr_on_any_host(tmp_path, monkeypatch):
    # SF-1 at the call itself, so it also runs where bubblewrap cannot (CI job 6): the server quotes its key file
    # in its stderr and in its error, and neither reaches the message that becomes a receipt.
    from foundry.systems import mcp_gateway
    from greg import worker_isolation
    from greg.capabilities import CapabilityError
    monkeypatch.setattr(worker_isolation, "_backend", lambda **_: "bubblewrap")   # confinement is tested above

    async def echoing(provider, tool, arguments):
        data = Path(provider["env"]["SVC_KEY"]).read_text()
        (Path(provider["scratch"]) / "server-stderr.log").write_text("could not parse credentials file: " + data)
        raise mcp_gateway.GatewayError("server exited: Unexpected token in " + data)

    monkeypatch.setattr(mcp_gateway, "_call", echoing)
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=SecretBroker(tmp_path / "s.json"),
                            manifest=BUILTINS["mcp.act"][0])
    c = {"server": "scribe", "command": ["mcp-server-scribe"], "root": str(tmp_path), "readable": [],
         "tool": "bad_key", "arguments": {"name": "SVC_KEY"}}
    with pytest.raises(CapabilityError) as raised:
        mcp_tools._invoke(c, ctx, files={"SVC_KEY": KEY})
    message = str(raised.value)
    assert "| stderr: could not parse credentials file:" in message and "[credential]" in message, message
    for leak in LEAKS:
        assert leak not in message, message
    assert not list((tmp_path / "ws").iterdir()), "the call's scratch and key directories are removed"


def test_scrubbing_covers_the_value_its_lines_and_its_tokens():
    text = f"boom: {KEY} | {' '.join(KEY.split())} | line {KEY.splitlines()[1]} | token {LEAKS[0]}"
    scrubbed = mcp_tools._scrub(text, [KEY])
    assert not any(leak in scrubbed for leak in LEAKS) and "boom:" in scrubbed


@needs_namespaces
def test_a_killed_calls_key_file_is_gone_before_anything_can_read_the_workspace(tmp_path):
    data = tmp_path / "data"
    (data / "notes").mkdir(parents=True)
    base = install_loud(data)
    script = tmp_path / "child.py"
    script.write_text(textwrap.dedent(f'''
        import json, sys
        from pathlib import Path
        sys.path.insert(0, {str(Path(__file__).resolve().parents[2])!r})
        from foundry.systems import relay_door
        from greg import mcp_tools
        from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
        relay_door._PRIVATE_ROOTS = set()
        secrets = SecretBroker(Path({str(tmp_path / "secrets.json")!r}))
        secrets.put("mcp:svc-key", {KEY!r})
        ctx = InvocationContext(workspace=Path({str(tmp_path / "ws" / "m_scribe")!r}), read_roots=(Path({str(data)!r}),),
                                secrets=secrets, manifest=BUILTINS["mcp.act"][0], target="mcp:scribe",
                                mission_id="m:scribe")
        print("calling", flush=True)
        mcp_tools.act({{**{base!r}, "tool": "slow", "writable": [{str(data / "notes")!r}],
                       "secret_files": {{"SVC_KEY": "mcp:svc-key"}}, "arguments": {{"n": 30}}}}, ctx)
    '''))
    child = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, text=True)
    assert child.stdout.readline().strip() == "calling"
    workspace = tmp_path / "ws"
    deadline = time.monotonic() + 30
    while not list(workspace.glob("m_scribe/cred-*/*")) and time.monotonic() < deadline:
        time.sleep(0.1)
    os.kill(child.pid, signal.SIGKILL)
    child.wait()
    held = [f for f in workspace.rglob("*") if f.is_file() and LEAKS[0].encode() in f.read_bytes()]
    assert held, "the call was killed after the key file was written (precondition)"
    removed = mcp_tools.sweep_leftovers(workspace)
    assert removed and not [f for f in workspace.rglob("*") if f.is_file() and LEAKS[0].encode() in f.read_bytes()]


def test_the_body_removes_call_leftovers_when_it_opens_and_keeps_everything_else(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    workspace = Layout(home).workspace / "m_scribe"
    (workspace / "cred-scribe-ab12cd34").mkdir(parents=True)
    (workspace / "cred-scribe-ab12cd34" / "svc_key").write_text(KEY)
    (workspace / "mcp-scribe-zz99yy88" / "home").mkdir(parents=True)
    (workspace / "cred-notes").mkdir()                       # a worker's own folder: not a call's leftover
    (workspace / "report.md").write_text("kept\n")
    with Body(home) as body:
        events = [e.payload for e in body.journal.replay("mcp.leftovers_removed")]
    assert sorted(events[0]["directories"]) == ["m_scribe/cred-scribe-ab12cd34", "m_scribe/mcp-scribe-zz99yy88"]
    assert not (workspace / "cred-scribe-ab12cd34").exists() and not (workspace / "mcp-scribe-zz99yy88").exists()
    assert (workspace / "cred-notes").is_dir() and (workspace / "report.md").read_text() == "kept\n"
    with Body(home) as body:                                  # nothing left: nothing recorded
        assert len(body.journal.replay("mcp.leftovers_removed")) == 1


@pytest.mark.parametrize("field", ["secret_files", "secrets", "bearer", "hosts", "writable"])
def test_an_earlier_actions_output_cannot_choose_a_servers_reach(field):
    ref = {"$from_action": {"action_id": "probe", "field": "text", "type": "string"}}
    value = ref if field in ("bearer",) else ([ref] if field in ("hosts", "writable") else {"K": ref})
    with pytest.raises(BindingError, match="authority or execution scope"):
        resolve({field: value}, journal=None, mission_id="m")


@needs_namespaces
def test_a_bound_credential_reference_blocks_the_mission_and_the_server_never_gets_the_key(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    (data / "notes").mkdir()
    (data / "handle.txt").write_text("mcp:admin-key")       # stands in for an earlier action's untrusted output
    SecretBroker(home / "secrets.json").put("mcp:admin-key", "ADMIN-KEY-FIXTURE")
    base = install_scribe(data)
    note = data / "notes" / "today.md"
    spec = act_mission("m:scribe-bound", base, {
        "tool": "write_note", "writable": [str(data / "notes")],
        "secret_files": {"SCRIBE_KEY": {"$from_action": {"action_id": "probe", "field": "text", "type": "string"}}},
        "arguments": {"path": str(note), "text": "x"}}, check_path=note, text="x")
    spec["strategies"].insert(0, {"action_id": "probe", "capability": "fs.read",
                                  "params": {"path": str(data / "handle.txt")}, "target": "fs:handle.txt",
                                  "advances": ["done"], "rationale": "read a value"})
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        for _ in range(6):
            body.tick()
        assert not approvals(body), "never asked to approve a scope it cannot run as signed"
        assert body.engine.book.missions["m:scribe-bound"].blocker, "the mission stops for the founder instead"
        assert not [e for e in body.journal.replay("mission.action") if e.payload["action_id"] == "act"
                    and e.payload["status"] in ("DONE", "FAILED", "UNCERTAIN")], "mcp.act never dispatched"
        assert not [r for r in body.ledger.by_type("receipt")
                    if (r.payload["result"].get("output") or {}).get("tool") == "write_note"]


@pytest.mark.parametrize("malformed", [["mcp:scribe-token"], "mcp:scribe-token", {"SCRIBE": 7}])
def test_a_malformed_secret_files_is_refused_before_anyone_is_asked(tmp_path, malformed):
    # No namespace needed: the scope is refused before anything is dispatched, so this runs on every CI host.
    home, key, body_id, data = make_body(tmp_path)
    (data / "notes").mkdir()
    base = install_scribe(data)
    note = data / "notes" / "today.md"
    spec = act_mission("m:scribe-bad", base, {
        "tool": "write_note", "writable": [str(data / "notes")], "secret_files": malformed,
        "arguments": {"path": str(note), "text": "x"}}, check_path=note, text="x")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        for _ in range(4):
            body.tick()                                       # never raises
        refused = [e.payload for e in body.journal.replay("mission.action")
                   if e.payload["action_id"] == "act" and e.payload["status"] == "REFUSED"]
        assert refused and "secret_files must map" in " ".join(refused[0]["reasons"])
        assert not approvals(body), "a malformed scope is refused, never asked about"


def test_the_approval_shows_what_the_bound_scope_reaches_and_a_malformed_one_as_malformed():
    from greg.missions import exact_reach
    reach = exact_reach("mcp.act", {"server": "s", "tool": "t", "secret_files": {"K": "mcp:k"}, "hosts": ["a.example"]})
    assert reach["credentials"] == ["mcp:k (as a file)"] and reach["may_reach"] == ["a.example:443 through the relay"]
    assert "secret_files must map" in exact_reach("mcp.act", {"server": "s", "tool": "t", "secret_files": ["x"]})["malformed"]


def test_a_credential_file_is_read_at_most_to_the_ceiling(tmp_path, monkeypatch):
    from greg import cli
    from greg.body import BodyError
    monkeypatch.setattr(Path, "read_bytes", lambda self: (_ for _ in ()).throw(AssertionError("whole file read")))
    big = tmp_path / "big.bin"
    with big.open("wb") as fh:
        fh.truncate(8 * 1024 * 1024)                          # sparse: 8 MiB of zeros
    with pytest.raises(BodyError, match="64 KiB"):
        cli._secret_file(str(big))
    small = tmp_path / "key.json"
    small.write_text(KEY)
    assert cli._secret_file(str(small)) == KEY
