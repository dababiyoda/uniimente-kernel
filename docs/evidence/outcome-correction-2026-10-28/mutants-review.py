"""Each mutant removes one safeguard added by the review fixes (S1-S10, F1-F8 of the second review of #219, then the
fixes for the review of #221); the resolution unit tests must catch it.

Usage: python -B mutants-review.py REPO_ROOT > mutants-review.txt

A mutant counts as CAUGHT only when at least one test FAILS on an assertion or an error inside a test. A mutant whose
target text is missing or occurs more than once, whose mutated file does not compile, whose run fails without a FAILED
test (for example a collection error), or whose run exceeds the time limit is INVALID: it tested nothing.

The gate refuses to run unless git works, greg/, tests/ and this script are unmodified, and every target file equals
HEAD's; the unmutated tests must then pass. It records HEAD and the sha256 of each target file and each test file (not
of every module the tests import). Bytecode is disabled and __pycache__ under greg/ and tests/ is purged before every
run. Each mutant is written atomically, and every target file is restored on normal exit, on an exception and on
SIGINT, SIGTERM or SIGHUP; the pytest child's process group is killed with it.
(Second review of #219, R3: the first version counted any non-zero exit as CAUGHT, and N9 matched only the start of
its line, so it was recorded as caught although the mutated file did not compile. A check of this branch then found
that SIGTERM left a mutant in the tree and that a dirty tree was only labelled, not refused. At #221, N6 and N11 were
retargeted to the rewritten fact key and Laplace check, N15-N24 cover F1-F8, and the review-2 test file was added.
After the fixes for the review of #221, N11, N17, N18 and N20 were retargeted, N25-N36 cover those fixes, a mutant may
name a target file other than settlement.py, and the review-3 test file was added.)
"""
import hashlib, os, platform, shutil, signal, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve()
SETTLEMENT = "greg/cognition/settlement.py"
SCRIPT = Path(__file__).resolve()
# name -> (old, new) in settlement.py, or (target file, old, new)
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
 "N11 S8 Laplace flips ignored": ('            if lo <= o_hi and o_lo <= hi:', '            if False:'),
 "N12 S9 unsigned fact eligible (replay)": ('(accept in named and accept in signed_facts', '(accept in named'),
 "N13 S9 unsigned fact eligible (row)": ('"eligible_to_accept": e.event_id in signed_facts\n                and', '"eligible_to_accept": True\n                and'),
 "N14 S10 engine label hashed": ('if k not in ANSWER_PROVENANCE_FIELDS}', 'if True}'),
 # Second review of #219 (F1-F8), at #221
 "N15 F1 old answer version not re-derived": ('        current = _current_answer_version(payload, journal)\n', '        current = None\n'),
 "N16 F2 Holm over pairs only": ('        families = [c for size in range(1, len(tested) + 1) for c in combinations(tested, size)]',
                                 '        families = [(m,) for m in tested]'),
 "N17 F3 unsettled fit not compared": ('        others.append(("an unsettled co-eligible fit", UNSETTLED_LAPLACE, UNSETTLED_LAPLACE))', '        pass'),
 "N18 F3 a tie at a bound ignored": ('            if lo <= o_hi and o_lo <= hi:', '            if lo < o_hi and o_lo < hi:'),
 "N19 F4 string order of issued_at": ('out.append((_instant(command["issued_at"]), position, event))', 'out.append((command["issued_at"], position, event))'),
 "N20 F4 older-signed overlap not refused": ('            if overlap and prior.payload["command_digest"] != command_digest and _instant(prior_at) > _instant(own):',
                                            '            if False:'),
 "N21 F5 unsigned fact absorbs a signed report": ('\n                 and (not command_digest or e.payload.get("command_digest") == command_digest\n                      or e.event_id in signed_facts)), None)',
                                                  '), None)'),
 "N22 F6 any principal resolves": (' for d, c in commands.items() if c.get("principal") == "founder"}', ' for d, c in commands.items()}'),
 "N23 F7 omitted source not defaulted": ('{"source": "founder_reported",       # Body.apply\'s default (F7)\n                                                 **signed', '{**signed'),
 "N24 F8 memo misses a new founder record": ('records[seen - 1].hash == tail \\\n                    and not any(_founder_record(r) for r in records[seen:]):', 'records[seen - 1].hash == tail:'),
 # The review of #221 (comment 6491739752), fixed on #221's branch
 "N25 F2-a a walk limit read as a hold": ('        reasons += preference + limits', '        reasons += preference'),
 "N26 F2-b the two extremes only": ('    return [(n, k)] + [(n + d, k + j) for j in range(d + 1)]', '    return [(n + d, k), (n + d, k + d)]'),
 "N27 F2-c other disputed methods held (preference)": ('    others = sorted(m for m in joint if m != method and m in tested)', '    others = []'),
 "N28 F2-c other disputed methods held (Laplace)": ('        others += [(other, *laplace(other)) for other in sorted(states) if other != method]',
                                                   '        others += [(other, Fraction(counts.get(other, (0, 0))[1] + 1, counts.get(other, (0, 0))[0] + 2),'
                                                   ' Fraction(counts.get(other, (0, 0))[1] + 1, counts.get(other, (0, 0))[0] + 2))'
                                                   ' for other in sorted(states) if other != method]'),
 "N29 F2-d a demoted fit tested as first": ('        eligible.sort(key=lambda r: 1 if r["demoted"] else 0)        # _rank\'s leading key; stable otherwise',
                                           '        pass'),
 "N30 F2-f the raw preferred value": ('        return (_settled_preference(eligible, world) or {}).get("preferred") or top',
                                      '        return (_settled_preference(eligible, world) or {}).get("preferred")'),
 "N31 F1-a shadowed chain heads left live": ('        for shadow in chain_heads[:-1]:', '        for shadow in []:'),
 "N32 F1-a merge closures not counted as superseding": ('    superseded = {e.payload.get("supersedes") for e in every}',
                                                        '    superseded = {e.payload.get("supersedes") for e in every if not e.payload.get("merged_into")}'),
 "N33 F1-a merged rows read as links": ('        if data.get("merged_into"):       # a closed duplicate chain (F1-a): the merged chain carries the link\n            continue\n',
                                        ''),
 "N34 G4-d an equal stamp refused": ('_instant(prior_at) > _instant(own):', '_instant(prior_at) >= _instant(own):'),
 "N35 F7-a a closed mission read as pending a closure": ('    if terminal:\n', '    if False:\n'),
 "N36 G4-a raw stamp as the inbox name": ("greg/body.py", '    return instant(issued_at).astimezone(timezone.utc).strftime("%Y-%m-%dT%H%M%S.%fZ")',
                                          '    return issued_at.replace(":", "")'),
}
MUTANTS = {name: (spec if len(spec) == 3 else (SETTLEMENT, *spec)) for name, spec in MUTANTS.items()}
TARGETS = sorted({path for path, _, _ in MUTANTS.values()})
TESTS = ["tests/unit/test_greg_outcome_resolution.py", "tests/unit/test_greg_pending_construction_realization.py",
         "tests/unit/test_greg_outcome_resolution_signed.py", "tests/unit/test_greg_outcome_resolution_review2.py",
         "tests/unit/test_greg_outcome_resolution_review3.py"]
COMMAND = [sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS]
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
TIME_LIMIT = 1800  # seconds per run; the unmutated set takes about six minutes


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"refused: git {' '.join(args)} failed ({r.stderr.strip()})")
    return r.stdout


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


MODES = {path: (ROOT / path).stat().st_mode for path in TARGETS}


def write(path, text):
    """Write one target file atomically, so an interruption never leaves a partly written file."""
    target = ROOT / path
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".mutant-", suffix=".py")
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    os.chmod(tmp, MODES[path])
    os.replace(tmp, target)


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
ORIG = {path: git("show", f"HEAD:{path}") for path in TARGETS}
for path in TARGETS:
    if (ROOT / path).read_text() != ORIG[path]:
        sys.exit(f"refused: the working {path} differs from HEAD's")
print(f"git rev-parse HEAD: {head}; greg/, tests/ and {script_path} unmodified")
print(f"python {platform.python_version()}; command: {' '.join(['python', *COMMAND[1:]])}")
for path in TARGETS:
    print(f"sha256 {path}: {sha256(ROOT / path)}")
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
    for name, (path, old, new) in MUTANTS.items():
        original = ORIG[path]
        if original.count(old) != 1:
            rows.append(f"INVALID {name}: target occurs {original.count(old)} times in {path}")
            print(rows[-1], flush=True)
            continue
        mutated = original.replace(old, new)
        try:
            compile(mutated, str(ROOT / path), "exec")
        except SyntaxError as exc:
            rows.append(f"INVALID {name}: the mutated {path} does not compile ({exc.msg}, line {exc.lineno})")
            print(rows[-1], flush=True)
            continue
        write(path, mutated)
        try:
            result, failing = run()
        finally:
            write(path, original)
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
    for path in TARGETS:
        write(path, ORIG[path])
    purge_bytecode()
valid = [r for r in rows if not r.startswith("INVALID")]
print(f"{sum(r.startswith('CAUGHT') for r in rows)} of {len(valid)} valid mutants caught; "
      f"{len(rows) - len(valid)} invalid; {sum(r.startswith('MISSED') for r in rows)} missed")
