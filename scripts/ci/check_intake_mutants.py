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
     "        elif unit[\"not_checked\"]:\n            recommendation, kind = f\"{NOT_CHECKED}: {unit['not_checked'][0]}\", "
     "NOT_CHECKED\n", ""),
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
    (I, "a claim written for another head, or for none, is stale",
     '        named = _names_head(record["head_sha"], unit["sha"])', "        named = True"),
    (I, "a claim whose tests gave no result here was not re-executed",
     '        elif not tests or any(not alone.get(t, {}).get("measured") for t in tests):', "        elif not tests:"),
    (I, "a check with no conclusion, or one a hosting service calls unfinished, is still running",
     "        elif conclusion is None or conclusion.lower() in UNFINISHED:", "        elif conclusion is None:"),
    # -- review of 885b7b7a (2026-11-12): its survivors and its findings ---------------------------------------------
    (I, "k: a failure whose failing tests are not all named is not a measurement",
     '                if state["state"] in (TIMED_OUT, NOT_RUN, ERRORED) or (state["state"] == FAILED\n'
     '                                                                        and not state["measured"]):',
     '                if state["state"] in (TIMED_OUT, NOT_RUN, ERRORED):'),
    (I, "o: a check whose every result is for another head holds the unit",
     '            hold.append(f"stale: check {check} has results only for another head")', "            pass"),
    (I, "q: an existing twin with other bytes is never overwritten",
     '        raise CapabilityError(f"{target.name} already exists with different content; nothing was overwritten")',
     "        target.unlink()"),
    (I, "n: an earlier attempt's scratch is removed first",
     "    shutil.rmtree(scratch, ignore_errors=True)        # an interrupted earlier attempt's exports; never a result\n",
     ""),
    (I, "F4: a recommendation GREG did not deliver under a receipt is not counted",
     "        elif receipt is None:\n            planted += 1\n", ""),
    (I, "F4: a delivered recommendation counts only while it is what its receipt renders",
     "        elif not verify_delivery(receipt[0], ctx.deliver_root)[0] \\\n", "        elif False \\\n"),
    (I, "F4: only brief.intake's own receipts are deliveries",
     '                 if r.payload.get("capability") == "brief.intake"}', "}"),
    (R, "F5: a renamed, copied or retyped test file is listed",
     'CHANGED = ("--no-renames", "--diff-filter=AMT")', 'CHANGED = ("--diff-filter=AM",)'),
    (I, "F6: git reads only the named repository",
     '**(_pinned(repo, roots) if roots is not None else {})}', "}"),
    (I, "F7: a head that contains a held head is held",
     '        unit["hold"] += [f"it contains {inner}, which is held', '        unit["hold"] += [] and [f"it contains {inner}, '
     'which is held'),
    (I, "F8: a STOP during the last run delivers nothing",
     "    runner.stopped()          # nothing is delivered after a STOP, even one that ended or arrived during the last "
     "run\n", ""),
    (I, "F10: a claim this run contradicts keeps the unit from ready",
     "            if claim[\"status\"] in (DIFFERENT, UNREADABLE):", "            if False:"),
    (I, "F11: a head is named only by its full SHA or a prefix of at least 12 hex digits",
     "    return len(claimed) >= MIN_SHA_PREFIX and", "    return"),
    (I, "F3: one invocation has a time budget across its files", "            if left < 1:", "            if False:"),
    (R, "F18: a test file the merged tree holds in exactly another head's version is not compared for this head",
     "            if owners:", "            if False:"),
    # -- the second review of 387e8417 (2026-11-12): its findings and the survivors it named ---------------------------
    (R, "R1: a failure in a test file the merged tree merges from several versions is measured, never dropped",
     "            if owners:", "            if True:"),
    (R, "R1: only a head that runs the file can own the merged version, so a failure in it is compared somewhere",
     "            owners = [o.name for o in in_merge if o.name != unit.name and file in o.tests",
     "            owners = [o.name for o in in_merge if o.name != unit.name"),
    (R, "R1: a head that edited the failing test's file is not left out to look for the cause",
     '            if other.name == conflict["unit"] or other.name in editors:',
     '            if other.name == conflict["unit"]:'),
    (I, "R1: every head whose edits the failing test's file holds is held",
     "            elif name in shared:", "            elif False:"),
    (I, "a head the cause search could not measure is not checked, never ready",
     '            elif name in conflict.get("not_measured_without", ()):', "            elif False:"),
    (I, "R3: a test file is found without following a link in GREG's own process",
     "        absent = {f: why for f in files if (why := _absent(tree, f))}",
     '        absent = {f: "the file does not exist in this tree" for f in files if not (tree / f).is_file()}'),
    (I, "R4 (M1): a passed or failed result for this head makes a check name current",
     '        current = {c["name"] for c in checks if c.get("this_head") and c["status"] in (CHECK_PASSED, CHECK_FAILED)}',
     "        current = set()"),
    (I, "R4: a cancelled, skipped, neutral or running row for this head does not make a check name current",
     '        current = {c["name"] for c in checks if c.get("this_head") and c["status"] in (CHECK_PASSED, CHECK_FAILED)}',
     '        current = {c["name"] for c in checks if c.get("this_head")}'),
    (I, "R5: a failing check that names no head holds",
     '            if check.get("names_no_head") and str(check.get("conclusion")).lower() in FAILING:',
     "            if False:"),
    (I, "R6: a link in the git directory that leads outside the read roots is refused",
     '    no_link_out(gitdir, "its git directory")\n', ""),
    (I, "R6: a link in an alternate object store that leads outside the read roots is refused",
     '        no_link_out(store, "an object store")\n', ""),
    (I, "R6: a file the configuration names outside the read roots is refused",
     "        for key in CONFIG_FILES if roots is not None else ():", "        for key in ():"),
    (I, "R6: a .git link that leads outside the read roots is refused",
     '    if dot.is_symlink():\n        inside(dot, "its .git")\n', ""),
    (I, "R7: alternate stores nested deeper than git follows them are refused",
     "                if depth >= ALTERNATE_DEPTH:", "                if False:"),
    (I, "R7 re-check: nesting is counted as plain git counts it, not as the rehearsal's git does",
     "                if depth >= ALTERNATE_DEPTH:", "                if depth >= ALTERNATE_DEPTH + 1:"),
    (I, "R6 re-check: a directory link to a place inside the roots is not listed in turn",
     "os.walk(directory, onerror=unlistable, followlinks=True)", "os.walk(directory, onerror=unlistable)"),
    (I, "R6 re-check: a link back to a directory already listed is listed again",
     "            if real in walked:\n", "            if False:\n"),
    (I, "R8 (M2): a head is named only by a prefix of its SHA",
     "and bool(SHA_PREFIX.fullmatch(claimed)) and sha.startswith(claimed)",
     "and bool(SHA_PREFIX.fullmatch(claimed)) and claimed in sha"),
    (I, "R8 (M3): an error count in a claimed result is a failure",
     '    if any(int(m.group(1)) for m in counts if m.group(2) in ("failed", "error", "errors")):',
     '    if any(int(m.group(1)) for m in counts if m.group(2) in ("failed",)):'),
    (I, "R8 (M6): a worktree's repository outside the read roots is refused",
     '        common = inside(gitdir / text(gitdir / "commondir").strip(), "the repository this worktree belongs to")',
     '        common = gitdir / text(gitdir / "commondir").strip()'),
    (I, "R8 (M7): a relative alternate is resolved from the store that lists it",
     "                stores.append((Path(line) if Path(line).is_absolute() else store / line, depth + 1))",
     "                stores.append((Path(line), depth + 1))"),
    (I, "R8 (M10): only a positive receipt is a delivery",
     ' and result.get("result_class") == "positive" \\\n', " \\\n"),
    (I, "R9: a recommendation's age comes from its receipt's time, not the file's",
     "                or (age := _receipt_age_hours(receipt[1], now)) is None:",
     "                or (age := max(now - markdown.stat().st_mtime, 0.0) / 3600) is None:"),
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
