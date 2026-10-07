"""Real browser owner session and same-origin artifact isolation; synthetic key only."""
import json
import shutil
import threading

import pytest

from greg.body import Layout
from greg import console as console_module
from tests.greg_fixtures import make_body

playwright = pytest.importorskip("playwright.sync_api")
CHROMIUM = shutil.which("chromium") or shutil.which("google-chrome")
pytestmark = pytest.mark.skipif(CHROMIUM is None, reason="requires an installed Chromium engine")


def test_owner_cookie_works_while_public_artifact_script_and_forms_cannot_sign(tmp_path, monkeypatch):
    home, key, _, _ = make_body(tmp_path)
    console = console_module.Console(home, key=key)
    server = console_module.serve(console, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    port = server.server_address[1]
    origin = f"http://127.0.0.1:{port}"
    # Deliberately place a hostile artifact on the same server as an unlocked
    # founder console. Knowing a CSRF token still must not authorize artifacts.
    hostile = ("<script>window.artifact_attack_ran=true;</script>"
               "<form method=post action=/stop><input name=mode value=signed>"
               f"<input name=csrf value='{console.csrf}'><button>Attack</button></form>").encode()
    monkeypatch.setattr(console_module, "render_owned_page", lambda *args: hostile)
    try:
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROMIUM)
            try:
                owner = browser.new_context()
                page = owner.new_page()
                page.on("dialog", lambda dialog: dialog.accept())
                page.goto(console.owner_url(port))
                assert page.url == origin + console.owner_path and "access=" not in page.url
                cookie = next(c for c in owner.cookies() if c["name"] == console_module.OWNER_COOKIE)
                assert cookie["path"] == console.owner_path and cookie["httpOnly"] and cookie["sameSite"] == "Strict"
                stranger = browser.new_context().new_page()
                response = stranger.goto(origin + "/")
                assert response.status == 403 and console.csrf not in stranger.content()

                response = page.goto(origin + console.owner_path + "owned/fixture/hostile")
                assert "sandbox;" in response.headers["content-security-policy"]
                assert page.evaluate("window.artifact_attack_ran === true") is False
                # Browser-enforced sandbox/form-action must block this even
                # when privileged test code explicitly tries submission.
                page.evaluate("document.querySelector('form').submit()")
                page.wait_for_timeout(100)
                assert not list(Layout(home).inbox.glob("*.json"))
                assert not Layout(home).stop_file.exists()

                page.goto(origin + console.owner_path)
                form = page.locator(f"form[action='{console.owner_path}stop']").filter(
                    has=page.locator("input[name=mode][value=signed]"))
                form.locator("button").click()
                files = list(Layout(home).inbox.glob("*.json"))
                assert len(files) == 1 and json.loads(files[0].read_text())["kind"] == "BODY_STOP"
                assert console._session not in files[0].read_text()
            finally:
                browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
