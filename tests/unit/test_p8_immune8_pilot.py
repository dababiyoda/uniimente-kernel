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
