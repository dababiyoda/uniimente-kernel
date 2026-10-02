"""Bounded Foundry mechanisms extracted from PR #132.

These are adapter implementations, not a capability registry. The canonical
GREG CapabilityRegistry, AuthorityOffice, Gate and journal remain the owners.
Only greg.foundry_bridge's explicit operations are invocable through GREG.
The 55-system obligation remains broader than this executable subset.
"""
from __future__ import annotations

import importlib

SYSTEMS = {1: "compiler", 2: "dsl", 6: "proofs", 11: "wasm", 17: "search", 18: "graph",
           19: "next_test", 20: "emulator", 22: "scenarios", 40: "mechanism", 41: "reputation",
           43: "model_check", 44: "observability"}


def module(system_id: int):
    if type(system_id) is not int or system_id not in SYSTEMS:
        raise KeyError(f"Foundry system {system_id!r} has no qualified adapter in this slice")
    return importlib.import_module(f"foundry.systems.{SYSTEMS[system_id]}")
