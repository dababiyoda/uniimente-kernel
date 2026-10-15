"""From Mission Control to a tool the founder installed, over real HTTP, and back to the answer.

The founder installs an MCP server (the stand-in "notes" server) under GREG's read roots. Mission Control lists it;
on request it lists the server's tools, run confined. The founder asks in plain words; the console proposes one
read-only ``mcp.call`` mission and shows what signing allows; the founder signs; the body runs it; and Mission
Control shows the tool's answer, marked as untrusted data, with its receipt.
"""
from __future__ import annotations

import re
import threading

import pytest

from greg.body import Body
from greg.console import Console, serve
from tests.greg_fixtures import make_body
from tests.integration.test_greg_mission_control import SESSIONS, http, owner_session, token
from tests.unit.test_greg_mcp_planner import install_notes, needs_namespaces


@pytest.fixture
def running(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    (data / "plan.md").write_text("one\ntwo\nthree\n")
    install_notes(data)
    console = Console(home, key=key)
    server = serve(console, port=0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    owner_session(console, port)
    yield home, data, console, port
    SESSIONS.pop(port, None)
    server.shutdown()
    server.server_close()


@needs_namespaces
def test_the_founder_asks_an_installed_tool_in_words_and_sees_its_answer(running):
    home, data, console, port = running
    _, command = http(port, "/mc/command")
    assert "Tool servers you installed (MCP)" in command and "<code>notes</code>" in command
    _, listed = http(port, "/mc/command?q=tools:notes")
    assert "notes: 2 tools" in listed and "count_lines" in listed and "append_line" in listed
    assert "claims read-only (not trusted)" in listed and "no read-only claim" in listed

    words = f"Use the notes server to count the lines of {data / 'plan.md'}"
    url, review = http(port, "/ask", {"csrf": token(command), "text": words})
    assert "/proposal/" in url and "template:mcp-tool" in review and "mcp.call" in review
    assert "read-only by construction" in review                         # what signing allows, before signing
    http(port, "/sign", {"csrf": token(review), "proposal": url.rsplit("/", 1)[1]})

    with Body(home) as body:
        body.boot()
        for _ in range(4):
            out = body.tick()["missions"][0]
            if out["state"] == "ACHIEVED":
                break
        chain_ok, _ = body.ledger.verify_chain()
    assert out["state"] == "ACHIEVED" and chain_ok, out

    _, after = http(port, "/mc/command")
    answers = after.split("Latest answers", 1)[1].split("</table>", 1)[0]
    assert "count_lines" in answers and "3 lines" in answers and "untrusted" in after
    assert re.search(r"sha256:[0-9a-f]{16}", answers)                    # the receipt it came from
