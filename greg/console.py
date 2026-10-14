"""GREG console: the one founder-facing interface, on this computer.

    python -m greg console --key ~/.greg-founder.pem        (prints a private link on 127.0.0.1:8766; the phone channel keeps 8765)

Alfonso says what he wants in plain words, reviews what GREG proposes and exactly
what signing it would let GREG do, signs, and closes the window. The body keeps
working under its supervisor. The console is not the body and not a second Kernel:

* it reads retained history only through the read-only observer (never the writer);
* its only write is a founder-signed command file dropped into the body inbox;
* the founder key is decrypted once at start and held in this process's memory only;
  without a key the console is read-only;
* it binds to 127.0.0.1 and refuses any other Host header (DNS rebinding);
* private reads and every POST require the owner's private session, established once from the
  single-use link ``greg console`` prints, in addition to the per-process CSRF token and same-origin
  POSTs. Loopback reachability alone never authorizes use of the unlocked founder key: any local
  process (a worker keeps host networking for its provider) can reach 127.0.0.1. Extracted from #157;
  the session cookie is scoped to a random path because cookies are not port-scoped;
* it caps request sizes. Owned public pages (/owned) stay readable without the session.

Mechanism lineage: #112 egregore/local_console.py (loopback page, Host check, CSRF,
head-bound review), now driving the canonical #113 body with real Ed25519 signatures
instead of synthetic development authority. That module left the active tree on 2026-09-30
(directive section 76; last in commit 6e0533f).
"""
from __future__ import annotations

import html
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, quote, urlsplit

from greg import metrics, planner
from greg.body import Layout, morning_projection, observe, send_signed, status

MAX_BODY = 16 * 1024
OWNER_COOKIE = "greg_console_owner"
PRIVATE = b"private owner session required; open the link printed by greg console"
STYLE = """
:root{--bg:#f5f6f4;--fg:#18242b;--muted:#5d6b73;--card:#fff;--line:#d5dcd9;--accent:#1f5f8b;--warn:#9a3b12;--ok:#2f6b3a}
@media (prefers-color-scheme:dark){:root{--bg:#121719;--fg:#e4e9eb;--muted:#9aa7ad;--card:#1b2226;--line:#2d383d;
--accent:#7ab7e0;--warn:#f0a07a;--ok:#8fd19e}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg)}
main{max-width:1000px;margin:0 auto;padding:16px;overflow-wrap:anywhere}h1{font-size:22px;margin:4px 0 12px}h2{font-size:17px;margin:0 0 8px}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:12px 0}
.muted{color:var(--muted)}.warn{color:var(--warn)}.ok{color:var(--ok)}table{border-collapse:collapse;width:100%}
td,th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
textarea,input{width:100%;font:inherit;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
button{font:inherit;padding:7px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer}
button.secondary{background:transparent;color:var(--accent)}button.danger{border-color:var(--warn);background:var(--warn)}
button[disabled]{opacity:.45;cursor:not-allowed}form.inline{display:inline}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;border:1px solid var(--line);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.stat b{display:block;font-size:20px}
@media (max-width:600px){td,th{padding:4px}main{padding:10px}textarea,input,button{font-size:16px}}
"""


def _e(value) -> str:
    return html.escape(str(value), quote=True)


class Console:
    """State held by one console process: the unlocked key, CSRF token, pending proposals."""

    def __init__(self, home: str | Path, *, key=None, transport=None, planner_context=None,
                 transport_factory=None):
        self.home = Path(home).expanduser().resolve()
        self.layout = Layout(self.home)
        self.key = key
        self.transport = transport
        self.transport_factory = transport_factory
        self._route_revision = None
        self.csrf = secrets.token_urlsafe(32)
        # Interface authentication only: commands still carry the founder's Ed25519 signature and pass the
        # body and Gate. None of these values reaches argv, the environment, body events or a public page.
        self._bootstrap = secrets.token_urlsafe(32)
        self._session = secrets.token_urlsafe(32)
        self.owner_path = "/owner/" + secrets.token_urlsafe(24) + "/"
        self.proposals: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.planner_context = planner_context
        self.flash: list[str] = []

    def owner_url(self, port: int) -> str:
        """The private, single-use link for the local owner who started this console."""
        return f"http://127.0.0.1:{port}{self.owner_path}?access={self._bootstrap}"

    def bootstrap(self, token: str) -> bool:
        with self.lock:
            if self._bootstrap is None or not secrets.compare_digest(token.encode(), self._bootstrap.encode()):
                return False
            self._bootstrap = None
            return True

    # -- reading ----------------------------------------------------------------------
    def snapshot(self) -> dict:
        state = status(self.home)
        with observe(self.home, actor="spiffe://uniimente.internal/greg/console") as journal:
            from greg.missions import MissionBook
            book = MissionBook(journal)
            missions = [{"mission_id": mid, "status": m.status, "paused": m.paused, "blocker": m.blocker,
                         "next_observe_at": m.next_observe_at, "actions_done": m.actions_done,
                         "intended_effect": m.spec["intended_effect"], "closure": m.spec["closure"]["kind"]}
                        for mid, m in sorted(book.missions.items())]
            from greg.presentation import cognitive_summaries
            cognitive = cognitive_summaries(journal)
            vepmc = metrics.vepmc(journal)
            recent = [{"type": e.type[len("greg."):], "at": e.occurred_at,
                       "mission_id": e.payload.get("mission_id"), "summary": _summary(e)}
                      for e in journal.replay()[-25:]][::-1]
        deliveries = []
        folder = self.deliver_root() / "briefs"
        if folder.is_dir():
            deliveries = [p.name for p in sorted(folder.glob("*.md"), key=lambda p: p.stat().st_mtime,
                                                   reverse=True)[:10]]
        return {"status": state, "missions": missions, "vepmc": vepmc, "recent": recent, "deliveries": deliveries, "cognitive": cognitive}

    def deliver_root(self) -> Path:
        config = json.loads(self.layout.config.read_text())
        return Path(config.get("deliver_root") or self.home / "deliveries")

    def context(self) -> planner.PlannerContext:
        if self.planner_context is not None:
            return self.planner_context
        config = json.loads(self.layout.config.read_text())
        return planner.PlannerContext(read_roots=tuple(Path(r) for r in config["read_roots"]),
                                      capabilities=status(self.home)["capabilities"],
                                      workspace=self.layout.workspace)

    # -- acting (signed files only) -----------------------------------------------------
    def sign(self, kind: str, body: dict) -> Path:
        if self.key is None:
            raise PermissionError("this console has no founder key; restart it with --key to sign")
        return send_signed(self.home, self.key, kind, body)

    def _refresh_transport(self):
        """A signed detach also invalidates drafts in an already open console."""
        if self.transport_factory is None:
            return
        with observe(self.home, actor="spiffe://uniimente.internal/greg/console-model-reader") as journal:
            from greg.models import effective_route_config
            events = journal.replay("model.configured")
            revision = events[-1].event_id if events else None
            if revision == self._route_revision:
                return
            base = json.loads(self.layout.config.read_text()).get("models")
            selected = effective_route_config(base, journal)
        replacement = self.transport_factory(selected)
        with self.lock:
            self.transport = replacement
            self.proposals.clear()
            self._route_revision = revision

    def ask(self, text: str) -> str:
        self._refresh_transport()
        revision = self._route_revision
        proposal = planner.propose(text, self.context(), transport=self.transport)
        self._refresh_transport()
        if self._route_revision != revision:
            proposal = {"status": "FAILED", "why": "model route changed during drafting; ask again"}
        pid = secrets.token_urlsafe(9)
        with self.lock:
            self.proposals[pid] = {"text": text, "proposal": proposal, "at": time.time()}
            for old in sorted(self.proposals, key=lambda k: self.proposals[k]["at"])[:-20]:
                self.proposals.pop(old)
        return pid

    def first_mission(self, effort_budget: str) -> str:
        """Draft the Founder's First Mission for review; nothing runs until it is signed."""
        try:
            effort = int(effort_budget)
        except (TypeError, ValueError):
            raise ValueError("the effort budget is a whole number from 1 to 200") from None
        text = (f"Run the Founder's First Mission with effort budget {effort}: understand where I am trying to go, "
                "find the highest-value unfinished work you can advance now, compare the ways to do it, produce "
                "something useful, verify it and tell me what is next.")
        proposal = planner._first_mission_route(text, self.context()) if 1 <= effort <= 200 else {
            "status": "NEEDS_INPUT", "origin": "template:first-mission",
            "questions": ["An effort budget is a whole number of units from 1 to 200."]}
        pid = secrets.token_urlsafe(9)
        with self.lock:
            self.proposals[pid] = {"text": text, "proposal": proposal, "at": time.time()}
        return pid

    def venture_rehearsal(self) -> str:
        """Draft the FIXTURE commerce rehearsal of the latest First Mission dossier, for review before signing."""
        from greg.venture_rehearsal import latest_canon, venture_rehearsal
        canon, source = latest_canon(self.deliver_root())
        text = f"[FIXTURE] Rehearse selling and delivering my latest First Mission dossier ({Path(source).name})."
        proposal = {"status": "PROPOSED", "origin": "template:venture-rehearsal", "spec": venture_rehearsal(canon=canon),
                    "notes": ["FIXTURE: the buyer is a published test key and the consideration is a fixture amount; "
                              "no payment rail is called and nothing is published",
                              "every step runs through the Foundry bridge inside this mission's workspace",
                              "the appraisal re-observes the company, the delivery, the acceptance and the books"]}
        pid = secrets.token_urlsafe(9)
        with self.lock:
            self.proposals[pid] = {"text": text, "proposal": proposal, "at": time.time()}
        return pid

    def attach(self, request_id: str, capability_id: str) -> Path:
        """Sign CAPABILITY_ATTACH only for a verified candidate that an open capability ask names."""
        open_asks = {r["request_id"]: r for r in status(self.home)["decisions_required"]}
        if capability_id not in {c["capability_id"] for c in _attachable(open_asks.get(request_id, {}))}:
            raise ValueError("that capability is not a verified candidate of an open capability ask")
        return self.sign("CAPABILITY_ATTACH", {"capability_id": capability_id})

    def sign_proposal(self, pid: str) -> Path:
        self._refresh_transport()
        with self.lock:
            entry = self.proposals.get(pid)
        if entry is None or entry["proposal"].get("status") != "PROPOSED":
            raise ValueError("unknown or unsignable proposal")
        path = self.sign("MISSION", entry["proposal"]["spec"])
        with self.lock:
            self.proposals.pop(pid, None)
        return path


def _summary(event) -> str:
    p = event.payload
    for key in ("state", "status", "verdict", "kind", "reason", "why_now", "check_id"):
        if key in p and isinstance(p[key], (str, int, float, bool)):
            return f"{key}={p[key]}"
    return ""


# -- rendering ------------------------------------------------------------------------------

def _page(title: str, body: str, *, refresh: bool = False) -> bytes:
    meta = '<meta http-equiv="refresh" content="15">' if refresh else ""
    return ("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,"
            f"initial-scale=1'>{meta}<title>{_e(title)}</title><style>{STYLE}</style><main>{body}</main></html>"
            ).encode()


def _ask_details(r: dict) -> str:
    """Section 60 on the page: what each option costs and does, how sure GREG is, what it needs."""
    parts = []
    if r.get("wording_withheld"):
        parts.append("<br><b>GREG's wording was withheld</b> (" + _e(", ".join(r["wording_withheld"]["rules"]))
                     + "); the facts and options below are unchanged.")
    if r.get("answer_effect"):
        parts.append("<br><b>What your answer does:</b> " + _e(r["answer_effect"]))
    if r.get("expected_effect"):
        parts.append("<br>Expected effect: " + _e(r["expected_effect"]))
    if r.get("options"):
        parts.append("<table>" + "".join(f"<tr><td>{_e(o['option'])}</td><td>{_e(o['cost'])}</td>"
                                         f"<td class=muted>{_e(o['expected_effect'])}</td></tr>"
                                         for o in r["options"]) + "</table>")
    if r.get("uncertainty"):
        parts.append("<span class=muted>Uncertainty: " + _e(r["uncertainty"]) + "</span>")
    for c in _attachable(r):
        mech = c.get("mechanism") or {}
        q = mech.get("qualification") or {}
        source = (mech.get("upstream") or {}).get("source") or "upstream not declared"
        parts.append(f"<br><b>Verified candidate {_e(c['capability_id'])}</b>"
                     + (f": {_e(mech.get('distribution'))} {_e(mech.get('version'))}, license {_e(mech.get('license'))}, "
                        f"{_e(source)}; qualified on {_e(q.get('cases'))} frozen cases with {_e(q.get('failures'))} "
                        f"failures; {_e(mech.get('competence'))}" if mech else ""))
    if r.get("resource"):
        parts.append("<br><span class=muted>Authority needed: "
                     + _e("; ".join(f"{k}: {v}" for k, v in r["authority_requested"].items())) + "</span>")
    return "".join(parts)


def _attachable(r: dict) -> list[dict]:
    """Verified candidates a capability ask names; only these can be attached from this page."""
    if r.get("kind") != "CAPABILITY_ATTACH":
        return []
    return [c for c in ((r.get("evidence") or {}).get("registered") or []) if c.get("state") == "VERIFIED"]


def _form(console: Console, action: str, fields: dict, label: str, *, cls: str = "", disabled=False,
          confirm: str | None = None) -> str:
    hidden = "".join(f"<input type=hidden name='{_e(k)}' value='{_e(v)}'>" for k, v in fields.items())
    onsubmit = f" onsubmit=\"return confirm('{_e(confirm)}')\"" if confirm else ""
    return (f"<form class=inline method=post action='{_e(action)}'{onsubmit}><input type=hidden name=csrf "
            f"value='{_e(console.csrf)}'>{hidden}<button class='{cls}'{' disabled' if disabled else ''}>"
            f"{_e(label)}</button></form>")




def owned_pages(console: Console) -> list[dict]:
    """Pages must be bound to successful canonical receipts, not filesystem presence."""
    pages = {}
    with observe(console.home, actor="spiffe://uniimente.internal/greg/owned-reader") as journal:
        ledger = journal.ledger
        ok, _ = ledger.verify_chain()
        if not ok:
            return []
        witnesses = {r.payload["witness_id"]: r.payload["grant_id"] for r in ledger.by_type("witness")
                     if r.payload.get("action_class") == "greg.foundry.apply"
                     and r.payload.get("capability") == "foundry.apply"}
        dispatched = {(r.payload.get("witness_id"), r.payload.get("grant_id"))
                      for r in ledger.by_type("grant_dispatch")}
        for event in journal.replay("mission.action"):
            p = event.payload
            if p.get("status") != "DONE" or p.get("capability") != "foundry.apply":
                continue
            receipt = ledger.find(p.get("receipt"))
            if receipt is None:
                continue
            rp = receipt.payload
            wid, gid = rp.get("witness_id"), rp.get("grant_id")
            if not gid or witnesses.get(wid) != gid or (wid, gid) not in dispatched:
                continue
            result = rp.get("result", {})
            output = result.get("output") or {}
            if result.get("result_class") != "positive" or not isinstance(output, dict):
                continue
            page = output.get("result") if output.get("system") == 31 else (
                (output.get("result") or {}).get("portal") if output.get("system") == 49 else None)
            if isinstance(page, dict) and page.get("kind") == "owned-page":
                item = {k: page.get(k) for k in ("name", "version", "address", "version_address", "title")}
                item["mission_id"] = p["mission_id"]
                pages[(p["mission_id"], item["name"], item["version"])] = item
    return list(pages.values())


def render_owned_index(console: Console) -> bytes:
    links = []
    for page in owned_pages(console):
        url = "/owned/" + quote(page["mission_id"], safe="") + "/" + quote(page["name"], safe="")
        links.append(f"<li><a href='{url}?version={page['version']}'>{_e(page['title'])}</a> "
                     f"(version {_e(page['version'])})</li>")
    return _page("Owned content", "<h1>Owned content</h1><p>Private pages produced by GREG. "
                 "Public deployment requires its own authority.</p><ul>" + "".join(links) +
                 "</ul><p><a href='/'>GREG</a></p>")


def render_owned_page(console: Console, mission_id: str, name: str, version: int | None) -> bytes:
    from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
    from greg import foundry_bridge
    approved = [p for p in owned_pages(console) if p["mission_id"] == mission_id and p["name"] == name
                and (version is None or p["version"] == version)]
    if not approved:
        raise FileNotFoundError("no canonical owned-page receipt")
    wanted = max(approved, key=lambda p: p["version"])
    root = (console.layout.workspace / mission_id.replace(":", "_")).resolve()
    if console.layout.workspace.resolve() not in root.parents:
        raise FileNotFoundError("owned mission outside workspace")
    ctx = InvocationContext(root, (root,), SecretBroker(console.layout.secrets), BUILTINS["foundry.query"][0])
    try:
        output = foundry_bridge.query({"system": 31, "op": "retrieve", "args": {
            "name": name, "version": wanted["version"]}}, ctx)["result"]
    except CapabilityError as exc:
        raise FileNotFoundError("owned content failed integrity checks") from exc
    if (output["address"], output["version_address"]) != (wanted["address"], wanted["version_address"]):
        raise FileNotFoundError("owned content lacks a matching canonical receipt")
    return output["html"].encode()


def home_parts(console: Console) -> dict:
    """The classic page's sections by name; Mission Control reuses the actionable ones."""
    parts = {}

    def add(name, html_text):
        parts[name] = parts.get(name, "") + html_text
    snap = console.snapshot()
    st = snap["status"]
    heartbeat = st.get("background") or {}
    age = None
    if heartbeat.get("at"):
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat["at"].replace("Z", "+00:00"))).total_seconds()
    alive = heartbeat.get("state") in ("RUNNING", "PAUSED") and age is not None and age < 180
    body_state = (f"<span class=ok>{_e(heartbeat['state'])}</span> (pid {_e(heartbeat.get('pid'))}, {int(age)}s ago)"
                  if alive else f"<span class=warn>{_e(heartbeat.get('state', 'NOT RUNNING'))}</span>")
    signer = ("<span class=ok>founder key unlocked in this console</span>" if console.key is not None
              else "<span class=warn>read-only (start with --key to sign)</span>")
    can = console.key is not None
    add("header", f"<h1>GREG</h1><p class=muted>Body {_e(st['body_id'])} · {body_state} · {signer} · "
           f"chain {'verified' if st['security']['chain_verified'] else '<b class=warn>FAILED</b>'}</p>")
    for message in console.flash[-3:]:
        add("flash", f"<section class=ok>{_e(message)}</section>")
    console.flash.clear()
    vepmc = snap["vepmc"]
    add("stats", "<section><div class=grid>"
               f"<div class=stat><b>{vepmc['VEPMC']}</b>verified persistent closures</div>"
               f"<div class=stat><b>{len(snap['missions'])}</b>missions</div>"
               f"<div class=stat><b>{len(st['decisions_required'])}</b>decisions waiting</div>"
               f"<div class=stat><b>{len(snap['deliveries'])}</b>recent deliveries</div></div></section>")
    add("ask", "<section><h2>Ask GREG</h2><form method=post action=/ask><input type=hidden name=csrf "
               f"value='{_e(console.csrf)}'><textarea name=text rows=3 maxlength=4000 placeholder='For example: "
               "Every morning tell me which of my pull requests are failing checks and what is stale.'></textarea>"
               "<p><button>Propose a mission</button> <span class=muted>Nothing runs until you review and sign."
               "</span></p></form></section>")
    if st["decisions_required"]:
        rows = []
        for r in st["decisions_required"]:
            actions = (_form(console, "/decide", {"request_id": r["request_id"], "answer": "approve"}, "Approve",
                             disabled=not can) + " " +
                       _form(console, "/decide", {"request_id": r["request_id"], "answer": "reject"}, "Reject",
                             cls="secondary", disabled=not can)) if r["kind"] != "RECONCILIATION" else (
                       _form(console, "/decide", {"request_id": r["request_id"], "answer": "reconcile_executed"},
                             "It happened", disabled=not can) + " " +
                       _form(console, "/decide", {"request_id": r["request_id"], "answer": "reconcile_not_executed"},
                             "It did not happen", cls="secondary", disabled=not can))
            actions += "".join(" " + _form(console, "/attach", {"request_id": r["request_id"],
                                                                "capability_id": c["capability_id"]},
                                           f"Attach {c['capability_id']}", disabled=not can,
                                           confirm=f"Sign CAPABILITY_ATTACH for {c['capability_id']}?")
                               for c in _attachable(r))
            rows.append(f"<tr><td><span class=pill>{_e(r['kind'])}</span></td><td>{_e(r['why_now'])}<br>"
                        f"<span class=muted>{_e(r['recommendation'])}</span>{_ask_details(r)}</td>"
                        f"<td>{actions}</td></tr>")
        add("decisions", "<section><h2>Decisions waiting for you</h2><table>" + "".join(rows) + "</table></section>")
    closures = [r for r in vepmc["missions"]]
    if closures:
        rows = []
        for r in closures:
            accept = ("" if r["founder_accepted"] else
                      _form(console, "/accept", {"event_id": r["closure_event_id"]}, "Accept result", disabled=not can))
            rows.append(f"<tr><td>{_e(r['mission_id'])}</td><td>{'counts' if r['counts'] else 'missing: ' + _e(', '.join(r['missing']))}"
                        f"</td><td>{accept}</td></tr>")
        add("closures", "<section><h2>Closures (VEPMC)</h2><table>" + "".join(rows) + "</table>"
                   "<p class=muted>A closure counts only when every condition holds, including your acceptance "
                   "and a run on the body you designated as your first body.</p></section>")
    if snap["missions"]:
        rows = "".join(
            f"<tr><td>{_e(m['mission_id'])}<br><span class=muted>{_e(m['intended_effect'])}</span></td>"
            f"<td>{_e(m['status'])}{' (paused)' if m['paused'] else ''}</td>"
            f"<td>{_e((m['blocker'] or {}).get('why', '')) if m['blocker'] else _e(m['next_observe_at'] or '')}</td>"
            f"<td>{m['actions_done']}</td></tr>" for m in snap["missions"])
        add("missions", "<section><h2>Missions</h2><table><tr><th>Mission</th><th>State</th><th>Blocker / next look"
                   "</th><th>Actions</th></tr>" + rows + "</table></section>")
    cognitive = snap['status'].get('cognition', {}).get('receipts', [])
    if cognitive:
        rows = []
        for r in cognitive:
            methods = ', '.join(c['kind'] for c in r['claims'])
            explanation = '; '.join(c['selection_rationale'] for c in r['claims'])
            rows.append(f"<tr><td>{_e(r['problem_id'])}<br>{_e(methods)}</td>"
                        f"<td>{'Checked conditional result' if r['answered'] else 'Needs evidence or review'}<br>"
                        f"{_e(r['next_step'])}<details><summary>Evidence and limits</summary>"
                        f"<p>{_e(explanation)}</p><pre>{_e(json.dumps(r['claims'], indent=2))}</pre>"
                        f"<p>{_e(r['cost_limits'])}; {_e(r['elapsed_ms'])} ms</p></details></td></tr>")
        add("reasoning", '<section><h2>Checked reasoning</h2><p>These results check computation and source binding. '
                   'Real-world assumptions and consequential decisions still need review.</p><table>' + ''.join(rows) + '</table></section>')
    if snap.get("cognitive"):
        cards = []
        for answer in snap["cognitive"]:
            cards.append("<section><h2>" + _e(answer["problem_id"]) + "</h2><p>Method: " + _e(answer["method"]) +
                         " · Result: " + _e(answer["outcome_state"]) + "</p><p>" + _e(answer["selection_rationale"]) +
                         "</p><pre>" + _e(json.dumps(answer["output"], ensure_ascii=False)) + "</pre><p>Evidence: " +
                         _e(answer["proof_class"]) + " · Receipt: " + _e(answer["receipt_id"]) + "</p><p>Uncertainty: " +
                         _e(answer["uncertainty"]) + "</p><p>Time: " + _e(answer["latency"]) + " seconds · Cost: $" +
                         _e(answer["money_cost"]) + "</p><p>Next permitted step: " +
                         _e('; '.join(answer["missing_information"] or []) or "Review this scoped result; any effect still requires the existing authority path.") + "</p></section>")
        add("cognitive", "".join(cards))
    if snap["deliveries"]:
        links = "".join(f"<li><a href='/delivery/{quote(n)}'>{_e(n)}</a></li>" for n in snap["deliveries"])
        add("deliveries", f"<section><h2>Deliveries</h2><ul>{links}</ul></section>")
    add("history", "<section><h2>Recent history</h2><table>" + "".join(
        f"<tr><td class=muted>{_e(r['at'][11:19])}</td><td>{_e(r['type'])}</td><td>{_e(r['mission_id'] or '')}</td>"
        f"<td>{_e(r['summary'])}</td></tr>" for r in snap["recent"]) + "</table>"
        "<p><a href=/morning>Morning report</a> · <a href=/api/state>JSON state</a> · <a href=/owned>Owned content</a></p></section>")
    add("stop", "<section><h2>Stop</h2><p class=muted>Shutdown always wins. A signed stop is recorded as your "
               "command; the local stop file works even without a key.</p>" +
               _form(console, "/stop", {"mode": "signed"}, "Stop GREG (signed)", cls="danger", disabled=not can,
                     confirm="Stop the GREG body?") + " " +
               _form(console, "/stop", {"mode": "local"}, "Stop GREG (local stop file)", cls="danger",
                     confirm="Write the local STOP file?") + "</section>")
    return parts


def render_home(console: Console) -> bytes:
    """The classic page, kept whole as the baseline Mission Control is measured against."""
    return _page("GREG", "".join(home_parts(console).values()), refresh=True)


def render_mission_control(console: Console, view: str = "overview", query: str = "") -> bytes:
    """The founder's first page: five questions answered from retained state, with the real controls."""
    from greg import mission_control
    if view not in dict(mission_control.VIEWS):
        raise FileNotFoundError(view)
    parts = home_parts(console)
    parts["_query"] = query[:200]
    body = parts.get("flash", "") + mission_control.render_view(console, view, parts)
    body += "<p class=muted><a href=/classic>Classic page</a> · <a href=/morning>Morning report</a> · <a href=/api/mc>JSON</a></p>"
    return _page("GREG Mission Control", f"<style>{mission_control.STYLE_EXTRA}</style>" + body,
                 refresh=view == "overview")


def render_first_mission(console: Console, name: str) -> bytes:
    folder = (console.deliver_root() / "first-mission").resolve()
    path = (folder / name).resolve()
    if path.parent != folder or not path.is_file() or path.suffix != ".md":
        raise FileNotFoundError(name)
    return _page(name, f"<p><a href=/>Mission Control</a></p><section><pre>{_e(path.read_text(errors='replace'))}</pre></section>")


def render_proposal(console: Console, pid: str) -> bytes:
    entry = console.proposals.get(pid)
    if entry is None:
        return _page("GREG proposal", "<section>That proposal is gone (signed, discarded or expired). "
                     "<a href=/>Back</a></section>")
    p = entry["proposal"]
    out = [f"<h1>Proposal</h1><section><p class=muted>You asked:</p><p>{_e(entry['text'])}</p>"
           f"<p class=muted>Route: {_e(p.get('origin'))} · status <b>{_e(p['status'])}</b></p></section>"]
    if p["status"] != "PROPOSED":
        detail = p.get("why") or "; ".join(p.get("questions", []))
        problems = "".join(f"<li>{_e(x)}</li>" for x in p.get("problems", []))
        out.append(f"<section><p>{_e(detail)}</p><ul>{problems}</ul><a href=/>Back</a></section>")
        from greg.discover import discover
        found = discover(entry["text"], limit=6)
        if found:
            out.append("<section><h2>Machinery your words name</h2><p class=muted>GREG could not draft a mission from "
                       "this sentence. These installed paths, capabilities and Foundry systems match its words; "
                       "lexical matching, not a feasibility judgment.</p><ul>" + "".join(
                           f"<li>{_e(r['kind'])} <code>{_e(r['id'])}</code>: {_e(r['title'])} "
                           f"<span class=muted>({_e(r['state'] or 'see the capability map')})</span></li>" for r in found)
                       + f"</ul><p><a href='/mc/organs?q={quote(entry['text'][:200])}'>Explore in Mission Control</a></p></section>")
        return _page("GREG proposal", "".join(out))
    spec = p["spec"]
    summary = planner.authority_summary(spec, console.context().capabilities)
    out.append(f"<section><h2>{_e(spec['intended_effect'])}</h2><p class=muted>{_e(spec['mission_id'])} · "
               f"{_e(summary['closure'])}</p><ul>" + "".join(f"<li>{_e(n)}</li>" for n in p.get("notes", []))
               + "</ul></section>")
    out.append("<section><h2>What signing lets GREG do</h2><table>"
               f"<tr><th>Without asking</th><td>{'<br>'.join(_e(x) for x in summary['may_do_without_asking'])}</td></tr>"
               f"<tr><th>Must ask you first</th><td>{'<br>'.join(_e(x) for x in summary['must_ask_you_first']) or '—'}</td></tr>"
               f"<tr><th>Budget</th><td>${_e(summary['budget_usd'])}</td></tr>"
               f"<tr><th>Mandate expires</th><td>{_e(summary['expires'])}</td></tr>"
               f"<tr><th>Never</th><td>{'<br>'.join(_e(x) for x in summary['never'])}</td></tr></table></section>")
    checks = "".join(f"<li><b>{_e(c['check_id'])}</b>: {_e(c['description'])} "
                     f"<span class=muted>({_e(c['sensor'].get('capability') or c['sensor'].get('function'))} "
                     f"{_e(c['predicate'])})</span></li>" for c in spec["success_checks"])
    out.append(f"<section><h2>How GREG will know it is done</h2><ul>{checks}</ul>"
               f"<details><summary>Full mission JSON (this is exactly what you sign)</summary>"
               f"<pre>{_e(json.dumps(spec, indent=1))}</pre></details></section>")
    out.append("<section>" + _form(console, "/sign", {"proposal": pid}, "Sign and send to GREG",
                                   disabled=console.key is None) + " " +
               _form(console, "/discard", {"proposal": pid}, "Discard", cls="secondary") + "</section>")
    return _page("GREG proposal", "".join(out))


def render_delivery(console: Console, name: str) -> bytes:
    folder = (console.deliver_root() / "briefs").resolve()
    path = (folder / name).resolve()
    if path.parent != folder or not path.is_file() or path.suffix != ".md":
        raise FileNotFoundError(name)
    return _page(name, f"<p><a href=/>Back</a></p><section><pre>{_e(path.read_text(errors='replace'))}</pre></section>")


def render_morning(console: Console) -> bytes:
    report = morning_projection(console.home)
    keep = {k: report[k] for k in ("q1_goals_worked_on", "q3_what_i_did", "q6_what_failed", "q7_surprises",
                                   "q12_decisions_required", "q13_tonight", "metrics", "claims_not_made")}
    return _page("GREG morning", "<p><a href=/>Back</a></p><section><h2>Morning report</h2><pre>"
                 + _e(json.dumps(keep, indent=1, default=str)) + "</pre></section>")


# -- HTTP -----------------------------------------------------------------------------------

def make_handler(console: Console):
    class Handler(BaseHTTPRequestHandler):
        server_version = "GREG-console/1"

        def log_message(self, *args):  # no request logging to stderr (the body keeps the evidence)
            pass

        def _host_ok(self) -> bool:
            port = self.server.server_address[1]
            return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _owner_authenticated(self) -> bool:
            try:
                cookies = SimpleCookie(self.headers.get("Cookie", ""))
            except CookieError:
                return False
            value = cookies.get(OWNER_COOKIE)
            return value is not None and secrets.compare_digest(value.value.encode(), console._session.encode())

        def _send(self, code: int, data: bytes, ctype="text/html; charset=utf-8", location=None,
                  *, owner=False, public_content=False, establish_session=False):
            if owner and ctype.startswith("text/html"):
                # Keep every private link and form under the owner path the session cookie is scoped to.
                text = data.decode("utf-8")
                text = re.sub(r"\b(href|action)=(['\"]?)/(?!/)",
                              lambda match: match.group(1) + "=" + match.group(2) + console.owner_path, text)
                data = text.encode("utf-8")
            if owner and location and location.startswith("/") and not location.startswith(console.owner_path):
                location = console.owner_path + location.lstrip("/")
            self.send_response(code)
            if location:
                self.send_header("Location", location)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            policy = ("sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
                      "script-src 'none'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'"
                      if public_content else
                      "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                      "form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Content-Security-Policy", policy)
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            if establish_session:
                self.send_header("Set-Cookie", f"{OWNER_COOKIE}={console._session}; "
                                 f"Path={console.owner_path}; HttpOnly; SameSite=Strict")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, b"loopback host required")
            parsed = urlsplit(self.path)
            path = parsed.path
            owner = path.startswith(console.owner_path)
            if owner:
                path = "/" + path[len(console.owner_path):]
                supplied = parse_qs(parsed.query).get("access", [])
                if path == "/" and len(supplied) == 1:
                    if console.bootstrap(supplied[0]):
                        return self._send(303, b"", location=console.owner_path, establish_session=True)
                    if self._owner_authenticated():
                        return self._send(303, b"", location=console.owner_path)
                if not self._owner_authenticated():
                    return self._send(403, PRIVATE, "text/plain; charset=utf-8")
            elif path != "/owned" and not path.startswith("/owned/"):
                return self._send(403, PRIVATE, "text/plain; charset=utf-8")
            try:
                if path == "/":
                    return self._send(200, render_mission_control(console), owner=True)
                if path == "/classic":
                    return self._send(200, render_home(console), owner=True)
                if path.startswith("/mc/"):
                    q = parse_qs(parsed.query).get("q", [""])[0]
                    return self._send(200, render_mission_control(console, path.split("/", 2)[2], q), owner=True)
                if path == "/api/mc":
                    from greg.mission_control import projection
                    return self._send(200, json.dumps(projection(console), default=str).encode(), "application/json")
                if path.startswith("/first-mission/"):
                    from urllib.parse import unquote
                    return self._send(200, render_first_mission(console, unquote(path.split("/", 2)[2])), owner=True)
                if path.startswith("/proposal/"):
                    return self._send(200, render_proposal(console, path.split("/", 2)[2]), owner=True)
                if path.startswith("/delivery/"):
                    from urllib.parse import unquote
                    return self._send(200, render_delivery(console, unquote(path.split("/", 2)[2])), owner=True)
                if path == "/owned":
                    return self._send(200, render_owned_index(console), owner=owner, public_content=True)
                if path.startswith("/owned/"):
                    from urllib.parse import unquote
                    parts = path.split("/")
                    if len(parts) != 4:
                        return self._send(404, b"not found")
                    query = parse_qs(urlsplit(self.path).query)
                    try:
                        version = int(query["version"][0]) if "version" in query else None
                    except ValueError:
                        return self._send(400, b"invalid page version")
                    return self._send(200, render_owned_page(console, unquote(parts[2]), unquote(parts[3]), version),
                                      owner=owner, public_content=True)
                if path == "/morning":
                    return self._send(200, render_morning(console), owner=True)
                if path == "/api/state":
                    return self._send(200, json.dumps(console.snapshot(), default=str).encode(), "application/json")
            except FileNotFoundError:
                return self._send(404, b"not found")
            return self._send(404, b"not found")

        def do_POST(self):
            if not self._host_ok():
                return self._send(403, b"loopback host required")
            parsed = urlsplit(self.path)
            if not parsed.path.startswith(console.owner_path) or not self._owner_authenticated():
                return self._send(403, PRIVATE, "text/plain; charset=utf-8")
            origin = self.headers.get("Origin")
            port = self.server.server_address[1]
            if origin not in (None, "null", f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
                return self._send(403, b"cross-origin request refused")
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BODY:
                return self._send(413, b"bounded form required")
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode("utf-8", "replace"),
                                                 keep_blank_values=True).items()}
            if not secrets.compare_digest(form.get("csrf", ""), console.csrf):
                return self._send(403, b"invalid form token; reload the page")
            path = "/" + parsed.path[len(console.owner_path):]
            try:
                if path == "/ask":
                    return self._send(303, b"", location="/proposal/" + console.ask(form.get("text", "")[:4000]),
                                      owner=True)
                if path == "/venture-rehearsal":
                    try:
                        return self._send(303, b"", location="/proposal/" + console.venture_rehearsal(), owner=True)
                    except FileNotFoundError as exc:
                        return self._send(409, str(exc).encode())
                if path == "/first-mission":
                    return self._send(303, b"", location="/proposal/" + console.first_mission(form.get("effort_budget", "8")),
                                      owner=True)
                if path == "/sign":
                    target = console.sign_proposal(form.get("proposal", ""))
                    console.flash.append(f"Signed and sent: {target.name}. You can close this window.")
                elif path == "/discard":
                    console.proposals.pop(form.get("proposal", ""), None)
                elif path == "/decide":
                    target = console.sign("DECISION", {"request_id": form["request_id"], "answer": form["answer"],
                                                       "reason": "decided in the GREG console"})
                    console.flash.append(f"Decision signed: {target.name}")
                elif path == "/attach":
                    target = console.attach(form.get("request_id", ""), form.get("capability_id", ""))
                    console.flash.append(f"Attach signed: {target.name}")
                elif path == "/accept":
                    console.sign("CRITIQUE", {"target_event_id": form["event_id"], "verdict": "accept",
                                              "evidence_type": "founder_judgment",
                                              "text": "accepted in the GREG console after review"})
                    console.flash.append("Acceptance signed.")
                elif path == "/body":
                    kind = {"pause": "BODY_PAUSE", "resume": "BODY_RESUME"}[form["mode"]]
                    console.sign(kind, {})
                    console.flash.append(f"Signed {kind.replace('_', ' ').lower()} sent.")
                elif path == "/lifecycle":
                    state = {"pause": "PAUSED", "resume": "ACTIVE", "revoke": "ABANDONED"}[form["action"]]
                    console.sign("LIFECYCLE", {"mission_id": form["mission_id"], "state": state,
                                               "reason": "founder decision in Mission Control"})
                    console.flash.append(f"Signed: mission {form['mission_id']} -> {state}.")
                elif path == "/stop":
                    if form.get("mode") == "local":
                        console.layout.stop_file.touch()
                        console.flash.append("STOP file written; the body exits at its next check.")
                    else:
                        console.sign("BODY_STOP", {})
                        console.flash.append("Signed stop sent.")
                else:
                    return self._send(404, b"not found")
            except PermissionError as exc:
                return self._send(403, str(exc).encode())
            except (KeyError, ValueError) as exc:
                return self._send(400, f"{type(exc).__name__}: {exc}".encode()[:500])
            return self._send(303, b"", location="/", owner=True)
    return Handler


def serve(console: Console, *, port: int = 8766, ready=None) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(console))
    if ready is not None:
        ready(server)
    return server
