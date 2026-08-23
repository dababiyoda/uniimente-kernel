"""One workload's own identity: its key, its certificate, its trust anchor.

Holding a `WorkloadIdentity` means being able to *prove* you are that SPIFFE ID.
It says nothing about what that ID may do, and there is no field here that
could.

## The temp-file materialisation, stated plainly

Python's `ssl` module loads certificate chains from paths on disk, not from
memory — `load_cert_chain` has no bytes-accepting form. So `materialise()`
writes the PEMs into a private temporary directory for exactly the duration of
a handshake and removes them afterwards.

This is a real limitation and it is recorded rather than glossed: for a moment,
a private key exists on the filesystem at mode 0600 inside a 0700 directory.
That is acceptable for consequence-inert internal use and would not be
acceptable for production key custody, where the key belongs in a keystore the
process cannot read wholesale. Named in `blueprint/registry.py` under #7.
"""
from __future__ import annotations

import contextlib
import os
import stat
import tempfile
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class WorkloadIdentity:
    """A workload's private identity material.

    Frozen: a workload cannot edit its own SPIFFE ID after issuance. That would
    be self-assigned identity, which is the thing the shared HMAC key permitted.
    """

    spiffe_id: str
    certificate_pem: bytes
    #: Private. Never leaves this process, never travels in a message, and is
    #: never what a peer verifies against.
    private_key_pem: bytes
    #: Public CA material. Safe to distribute — it confers verification, not
    #: signing.
    trust_bundle_pem: bytes
    serial: int

    def __repr__(self) -> str:
        """Redacted. A private key rendered into a log or a pytest failure
        banner has left the process, whatever the docstring above says."""
        return (f"WorkloadIdentity(spiffe_id={self.spiffe_id!r}, "
                f"serial={self.serial}, private_key_pem=<redacted>)")

    @contextlib.contextmanager
    def materialise(self) -> Iterator[tuple[str, str]]:
        """Yield `(chain_path, trust_path)` for the life of the block.

        The directory is created 0700 and both files 0600 before any secret is
        written — created restricted, not created and then restricted, so there
        is no window in which the key is readable.
        """
        directory = tempfile.mkdtemp(prefix="uniimente-pki-")
        os.chmod(directory, stat.S_IRWXU)
        chain = os.path.join(directory, "chain.pem")
        trust = os.path.join(directory, "trust.pem")
        try:
            for path, payload in (
                    (chain, self.certificate_pem + self.private_key_pem),
                    (trust, self.trust_bundle_pem)):
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as fh:
                    fh.write(payload)
            yield chain, trust
        finally:
            for path in (chain, trust):
                with contextlib.suppress(FileNotFoundError):
                    os.remove(path)
            with contextlib.suppress(OSError):
                os.rmdir(directory)
