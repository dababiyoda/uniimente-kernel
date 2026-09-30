"""Outcome hooks above canonical causal memory; proposed updates stay inert."""
from egregore.contracts import ContractError, canonical_copy, digest, require_hash
from memory.causal import CausalMemory
from copy import deepcopy


class RoutingMemory:
    def __init__(self, ledger):
        self.ledger = ledger
        self.causal_memory = CausalMemory(ledger)

    def propose_update(self, *, cognitive_receipt_ref, outcome_ref, contributions,
                       attribution_uncertainty, update_policy_version="seed-0.1"):
        with self.ledger._lock:
            return self._propose_update_locked(
                cognitive_receipt_ref=cognitive_receipt_ref, outcome_ref=outcome_ref,
                contributions=contributions, attribution_uncertainty=attribution_uncertainty,
                update_policy_version=update_policy_version)

    def _propose_update_locked(self, *, cognitive_receipt_ref, outcome_ref, contributions,
                              attribution_uncertainty, update_policy_version):
        """Require a canonical witnessed outcome and retain conditional credit.

        This is an evidence-qualified PROPOSAL. Canonical provenance links and
        externally_verified labels are retained assertions, not independent
        authentication or automatic evidence of factual correctness.
        """
        require_hash("cognitive_receipt_ref", cognitive_receipt_ref)
        require_hash("outcome_ref", outcome_ref)
        intact, reason = self.ledger.verify_chain()
        if not intact:
            raise ContractError(f"outcome history integrity failed: {reason}")
        cognitive = self.ledger.find(cognitive_receipt_ref)
        outcome = self.ledger.find(outcome_ref)
        if not cognitive or cognitive.record_type != "cognition.receipt":
            raise ContractError("canonical cognitive receipt required")
        if not outcome or outcome.record_type != "outcome":
            raise ContractError("canonical outcome required")
        if outcome.payload.get("validation_status") != "externally_verified":
            raise ContractError("outcome remains unresolved without external verification")
        if outcome.payload.get("result_class") not in ("positive", "negative"):
            raise ContractError("inconclusive outcomes cannot settle competence")
        if not isinstance(contributions, list) or not contributions:
            raise ContractError("explicit contribution attribution required")
        if not isinstance(attribution_uncertainty, str) or not attribution_uncertainty.strip():
            raise ContractError("attribution uncertainty required")
        action_ref = outcome.payload.get("action_ref")
        actions = [r for r in self.ledger.by_type("receipt") if r.payload.get("action_id") == action_ref]
        if len(actions) != 1:
            raise ContractError("outcome must link to one canonical consequence receipt")
        action = actions[0]
        witnesses = [r for r in self.ledger.by_type("witness")
                     if r.payload.get("witness_id") == action.payload.get("witness_id")]
        if len(witnesses) != 1:
            raise ContractError("canonical witness missing or ambiguous")
        witness = witnesses[0]
        if cognitive_receipt_ref not in witness.payload.get("evidence_refs", []):
            raise ContractError("witness does not attribute this cognition")
        if not cognitive.seq < witness.seq < action.seq < outcome.seq:
            raise ContractError("causal history order invalid")
        receipt = cognitive.payload["receipt"]
        if (not isinstance(receipt.get("selected_method"), str)
                or not receipt.get("method_version")
                or receipt.get("disposition") not in ("recommend", "test", "handoff")
                or not receipt.get("verification", {}).get("accepted")):
            raise ContractError("verified concrete method receipt required; abstention quality is separate")
        for item in contributions:
            if (not isinstance(item, dict) or not item.get("method") or not item.get("role")
                    or not item.get("evidence_refs")):
                raise ContractError("each contribution needs method, role and evidence")
            supported_methods = set()
            for ref in item["evidence_refs"]:
                require_hash("contribution evidence", ref)
                evidence = self.ledger.find(ref)
                if not evidence:
                    raise ContractError("contribution evidence missing")
                if evidence.record_type == "cognition.receipt":
                    cited = evidence.payload.get("receipt", {})
                    if cited.get("selected_method"):
                        supported_methods.add(cited["selected_method"])
                    if cited.get("verification", {}).get("accepted"):
                        supported_methods.update(("adversarial_verifier", "geometry_router"))
            if item["method"] not in supported_methods:
                raise ContractError("contribution method not supported by cited cognitive artifacts")
        observation_id = digest({"receipt": cognitive_receipt_ref, "outcome": outcome_ref})
        key = digest({"receipt": cognitive_receipt_ref, "outcome": outcome_ref,
                      "policy": update_policy_version, "contributions": contributions,
                      "uncertainty": attribution_uncertainty})
        for record in self.ledger.by_type("cognition.routing_update_proposed"):
            if record.payload["update_id"] == key:
                return deepcopy(record)
            if record.payload["observation_id"] == observation_id:
                revisions = self.ledger.by_type("cognition.routing_attribution_revision")
                for revision in revisions:
                    if revision.payload["update_id"] == key:
                        return deepcopy(revision)
                return self.ledger.append("cognition.routing_attribution_revision", {
                    "update_id": key, "observation_id": observation_id,
                    "supersedes_attribution_ref": record.hash,
                    "contributions": canonical_copy(contributions),
                    "attribution_uncertainty": attribution_uncertainty,
                    "update_policy_version": update_policy_version,
                    "additional_observations": 0, "applied": False, "authority_created": False})
        previous = len([r for r in self.ledger.by_type("cognition.routing_update_proposed")
                        if r.payload["geometry"] == receipt["geometry"]
                        and r.payload["method"] == receipt["selected_method"]])
        # A bounded candidate change, never applied by this hook.
        change = 0.05 if outcome.payload["result_class"] == "positive" else -0.05
        return self.ledger.append("cognition.routing_update_proposed", {
            "update_id": key, "observation_id": observation_id, "cognitive_receipt_ref": cognitive_receipt_ref,
            "outcome_ref": outcome_ref, "canonical_receipt_ref": action.hash,
            "canonical_witness_ref": witness.hash, "geometry": receipt["geometry"],
            "method": receipt["selected_method"], "method_version": receipt["method_version"],
            "contributions": canonical_copy(contributions), "attribution_uncertainty": attribution_uncertainty,
            "prior_observation_count": previous, "proposed_weight_delta": change,
            "update_policy_version": update_policy_version, "rollback_ref": cognitive_receipt_ref,
            "applied": False, "authority_created": False,
            "verification_scope": "recorded_canonical_links; external-verification assertion retained",
            "causal_precedents": self.causal_memory.precedents(witness.payload["action_class"]),
        })
