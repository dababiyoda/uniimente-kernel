"""Canonical worker acceptance must survive hostile, self-consistent local edits."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
APPRAISAL = "tests/unit/test_greg_workers.py::test_appraisal_binds_acceptance_to_the_original_commission"
FREEZE = "tests/unit/test_greg_worker_containment.py::"
FROZEN = FREEZE + "test_helpers_the_runner_and_shadowing_modules_are_part_of_the_frozen_evaluator"
NAMED = FREEZE + "test_scripts_and_configuration_are_frozen_but_named_code_is_not"
TIER = "tests/unit/test_greg_confinement_tier.py::"
OVERCLAIM = TIER + "test_the_appraiser_refuses_a_receipt_that_claims_more_than_its_evidence"
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
    # Graduated confinement (R2-A): each claim check of worker.appraise and the one tier derivation.
    ("tier: a stronger claimed tier", "greg/workers.py", 'TIER_RANK[tier] > TIER_RANK[derived["tier"]]', "False",
     OVERCLAIM),
    ("tier: a different Landlock ABI", "greg/workers.py",
     'claim["landlock_abi"] != derived["landlock_abi"]', "False", OVERCLAIM),
    ("tier: claimed signal scoping", "greg/workers.py",
     'if claim.get("signals_scoped") is True and not derived["signals_scoped"]:', "if False:", OVERCLAIM),
    ("tier: evidence scoping beyond its ABI", "greg/workers.py",
     'isolation.signals_record(isolation.SCOPE_SIGNAL) and not derived["signals_scoped"]:', "False:", OVERCLAIM),
    ("tier: an unknown tier", "greg/workers.py", "tier not in CONFINEMENT_TIERS", "False", OVERCLAIM),
    ("tier: implied by the confinement record", "greg/workers.py",
     '{"tier": implied, **record}', "record", OVERCLAIM),
    ("tier: acceptance records checked", "greg/workers.py",
     'findings += _claim_findings(f"acceptance record {index}", test, test_evidence)', "pass", OVERCLAIM),
    ("tier: overclaims reject", "greg/workers.py", "    if overclaims:\n        findings += overclaims\n"
     "        verdict = \"REJECTED\"", "    if overclaims:\n        findings += overclaims", OVERCLAIM),
    ("tier: required body, worker", "greg/workers.py",
     'if required and derived["tier"] in ("landlock", "supervised_unconfined"):', "if False:",
     TIER + "test_a_required_body_refuses_a_receipt_below_the_envelope"),
    ("tier: required body, acceptance", "greg/workers.py",
     'if required and tests[-1]["tier"] in ("landlock", "supervised_unconfined"):', "if False:",
     TIER + "test_a_required_body_refuses_a_receipt_below_the_envelope"),
    ("tier: an old receipt is not refused for absence", "greg/workers.py",
     "if tier is not None and tier not in CONFINEMENT_TIERS", "if tier not in CONFINEMENT_TIERS",
     TIER + "test_an_old_receipt_without_tiers_still_appraises_from_its_evidence"),
    ("tier: scoping needs ABI >= 6", "greg/workers.py", "and bool(isolation.signal_scope(abi)))", ")",
     TIER + "test_the_tier_is_derived_from_the_evidence_alone"),
    ("tier: never a provider's claim", "greg/workers.py", "    tier = confinement_tier(report.isolation if isinstance(",
     "    tier = confinement_tier(report.isolation if True or isinstance(",
     TIER + "test_a_provider_greg_did_not_launch_never_records_the_tier_it_claims"),
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
