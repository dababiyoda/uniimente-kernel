"""Layer 1 basal IntelligenceGenomes: contract shape, independent verification, abstention and scoring.

Development seeds only (0-9); the held-out admission seeds (>= 1000) are never generated here.
"""
from __future__ import annotations

import copy
import json
import math

import pytest

from greg.cognition.genomes import basal, library
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

FAMILIES = ("basal_pid", "basal_kalman", "basal_hysteresis", "basal_bandit", "basal_breaker")
OPS = {"basal_pid": "pid_track", "basal_kalman": "kalman_track", "basal_hysteresis": "hysteresis_switch",
       "basal_bandit": "bandit_allocate", "basal_breaker": "circuit_break"}
_CACHE: dict = {}


def item(family):
    return {x.genome.family: x for x in basal.INTELLIGENCES}[family]


def dev(family, seed=1):
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = item(family).instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed=1):
    data, truth = dev(family, seed)
    out = item(family).solve(data, {"latency_s": 5.0, "compute": 100000})
    return data, truth, out


def _json_clean(value):
    if isinstance(value, float):
        assert math.isfinite(value)
    elif isinstance(value, dict):
        assert all(isinstance(k, str) for k in value)
        for v in value.values():
            _json_clean(v)
    elif isinstance(value, list):
        assert len(value) <= 1000
        for v in value:
            _json_clean(v)
    else:
        assert value is None or isinstance(value, (str, int, bool))


# ------------------------------------------------------------------ genome contract
def test_genomes_validate_and_are_layer_one():
    assert sorted(x.genome.family for x in basal.INTELLIGENCES) == sorted(FAMILIES)
    for x in basal.INTELLIGENCES:
        g = x.genome
        assert isinstance(g, IntelligenceGenome)
        assert g.validate() is g
        assert g.layer == 1 and g.buildability == "BUILDABLE_NOW" and g.dependency is None
        assert g.operation == OPS[g.family]
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.authority_ceiling == "read_only" and g.standalone_decision
    assert {g.genome.epistemic_class for g in basal.INTELLIGENCES if g.genome.family in
            ("basal_pid", "basal_kalman", "basal_hysteresis")} == {"physical"}
    assert {g.genome.epistemic_class for g in basal.INTELLIGENCES if g.genome.family in
            ("basal_bandit", "basal_breaker")} == {"strategic"}


def test_library_registers_basal_families_without_collisions():
    families = library.executables()
    for family in FAMILIES:
        assert families[family].genome.operation == OPS[family]
        assert library.catalog_families()[family][0] == 1


# ------------------------------------------------------------------ solve / verify
@pytest.mark.parametrize("family", FAMILIES)
def test_solve_returns_a_compact_json_answer_that_verifies(family):
    data, truth, out = solved(family)
    assert set(out) == {"output", "certificate", "status", "missing"}
    assert out["status"] == "ANSWER" and out["missing"] == []
    _json_clean(out["output"])
    _json_clean(out["certificate"])
    assert len(json.dumps(out)) < 64 * 1024
    checks = item(family).verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    score = item(family).score(data, truth, out["output"])
    assert score["category"] == "correct" and math.isfinite(score["quality"])


def _corrupt(family, output, certificate):
    out, cert = copy.deepcopy(output), copy.deepcopy(certificate)
    if family == "basal_pid":
        out["kc"] *= 1.5
    elif family == "basal_kalman":
        out["positions"][len(out["positions"]) // 2] += 1.0
    elif family == "basal_hysteresis":
        k = len(out["states"]) // 3
        out["states"] = out["states"][:k] + ("1" if out["states"][k] == "0" else "0") + out["states"][k + 1:]
    elif family == "basal_bandit":
        seq = out["sequence"]
        i = next(i for i in range(1, len(seq)) if seq[i] != seq[0])
        seq[0], seq[i] = seq[i], seq[0]
    elif family == "basal_breaker":
        k = out["decisions"].index("0")
        out["decisions"] = out["decisions"][:k] + "1" + out["decisions"][k + 1:]
    return out, cert


@pytest.mark.parametrize("family", FAMILIES)
def test_verify_refutes_a_corrupted_output(family):
    data, _, out = solved(family)
    bad, cert = _corrupt(family, out["output"], out["certificate"])
    checks = item(family).verify(data, bad, cert)
    assert not all(checks.values()), checks


def test_pid_verify_refutes_a_false_performance_claim():
    data, _, out = solved("basal_pid")
    cert = dict(out["certificate"], iae=out["certificate"]["iae"] * 0.5)
    assert not item("basal_pid").verify(data, out["output"], cert)["iae_recomputed"]


def test_pid_stability_is_checked_two_independent_ways():
    data, _, out = solved("basal_pid")
    p = basal._pid_inputs(data)
    ctrl = basal._pid_controller(out["output"])
    assert abs(basal._pid_spectral_radius_poly(p, ctrl) - basal._pid_eig_radius(p, ctrl)) < 1e-6
    hot = dict(ctrl, kc=ctrl["kc"] * 40)
    assert basal._pid_spectral_radius_poly(p, hot) >= 1.0 and basal._pid_eig_radius(p, hot) >= 1.0


def test_bandit_verify_replays_the_declared_sampler():
    data, _, out = solved("basal_bandit")
    cert = dict(out["certificate"], seed=out["certificate"]["seed"] + 1)
    assert not item("basal_bandit").verify(data, out["output"], cert)["sampler_replayed"]


def test_breaker_verify_rejects_undeclared_thresholds():
    data, _, out = solved("basal_breaker")
    bad = copy.deepcopy(out["output"])
    bad["params"]["cooldown"] += 1
    assert not item("basal_breaker").verify(data, bad, out["certificate"])["declared_thresholds"]


# ------------------------------------------------------------------ invalid input
INVALID = {
    "basal_pid": [lambda d: d.update(gain=0.0), lambda d: d.update(u_min=5.0), lambda d: d.update(steps=20_000),
                  lambda d: d.update(setpoints=[[1.0, 2.0]]), lambda d: d.update(noise_sd=float("nan")),
                  lambda d: d.update(theta=(basal.PID_MAX_DELAY + 1) * d["dt"])],
    "basal_kalman": [lambda d: d.update(measurements=[1.0, 2.0]), lambda d: d.update(dt=-1.0),
                     lambda d: d["measurements"].__setitem__(0, "x"), lambda d: d.update(r=float("inf"))],
    "basal_hysteresis": [lambda d: d.update(levels=[1.0, 0.0]), lambda d: d.update(signal=[0.0] * 5),
                         lambda d: d.update(initial_state=2), lambda d: d.update(threshold=1e6)],
    "basal_bandit": [lambda d: d.update(horizon=5000), lambda d: d["outcomes"][0].pop(),
                     lambda d: d.update(outcomes=[[0, 1]]), lambda d: d["outcomes"][0].__setitem__(0, 2)],
    "basal_breaker": [lambda d: d.update(outcomes="0120"), lambda d: d.update(background_failure=1.5),
                      lambda d: d.update(costs=[1, 2]), lambda d: d.update(seed=-1)],
}


@pytest.mark.parametrize("family", FAMILIES)
def test_invalid_input_raises_genome_error(family):
    for mutate in INVALID[family]:
        data, _ = dev(family)
        mutate(data)
        with pytest.raises(GenomeError):
            item(family).solve(data, {})
    with pytest.raises(GenomeError):
        item(family).solve("not a dict", {})


# ------------------------------------------------------------------ abstention (counterindications)
def _abstains(family, data):
    out = item(family).solve(data, {})
    assert out["status"] == "ABSTAIN" and out["output"] is None and out["missing"], out
    _json_clean(out["certificate"])
    return out


def test_pid_abstains_outside_its_competence():
    data, _ = dev("basal_pid")
    _abstains("basal_pid", dict(data, theta=11.0 * data["tau"]))                       # dead-time dominated
    _abstains("basal_pid", dict(data, u_max=1.2))                                       # unreachable setpoint
    _abstains("basal_pid", dict(data, theta=0.0))                                       # no tau_c for zero delay
    assert item("basal_pid").solve(dict(data, theta=0.0, tau_c=data["tau"] / 4), {})["status"] == "ANSWER"


def test_kalman_abstains_without_or_against_its_noise_model():
    data, _ = dev("basal_kalman")
    _abstains("basal_kalman", {k: v for k, v in data.items() if k != "r"})
    out = _abstains("basal_kalman", dict(data, r=data["r"] / 100.0))                    # NIS test rejects
    assert "innovation" in out["missing"][0]


def test_hysteresis_abstains_without_noise_or_when_noise_swamps_the_levels():
    data, _ = dev("basal_hysteresis")
    _abstains("basal_hysteresis", {k: v for k, v in data.items() if k != "noise_sd"})
    sep = data["levels"][1] - data["levels"][0]
    _abstains("basal_hysteresis", dict(data, noise_sd=5.0 * sep))


def test_bandit_abstains_on_non_bernoulli_or_non_stationary_arms():
    data, _ = dev("basal_bandit")
    _abstains("basal_bandit", dict(data, stationary=False))
    data["outcomes"][0][0] = 0.5
    _abstains("basal_bandit", data)


def test_breaker_abstains_without_a_profile_or_on_a_mostly_failing_dependency():
    data, _ = dev("basal_breaker")
    _abstains("basal_breaker", dict(data, background_failure=0.6))
    _abstains("basal_breaker", {k: v for k, v in data.items() if k != "mean_outage"})


# ------------------------------------------------------------------ scoring
def _false_answer(family, data, truth):
    if family == "basal_pid":
        return {"law": "pid", "kc": 40 * basal.simc_pi(basal._pid_inputs(data))[0]["kc"], "ti": 1.0}
    if family == "basal_kalman":
        return {"positions": [x + 10.0 * math.sqrt(data["r"]) for x in truth["positions"]]}
    if family == "basal_hysteresis":
        return {"states": ("01" * len(data["signal"]))[:len(data["signal"])]}
    if family == "basal_bandit":
        worst = truth["means"].index(min(truth["means"]))
        assert max(truth["means"]) - min(truth["means"]) >= basal.BANDIT_WRONG_GAP
        return {"sequence": [worst] * data["horizon"]}
    return {"decisions": "0" * len(data["outcomes"])}


@pytest.mark.parametrize("family", FAMILIES)
def test_score_categories(family):
    data, truth, out = solved(family)
    x = item(family)
    abstain = x.score(data, truth, None)
    correct = x.score(data, truth, out["output"])
    wrong = x.score(data, truth, _false_answer(family, data, truth))
    malformed = x.score(data, truth, {"nothing": True})
    assert abstain["category"] == "abstain" and correct["category"] == "correct"
    assert wrong["category"] == "wrong" and malformed["category"] == "wrong"
    assert wrong["quality"] <= abstain["quality"] - 1.0 and malformed["quality"] <= abstain["quality"] - 1.0
    assert correct["quality"] > wrong["quality"]
    for arm in (x.baseline(data), x.competitor(data)):
        s = x.score(data, truth, arm)
        assert s["category"] in ("correct", "wrong", "abstain") and math.isfinite(s["quality"])


def test_candidates_beat_their_baselines_on_a_dev_instance():
    for family in ("basal_pid", "basal_kalman", "basal_breaker"):
        data, truth, out = solved(family)
        x = item(family)
        assert x.score(data, truth, out["output"])["quality"] > x.score(data, truth, x.baseline(data))["quality"]


def test_solves_are_deterministic():
    for family in FAMILIES:
        assert solved(family, 2)[2] == solved(family, 2)[2]


# ------------------------------------------------------------------ adversarial review 2026-10-09
def verify(family, data, output, certificate):
    return item(family).verify(data, output, certificate)


def test_declared_competitors_are_the_reviewed_strongest_alternatives():
    assert item("basal_pid").competitor is basal.pid_sim_optimised
    assert item("basal_kalman").competitor is basal.kalman_alpha_beta
    assert item("basal_hysteresis").competitor is basal.hysteresis_hmm
    assert item("basal_bandit").competitor is basal.bandit_klucb_plus
    assert item("basal_breaker").competitor is basal.breaker_consecutive
    for family in FAMILIES:
        assert item(family).notes.get("alternative_competitor")


def test_reviewed_competitors_answer_in_contract_and_deterministically():
    for family in FAMILIES:
        data, truth = dev(family, 3)
        x = item(family)
        comp = x.competitor(data)
        _json_clean(comp)
        assert x.score(data, truth, comp)["category"] == "correct"
        assert x.competitor(copy.deepcopy(data)) == comp


@pytest.mark.parametrize("family", FAMILIES)
def test_verify_fails_closed_on_an_empty_certificate(family):
    data, _, out = solved(family)
    checks = verify(family, data, out["output"], {})
    assert checks and not all(checks.values()), checks


def test_pid_verify_refutes_a_self_consistent_unstable_controller():
    data, _, out = solved("basal_pid")
    p = basal._pid_inputs(data)
    hot = dict(out["output"], kc=out["output"]["kc"] * 40)
    ctrl = basal._pid_controller(hot)
    sim = basal._pid_judge(p, ctrl)
    cert = dict(out["certificate"], iae=sim["iae"], effort_tv=sim["effort_tv"], cost=sim["cost"],
                max_abs_error=sim["max_abs_error"], longest_limit_run=sim["longest_limit_run"],
                closed_loop_spectral_radius=basal._pid_eig_radius(p, ctrl))
    checks = verify("basal_pid", data, hot, cert)
    assert checks["iae_recomputed"] and checks["cost_recomputed"]       # the performance numbers are honest
    assert not checks["linear_loop_stable"] and not checks["declared_rule"]


def test_pid_verify_recomputes_settling_and_limit_runs():
    data, _, out = solved("basal_pid")
    cert = out["certificate"]
    settle = list(cert["settling_time"])
    i = next(i for i, v in enumerate(settle) if v is not None)
    settle[i] += 10 * data["dt"]
    assert not verify("basal_pid", data, out["output"], dict(cert, settling_time=settle))["steps_recomputed"]
    bumped = dict(cert, longest_limit_run=cert["longest_limit_run"] + 1)
    assert not verify("basal_pid", data, out["output"], bumped)["limit_run_recomputed"]


def test_pid_abstains_instead_of_emitting_gains_its_verifier_refutes():
    slow = {"gain": 1.0, "tau": 1000.0, "theta": 0.5, "dt": 0.1, "steps": 500,
            "setpoints": [[0.0, 1.0], [5.0, 2.0]], "noise_sd": 0.001, "u_min": -0.5, "u_max": 3.5, "u0": 1.0,
            "seed": 3}
    out = _abstains("basal_pid", slow)                                  # the actuator saturates all horizon
    assert "saturation" in out["missing"][0]
    data, _ = dev("basal_pid")
    out = _abstains("basal_pid", dict(data, theta=0.0, tau_c=1e-9, tau=1000.0))
    assert "controller contract" in out["missing"][0]


def test_pid_worst_case_dead_time_stays_bounded():
    import time
    data = {"gain": 1.0, "tau": 1000.0, "theta": basal.PID_MAX_DELAY * 0.1, "dt": 0.1, "steps": 2000,
            "setpoints": [[0.0, 1.0], [20.0, 1.1]], "noise_sd": 0.001, "u_min": -0.5, "u_max": 3.5, "u0": 1.0,
            "seed": 3}
    started = time.perf_counter()
    out = item("basal_pid").solve(data, {})
    assert time.perf_counter() - started < 2.0
    assert out["status"] in ("ANSWER", "ABSTAIN")
    _json_clean(out["certificate"])


def test_kalman_verify_refutes_a_wrong_velocity_and_a_filter_for_another_model():
    data, _, out = solved("basal_kalman")
    cert = out["certificate"]
    bad = dict(out["output"], final_velocity=out["output"]["final_velocity"] + 1.0)
    assert not verify("basal_kalman", data, bad, cert)["final_velocity_recomputed"]
    dt, zs, q, r, prior = basal._kf_inputs(data)
    est, v, p11, nis, updates, _ = basal._kf_scalar(dt, zs, 100.0 * q, r, prior)
    other = {"positions": est, "final_velocity": v, "final_position_variance": p11}
    checks = verify("basal_kalman", data, other, dict(cert, nis_sum=nis))
    assert not checks["estimates_recomputed"] and not checks["nis_recomputed"]


def test_hysteresis_verify_refutes_a_valid_trace_with_an_undeclared_design():
    data, _, out = solved("basal_hysteresis")
    thr = data["threshold"]
    states, switches = basal._schmitt_run(data["signal"], thr, thr, 1, data["initial_state"])
    cert = dict(out["certificate"], upper=thr, lower=thr, hysteresis=0.0, confirm=1)
    checks = verify("basal_hysteresis", data, {"states": states, "switch_count": len(switches)}, cert)
    assert checks["switches_justified"] and checks["band_centered"]     # a genuine single-threshold trace
    assert not checks["declared_design_optimal"]                        # but not the declared optimal design
    inflated = dict(out["certificate"], expected_cost_per_change=out["certificate"]["expected_cost_per_change"] * 2)
    assert not verify("basal_hysteresis", data, out["output"], inflated)["declared_design_optimal"]


def test_hysteresis_design_check_agrees_with_the_solver_closed_form():
    data, _, out = solved("basal_hysteresis")
    sig, lo, hi, thr, sigma, dwell, s0 = basal._hy_inputs(data)
    cert = out["certificate"]
    independent = basal._hy_design_cost_check(lo, hi, thr, sigma, dwell, cert["hysteresis"], cert["confirm"])
    assert math.isclose(independent, cert["expected_cost_per_change"], rel_tol=1e-9)


def test_bandit_verify_recomputes_posterior_and_digest():
    data, _, out = solved("basal_bandit")
    cert = out["certificate"]
    post = copy.deepcopy(cert["posterior"])
    post[0][0] += 1
    assert not verify("basal_bandit", data, out["output"], dict(cert, posterior=post))["posterior_recomputed"]
    assert not verify("basal_bandit", data, out["output"], dict(cert, trace_digest="0" * 64))["trace_digest_bound"]


def test_breaker_verify_recomputes_observed_successes():
    data, _, out = solved("basal_breaker")
    cert = dict(out["certificate"], successes_observed=out["certificate"]["successes_observed"] + 1)
    assert not verify("basal_breaker", data, out["output"], cert)["successes_recomputed"]
