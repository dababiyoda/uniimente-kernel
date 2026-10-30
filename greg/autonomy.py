"""Earned autonomy (directive sections 59-60): failure regresses a standing approval; the earned level is reported.

Neither part grants anything.

1. ``regress``: a standing approval falls as soon as failure evidence names a run it allowed. A founder APPROVAL of
   an exact unpaid scope stands until it is withdrawn: greg/missions.py keeps it in ``approved_scopes`` and voids it
   only on a paid run or a restore. When the evidence says a run under it failed, it is withdrawn the way
   greg/recovery.py withdraws an approval after a restore: one ``decision.withdrawn`` with ``voids_approval``, which
   the mission fold already reads. The next selection of that scope asks the founder again. Failure evidence is:

   - **refuted:** the independent appraisal REFUTED the closure whose window holds the run (greg/appraisal.py's
     window: since the registration, or the mission's previous hold, up to the closure);
   - **ineffective:** the run executed, the world was re-observed and the check it advances still failed, as the
     mission's own loop judged it (the ``routing.outcome`` ``ineffective`` record the engine writes).

   Each regression is recorded first as ``autonomy.regressed`` (the evidence), then as the withdrawal. Only approvals
   asked before the failed run are withdrawn, so an approval the founder gives after the regression stands. A
   withdrawal narrows authority; it never widens it. A live mission only: a closed one selects nothing more.

2. ``report``: a read-only fold of the journal per (capability, action class, target pattern, budget band). It names
   the level the evidence has earned: SHADOW, RECOMMENDER or SUPERVISED_CANARY, by the thresholds below. A refuted or
   ineffective run, or a regression, drops the tuple back at once: only verified runs after the latest such failure
   count towards a level. BOUNDED_AUTONOMY and MANAGE_BY_EXCEPTION are never earned from evidence: they would need a
   founder-signed grant, which does not exist (NEEDS_FOUNDER_DECISION). A level changes nothing: every action still
   needs its light cone, its exact-scope approvals and the Gate.

Limits: a strategy the founder pre-approved inside the signed mission (``pre_approved_steps``) is part of the signed
mission and is not withdrawn here. A capability failure (a REFUSED receipt) counts against the level but does not
regress an approval: the mission's loop already keeps that strategy out of selection. An approval already standing on
a body when this code first runs is regressed by the failure evidence already on its ledger.
"""
from __future__ import annotations

import math

from greg.capabilities import BUILTINS
from greg.journal import fact_id, iso
from greg.missions import TERMINAL

LEVELS = ("SHADOW", "RECOMMENDER", "SUPERVISED_CANARY", "BOUNDED_AUTONOMY", "MANAGE_BY_EXCEPTION")
EARNED_CEILING = "SUPERVISED_CANARY"    # the highest level evidence alone reaches
RECOMMENDER_MIN_VERIFIED = 1            # verified runs since the latest failure
CANARY_MIN_VERIFIED = 5
CANARY_MIN_WILSON = 0.5                 # Wilson lower bound of the verified share of every judged run
WILSON_Z = 1.96
BUDGET_BANDS = ((0.0, "$0"), (1.0, "up to $1"), (10.0, "up to $10"), (100.0, "up to $100"))
SEVERE = ("refuted", "ineffective", "regressed")
ABOVE_CEILING = ("needs a founder-signed grant for this exact tuple; no such grant exists yet "
                 "(NEEDS_FOUNDER_DECISION), so no evidence reaches it")


def _closure_windows(journal, pos) -> dict:
    """appraisal event id -> (mission id, verdict, window start, closure position), as greg/appraisal.py windows a
    closure: from the registration or the mission's previous hold to the closure the appraisal names."""
    marks = {}
    for kind in ("mission.registered", "mission.held", "mission.achieved", "mission.unmet"):
        for e in journal.replay(kind):
            marks.setdefault(e.payload.get("mission_id"), []).append((pos.get(e.event_id, -1), kind, e.event_id))
    windows = {}
    for e in journal.replay("mission.appraised"):
        p = e.payload
        own = sorted(marks.get(p.get("mission_id"), []))
        closure = next((at for at, kind, eid in own if eid == p["closure_event"]), None) if p.get("closure_event") \
            else next((at for at, kind, _ in own if kind == "mission.achieved"), None)
        starts = [at for at, kind, _ in own if kind in ("mission.registered", "mission.held")
                  and closure is not None and at < closure]
        if closure is not None and starts:
            windows[e.event_id] = (p["mission_id"], p.get("verdict"), max(starts), closure, pos.get(e.event_id, -1))
    return windows


def failures(journal) -> list[dict]:
    """Every completed run that failure evidence names, with that evidence (``refuted`` or ``ineffective``)."""
    pos = journal.positions("")
    runs = [e for e in journal.replay("mission.action") if e.payload.get("status") == "DONE"]
    by_receipt = {e.payload["receipt"]: e for e in runs if e.payload.get("receipt")}
    out = []
    for e in journal.replay("routing.outcome"):
        p = e.payload
        run = by_receipt.get(p.get("receipt"))
        if p.get("verdict") == "ineffective" and run is not None \
                and (run.payload["mission_id"], run.payload["action_id"]) == (p.get("mission_id"), p.get("action_id")):
            out.append({"kind": "ineffective", "run": run, "evidence": e.event_id, "at": pos.get(e.event_id, -1),
                        "why": f"it executed and the check it advances still failed ({str(p.get('reason'))[:160]})"})
    for appraisal, (mid, verdict, start, closure, at) in _closure_windows(journal, pos).items():
        if verdict != "REFUTED":
            continue
        for run in runs:
            if run.payload["mission_id"] == mid and start < pos.get(run.event_id, -1) < closure:
                out.append({"kind": "refuted", "run": run, "evidence": appraisal, "at": at,
                            "why": "the independent appraisal refuted the closure this run belongs to"})
    return sorted(out, key=lambda f: (f["at"], pos.get(f["run"].event_id, -1)))


def regress(journal, book, now) -> list[dict]:
    """Withdraw every standing approval a failed run ran under (see the module docstring); returns what it recorded.

    Called by the body before any mission selects its next action, so a regressed scope is asked about again."""
    book.rebuild()
    if not any(m.approved_scopes for m in book.missions.values() if m.status not in TERMINAL):
        return []                       # nothing stands, so nothing can fall
    pos = journal.positions("")
    recorded, handled = [], set()
    for failure in failures(journal):
        run = failure["run"].payload
        m = book.missions.get(run["mission_id"])
        scope = run.get("scope_digest")
        if m is None or m.status in TERMINAL or scope not in m.approved_scopes:
            continue
        ran_at = pos.get(failure["run"].event_id, -1)
        for rid, request in sorted(book.requests.items()):
            if (request.get("kind") != "APPROVAL" or request.get("mission_id") != m.mission_id
                    or request.get("scope_digest") != scope or (book.answers.get(rid) or {}).get("answer") != "approve"
                    or rid in book.withdrawn or rid in book.consumed or rid in handled
                    or not pos.get(fact_id("decision.requested", rid), ran_at) < ran_at):
                continue
            handled.add(rid)
            key = [rid, "regressed"]
            regression = journal.retained("autonomy.regressed", key) or journal.record("autonomy.regressed", {
                "request_id": rid, "mission_id": m.mission_id, "action_id": run["action_id"], "scope_digest": scope,
                "tuple": tuple_of(journal, m.spec, run["action_id"], capability=run.get("capability")),
                "evidence": {"kind": failure["kind"], "event_id": failure["evidence"],
                             "run": failure["run"].event_id, "receipt": run.get("receipt")},
                "why": failure["why"], "at": iso(now)}, key=key)
            held = regression.payload        # the withdrawal is derived from the regression alone, so it re-records
            journal.record("decision.withdrawn", {
                "request_id": rid, "mission_id": m.mission_id, "voids_approval": True,
                "why": (f"a run of {held['action_id']} under this approval failed: {held['why']}; the approval no "
                        "longer stands, and GREG asks again before running it")[:400],
                "regression": regression.event_id, "at": held["at"]}, key=[rid, "withdrawn", "regressed"])
            recorded.append(regression.payload)
    if recorded:
        book.rebuild()
    return recorded


def _consequence_class(journal, capability) -> str:
    if capability in BUILTINS:
        return BUILTINS[capability][0].consequence_class
    registered = [e.payload.get("manifest") or {} for e in journal.replay("capability.registered")
                  if (e.payload.get("manifest") or {}).get("capability_id") == capability]
    return registered[-1].get("consequence_class", "unknown") if registered else "unknown"


def target_pattern(target) -> str:
    """The target's scheme as a pattern: ``workspace:c.txt`` -> ``workspace:*``."""
    scheme, sep, _ = str(target or "").partition(":")
    return f"{scheme}:*" if sep else "*"


def budget_band(cost_usd) -> str:
    cost = float(cost_usd or 0.0)
    return next((label for limit, label in BUDGET_BANDS if cost <= limit), f"over ${BUDGET_BANDS[-1][0]:g}")


def tuple_of(journal, spec: dict, action_id: str, *, capability: str | None = None) -> dict:
    """(capability, action class, target pattern, budget band) of one signed strategy."""
    s = next((x for x in spec.get("strategies", []) if x.get("action_id") == action_id), {})
    capability = capability or s.get("capability") or f"function:{s.get('function', '?')}"
    return {"capability": capability, "action_class": _consequence_class(journal, capability),
            "target_pattern": target_pattern(s.get("target")), "budget_band": budget_band(s.get("cost_usd"))}


def wilson_lower(successes: int, trials: int, z: float = WILSON_Z) -> float:
    if trials <= 0:
        return 0.0
    p = successes / trials
    centre = p + z * z / (2 * trials)
    spread = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials))
    return max(0.0, (centre - spread) / (1 + z * z / trials))


def earned_level(evidence: dict) -> str:
    """The level the evidence has earned, never above EARNED_CEILING."""
    recent = evidence["verified_since_last_failure"]
    if recent >= CANARY_MIN_VERIFIED and evidence["wilson_lower"] >= CANARY_MIN_WILSON:
        return "SUPERVISED_CANARY"
    if recent >= RECOMMENDER_MIN_VERIFIED:
        return "RECOMMENDER"
    return "SHADOW"


def _blank(t: dict) -> dict:
    return {"tuple": t, "strategies": 0, "asked": 0, "approved": 0, "rejected": 0, "runs": 0, "verified": 0,
            "refuted": 0, "ineffective": 0, "failed": 0, "unappraised": 0, "regressed": 0, "outcomes": []}


def report(journal) -> dict:
    """The earned level of every tuple a signed strategy names, from the journal alone. Writes nothing."""
    from greg.missions import MissionBook
    from greg.routing import founder_reconciled
    book = MissionBook(journal)          # founder answers count only as re-verified from signed DECISIONs
    pos = journal.positions("")
    rows = {}

    def row(t: dict) -> dict:
        return rows.setdefault(tuple(t.values()), _blank(t))

    def strategy_row(mid, aid, capability=None):
        m = book.missions.get(mid)
        return row(tuple_of(journal, m.spec, aid, capability=capability)) if m is not None else None

    for mid, m in sorted(book.missions.items()):
        for s in m.spec.get("strategies", []):
            strategy_row(mid, s["action_id"])["strategies"] += 1
    for rid, request in book.requests.items():
        asked = request.get("authority_requested") if isinstance(request.get("authority_requested"), dict) else {}
        if request.get("kind") != "APPROVAL" or not asked.get("capability"):
            continue
        # the exact scope asked about (a compensation names its own capability, not its strategy's)
        r = row({"capability": asked["capability"],
                 "action_class": asked.get("consequence_class") or _consequence_class(journal, asked["capability"]),
                 "target_pattern": target_pattern(asked.get("target")),
                 "budget_band": budget_band(asked.get("cost_usd"))})
        r["asked"] += 1
        answer = (book.answers.get(rid) or {}).get("answer")
        if answer == "approve":
            r["approved"] += 1
        elif answer == "reject":
            r["rejected"] += 1
    windows = sorted(_closure_windows(journal, pos).values(), key=lambda w: w[3])
    ineffective = {f["run"].event_id: f["at"] for f in failures(journal) if f["kind"] == "ineffective"}
    for e in journal.replay("mission.action"):
        p = e.payload
        if not p.get("receipt") or founder_reconciled(p) or p.get("status") not in ("DONE", "REFUSED"):
            continue                    # no receipted run: nothing the Gate saw happen
        r = strategy_row(p.get("mission_id"), p.get("action_id"), p.get("capability"))
        if r is None:
            continue
        at = pos.get(e.event_id, -1)
        if p["status"] == "REFUSED":    # the Gate ran it and the capability failed
            r["failed"] += 1
            r["outcomes"].append((at, "failed"))
            continue
        r["runs"] += 1
        if e.event_id in ineffective:   # its closure may still verify: the run itself changed nothing
            r["ineffective"] += 1
            r["outcomes"].append((ineffective[e.event_id], "ineffective"))
            continue
        # judged by the first appraised closure whose window holds it; an unmet or unavailable closure judges nothing
        judged = next((w for w in windows if w[0] == p["mission_id"] and w[2] < at < w[3]), None)
        if judged is None or judged[1] not in ("VERIFIED", "REFUTED"):
            r["unappraised"] += 1
        else:
            kind = "verified" if judged[1] == "VERIFIED" else "refuted"
            r[kind] += 1
            r["outcomes"].append((judged[4], kind))
    for e in journal.replay("autonomy.regressed"):
        r = strategy_row(e.payload.get("mission_id"), e.payload.get("action_id"))
        if r is not None:
            r["regressed"] += 1
            r["outcomes"].append((pos.get(e.event_id, -1), "regressed"))
    tuples = []
    for key in sorted(rows):
        r = rows[key]
        outcomes = sorted(r.pop("outcomes"))
        last_failure = max([at for at, kind in outcomes if kind in SEVERE], default=-1)
        judged = r["verified"] + r["refuted"] + r["ineffective"] + r["failed"]
        interventions = r["approved"] + r["rejected"]
        evidence = {**{k: v for k, v in r.items() if k != "tuple"},
                    "verified_since_last_failure": sum(1 for at, kind in outcomes
                                                       if kind == "verified" and at > last_failure),
                    "wilson_lower": round(wilson_lower(r["verified"], judged), 4),
                    "founder_interventions": interventions,
                    "interventions_per_verified_run": (round(interventions / r["verified"], 4)
                                                       if r["verified"] else None)}
        level = earned_level(evidence)
        above = LEVELS.index(level) + 1
        tuples.append({"tuple": r["tuple"], "level": level, "evidence": evidence,
                       "next_level": LEVELS[above] if above < len(LEVELS) else None,
                       "next_needs": _needs(level, evidence)})
    return {"levels": list(LEVELS), "earned_ceiling": EARNED_CEILING,
            "thresholds": {"RECOMMENDER": {"verified_since_last_failure": RECOMMENDER_MIN_VERIFIED},
                           "SUPERVISED_CANARY": {"verified_since_last_failure": CANARY_MIN_VERIFIED,
                                                 "wilson_lower": CANARY_MIN_WILSON, "z": WILSON_Z},
                           "BOUNDED_AUTONOMY": ABOVE_CEILING, "MANAGE_BY_EXCEPTION": ABOVE_CEILING},
            "grants": "none: a level is a report; every action still needs its light cone, its exact-scope approvals "
                      "and the Gate, whatever its tuple has earned",
            "tuples": tuples}


def _needs(level: str, evidence: dict) -> str:
    if level == "SHADOW":
        return f"{RECOMMENDER_MIN_VERIFIED} appraiser-verified run since the latest failure"
    if level == "RECOMMENDER":
        return (f"{CANARY_MIN_VERIFIED} appraiser-verified runs since the latest failure (has "
                f"{evidence['verified_since_last_failure']}) and a Wilson lower bound of at least {CANARY_MIN_WILSON} "
                f"(has {evidence['wilson_lower']})")
    return ABOVE_CEILING
