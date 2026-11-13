"""The P8 cycle-5 design pilot (scripts/p8_cr_pilot.py): review seeds only, the cycle's own loss and search."""
from __future__ import annotations

import importlib.util
import json
import math

import pytest

from greg.cognition import evolution as E
from greg.cognition.genomes import admission, developmental as D

_SPEC = importlib.util.spec_from_file_location("p8_cr_pilot", E.ROOT / "scripts" / "p8_cr_pilot.py")
P = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(P)


@pytest.mark.parametrize("seed", [7000, 7600, 7789, 8059, 1000, 1029, 1200, 2999, 4000, True, 3000.0])
def test_the_pilot_refuses_every_seed_outside_the_review_range(seed, monkeypatch):
    def refuse(s):
        raise AssertionError(f"generated instance {s}")
    monkeypatch.setattr(D, "constraint_release_instance", refuse)
    with pytest.raises(P.PilotError, match="review seeds 3000-3999"):
        P.items([3000, seed])
    with pytest.raises(P.PilotError):
        P.main(["grid", "--train", f"{seed}-{seed}" if type(seed) is int else "3000-3000", "--test", "4000-4001",
                "--out", "/dev/null"])


def test_the_pilot_defaults_are_review_seeds_disjoint_from_every_p8_and_admission_seed():
    seeds = set(P.PILOT_TRAIN) | set(P.PILOT_TEST)
    assert seeds <= set(range(3000, 4000)) and not set(P.PILOT_TRAIN) & set(P.PILOT_TEST)
    assert not seeds & (set(admission.P8_RESERVED) | set(admission.HELDOUT_SEEDS) | admission.spent_seeds())
    assert P.guard(P.PILOT_TRAIN) == P.PILOT_TRAIN


def test_pilot_losses_are_the_sealed_evaluators_losses_on_the_sandboxs_method():
    pilot = P.Pilot()
    its = P.items((0, 1))                                    # development seeds
    config = {**D.CR_DEFAULT_CONFIG, "p_restart": 0.5}
    got = pilot.losses(config, its)
    outputs = {k: {"output": D.constraint_release_solve_with(config, v["data"])["output"]} for k, v in its.items()}
    assert got == E.SealedEvaluator(its, D.constraint_release_score).losses(outputs)
    base = pilot.losses("random_restart", its)
    assert base == E.SealedEvaluator(its, D.constraint_release_score).losses(
        {k: {"output": D.constraint_release_random_restart(v["data"])} for k, v in its.items()})
    before = pilot.evaluations
    assert pilot.losses(config, its) == got and pilot.evaluations == before        # memoised
    stress = E._cr_stress(its)                               # same ids' derivations are told apart by their data
    assert set(pilot.losses(config, stress)) == set(stress) and pilot.evaluations == before + len(stress)


def test_an_answer_that_raises_counts_as_an_abstention_as_in_the_sandbox(monkeypatch):
    pilot = P.Pilot()
    its = P.items((2,))

    def broken(config, data):
        raise TypeError("boom")
    monkeypatch.setattr(D, "constraint_release_solve_with", broken)
    assert pilot.losses(dict(D.CR_DEFAULT_CONFIG), its) == {"r2": 1.0}


def test_a_small_grid_and_simulation_report_the_cycle_rules_stages():
    grid = P.grid((0, 1), (2, 3), configs=[dict(D.CR_DEFAULT_CONFIG), {**D.CR_DEFAULT_CONFIG, "p_restart": 1.0}],
                  cycle4=False)
    assert [r["config"]["p_restart"] for r in grid["rows"]] == [0.0, 1.0]
    incumbent_row = grid["rows"][0]
    for half in ("pilot_train", "pilot_test"):
        assert incumbent_row[half]["mean_loss"] == grid["summary"][half]["incumbent_mean_loss"]
        assert incumbent_row[half]["vs_incumbent"]["wins"] == incumbent_row[half]["vs_incumbent"]["losses"] == 0
    assert set(incumbent_row["stress"]) == {"lean", "fewval", "passes_gate"} and incumbent_row["stress"]["passes_gate"]
    sim = P.simulate((0, 1), (2, 3), settings=[
        {"generations": 2, "population": 2, "seed": 5, "search": "mutate-incumbent/1"},
        {"generations": 2, "population": 2, "seed": 5, "search": "cover/1", "lhs": 2}])
    plain, cover = sim["runs"]
    assert plain["declared_initial"] == 0 and cover["declared_initial"] == len(
        E.search_setting(E.cr_target(), "cover/1", seed=5, lhs=2)["initial"])
    assert cover["evaluated"] > plain["evaluated"]
    for run in sim["runs"]:
        assert set(run["stages"]) >= {"triggered", "advances", "adversarial_passes", "heldout_passes"}
        assert run["would_decide"] in ("NO_RECURRING_FAILURE", "RETAIN", "REJECT")
        assert math.isfinite(run["incumbent_train_mean_loss"])
    json.dumps(sim)


def test_the_cycle_4_lineage_is_read_from_its_record_without_generating_its_split():
    steps = P.cycle_4_configs()
    record = json.loads(P.CYCLE_4_RECORD.read_text())
    assert [s["id"] for s in steps] == [s["id"] for s in record["search"]["lineage"]] and len(steps) == 39
    assert all(E.config_id(E.cr_target().validate(s["config"])) == s["id"] for s in steps)


def test_the_resampled_decision_applies_both_held_out_conditions():
    better = {f"r{i}": 0.0 for i in range(40)}
    worse = {f"r{i}": 0.01 for i in range(40)}
    assert P.resampled_decision(better, worse, 90, draws=50)["retain_rate"] == 1.0
    assert P.resampled_decision(worse, better, 90, draws=50)["retain_rate"] == 0.0
    assert P.resampled_decision(better, better, 90, draws=50)["retain_rate"] == 0.0           # all ties
    # more wins but a heavier tail: the sign test passes, the mean does not, so the rule would not retain
    tail = {**{f"r{i}": 0.0 for i in range(30)}, **{f"r{i}": 1.0 for i in range(30, 40)}}
    flat = {f"r{i}": 0.05 for i in range(40)}
    once = P.resampled_decision(tail, flat, 90, draws=200)
    assert once == P.resampled_decision(tail, flat, 90, draws=200) and once["retain_rate"] < 0.05
    assert once["retain_rate_at_alpha_over_3"] <= once["retain_rate"]


def test_region_and_a_pool_look_use_fresh_review_seeds_only(monkeypatch):
    out = P.region((0, 1), [{"config": {**D.CR_DEFAULT_CONFIG, "p_restart": 1.0}, "why": "test"}])
    assert [r["id"] for r in out["rows"]][0] == "random_restart" and len(out["rows"]) == 2
    assert set(out["rows"][1]["losses"]) == set(out["incumbent"]["losses"]) == {"r0", "r1"}
    assert [r["n"] for r in out["rows"][1]["resampled"]] == [90, 180]
    with pytest.raises(P.PilotError, match="fresh"):
        P.simulate((0, 1), (2, 3), settings=[], pool_seeds=(1, 4))
    with pytest.raises(P.PilotError, match="review seeds"):
        P.region((7700,), [])


def test_spearman_uses_average_ranks():
    assert P.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert P.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert P.spearman([1, 1, 2, 3], [1, 2, 3, 4]) == pytest.approx(0.9486832980505138)   # tied ranks averaged


PILOT_DIR = E.EVIDENCE / "2026-10-16-cr-5" / "pilot"


def test_the_committed_pilot_summary_is_derived_from_the_committed_pilot_files():
    """The pre-registration's numbers come from pilot/summary.json, which the script re-derives exactly."""
    committed = json.loads((PILOT_DIR / "summary.json").read_text())
    assert json.loads(json.dumps(P.summarise(PILOT_DIR))) == committed
    grid = committed["grid"]
    assert grid["configurations"] == 140 and len(grid["pass_both_halves"]) == 9
    assert committed["region"]["seeds"] == {"pool": [3200, 3499]}
    seeds = [s for run in committed["simulated"]["runs"] for s in run["train"]]
    assert all(3000 <= s <= 3999 for s in seeds)                                  # review seeds only
    chosen = committed["simulated"]["by_policy"]["cover/1 lhs=0 generations=5 seed=20261016"]
    assert chosen["runs"] == 6
