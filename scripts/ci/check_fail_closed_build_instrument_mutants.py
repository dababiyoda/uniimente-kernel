"""Each safeguard of the fail-closed build instrument must fail a behavioural test when it is removed.

The safeguards (docs/evidence/fail-closed-build-instrument-2026-10-30/README.md):

- GREG_REQUIRE_SUPERVISOR=1 turns a missing supervisord into a failure of the supervised rehearsals instead of a
  skip (tests/supervisor_requirement.py, used by both rehearsal modules), and the build-frontier workflow sets it and
  runs the path-predicate gate and this one on every pull request;
- a body made by `greg rehearse` is marked in body.json before any key is enrolled (greg/rehearsal.py), and
  metrics.founder_tier keeps every mission of a marked body below the founder tier (greg/metrics.py). Over-reach is
  guarded too: an unmarked body, or a ledger with no body.json beside it, is not read as a rehearsal;
- the same holds for a body whose ledger carries a MISSION that opens with the [REHEARSAL] label every `greg rehearse`
  body signs, so a rehearsal body made before the mark existed, or whose body.json was edited, stays below the tier
  (review finding MWA-ATK-1); only a label that opens the expression counts, and the label never changes;
- every founder surface says a rehearsal body is one: `greg status` carries a command for another body as `how`, so
  the home banner never renders an empty command, and Mission Control's Proof row names the rehearsal body whether or
  not its key attested (review findings MWA-ATK-2 and MWA-FID-1).

Every mutant runs in a scratch copy of the repository, never the checkout, under ``python -B`` with
PYTHONDONTWRITEBYTECODE=1, after every ``__pycache__`` in the copy is purged, so no bytecode of the checkout or of an
earlier mutant can run in place of the mutated source. The named tests must pass unmutated first. A mutant whose
text no longer occurs exactly once is STALE. A mutant counts as caught only when one of its named tests FAILS, with
no collection error and no syntax or import error in the output.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TIER = "tests/unit/test_greg_rehearsal_founder_tier.py::"
REHEARSAL = TIER + "test_a_rehearsal_body_never_reaches_the_founder_tier_and_achieved_does_not_move"
READER = TIER + "test_the_mark_is_read_beside_the_ledger_and_an_unreadable_config_never_grants_the_tier"
EARLIER = TIER + "test_a_rehearsal_body_made_before_the_mark_is_known_by_the_label_in_its_ledger"
LABEL = TIER + "test_the_label_marks_the_whole_body_only_when_it_opens_a_missions_expression"
SURFACES = TIER + "test_every_founder_surface_says_a_rehearsal_body_is_one_and_never_shows_an_empty_command"
SUPERVISOR = "tests/unit/test_require_supervisor.py::"
REQUIRED = SUPERVISOR + "test_required_and_missing_every_supervised_rehearsal_fails_with_the_message"
UNSET = SUPERVISOR + "test_unset_a_missing_supervisord_still_skips"
HELPER = SUPERVISOR + "test_the_helper_fails_only_when_required_and_returns_a_present_supervisord"
WORKFLOW = "tests/unit/test_build_frontier_workflow.py::"
GATES = WORKFLOW + "test_every_pull_request_installs_supervisord_and_runs_both_gates"
REQUIRED_IN_CI = WORKFLOW + "test_the_supervised_rehearsals_run_with_supervisord_required"
ORDER = ('    mark_body(home)                                # before any key exists: no command of this body predates'
         ' the mark\n')
ENROL = ('    keyfile = work / f"{REHEARSAL}-throwaway-founder-key.pem"\n'
         '    public = generate_founder_key(keyfile, None)\n'
         '    key = load_founder_key(keyfile, None)\n'
         '    with Body(home) as body:\n'
         '        body.enroll_founder(public)\n')

# (name, file, old, new, tests that must catch it)
MUTANTS = [
    ("a rehearsal body reaches the founder tier", "greg/metrics.py",
     '        if rehearsal:\n            why = REHEARSAL_BODY\n        elif command.get("kind") != "MISSION":\n',
     '        if command.get("kind") != "MISSION":\n', [REHEARSAL]),
    ("the mark in body.json is never read", "greg/metrics.py",
     "    return bool(config.get(REHEARSAL_MARK)) if isinstance(config, dict) else True\n",
     "    return False if isinstance(config, dict) else True\n", [READER, REHEARSAL]),
    ("an unreadable body.json reads as unmarked", "greg/metrics.py",
     "    except (OSError, ValueError):\n        return True\n",
     "    except (OSError, ValueError):\n        return False\n", [READER]),
    ("a body.json that is not an object reads as unmarked", "greg/metrics.py",
     " if isinstance(config, dict) else True\n", " if isinstance(config, dict) else False\n", [READER]),
    ("a ledger with no body.json beside it reads as a rehearsal", "greg/metrics.py",
     "    except FileNotFoundError:\n        return False\n",
     "    except FileNotFoundError:\n        return True\n", [READER]),
    ("a ledger kept in memory reads as a rehearsal", "greg/metrics.py",
     "    if not location:\n        return False\n", "    if not location:\n        return True\n", [READER]),
    ("the status surface advises an attestation on a rehearsal body", "greg/metrics.py",
     '    advice = ({"rehearsal_body": True, "consequence": REHEARSAL_BODY, "how": REHEARSAL_HOW} if rehearsal else\n'
     '              {} if ok else\n',
     "    advice = ({} if ok else\n", [REHEARSAL]),
    ("the status surface gives a rehearsal body no command, so the banner shows an empty one", "greg/metrics.py",
     '{"rehearsal_body": True, "consequence": REHEARSAL_BODY, "how": REHEARSAL_HOW}',
     '{"rehearsal_body": True, "consequence": REHEARSAL_BODY}', [SURFACES]),
    ("Mission Control's Proof row treats a rehearsal body like any other", "greg/mission_control.py",
     '    if tier.get("rehearsal_body"):', "    if False:", [SURFACES]),
    ("the ledger's rehearsal label is never read", "greg/metrics.py",
     "    return any(rehearsal_mission(event.payload) for event in events)\n", "    return False\n",
     [EARLIER, LABEL]),
    ("rehearsal_body ignores the body.json mark", "greg/metrics.py",
     "    if rehearsal_marked(journal):\n        return True\n", "", [SURFACES]),
    ("founder_tier reads only the body.json mark", "greg/metrics.py",
     "    rehearsal = rehearsal_body(journal, accepted)\n    seq = ",
     "    rehearsal = rehearsal_marked(journal)\n    seq = ", [EARLIER, LABEL]),
    ("the status surface reads only the body.json mark", "greg/metrics.py",
     "    rehearsal = rehearsal_body(journal, accepted)\n    advice = ",
     "    rehearsal = rehearsal_marked(journal)\n    advice = ", [EARLIER]),
    ("the label anywhere in an expression marks the body", "greg/metrics.py",
     "expression.startswith(REHEARSAL_LABEL)", "REHEARSAL_LABEL in expression", [LABEL]),
    ("the label changes, so bodies made earlier lose it", "greg/rehearsal.py",
     'LABEL = f"[{REHEARSAL}]"\n', 'LABEL = f"[{REHEARSAL}-RUN]"\n', [LABEL]),
    ("greg rehearse signs its First Mission without the label", "greg/rehearsal.py",
     'founder_expression=f"{LABEL} Run the Founder\'s First Mission with a throwaway key.")',
     'founder_expression="Run the Founder\'s First Mission with a throwaway key.")', [EARLIER]),
    ("greg rehearse does not mark its body", "greg/rehearsal.py", ORDER, "", [REHEARSAL]),
    ("the mark is written after the key is enrolled", "greg/rehearsal.py", ORDER + ENROL,
     ENROL + "    mark_body(home)\n", [REHEARSAL]),
    ("body.json is rewritten readable by others", "greg/rehearsal.py",
     "    _private_write(temporary, json.dumps(config, indent=2).encode())\n",
     "    temporary.write_text(json.dumps(config, indent=2))\n", [REHEARSAL]),
    ("GREG_REQUIRE_SUPERVISOR=1 still skips", "tests/supervisor_requirement.py",
     '        if os.environ.get(REQUIRE) == "1":\n            pytest.fail(MISSING, pytrace=False)\n', "",
     [HELPER, REQUIRED]),
    ("a missing supervisord fails even when it is not required", "tests/supervisor_requirement.py",
     '        if os.environ.get(REQUIRE) == "1":\n', "        if True:\n", [HELPER, UNSET]),
    ("a supervisord on PATH is reported missing", "tests/supervisor_requirement.py",
     "    if found is None:\n", "    if True:\n", [HELPER]),
    ("the Chromebook rehearsal skips silently again", "tests/integration/test_greg_chromebook_rehearsal.py",
     '    require_supervisord("supervisord stands in for the systemd user unit")\n',
     '    if __import__("shutil").which("supervisord") is None:\n'
     '        pytest.skip("supervisord stands in for the systemd user unit")\n', [REQUIRED]),
    ("the VEPMC path rehearsal skips silently again", "tests/integration/test_greg_vepmc_path.py",
     '    require_supervisord("supervisord (requirements-dev) not installed")\n',
     '    if __import__("shutil").which("supervisord") is None:\n'
     '        pytest.skip("supervisord (requirements-dev) not installed")\n', [REQUIRED]),
    ("the VEPMC path rehearsal's check covers no test", "tests/integration/test_greg_vepmc_path.py",
     "@pytest.fixture(autouse=True)\n", "@pytest.fixture\n", [REQUIRED]),
    ("the workflow does not require supervisord", ".github/workflows/build-frontier.yml",
     '          GREG_REQUIRE_SUPERVISOR: "1"\n', '          GREG_REQUIRE_SUPERVISOR: "0"\n', [REQUIRED_IN_CI]),
    ("Canonical CI does not run the path-predicate gate", ".github/workflows/canonical-ci.yml",
     "        run: python scripts/ci/check_path_predicate_mutants.py\n", "        run: \"true\"\n", [GATES]),
    ("the workflow does not run this gate", ".github/workflows/build-frontier.yml",
     "        run: python scripts/ci/check_fail_closed_build_instrument_mutants.py\n", "        run: \"true\"\n",
     [GATES]),
    ("the workflow does not run on pull requests", ".github/workflows/build-frontier.yml",
     "on:\n  pull_request:\n  workflow_dispatch:\n", "on:\n  workflow_dispatch:\n", [GATES]),
]

# A failure raised as one of these is a mutant that broke an import, not a safeguard that was removed.
IMPORT_FAILURE = re.compile(r"^E\s+(SyntaxError|IndentationError|TabError|ImportError|ModuleNotFoundError)\b", re.M)


def purge_bytecode(repo: Path) -> None:
    for directory in [d for d in repo.rglob("__pycache__") if d.is_dir()]:
        shutil.rmtree(directory)


def pytest(repo: Path, *nodes: str) -> subprocess.CompletedProcess:
    purge_bytecode(repo)
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("GREG_REQUIRE_SUPERVISOR", None)          # the named tests set it themselves where they need it
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *nodes],
                          cwd=repo, env=env, capture_output=True, text=True, timeout=900)


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-fail-closed-build-instrument-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        baseline = pytest(repo, *sorted({t for m in MUTANTS for t in m[4]}))
        if baseline.returncode != 0:
            print("BASELINE_FAILS: the named tests must pass before any mutant can count as caught")
            print(baseline.stdout[-4000:])
            return 1
        print("BASELINE passes")
        for name, relative, old, new, tests in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            try:
                run = pytest(repo, *tests)
            finally:
                path.write_text(original)
            failed = [t for t in tests if f"FAILED {t}" in run.stdout]
            broken = IMPORT_FAILURE.search(run.stdout)
            caught = run.returncode == 1 and bool(failed) and "ERROR collecting" not in run.stdout and not broken
            if broken:
                print("INVALID", f"{name}: its test failed on {broken.group(1)}, not on behaviour")
            else:
                print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name, *(f"by {failed[0]}",) if failed else ())
            invalid += not caught
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
