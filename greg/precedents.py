"""A bounded GREG sensor over the existing institutional ledger and mission appraisals.

No index or second memory store. A prior action's Gate outcome remains a
self-report; a local separate-process appraisal belongs to the mission, not to
that action. Neither is independent external proof or a causal estimate.
"""
from __future__ import annotations

from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from greg.sop import verified_appraisals
from memory.causal import CausalMemory

MAX_EXAMPLES = 10


def precedents(params: dict, ctx: InvocationContext) -> dict:
    if set(params) != {"capability"} or not isinstance(params["capability"], str):
        raise CapabilityError("memory query requires exactly one capability")
    capability = params["capability"]
    if capability not in BUILTINS or capability == "memory.precedents":
        raise CapabilityError("memory query requires a known non-memory capability")
    if ctx.manifest.capability_id != "memory.precedents" or ctx.target != f"memory:{capability}":
        raise CapabilityError("memory query must match its signed capability target")
    if ctx.journal is None:
        raise CapabilityError("institutional memory is unavailable")

    ledger = ctx.journal.ledger
    ok, why = ledger.verify_chain()
    if not ok:
        raise CapabilityError(f"institutional history failed integrity check: {why}")
    actions = CausalMemory(ledger).precedents("greg." + capability)
    counts = {}
    for action in actions:
        status = action.get("validation_status") or "unknown"
        result = action.get("result_class") or "unknown"
        counts.setdefault(status, {}).setdefault(result, 0)
        counts[status][result] += 1
    # Only bounded metadata; never disclose mission text, targets, receipts or payloads.
    examples = [{field: action.get(field) for field in
                 ("action_id", "result_class", "validation_status", "recorded_at", "witness_id", "policy_version")}
                for action in actions[-MAX_EXAMPLES:]]

    appraisals = verified_appraisals(ctx.journal)
    achieved = {e.payload["mission_id"] for e in ctx.journal.replay("mission.achieved")}
    relevant = {e.payload["mission_id"] for e in ctx.journal.replay("mission.action")
                if e.payload.get("capability") == capability and e.payload.get("status") == "DONE"}
    local = [{"mission_id": mid, "appraisal_event": appraisals[mid]}
             for mid in sorted(achieved & relevant & appraisals.keys())]
    return {"capability": capability,
            "action_evidence": {"count": len(actions), "by_validation_and_result": counts,
                                "recent": examples, "shown": len(examples)},
            "locally_appraised_missions": local[-MAX_EXAMPLES:],
            "locally_appraised_mission_count": len(local),
            "limitations": "Action outcomes are self-reports unless separately evidenced. "
                           "Mission appraisals are local; no external verification or causal effect is inferred."}
