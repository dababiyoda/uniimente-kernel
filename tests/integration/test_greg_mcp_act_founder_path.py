"""From the founder's words to a change they approved, over real HTTP: Mission Control, sign, approve, verified.

The founder asks the stand-in "notes" server, in words, to append a line to their plan. The console proposes one
``mcp.act`` mission and says before signing that GREG will ask first. After signing, the body stops at the approval,
and the decision on Mission Control shows exactly what approving lets the server do: run ``append_line``, write the
plan's folder and nothing else, no network, no credentials. The founder approves; the line lands; GREG reads the
file itself and closes the mission. A second, rejected request never writes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

import pytest

from greg.body import Body
from tests.integration.test_greg_mcp_founder_path import running  # noqa: F401 (fixture)
from tests.integration.test_greg_mission_control import http, token
from tests.unit.test_greg_mcp_planner import needs_namespaces


def _tick(home, until, limit=6):
    with Body(home) as body:
        body.boot()
        for _ in range(limit):
            out = body.tick()["missions"]
            states = {m["state"] for m in out}
            if until in states:
                break
        chain_ok, _ = body.ledger.verify_chain()
    return out, chain_ok


def _ask_and_sign(port, words):
    _, command = http(port, "/mc/command")
    url, review = http(port, "/ask", {"csrf": token(command), "text": words})
    assert "/proposal/" in url and "template:mcp-act" in review, review[-2000:]
    http(port, "/sign", {"csrf": token(review), "proposal": url.rsplit("/", 1)[1]})
    return review


@needs_namespaces
def test_the_founder_asks_for_a_change_approves_its_exact_scope_and_sees_it_verified(running):
    home, data, console, port = running
    plan = data / "plan.md"
    review = _ask_and_sign(port, f"Use the notes server to append “ship the wedge” to {plan}")
    assert "mcp.act" in review and "asks you before it runs" in review           # said before signing
    out, _ = _tick(home, "WAITING")
    assert out[0]["state"] == "WAITING" and plan.read_text() == "one\ntwo\nthree\n", out
    _, page = http(port, "/")
    decision = page.split("Decisions waiting for you", 1)[1].split("</table>", 1)[0]
    assert "Approving lets it:" in decision and "append_line" in decision
    assert f"write: <code>{data}</code> (nothing else)" in decision and "no network" in decision
    request_id = re.search(r"name='request_id' value='([^']+)'", decision).group(1)
    http(port, "/decide", {"csrf": token(page), "request_id": request_id, "answer": "approve"})
    out, chain_ok = _tick(home, "ACHIEVED")
    assert out[0]["state"] == "ACHIEVED" and chain_ok, out
    assert plan.read_text() == "one\ntwo\nthree\nship the wedge\n"


@needs_namespaces
def test_a_change_the_founder_rejects_never_writes(running):
    home, data, console, port = running
    plan = data / "plan.md"
    _ask_and_sign(port, f"Use the notes server to append \"never\" to {plan}")
    _tick(home, "WAITING")
    _, page = http(port, "/")
    decision = page.split("Decisions waiting for you", 1)[1].split("</table>", 1)[0]
    request_id = re.search(r"name='request_id' value='([^']+)'", decision).group(1)
    http(port, "/decide", {"csrf": token(page), "request_id": request_id, "answer": "reject"})
    out, _ = _tick(home, "ACHIEVED", limit=4)
    assert out[0]["state"] != "ACHIEVED" and "never" not in plan.read_text()


@needs_namespaces
@pytest.mark.skipif(not os.environ.get("GREG_TEST_MCP_SERVERS"), reason="set GREG_TEST_MCP_SERVERS (filesystem/)")
def test_words_reach_the_official_filesystem_server_and_its_write_is_checked_by_greg(tmp_path):
    """``@modelcontextprotocol/server-filesystem`` (MIT), discovered with its launch configuration, asked in words."""
    from greg.planner import PlannerContext, propose
    from tests.greg_fixtures import drop, make_body, signed
    servers = Path(os.environ["GREG_TEST_MCP_SERVERS"])
    config = servers / "filesystem" / "greg-mcp.json"
    data = tmp_path / "data"
    (data / "notes").mkdir(parents=True)
    saved = config.read_text() if config.exists() else None
    config.write_text(json.dumps({"args": [str(data / "notes")], "readable": [str(data / "notes")]}))
    try:
        home, key, body_id, _ = make_body(tmp_path, read_roots=[data, servers])
        today = data / "notes" / "today.md"
        out = propose(f"Use the filesystem server to write “the wedge first” to {today}",
                      PlannerContext(read_roots=(str(data), str(servers)), capabilities=[], workspace=tmp_path / "ws"))
        assert out["status"] == "PROPOSED" and out["spec"]["strategies"][0]["params"]["tool"] == "write_file", out
        drop(home, signed(key, body_id, "MISSION", out["spec"]))
        out, _ = _tick(home, "WAITING")
        with Body(home) as body:
            [ask] = [e.payload for e in body.journal.replay("decision.requested")]
        assert ask["authority_requested"]["may_write"] == [str(data / "notes")] and not today.exists()
        drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
        out, chain_ok = _tick(home, "ACHIEVED")
        assert out[0]["state"] == "ACHIEVED" and chain_ok and today.read_text() == "the wedge first", out
    finally:
        if saved is None:
            config.unlink(missing_ok=True)
        else:
            config.write_text(saved)
