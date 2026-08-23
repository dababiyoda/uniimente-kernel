"""The smallest sufficient PKI: one asymmetric identity per workload.

Ratified by the founder on 2026-08-22 (FOUNDER-RULING-2026-08-22, technologies
#7 and #26): *"The shared HMAC key is no longer acceptable as the institutional
trust boundary."*

## What was wrong with the shared key

`adapters/bridge_transport.py` and its two peer mirrors authenticate with
HMAC-SHA256 over one secret, `WEALTHMACHINE_SIGNING_KEY`. That construction is
sound for integrity and useless for isolation: every participant needs the
secret to *verify*, so every participant can also *sign*. Any holder can claim
any identity in `KNOWN_IDENTITIES`, and no receiver can tell the difference.
The kernel's own module says so in its docstring — it recognises a *claimed*
identity, not an isolated one.

Asymmetric identity removes the symmetry that caused it. A workload signs with a
private key nobody else holds; peers verify with a public certificate that
grants no signing power. Impersonation stops being a matter of trust.

## What this is, and deliberately is not

The ruling said to start with the smallest sufficient PKI and not to install
SPIRE for architectural aesthetics. So: one self-signed root, per-workload
keypairs, SPIFFE URI SANs, expiry, rotation, a serial-based revocation list.
No intermediates, no OCSP, no attestation daemon, no node agent. Those are
answers to problems this institution does not yet have, and every one of them
would be another component claiming to be verified while never having run.

## Identity is not authority. This is the load-bearing rule.

> A valid certificate proves which workload is speaking; it does not create a
> capability, budget, approval, role, grant, or execution right.

`PeerIdentity` carries who, which serial, valid when, issued by whom — and
nothing else. There is no field for what the peer may do, because there is no
answer to that question at this layer. A verified peer still routes through the
Consequence Gate, still needs a capability grant, still needs human approval for
anything reserved.

`test_pki_identity_is_not_authority.py` asserts this structurally rather than
trusting the docstring: the package may not import `policy`, `authority`,
`capabilities`, `capital` or `constitution`, and `PeerIdentity` may not grow a
field that reads as a permission.

## Consequence-inert by construction

The handshake runs over `ssl.MemoryBIO` — a complete, real TLS 1.3 exchange with
real chain validation, in memory. No socket, no bind, no listener, no connect.
That is not a simulation of TLS; it is TLS, with the transport removed. The
founder's standing constraint forbids opening a network surface, and proving the
mechanism never required one.

What this therefore does NOT prove: that any real peer speaks it, that a real
network path exists, or that certificate distribution and key custody are
solved. Those are named in `blueprint/registry.py` under #7 and #26 and remain
open.
"""
from __future__ import annotations

from identity.pki.ca import CertificateAuthority, IssuedIdentity
from identity.pki.errors import (
    CertificateExpired,
    CertificateRevoked,
    HandshakeRefused,
    IdentityError,
    UntrustedIssuer,
)
from identity.pki.handshake import PeerIdentity, mutual_tls
from identity.pki.revocation import RevocationList
from identity.pki.workload import WorkloadIdentity

__all__ = [
    "CertificateAuthority",
    "CertificateExpired",
    "CertificateRevoked",
    "HandshakeRefused",
    "IdentityError",
    "IssuedIdentity",
    "PeerIdentity",
    "RevocationList",
    "UntrustedIssuer",
    "WorkloadIdentity",
    "mutual_tls",
]
