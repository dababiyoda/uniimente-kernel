"""Replay a compiled cognition receipt by the method, route and version it pinned.

Appraisal re-observes a cognition sensor by running it again. Learned routing
(condition preference, settled preference, settled inhibition) may since have
chosen a different method. A re-read is evidence about the method the receipt
names, so the compiler consults this pin instead of routing again. Nothing here
selects a method; it only carries the receipt's own record into that re-read.
"""
from __future__ import annotations

from contextvars import ContextVar

_PIN: ContextVar[dict | None] = ContextVar("greg_cognition_receipt_replay", default=None)


def current() -> dict | None:
    return _PIN.get()


def bind(pin: dict):
    return _PIN.set(pin)


def reset(token) -> None:
    _PIN.reset(token)


def _cortex_route(inner: dict) -> dict | None:
    """The executed cortex route the inner receipt recorded, if it recorded one."""
    routing = inner.get("routing") if isinstance(inner.get("routing"), dict) else None
    artifact = inner.get("proof_artifact") if isinstance(inner.get("proof_artifact"), dict) else None
    route = artifact.get("route") if isinstance(artifact, dict) and isinstance(artifact.get("route"), dict) else None
    out: dict = {}
    if isinstance(route, dict) and isinstance(route.get("selected"), list) and route["selected"]:
        out["selected"] = list(route["selected"])
        plan = route.get("formal_plan")
        if isinstance(plan, dict) and isinstance(plan.get("order"), list) and plan["order"]:
            out["order"] = list(plan["order"])
    if isinstance(routing, dict) and isinstance(routing.get("executed_order"), list) and routing["executed_order"]:
        out["executed_order"] = list(routing["executed_order"])
    return out or None


def pin_from_output(output) -> dict | None:
    """The method, route and version a compilation receipt pinned, or None if it did not.

    All three have to be present and agree (the selected method is the inner receipt's
    method). A missing pin is not a license to route again.
    """
    if not isinstance(output, dict):
        return None
    schema = output.get("schema")
    if not isinstance(schema, str) or not schema.startswith("greg-competency-compilation/"):
        return None
    method = output.get("method_or_composition_selected")
    selection = output.get("selection_level")
    inner = output.get("selected_receipt")
    if not isinstance(method, str) or not method or not isinstance(selection, str) or not selection:
        return None
    if not isinstance(inner, dict) or inner.get("method") != method:
        return None
    version = inner.get("method_version")
    if not isinstance(version, str) or not version or version == "none":
        return None
    route: dict = {"kind": "compiler", "selection": selection}
    cortex = _cortex_route(inner)
    if cortex is not None:
        route = {"kind": "cortex", "selection": selection, **cortex}
    return {"method": method, "version": version, "route": route}


def matches(output, pin: dict) -> bool:
    """True when ``output`` is a re-read of ``pin``: same method, route and version, no shadow,
    and the compiler recorded that it did not consult learned routing."""
    if not isinstance(output, dict) or output.get("condition_shadow"):
        return False
    replayed = output.get("replay")
    if (not isinstance(replayed, dict) or replayed.get("learned_routing") is not False
            or replayed.get("shadows") is not False):
        return False
    return pin_from_output(output) == pin
