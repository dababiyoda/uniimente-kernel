"""Each safeguard of the typed-blocker projection (greg/blockers.py and its surfaces) must fail a behavioral test
when removed.

Every mutant runs in a scratch copy of the repository with ``python -B`` and PYTHONDONTWRITEBYTECODE=1, after every
``__pycache__`` in the copy is purged, so no compiled file of an earlier mutant (or of the original) can stand in for
the mutated source. The unmutated copy must pass first; a mutant whose text no longer occurs exactly once is STALE.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TESTS = "tests/unit/test_greg_blockers.py"
B = "greg/blockers.py"
MUTANTS = [
    ("a blocker the engine's rule resolves is still listed",
     [(B, "        if resolved:\n            continue", "        if False:\n            continue")]),
    ("an abandoned mission's blocker is listed",
     [(B, "if m.blocker is None or m.status in TERMINAL or", "if m.blocker is None or")]),
    ("the mission filter is ignored",
     [(B, " or (mission_id is not None and mid != mission_id):", ":")]),
    ("an incomplete record is shown",
     [(B, "    if missing or set(record) != set(FIELDS):", "    if False:")]),
    ("'none required' without a reason is accepted",
     [(B, "    if not reason.strip():", "    if False:")]),
    ("a caller's engine without a registry is used for resolution",
     [(B, '    if getattr(engine, "registry", None) is None:', "    if engine is None:")]),
    ("the read-only view resolves without the body's Genesis",
     [(B, "    if home is not None:\n        genesis = Genesis(", "    if False:\n        genesis = Genesis(")]),
    ("the body home is not found from the ledger",
     [(B, "    return home if Layout(home).ledger == Path(path).resolve() and Layout(home).config.is_file() else None",
       "    return None")]),
    ("the record cites a stale mission.blocked fact",
     [(B, 'event = next((e for e in reversed(blocked.get(mid, [])) if e.payload.get("blocker") == m.blocker), None)',
       "event = next(iter(blocked.get(mid, [])), None)")]),
    ("a decision no DECISION lifts is typed as answerable",
     [(B, "    if kind in NOT_ANSWERABLE:", "    if False:")]),
    ("an outage claims it needs authority",
     [(B, '            "required_authority": _none("the re-run searches',
       '            "required_authority": ("the founder: the re-run searches')]),
    ("a person's step claims GREG needs a grant",
     [(B, '            "required_authority": _none("GREG asks for no grant;',
       '            "required_authority": ("a grant: GREG asks for no grant;')]),
    ("a capability blocker's named capability is not offered for attach",
     [(B, "is verified, or revise or abandon the mission\" if named_cid else",
       "is verified, or revise or abandon the mission\" if False else")]),
    ("a paused mission's next move hides the pause",
     [(B, "    if m.paused:", "    if False:")]),
    ("the CLI ignores --mission",
     [("greg/cli.py", "open_blockers(journal, home=home, mission_id=args.mission)",
       "open_blockers(journal, home=home)")]),
    ("the morning report drops the blockers",
     [("greg/tribunal.py", '    report["blockers"] = blockers.open_blockers(journal, engine=engine)\n', "")]),
    ("Mission Control drops the blockers",
     [("greg/mission_control.py", '"sandbox_integration": sandbox, "blockers": blocked,',
       '"sandbox_integration": sandbox,')]),
]


def _purge(repo: Path) -> None:
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _run(repo: Path) -> subprocess.CompletedProcess:
    _purge(repo)
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", TESTS],
                          cwd=repo, env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=900)


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-typed-blockers-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        originals = {f: (repo / f).read_text() for f in {f for _n, edits in MUTANTS for f, _o, _w in edits}}
        baseline = _run(repo)
        if baseline.returncode != 0:
            print("BASELINE_FAILS\n" + baseline.stdout[-3000:])
            return 1
        print("BASELINE passes")
        for name, edits in MUTANTS:
            texts = dict(originals)
            if any(texts[f].count(old) != 1 for f, old, _new in edits):
                print("STALE", name)
                invalid += 1
                continue
            for f, old, new in edits:
                texts[f] = texts[f].replace(old, new)
            for f, text in texts.items():
                (repo / f).write_text(text)
            try:
                run = _run(repo)
            finally:
                for f, text in originals.items():
                    (repo / f).write_text(text)
            caught = (run.returncode == 1 and f"FAILED {TESTS}::" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            failed = [line.split("::", 1)[1].split(" ")[0] for line in run.stdout.splitlines()
                      if line.startswith(f"FAILED {TESTS}::")]
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name, *(f"by {failed[0]}",) if failed else ())
            invalid += not caught
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} mutants caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
