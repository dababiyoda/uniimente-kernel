"""GREG <-> Foundry: every implemented Foundry system behind the Authority Office.

``foundry.query`` (read_only) and ``foundry.apply`` (internal_write) take
``{system, op, args}``. The system's store lives inside the mission workspace,
so a system can never write outside the scope GREG already grants that mission.
An op the system does not declare for that capability is refused, so a
read-only grant cannot reach a write op.
"""
from __future__ import annotations

from pathlib import Path

from greg.capabilities import CapabilityError, InvocationContext


def _call(params, ctx: InvocationContext, table: str) -> dict:
    from foundry.systems import module
    try:
        system = int(params["system"])
        op = str(params["op"])
    except (KeyError, TypeError, ValueError):
        raise CapabilityError("foundry call needs integer 'system' and string 'op'") from None
    try:
        ops = getattr(module(system), table)
    except KeyError as exc:
        raise CapabilityError(str(exc)) from None
    if op not in ops:
        raise CapabilityError(f"system {system} has no {table.split('_')[0].lower()} op {op!r}")
    root = Path(ctx.workspace) / "foundry" / f"system-{system:02d}"
    try:
        result = ops[op](dict(params.get("args") or {}), root)
    except CapabilityError:
        raise
    except Exception as exc:  # a refusal inside the system is a refused action, not a crash
        raise CapabilityError(f"system {system} refused {op}: {type(exc).__name__}: {exc}") from None
    return {"system": system, "op": op, "result": result}


def query(params, ctx: InvocationContext) -> dict:
    return _call(params, ctx, "QUERY_OPS")


def apply(params, ctx: InvocationContext) -> dict:
    return _call(params, ctx, "APPLY_OPS")
