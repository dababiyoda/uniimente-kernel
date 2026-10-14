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


def test_forecast_tolerances_follow_the_series_scale_so_tiny_units_cannot_hide_a_forgery():
    # review 2026-10-13: absolute 1e-6 tolerances accepted a 670x-off point on a series in tiny units, and
    # six absolute decimals collapsed such a series' forecast to a constant or to zero
    from greg.cognition.genomes import forecasting
    data, _ = forecasting.instance(3)
    for scale in (1e-6, 1e-9):
        tiny = {**data, "history": [v * scale for v in data["history"]]}
        out = forecasting.solve(tiny, {})
        assert all(forecasting.verify(tiny, out["output"], out["certificate"]).values())
        assert len({v for k in out["output"]["quantiles"] for v in out["output"]["quantiles"][k]}) > 1
        forged = {**out["output"], "point": [1e-9] * len(out["output"]["point"])}
        assert forecasting.verify(tiny, forged, out["certificate"])["point_recomputed"] is False


def test_forecast_levels_are_distinct_after_key_formatting():
    from greg.cognition.genomes import forecasting
    data, _ = forecasting.instance(3)
    out = forecasting.solve({**data, "levels": [0.25, 0.5, 0.5, 0.75]}, {})       # duplicates collapse
    assert out["output"]["levels"] == [0.25, 0.5, 0.75]
    assert all(forecasting.verify({**data, "levels": [0.25, 0.5, 0.5, 0.75]}, out["output"],
                                  out["certificate"]).values())
    with pytest.raises(GenomeError):                                              # would share one key
        forecasting.solve({**data, "levels": [0.1234567, 0.1234568, 0.9]}, {})


def test_newsvendor_refuses_unequal_scenario_counts_whose_summed_cost_is_not_the_sample_average():
    from greg.cognition.genomes import forecasting
    data = {"products": [{"name": "A", "scenarios": [10, 10], "over_cost": 1, "under_cost": 5},
                         {"name": "B", "scenarios": [10] * 10, "over_cost": 1, "under_cost": 2}], "capacity": 10}
    for fn in (lambda: forecasting.compile_newsvendor(data, {}), lambda: forecasting.newsvendor_optimum(data)):
        with pytest.raises(GenomeError):
            fn()


def test_forecast_verify_requires_the_declared_parameters_to_be_the_grid_selection():
    # review 2026-10-13: an in-space but unselected (alpha, beta, phi) with its own consistent quantiles
    # verified while scoring about 10x worse; the selection claim is now recomputed
    from greg.cognition.genomes import forecasting as F
    data, _ = F.instance(2)
    y, h, levels = F._series(data)
    cfg = dict(F.DEFAULT_CONFIG, fit_window=104, error_model="additive_scaled", interval_scale=1.4,
               beta_set=[0.0, 0.02, 0.05], phi_set=[0.9, 0.98, 1.0])
    forced = (0.1, 0.0, 1.0)
    assert forced != F.fit(y, cfg)
    point = F._holt_point(y, forced, h, cfg)
    eq, origins = F._error_quantiles(y, F._holt_point, forced, h, levels, cfg)
    forged = {"point": [F._sig(v) for v in point], "levels": levels,
              "quantiles": {f"{q:g}": [F._sig(max(point[k] + eq[k][i] * y[-1], 1e-9)) for k in range(h)]
                            for i, q in enumerate(levels)}}
    cert = {"alpha": 0.1, "beta": 0.0, "phi": 1.0, "fit_window": 104, "beta_set": cfg["beta_set"],
            "phi_set": cfg["phi_set"], "rolling_origins": origins, "interval_scale": 1.4,
            "error_model": "empirical additive_scaled quantiles per horizon"}
    checks = F.verify(data, forged, cert)
    assert checks["quantiles_recomputed"] and checks["parameters_are_the_grid_selection"] is False
    genuine = F.solve_with(cfg, data)
    assert all(F.verify(data, genuine["output"], genuine["certificate"]).values())
    for bad in ({"beta": [0.0]}, {"phi": {"x": 1}}, {"beta_set": "x"}, {"fit_window": 104.0}):
        assert not all(F.verify(data, genuine["output"], {**genuine["certificate"], **bad}).values())


@pytest.mark.parametrize("alpha,beta,n", [(5000.5, 0.5, 400), (2000.5, 1.5, 300), (3000, 1, 250), (5000.5, 0.5, 200)])
def test_preposterior_verify_does_not_underflow_on_valid_posteriors(alpha, beta, n):
    # review 2026-10-13: the float product for P(k=0) underflowed to 0 and refuted the solver's correct answer
    from greg.cognition.genomes import decision
    d = {"alpha": alpha, "beta": beta, "pilot_size": n, "customers": 1000, "value_per_success": 20,
         "fixed_cost": 1000, "pilot_cost": 100}
    out = decision.solve(d, {})
    assert all(decision.verify(d, out["output"], out["certificate"]).values())


def test_preposterior_exact_verify_is_linear_in_the_pilot_not_in_the_posterior_size():
    # review 2026-10-13: factorials of alpha and beta took 66 s at alpha = beta = 50 000
    import time
    from greg.cognition.genomes import decision
    d = {"alpha": 400_000, "beta": 400_000, "pilot_size": 200, "customers": 1000, "value_per_success": 20,
         "fixed_cost": 1000, "pilot_cost": 100}
    out = decision.solve(d, {})
    started = time.perf_counter()
    assert all(decision.verify(d, out["output"], out["certificate"]).values())
    assert time.perf_counter() - started < 2.0
    forged = {**out["output"], "posterior_scenarios": [dict(s) for s in out["output"]["posterior_scenarios"]]}
    forged["posterior_scenarios"][100]["probability"] *= 1.01
    assert decision.verify(d, forged, out["certificate"])["probabilities_recomputed"] is False


def test_the_admission_freeze_hashes_the_path_the_data_and_the_dependency_versions():
    # review 2026-10-13: the freeze hashed only the genome modules, so a changed cortex, solver or M4 file
    # would not have raised FROZEN_INPUT_CHANGED
    frozen = admission.inputs(sorted(library.executables()))
    for path in ("greg/cognition/cortex.py", "greg/cognition/solvers.py", "greg/cognition/worker.py",
                 "greg/capabilities.py", "cortex/evaluation/data/m4_weekly.json.gz", "tools/offline_test.py"):
        assert path in frozen["code"]
    assert frozen["dependencies"]["numpy"] and frozen["dependencies"]["scipy"]


def test_an_oracle_competitor_is_a_reference_and_never_supersedes():
    # independent evidence review 2026-10-13: collective_market was SUPERSEDED by a latency gap against a
    # centralized optimum that reads every private value, leaving the market geometry unroutable
    item = library.executables()["collective_market"]
    assert item.competitor_deployable is False
    assert all(e.competitor_deployable for f, e in library.executables().items() if f != "collective_market")
    rows = admission.evaluate(item, list(admission.DEV_SEEDS[:4]))
    status, detail = admission.decide(item, rows)
    assert status != "SUPERSEDED" and "reference upper bound" in detail["competitor_role"]
    deployable = type(item)(**{**item.__dict__, "competitor_deployable": True})
    assert "competitor_role" not in admission.decide(deployable, rows)[1]


def test_a_re_admission_freezes_its_own_fresh_seeds_and_refuses_spent_ones(tmp_path, monkeypatch):
    monkeypatch.setattr(admission, "EVIDENCE", tmp_path)
    admission.main(["--freeze", "r1", "--only", "flow_maxflow"])                  # default range 1000-1029
    with pytest.raises(SystemExit, match="spent"):
        admission.main(["--freeze", "r2", "--only", "flow_maxflow", "--heldout-start", "1010"])
    for reserved in ("7000", "0"):
        with pytest.raises(SystemExit, match="P8-reserved|development"):
            admission.main(["--freeze", f"r-{reserved}", "--only", "flow_maxflow", "--heldout-start", reserved])
    admission.main(["--freeze", "r3", "--only", "flow_maxflow", "--heldout-start", "1100"])
    frozen = json.loads((tmp_path / "r3" / "freeze.json").read_text())
    assert frozen["inputs"]["heldout_seeds"] == list(range(1100, 1130))
    assert admission.inputs(["flow_maxflow"], tuple(range(1100, 1130))) == frozen["inputs"]


def test_freshness_is_checked_on_the_data_a_seed_draws_not_on_the_seed_number(tmp_path, monkeypatch):
    """Review finding 6: forecast_quantile draws pool[(seed * 7919) % 241], so 'fresh' seed numbers redrew v1's
    series (start 1241) and v2's seeds 1100-1129 drew 30 series P8 had trained or been evaluated on."""
    monkeypatch.setattr(admission, "EVIDENCE", tmp_path)
    admission.main(["--freeze", "r1", "--only", "forecast_quantile", "--heldout-start", "1000"])
    with pytest.raises(SystemExit, match="draw data already used"):
        admission.main(["--freeze", "r2", "--only", "forecast_quantile", "--heldout-start", "1241"])
    reused = admission.reused_instances(["forecast_quantile"], tuple(range(1100, 1130)), set(range(1000, 1030)))
    assert reused == {"forecast_quantile": {"reused": 30, "of": 30}}         # every v2 series was P8's
    # a synthetic genome draws a new instance per seed: seed numbers are its identities
    assert admission.reused_instances(["queue_erlang"], tuple(range(1241, 1271)), set(range(1000, 1030))) == {}


def test_the_p8_forecast_split_replays_as_recorded_and_new_cycles_exclude_every_admission_run():
    from greg.cognition import evolution
    from pathlib import Path
    recorded = json.loads((Path(__file__).resolve().parents[2] / "docs/evidence/greg-protected-evolution/"
                           "2026-10-08/cycle-forecast-1.json").read_text())["split"]
    cycle = evolution.COMPLETED_FORECAST_CYCLES["2026-10-08/cycle-forecast-1"]
    train, held, excluded = evolution.forecasting_split(cycle["seed"], cycle["excluded_seeds"])
    assert (len(train), len(held), len(excluded)) == (recorded["train"], recorded["heldout"],
                                                      recorded["excluded_admission_series"])
    train, held, excluded = evolution.forecasting_split()
    from greg.cognition.genomes import forecasting
    for seed in sorted(admission.spent_seeds()):
        assert forecasting.instance_key(seed) not in train and forecasting.instance_key(seed) not in held
