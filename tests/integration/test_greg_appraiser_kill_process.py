"""Mission H (fault recovery), acceptance gap H.G7: the separate-process appraiser is interrupted mid-appraisal.

A real Body process runs the canonical main loop (Body.run, what `greg run` runs) and closes a founder-signed
mission. Its closure is then appraised by the separate appraiser process (``python -m greg.appraisal``). The
driver replaces only that child with a stand-in that runs the real appraiser or stops inside the appraisal. The
driver numbers each run and records its request before the stand-in starts, and gives the stand-in its mode, so
how a run ends never depends on how fast the machine is:

- SIGKILL after it read the request and before it wrote a verdict;
- SIGKILL after it wrote all but the last byte of a real VERIFIED verdict (a partial verdict on its stdout);
- SIGKILL after it wrote a whole, readable, real VERIFIED verdict (a killed run is no verdict, however complete
  its output looks);
- the Body's own appraisal timeout, which kills it: the stand-in never answers, and only that run is given a
  short timeout (the driver's; the Body's default is 120 s), so a later real appraisal runs with the default;
- exit 0 without a readable verdict: a verdict cut short, JSON that is no verdict, or nothing at all.

What must hold: no mission.appraised VERIFIED is recorded from an interrupted run (the partial and the whole
VERIFIED bytes included); the Body stays up (a hung appraiser does not crash it); each interrupted run is recorded
as one unavailable attempt saying how the run ended, and the closure is appraised again on a later tick; after
APPRAISAL_ATTEMPTS interrupted runs one final UNAVAILABLE appraisal is recorded and no further appraiser runs; and
when a later run completes, its real verdict (VERIFIED) is the one appraisal recorded. Attempts are counted per
closure: a standing mission whose first closure used two attempts still gets all of them for its second. A last
case kills the Body itself while its appraiser runs: the restarted Body appraises the closure again and records
the one real verdict. "Nothing more happens" is checked over a counted number of further ticks (heartbeats),
not over a stretch of wall-clock time.

The driver's clock is the real clock plus an offset that only the two-closure case moves forward (its wall clock
and its monotonic clock move together, so no host sleep is inferred). The founder key is a per-test Ed25519 key,
not Alfonso's; the stand-in appraiser is a test double that runs the real ``greg.appraisal.appraise`` whenever it
is not interrupted.
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
SHORT_TIMEOUT = 1.0                                     # given only to a run planned to be killed by the timeout

DRIVER = '''
import subprocess, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from greg.body import Body

home, control, short = Path(sys.argv[2]), Path(sys.argv[3]), float(sys.argv[4])
spawn = subprocess.run


def offset():                                       # seconds the test moved this Body's time forward
    try:
        return float((control / "clock").read_text())
    except FileNotFoundError:
        return 0.0


def mark(name, text):
    tmp = control / ("." + name)
    tmp.write_text(text)
    tmp.replace(control / name)


def run(argv, *args, **kwargs):
    if list(argv[1:]) == ["-m", "greg.appraisal"]:   # the Body's separate-process appraiser, and nothing else
        n = len(list(control.glob("run-*.request"))) + 1   # runs are sequential: the Body waits for each one
        mark(f"run-{n}.request", kwargs["input"])            # counted here, before the stand-in starts
        plan = (control / "plan").read_text().split()
        mode = plan[min(n, len(plan)) - 1]
        argv = [argv[0], str(control / "stub.py"), str(n), mode]
        if mode == "timeout":                       # only this run gets the short timeout; the rest keep the Body's
            kwargs["timeout"] = short
    return spawn(argv, *args, **kwargs)


subprocess.run = run
clock = lambda: datetime.now(timezone.utc) + timedelta(seconds=offset())
monotonic = lambda: time.monotonic() + offset()
sys.exit(Body(home, clock=clock, monotonic=monotonic).run(tick_seconds=0.2))
'''

STUB = '''
import json, os, sys, time
from pathlib import Path

control = Path(__file__).resolve().parent
n, mode = int(sys.argv[1]), sys.argv[2]


def mark(name, text):
    tmp = control / ("." + name)
    tmp.write_text(text)
    tmp.replace(control / name)


def verdict():
    from greg.appraisal import appraise
    return json.dumps(appraise(json.loads(raw)), sort_keys=True)


raw = sys.stdin.read()
if mode == "real":
    sys.stdout.write(verdict())
    sys.exit(0)
if mode == "unreadable":                            # exit 0: a verdict cut short, JSON that is no verdict, nothing
    sys.stdout.write([verdict()[:-1], "null", ""][(n - 1) % 3])
    sys.exit(0)
if mode in ("partial", "complete"):
    out = verdict()
    out = out[:-1] if mode == "partial" else out    # every byte of a real verdict but its closing brace, or all
    sys.stdout.write(out)
    sys.stdout.flush()
    mark(f"run-{n}.{mode}", out)
mark(f"run-{n}.pid", str(os.getpid()))
time.sleep(3600)                                    # interrupted here: SIGKILL, or the Body's timeout
'''

# How each interruption ends the stand-in's run, and what the Body must record as the reason.
MODES = {"sigkill-before-verdict": "hang", "sigkill-mid-verdict": "partial",
         "sigkill-after-whole-verdict": "complete", "timeout": "timeout", "exit-0-no-verdict": "unreadable"}
WHY = {"hang": "exited -9 without a verdict", "partial": "exited -9 without a verdict",
       "complete": "exited -9 without a verdict", "timeout": f"gave no verdict within {SHORT_TIMEOUT:g} s",
       "unreadable": "exited 0 without a readable verdict"}
KILLED = ("hang", "partial", "complete")               # the test SIGKILLs these inside their appraisal


def start(tmp_path: Path, home: Path, control: Path) -> subprocess.Popen:
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    return subprocess.Popen([sys.executable, str(driver), str(ROOT), str(home), str(control), str(SHORT_TIMEOUT)],
                            cwd=ROOT, stdout=(tmp_path / "body.log").open("a"), stderr=subprocess.STDOUT,
                            env={**os.environ, "PYTHONPATH": str(ROOT)})


def recorded(home: Path, prefix: str) -> list:
    with observe(home, actor="spiffe://uniimente.internal/greg/appraiser-kill-test") as journal:
        return journal.replay(prefix)


def events(home: Path, prefix: str) -> list[dict]:
    return [e.payload for e in recorded(home, prefix)]


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


def more_ticks(home: Path, count: int = 5) -> None:
    """Return once the Body wrote its heartbeat ``count`` more times (once per tick), however long that takes."""
    seen = set()

    def advanced():
        seen.add(json.loads((home / "heartbeat.json").read_text())["at"])
        return len(seen) > count
    wait_for(advanced, what=f"{count} more ticks of the Body")


def runs(control: Path) -> int:
    return len(list(control.glob("run-*.request")))


def kill(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def stop(body: subprocess.Popen, control: Path) -> None:
    body.send_signal(signal.SIGTERM)
    try:
        body.wait(timeout=30)
    except subprocess.TimeoutExpired:
        body.kill()
    for marker in control.glob("run-*.pid"):
        kill(int(marker.read_text()))


def move_clock(control: Path, seconds: float) -> None:
    tmp = control / ".clock"
    tmp.write_text(str(seconds))
    tmp.replace(control / "clock")


def setup(tmp_path: Path, plan: list[str], closure=None):
    home, key, body_id, _ = make_body(tmp_path)
    control = tmp_path / "appraiser"
    control.mkdir()
    (control / "stub.py").write_text(STUB)
    (control / "plan").write_text(" ".join(plan))
    note = workspace(home, MISSION) / "n.txt"
    drop(home, signed(key, body_id, "MISSION", mission(
        MISSION, checks=[note_check("n", note, "appraise me")], strategies=[write_strategy("w", "n.txt", "appraise me",
                                                                                          ["n"])],
        capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:n.txt"), closure=closure)))
    return home, control


def interrupt(control: Path, n: int, mode: str) -> None:
    """Interrupt appraiser run ``n`` inside its appraisal; a run the Body's timeout ends, or one that exits 0
    without a verdict, ends by itself."""
    if mode not in KILLED:
        wait_for(lambda: runs(control) >= n, what=f"appraiser run {n}")
        return
    pid = int(wait_for(lambda: (control / f"run-{n}.pid").read_text(), what=f"appraiser run {n} inside its appraisal"))
    if mode == "partial":
        partial = (control / f"run-{n}.partial").read_text()
        assert '"verdict": "VERIFIED"' in partial and not partial.endswith("}"), "a real VERIFIED verdict, cut short"
    if mode == "complete":
        assert json.loads((control / f"run-{n}.complete").read_text())["verdict"] == "VERIFIED", "a whole verdict"
    kill(pid)


@pytest.mark.parametrize("recovers", [True, False], ids=["a-later-run-completes", "no-run-completes"])
@pytest.mark.parametrize("interruption", list(MODES))
def test_an_interrupted_appraisal_is_retried_within_a_bound_and_never_fabricates_a_verdict(tmp_path, interruption,
                                                                                         recovers):
    mode = MODES[interruption]
    home, control = setup(tmp_path, [mode, "real"] if recovers else [mode])
    body = start(tmp_path, home, control)
    try:
        for n in range(1, (1 if recovers else APPRAISAL_ATTEMPTS) + 1):
            interrupt(control, n, mode)
            if n < APPRAISAL_ATTEMPTS and not recovers:
                wait_for(lambda: len(events(home, "mission.appraisal_unavailable")) >= n, what=f"attempt {n} recorded")
        [appraisal] = wait_for(lambda: events(home, "mission.appraised"), what="the closure's appraisal")
        more_ticks(home)                                 # nothing more is appraised
        assert body.poll() is None, "an interrupted appraiser does not take the Body down"
        final = events(home, "mission.appraised")
        attempts = events(home, "mission.appraisal_unavailable")
        assert len(events(home, "mission.achieved")) == 1
    finally:
        stop(body, control)

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
    assert all(a["mission_id"] == MISSION and WHY[mode] in a["why"] for a in attempts), [a["why"] for a in attempts]
    with observe(home) as journal:
        assert journal.ledger.verify_chain()[0]


def test_attempts_are_counted_per_closure_not_pooled_across_a_mission_s_closures(tmp_path):
    # A standing mission closes twice. Its first closure's appraisal is interrupted twice, then completes; its
    # second's is interrupted once, then completes. Pooled per mission, the second closure's first interruption
    # would be attempt 3 of 3 and end it UNAVAILABLE without the run that verifies it.
    home, control = setup(tmp_path, ["hang", "hang", "real", "hang", "real"],
                          closure={"kind": "infinite", "cadence_seconds": 60})
    body = start(tmp_path, home, control)
    try:
        for n in (1, 2):
            interrupt(control, n, "hang")
            wait_for(lambda: len(events(home, "mission.appraisal_unavailable")) >= n, what=f"attempt {n} recorded")
        wait_for(lambda: events(home, "mission.appraised"), what="the first closure's appraisal")
        (workspace(home, MISSION) / "n.txt").write_text("drifted")   # the world leaves the setpoint ...
        move_clock(control, 120)                                      # ... and the next observation is due
        wait_for(lambda: len(events(home, "mission.held")) == 2, what="the mission's second closure")
        interrupt(control, 4, "hang")
        wait_for(lambda: len(events(home, "mission.appraised")) == 2, what="the second closure's appraisal")
        more_ticks(home)                                 # nothing more is appraised
        assert body.poll() is None
        closures = [e.event_id for e in recorded(home, "mission.held")]
        appraised = events(home, "mission.appraised")
        attempts = events(home, "mission.appraisal_unavailable")
    finally:
        stop(body, control)

    assert [(a["closure_event"], a["verdict"]) for a in appraised] == [(c, "VERIFIED") for c in closures]
    assert [(a["closure_event"], a["attempt"]) for a in attempts] == [(closures[0], 1), (closures[0], 2),
                                                                      (closures[1], 1)]
    requests = [json.loads((control / f"run-{n}.request").read_text()) for n in range(1, runs(control) + 1)]
    assert [r["closure_event"] for r in requests] == [closures[0]] * 3 + [closures[1]] * 2
    with observe(home) as journal:
        assert journal.ledger.verify_chain()[0]


def test_a_body_killed_while_its_appraiser_runs_appraises_the_closure_again_after_restart(tmp_path):
    home, control = setup(tmp_path, ["hang", "real"])
    body = start(tmp_path, home, control)
    try:
        orphan = int(wait_for(lambda: (control / "run-1.pid").read_text(), what="the appraiser inside its appraisal"))
        body.send_signal(signal.SIGKILL)                 # the Body dies; its appraiser is left running
        body.wait(timeout=20)
        assert events(home, "mission.appraised") == [] and events(home, "mission.appraisal_unavailable") == []
        kill(orphan)
        body = start(tmp_path, home, control)
        [appraisal] = wait_for(lambda: events(home, "mission.appraised"), what="the appraisal after restart")
        more_ticks(home)
        assert body.poll() is None
        final = events(home, "mission.appraised")
    finally:
        stop(body, control)

    assert final == [appraisal] and appraisal["verdict"] == "VERIFIED"
    assert runs(control) == 2 and events(home, "body.recovered")
    assert events(home, "mission.appraisal_unavailable") == [], "a run the Body never saw end is not an attempt"
