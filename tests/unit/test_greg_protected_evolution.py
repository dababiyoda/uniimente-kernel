"""P8 protected evolutionary cognition: closed space, confined candidates, sealed evaluator, no activation."""
import json
import math
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
    monkeypatch.setattr(E, "_spent_heldout", lambda *a, **k: {})   # so has the spent-split rule
    _small_forecasting_split(monkeypatch)
    frozen = tmp_path / "freeze.json"
    E.freeze("forecast_quantile", frozen, generations=2, population=2)
    record = E.cycle(generations=2, population=2, out=tmp_path / "c.json", freeze=frozen,
                     require_confinement=isolation.available()["available"], allow_dirty_for_test=True)
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
    monkeypatch.setattr(E, "_spent_heldout", lambda *a, **k: {})
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
        E.cycle(generations=2, population=2, out=tmp_path / "c.json", freeze=frozen, require_confinement=False,
                allow_dirty_for_test=True)
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
        E.cycle(generations=2, population=2, out=tmp_path / "c.json", freeze=frozen, require_confinement=False,
                allow_dirty_for_test=True)


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
                require_confinement=isolation.available()["available"], allow_dirty_for_test=True)
    assert not (tmp_path / "c.json").exists()


def test_a_dirty_trusted_file_is_refused_for_a_freeze_and_for_a_record(monkeypatch, tmp_path):
    monkeypatch.setattr(E, "_dirty", lambda paths: ["greg/cognition/evolution.py"])
    monkeypatch.setattr(E, "_clean_room_violations", lambda code: [])      # the clean room has its own tests
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
    """The configuration the shipped executable actually runs, observed on a development instance (independent
    review, P8-5: comparing the named constant alone let the executable run a rejected configuration), which must
    also be the named constant."""
    import importlib
    from greg.cognition import evolution_sandbox as S
    from greg.cognition.genomes import library
    spec = E.TARGET_SPECS[target_name]()
    constant = getattr(importlib.import_module(spec.proposal["module"][:-3].replace("/", ".")),
                       spec.proposal["constant"])
    executable = library.executables()[E.EVOLVABLE_CONFIG_PINS[target_name][0]]
    module_name, function, _ = S.TARGETS[target_name]
    module = importlib.import_module(module_name)
    real, seen = getattr(module, function), []

    def spy(config, data):
        seen.append(json.loads(json.dumps(config)))
        return real(config, data)
    setattr(module, function, spy)
    try:
        data, _ = executable.instance(3)                                    # development seed
        out = executable.solve(data, {"latency_s": 5.0, "compute": 100000})
    finally:
        setattr(module, function, real)
    assert seen, (target_name, "the shipped executable never ran its evolvable method")
    assert all(c == seen[0] for c in seen) and seen[0] == json.loads(json.dumps(constant)), target_name
    # what the method reports it ran (the verifier's round 2: a substitution inside the method passed the spy)
    ran = _effective(target_name, out["certificate"], data)
    assert ran == {k: seen[0][k] for k in ran}, (target_name, ran)
    return seen[0]


def _effective(target_name, certificate, data):
    """The configuration a certificate shows the run used, from values the run computed rather than copied from
    its argument (the verifier's round 3: the forecasting certificate copies fit_window, the grids and the scale
    from the argument). Constraint release: the whole search configuration. Immune: detectors, folds, the alarm
    fraction (target_rate / tolerance) and the whitening (a Cholesky factor is full whitening). Forecasting: the
    rolling origins actually evaluated (one more than the configured count on this long development series).
    The rest - forecasting's window, grids, error model and scale; immune's uniform share and scale set - is not
    observable from the certificate and rests on the argument check above and on review."""
    if target_name == "constraint_release":
        return certificate["search_config"]
    if target_name == "forecast_quantile":
        return {"origins": certificate["rolling_origins"] - 1}
    cal = certificate["calibration"]
    return {"detectors": certificate["detectors_generated"], "calibration_folds": int(cal["method"].split("-fold")[0]),
            "alarm_fraction": round(cal["target_rate"] / data["max_false_alarm_rate"], 9),
            "whitening": "full" if "cholesky" in certificate["standardisation"] else "diagonal"}


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


# ------------------------------------------------------------------ independent review 2026-10-15: P8 integrity v2
def test_the_frozen_closure_covers_every_repository_file_each_target_runs_in_both_processes():
    """P8-1: the closure was ten named files; package __init__ files and ~25 parent-imported modules ran outside it.
    A fresh interpreter runs a development cycle per target (dev-seed items) and reports what it executed."""
    import subprocess
    import sys
    script = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from greg import isolation
from greg.cognition import evolution as E
from greg.cognition.genomes import collective, developmental as D, forecasting
train, held, _ = E.forecasting_split()
f_items = lambda d, n: dict(list(d.items())[:n])
def dev(make, seeds, category):
    return {f"s{s}": {"data": make(s)[0], "truth": make(s)[1], "category": category(make(s)[0])} for s in seeds}
E.forecasting_split = lambda seed=808, excluded_seeds=None: (f_items(train, 3), f_items(held, 2), [])
E.immune_split = lambda: (dev(collective.immune_gaussian_instance, (1, 2, 3), collective.immune_dimension_band),
                          dev(collective.immune_gaussian_instance, (4, 5), collective.immune_dimension_band), [])
cr = lambda seeds: dev(D.constraint_release_instance, seeds, D.constraint_release_subregion)
E.cr_split = lambda name=E.CR_CURRENT_SPLIT: (cr((1, 2, 3)), cr((4, 5)), [])
E.FAILURE_RATE_TRIGGER = 0.0
out = {}
for name in sorted(E.TARGET_SPECS):
    sandbox = []
    real = E.run_candidate
    def spy(*a, **k):
        result = real(*a, **k)
        sandbox.append(sorted(result["loaded"]))
        return result
    E.run_candidate = spy
    record = E.cycle(generations=1, population=2, target_name=name,
                     require_confinement=isolation.available()["available"])
    E.run_candidate = real
    closure = set(E.trusted_closure(name))
    out[name] = {"decision": record["decision"],
                 "parent_outside": sorted(E._loaded_repository_files() - closure),
                 "sandbox_outside": sorted({p for run in sandbox for p in run} - closure),
                 "sandbox_inits": sorted({p for run in sandbox for p in run if p.endswith("__init__.py")})}
print(json.dumps(out))
'''
    proc = subprocess.run([sys.executable, "-I", "-c", script, str(E.ROOT)], capture_output=True, timeout=900)
    assert proc.returncode == 0, proc.stderr[-2000:]
    out = json.loads(proc.stdout.splitlines()[-1])
    assert set(out) == set(E.TARGET_SPECS)
    for name, seen in out.items():
        assert seen["parent_outside"] == [] and seen["sandbox_outside"] == [], (name, seen)
        assert {"greg/__init__.py", "greg/cognition/__init__.py",
                "greg/cognition/genomes/__init__.py"} <= set(seen["sandbox_inits"]), name


def test_the_parent_refuses_a_sandbox_that_executed_code_outside_or_unlike_the_freeze(target):
    """P8-1: only the method module was compared; an edited package __init__ or helper ran unnoticed."""
    train, _, _ = E.forecasting_split()
    problems = [{"id": k, "data": v["data"]} for k, v in list(train.items())[:1]]
    code = E._code("forecast_quantile")
    confine = isolation.available()["available"]
    run = E.run_candidate(target, target.incumbent, problems, require_confinement=confine, expected_code=code)
    assert set(run["loaded"]) <= set(code) and "greg/cognition/genomes/__init__.py" in run["loaded"]
    assert all(run["loaded"][p] == code[p] for p in run["loaded"])
    uncovered = {p: v for p, v in code.items() if p != "greg/cognition/genomes/__init__.py"}
    with pytest.raises(E.EvolutionError, match="does not cover"):
        E.run_candidate(target, target.incumbent, problems, require_confinement=confine, expected_code=uncovered)
    edited = {**code, "greg/__init__.py": "sha256:" + "4" * 64}
    with pytest.raises(E.EvolutionError, match="FROZEN_INPUT_CHANGED: the sandbox executed greg/__init__.py"):
        E.run_candidate(target, target.incumbent, problems, require_confinement=confine, expected_code=edited)


def test_the_sandbox_hashes_the_bytes_it_compiles_and_never_reads_repository_bytecode():
    """P8-2: an UNCHECKED_HASH .pyc in the gitignored __pycache__ ran instead of the hashed source."""
    import importlib.machinery
    from greg.cognition import evolution_sandbox as S
    source = E.ROOT / "greg/isolation.py"
    loader = importlib.machinery.SourceFileLoader("greg.isolation", str(source))
    with pytest.raises(OSError, match="never executed"):
        S._get_data(loader, str(E.ROOT / "greg/__pycache__/isolation.cpython-313.pyc"))
    assert S._get_data(loader, str(source)) == source.read_bytes()
    assert S._EXECUTED["greg/isolation.py"] == E._sha(source)
    # importing the module for TARGETS changes nothing in the importing process
    assert importlib.machinery.SourceFileLoader.get_data is not S._get_data


def test_a_development_run_never_looks_at_the_held_out_split(monkeypatch, tmp_path):
    """P8-3: without a freeze the cycle evaluated the reserved held-out split, any number of times. The same
    settings under a freeze reach the one look."""
    monkeypatch.setattr(E, "FAILURE_RATE_TRIGGER", 0.0)
    monkeypatch.setattr(E, "TRAIN_GAIN_MIN", -math.inf)
    monkeypatch.setattr(E, "STRESS_TOLERANCE", math.inf)
    monkeypatch.setattr(E, "outputs_verified", lambda *a: True)
    monkeypatch.setattr(E, "_dirty", lambda paths: [])
    monkeypatch.setattr(E, "_spent_heldout", lambda *a, **k: {})
    _small_forecasting_split(monkeypatch)
    confine = isolation.available()["available"]
    seen = []
    real = E.SealedEvaluator.losses

    def spy(self, outputs):                     # every later evaluation scores better, so a candidate advances
        seen.append(set(self._items))
        return {k: -float(len(seen)) for k in real(self, outputs)}
    monkeypatch.setattr(E.SealedEvaluator, "losses", spy)
    _, held, _ = E.forecasting_split()
    record = E.cycle(generations=2, population=2, require_confinement=confine)
    assert record["decision"] == "STOPPED_BEFORE_HELDOUT" and "heldout" not in record
    frozen = tmp_path / "freeze.json"
    E.freeze("forecast_quantile", frozen, generations=2, population=2)
    record = E.cycle(generations=2, population=2, freeze=frozen, require_confinement=confine)   # no record written
    assert record["decision"] == "STOPPED_BEFORE_HELDOUT" and "heldout" not in record
    assert not any(items & set(held) for items in seen)
    # a test run may not look at a registered held-out split either (verifier's round-2 finding) ...
    with pytest.raises(E.EvolutionError, match="never evaluates a registered held-out split"):
        E.cycle(generations=2, population=2, freeze=frozen, require_confinement=confine,
                out=tmp_path / "c.json", allow_dirty_for_test=True)
    assert not any(items & set(held) for items in seen) and not (tmp_path / "c.json").exists()
    # ... and takes the one look only on development instances, writing its record
    from greg.cognition.genomes import developmental as D

    def dev(seeds):
        return {f"s{s}": {"data": D.constraint_release_instance(s)[0], "truth": D.constraint_release_instance(s)[1],
                          "category": D.constraint_release_subregion(D.constraint_release_instance(s)[0])}
                for s in seeds}
    monkeypatch.setattr(E, "cr_split", lambda name=E.CR_CURRENT_SPLIT: (dev((1, 2)), dev((4, 5)), []))
    frozen = tmp_path / "cr-freeze.json"
    E.freeze("constraint_release", frozen, generations=2, population=2)
    record = E.cycle(generations=2, population=2, target_name="constraint_release", freeze=frozen,
                     require_confinement=confine, out=tmp_path / "c.json", allow_dirty_for_test=True)
    assert record["decision"] in ("RETAIN", "REJECT") and record["heldout"]["n"] == 2
    assert json.loads((tmp_path / "c.json").read_text())["heldout"] == record["heldout"]


def test_the_sandbox_puts_the_repository_after_the_standard_library():
    """A file at the repository root named like a standard module must not shadow it in the sandbox (the
    verifier's addition to P8-1); the repository's packages still precede installed ones."""
    from greg.cognition import evolution_sandbox as S
    path = ["/usr/lib/python313.zip", "/usr/lib/python3.13", "/usr/lib/python3.13/lib-dynload",
            "/usr/local/lib/python3.13/dist-packages", "/usr/lib/python3/dist-packages"]
    assert S.search_path(path) == [*path[:3], str(S.ROOT), *path[3:]]
    assert S.search_path(path[:3]) == [*path[:3], str(S.ROOT)]


def test_a_freeze_refuses_a_held_out_split_an_earlier_cycle_or_freeze_looked_at(monkeypatch, tmp_path):
    """One look per held-out item: cycle 4's frozen split (s7500-s7589) and cycles 1-3's splits are spent."""
    from greg.cognition.genomes import developmental as D
    monkeypatch.setattr(E, "_dirty", lambda paths: [])
    data, truth = D.constraint_release_instance(3)                            # development seed, relabelled
    item = {"data": data, "truth": truth, "category": D.constraint_release_subregion(data)}
    monkeypatch.setattr(E, "cr_split", lambda name=E.CR_CURRENT_SPLIT: ({"s3": item}, {"s7500": item}, []))
    with pytest.raises(E.EvolutionError, match="SPLIT_SPENT.*2026-10-15-cr-4/freeze.json"):
        E.freeze("constraint_release", tmp_path / "f.json")
    assert not (tmp_path / "f.json").exists()
    monkeypatch.setattr(E, "cr_split", lambda name=E.CR_CURRENT_SPLIT: ({"s3": item}, {"s7300": item}, []))
    with pytest.raises(E.EvolutionError, match="SPLIT_SPENT.*cycle-cr-3"):
        E.freeze("constraint_release", tmp_path / "f.json")
    spent = E._spent_heldout("immune_detect")
    assert {f"s{s}" for s in E.IMMUNE_HELDOUT_SEEDS} <= set().union(*spent.values())


def test_a_recorded_cycle_needs_a_committed_freeze_confinement_and_the_clean_room(monkeypatch, tmp_path):
    """P8-4: a freeze outside the repository (or edited after its commit) was accepted; P8-7: a recorded cycle
    could run unconfined; P8-1/P8-2: nothing required the run to vouch for the code it executed."""
    with pytest.raises(E.EvolutionError, match="CONFINEMENT_REQUIRED"):
        E.cycle(out=tmp_path / "c.json", freeze=tmp_path / "f.json", require_confinement=False)
    with pytest.raises(E.EvolutionError, match="CLEAN_ROOM_REQUIRED"):     # a test process is no clean room
        E.cycle(out=tmp_path / "c.json", freeze=tmp_path / "f.json")
    monkeypatch.setattr(E, "_clean_room_violations", lambda code: [])
    monkeypatch.setattr(E, "_dirty", lambda paths: [])
    (tmp_path / "f.json").write_text(json.dumps({"inputs": {}}))
    with pytest.raises(E.EvolutionError, match="FREEZE_NOT_COMMITTED"):
        E.cycle(out=tmp_path / "c.json", freeze=tmp_path / "f.json")
    elsewhere = E.ROOT / "docs/evidence/greg-genome-admission/2026-10-15-v3/freeze.json"  # committed, not a P8 run's
    with pytest.raises(E.EvolutionError, match="FREEZE_NOT_COMMITTED"):
        E.cycle(target_name="constraint_release", out=tmp_path / "c.json", freeze=elsewhere)
    with pytest.raises(E.EvolutionError, match="FREEZE_NOT_COMMITTED"):
        E.run_recorded("constraint_release", tmp_path / "f.json", tmp_path / "c.json")
    committed = E.ROOT / "docs/evidence/greg-protected-evolution/2026-10-15-cr-4/freeze.json"
    monkeypatch.setattr(E, "_dirty", lambda paths: list(paths))          # an uncommitted edit of a committed freeze
    with pytest.raises(E.EvolutionError, match="FREEZE_NOT_COMMITTED"):
        E.run_recorded("constraint_release", committed, tmp_path / "c.json")


def test_the_clean_room_names_repository_bytecode_and_unfrozen_executed_code(monkeypatch, tmp_path):
    import sys
    import types
    import importlib.machinery
    monkeypatch.setattr(E.subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="",
                                                                                     stderr=""))  # a fresh checkout
    entry = lambda loader, path: b""                                            # the clean-room entry's loader
    entry.executed = {}
    monkeypatch.setattr(importlib.machinery.SourceFileLoader, "get_data", entry)
    code = {p: "x" for p in E._loaded_repository_files()}
    monkeypatch.setattr(sys, "pycache_prefix", None)
    assert any("bytecode" in v for v in E._clean_room_violations(code))
    prefix = tmp_path / "prefix"
    planted = prefix / E.ROOT.relative_to(E.ROOT.anchor) / "greg/cognition/genomes"
    planted.mkdir(parents=True)
    monkeypatch.setattr(sys, "pycache_prefix", str(prefix))
    assert E._clean_room_violations(code) == []
    (planted / "developmental.cpython-313.pyc").write_bytes(b"\0")
    assert any("holds repository bytecode" in v for v in E._clean_room_violations(code))
    (planted / "developmental.cpython-313.pyc").unlink()
    stray = types.ModuleType("greg_review_stray")
    stray.__file__ = str(E.ROOT / "greg/cognition/genomes/strategic_patch.py")
    monkeypatch.setitem(sys.modules, "greg_review_stray", stray)
    assert any("strategic_patch.py" in v for v in E._clean_room_violations(code))


def test_the_dirty_check_compares_bytes_with_head_so_an_index_flag_cannot_hide_an_edit(monkeypatch, tmp_path):
    """P8-6: ``git status`` trusted skip-worktree/assume-unchanged; the check now compares content with HEAD."""
    import subprocess
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 1\n")
    git("add", ".")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c")
    monkeypatch.setattr(E, "ROOT", tmp_path)
    assert E._dirty(["a.py", "b.py"]) == []
    git("update-index", "--skip-worktree", "a.py")
    (tmp_path / "a.py").write_text("x = 0\n")
    git("update-index", "--assume-unchanged", "b.py")
    (tmp_path / "b.py").write_text("y = 0\n")
    assert subprocess.run(["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True).stdout == ""
    assert E._dirty(["a.py", "b.py", "untracked.py"]) == ["a.py", "b.py", "untracked.py"]


def test_confinement_failure_is_reported_as_such_and_an_unconfined_run_asks_for_none(monkeypatch, target):
    """P8-7: without Landlock the child omitted its digest and the parent blamed METHOD_CHANGED; the request
    always asked for confinement."""
    problems = [{"id": "a", "data": E.forecasting_split()[0][next(iter(E.forecasting_split()[0]))]["data"]}]
    sent = []
    real_run = __import__("greg.capabilities", fromlist=["run_isolated"]).run_isolated

    def spy(argv, **kw):
        sent.append(json.loads(kw["input_bytes"]))
        return real_run(argv, **kw)
    monkeypatch.setattr("greg.capabilities.run_isolated", spy)
    E.run_candidate(target, target.incumbent, problems, require_confinement=False)
    assert sent[-1]["confine"] is False
    real = E.json.loads

    def unavailable(text):
        out = real(text)
        if isinstance(out, dict) and "outputs" in out:
            out = {"confined": None, "error": "CONFINEMENT_UNAVAILABLE: no Landlock", "imported": out["imported"],
                   "loaded": out["loaded"]}
        return out
    monkeypatch.setattr(E.json, "loads", unavailable)
    with pytest.raises(E.EvolutionError, match="CONFINEMENT_UNAVAILABLE"):
        E.run_candidate(target, target.incumbent, problems, require_confinement=True)

    def failed(text):                                   # an unconfined child's own error is reported as itself
        out = real(text)
        return {"confined": None, "error": "UNKNOWN_TARGET"} if isinstance(out, dict) and "outputs" in out else out
    monkeypatch.setattr(E.json, "loads", failed)
    with pytest.raises(E.EvolutionError, match="UNKNOWN_TARGET"):
        E.run_candidate(target, target.incumbent, problems, require_confinement=False)


@pytest.mark.parametrize("name,key,value,why", [
    ("constraint_release", "p_restart", float("nan"), "outside"),
    ("constraint_release", "p_restart", True, "outside"),
    ("forecast_quantile", "beta_set", [0.0, 0.05, 0.1, float("nan")], "outside the declared space"),
    ("immune_detect", "detectors", float("nan"), "outside the declared space")])
def test_non_finite_and_mistyped_values_are_evolution_errors(name, key, value, why):
    """P8-8: NaN inside a choice escaped as a bare ValueError."""
    target = E.TARGET_SPECS[name]().target()
    with pytest.raises(E.EvolutionError, match=why):
        target.validate({**target.incumbent, key: value})


def test_float_values_have_one_canonical_form_and_unknown_kinds_are_refused():
    """P8-8: 0 and -0.0 passed unchanged and became configurations distinct from the incumbent's 0.0."""
    target = E.cr_target()
    incumbent = E.config_id(target.validate(target.incumbent))
    assert incumbent == E.config_id(target.incumbent)
    for same in (0, -0.0, 0.0):
        assert E.config_id(target.validate({**target.incumbent, "p_restart": same})) == incumbent
    with pytest.raises(E.EvolutionError, match="unknown kinds"):
        E.Target("x", {"a": ("int", (0, 10))}, {"a": 1})


@pytest.mark.skipif(not isolation.available()["available"] or isolation.available()["abi"] < 6,
                    reason="Landlock scoping needs ABI 6")
def test_a_confined_process_cannot_reach_an_abstract_socket_created_outside_its_domain():
    """L1: only signal scoping had a test; dropping SCOPE_ABSTRACT_UNIX_SOCKET passed every suite."""
    import os
    import socket
    import subprocess
    import sys
    name = f"\0greg-review-{os.getpid()}"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(name)
    listener.listen(1)
    try:
        code = ("import json, socket, sys, tempfile; sys.path.insert(0, %r)\n"
                "from greg import isolation\n"
                "info = isolation.confine(tempfile.mkdtemp(), [], list_code=False)\n"
                "s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
                "try:\n    s.connect(%r); out = 'ALLOWED'\n"
                "except OSError as exc:\n    out = type(exc).__name__\n"
                "print(json.dumps({'connect': out, 'scopes': info['ipc_scopes']}))\n") % (str(E.ROOT), name)
        proc = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, timeout=60)
        out = json.loads(proc.stdout)
    finally:
        listener.close()
    assert out == {"connect": "PermissionError", "scopes": ["abstract_unix_socket", "signal"]}, out


@pytest.mark.skipif(not isolation.available()["available"], reason="Landlock unavailable on this host")
def test_confinement_refuses_a_process_whose_other_threads_would_stay_unconfined():
    """L2: landlock_restrict_self confines the calling thread only; a pre-existing thread kept full access."""
    import subprocess
    import sys
    code = ("import json, sys, tempfile, threading, time; sys.path.insert(0, %r)\n"
            "from greg import isolation\n"
            "threading.Thread(target=time.sleep, args=(5,), daemon=True).start()\n"
            "try:\n    isolation.confine(tempfile.mkdtemp(), [], list_code=False); print('CONFINED')\n"
            "except isolation.IsolationError as exc:\n    print('REFUSED', exc)\n") % str(E.ROOT)
    proc = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=60)
    assert proc.stdout.startswith("REFUSED") and "2 threads" in proc.stdout, proc.stdout + proc.stderr


# ------------------------------------------------------------------ verifier's round 2 on the P8 fix (2026-10-15)
def test_the_clean_room_requires_a_fresh_checkout(monkeypatch, tmp_path):
    """A direct --inside run in a working tree (untracked or ignored files, __pycache__ included) is not a clean
    room, whatever bytecode prefix the caller chose."""
    import subprocess
    import sys
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    (tmp_path / ".gitignore").write_text("__pycache__/\n")
    (tmp_path / "a.py").write_text("x = 1\n")
    git("add", ".")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c")
    import importlib.machinery
    entry = importlib.machinery.SourceFileLoader.get_data
    monkeypatch.setattr(importlib.machinery.SourceFileLoader, "get_data", lambda loader, path: entry(loader, path))
    importlib.machinery.SourceFileLoader.get_data.executed = {}
    monkeypatch.setattr(E, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "pycache_prefix", str(tmp_path.parent / "fresh-prefix"))
    assert E._clean_room_violations(None) == []
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "a.cpython-313.pyc").write_bytes(b"\0")
    assert any("not a fresh checkout" in v for v in E._clean_room_violations(None))


def test_a_recorded_cycle_checks_the_clean_room_before_it_imports_the_target(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(E, "_clean_room_violations", lambda code: ["planted"])
    monkeypatch.setitem(E.TARGET_SPECS, "constraint_release", lambda: called.append(1))
    with pytest.raises(E.EvolutionError, match="CLEAN_ROOM_REQUIRED: \\['planted'\\]"):
        E.cycle(target_name="constraint_release", out=tmp_path / "c.json", freeze=tmp_path / "f.json")
    assert called == []


def test_the_launcher_refuses_a_dirty_or_bytecode_bearing_tree_and_disables_hooks(monkeypatch, tmp_path):
    """The verifier tainted a 'clean_room' record through the launching process (an uncommitted edit it loaded,
    never-checked bytecode) and through a post-checkout hook run by git worktree add."""
    import subprocess
    committed = E.ROOT / "docs/evidence/greg-protected-evolution/2026-10-15-cr-4/freeze.json"
    with pytest.raises(E.EvolutionError, match="FREEZE_NOT_COMMITTED"):          # committed, but not a freeze
        E.run_recorded("constraint_release", E.ROOT / "greg/path.json", tmp_path / "c.json")
    monkeypatch.setattr(E, "_dirty", lambda paths: [p for p in paths if p == "greg/cognition/genomes/__init__.py"])
    with pytest.raises(E.EvolutionError, match="DIRTY_TREE: the launching tree"):
        E.run_recorded("constraint_release", committed, tmp_path / "c.json")
    monkeypatch.setattr(E, "_dirty", lambda paths: [])
    monkeypatch.setattr(E, "_unchecked_bytecode", lambda: ["greg/cognition/evolution.py"])
    with pytest.raises(E.EvolutionError, match="never-checked repository bytecode"):
        E.run_recorded("constraint_release", committed, tmp_path / "c.json")
    monkeypatch.setattr(E, "_unchecked_bytecode", lambda: [])
    calls = []

    class Stop(Exception):
        pass

    def run(argv, **kw):
        calls.append(argv)
        if "add" in argv:
            raise Stop
        return subprocess.CompletedProcess(argv, 0, b"", b"")
    monkeypatch.setattr(E.subprocess, "run", run)
    with pytest.raises(Stop):
        E.run_recorded("constraint_release", committed, tmp_path / "c.json")
    add = next(argv for argv in calls if "worktree" in argv)
    assert add[:3] == ["git", "-c", "core.hooksPath=/dev/null"] and "add" in add
    calls.clear()
    monkeypatch.setattr(E.subprocess, "run", lambda argv, **kw: calls.append(argv) or
                        subprocess.CompletedProcess(argv, 0, b"", b""))
    assert E.run_recorded("constraint_release", committed, tmp_path / "c.json") == 0
    inner = next(argv for argv in calls if "--inside" in argv)
    assert inner[1:5] == ["-E", "-s", "-B", "-X"] and inner[5].startswith("pycache_prefix=")
    assert inner[6].endswith("greg/cognition/evolution_room.py")          # the source-only entry, not -m


def test_never_checked_bytecode_of_a_loaded_module_is_named(monkeypatch, tmp_path):
    import sys
    import types
    pyc = tmp_path / "x.cpython-313.pyc"
    pyc.write_bytes(b"\0" * 4 + (0b01).to_bytes(4, "little") + b"\0" * 8)       # hash-based, source never checked
    module = types.ModuleType("greg_review_unchecked")
    module.__file__ = str(E.ROOT / "greg/cognition/x.py")
    module.__cached__ = str(pyc)
    monkeypatch.setitem(sys.modules, "greg_review_unchecked", module)
    assert E._unchecked_bytecode() == ["greg/cognition/x.py"]
    pyc.write_bytes(b"\0" * 4 + (0b11).to_bytes(4, "little") + b"\0" * 8)       # checked against the source
    assert E._unchecked_bytecode() == []


def test_the_spent_ledger_reads_every_freeze_under_the_evidence_tree(monkeypatch, tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "freeze.json").write_text(json.dumps({"inputs": {"target": "constraint_release",
                                                               "split": {"heldout": ["s9"]}}}))
    monkeypatch.setattr(E, "EVIDENCE", tmp_path)
    assert E._spent_heldout("constraint_release")["a/b/freeze.json"] == {"s9"}


# ------------------------------------------------------------------ verifier's round 3 on the P8 fix (2026-10-15)
def test_the_clean_room_entry_compiles_from_source_and_reads_no_bytecode():
    """evolution.py's own import chain loads every genome module, so a check after it is too late; the entry is
    stdlib-only and installs its loader before the first repository import."""
    import ast
    import importlib.machinery
    from greg.cognition import evolution_room as R
    source = E.ROOT / "greg/cognition/evolution_room.py"
    imported = {a.name.split(".")[0] for n in ast.walk(ast.parse(source.read_text()))
                for a in getattr(n, "names", []) if isinstance(n, (ast.Import, ast.ImportFrom))}
    imported |= {n.module.split(".")[0] for n in ast.walk(ast.parse(source.read_text()))
                 if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"greg", "cortex", "capabilities", "events", "provenance"}, imported
    loader = importlib.machinery.SourceFileLoader("greg.isolation", str(E.ROOT / "greg/isolation.py"))
    for pyc in ("/usr/lib/python3.13/json/__pycache__/decoder.cpython-313.pyc",
                str(E.ROOT / "greg/__pycache__/isolation.cpython-313.pyc")):
        with pytest.raises(OSError, match="never reads bytecode"):
            R.get_data(loader, pyc)
    assert R.get_data(loader, str(E.ROOT / "greg/isolation.py")) == (E.ROOT / "greg/isolation.py").read_bytes()
    assert R.get_data.executed["greg/isolation.py"] == E._sha(E.ROOT / "greg/isolation.py")
    assert importlib.machinery.SourceFileLoader.get_data is not R.get_data       # importing it installs nothing


def test_a_recorded_cycle_needs_the_clean_room_entry_and_its_compiled_digests_to_match(monkeypatch):
    import importlib.machinery
    import types
    monkeypatch.setattr(E.subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=0, stdout="",
                                                                                     stderr=""))
    monkeypatch.setattr(E.sys, "pycache_prefix", "/nonexistent-fresh-prefix")
    code = {p: "x" for p in E._loaded_repository_files()}
    assert any("clean-room entry" in v for v in E._clean_room_violations(code))     # started any other way
    entry = lambda loader, path: b""
    entry.executed = {"greg/cognition/genomes/developmental.py": "sha256:" + "5" * 64}
    monkeypatch.setattr(importlib.machinery.SourceFileLoader, "get_data", entry)
    assert any("unlike the freeze" in v for v in E._clean_room_violations(code))
    entry.executed = {"greg/cognition/genomes/developmental.py": "x"}
    assert E._clean_room_violations(code) == []


def test_a_virtualenv_inside_the_repository_is_not_repository_code(monkeypatch):
    """The launcher refused an honest run from a tree holding .venv (its .pth-loaded modules lie under ROOT)."""
    import types
    stray = types.ModuleType("greg_review_venv")
    stray.__file__ = str(E.ROOT / ".venv/lib/python3.11/site-packages/_distutils_hack/__init__.py")
    monkeypatch.setitem(E.sys.modules, "greg_review_venv", stray)
    assert not any(p.startswith(".venv/") for p in E._loaded_repository_files())
