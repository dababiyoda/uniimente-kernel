"""Post-outcome disposition review: RETAIN, REPAIR, REGRESS or REMOVE, proposed and never self-applied.

Directive section 22 (S22.A4): "RETAIN / REPAIR / REGRESS / REMOVE". Every capability Capability Genesis formed on
this body (a provider ``built:``, ``installed:`` or ``composed:``, Genesis's own test) is reviewed against what
happened when it was used, and a disposition is proposed:

- **RETAIN**: every counted outcome correct and no fault in service. Recorded quietly; nothing is asked.
- **REPAIR**: a wrong outcome or an earlier in-service quarantine, short of demotion. Requalify it against the
  failing cases (or have Genesis re-form the function).
- **REGRESS**: demoted, and an earlier formed implementation of the same function stands (in no out-of-service
  state, settled, right at least as often as wrong and not itself demoted): go back to that one.
- **REMOVE**: demoted, and no earlier implementation of its function stands: detach it.

A capability while QUARANTINED is not reviewed: it is out of service, and Genesis's self-repair (which re-forms the
function) and its recovery probe decide it. Its quarantines in service count as evidence once it is back in service.

Demoted is the body's own rule, ``compiler._settled_inhibition``: at least ``SETTLED_MIN_N`` (10) counted outcomes
and a 95% Wilson upper bound of the correct share below one half, compared unrounded.

Counted outcomes are the ones ``settlement.measured_outcomes`` credits to the capability's own id (constructions,
and installed Python packages Genesis formed; settlement credits no built or binary capability, whose evidence here
is its faults in service). Once the world has judged any answer of a capability (a REALIZATION report settled it),
only world-judged outcomes count: an answer judged on its own certificate alone is *pending* until its realization
arrives, so a demoted capability is not lifted by answers nobody has checked yet. A capability none of whose answers
is ever realized counts its certificate-checked outcomes, and every proposal says which tier it rests on.

A proposal is a fact (``capability.disposition_proposed``), recorded once per capability and evidence. GREG asks the
founder (kind CAPABILITY_DISPOSITION) when the disposition changes to anything but RETAIN, or when it holds but its
earlier ask became moot unanswered (withdrawn when the founder detached it); every other open disposition ask on that
capability is withdrawn, and an answered one is never asked again for the same disposition. The answer is only
recorded: the registry changes only by the founder's own signed command (CAPABILITY_DETACH, CAPABILITY_ATTACH), never
by this module, which writes no capability state.
"""
from __future__ import annotations

from collections import defaultdict

from greg import asks
from greg.cognition.compiler import _settled_inhibition
from greg.cognition.settlement import _wilson, measured_outcomes
from greg.journal import Journal, iso
from provenance.ledger import sha256_json

FORMED = ("built:", "installed:", "composed:")   # genesis.FORMED: the providers Genesis formed and can re-form
RECOVERABLE = "failed in service"                # genesis.RECOVERABLE: the one quarantine that keeps the identity
WORLD_JUDGED = ("reported", "verdict_concordant", "adjudicated", "disputed")
COMMANDS = {"RETAIN": None,
            "REPAIR": "none to keep it in service; CAPABILITY_DETACH takes it out while its failing cases are examined",
            "REGRESS": "CAPABILITY_DETACH of this capability, then CAPABILITY_ATTACH of the earlier one",
            "REMOVE": "CAPABILITY_DETACH"}


def _formed(journal: Journal) -> tuple[list[dict], dict]:
    """Every capability Genesis formed here, in first-registration order, and each one's (state, in-service
    quarantines, latest quarantine reason). A later registration resets the state, as Genesis's restore does."""
    out, seen, state, faults, why = [], set(), {}, defaultdict(int), {}
    for event in journal.replay("capability."):
        p = event.payload
        if event.type == "greg.capability.registered":
            manifest = p.get("manifest") or {}
            cid = manifest.get("capability_id")
            if not cid or not str(manifest.get("provider", "")).startswith(FORMED):
                continue
            state[cid] = p.get("state", "VERIFIED")
            if cid not in seen:
                origin = p.get("origin") or {}
                seen.add(cid)
                out.append({"capability_id": cid, "function": origin.get("function") or manifest.get("function"),
                            "origin": origin.get("kind") or str(manifest["provider"]).split(":", 1)[0],
                            "registered_event": event.event_id})
        elif event.type == "greg.capability.state" and p.get("capability_id") in seen:
            cid = p["capability_id"]
            state[cid] = p["state"]
            if p["state"] == "QUARANTINED":
                why[cid] = str(p.get("why", ""))
                faults[cid] += why[cid].startswith(RECOVERABLE)
    return out, {cid: (state.get(cid), faults[cid], why.get(cid)) for cid in seen}


def evidence(journal: Journal) -> list[dict]:
    """Each formed capability with its counted outcomes, pending answers, faults in service and state."""
    formed, states = _formed(journal)
    if not formed:                                # nothing Genesis formed: no outcome scan on this tick
        return []
    outcomes = defaultdict(list)
    for o in measured_outcomes(journal):
        outcomes[o["method"]].append(o)
    rows = []
    for capability in formed:
        cid = capability["capability_id"]
        settled = outcomes.get(cid, [])          # in the order their observations were recorded
        judged = [o for o in settled if (o.get("world") or {}).get("state") in WORLD_JUDGED]
        counted, tier = (judged, "world") if judged else (settled, "certificate" if settled else None)
        n, k = len(counted), sum(bool(o["correct"]) for o in counted)
        state, faults, why = states[cid]
        low, high = _wilson(k, n)
        rows.append({**capability, "state": state, "in_service_quarantines": faults, "quarantine_why": why,
                     "settled": n, "correct": k, "tier": tier, "pending": len(settled) - len(judged) if judged else 0,
                     "wilson95": [low, high],
                     "outcomes": [{"appraisal_event": o["appraisal_event"], "correct": bool(o["correct"])}
                                  for o in counted]})
    return rows


def _demoted(row: dict) -> bool:
    return _settled_inhibition(row["settled"], row["correct"]) is not None


def judge(row: dict, earlier: list[dict]) -> tuple[str, str, dict | None]:
    """(disposition, why, earlier implementation to go back to) for one reviewed capability."""
    n, k = row["settled"], row["correct"]
    if _demoted(row):
        standing = [e for e in earlier if e["state"] not in ("DETACHED", "QUARANTINED") and e["settled"]
                    and 2 * e["correct"] >= e["settled"] and not _demoted(e)]
        if standing:
            back = max(standing, key=lambda e: (e["wilson95"][0], e["settled"]))
            return ("REGRESS", f"{n - k} of {n} counted outcomes wrong: demoted; {back['capability_id']}, formed "
                               f"earlier for {row['function']}, is not out of service and stands at {back['correct']} "
                               f"of {back['settled']}", back)
        return "REMOVE", f"{n - k} of {n} counted outcomes wrong: demoted, and no earlier implementation stands", None
    if k < n or row["in_service_quarantines"]:
        return ("REPAIR", f"{n - k} of {n} counted outcomes wrong and {row['in_service_quarantines']} in-service "
                          "quarantine(s), short of demotion", None)
    return "RETAIN", f"all {n} counted outcomes correct and no fault in service", None


def _ask(proposal: dict, now) -> dict:
    cid, disposition = proposal["capability_id"], proposal["disposition"]
    e, back = proposal["evidence"], proposal.get("regress_to")
    options = {"RETAIN": f"RETAIN: keep {cid} as it is (costs nothing)",
               "REPAIR": f"REPAIR: requalify {cid} against its failing cases",
               "REGRESS": f"REGRESS: detach {cid} and attach {back} again" if back else None,
               "REMOVE": f"REMOVE: detach {cid}"}
    return {"request_id": proposal["request_id"], "kind": "CAPABILITY_DISPOSITION", "mission_id": None,
            "action_id": None, "scope_digest": proposal["evidence_digest"], "capability_id": cid,
            "why_now": f"{e['settled']} counted outcomes of {cid} ({proposal['function']}, {e['tier']} tier): "
                       f"{e['correct']} correct, Wilson 95% {[round(x, 4) for x in e['wilson95']]}, "
                       f"{e['in_service_quarantines']} in-service quarantine(s), {e['pending']} answer(s) pending",
            "recommendation": f"{disposition}: {proposal['why']}",
            "alternatives": [text for text in options.values() if text],
            "evidence": e, "authority_requested": {"command": COMMANDS[disposition], "spend": "none"},
            "consequence_of_no_response": f"nothing changes: {cid} stays {e['state'] or 'as registered'}; GREG applies "
                                          "no disposition",
            "created_at": iso(now), "reality_status": "RECORDED_LOCAL_MESSAGE"}


def _asks_by_capability(journal: Journal) -> dict:
    """capability id -> its disposition asks in request order, each [request_id, recommended, status]."""
    by_id, out = {}, defaultdict(list)
    for event in journal.replay("decision."):
        p = event.payload
        if event.type == "greg.decision.requested" and p.get("kind") == "CAPABILITY_DISPOSITION":
            row = [p["request_id"], str(p.get("recommendation", "")).split(":", 1)[0], "open"]
            by_id[p["request_id"]] = row
            out[p.get("capability_id")].append(row)
        elif event.type in ("greg.decision.answered", "greg.decision.withdrawn") and p.get("request_id") in by_id:
            row = by_id[p["request_id"]]
            if row[2] == "open":
                row[2] = "answered" if event.type == "greg.decision.answered" else "withdrawn"
    return out


def _withdraw(journal: Journal, request_id: str, why: str, now) -> None:
    key = [request_id, "withdrawn"]
    if journal.retained("decision.withdrawn", key) is None:
        journal.record("decision.withdrawn", {"request_id": request_id, "mission_id": None, "why": why[:400],
                                              "at": iso(now)}, key=key)


def propose(journal: Journal, now) -> list[dict]:
    """Record the disposition of every reviewed formed capability whose evidence changed; ask when it changes."""
    rows, recorded = evidence(journal), []
    proposed = defaultdict(list)
    for event in journal.replay("capability.disposition_proposed"):
        proposed[event.payload["capability_id"]].append(event.payload)
    asked = _asks_by_capability(journal)
    for i, row in enumerate(rows):
        cid = row["capability_id"]
        before = proposed[cid][-1] if proposed[cid] else None
        open_ids = [r[0] for r in asked[cid] if r[2] == "open"]
        if row["state"] == "DETACHED":                # the founder already acted: an open disposition ask is moot
            for rid in open_ids:
                _withdraw(journal, rid, f"the founder detached {cid}", now)
            continue
        if row["state"] == "QUARANTINED":
            continue      # out of service: Genesis's own repair and recovery decide it; its faults count once back
        if not row["settled"] and not row["in_service_quarantines"]:
            continue                                  # no outcome and no fault yet: nothing to review
        earlier = [r for r in rows[:i] if r["function"] == row["function"]]
        disposition, why, back = judge(row, earlier)
        digest = sha256_json({"capability_id": cid, "disposition": disposition,
                              "evidence": {k: row[k] for k in ("state", "in_service_quarantines", "settled", "correct",
                                                               "tier", "outcomes")},
                              "regress_to": back and back["capability_id"]})
        if before and before["evidence_digest"] == digest:      # nothing changed since the latest review
            continue
        ordinal = len(proposed[cid])
        changed = before is None or before["disposition"] != disposition
        latest = asked[cid][-1] if asked[cid] else None
        if disposition == "RETAIN":
            keep, asking = None, False
        elif changed:
            keep, asking = None, True
        elif open_ids:
            keep, asking = open_ids[-1], False
        else:                     # the same disposition: ask again only if its earlier ask became moot unanswered
            keep, asking = None, latest is None or latest[2] == "withdrawn"
        request_id = "disposition-" + sha256_json({"capability_id": cid, "ordinal": ordinal, "digest": digest})[7:31] \
            if asking else keep
        proposal = {"capability_id": cid, "function": row["function"], "origin": row["origin"],
                    "disposition": disposition, "why": why, "evidence_digest": digest,
                    "evidence": {k: row[k] for k in ("state", "in_service_quarantines", "settled", "correct", "tier",
                                                     "pending", "wilson95", "outcomes")},
                    **({"regress_to": back["capability_id"]} if back else {}),
                    "request_id": request_id,          # the disposition ask open on this capability, if any
                    "applies_by": COMMANDS[disposition] and f"the founder's signed command: {COMMANDS[disposition]}",
                    "applied": False, "authority_created": False,
                    "evidence_level": f"{row['tier'] or 'no'}-tier outcomes of locally reobserved, separately "
                                      "appraised answers, and faults in service; external outcome unproven"}
        # Withdrawals and the ask first, each recorded once; the proposal fact last marks the review done, so a
        # crash in between repeats neither, and an ask orphaned by a crash is withdrawn by the next review.
        for rid in open_ids:
            if rid != request_id:
                _withdraw(journal, rid, f"superseded: the disposition of {cid} is now {disposition} on new evidence",
                          now)
        if asking and journal.retained("decision.requested", request_id) is None:
            asks.record(journal, _ask(proposal, now))
        journal.record("capability.disposition_proposed", proposal, key=[cid, ordinal, digest])
        recorded.append(proposal)
    return recorded
