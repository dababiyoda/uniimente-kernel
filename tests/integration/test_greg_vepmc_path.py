"""The first-VEPMC acceptance path, end to end through the real product surface.

Directive §24: mission through the GREG interface -> durable -> interface closed ->
persistent supervised runtime -> real capability -> deliberate interruption ->
restore without re-prompting -> no duplicate effect -> approval boundary honored ->
evidence-backed appraisal -> inspectable episode. VEPMC is computed from the ledger.
On Linux every condition can be met EXCEPT ``mac_body``; the key is a test key.
"""
import json
import os
from pathlib import Path
import signal
import subprocess

import pytest

from tests.integration.test_greg_body_supervised import (ROOT, SUPERVISORD, events, greg, heartbeat, history,
                                                         wait_for)
from greg import service

pytestmark = pytest.mark.skipif(SUPERVISORD is None, reason="supervisord (requirements-dev) not installed")


def test_first_vepmc_path_meets_every_condition_except_the_mac(tmp_path):
    home, key = tmp_path / "body", tmp_path / "founder.pem"
    greg(home, "init", "--read-root", str(tmp_path))
    greg(home, "founder", "enroll", "--pubkey",
         greg(home, "founder", "keygen", "--key", str(key), "--no-passphrase").stdout.strip())
    conf = tmp_path / "supervisord.conf"
    (home / "logs").mkdir(exist_ok=True)
    conf.write_text(
        f"[supervisord]\nnodaemon=true\nlogfile={tmp_path / 'sd.log'}\npidfile={tmp_path / 'sd.pid'}\n"
        f"[unix_http_server]\nfile={tmp_path / 'sd.sock'}\n"
        "[rpcinterface:supervisor]\nsupervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface\n"
        f"[supervisorctl]\nserverurl=unix://{tmp_path / 'sd.sock'}\n" + service.supervisord_program(home, tick_seconds=0.3))
    supervisor = subprocess.Popen(["supervisord", "-c", str(conf)], cwd=ROOT,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        first = wait_for(lambda: heartbeat(home)["state"] == "RUNNING" and heartbeat(home), what="body start")
        # 1. Mission through the GREG interface (template, signed, interface process exits).
        greg(home, "mission", "new", "workspace-note", "--text", "the first body is alive",
             "--must-contain", "alive", "--key", str(key), "--no-passphrase")
        request = wait_for(lambda: events(home, "decision.requested"), what="approval boundary")[0]
        note = home.resolve() / "workspace" / "m_first-note" / "note.txt"
        assert request["kind"] == "APPROVAL" and not note.exists()
        # 2. Deliberate interruption while the mission waits.
        os.kill(first["pid"], signal.SIGKILL)
        wait_for(lambda: heartbeat(home)["pid"] != first["pid"] and heartbeat(home)["state"] == "RUNNING",
                 what="autonomous restart")
        wait_for(lambda: events(home, "body.recovered"), what="recovery record")
        # 3. Founder approval through the signed inbox; mission resumes without restatement.
        greg(home, "decide", request["request_id"], "approve", "--key", str(key), "--no-passphrase")
        appraisal = wait_for(lambda: events(home, "mission.appraised"), what="independent appraisal")[0]
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        assert note.read_text() == "the first body is alive"
        # 4. Morning tribunal: founder accepts the closure with a signed critique.
        # The founder reads the closure id from the product surface, not the journal.
        before = json.loads(greg(home, "vepmc").stdout)
        event_id = next(r for r in before["missions"] if r["mission_id"] == "m:first-note")["closure_event_id"]
        ledger, journal = history(home)
        try:
            assert event_id == journal.replay("mission.achieved")[0].event_id
        finally:
            ledger.close()
        greg(home, "accept", event_id, "--key", str(key), "--no-passphrase")
        wait_for(lambda: events(home, "critique.recorded"), what="founder acceptance")
        vepmc = json.loads(greg(home, "vepmc").stdout)
        row = next(r for r in vepmc["missions"] if r["mission_id"] == "m:first-note")
        assert row["missing"] == ([] if os.uname().sysname == "Darwin" else ["mac_body"]), row
        assert vepmc["VEPMC"] == (1 if os.uname().sysname == "Darwin" else 0)
        done = [a for a in events(home, "mission.action") if a["status"] == "DONE"]
        assert len(done) == 1  # exactly one consequence across kill/restart
        greg(home, "stop", "--key", str(key), "--no-passphrase")
        wait_for(lambda: heartbeat(home)["state"] == "STOPPED", what="founder stop")
        if os.environ.get("GREG_RECORD_EVIDENCE"):
            out = ROOT / "tests" / "evidence" / "greg-body"
            out.mkdir(parents=True, exist_ok=True)
            (out / "vepmc-path-summary.json").write_text(json.dumps({
                "vepmc": vepmc, "appraisal": appraisal, "decision": request,
                "recovered": events(home, "body.recovered"), "actions": events(home, "mission.action"),
                "founder_key": "per-test Ed25519 key; NOT Alfonso", "platform": os.uname().sysname}, indent=1))
            Path(out / "vepmc-path-ledger.jsonl").write_bytes((home / "ledger.jsonl").read_bytes())
    finally:
        supervisor.send_signal(signal.SIGTERM)
        try:
            supervisor.wait(timeout=20)
        except subprocess.TimeoutExpired:
            supervisor.kill()
