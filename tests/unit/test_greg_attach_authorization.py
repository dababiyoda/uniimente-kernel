"""Hostile controls on attaching an acquired capability (acceptance C.G8).

Attaching is the step that lets GREG use what Genesis acquired. It happens only by a founder-signed
CAPABILITY_ATTACH, or by a founder-signed mission's read-only ``auto_attach`` whose light cone already
contains the capability. These tests attack each route:

(a) a capability quarantined for real (its binary changed after verification) cannot be attached;
(b) an id that was never registered cannot be attached;
(c) ``auto_attach`` does not reach past the light cone: the result waits for the founder, nothing runs;
(d) a CAPABILITY_ATTACH signed by a key the body never enrolled is rejected;
(e) a model-drafted mission never carries ``auto_attach``.
"""
import hashlib
import json
import shutil

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from greg import genesis as genesis_mod
from greg import planner
from greg.body import Body
from greg.capabilities import installed_binary
from greg.founder import FounderAuthError
from greg.missions import MissionError
from provenance.ledger import sha256_json
from tests.greg_fixtures import Clock, drop, make_body, mission, signed
from tests.unit.test_greg_interface import GOOD, FakeModel, inventory

SHA256SUM = installed_binary("sha256sum")
needs_sha256sum = pytest.mark.skipif(not SHA256SUM, reason="sha256sum is needed on this host")
CID = "acquired.hash.sha256.sha256sum"


def _hash_spec(data, *, capabilities=("fs.read", "acquired.hash.sha256.*")):
    doc = data / "notes.txt"
    doc.write_text("attach\n")
    check = {"check_id": "digest", "description": "the notes have the founder's expected digest",
             "sensor": {"function": "hash.sha256", "params": {"path": str(doc)}, "target": "fs:notes.txt"},
             "predicate": {"op": "equals", "field": "sha256", "value": hashlib.sha256(b"attach\n").hexdigest()}}
    return mission("m:hash", checks=[check], strategies=[], ceiling="read_only", budget=1.0,
                   capabilities=list(capabilities), auto_attach=True)


def _body(tmp_path, spec, ticks=4):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", spec(data)))
    clock = Clock()
    body = Body(home, clock=clock, builder=None).open()
    body.boot()
    states = []
    for _ in range(ticks):
        clock.advance(30)
        states.append(body.tick()["missions"][0]["state"])
    return home, key, body_id, body, clock, states


def _attach(body, key, body_id, cid):
    return body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))


@needs_sha256sum
def test_a_capability_quarantined_because_its_binary_changed_cannot_be_attached_by_the_founder(tmp_path, monkeypatch):
    tools = tmp_path / "tools"
    tools.mkdir()
    copy = shutil.copy2(SHA256SUM, tools / "sha256sum")
    real = genesis_mod.installed_binary
    monkeypatch.setattr(genesis_mod, "installed_binary", lambda name: str(copy) if name == "sha256sum" else real(name))
    home, key, body_id, body, _, states = _body(tmp_path, _hash_spec)
    assert "ACHIEVED" in states and body.registry.state[CID] == "ATTACHED"
    body.close()
    with open(copy, "ab") as handle:                                  # the binary changes after verification
        handle.write(b"\0")
    with Body(home, clock=Clock()) as reopened:
        assert reopened.registry.state[CID] == "QUARANTINED"
        with pytest.raises(MissionError, match="only verified capabilities may be attached"):
            _attach(reopened, key, body_id, CID)
        assert reopened.registry.state[CID] == "QUARANTINED"
        assert not [e for e in reopened.journal.replay("capability.state")
                    if e.payload["capability_id"] == CID and e.payload.get("by") == "founder command"]


@needs_sha256sum
def test_an_id_never_registered_cannot_be_attached(tmp_path):
    home, key, body_id, body, _, _ = _body(tmp_path, _hash_spec)
    for cid in ("acquired.hash.sha256.sha256sum-impostor", "acquired.hash.sha256.shasum", "built.hash.sha256.x"):
        assert cid not in body.registry.manifests
        with pytest.raises(MissionError, match="unknown capability"):
            _attach(body, key, body_id, cid)
        assert cid not in body.registry.state
    body.close()


@needs_sha256sum
def test_auto_attach_does_not_reach_a_capability_outside_the_light_cone(tmp_path):
    spec = lambda data: _hash_spec(data, capabilities=("fs.read",))             # noqa: E731
    home, key, body_id, body, _, states = _body(tmp_path, spec)
    assert "ACHIEVED" not in states
    assert body.registry.state[CID] == "VERIFIED"                      # formed and verified, never attached
    waiting = [e.payload for e in body.journal.replay("deficit.awaiting_attach")
               if e.payload["capability_id"] == CID]
    assert waiting and waiting[0]["why"] == "mission scope does not pre-authorize this attach"
    assert not [e for e in body.journal.replay("capability.state")
                if e.payload["capability_id"] == CID and e.payload.get("state") == "ATTACHED"]
    receipts = [e.payload for e in body.journal.replay("mission.observed") if e.payload.get("passed")]
    assert receipts == []                                              # nothing ran through it
    asks = [e.payload for e in body.journal.replay("decision.requested")]
    assert [a["kind"] for a in asks] == ["CAPABILITY_ATTACH"], asks       # the founder is asked, once
    body.close()


@needs_sha256sum
def test_an_attach_signed_by_a_key_the_body_never_enrolled_is_rejected(tmp_path):
    spec = lambda data: _hash_spec(data, capabilities=("fs.read",))             # noqa: E731
    home, key, body_id, body, clock, _ = _body(tmp_path, spec)
    before = body.registry.state[CID]
    assert before == "VERIFIED"
    intruder = Ed25519PrivateKey.generate()
    forged = signed(intruder, body_id, "CAPABILITY_ATTACH", {"capability_id": CID})
    drop(home, forged)
    clock.advance(30)
    body.tick()
    rejected = [e.payload for e in body.journal.replay("command.rejected")
                if e.payload.get("digest") == sha256_json(forged)]
    assert len(rejected) == 1 and rejected[0]["reason"].startswith("FounderAuthError"), rejected
    assert not [e for e in body.journal.replay("command.accepted")
                             if e.payload.get("kind") == "CAPABILITY_ATTACH"]
    assert body.registry.state[CID] == "VERIFIED"
    with pytest.raises(FounderAuthError):
        body.apply(forged)                                             # the direct path verifies the signer too
    assert body.registry.state[CID] == "VERIFIED"
    body.close()


def test_a_model_drafted_mission_never_carries_auto_attach():
    draft = {**json.loads(json.dumps(GOOD)), "auto_attach": {"max_consequence_class": "read_only"}}
    ctx = planner.PlannerContext(read_roots=(), capabilities=inventory(), repositories={}, today="2026-09-26")
    proposal = planner.propose("Tell me if my kernel checkout gets dirty", ctx,
                               transport=FakeModel([json.dumps(draft)]))
    assert proposal["status"] == "PROPOSED", proposal
    assert "auto_attach" not in proposal["spec"]
