"""The Polyintelligence Cortex on the canonical GREG path (directive sections 3, 7, 8, 16).

One entry: the existing ``cognition.solve`` capability (PR #140), invoked by a
founder-signed mission through the AuthorityOffice and the Kernel Consequence Gate.
A request whose top-level key is ``problem`` uses the cortex contract (PR #141);
every other request keeps #140's operation contract unchanged. Both produce one
receipt envelope (``CognitiveReceipt``), retained by the same Gate receipt,
re-observed by the same separate-process appraiser and settled by the same
journal projection (``settlement.py``). One registry: every cortex organ is a GREG
``CapabilityManifest`` (``catalog.py``); a founder detach of that manifest is
projected into cortex eligibility (``IntelligenceRegistry.withhold``), so the
cortex never decides its own attachment.

The cortex runs in the same bounded worker process as #140's solvers
(``worker.py``: CPU and address-space limits, scrubbed environment, no network
unless the founder selected a loopback model and the problem carries sources).
The body re-validates the worker's receipt against the strict cortex-receipt
schema and its content address before anything is retained: worker output is
data, not authority.

Compatibility membrane: cortex receipt -> CognitiveReceipt (Final Build Order section 8)

    source contract       contracts/cortex-receipt.schema.json (0.2)
    destination contract  greg.cognition.contracts.CognitiveReceipt
    field mapping         problem_id <- request.problem_id
                          geometry <- _geometry(cortex geometry) (lossy, see below)
                          consequence_vector <- harm levels none/low/medium/high/critical as
                              0/.25/.5/.75/1; "unknown" as None (never coerced to zero)
                          method/method_version <- GREG capability of the single executed
                              organ, else the router capability "cognition.cortex"
                          epistemic_class <- cortex class, renamed where vocabularies differ
                          output <- {answer, state, disposition}
                          proof_type/proof_artifact <- "cortex_receipt" / the whole receipt
                          alternative_methods_considered <- eligibility rows + alternatives
                          strongest_counterargument, falsification_condition,
                              missing_information <- cortex accountability
                          abstention_state <- _abstention(state, disposition, verifier)
                          evaluator/evaluator_result <- the adversarial verifier
                          formal_validity <- cortex truth.formal_validity, renamed
                          outcome <- cortex outcome (directive taxonomy), unchanged
    information lost      none: the complete cortex receipt is the typed proof artifact;
                          the top-level GREG geometry is a coarser projection
    information added     GREG capability ids; input_digest of the signed params;
                          measured worker latency
    assumptions           the worker ran the reviewed code at this commit; integrity is the
                          receipt's content address, not an independent implementation
    failure behavior      any worker failure, contract violation or address mismatch yields an
                          ABSTAIN receipt naming the failure; nothing is claimed
    rollback              detach ``cognition.cortex`` (signed CAPABILITY_DETACH); retained
                          receipts stay in the ledger
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from cortex.contracts import CORTEX_VERSION, digest as cortex_digest
from cortex.schemas import validate as validate_cortex

from .contracts import (CognitionError, CognitiveReceipt, ConsequenceVector, ProblemGeometry, canonical, digest,
                        retained_data, strict_data)

ROOT = Path(__file__).resolve().parents[2]
ROUTER = "cognition.cortex"
VERIFIER = "cortex.verifier.adversarial@0.1.0"
# cortex organ key -> GREG capability id. tests/unit/test_greg_cortex_bridge.py keeps this
# equal to the cortex seed registry's enabled solver organs (no silent drift).
ORGANS = {
    "cortex.formal.z3@0.2.0": "cognition.cortex.formal.z3",
    "cortex.optimization.cpsat@0.2.0": "cognition.cortex.optimization.cpsat",
    "cortex.estimation.fermi@0.1.0": "cognition.cortex.estimation.fermi",
    "cortex.evidence_causal@0.1.0": "cognition.cortex.evidence_causal",
    "cortex.semantic@0.1.0": "cognition.cortex.semantic",
    "cortex.deterrence.accountability@0.1.0": "cognition.cortex.deterrence.accountability",
    "cortex.extraction.schedule@0.1.0": "cognition.cortex.extraction.schedule",
}
CAPABILITY_OF = dict(ORGANS)
ORGAN_OF = {cid: key for key, cid in ORGANS.items()}
MAX_REQUEST_BYTES = 64 * 1024
_LEVEL = {"none": 0.0, "low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0, "unknown": None}
_HARM_TO_VECTOR = {"physical": "physical", "financial": "financial", "rights": "rights", "privacy": "privacy",
                   "reputational": "reputation", "discrimination": "discrimination",
                   "third_party": "innocent_third_party", "irreversible_disclosure": "disclosure",
                   "systemic": "systemic_externality", "tail_risk": "tail_risk"}
_CLASS = {"deductive_logical": "deductive", "normative_value": "normative", "physical_perceptual": "physical",
          None: "unresolved"}
_FORMAL = {"valid_given_encoding": "VALID_CONDITIONAL_ON_MODEL", "not_established": "UNKNOWN",
           "not_applicable": "NOT_APPLICABLE"}


def _validate(params) -> tuple[str, dict, list]:
    if not isinstance(params, dict) or set(params) - {"problem_id", "problem", "records"}:
        raise CognitionError("cortex request takes problem_id, problem and optional records")
    strict_data(params)
    if len(canonical(params).encode()) > MAX_REQUEST_BYTES:
        raise CognitionError("cortex request exceeds 64 KiB")
    pid, problem = params.get("problem_id"), params.get("problem")
    if not isinstance(pid, str) or not 1 <= len(pid) <= 128:
        raise CognitionError("bounded problem identity required")
    if not isinstance(problem, dict) or set(problem) - {"question", "payload"} or \
            not isinstance(problem.get("payload", {}), dict):
        raise CognitionError("problem takes question and payload")
    records = params.get("records", [])
    if not isinstance(records, list) or len(records) > 64:
        raise CognitionError("records must be a list of at most 64 authority records")
    return pid, {"problem_id": pid, "question": str(problem.get("question", "")) or pid,
                 "payload": problem.get("payload", {})}, records


def withheld(registry, *, forced: str | None = None) -> dict:
    """GREG lifecycle -> cortex eligibility. A detached or quarantined manifest withholds its organ."""
    out = {}
    for key, cid in ORGANS.items():
        if cid not in registry.manifests:
            out[key] = f"{cid} is not registered in GREG"
            continue
        ok, why = registry.usable(cid)
        if not ok:
            out[key] = f"{cid}: {why}"
    if forced is not None and forced in ORGAN_OF:
        for key in ORGANS:
            if key != ORGAN_OF[forced]:
                out.setdefault(key, f"signed mission pinned {forced}")
    return out


def _semantic_model(model_config, problem) -> dict | None:
    """Only a founder-selected local Ollama model, and only when the problem has sources or a
    free-text schedule request the controlled grammar may not cover."""
    if not problem["payload"].get("sources") and not problem["payload"].get("schedule_request"):
        return None
    if not model_config or "ollama" not in model_config.get("order", []) or not model_config.get("ollama_model"):
        return None
    return {"model": model_config["ollama_model"], "timeout_seconds": 60.0, "max_tokens": 1024}


def run_worker(problem: dict, records: list, *, withheld_organs: dict, semantic_model: dict | None,
               cpu_seconds: float, created_at: str) -> dict:
    from greg.capabilities import CapabilityError, run_isolated
    request = {"problem": problem, "records": records, "withheld": withheld_organs,
               "semantic_model": semantic_model, "cpu_seconds": cpu_seconds, "created_at": created_at}
    try:
        proc = run_isolated([sys.executable, "-I", str(Path(__file__).with_name("worker.py")), "__cortex__",
                             canonical(request)], cwd=ROOT, isolate_network=semantic_model is None,
                            timeout=int(cpu_seconds) + 20,
                            extra_env={"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
                                       "MKL_NUM_THREADS": "1"})
    except CapabilityError as exc:
        raise CognitionError(f"worker isolation refused: {exc}") from exc
    if proc.returncode:
        raise CognitionError(f"cortex worker stopped (exit {proc.returncode}); result unknown")
    if len(proc.stdout) > 512 * 1024:
        raise CognitionError("cortex worker output exceeds 512 KiB")
    answer = json.loads(proc.stdout)
    if "error" in answer:
        raise CognitionError(answer["error"] + ": " + answer["detail"])
    return answer


def check_receipt(receipt: dict) -> dict:
    """The body accepts worker output only if it satisfies the contract and its own address."""
    validate_cortex(receipt, "cortex-receipt")
    body = dict(receipt)
    identity = body.pop("receipt_id")
    if identity != cortex_digest(body):
        raise CognitionError("cortex receipt content address mismatch")
    if receipt["authority_created"] is not False or receipt["execution_authority"] != "none":
        raise CognitionError("cortex receipt claims authority")
    if receipt["expenditure"]["usd"] != 0:
        raise CognitionError("GREG cognition never purchases inference")
    return receipt


def _geometry(g: dict | None) -> dict:
    if not g:
        return {"epistemic_class": "unresolved", "domain": "cortex"}
    cls = _CLASS.get(g.get("epistemic_class"), g.get("epistemic_class"))
    limits = g.get("resource_limits") or {}
    harm = g.get("consequence_vector") or {}
    quality = {"high": .9, "medium": .6, "low": .3, "none": 0.0}.get(g.get("evidence_quality"), 0.0)
    return {
        "objective_type": g.get("objective") or "unknown", "domain": "cortex", "epistemic_class": cls,
        "semantic_ambiguity": {"low": .2, "high": .8}.get(g.get("ambiguity"), .5),
        "exactness_required": g.get("exactness") == "exact_required",
        "static_or_sequential": "sequential" if g.get("temporal_character") == "sequential" else "static",
        "causal_question": cls == "causal", "optimization_question": cls == "optimization",
        "forecasting_question": cls == "prediction", "evidence_quality": quality,
        "identifiability": {"declared_experiment": "identified", "declared_adjustment": "identified",
                            "unidentified": "unidentified", "model_generated": "unidentified"}.get(
            g.get("causal_structure"), "unknown"),
        "latency_limit": min(30.0, max(.01, float(limits.get("max_latency_s", 30.0)))),
        "consequence_class": g.get("consequence_class") or "read_only",
        "reversibility": {"costly_to_reverse": "partially_reversible"}.get(g.get("reversibility"),
                                                                          g.get("reversibility") or "unknown"),
        "rights_impact": harm.get("rights") not in (None, "none"),
        "legal_content": cls == "legal", "human_value_content": cls == "normative",
    }


def _vector(g: dict | None) -> dict:
    harm = (g or {}).get("consequence_vector") or {}
    out = {dst: _LEVEL.get(harm.get(src, "unknown"), None) for src, dst in _HARM_TO_VECTOR.items()}
    return out


def _abstention(receipt: dict) -> str:
    state, kind = receipt["output"]["state"], receipt["disposition"]["kind"]
    if receipt["verifier"]["blocking"]:
        return "REFUTED"
    if kind == "recommend":
        return "NONE"
    if kind == "handoff":
        return "HUMAN_REVIEW_REQUIRED"
    return {"WORLD_UNVERIFIED": "WORLD_UNVERIFIED", "NOT_IDENTIFIED": "UNIDENTIFIED",
            "FORMALIZATION_INCOMPLETE": "FORMALIZATION_INCOMPLETE", "DEPENDENCY_UNAVAILABLE": "CAPABILITY_DEFICIT",
            "NO_ELIGIBLE_METHOD": "CAPABILITY_DEFICIT", "UNSUPPORTED_GEOMETRY": "CAPABILITY_DEFICIT",
            "TIMEOUT": "UNKNOWN", "INCONCLUSIVE": "UNKNOWN", "GATE_FAILED": "PROHIBITED",
            "GATE_UNRESOLVED": "HUMAN_REVIEW_REQUIRED", "REQUIRES_HUMAN_AUTHORITY": "HUMAN_REVIEW_REQUIRED",
            "CONTESTED": "HUMAN_REVIEW_REQUIRED"}.get(state, "ABSTAIN")


def to_cognitive_receipt(params: dict, receipt: dict, started: float) -> dict:
    executed = [r["organ_id"] for r in receipt["output"]["per_route"]]
    method = CAPABILITY_OF.get(executed[0], ROUTER) if len(executed) == 1 else ROUTER
    from .catalog import CORTEX_VERSIONS
    acc = receipt["accountability"]
    strongest = acc.get("strongest_counterargument") or {}
    exp = receipt["expenditure"]
    state = _abstention(receipt)
    verifier = receipt["verifier"]
    out = CognitiveReceipt(
        problem_id=params["problem_id"], geometry=_geometry(receipt["geometry"]),
        consequence_class=(receipt["geometry"] or {}).get("consequence_class") or "read_only",
        consequence_vector=_vector(receipt["geometry"]), method=method,
        method_version=CORTEX_VERSIONS[method], epistemic_class=_geometry(receipt["geometry"])["epistemic_class"],
        input_digest=digest(params), evidence_refs=receipt["inputs"]["evidence_refs"],
        assumptions=list(receipt["assumptions"]) + ["Input and model validity are not established by computation"],
        excluded_variables=[],
        output={"answer": receipt["output"]["answer"], "state": receipt["output"]["state"],
                "disposition": receipt["disposition"]["kind"]},
        uncertainty={"conditional_on_input": True, "world_confidence": None, "statement": receipt["uncertainty"]},
        proof_type="cortex_receipt", proof_artifact=receipt,
        alternative_methods_considered=list(receipt["eligibility"]) + list(receipt["alternatives"]),
        method_selection_reason=receipt["route"]["rationale"] + f" (policy {receipt['route']['policy']})",
        strongest_counterargument=(f"{strongest.get('severity')}: {strongest.get('kind')}: {strongest.get('detail')}"
                                   if strongest else "the adversarial verifier found no counterargument"),
        falsification_condition="; ".join(f"{f['route']}: {f['condition']}" for f in acc["falsification_conditions"])
        or "no claim asserted",
        abstention_state=state, missing_information=list(acc["missing_information"]),
        compute_cost={"solver_calls": exp["solver_calls"], "model_calls": exp["model_calls"],
                      "worker_seconds": exp["seconds"], "energy": "unmeasured"},
        money_cost=0.0, latency=time.monotonic() - started, evaluator=VERIFIER,
        evaluator_result={"verdict": "REFUTED" if verifier["blocking"] else "STRUCTURALLY_VERIFIED",
                          "findings": verifier["findings"], "independence": verifier["independence"]},
        formal_validity=_FORMAL.get(receipt["truth"]["formal_validity"], "UNKNOWN"),
        causal_credit=[{"method": CAPABILITY_OF.get(k, k), "role": "solver"} for k in executed]
        + [{"method": VERIFIER, "role": "falsifier"}],
        outcome=receipt["outcome"])
    return out.to_dict()


def _failure(params: dict, why: str, started: float, *, state: str = "ABSTAIN") -> dict:
    """A truthful receipt when the cortex could not run; nothing is claimed."""
    from cortex.outcomes import classify_greg
    from .catalog import CORTEX_VERSIONS
    return CognitiveReceipt(
        problem_id=str(params.get("problem_id", "invalid"))[:128] or "invalid",
        geometry={"epistemic_class": "unresolved", "domain": "cortex"}, consequence_class="read_only",
        consequence_vector=_vector(None), method=ROUTER, method_version=CORTEX_VERSIONS[ROUTER],
        epistemic_class="unresolved", input_digest=digest(params) if isinstance(params, dict) else "none",
        evidence_refs=[], assumptions=["no cognition ran"], excluded_variables=[], output=None,
        uncertainty={"conditional_on_input": True, "world_confidence": None}, proof_type=None, proof_artifact=None,
        alternative_methods_considered=[], method_selection_reason="not routed",
        strongest_counterargument=why[:500], falsification_condition="no claim asserted",
        abstention_state=state, missing_information=[why[:500]],
        compute_cost={"solver_calls": 0, "model_calls": 0, "energy": "unmeasured"}, money_cost=0.0,
        latency=time.monotonic() - started, evaluator=VERIFIER, evaluator_result={"verdict": "NOT_RUN"},
        outcome=classify_greg(state, has_output=False)).to_dict()


def reason_cortex(params, *, registry, journal=None, model_config=None, forced=None) -> dict:
    started = time.monotonic()
    pid, problem, records = _validate(params)
    ok, why = registry.usable(ROUTER) if ROUTER in registry.manifests else (False, "not registered")
    if not ok:
        return _failure(params, f"{ROUTER} unavailable: {why}", started, state="CAPABILITY_DEFICIT")
    limits = (problem["payload"].get("resources") or {})
    cpu = min(60.0, max(5.0, float(limits.get("max_latency_s", 30.0)) + 5.0))
    try:
        receipt = run_worker(problem, records, withheld_organs=withheld(registry, forced=forced),
                             semantic_model=_semantic_model(model_config, problem), cpu_seconds=cpu,
                             created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        check_receipt(receipt)
        if receipt["versions"]["cortex"] != CORTEX_VERSION:
            raise CognitionError(f"worker ran cortex {receipt['versions']['cortex']}, body expects {CORTEX_VERSION}")
        out = to_cognitive_receipt(params, receipt, started)
        retained_data(out)
        return out
    except (CognitionError, ValueError, TypeError, KeyError, OSError) as exc:
        return _failure(params, f"{type(exc).__name__}: {str(exc)[:400]}", started)
