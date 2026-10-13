"""The cheapest network connecting every site, in words, from an open-source engine, proved by GREG.

Fourth family on the open-source genesis route (#144). NetworkX and SciPy compute the minimum
spanning forest; GREG accepts it only on the cycle property, checked in exact arithmetic.
"""
from __future__ import annotations

import random

import pytest

pytest.importorskip("scipy")
pytest.importorskip("networkx")

from greg import genesis as genesis_mod  # noqa: E402
from greg import mechanisms, planner  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.capabilities import CapabilityError, CapabilityRegistry  # noqa: E402
from greg.cognition import spanning  # noqa: E402
from greg.templates import network_in_words, read_network_words  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402

WORDS = ("Depot and Mill: 4. Mill and Farm: 3. Depot and Farm: 9. Farm to School: 2. "
         "Cheapest network connecting all sites.")


def candidate(distribution):
    return next(c for c in genesis_mod.CATALOG["graph.spanning_tree"]["candidates"] if c.distribution == distribution)


def solve_with(distribution, params):
    c = candidate(distribution)
    card = mechanisms.card(c, "graph.spanning_tree", mechanisms.installed(distribution))
    req = spanning.normalize_spanning(params)
    [claim] = mechanisms.run(c, spanning.RUNNERS[c.runner], [req], location=card["location"], version=card["version"])
    return req, claim["result"]


def ticks(body, clock, n):
    out = []
    for _ in range(n):
        out.append(body.tick()["missions"][0])
        clock.advance(31)
    return out


@pytest.mark.parametrize("distribution", ["networkx", "scipy"])
def test_each_installed_engine_qualifies_on_greg_oracle_and_at_the_size_limit(distribution):
    c = candidate(distribution)
    card = mechanisms.card(c, "graph.spanning_tree", mechanisms.installed(distribution))
    passed, report = genesis_mod.qualify_package("graph.spanning_tree", c, card, seed=20261013)
    assert passed, report["failures"]
    assert report["scale_probe"]["certified"] and report["scale_probe"]["nodes"] == spanning.MAX_NODES
    assert report["scale_probe"]["agrees_with_local"]


@pytest.mark.parametrize("distribution", ["networkx", "scipy"])
def test_both_engines_give_the_same_certified_network(distribution):
    _, params = read_network_words(WORDS)
    req, claim = solve_with(distribution, params)
    answer = spanning.certify_spanning(req, claim)
    assert answer["total"] == 9 and answer["connected"]
    assert {frozenset(e[:2]) for e in answer["edges"]} == {frozenset(p) for p in
                                                          [("Depot", "Mill"), ("Farm", "Mill"), ("Farm", "School")]}


@pytest.mark.parametrize("distribution", ["networkx", "scipy"])
def test_zero_and_negative_weights_survive_scipys_zero_means_no_edge(distribution):
    req, claim = solve_with(distribution, {"edges": [["a", "b", 0], ["b", "c", -3], ["a", "c", 1], ["c", "d", 0]]})
    assert spanning.certify_spanning(req, claim)["total"] == -3


def test_a_heavier_network_a_cycle_a_gap_and_an_invented_link_are_refuted():
    req = spanning.normalize_spanning(read_network_words(WORDS)[1])
    good = [["Depot", "Mill", 4], ["Mill", "Farm", 3], ["Farm", "School", 2]]
    assert spanning.certify_spanning(req, {"edges": good})["total"] == 9
    for edges, why in [([["Depot", "Farm", 9], ["Mill", "Farm", 3], ["Farm", "School", 2]], "cheaper than"),
                       (good + [["Depot", "Farm", 9]], "closes a cycle"),
                       (good[:2], "not by the forest"),
                       ([["Depot", "School", 1], ["Mill", "Farm", 3], ["Farm", "School", 2]], "not a link")]:
        with pytest.raises(spanning.CertificateError, match=why):
            spanning.certify_spanning(req, {"edges": edges})


def test_two_separate_networks_are_reported_as_a_forest():
    req = spanning.normalize_spanning({"edges": [["a", "b", 1], ["c", "d", 2]], "nodes": ["a", "b", "c", "d", "z"]})
    answer = spanning.certify_spanning(req, {"edges": [["a", "b", 1], ["c", "d", 2]]})
    assert answer["components"] == 3 and not answer["connected"]


@pytest.mark.parametrize("seed", range(4))
def test_greg_oracle_and_an_engine_agree_on_random_networks(seed):
    rng = random.Random(seed)
    for _ in range(6):
        names = [f"s{i}" for i in range(rng.randint(2, 7))]
        params = {"nodes": names, "edges": [[rng.choice(names), rng.choice(names), rng.randint(-5, 20)]
                                            for _ in range(rng.randint(0, 10))]}
        req, claim = solve_with("scipy", params)
        assert spanning.judge_spanning(spanning.certify_spanning(req, claim), spanning.brute_force(req))


@pytest.mark.parametrize("params, message", [
    ({"edges": [["a", "b", float("inf")]]}, "finite"),
    ({"edges": [["a", "b", 2e9]]}, "1e9"),
    ({"edges": [["a", "b"]]}, "must be"),
    ({"edges": [["a!", "b", 1]]}, "site name"),
])
def test_networks_outside_competence_are_refused_before_any_engine_runs(params, message):
    with pytest.raises(CapabilityError, match=message):
        spanning.normalize_spanning(params)


def test_words_become_a_read_only_network_mission():
    ctx = planner.PlannerContext(read_roots=(), capabilities=CapabilityRegistry().inventory(), repositories={})
    proposal = planner.template_route(WORDS, ctx)
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:network-in-words"
    assert proposal["spec"]["strategies"][0]["function"] == "graph.spanning_tree"


def test_a_network_mission_closes_on_a_certified_answer_from_a_formed_capability(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=WORDS, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        answers = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                   if isinstance(r.payload["result"].get("output"), dict) and r.payload["result"]["output"].get("certified")]
        assert answers[-1]["total"] == 9 and answers[-1]["authority_created"] is False
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"
