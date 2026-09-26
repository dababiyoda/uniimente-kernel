"""GREG console: the one founder-facing interface, on this computer.

    python -m greg console --key ~/.greg-founder.pem        (http://127.0.0.1:8766; the phone channel keeps 8765)

Alfonso says what he wants in plain words, reviews what GREG proposes and exactly
what signing it would let GREG do, signs, and closes the window. The body keeps
working under its supervisor. The console is not the body and not a second Kernel:

* it reads retained history only through the read-only observer (never the writer);
* its only write is a founder-signed command file dropped into the body inbox;
* the founder key is decrypted once at start and held in this process's memory only;
  without a key the console is read-only;
* it binds to 127.0.0.1, refuses any other Host header (DNS rebinding), requires a
  per-process CSRF token and same-origin POSTs, and caps request sizes.

Mechanism lineage: #112 egregore/local_console.py (loopback page, Host check, CSRF,
head-bound review), now driving the canonical #113 body with real Ed25519 signatures
instead of synthetic development authority.
"""
from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import parse_qs, quote, urlsplit

from greg import metrics, planner
from greg.body import Layout, morning_projection, observe, send_signed, status

MAX_BODY = 16 * 1024
STYLE = """
:root{--bg:#f5f6f4;--fg:#18242b;--muted:#5d6b73;--card:#fff;--line:#d5dcd9;--accent:#1f5f8b;--warn:#9a3b12;--ok:#2f6b3a}
@media (prefers-color-scheme:dark){:root{--bg:#121719;--fg:#e4e9eb;--muted:#9aa7ad;--card:#1b2226;--line:#2d383d;
--accent:#7ab7e0;--warn:#f0a07a;--ok:#8fd19e}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--fg)}
main{max-width:1000px;margin:0 auto;padding:16px}h1{font-size:22px;margin:4px 0 12px}h2{font-size:17px;margin:0 0 8px}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:12px 0}
.muted{color:var(--muted)}.warn{color:var(--warn)}.ok{color:var(--ok)}table{border-collapse:collapse;width:100%}
td,th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
textarea,input{width:100%;font:inherit;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
button{font:inherit;padding:7px 12px;border-radius:6px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer}
button.secondary{background:transparent;color:var(--accent)}button.danger{border-color:var(--warn);background:var(--warn)}
button[disabled]{opacity:.45;cursor:not-allowed}form.inline{display:inline}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;border:1px solid var(--line);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.stat b{display:block;font-size:20px}
@media (max-width:600px){td,th{padding:4px}main{padding:10px}}
"""


def _e(value) -> str:
    return html.escape(str(value), quote=True)


class Console:
    """State held by one console process: the unlocked key, CSRF token, pending proposals."""

    def __init__(self, home: str | Path, *, key=None, transport=None, planner_context=None):
        self.home = Path(home).expanduser().resolve()
        self.layout = Layout(self.home)
        self.key = key
        self.transport = transport
        self.csrf = secrets.token_urlsafe(32)
        self.proposals: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.planner_context = planner_context
        self.flash: list[str] = []

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
            vepmc = metrics.vepmc(journal)
            recent = [{"type": e.type[len("greg."):], "at": e.occurred_at,
                       "mission_id": e.payload.get("mission_id"), "summary": _summary(e)}
                      for e in journal.replay()[-25:]][::-1]
        deliveries = []
        folder = self.deliver_root() / "briefs"
        if folder.is_dir():
            deliveries = [p.name for p in sorted(folder.glob("*.md"), key=lambda p: p.stat().st_mtime,
                                                   reverse=True)[:10]]
        return {"status": state, "missions": missions, "vepmc": vepmc, "recent": recent, "deliveries": deliveries}

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

    def ask(self, text: str) -> str:
        proposal = planner.propose(text, self.context(), transport=self.transport)
        pid = secrets.token_urlsafe(9)
        with self.lock:
            self.proposals[pid] = {"text": text, "proposal": proposal, "at": time.time()}
            for old in sorted(self.proposals, key=lambda k: self.proposals[k]["at"])[:-20]:
                self.proposals.pop(old)
        return pid

    def sign_proposal(self, pid: str) -> Path:
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


def _form(console: Console, action: str, fields: dict, label: str, *, cls: str = "", disabled=False,
          confirm: str | None = None) -> str:
    hidden = "".join(f"<input type=hidden name='{_e(k)}' value='{_e(v)}'>" for k, v in fields.items())
    onsubmit = f" onsubmit=\"return confirm('{_e(confirm)}')\"" if confirm else ""
    return (f"<form class=inline method=post action='{_e(action)}'{onsubmit}><input type=hidden name=csrf "
            f"value='{_e(console.csrf)}'>{hidden}<button class='{cls}'{' disabled' if disabled else ''}>"
            f"{_e(label)}</button></form>")


def render_home(console: Console) -> bytes:
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
    out = [f"<h1>GREG</h1><p class=muted>Body {_e(st['body_id'])} · {body_state} · {signer} · "
           f"chain {'verified' if st['security']['chain_verified'] else '<b class=warn>FAILED</b>'}</p>"]
    for message in console.flash[-3:]:
        out.append(f"<section class=ok>{_e(message)}</section>")
    console.flash.clear()
    vepmc = snap["vepmc"]
    out.append("<section><div class=grid>"
               f"<div class=stat><b>{vepmc['VEPMC']}</b>verified persistent closures</div>"
               f"<div class=stat><b>{len(snap['missions'])}</b>missions</div>"
               f"<div class=stat><b>{len(st['decisions_required'])}</b>decisions waiting</div>"
               f"<div class=stat><b>{len(snap['deliveries'])}</b>recent deliveries</div></div></section>")
    out.append("<section><h2>Ask GREG</h2><form method=post action=/ask><input type=hidden name=csrf "
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
            rows.append(f"<tr><td><span class=pill>{_e(r['kind'])}</span></td><td>{_e(r['why_now'])}<br>"
                        f"<span class=muted>{_e(r['recommendation'])}</span></td><td>{actions}</td></tr>")
        out.append("<section><h2>Decisions waiting for you</h2><table>" + "".join(rows) + "</table></section>")
    closures = [r for r in vepmc["missions"]]
    if closures:
        rows = []
        for r in closures:
            accept = ("" if r["founder_accepted"] else
                      _form(console, "/accept", {"event_id": r["closure_event_id"]}, "Accept result", disabled=not can))
            rows.append(f"<tr><td>{_e(r['mission_id'])}</td><td>{'counts' if r['counts'] else 'missing: ' + _e(', '.join(r['missing']))}"
                        f"</td><td>{accept}</td></tr>")
        out.append("<section><h2>Closures (VEPMC)</h2><table>" + "".join(rows) + "</table>"
                   "<p class=muted>A closure counts only when every condition holds, including your acceptance "
                   "and a Mac body.</p></section>")
    if snap["missions"]:
        rows = "".join(
            f"<tr><td>{_e(m['mission_id'])}<br><span class=muted>{_e(m['intended_effect'])}</span></td>"
            f"<td>{_e(m['status'])}{' (paused)' if m['paused'] else ''}</td>"
            f"<td>{_e((m['blocker'] or {}).get('why', '')) if m['blocker'] else _e(m['next_observe_at'] or '')}</td>"
            f"<td>{m['actions_done']}</td></tr>" for m in snap["missions"])
        out.append("<section><h2>Missions</h2><table><tr><th>Mission</th><th>State</th><th>Blocker / next look"
                   "</th><th>Actions</th></tr>" + rows + "</table></section>")
    if snap["deliveries"]:
        links = "".join(f"<li><a href='/delivery/{quote(n)}'>{_e(n)}</a></li>" for n in snap["deliveries"])
        out.append(f"<section><h2>Deliveries</h2><ul>{links}</ul></section>")
    out.append("<section><h2>Recent history</h2><table>" + "".join(
        f"<tr><td class=muted>{_e(r['at'][11:19])}</td><td>{_e(r['type'])}</td><td>{_e(r['mission_id'] or '')}</td>"
        f"<td>{_e(r['summary'])}</td></tr>" for r in snap["recent"]) + "</table>"
        "<p><a href=/morning>Morning report</a> · <a href=/api/state>JSON state</a></p></section>")
    out.append("<section><h2>Stop</h2><p class=muted>Shutdown always wins. A signed stop is recorded as your "
               "command; the local stop file works even without a key.</p>" +
               _form(console, "/stop", {"mode": "signed"}, "Stop GREG (signed)", cls="danger", disabled=not can,
                     confirm="Stop the GREG body?") + " " +
               _form(console, "/stop", {"mode": "local"}, "Stop GREG (local stop file)", cls="danger",
                     confirm="Write the local STOP file?") + "</section>")
    return _page("GREG", "".join(out), refresh=True)


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

        def _send(self, code: int, data: bytes, ctype="text/html; charset=utf-8", location=None):
            self.send_response(code)
            if location:
                self.send_header("Location", location)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; "
                             "script-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, b"loopback host required")
            path = urlsplit(self.path).path
            try:
                if path == "/":
                    return self._send(200, render_home(console))
                if path.startswith("/proposal/"):
                    return self._send(200, render_proposal(console, path.split("/", 2)[2]))
                if path.startswith("/delivery/"):
                    from urllib.parse import unquote
                    return self._send(200, render_delivery(console, unquote(path.split("/", 2)[2])))
                if path == "/morning":
                    return self._send(200, render_morning(console))
                if path == "/api/state":
                    return self._send(200, json.dumps(console.snapshot(), default=str).encode(), "application/json")
            except FileNotFoundError:
                return self._send(404, b"not found")
            return self._send(404, b"not found")

        def do_POST(self):
            if not self._host_ok():
                return self._send(403, b"loopback host required")
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
            path = urlsplit(self.path).path
            try:
                if path == "/ask":
                    return self._send(303, b"", location="/proposal/" + console.ask(form.get("text", "")[:4000]))
                if path == "/sign":
                    target = console.sign_proposal(form.get("proposal", ""))
                    console.flash.append(f"Signed and sent: {target.name}. You can close this window.")
                elif path == "/discard":
                    console.proposals.pop(form.get("proposal", ""), None)
                elif path == "/decide":
                    target = console.sign("DECISION", {"request_id": form["request_id"], "answer": form["answer"],
                                                       "reason": "decided in the GREG console"})
                    console.flash.append(f"Decision signed: {target.name}")
                elif path == "/accept":
                    console.sign("CRITIQUE", {"target_event_id": form["event_id"], "verdict": "accept",
                                              "evidence_type": "founder_judgment",
                                              "text": "accepted in the GREG console after review"})
                    console.flash.append("Acceptance signed.")
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
            return self._send(303, b"", location="/")
    return Handler


def serve(console: Console, *, port: int = 8766, ready=None) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(console))
    if ready is not None:
        ready(server)
    return server
