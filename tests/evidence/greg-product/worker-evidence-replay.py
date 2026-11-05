"""Replay real commits as worker output and record, per mutant, whether the commit's own tests kill it.

Usage: python3 replay_policies.py WT KERNEL OUT.jsonl SHA...   (WT = worktree holding greg/evidence_strength.py)
One JSON line per commit: discrimination, and for every policy the mutant labels with killed flags, so
policies and scorings can be compared offline from one set of test runs.
"""
import json, os, subprocess, sys, tempfile, time
from fnmatch import fnmatchcase
from pathlib import Path

WT, KERNEL, OUT, SHAS = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4:]
sys.path.insert(0, str(WT))
from greg import evidence_strength as es  # noqa: E402

POLICIES = ("all", "expressions", "none")
TIMEOUT = 300


def git(cwd, *a, check=True, text=True):
    p = subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, text=text)
    if check and p.returncode:
        raise RuntimeError(f"git {a[:3]}: {p.stderr[-300:]}")
    return p


def pytest(cwd, tests):
    t = time.monotonic()
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests], cwd=cwd,
                           capture_output=True, text=True, timeout=TIMEOUT,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = -1
    return rc, round(time.monotonic() - t, 1)


def clone(sha, dest):
    subprocess.run(["git", "clone", "-q", "--no-checkout", KERNEL, str(dest)], check=True)
    git(dest, "checkout", "-q", "--detach", sha)


for sha in SHAS:
    rec = {"sha": sha}
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="ev-") as tmp:
            tmp = Path(tmp)
            fresh, base = tmp / "fresh", tmp / "base"
            clone(sha, fresh); clone(sha + "^", base)
            names = git(fresh, "diff", "--name-only", sha + "^", sha).stdout.split()
            tests = [n for n in es.worker_tests(names) if (fresh / n).is_file()]
            rec["tests"] = tests
            if not tests:
                raise RuntimeError("no worker tests")
            rc_fresh, _ = pytest(fresh, tests)
            rec["fresh_rc"] = rc_fresh
            if rc_fresh != 0:
                raise RuntimeError(f"commit's own tests fail at the commit (rc {rc_fresh}): environment")
            patch = tmp / "c.patch"
            patch.write_bytes(git(fresh, "diff", "--binary", sha + "^", sha, text=False).stdout)
            include = [a for n in es.test_side(names) for a in ("--include", n)]
            ap = git(base, "apply", "--binary", *include, str(patch), check=False)
            if ap.returncode:
                rec["discrimination"] = "test hunks do not apply"
            else:
                rc_base, _ = pytest(base, tests)
                rec["base_rc"] = rc_base
            sources = [n for n in names if n.endswith(".py") and not fnmatchcase(n, es.TEST_SIDE)
                       and (fresh / n).is_file()]
            plan = {}
            for pol in POLICIES:
                items = []
                for name in sources:
                    lines = es.added_lines(git(fresh, "diff", "-U0", sha + "^", sha, "--", name).stdout)
                    src = (fresh / name).read_text()
                    for label, text in es.mutants(src, lines, max(0, es.MAX_MUTANTS - len(items)), constants=pol):
                        items.append((name, label, text))
                    if len(items) >= es.MAX_MUTANTS:
                        break
                plan[pol] = items
            # every unique (file, mutated text) runs once; also the full un-sampled 'all' universe per line
            results = {}
            for pol, items in plan.items():
                for name, label, text in items:
                    key = (name, text)
                    if key in results:
                        continue
                    path = fresh / name
                    orig = path.read_bytes()
                    try:
                        path.write_text(text)
                        rc, secs = pytest(fresh, tests)
                    finally:
                        path.write_bytes(orig)
                    results[key] = {"killed": rc != 0, "rc": rc, "seconds": secs}
            rec["policies"] = {pol: [{"file": n, "mutant": l, **results[(n, t)]} for n, l, t in items]
                               for pol, items in plan.items()}
    except Exception as exc:  # noqa: BLE001
        rec["error"] = str(exc)[:400]
    rec["seconds"] = round(time.monotonic() - started, 1)
    with OUT.open("a") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(sha, rec.get("error", "ok"), rec["seconds"], flush=True)
