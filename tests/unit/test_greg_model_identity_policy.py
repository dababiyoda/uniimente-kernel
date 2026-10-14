"""Model identity is the founder's choice: no silent server-side substitution (Defect 8).

The Anthropic route used to send ``betas=["server-side-fallback-2026-07-01"], fallbacks="default"``,
which lets the provider re-run a refused request on a model it picks and keep the conversation
there. These tests pin the replacement policy with fake SDK clients (official call shape, no
network, no spend).
"""
from types import SimpleNamespace as NS

import pytest

from greg import models


class Client:
    """``beta.messages.create`` stand-in that reports a chosen served model and usage iterations."""

    def __init__(self, *, served=None, iterations=None, stop_reason="end_turn"):
        self.calls, self.served, self.iterations, self.stop_reason = [], served, iterations, stop_reason
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        if self.stop_reason == "refusal":
            return NS(stop_reason="refusal", stop_details=NS(category="cyber"), content=[], model=kw["model"])
        return NS(stop_reason="end_turn", model=self.served or kw["model"],
                  content=[NS(type="text", text="answer")],
                  usage=NS(input_tokens=1000, output_tokens=1000, iterations=self.iterations))


class Witness:
    provider, name = "witness", "witness:model"

    def __init__(self):
        self.calls = 0

    def complete(self, system, user, *, budget_usd=None):
        self.calls += 1
        return {"text": "second vendor", "cost_usd": 0.0, "served_model": "witness-1"}


def test_default_request_sends_no_server_side_fallback():
    client = Client()
    result = models.AnthropicRoute("k", model="claude-opus-5-5", client=client).complete("s", "u")
    sent = client.calls[0]
    assert "fallbacks" not in sent and "betas" not in sent
    assert result["requested_model"] == result["served_model"] == "claude-opus-5-5"
    assert result["substituted"] is False and result["fallback_policy"] == []


def test_the_default_scalar_form_cannot_be_configured():
    with pytest.raises(ValueError):
        models.AnthropicRoute("k", model="claude-opus-5-5", client=Client(), fallback_models="default")


def test_an_unpriced_fallback_is_refused_at_construction():
    with pytest.raises(ValueError, match="without a known price"):
        models.AnthropicRoute("k", model="claude-opus-5-5", client=Client(), fallback_models=("claude-mystery-9",))


def test_dated_snapshot_of_the_requested_model_is_the_same_model():
    result = models.AnthropicRoute("k", model="claude-opus-5-5",
                                   client=Client(served="claude-opus-5-5-20261001")).complete("s", "u")
    assert result["substituted"] is False


def test_unselected_served_model_is_withheld_and_terminal():
    witness = models.ModelRouter([models.AnthropicRoute("k", model="claude-opus-5-5",
                                                        client=Client(served="claude-opus-4-8")), Witness()])
    with pytest.raises(models.ModelSubstitution) as info:
        witness.complete("s", "u")
    assert info.value.kind == models.MODEL_SUBSTITUTION
    assert info.value.requested == "claude-opus-5-5" and info.value.served == "claude-opus-4-8"
    assert witness.routes[1].calls == 0                     # no other vendor is asked
    assert witness.last["tried"][0]["outcome"] == "substituted"


def test_fallback_message_with_matching_name_still_counts_as_substitution():
    # a fallback iteration means another attempt answered, even if the name were reused
    iterations = [NS(type="message"), NS(type="fallback_message")]
    route = models.AnthropicRoute("k", model="claude-opus-5-5", client=Client(iterations=iterations))
    with pytest.raises(models.ModelSubstitution):
        route.complete("s", "u")


def test_explicit_priced_allowlist_uses_array_form_and_is_recorded():
    client = Client(served="claude-opus-4-8", iterations=[NS(type="message"), NS(type="fallback_message")])
    route = models.AnthropicRoute("k", model="claude-opus-5-5", client=client, fallback_models=("claude-opus-4-8",))
    result = route.complete("s", "u", budget_usd=1.0)
    sent = client.calls[0]
    assert sent["betas"] == ["server-side-fallback-2026-06-01"]
    assert sent["fallbacks"] == [{"model": "claude-opus-4-8"}]
    assert result["substituted"] is True and result["served_model"] == "claude-opus-4-8"
    assert result["cost_usd"] == pytest.approx((1000 * 5.0 + 1000 * 25.0) / 1e6)   # billed at the substitute's rate


def test_spend_bound_uses_the_most_expensive_permitted_model():
    cheap = models.AnthropicRoute("k", model="claude-haiku-5-5", client=Client())
    with_fallback = models.AnthropicRoute("k", model="claude-haiku-5-5", client=Client(),
                                          fallback_models=("claude-fable-5-1",))
    assert with_fallback._bound_price() == (10.0, 50.0) and cheap._bound_price() == (0.10, 0.50)
    # a budget the primary could meet but the permitted substitute could not is not spent blind
    with pytest.raises(models.Unbounded):
        with_fallback.complete("s", "u", budget_usd=0.01)


def test_a_refusal_is_still_terminal_with_no_fallback_configured():
    router = models.ModelRouter([models.AnthropicRoute("k", model="claude-opus-5-5",
                                                       client=Client(stop_reason="refusal")), Witness()])
    with pytest.raises(models.Refusal):
        router.complete("s", "u")
    assert router.routes[1].calls == 0


def test_router_result_carries_requested_and_served():
    router = models.ModelRouter([models.AnthropicRoute("k", model="claude-sonnet-5-5", client=Client())])
    result = router.complete("s", "u")
    assert result["requested_model"] == "claude-sonnet-5-5" and result["substituted"] is False


def test_configured_route_reads_the_explicit_allowlist():
    class Secrets:
        def resolve(self, name, declared=()):
            return "k"
    config = {"order": ["anthropic"], "anthropic_model": "claude-opus-5-5",
              "anthropic_fallback_models": ["claude-opus-4-8"]}
    routes, unavailable = models.available_routes(Secrets(), config=config)
    if not routes:   # the SDK is optional; the route reports why it is unavailable
        assert "anthropic" in unavailable
        return
    assert routes[0].fallback_models == ("claude-opus-4-8",)
