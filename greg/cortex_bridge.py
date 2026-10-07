"""Typed Cortex dialect on the existing signed cognition.solve/status mission path.

The seed dialect and its receipt history remain unchanged. Typed Cortex adds
fault-diverse integer solvers and controlled schedule extraction; graph and LP
recruit only founder-attached package functions from the existing Genesis.
No new ledger, provider selection, scheduler or consequence authority is created.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from cortex.contracts import digest
from cortex.schemas import validate
from greg.capabilities import CapabilityError
from provenance.ledger import sha256_json

_GRAPH_KIND = {"shortest_path": "graph.shortest_path", "max_flow": "graph.max_flow"}
_FORMED_CARD_FIELDS = ("distribution", "module", "runner", "runner_sha256", "pinned_paths",
                       "location", "version", "package_digest", "license")


def is_cortex(problem):
    return isinstance(problem, dict) and problem.get("dialect") == "cortex"


def normalize(problem):
    if not is_cortex(problem) or set(problem) - {"dialect", "problem_id", "question", "payload", "budget_ms"}:
        raise CapabilityError("typed Cortex requires an explicit cortex dialect and bounded problem fields")
    if not isinstance(problem.get("problem_id"), str) or not 1 <= len(problem["problem_id"]) <= 128:
        raise CapabilityError("bounded Cortex problem identity required")
    if not isinstance(problem.get("payload"), dict):
        raise CapabilityError("Cortex payload must be an object")
    budget = problem.get("budget_ms", 30000)
    if type(budget) is not int or not 100 <= budget <= 120000:
        raise CapabilityError("Cortex budget_ms must be in [100, 120000]")
    raw = json.dumps(problem, allow_nan=False)
    if len(raw.encode()) > 65536:
        raise CapabilityError("Cortex problem exceeds 64 KiB")
    return {"problem_id": problem["problem_id"], "question": str(problem.get("question", "")) or problem["problem_id"],
            "payload": problem["payload"]}, budget


def _formed(registry, problem):
    """Resolve only attached package functions; serialized cards are never authority."""
    needs = []
    payload = problem["payload"]
    graph = payload.get("graph")
    if isinstance(graph, dict) and graph.get("kind") in _GRAPH_KIND:
        needs.append(_GRAPH_KIND[graph["kind"]])
    if isinstance(payload.get("linear_program"), dict):
        needs.append("lp.optimize")
    out = {}
    for function in dict.fromkeys(needs):
        entry, why = None, "no attached formed function"
        for manifest in registry.by_function(function) if registry else ():
            ok, reason = registry.usable(manifest.capability_id)
            if not ok:
                why = f"{manifest.capability_id}: {reason}"
                continue
            prov = manifest.provenance or {}
            if prov.get("mode") != "DEPEND":
                why = f"{manifest.capability_id}: not a package-formed function"
                continue
            if any(not prov.get(k) for k in _FORMED_CARD_FIELDS):
                why = f"{manifest.capability_id}: incomplete Mechanism Card"
                continue
            from greg.genesis import CATALOG
            source = (CATALOG.get(function) or {}).get("runners", {}).get(prov["runner"])
            if not isinstance(source, str):
                why = f"{manifest.capability_id}: unknown reviewed runner"
                continue
            from greg import mechanisms
            dist = mechanisms.installed(prov["distribution"])
            if dist is None or dist.version != prov["version"] or \
                    mechanisms.digest(dist, tuple(prov["pinned_paths"]))[0] != prov["package_digest"] or \
                    hashlib.sha256(source.encode()).hexdigest() != prov["runner_sha256"]:
                why = f"{manifest.capability_id}: package or reviewed runner changed since qualification"
                # The canonical Genesis projection records/quarantines this at restore
                # or repair; advice here never edits a lifecycle state.
                continue
            entry = {"function": function, "capability_id": manifest.capability_id,
                     "runner_source": source, **{k: prov[k] for k in _FORMED_CARD_FIELDS}}
            why = None
            break
        out[function] = {"entry": entry, "why": why}
    return out


def dependency_deficits(problem, registry):
    typed, _ = normalize(problem)
    return [function for function, info in _formed(registry, typed).items() if info["entry"] is None]


def run(problem, *, registry=None, stop_check=None):
    """Run reviewed engines and adversarial checks in a bounded no-network worker."""
    typed, budget = normalize(problem)
    from greg.cognition import _worker
    started = time.monotonic()
    request = {"problem": typed, "records": [], "formed": _formed(registry, typed),
               "cpu_seconds": max(1, budget / 1000), "created_at": datetime.now(timezone.utc).isoformat(),
               "withheld": {}, "semantic_model": None}
    receipt = _worker("cortex", request, timeout=budget / 1000, stop_check=stop_check)
    validate(receipt, "cortex-receipt")
    body = dict(receipt)
    identity = body.pop("receipt_id")
    if identity != digest(body) or receipt["authority_created"] is not False or \
            receipt["execution_authority"] != "none":
        raise CapabilityError("Cortex receipt integrity or no-authority invariant failed")
    output = receipt["output"]
    answered = output["state"] in ("OK", "WORLD_UNVERIFIED") and output["answer"] is not None and \
        not receipt["verifier"]["blocking"] and receipt["disposition"]["kind"] in ("recommend", "bounded_test")
    deficits = dependency_deficits(problem, registry)
    return {"schema_version": "cognition-cortex/1", "dialect": "cortex", "problem_id": problem["problem_id"],
            "input_digest": sha256_json(problem), "policy_version": receipt["versions"]["policy"],
            "cortex_receipt": receipt, "claims": [
                {"claim_id": route["organ_id"], "method": route["organ_id"],
                 "geometry": {"epistemic_class": receipt["geometry"]["epistemic_class"]},
                 "result": {"version": route["organ_version"], "model_digest": digest(typed["payload"])},
                 "outcome": "ANSWERED_WITHIN_SCOPE" if route["state"] == "OK" else "CONDITIONAL_RESULT",
                 "verification": {"valid": not receipt["verifier"]["blocking"],
                                  "scope": "encoded computation; shared reviewed source/specification"}}
                for route in output["per_route"]], "answered": answered,
            "output": output, "dependency_deficits": deficits,
            "outcome": receipt["disposition"]["kind"], "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "authority_created": False, "execution_mode": "consequence-inert-computation",
            "verifier_digest": hashlib.sha256((Path(__file__).resolve().parents[1] /
                                               "cortex/organs/adversarial.py").read_bytes()).hexdigest(),
            "verification_scope": "encoded computation and separate execution; shared reviewed specification; "
                                  "no real-world acceptance or semantic model selected"}


def signed_problem(ctx, problem_id):
    specs = [e.payload["spec"] for e in ctx.journal.replay("mission.registered")
             if e.payload["mission_id"] == ctx.mission_id]
    problems = [s["params"]["problem"] for spec in specs for s in spec["strategies"]
                if s.get("capability") == "cognition.solve" and
                s.get("params", {}).get("problem", {}).get("problem_id") == problem_id]
    return problems[-1] if problems else None


def solve(problem, ctx):
    normalize(problem)
    key = [ctx.mission_id, problem["problem_id"]]
    retained = [e.payload for e in ctx.journal.replay("cognition.receipt")
                if [e.payload["mission_id"], e.payload["problem_id"]] == key]
    if retained and any(r["input_digest"] != sha256_json(problem) for r in retained):
        raise CapabilityError("problem ID already bound; use a new version")
    # Negative receipts are evidence of the old state. Recompute after dependency
    # attachment/repair and append a revision; never erase them or cache forever.
    result = run(problem, registry=ctx.registry, stop_check=ctx.stop_check)
    result.update({"receipt_id": sha256_json({"mission": ctx.mission_id, "problem": problem,
                                             "revision": len(retained), "receipt": result["cortex_receipt"]["receipt_id"]}),
                   "revision": len(retained), "supersedes": retained[-1]["receipt_id"] if retained else None,
                   "mission_id": ctx.mission_id, "authority_ref": ctx.authority_ref,
                   "grant_id": ctx.grant_id, "kernel_policy_version": ctx.policy_version})
    ctx.journal.record("cognition.receipt", result, key=[*key, len(retained)], sensitivity="confidential")
    return result


def status(problem, ctx):
    rows = [e.payload for e in ctx.journal.replay("cognition.receipt")
            if e.payload["mission_id"] == ctx.mission_id and e.payload["problem_id"] == problem["problem_id"]]
    deficits = dependency_deficits(problem, ctx.registry)
    if not rows:
        return {"exists": False, "answered": False, "receipt": None, "dependency_deficits": deficits}
    receipt = rows[-1]
    valid = receipt.get("dialect") == "cortex" and receipt["input_digest"] == sha256_json(problem)
    if valid and not deficits:
        fresh = run(problem, registry=ctx.registry, stop_check=ctx.stop_check)
        valid = fresh["answered"] and receipt["answered"] and fresh["output"]["answer"] == receipt["output"]["answer"]
    else:
        valid = False
    return {"exists": True, "answered": valid, "receipt": receipt, "dependency_deficits": deficits,
            "scope": "re-observed encoded computation; no real-world acceptance"}
