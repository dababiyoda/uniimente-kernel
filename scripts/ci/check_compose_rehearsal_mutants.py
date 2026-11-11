"""Each rule of scripts/compose_rehearsal.py must fail a behavioural test when removed.

    python scripts/ci/check_compose_rehearsal_mutants.py

A mutant counts as caught only when tests/unit/test_compose_rehearsal.py reports a FAILED test. The tests build
small git repositories of their own, so the gate needs no network. A scratch copy is mutated; the live source never
is. Exit 1 on any survivor or stale anchor.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mutation_harness import ROOT, run  # noqa: E402

TESTS = "tests/unit/test_compose_rehearsal.py"
T = "scripts/compose_rehearsal.py"
SORTED = '            (already_failing if node in alone else behavioural).append({"test": node, "unit": unit.name})'

MUTANTS = [
    (T, "a test that passes alone and fails merged is a conflict", SORTED,
     '            already_failing.append({"test": node, "unit": unit.name})'),
    (T, "a test that already fails on its own head is not a composition conflict", SORTED,
     '            behavioural.append({"test": node, "unit": unit.name})'),
    (T, "the merged tree is the tree that is tested",
     '    composed_tree = export(root, merged_commit, scratch / "composed")',
     '    composed_tree = export(root, base, scratch / "composed")'),
    (T, "a cause is named only when the test passes with that head left out",
     '            if conflict["test"] not in result["failed"] and result["ran"]:\n                causes.append(other.name)',
     '            causes.append(other.name)'),
    (T, "a textual conflict is reported",
     "        if made is None:\n            conflicts[unit.name] = files\n            continue",
     "        if made is None:\n            continue"),
    (T, "an extra test file that already fails on the base is not a conflict",
     "            (already_failing if node in before else behavioural).append({\"test\": node, \"unit\": \"(also)\"})",
     "            behavioural.append({\"test\": node, \"unit\": \"(also)\"})"),
    (T, "a run in which pytest never started counts as failing",
     "    elif not counts and not failed:      # pytest printed no summary: collection or start-up failed",
     "    elif False:"),
    (T, "only the test files a head changed are run by default",
     '    return sorted(n for n in names if Path(n).name.startswith("test_") and n.endswith(".py"))',
     "    return sorted(names)"),
    (T, "a head with no test to run is listed as not checked",
     '        "unchecked": [u.name for u in units if not [f for f in u.tests if f not in own[u.name]["missing"]]],',
     '        "unchecked": [],'),
    (T, "both sides' lines are kept only where every conflicted file was named",
     "        if not lines or not set(files) <= set(union):", "        if not lines or not set(files) & set(union):"),
    (T, "a conflict is never resolved in a file nobody named",
     "        if not lines or not set(files) <= set(union):\n            return None, files, []", ""),
    (T, "a resolution by keeping both sides' lines is reported",
     "        if kept and kept_both is not None:\n            kept_both[unit.name] = kept\n", ""),
    (T, "a head that fails on the base alone is blamed on the base, not on a neighbour",
     '            if reruns[key]["ran"] and conflict["test"] in reruns[key]["failed"]:', "            if False:"),
    (T, "a conflict makes the command exit 1",
     '    return 0 if report["clean"] else 1', "    return 0"),
    (T, "a report with a textual conflict is not clean",
     '        "clean": not textual and not behavioural,', '        "clean": not behavioural,'),
]

if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, prefix="compose-rehearsal-mutants-", root=ROOT, purge_dirs=("scripts", "tests")))
