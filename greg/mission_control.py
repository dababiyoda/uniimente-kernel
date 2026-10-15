"""Mission Control: the founder's first view of GREG as one working institution.

It is not a second interface or a dashboard of decorative cards. Every number and row on it is a
projection of state GREG already keeps, read through the console's read-only observer:

  body status (``greg.body.status``)       capabilities with attachment state and health, security,
                                           presence, compute, decisions, developmental position,
                                           cognition receipts, the VEPMC conditions
  the mission book (``MissionBook``)       what GREG is doing, under which light cone and budget
  the morning projection                   Night Shift / Morning Tribunal (thirteen questions)
  the Foundry completion contract          which of the 55 systems are runnable, partial, or have
                                           registered alternates
  the genome admission evidence            the Mind's measured verdicts, not a feature list
  worker providers and the browser         whether GREG's hands can actually run on this body

The first page answers five questions (what GREG is, what it can do now, what it is doing, what it can
be commanded to do, what needs Alfonso's authority). Each capability carries one of five truthful
classes: RUNNABLE, NEEDS_FOUNDER_ATTACH, BLOCKED (with the missing dependency), PARTIAL (with its gap)
and SPENDS_MONEY (available, but needs a signed budget). A view with nothing to show says so and names
what would fill it; nothing is invented to fill space.

Writes stay where the console already puts them: founder-signed command files, and the same
review-and-sign page for proposals. Mission Control adds no write path of its own.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

VIEWS = (("overview", "Overview"), ("command", "Command"), ("mind", "Mind"), ("body", "Body"), ("organs", "Organs"),
         ("goals", "Goal Chase"), ("ventures", "Ventures"), ("proof", "Proof & Memory"), ("authority", "Authority"),
         ("night", "Night Shift"))
KERNEL_ROOT = Path(__file__).resolve().parents[1]
ADMISSION = KERNEL_ROOT / "docs/evidence/greg-genome-admission/2026-10-13-v1/results.json"
REALITY = ("PROPOSED", "SIMULATED", "LOCAL-REAL", "EXPERIMENTALLY-VERIFIED", "FOUNDER-DEVICE-VERIFIED", "EXTERNALLY-VERIFIED")


def _e(value) -> str:
    return html.escape(str(value), quote=True)


# -- projection ---------------------------------------------------------------------------------

def classify_capability(c: dict, providers: dict) -> dict:
    """One truthful class per capability, from its own manifest state and health."""
    cid, state, health = c["capability_id"], c.get("state", ""), c.get("health", "")
    if cid == "worker.commission":
        ready = [n for n, ok in providers.items() if ok]
        if not ready:
            return {"class": "BLOCKED", "why": "no worker provider is installed on this body (Claude Code, Codex or Aider)"}
        return {"class": "SPENDS_MONEY", "why": f"providers ready: {', '.join(ready)}; each work order needs a signed budget"}
    if state in ("VERIFIED", "DETACHED", "REGISTERED", "WITHHELD"):
        return {"class": "NEEDS_FOUNDER_ATTACH", "why": f"{state.lower()}: attaching it is your decision"}
    if state == "QUARANTINED":
        return {"class": "BLOCKED", "why": "quarantined after a failure; see Proof & Memory"}
    if health and health != "available":
        return {"class": "BLOCKED", "why": str(health)}
    if c.get("credentials"):
        return {"class": "BLOCKED", "why": "needs credentials: " + ", ".join(map(str, c["credentials"]))}
    if c.get("consequence_class") in ("external_contact", "financial", "irreversible"):
        return {"class": "RUNNABLE", "why": f"{c['consequence_class']}: every use asks you or needs a signed standing mandate"}
    return {"class": "RUNNABLE", "why": "attached and available" + (" (asks before writing)" if c.get("consequence_class") == "internal_write" else "")}


def _providers() -> dict:
    try:
        from greg.workers import PROVIDERS
        return {name: bool(p.available()[0]) for name, p in PROVIDERS.items()}
    except Exception:  # a missing optional dependency is a fact about the body, not a crash of the view
        return {}


def _foundry() -> dict:
    import yaml
    from foundry.systems import ALTERNATES, SYSTEMS
    rows = yaml.safe_load((KERNEL_ROOT / "foundry/completion.yaml").read_text())
    from foundry.arsenal import technology
    systems = []
    for sid in range(1, 56):
        row = rows.get(sid, {})
        systems.append({"id": sid, "name": technology(sid).name, "state": row.get("state", "UNKNOWN"),
                        "module": SYSTEMS.get(sid), "alternates": list(ALTERNATES.get(sid, ())),
                        "gap": (row.get("gap") or "")[:300], "interface": (row.get("interface") or "")[:200]})
    counts = {}
    for s in systems:
        counts[s["state"]] = counts.get(s["state"], 0) + 1
    return {"counts": counts, "systems": systems,
            "note": "COMPLETE is bounded local contract evidence re-derived by re-running each system; never full-machine completion"}


def _mind() -> dict:
    if not ADMISSION.is_file():
        return {"genomes": [], "missing": str(ADMISSION)}
    data = json.loads(ADMISSION.read_text())
    out = []
    for family, g in sorted(data.get("genomes", {}).items()):
        vb = g.get("vs_baseline", {})
        out.append({"family": family, "layer": g.get("layer"), "status": g.get("status"), "intelligence_id": g.get("intelligence_id"),
                    "baseline": g.get("baseline", ""), "wins": vb.get("wins"), "losses": vb.get("losses")})
    counts = {}
    for g in out:
        counts[g["status"]] = counts.get(g["status"], 0) + 1
    return {"genomes": out, "counts": counts, "frozen": data.get("freeze_sha256", "")[:16], "source_commit": data.get("source_commit")}


def cost_rows(actions: list[dict], missions: list[dict], fixtures: list[dict]) -> list[dict]:
    """Per mission, money kept in distinct columns, never netted: the signed budget; what was booked; how much of
    that a provider measured; how much was booked at the signed cap because the true spend was unknown or not
    reported; and fixture amounts that moved no money. Read from the recorded actions, never estimated."""
    rows = {m["mission_id"]: {"mission_id": m["mission_id"], "budget_usd": float(m["cone"].get("budget_usd") or 0),
                              "booked_usd": 0.0, "measured_usd": 0.0, "unknown_at_cap_usd": 0.0,
                              "fixture_cents": 0, "money_moved": False} for m in missions}
    for a in actions:
        row = rows.get(a.get("mission_id"))
        if row is None or a.get("status") != "DONE":
            continue
        cost = float(a.get("cost_usd") or 0.0)
        row["booked_usd"] += cost
        basis = a.get("spend_basis")
        if basis == "provider_reported":
            row["measured_usd"] += float(a.get("provider_reported_usd") or 0.0)
        elif basis and basis.startswith("signed_cap"):
            row["unknown_at_cap_usd"] += cost
    for f in fixtures:
        if f.get("mission_id") in rows:
            rows[f["mission_id"]]["fixture_cents"] += int((f.get("totals") or {}).get("revenue") or 0)
    return [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()} for r in rows.values()]


def _resilience(console) -> dict:
    from greg.body import observe
    from greg import resilience
    try:
        with observe(console.home, actor="spiffe://uniimente.internal/greg/mission-control-resilience") as journal:
            return resilience.summary(journal)
    except Exception as exc:             # a projection failure is shown, never hidden
        return {"error": type(exc).__name__}


def _books(home, mission_id):
    from greg.venture_rehearsal import books
    return books(home, mission_id)


def projection(console) -> dict:
    """Everything Mission Control shows, from retained state only."""
    from greg.body import morning_projection, observe, status
    from greg.missions import MissionBook
    from greg import templates
    st = status(console.home)
    providers = _providers()
    caps = []
    for c in st["capabilities"]:
        k = classify_capability(c, providers)
        caps.append({"capability_id": c["capability_id"], "description": c.get("description", ""),
                     "consequence_class": c.get("consequence_class"), "state": c.get("state"), **k})
    by_class = {}
    for c in caps:
        by_class[c["class"]] = by_class.get(c["class"], 0) + 1
    with observe(console.home, actor="spiffe://uniimente.internal/greg/mission-control") as journal:
        book = MissionBook(journal)
        missions = []
        for mid, m in sorted(book.missions.items()):
            cone = m.spec.get("light_cone", {})
            missions.append({"mission_id": mid, "status": m.status, "paused": m.paused, "blocker": (m.blocker or {}).get("why"),
                             "intended_effect": m.spec.get("intended_effect", ""), "closure": m.spec.get("closure", {}).get("kind"),
                             "actions_done": m.actions_done, "next_observe_at": m.next_observe_at,
                             "cone": {"capabilities": cone.get("capabilities", []), "ceiling": cone.get("max_consequence_class"),
                                      "budget_usd": cone.get("budget_usd"), "horizon": cone.get("horizon")}})
        appraisals = [{"mission_id": e.payload.get("mission_id"), "verdict": e.payload.get("verdict"), "at": e.occurred_at}
                      for e in journal.replay("mission.appraised")][-20:]
        receipts = len(journal.ledger.by_type("receipt")) if hasattr(journal, "ledger") else None
        retained = journal.replay()
        events = len(retained)
        # Per-mission traces are #44's correlation over retained events: every row is a ledger fact.
        from foundry.systems import observability
        from greg import metrics as _metrics
        order = {r.payload.get("event_id"): r.seq for r in journal.ledger.by_type("event")}
        traces = {mid: t["spans"][-200:] for mid, t in observability.correlate(
            [{"type": e.type, "event_id": e.event_id, "payload": e.payload, "seq": order.get(e.event_id, -1),
              "at": e.payload.get("at") or e.occurred_at} for e in retained])["missions"].items()}
        sandbox = _metrics.sandbox_whole_machine(journal)
        quarantined = [e.payload for e in journal.replay("capability.quarantined")][-10:]
        action_rows = [e.payload for e in journal.replay("mission.action")]
        toggles = [e.type for e in journal.replay("body.") if e.type in ("greg.body.paused", "greg.body.resumed")]
        signed_pause = bool(toggles) and toggles[-1] == "greg.body.paused"
    morning = morning_projection(console.home)
    dossiers = []
    folder = console.deliver_root() / "first-mission"
    if folder.is_dir():
        dossiers = [p.name for p in sorted(folder.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]]
    ventures = []
    vfolder = console.deliver_root() / "ventures"
    if vfolder.is_dir():
        ventures = [p.name for p in sorted(vfolder.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]]
    heartbeat = dict(st.get("background") or {})
    if heartbeat.get("at"):                     # a heartbeat older than three minutes is not a running body
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat["at"].replace("Z", "+00:00"))).total_seconds()
        if age >= 180:
            heartbeat["state"] = f"NOT RUNNING (last seen {int(age // 60)} min ago)"
    active = [m for m in missions if m["status"] not in ("ACHIEVED", "ABANDONED", "FAILED", "STOPPED")]
    out = {
        "identity": {"body_id": st["body_id"], "version": st.get("version"), "boots": st.get("boots"),
                     "founder_keys": len(st["security"]["founder_keys_enrolled"]), "chain_verified": st["security"]["chain_verified"],
                     "background": heartbeat.get("state", "NOT RUNNING"), "signer": console.key is not None,
                     "stop": st["security"]["stop_file_present"], "pause": st["security"]["pause_file_present"],
                     "paused": signed_pause},
        "capabilities": caps, "capability_classes": by_class, "providers": providers,
        "missions": missions, "active_missions": len(active),
        "decisions": st["decisions_required"], "goals": st.get("goals", []),
        "position": st.get("developmental_position", {}), "vepmc": st.get("single_bottleneck_metric", {}),
        "presence": st.get("presence", {}), "compute": st.get("compute", {}), "devices": st["security"].get("devices", []),
        "anchor": st.get("external_anchor", {}), "cognition": st.get("cognition", {}),
        "appraisals": appraisals, "receipts": receipts, "events": events, "quarantined": quarantined,
        "morning": {k: morning.get(k) for k in ("q1_goals_worked_on", "q3_what_i_did", "q4_intentionally_not_done", "q6_what_failed",
                                                 "q7_surprises", "q9_learned", "q12_decisions_required", "q13_tonight", "claims_not_made")},
        "templates": sorted(templates.TEMPLATES), "dossiers": dossiers, "ventures": ventures,
        "rehearsals": [b for b in (_books(console.home, m["mission_id"]) for m in missions
                                   if m["mission_id"].startswith("m:venture-rehearsal-")) if b],
        "foundry": _foundry(), "mind": _mind(), "read_roots": st.get("permissions", {}).get("read_roots", []),
        "resilience": _resilience(console),
        "traces": traces, "sandbox_integration": sandbox,
    }
    out["costs"] = cost_rows(action_rows, out["missions"], out["rehearsals"])
    return out


# -- rendering ---------------------------------------------------------------------------------

STYLE_EXTRA = """
nav.mc{display:flex;gap:4px;overflow-x:auto;padding:4px 0 8px;margin:0 0 4px;border-bottom:1px solid var(--line)}
nav.mc a{white-space:nowrap;padding:6px 10px;border-radius:6px;text-decoration:none;color:var(--fg);border:1px solid transparent}
nav.mc a.on{border-color:var(--accent);color:var(--accent);font-weight:600}
.q{border-left:3px solid var(--accent);padding-left:10px;margin:10px 0}.q h2{margin:0 0 4px}
.cls{font-size:12px;font-weight:600;padding:1px 7px;border-radius:99px;border:1px solid var(--line);white-space:nowrap}
.cls.RUNNABLE,.cls.COMPLETE,.cls.DEFAULT_FOR_GEOMETRY,.cls.VERIFIED{color:var(--ok);border-color:var(--ok)}
.cls.BLOCKED,.cls.REFUTED,.cls.OUTSTANDING{color:var(--warn);border-color:var(--warn)}
.cls.SPENDS_MONEY,.cls.NEEDS_FOUNDER_ATTACH,.cls.PARTIAL{color:var(--accent);border-color:var(--accent)}
.reality{font-size:12px;color:var(--muted)}.empty{color:var(--muted);font-style:italic}
section{overflow-x:auto}
"""


def _cls(name) -> str:
    return f"<span class='cls {_e(name)}'>{_e(name)}</span>"


def _nav(view: str) -> str:
    return "<nav class=mc>" + "".join(f"<a href='/mc/{k}' class='{'on' if k == view else ''}'>{_e(t)}</a>" for k, t in VIEWS) + "</nav>"


def _table(headers, rows) -> str:
    if not rows:
        return "<p class=empty>Nothing yet.</p>"
    return ("<table><tr>" + "".join(f"<th>{_e(h)}</th>" for h in headers) + "</tr>"
            + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>")


def _button(console, action: str, fields: dict, label: str, *, cls: str = "secondary", confirm: str | None = None) -> str:
    """Posts to the console's existing signed-command handlers; Mission Control has no write path of its own."""
    hidden = "".join(f"<input type=hidden name='{_e(k)}' value='{_e(v)}'>" for k, v in fields.items())
    onsubmit = f" onsubmit=\"return confirm('{_e(confirm)}')\"" if confirm else ""
    disabled = "" if console.key is not None else " disabled title='read-only console: no founder key'"
    return (f"<form class=inline method=post action='{_e(action)}'{onsubmit}><input type=hidden name=csrf "
            f"value='{_e(console.csrf)}'>{hidden}<button class='{cls}'{disabled}>{_e(label)}</button></form>")


def _mission_controls(console, m) -> str:
    if m["status"] in ("ACHIEVED", "ABANDONED", "SUPERSEDED"):
        return ""
    pause = (_button(console, "/lifecycle", {"mission_id": m["mission_id"], "action": "resume"}, "Resume") if m["paused"]
             else _button(console, "/lifecycle", {"mission_id": m["mission_id"], "action": "pause"}, "Pause"))
    return pause + " " + _button(console, "/lifecycle", {"mission_id": m["mission_id"], "action": "revoke"}, "Revoke",
                                 cls="danger", confirm=f"Revoke {m['mission_id']}? It stops and is not resumed.")


def _first_mission_form(console, form) -> str:
    can = console.key is not None
    return ("<form method=post action=/first-mission><input type=hidden name=csrf value='" + _e(console.csrf) + "'>"
            "<label>Effort budget (units of work GREG may plan into the selection) "
            "<input name=effort_budget type=number min=1 max=200 value=8 style='width:7em'></label> "
            "<button>Prepare the Founder's First Mission</button></form>"
            "<p class=muted>GREG drafts one mission contract and shows you exactly what signing it allows. "
            + ("Nothing runs until you sign." if can else "This console is read-only (no founder key); review works, signing needs <code>--key</code>.")
            + "</p>")


def render_view(console, view: str, form) -> str:
    p = projection(console)
    ident = p["identity"]
    head = (f"<h1>GREG Mission Control</h1><p class=muted>Body {_e(ident['body_id'])} · "
            f"{'<span class=ok>' + _e(ident['background']) + '</span>' if ident['background'] in ('RUNNING', 'PAUSED') else '<span class=warn>' + _e(ident['background']) + '</span>'}"
            f" · ledger chain {'<span class=ok>verified</span>' if ident['chain_verified'] else '<b class=warn>FAILED</b>'}"
            f" · {'founder key unlocked' if ident['signer'] else '<span class=warn>read-only (start with --key to sign)</span>'}"
            f"{' · <b class=warn>STOP file present</b>' if ident['stop'] else ''}{' · <b class=warn>paused</b>' if ident['pause'] or ident['paused'] else ''}</p>")
    body = {"overview": _overview, "command": _command, "mind": _mind_view, "body": _body_view, "organs": _organs,
            "goals": _goals, "ventures": _ventures, "proof": _proof, "authority": _authority, "night": _night}[view](console, p, form)
    return head + _nav(view) + body


def _overview(console, p, form) -> str:
    c = p["capability_classes"]
    runnable = c.get("RUNNABLE", 0)
    pos = p["position"] or {}
    decisions = p["decisions"]
    out = ["<section class=q><h2>What is GREG?</h2><p>A persistent institution on this computer that works toward the "
           "objectives you authorize. It plans with many kinds of intelligence, acts only through capabilities you have "
           "attached, keeps a hash-chained record of everything it does, and never creates authority for itself. You can "
           "pause, revoke or stop it at any time.</p></section>",
           "<section class=q><h2>What can it actually do right now?</h2><div class=grid>"
           + "".join(f"<div class=stat><b>{c.get(k, 0)}</b>{_cls(k)}</div>" for k in ("RUNNABLE", "NEEDS_FOUNDER_ATTACH", "SPENDS_MONEY", "BLOCKED"))
           + f"<div class=stat><b>{p['foundry']['counts'].get('COMPLETE', 0)}/55</b>Foundry systems with re-derived evidence</div>"
           f"<div class=stat><b>{p['mind']['counts'].get('DEFAULT_FOR_GEOMETRY', 0) + p['mind']['counts'].get('NICHE_CAPABILITY', 0)}</b>admitted intelligences (measured)</div></div>"
           f"<p class=muted>{runnable} capabilities run now on this body. Classes come from each capability's own state and health; "
           "see <a href=/mc/command>Command</a> for the full map.</p></section>",
           f"<section class=q><h2>What is it doing?</h2><p>{p['active_missions']} active mission(s) of {len(p['missions'])}. "
           + (_table(["Mission", "State", "Blocker / next", "Your control"], [[_e(m['mission_id']) + "<br><span class=muted>" + _e(m['intended_effect'][:140]) + "</span>",
                                                            _e(m['status']) + (" (paused)" if m['paused'] else ""), _e(m['blocker'] or m['next_observe_at'] or ''),
                                                            _mission_controls(console, m)]
                                                           for m in p["missions"][-6:]]) if p["missions"] else
              "<span class=empty>No mission yet. The Founder's First Mission below is the intended start.</span>") + "</p></section>",
           "<section class=q><h2>What valuable work can I command?</h2>" + _first_mission_form(console, form)
           + "<p>Or describe any goal in <a href=/mc/command>Command</a>; GREG proposes a contract you review before anything runs.</p></section>",
           f"<section class=q><h2>What needs my authority?</h2><p>{len(decisions)} decision(s) waiting. "
           + (f"Primary objective <b>{_e(pos.get('active'))}</b> ({_e(pos.get('title'))}); its gate: {_e(pos.get('gate'))}." if pos else "")
           + "</p>" + ("" if decisions else "<p class=empty>No decision is waiting. When GREG needs you, the request and "
                       "its approve, reject or attach buttons appear here.</p>") + "</section>"]
    parts = form if isinstance(form, dict) else {}
    out.append(parts.get("decisions", ""))
    if p["dossiers"]:
        out.append("<section><h2>Founder's First Mission dossiers</h2><ul>" + "".join(
            f"<li><a href='/first-mission/{_e(n)}'>{_e(n)}</a></li>" for n in p["dossiers"]) + "</ul></section>")
    out += [parts.get(k, "") for k in ("gravity", "closures", "deliveries")]
    body_paused = p["identity"]["pause"] or p["identity"]["background"] == "PAUSED" or p["identity"].get("paused")
    out.append("<section><h2>Pause or resume the whole body</h2><p class=muted>A signed pause holds every mission at its "
               "next step; nothing is lost and resume continues from the ledger.</p>"
               + _button(console, "/body", {"mode": "resume" if body_paused else "pause"},
                         "Resume GREG (signed)" if body_paused else "Pause GREG (signed)") + "</section>")
    out.append(parts.get("stop", ""))
    return "".join(out)


def _command(console, p, form) -> str:
    rows = [[f"<code>{_e(c['capability_id'])}</code><br><span class=muted>{_e(c['description'][:110])}</span>",
             _cls(c["class"]), _e(c["consequence_class"]), _e(c["why"])] for c in sorted(p["capabilities"], key=lambda c: (c["class"], c["capability_id"]))]
    return ("<section><h2>Ask GREG</h2><form method=post action=/ask><input type=hidden name=csrf value='" + _e(console.csrf) + "'>"
            "<textarea name=text rows=4 maxlength=4000 placeholder='GREG, inspect the project sources and capabilities I have authorized. "
            "Understand my current objectives. Identify the highest-value unfinished opportunity...'></textarea>"
            "<p><button>Propose a mission</button> <span class=muted>Plain words become a contract you review; nothing runs before you sign.</span></p></form></section>"
            "<section><h2>Founder's First Mission</h2>" + _first_mission_form(console, form) + "</section>"
            f"<section><h2>Mission templates GREG can draft without a model</h2><p>{', '.join(f'<code>{_e(t)}</code>' for t in p['templates'])}</p></section>"
            "<section><h2>Capability map</h2><p class=reality>Derived from each installed capability's attachment state and health on this body; "
            "worker providers checked live.</p>" + _table(["Capability", "Class", "Consequence", "Why"], rows) + "</section>")


def _mind_view(console, p, form) -> str:
    m = p["mind"]
    rows = [[_e(g["family"]), _e(g["layer"]), _cls(g["status"]), _e(g["baseline"][:80]), f"{_e(g['wins'])}–{_e(g['losses'])}"] for g in m["genomes"]]
    receipts = (p["cognition"] or {}).get("receipts", [])
    return ("<section><h2>Intelligences, admitted by measurement</h2><p class=reality>Held-out evaluation frozen at "
            f"{_e(m.get('frozen'))} (commit {_e(m.get('source_commit'))}). A genome is routed by default only where it beat its "
            "simplest baseline on its native geometry; SUPERSEDED genomes lost to a simpler method and are not routed. "
            "Attaching any of them is your decision.</p><div class=grid>"
            + "".join(f"<div class=stat><b>{v}</b>{_cls(k)}</div>" for k, v in sorted(m.get("counts", {}).items()))
            + "</div>" + _table(["Family", "Layer", "Verdict", "Baseline it had to beat", "Wins–losses vs baseline"], rows) + "</section>"
            f"<section><h2>Checked reasoning on this body</h2><p>{len(receipts)} cognitive receipt(s).</p>"
            + _table(["Problem", "Methods", "Answered"], [[_e(r.get('problem_id')), _e(', '.join(c.get('kind', '') for c in r.get('claims', []))),
                                                           'yes' if r.get('answered') else 'needs evidence'] for r in receipts[-10:]])
            + "<p class=muted>Formal results prove computation and source binding; they do not prove legality, consent, market "
            "acceptance or future success.</p></section>")


def _body_view(console, p, form) -> str:
    c, pres = p["compute"], p["presence"]
    prov = "".join(f"<li><code>{_e(n)}</code>: {'installed' if ok else 'not installed'}</li>" for n, ok in p["providers"].items())
    return ("<section><h2>Process and persistence</h2>" + _table(["Fact", "Value"], [
        ["Background body", _e(p['identity']['background'])], ["Boots recorded", _e(p['identity']['boots'])],
        ["Presence", _e(pres.get('state'))], ["Availability", _e(pres.get('availability'))],
        ["Ledger events", _e(p['events'])], ["Receipts", _e(p['receipts'])]]) + "</section>"
            "<section><h2>Machine</h2>" + _table(["Fact", "Value"], [
                ["System", _e(f"{c.get('system')} {c.get('machine')}")], ["Cores", _e(c.get('cores'))], ["Load ratio", _e(c.get('load_ratio'))],
                ["Memory", _e(round((c.get('memory_bytes') or 0) / 2**30, 1)) + " GiB"],
                ["Disk free", _e(round((c.get('disk_free_ratio') or 0) * 100)) + " %"]]) + "</section>"
            f"<section><h2>Hands</h2><ul>{prov or '<li class=empty>worker module unavailable</li>'}</ul>"
            "<p class=muted>A worker never judges its own work: GREG collects the change, re-runs acceptance with no network and "
            "appraises it independently. Workers spend only a signed budget.</p></section>")


def _discover_section(console, p, form) -> str:
    from greg.discover import discover
    q = (form.get("_query") if isinstance(form, dict) else "") or ""
    box = ("<section><h2>What outcome do you want?</h2><form method=get action=/mc/organs>"
           f"<input name=q maxlength=200 value='{_e(q)}' placeholder='e.g. sell a product and reconcile the revenue'>"
           " <button>Find what helps</button></form><p class=muted>Ranks GREG's mission paths, capabilities and Foundry "
           "systems by the words they declare (lexical retrieval with a small disclosed synonym map); it finds what the "
           "words name, it does not judge feasibility.</p>")
    if not q.strip():
        return box + "</section>"
    classes = {c["capability_id"]: c["class"] for c in p["capabilities"]}
    rows = []
    for r in discover(q, limit=10):
        state = classes.get(r["id"], "UNKNOWN") if r["kind"] == "capability" else r["state"]
        rows.append([_e(r["kind"]), f"<code>{_e(r['id'])}</code><br><span class=muted>{_e(r['title'])}</span>",
                     _cls(state) if r["kind"] != "mission path" else _e(state),
                     _e(r.get("gap") or r["how"])[:300], _e(", ".join(r["matched"]))])
    return box + _table(["Kind", "What", "State here", "How to use it / gap", "Matched"], rows) + "</section>"


def _organs(console, p, form) -> str:
    f = p["foundry"]
    rows = [[_e(s["id"]), _e(s["name"]), _cls(s["state"]), f"<code>{_e(s['module'] or '—')}</code>"
             + (f"<br><span class=muted>alternates: {_e(', '.join(s['alternates']))}</span>" if s["alternates"] else ""),
             _e(s["gap"] or s["interface"])] for s in f["systems"]]
    organs = [x.name for x in sorted((KERNEL_ROOT / "organs").glob("*.manifest.yaml"))] if (KERNEL_ROOT / "organs").is_dir() else []
    return (_discover_section(console, p, form) + "<section><h2>Foundry: the 55-system capability factory</h2><div class=grid>"
            + "".join(f"<div class=stat><b>{v}</b>{_cls(k)}</div>" for k, v in sorted(f["counts"].items()))
            + f"</div><p class=reality>{_e(f['note'])}</p>" + _table(["#", "System", "State", "Module", "Gap or interface"], rows) + "</section>"
            f"<section><h2>Organ manifests</h2><p>{', '.join(f'<code>{_e(o)}</code>' for o in organs) or '<span class=empty>none</span>'}</p>"
            "<p class=muted>Organs own domain capability, never authority: every consequence crosses the Kernel's one gate.</p></section>")


def _goals(console, p, form) -> str:
    pos = p["position"] or {}
    return ("<section><h2>Infinite Goal Chase</h2>" + _table(["", ""], [
        ["Achieved", _e(", ".join(pos.get("achieved", [])) or "none yet")],
        ["Primary objective", f"<b>{_e(pos.get('active'))}</b> {_e(pos.get('title'))}"],
        ["Its gate", _e(pos.get("gate"))], ["Next node", _e(pos.get("next"))],
        ["Measurement", f"<pre>{_e(json.dumps(pos.get('measurement'), indent=1, default=str))}</pre>"]])
            + "<p class=muted>Exactly one node is operationally primary: the first whose exit evidence does not hold on this ledger.</p></section>"
            f"<section><h2>Persistent goals</h2>{_table(['Goal'], [[_e(json.dumps(g, default=str)[:300])] for g in p['goals']])}</section>")


def _ventures(console, p, form) -> str:
    rows = [[_e(b["mission_id"]), _cls("FIXTURE"), _e(f"{(b.get('totals') or {}).get('revenue', '—')} cents"),
             "balanced" if b.get("equation_holds") and not b.get("error") else _e(b.get("error", "does not balance")),
             "no"] for b in p["rehearsals"]]
    rehearsal = ("<section><h2>Commerce rehearsal (FIXTURE)</h2><p>Take your latest First Mission dossier through GREG's "
                 "governed company loop: offer, a fixture buyer's signed order, delivery, signed acceptance, books reconciled "
                 "to the cent. Every check is re-observed by the appraisal. The buyer is a published fixture key and no "
                 "payment rail is called.</p>"
                 + (_button(console, "/venture-rehearsal", {}, "Prepare the commerce rehearsal", cls="") if p["dossiers"] else
                    "<p class=empty>Run the Founder's First Mission first; the rehearsal sells its dossier.</p>")
                 + _table(["Rehearsal", "Mode", "Revenue booked", "Books", "Money moved"], rows) + "</section>")
    return rehearsal + ("<section><h2>Ventures</h2>" + (_table(["Delivered memo"], [[_e(v)] for v in p["ventures"]]) if p["ventures"] else
            "<p class=empty>No venture memo has been delivered on this body. A <code>venture-assessment</code> mission runs RailScout "
            "and WealthMachine on one signal and delivers a memo; nothing is sent, bought or contacted.</p>")
            + "<p class=reality>Revenue, customers and business validation stay hypotheses until external evidence exists. "
            "The Foundry's company loop (#49) runs end to end only in the sandbox with fixtures.</p></section>")


def _proof(console, p, form) -> str:
    v = p["vepmc"] or {}
    a = p["anchor"] or {}
    return ("<section><h2>Proof</h2>" + _table(["", ""], [
        ["Ledger chain", "verified" if p["identity"]["chain_verified"] else "<b class=warn>FAILED</b>"],
        ["External anchors (RFC 3161)", _e(f"{a.get('verified', 0)} verified of {a.get('anchors', 0)}; configured: {a.get('configured')}")],
        ["VEPMC", f"<b>{_e(v.get('VEPMC', 0))}</b> — {_e(v.get('external_confirmation_required', ''))}"],
        ["Sandbox whole-machine closures (engineering diagnostic; never VEPMC)",
         _e(f"{(p.get('sandbox_integration') or {}).get('SANDBOX_WHOLE_MACHINE_CLOSURES', 0)} — "
            f"{(p.get('sandbox_integration') or {}).get('tier', '')}")]])
            + "</section><section><h2>Independent appraisals</h2>"
            + _table(["Mission", "Verdict", "At"], [[_e(x["mission_id"]), _cls(x["verdict"]), _e(x["at"])] for x in p["appraisals"][::-1]])
            + "</section>" + _traces_section(p.get("traces") or {}) + _resilience_section(p["resilience"])
            + "<section><h2>Quarantine</h2>"
            + _table(["Capability", "Why"], [[_e(q.get("capability_id")), _e(q.get("reason") or q.get("why") or "")] for q in p["quarantined"]])
            + "</section>")


def _traces_section(traces: dict) -> str:
    """Each mission's trace, drawn from retained events only (Foundry #44 correlation)."""
    if not traces:
        return "<section><h2>Mission traces</h2><p class=empty>No mission events retained yet.</p></section>"
    parts = ["<section><h2>Mission traces</h2><p class=reality>Every row is a retained ledger event: actions, "
             "observations, organ exchanges, capability formation, decisions and appraisals, in time order.</p>"]
    for mid, spans in sorted(traces.items()):
        rows = [[_e(s.get("at", "")[:19]), _e(s["kind"]), _e(s.get("capability") or s.get("request_id") or ""),
                 _cls(s["verdict"]) if s.get("verdict") else _e(s.get("status") or s.get("answer") or s.get("reason") or ""),
                 _e(s["event_id"][:16])] for s in spans]
        parts.append(f"<h3 id='trace-{_e(mid)}'>{_e(mid)}</h3>" + _table(["At", "Kind", "Capability / request",
                                                                           "Status / verdict", "Event"], rows))
    return "".join(parts) + "</section>"


def _resilience_section(r: dict) -> str:
    if r.get("error"):
        return f"<section><h2>Recovery and learning</h2><p class=warn>Projection failed: {_e(r['error'])}</p></section>"
    e = r.get("episodes", {})
    def rate(x):
        return "—" if x is None else f"{x:.0%}"
    verdicts = [[_e(cap), _cls(v.get("verdict", "")), _e(v.get("failures")), rate(v.get("completion_before")),
                 rate(v.get("completion_after")), "yes" if v.get("learning_artifact_after_failure") else "no"]
                for cap, v in sorted((r.get("after_failure") or {}).items())]
    median = e.get("median_recovery_seconds")
    unaided = e.get("recovered_without_founder")
    return ("<section><h2>Recovery and learning</h2>" + _table(["", ""], [
        ["Failures / recovered / open", _e(f"{e.get('failures', 0)} / {e.get('recovered', 0)} / {e.get('open', 0)}")],
        ["Median recovery", "—" if median is None else f"{median:.1f} s"],
        ["Recovered without you", rate(unaided)],
        ["Warnings", _e("; ".join(r.get("warnings") or []) or "none")]])
            + "<p class=reality>" + _e(r.get("rule", "")) + "</p>"
            + _table(["Capability", "After-failure verdict", "Failures", "Completion before", "Completion after",
                      "Learning recorded"], verdicts) + "</section>")


def _authority(console, p, form) -> str:
    rows = [[_e(m["mission_id"]), _e(", ".join(m["cone"]["capabilities"])[:200]), _e(m["cone"]["ceiling"]), f"${_e(m['cone']['budget_usd'])}",
             _e(m["cone"]["horizon"])] for m in p["missions"]]
    return ("<section><h2>Who may act, within what envelope</h2>" + _table(["", ""], [
        ["Founder keys enrolled", _e(p["identity"]["founder_keys"])], ["Delegated devices", _e(len(p["devices"]))],
        ["Read roots", _e(", ".join(p["read_roots"]))], ["Pause file", _e(p["identity"]["pause"])], ["Stop file", _e(p["identity"]["stop"])]])
            + "<h2>Mission envelopes</h2>" + _table(["Mission", "May use without asking", "Ceiling", "Budget", "Expires"], rows)
            + "<h2>Money, kept in separate columns</h2><p class=reality>Booked spend comes from recorded actions. "
            "Provider-measured is what a provider reported. Unknown is booked at the signed cap, never assumed lower. "
            "FIXTURE amounts are rehearsal books and moved no money.</p>"
            + _table(["Mission", "Budget", "Booked", "Provider-measured", "Unknown (booked at cap)", "FIXTURE (no money moved)"],
                     [[_e(c["mission_id"]), f"${c['budget_usd']:.2f}", f"${c['booked_usd']:.2f}", f"${c['measured_usd']:.2f}",
                       f"${c['unknown_at_cap_usd']:.2f}", f"{c['fixture_cents']} cents" if c["fixture_cents"] else "—"]
                      for c in p["costs"]])
            + "<p class=muted>Intelligence never creates authority. A recommendation becomes an action only through a signed mission or "
            "decision, and only inside its envelope.</p></section>" + (form.get("stop", "") if isinstance(form, dict) else ""))


def _night(console, p, form) -> str:
    m = p["morning"]
    return ("<section><h2>Night Shift / Morning Tribunal</h2>" + _table(["Question", "Answer from the ledger"], [
        [_e(k.split("_", 1)[1].replace("_", " ")), f"<pre>{_e(json.dumps(v, indent=1, default=str)[:1500])}</pre>"] for k, v in m.items()]) + "</section>")
