"""Typed data handoffs from successful actions on the canonical mission ledger.

Bindings substitute parameter values only. Capability, target, permission, budget,
credentials and tool scopes remain founder-signed literals. A producer's receipt
is integrity evidence, not independent acceptance or authority.
"""
from __future__ import annotations
import copy
import json
from provenance.ledger import sha256_json

class BindingError(ValueError):
    pass

class PendingInput(BindingError):
    pass

PROTECTED = frozenset({"allowed_paths", "tools", "provider", "max_budget_usd", "timeout_seconds",
    "repo", "base", "acceptance", "credentials", "credential_refs", "also_hosts", "url",
    "network", "read_roots", "write_scope", "authority", "policy", "command", "argv",
    # mcp.act's reach: which credentials a server is handed (as values or files), which hosts it may reach and
    # which paths it may write are founder-signed literals, never an earlier action's output
    "secrets", "secret_files", "bearer", "hosts", "writable"})
TYPES = {"string": str, "object": dict, "array": list, "boolean": bool, "integer": int, "number": (int, float)}

def resolve(params, journal, mission_id, *, before_seq=None, observe=None):
    """``observe``: a list, for pipeline.inspect, which reports the producer's value as an observation. It receives,
    per binding, whether the producer declared its own observation incomplete and whether it vouched for this field.
    Without it (a handoff into the next action's params), a value the producer's receipt did not keep whole is
    refused: the next action gets its whole input or nothing."""
    provenance = []
    def visit(value, depth=0, protected=False):
        if depth > 20:
            raise BindingError("pipeline input nesting exceeds 20")
        if isinstance(value, dict) and "$from_action" in value:
            if protected or set(value) != {"$from_action"}:
                raise BindingError("artifact cannot modify an authority or execution scope")
            ref = value["$from_action"]
            if (not isinstance(ref, dict) or set(ref) != {"action_id", "field", "type"}
                or not isinstance(ref["type"], str) or ref["type"] not in TYPES):
                raise BindingError("binding requires action_id, field and a supported type")
            if not all(isinstance(ref[k], str) and 0 < len(ref[k]) <= 128 for k in ref):
                raise BindingError("bounded binding fields required")
            rows = []
            for event in journal.replay("mission.action"):
                data = event.payload
                if (data.get("mission_id") != mission_id or data.get("action_id") != ref["action_id"]
                        or data.get("status") != "DONE"):
                    continue
                if not data.get("receipt"):     # a founder-reconciled execution: its output was never retained
                    if before_seq is None or _event_seq(journal, event) < before_seq:
                        rows.append((event, None))
                    continue
                record = journal.ledger.find(data["receipt"])
                if (record is not None and record.record_type == "receipt"
                        and (before_seq is None or record.seq < before_seq)):
                    rows.append((event, record))
            if not rows:
                raise PendingInput("producer action has no successful retained receipt: " + ref["action_id"])
            event, record = rows[-1]
            if record is None:              # never an older receipt: that output is not the latest execution's
                raise BindingError(ref["action_id"] + "'s latest execution was reconciled without a retained "
                                   "receipt; its output is unknown")
            result = record.payload.get("result", {})
            if result.get("result_class") != "positive":
                raise BindingError("producer receipt is not a positive result")
            output = result.get("output")
            for part in ref["field"].split("."):
                if not isinstance(output, dict) or part not in output:
                    raise BindingError("producer output is missing the declared field")
                output = output[part]
            wanted = TYPES[ref["type"]]
            if type(output) not in (wanted if isinstance(wanted, tuple) else (wanted,)):
                raise BindingError("producer output violates the declared type")
            from greg.missions import _held_back
            held = _held_back(output)
            if held and observe is None:
                # a list the receipt kept to its first items, or a value holding a string kept as a prefix, is not
                # the producer's value: handed on, the next action would act on a silently shortened input (review
                # of #196, J4; bind edges have refused it since #201's review, 5b)
                raise BindingError(f"producer output {ref['field']} {held}; a part is not handed on as the whole value")
            if observe is not None:
                top = result.get("output")
                declared = isinstance(top, dict) and top.get("complete") is False and ref["field"] != "complete"
                observe.append((declared, declared and isinstance(top.get("decided"), list)
                                and ref["field"] in top["decided"]))
            try:
                encoded = json.dumps(output, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise BindingError("producer output is not bounded JSON data") from exc
            if len(encoded.encode()) > 65536:
                raise BindingError("producer output exceeds 64 KiB")
            provenance.append({**ref, "mission_id": mission_id, "action_event": event.event_id,
                               "receipt": record.hash, "value_digest": sha256_json(output)})
            return copy.deepcopy(output)
        if isinstance(value, dict):
            return {k: visit(v, depth+1, protected or k in PROTECTED) for k,v in value.items()}
        if isinstance(value, list):
            return [visit(v, depth+1, protected) for v in value]
        return value
    return visit(params), provenance


def _event_seq(journal, event) -> int:
    """Ledger position of a journal event (its own record, since it carries no receipt)."""
    return next((r.seq for r in journal.ledger.by_type("event") if r.payload.get("event_id") == event.event_id),
                1 << 60)


def inspect(params, ctx):
    from greg.capabilities import CapabilityError
    if ctx.journal is None or not ctx.mission_id or ctx.target != "pipeline:" + str(params.get("action_id", "")):
        raise CapabilityError("pipeline inspection requires its signed mission and producer target")
    observed = []
    try:
        value, links = resolve({"$from_action": params}, ctx.journal, ctx.mission_id, observe=observed)
    except PendingInput:
        return {"available": False, "value": None, "bindings": []}
    except BindingError as exc:
        raise CapabilityError(str(exc)) from exc
    out = {"available": True, "value": value, "bindings": links, "authority_created": False}
    declared, vouched = observed[0] if observed else (False, False)
    if declared:
        # the producer declared its observation incomplete (a PDF page with no text layer): the inspected value says
        # so too, so a check on it keeps only what more data could not undo. Before, inspection dropped the
        # declaration, and not_contains passed on a partly read document (review of #196, J3)
        out["complete"] = False
        out["decided"] = ["available", "bindings", "authority_created"] + (["value"] if vouched else [])
    return out
