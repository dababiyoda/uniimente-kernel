"""A goal's paid move after #157 bound paid scopes to the mission's spend (second review of PR #184, findings 8-10).

AuthorityOffice.scope_digest binds a paid scope to the budget state ({spent_usd, budget_usd}): one paid approval
funds one attempt. 3ded0a7 made strategy_scope derive the same digest so a goal's approval takes effect, which
left three goal-side readings keyed to a digest that moves whenever the mission spends:

- every goal surface told the founder a paid approval was standing (APPROVE_MEANS), when it funds one run;
- the goal lost its own open ask, its signed reject and its projection after a preparation spend;
- ``greg goal evidence`` dropped the signed approval behind the goal's executed paid move.

The authority digest is unchanged. The goal side links its move by a spend-free move digest instead.
"""
from greg import goal_gravity as gg
from tests.greg_fixtures import mission, note_check, write_strategy
from tests.unit.test_greg_goal_gravity import GOAL, MID, PaidWorld, World, ship_move, fast  # noqa: F401


class PaidRepairWorld(World):
    """Mission F with a paid in-cone repair (w, $0.05) and a paid out-of-cone ship (w2, $0.10)."""
    def mission_spec(self, **kw):
        return mission(MID, checks=[note_check("c", self.ws / "c.txt", "ok"), note_check("d", self.ws / "d.txt", "shipped")],
                       strategies=[write_strategy("w", "c.txt", "ok", ["c"], cost_usd=0.05),
                                   write_strategy("w2", "d.txt", "shipped", ["d"], cost_usd=0.10)],
                       capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt"), budget=1.0,
                       closure={"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400}, **kw)


def _regress_c_and_prepare(world):
    (world.ws / "c.txt").write_text("damaged")
    world.ingest("ops", "c.txt looks broken")        # the goal wakes and pulls the blocked mission (observe_now)
    world.tick(3, step=30.0)                         # preparation re-runs the paid repair w while the ask is open


def _done(world, aid):
    return [e for e in world.events("mission.action") if e["action_id"] == aid and e["status"] == "DONE"]


def test_a_paid_goal_approval_says_what_the_engine_does_one_run_then_one_new_ask(tmp_path, fast):
    """Finding 8: APPROVE_MEANS promised a standing approval and no new ask after a regression; a paid approval
    funds one run at the approved spend state, and the regression opens exactly one new ask."""
    world = PaidWorld(tmp_path)          # w2 costs $0.10 of a $1.00 budget; target outside the cone
    gid, _ = world.start(GOAL(intent="ship d and keep it shipped", moves=(ship_move(estimated_cost_usd=0.10),)))
    world.tick(6)
    ask = [r for r in world.w2_requests() if r.get("evidence", {}).get("goal_id") == gid]
    assert len(ask) == 1
    ask = ask[0]
    assert ask["evidence"]["approve_means"] == gg.APPROVE_MEANS_PAID
    assert ask["evidence"]["approve_means"] == gg.approve_means(0.10, 1.0) != gg.approve_means(0.0, 1.0)
    assert "runs it once" in gg.APPROVE_MEANS_PAID and "standing" not in gg.APPROVE_MEANS_PAID
    assert ask["authority_requested"]["spend"] == "$0.10 for this one action"

    world.submit("DECISION", {"request_id": ask["request_id"], "answer": "approve", "reason": "ship it"})
    world.tick(8)
    assert len(_done(world, "w2")) == 1

    (world.ws / "d.txt").unlink()        # the check regresses
    world.clock.advance(1.1 * 86400)
    world.tick(8)
    asks = world.w2_requests()
    assert len(asks) == 2 and asks[0]["request_id"] == ask["request_id"]     # exactly one new ask, nothing re-spent
    assert len(_done(world, "w2")) == 1
    with world.body() as b:
        shown = {a["request_id"]: a["approve_means"] for a in gg.evidence(b.journal, gid)["asks"]}
    assert shown[ask["request_id"]] == gg.APPROVE_MEANS_PAID
    assert world.projection()["approve_means"] == {"free": gg.APPROVE_MEANS, "paid": gg.APPROVE_MEANS_PAID}


def test_a_signed_reject_of_the_goals_paid_ask_is_remembered_by_the_goal_after_preparation_spends(tmp_path, fast):
    """Finding 9: a preparation spend moved the digest, so the goal blamed its own open ask and never mirrored the
    founder's signed reject into its refused routes."""
    world = PaidRepairWorld(tmp_path)
    gid, _ = world.start(GOAL(moves=(ship_move(estimated_cost_usd=0.10),)))
    world.tick(6)
    ask = [r for r in world.w2_requests() if (r.get("evidence") or {}).get("goal_id") == gid]
    assert len(ask) == 1
    rid = ask[0]["request_id"]
    spent_at_ask = world.book().missions[MID].spent_usd
    _regress_c_and_prepare(world)
    assert world.book().missions[MID].spent_usd > spent_at_ask      # preparation spent while the founder decides
    assert not [n for n in world.events("goal.notice") if n["kind"] == "ask_not_recorded" and rid in n.get("why", "")]
    world.submit("DECISION", {"request_id": rid, "answer": "reject", "reason": "not this way"})
    world.tick(6)
    assert world.book().missions[MID].failed["w2"].startswith("founder rejected")   # the mission took the reject
    assert world.registry().is_route_refused(gid, ship_move(estimated_cost_usd=0.10).route_hash)
    assert world.projection()["goals"][0]["refused_routes"] == 1


def test_the_goal_surfaces_keep_the_open_approval_for_its_move_after_preparation_spends(tmp_path, fast):
    """Finding 9: the mission was blocked on the goal's move while the goal's projection and evidence showed no ask."""
    world = PaidRepairWorld(tmp_path)
    world.submit("MISSION", world.mission_spec(), "a-mission.json")
    world.tick(6)
    rid = world.w2_requests()[0]["request_id"]              # the loop's own ask for w2
    world.submit("GOAL", GOAL(moves=(ship_move(estimated_cost_usd=0.10),)), "b-goal.json")
    out = world.tick(3)
    gid = [c for c in out[0]["commands"] if c["status"] == "APPLIED"][0]["result"]["goal_id"]
    assert world.projection()["goals"][0]["open_requests"] == [rid]
    _regress_c_and_prepare(world)
    book = world.book()
    assert book.missions[MID].blocker["request_id"] == rid and rid in [r["request_id"] for r in book.open_requests()]
    assert world.projection()["goals"][0]["open_requests"] == [rid]     # the mission is blocked on the goal's move
    with world.body() as b:
        assert rid in [a["request_id"] for a in gg.evidence(b.journal, gid)["asks"]]


def test_goal_evidence_keeps_the_signed_approval_behind_its_executed_paid_move(tmp_path, fast):
    """Finding 10: once the approved paid move ran, its digest moved and ``greg goal evidence`` dropped the founder's
    signed approval behind the goal's only consequential action."""
    world = PaidWorld(tmp_path)
    world.submit("MISSION", world.mission_spec(), "a-mission.json")
    world.tick(6)                                       # the mission's own loop asks about paid w2 (outside cone)
    loop_asks = world.w2_requests()
    assert len(loop_asks) == 1 and "goal_id" not in (loop_asks[0].get("evidence") or {})
    rid = loop_asks[0]["request_id"]

    world.submit("GOAL", GOAL(moves=(ship_move(estimated_cost_usd=0.10),)), "b-goal.json")
    out = world.tick(3)
    gid = [c for c in out[0]["commands"] if c["status"] == "APPLIED"][0]["result"]["goal_id"]
    assert [r["request_id"] for r in world.w2_requests()] == [rid]       # one scope, one ask: the goal reuses it
    with world.body() as b:
        assert [a["request_id"] for a in gg.evidence(b.journal, gid)["asks"]] == [rid]

    world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship"})
    world.tick(6)
    assert len(_done(world, "w2")) == 1 and (world.ws / "d.txt").read_text() == "shipped"

    with world.body() as b:
        asks = gg.evidence(b.journal, gid)["asks"]
    assert [a["request_id"] for a in asks] == [rid]
    assert asks[0]["answer"] == "approve" and asks[0]["answer_signature_verified"] is True
    assert asks[0]["approve_means"] == gg.APPROVE_MEANS_PAID


def test_a_request_recorded_before_the_move_digest_still_links_by_its_scope_digest(tmp_path, fast):
    """Ledgers written before the move digest existed keep their links: an APPROVAL without ``move_digest`` matches
    on the scope digest, as it did."""
    scope = {"mission_id": MID, "scope_digest": "sha256:a", "move_digest": "sha256:b"}
    assert gg.asks_for_move({"kind": "APPROVAL", "mission_id": MID, "scope_digest": "sha256:a"}, scope)
    assert not gg.asks_for_move({"kind": "APPROVAL", "mission_id": MID, "scope_digest": "sha256:c"}, scope)
    assert gg.asks_for_move({"kind": "APPROVAL", "mission_id": MID, "scope_digest": "sha256:c",
                             "move_digest": "sha256:b"}, scope)
    assert not gg.asks_for_move({"kind": "APPROVAL", "mission_id": MID, "scope_digest": "sha256:a",
                                 "move_digest": "sha256:x"}, scope)
    assert not gg.asks_for_move({"kind": "COMPENSATION", "mission_id": MID, "move_digest": "sha256:b"}, scope)
    assert not gg.asks_for_move({"kind": "APPROVAL", "mission_id": "m:other", "move_digest": "sha256:b"}, scope)
