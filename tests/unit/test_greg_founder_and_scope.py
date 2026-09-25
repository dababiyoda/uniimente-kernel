"""Founder authentication (Ed25519) and light-cone containment: hostile cases first."""
from datetime import datetime, timedelta, timezone
import os

import pytest

from greg.founder import (FounderAuthError, FounderVerifier, generate_founder_key, key_id, load_founder_key,
                          public_bytes, sign_command)
from greg.lightcone import LightCone, ScopeError


@pytest.fixture
def founder(tmp_path):
    public = generate_founder_key(tmp_path / "k.pem", b"passphrase-1")
    key = load_founder_key(tmp_path / "k.pem", b"passphrase-1")
    seen = set()
    verifier = FounderVerifier(body_id="body-1", enrolled={key_id(public): public}, seen_nonce=seen.__contains__)
    return key, verifier, seen


def test_valid_command_verifies_and_binds_kind(founder):
    key, verifier, _ = founder
    env = sign_command(key, "MISSION", {"mission_id": "m:x"}, body_id="body-1")
    assert verifier.verify(env)["body"] == {"mission_id": "m:x"}
    with pytest.raises(FounderAuthError, match="wrong command kind"):
        verifier.verify(env, expected_kind="DECISION")


@pytest.mark.parametrize("mutate,match", [
    (lambda e: e["body"].update(mission_id="m:evil"), "signature"),
    (lambda e: e.update(kind="BODY_STOP"), "signature"),
    (lambda e: e.update(body_id="body-2"), "different body"),
    (lambda e: e.update(founder_key_id="ed25519:" + "0" * 32), "not enrolled"),
    (lambda e: e.update(extra="x"), "unknown or missing"),
    (lambda e: e.update(signature="00" * 64), "signature"),
])
def test_tampered_or_misaddressed_commands_refuse(founder, mutate, match):
    key, verifier, _ = founder
    env = sign_command(key, "MISSION", {"mission_id": "m:x"}, body_id="body-1")
    mutate(env)
    with pytest.raises(FounderAuthError, match=match):
        verifier.verify(env)


def test_other_key_cannot_impersonate_founder(founder, tmp_path):
    _, verifier, _ = founder
    generate_founder_key(tmp_path / "attacker.pem", None)
    attacker = load_founder_key(tmp_path / "attacker.pem", None)
    env = sign_command(attacker, "MISSION", {}, body_id="body-1")
    with pytest.raises(FounderAuthError, match="not enrolled"):
        verifier.verify(env)
    # Claiming the founder's key id with the attacker's signature still fails.
    env["founder_key_id"] = next(iter(verifier.enrolled))
    with pytest.raises(FounderAuthError, match="signature"):
        verifier.verify(env)


def test_replay_expiry_and_future_commands_refuse(founder):
    key, verifier, seen = founder
    env = sign_command(key, "DECISION", {}, body_id="body-1")
    verifier.verify(env)
    seen.add(env["nonce"])
    with pytest.raises(FounderAuthError, match="replayed"):
        verifier.verify(env)
    old = sign_command(key, "DECISION", {}, body_id="body-1",
                       now=datetime.now(timezone.utc) - timedelta(days=2), ttl=timedelta(hours=1))
    with pytest.raises(FounderAuthError, match="expired"):
        verifier.verify(old)
    future = sign_command(key, "DECISION", {}, body_id="body-1",
                          now=datetime.now(timezone.utc) + timedelta(hours=2))
    with pytest.raises(FounderAuthError, match="future"):
        verifier.verify(future)
    with pytest.raises(FounderAuthError, match="lifetime"):
        sign_command(key, "DECISION", {}, body_id="body-1", ttl=timedelta(days=30))


def test_key_custody_requires_private_file_and_passphrase(tmp_path):
    generate_founder_key(tmp_path / "k.pem", b"pw")
    assert oct(os.stat(tmp_path / "k.pem").st_mode & 0o777) == "0o600"
    with pytest.raises(Exception):
        load_founder_key(tmp_path / "k.pem", b"wrong")
    with pytest.raises(FileExistsError):
        generate_founder_key(tmp_path / "k.pem", b"pw")  # never overwrite a founder key
    os.chmod(tmp_path / "k.pem", 0o644)
    with pytest.raises(FounderAuthError, match="readable by others"):
        load_founder_key(tmp_path / "k.pem", b"pw")
    key = None
    del key


def _cone(**over):
    base = dict(capabilities=["fs.read", "fs.write", "acquired.hash.sha256.*"], targets=["fs:*", "workspace:m1/*"],
                max_consequence_class="internal_write", budget_usd=10.0,
                horizon=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    base.update(over)
    return LightCone.from_dict(base)


def test_light_cone_admits_only_inside_actions():
    cone = _cone()
    assert cone.admits(capability="fs.read", target="fs:a", consequence_class="read_only", cost_usd=0) == []
    assert cone.admits(capability="acquired.hash.sha256.sha256sum", target="fs:a",
                       consequence_class="read_only", cost_usd=0) == []
    reasons = cone.admits(capability="http.get", target="https:x", consequence_class="external_contact",
                          cost_usd=11, spent_usd=0)
    assert len(reasons) == 4
    assert cone.admits(capability="fs.read", target="fs:a", consequence_class="read_only",
                       cost_usd=6, spent_usd=5)  # cumulative budget


def test_child_scope_can_never_exceed_parent():
    cone = _cone()
    child = cone.narrow(capabilities=["fs.read"], budget_usd=1.0, targets=["workspace:m1/sub/*"])
    assert cone.contains(child) == []
    for change in (dict(capabilities=["fs.read", "http.get"]), dict(budget_usd=11.0),
                   dict(targets=["workspace:*"]), dict(max_consequence_class="external_contact"),
                   dict(horizon=(datetime.now(timezone.utc) + timedelta(days=9)).isoformat())):
        with pytest.raises(ScopeError):
            cone.narrow(**change)


def test_unbounded_or_sovereign_scopes_are_not_scopes():
    for bad in (dict(targets=["*"]), dict(capabilities=["*"]), dict(max_consequence_class="financial"),
                dict(max_consequence_class="irreversible"), dict(budget_usd=-1)):
        with pytest.raises(ScopeError):
            _cone(**bad)


def test_public_key_identity_is_stable(tmp_path):
    public = generate_founder_key(tmp_path / "k.pem", None)
    key = load_founder_key(tmp_path / "k.pem", None)
    assert public_bytes(key.public_key()).hex() == public
    assert key_id(public).startswith("ed25519:") and len(key_id(public)) == 40
