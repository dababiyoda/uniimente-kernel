"""Directive part 2 §9: every surface that offers an answer shows the ask's exact scope and what silence does.

Real GREG code records the asks (greg/asks.record) and builds the projection (greg.body.status). The console and
Mission Control pages are rendered by their own code; the phone page by greg/phone/app.js under node, with only the
DOM, storage and transport stubbed. Chromium phone coverage is tests/integration/test_greg_phone_asks.py.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from greg import asks
from greg.body import Body, status
from greg.console import Console, _ask_details, render_home, render_mission_control
from tests.greg_fixtures import make_body, signed

ROOT = Path(__file__).resolve().parents[2]
SILENT_A = "the executed effect stands; nothing is run for it"
SILENT_B = "the mission waits; no action is taken"
SILENT_C = "missions continue at current capacity; nothing is bought"
SILENT_D = "the remote server is never called"
SILENT_R = "the reservation stays booked at its cap"
SCOPE = {"capability": "fs.write", "target": "workspace:note.txt", "consequence_class": "internal_write",
         "cost_usd": 0.0}
MALFORMED = "hosts must be a list of host names"


def _approval(rid, recommendation, requested, consequence, kind="APPROVAL", alternatives=None):
    """Shaped as MissionEngine._request records one (greg/missions.py)."""
    return {"request_id": rid, "mission_id": "m:terms", "kind": kind, "action_id": "write-note",
            "scope_digest": "sha256:" + "0" * 64, "why_now": "capability 'fs.write' outside scope",
            "recommendation": recommendation,
            "alternatives": alternatives or ["reject: the mission will try alternatives or ask again"],
            "authority_requested": requested, "consequence_of_no_response": consequence,
            "created_at": "2026-10-30T00:00:00Z", "reality_status": "RECORDED_LOCAL_MESSAGE"}


@pytest.fixture
def body(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as b:
        asks.record(b.journal, _approval("req-A", "approve write-note (fs.write on workspace:note.txt) at $0.0",
                                         dict(SCOPE), SILENT_A))
        # the wording screen replaces the whole recommendation, until now the only place the scope was readable
        asks.record(b.journal, _approval("req-B", "approve write-note (fs.write on workspace:other.txt) at $0.0: "
                                         "do it immediately", {**SCOPE, "target": "workspace:other.txt"}, SILENT_B))
        asks.record(b.journal, asks.resource_request(
            request_id="req-C", kind="COMPUTE", resource="compute", why_now="load ratio above 1.2 for 5 samples",
            recommendation="add a core", evidence={"load_ratio": [1.25] * 5},
            options=[{"option": "rent a core", "cost": "$5/month", "expected_effect": "missions stop queueing"},
                     {"option": "do nothing", "cost": "none", "expected_effect": "missions keep queueing"}],
            expected_effect="missions stop queueing", uncertainty="prices vary",
            authority_requested={"spend": "none requested; any purchase is a separate founder decision"},
            consequence_of_no_response=SILENT_C, created_at="2026-10-30T00:01:00Z"))
        # a malformed mcp scope (greg/missions.py exact_reach) must read as malformed, never as a narrow reach
        asks.record(b.journal, _approval("req-D", "approve call (mcp.act on mcp:files) at $0.0",
                                         {"capability": "mcp.act", "target": "mcp:files",
                                          "consequence_class": "external_contact", "cost_usd": 0.0,
                                          "tool": "files.list", "malformed": MALFORMED}, SILENT_D))
        asks.record(b.journal, _approval("req-R", "inspect the retained evidence, then state whether it executed",
                                         {"action_id": "pay", "attempt": 1}, SILENT_R, kind="RECONCILIATION",
                                         alternatives=["reconcile_executed", "reconcile_not_executed"]))
    return home, key, body_id


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).replace("&#x27;", "'")


def _rows(page: str) -> dict:
    """request id -> visible text of its decision row (the row carries the id in its hidden form inputs)."""
    rows = {}
    for row in re.findall(r"<tr><td><span class=pill>.*?</td></tr>", page, flags=re.S):
        rid = re.search(r"name='request_id' value='([^']+)'", row)
        if rid:
            rows[rid.group(1)] = _text(row)
    return rows


@pytest.mark.parametrize("render", [render_home, lambda c: render_mission_control(c, "overview")],
                         ids=["console", "mission_control"])
def test_console_and_mission_control_show_the_exact_scope_and_what_silence_does(body, render):
    page = render(Console(body[0])).decode()
    rows = _rows(page)
    assert {"req-A", "req-B", "req-D", "req-R"} <= set(rows)
    for rid, silent in (("req-A", SILENT_A), ("req-B", SILENT_B), ("req-D", SILENT_D), ("req-R", SILENT_R)):
        assert "If you do not answer: " + silent in rows[rid], rid
    assert "Exact scope of this ask: capability: fs.write; target: workspace:other.txt; " \
           "consequence_class: internal_write; cost_usd: 0.0" in rows["req-B"]   # withheld wording hides nothing
    assert "malformed: " + MALFORMED in rows["req-D"]
    assert rows["req-D"].count("files.list") == 1          # the reach list shows the tool; the scope does not repeat it
    text = _text(page)
    assert "If you do not answer: " + SILENT_C in text
    assert text.count("none requested; any purchase is a separate founder decision") == 1


def test_the_console_names_the_action_when_the_projection_carries_it():
    shown = _text(_ask_details({"kind": "APPROVAL", "action_id": "write-note", "authority_requested": dict(SCOPE)}))
    assert "Exact scope of this ask: action: write-note; capability: fs.write" in shown


def test_the_console_escapes_the_scope_and_the_consequence():
    # scope values can derive from outside input (a target, an mcp host); they are shown, never interpreted
    html = _ask_details({"kind": "APPROVAL", "authority_requested": {"target": "<img src=x onerror=alert(1)>"},
                         "consequence_of_no_response": "<script>alert(2)</script>"})
    assert "<img" not in html and "<script" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html and "&lt;script&gt;alert(2)&lt;/script&gt;" in html


def _node_major():
    try:
        return int(subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
                   .lstrip("v").split(".")[0])
    except (OSError, ValueError):
        return 0


# Only what greg/phone/app.js touches: elements, the stored device key, and the API it reads and posts to.
PHONE = """
import { readFileSync } from "node:fs";
import { newDeviceKey } from %(core)s;
const st = JSON.parse(readFileSync(%(status)s, "utf8"));
const nodes = {};
class N {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.textContent = this.className = this.value = ""; }
  append(...c) { this.children.push(...c); }
  replaceChildren(...c) { this.children = c; }
  setAttribute() {}
  get lastChild() { return this.children[this.children.length - 1]; }
}
globalThis.document = { getElementById: (id) => (nodes[id] ??= new N("div")), createElement: (t) => new N(t),
                        body: new N("body") };
const device = await newDeviceKey();
const later = (req) => { setTimeout(() => req.onsuccess()); return req; };
globalThis.indexedDB = { open: () => later({ result: { transaction: () => ({ objectStore: () => ({
  get: () => later({ result: device }) }) }) } }) };
const api = { "/api/hello": { body_id: st.body_id }, "/api/status": { data: st },
              "/api/decisions": { data: st.decisions_required }, "/api/vepmc": { VEPMC: 0, missions: [] },
              "/api/commands": { principal: "device:phone" } };
const sent = [];
globalThis.fetch = async (path, init = {}) => {
  if (path === "/api/command") { sent.push(JSON.parse(init.body)); return { ok: true, json: async () => ({}) }; }
  return { ok: path in api, status: path in api ? 200 : 404, json: async () => api[path] ?? { error: "absent" } };
};
await import(%(app)s);
for (let i = 0; i < 500 && !nodes.decisions?.children.length; i++) await new Promise((r) => setTimeout(r, 10));
const text = (n) => [n.textContent, ...n.children.map(text)].filter(Boolean).join("\\n");
const buttons = (n) => (n.tag === "button" ? [n] : n.children.flatMap(buttons));
const cards = {};
for (const card of nodes.decisions?.children || []) {
  const answers = [];
  for (const b of buttons(card)) { const before = sent.length; await b.onclick(); answers.push(sent[before]?.body.answer); }
  cards[card.dataset.requestId] = { text: text(card), answers };
}
console.log(JSON.stringify({ cards, state: nodes.state?.textContent }));
process.exit(0);
"""


@pytest.mark.skipif(shutil.which("node") is None or _node_major() < 20, reason="needs node >= 20 (global WebCrypto)")
def test_the_phone_shows_the_same_terms_and_sends_only_answers_the_body_applies(body, tmp_path):
    home, key, body_id = body
    projection = tmp_path / "status.json"
    projection.write_text(json.dumps(status(home)))
    script = tmp_path / "phone.mjs"
    script.write_text(PHONE % {"core": json.dumps((ROOT / "greg/phone/core.js").as_uri()),
                               "app": json.dumps((ROOT / "greg/phone/app.js").as_uri()),
                               "status": json.dumps(str(projection))})
    out = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    phone = json.loads(out.stdout)
    cards = phone["cards"]
    assert {"req-A", "req-B", "req-C", "req-D", "req-R"} <= set(cards), phone["state"]
    for rid, silent in (("req-A", SILENT_A), ("req-B", SILENT_B), ("req-C", SILENT_C), ("req-D", SILENT_D),
                        ("req-R", SILENT_R)):
        assert "If you do not answer: " + silent in cards[rid]["text"], rid
    assert "Exact scope of this ask: capability: fs.write; target: workspace:other.txt; " \
           "consequence_class: internal_write; cost_usd: 0" in cards["req-B"]["text"]
    assert "tool: files.list; malformed: " + MALFORMED in cards["req-D"]["text"]
    assert cards["req-A"]["answers"] == ["approve", "reject"]
    assert cards["req-R"]["answers"] == ["reconcile_executed", "reconcile_not_executed"]
    # The body applies the first answer each card sends (founder-signed here; the device path is
    # tests/integration/test_greg_phone_e2e.py). A RECONCILIATION refuses approve.
    with Body(home) as b:
        for rid in ("req-A", "req-R"):
            result = b.apply(signed(key, body_id, "DECISION", {"request_id": rid, "answer": cards[rid]["answers"][0],
                                                                "reason": ""}))
            assert result["status"] == "APPLIED", rid
