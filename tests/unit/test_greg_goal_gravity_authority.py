"""Goal Gravity on the GREG body: authority and security regressions (ADR-GOAL-GRAVITY-002, fix stage).

Each test adapts an independent reviewer's reproduction (decision digest unbound, cross-body views, smuggled
admission, guard gaps, rejected-goal replay, receipt substitution, excluded-strategy ask, prewritten backdated
goal) and asserts the corrected behaviour: every authority-relevant goal fact is re-derived from founder-signed
commands bound to this body, at their ledger position, with the validator the command path uses; anything else
is preserved, labelled and never trusted. Real bodies, a real Ed25519 TEST key (not Alfonso's), a fake clock.
"""
from __future__ import annotations

from egregore.attention import ANSWER_RECORD
from egregore.goals import GoalRegistry
from greg import goal_gravity as gg
from greg.body import status
from greg.founder import sign_command
from provenance.ledger import sha256_json
from tests.unit.test_greg_goal_gravity import GOAL, MID, expected_w2_request, fast, ship_move, world  # noqa: F401


def _forge_answer(world, rid, answer, digest):
    with world.body() as b:                                  # in-process: no DECISION is ever signed
        b.journal.record("decision.answered", {"request_id": rid, "mission_id": MID, "answer": answer,
                                               "reason": "forged in-process", "command_digest": digest}, key=rid)


def _smuggle_acceptance(world, env, *, now=None):
    """An in-process writer adds the registry record and a command.accepted for a genuine envelope."""
    body, dig = env["body"], sha256_json(env)
    with world.body() as b:
        gid = GoalRegistry(ledger=b.ledger).authorize(gg._spec(body, dig), now=now or world.clock.now)
        b.journal.record("command.accepted", {"kind": env["kind"], "digest": dig, "nonce": env["nonce"],
                                              "founder_key_id": env["founder_key_id"], "signer": "founder",
                                              "issued_at": env["issued_at"], "body": body, "envelope": env,
                                              "channel": "direct", "result": {}}, key=dig)
    return gid


# -- a recorded answer counts only with a DECISION for that request and that answer -----------------------

def test_signed_answer_binds_kind_request_and_answer():
    decision = {"kind": "DECISION", "principal": "founder",
                "envelope": {"body": {"request_id": "req-a", "answer": "approve"}}}
    goal = {"kind": "GOAL", "principal": "founder", "envelope": {"body": {"goal": {}, "missions": []}}}
    signed = {"sha256:d": decision, "sha256:g": goal}
    assert gg.signed_answer(signed, "req-a", {"answer": "approve", "command_digest": "sha256:d"}) is decision
    assert gg.signed_answer(signed, "req-a", {"answer": "reject", "command_digest": "sha256:d"}) is None
    assert gg.signed_answer(signed, "req-b", {"answer": "approve", "command_digest": "sha256:d"}) is None
    assert gg.signed_answer(signed, "req-a", {"answer": "approve", "command_digest": "sha256:g"}) is None
    assert gg.signed_answer(signed, "req-a", {"answer": "approve", "command_digest": "sha256:x"}) is None
    assert gg.signed_answer(signed, "req-a", None) is None


def test_a_forged_reject_citing_the_goal_digest_is_not_mirrored(world, fast):
    gid, goal_env = world.start()
    world.tick(3)
    rid, _ = expected_w2_request(world)
    _forge_answer(world, rid, "reject", sha256_json(goal_env))     # a verified GOAL digest, not a DECISION
    world.tick(2)
    assert not world.registry().is_route_refused(gid, ship_move().route_hash)
    assert not [r for r in world.records(GoalRegistry.PREFERENCE_RECORD)
                if r["preference"]["kind"] == "refused_route"]


def test_a_forged_approve_is_never_reported_signature_verified(world, fast):
    gid, goal_env = world.start()
    world.tick(3)
    rid, _ = expected_w2_request(world)
    _forge_answer(world, rid, "approve", sha256_json(goal_env))
    world.tick(4)                     # the mission fold still executes on it (ADR P2); the goal side never vouches
    with world.body() as b:
        ev = gg.evidence(b.journal, gid)
        closure = gg.ledger_closure(b.journal)
    ask = next(a for a in ev["asks"] if a["request_id"] == rid)
    assert ask["answer"] == "approve" and ask["answer_signature_verified"] is False
    assert not closure["ok"] and closure["unsigned_answers"] == 1
    assert any(p["problem"].startswith("decision.answered without a signature-verified DECISION")
               for p in closure["problems"])


def test_a_signed_decision_is_verified_and_the_closure_stays_clean(world, fast):
    gid, _ = world.start()
    world.tick(3)
    rid, _ = expected_w2_request(world)
    world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship it"})
    world.tick(2)
    with world.body() as b:
        ask = next(a for a in gg.evidence(b.journal, gid)["asks"] if a["request_id"] == rid)
        closure = gg.ledger_closure(b.journal)
    assert ask["answer_signature_verified"] is True and closure["ok"] and closure["unsigned_answers"] == 0


def test_ledger_closure_flags_any_founder_answer_on_a_body(world, fast):
    gid, _ = world.start()
    world.tick(3)
    rid, _ = expected_w2_request(world)
    env = world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship it"})
    world.tick(2)
    with world.body() as b:          # cites a real DECISION digest, for an item that DECISION never answered
        b.ledger.append(ANSWER_RECORD, {"item_id": "item:forged", "goal_id": gid, "decision": "refuse",
                                        "actor": "alfonso_lopez", "command_digest": sha256_json(env)})
        closure = gg.ledger_closure(b.journal)
    assert closure["founder_answers"] == 1 and not closure["ok"]
    assert closure["problems"][0]["problem"].startswith("egregore.founder_answer without")


# -- every founder view binds signatures to this body -------------------------------------------------------

def test_founder_views_do_not_admit_a_goal_signed_for_another_body(world, fast):
    world.start()
    body = GOAL(intent="signed for a different body")
    env = sign_command(world.key, "GOAL", body, body_id="some-other-body", now=world.clock.now)
    sid = _smuggle_acceptance(world, env)
    world.tick(2)
    assert world.registry().state(sid).status == "paused"                    # the tick quarantined it
    view = world.projection()
    assert sid not in [g["goal_id"] for g in view["goals"]]
    assert sid in [g["goal_id"] for g in view["unadmitted"]]
    gravity = status(world.home)["gravity"]
    assert sid not in [g["goal_id"] for g in gravity["goals"]] and gravity["unadmitted"] == 1
    with world.body() as b:
        assert sha256_json(env) not in gg.signed_commands(b.journal, "GOAL")    # no body_id passed: still bound
        assert gg.evidence(b.journal, sid)["admitted"] is False


# -- admission is re-derived at the command's ledger position with the command path's validator ---------------

def test_a_goal_rejected_for_widening_authority_is_never_admitted_when_smuggled(world, fast):
    import json
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    world.submit("GOAL", GOAL(ceiling="external_contact"), "wide.json")
    world.tick()
    assert "more authority than its missions" in world.rejections()[-1]
    rejected = world.events("command.rejected")[-1]
    assert rejected["consumed"]["kind"] == "GOAL"                # verified, then refused: its nonce is spent
    env = json.loads((world.home / "inbox" / "rejected" / "wide.json").read_text())
    gid = _smuggle_acceptance(world, env)
    world.tick(2)
    view = world.projection()
    assert view["goals"] == [] and [g["goal_id"] for g in view["unadmitted"]] == [gid]
    assert "replayed nonce" in view["unadmitted"][0]["why"]
    assert world.registry().state(gid).status == "paused"         # quarantined, preserved
    world.ingest("ops", "is the watch healthy?")
    assert gid not in world.tick()[0]["gravity"].get("woken", [])


def test_a_never_delivered_widening_goal_fails_the_validator_at_its_position(world, fast):
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    env = world.sign("GOAL", GOAL(ceiling="external_contact"))     # signed, never delivered: nonce unused
    gid = _smuggle_acceptance(world, env)
    world.tick(2)
    view = world.projection()
    assert view["goals"] == [] and "more authority than its missions" in view["unadmitted"][0]["why"]
    with world.body() as b:
        assert gg.admitted(gg.signed_commands(b.journal, "GOAL"), GoalRegistry(ledger=b.ledger)) == {}
    assert world.registry().state(gid).status == "paused"


def test_an_expired_never_applied_goal_is_never_admitted_when_smuggled(world, fast):
    from datetime import timedelta
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    env = world.sign("GOAL", GOAL(), ttl=timedelta(hours=1))      # signed, never delivered
    world.clock.advance(3 * 86400)                                 # long expired
    gid = _smuggle_acceptance(world, env)
    world.tick(2)
    view = world.projection()
    assert view["goals"] == [] and [g["goal_id"] for g in view["unadmitted"]] == [gid]
    assert "signed validity" in view["unadmitted"][0]["why"]


def test_a_prewritten_backdated_goal_record_is_refused_and_never_admitted(world, fast):
    import json
    from datetime import timedelta
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    world.submit("GOAL", GOAL(), "b.json")                          # the founder's GOAL, still in the inbox
    env = json.loads((world.home / "inbox" / "b.json").read_text())
    with world.body() as b:                                          # in-process, before the body applies it
        gid = GoalRegistry(ledger=b.ledger).authorize(gg._spec(env["body"], sha256_json(env)),
                                                      now=world.clock.now - timedelta(days=30))
    out = world.tick()[0]
    assert [c["status"] for c in out["commands"]] == ["REJECTED"]
    assert "already exists" in world.rejections()[-1] and "Sign a new GOAL" in world.rejections()[-1]
    view = world.projection()
    assert view["goals"] == [] and [g["goal_id"] for g in view["unadmitted"]] == [gid]
    world.submit("GOAL", GOAL(), "fresh.json")                      # a new signature: admitted, body clock
    at = world.clock.now
    world.tick()
    view = world.projection()
    assert len(view["goals"]) == 1 and view["goals"][0]["goal_id"] != gid
    fresh = next(r for r in world.records(GoalRegistry.AUTHORIZED_RECORD)
                 if r["goal"]["goal_id"] == view["goals"][0]["goal_id"])
    from greg.journal import iso
    assert fresh["authorized_at"] == iso(at)


def test_a_rejected_goal_file_cannot_be_replayed_after_a_revoke(world, fast):
    import shutil
    gid, _ = world.start()
    world.submit("GOAL", GOAL(), "dup.json")                        # the founder re-signs the same goal
    world.tick()
    assert "identical goal is already authorized" in world.rejections()[-1]
    world.clock.advance(3600)
    world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "revoke", "reason": "drop this goal"}, "rev.json")
    world.tick()
    assert world.registry().state(gid).status == "revoked"
    world.clock.advance(3600)
    shutil.copy(world.home / "inbox" / "rejected" / "dup.json", world.home / "inbox" / "dup-again.json")
    result = world.tick()[0]
    assert result["commands"][0]["status"] == "REJECTED" and "replayed command nonce" in world.rejections()[-1]
    assert [g["goal_id"] for g in world.projection()["goals"]] == [gid]
    assert world.registry().state(gid).status == "revoked"


def test_a_goal_signed_before_a_revoke_cannot_bring_the_intent_back(world, fast):
    gid, _ = world.start()
    early = world.sign("GOAL", GOAL())                              # signed now, delivered only after the revoke
    world.clock.advance(60)
    world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "revoke", "reason": "drop this goal"}, "rev.json")
    world.tick()
    from tests.greg_fixtures import drop
    drop(world.home, early, "late.json")
    world.tick()
    assert "after this GOAL was signed" in world.rejections()[-1]
    world.submit("GOAL", GOAL(), "again.json")                      # signed after the revoke: the founder's choice
    world.tick()
    assert len(world.projection()["goals"]) == 2


def test_a_goal_may_not_name_a_strategy_the_founder_excluded(world, fast):
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    with world.body() as b:
        target = next(e for e in b.journal.replay("mission.registered") if e.payload.get("mission_id") == MID)
    world.submit("CRITIQUE", {"target_event_id": target.event_id, "verdict": "reject",
                              "evidence_type": "founder_judgment", "text": "never ship d this way",
                              "exclude_strategy": "w2"}, "b.json")
    world.tick()
    assert "w2" in world.book().missions[MID].excluded
    world.submit("GOAL", GOAL(), "c.json")
    out = world.tick()[0]
    assert [c["status"] for c in out["commands"]] == ["REJECTED"]
    assert "which you excluded by a signed critique" in world.rejections()[-1]
    world.tick(4)
    assert world.w2_requests() == []                                # neither the goal nor the mission asks
    assert world.records(GoalRegistry.AUTHORIZED_RECORD) == []


def test_the_goal_ask_path_refuses_an_excluded_strategy(world, fast):
    import pytest
    from greg.missions import MissionError
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    with world.body() as b:
        b.engine.exclude_strategy(MID, "w2", "never ship d this way", "critique:test")
        with pytest.raises(MissionError, match="excluded w2 by a signed critique"):
            b.engine.request_decision(MID, "w2", why="goal", recommendation="approve", now=world.clock.now)
    assert world.w2_requests() == []


def test_the_goal_ask_path_refuses_a_strategy_the_mission_would_not_select(world, fast):
    import pytest
    from greg.missions import MissionError
    world.submit("MISSION", world.mission_spec(), "a.json")
    world.tick()
    with world.body() as b:                       # the engine's own record of a refused attempt: w2 is failed
        b.journal.record("mission.action", {"mission_id": MID, "action_id": "w2", "attempt": 0, "status": "REFUSED",
                                            "reasons": ["unavailable for now"]}, key=["w2-refused"])
        with pytest.raises(MissionError, match="not selectable now"):
            b.engine.request_decision(MID, "w2", why="goal", recommendation="approve", now=world.clock.now)
    assert world.w2_requests() == []


# -- the guard restores every signed narrowing an unsigned record widened -----------------------------------

def _forge_state(world, gid, **changes):
    with world.body() as b:                                  # an unsigned, in-process goal-state record
        state = GoalRegistry(ledger=b.ledger).state(gid).to_dict()
        prefs = changes.pop("preferences", None)
        state.update(changes)
        if prefs is not None:
            state["preferences"] = {**state["preferences"], **prefs}
        state["version"] += 1
        b.ledger.append(GoalRegistry.TRANSITION_RECORD, {"source": "in-process", "goal_id": gid,
                                                         "reason": "unsigned", "state": state})


def test_an_unsigned_record_cannot_resurrect_a_founder_superseded_goal(world, fast):
    old, _ = world.start()
    world.tick(3)
    world.submit("GOAL", GOAL(intent="ship d first", supersedes=old), "change.json")
    world.tick()
    assert world.registry().state(old).status == "superseded"
    _forge_state(world, old, status="dormant")               # unsigned: undo the founder's signed supersede

    def wakes():
        return [r for r in world.records(GoalRegistry.TRANSITION_RECORD)
                if r["goal_id"] == old and r["reason"].startswith("wake")]
    before = len(wakes())
    world.clock.advance(120)
    world.ingest("ops", "is the watch healthy?")
    gravity = world.tick()[0]["gravity"]
    assert old not in gravity["woken"] and len(wakes()) == before
    assert world.registry().state(old).status == "superseded"            # restored from the signed GOAL
    world.tick(3)
    assert world.registry().state(old).status == "superseded"


def test_an_unsigned_record_cannot_undo_a_founder_revoke(world, fast):
    gid, _ = world.start()
    world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "revoke", "reason": "drop it"}, "rev.json")
    world.tick()
    _forge_state(world, gid, status="dormant")
    world.ingest("ops", "is the watch healthy?")
    assert gid not in world.tick()[0]["gravity"].get("woken", [])
    assert world.registry().state(gid).status == "revoked"


def test_an_unsigned_record_cannot_unmute_or_drop_any_signed_narrowing(world, fast):
    gid, _ = world.start()
    world.tick(3)
    for n, (kind, value) in enumerate((("do_not_monitor", "ops"), ("never_use_tactic", "cold outreach"),
                                       ("ask_before", "spend"), ("forget_route", "sha256:" + "f" * 64),
                                       ("revoke_capability", "net.http"))):
        world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": kind, "value": value, "reason": "narrow"}, f"c{n}.json")
    world.tick()
    world.ingest("ops", "noise on ops about the watch")              # about the goal: only the mute stops it
    assert gid not in world.tick()[0]["gravity"].get("woken", [])        # the signed mute works
    _forge_state(world, gid, preferences={"do_not_monitor": [], "never_use_tactic": [], "ask_before": [],
                                          "forgotten_routes": [], "revoked_capabilities": []})
    world.clock.advance(120)
    world.ingest("ops", "more on ops about the watch")
    gravity = world.tick()[0]["gravity"]
    assert gid not in gravity.get("woken", [])                            # restored before the turn
    prefs = world.registry().state(gid).preferences
    assert prefs["do_not_monitor"] == ["ops"] and prefs["never_use_tactic"] == ["cold outreach"]
    assert prefs["ask_before"] == ["spend"] and prefs["forgotten_routes"] == ["sha256:" + "f" * 64]
    assert prefs["revoked_capabilities"] == ["net.http"]


def test_an_unsigned_record_cannot_raise_priority_above_what_the_founder_signed(world, fast):
    gid, _ = world.start()
    world.tick(3)
    _forge_state(world, gid, preferences={"priority_override": 1})       # above the signed spec's 2
    world.tick()
    assert world.registry().effective_priority(gid) == 2
    world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "lower_priority", "value": 5, "reason": "later"})
    world.tick()
    assert world.registry().effective_priority(gid) == 5
    _forge_state(world, gid, preferences={"priority_override": 1})       # undo the signed lower
    world.tick(3)
    assert world.registry().effective_priority(gid) == 5
    assert next(g for g in world.projection()["goals"] if g["goal_id"] == gid)["priority"] == 5


# -- an observation counts only with the Gate receipt of its own check's sensor read -----------------------

def test_a_foreign_receipt_never_makes_a_forged_observation_evidence(world, fast):
    world.ws.mkdir(parents=True, exist_ok=True)
    (world.ws / "c.txt").write_text("ok - and the release notes say shipped")
    gid, _ = world.start()
    world.tick(3)                                             # c observed (pass), d observed (fail), w2 asked
    assert world.registry().state(gid).active_node_id == "ship"
    observed = world.events("mission.observed")
    c_obs = next(o for o in reversed(observed) if o["check_id"] == "c" and o["passed"] and o.get("receipt"))
    d_obs = next(o for o in reversed(observed) if o["check_id"] == "d" and not o["passed"])
    with world.body() as b:                                   # cites c's real Gate receipt, whose text says "shipped"
        b.journal.record("mission.observed", {**d_obs, "passed": True, "receipt": c_obs["receipt"],
                                              "detail": "trust me"}, key="forged-d")
    world.ingest("ops", "re-check the watch")
    world.tick(2)
    assert not (world.ws / "d.txt").exists()
    with world.body() as b:
        loop = gg.binding_for(b).loop
        belief = loop.world.belief(MID, "d")
        assert belief is not None and belief.value is False and belief.trust_level == "attributed"
        c = loop.world.belief(MID, "c")                       # a genuine read stays attributed evidence
        assert c.value is True and c.trust_level == "attributed"
    assert world.registry().state(gid).active_node_id == "ship"


# -- founder surfaces say who stopped a goal ----------------------------------------------------------------

def test_only_a_signed_stop_is_shown_as_stopped_by_you(world, fast):
    from greg.console import Console, render_home
    gid, _ = world.start()
    world.tick(2)
    with world.body() as b:                                  # an unsigned, in-process stop: narrowing, not the founder
        gg.binding_for(b).loop.registry.record_preference(gid, kind="stop_pushing", value=True, now=world.clock.now,
                                                          actor="some in-process module", reason="unsigned")
    world.tick(2)
    row = status(world.home)["gravity"]["goals"][0]
    assert row["status"] == "paused" and row["stopped_by_founder"] is False
    assert row["stop_label"] == "stopped by an unsigned record, not by you"
    page = render_home(Console(world.home)).decode()
    assert "stopped by you" not in page and "stopped by an unsigned record" in page
    world.submit("GOAL_CONTROL", {"goal_id": gid, "kind": "stop_pushing", "value": True, "reason": "quiet"})
    world.tick()
    row = status(world.home)["gravity"]["goals"][0]
    assert row["stopped_by_founder"] is True and row["stop_label"] == "stopped by you"
    assert "stopped by you" in render_home(Console(world.home)).decode()


def test_a_quarantined_goal_is_labelled_as_quarantine_not_as_your_stop(world, fast):
    world.start()
    body = GOAL(intent="signed for a different body")
    env = sign_command(world.key, "GOAL", body, body_id="some-other-body", now=world.clock.now)
    sid = _smuggle_acceptance(world, env)
    world.tick(2)
    row = next(g for g in world.projection()["unadmitted"] if g["goal_id"] == sid)
    assert row["stopped_by_founder"] is False and row["stop_label"].startswith("quarantined by admission")
