"""Bounded Foundry computation through the existing GREG AuthorityOffice.

This adapter is not a registry, scheduler, policy service or learning plane.
It exposes an explicit read-only subset of PR #132's mechanisms. Source
operations that execute code, create grants, install/attach capabilities, edit
protected policy or open another store are deliberately absent. Persistence
uses existing fs.write/artifact.store and the canonical Gate receipt path.
"""
from __future__ import annotations

import hashlib
import json
import math

from greg.capabilities import CapabilityError, InvocationContext, MAX_READ_BYTES

MAX_INPUT_BYTES = 65536
MAX_COLLECTION = 512
MAX_INPUT_NODES = 4096
MAX_COMPUTE_OPERATIONS = 50000

# Implementation dispatch metadata only: the native CapabilityRegistry owns
# qualification, lifecycle and availability; AuthorityOffice owns invocation.
READ_ONLY_OPS = {
    1: frozenset({"compile"}),
    2: frozenset({"run", "check"}),
    6: frozenset({"root", "verify_member"}),
    11: frozenset({"run", "differential"}),
    17: frozenset({"search", "precedents"}),
    18: frozenset({"why", "impact", "shared"}),
    19: frozenset({"next_best_test", "next_depth"}),
    20: frozenset({"compare"}),
    22: frozenset({"tribunal"}),
    40: frozenset({"best_report", "procure"}),
    41: frozenset({"score"}),
    43: frozenset({"check", "check_approval_boundary"}),
    44: frozenset({"correlate", "metrics", "why_changed", "otel"}),
}

ARGUMENT_FIELDS = {
    (1, "compile"): ({"source"}, {"filename"}),
    (2, "run"): ({"language", "source", "inputs"}, set()),
    (2, "check"): ({"language", "source"}, set()),
    (6, "root"): ({"records"}, set()),
    (6, "verify_member"): ({"records", "member", "trusted_root"}, set()),
    (11, "run"): ({"language", "source", "inputs"}, set()),
    (11, "differential"): ({"language", "source"}, {"cases", "seed"}),
    (17, "search"): ({"cases", "query"}, {"context", "limit"}),
    (17, "precedents"): ({"cases", "query"}, {"context"}),
    (18, "why"): ({"node"}, {"graph", "mission_id"}),
    (18, "impact"): ({"node"}, {"graph", "mission_id"}),
    (18, "shared"): ({"kind"}, {"graph", "mission_id"}),
    (19, "next_best_test"): ({"hypotheses", "tests"}, set()),
    (19, "next_depth"): ({"current", "transitions"}, set()),
    (20, "compare"): ({"script", "honours_idempotency", "key", "amount"}, {"attempts"}),
    (22, "tribunal"): ({"strategies"}, {"runs", "seed"}),
    (40, "best_report"): ({"belief"}, set()),
    (40, "procure"): ({"bids"}, set()),
    (41, "score"): ({"records", "now"}, {"half_life_days"}),
    (43, "check"): ({"model"}, {"max_states"}),
    (43, "check_approval_boundary"): (set(), {"max_states"}),
    (44, "correlate"): (set(), {"mission_id"}),
    (44, "metrics"): (set(), {"mission_id", "start", "end"}),
    (44, "why_changed"): ({"metric", "split"}, {"mission_id", "start", "end"}),
    (44, "otel"): (set(), {"mission_id"}),
}


def operation_class(system: int, op: str) -> str:
    if type(system) is not int or not isinstance(op, str) or op not in READ_ONLY_OPS.get(system, ()):
        raise ValueError(f"system {system!r} operation {op!r} has no qualified read-only adapter")
    return "read_only"


def _bounded_json(value) -> str:
    nodes = 0
    def inspect(v, depth=0):
        nonlocal nodes
        nodes += 1
        if nodes > MAX_INPUT_NODES or depth > 16:
            raise CapabilityError("Foundry input nesting or node ceiling exceeded")
        if isinstance(v, dict):
            if len(v) > MAX_COLLECTION or any(not isinstance(k, str) for k in v):
                raise CapabilityError("Foundry mapping requires bounded string keys")
            for x in v.values():
                inspect(x, depth + 1)
        elif isinstance(v, list):
            if len(v) > MAX_COLLECTION:
                raise CapabilityError("Foundry collection ceiling exceeded")
            for x in v:
                inspect(x, depth + 1)
        elif type(v) in (int, float):
            if not math.isfinite(v) or abs(v) > 1e100:
                raise CapabilityError("Foundry numeric input must be finite and bounded")
        elif v is not None and type(v) not in (str, bool):
            raise CapabilityError("Foundry input must be JSON data")
    inspect(value)
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CapabilityError("invalid Foundry JSON data") from exc
    if len(encoded.encode()) > MAX_INPUT_BYTES:
        raise CapabilityError("Foundry input exceeds 64 KiB")
    return encoded


def _canonical_events(ctx: InvocationContext, args: dict, *, snapshot_head=None, mission_id=None) -> list[dict]:
    if "events" in args:
        raise CapabilityError("canonical journal events cannot be supplied by a worker")
    if ctx.journal is None:
        raise CapabilityError("canonical journal unavailable")
    ok, why = ctx.journal.ledger.verify_chain()
    if not ok:
        raise CapabilityError(f"canonical journal integrity failed: {why}")
    caller = mission_id or (ctx.cognition_budget.mission_id if ctx.cognition_budget else None)
    if not caller:
        raise CapabilityError("authenticated mission scope is unavailable")
    if args.get("mission_id") not in (None, caller):
        raise CapabilityError("journal projection cannot expand the authenticated mission scope")
    head = ctx.journal.ledger.head if snapshot_head is None else snapshot_head
    retained_head = ctx.journal.ledger.find(head)
    if retained_head is None:
        raise CapabilityError("journal snapshot head is not retained in the canonical chain")
    # The canonical ledger also retains flat authority audit records. They
    # are not EventSpine envelopes and must not be reinterpreted as GREG
    # mission events. Reuse the native Journal replay/schema semantics, then
    # constrain its view to the retained prefix and authenticated mission.
    positions = {r.payload["event_id"]: r.seq for r in ctx.journal.ledger.by_type("event")
                 if "event_id" in r.payload}
    events = []
    for event in ctx.journal.replay():
        if positions[event.event_id] > retained_head.seq or event.payload.get("mission_id") != caller:
            continue
        events.append({"type": event.type, "event_id": event.event_id, "payload": event.payload, "at": event.occurred_at})
        if len(events) > MAX_COLLECTION:
            raise CapabilityError("journal projection ceiling exceeded; request one mission")
    return events


def _compute(system: int, op: str, args: dict, ctx: InvocationContext, *, snapshot_head=None, mission_id=None):
    from foundry.systems import module
    mechanism = module(system)
    if system == 6 and op == "verify_member":
        return mechanism.prove_and_verify(args["records"], args["member"], args["trusted_root"])
    if system == 18:
        # A graph is a representation of claimed/recorded dependencies. It is
        # never a causal-identification certificate or an authority decision.
        if "graph" in args:
            graph = mechanism.Graph.from_dict(args["graph"])
            scope = "declared structural graph; statements unverified"
        else:
            graph = mechanism.from_greg(_canonical_events(ctx, args, snapshot_head=snapshot_head, mission_id=mission_id))
            scope = "canonical event ancestry; causation and legitimacy unverified"
        if op == "why":
            return {"ancestors": graph.why(args["node"]), "scope": scope}
        if op == "impact":
            return {"descendants": graph.impact(args["node"]), "scope": scope}
        return {"shared": graph.shared(args["kind"]), "scope": scope}
    if system == 40:
        if op == "best_report":
            if type(args["belief"]) not in (int, float) or not 0 <= args["belief"] <= 1:
                raise ValueError("belief must be a probability")
        elif (not isinstance(args["bids"], dict) or len(args["bids"]) < 2
              or any(type(v) not in (int, float) or v < 0 for v in args["bids"].values())):
            raise ValueError("procurement analysis needs at least two nonnegative bids")
    if system == 43:
        model = mechanism.APPROVAL_BOUNDARY if op == "check_approval_boundary" else args["model"]
        requested = args.get("max_states", 2000)
        if type(requested) is not int or requested < 1:
            raise ValueError("max_states must be a positive integer")
        budget = MAX_COMPUTE_OPERATIONS
        if ctx.cognition_budget is not None:
            budget = min(budget, ctx.cognition_budget.compute_ceiling_operations)
        transitions = max(1, len(model.get("transitions", [])))
        effective = min(requested, max(1, budget // transitions))
        result = mechanism.check(model, effective)
        return {**result, "native_status": "UNKNOWN" if result["holds"] is None else
                "ENCODED_MODEL_EXHAUSTED" if result["holds"] else "COUNTEREXAMPLE",
                "requested_state_limit": requested, "effective_state_limit": effective,
                "formalization_scope": "hand-declared finite model only; actual runtime is not thereby verified"}
    if system == 44:
        events = _canonical_events(ctx, args, snapshot_head=snapshot_head, mission_id=mission_id)
        if op == "correlate":
            return mechanism.correlate(events, args.get("mission_id"))
        if op == "metrics":
            return mechanism.metrics(events, start=args.get("start"), end=args.get("end"))
        if op == "why_changed":
            return mechanism.why_changed(events, args["metric"], split=args["split"],
                                         start=args.get("start"), end=args.get("end"))
        return {"spans": mechanism.otel_spans(events)}
    return mechanism.QUERY_OPS[op](args, ctx.workspace)


def _evaluate(params: dict, ctx: InvocationContext, *, snapshot_head=None, mission_id=None) -> dict:
    if ctx.manifest.capability_id != "foundry.query" or ctx.manifest.consequence_class != "read_only":
        raise CapabilityError("Foundry query requires the canonical read-only manifest")
    if not isinstance(params, dict) or set(params) != {"system", "op", "args"} or not isinstance(params["args"], dict):
        raise CapabilityError("Foundry query requires exactly system, op and JSON args")
    encoded = _bounded_json(params)
    system, op = params["system"], params["op"]
    try:
        operation_class(system, op)
    except ValueError as exc:
        raise CapabilityError(str(exc)) from None
    if ctx.target != f"foundry:{system}:{op}":
        raise CapabilityError("Foundry system/operation does not match the signed target")
    required, optional = ARGUMENT_FIELDS[system, op]
    if required - set(params["args"]) or set(params["args"]) - required - optional:
        raise CapabilityError("Foundry operation arguments have missing or unknown fields")
    canonical_projection = system == 44 or (system == 18 and "graph" not in params["args"])
    if canonical_projection:
        if ctx.journal is None:
            raise CapabilityError("canonical journal unavailable")
        snapshot_head = ctx.journal.ledger.head if snapshot_head is None else snapshot_head
        mission_id = mission_id or (ctx.cognition_budget.mission_id if ctx.cognition_budget else None)
        if not mission_id:
            raise CapabilityError("authenticated mission scope is unavailable")
    try:
        result = _compute(system, op, params["args"], ctx, snapshot_head=snapshot_head, mission_id=mission_id)
        output = json.dumps(result, sort_keys=True, allow_nan=False)
        if len(output.encode()) > MAX_READ_BYTES:
            raise CapabilityError("Foundry result exceeds the output ceiling")
    except CapabilityError:
        raise
    except ImportError as exc:
        raise CapabilityError(f"CAPABILITY_UNAVAILABLE: optional Foundry dependency {exc.name!r}") from None
    except Exception as exc:
        raise CapabilityError(f"Foundry system {system} refused {op}: {type(exc).__name__}: {exc}") from None
    return {"schema_version": "0.1", "system": system, "op": op, "result": result,
            "input_digest": "sha256:" + hashlib.sha256(encoded.encode()).hexdigest(),
            "implementation_ref": "PR132 da3d4ac8643ecf6791ffadcac064f8bb1cc6269d; bounded canonical extraction",
            "evidence_scope": "scoped computation over supplied data or a checked journal projection; no world truth or authority",
            "journal_head": snapshot_head if canonical_projection else None,
            "scope_mission_id": mission_id if canonical_projection else None,
            "world_validity": "WORLD_UNVERIFIED",
            "shared_dependencies": ["same source implementation", "same declared inputs", "canonical journal prefix when used"],
            "authority_created": False, "external_effect": False, "learning_updated": False}


def query(params: dict, ctx: InvocationContext) -> dict:
    return _evaluate(params, ctx)


def revalidate(params: dict, original_output: dict, ctx: InvocationContext, *, mission_id: str) -> dict:
    """Challenge the original artifact without a new authority or live projection.

    The caller is the independent native appraiser after binding the exact
    signed mission, sensor input and Gate witness. This function establishes
    computational agreement and retained-prefix integrity only. It shares
    producer implementation and data; it cannot certify empirical truth.
    """
    if not isinstance(original_output, dict):
        raise CapabilityError("original Foundry artifact is missing")
    canonical_projection = params.get("system") == 44 or (params.get("system") == 18 and "graph" not in params.get("args", {}))
    if canonical_projection:
        if original_output.get("scope_mission_id") != mission_id or not isinstance(original_output.get("journal_head"), str):
            raise CapabilityError("original Foundry snapshot is not bound to this authenticated mission and head")
    expected = _evaluate(params, ctx, snapshot_head=original_output.get("journal_head") if canonical_projection else None,
                         mission_id=mission_id if canonical_projection else None)
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if canonical(expected) != canonical(original_output):
        raise CapabilityError("original Foundry artifact differs from recomputed inputs or retained journal prefix")
    return {"verified": True, "current_world_observation": False, "world_validity": "WORLD_UNVERIFIED",
            "execution_scope": "separate native appraisal; same algorithm and data dependencies",
            "journal_head": original_output.get("journal_head"), "input_digest": original_output["input_digest"],
            "shared_dependencies": expected["shared_dependencies"], "authority_created": False}


def apply(params: dict, ctx: InvocationContext) -> dict:
    raise CapabilityError("Foundry writes must use existing canonical capability owners; no generic apply route")
