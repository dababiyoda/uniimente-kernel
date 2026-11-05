"""The appraiser's pinned re-read of a compiled cognition receipt must survive hostile, self-consistent local edits.

The join of unit B onto #243's one pin channel (``greg.cognition.replay``): the receipt's pin is bound in a context
variable around the ordinary adapter call and read once by ``compiler.run``. Each mutant names the test that must
catch it. A named test that fails on the unmutated copy is INVALID (it proves nothing about the mutant); a mutant is
CAUGHT only when its named test then fails.
"""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
TESTS = "tests/unit/test_greg_appraisal_pinned_reread.py::"
FIRED = TESTS + "test_a_failure_closure_stays_confirmed_after_the_cell_preference_fires"
SERVED = TESTS + "test_a_success_the_preferred_alternative_served_is_verified_by_the_bodys_own_appraiser"
SHADOW = TESTS + "test_the_appraiser_runs_no_shadow_trial_when_one_is_due_in_its_view"
CHANGED = TESTS + "test_a_failure_whose_method_changed_since_the_receipt_is_never_confirmed"
ROUTED = TESTS + "test_routing_changed_since_the_receipt_never_changes_which_method_a_pinned_compile_runs"
INPUTS = TESTS + "test_a_re_read_of_other_inputs_than_the_receipt_answered_is_refused"
EARLY = TESTS + "test_a_pinned_compile_at_another_registered_version_raises_before_any_solver_runs"
POST = TESTS + "test_a_re_read_that_did_not_run_the_pinned_method_at_its_version_is_not_a_replay"
LOST = TESTS + "test_a_re_read_that_lost_its_pin_is_refused_by_the_appraisers_postcondition"
TARGET = TESTS + "test_a_pinned_re_read_requires_the_signed_cognition_target"
FORMED = TESTS + "test_a_formed_mechanism_compile_closure_is_still_re_read_and_verified"
DETACHED = TESTS + "test_a_success_the_preferred_alternative_served_is_not_re_read_once_it_is_detached"
NATIVE = TESTS + "test_a_success_the_alternative_answered_on_its_native_route_is_verified"
NATIVE_PIN = TESTS + "test_a_pinned_compile_answers_on_a_native_route_receipt"
MIXED = TESTS + "test_a_request_carrying_both_input_shapes_is_re_read_on_the_route_its_receipt_took"
ROUTE = TESTS + "test_a_receipt_whose_route_disagrees_with_its_recorded_preference_is_refused"
NO_METHOD = TESTS + "test_a_compile_receipt_naming_no_method_is_refused_and_never_re_read_on_other_inputs"
UNMEASURED = TESTS + "test_a_refused_pinned_re_read_reads_as_unmeasured_not_as_a_changed_world"
NO_NATIVE = TESTS + "test_a_preference_route_pin_is_never_answered_on_the_native_row_once_the_adapter_row_cannot_run"
NO_NATIVE_BODY = (TESTS + "test_a_preference_route_failure_on_both_shapes_is_not_confirmed_once_the_adapter_row_"
                  "cannot_run")
FORGED = TESTS + "test_a_receipt_claiming_the_preference_route_without_its_record_is_refused"
ABSTAINED = TESTS + "test_a_failure_closure_whose_pinned_re_read_abstains_is_not_confirmed"
NO_ANSWER = TESTS + "test_a_pinned_re_read_that_ran_and_gave_no_answer_measured_nothing"
OFF_ROUTE = TESTS + "test_a_receipt_recording_a_fired_preference_for_its_method_off_the_preference_route_is_refused"
COMPOSED = TESTS + "test_a_composition_closure_is_re_read_on_its_recipe_and_verified"
HUMAN = TESTS + "test_the_human_route_is_re_read_on_that_route_alone"
VERSIONLESS = TESTS + "test_a_versionless_pin_is_never_honoured_on_an_operation_route"
BOUND = TESTS + "test_a_bound_pin_is_honoured_only_on_a_compile_of_the_receipts_inputs"
CHANNEL = TESTS + "test_the_pin_has_one_channel_and_nothing_in_the_compiler_rebinds_it"
CHANGED_PIN = TESTS + "test_a_pinned_compile_of_a_changed_method_raises_before_any_solver_runs"
SETTLED = TESTS + "test_a_pinned_compile_reads_no_settled_outcomes"
# #243's own tests, on the kept channel
OWN = "tests/unit/test_greg_receipt_pinned_appraisal.py::"
OWN_STAYS = OWN + "test_a_discordant_failure_stays_verified_unmet_after_routing_moves"
OWN_CLOSED = OWN + "test_an_unavailable_pinned_method_fails_closed"
# three closures #243 refused, in the suites the review matrix (#243 issuecomment-6531360617) ran
GENESIS = ("tests/unit/test_greg_cognition_genesis.py::"
           "test_an_assignment_deficit_forms_scipy_on_a_card_and_asks_the_founder_exactly_once")
BUILT = ("tests/unit/test_greg_pending_construction_realization.py::"
         "test_real_construction_is_listed_reported_by_signed_cli_and_no_longer_pending")

APPRAISAL, REPLAY, COMPILER, CORTEX = ("greg/appraisal.py", "greg/cognition/replay.py", "greg/cognition/compiler.py",
                                       "greg/cognition/cortex.py")
BIND = "if pinned is not None:\n                        replay_token = bind_cognition_replay(pinned)"
POSTCONDITION = "if pinned is not None and not cognition_replay_matches(output, pinned):"
ABSTAIN_SITE = "if pinned is not None and cognition_replay_unmeasured(output):"
DIGEST = 'if output.get("inputs_digest") != digest(bound_params):'
FIRED_FOR = ('fired_for_method = (isinstance(preference, dict) and preference.get("fired") is True\n'
             '                        and preference.get("prefer") == method)')
LEVEL = "if level == PREFERENCE_ROUTE and not fired_for_method:"
OFF = "if method == ALTERNATIVE and level != PREFERENCE_ROUTE and fired_for_method:"
VERSIONED = 'return {"method": method, "version": version, "route": route, "inputs_digest": inputs}'
SELECTION = '    route: dict = {"kind": "compiler", "selection": selection}\n'
SAME = "return pin_from_output(output) == pin"
LEARNED = 'or replayed.get("learned_routing") is not False'
INNER = 'return None if state in ("NONE", "REFUTED") else str(inner.get("reason_code") or state)'
OWN_STATE = 'return None if output.get("state") == "REFUTED" else str(output.get("state") or "no answer")'
READ = "    pin = replay_pin()\n"
ON_INPUTS = ('if pin is not None and (not isinstance(pin, dict) or pin.get("inputs_digest") != '
             'receipt["inputs_digest"]):')
HUMAN_CHECK = 'if pin is not None and (pin.get("method"), _pinned_selection(pin), pin.get("version")) != ('
FORMED_ROUTE = 'if _pinned_selection(pin) == "formed_by_capability_genesis":'
PREFERENCE = 'if route["selection"] == "preferred_by_condition_evidence":\n        if method != condition_competence'
OFFERABLE = "if not (condition_competence._attached(registry) and condition_competence._admitted()):"
NOTHING = "return None          # the receipt's route cannot run here: never the native row in its place"
NAMED = 'matches = [r for r in rows if r.get("method") == method and not r.get("rejected")]'
KINDS = ('if row.get("kind") not in (("composition", "constructed") if version is None else '
         '("operation", "problem")):')
REGISTERED = "if manifest is None or str(manifest.version) != version:"
PACKAGE = 'and isinstance(pin.get("version"), str) and str(m.provenance.get("version")) == pin["version"]]'
HOOK = "    if pin is None:\n        runnable = condition_competence.compile_hook("
LEARNING = "    if pin is None:\n        # learned routing:"
SIGNED = ('def solve(params, ctx):\n    from greg.capabilities import CapabilityError\n'
          '    if not ctx.manifest.capability_id.startswith("cognition.") or not ctx.target.startswith("cognition:"):')
MUTANTS = [
    # the appraiser: one channel, bound around the ordinary adapter call
    ("appraiser binds no pin (failure closure)", APPRAISAL, BIND, "if False:\n                        pass", FIRED),
    ("appraiser binds no pin (success closure)", APPRAISAL, BIND, "if False:\n                        pass", SERVED),
    ("appraiser binds no pin (#243's own test)", APPRAISAL, BIND, "if False:\n                        pass",
     OWN_STAYS),
    ("appraiser's replay postcondition removed", APPRAISAL, POSTCONDITION, "if False:", LOST),
    ("abstaining pinned re-read judged (solver raises)", APPRAISAL, ABSTAIN_SITE, "if False:",
     ABSTAINED + "[value_error]"),
    ("abstaining pinned re-read judged (solver times out)", APPRAISAL, ABSTAIN_SITE, "if False:",
     ABSTAINED + "[timeout]"),
    ("a refused re-read reported as a changed world", APPRAISAL,
     '"the world could not be re-measured" if now_ok is None else "world no longer matches"',
     '"world no longer matches"', UNMEASURED),
    # the receipt's own records (replay.receipt_pin)
    ("inputs digest unchecked", REPLAY, DIGEST, "if False:", INPUTS),
    ("digest checked only when the receipt names a method", REPLAY, DIGEST,
     'if output.get("method_or_composition_selected") and output.get("inputs_digest") != digest(bound_params):',
     NO_METHOD),
    ("route accepted from an unfired preference", REPLAY, FIRED_FOR,
     'fired_for_method = (isinstance(preference, dict)\n                        and preference.get("prefer") == method)',
     ROUTE + "[unfired]"),
    ("route accepted from a preference for another method", REPLAY, FIRED_FOR,
     'fired_for_method = (isinstance(preference, dict) and preference.get("fired") is True\n'
     '                        )', ROUTE + "[other]"),
    ("preference route accepted without its record (constructed)", REPLAY, LEVEL,
     "if level == PREFERENCE_ROUTE and isinstance(preference, dict) and not fired_for_method:", ROUTE + "[absent]"),
    ("preference route accepted without its record (forged receipt)", REPLAY, LEVEL,
     "if level == PREFERENCE_ROUTE and isinstance(preference, dict) and not fired_for_method:", FORGED),
    ("fired preference for the method accepted off the preference route", REPLAY, OFF, "if False:", OFF_ROUTE),
    # the pin's shape (replay.pin_from_output) and the postcondition (replay.matches)
    ("receipt's version never pinned", REPLAY, VERSIONED,
     'return {"method": method, "version": None, "route": route, "inputs_digest": inputs}', FIRED),
    ("receipt's route never passed on", REPLAY, SELECTION,
     '    route: dict = {"kind": "compiler", "selection": "admission_status"}\n', SERVED),
    ("postcondition accepts any re-read", REPLAY, SAME, "return True", POST + "[ran0-deficit]"),
    ("postcondition accepts another version", REPLAY, SAME,
     'return {**(pin_from_output(output) or {}), "version": pin["version"]} == pin', POST + "[ran1-version]"),
    ("postcondition accepts learned routing", REPLAY, LEARNED, "", POST + "[ran3-same]"),
    ("a pinned method that abstained judged", REPLAY, INNER, "return None", NO_ANSWER + "[operation-abstained]"),
    ("a refuting pinned re-read refused as an abstention", REPLAY, INNER,
     'return None if state in ("NONE",) else str(inner.get("reason_code") or state)',
     NO_ANSWER + "[operation-refuted]"),
    ("composition re-read with no answer judged", REPLAY, OWN_STATE, "return None",
     NO_ANSWER + "[composition-abstained]"),
    ("composition refutation refused as an abstention", REPLAY, OWN_STATE,
     'return str(output.get("state") or "no answer")', NO_ANSWER + "[composition-refuted]"),
    # the compiler: read once, never rebound, honoured only on the receipt's inputs and route
    ("the pin is reset to nothing (failure closure)", COMPILER, READ, "    pin = None\n", FIRED),
    ("the pin is reset to nothing (structure)", COMPILER, READ, "    pin = replay_pin()\n    pin = pin\n", CHANNEL),
    ("a pin honoured on other inputs", COMPILER, ON_INPUTS, "if pin is not None and not isinstance(pin, dict):",
     BOUND),
    ("human route answers any pin", COMPILER, HUMAN_CHECK, HUMAN_CHECK.replace("if pin", "if False and pin"),
     HUMAN),
    ("formed route looked up in the catalog (#243's refusal)", COMPILER, FORMED_ROUTE, "if False:", FORMED),
    ("formed mechanism matched by manifest, not package, version", COMPILER, PACKAGE,
     'and isinstance(pin.get("version"), str) and str(m.version) == pin["version"]]', FORMED),
    ("formed mechanism at any package version", COMPILER, PACKAGE, "]", FORMED),
    ("pinned re-read never offers the adapter row", COMPILER, PREFERENCE,
     PREFERENCE.replace('if route["selection"]', 'if False and route["selection"]'), SERVED),
    ("pinned re-read runs an unadmitted alternative", COMPILER, OFFERABLE,
     "if not condition_competence._attached(registry):", SERVED),
    # "pinned re-read runs a detached alternative" (OFFERABLE -> "if not condition_competence._admitted():") is not
    # listed: it is equivalent, since _pinned_row's _usable check refuses a detached alternative's operation row too
    ("adapter row offered whatever route the receipt took (body)", COMPILER, PREFERENCE,
     PREFERENCE.replace('if route["selection"] == "preferred_by_condition_evidence":',
                        'if route["selection"] == "preferred_by_condition_evidence" or method == '
                        'condition_competence.ALTERNATIVE:'), NATIVE),
    ("adapter row offered whatever route the receipt took (compile)", COMPILER, PREFERENCE,
     PREFERENCE.replace('if route["selection"] == "preferred_by_condition_evidence":',
                        'if route["selection"] == "preferred_by_condition_evidence" or method == '
                        'condition_competence.ALTERNATIVE:'), NATIVE_PIN),
    ("adapter row offered whatever route the receipt took (both shapes)", COMPILER, PREFERENCE,
     PREFERENCE.replace('if route["selection"] == "preferred_by_condition_evidence":',
                        'if route["selection"] == "preferred_by_condition_evidence" or method == '
                        'condition_competence.ALTERNATIVE:'), MIXED),
    ("preference-route pin falls back to the native row (compile)", COMPILER, NOTHING,
     'return next((dict(r) for r in rows if r.get("method") == method and not r.get("rejected")), None)',
     NO_NATIVE),
    ("preference-route pin falls back to the native row (body)", COMPILER, NOTHING,
     'return next((dict(r) for r in rows if r.get("method") == method and not r.get("rejected")), None)',
     NO_NATIVE_BODY),
    ("pinned compile not restricted to the named method", COMPILER, NAMED,
     'matches = [min((r for r in rows if not r.get("rejected")), key=lambda r: _rank(r, [], {}))]', ROUTED),
    ("versionless pin honoured on an operation route", COMPILER, KINDS,
     'if version is not None and row.get("kind") not in ("operation", "problem"):', VERSIONLESS),
    ("composition pin refused (#243's refusal)", COMPILER, KINDS,
     'if row.get("kind") not in (() if version is None else ("operation", "problem")):', COMPOSED),
    ("construction pin refused (#243's refusal, real construction suite)", COMPILER, KINDS,
     'if row.get("kind") not in (("composition",) if version is None else ("operation", "problem")):', BUILT),
    ("formed pin refused (#243's refusal, Genesis suite)", COMPILER, FORMED_ROUTE, "if False:", GENESIS),
    ("registered version not compared", COMPILER, REGISTERED, "if manifest is None:", EARLY),
    ("registered version not compared (compile)", COMPILER, REGISTERED, "if manifest is None:",
     CHANGED_PIN + "[version]"),
    # "detached method re-read" ("return row if usable else None" -> "return row") is not listed: it is equivalent,
    # since run() re-checks every eligible row's _usable and raises under a pin when none can run
    ("condition hook consulted under a pin", COMPILER, HOOK,
     "    if True:\n        runnable = condition_competence.compile_hook(", SHADOW),
    ("learned routing consulted under a pin", COMPILER, LEARNING, "    if True:\n        # learned routing:", SETTLED),
    ("the adapter ignores the signed target", CORTEX, SIGNED, SIGNED.split("    if not")[0] + "    if False:", TARGET),
]


def _run(repo, node):
    # every run compiles the source as it is now, so a stale .pyc cannot hide a mutant: this process tree writes no
    # bytecode, and isolated (-I) solver workers, which ignore that setting, have their caches removed first
    for cache in list(repo.rglob("__pycache__")):
        shutil.rmtree(cache, ignore_errors=True)
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", node],
                              cwd=repo, env=env, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return None                  # a hang proves nothing: never a valid named test, never a caught mutant


def main():
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-pinned-reread-mutants-") as temp:
        repo = Path(temp) / "repo"
        # a full copy (about 100 MB): a test that rewrote a file in place could never reach the source tree
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        valid = {}
        for node in dict.fromkeys(m[4] for m in MUTANTS):
            run = _run(repo, node)
            valid[node] = run is not None and run.returncode == 0
            if not valid[node]:
                print("INVALID (fails unmutated)" if run else "INVALID (timed out unmutated)", node)
        for name, relative, old, new, node in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name); invalid += 1; continue
            if not valid[node]:
                print("INVALID", name); invalid += 1; continue
            path.write_text(original.replace(old, new))
            try:
                run = _run(repo, node)
            finally:
                path.write_text(original)
            # a module fixture that asserts the body's own appraisal (``failed``) errors the test instead: that is
            # the named test failing too, never a collection error
            caught = (run is not None and run.returncode == 1 and (f"FAILED {node}" in run.stdout
                                                                   or f"ERROR {node}" in run.stdout)
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "TIMED OUT" if run is None else "SURVIVED", name, "--",
                  node.split("::")[-1])
            invalid += not caught
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
