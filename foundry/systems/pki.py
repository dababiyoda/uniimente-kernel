"""#7 Public-key infrastructure on GREG's founder/device identity (greg/founder.py).

Every command names its signing key; the founder key is enrolled; phones get
founder-delegated device keys that are short-lived, limited to named command
kinds and revocable. Possession of a device key never confers founder power.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def exercise(root) -> dict:
    from greg.founder import (FounderAuthError, FounderVerifier, key_id, public_bytes, sign_command,
                              validate_device_grant)
    founder = Ed25519PrivateKey.from_private_bytes(bytes(32 * [7]))
    phone = Ed25519PrivateKey.from_private_bytes(bytes(32 * [9]))
    f_hex, p_hex = public_bytes(founder.public_key()).hex(), public_bytes(phone.public_key()).hex()
    grant = validate_device_grant({"public_key": p_hex, "label": "phone", "kinds": ["DECISION"],
                                   "expires_at": (NOW + timedelta(days=30)).isoformat().replace("+00:00", "Z")}, now=NOW)
    seen = set()
    verifier = FounderVerifier(body_id="body-a", enrolled={key_id(f_hex): f_hex}, seen_nonce=lambda n: n in seen,
                               devices={grant["device_key_id"]: grant})

    def outcome(envelope, *, now=NOW, v=verifier):
        try:
            v.verify(envelope, now=now)
            seen.add(envelope["nonce"])
            return "accepted"
        except FounderAuthError as exc:
            return "refused: " + str(exc).split(";")[0]

    mission = sign_command(founder, "MISSION", {"mission_id": "m:x"}, body_id="body-a", now=NOW, nonce="n" * 16)
    results = {"founder_mission": outcome(mission), "replayed_nonce": outcome(mission)}
    results["other_body"] = outcome(sign_command(founder, "MISSION", {}, body_id="body-b", now=NOW, nonce="o" * 16))
    tampered = sign_command(founder, "MISSION", {"mission_id": "m:x"}, body_id="body-a", now=NOW, nonce="t" * 16)
    tampered["body"] = {"mission_id": "m:evil"}
    results["tampered_body"] = outcome(tampered)
    results["device_decision"] = outcome(sign_command(phone, "DECISION", {}, body_id="body-a", now=NOW, nonce="d" * 16))
    results["device_mission"] = outcome(sign_command(phone, "MISSION", {}, body_id="body-a", now=NOW, nonce="e" * 16))
    late = NOW + timedelta(days=31)
    results["device_after_expiry"] = outcome(sign_command(phone, "DECISION", {}, body_id="body-a", now=late, nonce="l" * 16),
                                             now=late)
    revoked = FounderVerifier(body_id="body-a", enrolled={key_id(f_hex): f_hex}, seen_nonce=lambda n: False, devices={})
    results["device_after_revocation"] = outcome(sign_command(phone, "DECISION", {}, body_id="body-a", now=NOW,
                                                              nonce="r" * 16), v=revoked)
    try:
        validate_device_grant({"public_key": p_hex, "label": "phone", "kinds": ["DECISION"],
                               "expires_at": (NOW + timedelta(days=400)).isoformat().replace("+00:00", "Z")}, now=NOW)
        long_lived_refused = False
    except FounderAuthError:
        long_lived_refused = True
    results["long_lived_delegation_refused"] = long_lived_refused
    return results


QUERY_OPS = {"demonstrate": lambda a, r: exercise(r)}
APPLY_OPS: dict = {}
