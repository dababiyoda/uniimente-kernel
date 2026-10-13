"""Directive §16 rehearsal: a heterogeneous cognition mission through GREG's real entry points.

founder signs a pipeline mission with the CLI -> supervised body -> SIGKILL -> torn ledger
tail while frozen -> autonomous restart -> L1 validation, CP-SAT, Z3 cross-check -> typed
receipt -> separate-process appraisal VERIFIED -> exactly one action -> settled once ->
signed detach -> SIGKILL -> the detach survives restart and a new pipeline mission cannot
run -> signed stop. The founder key is a per-test key, not Alfonso's; the body is a Linux
container process, not the founder's Chromebook, so nothing here is VEPMC evidence.
"""
import json
import os
from pathlib import Path
import signal
import subprocess

import pytest

from greg import service
from tests.integration.test_greg_body_supervised import (ROOT, SUPERVISORD, events, greg, heartbeat, history,
                                                         supervisor_endpoint, wait_for)

pytestmark = pytest.mark.skipif(SUPERVISORD is None, reason="supervisord (requirements-dev) not installed")

TEXT = ("Schedule two shifts x and y, each between 0 and 10 hours, together at least 5 hours; "
        "minimize cost x + 2y.")
MODEL = {"variables": {"x": [0, 10], "y": [0, 10]},
         "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": ">=", "rhs": 5}],
         "objective": {"coefficients": {"x": 1, "y": 2}, "sense": "min"}}


def _request(tmp_path, name, problem_id):
    path = tmp_path / name
    path.write_text(json.dumps({"pipeline": "schedule_from_request", "problem_id": problem_id,
                                "source": {"text": TEXT}, "model": MODEL}))
    return path


def _receipts(home, problem_id):
    """Gate receipts whose result is a pipeline run for this problem (sensor or action alike)."""
    ledger, _ = history(home)
    try:
        return [r.payload for r in ledger.by_type("receipt")
                if isinstance(r.payload.get("result", {}).get("output"), dict)
                and (r.payload["result"]["output"].get("receipt") or {}).get("problem_id") == problem_id]
    finally:
        ledger.close()


def test_cognition_mission_survives_kill_and_torn_write_closes_once_and_respects_detach(tmp_path):
    home, key = tmp_path / "body", tmp_path / "founder.pem"
    greg(home, "init", "--read-root", str(tmp_path))
    greg(home, "founder", "enroll", "--pubkey",
         greg(home, "founder", "keygen", "--key", str(key), "--no-passphrase").stdout.strip())
    conf = tmp_path / "supervisord.conf"
    (home / "logs").mkdir(exist_ok=True)
    endpoint, ctl = supervisor_endpoint(tmp_path)
    conf.write_text(
        f"[supervisord]\nnodaemon=true\nlogfile={tmp_path / 'sd.log'}\npidfile={tmp_path / 'sd.pid'}\n" + endpoint +
        "[rpcinterface:supervisor]\nsupervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface\n"
        + ctl + service.supervisord_program(home, tick_seconds=0.3))
    supervisor = subprocess.Popen([SUPERVISORD, "-c", str(conf)], cwd=ROOT,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        first = wait_for(lambda: heartbeat(home)["state"] == "RUNNING" and heartbeat(home), what="body start")
        # 1. Kill the body, then tear the ledger tail while it is frozen.
        os.kill(first["pid"], signal.SIGKILL)
        second = wait_for(lambda: heartbeat(home)["pid"] != first["pid"] and heartbeat(home)["state"] == "RUNNING"
                          and heartbeat(home), what="restart after SIGKILL")
        os.kill(second["pid"], signal.SIGSTOP)
        with open(home / "ledger.jsonl", "ab") as fh:
            fh.write(b'{"seq": 999999, "record_type": "event", "payload": {"type": "greg.mission.act')
        os.kill(second["pid"], signal.SIGKILL)
        wait_for(lambda: heartbeat(home)["pid"] not in (first["pid"], second["pid"])
                 and heartbeat(home)["state"] == "RUNNING", what="restart after torn write")
        assert wait_for(lambda: [b for b in events(home, "body.booted") if b.get("ledger_recovery")],
                        what="torn tail quarantined")
        # 2. The founder signs a heterogeneous cognition mission through the real CLI.
        greg(home, "cognition", "mission", "--request", str(_request(tmp_path, "r1.json", "schedule-1")),
             "--capability", "pipeline", "--id", "m:schedule", "--field", "outcome",
             "--equals", '"ANSWERED_WITHIN_SCOPE"', "--key", str(key), "--no-passphrase")
        # 3. Kill it again while the mission is in flight.
        wait_for(lambda: [e for e in events(home, "mission.registered") if e["mission_id"] == "m:schedule"],
                 what="mission registered")
        third = heartbeat(home)
        os.kill(third["pid"], signal.SIGKILL)
        wait_for(lambda: heartbeat(home)["pid"] != third["pid"] and heartbeat(home)["state"] == "RUNNING",
                 what="restart mid-mission")
        appraisal = wait_for(lambda: [a for a in events(home, "mission.appraised") if a["mission_id"] == "m:schedule"],
                             what="separate-process appraisal", timeout=90)[-1]
        assert appraisal["verdict"] == "VERIFIED", appraisal.get("findings")
        # 4. One closure despite three kills; the pipeline receipt survived and is typed.
        results = [e for e in events(home, "mission.achieved") if e.get("mission_id") == "m:schedule"]
        assert len(results) == 1
        done = _receipts(home, "schedule-1")
        assert done, "the pipeline's Gate receipt must be retained"
        output = done[0]["result"]["output"]
        assert output["outcome"] == "ANSWERED_WITHIN_SCOPE" and output["authority_created"] is False
        assert [s["id"] for s in output["stages"]] == ["extract", "validate", "solve", "handoff"]
        assert output["receipt"]["evaluator_result"]["checks"]["optimality_cross_engine"] is True
        before_detach = len(done)
        # 5. A signed detach survives a hard kill; a new pipeline mission cannot use the detached capability.
        greg(home, "detach", "cognition.pipeline", "--key", str(key), "--no-passphrase")
        wait_for(lambda: [e for e in events(home, "capability.state")
                          if e["capability_id"] == "cognition.pipeline" and e["state"] == "DETACHED"], what="detach")
        fourth = heartbeat(home)
        os.kill(fourth["pid"], signal.SIGKILL)
        wait_for(lambda: heartbeat(home)["pid"] != fourth["pid"] and heartbeat(home)["state"] == "RUNNING",
                 what="restart after detach")
        greg(home, "cognition", "mission", "--request", str(_request(tmp_path, "r2.json", "schedule-2")),
             "--capability", "pipeline", "--id", "m:schedule-2", "--field", "outcome",
             "--equals", '"ANSWERED_WITHIN_SCOPE"', "--key", str(key), "--no-passphrase")
        wait_for(lambda: [e for e in events(home, "mission.registered") if e["mission_id"] == "m:schedule-2"],
                 what="second mission registered")
        blocked = wait_for(lambda: [e for e in events(home, "decision.requested")
                                    if "cognition.pipeline" in json.dumps(e)], what="truthful capability blocker")
        import time
        time.sleep(3)                                                  # several ticks at 0.3 s
        assert not _receipts(home, "schedule-2")                       # nothing ran after the detach
        assert len(_receipts(home, "schedule-1")) == before_detach
        assert not [e for e in events(home, "mission.achieved") if e.get("mission_id") == "m:schedule-2"]
        greg(home, "stop", "--key", str(key), "--no-passphrase")
        wait_for(lambda: heartbeat(home)["state"] == "STOPPED", what="signed stop")
        if os.environ.get("GREG_RECORD_EVIDENCE"):
            out = ROOT / "tests" / "evidence" / "cognition-convergence-2026-10-01"
            out.mkdir(parents=True, exist_ok=True)
            (out / "rehearsal-summary.json").write_text(json.dumps({
                "appraisal": appraisal, "actions_done": done, "achieved": results,
                "boots": events(home, "body.booted"), "detach": events(home, "capability.state"),
                "second_mission_blocker": blocked,
                "limits": "Linux container, per-test founder key, supervisord; not the founder's Chromebook"},
                indent=1, default=str) + "\n")
    finally:
        supervisor.send_signal(signal.SIGTERM)
        supervisor.wait(timeout=30)
