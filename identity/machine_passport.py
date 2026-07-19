"""Machine passports: SPIFFE-style workload identity for every process.

Layer 2 of the stack (Machine Identity and Authority).

The separation this enforces (doctrine, non-negotiable):
    identity  !=  authority  !=  legal responsibility  !=  capability
    !=  budget  !=  consequence.

A service proving its identity does NOT automatically receive permission.
A valid agent signature does NOT make the agent sovereign. A passport
therefore carries no authority at all: authority arrives only through a
CapabilityGrant evaluated against compiled constitutional policy.

SPIRE-style: identities are short-lived and issued only when observed
properties match registered conditions (here: creator, owner organ, legal
principal, declared capability need, budget ceiling, consequence class,
and a mandatory expiry).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta

NAMESPACE = "spiffe://uniimente.internal"

PASSPORT_KINDS = ("process", "agent", "workflow", "organ", "connector", "venture_cell")
CONSEQUENCE_CLASSES = ("read_only", "internal_write", "external_contact", "financial", "irreversible")


class PassportError(ValueError):
    pass


@dataclass
class MachinePassport:
    """What UNIIMENTE always knows about any acting thing."""
    passport_id: str            # spiffe://uniimente.internal/<kind>/<uuid>
    kind: str
    creator: str                # passport_id or 'alfonso' of whoever created it
    owner_organ: str            # which organization/organ owns it
    legal_principal: str        # which entity bears liability (never UNIIMENTE)
    declared_capabilities: list[str]   # what it needs; NOT what it may do
    budget_ceiling_usd: float
    consequence_class: str
    issued_at: str              # RFC 3339 UTC
    expires_at: str             # mandatory; short-lived
    revoked: bool = False
    revoked_at: str | None = None
    revocation_reason: str | None = None

    @property
    def authority(self) -> None:
        # Identity never carries authority. This property exists to make
        # the separation explicit and is always None.
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class PassportRegistry:
    """Issues, verifies, and revokes short-lived machine passports."""

    def __init__(self, max_ttl_seconds: int = 3600):
        self.max_ttl = timedelta(seconds=max_ttl_seconds)
        self._passports: dict[str, MachinePassport] = {}

    def issue(self, *, kind: str, creator: str, owner_organ: str, legal_principal: str,
              declared_capabilities: list[str], budget_ceiling_usd: float,
              consequence_class: str, ttl_seconds: int | None = None) -> MachinePassport:
        if kind not in PASSPORT_KINDS:
            raise PassportError(f"unknown passport kind {kind!r}")
        if legal_principal == "UNIIMENTE":
            raise PassportError("UNIIMENTE may never be a legal principal")
        if consequence_class not in CONSEQUENCE_CLASSES:
            raise PassportError(f"unknown consequence class {consequence_class!r}")
        if budget_ceiling_usd < 0:
            raise PassportError("budget ceiling may not be negative")
        ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else self.max_ttl
        if ttl > self.max_ttl:
            raise PassportError("passport TTL exceeds registry maximum (identities are short-lived)")
        now = _now()
        p = MachinePassport(
            passport_id=f"{NAMESPACE}/{kind}/{uuid.uuid4()}",
            kind=kind, creator=creator, owner_organ=owner_organ,
            legal_principal=legal_principal,
            declared_capabilities=list(declared_capabilities),
            budget_ceiling_usd=float(budget_ceiling_usd),
            consequence_class=consequence_class,
            issued_at=_rfc3339(now), expires_at=_rfc3339(now + ttl),
        )
        self._passports[p.passport_id] = p
        return p

    def verify(self, passport_id: str, *, at: datetime | None = None) -> tuple[bool, str]:
        """Identity check only. Never an authorization decision."""
        p = self._passports.get(passport_id)
        if p is None:
            return False, "unknown_identity"
        if p.revoked:
            return False, f"revoked:{p.revocation_reason or 'unspecified'}"
        if (at or _now()) >= _parse(p.expires_at):
            return False, "expired"
        return True, "identity_verified"

    def inspect(self, passport_id: str) -> dict:
        """The six questions UNIIMENTE can always answer about an actor."""
        p = self._passports.get(passport_id)
        if p is None:
            raise PassportError("unknown_identity")
        return {
            "what_it_is": f"{p.kind}:{p.passport_id}",
            "who_created_it": p.creator,
            "which_organization_owns_it": p.owner_organ,
            "what_it_may_do": "nothing by identity alone; see capability grants",
            "which_entity_bears_liability": p.legal_principal,
            "when_its_authority_expires": p.expires_at,
        }

    def revoke(self, passport_id: str, *, reason: str, revoker: str) -> None:
        p = self._passports.get(passport_id)
        if p is None:
            raise PassportError("unknown_identity")
        if p.revoked:
            return
        p.revoked = True
        p.revoked_at = _rfc3339(_now())
        p.revocation_reason = f"{reason} (by {revoker})"

    def to_dict(self, passport_id: str) -> dict:
        return asdict(self._passports[passport_id])
