"""The two call sites of condition-specific competence on the real compile path (§14 antifragility v3).

Requests use #189's disclosed pilot seeds only (its generator, 3 dimensions for speed where the cell does not
matter); no stress or holdout seed of either experiment is generated here.
"""
import random

import pytest

from greg.cognition import condition_competence as cc
from greg.cognition.cortex import reason, registry_view


def _request(d, seed=0):
    rnd = random.Random(seed)
    return {"function": "sphere", "shift": [round(rnd.uniform(-2, 2), 3) for _ in range(d)],
            "bounds": [[-5.12, 5.12]] * d, "budget": 300 * d, "seed": seed}


def _registry(alternative=True):
    registry = registry_view(None)
    for cid in ("cognition.swarm", "cognition.blackbox") + ((cc.ALTERNATIVE,) if alternative else ()):
        registry.set_state(cid, "ATTACHED")
    return registry


def _compile(req, registry, journal=None):
    return reason({"problem_id": "cc-hook", "compile": {"geometry": {"geometry": "optimization"}, "data": req}},
                  registry=registry, journal=journal)


FIRED = {"optimization|d11-30": {"pairs": 6, "alternative_only": 6, "incumbent_only": 0}}


@pytest.fixture
def journal(tmp_path):
    """A real, empty body journal; the evidence readers are patched per test."""
    from greg.body import Body
    from tests.greg_fixtures import make_body
    home, _, _, _ = make_body(tmp_path)
    with Body(home) as body:
        yield body.journal


def test_every_compile_records_its_cell_and_nothing_else_without_evidence():
    r = _compile(_request(12), _registry())
    assert r["condition"] == {"policy": cc.POLICY, "cell": "optimization|d11-30", "mode": "on"}
    assert r["method_or_composition_selected"] == cc.INCUMBENT and "condition_shadow" not in r


def test_a_fired_cell_routes_the_attached_admitted_alternative_through_the_adapter(monkeypatch):
    monkeypatch.setattr(cc, "evidence_from", lambda journal: FIRED)
    r = _compile(_request(12), _registry())
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == cc.ALTERNATIVE
    assert r["selection_level"] == "preferred_by_condition_evidence"
    assert set(r["result"]) == {"candidate", "fitness", "evaluations"} and r["result"]["evaluations"] <= 3600
    assert any("not a re-admission" in d for d in r["dissent"])
    assert r["selected_receipt"]["method"] == cc.ALTERNATIVE and r["authority_created"] is False


def test_the_preference_never_crosses_cells(monkeypatch):
    monkeypatch.setattr(cc, "evidence_from", lambda journal: FIRED)
    assert _compile(_request(5), _registry())["method_or_composition_selected"] == cc.INCUMBENT


def test_an_unattached_alternative_is_never_routed_however_strong_the_evidence(monkeypatch):
    monkeypatch.setattr(cc, "evidence_from", lambda journal: FIRED)
    r = _compile(_request(12), _registry(alternative=False))
    assert r["method_or_composition_selected"] == cc.INCUMBENT and "condition_shadow" not in r


def test_an_unadmitted_alternative_is_never_routed(monkeypatch):
    monkeypatch.setattr(cc, "evidence_from", lambda journal: FIRED)
    monkeypatch.setattr(cc, "_admitted", lambda: False)
    assert _compile(_request(12), _registry())["method_or_composition_selected"] == cc.INCUMBENT


def test_the_control_arm_reads_no_evidence(monkeypatch):
    monkeypatch.setattr(cc, "MODE", "off")
    monkeypatch.setattr(cc, "evidence_from", lambda journal: pytest.fail("CONTROL read the evidence"))
    assert _compile(_request(12), _registry())["method_or_composition_selected"] == cc.INCUMBENT


def test_a_due_shadow_is_inert_recorded_and_never_returned(monkeypatch, journal):
    monkeypatch.setattr(cc, "evidence_from", lambda journal: {})
    monkeypatch.setattr(cc, "pairs_from", lambda journal: [])
    monkeypatch.setattr(cc, "incumbent_unmet", lambda journal, cell, exclude_problem=None: 1)
    r = _compile(_request(12), _registry(), journal=journal)
    shadow = r["condition_shadow"]
    assert shadow["inert"] and shadow["verified"] and shadow["cell"] == "optimization|d11-30"
    assert r["method_or_composition_selected"] == cc.INCUMBENT
    assert r["selected_receipt"]["method"] == cc.INCUMBENT          # the answer is the incumbent's own


def test_the_shadow_ceiling_stops_shadows(monkeypatch, journal):
    monkeypatch.setattr(cc, "evidence_from", lambda journal: {})
    monkeypatch.setattr(cc, "pairs_from", lambda journal: [{"cell": "optimization|d11-30"}] * cc.SHADOW_CEILING_PER_CELL)
    monkeypatch.setattr(cc, "incumbent_unmet", lambda journal, cell, exclude_problem=None: 5)
    assert "condition_shadow" not in _compile(_request(12), _registry(), journal=journal)


def test_settlement_pairs_a_shadow_under_the_signed_check():
    check = {"predicate": {"op": "lte", "field": "result.fitness", "value": 0.5}}
    compiled = {"condition": {"cell": "optimization|d11-30"},
                "condition_shadow": {"verified": True, "fitness": 0.1, "evaluations": 900, "seconds": 0.2}}
    out = cc.settlement_fields(compiled, check, False)
    assert out["condition_cell"] == "optimization|d11-30"
    assert out["condition_pair"]["alternative_pass"] and not out["condition_pair"]["incumbent_pass"]
    assert cc.settlement_fields({"condition": {"cell": "c"}}, check, True) == {"condition_cell": "c"}
    assert cc.settlement_fields(None, check, True) == {}


def test_a_request_is_never_shadowed_because_of_its_own_failure(monkeypatch, journal):
    """The failure that triggers shadowing must not enter the paired evidence as a known discordant pair."""
    from greg.cognition import settlement
    own = {"condition_cell": "optimization|d11-30", "method": cc.INCUMBENT, "correct": False, "problem_id": "cc-hook"}
    monkeypatch.setattr(settlement, "measured_outcomes", lambda j: [own])
    assert cc.incumbent_unmet(journal, "optimization|d11-30", exclude_problem="cc-hook") == 0
    assert cc.incumbent_unmet(journal, "optimization|d11-30", exclude_problem="other") == 1
    monkeypatch.undo()
    # the compiler passes the request's own problem id: its own failure alone never makes a shadow due
    monkeypatch.setattr(cc, "evidence_from", lambda j: {})
    monkeypatch.setattr(cc, "pairs_from", lambda j: [])
    monkeypatch.setattr(cc, "incumbent_unmet",
                        lambda j, cell, exclude_problem=None: 0 if exclude_problem == "cc-hook" else 1)
    assert "condition_shadow" not in _compile(_request(12), _registry(), journal=journal)
