"""immune-8, the successor design pilot to immune-7 (scripts/p8_immune8_pilot.py)."""
from __future__ import annotations

import importlib.util
import inspect
import math

import pytest

from greg.cognition import evolution as E
from greg.cognition.genomes import collective as C

_SPEC = importlib.util.spec_from_file_location("p8_immune8_pilot", E.ROOT / "scripts" / "p8_immune8_pilot.py")
P = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(P)


def test_the_pilot_gate_is_the_merged_stress_summary_and_stress_worsened(monkeypatch):
    """The simulated adversarial gate calls evolution.stress_summary on item-level losses and stress_worsened on
    its record (the gate merged from the independent stress-gate audit, 09555108); the cycle makes the same calls."""
    cycle = inspect.getsource(E.cycle)
    assert "adversarial = stress_summary(inc_s, cand_s)" in cycle and "stress_worsened(v)" in cycle
    seen = {}
    real_summary, real_worsened = E.stress_summary, E.stress_worsened

    def summary(inc, cand):
        seen["summary"] = (dict(inc), dict(cand))
        return real_summary(inc, cand)

    def worsened(kind):
        seen.setdefault("worsened", []).append(kind)
        return real_worsened(kind)
    monkeypatch.setattr(E, "stress_summary", summary)
    monkeypatch.setattr(E, "stress_worsened", worsened)
    pilot = P.P7.Pilot(workers=1)
    stress = E._immune_stress(P.P7.items((0,)))
    g = P.gate(pilot, {**C.IMMUNE_DEFAULT_CONFIG, "whitening": "full"}, stress)
    assert set(seen["summary"][0]) == set(stress) and all(isinstance(v, float) for v in seen["summary"][0].values())
    assert seen["worsened"] and g["adversarial"] == real_summary(*seen["summary"])
    assert not hasattr(P, "adversarial_kinds")                       # no replica of the gate


def test_the_gate_counts_wrong_answers_where_the_old_means_only_gate_did_not():
    inc = {"scarce:a": math.inf, "scarce:b": -0.5, "strict:a": -0.4, "strict:b": -0.4}
    worse = {"scarce:b": math.inf, "scarce:a": math.inf, "strict:a": -0.4, "strict:b": -0.4}   # other order
    kinds = E.stress_summary(inc, worse)
    assert kinds["scarce"]["wrong"]["incumbent"] == 1 and kinds["scarce"]["wrong"]["candidate"] == 2
    assert E.stress_worsened(kinds["scarce"]) and not E.worsened(kinds["scarce"]["incumbent"],
                                                                 kinds["scarce"]["candidate"])
    assert not E.stress_worsened(kinds["strict"]) and "wrong" not in kinds["strict"]


def test_the_gate_audit_regenerates_only_immune_7s_exposed_train_items(monkeypatch):
    def refuse(seed):
        raise AssertionError(f"generated instance {seed}")
    monkeypatch.setattr(C, "immune_gaussian_instance", refuse)
    for seeds in ([3460], [4000], [8600], [3099]):
        with pytest.raises(P.PilotError):
            P._immune7_items(seeds)


def test_gate_on_development_items_matches_a_direct_computation():
    pilot = P.P7.Pilot(workers=1)
    stress = E._immune_stress(P.P7.items((0, 1)))
    config = {**C.IMMUNE_DEFAULT_CONFIG, "alarm_fraction": 0.95, "whitening": "full"}
    g = P.gate(pilot, config, stress)
    inc_s, cand_s = pilot.losses(pilot.target.incumbent, stress), pilot.losses(config, stress)
    assert g["adversarial"] == E.stress_summary(inc_s, cand_s)
    assert g["passes_fixed_gate"] == (g["all_outputs_verified"]
                                      and not any(E.stress_worsened(v) for v in g["adversarial"].values()))


# ------------------------------------------------------------------ step C: the declaration
@pytest.mark.parametrize("seed", [0 - 1, 1000, 1029, 1100, 1200, 1399, 3000, 3459, 3999, 5000, 5001, 5040, 7000, 8600,
                                  8839, 8840, 9199, True, 4000.0])
def test_the_pilot_refuses_every_seed_outside_its_review_range(seed, monkeypatch):
    def refuse(s):
        raise AssertionError(f"generated instance {s}")
    monkeypatch.setattr(C, "immune_gaussian_instance", refuse)
    with pytest.raises(P.PilotError, match="review seeds 4000-4999"):
        P.items([4000, seed])


def test_the_declared_seeds_are_disjoint_unused_review_seeds():
    from greg.cognition.genomes import admission
    train = [s for seeds in P.TRAIN_SETS.values() for s in seeds]
    assert len(train) == len(set(train)) == 360 and not set(train) & set(P.POOL) and len(P.POOL) == 640
    every = set(train) | set(P.POOL)
    assert every == set(range(4000, 5000)) and not every & P.forbidden_seeds()
    assert not every & (set(admission.P8_RESERVED) | set(admission.HELDOUT_SEEDS) | admission.spent_seeds()
                        | set(P.P7.REVIEW_SEEDS) | set(range(3000, 3100)))
    assert all(len(v) == 120 for v in P.TRAIN_SETS.values()) and P.guard(P.POOL) == P.POOL


def test_no_other_generator_rng_stream_reaches_the_declared_review_instances():
    """Exposure audit (step B): the Gaussian generator seeds Random/default_rng(7_400_000 + seed). Every other
    integer offset in the genome modules would need a seed above 90,000 (or a negative one) to reach 7_404_000-
    7_404_999; no seed range in the repository is that large."""
    import re
    source = "".join(p.read_text() for p in (E.ROOT / "greg" / "cognition" / "genomes").glob("*.py"))
    offsets = {int(m.replace("_", "")) for m in re.findall(r"(?:Random|default_rng)\(\s*([0-9_]+)\s*\+\s*seed", source)}
    assert 7_400_000 in offsets
    for c in offsets - {7_400_000}:
        needed = range(7_404_000 - c, 7_405_000 - c)
        assert needed.stop <= 0 or needed.start > 90_000, c


def test_the_narrowed_space_caps_only_alarm_fraction_at_the_incumbents_value():
    full, narrow = E.immune_search_space("full/1"), E.immune_search_space(P.SPACE)
    assert full is C.IMMUNE_CONFIG_SPACE and E.immune_target().space is C.IMMUNE_CONFIG_SPACE   # default unchanged
    assert {k: v for k, v in narrow.items() if k != "alarm_fraction"} == {
        k: v for k, v in full.items() if k != "alarm_fraction"}
    assert narrow["alarm_fraction"] == ("float", [full["alarm_fraction"][1][0], C.IMMUNE_DEFAULT_CONFIG["alarm_fraction"]])
    assert C.IMMUNE_DEFAULT_CONFIG["alarm_fraction"] == 0.75 and full["alarm_fraction"] == ("float", [0.4, 0.95])
    target = P.narrow_target()
    assert target.validate(target.incumbent) == E.immune_target().validate(target.incumbent)
    with pytest.raises(E.EvolutionError):
        target.validate({**target.incumbent, "alarm_fraction": 0.751})
    with pytest.raises(E.EvolutionError):
        E.immune_search_space("immune-8/other")
    import random
    rng = random.Random(0)
    for _ in range(200):                        # every mutant stays in the narrower space
        child, _ = E.mutate(target, target.incumbent, rng)
        assert child["alarm_fraction"] <= 0.75


def test_the_informed_configurations_are_immune_7s_recorded_rows_and_labelled():
    import json
    rows = json.loads((P.IMMUNE_7 / "pilot" / "region.json").read_text())["rows"]
    recorded = {E.config_id(E.immune_target().validate(r["config"])) for r in rows}
    for entry in P.INFORMED:
        assert entry["label"].startswith("informed:")
        assert E.config_id(E.immune_target().validate(entry["config"])) in recorded
        assert entry["inside_space"] == P._inside(entry["config"])


def test_the_confirmatory_seed_proposal_avoids_every_registered_split():
    from greg.cognition.genomes import admission
    used = set(admission.spent_seeds())
    for name, seeds in (*E.IMMUNE_SPLITS.items(), *E.CR_SPLITS.items()):
        used |= {s for part in seeds for s in part}
    used |= {s for seeds in E.CR_CANARY_SEEDS.values() for s in seeds}
    assert not used & set(range(8840, 9200)) and not used & set(range(7040, 7200))


def test_clopper_pearson_never_reports_zero_risk_from_zero_errors():
    assert P.clopper_pearson_upper(0, 120) == pytest.approx(1 - 0.05 ** (1 / 120))
    assert P.clopper_pearson_upper(0, 480) > 0.006
    assert P.errors({"a": math.inf, "b": -0.5})["wrong"] == 1


def _sim(rates, triggered=True, complete=True):
    runs = [{"settings": {"train": t, "size": 120, "search": s}, "stages": {"triggered": triggered},
             "resampled_retain": [{"n": n, "retain_rate_alpha": r(n), "retain_rate_target_2": r(n),
                                   "retain_rate_programme_7": r(n) / 2} for n in P.RESAMPLE_SIZES]}
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
    pilot = P.Pilot(workers=1)
    reg = P.region(pilot=pilot)
    (row,) = reg["rows"]
    assert row["informed_by_prior_observations"] and set(row["gate"]) == {"T1", "T2", "T3"}
    assert set(reg["baselines"]) == {"zscore", "hotelling", "knn5"} and set(reg["trigger"]) == {"T1", "T2", "T3"}
    sim = P.simulate(({"train": "T1", "size": 2, "search": "mutate-incumbent/1"},), pilot=pilot)
    (run,) = sim["runs"]
    assert set(run["stages"]) == {"triggered", "advances", "adversarial_passes"}
    assert all(c["alarm_fraction"] <= 0.75 for c in [s["config"] for s in run["top_train"]])
    assert [r["n"] for r in run["resampled_retain"]] == list(P.RESAMPLE_SIZES)


def test_design_md_states_the_declared_constants():
    text = (E.ROOT / "docs/evidence/greg-protected-evolution/2026-10-21-immune-8/DESIGN.md").read_text()
    for needle in ("immune-8/alarm-cap/1", "[0.4, 0.75]", "4000-4119", "4120-4239", "4240-4359", "4360-4999",
                   "20261022", "0.30", "120, 240, 360, 480", "stress_summary", "stress_worsened", "50,000", "15,000"):
        assert needle in text, needle
