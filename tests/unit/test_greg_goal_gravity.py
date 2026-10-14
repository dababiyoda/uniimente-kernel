"""Goal Gravity on the GREG body: the canonical persistent operating path (ADR-GOAL-GRAVITY-002).

Every test drives a real Body with a real Ed25519 test founder key (tests.greg_fixtures; NOT Alfonso's key)
and a deterministic clock. Mission F: a founder-signed infinite mission watches c.txt (repair in cone) and
can ship d.txt only with the founder's decision (outside the cone); a founder-signed GOAL binds to it.
Passing these tests proves the mechanism on this tree; it is not evidence of any external effect.
"""
from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from egregore.attention import ANSWER_RECORD, ASK_RECORD
from egregore.contracts import ContractError
from egregore.goals import GoalRegistry, GoalSpec, InterventionSpec, PlanNode, WakeCondition
from egregore.gravity import GoalGravityLoop
from greg import dataplane, goal_gravity as gg, path as devpath
from greg.authority import AuthorityOffice
from greg.body import Body, status
from greg.founder import generate_founder_key, load_founder_key, sign_command
from greg.journal import iso
from greg.missions import MissionBook
from provenance.ledger import sha256_json
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, workspace, write_strategy

MID = "m:watch"
GREG = Path(__file__).resolve().parents[2] / "greg"


def ship_move(**kw):
    base = dict(intervention_id="ship", description="write d.txt (outside the mission's cone)",
                action_class="greg.fs.write", requested_capability="fs.write", consequence_class="internal_write",
                target="workspace:d.txt", expected_outcome="d.txt says shipped",
                payload={"mission_id": MID, "action_id": "w2"})
    base.update(kw)
    return InterventionSpec.build(**base)


def goal_body(*, intent="keep the watch healthy and ship d", moves=None, supersedes=None):
    kw = {"supersedes": supersedes} if supersedes else {}
    spec = GoalSpec.build(
        founder_intent=intent, desired_state="d shipped and N1 reached", priority=2,
        authority={"authorized_by": "x", "authorization_ref": "x", "legal_principal": "alfonso_lopez",
                   "max_consequence_class": "internal_write"}, time_horizon="weeks",
        plan=[PlanNode.build(node_id="ship", outcome="d shipped", gate="founder decides the out-of-cone write",
                             sbm=f"{MID}.d", sbm_direction="eq", sbm_target=True,
                             interventions=tuple(moves if moves is not None else (ship_move(),))),
              PlanNode.build(node_id="n1", outcome="developmental node N1", gate="VEPMC", sbm="greg.path.N1",
                             sbm_direction="eq", sbm_target=True)],
        wake_conditions=(WakeCondition.build(kind="subject", match=MID), WakeCondition.build(kind="domain", match="ops")),
        review_cadence_seconds=7 * 86400, **kw)
    return {k: v for k, v in spec.to_dict().items() if k not in gg.DERIVED_GOAL_FIELDS}


def GOAL(ceiling="internal_write", missions=(MID,), **kw):
    return {"goal": goal_body(**kw), "missions": list(missions), "max_consequence_class": ceiling}


class World:
    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.home, self.key, self.body_id, self.data = make_body(self.tmp)
        self.clock = Clock()
        self.ws = workspace(self.home, MID)

    def mission_spec(self, **kw):
        return mission(MID, checks=[note_check("c", self.ws / "c.txt", "ok"), note_check("d", self.ws / "d.txt", "shipped")],
                       strategies=[write_strategy("w", "c.txt", "ok", ["c"]), write_strategy("w2", "d.txt", "shipped", ["d"])],
                       capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"),
                       closure={"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400}, **kw)

    def sign(self, kind, body, *, key=None, at=None, **kw):
        return sign_command(key or self.key, kind, body, body_id=self.body_id, now=at or self.clock.now, **kw)

    def submit(self, kind, body, name=None, **kw):
        env = self.sign(kind, body, **kw)
        drop(self.home, env, name)
        return env

    def body(self):
        return Body(self.home, clock=self.clock)

    def tick(self, n=1, step=1.0):
        out = []
        with self.body() as b:
            for _ in range(n):
                out.append(b.tick())
                self.clock.advance(step)
        return out

    def start(self, goal=None):
        self.submit("MISSION", self.mission_spec(), "a-mission.json")
        env = self.submit("GOAL", goal or GOAL(), "b-goal.json")
        result = self.tick()[0]
        applied = [c for c in result["commands"] if c["status"] == "APPLIED"]
        assert len(applied) == 2, result["commands"]
        return applied[1]["result"]["goal_id"], env

    def ingest(self, channel, content):
        with self.body() as b:
            return dataplane.ingest(b.journal, source=f"feed://{channel}", content=content, channel=channel)

    def events(self, prefix):
        with self.body() as b:
            return [e.payload for e in b.journal.replay(prefix)]

    def records(self, record_type):
        with self.body() as b:
            return [r.payload for r in b.ledger.by_type(record_type)]

    def count(self):
        with self.body() as b:
            return len(b.ledger.records)

    def book(self):
        with self.body() as b:
            return MissionBook(b.journal)

    def projection(self):
        with self.body() as b:
            return gg.projection(b.journal)

    def registry(self):
        with self.body() as b:
            return GoalRegistry(ledger=b.ledger)

    def rejections(self):
        return [e["reason"] for e in self.events("command.rejected")]

    def w2_requests(self):
        return [r for r in self.events("decision.requested") if r.get("action_id") == "w2"]


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


@pytest.fixture
def fast(monkeypatch):
    """Skip the separate-process appraisal of each mission hold (it is exercised by the end-to-end test)."""
    monkeypatch.setattr(Body, "_close_out", lambda self, now: None)


def expected_w2_request(world) -> tuple[str, str]:
    spec = world.mission_spec()
    s = next(s for s in spec["strategies"] if s["action_id"] == "w2")
    scope = AuthorityOffice.scope_digest(mission_id=MID, capability_id="fs.write", params=s["params"],
                                         target=s["target"], consequence_class="internal_write", cost_usd=0.0)
    return "req-" + sha256_json({"mission": MID, "kind": "APPROVAL", "scope": scope})[7:31], scope


# -- idle bodies and dormancy ----------------------------------------------------------------------------

def test_a_body_without_goals_does_no_gravity_work_and_writes_nothing(world):
    with world.body() as b:
        before = len(b.ledger.records)
        results = [b.tick() for _ in range(3)]
        assert len(b.ledger.records) == before            # an idle body appends nothing
    assert all("gravity" not in r for r in results)
    world.submit("MISSION", world.mission_spec())
    results = world.tick(4)
    assert all("gravity" not in r for r in results)
    with world.body() as b:
        assert not [r for r in b.ledger.records if r.record_type.startswith("egregore.")]
        assert not b.journal.replay("goal")
        assert status(world.home)["gravity"]["goals"] == []


def test_a_dormant_goal_with_no_new_evidence_costs_no_record(world, fast):
    world.start()
    world.tick(6)                                          # the mission repairs c, asks about d, holds
    with world.body() as b:
        before = len(b.ledger.records)
        result = b.tick()
        assert result["gravity"]["state"] == "DORMANT" and len(b.ledger.records) == before


# -- the founder-signed GOAL lives on the one ledger ------------------------------------------------------

def test_a_signed_goal_lives_on_the_body_ledger_and_survives_restart(world, fast):
    at = iso(world.clock.now)
    gid, env = world.start()
    authorized = world.records(GoalRegistry.AUTHORIZED_RECORD)
    assert len(authorized) == 1 and authorized[0]["goal"]["goal_id"] == gid
    assert authorized[0]["goal"]["authority"]["authorization_ref"] == sha256_json(env)
    assert authorized[0]["goal"]["authority"]["missions"] == [MID]
    assert authorized[0]["authorized_at"] == at            # the body clock, never the envelope's
    assert sorted(p.name for p in world.home.iterdir() if p.name.startswith("ledger")) == ["ledger.jsonl", "ledger.jsonl.lock"]
    view = world.projection()                               # a fresh process view
    assert [g["goal_id"] for g in view["goals"]] == [gid] and view["goals"][0]["admitted"] is True
    assert view["goals"][0]["status"] == "dormant" and view["unadmitted"] == []


# -- Mission F end to end ---------------------------------------------------------------------------------

def test_mission_F_end_to_end(world):
    gid, _ = world.start()
    rid, scope = expected_w2_request(world)
    world.tick(3)
    # Permitted preparation inside the cone ran through the Gate: c.txt repaired with a receipt.
    book = world.book()
    assert (world.ws / "c.txt").read_text() == "ok" and book.missions[MID].rung == 1
    repairs = [a for a in world.events("mission.action") if a["action_id"] == "w" and a["status"] == "DONE"]
    with world.body() as b:
        assert repairs and all(b.ledger.find(a["receipt"]).record_type == "receipt" for a in repairs)
    # Exactly one founder ask for the consequential out-of-cone move, on the engine's own path.
    asks = world.w2_requests()
    assert [a["request_id"] for a in asks] == [rid] and asks[0]["kind"] == "APPROVAL"
    assert asks[0]["scope_digest"] == scope and asks[0]["evidence"]["goal_id"] == gid
    assert not world.events("decision.withdrawn")
    assert not [r for r in world.events("decision.requested") if r["request_id"].startswith("req-goal-")]
    reg = world.registry()
    assert reg.state(gid).active_node_id == "ship"          # the bottleneck before the decision
    # Approve: it executes once, through the mission's Gate.
    world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship it"})
    world.tick(4)
    assert (world.ws / "d.txt").read_text() == "shipped"
    assert len([a for a in world.events("mission.action") if a["action_id"] == "w2" and a["status"] == "DONE"]) == 1
    world.ingest("ops", "check the watch after shipping")   # relevant evidence: the goal re-fixes its GPS
    world.tick(2)
    assert world.registry().state(gid).active_node_id == "n1"   # recalculated bottleneck: d done, N1 next
    world.tick(4)
    # Mission F: dormant goal, noise wakes nothing; relevant evidence wakes it and pulls the mission.
    (world.ws / "c.txt").write_text("damaged")
    pulls = len([e for e in world.events("mission.schedule") if "cause" in e])
    world.ingest("weather", "sunny tomorrow")
    noise = world.tick()[0]["gravity"]
    assert noise.get("woken", []) == [] and (world.ws / "c.txt").read_text() == "damaged"
    assert len([e for e in world.events("mission.schedule") if "cause" in e]) == pulls
    world.ingest("ops", "c.txt looks broken")
    relevant = world.tick(3)
    assert gid in relevant[0]["gravity"]["woken"] and relevant[0]["gravity"]["missions_pulled"] == [MID]
    assert (world.ws / "c.txt").read_text() == "ok"
    # One ledger, one Gate path, no hidden founder channel, no execution by the loop.
    with world.body() as b:
        assert b.ledger.verify_chain()[0]
        assert b.ledger.by_type(ASK_RECORD) == [] and b.ledger.by_type(ANSWER_RECORD) == []
        assert all(r.payload["turn"]["executed"] == [] for r in b.ledger.by_type(GoalGravityLoop.TURN_RECORD))
        closure = gg.ledger_closure(b.journal)
        assert closure["ok"] and closure["grant_dispatches"] >= 3
        assert not b.journal.replay("goal_gravity.fault")


def test_a_rejection_is_remembered_by_both_lineages(world, fast):
    gid, _ = world.start()
    world.tick(3)
    rid, scope = expected_w2_request(world)
    world.submit("DECISION", {"request_id": rid, "answer": "reject", "reason": "not this way"})
    world.tick(3)
    m = world.book().missions[MID]
    assert scope in m.rejected_scopes and m.failed["w2"].startswith("founder rejected")
    reg = world.registry()
    assert reg.is_route_refused(gid, ship_move().route_hash)
    refusal = [r for r in world.records(GoalRegistry.PREFERENCE_RECORD) if r["preference"]["kind"] == "refused_route"]
    assert len(refusal) == 1 and "signed DECISION" in refusal[0]["reason"]
    world.ingest("ops", "anything new on the watch?")
    world.tick(3)
    assert len(world.w2_requests()) == 1                    # the refused route is not asked again
    assert (world.ws / "d.txt").exists() is False


def test_a_goal_never_resumes_a_paused_mission(world, fast):
    world.start()
    world.tick(2)
    world.submit("LIFECYCLE", {"mission_id": MID, "state": "PAUSED", "reason": "hold"})
    world.tick()
    pulls = len([e for e in world.events("mission.schedule") if "cause" in e])
    (world.ws / "c.txt").write_text("damaged")
    world.ingest("ops", "c.txt looks broken")
    world.tick(3)
    assert world.book().missions[MID].paused is True
    assert len([e for e in world.events("mission.schedule") if "cause" in e]) == pulls
    assert (world.ws / "c.txt").read_text() == "damaged"


# -- admission: a goal never widens authority ------------------------------------------------------------

@pytest.mark.parametrize("goal,needle", [
    (GOAL(ceiling="external_contact"), "more authority than its missions"),
    (GOAL(missions=("m:nowhere",)), "unknown or closed mission"),
    (GOAL(moves=(ship_move(payload={"mission_id": MID, "action_id": "w"}, target="workspace:c.txt"),)),
     "inside its mission's light cone"),
    (GOAL(moves=(ship_move(target="workspace:e.txt"),)), "restate its strategy"),
    (GOAL(moves=(ship_move(payload={"topic": "free-form"}),)), "must name {mission_id, action_id}"),
])
def test_admission_refuses_goals_that_would_widen_authority(world, fast, goal, needle):
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    world.submit("GOAL", goal, "b.json")
    world.tick()
    assert any(needle in r for r in world.rejections()), world.rejections()
    assert world.records(GoalRegistry.AUTHORIZED_RECORD) == []


def test_a_goal_move_must_name_a_static_strategy(world, fast):
    spec = world.mission_spec()
    spec["strategies"].append(write_strategy("w3", "e.txt", "bound", ["d"],
                                             bind=[{"from_action": "w", "path": "text", "to": "content"}]))
    world.submit("MISSION", spec, "a.json")
    world.tick()
    world.submit("GOAL", GOAL(moves=(ship_move(payload={"mission_id": MID, "action_id": "w3"},
                                               target="workspace:e.txt"),)), "b.json")
    world.tick()
    assert any("static, capability-bound strategy" in r or "bind" in r for r in world.rejections()), world.rejections()


def test_a_goal_body_cannot_carry_its_own_authority(world, fast):
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    smuggled = GOAL()
    smuggled["goal"]["authority"] = {"authorized_by": "alfonso_lopez", "authorization_ref": "sha256:" + "a" * 64,
                                     "legal_principal": "alfonso_lopez", "max_consequence_class": "irreversible"}
    world.submit("GOAL", smuggled, "b.json")
    world.tick()
    assert any("derives them from your signature" in r for r in world.rejections())


# -- founder keys: GOAL is founder-only; a device may only narrow a goal ---------------------------------

def _device(world, kinds):
    public = generate_founder_key(world.tmp / "phone.pem", None)
    key = load_founder_key(world.tmp / "phone.pem", None)
    world.submit("DEVICE_ENROLL", {"public_key": public, "label": "phone", "kinds": kinds,
                                   "expires_at": iso(world.clock.now + timedelta(days=30))}, "dev.json")
    world.tick()
    return key


def test_a_device_key_cannot_sign_a_goal_and_may_only_narrow_one(world, fast):
    gid, _ = world.start()
    phone = _device(world, ["DECISION", "GOAL_CONTROL"])
    world.submit("GOAL", GOAL(intent="from the phone"), "p1.json", key=phone)
    world.tick()
    assert "device key may not sign GOAL" in world.rejections()[-1]
    world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "stop_pushing", "value": True, "reason": "quiet"},
                 "p2.json", key=phone)
    world.tick()
    assert world.registry().state(gid).status == "paused"
    for n, body in enumerate(({"goal_id": gid, "kind": "stop_pushing", "value": False},
                              {"goal_id": gid, "kind": "revoke"},
                              {"goal_id": gid, "kind": "change_goal", "value": "something else"})):
        world.submit("GOAL_CONTROL", body, f"p3-{n}.json", key=phone)
        world.tick()
        assert "needs the founder key" in world.rejections()[-1]
    assert world.registry().state(gid).status == "paused"
    world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "lower_priority", "value": 4}, "p4.json", key=phone)
    world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "stop_pushing", "value": False, "reason": "go on"},
                 "p5.json")                                  # the founder key resumes
    world.tick()
    reg = world.registry()
    assert reg.state(gid).status == "dormant" and reg.effective_priority(gid) == 4


def test_signed_commands_honour_device_revocation_and_founder_rotation(world, fast):
    gid, _ = world.start()
    phone = _device(world, ["DECISION"])
    with world.body() as b:
        device_id = next(iter(b.device_keys()))
    world.submit("DEVICE_REVOKE", {"device_key_id": device_id}, "rev.json")
    world.tick()
    late = world.sign("DECISION", {"request_id": "req-x", "answer": "approve"}, key=phone)
    new_public = generate_founder_key(world.tmp / "new.pem", None)
    new_key = load_founder_key(world.tmp / "new.pem", None)
    world.submit("ROTATE_FOUNDER_KEY", {"new_public_key": new_public}, "rot.json")
    world.tick()
    stale_goal = world.sign("GOAL", GOAL(intent="signed with the retired key"))
    with world.body() as b:
        for env in (late, stale_goal):                      # smuggled in-process, bypassing the verifier
            b.journal.record("command.accepted", {"kind": env["kind"], "digest": sha256_json(env),
                                                  "nonce": env["nonce"], "founder_key_id": env["founder_key_id"],
                                                  "signer": "founder", "issued_at": env["issued_at"],
                                                  "body": env["body"], "envelope": env, "channel": "direct",
                                                  "result": {}}, key=sha256_json(env))
        signed = gg.signed_commands(b.journal, "DECISION", "GOAL")
        assert sha256_json(late) not in signed and sha256_json(stale_goal) not in signed
        assert gg.admitted(signed, GoalRegistry(ledger=b.ledger)) == {gid: next(iter(
            d for d, c in signed.items() if c["kind"] == "GOAL"))}
    world.submit("GOAL", GOAL(intent="signed with the new key"), "new-goal.json", key=new_key)
    world.tick()
    assert len(world.projection()["goals"]) == 2


# -- attacks ------------------------------------------------------------------------------------------------

def test_a_forged_goal_is_preserved_but_never_woken(world, fast):
    world.start()
    forged = GoalSpec.from_dict({**goal_body(intent="forged"), "authority": {
        "authorized_by": "alfonso_lopez", "authorization_ref": "sha256:" + "b" * 64,
        "legal_principal": "alfonso_lopez", "max_consequence_class": "internal_write", "missions": [MID]}})
    with world.body() as b:
        fid = GoalRegistry(ledger=b.ledger).authorize(forged, now=world.clock.now - timedelta(days=30))
    world.ingest("ops", "wake everything")
    world.tick(4)
    view = world.projection()
    assert [g["goal_id"] for g in view["unadmitted"]] == [fid]
    assert world.registry().state(fid).status == "paused"
    assert not [p for p in world.records(GoalRegistry.TRANSITION_RECORD)
                if p["goal_id"] == fid and p["reason"].startswith("wake")]
    assert not [r for r in world.events("decision.requested") if (r.get("evidence") or {}).get("goal_id") == fid]
    assert not [e for e in world.events("mission.schedule") if fid[7:23] in e.get("cause", "")]
    assert len(world.records(GoalRegistry.AUTHORIZED_RECORD)) == 2      # retained, never deleted


def test_a_smuggled_acceptance_with_a_bad_signature_is_not_admission(world, fast):
    world.start()
    body = GOAL(intent="smuggled")
    env = sign_command(Ed25519PrivateKey.generate(), "GOAL", body, body_id=world.body_id, now=world.clock.now)
    with world.body() as b:
        env["founder_key_id"] = next(iter(b.enrolled_keys()))          # claims the founder's key id
        dig = sha256_json(env)
        sid = gg.binding_for(b).loop.registry.authorize(gg._spec(body, dig), now=world.clock.now)
        b.journal.record("command.accepted", {"kind": "GOAL", "digest": dig, "nonce": env["nonce"],
                                              "founder_key_id": env["founder_key_id"], "signer": "founder",
                                              "issued_at": env["issued_at"], "body": body, "envelope": env,
                                              "channel": "direct", "result": {}}, key=dig)
        assert sid not in gg.admitted(gg.signed_commands(b.journal, "GOAL"), GoalRegistry(ledger=b.ledger))
    world.tick()
    assert sid in [g["goal_id"] for g in world.projection()["unadmitted"]]


def test_a_backdated_envelope_is_refused_and_a_fresh_one_uses_the_body_clock(world, fast):
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    world.submit("GOAL", GOAL(), "old.json", at=world.clock.now - timedelta(days=8), ttl=timedelta(days=7))
    world.tick()
    assert "expired or issued in the future" in world.rejections()[-1]
    at = iso(world.clock.now)
    world.submit("GOAL", GOAL(), "recent.json", at=world.clock.now - timedelta(days=6), ttl=timedelta(days=7))
    world.tick()
    authorized = world.records(GoalRegistry.AUTHORIZED_RECORD)
    assert len(authorized) == 1 and authorized[0]["authorized_at"] == at
    assert world.registry().due_for_review(world.clock.now) == []


def test_replayed_duplicate_and_superseded_goals(world, fast):
    gid, env = world.start()
    drop(world.home, env, "again.json")                     # the same signed file, re-dropped
    assert world.tick()[0]["commands"][0]["status"] == "ALREADY_APPLIED"
    world.submit("GOAL", GOAL(), "dup.json")                # the same intent, newly signed
    world.tick()
    assert "identical goal is already authorized" in world.rejections()[-1]
    world.submit("GOAL", GOAL(intent="ship d first", supersedes=gid), "change.json")
    world.tick()
    reg = world.registry()
    new = [g for g in reg.goals() if g != gid]
    assert len(new) == 1 and reg.state(gid).status == "superseded" and reg.get(new[0]).supersedes == gid
    assert len(world.records(GoalRegistry.AUTHORIZED_RECORD)) == 2


def test_after_a_signed_supersede_relevant_evidence_wakes_the_replacement_without_a_fault(world, fast):
    gid, _ = world.start()
    world.tick(3)
    world.submit("GOAL", GOAL(intent="ship d first", supersedes=gid), "change.json")
    world.tick()
    new = next(g["goal_id"] for g in world.projection()["goals"] if g["goal_id"] != gid)
    world.ingest("ops", "is the watch healthy?")            # matches both goals' wake conditions
    results = world.tick(2)
    gravity = results[0]["gravity"]
    assert gravity["state"] != "FAULT" and new in gravity["woken"] and gid not in gravity["woken"]
    assert gravity["wake_refused"] == [] and not world.events("goal_gravity.fault")


def test_a_crash_between_the_goal_record_and_its_acceptance_replays_to_one_goal(world, fast, monkeypatch):
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    real = gg.command

    def crash(*a, **kw):
        real(*a, **kw)
        raise RuntimeError("power loss after the goal record, before command.accepted")
    monkeypatch.setattr(gg, "command", crash)
    world.submit("GOAL", GOAL(), "b.json")
    with pytest.raises(RuntimeError):
        world.tick()
    monkeypatch.setattr(gg, "command", real)
    assert [p.name for p in (world.home / "inbox").glob("*.json")] == ["b.json"]
    world.tick()
    view = world.projection()
    assert len(world.records(GoalRegistry.AUTHORIZED_RECORD)) == 1
    assert len(view["goals"]) == 1 and view["goals"][0]["status"] == "dormant" and view["unadmitted"] == []


def test_an_expired_replay_after_a_crash_leaves_the_goal_quarantined(world, fast, monkeypatch):
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    real = gg.command
    monkeypatch.setattr(gg, "command", lambda *a, **kw: (real(*a, **kw), (_ for _ in ()).throw(RuntimeError("crash")))[0])
    world.submit("GOAL", GOAL(), "b.json", ttl=timedelta(hours=1))
    with pytest.raises(RuntimeError):
        world.tick()
    monkeypatch.setattr(gg, "command", real)
    world.clock.advance(2 * 3600)
    world.tick()
    view = world.projection()
    assert view["goals"] == [] and len(view["unadmitted"]) == 1 and view["unadmitted"][0]["status"] == "paused"


def test_a_signed_founder_stop_survives_an_unsigned_resume(world, fast):
    gid, _ = world.start()
    world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "stop_pushing", "value": True, "reason": "pause it"})
    world.tick()
    with world.body() as b:
        reg = gg.binding_for(b).loop.registry
        reg.record_preference(gid, kind="stop_pushing", value=False, actor="alfonso_lopez", reason="forged resume",
                              now=world.clock.now)
        assert reg.state(gid).status == "dormant"
    world.tick()
    assert world.registry().state(gid).status == "paused"
    assert world.projection()["goals"][0]["stopped_by_founder"] is True


def test_an_answer_without_a_signed_decision_is_never_mirrored(world, fast):
    gid, _ = world.start()
    world.tick(3)
    rid, _ = expected_w2_request(world)
    with world.body() as b:
        b.journal.record("decision.answered", {"request_id": rid, "mission_id": MID, "answer": "reject",
                                               "reason": "forged", "command_digest": "sha256:" + "d" * 64}, key=rid)
        loop = gg.binding_for(b).loop
        with pytest.raises(ContractError):
            loop.founder_answer("item:any", decision="refuse", actor="alfonso_lopez", note="x", now=world.clock.now)
        b.ledger.append(ANSWER_RECORD, {"item_id": "item:forged", "decision": "accept", "actor": "someone"})
        closure = gg.ledger_closure(b.journal)
    assert not closure["ok"] and closure["problems"][0]["problem"].startswith("egregore.founder_answer without")
    world.tick(2)
    assert not world.registry().is_route_refused(gid, ship_move().route_hash)


def test_an_executor_claim_never_becomes_goal_evidence(world, fast):
    gid, _ = world.start()
    (world.ws / "d.txt").write_text("not yet")
    world.tick(3)
    failing = next(o for o in reversed(world.events("mission.observed")) if o["check_id"] == "d" and not o["passed"])
    with world.body() as b:                                  # an in-process claim that d passed, citing that receipt
        b.journal.record("mission.observed", {**failing, "passed": True, "detail": "trust me"}, key="forged-pass")
    world.ingest("ops", "re-check")
    world.tick(2)
    with world.body() as b:
        loop = gg.binding_for(b).loop
        belief = loop.world.belief(MID, "d")
        assert belief.value is False and belief.trust_level == "untrusted"
        assert loop.registry.state(gid).status != "completed"
        assert b.ledger.by_type(GoalGravityLoop.VERIFICATION_RECORD) == []


def test_untrusted_intake_can_wake_a_goal_but_never_clear_its_gate(world, fast):
    gid, _ = world.start()
    world.tick(3)
    world.ingest("ops", json.dumps({"subject": MID, "attribute": "d", "value": True}))
    gravity = world.tick()[0]["gravity"]
    assert gid in gravity["woken"]
    with world.body() as b:
        belief = gg.binding_for(b).loop.world.belief(MID, "d")
        assert belief is None or belief.value is not True
    assert world.registry().state(gid).active_node_id == "ship"


# -- structure: one authority, one ledger -----------------------------------------------------------------

def test_the_binding_holds_no_second_authority(world, fast, monkeypatch):
    source = (GREG / "goal_gravity.py").read_text()
    for forbidden in ("ConsequenceGate(", "GrantIssuer", "issue_single_action", "EvidenceLedger(", ".run(",
                      'record("decision.requested"', 'record("mission.', "ASK_RECORD", "ANSWER_RECORD"):
        assert forbidden not in source, forbidden
    seen = []
    real_turn = GoalGravityLoop.turn

    def spy(self, **kw):
        seen.append((kw.get("gate"), kw.get("executor"), kw.get("grants")))
        return real_turn(self, **kw)
    monkeypatch.setattr(GoalGravityLoop, "turn", spy)
    world.start()
    import provenance.ledger as ledger_module
    opened = []
    real_init = ledger_module.EvidenceLedger.__init__
    with world.body() as b:
        monkeypatch.setattr(ledger_module.EvidenceLedger, "__init__",
                            lambda self, *a, **kw: (opened.append(a), real_init(self, *a, **kw))[1])
        for _ in range(3):
            b.tick()
            world.clock.advance(1)
        held = gg.binding_for(b)
        assert not {k for k in vars(held.loop) if k in ("gate", "executor", "grants", "_gate", "_executor")}
    monkeypatch.setattr(ledger_module.EvidenceLedger, "__init__", real_init)
    assert seen and all(s == (None, None, None) for s in seen)
    assert opened == []
    assert sorted(p.name for p in world.home.iterdir() if p.suffix == ".jsonl") == ["ledger.jsonl"]


def test_a_body_hosted_loop_refuses_a_gate_executor_or_grant(world, fast):
    world.start()
    from egregore.resources import ResourceGovernor
    with world.body() as b:
        loop = gg.binding_for(b).loop
        plain = GoalGravityLoop(ledger=b.ledger, compiled=b.compiled, passports=b.passports,
                                actor=b.identity.passport_id, legal_principal="alfonso_lopez")
        for candidate in (loop, plain):                      # constructor flag or not: the ledger decides
            assert candidate.body_mode is True
            for kw in ({"gate": b.office.gate}, {"executor": lambda p: {}}, {"grants": {"g": {"grant_id": "g"}}}):
                with pytest.raises(ContractError, match="takes no gate, executor or grants"):
                    candidate.turn(trigger_id="attack", now=world.clock.now, resources=ResourceGovernor(
                        max_model_calls=1, max_estimated_cost_usd=0.01), **kw)


def test_a_gravity_fault_is_contained_and_recorded_once(world, fast, monkeypatch):
    world.start()

    def boom(self, **kw):
        raise ContractError("boom")
    monkeypatch.setattr(GoalGravityLoop, "turn", boom)
    results = world.tick(4)
    assert {r["gravity"]["state"] for r in results} == {"FAULT"}
    assert len(world.events("goal_gravity.fault")) == 1
    assert (world.ws / "c.txt").read_text() == "ok"         # the mission kept its own loop


def test_a_faulted_turn_does_not_lose_the_waking_evidence(world, fast, monkeypatch):
    gid, _ = world.start()
    world.tick(6)
    real = GoalGravityLoop.turn
    calls = []

    def once(self, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise ContractError("transient refusal")
        return real(self, **kw)
    monkeypatch.setattr(GoalGravityLoop, "turn", once)
    world.ingest("ops", "c.txt looks broken")
    with world.body() as b:                                  # one open body: the sensing cursor is in memory
        first = b.tick()["gravity"]
        world.clock.advance(1)
        second = b.tick()["gravity"]
    assert first["state"] == "FAULT" and gid in second["woken"]


def test_a_stray_goal_record_is_quarantined_instead_of_faulting_every_tick(world, fast):
    gid, _ = world.start()
    with world.body() as b:
        state = GoalRegistry(ledger=b.ledger).state(gid).to_dict()
        state["goal_id"] = "sha256:" + "e" * 64
        b.ledger.append(GoalRegistry.TRANSITION_RECORD, {"source": "stray", "goal_id": state["goal_id"],
                                                         "reason": "stray", "state": state})
    results = world.tick(3)
    assert all(r["gravity"]["state"] != "FAULT" for r in results)
    assert len(world.events("goal.record_quarantined")) == 1
    assert world.projection()["quarantined_records"][0]["goal_id"] == "sha256:" + "e" * 64


def test_one_backcast_greg_path_and_the_goal_agree(world, fast, monkeypatch):
    gid, _ = world.start()
    with world.body() as b:
        assert "N1" not in devpath.position(b.journal)["achieved"]
        assert gg.binding_for(b).loop.world.belief("greg.path", "N1").value is False
    monkeypatch.setitem(devpath.PREDICATES, "vepmc_at_least_one", lambda journal: {"met": True, "value": 1})
    world.tick()
    with world.body() as b:
        assert "N1" in devpath.position(b.journal)["achieved"]
        b.tick()
        assert gg.binding_for(b).loop.world.belief("greg.path", "N1").value is True


def test_ledger_closure_traces_every_dispatch_to_a_signed_mission(world, fast):
    world.start()
    world.tick(3)
    with world.body() as b:
        good = gg.ledger_closure(b.journal)
        b.ledger.append("grant_dispatch", {"proposal_id": "p-forged", "grant_id": "g-forged",
                                           "witness_id": "w", "effect_digest": "sha256:" + "0" * 64})
        bad = gg.ledger_closure(b.journal)
    assert good["ok"] and good["grant_dispatches"] >= 1 and good["founder_answers"] == 0
    assert not bad["ok"] and bad["problems"][-1]["problem"] == "grant_dispatch without greg.authority.grant_issued"
