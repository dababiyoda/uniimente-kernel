"""Canonical worker acceptance must survive hostile, self-consistent local edits."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
APPRAISAL = "tests/unit/test_greg_workers.py::test_appraisal_binds_acceptance_to_the_original_commission"
FREEZE = "tests/unit/test_greg_worker_containment.py::"
FROZEN = FREEZE + "test_helpers_the_runner_and_shadowing_modules_are_part_of_the_frozen_evaluator"
NAMED = FREEZE + "test_scripts_and_configuration_are_frozen_but_named_code_is_not"
DIVIDEND = "tests/unit/test_greg_worker_acceptance_dividend.py::"
STAFFING_VERIFIER = DIVIDEND + "test_the_staffing_verifier_checks_feasibility_its_own_total_and_the_exhaustive_optimum"
MUTANTS = [
    ("canonical commission binding", "greg/workers.py", "if ctx.journal is not None:", "if False:", APPRAISAL),
    ("worker world reobservation", "greg/appraisal.py", '"worker.appraise", "browser.trace"', '"browser.trace"',
     APPRAISAL),
    ("read-only journal propagation", "greg/appraisal.py", '"artifact.inspect", "worker.appraise", "daleobanks.outcome")',
     '"artifact.inspect", "daleobanks.outcome")', APPRAISAL),
    # The frozen evaluator (#173 I.G6 and the PR #184 port's review 0afd309): each guard of evaluator_findings/appraise.
    ("evaluator: helper directory of a named test", "greg/workers.py",
     'or any(path.startswith(d + "/") for d in helper_dirs)', "", FROZEN),
    ("evaluator: package test's nearest test directory", "greg/workers.py", 'part in TEST_DIRS), "")',
     'part in ()), "")', FREEZE + "test_a_test_inside_packages_freezes_its_test_directory_not_the_code"),
    ("evaluator: named test directory frozen whole", "greg/workers.py", "                helper_dirs.add(path)",
     "                pass", FREEZE + "test_a_named_test_directory_freezes_every_existing_file_in_it"),
    ("evaluator: interpreter hooks and plugin metadata", "greg/workers.py", "allowed(path, EVALUATOR_RUNTIME) or ", "",
     FROZEN),
    ("evaluator: -m and -p modules", "greg/workers.py", "or module(path) or shadows(path)", "or shadows(path)", NAMED),
    ("evaluator: shadowing modules", "greg/workers.py", "or module(path) or shadows(path)", "or module(path)", FROZEN),
    ("evaluator: shadowing packages", "greg/workers.py", 'elif entry + "/__init__.py" in after', "elif False", FROZEN),
    ("evaluator: standard-library shadows", "greg/workers.py", "SHADOWED_MODULES | {m.split",
     "RUNNER_MODULES | {m.split", FROZEN),
    ("evaluator: executed scripts and named configuration", "greg/workers.py",
     'frozen = {p for p in map(norm, targets["scripts"] | targets["config"]) if p}', "frozen = set()", NAMED),
    ("evaluator: shell -c commands", "greg/workers.py", "                            _acceptance_targets(command, out)",
     "                            pass", NAMED),
    ("evaluator: named code stays writable", "greg/workers.py", 'elif not path.endswith(".py"):', "else:", NAMED),
    ("evaluator: named non-Python files frozen", "greg/workers.py", 'elif not path.endswith(".py"):', "elif False:",
     NAMED),
    ("evaluator: shared files never override a rejection", "greg/workers.py",
     'if evaluator["shared"] and verdict == "ACCEPTED":', 'if evaluator["shared"]:',
     FREEZE + "test_a_project_file_change_never_turns_a_rejection_into_a_founder_decision"),
    # Worker-independent acceptance (R1-A, #190): each guard of the discrimination, bound-artifact and re-derivation
    # layers, the one_machine binding that uses them, and the verifier's place among the protected surfaces.
    ("r1a: changed tests must not pass on the base", "greg/workers.py",
     '    if result["passed"]:\n        return [f"the worker\'s tests {tests} pass on the recorded base',
     '    if False:\n        return [f"the worker\'s tests {tests} pass on the recorded base',
     DIVIDEND + "test_a_test_that_passes_on_the_base_proves_nothing_and_is_refused"),
    ("r1a: the discrimination run is wired into appraise", "greg/workers.py",
     'if verdict == "ACCEPTED":          # the one extra run', "if False:          # the one extra run", DIVIDEND
     + "test_a_vacuous_test_no_longer_closes_a_code_change_mission"),
    ("r1a: test-side helpers travel to the base run", "greg/workers.py",
     'set(path.split("/")[:-1]) & set(TEST_DIRS))', "set())", DIVIDEND + "test_test_side_helpers_travel_to_the_base_run"),
    ("r1a: symbolic links are never followed", "greg/workers.py", 'if mode is None or mode == "120000":',
     "if mode is None:", DIVIDEND + "test_a_symbolic_link_is_never_followed_as_a_test_or_an_artifact"),
    ("r1a: bound artifact values compared", "greg/workers.py",
     "elif got is missing or canonical(got) != canonical(want):", "elif got is missing:",
     DIVIDEND + "test_a_delivered_artifact_must_equal_the_value_the_mission_bound_on_its_keys"),
    ("r1a: exactly one bound value in the frozen context", "greg/workers.py", "if context.count(mark) != 1:",
     "if mark not in context:", DIVIDEND + "test_the_bound_value_must_be_one_json_value_in_the_frozen_context"),
    ("r1a: bound and re-derivation findings refuse in appraise", "greg/workers.py", "            if unbound:",
     "            if False:", DIVIDEND + "test_a_coherent_lie_is_refused_by_the_named_verifier_on_the_canonical_path"),
    ("r1a: verifier findings are kept", "greg/workers.py",
     '            findings += [f"verifier {name} on {artifact}: {f}" for f in check(*parsed)]',
     "            check(*parsed)", DIVIDEND + "test_re_derivation_runs_on_gregs_copies_and_names_the_verifier"),
    ("r1a: a bound artifact is on the writable surface", "greg/workers.py",
     '        if not allowed(bound["path"], allowed_paths):', "        if False:",
     DIVIDEND + "test_malformed_acceptance_bindings_are_refused_at_commission"),
    ("r1a: bindings are validated at commission", "greg/workers.py",
     "            acceptance_bindings(acceptance, mode, allowed_paths)", "            pass",
     DIVIDEND + "test_a_work_order_with_malformed_bindings_is_refused_before_any_worker_runs"),
    ("r1a: the verifiers are a protected surface", "greg/workers.py", '    "greg/artifact_verifiers.py",\n', "",
     DIVIDEND + "test_the_artifact_verifiers_are_a_protected_surface"),
    ("r1a: verifier checks the exhaustive optimum", "greg/artifact_verifiers.py", "    if staffed != best:",
     "    if False:", STAFFING_VERIFIER),
    ("r1a: verifier checks capacity", "greg/artifact_verifiers.py",
     '    findings += [f"{w} is assigned {u}, above capacity {capacity[w]}" for w, u in used.items() if u > capacity[w]]',
     "    pass", STAFFING_VERIFIER),
    ("r1a: verifier never assumes optimality it cannot re-derive", "greg/artifact_verifiers.py",
     "    if len(demand) > MAX_EXHAUSTIVE_ORDERS:", "    if False:",
     DIVIDEND + "test_the_staffing_verifier_never_assumes_optimality_it_cannot_re_derive"),
    # The adversarial review of c3a9e26: what discrimination judges (exactly what the acceptance runs), where (a clone
    # laid out as the fresh one), how a base outcome reads, and the declared behaviour-preserving order.
    ("r1a review: discrimination judges what the acceptance runs", "greg/workers.py",
     "    tests = [p for p in acceptance_runs(acceptance, [p for _, p in changed]) if p in written]",
     "    tests = [p for p in written if any(fnmatchcase(posixpath.basename(p), t) for t in TEST_FILES)]",
     DIVIDEND + "test_discrimination_judges_every_changed_file_the_acceptance_runs_whatever_its_name"),
    ("r1a review: a pytest naming no path collects from its root", "greg/workers.py",
     '        targets = targets or {"."}', "        targets = targets",
     DIVIDEND + "test_discrimination_judges_only_changed_files_the_acceptance_runs"),
    ("r1a review: a pytest option's value is never a path", "greg/workers.py",
     "                skip = a in _PYTEST_VALUED", "                skip = False",
     DIVIDEND + "test_discrimination_judges_only_changed_files_the_acceptance_runs"),
    ("r1a review: a changed file the acceptance never runs is not judged", "greg/workers.py",
     '            if name in targets or default and any(t == "." or name.startswith(t + "/") for t in targets):',
     "            if True:", DIVIDEND + "test_discrimination_judges_only_changed_files_the_acceptance_runs"),
    ("r1a review: the base copy stages the test-side files", "greg/workers.py",
     '        _git(dest, "add", "-f", "--", *files)', "        pass",
     DIVIDEND + "test_the_base_copy_is_a_clone_laid_out_as_the_fresh_clone"),
    ("r1a review: an unbuildable base copy is a refusal, never a crash", "greg/workers.py",
     "                except (CapabilityError, OSError, subprocess.SubprocessError) as exc:",
     "                except () as exc:", DIVIDEND + "test_a_base_copy_that_cannot_be_built_is_a_refusal_never_a_crash"),
    ("r1a review: a confinement refusal is never discrimination", "greg/workers.py",
     '    if result["confinement"] == "refused":', "    if False:",
     DIVIDEND + "test_a_confinement_refusal_of_the_base_run_is_never_read_as_discrimination"),
    ("r1a review: any other base failure discriminates", "greg/workers.py",
     '                "about it"], result\n    return [], result\n',
     '                "about it"], result\n    return ["unjudged"] if result["returncode"] not in (1, 2) else [], result\n',
     DIVIDEND + "test_any_base_failure_other_than_a_confinement_refusal_is_a_discriminating_test"),
    ("r1a review: the base run is bounded by the acceptance run", "greg/workers.py",
     '    return min(timeout, 10 + math.ceil(4 * sum(r["seconds"] for r in acceptance_runs)))', "    return timeout",
     DIVIDEND + "test_the_base_run_timeout_scales_with_the_acceptance_run_not_the_order"),
    ("r1a review: a behaviour-preserving order needs its tests to pass on the base", "greg/workers.py",
     '        if result["passed"]:\n            return [], result', "        if True:\n            return [], result",
     DIVIDEND + "test_a_behaviour_preserving_order_requires_its_changed_tests_to_pass_on_the_base"),
    ("r1a review: the discrimination declaration is validated at commission", "greg/workers.py",
     '        if "discrimination" in acceptance and (', "        if False and (",
     DIVIDEND + "test_a_malformed_discrimination_declaration_is_refused_at_commission"),
    ("r1a review: code_change declares a behaviour-preserving order when asked", "greg/templates.py",
     '        acceptance["discrimination"] = "passes_on_base"', "        pass",
     DIVIDEND + "test_the_code_change_template_declares_a_behaviour_preserving_order_only_when_asked"),
    ("r1a: one_machine binds the certified plan", "greg/templates.py",
     '"bound_artifacts": [{"path": "plan/plan.json", "label": "CERTIFIED_PLAN_JSON",\n'
     '                                                            "keys": ["assignment", "staffed"]}],\n', "",
     DIVIDEND + "test_the_one_machine_order_binds_the_certified_plan_and_names_its_verifier"),
]

def main():
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-worker-appraisal-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        for name, relative, old, new, node in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name); invalid += 1; continue
            path.write_text(original.replace(old, new))
            run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", node],
                                 cwd=repo, env={**os.environ, "PYTHONPATH": str(repo)},
                                 capture_output=True, text=True, timeout=90)
            caught = (run.returncode == 1 and f"FAILED {node.split('::')[0]}::" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            path.write_text(original)
    return int(bool(invalid))

if __name__ == "__main__":
    raise SystemExit(main())
