"""Missing or malformed evidence cannot spend even a permitted model call."""
import pytest
from greg.cognition.cortex import reason, registry_view
from greg import models


@pytest.mark.parametrize("sources", [None, [], [{"id": "s", "text": ""}],
    [{"id": "s", "text": "one"}, {"id": "s", "text": "two"}],
    [{"id": 3, "text": "one"}], [{"id": "x" * 129, "text": "one"}]])
def test_invalid_sources_abstain_before_model_invocation(monkeypatch, sources):
    calls = []
    def unexpected(*args, **kw):
        calls.append(kw)
        raise AssertionError("invalid evidence invoked a model")
    monkeypatch.setattr(models.OllamaRoute, "complete", unexpected)
    receipt = reason({"problem_id": "preflight", "operation": "interpret",
                      "data": {"task": "summarize", "sources": sources}},
                     registry=registry_view(), model_config={"order": ["ollama"], "ollama_model": "local:test"})
    assert receipt["abstention_state"] == "ABSTAIN" and not calls
    assert receipt["compute_cost"]["model_calls"] == 0
    assert receipt["proof_artifact"] is None and receipt["authority_created"] is False
