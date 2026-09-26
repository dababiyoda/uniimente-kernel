"""Routing integrity through the real ``openai`` and ``anthropic`` SDK clients.

The SDKs are optional dependencies (not installed in CI); these tests run wherever they are.
Each client talks to an in-process HTTP stub (httpx MockTransport), so the error objects,
request shapes and response parsing are the SDKs' own. No network, no key, no spend.
"""
import json

import pytest

httpx2 = pytest.importorskip("httpx2")
openai = pytest.importorskip("openai")
anthropic = pytest.importorskip("anthropic")

from greg import models  # noqa: E402

FLAGGED = {"error": {"message": "Invalid prompt: your prompt was flagged as potentially violating our usage policy. "
                                "Please try again with a different prompt.",
                     "type": "invalid_request_error", "param": None, "code": "invalid_prompt"}}


def openai_client(status, body):
    transport = httpx2.MockTransport(lambda request: httpx2.Response(status, json=body))
    return openai.OpenAI(api_key="sk-test", base_url="https://api.openai.com/v1", max_retries=0,
                         http_client=httpx2.Client(transport=transport))


def anthropic_client(handler):
    return anthropic.Anthropic(api_key="sk-ant-test", base_url="https://api.anthropic.com", max_retries=0,
                               http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))


class Witness:
    provider, name = "witness", "witness:model"

    def __init__(self):
        self.calls = 0

    def complete(self, system, user, *, budget_usd=None):
        self.calls += 1
        return {"text": "answer from a second vendor", "cost_usd": 0.0, "served_model": "witness-1"}


def test_the_real_openai_sdk_policy_error_is_a_terminal_refusal():
    witness = Witness()
    router = models.ModelRouter([models.OpenAIRoute("sk-test", model="gpt-x", price=(2.0, 12.0),
                                                    client=openai_client(400, FLAGGED)), witness])
    with pytest.raises(models.Refusal) as info:
        router.complete("sys", "the same request")
    assert info.value.kind == models.PROVIDER_POLICY_REFUSAL and witness.calls == 0


def test_the_real_openai_sdk_rate_limit_still_fails_over():
    witness = Witness()
    router = models.ModelRouter([models.OpenAIRoute("sk-test", model="gpt-x", price=(2.0, 12.0), client=openai_client(
        429, {"error": {"message": "Rate limit reached", "type": "requests", "code": "rate_limit_exceeded"}})), witness])
    result = router.complete("sys", "user")
    assert witness.calls == 1 and result["tried"][0]["class"] == models.TRANSIENT


def test_anthropic_errors_are_classified_through_the_real_sdk():
    def handler(request):
        text = json.loads(request.content)["messages"][0]["content"]
        if text == "overloaded":
            return httpx2.Response(529, json={"type": "error", "error": {"type": "overloaded_error",
                                                                          "message": "Overloaded"}})
        if text == "policy":   # illustrative wording: Anthropic normally declines via stop_reason "refusal"
            return httpx2.Response(400, json={"type": "error", "error": {
                "type": "invalid_request_error", "message": "Output blocked by content filtering policy"}})
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-20260801",
            "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5}})

    route = models.AnthropicRoute("sk-ant-test", model="claude-opus-5", client=anthropic_client(handler))
    with pytest.raises(models.RouteError) as outage:
        route.complete("s", "overloaded")
    assert outage.value.kind == models.TRANSIENT and not isinstance(outage.value, models.Refusal)
    with pytest.raises(models.Refusal) as verdict:
        route.complete("s", "policy")
    assert verdict.value.kind == models.PROVIDER_POLICY_REFUSAL
    served = route.complete("s", "hello")
    assert served["served_model"] == "claude-sonnet-5-20260801"                 # the provider's report, not our request
