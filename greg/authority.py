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

import urllib.parse

from dataclasses import dataclass, replace
from datetime import datetime, timezone

from greg.capabilities import CapabilityError, CapabilityManifest, InvocationContext, InvocationBudgetWindow
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
    failure_class: str | None = None     # typed where a capability failure was raised (CapabilityError)
    output_artifact: dict | None = None  # the receipt's record of the whole output kept beside a cut one (keep_output)


class AuthorityOffice:
    def __init__(self, *, compiled, passports, signer, ledger, registry, grants: GrantIssuer | None = None):
        """``registry``: the body's CapabilityRegistry, required. ``act`` refuses a capability the founder has not
        left ATTACHED (behaviour B: "the Kernel must deny affected execution immediately"), whatever path reached
        the office. There is no office without one: leaving the argument out is a TypeError, and an office whose
        registry is None refuses every act, since it cannot tell what is attached."""
        self.compiled, self.passports, self.signer, self.ledger = compiled, passports, signer, ledger
        self.registry = registry
        self.grants = grants or GrantIssuer()
        self.gate = ConsequenceGate(compiled=compiled, passports=passports, grants=self.grants,
                                    signer=signer, ledger=ledger)

    @staticmethod
    def scope_digest(*, mission_id: str, capability_id: str, params: dict, target: str,
                     consequence_class: str, cost_usd: float, spent_usd: float = 0.0,
                     budget_usd: float | None = None) -> str:
        material = {"mission_id": mission_id, "capability": capability_id, "params": params,
                    "target": target, "consequence_class": consequence_class, "cost_usd": cost_usd}
        if cost_usd > 0 and budget_usd is not None:
            # Extracted from #157: approval of one paid attempt cannot also approve another attempt after known
            # spend, or an unknown-spend reservation, changed the remaining mandate. Free reads keep their
            # stable exact scope.
            material["paid_budget_state"] = {"spent_usd": spent_usd, "budget_usd": budget_usd}
        return sha256_json(material)

    @staticmethod
    def precheck(manifest: CapabilityManifest, *, target: str, params: dict) -> tuple[str, str] | None:
        """(status, reason) when this capability cannot act on this target here, before any cone or approval
        question: unavailable on this body, or a target its manifest does not admit. None when it can.

        ``act`` returns these before it reaches the cone, so a mission never asks about such an act; asking the
        founder about it ahead of the mission's loop (``MissionEngine._askable``) applies the same test."""
        ok, why = manifest.available()
        if not ok:
            return "UNAVAILABLE", why
        if not target.startswith(manifest.target_prefix):
            return "REFUSED", f"target {target!r} outside capability prefix {manifest.target_prefix!r}"
        if manifest.target_from:  # the founder-signed target must name the host actually contacted
            host = urllib.parse.urlsplit(str(params.get(manifest.target_from, ""))).hostname or ""
            if target != manifest.target_prefix + host:
                return "REFUSED", (f"target {target!r} does not name the host {host!r} "
                                   f"that {manifest.target_from} would contact")
        return None

    def attach_refusal(self, manifest: CapabilityManifest, adapter, ctx) -> str | None:
        """Why this act may not execute on this body now, or None. Attach state is the founder's (signed
        CAPABILITY_ATTACH / DETACH, Genesis quarantine); only ATTACHED executes. A capability the registry does not
        hold is not this body's to run. Epistemic requalification never reaches this test: it does not attach.

        Attach state is keyed by id, so the id alone is not enough: what runs is the adapter, and the adapter reads
        its allowlist, binaries and credentials from the context's manifest. The manifest, the adapter and the
        context's manifest must each be the one the registry holds under that id, and none may be missing.
        Otherwise a detached capability's adapter, presented under an attached capability's manifest, would run on
        that capability's grant and be receipted in its name."""
        if self.registry is None:       # fail closed: nothing can be shown to be attached
            return ("this authority office was built without a capability registry; the Kernel runs nothing it "
                    "cannot check against one")
        cid = manifest.capability_id
        state = self.registry.state.get(cid)
        if state is None:
            return f"capability {cid} is not registered on this body; the Kernel runs no unregistered capability"
        if state != "ATTACHED":
            return f"capability {cid} is {state}; the Kernel runs only ATTACHED capabilities"
        registered = self.registry.manifests.get(cid)
        if registered is None or not self._same_manifest(registered, manifest):
            return f"the manifest presented as {cid} is not the one registered on this body"
        if adapter is None or self.registry.adapters.get(cid) is not adapter:
            return (f"the adapter presented for {cid} is not the one registered for it; the Kernel runs a "
                    "capability's own adapter only")
        if not isinstance(ctx, InvocationContext) or ctx.manifest is None:
            return (f"no invocation context names {cid}; an adapter is told which capability it runs as by the "
                    "Kernel, not left to guess")
        if not self._same_manifest(registered, ctx.manifest):
            named = getattr(ctx.manifest, "capability_id", None)
            return ((f"the invocation context names {named}, not {cid}" if named != cid else
                     f"the invocation context carries a manifest for {cid} that is not the registered one")
                    + "; an adapter is told which capability it runs as by the Kernel, not by its caller")
        return None

    @staticmethod
    def _same_manifest(registered: CapabilityManifest, presented) -> bool:
        """The registered object itself, or an equal copy of exactly its type (a restart rebuilds manifests from
        their records). A subclass that answers ``digest()`` for itself is not trusted to describe itself."""
        return presented is registered or (type(presented) is type(registered)
                                           and presented.digest() == registered.digest())

    @staticmethod
    def proposal_id(scope: str, attempt) -> str:
        """The one proposal (hence at most one Gate dispatch) of this exact scope at this attempt."""
        return "greg-" + sha256_json({"scope": scope, "attempt": attempt})[7:39]

    def prior(self, proposal_id: str):
        """Retained dispatch claim and receipt of this exact proposal: what the Gate itself recorded."""
        return self._prior(proposal_id)

    def _prior(self, proposal_id: str):
        """Retained dispatch/receipt for this exact proposal, if any (crash recovery)."""
        claims = self.ledger.select("grant_dispatch", proposal_id=proposal_id)
        if not claims:
            return None, None
        receipts = self.ledger.select("receipt", grant_id=claims[-1].payload.get("grant_id"))
        return claims[-1], (receipts[-1] if receipts else None)

    @staticmethod
    def outcome_of(receipt, *, cost_usd: float, proposal_id: str, scope_digest: str,
                   reused: str | None = None) -> ActionOutcome:
        """What one Gate receipt says happened. The receipt's result decides, never the fact that it exists.

        The one reading of a receipt, for the dispatch that just produced it (``reused`` None) and for a retained
        one found again after an interruption (``reused`` says why it stands and nothing was dispatched for it):

        - ``negative``: the capability refused or failed. REFUSED with the receipt's observed outcome and failure
          class and nothing booked, however often and whenever it is asked about;
        - ``positive``: DONE with the output it kept and the action's cost;
        - anything else (another class, no class, a result that cannot be read): UNCERTAIN. This office's executor
          writes exactly those two classes, so such a receipt does not say whether the capability acted. It is
          not a success, and it is not a refusal either: a refusal lets the mission try the action again, which
          would repeat an effect that may already have happened. It is reconciled like any unknown outcome.

        Before, ``act`` reported any retained receipt of the same proposal as DONE without reading its result. A
        body stopped between the Gate's receipt of a refusal and the mission's record of it then recorded the
        refusal as done: a refused compensation was on the record as DONE and the founder was never asked, and a
        refused read passed an ``absent`` check and closed its mission."""
        result = receipt.payload.get("result")
        result = result if isinstance(result, dict) else {}
        kept = dict(receipt_hash=receipt.hash, grant_id=receipt.payload.get("grant_id"), proposal_id=proposal_id,
                    scope_digest=scope_digest)
        klass = result.get("result_class")
        if klass == "negative":
            return ActionOutcome("REFUSED", [result.get("observed_outcome", "capability failed")],
                                 failure_class=result.get("failure_class"), **kept)
        if klass != "positive":
            return ActionOutcome("UNCERTAIN", [f"the receipt does not say whether the capability acted (result class "
                                               f"{klass!r}); its outcome is unknown and must be reconciled"], **kept)
        return ActionOutcome("DONE", [reused] if reused else [], output=result.get("output"), cost_usd=cost_usd,
                             output_artifact=result.get("output_artifact"), **kept)

    def act(self, *, mission_id: str, cone: LightCone, command_digest: str, manifest: CapabilityManifest,
            adapter, ctx: InvocationContext, params: dict, target: str, cost_usd: float,
            expected_outcome: str, evidence_refs: list, attempt, spent_usd: float,
            approved_scopes: set, evidence_confidence: float = 1.0,
            signed_scopes: frozenset = frozenset(), around=None) -> ActionOutcome:
        """``signed_scopes``: exact scopes the founder-signed mission itself pre-approves (its
        ``pre_approved_steps``). They admit that one action past the light cone only; a constitutional
        requirement for a human is still answered by an exact-scope founder DECISION alone.

        ``adapter`` is the capability's registered adapter itself (``attach_refusal``). A caller that must shape
        how it is dispatched (a long worker run off the body's turn) passes ``around``: the office applies it to
        the registered adapter at dispatch, inside the call the Gate makes once the act is authorized. No caller
        code runs before that. It changes how the adapter is called, never which adapter; the callers allowed to
        pass it are listed in the unit suite."""
        consequence = manifest.consequence_class
        scope = self.scope_digest(mission_id=mission_id, capability_id=manifest.capability_id, params=params,
                                  target=target, consequence_class=consequence, cost_usd=cost_usd,
                                  spent_usd=spent_usd, budget_usd=cone.budget_usd)
        proposal_id = self.proposal_id(scope, attempt)
        base = dict(proposal_id=proposal_id, scope_digest=scope)

        unattached = self.attach_refusal(manifest, adapter, ctx)
        if unattached is not None:      # before any cone, passport, grant, dispatch or retained-receipt reuse
            self.ledger.append("event", {"type": "greg.authority.refused_unattached", "proposal_id": proposal_id,
                                         "scope_digest": scope, "capability": manifest.capability_id,
                                         "mission_id": mission_id, "reason": unattached})
            return ActionOutcome("REFUSED", [unattached], **base)
        # The adapter is told which capability it runs as by the Kernel: the registered manifest, on a copy of the
        # context, so nothing the caller does to its own context object afterwards reaches the adapter.
        ctx = replace(ctx, manifest=self.registry.manifests[manifest.capability_id])
        if around is not None:
            # ``around`` is the caller's code, so none of it runs here. It is applied to the registered adapter
            # (checked above) inside the call the Gate makes at dispatch: after the precheck, the cone, policy and
            # the grant, and never for a refused act, a reused receipt or a dispatch whose outcome is unknown.
            registered = adapter

            def adapter(params, ctx):
                return around(registered)(params, ctx)
        refused = self.precheck(manifest, target=target, params=params)
        if refused is not None:
            return ActionOutcome(refused[0], [refused[1]], **base)
        # Exactly-once recovery for a body stopped between a paid dispatch or receipt and the mission projection
        # under the earlier scope form: only a retained exact legacy dispatch is used; legacy approvals grant
        # no new action.
        legacy_scope = self.scope_digest(mission_id=mission_id, capability_id=manifest.capability_id, params=params,
                                         target=target, consequence_class=consequence, cost_usd=cost_usd)
        if legacy_scope != scope:
            legacy_id = "greg-" + sha256_json({"scope": legacy_scope, "attempt": attempt})[7:39]
            old_claim, old_receipt = self._prior(legacy_id)
            old_base = dict(proposal_id=legacy_id, scope_digest=legacy_scope)
            if old_receipt is not None:   # a refusal keeps its own reason and failure class, as below
                return self.outcome_of(old_receipt, cost_usd=cost_usd, reused="retained legacy receipt; no redispatch",
                                       **old_base)
            if old_claim is not None:
                return ActionOutcome("UNCERTAIN", ["retained legacy dispatch; no receipt or blind retry"], **old_base)
        outside = cone.admits(capability=manifest.capability_id, target=target, consequence_class=consequence,
                              cost_usd=cost_usd, spent_usd=spent_usd)
        if outside and scope not in approved_scopes and scope not in signed_scopes:
            return ActionOutcome("OUTSIDE_SCOPE", outside, **base)

        claim, receipt = self._prior(proposal_id)
        if receipt is not None:  # already dispatched before an interruption: reuse, never redo
            # Reported as the call that produced it reported it: DONE with the whole output it kept, so a reused
            # reading is judged as the fresh one was (review of #209), or the same REFUSED when the capability
            # refused. A retained refusal is not a success because a restart came between it and its record.
            return self.outcome_of(receipt, cost_usd=cost_usd, reused="retained receipt reused after restart", **base)
        if claim is not None:  # the dispatch the claim names, so its reconciliation settles exactly that one
            return ActionOutcome("UNCERTAIN", ["dispatch claimed without receipt; outcome unknown"],
                                 grant_id=claim.payload.get("grant_id"), **base)

        worker = self.passports.issue(kind="agent", creator="greg-authority-office", owner_organ="uniimente-kernel",
                                      legal_principal=PRINCIPAL, declared_capabilities=[manifest.capability_id],
                                      budget_ceiling_usd=cost_usd, consequence_class=consequence, ttl_seconds=900)
        try:
            return self._act_as(worker, manifest=manifest, mission_id=mission_id, params=params, target=target,
                                consequence=consequence, cost_usd=cost_usd, command_digest=command_digest,
                                evidence_refs=evidence_refs, evidence_confidence=evidence_confidence,
                                expected_outcome=expected_outcome, scope=scope, proposal_id=proposal_id,
                                approved_scopes=approved_scopes, signed_scopes=signed_scopes, outside=outside,
                                ctx=ctx, adapter=adapter, cone=cone, spent_usd=spent_usd, base=base)
        finally:
            # The call has returned, including a refusal or an unknown outcome. This passport
            # was live only while the call held it. Leaving it until the 900s TTL fills the
            # ceiling and the body stops. A revocation is a different record and is not retired.
            self.passports.retire(worker.passport_id)

    def _act_as(self, worker, *, manifest, mission_id, params, target, consequence, cost_usd,
                command_digest, evidence_refs, evidence_confidence, expected_outcome, scope,
                proposal_id, approved_scopes, signed_scopes, outside, ctx, adapter, cone, spent_usd, base):
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
                                     "founder_approved_scope": scope in approved_scopes,
                                     **({"pre_approved_in_signed_mission": True}
                                        if outside and scope in signed_scopes else {})})

        def execute(p):
            try:
                # Limits are projected from the current canonical dispatch. The
                # projection is not a grant and cannot replenish reserved spend.
                window = None
                if manifest.capability_id.startswith("cognition."):
                    dispatch, _ = self._prior(proposal_id)
                    window = InvocationBudgetWindow(
                        horizon=cone.horizon, grant_expires_at=grant["expires_at"],
                        remaining_money_usd=max(0.0, cone.budget_usd - spent_usd - cost_usd),
                        authority_ref=command_digest, grant_id=grant["grant_id"],
                        grant_digest=sha256_json(grant), mission_id=mission_id,
                        scope_digest=scope, proposal_id=proposal_id,
                        witness_id=dispatch.payload.get("witness_id") if dispatch else None,
                        dispatch_effect_digest=dispatch.payload.get("effect_digest") if dispatch else None)
                output = adapter(params, replace(ctx, target=target, mission_id=mission_id,
                                                authority_ref=command_digest, grant_id=grant['grant_id'],
                                                policy_version=self.compiled.constitution_version,
                                                cognition_budget=window))
            except CapabilityError as exc:
                return {"observed_outcome": "capability refused: " + str(exc)[:300], "result_class": "negative",
                        "failure_class": exc.failure_class, "output": None, "validation_status": "self_reported"}
            kept, whole = keep_output(output, ctx.artifact_root)
            return {"observed_outcome": expected_outcome, "result_class": "positive",
                    "output": kept, "validation_status": "self_reported", **({"output_artifact": whole} if whole else {})}

        def approver(p, reasons):
            return (scope in approved_scopes, "founder-signed decision for exact scope"
                    if scope in approved_scopes else "no founder decision")

        record = self.gate.run(proposal, executor=execute, approver=approver, standing_grant=grant)
        if record.state == "recorded":   # read by the one function a retained receipt is read by, so they cannot differ
            return self.outcome_of(self.ledger.find(record.receipt_hash), cost_usd=cost_usd, **base)
        if record.state == "reconciliation_required":
            return ActionOutcome("UNCERTAIN", record.refusal_reasons, grant_id=grant["grant_id"], **base)
        return ActionOutcome("REFUSED", record.refusal_reasons or [record.state], grant_id=grant["grant_id"], **base)


RECEIPT_TEXT_LIMIT = 16 * 1024
RECEIPT_LIST_LIMIT = 1000      # items a receipt keeps of a list; greg/missions.py reads this one constant


def text_bytes(value: str) -> bytes:
    """The bytes a receipt digests a string by: UTF-8, with a lone surrogate (which JSON from an untrusted tool or
    server can carry) kept as its own code unit instead of failing the action. Identical to UTF-8 for any other
    string."""
    return value.encode("utf-8", "surrogatepass")


NON_FINITE = {"NaN", "Infinity", "-Infinity"}


def bounded(value):
    """Receipts keep evidence, not bulk: long strings keep a prefix plus their digest. A number that is not finite
    (NaN or an infinity, which JSON cannot carry) is kept as ``{"non_finite": ...}``: before, it passed through and
    made the ledger's strict JSON raise after the action had run, out of every tick (review of #196, J6)."""
    import hashlib
    import math
    if isinstance(value, float) and not math.isfinite(value):
        return {"non_finite": "NaN" if value != value else "Infinity" if value > 0 else "-Infinity"}
    if isinstance(value, str) and len(value) > RECEIPT_TEXT_LIMIT:
        return {"prefix": value[:RECEIPT_TEXT_LIMIT], "truncated": True,
                "sha256": hashlib.sha256(text_bytes(value)).hexdigest(), "length": len(value)}
    if isinstance(value, dict):
        return {k: bounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [bounded(v) for v in value[:RECEIPT_LIST_LIMIT]]
    return value


OUTPUT_ARTIFACT_BYTES = 1024 * 1024   # the whole output kept beside a cut receipt (the cognition request ceiling)
OUTPUT_ARTIFACT_DIR = "outputs"        # their own root, so kept outputs never spend the quota artifact.store imports use


def output_store(artifact_root):
    """The store kept outputs live in: a separate root under the body's artifact store, with its own quota. When it
    is full, outputs are no longer kept (the receipt says so); imports through artifact.store are never refused for
    it."""
    from pathlib import Path
    from greg.artifacts import ArtifactStore
    return ArtifactStore(Path(artifact_root) / OUTPUT_ARTIFACT_DIR, max_object_bytes=OUTPUT_ARTIFACT_BYTES)


def keep_output(output, artifact_root):
    """What a receipt keeps of an action's output, and where the whole output went when the bound cut it.

    The one place an output is cut for a receipt. When ``bounded`` would cut it (a string past RECEIPT_TEXT_LIMIT, a
    list past its item limit), the whole output is kept, as canonical JSON, in the body's content-addressed artifact
    store, and the receipt records that address beside the cut wrappers, which stay exactly as before. The store holds
    bytes, not authority: a bind reads them back only by the address the ledger recorded, re-hashed on read
    (greg/missions.py ``artifact_output``). When the body has no store, or the output cannot be kept there, the
    receipt says so, and only the cut form exists: nothing downstream may stand a prefix in for it."""
    import json
    kept = bounded(output)
    if kept == output:
        return kept, None
    if artifact_root is None:
        return kept, {"address": None, "unavailable": "this body has no artifact store"}
    try:
        try:
            data = json.dumps(output, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        except UnicodeEncodeError:   # a lone surrogate: the same JSON value, written with escapes
            data = json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
        address, _ = output_store(artifact_root).put(data)
    except (TypeError, ValueError, CapabilityError, OSError) as exc:
        return kept, {"address": None, "unavailable": "whole output not kept: " + str(exc)[:200]}
    return kept, {"address": address, "bytes": len(data), "encoding": "canonical-json"}


def now() -> datetime:
    return datetime.now(timezone.utc)
