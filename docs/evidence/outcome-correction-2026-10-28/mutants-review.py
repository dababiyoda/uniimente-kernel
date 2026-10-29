"""Each mutant removes one safeguard added by the review fixes (S1-S10); the resolution unit tests must catch it.

Usage: python -B mutants-review.py REPO_ROOT > mutants-review.txt

A mutant counts as CAUGHT only when at least one test FAILS on an assertion or an error inside a test. A mutant whose
target text is missing or occurs more than once, whose mutated file does not compile, or whose run fails without a
FAILED test (for example a collection error) is INVALID: it tested nothing. The unmutated tree must pass first.
Bytecode is disabled and __pycache__ under greg/ and tests/ is purged before every run.
(Second review of #219, R3: the first version of this gate counted any non-zero exit as CAUGHT, and N9 matched only
the start of its line, so it was recorded as caught although the mutated file did not compile.)
"""
import hashlib, os, platform, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); F = ROOT / "greg/cognition/settlement.py"
ORIG = F.read_text()
MUTANTS = {
 "N1 S1 signed body not compared": ('\n                or not _signed_body_matches(data, command["body"], ("receipt", "resolves", "accept"))):', '):'),
 "N2 S1 one signed command reused": ('command is None or data["command_digest"] in seen', 'command is None'),
 "N3 S2 any resolution adjudicates": ('held_by_acceptance = any(e.event_id in accepted for e in live)', 'held_by_acceptance = applied is not None'),
 "N4 S2 partial invalidation accepted": ('        if standing:\n            raise', '        if False:\n            raise'),
 "N5 S3 dedupe against rejected facts": ('live = [e for e in existing if ruling.get(e.event_id, True)]', 'live = existing'),
 "N6 S3 one fact per receipt and value": ('key = receipt if not existing else [receipt, "fact", source, repr(realized), len(existing)]', 'key = receipt if not existing else [receipt, "fact", repr(realized)]'),
 "N7 S4 journal order wins": ('key=lambda item: (item[0], item[1])', 'key=lambda item: item[1]'),
 "N8 S5 succeeded only when prior is None": ('        if outcome.get("answer_version") and _base_identity(outcome) in legacy:', '        if prior is None and outcome.get("answer_version") and _base_identity(outcome) in legacy:'),
 "N9 S6 failed check hidden by dispute": ('        if not outcome["correct"]:        # the signed check failed', '        if False:        # the signed check failed'),
 "N10 S7 unsettleable dispute weighed": ('        if row["mission_id"] not in settling:', '        if False:'),
 "N11 S8 Laplace flips ignored": ('            if min(laplace) < other_mean < max(laplace):', '            if False:'),
 "N12 S9 unsigned fact eligible (replay)": ('(accept in named and accept in signed_facts', '(accept in named'),
 "N13 S9 unsigned fact eligible (row)": ('"eligible_to_accept": e.event_id in signed_facts\n                and', '"eligible_to_accept": True\n                and'),
 "N14 S10 engine label hashed": ('if k not in ANSWER_PROVENANCE_FIELDS}', 'if True}'),
}
TESTS = ["tests/unit/test_greg_outcome_resolution.py", "tests/unit/test_greg_pending_construction_realization.py",
         "tests/unit/test_greg_outcome_resolution_signed.py"]
COMMAND = [sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS]
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def purge_bytecode():
    for top in ("greg", "tests"):
        for cache in (ROOT / top).rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)


def run():
    purge_bytecode()
    r = subprocess.run(COMMAND, cwd=ROOT, capture_output=True, text=True, env=ENV)
    failing = [l.split("::")[-1].split(" ")[0] for l in r.stdout.splitlines() if l.startswith("FAILED")]
    return r, failing


head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
dirty = subprocess.run(["git", "status", "--porcelain", "--", "greg", "tests"], cwd=ROOT, capture_output=True,
                       text=True).stdout.strip()
print(f"git rev-parse HEAD: {head}; greg/ and tests/ {'DIRTY' if dirty else 'clean'}")
print(f"python {platform.python_version()}; command: {' '.join(['python', *COMMAND[1:]])}")
print(f"sha256 greg/cognition/settlement.py: {sha256(F)}")
for t in TESTS:
    print(f"sha256 {t}: {sha256(ROOT / t)}")
rows = []
try:
    base, failing = run()
    tail = (base.stdout.strip().splitlines() or [""])[-1]
    print(f"baseline (no mutant): rc={base.returncode} {tail}")
    if base.returncode != 0:
        sys.exit("baseline fails: no mutant result would mean anything")
    for name, (old, new) in MUTANTS.items():
        if ORIG.count(old) != 1:
            rows.append(f"INVALID {name}: target occurs {ORIG.count(old)} times")
            print(rows[-1], flush=True)
            continue
        mutated = ORIG.replace(old, new)
        try:
            compile(mutated, str(F), "exec")
        except SyntaxError as exc:
            rows.append(f"INVALID {name}: the mutated file does not compile ({exc.msg}, line {exc.lineno})")
            print(rows[-1], flush=True)
            continue
        F.write_text(mutated)
        r, failing = run()
        if r.returncode == 0:
            rows.append(f"MISSED  {name}: []")
        elif failing:
            rows.append(f"CAUGHT  {name}: {failing[:1]}")
        else:
            tail = (r.stdout.strip().splitlines() or [""])[-1]
            rows.append(f"INVALID {name}: rc={r.returncode} with no FAILED test ({tail})")
        print(rows[-1], flush=True)
finally:
    F.write_text(ORIG)
    purge_bytecode()
valid = [r for r in rows if not r.startswith("INVALID")]
print(f"{sum(r.startswith('CAUGHT') for r in rows)} of {len(valid)} valid mutants caught; "
      f"{len(rows) - len(valid)} invalid; {sum(r.startswith('MISSED') for r in rows)} missed")
