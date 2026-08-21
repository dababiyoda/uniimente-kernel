"""The runtime contract is frozen; drift must break the build, not pass quietly.

The contract in ``runtime/contract.py`` is written before the runtime spine,
before the evaluator freeze, and before any candidate code exists. Its whole
value is that it cannot be adjusted afterwards to match whatever the runtime
turned out to do. These tests are the mechanism that makes that true rather than
merely intended.

The failure mode being guarded is specific and has happened repeatedly in this
repository's own history: an experiment quietly retuned to fit its result, and an
instrument whose silence looked like success.
"""
from __future__ import annotations

import pytest

from runtime import contract


def test_contract_hash_has_not_drifted():
    """Any edit to a frozen table changes this hash and fails here.

    If this test fails, that is the mechanism working. Do not update the constant
    to silence it — decide whether the amendment is intended, and if it is, make
    it visible in the diff alongside the new hash.
    """
    assert contract.contract_digest() == contract.CONTRACT_SHA256, (
        "runtime/contract.py changed after freezing. This is not automatically "
        "wrong, but it must be deliberate and reviewable."
    )


def test_the_seal_can_actually_fire(monkeypatch):
    """Negative control: prove the freeze detects a change, rather than trusting it.

    A hash guard that has never been observed to fail is indistinguishable from a
    hash guard that cannot fail. This mutates one frozen table in memory and
    requires the digest to move.
    """
    before = contract.contract_digest()
    assert before == contract.CONTRACT_SHA256

    mutated = dict(contract._FROZEN_TABLES)
    mutated["resource_ceilings"] = {**contract.RESOURCE_CEILINGS, "max_candidates": 999}
    monkeypatch.setattr(contract, "_FROZEN_TABLES", mutated)

    after = contract.contract_digest()
    assert after != before, "the frozen tables changed and the digest did not move"
    assert after != contract.CONTRACT_SHA256


def test_all_twelve_closure_conditions_are_present():
    assert sorted(contract.CLOSURE_CONDITIONS) == list(range(1, 13))
    for number, text in contract.CLOSURE_CONDITIONS.items():
        assert text.strip(), f"condition {number} has no text"


def test_closure_requires_every_condition():
    """Eleven of twelve is not a closure."""
    all_true = {c: True for c in contract.CLOSURE_CONDITIONS}
    assert contract.closure_achieved(all_true) is True

    for condition in contract.CLOSURE_CONDITIONS:
        partial = dict(all_true)
        partial[condition] = False
        assert contract.closure_achieved(partial) is False, (
            f"closure reported as achieved with condition {condition} unmet"
        )
        assert contract.unmet_conditions(partial) == [condition]


def test_missing_conditions_are_named_not_counted():
    """'Closure not achieved' with no explanation is a silent result."""
    nothing_satisfied: dict[int, bool] = {}
    assert contract.closure_achieved(nothing_satisfied) is False
    assert contract.unmet_conditions(nothing_satisfied) == list(range(1, 13))


def test_the_two_conditions_a_benchmark_cannot_satisfy_are_named():
    """Conditions 2 and 7 are what separate a closure from a demonstration.

    2 — the running process actually consumes the target function.
    7 — the runtime actually routes work through the replacement.

    A detached benchmark satisfies neither, which is precisely why the planning
    round's strongest objection is answered structurally rather than by caveat.
    """
    assert contract.CONDITIONS_THAT_REQUIRE_A_RUNNING_SYSTEM == (2, 7)
    assert "consumed by that running process" in contract.CLOSURE_CONDITIONS[2]
    assert "routes work through the replacement" in contract.CLOSURE_CONDITIONS[7]


def test_evaluator_and_authority_surfaces_are_protected():
    """Candidates may never reach the environment that judges them."""
    for path in (
        "constitution/",
        "authority/",
        "identity/",
        "runtime/contract.py",
        "runtime/evaluator/",
        "evolution/repair/spec.py",
    ):
        assert path in contract.PROTECTED_PATHS, f"{path} is not protected"


def test_candidate_write_surface_is_narrow():
    assert contract.CANDIDATE_WRITABLE_PATHS == ("<chamber>/candidate/",)
    for writable in contract.CANDIDATE_WRITABLE_PATHS:
        for protected in contract.PROTECTED_PATHS:
            assert not writable.startswith(protected), (
                f"writable path {writable} overlaps protected path {protected}"
            )


def test_episode_is_consequence_inert_with_no_network():
    assert contract.CONSEQUENCE_CLASS == "INERT"
    assert contract.RESOURCE_CEILINGS["network_access"] == "DENIED"


def test_every_negative_control_declares_a_forced_failure():
    """A control that does not force a failure proves nothing."""
    assert len(contract.REQUIRED_NEGATIVE_CONTROLS) >= 6
    for name, expected in contract.REQUIRED_NEGATIVE_CONTROLS.items():
        assert expected.strip(), f"negative control {name} declares no expected outcome"
        assert any(
            word in expected for word in ("halts", "fails", "rejected", "not counted", "not as pass")
        ), f"negative control {name} does not describe a failure: {expected!r}"


def test_no_candidate_qualifying_is_a_result_not_a_pass():
    """The episode must be able to conclude 'no closure' without that reading as success."""
    outcome = contract.REQUIRED_NEGATIVE_CONTROLS["no_candidate_qualifies"]
    assert "CLOSURE_NOT_ACHIEVED" in outcome
    assert "not as pass" in outcome


def test_reimplementation_of_existing_components_is_prohibited():
    """The measured defect was disconnection, not absence. Do not rebuild."""
    for component in ("linker", "closure_controller", "capability_registry", "adapters"):
        assert component in contract.REQUIRED_EXISTING_COMPONENTS
    assert set(contract.REIMPLEMENTATION_PROHIBITED) == set(
        contract.REQUIRED_EXISTING_COMPONENTS
    )


def test_rollback_target_is_the_frozen_baseline():
    assert contract.ROLLBACK_TARGET == contract.BASELINE_COMMIT
    assert len(contract.ROLLBACK_TARGET) == 40


def test_contract_creates_no_authority_and_performs_no_io():
    """A specification module must stay a specification.

    Import-time side effects are how a 'contract' quietly becomes a participant.

    This inspects the parsed AST rather than the source text. A substring scan
    was tried first and produced a false positive: the ceiling named
    ``max_subprocesses_per_candidate`` contains the word ``subprocess`` while the
    module imports nothing of the kind. A guard that fires when nothing is wrong
    is as broken as one that stays silent, and it trains people to ignore it.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(contract))

    forbidden_modules = {
        "os", "sys", "socket", "subprocess", "urllib", "requests",
        "http", "pathlib", "shutil", "importlib",
    }
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    leaked = imported & forbidden_modules
    assert not leaked, f"runtime/contract.py imports {sorted(leaked)}; it must stay inert"

    forbidden_calls = {"open", "exec", "eval", "compile", "__import__", "input"}
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
    leaked_calls = called & forbidden_calls
    assert not leaked_calls, (
        f"runtime/contract.py calls {sorted(leaked_calls)}; it must perform no I/O"
    )

    # Module level must define constants and functions only — no executable
    # statements that could act at import time.
    for node in tree.body:
        assert isinstance(
            node,
            (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.FunctionDef,
             ast.ClassDef, ast.Expr),
        ), f"runtime/contract.py executes {type(node).__name__} at module level"


@pytest.mark.parametrize("stage", ["cold_start", "verify_restoration",
                                   "restart_and_prove_episode_survives_recovery"])
def test_episode_stages_include_the_load_bearing_ones(stage):
    assert stage in contract.EPISODE_STAGES


def test_episode_stages_are_ordered_start_to_recovery():
    stages = contract.EPISODE_STAGES
    assert stages[0] == "cold_start"
    assert stages[-1] == "restart_and_prove_episode_survives_recovery"
    assert stages.index("evaluate_through_protected_evaluator") > stages.index(
        "build_candidates_in_isolated_chambers"
    ), "candidates must be built before they are evaluated"
    assert stages.index("verify_restoration") > stages.index(
        "route_internal_request_through_replacement"
    ), "restoration must be verified after work is routed through the replacement"
