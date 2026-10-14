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
