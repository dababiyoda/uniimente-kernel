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

    def __init__(self, *, served=None, iterations=None, stop_reason="end_turn", tokens=(1000, 1000),
                 report_model=True, text="answer"):
        self.calls, self.served, self.iterations, self.stop_reason = [], served, iterations, stop_reason
        self.tokens, self.report_model, self.text = tokens, report_model, text
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        if self.stop_reason == "refusal":
            return NS(stop_reason="refusal", stop_details=NS(category="cyber"), content=[], model=kw["model"])
        return NS(stop_reason="end_turn", model=(self.served or kw["model"]) if self.report_model else None,
                  content=[NS(type="text", text=self.text)],
                  usage=NS(input_tokens=self.tokens[0], output_tokens=self.tokens[1], iterations=self.iterations))


def attempt(kind, input_tokens, output_tokens):
    """One ``usage.iterations`` entry: the per-attempt billing record of the server-side fallback chain."""
    return NS(type=kind, input_tokens=input_tokens, output_tokens=output_tokens)


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


def test_a_withheld_substitution_is_still_booked_against_the_budget():
    """The provider billed the substituted call even though GREG withholds its answer, so the router's
    spend must include it, at the served model's price (1k in + 1k out tokens of claude-opus-4-8)."""
    router = models.ModelRouter([models.AnthropicRoute("k", model="claude-opus-5-5",
                                                       client=Client(served="claude-opus-4-8"))])
    with pytest.raises(models.ModelSubstitution) as info:
        router.complete("s", "u")
    assert info.value.cost_usd == pytest.approx((1000 * 5.0 + 1000 * 25.0) / 1e6)
    assert router.last["cost_usd"] == pytest.approx(info.value.cost_usd)


def test_an_unknown_substitute_is_booked_at_the_dearest_known_price():
    route = models.AnthropicRoute("k", model="claude-haiku-5-5", client=Client(served="claude-mystery-9"))
    with pytest.raises(models.ModelSubstitution) as info:
        route.complete("s", "u")
    dearest = max(models.ANTHROPIC_PRICES.values(), key=lambda p: p[1])
    assert info.value.cost_usd == pytest.approx((1000 * dearest[0] + 1000 * dearest[1]) / 1e6)


def test_fallback_message_with_matching_name_still_counts_as_substitution():
    # a fallback iteration means another attempt answered, even if the name were reused
    iterations = [attempt("message", 1000, 0), attempt("fallback_message", 1000, 1000)]
    route = models.AnthropicRoute("k", model="claude-opus-5-5", client=Client(iterations=iterations))
    with pytest.raises(models.ModelSubstitution) as info:
        route.complete("s", "u")
    # the withheld answer books both billed attempts, not just the top-level (last) one
    assert info.value.cost_usd == pytest.approx((2000 * 4.0 + 1000 * 20.0) / 1e6)


def test_explicit_priced_allowlist_uses_array_form_and_is_recorded():
    # the requested model declined after 1000 prompt tokens; the permitted substitute answered
    client = Client(served="claude-opus-4-8",
                    iterations=[attempt("message", 1000, 0), attempt("fallback_message", 1000, 1000)])
    route = models.AnthropicRoute("k", model="claude-opus-5-5", client=client, fallback_models=("claude-opus-4-8",))
    result = route.complete("s", "u", budget_usd=1.0)
    sent = client.calls[0]
    assert sent["betas"] == ["server-side-fallback-2026-06-01"]
    assert sent["fallbacks"] == [{"model": "claude-opus-4-8"}]
    assert result["substituted"] is True and result["served_model"] == "claude-opus-4-8"
    # Every attempt is booked (top-level usage covers only the answering one), each at the dearest permitted
    # rate because an iteration does not reliably name its model: claude-opus-4-8's $5/$25.
    assert result["cost_usd"] == pytest.approx((2000 * 5.0 + 1000 * 25.0) / 1e6)


def test_the_spend_bound_covers_every_attempt_of_the_fallback_chain():
    """Each permitted model may run as its own attempt with the same max_tokens and its own copy of the
    prompt, so the worst case of the whole chain, not of one attempt, must fit the signed budget."""
    client = Client()
    route = models.AnthropicRoute("k", model="claude-opus-5-5", client=client,
                                  fallback_models=("claude-opus-4-8", "claude-opus-5"))
    budget = 0.3
    route.complete("s", "u", budget_usd=budget)
    prompt = models._estimate_tokens("s" + "u")
    worst_chain = 3 * (prompt * 5.0 + client.calls[0]["max_tokens"] * 25.0) / 1e6
    assert worst_chain <= budget


def test_haiku_long_prompt_tier_is_used_for_the_bound_and_the_cost():
    """Above 100K prompt tokens claude-haiku-5-5 bills $0.50/$2.50, not $0.10/$0.50."""
    client = Client(tokens=(150_000, 1000))
    route = models.AnthropicRoute("k", model="claude-haiku-5-5", client=client)
    user = "x" * 330_000                                     # estimated well above 100K tokens
    budget = 0.08
    result = route.complete("s", user, budget_usd=budget)
    prompt = models._estimate_tokens("s" + user)
    assert prompt * 0.50 / 1e6 + client.calls[0]["max_tokens"] * 2.50 / 1e6 <= budget
    assert result["cost_usd"] == pytest.approx((150_000 * 0.50 + 1000 * 2.50) / 1e6)
    short = models.AnthropicRoute("k", model="claude-haiku-5-5", client=Client()).complete("s", "u")
    assert short["cost_usd"] == pytest.approx((1000 * 0.10 + 1000 * 0.50) / 1e6)   # the base tier is unchanged


def test_a_response_naming_no_model_is_unknown_not_the_requested_model():
    client = Client(report_model=False)
    route = models.AnthropicRoute("k", model="claude-opus-5-5", client=client)
    result = route.complete("s", "u")
    assert result["served_model"] is None and result["substituted"] is None
    assert result["requested_model"] == "claude-opus-5-5"
    routed = models.ModelRouter([models.AnthropicRoute("k", model="claude-opus-5-5",
                                                       client=Client(report_model=False))]).complete("s", "u")
    assert routed["served_model"] is None and routed["substituted"] is None


def test_a_route_that_never_checks_identity_reports_substituted_as_unknown():
    result = models.ModelRouter([Witness()]).complete("s", "u")
    assert result["substituted"] is None                      # not checked is not the same as "not substituted"


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


def test_configured_allowlist_must_be_a_list_and_prices_a_mapping():
    class Secrets:
        def resolve(self, name, declared=()):
            return "k"
    config = {"order": ["anthropic"], "anthropic_model": "claude-opus-5-5", "anthropic_fallback_models": "default"}
    routes, unavailable = models.available_routes(Secrets(), config=config)
    assert routes == [] and "explicit list of model ids" in unavailable["anthropic"]   # not split into letters
    with pytest.raises(ValueError, match="must map each fallback model"):
        models.AnthropicRoute("k", model="claude-opus-5-5", client=Client(), fallback_models=("claude-opus-4-8",),
                              fallback_prices=[[50.0, 250.0]])   # never silently replaced by the snapshot price


def test_a_withheld_build_attempt_is_booked_against_the_signed_build_budget(tmp_path):
    """Genesis pays for builds from the founder-signed build_budget_usd. A substituted answer is withheld,
    so no candidate comes back, but the provider billed it: the next build's budget must be smaller."""
    from greg import builders
    from tests.greg_fixtures import Clock, drop, make_body, signed
    from tests.unit.test_greg_genesis_builder import FUNCTION, _mission, _run

    class Recording(builders.ModelBuilder):
        def build(self, request, feedback=None):
            self.budgets.append(self.max_budget_usd)
            return super().build(request, feedback)

    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))          # build_budget_usd 1.0
    builder = Recording(models.ModelRouter([models.AnthropicRoute("k", model="claude-opus-5-5",
                                                                  client=Client(served="claude-opus-4-8"))]))
    builder.budgets = []
    body, states = _run(home, builder, ticks=2)
    assert builder.budgets == [1.0] and "ACHIEVED" not in states and not body.journal.replay("genesis.built")
    per_attempt = (1000 * 5.0 + 1000 * 25.0) / 1e6                       # claude-opus-4-8: withheld, but billed
    # the same deficit resolved again (e.g. after the founder's answer) builds on what remains of the budget
    body.genesis.resolve(mission=body.engine.book.missions["m:runbook"], function=FUNCTION, purpose="again",
                         now=Clock()())
    assert builder.budgets[1] == pytest.approx(1.0 - per_attempt)
    assert [e.payload["cost_usd"] for e in body.journal.replay("genesis.unbuilt")] == [pytest.approx(per_attempt)] * 2
    body.close()


def test_substitution_evidence_reaches_the_build_record_and_the_planner_provenance(tmp_path):
    """requested_model and substituted are evidence: a consumer must not drop them on the way to the journal."""
    import json
    from greg import builders, planner
    from tests.greg_fixtures import drop, make_body, signed
    from tests.unit.test_greg_genesis_builder import GOOD, _mission, _run
    from tests.unit.test_greg_interface import GOOD as DRAFT, inventory

    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    client = Client(served="claude-opus-4-8", text="```python\n" + GOOD + "```",
                    iterations=[attempt("message", 1000, 0), attempt("fallback_message", 1000, 1000)])
    builder = builders.ModelBuilder(models.ModelRouter([models.AnthropicRoute(
        "k", model="claude-opus-5-5", client=client, fallback_models=("claude-opus-4-8",))]))
    body, states = _run(home, builder)
    assert "ACHIEVED" in states                                           # a permitted substitute may build
    built = body.journal.replay("genesis.built")[0].payload
    assert built["requested_model"] == "claude-opus-5-5" and built["served_model"] == "claude-opus-4-8"
    assert built["substituted"] is True
    body.close()

    ctx = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={}, today="2026-09-26")
    router = models.ModelRouter([models.AnthropicRoute("k", model="claude-sonnet-5-5",
                                                       client=Client(text=json.dumps(DRAFT)))])
    proposal = planner.model_route("watch my notes", ctx, router)
    assert proposal["status"] == "PROPOSED", proposal                     # the mission schema admits the fields
    prov = proposal["spec"]["provenance"]
    assert prov["requested_model"] == prov["served_model"] == "claude-sonnet-5-5" and prov["substituted"] is False
