"""P6 cognitive composition: typed chains of cortex intelligences, routed by problem geometry.

A composite problem names what it knows (an estimation model, causal studies, a formal model with
typed parameter slots). The router recognises which recipe the geometry calls for; each stage is an
ordinary cortex request through ``cognition.reason`` (the same bounded, network-isolated worker,
verifier and receipt), and a typed translation step carries one stage's verified answer into the next
stage's model. Nothing here is a new solver or a new authority:

    composite problem
      -> route(payload)                       geometry -> recipe (or none: no composition)
      -> stage 1..k (cortex receipts)          estimate / identify
      -> translate                             {"$param": "<stage>.<field>"} -> number (typed,
                                               rounded as declared; any failure is recorded)
      -> final stage (cortex receipt)          optimize, certified by the cortex as usual
      -> composition receipt                   stage receipt ids, bindings, failures, latency

A stage that abstains, a translation that fails, or a chain that exceeds its latency budget makes
the composition abstain; the receipt says which. ``recipe`` in the request pins one chain (a static
composition); without it the geometry router chooses.

Recipes live in ``RECIPES``; each declares the payload keys that identify its geometry. A recipe is
eligible only when exactly its geometry is present, so two recipes never claim the same problem.
"""
from __future__ import annotations

import copy
import math
import time

from .contracts import CognitionError, canonical, digest, strict_data

SCHEMA = "greg-composition/0.1"
MAX_REQUEST_BYTES = 192 * 1024
DECL = {"consequence_class": "read_only", "reversibility": "reversible"}

RECIPES = {
    # Fermi estimate -> robust optimisation: the optimiser's demand slot takes an estimate quantile.
    "estimate_then_optimize": {"requires": ("estimation_model", "formal_template"),
                               "stages": ("estimate", "optimize")},
    # Causal identification of each intervention -> allocation over the identified effects.
    "identify_then_optimize": {"requires": ("causal_studies", "formal_template"),
                               "stages": ("identify", "optimize")},
}


def route(payload: dict) -> str | None:
    """The recipe whose geometry the payload has, or None when no single recipe fits."""
    keys = set(payload)
    matches = [name for name, r in RECIPES.items() if set(r["requires"]) <= keys]
    return matches[0] if len(matches) == 1 else None


class TranslationError(CognitionError):
    """A stage's answer could not be carried into the next stage's model."""


def _lookup(values: dict, path: str):
    node = values
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise TranslationError(f"no value at {path}")
        node = node[part]
    if isinstance(node, bool) or not isinstance(node, (int, float)) or not math.isfinite(node):
        raise TranslationError(f"{path} is not a finite number")
    return float(node)


def substitute(template, values: dict, bindings: list):
    """Replace every {"$param": path, "scale": s, "round": r} node with a number."""
    if isinstance(template, dict) and "$param" in template:
        if set(template) - {"$param", "scale", "round"}:
            raise TranslationError("a parameter slot takes $param, scale and round only")
        value = _lookup(values, template["$param"]) * float(template.get("scale", 1))
        rounding = template.get("round", "ceil")
        if rounding == "ceil":
            out = int(math.ceil(value - 1e-9))
        elif rounding == "floor":
            out = int(math.floor(value + 1e-9))
        elif rounding == "nearest":
            out = int(round(value))
        else:
            raise TranslationError(f"unknown rounding {rounding!r}")
        bindings.append({"slot": template["$param"], "value": value, "scale": template.get("scale", 1),
                         "round": rounding, "bound": out})
        return out
    if isinstance(template, dict):
        return {k: substitute(v, values, bindings) for k, v in template.items()}
    if isinstance(template, list):
        return [substitute(v, values, bindings) for v in template]
    return template


def _stage(reason, pid: str, question: str, payload: dict, *, registry, journal, model_config) -> dict:
    receipt = reason({"problem_id": pid[:128], "problem": {"question": question, "payload": payload}},
                     registry=registry, journal=journal, model_config=model_config)
    return receipt


def _summary(name: str, receipt: dict) -> dict:
    output = receipt.get("output") or {}
    return {"stage": name, "receipt_id": receipt["receipt_id"], "method": receipt["method"],
            "abstention_state": receipt["abstention_state"], "answer": output.get("answer"),
            "state": output.get("state"), "latency_s": round(receipt["latency"], 4)}


def validate(params) -> tuple[str, dict]:
    if not isinstance(params, dict) or set(params) - {"problem_id", "chain"}:
        raise CognitionError("a composite request takes problem_id and chain")
    strict_data(params)
    if len(canonical(params).encode()) > MAX_REQUEST_BYTES:
        raise CognitionError("composite request exceeds 192 KiB")
    chain = params.get("chain")
    if not isinstance(chain, dict) or set(chain) - {"question", "payload", "recipe", "max_latency_s"} or \
            not isinstance(chain.get("payload"), dict):
        raise CognitionError("chain takes question, payload, optional recipe and max_latency_s")
    recipe = chain.get("recipe")
    if recipe is not None and recipe not in RECIPES:
        raise CognitionError(f"unknown recipe {recipe!r}")
    pid = params.get("problem_id")
    if not isinstance(pid, str) or not 1 <= len(pid) <= 96:
        raise CognitionError("bounded problem identity required")
    return pid, chain


def run(params, *, registry, journal=None, model_config=None) -> dict:
    from .cortex import reason
    started = time.monotonic()
    pid, chain = validate(params)
    payload = chain["payload"]
    question = str(chain.get("question", "")) or pid
    budget = float(chain.get("max_latency_s", 60.0))
    recipe = chain.get("recipe") or route(payload)
    routed_by = "fixed" if chain.get("recipe") else "geometry"
    receipt = {"schema": SCHEMA, "problem_id": pid, "input_digest": digest(params), "recipe": recipe,
               "routed_by": routed_by, "stages": [], "bindings": [], "translation_failures": [],
               "answer": None, "state": "ABSTAIN", "reason": None, "authority_created": False,
               "execution_authority": "none"}

    def finish(state, why=None, answer=None):
        receipt.update(state=state, reason=why, answer=answer,
                       latency_s=round(time.monotonic() - started, 4))
        if state == "ANSWERED" and receipt["latency_s"] > budget:
            receipt.update(state="TIMEOUT", reason=f"chain took {receipt['latency_s']}s of {budget}s", answer=None)
        receipt["receipt_id"] = digest({k: v for k, v in receipt.items() if k != "receipt_id"})
        return receipt

    if recipe is None:
        return finish("NO_RECIPE", "no single composition recipe matches this geometry")
    missing = [k for k in RECIPES[recipe]["requires"] if k not in payload]
    if missing:
        return finish("NO_RECIPE", f"recipe {recipe} needs {missing}")
    declared = payload.get("declared", DECL)
    values = {}
    kw = dict(registry=registry, journal=journal, model_config=model_config)
    if recipe == "estimate_then_optimize":
        first = _stage(reason, f"{pid}/estimate", question,
                       {"estimation_model": payload["estimation_model"], "declared": declared}, **kw)
        receipt["stages"].append(_summary("estimate", first))
        if first["abstention_state"] != "NONE" or not isinstance((first.get("output") or {}).get("answer"), dict):
            return finish("STAGE_ABSTAINED", f"estimate: {first['abstention_state']}")
        values["estimate"] = first["output"]["answer"]
    else:
        studies = payload["causal_studies"]
        if not isinstance(studies, dict) or not 1 <= len(studies) <= 8:
            raise CognitionError("causal_studies maps 1-8 named studies")
        values["effect"] = {}
        for name, study in sorted(studies.items()):
            if not isinstance(study, dict):
                raise CognitionError("each causal study is an object")
            result = _stage(reason, f"{pid}/identify-{name}", question, {**study, "declared": declared}, **kw)
            receipt["stages"].append(_summary(f"identify:{name}", result))
            answer = (result.get("output") or {}).get("answer")
            if result["abstention_state"] not in ("NONE", "WORLD_UNVERIFIED") or not isinstance(answer, dict) \
                    or "effect" not in answer:
                return finish("STAGE_ABSTAINED", f"identify {name}: {result['abstention_state']}")
            values["effect"][name] = answer["effect"]
    try:
        model = substitute(copy.deepcopy(payload["formal_template"]), values, receipt["bindings"])
    except TranslationError as exc:
        receipt["translation_failures"].append(str(exc))
        return finish("TRANSLATION_FAILED", str(exc))
    final = _stage(reason, f"{pid}/optimize", question, {"formal_model": model, "declared": declared}, **kw)
    receipt["stages"].append(_summary("optimize", final))
    answer = (final.get("output") or {}).get("answer")
    if final["abstention_state"] != "NONE" or not isinstance(answer, dict):
        return finish("STAGE_ABSTAINED", f"optimize: {final['abstention_state']}")
    return finish("ANSWERED", None, answer)
