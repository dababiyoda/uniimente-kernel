"""An old token of a re-delegated device key never reactivates, on the command path and in its re-derivation.

Ported from #173 a8efed0 / f13dee5 / caa50b8 (``signed_not_before`` on device delegations) onto PR #184's founder
code. Before it, a command a phone signed under a delegation the founder then revoked was accepted again once the
founder delegated the same key again, and counted: by the body's verifier (FounderVerifier, fed by
``greg.body.device_delegations``), by the mission fold and by the separate appraiser (both read
``greg.goal_gravity.founder_facts``, which re-derives devices from the signed DEVICE_ENROLL / DEVICE_REVOKE
commands). Both derivations now carry the same anchor, the instant the body accepted the re-delegation, and a parity
test keeps them in agreement. Real bodies, per-test Ed25519 keys (not Alfonso's), a fake clock.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from greg import goal_gravity as gg
from greg.body import Body
from greg.founder import FounderAuthError, generate_founder_key, instant, key_id, load_founder_key, stamp
from greg.journal import iso
from provenance.ledger import sha256_json
from tests.greg_fixtures import Clock, make_body, mission, note_check, signed, workspace, write_strategy

MID = "m:re-delegated-old-token"
REFUSED = "before this device key's current delegation"
SIGNED_WHEN = ("before_its_revocation", "after_the_founder_presigned_the_re_delegation", "while_it_stood_revoked")


def _run(body, clock, ticks=8):
    states = []
    for _ in range(ticks):
        clock.advance(60)
        states.append(body.tick()["missions"][0]["state"])
        if states[-1] == "ACHIEVED":
            break
    return states


def _world(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    phone_public = generate_founder_key(tmp_path / "phone.pem", None)
    phone = load_founder_key(tmp_path / "phone.pem", None)
    clock = Clock()
    grant = {"public_key": phone_public, "label": "phone", "kinds": ["DECISION"],
             "expires_at": stamp(clock.now + timedelta(days=30))}
    return home, key, body_id, phone, phone_public, clock, grant


def _asking(body, key, body_id, clock, grant, home):
    """Delegate the phone, register a mission whose write is outside its cone, and return its approval ask."""
    body.apply(signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), channel="inbox")
    spec = mission(MID, checks=[note_check("n", workspace(home, MID) / "n.txt", "approved")],
                   strategies=[write_strategy("w", "n.txt", "approved", ["n"])], capabilities=["fs.read"],
                   ceiling="read_only")
    body.apply(signed(key, body_id, "MISSION", spec, now=clock.now), channel="inbox")
    body.boot()
    assert _run(body, clock, ticks=2)[-1] == "WAITING"
    [ask] = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "APPROVAL"]
    return {"request_id": ask["request_id"], "answer": "approve"}


def _old_token(body, key, body_id, phone, phone_public, clock, grant, answer, signed_when):
    """Revoke the phone and delegate it again; return the old token, signed at ``signed_when``."""
    old = presigned = None
    if signed_when == "before_its_revocation":
        old = signed(phone, body_id, "DECISION", answer, now=clock.now)
    clock.advance(10)
    presigned = signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now)   # prepared in advance
    clock.advance(10)
    if signed_when == "after_the_founder_presigned_the_re_delegation":
        old = signed(phone, body_id, "DECISION", answer, now=clock.now)
    clock.advance(40)
    body.apply(signed(key, body_id, "DEVICE_REVOKE", {"device_key_id": key_id(phone_public)}, now=clock.now),
               channel="inbox")
    clock.advance(30)
    if signed_when == "while_it_stood_revoked":
        old = signed(phone, body_id, "DECISION", answer, now=clock.now)
    clock.advance(30)
    body.apply(presigned, channel="inbox")
    clock.advance(5)
    return old


@pytest.mark.parametrize("signed_when", SIGNED_WHEN)
def test_the_body_refuses_a_token_signed_before_the_keys_re_delegation(tmp_path, signed_when):
    home, key, body_id, phone, phone_public, clock, grant = _world(tmp_path)
    with Body(home, clock=clock) as body:
        answer = _asking(body, key, body_id, clock, grant, home)
        old = _old_token(body, key, body_id, phone, phone_public, clock, grant, answer, signed_when)
        with pytest.raises(FounderAuthError, match=REFUSED):
            body.apply(old, channel="inbox")
    with Body(home, clock=clock) as body:                  # a restart re-derives the same refusal from the ledger
        with pytest.raises(FounderAuthError, match=REFUSED):
            body.apply(old, channel="inbox")
        fresh = signed(phone, body_id, "DECISION", answer, now=clock.now)   # what the phone signs now is honoured
        assert body.apply(fresh, channel="inbox")["status"] == "APPLIED"
        assert _run(body, clock)[-1] == "ACHIEVED"
    assert (workspace(home, MID) / "n.txt").read_text() == "approved"


@pytest.mark.parametrize("signed_when", SIGNED_WHEN)
def test_founder_facts_never_counts_an_old_token_smuggled_in_as_accepted(tmp_path, signed_when):
    """The fold reads founder_facts: an in-process writer's acceptance of the old token moves no mission."""
    home, key, body_id, phone, phone_public, clock, grant = _world(tmp_path)
    with Body(home, clock=clock) as body:
        answer = _asking(body, key, body_id, clock, grant, home)
        old = _old_token(body, key, body_id, phone, phone_public, clock, grant, answer, signed_when)
        digest = sha256_json(old)
        body.journal.record("command.accepted", {
            "kind": "DECISION", "digest": digest, "nonce": old["nonce"], "founder_key_id": old["founder_key_id"],
            "signer": "device:phone", "issued_at": old["issued_at"], "accepted_at": iso(clock.now),
            "body": old["body"], "envelope": old, "channel": "inbox",
            "result": {"request_id": answer["request_id"]}}, key=digest)
        body.engine.answer(old["body"], digest)            # the answer row MissionEngine.answer would write
        assert digest not in gg.founder_facts(body.ledger).signed
        assert digest not in gg.verified_decisions(body.ledger)
        assert _run(body, clock, ticks=3)[-1] == "WAITING"
    assert not (workspace(home, MID) / "n.txt").exists()


@pytest.mark.parametrize("signed_when", ["before_its_revocation", "while_it_stood_revoked"])
def test_the_appraiser_refutes_a_body_that_acted_on_an_old_token(tmp_path, monkeypatch, signed_when):
    """A body whose verifier and fold both lacked the rule acts on the old token; the separate appraiser (a real
    process running the unpatched code) refutes the closure. Adapted from #173's
    test_the_appraiser_refuses_an_approval_a_re_delegated_device_signed_before_its_re_delegation."""
    import greg.body as body_module
    home, key, body_id, phone, phone_public, clock, grant = _world(tmp_path)
    with Body(home, clock=clock) as body:
        answer = _asking(body, key, body_id, clock, grant, home)
        old = _old_token(body, key, body_id, phone, phone_public, clock, grant, answer, signed_when)
        [device] = body.device_keys().values()
        strip = lambda devices: {k: {f: v for f, v in d.items() if f != "signed_not_before"}  # noqa: E731
                                 for k, d in devices.items()}
        body.device_keys = lambda: strip(body_module.device_delegations(body.journal))
        real = gg._verify_envelope
        monkeypatch.setattr(gg, "_verify_envelope",
                            lambda payload, founders, devices, body_id_, at=None:
                            real(payload, founders, strip(devices), body_id_, at))
        body.apply(old, channel="inbox")
        assert _run(body, clock)[-1] == "ACHIEVED"
        verdict = body.journal.replay("mission.appraised")[-1].payload
    assert verdict["verdict"] == "REFUTED", verdict
    assert verdict["checks"]["approval_boundaries_honored"] is False, verdict
    assert [f for f in verdict["findings"] if f.startswith("w: executed without a prior founder approval")], \
        verdict["findings"]
    assert instant(device["signed_not_before"]) > instant(old["issued_at"])   # the body's own verifier refuses it


def _view(devices: dict) -> dict:
    return {kid: (d["public_key"], d["label"], tuple(sorted(d["kinds"])), instant(d["expires_at"]),
                  d.get("signed_not_before")) for kid, d in devices.items()}


def test_the_body_and_founder_facts_derive_the_same_delegations_and_verdicts(tmp_path):
    """Parity: after delegate / revoke / delegate again / revoke / delegate again (and a second device that is never
    revoked), both derivations list the same delegations with the same anchor, and judge every token alike."""
    home, key, body_id, phone, phone_public, clock, grant = _world(tmp_path)
    tablet_public = generate_founder_key(tmp_path / "tablet.pem", None)
    tablet = load_founder_key(tmp_path / "tablet.pem", None)
    stranger_public = generate_founder_key(tmp_path / "stranger.pem", None)
    stranger = load_founder_key(tmp_path / "stranger.pem", None)
    tablet_grant = {**grant, "public_key": tablet_public, "label": "tablet"}
    body_ = {"request_id": "req-parity", "answer": "approve"}
    tokens = {}
    revoke = {"device_key_id": key_id(phone_public)}
    with Body(home, clock=clock) as body:
        body.apply(signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), channel="inbox")
        body.apply(signed(key, body_id, "DEVICE_ENROLL", tablet_grant, now=clock.now), channel="inbox")
        clock.advance(10)
        tokens["first_delegation"] = signed(phone, body_id, "DECISION", body_, now=clock.now)
        tokens["tablet_early"] = signed(tablet, body_id, "DECISION", body_, now=clock.now)
        clock.advance(10)
        body.apply(signed(key, body_id, "DEVICE_REVOKE", revoke, now=clock.now), channel="inbox")
        clock.advance(10)
        tokens["first_revocation"] = signed(phone, body_id, "DECISION", body_, now=clock.now)
        clock.advance(10)
        body.apply(signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), channel="inbox")
        clock.advance(10)
        tokens["second_delegation"] = signed(phone, body_id, "DECISION", body_, now=clock.now)
        clock.advance(10)
        body.apply(signed(key, body_id, "DEVICE_REVOKE", revoke, now=clock.now), channel="inbox")
        clock.advance(10)
        body.apply(signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), channel="inbox")
        clock.advance(10)
        tokens["third_delegation"] = signed(phone, body_id, "DECISION", body_, now=clock.now)
        tokens["tablet_late"] = signed(tablet, body_id, "DECISION", body_, now=clock.now)
        tokens["stranger"] = signed(stranger, body_id, "DECISION", body_, now=clock.now)
        assert stranger_public not in {d["public_key"] for d in body.device_keys().values()}

        facts = gg.founder_facts(body.ledger)
        assert _view(body.device_keys()) == _view(facts.devices)
        anchors = {kid: d.get("signed_not_before") for kid, d in body.device_keys().items()}
        assert anchors[key_id(tablet_public)] is None and anchors[key_id(phone_public)] is not None

        verifier = body.verifier()
        body_verdict = {}
        for name, token in tokens.items():
            try:
                verifier.verify(token, now=clock.now)
                body_verdict[name] = True
            except FounderAuthError:
                body_verdict[name] = False
        assert body_verdict == {"first_delegation": False, "tablet_early": True, "first_revocation": False,
                                "second_delegation": False, "third_delegation": True, "tablet_late": True,
                                "stranger": False}
        for token in tokens.values():                      # an acceptance of each, at this instant, by any writer
            digest = sha256_json(token)
            body.journal.record("command.accepted", {
                "kind": "DECISION", "digest": digest, "nonce": token["nonce"],
                "founder_key_id": token["founder_key_id"], "signer": "device", "issued_at": token["issued_at"],
                "accepted_at": iso(clock.now), "body": token["body"], "envelope": token, "channel": "inbox",
                "result": {}}, key=digest)
        counted = gg.founder_facts(body.ledger).signed
        assert {name: sha256_json(token) in counted for name, token in tokens.items()} == body_verdict


def test_a_re_delegation_anchor_is_the_instant_its_command_was_accepted(tmp_path):
    """device.enrolled's ``at`` and the DEVICE_ENROLL's ``accepted_at`` are one clock reading, so the body's
    anchor and founder_facts' anchor are the same instant even on a real clock."""
    home, key, body_id, phone, phone_public, _, grant = _world(tmp_path)
    with Body(home) as body:                              # the real clock: two readings would differ
        body.apply(signed(key, body_id, "DEVICE_ENROLL", grant), channel="inbox")
        body.apply(signed(key, body_id, "DEVICE_REVOKE", {"device_key_id": key_id(phone_public)}), channel="inbox")
        again = signed(key, body_id, "DEVICE_ENROLL", grant)
        body.apply(again, channel="inbox")
        [accepted] = [e.payload for e in body.journal.replay("command.accepted")
                      if e.payload["digest"] == sha256_json(again)]
        [device] = body.device_keys().values()
        assert device["signed_not_before"] == accepted["accepted_at"]
        assert gg.founder_facts(body.ledger).devices[key_id(phone_public)]["signed_not_before"] == \
            accepted["accepted_at"]


def _accept(body, clock, token, *, accepted_at=True):
    """Record an acceptance of ``token`` as any in-process writer could (``accepted_at`` False: a legacy record)."""
    digest = sha256_json(token)
    body.journal.record("command.accepted", {
        "kind": token["kind"], "digest": digest, "nonce": token["nonce"], "founder_key_id": token["founder_key_id"],
        "signer": "device", "issued_at": token["issued_at"], "body": token["body"], "envelope": token,
        "channel": "inbox", "result": {}, **({"accepted_at": iso(clock.now)} if accepted_at else {})}, key=digest)
    return digest


def test_an_unreadable_or_absent_anchor_fails_closed_and_the_anchor_instant_itself_verifies():
    from greg.founder import signed_before_delegation
    t = instant("2026-10-21T12:00:00.000005Z")
    assert signed_before_delegation({}, t) is False                              # first delegation: no anchor
    assert signed_before_delegation({"signed_not_before": "garbage"}, t) is True
    assert signed_before_delegation({"signed_not_before": None}, t) is True      # a re-delegation with no time
    assert signed_before_delegation({"signed_not_before": "2026-10-21T12:00:00.000005Z"}, t) is False
    assert signed_before_delegation({"signed_not_before": "2026-10-21T12:00:00.000006Z"}, t) is True


def test_a_token_issued_at_the_re_delegation_instant_verifies_and_one_a_microsecond_earlier_does_not(tmp_path):
    """The boundary, in the body's verifier and in founder_facts alike: the anchor instant is the first that counts."""
    home, key, body_id, phone, phone_public, clock, grant = _world(tmp_path)
    request = {"request_id": "req-boundary", "answer": "approve"}
    with Body(home, clock=clock) as body:
        body.apply(signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), channel="inbox")
        clock.advance(10)
        body.apply(signed(key, body_id, "DEVICE_REVOKE", {"device_key_id": key_id(phone_public)}, now=clock.now),
                   channel="inbox")
        clock.advance(10)
        body.apply(signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), channel="inbox")
        anchor = instant(body.device_keys()[key_id(phone_public)]["signed_not_before"])
        assert anchor == clock.now
        at = signed(phone, body_id, "DECISION", request, now=anchor)
        early = signed(phone, body_id, "DECISION", request, now=anchor - timedelta(microseconds=1))
        verifier = body.verifier()
        assert verifier.verify(at, now=clock.now) is at
        with pytest.raises(FounderAuthError, match=REFUSED):
            verifier.verify(early, now=clock.now)
        counted = {name: _accept(body, clock, token) for name, token in (("at", at), ("early", early))}
        signed_facts = gg.founder_facts(body.ledger).signed
        assert {name: digest in signed_facts for name, digest in counted.items()} == {"at": True, "early": False}


@pytest.mark.parametrize("anchor_recorded", [True, False])
def test_founder_facts_refuses_every_token_of_a_re_delegation_accepted_with_no_time(tmp_path, anchor_recorded):
    """A re-delegation whose acceptance record carries no accepted_at (a legacy record) has no readable anchor:
    founder_facts counts nothing the key signs under it, never treating the missing time as the beginning of time."""
    home, key, body_id, phone, phone_public, clock, grant = _world(tmp_path)
    with Body(home, clock=clock) as body:
        body.apply(signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), channel="inbox")
        clock.advance(10)
        body.apply(signed(key, body_id, "DEVICE_REVOKE", {"device_key_id": key_id(phone_public)}, now=clock.now),
                   channel="inbox")
        clock.advance(10)
        _accept(body, clock, signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), accepted_at=anchor_recorded)
        clock.advance(10)
        later = _accept(body, clock, signed(phone, body_id, "DECISION", {"request_id": "req-legacy",
                                                                         "answer": "approve"}, now=clock.now))
        facts = gg.founder_facts(body.ledger)
        assert (facts.devices[key_id(phone_public)]["signed_not_before"] is not None) is anchor_recorded
        assert (later in facts.signed) is anchor_recorded


@pytest.mark.parametrize("anchor_recorded", [True, False])
def test_the_body_refuses_every_command_of_a_re_delegation_recorded_with_no_time(tmp_path, anchor_recorded):
    """A device.enrolled for a re-delegated key that names no ``at`` (a legacy record) leaves an unreadable anchor:
    FounderVerifier refuses that key's commands instead of treating the missing time as the beginning of time."""
    home, key, body_id, phone, phone_public, clock, grant = _world(tmp_path)
    with Body(home, clock=clock) as body:
        body.apply(signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), channel="inbox")
        [first] = [e.payload for e in body.journal.replay("device.enrolled")]
        clock.advance(10)
        body.apply(signed(key, body_id, "DEVICE_REVOKE", {"device_key_id": key_id(phone_public)}, now=clock.now),
                   channel="inbox")
        clock.advance(10)
        again = {k: v for k, v in first.items() if k != "at"}
        again["command_digest"] = "legacy-re-delegation"
        if anchor_recorded:
            again["at"] = iso(clock.now)
        body.journal.record("device.enrolled", again, key=[first["device_key_id"], "legacy-re-delegation"])
        clock.advance(10)
        fresh = signed(phone, body_id, "DECISION", {"request_id": "req-legacy", "answer": "approve"}, now=clock.now)
        if anchor_recorded:
            assert body.verifier().verify(fresh, now=clock.now) is fresh
        else:
            with pytest.raises(FounderAuthError, match=REFUSED):
                body.verifier().verify(fresh, now=clock.now)


@pytest.mark.parametrize("revoked", [True, False])
def test_the_founder_key_never_rotates_to_a_device_key_so_its_old_tokens_stay_dead(tmp_path, revoked):
    """Rotated in, a key that is (or was, then revoked) a delegated device would make every unexpired token it signed
    as a device verify again, now as a founder command. The body refuses the rotation; founder_facts ignores an
    acceptance of it, so the old token counts in neither."""
    from greg.missions import MissionError
    home, key, body_id, phone, phone_public, clock, grant = _world(tmp_path)
    request = {"request_id": "req-rotate", "answer": "approve"}
    with Body(home, clock=clock) as body:
        founder_before = body.enrolled_keys()
        body.apply(signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), channel="inbox")
        clock.advance(10)
        old = signed(phone, body_id, "DECISION", request, now=clock.now)       # signed as a device
        clock.advance(10)
        if revoked:
            body.apply(signed(key, body_id, "DEVICE_REVOKE", {"device_key_id": key_id(phone_public)},
                              now=clock.now), channel="inbox")
            clock.advance(10)
        rotate = signed(key, body_id, "ROTATE_FOUNDER_KEY", {"new_public_key": phone_public}, now=clock.now)
        with pytest.raises(MissionError, match="is or was a delegated device key"):
            body.apply(rotate, channel="inbox")
        assert body.enrolled_keys() == founder_before
        if revoked:
            with pytest.raises(FounderAuthError, match="not enrolled or revoked"):
                body.verifier().verify(old, now=clock.now)
        digest = _accept(body, clock, rotate)                  # an in-process writer records the rotation anyway
        clock.advance(10)
        token = _accept(body, clock, old)
        facts = gg.founder_facts(body.ledger)
        assert facts.refused[digest] == "rotation to a key that is or was a delegated device key"
        assert (token in facts.signed) is (not revoked)        # still a device token under a live delegation, or dead
        if not revoked:
            assert facts.signed[token]["principal"] == "device:phone"


def test_a_key_delegated_again_after_a_revocation_record_carries_the_anchor_in_both_derivations(tmp_path):
    """Any revocation record removes a device (a restore voids every delegation this way, #186), and the body's rule
    anchors a key delegated after one. founder_facts anchors it too, so a token the key signed while it stood voided
    counts in neither (the port's founder_facts anchored only after a signed DEVICE_REVOKE)."""
    home, key, body_id, phone, phone_public, clock, grant = _world(tmp_path)
    request = {"request_id": "req-voided", "answer": "approve"}
    with Body(home, clock=clock) as body:
        body.apply(signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), channel="inbox")
        clock.advance(10)
        body.journal.record("device.revoked", {"device_key_id": key_id(phone_public), "command_digest": "voided",
                                               "at": iso(clock.now)}, key=[key_id(phone_public), "voided"])
        clock.advance(10)
        voided = signed(phone, body_id, "DECISION", request, now=clock.now)
        clock.advance(10)
        body.apply(signed(key, body_id, "DEVICE_ENROLL", grant, now=clock.now), channel="inbox")
        assert _view(body.device_keys()) == _view(gg.founder_facts(body.ledger).devices)
        assert body.device_keys()[key_id(phone_public)]["signed_not_before"] == iso(clock.now)
        with pytest.raises(FounderAuthError, match=REFUSED):
            body.verifier().verify(voided, now=clock.now)
        assert _accept(body, clock, voided) not in gg.founder_facts(body.ledger).signed
