"""Authenticated inbox STOP preempts an already running child, without applying other commands."""
import os
import sys
import threading
import time

import pytest

from greg.body import Body
from greg.workers import WorkerInterrupted, supervised_run
from tests.greg_fixtures import drop, make_body, signed


def test_signed_stop_terminates_inflight_child_and_persists_without_draining_other_commands(tmp_path):
    home, key, bid, _ = make_body(tmp_path)
    pending = drop(home, signed(key, bid, "BODY_PAUSE", {}), "pause.json")
    marker = tmp_path / "child.pid"
    stop = signed(key, bid, "BODY_STOP", {})

    def deliver_stop():
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        drop(home, stop, "stop.json")

    sender = threading.Thread(target=deliver_stop)
    sender.start()
    started = time.monotonic()
    try:
        with Body(home) as body:
            with pytest.raises(WorkerInterrupted):
                supervised_run([sys.executable, "-c",
                                "import os,sys,time; from pathlib import Path; "
                                "Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)", str(marker)],
                               cwd=tmp_path, env={"PATH": "/usr/bin:/bin"}, timeout=10,
                               stop_check=body._stop_now)
            assert body.stop_requested and body.layout.stop_file.exists()
            assert pending.exists() and not body.paused()
            accepted = body.journal.replay("command.accepted")
            assert [e.payload["kind"] for e in accepted] == ["BODY_STOP"]
            assert accepted[0].payload["channel"] == "inbox"
        assert time.monotonic() - started < 5
        with pytest.raises(ProcessLookupError):
            os.kill(int(marker.read_text()), 0)
        with Body(home) as reopened:
            assert reopened._stop_now()
    finally:
        sender.join(timeout=6)


def test_forged_stop_is_rejected_during_supervision_and_cannot_stop_body(tmp_path):
    home, key, bid, _ = make_body(tmp_path)
    forged = signed(key, bid, "BODY_STOP", {})
    forged["signature"] = "00" * 64
    path = drop(home, forged, "forged-stop.json")
    with Body(home) as body:
        assert body._stop_now() is False
        assert not path.exists() and (body.layout.rejected / path.name).exists()
        assert body.journal.replay("command.rejected")
        assert not body.journal.replay("body.stop_persisted")
