"""Post-outcome disposition review: RETAIN, REPAIR, REGRESS or REMOVE, proposed and never self-applied.

Directive section 22 (S22.A4): "RETAIN / REPAIR / REGRESS / REMOVE". After real settled outcomes, each capability
Capability Genesis formed on this body (acquired, constructed or built) is reviewed against what happened when it was
used, and a disposition is proposed:

- **RETAIN**: every settled outcome correct and no fault in service. Recorded quietly; nothing is asked.
- **REPAIR**: a wrong outcome or an in-service quarantine, short of the demotion bound. Requalify it against the
  failing cases (or have Genesis re-form the function).
- **REGRESS**: demoted, and an earlier formed implementation of the same function is not: go back to that one.
- **REMOVE**: demoted, and no earlier implementation of its function stands: detach it.

Demoted means the settlement module's own rule: the 95% Wilson upper bound of its correct share is below 1/2, so
four wrong settled outcomes in a row are needed before REGRESS or REMOVE is proposed. Outcomes are the ones
``settlement.measured_outcomes`` credits to the capability's own id (its constructions' certified answers and the
formed mechanisms it pinned); a capability with no settled outcome yet is not reviewed.

A proposal is a fact (``capability.disposition_proposed``), recorded once per capability, disposition and evidence.
When the disposition changes to anything but RETAIN, GREG asks the founder (kind CAPABILITY_DISPOSITION) and
withdraws its earlier disposition ask on that capability. The answer is only recorded: the registry changes only by
the founder's own signed command (CAPABILITY_DETACH, CAPABILITY_ATTACH), never by this module, which writes no
capability state.
"""
from __future__ import annotations

from collections import defaultdict

from greg import asks
from greg.cognition.settlement import _wilson, measured_outcomes
from greg.journal import Journal, iso
from provenance.ledger import sha256_json

FORMED = ("package", "composed", "built")     # Genesis origins: acquired, constructed by reduction, built
DEMOTION_BOUND = 0.5                          # the settlement module's demotion: Wilson upper bound below 1/2
COMMANDS = {"RETAIN": None,
            "REPAIR": "none to keep it in service; CAPABILITY_DETACH takes it out while its failing cases are examined",
            "REGRESS": "CAPABILITY_DETACH of this capability, then CAPABILITY_ATTACH of the earlier one",
            "REMOVE": "CAPABILITY_DETACH"}


def _formed(journal: Journal) -> list[dict]:
    """Every capability Genesis formed here, first registration only, in registration order."""
    out, seen = [], set()
    for event in journal.replay("capability.registered"):
        origin, manifest = event.payload.get("origin") or {}, event.payload.get("manifest") or {}
        cid = manifest.get("capability_id")
        if origin.get("kind") in FORMED and cid and cid not in seen:
            seen.add(cid)
            out.append({"capability_id": cid, "function": origin.get("function") or manifest.get("function"),
                        "origin": origin["kind"], "registered_event": event.event_id})
    return out


def _states(journal: Journal) -> dict:
    """capability id -> (latest state, number of in-service quarantines) from the capability state facts."""
    latest, faults = {}, defaultdict(int)
    for event in journal.replay("capability.state"):
        p = event.payload
        latest[p["capability_id"]] = p["state"]
        if p["state"] == "QUARANTINED" and str(p.get("why", "")).startswith("failed in service"):
            faults[p["capability_id"]] += 1
    return {cid: (latest.get(cid), faults[cid]) for cid in set(latest) | set(faults)}


def evidence(journal: Journal) -> list[dict]:
    """Each formed capability with its settled outcomes, its faults in service and its earlier rivals."""
    formed = _formed(journal)
    if not formed:                                # nothing Genesis formed: no outcome scan on this tick
        return []
    outcomes = defaultdict(list)
    for o in measured_outcomes(journal):
        outcomes[o["method"]].append(o)
    states, rows = _states(journal), []
    for capability in formed:
        cid = capability["capability_id"]
        settled = outcomes.get(cid, [])          # in the order their observations were recorded
        n, k = len(settled), sum(bool(o["correct"]) for o in settled)
        state, faults = states.get(cid, (None, 0))
        low, high = _wilson(k, n)
        rows.append({**capability, "state": state, "in_service_quarantines": faults, "settled": n, "correct": k,
                     "wilson95": [round(low, 4), round(high, 4)],
                     "outcomes": [{"appraisal_event": o["appraisal_event"], "correct": bool(o["correct"])}
                                  for o in settled]})
    return rows


def judge(row: dict, earlier: list[dict]) -> tuple[str, str, dict | None]:
    """(disposition, why, earlier implementation to go back to) for one reviewed capability."""
    n, k = row["settled"], row["correct"]
    if row["wilson95"][1] < DEMOTION_BOUND:
        standing = [e for e in earlier if e["settled"] and e["wilson95"][1] >= DEMOTION_BOUND
                    and e["state"] not in ("DETACHED", "QUARANTINED")]      # out of service is no place to go back
        if standing:
            back = max(standing, key=lambda e: (e["wilson95"][0], e["settled"]))
            return ("REGRESS", f"{n - k} of {n} settled outcomes wrong: demoted; {back['capability_id']}, formed "
                               f"earlier for {row['function']}, stands at {back['correct']} of {back['settled']}", back)
        return "REMOVE", f"{n - k} of {n} settled outcomes wrong: demoted, and no earlier implementation stands", None
    if k < n or row["in_service_quarantines"]:
        return ("REPAIR", f"{n - k} of {n} settled outcomes wrong and {row['in_service_quarantines']} in-service "
                          "quarantine(s), short of demotion", None)
    return "RETAIN", f"all {n} settled outcomes correct and no fault in service", None


def _ask(proposal: dict, now) -> dict:
    cid, disposition = proposal["capability_id"], proposal["disposition"]
    e, back = proposal["evidence"], proposal.get("regress_to")
    options = {"RETAIN": f"RETAIN: keep {cid} as it is (costs nothing)",
               "REPAIR": f"REPAIR: requalify {cid} against its failing cases",
               "REGRESS": f"REGRESS: detach {cid} and attach {back} again" if back else None,
               "REMOVE": f"REMOVE: detach {cid}"}
    return {"request_id": proposal["request_id"], "kind": "CAPABILITY_DISPOSITION", "mission_id": None,
            "action_id": None, "scope_digest": proposal["evidence_digest"], "capability_id": cid,
            "why_now": f"{e['settled']} settled outcomes of {cid} ({proposal['function']}): {e['correct']} correct, "
                       f"Wilson 95% {e['wilson95']}, {e['in_service_quarantines']} in-service quarantine(s)",
            "recommendation": f"{disposition}: {proposal['why']}",
            "alternatives": [text for text in options.values() if text],
            "evidence": e, "authority_requested": {"command": COMMANDS[disposition], "spend": "none"},
            "consequence_of_no_response": f"nothing changes: {cid} stays {e['state'] or 'as registered'}; GREG applies "
                                          "no disposition",
            "created_at": iso(now), "reality_status": "RECORDED_LOCAL_MESSAGE"}


def _withdraw(journal: Journal, request_id: str, why: str, key: list, now) -> None:
    key = [request_id, "withdrawn", *key]
    if journal.retained("decision.withdrawn", key) is None:
        journal.record("decision.withdrawn", {"request_id": request_id, "mission_id": None, "why": why[:400],
                                              "at": iso(now)}, key=key)


def propose(journal: Journal, now) -> list[dict]:
    """Record the disposition of every reviewed formed capability whose evidence changed; ask when it changes."""
    rows, recorded = evidence(journal), []
    proposed = defaultdict(list)
    for event in journal.replay("capability.disposition_proposed"):
        proposed[event.payload["capability_id"]].append(event.payload)
    withdrawn = {e.payload["request_id"] for e in journal.replay("decision.withdrawn")}
    for i, row in enumerate(rows):
        before = proposed[row["capability_id"]][-1] if proposed[row["capability_id"]] else None
        if row["state"] == "DETACHED":                # the founder already acted: an open disposition ask is moot
            if before and before.get("request_id") and before["request_id"] not in withdrawn:
                _withdraw(journal, before["request_id"], f"the founder detached {row['capability_id']}",
                          ["detached"], now)
            continue
        if not row["settled"]:                        # no real outcome yet: nothing to review
            continue
        earlier = [r for r in rows[:i] if r["function"] == row["function"]]
        disposition, why, back = judge(row, earlier)
        digest = sha256_json({"capability_id": row["capability_id"], "disposition": disposition,
                              "evidence": {k: row[k] for k in ("state", "in_service_quarantines", "settled",
                                                               "correct", "outcomes")},
                              "regress_to": back and back["capability_id"]})
        if before and before["evidence_digest"] == digest:      # nothing changed since the latest review
            continue
        changed = before is None or before["disposition"] != disposition
        asking = changed and disposition != "RETAIN"
        open_request = ("disposition-" + digest[7:31] if asking
                        else None if changed else before.get("request_id"))
        proposal = {"capability_id": row["capability_id"], "function": row["function"], "origin": row["origin"],
                    "disposition": disposition, "why": why, "evidence_digest": digest,
                    "evidence": {k: row[k] for k in ("state", "in_service_quarantines", "settled", "correct",
                                                     "wilson95", "outcomes")},
                    **({"regress_to": back["capability_id"]} if back else {}),
                    "request_id": open_request,        # the disposition ask still open on this capability, if any
                    "applies_by": COMMANDS[disposition] and f"the founder's signed command: {COMMANDS[disposition]}",
                    "applied": False, "authority_created": False,
                    "evidence_level": "settled outcomes of locally reobserved, separately appraised answers; "
                                      "external outcome unproven"}
        # The ask and the withdrawal first, each recorded once; the proposal fact last marks the review done, so a
        # crash in between repeats neither on the next tick.
        if changed and before and before.get("request_id"):   # the earlier ask no longer says what the evidence says
            _withdraw(journal, before["request_id"], f"superseded: the disposition of {row['capability_id']} is now "
                                                     f"{disposition} on new evidence", [digest], now)
        if asking and journal.retained("decision.requested", open_request) is None:
            asks.record(journal, _ask(proposal, now))
        journal.record("capability.disposition_proposed", proposal,
                       key=[row["capability_id"], len(proposed[row["capability_id"]]), digest])
        recorded.append(proposal)
    return recorded
