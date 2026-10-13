"""The IntelligenceGenome library projects onto GREG's one catalog, worker, verifier and receipt."""
import json

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import admission, library
from greg.cognition.genomes.contract import ADMISSION, GenomeError, IntelligenceGenome


def test_every_genome_validates_and_projects_onto_the_existing_catalog():
    items = library.executables()
    assert {"flow_maxflow", "forecast_quantile", "decision_preposterior"} <= set(items)
    for family, item in items.items():
        g = item.genome
        assert catalog.FAMILIES[family] == (g.layer, (g.operation,), (g.epistemic_class,), "genome_certificate",
                                            g.dependency)
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert catalog.initial_state(f"cognition.{family}") == "VERIFIED"      # registered, never auto-attached


def test_a_genome_cannot_declare_effect_authority_or_skip_its_baseline():
    g = library.genome("flow_maxflow")
    with pytest.raises(GenomeError):
        IntelligenceGenome(**{**g.to_dict(), "authority_ceiling": "financial"}).validate()
    with pytest.raises(GenomeError):
        IntelligenceGenome(**{**g.to_dict(), "baseline": ""}).validate()


def test_a_genome_runs_on_the_canonical_path_with_an_independent_verifier():
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = library.executables()["flow_maxflow"].instance(3)
    withheld = reason({"problem_id": "g", "operation": "max_flow", "data": data}, registry=registry)
    assert withheld["abstention_state"] == "CAPABILITY_DEFICIT"            # withheld until attached
    registry.set_state("cognition.flow_maxflow", "ATTACHED")
    r = reason({"problem_id": "g", "operation": "max_flow", "data": data}, registry=registry)
    assert r["abstention_state"] == "NONE" and r["output"]["value"] == truth["value"]
    assert r["proof_type"] == "genome_certificate" and r["proof_artifact"]["evidence_type"] == "optimality_certificate"
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False


def test_the_independent_check_refutes_a_forged_flow():
    data, _ = library.executables()["flow_maxflow"].instance(3)
    out = library.run("flow_maxflow", data, {"latency_limit": 5, "compute_limit": 1000})
    assert all(library.check("flow_maxflow", data, out["output"], out["proof"]).values())
    forged = json.loads(json.dumps(out["output"]))
    forged["value"] += 1
    assert not all(library.check("flow_maxflow", data, forged, out["proof"]).values())
    tampered = {**out["proof"], "inputs_digest": "sha256:0"}
    assert not library.check("flow_maxflow", data, out["output"], tampered)["inputs_bound"]


class _Item:
    def __init__(self, standalone=True):
        self.tolerance = 1e-9
        self.subregion = None
        self.genome = type("G", (), {"standalone_decision": standalone})()


def _rows(c, b, k, *, cat=lambda q: "correct", secs=(1.0, 1.0, 1.0)):
    return [{"arms": {"candidate": {"quality": x, "category": cat(x), "seconds": secs[0]},
                      "baseline": {"quality": y, "category": cat(y), "seconds": secs[1]},
                      "competitor": {"quality": z, "category": cat(z), "seconds": secs[2]}}}
            for x, y, z in zip(c, b, k)]


def test_admission_rule_outcomes():
    ten = [1.0] * 10
    assert admission.decide(_Item(False), _rows(ten, ten, ten))[0] == "COMPOSITION_ONLY"
    assert admission.decide(_Item(), _rows([0.0] * 10, ten, ten))[0] == "REJECTED"
    assert admission.decide(_Item(), _rows(ten, ten, ten))[0] == "EXPERIMENTAL"
    assert admission.decide(_Item(), _rows(ten, [0.0] * 10, [2.0] * 10))[0] == "SUPERSEDED"
    assert admission.decide(_Item(), _rows([2.0] + [1.0] * 9, [0.0] * 10, [1.5] + [2.0] * 9))[0] == "NICHE_CAPABILITY"
    assert admission.decide(_Item(), _rows(ten, [0.0] * 10, ten))[0] == "DEFAULT_FOR_GEOMETRY"
    assert admission.decide(_Item(), _rows(ten, [0.0] * 10, ten, secs=(3.0, 1.0, 1.0)))[0] == "SUPERSEDED"
    assert set(ADMISSION) >= {"DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY", "REJECTED", "FRONTIER_HORIZON"}


def test_a_refuted_candidate_answer_is_scored_as_a_false_answer_below_abstention():
    item = library.executables()["flow_maxflow"]
    forged = type(item)(**{**item.__dict__, "verify": lambda d, o, c: {"forged": False}})
    rows = admission.evaluate(forged, [0])
    arm = rows[0]["arms"]["candidate"]
    data, truth = item.instance(0)
    assert arm["category"] == "wrong" and arm["refuted"] is True
    assert arm["quality"] < item.score(data, truth, None)["quality"]


def test_held_out_admission_refuses_changed_code(tmp_path, monkeypatch):
    monkeypatch.setattr(admission, "EVIDENCE", tmp_path)
    admission.main(["--freeze", "r1", "--only", "flow_maxflow"])
    frozen = json.loads((tmp_path / "r1" / "freeze.json").read_text())
    frozen["inputs"]["code"]["greg/cognition/genomes/flow.py"] = "sha256:changed"
    (tmp_path / "r1" / "freeze.json").write_text(json.dumps(frozen))
    with pytest.raises(SystemExit, match="FROZEN_INPUT_CHANGED"):
        admission.main(["--run", "r1"])


def _leaf_mutants(value, path=()):
    """Every single-leaf corruption: flip a bool, shift a number, drop a list's last element, suffix a string."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _leaf_mutants(v, path + (k,))
    elif isinstance(value, list):
        if value and all(not isinstance(v, (dict, list)) for v in value):
            yield path, value[:-1]
        for i, v in enumerate(value[:3]):
            yield from _leaf_mutants(v, path + (i,))
    elif type(value) is bool:
        yield path, not value
    elif isinstance(value, (int, float)):
        yield path, value * 1.37 + 1 if isinstance(value, float) else value + 1
    elif isinstance(value, str):
        yield path, value + "_x"


# A compiled model whose non-binding upper bound is raised means the same thing (same feasible integer
# points, same optimum); the verifiers require bounds that never cut the feasible region, not byte equality.
EQUIVALENT = {"flow_capacity_plan", "newsvendor_compile"}


@pytest.mark.parametrize("family", sorted(library.executables()))
def test_every_single_leaf_corruption_of_an_answer_is_refuted_or_provably_equivalent(family):
    import copy
    from greg.cognition.genomes.contract import model_optimum
    item = library.executables()[family]
    for seed in range(10):                              # the first dev seed on which the candidate answers
        data, truth = item.instance(seed)
        out = item.solve(data, {"latency_s": 5.0, "compute": 100000})
        if out["status"] == "ANSWER":
            break
    assert out["status"] == "ANSWER", family
    survivors = []
    for path, value in _leaf_mutants(out["output"]):
        if not path:
            continue
        forged = copy.deepcopy(out["output"])
        target = forged
        for k in path[:-1]:
            target = target[k]
        original, target[path[-1]] = target[path[-1]], value
        try:
            accepted = all(item.verify(data, forged, out["certificate"]).values())
        except Exception:                               # a verifier must refute malformed output, not raise
            accepted = "raised"
        if not accepted:
            continue
        if (accepted is True and family in EQUIVALENT and path[:2] == ("model", "variables") and path[-1] == 1
                and value > original and abs(model_optimum(forged["model"]) - truth["optimum"]) <= 1e-6):
            continue
        survivors.append((path, accepted))
    assert not survivors, (family, survivors[:10])


def test_maxflow_verify_proves_the_returned_cut_on_its_own():
    from greg.cognition.genomes import flow
    item = library.executables()["flow_maxflow"]
    data, _ = item.instance(3)
    out = item.solve(data, {"latency_s": 5.0})
    o = out["output"]
    assert flow.maxflow_verify(data, o, out["certificate"])["returned_cut_is_an_s_t_cut_of_value"]
    loose = dict(o, cut_edges=o["cut_edges"][1:])                  # no longer separates s from t
    assert not flow.maxflow_verify(data, loose, out["certificate"])["returned_cut_is_an_s_t_cut_of_value"]
    wrong_cap = dict(o, cut_edges=[[u, v, c + 1] for u, v, c in o["cut_edges"]])
    assert not flow.maxflow_verify(data, wrong_cap, out["certificate"])["returned_cut_is_an_s_t_cut_of_value"]
    assert flow.maxflow_verify(data, dict(o, flow=[["s", "t"]]), {}) == {"output_well_formed": False}
    assert flow.maxflow_verify(data, dict(o, flow=o["flow"] + [["nowhere", "t", 1]]), out["certificate"])[
        "capacity_respected"] is False


def test_forecast_verify_recomputes_every_quantile_and_bounds_the_declared_configuration():
    from greg.cognition.genomes import forecasting
    data, _ = forecasting.instance(2)
    out = forecasting.solve(data, {})
    assert all(forecasting.verify(data, out["output"], out["certificate"]).values())
    shifted = {**out["output"], "quantiles": {k: [v * 1.01 for v in path] if k == "0.9" else path
                                              for k, path in out["output"]["quantiles"].items()}}
    assert forecasting.verify(data, shifted, out["certificate"])["quantiles_recomputed"] is False
    widened = dict(out["certificate"], interval_scale=1.3)          # inside the space, not what was run
    assert forecasting.verify(data, out["output"], widened)["quantiles_recomputed"] is False
    outside = dict(out["certificate"], interval_scale=3.0)
    assert forecasting.verify(data, out["output"], outside)["declared_configuration_in_reviewed_space"] is False
    assert forecasting.verify(data, {"point": []}, out["certificate"]) == {"shape": False}


@pytest.mark.parametrize("family", ["flow_capacity_plan", "newsvendor_compile"])
def test_compiled_models_are_scored_by_their_exact_optimum_not_their_shape(family):
    import copy
    item = library.executables()[family]
    data, truth = item.instance(1)
    out = item.solve(data, {"latency_s": 5.0})
    assert item.score(data, truth, out["output"]) == {"quality": 1.0, "category": "correct"}
    flipped = copy.deepcopy(out["output"])
    flipped["model"]["objective"]["sense"] = "min" if flipped["model"]["objective"]["sense"] == "max" else "max"
    assert item.score(data, truth, flipped)["category"] == "wrong"
    dropped = copy.deepcopy(out["output"])
    dropped["model"]["constraints"].pop()                          # the capacity or budget row is gone
    assert not all(item.verify(data, dropped, out["certificate"]).values())
    assert item.score(data, truth, dropped)["category"] == "wrong"


def test_preposterior_verify_binds_the_act_now_decision_and_refutes_malformed_scenarios():
    from greg.cognition.genomes import decision
    data, _ = decision.instance(4)
    out = decision.solve(data, {})
    o = out["output"]
    flipped = dict(o, act_now="launch" if o["act_now"] == "abandon" else "abandon")
    assert decision.verify(data, flipped, {})["act_now_is_the_prior_best_decision"] is False
    assert decision.verify(data, dict(o, posterior_scenarios=[{"probability": 1.0}]), {}) == {
        "scenarios_well_formed": False}


def test_a_genome_abstention_through_the_canonical_path_is_an_abstention_receipt_not_an_error():
    """Found by the 2026-10-13-v1 admission smoke: an abstaining genome used to carry its certificate as a
    proof artifact without an output, and the receipt rejected it (CognitionError)."""
    from greg.cognition.cortex import reason, registry_view
    item = library.executables()["collective_flock"]
    data, _ = item.instance(1)
    data["steps"] = 10                                   # too short for local rules: an honest abstention
    assert item.solve(data, {"latency_s": 5.0})["status"] == "ABSTAIN"
    registry = registry_view()
    registry.set_state("cognition.collective_flock", "ATTACHED")
    r = reason({"problem_id": "flock-abstain", "operation": item.genome.operation, "data": data,
                "geometry": {"latency_limit": 30}}, registry=registry)
    assert r["abstention_state"] == "ABSTAIN" and r["output"] is None
    assert r["proof_type"] is None and r["proof_artifact"] is None
    assert "short of their goals" in r["missing_information"][0] and r["authority_created"] is False
