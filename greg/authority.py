"""Authority office: founder-signed light cone -> single-action Kernel grant -> Gate.

This is not a second authority plane. It holds no policy of its own beyond the
containment rule; it composes the canonical owners:

    founder-signed MISSION (light cone)            root of delegated scope
      -> LightCone.admits(...)                     is the action inside the cone?
      -> policy.engine.evaluate(...)               does the Constitution allow it?
      -> founder DECISION (only if REQUIRE_HUMAN)  exact-scope human approval
      -> GrantIssuer.issue_single_action(...)      Kernel grant bound to one effect
      -> ConsequenceGate.run(...)                  witness, commit-time revalidation,
                                                   dispatch claim, receipt, outcome

A worker receives a fresh short-lived machine passport scoped to one capability
(its own small light cone). Consequence class always comes from the capability
manifest, never from the caller, so a mislabelled action cannot pass as harmless.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from greg.capabilities import CapabilityError, CapabilityManifest, InvocationContext
from greg.lightcone import LightCone
from policy.consequence_gate import ConsequenceGate, GrantIssuer
from policy.engine import Proposal, Verdict, evaluate
from provenance.ledger import sha256_json

PRINCIPAL = "alfonso_lopez"


@dataclass
class ActionOutcome:
    status: str          # DONE | NEEDS_DECISION | OUTSIDE_SCOPE | REFUSED | UNCERTAIN | UNAVAILABLE
    reasons: list
    proposal_id: str
    scope_digest: str
    output: dict | None = None
    receipt_hash: str | None = None
    grant_id: str | None = None
    cost_usd: float = 0.0


class AuthorityOffice:
    def __init__(self, *, compiled, passports, signer, ledger, grants: GrantIssuer | None = None):
        self.compiled, self.passports, self.signer, self.ledger = compiled, passports, signer, ledger
        self.grants = grants or GrantIssuer()
        self.gate = ConsequenceGate(compiled=compiled, passports=passports, grants=self.grants,
                                    signer=signer, ledger=ledger)

    @staticmethod
    def scope_digest(*, mission_id: str, capability_id: str, params: dict, target: str,
                     consequence_class: str, cost_usd: float) -> str:
        return sha256_json({"mission_id": mission_id, "capability": capability_id, "params": params,
                            "target": target, "consequence_class": consequence_class, "cost_usd": cost_usd})

    def _prior(self, proposal_id: str):
        """Retained dispatch/receipt for this exact proposal, if any (crash recovery)."""
        claims = [r for r in self.ledger.by_type("grant_dispatch") if r.payload.get("proposal_id") == proposal_id]
        if not claims:
            return None, None
        receipts = [r for r in self.ledger.by_type("receipt")
                    if r.payload.get("grant_id") == claims[-1].payload.get("grant_id")]
        return claims[-1], (receipts[-1] if receipts else None)

    def act(self, *, mission_id: str, cone: LightCone, command_digest: str, manifest: CapabilityManifest,
            adapter, ctx: InvocationContext, params: dict, target: str, cost_usd: float,
            expected_outcome: str, evidence_refs: list, attempt, spent_usd: float,
            approved_scopes: set, evidence_confidence: float = 1.0) -> ActionOutcome:
        consequence = manifest.consequence_class
        scope = self.scope_digest(mission_id=mission_id, capability_id=manifest.capability_id, params=params,
                                  target=target, consequence_class=consequence, cost_usd=cost_usd)
        proposal_id = "greg-" + sha256_json({"scope": scope, "attempt": attempt})[7:39]
        base = dict(proposal_id=proposal_id, scope_digest=scope)

        ok, why = manifest.available()
        if not ok:
            return ActionOutcome("UNAVAILABLE", [why], **base)
        if not target.startswith(manifest.target_prefix):
            return ActionOutcome("REFUSED", [f"target {target!r} outside capability prefix "
                                             f"{manifest.target_prefix!r}"], **base)
        outside = cone.admits(capability=manifest.capability_id, target=target, consequence_class=consequence,
                              cost_usd=cost_usd, spent_usd=spent_usd)
        if outside and scope not in approved_scopes:
            return ActionOutcome("OUTSIDE_SCOPE", outside, **base)

        claim, receipt = self._prior(proposal_id)
        if receipt is not None:  # already done before an interruption: reuse, never redo
            return ActionOutcome("DONE", ["retained receipt reused after restart"], output=receipt.payload["result"].get("output"),
                                 receipt_hash=receipt.hash, grant_id=receipt.payload.get("grant_id"),
                                 cost_usd=cost_usd, **base)
        if claim is not None:
            return ActionOutcome("UNCERTAIN", ["dispatch claimed without receipt; outcome unknown"], **base)

        worker = self.passports.issue(kind="agent", creator="greg-authority-office", owner_organ="uniimente-kernel",
                                      legal_principal=PRINCIPAL, declared_capabilities=[manifest.capability_id],
                                      budget_ceiling_usd=cost_usd, consequence_class=consequence, ttl_seconds=900)
        proposal = Proposal(actor=worker.passport_id, legal_principal=PRINCIPAL,
                            action_class="greg." + manifest.capability_id, objective=mission_id,
                            payload={"capability": manifest.capability_id, "params": params,
                                     "manifest_digest": manifest.digest()},
                            target=target, consequence_class=consequence,
                            evidence_confidence=evidence_confidence,
                            evidence_refs=[command_digest, *evidence_refs], estimated_cost_usd=cost_usd,
                            requested_capability=manifest.capability_id, expected_outcome=expected_outcome,
                            context={"mission_id": mission_id, "scope_digest": scope,
                                     "authority_ref": command_digest}, proposal_id=proposal_id)
        grant = self.grants.issue_single_action(proposal=proposal,
                                                policy_version=self.compiled.constitution_version)
        # Policy sees the real in-cone grant (budget authorization included). A grant
        # that policy denies, or that still needs a human, is revoked unused.
        decision = evaluate(self.compiled, proposal, identity_ok=True, grant=self.gate._eval_view(grant))
        if decision.verdict == Verdict.DENY or (decision.verdict == Verdict.REQUIRE_HUMAN
                                                and scope not in approved_scopes):
            self.grants.revoke(grant["grant_id"], reason="pre-dispatch policy verdict " + decision.verdict.value,
                               revoker="greg-authority-office")
            self.ledger.append("event", {"type": "greg.authority.grant_revoked_unused", "grant_id": grant["grant_id"],
                                         "proposal_id": proposal_id, "verdict": decision.verdict.value,
                                         "reasons": decision.reasons})
            status = "REFUSED" if decision.verdict == Verdict.DENY else "NEEDS_DECISION"
            return ActionOutcome(status, decision.reasons, **base)
        self.ledger.append("event", {"type": "greg.authority.grant_issued", "grant_id": grant["grant_id"],
                                     "proposal_id": proposal_id, "scope_digest": scope,
                                     "authority_ref": command_digest, "cone": cone.to_dict(),
                                     "founder_approved_scope": scope in approved_scopes})

        def execute(p):
            try:
                output = adapter(params, ctx)
            except CapabilityError as exc:
                return {"observed_outcome": "capability refused: " + str(exc)[:300], "result_class": "negative",
                        "output": None, "validation_status": "self_reported"}
            return {"observed_outcome": expected_outcome, "result_class": "positive",
                    "output": bounded(output), "validation_status": "self_reported"}

        def approver(p, reasons):
            return (scope in approved_scopes, "founder-signed decision for exact scope"
                    if scope in approved_scopes else "no founder decision")

        record = self.gate.run(proposal, executor=execute, approver=approver, standing_grant=grant)
        if record.state == "recorded":
            receipt = self.ledger.find(record.receipt_hash)
            result = receipt.payload["result"]
            if result.get("result_class") != "positive":
                return ActionOutcome("REFUSED", [result.get("observed_outcome", "capability failed")],
                                     receipt_hash=record.receipt_hash, grant_id=grant["grant_id"], **base)
            return ActionOutcome("DONE", [], output=result.get("output"), receipt_hash=record.receipt_hash,
                                 grant_id=grant["grant_id"], cost_usd=cost_usd, **base)
        if record.state == "reconciliation_required":
            return ActionOutcome("UNCERTAIN", record.refusal_reasons, grant_id=grant["grant_id"], **base)
        return ActionOutcome("REFUSED", record.refusal_reasons or [record.state], grant_id=grant["grant_id"], **base)


RECEIPT_TEXT_LIMIT = 16 * 1024


def bounded(value):
    """Receipts keep evidence, not bulk: long strings keep a prefix plus their digest."""
    import hashlib
    if isinstance(value, str) and len(value) > RECEIPT_TEXT_LIMIT:
        return {"prefix": value[:RECEIPT_TEXT_LIMIT], "truncated": True,
                "sha256": hashlib.sha256(value.encode()).hexdigest(), "length": len(value)}
    if isinstance(value, dict):
        return {k: bounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [bounded(v) for v in value[:1000]]
    return value


def now() -> datetime:
    return datetime.now(timezone.utc)
