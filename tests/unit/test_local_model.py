"""Local HTTP protocol and cognition boundary regression evidence; no real model."""
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from egregore.contracts import ContractError, SignalEnvelope
from egregore.local_model import LocalDraftProposer, LocalModelClient, LocalModelConfig
from egregore.resources import ResourceGovernor
from egregore.runtime import StandingCognitionRuntime
from provenance.ledger import EvidenceLedger


@contextmanager
def endpoint(content='{"objective":"draft update","text":"Review this supplied evidence."}', status=200):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(status)
            if status == 302:
                self.send_header("Location", "https://api.openai.com/v1/chat/completions")
            self.end_headers()
            self.wfile.write(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = LocalModelClient(LocalModelConfig(base_url=f"http://127.0.0.1:{server.server_port}/v1"))
        yield client, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("url", [
    "https://api.openai.com/v1", "https://example.com/v1", "http://192.168.1.1/v1",
    "http://localhost/v1?redirect=1", "http://secret@localhost/v1", "file:///v1",
])
def test_refuses_hosted_or_ambiguous_endpoints(url):
    with pytest.raises(ContractError):
        LocalModelConfig(base_url=url)


@pytest.mark.parametrize("config", [
    {"max_tokens": 0}, {"max_tokens": True}, {"timeout_seconds": float("inf")},
    {"timeout_seconds": 0}, {"model": "qwen-cloud"}, {"model": ""},
])
def test_bounded_configuration(config):
    with pytest.raises(ContractError):
        LocalModelConfig(**config)


def signal():
    return SignalEnvelope.build(source="test", source_event_id="1", observed_at="2026-09-30",
                                payload={"text": "supplied evidence"}, evidence_refs=("source:1",))


def test_real_loopback_protocol_is_proposal_only_and_retry_is_idempotent(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unused-key")
    with endpoint() as (client, calls):
        proposer = LocalDraftProposer(client=client)
        ledger = EvidenceLedger("sha256:" + "a" * 64)
        runtime = StandingCognitionRuntime(ledger=ledger, proposers={proposer.name: proposer}, evaluators={})
        item = signal()
        runtime.ingest(item)
        kwargs = dict(trigger_id="local-1", signal_ids=(item.signal_id,),
                      resources=ResourceGovernor(max_model_calls=2, max_estimated_cost_usd=0))
        cycle = runtime.tick(**kwargs)
        candidate = cycle.candidates[0]
        assert candidate.execution_authority == "none"
        assert candidate.target == "internal://review/drafts"
        assert candidate.evidence_refs == ("source:1",)
        assert candidate.confidence == 0
        assert cycle.selected_candidate_id is None  # required evaluators are absent
        assert runtime.tick(**kwargs).to_dict() == cycle.to_dict()
        assert len(calls) == 1
        assert calls[0]["model"] == "qwen3.5:4b"
        assert calls[0]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("content", [
    "not json", '{"objective":"x","text":"y","execution_authority":"founder"}',
    '{"objective":"x","text":null}', '{"objective":"","text":"y"}',
])
def test_untrusted_model_output_cannot_supply_authority_or_invalid_contracts(content):
    with endpoint(content) as (client, _):
        with pytest.raises(ContractError):
            LocalDraftProposer(client=client)((signal(),), {})


def test_redirect_is_refused_instead_of_reaching_paid_provider():
    with endpoint(status=302) as (client, calls):
        with pytest.raises(ContractError, match="redirect"):
            client.complete("system", "user")
        assert len(calls) == 1
