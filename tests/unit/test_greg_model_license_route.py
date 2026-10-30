"""Route selection consumes the model-license helper.

`licensing.ollama_model` and `qualify_use` already judge an installed model's weights.
Selection did not ask them, so a model whose license disallows GREG's use was still
chosen. These tests drive `available_routes`, `planner.default_transport` and
`validate_route_selection` — the real selection path — not the helper alone.
"""
from __future__ import annotations

import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from greg import licensing, models
from greg.body import Body
from greg import planner
from tests.greg_fixtures import drop, make_body, signed
from tests.unit.test_greg_ollama import LocalOllama

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "licenses"
APACHE = (FIXTURES / "Apache-2.0.txt").read_text()
LLAMA = "LLAMA 3.1 COMMUNITY LICENSE AGREEMENT\nLlama 3.1 Version Release Date: July 23, 2024\n"


def store(tmp_path, name, licenses=(APACHE,)):
    """One Ollama store entry: manifest, weight blob, and one blob per license text."""
    root = tmp_path / "models"
    (root / "blobs").mkdir(parents=True, exist_ok=True)

    def blob(data: bytes) -> str:
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        (root / "blobs" / digest.replace(":", "-")).write_bytes(data)
        return digest

    weights = b"GGUF weights"
    layers = [{"mediaType": "application/vnd.ollama.image.model", "digest": blob(weights), "size": len(weights)}]
    layers += [{"mediaType": licensing.OLLAMA_LICENSE, "digest": blob(text.encode()), "size": len(text)}
               for text in licenses]
    path = root / "manifests" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schemaVersion": 2, "layers": layers}))
    return root


def _isolate_store(monkeypatch, tmp_path, root: Path):
    monkeypatch.setenv("OLLAMA_MODELS", str(root))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def test_a_license_that_disallows_use_is_not_selected_and_the_reason_is_kept(tmp_path, monkeypatch):
    root = store(tmp_path, "registry.ollama.ai/library/llama3.1/8b", licenses=(LLAMA,))
    _isolate_store(monkeypatch, tmp_path, root)
    config = {"order": ["ollama"], "ollama_model": "llama3.1:8b"}
    routes, missing = models.available_routes(config=config)
    assert routes == []
    assert "ollama" in missing and "license" in missing["ollama"].lower()
    assert planner.default_transport(config=config) is None
    with pytest.raises(ValueError, match="license"):
        models.validate_route_selection(config)


def test_a_missing_or_unlicensed_model_fails_closed(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    _isolate_store(monkeypatch, tmp_path, empty)
    routes, missing = models.available_routes(config={"order": ["ollama"], "ollama_model": "test:small"})
    assert routes == [] and "license" in missing["ollama"].lower()

    root = store(tmp_path / "bare", "registry.ollama.ai/library/test/small", licenses=())
    _isolate_store(monkeypatch, tmp_path, root)
    routes, missing = models.available_routes(config={"order": ["ollama"], "ollama_model": "test:small"})
    assert routes == [] and "license" in missing["ollama"].lower()
    with pytest.raises(ValueError, match="license"):
        models.validate_route_selection({"order": ["ollama"], "ollama_model": "test:small"})


def test_a_cleared_model_is_selected_and_the_assessment_is_on_the_route(tmp_path, monkeypatch):
    root = store(tmp_path, "registry.ollama.ai/library/test/small")
    _isolate_store(monkeypatch, tmp_path, root)
    LocalOllama.calls = []
    LocalOllama.mode = "ok"
    http = ThreadingHTTPServer(("127.0.0.1", 0), LocalOllama)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        config = {"order": ["ollama"], "ollama_model": "test:small"}
        routes, missing = models.available_routes(config=config)
        assert missing == {} and len(routes) == 1
        route = routes[0]
        assert route.license_assessment["verdict"] == "CLEARED"
        assert route.license_assessment["held"] is False
        assert route.license_use["verdict"] == licensing.COMPATIBLE
        assert route.license_use["use"] == licensing.GREG_USE
        transport = planner.default_transport(config=config)
        assert transport is not None and transport.routes[0].name == "ollama:test:small"
        transport.routes[0].port = http.server_port
        assert transport.complete("s", "u", budget_usd=0)["served_model"] == "test:small"
        assert [call[0] for call in LocalOllama.calls] == ["GET", "POST"]
    finally:
        http.shutdown()
        http.server_close()
        thread.join()


def test_selection_does_not_call_the_model_server(tmp_path, monkeypatch):
    root = store(tmp_path, "registry.ollama.ai/library/llama3.1/8b", licenses=(LLAMA,))
    _isolate_store(monkeypatch, tmp_path, root)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            raise AssertionError("selection contacted the model server")

        def do_POST(self):
            raise AssertionError("selection contacted the model server")

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        routes, missing = models.available_routes(config={"order": ["ollama"], "ollama_model": "llama3.1:8b"})
        assert routes == [] and "license" in missing["ollama"].lower()
    finally:
        http.shutdown()
        http.server_close()
        thread.join()


def test_an_inbox_command_for_a_disallowed_model_is_rejected_and_recorded(tmp_path, monkeypatch):
    root = store(tmp_path, "registry.ollama.ai/library/llama3.1/8b", licenses=(LLAMA,))
    _isolate_store(monkeypatch, tmp_path, root)
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        drop(home, signed(key, body_id, "MODEL_ROUTE_SET",
                          {"order": ["ollama"], "ollama_model": "llama3.1:8b"}))
        outcome = body.ingest_inbox()
        assert outcome[0]["status"] == "REJECTED"
        assert "license" in outcome[0]["reason"].lower()
        refused = body.journal.replay("command.rejected")
        assert refused and "license" in refused[-1].payload["reason"].lower()
        assert body.journal.replay("model.configured") == []
