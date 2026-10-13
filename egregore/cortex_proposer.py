"""Seed Cortex → standing cognition: a consequence-inert proposer.

The Polyintelligence Cortex seed (``cortex/``) classifies a problem's geometry,
recruits an eligible organ, verifies the result and returns a receipt. On its
own it is a library. This module attaches it to the one place on main where
GREG already deliberates, ``StandingCognitionRuntime``'s existing proposer slot,
without adding a second runtime, gate or authority path.

Mechanism recombined from PR #139 (``egregore/cognition/integration.py``,
``CortexProposer``): bind explicitly to the runtime's proposer mapping; ledger
the receipt first; return a candidate only when the cortex recommends or asks
for human adjudication; cite the ledger record as evidence.

What this binding does and does not do:

* every call that reaches the cortex writes exactly one ``cortex.receipt``
  record to the evidence ledger, whatever the disposition (abstentions are
  traces too); a malformed request is refused before the cortex runs and the
  runtime records that refusal as this proposer's failure;
* authority records reach the cortex only through the constructor-time
  ``records_provider``; a request carrying ``authority_records`` in tick
  context is refused, because context is unauthenticated text;
* the runtime requires ``candidate.proposed_by`` to equal the mapping key it was
  registered under: register it as ``proposer.as_organ()``;
* ``recommend`` becomes a ``draft.prepare`` candidate at ``internal_write`` whose
  only effect is a human review of the receipt;
* ``handoff`` becomes a ``human.adjudicate`` candidate at ``internal_write``:
  the question is routed to legitimate human judgment, nothing is decided;
* ``abstain`` and ``bounded_test`` produce no candidate (the receipt names the
  missing information or the premise to test);
* the semantic organ gets at most the model calls this proposer was configured
  with (default 0), so the runtime's resource accounting stays truthful;
* the cortex never sees the Consequence Gate, grants or adapters, and the
  candidate's ``execution_authority`` is ``"none"`` by contract;
* a receipt is accepted only if it validates against its contract, matches its
  own content address, claims no authority and spent nothing beyond the
  proposer's ceiling (guard recombined from PR #143's bridge).

Competence estimates live in ``cortex.memory.CompetenceLedger`` and settle only
on verified outcomes; a candidate's ``confidence`` is 0.0 until that exists.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from egregore.contracts import CandidateProposal, ContractError, SignalEnvelope, canonical_copy

RECEIPT_RECORD = "cortex.receipt"
REQUEST_KEY = "cognitive_request"
CANDIDATE_DISPOSITIONS = {
    "recommend": ("draft.prepare", "draft.prepare", "internal://review/cognition",
                  "a human reviews the receipted cognitive recommendation"),
    "handoff": ("human.adjudicate", "human.adjudicate", "internal://founder/attention",
                "legitimate human judgment decides; the receipt carries the question and its evidence"),
}


class CortexProposer:
    """Attach the Seed Cortex to ``StandingCognitionRuntime(proposers={name: proposer})``."""

    def __init__(self, cortex: Any, ledger: Any, *, name: str = "seed_cortex", max_model_calls: int = 0,
                 max_receipt_usd: float = 0.0,
                 records_provider: Callable[[Mapping[str, Any]], Sequence[Mapping[str, Any]]] | None = None):
        if not hasattr(cortex, "run"):
            raise ContractError("cortex must expose run(problem, records=...)")
        if not hasattr(ledger, "append") or not hasattr(ledger, "by_type"):
            raise ContractError("ledger must provide append() and by_type()")
        if not isinstance(name, str) or not name.strip():
            raise ContractError("proposer name required")
        if not isinstance(max_model_calls, int) or isinstance(max_model_calls, bool) or max_model_calls < 0:
            raise ContractError("max_model_calls must be a non-negative integer")
        if isinstance(max_receipt_usd, bool) or not isinstance(max_receipt_usd, (int, float)) or max_receipt_usd < 0:
            raise ContractError("max_receipt_usd must be a non-negative number")
        self.cortex = cortex
        self.ledger = ledger
        self.name = name
        self.max_model_calls = max_model_calls
        self.max_receipt_usd = float(max_receipt_usd)
        self.records_provider = records_provider

    @property
    def execution_authority(self) -> str:
        return "none"

    def as_organ(self) -> dict:
        """The mapping to pass as ``StandingCognitionRuntime(proposers=...)``: the key must equal ``name``."""
        return {self.name: self}

    # ------------------------------------------------------------------ proposer protocol
    def __call__(self, signals: Sequence[SignalEnvelope], context: Mapping[str, Any]):
        if not signals:
            return None
        request = context.get(REQUEST_KEY) if isinstance(context, Mapping) else None
        if not isinstance(request, Mapping):
            return None
        problem = request.get("problem")
        if not isinstance(problem, Mapping):
            raise ContractError("cognitive_request.problem must be a mapping")
        if "authority_records" in request:
            # Authority records travel only through the trusted constructor-time provider. A record that
            # arrives in tick context is unauthenticated text and could flip a gate on the ledgered receipt.
            raise ContractError("authority records are not accepted from tick context; supply a records_provider")
        problem = self._bounded_problem(problem)
        records = list(self.records_provider(request)) if self.records_provider is not None else []
        receipt = self._checked(self.cortex.run(problem, records=records or None))
        record = self.ledger.append(RECEIPT_RECORD, {
            "proposer": self.name, "receipt": receipt, "execution_authority": "none",
            "source_signal_ids": [s.signal_id for s in signals],
        })
        kind = receipt["disposition"]["kind"]
        if kind not in CANDIDATE_DISPOSITIONS:
            return None
        action_class, capability, target, expected = CANDIDATE_DISPOSITIONS[kind]
        objective = str(problem.get("question") or "").strip() or f"cognition receipt {receipt['receipt_id']}"
        geometry = receipt.get("geometry") or {}
        return CandidateProposal.build(
            proposed_by=self.name,
            objective=objective,
            action_class=action_class,
            requested_capability=capability,
            target=target,
            consequence_class="internal_write",
            payload={
                "cortex_receipt_ref": record.hash,
                "receipt_id": receipt["receipt_id"],
                "disposition": receipt["disposition"],
                "epistemic_class": geometry.get("epistemic_class"),
                "selected_routes": list((receipt.get("route") or {}).get("selected") or []),
                "state": receipt["output"]["state"],
                "answer": receipt["output"]["answer"],
                "authority_created": False,
            },
            evidence_refs=(f"ledger:{record.hash}", *self._receipt_refs(receipt)),
            confidence=0.0,
            estimated_cost_usd=float(receipt["expenditure"]["usd"]),
            expected_outcome=expected,
            source_signal_ids=tuple(s.signal_id for s in signals),
        )

    # ------------------------------------------------------------------ helpers
    def _checked(self, receipt: Mapping[str, Any]) -> dict:
        """Accept a receipt only if it satisfies its contract and its own content address, claims no
        authority, and spent nothing beyond the proposer's ceiling (mechanism from PR #143's bridge
        ``check_receipt``). A receipt that fails is never ledgered as a receipt; the runtime records
        the failure for this proposer and the other organs' trace is unaffected."""
        if not isinstance(receipt, Mapping):
            raise ContractError("cortex returned a non-mapping receipt")
        receipt = dict(receipt)
        if receipt.get("authority_created") is not False or receipt.get("execution_authority") != "none":
            raise ContractError("cortex receipt claims authority; refused")
        from cortex.contracts import digest as cortex_digest
        from cortex.schemas import validate as validate_cortex
        validate_cortex(receipt, "cortex-receipt")
        body = dict(receipt)
        identity = body.pop("receipt_id")
        if identity != cortex_digest(body):
            raise ContractError("cortex receipt content address mismatch; refused")
        usd = float((receipt.get("expenditure") or {}).get("usd", 0.0))
        if usd > self.max_receipt_usd:
            raise ContractError(f"cortex receipt spent {usd} USD; proposer ceiling is {self.max_receipt_usd}")
        return receipt

    def _bounded_problem(self, problem: Mapping[str, Any]) -> dict:
        """Clamp the semantic organ's model budget to what this proposer may spend."""
        problem = canonical_copy(dict(problem))
        payload = problem.get("payload") or {}
        if not isinstance(payload, Mapping):
            raise ContractError("problem.payload must be a mapping")
        payload = dict(payload)
        resources = payload.get("resources") or {}
        if not isinstance(resources, Mapping):
            raise ContractError("payload.resources must be a mapping")
        resources = dict(resources)
        requested = resources.get("max_model_calls", self.max_model_calls)
        if not isinstance(requested, int) or isinstance(requested, bool) or requested < 0:
            raise ContractError("resources.max_model_calls must be a non-negative integer")
        resources["max_model_calls"] = min(requested, self.max_model_calls)
        payload["resources"] = resources
        problem["payload"] = payload
        return problem

    @staticmethod
    def _receipt_refs(receipt: Mapping[str, Any]) -> list[str]:
        inputs = receipt.get("inputs") or {}
        return [ref for ref in (inputs.get("evidence_refs") or []) if isinstance(ref, str) and ref]

    def receipts(self) -> list:
        """Every receipt this proposer (by name) has ledgered, oldest first."""
        return [r for r in self.ledger.by_type(RECEIPT_RECORD) if r.payload.get("proposer") == self.name]
