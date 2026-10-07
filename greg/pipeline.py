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
    "network", "read_roots", "write_scope", "authority", "policy", "command", "argv"})
TYPES = {"string": str, "object": dict, "array": list, "boolean": bool, "integer": int, "number": (int, float)}

def resolve(params, journal, mission_id, *, before_seq=None):
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
                record = journal.ledger.find(data.get("receipt", ""))
                if (data.get("mission_id") == mission_id and data.get("action_id") == ref["action_id"]
                    and data.get("status") == "DONE" and record is not None
                    and record.record_type == "receipt" and (before_seq is None or record.seq < before_seq)):
                    rows.append((event, record))
            if not rows:
                raise PendingInput("producer action has no successful retained receipt: " + ref["action_id"])
            event, record = rows[-1]
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


def inspect(params, ctx):
    from greg.capabilities import CapabilityError
    if ctx.journal is None or not ctx.mission_id or ctx.target != "pipeline:" + str(params.get("action_id", "")):
        raise CapabilityError("pipeline inspection requires its signed mission and producer target")
    try:
        value, links = resolve({"$from_action": params}, ctx.journal, ctx.mission_id)
    except PendingInput:
        return {"available": False, "value": None, "bindings": []}
    except BindingError as exc:
        raise CapabilityError(str(exc)) from exc
    return {"available": True, "value": value, "bindings": links, "authority_created": False}
