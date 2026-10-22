"""Infinite Goal Chase for the GREG body: persistent missions as feedback control.

A mission is a founder-signed target state plus the scope in which GREG may
pursue it. Each tick is one turn of a goal-directed feedback loop:

    observe (read-only sensors, through the Gate)
      -> discrepancy = failing checks of the current setpoint
      -> none failing: bounded mission closes; infinite mission advances to the
         next setpoint on its ladder, or holds and keeps re-verifying so drift is
         noticed and corrected (the practical meaning of "self-healing")
      -> otherwise choose the highest-leverage strategy that advances a failing
         check (most discrepancy closed per cost; structured routes before
         visual ones; founder critique exclusions respected)
      -> missing function  -> CapabilityDeficit -> Capability Genesis -> resume
      -> outside scope / constitution requires a human -> ONE decision request,
         then wait economically with the blocker remembered
      -> uncertain outcome -> reconcile; never blind retry of a consequential act

Mission truth is a projection of ``greg.*`` events on the canonical spine, so a
killed process, a new process or a replacement machine reconstructs the same
state. Process completion never closes a mission: only re-observed evidence does.
"""
from __future__ import annotations

import os

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from greg.authority import ActionOutcome, AuthorityOffice
from greg.capabilities import CapabilityError, InvocationContext, ROUTES
from greg.genesis import is_capability_fault
from greg import asks, improvement, routing
from greg.journal import Journal, fact_id, iso
from greg.lightcone import LightCone
from provenance.ledger import sha256_json

ROOT = Path(__file__).resolve().parents[1]
MISSION_SCHEMA = json.loads((ROOT / "contracts/greg-mission.schema.json").read_text())
TERMINAL = {"ACHIEVED", "ABANDONED", "SUPERSEDED"}
LIFECYCLE_STATES = {"ACTIVE", "PAUSED", "ABANDONED", "SUPERSEDED"}
DECISION_ANSWERS = {"approve", "reject", "reconcile_executed", "reconcile_not_executed"}
EPOCH = datetime.min.replace(tzinfo=timezone.utc)
# A retry-safe (read-only, idempotent) dispatch whose completion is unknown is re-attempted, but boundedly:
# at most RETRY_LIMIT consecutive unknown outcomes per strategy, the first retry at once (an interrupted read),
# later ones after an exponential backoff. Then the strategy counts as failed and the mission replans: another
# strategy, or one NO_STRATEGY ask on the founder-ask path. A non-retry-safe dispatch is never retried blindly.
RETRY_LIMIT = 3
RETRY_BACKOFF_SECONDS = 60


def retry_delay(streak: int) -> int:
    """Seconds to wait before re-attempting after ``streak`` consecutive unknown outcomes (1-based)."""
    return 0 if streak <= 1 else RETRY_BACKOFF_SECONDS * 2 ** (streak - 2)

# Asks no DECISION can close. An expired mandate is renewed only by a new signed MISSION, or ended by a
# LIFECYCLE abandon/supersede; an "approve" here changed nothing and left the mission blocked with no
# ask left to answer (review of 2026-10-14).
NOT_ANSWERABLE = {"SCOPE_RENEWAL": "an expired mandate is not renewed by a decision: sign a new MISSION with a "
                                   "new horizon (and supersede this one), or LIFECYCLE abandon it",
                  # greg/body.py hold_ask: an "approve" would lift nothing and close the ask on a still-held body
                  "CRASH_LOOP_HOLD": "a crash-loop hold is not lifted by a decision: sign BODY_RESUME (or BODY_STOP)"}


class MissionError(ValueError):
    """Malformed or conflicting mission input. Retained as data, never executed."""


def validate_mission(spec: dict) -> dict:
    errors = sorted(Draft202012Validator(MISSION_SCHEMA, format_checker=FormatChecker()).iter_errors(spec),
                    key=lambda e: list(e.path))
    if errors:
        raise MissionError(f"mission contract: {errors[0].message} at {list(errors[0].path)}")
    cone = LightCone.from_dict(spec["light_cone"])
    checks = {c["check_id"] for c in spec["success_checks"]}
    if len(checks) != len(spec["success_checks"]):
        raise MissionError("duplicate check ids")
    actions = [s["action_id"] for s in spec["strategies"]]
    if len(actions) != len(set(actions)):
        raise MissionError("duplicate strategy ids")
    for strategy in spec["strategies"]:
        unknown = set(strategy["advances"]) - checks
        if unknown:
            raise MissionError(f"strategy {strategy['action_id']} advances unknown checks {sorted(unknown)}")
        if ("capability" in strategy) == ("function" in strategy):
            raise MissionError("each strategy names exactly one of capability or function")
        requires = set(strategy.get("requires", []))
        if requires - checks:
            raise MissionError(f"strategy {strategy['action_id']} requires unknown checks {sorted(requires - checks)}")
        if requires & set(strategy["advances"]):
            raise MissionError(f"strategy {strategy['action_id']} cannot require a check it advances")
        if "declined_if" in strategy and not asks.human_work(strategy.get("function")):
            raise MissionError(f"strategy {strategy['action_id']}: declined_if applies only to a person's step "
                               "(human.* or professional.*)")
        _validate_bindings(strategy, set(actions))
        outside = compensation_outside(cone, strategy["compensate"]) if "compensate" in strategy else []
        if "compensate" in strategy and strategy["compensate"]["capability"] in METERED_SPEND:
            outside.append(f"{strategy['compensate']['capability']} spends money by itself, and a compensation "
                           "runs unpaid (cost 0): put that effect to the founder instead")
        if outside:
            raise MissionError(f"strategy {strategy['action_id']} compensation outside the light cone: "
                               + "; ".join(outside))
        for ref in inline_refs(strategy.get("params", {})):
            source = ref.get("action_id")
            if source not in actions or source == strategy["action_id"]:
                raise MissionError(f"strategy {strategy['action_id']} consumes inline input from unknown or own "
                                   f"action {source!r}")
    _acyclic_bindings(spec["strategies"])
    _validate_appraised_handoffs(spec)
    by_id = {s["action_id"]: s for s in spec["strategies"]}
    pre = [p["action_id"] for p in spec.get("pre_approved_steps", [])]
    if len(pre) != len(set(pre)):
        raise MissionError("a step is pre-approved at most once")
    for step in spec.get("pre_approved_steps", []):
        strategy = by_id.get(step["action_id"])
        if (strategy is None or strategy.get("capability") != step["capability"]
                or strategy["target"] != step["target"] or float(strategy.get("cost_usd", 0) or 0) != 0):
            raise MissionError(f"pre-approved step {step['action_id']} must name one free strategy by its exact "
                               "capability and target")
    ladder = spec["closure"].get("ladder", [])
    for rung in ladder:
        if set(rung) - checks:
            raise MissionError("ladder rung names unknown checks")
    if spec["closure"]["kind"] == "bounded" and ladder:
        raise MissionError("bounded missions close on their checks; ladders are for infinite missions")
    functions = [c["function"] for c in spec.get("capability_specs", [])]
    if len(functions) != len(set(functions)):
        raise MissionError("duplicate capability_specs functions")
    if sum(c["build_budget_usd"] for c in spec.get("capability_specs", [])) > cone.budget_usd + 1e-9:
        raise MissionError("capability build budgets exceed the mission budget")
    del cone
    return spec


def compensation_outside(cone: LightCone, compensate: dict, consequence_class: str = "read_only") -> list[str]:
    """Why a signed compensating action falls outside its mission's light cone (empty = inside).

    Judged at signing, so not against the horizon: compensation runs after the mission ends, and the
    Gate re-checks the whole cone when it runs (outside it, the founder decides an exact-scope APPROVAL)."""
    return cone.admits(capability=compensate["capability"], target=compensate["target"],
                       consequence_class=consequence_class, cost_usd=0.0, at=EPOCH)


def pre_approved(spec: dict, strategy: dict, manifest) -> bool:
    """Whether the founder-signed mission pre-approves exactly this strategy as resolved to ``manifest``:
    its own action id, capability, target and consequence class, at no cost (greg/sop.py runs)."""
    return float(strategy.get("cost_usd", 0) or 0) == 0 and any(
        p["action_id"] == strategy["action_id"] and p["capability"] == manifest.capability_id
        and p["target"] == strategy["target"] and p["consequence_class"] == manifest.consequence_class
        for p in spec.get("pre_approved_steps", []))


BIND_TYPES = {"string": (str,), "number": (int, float), "integer": (int,), "boolean": (bool,),
              "object": (dict,), "array": (list,)}
DEFAULT_BIND_BYTES = 16 * 1024


def exact_reach(capability_id: str, params: dict) -> dict:
    """What approving this exact scope lets the capability touch, shown before the founder answers. The approval is
    bound to the scope digest of these params; this makes the same params readable. Credentials by handle only."""
    if capability_id != "mcp.act":
        return {}
    from urllib.parse import urlsplit
    from greg.mcp_tools import reach_problem
    problem = reach_problem(params)
    if problem is not None:       # a malformed scope is shown as such, never parsed into a misleading reach
        return {"tool": f"{params.get('server')}.{params.get('tool')}" if isinstance(params, dict) else None,
                "malformed": problem}
    hosts = params.get("hosts") or ([urlsplit(str(params["url"])).hostname] if params.get("url") else [])
    credentials = [str(v) for v in (params.get("secrets") or {}).values()] + \
                  [f"{v} (as a file)" for v in (params.get("secret_files") or {}).values()] + \
                  ([str(params["bearer"])] if params.get("bearer") else [])
    return {"tool": f"{params.get('server')}.{params.get('tool')}",
            **({"remote_server": str(params["url"])} if params.get("url") else {}),
            "may_write": list(params.get("writable") or []) or "nothing",
            "may_reach": [f"{h}:443 through the relay" for h in hosts] or "no network",
            "credentials": sorted(credentials) or "none"}


# Capabilities whose network access runs behind the body's #26 relay when the body confines egress. A capability
# that decides its own confinement from ``ctx.egress`` (the organ exchange runs its organs with no network at all)
# must be listed, or a confined body hands it None and it runs with the body's network.
CONFINED_EGRESS = frozenset({"http.get", "github.pulls", "brief.engineering", "browser.render",
                             "browser.session", "worker.commission", "daleobanks.verify", "daleobanks.publish",
                             "venture.assess", "mcp.act", "organs.exchange"})


class Unbound(Exception):
    """A bound input is not available yet (or no longer matches its declared type)."""


# Producers whose output has an independent appraiser: producer capability -> (appraiser capability, the
# appraiser's sensor param naming the instance, the producer output field naming it, the accepting verdict).
# A typed handoff consumes such an output only after the mission observed that appraisal accept it.
APPRAISED_PRODUCERS = {"worker.commission": ("worker.appraise", "order", "work_order", "ACCEPTED")}


def inline_refs(params) -> list[dict]:
    """Every inline ``$from_action`` reference in a strategy's params (greg/pipeline.py syntax)."""
    found = []
    if isinstance(params, dict):
        ref = params.get("$from_action")
        if isinstance(ref, dict):
            found.append(ref)
        for key, value in params.items():
            if key != "$from_action":
                found += inline_refs(value)
    elif isinstance(params, list):
        for value in params:
            found += inline_refs(value)
    return found


def handoff_producers(strategy: dict) -> set:
    """The strategies whose output this strategy consumes through a typed handoff (bind or inline)."""
    return ({e["from"]["action_id"] for e in strategy.get("bind", []) if "action_id" in e["from"]}
            | {r.get("action_id") for r in inline_refs(strategy.get("params", {}))})


def _validate_appraised_handoffs(spec: dict):
    """A handoff from a producer that has an independent appraiser needs that appraisal in the mission:
    otherwise nothing could ever accept the output, and the consumer would only ever wait."""
    strategies = {s["action_id"]: s for s in spec["strategies"]}
    for consumer in spec["strategies"]:
        for producer in sorted(handoff_producers(consumer) & set(strategies)):
            rule = APPRAISED_PRODUCERS.get(strategies[producer].get("capability"))
            if rule is None:
                continue
            appraiser, key, _, _ = rule
            instance = strategies[producer].get("params", {}).get(key)
            if not any(c["sensor"].get("capability") == appraiser
                       and (c["sensor"].get("params") or {}).get(key) == instance for c in spec["success_checks"]):
                raise MissionError(f"strategy {consumer['action_id']} consumes {producer}'s output, which has no "
                                   f"independent appraisal ({appraiser} of {key} {instance!r}) in this mission")


def protected_param(path: str) -> str | None:
    """The protected key on ``path`` (greg/pipeline.py PROTECTED: budget, provider, scope, credentials, ...),
    if any. A typed handoff substitutes data only; it never sets authority, budget or execution scope."""
    from greg.pipeline import PROTECTED
    return next((part for part in str(path).split(".") if part in PROTECTED), None)


def _validate_bindings(strategy: dict, actions: set):
    seen = set()
    for edge in strategy.get("bind", []):
        if "check_id" in edge["from"]:
            # Only a check this strategy requires: the gate guarantees it was observed passing,
            # so the bound value is exactly the evidence that satisfied the precondition.
            if edge["from"]["check_id"] not in strategy.get("requires", []):
                raise MissionError(f"strategy {strategy['action_id']} binds from check "
                                   f"{edge['from']['check_id']!r}, which it does not require")
        else:
            source = edge["from"]["action_id"]
            if source not in actions or source == strategy["action_id"]:
                raise MissionError(f"strategy {strategy['action_id']} binds from unknown or own action {source!r}")
        if protected_param(edge["param"]):
            raise MissionError(f"strategy {strategy['action_id']} binds {edge['param']}: {protected_param(edge['param'])!r} "
                               "is protected (budget, provider, scope or credentials stay founder-signed literals)")
        if edge["param"] in seen:
            raise MissionError(f"strategy {strategy['action_id']} binds {edge['param']} twice")
        seen.add(edge["param"])
        try:
            _path(strategy.get("params", {}), edge["param"])
        except KeyError:
            pass
        else:
            raise MissionError(f"strategy {strategy['action_id']} binds {edge['param']}, which is also signed "
                               "statically; one source per param")
        template = edge.get("template")
        if template is not None and template.count("{value}") != 1:
            raise MissionError("a binding template needs exactly one {value} placeholder")
        if template is not None and edge["type"] != "string" and edge.get("render") != "json":
            raise MissionError("a templated binding renders text: declare type string or render json")


def _acyclic_bindings(strategies: list):
    edges = {s["action_id"]: handoff_producers(s) for s in strategies}   # signed bind and inline $from_action
    state = {}

    def visit(node):
        if state.get(node) == 1:
            raise MissionError(f"binding cycle through {node}")
        if state.get(node) == 2:
            return
        state[node] = 1
        for parent in edges.get(node, ()):
            visit(parent)
        state[node] = 2

    for node in edges:
        visit(node)


def _path(params: dict, path: str):
    node = params
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(path)
        node = node[part]
    return node


def _set_path(params: dict, path: str, value):
    parts = path.split(".")
    node = params
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise Unbound(f"param {path} crosses a non-object")
    node[parts[-1]] = value


def bound_value(edge: dict, output):
    """The typed, size-bounded value one edge carries from a receipt's output."""
    source = edge["from"].get("action_id") or "check " + str(edge["from"].get("check_id"))
    try:
        value = _field(output, edge["from"]["field"])
    except KeyError:
        raise Unbound(f"{source} output has no {edge['from']['field']}") from None
    kinds = BIND_TYPES[edge["type"]]
    if not isinstance(value, kinds) or (edge["type"] in ("number", "integer") and isinstance(value, bool)):
        raise Unbound(f"{source}.{edge['from']['field']} is not {edge['type']}")
    if edge.get("render") == "json":
        value = json.dumps(value, sort_keys=True, indent=1, ensure_ascii=False)
    if edge.get("template") is not None:
        value = edge["template"].replace("{value}", value if isinstance(value, str) else json.dumps(value))
    size = len(json.dumps(value, ensure_ascii=False).encode())
    if size > edge.get("max_bytes", DEFAULT_BIND_BYTES):
        raise Unbound(f"bound value of {size} bytes exceeds {edge.get('max_bytes', DEFAULT_BIND_BYTES)}")
    return value


# Capabilities whose own adapter measures provider spend (not a worker's self-claim):
# capability -> field of the adapter output holding the provider-reported USD.
METERED_SPEND = {"worker.commission": "worker.cost_usd"}


def reconciliation_terms(capability: str | None, reserved: float) -> tuple[str, dict]:
    """What every RECONCILIATION ask tells the founder before they answer: what to do, and what each answer books.
    A metered capability's provider may have spent while it ran, so "not executed" does not release its cap."""
    metered = capability in METERED_SPEND
    recommendation = "inspect the retained evidence, then state whether it executed"
    if metered:
        recommendation += (f". {capability} is metered: its provider may have spent while it ran, so either answer "
                           f"books ${reserved:.2f}, its signed cap, as spent; 'not executed' settles only whether its "
                           "effect happened, and a new run spends again")
    return recommendation, {"reconcile_executed": reserved, "reconcile_not_executed": reserved if metered else 0.0}


def metered_spend(capability_id: str, output, cap_usd: float) -> dict:
    """What a DONE action books against the mission budget.

    The signed cap stays the authorization ceiling. Where GREG's adapter measured the
    provider's spend, that measurement is booked; an absent, malformed, negative or
    over-cap report books the cap (conservative), and the basis says which happened."""
    cap = float(cap_usd)
    field_path = METERED_SPEND.get(capability_id)
    reported = None
    if field_path is not None and isinstance(output, dict):
        try:
            reported = _field(output, field_path)
        except KeyError:
            reported = None
    if isinstance(reported, bool) or not isinstance(reported, (int, float)) or reported != reported:
        return {"cost_usd": cap, "cost_cap_usd": cap, "spend_basis": "signed_cap" if field_path is None
                else "signed_cap: provider spend not reported", "provider_reported_usd": None}
    if reported < 0:
        return {"cost_usd": cap, "cost_cap_usd": cap, "provider_reported_usd": float(reported),
                "spend_basis": "signed_cap: provider report outside [0, cap]"}
    if reported > cap + 1e-9:     # spent more than signed: the actual spend is booked, never the cap in its place
        return {"cost_usd": round(float(reported), 6), "cost_cap_usd": cap, "provider_reported_usd": float(reported),
                "overspend_usd": round(float(reported) - cap, 6),
                "spend_basis": "provider_reported: over the signed cap"}
    return {"cost_usd": round(float(reported), 6), "cost_cap_usd": cap, "provider_reported_usd": float(reported),
            "spend_basis": "provider_reported"}


def reconciled_booking(capability: str | None, answer: str, worst: float, output=None) -> dict:
    """What the founder's reconciliation answer books for one UNCERTAIN dispatch, as the engine records it and the
    separate appraiser re-derives it (acceptance H.G4).

    "Executed" books the signed cap (its spend was never measured). "Not executed" settles the effect, not the
    money: a metered capability (a paid worker) may have spent while its provider ran, so it books the cap too;
    any other capability releases it. ``output`` is a receipted interrupt's collected output: its provider report
    is stated, and one over the cap is booked as reported, with the overspend (never below what the provider said
    it spent, as ``metered_spend`` books a DONE run; merge review of e410977), so the budget bounds a retry."""
    worst = float(worst)
    booked = answer == "reconcile_executed" or capability in METERED_SPEND
    reported = metered_spend(capability, output, worst)["provider_reported_usd"] \
        if output is not None and capability in METERED_SPEND else None
    out = {"booked": booked, "provider_reported_usd": reported, "cost_usd": worst if booked else 0.0,
           "overspend_usd": None}
    if booked and reported is not None and reported > worst + 1e-9:
        out.update(cost_usd=round(float(reported), 6), overspend_usd=round(float(reported) - worst, 6))
    return out


def disagreement(output) -> dict | None:
    """The views behind a composition that reported CONFLICT, kept side by side for the founder: which question,
    which method said what (a digest and a short preview of each output), and the dissent. Nothing is ranked."""
    meta = output.get("metaconsensus") if isinstance(output, dict) else None
    if not isinstance(meta, dict) or meta.get("state") != "CONFLICT":
        return None
    questions = {(q.get("problem_id"), q.get("epistemic_class")) for q in meta.get("conflicting_questions") or []}
    views = [{"problem_id": r.get("problem_id"), "method": r.get("method"), "receipt_id": r.get("receipt_id"),
              "output_digest": sha256_json(r.get("output")), "output_preview": json.dumps(r.get("output"),
                                                                                         default=str)[:160]}
             for r in output.get("receipts") or [] if isinstance(r, dict)
             and (r.get("problem_id"), r.get("epistemic_class")) in questions]
    return {"questions": sorted(f"{p}" for p, _ in questions), "views": views,
            "dissent": [str(d)[:200] for d in meta.get("dissent") or []][:4], "vote_taken": False}


def signed_cost(spec: dict, action_id: str) -> float:
    """The cost Alfonso signed for one strategy: its spend cap, hence the worst case of one dispatch of it."""
    strategy = next((s for s in spec["strategies"] if s["action_id"] == action_id), None)
    return float(strategy.get("cost_usd", 0.0)) if strategy else 0.0


def _field(output, path: str):
    value = output
    for part in path.split(".") if path else []:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise KeyError(path)
    if isinstance(value, dict) and value.get("truncated"):
        value = value["prefix"]
    return value


def unanswered(output) -> str | None:
    """Why a cognitive sensor receipt carries no answer; None when it answered or refuted.

    A receipt that abstained (budget exhausted, timeout, capability deficit, evidence
    expired, no quorum...) did not measure the world. Reading its missing field as a
    negative observation would book the world as unchanged and blame the strategy.
    REFUTED is a real negative result and stays one."""
    if not isinstance(output, dict) or "abstention_state" not in output:
        return None
    if output.get("abstention_state") in ("NONE", "REFUTED"):
        return None
    return str(output.get("reason_code") or output.get("abstention_state"))


def blames_strategy(reason: str) -> bool:
    """Whether a failed-strategy reason is evidence against the strategy's capability.

    Only "executed, re-observed, and the world measurably did not change" is. A re-observation
    that did not measure the world (a failed sensor call or an abstaining cognitive receipt,
    both recorded as "sensor ...") says nothing about the strategy's effect."""
    return reason.startswith("executed but ") and ": sensor " not in reason


def reconciled(action: dict) -> bool:
    """Whether a DONE record is the founder's reconciliation of an uncertain dispatch, not a receipted run
    (either lineage's record shape)."""
    return action.get("route") == "founder_reconciliation" or "reconciles" in action or any(
        str(r).startswith("founder reconciliation") for r in action.get("reasons", []))


def measured(observation: dict) -> bool:
    """Whether a recorded observation measured the world. The engine records a read that did not (the sensor
    call refused or failed, the host stopped it, or the receipt abstained) with a "sensor ..." detail, the
    marker its SENSOR_RETRY path and ``blames_strategy`` read; a predicate's own detail never starts so."""
    return not str(observation.get("detail", "")).startswith("sensor ")


def evaluate_predicate(predicate: dict, output) -> tuple[bool, str]:
    op = predicate["op"]
    try:
        value = _field(output, predicate.get("field", ""))
    except KeyError:
        return (op == "absent"), f"field {predicate.get('field')!r} absent"
    expected = predicate.get("value")
    if op == "exists":
        return True, "present"
    if op == "absent":
        return False, "present"
    if op == "equals":
        return value == expected, f"{value!r} == {expected!r}"
    if op == "contains":
        return (expected in value) if isinstance(value, (str, list)) else False, f"contains {expected!r}"
    if op == "not_contains":
        return (expected not in value) if isinstance(value, (str, list)) else False, f"not contains {expected!r}"
    if op in ("gte", "lte"):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False, "not numeric"
        return (value >= expected if op == "gte" else value <= expected), f"{value} {op} {expected}"
    if op == "count_gte":
        return (len(value) >= expected) if isinstance(value, (list, str)) else False, f"len {op} {expected}"
    raise MissionError(f"unknown predicate op {op!r}")


@dataclass
class MissionState:
    spec: dict
    command_digest: str
    cone: LightCone
    status: str = "ACTIVE"
    paused: bool = False
    rung: int = 0
    blocker: dict | None = None
    failed: dict = field(default_factory=dict)          # action_id -> reason
    excluded: dict = field(default_factory=dict)        # action_id -> founder critique reason
    attempts: dict = field(default_factory=dict)        # action_id -> next attempt number
    spent_usd: float = 0.0
    approved_scopes: set = field(default_factory=set)
    rejected_scopes: set = field(default_factory=set)
    observations: dict = field(default_factory=dict)    # check_id -> latest observation data
    next_observe_at: str | None = None
    actions_done: int = 0
    setpoints_reached: int = 0
    pending_effect: dict = field(default_factory=dict)  # action_id -> checks it should change
    collateral: dict = field(default_factory=dict)      # action_id -> passing checks it does not advance
    uncertain: dict = field(default_factory=dict)       # action_id -> its latest record, while that is UNCERTAIN
    # A persistent goal's pull (greg/goal_gravity.py) not yet served while the mission waits on an APPROVAL:
    # only ``observe_now`` sets it, so a mission no goal is bound to never has one.
    pull: str | None = None
    # (action_id, attempt) -> worst-case USD of a dispatch whose completion is unknown (UNCERTAIN). It counts
    # against the signed budget until a founder reconciliation settles that one dispatch: executed books it as
    # spent, not executed releases it (except a metered run's, which is booked: its provider may have spent while it
    # ran). A retry-safe dispatch is never reconciled, so its reservation stands.
    reserved: dict = field(default_factory=dict)
    uncertain_streak: dict = field(default_factory=dict)  # action_id -> consecutive dispatches of unknown outcome

    @property
    def mission_id(self):
        return self.spec["mission_id"]

    @property
    def reserved_usd(self) -> float:
        return round(sum(self.reserved.values()), 9)

    @property
    def committed_usd(self) -> float:
        """What the signed budget must cover: booked spend plus every unreconciled dispatch at its worst case."""
        return round(self.spent_usd + self.reserved_usd, 9)

    def current_checks(self) -> list[dict]:
        ladder = self.spec["closure"].get("ladder") or []
        if self.spec["closure"]["kind"] == "infinite" and ladder:
            wanted = set().union(*ladder[: self.rung + 1])
        else:
            wanted = {c["check_id"] for c in self.spec["success_checks"]}
        return [c for c in self.spec["success_checks"] if c["check_id"] in wanted]


# What lifts each kind of founder ask, for the active constraint (acceptance A.G2).
CONSTRAINT_LIFTED_BY = {"APPROVAL": "authority", "SCOPE_RENEWAL": "authority", "CAPABILITY_ATTACH": "capability",
                        "HUMAN_WORK": "a person's work", "RECONCILIATION": "evidence of what happened",
                        "NO_STRATEGY": "a strategy"}


MISSION_RESUME_LIFTS = ("a signed LIFECYCLE ACTIVE for this mission: the founder key, or a device key the founder "
                        "delegated LIFECYCLE to")


def active_constraint(m: "MissionState", book: "MissionBook", *, body_paused: list | None = None) -> dict | None:
    """The one thing this mission waits on now, named for the founder (acceptance A.G2).

    Derived only from retained facts, so a restart cannot change it: the first currently pursued check whose
    latest observation did not pass (or that was never observed), the strategies held because a check they
    require has not passed, and the blocker with the kind of thing that would lift it. None when the mission is
    closed, or when it is not paused, every pursued check passes and nothing blocks it.

    A pause comes first, because nothing else moves while it holds: ``paused_by`` names each pause in force (the
    body's, from greg.body ``body_pauses``, then the mission's own) and what lifts it. A blocker whose request
    the founder already answered (a decision or reconciliation, which an answer resolves) or the body withdrew
    waits on no one any more: it is shown with that answer, lifted by the next tick. An answer to a capability
    or human-work ask is only a record, and an answer an older ledger holds to a NOT_ANSWERABLE kind (a mandate
    renewal) lifts nothing, so those blockers still name what lifts them."""
    if m.status != "ACTIVE":
        return None
    paused_by = list(body_paused or [])
    if m.paused:
        paused_by.append({"by": "mission paused (signed LIFECYCLE)", "lifted_by": MISSION_RESUME_LIFTS})
    failing = [c["check_id"] for c in m.current_checks() if not (m.observations.get(c["check_id"]) or {}).get("passed")]
    if not failing and not m.blocker and not paused_by:
        return None
    passed = {cid for cid, o in m.observations.items() if (o or {}).get("passed")}
    out = {"check_id": failing[0] if failing else None,
           "observed": (m.observations.get(failing[0]) or {}).get("detail", "never observed") if failing else None,
           "held_strategies": [s["action_id"] for s in m.spec["strategies"] if set(s.get("requires", [])) - passed]}
    if paused_by:
        out = {"paused_by": paused_by, **out}
    if m.blocker:
        rid = m.blocker.get("request_id")
        kind = (book.requests.get(rid) or {}).get("kind")
        out["blocker"] = {"type": m.blocker.get("type"), "request_id": rid, "kind": kind,
                          "lifted_by": CONSTRAINT_LIFTED_BY.get(kind, m.blocker.get("type")),
                          "why": m.blocker.get("why")}
        if rid in book.withdrawn:           # MissionEngine._finish_withdrawal lifts it at the next step
            out["blocker"].update(withdrawn=book.withdrawn[rid].get("why"), lifted_by="the next tick")
        elif rid in book.answers and m.blocker.get("type") in ("decision", "reconciliation") \
                and kind not in NOT_ANSWERABLE:    # a legacy answer to these lifts nothing: the mission asks again
            out["blocker"].update(answered=book.answers[rid].get("answer"), lifted_by="the next tick")
    return out


def pursued_checks(spec: dict) -> set:
    """The check ids the mission's own loop ever observes and pursues: every rung of an infinite mission's ladder,
    otherwise every success check. A strategy that advances none of them is never selected, so never run."""
    ladder = spec["closure"].get("ladder") or []
    if spec["closure"]["kind"] == "infinite" and ladder:
        return set().union(*ladder)
    return {c["check_id"] for c in spec["success_checks"]}


def rank_key(s: dict, index: int, failing: set, manifest, record: dict | None, value_per_check_usd: float) -> tuple:
    """(-expected value, route rank, signed order, reliability): the order ``MissionEngine._pursue`` selects
    candidates in (most expected discrepancy closed per cost, structured routes before visual ones, then the
    order Alfonso signed). One rule for the mission's own selection and for what a goal may ask about ahead."""
    gain = len(set(s["advances"]) & failing)
    route = ROUTES.index(manifest.route) if manifest else len(ROUTES)
    estimate = routing.reliability(record)
    expected = routing.score(gain=gain, reliability_estimate=estimate, cost_usd=float(s.get("cost_usd", 0.0)),
                             value_per_check_usd=value_per_check_usd)
    return -expected, route, index, estimate


def first_choice(spec: dict, failing: set, *, manifest_for, records: dict, failed=(), excluded=(),
                 held=()) -> str | None:
    """The strategy the mission's own selection ranks first for these failing checks, or None.

    The candidates are ``_pursue``'s: strategies advancing a failing check, not failed, not excluded, whose
    signed preconditions (``requires``) are not among the failing checks, and not ``held``: strategies whose
    typed inputs cannot resolve now, which ``_pursue`` holds the same way (``MissionEngine._inputs``). A caller
    without the ledger (``goal_from_mission``) passes none and keeps the signed order."""
    value = float(spec.get("value_per_check_usd", 1.0))
    ranked = []
    for index, s in enumerate(spec["strategies"]):
        if not set(s["advances"]) & failing or s["action_id"] in failed or s["action_id"] in excluded \
                or set(s.get("requires", [])) & failing or s["action_id"] in held:
            continue
        manifest = manifest_for(s)
        key = rank_key(s, index, failing, manifest, records.get(manifest.capability_id) if manifest else None, value)
        ranked.append((*key[:3], s["action_id"]))
    return min(ranked)[3] if ranked else None


def strategy_scope(m: "MissionState | None", manifests: dict, action_id: str, *, now: datetime) -> dict:
    """The exact Gate scope of one static strategy of mission ``m`` and the reasons it lies outside its cone.

    Pure: the mission state and the capability manifests are given, so the same answer is derived by the
    engine (live) and by greg/goal_gravity.py (the mission state at a founder command's ledger position)."""
    s = next((x for x in (m.spec["strategies"] if m else []) if x["action_id"] == action_id), None)
    if s is None or "capability" not in s or s.get("bind") or "$from_action" in json.dumps(s.get("params", {})):
        raise MissionError("only a static, capability-bound strategy of a registered mission has an exact scope")
    manifest = manifests.get(s["capability"])
    if manifest is None:
        raise MissionError(f"capability {s['capability']} is not registered on this body")
    cost = float(s.get("cost_usd", 0.0))
    # The paid budget state too, exactly as AuthorityOffice.act binds a paid scope (#157): without it a goal's
    # ahead-of-time approval of a paid strategy names a digest the mission's own dispatch never derives.
    scope = AuthorityOffice.scope_digest(mission_id=m.mission_id, capability_id=manifest.capability_id,
                                         params=s.get("params", {}), target=s["target"],
                                         consequence_class=manifest.consequence_class, cost_usd=cost,
                                         spent_usd=m.committed_usd, budget_usd=m.cone.budget_usd)
    # The move itself, whatever the mission has spent: the identity a goal links its move and its asks by. The
    # scope digest above changes whenever a paid mission spends; it stays the one an approval is checked against.
    move = AuthorityOffice.scope_digest(mission_id=m.mission_id, capability_id=manifest.capability_id,
                                        params=s.get("params", {}), target=s["target"],
                                        consequence_class=manifest.consequence_class, cost_usd=cost)
    outside = m.cone.admits(capability=manifest.capability_id, target=s["target"],
                            consequence_class=manifest.consequence_class, cost_usd=cost,
                            spent_usd=m.committed_usd, at=now)
    return {"mission_id": m.mission_id, "action_id": action_id, "capability": manifest.capability_id,
            "target": s["target"], "consequence_class": manifest.consequence_class, "cost_usd": cost,
            "scope_digest": scope, "move_digest": move, "outside_cone": outside, "strategy": s}


def signed_answer(signed: dict, request_id: str, answer: Any) -> dict | None:
    """The signature-verified DECISION behind one recorded ``decision.answered``, or None.

    It counts only when the cited digest is a verified DECISION (not a MISSION, GOAL or GOAL_CONTROL),
    for exactly this request, with exactly the recorded answer. Every reader uses this one predicate: the
    mission fold, the mirrored refusal, the attention store, the evidence view and the ledger closure."""
    if not isinstance(answer, dict) or not isinstance(answer.get("command_digest"), str):
        return None
    cmd = signed.get(answer["command_digest"])
    body = ((cmd or {}).get("envelope") or {}).get("body")
    if cmd is None or cmd.get("kind") != "DECISION" or not isinstance(body, dict):
        return None
    if body.get("request_id") != request_id or body.get("answer") != answer.get("answer"):
        return None
    return cmd


def answer_record(request: dict, body: dict, command_digest: str) -> dict:
    """The one shape of a ``decision.answered`` row: what ``MissionEngine.answer`` records for the signed DECISION
    ``body`` answering ``request``, and the only record the mission fold applies (re-derived from the signature,
    never read from the row)."""
    return {"request_id": body.get("request_id"), "mission_id": request.get("mission_id"),
            "answer": body.get("answer"), "reason": str(body.get("reason", ""))[:500],
            "command_digest": command_digest}


class MissionBook:
    """Projection of mission truth from retained greg.* events.

    A ``decision.answered`` row is not the founder's answer by being on the ledger, whose hash chain is unkeyed: on
    a journal with a ledger it counts only as ``answer_record`` re-derives it from a founder-signed DECISION that
    ``goal_gravity.founder_facts`` counts as signed at its ``command.accepted`` position (a key valid there, this
    body, an unspent nonce, accepted inside its signed validity), and only if the command path's checks hold there.
    It takes effect at that acceptance. Any other row is kept in ``unverified`` and never moves a mission."""

    def __init__(self, journal: Journal, *, verify_answers: bool | None = None):
        self.journal = journal
        # None: verify exactly when there is a ledger to verify against (every body journal and the gravity prefix);
        # a replay-only test stand-in folds recorded rows as they are.
        self.verify_answers = getattr(journal, "ledger", None) is not None if verify_answers is None \
            else verify_answers
        self.missions: dict[str, MissionState] = {}
        self.requests: dict[str, dict] = {}
        self.answers: dict[str, dict] = {}
        self.rebuild()

    def rebuild(self):
        self.missions, self.requests, self.answers, self.withdrawn = {}, {}, {}, {}
        self.consumed: set[str] = set()    # answered paid APPROVALs whose one funded run has happened
        self._deficit_of = {}              # deficit_id -> the mission whose light cone pays for its builds
        self.unverified: dict[str, dict] = {}   # request_id -> {row, why}: an answer row kept as data, never applied
        self.unverified_requests: list[dict] = []  # decision.requested rows not recorded the way greg.asks records one
        self._admitted: set[str] = set()   # DECISION digests whose acceptance has been admitted (once each)
        self._refused_commands: dict[str, str] = {}   # digest -> why the body refused that command (command.rejected)
        self._unverifiable: set[str] = set()   # DECISION digests with an acceptance record that does not verify
        self._pending: dict = {}           # cited digest -> answer rows awaiting that DECISION's signed acceptance
        self._signed, self._signed_at = {}, {}   # verified DECISIONs; digest -> the acceptance event each verified at
        if self.verify_answers and getattr(self.journal, "ledger", None) is not None:
            from greg import goal_gravity  # goal_gravity imports this module
            self._signed = goal_gravity.verified_decisions(self.journal.ledger)
            self._signed_at = goal_gravity.decision_positions(self.journal.ledger)
        for event in self.journal.replay():
            self.fold(event.type[len("greg."):], event.payload, event_id=getattr(event, "event_id", None))
        self.finish()

    def finish(self) -> None:
        """End of the replay: an answer row no signed DECISION it cites was accepted after is kept as data, with the
        reason the founder is shown: the body refused the very command it cites (sign again), an acceptance record
        exists that cannot be verified, or no signed decision stands behind it at all."""
        for digest, rows in self._pending.items():
            if digest in self._refused_commands:
                cause, why = "refused_by_body", ("the body refused the signed decision it cites: "
                                                 + self._refused_commands[digest])[:300]
            elif digest in self._unverifiable:
                cause, why = "unverifiable_acceptance", ("a record says the body accepted the decision it cites, but "
                                                         "it carries no signed envelope that verifies (bodies before "
                                                         "2026-09-26 kept none)")
            else:
                cause, why = "no_signed_decision", "no founder-signed DECISION it cites was accepted after it was recorded"
            for data in rows:
                self.unverified[str(data.get("request_id"))] = {"row": data, "why": why, "cause": cause}
        self._pending = {}

    def fold(self, kind: str, data: dict, *, event_id: str | None = None) -> None:
        """Fold one retained greg.* fact (``kind`` without the ``greg.`` prefix), in ledger order.

        ``rebuild`` is this fold over the whole journal; greg/goal_gravity.py folds the same facts one at a
        time to judge a founder command against the mission state at its own ledger position. ``event_id``
        identifies a ``command.accepted`` record, where a signed DECISION's answer takes effect."""
        if kind == "command.accepted":
            if self.verify_answers:
                self._admit(data, event_id)
            return
        if kind == "command.rejected":
            if isinstance(data.get("digest"), str):
                self._refused_commands[data["digest"]] = str(data.get("reason", ""))
            return
        mid = data.get("mission_id")
        m = self.missions.get(mid)
        if kind in ("genesis.built", "genesis.unbuilt"):
            # The build budget is carved from the light-cone budget (validate_mission), so what a
            # build was billed is spent from the cone that every later paid action is admitted against.
            payer = self.missions.get(self._deficit_of.get(data.get("deficit_id")))
            if payer is not None:
                payer.spent_usd += float(data.get("cost_usd") or 0.0)
                # either settles its call (a billed failure is booked here, before its genesis.build_failed)
                payer.reserved.pop(("genesis", data["deficit_id"], data.get("build")), None)
            return
        if kind in ("genesis.build_started", "genesis.build_failed"):
            # A builder call is reserved on the cone at the ceiling it was given until it settles (built, or
            # failed with any bill booked by genesis.unbuilt): a call the body died inside never reports its
            # cost and Genesis._build_spend charges it at that ceiling, so the cone counts it too.
            payer = self.missions.get(self._deficit_of.get(data.get("deficit_id")))
            if payer is not None:
                slot = ("genesis", data["deficit_id"], data.get("build"))
                if kind == "genesis.build_started":
                    payer.reserved[slot] = float(data.get("reserved_usd") or 0.0)
                else:
                    payer.reserved.pop(slot, None)
            return
        if kind == "deficit.opened" and mid is not None:
            self._deficit_of[data["deficit_id"]] = mid
        if kind == "mission.registered":
            self.missions[mid] = MissionState(spec=data["spec"], command_digest=data["command_digest"],
                                              cone=LightCone.from_dict(data["spec"]["light_cone"]))
        elif m is None:
            if kind == "decision.requested":
                self._requested(data, event_id)
            elif kind == "decision.answered":
                self._answered(data)
            elif kind == "decision.withdrawn":
                self.withdrawn[data["request_id"]] = data
            return
        elif kind == "mission.lifecycle":
            m.paused = data["state"] == "PAUSED"
            if m.paused:              # a founder pause ends any goal pull; a later wake pulls afresh
                m.pull = None
            if data["state"] in ("ABANDONED", "SUPERSEDED"):
                m.status = data["state"]
        elif kind == "mission.observed":
            m.observations[data["check_id"]] = data
            if m.blocker is None:     # an observation of the unblocked loop serves any pending goal pull
                m.pull = None
            if data["passed"]:  # drift later -> previously ineffective strategies may be tried again
                for aid in [a for a, r in m.failed.items() if r.startswith(f"executed but {data['check_id']} ")]:
                    m.failed.pop(aid)
            for aid, checks in list(m.pending_effect.items()):
                if data["check_id"] not in checks:
                    continue
                if data["passed"]:
                    checks.discard(data["check_id"])
                else:
                    # Surprise: executed, yet the world did not change. Replan
                    # instead of repeating; eligible again after a later pass.
                    # A producer whose output another strategy binds changed its consumers' input,
                    # not the world: it is done, not ineffective, and is not re-run either.
                    if m.failed.get(aid, "").startswith("regressed "):
                        pass                     # blame for damaging the whole is never washed out by drift
                    elif any(e["from"].get("action_id") == aid for s in m.spec["strategies"] for e in s.get("bind", [])):
                        m.failed[aid] = f"produced bound input; {data['check_id']} awaits its consumers"[:300]
                    else:
                        m.failed[aid] = f"executed but {data['check_id']} still failing: {data['detail']}"[:300]
                if not checks:
                    m.pending_effect.pop(aid, None)
            # Section 13, a local gain that damages the whole: a check that passed just before an action ran,
            # which that action does not advance, is re-observed failing. The action is blamed and not re-run
            # automatically; if only such trade-offs remain, the founder decides. Unmeasured is not a regression.
            for aid, watched in list(m.collateral.items()):
                if data["check_id"] not in watched or data["detail"].startswith("sensor "):
                    continue
                watched.discard(data["check_id"])
                if not data["passed"]:
                    m.failed[aid] = f"regressed {data['check_id']}, which passed before it ran: {data['detail']}"[:300]
                    watched.clear()
                if not watched:
                    m.collateral.pop(aid, None)
        elif kind == "mission.action":
            aid = data["action_id"]
            m.attempts[aid] = data["attempt"] + 1
            slot = (aid, data["attempt"])
            if data["status"] == "UNCERTAIN":
                # The dispatch may have taken effect: its signed cap is reserved until reconciled. Records written
                # before the reservation existed carry no ``reserved_usd``; their worst case is the signed cost (a
                # PR #184 record of an interrupted worker held it as ``cost_usd`` with ``cost_reserved``).
                legacy = data.get("cost_usd", 0.0) if data.get("cost_reserved") else signed_cost(m.spec, aid)
                m.reserved[slot] = float(data.get("reserved_usd", legacy))
                streak = m.uncertain_streak[aid] = m.uncertain_streak.get(aid, 0) + 1
                if streak >= RETRY_LIMIT:   # bounded: no further blind re-attempt; the mission replans or asks
                    m.failed[aid] = (f"completion unknown on {streak} consecutive dispatches (retry limit "
                                     f"{RETRY_LIMIT}): " + "; ".join(data["reasons"]))[:300]
            else:                     # a later record for the same dispatch settles it (reconciled or receipted)
                m.reserved.pop(slot, None)
                m.uncertain_streak.pop(aid, None)
            # Settled by any later record about the action: its reconciliation, a standing proof, a later attempt.
            if data["status"] == "UNCERTAIN":
                m.uncertain[aid] = data
            else:
                m.uncertain.pop(aid, None)
            if data["status"] == "DONE":
                m.actions_done += 1
                m.spent_usd += data.get("cost_usd", 0.0)
                m.failed.pop(aid, None)
                if data.get("cost_cap_usd", 0.0) > 0 and data.get("scope_digest") in m.approved_scopes:
                    # One paid approval funds one run (#157), even a run that books $0 (a provider reporting no
                    # spend leaves the spend state, and so the digest, unchanged): the next selection asks again.
                    m.approved_scopes.discard(data["scope_digest"])
                    self.consumed |= {rid for rid, r in self.requests.items()
                                      if r.get("mission_id") == m.mission_id and r.get("kind") == "APPROVAL"
                                      and r.get("scope_digest") == data["scope_digest"] and rid in self.answers}
                strategy = next((s for s in m.spec["strategies"] if s["action_id"] == aid), None)
                if strategy:
                    m.pending_effect[aid] = set(strategy["advances"])
                    current = {c["check_id"] for c in m.current_checks()}
                    m.collateral[aid] = {c for c, o in m.observations.items()
                                         if o["passed"] and c in current and c not in strategy["advances"]}
            elif data["status"] in ("REFUSED", "UNAVAILABLE"):
                m.failed[aid] = "; ".join(data["reasons"])[:300]
            elif data["status"] == "RECONCILED_NOT_EXECUTED":
                m.spent_usd += data.get("cost_usd", 0.0)   # a metered run's unmeasured spend; 0.0 otherwise
        elif kind == "mission.blocked":
            m.blocker = data["blocker"]
        elif kind == "mission.unblocked":
            m.blocker = None
            m.pull = None
        elif kind == "mission.setpoint":
            m.setpoints_reached += 1
            m.rung = data["next_rung"]
        elif kind == "mission.achieved":
            m.status = "ACHIEVED"
        elif kind == "mission.schedule":
            m.next_observe_at = data["next_observe_at"]
            if "cause" in data:       # a persistent goal pulled this observation forward (observe_now)
                m.pull = data["next_observe_at"]
        elif kind == "mission.prepared":
            m.pull = None             # the pull was served while the mission waited on the founder
        elif kind == "mission.pull_released":
            m.pull = None             # released unserved: no open, unstopped goal binds the mission any more
        elif kind == "mission.strategy_excluded":
            m.excluded[data["action_id"]] = data["reason"]
        elif kind == "decision.requested":
            self._requested(data, event_id)
        elif kind == "decision.withdrawn":
            self.withdrawn[data["request_id"]] = data
            request = self.requests.get(data["request_id"])
            if data.get("voids_approval") and request:   # a restore from a backup (#186): the approval is asked again
                m.approved_scopes.discard(request["scope_digest"])
        elif kind == "decision.answered":
            self._answered(data)

    def _requested(self, data: dict, event_id: str | None) -> None:
        """A founder ask. ``greg.asks.record`` is its one writer and keys it on its request id, so on a verifying
        book a row under any other identity (another key under the same id) is kept as data: it cannot replace the
        ask a signed DECISION answers, nor send that answer to another mission's scope. A fold given no event id
        (a test stand-in replaying payloads) cannot tell and takes the row as before."""
        rid = data.get("request_id")
        if self.verify_answers and event_id is not None and event_id != fact_id("decision.requested", rid):
            self.unverified_requests.append({"row": data, "why": "not recorded under its request id, the identity "
                                                                 "greg.asks records every founder ask under"})
            return
        self.requests[rid] = data

    def _answered(self, data: dict) -> None:
        if not self.verify_answers:
            self._apply_answer(data)
            return
        digest = data.get("command_digest")
        self._pending.setdefault(digest if isinstance(digest, str) else None, []).append(data)

    def _apply_answer(self, data: dict) -> None:
        self.answers[data["request_id"]] = data
        m = self.missions.get(data.get("mission_id"))
        request = self.requests.get(data["request_id"])
        if m is None or request is None:
            return
        if data["answer"] == "approve":
            m.approved_scopes.add(request["scope_digest"])
        elif data["answer"] == "reject":
            m.rejected_scopes.add(request["scope_digest"])
            if request.get("action_id"):
                m.failed[request["action_id"]] = "founder rejected: " + data.get("reason", "")[:200]

    def _admit(self, accepted: dict, event_id: str | None) -> None:
        """A signed DECISION's acceptance: the answer rows citing it count, re-derived, if the command path's own
        checks (``MissionEngine.answer``) hold here. Only at the one ``command.accepted`` record ``founder_facts``
        counts it signed at; rows recorded later, or citing anything else, never count."""
        digest = accepted.get("digest")
        if accepted.get("kind") == "DECISION" and isinstance(digest, str) and digest not in self._signed:
            self._unverifiable.add(digest)
        if accepted.get("kind") != "DECISION" or not isinstance(digest, str) or digest not in self._signed_at \
                or self._signed_at[digest] != event_id or digest in self._admitted:
            return
        self._admitted.add(digest)     # once: a byte-identical copy of the acceptance carries the same event id
        cmd = self._signed[digest]
        for data in self._pending.pop(digest, []):
            rid = data.get("request_id")
            request = self.requests.get(rid) if isinstance(rid, str) else None
            why = self._refusal(data, request, cmd)
            if why is None:
                self._apply_answer(answer_record(request, cmd["envelope"]["body"], digest))
            else:
                self.unverified[str(rid)] = {"row": data, "why": why, "cause": "refused_at_acceptance"}

    def _refusal(self, data: dict, request: dict | None, cmd: dict) -> str | None:
        """Why a row citing a signed DECISION does not count at its acceptance (None: it counts)."""
        rid = data.get("request_id")
        if signed_answer(self._signed, rid, data) is None:
            return "the signed DECISION it cites answers another request or gives another answer"
        if request is None:
            return "no such request was recorded before the DECISION's acceptance"
        if rid in self.withdrawn:
            return "the request was withdrawn before the DECISION's acceptance: the command path refuses it"
        if rid in self.answers:
            return "the request was already answered before this DECISION's acceptance"
        reconcile = str(data.get("answer")).startswith("reconcile_")
        if data.get("answer") not in DECISION_ANSWERS or reconcile != (request.get("kind") == "RECONCILIATION"):
            return "the answer does not fit the request's kind: the command path refuses it"
        if data != answer_record(request, cmd["envelope"]["body"], cmd["digest"]):
            return "not the record MissionEngine.answer writes for the signed DECISION (its words or mission differ)"
        return None

    def open_requests(self) -> list[dict]:
        return [r for rid, r in self.requests.items() if rid not in self.answers and rid not in self.withdrawn]


def _named_verified(ask: dict) -> set[str]:
    """The verified (withheld, attachable) capabilities an attach ask names: what the founder's answer to it decides,
    and what the console offers to attach from it."""
    return {c.get("capability_id") for c in (ask.get("evidence") or {}).get("registered") or []
            if isinstance(c, dict) and c.get("state") == "VERIFIED"}


def _mechanism_summary(provenance: dict) -> dict:
    """What the founder needs to decide whether GREG may depend on an open-source package."""
    qualification = provenance.get("qualification") or {}
    return {k: provenance.get(k) for k in ("distribution", "version", "license", "upstream", "package_digest",
                                           "primitive", "competence", "common_mode", "acquisition", "limits")} | {
        "qualification": {"cases": qualification.get("cases"), "failures": len(qualification.get("failures", [])),
                          "oracle": qualification.get("oracle"), "scale_probe": qualification.get("scale_probe")}}


class MissionEngine:
    """One tick = one bounded turn of every active mission's feedback loop."""

    def __init__(self, *, journal: Journal, office: AuthorityOffice, registry, secrets, workspace_root: Path,
                 read_roots: tuple, genesis=None, max_actions_per_tick: int = 1, deliver_root: Path | None = None,
                 artifact_root: Path | None = None):
        self.journal, self.office, self.registry, self.secrets = journal, office, registry, secrets
        self.workspace_root, self.read_roots = Path(workspace_root), tuple(Path(p) for p in read_roots)
        self.deliver_root = Path(deliver_root) if deliver_root else None
        self.artifact_root = Path(artifact_root) if artifact_root else None
        self.genesis, self.max_actions_per_tick = genesis, max_actions_per_tick
        self.book = MissionBook(journal)
        self._stop_check = None
        self.selector = None          # the Body installs Goal Gravity here; None keeps the static order

    # -- founder inputs (already signature-verified by the body) ---------------
    def register(self, spec: dict, command_digest: str) -> str:
        spec = validate_mission(spec)
        mid = spec["mission_id"]
        existing = self.book.missions.get(mid)
        if existing:
            if existing.command_digest == command_digest or existing.spec == spec:
                return mid
            raise MissionError("mission id already bound to different founder intent; supersede explicitly")
        cone = LightCone.from_dict(spec["light_cone"])
        for s in (s for s in spec["strategies"] if "compensate" in s):   # its class is the manifest's, never claimed
            manifest = self.registry.manifests.get(s["compensate"]["capability"])
            outside = compensation_outside(cone, s["compensate"], manifest.consequence_class) if manifest \
                else ["its capability is not registered, so its consequence class is unknown"]
            if outside:
                raise MissionError(f"strategy {s['action_id']} compensation: " + "; ".join(outside))
        self.journal.record("mission.registered", {"mission_id": mid, "spec": spec,
                                                   "command_digest": command_digest}, key=mid)
        self.book.rebuild()
        return mid

    def lifecycle(self, body: dict, command_digest: str):
        mid, state = body.get("mission_id"), body.get("state")
        if mid not in self.book.missions or state not in LIFECYCLE_STATES:
            raise MissionError("unknown mission or lifecycle state")
        if self.book.missions[mid].status in TERMINAL:
            raise MissionError("terminal mission cannot change lifecycle")
        self.journal.record("mission.lifecycle", {"mission_id": mid, "state": state,
                                                  "reason": body.get("reason", ""),
                                                  "command_digest": command_digest}, key=command_digest)
        self.book.rebuild()

    def answer(self, body: dict, command_digest: str):
        rid, answer = body.get("request_id"), body.get("answer")
        request = self.book.requests.get(rid)
        if request is None or answer not in DECISION_ANSWERS:
            raise MissionError("unknown decision request or answer")
        if rid in self.book.withdrawn:
            raise MissionError("request withdrawn: " + self.book.withdrawn[rid]["why"])
        if rid in self.book.answers:
            if self.book.answers[rid]["answer"] == answer:
                return  # duplicate approval: no duplicate action
            raise MissionError("decision already answered differently")
        if request["kind"] in NOT_ANSWERABLE:
            raise MissionError(NOT_ANSWERABLE[request["kind"]])
        if request["kind"] == "RECONCILIATION" and not answer.startswith("reconcile_"):
            raise MissionError("reconciliation requests take reconcile_* answers")
        if request["kind"] != "RECONCILIATION" and answer.startswith("reconcile_"):
            raise MissionError("reconcile answers apply only to reconciliation requests")
        # The row counts once Body.apply records this command's acceptance (MissionBook re-derives it from the
        # signature). Its identity is its own content, so the only row that can hold it is this exact record: a row
        # anyone else wrote under the request id or the command's digest cannot refuse the founder's answer. A row
        # an interrupted apply already wrote under the request id (bodies before fold-time re-verification) is this
        # same record and is not written twice.
        record = answer_record(request, body, command_digest)
        retained = self.journal.retained("decision.answered", rid)
        if retained is None or retained.payload != record:
            self.journal.record("decision.answered", record)
        self.book.rebuild()

    def exclude_strategy(self, mission_id: str, action_id: str, reason: str, critique_ref: str):
        self.journal.record("mission.strategy_excluded", {"mission_id": mission_id, "action_id": action_id,
                                                          "reason": reason[:300], "critique_ref": critique_ref},
                            key=[mission_id, action_id, critique_ref])
        self.book.rebuild()

    # -- timing and asks for a persistent goal bound to signed missions (greg/goal_gravity.py) ---
    def observe_now(self, mission_id: str, now: datetime, *, cause: str) -> bool:
        """Pull a mission's next read-only observation forward (a goal bound to it woke).

        Timing only: scope, light cone, budget and strategies are unchanged, and the observation
        still goes through the Gate. A paused or terminal mission is the founder's and is never
        touched; a mission already due needs no pull. A mission waiting on the founder's answer to
        an APPROVAL may be pulled, one pull pending at a time: it then re-observes and repairs its
        other checks inside its cone while the decision stays open (``_prepare``); the asked scope
        itself still runs only after a signed approve."""
        self.book.rebuild()
        m = self.book.missions.get(mission_id)
        if m is None or m.status in TERMINAL or m.paused:
            return False
        if self._awaiting_approval(m):
            if m.pull is not None:
                return False
        elif not m.next_observe_at or datetime.fromisoformat(m.next_observe_at.replace("Z", "+00:00")) <= now:
            return False
        self.journal.record("mission.schedule", {"mission_id": mission_id, "next_observe_at": iso(now),
                                                 "cause": str(cause)[:300]},
                            key=[mission_id, "observe-now", str(cause)[:300]])
        self.book.rebuild()
        return True

    def release_pull(self, mission_id: str, now: datetime, *, why: str) -> bool:
        """Release a goal's pending pull unserved (greg/goal_gravity.py: no open, admitted, unstopped goal binds
        the mission any more, e.g. the founder revoked or stopped it). The mission returns to its own loop:
        while it waits on an APPROVAL it only waits, as a mission no goal is bound to does."""
        self.book.rebuild()
        m = self.book.missions.get(mission_id)
        if m is None or m.pull is None:
            return False
        self.journal.record("mission.pull_released", {"mission_id": mission_id, "pull": m.pull,
                                                      "why": str(why)[:300], "at": iso(now)},
                            key=[mission_id, "pull-released", m.pull])
        self.book.rebuild()
        return True

    def strategy_scope(self, mission_id: str, action_id: str, *, now: datetime) -> dict:
        """The exact Gate scope of one founder-signed static strategy, and why it lies outside the cone.

        The digest is the one ``AuthorityOffice.act`` derives for the same strategy (consequence class
        from the capability manifest, never from the caller), so an approve of it is the approval the
        mission itself would ask for. Strategies bound to another action's output have no exact scope
        before they run and are refused here."""
        return strategy_scope(self.book.missions.get(mission_id), self.registry.manifests, action_id, now=now)

    def _manifest_for(self, s: dict):
        """A strategy's capability manifest: the signed capability, else one Genesis attached for its function."""
        manifest = self.registry.manifests.get(s.get("capability"))
        if manifest is None and s.get("function") and self.genesis is not None:
            manifest = self.genesis.find_attached(s["function"])
        return manifest

    def _askable(self, m: "MissionState | None", mission_id: str, action_id: str, *, now: datetime) -> dict:
        """The exact scope of a strategy the founder may be asked about ahead of the mission's loop, or
        MissionError saying why not. One predicate for ``request_decision`` and ``ask_refusal``."""
        if m is None or m.status in TERMINAL or m.paused:
            raise MissionError(f"mission {mission_id} is unknown, closed or paused: nothing to ask for it")
        scope = self.strategy_scope(mission_id, action_id, now=now)
        if not scope["outside_cone"]:
            raise MissionError(f"{action_id} is inside the mission's light cone: it needs no founder decision")
        if scope["scope_digest"] in m.rejected_scopes:
            raise MissionError("the founder already rejected this exact scope")
        # AuthorityOffice.act refuses such an act before the cone, so the mission never asks about it: an approve
        # asked for ahead of its loop could change nothing on this body.
        refused = AuthorityOffice.precheck(self.registry.manifests[scope["capability"]], target=scope["target"],
                                           params=scope["strategy"].get("params", {}))
        if refused is not None:
            raise MissionError(f"{action_id} cannot act here ({refused[0]}): {refused[1]}"[:400])
        # The mission's own selection never picks an excluded or failed strategy (tick: "in m.failed or in
        # m.excluded"), nor one that advances no check its loop pursues, so it would never ask for (or run)
        # one; asking ahead of it must not either: an approve could change nothing.
        if action_id in m.excluded:
            raise MissionError(f"the founder excluded {action_id} by a signed critique: {m.excluded[action_id]}"[:400])
        if action_id in m.failed:
            raise MissionError(f"{action_id} is not selectable now: {m.failed[action_id]}"[:400])
        pursued = pursued_checks(m.spec)
        checks = set(scope["strategy"].get("advances", [])) & pursued
        if not checks:
            raise MissionError(f"{action_id} advances {sorted(scope['strategy'].get('advances', []))}, none of which "
                               f"the mission's loop pursues ({sorted(pursued)}): it would never run it")
        # Only the move the mission's own selection would run next for these checks may be asked about ahead:
        # one consequential decision is one ask, and its approve is what the mission then runs.
        held = {s["action_id"] for s in m.spec["strategies"] if set(s["advances"]) & checks and self._held(m, s)}
        first = first_choice(m.spec, checks, manifest_for=self._manifest_for,
                             records=routing.track_record(self.journal), failed=m.failed, excluded=m.excluded,
                             held=held)
        if first != action_id:
            raise MissionError(f"for {', '.join(sorted(checks))} the mission's own selection runs {first} first, not "
                               f"{action_id}: it would ask for (or run) {first}, so an approve of {action_id} could "
                               "change nothing")
        for rid, r in self.book.requests.items():
            other = next((x for x in m.spec["strategies"] if x["action_id"] == r.get("action_id")), None)
            if r.get("kind") == "APPROVAL" and r.get("mission_id") == mission_id and other is not None \
                    and r.get("scope_digest") != scope["scope_digest"] and rid not in self.book.answers \
                    and rid not in self.book.withdrawn and set(other["advances"]) & checks:
                raise MissionError(f"an open APPROVAL ({rid}, {other['action_id']}) already asks about "
                                   f"{', '.join(sorted(set(other['advances']) & checks))}: one decision, one ask")
        return scope

    def ask_refusal(self, mission_id: str, action_id: str, *, now: datetime) -> str | None:
        """Why ``request_decision`` would refuse to ask about this strategy now, or None. Records nothing."""
        self.book.rebuild()
        try:
            self._askable(self.book.missions.get(mission_id), mission_id, action_id, now=now)
        except MissionError as exc:
            return f"MissionError: {exc}"
        return None

    def request_decision(self, mission_id: str, action_id: str, *, why: str, recommendation: str, now: datetime,
                         evidence: dict | None = None, quoted: tuple = ()) -> str:
        """Ask the founder ahead of time about one signed strategy whose exact scope is outside the cone.

        This is the engine's own APPROVAL ask: the same deterministic request id (mission, APPROVAL,
        exact scope), the same contract and the same one-ask-per-scope rule, so when the mission's
        loop later reaches the strategy it finds this request instead of asking again. Asking grants
        nothing and executes nothing; an approve adds exactly this scope to the mission's approved
        scopes, used only when the mission's own feedback loop selects the strategy. A paid scope
        includes the mission's spend state (#157), so its approve funds one run: once that run, or
        any other spend, changes the state, the mission asks again before spending again."""
        self.book.rebuild()
        m = self.book.missions.get(mission_id)
        scope = self._askable(m, mission_id, action_id, now=now)
        s, cost = scope["strategy"], scope["cost_usd"]
        resource = None
        if cost > 0:
            from types import SimpleNamespace
            records = routing.track_record(self.journal)
            routing_decision = {"chosen": action_id, "reliability": routing.reliability(records.get(scope["capability"])),
                                "asked_ahead_of_the_mission_loop": True}
            resource = self._spend_ask(m, s, SimpleNamespace(reasons=scope["outside_cone"]), routing_decision)
            if evidence:
                resource = {**resource, "evidence": {**resource["evidence"], **evidence}}
        return self._request(
            m, kind="APPROVAL", scope_digest=scope["scope_digest"], move_digest=scope["move_digest"],
            action_id=action_id, why=(why or "; ".join(scope["outside_cone"]))[:400],
            recommendation=recommendation[:400],
            alternatives=[x["action_id"] for x in m.spec["strategies"] if x["action_id"] != action_id][:5]
            + ["reject: the mission will try alternatives or ask again"],
            requested={"capability": scope["capability"], "target": scope["target"],
                       "consequence_class": scope["consequence_class"], "cost_usd": s.get("cost_usd", 0.0),
                       # the same reach the loop's ask shows: one scope has one request, whichever path asks first
                       **exact_reach(scope["capability"], s.get("params", {})),
                       **({"spend": f"${cost:.2f} for this one action"} if cost > 0 else {})},
            now=now, resource=resource, evidence=evidence, quoted=quoted)

    # -- the loop ---------------------------------------------------------------
    def tick(self, now: datetime, *, should_stop=None) -> list[dict]:
        """One turn per mission. ``should_stop`` is consulted before every mission step:
        a stop that arrives mid-tick admits no further dispatch (from #112)."""
        self._stop_check = should_stop
        self.book.rebuild()
        summary = []
        order = sorted(self.book.missions.values(), key=lambda m: (-m.spec.get("priority", 0), m.mission_id))
        if self.selector is not None:
            # Goal Gravity orders the signed missions (greg.gravity.select); it never adds or drops one.
            ranked = list(dict.fromkeys(mid for mid in self.selector(order) if mid in self.book.missions))
            order = [self.book.missions[mid] for mid in ranked] + [m for m in order if m.mission_id not in ranked]
        for m in order:
            if should_stop is not None and should_stop():
                summary.append({"mission_id": m.mission_id, "state": "NOT_STEPPED", "why": "stop requested"})
                continue
            summary.append({"mission_id": m.mission_id, **self._step(m, now)})
        return summary

    def _ledger_reader(self):
        from greg.ventures import LedgerReader
        return LedgerReader(self.journal) if self.journal is not None else None

    def _context(self, m: MissionState, manifest) -> InvocationContext:
        # worker.appraise reads the ledger to bind a retained WorkOrder to its canonical commission receipt, as the
        # separate appraiser does: evidence a stopped body wrote before its receipt is never accepted (H.G11).
        return InvocationContext(workspace=self.workspace_root / m.mission_id.replace(":", "_"),
                                 read_roots=self.read_roots, secrets=self.secrets, manifest=manifest,
                                 deliver_root=self.deliver_root, learned=improvement.learned(self.journal),
                                 # ledger access: memory, artifacts, cognition and the body's own records; the organ
                                 # bridges that render or check the Mind's receipts (the venture memo, DALEOBANKS's
                                 # claim-by-claim verify) and worker.appraise (it reads its commission receipt; its
                                 # Mind evaluator gets no ledger it could write, #185) get a reader that cannot write
                                 journal=self._ledger_reader() if manifest.capability_id in ("venture.assess",
                                                                                             "daleobanks.verify",
                                                                                             "worker.appraise")
                                 else self.journal if manifest.capability_id in ("memory.precedents", "daleobanks.outcome")
                                 or manifest.capability_id.startswith(("artifact.", "cognition.", "pipeline.", "institution.",
                                                                       "organ.", "foundry.")) else None,
                                 artifact_root=self.artifact_root, stop_check=self._stop_check,
                                 # eligibility view for the Mind, and for the evaluator that asks it
                                 capability_registry=self.registry if manifest.capability_id.startswith("cognition.")
                                 or manifest.capability_id == "worker.appraise" else None,
                                 cognition_model=getattr(self, "cognition_model", None),
                                 egress=getattr(self, "egress", None) if manifest.capability_id in CONFINED_EGRESS else None,
                                 worker_confinement=getattr(self, "worker_confinement", "required"))

    def _inert_interruption(self, m: MissionState, strategy: dict, manifest) -> dict:
        """The standing-reconciliation proof for an UNCERTAIN dispatch (greg.workers.inert_interruption_proof)."""
        from greg.workers import inert_interruption_proof
        prior = sum(1 for e in self.journal.replay("mission.action")
                    if e.payload.get("mission_id") == m.mission_id
                    and e.payload.get("action_id") == strategy["action_id"]
                    and e.payload.get("route") == "standing_reconciliation")
        return inert_interruption_proof(spec=m.spec, strategy=strategy, capability_id=manifest.capability_id,
                                        consequence_class=manifest.consequence_class,
                                        mission_workspace=self.workspace_root / m.mission_id.replace(":", "_"),
                                        prior=prior)

    def _request(self, m: MissionState, *, kind: str, scope_digest: str, action_id: str | None, why: str,
                 recommendation: str, alternatives: list | None = None, requested: dict, now: datetime,
                 resource: dict | None = None, evidence: dict | None = None, quoted: tuple = (),
                 instance: dict | None = None, consequence: str = "the mission waits; no action is taken",
                 move_digest: str | None = None) -> str:
        """One escalation per exact scope, recorded through the founder-ask contract (greg/asks.py).

        ``resource`` makes it a section-60 resource ask: evidence, costed options with their
        expected effects, the recommendation's expected effect and uncertainty. Everything
        Alfonso signed in the mission is exempt from the wording screen. ``instance`` binds the
        request to one occurrence inside its scope (a RECONCILIATION names the one dispatch it
        settles), so an answer about one occurrence is never reused for another. An APPROVAL also
        records the move it asks about without the spend state (``move_digest``; the scope digest
        when none is given, which is the same for an unpaid scope), so a goal still finds its ask,
        and the answer to it, after the mission spends."""
        epoch = 0
        while True:
            rid = "req-" + sha256_json({"mission": m.mission_id, "kind": kind, "scope": scope_digest,
                                        **({"epoch": epoch} if epoch else {}),
                                        **({"instance": instance} if instance is not None else {})})[7:31]
            if rid not in self.book.withdrawn and rid not in self.book.consumed \
                    and not (kind in NOT_ANSWERABLE and rid in self.book.answers):
                break
            epoch += 1  # the same discrepancy returned after healing, a paid approval used, or a legacy answer
            # closed an unanswerable ask: a new escalation
        if rid in self.book.requests:
            return rid  # one escalation per exact scope; waiting creates no spam
        why = why.strip() or f"{kind.lower().replace('_', ' ')} needs your decision"   # never an empty ask
        message = {"request_id": rid, "mission_id": m.mission_id, "kind": kind, "action_id": action_id,
                   "scope_digest": scope_digest, "why_now": why, "recommendation": recommendation,
                   "alternatives": alternatives, "authority_requested": requested,
                   "consequence_of_no_response": consequence,
                   "created_at": iso(now), "reality_status": "RECORDED_LOCAL_MESSAGE"}
        if kind == "APPROVAL":
            message["move_digest"] = move_digest or scope_digest
        if evidence is not None:
            message["evidence"] = evidence
        if resource is not None:
            message.update(resource)
            message["alternatives"] = [o["option"] for o in resource["options"]]
        founder_words = [a.get("reason", "") for a in self.book.answers.values() if a.get("mission_id") == m.mission_id]
        asks.record(self.journal, message, quoted=asks.founder_text([m.spec, m.mission_id, founder_words,
                                                                     list(m.excluded.values()), list(quoted)]))
        return rid

    def _generation(self, m: MissionState, kind: str) -> int:
        # Blocks and unblocks are facts per occurrence: the same blocker after an unblock is a new block,
        # never deduplicated into the old one (which silently left the mission unblocked).
        return sum(1 for e in self.journal.replay(kind) if e.payload["mission_id"] == m.mission_id)

    def _block(self, m: MissionState, blocker: dict):
        if m.blocker != blocker:
            self.journal.record("mission.blocked", {"mission_id": m.mission_id, "blocker": blocker},
                                key=[m.mission_id, blocker, self._generation(m, "mission.unblocked")])
            m.blocker = blocker

    def _unblock(self, m: MissionState, why: str):
        self.journal.record("mission.unblocked", {"mission_id": m.mission_id, "resolved": m.blocker, "why": why},
                            key=[m.mission_id, "unblock", m.blocker, self._generation(m, "mission.blocked")])
        m.blocker = None

    def _finish_withdrawal(self, m: MissionState) -> MissionState:
        """Lift a blocker whose request was withdrawn but whose mission was never unblocked.

        Each withdraw site (``_prepare``, ``_watch_while_blocked``, ``_honor_refusal``) records decision.withdrawn
        and then mission.unblocked as separate appends. A body that died between them left a blocker nothing could
        lift: ``answer`` refuses a withdrawn request, ``_blocker_resolved`` waits for an answer, and no ask is open,
        so the founder was told nothing is needed. The rest of the withdrawal is finished from the retained facts,
        recording exactly what the site would have (so it is idempotent): an honored refusal's exclusion, then the
        unblock. Normal handling resumes, and may raise a new ask."""
        rid = m.blocker["request_id"]
        honored = next((e.payload for e in self.journal.replay("human.refusal_honored")
                        if e.payload["mission_id"] == m.mission_id and e.payload["request_id"] == rid), None)
        if honored is not None:              # _honor_refusal: the person's refusal stands, for good
            self._exclude_refused(m, honored)
        self._unblock(m, self.book.withdrawn[rid]["why"])
        self.book.rebuild()
        return self.book.missions[m.mission_id]

    def _exclude_refused(self, m: MissionState, honored: dict):
        """The exclusion an honored refusal records, derived only from that record (so re-recording is idempotent)."""
        evidence = honored["evidence"]
        self.journal.record("mission.strategy_excluded", {
            "mission_id": m.mission_id, "action_id": honored["action_id"],
            "reason": "declined by the person: " + honored["detail"][:200],
            "critique_ref": "refusal:" + (evidence[0] if evidence else honored["request_id"])},
            key=[m.mission_id, honored["action_id"], "refusal"])

    def _blocker_resolved(self, m: MissionState) -> tuple[bool, str]:
        b = m.blocker
        if b["type"] in ("decision", "reconciliation"):
            answer = self.book.answers.get(b["request_id"])
            return (answer is not None, f"founder answered {answer['answer']}" if answer else "awaiting founder")
        if b["type"] == "capability":
            ok, why = self.registry.usable(b["capability_id"]) if b.get("capability_id") else (False, "none")
            if not ok and self.genesis is not None and b.get("function"):
                # the rule that decides whether a mission arriving now has this need (Genesis.serving), never only
                # what this blocker offered: a fitting method that could not run when the mission blocked (founder-
                # detached, unregistered, unavailable) serves it once it can, whatever its function name
                served = self.genesis.serving(m.mission_id, b["function"])
                if served is not None:
                    return True, f"{served} now serves {b['function']}"
                if self.genesis.construction_ready(b["function"]):
                    # once: the engine a construction needs was attached, so Genesis can now form it
                    return True, "the engine this function is constructed over is now attached"
                lifted = " ".join(e.payload.get("why", "") for e in self.journal.replay("mission.unblocked")
                                  if e.payload["mission_id"] == m.mission_id)
                fresh = [k for k in self.genesis.recovered_for(b["function"]) if k not in lifted]
                if fresh:   # once per recovery: re-admission is offered under the mission's own scope
                    return True, f"recovered and eligible again: {fresh[0]}"
                return False, why
            return ok, why
        if b["type"] == "no_strategy":
            return True, "re-evaluate strategies at cadence"
        if b["type"] == "outage":                # _after_outage re-runs the search when its back-off elapses
            return False, "host outage: the search re-runs after the back-off"
        if b["type"] == "human_work":            # an answer is not the work; only observing the deliverable is
            return False, f"awaiting the deliverable for {b['function']}; GREG does not perform or fake it"
        return False, "unknown blocker"

    def _schedule(self, m: MissionState, now: datetime, seconds: int):
        at = iso(now + timedelta(seconds=seconds))
        self.journal.record("mission.schedule", {"mission_id": m.mission_id, "next_observe_at": at},
                            key=[m.mission_id, "schedule", at])
        m.next_observe_at = at

    def _awaiting_approval(self, m: MissionState) -> bool:
        """Blocked on the founder's still-open answer to an APPROVAL for one exact strategy scope."""
        b = m.blocker or {}
        rid = b.get("request_id")
        return (b.get("type") == "decision" and bool(b.get("action_id")) and rid not in self.book.answers
                and rid not in self.book.withdrawn and (self.book.requests.get(rid) or {}).get("kind") == "APPROVAL")

    def _withdraw_spent_paid_asks(self, m: MissionState, now: datetime) -> MissionState:
        """A paid APPROVAL names the spend state it was asked at (#157); once the mission spends, an approve of it
        could fund nothing. Withdraw it (a body event, never a founder answer) so every open ask is one an approve
        can run; when it was the blocker, the loop goes on and asks again at the current spend."""
        stale = []
        for rid, r in self.book.requests.items():
            if r.get("kind") != "APPROVAL" or r.get("mission_id") != m.mission_id or rid in self.book.answers \
                    or rid in self.book.withdrawn or r.get("move_digest", r.get("scope_digest")) == r.get("scope_digest"):
                continue                       # another mission's, answered, withdrawn, unpaid, or recorded before
            evidence = r.get("evidence") if isinstance(r.get("evidence"), dict) else {}
            state = evidence.get("budget") if isinstance(evidence.get("budget"), dict) else None
            # The paid scope binds what the budget must cover (booked spend plus #173's reservations of unknown
            # outcomes, ``committed_usd``), so a reservation made or released since the ask makes it unfundable too.
            then = float(state.get("spent_usd", 0.0)) + float(state.get("reserved_usd", 0.0)) if state else None
            if state is None or (abs(then - m.committed_usd) < 1e-9 and state.get("budget_usd") == m.cone.budget_usd):
                continue
            stale.append((rid, state))
        for rid, state in stale:
            then = float(state.get("spent_usd", 0.0)) + float(state.get("reserved_usd", 0.0))
            why = (f"the mission has spent since this paid move was asked (${then:.2f} "
                   f"then, ${m.committed_usd:.2f} now): an approve of it could fund nothing, so it is asked again at the "
                   "current spend")
            self.journal.record("decision.withdrawn", {"request_id": rid, "mission_id": m.mission_id, "why": why,
                                                       "at": iso(now)}, key=[rid, "withdrawn"])
            if (m.blocker or {}).get("request_id") == rid:
                self._unblock(m, why)
        if stale:
            self.book.rebuild()
            m = self.book.missions[m.mission_id]
        return m

    def _inside_cone(self, m: MissionState, s: dict, now: datetime) -> bool:
        """A static strategy whose exact scope the mission's signed light cone admits now (no decision needed)."""
        try:
            return not strategy_scope(m, self.registry.manifests, s["action_id"], now=now)["outside_cone"]
        except MissionError:
            return False

    def _prepare(self, m: MissionState, now: datetime) -> dict:
        """Permitted preparation while the founder decides (a goal pulled this mission; Mission F).

        The mission re-observes its current checks through the Gate and pursues the failing checks the
        awaited strategy does not advance, with in-cone static strategies only. The decision stays open
        and its blocker stays in place; nothing new is asked. The pull stays pending while a repair
        awaits its re-observation and is served (``mission.prepared``) once nothing more can be done."""
        pending = m.blocker["action_id"]
        rid = m.blocker["request_id"]
        failing, evidence = self._observe(m, now)
        if failing is None:                  # the sensor itself needs a capability or a decision
            return {"state": "BLOCKED", "blocker": m.blocker}
        self.book.rebuild()
        m = self.book.missions[m.mission_id]
        self._record_routing_outcomes(m)
        awaited = next((set(s["advances"]) for s in m.spec["strategies"] if s["action_id"] == pending), set())
        observed = {c["check_id"] for c in m.current_checks()}
        if awaited and awaited <= observed and not awaited & failing:
            # The world already satisfies what the awaited move would do (no GREG action): the ask is moot.
            # Withdrawn as _watch_while_blocked withdraws one (a body event, never a founder answer); the
            # awaited move never runs on it, and the same scope returning later is a new escalation.
            why = ("world re-observed while preparing: every check the awaited move advances now passes without "
                   "any GREG action")
            self.journal.record("decision.withdrawn", {"request_id": rid, "mission_id": m.mission_id, "why": why,
                                                       "evidence": evidence, "at": iso(now)}, key=[rid, "withdrawn"])
            self._unblock(m, why)
            self.book.rebuild()
            if failing:
                return {"state": "RESUMED", "withdrawn": rid, "still_failing": sorted(failing)}
            return self._setpoint_reached(self.book.missions[m.mission_id], now, evidence)
        other = failing - awaited - set(self.sensor_errors)
        if other:
            done = self._pursue(m, now, other, evidence, prepare_for=pending)
            if done.get("state") == "ACTED":
                return {"state": "PREPARING", "awaiting": rid, "action": done["action"], "repairing": sorted(other)}
            if done.get("state") not in ("NOTHING_TO_PREPARE", "REPLANNING"):
                return done                  # e.g. an uncertain outcome now needs reconciliation
        self.journal.record("mission.prepared", {"mission_id": m.mission_id, "awaiting": rid, "pull": m.pull,
                                                 "still_failing": sorted(failing), "at": iso(now)},
                            key=[m.mission_id, "prepared", m.pull])
        return {"state": "WAITING", "blocker": m.blocker, "prepared": True, "still_failing": sorted(failing)}

    def _step(self, m: MissionState, now: datetime) -> dict:
        if m.status in TERMINAL:
            if m.status == "ACHIEVED":
                return {"state": m.status}
            if m.uncertain and self._unsettled(m) is not None:
                # A question lost to a crash, or a reconciliation block a later decision displaced (the horizon's
                # SCOPE_RENEWAL), is asked (an open one reused) before anything is undone.
                self._resume_unsettled(m, now, displace=True)
                self.book.rebuild()
                m = self.book.missions[m.mission_id]
            if m.blocker and m.blocker.get("type") == "reconciliation":
                # Nothing is undone before the founder says what an interrupted dispatch did: compensation
                # waits for the answer, and an answer that arrives with or after the end is still recorded.
                if m.blocker["request_id"] not in self.book.answers:
                    return {"state": m.status, "compensation": [{"state": "AWAITING_RECONCILIATION",
                                                                 "request_id": m.blocker["request_id"]}]}
                asked_again = self._record_reconciliation(m, now)
                if asked_again is not None:
                    return {**asked_again, "state": m.status}
                self._unblock(m, "founder reconciliation recorded after the mission ended")
                self.book.rebuild()
                m = self.book.missions[m.mission_id]
            return {"state": m.status, **self._compensate(m, now)}
        if m.paused:
            return {"state": "PAUSED"}
        recovered = self._recover_dispatch(m, now)   # a dispatch the body died inside is settled first
        if recovered is not None:
            return recovered
        resumed = self._resume_unsettled(m, now)     # no blocker: a question a crash lost comes next
        if resumed is not None:
            return resumed
        # A shared body-level attach ask withdrawn under the mission is not this mission's withdraw site: the
        # mission's own handling asks about its undecided candidates (``_shared_ask_lapsed``).
        if m.blocker and m.blocker.get("request_id") in self.book.withdrawn and not m.blocker.get("shared_ask"):
            m = self._finish_withdrawal(m)
        m = self._withdraw_spent_paid_asks(m, now)   # a paid ask the mission's spend has made unfundable
        # An open reconciliation stays the blocker past the horizon: its answer is recorded first, then renewal.
        if datetime.fromisoformat(m.cone.horizon.replace("Z", "+00:00")) <= now and \
                (m.blocker or {}).get("type") != "reconciliation":
            self._block(m, {"type": "decision", "request_id": self._request(
                m, kind="SCOPE_RENEWAL", scope_digest=sha256_json({"horizon": m.cone.horizon}), action_id=None,
                why="the mission mandate horizon expired", recommendation="renew with a new signed MISSION",
                requested={"horizon": "extend", "spend": "none beyond the renewed mission's own budget"}, now=now,
                resource={"resource": "mandate", "evidence": {"horizon": m.cone.horizon, "observed_at": iso(now),
                                                             "spent_usd": m.spent_usd,
                                                             **({"reserved_usd": m.reserved_usd}
                                                                if m.reserved else {}),
                                                             "budget_usd": m.cone.budget_usd},
                          "expected_effect": "the mission resumes inside a renewed, founder-signed mandate",
                          "uncertainty": "GREG cannot know whether this goal still matters to you; its value is "
                                         "not re-measured here",
                          "options": [
                              {"option": "renew with a new signed MISSION", "cost": "none in money; your signature",
                               "expected_effect": "the mission resumes with the scope and budget you sign"},
                              {"option": "renew with narrower scope", "cost": "none in money; your signature",
                               "expected_effect": "the mission resumes with less authority"},
                              self._abandon_option(m)]}),
                "why": "mandate expired", "reconsider": "founder renews or abandons"})
            return {"state": "BLOCKED", "blocker": m.blocker}
        if m.blocker and m.blocker.get("type") == "outage":
            return self._after_outage(m, now)
        if m.blocker and m.blocker.get("failing_checks") and not self._blocker_resolved(m)[0]:
            return self._watch_while_blocked(m, now)
        if m.blocker:
            resolved, why = self._blocker_resolved(m)
            if not resolved and self._shared_ask_lapsed(m):
                # the shared ask no longer stands for this mission's need and part of it was never decided: that part
                # is asked about once, on another standing ask naming an undecided candidate or on the mission's own
                # ask naming only those; an attach of any method that fits the need still resolves it
                self._escalate_capability(m, m.blocker["function"], m.blocker.get("capability_id"),
                                          self._deficit_purpose(m, m.blocker["function"]), now,
                                          keep=m.blocker.get("attach_candidates", ()))
                return {"state": "BLOCKED", "blocker": m.blocker}
            if not resolved:
                if m.pull is not None and self._awaiting_approval(m):
                    # Preparation dispatches while the APPROVAL stays open: a question a crash lost comes first.
                    resumed = self._resume_unsettled(m, now, displace=True)
                    if resumed is not None:
                        return resumed
                    return self._prepare(m, now)
                return {"state": "WAITING", "blocker": m.blocker, "why": why}
            if m.blocker["type"] == "capability" and not m.blocker.get("shared_ask") \
                    and not self._closed(m.blocker["request_id"]):
                # this mission's own attach ask is moot once a capability resolves it; a shared ask stays open for
                # its other uses
                rid = m.blocker["request_id"]
                self.journal.record("decision.withdrawn", {"request_id": rid, "mission_id": m.mission_id,
                                                           "why": f"resolved: {why}", "evidence": [], "at": iso(now)},
                                    key=[rid, "withdrawn", "resolved"])
            if m.blocker["type"] == "reconciliation":
                asked_again = self._record_reconciliation(m, now)
                if asked_again is not None:
                    return asked_again
            lifted = m.blocker
            self._unblock(m, why)
            self.book.rebuild()
            m = self.book.missions[m.mission_id]
            if lifted["type"] == "capability" and lifted.get("function") and self.genesis is not None \
                    and self.genesis.serving(m.mission_id, lifted["function"]) is None:
                # Lifted because a construction's engine was attached (or a capability recovered): form the
                # construction now, since the step that reported the deficit does not repeat. It still waits for
                # its own attach. A need something now serves (Genesis.serving: an attached capability, or for a
                # cognition residual a fitting method that can run) is not re-formed: the next step uses it.
                function = lifted["function"]
                purpose = f"construction of {function} over its attached engine"
                formed, deferred = self._form(m, function, now, lambda: self.genesis.resolve(
                    mission=m, function=function, purpose=purpose, now=now), purpose=purpose)
                if deferred:
                    return {"state": "BLOCKED", "blocker": m.blocker}
                if formed is None:
                    waiting = [c.capability_id for c in self.registry.by_function(function)
                               if self.registry.state[c.capability_id] == "VERIFIED"]
                    self._escalate_capability(m, function, waiting[-1] if waiting else None, purpose, now,
                                              awaiting=bool(waiting))
                    return {"state": "BLOCKED", "blocker": m.blocker}
        if m.next_observe_at and now < datetime.fromisoformat(m.next_observe_at.replace("Z", "+00:00")):
            return {"state": "WAITING", "until": m.next_observe_at}

        failing, evidence = self._observe(m, now)
        if failing is None:
            return {"state": "BLOCKED", "blocker": m.blocker}
        # Fresh observations may reveal a surprise; decide on the updated truth.
        self.book.rebuild()
        m = self.book.missions[m.mission_id]
        self._record_routing_outcomes(m)
        if not failing:
            return self._setpoint_reached(m, now, evidence)
        repaired = self._self_repair(m, now)
        if repaired is not None:
            return repaired
        errors = set(self.sensor_errors)
        if errors and errors == failing:
            # The world was not measured; that is not a failed goal. Back off and
            # re-observe; escalate once after repeated measurement failure.
            streak = 0
            for obs in reversed([e.payload for e in self.journal.replay("mission.observed")
                                 if e.payload["mission_id"] == m.mission_id]):
                if obs["check_id"] in errors and not measured(obs):
                    streak += 1
                else:
                    break
            if streak >= 3:
                rid = self._request(m, kind="SENSOR_FAILURE", scope_digest=sha256_json(sorted(errors)), action_id=None,
                                    why="the mission cannot measure its success checks",
                                    recommendation="repair or replace the sensor capability, or revise the check",
                                    alternatives=["attach another capability for this function", "abandon"],
                                    requested={"checks": sorted(errors)}, now=now)
                self._block(m, {"type": "decision", "request_id": rid, "why": "repeated sensor failure",
                                "reconsider": "founder repairs sensing"})
                return {"state": "BLOCKED", "blocker": m.blocker}
            self._schedule(m, now, 30 * streak or 30)
            return {"state": "SENSOR_RETRY", "checks": sorted(errors)}
        return self._pursue(m, now, failing, evidence)

    def _settle_uncertain(self, m: MissionState, s: dict, manifest, record: dict, now: datetime) -> dict:
        """An UNCERTAIN dispatch of a non-retry-safe action (``record``, its retained mission.action), never
        retried blind: settled by the founder's standing mandate when the retained facts prove it inert, else one
        reconciliation question naming exactly this dispatch (#173: its attempt, proposal and grant, with the cap
        reserved and what each answer books). Called when the dispatch is recorded, and again after a restart that
        found the record unsettled."""
        aid, attempt = record["action_id"], record["attempt"]
        proof = self._inert_interruption(m, s, manifest) if manifest is not None else \
            {"holds": False, "predicates": {"founder_mandate": False}}
        if proof["holds"]:
            # The founder signed a standing mandate for exactly this class, and the retained facts prove the
            # interrupted run could not have left a consequence: settle it with the proof, retry once.
            self.journal.record("mission.action", {
                "mission_id": m.mission_id, "action_id": aid, "attempt": attempt,
                "status": "RECONCILED_NOT_EXECUTED", "capability": manifest.capability_id,
                "route": "standing_reconciliation", "dispatch_route": manifest.route, "receipt": None,
                "at": iso(now), "mandate": m.command_digest, "proof": proof, "cost_usd": 0.0,
                "reasons": ["standing reconciliation: a consequence-inert interruption, settled under the "
                            "founder-signed mission mandate"]},
                key=[m.mission_id, aid, "standing", attempt])
            return {"state": "RETRYING", "action": aid, "why": "standing reconciliation of an inert interruption"}
        unmet = [k for k, ok in proof["predicates"].items() if not ok]
        # One reconciliation per dispatch: the request names this attempt's proposal and grant, so the answer
        # settles exactly this dispatch and a later uncertain dispatch opens its own request.
        dispatch = {"attempt": attempt, "proposal_id": record.get("proposal_id"), "grant_id": record.get("grant_id")}
        capability = record.get("capability") or getattr(manifest, "capability_id", None)
        reserved = m.reserved.get((aid, attempt), signed_cost(m.spec, aid))
        recommendation, booked_by_answer = reconciliation_terms(capability, reserved)
        rid = self._request(m, kind="RECONCILIATION", scope_digest=record.get("scope_digest") or "", action_id=aid,
                            why="an action may or may not have executed before an interruption"
                            + ("; GREG could not settle it under your standing mandate: " + ", ".join(unmet)
                               if proof["predicates"]["founder_mandate"] else ""),
                            recommendation=recommendation,
                            alternatives=["reconcile_executed", "reconcile_not_executed"],
                            requested={"action_id": aid, **dispatch}, now=now, instance=dispatch,
                            evidence={"dispatch": dispatch, "reasons": list(record.get("reasons", []))[:3],
                                      "reserved_usd": reserved,
                                      "booked_usd_by_answer": booked_by_answer,
                                      "budget": {"spent_usd": m.spent_usd, "budget_usd": m.cone.budget_usd}})
        self._block(m, {"type": "reconciliation", "request_id": rid, "action_id": aid, **dispatch,
                        "scope_digest": record.get("scope_digest"), "capability": capability,
                        "why": "uncertain completion; no blind retry",
                        "reconsider": "founder reconciliation decision"})
        return {"state": "BLOCKED", "blocker": m.blocker}

    def _resume_unsettled(self, m: MissionState, now: datetime, *, displace: bool = False) -> dict | None:
        """A dispatch recorded UNCERTAIN whose settlement never became durable: the body died after that record
        and before its reconciliation question (or the block on it) was retained. Settle it now, exactly as the
        dispatch would have, instead of letting the next tick dispatch the next attempt with no answer.

        ``displace``: another blocker (a goal's open APPROVAL during preparation, the horizon's SCOPE_RENEWAL on an
        ended mission) stands where the reconciliation block would have been. It is lifted first, as the dispatch
        itself would have replaced it, so the question comes before anything else is dispatched or undone; the
        lifted decision stays open and is asked again by the path that raised it."""
        if (m.blocker or {}).get("type") == "reconciliation" or (m.blocker is not None and not displace):
            return None
        unsettled = self._unsettled(m)
        if unsettled is None:
            return None
        if m.blocker is not None:
            self._unblock(m, "an interrupted dispatch is reconciled before anything else is dispatched or undone")
            self.book.rebuild()
            m = self.book.missions[m.mission_id]
        return self._settle_uncertain(m, *unsettled, now)

    def _unsettled(self, m: MissionState):
        """The first non-retry-safe action whose latest record is UNCERTAIN: (strategy, manifest, that record),
        or None."""
        for aid, record in sorted(m.uncertain.items()):
            strategy = next((x for x in m.spec["strategies"] if x["action_id"] == aid), None)
            manifest = self.registry.manifests.get(record.get("capability"))
            if manifest is None and strategy is not None:
                manifest = self._manifest_for(strategy)
            if strategy is None or (manifest is not None and manifest.retry_safe):
                continue
            return strategy, manifest, record
        return None

    def _inputs(self, m: MissionState, s: dict) -> tuple[tuple[dict, list, list], tuple | None]:
        """A strategy's typed inputs, resolvable and consumable now: signed ``bind`` edges, then inline
        ``$from_action`` references, both read from this mission's retained Gate receipts, and every
        producer's output accepted by its independent appraiser where it has one (``_handoff_hold``).
        Returns (bound params, bindings, sources) and the inline resolution (or None). Raises Unbound or
        BindingError while an input cannot be used: the one hold rule ``_pursue`` selects under and
        ``_askable`` asks ahead under."""
        from greg.pipeline import resolve
        bound = self._bind(m, s) if s.get("bind") else (s.get("params", {}), [], [])
        resolve(bound[0], self.journal, m.mission_id)
        inline = resolve(s.get("params", {}), self.journal, m.mission_id) \
            if inline_refs(s.get("params", {})) else None
        links = [(b["from_action"], b["from_receipt"]) for b in bound[1] if "from_action" in b]
        links += [(p["action_id"], p["receipt"]) for p in (inline[1] if inline else [])]
        holds = [h for h in (self._handoff_hold(m, producer, receipt) for producer, receipt in links) if h]
        if holds:
            raise Unbound("; ".join(holds))
        return bound, inline

    def _held(self, m: MissionState, s: dict) -> bool:
        from greg.pipeline import BindingError
        try:
            self._inputs(m, s)
        except (Unbound, BindingError):
            return True
        return False

    def _bind(self, m: MissionState, s: dict) -> tuple[dict, list, list]:
        """Resolve a strategy's typed input edges from retained Gate receipts of this mission.

        The source is the latest DONE action of the named strategy; its output is read from
        the canonical ledger, never from a cache or the adapter's memory. Only param values
        change: capability, target, cost and consequence class stay exactly as signed."""
        latest = {}   # action_id -> receipt of its latest DONE; None when the founder reconciled it unreceipted
        for event in self.journal.replay("mission.action"):
            data = event.payload
            if data.get("mission_id") == m.mission_id and data.get("status") == "DONE":
                latest[data["action_id"]] = data.get("receipt")
        params = json.loads(json.dumps(s.get("params", {})))
        bindings, sources = [], []
        for edge in s["bind"]:
            if protected_param(edge["param"]):   # a mission retained from before registration refused this
                raise Unbound(f"bind onto {edge['param']} is refused: {protected_param(edge['param'])!r} is protected "
                              "and stays a founder-signed literal")
            if "check_id" in edge["from"]:
                source = edge["from"]["check_id"]
                passing = [e.payload["receipt"] for e in self.journal.replay("mission.observed")
                           if e.payload.get("mission_id") == m.mission_id and e.payload.get("check_id") == source
                           and e.payload.get("passed") and e.payload.get("receipt")]
                receipt = passing[-1] if passing else None
                if receipt is None:
                    raise Unbound(f"check {source} has no passing observation yet")
            else:
                source = edge["from"]["action_id"]
                if source not in latest:
                    raise Unbound(f"{source} has no completed action yet")
                receipt = latest[source]
                if receipt is None:     # never an older receipt: that output is not the latest execution's
                    raise Unbound(f"{source}'s latest execution was reconciled without a retained receipt; "
                                  "its output is unknown")
            record = self.office.ledger.find(receipt)
            if record is None or record.record_type != "receipt":
                raise Unbound(f"{source} receipt {receipt[:19]} is not on the ledger")
            value = bound_value(edge, record.payload.get("result", {}).get("output"))
            _set_path(params, edge["param"], value)
            bindings.append({"param": edge["param"], ("from_check" if "check_id" in edge["from"] else "from_action"): source,
                             "from_receipt": receipt,
                             "field": edge["from"]["field"], "value_sha256": sha256_json({"v": value})})
            sources.append(receipt)
        return params, bindings, sources

    def _handoff_hold(self, m: MissionState, producer: str, receipt: str) -> str | None:
        """Why a typed handoff may not consume ``producer``'s output (its retained ``receipt``) yet, or None.

        An output whose producer has an independent appraiser (APPRAISED_PRODUCERS) is consumed only after this
        mission observed that appraisal, later than the receipt, accept it: never before, never if it rejected.
        A producer without an appraiser hands over its receipted output (integrity evidence) as before."""
        strategy = next((x for x in m.spec["strategies"] if x["action_id"] == producer), None)
        rule = APPRAISED_PRODUCERS.get(strategy.get("capability")) if strategy else None
        if rule is None:
            return None
        appraiser, key, field, accepted = rule
        ledger = self.journal.ledger
        record = ledger.find(receipt)
        output = (record.payload.get("result") or {}).get("output") if record is not None else None
        instance = output.get(field) if isinstance(output, dict) else None
        checks = {c["check_id"] for c in m.spec["success_checks"] if c["sensor"].get("capability") == appraiser
                  and (c["sensor"].get("params") or {}).get(key) == instance}
        if record is None or not checks:
            return f"{producer}'s output has no independent appraisal ({appraiser}) in this mission"
        latest = None
        for event in self.journal.replay("mission.observed"):
            data = event.payload
            if data.get("mission_id") != m.mission_id or data.get("check_id") not in checks or not data.get("receipt"):
                continue
            seen = ledger.find(data["receipt"])
            if seen is not None and seen.seq > record.seq:
                latest = seen
        if latest is None:
            return f"awaiting the independent appraisal ({appraiser}) of {producer}'s output"
        verdict = ((latest.payload.get("result") or {}).get("output") or {}).get("verdict")
        if verdict != accepted:
            return (f"the independent appraisal of {producer}'s output is {verdict}, not {accepted}; "
                    "a rejected output is never consumed")
        return None

    def _self_repair(self, m: MissionState, now: datetime):
        """A formed capability that faults twice in a row on the same check is re-formed, not escalated."""
        for check_id, (manifest, detail, params) in sorted(self.capability_faults.items()):
            # Only faults of *this* implementation count: a replacement starts with a clean record.
            since = max((e.payload["at"] for e in self.journal.replay("deficit.resolved")
                         if e.payload["capability_id"] == manifest.capability_id), default="")
            streak = 0
            for obs in reversed([e.payload for e in self.journal.replay("mission.observed")
                                 if e.payload["mission_id"] == m.mission_id and e.payload["check_id"] == check_id]):
                if obs["at"] < since or not is_capability_fault(manifest, obs["detail"], obs.get("failure_class")):
                    break
                streak += 1
            if streak < 2:
                continue
            repaired, deferred = self._form(m, manifest.function, now, lambda: self.genesis.repair(
                mission=m, capability_id=manifest.capability_id, failure=detail, params=params, now=now),
                purpose=f"self-repair of {manifest.capability_id}")
            if deferred:
                return {"state": "BLOCKED", "blocker": m.blocker}
            if repaired is not None:   # the next tick re-measures with the re-formed capability
                return {"state": "REPAIRED", "replaced": manifest.capability_id, "by": repaired.capability_id}
            self._escalate_capability(m, manifest.function, None, f"self-repair of {manifest.capability_id}", now)
            return {"state": "BLOCKED", "blocker": m.blocker}
        return None

    def _observe(self, m: MissionState, now: datetime):
        failing, evidence = set(), []
        sensor_errors = self.sensor_errors = set()
        self.capability_faults = {}
        self.disagreements = {}
        for check in m.current_checks():
            sensor = check["sensor"]
            failure_class = None          # typed where a capability failure was raised, when one was
            manifest, adapter, missing = self._resolve(sensor)
            if manifest is None:
                self._deficit(m, sensor, now, purpose=f"sensor for {check['check_id']}")
                return None, None
            if manifest.consequence_class != "read_only":
                self._block(m, {"type": "no_strategy", "why": f"sensor {manifest.capability_id} is not read-only"})
                return None, None
            # A new observation must not reuse a prior sensor receipt merely
            # because the wall clock repeated its timestamp (clock freeze/NTP).
            # The journal survives process death; count only this check's
            # retained observations so each completed read gets a new attempt.
            attempt = sum(1 for e in self.journal.replay("mission.observed")
                          if e.payload.get("mission_id") == m.mission_id
                          and e.payload.get("check_id") == check["check_id"])
            from greg.pipeline import resolve, PendingInput, BindingError
            try:
                bound_params, input_bindings = resolve(sensor.get("params", {}), self.journal, m.mission_id)
            except (PendingInput, BindingError) as exc:
                failing.add(check["check_id"])
                self.journal.record("mission.input_wait", {"mission_id": m.mission_id,
                    "check_id": check["check_id"], "why": str(exc)}, key=[m.mission_id, check["check_id"], str(exc)])
                continue
            outcome = self.office.act(
                mission_id=m.mission_id, cone=m.cone, command_digest=m.command_digest, manifest=manifest,
                adapter=adapter, ctx=self._context(m, manifest), params=bound_params,
                target=sensor["target"], cost_usd=0.0, expected_outcome="observation captured",
                evidence_refs=[], attempt=f"{attempt}@{iso(now)}", spent_usd=m.committed_usd,
                approved_scopes=m.approved_scopes)
            if outcome.status != "DONE":
                if outcome.status in ("OUTSIDE_SCOPE", "NEEDS_DECISION"):
                    rid = self._request(m, kind="SENSOR_SCOPE", scope_digest=outcome.scope_digest, action_id=None,
                                        why=f"sensor for {check['check_id']} is outside the mission scope",
                                        recommendation="approve this exact read-only observation or narrow the check",
                                        alternatives=["reject and revise the success check"],
                                        requested={"capability": manifest.capability_id, "target": sensor["target"]},
                                        now=now)
                    self._block(m, {"type": "decision", "request_id": rid, "why": "; ".join(outcome.reasons)})
                    return None, None
                passed, detail = False, "sensor " + outcome.status + ": " + "; ".join(outcome.reasons)[:200]
                sensor_errors.add(check["check_id"])
                failure_class = outcome.failure_class
                if self.genesis is not None and is_capability_fault(manifest, detail, failure_class):
                    self.capability_faults[check["check_id"]] = (manifest, detail, sensor.get("params", {}))
            else:
                passed, detail = evaluate_predicate(check["predicate"], outcome.output)
                fault = outcome.output.get("capability_fault") if isinstance(outcome.output, dict) else None
                if not passed and isinstance(fault, dict) and self.genesis is not None \
                        and fault.get("capability_id") in self.registry.manifests:
                    # A construction the Mind invoked faulted: attribute it to that capability, so the
                    # same two-strike self-repair re-forms it (cognition itself did not fail).
                    formed = self.registry.manifests[fault["capability_id"]]
                    detail = f"{detail}; {str(fault.get('detail'))[:300]}"
                    failure_class = fault.get("failure_class")
                    if is_capability_fault(formed, detail, failure_class):
                        self.capability_faults[check["check_id"]] = (formed, detail, sensor.get("params", {}))
                    elif failure_class in ("transient", "budget_exceeded"):
                        # The host (or a resource ceiling) stopped the construction: the world was not
                        # measured. The SENSOR_RETRY path applies; no strategy is blamed for it.
                        detail = f"sensor inconclusive ({failure_class}): {detail}"
                        sensor_errors.add(check["check_id"])
                views = disagreement(outcome.output)
                if views and not passed:
                    self.disagreements[check["check_id"]] = {**views, "observation": outcome.receipt_hash}
                why = None if passed else unanswered(outcome.output)
                if why:
                    # The receipt abstained: the world was not measured. The mission keeps its
                    # retry cadence (learned routing settles the lead engine's resource failure
                    # from these retries); _record_routing_outcomes never blames the strategy.
                    detail = f"sensor inconclusive ({why}): {detail}"
            data = {"mission_id": m.mission_id, "check_id": check["check_id"], "passed": passed,
                    "detail": detail[:300], "receipt": outcome.receipt_hash, "rung": m.rung, "at": iso(now),
                    "capability": manifest.capability_id}     # the sensor as resolved (a spec may name a function)
            if failure_class is not None:
                data["failure_class"] = failure_class
            self.journal.record("mission.observed", data, key=[m.mission_id, check["check_id"], outcome.proposal_id])
            if outcome.receipt_hash:
                evidence.append(outcome.receipt_hash)
            if not passed:
                failing.add(check["check_id"])
        return failing, evidence

    def _record_routing_outcomes(self, m: MissionState):
        """Close the routing loop: an executed strategy that did not change the world
        lowers its capability's reliability for every future mission."""
        for aid, reason in m.failed.items():
            if not blames_strategy(reason):
                continue
            done = [e.payload for e in self.journal.replay("mission.action")
                    if e.payload["mission_id"] == m.mission_id and e.payload["action_id"] == aid
                    and e.payload["status"] == "DONE" and e.payload.get("capability")]
            # A founder reconciliation has no receipt: it is not a receipted execution to blame.
            if done and done[-1].get("receipt"):
                last = done[-1]
                # A dispatch the founder reconciled as executed has no receipt: it is identified by its attempt.
                which = last.get("receipt") or ["reconciled attempt", last["attempt"]]
                self.journal.record("routing.outcome", {"mission_id": m.mission_id, "action_id": aid,
                                                        "capability": last["capability"], "verdict": "ineffective",
                                                        "receipt": last.get("receipt"), "reason": reason[:300]},
                                    key=[m.mission_id, aid, which])

    def _watch_while_blocked(self, m: MissionState, now: datetime) -> dict:
        """No strategy is not blindness: keep re-observing at cadence. If the world heals
        without GREG acting, the escalation is withdrawn as moot (a body event, never a
        founder answer) and the mission resumes; otherwise it keeps waiting, silently."""
        if m.next_observe_at and now < datetime.fromisoformat(m.next_observe_at.replace("Z", "+00:00")) \
                and not self._deliverable_arrived(m):
            return {"state": "WAITING", "blocker": m.blocker, "until": m.next_observe_at}
        failing, evidence = self._observe(m, now)
        if failing is None:
            return {"state": "BLOCKED", "blocker": m.blocker}
        if failing and self.capability_faults and m.blocker["type"] != "human_work":
            # A formed capability faulting is repairable machinery, not a reason to wait on the founder:
            # the same two-strike self-repair runs; the next observation then withdraws a moot blocker.
            repaired = self._self_repair(self.book.missions[m.mission_id], now)
            if repaired is not None and repaired["state"] == "REPAIRED":
                return repaired
        human = m.blocker["type"] == "human_work"   # it waits only on the checks the person's work advances
        waiting_on = failing & set(m.blocker["failing_checks"]) if human else failing
        if waiting_on and human:
            declined = self._declined(m, now)
            if declined is not None:
                return self._honor_refusal(m, now, *declined)
        if waiting_on:
            self._schedule(m, now, m.spec["closure"].get("cadence_seconds", 3600))
            return {"state": "WAITING", "blocker": m.blocker, "still_failing": sorted(failing)}
        rid = m.blocker["request_id"]
        why = ("the deliverable is observed: the checks this work advances now pass, and GREG took no action for it"
               if human else "world re-observed: every failing check now passes without any GREG action")
        if not m.blocker.get("shared_ask"):      # an ask this mission only shares stays open for its other uses
            self.journal.record("decision.withdrawn", {"request_id": rid, "mission_id": m.mission_id, "why": why,
                                                       "evidence": evidence, "at": iso(now)}, key=[rid, "withdrawn"])
        self._unblock(m, why)
        self.book.rebuild()
        if failing:                                  # other checks remain: pursue them from the next step
            resumed = self.book.missions[m.mission_id]
            if resumed.next_observe_at and now < datetime.fromisoformat(resumed.next_observe_at.replace("Z", "+00:00")):
                self._schedule(resumed, now, 0)      # observed early: the next step must not wait out the old slot
            return {"state": "RESUMED", "still_failing": sorted(failing)}
        return self._setpoint_reached(self.book.missions[m.mission_id], now, evidence)

    def _deliverable_arrived(self, m: MissionState) -> bool:
        """A person's work landed since GREG last looked: observe now, not at the next cadence slot.

        Only for a human_work blocker, only the file paths the founder-signed mission's own read-only
        sensors name in their ``path`` param (the checks this work advances, and its declined_if), and only their metadata:
        no content is read, no grant is issued and nothing is recorded until the governed
        observation runs. ctime counts as well as mtime, because a downloaded or copied file keeps
        an old mtime but gets a new ctime when it lands. Without this, an hourly cadence left each
        of a business case's four human steps unnoticed for up to an hour.
        """
        if m.blocker.get("type") != "human_work" or not m.next_observe_at:
            return False
        last = datetime.fromisoformat(m.next_observe_at.replace("Z", "+00:00")) - timedelta(
            seconds=m.spec["closure"].get("cadence_seconds", 3600))
        waiting = set(m.blocker.get("failing_checks", []))
        sensors = [c["sensor"] for c in m.spec["success_checks"] if c["check_id"] in waiting]
        strategy = next((s for s in m.spec["strategies"] if s["action_id"] == m.blocker.get("action_id")), None)
        if strategy and strategy.get("declined_if"):
            sensors.append(strategy["declined_if"]["sensor"])
        for sensor in sensors:
            # Any read-only sensor whose signed params name a file: fs.read, and business.reconcile over
            # the exported statement (the payment step was still noticed only at the hourly slot).
            path = (sensor.get("params") or {}).get("path")
            manifest = self.registry.manifests.get(sensor.get("capability"))
            if manifest is None or manifest.consequence_class != "read_only" or not isinstance(path, str):
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            if max(st.st_mtime, st.st_ctime) > last.timestamp():
                return True
        return False

    def _declined(self, m: MissionState, now: datetime):
        """(detail, receipt) when the person this step waits on is observed to have declined, else None."""
        strategy = next((s for s in m.spec["strategies"] if s["action_id"] == m.blocker.get("action_id")), None)
        watch = (strategy or {}).get("declined_if")
        if not watch:
            return None
        manifest, adapter, _ = self._resolve(watch["sensor"])
        if manifest is None or manifest.consequence_class != "read_only":
            return None                              # an unreadable refusal is never assumed
        attempt = sum(1 for e in self.journal.replay("human.refusal_observed")
                      if e.payload["mission_id"] == m.mission_id)
        outcome = self.office.act(
            mission_id=m.mission_id, cone=m.cone, command_digest=m.command_digest, manifest=manifest,
            adapter=adapter, ctx=self._context(m, manifest), params=watch["sensor"].get("params", {}),
            target=watch["sensor"]["target"], cost_usd=0.0, expected_outcome="observation captured",
            evidence_refs=[], attempt=f"declined:{attempt}@{iso(now)}", spent_usd=m.spent_usd,
            approved_scopes=m.approved_scopes)
        if outcome.status != "DONE":
            return None
        passed, detail = evaluate_predicate(watch["predicate"], outcome.output)
        self.journal.record("human.refusal_observed", {"mission_id": m.mission_id, "action_id": strategy["action_id"],
                                                       "declined": passed, "detail": detail[:300],
                                                       "receipt": outcome.receipt_hash, "at": iso(now)},
                            key=[m.mission_id, strategy["action_id"], outcome.proposal_id])
        return (detail, outcome.receipt_hash) if passed else None

    def _honor_refusal(self, m: MissionState, now: datetime, detail: str, receipt: str | None) -> dict:
        """A person may say no. GREG records it as legitimate, stops asking for that step for good,
        and leaves the next move to Alfonso; it never re-asks, argues or routes around the person."""
        aid, rid, function = m.blocker["action_id"], m.blocker["request_id"], m.blocker["function"]
        why = "the person declined; the refusal is legitimate, and GREG asks nothing more of them in this mission"
        honored = {"mission_id": m.mission_id, "action_id": aid, "function": function, "request_id": rid,
                   "evidence": [receipt] if receipt else [], "detail": detail[:300], "at": iso(now)}
        # A body that died after recording this refusal observes it again on restart: finish that one refusal
        # (its facts are idempotent), never record a second, different one under the same identity.
        honored = next((e.payload for e in self.journal.replay("human.refusal_honored")
                        if e.payload["mission_id"] == m.mission_id and e.payload["action_id"] == aid), honored)
        self.journal.record("human.refusal_honored", honored, key=[m.mission_id, aid, "refusal"])
        self.journal.record("decision.withdrawn", {"request_id": rid, "mission_id": m.mission_id, "why": why,
                                                   "evidence": honored["evidence"], "at": iso(now)},
                            key=[rid, "withdrawn"])
        self._exclude_refused(m, honored)
        self._unblock(m, why)
        self.book.rebuild()
        return {"state": "REFUSAL_HONORED", "action": aid}

    def _setpoint_reached(self, m: MissionState, now: datetime, evidence: list) -> dict:
        closure = m.spec["closure"]
        if closure["kind"] == "bounded":
            self.journal.record("mission.achieved", {
                "mission_id": m.mission_id, "evidence": evidence, "actions_done": m.actions_done,
                "closure_rule": "every success check re-observed passing through the Gate",
                "founder_authenticated_mission": True, "at": iso(now)}, key=[m.mission_id, "achieved"])
            return {"state": "ACHIEVED", "evidence": evidence}
        ladder = closure.get("ladder") or []
        if m.rung + 1 < len(ladder):
            self.journal.record("mission.setpoint", {"mission_id": m.mission_id, "reached_rung": m.rung,
                                                     "next_rung": m.rung + 1, "evidence": evidence, "at": iso(now)},
                                key=[m.mission_id, "rung", m.rung])
            return {"state": "ADVANCED", "rung": m.rung + 1}
        # Homeostasis: the infinite mission holds its highest setpoint and keeps
        # re-verifying it; a later failing check is pursued again. A hold reached
        # after new action is a closure too: it is recorded once and appraised by
        # the separate process, like a bounded mission's achievement.
        held = {e.payload["actions_done"] for e in self.journal.replay("mission.held")
                if e.payload["mission_id"] == m.mission_id}
        if m.actions_done and m.actions_done not in held:
            self.journal.record("mission.held", {
                "mission_id": m.mission_id, "evidence": evidence, "actions_done": m.actions_done,
                "closure_rule": "every success check re-observed passing after new action",
                "at": iso(now)}, key=[m.mission_id, "held", m.actions_done])
        self._schedule(m, now, closure.get("cadence_seconds", 3600))
        return {"state": "HOLDING", "evidence": evidence}

    def _resolve(self, spec: dict):
        cid = spec.get("capability")
        if cid is None and self.genesis is not None:
            found = self.genesis.find_attached(spec["function"])
            cid = found.capability_id if found else None
        if cid is None:
            return None, None, spec.get("function")
        ok, _ = self.registry.usable(cid)
        if not ok and cid in self.registry.manifests and self.registry.state[cid] == "ATTACHED":
            return self.registry.manifests[cid], self.registry.adapters[cid], None  # unavailable is reported by act
        if not ok:
            return None, None, cid
        return self.registry.manifests[cid], self.registry.adapters[cid], None

    def _deficit(self, m: MissionState, spec: dict, now: datetime, *, purpose: str, cognition: dict | None = None):
        function = spec.get("function") or self.registry.manifests.get(spec.get("capability"), None)
        function = function.function if hasattr(function, "function") else (function or spec.get("capability"))
        resource = asks.human_work(function)
        if resource is not None:                  # never searched, built or attached: a person does this work
            return self._escalate_human(m, spec, function, resource, purpose, now)
        if self.genesis is not None:
            # a cognition residual carries the compiler's own deficit (geometry, inputs, fitting methods) to Genesis
            extra = {"deficit": cognition} if cognition is not None else {}
            capability, deferred = self._form(m, function, now, lambda: self.genesis.resolve(
                mission=m, function=function, purpose=purpose, now=now, **extra), purpose=purpose, deficit=cognition)
            if deferred:
                return None
            if capability is not None:
                return capability
        return self._escalate_capability(m, function, spec.get("capability"), purpose, now)

    OUTAGE_DEFERRALS = 5          # consecutive host outages forming one function before the founder is also told
    OUTAGE_RETRY_CAP = 3600       # seconds: the longest back-off between searches during an outage

    def _form(self, m: MissionState, function: str, now: datetime, formation, *, purpose: str, attempt: int = 0,
              deficit: dict | None = None):
        """Run a Genesis formation. A host outage while qualifying (a runner timeout, isolation unavailable)
        is no evidence about any candidate: nothing was qualified, failed or built. The mission waits on an
        outage blocker that re-runs this formation after a growing back-off (``_after_outage``); it does not
        re-observe meanwhile, so no strategy is judged on a capability that could not be formed. From the
        fifth consecutive outage the founder is also asked, and the search keeps re-running.
        Returns (result, deferred)."""
        try:
            return formation(), False
        except CapabilityError as exc:
            if exc.failure_class != "transient":
                raise
            attempt += 1
            blocker = {"type": "outage", "function": function, "purpose": purpose[:200], "attempt": attempt,
                       "why": str(exc)[:200],
                       "retry_at": iso(now + timedelta(seconds=min(60 * 2 ** (attempt - 1), self.OUTAGE_RETRY_CAP))),
                       "reconsider": "the search re-runs after the back-off; nothing was qualified, failed or built"}
            if deficit is not None:
                # the retry searches for the need the compile reported (its fitting rows and what it tried), not
                # for the body as it stands when the back-off ends
                blocker["deficit"] = deficit
            if attempt >= self.OUTAGE_DEFERRALS:
                blocker["request_id"] = self._capability_request(
                    m, function, f"{purpose}: the host failed {attempt} times in a row while forming {function} "
                                 f"({str(exc)[:120]}); GREG keeps re-searching", now,
                    scope={"function": function, "outage": True})
            self._block(m, blocker)
            return None, True

    def _reask_reconciliation(self, m: MissionState, aid: str, uncertain: dict, capability: str | None,
                              now: datetime, why: str, *, terms: str | None = None) -> dict:
        """The retained answer cannot settle the dispatch ``uncertain`` (its UNCERTAIN record): lift the block and ask
        about that dispatch again, with what each answer books. ``terms`` salts the request, so a second question
        about the same dispatch is not the one already answered."""
        self._unblock(m, why)
        self.book.rebuild()
        m = self.book.missions[m.mission_id]
        dispatch = {"attempt": uncertain["attempt"], "proposal_id": uncertain.get("proposal_id"),
                    "grant_id": uncertain.get("grant_id")}
        reserved = m.reserved.get((aid, uncertain["attempt"]), signed_cost(m.spec, aid))
        recommendation, booked_by_answer = reconciliation_terms(capability, reserved)
        again = self._request(m, kind="RECONCILIATION", scope_digest=uncertain.get("scope_digest") or "",
                              action_id=aid, why="an action may or may not have executed before an interruption",
                              recommendation=recommendation,
                              alternatives=["reconcile_executed", "reconcile_not_executed"],
                              requested={"action_id": aid, **dispatch}, now=now,
                              instance=dispatch if terms is None else {**dispatch, "terms": terms},
                              evidence={"dispatch": dispatch, "reasons": list(uncertain.get("reasons", []))[:3],
                                        "reserved_usd": reserved, "booked_usd_by_answer": booked_by_answer})
        self._block(m, {"type": "reconciliation", "request_id": again, "action_id": aid, **dispatch,
                        "scope_digest": uncertain.get("scope_digest"), "capability": capability,
                        "why": "uncertain completion; no blind retry",
                        "reconsider": "founder reconciliation decision"})
        return {"state": "BLOCKED", "blocker": m.blocker}

    def _record_reconciliation(self, m: MissionState, now: datetime) -> dict | None:
        """Record the founder's answer about one UNCERTAIN dispatch (the blocker's request), for a live mission
        or one that ended while the question was open. Returns a state when the founder must be asked again.

        One answer settles exactly the one dispatch its request names. A blocker retained from before requests
        named their dispatch settles the latest attempt, unless its answer predates that attempt's dispatch:
        then it was given about an earlier dispatch, and the founder is asked about this one."""
        rid = m.blocker["request_id"]
        answer = self.book.answers[rid]["answer"]
        aid = m.blocker["action_id"]
        seq = {r.payload.get("event_id"): r.seq for r in self.journal.ledger.by_type("event")}
        uncertain = [e for e in self.journal.replay("mission.action")
                     if e.payload.get("mission_id") == m.mission_id and e.payload.get("action_id") == aid
                     and e.payload.get("status") == "UNCERTAIN"]
        if "proposal_id" not in m.blocker and uncertain:
            answered = [seq[e.event_id] for e in self.journal.replay("decision.answered")
                        if e.payload.get("request_id") == rid]
            latest = uncertain[-1].payload
            if answered and answered[0] < seq[uncertain[-1].event_id]:
                return self._reask_reconciliation(m, aid, latest, latest.get("capability"), now,
                                                  "the retained reconciliation answered an earlier dispatch; asking "
                                                  "about this one")
        attempt = m.blocker.get("attempt", m.attempts.get(aid, 1) - 1)
        # The record reconciles the UNCERTAIN dispatch of this attempt: it names the capability that dispatch
        # actually used (a strategy may name only a function), never the strategy's spec.
        dispatch = next((e.payload for e in reversed(uncertain) if e.payload.get("attempt") == attempt), {})
        if self.journal.retained("mission.action", [m.mission_id, aid, "reconciled", rid]) is not None:
            return None      # recorded before a crash that came before the unblock: never re-stamped
        strategy = next((x for x in m.spec["strategies"] if x["action_id"] == aid), {})
        executed = answer == "reconcile_executed"
        worst = m.reserved.get((aid, attempt), signed_cost(m.spec, aid))
        capability = m.blocker.get("capability") or dispatch.get("capability") or strategy.get("capability")
        # A metered capability (a paid worker) spends while its provider runs, whether or not its result was
        # collected: "not executed" settles the effect, not the money, so its unmeasured spend is booked at the
        # signed cap instead of being released as zero (acceptance H.G4).
        booked = executed or capability in METERED_SPEND
        disclosed = (((self.book.requests.get(rid) or {}).get("evidence") or {})
                     .get("booked_usd_by_answer") or {}).get(answer)
        if not executed and booked and disclosed != worst:
            # Asked before the disclosure (code from before H.G4): the founder answered "not executed" without being
            # told it keeps a metered cap booked, so that answer books nothing on its own. Ask once more about this
            # dispatch, with the terms; the cap stays reserved as unknown spend meanwhile. ("Executed" booked the cap
            # under the old rule too, so its answer was given on the terms it settles at.)
            return self._reask_reconciliation(m, aid, {**dispatch, "attempt": attempt}, capability, now,
                                              "the answered reconciliation did not state what it books; asking "
                                              "again with the terms", terms="booked_usd_by_answer")
        # A receipted interrupt (a cancellable worker stopped itself, its report collected) carries the provider's
        # report: stated as given, though an interrupted run's report does not bound what it spent; one over the
        # cap is booked as reported, never the cap in its place (reconciled_booking).
        receipt = self.office.ledger.find(dispatch["receipt"]) if dispatch.get("receipt") else None
        output = (receipt.payload.get("result") or {}).get("output") \
            if receipt is not None and receipt.record_type == "receipt" else None
        booking = reconciled_booking(capability, answer, worst, output)
        reported, over = booking["provider_reported_usd"], booking["overspend_usd"]
        measured = None if reported is None else (f"its receipted run reported ${reported:.2f} before it was "
                                                  "interrupted, which does not bound what an interrupted run spent")
        settled = {"mission_id": m.mission_id, "action_id": aid, "attempt": attempt,
                   "status": "DONE" if executed else "RECONCILED_NOT_EXECUTED",
                   "capability": capability, "route": "founder_reconciliation",
                   "dispatch_route": dispatch.get("route"), "receipt": None, "at": iso(now),
                   "reasons": ["founder reconciliation: " + answer], "cost_usd": booking["cost_usd"]}
        if "proposal_id" in m.blocker:
            settled.update(reconciles={k: m.blocker.get(k) for k in ("request_id", "proposal_id", "grant_id")},
                           scope_digest=m.blocker.get("scope_digest"))
        if over is not None:   # it reported spending more than signed: that spend is booked, with the overspend
            settled.update(cost_cap_usd=worst, provider_reported_usd=reported, overspend_usd=over,
                           spend_basis="provider_reported: over the signed cap; founder reconciliation: " + answer
                                       + f"; {measured}, so at least the reported spend is booked")
        elif executed:     # it executed, but its spend was never measured: book the signed cap
            settled.update(cost_cap_usd=worst, provider_reported_usd=reported,
                           spend_basis="signed_cap: founder reconciled the dispatch as executed; "
                                       + (measured or "its spend was never measured"))
        elif booked:
            settled.update(cost_cap_usd=worst, provider_reported_usd=reported, spend_basis="signed_cap: " + (
                measured or ("its receipted run was interrupted with no provider report" if receipt is not None
                             else "the dispatch was claimed and never receipted")
                + ", so whether its metered provider ran (the body may have stopped before it started) and what it "
                  "spent are unknown") + "; not executed settles its effect, not that possible spend")
        self.journal.record("mission.action", settled, key=[m.mission_id, aid, "reconciled", rid])
        return None

    def _after_outage(self, m: MissionState, now: datetime) -> dict:
        """The back-off after a host outage elapsed: re-run the formation the outage interrupted."""
        b = m.blocker
        if b.get("retry_at") and now < datetime.fromisoformat(b["retry_at"].replace("Z", "+00:00")):
            return {"state": "WAITING", "blocker": b, "why": "host outage: the search re-runs after the back-off"}
        function = b["function"]
        purpose = b.get("purpose") or f"re-search of {function} after a host outage"
        self._unblock(m, "the back-off after a host outage elapsed; the search re-runs")
        self.book.rebuild()
        m = self.book.missions[m.mission_id]
        if self.genesis is None:
            self._escalate_capability(m, function, None, purpose, now)
            return {"state": "BLOCKED", "blocker": m.blocker}
        deficit = b.get("deficit")
        extra = {"deficit": deficit} if deficit is not None else {}
        formed, deferred = self._form(m, function, now, lambda: self.genesis.resolve(
            mission=m, function=function, purpose=purpose, now=now, **extra), purpose=purpose,
            attempt=b.get("attempt", 0), deficit=deficit)
        if deferred:
            return {"state": "BLOCKED", "blocker": m.blocker}
        rid = b.get("request_id")
        if rid and rid not in self.book.answers and rid not in self.book.withdrawn:
            # The founder was told the host kept failing; the search ran on a working host now, so that ask
            # is moot: the capability is formed, or a real escalation with current evidence replaces it.
            self.journal.record("decision.withdrawn", {
                "request_id": rid, "mission_id": m.mission_id, "at": iso(now),
                "why": f"the host recovered and the search for {function} ran: " + (
                    f"formed {formed.capability_id}" if formed is not None else "nothing qualified; asked anew"),
                "evidence": {"capability_id": getattr(formed, "capability_id", None)}}, key=[rid, "withdrawn"])
            self.book.rebuild()
            m = self.book.missions[m.mission_id]
        if formed is None:
            waiting = [c.capability_id for c in self.registry.by_function(function)
                       if self.registry.state[c.capability_id] == "VERIFIED"]
            self._escalate_capability(m, function, waiting[-1] if waiting else None, purpose, now,
                                      awaiting=bool(waiting))
            return {"state": "BLOCKED", "blocker": m.blocker}
        return {"state": "FORMED", "function": function, "capability": formed.capability_id}

    def _capability_request(self, m: MissionState, function: str, purpose: str, now: datetime,
                            *, scope: dict | None = None) -> str:
        return self._request(m, kind="CAPABILITY_ATTACH", scope_digest=sha256_json(scope or {"function": function}),
                             action_id=None, why=f"missing capability for {purpose}",
                             recommendation="attach a verified capability for this function, or revise the mission",
                             requested={"function": function,
                                        "spend": "none requested; any account, license or purchase is yours to make"},
                             now=now, resource=self._capability_ask(m, function, purpose))

    def _deficit_purpose(self, m: MissionState, function: str) -> str:
        opened = [e.payload for e in self.journal.replay("deficit.opened")
                  if e.payload["mission_id"] == m.mission_id and e.payload["function"] == function]
        return opened[-1]["purpose"] if opened else f"a capability for {function}"

    def _attach_candidates(self, m: MissionState, function: str) -> list[str]:
        """Withheld capabilities Genesis found for a cognition deficit (they carry other function names)."""
        return self.genesis.attach_candidates(m.mission_id, function) if self.genesis is not None else []

    def _closed(self, request_id: str) -> bool:
        return request_id in self.book.answers or request_id in self.book.withdrawn

    def _rejected_for(self, m: MissionState, function: str) -> dict[str, str]:
        """What the founder already answered for this mission's need, by candidate: every verified candidate named by
        an attach ask this mission waited on (its own, or a body-level one it shared) that the founder rejected,
        mapped to that ask. An answer decides exactly what its ask named, never more: none of these is asked about
        again for this need (section 60), and a candidate no answered ask named is still undecided."""
        waited = dict.fromkeys(e.payload["blocker"].get("request_id") for e in self.journal.replay("mission.blocked")
                               if e.payload["mission_id"] == m.mission_id
                               and e.payload["blocker"].get("type") == "capability"
                               and e.payload["blocker"].get("function") == function)
        return {cid: rid for rid in waited if (self.book.answers.get(rid) or {}).get("answer") == "reject"
                for cid in sorted(_named_verified(self.book.requests.get(rid) or {}))}

    def _undecided(self, m: MissionState, function: str) -> list[str]:
        """The candidates of this mission's need that no founder act has decided: still withheld (an attach resolves
        the need; a founder detach is a decision against that candidate) and named by no ask this mission waited on
        that the founder rejected. Only these are ever asked about again for this need."""
        rejected = self._rejected_for(m, function)
        return [c for c in self._attach_candidates(m, function) if c not in rejected]

    def _stands(self, ask: dict, undecided: list[str]) -> bool:
        """Whether a body-level attach ask still stands for a need whose undecided candidates are ``undecided``: it
        names one of them, and the founder can still answer it (open) or has said yes to it (approved; the signed
        attach then resolves every mission waiting on it, since approving only records the answer). A rejected or
        withdrawn ask does not stand, nor does an open or approved ask whose named candidates have all been decided
        since (a founder detach decides a candidate without any answer to the ask)."""
        rid = ask["request_id"]
        answer = (self.book.answers.get(rid) or {}).get("answer")       # None while the ask is open
        return rid not in self.book.withdrawn and answer in (None, "approve") \
            and bool(_named_verified(ask) & set(undecided))

    def _shared_ask_lapsed(self, m: MissionState) -> bool:
        """Whether a mission waiting on a shared body-level ask must be asked about the rest of its need: the ask no
        longer stands for it (``_stands``, the same rule that decides whether a mission arriving now would share it)
        and a candidate remains undecided. The founder's answer to a shared ask is this mission's answer for exactly
        what the ask named, as for its own ask; it decides nothing the ask did not name (the compiler's ask names its
        best fit alone, while the blocker keeps every candidate). So the mission waits while the ask is open or
        approved and names an undecided candidate. Once it does not (rejected, withdrawn unanswered, or every
        candidate it named decided, answered or not), the mission is asked once more, only about the undecided
        candidates. Being open is not standing: an open ask about a detached candidate is moot for this need."""
        b = m.blocker
        if b["type"] != "capability" or not b.get("shared_ask"):
            return False
        undecided = self._undecided(m, b["function"])
        return bool(undecided) and not self._stands(self.book.requests[b["request_id"]], undecided)

    def _shared_attach_ask(self, undecided: list[str]) -> str | None:
        """A body-level attach ask already recorded (the Competency Compiler records one per method, for its best
        fit) that stands for one of the undecided candidates (``_stands``). The mission waits on it, keeping every
        candidate in its blocker, instead of asking the founder about the same attach a second time. A rejected or
        withdrawn ask is never shared: this mission's need would then wait on a closed request that no open ask
        names, and a reject given before this mission existed did not answer its need. Once shared, the founder's
        answer to it is this mission's answer for what it named (``_shared_ask_lapsed``). Another mission's ask is
        never shared either, since that mission may withdraw it."""
        if not undecided:
            return None
        for event in self.journal.replay("decision.requested"):
            ask = event.payload
            if ask.get("kind") == "CAPABILITY_ATTACH" and ask.get("mission_id") is None \
                    and self._stands(ask, undecided):
                return ask["request_id"]
        return None

    def _escalate_capability(self, m: MissionState, function: str, capability_id, purpose: str, now: datetime,
                             *, awaiting: bool = False, keep=()):
        """Ask once about this need's undecided candidates. The blocker records every candidate the mission waited
        on (``keep``: those of a lapsed blocker, no longer offered); what resolves it is ``_blocker_resolved``.
        ``awaiting``: a named, newly formed capability waits for its attach; that is a new ask, not the old one."""
        candidates = self._attach_candidates(m, function)
        shared = self._shared_attach_ask(self._undecided(m, function))
        scope = {"function": function, **({"awaiting": capability_id} if awaiting else {})}
        rid = shared or self._capability_request(m, function, purpose, now, scope=scope)
        candidates = list(dict.fromkeys([*candidates, *keep]))
        self._block(m, {"type": "capability", "function": function, "capability_id": capability_id,
                        "request_id": rid, "why": f"no attached capability for {function}",
                        "reconsider": "a verified capability for this function is attached",
                        **({"attach_candidates": candidates} if candidates else {}),
                        **({"shared_ask": True} if shared else {})})
        return None

    def _escalate_human(self, m: MissionState, spec: dict, function: str, resource: str, purpose: str,
                        now: datetime):
        """Section 60, "I need a licensed professional for this decision": work only a person
        may do. GREG contacts, hires and pays no one; it asks once, with what the work is for,
        what each route costs and what it cannot know, then keeps observing the mission's own
        checks and closes the ask when the deliverable exists."""
        who = "a licensed professional" if resource == "professional" else "a person"
        watched = sorted(set(spec.get("advances", [])))
        checks = [{"check_id": c["check_id"], "description": c["description"],
                   "observed_by": c["sensor"].get("capability") or c["sensor"].get("function"),
                   "params": c["sensor"].get("params", {})} for c in m.spec["success_checks"] if c["check_id"] in watched]
        rid = self._request(
            m, kind="HUMAN_WORK", scope_digest=sha256_json({"function": function, "purpose": purpose}),
            action_id=spec.get("action_id"),
            why=f"{purpose} needs {function}, which only {who} may do; GREG will not substitute software for it",
            recommendation=(f"arrange {function} yourself or through {who} you choose, and put the deliverable where "
                            "the mission's check reads it; GREG closes this ask when it observes it"),
            requested={"function": function, "spend": "none requested; any engagement or payment is yours to make",
                       "contact": "none; GREG contacts no one"},
            now=now, resource={
                "resource": resource,
                "evidence": {"function": function, "required_by": purpose, "rationale": spec.get("rationale", ""),
                             "deliverable_observed_by": checks,
                             "not_attempted": "no software search, build or attachment: this function is reserved "
                                              "for a person (greg/asks.py HUMAN_WORK)"},
                "expected_effect": ("the mission's check observes the deliverable, the ask is withdrawn, and the "
                                    "mission continues without GREG acting for this step") if checks else
                                   "the mission continues once you revise how this step is observed",
                "uncertainty": ("how long the work takes, what it costs and whether its result is right are unknown "
                                "to GREG; no price was looked up and no one was contacted; GREG checks only that the "
                                "deliverable exists where the mission says, not its professional quality"),
                "options": [
                    {"option": f"do {function} yourself and place the deliverable", "cost": "your time",
                     "expected_effect": "observed at the next check; the ask is withdrawn and the mission continues"},
                    {"option": f"engage {who} you choose and place their deliverable",
                     "cost": "their fee, unknown to GREG; you contract and pay them directly",
                     "expected_effect": "observed at the next check; the ask is withdrawn and the mission continues"},
                    {"option": "revise the mission so this step is not needed", "cost": "none",
                     "expected_effect": "a new signed MISSION replaces this one; nothing runs for this step"},
                    self._abandon_option(m)]})
        self._block(m, {"type": "human_work", "request_id": rid, "function": function, "resource": resource,
                        "action_id": spec.get("action_id"),
                        "why": f"{function} is work only {who} may do",
                        **({"failing_checks": watched} if watched else {}),
                        "reconsider": "the deliverable is observed by the mission's own checks, or you revise or "
                                      "abandon the mission"})
        return None

    def _executed(self, m: MissionState) -> list[tuple[dict, str]]:
        """(latest DONE record, consequence class) of each executed strategy that is not read-only, in execution
        order. A capability this body no longer knows has an unknown class, never a presumed harmless one."""
        latest = {}
        for e in self.journal.replay("mission.action"):
            if e.payload.get("mission_id") == m.mission_id and e.payload.get("status") == "DONE":
                latest.pop(e.payload["action_id"], None)
                latest[e.payload["action_id"]] = e.payload
        classes = {a: getattr(self.registry.manifests.get(d.get("capability")), "consequence_class", "unknown")
                   for a, d in latest.items()}
        return [(d, classes[a]) for a, d in latest.items() if classes[a] != "read_only"]

    def _abandon_option(self, m: MissionState) -> dict:
        """Abandoning costs no money, but an executed effect does not end with the mission (Defect 7)."""
        executed = len(self._executed(m))
        if not executed:
            return {"option": "abandon", "cost": "none",
                    "expected_effect": "the mission ends; nothing further runs for it"}
        return {"option": "abandon",
                "cost": f"none in money; {executed} executed effect(s) do not end with the mission",
                "expected_effect": "the mission ends; each executed effect is compensated through the Gate where a "
                                   "compensating action was signed, otherwise put to you as a COMPENSATION decision "
                                   "(external effects) or recorded as an open compensation obligation (workspace "
                                   "writes)"}

    def _compensate(self, m: MissionState, now: datetime) -> dict:
        """An abandoned or superseded mission leaves no executed effect unaccounted for (Defect 7).

        Each executed, non-read-only strategy gets one compensation_required fact. A compensation signed with the
        strategy runs once, through this office and the Gate like any action, bound to the original receipt.
        With none signed, an external, financial, irreversible or unknown effect becomes one COMPENSATION
        decision and nothing runs; a workspace write stays recorded as an open obligation. Never blind-retried,
        never repeated after a restart (the fact keys and the Gate's retained receipt make it idempotent)."""
        mid = m.mission_id
        required = {e.payload["action_id"] for e in self.journal.replay("mission.compensation_required")
                    if e.payload["mission_id"] == mid}
        closed = {e.payload["action_id"] for e in self.journal.replay("mission.compensated")
                  if e.payload["mission_id"] == mid}
        strategies = {s["action_id"]: s for s in m.spec["strategies"]}
        rows, dispatched = [], False
        for action, klass in reversed(self._executed(m)):           # undo in reverse order of execution
            aid = action["action_id"]
            if aid in closed:
                continue
            decided = self._compensation_answer(m, action)
            if decided is not None and not decided.get("answer"):
                # The founder was asked about this effect and promised that nothing runs for it until the
                # answer: a capability re-attached meanwhile does not license the compensation.
                rows.append({"action_id": aid, "state": "AWAITING_FOUNDER", "request_id": decided["request_id"]})
                continue
            if decided is not None:            # the founder answered for this effect: that answer stands
                self.journal.record("mission.compensated", {
                    "mission_id": mid, "action_id": aid, "status": "FOUNDER_DECIDED", "receipt": None,
                    "answer": decided["answer"], "request_id": decided["request_id"],
                    "original_receipt": action.get("receipt"), "at": iso(now),
                    "reasons": [("founder: " + str(decided.get("reason") or ""))[:300]]}, key=[mid, aid, "compensated"])
                rows.append({"action_id": aid, "state": "FOUNDER_DECIDED"})
                continue
            declared = strategies.get(aid, {}).get("compensate")
            if aid not in required:
                reason = "compensation declared" if declared else "no compensation declared" + (
                    "" if klass == "internal_write" else "; founder decision required")
                self.journal.record("mission.compensation_required", {
                    "mission_id": mid, "action_id": aid, "capability": action.get("capability"),
                    "consequence_class": klass, "original_receipt": action.get("receipt"), "compensate": declared,
                    "lifecycle": m.status, "reason": reason, "at": iso(now)}, key=[mid, aid, "compensate"])
            if declared is None:
                if klass != "internal_write":
                    self._compensation_ask(m, action, klass, now)
                rows.append({"action_id": aid, "state": "COMPENSATION_REQUIRED"})
            elif dispatched or (self._stop_check is not None and self._stop_check()):
                # One dispatch per mission step, like any action, so a STOP that arrives during one
                # admits no further compensation in this tick; the rest run on later ticks.
                rows.append({"action_id": aid, "state": "NEXT_TICK"})
            else:
                state = self._run_compensation(m, action, klass, declared, now)
                dispatched = state not in ("WAITING", "DECLINED", "ESCALATED")
                rows.append({"action_id": aid, "state": state})
        return {"compensation": rows} if rows else {}

    def _compensation_answer(self, m: MissionState, action: dict) -> dict | None:
        """The COMPENSATION ask raised for this executed effect: with the founder's answer when there is one,
        else ``{"request_id": rid}`` (asked, not yet answered). None when the founder was never asked."""
        scope = sha256_json({"compensate": action["action_id"], "receipt": action.get("receipt")})
        for rid, request in self.book.requests.items():
            if request.get("mission_id") == m.mission_id and request.get("kind") == "COMPENSATION" \
                    and request.get("scope_digest") == scope and rid not in self.book.withdrawn:
                return {"request_id": rid, **self.book.answers.get(rid, {})}
        return None

    def _run_compensation(self, m: MissionState, action: dict, klass: str, declared: dict, now: datetime) -> str:
        mid, aid, original = m.mission_id, action["action_id"], action.get("receipt")
        manifest, adapter, missing = self._resolve(declared)
        if manifest is None:
            self._compensation_ask(m, action, klass, now, failure=[f"compensating capability {missing} is not usable"])
            return "ESCALATED"
        if manifest.capability_id in METERED_SPEND:      # signed before validate_mission refused it
            self._compensation_ask(m, action, klass, now, failure=[
                f"{manifest.capability_id} spends money by itself; GREG runs no unpaid compensation through it"])
            return "ESCALATED"
        params, target = declared.get("params", {}), declared["target"]
        scope = self.office.scope_digest(mission_id=mid, capability_id=manifest.capability_id, params=params,
                                         target=target, consequence_class=manifest.consequence_class, cost_usd=0.0)
        if any(r["kind"] == "APPROVAL" and r["scope_digest"] == scope for r in self.book.open_requests()):
            return "WAITING"                    # the founder decides this exact scope; no re-evaluation meanwhile
        record = {"mission_id": mid, "action_id": aid, "capability": manifest.capability_id, "target": target,
                  "original_receipt": original, "scope_digest": scope}
        if scope in m.rejected_scopes:
            self.journal.record("mission.compensated", {**record, "status": "DECLINED", "receipt": None, "at": iso(now),
                                                        "reasons": ["founder rejected this compensating action"]},
                                key=[mid, aid, "compensated"])
            return "DECLINED"
        if m.status == "SUPERSEDED" and scope not in m.approved_scopes:
            # A successor mission may rely on this effect: undoing it is the founder's call, for this exact scope.
            self._request(m, kind="APPROVAL", scope_digest=scope, action_id=aid,
                          why=f"compensation of {aid}: the mission was superseded, and its successor may rely on "
                              f"the effect this compensation would undo",
                          recommendation=f"approve the compensating action signed with {aid} "
                                         f"({manifest.capability_id} on {target}) only if the successor does not "
                                         "need the effect",
                          alternatives=["reject: the executed effect stands; nothing is run for it"],
                          requested={"capability": manifest.capability_id, "target": target,
                                     "consequence_class": manifest.consequence_class, "cost_usd": 0.0}, now=now,
                          evidence={"original_receipt": original, "lifecycle": m.status},
                          consequence="the executed effect stands; nothing is run for it")
            return "WAITING"
        outcome = self.office.act(
            mission_id=mid, cone=m.cone, command_digest=m.command_digest, manifest=manifest, adapter=adapter,
            ctx=self._context(m, manifest), params=params, target=target, cost_usd=0.0,
            expected_outcome=f"compensation of {aid}", evidence_refs=[original] if original else [],
            # Unpaid by construction (cost 0; self-spending capabilities refused), so an overrun of the cone
            # by earlier spend is no reason to refuse undoing an effect: the budget clause sees what it adds.
            attempt=f"compensate:{aid}:{original}", spent_usd=min(m.spent_usd, m.cone.budget_usd),
            approved_scopes=m.approved_scopes)
        if outcome.status in ("OUTSIDE_SCOPE", "NEEDS_DECISION"):
            self._request(m, kind="APPROVAL", scope_digest=outcome.scope_digest, action_id=aid,
                          why=f"compensation of {aid}: " + "; ".join(outcome.reasons)[:400],
                          recommendation=f"approve the compensating action signed with {aid} "
                                         f"({manifest.capability_id} on {target})",
                          alternatives=["reject: the executed effect stands; nothing is run for it"],
                          requested={"capability": manifest.capability_id, "target": target,
                                     "consequence_class": manifest.consequence_class, "cost_usd": 0.0}, now=now,
                          evidence={"original_receipt": original, "lifecycle": m.status},
                          consequence="the executed effect stands; nothing is run for it")
            return "WAITING"
        self.journal.record("mission.compensated", {**record, "status": outcome.status, "receipt": outcome.receipt_hash,
                                                    "reasons": [str(r)[:300] for r in outcome.reasons], "at": iso(now)},
                            key=[mid, aid, "compensated"])
        if outcome.status != "DONE":            # refused, unavailable or uncertain: never blind-retried
            self._compensation_ask(m, action, klass, now, failure=outcome.reasons)
        return outcome.status

    def _compensation_ask(self, m: MissionState, action: dict, klass: str, now: datetime, *, failure=None) -> str:
        """One founder decision for an executed effect GREG does not undo: none was signed, or the signed
        compensation did not complete. The answer is only recorded; nothing is executed for it."""
        aid, original = action["action_id"], action.get("receipt")
        strategy = next((s for s in m.spec["strategies"] if s["action_id"] == aid), {})
        evidence = {"original_receipt": original, "capability": action.get("capability"),
                    "target": strategy.get("target"), "consequence_class": klass, "lifecycle": m.status,
                    "executed_at": action.get("at"),
                    **({"compensation_failed": [str(r)[:300] for r in failure]} if failure else {})}
        return self._request(
            m, kind="COMPENSATION", scope_digest=sha256_json({"compensate": aid, "receipt": original}), action_id=aid,
            why=f"{aid} executed a {klass} effect through {action.get('capability')} before the mission ended "
                f"({m.status}); " + ("its signed compensation did not complete" if failure
                                     else "the mission signed no compensating action for it"),
            recommendation="inspect the retained receipt, then undo or accept the effect yourself",
            alternatives=["approve: record that you have handled this effect", "reject: record that the effect stands"],
            requested={"action_id": aid, "consequence_class": klass, "spend": "none",
                       "execution": "none: GREG runs no compensation that was not signed with the strategy"},
            now=now, evidence=evidence, consequence="the effect stays recorded as compensation required; nothing runs")

    def _capability_ask(self, m: MissionState, function: str, purpose: str) -> dict:
        """Section 60 for a missing capability: what was searched, what each route costs."""
        opened = [e.payload for e in self.journal.replay("deficit.opened")
                  if e.payload["mission_id"] == m.mission_id and e.payload["function"] == function]
        deficit_id = opened[-1]["deficit_id"] if opened else None
        routes = [{"route": e.payload["route"], "result": e.payload["result"]}
                  for e in self.journal.replay("genesis.route") if deficit_id and e.payload["deficit_id"] == deficit_id]
        rejected = self._rejected_for(m, function)     # already answered for this need: listed, never offered again
        listed = [c for c in self.registry.by_function(function) if c.capability_id not in rejected]
        listed += [self.registry.manifests[cid] for cid in self._attach_candidates(m, function)
                   if cid in self.registry.manifests and cid not in rejected
                   and all(c.capability_id != cid for c in listed)]
        evidence = {"function": function, "required_by": purpose, "deficit_id": deficit_id,
                    "searched": routes or [{"route": "genesis", "result": "not available on this body"
                                            if self.genesis is None else "no route recorded"}],
                    "registered": [{"capability_id": c.capability_id, "state": self.registry.state[c.capability_id],
                                    **({"mechanism": _mechanism_summary(c.provenance)}
                                       if c.provider.startswith("installed:python:") else {})}
                                   for c in listed],
                    **({"already_answered": [{"capability_id": cid, "request_id": rid, "answer": "reject"}
                                             for cid, rid in rejected.items()]} if rejected else {})}
        engine = self.genesis.construction_engine(function) if self.genesis is not None else None
        if engine:   # a constructible function first needs its engine; both are attachable from this ask
            evidence["registered"] += [{"capability_id": c.capability_id, "state": self.registry.state[c.capability_id],
                                        "role": f"engine ({engine}) {function} is constructed over"}
                                       for c in self.registry.by_function(engine) if c.capability_id not in rejected]
        return {"resource": "capability", "evidence": evidence,
                "expected_effect": f"the blocked step ({purpose}) proceeds once a verified capability for "
                                   f"{function} is attached",
                "uncertainty": "whether a service, tool or build passes the frozen verification is unknown until "
                               "it is tried; no provider price was looked up",
                "options": [
                    {"option": "provide an API key/connector for a service that performs this function (held by "
                               "the secret broker, never written to the ledger)",
                     "cost": "the provider's price, if any; the credential is exposed to that provider",
                     "expected_effect": "a capability using it can be verified and attached; the mission resumes"},
                    {"option": "install software that performs this function; genesis verifies it before attaching",
                     "cost": "your installation time; the software's license",
                     "expected_effect": "attached only if it passes the frozen verification; the mission resumes"},
                    {"option": "add a capability contract (examples and held-out cases) so a bounded adapter can be "
                               "built and verified",
                     "cost": "none in money; model time if you selected a model route",
                     "expected_effect": "a built capability attaches only after it passes the held-out cases"},
                    {"option": "revise the strategy", "cost": "none",
                     "expected_effect": "the mission continues on strategies that do not need this function"},
                    self._abandon_option(m)]}

    def _access_ask(self, m: MissionState, aid: str, manifest, gap: dict, now: datetime) -> str | None:
        """Section 60, "I need access to this account to answer reliably": the action worked,
        but a service refused reads a credential would allow. Informational, never a blocker;
        one ask per credential per mission. Asking grants nothing: only Alfonso stores a
        credential, on the body, with `greg secret set`."""
        handle = gap.get("credential")
        if handle not in manifest.credentials:
            return None                     # a capability may only ask for a handle it declares
        refused = gap["evidence"].get("refused", {})
        return self._request(
            m, kind="ACCOUNT_ACCESS", scope_digest=sha256_json({"credential": handle}), action_id=aid,
            why=f"{gap['service']} refused {len(refused) or 'some'} read(s) this mission needed; "
                "the result was delivered with those gaps listed",
            recommendation=f"if you want complete answers, create a read-only token for these repositories and "
                           f"store it on this body with: greg secret set {handle}",
            requested={"credential": f"{handle}: read-only; held by the secret broker on this body, never in the "
                                     "ledger, revocable by you at any time",
                       "spend": "none requested"},
            now=now,
            resource={"resource": "account_access", "evidence": gap["evidence"],
                      "expected_effect": "later runs read what was refused, so the gaps listed in the result close",
                      "uncertainty": "GitHub does not say which refusals were rate limits and which were missing "
                                     "access; some may clear on their own, and a token only helps for repositories "
                                     "it is granted",
                      "options": [
                          {"option": f"store a read-only token with: greg secret set {handle}",
                           "cost": "none in money; the token can read what you grant it until you revoke it",
                           "expected_effect": "authenticated reads; the refused repositories are read on the next run"},
                          {"option": "narrow the mission to fewer repositories", "cost": "none",
                           "expected_effect": "fewer calls; the remaining repositories are more likely to be read"},
                          {"option": "do nothing: keep results with their gaps listed", "cost": "none",
                           "expected_effect": "results stay partial; every gap stays visible in each result"}]})

    def _cognition_ask(self, m: MissionState, aid: str, receipt: dict, now: datetime) -> str | None:
        """Goal gravity for the Mind: a persistent goal pulls the intelligence it needs. A cognition
        receipt that abstained because the eligible families are built but not attached becomes one
        ask naming them with their native-benchmark admission (greg/cognition/genome_library.py).
        A family REJECTED or SUPERSEDED on its own geometry is listed, never recommended. Informational,
        never a blocker; asking grants nothing: only Alfonso attaches, with ``greg attach``."""
        from greg.cognition.genome_library import inventory
        waiting = sorted({r["method"] for r in receipt.get("alternative_methods_considered") or []
                          if not r.get("eligible") and str(r.get("reason", "")).startswith("state ")})
        if not waiting:
            return None
        library = {e.genome_id: e for e in inventory()}
        families = [{"capability": cid, "admission": library[cid].admission if cid in library else "NOT_INVENTORIED",
                     "layer": library[cid].layer if cid in library else None,
                     "detail": library[cid].detail[:200] if cid in library else "",
                     "evidence_refs": list(library[cid].evidence_refs) if cid in library else []} for cid in waiting]
        # never recommend a composition stage on its own: the compiler rejects it as a standalone decision, so
        # the hook's admissible set follows the compiler's rule (review of #179, M2)
        order = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY", "EXPERIMENTAL", "NOT_INVENTORIED")
        admissible = sorted((f for f in families if f["admission"] in order), key=lambda f: order.index(f["admission"]))
        best = admissible[0] if admissible else None
        return self._request(
            m, kind="CAPABILITY_ATTACH", scope_digest=sha256_json({"cognition": waiting}), action_id=aid,
            why=f"{aid} needed {receipt.get('epistemic_class')} cognition; the eligible families are built and "
                "verified but not attached, so the receipt abstained",
            recommendation=(f"attach {best['capability']} (native-benchmark admission: {best['admission']}) with: "
                            f"greg attach {best['capability']}") if best else
                           "do not attach: every eligible family lost to a simpler method on its own benchmark; "
                           "revise the mission's operation",
            requested={"capabilities": waiting, "spend": "none requested"}, now=now,
            resource={"resource": "capability",
                      "evidence": {"families": families, "receipt": receipt.get("missing_information", [])[:3]},
                      "expected_effect": "the next attempt is answered by the attached family and re-verified by the "
                                         "independent checker; the mission's own success checks still decide",
                      "uncertainty": "admission was measured on synthetic native benchmarks, not on this mission's data",
                      "options": [{"option": f"greg attach {f['capability']}", "cost": "none in money",
                                   "expected_effect": f"{f['capability']} becomes routable ({f['admission']})"}
                                  for f in admissible[:3]] +
                                 [{"option": "do nothing: the mission tries its other strategies", "cost": "none",
                                   "expected_effect": "this step keeps abstaining"}]})

    def _spend_ask(self, m: MissionState, s: dict, outcome, routing_decision: dict) -> dict:
        """Section 60 for money: an approval that spends is a resource ask with its own evidence."""
        cost = float(s["cost_usd"])
        others = [x["action_id"] for x in m.spec["strategies"] if x["action_id"] != s["action_id"]][:5]
        return {"resource": "spend",
                "evidence": {"policy": [str(r)[:300] for r in outcome.reasons], "routing": routing_decision,
                             "budget": {"spent_usd": m.spent_usd, "budget_usd": m.cone.budget_usd,
                                        **({"reserved_usd": m.reserved_usd} if m.reserved else {})}},
                "expected_effect": f"advances {sorted(s['advances'])} if the action succeeds",
                "uncertainty": f"estimated reliability {routing_decision['reliability']:.2f} from this body's "
                               "record of the capability; the outcome is re-observed, never assumed",
                "options": [
                    {"option": f"approve {s['action_id']}", "cost": f"${cost:.2f} from this mission's budget",
                     "expected_effect": f"runs once; advances {sorted(s['advances'])} if it succeeds"},
                    {"option": "reject: the mission will try alternatives or ask again", "cost": "none",
                     "expected_effect": "no money is spent; the mission tries " + (", ".join(others) or
                                                                                 "no other strategy") + " or asks again"}]}

    def _pursue(self, m: MissionState, now: datetime, failing: set, evidence: list, *,
                prepare_for: str | None = None) -> dict:
        """Choose and run the highest-leverage strategy for the failing checks.

        ``prepare_for`` (the strategy whose APPROVAL the founder has not answered yet) restricts the turn
        to static strategies whose exact scope lies inside the cone: nothing is asked, nothing blocks,
        and the awaited strategy itself never runs here."""
        from greg.pipeline import resolve, BindingError
        if self._unsettled(m) is not None:     # never dispatch past an unsettled interruption, whatever the path
            resumed = self._resume_unsettled(m, now, displace=True)
            return resumed if resumed is not None else {"state": "BLOCKED", "blocker": m.blocker}
        candidates = []
        records = routing.track_record(self.journal)
        value = float(m.spec.get("value_per_check_usd", 1.0))
        held = {}                            # strategies waiting on a precondition observation says fails
        bound = {}                           # action_id -> (params, binding provenance, source receipts)
        inline = {}                          # action_id -> (params, provenance) of inline $from_action inputs
        for index, s in enumerate(m.spec["strategies"]):
            gain = len(set(s["advances"]) & failing)
            if not gain or s["action_id"] in m.failed or s["action_id"] in m.excluded:
                continue
            if prepare_for is not None and (s["action_id"] == prepare_for or not self._inside_cone(m, s, now)):
                continue
            if set(s.get("requires", [])) & failing:
                held[s["action_id"]] = sorted(set(s["requires"]) & failing)
                continue
            try:      # inputs that cannot resolve (or be consumed) yet hold the strategy: an alternative runs,
                bound[s["action_id"]], inline_out = self._inputs(m, s)   # or the founder is asked
            except (Unbound, BindingError) as why:
                held[s["action_id"]] = [f"input: {why}"]
                continue
            if inline_out is not None:
                inline[s["action_id"]] = inline_out
            manifest = self._manifest_for(s)
            neg_expected, route, _, estimate = rank_key(
                s, index, failing, manifest, records.get(manifest.capability_id) if manifest else None, value)
            candidates.append((neg_expected, route, index, s, estimate))
        if not candidates and prepare_for is not None:
            return {"state": "NOTHING_TO_PREPARE"}
        if not candidates:
            key = sha256_json({"failing": sorted(failing), "failed": sorted(m.failed), "excluded": sorted(m.excluded)})
            split = {c: v for c, v in sorted(getattr(self, "disagreements", {}).items()) if c in failing}
            declined = sorted(a for a, r in m.excluded.items() if r.startswith("declined by the person"))
            why = ((f"the person declined {', '.join(declined)}; that refusal stands, and GREG asks nothing more of "
                    "them") if declined else
                   ("the remaining strategies wait on checks that observation says fail: "
                    + ", ".join(sorted({c for cs in held.values() for c in cs})))
                   if held else "every strategy for the failing checks is exhausted, refused or excluded")
            if split:
                why = (f"qualified intelligences disagree on {', '.join(split)}; GREG keeps every view and does not "
                       f"vote, so it cannot close on either; " + why)
            tradeoffs = {a: r for a, r in sorted(m.failed.items()) if r.startswith("regressed ")}
            routes = [s["action_id"] for s in m.spec["strategies"] if set(s["advances"]) & failing]
            blamed = "; ".join(f"{a} {r.split(',')[0]}" for a, r in tradeoffs.items())
            if tradeoffs and not split and routes and all(a in tradeoffs for a in routes):
                why = ("every remaining route improves one check only by breaking another that already passed ("
                       + blamed + "); GREG will not trade one for the other on its own")
            elif tradeoffs and not split:
                why += "; routes that broke a check which already passed are not repeated (" + blamed + ")"
            rid = self._request(m, kind="NO_STRATEGY", scope_digest=key, action_id=None, why=why,
                                recommendation=("review both views and decide, or add an independent verifier that "
                                                "can settle the question" if split else
                                                "decide which check matters more, or add a strategy that satisfies "
                                                "both" if tradeoffs and routes and all(a in tradeoffs for a in routes) else
                                                "ask someone else in a new signed mission, do the work yourself, "
                                                "or abandon" if declined else
                                                "add or revise strategies, widen scope, or abandon the mission"),
                                alternatives=["sign a new mission naming someone else",
                                              "do the work yourself and place the deliverable where the check reads it",
                                              "abandon the mission"] if declined else
                                ["add or revise strategies for the failing checks", "widen the scope",
                                 "abandon the mission"],
                                requested={"failing_checks": sorted(failing)}, now=now,
                                evidence={"failing_checks": sorted(failing), "failed": dict(sorted(m.failed.items())),
                                          "excluded": dict(sorted(m.excluded.items())),
                                          **({"held_by_precondition": held} if held else {}),
                                          **({"tradeoffs": tradeoffs} if tradeoffs else {}),
                                          **({"disagreement": split} if split else {})})
            if m.actions_done and not held and not split:
                # Every admissible strategy ran and these signed checks still fail: a failure closure. The
                # separate process appraises it as it does an achievement, so settlement hears failures too.
                # Not while qualified intelligences disagree on a failing check: GREG does not vote, so it closes
                # on neither view, as a success or as a failure.
                # A closure is identified by the actions it closes over: after the founder answers the ask with
                # nothing new run, the mission re-closes over the same actions, which is the closure already
                # recorded and appraised, not a second one (and not the same identity with a later time).
                closure = [m.mission_id, "unmet", m.actions_done]
                if self.journal.retained("mission.unmet", closure) is None:
                    self.journal.record("mission.unmet", {
                        "mission_id": m.mission_id, "failing_checks": sorted(failing),
                        # the receipts of the observations it closes over, bound by the appraiser as for an
                        # achievement (#173's closure-bound evidence)
                        "evidence": [m.observations[c]["receipt"] for c in sorted(failing)
                                     if (m.observations.get(c) or {}).get("receipt")],
                        "actions_done": m.actions_done,
                        "closure_rule": "every admissible strategy ran; these signed checks re-observed failing",
                        "at": iso(now)}, key=closure)
            self._block(m, {"type": "decision", "request_id": rid, "why": "no admissible strategy",
                            "failing_checks": sorted(failing), "reconsider": "founder revises mission"})
            return {"state": "BLOCKED", "blocker": m.blocker}
        candidates.sort(key=lambda c: c[:3])
        s = candidates[0][3]
        routing_decision = {"chosen": s["action_id"], "expected_value": round(-candidates[0][0], 4),
                            "reliability": round(candidates[0][4], 4),
                            "alternatives": [{"action_id": c[3]["action_id"], "expected_value": round(-c[0], 4),
                                              "reliability": round(c[4], 4)} for c in candidates[1:6]]}
        manifest, adapter, _ = self._resolve(s)
        if manifest is None and prepare_for is not None:
            return {"state": "NOTHING_TO_PREPARE"}
        if manifest is None:
            if self._deficit(m, s, now, purpose=f"strategy {s['action_id']}") is None:
                return {"state": "BLOCKED", "blocker": m.blocker}
            # Forming it may have spent (a build is booked on this cone): the act is admitted on what is left.
            self.book.rebuild()
            m = self.book.missions[m.mission_id]
            manifest, adapter, _ = self._resolve(s)
            if manifest is None:
                return {"state": "BLOCKED", "blocker": m.blocker}
        aid = s["action_id"]
        attempt = m.attempts.get(aid, 0)
        params, bindings, sources = bound.get(aid, (s.get("params", {}), [], []))
        # Two typed-handoff syntaxes, one resolver order: signed ``bind`` edges (above) first, then
        # inline ``$from_action`` references (#156/#159 pipeline). Both read only retained Gate
        # receipts of this mission; neither can touch capability, target, cost or scope.
        try:
            bound_params, input_bindings = inline[aid] if aid in inline and not bindings else \
                resolve(params, self.journal, m.mission_id)
        except BindingError as exc:          # held during selection; reaching here is a recorded refusal
            self.journal.record("mission.action", {
                "mission_id": m.mission_id, "action_id": aid, "attempt": attempt, "status": "REFUSED",
                "reasons": ["pipeline input unavailable: " + str(exc)[:280]], "receipt": None,
                "cost_usd": 0.0, "at": iso(now)},       # no capability: its input failed, not the capability
                key=[m.mission_id, aid, attempt, "input"])
            return {"state": "REPLANNING", "action": aid, "why": "pipeline input unavailable"}
        # A worker's own provider budget never exceeds the cost Alfonso signed for the strategy: whatever the
        # params say, the dispatch carries at most the signed ceiling, so no spend can escape the budget.
        budget_capped = None
        requested = bound_params.get("max_budget_usd") if isinstance(bound_params, dict) else None
        if isinstance(requested, (int, float)) and not isinstance(requested, bool) \
                and requested > float(s.get("cost_usd", 0.0)) + 1e-9:
            budget_capped = {"signed_cost_usd": float(s.get("cost_usd", 0.0)), "requested_usd": float(requested)}
            bound_params = {**bound_params, "max_budget_usd": float(s.get("cost_usd", 0.0))}
        # Write-ahead: the exact proposal is on the ledger before the Gate is asked, so a body that dies inside
        # the dispatch finds it again on restart and settles it from the Gate's own record (_recover_dispatch).
        # The exact scope the Gate derives below, paid budget state included (#157), so the intent names its proposal.
        scope = AuthorityOffice.scope_digest(mission_id=m.mission_id, capability_id=manifest.capability_id,
                                             params=bound_params, target=s["target"],
                                             consequence_class=manifest.consequence_class,
                                             cost_usd=float(s.get("cost_usd", 0.0)), spent_usd=m.committed_usd,
                                             budget_usd=m.cone.budget_usd)
        budget_state = {"spent_usd": m.committed_usd, "budget_usd": m.cone.budget_usd}
        self.journal.record("mission.dispatching", {
            "mission_id": m.mission_id, "action_id": aid, "attempt": attempt, "capability": manifest.capability_id,
            "scope_digest": scope, "proposal_id": AuthorityOffice.proposal_id(scope, attempt),
            **({"budget_state": budget_state} if float(s.get("cost_usd", 0.0)) > 0 else {})},
            key=[m.mission_id, aid, attempt, scope])
        # A founder-signed SOP pre-approval covers exactly this step's final scope: the one dispatched,
        # after any budget cap, so a pre-approval never covers a scope it did not name.
        signed = frozenset({scope}) if pre_approved(m.spec, s, manifest) else frozenset()
        outcome = self.office.act(
            mission_id=m.mission_id, cone=m.cone, command_digest=m.command_digest, manifest=manifest,
            adapter=adapter, ctx=self._context(m, manifest), params=bound_params, target=s["target"],
            cost_usd=float(s.get("cost_usd", 0.0)), expected_outcome=s.get("expected_outcome", "strategy executed"),
            evidence_refs=evidence + [r for r in sources if r not in evidence], attempt=attempt,
            spent_usd=m.committed_usd, approved_scopes=m.approved_scopes,
            evidence_confidence=float(s.get("evidence_confidence", 1.0)), signed_scopes=signed)
        if (manifest.capability_id == "worker.commission" and outcome.status == "DONE"
                and isinstance(outcome.output, dict) and outcome.output.get("status") == "UNCERTAIN"):
            # Extracted from #157: the Gate completed collection, but the cancellable worker stopped after
            # possible partial effects and spend. Keep its receipt and route it through the same
            # no-blind-retry reconciliation as any uncertain act, with the signed cap reserved.
            outcome.status = "UNCERTAIN"
            outcome.reasons = ["worker execution interrupted; partial outcome and spend require reconciliation"]
        return self._record_outcome(m, s, manifest, outcome, attempt=attempt, routing_decision=routing_decision,
                                    input_bindings=input_bindings, bindings=bindings, budget_capped=budget_capped,
                                    prepare_for=prepare_for, now=now, params=bound_params, budget_state=budget_state)

    def _recover_dispatch(self, m: MissionState, now: datetime) -> dict | None:
        """Settle a dispatch this body began but never recorded, before anything else is decided.

        A body killed inside ``office.act`` leaves its write-ahead intent (mission.dispatching) and possibly the
        Gate's dispatch claim, but no mission.action: the world may already show the effect, and observing first
        would close the mission over an unrecorded, unreconciled dispatch. The Gate's own record decides: a
        receipt is reused (DONE, its spend booked), a claim without a receipt is UNCERTAIN (its cap reserved,
        one reconciliation of exactly that dispatch, never a blind retry), and no claim means nothing happened.
        A free read_only claim without a receipt is left to observation: it cannot have changed the world or the
        budget, so recovering it first would only turn an answerable mission into a needless reconciliation."""
        recorded = {(e.payload["action_id"], e.payload["attempt"]) for e in self.journal.replay("mission.action")
                    if e.payload.get("mission_id") == m.mission_id}
        for intent in [e.payload for e in self.journal.replay("mission.dispatching")
                       if e.payload.get("mission_id") == m.mission_id]:
            if (intent["action_id"], intent["attempt"]) in recorded:
                continue
            claim, receipt = self.office.prior(intent["proposal_id"])
            s = next((x for x in m.spec["strategies"] if x["action_id"] == intent["action_id"]), None)
            manifest = self.registry.manifests.get(intent["capability"])
            if claim is None and receipt is None or s is None or manifest is None:
                continue                     # the Gate never dispatched it: nothing happened, nothing to settle
            if receipt is None and manifest.consequence_class == "read_only" and float(s.get("cost_usd", 0.0)) <= 0:
                # A free read-only dispatch cannot have changed the world or the budget: its unknown outcome gives
                # observation nothing to close over, so observation decides first, as it did before this recovery.
                continue
            base = dict(proposal_id=intent["proposal_id"], scope_digest=intent["scope_digest"])
            if receipt is not None:
                result = receipt.payload.get("result") or {}
                outcome = ActionOutcome(
                    "DONE" if result.get("result_class") == "positive" else "REFUSED",
                    ["retained receipt of a dispatch the body did not record before it stopped"]
                    if result.get("result_class") == "positive" else [result.get("observed_outcome", "failed")],
                    output=result.get("output"), receipt_hash=receipt.hash, grant_id=receipt.payload.get("grant_id"),
                    cost_usd=float(s.get("cost_usd", 0.0)), **base)
            else:
                outcome = ActionOutcome("UNCERTAIN", ["dispatch claimed without receipt; the body stopped inside "
                                                      "it, so its outcome is unknown"],
                                        grant_id=claim.payload.get("grant_id"), **base)
            return {**self._record_outcome(m, s, manifest, outcome, attempt=intent["attempt"],
                                           routing_decision={"chosen": s["action_id"], "recovered": True},
                                           input_bindings=[], bindings=[], budget_capped=None, prepare_for=None,
                                           now=now, budget_state=intent.get("budget_state")),
                    "recovered": intent["proposal_id"]}
        return None

    def _record_outcome(self, m: MissionState, s: dict, manifest, outcome, *, attempt, routing_decision: dict,
                        input_bindings: list, bindings: list, budget_capped, prepare_for, now: datetime,
                        params: dict | None = None, budget_state: dict | None = None) -> dict:
        """Record one Gate outcome of strategy ``s`` and decide what the mission does next. ``params``: the bound
        params the Gate was asked with (a recovered dispatch's outcome never needs them: it is never a decision)."""
        aid = s["action_id"]
        bound_params = s.get("params", {}) if params is None else params
        record = {"mission_id": m.mission_id, "action_id": aid, "attempt": attempt, "status": outcome.status,
                  "reasons": [str(r)[:300] for r in outcome.reasons], "receipt": outcome.receipt_hash,
                  "capability": manifest.capability_id, "route": manifest.route,
                  "cost_usd": outcome.cost_usd if outcome.status == "DONE" else 0.0,
                  "scope_digest": outcome.scope_digest, "routing": routing_decision, "at": iso(now),
                  "input_bindings": input_bindings}
        if float(s.get("cost_usd", 0.0)) > 0:
            # The paid budget state the Gate bound into this scope (#157), so a separate appraiser re-derives it.
            record["budget_state"] = budget_state or {"spent_usd": m.committed_usd, "budget_usd": m.cone.budget_usd}
        if outcome.status == "DONE" and float(s.get("cost_usd", 0.0)) > 0:
            record.update(metered_spend(manifest.capability_id, outcome.output, outcome.cost_usd))
        if outcome.status == "UNCERTAIN":
            # Completion unknown: nothing is booked as spent, and the dispatch's worst case (its signed cap) is
            # reserved against the budget until a reconciliation settles this one dispatch.
            record.update(reserved_usd=float(s.get("cost_usd", 0.0)), proposal_id=outcome.proposal_id,
                          grant_id=outcome.grant_id,
                          spend_basis="reserved: completion unknown; the signed cap counts against the budget "
                                      "until this dispatch is reconciled")
            if manifest.retry_safe:
                streak = m.uncertain_streak.get(aid, 0) + 1
                record["retry"] = {"consecutive_unknown": streak, "limit": RETRY_LIMIT,
                                   "retry_in_seconds": retry_delay(streak) if streak < RETRY_LIMIT else None}
        if bindings:
            record["bindings"] = bindings
        if budget_capped:
            record["budget_capped"] = budget_capped
        if outcome.status in ("OUTSIDE_SCOPE", "NEEDS_DECISION") and prepare_for is not None:
            return {"state": "NOTHING_TO_PREPARE"}    # preparation never asks; nothing was dispatched
        if outcome.status in ("OUTSIDE_SCOPE", "NEEDS_DECISION") and manifest.capability_id == "mcp.act":
            from greg.mcp_tools import reach_problem
            problem = reach_problem(bound_params)
            if problem is not None:          # refused before anyone is asked: the signed scope cannot run as written
                record["status"] = "REFUSED"
                record["reasons"].append(f"the signed mcp.act scope cannot run: {problem}")
                self.journal.record("mission.action", record, key=[m.mission_id, aid, attempt, "malformed"])
                return {"state": "REPLANNING", "action": aid}
        if outcome.status in ("OUTSIDE_SCOPE", "NEEDS_DECISION"):
            if outcome.scope_digest in m.rejected_scopes:
                record["status"] = "REFUSED"
                record["reasons"].append("founder already rejected this exact scope")
                self.journal.record("mission.action", record, key=[m.mission_id, aid, attempt, "rejected"])
                return {"state": "REPLANNING", "action": aid}
            move = self.office.scope_digest(mission_id=m.mission_id, capability_id=manifest.capability_id,
                                            params=bound_params, target=s["target"],
                                            consequence_class=manifest.consequence_class,
                                            cost_usd=float(s.get("cost_usd", 0.0)))
            rid = self._request(m, kind="APPROVAL", scope_digest=outcome.scope_digest, move_digest=move,
                                action_id=aid, why="; ".join(outcome.reasons)[:400],
                                recommendation=f"approve {aid} ({manifest.capability_id} on {s['target']}) "
                                               f"at ${s.get('cost_usd', 0.0)}: {s.get('rationale', '')}"[:400],
                                alternatives=[x["action_id"] for x in m.spec["strategies"] if x["action_id"] != aid][:5]
                                + ["reject: the mission will try alternatives or ask again"],
                                requested={"capability": manifest.capability_id, "target": s["target"],
                                           "consequence_class": manifest.consequence_class,
                                           "cost_usd": s.get("cost_usd", 0.0),
                                           # what the bound scope (the one the digest covers) lets it touch
                                           **exact_reach(manifest.capability_id, bound_params),
                                           **({"spend": f"${float(s['cost_usd']):.2f} for this one action"}
                                              if float(s.get("cost_usd", 0.0)) > 0 else {})},
                                now=now, resource=self._spend_ask(m, s, outcome, routing_decision)
                                if float(s.get("cost_usd", 0.0)) > 0 else None)
            self._block(m, {"type": "decision", "request_id": rid, "action_id": aid, "why": record["reasons"][:3],
                            "reconsider": "founder approves or rejects this exact scope"})
            return {"state": "WAITING", "blocker": m.blocker}
        self.journal.record("mission.action", record, key=[m.mission_id, aid, attempt])
        if outcome.status == "UNCERTAIN":
            if manifest.retry_safe:
                streak = m.uncertain_streak.get(aid, 0) + 1          # this record is the latest of the streak
                if streak >= RETRY_LIMIT:
                    return {"state": "REPLANNING", "action": aid, "status": outcome.status,
                            "why": f"completion unknown on {streak} consecutive dispatches; retry limit reached"}
                delay = retry_delay(streak)
                if delay:
                    self._schedule(m, now, delay)
                return {"state": "RETRYING", "action": aid, "why": "read-only idempotent capability",
                        "attempt": attempt, "retry_in_seconds": delay}
            return self._settle_uncertain(m, s, manifest, record, now)
        if outcome.status == "DONE" and isinstance(outcome.output, dict) and outcome.output.get("access_gap"):
            self._access_ask(m, aid, manifest, outcome.output["access_gap"], now)
        # A plain cognition receipt that abstained because built families are unattached (PR #155 lineage):
        # one informational attach ask. Compiler deficits naming a missing function go to Genesis below.
        if outcome.status == "DONE" and isinstance(outcome.output, dict) \
                and outcome.output.get("abstention_state") == "CAPABILITY_DEFICIT":
            self._cognition_ask(m, aid, outcome.output, now)
        deficit = outcome.output.get("capability_deficit") if outcome.status == "DONE" and \
            isinstance(outcome.output, dict) and outcome.output.get("state") == "CAPABILITY_DEFICIT" else None
        if isinstance(deficit, dict) and deficit.get("function"):
            # Directive 2026-10-07 section 24: no current intelligence fits the residual geometry, so the one
            # Capability Genesis loop searches for it under this mission's authority, else asks the founder once.
            # The deficit is the missing function, not the (attached) solver that reported it: only a capability
            # attached for that function or one of the candidates Genesis named for it clears the blocker.
            cognition = {**deficit, "acquisition_candidates": outcome.output.get("acquisition_candidates") or []}
            if self._deficit(m, {"function": deficit["function"]}, now, cognition=cognition,
                             purpose=f"cognition for {deficit.get('purpose', 'a cognitive request')}"[:200]) is None:
                return {"state": "BLOCKED", "blocker": m.blocker}
        # DONE: re-observe next tick to verify the effect in the world; REFUSED/
        # UNAVAILABLE: the failure is retained and an alternative is tried next.
        return {"state": "ACTED" if outcome.status == "DONE" else "REPLANNING", "action": aid,
                "status": outcome.status}
