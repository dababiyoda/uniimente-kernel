"""The institutional shell must report, and must stay unable to do anything else.

Specified by `docs/INSTITUTIONAL_SHELL_SPEC.md`. The failure modes worth
guarding are not "it crashes" — they are:

1. A stage grows a parameter, and a reporter becomes something a caller can
   point at a target.
2. The shell grows an execution or authority surface and quietly becomes a
   second control plane.
3. A broken reporter is swallowed, so the surface prints confidence it has not
   earned.
4. The composition re-enters itself. This one is not hypothetical: the first
   version of the `closures` stage verified the whole registry, the shell is in
   that registry, and its technical closure collects every pipeline — so
   verifying the shell verified the shell, without terminating.
"""
from __future__ import annotations

import ast
import os

import pytest

from closure.nervous_system_registry import FORBIDDEN_IMPORTS, package_imports
from shell.pipeline import (
    Outcome,
    Pipeline,
    ShellError,
    Stage,
    StageResult,
    ok,
    report,
)
from shell.pipelines import DEFAULT_PIPELINE, PIPELINES, SELF, STATUS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHELL_DIR = os.path.join(ROOT, "shell")


@pytest.fixture(scope="module")
def collected() -> dict:
    """Every pipeline, collected once. Slow enough to be worth sharing."""
    return {name: report(p) for name, p in PIPELINES.items()}


# ------------------------------------------------------- a stage cannot be aimed
def test_a_stage_reporter_may_not_take_a_target():
    """The zero-argument rule is the whole safety argument. Enforce it."""
    def needs_a_target(path):            # noqa: ARG001 - the point of the test
        return ok("x", "never runs")

    with pytest.raises(ShellError) as exc:
        Stage("aimed", needs_a_target)
    assert "must take none" in str(exc.value)


def test_a_stage_may_take_optional_arguments():
    """Defaults are fine — a caller still cannot be required to supply a target."""
    def with_default(root=ROOT):
        return ok("x", f"read {os.path.basename(root)}")

    assert Stage("defaulted", with_default).collect().outcome is Outcome.OK


def test_a_non_callable_reporter_is_refused():
    with pytest.raises(ShellError):
        Stage("not-callable", "blueprint/critical_path.py")   # type: ignore[arg-type]


# --------------------------------------------------------------- degradation
def test_a_raising_reporter_becomes_a_failed_stage():
    def detonate():
        raise RuntimeError("the ledger is unreadable")

    result = Stage("detonate", detonate).collect()
    assert result.outcome is Outcome.FAILED
    assert "the ledger is unreadable" in result.headline
    assert "RuntimeError" in result.headline


def test_a_reporter_returning_the_wrong_type_is_failed():
    result = Stage("wrong", lambda: {"technologies": 55}).collect()
    assert result.outcome is Outcome.FAILED
    assert "not a StageResult" in result.headline


def test_a_failing_stage_does_not_truncate_the_pipeline():
    """A partial picture with a named hole beats a truncated one."""
    def detonate():
        raise RuntimeError("boom")

    pipeline = Pipeline("mixed", "one broken, one fine", (
        Stage("broken", detonate),
        Stage("fine", lambda: ok("fine", "still collected")),
    ))
    results = report(pipeline).results
    assert [r.outcome for r in results] == [Outcome.FAILED, Outcome.OK]


def test_exit_code_reflects_the_worst_outcome():
    def detonate():
        raise RuntimeError("boom")

    clean = Pipeline("clean", "p", (Stage("a", lambda: ok("a", "fine")),))
    broken = Pipeline("broken", "p", (Stage("a", detonate),))
    assert report(clean).exit_code == 0
    assert report(broken).exit_code == 2


# ------------------------------------------------------------ declaration rules
def test_a_pipeline_must_declare_stages():
    with pytest.raises(ShellError):
        Pipeline("empty", "declares nothing", ())


def test_a_pipeline_may_not_repeat_a_stage_name():
    stage = Stage("dup", lambda: ok("dup", "x"))
    with pytest.raises(ShellError):
        Pipeline("repeats", "p", (stage, stage))


# ------------------------------------------------------------------- no acting
def test_the_shell_offers_no_way_to_act():
    """The absence is the contract, and it is the same list the spec names."""
    import shell

    forbidden = ("authorize", "activate", "schedule", "execute", "apply",
                 "run_action", "grant", "approve", "write", "publish")
    exposed = [n for n in forbidden if hasattr(shell, n)]
    assert exposed == [], f"the shell grew an action surface: {exposed}"

    for obj in (Pipeline, Stage, StageResult):
        leaked = [n for n in forbidden if hasattr(obj, n)]
        assert leaked == [], f"{obj.__name__} grew {leaked}"


def test_the_shell_imports_no_authority_module():
    imports = package_imports("shell")
    violations = sorted(
        i for i in imports
        if any(i == f or i.startswith(f + ".") for f in FORBIDDEN_IMPORTS)
    )
    assert violations == [], f"shell imports authority modules: {violations}"


def test_the_shell_opens_no_network_surface():
    """#31 is a separate, unbuilt, founder-gated question. Keep it separate."""
    networking = {"socket", "http", "http.server", "flask", "fastapi",
                  "uvicorn", "requests", "urllib.request", "aiohttp"}
    assert not (package_imports("shell") & networking)


def test_no_shell_module_writes_to_disk():
    """Read-only is asserted against the AST, not promised in a docstring."""
    offenders = []
    for name in sorted(os.listdir(SHELL_DIR)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(SHELL_DIR, name)
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                target = getattr(func, "id", None) or getattr(func, "attr", None)
                if target in ("open", "write_text", "mkdir", "makedirs",
                              "remove", "unlink", "rmtree"):
                    offenders.append(f"{name}:{node.lineno} {target}")
    assert offenders == [], f"shell writes to disk: {offenders}"


# ----------------------------------------------------------- real composition
def test_every_declared_pipeline_collects_without_a_reporter_failure(collected):
    for name, result_report in collected.items():
        failed = [r.name for r in result_report.results
                  if r.outcome is Outcome.FAILED]
        assert failed == [], f"pipeline {name} has failing stages: {failed}"


def test_the_default_pipeline_exists(collected):
    assert DEFAULT_PIPELINE in PIPELINES
    assert collected[DEFAULT_PIPELINE].results


def test_the_shell_reports_the_source_reporters_own_number(collected):
    """Composition, not computation: the count comes from the ladder itself."""
    from blueprint.critical_path import compute

    expected = len(compute().statuses)
    ladder = next(r for r in collected["status"].results if r.name == "ladder")
    assert str(expected) in ladder.headline


def test_the_status_pipeline_reads_more_than_one_reporter():
    assert len({stage.reads for stage in STATUS.stages}) >= 4


def test_unresolved_institutional_state_is_surfaced_not_hidden(collected):
    """The verified-outcome count is 0. The shell must say so, not omit it."""
    outcomes = next(r for r in collected["status"].results if r.name == "outcomes")
    assert outcomes.outcome is Outcome.UNRESOLVED
    assert "0" in outcomes.headline


# ------------------------------------------------------------------ recursion
def test_the_closures_stage_excludes_the_shell_itself():
    """Regression guard: verifying the shell from inside the shell never ends."""
    from closure.integration_registry import build_registry

    assert SELF in build_registry().modules(), (
        "the shell should be registered for five-closure verification"
    )
    closures = next(r for r in report(PIPELINES["status"]).results
                    if r.name == "closures")
    assert "excluded" in closures.headline
    assert SELF in closures.headline
