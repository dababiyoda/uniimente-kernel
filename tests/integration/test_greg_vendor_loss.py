"""Losing a model vendor, end to end: the real vendor SDKs over real HTTP, through the body's one Genesis path.

The founder's signed mission needs a function GREG does not have. The routes are the real ``anthropic`` and
``openai`` SDK clients, each pointed at a local endpoint: Anthropic's is down (nothing listens; the SDK retries and
fails as it would against an outage), OpenAI's answers. Genesis builds through the vendor that is up, the ORIGINAL
mission closes, the failed vendor is recorded as an outage (never a refusal), and a restarted body replays that
health. When the vendor that answered is lost too, the next build has no route: the body says so and keeps the
mission open, rather than closing it on anything less.
"""
from __future__ import annotations

import http.server
import json
import socket
import threading

import pytest

from greg import builders, models
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_genesis_builder import GOOD, _mission

anthropic = pytest.importorskip("anthropic")
openai = pytest.importorskip("openai")


def _closed_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()                                   # nothing listens here: the vendor is down
    return port


def _openai_endpoint(reply_source: str):
    calls = []

    class Responses(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = json.dumps({"id": f"resp_{len(calls)}", "object": "response", "created_at": 0, "model": "gpt-x",
                               "status": "completed",
                               "output": [{"type": "message", "id": "msg", "role": "assistant", "status": "completed",
                                           "content": [{"type": "output_text", "annotations": [],
                                                        "text": "```python\n" + reply_source + "```"}]}],
                               "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Responses)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, calls


def _routes(anthropic_port: int, openai_port: int):
    return [models.AnthropicRoute("sk-ant-fixture", client=anthropic.Anthropic(
                api_key="sk-ant-fixture", base_url=f"http://127.0.0.1:{anthropic_port}", max_retries=1, timeout=5)),
            models.OpenAIRoute("sk-openai-fixture", price=(1.0, 4.0), client=openai.OpenAI(
                api_key="sk-openai-fixture", base_url=f"http://127.0.0.1:{openai_port}/v1", max_retries=1, timeout=5))]


def test_genesis_builds_through_the_vendor_that_is_up_and_the_outage_is_remembered(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    down = _closed_port()
    server, calls = _openai_endpoint(GOOD)
    port = server.server_address[1]
    clock = Clock()
    try:
        body = Body(home, clock=clock, builder=lambda s, c: builders.ModelBuilder(
            models.ModelRouter(_routes(down, port)))).open()
        body.boot()
        states = []
        for _ in range(4):
            clock.advance(30)
            states.append(body.tick()["missions"][0]["state"])
        routes = [e.payload for e in body.journal.replay("model.route")]
        built = body.journal.replay("genesis.built")[0].payload
        body.close()
        assert "ACHIEVED" in states, states                              # the ORIGINAL mission closed
        assert built["builder"] == "model:openai:gpt-5.5" and calls        # built through the vendor that was up
        assert [(r["provider"], r["outcome"], r.get("class")) for r in routes][:2] == [
            ("anthropic", "failed", models.TRANSIENT), ("openai", "ok", None)]   # an outage, never a refusal

        with Body(home, clock=Clock(), builder=lambda s, c: builders.ModelBuilder(
                models.ModelRouter(_routes(down, port)))) as reopened:
            health = reopened.builder.router.health
        assert health["anthropic:claude-opus-5"]["consecutive_failures"] == 1   # the outage survives a restart
        assert health["openai:gpt-5.5"]["consecutive_failures"] == 0
    finally:
        server.shutdown()


def test_with_every_vendor_lost_the_mission_stays_open_and_the_body_says_why(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    clock = Clock()
    body = Body(home, clock=clock, builder=lambda s, c: builders.ModelBuilder(
        models.ModelRouter(_routes(_closed_port(), _closed_port())))).open()
    body.boot()
    states = []
    for _ in range(4):
        clock.advance(30)
        states.append(body.tick()["missions"][0]["state"])
    routes = [e.payload for e in body.journal.replay("model.route")]
    achieved = body.journal.replay("mission.achieved")
    built = body.journal.replay("genesis.built")
    body.close()
    assert not achieved and not built and "ACHIEVED" not in states, states
    assert {(r["provider"], r["outcome"], r.get("class")) for r in routes} == {
        ("anthropic", "failed", models.TRANSIENT), ("openai", "failed", models.TRANSIENT)}
