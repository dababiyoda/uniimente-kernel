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
    unknown or stale evidence      -> fail closed at evaluation and again at
                                      commit, for a Gate holding an evidence
                                      register; without one, evidence refs are
                                      opaque digests checked for presence only
    effect mismatch at commit      -> hard refusal and incident
    authority change at commit     -> hard refusal and incident: only ALLOW, or
                                      REQUIRE_HUMAN covered by a human approval
                                      held for this exact proposal, executes
    proposal changed after admission -> refused up to the dispatch claim; the
                                      Gate witnesses, claims and executes its
                                      own frozen copy, so a later change to the
                                      caller's object never reaches the effect
    missing outcome record         -> blocks autonomy promotion
    any failure                    -> fails toward silence, never toward
                                      uncontrolled external action

The gate never performs I/O itself. Execution happens through an injected
executor callable; approval through an injected approver callable. Models
recommend. This code authorizes.
"""
from __future__ import annotations

import copy
import math
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Callable, Any, Mapping

from compiler.ucl_compiler import CompiledConstitution
from identity.machine_passport import CONSEQUENCE_CLASSES, PassportRegistry
from policy.engine import Proposal, Verdict, evaluate
from provenance.ledger import EvidenceLedger
from provenance.commit_witness import WitnessSigner, new_witness, sha256_obj

TERMINAL_STATES = {"recorded", "refused", "denied", "expired", "revoked", "failed"}
APPROVAL_TTL = timedelta(hours=72)          # pending_human expires after 72 hours
GRANT_TTL = timedelta(minutes=15)           # single-action grants are short-lived

# Who may do what, under which principal, at which consequence class. A grant
# is minted for exactly these; the effect itself (payload, target, action_class)
# is bound separately by bound_effect_hash.
GRANT_AUTHORITY_FIELDS = ("actor", "legal_principal", "objective", "action_class",
                          "consequence_class", "requested_capability")
# Everything policy read when this run admitted the proposal, and the identity
# its dispatch is claimed under. Proposal is a mutable dataclass, so the run
# snapshots these at admission and refuses at commit if any changed in between
# (#55, CASE 27: an escalation in the commit window must not execute on an
# earlier evaluation). From admission on the Gate also acts on its own frozen
# copy of the proposal, never on the caller's object (see ConsequenceGate.run).
COMMIT_WINDOW_FIELDS = GRANT_AUTHORITY_FIELDS + (
    "payload", "target", "estimated_cost_usd", "evidence_confidence", "evidence_refs",
    "expected_outcome", "context", "proposal_id")


def _authority_digest(proposal: Proposal, fields: tuple[str, ...]) -> str:
    return sha256_obj({name: getattr(proposal, name) for name in fields})


def _digest_or_none(proposal: Proposal) -> str | None:
    """The commit-window digest, or None when the proposal cannot be canonicalised
    (e.g. a dict with mixed key types). None never equals an admitted digest."""
    try:
        return _authority_digest(proposal, COMMIT_WINDOW_FIELDS)
    except Exception:  # noqa: BLE001 - an uncanonicalisable proposal is refused, not raised
        return None


def _is_cost(value) -> bool:
    """A cost is a finite, non-negative number (NaN compares false with every limit)."""
    try:
        return not isinstance(value, bool) and math.isfinite(float(value)) and float(value) >= 0
    except (TypeError, ValueError, OverflowError):
        return False


REVOCATION_FIELDS = ("revoked", "revoked_at", "revocation_reason")


def _sans_revocation(grant: dict) -> dict:
    """A grant's issued content. Revocation is read from the issuer's record, never from a copy."""
    return {k: v for k, v in grant.items() if k not in REVOCATION_FIELDS}


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
    explicit and per-grant. Uncertain effects retain their reservation pending
    reconciliation; definite pre-execution refusals can release it."""

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


class GrantRefused(ValueError):
    """The issuer will not mint this grant: it would exceed what its parent holds."""


class GrantIssuer:
    """Issues single-action capability grants per the grant contract.
    New grants start at simulate/shadow; an executable single-action grant
    is issued only after policy ALLOW (and human approval where required),
    is bound to one exact effect hash, and expires in minutes.

    The issued grant validates exactly against contracts/capability-grant.
    Gate-internal metadata (stage, single-use, effect binding) lives in a
    separate internal record keyed by grant_id; the wire contract is never
    patched silently.

    The issuer's own records are never handed out. ``issue_single_action``
    returns a published copy (the issuer refreshes its revocation fields when it
    revokes), ``get`` and ``get_meta`` return fresh copies, and every decision
    reads the sealed record: a holder who edits a grant it was given (un-revoking
    it, widening its limit or actions) changes only its own copy, which the
    Gate then refuses as altered.

    A child grant (proposal.context["parent_grant"]) is a strict subset of its
    parent, as authority/authority-matrix.yaml grant_rules declares
    (child_grants: strict_subset_of_parent; revocation:
    immediate_and_propagating):

    * the parent and every ancestor must be known to this issuer, unrevoked,
      unexpired and unconsumed, at minting and again whenever a descendant is
      admitted or committed by the Gate;
    * the child may not exceed the parent's permitted actions, counterparties
      or legal actor, may not take an action the parent prohibits, may not
      raise its consequence class or change its action class or objective,
      inherits its prohibitions and never outlives it;
    * spending is delegated, not copied: the children of one parent together
      hold at most the parent's spending limit, and the parent itself may then
      spend only what it has not delegated;
    * a single-use parent is one action: once the parent executes, its
      delegation ends and its descendants refuse;
    * revoking a grant revokes its descendants.
    """

    def __init__(self, issuer_id: str = "spiffe://uniimente.internal/kernel/action-gateway"):
        self.issuer_id = issuer_id
        self._grants: dict[str, dict] = {}       # published copies handed to holders; never trusted
        self._sealed: dict[str, dict] = {}       # the issuer's own contract-valid records
        self._meta: dict[str, dict] = {}         # gate-internal metadata
        self._children: dict[str, list[str]] = {}

    @staticmethod
    def _expires(grant: dict) -> datetime:
        return datetime.fromisoformat(grant["expires_at"].replace("Z", "+00:00"))

    def lineage_problems(self, grant_id: str, now: datetime) -> list[str]:
        """Why an ancestor of ``grant_id`` no longer supports it (empty when every ancestor does)."""
        problems: list[str] = []
        seen = {grant_id}
        record = self._sealed.get(grant_id)
        parent_id = record.get("parent_grant") if record else None
        while parent_id is not None:
            if parent_id in seen:
                return problems + ["grant lineage is cyclic"]
            seen.add(parent_id)
            parent = self._sealed.get(parent_id)
            if parent is None:
                return problems + [f"ancestor grant {parent_id!r} is unknown to this issuer"]
            if parent["revoked"]:
                problems.append(f"ancestor grant {parent_id} is revoked")
            if now >= self._expires(parent):
                problems.append(f"ancestor grant {parent_id} is expired")
            if self._meta.get(parent_id, {}).get("used"):
                problems.append(f"ancestor grant {parent_id} is already consumed: its single action ended "
                                f"its delegation")
            parent_id = parent.get("parent_grant")
        return problems

    def delegation_problems(self, grant_id: str, cost) -> list[str]:
        """A grant may itself spend only the part of its limit it has not delegated to children."""
        record, meta = self._sealed.get(grant_id), self._meta.get(grant_id, {})
        if record is None:
            return [f"grant {grant_id!r} is unknown to this issuer"]
        delegated = meta.get("delegated_usd", 0.0)
        if not _is_cost(cost):
            return [f"cost {cost!r} is not a finite non-negative amount"]
        if delegated and float(cost) + delegated > float(record["spending_limit_usd"]):
            return [f"cost {float(cost)} exceeds what this grant has not delegated to its children "
                    f"({float(record['spending_limit_usd']) - delegated} of {record['spending_limit_usd']})"]
        return []

    def _parent_of(self, proposal: Proposal, now: datetime) -> dict | None:
        """Refuse a child grant that would exceed its parent (mechanism of PR #12
        sdk-python/uniimente_kernel/capability.py _enforce_subset_of_parent)."""
        parent_id = proposal.context.get("parent_grant")
        if parent_id is None:
            return None
        parent = self._sealed.get(parent_id) if isinstance(parent_id, str) else None
        if parent is None:
            raise GrantRefused(f"parent grant {parent_id!r} unknown to this issuer")
        meta = self._meta[parent_id]
        if parent["revoked"]:
            raise GrantRefused("parent grant is revoked")
        if now >= self._expires(parent):
            raise GrantRefused("parent grant is expired")
        if meta.get("used"):
            raise GrantRefused("parent grant is already consumed")
        lineage = self.lineage_problems(parent_id, now)
        if lineage:
            raise GrantRefused("parent grant lineage: " + "; ".join(lineage))
        if proposal.requested_capability not in parent.get("permitted_actions", []):
            raise GrantRefused("child grant exceeds parent permitted_actions")
        if not _is_cost(proposal.estimated_cost_usd):
            raise GrantRefused(f"child grant cost {proposal.estimated_cost_usd!r} is not a finite "
                               f"non-negative amount")
        cost, limit = float(proposal.estimated_cost_usd), float(parent.get("spending_limit_usd", 0))
        if cost > limit:
            raise GrantRefused("child grant exceeds parent spending limit")
        if cost + meta.get("delegated_usd", 0.0) > limit:
            raise GrantRefused(f"child grant exceeds what remains of the parent spending limit "
                               f"({limit - meta.get('delegated_usd', 0.0)} of {limit} not yet delegated)")
        if proposal.target not in parent.get("counterparties", []):
            raise GrantRefused("child grant exceeds parent counterparties")
        if proposal.legal_principal != parent.get("legal_actor"):
            raise GrantRefused("child grant changes the parent's legal actor")
        if proposal.action_class in parent.get("prohibited", []):
            raise GrantRefused(f"{proposal.action_class} is prohibited by the parent grant")
        if proposal.action_class != meta.get("action_class"):
            raise GrantRefused("child grant changes the parent's action class")
        if proposal.objective != parent.get("objective"):
            raise GrantRefused("child grant changes the parent's objective")
        if (proposal.consequence_class not in CONSEQUENCE_CLASSES
                or meta.get("consequence_class") not in CONSEQUENCE_CLASSES
                or CONSEQUENCE_CLASSES.index(proposal.consequence_class)
                > CONSEQUENCE_CLASSES.index(meta["consequence_class"])):
            raise GrantRefused("child grant raises the parent's consequence class")
        return parent

    def issue_single_action(self, *, proposal: Proposal, policy_version: str) -> dict:
        now = _now()
        parent = self._parent_of(proposal, now)
        expires = now + GRANT_TTL
        if parent is not None:
            expires = min(expires, self._expires(parent))
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
            "prohibited": list(parent.get("prohibited", [])) if parent else [],
            "initial_stage": "simulate",           # lineage: starts non-executable
            "parent_grant": parent["grant_id"] if parent else None,
            "issued_at": _rfc(now),
            "expires_at": _rfc(expires),
            "escalation_triggers": [],
            "revocable_by": ["spiffe://uniimente.internal/kernel/action-gateway"],
            "revoked": False,
            "revoked_at": None,
            "revocation_reason": None,
        }
        meta = {
            "stage": "execute_once",               # promoted by policy decision, recorded
            "stage_promotion_evidence": policy_version,
            "single_use": True,
            "used": False,
            "bound_effect_hash": sha256_obj({"payload": proposal.payload, "target": proposal.target,
                                             "action_class": proposal.action_class}),
            "bound_authority_hash": _authority_digest(proposal, GRANT_AUTHORITY_FIELDS),
            # what a child is measured against (the hash above binds them; these are the values)
            "action_class": proposal.action_class,
            "consequence_class": proposal.consequence_class,
            "delegated_usd": 0.0,
        }
        gid = grant["grant_id"]
        self._sealed[gid] = copy.deepcopy(grant)
        self._meta[gid] = meta
        if parent is not None:
            self._meta[parent["grant_id"]]["delegated_usd"] += grant["spending_limit_usd"]
            self._children.setdefault(parent["grant_id"], []).append(gid)
        self._grants[gid] = grant
        return grant

    def get(self, grant_id: str) -> dict | None:
        """A copy of the issuer's record (None when this issuer never issued it)."""
        record = self._sealed.get(grant_id)
        return copy.deepcopy(record) if record is not None else None

    def get_meta(self, grant_id: str) -> dict:
        return copy.deepcopy(self._meta.get(grant_id, {}))

    def revoke(self, grant_id: str, *, reason: str, revoker: str) -> None:
        """Revoke a grant and, propagating, every grant delegated from it."""
        pending = [(grant_id, f"{reason} (by {revoker})")]
        while pending:
            gid, why = pending.pop()
            g = self._sealed.get(gid)
            if not g or g["revoked"]:
                continue
            fields = {"revoked": True, "revoked_at": _rfc(_now()), "revocation_reason": why}
            g.update(fields)
            if gid in self._grants:
                self._grants[gid].update(fields)   # holders see the revocation; nothing trusts their copy
            pending.extend((child, f"parent grant {gid} revoked") for child in self._children.get(gid, ()))

    def mark_used(self, grant_id: str) -> None:
        if grant_id in self._meta:
            self._meta[grant_id]["used"] = True


class ConsequenceGate:
    """The sole path to external effects."""

    def __init__(self, *, compiled: CompiledConstitution, passports: PassportRegistry,
                 ledger: EvidenceLedger, signer: WitnessSigner,
                 grants: GrantIssuer | None = None, budget: BudgetOffice | None = None,
                 policy_version: str = "1.0.0",
                 evidence_thresholds: dict | None = None,
                 evidence: Mapping[str, dict] | None = None):
        self.compiled = compiled
        self.passports = passports
        self.ledger = ledger
        self.signer = signer
        self.grants = grants or GrantIssuer()
        self.budget = budget or BudgetOffice()
        self.policy_version = policy_version
        self.evidence_thresholds = evidence_thresholds
        # Register of contracts/evidence.schema.json packets by packet_id. When
        # present, every evidence ref must resolve to a fresh packet at
        # evaluation and again at commit (#21); unknown or stale refuses.
        self.evidence = evidence

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

        # Admission (#55). The caller's Proposal is a mutable object the caller
        # still holds. The Gate digests it and takes its own deep copy here;
        # everything after admission (policy, budget, witness, commit check,
        # dispatch claim, executor argument, outcome) reads the frozen copy, and
        # a change to the caller's object is refused up to the dispatch claim.
        # A proposal that cannot be canonicalised cannot be bound: refused.
        try:
            admitted = _authority_digest(proposal, COMMIT_WINDOW_FIELDS)
            frozen = copy.deepcopy(proposal)
        except Exception as exc:  # noqa: BLE001 - fail closed, never raise out of the Gate
            return self._refuse(rec, "refused", [f"proposal is not canonicalizable: {type(exc).__name__}: {exc}"])

        # A supplied object is not authority: resolve it against the existing
        # issuer, validate its contract and bind actor/objective/target. No new
        # issuer, credentials or founder authentication is introduced here. The
        # caller's dict is only compared: from here on the Gate reads the
        # issuer's record, so revocation, lineage and delegation are the issuer's.
        managed = None
        if standing_grant is not None:
            from adapters.contract_validation import validate_contract
            try:
                validate_contract(standing_grant, 'capability-grant')
                managed = self.grants.get(standing_grant['grant_id'])
                if managed is None or managed != standing_grant:
                    raise ValueError('unregistered or altered grant')
                if (managed['grantee'] != frozen.actor
                        or managed['objective'] != frozen.objective
                        or frozen.target not in managed.get('counterparties', [])):
                    raise ValueError('grant actor/objective/target mismatch')
                if (self.grants.get_meta(managed['grant_id']).get('bound_authority_hash')
                        != _authority_digest(frozen, GRANT_AUTHORITY_FIELDS)):
                    raise ValueError('grant authority binding mismatch: consequence class, '
                                     'capability or principal differs from what was granted')
            except (ValueError, KeyError, TypeError) as exc:
                return self._refuse(rec, 'refused', [f'grant: {exc}'])
            problems = (self.grants.lineage_problems(managed['grant_id'], _now())
                        + self.grants.delegation_problems(managed['grant_id'], frozen.estimated_cost_usd))
            if problems:
                return self._refuse(rec, 'refused', [f'grant: {p}' for p in problems])

        # 3-5. legal principal + evidence + policy -----------------------
        approval: dict | None = None
        eval_grant = self._eval_view(managed) if managed is not None else None
        decision = evaluate(self.compiled, frozen, identity_ok=ok, grant=eval_grant,
                            thresholds=self.evidence_thresholds, evidence=self.evidence)
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
            if _digest_or_none(proposal) != admitted:
                return self._refuse(rec, "refused", ["proposal changed during human approval; "
                                                     "the approval covers only the evaluated proposal"])
            # The approval covers exactly these reasons for exactly this proposal.
            approval = {"authority_digest": admitted, "reasons": list(decision.reasons)}
            self._transition(rec, "evaluating", {"step": "policy_recheck_after_approval"})
            decision = evaluate(self.compiled, frozen, identity_ok=True, grant=eval_grant,
                                thresholds=self.evidence_thresholds, evidence=self.evidence)
            if decision.verdict == Verdict.DENY:
                return self._refuse(rec, "refused", decision.reasons)

        # 7. capability ----------------------------------------------------
        # Extracted from #87: an external proposal cannot acquire its own
        # missing authority merely by reaching this line. Unknown classes deny.
        # A caller-supplied low consequence label cannot make an arbitrary
        # injected executor harmless. The Gate consumes grants; it never fills
        # in a missing one. Policy may issue bounded internal grants upstream.
        if managed is None:
            return self._refuse(rec, 'refused', ['executor admission requires pre-existing grant'])
        grant = managed
        rec.grant_id = grant["grant_id"]
        self._transition(rec, "granted", {"grant_id": grant["grant_id"]})

        # 8. budget reservation ---------------------------------------------
        try:
            reservation = self.budget.reserve(grant["grant_id"], frozen.estimated_cost_usd,
                                              float(grant.get("spending_limit_usd", 0)))
        except ValueError as e:
            return self._refuse(rec, "refused", [f"budget: {e}"])

        # 9. Commit Witness ---------------------------------------------------
        witness = new_witness(
            actor=frozen.actor, legal_principal=frozen.legal_principal,
            action_class=frozen.action_class, payload=frozen.payload, target=frozen.target,
            policy_version=self.policy_version, constitution_hash=self.compiled.constitution_hash,
            grant_id=grant["grant_id"], capability=frozen.requested_capability,
            budget_reservation_id=reservation["reservation_id"],
            expected_outcome=frozen.expected_outcome, evidence_refs=frozen.evidence_refs)
        self.signer.sign(witness)
        rec.witness_id = witness.witness_id
        self.ledger.append("witness", asdict(witness))

        # 10. commit-time revalidation ---------------------------------------
        problem = self._reauthorize_at_commit(frozen, grant, witness, admitted=admitted,
                                              approval=approval, live=proposal)
        if problem is not None:
            self.budget.release(reservation["reservation_id"])
            state, reasons = problem
            if state == "refused" and any("effect mismatch" in r for r in reasons):
                rec.incident = "effect_mismatch_at_commit"
                self.ledger.append("event", {"type": "incident.effect_mismatch",
                                             "action_id": rec.action_id, "reasons": reasons})
            elif state == "refused" and any("authority" in r and "mismatch" in r for r in reasons):
                rec.incident = "authority_mismatch_at_commit"
                self.ledger.append("event", {"type": "incident.authority_mismatch",
                                             "action_id": rec.action_id, "reasons": reasons})
            return self._refuse(rec, state, reasons)

        # 11. execution --------------------------------------------------------
        # Reserve a durable dispatch identity BEFORE invoking anything. An
        # exception can mean an effect occurred: retain reservation and claim.
        # The claim, the executed effect and the outcome are all the frozen
        # copy's; the caller's object is checked one last time before the claim.
        effect_digest = sha256_obj({'payload': frozen.payload, 'target': frozen.target,
                                    'action_class': frozen.action_class})
        with self.ledger._lock:
            if _digest_or_none(proposal) != admitted:
                self.budget.release(reservation['reservation_id'])
                rec.incident = "authority_mismatch_at_commit"
                reasons = ["authority mismatch before dispatch: proposal changed after the commit check"]
                self.ledger.append("event", {"type": "incident.authority_mismatch",
                                             "action_id": rec.action_id, "reasons": reasons})
                return self._refuse(rec, "refused", reasons)
            claims = self.ledger.by_type('grant_dispatch')
            if any(r.payload['proposal_id'] == frozen.proposal_id or
                   r.payload['grant_id'] == grant['grant_id'] for r in claims):
                self.budget.release(reservation['reservation_id'])
                return self._refuse(rec, 'reconciliation_required', ['dispatch already claimed; no blind retry'])
            self.ledger.append('grant_dispatch', {'proposal_id': frozen.proposal_id,
                'grant_id': grant['grant_id'], 'witness_id': witness.witness_id,
                'effect_digest': effect_digest})
        self._transition(rec, "executing", {"witness_id": witness.witness_id})
        try:
            result = executor(copy.deepcopy(frozen))
        except Exception as e:  # fail toward silence + preservation
            rec.incident = f"executor_exception:{type(e).__name__}"
            return self._refuse(rec, "reconciliation_required", [f"executor raised {type(e).__name__}: {e}; outcome unknown"])
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
        reconciled = observed == frozen.expected_outcome
        outcome = {
            "outcome_id": str(uuid.uuid4()),
            "action_ref": rec.action_id,
            "recorded_at": _rfc(_now()),
            "recorded_by": frozen.actor,
            "external_observation": observed,
            "result_class": result.get("result_class", "inconclusive"),
            "expected_vs_actual": f"expected={frozen.expected_outcome!r} actual={observed!r} "
                                  f"reconciled={reconciled}",
            "metrics": result.get("metrics"),
            "evidence_refs": frozen.evidence_refs,
            "learning": result.get("learning"),
            "validation_status": result.get("validation_status", "internally_observed"),
            "feeds": ["causal_memory", "calibration"],
        }
        self.ledger.append("outcome", outcome)
        rec.outcome = outcome
        self._transition(rec, "recorded", {"outcome_id": outcome["outcome_id"],
                                           "reconciled": reconciled})
        return rec

    def _reauthorize_at_commit(self, proposal: Proposal, grant: dict, witness, *,
                               admitted: str | None = None,
                               approval: dict | None = None,
                               live: Proposal | None = None) -> tuple[str, list[str]] | None:
        """Authority is ALWAYS revalidated at the durability boundary.

        Only ALLOW passes. REQUIRE_HUMAN passes only when this run holds a human
        approval given for this exact proposal and for every reason now raised;
        anything else (DENY, an unapproved REQUIRE_HUMAN, an unknown verdict)
        refuses. ``proposal`` is the Gate's frozen admission copy; ``live`` is
        the caller's object it was frozen from. Both must still equal what was
        admitted and granted; when the caller's object changed it is judged too,
        so the refusal names what the change would have needed.
        """
        reasons: list[str] = []
        current = _digest_or_none(proposal)
        subjects = [proposal]
        changed = admitted is None or current != admitted
        if live is not None and live is not proposal and _digest_or_none(live) != admitted:
            changed = True
            subjects.append(live)
        if changed:
            reasons.append("authority mismatch at commit: proposal changed after admission "
                           "(consequence class, cost, evidence, effect or context)")
        # witness signature must verify
        if not self.signer.verify(witness):
            reasons.append("witness signature invalid")
        # grant must still be valid, fresh, unrevoked, unused, and bound to this effect
        # ``grant`` is the Gate's own admission copy of the issuer's record; only the
        # issuer can have changed it since, and only by revoking it.
        managed = self.grants.get(grant["grant_id"])
        if managed is None or _sans_revocation(managed) != _sans_revocation(grant):
            return 'refused', ['grant missing or altered at commit']
        g = managed
        meta = self.grants.get_meta(g["grant_id"])
        if g.get("revoked"):
            reasons.append("revoked grant at commit")
        if meta.get("single_use") and meta.get("used"):
            reasons.append("single-use grant already consumed")
        now = _now()
        if now >= datetime.fromisoformat(g["expires_at"].replace("Z", "+00:00")):
            reasons.append("expired grant at commit")
        reasons.extend(f"{p} at commit" for p in self.grants.lineage_problems(g["grant_id"], now))
        reasons.extend(f"{p} at commit" for p in self.grants.delegation_problems(g["grant_id"],
                                                                               proposal.estimated_cost_usd))
        for subject in subjects:
            try:
                found = self._commit_reasons(subject, g, meta, approval)
            except Exception as exc:  # noqa: BLE001 - an unjudgeable proposal is refused
                found = [f"authority mismatch at commit: proposal cannot be re-evaluated ({type(exc).__name__})"]
            reasons.extend(r for r in found if r not in reasons)
        if reasons:
            state = "revoked" if any("revoked" in r for r in reasons) else "refused"
            return state, reasons
        return None

    def _commit_reasons(self, proposal: Proposal, grant: dict, meta: dict,
                        approval: dict | None) -> list[str]:
        """Effect and authority bindings, identity and policy for one proposal at commit."""
        reasons: list[str] = []
        bound = meta.get("bound_effect_hash")
        if bound and bound != sha256_obj(
                {"payload": proposal.payload, "target": proposal.target,
                 "action_class": proposal.action_class}):
            reasons.append("effect mismatch at commit: payload/target diverged from authorized effect")
        if meta.get("bound_authority_hash") != _authority_digest(proposal, GRANT_AUTHORITY_FIELDS):
            reasons.append("authority binding mismatch at commit: consequence class, capability or "
                           "principal diverged from the granted authority")
        # identity must still be valid
        ok, why = self.passports.verify(proposal.actor)
        if not ok:
            reasons.append(f"identity lapsed before commit: {why}")
        # policy must still allow, with the identical input. The evaluation view
        # merges the wire contract with gate-managed stage metadata (the contract
        # records initial_stage; the runtime stage is promoted by the decision).
        decision = evaluate(self.compiled, proposal, identity_ok=True, grant=self._eval_view(grant),
                            thresholds=self.evidence_thresholds, evidence=self.evidence)
        if decision.verdict == Verdict.DENY:
            reasons.extend(f"commit-time policy refusal: {r}" for r in decision.reasons)
        elif decision.verdict == Verdict.REQUIRE_HUMAN:
            held = (approval is not None and approval.get("authority_digest") == _digest_or_none(proposal)
                    and set(decision.reasons) <= set(approval.get("reasons", ())))
            if not held:
                reasons.extend(f"commit-time policy requires a human approval this run does not hold: {r}"
                               for r in decision.reasons)
        elif decision.verdict != Verdict.ALLOW:
            reasons.append(f"commit-time policy verdict {decision.verdict!r} is not allow")
        return reasons
