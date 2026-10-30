"""Each safeguard of the cathedral detector and the reality-claim guard must fail a behavioural test when removed.

Every mutant runs in a scratch copy of the repository (the live source is never mutated), under ``python -B`` with
PYTHONDONTWRITEBYTECODE=1 and every ``__pycache__`` purged first, so no bytecode from the checkout or an earlier mutant
runs in place of the mutated source. The named tests must pass unmutated first. A mutant counts as caught only when a
named test fails on behaviour: a mutated module that does not import is INVALID and never counted.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
C, G, CLI = "greg/cathedral.py", "acceptance/claims.py", "greg/cli.py"
TC, TG = "tests/unit/test_cathedral_detector.py", "tests/unit/test_reality_claims.py"
# (name, file, old, new, test file that must fail)
MUTANTS = [
    # cathedral: activity from git objects
    ("a shallow clone is counted as complete", C,
     'if _git(repo, "rev-parse", "--is-shallow-repository").stdout.strip() == "true":', 'if False:', TC),
    ("commits before the window count", C,
     'if stamp.isdigit() and low <= int(stamp) < high:', 'if stamp.isdigit() and int(stamp) < high:', TC),
    ("commits after the window count", C,
     'if stamp.isdigit() and low <= int(stamp) < high:', 'if stamp.isdigit() and low <= int(stamp):', TC),
    ("files added outside the window count", C,
     '            if sha not in inside:\n                continue\n', '            if False:\n                continue\n', TC),
    ("a rename counts as a new file", C, '"-M", "--diff-filter=A"', '"--no-renames", "--diff-filter=A"', TC),
    ("a merge commit is not PR-like", C, 'sum(c["parents"] > 1 or bool(', 'sum(False or bool(', TC),
    ("a squash-merge subject is not PR-like", C,
     r'PR_SUBJECT = re.compile(r"^Merge pull request #\d+|\(#\d+\)\s*$")',
     r'PR_SUBJECT = re.compile(r"^Merge pull request #\d+")', TC),
    ("any README.md is an evidence README", C, ' and "evidence" in Path(p).parts[:-1] for p in paths)', ' for p in paths)',
     TC),
    ("any file under evidence/ is an evidence README", C,
     'sum(Path(p).name == "README.md" and "evidence" in Path(p).parts[:-1] for p in paths)',
     'sum("evidence" in Path(p).parts[:-1] for p in paths)', TC),
    ("activity always rises", C, '"floors_applied": applied, "rose": bool(crossed),',
     '"floors_applied": applied, "rose": True,', TC),
    ("a replace ref cuts the history counted", C, ',\n                                   "GIT_NO_REPLACE_OBJECTS": "1"})',
     '})', TC),
    ("a grafts file is counted as complete", C, '    if grafts and (repo / grafts).is_file():', '    if False:', TC),
    ("a path that is not UTF-8 crashes the detector", C, 'encoding="utf-8", errors="surrogateescape"',
     'encoding="utf-8"', TC),
    ("a missing git crashes the detector", C,
     '        return subprocess.CompletedProcess(argv, 127, "", f"{type(exc).__name__}: {exc}")\n',
     '        raise\n', TC),
    # cathedral: the floors are scaled to the window
    ("the floors never scale with the window", C, 'scale = max(1.0, days / THRESHOLDS["window_days"])',
     'scale = 1.0', TC),
    ("a shorter window lowers the floors", C, 'scale = max(1.0, days / THRESHOLDS["window_days"])',
     'scale = days / THRESHOLDS["window_days"]', TC),
    # cathedral: founder-tier outcomes on the founder's designated body, read on the ledger at both ends
    ("a test-key closure counts as a founder-tier closure", C,
     'counted = [m for m in closed if (tiers.get(m) or {}).get("tier") == metrics.FOUNDER_TIER',
     'counted = [m for m in closed if True', TC),
    ("a body never designated counts its founder-tier closures", C,
     '               and body is not None and body["seq"] < registered.get(m, -1)]', ']', TC),
    ("a closure registered before the designation counts", C,
     'and body is not None and body["seq"] < registered.get(m, -1)]', 'and body is not None]', TC),
    ("a delegate's designation names the founder's body", C,
     'if e.payload.get("kind") == "BODY_DESIGNATE" and e.payload.get("signer") == "founder"}',
     'if e.payload.get("kind") == "BODY_DESIGNATE"}', TC),
    ("any designation purpose names the founder's body", C,
     'if event.payload.get("purpose") == "first_founder_body" and record is not None:',
     'if record is not None:', TC),
    ("closures already there at the start count again", C,
     '"founder_tier_closures": sorted(set(b["founder_tier_closures"]) - set(a["founder_tier_closures"])),',
     '"founder_tier_closures": sorted(b["founder_tier_closures"]),', TC),
    ("a VEPMC decrease counts as growth", C,
     'max(0, b["vepmc_founder_tier_count"] - a["vepmc_founder_tier_count"])',
     'b["vepmc_founder_tier_count"] - a["vepmc_founder_tier_count"]', TC),
    ("nodes achieved before the window count", C,
     '"achieved_nodes": [n for n in b["achieved_nodes"] if n not in a["achieved_nodes"]],',
     '"achieved_nodes": list(b["achieved_nodes"]),', TC),
    ("no outcome ever moves", C, 'moved = [k for k in THRESHOLDS["outcome_moved_when_any_grew"] if grew[k]]',
     'moved = []', TC),
    ("the window's start reads the whole ledger", C,
     'cut = next((i for i, r in enumerate(records) if _at(r.ts_utc) >= moment), len(records))',
     'cut = len(records)', TC),
    ("a record at the window's start counts before it", C,
     'if _at(r.ts_utc) >= moment), len(records))', 'if _at(r.ts_utc) > moment), len(records))', TC),
    # cathedral: the ledger covers the window as the founder's body, or the verdict is insufficient
    ("a ledger that begins after the window reads as flat", C,
     '    if begins is None or _at(begins) >= until:\n', '    if begins is None:\n', TC),
    ("an undesignated body decides", C, '    elif body is None:\n        gap = (', '    elif False:\n        gap = (', TC),
    ("a designation inside the window covers all of it", C, '    elif _at(body["at"]) > since:\n',
     '    elif False:\n', TC),
    ("an outcome that moved under partial coverage does not decide", C,
     '"decides": gap is None or bool(moved)', '"decides": gap is None', TC),
    ("vertical progress lifts the verdict", C, '    elif act["rose"] and not outcome["moved"]:\n',
     '    elif act["rose"] and not outcome["moved"] and not (vertical or {}).get("newly_built"):\n', TC),
    ("no ledger reads as flat outcomes", C,
     'outcome, vertical = {"measured": False, "decides": False, "why": NO_LEDGER}, None',
     'outcome, vertical = {"measured": True, "decides": True, "moved": False, "why": NO_LEDGER}, None', TC),
    ("missing history still gives a verdict", C, '    if insufficient:\n        verdict = INSUFFICIENT_HISTORY\n',
     '    if False:\n        verdict = INSUFFICIENT_HISTORY\n', TC),
    # cathedral: the window
    ("the declared window length is ignored", C,
     'span = THRESHOLDS["window_days"] if days is None else days', 'span = 7 if days is None else days', TC),
    ("an empty window is accepted", C, '    if not start < end:\n', '    if False:\n', TC),
    ("a window past the calendar is a traceback", C, '    except (OverflowError, ValueError) as exc:\n',
     '    except ValueError as exc:\n', TC),
    ("cli --body alone does not read --home", CLI, 'body_home = args.body or home', 'body_home = args.body', TC),
    # reality-claim guard: ceilings
    ("a claim above its declared kind passes", G, '        if rank(rung) > rank(ceiling):\n', '        if False:\n', TG),
    ("unit tests reach BODY_VERIFIED", G, '"unit_test": {"ladder": "SANDBOX_VERIFIED"', '"unit_test": {"ladder": "BODY_VERIFIED"',
     TG),
    ("an undeclared claim may reach any rung", G, 'TEST_CEILING = TEST_TIERS[-1]',
     'TEST_CEILING = "COMMERCIAL_OUTCOME_VERIFIED"', TG),
    ("an undeclared claim above the tests passes", G, '    if rank(rung) > rank(TEST_CEILING):\n', '    if False:\n', TG),
    ("an unknown kind is accepted", G, '        if not isinstance(kind, str) or kind not in CEILINGS:\n',
     '        if not isinstance(kind, str) or False:\n', TG),
    # reality-claim guard: a declared kind beyond the tests rests on a checkable record and describes no test run
    ("a founder-device claim needs no checkable evidence_ref", G, '            if unchecked:\n', '            if False:\n',
     TG),
    ("only a founder-device claim needs a checkable ref", G, '        if ceiling in BEYOND_TESTS:\n',
     '        if ceiling == "FOUNDER_ACCEPTED":\n', TG),
    ("a placeholder ref is not called one", G, '    if PLACEHOLDER.match(text):\n', '    if False:\n', TG),
    ("any sha256 text is a digest", G, r'DIGEST = re.compile(r"\bsha256:[0-9a-f]{64}\b")',
     r'DIGEST = re.compile(r"\bsha256:[0-9a-f]+")', TG),
    ("an all-zero digest resolves", G, 'if any(set(d[7:]) != {"0"} for d in DIGEST.findall(text)):',
     'if DIGEST.findall(text):', TG),
    ("any path resolves", G, '            and target != relative and (Path(root) / target).is_file():',
     '            and True:', TG),
    ("a record may rest on itself", G, '            and target != relative and (Path(root) / target).is_file():',
     '            and (Path(root) / target).is_file():', TG),
    ("a ref may leave the repository", G, 'and ".." not in Path(target).parts', 'and True', TG),
    ("an absolute path is a repository file", G, 'and not Path(target).is_absolute() and', 'and', TG),
    ("a founder-device claim may describe a container run", G,
     '            if markers:\n                problems.append(f"declared',
     '            if False:\n                problems.append(f"declared', TG),
    ("only the claim itself is read for a run it describes", G,
     'others = [s for key, v in record.items() if field_name(key) != KIND_FIELD for s in _strings(v)]',
     'others = [value]', TG),
    ("a nested record's strings are not read for a run", G,
     '    if isinstance(value, dict):\n        return [s for v in value.values() for s in _strings(v)]\n',
     '    if isinstance(value, dict):\n        return []\n', TG),
    ("a test run is not a marker", G, 'MARKERS = (REHEARSAL, CONTAINER, TEST_RUN, CI)', 'MARKERS = (REHEARSAL, CONTAINER, CI)',
     TG),
    ("CI is not a marker", G, 'MARKERS = (REHEARSAL, CONTAINER, TEST_RUN, CI)', 'MARKERS = (REHEARSAL, CONTAINER, TEST_RUN)',
     TG),
    ("a test key is not a marker", G, r'\btest[- ]keys?\b|', '', TG),
    ("a fixture is not a marker", G, r'|\bfixtures?\b", re.I)', '", re.I)', TG),
    ("--no-passphrase is not a marker", G, '|--no-passphrase|', '|', TG),
    ("a throwaway home is not a marker", G, r'|\bthrowaway\b|', '|', TG),
    ("docker is not a marker", G, 'containers?|docker|sandbox(?:ed)?', 'containers?|sandbox(?:ed)?', TG),
    ("sandboxed is not a marker", G, 'containers?|docker|sandbox(?:ed)?', 'containers?|docker', TG),
    ("a simulation is not a marker", G, r'\bsimulat(?:ed|ion|or)\b|', '', TG),
    # reality-claim guard: reading labels
    ("a negator before the label is ignored", G, '        if _only_filler(before[negators[-1].end():]):\n            return "before"\n',
     '        if False:\n            return "before"\n', TG),
    ("a prohibition with a labelling verb is a claim", G,
     '        if verbs and _only_filler(before[verbs[-1].end():]) and any(\n',
     '        if False and any(\n', TG),
    ("a conjunction does not end a prohibition", G,
     '                not COORDINATION.search(before[n.end():verbs[-1].start()]) for n in negators\n',
     '                True for n in negators\n', TG),
    ("a negation after the label is ignored", G, '    return "after" if NEGATED_AFTER.match(text[end:end + 80]) else None\n',
     '    return None\n', TG),
    ("a status after a comma negates the label", G, 'NEGATED_AFTER = re.compile(r"^ *:? *', 'NEGATED_AFTER = re.compile(r"^[ :,]*', TG),
    ("a status after a dash negates the label", G, 'NEGATED_AFTER = re.compile(r"^ *:? *', 'NEGATED_AFTER = re.compile(r"^[ :-]*', TG),
    ("a negation inside a parenthesis hides the label before it", G,
     'NEGATED_AFTER = re.compile(r"^ *:? *', 'NEGATED_AFTER = re.compile(r"^[ :(]*', TG),
    ("'not' followed by anything negates the label", G, r'r"(?:not\s+yet\b|not\s+(?:reached', r'r"(?:not\b|not\s+(?:reached', TG),
    ("'as required' negates the label", G, r'r"(?:not\s+yet\b|', r'r"(?:as\s+required\b|not\s+yet\b|', TG),
    ("'open' negates the label", G, r'r"(?:not\s+yet\b|', r'r"(?:open\b|not\s+yet\b|', TG),
    ("a status after the label holds over a container record", G,
     '    claims = asserted(value, after_holds=not markers)\n', '    claims = asserted(value)\n', TG),
    ("a negation reaches across clauses", G,
     '    clause = max((m.end() for m in CLAUSE_BREAK.finditer(text, 0, start)), default=0)\n', '    clause = 0\n', TG),
    ("one-word labels are read in any case", G, '    any_case = len(parts) > 1 and label not in LABEL_CROSSWALK\n',
     '    any_case = True\n', TG),
    ("a whole value of 'live' is not LIVE", G, '    if whole in LABEL_CROSSWALK:', '    if False:', TG),
    ("a negated container marker contradicts a founder-device claim", G,
     '        hits += [m.group(0) for m in pattern.finditer(text) if not _negated(text, m.start(), m.end())]\n',
     '        hits += [m.group(0) for m in pattern.finditer(text)]\n', TG),
    ("the founder's-device phrase is not a label", G,
     ' + [\n    ("on the founder\'s device", "FOUNDER_ACCEPTED", FOUNDER_DEVICE_PHRASE)]', '', TG),
    ("the founder's laptop is not the founder's device", G, '(?:device|chromebook|hardware|machine|laptop|',
     '(?:device|chromebook|hardware|machine|', TG),
    ("'the founder device' is not the founder's device", G, r"(?:founder|alfonso)(?:['’]s)? ", r"(?:founder|alfonso)['’]s ",
     TG),
    ("LIVE is not a label", G, 'LABEL_CROSSWALK = {"LIVE": "AUTHORIZED_LIVE", ', 'LABEL_CROSSWALK = {', TG),
    # reality-claim guard: what is read, in what form
    ("look-alike dashes are not read as '-'", G, '    return re.sub(r"\\s", " ", DASHES.sub("-", text))\n',
     '    return re.sub(r"\\s", " ", text)\n', TG),
    ("tabs and other spaces are not read as ' '", G, '    return re.sub(r"\\s", " ", DASHES.sub("-", text))\n',
     '    return DASHES.sub("-", text)\n', TG),
    ("zero-width characters are kept", G, 'if unicodedata.category(ch) != "Cf")', 'if True)', TG),
    ("compatibility forms are not normalised", G, 'unicodedata.normalize("NFKC", text)', 'text', TG),
    ("keys are matched only as written", G, '    return SEPARATORS.sub("_", CAMEL.sub("_", str(key))).lower()\n',
     '    return str(key)\n', TG),
    ("a list under a claim field is not read", G,
     '    if isinstance(value, (list, tuple)):\n        return [found for i, v in enumerate(value)',
     '    if False:\n        return [found for i, v in enumerate(value)', TG),
    ("a record under a claim field is not read", G,
     '    if isinstance(value, dict):\n        return [found for key, v in value.items()',
     '    if False:\n        return [found for key, v in value.items()', TG),
    ("a record under a claim field brings no evidence kind", G,
     '            record = {**data, **value} if isinstance(value, dict) else data\n', '            record = data\n', TG),
    ("validation_status is not a claim field", G, '"status",\n                "validation_status")', '"status")', TG),
    ("current_reality is not a claim field", G, '"reality_tier", "current_reality", ', '"reality_tier", ', TG),
    ("evidence directories outside docs are not read", G, '"**/evidence/**/*.json", ', '', TG),
    ("a schema is read as claims", G, ' and not p.name.endswith(".schema.json")}', '}', TG),
    ("an unreadable file passes", G, '"failing": ladder + failing + stale + unreadable,', '"failing": ladder + failing + stale,',
     TG),
    ("a byte-order mark makes a file unreadable", G, 'path.read_text(encoding="utf-8-sig")', 'path.read_text(encoding="utf-8")',
     TG),
    ("only one YAML document is read", G, '    documents = list(yaml.safe_load_all(text))\n',
     '    documents = [yaml.safe_load(text)]\n', TG),
    # reality-claim guard: the crosswalk onto the one ladder
    ("FOUNDER-USED maps below the founder", G, '"FOUNDER-USED": "FOUNDER_ACCEPTED"', '"FOUNDER-USED": "BODY_VERIFIED"', TG),
    ("externally_verified outcomes map below the tests", G, '"externally_verified": "EXTERNALLY_VERIFIED"}',
     '"externally_verified": "BODY_VERIFIED"}', TG),
    ("the Outcome contract is not crosswalked", G,
     ',\n                  "contracts/outcome.schema.json validation_status": (outcome_levels(), OUTCOME_CROSSWALK)}', '}', TG),
    ("an unmapped level passes", G, '        if missing or extra:\n', '        if False:\n', TG),
    ("a non-monotone crosswalk passes", G, '        elif any(rank(a) > rank(b) for a, b in zip(rungs, rungs[1:])):\n',
     '        elif False:\n', TG),
    ("the directive's first level is dropped", G, 'return tuple(line for line in lines[begin + 1:end] if line)',
     'return tuple(line for line in lines[begin + 1:end] if line)[1:]', TG),
    ("a broken crosswalk does not fail the scan", G, '"failing": ladder + failing + stale + unreadable,',
     '"failing": failing + stale + unreadable,', TG),
    # reality-claim guard: the allowlist is never silent and stays with this repository
    ("an allowlist entry needs no reason or owner", G,
     '        if entry and str(entry.get("reason", "")).strip() and str(entry.get("owner", "")).strip():\n',
     '        if entry:\n', TG),
    ("a stale allowlist entry passes", G, 'for key in allowlist if key not in matched]', 'for key in allowlist if False]', TG),
    ("this repository's allowlist applies to any tree", G, 'allowlist = ALLOWLIST if root.resolve() == ROOT else {}',
     'allowlist = ALLOWLIST', TG),
]

IMPORT_FAILURE = re.compile(r"^E\s+(SyntaxError|IndentationError|TabError|ImportError|ModuleNotFoundError)\b", re.M)


def purge(repo: Path) -> None:
    for cache in [d for d in repo.rglob("__pycache__") if d.is_dir()]:
        shutil.rmtree(cache, ignore_errors=True)


def main() -> int:
    invalid = caught_count = 0
    with tempfile.TemporaryDirectory(prefix="greg-cathedral-mutants-") as temp:
        repo, scratch = Path(temp) / "repo", Path(temp) / "tmp"
        scratch.mkdir()
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(scratch)}

        def pytest(*tests, first_failure=True):
            purge(repo)
            return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", *(["-x"] if first_failure else []),
                                   "-p", "no:cacheprovider", *tests], cwd=repo, env=env, capture_output=True,
                                  text=True, timeout=900)

        baseline = pytest(TC, TG, first_failure=False)
        if baseline.returncode != 0:
            print("BASELINE_FAILS: the named tests must pass before any mutant can count as caught", flush=True)
            print(baseline.stdout[-4000:])
            return 1
        for name, relative, old, new, test in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1 or old == new:
                print("STALE", name, flush=True)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            try:
                purge(repo)
                module = ".".join(Path(relative).with_suffix("").parts)
                loads = subprocess.run([sys.executable, "-B", "-c", f"import {module}"], cwd=repo, env=env,
                                       capture_output=True, text=True, timeout=120)
                run = None if loads.returncode else pytest(test)
            finally:
                path.write_text(original)
            if run is None:
                print("INVALID", f"{name}: the mutated module does not import", flush=True)
                invalid += 1
                continue
            on_import = IMPORT_FAILURE.search(run.stdout)
            caught = (run.returncode == 1 and "FAILED tests/" in run.stdout and "ERROR collecting" not in run.stdout
                      and not on_import)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name, flush=True)
            invalid += not caught
            caught_count += caught
        clean = pytest(TC, TG, first_failure=False)
        print("UNMUTATED", "PASS" if clean.returncode == 0 else "FAIL", flush=True)
        invalid += clean.returncode != 0
    print(f"{caught_count}/{len(MUTANTS)} mutants caught", flush=True)
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
