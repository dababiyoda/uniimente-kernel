"""Disposable typed Cortex worker; canonical GREG owns all authority and persistence."""
from __future__ import annotations
import json
import math
import resource
import sys
from greg.cortex_engines.contracts import CognitionError, canonical
def _formed_callable(entry: dict):
    """One formed function as an organ-callable: re-pin, run isolated, certify (issue #117).

    Rebuilds the qualified execution path from the Mechanism Card the bridge serialized:
    the function's own normalize enforces its competence envelope, the installed package
    is re-pinned against the card's digest before every call, the qualified runner source
    travels with the card and is re-pinned against its attested hash before it executes
    in a nested no-network interpreter, and the answer is accepted only on GREG's
    certificate. Nothing the engine asserts is trusted.
    """
    import hashlib

    from cortex.contracts import digest as cortex_digest
    from cortex.organs.formed import FormedFunctionError
    from greg import mechanisms
    from greg.capabilities import CapabilityError
    from greg.genesis import CATALOG
    from greg.mechanisms import PackageCandidate

    function = entry["function"]
    spec = CATALOG[function]
    candidate = PackageCandidate(entry["distribution"], entry["module"], entry["runner"],
                                 tuple(entry["pinned_paths"]),
                                 "pinned by the formed function's Mechanism Card",
                                 "see the formed function's Mechanism Card")

    def call(params: dict, cpu_seconds: int) -> dict:
        try:
            request = spec["normalize"](params)
        except (CapabilityError, ValueError, TypeError, KeyError) as exc:
            raise FormedFunctionError("invalid", str(exc)[:300])
        dist = mechanisms.installed(entry["distribution"])
        if dist is None or dist.version != entry["version"] or \
                mechanisms.digest(dist, tuple(entry["pinned_paths"]))[0] != entry["package_digest"]:
            raise FormedFunctionError("unavailable", "package changed since qualification; the formed "
                                                     "function must be re-qualified before it may serve")
        if hashlib.sha256(entry["runner_source"].encode()).hexdigest() != entry["runner_sha256"]:
            raise FormedFunctionError("unavailable", "runner changed since qualification; the formed "
                                                     "function must be re-qualified before it may serve")
        try:
            claims = mechanisms.run(candidate, entry["runner_source"], [request],
                                    location=entry["location"], version=entry["version"],
                                    cpu_seconds=cpu_seconds)
        except CapabilityError as exc:
            kind = "timeout" if "did not complete" in str(exc) else "unavailable"
            raise FormedFunctionError(kind, str(exc)[:300])
        claim = claims[0]
        if "error" in claim:
            raise FormedFunctionError("unavailable", f"engine raised {claim['error'][:200]}")
        calls = 1
        try:
            answer = spec["certify"](request, claim["result"])
            if answer.get("follow_up") and spec.get("follow_up"):
                # An engine's negative claim is proved or refuted by GREG's own follow-up solves.
                extras = mechanisms.run(candidate, entry["runner_source"], answer["follow_up"],
                                        location=entry["location"], version=entry["version"],
                                        cpu_seconds=cpu_seconds)
                calls += 1
                if any("error" in e for e in extras):
                    raise FormedFunctionError("unavailable", f"engine raised {next(e['error'] for e in extras if 'error' in e)[:200]}")
                answer = spec["follow_up"](request, answer, [e["result"] for e in extras])
        except spec["certificate_error"] as exc:
            raise FormedFunctionError("certificate", str(exc)[:300])
        answer.pop("follow_up", None)
        answer["_mechanism"] = {"capability_id": entry["capability_id"],
                                "distribution": entry["distribution"], "version": entry["version"],
                                "license": entry["license"], "runner": entry["runner"],
                                "package_digest": entry["package_digest"],
                                "request_sha256": cortex_digest(request),
                                "request_shape": _shape(function, request)}
        return {"answer": {**answer, "engine": f"{entry['distribution']} {entry['version']}",
                           "license": entry["license"], "authority_created": False},
                "solver_calls": calls}
    return call

def _shape(function: str, request: dict) -> dict:
    """Request dimensions for the proof without embedding the request itself."""
    if function == "lp.optimize":
        return {"variables": len(request["names"]),
                "constraints": len(request["a_ub"]) + len(request["a_eq"])}
    if function == "graph.max_flow":
        return {"nodes": len(request["nodes"]), "arcs": len(request["arcs"])}
    return {"nodes": len(request["nodes"]), "edges": len(request["edges"])}

def _formed_organs(formed: dict) -> dict:
    """Build the formed-function organs from the bridge's serialized Mechanism Cards.

    Every organ is overridden whenever the request carries formed data, so a missing or
    detached function is reported with its reason (a truthful deficit) instead of the
    default no-data organ."""
    from cortex.organs.continuous import ContinuousOptimizationOrgan
    from cortex.organs.graphsearch import FUNCTIONS, GraphSearchOrgan

    def slot(function: str):
        info = formed.get(function) or {}
        entry = info.get("entry")
        return (_formed_callable(entry) if entry else None,
                info.get("why") or "no attached formed function")

    return {"cortex.graph.search@0.2.0": GraphSearchOrgan({f: slot(f) for f in FUNCTIONS.values()}),
            "cortex.optimization.continuous@0.1.0": ContinuousOptimizationOrgan({"lp.optimize": slot("lp.optimize")})}

def cortex_main(request):
    """Run the Polyintelligence Cortex inside this bounded, network-isolated process.

    The body supplies which organs GREG's registry withholds (founder detach) and,
    only when the founder selected a local model, the loopback model to use. The
    receipt is printed; the body re-validates it before anything is retained."""
    from cortex.genome import seed_registry
    from cortex.organs.schedule_extraction import ScheduleExtractionOrgan
    from cortex.organs.semantic import SemanticOrgan
    from cortex.routing import Cortex
    seconds = max(1, math.ceil(request["cpu_seconds"]))
    resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds + 1))
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    registry = seed_registry()
    for key, why in request["withheld"].items():
        registry.withhold(key, why)
    model = request.get("semantic_model")
    if model:
        from egregore.local_model import LocalModelClient, LocalModelConfig
        client = LocalModelClient(LocalModelConfig(model=model["model"], timeout_seconds=model["timeout_seconds"],
                                                   max_tokens=model["max_tokens"]))
    else:
        client = _NoSelectedModel()
    cortex = Cortex(registry, clock=lambda: request["created_at"])
    cortex.organs["cortex.semantic@0.1.0"] = SemanticOrgan(client)
    # The extractor reads free text only through a founder-selected model; otherwise the
    # controlled grammar alone, and out-of-grammar text abstains (DEPENDENCY_UNAVAILABLE).
    cortex.organs["cortex.extraction.schedule@0.1.0"] = ScheduleExtractionOrgan(client if model else None)
    formed = request.get("formed") or {}
    if formed:
        cortex.organs.update(_formed_organs(formed))
    receipt = cortex.run(request["problem"], records=request.get("records"))
    text = canonical(receipt)
    if len(text.encode()) > 512 * 1024:
        raise CognitionError("cortex receipt exceeds 512 KiB")
    print(text)

class _NoSelectedModel:
    """GREG's founder-selected route names no local model: the semantic organ abstains."""
    def complete(self, system, user):
        raise OSError("no founder-selected local model (greg model set --route ollama --local-model <name> --key ...)")

def main():
    request = json.loads(sys.stdin.buffer.read(131073))
    cortex_main(request)

if __name__ == "__main__":
    main()
