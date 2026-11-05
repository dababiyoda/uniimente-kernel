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


def _select_cleared_model(tmp_path, monkeypatch):
    """A body whose signed selection names an Apache-licensed local model."""
    root = store(tmp_path, "registry.ollama.ai/library/test/small")
    _isolate_store(monkeypatch, tmp_path, root)
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        drop(home, signed(key, body_id, "MODEL_ROUTE_SET",
                          {"order": ["ollama"], "ollama_model": "test:small"}))
        outcome = body.ingest_inbox()
        assert outcome[0]["status"] == "APPLIED", outcome
        assert body.journal.replay("model.configured")
    return home


def test_a_license_change_after_selection_holds_the_route_and_the_body_still_opens_and_ticks(
        tmp_path, monkeypatch):
    """A stored selection whose license no longer permits use is a hold, not a crash.

    Review 6528337584 (g5, g8), correction 6530419356: Body open and Body.tick
    re-validate the stored selection by raising. The body must stay up, drop the
    route, and record the reason.
    """
    home = _select_cleared_model(tmp_path, monkeypatch)
    later = store(tmp_path / "later", "registry.ollama.ai/library/test/small", licenses=(LLAMA,))
    monkeypatch.setenv("OLLAMA_MODELS", str(later))
    with Body(home) as body:
        selected = body.engine.cognition_model
        assert "ollama" not in selected.get("order", [])
        assert "ollama_model" not in selected
        hold = selected.get("model_license_hold")
        assert isinstance(hold, dict) and "license" in str(hold.get("reason", "")).lower()
        body.boot()
        body.tick()
        body.tick()
        recorded = body.journal.replay("model.license_held")
        assert recorded and recorded[-1].payload["model"] == "test:small"
        assert "license" in recorded[-1].payload["reason"].lower()


def test_a_selected_model_the_body_cannot_read_is_held_not_a_crash(tmp_path, monkeypatch):
    """g6: the body process cannot see the store that was visible when the model was selected."""
    home = _select_cleared_model(tmp_path, monkeypatch)
    invisible = tmp_path / "no-store"
    invisible.mkdir()
    monkeypatch.setenv("OLLAMA_MODELS", str(invisible))
    monkeypatch.setenv("HOME", str(tmp_path / "other-home"))
    with Body(home) as body:
        selected = body.engine.cognition_model
        assert "ollama" not in selected.get("order", [])
        assert isinstance(selected.get("model_license_hold"), dict)
        body.boot()
        assert body.tick().get("stopped") is not True


def test_an_init_model_whose_license_does_not_permit_use_is_held_when_the_body_opens(
        tmp_path, monkeypatch):
    """g3: `greg init --local-model` writes the name and never asks the license helper.

    Opening the body is where that config becomes a route. A disallowed model is
    held there, so cognition is not handed the name.
    """
    from greg.body import init_body

    root = store(tmp_path, "registry.ollama.ai/library/llama3.1/8b", licenses=(LLAMA,))
    _isolate_store(monkeypatch, tmp_path, root)
    home = tmp_path / "init-body"
    init_body(home, read_roots=[str(tmp_path / "data")], local_model="llama3.1:8b")
    with Body(home) as body:
        selected = body.engine.cognition_model
        assert "ollama" not in selected.get("order", [])
        hold = selected.get("model_license_hold")
        assert isinstance(hold, dict) and hold.get("model") == "llama3.1:8b"
        assert "license" in str(hold.get("reason", "")).lower()


def test_semantic_cognition_does_not_call_a_model_whose_license_does_not_permit_use(
        tmp_path, monkeypatch):
    """The direct OllamaRoute path in cortex._semantic posts a held model today."""
    from greg.cognition.contracts import CognitionError, ProblemGeometry
    from greg.cognition.cortex import _semantic

    root = store(tmp_path, "registry.ollama.ai/library/test/small", licenses=(LLAMA,))
    _isolate_store(monkeypatch, tmp_path, root)
    called = []

    def spy(self, *args, **kwargs):
        called.append(self.model)
        raise AssertionError("a held model was called")

    monkeypatch.setattr(models.OllamaRoute, "complete", spy)
    with pytest.raises(CognitionError, match="license"):
        _semantic({"sources": [{"id": "s", "text": "hello"}]}, ProblemGeometry(),
                  {"order": ["ollama"], "ollama_model": "test:small"})
    assert called == []


def test_admit_model_selection_runs_after_validate_and_a_hold_rejects_the_command(
        tmp_path, monkeypatch):
    """#264's gate is called after validate_route_selection. Its output is not stored:
    extra evidence would fail the next validate. A hold rejects the new command.
    """
    root = store(tmp_path, "registry.ollama.ai/library/test/small")
    _isolate_store(monkeypatch, tmp_path, root)
    calls = []
    real = models.validate_route_selection

    def tracking(body):
        calls.append("validate")
        return real(body)

    def admit(config, models_dir=None):
        calls.append("admit")
        return {"order": [name for name in config.get("order", []) if name != "ollama"],
                "model_license_hold": {"model": config.get("ollama_model"), "verdict": "FOUNDER_REVIEW",
                                       "reason": "stricter gate", "manifest_sha256": None,
                                       "assessment_digest": None}}

    monkeypatch.setattr(models, "validate_route_selection", tracking)
    monkeypatch.setattr(licensing, "admit_model_selection", admit, raising=False)
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        drop(home, signed(key, body_id, "MODEL_ROUTE_SET",
                          {"order": ["ollama"], "ollama_model": "test:small"}))
        outcome = body.ingest_inbox()
        assert outcome[0]["status"] == "REJECTED"
        assert "stricter gate" in outcome[0]["reason"]
        assert body.journal.replay("model.configured") == []
    assert calls[:2] == ["validate", "admit"]


def test_admit_evidence_is_not_written_into_the_signed_selection(tmp_path, monkeypatch):
    """A cleared admit result may carry license_evidence. The ledger keeps the
    validated selection, which validate_route_selection can read again."""
    root = store(tmp_path, "registry.ollama.ai/library/test/small")
    _isolate_store(monkeypatch, tmp_path, root)
    calls = []
    real = models.validate_route_selection

    def tracking(body):
        calls.append("validate")
        return real(body)

    def admit(config, models_dir=None):
        calls.append("admit")
        return {**config, "license_evidence": {"model": config.get("ollama_model"), "verdict": "CLEARED",
                                               "manifest_sha256": "abc", "assessment_digest": "def"}}

    monkeypatch.setattr(models, "validate_route_selection", tracking)
    monkeypatch.setattr(licensing, "admit_model_selection", admit, raising=False)
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        drop(home, signed(key, body_id, "MODEL_ROUTE_SET",
                          {"order": ["ollama"], "ollama_model": "test:small"}))
        outcome = body.ingest_inbox()
        assert outcome[0]["status"] == "APPLIED", outcome
        stored = body.journal.replay("model.configured")[-1].payload["selection"]
        assert stored == {"order": ["ollama"], "ollama_model": "test:small"}
        assert calls[:2] == ["validate", "admit"]


def test_a_replayed_selection_is_admitted_after_it_is_validated(tmp_path, monkeypatch):
    """On open, validate runs on the stored selection and then admit. Admit's hold
    is what the body uses. Admit is not fed back into validate."""
    home = _select_cleared_model(tmp_path, monkeypatch)
    calls = []
    real = models.validate_route_selection

    def tracking(body):
        calls.append(("validate", set(body)))
        return real(body)

    def admit(config, models_dir=None):
        calls.append(("admit", set(config)))
        return {"order": [name for name in config.get("order", []) if name != "ollama"],
                **{k: v for k, v in config.items() if k not in ("order", "ollama_model")},
                "model_license_hold": {"model": config.get("ollama_model"), "verdict": "FOUNDER_REVIEW",
                                       "reason": "gate hold on replay", "manifest_sha256": "abc",
                                       "assessment_digest": "def"}}

    monkeypatch.setattr(models, "validate_route_selection", tracking)
    monkeypatch.setattr(licensing, "admit_model_selection", admit, raising=False)
    with Body(home) as body:
        selected = body.engine.cognition_model
        assert "ollama" not in selected.get("order", [])
        assert selected["model_license_hold"]["reason"] == "gate hold on replay"
        kinds = [name for name, _ in calls]
        assert kinds.index("validate") < kinds.index("admit")
        admitted = next(fields for name, fields in calls if name == "admit")
        assert "model_license_hold" not in admitted
        assert "ollama_model" in admitted


def test_a_cleared_model_stays_selected_when_the_body_reopens(tmp_path, monkeypatch):
    home = _select_cleared_model(tmp_path, monkeypatch)
    with Body(home) as body:
        selected = body.engine.cognition_model
        assert selected.get("order") == ["ollama"]
        assert selected.get("ollama_model") == "test:small"
        assert "model_license_hold" not in selected
        assert body.journal.replay("model.license_held") == []
