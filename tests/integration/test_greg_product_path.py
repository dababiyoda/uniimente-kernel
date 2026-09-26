"""Directive §24 acceptance, through the real product surface, with stronger failures.

Founder console (HTTP) -> plain-words ask -> signed proposal -> console CLOSED ->
supervised body -> real capability (local Git; brief delivered to a founder folder) ->
approval boundary -> SIGKILL while waiting -> power-loss torn write while frozen ->
autonomous restart quarantines the torn bytes -> approval -> exactly one delivery ->
separate-process appraisal (file == render of receipted inputs) -> signed acceptance ->
VEPMC conditions from the ledger -> signed stop. The founder key is a per-test key.
"""
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from greg import service
from tests.integration.test_greg_body_supervised import ROOT, SUPERVISORD, events, greg, heartbeat, wait_for

pytestmark = pytest.mark.skipif(SUPERVISORD is None, reason="supervisord (requirements-dev) not installed")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def http(port, path, fields=None):
    headers = {"Host": f"127.0.0.1:{port}"}
    data = None
    if fields is not None:
        data = urlencode(fields).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    with urlopen(Request(f"http://127.0.0.1:{port}{path}", data=data, headers=headers), timeout=30) as r:
        return r.geturl(), r.read().decode()


def console(home, key, port):
    proc = subprocess.Popen([sys.executable, "-m", "greg", "--home", str(home), "console", "--key", str(key),
                             "--no-passphrase", "--no-model", "--port", str(port)], cwd=ROOT,
                            env={**os.environ, "PYTHONPATH": str(ROOT)}, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            http(port, "/")
            return proc
        except OSError:
            assert proc.poll() is None, proc.stdout.read()
            time.sleep(0.2)
    raise AssertionError("console did not start")


def test_founder_product_path_survives_kill_and_torn_write_and_delivers_once(tmp_path):
    home, key, code = tmp_path / "body", tmp_path / "founder.pem", tmp_path / "code"
    repo = code / "kernel"
    repo.mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                    check=True, capture_output=True)
    git("init", "-q", "-b", "main"); (repo / "a").write_text("a"); git("add", "a"); git("commit", "-q", "-m", "first")
    greg(home, "init", "--read-root", str(code), "--deliver-root", str(tmp_path / "Deliveries"))
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
    port = free_port()
    ui = None
    try:
        first = wait_for(lambda: heartbeat(home)["state"] == "RUNNING" and heartbeat(home), what="body start")
        # 1. Alfonso asks in plain words through the console, reviews, signs; then closes the console.
        ui = console(home, key, port)
        token = re.search(r"name=csrf value='([^']+)'", http(port, "/")[1]).group(1)
        url, review = http(port, "/ask", {"csrf": token, "text": "Brief me on the state of my repositories"})
        assert "Must ask you first" in review and "brief.engineering" in review
        http(port, "/sign", {"csrf": token, "proposal": url.rsplit("/", 1)[1]})
        ui.terminate(); ui.wait(10); ui = None                       # the interface is closed
        # 2. The body carries on alone and stops at the approval boundary.
        request = wait_for(lambda: events(home, "decision.requested"), what="approval boundary")[0]
        assert request["kind"] == "APPROVAL" and request["authority_requested"]["capability"] == "brief.engineering"
        briefs = tmp_path / "Deliveries" / "briefs"
        assert not briefs.exists() or not list(briefs.glob("*.md"))
        # 3. Hard kill while waiting.
        pid = heartbeat(home)["pid"]
        os.kill(pid, signal.SIGKILL)
        second = wait_for(lambda: heartbeat(home)["pid"] != pid and heartbeat(home)["state"] == "RUNNING"
                          and heartbeat(home), what="restart after SIGKILL")
        # 4. Power loss mid-append: freeze the body, tear the ledger tail, kill it.
        os.kill(second["pid"], signal.SIGSTOP)
        with open(home / "ledger.jsonl", "ab") as fh:
            fh.write(b'{"seq": 999999, "record_type": "event", "payload": {"type": "greg.mission.act')
        os.kill(second["pid"], signal.SIGKILL)
        wait_for(lambda: heartbeat(home)["pid"] not in (pid, second["pid"]) and heartbeat(home)["state"] == "RUNNING",
                 what="restart after torn write")
        boots = wait_for(lambda: [b for b in events(home, "body.booted") if b.get("ledger_recovery")],
                         what="torn tail quarantined")
        sidecar = Path(boots[0]["ledger_recovery"]["sidecar"])
        assert sidecar.read_bytes().startswith(b'{"seq": 999999')
        assert len(events(home, "body.recovered")) >= 2
        # 5. Approval from a fresh interface process; exactly one delivery follows.
        greg(home, "decide", request["request_id"], "approve", "--key", str(key), "--no-passphrase")
        appraisal = wait_for(lambda: events(home, "mission.appraised"), what="independent appraisal", timeout=60)[0]
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        assert appraisal["checks"]["deliveries_bound_to_evidence"] is True
        delivered = list(briefs.glob("*.md"))
        assert len(delivered) == 1 and "## Local checkouts" in delivered[0].read_text()
        done = [a for a in events(home, "mission.action") if a["status"] == "DONE"]
        assert len(done) == 1 and done[0]["capability"] == "brief.engineering"
        # 6. The founder reads the result through the console and accepts it there.
        ui = console(home, key, port)
        page = http(port, "/")[1]
        assert "Accept result" in page and delivered[0].name in page
        token = re.search(r"name=csrf value='([^']+)'", page).group(1)
        event_id = json.loads(greg(home, "vepmc").stdout)["missions"][0]["closure_event_id"]
        http(port, "/accept", {"csrf": token, "event_id": event_id})
        wait_for(lambda: events(home, "critique.recorded"), what="acceptance")
        row = json.loads(greg(home, "vepmc").stdout)["missions"][0]
        assert row["missing"] == ([] if os.uname().sysname == "Darwin" else ["mac_body"]), row
        http(port, "/stop", {"csrf": token, "mode": "signed"})
        wait_for(lambda: heartbeat(home)["state"] == "STOPPED", what="signed stop")
        if os.environ.get("GREG_RECORD_EVIDENCE"):
            out = ROOT / "tests" / "evidence" / "greg-product"
            out.mkdir(parents=True, exist_ok=True)
            (out / "product-path-summary.json").write_text(json.dumps({
                "vepmc_row": row, "appraisal": appraisal, "approval": request, "torn_tail": boots[0]["ledger_recovery"],
                "recoveries": events(home, "body.recovered"), "actions": events(home, "mission.action"),
                "brief_excerpt": delivered[0].read_text()[:1500]}, indent=1, default=str))
            (out / "product-path-ledger.jsonl").write_bytes((home / "ledger.jsonl").read_bytes())
    finally:
        if ui is not None:
            ui.terminate(); ui.wait(10)
        supervisor.send_signal(signal.SIGTERM)
        supervisor.wait(30)
