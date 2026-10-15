"""Per-organ bridge keys: isolation when configured, byte-compatibility when not.

tests/fixtures/bridge_transport_v2_4999acff.py is the exact transport both
organs pin today (sha256 930d63af...), vendored so interoperability is
checked against what they actually run.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from adapters import bridge_transport as bt

PINNED = Path(__file__).resolve().parents[1] / "fixtures" / "bridge_transport_v2_4999acff.py"
PINNED_SHA256 = "930d63af8d798a844fbc81a1055c2659b2fca85824c44198074c0547bd4c460f"
BODY = json.dumps({"id": "p-1"}).encode()
ORGANS = ("daleobanks", "wealthmachine", "kernel")


def _pinned():
    assert hashlib.sha256(PINNED.read_bytes()).hexdigest() == PINNED_SHA256
    spec = importlib.util.spec_from_file_location("pinned_bridge_transport", PINNED)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def shared_only(monkeypatch):
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "shared-key")
    for organ in ORGANS:
        monkeypatch.delenv(bt.IDENTITY_KEY_ENV_PREFIX + organ.upper(), raising=False)


@pytest.fixture()
def per_organ(monkeypatch, shared_only):
    for organ in ORGANS:
        monkeypatch.setenv(bt.IDENTITY_KEY_ENV_PREFIX + organ.upper(), f"{organ}-own-key")


def _verify(headers, body=BODY, **kw):
    return bt.verify_headers(headers, body, nonce_cache=bt.NonceCache(), expected_sender="daleobanks", **kw)


# --- compatibility with the pinned transport ---------------------------------

def test_pinned_organ_messages_still_verify(shared_only):
    pinned = _pinned()
    headers = pinned.build_headers(BODY, identity="daleobanks", schema_version="1.1", trace_id="t")
    meta = _verify(headers)
    assert meta["identity_isolated"] == "false" and meta["key_scope"] == "shared"


def test_shared_scope_output_is_byte_compatible_with_pinned_verifier(shared_only):
    pinned = _pinned()
    headers = bt.build_headers(BODY, identity="daleobanks", schema_version="1.1", trace_id="t")
    assert bt.H_KEY_SCOPE not in headers
    pinned.verify_headers(headers, BODY, nonce_cache=pinned.NonceCache(), expected_sender="daleobanks")


def test_shared_signature_is_identical_to_pinned(shared_only):
    pinned = _pinned()
    args = ("shared-key", "daleobanks", "1700000000", "n", "i", "1.1", BODY)
    assert bt.sign(*args, trace_id="t") == pinned.sign(*args, trace_id="t")


# --- isolation ---------------------------------------------------------------

def test_per_organ_key_yields_isolated_identity(per_organ):
    headers = bt.build_headers(BODY, identity="daleobanks", schema_version="1.1")
    assert headers[bt.H_KEY_SCOPE] == "identity"
    meta = _verify(headers, require_isolated_identity=True)
    assert meta["identity_isolated"] == "true" and meta["key_scope"] == "identity"


def test_organ_cannot_sign_as_another_organ(per_organ, monkeypatch):
    """WealthMachine holds only its own key and the shared key, and claims DALEOBANKS."""
    body, ts, nonce = BODY, str(int(__import__("time").time())), "n-forged"
    sig = bt.sign("wealthmachine-own-key", "daleobanks", ts, nonce, "i", "1.1", body, key_scope="identity")
    headers = {bt.H_PROTOCOL: bt.PROTOCOL_VERSION, bt.H_IDENTITY: "daleobanks", bt.H_RECIPIENT: "wealthmachine",
               bt.H_TIMESTAMP: ts, bt.H_NONCE: nonce, bt.H_IDEMPOTENCY: "i", bt.H_SCHEMA: "1.1",
               bt.H_TRACE: "", bt.H_OPERATION: "opportunity.evaluate", bt.H_REQUEST: "",
               bt.H_DIRECTION: "request", bt.H_STATUS: "", bt.H_KEY_SCOPE: "identity", bt.H_SIGNATURE: sig}
    with pytest.raises(bt.BridgeSecurityError, match="signature"):
        _verify(headers)


def test_scope_downgrade_is_refused_when_isolation_required(per_organ, monkeypatch):
    """A shared-key holder strips the scope and signs with the shared key."""
    monkeypatch.delenv(bt.IDENTITY_KEY_ENV_PREFIX + "DALEOBANKS")
    downgraded = bt.build_headers(BODY, identity="daleobanks", schema_version="1.1")
    monkeypatch.setenv(bt.IDENTITY_KEY_ENV_PREFIX + "DALEOBANKS", "daleobanks-own-key")
    assert bt.H_KEY_SCOPE not in downgraded
    assert _verify(downgraded)["identity_isolated"] == "false"
    with pytest.raises(bt.BridgeSecurityError, match="isolated sender identity required"):
        _verify(downgraded, require_isolated_identity=True)


def test_scope_is_bound_into_the_signature(per_organ):
    headers = bt.build_headers(BODY, identity="daleobanks", schema_version="1.1")
    stripped = {k: v for k, v in headers.items() if k != bt.H_KEY_SCOPE}
    with pytest.raises(bt.BridgeSecurityError, match="signature"):
        _verify(stripped)


@pytest.mark.parametrize("collision", ["shared-key", "wealthmachine-own-key"])
def test_colliding_keys_are_not_reported_as_isolated(per_organ, monkeypatch, collision):
    monkeypatch.setenv(bt.IDENTITY_KEY_ENV_PREFIX + "DALEOBANKS", collision)
    headers = bt.build_headers(BODY, identity="daleobanks", schema_version="1.1")
    assert _verify(headers)["identity_isolated"] == "false"
    headers = bt.build_headers(BODY, identity="daleobanks", schema_version="1.1")
    with pytest.raises(bt.BridgeSecurityError):
        _verify(headers, require_isolated_identity=True)


def test_identity_scope_without_verifier_key_fails_closed(per_organ, monkeypatch):
    headers = bt.build_headers(BODY, identity="daleobanks", schema_version="1.1")
    monkeypatch.delenv(bt.IDENTITY_KEY_ENV_PREFIX + "DALEOBANKS")
    with pytest.raises(bt.BridgeSecurityError, match="no per-organ key"):
        _verify(headers)


def test_unknown_scope_is_refused(shared_only):
    headers = {**bt.build_headers(BODY, identity="daleobanks", schema_version="1.1"), bt.H_KEY_SCOPE: "founder"}
    with pytest.raises(bt.BridgeSecurityError, match="unsupported key scope"):
        _verify(headers)


def test_pinned_verifier_rejects_identity_scope_rather_than_misreading_it(per_organ):
    """Older verifiers fail closed on per-organ messages; rollout must upgrade verifiers first."""
    pinned = _pinned()
    headers = bt.build_headers(BODY, identity="daleobanks", schema_version="1.1")
    with pytest.raises(pinned.BridgeSecurityError):
        pinned.verify_headers(headers, BODY, nonce_cache=pinned.NonceCache(), expected_sender="daleobanks")
