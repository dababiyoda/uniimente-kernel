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


def _small_forecasting_split(monkeypatch):
    train, held, excluded = E.forecasting_split()
    monkeypatch.setattr(E, "forecasting_split", lambda seed=808: (dict(list(train.items())[:4]),
                                                                  dict(list(held.items())[:4]), excluded))


def test_a_cycle_without_a_recurring_failure_changes_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(E, "FAILURE_RATE_TRIGGER", 1.01)
    monkeypatch.setattr(E, "_dirty", lambda paths: [])         # the dirty-tree rule has its own test
    _small_forecasting_split(monkeypatch)
    frozen = tmp_path / "freeze.json"
    E.freeze("forecast_quantile", frozen, generations=2, population=2)
    record = E.cycle(generations=2, population=2, out=tmp_path / "c.json", freeze=frozen,
                     require_confinement=isolation.available()["available"])
    assert record["decision"] == "NO_RECURRING_FAILURE" and record["authority_created"] is False
    assert record["freeze"]["sha256"].startswith("sha256:") and record["source_dirty"] == []
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
        collective.immune_solve_with({**target.incumbent, "whitening": "learned"},
                                    collective.immune_gaussian_instance(0)[0])


def test_immune_split_is_fresh_and_disjoint_from_admission():
    from greg.cognition.genomes import admission
    train, held, excluded = E.immune_split()
    assert len(train) == 40 and len(held) == 60 and not set(train) & set(held)
    used = {int(k[1:]) for k in (*train, *held)}
    assert not used & (set(admission.DEV_SEEDS) | set(admission.HELDOUT_SEEDS))
    assert all("labels" not in json.dumps(v["data"]) for v in (*train.values(), *held.values()))


def test_full_whitening_is_independently_verified_and_a_forged_factor_is_refuted():
    from greg.cognition.genomes import collective
    data, _ = collective.immune_gaussian_instance(3)        # P8's immune items come from this generator
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
    data, _ = collective.immune_gaussian_instance(2)
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


def test_the_constraint_release_target_is_a_closed_data_space_over_fresh_reserved_seeds():
    """Cycle 3 (2026-10-14): the search policy of develop_constraint_release, where random restart beat the
    incumbent 15-5 on admission v2's fresh seeds. A candidate is data; the default reproduces the admitted search."""
    from greg.cognition.genomes import admission, developmental as D
    target = E.cr_target()
    assert target.validate(dict(D.CR_DEFAULT_CONFIG)) == D.CR_DEFAULT_CONFIG
    for bad in ({**D.CR_DEFAULT_CONFIG, "mu": 5}, {**D.CR_DEFAULT_CONFIG, "p_restart": 1.5},
                {**D.CR_DEFAULT_CONFIG, "retain_threshold": 0.0}):
        with pytest.raises(E.EvolutionError):
            target.validate(bad)
    used = set(admission.DEV_SEEDS) | set(admission.HELDOUT_SEEDS) | admission.spent_seeds() | \
        set(E.IMMUNE_TRAIN_SEEDS) | set(E.IMMUNE_HELDOUT_SEEDS)
    assert not used & (set(E.CR_TRAIN_SEEDS) | set(E.CR_HELDOUT_SEEDS))
    assert set(E.CR_TRAIN_SEEDS) | set(E.CR_HELDOUT_SEEDS) <= set(admission.P8_RESERVED)
    every = [s for train, held in E.CR_SPLITS.values() for s in (*train, *held)]
    assert len(every) == len(set(every)) and not used & set(every) and set(every) <= set(admission.P8_RESERVED)
    rng = random.Random(3)
    child, _ = E.mutate(target, dict(D.CR_DEFAULT_CONFIG), rng)
    data, _ = D.constraint_release_instance(3)                              # development seed
    out = D.constraint_release_solve_with(child, data)
    if out["status"] == "ANSWER":
        assert all(D.constraint_release_verify(data, out["output"], out["certificate"]).values())


def test_a_constraint_release_candidate_runs_confined_and_verifies(tmp_path):
    from greg.cognition.genomes import developmental as D
    target = E.cr_target()
    config = {**D.CR_DEFAULT_CONFIG, "p_restart": 0.4}
    data, _ = D.constraint_release_instance(4)                              # development seed
    run = E.run_candidate(target, config, [{"id": "a", "data": data}],
                          require_confinement=isolation.available()["available"])
    produced = run["outputs"]["a"]
    assert "error" not in produced
    assert all(D.constraint_release_verify(data, produced["output"], produced["certificate"]).values())


# ------------------------------------------------------------------ review of #179 (2026-10-15): P8 integrity
def _frozen(monkeypatch, tmp_path, edit=None):
    """A pre-registered small forecasting cycle; ``edit`` changes the freeze as an on-disk edit after it would."""
    monkeypatch.setattr(E, "_dirty", lambda paths: [])
    _small_forecasting_split(monkeypatch)
    path = tmp_path / "freeze.json"
    E.freeze("forecast_quantile", path, generations=2, population=2)
    if edit is not None:
        manifest = json.loads(path.read_text())
        edit(manifest["inputs"])
        path.write_text(json.dumps(manifest))
    return path


def test_a_cycle_that_writes_a_record_needs_its_pre_registered_freeze(tmp_path):
    with pytest.raises(E.EvolutionError, match="FREEZE_REQUIRED"):
        E.cycle(generations=2, population=2, out=tmp_path / "c.json")


@pytest.mark.parametrize("path", ["greg/cognition/evolution.py",              # the evaluator edited before the run
                                  "greg/cognition/genomes/forecasting.py",    # the candidate method edited
                                  "greg/cognition/evolution_sandbox.py"])
def test_a_trusted_file_that_differs_from_the_freeze_is_refused(monkeypatch, tmp_path, path):
    def edit(inputs):
        inputs["code"][path] = "sha256:" + "0" * 64
    frozen = _frozen(monkeypatch, tmp_path, edit)
    with pytest.raises(E.EvolutionError, match="FROZEN_INPUT_CHANGED"):
        E.cycle(generations=2, population=2, out=tmp_path / "c.json", freeze=frozen, require_confinement=False)
    assert not (tmp_path / "c.json").exists()


@pytest.mark.parametrize("edit,why", [
    (lambda i: i["seals"].update(heldout="sha256:" + "1" * 64), "EVALUATOR_TAMPERED"),
    (lambda i: i["split"].update(train=i["split"]["train"][:-1]), "EVALUATOR_TAMPERED"),
    (lambda i: i["settings"].update(population=3), "FROZEN_INPUT_CHANGED"),
    (lambda i: i["constants"].update(alpha=0.5), "FROZEN_INPUT_CHANGED"),
    (lambda i: i.update(rule="RETAIN always"), "FROZEN_INPUT_CHANGED")])
def test_seals_split_settings_and_rule_must_equal_the_freeze(monkeypatch, tmp_path, edit, why):
    frozen = _frozen(monkeypatch, tmp_path, edit)
    with pytest.raises(E.EvolutionError, match=why):
        E.cycle(generations=2, population=2, out=tmp_path / "c.json", freeze=frozen, require_confinement=False)


def test_a_trusted_file_changed_mid_run_stops_the_cycle_before_the_next_evaluation(monkeypatch, tmp_path):
    frozen = _frozen(monkeypatch, tmp_path)
    real, calls = E._code, []

    def drifting(name):
        calls.append(name)
        code = real(name)
        if len(calls) > 2:                     # after the start checks, the method module changes on disk
            code["greg/cognition/genomes/forecasting.py"] = "sha256:" + "2" * 64
        return code
    monkeypatch.setattr(E, "_code", drifting)
    with pytest.raises(E.EvolutionError, match="FROZEN_INPUT_CHANGED"):
        E.cycle(generations=2, population=2, out=tmp_path / "c.json", freeze=frozen,
                require_confinement=isolation.available()["available"])
    assert not (tmp_path / "c.json").exists()


def test_a_dirty_trusted_file_is_refused_for_a_freeze_and_for_a_record(monkeypatch, tmp_path):
    monkeypatch.setattr(E, "_dirty", lambda paths: ["greg/cognition/evolution.py"])
    with pytest.raises(E.EvolutionError, match="DIRTY_TREE"):
        E.freeze("forecast_quantile", tmp_path / "f.json")
    (tmp_path / "f.json").write_text(json.dumps({"inputs": {}}))
    with pytest.raises(E.EvolutionError, match="DIRTY_TREE"):
        E.cycle(out=tmp_path / "c.json", freeze=tmp_path / "f.json")
    with pytest.raises(E.EvolutionError, match="evidence tree"):
        E.cycle(out=E.ROOT / "docs/evidence/greg-protected-evolution/x/c.json", freeze=tmp_path / "f.json",
                allow_dirty_for_test=True)


def test_the_parent_refuses_a_sandbox_that_imported_a_different_method(target):
    train, _, _ = E.forecasting_split()
    problems = [{"id": k, "data": v["data"]} for k, v in list(train.items())[:1]]
    with pytest.raises(E.EvolutionError, match="METHOD_CHANGED"):
        E.run_candidate(target, target.incumbent, problems, require_confinement=isolation.available()["available"],
                        expected_module="sha256:" + "3" * 64)
    run = E.run_candidate(target, target.incumbent, problems, require_confinement=isolation.available()["available"])
    assert run["imported"]["sha256"] == E._sha(E.ROOT / "greg/cognition/genomes/forecasting.py")


@pytest.mark.skipif(not isolation.available()["available"], reason="Landlock unavailable on this host")
def test_the_parent_itself_checks_the_sandbox_cannot_read_the_evaluator(target, monkeypatch):
    train, _, _ = E.forecasting_split()
    problems = [{"id": k, "data": v["data"]} for k, v in list(train.items())[:1]]
    run = E.run_candidate(target, target.incumbent, problems)
    assert run["probe"].startswith("DENIED")                 # probed by default, not only when a test asks
    real = E.json.loads

    def readable(text):
        out = real(text)
        if isinstance(out, dict) and "probe" in out:
            out["probe"] = "READ"                            # a child reporting confinement it did not have
        return out
    monkeypatch.setattr(E.json, "loads", readable)
    with pytest.raises(E.EvolutionError, match="CONFINEMENT_UNVERIFIED"):
        E.run_candidate(target, target.incumbent, problems)


@pytest.mark.parametrize("name,key,value", [
    ("constraint_release", "mu", 2.0), ("constraint_release", "tournament", True),
    ("forecast_quantile", "fit_window", 156.0), ("forecast_quantile", "beta_set", [0, 0.02, 0.05]),
    ("immune_detect", "detectors", 1000.0), ("immune_detect", "calibration_folds", 3.0)])
def test_choices_are_type_strict_so_bool_and_float_never_pass_for_int(name, key, value):
    """Each value equals a declared choice in Python (True == 1, 2.0 == 2) but is not that choice."""
    target = E.TARGET_SPECS[name]().target()
    kind, values = target.space[key]
    assert kind == "choice" and any(value == v for v in values)
    with pytest.raises(E.EvolutionError, match="outside the declared space"):
        target.validate({**target.incumbent, key: value})


def test_a_method_error_is_recorded_per_problem_and_never_aborts_the_sandbox():
    import subprocess
    import sys
    train, _, _ = E.forecasting_split()
    problems = [{"id": k, "data": v["data"]} for k, v in list(train.items())[:2]]
    request = {"target": "forecast_quantile", "problems": problems, "confine": False,
               "config": {**forecasting.DEFAULT_CONFIG, "fit_window": "not a number"}}   # a TypeError inside
    proc = subprocess.run([sys.executable, "-I", str(E.SANDBOX)], input=json.dumps(request).encode(),
                          capture_output=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-300:]
    outputs = json.loads(proc.stdout)["outputs"]
    assert set(outputs) == {p["id"] for p in problems} and all("error" in v for v in outputs.values())


def _shipped(target_name):
    import importlib
    spec = E.TARGET_SPECS[target_name]()
    module = importlib.import_module(spec.proposal["module"][:-3].replace("/", "."))
    return getattr(module, spec.proposal["constant"])


def test_no_rejected_p8_configuration_is_shipped_and_every_incumbent_still_is():
    records = [json.loads(p.read_text()) for p in sorted((E.ROOT / "docs/evidence/greg-protected-evolution")
                                                        .glob("*/cycle-*.json"))]
    records = [r for r in records if r.get("schema") == "greg-protected-evolution/1"]
    assert {r["target"] for r in records} == set(E.TARGET_SPECS)
    for r in records:
        shipped = _shipped(r["target"])
        if r["decision"] != "RETAIN":
            assert shipped == r["incumbent"]["config"], r["target"]
        rejected = [step["config"] for step in r.get("search", {}).get("lineage", [])
                    if step["id"] != r["incumbent"]["id"]]
        if r.get("candidate") and r["decision"] != "RETAIN":
            rejected.append(r["candidate"]["config"])
        assert all(shipped != c for c in rejected), r["target"]


def test_each_shipped_evolvable_configuration_is_pinned_to_its_genome_version():
    from greg.cognition.contracts import digest
    from greg.cognition.genomes import library
    assert set(E.EVOLVABLE_CONFIG_PINS) == set(E.TARGET_SPECS)
    for name, (family, version, config_digest) in E.EVOLVABLE_CONFIG_PINS.items():
        assert library.executables()[family].genome.version == version, (name, "bump the pin with the version")
        assert digest(_shipped(name)) == config_digest, (name, "a changed configuration needs a version bump")


@pytest.mark.skipif(not isolation.available()["available"] or isolation.available()["abi"] < 6,
                    reason="Landlock scoping needs ABI 6")
def test_a_confined_sandbox_cannot_signal_its_parent_or_list_the_repository():
    import subprocess
    import sys
    code = ("import json, os, sys, tempfile; sys.path.insert(0, %r)\n"
            "from greg import isolation\n"
            "info = isolation.confine(tempfile.mkdtemp(), [], list_code=False)\n"
            "out = {'info': info}\n"
            "for name, act in (('signal', lambda: os.kill(os.getppid(), 0)), ('list', lambda: os.listdir(%r))):\n"
            "    try:\n        act(); out[name] = 'ALLOWED'\n"
            "    except OSError as exc:\n        out[name] = type(exc).__name__\n"
            "print(json.dumps(out))\n") % (str(E.ROOT), str(E.ROOT))
    proc = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, timeout=60)
    out = json.loads(proc.stdout)
    assert out["signal"] == "PermissionError" and out["list"] == "PermissionError", out
    assert out["info"]["signals"] == "scoped to the domain" and out["info"]["repository_listing"] == "denied"


def test_an_earlier_cycles_split_reproduces_its_frozen_evaluator_seals():
    """Splits are named per cycle, so adding cycle 4 leaves cycle 3 reproducible: its evaluators re-seal to the
    digests its frozen record states (evaluator code, score function, rule, outcomes and inputs)."""
    from greg.cognition.genomes import developmental as D
    record = json.loads((E.ROOT / "docs/evidence/greg-protected-evolution/2026-10-14/cycle-cr-3.json").read_text())
    train, held, _ = E.cr_split("cycle-3")
    assert E.SealedEvaluator(train, D.constraint_release_score).seal == record["evaluator_seals"]["train"]
    assert E.SealedEvaluator(held, D.constraint_release_score).seal == record["evaluator_seals"]["heldout"]
    assert E.CR_CURRENT_SPLIT != "cycle-3"
