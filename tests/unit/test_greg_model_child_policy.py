"""The confined model child (#169) keeps the founder's model-identity policy (#178).

#169 moved every paid SDK call into ``greg.model_child`` so that, on a body with confined egress, it runs in a network
namespace behind the relay. Its call sent ``fallbacks="default"``: the provider chooses a substitute, and #178 had
removed exactly that after an audit found substitutes billed at the requested model's price. After the merge the
child sends only the founder's explicit allowlist, in the array form, and returns the per-attempt usage that #178's
accounting bills from, on both the in-process and the confined path.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from greg import model_child, models


class _Messages:
    def __init__(self, sent):
        self.sent = sent

    def create(self, **request):
        self.sent.append(request)
        usage = NS(input_tokens=10, output_tokens=5,
                   iterations=[NS(type="message", input_tokens=10, output_tokens=0),
                               NS(type="fallback_message", input_tokens=10, output_tokens=5)])
        return NS(stop_reason="end_turn", stop_details=None, model="claude-opus-4-8", usage=usage,
                  content=[NS(type="text", text="ok")])


def _sdk(sent):
    return NS(beta=NS(messages=_Messages(sent)))


def test_without_an_allowlist_the_child_sends_no_fallback_at_all():
    sent = []
    model_child.call("anthropic", _sdk(sent), "claude-opus-5-5", "s", "u", 100)
    assert "fallbacks" not in sent[0] and "betas" not in sent[0]


def test_an_allowlist_goes_in_the_array_form_and_the_attempts_come_back():
    sent = []
    answer = model_child.call("anthropic", _sdk(sent), "claude-opus-5-5", "s", "u", 100,
                              fallbacks=("claude-opus-4-8",), fallback_beta="server-side-fallback-2026-06-01")
    assert sent[0]["fallbacks"] == [{"model": "claude-opus-4-8"}]
    assert sent[0]["betas"] == ["server-side-fallback-2026-06-01"]
    assert [i["type"] for i in answer["iterations"]] == ["message", "fallback_message"]
    assert answer["served_model"] == "claude-opus-4-8"


@pytest.mark.parametrize("bad", ["default", ["default", ""], [None]])
def test_the_provider_chosen_form_is_refused_by_the_child_itself(bad):
    with pytest.raises(ValueError):
        model_child.call("anthropic", _sdk([]), "claude-opus-5-5", "s", "u", 100, fallbacks=bad,
                         fallback_beta="server-side-fallback-2026-06-01")


def test_a_confined_route_hands_the_child_exactly_the_founders_allowlist(monkeypatch):
    seen = {}

    def fake_confined(provider, api_key, model, system, user, max_tokens, relay, **kw):
        seen.update(kw, provider=provider, model=model)
        return {"refusal": False, "refusal_detail": None, "text": "ok", "status": "end_turn", "input_tokens": 10,
                "output_tokens": 5, "served_model": "claude-opus-4-8",
                "iterations": [{"type": "message", "input_tokens": 10, "output_tokens": 0},
                               {"type": "fallback_message", "input_tokens": 10, "output_tokens": 5}]}
    monkeypatch.setattr(models, "confined_call", fake_confined)
    route = models.AnthropicRoute("k", model="claude-opus-5-5", fallback_models=("claude-opus-4-8",), egress=object())
    result = route.complete("s", "u")
    assert seen["fallbacks"] == ("claude-opus-4-8",) and seen["fallback_beta"] == route.FALLBACK_BETA
    assert result["served_model"] == "claude-opus-4-8" and result["substituted"] is True
    assert result["cost_usd"] is not None and result["cost_usd"] > 0     # both billed attempts, at the bound price


def test_a_confined_answer_from_a_model_outside_the_allowlist_is_withheld(monkeypatch):
    monkeypatch.setattr(models, "confined_call", lambda *a, **k: {
        "refusal": False, "refusal_detail": None, "text": "ok", "status": "end_turn", "input_tokens": 10,
        "output_tokens": 5, "served_model": "claude-mystery-9", "iterations": []})
    route = models.AnthropicRoute("k", model="claude-haiku-5-5", egress=object())
    with pytest.raises(models.ModelSubstitution):
        route.complete("s", "u")


def test_an_unreported_served_model_stays_unknown_on_the_openai_route(monkeypatch):
    monkeypatch.setattr(models, "confined_call", lambda *a, **k: {
        "refusal": False, "refusal_detail": None, "text": "ok", "status": "completed", "input_tokens": 1,
        "output_tokens": 1, "served_model": None, "iterations": []})
    route = models.OpenAIRoute("k", price=(1.0, 4.0), egress=object())
    assert route.complete("s", "u")["served_model"] is None
