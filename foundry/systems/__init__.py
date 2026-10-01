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
           24: "queue", 27: "discovery", 28: "mcp_gateway", 30: "gate", 31: "portal", 32: "community", 34: "journeys", 35: "media", 36: "cas", 37: "offers", 39: "accounting", 40: "mechanism",
           41: "reputation", 42: "twin", 43: "model_check", 44: "observability", 45: "siem", 46: "seed", 47: "business_compiler", 48: "teams", 49: "media_company", 50: "journeys", 52: "repair", 53: "build", 54: "offers",
           55: "treasury"}


def module(system_id: int):
    if system_id not in SYSTEMS:
        raise KeyError(f"Foundry system {system_id} is not implemented yet (see foundry/completion.yaml)")
    return importlib.import_module(f"foundry.systems.{SYSTEMS[system_id]}")
