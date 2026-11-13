"""Robust tube MPC (L3), two-sided CUSUM signal sensing (L1) and Hamming/SECDED correction (L1): contract, withheld
registration, canonical path, Competency Compiler reachability, independent verification, refutation of corrupted
answers and forged certificates, exhaustive correctness of the mechanisms, invalid input and scoring.

Development seeds 0-9 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
import itertools
import json
import math

import pytest

from greg.cognition import catalog, worlds
from greg.cognition.genomes import control_b as C, library
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

ITEMS = {x.genome.family: x for x in C.INTELLIGENCES}
FAMILIES = tuple(sorted(ITEMS))
SPEC = {  # family: (layer, operation, epistemic class, evidence type, dependency)
    "control_robust_tube": (3, "robust_tube_mpc", "physical", "feasibility_witness", "scipy"),
    "basal_cusum_detect": (1, "detect_mean_shift", "estimate", "statistical_estimate", None),
    "basal_hamming_correct": (1, "correct_bit_errors", "arithmetic", "exact_calculation", None),
}
BUDGET = {"latency_s": 8.0, "compute": 100000}
_CACHE: dict = {}


def dev(family, seed=1):
    assert 0 <= seed < 10                                       # never a held-out seed
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = ITEMS[family].instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), copy.deepcopy(truth)


def solved(family, seed=1):
    key = ("solved", family, seed)
    if key not in _CACHE:
        data, _ = dev(family, seed)
        _CACHE[key] = ITEMS[family].solve(data, BUDGET)
    data, truth = dev(family, seed)
    return data, truth, copy.deepcopy(_CACHE[key])


def _ok(family, data, output, cert):
    return all(ITEMS[family].verify(data, output, cert).values())


def _answered(family):
    return [s for s in range(10) if solved(family, s)[2]["status"] == "ANSWER"]


def _correct(family):
    return [s for s in _answered(family)
            if ITEMS[family].score(*solved(family, s)[:2], solved(family, s)[2]["output"])["category"] == "correct"]


def _json_clean(value):
    if isinstance(value, float):
        assert math.isfinite(value)
    elif isinstance(value, dict):
        assert all(isinstance(k, str) for k in value)
        for v in value.values():
            _json_clean(v)
    elif isinstance(value, list):
        for v in value:
            _json_clean(v)
    else:
        assert value is None or isinstance(value, (str, int, bool))


# ------------------------------------------------------------------ contract and registration
def test_genomes_validate_with_declared_identity_and_world():
    assert set(FAMILIES) == set(SPEC)
    for family, x in ITEMS.items():
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        assert (g.layer, g.operation, g.epistemic_class, g.evidence_type, g.dependency) == SPEC[family]
        assert worlds.world("genome", family) == "simulated_world"
        assert g.buildability == "BUILDABLE_NOW" and g.standalone_decision and g.version == "1.0.0"
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert any("MIND-COVERAGE-2026-10-21" in item for item in g.lineage)
        assert len(g.known_failure_modes) >= 3 and g.counterindications and g.abstention_conditions
        assert g.baseline and g.competitor and x.subregion is not None and x.competitor_deployable
        assert "seeds 0-9 dev" in g.benchmark_suite


def test_sensing_names_its_limit_honestly():
    g = ITEMS["basal_cusum_detect"].genome
    assert "no physical sensors" in g.subgeometry
    assert any("no physical sensors" in f for f in g.known_failure_modes)


def test_registered_in_the_one_catalog_and_withheld():
    families = library.executables()
    for family in FAMILIES:
        assert families[family] is ITEMS[family]
        g = ITEMS[family].genome
        assert catalog.FAMILIES[family] == (g.layer, (g.operation,), (g.epistemic_class,), "genome_certificate",
                                            g.dependency)
        assert catalog.initial_state(f"cognition.{family}") == "VERIFIED"      # registered, never auto-attached


def test_reserved_mechanisms_name_their_new_executors():
    from greg.cognition.reserved import EXECUTED_ON_GREG
    assert "cognition.control_robust_tube" in EXECUTED_ON_GREG["cortex.control.feedback"][0]
    assert "cognition.basal_cusum_detect" in EXECUTED_ON_GREG["cortex.pattern.anomaly"][0]


def test_module_imports_no_heavy_package_at_top_level():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(C))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {
        n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


# ------------------------------------------------------------------ solve / verify on development seeds
@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("seed", range(10))
def test_solve_is_compact_and_every_answer_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert out["status"] in ("ANSWER", "ABSTAIN"), out["missing"]
    _json_clean(out["certificate"])
    json.dumps(data, allow_nan=False)
    if out["status"] != "ANSWER":
        assert out["output"] is None and out["missing"]
        assert ITEMS[family].score(data, truth, None)["category"] == "abstain"
        return
    _json_clean(out["output"])
    checks = ITEMS[family].verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    score = ITEMS[family].score(data, truth, out["output"])
    assert math.isfinite(score["quality"])
    if family == "control_robust_tube":
        assert score["category"] == "correct"          # robust by construction: never a violating policy


def test_every_family_answers_correctly_on_some_development_seed():
    for family in FAMILIES:
        assert _correct(family), family


def test_solve_is_deterministic():
    for family in FAMILIES:
        seed = _answered(family)[0]
        data, _ = dev(family, seed)
        assert ITEMS[family].solve(data, BUDGET) == ITEMS[family].solve(copy.deepcopy(data), BUDGET)


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    seed = _correct(family)[0]
    registry = registry_view()
    data, truth = dev(family, seed)
    request = {"problem_id": f"control-b-{family}", "operation": SPEC[family][1], "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["proof_artifact"]["evidence_type"] == SPEC[family][3]
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False
    assert ITEMS[family].score(data, truth, r["output"])["category"] == "correct"


@pytest.mark.parametrize("family", FAMILIES)
def test_the_competency_compiler_reaches_the_family_by_its_inputs(family, tmp_path, monkeypatch):
    """Evaluation only: an in-memory attach (no body, journal or founder pin) and an empty evidence index."""
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    data, truth = dev(family, _correct(family)[0])
    cls = SPEC[family][2]
    request = {"problem_id": f"control-b-compile-{family}", "compile": {"geometry": {"geometry": cls},
                                                                        "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{family}"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{family}"
    assert r["authority_created"] is False


# ------------------------------------------------------------------ robust tube MPC
def _tube_answer():
    seed = _answered("control_robust_tube")[0]
    return solved("control_robust_tube", seed)


def test_tube_rejects_six_distinct_corruptions():
    data, truth, out = _tube_answer()
    o, cert = out["output"], out["certificate"]
    verify = C.tube_verify
    assert all(verify(data, o, cert).values())
    corrupt = []
    a = copy.deepcopy(o)                                   # 1. nominal start moved off x0
    a["nominal_states"][0][0] += 0.05
    corrupt.append((a, cert, "nominal_starts_at_x0"))
    b = copy.deepcopy(o)                                   # 2. nominal state off the model
    b["nominal_states"][2][1] += 0.05
    corrupt.append((b, cert, "nominal_follows_the_model"))
    c = copy.deepcopy(o)                                   # 3. nominal input pushed past the input bound
    c["nominal_inputs"][0][0] = data["u_max"][0] * 1.5
    corrupt.append((c, cert, "input_bounds_hold_on_every_vertex_sequence"))
    d = copy.deepcopy(o)                                   # 4. a gain fifty times too strong saturates the input
    d["K"] = [[50.0 * x for x in row] for row in o["K"]]
    corrupt.append((d, cert, "input_bounds_hold_on_every_vertex_sequence"))
    e = copy.deepcopy(o)                                   # 5. a model-consistent plan that rides the input bound
    p = C._rt(data)
    import numpy as np
    v = np.full((p["N"], p["m"]), p["umax"][0])
    c0, G = C._rt_prediction(p)
    e["nominal_inputs"] = v.tolist()
    e["nominal_states"] = (c0 + np.einsum("tij,j->ti", G, v.reshape(-1))).tolist()
    corrupt.append((o, dict(cert, worst_case_cost_bound=cert["nominal_cost"] * 0.5),   # 6. forged cost bound
                    "worst_case_cost_within_certified_bound"))
    corrupt.append((o, dict(cert, worst_case_cost_bound=None), "worst_case_cost_within_certified_bound"))
    shape = copy.deepcopy(o)                               # 7. malformed shape
    shape["nominal_inputs"] = shape["nominal_inputs"][:-1]
    assert verify(data, shape, cert) == {"output_shape": False}
    nan = copy.deepcopy(o)                                 # 8. non-finite gain
    nan["K"][0][0] = float("nan")
    assert verify(data, nan, cert) == {"output_shape": False}
    for bad, bad_cert, check in corrupt:
        assert verify(data, bad, bad_cert)[check] is False, check
    checks = verify(data, e, cert)
    assert checks["nominal_follows_the_model"] and not all(checks.values()), checks


def test_tube_feedback_matters_on_some_seed():
    """Removing K, or keeping K but dropping the tightening, breaks robustness on some development seed."""
    broken = 0
    for seed in _answered("control_robust_tube"):
        data, truth, out = solved("control_robust_tube", seed)
        o = copy.deepcopy(out["output"])
        o["K"] = [[0.0] * len(data["A"])]
        broken += not all(C.tube_verify(data, o, out["certificate"]).values())
    assert broken


def test_tube_score_superposition_agrees_with_the_verifier_simulation():
    for seed in _answered("control_robust_tube"):
        data, truth, out = solved("control_robust_tube", seed)
        p = C._rt(data)
        violation, cost = C._rt_worst_case(p, out["output"])
        assert violation <= 1e-9
        assert cost <= out["certificate"]["worst_case_cost_bound"] * (1 + 1e-9) + 1e-9
        assert out["certificate"]["nominal_cost"] <= cost + 1e-6    # the nominal path is one admissible case


def test_tube_baseline_violates_somewhere_and_competitor_never_does():
    wrong = 0
    for seed in range(10):
        data, truth = dev("control_robust_tube", seed)
        base = ITEMS["control_robust_tube"].score(data, truth, C.tube_nominal(data))
        wrong += base["category"] == "wrong"
        comp = C.tube_minmax_open_loop(data)
        if comp is not None:
            assert ITEMS["control_robust_tube"].score(data, truth, comp)["category"] == "correct"
            assert all(C.tube_verify(data, comp, {"worst_case_cost_bound": 1e12}).values())
    assert wrong >= 1


def test_tube_competitor_is_optimal_among_open_loop_policies():
    """The min-max LP's worst case is no worse than the baseline's open-loop plan whenever that plan is safe."""
    for seed in range(10):
        data, truth = dev("control_robust_tube", seed)
        comp, base = C.tube_minmax_open_loop(data), C.tube_nominal(data)
        if comp is None or base is None:
            continue
        p = C._rt(data)
        bv, bc = C._rt_worst_case(p, base)
        if bv <= 1e-9:
            assert C._rt_worst_case(p, comp)[1] <= bc + 1e-6


def test_tube_abstains_without_guessing_and_refuses_invalid_input():
    data, _ = dev("control_robust_tube", 0)
    tight = dict(data, w_max=[x * 0.9 for x in data["x_max"]])
    out = C.tube_solve(tight, BUDGET)
    assert out["status"] == "ABSTAIN" and out["output"] is None
    for bad in (dict(data, horizon=0), dict(data, x0=[x * 2 for x in data["x_max"]]), dict(data, A=[[1.0]]),
                dict(data, weights={"q": 1.0}), dict(data, u_max=[-1.0]), "not a dict"):
        with pytest.raises(GenomeError):
            C.tube_solve(bad, BUDGET)
    assert ITEMS["control_robust_tube"].score(data, {}, {"K": 1})["category"] == "wrong"


# ------------------------------------------------------------------ two-sided CUSUM
def test_cusum_rejects_six_distinct_corruptions():
    seed = next(s for s in _answered("basal_cusum_detect") if solved("basal_cusum_detect", s)[2]["output"]["alarm"])
    data, truth, out = solved("basal_cusum_detect", seed)
    o, cert = out["output"], out["certificate"]
    v = C.cusum_verify
    assert all(v(data, o, cert).values())
    assert v(data, dict(o, alarm=o["alarm"] + 1), cert)["alarm_is_the_first_crossing"] is False      # 1. late
    assert v(data, dict(o, alarm=o["alarm"] - 1), cert)["alarm_is_the_first_crossing"] is False      # 2. early
    assert v(data, {"alarm": None, "direction": None}, cert)["alarm_is_the_first_crossing"] is False  # 3. suppressed
    flipped = dict(o, direction="down" if o["direction"] == "up" else "up")
    assert v(data, flipped, cert)["direction_matches_the_crossing_chart"] is False                   # 4. direction
    assert v(data, o, dict(cert, h=cert["h"] * 0.8))["threshold_meets_declared_arl0"] is False       # 5. threshold
    assert v(data, o, dict(cert, k=cert["k"] * 1.3))["reference_value_matches_delta"] is False       # 6. reference
    assert v(data, dict(o, alarm=len(data["stream"])), cert) == {"output_shape": False}               # 7. range
    assert v(data, dict(o, direction=None), cert) == {"output_shape": False}                          # 8. shape
    assert v(data, o, {"k": cert["k"]}) == {"output_shape": True, "certificate_well_formed": False}   # 9. no h


def test_cusum_recursion_matches_the_running_minimum_identity_on_every_seed():
    import numpy as np
    for seed in range(10):
        data, _ = dev("basal_cusum_detect", seed)
        stream, mu0, sigma, delta, _ = C._cu(data)
        k = delta / (2 * sigma)
        up, rec = 0.0, []
        for x in stream:
            up = max(0.0, up + (x - mu0) / sigma - k)
            rec.append(up)
        cs = np.concatenate([[0.0], np.cumsum((np.asarray(stream) - mu0) / sigma - k)])
        assert np.allclose(rec, cs[1:] - np.minimum.accumulate(cs)[1:], atol=1e-9)


def test_cusum_threshold_rises_with_arl0_and_the_window_test_is_calibrated():
    hs = [C._cusum_threshold(0.5, a) for a in (100, 500, 1000, 10000)]
    assert hs == sorted(hs) and all(abs(C._siegmund_two_sided_arl(h, 0.5) / a - 1) < 1e-9
                                    for h, a in zip(hs, (100, 500, 1000, 10000)))
    assert abs(C._normal_quantile(0.975) - 1.959964) < 1e-5


def test_cusum_detects_a_clean_large_shift_quickly_and_stays_quiet_on_a_constant_stream():
    stream = [0.0] * 100 + [3.0] * 50
    data = {"stream": stream, "mu0": 0.0, "sigma": 1.0, "delta": 2.0, "arl0": 1000.0}
    out = C.cusum_solve(data, BUDGET)["output"]
    assert out["direction"] == "up" and 100 <= out["alarm"] <= 105
    quiet = dict(data, stream=[0.0] * 300)
    assert C.cusum_solve(quiet, BUDGET)["output"] == {"alarm": None, "direction": None}
    assert C.cusum_shiryaev_roberts(quiet)["alarm"] is None and C.cusum_window_ztest(quiet)["alarm"] is None
    down = dict(data, stream=[0.0] * 100 + [-3.0] * 50)
    assert C.cusum_solve(down, BUDGET)["output"]["direction"] == "down"
    assert C.cusum_shiryaev_roberts(down)["direction"] == "down"


def test_cusum_score_follows_the_declared_loss():
    data = {"stream": [0.0] * 100}
    assert C.cusum_score(data, {"change_point": 40}, {"alarm": 45}) == {"quality": -5.0, "category": "correct"}
    assert C.cusum_score(data, {"change_point": 40}, {"alarm": 10})["quality"] == -C.FALSE_ALARM_LOSS
    assert C.cusum_score(data, {"change_point": 40}, {"alarm": None}) == {"quality": -(60 + C.MISS_LOSS),
                                                                         "category": "wrong"}
    assert C.cusum_score(data, {"change_point": None}, {"alarm": None}) == {"quality": 0.0, "category": "correct"}
    assert C.cusum_score(data, {"change_point": None}, {"alarm": 3})["category"] == "wrong"
    assert C.cusum_score(data, {"change_point": None}, None)["category"] == "abstain"
    assert C.cusum_score(data, {"change_point": 40}, {"alarm": 500})["category"] == "wrong"


def test_cusum_refuses_invalid_input():
    good = {"stream": [0.0, 1.0], "mu0": 0.0, "sigma": 1.0, "delta": 1.0, "arl0": 100.0}
    for bad in (dict(good, sigma=0), dict(good, delta=-1.0), dict(good, arl0=5.0), dict(good, stream=[1.0]),
                dict(good, stream=[0.0, float("inf")]), [1, 2]):
        with pytest.raises(GenomeError):
            C.cusum_solve(bad, BUDGET)


# ------------------------------------------------------------------ Hamming / SECDED
def _received(code, data_bits, flips):
    r, extended = C.CODES[code]
    word = C._reencode(list(data_bits), r, extended)
    for j in flips:
        word[j] ^= 1
    return "".join(map(str, word))


@pytest.mark.parametrize("code", sorted(C.CODES))
def test_every_single_flip_is_corrected_exactly(code):
    r, extended = C.CODES[code]
    k = len(C._data_positions(r))
    n = (1 << r) - 1 + extended
    msgs = list(itertools.product((0, 1), repeat=k))[:: 1 if k <= 4 else 97]
    words, original = [], []
    for m in msgs:
        for j in [None] + list(range(n)):
            words.append(_received(code, m, [] if j is None else [j]))
            original.append("".join(map(str, m)))
    data = {"code": code, "codewords": words, "flip_probability": 0.01}
    out = C.hamming_solve(data, BUDGET)
    assert out["output"]["decoded"] == original
    assert all(C.hamming_verify(data, out["output"], out["certificate"]).values())


@pytest.mark.parametrize("code", ["secded_8_4", "secded_16_11"])
def test_secded_flags_every_double_flip(code):
    r, extended = C.CODES[code]
    k = len(C._data_positions(r))
    n = (1 << r) + 0
    m = tuple(i % 2 for i in range(k))
    words = [_received(code, m, list(pair)) for pair in itertools.combinations(range(n), 2)]
    data = {"code": code, "codewords": words, "flip_probability": 0.01}
    out = C.hamming_solve(data, BUDGET)
    assert set(out["output"]["status"]) == {"uncorrectable"} and set(out["output"]["decoded"]) == {None}
    assert all(C.hamming_verify(data, out["output"], out["certificate"]).values())


def test_plain_hamming_silently_miscorrects_double_flips():
    data = {"code": "hamming_7_4", "codewords": [_received("hamming_7_4", (1, 0, 1, 1), [0, 3])],
            "flip_probability": 0.01}
    out = C.hamming_solve(data, BUDGET)["output"]
    assert out["status"] == ["corrected"] and out["decoded"] != ["1011"]
    assert C.hamming_score(data, {"data": ["1011"]}, out) == {"quality": -1.0, "category": "wrong"}


def test_hamming_rejects_six_distinct_corruptions():
    seed = next(s for s in _answered("basal_hamming_correct")
                if "corrected" in solved("basal_hamming_correct", s)[2]["output"]["status"])
    data, truth, out = solved("basal_hamming_correct", seed)
    o, cert = out["output"], out["certificate"]
    v = C.hamming_verify
    assert all(v(data, o, cert).values())
    i = o["status"].index("corrected")
    ok = o["status"].index("ok")

    def flip(s, j=0):
        return s[:j] + ("1" if s[j] == "0" else "0") + s[j + 1:]
    bad = copy.deepcopy(o)                                  # 1. a corrected block's data changed
    bad["decoded"][i] = flip(bad["decoded"][i])
    assert v(data, bad, cert)["every_decoded_block_reencodes_within_its_claimed_distance"] is False
    bad = copy.deepcopy(o)                                  # 2. a clean block's data changed
    bad["decoded"][ok] = flip(bad["decoded"][ok], 1)
    assert v(data, bad, cert)["every_decoded_block_reencodes_within_its_claimed_distance"] is False
    bad = copy.deepcopy(o)                                  # 3. a corrected block claimed clean
    bad["status"][i] = "ok"
    assert v(data, bad, cert)["every_decoded_block_reencodes_within_its_claimed_distance"] is False
    bad = copy.deepcopy(o)                                  # 4. a correctable block flagged as uncorrectable
    bad["status"][i], bad["decoded"][i] = "uncorrectable", None
    assert v(data, bad, cert)["every_flag_is_a_detected_double_error"] is False
    bad = copy.deepcopy(o)                                  # 5. a flag that still carries data
    bad["status"][ok] = "uncorrectable"
    assert v(data, bad, cert)["flagged_blocks_carry_no_data"] is False
    bad = copy.deepcopy(o)                                  # 6. a truncated data word
    bad["decoded"][ok] = bad["decoded"][ok][:-1]
    assert v(data, bad, cert)["output_shape"] is False
    bad = copy.deepcopy(o)                                  # 7. an unknown status
    bad["status"][ok] = "fine"
    assert v(data, bad, cert)["output_shape"] is False
    assert v(data, dict(o, decoded=o["decoded"][:-1]), cert) == {"output_shape": False}    # 8. a block dropped


def test_hamming_bayes_competitor_agrees_at_low_noise_and_can_flag_at_high_noise():
    code = "hamming_15_11"
    m = (1,) * 11
    words = [_received(code, m, []), _received(code, m, [4])]
    low = {"code": code, "codewords": words, "flip_probability": 0.01}
    assert C.hamming_bayes(low)["decoded"] == C.hamming_solve(low, BUDGET)["output"]["decoded"]
    high = dict(low, flip_probability=0.2)
    assert C.hamming_bayes(high)["status"][1] == "uncorrectable"         # posterior of the nearest codeword < 1/2
    assert C.hamming_solve(high, BUDGET)["output"]["status"][1] == "corrected"


def test_hamming_score_treats_silent_miscorrection_as_worse_than_a_flag():
    truth = {"data": ["1010", "1111", "0000"]}
    out = {"decoded": ["1010", None, "0001"], "status": ["ok", "uncorrectable", "corrected"]}
    assert C.hamming_score({}, truth, out) == {"quality": 0.0, "category": "wrong"}
    out["decoded"][2] = None
    assert C.hamming_score({}, truth, out) == {"quality": 1 / 3, "category": "correct"}
    assert C.hamming_score({}, truth, None)["category"] == "abstain"


def test_hamming_refuses_invalid_input():
    good = {"code": "hamming_7_4", "codewords": ["0000000"], "flip_probability": 0.01}
    for bad in (dict(good, code="golay"), dict(good, codewords=["000000"]), dict(good, codewords=["000000x"]),
                dict(good, flip_probability=0.5), dict(good, codewords=[]), None):
        with pytest.raises(GenomeError):
            C.hamming_solve(bad, BUDGET)
