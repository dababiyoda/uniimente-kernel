"""Commit Witness: binds authorization to the exact effect, at commit time.

Layer 3 of the stack (Consequence Gate and Commit Witness).

A Commit Witness binds an authorization to:
    the exact payload, the exact target, the policy version,
    the Constitution version, the current authority, the current
    capability, the current budget, and the expected outcome.

It answers, with a proof that survives the disappearance of the original
model: "This exact machine, acting for this exact entity, received this
exact permission, under this exact law, using this exact evidence, to
create this exact result."

Commit-time authorization research (July 2026 preprint, per doctrine):
agents frequently complete durable effects after their earlier authority
path has become invalid — therefore authority is ALWAYS revalidated at
the durability boundary, and the witness is what gets revalidated.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

DEV_KEY_ENV = "UNIIMENTE_WITNESS_KEY"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def sha256_obj(obj) -> str:
    return "sha256:" + hashlib.sha256(_canon(obj)).hexdigest()


#: v2 fields that are dropped from the signed payload when unset. Kept here
#: rather than derived from `witness_v2` so this module stays importable on its
#: own; `test_witness_v2_migration.py` asserts the two agree.
_V2_OPTIONAL = frozenset({
    "witness_version", "evidence_confidence", "consequence_class",
    "exposure_ceiling_usd", "predicted_success_probability",
})


@dataclass
class CommitWitness:
    """The signed binding between an authorization and one exact effect."""
    witness_id: str
    issued_at: str
    actor: str                    # machine passport id (this exact machine)
    legal_principal: str          # this exact entity
    action_class: str
    payload_hash: str             # this exact payload
    target: str                   # this exact target
    policy_version: str           # this exact law (policy)
    constitution_hash: str        # this exact law (constitution)
    grant_id: str                 # this exact permission (authority)
    capability: str               # current capability used
    budget_reservation_id: str    # current budget bound
    expected_outcome: str         # this exact result, predicted
    evidence_refs: list[str]      # this exact evidence
    signature: str                # HMAC-SHA256 over all of the above

    # -- Witness contract v2 -------------------------------------------------
    # Authorised by FOUNDER-RULING-2026-08-23 (CONTRADICTION-0002 unblocked the
    # file; CONTRADICTION-0003 settled which confidences exist). Every one
    # defaults to None and None means *absent*, so a witness that sets none of
    # them is byte-identical to a v1 witness and its signature still verifies.
    witness_version: int | None = None
    #: How well-evidenced the decision to act was. Governs Gate admission.
    evidence_confidence: float | None = None
    #: What class of consequence was authorised.
    consequence_class: str | None = None
    #: The effective ceiling this action ran under — not a reservation id.
    exposure_ceiling_usd: float | None = None
    #: The preregistered forecast, for Bridge D to score against reality.
    #: Absent for the majority of actions, which are not experiments.
    predicted_success_probability: float | None = None

    def unsigned(self) -> dict:
        """The signed payload. Absent v2 facts are dropped, never sent as null.

        This is what keeps v1 byte-compatibility exact: a witness with no v2
        fields set canonicalises to precisely the bytes v1 signed, so every
        historical signature keeps verifying without re-signing anything. It is
        also what makes `UNRECORDED` honest downstream — a dropped field reads
        as absent, while a `null` would read as a recorded nothing.
        """
        d = asdict(self)
        d.pop("signature")
        return {k: v for k, v in d.items()
                if not (v is None and k in _V2_OPTIONAL)}


class WitnessSigner:
    """Signs and verifies Commit Witnesses.

    Key discipline: the signing key comes from the environment. A missing
    key is a hard refusal (fail closed), never an unsigned witness. The
    dev fallback exists only when UNIIMENTE_ENV=development.
    """

    def __init__(self, key: bytes | None = None, env: str | None = None):
        self.env = env or os.environ.get("UNIIMENTE_ENV", "production")
        if key is not None:
            self.key = key
        elif self.env == "development":
            self.key = b"uniimente-dev-witness-key"  # dev only; production requires a real key
        else:
            k = os.environ.get(DEV_KEY_ENV)
            if not k:
                raise RuntimeError(f"{DEV_KEY_ENV} required outside development")
            self.key = k.encode("utf-8")

    def sign(self, witness: CommitWitness) -> CommitWitness:
        witness.signature = "hmac-sha256:" + hmac.new(
            self.key, _canon(witness.unsigned()), hashlib.sha256).hexdigest()
        return witness

    def verify(self, witness: CommitWitness) -> bool:
        expected = "hmac-sha256:" + hmac.new(
            self.key, _canon(witness.unsigned()), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, witness.signature)


def new_witness(*, actor: str, legal_principal: str, action_class: str,
                payload: dict, target: str, policy_version: str,
                constitution_hash: str, grant_id: str, capability: str,
                budget_reservation_id: str, expected_outcome: str,
                evidence_refs: list[str],
                witness_version: int | None = None,
                evidence_confidence: float | None = None,
                consequence_class: str | None = None,
                exposure_ceiling_usd: float | None = None,
                predicted_success_probability: float | None = None
                ) -> CommitWitness:
    """Build a witness. Omitting every v2 argument produces a v1 record.

    The v2 arguments are keyword-only and default to None so that no existing
    caller changes behaviour by being recompiled, and so that a caller which
    does not actually hold a value cannot supply one by accident. A writer that
    passed zeros here to look modern would be fabricating evidence.
    """
    import uuid
    return CommitWitness(
        witness_id=str(uuid.uuid4()),
        issued_at=_now(),
        actor=actor,
        legal_principal=legal_principal,
        action_class=action_class,
        payload_hash=sha256_obj(payload),
        target=target,
        policy_version=policy_version,
        constitution_hash=constitution_hash,
        grant_id=grant_id,
        capability=capability,
        budget_reservation_id=budget_reservation_id,
        expected_outcome=expected_outcome,
        evidence_refs=list(evidence_refs),
        signature="",
        witness_version=witness_version,
        evidence_confidence=evidence_confidence,
        consequence_class=consequence_class,
        exposure_ceiling_usd=exposure_ceiling_usd,
        predicted_success_probability=predicted_success_probability,
    )
