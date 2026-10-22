"""Pure parts of the §14 v3 condition-specific competence mechanism (greg/cognition/condition_competence.py)."""
import pytest

from greg.cognition import condition_competence as cc


def _req(d, lo=-5.12, hi=5.12):
    return {"function": "griewank", "shift": [0.5] * d, "bounds": [[lo, hi]] * d, "budget": 1000 * d, "seed": 7}


def test_the_condition_key_reads_only_the_declared_dimension_band():
    assert cc.condition_key("optimization", _req(10)) == "optimization|d<=10"
    assert cc.condition_key("optimization", _req(11)) == "optimization|d11-30"
    assert cc.condition_key("optimization", _req(30)) == "optimization|d11-30"
    assert cc.condition_key("optimization", _req(31)) is None          # outside every declared band: no cell
    assert cc.condition_key("optimization", {"function": "sphere"}) is None


def test_the_adapter_is_exact_and_refuses_what_it_cannot_express():
    native = cc.adapter(_req(20))
    assert native == {"objective": "griewank", "dimension": 20, "lower": -5.12, "upper": 5.12,
                      "shift": [0.5] * 20, "evaluations": 20000, "seed": 7}
    mixed = _req(3)
    mixed["bounds"][1] = [-1.0, 1.0]
    with pytest.raises(ValueError):
        cc.adapter(mixed)                                               # a non-uniform box is not approximated
    short = _req(3)
    short["bounds"] = short["bounds"][:2]
    with pytest.raises(ValueError):
        cc.adapter(short)


def test_the_sign_test_is_exact():
    assert cc.sign_test(5, 0) == pytest.approx(1 / 32)
    assert cc.sign_test(0, 0) == 1.0
    assert cc.sign_test(6, 1) == pytest.approx(8 / 128)


def _pair(claim, inc, alt, cell="optimization|d11-30"):
    return {"cell": cell, "claim": claim, "incumbent_pass": inc, "alternative_pass": alt}


def test_the_preference_fires_only_on_enough_significant_discordant_pairs():
    four = cc.cell_evidence([_pair(f"c{i}", False, True) for i in range(4)])
    assert not cc.preference("optimization|d11-30", four)["fired"]       # 4 discordant < MIN_DISCORDANT
    five = cc.cell_evidence([_pair(f"c{i}", False, True) for i in range(5)])
    rec = cc.preference("optimization|d11-30", five)
    assert rec["fired"] and rec["prefer"] == cc.ALTERNATIVE and "not a re-admission" in rec["basis"]
    mixed = cc.cell_evidence([_pair(f"c{i}", False, True) for i in range(6)] + [_pair("x", True, False)])
    assert not cc.preference("optimization|d11-30", mixed)["fired"]      # 6-1: p = 0.0625
    assert cc.preference("optimization|d<=10", five) is None               # another cell is untouched


def test_a_re_observed_claim_counts_once():
    ev = cc.cell_evidence([_pair("same", False, True)] * 9)
    assert ev["optimization|d11-30"]["pairs"] == 1


def test_the_shuffle_ablation_is_seeded_and_ignores_the_dimension():
    pairs = [_pair(f"c{i}", False, True) for i in range(36)]
    a, b = cc.cell_evidence(pairs, shuffle=True), cc.cell_evidence(pairs, shuffle=True)
    assert a == b and set(a) == {"optimization|d<=10", "optimization|d11-30"}


def test_a_shadow_is_due_only_after_a_settled_failure_and_within_the_ceiling():
    assert not cc.shadow_due("optimization|d11-30", 0, 0)
    assert cc.shadow_due("optimization|d11-30", 1, 0)
    assert not cc.shadow_due("optimization|d11-30", 1, cc.SHADOW_CEILING_PER_CELL)
    assert not cc.shadow_due(None, 3, 0)
