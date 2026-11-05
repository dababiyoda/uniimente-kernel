"""Each safeguard of the post-outcome disposition review (directive section 22, S22.A4) must fail its unit tests when removed.

    python scripts/ci/check_capability_disposition_mutants.py

Mutants are applied to greg/disposition.py and greg/body.py in a scratch copy of the repository, never to the working
tree; the copy runs without bytecode and its __pycache__ is purged before each mutant. A mutant is caught only when
tests/unit/test_greg_capability_disposition.py reports a FAILED test (an import or collection error does not count). Exit status
1 if any mutant survives or no longer applies.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
DISPOSITION = "greg/disposition.py"
BODY = "greg/body.py"
TESTS = "tests/unit/test_greg_capability_disposition.py"
MUTANTS = [
    (DISPOSITION, "demotion is not the body's own rule (no ten-outcome floor)",
     'return _settled_inhibition(row["settled"], row["correct"]) is not None', 'return row["wilson95"][1] < 0.5'),
    (DISPOSITION, "an earlier implementation is never gone back to", '        if standing:', '        if False:'),
    (DISPOSITION, "a detached earlier implementation counts as standing",
     'e["state"] not in ("DETACHED", "QUARANTINED")', 'e["state"] not in ("QUARANTINED",)'),
    (DISPOSITION, "a quarantined earlier implementation counts as standing",
     'e["state"] not in ("DETACHED", "QUARANTINED")', 'e["state"] not in ("DETACHED",)'),
    (DISPOSITION, "an earlier implementation wrong more often than right counts as standing",
     'and 2 * e["correct"] >= e["settled"] and not _demoted(e)', 'and not _demoted(e)'),
    (DISPOSITION, "a fault in service does not stop a RETAIN",
     'if k < n or row["in_service_quarantines"]:', 'if k < n:'),
    (DISPOSITION, "certificate-only answers count once the world judges the capability",
     'counted, tier = (judged, "world") if judged else', 'counted, tier = (settled, "world") if judged else'),
    (DISPOSITION, "a request id is reused when the evidence returns",
     '{"capability_id": cid, "ordinal": ordinal, "digest": digest}', '{"capability_id": cid, "digest": digest}'),
    (DISPOSITION, "an orphaned or superseded open ask is not withdrawn",
     '            if rid != request_id:\n                _withdraw(', '            if False:\n                _withdraw('),
    (DISPOSITION, "a detach leaves its disposition ask open",
     '            for rid in open_ids:\n                _withdraw(journal, rid, f"the founder detached {cid}", now)',
     '            pass'),
    (DISPOSITION, "an ask made moot by a detach is not asked again",
     'keep, asking = None, latest is None or latest[2] == "withdrawn"', 'keep, asking = None, latest is None'),
    (DISPOSITION, "an answered ask is asked again for the same disposition",
     'keep, asking = None, latest is None or latest[2] == "withdrawn"', 'keep, asking = None, True'),
    (DISPOSITION, "an unchanged disposition asks again",
     '        elif open_ids:\n            keep, asking = open_ids[-1], False',
     '        elif open_ids:\n            keep, asking = None, True'),
    (DISPOSITION, "a later registration does not reset the state",
     '            state[cid] = p.get("state", "VERIFIED")\n', '            state.setdefault(cid, p.get("state", "VERIFIED"))\n'),
    (DISPOSITION, "a quarantined capability is reviewed", '        if row["state"] == "QUARANTINED":\n',
     '        if False:\n'),
    (DISPOSITION, "a capability with faults but no outcome is not reviewed",
     'if not row["settled"] and not row["in_service_quarantines"]:', 'if not row["settled"]:'),
    (DISPOSITION, "an installed binary is not a formed capability",
     'FORMED = ("built:", "installed:", "composed:")', 'FORMED = ("built:", "composed:")'),
    (BODY, "the body never reviews", '        disposition.propose(self.journal, now)', '        pass'),
]


def purge(repo: Path) -> None:
    for top in ("greg", "tests"):
        for cache in (repo / top).rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="capability-disposition-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
        for target, name, old, new in MUTANTS:
            path = repo / target
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            purge(repo)
            try:
                run = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", TESTS],
                                     cwd=repo, env=env, capture_output=True, text=True, timeout=900)
            finally:
                path.write_text(original)
            caught = (run.returncode == 1 and f"FAILED {TESTS}::" in run.stdout and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name, flush=True)
            invalid += not caught
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
