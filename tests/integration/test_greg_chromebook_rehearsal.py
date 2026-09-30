"""greg/CHROMEBOOK_FIRST_MISSION.md, rehearsed as written, as one piece, then N2 on the same body.

The installer (install.sh), the `greg` command it writes, the founder console in a browser
(HTTP forms), the repository brief, `kill -9` of the body, approval and acceptance in the
console, then `greg vepmc`, `greg morning`, `greg presence --hours 2` and `greg path`. Then, still without a model: "Verify <file> against
sha256 <hex>" and "Confirm <draft> is at most 50 words", each needing a capability GREG lacks
(Capability Genesis acquires and verifies one), each interrupted by kill -9 while it waits for
approval, each accepted: `greg path` moves N1 -> N2 -> N3 on ledger evidence alone.

What stands in for the Chromebook: this Linux container (`--allow-other-linux`), supervisord in
place of the systemd user unit (same command, restart-on-crash, stay stopped after STOP), a
per-test founder key without a passphrase, and an HTTP client in place of Chrome. A complete
row here is a structural rehearsal of the gate, never an external VEPMC: the ledger cannot
prove whose machine or whose key this is.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

import pytest

from greg import service
from greg import path as devpath
from tests.integration.test_greg_body_supervised import (SUPERVISORD, events, heartbeat, history,
                                                         supervisor_endpoint, wait_for)
from tests.integration.test_greg_product_path import free_port, http

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "greg/chromebook/install.sh"
pytestmark = pytest.mark.skipif(SUPERVISORD is None, reason="supervisord stands in for the systemd user unit")


def test_the_chromebook_runbook_reaches_n1_and_then_n2_on_the_same_body_without_a_model(tmp_path):
    home, key, bin_dir = tmp_path / "body", tmp_path / "founder.pem", tmp_path / "bin"
    src, deliver = tmp_path / "src", tmp_path / "GREG"
    repo = src / "kernel-checkout"
    repo.mkdir(parents=True)
    git = lambda *a: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                    check=True, capture_output=True)
    git("init", "-q", "-b", "main"); (repo / "a").write_text("a"); git("add", "a"); git("commit", "-q", "-m", "first")
    env = {**os.environ, "HOME": str(tmp_path / "home")}
    env.pop("GREG_FOUNDER_PASSPHRASE", None)
    (tmp_path / "home").mkdir()

    # Step 1: one command.
    installed = subprocess.run(
        ["bash", str(INSTALL), "--allow-other-linux", "--no-service", "--skip-deps", "--no-passphrase",
         "--python", sys.executable, "--home", str(home), "--key", str(key), "--bin-dir", str(bin_dir),
         "--read-root", str(src), "--deliver-root", str(deliver)],
        capture_output=True, text=True, env=env, timeout=300)
    assert installed.returncode == 0, installed.stdout[-3000:] + installed.stderr[-3000:]

    def greg(*args):
        out = subprocess.run([str(bin_dir / "greg"), *args], capture_output=True, text=True, env=env, timeout=120)
        assert out.returncode == 0, out.stderr[-2000:]
        return out.stdout

    # The systemd user unit, played by supervisord: same program, restarts a crash, honours STOP.
    conf = tmp_path / "supervisord.conf"
    (home / "logs").mkdir(exist_ok=True)              # what `greg service install` creates; journald on systemd
    endpoint, ctl = supervisor_endpoint(tmp_path)
    conf.write_text(
        f"[supervisord]\nnodaemon=true\nlogfile={tmp_path / 'sd.log'}\npidfile={tmp_path / 'sd.pid'}\n" + endpoint
        + "[rpcinterface:supervisor]\nsupervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface\n"
        + ctl + service.supervisord_program(home, sys.executable, tick_seconds=0.3))
    supervisor = subprocess.Popen(["supervisord", "-c", str(conf)], cwd=ROOT,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    port, ui = free_port(), None

    def open_console():
        proc = subprocess.Popen([str(bin_dir / "greg"), "console", "--key", str(key), "--no-passphrase", "--no-model",
                                 "--port", str(port)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True)
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                http(port, "/")
                return proc
            except OSError:
                assert proc.poll() is None, proc.stdout.read()
                time.sleep(0.2)
        raise AssertionError("console did not start")

    def close(proc):
        proc.terminate()
        proc.wait(10)

    try:
        first = wait_for(lambda: heartbeat(home)["state"] == "RUNNING" and heartbeat(home), what="body start")
        wait_for(lambda: events(home, "body.designated"), what="the queued designation accepted by the body")
        assert json.loads(greg("status"))["designation"][0]["purpose"] == "first_founder_body"

        # Step 2: ask in plain words, review, sign, close the tab and the console.
        ui = open_console()
        token = re.search(r"name=csrf value='([^']+)'", http(port, "/")[1]).group(1)
        url, review = http(port, "/ask", {"csrf": token, "text": "Brief me on the state of my repositories."})
        assert "brief.engineering" in review
        http(port, "/sign", {"csrf": token, "proposal": url.rsplit("/", 1)[1]})
        close(ui); ui = None
        request = wait_for(lambda: events(home, "decision.requested"), what="the one waiting delivery")[0]
        assert request["kind"] == "APPROVAL"

        # `greg status`, note the PID, `kill -9 <PID>`; the supervisor restarts GREG.
        pid = json.loads(greg("status"))["background"]["pid"]
        assert pid == first["pid"]
        os.kill(pid, signal.SIGKILL)
        wait_for(lambda: heartbeat(home)["pid"] != pid and heartbeat(home)["state"] == "RUNNING", what="restart")
        wait_for(lambda: events(home, "body.recovered"), what="recovery record")

        # Reopen the console, approve the one waiting delivery, read the brief, accept the result.
        ui = open_console()
        page = http(port, "/")[1]
        token = re.search(r"name=csrf value='([^']+)'", page).group(1)
        http(port, "/decide", {"csrf": token, "request_id": request["request_id"], "answer": "approve"})
        appraisal = wait_for(lambda: events(home, "mission.appraised"), what="independent appraisal", timeout=90)[0]
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        [brief] = list((deliver / "briefs").glob("*.md"))
        assert "kernel-checkout" in brief.read_text()
        event_id = json.loads(greg("vepmc"))["missions"][0]["closure_event_id"]
        page = http(port, "/")[1]
        token = re.search(r"name=csrf value='([^']+)'", page).group(1)
        http(port, "/accept", {"csrf": token, "event_id": event_id})
        wait_for(lambda: events(home, "critique.recorded"), what="founder acceptance")
        close(ui); ui = None

        # greg vepmc ; greg morning ; greg presence --hours 2 ; greg path
        vepmc = json.loads(greg("vepmc"))
        row = vepmc["missions"][0]
        assert row["missing"] == [] and vepmc["VEPMC"] == 1, row             # structurally complete, not external
        assert vepmc["external_confirmation_required"]
        assert [a["status"] for a in events(home, "mission.action")].count("DONE") == 1   # delivered once
        morning = json.loads(greg("morning"))
        assert morning["q0_was_i_present"]["absences"]
        presence = json.loads(greg("presence", "--hours", "2"))
        assert "process_lost" in {a["cause"] for a in presence["absences"]}   # the kill -9, bounded by a heartbeat
        path = json.loads(greg("path"))
        assert "N1" in path["achieved"] and path["active"]["id"] == "N2"     # the GPS moves on ledger evidence

        # N2 on the same body, still without a model: a mission that needs a capability GREG lacks.
        download = src / "downloads" / "tool.tar.gz"
        download.parent.mkdir()
        download.write_bytes(b"published release bytes\n")
        digest = hashlib.sha256(download.read_bytes()).hexdigest()
        ui = open_console()
        token = re.search(r"name=csrf value='([^']+)'", http(port, "/")[1]).group(1)
        url, review = http(port, "/ask", {"csrf": token, "text": f"Verify {download} against sha256 {digest}"})
        assert "hash.sha256" in review
        http(port, "/sign", {"csrf": token, "proposal": url.rsplit("/", 1)[1]})
        close(ui); ui = None
        verify = wait_for(lambda: [m for m in events(home, "mission.registered")
                                   if m["mission_id"].startswith("m:verify")], what="verification registered")[0]["mission_id"]
        wait_for(lambda: [d for d in events(home, "deficit.resolved") if d["mission_id"] == verify], what="genesis")
        ask = wait_for(lambda: [r for r in events(home, "decision.requested")
                                if r["mission_id"] == verify and r["kind"] == "APPROVAL"], what="approval")[0]
        pid = json.loads(greg("status"))["background"]["pid"]
        os.kill(pid, signal.SIGKILL)                                           # interrupted while it waits
        wait_for(lambda: heartbeat(home)["pid"] != pid and heartbeat(home)["state"] == "RUNNING", what="restart 2")
        ui = open_console()
        token = re.search(r"name=csrf value='([^']+)'", http(port, "/")[1]).group(1)
        http(port, "/decide", {"csrf": token, "request_id": ask["request_id"], "answer": "approve"})
        second = wait_for(lambda: [a for a in events(home, "mission.appraised") if a["mission_id"] == verify],
                          what="independent appraisal of the verification", timeout=90)[0]
        assert second["verdict"] == "VERIFIED" and second["checks"]["preconditions_honored"], second["findings"]
        closure = next(r for r in json.loads(greg("vepmc"))["missions"] if r["mission_id"] == verify)["closure_event_id"]
        token = re.search(r"name=csrf value='([^']+)'", http(port, "/")[1]).group(1)
        http(port, "/accept", {"csrf": token, "event_id": closure})
        wait_for(lambda: len(events(home, "critique.recorded")) == 2, what="second acceptance")
        close(ui); ui = None
        vepmc = json.loads(greg("vepmc"))
        assert vepmc["VEPMC"] == 2 and all(r["counts"] for r in vepmc["missions"])
        path = json.loads(greg("path"))
        assert path["achieved"][-1] == "N2" and path["active"]["id"] == "N3"   # novel capability closure, measured

        # A second genesis closure on an unrelated function (word counting), before any claim of generality.
        draft = src / "drafts" / "essay.md"
        draft.parent.mkdir()
        draft.write_text("a short essay of seven words here\n")
        ui = open_console()
        token = re.search(r"name=csrf value='([^']+)'", http(port, "/")[1]).group(1)
        url, review = http(port, "/ask", {"csrf": token, "text": f"Confirm {draft} is at most 50 words"})
        http(port, "/sign", {"csrf": token, "proposal": url.rsplit("/", 1)[1]})
        words = wait_for(lambda: [m for m in events(home, "mission.registered")
                                  if m["mission_id"].startswith("m:words")], what="word-limit registered")[0]["mission_id"]
        ask = wait_for(lambda: [r for r in events(home, "decision.requested")
                                if r["mission_id"] == words and r["kind"] == "APPROVAL"], what="approval 3")[0]
        pid = json.loads(greg("status"))["background"]["pid"]
        os.kill(pid, signal.SIGKILL)
        wait_for(lambda: heartbeat(home)["pid"] != pid and heartbeat(home)["state"] == "RUNNING", what="restart 3")
        token = re.search(r"name=csrf value='([^']+)'", http(port, "/")[1]).group(1)
        http(port, "/decide", {"csrf": token, "request_id": ask["request_id"], "answer": "approve"})
        wait_for(lambda: [a for a in events(home, "mission.appraised") if a["mission_id"] == words
                          and a["verdict"] == "VERIFIED"], what="third appraisal", timeout=90)
        closure = next(r for r in json.loads(greg("vepmc"))["missions"] if r["mission_id"] == words)["closure_event_id"]
        token = re.search(r"name=csrf value='([^']+)'", http(port, "/")[1]).group(1)
        http(port, "/accept", {"csrf": token, "event_id": closure})
        wait_for(lambda: len(events(home, "critique.recorded")) == 3, what="third acceptance")
        close(ui); ui = None
        ledger, journal = history(home)
        try:
            genesis = devpath.PREDICATES["genesis_closure"](journal)
        finally:
            ledger.close()
        assert genesis["value"] == 2 and genesis["distinct_capabilities"] == 2, genesis

        # To stop: greg stop --local (a deliberate stop stays stopped).
        greg("stop", "--local")
        wait_for(lambda: heartbeat(home)["state"] == "STOPPED", what="local stop")
    finally:
        if ui is not None:
            close(ui)
        supervisor.send_signal(signal.SIGTERM)
        try:
            supervisor.wait(timeout=20)
        except subprocess.TimeoutExpired:
            supervisor.kill()
