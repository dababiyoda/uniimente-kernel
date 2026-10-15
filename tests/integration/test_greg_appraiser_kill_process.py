"""Mission H (fault recovery), acceptance gap H.G7: the separate-process appraiser is interrupted mid-appraisal.

A real Body process runs the canonical main loop (Body.run, what `greg run` runs) and closes a founder-signed
mission. Its closure is then appraised by the separate appraiser process (``python -m greg.appraisal``). The
driver replaces only that child with a stand-in that reads the Body's request and then either runs the real
appraiser or stops inside the appraisal, where it is interrupted three ways:

- SIGKILL after it read the request and before it wrote a verdict;
- SIGKILL after it wrote all but the last byte of a real VERIFIED verdict (a partial verdict on its stdout);
- the Body's own appraisal timeout, which kills it (shortened by the driver; the Body's default is 120 s).

What must hold: no mission.appraised VERIFIED is recorded from an interrupted run (the partial VERIFIED bytes
included); the Body stays up (a hung appraiser does not crash it); each interrupted run is recorded as one
unavailable attempt and the closure is appraised again on a later tick; after APPRAISAL_ATTEMPTS interrupted
runs one final UNAVAILABLE appraisal is recorded and no further appraiser runs; and when a later run completes,
its real verdict (VERIFIED) is the one appraisal recorded. A last case kills the Body itself while its appraiser
runs: the restarted Body appraises the closure again and records the one real verdict.

The founder key is a per-test Ed25519 key, not Alfonso's; the stand-in appraiser is a test double that runs the
real ``greg.appraisal.appraise`` whenever it is not interrupted.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from greg.body import APPRAISAL_ATTEMPTS, observe
from tests.greg_fixtures import drop, make_body, mission, note_check, signed, workspace, write_strategy

ROOT = Path(__file__).resolve().parents[2]
MISSION = "m:appraised-note"

DRIVER = '''
import subprocess, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from greg.body import Body

home, stub, timeout = Path(sys.argv[2]), sys.argv[3], float(sys.argv[4])
spawn = subprocess.run


def run(argv, *args, **kwargs):
    if list(argv[1:]) == ["-m", "greg.appraisal"]:   # the Body's separate-process appraiser, and nothing else
        argv = [argv[0], stub]                      # this test's stand-in for it (runs the real one unless stopped)
        kwargs["timeout"] = timeout
    return spawn(argv, *args, **kwargs)


subprocess.run = run
sys.exit(Body(home).run(tick_seconds=0.2))
'''

STUB = '''
import json, os, sys, time
from pathlib import Path

control = Path(__file__).resolve().parent
n = len(list(control.glob("run-*.request"))) + 1     # runs are sequential: the Body waits for each one


def mark(name, text):
    tmp = control / ("." + name)
    tmp.write_text(text)
    tmp.replace(control / name)


raw = sys.stdin.read()
mark(f"run-{n}.request", raw)
plan = (control / "plan").read_text().split()
mode = plan[min(n, len(plan)) - 1]
if mode in ("real", "partial"):
    from greg.appraisal import appraise
    out = json.dumps(appraise(json.loads(raw)), sort_keys=True)
    if mode == "real":
        sys.stdout.write(out)
        sys.exit(0)
    sys.stdout.write(out[:-1])                       # every byte of a real verdict but its closing brace
    sys.stdout.flush()
    mark(f"run-{n}.partial", out[:-1])
mark(f"run-{n}.pid", str(os.getpid()))
time.sleep(3600)                                    # interrupted here: SIGKILL, or the Body's timeout
'''


def start(tmp_path: Path, home: Path, stub: Path, timeout: float) -> subprocess.Popen:
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    return subprocess.Popen([sys.executable, str(driver), str(ROOT), str(home), str(stub), str(timeout)], cwd=ROOT,
                            stdout=(tmp_path / "body.log").open("a"), stderr=subprocess.STDOUT,
                            env={**os.environ, "PYTHONPATH": str(ROOT)})


def events(home: Path, prefix: str) -> list[dict]:
    with observe(home, actor="spiffe://uniimente.internal/greg/appraiser-kill-test") as journal:
        return [e.payload for e in journal.replay(prefix)]


def wait_for(predicate, *, timeout=60, what="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
        except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError):
            value = None
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {what}")


def runs(control: Path) -> int:
    return len(list(control.glob("run-*.request")))


def kill(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def setup(tmp_path: Path, plan: list[str]):
    home, key, body_id, _ = make_body(tmp_path)
    control = tmp_path / "appraiser"
    control.mkdir()
    (control / "stub.py").write_text(STUB)
    (control / "plan").write_text(" ".join(plan))
    note = workspace(home, MISSION) / "n.txt"
    drop(home, signed(key, body_id, "MISSION", mission(
        MISSION, checks=[note_check("n", note, "appraise me")], strategies=[write_strategy("w", "n.txt", "appraise me",
                                                                                          ["n"])],
        capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:n.txt"))))
    return home, control


def interrupt(control: Path, n: int, interruption: str) -> None:
    """Interrupt appraiser run ``n`` inside its appraisal (the timeout case: wait while the Body kills it)."""
    if interruption == "timeout":
        wait_for(lambda: runs(control) >= n, what=f"appraiser run {n}")
        return
    pid = int(wait_for(lambda: (control / f"run-{n}.pid").read_text(), what=f"appraiser run {n} inside its appraisal"))
    if interruption == "sigkill-mid-verdict":
        partial = (control / f"run-{n}.partial").read_text()
        assert '"verdict": "VERIFIED"' in partial and not partial.endswith("}"), "a real VERIFIED verdict, cut short"
    kill(pid)


@pytest.mark.parametrize("recovers", [True, False], ids=["a-later-run-completes", "no-run-completes"])
@pytest.mark.parametrize("interruption", ["sigkill-before-verdict", "sigkill-mid-verdict", "timeout"])
def test_an_interrupted_appraisal_is_retried_within_a_bound_and_never_fabricates_a_verdict(tmp_path, interruption,
                                                                                         recovers):
    stopped = "partial" if interruption == "sigkill-mid-verdict" else "hang"
    home, control = setup(tmp_path, [stopped, "real"] if recovers else [stopped])
    body = start(tmp_path, home, control / "stub.py", 1.0 if interruption == "timeout" else 120.0)
    try:
        for n in range(1, (1 if recovers else APPRAISAL_ATTEMPTS) + 1):
            interrupt(control, n, interruption)
            if n < APPRAISAL_ATTEMPTS and not recovers:
                wait_for(lambda: len(events(home, "mission.appraisal_unavailable")) >= n, what=f"attempt {n} recorded")
        [appraisal] = wait_for(lambda: events(home, "mission.appraised"), what="the closure's appraisal")
        time.sleep(1.5)                                  # ~7 more ticks: nothing more is appraised
        assert body.poll() is None, "an interrupted appraiser does not take the Body down"
        final = events(home, "mission.appraised")
        attempts = events(home, "mission.appraisal_unavailable")
        assert len(events(home, "mission.achieved")) == 1
    finally:
        body.send_signal(signal.SIGTERM)
        try:
            body.wait(timeout=30)
        except subprocess.TimeoutExpired:
            body.kill()
        for marker in control.glob("run-*.pid"):
            kill(int(marker.read_text()))

    assert final == [appraisal], "exactly one appraisal of the closure"
    requests = [json.loads((control / f"run-{n}.request").read_text()) for n in range(1, runs(control) + 1)]
    assert {r["mission_id"] for r in requests} == {MISSION}
    if recovers:
        assert runs(control) == 2, "one interrupted run, then exactly one re-appraisal on a later tick"
        assert [a["attempt"] for a in attempts] == [1]
        assert appraisal["verdict"] == "VERIFIED"           # the real appraiser's own verdict, re-derived
        assert all(appraisal["checks"][c] for c in ("founder_signature_verified", "checks_rederived_from_receipts",
                                                     "world_reobserved", "exactly_once"))
    else:
        assert runs(control) == APPRAISAL_ATTEMPTS, "the re-appraisals stop at the bound"
        assert [a["attempt"] for a in attempts] == list(range(1, APPRAISAL_ATTEMPTS + 1))
        assert appraisal["verdict"] == "UNAVAILABLE" and appraisal["checks"] == {}
        assert appraisal["attempts"] == APPRAISAL_ATTEMPTS and len(appraisal["findings"]) == APPRAISAL_ATTEMPTS
    assert all(a["mission_id"] == MISSION and a["why"] for a in attempts)
    with observe(home) as journal:
        assert journal.ledger.verify_chain()[0]


def test_a_body_killed_while_its_appraiser_runs_appraises_the_closure_again_after_restart(tmp_path):
    home, control = setup(tmp_path, ["hang", "real"])
    body = start(tmp_path, home, control / "stub.py", 120.0)
    try:
        orphan = int(wait_for(lambda: (control / "run-1.pid").read_text(), what="the appraiser inside its appraisal"))
        body.send_signal(signal.SIGKILL)                 # the Body dies; its appraiser is left running
        body.wait(timeout=20)
        assert events(home, "mission.appraised") == [] and events(home, "mission.appraisal_unavailable") == []
        kill(orphan)
        body = start(tmp_path, home, control / "stub.py", 120.0)
        [appraisal] = wait_for(lambda: events(home, "mission.appraised"), what="the appraisal after restart")
        time.sleep(1.5)
        assert body.poll() is None
        final = events(home, "mission.appraised")
    finally:
        body.send_signal(signal.SIGTERM)
        try:
            body.wait(timeout=30)
        except subprocess.TimeoutExpired:
            body.kill()
        for marker in control.glob("run-*.pid"):
            kill(int(marker.read_text()))

    assert final == [appraisal] and appraisal["verdict"] == "VERIFIED"
    assert runs(control) == 2 and events(home, "body.recovered")
    assert events(home, "mission.appraisal_unavailable") == [], "a run the Body never saw end is not an attempt"
