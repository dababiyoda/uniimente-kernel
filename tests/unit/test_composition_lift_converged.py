"""P6 converged v1 (founder directive 2026-10-21): recipe lifts re-measured on the converged tree against the strongest
single intelligence available, on fresh held-out seeds, under a freeze that binds every recipe's complete code."""
from __future__ import annotations

import json

import pytest

from cortex.evaluation.composition_lift import run as V1
from cortex.evaluation.composition_lift import run_converged_v1 as R
from cortex.evaluation.composition_lift import run_v2 as V2
from greg.cognition import compiler as C

pytestmark = pytest.mark.filterwarnings("ignore::RuntimeWarning")


def test_the_runner_reuses_the_lineage_families_and_arms_unchanged():
    assert R.CONSTITUENTS["F1"] == V1.CONSTITUENTS["F1"]
    assert all(R.CONSTITUENTS[f] == V2.CONSTITUENTS[f] for f in ("F2R", "F3", "F4"))
    assert R.generate("F1", 1)["payload"] == V1.f1(1)["payload"]
    assert R.generate("F3", 1) == V2.f3(1)


def test_every_family_compares_against_the_strongest_available_single_and_the_compiler():
    for family in R.SEEDS:
        arms = R.arms_for(family)
        assert set(R.CONSTITUENTS[family]) <= set(arms) and {"routed_composition", "compiled"} <= set(arms)
    assert "exact_single" in R.arms_for("F3")


def test_preregistration_matches_the_runner():
    prereg = json.loads(R.PREREG.read_text())
    assert prereg["seeds"] == {f: [s.start, s.stop - 1] for f, s in R.SEEDS.items()}
    assert prereg["recipes"] == R.RECIPE and prereg["rule"] == R.RULE
    assert prereg["eval_attach"] == list(R.EVAL_ATTACH)


def test_held_out_seeds_are_unspent_and_outside_every_reservation():
    from greg.cognition.genomes.admission import P8_RESERVED, spent_seeds
    spent, reserved = spent_seeds(), set(P8_RESERVED) | set(range(3000, 4000))
    for family, seeds in R.SEEDS.items():
        assert not set(seeds) & spent, family
        assert not set(seeds) & reserved, family
    dev = set(range(0, 200))                       # every lineage's development seeds
    assert not dev & set().union(*map(set, R.SEEDS.values()))


def test_the_freeze_binds_every_recipes_complete_code():
    bound = R.bindings()
    assert set(bound) == set(R.RECIPE.values())
    for recipe, code in bound.items():
        assert code and code["closure_sha256"].startswith("sha256:") and code["stage_closures"], recipe
        assert not code["closure_unresolved"], recipe
    assert R.inputs()["recipe_bindings"] == bound


def test_a_changed_recipe_binding_changes_the_frozen_inputs(monkeypatch):
    before = R.inputs()
    real = R.bindings()
    recipe = R.RECIPE["F1"]
    monkeypatch.setattr(R, "bindings", lambda: {**real, recipe: {**real[recipe], "closure_sha256": "sha256:" + "0" * 64}})
    assert R.inputs() != before


def test_the_run_refuses_a_dirty_tree_and_unfrozen_or_changed_inputs(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "dirty", lambda: [" M greg/cognition/compiler.py"])
    monkeypatch.setattr("sys.argv", ["run_converged_v1", "--out", str(tmp_path / "r.json")])
    with pytest.raises(SystemExit, match="DIRTY_TREE"):
        R.main()
    monkeypatch.setattr(R, "dirty", lambda: [])
    monkeypatch.setattr(R, "MANIFEST", tmp_path / "missing.json")
    with pytest.raises(SystemExit, match="NOT_FROZEN"):
        R.main()
    stale = tmp_path / "freeze.json"
    stale.write_text(json.dumps({"inputs": {**R.inputs(), "seeds": {"F1": [1, 40]}}}))
    monkeypatch.setattr(R, "MANIFEST", stale)
    with pytest.raises(SystemExit, match="FROZEN_INPUT_CHANGED"):
        R.main()
    assert not (tmp_path / "r.json").exists()


def test_the_freeze_refuses_to_overwrite(monkeypatch, tmp_path):
    existing = tmp_path / "freeze.json"
    existing.write_text("{}")
    monkeypatch.setattr(R, "dirty", lambda: [])
    monkeypatch.setattr(R, "MANIFEST", existing)
    monkeypatch.setattr("sys.argv", ["run_converged_v1", "--freeze"])
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        R.main()
    assert existing.read_text() == "{}"


def _row(fr_results: dict) -> dict:
    return {"arms": {a: {"result": r, "seconds": 0.1, "state": "ANSWERED"} for a, r in fr_results.items()}}


def test_the_verdict_takes_the_best_single_over_constituents_and_exact_singles():
    """F7's lesson: a composition that ties the exact single genome has no converged lift, whatever it does against
    the lineage constituents."""
    rows = [_row({"graph_alone_greedy": "suboptimal", "optimize_flow_blind": "suboptimal", "exact_single": "correct",
                  "routed_composition": "correct"}) for _ in range(12)]
    converged = R._verdict(rows, ("graph_alone_greedy", "optimize_flow_blind", "exact_single"))
    lineage = R._verdict(rows, ("graph_alone_greedy", "optimize_flow_blind"))
    assert converged["best_single"] == "exact_single" and converged["lift"] is False
    assert lineage["lift"] is True and lineage["routed_wins"] == 12


def test_a_wrong_answer_over_the_best_single_blocks_the_lift():
    rows = [_row({"a": "suboptimal", "routed_composition": "correct"}) for _ in range(12)]
    rows.append(_row({"a": "suboptimal", "routed_composition": "wrong"}))
    assert R._verdict(rows, ("a",))["lift"] is False


def test_the_compiler_rejects_an_organ_that_answers_a_relaxation_of_a_routed_recipe():
    """Development check, 2026-10-21: with every recipe UNEVALUATED on the converged tree, the Fermi organ tied
    estimate_then_optimize on status, won on the method name, ignored formal_template and abstained."""
    data = V1.f1(1)["payload"]
    rows = {r["method"]: r for r in C.candidates(data, C.CompetencyGeometry(), C.evidence_index())}
    assert "answers a relaxation" in rows["cognition.cortex.estimation.fermi"]["rejected"]
    assert "formal_template" in rows["cognition.cortex.estimation.fermi"]["rejected"]
    assert rows["composition:estimate_then_optimize"]["rejected"] is None


def test_an_admitted_twin_genome_still_competes_with_its_recipe():
    data = V2.f3(1)["payload"]
    rows = {r["method"]: r for r in C.candidates(data, C.CompetencyGeometry(), C.evidence_index())}
    assert not rows["cognition.flow_expansion_mcf"]["rejected"]
