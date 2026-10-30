"""The first-VEPMC acceptance path, end to end through the real product surface.

Directive §24: mission through the GREG interface -> durable -> interface closed ->
persistent supervised runtime -> real capability -> deliberate interruption ->
restore without re-prompting -> no duplicate effect -> approval boundary honored ->
evidence-backed appraisal -> inspectable episode. VEPMC is computed from the ledger.
The Linux fixture uses a test key, so even a complete structural row is not an external closure.

Run twice (#138 structural-candidate gate, ported onto the founder-tier rule). With a
--no-passphrase key the complete row is a STRUCTURAL_CANDIDATE and `greg path` stays at N1,
as N1's kill condition requires. With a passphrase-protected key, `greg body designate` also
signs the founder-tier attestation, and the same closure moves the path to N2: a genuine
founder run can clear N1. The fixture passphrase does not make the key Alfonso's; the ledger
cannot tell (greg/metrics.py founder_tier, residual).
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest

from tests.integration.test_greg_body_supervised import (ROOT, events, greg, heartbeat, history, supervisor_endpoint,
                                                         wait_for)
from greg import metrics, service
from tests.supervisor_requirement import require_supervisord

FIXTURE_PASSPHRASE = "fixture passphrase, not Alfonso's"


@pytest.fixture(autouse=True)
def supervisor_on_path():
    """Skip without supervisord, or fail under GREG_REQUIRE_SUPERVISOR=1 (tests/supervisor_requirement.py)."""
    require_supervisord("supervisord (requirements-dev) not installed")


def founder(home, passphrase, *args):
    """A founder command as Alfonso types it: GREG asks for the passphrase (here, from the environment)."""
    if passphrase is None:
        return greg(home, *args, "--no-passphrase")
    env = {**os.environ, "GREG_FOUNDER_PASSPHRASE": passphrase, "PYTHONPATH": str(ROOT)}
    proc = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return proc


@pytest.mark.parametrize("passphrase", [None, FIXTURE_PASSPHRASE], ids=["test-key", "passphrase-key"])
def test_first_vepmc_path_requires_founder_body_designation(tmp_path, passphrase):
    home, key = tmp_path / "body", tmp_path / "founder.pem"
    greg(home, "init", "--read-root", str(tmp_path))
    greg(home, "founder", "enroll", "--pubkey",
         founder(home, passphrase, "founder", "keygen", "--key", str(key)).stdout.strip())
    conf = tmp_path / "supervisord.conf"
    (home / "logs").mkdir(exist_ok=True)
    endpoint, ctl = supervisor_endpoint(tmp_path)
    conf.write_text(
        f"[supervisord]\nnodaemon=true\nlogfile={tmp_path / 'sd.log'}\npidfile={tmp_path / 'sd.pid'}\n"
        + endpoint +
        "[rpcinterface:supervisor]\nsupervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface\n"
        + ctl + service.supervisord_program(home, tick_seconds=0.3))
    supervisor = subprocess.Popen(["supervisord", "-c", str(conf)], cwd=ROOT,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        first = wait_for(lambda: heartbeat(home)["state"] == "RUNNING" and heartbeat(home), what="body start")
        founder(home, passphrase, "body", "designate", "--key", str(key))
        wait_for(lambda: events(home, "body.designated"), what="signed first body designation")
        if passphrase:                                  # the attestation is accepted before the mission is signed
            wait_for(lambda: [c for c in events(home, "command.accepted") if c["kind"] == "FOUNDER_TIER"],
                     what="founder-tier attestation")
        # 1. Mission through the GREG interface (template, signed, interface process exits).
        founder(home, passphrase, "mission", "new", "workspace-note", "--text", "the first body is alive",
                "--must-contain", "alive", "--key", str(key))
        request = wait_for(lambda: events(home, "decision.requested"), what="approval boundary")[0]
        note = home.resolve() / "workspace" / "m_first-note" / "note.txt"
        assert request["kind"] == "APPROVAL" and not note.exists()
        # 2. Deliberate interruption while the mission waits.
        os.kill(first["pid"], signal.SIGKILL)
        wait_for(lambda: heartbeat(home)["pid"] != first["pid"] and heartbeat(home)["state"] == "RUNNING",
                 what="autonomous restart")
        wait_for(lambda: events(home, "body.recovered"), what="recovery record")
        # 3. Founder approval through the signed inbox; mission resumes without restatement.
        founder(home, passphrase, "decide", request["request_id"], "approve", "--key", str(key))
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
        founder(home, passphrase, "accept", event_id, "--key", str(key))
        wait_for(lambda: events(home, "critique.recorded"), what="founder acceptance")
        vepmc = json.loads(greg(home, "vepmc").stdout)
        row = next(r for r in vepmc["missions"] if r["mission_id"] == "m:first-note")
        assert row["missing"] == [] and row["founder_body"], row
        # Structurally complete fixture; test key and test machine cannot establish external VEPMC.
        assert vepmc["VEPMC"] == 1 and vepmc["external_confirmation_required"]
        assert vepmc["structural_candidate_count"] == 1
        done = [a for a in events(home, "mission.action") if a["status"] == "DONE"]
        assert len(done) == 1  # exactly one consequence across kill/restart
        path = json.loads(greg(home, "path").stdout)
        n1 = path["active"]["measurement"] if path["active"]["id"] == "N1" else None
        if passphrase is None:                          # N1's kill condition: a closure counted with a test key
            assert row["evidence_level"] == vepmc["evidence_level"] == metrics.STRUCTURAL_CANDIDATE
            assert vepmc["founder_tier_count"] == 0 and row["not_founder_tier"] == metrics.NOT_FOUNDER_TIER
            assert path["achieved"] == ["N0"] and n1 and n1["structurally_met"] and not n1["met"]
            assert n1["not_founder_tier"] == {"m:first-note": metrics.NOT_FOUNDER_TIER}
        else:                                           # the same closure, signed at the founder tier, moves it
            assert row["evidence_level"] == vepmc["evidence_level"] == metrics.FOUNDER_TIER
            assert vepmc["founder_tier_count"] == 1 and "not_founder_tier" not in row
            assert path["achieved"] == ["N0", "N1"] and path["active"]["id"] == "N2"
        founder(home, passphrase, "stop", "--key", str(key))
        wait_for(lambda: heartbeat(home)["state"] == "STOPPED", what="founder stop")
        if os.environ.get("GREG_RECORD_EVIDENCE") and passphrase is None:
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
