"""C.G9: the independent appraiser audits the Genesis chain and who attached a formed capability.

Before this, the separate-process appraisal read a formed capability's attach state as retained and never asked how
it became ATTACHED. A ``capability.state ATTACHED`` record with no founder command behind it (written by a faulty or
subverted engine, or injected into the journal) served a mission, and the appraisal still returned VERIFIED. Now
every receipt a capability that is not built in served must be preceded on the ledger by the whole chain:
``deficit.opened`` -> passing ``genesis.verified`` -> ``capability.registered`` -> ``capability.state ATTACHED``,
where the attach is a founder-signed CAPABILITY_ATTACH that re-verifies, or a signed mission's ``auto_attach`` for a
read-only capability inside its light cone.
"""
from __future__ import annotations

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg.body import Body  # noqa: E402
from greg.templates import network_in_words  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402
from tests.unit.test_greg_open_source_genesis import ROUTE, receipts, ticks  # noqa: E402

CHECK = "formed_capabilities_authorized"


def _appraisal(body):
    return body.journal.replay("mission.appraised")[-1].payload


def _waiting_for_attach(tmp_path, *, auto_attach=False):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", network_in_words(text=ROUTE, auto_attach=auto_attach)))
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    return home, key, body_id, clock, body


def _verified_candidate(body):
    [ask] = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "CAPABILITY_ATTACH"]
    [verified] = [c for c in ask["evidence"]["registered"] if c["state"] == "VERIFIED"]
    return verified["capability_id"]


def _forge_attach(body, cid, **payload):
    """What a faulty engine or an injected record does: the state changes, and no founder command carries it."""
    body.registry.set_state(cid, "ATTACHED")
    body.journal.record("capability.state", {"capability_id": cid, "state": "ATTACHED", **payload},
                        key=[cid, "forged", sorted(payload)])


def test_a_founder_signed_attach_keeps_the_closure_verified(tmp_path):
    home, key, body_id, clock, body = _waiting_for_attach(tmp_path)
    ticks(body, clock, 2)
    cid = _verified_candidate(body)
    body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
    assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 2)]
    judged = _appraisal(body)
    assert judged["verdict"] == "VERIFIED" and judged["checks"][CHECK] is True, judged
    body.close()


def test_a_signed_read_only_auto_attach_keeps_the_closure_verified(tmp_path):
    home, key, body_id, clock, body = _waiting_for_attach(tmp_path, auto_attach=True)
    assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
    judged = _appraisal(body)
    assert judged["verdict"] == "VERIFIED" and judged["checks"][CHECK] is True, judged
    body.close()


@pytest.mark.parametrize("payload, why", [
    ({}, "no founder command"),                                                     # nothing names an authority
    ({"by": "founder command"}, "no founder command"),                              # claims one, cites none
    ({"by": "founder command", "command_digest": "0" * 64}, "no founder command"),  # cites one that was never accepted
    ({"by": "founder-signed mission auto_attach (read_only)", "mission_id": "m:nowhere"}, "no signed mission"),
])
def test_an_attach_no_founder_authority_carries_refutes_the_closure(tmp_path, payload, why):
    home, key, body_id, clock, body = _waiting_for_attach(tmp_path)
    ticks(body, clock, 2)
    cid = _verified_candidate(body)
    assert not receipts(body)
    _forge_attach(body, cid, **payload)
    assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 2)]       # the forged attach served the mission
    judged = _appraisal(body)
    assert judged["verdict"] == "REFUTED" and judged["checks"][CHECK] is False, judged
    assert any(cid in f and why in f for f in judged["findings"]), judged["findings"]
    body.close()


def test_a_founder_command_for_another_capability_does_not_authorize_this_one(tmp_path):
    """A real, verified founder command is reused for a capability it does not name."""
    home, key, body_id, clock, body = _waiting_for_attach(tmp_path)
    ticks(body, clock, 2)
    cid = _verified_candidate(body)
    pause = signed(key, body_id, "BODY_PAUSE", {})
    body.apply(pause)
    body.apply(signed(key, body_id, "BODY_RESUME", {}))
    [paused] = [e.payload for e in body.journal.replay("body.paused")]
    _forge_attach(body, cid, by="founder command", command_digest=paused["command_digest"])
    assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 2)]
    judged = _appraisal(body)
    assert judged["verdict"] == "REFUTED" and judged["checks"][CHECK] is False, judged
    assert any(cid in f and "CAPABILITY_ATTACH" in f for f in judged["findings"]), judged["findings"]
    body.close()


def _served(body):
    """(capability id, receipt seq) of the formed capability that served the closed mission, from its own ledger."""
    served = [e.payload for e in body.journal.replay("mission.action") + body.journal.replay("mission.observed")
              if str(e.payload.get("capability", "")).startswith("acquired.") and e.payload.get("receipt")]
    return served[0]["capability"], body.ledger.find(served[0]["receipt"]).seq


def test_the_chain_check_also_holds_where_the_dispatch_gate_does_not_reach(tmp_path, monkeypatch):
    """The cone, the read-only rule and the cognition rule also gate dispatch, so a forged attach that breaks them
    never reaches a closure through the Body. The appraiser still re-derives each from the ledger on its own, so it
    does not rest on the code it audits: an honest auto-attach ledger, read under each broken premise, is refused."""
    from greg import appraisal
    from greg.capabilities import CapabilityManifest
    from greg.lightcone import LightCone
    home, key, body_id, clock, body = _waiting_for_attach(tmp_path, auto_attach=True)
    assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
    cid, served = _served(body)
    seq = {r.payload.get("event_id"): r.seq for r in body.ledger.by_type("event")}
    audit = lambda: appraisal._formed_attach_unauthorized(body.journal, body.ledger, seq, cid, served)  # noqa: E731
    assert audit() is None                                                    # the honest ledger
    with monkeypatch.context() as m:
        m.setattr(LightCone, "_capability_inside", lambda self, c: False)
        assert "light cone" in audit()
    real = CapabilityManifest.from_dict
    with monkeypatch.context() as m:
        m.setattr(CapabilityManifest, "from_dict", staticmethod(
            lambda d: real({**d, "consequence_class": "external_contact"})))
        assert "read_only capabilities only" in audit()
    with monkeypatch.context() as m:
        m.setattr(CapabilityManifest, "from_dict", staticmethod(lambda d: real({**d, "function": "cognition.x"})))
        assert "formed for cognition" in audit()
    assert audit() is None and appraisal._formed_attach_unauthorized(
        body.journal, body.ledger, seq, cid, 1) and "registered" in appraisal._formed_attach_unauthorized(
        body.journal, body.ledger, seq, cid, 1)                                # before it existed, it could not serve
    body.close()


def test_an_injected_attach_command_another_key_signed_refutes_the_closure(tmp_path):
    """A well-formed CAPABILITY_ATTACH naming this capability and the enrolled founder key id, signed by a stranger,
    written into the journal as if accepted: only the signature, re-verified against the enrolled key, refuses it."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from provenance.ledger import sha256_json
    home, key, body_id, clock, body = _waiting_for_attach(tmp_path)
    ticks(body, clock, 2)
    cid = _verified_candidate(body)
    [enrolled] = [e.payload["key_id"] for e in body.journal.replay("founder.enrolled")]
    env = signed(Ed25519PrivateKey.generate(), body_id, "CAPABILITY_ATTACH", {"capability_id": cid})
    env["founder_key_id"] = enrolled
    digest = sha256_json(env)
    body.journal.record("command.accepted", {"kind": "CAPABILITY_ATTACH", "digest": digest, "nonce": env["nonce"],
                                             "founder_key_id": enrolled, "envelope": env, "channel": "inbox",
                                             "result": {"capability_id": cid, "state": "ATTACHED"}}, key=digest)
    _forge_attach(body, cid, by="founder command", command_digest=digest)
    assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 2)]
    judged = _appraisal(body)
    assert judged["verdict"] == "REFUTED" and judged["checks"][CHECK] is False, judged
    assert any(cid in f and "re-verifies" in f for f in judged["findings"]), judged["findings"]
    body.close()
