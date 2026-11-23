"""Acceptance I.G9 (Mission I): an old token of a re-delegated device key never authenticates a read.

``FounderVerifier.verify`` refuses a command a device key signed before its current delegation
(``signed_not_before``, stamped by ``greg.body.device_delegations`` when a revoked key is delegated again), and
``goal_gravity``'s verified fold does the same since 6c33c726. ``verify_read`` did not: a read the phone signed
under its revoked delegation still authenticated for the 60 s read window after the key was delegated again.
Reads change nothing, so this narrows what a stale token can see, not what it can do.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from greg.founder import FounderAuthError, FounderVerifier, key_id, public_bytes, sign_read, stamp

BODY = "body-test"
T0 = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


def _verifier(device_key: Ed25519PrivateKey, **grant) -> FounderVerifier:
    public = public_bytes(device_key.public_key()).hex()
    kid = key_id(public)
    device = {"device_key_id": kid, "public_key": public, "label": "phone", "kinds": ["DECISION"],
              "expires_at": "2099-01-01T00:00:00Z", **grant}
    return FounderVerifier(body_id=BODY, enrolled={}, seen_nonce=lambda n: False, devices={kid: device})


def test_a_read_signed_before_the_key_was_delegated_again_is_refused():
    phone = Ed25519PrivateKey.generate()
    old = sign_read(phone, body_id=BODY, method="GET", path="/api/status", now=T0)
    verifier = _verifier(phone, signed_not_before=stamp(T0 + timedelta(seconds=20)))
    with pytest.raises(FounderAuthError, match="delegated again"):
        verifier.verify_read(old, method="GET", path="/api/status", now=T0 + timedelta(seconds=30))


def test_a_read_signed_after_the_new_delegation_still_verifies():
    phone = Ed25519PrivateKey.generate()
    verifier = _verifier(phone, signed_not_before=stamp(T0))
    fresh = sign_read(phone, body_id=BODY, method="GET", path="/api/status", now=T0 + timedelta(seconds=5))
    assert verifier.verify_read(fresh, method="GET", path="/api/status",
                                now=T0 + timedelta(seconds=10)) == "device:phone"


def test_a_key_never_delegated_again_is_unaffected():
    phone = Ed25519PrivateKey.generate()
    read = sign_read(phone, body_id=BODY, method="GET", path="/api/status", now=T0)
    assert _verifier(phone).verify_read(read, method="GET", path="/api/status", now=T0) == "device:phone"


def test_on_a_real_body_the_phone_channel_refuses_a_read_signed_under_the_revoked_delegation(tmp_path):
    """End to end: enrol, sign a read, revoke, delegate the same key again, then replay the old read inside its
    60 s window through the remote channel (which builds its verifier from greg.body.device_delegations)."""
    from greg import remote
    from greg.body import Body
    from tests.unit.test_greg_missions import run, submit
    from tests.unit.test_greg_remote import _phone

    home, key, body_id, phone, clock = _phone(tmp_path)
    old = sign_read(phone, body_id=body_id, method="GET", path="/api/status", now=clock.now)
    assert remote.handle(home, "GET", "/api/status", old, b"", now=clock.now)[0] == 200
    with Body(home) as body:
        kid = next(iter(body.device_keys()))
    submit(home, key, body_id, "DEVICE_REVOKE", {"device_key_id": kid})
    run(home, clock, ticks=1)
    submit(home, key, body_id, "DEVICE_ENROLL", {"public_key": public_bytes(phone.public_key()).hex(),
                                                 "label": "phone", "kinds": ["DECISION"],
                                                 "expires_at": stamp(clock.now + timedelta(days=30))})
    run(home, clock, ticks=1)
    with pytest.raises(remote.RemoteError) as refused:
        remote.handle(home, "GET", "/api/status", old, b"", now=clock.now)
    assert refused.value.status == 401 and "delegated again" in str(refused.value)
    fresh = sign_read(phone, body_id=body_id, method="GET", path="/api/status", now=clock.now)
    assert remote.handle(home, "GET", "/api/status", fresh, b"", now=clock.now)[0] == 200
