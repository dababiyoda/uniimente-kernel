"""Adapters to existing policy and standing cognition; no new control plane."""
from policy.engine import evaluate
from egregore.contracts import CandidateProposal, ContractError, canonical_json
from .contracts import CognitiveRequest, GateAssessment


def assess_for_cognition(compiled, proposal, *, identity_ok, grant, domain_checks):
    """Reflect canonical policy plus explicit domain assessment as advisory data.

    The host supplies domain judgments, including unresolved applicable law and
    harms. Neither this adapter nor a solver authenticates founder permission.
    The existing ConsequenceGate revalidates every actual proposed consequence.
    """
    decision = evaluate(compiled, proposal, identity_ok=identity_ok, grant=grant)
    return GateAssessment(checks=domain_checks, policy_ref=compiled.constitution_hash,
                          policy_verdict=decision.verdict.value, missing=tuple(decision.missing))


class CortexProposer:
    """Attach explicitly to StandingCognitionRuntime's existing proposer slot."""
    def __init__(self, cortex, gate_evaluator, name="polyintelligence_seed"):
        if not callable(gate_evaluator):
            raise ContractError("host-owned gate evaluator required")
        self.cortex = cortex
        self.gate_evaluator = gate_evaluator
        self.name = name

    def __call__(self, signals, context):
        if not signals or "cognitive_request" not in context:
            return None
        request = CognitiveRequest.from_dict(context["cognitive_request"])
        receipt = self.cortex.think(request, gates=self.gate_evaluator(request))
        if receipt.disposition != "recommend":
            return None
        records = [r for r in self.cortex.ledger.by_type(self.cortex.RECEIPT_RECORD)
                   if r.payload.get("receipt", {}).get("receipt_id") == receipt.receipt_id]
        if len(records) != 1:
            raise ContractError("canonical cognitive receipt missing or ambiguous")
        record = records[0]
        return CandidateProposal.build(
            proposed_by=self.name, objective=request.question,
            action_class="draft.prepare", requested_capability="draft.prepare",
            target="internal://review/cognition", consequence_class="internal_write",
            payload={"cognitive_receipt_ref": record.hash, "result": receipt.result.to_dict()},
            evidence_refs=(*request.evidence_refs, record.hash), confidence=0.0, estimated_cost_usd=0.0,
            expected_outcome="a human reviews the receipted cognitive recommendation",
            source_signal_ids=tuple(signal.signal_id for signal in signals))
