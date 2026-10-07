"""Interruption and recovery rehearsal of the seed composition on the real runtime entry point.

Directive sections 16 and 20.9: "Run the integrated interruption/recovery rehearsal". The body
runs as its own OS process under supervisord (standing in for the systemd user unit), interfaces
are separate CLI processes that exit, and the test sends real signals:

1. A founder-signed mission asks, in words, for the best order of today's jobs and then for the
   agreed plan to be recorded. The cortex step (extraction -> CP-SAT -> Z3 certificate ->
   verifier) is inside the light cone and runs on its own; recording the plan is a write outside
   it, so GREG asks and waits.
2. ``kill -9`` while it waits. The supervisor restarts the body. Nothing has acted yet, nothing
   acts before approval, and the approval is remembered, not re-asked. The cortex step is a
   read-only observation, so recovery may re-observe it; a read is never a repeated consequence.
3. The founder approves. The mission closes on re-observed evidence, the separate-process
   appraiser verifies it, and competence settles exactly once.
4. The founder detaches CP-SAT. ``kill -9`` again. After the restart a new cortex mission routes
   to Z3: the revocation survived the restart.
5. The founder stops the body and it stays stopped.

The founder key is a per-test key; nothing here is founder use or a Chromebook run.
"""
from datetime import datetime, timedelta, timezone
import itertools
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from cortex.evaluation.build_suites import schedule  # noqa: E402
from greg import service  # noqa: E402
from tests.integration.test_greg_body_supervised import (SUPERVISORD, events, greg, heartbeat, history,  # noqa: E402
                                                         supervisor_endpoint, wait_for)

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(SUPERVISORD is None, reason="supervisord stands in for the systemd user unit")
NOTE = ("Shift: 10 hours. Job J takes 3 hours. Job K takes 2 hours. Job L takes 4 hours. J before L. "
        "One machine; one job at a time. Minimize total completion time.")
DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}


def best_total_completion():
    """Brute force over every start time: no solver, no shared parser."""
    jobs, best = {"J": 3, "K": 2, "L": 4}, None
    for s in itertools.product(range(11), repeat=3):
        start = dict(zip("JKL", s))
        end = {j: start[j] + jobs[j] for j in jobs}
        if any(v > 10 for v in end.values()) or start["L"] < end["J"]:
            continue
        if any(not (end[a] <= start[b] or end[b] <= start[a]) for a, b in itertools.combinations(jobs, 2)):
            continue
        best = sum(end.values()) if best is None else min(best, sum(end.values()))
    return best


def horizon():
    return (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")


def cortex_receipts(home):
    ledger, _ = history(home)
    try:
        out = []
        for r in ledger.by_type("receipt"):
            value = (r.payload.get("result") or {}).get("output")
            if isinstance(value, dict) and value.get("proof_type") == "cortex_receipt":
                out.append(value)
        return out
    finally:
        ledger.close()


def test_kill_restart_approve_settle_once_then_revocation_survives_restart(tmp_path):
    home, data, key = tmp_path / "body", tmp_path / "data", tmp_path / "founder.pem"
    data.mkdir()
    greg(home, "init", "--read-root", str(data))
    public = greg(home, "founder", "keygen", "--key", str(key), "--no-passphrase").stdout.strip()
    greg(home, "founder", "enroll", "--pubkey", public)
    signed = ("--key", str(key), "--no-passphrase")

    conf = tmp_path / "supervisord.conf"
    (home / "logs").mkdir(exist_ok=True)
    server, ctl = supervisor_endpoint(tmp_path)
    conf.write_text(
        f"[supervisord]\nnodaemon=true\nlogfile={tmp_path / 'supervisord.log'}\npidfile={tmp_path / 'sd.pid'}\n"
        + server +
        "[rpcinterface:supervisor]\nsupervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface\n"
        + ctl + service.supervisord_program(home, tick_seconds=0.3))
    supervisor = subprocess.Popen([SUPERVISORD, "-c", str(conf)], cwd=ROOT,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    best = best_total_completion()
    try:
        first = wait_for(lambda: heartbeat(home)["state"] == "RUNNING" and heartbeat(home), what="body start")
        workspace = home.resolve() / "workspace" / "m_cortex-rehearsal"
        step = {"capability": "cognition.solve", "target": "cognition:schedule",
                "params": {"problem_id": "cortex:words", "problem": {
                    "question": "Best order for today's jobs, from my note",
                    "payload": {"schedule_request": {"text": NOTE, "availability_evidence":
                                                     "founder note: the machine is free all shift"},
                                "declared": DECL}}}}
        spec = {
            "mission_id": "m:cortex-rehearsal",
            "founder_expression": "Work out the best order for today's jobs from my note, then record the plan.",
            "intended_effect": "a certified optimal order for the note, and the agreed plan in the workspace",
            "priority": 80, "closure": {"kind": "bounded"},
            "success_checks": [
                {"check_id": "optimal", "description": f"certified optimal total completion time {best}",
                 "sensor": step, "predicate": {"op": "equals", "field": "output.answer.1.objective", "value": best}},
                {"check_id": "recorded", "description": "agreed plan recorded",
                 "sensor": {"capability": "fs.read", "params": {"path": str(workspace / "plan.txt")},
                            "target": "fs:plan.txt"},
                 "predicate": {"op": "contains", "field": "text", "value": "total completion"}}],
            "strategies": [
                {"action_id": "solve", **step, "advances": ["optimal"], "rationale": "compute through the cortex"},
                {"action_id": "record", "capability": "fs.write",
                 "params": {"relative_path": "plan.txt", "content": f"agreed plan: K, J, L; total completion {best}h"},
                 "target": "workspace:plan.txt", "advances": ["recorded"],
                 "rationale": "record the agreed plan (a write: needs founder approval)"}],
            "light_cone": {"capabilities": ["cognition.solve", "fs.read"],
                           "targets": ["cognition:*", "fs:*", "workspace:*"],
                           "max_consequence_class": "read_only", "budget_usd": 0, "horizon": horizon()}}
        mission_file = tmp_path / "mission.json"
        mission_file.write_text(json.dumps(spec))
        greg(home, "mission", "submit", str(mission_file), *signed)

        # 1. The cortex step runs on its own; the write waits for the founder.
        wait_for(lambda: cortex_receipts(home), what="cortex receipt", timeout=90)
        request = wait_for(lambda: [r for r in events(home, "decision.requested") if r["kind"] == "APPROVAL"],
                           what="approval request for the write", timeout=60)[0]
        solved = cortex_receipts(home)
        assert solved[-1]["outcome"]["outcome"] == "ANSWERED_WITHIN_SCOPE" and solved[-1]["authority_created"] is False
        assert solved[-1]["proof_artifact"]["output"]["answer"][1]["objective"] == best
        assert not (workspace / "plan.txt").exists()
        assert not [a for a in events(home, "mission.action") if a["status"] == "DONE"]   # nothing acted yet
        observed_before_kill = len(solved)

        # 2. kill -9 while it waits; the supervisor restarts the body.
        os.kill(first["pid"], signal.SIGKILL)
        second = wait_for(lambda: heartbeat(home)["pid"] != first["pid"] and heartbeat(home)["state"] == "RUNNING"
                          and heartbeat(home), what="supervisor restart")
        wait_for(lambda: events(home, "body.recovered"), what="recovery record")
        time.sleep(1.5)   # several ticks while blocked
        # The cortex step is a read-only observation: recovery may re-observe it (a read, never a
        # consequence). What must not repeat is a consequence or a request.
        assert len(cortex_receipts(home)) <= observed_before_kill + 1
        assert not [a for a in events(home, "mission.action") if a["status"] == "DONE"]
        assert not (workspace / "plan.txt").exists()
        assert len([r for r in events(home, "decision.requested") if r["kind"] == "APPROVAL"]) == 1

        # 3. Approve: closure on re-observed evidence, independent appraisal, one settlement.
        greg(home, "decide", request["request_id"], "approve", "--reason", "record it", *signed)
        wait_for(lambda: [m for m in events(home, "mission.achieved") if m["mission_id"] == "m:cortex-rehearsal"],
                 what="mission closure", timeout=90)
        appraisal = wait_for(lambda: [a for a in events(home, "mission.appraised")
                                      if a["mission_id"] == "m:cortex-rehearsal"], what="appraisal", timeout=90)[0]
        assert appraisal["verdict"] == "VERIFIED", appraisal
        assert (workspace / "plan.txt").read_text().startswith("agreed plan")
        assert [a["action_id"] for a in events(home, "mission.action") if a["status"] == "DONE"] == ["record"]
        settled = wait_for(lambda: events(home, "cognition.settled"), what="settlement", timeout=60)
        assert len(settled) == 1 and settled[0]["method"] == "cognition.cortex"

        # 4. Founder detaches CP-SAT; kill -9; after restart a new mission routes to Z3.
        greg(home, "detach", "cognition.cortex.optimization.cpsat", *signed)
        wait_for(lambda: [e for e in events(home, "capability") if "cpsat" in json.dumps(e)]
                 or [e for e in events(home, "command") if "cpsat" in json.dumps(e)], what="detach applied",
                 timeout=30)
        os.kill(second["pid"], signal.SIGKILL)
        third = wait_for(lambda: heartbeat(home)["pid"] != second["pid"] and heartbeat(home)["state"] == "RUNNING"
                         and heartbeat(home), what="second restart")
        model, _, _ = schedule([("A", 3), ("B", 4), ("C", 2)], 10, query={
            "kind": "optimize", "sense": "minimize", "objective": ["+", "s_A", "s_B", "s_C"]})
        z3_step = {"capability": "cognition.solve", "target": "cognition:schedule",
                   "params": {"problem_id": "cortex:after-detach", "problem": {
                       "question": "Earliest starts for A, B, C", "payload": {"formal_model": model, "declared": DECL}}}}
        spec2 = {"mission_id": "m:after-detach", "founder_expression": "Earliest starts for A, B and C.",
                 "intended_effect": "a certified optimal schedule", "priority": 70, "closure": {"kind": "bounded"},
                 "success_checks": [{"check_id": "opt", "description": "optimum 7", "sensor": z3_step,
                                     "predicate": {"op": "equals", "field": "output.answer.objective", "value": 7}}],
                 "strategies": [{"action_id": "solve2", **z3_step, "advances": ["opt"], "rationale": "cortex"}],
                 "light_cone": {"capabilities": ["cognition.solve"], "targets": ["cognition:*"],
                                "max_consequence_class": "read_only", "budget_usd": 0, "horizon": horizon()}}
        mission_file.write_text(json.dumps(spec2))
        greg(home, "mission", "submit", str(mission_file), *signed)
        wait_for(lambda: [m for m in events(home, "mission.achieved") if m["mission_id"] == "m:after-detach"],
                 what="second closure", timeout=90)
        after = [r for r in cortex_receipts(home) if r["problem_id"] == "cortex:after-detach"]
        assert after and {r["method"] for r in after} == {"cognition.cortex.formal.z3"}, {r["method"] for r in after}
        assert third["boot_id"] != second["boot_id"]

        # 5. Founder stop: the body stays stopped.
        greg(home, "stop", *signed)
        wait_for(lambda: heartbeat(home)["state"] == "STOPPED", what="founder stop")
        time.sleep(2.0)
        status = subprocess.run(["supervisorctl", "-c", str(conf), "status"], capture_output=True, text=True)
        assert "EXITED" in status.stdout, status.stdout

        ledger, journal = history(home)
        try:
            ok, why = ledger.verify_chain()
            assert ok, why
            boots = journal.replay("body.booted")
            assert len(boots) == 3
            assert len(ledger.by_type("receipt")) == len({r.payload["grant_id"] for r in ledger.by_type("receipt")})
            assert len(journal.replay("cognition.settled")) == len({e.payload["observation_event"]
                                                                     for e in journal.replay("cognition.settled")})
        finally:
            ledger.close()
        if os.environ.get("GREG_RECORD_EVIDENCE"):
            out = ROOT / "tests" / "evidence" / "greg-cortex-rehearsal"
            out.mkdir(parents=True, exist_ok=True)
            shutil.copy(home / "ledger.jsonl", out / "rehearsal-ledger.jsonl")
            (out / "rehearsal-summary.json").write_text(json.dumps({
                "what": "seed composition on the supervised body: kill -9 while waiting, restart, approve, "
                        "settle once; founder detach; kill -9; revocation survives restart; founder stop",
                "founder_key": "per-test Ed25519 key; NOT Alfonso", "host": "Linux container, supervisord in place "
                "of the systemd user unit; not a Chromebook or founder run",
                "boots": [b.payload for b in boots], "recovered": events(home, "body.recovered"),
                "decision_requests": events(home, "decision.requested"),
                "actions": events(home, "mission.action"), "achieved": events(home, "mission.achieved"),
                "appraised": events(home, "mission.appraised"), "settled": events(home, "cognition.settled"),
                "cortex_receipts": [{"problem_id": r["problem_id"], "method": r["method"],
                                     "outcome": r["outcome"], "receipt_id": r["receipt_id"]}
                                    for r in cortex_receipts(home)],
                "supervisor_status": status.stdout.strip()}, indent=1, default=str) + "\n")
    finally:
        supervisor.send_signal(signal.SIGTERM)
        try:
            supervisor.wait(timeout=20)
        except subprocess.TimeoutExpired:
            supervisor.kill()
