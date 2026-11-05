"""Retained-capability compounding: a later, different mission is cheaper because an earlier one formed a capability.

The founder's test (Goal Set, 2026-10-22, re-sent 2026-11-04 and 2026-11-05):

    "First: GREG independently completes a substantial, authorized, real-world mission, including unexpected
    problems, without you manually managing every step. Second: GREG subsequently completes a different mission
    measurably better because of a capability it developed, verified and retained during the first."

The path counts the first half's formation (N2, ``greg.path.genesis_closure``) and reruns of one procedure
(N4, ``greg.sop``). This module measures the second half from the ledger alone, and only that:

* **Formed in A.** Mission A opened a deficit for a function, Capability Genesis resolved it with a capability
  that is not built in, and A was then appraised VERIFIED with every check the SOP observer requires.
* **Reused by B.** A later mission B was registered after that resolution. B used *the same* capability in a
  receipted observation or action and was appraised VERIFIED. B opened no deficit of its own for that function.
  The capability was not quarantined, detached or re-formed between A's resolution and B's use.
* **Different.** B is not a run of A's procedure: its signed shape (``greg.sop.shape``, what must be identical
  across runs of one procedure) differs from A's. A rerun is N4's business, not this test's.
* **Measurably better.** What A paid to have the function is priced from A's own records: the builder calls
  and their booked cost, the verifications, and the time the mission stood blocked on the deficit. B paid
  none of it for that function, and that difference is the gain. It is attributed only when B used the
  capability; it is never extrapolated to missions that did not.

What it does not establish: that B could not have obtained the function some other way, or that the outcome
mattered in the world. The counterfactual run (B alone on a body that never formed the capability) is evidence
kept beside this measure (docs/evidence/retained-capability-compounding/), not something a ledger can show.
Read-only; it records nothing, grants nothing and moves no money. Like every path predicate, a reuse counts for
the founder only when both missions are at the founder tier (``greg.path._at_founder_tier``).
"""
from __future__ import annotations

from datetime import datetime

from greg.journal import Journal

UNUSABLE = ("QUARANTINED", "DETACHED")


def _instant(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _seconds(start, end):
    a, b = _instant(start), _instant(end)
    return None if a is None or b is None else max(0.0, round((b - a).total_seconds(), 3))


def _uses(journal: Journal, seq: dict) -> dict:
    """mission_id -> [(capability, ledger seq)] of every successful, receipted observation and DONE action.

    An observation counts only when it passed and carries no failure class: a failed or transient reading of the
    capability did not serve the mission (review of 2026-11-05, R3)."""
    used = {}
    for kind in ("mission.observed", "mission.action"):
        for event in journal.replay(kind):
            data = event.payload
            if not data.get("capability") or not data.get("receipt") or not data.get("mission_id"):
                continue
            if kind == "mission.action" and data.get("status") != "DONE":
                continue
            if kind == "mission.observed" and (data.get("passed") is not True or data.get("failure_class")):
                continue
            used.setdefault(data["mission_id"], []).append((data["capability"], seq[event.event_id]))
    return used


def _is_cost(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _same_capability(verified_id, resolved_id) -> bool:
    """A verification names the candidate (``built:<digest>``); the attached manifest is ``built.<fn>.<digest[:12]>``."""
    if not isinstance(verified_id, str) or not isinstance(resolved_id, str):
        return False
    if verified_id == resolved_id:
        return True
    return verified_id.startswith("built:") and resolved_id.endswith("." + verified_id[len("built:"):][:12])


def retained_reuse(journal: Journal) -> dict:
    """Every (A, B) pair in which a different, later mission reused a capability A formed, priced.

    A formation is a deficit A opened and resolved with a capability that passed verification *under that
    deficit*. Re-attaching an already-verified capability (Genesis rung ``verified_detached``, or Goal Gravity
    serving a function with an attached implementation) resolves a deficit but develops nothing, so it is not a
    formation, and it never takes a later use away from the mission that did develop it (review R1). A capability
    attached by the founder's command after waiting in ``deficit.awaiting_attach`` has no resolution record and is
    not seen, as in N2's ``genesis_closure``: the measure under-credits rather than over-credits."""
    from greg import sop
    from greg.capabilities import BUILTINS
    seq = {r.payload.get("event_id"): r.seq for r in journal.ledger.by_type("event")}
    verified = {mid: seq[eid] for mid, eid in sop.verified_appraisals(journal).items() if eid in seq}
    rejected = {e.payload.get("mission_id") for e in journal.replay("mission.appraised")} - set(verified)
    registered = {e.payload["mission_id"]: (e.payload.get("spec") or {}, seq[e.event_id])
                  for e in journal.replay("mission.registered") if e.payload.get("mission_id")}
    opened = {e.payload["deficit_id"]: e.payload for e in journal.replay("deficit.opened")
              if e.payload.get("deficit_id")}
    own_deficits = {(d.get("mission_id"), d.get("function")) for d in opened.values()}
    builds, checks = {}, {}
    for e in journal.replay("genesis.built"):
        builds.setdefault(e.payload.get("deficit_id"), []).append(e.payload)
    for e in journal.replay("genesis.verified"):
        checks.setdefault(e.payload.get("deficit_id"), []).append(e.payload)
    unusable = {}
    for e in journal.replay("capability.state"):
        if e.payload.get("state") in UNUSABLE:
            unusable.setdefault(e.payload.get("capability_id"), []).append(seq[e.event_id])
    uses = _uses(journal, seq)

    def developed(did, cid):
        return any(c.get("passed") is True and _same_capability(c.get("capability_id"), cid)
                   for c in checks.get(did, []))

    resolutions = []
    for event in journal.replay("deficit.resolved"):
        res = event.payload
        a, cid, did = res.get("mission_id"), res.get("capability_id"), res.get("deficit_id")
        deficit = opened.get(did)
        if not deficit or deficit.get("mission_id") != a or cid in BUILTINS or not developed(did, cid):
            continue
        resolutions.append((event, res, deficit, seq[event.event_id]))
    formations = {}
    for _, res, _, at in resolutions:
        formations.setdefault(res["capability_id"], []).append(at)

    formed, reuses, refused = [], [], []
    for event, res, deficit, at in resolutions:
        a, cid, did = res["mission_id"], res["capability_id"], res["deficit_id"]
        if a not in verified or verified[a] < at:          # A's verdict must come after A had the capability
            continue
        function = deficit.get("function")
        costs = [b.get("cost_usd") for b in builds.get(did, [])]
        cost = {"builder_calls": len(costs),
                "build_cost_usd": round(sum(c for c in costs if _is_cost(c)), 6),
                "build_cost_known": all(_is_cost(c) for c in costs),
                "verifications": len(checks.get(did, [])),
                "blocked_seconds": _seconds(deficit.get("at"), res.get("at"))}
        formed.append({"mission_id": a, "capability_id": cid, "function": function, "acquisition": cost})
        shape_a = _shape(registered[a][0]) if a in registered else None
        later = [fs for fs in formations.get(cid, []) if fs > at]
        for b, used in sorted(uses.items()):
            # credited only to the latest formation of this capability before the use, never twice
            hits = [s for c, s in used if c == cid and s > at and not any(fs < s for fs in later)]
            if b == a or not hits:
                continue
            why = []
            if a not in registered or b not in registered:
                why.append("a mission of the pair has no registration on this ledger")
            elif registered[b][1] < at:
                why.append("registered before the capability was formed")
            if b not in verified:
                why.append("not appraised VERIFIED" + (" (appraisal rejected it)" if b in rejected else ""))
            else:
                hits = [s for s in hits if s < verified[b]]   # only uses that could serve B's verdict
                if not hits:
                    why.append("used the capability only after its verdict")
            if (b, function) in own_deficits:
                why.append(f"opened its own deficit for {function}")
            if hits and all(any(at < u < s for u in unusable.get(cid, [])) for s in hits):
                why.append("the capability was quarantined or detached before this use")
            if shape_a is not None and b in registered and _shape(registered[b][0]) == shape_a:
                why.append("a run of the same procedure (N4 counts reruns), not a different mission")
            row = {"formed_in": a, "reused_in": b, "capability_id": cid, "function": function}
            if why:
                refused.append({**row, "why_not": why})
                continue
            reuses.append({**row, "avoided": dict(cost),
                           "paid_in_reuse": {"builder_calls": 0, "build_cost_usd": 0.0, "verifications": 0,
                                             "blocked_seconds": 0.0, "deficits_opened": 0}})
    return {"formed": formed, "reuses": reuses, "refused": refused,
            "compounding": bool(reuses),
            "per_pair_price": "each reuse reports the whole price its formation paid; several reuses of one "
                              "formation are not to be summed as total savings",
            "reality": "measured from the ledger: a later different mission used a capability an earlier one formed, "
                       "and paid none of the earlier acquisition; that it could not have obtained the function "
                       "another way, and that the outcomes mattered, are not provable here. A mission that differs "
                       "from the forming one by one trivial check is 'different' by signed shape; that is a limit."}


def _shape(spec: dict) -> str | None:
    from greg import sop
    try:
        return sop.shape(spec) if spec else None
    except sop.SopError:
        return None


def capability_compounding(journal: Journal) -> dict:
    """The founder's second achievement as a tiered result: met only when both missions are founder-tier."""
    from greg import path
    measured = retained_reuse(journal)
    groups = {f"{r['formed_in']}->{r['reused_in']}": [r["formed_in"], r["reused_in"]] for r in measured["reuses"]}
    passed, refused = path._at_founder_tier(journal, groups)
    return path._tiered({"value": len(passed), "structural_value": len(measured["reuses"]), **measured},
                        structural=bool(measured["reuses"]), passed=passed, refused=refused)
