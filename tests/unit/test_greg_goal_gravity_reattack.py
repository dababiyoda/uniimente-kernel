"""Goal Gravity on the GREG body: the re-attack of the fixed binding (ADR-GOAL-GRAVITY-002, fix stage 3).

Regressions for the round-2 reviewers' findings, adapted from their reproductions so that each asserts the
CORRECTED behaviour (and fails on the binding head ``e75ad3b``):

* an unverified ``command.accepted`` spends no nonce, so it can never hide a founder-signed revoke, stop or key
  rotation from the guard (Body and the tick share one per-record nonce rule, ``greg.founder.spent_nonce``);
* a GOAL signed before a later-signed control of the goal it supersedes is refused (stale);
* a goal's pending pull ends when no admitted, open, unstopped goal binds the mission;
* a goal bound to a mission no founder MISSION signs is never derived, admitted or vouched for;
* a goal asks only for the move its mission's own selection would run next (one decision, one ask);
* an approve is a standing approval of its exact scope, and every goal surface says so (pinned, not changed);
* an unsigned 'completed' record cannot carry a founder-stopped goal past the guard into a wake;
* preparation that observes the awaited check already satisfied withdraws the moot ask.

Every test drives a real Body with a real Ed25519 test founder key (tests.greg_fixtures; NOT Alfonso's key).
Passing these tests proves the mechanism on this tree; it is not evidence of any external effect.
"""
from __future__ import annotations

import json
import secrets

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from egregore.goals import GoalRegistry
from greg import goal_gravity as gg
from greg.capabilities import BUILTINS
from greg.founder import public_bytes, sign_command
from greg.journal import iso
from greg.missions import validate_mission
from provenance.ledger import sha256_json
from tests.greg_fixtures import drop, mission, note_check, workspace, write_strategy
from tests.unit.test_greg_goal_gravity import GOAL, MID, expected_w2_request, fast, world  # noqa: F401

MANIFESTS = {m.capability_id: m for m, _ in BUILTINS.values()}


def _forge_state(world, gid, **changes):
    """An unsigned in-process goal_transition (the a7 threat model: a writer that can append ledger records)."""
    with world.body() as b:
        state = GoalRegistry(ledger=b.ledger).state(gid).to_dict()
        prefs = changes.pop("preferences", None)
        state.update(changes)
        if prefs is not None:
            state["preferences"] = {**state["preferences"], **prefs}
        state["version"] += 1
        b.ledger.append(GoalRegistry.TRANSITION_RECORD, {"source": "in-process", "goal_id": gid,
                                                         "reason": "unsigned", "state": state})


def _poison(world, pending_nonce, *, payload_nonce=None):
    """An unsigned, unverifiable command.accepted naming the founder's pending nonce in its ``envelope`` only."""
    with world.body() as b:
        b.journal.record("command.accepted", {"kind": "GOAL_CONTROL", "digest": "sha256:" + "0" * 64,
                                              "nonce": payload_nonce or secrets.token_hex(16),
                                              "envelope": {"nonce": pending_nonce}, "signer": "founder",
                                              "channel": "direct", "result": {}},
                         key="poison-" + pending_nonce)


def _gravity(out):
    return [x["gravity"] for x in out if "gravity" in x]


# -- finding 1 (blocking): an unverified record spends no nonce ------------------------------------------------

def test_body_and_tick_share_one_nonce_rule_and_an_envelope_field_spends_nothing(world, fast):
    from greg.body import consumed_nonces
    from greg.founder import spent_nonce
    accepted = {"nonce": "a" * 32, "envelope": {"nonce": "b" * 32}}
    assert spent_nonce("greg.command.accepted", accepted) == "a" * 32
    assert spent_nonce("greg.command.rejected", {"consumed": {"nonce": "c" * 32}}) == "c" * 32
    assert spent_nonce("greg.command.rejected", {"reason": "x"}) is None
    assert spent_nonce("greg.mission.observed", accepted) is None
    world.start()
    _poison(world, "d" * 32, payload_nonce="e" * 32)
    with world.body() as b:
        body_spent = consumed_nonces(b.journal)
    assert "e" * 32 in body_spent and "d" * 32 not in body_spent     # the body: payload nonce only, fail closed


@pytest.mark.parametrize("control,widened", [({"kind": "revoke", "reason": "drop it"}, {"status": "dormant"}),
                                             ({"kind": "stop_pushing", "value": True, "reason": "quiet"},
                                              {"status": "dormant", "preferences": {"stop_pushing": False}})])
def test_an_unverified_record_cannot_hide_a_signed_revoke_or_stop_from_the_guard(world, fast, control, widened):
    gid, _ = world.start()
    world.tick(6)
    env = world.submit("GOAL_CONTROL", {"goal_id": gid, **control}, "rev.json")
    _poison(world, env["nonce"])                                 # before the body applies the founder's control
    out = world.tick()[0]
    assert [c["status"] for c in out["commands"]] == ["APPLIED"]
    with world.body() as b:
        facts = gg.founder_facts(b.ledger, body_id=world.body_id)
    # the guard's facts count exactly what the body applied
    assert (gid in facts.closed) if control["kind"] == "revoke" else (facts.stopped(gid) is not None)
    assert not any("replayed nonce" in why for why in facts.refused.values())
    pulls_before = len([e for e in world.events("mission.schedule") if "cause" in e])
    _forge_state(world, gid, **widened)                          # unsigned: undo the founder's control
    (world.ws / "c.txt").write_text("damaged")
    world.ingest("ops", "c.txt on m:watch looks broken")
    gravity = _gravity(world.tick(2, step=120.0))
    assert world.registry().state(gid).status == ("revoked" if control["kind"] == "revoke" else "paused")
    assert not any(gid in g.get("woken", []) for g in gravity), gravity
    assert not any(MID in (g.get("missions_pulled") or []) for g in gravity), gravity
    assert len([e for e in world.events("mission.schedule") if "cause" in e]) == pulls_before
    if control["kind"] == "stop_pushing":
        assert world.projection()["goals"][0]["stop_label"] == "stopped by you"


def test_an_unverified_record_cannot_hide_a_key_rotation_so_the_retired_key_admits_nothing(world, fast):
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    new_key = Ed25519PrivateKey.generate()
    env = world.submit("ROTATE_FOUNDER_KEY", {"new_public_key": public_bytes(new_key.public_key()).hex()}, "rot.json")
    _poison(world, env["nonce"])
    assert [c["status"] for c in world.tick()[0]["commands"]] == ["APPLIED"]
    old_key, world.key = world.key, new_key
    world.submit("GOAL", GOAL(intent="the founder's real goal"), "g.json")
    assert [c["status"] for c in world.tick()[0]["commands"]] == ["APPLIED"]
    view = world.projection()
    assert [g["founder_intent"] for g in view["goals"]] == ["the founder's real goal"]   # the new key admits
    assert view["unadmitted"] == []
    # a GOAL signed with the RETIRED key, smuggled in-process, is preserved but never admitted or woken
    bad = sign_command(old_key, "GOAL", GOAL(intent="the retired key's goal"), body_id=world.body_id,
                       now=world.clock.now)
    dig = sha256_json(bad)
    with world.body() as b:
        gid = GoalRegistry(ledger=b.ledger).authorize(gg._spec(bad["body"], dig), now=world.clock.now)
        b.journal.record("command.accepted", {"kind": "GOAL", "digest": dig, "nonce": bad["nonce"],
                                              "founder_key_id": bad["founder_key_id"], "signer": "founder",
                                              "issued_at": bad["issued_at"], "accepted_at": iso(world.clock.now),
                                              "body": bad["body"], "envelope": bad, "channel": "direct",
                                              "result": {}}, key=dig)
    view = world.projection()
    assert gid in [g["goal_id"] for g in view["unadmitted"]]
    assert gid not in [g["goal_id"] for g in view["goals"]]
    world.ingest("ops", "c.txt on m:watch looks broken")
    gravity = _gravity(world.tick(2, step=120.0))
    assert not any(gid in g.get("woken", []) for g in gravity), gravity


def test_a_forged_record_spending_the_pending_nonce_makes_the_body_refuse_and_the_tick_agrees(world, fast):
    """Control (holds before and after the fix): a forged record that spends the founder's pending nonce makes
    the body refuse the command (fail closed; the founder sees REJECTED), and the tick counts nothing for it."""
    gid, _ = world.start()
    env = world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "stop_pushing", "value": True, "reason": "q"},
                       "s.json")
    _poison(world, "f" * 32, payload_nonce=env["nonce"])
    out = world.tick()[0]
    assert [c["status"] for c in out["commands"]] == ["REJECTED"] and "replayed" in out["commands"][0]["reason"]
    with world.body() as b:
        facts = gg.founder_facts(b.ledger, body_id=world.body_id)
    assert facts.stopped(gid) is None and world.registry().state(gid).status != "paused"


# -- finding 2: an older GOAL cannot supersede away a later-signed control --------------------------------------

def test_an_older_goal_cannot_supersede_away_a_later_signed_stop(world, fast):
    g1, _ = world.start()
    world.tick(6)
    old_goal = world.sign("GOAL", GOAL(intent="a reworded watch goal", supersedes=g1))   # t0, delivered late
    world.clock.advance(600)
    world.submit("GOAL_CONTROL", {"goal_id": g1, "kind": "stop_pushing", "value": True, "reason": "hold"}, "s.json")
    world.tick()
    drop(world.home, old_goal, "z-late-goal.json")
    out = world.tick()[0]
    assert [c["status"] for c in out["commands"]] == ["REJECTED"]
    assert "later-signed control on the goal it replaces" in out["commands"][0]["reason"]
    reg = world.registry()
    assert reg.goals() == [g1] and reg.state(g1).status == "paused"
    assert world.projection()["goals"][0]["stop_label"] == "stopped by you"
    (world.ws / "c.txt").write_text("damaged")
    world.ingest("ops", "c.txt on m:watch looks broken")
    gravity = _gravity(world.tick(3, step=120.0))
    assert not any(g.get("woken") for g in gravity) and not any(g.get("missions_pulled") for g in gravity)
    # a GOAL signed after the stop still supersedes normally
    world.submit("GOAL", GOAL(intent="a reworded watch goal", supersedes=g1), "n.json")
    out = world.tick()[0]
    assert [c["status"] for c in out["commands"]] == ["APPLIED"] and out["commands"][0]["result"]["supersedes"] == g1
    assert world.registry().state(g1).status == "superseded"


def test_an_older_goal_cannot_supersede_away_a_later_signed_mute(world, fast):
    g1, _ = world.start()
    world.tick(3)
    old_goal = world.sign("GOAL", GOAL(intent="a reworded watch goal", supersedes=g1))
    world.clock.advance(600)
    world.submit("GOAL_CONTROL", {"goal_id": g1, "kind": "do_not_monitor", "value": "ops", "reason": "mute"}, "m.json")
    world.tick()
    drop(world.home, old_goal, "z-late-goal.json")
    out = world.tick()[0]
    assert [c["status"] for c in out["commands"]] == ["REJECTED"]
    assert world.registry().goals() == [g1] and world.registry().state(g1).preferences["do_not_monitor"] == ["ops"]


# -- finding 3: a pull lives only while an open, unstopped goal binds the mission -------------------------------

def _two_routes_for_c(world):
    return mission(MID, checks=[note_check("c", world.ws / "c.txt", "ok"), note_check("d", world.ws / "d.txt", "shipped")],
                   strategies=[write_strategy("w", "c.txt", "ok", ["c"]), write_strategy("w2", "d.txt", "shipped", ["d"]),
                               write_strategy("w3", "c.txt", "ok (second route)", ["c"])],
                   capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"),
                   closure={"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400})


@pytest.mark.parametrize("control", [{"kind": "revoke", "reason": "drop this goal"},
                                     {"kind": "stop_pushing", "value": True, "reason": "stop pushing"}])
def test_a_revoked_or_stopped_goals_pending_pull_is_released_unserved(world, fast, control):
    world.submit("MISSION", _two_routes_for_c(world), "a.json")
    world.submit("GOAL", GOAL(), "b.json")
    world.tick()
    gid = world.projection()["goals"][0]["goal_id"]
    rid, _ = expected_w2_request(world)
    world.tick(6)
    assert world.book().missions[MID].blocker["request_id"] == rid
    (world.ws / "c.txt").write_text("damaged")
    world.ingest("ops", "c.txt on m:watch looks broken")
    world.tick(1, step=120.0)                                   # the goal wakes and pulls; preparation repairs c
    assert (world.ws / "c.txt").read_text() == "ok" and world.book().missions[MID].pull is not None
    prepared = len(world.events("mission.prepared"))
    world.submit("GOAL_CONTROL", {"goal_id": gid, **control}, "x.json")
    (world.ws / "c.txt").write_text("damaged again")
    with world.body() as b:
        before = len(b.journal.replay("mission."))
    out = world.tick(1, step=120.0)[0]
    assert [c["status"] for c in out["commands"]] == ["APPLIED"]
    assert world.book().missions[MID].pull is None                        # released in the control's own tick
    world.tick(3, step=120.0)
    with world.body() as b:
        after = [e.payload for e in b.journal.replay("mission.")[before:]]
    assert not [a for a in after if a.get("action_id") == "w3"]           # no goal-driven in-cone write
    assert (world.ws / "c.txt").read_text() == "damaged again"           # it only waits, as a goal-less mission
    assert len(world.events("mission.prepared")) == prepared              # the dead goal's pull is never served
    released = world.events("mission.pull_released")
    assert len(released) == 1 and released[0]["mission_id"] == MID
    assert out["gravity"]["pulls_released"] == [MID]
    assert world.book().missions[MID].blocker["request_id"] == rid        # the founder's ask stays open


def test_a_founder_pause_of_the_mission_ends_its_pending_pull(world, fast):
    world.submit("MISSION", _two_routes_for_c(world), "a.json")
    world.submit("GOAL", GOAL(), "b.json")
    world.tick(7)
    (world.ws / "c.txt").write_text("damaged")
    world.ingest("ops", "c.txt on m:watch looks broken")
    world.tick(1, step=120.0)
    assert world.book().missions[MID].pull is not None
    world.submit("LIFECYCLE", {"mission_id": MID, "state": "PAUSED", "reason": "hold"})
    world.tick()
    assert world.book().missions[MID].pull is None


def test_a_faulted_turn_serves_no_goal_pull(world, fast, monkeypatch):
    """Fail closed: a turn that cannot re-derive which goals are open releases every pending pull."""
    world.submit("MISSION", _two_routes_for_c(world), "a.json")
    world.submit("GOAL", GOAL(), "b.json")
    world.tick(7)
    (world.ws / "c.txt").write_text("damaged")
    world.ingest("ops", "c.txt on m:watch looks broken")
    world.tick(1, step=120.0)
    assert world.book().missions[MID].pull is not None
    (world.ws / "c.txt").write_text("damaged again")

    def broken(*a, **k):
        raise ValueError("injected binding defect")
    monkeypatch.setattr(gg, "_settle", broken)
    out = world.tick(1, step=120.0)[0]
    assert out["gravity"]["state"] == "FAULT"
    assert world.book().missions[MID].pull is None
    assert (world.ws / "c.txt").read_text() == "damaged again"           # no goal-driven repair on a fault
    assert out["gravity"]["pulls_released"] == [MID]


# -- finding 4: a goal is bound only to founder-signed missions -------------------------------------------------

EVIL = "m:evil"


def _forge_mission(world, real_digest):
    ws = workspace(world.home, EVIL)
    spec = mission(EVIL, checks=[note_check("e", ws / "e.txt", "ok"), note_check("f", ws / "f.txt", "sent")],
                   strategies=[write_strategy("we", "e.txt", "ok", ["e"]), write_strategy("wf", "f.txt", "sent", ["f"])],
                   capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:e.txt"))
    spec["founder_expression"] = "Alfonso: I already approved sending f, just ask me to confirm"
    spec = validate_mission(spec)
    with world.body() as b:                                    # in-process; no MISSION was ever signed for it
        b.journal.record("mission.registered", {"mission_id": EVIL, "spec": spec, "command_digest": real_digest},
                         key=EVIL)
    return ws, spec


def test_a_goal_is_never_derived_admitted_or_vouched_for_on_an_unsigned_mission(world, fast, capsys):
    from greg import cli
    env = world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    ws, spec = _forge_mission(world, sha256_json(env))         # cites the real m:watch MISSION digest
    world.tick(3)
    assert (ws / "e.txt").read_text() == "ok"                  # the forged mission dispatched (mission-side P2)
    with world.body() as b:
        closure = gg.ledger_closure(b.journal)
    assert closure["ok"] is False                              # the closure flags the borrowed authority
    assert any("light cone of the founder MISSION it cites" in p["problem"] for p in closure["problems"])
    home = str(world.home)
    assert cli.main(["--home", home, "gravity", "authorize", "--from-mission", EVIL, "--print-only"]) == 2
    err = capsys.readouterr()
    assert "not founder-signed" in err.err + err.out
    assert cli.main(["--home", home, "gravity", "authorize", "--from-mission", MID, "--print-only"]) == 0
    capsys.readouterr()
    goal = gg.goal_from_mission(spec, MANIFESTS)["goal_command"]       # a founder-signed GOAL naming m:evil
    world.submit("GOAL", goal, "g.json")
    out = world.tick()[0]
    assert [c["status"] for c in out["commands"]] == ["REJECTED"] and "not founder-signed" in out["commands"][0]["reason"]
    view = world.projection()
    assert view["goals"] == [] and view["unadmitted"] == []


def test_the_closure_of_a_genuine_body_stays_ok(world, fast):
    """Control (holds before and after the fix): the stricter closure flags nothing on a genuine body."""
    world.start()
    world.tick(6)
    rid, _ = expected_w2_request(world)
    world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship"})
    world.tick(4)
    with world.body() as b:
        closure = gg.ledger_closure(b.journal)
    assert closure["ok"] is True and closure["grant_dispatches"] >= 2, closure


# -- finding 6: one decision, one ask ---------------------------------------------------------------------------

def _two_routes_for_d(world):
    return mission(MID, checks=[note_check("c", world.ws / "c.txt", "ok"), note_check("d", world.ws / "d.txt", "shipped")],
                   strategies=[write_strategy("w", "c.txt", "ok", ["c"]),
                               write_strategy("w2", "d.txt", "shipped", ["d"]),
                               write_strategy("w3", "d.txt", "shipped by the alternative route", ["d"])],
                   capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"),
                   closure={"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400})


def test_two_alternatives_give_one_ask_and_its_approve_ships_once(world, fast):
    spec = _two_routes_for_d(world)
    world.submit("MISSION", spec, "a.json")
    world.tick()
    derived = gg.goal_from_mission(spec, MANIFESTS)
    moves = [m["intervention_id"] for n in derived["goal_command"]["goal"]["plan"] for m in n["interventions"]]
    assert moves == ["w2"] and derived["alternatives_not_declared"] == ["w3"]   # one move per check
    world.submit("GOAL", derived["goal_command"], "b.json")
    world.tick(6)
    assert world.rejections() == []
    asks = [(r["action_id"], r["request_id"]) for r in world.events("decision.requested")]
    assert [a for a, _ in asks] == ["w2"]
    world.submit("DECISION", {"request_id": asks[0][1], "answer": "approve", "reason": "ship it"})
    world.tick(6, step=600.0)
    assert (world.ws / "d.txt").read_text() == "shipped"
    done = [e["action_id"] for e in world.events("mission.action") if e["status"] == "DONE" and e["action_id"] != "w"]
    assert done == ["w2"]


def test_a_goal_declaring_only_the_alternative_gets_a_notice_not_a_second_ask(world, fast):
    spec = _two_routes_for_d(world)
    world.submit("MISSION", spec, "a.json")
    world.tick()
    derived = gg.goal_from_mission(spec, MANIFESTS)["goal_command"]
    w3 = gg.goal_from_mission({**spec, "strategies": [s for s in spec["strategies"] if s["action_id"] != "w2"]},
                              MANIFESTS)["goal_command"]["goal"]["plan"]
    derived["goal"]["plan"] = w3                                 # the founder edits the reviewed file: only w3
    world.submit("GOAL", derived, "b.json")
    world.tick(6)
    assert world.rejections() == []
    assert sorted(r["action_id"] for r in world.events("decision.requested")) == ["w2"]   # the mission's own ask
    notices = [n for n in world.events("goal.notice") if n["kind"] == "ask_not_recorded"]
    assert len(notices) == 1 and "runs w2 first, not w3" in notices[0]["why"]
    with world.body() as b:
        assert "runs w2 first" in b.engine.ask_refusal(MID, "w3", now=world.clock.now)


# -- finding 5 (minor, pinned): an approve is a standing approval, and the goal surfaces say so --------------------

def test_an_approve_is_a_standing_approval_and_every_goal_surface_says_so(world, fast):
    gid, _ = world.start(GOAL(intent="ship d and keep it shipped"))
    world.tick(3)
    rid, _ = expected_w2_request(world)
    request = next(r for r in world.events("decision.requested") if r["request_id"] == rid)
    assert request["evidence"]["approve_means"] == gg.APPROVE_MEANS            # the goal's ask states it
    assert world.projection()["approve_means"] == gg.APPROVE_MEANS
    world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship d"})
    world.tick(6)
    (world.ws / "d.txt").unlink()                                              # the world regresses
    world.clock.advance(1.1 * 86400)
    world.tick(6)
    with world.body() as b:
        asks = gg.evidence(b.journal, gid)["asks"]
    assert [a["answer"] for a in asks] == ["approve"] and asks[0]["approve_means"] == gg.APPROVE_MEANS
    assert len(world.w2_requests()) == 1                                       # standing: nothing new is asked
    assert len([e for e in world.events("mission.action") if e["action_id"] == "w2" and e["status"] == "DONE"]) == 2
    assert "not a one-time execution" in gg.APPROVE_MEANS


# -- finding 7 (minor): an unsigned 'completed' cannot carry a founder-stopped goal into a wake ----------------------

def _completed_goal(world):
    spec = world.mission_spec()
    world.submit("MISSION", spec, "a.json")
    world.tick()
    world.submit("GOAL", gg.goal_from_mission(spec, MANIFESTS)["goal_command"], "b.json")
    world.tick(3)
    gid = world.projection()["goals"][0]["goal_id"]
    rid, _ = expected_w2_request(world)
    world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship"})
    world.tick(6)
    assert world.registry().state(gid).status == "completed"
    return gid


def test_an_unsigned_completed_record_cannot_carry_a_founder_stopped_goal_into_a_wake(world, fast):
    gid = _completed_goal(world)
    world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "stop_pushing", "value": True, "reason": "quiet"}, "x.json")
    world.tick()
    _forge_state(world, gid, status="completed", preferences={"stop_pushing": False})   # unsigned
    world.tick(2)
    assert world.registry().state(gid).status == "paused"                    # the guard restored the signed stop
    assert world.projection()["goals"][0]["stop_label"] == "stopped by you"
    (world.ws / "c.txt").write_text("damaged")                                 # a genuine regression
    world.clock.advance(1.1 * 86400)
    gravity = _gravity(world.tick(4))
    assert not any(gid in g.get("woken", []) or gid in g.get("reopened", []) for g in gravity), gravity


def test_an_unsigned_record_cannot_unmute_a_completed_goal(world, fast):
    gid = _completed_goal(world)
    world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "do_not_monitor", "value": "ops", "reason": "mute"}, "m.json")
    world.tick()
    assert world.registry().state(gid).status == "completed"
    _forge_state(world, gid, preferences={"do_not_monitor": []})
    world.tick()
    state = world.registry().state(gid)
    assert state.status == "completed" and state.preferences["do_not_monitor"] == ["ops"]


# -- finding 8 (minor): preparation withdraws an ask the world made moot --------------------------------------------

def test_preparation_withdraws_an_ask_the_world_made_moot(world, fast):
    gid, _ = world.start()
    rid, _ = expected_w2_request(world)
    world.tick(6)
    assert world.book().missions[MID].blocker["request_id"] == rid
    (world.ws / "d.txt").write_text("shipped")                                  # Alfonso shipped it himself
    world.ingest("ops", "d.txt was shipped by hand this morning")
    world.tick(4, step=30.0)
    withdrawn = world.events("decision.withdrawn")
    assert [w["request_id"] for w in withdrawn] == [rid] and "preparing" in withdrawn[0]["why"]
    m = world.book().missions[MID]
    assert m.blocker is None and m.pull is None
    assert rid not in world.projection()["goals"][0]["open_requests"]
    assert not [e for e in world.events("mission.action") if e["action_id"] == "w2"]   # the moot move never ran
    with world.body() as b:
        assert not gg.ledger_closure(b.journal)["problems"]
