"""#52 residual: failure-driven repair of a real multi-file source tree under the worker OS envelope.

Pure parts (closure, layout-preserving mutants, junit judgement, tamper manifest, refusals) run on every
host. Executions need bubblewrap user/network namespaces and are skipped without them; on such a host
``repair_source`` itself refuses (fail closed), which is tested here without namespaces.
"""
import hashlib
from pathlib import Path

import pytest

from foundry.systems import repair, versions
from greg import worker_isolation
from tests.unit.test_greg_mcp_planner import needs_namespaces


UTIL = '''"""Integer helpers (a comment that a mutant must not erase)."""


def ceil_div(a, b):
    # pages needed for a items at b per page
    return (a + b - 2) // b
'''
CALC = '''from pkg.util import ceil_div


def pages(items, per_page):
    if items <= 0:
        return 0
    return ceil_div(items, per_page)
'''
TESTS = '''from pkg.calc import pages


def test_exact_multiple():
    assert pages(10, 5) == 2


def test_empty():
    assert pages(0, 5) == 0
'''
FAILING = {"id": "eleven-by-five", "args": [11, 5], "expect": 3}
PASSING = [{"args": [10, 5]}, {"args": [15, 5]}]


def make_tree(base: Path, util: str = UTIL) -> Path:
    for rel, text in {"pkg/__init__.py": "", "pkg/util.py": util, "pkg/calc.py": CALC,
                      "tests/test_calc.py": TESTS, "README.txt": "not imported, not copied\n"}.items():
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text(text)
    return base


def tree_hash(base: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in base.rglob("*")):
        h.update(str(path.relative_to(base)).encode())
        if path.is_file():
            h.update(path.read_bytes())
    return h.hexdigest()


def run_repair(tmp_path, tree, **kw):
    kw = {"failing": FAILING, "passing": PASSING, "existing_tests": ["tests/test_calc.py"], "run_timeout": 60} | kw
    return repair.repair_source(tmp_path / "store", source_root=tree, target="pkg/util.py", func="ceil_div", **kw)


# -- pure parts: no namespaces needed ----------------------------------------------------------------

def test_closure_follows_static_imports_and_package_markers_without_executing(tmp_path):
    tree = make_tree(tmp_path / "t")
    (tree / "pkg" / "util.py").write_text(UTIL + "\nraise SystemExit('executed')\n")   # never imported
    files = repair.source_closure(tree, ["pkg/util.py", "tests/test_calc.py"])
    assert files == ["pkg/__init__.py", "pkg/calc.py", "pkg/util.py", "tests/test_calc.py"]
    with pytest.raises(repair.RepairError, match="relative"):
        repair.source_closure(tree, ["../escape.py"])
    with pytest.raises(repair.RepairError, match="relative"):
        repair.source_closure(tree, [str(tree / "pkg/util.py")])
    (tree / "pkg" / "link.py").symlink_to(tree / "pkg" / "util.py")
    with pytest.raises(repair.RepairError, match="symlink"):
        repair.source_closure(tree, ["pkg/link.py"])


def test_mutants_change_only_the_mutated_span_and_keep_comments():
    mutants = dict(repair.source_mutants(UTIL, [6]))
    assert set(mutants) == {"line 6 col 12-17: swap +/-", "line 6 col 12-21: swap +/-", "line 6 col 12-21: drop '- 2'",
                            "line 6 col 20-21: 2 -> 3", "line 6 col 20-21: 2 -> 1"}
    for label, patched in mutants.items():
        changed = [(a, b) for a, b in zip(UTIL.splitlines(), patched.splitlines()) if a != b]
        assert len(changed) == 1 and changed[0][0].strip().startswith("return"), label
        assert "a comment that a mutant must not erase" in patched and "# pages needed" in patched
    assert mutants["line 6 col 20-21: 2 -> 1"].splitlines()[5] == "    return (a + b - 1) // b"
    assert mutants["line 6 col 12-21: drop '- 2'"].splitlines()[5] == "    return (a + b) // b"
    # precedence is never silently changed: a bare splice that reparses differently gets parentheses
    swapped = dict(repair.source_mutants("x = 2 * (a + b)\n", [1]))["line 1 col 9-14: swap +/-"]
    assert swapped == "x = 2 * (a - b)\n"
    negated = dict(repair.source_mutants("y = 0 ** 2\n", [1]))["line 1 col 4-5: 0 -> -1"]
    assert negated == "y = (-1) ** 2\n" and eval(negated[4:]) == 1             # bare '-1 ** 2' would be -1


def test_suspects_take_whole_bands_and_refuse_an_undiscriminating_tie():
    diag = [{"line": 6, "score": 1.0}, {"line": 2, "score": 0.5}, {"line": 3, "score": 0.5}, {"line": 9, "score": 0.0}]
    assert repair.suspect_lines(diag) == [6, 2, 3]
    assert repair.suspect_lines(diag, limit=2) == [6]                     # a band is never truncated
    with pytest.raises(repair.RepairError, match="equally suspicious"):
        repair.suspect_lines([{"line": n, "score": 0.7} for n in range(9)])


def _junit(body: str) -> bytes:
    return f'<?xml version="1.0"?><testsuites><testsuite>{body}</testsuite></testsuites>'.encode()


def test_only_the_regression_tests_own_assertion_is_failing_before_evidence():
    text, name, line = repair.regression_source("pkg.util", "ceil_div", FAILING)
    compile(text, repair.REGRESSION_FILE, "exec")
    assert text.splitlines()[line - 1].lstrip().startswith("assert observed == EXPECTED")
    own = (f'<testcase classname="test_repair_regression" name="{name}"><failure message="AssertionError: '
           f'{repair.REGRESSION_MARKER}&#10;assert 2 == 3">tb\n\n{repair.REGRESSION_FILE}:{line}: AssertionError'
           f'</failure></testcase>')
    assert repair.fails_by_assertion(repair.parse_junit(_junit(own)), name, line)[0]
    import_error = (f'<testcase classname="" name="test_repair_regression"><error message="collection failure">'
                    f"ImportError while importing test module</error></testcase>")
    other_exception = (f'<testcase classname="t" name="{name}"><failure message="ZeroDivisionError: x">'
                       f"pkg/util.py:6: ZeroDivisionError</failure></testcase>")
    assert_elsewhere = (f'<testcase classname="t" name="{name}"><failure message="AssertionError: '
                        f'{repair.REGRESSION_MARKER}">pkg/util.py:6: AssertionError</failure></testcase>')
    unmarked = (f'<testcase classname="t" name="{name}"><failure message="AssertionError: other">'
                f"{repair.REGRESSION_FILE}:{line}: AssertionError</failure></testcase>")
    passed = f'<testcase classname="t" name="{name}"/>'
    as_error = own.replace("<failure", "<error").replace("</failure>", "</error>")   # setup/teardown error
    for body in (import_error, other_exception, assert_elsewhere, unmarked, passed, as_error,
                 own + passed.replace(name, "x")):
        ok, why = repair.fails_by_assertion(repair.parse_junit(_junit(body)), name, line)
        assert not ok, body
    assert not repair.fails_by_assertion(None, name, line)[0]          # timeout / crash: no report at all
    assert repair.parse_junit(b"<not-xml") is None


def test_tamper_manifest_names_changed_added_and_removed_paths(tmp_path):
    tree = make_tree(tmp_path / "t")
    frozen = repair._manifest(tree)
    assert repair.tampered(frozen, repair._manifest(tree)) == []
    (tree / "tests" / "test_calc.py").write_text("def test_x():\n    pass\n")
    (tree / "pkg" / "new.py").write_text("")
    (tree / "README.txt").unlink()
    assert repair.tampered(frozen, repair._manifest(tree)) == ["README.txt", "pkg/new.py", "tests/test_calc.py"]


def test_no_envelope_means_refusal_before_anything_executes(tmp_path, monkeypatch):
    tree = make_tree(tmp_path / "t")
    before = tree_hash(tree)

    def unavailable(*a, **k):
        raise worker_isolation.WorkerIsolationError("bubblewrap is unavailable on this host")
    monkeypatch.setattr(worker_isolation, "prepare_worker", unavailable)
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("nothing may execute unconfined"))
    with pytest.raises(repair.RepairError, match="isolation envelope"):
        run_repair(tmp_path, tree)
    assert tree_hash(tree) == before and not (tmp_path / "store" / "procedures").exists()


def test_repair_source_validates_its_recipe(tmp_path):
    tree = make_tree(tmp_path / "t")
    with pytest.raises(repair.RepairError, match="existing tests"):
        run_repair(tmp_path, tree, existing_tests=[])
    with pytest.raises(repair.RepairError, match="identifier"):
        repair.repair_source(tmp_path, source_root=tree, target="pkg/util.py", func="x; y", failing=FAILING,
                             passing=[], existing_tests=["tests/test_calc.py"])
    with pytest.raises(repair.RepairError, match="relative"):
        run_repair(tmp_path, tree, existing_tests=["/etc/passwd"])
    with pytest.raises(repair.RepairError, match="reserved"):
        run_repair(tmp_path, tree, existing_tests=[repair.REGRESSION_FILE])
    with pytest.raises(repair.RepairError, match="max_candidates"):
        run_repair(tmp_path, tree, max_candidates=0)


def test_frozen_acceptance_detects_any_change_except_to_the_target(tmp_path):
    tree = make_tree(tmp_path / "t")
    (tree / repair.REGRESSION_FILE).write_text("frozen\n")
    evaluator = {"func": "ceil_div", "failing": dict(FAILING)}
    acceptance = repair.freeze_acceptance(repair._manifest(tree), evaluator, ["tests/test_calc.py"], "pkg/util.py")
    assert repair.acceptance_intact(acceptance, evaluator, tree, "pkg/util.py")
    (tree / "pkg" / "util.py").write_text("candidate\n")                       # the target may change
    assert repair.acceptance_intact(acceptance, evaluator, tree, "pkg/util.py")
    rewritten = {**evaluator, "failing": {**FAILING, "expect": 2}}            # acceptance criteria rewritten
    assert not repair.acceptance_intact(acceptance, rewritten, tree, "pkg/util.py")
    for rel, text in ((repair.REGRESSION_FILE, "rewritten\n"), ("tests/test_calc.py", ""), ("pkg/calc.py", "x = 1\n")):
        original = (tree / rel).read_text()
        (tree / rel).write_text(text)
        assert not repair.acceptance_intact(acceptance, evaluator, tree, "pkg/util.py"), rel
        (tree / rel).write_text(original)
    (tree / "pkg" / "extra.py").write_text("")
    assert not repair.acceptance_intact(acceptance, evaluator, tree, "pkg/util.py")


def test_an_envelope_without_network_isolation_is_refused(tmp_path, monkeypatch):
    tree = make_tree(tmp_path / "t")

    def networked(argv, cwd, **kw):
        return {"argv": argv, "env": {}, "preexec_fn": None,
                "runtime_root": Path(cwd).parent / ".worker-runtime" / "repair-tests",
                "evidence": {"mechanism": "bubblewrap", "network_isolated": False}}
    monkeypatch.setattr(worker_isolation, "prepare_worker", networked)
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("nothing may execute"))
    with pytest.raises(repair.RepairError, match="no-network bubblewrap"):
        run_repair(tmp_path, tree)


def test_repair_source_is_reachable_through_the_foundry_apply_table():
    assert "repair_source" in repair.APPLY_OPS and "repair" in repair.APPLY_OPS


# -- confined executions --------------------------------------------------------------------------

@needs_namespaces
def test_a_multi_file_fault_is_diagnosed_repaired_verified_and_recorded_as_a_proposal(tmp_path):
    tree = make_tree(tmp_path / "t")
    before = tree_hash(tree)
    out = run_repair(tmp_path, tree)
    assert out["status"] == "PROPOSED" and out["symptom"]["observed"] == "2" and out["suspects"][0] == 6
    assert out["regression_before"]["failed_for_intended_reason"]
    assert "assert 2 == 3" in out["regression_before"]["message"]
    outcomes = {c["patch"]: c["outcome"] for c in out["candidates"]}
    assert outcomes["line 6 col 12-21: drop '- 2'"] == "broke_existing"          # passes the regression only
    assert outcomes["line 6 col 20-21: 2 -> 3"] == "regression_still_fails"
    assert out["chosen"] == "line 6 col 20-21: 2 -> 1" and out["survivors"] == ["line 6 col 20-21: 2 -> 1"]
    assert out["after"] == {"test_regression_eleven_by_five": "passed", "test_exact_multiple": "passed",
                            "test_empty": "passed"} and out["after_passed"]
    assert out["isolation"]["network_isolated"] and out["isolation"]["mechanism"] == "bubblewrap"
    assert out["applies_to_source"] is False and out["promotion"].startswith("none")
    assert tree_hash(tree) == before and "(a + b - 2)" in (tree / "pkg" / "util.py").read_text()
    procedure = versions.content(tmp_path / "store" / "procedures", "recovery:pkg.util.ceil_div")
    assert procedure["fix"] == out["chosen"] and procedure["status"] == "PROPOSED"
    assert procedure["acceptance"] == out["acceptance"] and procedure["regression_test"].count("assert") == 1


@needs_namespaces
def test_a_candidate_that_edits_the_regression_test_is_rejected_as_tampering(tmp_path):
    tree = make_tree(tmp_path / "t")
    cheat = ("import pathlib\n"
             f"pathlib.Path({repr(repair.REGRESSION_FILE)}).write_text('def test_regression_eleven_by_five():\\n    pass\\n')\n"
             + UTIL)                                            # still wrong: only rewriting the test could pass it
    edits_existing = "import pathlib\npathlib.Path('tests/test_calc.py').write_text('')\n" + UTIL.replace("- 2", "- 1")
    out = run_repair(tmp_path, tree, proposals=[{"label": "cheat", "source": cheat},
                                                {"label": "right-but-edits-tests", "source": edits_existing}])
    outcomes = {c["patch"]: c["outcome"] for c in out["candidates"]}
    assert outcomes["cheat"] == "tampering" and outcomes["right-but-edits-tests"] == "tampering"
    assert out["chosen"] == "line 6 col 20-21: 2 -> 1"


@needs_namespaces
def test_timeouts_crashes_and_the_candidate_cap_are_recorded(tmp_path):
    tree = make_tree(tmp_path / "t")
    out = run_repair(tmp_path, tree, run_timeout=8, proposals=[
        {"label": "sleeps", "source": "import time\ntime.sleep(60)\n" + UTIL},
        {"label": "exits", "source": "import os\nos._exit(3)\n" + UTIL}])
    outcomes = {c["patch"]: c["outcome"] for c in out["candidates"]}
    assert outcomes["sleeps"] == "timeout" and outcomes["exits"] == "crashed"
    with pytest.raises(repair.RepairEscalation) as escalation:
        run_repair(tmp_path / "capped", tree, max_candidates=1)
    assert escalation.value.evidence["not_evaluated"] > 0 and len(escalation.value.evidence["candidates"]) == 1


@needs_namespaces
def test_a_before_run_that_fails_by_import_error_is_refused(tmp_path):
    util = UTIL.replace("    return (a + b - 2) // b", "    from pkg import missing_helper\n    return (a + b - 2) // b")
    tree = make_tree(tmp_path / "t", util)
    with pytest.raises(repair.RepairError, match="does not fail for the intended reason") as refused:
        run_repair(tmp_path, tree)
    assert "ImportError" in str(refused.value)
    assert not (tmp_path / "store" / "procedures").exists()


@needs_namespaces
def test_a_fault_no_candidate_can_fix_escalates_with_the_diagnosis(tmp_path):
    tree = make_tree(tmp_path / "t", UTIL.replace("(a + b - 2) // b", "(a + b + b) // b"))
    with pytest.raises(repair.RepairEscalation) as escalation:
        run_repair(tmp_path, tree, failing={"id": "x", "args": [11, 5], "expect": 3})
    evidence = escalation.value.evidence
    assert evidence["status"] == "ESCALATED" and evidence["diagnosis"][0]["line"] == 6
    assert evidence["candidates"] and {c["outcome"] for c in evidence["candidates"]} <= {"regression_still_fails",
                                                                                        "broke_existing"}
    assert evidence["acceptance"]["regression_test_sha256"].startswith("sha256:")


@needs_namespaces
def test_a_seeded_fault_in_a_copy_of_a_real_repository_module_is_repaired(tmp_path):
    target = repair.REPO_ROOT / repair.SEEDED_TARGET
    real_before = hashlib.sha256(target.read_bytes()).hexdigest()
    out = repair.exercise_source(tmp_path)
    assert out["status"] == "PROPOSED" and out["repository_unchanged"] and out["source_tree_unchanged"]
    assert out["chosen"].startswith("line 21 ") and "ast.LtE: lambda a, b: a <= b" in out["diff"]
    assert out["after_passed"] and out["after"]["test_dsl_runs_narrow_rules_and_rejects_code"] == "passed"
    assert sum(c["outcome"] == "regression_still_fails" for c in out["candidates"]) >= 1
    assert hashlib.sha256(target.read_bytes()).hexdigest() == real_before
    assert repair.SEEDED_FAULT[0] in target.read_text()


@needs_namespaces
def test_the_chosen_patch_must_reproduce_in_an_independent_verification_run(tmp_path):
    tree = make_tree(tmp_path / "t", UTIL.replace("(a + b - 2) // b", "(a * b) // b"))   # no mutation sites
    flaky = ("import os\nFIRST = os.getcwd().split(os.sep)[-2] == '004'\n\n\n"
             "def ceil_div(a, b):\n    return (a + b - 1) // b if FIRST else 0\n")   # right only in its first run
    with pytest.raises(repair.RepairError, match="did not reproduce on verification"):
        run_repair(tmp_path, tree, proposals=[{"label": "flaky", "source": flaky}])
    assert not (tmp_path / "store" / "procedures").exists()


@needs_namespaces
def test_a_source_tree_that_changes_during_repair_voids_the_proposal(tmp_path, monkeypatch):
    tree = make_tree(tmp_path / "t")
    real = repair._Runner.pytest

    def concurrent_writer(self, nodes, target_source=None):
        (tree / "pkg" / "calc.py").write_text(CALC + "\n# edited elsewhere while the repair ran\n")
        return real(self, nodes, target_source)
    monkeypatch.setattr(repair._Runner, "pytest", concurrent_writer)
    with pytest.raises(repair.RepairError, match="source tree changed"):
        run_repair(tmp_path, tree)
    assert not (tmp_path / "store" / "procedures").exists()
