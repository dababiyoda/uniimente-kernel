"""repair-1, the declared design pilot for develop_repair as a P8 target (scripts/p8_repair1_pilot.py).

Development seeds 0-9 only: a test never generates a review seed.
"""
from __future__ import annotations

import importlib.util
import inspect
import math

import pytest

from greg.cognition import evolution as E
from greg.cognition.genomes import developmental as D

_SPEC = importlib.util.spec_from_file_location("p8_repair1_pilot", E.ROOT / "scripts" / "p8_repair1_pilot.py")
P = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(P)
DESIGN = E.ROOT / "docs/evidence/greg-protected-evolution/2026-10-21-repair-1/DESIGN.md"


def test_the_pilot_gate_is_the_cycles_stress_summary_and_stress_worsened(monkeypatch):
    """The simulated adversarial gate calls evolution.stress_summary on item-level losses and stress_worsened on
    each kind's record, and outputs_verified on the candidate's answers; the cycle makes the same three calls."""
    cycle = inspect.getsource(E.cycle)
    assert "adversarial = stress_summary(inc_s, cand_s)" in cycle and "stress_worsened(v)" in cycle
    assert "verified = outputs_verified(spec.verify, stress._items, cand_run[\"outputs\"])" in cycle
    seen = {}
    real_summary, real_worsened, real_verified = E.stress_summary, E.stress_worsened, E.outputs_verified

    def summary(inc, cand):
        seen["summary"] = (dict(inc), dict(cand))
        return real_summary(inc, cand)

    def worsened(kind):
        seen.setdefault("worsened", []).append(kind)
        return real_worsened(kind)

    def verified(verify, its, outputs):
        seen["verify"] = verify
        return real_verified(verify, its, outputs)
    monkeypatch.setattr(E, "stress_summary", summary)
    monkeypatch.setattr(E, "stress_worsened", worsened)
    monkeypatch.setattr(E, "outputs_verified", verified)
    pilot = P.Pilot(workers=1)
    stress = E._repair_stress(P.items((0,)))
    config = {**D.REPAIR_DEFAULT_CONFIG, "wave_period": 12, "repeats": 2}
    g = P.gate(pilot, config, stress)
    assert set(seen["summary"][0]) == set(stress) and all(isinstance(v, float) for v in seen["summary"][0].values())
    assert len(seen["worsened"]) == 2 and g["adversarial"] == real_summary(*seen["summary"])
    assert seen["verify"] is D.repair_verify
    assert not hasattr(P, "stress_kinds") and "def stress_worsened" not in inspect.getsource(P)   # no replica


def test_gate_on_development_items_matches_a_direct_computation():
    pilot = P.Pilot(workers=1)
    stress = E._repair_stress(P.items((0, 1)))
    config = {"wave_period": 12, "expiry_waves": 3, "repeats": 1, "retract_repeats": 1}
    g = P.gate(pilot, config, stress)
    inc_s, cand_s = pilot.losses(pilot.target.incumbent, stress), pilot.losses(config, stress)
    assert g["adversarial"] == E.stress_summary(inc_s, cand_s)
    assert g["passes_gate"] == (g["all_outputs_verified"]
                                and not any(E.stress_worsened(v) for v in g["adversarial"].values()))
    assert g["all_outputs_verified"] == E.outputs_verified(D.repair_verify, stress, pilot.run(config, stress))


def test_the_pilot_loss_is_the_cycles_sealed_loss():
    pilot = P.Pilot(workers=1)
    its = P.items((2, 3))
    config = {**D.REPAIR_DEFAULT_CONFIG, "expiry_waves": 1}
    outputs = {k: {"output": D.repair_solve_with(config, v["data"])["output"]} for k, v in its.items()}
    assert pilot.losses(config, its) == E.SealedEvaluator(its, D.repair_score).losses(outputs)
    base = {k: {"output": D.repair_no_repair(v["data"])} for k, v in its.items()}
    assert pilot.losses("no_repair", its) == E.SealedEvaluator(its, D.repair_score).losses(base)
    assert pilot.evaluations == 2 and pilot.baseline_evaluations == 2


# ------------------------------------------------------------------ the declaration
@pytest.mark.parametrize("seed", [-1, 10, 1000, 1029, 1100, 1200, 1399, 1400, 2999, 4000, 4999, 5001, 6501, 7000,
                                  8840, 9199, 9300, True, 3000.0])
def test_the_pilot_refuses_every_seed_outside_its_review_range(seed, monkeypatch):
    def refuse(s):
        raise AssertionError(f"generated instance {s}")
    monkeypatch.setattr(D, "repair_instance", refuse)
    with pytest.raises(P.PilotError, match="review seeds 3000-3999"):
        P.items([3000, seed])


def test_the_declared_seeds_are_disjoint_unused_review_seeds():
    from greg.cognition.genomes import admission
    train = [s for seeds in P.TRAIN_SETS.values() for s in seeds]
    assert len(train) == len(set(train)) == 360 and not set(train) & set(P.POOL) and len(P.POOL) == 640
    every = set(train) | set(P.POOL)
    assert every == set(range(3000, 4000)) and not every & P.forbidden_seeds()
    assert not every & (set(admission.P8_RESERVED) | set(admission.HELDOUT_SEEDS) | admission.spent_seeds())
    assert all(len(v) == 120 for v in P.TRAIN_SETS.values()) and P.guard(P.POOL) == P.POOL


def test_the_exposure_ledger_shows_the_review_seeds_unused_for_the_repair_generator():
    import sys
    sys.path.insert(0, str(E.ROOT / "scripts"))
    import data_exposure_ledger as L
    ledger = L.load()
    assert L.exposed("develop_repair", range(3000, 4000), ledger) == []
    assert L.exposed("greg.cognition.genomes.developmental:repair_instance", range(3000, 4000), ledger) == []
    used = {s for rec in L.exposed("develop_repair", range(0, 100_000), ledger) for lo, hi in rec["seeds"]
            for s in range(lo, hi + 1)}
    assert used == set(range(10)) | set(range(1000, 1030)) | set(range(1100, 1130))


def test_the_pilot_draws_the_generator_p8_cycles_would_draw():
    assert P.items((4,))["r4"] == E.repair_item(4)
    assert inspect.getsource(E.repair_split).count("repair_item(s)") == 2


def test_the_informed_configurations_are_labelled_comparators_inside_the_space():
    target = E.repair_target()
    ids = set()
    for entry in P.INFORMED:
        assert entry["label"].startswith("informed:")
        config = target.validate(entry["config"])
        assert config != target.incumbent
        ids.add(E.config_id(config))
    assert len(ids) == len(P.INFORMED)


def test_clopper_pearson_never_reports_zero_risk_from_zero_errors():
    assert P.clopper_pearson_upper(0, 120) == pytest.approx(1 - 0.05 ** (1 / 120))
    assert P.clopper_pearson_upper(0, 480) > 0.006
    assert P.errors({"a": math.inf, "b": -0.5})["wrong"] == 1


def _sim(rates, triggered=True, complete=True):
    runs = [{"settings": {"train": t, "size": 120, "search": s}, "stages": {"triggered": triggered},
             "resampled_retain": [{"n": n, "retain_rate_alpha": r(n), "retain_rate_programme_7": r(n) / 2}
                                  for n in P.RESAMPLE_SIZES]}
            for s, r in rates.items() for t in P.TRAIN_SETS]
    return {"runs": runs, "complete": complete}


def test_the_choice_takes_the_largest_viable_heldout_size_never_a_smaller_one():
    sim = _sim({"mutate-incumbent/1": lambda n: 0.5 if n <= 240 else 0.1,
                "cover/1": lambda n: 0.6 if n <= 120 else 0.05})
    d = P.choose(sim)
    assert d["verdict"] == "VIABLE" and d["choice"]["heldout_size"] == 240
    assert d["choice"]["search"] == "mutate-incumbent/1"
    assert d["choice"]["zero_violation_upper_95_at_n"] == pytest.approx(1 - 0.05 ** (1 / 240), abs=1e-6)
    assert P.choose(_sim({"cover/1": lambda n: 0.29, "mutate-incumbent/1": lambda n: 0.2}))["verdict"] == "NOT_VIABLE"
    assert P.choose(_sim({"cover/1": lambda n: 0.9, "mutate-incumbent/1": lambda n: 0.9},
                         complete=False))["verdict"] == "NOT_VIABLE"
    assert P.choose(_sim({"cover/1": lambda n: 0.9, "mutate-incumbent/1": lambda n: 0.9},
                         triggered=False))["verdict"] == "NOT_VIABLE"
    assert P.THRESHOLDS == {"alpha": 0.05, "programme_7": 0.05 / 7}


def test_the_declared_limits_stop_the_pilot():
    pilot = P.Pilot(workers=1, limits={"evaluations": 0, "seconds": 3600})
    pilot.evaluations = 1
    with pytest.raises(P.LimitExceeded):
        pilot.check_limits()
    assert len(P.SIMULATIONS) == 6 and {s["size"] for s in P.SIMULATIONS} == {120}


def test_a_small_region_and_simulation_on_development_seeds(monkeypatch):
    monkeypatch.setattr(P, "POOL", (0, 1, 2))
    monkeypatch.setattr(P, "TRAIN_SETS", {"T1": (3, 4), "T2": (5, 6), "T3": (7, 8)})
    monkeypatch.setattr(P, "INFORMED", P.INFORMED[:1])
    monkeypatch.setattr(P, "DRAWS", 20)
    monkeypatch.setattr(P, "GENERATIONS", 2)
    pilot = P.Pilot(workers=1)
    reg = P.region(pilot=pilot)
    (row,) = reg["rows"]
    assert row["informed_by_prior_observations"] and set(row["gate"]) == {"T1", "T2", "T3"}
    assert set(reg["baselines"]) == {"no_repair", "replanner"} and set(reg["trigger"]) == {"T1", "T2", "T3"}
    assert set(reg["trigger"]["T1"]) == {"rule_no_repair", "diagnostic_replanner", "fires"}
    sim = P.simulate(({"train": "T1", "size": 2, "search": "mutate-incumbent/1"},), pilot=pilot)
    (run,) = sim["runs"]
    assert set(run["stages"]) == {"triggered", "advances", "adversarial_passes"}
    assert [r["n"] for r in run["resampled_retain"]] == list(P.RESAMPLE_SIZES)
    if not all(run["stages"].values()):
        assert all(r["retain_rate_alpha"] == 0.0 for r in run["resampled_retain"])


def test_design_md_states_the_declared_constants():
    text = DESIGN.read_text()
    for needle in ("3000-3119", "3120-3239", "3240-3359", "3360-3999", "20261023", "0.30", "120, 240, 360, 480",
                   "stress_summary", "stress_worsened", "outputs_verified", "80,000", "20,000", "0.05/7",
                   "repair_no_repair", "INFORMED BY PRIOR OBSERVATIONS", "LARGEST"):
        assert needle in text, needle
    for entry in P.INFORMED:
        assert entry["label"] in text, entry["label"]
