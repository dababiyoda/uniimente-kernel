"""Interface-level acceptance: a real Chromium drives Mission Control at Chromebook and phone sizes.

Fourteen properties, each asserted through what the founder sees and clicks, with the body ticked
in-process between founder actions (no supervisor, no network, no model, no money). A per-test
Ed25519 key stands in for the founder. The same task is then attempted on the classic page as the
baseline. Set ``GREG_ACCEPTANCE_EVIDENCE=<dir>`` to write the measured results and screenshots.

Skipped where Playwright or a Chromium binary is absent (CI installs neither); the recorded run is
in docs/evidence/mission-control-acceptance/.
"""
import json
import os
from pathlib import Path
import shutil
import threading
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
CHROMIUM = next((p for p in (os.environ.get("GREG_CHROMIUM"), "/opt/pw-browsers/chromium", shutil.which("chromium"),
                             shutil.which("chromium-browser"), shutil.which("google-chrome")) if p and Path(p).exists()), None)
if CHROMIUM is None:
    pytest.skip("no Chromium binary for the interface acceptance suite", allow_module_level=True)

from greg.body import Body, status                                              # noqa: E402
from greg.console import Console, serve                                         # noqa: E402
from greg.mission_control import projection                                     # noqa: E402
from tests.greg_fixtures import make_body                                       # noqa: E402
from tests.integration.test_greg_first_mission import kernel_copy               # noqa: E402

VIEWPORTS = {"chromebook": {"width": 1366, "height": 768}, "phone": {"width": 390, "height": 844}}
QUESTIONS = ("What is GREG?", "What can it actually do right now?", "What is it doing?",
             "What valuable work can I command?", "What needs my authority?")
EVIDENCE = os.environ.get("GREG_ACCEPTANCE_EVIDENCE")


def tick(home, n=1):
    with Body(home) as body:
        body.boot()
        return [body.tick() for _ in range(n)]


def actions(home):
    with Body(home) as body:
        return [e.payload for e in body.journal.replay("mission.action")]


class Site:
    def __init__(self, console):
        self.console = console
        self.server = serve(console, port=0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.port}"
        self.url = self.base + console.owner_path.rstrip("/")     # private pages live under the owner path

    def enter(self, page):
        """Open the single-use private link, as the founder does with the one `greg console` prints."""
        page.goto(self.console.owner_url(self.port))

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        yield b
        b.close()


@pytest.mark.parametrize("device", sorted(VIEWPORTS))
def test_fourteen_properties_through_the_founder_interface(browser, tmp_path, device):
    results, started = {}, time.monotonic()
    home, key, body_id, _ = make_body(tmp_path)
    kernel_copy(tmp_path)
    console = Console(home, key=key)
    site = Site(console)
    page = browser.new_page(viewport=VIEWPORTS[device], is_mobile=device == "phone")
    site.enter(page)
    page.on("dialog", lambda d: d.accept())
    clicks = 0

    def click(selector):
        nonlocal clicks
        clicks += 1
        page.locator(selector).first.click()
        page.wait_for_load_state()

    try:
        # P1 the first page answers the five questions
        page.goto(site.url + "/")
        text = page.inner_text("main")
        results["P01_five_questions"] = all(q in text for q in QUESTIONS)
        # P2 it fits the device: no horizontal page scroll
        results["P02_fits_viewport"] = page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        # P3 every view is a working projection
        views = {}
        for href in page.eval_on_selector_all("nav.mc a", "els => els.map(e => e.getAttribute('href'))"):
            response = page.goto(site.base + href)
            views[href] = response.status == 200 and "Traceback" not in page.content()
        results["P03_every_view_renders"] = len(views) == 10 and all(views.values())
        # P4 capability truth: the page's numbers are the body's own classification
        page.goto(site.url + "/")
        classes = projection(console)["capability_classes"]
        shown = {cls: int(page.locator(f".stat:has(.cls.{cls}) b").first.inner_text()) for cls in
                 ("RUNNABLE", "NEEDS_FOUNDER_ATTACH", "SPENDS_MONEY", "BLOCKED")}
        results["P04_capability_truth"] = all(shown[c] == classes.get(c, 0) for c in shown)
        # P5 command: one click drafts the First Mission; the review shows the envelope before signing
        page.fill("input[name=effort_budget]", "8")
        click("form[action$='/first-mission'] button")
        review = page.inner_text("main")
        results["P05_review_before_sign"] = (page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
                                             and "What signing lets GREG do" in review and "Never" in review
                                             and "institution.survey" in review and not actions(home))
        # P6 sign; GREG stops for the founder's attach of the exact selection engine; attach from the page
        click("form[action$='/sign'] button")
        tick(home, 3)
        page.goto(site.url + "/")
        attach = page.locator("form[action$='/attach'] button")
        results["P06_attach_is_founder_decision"] = attach.count() == 1 and "cognition.dp_knapsack" in attach.inner_text()
        click("form[action$='/attach'] button")
        # P7 crash after one more step, resume in a new process, no step repeated
        tick(home, 1)
        done_before = [a["action_id"] for a in actions(home) if a["status"] == "DONE"]
        tick(home, 10)
        done = [a["action_id"] for a in actions(home) if a["status"] == "DONE"]
        results["P07_crash_resume_no_repeat"] = (len(done) == len(set(done)) == 6 and done[:len(done_before)] == done_before)
        # P8 no duplicate consequence after further restarts
        tick(home, 2)
        dossiers = list((home / "deliveries" / "first-mission").glob("*.json"))
        results["P08_one_consequence"] = len(dossiers) == 1 and [a["action_id"] for a in actions(home) if a["status"] == "DONE"] == done
        # P9 the result is independently verified and readable from the page
        page.goto(site.url + "/mc/proof")
        proof = page.inner_text("main")
        page.goto(site.url + "/")
        click("a[href*='/first-mission/']")
        dossier = page.inner_text("main")
        results["P09_verified_and_readable"] = ("VERIFIED" in proof and "Where you are trying to go" in dossier
                                                and "Next authorized step" in dossier)
        # P10 cost integrity: a $0 envelope, no booked spend, and budget / booked / provider-measured / unknown /
        # fixture amounts shown in separate columns rather than one netted number
        page.goto(site.url + "/mc/authority")
        authority = page.inner_text("main")
        results["P10_cost_integrity"] = ("$0" in authority and "Money, kept in separate columns" in authority
                                         and "Unknown (booked at cap)" in authority and "Provider-measured" in authority
                                         and all(not a.get("spend_usd") and not a.get("cost_usd") for a in actions(home)))
        # P11 pause holds every mission; resume continues
        page.goto(site.url + "/")
        click("form[action$='/body'] button")
        paused_tick = tick(home, 1)[0]
        page.goto(site.url + "/")
        held = paused_tick.get("paused") is True and "Resume GREG (signed)" in page.inner_text("main")
        click("form[action$='/body'] button")
        resumed_tick = tick(home, 1)[0]
        results["P11_pause_resume"] = held and not resumed_tick.get("paused")
        # P12 revoke: a second mission revoked before it acts never acts
        page.goto(site.url + "/")
        page.fill("input[name=effort_budget]", "3")
        click("form[action$='/first-mission'] button")
        click("form[action$='/sign'] button")
        tick(home, 1)
        second = [m for m in projection(console)["missions"] if m["status"] not in ("ACHIEVED",)]
        before = len(actions(home))
        page.goto(site.url + "/")
        revoked_id = second[0]["mission_id"] if second else None
        if revoked_id:
            page.locator(f"form[action$='/lifecycle']:has(input[value='{revoked_id}']):has(input[value='revoke']) button").click()
            page.wait_for_load_state()
            clicks += 1
        tick(home, 3)
        after = [a for a in actions(home)[before:] if a["mission_id"] == revoked_id]
        state = {m["mission_id"]: m["status"] for m in projection(console)["missions"]}.get(revoked_id)
        results["P12_revoke"] = revoked_id is not None and state == "ABANDONED" and not [a for a in after if a["status"] == "DONE"]
        # P13 memory after restart: a new console process sees the same institution
        site.close()
        console2 = Console(home, key=key)
        site = Site(console2)
        site.enter(page)
        page.goto(site.url + "/")
        again = page.inner_text("main")
        results["P13_memory_after_restart"] = "First Mission dossiers" in again and "ACHIEVED" in again
        # P14 product truth and authority refusals: VEPMC stays 0, Foundry count matches the contract,
        # a console without a key cannot sign, and the stop always works
        page.goto(site.url + "/mc/proof")
        proof = page.inner_text("main")
        page.goto(site.url + "/mc/organs")
        organs = page.inner_text("main")
        import yaml
        contract = yaml.safe_load((Path(__file__).resolve().parents[2] / "foundry/completion.yaml").read_text())
        complete = sum(1 for r in contract.values() if isinstance(r, dict) and r.get("state") == "COMPLETE")
        readonly = Site(Console(home))
        readonly.enter(page)
        page.goto(readonly.url + "/")
        disabled = page.locator("form[action$='/body'] button").get_attribute("disabled") is not None
        readonly.close()
        page.goto(site.url + "/")
        if EVIDENCE:
            Path(EVIDENCE).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(EVIDENCE) / f"mission-control-{device}.png"), full_page=False)
        click("form[action$='/stop'] button.danger >> nth=1")
        results["P14_truth_and_refusals"] = ("VEPMC" in proof and "\n0" in proof.replace("VEPMC\t", "\n") or "0 —" in proof) \
            and f"{complete}" in organs and disabled and (home / "STOP").exists() \
            and status(home)["single_bottleneck_metric"].get("VEPMC", 0) == 0
    finally:
        site.close()
        page.close()
    measured = {"device": device, "viewport": VIEWPORTS[device], "properties": results,
                "founder_clicks_to_verified_dossier_and_controls": clicks,
                "seconds": round(time.monotonic() - started, 2)}
    if EVIDENCE:
        (Path(EVIDENCE) / f"results-{device}.json").write_text(json.dumps(measured, indent=1))
    failed = [k for k, v in results.items() if not v]
    assert len(results) == 14 and not failed, measured


def test_baseline_classic_page_on_the_same_task(browser, tmp_path):
    """The classic page is the baseline: how many of the five questions it answers, and how the First Mission starts."""
    home, key, _, _ = make_body(tmp_path)
    kernel_copy(tmp_path)
    site = Site(Console(home, key=key))
    page = browser.new_page(viewport=VIEWPORTS["chromebook"])
    site.enter(page)
    try:
        page.goto(site.url + "/classic")
        text = page.inner_text("main")
        markers = {"What is GREG?": "persistent institution", "What can it actually do right now?": "Capability map",
                   "What is it doing?": "missions", "What valuable work can I command?": "First Mission",
                   "What needs my authority?": "decisions waiting"}
        answered = {q: m.lower() in text.lower() for q, m in markers.items()}
        page.fill("textarea[name=text]", "Run my first mission")       # the planner still routes plain words
        page.locator("form[action$='/ask'] button").click()
        page.wait_for_load_state()
        routed = "template:first-mission" in page.inner_text("main")
        page.goto(site.url + "/")
        mc_text = page.inner_text("main")
        mc_answered = {q: q in mc_text for q in QUESTIONS}
    finally:
        site.close()
        page.close()
    comparison = {"classic": {"questions_answered": sum(answered.values()), "detail": answered,
                              "first_mission_start": "type a sentence the planner recognizes, then review" if routed else "not reachable"},
                  "mission_control": {"questions_answered": sum(mc_answered.values()),
                                      "first_mission_start": "one button with a visible effort budget, then review"}}
    if EVIDENCE:
        Path(EVIDENCE).mkdir(parents=True, exist_ok=True)
        (Path(EVIDENCE) / "baseline.json").write_text(json.dumps(comparison, indent=1))
    assert comparison["mission_control"]["questions_answered"] == 5
    assert comparison["mission_control"]["questions_answered"] > comparison["classic"]["questions_answered"]
    assert routed, "the classic route to the same mission still works (no capability was removed)"
