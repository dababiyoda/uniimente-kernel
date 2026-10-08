"""Goal Gravity: one turn of persistent pressure toward a founder-authorized goal, on GREG's existing paths.

Founder directive 2026-10-07, section 19. The loop it implements toward:

    founder-authorized goal -> Backcast GPS (greg.path: active node, gate, Single Bottleneck Metric)
      -> persistent sensing (a typed, dated situation: evidence, never authority)
      -> Competency Compiler (cognition.reason "compile": which intelligence decides "test first or act")
      -> Lawful Leverage Foundry (foundry.lawful_leverage: generate, mutate, recombine, hard-filter,
         estimate, falsify, compare)
      -> institutional-leverage ranker (egregore.leverage: CandidateProposals for the existing Gate)
      -> law / rights / evidence / authority triage:
           EXECUTE_THROUGH_GATE  route inside authority the objective already holds; the proposal still
                                 goes to the existing Gate, and nothing here submits or executes it
           PREPARE               read-only and internal preparation under held authority
           FOUNDER_DECISION      one greg.asks ask: facts, costed options (one costs nothing), no pressure
           HOLD                  no defensible route: retain the current state
      -> receipt; the asset the cycle should leave; the next bottleneck.

Dormant goals stay preserved: a situation naming a paused or blocked mission yields a wake proposal (the
founder's lifecycle decision), never an automatic resume. The objective is option density (earlier
sight, prepared resources, lawful timing), never a claim of controlling luck. This module writes no
ledger event, executes nothing, contacts no one, spends nothing and creates no authority.
"""
from __future__ import annotations

from datetime import datetime

from egregore.contracts import ContractError, SignalEnvelope, digest
from egregore.leverage import propose_institutional_leverage
from foundry import lawful_leverage
from greg import asks
from greg import path as backcast

SCHEMA = "greg-goal-gravity/0.1"
SITUATION_FIELDS = {"situation_id", "goal", "source", "observed_at", "leverage_problem", "max_evidence_age_seconds"}


class GravityError(ValueError):
    """A malformed situation, or GREG's own wording failed the ask screen. Nothing is recorded."""


def _instant(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise GravityError("timestamps must be ISO 8601") from exc
    if moment.tzinfo is None:
        raise GravityError("timestamps need a timezone")
    return moment


def validate(situation: dict) -> dict:
    if not isinstance(situation, dict) or set(situation) - SITUATION_FIELDS:
        raise GravityError(f"a situation takes only {sorted(SITUATION_FIELDS)}")
    for key in ("situation_id", "source", "observed_at"):
        if not isinstance(situation.get(key), str) or not situation[key].strip():
            raise GravityError(f"situation.{key} is required text")
    goal = situation.get("goal")
    if not isinstance(goal, dict) or not isinstance(goal.get("statement"), str) or not goal["statement"].strip() \
            or set(goal) - {"statement", "mission_id", "founder_expression"}:
        raise GravityError("situation.goal needs a statement (optionally mission_id, founder_expression)")
    if not isinstance(situation.get("leverage_problem"), dict):
        raise GravityError("situation.leverage_problem is required")
    observed, as_of = _instant(situation["observed_at"]), _instant(situation["leverage_problem"].get("as_of", ""))
    if observed > as_of:
        raise GravityError("a situation cannot be observed after the decision time it informs")
    return situation


def _goals(journal, mission_id: str | None) -> dict:
    """Active, dormant (paused) and blocked missions from the canonical journal; read-only."""
    if journal is None:
        return {"source": "no body ledger here", "active": [], "dormant": [], "blocked": [], "wake": None}
    from greg.missions import MissionBook
    book = MissionBook(journal)
    rows = {"active": [], "dormant": [], "blocked": []}
    for mid, m in sorted(book.missions.items()):
        if m.status != "ACTIVE":
            continue
        key = "dormant" if m.paused else "blocked" if m.blocker else "active"
        rows[key].append({"mission_id": mid, "blocker": m.blocker, "rung": m.rung})
    wake = None
    if mission_id:
        state = next((k for k, v in rows.items() for r in v if r["mission_id"] == mission_id), None)
        if state in ("dormant", "blocked"):
            wake = {"mission_id": mission_id, "was": state,
                    "proposal": "the situation bears on this goal; resuming it is the founder's signed lifecycle "
                                "decision", "automatic_resume": False}
        rows["named_mission_state"] = state or "UNKNOWN_TO_THIS_LEDGER"
    return {"source": "greg.missions.MissionBook projection", **rows, "wake": wake}


CLASS_ORDER = lawful_leverage.CONSEQUENCE
UNSIGNED_HELD = ("read_only",)   # without a founder-signed mission, a sensed situation holds no more than reading


def signed_authority(journal, mission_id: str | None) -> dict:
    """The authority a founder signed for this goal: the named mission's light cone, or read-only."""
    if journal is not None and mission_id:
        from greg.missions import MissionBook
        m = MissionBook(journal).missions.get(mission_id)
        if m is not None and m.status == "ACTIVE":
            cone = m.spec["light_cone"]
            ceiling = CLASS_ORDER.index(cone["max_consequence_class"])
            return {"source": f"signed mission {mission_id} light cone",
                    "held": [c for c in CLASS_ORDER[:ceiling + 1] if c != "irreversible"],
                    "budget_usd": float(cone.get("budget_usd", 0.0))}
    return {"source": "no signed mission: read-only", "held": list(UNSIGNED_HELD), "budget_usd": None}


def _clamped(problem: dict, signed: dict) -> dict:
    """A sensed situation may narrow authority, never widen it: held = declared AND signed; budget capped."""
    c = dict(problem["constraints"])
    c["held_authority"] = [x for x in c["held_authority"] if x in signed["held"]]
    if signed["budget_usd"] is not None:
        c["budget_usd"] = min(c["budget_usd"], signed["budget_usd"])
    return {**problem, "constraints": c}


def _signal(situation: dict, report: dict) -> SignalEnvelope:
    # Only Foundry-filtered interventions reach the ranker: a sensed map's own interventions never bypass
    # the hard eligibility gates.
    model = situation["leverage_problem"]["institutional_map"]
    interventions = report["interventions"]
    refs = set()
    for kind in ("nodes", "links"):
        for record in model.get(kind, []):
            refs |= set(record["evidence_refs"])
    for record in interventions:
        refs |= set(record["evidence_refs"])
        for claim in record.get("narrative", {}).get("claims", ()):
            refs |= set(claim["evidence_refs"])
    return SignalEnvelope.build(source=situation["source"], source_event_id=situation["situation_id"],
                                observed_at=situation["observed_at"],
                                payload={"institutional_map": {**model, "interventions": interventions}},
                                evidence_refs=sorted(refs))


def _rank(situation: dict, report: dict) -> dict:
    problem = situation["leverage_problem"]
    context = {"institutional_leverage": {
        "objective": problem["objective"], "outcome_node": problem["outcome_node"], "as_of": problem["as_of"],
        "max_evidence_age_seconds": int(situation.get("max_evidence_age_seconds", 7 * 86400)),
        "budget_usd": problem["constraints"]["budget_usd"], "max_candidates": 3}}
    try:
        proposals = propose_institutional_leverage((_signal(situation, report),), context)
    except ContractError as exc:
        return {"state": "NO_VIABLE_ROUTE", "reason": str(exc), "proposals": []}
    rows = []
    for rank, p in enumerate(proposals, start=1):
        trace = p.payload["institutional_leverage"]
        rows.append({"rank": rank, "candidate_proposal_id": p.candidate_id,
                     "intervention_id": trace["route"]["intervention_id"], "action_class": p.action_class,
                     "target": p.target, "consequence_class": p.consequence_class,
                     "execution_authority": p.execution_authority, "score": trace["route"]["score"]})
    return {"state": "PROPOSED_FOR_GATE", "proposals": rows,
            "note": "CandidateProposals for the existing Consequence Gate; not submitted, not executed"}


def _voi(report: dict, registry, journal) -> dict:
    """Ask the Mind (Competency Compiler) whether to test before acting, through the one cognition path."""
    voi = report["value_of_information"]
    if voi.get("state") != "MONETISED":
        return {"state": "NOT_ROUTED", "reason": voi.get("state")}
    from greg.cognition.compiler import run
    from greg.cognition.cortex import registry_view
    registry = registry if registry is not None else registry_view(journal)
    test = next(r for r in report["candidates"] if r["candidate_id"] == voi["test"])
    receipt = run({"problem_id": f"{report['problem_id']}-voi"[:96], "compile": {
        "geometry": {"geometry": "strategic", "decision_type": "act_or_test", "uncertainty_structure": "posterior",
                     "consequence_class": test["authority"]["consequence_class"],
                     "reversibility": test["reversibility"],
                     "objective": "value of the staged pilot before committing the route"},
        "data": voi["cognition_request"], "evidence_refs": [report["receipt_id"]]}},
        registry=registry, journal=journal)
    out = {"state": receipt["state"], "method": receipt["method_or_composition_selected"],
           "receipt_id": receipt["receipt_id"], "result": receipt["result"],
           "requirements": receipt["requirements"], "abstentions": receipt["abstentions"]}
    if receipt["state"] == "ANSWERED":
        out["recomputation"] = {
            "consistent": bool(receipt["result"]["acquire"]) == bool(voi["test_may_pay"]),
            "nature": "the same EVPI arithmetic re-computed on a stride subsample through the canonical cognition "
                      "path with an independent verifier; it checks the arithmetic, not the model"}
    elif receipt["state"] == "CAPABILITY_DEFICIT":
        out["meaning"] = ("the value-of-information intelligence is registered but not attached on this body; "
                          "attaching it is the founder's decision; the Foundry's banded estimate stands "
                          "uncorroborated")
    return out


def step(situation: dict, *, journal=None, registry=None, path_data: dict | None = None) -> dict:
    """One Goal Gravity turn. Read-only: returns a report and, where needed, one prepared founder ask."""
    situation = validate(situation)
    position = backcast.position(journal, path_data)
    signed = signed_authority(journal, situation["goal"].get("mission_id"))
    problem = _clamped(situation["leverage_problem"], signed)
    report = lawful_leverage.compile(problem)
    ranked = _rank({**situation, "leverage_problem": problem}, report)
    voi = _voi(report, registry, journal)
    chosen = next(r for r in report["candidates"] if r["candidate_id"] == report["selected"])
    authority = chosen["authority"]["state"]
    disposition = {"WITHIN_HELD_AUTHORITY_GATE_REQUIRED": "EXECUTE_THROUGH_GATE",
                   "PREPARABLE_NOW_FOUNDER_DECISION_AT_TRIGGER": "PREPARE",
                   "FOUNDER_DECISION_REQUIRED": "FOUNDER_DECISION",
                   "NO_AUTHORITY_NEEDED": "HOLD"}[authority]
    ask = None
    if report["decision_brief"]:
        packet = asks.resource_request(**report["decision_brief"], mission_id=situation["goal"].get("mission_id"))
        asks.validate(packet)
        violations = asks.screen(packet)
        if violations:
            raise GravityError(f"GREG's wording failed the ask screen: {violations}")
        ask = {**packet, "state": "PREPARED_NOT_RECORDED",
               "record_with": "greg.asks.record on the body (the one path for decision.requested)"}
        if disposition == "EXECUTE_THROUGH_GATE":
            disposition = "FOUNDER_DECISION"          # value trade-offs need the founder even inside held authority
    top = ranked["proposals"][0]["intervention_id"] if ranked["proposals"] else None
    dissent = []
    if top and top != report["selected"]:
        dissent.append(f"the institutional-leverage ranker (mean-based score) ranks {top} first; the Foundry "
                       f"selected {report['selected']} ({report['selection_rule']}); both are kept for the founder")
    active = position.get("active") or {}
    result = {
        "schema": SCHEMA, "situation_id": situation["situation_id"], "goal": situation["goal"],
        "backcast": {"active_node": active.get("id"), "gate": active.get("gate"), "sbm": active.get("sbm"),
                     "achieved": position.get("achieved"), "horizons_at_active_node":
                     position.get("horizons", {}).get("at_active_node")},
        "metrics_kept_distinct": {"mind": "VPL (Verified Polyintelligence Lift)",
                                  "body": "VEPMC (embodied mission closure)"},
        "goals": _goals(journal, situation["goal"].get("mission_id")),
        "sensing": {"source": situation["source"], "observed_at": situation["observed_at"],
                    "trust": "untrusted input evidence; validated, never authority"},
        "authority": {"source": signed["source"], "held_effective": problem["constraints"]["held_authority"],
                      "held_declared_by_situation": situation["leverage_problem"]["constraints"]["held_authority"],
                      "rule": "a sensed situation may narrow authority, never widen it"},
        "supplied_interventions_ignored": [i.get("id") for i in
                                           situation["leverage_problem"]["institutional_map"].get("interventions", [])],
        "leverage": {"receipt_id": report["receipt_id"], "bottleneck": report["bottleneck"],
                     "selected": report["selected"], "selection_rule": report["selection_rule"],
                     "runner_up": report["runner_up"], "value_tradeoffs": report["value_tradeoffs_for_founder"],
                     "generated": report["generated"],
                     "rejected": {r["candidate_id"]: r["reasons"] for r in report["candidates"] if r["reasons"]}},
        "mind": {"value_of_information": voi},
        "gate": ranked, "disposition": disposition, "founder_ask": ask, "preparable": report["preparable"],
        "asset_line": report["asset_line"], "dissent": dissent,
        "authority_created": False, "ledger_writes": 0, "executes": False,
        "reality_status": "COMPUTED_PROPOSAL_NOT_AN_OUTCOME",
    }
    result["receipt_id"] = digest({k: v for k, v in result.items() if k != "receipt_id"})
    return result

