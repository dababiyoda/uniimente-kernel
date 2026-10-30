"""Local open-weight cognition uses the existing router and never acquires authority."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
from threading import Thread

import pytest

from greg import models, planner
from greg import builders
from greg.body import Body, init_body
from greg.console import Console
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_genesis_builder import GOOD as BUILT_SOURCE, _mission
from tests.unit.test_greg_interface import GOOD, inventory


class LocalOllama(BaseHTTPRequestHandler):
    calls = []
    mode = "ok"

    def log_message(self, *args):
        pass

    def _send(self, status, payload):
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.calls.append(("GET", self.path))
        self._send(200, {"models": [{"name": name, "size": 1000, "digest": digest * 64,
                                      "details": {"format": "gguf"}}
                                     for name, digest in (("test:small", "a"), ("test:better", "b"))]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append(("POST", self.path, body))
        if self.mode == "policy":
            self._send(400, {"error": "Blocked by content policy"})
        elif self.mode == "down":
            self._send(503, {"error": "server unavailable"})
        else:
            content = ("```python\n" + BUILT_SOURCE + "\n```") if self.mode == "code" else json.dumps(GOOD)
            self._send(200, {"model": body["model"], "message": {"role": "assistant",
                                                       "content": content}, "done": True})


@pytest.fixture
def server():
    LocalOllama.calls = []
    LocalOllama.mode = "ok"
    http = ThreadingHTTPServer(("127.0.0.1", 0), LocalOllama)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield http.server_port
    http.shutdown()
    http.server_close()
    thread.join()


def test_local_model_proposes_through_one_router_without_a_key_or_authority(server):
    route = models.OllamaRoute("test:small", port=server)
    router = models.ModelRouter([route])
    context = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={})
    proposal = planner.model_route("Tell me if my repository is dirty", context, router)
    assert proposal["status"] == "PROPOSED", proposal
    assert proposal["spec"]["provenance"]["model"] == "ollama:test:small"
    assert proposal["spec"]["provenance"]["served_model"] == "test:small"
    assert proposal["spec"]["provenance"]["model_digest"] == "a" * 64
    assert proposal["spec"]["light_cone"]["budget_usd"] == 0
    assert LocalOllama.calls[0] == ("GET", "/api/tags")
    request = LocalOllama.calls[1]
    assert request[:2] == ("POST", "/api/chat")
    assert request[2]["stream"] is False and request[2]["options"]["num_predict"] <= 8192
    assert router.last["cost_usd"] == 0


def test_local_model_refusal_is_terminal_and_outage_can_fail_over(server):
    class Witness:
        name, provider = "witness", "witness"
        calls = 0

        def complete(self, *args, **kwargs):
            self.calls += 1
            return {"text": "available", "served_model": "witness", "cost_usd": 0}

    witness = Witness()
    router = models.ModelRouter([models.OllamaRoute("test:small", port=server), witness])
    LocalOllama.mode = "policy"
    with pytest.raises(models.Refusal):
        router.complete("s", "u")
    assert witness.calls == 0
    LocalOllama.mode = "down"
    assert router.complete("s", "u")["route"] == "witness"
    assert witness.calls == 1


def test_cloud_and_missing_models_are_not_labeled_local(server):
    with pytest.raises(ValueError, match="cloud"):
        models.OllamaRoute("test:cloud", port=server)
    with pytest.raises(models.RouteError, match="not installed locally"):
        models.OllamaRoute("missing:small", port=server).complete("s", "u", budget_usd=0)
    assert all(call[0] == "GET" for call in LocalOllama.calls)


def _permit_local_models(tmp_path, monkeypatch):
    """Apache-2.0 weights for the models these tests select. Selection now refuses a model with no permitting license."""
    from greg import licensing
    apache = (Path(__file__).resolve().parents[1] / "fixtures" / "licenses" / "Apache-2.0.txt").read_text().encode()
    root = tmp_path / "ollama-models"
    (root / "blobs").mkdir(parents=True)
    weights = b"GGUF weights"
    digests = {}
    for data in (weights, apache):
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        (root / "blobs" / digest.replace(":", "-")).write_bytes(data)
        digests[data] = digest
    layers = [
        {"mediaType": "application/vnd.ollama.image.model", "digest": digests[weights], "size": len(weights)},
        {"mediaType": licensing.OLLAMA_LICENSE, "digest": digests[apache], "size": len(apache)},
    ]
    for name in ("registry.ollama.ai/library/test/small", "registry.ollama.ai/library/test/better"):
        path = root / "manifests" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schemaVersion": 2, "layers": layers}))
    monkeypatch.setenv("OLLAMA_MODELS", str(root))
    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))


def test_local_route_is_opt_in_and_requires_an_explicit_model(tmp_path, monkeypatch):
    assert "ollama" not in [r.provider for r in models.available_routes()[0]]
    routes, missing = models.available_routes(config={"order": ["ollama"]})
    assert not routes and "ollama" in missing
    _permit_local_models(tmp_path, monkeypatch)
    routes, missing = models.available_routes(config={"order": ["ollama"], "ollama_model": "test:small"})
    assert not missing and routes[0].provider == "ollama"


def test_first_body_can_opt_in_without_a_key_and_refuses_cloud_before_creation(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="cloud"):
        init_body(tmp_path / "refused", read_roots=[], local_model="test:cloud")
    assert not (tmp_path / "refused").exists()
    home = tmp_path / "local"
    config = init_body(home, read_roots=[], local_model="test:small")
    assert config["models"] == {"order": ["ollama"], "ollama_model": "test:small"}
    _permit_local_models(tmp_path, monkeypatch)
    transport = planner.default_transport(config=config["models"])
    assert transport.name == "router[ollama:test:small]"


def test_local_model_builds_a_bounded_capability_and_original_signed_mission_resumes(tmp_path, server):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    LocalOllama.mode = "code"
    clock = Clock()
    with Body(home, clock=clock, builder=lambda s, c: builders.ModelBuilder(
            models.ModelRouter([models.OllamaRoute("test:small", port=server)]))) as body:
        body.boot()
        states = []
        for _ in range(5):
            clock.advance(30)
            states.extend(m["state"] for m in body.tick()["missions"])
        assert "ACHIEVED" in states
        built = body.journal.replay("genesis.built")[0].payload
        assert built["builder"] == "model:ollama:test:small"
        assert built["model_digest"] == "a" * 64 and built["cost_usd"] == 0
        assert body.journal.replay("mission.appraised")[0].payload["verdict"] == "VERIFIED"


def test_founder_detaches_and_replaces_model_while_identity_and_history_survive(tmp_path, server, monkeypatch):
    from greg.founder import DEVICE_KINDS
    home, key, body_id, _ = make_body(tmp_path)
    _permit_local_models(tmp_path, monkeypatch)
    assert "MODEL_ROUTE_SET" not in DEVICE_KINDS

    def factory(secrets, config):
        selection = dict(config["models"])
        routes, _ = models.available_routes(secrets, config=selection)
        if not routes:
            raise RuntimeError("no configured model")
        for route in routes:
            if route.provider == "ollama":
                route.port = server
        return builders.ModelBuilder(models.ModelRouter(routes))

    with Body(home, builder=factory) as body:
        body.apply(signed(key, body_id, "MODEL_ROUTE_SET",
                          {"order": ["ollama"], "ollama_model": "test:small"}))
        assert body.builder.router.routes[0].name == "ollama:test:small"
        body.apply(signed(key, body_id, "MODEL_ROUTE_SET", {"order": []}))
        assert body.builder is None and body.config["body_id"] == body_id
    with Body(home, builder=factory) as body:
        assert body.builder is None
        body.apply(signed(key, body_id, "MODEL_ROUTE_SET",
                          {"order": ["ollama"], "ollama_model": "test:better"}))
        assert body.builder.router.routes[0].name == "ollama:test:better"
        assert body.builder.router.complete("s", "u", budget_usd=0)["model_digest"] == "b" * 64
        assert len(body.journal.replay("founder.enrolled")) == 1
        assert len(body.journal.replay("model.configured")) == 3
    with Body(home, builder=factory) as body:
        assert body.builder.router.routes[0].name == "ollama:test:better"
        assert body.config["body_id"] == body_id


def test_open_console_discards_detached_model_draft_before_founder_signs(tmp_path, server, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    _permit_local_models(tmp_path, monkeypatch)

    def transport(selection):
        routes, _ = models.available_routes(config=selection)
        for route in routes:
            if route.provider == "ollama":
                route.port = server
        return models.ModelRouter(routes) if routes else None

    ctx = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={})
    console = Console(home, key=key, transport_factory=transport, planner_context=ctx)
    with Body(home) as body:
        body.apply(signed(key, body_id, "MODEL_ROUTE_SET",
                          {"order": ["ollama"], "ollama_model": "test:small"}))
        pending = console.ask("Tell me if my repository is dirty")
        assert console.proposals[pending]["proposal"]["status"] == "PROPOSED"
        body.apply(signed(key, body_id, "MODEL_ROUTE_SET", {"order": []}))
        with pytest.raises(ValueError, match="unknown or unsignable"):
            console.sign_proposal(pending)
        assert console.transport is None
        body.apply(signed(key, body_id, "MODEL_ROUTE_SET",
                          {"order": ["ollama"], "ollama_model": "test:better"}))
        next_id = console.ask("Tell me if my repository is dirty")
        assert console.proposals[next_id]["proposal"]["spec"]["provenance"]["model_digest"] == "b" * 64
