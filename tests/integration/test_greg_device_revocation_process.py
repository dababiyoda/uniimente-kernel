"""Mission K (founder shutdown) at the real-process tier: revoked authority stays revoked.

Directive 2026-10-13 section 33, Mission K: "Verify that revoked authority is not restored by restart or another
worker." A running `greg run` Body holds two founder-delegated device keys (a phone and a laptop). The founder
revokes the phone. From then on the phone's answer, signed by its own `greg decide` process, is refused as data,
before and after a SIGKILL restart; the laptop, another delegated device, cannot re-enroll the phone (only the
founder key may delegate); and the laptop's own still-valid answer is honoured, so the refusal is specific to the
revoked key, not a stalled body.

Every key is a per-test Ed25519 key, not Alfonso's.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from greg.body import Body, observe
from greg.founder import generate_founder_key, key_id, load_founder_key, sign_command, stamp
from tests.greg_fixtures import drop, make_body, mission, note_check, workspace, write_strategy

ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": str(ROOT), "GREG_FOUNDER_PASSPHRASE": ""}
MID = "m:revoke"


def start(home: Path, log: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", "0.1"],
                            cwd=ROOT, env=ENV, stdout=log.open("a"), stderr=subprocess.STDOUT)


def stop(body: subprocess.Popen, sig=signal.SIGTERM) -> None:
    body.send_signal(sig)
    try:
        body.wait(timeout=30)
    except subprocess.TimeoutExpired:
        body.kill()
        body.wait(timeout=10)


def events(home: Path, prefix: str) -> list[dict]:
    with observe(home, actor="spiffe://uniimente.internal/greg/revocation-process-test") as journal:
        return [e.payload for e in journal.replay(prefix)]


def wait_for(predicate, *, timeout=90, what="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
        except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError):
            value = None
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {what}")


def decide(home: Path, rid: str, key_file: Path) -> None:
    """A device answers from its own process, signing with its own key file."""
    proc = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "decide", rid, "approve", "--reason",
                           "approve from a device", "--key", str(key_file), "--no-passphrase"],
                          cwd=ROOT, env=ENV, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-2000:]


def revoked_refusals(home: Path) -> list[dict]:
    return [r for r in events(home, "command.rejected") if "not enrolled or revoked" in r["reason"]]


def test_a_revoked_device_stays_revoked_across_a_kill_and_no_other_device_can_restore_it(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    log, note = tmp_path / "body.log", workspace(home, MID) / "n.txt"
    devices = {name: generate_founder_key(tmp_path / f"{name}.pem", None) for name in ("phone", "laptop")}
    expires = stamp(datetime.now(timezone.utc) + timedelta(days=30))
    for name, public in devices.items():
        drop(home, sign_command(key, "DEVICE_ENROLL", {"public_key": public, "label": name, "kinds": ["DECISION"],
                                                       "expires_at": expires}, body_id=body_id), f"a-{name}.json")
    drop(home, sign_command(key, "MISSION", mission(MID, checks=[note_check("n", note, "approved")],
                                                    strategies=[write_strategy("w", "n.txt", "approved", ["n"])],
                                                    capabilities=["fs.read"], ceiling="read_only"),
                            body_id=body_id), "b-mission.json")      # the write is outside the cone: it asks

    body = start(home, log)
    try:
        wait_for(lambda: len(events(home, "device.enrolled")) == 2, what="both delegations")
        [ask] = wait_for(lambda: [r for r in events(home, "decision.requested") if r["mission_id"] == MID],
                         what="the founder ask")
        drop(home, sign_command(key, "DEVICE_REVOKE", {"device_key_id": key_id(devices["phone"])},
                                body_id=body_id), "c-revoke.json")
        wait_for(lambda: events(home, "device.revoked"), what="the revocation")
        decide(home, ask["request_id"], tmp_path / "phone.pem")
        wait_for(lambda: len(revoked_refusals(home)) == 1, what="the revoked phone's refusal")
        time.sleep(1.0)
        assert not note.exists() and events(home, "decision.answered") == []
    finally:
        stop(body, signal.SIGKILL)

    body = start(home, log)
    try:
        wait_for(lambda: events(home, "body.recovered"), what="the restart")
        decide(home, ask["request_id"], tmp_path / "phone.pem")          # a restart restores nothing
        wait_for(lambda: len(revoked_refusals(home)) == 2, what="the second refusal")
        laptop = load_founder_key(tmp_path / "laptop.pem", None)
        drop(home, sign_command(laptop, "DEVICE_ENROLL", {"public_key": devices["phone"], "label": "phone",
                                                          "kinds": ["DECISION"], "expires_at": expires},
                                body_id=body_id), "d-reenroll.json")     # another device cannot restore it
        wait_for(lambda: len(events(home, "command.rejected")) == 3, what="the re-enrollment's refusal")
        time.sleep(1.0)
        assert not note.exists() and events(home, "decision.answered") == []
        decide(home, ask["request_id"], tmp_path / "laptop.pem")         # a still-valid device is honoured
        wait_for(lambda: note.exists() and note.read_text() == "approved", what="the laptop-approved write")
        time.sleep(1.0)
    finally:
        stop(body)

    with Body(home) as b:
        assert b.ledger.verify_chain()[0]
        assert set(b.device_keys()) == {key_id(devices["laptop"])}
        assert len(events(home, "device.enrolled")) == 2 and len(events(home, "device.revoked")) == 1
        rejected = events(home, "command.rejected")
        assert [r["file"] for r in rejected if r["file"] == "d-reenroll.json"] == ["d-reenroll.json"]
        assert all(r["instruction_status"] == "data_only" for r in rejected)
        done = [a for a in events(home, "mission.action") if a["mission_id"] == MID and a["status"] == "DONE"]
        assert [a["action_id"] for a in done] == ["w"]
