"""Typed blockers: every open mission blocker as one record the founder can act on (directive section 29).

"Blocked goals remain durable. Store: blocker, why blocked, reconsideration condition, required evidence, required
authority, next possible move." The mission engine already keeps each blocker on the canonical journal
(``mission.blocked`` and ``mission.unblocked``, greg/missions.py) and already decides when one is resolved
(``MissionEngine._blocker_resolved``). This module only projects. It folds the journal through the one MissionBook,
asks the engine's own resolution rule whether each blocker still holds, and types the blockers that do. A blocker
the next tick would lift (resolved by that rule, or its ask withdrawn by the body) is still typed while a pause or
hold keeps that tick from coming, with the hold and what lifts it.

A record names who would have to act and with what; it grants nothing. The projection records, signs, attaches and
asks nothing, and never opens the secret broker. A field that genuinely does not apply says ``none required:`` and
why, never an empty value.
"""
from __future__ import annotations

import json
from pathlib import Path

from greg import asks

FIELDS = ("mission_id", "kind", "blocker", "why", "reconsider_when", "required_evidence", "required_authority",
          "next_move", "since", "source_event")
NONE = "none required: "
SIGNER = "your key, or a device key you delegated {kind} to"


class BlockerError(ValueError):
    """A typed record missing a field: a defect in this projection, never shown half-typed."""


def _none(reason: str) -> str:
    if not reason.strip():
        raise BlockerError("'none required' needs its reason")
    return NONE + reason


def _text(value) -> str:
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value if str(v).strip())
    return str(value).strip() if value is not None else ""


def _join(*parts) -> str:
    return "; ".join(dict.fromkeys(p for p in (_text(x) for x in parts) if p))


def _scope(request: dict) -> str:
    asked = request.get("authority_requested")
    return json.dumps(asked, sort_keys=True, default=str) if asked else "the scope recorded on the ask"


def _signer(kind: str) -> str:
    return SIGNER.format(kind=kind)


def _decision(m, b: dict, request: dict, state: str, held: bool) -> dict:
    from greg.missions import NOT_ANSWERABLE
    rid, kind = b.get("request_id"), request.get("kind") or "unrecorded"
    reconsider = b.get("reconsider") or f"your answer to {rid}"
    if b.get("failing_checks"):             # greg/missions.py _step: such a blocker is watched, not only waited on
        reconsider += (f"; meanwhile GREG re-observes {', '.join(b['failing_checks'])} at the mission's cadence and "
                       "withdraws the ask if they pass without any GREG action")
    out = {"blocker": f"founder decision: {kind} ask {rid}"
                      + (f" on action {b['action_id']}" if b.get("action_id") else "")
                      + (f" ({spend})" if request.get("resource") == "spend"
                         and (spend := (request.get("authority_requested") or {}).get("spend")) else ""),
           "why": _join(b.get("why"), request.get("why_now")), "reconsider_when": reconsider}
    if kind in NOT_ANSWERABLE:              # no DECISION lifts it: the engine refuses one (MissionEngine.answer)
        return {**out, "required_evidence": _none(f"a {kind} ask is lifted by your signed command alone, "
                                                  "not by evidence"),
                "required_authority": NOT_ANSWERABLE[kind],
                "next_move": asks.NOT_ANSWERABLE.get(kind, NOT_ANSWERABLE[kind])}
    return {**out,
            "required_evidence": f"your signed DECISION on {rid}, accepted on this body's ledger; the mission book "
                                 "counts no other row as your answer (now: " + state + ")",
            "required_authority": f"a founder-signed DECISION ({_signer('DECISION')}) answering exactly: "
                                  + _scope(request),
            "next_move": f"answer it: greg decide {rid} approve|reject, or the console or phone"
                         + (f"; recommended: {request['recommendation']}" if request.get("recommendation") else "")
                         + "; GREG lifts the blocker at the next tick after your answer"}


def _reconciliation(m, b: dict, request: dict, state: str, held: bool) -> dict:
    rid, aid = b.get("request_id"), b.get("action_id")
    attempt = f"attempt {b['attempt']}" if b.get("attempt") is not None else "its latest attempt"
    booked = ((request.get("evidence") or {}) if isinstance(request.get("evidence"), dict) else {}).get(
        "booked_usd_by_answer")
    return {"blocker": f"uncertain dispatch of {aid} ({attempt}): reconciliation ask {rid}",
            "why": _join(b.get("why"), request.get("why_now")),
            "reconsider_when": b.get("reconsider") or f"your answer to {rid}",
            "required_evidence": f"your account of whether {attempt} of {aid} (proposal {b.get('proposal_id')}, "
                                 f"grant {b.get('grant_id')}) took effect: a signed DECISION reconcile_executed or "
                                 f"reconcile_not_executed on {rid}"
                                 + (f"; booked USD by answer: {json.dumps(booked, sort_keys=True)}" if booked else ""),
            "required_authority": f"a founder-signed DECISION ({_signer('DECISION')}) on {rid}; asked: "
                                  + _scope(request),
            "next_move": f"answer it: greg decide {rid} reconcile_executed|reconcile_not_executed"
                         + (f"; recommended: {request['recommendation']}" if request.get("recommendation") else "")
                         + "; until then nothing is retried, dispatched or undone for this mission"}


def _capability(m, b: dict, request: dict, state: str, held: bool) -> dict:
    rid, function = b.get("request_id"), b.get("function")
    candidates, named_cid = list(b.get("attach_candidates") or ()), b.get("capability_id")
    named = f" ({', '.join(candidates)})" if candidates else ""
    return {"blocker": f"missing capability for {function}" + (f": attach ask {rid}" if rid else "")
                       + (", a body-level ask other missions share" if b.get("shared_ask") else ""),
            "why": _join(b.get("why"), request.get("why_now")),
            "reconsider_when": _join(b.get("reconsider"), "GREG re-checks at every tick"),
            "required_evidence": f"a capability for {function} that this body's registry reports usable, or that "
                                 "Capability Genesis reports serving this need (the rule a mission arriving now "
                                 "meets); now: " + (state if state != "none" else "the blocker names no capability "
                                                                                    "and nothing serves the function"),
            "required_authority": f"your signed CAPABILITY_ATTACH of a verified capability{named}; "
                                  + asks.ANSWER_ONLY_RECORDS["CAPABILITY_ATTACH"],
            "next_move": (f"attach one with greg attach <capability_id>{named}, or revise or abandon the mission"
                          if candidates else
                          f"this blocker names {named_cid} (now: {state}): attach it with greg attach {named_cid} if it "
                          "is verified, or revise or abandon the mission" if named_cid else
                          _join(request.get("recommendation") or "attach a verified capability for this function, "
                                                                 "or revise the mission",
                                "this blocker names no verified candidate"))}


def _human_work(m, b: dict, request: dict, state: str, held: bool) -> dict:
    rid, function = b.get("request_id"), b.get("function")
    checks = b.get("failing_checks") or []
    return {"blocker": f"work only a person may do: {function} (ask {rid})",
            "why": _join(b.get("why"), request.get("why_now")),
            "reconsider_when": _join(b.get("reconsider"), "GREG re-observes at the mission's cadence"),
            "required_evidence": (f"the mission's own checks {', '.join(checks)} re-observed passing: the "
                                  "deliverable exists where they read (GREG checks that it exists, not its "
                                  "professional quality)") if checks else
                                 ("not observable: no check of this mission watches this step; revise how it is "
                                  "observed"),
            "required_authority": _none("GREG asks for no grant; you arrange, contract and pay the person yourself, "
                                        "outside GREG. " + asks.ANSWER_ONLY_RECORDS["HUMAN_WORK"]),
            "next_move": request.get("recommendation") or f"do {function} yourself or through a person you choose, "
                                                          "and place the deliverable where the check reads it"}


def _outage(m, b: dict, request: dict, state: str, held: bool) -> dict:
    from greg.missions import MissionEngine
    rid, function, when = b.get("request_id"), b.get("function"), b.get("retry_at")
    asked = (f"; from the {MissionEngine.OUTAGE_DEFERRALS}th consecutive outage you are also told (ask {rid}), "
             "and an answer there only records it") if rid else ""
    return {"blocker": f"host outage while forming {function} (consecutive outage {b.get('attempt')})",
            "why": _join(b.get("why"), state),
            "reconsider_when": _join(f"after {when}" if when else "", b.get("reconsider")),
            "required_evidence": _none("an outage is no evidence about any candidate; the search re-runs once the "
                                       "back-off elapses"),
            "required_authority": _none("the re-run searches under the mission's own signed scope and budget and "
                                        "asks for no new authority" + asked),
            "next_move": f"GREG re-runs the search for {function}" + (f" after {when}" if when else "")
                         + ("" if held else "; nothing for you to do")    # under a hold, lifting it is yours
                         + (f"; ask {rid} stays open for your view" if rid else "")}


def _no_strategy(m, b: dict, request: dict, state: str, held: bool) -> dict:
    why = _text(b.get("why")) or "no strategy the mission may run"
    return {"blocker": f"no admissible strategy: {why}", "why": why,
            "reconsider_when": f"every tick ({state})",
            "required_evidence": _none(f"it is re-evaluated at every tick and holds while its cause holds ({why})"),
            "required_authority": f"a new founder-signed MISSION (your key) that removes the cause ({why}), "
                                  "superseding this one",
            "next_move": "GREG re-observes at the next tick and blocks again while the cause holds; revise the "
                         "mission or abandon it"}


TYPES = {"decision": _decision, "reconciliation": _reconciliation, "capability": _capability,
         "human_work": _human_work, "outage": _outage, "no_strategy": _no_strategy}


def _unknown(m, b: dict, request: dict, state: str, held: bool) -> dict:
    unknown = f"unknown: blocker type {b.get('type')!r} is not one greg/missions.py resolves ({state})"
    return {"blocker": unknown, "why": _text(b.get("why")) or unknown, "reconsider_when": unknown,
            "required_evidence": unknown, "required_authority": unknown, "next_move": unknown}


def typed(m, book, state: str, event, *, holds=(), lifted: str | None = None) -> dict:
    """One open blocker of mission ``m`` (its fold state), typed. ``state`` is the engine's own word on it
    (``_blocker_resolved``); ``event`` the ``mission.blocked`` fact that recorded it. ``holds``: the pauses in force
    over the mission (``active_constraint``'s ``paused_by``: the body's, then the mission's own), each with what
    lifts it. ``lifted``: why the next tick would lift this blocker, given only while a hold keeps that tick away."""
    b = m.blocker
    request = book.requests.get(b.get("request_id")) or {}
    record = {"mission_id": m.mission_id, "kind": _text(b.get("type")) or "unknown",
              **TYPES.get(b.get("type"), _unknown)(m, b, request, state, bool(holds)),
              "since": event.occurred_at if event is not None else "not recorded: no mission.blocked fact holds it",
              "source_event": event.event_id if event is not None else "not recorded: no mission.blocked fact"}
    until = "; ".join(_text(h.get("lifted_by")) for h in holds)
    if lifted is not None:                  # nothing is owed on the blocker itself: only the hold keeps it
        record.update(reconsider_when="at the first tick after it",
                      required_evidence=_none(f"nothing more is needed: {lifted}"),
                      required_authority=f"{until} (that lifts the hold; the blocker itself needs none: {lifted})",
                      next_move=f"nothing to answer; GREG lifts this blocker at that tick ({lifted})")
    if holds:                               # greg/missions.py _step and Body.tick: nothing moves while one holds
        record["reconsider_when"] = f"only once the hold lifts ({until}): {record['reconsider_when']}"
        record["next_move"] = "; ".join(f"{_text(h.get('by'))}: nothing moves until {_text(h.get('lifted_by'))}"
                                        for h in holds) + ". Then: " + record["next_move"]
    missing = [f for f in FIELDS if not (isinstance(record.get(f), str) and record[f].strip())]
    if missing or set(record) != set(FIELDS):
        raise BlockerError(f"blocker of {m.mission_id} typed without {missing or sorted(set(record) ^ set(FIELDS))}")
    return {f: record[f] for f in FIELDS}


def _home(journal) -> Path | None:
    """The body home this journal's ledger lives in (greg.body.Layout), else None."""
    from greg.body import Layout
    path = getattr(getattr(journal, "ledger", None), "path", None)
    if not path:
        return None
    home = Path(path).resolve().parent
    return home if Layout(home).ledger == Path(path).resolve() and Layout(home).config.is_file() else None


def resolution_engine(journal, home=None):
    """A MissionEngine over a read-only view of the body's registry, so ``_blocker_resolved`` answers exactly as on
    the body: built-ins, every capability Genesis formed (re-checked as at restart, nothing written) and every
    recorded state change. It holds no office and no secret broker; this module calls nothing on it but the
    resolution rule."""
    from greg.body import Layout
    from greg.cognition.cortex import registry_view
    from greg.genesis import Genesis
    from greg.missions import MissionEngine
    home = Path(home) if home is not None else _home(journal)
    registry = registry_view(journal)
    workspace = Layout(home).workspace if home is not None else Path(".")
    genesis = None
    if home is not None:
        genesis = Genesis(journal=journal, registry=registry, workspace_root=workspace)
        genesis.restore(record=False)
    return MissionEngine(journal=journal, office=None, registry=registry, secrets=None, workspace_root=workspace,
                         read_roots=(), genesis=genesis)


def open_blockers(journal, *, home=None, engine=None, mission_id: str | None = None) -> list[dict]:
    """Every open blocker of a mission still pursued (not ACHIEVED, ABANDONED or SUPERSEDED), one typed record each.

    A blocker the next tick lifts is not shown: one the engine's own rule (``MissionEngine._blocker_resolved``)
    treats as resolved, or whose ask the body withdrew (``active_constraint``'s marker; ``_step`` then finishes the
    withdrawal). While a pause or hold is in force that tick does not come (``_step`` returns PAUSED first; a paused or
    held body ticks no mission), so such a blocker is shown with the hold and what lifts it. ``engine``: the running
    body's engine when the caller has one; otherwise a read-only one is built (``resolution_engine``)."""
    from greg.body import Layout, body_pauses
    from greg.missions import TERMINAL, active_constraint
    home = Path(home) if home is not None else _home(journal)
    if getattr(engine, "registry", None) is None:
        engine = resolution_engine(journal, home)
    book = engine.book
    book.rebuild()
    body_held = body_pauses(journal, pause_file=home is not None and Layout(home).pause_file.exists())
    blocked = {}
    for event in journal.replay("mission.blocked"):
        blocked.setdefault(event.payload.get("mission_id"), []).append(event)
    out = []
    for mid, m in sorted(book.missions.items()):
        if m.blocker is None or m.status in TERMINAL or (mission_id is not None and mid != mission_id):
            continue
        constraint = active_constraint(m, book, body_paused=body_held) or {}
        holds = constraint.get("paused_by") or []
        resolved, state = engine._blocker_resolved(m)
        shown = constraint.get("blocker") or {}
        lifted = state if resolved else f"the body withdrew its ask: {shown['withdrawn']}" if "withdrawn" in shown \
            else None
        if lifted is not None and not holds:
            continue                        # the next tick lifts it
        event = next((e for e in reversed(blocked.get(mid, [])) if e.payload.get("blocker") == m.blocker), None)
        out.append(typed(m, book, state, event, holds=holds, lifted=lifted))
    return out


def section(journal, **kw) -> list[dict] | dict:
    """``open_blockers`` for a founder surface (the morning report, Mission Control). A failure to compute it (a
    formed capability that no longer restores, a record this module could not type) is shown in its place, never
    hidden and never taking the surface's other sections down: ``{"unavailable", "error"}``, never an empty list."""
    try:
        return open_blockers(journal, **kw)
    except Exception as exc:                # a projection failure is shown, never hidden
        return {"unavailable": "the typed blockers could not be computed; greg status still names each mission's "
                               "blocker", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
