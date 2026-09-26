"""Provider-independent model routing: failover, true authorship, no refusal shopping, bounded spend.

The SDK clients are fakes with the official SDKs' call shapes (anthropic ``beta.messages.create``,
openai ``responses.create``); no network or money is used here.
"""
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace as NS

import pytest

from greg import builders, models, planner
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_genesis_builder import GOOD, _mission


class FakeAnthropic:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if reply == "REFUSE":
            return NS(stop_reason="refusal", stop_details=NS(category="cyber"), content=[])
        return NS(stop_reason="end_turn", content=[NS(type="text", text=reply)],
                  usage=NS(input_tokens=1000, output_tokens=2000))


class FakeOpenAI:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.responses = NS(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return NS(output_text=reply, output=[], status="completed", usage=NS(input_tokens=1000, output_tokens=2000))


def fenced(source):
    return "```python\n" + source + "```"


def test_router_fails_over_and_names_the_true_author():
    down = models.AnthropicRoute("k", client=FakeAnthropic(ConnectionError("503 overloaded")))
    up = models.OpenAIRoute("k", client=FakeOpenAI("hello"), price=(1.0, 4.0))
    router = models.ModelRouter([down, up])
    result = router.complete("sys", "user")
    assert result["text"] == "hello" and result["route"] == "openai:gpt-5.5"
    assert [t["outcome"] for t in result["tried"]] == ["failed", "ok"]
    assert result["cost_usd"] == pytest.approx((1000 * 1.0 + 2000 * 4.0) / 1e6)


def test_a_refusal_is_final_and_never_shopped_to_another_vendor():
    refusing = models.AnthropicRoute("k", client=FakeAnthropic("REFUSE"))
    other = FakeOpenAI("would have answered")
    router = models.ModelRouter([refusing, models.OpenAIRoute("k", client=other, price=(1.0, 4.0))])
    with pytest.raises(models.Refusal):
        router.complete("sys", "user")
    assert other.calls == []


def test_spend_is_bounded_per_route_and_unpriced_routes_are_skipped_when_money_is_at_stake():
    unpriced = FakeOpenAI("x")
    priced = FakeAnthropic("ok")
    router = models.ModelRouter([models.OpenAIRoute("k", client=unpriced),       # price unknown
                                 models.AnthropicRoute("k", model="claude-opus-5", client=priced)])
    result = router.complete("s", "u", budget_usd=0.10)
    assert unpriced.calls == [] and result["tried"][0]["outcome"] == "skipped"
    max_tokens = priced.calls[0]["max_tokens"]
    assert max_tokens * 25.0 / 1e6 <= 0.10                                     # worst case fits the budget
    with pytest.raises(models.RouteError):                                      # too little to answer at all
        models.ModelRouter([models.AnthropicRoute("k", client=FakeAnthropic("ok"))]).complete(
            "s", "u", budget_usd=0.001)


def test_a_route_that_keeps_failing_is_demoted_until_its_cooldown_passes():
    now = [datetime(2026, 9, 26, tzinfo=timezone.utc)]
    flaky = FakeAnthropic(*[ConnectionError("down")] * 2, "back")
    steady = FakeOpenAI("a", "b", "c", "d")
    router = models.ModelRouter([models.AnthropicRoute("k", client=flaky),
                                 models.OpenAIRoute("k", client=steady, price=(1.0, 4.0))], clock=lambda: now[0])
    router.complete("s", "u")
    router.complete("s", "u")
    assert len(flaky.calls) == 2
    assert router.complete("s", "u")["route"].startswith("openai")              # demoted: not even tried
    assert len(flaky.calls) == 2
    now[0] += timedelta(minutes=11)
    assert router.complete("s", "u")["route"].startswith("anthropic")           # recovered after cooldown


def test_planner_records_the_route_that_wrote_the_draft():
    from tests.unit.test_greg_interface import GOOD as DRAFT, inventory

    def _ctx():
        return planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={}, today="2026-09-26")
    router = models.ModelRouter([models.AnthropicRoute("k", client=FakeAnthropic(TimeoutError("slow"))),
                                 models.OpenAIRoute("k", client=FakeOpenAI(json.dumps(DRAFT)), price=(1.0, 4.0))])
    proposal = planner.model_route("watch my notes", _ctx(), router)
    assert proposal["status"] == "PROPOSED", proposal
    prov = proposal["spec"]["provenance"]
    assert prov["model"] == "openai:gpt-5.5" and prov["routes_tried"][0]["outcome"] == "failed"
    refused = planner.model_route("x", _ctx(), models.ModelRouter([models.AnthropicRoute(
        "k", client=FakeAnthropic("REFUSE"))]))
    assert refused["status"] == "REFUSED"


def test_genesis_builds_through_whichever_vendor_is_up_and_records_route_health(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    anthropic = FakeAnthropic(ConnectionError("503"), ConnectionError("503"))
    openai = FakeOpenAI(fenced(GOOD))

    def factory(secrets, config):
        return builders.ModelBuilder(models.ModelRouter([
            models.AnthropicRoute("k", client=anthropic),
            models.OpenAIRoute("k", client=openai, price=(1.0, 4.0))]))

    clock = Clock()
    body = Body(home, clock=clock, builder=factory).open()
    body.boot()
    states = []
    for _ in range(4):
        clock.advance(30)
        states.append(body.tick()["missions"][0]["state"])
    assert "ACHIEVED" in states                                                 # the ORIGINAL mission closed
    built = body.journal.replay("genesis.built")[0].payload
    assert built["builder"] == "model:openai:gpt-5.5" and built["cost_usd"] > 0
    assert json.dumps(openai.calls).count("held_out") == 0                      # contract, not held-out vectors
    assert openai.calls[0]["max_output_tokens"] * 4.0 / 1e6 <= 1.0              # bounded by the signed budget
    routes = [e.payload for e in body.journal.replay("model.route")]
    assert [(r["provider"], r["outcome"]) for r in routes] == [("anthropic", "failed"), ("openai", "ok")]
    registered = body.journal.replay("capability.registered")[0].payload["manifest"]
    assert registered["provider"] == "built:model:openai:gpt-5.5"
    body.close()

    anthropic2 = FakeAnthropic()
    body = Body(home, clock=Clock(), builder=lambda s, c: builders.ModelBuilder(models.ModelRouter(
        [models.AnthropicRoute("k", client=anthropic2)]))).open()
    assert body.builder.router.health["anthropic:claude-opus-5"]["consecutive_failures"] == 1   # history replayed
    body.close()


def test_available_routes_reports_what_is_missing_instead_of_guessing():
    class NoSecrets:
        def resolve(self, name, declared):
            raise KeyError(name)
    routes, missing = models.available_routes(NoSecrets(), config={"order": ["anthropic", "openai"]})
    assert routes == [] and set(missing) == {"anthropic", "openai"}
    assert planner.default_transport(NoSecrets(), config={"order": ["anthropic"]}) is None


def test_installed_body_can_build_and_a_missing_route_degrades_instead_of_crash_looping(tmp_path):
    import plistlib
    from greg import service
    plist = plistlib.loads(service.install(tmp_path / "home", "macos", target_dir=tmp_path, builder="models")
                           .read_bytes())
    assert plist["ProgramArguments"][-2:] == ["--builder", "models"]
    assert "/opt/homebrew/bin" in plist["EnvironmentVariables"]["PATH"]          # launchd can find `claude`
    assert "--builder" not in service.command(tmp_path, builder="none")
    with pytest.raises(ValueError):
        service.command(tmp_path, builder="anything")

    (tmp_path / "b").mkdir()
    home, key, body_id, data = make_body(tmp_path / "b")

    def no_routes(secrets, config):
        raise builders.BuildError("no model route is available: {'anthropic': 'credential unavailable'}")

    body = Body(home, clock=Clock(), builder=no_routes).open()
    assert body.builder is None and body.genesis.builder is None
    why = body.journal.replay("genesis.builder")[0].payload
    assert why["available"] is False and "credential unavailable" in why["why"]
    body.close()



def test_a_provider_policy_error_is_a_refusal_not_an_outage():
    class PolicyError(Exception):
        code = "content_policy_violation"

    class Declines:
        responses = NS(create=lambda **kw: (_ for _ in ()).throw(PolicyError("400 flagged by moderation")))

    other = FakeAnthropic("would have answered")
    router = models.ModelRouter([models.OpenAIRoute("k", client=Declines(), price=(1.0, 4.0)),
                                 models.AnthropicRoute("k", client=other)])
    with pytest.raises(models.Refusal):
        router.complete("sys", "user")
    assert other.calls == []                                                   # never re-asked elsewhere
    outage = models.ModelRouter([models.OpenAIRoute("k", client=FakeOpenAI(ConnectionError("503")), price=(1, 4)),
                                 models.AnthropicRoute("k", client=FakeAnthropic("ok"))])
    assert outage.complete("s", "u")["route"].startswith("anthropic")          # availability fallback still works


def test_configured_price_overrides_a_stale_builtin_price():
    stale = models.AnthropicRoute("k", model="claude-opus-5", client=FakeAnthropic("ok"))
    raised = models.AnthropicRoute("k", model="claude-opus-5", price=(10.0, 50.0), client=FakeAnthropic("ok"))
    assert raised.price == (10.0, 50.0) and stale.price != raised.price
    raised.complete("s", "u", budget_usd=0.10)
    assert raised.client.calls[0]["max_tokens"] * 50.0 / 1e6 <= 0.10           # bound follows the configured price
    unknown = models.AnthropicRoute("k", model="claude-future-9", client=FakeAnthropic("ok"))
    with pytest.raises(models.Unbounded):                                      # unknown price degrades safely
        unknown.complete("s", "u", budget_usd=0.10)
