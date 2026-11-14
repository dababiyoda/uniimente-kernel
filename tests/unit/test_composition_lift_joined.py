"""P6 joined v1: the converged v1 procedure re-run on the joined tree under a new identity and fresh seeds."""
from __future__ import annotations

import json

import pytest

from cortex.evaluation.composition_lift import run_converged_v1 as V
from cortex.evaluation.composition_lift import run_joined_v1 as J

pytestmark = pytest.mark.filterwarnings("ignore::RuntimeWarning")


def test_the_runner_reuses_v1_unchanged_and_leaves_v1_identity_alone():
    assert J.C.__file__ == V.__file__                      # the same source file, executed unchanged
    assert V.MANIFEST.name == "freeze-converged-v1.json" and V.SEEDS["F1"] == range(6501, 6541)
    assert J.C.MANIFEST == J.MANIFEST and J.MANIFEST.name == "freeze-joined-v1.json"
    assert J.C.SEEDS is J.SEEDS
    assert J.RECIPE == V.RECIPE and J.RULE == V.RULE and J.EVAL_ATTACH == V.EVAL_ATTACH
    assert {f: J.arms_for(f) for f in J.SEEDS} == {f: V.arms_for(f) for f in V.SEEDS}
    assert J.generate("F3", 1) == V.generate("F3", 1)


def test_preregistration_matches_the_runner():
    prereg = json.loads(J.PREREG.read_text())
    assert prereg["seeds"] == {f: [s.start, s.stop - 1] for f, s in J.SEEDS.items()}
    assert prereg["recipes"] == J.RECIPE and prereg["rule"] == J.RULE
    assert prereg["eval_attach"] == list(J.EVAL_ATTACH)
    assert {f: len(s) for f, s in J.SEEDS.items()} == {"F1": 40, "F2R": 64, "F3": 40, "F4": 40}


def test_held_out_seeds_are_fresh_and_inside_the_assigned_range():
    from greg.cognition.genomes.admission import P8_RESERVED, spent_seeds
    seeds = set().union(*map(set, J.SEEDS.values()))
    assert sum(map(len, J.SEEDS.values())) == len(seeds)            # families are disjoint
    assert seeds <= set(range(4000, 5000))
    assert not seeds & (spent_seeds() | set(P8_RESERVED) | set(range(3000, 4000)) | set(range(0, 200)))
    assert not seeds & set().union(*map(set, V.SEEDS.values()))


def test_the_frozen_inputs_cover_both_runners_and_every_recipe_binding():
    files = J.inputs()["files"]
    assert {"cortex/evaluation/composition_lift/run_joined_v1.py",
            "cortex/evaluation/composition_lift/prereg-joined-v1.json",
            "cortex/evaluation/composition_lift/run_converged_v1.py"} <= set(files)
    assert set(J.inputs()["recipe_bindings"]) == set(J.RECIPE.values())


def test_the_run_refuses_dirty_unfrozen_changed_or_non_isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(J, "dirty", lambda: [" M greg/cognition/cortex.py"])
    monkeypatch.setattr("sys.argv", ["run_joined_v1", "--out", str(tmp_path / "r.json")])
    with pytest.raises(SystemExit, match="DIRTY_TREE"):
        J.main()
    monkeypatch.setattr(J, "dirty", lambda: [])
    monkeypatch.setattr(J, "MANIFEST", tmp_path / "missing.json")
    with pytest.raises(SystemExit, match="NOT_FROZEN"):
        J.main()
    stale = tmp_path / "freeze.json"
    stale.write_text(json.dumps({"inputs": {**J.inputs(), "seeds": {"F1": [1, 40]}}}))
    monkeypatch.setattr(J, "MANIFEST", stale)
    with pytest.raises(SystemExit, match="FROZEN_INPUT_CHANGED"):
        J.main()
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"inputs": J.inputs()}))
    monkeypatch.setattr(J, "MANIFEST", good)
    with pytest.raises(SystemExit, match="NOT_ISOLATED"):       # pytest is not python -I
        J.main()
    assert not (tmp_path / "r.json").exists()
