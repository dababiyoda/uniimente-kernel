"""Each browser method-gate and step-program safeguard must fail a behavioral test when removed.

Mirrors check_pipeline_mutants.py: mutations happen in an isolated copy, never in the checkout; bytecode is never
written and every __pycache__ is purged before each mutant, so a stale compiled module cannot mask a mutation; and
an import error or collection error never counts as a caught safeguard. The browser tests need Playwright and a
Chromium (requirements-computer.txt); without them this script refuses to run instead of reporting survivors.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
COMPUTER = "tests/unit/test_greg_computer.py::"
PIPELINE = "tests/unit/test_greg_pipeline_protected.py::"
MUTANTS = [
    ("a write leaves the browser", "greg/computer.py",
     "if method.upper() in READ_METHODS:\n            return True", "if True:\n            return True",
     COMPUTER + "test_a_click_on_an_unmarked_post_form_is_aborted_and_ends_at_the_authority_boundary"),
    ("a refused write does not stop the session", "greg/computer.py",
     "                if len(attempts) > seen:\n                    trace[-1][\"blocked_methods\"]",
     "                if False:\n                    trace[-1][\"blocked_methods\"]",
     COMPUTER + "test_a_page_that_writes_while_it_loads_is_refused_and_stops_at_the_open"),
    ("a failed step hides the write it attempted", "greg/computer.py",
     "if len(attempts) > seen:           # the step failed", "if False:           # the step failed",
     COMPUTER + "test_a_step_that_fails_after_a_refused_write_is_reported_as_the_write"),
    ("a WebSocket to a signed origin is ungated", "greg/computer.py",
     'if gate("WEBSOCKET", ws.url):', "if True:",
     COMPUTER + "test_every_write_channel_a_step_can_trigger_is_aborted_and_stops_the_session[websocket]"),
    ("a signed exception is ignored", "greg/computer.py",
     "if key in exceptions:", "if False:",
     COMPUTER + "test_a_signed_read_methods_exception_is_honoured_for_that_method_origin_and_path_only"),
    ("an exception covers every path of its method", "greg/computer.py",
     "if key in exceptions:", 'if any(key.split(" ")[0] == e.split(" ")[0] for e in exceptions):',
     COMPUTER + "test_a_signed_read_methods_exception_is_honoured_for_that_method_origin_and_path_only"),
    ("an exception widens the signed origins", "greg/computer.py",
     "        if _origin(url) not in origins:\n            raise CapabilityError(f\"read_methods entry",
     "        if False:\n            raise CapabilityError(f\"read_methods entry",
     COMPUTER + "test_read_methods_never_widen_the_signed_origins_and_name_one_exact_path"),
    ("a whole step program is bindable", "greg/pipeline.py",
     "            if program:\n                raise BindingError", "            if False:\n                raise BindingError",
     PIPELINE + "test_a_step_program_or_a_whole_step_is_never_an_earlier_actions_output"),
    ("a whole step inside the list is bindable", "greg/pipeline.py",
     "return [visit(v, depth+1, protected, program) for v in value]",
     "return [visit(v, depth+1, protected) for v in value]",
     PIPELINE + "test_a_step_program_or_a_whole_step_is_never_an_earlier_actions_output[whole-step]"),
    ("a step's selector is bindable", "greg/pipeline.py",
     '{"op", "selector", "secret", "consequential", "read_methods"}',
     '{"op", "secret", "consequential", "read_methods"}',
     PIPELINE + "test_a_steps_operation_element_credential_and_consequence_marker_stay_signed_literals"),
    ("the method gate's exceptions are bindable", "greg/pipeline.py",
     '{"op", "selector", "secret", "consequential", "read_methods"}',
     '{"op", "selector", "secret", "consequential"}',
     PIPELINE + "test_the_method_gates_signed_exceptions_are_never_an_earlier_actions_output"),
    ("a required browser may still be skipped", "conftest.py",
     'if os.environ.get("GREG_REQUIRE_BROWSER") == "1":\n        _require_browser()',
     'if False:\n        _require_browser()',
     "tests/unit/test_greg_browser_required.py"),
]


def purge(repo: Path):
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def pytest(repo: Path, node: str) -> subprocess.CompletedProcess:
    purge(repo)
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", node],
                          cwd=repo, env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=300)


def main():
    sys.path.insert(0, str(ROOT))
    try:
        import playwright.sync_api  # noqa: F401
        from greg.computer import chromium
        chromium()
    except Exception as exc:          # a survivor list would be meaningless without the browser
        print(f"BROWSER_MISSING: install requirements-computer.txt and a Chromium first ({exc})")
        return 2
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-browser-gate-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        for node in sorted({m[4] for m in MUTANTS}):           # every catching test passes unmutated
            run = pytest(repo, node)
            if run.returncode != 0:
                print("BASELINE_FAILS", node, run.stdout[-600:])
                return 1
        for name, relative, old, new, node in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            run = pytest(repo, node)
            caught = (run.returncode == 1 and f"FAILED {node.split('::')[0]}::" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            path.write_text(original)
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
