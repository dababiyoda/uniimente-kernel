"""The legacy HMAC transport may survive only as an explicit dev mode.

FOUNDER-RULING-2026-08-22, ratifying #7 and #26:

> If legacy HMAC compatibility must temporarily survive, it must be an explicit
> development compatibility mode, fail closed, never auto-downgrade, and never
> be mistaken for mutually isolated identity.

Three separate requirements, tested separately below, because a module can
satisfy any two and fail the third.

## The defect this closes

`verify_headers` derived `must_sign = bool(key)`. An unset
`WEALTHMACHINE_SIGNING_KEY` therefore did not fail — it returned SUCCESS
carrying the caller's *claimed* identity, unverified. Absence of configuration
silently disabled authentication.

That is worse than an off switch, because nobody chose it. A new deployment that
had simply not set the variable yet would report a working trust boundary while
accepting any identity from anyone. `bridges/signal_to_venture.py` was running
through exactly that path in any environment without the key set.
"""
from __future__ import annotations

import json

import pytest

from adapters import bridge_transport as bt


@pytest.fixture(autouse=True)
def _no_ambient_config(monkeypatch):
    """Neither variable set, which is the state the defect lived in."""
    monkeypatch.delenv(bt.SIGNING_KEY_ENV, raising=False)
    monkeypatch.delenv(bt.DEV_UNSIGNED_ENV, raising=False)


def _headers(identity: str = "daleobanks") -> dict[str, str]:
    return {bt.H_IDENTITY: identity, bt.H_SCHEMA: "1.1"}


# ------------------------------------------------------------- fail closed
def test_a_missing_signing_key_refuses_instead_of_succeeding_unsigned():
    """The core regression. This call used to return a verified-looking dict."""
    with pytest.raises(bt.BridgeSecurityError, match="no signing key configured"):
        bt.verify_headers(_headers(), b"{}", nonce_cache=bt.NonceCache())


def test_the_refusal_names_the_two_ways_out_and_neither_is_automatic():
    """An error that does not say what to do next gets worked around badly."""
    with pytest.raises(bt.BridgeSecurityError) as caught:
        bt.verify_headers(_headers(), b"{}", nonce_cache=bt.NonceCache())
    message = str(caught.value)
    assert bt.SIGNING_KEY_ENV in message
    assert bt.DEV_UNSIGNED_ENV in message
    assert "never disabled by the absence of configuration" in message


def test_asking_for_unsigned_without_the_opt_in_is_still_refused():
    """`require_signature=False` alone is not enough. Two deliberate acts."""
    with pytest.raises(bt.BridgeSecurityError, match=bt.DEV_UNSIGNED_ENV):
        bt.verify_headers(_headers(), b"{}", nonce_cache=bt.NonceCache(),
                          require_signature=False)


def test_an_unknown_identity_cannot_reach_the_unsigned_path_by_omission():
    """Omitting headers entirely must not be quieter than sending bad ones."""
    with pytest.raises(bt.BridgeSecurityError):
        bt.verify_headers({}, b"{}", nonce_cache=bt.NonceCache())


# ---------------------------------------------------------- explicit dev mode
def test_the_legacy_path_works_when_a_human_asks_for_it_by_name(monkeypatch):
    """Preserved, not deleted — but it takes both an argument and an env var."""
    monkeypatch.setenv(bt.DEV_UNSIGNED_ENV, "1")
    meta = bt.verify_headers(_headers(), b"{}", nonce_cache=bt.NonceCache(),
                             require_signature=False)
    assert meta["identity"] == "daleobanks"
    assert meta["signed"] == "false"


def test_only_the_exact_opt_in_value_counts(monkeypatch):
    """`true`, `yes` and `0` are not the opt-in. Ambiguity here is a downgrade."""
    for value in ("true", "yes", "0", "", "TRUE", "1 "):
        monkeypatch.setenv(bt.DEV_UNSIGNED_ENV, value)
        with pytest.raises(bt.BridgeSecurityError):
            bt.verify_headers(_headers(), b"{}", nonce_cache=bt.NonceCache(),
                              require_signature=False)


# ------------------------------------- never mistaken for isolated identity
def test_the_dev_mode_record_says_it_is_not_isolated_identity(monkeypatch):
    monkeypatch.setenv(bt.DEV_UNSIGNED_ENV, "1")
    meta = bt.verify_headers(_headers(), b"{}", nonce_cache=bt.NonceCache(),
                             require_signature=False)
    assert meta["identity_isolated"] == "false"
    assert meta["dev_compatibility_mode"] == "true"


def test_even_a_valid_signature_is_not_isolated_identity(monkeypatch):
    """The subtle half of the ruling, and the reason #7 was ratified at all.

    A correct HMAC proves the sender held the shared secret. It does not prove
    *which* holder sent it, because every participant needs that same secret to
    verify and can therefore also sign. `signed` and `identity_isolated` are
    separate facts and the record must carry both, or a reader sees
    `signed: true` and concludes something stronger than what was proven.
    """
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "shared-secret")
    body = json.dumps({"id": "OPP-1"}, sort_keys=True).encode()
    headers = bt.build_headers(body, identity="daleobanks", schema_version="1.1")

    meta = bt.verify_headers(headers, body, nonce_cache=bt.NonceCache())
    assert meta["signed"] == "true"
    assert meta["identity_isolated"] == "false"


def test_any_holder_of_the_shared_secret_can_claim_any_known_identity(monkeypatch):
    """The defect that motivated asymmetric identity, demonstrated.

    Signing as `kernel` while holding only the shared secret succeeds. Nothing
    in this transport can tell the difference — which is exactly what
    `identity/pki/` fixes, and why the mirrors' own docstring calls this a
    *recognised claimed identity* rather than an isolated one.
    """
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "shared-secret")
    body = b"{}"

    # An organ holding the shared key signs as the kernel. It verifies.
    forged = bt.build_headers(body, identity="kernel", schema_version="1.1")
    meta = bt.verify_headers(forged, body, nonce_cache=bt.NonceCache())
    assert meta["identity"] == "kernel"
    assert meta["identity_isolated"] == "false", (
        "this impersonation succeeds; the record must not imply otherwise"
    )


def test_the_asymmetric_replacement_refuses_the_same_impersonation():
    """The contrast, asserted rather than described.

    Same attack, against `identity/pki/`: forging the kernel's SPIFFE ID fails,
    because signing requires a private key the forger does not hold.
    """
    from identity.pki import CertificateAuthority, UntrustedIssuer, mutual_tls

    ca = CertificateAuthority()
    kernel, _ = ca.issue("spiffe://uniimente.internal/kernel/action-gateway")

    attacker_ca = CertificateAuthority(common_name="Attacker CA")
    forged, _ = attacker_ca.issue("spiffe://uniimente.internal/kernel/action-gateway")

    with pytest.raises(UntrustedIssuer):
        mutual_tls(forged, kernel)


# --------------------------------------------------------- the bridge caller
def test_bridge_a_no_longer_needs_a_shared_secret_to_have_verified_transport():
    """Second behaviour change, pinned deliberately.

    The first (2026-08-22) was: with no key and no opt-in, Bridge A halts at
    TRANSPORT_REFUSED rather than traversing on a verification that verified
    nothing. That test asserted the halt.

    The second (2026-08-23, FOUNDER-RULING-2026-08-23) is the adoption: Bridge A
    authenticates its peer with an isolated workload key via `identity.mesh`, so
    there is no shared secret to be missing. `WEALTHMACHINE_SIGNING_KEY` is
    irrelevant to this leg now, and the run gets *past* transport with no
    environment configured at all.

    That is strictly stronger, not weaker. The old path could only fail closed;
    this one authenticates. The run below still does not complete — it stops
    later, on the packet's own contract — and the distinction between "the peer
    is unverified" and "the payload is malformed" is exactly what was previously
    impossible to draw here.
    """
    import os

    from bridges import signal_to_venture as sv

    assert os.getenv("WEALTHMACHINE_SIGNING_KEY") is None
    assert os.getenv("UNIIMENTE_BRIDGE_DEV_UNSIGNED") != "1"

    run = sv.run({"id": "OPP-TRANSPORT-CHECK", "schema_version": "1.1"}, {})

    assert run.completed is False
    assert run.halted_at is not sv.Halt.TRANSPORT_REFUSED, (
        "the peer authenticated with an isolated key; a TRANSPORT_REFUSED here "
        "would mean the mesh handshake regressed to the shared-secret path")


def test_bridge_a_still_halts_at_transport_when_the_peer_cannot_authenticate():
    """The property the previous test protected, kept — on the new mechanism.

    A revoked workload must not traverse the bridge. Revocation is the cheapest
    honest way to make a real handshake fail: the certificate is well-formed and
    correctly issued, and trust in it has been withdrawn.
    """
    from bridges import signal_to_venture as sv
    from identity.mesh import InternalMesh

    mesh = InternalMesh()
    # Revoke and then re-pin the same serial, so the identity the bridge uses is
    # the revoked one rather than a freshly minted replacement.
    workload = mesh.identity_for("bridge_daleobanks")
    mesh.revocations.revoke(workload.serial, reason="adversarial test")

    run = sv.run({"id": "OPP-TRANSPORT-CHECK", "schema_version": "1.1"}, {},
                 mesh=mesh)

    assert run.completed is False
    assert run.halted_at is sv.Halt.TRANSPORT_REFUSED
    assert "transport refused" in run.reason
