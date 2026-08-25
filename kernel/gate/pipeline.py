"""The 15-step Consequence Gate pipeline.

Gate(policy_version, constitution_version, authority, spine).run(intent)
executes exactly:

    PROPOSE -> IDENTIFY -> CLASSIFY -> EVALUATE -> APPROVE -> RESERVE ->
    ISSUE -> WITNESS -> REAUTHORIZE -> EXECUTE -> RECEIPT -> VERIFY ->
    RECONCILE -> OUTCOME -> close DecisionEpisode

Hard rules enforced here:
1. The adapter is only ever invoked with the freshly signed CommitWitness.
2. Approvals/grants/witnesses all bind to the intent fingerprint; mutation
   invalidates them and is caught at REAUTHORIZE at the latest.
3. effect == REQUIRE_HUMAN blocks until a valid ApprovalRecord exists.
4. Every artifact is appended to the append-only spine; ANY failure raises
   GateRefusal, closes the episode with the reason, and records a
   GATE_REFUSAL event on the spine (best effort if the spine itself is lost).
5. All hashes are canonical-JSON sha256; the decision trace is deterministic.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping

from ..authority.approvals import ApprovalService
from ..contracts.action import (
    ActionIntent,
    ApprovalRecord,
    CapabilityGrant,
    PolicyDecision,
)
from ..contracts.execution import (
    CommitWitness,
    DecisionEpisode,
    ExecutionReceipt,
    OutcomeRecord,
    ReconciliationRecord,
)
from ..contracts.institutional import EvidencePacket, InstitutionalEvent
from ..crypto import keys as crypto_keys
from ..crypto.hashing import canonical_json, content_hash, sha256_hex
from . import errors
from .fingerprint import intent_fingerprint
from .revalidate import check_evidence_freshness, revalidate

CONSEQUENCE_CLASSES = ("C0", "C1", "C2", "C3", "C4", "C5")
BUDGET_KEYS = ("cpu_seconds", "memory_mb", "cost_usd")
DEFAULT_BUDGET_CAPS = {
    "per_intent": {"cpu_seconds": 600.0, "memory_mb": 8192.0, "cost_usd": 25.0},
    "window": {"cpu_seconds": 3600.0, "memory_mb": 32768.0, "cost_usd": 100.0},
}

# Excluded from adapter/authority signature bodies: base metadata + signature field.
_GRANT_UNSIGNED = {"schema_version", "id", "created_at", "signature"}
_WITNESS_UNSIGNED = {"schema_version", "id", "created_at", "witness_signature"}
_RECEIPT_UNSIGNED = {"schema_version", "id", "created_at", "signature"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def default_policy_evaluator(
    intent: ActionIntent,
    *,
    intent_fingerprint: str,
    policy_version: str,
    constitution_version: str,
    trace: list[str],
) -> PolicyDecision:
    """Default evaluator: C0/C1 PERMIT, C2 REQUIRE_HUMAN, C3+ DENY."""
    cls = intent.consequence_class
    if cls in ("C0", "C1"):
        effect = "PERMIT"
    elif cls == "C2":
        effect = "REQUIRE_HUMAN"
    else:
        effect = "DENY"
    decision_trace = [*trace, f"EVALUATE: default evaluator class={cls} effect={effect}"]
    return PolicyDecision(
        intent_fingerprint=intent_fingerprint,
        effect=effect,
        governing_clauses=[f"default-policy:{cls}:{effect}"],
        policy_version=policy_version,
        constitution_version=constitution_version,
        decision_trace=decision_trace,
    )


class GrantStore:
    """In-memory grant state; the durable spent marker lives on the spine."""

    def __init__(self) -> None:
        self._grants: dict[str, CapabilityGrant] = {}
        self._spent: set[str] = set()

    def add(self, grant: CapabilityGrant) -> None:
        self._grants[grant.grant_id] = grant

    def get(self, grant_id: str) -> CapabilityGrant | None:
        return self._grants.get(grant_id)

    def revoke(self, grant_id: str) -> None:
        grant = self._grants.get(grant_id)
        if grant is not None:
            self._grants[grant_id] = grant.model_copy(update={"revoked": True})

    def mark_spent(self, grant_id: str) -> None:
        self._spent.add(grant_id)

    def is_spent(self, grant_id: str) -> bool:
        return grant_id in self._spent


class BudgetLedger:
    """Cumulative budget guard — blocks split-budget evasion (Hard Rule 4).

    Per-intent caps stop a single oversized action; the cumulative per-window
    cap per legal_principal stops an attacker splitting one oversized action
    into several under-limit intents.
    """

    def __init__(self, caps: dict[str, dict[str, float]] | None = None):
        caps = caps or DEFAULT_BUDGET_CAPS
        self._per_intent = dict(caps.get("per_intent", {}))
        self._window = dict(caps.get("window", {}))
        self._reserved: dict[str, dict[str, float]] = {}

    def reserve(self, principal: str, budget: dict[str, float]) -> None:
        for key, amount in budget.items():
            cap = self._per_intent.get(key)
            if cap is not None and amount > cap:
                raise errors.BudgetRefusal(
                    f"budget {key}={amount} exceeds per-intent cap {cap}", stage="RESERVE"
                )
        totals = self._reserved.setdefault(principal, {k: 0.0 for k in BUDGET_KEYS})
        for key, amount in budget.items():
            cap = self._window.get(key)
            if cap is not None and totals.get(key, 0.0) + amount > cap:
                raise errors.BudgetRefusal(
                    f"cumulative {key} for {principal!r} would exceed window cap {cap} "
                    f"(split-budget evasion refused)",
                    stage="RESERVE",
                )
        for key, amount in budget.items():
            totals[key] = totals.get(key, 0.0) + amount


@dataclass
class PipelineContext:
    """Mutable carrier threaded through the 15 stages."""

    intent: ActionIntent
    fingerprint: str
    episode: DecisionEpisode
    trace: list[str]
    decision: PolicyDecision | None = None
    approval: ApprovalRecord | None = None
    grant: CapabilityGrant | None = None
    witness: CommitWitness | None = None
    receipt: ExecutionReceipt | None = None
    reconciliation: ReconciliationRecord | None = None
    outcome: OutcomeRecord | None = None


class Gate:
    """The Consequence Gate. Constructed with versions, authority and spine."""

    def __init__(
        self,
        policy_version: str,
        constitution_version: str,
        authority: ApprovalService,
        spine,
        *,
        policy_fn: Callable[..., PolicyDecision] | None = None,
        clock: Callable[[], datetime] | None = None,
        evidence_store: Mapping[str, EvidencePacket] | None = None,
        budget_caps: dict[str, dict[str, float]] | None = None,
        grant_ttl_seconds: int = 300,
        witness_ttl_seconds: int = 300,
        interceptors: Mapping[str, Iterable[Callable[["Gate", PipelineContext], None]]] | None = None,
    ):
        self.policy_version = policy_version
        self.constitution_version = constitution_version
        self.authority = authority
        self.spine = spine
        self.policy_fn = policy_fn
        self._clock = clock or _utcnow
        self.evidence_store: Mapping[str, EvidencePacket] = evidence_store or {}
        self.grant_store = GrantStore()
        self._ledger = BudgetLedger(budget_caps)
        self.grant_ttl_seconds = grant_ttl_seconds
        self.witness_ttl_seconds = witness_ttl_seconds
        self.interceptors: dict[str, list] = {
            stage: list(hooks) for stage, hooks in (interceptors or {}).items()
        }
        # adapter_id -> registered public key hex (trusted receipt keys).
        self._adapter_registry: dict[str, str] = {}

    # ------------------------------------------------------------------ API

    def register_adapter(self, adapter_id: str, public_key_hex: str) -> None:
        """Register a trusted adapter receipt key (independent of the adapter)."""
        self._adapter_registry[adapter_id] = public_key_hex

    def fingerprint(self, intent: ActionIntent) -> str:
        """The fingerprint this gate binds approvals/grants/witnesses to."""
        return intent_fingerprint(intent, self.policy_version)

    def run(
        self,
        intent: ActionIntent,
        *,
        adapter=None,
        approval: ApprovalRecord | None = None,
    ) -> DecisionEpisode:
        """Execute the 15-step pipeline. Returns the closed DecisionEpisode."""
        if not isinstance(intent, ActionIntent):
            raise errors.GateRefusal("run() requires an ActionIntent", stage="PROPOSE")
        ctx = PipelineContext(
            intent=intent,
            fingerprint="",
            episode=DecisionEpisode(intent_id=intent.id),
            trace=[],
        )
        stage = "PROPOSE"
        try:
            # PROPOSE: compute the fingerprint everything will bind to.
            ctx.fingerprint = intent_fingerprint(intent, self.policy_version)
            ctx.trace.append(f"PROPOSE: fingerprint={ctx.fingerprint}")
            self._append(ctx.intent)
            self._after(stage, ctx)

            # IDENTIFY: legal_principal must be non-empty.
            stage = "IDENTIFY"
            if not intent.legal_principal or not intent.legal_principal.strip():
                raise errors.IdentityRefusal("legal_principal must be non-empty", stage=stage)
            ctx.trace.append(f"IDENTIFY: legal_principal={intent.legal_principal}")
            self._after(stage, ctx)

            # CLASSIFY: consequence_class must be present and known.
            stage = "CLASSIFY"
            if intent.consequence_class not in CONSEQUENCE_CLASSES:
                raise errors.ClassificationRefusal(
                    f"unknown consequence_class {intent.consequence_class!r}", stage=stage
                )
            ctx.trace.append(f"CLASSIFY: consequence_class={intent.consequence_class}")
            self._after(stage, ctx)

            # EVALUATE: policy_fn(intent) -> PolicyDecision (injectable).
            stage = "EVALUATE"
            check_evidence_freshness(
                intent.evidence_ids, self.evidence_store, self._clock(), stage=stage
            )
            policy_fn = self.policy_fn or default_policy_evaluator
            decision = policy_fn(
                intent,
                intent_fingerprint=ctx.fingerprint,
                policy_version=self.policy_version,
                constitution_version=self.constitution_version,
                trace=list(ctx.trace),
            )
            self._check_decision(decision, ctx)
            ctx.decision = decision
            ctx.episode = ctx.episode.model_copy(update={"decision_id": decision.id})
            self._append(decision)
            if decision.effect == "DENY":
                raise errors.PolicyDenial("policy denied the intent", stage=stage)
            self._after(stage, ctx)

            # APPROVE: REQUIRE_HUMAN is unbypassable (Hard Rule 3).
            stage = "APPROVE"
            if decision.effect == "REQUIRE_HUMAN":
                if approval is None:
                    raise errors.ApprovalRefusal(
                        "requires_human_approval is unbypassable: no ApprovalRecord supplied",
                        stage=stage,
                    )
                self.authority.verify_approval(approval, ctx.fingerprint, now=self._clock())
                ctx.approval = approval
                ctx.episode = ctx.episode.model_copy(update={"approval_id": approval.id})
                self._append(approval)
            self._after(stage, ctx)

            # RESERVE: budget check (per-intent cap + cumulative window cap).
            stage = "RESERVE"
            budget = self._extract_budget(intent)
            self._ledger.reserve(intent.legal_principal, budget)
            self._after(stage, ctx)

            # ISSUE: one_use CapabilityGrant with short expiry.
            stage = "ISSUE"
            grant = self._issue_grant(ctx, budget)
            ctx.grant = grant
            self.grant_store.add(grant)
            self._append(grant)
            self._after(stage, ctx)

            # WITNESS: create + sign the CommitWitness.
            stage = "WITNESS"
            witness = self._create_witness(ctx)
            ctx.witness = witness
            ctx.episode = ctx.episode.model_copy(update={"witness_id": witness.id})
            self._append(witness)
            self._after(stage, ctx)

            # REAUTHORIZE: re-validate everything immediately before execute.
            stage = "REAUTHORIZE"
            revalidate(
                intent=ctx.intent,
                fingerprint=ctx.fingerprint,
                decision=ctx.decision,
                approval=ctx.approval,
                grant=ctx.grant,
                witness=ctx.witness,
                now=self._clock(),
                spine_records=list(self.spine.iter()),
                grant_store=self.grant_store,
                evidence_store=self.evidence_store,
                policy_version=self.policy_version,
                constitution_version=self.constitution_version,
            )
            self.grant_store.mark_spent(ctx.grant.grant_id)
            # Durable execution marker: survives restarts, prevents replay.
            self._append(
                InstitutionalEvent(
                    event_type="EXECUTE_BEGIN",
                    actor_id=ctx.intent.actor_id,
                    organ_id=ctx.intent.organ_id,
                    payload_hash=content_hash(ctx.witness),
                ),
                kind="EXECUTE_BEGIN",
                refs={
                    "intent_fingerprint": ctx.fingerprint,
                    "witness_id": ctx.witness.id,
                    "grant_id": ctx.grant.grant_id,
                },
            )
            self._after(stage, ctx)

            # EXECUTE: the adapter is invoked ONLY with the verified witness.
            stage = "EXECUTE"
            if adapter is None:
                raise errors.ExecutionRefusal(
                    "no adapter bound; no witness-checked adapter, no execution", stage=stage
                )
            adapter_id = getattr(adapter, "adapter_id", None)
            if adapter_id not in self._adapter_registry:
                raise errors.ExecutionRefusal(
                    f"adapter {adapter_id!r} is not registered with this gate", stage=stage
                )
            receipt = adapter.execute(ctx.witness)
            if not isinstance(receipt, ExecutionReceipt):
                raise errors.ExecutionRefusal(
                    "adapter returned no ExecutionReceipt", stage=stage
                )
            ctx.receipt = receipt
            self._after(stage, ctx)

            # RECEIPT: verify the receipt signature against the registered key.
            stage = "RECEIPT"
            self._verify_receipt(ctx, adapter)
            self._append(receipt)
            ctx.episode = ctx.episode.model_copy(update={"receipt_id": receipt.id})
            self._after(stage, ctx)

            # VERIFY: postcondition check.
            stage = "VERIFY"
            self._verify_postconditions(ctx)
            self._after(stage, ctx)

            # RECONCILE: expected vs actual outcome hashes.
            stage = "RECONCILE"
            reconciliation = self._reconcile(ctx)
            ctx.reconciliation = reconciliation
            self._append(reconciliation)
            if not reconciliation.reconciled:
                raise errors.ReconciliationRefusal(
                    f"outcome mismatch: {reconciliation.discrepancy}", stage=stage
                )
            self._after(stage, ctx)

            # OUTCOME.
            stage = "OUTCOME"
            outcome = OutcomeRecord(
                intent_fingerprint=ctx.fingerprint,
                receipt_id=receipt.id,
                actual_outcome=ctx.witness.expected_outcome,
                matched_expected=True,
                regenerative_effect={},
            )
            ctx.outcome = outcome
            self._append(outcome)
            ctx.episode = ctx.episode.model_copy(update={"outcome_id": outcome.id})
            self._after(stage, ctx)

            # CLOSE the DecisionEpisode.
            ctx.episode = ctx.episode.model_copy(
                update={"closed": True, "close_reason": "completed"}
            )
            self._append(ctx.episode)
            return ctx.episode

        except errors.GateRefusal as refusal:
            self._record_refusal(ctx, refusal)
            raise
        except Exception as exc:  # Hard Rule 4: fail closed on ANY ambiguity.
            refusal = errors.GateRefusal(f"unexpected error: {exc!r}", stage=stage)
            self._record_refusal(ctx, refusal)
            raise refusal from exc

    # -------------------------------------------------------------- internals

    def _after(self, stage: str, ctx: PipelineContext) -> None:
        for hook in self.interceptors.get(stage, ()):
            hook(self, ctx)

    def _append(self, model, *, kind: str | None = None, refs: dict | None = None):
        try:
            return self.spine.append(model, kind=kind, refs=refs)
        except errors.GateRefusal:
            raise
        except Exception as exc:
            raise errors.SpineRefusal(f"spine append failed: {exc!r}", stage="SPINE") from exc

    def _record_refusal(self, ctx: PipelineContext, refusal: errors.GateRefusal) -> None:
        """Record the refusal + closed episode on the spine (best effort).

        If the spine itself is lost mid-pipeline, the appends fail and are
        swallowed — the GateRefusal still propagates, and a later recovery
        pass records the refusal once the spine is restored.
        """
        try:
            event = InstitutionalEvent(
                event_type="GATE_REFUSAL",
                actor_id=ctx.intent.actor_id,
                organ_id=ctx.intent.organ_id,
                payload_hash=sha256_hex(str(refusal).encode("utf-8")),
            )
            self._append(
                event,
                kind="GATE_REFUSAL",
                refs={"intent_fingerprint": ctx.fingerprint, "stage": refusal.stage},
            )
        except Exception:
            pass
        try:
            closed = ctx.episode.model_copy(
                update={"closed": True, "close_reason": str(refusal)}
            )
            self._append(closed)
        except Exception:
            pass

    def _check_decision(self, decision: Any, ctx: PipelineContext) -> None:
        stage = "EVALUATE"
        if not isinstance(decision, PolicyDecision):
            raise errors.PolicyRefusal("policy_fn did not return a PolicyDecision", stage=stage)
        if decision.intent_fingerprint != ctx.fingerprint:
            raise errors.PolicyRefusal("policy decision fingerprint mismatch", stage=stage)
        if (
            decision.policy_version != self.policy_version
            or decision.constitution_version != self.constitution_version
        ):
            raise errors.PolicyRefusal("policy decision version mismatch", stage=stage)
        if decision.effect not in ("PERMIT", "DENY", "REQUIRE_HUMAN"):
            raise errors.PolicyRefusal(f"unknown effect {decision.effect!r}", stage=stage)

    def _extract_budget(self, intent: ActionIntent) -> dict[str, float]:
        raw = intent.payload.get("budget") or {}
        if not isinstance(raw, dict):
            raise errors.BudgetRefusal("payload.budget must be a mapping", stage="RESERVE")
        unknown = set(raw) - set(BUDGET_KEYS)
        if unknown:
            raise errors.BudgetRefusal(
                f"unknown budget dimensions {sorted(unknown)}; ambiguity fails closed",
                stage="RESERVE",
            )
        return {k: float(raw.get(k, 0.0)) for k in BUDGET_KEYS}

    def _issue_grant(self, ctx: PipelineContext, budget: dict[str, float]) -> CapabilityGrant:
        now = self._clock()
        grant_id = uuid.uuid4().hex
        expires_at = now + timedelta(seconds=self.grant_ttl_seconds)
        grant = CapabilityGrant(
            grant_id=grant_id,
            intent_fingerprint=ctx.fingerprint,
            allowed_tools=[ctx.intent.action_type],
            allowed_targets=[ctx.intent.target],
            budget=budget,
            one_use=True,
            expires_at=expires_at,
            revoked=False,
            signature="",
        )
        body = grant.model_dump(mode="json", exclude=_GRANT_UNSIGNED)
        signature = self.authority.sign_body(body)
        return grant.model_copy(update={"signature": signature})

    def _create_witness(self, ctx: PipelineContext) -> CommitWitness:
        now = self._clock()
        expires_at = now + timedelta(seconds=self.witness_ttl_seconds)
        witness = CommitWitness(
            intent_fingerprint=ctx.fingerprint,
            policy_decision_id=ctx.decision.id,
            approval_id=ctx.approval.id if ctx.approval else None,
            grant_id=ctx.grant.grant_id,
            constitution_version=self.constitution_version,
            policy_version=self.policy_version,
            exact_payload_hash=content_hash(ctx.intent.payload),
            exact_target=ctx.intent.target,
            expected_outcome=ctx.intent.expected_outcome,
            expires_at=expires_at,
            witness_signature="",
        )
        body = witness.model_dump(mode="json", exclude=_WITNESS_UNSIGNED)
        signature = self.authority.sign_body(body)
        return witness.model_copy(update={"witness_signature": signature})

    def _verify_receipt(self, ctx: PipelineContext, adapter) -> None:
        stage = "RECEIPT"
        receipt, witness = ctx.receipt, ctx.witness
        if receipt.witness_id != witness.id:
            raise errors.ReceiptForgery("receipt witness_id mismatch", stage=stage)
        if receipt.adapter_id != adapter.adapter_id:
            raise errors.ReceiptForgery("receipt adapter_id mismatch", stage=stage)
        pk_hex = self._adapter_registry.get(receipt.adapter_id)
        if pk_hex is None:
            raise errors.ReceiptForgery("receipt from unregistered adapter", stage=stage)
        body = receipt.model_dump(mode="json", exclude=_RECEIPT_UNSIGNED)
        if not crypto_keys.verify(
            crypto_keys.public_key_from_hex(pk_hex),
            canonical_json(body).encode("utf-8"),
            receipt.signature,
        ):
            raise errors.ReceiptForgery("receipt signature invalid (forged receipt)", stage=stage)
        if not receipt.success:
            raise errors.ExecutionRefusal("adapter reported failed execution", stage=stage)

    def _verify_postconditions(self, ctx: PipelineContext) -> None:
        stage = "VERIFY"
        h = ctx.receipt.provider_response_hash
        if (
            not isinstance(h, str)
            or len(h) != 64
            or any(c not in "0123456789abcdef" for c in h)
        ):
            raise errors.VerificationRefusal(
                "provider_response_hash is not a sha256 hex digest", stage=stage
            )
        if ctx.receipt.executed_at > self._clock() + timedelta(seconds=60):
            raise errors.VerificationRefusal("receipt executed_at is in the future", stage=stage)
        if not ctx.witness.expected_outcome:
            raise errors.VerificationRefusal("expected_outcome is empty", stage=stage)

    def _reconcile(self, ctx: PipelineContext) -> ReconciliationRecord:
        expected_hash = sha256_hex(canonical_json(ctx.witness.expected_outcome).encode("utf-8"))
        actual_hash = ctx.receipt.provider_response_hash
        reconciled = expected_hash == actual_hash
        return ReconciliationRecord(
            receipt_id=ctx.receipt.id,
            expected_hash=expected_hash,
            actual_hash=actual_hash,
            reconciled=reconciled,
            discrepancy=None
            if reconciled
            else "provider outcome hash differs from expected outcome hash",
        )
