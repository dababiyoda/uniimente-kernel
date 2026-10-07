"""Joined founder-facing workflows on the existing mission feedback loop."""
from __future__ import annotations

from greg.templates import browser_task, _slug


def browser_worker_document(*, url: str, steps: list[dict], session: str, extracted_field: str,
                            objective: str, order: str, output: str = "draft.md",
                            provider: str = "claude-code", budget_usd: float = 1.0,
                            horizon_days: float = 1, require_context_quote: bool = True) -> dict:
    """Retrieve site evidence, commission a document, independently appraise it.

    The founder signs the browser host/steps and worker/acceptance/budget once.
    Only the complete extracted string becomes worker context. A failed browser
    check prevents commissioning; worker acceptance remains independently fixed.
    This template neither contacts recipients nor publishes the result.
    """
    if not extracted_field or not any(s.get("op") == "extract" and s.get("as") == extracted_field for s in steps):
        raise ValueError("extracted_field must name a signed browser extract step")
    if not output or output.startswith("/") or "/" in output or "\\" in output or output in (".", ".."):
        raise ValueError("output must be a filename inside the worker workspace")
    spec = browser_task(url=url, steps=steps, session=session,
                        expect={"op": "equals", "field": "status", "value": "COMPLETED"},
                        horizon_days=horizon_days)
    spec["mission_id"] = f"m:browse-work-{_slug(order)}"
    spec["founder_expression"] = f"Retrieve {extracted_field} from {url} and use it to {objective}"
    spec["intended_effect"] = "retrieved browser evidence feeds an independently appraised document automatically"
    spec["success_checks"].append({
        "check_id": "document_accepted", "description": "independent appraisal accepts the document",
        "sensor": {"capability": "worker.appraise", "params": {"order": order}, "target": f"work:{order}"},
        "predicate": {"op": "equals", "field": "verdict", "value": "ACCEPTED"}})
    spec["strategies"].append({
        "action_id": "draft-from-browser", "capability": "worker.commission", "target": f"work:{order}",
        "params": {"order": order, "mode": "document", "objective": objective, "context": "",
                   "provider": provider, "inputs": [], "allowed_paths": [output], "max_budget_usd": budget_usd,
                   "timeout_seconds": 900, "acceptance": {"output": output, "max_changed_files": 1,
                                                           "require_context_quote": require_context_quote}},
        "param_bindings": [{"param": "context", "check_id": "retrieved", "field": f"extracted.{extracted_field}"}],
        "requires": ["retrieved"], "advances": ["document_accepted"], "cost_usd": budget_usd,
        "rationale": "compose complete Gate-observed evidence into a bounded worker; independently re-appraise"})
    spec["light_cone"]["capabilities"] += ["worker.commission", "worker.appraise"]
    spec["light_cone"]["targets"].append(f"work:{order}")
    spec["light_cone"]["budget_usd"] = budget_usd
    return spec
