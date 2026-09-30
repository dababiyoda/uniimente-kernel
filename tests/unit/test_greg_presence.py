"""Body presence on part-time hardware: measured, never implied.

The founder's first body is a Chromebook (2026-09-26 correction): ChromeOS kills Linux
processes at logout, never restarts the VM at login, and suspends it with the lid. A
morning report that says nothing failed while GREG was absent all night misstates
persistence. These tests pin what the body can truthfully know about its own absence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from greg import doctor, presence, tribunal
from greg.body import Body, status
from greg.journal import iso
from tests.greg_fixtures import Clock, make_body

T0 = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[2]


def at(hours: float) -> str:
    return iso(T0 + timedelta(hours=hours))


def boot(journal, boot_id, hours, previous=None):
    payload = {"boot_id": boot_id, "at": at(hours), "pid": 1, "version": "t", "body_id": "b", "boot_number": 0,
               "platform": "Linux", "ledger_head_at_boot": "x"}
    if previous:
        payload["previous_heartbeat"] = {"boot_id": previous[0], "at": at(previous[1]), "state": "RUNNING",
                                         "source": "heartbeat file"}
    journal.record("body.booted", payload, key=boot_id)


def stop(journal, boot_id, hours, reason):
    journal.record("body.stopped", {"boot_id": boot_id, "reason": reason, "at": at(hours), "ledger_head": "x"},
                   key=[boot_id, "stopped"])


@pytest.fixture
def journal(tmp_path):
    home, *_ = make_body(tmp_path)
    body = Body(home).open()
    yield body.journal
    body.close()


def test_absences_are_classified_bounded_and_deliberate_stops_do_not_count(journal):
    boot(journal, "b1", 0)                                   # runs 0h..2h, then SIGKILL (no stop record)
    boot(journal, "b2", 5, previous=("b1", 2))               # heartbeat bounds the death to 2h
    journal.record("body.gap_observed", {"boot_id": "b2", "from": at(6), "to": at(9), "cause": "host_suspended",
                                         "wall_seconds": 10800.0, "monotonic_seconds": 4.0, "evidence": "e"},
                   key=["b2", "gap"])
    stop(journal, "b2", 10, "founder BODY_STOP or signal")   # SIGTERM at logout: counts
    boot(journal, "b3", 11, previous=("b2", 10))
    stop(journal, "b3", 12, "local STOP file")               # the founder stopped it: does not count
    boot(journal, "b4", 20, previous=("b3", 12))
    s = presence.summary(journal, now=T0 + timedelta(hours=24))
    causes = [(a["cause"], a["seconds"] / 3600, a["counts"]) for a in s["absences"]]
    assert causes == [("process_lost", 3.0, True), ("host_suspended", 3.0, True),
                      ("os_stop_or_shutdown", 1.0, True), ("deliberate_stop", 8.0, False)]
    # present: b1 2h + b2 (5h - 3h suspended) + b3 1h + b4 4h = 9h; eligible 24h - 8h deliberate = 16h
    assert s["present_seconds"] == 9 * 3600 and s["deliberately_stopped_seconds"] == 8 * 3600
    assert s["availability"] == round(9 / 16, 4) and s["state"] == "RUNNING"


def test_a_boot_with_no_evidence_of_its_duration_counts_none_of_it(journal):
    boot(journal, "b1", 0)
    boot(journal, "b2", 6)                                    # no heartbeat, no stop: unknown run time
    s = presence.summary(journal, now=T0 + timedelta(hours=8))
    assert s["absences"][0]["cause"] == "process_lost" and s["absences"][0]["end_uncertain"]
    assert s["present_seconds"] == 2 * 3600 and s["availability"] == 0.25


def test_the_window_clips_history_and_a_silent_last_process_is_reported_not_assumed_running(journal):
    boot(journal, "b1", 0)
    stale = {"boot_id": "b1", "at": at(3), "state": "RUNNING"}
    s = presence.summary(journal, now=T0 + timedelta(hours=10), since=T0 + timedelta(hours=2), heartbeat=stale)
    assert s["state"] == "NOT_REPORTING" and s["present_seconds"] == 3600
    assert s["absences"] == [{"from": at(3), "to": None, "cause": "not_reporting", "counts": True,
                              "seconds": 7 * 3600.0,
                              "detail": "the last process stopped writing its heartbeat and recorded no stop"}]
    fresh = {"boot_id": "b1", "at": at(10), "state": "RUNNING"}
    assert presence.summary(journal, now=T0 + timedelta(hours=10), heartbeat=fresh)["state"] == "RUNNING"


def test_due_observations_inside_an_absence_are_reported_late_with_their_cost(journal):
    boot(journal, "b1", 0)
    boot(journal, "b2", 9, previous=("b1", 1))
    journal.record("mission.schedule", {"mission_id": "m:watch", "next_observe_at": at(4)}, key=["m", 4])
    journal.record("mission.schedule", {"mission_id": "m:watch", "next_observe_at": at(0.5)}, key=["m", 0.5])
    for hours in (0.5, 9.01):
        journal.record("mission.observed", {"mission_id": "m:watch", "check_id": "c", "passed": True,
                                            "detail": "", "at": at(hours)}, key=["o", hours])
    late = presence.summary(journal, now=T0 + timedelta(hours=10))["late_observations"]
    assert late == [{"mission_id": "m:watch", "due": at(4), "observed": at(9.01), "late_seconds": 5.01 * 3600}]


def test_note_gap_distinguishes_host_sleep_from_a_stalled_process_and_ignores_jitter(journal):
    t = T0
    assert presence.note_gap(journal, "b1", (t, 100.0), (t + timedelta(seconds=31), 131.0)) is None
    assert presence.note_gap(journal, "b1", (t, 100.0), (t - timedelta(hours=1), 101.0)) is None   # clock stepped back
    slept = presence.note_gap(journal, "b1", (t, 100.0), (t + timedelta(hours=8), 101.0))
    stalled = presence.note_gap(journal, "b1", (t, 100.0), (t + timedelta(minutes=20), 1300.0))
    assert slept.payload["cause"] == "host_suspended" and stalled.payload["cause"] == "process_stalled"
    assert presence.note_gap(journal, "b1", (t, 100.0), (t + timedelta(hours=8), 101.0)).event_id == slept.event_id


def test_boot_records_the_previous_processes_last_heartbeat(tmp_path):
    home, *_ = make_body(tmp_path)
    clock = Clock(T0)
    first = Body(home, clock=clock).open()
    first.boot()
    clock.advance(40)
    first._heartbeat("RUNNING", [])
    first.close()                                             # killed: no body.stopped
    clock.advance(3 * 3600)
    second = Body(home, clock=clock).open()
    record = second.boot()
    second.close()
    assert record["previous_heartbeat"]["boot_id"] == first.boot_id
    assert record["previous_heartbeat"]["at"] == iso(T0 + timedelta(seconds=40))
    (home / "heartbeat.json").write_text("{torn")
    third = Body(home, clock=clock).open()
    assert "previous_heartbeat" not in third.boot()           # a torn file is not evidence
    third.close()


def test_the_running_loop_records_host_sleep_from_clock_divergence(tmp_path):
    home, *_ = make_body(tmp_path)
    clock = Clock(T0)
    calls = []

    def monotonic():                                          # the host sleeps 8h during the first wait
        calls.append(len(calls))
        if len(calls) == 1:
            clock.advance(8 * 3600)
        return 100.0 + len(calls)

    assert Body(home, clock=clock, monotonic=monotonic).run(tick_seconds=0.01, max_ticks=2) == 0
    with Body(home) as body:
        gaps = [e.payload for e in body.journal.replay("body.gap_observed")]
    assert [(g["cause"], g["wall_seconds"], g["monotonic_seconds"]) for g in gaps] == [("host_suspended", 28800.0, 1.0)]


def _shortfall(journal):
    boot(journal, "b1", 0)
    for day in range(3):                                      # present 8h a day, then logout (SIGTERM)
        stop(journal, f"b{day + 1}", 24 * day + 8, "founder BODY_STOP or signal")
        boot(journal, f"b{day + 2}", 24 * (day + 1), previous=(f"b{day + 1}", 24 * day + 8))
        journal.record("mission.schedule", {"mission_id": "m:daily", "next_observe_at": at(24 * day + 12)},
                       key=["m", day])
        journal.record("mission.observed", {"mission_id": "m:daily", "check_id": "c", "passed": True,
                                            "detail": "", "at": at(24 * (day + 1) + 0.1)}, key=["o", day])


def test_a_sustained_shortfall_becomes_one_bounded_founder_decision(journal):
    _shortfall(journal)
    now = T0 + timedelta(hours=73)
    assert presence.recommend(journal, now=T0 + timedelta(hours=20)) is None      # under 24h of history
    request = presence.recommend(journal, now=now, platform_hint="chromeos")
    assert request["kind"] == "BODY_AVAILABILITY" and request["mission_id"] is None
    assert request["authority_requested"] == {"spend": "none requested; any purchase, rental or enrollment is "
                                                        "a separate founder decision"}
    assert "never the body's own continuation" in request["argued_from"]
    assert "Linux terminal" in request["alternatives"][0] and "do nothing" in request["alternatives"][-1]
    assert request["evidence"]["availability"] < presence.AVAILABILITY_THRESHOLD
    assert presence.recommend(journal, now=now) is None                           # one open request at a time
    journal.record("decision.answered", {"request_id": request["request_id"], "answer": "reject"},
                   key=[request["request_id"], "answered"])
    assert presence.recommend(journal, now=now + timedelta(minutes=5)) is None    # one per week
    asked = [e for e in journal.replay("decision.requested") if e.payload["kind"] == "BODY_AVAILABILITY"]
    assert len(asked) == 1


def test_low_availability_without_late_work_asks_nothing(journal):
    boot(journal, "b1", 0)
    stop(journal, "b1", 2, "founder BODY_STOP or signal")
    boot(journal, "b2", 60, previous=("b1", 2))
    assert presence.summary(journal, now=T0 + timedelta(hours=73))["availability"] < 0.5
    assert presence.recommend(journal, now=T0 + timedelta(hours=73)) is None


def test_morning_report_and_status_answer_whether_greg_was_present(tmp_path):
    home, *_ = make_body(tmp_path)
    Body(home).run(tick_seconds=0.01, max_ticks=2)
    with Body(home) as body:
        report = tribunal.morning_report(body.journal, body.engine)
    q0 = report["q0_was_i_present"]
    assert q0["boots"] == 1 and q0["state"] == "STOPPED" and q0["availability"] is not None
    assert "no continuous operation beyond the presence measured in q0" in report["claims_not_made"]
    assert status(home)["presence"]["boots"] == 1


def test_doctor_names_the_crostini_venv_gap_and_detects_chromeos_only_from_markers(tmp_path):
    report = doctor.chromebook()
    assert "python_venv_available" in report["checks"] and isinstance(report["crostini_detected"], bool)
    marker = tmp_path / ".cros_milestone"
    assert not doctor.is_crostini((str(marker),))
    marker.write_text("129")
    assert doctor.is_crostini((str(marker),))


def test_a_real_sigkilled_body_process_leaves_an_absence_bounded_by_its_last_heartbeat(tmp_path):
    home, *_ = make_body(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    cmd = [sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", "0.2"]
    child = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    heartbeat = home / "heartbeat.json"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not (heartbeat.exists() and '"RUNNING"' in heartbeat.read_text()):
        time.sleep(0.05)
    assert heartbeat.exists(), child.stderr.read() if child.poll() is not None else "no heartbeat"
    child.send_signal(signal.SIGKILL)
    child.wait(timeout=10)
    killed_at = datetime.now(timezone.utc)
    time.sleep(2.0)
    subprocess.run(cmd + ["--max-ticks", "1"], cwd=ROOT, env=env, check=True, capture_output=True, timeout=60)
    out = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "presence"], cwd=ROOT, env=env,
                         check=True, capture_output=True, text=True, timeout=60)
    s = json.loads(out.stdout)
    lost = [a for a in s["absences"] if a["cause"] == "process_lost"]
    assert s["boots"] == 2 and len(lost) == 1 and "end_uncertain" not in lost[0]   # bounded by the heartbeat
    assert s["present_seconds"] > 0                          # the killed process's running time is counted
    assert 2.0 <= lost[0]["seconds"] <= 2.0 + 5.0            # the sleep, plus at most a tick and restart time
    assert presence._t(lost[0]["from"]) <= killed_at


@pytest.mark.parametrize("garbage", [{"boot_id": "b1", "at": "2026-10-01T09:00:00", "state": "RUNNING"},
                                     {"boot_id": "b1", "at": "not a time"}, ["b1"], {"boot_id": "b1"}, None])
def test_a_corrupt_heartbeat_file_is_ignored_never_crashes_the_body_or_its_readers(tmp_path, garbage):
    home, *_ = make_body(tmp_path)
    (home / "heartbeat.json").write_text(json.dumps(garbage))
    body = Body(home).open()
    record = body.boot()                                       # a naive or malformed time is not evidence
    assert "previous_heartbeat" not in record
    s = presence.summary(body.journal, now=datetime.now(timezone.utc), heartbeat=garbage)
    assert s["boots"] == 1 and s["state"] == "RUNNING"
    body.close()
    assert status(home)["presence"]["boots"] == 1               # the founder's status view still works
