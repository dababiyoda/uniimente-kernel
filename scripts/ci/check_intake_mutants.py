"""Each decision of the intake recommendation must fail a behavioural test when removed.

    python scripts/ci/check_intake_mutants.py

``brief.intake`` (greg/intake.py) tells the founder which open changes to take. Every mutant here is a way for it to
say something it did not measure: a check that did not run read as passed, a timeout read as a failure or as a cause,
a stale claim read as current, a recommendation about other heads closing this mission, a head's code started outside
the worker envelope, an edit after delivery going unseen.

A mutant counts as caught only when tests/unit/test_greg_intake.py reports a FAILED test. The tests build small git
repositories of their own, so the gate needs no network. A scratch copy is mutated; the live source never is. Exit 1
on any survivor or stale anchor. The rehearsal's own rules are in check_compose_rehearsal_mutants.py.
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
    (I, "a revision that is not in the repository is refused by name",
     '                if rehearsal.git(repo, "cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode:',
     "                if False:"),
    (I, "untrusted text is one bounded line before it is kept",
     '    text = " ".join("".join(ch if ch.isprintable() else " " for ch in value).split())\n'
     "    return text if len(text) <= limit else text[:limit - 1] + \"…\"",
     "    return value"),
    (I, "untrusted text cannot open a table cell or a code span in the recommendation",
     '    text = text.replace("`", "\'").replace("|", "\\\\|")\n', ""),
    # -- the envelope ----------------------------------------------------------------------------------------
    (I, "the body's own confinement setting reaches the envelope",
     "                                         stop_check=self.ctx.stop_check, confinement=self.ctx.worker_confinement)",
     '                                         stop_check=self.ctx.stop_check, confinement="supervised")'),
    (I, "a stop request ends the rehearsal",
     "            if self.ctx.stop_check is not None and self.ctx.stop_check():", "            if False:"),
    (I, "the rehearsal runs with the capability's confined runner",
     "tuple(asked[\"union\"]), run=runner, facts=facts)",
     "tuple(asked[\"union\"]), run=lambda tree, files, timeout: {\"failed\": [], \"counts\": {\"passed\": 1}, "
     "\"missing\": [], \"ran\": True, \"tail\": \"\"}, facts=facts)"),
    # -- five words, never merged ------------------------------------------------------------------------------
    (I, "a refused run is not run, never an error or a failure",
     '    if result.get("confinement") == "refused":', "    if False:"),
    (I, "a refusal says envelope unavailable only where the host has none",
     '("envelope unavailable: " if not envelope() else "refused before it ran: ")',
     '("envelope unavailable: " if envelope() else "refused before it ran: ")'),
    (I, "a timeout is its own word",
     '    if result.get("returncode") == -1 and tail == f"timed out after {timeout}s":', "    if False:"),
    (I, "a pass needs pytest to have exited 0",
     '    if counts.get("passed") and result.get("returncode") == 0:', '    if counts.get("passed"):'),
    (I, "a failure whose failing tests are not all named is not a whole measurement",
     "        whole = bool(counts) and len(named) >= bad and len(named) <= MAX_NODES \\\n"
     "            and all(len(n) <= NODE_TEXT for n in named)", "        whole = True"),
    (I, "another file's name in the output is not this file's failure",
     "             if m and rehearsal.node_file(m.group(2)) == file}", "             if m}"),
    (I, "a file in which nothing ran to a result is not run, not passed",
     '    if counts or "no tests ran" in " ".join(lines[-2:]):\n        return {"state": NOT_RUN,',
     '    if counts or "no tests ran" in " ".join(lines[-2:]):\n        return {"state": PASSED,'),
    # -- the recommendation -------------------------------------------------------------------------------------
    (I, "a unit is never ready while one of its checks gave no result",
     "        elif unchecked:\n            recommendation, kind = f\"{NOT_CHECKED}: {unchecked[0]}\", NOT_CHECKED\n", ""),
    (I, "a unit with no test is not checked",
     '        if not tests:\n            unchecked.append("no test changed, and none was named for it")\n', ""),
    (I, "a unit left out of the merge says its tests did not run there",
     "            if merged is None:\n                both = {\"state\": NOT_RUN, \"measured\": False,",
     "            if False:\n                both = {\"state\": NOT_RUN, \"measured\": False,"),
    (I, "a test file over the limit or oddly named is reported as not run",
     "        for item in skipped:\n            tests.append(", "        for item in []:\n            tests.append("),
    (I, "a unit whose own test fails on its own head is held", "        if broken:", "        if False:"),
    (I, "a textual conflict holds the unit",
     '        if name in report["textual_conflicts"]:', "        if False:"),
    (I, "the head that breaks another head's test is held too",
     '            elif name in conflict["caused_by"]:', "            elif False:"),
    (I, "a head that contains another is taken after it", "        elif after:", "        elif False:"),
    (I, "a failed check for this revision holds the unit",
     '        if any(c["status"] == CHECK_FAILED for c in checks):', "        if False:"),
    (I, "the result says whether any check ran",
     '    checks = {"ran": bool(ran), "why": None if ran else (', '    checks = {"ran": True, "why": None if ran else ('),
    # -- claims and appraisals ---------------------------------------------------------------------------------
    (I, "a claim written for another head is stale",
     '        if record["head_sha"] != unit["sha"]:', "        if False:"),
    (I, "a claim whose tests gave no result here was not re-executed",
     '        elif not tests or any(not alone.get(t, {}).get("measured") for t in tests):', "        elif not tests:"),
    (I, "a different result is said to be different",
     "            status = SAME if same else DIFFERENT", "            status = SAME"),
    (I, "a unit with no claims record is said to have none",
     "    if record is None:\n        return [{\"claim\": \"\", \"status\": NO_CLAIMS, \"detail\": \"\"}], \\",
     "    if record is None:\n        return [], \\"),
    (I, "a check result for another head is stale",
     '        if row["head_sha"] != unit["sha"]:', "        if False:"),
    (I, "a check with no conclusion is still running",
     '        elif row["conclusion"] is None:', "        elif False:"),
    (I, "a failing conclusion is a failed check",
     '        elif row["conclusion"] in FAILING:', "        elif False:"),
    (I, "a unit with no result for its exact head says so",
     "    if not exact:\n        checks.append(", "    if False:\n        checks.append("),
    # -- the repository is read, and runs nothing of its own -----------------------------------------------------
    (I, "the merge's objects are written to scratch, not into the repository",
     '        env |= rehearsal.scratch_objects(repo, scratch / "objects")\n', ""),
    (I, "a filter driver the repository configures is blanked",
     '            config.append((key, ""))', "            pass"),
    (I, "a repository that configures a merge driver is refused",
     '            if key.startswith("merge."):', "            if False:"),
    (I, "a git that ignores configuration from its environment is refused",
     '        if rehearsal.git(repo, "config", "--get", "core.hooksPath", check=False).stdout.decode().strip() != '
     '"/dev/null":', "        if False:"),
    (I, "a path that cannot be read as a repository is a refusal, not an unknown outcome",
     "    except OSError as exc:      # scratch could not be written",
     "    except ZeroDivisionError as exc:      # scratch could not be written"),
    (I, "only the first test files up to the limit are started",
     'units.append(rehearsal.Unit(unit["name"], unit["sha"], tests=tests[:MAX_TESTS]))',
     'units.append(rehearsal.Unit(unit["name"], unit["sha"], tests=tests))'),
    # -- delivery, the sensor, the appraiser's check ----------------------------------------------------------------
    (I, "a recommendation for another request is not counted",
     '        elif twin["request_digest"] != asked:', "        elif False:"),
    (I, "a recommendation edited after delivery is not counted",
     "                      and hashlib.sha256(markdown.read_bytes()).hexdigest() == twin.get(\"markdown_sha256\")\n",
     ""),
    (I, "a twin that claims a request it does not hold is not counted",
     '                      and digest(twin.get("request")) == twin.get("request_digest"))', "                      )"),
    (I, "a recommendation older than the limit is not counted",
     "max(now - markdown.stat().st_mtime, 0.0) / 3600) > limit:",
     "max(now - markdown.stat().st_mtime, 0.0) / 3600) > limit * 1000:"),
    (I, "the appraiser compares the delivered bytes with the render",
     "    if not path.is_file() or path.read_bytes() != expected:", "    if not path.is_file():"),
    (I, "the appraiser compares the twin with the receipted inputs",
     "    if not twin.is_file() or twin.read_bytes() != twin_bytes(inputs, text, path.name):",
     "    if not twin.is_file():"),
    (I, "the appraiser checks the retained inputs against their digest",
     '    if digest(inputs) != output.get("inputs_digest"):', "    if False:"),
    (I, "the appraiser refuses a file outside the delivery root",
     "    if deliver_root is None or Path(deliver_root).resolve() not in path.resolve().parents:", "    if False:"),
    # -- the rehearsal: a file that gave no result is no measurement ----------------------------------------------
    (R, "a runner's own word decides whether a file was measured",
     '    return states is None or bool(states.get(file, {}).get("measured"))', "    return True"),
    (R, "a test that fails merged is no conflict when its own head gave no result",
     "            if node not in alone and not measured(own[unit.name], node_file(node)):", "            if False:"),
    (R, "a test that fails alone did not pass merged when the merged tree gave no result",
     "            if not measured(composed[unit.name], node_file(node)):", "            if False:"),
    (R, "a rerun that gave no result names no cause",
     '            if result["ran"] and not measured(result, file):\n                blind.append(other.name)\n'
     "                continue\n", ""),
    (R, "a rerun on the base that gave no result is said",
     '            if reruns[key]["ran"] and not measured(reruns[key], file):', "            if False:"),
    (R, "what each file did is carried beside the counts",
     '    if any("states" in result for result in own.values()):', "    if False:"),
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
