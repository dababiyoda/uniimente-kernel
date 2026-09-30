"""The phone page shows a section-60 ask the way the founder must see it: costs, effect, uncertainty.

Real GREG code produces the asks (a compute bottleneck and a withheld plea) and the status
projection the phone reads; the real phone page (greg/phone) renders them in Chromium with an
iPhone profile. Only the transport is replaced: API reads are served from that projection
instead of through signed device reads, which tests/integration/test_greg_phone_e2e.py covers.
Chromium stands in for iOS Safari, which is not available here.
"""
import json
from pathlib import Path

import pytest

from greg import asks, compute
from greg.body import Body, status
from tests.greg_fixtures import make_body
from tests.integration.test_greg_phone_e2e import CHROMIUM

playwright = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(CHROMIUM is None, reason="needs a Chromium binary")
PHONE = Path(__file__).resolve().parents[2] / "greg/phone"
TYPES = {".html": "text/html", ".js": "text/javascript"}


def _asks(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        for i in range(compute.SUSTAINED_SAMPLES):
            compute.record_telemetry(body.journal, body.layout.home, telemetry={
                "at": f"2026-09-30T00:0{i}:00Z", "cores": 4, "load1": 5.0, "load_ratio": 1.25, "disk_free_ratio": 0.5,
                "memory_bytes": 1, "disk_total": 1, "disk_free": 1, "machine": "x86_64", "system": "Linux"})
        compute.recommend(body.journal)
        plea = asks.resource_request(
            request_id="req-plea", kind="RESOURCE", resource="account_access", why_now="Please, I need you",
            recommendation="grant the account", evidence={"failed_reads": 3},
            options=[{"option": "grant read access", "cost": "the account's exposure to GREG",
                      "expected_effect": "reads succeed"},
                     {"option": "do nothing", "cost": "none", "expected_effect": "the mission waits"}],
            expected_effect="reads succeed", uncertainty="3 failures observed",
            authority_requested={"spend": "none requested"}, consequence_of_no_response="the mission waits",
            created_at="2026-09-30T00:10:00Z")
        asks.record(body.journal, plea)
    return status(home)


def test_the_phone_shows_what_each_option_costs_and_never_the_withheld_plea(tmp_path):
    st = _asks(tmp_path)
    api = {"/api/hello": {"protocol": "greg-remote-v1", "body_id": st["body_id"]},
           "/api/status": {"principal": "device:iphone", "data": st},
           "/api/decisions": {"principal": "device:iphone", "data": st["decisions_required"]},
           "/api/vepmc": {"principal": "device:iphone", "VEPMC": 0, "missions": []},
           "/api/commands": {"principal": "device:iphone", "recent": [], "rejected": []}}

    def serve(route):
        path = "/" + route.request.url.split("://", 1)[1].split("/", 1)[1].split("?")[0]
        if path in api:
            return route.fulfill(status=200, content_type="application/json", body=json.dumps(api[path]))
        name = "index.html" if path == "/" else path.lstrip("/")
        file = PHONE / name
        if file.is_file():
            return route.fulfill(status=200, content_type=TYPES[file.suffix], body=file.read_bytes())
        return route.fulfill(status=404, body="")

    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=CHROMIUM)
        try:
            page = browser.new_context(**pw.devices["iPhone 13"]).new_page()
            page.route("http://localhost:9/**", serve)
            page.goto("http://localhost:9/")
            page.wait_for_selector("article.card", timeout=20000)
            cards = {c.get_attribute("data-request-id"): c.inner_text() for c in page.query_selector_all("article.card")}
            stop_text = page.evaluate("() => document.getElementById('stop').onclick.toString()")
        finally:
            browser.close()
    compute_card = next(text for rid, text in cards.items() if rid.startswith("req-compute-"))
    assert "metered provider price" in compute_card and "Uncertainty: prices and workload growth" in compute_card
    assert "Expected effect: missions stop queueing" in compute_card and "undefined" not in compute_card
    plea_card = cards["req-plea"]
    assert "Please, I need you" not in plea_card and "wording was withheld (emotional_manipulation)" in plea_card
    assert "the account's exposure to GREG" in plea_card                        # the facts and costs remain
    assert "on the Mac" not in stop_text                                          # Body 1 is a Chromebook
