"""Implementation fingerprints: bind a part's identity to its executable artifact.

A ``PartSpec`` describes a part; this module hashes what the part *does*: the
callable's bytecode, constants, names, defaults and closure values, recursing into
nested functions and the public state of callable objects. Two callables with the
same description but different behavior therefore get different fingerprints, and a
registration whose fingerprint disagrees with the recorded digest is refused.

The fingerprint is a stable approximation, not a proof of semantic identity: it
covers code and declared public state at registration time, not external model
weights (declare those separately via ``PartSpec.model_digest``) and not state a
callable mutates later.
"""
from __future__ import annotations

import hashlib
import inspect
import types
from typing import Any

_MAX_DEPTH = 6
_PRIMITIVE = (str, bytes, int, float, bool, type(None))


def _walk(value: Any, depth: int, seen: set[int]) -> Any:
    if depth > _MAX_DEPTH:
        return {"truncated": True}
    if isinstance(value, _PRIMITIVE):
        return value if not isinstance(value, bytes) else value.hex()
    if isinstance(value, types.CodeType):
        return {
            "code": value.co_code.hex(),
            "consts": [_walk(c, depth + 1, seen) for c in value.co_consts],
            "names": list(value.co_names),
            "varnames": list(value.co_varnames),
            "argcount": value.co_argcount,
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_walk(v, depth + 1, seen) for v in value]
        return sorted(map(repr, items)) if isinstance(value, (set, frozenset)) else items
    if isinstance(value, dict):
        return {str(k): _walk(v, depth + 1, seen) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if id(value) in seen:
        return {"cycle": type(value).__qualname__}
    seen.add(id(value))
    if isinstance(value, (types.FunctionType, types.MethodType)):
        fn = value.__func__ if isinstance(value, types.MethodType) else value
        body = {
            "qualname": fn.__qualname__,
            "module": fn.__module__,
            "code": _walk(fn.__code__, depth + 1, seen),
            "defaults": _walk(fn.__defaults__ or (), depth + 1, seen),
            "kwdefaults": _walk(fn.__kwdefaults__ or {}, depth + 1, seen),
            "closure": [_walk(c.cell_contents, depth + 1, seen) for c in (fn.__closure__ or ())
                        if _has_contents(c)],
        }
        if isinstance(value, types.MethodType):
            body["bound_to"] = _walk(value.__self__, depth + 1, seen)
        return body
    if isinstance(value, type):
        return {"class": f"{value.__module__}.{value.__qualname__}"}
    if isinstance(value, types.ModuleType):
        return {"module": value.__name__}
    # Callable objects and plain instances: class identity plus declared public state.
    state = {}
    for name, attr in sorted(vars(value).items()) if hasattr(value, "__dict__") else []:
        if name.startswith("_"):
            continue
        state[name] = _walk(attr, depth + 1, seen)
    body = {"class": f"{type(value).__module__}.{type(value).__qualname__}", "state": state}
    call = getattr(type(value), "__call__", None)
    if callable(value) and isinstance(call, types.FunctionType):
        body["call"] = _walk(call.__code__, depth + 1, seen)
    try:
        body["class_source_hash"] = hashlib.sha256(inspect.getsource(type(value)).encode()).hexdigest()
    except (OSError, TypeError):
        pass
    return body


def _has_contents(cell: Any) -> bool:
    try:
        cell.cell_contents
    except ValueError:  # empty cell
        return False
    return True


def implementation_digest(implementation: Any) -> str:
    """sha256 over the callable's code, constants, defaults, closure and public state."""
    if not callable(implementation):
        raise TypeError("implementation must be callable")
    import json

    body = _walk(implementation, 0, set())
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), default=repr).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()
