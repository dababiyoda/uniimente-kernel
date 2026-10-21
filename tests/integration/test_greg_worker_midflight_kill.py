"""Mission H (fault recovery), gap H.G4: the paid worker is interrupted inside a real Body process.

Directive section 33, Mission H: "Interrupt workers ... Demonstrate correct recovery, no unbounded retry loop, no
duplicate irreversible consequence, and truthful handling of unknown completion." The Body runs as its own OS
process through the canonical main loop (Body.run, what `greg run` runs). Its one extra piece is a worker provider
registered in greg.workers.PROVIDERS: the real CliAgentWorker path (scrubbed environment, Landlock where the kernel
has it, the parent-death signal, the timeout) around a scripted program instead of a frontier CLI. A signed mission
commissions one WorkOrder (worker.commission, internal_write, a signed $0.50 cap) and closes only on the
independent worker.appraise verdict ACCEPTED.

The first worker writes a partial edit into its private clone and keeps working. The test waits until the
WorkerLease names the grant the Gate dispatched and the worker is a running child of the Body (read from /proc,
not from the worker), then SIGKILLs the Body. The worker dies with it: the parent-death signal, not cooperation.
After the restart the dispatch is UNCERTAIN, bound to the killed grant, its signed cap reserved, and exactly one
RECONCILIATION request names it; nothing is commissioned while it waits. The founder's signed
reconcile_not_executed lets exactly one new WorkOrder run, under a new grant, in a fresh clone (the partial clone
is discarded); the independent appraisal accepts it and the separate-process mission appraisal verifies the
closure. The interrupted run's spend was never measured, so its signed cap is booked, never zero, and the booked
total is at most twice the cap. Every grant is dispatched once and receipted at most once.

Every key is a per-test Ed25519 key, not Alfonso's; the worker is a scripted test double, not a frontier worker.
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

from greg import isolation
from greg.body import Body, Layout, observe
from greg.missions import MissionBook
from tests.greg_fixtures import drop, make_body, mission, signed, workspace

ROOT = Path(__file__).resolve().parents[2]
# Cert-bundle variables a host may point outside the system certificate roots: the worker envelope refuses those by
# design (tests/unit/test_greg_worker_isolation.py), so the Body here gets none.
CERT_ENV = ("SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS")
MID, ORDER, CAP, MARK = "m:work-once", "add-sub", 0.5, "h-g4-scripted-worker"

# The worker program, run as ``python -c`` by the provider inside the private clone, confined like any worker.
WORKER = f'''# {MARK}
import sys, time
mode = sys.argv[1]
sys.stdin.read()                                  # the WorkOrder prompt: data, never instructions
if mode == "hang":
    with open("pkg/partial_edit.py", "w") as f:   # a partial edit in the private clone ...
        f.write("def sub(a, b):\\n    return a -\\n")
    time.sleep(30)                                # ... and still working when its Body dies
    sys.exit(0)
with open("pkg/calc.py", "w") as f:
    f.write("def add(a, b):\\n    return a + b\\n\\n\\ndef sub(a, b):\\n    return a - b\\n")
print('WORK_REPORT: {{"changed": ["pkg/calc.py"], "confidence": 1.0}}')
'''

DRIVER = '''
import os, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from greg import workers
from greg.body import Body

home, calls, program, mode = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]).read_text(), sys.argv[5]


class ScriptedWorker(workers.CliAgentWorker):
    """The real provider path (scrubbed env, confinement, parent-death signal, timeout) around a scripted program."""

    def run(self, order, cwd, **kwargs):
        with calls.open("a") as f:
            f.write(order.grant_id + "\\n")
            f.flush()
            os.fsync(f.fileno())
        return super().run(order, cwd, **kwargs)


# Reviewed: it stands for a frontier CLI on the default body, so it runs in the worker envelope (#184).
workers.PROVIDERS["scripted"] = ScriptedWorker("scripted", [sys.executable, "-c", program, mode], reviewed=True)
if mode == "stop-after-evidence":
    commission = workers.commission

    def stops_after_evidence(params, ctx):
        """The real commission, then this Body holds still until the test kills it: the WorkOrder's evidence.json
        is written and the Gate has not recorded the receipt (a forced point, not a race)."""
        commission(params, ctx)
        calls.with_name("evidence-written").write_text(ctx.grant_id)
        time.sleep(3600)
        raise SystemExit(3)

    workers.commission = stops_after_evidence
sys.exit(Body(home).run(tick_seconds=0.2))
'''


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def make_repo(data: Path) -> Path:
    """A project whose frozen acceptance test fails until ``sub`` exists."""
    repo = data / "proj"
    (repo / "pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (repo / "tests" / "test_calc.py").write_text("from pkg.calc import sub\n\n\ndef test_sub():\n    assert sub(3, 1) == 2\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return repo


def spec(repo: Path) -> dict:
    return mission(MID, checks=[{
        "check_id": "work_accepted", "description": "the work order is independently accepted",
        "sensor": {"capability": "worker.appraise", "params": {"order": ORDER}, "target": f"work:{ORDER}"},
        "predicate": {"op": "equals", "field": "verdict", "value": "ACCEPTED"}}],
        strategies=[{"action_id": "commission", "capability": "worker.commission", "target": f"work:{ORDER}",
                     "params": {"order": ORDER, "mode": "repository", "repo": str(repo), "objective": "add sub()",
                                "acceptance": {"tests": [["python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                                                          "tests/test_calc.py"]]},
                                "allowed_paths": ["pkg/*"], "provider": "scripted", "max_budget_usd": CAP,
                                "timeout_seconds": 60},
                     "cost_usd": CAP, "advances": ["work_accepted"], "rationale": "commission one paid worker"}],
        capabilities=["worker.commission", "worker.appraise"], targets=("work:*",), budget=1.0)


def start(tmp_path: Path, home: Path, calls: Path, mode: str) -> subprocess.Popen:
    driver, program = tmp_path / "driver.py", tmp_path / "worker_program.py"
    driver.write_text(DRIVER)
    program.write_text(WORKER)
    return subprocess.Popen([sys.executable, str(driver), str(ROOT), str(home), str(calls), str(program), mode],
                            cwd=ROOT, stdout=(tmp_path / "body.log").open("a"), stderr=subprocess.STDOUT,
                            env={**{k: v for k, v in os.environ.items() if k not in CERT_ENV}, "PYTHONPATH": str(ROOT)})


def read(home: Path) -> dict:
    """Read-only view of the Body's ledger and its mission projection (the Body process owns the writer)."""
    with observe(home, actor="spiffe://uniimente.internal/greg/worker-kill-test") as journal:
        out = {kind: [e.payload for e in journal.replay(kind)]
               for kind in ("mission.dispatching", "mission.action", "mission.observed", "decision.requested",
                            "mission.achieved", "mission.appraised", "body.recovered")}
        out["dispatch"] = [r.payload for r in journal.ledger.by_type("grant_dispatch")]
        out["receipt"] = {r.hash: r.payload for r in journal.ledger.by_type("receipt")}
        out["mission"] = MissionBook(journal).missions[MID]
        return out


def commissions(state: dict) -> list[dict]:
    return [a for a in state["mission.action"] if a["action_id"] == "commission"]


def commission_dispatches(state: dict) -> list[dict]:
    proposals = {i["proposal_id"] for i in state["mission.dispatching"] if i["action_id"] == "commission"}
    return [d for d in state["dispatch"] if d.get("proposal_id") in proposals]


def waiting_ticks(home: Path, seen: set) -> int:
    """How many distinct main-loop turns have been seen with the mission WAITING (one heartbeat per turn)."""
    beat = json.loads(Layout(home).heartbeat.read_text())
    if any(m.get("mission_id") == MID and m.get("state") == "WAITING" for m in beat.get("missions", [])):
        seen.add(beat["at"])
    return len(seen)


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


def _stat(pid: int) -> list[str] | None:
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except OSError:
        return None


def worker_processes(parent: int) -> list[int]:
    """The scripted worker processes descended from ``parent``, read from /proc (not reported by the worker)."""
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        fields = _stat(int(entry.name))
        try:
            cmdline = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        launcher = Path(cmdline.split(b"\0", 1)[0].decode(errors="replace")).name == "bwrap"   # carries the argv too
        if fields and MARK.encode() in cmdline and not launcher and _descends(int(entry.name), parent):
            found.append(int(entry.name))
    return found


def _descends(pid: int, ancestor: int) -> bool:
    """Whether ``ancestor`` is on ``pid``'s parent chain: the Body's direct child under Landlock, or inside the
    bubblewrap envelope (Body -> bwrap -> the namespace's init -> worker), which dies with the Body
    (--die-with-parent, and the PID namespace ends with its init)."""
    for _ in range(8):
        fields = _stat(pid)
        if not fields:
            return False
        pid = int(fields[1])
        if pid == ancestor:
            return True
        if pid <= 1:
            return False
    return False


def alive(pid: int, started: str) -> bool:
    """The same process (its start time) still exists and is not a zombie."""
    fields = _stat(pid)
    return bool(fields) and fields[0] not in ("Z", "X") and fields[19] == started


def stop(body: subprocess.Popen) -> None:
    body.send_signal(signal.SIGTERM)
    try:
        body.wait(timeout=30)
    except subprocess.TimeoutExpired:
        body.kill()
        body.wait(timeout=10)


def test_a_worker_killed_with_its_body_is_reconciled_then_recommissioned_exactly_once(tmp_path):
    if not sys.platform.startswith("linux"):
        pytest.skip("the parent-death signal is Linux-only (stated limit in greg/workers.py)")
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    drop(home, signed(key, body_id, "MISSION", spec(repo)))
    calls = tmp_path / "calls"
    order_dir = workspace(home, MID) / "work-orders" / ORDER
    partial = order_dir / "repo" / "pkg" / "partial_edit.py"

    body = start(tmp_path, home, calls, "hang")
    worker, started = None, None
    try:
        # The WorkerLease names the grant the Gate dispatched; its worker is a running child of this Body process
        # and has already changed its private clone. No receipt exists: the Body has recorded nothing yet.
        lease = wait_for(lambda: json.loads((order_dir / "lease.json").read_text()), what="the WorkerLease")
        [worker] = wait_for(lambda: worker_processes(body.pid), what="the worker process")
        started = _stat(worker)[19]
        wait_for(partial.exists, what="the worker's partial edit in its private clone")
        before = read(home)
        killed = lease["grant_id"]
        assert [d["grant_id"] for d in commission_dispatches(before)] == [killed]
        assert not [r for r in before["receipt"].values() if r["grant_id"] == killed]
        assert commissions(before) == []
        assert lease["authority_created"] is False and lease["push_rights"] is False

        body.send_signal(signal.SIGKILL)
        body.wait(timeout=20)
        deadline = time.time() + 5
        while alive(worker, started) and time.time() < deadline:
            time.sleep(0.05)
        assert not alive(worker, started), "the worker outlived its Body (it would keep working and spending)"
    finally:
        if body.poll() is None:
            body.kill()
            body.wait(timeout=20)
        if worker and started and alive(worker, started):
            os.kill(worker, signal.SIGKILL)

    body = start(tmp_path, home, calls, "normal")
    try:
        wait_for(lambda: [r for r in read(home)["decision.requested"] if r["kind"] == "RECONCILIATION"]
                 or len(calls.read_text().split()) > 1, what="the reconciliation request")
        ticks: set = set()                                # 10 turns of the main loop while the founder is silent
        wait_for(lambda: waiting_ticks(home, ticks) >= 10 or len(calls.read_text().split()) > 1,
                 what="ten ticks waiting on the founder")
        waiting = read(home)
        assert calls.read_text().split() == [killed], "nothing is commissioned while the reconciliation is open"
        [request] = [r for r in waiting["decision.requested"] if r["kind"] == "RECONCILIATION"]
        assert waiting["body.recovered"], "the restart reconstructs from retained history"
        assert [(a["status"], a["attempt"]) for a in commissions(waiting)] == [("UNCERTAIN", 0)]
        uncertain = commissions(waiting)[0]
        assert uncertain["grant_id"] == killed
        assert uncertain["reserved_usd"] == CAP and uncertain["cost_usd"] == 0.0   # unknown, reserved at its cap
        assert waiting["mission"].committed_usd == CAP
        assert request["authority_requested"]["grant_id"] == killed and request["authority_requested"]["attempt"] == 0
        # The founder is told before answering that "not executed" still books the metered run's signed cap.
        assert request["evidence"]["booked_usd_by_answer"] == {"reconcile_executed": CAP,
                                                               "reconcile_not_executed": CAP}
        assert partial.exists(), "no blind re-execution touched the interrupted clone"

        drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"],
                                                     "answer": "reconcile_not_executed",
                                                     "reason": "the worker died with its body; nothing was collected"}))
        wait_for(lambda: read(home)["mission.appraised"], timeout=90, what="the separate-process appraisal")
        final = read(home)
    finally:
        stop(body)

    # Exactly one re-commission, under a new grant, in a fresh clone: the partial clone was discarded.
    [first, second] = calls.read_text().split()
    assert first == killed and second != killed
    assert [(a["status"], a["attempt"]) for a in commissions(final)] == \
        [("UNCERTAIN", 0), ("RECONCILED_NOT_EXECUTED", 0), ("DONE", 1)]
    settled, done = commissions(final)[1:]
    assert settled["reconciles"]["grant_id"] == killed
    assert [r["kind"] for r in final["decision.requested"]] == ["RECONCILIATION"]   # one ask in the whole run
    assert final["receipt"][done["receipt"]]["grant_id"] == second
    assert not partial.exists()
    evidence = json.loads((order_dir / "evidence.json").read_text())["summary"]
    assert evidence["grant_id"] == second and evidence["changed_files"] == ["pkg/calc.py"]
    assert "partial_edit" not in (order_dir / "change.patch").read_text()
    assert json.loads((order_dir / "lease.json").read_text())["grant_id"] == second
    # The double ran on the real, confined provider path: the default body's bubblewrap envelope, or Landlock where
    # the envelope is unavailable and the founder chose supervision.
    if evidence["worker"]["confinement"].get("mechanism") == "bubblewrap":
        assert evidence["worker"]["confinement"]["filesystem"] == "os-confined"
    elif isolation.available().get("available"):
        assert evidence["worker"]["confinement"]["filesystem"] == "landlock"

    # The independent appraisal gives the verdict, and the separate-process appraiser verifies the closure.
    accepted = [o for o in final["mission.observed"] if o["check_id"] == "work_accepted"][-1]
    verdict = final["receipt"][accepted["receipt"]]["result"]["output"]
    assert accepted["passed"] and verdict["verdict"] == "ACCEPTED", verdict
    assert final["mission.achieved"] and [a["verdict"] for a in final["mission.appraised"]] == ["VERIFIED"], \
        final["mission.appraised"]

    # Spend: the interrupted run's spend was never measured, so its signed cap is booked, not zero; the provider of
    # the re-commission reported none either, so it is booked at its cap; at most twice the cap in all.
    assert settled["cost_usd"] == CAP, "an interrupted paid run's unmeasured spend is booked at its cap, not zero"
    assert "whether its metered provider ran" in settled["spend_basis"]
    assert done["cost_usd"] == CAP and done["spend_basis"].startswith("signed_cap")
    m = final["mission"]
    assert (m.spent_usd, m.reserved_usd) == (2 * CAP, 0.0) and m.spent_usd <= 2 * CAP

    # No duplicate consequence: every grant is dispatched once and receipted at most once.
    grants = [d["grant_id"] for d in final["dispatch"]]
    assert len(grants) == len(set(grants))
    receipted = [r["grant_id"] for r in final["receipt"].values()]
    assert len(receipted) == len(set(receipted)) and killed not in receipted
    with Body(home) as b:
        assert b.ledger.verify_chain()[0]


def test_a_body_killed_after_the_work_order_evidence_and_before_its_receipt_is_recommissioned_not_closed(tmp_path):
    """Gap H.G11: the Body dies after the WorkOrder's evidence.json is written but before the Gate's receipt.

    Before the fix, a signed reconcile_not_executed let the engine's own worker.appraise sensor accept that
    unreceipted evidence: the mission closed ACHIEVED with one worker run and no receipted DONE action, and the
    separate-process appraisal (which binds the evidence to its commission receipt) gave REFUTED. Now the engine's
    sensor rejects it as the appraiser does, and the re-commission runs a new worker under a new grant."""
    if not sys.platform.startswith("linux"):
        pytest.skip("the parent-death signal is Linux-only (stated limit in greg/workers.py)")
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    drop(home, signed(key, body_id, "MISSION", spec(repo)))
    calls = tmp_path / "calls"
    order_dir = workspace(home, MID) / "work-orders" / ORDER

    body = start(tmp_path, home, calls, "stop-after-evidence")
    try:
        killed = wait_for(lambda: calls.with_name("evidence-written").read_text(),
                          what="the work order's evidence, before its receipt")
        evidence = json.loads((order_dir / "evidence.json").read_text())["summary"]
        assert evidence["grant_id"] == killed and evidence["status"] == "COMPLETED"   # the worker finished
        before = read(home)
        assert [d["grant_id"] for d in commission_dispatches(before)] == [killed]
        assert not [r for r in before["receipt"].values() if r["grant_id"] == killed] and not commissions(before)
        body.send_signal(signal.SIGKILL)
        body.wait(timeout=20)
    finally:
        if body.poll() is None:
            body.kill()
            body.wait(timeout=20)

    body = start(tmp_path, home, calls, "normal")
    try:
        wait_for(lambda: [r for r in read(home)["decision.requested"] if r["kind"] == "RECONCILIATION"]
                 or len(calls.read_text().split()) > 1, what="the reconciliation request")
        waiting = read(home)
        assert calls.read_text().split() == [killed], "nothing is commissioned while the reconciliation is open"
        assert [(a["status"], a["attempt"]) for a in commissions(waiting)] == [("UNCERTAIN", 0)]
        assert not waiting["mission.achieved"], "no closure over the unreceipted run while the founder decides"
        [request] = [r for r in waiting["decision.requested"] if r["kind"] == "RECONCILIATION"]
        drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"],
                                                     "answer": "reconcile_not_executed",
                                                     "reason": "its receipt was never recorded"}))
        wait_for(lambda: read(home)["mission.appraised"], timeout=90, what="the separate-process appraisal")
        final = read(home)
    finally:
        stop(body)

    # A new worker run under a new grant; the unreceipted evidence was neither accepted nor reused.
    [first, second] = calls.read_text().split()
    assert first == killed and second != killed
    assert [(a["status"], a["attempt"]) for a in commissions(final)] == \
        [("UNCERTAIN", 0), ("RECONCILED_NOT_EXECUTED", 0), ("DONE", 1)]
    done = commissions(final)[2]
    output = final["receipt"][done["receipt"]]["result"]["output"]
    assert final["receipt"][done["receipt"]]["grant_id"] == second
    assert output["grant_id"] == second and "reused" not in output
    assert json.loads((order_dir / "evidence.json").read_text())["summary"]["grant_id"] == second
    observed = [o for o in final["mission.observed"] if o["check_id"] == "work_accepted"]
    assert any("REJECTED" in str(o.get("detail")) for o in observed), observed   # the engine refused it itself
    assert [o["passed"] for o in observed].count(True) == 1 and observed[-1]["passed"]
    assert [a["actions_done"] for a in final["mission.achieved"]] == [1]
    assert [a["verdict"] for a in final["mission.appraised"]] == ["VERIFIED"], final["mission.appraised"]
    m = final["mission"]
    assert (m.spent_usd, m.reserved_usd) == (2 * CAP, 0.0)
    grants = [d["grant_id"] for d in final["dispatch"]]
    assert len(grants) == len(set(grants))
    receipted = [r["grant_id"] for r in final["receipt"].values()]
    assert len(receipted) == len(set(receipted)) and killed not in receipted
    with Body(home) as b:
        assert b.ledger.verify_chain()[0]
