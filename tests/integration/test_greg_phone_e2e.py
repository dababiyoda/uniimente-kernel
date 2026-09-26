"""The phone path, end to end with real processes and a real browser engine.

supervisord keeps the body alive; `greg serve` is its own process; Chromium, emulating an
iPhone viewport, runs the actual phone page, which generates a non-extractable Ed25519 key.
The founder delegates that key from the CLI. The approval and the stop then come from taps
on the page. Nothing is simulated except the founder key (per test) and the browser engine
(Chromium stands in for iOS Safari, which is not available here).
"""
import glob
import json
import os
import shutil
import signal
import socket
import subprocess
import sys

import pytest

from greg import service
from tests.integration.test_greg_body_supervised import (ROOT, SUPERVISORD, events, greg, heartbeat, wait_for)

playwright = pytest.importorskip("playwright.sync_api")
CHROMIUM = os.environ.get("GREG_CHROMIUM") or next(
    iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
         + [p for p in (shutil.which("chromium"), shutil.which("google-chrome")) if p]), None)
pytestmark = pytest.mark.skipif(SUPERVISORD is None or CHROMIUM is None,
                                reason="needs supervisord and a Chromium binary")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_phone_page_approves_a_real_decision_and_stops_the_body(tmp_path):
    home, key = tmp_path / "body", tmp_path / "founder.pem"
    greg(home, "init", "--read-root", str(tmp_path))
    greg(home, "founder", "enroll", "--pubkey",
         greg(home, "founder", "keygen", "--key", str(key), "--no-passphrase").stdout.strip())
    (home / "logs").mkdir(exist_ok=True)
    conf = tmp_path / "supervisord.conf"
    conf.write_text(
        f"[supervisord]\nnodaemon=true\nlogfile={tmp_path / 'sd.log'}\npidfile={tmp_path / 'sd.pid'}\n"
        f"[unix_http_server]\nfile={tmp_path / 'sd.sock'}\n"
        "[rpcinterface:supervisor]\nsupervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface\n"
        f"[supervisorctl]\nserverurl=unix://{tmp_path / 'sd.sock'}\n" + service.supervisord_program(home, tick_seconds=0.3))
    port = _free_port()
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    supervisor = subprocess.Popen(["supervisord", "-c", str(conf)], cwd=ROOT,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    server = subprocess.Popen([sys.executable, "-m", "greg", "--home", str(home), "serve", "--port", str(port)],
                              cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        wait_for(lambda: heartbeat(home)["state"] == "RUNNING", what="body start")
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROMIUM)
            page = browser.new_context(**pw.devices["iPhone 13"]).new_page()
            page.on("dialog", lambda dialog: dialog.accept())
            wait_for(lambda: _open(page, port), what="phone page served")
            page.wait_for_selector("body[data-ready=true]", timeout=20000)
            public_hex = page.text_content("#pubkey").strip()
            # The private key exists only inside the browser and cannot be exported.
            exported = page.evaluate("""async () => { const db = await new Promise(r => { const q = indexedDB.open('greg-phone', 1); q.onsuccess = () => r(q.result); });
                const k = await new Promise(r => { const g = db.transaction('keys').objectStore('keys').get('device'); g.onsuccess = () => r(g.result); });
                if (!k || !(k.privateKey instanceof CryptoKey)) return {present: false};
                let exported = true; try { await crypto.subtle.exportKey('pkcs8', k.privateKey); } catch (e) { exported = false; }
                return {present: true, type: k.privateKey.type, extractable: k.privateKey.extractable, exported,
                        algorithm: k.privateKey.algorithm.name, public_matches: k.publicHex}; }""")
            assert exported == {"present": True, "type": "private", "extractable": False, "exported": False,
                                "algorithm": "Ed25519", "public_matches": public_hex} and len(public_hex) == 64
            assert "Not authorized" in page.inner_text("#state")  # an unknown phone reads nothing

            greg(home, "device", "enroll", "--pubkey", public_hex, "--label", "iphone", "--key", str(key),
                 "--no-passphrase")
            wait_for(lambda: events(home, "device.enrolled"), what="device delegation")
            greg(home, "mission", "new", "workspace-note", "--text", "approved from my phone",
                 "--must-contain", "phone", "--key", str(key), "--no-passphrase")
            request = wait_for(lambda: events(home, "decision.requested"), what="approval boundary")[0]
            note = home.resolve() / "workspace" / "m_first-note" / "note.txt"
            assert not note.exists()

            page.click("#refresh")
            card = f"article[data-request-id='{request['request_id']}']"
            page.wait_for_selector(card, timeout=20000)
            page.fill(f"{card} input", "aprobado desde el teléfono ✓")
            page.click(f"{card} button.approve")
            try:
                appraisal = wait_for(lambda: events(home, "mission.appraised"), what="closure appraisal")[0]
            except AssertionError as exc:
                raise AssertionError(f"{exc}; page says {page.text_content('#note')!r}; "
                                     f"rejected={events(home, 'command.rejected')}; "
                                     f"inbox={sorted(p.name for p in (home / 'inbox').glob('*.json'))}; "
                                     f"rejected_bodies={[json.loads(p.read_text())['body'] for p in (home / 'inbox' / 'rejected').glob('*.json')]}; "
                                     f"requests={[(r['request_id'], r['kind']) for r in events(home, 'decision.requested')]}; "
                                     f"answered={events(home, 'decision.answered')}") from None
            assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
            assert note.read_text() == "approved from my phone"
            decision = [e for e in events(home, "command.accepted") if e["kind"] == "DECISION"]
            assert decision[0]["signer"] == "device:iphone" and decision[0]["channel"] == "inbox"
            assert "teléfono" in decision[0]["body"]["reason"]

            page.click("#refresh")
            page.wait_for_function("document.querySelector('#who').textContent.includes('device:iphone')")
            page.click("#stop")
            wait_for(lambda: heartbeat(home)["state"] == "STOPPED", what="stop from the phone")
            stops = [e for e in events(home, "command.accepted") if e["kind"] == "BODY_STOP"]
            assert stops and stops[0]["signer"] == "device:iphone"
            browser.close()
        ctl = subprocess.run(["supervisorctl", "-c", str(conf), "status"], capture_output=True, text=True)
        assert "EXITED" in ctl.stdout  # a stop from the phone is honored by the supervisor: no restart
        if os.environ.get("GREG_RECORD_EVIDENCE"):
            out = ROOT / "tests" / "evidence" / "greg-body"
            (out / "phone-e2e-summary.json").write_text(json.dumps({
                "browser": "Chromium (iPhone 13 emulation), not iOS Safari", "chromium": CHROMIUM,
                "device_enrolled": events(home, "device.enrolled"), "decision": decision, "stop": stops,
                "appraisal": appraisal, "private_key_export": exported, "supervisor": ctl.stdout.strip(),
                "founder_key": "per-test Ed25519 key; NOT Alfonso"}, indent=1, ensure_ascii=False))
    finally:
        server.send_signal(signal.SIGTERM)
        server.wait(timeout=10)
        supervisor.send_signal(signal.SIGTERM)
        try:
            supervisor.wait(timeout=20)
        except subprocess.TimeoutExpired:
            supervisor.kill()


def _open(page, port):
    try:
        page.goto(f"http://127.0.0.1:{port}/", timeout=3000)
        return True
    except Exception:
        return False
