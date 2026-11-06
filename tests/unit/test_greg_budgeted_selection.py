"""Portfolio under a spending cap: selection.budgeted, constructed over selection.closure in rounds.

A cap on what the costs may total turns the best closure into a precedence-constrained knapsack
(NP-hard), so one cut no longer answers it. GREG constructs a branch-and-bound whose every node is a
closure problem the qualified max-flow engine answers with a funding certificate, and accepts the
result only when its own check of the whole search tree, from the original items, proves that no
plan within the cap earns more.
"""
from __future__ import annotations

import copy

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg import planner, recombine, templates  # noqa: E402
from greg.capabilities import CapabilityRegistry  # noqa: E402
from greg.cognition import network  # noqa: E402
from greg.genesis import CATALOG  # noqa: E402

FLIP = {"items": [{"id": "Big", "value": 9}, {"id": "Plant", "value": -7}, {"id": "Small1", "value": 3},
                  {"id": "Small2", "value": 3}, {"id": "Kit", "value": -2}],
        "requires": [["Big", "Plant"], ["Small1", "Kit"], ["Small2", "Kit"]], "budget": 5}
FLIP_WORDS = ("Which should I build? Big earns 9. Plant costs 7. Small1 earns 3. Small2 earns 3. Kit costs 2. "
              "Big needs Plant. Small1 needs Kit. Small2 needs Kit. Spend at most 5.")


def _local_flow(params):
    import networkx as nx                     # test-only: the body never imports an engine in-process
    req = network.normalize_max_flow(params)
    g = nx.DiGraph()
    g.add_nodes_from(req["nodes"])
    for u, v, c in req["arcs"]:
        g.add_edge(u, v, capacity=c)
    value, flows = nx.maximum_flow(g, req["source"], req["sink"])
    return {"flows": [[u, v, x] for u, out in flows.items() for v, x in out.items() if x], "value": value}


def closure(request):
    p = recombine.normalize_selection(request)
    raw = recombine.direct_selection(p)
    if raw is None:
        enc = recombine.encode_selection(p)
        raw = recombine.decode_selection(p, network.certify_max_flow(network.normalize_max_flow(enc), _local_flow(enc)))
    return recombine.certify_selection(p, raw)


def search(params):
    p = recombine.normalize_budgeted(params)
    history = []
    while requests := recombine.encode_budgeted(p, history):
        history += [(r, closure(r)) for r in requests]
    return p, recombine.decode_budgeted(p, history)


def test_a_cap_flips_the_choice_and_the_proof_tree_says_why():
    p, raw = search(FLIP)
    answer = recombine.certify_budgeted(p, raw)
    # Uncapped, Big and both smalls earn 6 but spend 9; within 5 only the Kit plan fits: 3 + 3 - 2 = 4.
    assert answer["chosen"] == ["Kit", "Small1", "Small2"] and answer["profit"] == 4
    assert answer["spend"] == 2 and answer["unspent"] == 3 and answer["why_left_out"] == {"Big": ["Plant"]}
    assert answer["proof_nodes"] == 3 and answer["profit"] == recombine.budgeted_brute_force(p)


def _refuted(p, raw, match):
    with pytest.raises(recombine.ReductionError, match=match):
        recombine.certify_budgeted(p, raw)


def test_the_certificate_refutes_overspending_unclosed_and_unproved_plans():
    p, raw = search(FLIP)
    _refuted(p, {**raw, "chosen": ["Big", "Plant"], "profit": 2}, "above the budget")
    _refuted(p, {**raw, "chosen": ["Small1"], "profit": 3}, "without what it requires")
    _refuted(p, {**raw, "chosen": [], "profit": 0}, "earns more than the answer")       # a cheaper plan is claimed
    cut = copy.deepcopy(raw)
    assert cut["tree"]["on"] == "Plant" and cut["tree"]["children"][0]["kind"] == "infeasible"
    cut["tree"]["children"][1] = {"in": [], "out": ["Plant"], "kind": "bounded"}        # a branch never explored
    _refuted(p, cut, "does not meet the bound")
    lied = copy.deepcopy(raw)
    lied["tree"]["children"][1]["funding"] = []                                          # a bound with no proof
    _refuted(p, lied, "does not meet the bound")
    forged = copy.deepcopy(raw)
    forged["tree"]["children"][0] = {"in": ["Plant"], "out": [], "kind": "bounded"}     # a real branch, closed falsely
    _refuted(p, forged, "not closed as such")
    skipped = copy.deepcopy(raw)
    skipped["tree"]["children"] = [skipped["tree"]["children"][0], skipped["tree"]["children"][0]]
    _refuted(p, skipped, "does not split its parent")
    hidden = copy.deepcopy(raw)
    hidden["tree"]["children"][1]["kind"] = "bounded"                                    # its plan fits and earns 4
    _refuted(p, {**hidden, "chosen": [], "profit": 0}, "closed by its bound can earn more")
    vague = copy.deepcopy(raw)
    vague["tree"]["kind"] = "trust me"
    _refuted(p, vague, "proves nothing")


def test_the_budgeted_oracle_agrees_with_the_certified_search_on_seeded_cases():
    for seed in range(15):
        for case in recombine.oracle_budgeted(seed):
            p, raw = search(case["input"])
            assert recombine.judge_budgeted(recombine.certify_budgeted(p, raw), case["expected"]), (seed, case["name"])


def test_the_chain_reaches_the_engine_through_the_closure_and_only_a_head_searches_in_rounds():
    path, engine = recombine.chain("selection.budgeted", CATALOG)
    assert [r.reduction_id for r in path] == ["budgeted-selection-via-closure", "selection-via-maxflow"]
    assert engine == "graph.max_flow"
    nested = {"x.outer": recombine.Reduction("outer", "x.outer", "selection.budgeted", "", {}, *([None] * 7),
                                             "", {}),
              **recombine.REDUCTIONS}
    assert recombine.chain("x.outer", CATALOG, nested) is None


def test_a_request_too_large_to_prove_is_refused_before_any_claim():
    items = [{"id": f"O{k}", "value": 5} for k in range(30)] + [{"id": f"C{k}", "value": -4} for k in range(30)]
    requires = [[f"O{k}", f"C{k}"] for k in range(30)] + [[f"O{k}", f"C{(k + 1) % 30}"] for k in range(30)]
    p = recombine.normalize_budgeted({"items": items, "requires": requires, "budget": 31})
    with pytest.raises(Exception, match="more than 2048 closure problems"):
        history = []
        while requests := recombine.encode_budgeted(p, history):
            history += [(r, closure(r)) for r in requests]


def test_a_budget_sentence_turns_the_portfolio_into_the_capped_construction():
    proposal = planner.template_route(FLIP_WORDS, planner.PlannerContext(
        read_roots=(), capabilities=CapabilityRegistry().inventory(), repositories={}))
    step = proposal["spec"]["strategies"][0]
    assert step["function"] == "selection.budgeted" and step["params"] == FLIP
    assert proposal["spec"]["light_cone"]["capabilities"] == ["composed.selection.budgeted.*",
                                                              "acquired.graph.max_flow.*"]
    for words, message in [(FLIP_WORDS + " Budget: 6.", "budget once"),
                           (FLIP_WORDS.replace("at most 5", "at most 5.5"), "whole number")]:
        with pytest.raises(ValueError, match=message):
            templates.read_portfolio_words(words)
    assert templates.read_portfolio_words(FLIP_WORDS.replace("Spend at most 5", "I can spend $5"))["budget"] == 5


def test_a_signed_capped_portfolio_constructs_the_capability_and_closes_with_its_proof(tmp_path):
    from greg.body import Body
    from tests.greg_fixtures import Clock, drop, make_body, signed
    home, key, body_id, _ = make_body(tmp_path)
    spec = templates.portfolio_in_words(text=FLIP_WORDS, auto_attach=True)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(4):
            body.tick()
            clock.advance(31)
        assert body.engine.book.missions[spec["mission_id"]].status == "ACHIEVED"
        [answer] = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and r.payload["result"]["output"].get("composed_of") == ["budgeted-selection-via-closure",
                                                                             "selection-via-maxflow"]][-1:]
        assert answer["certified"] and answer["chosen"] == ["Kit", "Small1", "Small2"] and answer["profit"] == 4
        assert answer["subproblems_answered"] == 2 and answer["engine"] != "none needed"
        assert answer["authority_created"] is False
        qualified = [e.payload for e in body.journal.replay("genesis.verified")
                     if e.payload["capability_id"].startswith("composed.selection.budgeted.")]
        assert qualified and qualified[-1]["passed"] and qualified[-1]["report"]["engine_calls"] > 0
