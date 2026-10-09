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


# ------------------------------------------------------------------ cycle 2 target: negative selection
def test_the_immune_target_is_the_shipped_configuration_inside_a_closed_space():
    from greg.cognition.genomes import collective
    target = E.immune_target()
    assert target.incumbent == collective.IMMUNE_DEFAULT_CONFIG
    with pytest.raises(E.EvolutionError, match="constitutional or evaluation state"):
        target.validate({**target.incumbent, "alarm_threshold": 0.9})
    with pytest.raises(E.EvolutionError):
        target.validate({**target.incumbent, "detectors": 7})
    with pytest.raises(collective.GenomeError):
        collective.immune_solve_with({**target.incumbent, "whitening": "learned"}, collective.immune_instance(0)[0])


def test_immune_split_is_fresh_and_disjoint_from_admission():
    from greg.cognition.genomes import admission
    train, held, excluded = E.immune_split()
    assert len(train) == 40 and len(held) == 60 and not set(train) & set(held)
    used = {int(k[1:]) for k in (*train, *held)}
    assert not used & (set(admission.DEV_SEEDS) | set(admission.HELDOUT_SEEDS))
    assert all("labels" not in json.dumps(v["data"]) for v in (*train.values(), *held.values()))


def test_full_whitening_is_independently_verified_and_a_forged_factor_is_refuted():
    from greg.cognition.genomes import collective
    data, _ = collective.immune_instance(3)
    out = collective.immune_solve_with({**collective.IMMUNE_DEFAULT_CONFIG, "whitening": "full"}, data)
    assert all(collective.immune_verify(data, out["output"], out["certificate"]).values())
    forged = json.loads(json.dumps(out["certificate"]))
    forged["standardisation"]["cholesky"][0][0] *= 1.5
    assert not all(collective.immune_verify(data, out["output"], forged).values())


@pytest.mark.skipif(not isolation.available()["available"], reason="Landlock unavailable on this host")
def test_an_immune_candidate_runs_confined_from_the_allow_list():
    target = E.immune_target()
    train, _, _ = E.immune_split()
    problems = [{"id": k, "data": v["data"]} for k, v in list(train.items())[:2]]
    run = E.run_candidate(target, {**target.incumbent, "whitening": "full"}, problems,
                          probe_read=str(E.ROOT / "greg/cognition/evolution.py"))
    assert run["confined"]["filesystem"] == "landlock" and run["probe"].startswith("DENIED")
    assert all("output" in v for v in run["outputs"].values())


@pytest.mark.parametrize("incumbent,candidate,gain,worse", [
    (2.0, 1.8, 0.1, False),        # positive losses (pinball): identical to 1 - c/i
    (2.0, 2.2, -0.1, True),
    (-0.5, -0.6, 0.2, False),      # negative losses (-F1): a better candidate has a POSITIVE gain
    (-0.5, -0.4, -0.2, True),      # ... and a 20% worse candidate is worsened
    (-0.5, -0.49, -0.02, False),   # within the 5% stress tolerance
])
def test_gain_and_stress_tolerance_are_correct_for_losses_of_either_sign(incumbent, candidate, gain, worse):
    assert E.relative_gain(incumbent, candidate) == pytest.approx(gain)
    assert E.worsened(incumbent, candidate) is worse


def test_an_infinite_mean_loss_never_yields_a_nan_gain():
    inf = float("inf")
    assert E.relative_gain(inf, -0.5) == inf          # the candidate removed a wrong answer
    assert E.relative_gain(inf, inf) == 0.0            # both wrong somewhere: no evidence of gain
    assert E.relative_gain(-0.5, inf) == -inf          # the candidate added a wrong answer
    assert not E.relative_gain(inf, inf) > E.TRAIN_GAIN_MIN


def test_abstentions_are_not_counted_as_failed_verification():
    from greg.cognition.genomes import collective
    data, _ = collective.immune_instance(2)
    good = collective.immune_solve(data, {})
    items = {"a": {"data": data}, "b": {"data": data}}
    abstained = {"output": None, "certificate": {"self_samples": 3}}
    assert E.outputs_verified(collective.immune_verify, items, {"a": good, "b": abstained})
    forged = {"output": {"flagged": [0], "self_radius": 0.0}, "certificate": {}}
    assert not E.outputs_verified(collective.immune_verify, items, {"a": good, "b": forged})


def test_lazily_imported_runtime_is_loaded_before_confinement():
    """CI regression (ed4ee29): numpy imported after Landlock could not open libstdc++ on a runner whose
    Python lives outside /usr. Every allow-listed target that uses numpy declares it for preloading."""
    import importlib
    import inspect
    from greg.cognition import evolution_sandbox as S
    for name, (module, function, runtime) in S.TARGETS.items():
        source = inspect.getsource(getattr(importlib.import_module(module), function))
        if "import numpy" in source:
            assert "numpy" in runtime, f"{name} imports numpy lazily but does not preload it"
    assert {"numpy", "numpy.linalg"} <= set(S.TARGETS["immune_detect"][2])
    main = inspect.getsource(S.main)
    assert main.index("for name in runtime") < main.index("isolation.confine(")
