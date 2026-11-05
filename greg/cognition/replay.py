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

    The version is the executed method's own receipt's (``selected_receipt``): the catalog
    version for an operation or organ, the package version for a Genesis-formed mechanism.
    Three routes record no executed-method receipt by design: a composition, a construction
    and the constitutional human route. Their pin names the method and route with version
    None, and the compiler honours such a pin only on those routes (``compiler._pinned_row``),
    so a receipt stripped of its executed-method receipt is never re-read by name alone.
    The pin also carries the receipt's inputs digest: it is honoured only on a compile of
    those inputs.
    """
    if not isinstance(output, dict):
        return None
    schema = output.get("schema")
    if not isinstance(schema, str) or not schema.startswith("greg-competency-compilation/"):
        return None
    method = output.get("method_or_composition_selected")
    selection = output.get("selection_level")
    inner = output.get("selected_receipt")
    inputs = output.get("inputs_digest")
    if not isinstance(method, str) or not method or not isinstance(selection, str) or not selection:
        return None
    if not isinstance(inputs, str) or not inputs:
        return None
    if inner is None:
        return {"method": method, "version": None, "route": {"kind": "compiler", "selection": selection},
                "inputs_digest": inputs}
    if not isinstance(inner, dict) or inner.get("method") != method:
        return None
    version = inner.get("method_version")
    if not isinstance(version, str) or not version or version == "none":
        return None
    route: dict = {"kind": "compiler", "selection": selection}
    cortex = _cortex_route(inner)
    if cortex is not None:
        route = {"kind": "cortex", "selection": selection, **cortex}
    return {"method": method, "version": version, "route": route, "inputs_digest": inputs}


PREFERENCE_ROUTE = "preferred_by_condition_evidence"
FORMED_ROUTE = "formed_by_capability_genesis"
HUMAN_ROUTE = "constitutional_route"


def receipt_pin(output, bound_params) -> dict | None:
    """The pin the appraiser binds for a re-read of ``output``, or None when it is no compile receipt.

    Raises ValueError when the re-read would answer another question than the receipt did:
    inputs other than the receipt's (by the digest the compiler writes them with), or a route
    the receipt's own records contradict. A preference-route receipt must record that
    preference, fired and preferring its method; a receipt naming the alternative with a
    fired preference for it must be on the preference's route (the compiler writes the level
    and the record together). Returns the receipt's pin, or raises when it names none
    ("receipt method unavailable").
    """
    if not (isinstance(output, dict) and str(output.get("schema", "")).startswith("greg-competency-compilation/")):
        return None
    from .contracts import digest
    if output.get("inputs_digest") != digest(bound_params):
        raise ValueError("the receipt answered other inputs than the signed request")
    method, level = output.get("method_or_composition_selected"), output.get("selection_level")
    condition = output.get("condition") if isinstance(output.get("condition"), dict) else {}
    preference = condition.get("preference")
    fired_for_method = (isinstance(preference, dict) and preference.get("fired") is True
                        and preference.get("prefer") == method)
    if level == PREFERENCE_ROUTE and not fired_for_method:
        raise ValueError("the receipt's route is not the condition preference it records")
    from .condition_competence import ALTERNATIVE
    if method == ALTERNATIVE and level != PREFERENCE_ROUTE and fired_for_method:
        # the compiler never writes this pair: a fired preference that switched the route always records its level
        raise ValueError("the receipt records a fired preference for its method but not the preference's route")
    pin = pin_from_output(output)
    if pin is None:
        from greg.capabilities import CapabilityError
        raise CapabilityError(f"{UNAVAILABLE}: the cognition receipt does not pin a method, route and version")
    return pin


UNAVAILABLE = "receipt method unavailable"


def unmeasured(output) -> str | None:
    """Why a pinned re-read measured nothing, or None when it answered or refuted.

    The pinned method ran on the recorded route and gave no answer (its solver raised, timed
    out or abstained): judging that compile would read a missing field as a failing reading.
    The executed method's own abstention state decides; a refutation is a measurement. A
    route with no executed-method receipt is judged by the compile's own state.
    """
    if not isinstance(output, dict) or output.get("result") is not None:
        return None
    inner = output.get("selected_receipt")
    if isinstance(inner, dict) and "abstention_state" in inner:
        state = inner.get("abstention_state")
        return None if state in ("NONE", "REFUTED") else str(inner.get("reason_code") or state)
    return None if output.get("state") == "REFUTED" else str(output.get("state") or "no answer")


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
