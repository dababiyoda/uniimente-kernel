"""Each safeguard of the capability readiness ladder (greg/readiness.py) must fail a behavioral test when removed.

Every mutant runs in a scratch copy of the repository with ``python -B`` and PYTHONDONTWRITEBYTECODE=1, after every
``__pycache__`` in the copy is purged, so no compiled file of an earlier mutant (or of the original) can stand in for
the mutated source. The unmutated copy must pass first; a mutant whose text no longer occurs once is STALE.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TARGET = "greg/readiness.py"
TESTS = "tests/unit/test_greg_readiness.py"
LATER = '    later = [r for r in rows if r[1] in ("REFUTED", "INEFFECTIVE") and r[0] > last[0]]'
OPEN = '            open_ = m.status == "ACTIVE" and not m.paused and now < _instant(m.cone.horizon)'
MUTANTS = [
    ("a later refutation is ignored", [(LATER, "    later = []")]),
    ("a later REFUTED appraisal is not counted", [(LATER, LATER.replace('("REFUTED", "INEFFECTIVE")',
                                                                        '("INEFFECTIVE",)'))]),
    ("a later ineffective routing verdict is not counted", [(LATER, LATER.replace('("REFUTED", "INEFFECTIVE")',
                                                                                  '("REFUTED",)'))]),
    ("an earlier refutation outlives a later VERIFIED", [(LATER, LATER.replace(" and r[0] > last[0]", ""))]),
    ("a verified failure closure reads as a success",
     [('verdict, mid = a.payload.get("verdict"), a.payload.get("mission_id")',
       'verdict, mid = str(a.payload.get("verdict")).replace("_UNMET", ""), a.payload.get("mission_id")')]),
    ("an appraisal judges every mission's receipts",
     [("judged = {r for pos, r in done.get(mid, ()) if pos < until}",
       "judged = {r for rows in done.values() for pos, r in rows if pos < until}")]),
    ("a declared credential handle is not required",
     [("    missing = [h for h in declared if h not in handles]", "    missing = []")]),
    ("a credential value reaches the evidence",
     [("        handles = set(secrets.names())",
       "        handles = {n: secrets.resolve(n, declared=(n,)) for n in secrets.names()}"),
      ('    evidence = [{"kind": "stored_handle", "ref": h} for h in present]',
       '    evidence = [{"kind": "stored_handle", "ref": h, "value": handles[h]} for h in present]')]),
    ("a closed mission still grants", [(OPEN, OPEN.replace('m.status == "ACTIVE" and ', ""))]),
    ("a paused mission still grants", [(OPEN, OPEN.replace(" and not m.paused", ""))]),
    ("an expired horizon still grants", [(OPEN, OPEN.replace(" and now < _instant(m.cone.horizon)", ""))]),
    ("the cone's consequence ceiling is ignored",
     [("        if _rank(manifest.consequence_class) > _rank(m.cone.max_consequence_class):", "        if False:")]),
    ("the cone's targets are ignored",
     [("        if not any(_may_target(t, manifest.target_prefix) for t in m.cone.targets):", "        if False:")]),
    ("an unattached capability is granted",
     [('    if state != "ATTACHED":\n        return _rung(MISSING, grants + lineage',
       '    if False:\n        return _rung(MISSING, grants + lineage')]),
    ("a refused invocation counts as exercise",
     [("    positive = [h for h, ok in mine if ok]", "    positive = [h for h, ok in mine]")]),
    ("installation is not checked", [("    ok, why = manifest.available()", '    ok, why = True, "available"')]),
    ("a pinned distribution version is not checked", [("        if pinned and found != pinned:", "        if False:")]),
    ("capabilities Genesis registered are left out",
     [('            if cid in BUILTINS or not str(manifest.get("provider", "")).startswith(FORMED):',
       "            if True:")]),
    ("recorded lifecycle state changes are ignored",
     [('            registry.set_state(data["capability_id"], data["state"])', "            pass")]),
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
    with tempfile.TemporaryDirectory(prefix="greg-readiness-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        path = repo / TARGET
        original = path.read_text()
        baseline = _run(repo)
        if baseline.returncode != 0:
            print("BASELINE_FAILS\n" + baseline.stdout[-3000:])
            return 1
        print("BASELINE passes")
        for name, edits in MUTANTS:
            text = original
            if any(text.count(old) != 1 for old, _new in edits):
                print("STALE", name)
                invalid += 1
                continue
            for old, new in edits:
                text = text.replace(old, new)
            path.write_text(text)
            try:
                run = _run(repo)
            finally:
                path.write_text(original)
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
