"""The acceptance report claims no more than its evidence shows.

Two defects the device-preparation lane reproduced on #196 b1950be2 (2026-10-30):
- a body designated and run with a test key, which ``install.sh --no-passphrase --allow-other-linux`` produces, was
  labelled FOUNDER-DEVICE;
- ``supervised_runtime`` passed on a heartbeat whose process was dead.

A per-test key stands in for the founder throughout; nothing here is founder-device evidence.
"""
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from greg import acceptance
from greg.acceptance import report
from greg.body import Body
from greg.templates import first_mission
from tests.greg_fixtures import TEST_PASSPHRASE, attest_founder_tier, drop, make_body, signed
from tests.integration.test_greg_first_mission import kernel_copy, run_until_settled


def designated_first_mission(tmp_path, monkeypatch=None, *, attested: bool):
    """A designated body whose First Mission closes; its key attested passphrase custody first only if asked."""
    home, key, body_id, _ = make_body(tmp_path, passphrase=TEST_PASSPHRASE if attested else None)
    with Body(home) as body:
        body.apply(signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}))
    if attested:
        attest_founder_tier(home, tmp_path / "founder.pem", TEST_PASSPHRASE, monkeypatch)
        with Body(home) as body:              # the attestation is applied before the mission is registered
            body.boot()
            body.tick()
    spec = first_mission(kernel_root=str(kernel_copy(tmp_path)), effort_budget=8, run="test")
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.dp_knapsack"}), "a.json")
    drop(home, signed(key, body_id, "MISSION", spec), "m.json")
    out, _ = run_until_settled(home)
    assert out["missions"][0]["state"] == "ACHIEVED", out
    return home


def test_a_designated_body_whose_mission_a_test_key_signed_is_not_founder_device(tmp_path):
    result = report(designated_first_mission(tmp_path, attested=False))
    assert result["first_mission"]["founder_body"] is True              # it did run on the designated body
    assert result["reality"].startswith("LOCAL-DESIGNATED"), result["reality"]   # before: FOUNDER-DEVICE
    assert "FOUNDER-DEVICE" not in result["reality"] and "passphrase custody" in result["reality"]


def test_a_designated_body_whose_mission_a_founder_tier_key_signed_reads_founder_device(tmp_path, monkeypatch):
    result = report(designated_first_mission(tmp_path, monkeypatch, attested=True))
    assert result["reality"].startswith("FOUNDER-DEVICE"), result["reality"]
    assert "not provable from a ledger" in result["reality"]           # the limit is still stated


def runtime_status(home, **heartbeat):
    (home / "heartbeat.json").write_text(json.dumps({"boot_id": "b", "ledger_head": None, "missions": [],
                                                     **heartbeat}))
    result = report(home)
    return {p["property"]: p["status"] for p in result["properties"]}["supervised_runtime"]


def dead_pid() -> int:
    child = subprocess.Popen(["true"])
    child.wait()
    return child.pid


def now(seconds_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def test_a_heartbeat_from_a_live_process_written_just_now_is_a_running_body(tmp_path):
    home, *_ = make_body(tmp_path)
    for state in ("RUNNING", "PAUSED"):
        assert runtime_status(home, pid=os.getpid(), at=now(), state=state) == "PASS"   # this process predates it


@pytest.mark.parametrize("why, heartbeat", [
    ("its process is dead", lambda: {"pid": dead_pid(), "at": now(5), "state": "RUNNING"}),     # before: PASS
    ("it is older than three minutes", lambda: {"pid": os.getpid(), "at": now(600), "state": "RUNNING"}),
    ("it has no time", lambda: {"pid": os.getpid(), "state": "RUNNING"}),
    ("its time is not a time", lambda: {"pid": os.getpid(), "at": "yesterday", "state": "RUNNING"}),
    ("it is dated in the future", lambda: {"pid": os.getpid(), "at": now(-600), "state": "RUNNING"}),
    ("it names no process", lambda: {"at": now(5), "state": "RUNNING"}),
    ("its process is not a number", lambda: {"pid": True, "at": now(5), "state": "RUNNING"}),
    ("the body is held", lambda: {"pid": os.getpid(), "at": now(5), "state": "HELD"}),
])
def test_a_heartbeat_is_not_a_running_body_when(tmp_path, monkeypatch, why, heartbeat):
    # Each case tests one reason alone, so its process is taken to predate the heartbeat: this test process may well
    # have started after a heartbeat dated minutes ago, which would fail every case for that reason instead.
    # The start time itself is read for real by the live-process test and the reused-pid test.
    monkeypatch.setattr(acceptance, "_started_after", lambda pid, at: False, raising=False)
    home, *_ = make_body(tmp_path)
    assert runtime_status(home, **heartbeat()) == "NOT_YET", why


def test_a_process_started_after_the_heartbeat_did_not_write_it(tmp_path):
    """The independent review of #231: any live process with the heartbeat's pid counted. A process that started after
    the heartbeat was written holds a reused pid, not the writer's (Linux; elsewhere the start time is not read)."""
    home, *_ = make_body(tmp_path)
    late = subprocess.Popen(["sleep", "60"])
    try:
        assert runtime_status(home, pid=late.pid, at=now(30), state="RUNNING") == "NOT_YET"      # before: PASS
        assert acceptance._runtime({"pid": late.pid, "at": now(30), "state": "RUNNING"})["started_after_heartbeat"]
    finally:
        late.kill()
        late.wait()


def test_no_heartbeat_at_all_is_not_a_running_body(tmp_path):
    home, *_ = make_body(tmp_path)
    assert {p["property"]: p["status"] for p in report(home)["properties"]}["supervised_runtime"] == "NOT_YET"


def test_the_report_names_the_signature_tier_and_the_runtime_it_read(tmp_path):
    """A reviewer sees why the label and the runtime property read as they do, not only the verdicts."""
    home = designated_first_mission(tmp_path, attested=False)
    result = report(home)
    assert result["signature_tier"]["tier"] == "STRUCTURAL_CANDIDATE"
    assert "passphrase custody" in result["signature_tier"]["why_not"]
    pid = dead_pid()
    (home / "heartbeat.json").write_text(json.dumps({"pid": pid, "at": now(5), "state": "RUNNING"}))
    runtime = report(home)["runtime"]
    assert runtime == {"running": False, "state": "RUNNING", "pid": pid, "process_alive": False,
                       "started_after_heartbeat": None,
                       "age_seconds": runtime["age_seconds"]} and 0 <= runtime["age_seconds"] < 180
