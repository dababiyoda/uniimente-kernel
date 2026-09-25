"""Real processes, commodity supervisor, hard kill, autonomous recovery, founder stop.

Nothing here is simulated except the founder key (a per-test Ed25519 key, not
Alfonso's). The body runs as its own OS process under supervisord; interfaces
are separate CLI processes that exit immediately; the test only observes files
and retained history, and sends real signals.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest

from events.spine import EventSpine
from greg import service
from greg.journal import Journal
from provenance.ledger import EvidenceLedger

ROOT = Path(__file__).resolve().parents[2]
SUPERVISORD = shutil.which("supervisord")
pytestmark = pytest.mark.skipif(SUPERVISORD is None, reason="supervisord (requirements-dev) not installed; "
                                                            "no substitute supervisor is used")


def greg(home, *args, check=True):
    env = {**os.environ, "GREG_FOUNDER_PASSPHRASE": "", "PYTHONPATH": str(ROOT)}
    proc = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60)
    if check:
        assert proc.returncode == 0, proc.stderr[-2000:]
    return proc


def history(home):
    config = json.loads((Path(home) / "body.json").read_text())
    ledger = EvidenceLedger(config["constitution_hash"], str(Path(home) / "ledger.jsonl"), read_only=True)
    journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/greg/test-observer")
    return ledger, journal


def wait_for(predicate, timeout=40, what="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            value = None
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {what}")


def heartbeat(home):
    return json.loads((Path(home) / "heartbeat.json").read_text())


def events(home, prefix):
    ledger, journal = history(home)
    try:
        return [e.payload for e in journal.replay(prefix)]
    finally:
        ledger.close()


def test_body_survives_hard_kill_waits_for_founder_and_stops_on_command(tmp_path):
    home, data, key = tmp_path / "body", tmp_path / "data", tmp_path / "founder.pem"
    data.mkdir()
    greg(home, "init", "--read-root", str(data))
    public = greg(home, "founder", "keygen", "--key", str(key), "--no-passphrase").stdout.strip()
    greg(home, "founder", "enroll", "--pubkey", public)

    conf = tmp_path / "supervisord.conf"
    (home / "logs").mkdir(exist_ok=True)
    conf.write_text(
        f"[supervisord]\nnodaemon=true\nlogfile={tmp_path / 'supervisord.log'}\npidfile={tmp_path / 'sd.pid'}\n"
        f"[unix_http_server]\nfile={tmp_path / 'sd.sock'}\n"
        "[rpcinterface:supervisor]\nsupervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface\n"
        f"[supervisorctl]\nserverurl=unix://{tmp_path / 'sd.sock'}\n"
        + service.supervisord_program(home, tick_seconds=0.3))
    supervisor = subprocess.Popen([SUPERVISORD, "-c", str(conf)], cwd=ROOT,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        first = wait_for(lambda: heartbeat(home)["state"] == "RUNNING" and heartbeat(home), what="body start")
        workspace = home.resolve() / "workspace" / "m_overnight-report"
        horizon = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
        spec = {
            "mission_id": "m:overnight-report", "founder_expression": "Prepare my overnight status report.",
            "intended_effect": "a report file exists in the mission workspace", "priority": 80,
            "closure": {"kind": "bounded"},
            "success_checks": [{"check_id": "report", "description": "report written",
                                "sensor": {"capability": "fs.read", "params": {"path": str(workspace / "report.txt")},
                                           "target": "fs:report.txt"},
                                "predicate": {"op": "contains", "field": "text", "value": "overnight"}}],
            "strategies": [{"action_id": "write-report", "capability": "fs.write",
                            "params": {"relative_path": "report.txt", "content": "overnight: all systems nominal"},
                            "target": "workspace:report.txt", "advances": ["report"],
                            "rationale": "write the report (requires founder approval: outside read-only scope)"}],
            "light_cone": {"capabilities": ["fs.read"], "targets": ["fs:*", "workspace:*"],
                           "max_consequence_class": "read_only", "budget_usd": 0, "horizon": horizon}}
        mission_file = tmp_path / "mission.json"
        mission_file.write_text(json.dumps(spec))
        greg(home, "mission", "submit", str(mission_file), "--key", str(key), "--no-passphrase")  # interface exits

        request = wait_for(lambda: events(home, "decision.requested"), what="approval request")[0]
        assert request["kind"] == "APPROVAL" and not (workspace / "report.txt").exists()

        # Hard kill while the mission waits at the approval boundary.
        os.kill(first["pid"], signal.SIGKILL)
        second = wait_for(lambda: heartbeat(home)["pid"] != first["pid"] and heartbeat(home)["state"] == "RUNNING"
                          and heartbeat(home), what="supervisor restart")
        assert wait_for(lambda: events(home, "body.recovered"), what="recovery record")
        time.sleep(1.5)  # several ticks while blocked
        assert len(events(home, "decision.requested")) == 1  # remembered, not re-escalated

        greg(home, "decide", request["request_id"], "approve", "--reason", "go ahead",
             "--key", str(key), "--no-passphrase")
        wait_for(lambda: events(home, "mission.achieved"), what="mission closure")
        assert (workspace / "report.txt").read_text().startswith("overnight")
        done = [a for a in events(home, "mission.action") if a["status"] == "DONE"]
        assert len(done) == 1 and done[0]["receipt"]  # exactly one consequence, receipted

        greg(home, "stop", "--key", str(key), "--no-passphrase")
        wait_for(lambda: heartbeat(home)["state"] == "STOPPED", what="founder stop")
        time.sleep(2.0)
        status = subprocess.run(["supervisorctl", "-c", str(conf), "status"], capture_output=True, text=True)
        assert "EXITED" in status.stdout, status.stdout  # deliberate stop is not restarted

        ledger, journal = history(home)
        try:
            ok, why = ledger.verify_chain()
            assert ok, why
            boots = journal.replay("body.booted")
            stops = journal.replay("body.stopped")
            assert len(boots) == 2 and len(stops) == 1 and second["boot_id"] == boots[1].payload["boot_id"]
            assert len(ledger.by_type("receipt")) == len({r.payload["grant_id"] for r in ledger.by_type("receipt")})
        finally:
            ledger.close()
        evidence_dir = ROOT / "tests" / "evidence" / "greg-body"
        if os.environ.get("GREG_RECORD_EVIDENCE"):
            evidence_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(home / "ledger.jsonl", evidence_dir / "supervised-run-ledger.jsonl")
            (evidence_dir / "supervised-run-summary.json").write_text(json.dumps({
                "boots": [b.payload for b in boots], "recovered": events(home, "body.recovered"),
                "decision_requests": events(home, "decision.requested"), "actions": events(home, "mission.action"),
                "achieved": events(home, "mission.achieved"), "supervisor_status": status.stdout.strip(),
                "founder_key": "per-test Ed25519 key; NOT Alfonso"}, indent=1))
    finally:
        supervisor.send_signal(signal.SIGTERM)
        try:
            supervisor.wait(timeout=20)
        except subprocess.TimeoutExpired:
            supervisor.kill()
