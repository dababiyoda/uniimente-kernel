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
           32: "commons", 33: "federation", 34: "attribution", 35: "media_engine", 36: "cas", 37: "marketplace", 38: "payments",
           39: "accounting", 40: "mechanism", 41: "reputation", 42: "twin", 43: "model_check", 44: "observability", 45: "siem",
           46: "seed", 47: "business_compiler", 48: "teams", 49: "company_loop", 50: "rabbit_hole", 51: "commissioning", 52: "repair",
           53: "build", 54: "agent_commerce",
           55: "treasury"}


# Governed implementation pluralism (Final Build Order section 9): a second lineage that solves the same numbered
# system stays registered and reachable instead of being deleted. The canonical entry above is the one whose
# completion row the audit re-derives; alternates keep their own exercises and tests.
ALTERNATES = {31: ("portal",), 32: ("community",), 34: ("journeys",), 35: ("media",), 37: ("offers",), 49: ("media_company",),
              50: ("journeys",), 54: ("offers",)}


def module(system_id: int, implementation: str | None = None):
    if implementation is not None:
        if implementation != SYSTEMS.get(system_id) and implementation not in ALTERNATES.get(system_id, ()):
            raise KeyError(f"{implementation!r} is not a registered implementation of Foundry system {system_id}")
        return importlib.import_module(f"foundry.systems.{implementation}")
    if system_id not in SYSTEMS:
        raise KeyError(f"Foundry system {system_id} is not implemented yet (see foundry/completion.yaml)")
    return importlib.import_module(f"foundry.systems.{SYSTEMS[system_id]}")


def split_op(op: str, implementation: str | None = None) -> tuple[str | None, str]:
    """'<implementation>.<op>' names one registered implementation explicitly; a bare op follows the rule."""
    if implementation is None and "." in op:
        implementation, op = op.split(".", 1)
    return implementation, op


def _declares(mod, op: str) -> bool:
    return op in getattr(mod, "QUERY_OPS", {}) or op in getattr(mod, "APPLY_OPS", {})


def implementation_for(system_id: int, op: str, implementation: str | None = None) -> str:
    """Which registered implementation serves ``op`` on a system: one deterministic rule, no hidden routing.

    An explicit ``implementation`` wins (and must be registered). Otherwise the canonical module serves
    every op it declares; an op only one alternate declares goes to that alternate, so callers written
    against either convergent lineage keep their contract. An op no implementation declares, or one
    several alternates declare, stays with the canonical module and is refused there.
    """
    implementation, op = split_op(op, implementation)
    if implementation is not None:
        module(system_id, implementation)
        return implementation
    canonical = module(system_id)
    if _declares(canonical, op):
        return SYSTEMS[system_id]
    owners = [name for name in ALTERNATES.get(system_id, ()) if _declares(module(system_id, name), op)]
    return owners[0] if len(owners) == 1 else SYSTEMS[system_id]


def module_for(system_id: int, op: str, implementation: str | None = None):
    return module(system_id, implementation_for(system_id, op, implementation))


# Convenience wrappers over the one rule above (callers written during the 2026-10-14 convergence use
# them). They add no routing of their own: every lookup goes through implementation_for.
class OperationError(KeyError):
    """An op the serving implementation does not declare in the requested table."""

    def __str__(self) -> str:
        return str(self.args[0]) if self.args else ""


def implementations(system_id: int) -> tuple[str, ...]:
    """Canonical first, then registered alternates; KeyError when the system is unregistered."""
    module(system_id)
    return (SYSTEMS[system_id], *ALTERNATES.get(system_id, ()))


def operation(system_id: int, table: str, op: str, implementation: str | None = None):
    """The callable serving ``op`` in one table under the canonical rule; OperationError when none does."""
    if table not in ("QUERY_OPS", "APPLY_OPS"):
        raise ValueError(f"unknown op table {table!r}")
    implementation, bare = split_op(op, implementation)
    serving = implementation_for(system_id, bare, implementation)
    fn = (getattr(module(system_id, serving), table, None) or {}).get(bare)
    if fn is None:
        raise OperationError(f"system {system_id} has no {table.split('_')[0].lower()} op {op!r}")
    return fn


def any_operation(system_id: int, op: str):
    """Read op if one serves, else write op: the order composition callers always used."""
    try:
        return operation(system_id, "QUERY_OPS", op)
    except OperationError:
        try:
            return operation(system_id, "APPLY_OPS", op)
        except OperationError:
            raise OperationError(f"system {system_id} has no op {op!r}") from None


def op_class(system_id: int, op: str) -> str | None:
    """'read_only' or 'internal_write' for the op the rule serves, None when none does."""
    for table, cls in (("QUERY_OPS", "read_only"), ("APPLY_OPS", "internal_write")):
        try:
            operation(system_id, table, op)
            return cls
        except OperationError:
            continue
    return None
