"""The founder asks a portfolio question in plain words and gets a certified answer (selection.closure).

"Which offers should I build?" is the decision a founder makes most often, and it is the one a greedy
rule gets wrong when offers share a costly prerequisite. The controlled language is read without a
model; a sentence it cannot read stops the plan. The planner turns the words into a read-only mission
whose answer Capability Genesis constructs (Picard's reduction onto a max-flow engine it qualifies),
and each formed capability waits for the founder's own attach before any answer exists.
"""
from __future__ import annotations

import pytest

from greg import planner, recombine, templates
from greg.capabilities import CapabilityRegistry

STORY = ("Which offers should I build? Offer1 earns 5. Offer2 earns $6. Platform costs 6. Audit costs 3. "
         "Pilot earns 3. Lab costs 5. Offer1 needs Platform. Offer2 needs Platform and Audit. Pilot requires Lab.")
PARAMS = {"items": [{"id": "Offer1", "value": 5}, {"id": "Offer2", "value": 6}, {"id": "Platform", "value": -6},
                    {"id": "Audit", "value": -3}, {"id": "Pilot", "value": 3}, {"id": "Lab", "value": -5}],
          "requires": [["Offer1", "Platform"], ["Offer2", "Platform"], ["Offer2", "Audit"], ["Pilot", "Lab"]]}


def ctx():
    return planner.PlannerContext(read_roots=(), capabilities=CapabilityRegistry().inventory(), repositories={})


def test_the_words_read_exactly_into_items_and_prerequisites():
    assert templates.read_portfolio_words(STORY) == PARAMS
    lenient = ("Ads earns 1,200 dollars a month\nSite costs $900\nCRM costs 250 USD\n"
               "Ads depends on Site, CRM and Copy\nCopy is worth 0")
    p = templates.read_portfolio_words(lenient)
    assert {i["id"]: i["value"] for i in p["items"]} == {"Ads": 1200, "Site": -900, "CRM": -250, "Copy": 0}
    assert p["requires"] == [["Ads", "Site"], ["Ads", "CRM"], ["Ads", "Copy"]]


@pytest.mark.parametrize("text, message", [
    ("Offer1 earns 5. Bring snacks. Platform costs 2. Offer1 needs Platform.", "could not read: 'Bring snacks'"),
    ("Offer1 earns 5. Offer1 needs Lab.", "Lab is needed but never given a value"),
    ("Offer1 earns 1.5. Lab costs 1. Offer1 needs Lab.", "whole numbers"),
    ("Offer1 earns 5. Offer1 costs 2. Offer1 needs Offer1.", "given a value twice"),
    ("Lab costs 3. A costs 1. A needs Lab.", "at least one item that earns"),
    ("Which? Pick one? Offer1 earns 5. Lab costs 1. Offer1 needs Lab.", "one portfolio question"),
])
def test_a_sentence_greg_cannot_read_or_an_incomplete_portfolio_stops_the_plan(text, message):
    with pytest.raises(ValueError, match=message):
        templates.read_portfolio_words(text)


def test_the_planner_turns_the_words_into_a_read_only_constructed_mission():
    proposal = planner.template_route(STORY, ctx())
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:portfolio-in-words"
    spec = proposal["spec"]
    step = spec["strategies"][0]
    assert step["function"] == "selection.closure" and step["params"] == PARAMS
    assert spec["founder_expression"] == STORY and spec["mission_id"].startswith("m:portfolio-")
    assert spec["light_cone"]["max_consequence_class"] == "read_only" and spec["light_cone"]["budget_usd"] == 0
    assert "auto_attach" not in spec                                   # the founder attaches what Genesis forms
    assert recombine.REDUCTIONS["selection.closure"].normalize(step["params"])
    unread = planner.template_route("Offer1 earns 5. Hire Bob. Platform costs 6. Offer1 needs Platform.", ctx())
    assert unread["status"] == "NEEDS_INPUT" and "Hire Bob" in unread["questions"][0]


def test_the_portfolio_route_leaves_the_other_controlled_languages_alone():
    route = "Plant to Hub: 4. Hub to North: 3. Shortest route from Plant to North."
    plan = "Maximize 3 chairs + 5 tables. 2 chairs + 4 tables <= 40. chairs <= 10."
    assert planner.template_route(route, ctx())["origin"] == "template:network-in-words"
    assert planner.template_route(plan, ctx())["origin"] == "template:plan-in-words"


def test_from_the_founders_words_to_a_certified_portfolio_through_two_attaches(tmp_path):
    pytest.importorskip("networkx")
    pytest.importorskip("scipy")
    from greg.body import Body
    from tests.greg_fixtures import Clock, drop, make_body, signed
    home, key, body_id, _ = make_body(tmp_path)
    spec = planner.template_route(STORY, ctx())["spec"]
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()

    def run(n):
        with Body(home, clock=clock) as body:
            body.boot()
            for _ in range(n):
                body.tick()
                clock.advance(31)
            return dict(body.registry.state), body.engine.book.missions[spec["mission_id"]].status

    state, status = run(3)
    engine = next(c for c, s in state.items() if c.startswith("acquired.graph.max_flow."))
    assert state[engine] == "VERIFIED" and status != "ACHIEVED"          # acquired, never attached by GREG
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": engine}))
    state, status = run(3)
    construction = next(c for c, s in state.items() if c.startswith("composed.selection.closure."))
    assert state[construction] == "VERIFIED" and status != "ACHIEVED"    # formed over it; still yours to attach
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": construction}))
    state, status = run(3)
    assert status == "ACHIEVED"
    with Body(home, clock=clock) as body:
        body.boot()
        [answer] = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and r.payload["result"]["output"].get("composed_of") == ["selection-via-maxflow"]][-1:]
    assert answer["certified"] and answer["chosen"] == ["Audit", "Offer1", "Offer2", "Platform"]
    assert answer["profit"] == 2 and answer["why_left_out"] == {"Pilot": [["Lab", 3]]}
    assert answer["authority_created"] is False
