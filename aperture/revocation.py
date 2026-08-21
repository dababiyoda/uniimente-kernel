"""Revocation for offline-verifiable authority.

The certificate's strength is that an effector can verify it without reaching
the Kernel. That same property is its hardest problem: an effector that never
calls home cannot learn that authority was withdrawn.

Three models were evaluated (docs/authority/REVOCATION_MODEL.md). The selected
RC1 model is a HYBRID, because no single model covers the full consequence
range:

  A  short-lived certificates      bounds exposure everywhere, cheap, but a
                                   120s TTL is still 120s of exposure
  B  signed revocation snapshots   an effector holds a signed, versioned,
                                   monotonic revocation epoch it can check
                                   offline, but the snapshot itself goes stale
  C  online validation             zero window, but reintroduces the
                                   availability hazard that motivated the
                                   whole architecture

Hybrid: A everywhere, B distributed to every effector, and C's freshness
requirement expressed as a MAXIMUM STALENESS per consequence class. The organ
never has to call the Kernel; it has to hold a snapshot no older than the class
permits. Low-consequence actions tolerate a day. Irreversible actions tolerate
nothing and escalate to a human.

The asymmetry is deliberate: staleness is permissive at the bottom and
fail-closed at the top. An effector that cannot prove its revocation state is
fresh enough MUST NOT perform a financial or irreversible action.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from .certificate import (CertificateError, canonical_json, rfc3339,
                          sha256_hex)
from .verification import VerificationRegistry
from . import manifest

PERMIT = "permit"
REFUSE = "refuse"
LOCAL_CONTAINMENT = "local_containment"
HUMAN_ESCALATION = "human_escalation"


class RevocationRefusal(CertificateError):
    pass


class StaleRevocationState(CertificateError):
    pass


class RevocationEscalation(CertificateError):
    """High-consequence action cannot proceed without a human."""


@dataclass
class RevocationSnapshot:
    """A signed, versioned statement of what is revoked as of an instant.

    Monotonic `epoch` defeats rollback: an effector that has seen epoch 7 must
    refuse a snapshot claiming epoch 5, or an attacker could replay an old
    snapshot to un-revoke something.
    """
    epoch: int
    issued_at: str
    revoked_certificates: tuple[str, ...] = ()
    revoked_actors: tuple[str, ...] = ()
    revoked_organs: tuple[str, ...] = ()
    revoked_workloads: tuple[str, ...] = ()
    revoked_keys: tuple[str, ...] = ()
    algorithm: str = "ed25519"
    key_id: str = ""
    signature: str = ""

    def body(self) -> dict:
        return {
            "epoch": self.epoch,
            "issued_at": self.issued_at,
            "revoked_certificates": sorted(self.revoked_certificates),
            "revoked_actors": sorted(self.revoked_actors),
            "revoked_organs": sorted(self.revoked_organs),
            "revoked_workloads": sorted(self.revoked_workloads),
            "revoked_keys": sorted(self.revoked_keys),
        }

    def signing_input(self) -> bytes:
        return canonical_json({
            "snapshot_hash": "sha256:" + sha256_hex(canonical_json(self.body())),
            "algorithm": self.algorithm,
            "key_id": self.key_id,
        })

    def age_seconds(self, now: Optional[datetime] = None) -> float:
        now = now or datetime.now(timezone.utc)
        issued = datetime.fromisoformat(self.issued_at.replace("Z", "+00:00"))
        return max(0.0, (now - issued).total_seconds())


class RevocationState:
    """Effector side. Holds the newest snapshot it has seen and checks freshness."""

    def __init__(self, registry: VerificationRegistry):
        self.registry = registry
        self.snapshot: Optional[RevocationSnapshot] = None

    def accept(self, snap: RevocationSnapshot) -> None:
        ok = self.registry.verify(snap.key_id, snap.signing_input(),
                                  snap.signature, algorithm=snap.algorithm)
        if not ok:
            raise RevocationRefusal(
                "revocation snapshot signature does not verify; refusing to "
                "accept an unsigned view of what is revoked",
                code="snapshot_bad_signature")
        if self.snapshot is not None and snap.epoch < self.snapshot.epoch:
            raise RevocationRefusal(
                f"snapshot epoch {snap.epoch} is older than the epoch already "
                f"seen ({self.snapshot.epoch}); refusing a rollback that would "
                "un-revoke authority", code="snapshot_rollback")
        self.snapshot = snap

    def check(self, cert, *, now: Optional[datetime] = None) -> None:
        """Apply the manifest's policy for this certificate's consequence class."""
        policy = manifest.revocation_policy_for(cert.consequence_class)
        skew = float(manifest.revocation_policy().get(
            "clock_skew_tolerance_seconds", 0))
        max_stale = float(policy["maximum_staleness_seconds"])
        on_stale = policy["on_stale_or_unavailable"]

        if self.snapshot is None:
            self._apply(on_stale, cert,
                        "no revocation snapshot has ever been received")
            return

        age = self.snapshot.age_seconds(now)
        if age > max_stale + skew:
            self._apply(on_stale, cert,
                        f"revocation snapshot is {age:.0f}s old; class "
                        f"{cert.consequence_class!r} permits {max_stale:.0f}s")
            return

        s = self.snapshot
        if cert.key_id in s.revoked_keys:
            raise RevocationRefusal(
                f"issuer key {cert.key_id!r} is revoked; every certificate it "
                "signed is refused", code="issuer_key_revoked")
        if cert.authority_record_id in s.revoked_certificates:
            raise RevocationRefusal("certificate is revoked",
                                    code="certificate_revoked")
        if cert.actor_id in s.revoked_actors:
            raise RevocationRefusal(f"actor {cert.actor_id!r} is revoked",
                                    code="actor_revoked")
        if cert.organ_id in s.revoked_organs:
            raise RevocationRefusal(f"organ {cert.organ_id!r} is revoked",
                                    code="organ_revoked")
        if cert.workload_identity in s.revoked_workloads:
            raise RevocationRefusal(
                f"workload {cert.workload_identity!r} is revoked; a replaced "
                "workload does not inherit authority",
                code="workload_revoked")

    def _apply(self, action: str, cert, why: str) -> None:
        if action == PERMIT:
            return
        if action == HUMAN_ESCALATION:
            raise RevocationEscalation(
                f"{why}. Consequence class {cert.consequence_class!r} requires a "
                "human decision when revocation state cannot be shown fresh.",
                code="revocation_human_escalation")
        if action == LOCAL_CONTAINMENT:
            raise RevocationRefusal(f"{why}; entering local containment",
                                    code="revocation_local_containment")
        raise StaleRevocationState(
            f"{why}. Class {cert.consequence_class!r} fails closed on stale or "
            "unavailable revocation state.", code="revocation_stale")


def max_ttl_for(consequence_class: str) -> int:
    return int(manifest.revocation_policy_for(
        consequence_class)["max_certificate_ttl_seconds"])
