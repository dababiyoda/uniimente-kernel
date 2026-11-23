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
     mission's own loop judged it (the ``routing.outcome`` ``ineffective`` record the engine writes). A run the
     founder reconciled as executed has no receipt, so the engine writes no such record for it; its effect is read
     from the observations after it, as the mission fold reads them.

   Each regression is recorded first as ``autonomy.regressed`` (the evidence), then as the withdrawal. Only approvals
   asked before the failed run are withdrawn, so an approval the founder gives after the regression stands. A
   withdrawal narrows authority; it never widens it. A live mission only: a closed one selects nothing more.

2. ``report``: a read-only fold of the journal per (capability, action class, target pattern, budget band). It names
   the level the evidence has earned: SHADOW, RECOMMENDER or SUPERVISED_CANARY, by the thresholds below. A refuted or
   ineffective run drops the tuple back at once: only verified runs after the latest such run count towards a level.
   Runs are ordered by where each run itself sits on the ledger, not by when its verdict was recorded (an appraisal
   retried after an unavailable run lands late). A run the founder reconciled as executed is counted apart and never
   verified (no Gate receipt shows it), but failure evidence naming it counts like any other. A regression always
   names a run that ``failures`` names, which the fold already counts as refuted or ineffective at that run's place,
   so it is counted but drops nothing a second time. Compensations (``mission.compensation_required``, closed by
   ``mission.compensated``) are counted against the run's tuple, never judged: the mission ended, which does not show
   the run failed. BOUNDED_AUTONOMY and MANAGE_BY_EXCEPTION are never earned from evidence: they would need a
   founder-signed grant, which does not exist (NEEDS_FOUNDER_DECISION). A level changes nothing: every action still
   needs its light cone, its exact-scope approvals and the Gate.

Limits: a strategy the founder pre-approved inside the signed mission (``pre_approved_steps``) is part of the signed
mission and is not withdrawn here. A capability failure (a REFUSED receipt) counts against the level but does not
regress an approval: the mission's loop already keeps that strategy out of selection. An approval already standing on
a body when this code first runs is regressed by the failure evidence already on its ledger.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
import math

from greg.capabilities import BUILTINS
from greg.journal import fact_id, iso
from greg.missions import TERMINAL, blames_strategy
from greg.routing import founder_reconciled

LEVELS = ("SHADOW", "RECOMMENDER", "SUPERVISED_CANARY", "BOUNDED_AUTONOMY", "MANAGE_BY_EXCEPTION")
EARNED_CEILING = "SUPERVISED_CANARY"    # the highest level evidence alone reaches
RECOMMENDER_MIN_VERIFIED = 1            # verified runs since the latest failure
CANARY_MIN_VERIFIED = 5
CANARY_MIN_WILSON = 0.5                 # Wilson lower bound of the verified share of every judged run
WILSON_Z = 1.96
BUDGET_BANDS = ((0.0, "$0"), (1.0, "up to $1"), (10.0, "up to $10"), (100.0, "up to $100"))
SEVERE = ("refuted", "ineffective")
TUPLE = ("capability", "action_class", "target_pattern", "budget_band")
ABOVE_CEILING = ("needs a founder-signed grant for this exact tuple; no such grant exists yet "
                 "(NEEDS_FOUNDER_DECISION), so no evidence reaches it")


def _closure_windows(journal, pos) -> dict:
    """appraisal event id -> (mission id, verdict, window start, closure position, appraisal position), as
    greg/appraisal.py windows a closure: from the registration or the mission's previous hold to the closure the
    appraisal names. One pass over the marks in ledger order, so a long standing history costs n log n, not n^2."""
    marks = sorted((pos.get(e.event_id, -1), e.event_id, kind, e.payload.get("mission_id"))
                   for kind in ("mission.registered", "mission.held", "mission.achieved", "mission.unmet")
                   for e in journal.replay(kind))
    opened, closures, achieved = {}, {}, {}
    for at, eid, kind, mid in marks:
        if kind != "mission.registered" and mid in opened:     # a closure: its window opened at the latest start
            closures[eid] = (mid, opened[mid], at)
            if kind == "mission.achieved":
                achieved.setdefault(mid, eid)    # a bounded mission's appraisal names no closure: its achievement
        if kind in ("mission.registered", "mission.held"):
            opened[mid] = at
    windows = {}
    for e in journal.replay("mission.appraised"):
        p = e.payload
        closure = closures.get(p["closure_event"] if p.get("closure_event") else achieved.get(p.get("mission_id")))
        if closure is not None and closure[0] == p.get("mission_id"):
            mid, start, at = closure
            windows[e.event_id] = (mid, p.get("verdict"), start, at, pos.get(e.event_id, -1))
    return windows


def failures(journal) -> list[dict]:
    """Every completed run that failure evidence names, with that evidence (``refuted`` or ``ineffective``)."""
    pos = journal.positions("")
    runs = [e for e in journal.replay("mission.action") if e.payload.get("status") == "DONE"]
    by_receipt = {e.payload["receipt"]: e for e in runs if e.payload.get("receipt")}
    own = {}                            # mission id -> its completed runs and their positions, in ledger order
    for e in runs:
        mine = own.setdefault(e.payload["mission_id"], ([], []))
        mine[0].append(pos.get(e.event_id, -1))
        mine[1].append(e)
    out = []
    for e in journal.replay("routing.outcome"):
        p = e.payload
        run = by_receipt.get(p.get("receipt"))
        if p.get("verdict") == "ineffective" and run is not None \
                and (run.payload["mission_id"], run.payload["action_id"]) == (p.get("mission_id"), p.get("action_id")):
            out.append({"kind": "ineffective", "run": run, "evidence": e.event_id, "at": pos.get(e.event_id, -1),
                        "why": f"it executed and the check it advances still failed ({str(p.get('reason'))[:160]})"})
    out += _reconciled_ineffective(journal, pos, runs, own)
    for appraisal, (mid, verdict, start, closure, at) in _closure_windows(journal, pos).items():
        if verdict != "REFUTED" or mid not in own:
            continue
        ats, ran = own[mid]             # the runs strictly inside the window: after its start, before its closure
        for run in ran[bisect_right(ats, start):bisect_left(ats, closure)]:
            out.append({"kind": "refuted", "run": run, "evidence": appraisal, "at": at,
                        "why": "the independent appraisal refuted the closure this run belongs to"})
    return sorted(out, key=lambda f: (f["at"], pos.get(f["run"].event_id, -1)))


def _reconciled_ineffective(journal, pos, runs, own) -> list[dict]:
    """The founder-reconciled runs the mission's own loop judged ineffective.

    The engine writes ``routing.outcome`` for a receipted run only: a reconciliation has no receipt and never moves
    routing. Its effect is still judged, as the mission fold judges any DONE run: each check the strategy advances is
    decided by its first observation after the run (before the strategy's next run) that passed or measured the
    world. A measured failure there is the fold's "executed but ... still failing", read through the engine's own
    ``blames_strategy``. A strategy whose output another strategy binds is done, not ineffective, as in the fold.
    The fold's one other exception (a run already blamed for damaging another check) is not followed: that run counts
    as ineffective here too, which only narrows."""
    reconciled = [e for e in runs if founder_reconciled(e.payload)]
    if not reconciled:                  # the common case costs nothing more
        return []
    specs = {e.payload["mission_id"]: e.payload.get("spec") or {} for e in journal.replay("mission.registered")}
    observed = {}                       # (mission id, check id) -> its observations and their positions, in order
    for e in journal.replay("mission.observed"):
        mine = observed.setdefault((e.payload.get("mission_id"), e.payload.get("check_id")), ([], []))
        mine[0].append(pos.get(e.event_id, -1))
        mine[1].append(e)
    out = []
    for run in reconciled:
        mid, aid = run.payload["mission_id"], run.payload["action_id"]
        strategies = specs.get(mid, {}).get("strategies", [])
        strategy = next((s for s in strategies if s.get("action_id") == aid), None)
        if strategy is None or any(b.get("from", {}).get("action_id") == aid
                                   for s in strategies for b in s.get("bind", [])):
            continue
        ats, ran = own[mid]
        at = pos.get(run.event_id, -1)
        end = next((ats[i] for i in range(bisect_right(ats, at), len(ats)) if ran[i].payload["action_id"] == aid),
                   None)                # the strategy's next run sets its pending effect afresh
        blamed = []
        for check in strategy.get("advances", []):
            seen, obs = observed.get((mid, check), ((), ()))
            for i in range(bisect_right(seen, at), len(seen)):
                if end is not None and seen[i] > end:
                    break
                o = obs[i].payload
                if o.get("passed"):
                    break
                reason = f"executed but {check} still failing: {o.get('detail')}"[:300]
                if blames_strategy(reason):
                    blamed.append((seen[i], obs[i].event_id, reason))
                    break               # an unmeasured read decides nothing: the next observation does
        if blamed:
            seen_at, evidence, reason = min(blamed)
            out.append({"kind": "ineffective", "run": run, "evidence": evidence, "at": seen_at,
                        "why": "the founder reconciled it as executed and the check it advances still failed "
                               f"({reason[:160]})"})
    return out


def regress(journal, book, now) -> list[dict]:
    """Withdraw every standing approval a failed run ran under (see the module docstring); returns what it recorded.

    Called by the body before any mission selects its next action, so a regressed scope is asked about again."""
    book.rebuild()
    if not any(m.approved_scopes for m in book.missions.values() if m.status not in TERMINAL):
        return []                       # nothing stands, so nothing can fall
    pos = journal.positions("")
    asks = {}                           # (mission id, scope) -> the APPROVAL asks of that exact scope
    for rid, request in sorted(book.requests.items()):
        if request.get("kind") == "APPROVAL":
            asks.setdefault((request.get("mission_id"), request.get("scope_digest")), []).append(rid)
    recorded, handled = [], set()
    for failure in failures(journal):
        run = failure["run"].payload
        m = book.missions.get(run["mission_id"])
        scope = run.get("scope_digest")
        if m is None or m.status in TERMINAL or scope not in m.approved_scopes:
            continue
        ran_at = pos.get(failure["run"].event_id, -1)
        for rid in asks.get((m.mission_id, scope), ()):
            if ((book.answers.get(rid) or {}).get("answer") != "approve"
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
    return {"tuple": t, "strategies": 0, "asked": 0, "approved": 0, "rejected": 0, "runs": 0, "reconciled": 0,
            "verified": 0, "refuted": 0, "ineffective": 0, "failed": 0, "unappraised": 0, "regressed": 0,
            "compensation_required": 0, "compensated": 0, "compensation_open": 0, "outcomes": []}


def report(journal) -> dict:
    """The earned level of every tuple a signed strategy names, from the journal alone. Writes nothing."""
    from greg.missions import MissionBook
    book = MissionBook(journal)          # founder answers count only as re-verified from signed DECISIONs
    pos = journal.positions("")
    rows = {}

    def row(t: dict) -> dict:
        key = tuple(t[k] for k in TUPLE)
        return rows.setdefault(key, _blank(dict(zip(TUPLE, key))))

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
    judging = {}                        # mission id -> (closure positions, windows) of its appraised closures
    for w in sorted(_closure_windows(journal, pos).values(), key=lambda w: w[3]):
        at_closure, own = judging.setdefault(w[0], ([], []))
        at_closure.append(w[3])
        own.append(w)
    severe = {}                         # run event id -> the failure evidence naming it; ineffective outranks refuted
    for f in failures(journal):
        if severe.get(f["run"].event_id) != "ineffective":
            severe[f["run"].event_id] = f["kind"]
    for e in journal.replay("mission.action"):
        p = e.payload
        reconciled = p.get("status") == "DONE" and founder_reconciled(p)
        if not reconciled and (not p.get("receipt") or p.get("status") not in ("DONE", "REFUSED")):
            continue                    # neither a receipted run nor the founder's word that one ran
        r = strategy_row(p.get("mission_id"), p.get("action_id"), p.get("capability"))
        if r is None:
            continue
        at = pos.get(e.event_id, -1)
        if reconciled:                  # the founder says it ran; no Gate receipt shows it, so it is never verified,
            r["reconciled"] += 1        # but failure evidence naming it counts, as for any run
            kind = severe.get(e.event_id)
            if kind is not None:
                r[kind] += 1
                r["outcomes"].append((at, kind))
            continue
        if p["status"] == "REFUSED":    # the Gate ran it and the capability failed
            r["failed"] += 1
            r["outcomes"].append((at, "failed"))
            continue
        r["runs"] += 1
        # failure evidence first (an ineffective run's closure may still verify: the run itself changed nothing);
        # otherwise the first appraised closure whose window holds it judges it. Window starts never fall as closures
        # climb, so that is the first closure after the run, if its window opened before the run. An unmet or
        # unavailable closure judges nothing.
        kind, judged = severe.get(e.event_id), None
        closures, windows = judging.get(p["mission_id"], ((), ()))
        if kind is None:
            i = bisect_right(closures, at)
            judged = windows[i] if i < len(windows) and windows[i][2] < at else None
            kind = "verified" if judged is not None and judged[1] == "VERIFIED" else None
        if kind is None:
            r["unappraised"] += 1
            continue
        r[kind] += 1
        r["outcomes"].append((at, kind))  # the run's own place: runs in the order they ran, not their verdicts' order
    # A compensation is counted, not judged: the mission ended (abandoned or superseded), which does not show the run
    # failed. compensated: undone through the Gate, or the founder decided; open: neither yet.
    closed = {(e.payload.get("mission_id"), e.payload.get("action_id")): e.payload.get("status")
              for e in journal.replay("mission.compensated")}
    for e in journal.replay("mission.compensation_required"):
        p = e.payload
        r = strategy_row(p.get("mission_id"), p.get("action_id"), p.get("capability"))
        if r is None:
            continue
        r["compensation_required"] += 1
        settled = closed.get((p.get("mission_id"), p.get("action_id"))) in ("DONE", "FOUNDER_DECIDED")
        r["compensated" if settled else "compensation_open"] += 1
    for e in journal.replay("autonomy.regressed"):
        # counted against the run it names, which the fold above already counts as refuted or ineffective
        t = e.payload.get("tuple") if isinstance(e.payload.get("tuple"), dict) else {}
        r = strategy_row(e.payload.get("mission_id"), e.payload.get("action_id"), t.get("capability"))
        if r is not None:
            r["regressed"] += 1
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
