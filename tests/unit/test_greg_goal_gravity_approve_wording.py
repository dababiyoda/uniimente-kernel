"""approve_means / GOAL_GRAVITY.md must not offer the founder a reject the engine refuses after an approve.
Third review of PR #184: the wording 6352c68 added offered it."""
import re
from pathlib import Path

from greg import goal_gravity as gg
from tests.unit.test_greg_goal_gravity import GOAL, PaidWorld, World, fast, ship_move  # noqa: F401

DOC = Path(__file__).resolve().parents[2] / "docs" / "GOAL_GRAVITY.md"
OFFERS_REJECT = r"\breject(ing)? (it|the approv)"


def _run_approve_then_reject(world, goal=None):
    gid, _ = world.start(goal) if goal else world.start()
    world.tick(6)
    asks = [r for r in world.w2_requests() if (r.get("evidence") or {}).get("goal_id") == gid]
    assert len(asks) == 1
    rid = asks[0]["request_id"]
    world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship it"}, "c1-approve.json")
    world.submit("DECISION", {"request_id": rid, "answer": "reject", "reason": "end it before it runs"},
                 "c2-reject.json")
    world.tick(8)
    refused = "MissionError: decision already answered differently" in world.rejections()
    ran = any(e["action_id"] == "w2" and e["status"] == "DONE" for e in world.events("mission.action"))
    return asks[0]["evidence"]["approve_means"], refused, ran


def _approve_paragraph():
    text = DOC.read_text()
    start = text.index("**An approve")
    return text[start:text.index("\n\n", start)]


def _end_routes(text):
    """The sentences that tell the founder how to end an approve he has given ("end it", "end either sooner")."""
    sentences = re.split(r"(?<=[.;])\s+", " ".join(text.split()))
    return [x for x in sentences if re.search(r"\bend (it|either|the approv)", x, re.I)]


def test_paid_ask_does_not_offer_a_reject_the_engine_refuses(tmp_path, fast):
    told, refused, ran = _run_approve_then_reject(PaidWorld(tmp_path),
                                                  GOAL(moves=(ship_move(estimated_cost_usd=0.10),)))
    assert told == gg.APPROVE_MEANS_PAID
    if refused and ran:   # engine semantics: a reject after an approve is refused and the paid move runs
        assert _end_routes(told), told
        assert not [x for x in _end_routes(told) if re.search(OFFERS_REJECT, x, re.I)], \
            "the paid ask tells the founder he can end the approve by rejecting it; the engine refuses that reject"
        assert not [x for x in _end_routes(_approve_paragraph()) if re.search(OFFERS_REJECT, x, re.I)], \
            "GOAL_GRAVITY.md offers a reject the engine refuses"


def test_free_approve_doc_does_not_offer_a_reject_the_engine_refuses(tmp_path, fast):
    told, refused, ran = _run_approve_then_reject(World(tmp_path))
    assert told == gg.APPROVE_MEANS
    if refused and ran:
        assert not [x for x in _end_routes(told) if re.search(OFFERS_REJECT, x, re.I)]
        assert _end_routes(_approve_paragraph())
        assert not [x for x in _end_routes(_approve_paragraph()) if re.search(OFFERS_REJECT, x, re.I)], \
            "GOAL_GRAVITY.md offers a reject the engine refuses"
