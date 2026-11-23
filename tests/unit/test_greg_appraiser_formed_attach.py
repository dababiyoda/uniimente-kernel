"""Acceptance C.G9: the independent appraiser audits the genesis chain and the attach authority of formed capabilities.

A capability Capability Genesis formed (here a built one) has no reviewed code behind it. What makes its readings
admissible is the chain on the ledger (deficit opened, candidate verified by the frozen oracle, registered) and an
attach the founder authorized: his signed CAPABILITY_ATTACH, or a signed mission's read-only auto_attach whose light
cone holds the capability. The appraiser, in its separate process over the read-only ledger, now checks both for
every receipt a closure rests on (``formed_capabilities_authorized``).

Honest paths stay VERIFIED: an auto-attach, a founder attach, and a later mission reusing the capability another
mission's scope attached. Two forgeries are REFUTED with the finding: an ATTACHED state journaled by hand with no
command behind it, and an auto-attach claimed under a mission whose signed scope does not cover the capability.

In-process Body with a test clock and a deterministic builder (SANDBOX); the founder key is a per-test key.
"""
from __future__ import annotations

from greg import builders
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed
from tests.unit.test_greg_genesis_builder import CONTRACT, FUNCTION, GOOD

DOC, COUNT = "- [ ] a\n- [x] b\n* [ ] c\n", 2


def _spec(data, mission_id, *, auto_attach=True, cone=None):
    doc = data / f"{mission_id.replace(':', '_')}.md"
    doc.write_text(DOC)
    check = {"check_id": "open-items-counted", "description": "the number of open items is known",
             "sensor": {"function": FUNCTION, "params": {"path": str(doc)}, "target": f"fs:{doc.name}"},
             "predicate": {"op": "equals", "field": "unchecked", "value": COUNT}}
    spec = mission(mission_id, checks=[check], strategies=[], ceiling="read_only", budget=1.0,
                   capabilities=cone or ["fs.read", f"built.{FUNCTION}.*"], auto_attach=auto_attach)
    spec["capability_specs"] = [dict(CONTRACT)]
    return spec


def _tick(home, ticks=4, builder=None):
    clock = Clock()
    body = Body(home, clock=clock, builder=builder or builders.StaticBuilder(GOOD, identity="static-test")).open()
    body.boot()
    for _ in range(ticks):
        clock.advance(30)
        body.tick()
    return body


def _appraisal(body, mission_id):
    found = [e.payload for e in body.journal.replay("mission.appraised") if e.payload.get("mission_id") == mission_id]
    assert found, f"{mission_id} was appraised"
    return found[-1]


def _formed_waiting(tmp_path):
    """A capability built and VERIFIED for a mission that does not pre-authorize its attach."""
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, "m:waits", auto_attach=False)))
    body = _tick(home, ticks=3)
    try:
        cid = body.journal.replay("capability.registered")[0].payload["manifest"]["capability_id"]
        assert body.registry.state[cid] == "VERIFIED" and body.journal.replay("deficit.awaiting_attach")
        assert not body.journal.replay("mission.appraised")
    finally:
        body.close()
    return home, key, body_id, data, cid


def test_honest_auto_attach_and_its_later_reuse_are_verified(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, "m:forms")))
    body = _tick(home)
    body.close()
    drop(home, signed(key, body_id, "MISSION", _spec(data, "m:reuses")))     # another mission, same capability
    body = _tick(home)
    try:
        for mission_id in ("m:forms", "m:reuses"):
            appraisal = _appraisal(body, mission_id)
            assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
            assert appraisal["checks"]["formed_capabilities_authorized"] is True
        assert len(body.journal.replay("deficit.opened")) == 1
    finally:
        body.close()


def test_a_founder_signed_attach_is_verified(tmp_path):
    home, key, body_id, data, cid = _formed_waiting(tmp_path)
    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
    body = _tick(home)
    try:
        appraisal = _appraisal(body, "m:waits")
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        assert appraisal["checks"]["formed_capabilities_authorized"] is True
    finally:
        body.close()


def test_an_attach_journaled_by_hand_with_no_command_is_refuted(tmp_path):
    home, key, body_id, data, cid = _formed_waiting(tmp_path)
    with Body(home) as body:                              # the forgery: state set and journaled, no signed command
        body.registry.set_state(cid, "ATTACHED")
        body.journal.record("capability.state", {"capability_id": cid, "state": "ATTACHED", "by": "founder command",
                                                 "command_digest": "sha256:" + "0" * 64}, key=[cid, "forged"])
    body = _tick(home)
    try:
        assert any(e.payload["mission_id"] == "m:waits" for e in body.journal.replay("mission.achieved")), \
            "the body itself trusted the forged state and closed the mission"
        appraisal = _appraisal(body, "m:waits")
        assert appraisal["verdict"] == "REFUTED"
        assert appraisal["checks"]["formed_capabilities_authorized"] is False
        assert any(cid in f and "without founder authority" in f and "CAPABILITY_ATTACH" in f
                   for f in appraisal["findings"])
    finally:
        body.close()


def test_an_auto_attach_claimed_under_a_scope_that_does_not_cover_it_is_refuted(tmp_path):
    home, key, body_id, data, cid = _formed_waiting(tmp_path)
    # A real, signed mission whose cone holds only fs.read: the forged record names it as the authority.
    note = data / "narrow.txt"
    note.write_text("here")
    drop(home, signed(key, body_id, "MISSION", mission("m:narrow", checks=[note_check("n", note, "here")],
                                                       strategies=[], ceiling="read_only", capabilities=["fs.read"],
                                                       auto_attach=True)))
    narrow = _tick(home, ticks=1)
    try:
        assert any(e.payload.get("kind") == "MISSION" and e.payload["envelope"]["body"]["mission_id"] == "m:narrow"
                   for e in narrow.journal.replay("command.accepted")), "the narrow mission is a real signed one"
    finally:
        narrow.close()
    with Body(home) as body:
        body.registry.set_state(cid, "ATTACHED")
        body.journal.record("capability.state", {"capability_id": cid, "state": "ATTACHED",
                                                 "by": "founder-signed mission auto_attach (read_only)",
                                                 "mission_id": "m:narrow"}, key=[cid, "forged-scope"])
    body = _tick(home)
    try:
        appraisal = _appraisal(body, "m:waits")
        assert appraisal["verdict"] == "REFUTED"
        assert any(cid in f and "m:narrow" in f and "does not pre-authorize" in f for f in appraisal["findings"])
    finally:
        body.close()


def test_a_forged_command_acceptance_signed_by_an_unenrolled_key_is_refuted(tmp_path):
    """Whoever can journal a state by hand can journal a command's acceptance too. The appraiser re-verifies the
    retained envelope against the founder keys enrolled at the time, so an acceptance record is not authority."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from greg.founder import sign_command
    from provenance.ledger import sha256_json

    home, key, body_id, data, cid = _formed_waiting(tmp_path)
    impostor = sign_command(Ed25519PrivateKey.generate(), "CAPABILITY_ATTACH", {"capability_id": cid}, body_id=body_id)
    digest = sha256_json(impostor)
    with Body(home) as body:
        body.registry.set_state(cid, "ATTACHED")
        body.journal.record("capability.state", {"capability_id": cid, "state": "ATTACHED", "by": "founder command",
                                                 "command_digest": digest}, key=[cid, "forged-accepted"])
        body.journal.record("command.accepted", {"kind": "CAPABILITY_ATTACH", "digest": digest,
                                                 "nonce": impostor["nonce"], "founder_key_id": impostor["founder_key_id"],
                                                 "envelope": impostor, "channel": "inbox",
                                                 "result": {"capability_id": cid, "state": "ATTACHED"}}, key=digest)
    body = _tick(home)
    try:
        appraisal = _appraisal(body, "m:waits")
        assert appraisal["verdict"] == "REFUTED"
        assert any(cid in f and "founder-signed CAPABILITY_ATTACH" in f for f in appraisal["findings"])
    finally:
        body.close()


def test_an_attach_with_an_unknown_authority_is_refuted(tmp_path):
    home, key, body_id, data, cid = _formed_waiting(tmp_path)
    with Body(home) as body:
        body.registry.set_state(cid, "ATTACHED")
        body.journal.record("capability.state", {"capability_id": cid, "state": "ATTACHED", "by": "operator console"},
                            key=[cid, "forged-by"])
    body = _tick(home)
    try:
        appraisal = _appraisal(body, "m:waits")
        assert appraisal["verdict"] == "REFUTED"
        assert any(cid in f and "operator console" in f for f in appraisal["findings"])
    finally:
        body.close()


def test_an_attach_set_in_memory_and_never_journaled_is_refuted(tmp_path):
    """The gap's own forgery: registry.set_state in the running body, with no state change on the ledger at all."""
    home, key, body_id, data, cid = _formed_waiting(tmp_path)
    clock = Clock()
    body = Body(home, clock=clock, builder=builders.StaticBuilder(GOOD, identity="static-test")).open()
    try:
        body.boot()
        body.registry.set_state(cid, "ATTACHED")
        for _ in range(4):
            clock.advance(30)
            body.tick()
        assert not [e for e in body.journal.replay("capability.state") if e.payload.get("state") == "ATTACHED"]
        appraisal = _appraisal(body, "m:waits")
        assert appraisal["verdict"] == "REFUTED"
        assert any(cid in f and "not ATTACHED by any recorded state change" in f for f in appraisal["findings"])
    finally:
        body.close()
