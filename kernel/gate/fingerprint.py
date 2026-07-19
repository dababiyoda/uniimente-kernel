"""Intent fingerprinting — Hard Rule 2: approvals bind to the intent fingerprint.

ANY change to payload, target, budget, legal_principal, policy_version or
consequence_class produces a different fingerprint and therefore invalidates
every approval, grant and witness bound to it. The kernel binds strictly:
actor_id, organ_id, action_type, resource and expected_outcome are included as
well, so cross-organ capability use is also a fingerprint mismatch (fail
closed on any ambiguity, Hard Rule 4).

Determinism (Hard Rule 5): the fingerprint is sha256 over canonical JSON.
"""
from __future__ import annotations

from ..contracts.action import ActionIntent
from ..crypto.hashing import canonical_json, sha256_hex


def intent_fingerprint(intent: ActionIntent, policy_version: str | None = None) -> str:
    """sha256 of the canonical form of the intent's binding fields."""
    body = {
        "actor_id": intent.actor_id,
        "organ_id": intent.organ_id,
        "legal_principal": intent.legal_principal,
        "action_type": intent.action_type,
        "resource": intent.resource,
        "target": intent.target,
        "payload": intent.payload,
        "budget": intent.payload.get("budget"),
        "consequence_class": intent.consequence_class,
        "expected_outcome": intent.expected_outcome,
        "policy_version": policy_version,
    }
    return sha256_hex(canonical_json(body).encode("utf-8"))
