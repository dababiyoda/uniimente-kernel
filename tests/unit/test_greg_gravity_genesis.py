"""Acceptance C.G11: an egregore Goal Gravity capability deficit is routed into GREG Capability Genesis.

An egregore ``GoalGravityLoop`` goal whose active plan node requires ``hash.sha256@function`` WAITs and records an
``egregore.capability_deficit``. ``greg.gravity_genesis.draft_missions`` turns it into an unsigned GREG mission draft
(never signed by GREG; an unsigned copy dropped in the inbox is not applied). After a founder signature (a per-test
key here, not Alfonso's), Genesis acquires the function on the same Body, and the founder attaches it. ``settle`` then
closes the egregore deficit with a link to GREG's ``deficit.resolved`` and the next gravity turn classifies the move
instead of WAITing. Ablation: without ``settle``, the same goal still WAITs.

The egregore runtime keeps its own evidence ledger (as it does outside a Body); the adapter bridges it to the Body.
Hosting the unsigned egregore goal on the Body's ledger instead is refused by the Body's own admission check, which
quarantines it, and the adapter then drafts nothing (negative control). SANDBOX: in-process Body, test clock.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest

from capabilities.genome import GenomeRegistry
from egregore.goals import GoalSpec, PlanNode, WakeCondition
from egregore.gravity import GoalGravityLoop
from greg import genesis as genesis_mod
from greg import gravity_genesis as gg
from greg.body import Body
from compiler.ucl_compiler import compile_constitution
from identity.machine_passport import PassportRegistry
from provenance.ledger import EvidenceLedger
from tests.unit.test_goal_gravity import ROOT
from tests.greg_fixtures import Clock, make_body, signed
from tests.unit.test_goal_gravity import AUTH_REF, T0, T1, T2, brief_move, governor, obs, signal
from tests.unit.test_greg_missions import events, run, submit

CAP = "hash.sha256@function"


def digest_check(path, content: bytes) -> dict:
    return {"check_id": "hashed", "description": "digest of the evidence file known",
            "sensor": {"function": "hash.sha256", "params": {"path": str(path)}, "target": f"fs:{path.name}"},
            "predicate": {"op": "equals", "field": "sha256", "value": hashlib.sha256(content).hexdigest()}}


def goal(requires=(CAP,)) -> GoalSpec:
    return GoalSpec.build(
        founder_intent="Keep a verifiable digest of every evidence file I hand GREG.",
        desired_state="every evidence file has a verified digest", priority=2,
        authority={"authorized_by": "alfonso_lopez", "authorization_ref": AUTH_REF,
                   "legal_principal": "alfonso_lopez", "max_consequence_class": "internal_write"},
        time_horizon="months",
        plan=[PlanNode.build(node_id="D1", outcome="evidence digested", gate="digest available",
                             sbm="evidence.digested", sbm_direction="eq", sbm_target=True,
                             interventions=(brief_move(),), requires_capabilities=requires)],
        wake_conditions=(WakeCondition.build(kind="tag", match="evidence"),))


class Harness:
    def __init__(self, tmp_path):
        if genesis_mod.installed_binary("sha256sum") is None and genesis_mod.installed_binary("shasum") is None:
            pytest.skip("no sha256 tool installed on this body; Genesis would correctly escalate")
        self.home, self.key, self.body_id, data = make_body(tmp_path)
        self.evidence = data / "evidence.bin"
        self.evidence.write_bytes(b"founder evidence bytes")
        self.passports = PassportRegistry()
        self.actor = self.passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                                          legal_principal="alfonso_lopez", declared_capabilities=["research.brief"],
                                          budget_ceiling_usd=5.0, consequence_class="internal_write")
        self.genomes = GenomeRegistry()        # the egregore repertoire
        self.compiled = compile_constitution(ROOT)
        self.ledger = EvidenceLedger(self.compiled.constitution_hash)   # the egregore runtime's own ledger
        self.clock = Clock()
        self.seen = 0

    def loop(self, body=None, *, ledger=None) -> GoalGravityLoop:
        return GoalGravityLoop(ledger=ledger or self.ledger, compiled=self.compiled, passports=self.passports,
                               actor=self.actor.passport_id, legal_principal="alfonso_lopez", genomes=self.genomes)

    def turn(self, body, trigger, at, *, ledger=None):
        self.seen += 1                      # new evidence each turn, so the dormant goal wakes
        t = self.loop(ledger=ledger).turn(trigger_id=trigger, now=at, resources=governor(), evidence_confidence=0.9,
                                 signals=[signal(f"s-{trigger}", tags=["evidence"],
                                                 observations=[obs("evidence", "count", self.seen)])])
        return [d["decision"] for p in t.processed for d in p["decisions"]]

    def blocked_goal(self):
        with Body(self.home) as b:
            gid = self.loop().registry.authorize(goal(), now=T0)
            assert self.turn(b, "t1", T1) == ["WAIT"]
            [deficit] = gg.open_deficits(self.ledger)
        assert deficit["missing_capabilities"] == [CAP] and deficit["disposition"] == "goal_blocked_not_closed"
        return gid, deficit

    def draft(self):
        with Body(self.home) as b:
            return gg.draft_missions(self.ledger, self.loop().registry, b.genesis, checks={"hash.sha256": digest_check(
                self.evidence, b"founder evidence bytes")}, now=datetime.now(timezone.utc))

    def sign_and_form(self, spec):
        submit(self.home, self.key, self.body_id, "MISSION", spec)
        missions, requests = run(self.home, self.clock, ticks=4)
        return missions, requests


def test_a_gravity_deficit_becomes_an_unsigned_draft_genesis_forms_it_and_the_goal_resumes(tmp_path):
    h = Harness(tmp_path)
    gid, deficit = h.blocked_goal()
    out = h.draft()
    [draft] = out["drafts"]
    spec = draft["body"]
    # Drafted, never signed: GREG holds no key here and the founder must sign.
    assert draft["signed"] is False and draft["requires_founder_signature"] is True
    assert not {"signature", "nonce", "signer"} & (set(draft) | set(spec)) and "auto_attach" not in spec
    assert spec["light_cone"]["max_consequence_class"] == "read_only" and spec["light_cone"]["budget_usd"] == 0.0
    assert spec["light_cone"]["capabilities"] == ["acquired.hash.sha256.*"]
    assert spec["provenance"]["origin"] == f"egregore.capability_deficit:{deficit['deficit_id']}"
    assert spec["founder_expression"] == deficit["founder_intent"]
    assert h.draft()["drafts"][0]["body"]["mission_id"] == spec["mission_id"]    # stable identity, recorded once
    with Body(h.home) as b:
        assert len(h.ledger.by_type(gg.DRAFT_RECORD)) == 1

    # An unsigned draft dropped in the inbox is not applied.
    (h.home / "inbox" / "unsigned-draft.json").write_text(json.dumps(spec))
    missions, _ = run(h.home, h.clock, ticks=2)
    assert spec["mission_id"] not in missions

    # Founder signs; Genesis acquires the function but waits for the founder's attach.
    missions, requests = h.sign_and_form(spec)
    m = missions[spec["mission_id"]]
    assert m.status == "ACTIVE" and m.blocker["type"] == "capability"
    assert [r["kind"] for r in requests] == ["CAPABILITY_ATTACH"]
    with Body(h.home) as b:
        assert gg.settle(h.ledger, h.loop().registry, h.genomes, b, now=T2) == []   # nothing before the attach
        assert h.turn(b, "t1b", T2) == ["WAIT"]
    [verified] = [e for e in events(h.home, "genesis.verified") if e["passed"]]
    cid = verified["capability_id"]
    assert cid.startswith("acquired.hash.sha256.")

    with Body(h.home) as b:
        assert b.apply(signed(h.key, h.body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))["status"] == "APPLIED"
        attach_digest = [e for e in [x.payload for x in b.journal.replay("capability.state")]
                         if e["capability_id"] == cid and e.get("by") == "founder command"][-1]["command_digest"]
    missions, _ = run(h.home, h.clock, ticks=4)
    assert missions[spec["mission_id"]].status == "ACHIEVED"
    [opened] = [e for e in events(h.home, "deficit.opened") if e["mission_id"] == spec["mission_id"]]
    # GREG records no deficit.resolved after a founder attach (greg/body.py); settle links the signed attach instead.
    assert [e for e in events(h.home, "deficit.resolved") if e["mission_id"] == spec["mission_id"]] == []

    with Body(h.home) as b:
        [row] = gg.settle(h.ledger, h.loop().registry, h.genomes, b, now=T2)
        assert gg.settle(h.ledger, h.loop().registry, h.genomes, b, now=T2) == []     # idempotent
        assert row["greg_deficit_id"] == opened["deficit_id"] and row["capability_id"] == cid
        assert gg.open_deficits(h.ledger) == []
        closed = [r.payload["deficit"] for r in h.ledger.by_type(gg.DEFICIT_RECORD)][-1]
        assert closed["disposition"] == "resolved_resume_original_goal"
        assert closed["resolved_by"] == f"greg:founder_attach:{opened['deficit_id']}:{cid}:{attach_digest}"
        reg = h.loop().registry
        assert reg.state(gid).missing_capabilities == []
        assert reg.get(gid).to_dict() == goal().to_dict()                  # the original goal is untouched
        decisions = h.turn(b, "t2", T2)
    assert decisions and "WAIT" not in decisions


def test_ablation_without_settle_the_goal_stays_blocked(tmp_path):
    h = Harness(tmp_path)
    h.blocked_goal()
    [draft] = h.draft()["drafts"]
    spec = draft["body"]
    h.sign_and_form(spec)
    [verified] = [e for e in events(h.home, "genesis.verified") if e["passed"]]
    with Body(h.home) as b:
        b.apply(signed(h.key, h.body_id, "CAPABILITY_ATTACH", {"capability_id": verified["capability_id"]}))
    missions, _ = run(h.home, h.clock, ticks=4)
    assert missions[spec["mission_id"]].status == "ACHIEVED"                # GREG has the function ...
    with Body(h.home) as b:
        assert h.turn(b, "t2", T2) == ["WAIT"]                              # ... but the goal never learns it
        assert len(gg.open_deficits(h.ledger)) == 1


def test_unformable_or_mismatched_functions_are_not_drafted(tmp_path):
    h = Harness(tmp_path)
    h.blocked_goal()
    reg = h.loop().registry
    with Body(h.home) as b:
        wrong = digest_check(h.evidence, b"x")
        wrong["sensor"] = {"capability": "fs.read", "params": {"path": str(h.evidence)}, "target": "fs:evidence.bin"}
        out = gg.draft_missions(h.ledger, reg, b.genesis, checks={"hash.sha256": wrong}, now=T1)
        assert out["drafts"] == [] and "does not call hash.sha256" in out["unrouted"][0]["reason"]
        out = gg.draft_missions(h.ledger, reg, b.genesis, checks={}, now=T1)
        assert out["drafts"] == [] and out["unrouted"][0]["reason"] == "no founder check senses this function"
        assert h.ledger.by_type(gg.DRAFT_RECORD) == []


def test_a_capability_that_is_not_a_greg_function_is_reported_not_drafted(tmp_path):
    h = Harness(tmp_path)
    with Body(h.home) as b:
        h.loop().registry.authorize(goal(requires=("brief.compiler@1.0",)), now=T0)
        assert h.turn(b, "t1", T1) == ["WAIT"]
        out = gg.draft_missions(h.ledger, h.loop().registry, b.genesis, checks={}, now=T1)
    assert out["drafts"] == []
    assert out["unrouted"] == [{"deficit_id": out["unrouted"][0]["deficit_id"], "capability": "brief.compiler@1.0",
                                "reason": "not a GREG function (<function>@function)"}]


def test_the_adapter_holds_no_signing_path():
    import inspect
    source = inspect.getsource(gg)
    for forbidden in ("sign_command", "founder_key", "private_key", "Ed25519"):
        assert forbidden not in source


def test_an_unsigned_egregore_goal_on_the_body_ledger_is_quarantined_and_never_drafted(tmp_path):
    """Negative control: the Body's admission check stops an egregore goal no founder-signed GOAL authorizes; the
    adapter then routes nothing for it, so an unsigned goal cannot pull Genesis through the Body's own ledger."""
    h = Harness(tmp_path)
    with Body(h.home) as b:
        loop = h.loop(ledger=b.ledger)
        gid = loop.registry.authorize(goal(), now=T0)
        assert h.turn(b, "t1", T1, ledger=b.ledger) == ["WAIT"]
    run(h.home, h.clock, ticks=2)
    with Body(h.home) as b:
        reg = h.loop(ledger=b.ledger).registry
        assert reg.state(gid).preferences.get("stop_pushing") is True
        out = gg.draft_missions(b.ledger, reg, b.genesis, checks={"hash.sha256": digest_check(
            h.evidence, b"founder evidence bytes")}, now=datetime.now(timezone.utc))
        assert out["drafts"] == [] and out["unrouted"][0]["reason"] == "goal is paused"
        assert b.ledger.by_type(gg.DRAFT_RECORD) == []


def test_a_stopped_goal_is_not_settled_even_after_greg_formed_the_function(tmp_path):
    h = Harness(tmp_path)
    gid, _ = h.blocked_goal()
    [draft] = h.draft()["drafts"]
    h.sign_and_form(draft["body"])
    [verified] = [e for e in events(h.home, "genesis.verified") if e["passed"]]
    with Body(h.home) as b:
        b.apply(signed(h.key, h.body_id, "CAPABILITY_ATTACH", {"capability_id": verified["capability_id"]}))
    run(h.home, h.clock, ticks=4)
    reg = h.loop().registry
    reg.record_preference(gid, kind="stop_pushing", value=True, actor="alfonso_lopez", reason="founder stop", now=T2)
    with Body(h.home) as b:
        assert gg.settle(h.ledger, reg, h.genomes, b, now=T2) == []
    assert len(gg.open_deficits(h.ledger)) == 1 and h.genomes.get("hash.sha256", "function") is None


def test_a_founder_who_signs_the_draft_with_auto_attach_settles_through_deficit_resolved(tmp_path):
    """The founder may widen the draft before signing (here: a read-only auto_attach). GREG then writes
    deficit.resolved itself, and settle links that record."""
    h = Harness(tmp_path)
    gid, _ = h.blocked_goal()
    [draft] = h.draft()["drafts"]
    spec = {**draft["body"], "auto_attach": {"max_consequence_class": "read_only"}}
    missions, _ = h.sign_and_form(spec)
    assert missions[spec["mission_id"]].status == "ACHIEVED"
    [resolved] = [e for e in events(h.home, "deficit.resolved") if e["mission_id"] == spec["mission_id"]]
    with Body(h.home) as b:
        [row] = gg.settle(h.ledger, h.loop().registry, h.genomes, b, now=T2)
        assert row["link"] == f"greg:deficit.resolved:{resolved['deficit_id']}:{resolved['capability_id']}"
        assert h.turn(b, "t2", T2) != ["WAIT"]


def test_a_detached_capability_does_not_settle(tmp_path):
    h = Harness(tmp_path)
    h.blocked_goal()
    [draft] = h.draft()["drafts"]
    h.sign_and_form(draft["body"])
    [verified] = [e for e in events(h.home, "genesis.verified") if e["passed"]]
    cid = verified["capability_id"]
    with Body(h.home) as b:
        b.apply(signed(h.key, h.body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
        b.apply(signed(h.key, h.body_id, "CAPABILITY_DETACH", {"capability_id": cid}))
        assert gg.settle(h.ledger, h.loop().registry, h.genomes, b, now=T2) == []
        assert h.turn(b, "t2", T2) == ["WAIT"]


def test_a_revoked_goal_is_neither_drafted_for_nor_settled(tmp_path):
    h = Harness(tmp_path)
    gid, _ = h.blocked_goal()
    [draft] = h.draft()["drafts"]
    h.sign_and_form(draft["body"])
    [verified] = [e for e in events(h.home, "genesis.verified") if e["passed"]]
    with Body(h.home) as b:
        b.apply(signed(h.key, h.body_id, "CAPABILITY_ATTACH", {"capability_id": verified["capability_id"]}))
    reg = h.loop().registry
    reg.revoke(gid, actor="alfonso_lopez", reason="founder revoked the goal", now=T2)
    with Body(h.home) as b:
        assert gg.settle(h.ledger, reg, h.genomes, b, now=T2) == []
        out = gg.draft_missions(h.ledger, reg, b.genesis, checks={}, now=datetime.now(timezone.utc))
    assert out["drafts"] == [] and out["unrouted"][0]["reason"] == "goal is revoked"


def test_a_function_genesis_cannot_form_without_a_builder_stays_with_the_founder(tmp_path):
    h = Harness(tmp_path)
    with Body(h.home) as b:
        h.loop().registry.authorize(goal(requires=("vision.read_plate@function",)), now=T0)
        assert h.turn(b, "t1", T1) == ["WAIT"]
        check = digest_check(h.evidence, b"founder evidence bytes")
        check["sensor"]["function"] = "vision.read_plate"
        out = gg.draft_missions(h.ledger, h.loop().registry, b.genesis, checks={"vision.read_plate": check},
                                now=datetime.now(timezone.utc))
    assert out["drafts"] == [] and "cannot form" in out["unrouted"][0]["reason"]


def test_a_partly_formed_deficit_keeps_its_other_need_and_settles_once(tmp_path):
    """Two needs: GREG forms hash.sha256; brief.compiler@1.0 is not a GREG function. The goal sheds only the formed
    one, the egregore deficit stays open, and a second settle records nothing more."""
    h = Harness(tmp_path)
    with Body(h.home) as b:
        gid = h.loop().registry.authorize(goal(requires=(CAP, "brief.compiler@1.0")), now=T0)
        assert h.turn(b, "t1", T1) == ["WAIT"]
    [draft] = h.draft()["drafts"]
    h.sign_and_form(draft["body"])
    [verified] = [e for e in events(h.home, "genesis.verified") if e["passed"]]
    with Body(h.home) as b:
        b.apply(signed(h.key, h.body_id, "CAPABILITY_ATTACH", {"capability_id": verified["capability_id"]}))
        reg = h.loop().registry
        [row] = gg.settle(h.ledger, reg, h.genomes, b, now=T2)
        assert row["deficit_closed"] is False
        assert gg.settle(h.ledger, reg, h.genomes, b, now=T2) == []
        assert len(h.ledger.by_type(gg.SETTLED_RECORD)) == 1
        assert reg.state(gid).missing_capabilities == ["brief.compiler@1.0"]
        assert len(gg.open_deficits(h.ledger)) == 1
        assert h.turn(b, "t2", T2) == ["WAIT"]
