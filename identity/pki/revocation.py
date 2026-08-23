"""Serial-based revocation: the case expiry alone cannot answer.

Expiry handles the ordinary lifecycle. Revocation handles the emergency — a key
believed compromised before its natural end, an organ detached, a workload
retired early.

## Why a set of serials rather than a signed X.509 CRL

An X.509 CRL is the right answer once revocation data crosses a trust boundary,
because the consumer needs to verify the list came from the CA. Here the list is
passed directly to `mutual_tls` inside one process, so a signature would be
checked by the same code that constructed it — ceremony that proves nothing.
When revocation has to travel between organs, this becomes a signed CRL or OCSP,
and that is recorded as open under #7 rather than pretended away.

## Revocation is permanent

There is no `unrevoke`. A serial is revoked because its key is no longer
trustworthy, and a key does not become trustworthy again. Recovery is issuing a
new certificate with a new keypair — which `CertificateAuthority.issue` already
does, since it never reuses a key.
"""
from __future__ import annotations

import datetime


class RevocationList:
    """Serials that must be refused even though their certificates validate."""

    def __init__(self) -> None:
        self._revoked: dict[int, tuple[datetime.datetime, str]] = {}

    def revoke(self, serial: int, *, reason: str = "") -> None:
        """Revoke a serial. Idempotent, and the first reason is kept.

        Re-revoking must not overwrite the original reason: the first one
        records why trust was actually withdrawn, and a later blanket sweep
        would otherwise erase it.
        """
        if serial not in self._revoked:
            self._revoked[serial] = (
                datetime.datetime.now(datetime.timezone.utc), reason)

    def is_revoked(self, serial: int) -> bool:
        return serial in self._revoked

    def reason(self, serial: int) -> str:
        entry = self._revoked.get(serial)
        return entry[1] if entry else ""

    def revoked_at(self, serial: int) -> datetime.datetime | None:
        entry = self._revoked.get(serial)
        return entry[0] if entry else None

    def __len__(self) -> int:
        return len(self._revoked)

    def __contains__(self, serial: object) -> bool:
        return isinstance(serial, int) and serial in self._revoked
