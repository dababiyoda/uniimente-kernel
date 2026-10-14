"""flow_expansion_mcf: budgeted capacity expansion by min-cost flow, certified without the solver's code.

Development seeds 0-9 only. The genome starts registered and withheld (VERIFIED); the canonical-path test attaches
it in an in-memory registry view, as an evaluation does. Nothing here changes a body or creates authority.
"""
import copy

import pytest

pytest.importorskip("networkx")

from greg.cognition.cortex import reason, registry_view  # noqa: E402
from greg.cognition.genomes import flow, library  # noqa: E402
from greg.cognition.genomes.contract import GenomeError  # noqa: E402

MCF = library.executables()["flow_expansion_mcf"]


def solved(seed):
    data, truth = MCF.instance(seed)
    out = MCF.solve(data, None)
    return data, truth, out


@pytest.mark.parametrize("seed", range(10))
def test_it_reaches_the_independent_optimum_and_its_certificate_verifies(seed):
    data, truth, out = solved(seed)
    assert out["status"] == "ANSWER" and out["output"]["flow_value"] == truth["optimum"] == flow.expansion_truth(data)
    assert all(MCF.verify(data, out["output"], out["certificate"]).values())
    assert MCF.score(data, truth, out["output"])["category"] == "correct"


def test_both_certificate_kinds_occur_and_verify():
    data, _, out = solved(0)
    assert out["certificate"]["kind"] == "budget"
    rich = copy.deepcopy(data)
    rich["budget"] = 10_000                                   # money is no constraint: the expanded cut binds
    out = MCF.solve(rich, None)
    assert out["certificate"]["kind"] == "capacity"
    assert all(MCF.verify(rich, out["output"], out["certificate"]).values())
    assert out["output"]["flow_value"] == flow.expansion_truth(rich)


def test_a_suboptimal_plan_cannot_borrow_the_optimal_certificate():
    for seed in range(10):
        data, truth, out = solved(seed)
        greedy = flow.greedy_solve(data, None)["output"]
        if greedy["flow_value"] == truth["optimum"]:
            continue
        borrowed = dict(out["certificate"], next_volume=greedy["flow_value"] + 1)
        checks = MCF.verify(data, greedy, borrowed)
        assert checks["flow_value_recomputed"] and not checks["optimal_by_dual_bound"]   # weak duality refuses
        return
    pytest.fail("greedy was optimal on every development seed; the test needs a suboptimal plan")


def test_corrupted_plans_and_certificates_are_refuted():
    data, _, out = solved(3)
    o, c = out["output"], out["certificate"]
    key = next(k for k, v in o["increments"].items() if v > 0)
    assert not MCF.verify(data, dict(o, flow_value=o["flow_value"] + 1), c)["flow_value_recomputed"]
    assert not MCF.verify(data, dict(o, spent=o["spent"] - 1), c)["spend_recomputed"]
    over = dict(o, increments={**o["increments"], key: data["max_increment"] + 1})
    assert not MCF.verify(data, over, c)["within_budget_and_bounds"]
    assert not MCF.verify(data, o, dict(c, potentials={**c["potentials"], data["source"]: 10**6}))[
        "optimal_by_dual_bound"]
    assert not MCF.verify(data, o, dict(c, next_volume=o["flow_value"] + 2))["optimal_by_dual_bound"]
    assert not MCF.verify(data, o, {"kind": "capacity", "source_side": [data["source"]]})["optimal_by_cut"]
    assert not MCF.verify(data, o, {})["optimality_certificate_present"]
    assert MCF.verify(data, {"increments": "all"}, c) == {"output_well_formed": False}


def test_parallel_edges_and_malformed_networks_are_refused():
    data, _, _ = solved(1)
    doubled = copy.deepcopy(data)
    doubled["edges"].append(list(doubled["edges"][0]))
    with pytest.raises(GenomeError, match="parallel edges"):
        MCF.solve(doubled, None)
    broken = dict(data, budget=-1)
    with pytest.raises(GenomeError):
        MCF.solve(broken, None)


def test_on_the_canonical_path_it_answers_with_an_optimality_certificate_and_no_authority():
    data, truth = MCF.instance(4)
    registry = registry_view()
    registry.set_state("cognition.flow_expansion_mcf", "ATTACHED")
    r = reason({"problem_id": "mcf", "operation": "expand_capacity_mcf", "data": data}, registry=registry)
    assert r["abstention_state"] == "NONE" and r["output"]["flow_value"] == truth["optimum"]
    assert r["proof_artifact"]["evidence_type"] == "optimality_certificate"
    assert r["authority_created"] is False
    withheld = reason({"problem_id": "mcf", "operation": "expand_capacity_mcf", "data": data}, registry=registry_view())
    assert withheld["abstention_state"] == "CAPABILITY_DEFICIT"                     # registered, not attached


# one priced edge s->t: buying one unit for exactly the budget is affordable, so the optimum is 1 and a zero plan is
# wrong. Each certificate below is the boundary or the side condition a verifier must refuse (review 2026-10-14).
ONE_EDGE = {"edges": [["s", "t", 0]], "source": "s", "sink": "t", "unit_cost": {"s->t": 1}, "max_increment": 5,
            "budget": 1}
ZERO_PLAN = {"increments": {"s->t": 0}, "flow_value": 0, "spent": 0}


def test_a_dual_bound_equal_to_the_budget_does_not_certify_optimality():
    """C(V+1) == budget means one more unit is affordable: only a bound strictly above the budget certifies."""
    assert flow.expansion_truth(ONE_EDGE) == 1
    at_budget = {"kind": "budget", "next_volume": 1, "potentials": {"s": 0, "t": 1}}       # LB = 1 * 1 = budget
    checks = MCF.verify(ONE_EDGE, ZERO_PLAN, at_budget)
    assert checks["within_budget_and_bounds"] and not checks["optimal_by_dual_bound"]
    above = dict(ONE_EDGE, budget=0)                       # the same bound now exceeds the budget: certified
    assert all(MCF.verify(above, ZERO_PLAN, at_budget).values())


def test_a_cut_must_hold_the_source_and_not_the_sink():
    assert not MCF.verify(ONE_EDGE, ZERO_PLAN, {"kind": "capacity", "source_side": ["s", "t"]})["optimal_by_cut"]
    assert not MCF.verify(ONE_EDGE, ZERO_PLAN, {"kind": "capacity", "source_side": []})["optimal_by_cut"]
    # a two-edge path whose middle edge has no capacity and no increment: {s, m} is a valid zero cut
    closed = {"edges": [["s", "m", 3], ["m", "t", 0]], "source": "s", "sink": "t",
              "unit_cost": {"s->m": 1, "m->t": 1}, "max_increment": 0, "budget": 10}
    assert all(MCF.verify(closed, {"increments": {"s->m": 0, "m->t": 0}, "flow_value": 0, "spent": 0},
                          {"kind": "capacity", "source_side": ["s", "m"]}).values())
    assert not MCF.verify(closed, {"increments": {"s->m": 0, "m->t": 0}, "flow_value": 0, "spent": 0},
                          {"kind": "capacity", "source_side": ["m"]})["optimal_by_cut"]       # s left out


@pytest.mark.parametrize("family", ["flow_expansion_mcf", "flow_reinforce_greedy", "flow_capacity_plan"])
def test_distinct_edges_sharing_one_u_to_v_name_are_refused_at_input(family):
    """('a->b', 'c') and ('a', 'b->c') are both named 'a->b->c': one increment and one price would stand for two
    edges, and the mcf solver's own plan overspent (10 against a budget of 5) before its verifier refuted it."""
    data = {"edges": [["s", "a->b", 10], ["a->b", "c", 0], ["c", "t", 10],
                      ["s", "a", 10], ["a", "b->c", 0], ["b->c", "t", 10]],
            "source": "s", "sink": "t",
            "unit_cost": {"s->a->b": 0, "a->b->c": 1, "c->t": 0, "s->a": 0, "b->c->t": 0},
            "max_increment": 5, "budget": 5}
    genome = library.executables()[family]
    with pytest.raises(GenomeError, match="share one 'u->v' name"):
        genome.solve(data, None)
    with pytest.raises(GenomeError, match="share one 'u->v' name"):
        genome.verify(data, {"increments": {}, "flow_value": 0, "spent": 0}, {})
    renamed = copy.deepcopy(data)                          # the same network, unambiguous names: answered
    rename = {"a->b": "ab", "b->c": "bc"}
    renamed["edges"] = [[rename.get(u, u), rename.get(v, v), c] for u, v, c in data["edges"]]
    renamed["unit_cost"] = {f"{u}->{v}": (1 if (u, v) in (("ab", "c"), ("a", "bc")) else 0)
                            for u, v, _ in renamed["edges"]}
    assert genome.solve(renamed, None)["status"] == "ANSWER"
