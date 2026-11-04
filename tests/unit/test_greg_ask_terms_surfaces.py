"""Directive part 2 §9: every surface that offers an answer shows the authority an ask requests, what approving
covers, and what silence does.

Real GREG code records the asks (greg/asks.record, and the mission engine for the real approvals) and builds the
projection (greg.body.status). The console and Mission Control pages are rendered by their own code; the phone page
by greg/phone/app.js under node, with only the DOM, storage and transport stubbed. Chromium phone coverage is
tests/integration/test_greg_phone_asks.py.
"""
import html as html_text
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from greg import asks, blockers
from greg.body import Body, hold_ask, morning_projection, observe, status
from greg import console as console_page
from greg.console import Console, _ask_details, render_home, render_mission_control
from greg.missions import MissionBook
from provenance.ledger import sha256_json
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

ROOT = Path(__file__).resolve().parents[2]
SILENT_A = "the executed effect stands; nothing is run for it"
SILENT_B = "the mission waits; no action is taken"
SILENT_C = "missions continue at current capacity; nothing is bought"
SILENT_D = "the remote server is never called"
SILENT_P = "no money is spent; the mission waits"
SILENT_R = "the reservation stays booked at its cap"
SILENT_S = "the mandate lapses at its horizon"
SCOPE = {"capability": "fs.write", "target": "workspace:note.txt", "consequence_class": "internal_write",
         "cost_usd": 0.0}
MALFORMED = "hosts must be a list of host names"
COVERS = "Approving covers this exact scope: "
ABOVE = "the capability, target, consequence class and cost above"


def _approval(rid, recommendation, requested, consequence, kind="APPROVAL", alternatives=None):
    """Shaped as MissionEngine._request records one (greg/missions.py); why_now names the ask for the row lookup."""
    return {"request_id": rid, "mission_id": "m:terms", "kind": kind, "action_id": "write-note",
            "scope_digest": "sha256:" + "0" * 64, "why_now": f"{rid}: capability 'fs.write' outside scope",
            "recommendation": recommendation,
            "alternatives": alternatives or ["reject: the mission will try alternatives or ask again"],
            "authority_requested": requested, "consequence_of_no_response": consequence,
            "created_at": "2026-10-30T00:00:00Z", "reality_status": "RECORDED_LOCAL_MESSAGE"}


HOLD = hold_ask({"boot_id": "boot-1", "why": "req-H: the body crashed 3 times in 600 seconds",
                 "at": "2026-10-30T00:02:00Z"})


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
            request_id="req-C", kind="COMPUTE", resource="compute", why_now="req-C: load ratio above 1.2 for 5 samples",
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
        asks.record(b.journal, _approval("req-P", "approve fetch (http.get on web:example) at $2.5",
                                         {"capability": "http.get", "target": "web:example",
                                          "consequence_class": "external_read", "cost_usd": 2.5,
                                          "spend": "$2.50 for this one action"}, SILENT_P))
        asks.record(b.journal, _approval("req-R", "inspect the retained evidence, then state whether it executed",
                                         {"action_id": "pay", "attempt": 1}, SILENT_R, kind="RECONCILIATION",
                                         alternatives=["reconcile_executed", "reconcile_not_executed"]))
        # asks no DECISION closes: no answer buttons anywhere, but the same terms
        asks.record(b.journal, _approval("req-S", "sign a new MISSION with a new horizon",
                                         {"renew": "the mission's mandate", "spend": "none"}, SILENT_S,
                                         kind="SCOPE_RENEWAL"))
        asks.record(b.journal, HOLD)
    return home, key, body_id


def _text(page: str) -> str:
    return html_text.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)))


def _rows(page: str, *, markup=False) -> dict:
    """request id -> visible text (or ``markup``) of its whole decision row. A row ends at the </tr> that balances
    its <tr>, so an options table nested inside it stays in it. The id is the row's hidden request_id input, else
    its why_now marker (an ask with no answer buttons has no form)."""
    rows = {}
    for start in (m.start() for m in re.finditer(r"<tr><td><span class=pill>", page)):
        depth = 0
        for tag in re.finditer(r"<(/?)tr\b[^>]*>", page[start:]):
            depth += -1 if tag.group(1) else 1
            if depth == 0:
                row = page[start:start + tag.end()]
                break
        rid = re.search(r"name='request_id' value='([^']+)'", row) or re.search(r"\b(req-[A-Z]):", _text(row))
        if rid:
            rows[rid.group(1)] = row if markup else _text(row)
    return rows


def _terms(*, scope, covers=None, silent):
    """The lines one ask shows, in order (the phone shows every authority key; the console leaves out the ones its
    reach list already shows)."""
    return [x for x in ("Authority requested: " + scope, covers, "If you do not answer: " + silent) if x]


def _in_order(text: str, parts: list) -> bool:
    at = 0
    for part in parts:
        at = text.find(part, at)
        if at < 0:
            return False
        at += len(part)
    return True


NO_PARAMS = "params: not recorded with this ask. Asked for action write-note."
CONSOLE = {
    "req-A": _terms(scope="capability: fs.write; target: workspace:note.txt; consequence_class: "
                    "internal_write; cost_usd: 0", covers=f"{COVERS}mission m:terms; {ABOVE}; {NO_PARAMS}",
                    silent=SILENT_A),
    "req-B": ["the facts and options below are unchanged."] + _terms(
        scope="capability: fs.write; target: workspace:other.txt; consequence_class: internal_write; "
        "cost_usd: 0", covers=f"{COVERS}mission m:terms; {ABOVE}; {NO_PARAMS}", silent=SILENT_B),
    "req-C": ["rent a core", "do nothing"] + _terms(
        scope="spend: none requested; any purchase is a separate founder decision", silent=SILENT_C),
    # the malformed marker comes first: the reach list after it must not read as a narrow reach
    "req-D": ["This scope is malformed: " + MALFORMED, "Approving lets it: run files.list"] + _terms(
        scope="capability: mcp.act; target: mcp:files; consequence_class: external_contact; cost_usd: 0",
        covers=f"{COVERS}mission m:terms; {ABOVE}; {NO_PARAMS}", silent=SILENT_D),
    "req-P": _terms(scope="capability: http.get; target: web:example; consequence_class: external_read; "
                    "cost_usd: 2.5; spend: $2.50 for this one action",
                    covers=f"{COVERS}mission m:terms; {ABOVE}; the mission's spend and budget when it was asked "
                           f"(one paid approval funds one run); {NO_PARAMS}", silent=SILENT_P),
    "req-R": _terms(scope="action_id: pay; attempt: 1", silent=SILENT_R),
    "req-S": _terms(scope="renew: the mission's mandate; spend: none", silent=SILENT_S),
    "req-H": _terms(scope="body: resume (a signed BODY_RESUME); spend: none",
                    silent=HOLD["consequence_of_no_response"]),
}


@pytest.mark.parametrize("render", [render_home, lambda c: render_mission_control(c, "overview")],
                         ids=["console", "mission_control"])
def test_console_and_mission_control_show_the_authority_requested_and_what_silence_does(body, render):
    page = render(Console(body[0])).decode()
    rows, markup = _rows(page), _rows(page, markup=True)
    assert set(CONSOLE) <= set(rows)
    for rid, lines in CONSOLE.items():
        assert _in_order(rows[rid], lines), (rid, rows[rid])
    assert rows["req-D"].count("files.list") == 1     # the reach list shows the tool; the scope does not repeat it
    assert rows["req-D"].count(MALFORMED) == 1
    assert rows["req-C"].count("none requested; any purchase is a separate founder decision") == 1
    assert "Exact scope" not in "".join(rows.values())     # the line names the authority asked for, nothing more
    for rid in ("req-C", "req-R", "req-S", "req-H"):
        assert COVERS not in rows[rid], rid               # only an APPROVAL's answer covers a Gate scope
    for rid in ("req-S", "req-H"):
        assert "<button" not in markup[rid], rid


def test_the_console_escapes_the_scope_and_the_consequence():
    # scope values can derive from outside input (a target, an mcp host, a bound param); shown, never interpreted
    html = _ask_details({"kind": "APPROVAL", "authority_requested": {"target": "<img src=x onerror=alert(1)>"},
                         "bound_params": {"json": '{"c":"<svg onload=alert(3)>"}', "length": 29,
                                          "sha256": "sha256:" + "0" * 64},
                         "consequence_of_no_response": "<script>alert(2)</script>"})
    assert "<img" not in html and "<script" not in html and "<svg" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html and "&lt;script&gt;alert(2)&lt;/script&gt;" in html
    assert "&lt;svg onload=alert(3)&gt;" in html


# ---- real approvals, recorded by the mission engine and projected by greg.body.status --------------------------

CONTENT = 'PAYLOAD "quoted" <b>ok</b> café'
LONG = "x" * 2000


@pytest.fixture
def engine_body(tmp_path):
    """Two missions whose fs.write lies outside their light cone, so the engine itself asks to approve each."""
    home, key, body_id, _ = make_body(tmp_path)
    for mid, content in (("m:real", CONTENT), ("m:long", LONG)):
        drop(home, signed(key, body_id, "MISSION", mission(
            mid, checks=[note_check("c", workspace(home, mid) / "c.txt", "ok")],
            strategies=[write_strategy("w", "c.txt", content, ["c"])], capabilities=["fs.read"])))
    clock = Clock()
    with Body(home, clock=clock) as b:
        for _ in range(6):
            b.tick()
            clock.advance(1)
    return home, key, body_id


def _covers_real(mid, content):
    params = {"relative_path": "c.txt", "content": content}
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
    shown = canonical if len(canonical) <= 500 else canonical[:500] + "…"
    size = str(len(canonical)) if len(canonical) <= 500 else f"the first 500 of {len(canonical)}"
    return (f"{COVERS}mission {mid}; {ABOVE}; params {shown} ({size} characters of canonical JSON, "
            f"{sha256_json(params)}). Asked for action w.")


def _real_asks(home):
    return {r["mission_id"]: r for r in status(home)["decisions_required"] if r["mission_id"] in ("m:real", "m:long")}


def test_a_real_approval_shows_the_exact_scope_approving_covers(engine_body):
    home = engine_body[0]
    real = _real_asks(home)
    assert set(real) == {"m:real", "m:long"} and {r["kind"] for r in real.values()} == {"APPROVAL"}
    for r in real.values():           # the projection carries what the Gate digest binds, for display only
        assert r["action_id"] == "w" and r["bound_params"]["sha256"].startswith("sha256:")
    for page in (render_home(Console(home)), render_mission_control(Console(home), "overview")):
        rows = _rows(page.decode())
        for mid, content in (("m:real", CONTENT), ("m:long", LONG)):
            row = rows[real[mid]["request_id"]]
            assert _in_order(row, ["Authority requested: capability: fs.write; target: workspace:c.txt; "
                                   "consequence_class: internal_write; cost_usd: 0", _covers_real(mid, content),
                                   "If you do not answer: the mission waits; no action is taken"]), row
        assert "\\u00e9" in rows[real["m:real"]["request_id"]]   # non-ASCII and invisible characters show escaped


def test_both_surfaces_print_values_alike(tmp_path):
    values = [0.0, 5.0, 0.25, -0.0, 2.5, 1e21, 1.5e16, 1e-7, 0.000001, 123456789012345678901234, 7, True, False,
              None, {"b": 1.0, "a": [None, True, "x"], "é": {}, "10": 2}, [], "text, more", [1, [2.5, "y"]],
              {"\U0001F600": 1, "\uffff": 2}]     # code point order puts U+FFFF first; UTF-16 order would not
    script = tmp_path / "shown.mjs"
    script.write_text(f"import {{ shownValue }} from {json.dumps((ROOT / 'greg/phone/core.js').as_uri())};\n"
                      f"console.log(JSON.stringify(JSON.parse({json.dumps(json.dumps(values))}).map(shownValue)));\n")
    if shutil.which("node") is None or _node_major() < 20:
        pytest.skip("needs node >= 20")
    out = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    phone = json.loads(out.stdout)
    console = [console_page._shown(v) for v in values]
    assert phone == console
    assert console[:4] == ["0", "5", "0.25", "0"] and console[11:14] == ["true", "false", "null"]
    assert console[-1] == "{\uffff: 2, \U0001F600: 1}"


def _node_major():
    try:
        return int(subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
                   .lstrip("v").split(".")[0])
    except (OSError, ValueError):
        return 0


# Only what greg/phone/app.js touches: elements, the stored device key, and the API it reads and posts to.
PHONE = """
import { readFileSync } from "node:fs";
import { askAnswers, newDeviceKey } from %(core)s;
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
  const pressed = [];   // [label, answer, the signed envelope]: what each button says, and what it signs
  for (const b of buttons(card)) {
    const before = sent.length;
    await b.onclick();
    pressed.push([b.textContent, sent[before]?.body.answer, sent[before]]);
  }
  cards[card.dataset.requestId] = { text: text(card), lines: card.children.map((c) => c.textContent), pressed };
}
const offered = Object.fromEntries(st.decisions_required.map((r) => [r.request_id, askAnswers(r)]));
console.log(JSON.stringify({ cards, offered, device: device.publicHex, state: nodes.state?.textContent }));
process.exit(0);
"""


def _phone(home, tmp_path):
    projection = tmp_path / "status.json"
    projection.write_text(json.dumps(status(home)))
    script = tmp_path / "phone.mjs"
    script.write_text(PHONE % {"core": json.dumps((ROOT / "greg/phone/core.js").as_uri()),
                               "app": json.dumps((ROOT / "greg/phone/app.js").as_uri()),
                               "status": json.dumps(str(projection))})
    out = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


NEEDS_NODE = pytest.mark.skipif(shutil.which("node") is None or _node_major() < 20,
                                reason="needs node >= 20 (global WebCrypto)")
# The phone has no reach list: its authority line names every key, and GREG's withheld wording reads differently.
PHONE_SCOPE = {"req-D": "capability: mcp.act; target: mcp:files; consequence_class: external_contact; cost_usd: 0; "
                        "tool: files.list"}


def _phone_lines(rid):
    lines = [x for x in CONSOLE[rid] if not x.startswith(("Approving lets it", "the facts and options below"))]
    return ["Authority requested: " + PHONE_SCOPE[rid] if rid in PHONE_SCOPE and x.startswith("Authority requested")
            else x for x in lines]


@NEEDS_NODE
def test_the_phone_shows_the_same_terms_and_sends_only_answers_the_body_applies(body, tmp_path):
    home, key, body_id = body
    phone = _phone(home, tmp_path)
    cards = {("req-H" if rid == HOLD["request_id"] else rid): c for rid, c in phone["cards"].items()}
    assert set(CONSOLE) <= set(cards), phone["state"]
    for rid in CONSOLE:
        assert _in_order(cards[rid]["text"], _phone_lines(rid)), (rid, cards[rid]["text"])
    lines = cards["req-D"]["lines"]
    assert lines.index("This scope is malformed: " + MALFORMED) < lines.index("Authority requested: "
                                                                               + PHONE_SCOPE["req-D"])
    # Each button's label against the answer it signs: a swapped label would, for one, book a dispatch the
    # founder says happened as not executed.
    pairs = {rid: [p[:2] for p in c["pressed"]] for rid, c in cards.items()}
    for rid in ("req-A", "req-B", "req-C", "req-D", "req-P"):
        assert pairs[rid] == [["Approve", "approve"], ["Reject", "reject"]], rid
    assert pairs["req-R"] == [["It happened", "reconcile_executed"], ["It did not happen", "reconcile_not_executed"]]
    assert pairs["req-S"] == pairs["req-H"] == []
    # askAnswers itself offers nothing on an ask no DECISION closes, whoever calls it
    assert phone["offered"]["req-S"] == phone["offered"][HOLD["request_id"]] == []
    assert phone["offered"]["req-R"] == pairs["req-R"]
    # The body applies what the phone itself signed, once the founder has delegated DECISION to that device key:
    # the approve on the APPROVAL and "It happened" on the RECONCILIATION.
    with Body(home) as b:
        expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
        enrolled = b.apply(signed(key, body_id, "DEVICE_ENROLL", {"public_key": phone["device"], "label": "phone",
                                                                  "kinds": ["DECISION"], "expires_at": expires}))
        assert enrolled["status"] == "APPLIED", enrolled
        for rid in ("req-A", "req-R"):
            envelope = cards[rid]["pressed"][0][2]
            assert envelope["founder_key_id"] == enrolled["result"]["device_key_id"]   # the device's key
            result = b.apply(envelope)
            assert result["status"] == "APPLIED", (rid, result)


@NEEDS_NODE
def test_the_phone_shows_what_a_real_approval_covers(engine_body, tmp_path):
    home = engine_body[0]
    real = _real_asks(home)
    cards = _phone(home, tmp_path)["cards"]
    for mid, content in (("m:real", CONTENT), ("m:long", LONG)):
        card = cards[real[mid]["request_id"]]
        assert _in_order(card["text"], ["Authority requested: capability: fs.write; target: workspace:c.txt; "
                                        "consequence_class: internal_write; cost_usd: 0", _covers_real(mid, content),
                                        "If you do not answer: the mission waits; no action is taken"]), card["text"]
        assert [p[:2] for p in card["pressed"]] == [["Approve", "approve"], ["Reject", "reject"]]


# ---- compensation approvals: approving runs the action that undoes w, never w again ------------------------------

RESTORE = {"capability": "fs.write", "params": {"relative_path": "note.txt", "content": "original"},
           "target": "workspace:note.txt"}


@pytest.fixture(scope="module")
def compensation_body(tmp_path_factory):
    """Both compensation APPROVAL sites of greg/missions.py, set up as tests/integration/test_greg_compensation.py
    does. Action w wrote "draft"; each mission signed a compensation that writes "original" back. m:comp is
    superseded, so a successor may rely on the write. m:late is abandoned after its signed horizon, so the Gate puts
    the compensation outside the scope."""
    home, key, body_id, _ = make_body(tmp_path_factory.mktemp("compensation"))
    horizon = datetime.now(timezone.utc) + timedelta(seconds=6)    # the Gate judges the horizon on the wall clock
    for mid in ("m:comp", "m:late"):
        note = workspace(home, mid) / "note.txt"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text("original")
        spec = mission(mid, checks=[note_check("c", note, "final")], capabilities=["fs.read", "fs.write"],
                       strategies=[write_strategy("w", "note.txt", "draft", ["c"], compensate=RESTORE)])
        if mid == "m:late":
            spec["light_cone"]["horizon"] = horizon.isoformat().replace("+00:00", "Z")
        drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as b:
        for _ in range(3):
            b.tick()
            clock.advance(1)
        assert [(workspace(home, mid) / "note.txt").read_text() for mid in ("m:comp", "m:late")] == ["draft"] * 2
        while datetime.now(timezone.utc) <= horizon:
            time.sleep(0.1)
        for mid, state in (("m:comp", "SUPERSEDED"), ("m:late", "ABANDONED")):
            drop(home, signed(key, body_id, "LIFECYCLE", {"mission_id": mid, "state": state, "reason": "not wanted"}))
        for _ in range(3):
            b.tick()
            clock.advance(1)
    return home, key, body_id


def _compensation_asks(home):
    found = {r["mission_id"]: r for r in status(home)["decisions_required"]
             if r["kind"] == "APPROVAL" and r["mission_id"] in ("m:comp", "m:late")}
    assert set(found) == {"m:comp", "m:late"}, status(home)["decisions_required"]
    # one ask from each site: the superseded mission's, and the Gate's refusal after the horizon
    assert "superseded" in found["m:comp"]["why_now"] and "horizon" in found["m:late"]["why_now"]
    assert {r["action_id"] for r in found.values()} == {"w"}
    return found


def _covers_compensation(mid):
    params = RESTORE["params"]
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return (f"{COVERS}mission {mid}; {ABOVE}; params {canonical} ({len(canonical)} characters of canonical JSON, "
            f"{sha256_json(params)}). Asked to compensate action w.")


def test_a_compensation_approval_names_the_compensation_not_the_action_it_undoes(compensation_body):
    home = compensation_body[0]
    found = _compensation_asks(home)
    for page in (render_home(Console(home)), render_mission_control(Console(home), "overview")):
        rows = _rows(page.decode())
        for mid, r in found.items():
            row = rows[r["request_id"]]
            assert _in_order(row, [_covers_compensation(mid), "If you do not answer: " + SILENT_A]), row
            assert "Asked for action" not in row        # w wrote "draft": approving never runs w again


@NEEDS_NODE
def test_the_phone_names_the_compensation_too(compensation_body, tmp_path):
    home = compensation_body[0]
    found = _compensation_asks(home)
    cards = _phone(home, tmp_path)["cards"]
    for mid, r in found.items():
        card = cards[r["request_id"]]
        assert _in_order(card["text"], [_covers_compensation(mid), "If you do not answer: " + SILENT_A]), card["text"]
        assert "Asked for action" not in card["text"]


# ---- the typed blockers (greg/blockers.py, from #251): the morning report, Mission Control's Goals page, greg blockers

def _blocked_goals(page: str) -> dict:
    """Mission Control's Blocked goals rows, keyed by mission, as visible text."""
    section = page.split("<h2>Blocked goals</h2>", 1)[1].split("</section>", 1)[0]
    return {(t := _text(row).strip()).split()[0]: t for row in re.findall(r"<tr>(.*?)</tr>", section, re.S)[1:]}


def test_a_typed_blocker_says_what_approving_covers_and_what_silence_does(engine_body):
    home = engine_body[0]
    real = _real_asks(home)
    shown = morning_projection(home)["blockers"]
    assert isinstance(shown, list), shown              # computed, not "unavailable"
    records = {b["mission_id"]: b for b in shown}
    page = render_mission_control(Console(home), "goals").decode()
    goals = _blocked_goals(page)
    assert "<b>ok</b>" not in page                    # a bound param is shown, never interpreted
    for mid, content in (("m:real", CONTENT), ("m:long", LONG)):
        b, rid = records[mid], real[mid]["request_id"]
        assert b["kind"] == "decision" and b["blocker"] == f"founder decision: APPROVAL ask {rid} on action w"
        # "answering exactly" names every part the digest binds, as the console and phone do before their buttons
        assert b["required_authority"].endswith('"target": "workspace:c.txt"}. ' + _covers_real(mid, content)), b
        assert b["next_move"].endswith("; if you do not answer: " + SILENT_B), b
        assert _in_order(goals[mid], [b["blocker"], _covers_real(mid, content), "if you do not answer: " + SILENT_B])


def test_a_compensation_approval_is_never_typed_as_the_action_it_undoes(compensation_body):
    home = compensation_body[0]
    found = _compensation_asks(home)
    # Today neither compensation ask blocks a pursued mission: both are asked once the mission is SUPERSEDED or
    # ABANDONED, and no surface lists those missions' blockers.
    shown = morning_projection(home)["blockers"]
    assert isinstance(shown, list) and not {b["mission_id"] for b in shown} & set(found), shown
    assert not set(_blocked_goals(render_mission_control(Console(home), "goals").decode())) & set(found)
    # Were one typed, it would name the compensation, as the console and phone do.
    with observe(home, actor="spiffe://uniimente.internal/greg/morning-reader") as journal:
        book = MissionBook(journal)
        book.rebuild()
        for mid, r in found.items():
            rid = r["request_id"]
            held = SimpleNamespace(mission_id=mid, blocker={"type": "decision", "request_id": rid, "action_id": "w"})
            b = blockers.typed(held, book, "awaiting founder", None)
            assert b["blocker"] == f"founder decision: APPROVAL ask {rid} to compensate action w", b
            assert b["required_authority"].endswith(". " + _covers_compensation(mid)), b
            assert b["next_move"].endswith("; if you do not answer: " + SILENT_A), b
            assert "on action" not in b["blocker"] and "Asked for action" not in b["required_authority"]
