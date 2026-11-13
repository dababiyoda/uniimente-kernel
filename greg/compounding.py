"""Retained-capability compounding: a later, different mission is cheaper because an earlier one formed a capability.

The founder's test (Goal Set, 2026-10-22, re-sent 2026-11-04 and 2026-11-05):

    "First: GREG independently completes a substantial, authorized, real-world mission, including unexpected
    problems, without you manually managing every step. Second: GREG subsequently completes a different mission
    measurably better because of a capability it developed, verified and retained during the first."

The path counts the first half's formation (N2, ``greg.path.genesis_closure``) and ratified SOP runs (N4, ``greg.sop``).
This module measures the second half from the ledger alone, and only that. It is the runtime counterpart of the
pre-registered laboratory experiment ``scripts/greg_transfer_eval.py`` (#213): that harness showed transfer under
controlled arms; this reads it on any body's own ledger, including the founder's.

* **Formed in A.** Mission A opened a deficit for a function, and a capability that is not built in passed
  verification under that deficit. It then served A in one of two ways: Genesis resolved the deficit with it, or it
  waited for the founder, who attached it (the Mind's constructions and anything outside auto-attach scope; the
  attach is the formation point). A was appraised VERIFIED after that, with every check the SOP observer requires.
  A re-attach of a capability verified elsewhere develops nothing and is not a formation.
* **Reused by B.** A later mission B, registered after the formation, used that capability in a passing, receipted
  observation or a DONE action before its own VERIFIED appraisal. A use through the Mind names ``cognition.solve``;
  the formed construction that answered is read from the receipt (``method_or_composition_selected``), together with
  each engine the construction is built on. B opened no deficit of its own for the function, at least one use came
  before any quarantine or detach, and a use is credited only to the latest formation before it.
* **Different.** B is not the same problem asked again: its signed content, with the mission id, horizon and
  provenance masked, differs from A's. Each credited row says whether B ran the same procedure on new inputs or a
  different procedure (``relation``).
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


def _engines(journal: Journal) -> dict:
    """capability_id -> the engine a construction is reduced onto (manifest provenance ``target_capability_id``)."""
    out = {}
    for event in journal.replay("capability.registered"):
        manifest = event.payload.get("manifest") or {}
        target = (manifest.get("provenance") or {}).get("target_capability_id")
        if manifest.get("capability_id") and isinstance(target, str):
            out[manifest["capability_id"]] = target
    return out


def _served_by(journal: Journal, data: dict, engines: dict) -> set:
    """Every capability one use exercised: the one it named, the method the Mind's receipt says it selected, and
    each engine that method is built on. Through the Mind, a mission names only ``cognition.solve``; the formed
    construction that answered is in the receipt (``method_or_composition_selected``)."""
    served = {data["capability"]}
    record = journal.ledger.find(data["receipt"])
    output = ((record.payload.get("result") or {}).get("output") if record is not None else None)
    method = output.get("method_or_composition_selected") if isinstance(output, dict) else None
    while isinstance(method, str) and method not in served:
        served.add(method)
        method = engines.get(method)
    return served


def _uses(journal: Journal, seq: dict, engines: dict | None = None) -> dict:
    """mission_id -> [(capability, ledger seq)] of every successful, receipted observation and DONE action.

    An observation counts only when it passed and carries no failure class: a failed or transient reading of the
    capability did not serve the mission (review of 2026-11-05, R3)."""
    engines = _engines(journal) if engines is None else engines
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
            for capability in sorted(_served_by(journal, data, engines)):
                used.setdefault(data["mission_id"], []).append((capability, seq[event.event_id]))
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
    awaiting = sop.awaiting_appraisal(journal)      # appraised again when the founder attaches what was not run
    rejected = {e.payload.get("mission_id") for e in journal.replay("mission.appraised")} - set(verified) - awaiting
    registered = {e.payload["mission_id"]: (e.payload.get("spec") or {}, seq[e.event_id])
                  for e in journal.replay("mission.registered") if e.payload.get("mission_id")}
    opened = {e.payload["deficit_id"]: e.payload for e in journal.replay("deficit.opened")
              if e.payload.get("deficit_id")}
    own_deficits = {(d.get("mission_id"), d.get("function")) for d in opened.values()}
    builds, checks = {}, {}
    for e in journal.replay("genesis.built"):
        builds.setdefault(e.payload.get("deficit_id"), []).append(e.payload)
    for e in journal.replay("genesis.verified"):
        checks.setdefault(e.payload.get("deficit_id"), []).append((e.payload, seq[e.event_id]))
    unusable, attaches = {}, []
    for e in journal.replay("capability.state"):
        if e.payload.get("state") in UNUSABLE:
            unusable.setdefault(e.payload.get("capability_id"), []).append(seq[e.event_id])
        elif e.payload.get("state") == "ATTACHED":
            attaches.append((e.payload.get("capability_id"), seq[e.event_id], e.occurred_at))
    uses = _uses(journal, seq)

    def developed(did, cid):
        return any(c.get("passed") is True and _same_capability(c.get("capability_id"), cid)
                   for c, _ in checks.get(did, []))

    # A formation is (mission, capability, deficit, ledger point, time). Two routes reach it:
    #  * Genesis resolves A's deficit with a capability verified under it (auto-attach, builder, package);
    #  * a capability verified under A's deficit waits for the founder, who attaches it (the Mind's constructions,
    #    anything outside auto-attach scope). The attach is the formation point; no resolution is recorded.
    by_deficit = {}
    for event in journal.replay("deficit.resolved"):
        res = event.payload
        a, cid, did = res.get("mission_id"), res.get("capability_id"), res.get("deficit_id")
        deficit = opened.get(did)
        if not deficit or deficit.get("mission_id") != a or cid in BUILTINS or not developed(did, cid):
            continue
        by_deficit.setdefault(did, (a, cid, did, deficit, seq[event.event_id], res.get("at")))
    for did, deficit in opened.items():
        if did in by_deficit:
            continue
        for check, checked_at in checks.get(did, []):
            if check.get("passed") is not True:
                continue
            attached = [(cid, at, when) for cid, at, when in attaches
                        if at > checked_at and cid not in BUILTINS and _same_capability(check.get("capability_id"), cid)]
            if attached:
                cid, at, when = min(attached, key=lambda x: x[1])
                by_deficit[did] = (deficit.get("mission_id"), cid, did, deficit, at, when)
                break
    resolutions = sorted(by_deficit.values(), key=lambda r: r[4])
    resolved_ids = {e.payload.get("deficit_id") for e in journal.replay("deficit.resolved")}
    formations = {}
    for _, cid, _, _, at, _ in resolutions:
        formations.setdefault(cid, []).append(at)

    formed, reuses, refused = [], [], []
    for a, cid, did, deficit, at, formed_when in resolutions:
        if a not in verified or verified[a] < at:          # A's verdict must come after A had the capability
            continue
        function = deficit.get("function")
        costs = [b.get("cost_usd") for b in builds.get(did, [])]
        cost = {"builder_calls": len(costs),
                "build_cost_usd": round(sum(c for c in costs if _is_cost(c)), 6),
                "build_cost_known": all(_is_cost(c) for c in costs),
                "verifications": len(checks.get(did, [])),
                "founder_attach": formed_when is not None and did not in resolved_ids,
                "blocked_seconds": _seconds(deficit.get("at"), formed_when)}
        formed.append({"mission_id": a, "capability_id": cid, "function": function, "acquisition": cost})
        shape_a = _shape(registered[a][0]) if a in registered else None
        content_a = _content(registered[a][0]) if a in registered else None
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
                why.append("not appraised VERIFIED" + (
                    " (appraisal rejected it)" if b in rejected else
                    " (not yet appraised: a capability its appraisal needs is not attached)" if b in awaiting else ""))
            else:
                hits = [s for s in hits if s < verified[b]]   # only uses that could serve B's verdict
                if not hits:
                    why.append("used the capability only after its verdict")
            if (b, function) in own_deficits:
                why.append(f"opened its own deficit for {function}")
            if hits and all(any(at < u < s for u in unusable.get(cid, [])) for s in hits):
                why.append("the capability was quarantined or detached before this use")
            if content_a is not None and b in registered and _content(registered[b][0]) == content_a:
                why.append("the same problem asked again (a replay), not a different mission")
            row = {"formed_in": a, "reused_in": b, "capability_id": cid, "function": function}
            if b in registered and shape_a is not None:
                row["relation"] = ("same procedure, new inputs" if _shape(registered[b][0]) == shape_a
                                   else "different procedure")
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


def _content(spec: dict) -> str | None:
    """Digest of a signed mission with its identity, horizon and provenance masked: equal means the same problem asked
    again (a replay), whatever the mission id."""
    from greg import sop
    from provenance.ledger import sha256_json
    try:
        return sha256_json([[list(path), value] for path, value in sop._leaves(spec) if not sop._masked(path)]) \
            if spec else None
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
