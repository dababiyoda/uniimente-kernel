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

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta

NAMESPACE = "spiffe://uniimente.internal"

PASSPORT_KINDS = ("process", "agent", "workflow", "organ", "connector", "venture_cell")
CONSEQUENCE_CLASSES = ("read_only", "internal_write", "external_contact", "financial", "irreversible")
# A running body issues a passport per governed act. Unexpired ones stay. Expired ones stay
# only inside this audit window; older expirations fold into a chain head. Revocations never fold.
MAX_LIVE = 256
MAX_EXPIRED_AUDIT = 1024
_FOLDED_GENESIS = "sha256:" + "0" * 64


def _fold_head(previous: str, passport_id: str, expires_at: str) -> str:
    raw = json.dumps(
        {"expires_at": expires_at, "passport_id": passport_id, "prev": previous},
        sort_keys=True, separators=(",", ":"),
    ).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


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
    """Issues, verifies, and revokes short-lived machine passports.

    At most ``max_live`` unexpired, unrevoked passports are issued. Expired identities
    stay addressable until ``max_expired_audit`` of them have accumulated; older ones
    leave the map and extend ``retention()["folded_head"]``. A revocation stays in the
    map for the life of the registry: forgetting one would let a compromised identity
    read as merely unknown.
    """

    def __init__(self, max_ttl_seconds: int = 3600, *, max_live: int = MAX_LIVE,
                 max_expired_audit: int = MAX_EXPIRED_AUDIT):
        if max_live < 1 or max_expired_audit < 1:
            raise PassportError("passport retention bounds must be positive")
        self.max_ttl = timedelta(seconds=max_ttl_seconds)
        self.max_live = max_live
        self.max_expired_audit = max_expired_audit
        self._passports: dict[str, MachinePassport] = {}
        self._expired: dict[str, MachinePassport] = {}
        self._expired_order: list[str] = []
        self._folded = {"count": 0, "head": _FOLDED_GENESIS}

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
        self.retain()
        if self.retention()["live"] >= self.max_live:
            raise PassportError("live passport ceiling reached")
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
        if passport_id in self._expired:
            return False, "expired"
        p = self._passports.get(passport_id)
        if p is None:
            return False, "unknown_identity"
        if p.revoked:
            return False, f"revoked:{p.revocation_reason or 'unspecified'}"
        if (at or _now()) >= _parse(p.expires_at):
            return False, "expired"
        return True, "identity_verified"

    def retain(self, *, at: datetime | None = None) -> dict:
        """Move expired passports out of the live map. Ones past the audit window fold
        into the chain head. A revoked passport stays, whole, for the life of the registry."""
        now = at or _now()
        for pid, p in list(self._passports.items()):
            if p.revoked:
                continue
            if now >= _parse(p.expires_at):
                self._passports.pop(pid)
                self._remember_expired(p)
        while len(self._expired_order) > self.max_expired_audit:
            pid = self._expired_order.pop(0)
            expired = self._expired.pop(pid)
            self._folded["count"] += 1
            self._folded["head"] = _fold_head(self._folded["head"], pid, expired.expires_at)
        return self.retention()

    def _remember_expired(self, passport: MachinePassport) -> None:
        if passport.passport_id in self._expired or passport.revoked:
            return
        self._expired[passport.passport_id] = passport
        self._expired_order.append(passport.passport_id)

    def _find(self, passport_id: str) -> MachinePassport | None:
        return self._passports.get(passport_id) or self._expired.get(passport_id)

    def retention(self) -> dict:
        return {
            "live": sum(1 for p in self._passports.values() if not p.revoked),
            "expired_retained": len(self._expired),
            "revoked": sum(1 for p in self._passports.values() if p.revoked),
            "folded": self._folded["count"],
            "folded_head": self._folded["head"],
            "max_live": self.max_live,
            "max_expired_audit": self.max_expired_audit,
        }

    def inspect(self, passport_id: str) -> dict:
        """The six questions UNIIMENTE can always answer about an actor still on record."""
        p = self._find(passport_id)
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
        note = f"{reason} (by {revoker})"
        expired = self._expired.pop(passport_id, None)
        if expired is not None:
            self._expired_order.remove(passport_id)
            self._passports[passport_id] = expired
        p = self._passports.get(passport_id)
        if p is None:
            raise PassportError("unknown_identity")
        if p.revoked:
            return
        p.revoked = True
        p.revoked_at = _rfc3339(_now())
        p.revocation_reason = note

    def to_dict(self, passport_id: str) -> dict:
        p = self._find(passport_id)
        if p is None:
            raise PassportError("unknown_identity")
        return asdict(p)
