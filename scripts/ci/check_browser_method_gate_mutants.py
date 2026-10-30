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
     "if not socket and method in READ_METHODS and not body:", "if not socket:",
     COMPUTER + "test_a_click_on_an_unmarked_post_form_is_aborted_and_ends_at_the_authority_boundary"),
    ("an OPTIONS body leaves the browser", "greg/computer.py",
     "if not socket and method in READ_METHODS and not body:", "if not socket and method in READ_METHODS:",
     COMPUTER + "test_a_websocket_exception_never_passes_an_http_request_and_options_never_carries_a_body"),
    ("a refused write does not stop its step", "greg/computer.py",
     "                if keys:\n                    trace[-1][\"blocked_methods\"] = keys\n                    raise",
     "                if False:\n                    trace[-1][\"blocked_methods\"] = keys\n                    raise",
     COMPUTER + "test_a_click_on_an_unmarked_post_form_is_aborted_and_ends_at_the_authority_boundary"),
    ("a failed step hides the write it attempted", "greg/computer.py",
     "if keys:                           # the step failed", "if False:                           # the step failed",
     COMPUTER + "test_a_step_that_fails_after_a_refused_write_is_reported_as_the_write"),
    ("a stopping step hides the write it attempted", "greg/computer.py",
     "if keys:                           # the stopping step", "if False:                           # the stopping step",
     COMPUTER + "test_a_write_seen_during_a_step_that_then_fails_its_expectation_still_decides"),
    ("a write at the close is dropped", "greg/computer.py",
     "    closing = attempts[seen:]", "    closing = []",
     COMPUTER + "test_writes_a_page_sends_as_the_session_closes_are_aborted_and_recorded_at_the_close"),
    ("a write at the close leaves another stop's status", "greg/computer.py",
     'if status != "AUTHORITY_BOUNDARY":         # a refused write always decides',
     'if status == "COMPLETED":         # a refused write always decides',
     COMPUTER + "test_a_write_at_the_close_decides_even_after_another_stop"),
    ("page routing instead of browser-target interception", "greg/computer.py",
     '            network.send("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]})\n',
     '            browser.new_context = (lambda make: lambda **kw: (lambda c: (c.route("**/*", lambda r: r.continue_() '
     'if decide({"url": r.request.url, "method": r.request.method, "postData": r.request.post_data}) else r.abort()),'
     ' c)[1])(make(**kw)))(browser.new_context)\n',
     COMPUTER + "test_writes_a_page_sends_as_a_step_navigates_away_are_aborted_and_stop_that_step[goto]"),
    ("a redirect hop is not decided", "greg/computer.py",
     'allowed = decide(event["request"])', 'allowed = bool(event.get("redirectedRequestId")) or decide(event["request"])',
     COMPUTER + "test_a_redirect_after_a_signed_exception_is_gated_as_a_request_of_its_own"),
    ("a request to an unsigned origin leaves", "greg/computer.py",
     "        if _origin(url) not in origins:\n            return outside(url, blocked)",
     "        if False:\n            return outside(url, blocked)",
     COMPUTER + "test_a_redirect_to_an_unsigned_origin_never_arrives[get-302]"),
    ("a WebSocket to a signed origin is ungated", "greg/computer.py",
     'if gate("WEBSOCKET", ws.url, socket=True):', "if True:",
     COMPUTER + "test_every_write_channel_a_step_can_trigger_is_aborted_and_stops_the_session[websocket]"),
    ("a signed exception is ignored", "greg/computer.py",
     'if key in exceptions and socket == (method == "WEBSOCKET"):', "if False:",
     COMPUTER + "test_a_signed_read_methods_exception_is_honoured_for_that_method_origin_and_path_only"),
    ("an exception covers every path of its method", "greg/computer.py",
     'if key in exceptions and socket == (method == "WEBSOCKET"):',
     'if any(key.split(" ")[0] == e.split(" ")[0] for e in exceptions):',
     COMPUTER + "test_a_signed_read_methods_exception_is_honoured_for_that_method_origin_and_path_only"),
    ("a WEBSOCKET exception passes an HTTP request", "greg/computer.py",
     'if key in exceptions and socket == (method == "WEBSOCKET"):', "if key in exceptions:",
     COMPUTER + "test_a_websocket_exception_never_passes_an_http_request_and_options_never_carries_a_body"),
    ("an exception widens the signed origins", "greg/computer.py",
     "        if _origin(url) not in origins:\n            raise CapabilityError(f\"read_methods entry",
     "        if False:\n            raise CapabilityError(f\"read_methods entry",
     COMPUTER + "test_read_methods_never_widen_the_signed_origins_and_name_one_exact_path"),
    ("a malformed URL crashes instead of refusing", "greg/computer.py",
     "    except ValueError as exc:\n        raise CapabilityError(f\"{what}",
     "    except KeyError as exc:\n        raise CapabilityError(f\"{what}",
     COMPUTER + "test_a_malformed_read_methods_entry_is_refused_as_a_capability_error"),
    ("the page prelude is not installed", "greg/computer.py",
     "            context.add_init_script(PAGE_PRELUDE)\n", "",
     COMPUTER + "test_pages_get_no_worker_and_no_channel_that_request_interception_cannot_see"),
    ("WebSocketStream stays on in the engine", "greg/computer.py",
     'ENGINE_OFF = "--disable-blink-features=WebSocketStream,SharedWorker"',
     'ENGINE_OFF = "--disable-blink-features=SharedWorker"',
     COMPUTER + "test_each_layer_that_removes_those_channels_holds_on_its_own[engine-flag-alone]"),
    ("the prelude keeps dedicated workers", "greg/computer.py",
     "for (const name of ['Worker', ", "for (const name of [",
     COMPUTER + "test_each_layer_that_removes_those_channels_holds_on_its_own[page-prelude-alone]"),
    ("a capability's whole params are bindable", "greg/pipeline.py",
     "            if depth == 0:\n                raise BindingError", "            if False:\n                raise BindingError",
     PIPELINE + "test_a_capabilitys_whole_params_are_never_an_earlier_actions_output"),
    ("inspection returns its wrapper instead of the value", "greg/pipeline.py",
     '        value = wrapped["value"]', "        value = wrapped",
     PIPELINE + "test_inspection_still_returns_the_producers_value_through_its_wrapped_reference"),
    ("a whole step program is bindable", "greg/pipeline.py",
     "            if program and kind in PROGRAM_TYPES:\n                raise BindingError",
     "            if False:\n                raise BindingError",
     PIPELINE + "test_a_step_program_or_a_whole_step_is_never_an_earlier_actions_output"),
    ("a scalar step count is refused as a program", "greg/pipeline.py",
     "            if program and kind in PROGRAM_TYPES:\n                raise BindingError",
     "            if program:\n                raise BindingError",
     PIPELINE + "test_a_scalar_under_a_steps_key_stays_bindable_data"),
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
