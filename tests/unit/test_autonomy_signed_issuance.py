"""Acceptance I.G5: autonomy above A0 is issued only on the founder's signature, never on a name.

Before this, ``AutonomyAuthority.issue(subject, tuple_, level=8, authorized_by="Alfonso Lopez")`` minted an A8
license: ``authorized_by`` was a caller string, so any caller could type the founder's name. Now a level above A0
also needs a greg.founder envelope of kind AUTONOMY_GRANT, signed by an enrolled founder key, for exactly this
subject, tuple and level, whose nonce this authority has not spent.
"""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from autonomy.levels import GRANT_KIND, AutonomyAuthority, AutonomyTuple
from greg.founder import (COMMAND_KINDS, DEVICE_KINDS, FounderVerifier, key_id, public_bytes, sign_command,
                          validate_device_grant)
from provenance.ledger import EvidenceLedger

BODY = "autonomy-signed-issuance-body"
FOUNDER, OTHER, DEVICE = (Ed25519PrivateKey.generate() for _ in range(3))
NAME = "Alfonso Lopez"


def _pub(key):
    return public_bytes(key.public_key()).hex()


def _verifier(*, devices=None):
    return FounderVerifier(body_id=BODY, enrolled={key_id(_pub(FOUNDER)): _pub(FOUNDER)},
                           seen_nonce=lambda n: False, devices=devices)


def _tuple(**kw):
    base = dict(capability="draft.publish", domain="comms", action="publish", resource="outbox", target="sandbox",
                consequence_class="external_contact", environment="production", budget_usd=25.0,
                duration="30 days")
    return AutonomyTuple(**{**base, **kw})


def _grant(subject="agent-1", tuple_=None, level=5, *, key=FOUNDER, kind=GRANT_KIND, body_id=BODY, **kw):
    body = {"subject": subject, "tuple": asdict(tuple_ or _tuple()), "level": level}
    return sign_command(key, kind, body, body_id=body_id, **kw)


def _auth(verifier="founder"):
    return AutonomyAuthority(EvidenceLedger("sha256:" + "0" * 64),
                             verifier=_verifier() if verifier == "founder" else verifier)


def _issued(auth):
    return [r.payload for r in auth.ledger.by_type("event") if r.payload.get("type") == "autonomy.issued"]


def _refused(auth, match, *, subject="agent-1", tuple_=None, level=5, **issue_kw):
    with pytest.raises(ValueError, match=match):
        auth.issue(subject, tuple_ or _tuple(), level=level, authorized_by=NAME, **issue_kw)
    assert auth.level_of(subject, tuple_ or _tuple()) == 0 and _issued(auth) == []


def test_the_grant_kind_is_founder_only():
    assert GRANT_KIND in COMMAND_KINDS and GRANT_KIND not in DEVICE_KINDS


def test_a_signed_grant_issues_exactly_that_level_and_the_ledger_keeps_the_signature():
    auth = _auth()
    grant = _grant()
    lic = auth.issue("agent-1", _tuple(), level=5, authorized_by=NAME, authorization=grant)
    assert lic.level == 5 and auth.level_of("agent-1", _tuple()) == 5
    [event] = _issued(auth)
    assert event["authorized_by"] == NAME
    assert event["authorization"]["founder_key_id"] == key_id(_pub(FOUNDER))
    assert event["authorization"]["nonce"] == grant["nonce"] and event["authorization"]["kind"] == GRANT_KIND
    assert len(event["authorization"]["envelope_sha256"]) == 64
    assert lic.history[0]["authorization"] == event["authorization"]
    assert auth.ledger.verify_chain()[0]


def test_a_name_alone_no_longer_issues_autonomy():
    """The I.G5 gap itself: on f383fd26 this returned an A8 license."""
    _refused(_auth(), "named authorizer alone does not authenticate", level=8)


def test_without_a_founder_verifier_nothing_above_a0_is_issued_even_with_a_signed_grant():
    _refused(_auth(verifier=None), "no founder verifier", authorization=_grant())


def test_a_grant_signed_by_a_key_that_is_not_enrolled_is_refused():
    _refused(_auth(), "does not verify", authorization=_grant(key=OTHER))


def test_a_delegated_device_key_cannot_sign_an_autonomy_grant():
    now = datetime.now(timezone.utc)
    device = validate_device_grant({"public_key": _pub(DEVICE), "label": "phone", "kinds": ["DECISION"],
                                    "expires_at": (now + timedelta(days=30)).isoformat()}, now=now)
    auth = _auth(verifier=_verifier(devices={device["device_key_id"]: device}))
    _refused(auth, "does not verify", authorization=_grant(key=DEVICE))


def test_even_a_device_delegated_this_kind_cannot_issue_autonomy(monkeypatch):
    """Defence in depth: if DEVICE_KINDS ever grew to include AUTONOMY_GRANT and a delegation listed it, the
    authority still refuses anything but the founder key itself."""
    import greg.founder as founder
    monkeypatch.setattr(founder, "DEVICE_KINDS", founder.DEVICE_KINDS + (GRANT_KIND,))
    device = {"device_key_id": key_id(_pub(DEVICE)), "public_key": _pub(DEVICE), "label": "phone",
              "kinds": [GRANT_KIND], "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
    auth = _auth(verifier=_verifier(devices={device["device_key_id"]: device}))
    _refused(auth, "founder key itself", authorization=_grant(key=DEVICE))


@pytest.mark.parametrize("signed", [
    dict(subject="agent-2"),                                         # another subject
    dict(level=2),                                                   # a lower level, used for A5
    dict(tuple_=_tuple(budget_usd=10_000.0)),                        # another budget
    dict(tuple_=_tuple(environment="sandbox")),                      # another environment
    dict(tuple_=_tuple(action="delete")),                            # another action
])
def test_a_grant_for_a_different_subject_tuple_or_level_is_refused(signed):
    _refused(_auth(), "for a different grant", authorization=_grant(**signed))


def test_a_grant_cannot_be_used_twice():
    auth = _auth()
    grant = _grant()
    auth.issue("agent-1", _tuple(), level=5, authorized_by=NAME, authorization=grant)
    auth.regress(auth._by_subject_tuple[("agent-1", _tuple().key())], failure_class="harm", detail="x")
    with pytest.raises(ValueError, match="already used"):
        auth.issue("agent-1", _tuple(), level=5, authorized_by=NAME, authorization=grant)
    assert auth.level_of("agent-1", _tuple()) == 0 and len(_issued(auth)) == 1


@pytest.mark.parametrize("bad", [
    dict(kind="DECISION"),                                           # the founder's key, the wrong kind
    dict(body_id="another-body"),                                    # signed for another body
    dict(now=datetime.now(timezone.utc) - timedelta(days=3), ttl=timedelta(days=1)),   # expired
])
def test_a_grant_of_the_wrong_kind_body_or_lifetime_is_refused(bad):
    _refused(_auth(), "does not verify", authorization=_grant(**bad))


def test_a_grant_edited_after_signing_is_refused():
    grant = _grant(level=1)
    grant["body"] = {**grant["body"], "level": 8}
    _refused(_auth(), "does not verify", level=8, authorization=grant)


@pytest.mark.parametrize("junk", ["signed", 42, ["x"], {}])
def test_an_authorization_that_is_not_an_envelope_is_refused(junk):
    _refused(_auth(), "needs a founder-signed|does not verify", authorization=junk)


def test_the_name_checks_still_run_before_the_signature():
    """A signed grant does not let UNIIMENTE or the subject be named as the authorizer."""
    auth = _auth()
    with pytest.raises(ValueError, match="never creates authority"):
        auth.issue("agent-1", _tuple(), level=5, authorized_by="UNIIMENTE", authorization=_grant())
    assert _issued(auth) == []


def test_a0_still_needs_neither_a_name_nor_a_signature():
    auth = _auth(verifier=None)
    assert auth.issue("agent-1", _tuple(), level=0).level == 0


def test_a_signed_grant_does_not_buy_a9():
    _refused(_auth(), "reserved human sovereignty", level=9, authorization=_grant(level=9))


def test_a_greg_body_refuses_an_autonomy_grant_in_its_inbox_and_keeps_running(tmp_path):
    """The kind has no Body command path yet: a GREG Body records the envelope as rejected, applies nothing and
    keeps a verifiable ledger (I.G5's residual: autonomy issuance is a library, not a Body command)."""
    from greg.body import Body
    from tests.greg_fixtures import drop, make_body, signed
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
        drop(home, signed(key, body_id, GRANT_KIND, {"subject": "a", "tuple": asdict(_tuple()), "level": 1}))
        body.tick()
        rejected = [r.payload for r in body.ledger.by_type("event") if r.payload.get("type") == "greg.command.rejected"]
        assert rejected and "unsupported command kind AUTONOMY_GRANT" in str(rejected[-1])
        assert not [r for r in body.ledger.by_type("event") if r.payload.get("type") == "autonomy.issued"]
        assert body.ledger.verify_chain()[0]
