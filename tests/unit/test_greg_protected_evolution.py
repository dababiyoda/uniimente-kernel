"""P8 protected evolutionary cognition: closed space, confined candidates, sealed evaluator, no activation."""
import json
import random

import pytest

from greg import isolation
from greg.cognition import evolution as E
from greg.cognition.genomes import forecasting


@pytest.fixture(scope="module")
def target():
    return E.forecasting_target()


@pytest.mark.parametrize("bad", [
    {"acceptance_threshold": 0.0}, {"evaluator_seal": "x"}, {"budget_usd": 5}, {"authority_ceiling": "financial"},
    {"shutdown": False}, {"target_scope": "*"}, {"heldout_split": "train"}])
def test_candidates_cannot_name_constitutional_or_evaluation_state(target, bad):
    with pytest.raises(E.EvolutionError, match="constitutional or evaluation state"):
        target.validate({**target.incumbent, **bad})


def test_candidates_stay_inside_the_declared_space(target):
    with pytest.raises(E.EvolutionError):
        target.validate({**target.incumbent, "fit_window": 999})
    with pytest.raises(E.EvolutionError):
        target.validate({k: v for k, v in target.incumbent.items() if k != "origins"})
    rng = random.Random(1)
    config = target.incumbent
    for _ in range(50):
        config, _ = E.mutate(target, config, rng)
        other, _ = E.mutate(target, target.incumbent, rng)
        config, _ = E.crossover(target, config, other, rng)
        assert target.validate(config) == config


def test_incumbent_is_the_shipped_configuration(target):
    assert target.incumbent == forecasting.DEFAULT_CONFIG


@pytest.mark.skipif(not isolation.available()["available"], reason="Landlock unavailable on this host")
def test_a_candidate_runs_confined_and_cannot_read_the_evaluators_outcomes(target):
    train, _, _ = E.forecasting_split()
    problems = [{"id": k, "data": v["data"]} for k, v in list(train.items())[:2]]
    run = E.run_candidate(target, target.incumbent, problems,
                          probe_read=str(E.ROOT / "cortex/evaluation/data/m4_weekly.json.gz"))
    assert run["confined"]["filesystem"] == "landlock"
    assert run["probe"].startswith("DENIED")
    assert set(run["outputs"]) == {p["id"] for p in problems}
    assert "actual" not in json.dumps([p["data"] for p in problems])   # outcomes never enter the request


def test_the_sealed_evaluator_refuses_after_tampering():
    train, _, _ = E.forecasting_split()
    items = dict(list(train.items())[:3])
    evaluator = E.SealedEvaluator(items, forecasting.score)
    evaluator.check()
    next(iter(items.values()))["truth"]["actual"][0] += 1.0             # an outcome edited after the seal
    with pytest.raises(E.EvolutionError, match="EVALUATOR_TAMPERED"):
        evaluator.check()


def test_splits_are_disjoint_from_admission_and_the_natural_composition_family():
    train, held, excluded = E.forecasting_split()
    assert not set(train) & set(held)
    assert not (set(train) | set(held)) & set(excluded)
    assert all(v["category"] not in forecasting.RESERVED for v in (*train.values(), *held.values()))


def test_a_cycle_without_a_recurring_failure_changes_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(E, "FAILURE_RATE_TRIGGER", 1.01)
    train, held, excluded = E.forecasting_split()
    monkeypatch.setattr(E, "forecasting_split", lambda seed=808: (dict(list(train.items())[:4]),
                                                                  dict(list(held.items())[:4]), excluded))
    record = E.cycle(generations=2, population=2, out=tmp_path / "c.json",
                     require_confinement=isolation.available()["available"])
    assert record["decision"] == "NO_RECURRING_FAILURE" and record["authority_created"] is False
    assert "proposal" not in record
    with pytest.raises(E.EvolutionError, match="overwrite"):
        E._finish(record, tmp_path / "c.json")
