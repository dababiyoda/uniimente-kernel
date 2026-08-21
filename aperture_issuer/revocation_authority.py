"""Publishing signed revocation snapshots. ISSUER DISTRIBUTION ONLY.

Only the canonical issuer signs snapshots. An organ consumes them through
`aperture.revocation.RevocationState`, which verifies but cannot publish.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from aperture.certificate import rfc3339
from aperture.revocation import RevocationSnapshot

from .signing import SigningProvider


class RevocationAuthority:
    """Kernel side. Publishes signed snapshots. Only the issuer signs them."""

    def __init__(self, signer: SigningProvider):
        self.signer = signer
        self._epoch = 0
        self._certs: set[str] = set()
        self._actors: set[str] = set()
        self._organs: set[str] = set()
        self._workloads: set[str] = set()
        self._keys: set[str] = set()

    def revoke_certificate(self, cid: str) -> None:
        self._certs.add(cid)

    def revoke_actor(self, a: str) -> None:
        self._actors.add(a)

    def revoke_organ(self, o: str) -> None:
        self._organs.add(o)

    def revoke_workload(self, w: str) -> None:
        self._workloads.add(w)

    def revoke_key(self, k: str) -> None:
        self._keys.add(k)

    def publish(self, *, now: Optional[datetime] = None) -> RevocationSnapshot:
        self._epoch += 1
        snap = RevocationSnapshot(
            epoch=self._epoch,
            issued_at=rfc3339(now or datetime.now(timezone.utc)),
            revoked_certificates=tuple(sorted(self._certs)),
            revoked_actors=tuple(sorted(self._actors)),
            revoked_organs=tuple(sorted(self._organs)),
            revoked_workloads=tuple(sorted(self._workloads)),
            revoked_keys=tuple(sorted(self._keys)),
            algorithm=self.signer.algorithm, key_id=self.signer.key_id)
        snap.signature = self.signer.sign(snap.signing_input())
        return snap


