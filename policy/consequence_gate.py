"""Consequence Gate: the ONE boundary through which every external effect passes.

Layer 3 of the stack. The exact pipeline (doctrine):

    Proposal -> identity -> legal principal -> evidence -> policy
    -> approval -> budget reservation -> capability -> Commit Witness
    -> commit-time revalidation -> execution -> receipt -> postcondition
    -> reconciliation -> outcome

Lifecycle states (workflows/approval-lifecycle.yaml):
    proposed, evaluating, pending_human, granted, executing, committed,
    recorded | refused, denied, expired, revoked, failed

Hard rules:
    expired approval at commit     -> fail closed and re-request
    revoked grant at commit        -> fail closed
    stale evidence at commit       -> fail closed and refresh
    effect mismatch at commit      -> hard refusal and incident
    missing outcome record         -> blocks autonomy promotion
    any failure                    -> fails toward silence, never toward
                                      uncontrolled external action

The gate never performs I/O itself. Execution happens through an injected
executor callable; approval through an injected approver callable. Models
recommend. This code authorizes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Callable, Any

from compiler.ucl_compiler import CompiledConstitution
from identity.machine_passport import PassportRegistry
from policy.engine import CONTAINED_CLASSES, Proposal, Verdict, evaluate
from provenance.ledger import EvidenceLedger
from provenance.commit_witness import WitnessSigner, new_witness, sha256_obj
from provenance.witness_v2 import WITNESS_CONTRACT_VERSION

TERMINAL_STATES = {"recorded", "refused", "denied", "expired", "revoked", "failed"}
APPROVAL_TTL = timedelta(hours=72)          # pending_human expires after 72 hours
GRANT_TTL = timedelta(minutes=15)           # single-action grants are short-lived


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rfc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class ActionRecord:
    """The verifiable institutional action record: what the constitution
    requires every consequential action to leave behind."""
    action_id: str
    proposal_id: str
    state: str
    trajectory: list[dict] = field(default_factory=list)
    witness_id: str | None = None
    grant_id: str | None = None
    receipt_hash: str | None = None
    outcome: dict | None = None
    refusal_reasons: list[str] = field(default_factory=list)
    incident: str | None = None


class BudgetOffice:
    """Budget reservations. Bounded authority over money: reservations are
    explicit, per-grant, and released on any failure path."""

    def __init__(self):
        self._reservations: dict[str, dict] = {}

    def reserve(self, grant_id: str, amount: float, limit: float) -> dict:
        if amount > limit:
            raise ValueError(f"budget overflow: {amount} > limit {limit}")
        rid = str(uuid.uuid4())
        self._reservations[rid] = {"reservation_id": rid, "grant_id": grant_id,
                                   "amount": float(amount), "state": "reserved"}
        return self._reservations[rid]

    def commit(self, reservation_id: str) -> None:
        self._reservations[reservation_id]["state"] = "committed"

    def release(self, reservation_id: str) -> None:
        if reservation_id in self._reservations:
            self._reservations[reservation_id]["state"] = "released"

    def state(self, reservation_id: str) -> str:
        return self._reservations[reservation_id]["state"]


class GrantIssuer:
    """Issues single-action capability grants per the grant contract.
    New grants start at simulate/shadow; an executable single-action grant
    is issued only after policy ALLOW (and human approval where required),
    is bound to one exact effect hash, and expires in minutes.

    The issued grant validates exactly against contracts/capability-grant.
    Gate-internal metadata (stage, single-use, effect binding) lives in a
    separate internal record keyed by grant_id; the wire contract is never
    patched silently.
    """

    def __init__(self, issuer_id: str = "spiffe://uniimente.internal/kernel/action-gateway"):
        self.issuer_id = issuer_id
        self._grants: dict[str, dict] = {}       # contract-valid grants
        self._meta: dict[str, dict] = {}         # gate-internal metadata

    def issue_single_action(self, *, proposal: Proposal, policy_version: str) -> dict:
        now = _now()
        grant = {
            "grant_id": str(uuid.uuid4()),
            "grantee": proposal.actor,
            "granted_by": self.issuer_id,
            "legal_actor": proposal.legal_principal,
            "venture_cell": proposal.context.get("venture_cell"),
            "objective": proposal.objective,
            "permitted_actions": [proposal.requested_capability],
            "accounts": [],
            "counterparties": [proposal.target],
            "data_boundaries": [],
            "spending_limit_usd": float(proposal.estimated_cost_usd),
            "rate_limits": None,
            "prohibited": [],
            "initial_stage": "simulate",           # lineage: starts non-executable
            "parent_grant": proposal.context.get("parent_grant"),
            "issued_at": _rfc(now),
            "expires_at": _rfc(now + GRANT_TTL),
            "escalation_triggers": [],
            "revocable_by": ["spiffe://uniimente.internal/kernel/action-gateway"],
            "revoked": False,
            "revoked_at": None,
            "revocation_reason": None,
        }
        self._grants[grant["grant_id"]] = grant
        self._meta[grant["grant_id"]] = {
            "stage": "execute_once",               # promoted by policy decision, recorded
            "stage_promotion_evidence": policy_version,
            "single_use": True,
            "used": False,
            "bound_effect_hash": sha256_obj({"payload": proposal.payload, "target": proposal.target,
                                             "action_class": proposal.action_class}),
        }
        return grant

    def get(self, grant_id: str) -> dict | None:
        return self._grants.get(grant_id)

    def get_meta(self, grant_id: str) -> dict:
        return self._meta.get(grant_id, {})

    def revoke(self, grant_id: str, *, reason: str, revoker: str) -> None:
        g = self._grants.get(grant_id)
        if g and not g["revoked"]:
            g["revoked"] = True
            g["revoked_at"] = _rfc(_now())
            g["revocation_reason"] = f"{reason} (by {revoker})"

    def mark_used(self, grant_id: str) -> None:
        if grant_id in self._meta:
            self._meta[grant_id]["used"] = True


class ConsequenceGate:
    """The sole path to external effects."""

    def __init__(self, *, compiled: CompiledConstitution, passports: PassportRegistry,
                 ledger: EvidenceLedger, signer: WitnessSigner,
                 grants: GrantIssuer | None = None, budget: BudgetOffice | None = None,
                 policy_version: str = "1.0.0",
                 evidence_thresholds: dict | None = None):
        self.compiled = compiled
        self.passports = passports
        self.ledger = ledger
        self.signer = signer
        self.grants = grants or GrantIssuer()
        self.budget = budget or BudgetOffice()
        self.policy_version = policy_version
        self.evidence_thresholds = evidence_thresholds

    # -- internal helpers -------------------------------------------------
    def _transition(self, rec: ActionRecord, state: str, detail: dict | None = None) -> None:
        rec.state = state
        entry = {"state": state, "ts": _rfc(_now()), **(detail or {})}
        rec.trajectory.append(entry)
        self.ledger.append("event", {"type": f"action.{state}", "action_id": rec.action_id,
                                     "proposal_id": rec.proposal_id, **(detail or {})})

    def _refuse(self, rec: ActionRecord, state: str, reasons: list[str]) -> ActionRecord:
        rec.refusal_reasons = reasons
        self._transition(rec, state, {"reasons": reasons})
        return rec

    def _eval_view(self, grant: dict) -> dict:
        """Runtime evaluation view: wire contract + gate-managed stage metadata."""
        view = dict(grant)
        meta = self.grants.get_meta(grant["grant_id"])
        if meta.get("stage"):
            view["stage"] = meta["stage"]
        return view

    # -- the pipeline -----------------------------------------------------
    def run(self, proposal: Proposal, *,
            executor: Callable[[Proposal], dict],
            approver: Callable[[Proposal, list[str]], tuple[bool, str]] | None = None,
            standing_grant: dict | None = None) -> ActionRecord:
        rec = ActionRecord(action_id=str(uuid.uuid4()), proposal_id=proposal.proposal_id, state="proposed")
        self._transition(rec, "proposed", {"actor": proposal.actor, "action_class": proposal.action_class})

        # 1-2. identity --------------------------------------------------
        self._transition(rec, "evaluating", {"step": "identity"})
        ok, why = self.passports.verify(proposal.actor)
        if not ok:
            return self._refuse(rec, "refused", [f"identity: {why}"])

        # 3-5. legal principal + evidence + policy -----------------------
        eval_grant = self._eval_view(standing_grant) if standing_grant else None
        decision = evaluate(self.compiled, proposal, identity_ok=ok, grant=eval_grant, thresholds=self.evidence_thresholds)
        if decision.verdict == Verdict.DENY:
            return self._refuse(rec, "refused", decision.reasons)

        # 6. approval ------------------------------------------------------
        if decision.verdict == Verdict.REQUIRE_HUMAN:
            self._transition(rec, "pending_human", {"reasons": decision.reasons})
            if approver is None:
                return self._refuse(rec, "expired", ["pending_human: no approver available; 72h TTL applies"])
            approved, why = approver(proposal, decision.reasons)
            if not approved:
                return self._refuse(rec, "denied", [f"human decision: {why}"])
            self._transition(rec, "evaluating", {"step": "policy_recheck_after_approval"})
            decision = evaluate(self.compiled, proposal, identity_ok=True, grant=eval_grant, thresholds=self.evidence_thresholds)
            if decision.verdict == Verdict.DENY:
                return self._refuse(rec, "refused", decision.reasons)

        # 7. capability ----------------------------------------------------
        # An action that reaches outside may not be granted by the same run
        # that proposes it. Self-issuance is fine for internal effects and is
        # authority creation for external ones — "no component may authorize
        # its own promotion or expand its own sovereignty".
        #
        # Found 2026-08-23 while discharging CONTRADICTION-0003 Option B, and
        # found only because that remedy removed what was hiding it: the
        # evidence floor had been refusing these proposals earlier in the
        # pipeline, so no external_contact run had ever reached this line
        # without a supplied grant. A floor was doing an authorization check's
        # job, and the two failures looked identical from outside.
        #
        # `authorized` is one of the seven properties the founder's ruling
        # named. This is where it is enforced.
        if standing_grant is None and \
                proposal.consequence_class in CONTAINED_CLASSES:
            return self._refuse(rec, "refused", [
                f"{proposal.consequence_class} requires a grant issued outside "
                "this run; the Gate does not issue its own authority to act "
                "externally"])
        grant = standing_grant or self.grants.issue_single_action(
            proposal=proposal, policy_version=self.policy_version)
        rec.grant_id = grant["grant_id"]
        self._transition(rec, "granted", {"grant_id": grant["grant_id"]})

        # 8. budget reservation ---------------------------------------------
        try:
            reservation = self.budget.reserve(grant["grant_id"], proposal.estimated_cost_usd,
                                              float(grant.get("spending_limit_usd", 0)))
        except ValueError as e:
            return self._refuse(rec, "refused", [f"budget: {e}"])

        # 9. Commit Witness ---------------------------------------------------
        # Emits Witness contract v2, authorised by FOUNDER-RULING-2026-08-23.
        #
        # The gap this closes was never that the values were unavailable: the
        # Proposal has carried `consequence_class` and `evidence_confidence`
        # all along, and the grant states the ceiling at the moment budget is
        # reserved. The gate held all of them and dropped them, so the durable
        # record could not answer "what did we believe, how strongly, under
        # exactly what authority, and what exposure was permitted".
        #
        # `predicted_success_probability` rides along unchanged from the
        # proposal, including when it is None. None means the action
        # preregistered no forecast, the field is dropped from the signed
        # payload, and the record reads back as UNRECORDED rather than as a
        # prediction of zero.
        witness = new_witness(
            actor=proposal.actor, legal_principal=proposal.legal_principal,
            action_class=proposal.action_class, payload=proposal.payload, target=proposal.target,
            policy_version=self.policy_version, constitution_hash=self.compiled.constitution_hash,
            grant_id=grant["grant_id"], capability=proposal.requested_capability,
            budget_reservation_id=reservation["reservation_id"],
            expected_outcome=proposal.expected_outcome, evidence_refs=proposal.evidence_refs,
            witness_version=WITNESS_CONTRACT_VERSION,
            evidence_confidence=proposal.evidence_confidence,
            consequence_class=proposal.consequence_class,
            exposure_ceiling_usd=float(grant.get("spending_limit_usd", 0)),
            predicted_success_probability=proposal.predicted_success_probability)
        self.signer.sign(witness)
        rec.witness_id = witness.witness_id
        self.ledger.append("witness", asdict(witness))

        # 10. commit-time revalidation ---------------------------------------
        problem = self._reauthorize_at_commit(proposal, grant, witness)
        if problem is not None:
            self.budget.release(reservation["reservation_id"])
            state, reasons = problem
            if state == "refused" and any("mismatch" in r for r in reasons):
                rec.incident = "effect_mismatch_at_commit"
                self.ledger.append("event", {"type": "incident.effect_mismatch",
                                             "action_id": rec.action_id, "reasons": reasons})
            return self._refuse(rec, state, reasons)

        # 11. execution --------------------------------------------------------
        self._transition(rec, "executing", {"witness_id": witness.witness_id})
        try:
            result = executor(proposal)
        except Exception as e:  # fail toward silence + preservation
            self.budget.release(reservation["reservation_id"])
            rec.incident = f"executor_exception:{type(e).__name__}"
            return self._refuse(rec, "failed", [f"executor raised {type(e).__name__}: {e}"])
        self.budget.commit(reservation["reservation_id"])
        if self.grants.get_meta(grant["grant_id"]).get("single_use"):
            self.grants.mark_used(grant["grant_id"])
        self._transition(rec, "committed", {"result_summary": str(result)[:200]})

        # 12. receipt -----------------------------------------------------------
        receipt = self.ledger.append("receipt", {
            "action_id": rec.action_id, "witness_id": witness.witness_id,
            "grant_id": grant["grant_id"], "result": result,
            "proof": "this exact machine, acting for this exact entity, received this exact "
                     "permission, under this exact law, using this exact evidence, to create "
                     "this exact result",
        })
        rec.receipt_hash = receipt.hash

        # 13. postcondition + 14. reconciliation -------------------------------
        observed = result.get("observed_outcome", "unreported")
        reconciled = observed == proposal.expected_outcome
        outcome = {
            "outcome_id": str(uuid.uuid4()),
            "action_ref": rec.action_id,
            "recorded_at": _rfc(_now()),
            "recorded_by": proposal.actor,
            "external_observation": observed,
            "result_class": result.get("result_class", "inconclusive"),
            "expected_vs_actual": f"expected={proposal.expected_outcome!r} actual={observed!r} "
                                  f"reconciled={reconciled}",
            "metrics": result.get("metrics"),
            "evidence_refs": proposal.evidence_refs,
            "learning": result.get("learning"),
            "validation_status": result.get("validation_status", "internally_observed"),
            "feeds": ["causal_memory", "calibration"],
        }
        self.ledger.append("outcome", outcome)
        rec.outcome = outcome
        self._transition(rec, "recorded", {"outcome_id": outcome["outcome_id"],
                                           "reconciled": reconciled})
        return rec

    def _reauthorize_at_commit(self, proposal: Proposal, grant: dict, witness) -> tuple[str, list[str]] | None:
        """Authority is ALWAYS revalidated at the durability boundary."""
        reasons: list[str] = []
        # witness signature must verify
        if not self.signer.verify(witness):
            reasons.append("witness signature invalid")
        # grant must still be valid, fresh, unrevoked, unused, and bound to this effect
        managed = self.grants.get(grant["grant_id"])
        g = managed or grant
        meta = self.grants.get_meta(g["grant_id"])
        if g.get("revoked"):
            reasons.append("revoked grant at commit")
        if meta.get("single_use") and meta.get("used"):
            reasons.append("single-use grant already consumed")
        if _now() >= datetime.fromisoformat(g["expires_at"].replace("Z", "+00:00")):
            reasons.append("expired grant at commit")
        bound = meta.get("bound_effect_hash")
        if bound and bound != sha256_obj(
                {"payload": proposal.payload, "target": proposal.target,
                 "action_class": proposal.action_class}):
            reasons.append("effect mismatch at commit: payload/target diverged from authorized effect")
        # identity must still be valid
        ok, why = self.passports.verify(proposal.actor)
        if not ok:
            reasons.append(f"identity lapsed before commit: {why}")
        # policy must still allow, with the identical input. The evaluation view
        # merges the wire contract with gate-managed stage metadata (the contract
        # records initial_stage; the runtime stage is promoted by the decision).
        decision = evaluate(self.compiled, proposal, identity_ok=True, grant=self._eval_view(g), thresholds=self.evidence_thresholds)
        if decision.verdict == Verdict.DENY:
            reasons.extend(f"commit-time policy refusal: {r}" for r in decision.reasons)
        if reasons:
            state = "revoked" if any("revoked" in r for r in reasons) else "refused"
            return state, reasons
        return None
