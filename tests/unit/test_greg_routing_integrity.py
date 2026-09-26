"""Routing integrity: fallback may improve availability; it may never bypass a policy decision.

Reproduced first on #114 at 14b44e5: OpenAI reports a policy flag as HTTP 400
``invalid_prompt`` ("your prompt was flagged as potentially violating our usage policy").
The router treated it as an outage, asked the next vendor the same thing, and that
vendor's answer came back as the draft. It also demoted the flagging route as "failed".

Here the client raises errors shaped like the SDKs' ``APIStatusError`` (``status_code``,
``body``, message), so these run where the optional SDKs are not installed (CI).
``test_greg_routing_integrity_sdk.py`` repeats the decisive cases through the real
``openai`` and ``anthropic`` clients against an in-process HTTP stub when they are present.
No network, no key, no spend.
"""
import json

from types import SimpleNamespace as NS

import pytest

from greg import builders, models, planner
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_genesis_builder import GOOD, _mission
from tests.unit.test_greg_interface import GOOD as GOOD_MISSION, inventory

FLAGGED = {"error": {"message": "Invalid prompt: your prompt was flagged as potentially violating our usage policy. "
                                "Please try again with a different prompt.",
                     "type": "invalid_request_error", "param": None, "code": "invalid_prompt"}}


class StatusError(Exception):
    """Shaped like openai/anthropic ``APIStatusError``: status_code, body, and the SDK's message format."""

    def __init__(self, status, body):
        super().__init__(f"Error code: {status} - {body}")
        self.status_code, self.body = status, body.get("error", body)


def openai_client(status, body):
    def create(**kw):
        raise StatusError(status, body)
    return NS(responses=NS(create=create))


class Witness:
    """A second vendor that must never be asked when the first one's policy said no."""
    provider, name = "witness", "witness:model"

    def __init__(self, text="answer from a second vendor"):
        self.text, self.calls = text, 0

    def complete(self, system, user, *, budget_usd=None):
        self.calls += 1
        return {"text": self.text, "cost_usd": 0.0, "served_model": "witness-1"}


def test_a_provider_policy_flag_is_a_refusal_and_is_never_shopped_to_another_vendor():
    flagged = models.OpenAIRoute("sk-test", model="gpt-x", price=(2.0, 12.0), client=openai_client(400, FLAGGED))
    witness = Witness()
    router = models.ModelRouter([flagged, witness])
    with pytest.raises(models.Refusal) as info:
        router.complete("sys", "the same request")
    assert info.value.kind == models.PROVIDER_POLICY_REFUSAL
    assert witness.calls == 0
    assert router.last["tried"] == [{"route": "openai:gpt-x", "outcome": "refused",
                                     "class": "provider_policy_refusal", "why": router.last["tried"][0]["why"]}]
    assert router.health["openai:gpt-x"]["consecutive_failures"] == 0          # a verdict is not an outage


@pytest.mark.parametrize("status, body, kind", [
    (429, {"error": {"message": "Rate limit reached", "type": "requests", "code": "rate_limit_exceeded"}},
     models.TRANSIENT),
    (503, {"error": {"message": "overloaded", "type": "server_error", "code": None}}, models.TRANSIENT),
    (401, {"error": {"message": "Incorrect API key", "type": "invalid_request_error", "code": "invalid_api_key"}},
     models.AUTH),
    (404, {"error": {"message": "The model `gpt-x` does not exist", "type": "invalid_request_error",
                     "code": "model_not_found"}}, models.UNAVAILABLE),
    (400, {"error": {"message": "Unsupported parameter: 'max_output_tokens'", "type": "invalid_request_error",
                     "code": "unsupported_parameter"}}, models.INVALID_REQUEST),
])
def test_availability_failures_are_classified_and_still_fail_over(status, body, kind):
    route = models.OpenAIRoute("sk-test", model="gpt-x", price=(2.0, 12.0), client=openai_client(status, body))
    witness = Witness()
    router = models.ModelRouter([route, witness])
    result = router.complete("sys", "user")
    assert witness.calls == 1 and result["route"] == "witness:model" and result["served_model"] == "witness-1"
    assert result["tried"][0]["outcome"] == "failed" and result["tried"][0]["class"] == kind


def test_the_planner_reports_the_refusal_class_and_proposes_nothing():
    ctx = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={})
    witness = Witness(json.dumps(GOOD_MISSION))
    router = models.ModelRouter([models.OpenAIRoute("sk-test", model="gpt-x", price=(2.0, 12.0),
                                                    client=openai_client(400, FLAGGED)), witness])
    proposal = planner.propose("Tell me if my kernel checkout gets dirty", ctx, transport=router)
    assert proposal["status"] == "REFUSED" and proposal["refusal_class"] == "provider_policy_refusal"
    assert "spec" not in proposal and witness.calls == 0
    assert proposal["routes_tried"][0]["class"] == "provider_policy_refusal"


def test_the_signed_mission_names_the_model_the_provider_actually_served():
    ctx = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={})
    down = models.OpenAIRoute("sk-test", model="gpt-x", price=(2.0, 12.0),
                              client=openai_client(503, {"error": {"message": "down", "type": "server_error"}}))
    router = models.ModelRouter([down, Witness(json.dumps(GOOD_MISSION))])
    proposal = planner.propose("Tell me if my kernel checkout gets dirty", ctx, transport=router)
    assert proposal["status"] == "PROPOSED", proposal
    provenance = proposal["spec"]["provenance"]
    assert provenance["model"] == "witness:model" and provenance["served_model"] == "witness-1"
    assert provenance["routes_tried"][0] == {"route": "openai:gpt-x", "outcome": "failed", "class": "transient",
                                             "why": provenance["routes_tried"][0]["why"]}


def test_genesis_escalates_a_policy_refused_build_instead_of_asking_another_vendor(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))
    witness = Witness("```python\n" + GOOD + "```")

    def factory(secrets, config):
        return builders.ModelBuilder(models.ModelRouter([
            models.OpenAIRoute("sk-test", model="gpt-x", price=(1.0, 4.0), client=openai_client(400, FLAGGED)),
            witness]))

    clock = Clock()
    body = Body(home, clock=clock, builder=factory).open()
    body.boot()
    states = []
    for _ in range(3):
        clock.advance(30)
        states.append(body.tick()["missions"][0]["state"])
    assert witness.calls == 0 and "ACHIEVED" not in states
    assert not body.journal.replay("capability.registered")
    routes = [e.payload for e in body.journal.replay("genesis.route")]
    assert any("provider policy rejected" in r["result"] for r in routes)
    assert routes[-1]["route"] == "founder" and routes[-1]["result"] == "escalated"
    recorded = [e.payload for e in body.journal.replay("model.route")]
    assert recorded and recorded[0]["outcome"] == "refused" and recorded[0]["class"] == "provider_policy_refusal"
    body.close()
