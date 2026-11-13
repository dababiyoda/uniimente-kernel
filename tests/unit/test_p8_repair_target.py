"""develop_repair as a protected-evolution (P8) target (step A of the repair-1 design, 2026-10-21).

Development seeds 0-9 only. Nothing here generates a review, held-out or P8-reserved instance.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import random
import subprocess
import sys

import pytest

from greg.cognition import evolution as E
from greg.cognition.genomes import developmental as D
from greg.cognition.genomes import library

DEV = tuple(range(10))
BASE = "6cb7c319"                     # the commit before the configuration hook (develop_repair 1.1.1)
# sha256 of json.dumps(repair_solve(data, {}), sort_keys=True) at BASE, on development seeds 0-9 and three
# perturbations of seed 0 that reach both abstention paths and the validated maximum message loss
GOLDEN = {
    0: "2440d62f41feeb6703cfdba3da0db6e3ab7d076f861e6f8b20c23a992e85f35c",
    1: "5e6b2f8e03d2f12c7bfce9b170f5b37a16ff09944d4776cbbad50fa2d04e75bb",
    2: "bf3f0a8769f08eb3d011034b47905fd724ff480fb6efd804329f13967592602e",
    3: "3c2a38ff3bce7f16f7e381d0516f103b827070ace4090ba4eb5578eb9df42978",
    4: "c6e69df4c94c5934425214ffafe29bd266bf77bdfec3a678071075acb9080325",
    5: "6f469150997bc449af3658d8b59b13110a8e5c7261fe3f55583faea504b90c7e",
    6: "fab93fc24c0f6f02a3cdffaf331d572b6da45faed1dbbe0c28c3d9c014a55b4f",
    7: "b1645c4497452e67dcd9b3b21cdf1b94a2a219d090affce1c7956028d5a5ecc0",
    8: "0315b867862c8af7ef3d5b6891ad88d908db6ff9e4890842a237bae390c80371",
    9: "5d328703df821a094120a50de586556fcd80310c71abf7a22e40970d0c16f50d",
    "loss0.6": "0097ea1f239ba30a741946ae8a752fd78bafb41ac0e6a9239e85028751432552",
    "steps40": "e96d4249572140790d48541d8f2d1b22d03bea729e4bfb297b4b147a62459ed7",
    "loss0.5": "816a2461f127c301b59c8eec3b81998c638f0748d9d4a3fb61c5997a7ef1c56b",
}
_CACHE: dict = {}


def dev(seed):
    if seed not in _CACHE:
        _CACHE[seed] = D.repair_instance(seed)
    data, truth = _CACHE[seed]
    return copy.deepcopy(data), truth


def _inputs():
    out = {s: dev(s)[0] for s in DEV}
    data = dev(0)[0]
    out.update({"loss0.6": {**data, "message_loss": 0.6}, "steps40": {**data, "steps": 40, "events": []},
                "loss0.5": {**data, "message_loss": 0.5}})
    return out


def _sha(answer) -> str:
    return hashlib.sha256(json.dumps(answer, sort_keys=True).encode()).hexdigest()


def _axis_and_sample(n=12, seed=0):
    target = E.repair_target()
    rng = random.Random(f"test-repair-space:{seed}")
    sample = [target.validate({k: rng.choice(v) for k, (_, v) in D.REPAIR_CONFIG_SPACE.items()}) for _ in range(n)]
    return [target.incumbent, *E._axis_cover(target), *sample]


# ------------------------------------------------------------------ the default is byte-identical
@pytest.mark.parametrize("key", list(GOLDEN))
def test_the_default_configuration_is_byte_identical_to_the_code_before_the_hook(key):
    data = _inputs()[key]
    out = D.repair_solve(copy.deepcopy(data), {})
    assert _sha(out) == GOLDEN[key]
    assert D.repair_solve_with(dict(D.REPAIR_DEFAULT_CONFIG), copy.deepcopy(data)) == out
    assert out["status"] == ("ABSTAIN" if key in ("loss0.6", "steps40") else "ANSWER")


def _module_at(commit):
    blob = subprocess.run(["git", "show", f"{commit}:greg/cognition/genomes/developmental.py"], cwd=E.ROOT,
                          capture_output=True)
    if blob.returncode:
        return None
    spec = importlib.util.spec_from_loader("greg.cognition.genomes._developmental_before_hook", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "greg.cognition.genomes"
    exec(compile(blob.stdout, f"{commit}:developmental.py", "exec"), module.__dict__)
    return module


def test_the_default_equals_the_pre_hook_source_run_side_by_side():
    old = _module_at(BASE)
    if old is None:
        pytest.skip(f"{BASE} is not in this clone")
    for key, data in _inputs().items():
        assert D.repair_solve(copy.deepcopy(data), {}) == old.repair_solve(copy.deepcopy(data), {}), key


def test_the_shipped_executable_runs_the_default_through_the_sandbox_entry(monkeypatch):
    seen = []
    real = D.repair_solve_with

    def spy(config, data):
        seen.append(dict(config))
        return real(config, data)
    monkeypatch.setattr(D, "repair_solve_with", spy)
    data, _ = dev(3)
    library.executables()["develop_repair"].solve(data, {"latency_s": 5.0, "compute": 100000})
    assert seen == [D.REPAIR_DEFAULT_CONFIG]


# ------------------------------------------------------------------ the declared space
def test_the_space_is_protocol_constants_only_and_every_point_settles_within_the_benchmark():
    assert D.REPAIR_DEFAULT_CONFIG == {"wave_period": D.WAVE_PERIOD, "expiry_waves": D.EXPIRY_WAVES,
                                       "repeats": D.REPEATS, "retract_repeats": D.RETRACT_REPEATS}
    assert set(D.REPAIR_CONFIG_SPACE) == set(D.REPAIR_DEFAULT_CONFIG)
    assert not any(E.protected(k) for k in D.REPAIR_CONFIG_SPACE)
    for constant in ("action_cost", "wrong_penalty", "max_loss", "message_loss", "steps"):
        assert constant not in D.REPAIR_CONFIG_SPACE           # evaluation state and input validation stay out
    target = E.repair_target()
    assert target.validate(target.incumbent) == D.REPAIR_DEFAULT_CONFIG
    assert all(kind == "choice" for kind, _ in D.REPAIR_CONFIG_SPACE.values())
    worst = max(p for p in D.REPAIR_CONFIG_SPACE["wave_period"][1]) * (max(D.REPAIR_CONFIG_SPACE["expiry_waves"][1])
                                                                        + 1)
    assert worst + 2 * (16 + 12) <= D.BENCH_STEPS                # the benchmark's largest lattice never abstains


@pytest.mark.parametrize("bad", [{**D.REPAIR_DEFAULT_CONFIG, "wave_period": 7},
                                 {**D.REPAIR_DEFAULT_CONFIG, "repeats": True},
                                 {**D.REPAIR_DEFAULT_CONFIG, "expiry_waves": 2.0},
                                 {**D.REPAIR_DEFAULT_CONFIG, "action_cost": 0.0},
                                 {k: v for k, v in D.REPAIR_DEFAULT_CONFIG.items() if k != "repeats"},
                                 ["not", "a", "mapping"]])
def test_the_method_refuses_a_configuration_outside_the_space(bad):
    data, _ = dev(0)
    with pytest.raises(D.GenomeError):
        D.repair_solve_with(bad, data)


def test_a_configuration_changes_the_protocol_it_runs():
    data, _ = dev(0)
    base = D.repair_solve_with(D.REPAIR_DEFAULT_CONFIG, copy.deepcopy(data))
    slow = D.repair_solve_with({**D.REPAIR_DEFAULT_CONFIG, "wave_period": 12}, copy.deepcopy(data))
    assert slow["certificate"]["wave_period"] == 12 and slow["certificate"]["final_wave"] == 10
    assert slow["certificate"]["messages_per_step"] != base["certificate"]["messages_per_step"]


# ------------------------------------------------------------------ the verifier stays outcome-based
@pytest.mark.parametrize("seed", (0, 3, 7))
def test_the_verifier_accepts_exactly_the_answers_whose_claims_deliver_under_any_configuration(seed):
    """No false refutation of a configuration and no false acceptance: across the incumbent, every axis move and a
    random sample of the space, the verifier passes an answer iff its score is not wrong, and it never reads the
    protocol constants (rewriting them in the certificate leaves every check unchanged)."""
    data, truth = dev(seed)
    for config in _axis_and_sample():
        out = D.repair_solve_with(config, copy.deepcopy(data))
        if out["status"] != "ANSWER":
            continue
        checks = D.repair_verify(data, out["output"], out["certificate"])
        wrong = D.repair_score(data, truth, out["output"])["category"] == "wrong"
        assert all(checks.values()) == (not wrong), (config, checks)
        other = {**out["certificate"], "wave_period": 99, "expiry_waves": 99, "repeats": 99}
        assert D.repair_verify(data, out["output"], other) == checks


def test_the_verifier_still_refutes_a_false_claim_under_a_non_default_configuration():
    data, truth = dev(0)
    config = {"wave_period": 4, "expiry_waves": 3, "repeats": 1, "retract_repeats": 1}
    out = D.repair_solve_with(config, copy.deepcopy(data))
    claimed = out["output"]["claimed"][0]
    hop = {k: v for k, v in out["output"]["next_hop"].items() if k != claimed}      # cut the claimed chain
    forged = {**out["output"], "next_hop": hop}
    assert D.repair_verify(data, forged, out["certificate"])["every_claimed_source_delivers_on_realized_topology"] \
        is False
    assert D.repair_score(data, truth, forged)["category"] == "wrong"


# ------------------------------------------------------------------ P8 wiring and wrong-answer semantics
def test_the_target_is_registered_with_the_cycle_rule_unchanged():
    from greg.cognition import evolution_sandbox as S
    assert "develop_repair" in E.TARGET_SPECS
    assert S.TARGETS["develop_repair"] == ("greg.cognition.genomes.developmental", "repair_solve_with", ())
    spec = E.TARGET_SPECS["develop_repair"]()
    assert spec.baseline is D.repair_no_repair and spec.verify is D.repair_verify and spec.score is D.repair_score
    assert spec.proposal["constant"] == "REPAIR_DEFAULT_CONFIG"
    assert E.RULE.startswith("trigger: incumbent worse than the simple baseline on >= 25% of train items")
    assert (E.FAILURE_RATE_TRIGGER, E.TRAIN_GAIN_MIN, E.STRESS_TOLERANCE, E.ALPHA) == (0.25, 0.01, 0.05, 0.05)
    family, version, _ = E.EVOLVABLE_CONFIG_PINS["develop_repair"]
    assert (family, version) == ("develop_repair", "1.1.2")


def test_no_split_is_registered_so_no_cycle_can_run_on_this_target():
    assert E.REPAIR_SPLITS == {} and E.REPAIR_CURRENT_SPLIT is None
    with pytest.raises(E.EvolutionError, match="no develop_repair split"):
        E.repair_split()
    with pytest.raises(E.EvolutionError):
        E.freeze_inputs("develop_repair", generations=1, population=2, seed=0)


def test_a_wrong_answer_is_infinite_an_abstention_is_zero_and_an_answer_is_finite():
    data, truth = dev(0)
    item = {"a": {"data": data, "truth": truth}}
    evaluator = E.SealedEvaluator(item, D.repair_score)
    out = D.repair_solve(copy.deepcopy(data), {})["output"]
    answered = evaluator.losses({"a": {"output": out}})["a"]
    assert math.isfinite(answered) and answered < 0
    claimed = out["claimed"][0]
    forged = {**out, "next_hop": {k: v for k, v in out["next_hop"].items() if k != claimed}}
    assert D.repair_score(data, truth, forged)["quality"] > -math.inf            # finite in the genome's score ...
    assert evaluator.losses({"a": {"output": forged}})["a"] == math.inf          # ... +inf in the P8 evaluator
    assert evaluator.losses({"a": {"output": None}})["a"] == 0                   # abstention
    assert evaluator.losses({"a": {"error": "TypeError: x"}})["a"] == 0          # a sandbox error is no answer
    assert evaluator.losses({"a": {"output": {**out, "claimed": [claimed, claimed]}}})["a"] == math.inf
    assert evaluator.losses({"a": {"output": {**out, "actions": -1}}})["a"] == math.inf


def test_the_sandbox_runs_the_method_and_matches_the_parent():
    from greg import isolation
    items = {f"s{s}": E.repair_item(s) for s in (1, 2)}
    problems = [{"id": k, "data": v["data"]} for k, v in items.items()]
    config = {"wave_period": 10, "expiry_waves": 1, "repeats": 3, "retract_repeats": 4}
    run = E.run_candidate(E.repair_target(), config, problems,
                          require_confinement=isolation.available()["available"])
    for k, v in items.items():
        direct = D.repair_solve_with(config, copy.deepcopy(v["data"]))
        assert run["outputs"][k] == {"output": direct["output"], "certificate": direct["certificate"]}


# ------------------------------------------------------------------ stress derivations
def test_the_stress_sets_are_lossy_and_late_with_truth_recomputed():
    items = {f"s{s}": E.repair_item(s) for s in DEV}
    stress = E._repair_stress(items)
    assert {k.split(":")[0] for k in stress} == {"lossy", "late"} and len(stress) == 2 * len(items)
    for key, item in items.items():
        d = item["data"]
        lossy = stress[f"lossy:{key}"]["data"]
        assert lossy["message_loss"] == round(min(D.MAX_LOSS, d["message_loss"] + 0.2), 6) <= D.MAX_LOSS
        assert {k: v for k, v in lossy.items() if k != "message_loss"} == {k: v for k, v in d.items()
                                                                           if k != "message_loss"}
        late = stress[f"late:{key}"]["data"]
        assert late["events"][:-1] == d["events"]
        event = late["events"][-1]
        assert event["step"] == d["steps"] - (d["width"] + d["height"])
        assert event["step"] > max(e["step"] for e in d["events"])
        assert 1 <= len(event["fail"]) <= E.REPAIR_LATE_UNITS
        ends = {tuple(c) for c in d["sources"] + d["sinks"]}
        assert not {tuple(c) for c in event["fail"]} & ends
        D._repair_inputs(late)                                    # a valid world script
        truth = stress[f"late:{key}"]["truth"]
        assert truth["distances"] and truth == E.repair_truth(late)
        assert E.repair_truth(d)["distances"] == item["truth"]["distances"]      # the generator's own truth
    assert E._repair_stress(items) == stress                       # deterministic


def test_controller_loss_is_not_a_stress_set_because_the_local_rules_never_read_it():
    data, _ = dev(0)
    crashed = {**data, "controller": {"mode": "crash", "view_lag": 0, "crash_at": 1}}
    assert D.repair_solve(copy.deepcopy(data), {}) == D.repair_solve(copy.deepcopy(crashed), {})
