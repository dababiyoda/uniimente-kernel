"""An additive cognitive selector, using the existing registry and ledger.

No executor, grant issuer, scheduler, policy mutation or deployment path exists.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from time import monotonic

from capabilities.genome import GenomeRegistry
from egregore.contracts import ContractError, IntegrityConflict, canonical_copy, digest
from egregore.resources import ResourceExhausted, ResourceGovernor
from .contracts import (CognitiveReceipt, CognitiveRequest, CognitiveResult, EpistemicClass,
                        GateAssessment, ProblemGeometry, ProofArtifact, ResultStatus,
                        VerificationResult, bounded_json_size)
from .genomes import SEED_METHODS, IntelligenceGenome, register_seed_genomes


def compile_geometry(request):
    """Inspect supplied structure; unstructured/ambiguous input stays unresolved."""
    hints = []
    for key, cls in (("fermi", EpistemicClass.ESTIMATE), ("formal", EpistemicClass.FORMAL),
                     ("causal_question", EpistemicClass.CAUSAL)):
        if key in request.payload:
            hints.append(cls)
    declared = request.geometry.epistemic_class
    if len(set(hints)) > 1:
        return replace(request.geometry, unresolved=(*request.geometry.unresolved, "mixed_geometry_requires_explicit_composition"))
    if hints and declared not in (EpistemicClass.UNKNOWN, hints[0]):
        return replace(request.geometry, unresolved=(*request.geometry.unresolved, "declared_geometry_conflicts_with_input"))
    if declared == EpistemicClass.UNKNOWN and hints:
        return replace(request.geometry, epistemic_class=hints[0])
    return request.geometry


def abstention(method, epistemic_class, reason, *, status=ResultStatus.ABSTAIN):
    return CognitiveResult(method, epistemic_class, status, {},
                           ProofArtifact("abstention", {"reason": reason}),
                           missing_information=(reason,))


class SeedCortex:
    RECEIPT_RECORD = "cognition.receipt"

    def __init__(self, ledger, registry=None, semantic_client=None):
        from .organs import EvidenceOrgan, FermiOrgan, FormalOrgan, SemanticOrgan
        self.ledger = ledger
        self.registry = register_seed_genomes(registry if registry is not None else GenomeRegistry())
        self.organs = {x.method: x for x in (
            SemanticOrgan(client=semantic_client), FermiOrgan(), FormalOrgan(), EvidenceOrgan())}

    @property
    def execution_authority(self):
        return "none"

    def _evidence(self, request):
        resolved = []
        remaining_bytes = 128 * 1024
        for ref in request.evidence_refs:
            rec = self.ledger.find(ref)
            if rec is None:
                raise ContractError("evidence_reference_missing")
            if rec.record_type not in ("evidence", "outcome", "event"):
                raise ContractError("reference_is_not_source_evidence")
            size = bounded_json_size(rec.payload, max_bytes=remaining_bytes)
            remaining_bytes -= size
            expiry = rec.payload.get("expires_at")
            if expiry:
                try:
                    instant = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                    if instant.tzinfo is None or instant <= datetime.now(timezone.utc):
                        raise ContractError("evidence_expired_or_timezone_missing")
                except (ValueError, AttributeError) as exc:
                    raise ContractError("invalid_evidence_expiry") from exc
            resolved.append({"ref": ref, "record_type": rec.record_type,
                             "payload": canonical_copy(rec.payload), "ts_utc": rec.ts_utc})
        return tuple(resolved)

    def think(self, request, *, gates, resources=None):
        # Reuse the canonical ledger owner's lock for check/compute/append.
        # Two cortical adapters sharing one ledger cannot double-run an ID.
        started = monotonic()
        if not isinstance(request, CognitiveRequest):
            raise ContractError("typed cognitive request required")
        if not self.ledger._lock.acquire(timeout=request.budget.max_latency_ms / 1000):
            raise ResourceExhausted("ledger busy beyond latency ceiling; no cognition executed")
        try:
            return self._think_locked(request, gates=gates, resources=resources, started=started)
        finally:
            self.ledger._lock.release()

    def _think_locked(self, request, *, gates, resources=None, started):
        from .organs import verify
        if not isinstance(request, CognitiveRequest) or not isinstance(gates, GateAssessment):
            raise ContractError("typed request and owner-supplied eligibility assessment required")
        # Revalidate and detach nested mutable values at the trust boundary.
        request = CognitiveRequest.from_dict(request.to_dict())
        gates = GateAssessment.from_dict(gates.to_dict())
        ok, reason = self.ledger.verify_chain()
        if not ok:
            raise IntegrityConflict(reason)
        input_digest = digest({"request": request.to_dict(), "gates": gates.to_dict()})
        prior = []
        for record in self.ledger.by_type(self.RECEIPT_RECORD):
            if not isinstance(record.payload.get("receipt"), dict):
                raise IntegrityConflict("malformed cognitive receipt history")
            if record.payload["receipt"].get("problem_id") == request.problem_id:
                prior.append(record)
        if prior:
            saved = prior[-1].payload["receipt"]
            if saved["input_digest"] != input_digest:
                raise IntegrityConflict("problem_id reused with changed inputs; use a new problem_id")
            cached = CognitiveReceipt.from_dict(saved)
            expected_id = digest({"kind": "cognitive_receipt", "input_digest": input_digest,
                                  "result": cached.result.to_dict(),
                                  "verification": cached.verification.to_dict()})
            original = self.ledger.find(cached.request_ref) if cached.request_ref else None
            if (cached.receipt_id != expected_id or original is None
                    or original.record_type != "cognition.request"
                    or original.payload.get("input_digest") != input_digest
                    or original.payload.get("request") != request.to_dict()
                    or cached.geometry != compile_geometry(request).to_dict()
                    or cached.gates != gates.to_dict()
                    or cached.consequence != request.consequence.to_dict()
                    or cached.evidence_refs != request.evidence_refs):
                raise IntegrityConflict("cached receipt does not match original cognitive contract")
            expected_disposition = {ResultStatus.ANSWERED: "recommend", ResultStatus.NEED_EVIDENCE: "test",
                                    ResultStatus.HUMAN_REVIEW: "handoff"}.get(cached.result.status, "abstain")
            if cached.disposition != expected_disposition or (cached.disposition == "recommend" and not gates.eligible):
                raise IntegrityConflict("cached disposition violates current eligibility or result status")
            if cached.disposition == "recommend":
                genome = self.registry.get(f"cognition.{cached.selected_method}", cached.method_version)
                if (compile_geometry(request).unresolved or not cached.verification.accepted or cached.selected_method not in SEED_METHODS
                        or cached.result.method != cached.selected_method
                        or cached.result.epistemic_class != compile_geometry(request).epistemic_class
                        or not isinstance(genome, IntelligenceGenome) or genome.validate()
                        or not genome.cognitive_profile.enabled
                        or cached.result.epistemic_class.value not in genome.cognitive_profile.geometries):
                    raise IntegrityConflict("cached recommendation lacks a verified eligible method")
            # History is reusable only while its referenced evidence remains
            # current. Expiration creates a new abstention, preserving history.
            try:
                current_evidence = self._evidence(request)
            except ContractError:
                pass
            else:
                if cached.selected_method is not None:
                    expected_request = replace(request, geometry=compile_geometry(request))
                    checked = verify(expected_request, cached.result, current_evidence)
                    if (cached.verification.accepted or cached.disposition == "recommend") and not checked.accepted:
                        raise IntegrityConflict("cached artifact failed independent revalidation")
                return cached
        request_records = [r for r in self.ledger.by_type("cognition.request")
                           if r.payload.get("input_digest") == input_digest]
        request_record = request_records[-1] if request_records else self.ledger.append(
            "cognition.request", {"input_digest": input_digest, "request": request.to_dict(),
                                  "scope": "internal audit under existing ledger retention/access policy"})
        budget = ResourceGovernor(max_model_calls=request.budget.max_model_calls,
                                  max_estimated_cost_usd=request.budget.max_cost_usd)
        geometry = compile_geometry(request)
        request = replace(request, geometry=geometry)
        alternatives = []
        selected = None
        reason = "hard eligibility gates precede solver ranking"
        verification = VerificationResult(False, ("not_evaluated",))
        result = abstention("router", geometry.epistemic_class, "no_eligible_method")
        if not gates.eligible:
            blocked = [name for name, state in gates.checks.items() if state not in ("pass", "not_applicable")]
            reason = "eligibility blocked: " + ", ".join(blocked or gates.missing or (gates.policy_verdict,))
            result = abstention("router", geometry.epistemic_class, reason,
                                status=ResultStatus.HUMAN_REVIEW if gates.policy_verdict == "require_human" else ResultStatus.ABSTAIN)
        elif geometry.unresolved:
            result = abstention("router", geometry.epistemic_class, "; ".join(geometry.unresolved))
        else:
            for method in SEED_METHODS:
                genome = self.registry.get(f"cognition.{method}", "0.1.0")
                if not isinstance(genome, IntelligenceGenome) or genome.validate():
                    continue
                profile = genome.cognitive_profile
                allowed, _ = self.registry.may_instantiate(
                    genome.name, genome.version, requested_class="read_only", requested_budget_usd=0)
                if profile.enabled and allowed and geometry.epistemic_class.value in profile.geometries:
                    alternatives.append(method)
            if alternatives:
                selected = alternatives[0]
                reason = "smallest implemented native-geometry method after hard gates; static seed policy v0.1"
                organ = self.organs[selected]
                try:
                    evidence = self._evidence(request)
                    calls = organ.model_calls
                    for _ in range(calls):
                        budget.consume_call(component=selected, estimated_cost_usd=organ.estimated_cost_usd)
                        if resources is not None:
                            resources.consume_call(component=f"cognition.{selected}", estimated_cost_usd=organ.estimated_cost_usd)
                    remaining_ms = request.budget.max_latency_ms - int((monotonic() - started) * 1000)
                    if remaining_ms <= 0:
                        raise ResourceExhausted("latency_ceiling_before_solver")
                    # The solver receives separate objects from the independently
                    # retained inputs; an organ cannot rewrite what gets verified.
                    result = organ.solve(CognitiveRequest.from_dict(request.to_dict()),
                                         tuple(canonical_copy(list(evidence))), timeout_ms=remaining_ms)
                    if (not isinstance(result, CognitiveResult) or result.method != selected
                            or result.epistemic_class != geometry.epistemic_class):
                        raise ContractError("solver returned the wrong cognitive contract")
                    # Roundtrip refuses malformed or caller-mutated nested output.
                    raw = result.to_dict()
                    raw["proof"] = ProofArtifact(**raw["proof"])
                    result = CognitiveResult(**raw)
                    verification = verify(request, result, evidence)
                    if not isinstance(verification, VerificationResult) or type(verification.accepted) is not bool:
                        raise ContractError("invalid verifier contract")
                    if not verification.accepted:
                        result = replace(result, status=ResultStatus.ABSTAIN,
                                         missing_information=(*result.missing_information, "independent_verification_failed"))
                except Exception as exc:
                    # Error types are retained; credentials or raw private inputs are not.
                    result = abstention(selected, geometry.epistemic_class,
                                        f"bounded_solver_failure:{type(exc).__name__}")
                    verification = VerificationResult(False, (f"bounded_solver_failure:{type(exc).__name__}",))
        if result.status == ResultStatus.ANSWERED:
            try:
                self._evidence(request)
            except ContractError:
                result = replace(result, status=ResultStatus.ABSTAIN,
                                 missing_information=(*result.missing_information, "evidence_not_current_at_completion"))
                verification = replace(verification, accepted=False,
                                       findings=(*verification.findings, "evidence_not_current_at_completion"))
        elapsed = (monotonic() - started) * 1000
        if elapsed > request.budget.max_latency_ms:
            result = replace(result, status=ResultStatus.ABSTAIN,
                             missing_information=(*result.missing_information, "latency_ceiling_exceeded"))
            verification = replace(verification, accepted=False,
                                   findings=(*verification.findings, "latency_ceiling_exceeded"))
        disposition = {ResultStatus.ANSWERED: "recommend", ResultStatus.NEED_EVIDENCE: "test",
                       ResultStatus.HUMAN_REVIEW: "handoff"}.get(result.status, "abstain")
        receipt = CognitiveReceipt(
            receipt_id=digest({"kind": "cognitive_receipt", "input_digest": input_digest,
                               "result": result.to_dict(), "verification": verification.to_dict()}),
            problem_id=request.problem_id, input_digest=input_digest,
            geometry=geometry.to_dict(), consequence=request.consequence.to_dict(), gates=gates.to_dict(),
            selected_method=selected, alternative_methods_considered=tuple(alternatives),
            method_selection_reason=reason, result=result, verification=verification,
            resource_usage={**budget.snapshot().to_dict(),
                            "latency_scope": "entry_through_verification; final_receipt_fsync_not_bounded"}, latency_ms=elapsed,
            evidence_refs=request.evidence_refs, disposition=disposition,
            request_ref=request_record.hash)
        self.ledger.append(self.RECEIPT_RECORD, {"receipt": receipt.to_dict()})
        return receipt
