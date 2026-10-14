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
