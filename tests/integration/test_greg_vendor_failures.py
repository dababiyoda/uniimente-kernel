"""A model vendor that fails in the ways real vendors do, over real HTTP, through the real Anthropic SDK.

Three ways, each against a local endpoint the SDK is pointed at:
  - slow: the vendor accepts the request and does not answer before the SDK's timeout;
  - truncated: the vendor sends its headers and part of the body, then drops the connection;
  - rejected: the vendor refuses the key (HTTP 401, ``authentication_error``).

Each time the founder's mission still closes through the vendor that answers (OpenAI's SDK, also local), and the
failure is recorded with its true class: the first two are outages, the third is the founder's credential.
"""
from __future__ import annotations

import http.server
import json
import threading
import time

import pytest

from greg import builders, models
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.integration.test_greg_vendor_loss import _openai_endpoint
from tests.unit.test_greg_genesis_builder import GOOD, _mission

anthropic = pytest.importorskip("anthropic")
openai = pytest.importorskip("openai")


def misbehaving(mode: str):
    """A local stand-in for Anthropic's Messages API that fails as ``mode`` says; it records every request."""
    seen = []

    class Messages(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            seen.append(self.headers.get("x-api-key"))
            if mode == "slow":
                time.sleep(3)                                    # longer than the SDK's timeout
                return
            if mode == "truncated":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", "500")
                self.end_headers()
                self.wfile.write(b'{"id": "msg_1", "type": "message", "content": [{"type": "te')
                self.wfile.flush()
                self.connection.shutdown(2)                      # the rest never arrives
                return
            body = json.dumps({"type": "error", "error": {"type": "authentication_error",
                                                          "message": "invalid x-api-key"}}).encode()
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Messages)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, seen


def routes(anthropic_port: int, openai_port: int):
    return [models.AnthropicRoute("sk-ant-fixture", client=anthropic.Anthropic(
                api_key="sk-ant-fixture", base_url=f"http://127.0.0.1:{anthropic_port}", max_retries=0, timeout=1)),
            models.OpenAIRoute("sk-openai-fixture", price=(1.0, 4.0), client=openai.OpenAI(
                api_key="sk-openai-fixture", base_url=f"http://127.0.0.1:{openai_port}/v1", max_retries=0, timeout=5))]


@pytest.mark.parametrize("mode, kind", [("slow", models.TRANSIENT), ("truncated", models.TRANSIENT),
                                        ("rejected", models.AUTH)])
def test_the_mission_closes_through_the_vendor_that_answers_and_the_failure_keeps_its_class(tmp_path, mode, kind):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    bad, seen = misbehaving(mode)
    good, calls = _openai_endpoint(GOOD)
    clock = Clock()
    try:
        with Body(home, clock=clock, builder=lambda s, c: builders.ModelBuilder(models.ModelRouter(
                routes(bad.server_address[1], good.server_address[1])))) as body:
            body.boot()
            states = []
            for _ in range(4):
                clock.advance(30)
                states.append(body.tick()["missions"][0]["state"])
            tried = [(e.payload["provider"], e.payload["outcome"], e.payload.get("class"))
                     for e in body.journal.replay("model.route")]
            built = body.journal.replay("genesis.built")[0].payload
        assert "ACHIEVED" in states and built["builder"] == "model:openai:gpt-5.5" and calls, states
        assert tried[:2] == [("anthropic", "failed", kind), ("openai", "ok", None)], tried
        assert seen == ["sk-ant-fixture"]                        # one request (the SDK's own retries are off here)
    finally:
        bad.shutdown()
        good.shutdown()


def test_a_refused_key_is_not_tried_again_until_the_founder_stores_a_new_one(tmp_path):
    from greg import mission_control
    from greg.body import status
    from greg.capabilities import SecretBroker
    from greg.console import Console
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    bad, seen = misbehaving("rejected")
    good, _ = _openai_endpoint(GOOD)
    a, o = bad.server_address[1], good.server_address[1]

    def builder(api_key="sk-ant-fixture"):
        def make(secrets, config):
            first = models.AnthropicRoute(api_key, client=anthropic.Anthropic(
                api_key=api_key, base_url=f"http://127.0.0.1:{a}", max_retries=0, timeout=1))
            return builders.ModelBuilder(models.ModelRouter([first, routes(a, o)[1]]))
        return make
    clock = Clock()
    try:
        with Body(home, clock=clock, builder=builder()) as body:
            body.boot()
            for _ in range(4):
                clock.advance(30)
                state = body.tick()["missions"][0]["state"]
            assert state == "ACHIEVED" and seen == ["sk-ant-fixture"]
            clock.advance(3600)                                      # far past the router's cooldown
            assert body.builder.router.complete("system", "user")["route"] == "openai:gpt-5.5"
            assert seen == ["sk-ant-fixture"]                         # the refused key was not sent again
        [refused] = status(home)["refused_model_keys"]
        assert refused["route"] == "anthropic:claude-opus-5" and refused["handle"] == "anthropic_api_key"
        assert refused["replaced"] is False
        page = mission_control._authority(Console(home, key=key), mission_control.projection(Console(home, key=key)), {})
        assert "Model keys a vendor refused" in page and "greg secret set anthropic_api_key" in page
        assert not [p for p in home.rglob("*") if p.is_file() and b"sk-ant-fixture" in p.read_bytes()]   # fingerprint only

        with Body(home, clock=Clock(), builder=builder()) as body:   # restarted: benched from the record
            body.builder.router.complete("system", "user")
        assert seen == ["sk-ant-fixture"]

        SecretBroker(home / "secrets.json").put("anthropic_api_key", "sk-ant-new")
        assert status(home)["refused_model_keys"][0]["replaced"] is True
        with Body(home, clock=Clock(), builder=builder("sk-ant-new")) as body:
            body.builder.router.complete("system", "user")
        assert seen == ["sk-ant-fixture", "sk-ant-new"]               # a new key is tried, once
    finally:
        bad.shutdown()
        good.shutdown()
