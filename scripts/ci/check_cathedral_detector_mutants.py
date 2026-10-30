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
    ("activity always rises", C, '"counts": counts, "rose": bool(crossed),', '"counts": counts, "rose": True,', TC),
    # cathedral: founder-tier outcomes, read on the ledger at both ends
    ("a test-key closure counts as a founder-tier closure", C,
     '"founder_tier_closures": [m for m in closed if (tiers.get(m) or {}).get("tier") == metrics.FOUNDER_TIER],',
     '"founder_tier_closures": list(closed),', TC),
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
    ("vertical progress lifts the verdict", C, '    elif act["rose"] and not outcome["moved"]:\n',
     '    elif act["rose"] and not outcome["moved"] and not (vertical or {}).get("newly_built"):\n', TC),
    ("no ledger reads as flat outcomes", C, 'outcome, vertical = {"measured": False, "why": NO_LEDGER}, None',
     'outcome, vertical = {"measured": True, "moved": False, "why": NO_LEDGER}, None', TC),
    ("missing history still gives a verdict", C, '    if insufficient:\n        verdict = INSUFFICIENT_HISTORY\n',
     '    if False:\n        verdict = INSUFFICIENT_HISTORY\n', TC),
    ("the declared window length is ignored", C,
     'span = THRESHOLDS["window_days"] if days is None else days', 'span = 7 if days is None else days', TC),
    ("an empty window is accepted", C, '    if not start < end:\n', '    if False:\n', TC),
    ("cli --body alone does not read --home", CLI, 'body_home = args.body or home', 'body_home = args.body', TC),
    # reality-claim guard: ceilings
    ("a claim above its declared kind passes", G, '        if rank(rung) > rank(ceiling):\n', '        if False:\n', TG),
    ("unit tests reach BODY_VERIFIED", G, '"unit_test": {"ladder": "SANDBOX_VERIFIED"', '"unit_test": {"ladder": "BODY_VERIFIED"',
     TG),
    ("an undeclared claim may reach any rung", G, 'TEST_CEILING = TEST_TIERS[-1]',
     'TEST_CEILING = "COMMERCIAL_OUTCOME_VERIFIED"', TG),
    ("an undeclared claim above the tests passes", G, '    if rank(rung) > rank(TEST_CEILING):\n', '    if False:\n', TG),
    ("a founder-device claim needs no evidence_ref", G, '            if not (isinstance(ref, str) and ref.strip()):\n',
     '            if False:\n', TG),
    ("a founder-device claim may describe a container run", G,
     '            if markers:\n                problems.append(f"declared',
     '            if False:\n                problems.append(f"declared', TG),
    ("an unknown kind is accepted", G, '        if not isinstance(kind, str) or kind not in CEILINGS:\n',
     '        if not isinstance(kind, str) or False:\n', TG),
    # reality-claim guard: reading labels
    ("a negator before the label is ignored", G, '        if _only_filler(before[negators[-1].end():]):\n            return True\n',
     '        if False:\n            return True\n', TG),
    ("a prohibition with a labelling verb is a claim", G, '        if verbs and _only_filler(before[verbs[-1].end():]):\n',
     '        if False:\n', TG),
    ("a negation after the label is ignored", G, '    return bool(NEGATED_AFTER.match(text[end:end + 80]))\n',
     '    return False\n', TG),
    ("a negation reaches across clauses", G,
     '    clause = max((m.end() for m in CLAUSE_BREAK.finditer(text, 0, start)), default=0)\n', '    clause = 0\n', TG),
    ("one-word labels are read in any case", G, '    any_case = len(parts) > 1 and label not in LABEL_CROSSWALK\n',
     '    any_case = True\n', TG),
    ("a negated container marker contradicts a founder-device claim", G,
     '        hits += [m.group(0) for m in pattern.finditer(text) if not _negated(text, m.start(), m.end())]\n',
     '        hits += [m.group(0) for m in pattern.finditer(text)]\n', TG),
    ("the founder's-device phrase is not a label", G,
     ' + [\n    ("on the founder\'s device", "FOUNDER_ACCEPTED", FOUNDER_DEVICE_PHRASE)]', '', TG),
    ("LIVE is not a label", G, 'LABEL_CROSSWALK = {"LIVE": "AUTHORIZED_LIVE", ', 'LABEL_CROSSWALK = {', TG),
    ("current_reality is not a claim field", G, '"reality_status", "current_reality", ', '"reality_status", ', TG),
    ("a schema is read as claims", G, ' and not p.name.endswith(".schema.json")}', '}', TG),
    # reality-claim guard: the crosswalk onto the one ladder
    ("FOUNDER-USED maps below the founder", G, '"FOUNDER-USED": "FOUNDER_ACCEPTED"', '"FOUNDER-USED": "BODY_VERIFIED"', TG),
    ("an unmapped level passes", G, '        if missing or extra:\n', '        if False:\n', TG),
    ("a non-monotone crosswalk passes", G, '        elif any(rank(a) > rank(b) for a, b in zip(rungs, rungs[1:])):\n',
     '        elif False:\n', TG),
    ("the directive's first level is dropped", G, 'return tuple(line for line in lines[begin + 1:end] if line)',
     'return tuple(line for line in lines[begin + 2:end] if line)', TG),
    ("a broken crosswalk does not fail the scan", G, '"failing": ladder + failing + stale,', '"failing": failing + stale,',
     TG),
    # reality-claim guard: the allowlist is never silent
    ("an allowlist entry needs no reason or owner", G,
     '        if entry and str(entry.get("reason", "")).strip() and str(entry.get("owner", "")).strip():\n',
     '        if entry:\n', TG),
    ("a stale allowlist entry passes", G, 'for key in allowlist if key not in matched]', 'for key in allowlist if False]', TG),
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
