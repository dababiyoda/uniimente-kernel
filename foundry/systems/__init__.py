"""Foundry systems: the numbered arsenal as working, individually usable tools.

Each module exposes ``QUERY_OPS`` (read-only), ``APPLY_OPS`` (writes inside the
caller's store) and ``exercise(root)``, a deterministic demonstration whose
result hash is the reproducible execution evidence audited by
``foundry.completion``. GREG reaches every system through two capabilities,
``foundry.query`` and ``foundry.apply``, under the Authority Office.
"""
from __future__ import annotations

import importlib

SYSTEMS = {1: "compiler", 2: "dsl", 3: "versions", 4: "datamodel", 5: "event_sourcing", 6: "proofs", 7: "pki", 8: "capsec", 9: "oci", 11: "wasm",
           12: "registry", 13: "linking", 14: "shell", 15: "workflows", 16: "promotion", 17: "search",
           18: "graph", 19: "next_test", 20: "emulator", 21: "snapshots", 22: "scenarios", 23: "distributed",
           24: "queue", 25: "cognitive_router", 27: "discovery", 28: "mcp_gateway", 29: "embassy_wire", 30: "gate", 31: "webserver",
           32: "owned_community", 33: "federation", 34: "attribution", 35: "media_engine", 36: "cas", 37: "marketplace", 38: "payments",
           39: "accounting", 40: "mechanism", 41: "reputation", 42: "twin", 43: "model_check", 44: "observability", 45: "siem", 46: "seed",
           47: "business_compiler", 48: "teams", 49: "company_loop", 50: "rabbit_hole", 51: "commissioning", 52: "repair", 53: "build",
           54: "agent_commerce",
           55: "treasury"}


# Governed implementation pluralism (UNIIMENTE Final Build Order section 9). Where two
# lineages built the same numbered system, both stay registered: the primary in
# SYSTEMS backs the audited completion evidence (``exercise``); each co-implementation
# keeps its own store conventions, tests and contract row (``co_implementations`` in
# foundry/completion.yaml) and its ops stay reachable through the same system number.
# An op name declared by more than one implementation must be qualified as
# "<implementation>.<op>"; a bare ambiguous name is refused, never resolved silently.
CO_IMPLEMENTATIONS = {31: ("portal",), 32: ("community",), 34: ("journeys",), 35: ("media",), 37: ("offers",),
                      49: ("media_company",), 50: ("journeys",), 54: ("offers",)}


def module(system_id: int):
    if system_id not in SYSTEMS:
        raise KeyError(f"Foundry system {system_id} is not implemented yet (see foundry/completion.yaml)")
    return importlib.import_module(f"foundry.systems.{SYSTEMS[system_id]}")


def implementations(system_id: int) -> tuple[str, ...]:
    """Primary first, then co-implementations; KeyError when the system is unregistered."""
    module(system_id)
    return (SYSTEMS[system_id], *CO_IMPLEMENTATIONS.get(system_id, ()))


def operations(system_id: int, table: str) -> dict[str, tuple[str, str]]:
    """Every reachable op name -> (implementation, bare op) for one table.

    Unambiguous bare names and every qualified "<implementation>.<op>" name are
    listed; a bare name two implementations declare is listed only qualified.
    """
    if table not in ("QUERY_OPS", "APPLY_OPS"):
        raise ValueError(f"unknown op table {table!r}")
    owners: dict[str, list[str]] = {}
    out: dict[str, tuple[str, str]] = {}
    for name in implementations(system_id):
        for op in getattr(importlib.import_module(f"foundry.systems.{name}"), table, None) or {}:
            owners.setdefault(op, []).append(name)
            out[f"{name}.{op}"] = (name, op)
    for op, names in owners.items():
        if len(names) == 1:
            out[op] = (names[0], op)
    return out


def ambiguous(system_id: int, table: str, op: str) -> list[str]:
    """Qualified alternatives when a bare op name is declared by several implementations."""
    if "." in op:
        return []
    names = [n for n in implementations(system_id)
             if op in (getattr(importlib.import_module(f"foundry.systems.{n}"), table, None) or {})]
    return [f"{n}.{op}" for n in names] if len(names) > 1 else []


def operation(system_id: int, table: str, op: str):
    """Resolve an op to its callable; LookupError names the refusal."""
    reachable = operations(system_id, table)
    if op not in reachable:
        choices = ambiguous(system_id, table, op)
        if choices:
            raise LookupError(f"system {system_id} op {op!r} is ambiguous; qualify it as one of {choices}")
        raise LookupError(f"system {system_id} has no {table.split('_')[0].lower()} op {op!r}")
    name, bare = reachable[op]
    return getattr(importlib.import_module(f"foundry.systems.{name}"), table)[bare]
