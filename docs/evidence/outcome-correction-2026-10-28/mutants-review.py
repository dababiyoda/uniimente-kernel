"""Each mutant removes one safeguard added by the review fixes (S1-S10, then F1-F8 of the second review of #219); the
resolution unit tests must catch it.

Usage: python -B mutants-review.py REPO_ROOT > mutants-review.txt

A mutant counts as CAUGHT only when at least one test FAILS on an assertion or an error inside a test. A mutant whose
target text is missing or occurs more than once, whose mutated file does not compile, whose run fails without a FAILED
test (for example a collection error), or whose run exceeds the time limit is INVALID: it tested nothing.

The gate refuses to run unless git works, greg/, tests/ and this script are unmodified, and the working
settlement.py equals HEAD's; the unmutated tests must then pass. It records HEAD and the sha256 of settlement.py and
each test file (not of every module the tests import). Bytecode is disabled and __pycache__ under greg/ and
tests/ is purged before every run. Each mutant is written atomically, and settlement.py is restored on normal exit,
on an exception and on SIGINT, SIGTERM or SIGHUP; the pytest child's process group is killed with it.
(Second review of #219, R3: the first version counted any non-zero exit as CAUGHT, and N9 matched only the start of
its line, so it was recorded as caught although the mutated file did not compile. A check of this branch then found
that SIGTERM left a mutant in the tree and that a dirty tree was only labelled, not refused. At #221, N6 and N11 were
retargeted to the rewritten fact key and Laplace check, N15-N24 cover F1-F8, and the review-2 test file was added.)
"""
import hashlib, os, platform, shutil, signal, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); F = ROOT / "greg/cognition/settlement.py"
SCRIPT = Path(__file__).resolve()
MUTANTS = {
 "N1 S1 signed body not compared": ('\n                or not _signed_body_matches(data, command["body"], ("receipt", "resolves", "accept"))):', '):'),
 "N2 S1 one signed command reused": ('command is None or data["command_digest"] in seen', 'command is None'),
 "N3 S2 any resolution adjudicates": ('held_by_acceptance = any(e.event_id in accepted for e in live)', 'held_by_acceptance = applied is not None'),
 "N4 S2 partial invalidation accepted": ('        if standing:\n            raise', '        if False:\n            raise'),
 "N5 S3 dedupe against rejected facts": ('live = [e for e in existing if ruling.get(e.event_id, True)]', 'live = existing'),
 "N6 S3 one fact per receipt and value": ('[receipt, "fact", source, repr(realized), len(existing),\n', '[receipt, "fact", repr(realized),\n'),
 "N7 S4 journal order wins": ('key=lambda item: (item[0], item[1])', 'key=lambda item: item[1]'),
 "N8 S5 succeeded only when prior is None": ('        if outcome.get("answer_version") and _base_identity(outcome) in legacy:', '        if prior is None and outcome.get("answer_version") and _base_identity(outcome) in legacy:'),
 "N9 S6 failed check hidden by dispute": ('        if not outcome["correct"]:        # the signed check failed', '        if False:        # the signed check failed'),
 "N10 S7 unsettleable dispute weighed": ('        if row["mission_id"] not in settling:', '        if False:'),
 "N11 S8 Laplace flips ignored": ('            if lo <= mean <= hi:          # inclusive', '            if False:          # inclusive'),
 "N12 S9 unsigned fact eligible (replay)": ('(accept in named and accept in signed_facts', '(accept in named'),
 "N13 S9 unsigned fact eligible (row)": ('"eligible_to_accept": e.event_id in signed_facts\n                and', '"eligible_to_accept": True\n                and'),
 "N14 S10 engine label hashed": ('if k not in ANSWER_PROVENANCE_FIELDS}', 'if True}'),
 # Second review of #219 (F1-F8), at #221
 "N15 F1 old answer version not re-derived": ('        current = _current_answer_version(payload, journal)\n', '        current = None\n'),
 "N16 F2 Holm over pairs only": ('        families = [c for size in range(1, len(tested) + 1) for c in combinations(tested, size)]',
                                 '        families = [(m,) for m in tested]'),
 "N17 F3 unsettled fit not compared": ('        others.append(("an unsettled co-eligible fit", UNSETTLED_LAPLACE))', '        pass'),
 "N18 F3 a tie at a bound ignored": ('            if lo <= mean <= hi:', '            if lo < mean < hi:'),
 "N19 F4 string order of issued_at": ('out.append((_instant(command["issued_at"]), position, event))', 'out.append((command["issued_at"], position, event))'),
 "N20 F4 older-signed overlap not refused": ('            if overlap and prior.payload["command_digest"] != command_digest and _instant(prior_at) >= _instant(own):',
                                            '            if False:'),
 "N21 F5 unsigned fact absorbs a signed report": ('\n                 and (not command_digest or e.payload.get("command_digest") == command_digest\n                      or e.event_id in signed_facts)), None)',
                                                  '), None)'),
 "N22 F6 any principal resolves": (' for d, c in commands.items() if c.get("principal") == "founder"}', ' for d, c in commands.items()}'),
 "N23 F7 omitted source not defaulted": ('{"source": "founder_reported",       # Body.apply\'s default (F7)\n                                                 **signed', '{**signed'),
 "N24 F8 memo misses a new founder record": ('records[seen - 1].hash == tail \\\n                    and not any(_founder_record(r) for r in records[seen:]):', 'records[seen - 1].hash == tail:'),
}
TESTS = ["tests/unit/test_greg_outcome_resolution.py", "tests/unit/test_greg_pending_construction_realization.py",
         "tests/unit/test_greg_outcome_resolution_signed.py", "tests/unit/test_greg_outcome_resolution_review2.py"]
COMMAND = [sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS]
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
TIME_LIMIT = 900  # seconds per run; the unmutated set takes about a minute


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"refused: git {' '.join(args)} failed ({r.stderr.strip()})")
    return r.stdout


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


MODE = F.stat().st_mode


def write(text):
    """Write settlement.py atomically, so an interruption never leaves a partly written file."""
    fd, tmp = tempfile.mkstemp(dir=F.parent, prefix=".mutant-", suffix=".py")
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    os.chmod(tmp, MODE)
    os.replace(tmp, F)


def purge_bytecode():
    for top in ("greg", "tests"):
        for cache in (ROOT / top).rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)


def run():
    """Run the tests in their own process group; on a time-out or an interruption the whole group is killed."""
    purge_bytecode()
    proc = subprocess.Popen(COMMAND, cwd=ROOT, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=TIME_LIMIT)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return None, []
    except BaseException:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        raise
    failing = [l.split("::")[-1].split(" ")[0] for l in out.splitlines() if l.startswith("FAILED")]
    return (proc.returncode, out), failing


def on_signal(signum, frame):
    raise SystemExit(f"interrupted by signal {signum}")


head = git("rev-parse", "HEAD").strip()
script_path = SCRIPT.relative_to(ROOT) if SCRIPT.is_relative_to(ROOT) else SCRIPT
dirty = git("status", "--porcelain", "--", "greg", "tests", str(script_path)).strip()
if dirty:
    sys.exit(f"refused: greg/, tests/ or the gate itself is modified:\n{dirty}")
ORIG = git("show", f"HEAD:{F.relative_to(ROOT)}")
if F.read_text() != ORIG:
    sys.exit("refused: the working settlement.py differs from HEAD's")
print(f"git rev-parse HEAD: {head}; greg/, tests/ and {script_path} unmodified")
print(f"python {platform.python_version()}; command: {' '.join(['python', *COMMAND[1:]])}")
print(f"sha256 greg/cognition/settlement.py: {sha256(F)}")
for t in TESTS:
    print(f"sha256 {t}: {sha256(ROOT / t)}")
for signum in (signal.SIGTERM, signal.SIGHUP):
    signal.signal(signum, on_signal)
rows = []
try:
    base, failing = run()
    if base is None:
        sys.exit(f"baseline exceeded {TIME_LIMIT} s")
    tail = (base[1].strip().splitlines() or [""])[-1]
    print(f"baseline (no mutant): rc={base[0]} {tail}")
    if base[0] != 0:
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
        write(mutated)
        result, failing = run()
        if result is None:
            rows.append(f"INVALID {name}: the run exceeded {TIME_LIMIT} s")
        elif result[0] == 0:
            rows.append(f"MISSED  {name}: []")
        elif failing:
            rows.append(f"CAUGHT  {name}: {failing[:1]}")
        else:
            tail = (result[1].strip().splitlines() or [""])[-1]
            rows.append(f"INVALID {name}: rc={result[0]} with no FAILED test ({tail})")
        print(rows[-1], flush=True)
finally:
    write(ORIG)
    purge_bytecode()
valid = [r for r in rows if not r.startswith("INVALID")]
print(f"{sum(r.startswith('CAUGHT') for r in rows)} of {len(valid)} valid mutants caught; "
      f"{len(rows) - len(valid)} invalid; {sum(r.startswith('MISSED') for r in rows)} missed")
