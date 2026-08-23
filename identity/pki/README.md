# Asymmetric workload identity

Ratified 2026-08-22 under `FOUNDER-RULING-2026-08-22` (technologies #7 and #26).

## Why this document is here and not in `service-identities.yaml`

The obvious place to record this was `identity/service-identities.yaml`, next to
the SPIFFE namespace it implements. That was the first attempt, and the test
suite refused it.

`identity/service-identities.yaml` is one of the institution's **continuity
artifacts**, pinned by SHA-256 in `evolution/repair/spec.CONTINUITY_ARTIFACT_SHA256`
alongside the Constitution and the authority matrix. The Package 3 experiment
uses those pins to prove that governance and continuity held while a component
was deliberately removed. Editing one to document a new feature would have
invalidated that proof, and updating the pin to match would have rewritten
historical evidence — which the same ruling forbids.

So the namespace file stays byte-identical and this file carries the addition.
Recorded because the near-miss is the useful part: the preservation rule caught
an edit that looked purely additive.

## What this is

The smallest sufficient PKI. One self-signed root, one independent keypair per
workload, SPIFFE URI SANs, expiry, rotation, a serial-based revocation list. No
intermediates, no OCSP, no SPIRE — the ruling said not to install a large
infrastructure for architectural aesthetics if a smaller one proves the
mechanism.

```python
from identity.pki import CertificateAuthority, mutual_tls

ca = CertificateAuthority()
server, _ = ca.issue("spiffe://uniimente.internal/kernel/action-gateway")
client, issued = ca.issue("spiffe://uniimente.internal/organ/daleobanks/bridge")

seen_server, seen_client = mutual_tls(client, server)
seen_client.spiffe_id   # read from the validated certificate, never from a claim
```

## The defect it answers

`adapters/bridge_transport.py` and its two peer mirrors authenticate with
HMAC-SHA256 over one shared secret. That is sound for integrity and useless for
isolation: every participant needs the secret to *verify*, so every participant
can also *sign*. Any holder can claim any known identity, and no receiver can
tell. The kernel mirror's own docstring says so — it recognises a *claimed*
identity.

`test_bridge_transport_no_downgrade.py::test_any_holder_of_the_shared_secret_can_claim_any_known_identity`
demonstrates the impersonation succeeding, and the test immediately after it
shows the same attack failing against this package.

## Identity is not authority

> A valid certificate proves which workload is speaking; it does not create a
> capability, budget, approval, role, grant, or execution right.

`PeerIdentity` carries `spiffe_id`, `serial`, `not_before`, `not_after`,
`issuer`. Nothing else, and the absence is enforced:
`test_pki_identity_is_not_authority.py` refuses any import of `policy`,
`authority`, `capabilities`, `capital`, `constitution`, `provenance` or
`embassy` anywhere in this package, and refuses any authority-shaped field or
property on `PeerIdentity`. A verified peer still crosses the Consequence Gate.

## What it does not prove

Stated here rather than left to inference, and mirrored in
`blueprint/registry.py` under #7 and #26:

- **No transport.** The handshake runs over `ssl.MemoryBIO` — genuine TLS 1.3
  with genuine chain validation and no socket, because opening a network
  surface remains founder-gated. No real peer has spoken it.
- **Not adopted.** No bridge, gate or organ calls `mutual_tls`. The live trust
  boundary is unchanged. #26 therefore stays at `BUILT`, not `EXERCISED`:
  `EXERCISED` means the technology runs inside the institution's own loop, and
  passing tests are not adoption.
- **Key custody is unsolved.** `WorkloadIdentity.materialise()` writes the
  private key to a 0600 file in a 0700 directory for the duration of a
  handshake, because Python's `ssl` loads chains from paths and not from memory.
  Acceptable for consequence-inert internal use; not acceptable for production.
- **Revocation does not travel.** An in-process serial set, not a signed CRL or
  OCSP. Sufficient until revocation data crosses a trust boundary.

## Attacks covered

Every item the ruling named, in `tests/unit/test_pki_mutual_tls.py`:
impersonation by a foreign CA minting the kernel's exact SPIFFE ID; identity
taken from the certificate rather than any claim; expired client and expired
server; revoked client and revoked server; rotation with an independent key and
retirement of the old serial; replay of a captured certificate without its key;
downgrade to one-way TLS; and cross-organ handshakes in both directions. Each
refusal is paired with the positive control that would otherwise have succeeded.

## Legacy HMAC

Preserved as an explicit development compatibility mode, per the ruling. It now
fails closed: an unset `WEALTHMACHINE_SIGNING_KEY` used to make
`verify_headers` return success carrying the caller's claimed identity
unverified — absence of configuration silently disabled authentication. Running
unsigned now requires both `require_signature=False` and
`UNIIMENTE_BRIDGE_DEV_UNSIGNED=1`, and every returned record carries
`identity_isolated: "false"` — including the signed path, because a valid HMAC
proves possession of the shared secret and not which holder sent it.
