"""Signed data bindings from successful observations on the canonical ledger.

Sensor output is untrusted data. It may fill explicit content fields, never
choose a capability, target, worker provider, executable acceptance or authority.
Bindings are re-resolved from fresh observations before every dispatch; the
existing authority office authorizes the exact resolved parameters.
"""
from __future__ import annotations

from copy import deepcopy
import json

from provenance.ledger import sha256_json

MAX_BINDING_BYTES = 16 * 1024
MAX_DEPTH = 20
# Deliberately explicit. New adapters must identify their inert data parameters
# before participating; generic parameter substitution can change authority.
BINDABLE_PARAMS = {"fs.write": {"content"}, "worker.commission": {"context", "objective"}}


class BindingError(ValueError):
    """A declared input is not complete, observed, or safe to substitute."""


def validate_bindings(strategy: dict, checks: set[str]) -> None:
    bindings = strategy.get("param_bindings", [])
    destinations = set()
    allowed = BINDABLE_PARAMS.get(strategy.get("capability") or strategy.get("function"), set())
    for binding in bindings:
        param, source = binding["param"], binding["check_id"]
        if param not in allowed:
            raise BindingError(f"parameter {param!r} is not an inert bindable field of this capability")
        if param in destinations:
            raise BindingError(f"duplicate parameter binding {param!r}")
        destinations.add(param)
        if source not in checks or source not in strategy.get("requires", []):
            raise BindingError("each binding source must be a known required check")
        if param not in strategy.get("params", {}) or not isinstance(strategy["params"][param], str):
            raise BindingError("a bound content parameter needs a signed string placeholder")


def _complete(value, depth=0) -> None:
    if depth > MAX_DEPTH:
        raise BindingError("bound value exceeds the nesting limit")
    if isinstance(value, dict):
        if value.get("truncated") is True:
            raise BindingError("bound value was truncated in the receipt")
        if len(value) > 1000:
            raise BindingError("bound value exceeds the container limit")
        for child in value.values():
            _complete(child, depth + 1)
    elif isinstance(value, list):
        # Historical bounded() receipts silently cap lists at 1000 elements.
        # A list of exactly that size cannot prove completeness, so fail closed.
        if len(value) >= 1000:
            raise BindingError("bound list may have been truncated in the receipt")
        for child in value:
            _complete(child, depth + 1)


def _select(output, path: str):
    value = output
    for part in path.split(".") if path else []:
        if isinstance(value, dict) and value.get("truncated") is True:
            raise BindingError("source path crosses a truncated receipt value")
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            if len(value) >= 1000:
                raise BindingError("source path crosses a possibly truncated list")
            value = value[int(part)]
        else:
            raise BindingError(f"source field {path!r} is missing")
    _complete(value)
    return value


def resolve_bindings(*, mission, strategy: dict, journal, observed_at: str,
                     evaluate_predicate) -> tuple[dict, list[dict]]:
    """Return adapter parameters and inspectable lineage; no retained output cache."""
    params, lineage = deepcopy(strategy.get("params", {})), []
    for binding in strategy.get("param_bindings", []):
        source, param = binding["check_id"], binding["param"]
        observation = mission.observations.get(source)
        if not observation or not observation.get("passed") or observation.get("at") != observed_at:
            raise BindingError(f"source check {source!r} has no fresh passing observation")
        receipt = journal.ledger.find(observation.get("receipt"))
        if receipt is None or receipt.record_type != "receipt":
            raise BindingError("source observation has no retained Gate receipt")
        result = receipt.payload.get("result", {})
        if result.get("result_class") != "positive":
            raise BindingError("source Gate receipt is not a successful observation")
        claims = [r for r in journal.ledger.by_type("grant_dispatch")
                  if r.payload.get("grant_id") == receipt.payload.get("grant_id")]
        if len(claims) != 1 or claims[0].payload.get("proposal_id") != observation.get("proposal_id"):
            raise BindingError("source receipt does not match the observed sensor dispatch")
        check = next(c for c in mission.spec["success_checks"] if c["check_id"] == source)
        output = result.get("output")
        if not evaluate_predicate(check["predicate"], output)[0]:
            raise BindingError("source receipt no longer satisfies the signed check")
        value = _select(output, binding["field"])
        if not isinstance(value, str):
            raise BindingError("bound content must be a complete string")
        limit = 8000 if param in ("context", "objective") else MAX_BINDING_BYTES
        if len(value) > limit:
            raise BindingError("bound content exceeds the destination's complete-value limit")
        params[param] = value
        events = [e for e in journal.replay("mission.observed")
                  if e.payload.get("mission_id") == mission.mission_id
                  and e.payload.get("check_id") == source and e.payload.get("receipt") == receipt.hash]
        if not events:
            raise BindingError("source observation is not retained on the mission spine")
        lineage.append({"param": param, "check_id": source, "field": binding["field"],
                        "receipt": receipt.hash, "observation_event": events[-1].event_id,
                        "observation_hash": journal.event_hash(events[-1].event_id),
                        "value_digest": sha256_json(value)})
    if lineage:
        try:
            size = len(json.dumps(params, ensure_ascii=False, allow_nan=False).encode())
        except (UnicodeEncodeError, ValueError) as exc:
            raise BindingError("resolved content is not complete UTF-8 JSON data") from exc
        if size > MAX_BINDING_BYTES:
            raise BindingError("resolved parameters exceed the binding byte limit")
    return params, lineage
