"""Hold a selected Ollama route when its license does not permit use.

``greg.models.effective_route_config`` re-validates a stored selection by raising.
That raise is what stops the body from opening or ticking after a license change.
This module turns that refusal into a held route. It does not edit ``greg/models.py``
(frozen in Seed Genome freeze-v13) or ``greg/licensing.py`` (#264).

``licensing.admit_model_selection`` lives on draft #264 (``6f9b0286``) and is not
on this tree or on #196. When that function is present it is called only after
``validate_route_selection`` has returned, or after that call has refused on a
license. Its extra fields are not written back into the signed selection.
"""
from __future__ import annotations


def _is_license_refusal(exc: BaseException) -> bool:
    return isinstance(exc, ValueError) and "license" in str(exc).lower()


def _narrow(selection: dict) -> dict:
    order = selection.get("order")
    if not isinstance(order, list):
        return {"order": []}
    narrow = {"order": list(order)}
    if "ollama_model" in selection:
        narrow["ollama_model"] = selection["ollama_model"]
    return narrow


def hold_selection(selection: dict, reason: str) -> dict:
    """Drop ollama. The other routes keep their order. The reason stays on the result."""
    order = selection.get("order") if isinstance(selection, dict) else None
    kept = [name for name in order if name != "ollama"] if isinstance(order, list) else []
    model = selection.get("ollama_model") if isinstance(selection, dict) else None
    return {"order": kept, "model_license_hold": {
        "model": model, "verdict": "UNASSESSED", "reason": reason,
        "manifest_sha256": None, "assessment_digest": None}}


def _needs_admit(selection: dict) -> bool:
    order = selection.get("order")
    return ((isinstance(order, list) and "ollama" in order)
            or "license_evidence" in selection or "model_license_hold" in selection)


def admit_after_validate(selection: dict) -> dict:
    """Call ``admit_model_selection`` on a selection validate has already accepted.

    Absent on this tree: the selection is returned unchanged. A failure inside the
    gate holds the route and does not raise.
    """
    if not isinstance(selection, dict) or not _needs_admit(selection):
        return selection
    from greg import licensing
    admit = getattr(licensing, "admit_model_selection", None)
    if admit is None:
        return selection
    try:
        admitted = admit(selection)
    except Exception as exc:
        return _replace_route(selection, hold_selection(
            selection, f"license: admit_model_selection failed ({type(exc).__name__})"))
    if not isinstance(admitted, dict):
        return hold_selection(selection, "license: model selection was not admitted")
    return admitted


def _hold_or_admit(selection: dict, reason: str) -> dict:
    """Validate has already refused this selection on a license. Admit, if present, is next."""
    from greg import licensing
    admit = getattr(licensing, "admit_model_selection", None)
    if admit is None:
        return hold_selection(selection, reason)
    try:
        admitted = admit(selection)
    except Exception as exc:
        return hold_selection(selection, f"license: admit_model_selection failed ({type(exc).__name__})")
    if isinstance(admitted, dict):
        return admitted
    return hold_selection(selection, reason)


def _replace_route(original, replacement: dict) -> dict:
    base = dict(original or {})
    base.pop("ollama_model", None)
    base.pop("license_evidence", None)
    base.pop("model_license_hold", None)
    base.update(replacement)
    return base


def refusal_after_admit(validated: dict, admitted: dict) -> str | None:
    """A new signed command is refused when the gate holds the model it named."""
    if not isinstance(admitted, dict):
        return "license: model selection was not admitted"
    hold = admitted.get("model_license_hold")
    if isinstance(hold, dict):
        return "license: " + str(hold.get("reason") or "model license does not permit this use")
    order = validated.get("order") if isinstance(validated, dict) else None
    admitted_order = admitted.get("order")
    if isinstance(order, list) and "ollama" in order and (
            not isinstance(admitted_order, list) or "ollama" not in admitted_order):
        return "license: the selected model was not admitted"
    return None


def validate_then_admit(body: dict) -> tuple[dict, dict]:
    """``validate_route_selection``, then ``admit_model_selection`` when it exists.

    The validated dict is what a signed ``model.configured`` fact may store.
    Admit's evidence is not part of that fact: ``validate_route_selection``
    rejects those extra fields on the next read.
    """
    from greg import models
    validated = models.validate_route_selection(body)
    return validated, admit_after_validate(validated)


def gate_model_config(model_config):
    """A config that has not yet been through ``validate_route_selection``.

    Used for an init config and for a caller that builds ``OllamaRoute`` from a
    dict. A license refusal holds. Any other refusal still raises.
    """
    if not isinstance(model_config, dict):
        return model_config
    order = model_config.get("order")
    if not isinstance(order, list) or "ollama" not in order or "ollama_model" not in model_config:
        return admit_after_validate(model_config)
    from greg import models
    narrow = _narrow(model_config)
    try:
        validated = models.validate_route_selection(narrow)
    except ValueError as exc:
        if not _is_license_refusal(exc):
            raise
        return _replace_route(model_config, _hold_or_admit(narrow, str(exc)))
    return admit_after_validate(_replace_route(model_config, validated))


def _stored_selection(journal) -> dict | None:
    changes = journal.replay("model.configured")
    if not changes:
        return None
    payload = changes[-1].payload
    selection = payload.get("selection") if isinstance(payload, dict) else None
    return selection if isinstance(selection, dict) else None


def route_config_for_body(initial, journal) -> dict:
    """The route the body may use now. A license hold never raises."""
    from greg import models
    try:
        selection = models.effective_route_config(initial, journal)
    except ValueError as exc:
        if not _is_license_refusal(exc):
            raise
        stored = _stored_selection(journal)
        source = stored if stored is not None else (initial if isinstance(initial, dict) else {})
        return _replace_route(initial, _hold_or_admit(_narrow(source), str(exc)))
    if not journal.replay("model.configured"):
        return gate_model_config(selection if isinstance(selection, dict) else {})
    return admit_after_validate(selection)
