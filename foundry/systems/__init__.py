"""Foundry systems: the numbered arsenal as working, individually usable tools.

Each module exposes ``QUERY_OPS`` (read-only), ``APPLY_OPS`` (writes inside the
caller's store) and ``exercise(root)``, a deterministic demonstration whose
result hash is the reproducible execution evidence audited by
``foundry.completion``. GREG reaches every system through two capabilities,
``foundry.query`` and ``foundry.apply``, under the Authority Office.
"""
from __future__ import annotations

import importlib

SYSTEMS = {3: "versions", 17: "search", 18: "graph", 36: "cas", 39: "accounting", 41: "reputation",
           43: "model_check"}


def module(system_id: int):
    if system_id not in SYSTEMS:
        raise KeyError(f"Foundry system {system_id} is not implemented yet (see foundry/completion.yaml)")
    return importlib.import_module(f"foundry.systems.{SYSTEMS[system_id]}")
