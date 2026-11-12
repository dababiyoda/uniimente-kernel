"""Each decision of the intake recommendation must fail a behavioural test when removed.

    python scripts/ci/check_intake_mutants.py

``brief.intake`` (greg/intake.py) tells the founder which open changes to take. Every mutant here is a way for it to
say something it did not measure: a check that did not run read as passed, a timeout read as a failure or as a cause,
a stale claim read as current, a recommendation about other heads closing this mission, a head's code started outside
the worker envelope, an edit after delivery going unseen.

Only the decision points are here, because the mutation-gates job is near its time limit: what makes a unit ready,
what counts as a result, what reaches the worker envelope, what the repository may run, and what closes the mission.
The tests cover more than the gate mutates.

A mutant counts as caught only when tests/unit/test_greg_intake.py reports a FAILED test. The tests build one small
git repository and copy it, start no process but git, and need no network: the whole file runs in seconds. A scratch
copy is mutated; the live source never is. Exit 1 on any survivor or stale anchor. The rehearsal's own rules are in
check_compose_rehearsal_mutants.py.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mutation_harness import ROOT, run  # noqa: E402

TESTS = "tests/unit/test_greg_intake.py"
I = "greg/intake.py"                    # noqa: E741
R = "greg/intake_rehearsal.py"
T = "greg/templates.py"

MUTANTS = [
    # -- the request -----------------------------------------------------------------------------------------
    (I, "a branch name or a short SHA is refused",
     "    if not isinstance(value, str) or not SHA.fullmatch(value):", "    if not isinstance(value, str):"),
    (I, "the repository must be inside the body's read roots",
     '    repo = _inside(Path(asked["repository"]), ctx.read_roots)', '    repo = Path(asked["repository"])'),
    # -- the envelope ----------------------------------------------------------------------------------------
    (I, "the body's own confinement setting reaches the envelope",
     "                                         stop_check=self.ctx.stop_check, confinement=self.ctx.worker_confinement)",
     '                                         stop_check=self.ctx.stop_check, confinement="supervised")'),
    (I, "the rehearsal runs with the capability's confined runner",
     "tuple(asked[\"union\"]), run=runner, facts=facts)",
     "tuple(asked[\"union\"]), run=lambda tree, files, timeout: {\"failed\": [], \"counts\": {\"passed\": 1}, "
     "\"missing\": [], \"ran\": True, \"tail\": \"\"}, facts=facts)"),
    # -- five words, never merged ------------------------------------------------------------------------------
    (I, "a refused run is not run, never an error or a failure",
     '    if result.get("confinement") == "refused":', "    if False:"),
    (I, "a timeout is its own word",
     '    if result.get("returncode") == -1 and tail == f"timed out after {timeout}s":', "    if False:"),
    (I, "a pass needs pytest to have exited 0",
     '    if counts.get("passed") and result.get("returncode") == 0:', '    if counts.get("passed"):'),
    # -- the recommendation -------------------------------------------------------------------------------------
    (I, "a unit is never ready while one of its checks gave no result",
     "        elif unchecked:\n            recommendation, kind = f\"{NOT_CHECKED}: {unchecked[0]}\", NOT_CHECKED\n", ""),
    (I, "a unit with no test is not checked",
     '        if not tests:\n            unchecked.append("no test changed, and none was named for it")\n', ""),
    (I, "a unit whose own test fails on its own head inside the envelope is left ready", "        if broken:",
     "        if False:"),
    (I, "a unit whose own test fails on its own head inside the envelope is held as a defect of the head",
     "            unchecked.append(\"its own test fails on its own head inside the test envelope (\"",
     "            hold.append(\"its own test fails on its own head inside the test envelope (\""),
    (I, "a file rendered by another renderer version is re-rendered and judged",
     "        if inputs.get(\"renderer\") != RENDERER:", "        if False:"),
    (I, "a textual conflict holds the unit",
     '        if name in report["textual_conflicts"]:', "        if False:"),
    # -- claims and appraisals ---------------------------------------------------------------------------------
    (I, "a claim written for another head is stale",
     '        if record["head_sha"] != unit["sha"]:', "        if False:"),
    (I, "a claim whose tests gave no result here was not re-executed",
     '        elif not tests or any(not alone.get(t, {}).get("measured") for t in tests):', "        elif not tests:"),
    (I, "a check with no conclusion is still running",
     '        elif row["conclusion"] is None:', "        elif False:"),
    # -- the repository is read, and runs nothing of its own -----------------------------------------------------
    (I, "the merge's objects are written to scratch, not into the repository",
     '        env |= rehearsal.scratch_objects(repo, scratch / "objects")\n', ""),
    (I, "a filter driver the repository configures is blanked",
     '            config.append((key, ""))', "            pass"),
    (I, "a repository that configures a merge driver is refused",
     '            if key.startswith("merge."):', "            if False:"),
    # -- delivery, the sensor, the appraiser's check ----------------------------------------------------------------
    (I, "a recommendation for another request is not counted",
     '        elif twin["request_digest"] != asked:', "        elif False:"),
    (I, "the appraiser compares the delivered bytes with the render",
     "    if not path.is_file() or path.read_bytes() != expected:", "    if not path.is_file():"),
    # -- the rehearsal: a file that gave no result is no measurement ----------------------------------------------
    (R, "a runner's own word decides whether a file was measured",
     '    return states is None or bool(states.get(file, {}).get("measured"))', "    return True"),
    (R, "a test that fails merged is no conflict when its own head gave no result",
     "            if node not in alone and not measured(own[unit.name], node_file(node)):", "            if False:"),
    (R, "a rerun that gave no result names no cause",
     '            if result["ran"] and not measured(result, file):\n                blind.append(other.name)\n'
     "                continue\n", ""),
    (R, "the rehearsal has no runner of its own",
     "             union: tuple[str, ...] = (), *, run, facts: dict | None = None) -> dict:",
     "             union: tuple[str, ...] = (), *, run=None, facts: dict | None = None) -> dict:"),
    # -- the mission -----------------------------------------------------------------------------------------------
    (T, "the delivery is outside the cone unless the founder signs it in",
     '    capabilities = ["brief.intake_status", "fs.read"] + (["brief.intake"] if preauthorize_delivery else [])',
     '    capabilities = ["brief.intake_status", "fs.read", "brief.intake"]'),
    (T, "the mission's check asks for this request's digest",
     '                                       "params": {"request_digest": digest, "max_age_hours": max_age_hours},',
     '                                       "params": {"request_digest": "sha256:" + "0" * 64, '
     '"max_age_hours": max_age_hours},'),
]

if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, prefix="intake-mutants-", root=ROOT, purge_dirs=("greg", "scripts", "tests")))
