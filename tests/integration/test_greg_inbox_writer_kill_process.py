"""Mission H (fault recovery), acceptance gap H.G7: the console or remote service is killed during a decision POST.

A real `greg run` Body process waits at an APPROVAL boundary. The founder's approval reaches it through one of
the two HTTP services that write signed commands into its inbox: the console (`greg console`, POST /decide, which
signs with the founder key it holds) or the remote channel for the phone (`greg serve`, POST /api/command, which
pre-verifies an envelope the phone signed). Each service runs as its own process from the real CLI entry point;
its driver only stops it at one point of the inbox write, where the test SIGKILLs it:

- mid-write: half of the command's bytes are on disk in the service's temporary file;
- before-rename: the temporary file is complete and not yet renamed into the inbox;
- after-rename: the command file is in the inbox and the HTTP response was never sent.

The client never hears back, so the founder retries through a fresh service process (the console signs again
with a new nonce; the phone re-sends the same signed envelope). What must hold, with the Body running all along:
the inbox never holds a partial command file (every *.json the Body can read is one complete, verifying signed
envelope, and a torn temporary file is never read or rejected); it holds zero complete decision files after a kill
before the rename and one after it; the decision is applied exactly once (one decision.answered, one approved
dispatch, one effect), the retry of an applied decision changes nothing, and the mission closes.

The founder key is a per-test Ed25519 key, not Alfonso's.
"""
from __future__ import annotations

from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlencode

import pytest

from greg.body import Layout, device_delegations, founder_keys, observe
from greg.founder import FounderVerifier, sign_command
from tests.greg_fixtures import drop, make_body, mission, note_check, signed, workspace, write_strategy

ROOT = Path(__file__).resolve().parents[2]
ENV = {**os.environ, "PYTHONPATH": str(ROOT)}
MISSION = "m:approved-note"

# The service's own CLI entry point, stopped at one point of the inbox write (the test SIGKILLs it there).
DRIVER = '''
import os, pathlib, sys, time
sys.path.insert(0, sys.argv[1])
home, point, marker = pathlib.Path(sys.argv[2]).resolve(), sys.argv[3], pathlib.Path(sys.argv[4])
inbox = home / "inbox"
write_text, replace = pathlib.Path.write_text, pathlib.Path.replace


def stop_here(path):
    write_text(marker.with_name(marker.name + ".tmp"), str(path))
    replace(marker.with_name(marker.name + ".tmp"), marker)
    time.sleep(3600)


def stopping_write_text(self, data, *args, **kwargs):
    if self.parent == inbox and point == "mid-write":
        raw = data.encode()
        with open(self, "wb") as f:
            f.write(raw[: len(raw) // 2])
            f.flush()
            os.fsync(f.fileno())
        stop_here(self)
    result = write_text(self, data, *args, **kwargs)
    if self.parent == inbox and point == "before-rename":
        stop_here(self)
    return result


def stopping_replace(self, target):
    result = replace(self, target)
    if pathlib.Path(target).parent == inbox and point == "after-rename":
        stop_here(target)
    return result


pathlib.Path.write_text, pathlib.Path.replace = stopping_write_text, stopping_replace
from greg import cli
sys.exit(cli.main(sys.argv[5:]))
'''


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def events(home: Path, prefix: str) -> list[dict]:
    with observe(home, actor="spiffe://uniimente.internal/greg/inbox-writer-kill-test") as journal:
        return [e.payload for e in journal.replay(prefix)]


def wait_for(predicate, *, timeout=60, what="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
        except (FileNotFoundError, json.JSONDecodeError, ValueError, KeyError, OSError):
            value = None
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {what}")


def request(port: int, method: str, path: str, body: bytes = b"", headers=None, timeout=30):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        return response.status, response.read()
    finally:
        conn.close()


def stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


class Service:
    """One console or remote-channel process, from the CLI entry point; ``point`` is where it stops, if anywhere."""

    def __init__(self, tmp_path: Path, home: Path, kind: str, point: str, keyfile: Path):
        self.kind, self.port, self.marker = kind, free_port(), tmp_path / f"stopped-{kind}-{point}"
        driver = tmp_path / "service_driver.py"
        driver.write_text(DRIVER)
        args = (["console", "--key", str(keyfile), "--no-passphrase", "--no-model", "--port", str(self.port)]
                if kind == "console" else ["serve", "--port", str(self.port)])
        self.proc = subprocess.Popen([sys.executable, str(driver), str(ROOT), str(home), point, str(self.marker),
                                      "--home", str(home), *args], cwd=ROOT, env=ENV,
                                     stdout=(tmp_path / f"{kind}.log").open("a"), stderr=subprocess.STDOUT)
        wait_for(lambda: request(self.port, "GET", "/" if kind == "console" else "/api/hello", timeout=2)[0] == 200,
                 what=f"the {kind} service")

    def decide(self, request_id: str, envelope: dict | None):
        """The founder's approval, as each interface sends it: a console form, or the phone's signed envelope."""
        if self.kind == "console":
            page = request(self.port, "GET", "/")[1].decode()
            csrf = re.search(r"name=csrf value='([^']+)'", page).group(1)
            form = urlencode({"csrf": csrf, "request_id": request_id, "answer": "approve"}).encode()
            return request(self.port, "POST", "/decide", form,
                           {"Content-Type": "application/x-www-form-urlencoded"})
        return request(self.port, "POST", "/api/command", json.dumps(envelope).encode(),
                       {"Content-Type": "application/json"})


def verifier(home: Path) -> FounderVerifier:
    with observe(home, actor="spiffe://uniimente.internal/greg/inbox-writer-kill-test") as journal:
        config = json.loads(Layout(home).config.read_text())
        return FounderVerifier(body_id=config["body_id"], enrolled=founder_keys(journal), seen_nonce=lambda n: False,
                               devices=device_delegations(journal))


def command_files(home: Path) -> list[tuple[Path, dict]]:
    """Every command file the Body can read or has filed: each must be one complete, verifying signed envelope."""
    layout, check, out = Layout(home), verifier(home), []
    for path in sorted([*layout.inbox.glob("*.json"), *layout.processed.glob("*"), *layout.rejected.glob("*")]):
        envelope = json.loads(path.read_text())       # a partial file fails here
        check.verify(envelope, now=datetime.now(timezone.utc))
        out.append((path, envelope))
    return out


def decisions(home: Path, request_id: str) -> list[dict]:
    return [e for _, e in command_files(home) if e["kind"] == "DECISION" and e["body"]["request_id"] == request_id]


def body_ticked_since(home: Path, moment: float, ticks: int = 5) -> bool:
    """The Body's heartbeat was written well after ``moment`` (it ran several 0.1 s ticks since)."""
    at = json.loads(Layout(home).heartbeat.read_text())["at"]
    return datetime.fromisoformat(at.replace("Z", "+00:00")).timestamp() > moment + 0.1 * ticks


@pytest.mark.parametrize("point", ["mid-write", "before-rename", "after-rename"])
@pytest.mark.parametrize("kind", ["console", "remote"])
def test_a_service_killed_while_writing_a_decision_leaves_no_partial_command_and_it_applies_once(tmp_path, kind,
                                                                                                 point):
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, MISSION) / "n.txt"
    drop(home, signed(key, body_id, "MISSION", mission(          # fs.write is outside the read-only cone: it asks
        MISSION, checks=[note_check("n", note, "approved")], strategies=[write_strategy("w", "n.txt", "approved",
                                                                                       ["n"])],
        capabilities=["fs.read"], targets=("fs:*", "workspace:*"), ceiling="read_only")))
    body = subprocess.Popen([sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", "0.1"],
                            cwd=ROOT, env=ENV, stdout=(tmp_path / "body.log").open("a"), stderr=subprocess.STDOUT)
    services = []
    try:
        [ask] = wait_for(lambda: [r for r in events(home, "decision.requested") if r["kind"] == "APPROVAL"],
                         what="the approval request")
        rid = ask["request_id"]
        # The phone signs its envelope itself; the console signs inside its own process.
        envelope = sign_command(key, "DECISION", {"request_id": rid, "answer": "approve", "reason": "from the phone"},
                                body_id=body_id) if kind == "remote" else None

        services.append(Service(tmp_path, home, kind, point, tmp_path / "founder.pem"))
        service = services[-1]
        outcome = {}
        client = threading.Thread(target=lambda: outcome.update(
            result=_attempt(lambda: service.decide(rid, envelope))), daemon=True)
        client.start()
        stopped_at = Path(wait_for(lambda: service.marker.read_text(), what=f"the {kind} at {point}"))
        service.proc.send_signal(signal.SIGKILL)
        service.proc.wait(timeout=20)
        killed_at = time.time()
        client.join(timeout=30)
        assert isinstance(outcome["result"], Exception), f"the founder was never told it was delivered: {outcome}"

        if point == "after-rename":
            # the one complete file is in the inbox; the running Body applies it
            wait_for(lambda: [c for c in events(home, "command.accepted") if c["kind"] == "DECISION"],
                     what="the delivered decision applied")
            assert len(decisions(home, rid)) == 1
        else:
            wait_for(lambda: body_ticked_since(home, killed_at), what="the Body ticking after the kill")
            assert decisions(home, rid) == [] and events(home, "decision.answered") == []
            torn = stopped_at.read_bytes()                 # the service's temporary file, outside the *.json read
            assert stopped_at.suffix == ".tmp" and stopped_at.parent == Layout(home).inbox
            if point == "mid-write":
                with pytest.raises(json.JSONDecodeError):
                    json.loads(torn)
        assert events(home, "command.rejected") == [] and events(home, "command.faulted") == []
        assert all(not p.name.endswith(".tmp") for p, _ in command_files(home))

        # The founder retries through a fresh service process.
        services.append(Service(tmp_path, home, kind, "none", tmp_path / "founder.pem"))
        status, reply = services[-1].decide(rid, envelope)
        if kind == "remote" and point == "after-rename":
            assert status == 403 and b"replayed command nonce" in reply   # refused at the door: already applied
        else:
            assert status in (202, 303), reply
        wait_for(lambda: events(home, "mission.achieved"), what="the mission closing")
        expected = 2 if kind == "console" and point == "after-rename" else 1
        wait_for(lambda: len([c for c in events(home, "command.accepted") if c["kind"] == "DECISION"]) == expected,
                 what="every decision file filed")
        answered = [a for a in events(home, "decision.answered") if a["request_id"] == rid]
        done = [a for a in events(home, "mission.action") if a["status"] == "DONE"]
        assert body.poll() is None
    finally:
        for service in services:
            stop(service.proc)
        stop(body)

    assert len(answered) == 1, "the decision is applied exactly once"
    assert len(done) == 1 and done[0]["receipt"], "one approved dispatch, receipted"
    assert note.read_text() == "approved"
    files = decisions(home, rid)
    assert len(files) == expected and len({e["nonce"] for e in files}) == expected
    assert not list(Layout(home).inbox.glob("*.json")), "every complete decision file was read and filed"
    with observe(home) as journal:
        assert journal.ledger.verify_chain()[0]
        receipts = [r.payload["grant_id"] for r in journal.ledger.by_type("receipt")]
        assert len(receipts) == len(set(receipts))


def _attempt(call):
    try:
        return call()
    except Exception as exc:           # the connection drops when the service is killed
        return exc
