"""Open-source mechanisms as construction supply (founder correction 2026-10-01, #144).

A mission needs a function GREG lacks (a shortest route, a maximum flow). Capability Genesis
does not hand-build it: it finds an installed open-source package, pins it on a Mechanism
Card (version, license, upstream, file digest), qualifies it in a no-network interpreter
against GREG's own oracle, and asks the founder to attach it. Every answer is accepted only
on GREG's certificate, which shares no code with the engine, so a lying engine is caught,
quarantined and replaced by a different package. Nothing is installed or downloaded.
"""
from __future__ import annotations

import json
import random

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg import genesis as genesis_mod  # noqa: E402
from greg import mechanisms, planner  # noqa: E402
from greg.body import Body, status  # noqa: E402
from greg.capabilities import CapabilityError, CapabilityRegistry  # noqa: E402
from greg.cognition import network  # noqa: E402
from greg.console import Console, render_home  # noqa: E402
from greg.templates import network_in_words, read_network_words  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402

ROUTE = "Warehouse to Hub: 4 miles. Hub to Store: 3. Warehouse to Store: 9. Shortest route from Warehouse to Store."
FLOW = ("Plant to North: 10. Plant to South: 5. North to Market: 4. South to Market: 8. North to South: 6. "
        "Maximum flow from Plant to Market.")


def candidate(function, distribution):
    return next(c for c in genesis_mod.CATALOG[function]["candidates"] if c.distribution == distribution)


def solve_with(function, distribution, params):
    c = candidate(function, distribution)
    dist = mechanisms.installed(c.distribution)
    card = mechanisms.card(c, function, dist)
    req = genesis_mod.CATALOG[function]["normalize"](params)
    [claim] = mechanisms.run(c, network.RUNNERS[c.runner], [req], location=card["location"], version=card["version"])
    return req, claim["result"]


def receipts(body):
    return [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
            if isinstance(r.payload["result"].get("output"), dict) and r.payload["result"]["output"].get("certified")]


def ticks(body, clock, n):
    out = []
    for _ in range(n):
        out.append(body.tick()["missions"][0])
        clock.advance(31)
    return out


# -- the Mechanism Card is read from what is installed -------------------------------------

def test_the_card_pins_version_license_upstream_and_files_from_installed_metadata():
    import importlib.metadata
    c = candidate("graph.shortest_path", "networkx")
    card = mechanisms.card(c, "graph.shortest_path", mechanisms.installed("networkx"))
    assert card["mode"] == "DEPEND" and card["version"] == importlib.metadata.version("networkx")
    assert card["license"] == "BSD-3-Clause" and "github.com/networkx/networkx" in card["upstream"]["source"]
    assert len(card["package_digest"]) == 64 and card["pinned_files"] > 10
    assert "did not download or install" in card["acquisition"] and "not detected" in card["limits"]
    scipy_card = mechanisms.card(candidate("graph.max_flow", "scipy"), "graph.max_flow", mechanisms.installed("scipy"))
    assert [d["distribution"] for d in scipy_card["common_mode"]] == ["numpy"]       # shared dependency disclosed
    assert scipy_card["common_mode"][0]["version"] == importlib.metadata.version("numpy")
    assert mechanisms.installed("no-such-distribution-greg") is None                 # absence is not an install


def test_an_engine_imported_from_anywhere_but_its_qualified_location_is_refused(tmp_path):
    c = candidate("graph.shortest_path", "networkx")
    card = mechanisms.card(c, "graph.shortest_path", mechanisms.installed("networkx"))
    req = network.normalize_shortest(read_network_words(ROUTE)[1])
    with pytest.raises(CapabilityError, match="not from the qualified location"):
        mechanisms.run(c, network.RUNNERS[c.runner], [req], location=str(tmp_path), version=card["version"])
    with pytest.raises(CapabilityError, match="reported version"):
        mechanisms.run(c, network.RUNNERS[c.runner], [req], location=card["location"], version="0.0.0")


# -- certificates: GREG's own proof, independent of the engine ------------------------------

def test_engine_answers_certify_and_a_suboptimal_or_false_claim_is_refuted():
    req, claim = solve_with("graph.shortest_path", "networkx", read_network_words(ROUTE)[1])
    answer = network.certify_shortest(req, claim)
    assert answer["distance"] == 7 and answer["path"] == ["Warehouse", "Hub", "Store"]
    lying = {"distances": {**claim["distances"], "Store": 9}, "predecessors": {**claim["predecessors"],
                                                                              "Store": "Warehouse"}}
    with pytest.raises(network.CertificateError, match="shorter path"):
        network.certify_shortest(req, lying)                         # a valid but longer route
    hidden = {"distances": {"Warehouse": 0, "Hub": 4}, "predecessors": {"Hub": "Warehouse"}}
    with pytest.raises(network.CertificateError, match="claimed unreachable"):
        network.certify_shortest(req, hidden)                        # a false "no route"
    with pytest.raises(network.CertificateError, match="differs from the weight of its own path"):
        network.certify_shortest(req, {**claim, "distances": {**claim["distances"], "Store": 6}})
    with pytest.raises(network.CertificateError, match="not in the graph"):
        network.certify_shortest(req, {**claim, "predecessors": {**claim["predecessors"], "Hub": "Store"}})
    loop = {"distances": {"Warehouse": 0, "Hub": 4, "Store": 7}, "predecessors": {"Hub": "Store", "Store": "Hub"}}
    with pytest.raises(network.CertificateError):
        network.certify_shortest(req, loop)


def test_a_flow_certifies_by_an_equal_cut_and_a_non_maximum_flow_is_refuted():
    req, claim = solve_with("graph.max_flow", "scipy", read_network_words(FLOW)[1])
    answer = network.certify_max_flow(req, claim)
    assert answer["value"] == 12 and answer["min_cut"]["capacity"] == 12
    smaller = {"value": 4, "flows": [["Plant", "North", 4], ["North", "Market", 4]]}
    with pytest.raises(network.CertificateError, match="augmenting path"):
        network.certify_max_flow(req, smaller)
    with pytest.raises(network.CertificateError, match="capacity"):
        network.certify_max_flow(req, {"value": 11, "flows": [["Plant", "South", 11], ["South", "Market", 11]]})
    with pytest.raises(network.CertificateError, match="conserved"):
        network.certify_max_flow(req, {"value": 4, "flows": [["Plant", "North", 4]]})
    with pytest.raises(network.CertificateError, match="claimed value"):
        network.certify_max_flow(req, {**claim, "value": 13})


@pytest.mark.parametrize("seed", range(25))
def test_greg_two_references_agree_on_random_graphs(seed):
    rng = random.Random(seed)
    names = [f"n{i}" for i in range(rng.randint(2, 9))]
    edges = [[rng.choice(names), rng.choice(names), rng.randint(0, 9)] for _ in range(rng.randint(0, 25))]
    req = network.normalize_shortest({"edges": edges, "nodes": names, "source": names[0], "directed": seed % 3 != 0})
    assert network.bellman_ford(req) == network.local_dijkstra(req)["distances"]
    flow = network.normalize_max_flow({"edges": edges, "nodes": names, "source": names[0], "sink": names[-1]}) \
        if len(names) > 1 else None
    assert network.min_cut_brute_force(flow) == network.local_edmonds_karp(flow)["value"]


@pytest.mark.parametrize("params, message", [
    ({"edges": [["a", "b", -1]], "source": "a"}, "negative weights"),
    ({"edges": [["a", "b", float("inf")]], "source": "a"}, "not finite"),
    ({"edges": [["a", "b", 1]], "source": "z"}, "not a node"),
    ({"edges": [["a", "b", True]], "source": "a"}, "not a number"),
])
def test_requests_outside_competence_are_refused_before_any_engine_runs_and_are_not_engine_faults(params, message):
    with pytest.raises(CapabilityError, match=message) as caught:
        network.normalize_shortest(params)
    manifest = type("M", (), {"provider": "installed:python:networkx==1", "binaries": ()})()
    assert not genesis_mod.is_capability_fault(manifest, f"capability refused: {caught.value}")
    with pytest.raises(CapabilityError, match="integers"):
        network.normalize_max_flow({"edges": [["a", "b", 1.5]], "source": "a", "sink": "b"})
    with pytest.raises(CapabilityError, match="differ"):
        network.normalize_max_flow({"edges": [["a", "b", 1]], "source": "a", "sink": "a"})


# -- qualification: both engines, both functions; mutants are caught --------------------------

@pytest.mark.parametrize("function", ["graph.shortest_path", "graph.max_flow"])
@pytest.mark.parametrize("distribution", ["networkx", "scipy"])
def test_each_installed_engine_qualifies_on_the_frozen_oracle_and_is_compared_with_a_local_baseline(
        tmp_path, function, distribution):
    c = candidate(function, distribution)
    card = mechanisms.card(c, function, mechanisms.installed(distribution))
    passed, report = genesis_mod.qualify_package(function, c, card, seed=20261001)
    assert passed, report["failures"]
    probe = report["scale_probe"]
    assert probe["certified"] and probe["agrees_with_local"] and probe["local_seconds"] >= 0
    assert report["cases"] >= 12 and "GREG" in report["oracle"]


def test_the_oracle_catches_a_runner_that_lets_sparse_matrices_sum_parallel_edges(tmp_path, monkeypatch):
    naive = network.RUNNERS["scipy.shortest_path"].replace("best[key] = min(best.get(key, w), w)",
                                                          "best[key] = best.get(key, 0) + w")
    monkeypatch.setitem(network.RUNNERS, "scipy.shortest_path", naive)
    c = candidate("graph.shortest_path", "scipy")
    passed, report = genesis_mod.qualify_package("graph.shortest_path", c,
                                       mechanisms.card(c, "graph.shortest_path", mechanisms.installed("scipy")), 7)
    assert not passed and "parallel-min" in {f["case"] for f in report["failures"]}


def test_the_oracle_caught_networkx_naming_the_source_its_own_predecessor(tmp_path, monkeypatch):
    """Negative evidence kept: the first runner took NetworkX's first tied predecessor, which across a
    zero-weight self-loop is the source itself. The frozen oracle's self-loop case refuted it."""
    first = network.RUNNERS["networkx.shortest_path"]
    original = first.split("    # NetworkX lists")[0] + \
        '    return {"distances": dist, "predecessors": {v: p[0] for v, p in pred.items() if p}}\n'
    monkeypatch.setitem(network.RUNNERS, "networkx.shortest_path", original)
    c = candidate("graph.shortest_path", "networkx")
    passed, report = genesis_mod.qualify_package("graph.shortest_path", c,
                                       mechanisms.card(c, "graph.shortest_path", mechanisms.installed("networkx")), 7)
    assert not passed and [f["case"] for f in report["failures"]] == ["self-loop"]


# -- the mission path: words -> deficit -> card -> founder attach -> certified answer ---------

def test_console_words_become_a_read_only_mission_that_needs_a_formed_capability():
    ctx = planner.PlannerContext(read_roots=(), capabilities=CapabilityRegistry().inventory(), repositories={})
    proposal = planner.template_route(ROUTE, ctx)
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:network-in-words"
    spec = proposal["spec"]
    assert spec["success_checks"][0]["sensor"]["function"] == "graph.shortest_path"   # no built-in: genesis forms it
    assert spec["light_cone"]["max_consequence_class"] == "read_only" and "auto_attach" not in spec
    unread = planner.template_route("Plant to North: 10. Bring snacks. Maximum flow from Plant to North.", ctx)
    assert unread["status"] == "NEEDS_INPUT" and "Bring snacks" in unread["questions"][0]
    assert planner.template_route(FLOW, ctx)["spec"]["strategies"][0]["function"] == "graph.max_flow"


def test_genesis_qualifies_an_installed_package_and_the_founder_attaches_it_before_any_answer(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=ROUTE)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 2)[-1]["state"] in ("BLOCKED", "WAITING")
        routes = [(e.payload["route"], e.payload["result"]) for e in body.journal.replay("genesis.route")]
        assert ("existing_project", next(r for k, r in routes if k == "existing_project")) in routes
        assert ("installed_package", "acquired") in routes
        [ask] = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "CAPABILITY_ATTACH"]
        [verified] = [c for c in ask["evidence"]["registered"] if c["state"] == "VERIFIED"]
        assert verified["mechanism"]["license"] == "BSD-3-Clause"
        assert verified["mechanism"]["qualification"]["failures"] == 0
        assert not receipts(body)                                       # nothing answered before the attach
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": verified["capability_id"]}))
        assert ticks(body, clock, 2)[0]["state"] == "ACHIEVED"
        answer = receipts(body)[-1]
        assert answer["distance"] == 7 and answer["path"] == ["Warehouse", "Hub", "Store"]
        assert answer["engine"].startswith("networkx ") and answer["authority_created"] is False
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"


def test_a_lying_engine_is_caught_by_the_certificate_quarantined_and_replaced_by_a_different_package(
        tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=ROUTE, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)                                   # honest qualification; read-only auto-attach
        assert body.registry.state["acquired.graph.shortest_path.networkx"] == "ATTACHED" and not receipts(body)
        lie = network.RUNNERS["networkx.shortest_path"].replace(
            '    return {"distances": dist,',
            '    dist = {**dist, "Store": 9}\n    pred["Store"] = ["Warehouse"]\n    return {"distances": dist,')
        monkeypatch.setitem(network.RUNNERS, "networkx.shortest_path", lie)   # the engine now lies in service
        states = [s["state"] for s in ticks(body, clock, 8)]
        assert "ACHIEVED" in states, states
        quarantined = [e.payload for e in body.journal.replay("capability.state") if e.payload["state"] == "QUARANTINED"]
        assert [q["capability_id"] for q in quarantined] == ["acquired.graph.shortest_path.networkx"]
        assert "certificate" in quarantined[0]["why"]
        skipped = [e.payload["result"] for e in body.journal.replay("genesis.route")
                   if e.payload["capability_id"] == "acquired.graph.shortest_path.networkx"]
        assert any("failed in service" in r for r in skipped)    # not re-admitted by the repair search
        answers = receipts(body)
        assert answers and all(a["distance"] == 7 for a in answers)   # no lie was ever accepted
        assert answers[-1]["engine"].startswith("scipy ")


def test_a_maximum_flow_question_closes_with_its_minimum_cut(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=FLOW, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        answer = receipts(body)[-1]
        assert answer["value"] == 12 and answer["min_cut"]["capacity"] == 12
        assert sorted(map(tuple, answer["min_cut"]["arcs"])) == [("North", "Market"), ("South", "Market")]


def test_a_qualified_package_survives_restart_and_is_quarantined_when_its_files_change(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=ROUTE, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 2)
    cid = "acquired.graph.shortest_path.networkx"
    with Body(home, clock=clock) as body:                                        # restart: pinned files unchanged
        assert body.registry.state[cid] == "ATTACHED"
    real = mechanisms.digest
    monkeypatch.setattr(mechanisms, "digest", lambda dist, prefixes: ("0" * 64, real(dist, prefixes)[1]))
    with Body(home, clock=clock) as body:                                        # restart after the files changed
        assert body.registry.state[cid] == "QUARANTINED"
        why = [e.payload["why"] for e in body.journal.replay("capability.state") if e.payload["state"] == "QUARANTINED"]
        assert why == ["pinned package files changed since qualification"]


def test_with_no_engine_installed_greg_asks_and_installs_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(mechanisms, "installed", lambda name: None)
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=ROUTE, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 2)[-1]["state"] in ("BLOCKED", "WAITING")
        results = [e.payload["result"] for e in body.journal.replay("genesis.route")
                   if e.payload["route"] == "installed_package"]
        assert results == ["networkx not installed (GREG installs nothing; you may)",
                           "scipy not installed (GREG installs nothing; you may)"]
        assert not body.registry.by_function("graph.shortest_path")
        [ask] = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "CAPABILITY_ATTACH"]
        assert any("install software" in o["option"] for o in ask["options"])


def test_the_console_attaches_only_a_verified_candidate_an_open_ask_names(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=ROUTE)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 2)
    console = Console(home, key=key)
    page = render_home(console).decode()
    assert "Attach acquired.graph.shortest_path.networkx" in page and "BSD-3-Clause" in page
    [ask] = [r for r in status(home)["decisions_required"] if r["kind"] == "CAPABILITY_ATTACH"]
    assert "only records your answer" in ask["answer_effect"]
    with pytest.raises(ValueError):
        console.attach(ask["request_id"], "fs.write")                          # not a candidate of this ask
    path = console.attach(ask["request_id"], "acquired.graph.shortest_path.networkx")
    assert json.loads(path.read_text())["kind"] == "CAPABILITY_ATTACH"
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 2)]
