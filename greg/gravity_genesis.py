"""Route egregore Goal Gravity capability deficits into GREG Capability Genesis (acceptance C.G11).

An egregore ``GoalGravityLoop`` goal whose active plan node requires a function the repertoire lacks records an
``egregore.capability_deficit`` (disposition ``goal_blocked_not_closed``) and WAITs. Before this adapter nothing read
that record, so the goal stayed blocked. GREG's own Goal Gravity (``greg/goal_gravity.py``) already asks Genesis to
form a function for GREG goals; this module is the missing seam for the egregore runtime. It does not choose which
Goal Gravity runtime is canonical; that founder decision stays open.

The egregore runtime keeps its own evidence ledger; the adapter bridges it to a GREG Body. It does not host the egregore
goal on the Body's ledger: there the Body's admission check quarantines (``stop_pushing``) every egregore goal that no
founder-signed GOAL authorizes, and such a goal is GREG's own (``greg/goal_gravity.py`` serves it). A stopped, paused,
revoked or closed goal is never drafted for and never settled.

Two steps, neither of which carries authority:

``draft_missions``
    For each open egregore deficit naming ``<function>@function`` that Genesis can form without a builder, and for
    which the caller supplies a check that senses that function, return an **unsigned** GREG mission draft. The
    draft is read-only, spends nothing, has no ``auto_attach`` and no strategies, and names only
    ``acquired.<function>.*`` plus the check's target. Its signed ``provenance.origin`` names the egregore deficit. This
    module holds no key and never signs: the founder signs, or nothing happens (an unsigned draft dropped in the
    inbox is kept as data). A draft is recorded on the ledger as ``egregore.genesis_mission_drafted``.

``settle``
    Once the Body's journal shows GREG closed the drafted mission's Genesis deficit (``deficit.resolved``, or the
    founder's signed attach of the capability Genesis verified for it), and that capability still serves the function
    ATTACHED (the draft carries no auto_attach, so attaching is a founder command), register a read-only
    ``<function>@function`` genome in the egregore repertoire and append the egregore deficit as
    ``resolved_resume_original_goal`` with ``resolved_by`` naming GREG's deficit, the capability and the closing record. The goal's
    ``missing_capabilities`` shrink, so its next gravity turn classifies the move instead of WAITing. The original
    goal is never edited.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from capabilities.genome import AuthorityEnvelope, CapabilityGenome
from egregore.contract_check import validate_record
from provenance.ledger import sha256_json

DEFICIT_RECORD = "egregore.capability_deficit"
DRAFT_RECORD = "egregore.genesis_mission_drafted"
SETTLED_RECORD = "egregore.genesis_deficit_settled"
FUNCTION_VERSION = "function"          # the version tag both Goal Gravity runtimes give a GREG function
PLANNER = "greg.gravity_genesis"


def _iso(now) -> str:
    if isinstance(now, str):
        return now
    return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def open_deficits(ledger) -> list[dict]:
    """Egregore deficits whose latest record is still ``goal_blocked_not_closed``, oldest first."""
    latest: dict[str, dict] = {}
    for record in ledger.by_type(DEFICIT_RECORD):
        deficit = record.payload.get("deficit")
        if deficit:
            latest[deficit["deficit_id"]] = deficit
    return [d for d in latest.values() if d["disposition"] == "goal_blocked_not_closed"]


def _functions(deficit: Mapping[str, Any]) -> list[str]:
    out = []
    for cap in deficit["missing_capabilities"]:
        function, _, version = cap.partition("@")
        if version == FUNCTION_VERSION:
            out.append(function)
    return out


def mission_id_for(deficit_id: str, function: str) -> str:
    return f"m:gravity-{deficit_id[7:31]}-{function}"


def _drafted(ledger) -> dict[str, dict]:
    return {r.payload["mission_id"]: r.payload for r in ledger.by_type(DRAFT_RECORD)}


HALTED = ("revoked", "paused", "completed", "superseded")


def _halted(registry, goal_id: str) -> str | None:
    """Why a goal must not pull Genesis: it is stopped, paused, closed or quarantined (a Body's admission check
    sets ``stop_pushing`` on any egregore goal no founder-signed GOAL authorizes)."""
    try:
        state = registry.state(goal_id)
    except Exception:                                  # unknown to this registry: nothing authorizes it here
        return "goal unknown to the registry"
    if state.status in HALTED:                     # a stop_pushing preference always sets ``paused``
        return f"goal is {state.status}"
    return None


def draft_missions(ledger, registry, genesis, *, checks: Mapping[str, Mapping[str, Any]], now,
                   horizon_days: float = 7.0) -> dict[str, list[dict]]:
    """Unsigned GREG mission drafts for the open egregore deficits Genesis can serve.

    ``checks`` maps a function to the success check the founder wants re-observed (its sensor must call that
    function). Returns ``{"drafts": [...], "unrouted": [...]}``; each draft is ``{"kind": "MISSION", "body": spec,
    "signed": False, "requires_founder_signature": True, ...}``. A function Genesis cannot form without a builder, or
    one with no check, is reported in ``unrouted`` with the reason and stays blocked."""
    at = _iso(now)
    horizon = (datetime.fromisoformat(at.replace("Z", "+00:00")) + timedelta(days=horizon_days)
               ).isoformat().replace("+00:00", "Z")
    known = _drafted(ledger)
    drafts, unrouted = [], []
    for deficit in open_deficits(ledger):
        halted = _halted(registry, deficit["goal_id"])
        if halted:
            unrouted.append({"deficit_id": deficit["deficit_id"], "goal_id": deficit["goal_id"], "reason": halted})
            continue
        for cap in deficit["missing_capabilities"]:
            if cap.partition("@")[2] != FUNCTION_VERSION:
                unrouted.append({"deficit_id": deficit["deficit_id"], "capability": cap,
                                 "reason": "not a GREG function (<function>@function)"})
        for function in _functions(deficit):
            reason = None
            check = checks.get(function)
            if not genesis.formable(function):
                reason = "Genesis cannot form this function without a builder; it stays with the founder"
            elif check is None:
                reason = "no founder check senses this function"
            elif (check.get("sensor") or {}).get("function") != function:
                reason = f"the check's sensor does not call {function}"
            if reason:
                unrouted.append({"deficit_id": deficit["deficit_id"], "function": function, "reason": reason})
                continue
            mission_id = mission_id_for(deficit["deficit_id"], function)
            spec = {
                "mission_id": mission_id,
                "founder_expression": deficit["founder_intent"],
                "intended_effect": (f"GREG forms {function} so the egregore goal {deficit['goal_id'][:23]} can leave "
                                    f"plan node {deficit['active_node_id']}"),
                "priority": 50, "closure": {"kind": "bounded"},
                "success_checks": [dict(check)], "strategies": [],
                "light_cone": {"capabilities": [f"acquired.{function}.*"], "targets": [check["sensor"]["target"]],
                               "max_consequence_class": "read_only", "budget_usd": 0.0, "horizon": horizon},
                "provenance": {"origin": f"{DEFICIT_RECORD}:{deficit['deficit_id']}", "planner": PLANNER,
                               "model_calls": 0},
            }
            draft = {"kind": "MISSION", "body": spec, "signed": False, "requires_founder_signature": True,
                     "goal_id": deficit["goal_id"], "deficit_id": deficit["deficit_id"], "function": function,
                     "draft_digest": sha256_json(spec)}
            if mission_id not in known:
                ledger.append(DRAFT_RECORD, {"mission_id": mission_id, "goal_id": deficit["goal_id"],
                                             "deficit_id": deficit["deficit_id"], "function": function,
                                             "draft_digest": draft["draft_digest"], "signed": False,
                                             "drafted_at": at, "execution_authority": "none"})
                known[mission_id] = draft
            drafts.append(draft)
    return {"drafts": drafts, "unrouted": unrouted}


def _genome(function: str, greg_deficit: str, capability_id: str) -> CapabilityGenome:
    return CapabilityGenome(
        name=function, version=FUNCTION_VERSION,
        description=f"GREG capability {capability_id}, formed by Capability Genesis for {function}",
        interface={"inputs": {"params": "object"}, "outputs": {"value": "object"}}, contracts=["evidence"],
        authority=AuthorityEnvelope(max_consequence_class="read_only", budget_ceiling_usd=0.0),
        acceptance_tests=[f"greg:genesis.verified:{greg_deficit}"],
        failure_modes=["capability detached, revoked or quarantined on the Body"],
        recovery_path="Genesis re-forms the function on the next mission that needs it")


def _resolutions(body) -> list[dict]:
    """How GREG closed a Genesis deficit, from its journal, in journal order.

    Two closures count. ``deficit.resolved`` (written when a signed mission's auto_attach attached the capability)
    and a founder command that attached the capability Genesis verified for that deficit. The second is needed
    because a founder ``CAPABILITY_ATTACH`` records ``capability.state`` ATTACHED but writes no ``deficit.resolved``
    for the mission's deficit (greg/body.py); it is linked by the attach command's digest."""
    out, seen = [], set()
    for e in body.journal.replay("deficit.resolved"):
        p = e.payload
        seen.add(p["deficit_id"])
        out.append({"deficit_id": p["deficit_id"], "capability_id": p["capability_id"],
                    "mission_id": p.get("mission_id"),
                    "link": f"greg:deficit.resolved:{p['deficit_id']}:{p['capability_id']}"})
    verified: dict[str, set] = {}
    for e in body.journal.replay("genesis.verified"):
        if e.payload.get("passed"):
            verified.setdefault(e.payload["capability_id"], set()).add(e.payload["deficit_id"])
    opened = {e.payload["deficit_id"]: e.payload for e in body.journal.replay("deficit.opened")}
    for e in body.journal.replay("capability.state"):
        p = e.payload
        if p.get("state") != "ATTACHED" or p.get("by") != "founder command" or not p.get("command_digest"):
            continue
        for deficit_id in sorted(verified.get(p["capability_id"], ())):
            if deficit_id in seen or deficit_id not in opened:
                continue
            seen.add(deficit_id)
            out.append({"deficit_id": deficit_id, "capability_id": p["capability_id"],
                        "mission_id": opened[deficit_id].get("mission_id"),
                        "link": f"greg:founder_attach:{deficit_id}:{p['capability_id']}:{p['command_digest']}"})
    return out


def settle(ledger, registry, genomes, body, *, now) -> list[dict]:
    """Close each drafted egregore deficit that GREG Genesis has resolved with an attached capability."""
    at = _iso(now)
    drafts = _drafted(ledger)
    settled_ids = {r.payload["mission_id"] for r in ledger.by_type(SETTLED_RECORD)}
    opened = {e.payload["deficit_id"]: e.payload for e in body.journal.replay("deficit.opened")}
    open_by_id = {d["deficit_id"]: d for d in open_deficits(ledger)}
    out = []
    for resolved in _resolutions(body):
        mission_id = resolved.get("mission_id")
        draft = drafts.get(mission_id)
        if draft is None or mission_id in settled_ids:
            continue
        function = draft["function"]
        greg_opened = opened.get(resolved["deficit_id"])
        if greg_opened is None or greg_opened.get("function") != function:
            continue                                   # GREG resolved some other function for this mission
        serving = body.genesis.find_attached(function)  # usable and ATTACHED only (CapabilityRegistry.usable)
        if serving is None or serving.capability_id != resolved["capability_id"]:
            continue                                   # not attached (or since detached, revoked or quarantined)
        deficit = open_by_id.get(draft["deficit_id"])
        if deficit is None or _halted(registry, deficit["goal_id"]):
            continue
        key = f"{function}@{FUNCTION_VERSION}"
        if genomes.get(function, FUNCTION_VERSION) is None:
            genomes.register(_genome(function, resolved["deficit_id"], serving.capability_id))
        link = resolved["link"]
        remaining = [c for c in deficit["missing_capabilities"] if c != key]
        if not remaining:
            closed = {**deficit, "lifecycle": "TESTED", "disposition": "resolved_resume_original_goal",
                      "resolved_at": at, "resolved_by": link}
            validate_record(closed, "capability-deficit")
            ledger.append(DEFICIT_RECORD, {"source": PLANNER, "deficit": closed, "goal_id": deficit["goal_id"],
                                           "missing_capabilities": closed["missing_capabilities"],
                                           "founder_intent": closed["founder_intent"],
                                           "disposition": closed["disposition"]})
        state = registry.state(deficit["goal_id"])
        if key in state.missing_capabilities:
            registry.transition(deficit["goal_id"], now=at, reason=f"GREG Genesis formed {function}: {link}",
                                missing_capabilities=[c for c in state.missing_capabilities if c != key])
        row = {"mission_id": mission_id, "goal_id": deficit["goal_id"], "egregore_deficit_id": deficit["deficit_id"],
               "greg_deficit_id": resolved["deficit_id"], "capability_id": serving.capability_id,
               "function": function, "link": link, "deficit_closed": not remaining, "settled_at": at,
               "execution_authority": "none"}
        ledger.append(SETTLED_RECORD, row)
        settled_ids.add(mission_id)
        out.append(row)
    return out
