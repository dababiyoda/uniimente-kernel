"""Foundry systems: the numbered arsenal as working, individually usable tools.

Each module exposes ``QUERY_OPS`` (read-only), ``APPLY_OPS`` (writes inside the
caller's store) and ``exercise(root)``, a deterministic demonstration whose
result hash is the reproducible execution evidence audited by
``foundry.completion``. GREG reaches every system through two capabilities,
``foundry.query`` and ``foundry.apply``, under the Authority Office.
"""
from __future__ import annotations

import importlib

SYSTEMS = {1: "compiler", 2: "dsl", 3: "versions", 4: "datamodel", 5: "event_sourcing", 6: "proofs", 7: "pki", 8: "capsec", 11: "wasm",
           12: "registry", 13: "linking", 14: "shell", 15: "workflows", 16: "promotion", 17: "search",
           18: "graph", 19: "next_test", 20: "emulator", 21: "snapshots", 22: "scenarios", 23: "distributed",
           24: "queue", 25: "cognitive_router", 27: "discovery", 28: "mcp_gateway", 30: "gate",
           31: ("webserver", "portal"), 32: "community", 34: ("attribution", "journeys"), 35: "media", 36: "cas",
           37: "offers", 38: "payments", 39: "accounting", 40: "mechanism",
           41: "reputation", 42: "twin", 43: "model_check", 44: "observability", 45: "siem", 46: "seed",
           47: "business_compiler", 48: "teams", 49: "media_company", 50: ("rabbit_hole", "journeys"),
           52: "repair", 53: "build", 54: "offers",
           55: "treasury"}


def _names(system_id: int) -> tuple[str, ...]:
    if system_id not in SYSTEMS:
        raise KeyError(f"Foundry system {system_id} is not implemented yet (see foundry/completion.yaml)")
    names = SYSTEMS[system_id]
    return (names,) if isinstance(names, str) else tuple(names)


def module(system_id: int):
    """The system's primary module: the one its completion contract, exercise and evidence name."""
    return importlib.import_module(f"foundry.systems.{_names(system_id)[0]}")


def modules(system_id: int) -> list:
    """Every module serving the system, primary first. Two lineages built complementary halves of
    #31 (serve vs build owned pages), #34 (attribution vs journey ingest) and #50 (territory
    routing vs journey routing); both stay reachable under the one number."""
    return [importlib.import_module(f"foundry.systems.{name}") for name in _names(system_id)]


def ops(system_id: int, table: str) -> dict:
    """The system's operations for a table; on a shared op name the primary module wins."""
    merged: dict = {}
    for mod in reversed(modules(system_id)):
        merged.update(getattr(mod, table, None) or {})
    return merged


def module_for(system_id: int, table: str, op: str):
    """The module that serves ``op``: the first, in primary order, whose ``table`` defines it."""
    for mod in modules(system_id):
        if op in (getattr(mod, table, None) or {}):
            return mod
    raise KeyError(f"system {system_id} has no {table.split('_')[0].lower()} op {op!r}")
