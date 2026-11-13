"""The P8 cycle-7 design pilot (scripts/p8_immune_pilot.py): immune review seeds only, the cycle's own loss,
search, stress sets and rule."""
from __future__ import annotations

import importlib.util
import math

import pytest

from greg.cognition import evolution as E
from greg.cognition.genomes import admission, collective as C

_SPEC = importlib.util.spec_from_file_location("p8_immune_pilot", E.ROOT / "scripts" / "p8_immune_pilot.py")
P = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(P)


@pytest.mark.parametrize("seed", [7000, 7039, 8000, 8059, 8599, 8600, 9199, 1000, 1200, 3000, 3059, 3099, 4000,
                                  True, 3100.0])
def test_the_pilot_refuses_every_seed_outside_its_review_range(seed, monkeypatch):
    def refuse(s):
        raise AssertionError(f"generated instance {s}")
    monkeypatch.setattr(C, "immune_gaussian_instance", refuse)
    with pytest.raises(P.PilotError, match="review seeds 3100-3999"):
        P.items([3100, seed])


def test_the_declared_seeds_are_disjoint_review_seeds():
    train = [s for seeds in P.TRAIN_SETS.values() for s in seeds]
    assert len(train) == len(set(train)) == 360 and not set(train) & set(P.POOL)
    every = set(train) | set(P.POOL)
    assert every <= set(range(3100, 4000)) and len(P.POOL) == 540
    assert not every & (set(admission.P8_RESERVED) | set(P.P8_EXTENSION) | set(admission.HELDOUT_SEEDS)
                        | admission.spent_seeds())
    assert P.guard(P.POOL) == P.POOL
    assert len(P.SIMULATIONS) == 9 and P.THRESHOLDS["programme_7"] == pytest.approx(0.05 / 7)


def test_pilot_losses_are_the_sealed_evaluators_losses_on_the_sandboxs_method():
    pilot = P.Pilot(workers=1)
    its = P.items((0, 1))                                    # development seeds
    config = {**C.IMMUNE_DEFAULT_CONFIG, "whitening": "full"}
    got = pilot.losses(config, its)
    outputs = {k: {"output": C.immune_solve_with(config, v["data"])["output"]} for k, v in its.items()}
    assert got == E.SealedEvaluator(its, C.immune_score).losses(outputs)
    base = pilot.losses("zscore", its)
    assert base == E.SealedEvaluator(its, C.immune_score).losses(
        {k: {"output": C.immune_zscore(v["data"])} for k, v in its.items()})
    before = pilot.evaluations
    assert pilot.losses(config, its) == got and pilot.evaluations == before        # memoised
    stress = E._immune_stress(its)                           # same ids' derivations are told apart by their data
    assert set(pilot.losses(config, stress)) == set(stress) and pilot.evaluations == before + len(stress)
    assert pilot.verified(config, stress)


def test_an_answer_that_raises_counts_as_an_abstention_as_in_the_sandbox(monkeypatch):
    pilot = P.Pilot(workers=1)
    its = P.items((2,))

    def broken(config, data):
        raise TypeError("boom")
    monkeypatch.setattr(C, "immune_solve_with", broken)
    assert pilot.losses(dict(C.IMMUNE_DEFAULT_CONFIG), its) == {"r2": 0.0}


def test_resampling_never_retains_when_both_means_are_infinite_or_the_candidate_is_wrong():
    inc = {f"k{i}": -0.5 for i in range(50)}
    cand = {f"k{i}": -0.6 for i in range(50)}
    assert P.resampled(cand, inc, 40)["retain_rate_alpha"] == 1.0
    assert P.resampled({**cand, "k0": math.inf}, inc, 200)["retain_rate_alpha"] < 0.05
    both = P.resampled({**cand, "k0": math.inf}, {**inc, "k0": math.inf}, 400)
    assert both["retain_rate_alpha"] < 0.05


def test_the_choice_rule_is_declared_and_refuses_a_target_without_headroom():
    def run(train, size, search, rate, triggered=True, passes=True):
        return {"settings": {"train": train, "size": size, "search": search},
                "stages": {"triggered": triggered, "advances": passes, "adversarial_passes": passes},
                "resampled_retain": [{"n": n, "retain_rate_alpha": rate, "retain_rate_target_2": rate,
                                      "retain_rate_programme_7": rate / 2} for n in P.RESAMPLE_SIZES]}
    good = {"runs": [run(t, 120, "cover/1", 0.6) for t in ("T1", "T2", "T3")]
            + [run(t, 120, "mutate-incumbent/1", 0.6) for t in ("T1", "T2", "T3")]}
    chosen = P.choose(good)
    assert chosen["verdict"] == "VIABLE" and chosen["choice"] == {"search": "cover/1", "train_size": 120,
                                                                  "heldout_size": min(P.RESAMPLE_SIZES)}
    weak = {"runs": [run(t, 120, "cover/1", 0.2) for t in ("T1", "T2", "T3")]}
    assert P.choose(weak)["verdict"] == "NOT_VIABLE" and P.choose(weak)["choice"] is None
    quiet = {"runs": [run(t, 120, "cover/1", 0.9, triggered=t == "T1") for t in ("T1", "T2", "T3")]}
    assert P.choose(quiet)["verdict"] == "NOT_VIABLE"


def test_a_small_region_and_simulation_report_the_cycle_rules_stages():
    pilot = P.Pilot(workers=1)
    reg = P.region((0, 1, 2), (3, 4), configs=[{"config": {**C.IMMUNE_DEFAULT_CONFIG, "alarm_fraction": 0.9}}],
                   pilot=pilot)
    (row,) = reg["rows"]
    assert set(row["stress"]) == {"scarce", "strict", "all_outputs_verified", "passes_gate"}
    assert row["pool"]["vs_incumbent"]["wins"] + row["pool"]["vs_incumbent"]["losses"] + \
        row["pool"]["vs_incumbent"]["ties"] == 3
    out = P.simulate_one(pilot, P.items((3, 4)), P.items((0, 1, 2)), {"train": "dev", "size": 2,
                                                                    "search": "mutate-incumbent/1"})
    assert set(out["stages"]) == {"triggered", "advances", "adversarial_passes"}
    assert out["evaluated"] >= 2 and len(out["resampled_retain"]) == len(P.RESAMPLE_SIZES)
