"""Least-cost delivery in words, from an installed open-source engine, proved by GREG.

Fifth family on the open-source genesis route (#144). NetworkX's network simplex and OR-Tools'
SimpleMinCostFlow are untrusted: GREG checks capacities, balances and that no rerouting is cheaper
(no negative residual cycle), and proves "no plan meets every demand" by Gale's condition.
"""
from __future__ import annotations

import pytest

pytest.importorskip("networkx")
pytest.importorskip("ortools")

from greg import genesis as genesis_mod  # noqa: E402
from greg import mechanisms, planner  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.capabilities import CapabilityError, CapabilityRegistry  # noqa: E402
from greg.cognition import flow  # noqa: E402
from greg.templates import delivery_in_words, read_delivery_words  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402

WORDS = ("Plant sends 30 crates. Depot sends 10. Store needs 25. Shop needs 15. Plant to Store: 20 at 4. "
         "Plant to Shop at 7. Depot to Store at 2. Depot to Shop: 10 at 3. Store to Shop: 5 at 1. Cheapest delivery.")
SHORT = "Plant sends 5. Store needs 5. Plant to Store: 3 at 2. Cheapest delivery."


def candidate(distribution):
    return next(c for c in genesis_mod.CATALOG["flow.min_cost"]["candidates"] if c.distribution == distribution)


def solve_with(distribution, params):
    c = candidate(distribution)
    card = mechanisms.card(c, "flow.min_cost", mechanisms.installed(distribution))
    req = flow.normalize_min_cost(params)
    [claim] = mechanisms.run(c, flow.RUNNERS[c.runner], [req], location=card["location"], version=card["version"])
    return req, claim["result"]


def ticks(body, clock, n):
    out = []
    for _ in range(n):
        out.append(body.tick()["missions"][0])
        clock.advance(31)
    return out


def certified_answers(body):
    return [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
            if isinstance(r.payload["result"].get("output"), dict) and r.payload["result"]["output"].get("certified")]


@pytest.mark.parametrize("distribution", ["networkx", "ortools"])
def test_each_installed_engine_qualifies_on_greg_oracle_and_at_scale(distribution):
    c = candidate(distribution)
    card = mechanisms.card(c, "flow.min_cost", mechanisms.installed(distribution))
    passed, report = genesis_mod.qualify_package("flow.min_cost", c, card, seed=20261013)
    assert passed, report["failures"]
    assert report["scale_probe"]["certified"] and report["scale_probe"]["agrees_with_local"]


@pytest.mark.parametrize("distribution", ["networkx", "ortools"])
def test_both_engines_give_a_certified_least_cost_plan(distribution):
    req, claim = solve_with(distribution, read_delivery_words(WORDS))
    answer = flow.certify_min_cost(req, claim)
    assert answer["status"] == "optimal" and answer["total_cost"] == 175
    assert set(answer["certificate"]["site_prices"]) == {"Depot", "Plant", "Shop", "Store"}


@pytest.mark.parametrize("distribution", ["networkx", "ortools"])
def test_no_plan_is_proved_by_naming_the_sites_whose_supply_cannot_get_out(distribution):
    req, claim = solve_with(distribution, read_delivery_words(SHORT))
    assert claim["status"] == "infeasible"
    answer = flow.certify_min_cost(req, claim)
    assert answer["sites"] == ["Plant"] and answer["net_supply"] == 5 and answer["capacity_leaving"] == 3
    assert answer["most_deliverable"] == 3


def test_a_dearer_plan_an_overload_an_imbalance_and_a_false_no_plan_are_refuted():
    req = flow.normalize_min_cost(read_delivery_words(WORDS))
    best = [20, 10, 5, 5, 0]
    assert flow.certify_min_cost(req, {"status": "optimal", "flows": best})["total_cost"] == 175
    for flows, why in [([15, 15, 10, 0, 0], "cheaper rerouting"),           # valid, 185
                       ([25, 5, 0, 10, 0], "within capacity"),               # Plant to Store holds 20
                       ([20, 10, 5, 4, 0], "supply is"),
                       ([20, 10, 5], "one flow per arc")]:
        with pytest.raises(flow.CertificateError, match=why):
            flow.certify_min_cost(req, {"status": "optimal", "flows": flows})
    with pytest.raises(flow.CertificateError, match="but one does"):
        flow.certify_min_cost(req, {"status": "infeasible"})


def test_a_negative_cost_cycle_must_be_used_up_to_its_capacity():
    req = flow.normalize_min_cost({"arcs": [["a", "b", 2, -2], ["b", "a", 1, 1]], "supplies": {}})
    with pytest.raises(flow.CertificateError, match="cheaper rerouting"):
        flow.certify_min_cost(req, {"status": "optimal", "flows": [0, 0]})
    assert flow.certify_min_cost(req, {"status": "optimal", "flows": [1, 1]})["total_cost"] == -1


@pytest.mark.parametrize("seed", range(4))
def test_greg_oracle_and_an_engine_agree_on_random_networks(seed):
    for case in flow.oracle_min_cost(seed)[len(flow.FIXED_MIN_COST):]:
        req, claim = solve_with("ortools", case["input"])
        assert flow.judge_min_cost(flow.certify_min_cost(req, claim), case["expected"])


@pytest.mark.parametrize("params, message", [
    ({"arcs": [["a", "b", 3, 1]], "supplies": {"a": 2, "b": -1}}, "must balance"),
    ({"arcs": [["a", "a", 3, 1]], "supplies": {}}, "goes nowhere"),
    ({"arcs": [["a", "b", 2.5, 1]], "supplies": {}}, "whole number"),
    ({"arcs": [["a", "b", -1, 1]], "supplies": {}}, "nonnegative"),
    ({"arcs": [["a", "b", 1, 0.1234567]], "supplies": {}}, "six decimal places"),
    ({"arcs": [], "supplies": {}}, "1-5000"),
])
def test_networks_outside_competence_are_refused_before_any_engine_runs(params, message):
    with pytest.raises(CapabilityError, match=message):
        flow.normalize_min_cost(params)


def test_words_become_a_read_only_delivery_mission_and_unread_words_stop_it():
    ctx = planner.PlannerContext(read_roots=(), capabilities=CapabilityRegistry().inventory(), repositories={})
    proposal = planner.template_route(WORDS, ctx)
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:delivery-in-words"
    assert proposal["spec"]["light_cone"]["max_consequence_class"] == "read_only"
    unread = planner.template_route("Plant sends 5. Store needs 5. Plant to Store at 2. Be quick. Cheapest delivery.",
                                    ctx)
    assert unread["status"] == "NEEDS_INPUT" and "Be quick" in unread["questions"][0]


def test_a_delivery_mission_closes_on_a_certified_plan_from_a_formed_capability(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", delivery_in_words(text=WORDS, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        answer = certified_answers(body)[-1]
        assert answer["total_cost"] == 175 and answer["authority_created"] is False
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"


def test_an_engine_that_falsely_says_no_plan_exists_is_quarantined_and_replaced(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", delivery_in_words(text=WORDS, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)
        assert body.registry.state["acquired.flow.min_cost.networkx"] == "ATTACHED"
        lie = flow.RUNNERS["networkx.min_cost"].replace(
            "def solve(req):\n", 'def solve(req):\n    return {"status": "infeasible"}\n', 1)
        monkeypatch.setitem(flow.RUNNERS, "networkx.min_cost", lie)
        states = [s["state"] for s in ticks(body, clock, 8)]
        assert "ACHIEVED" in states, states
        [quarantined] = [e.payload for e in body.journal.replay("capability.state")
                         if e.payload["state"] == "QUARANTINED"]
        assert quarantined["capability_id"] == "acquired.flow.min_cost.networkx"
        answers = certified_answers(body)
        assert answers and all(a["status"] == "optimal" for a in answers)
        assert answers[-1]["engine"].startswith("ortools ") and answers[-1]["total_cost"] == 175


def test_random_seed_examples_are_reproducible():
    assert flow.oracle_min_cost(3) == flow.oracle_min_cost(3)
