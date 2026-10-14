"""An abstaining cognitive sensor did not measure the world.

Under host load a budget-bounded solve may return a receipt with no answer
(TIMEOUT, BUDGET_EXHAUSTED, ...). Reading its missing field as a negative
observation booked the world as unchanged and blamed the executed strategy,
which then lowered that capability's learned routing reliability for every
future mission. The observation is now a sensor error: bounded retry, then
escalation, and the strategy's effect stays unknown instead of refuted.
"""
from greg.body import Body
from greg.missions import MissionBook, unanswered
from tests.greg_fixtures import make_body, mission, signed

PARAMS = {"problem_id": "qualified:game", "operation": "minimax", "data": {"payoffs": [[1, -1], [-1, 1]]}}


def test_unanswered_separates_abstention_from_answers_and_refutations():
    assert unanswered(None) is None and unanswered({"value": 0}) is None
    assert unanswered({"abstention_state": "NONE", "output": {"value": 0}}) is None
    assert unanswered({"abstention_state": "REFUTED", "output": None}) is None, "a refutation is a real negative result"
    assert unanswered({"abstention_state": "UNKNOWN", "reason_code": "TIMEOUT", "output": None}) == "TIMEOUT"
    assert unanswered({"abstention_state": "CAPABILITY_DEFICIT", "output": None}) == "CAPABILITY_DEFICIT"


def test_an_unmeasured_world_never_blames_the_executed_strategy(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = mission("m:game", checks=[{
        "check_id": "value", "description": "minimax value",
        "sensor": {"capability": "cognition.solve", "target": "cognition:game", "params": PARAMS},
        "predicate": {"op": "equals", "field": "output.value", "value": 0}}],
        strategies=[{"action_id": "recompute", "capability": "cognition.solve", "target": "cognition:game",
                     "params": PARAMS, "advances": ["value"], "rationale": "bounded numeric minimax"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec))
        journal = body.journal
        journal.record("mission.action", {"mission_id": "m:game", "action_id": "recompute", "attempt": 0, "status": "DONE",
                                          "reasons": [], "receipt": "sha256:" + "1" * 64, "capability": "cognition.solve",
                                          "cost_usd": 0.0}, key=["m:game", "recompute", 0])
        journal.record("mission.observed", {"mission_id": "m:game", "check_id": "value", "passed": False,
                                            "detail": "sensor inconclusive (TIMEOUT): field 'output.value' absent",
                                            "receipt": "sha256:" + "2" * 64, "rung": 0, "at": "2026-10-14T00:00:00Z"},
                       key=["m:game", "value", "p1"])
        state = MissionBook(journal).missions["m:game"]
        assert "recompute" not in state.failed and state.pending_effect.get("recompute") == {"value"}
        # control: a conclusive negative observation still marks the surprise and replans
        journal.record("mission.observed", {"mission_id": "m:game", "check_id": "value", "passed": False,
                                            "detail": "1 == 0", "receipt": "sha256:" + "3" * 64, "rung": 0,
                                            "at": "2026-10-14T00:01:00Z"}, key=["m:game", "value", "p2"])
        state = MissionBook(journal).missions["m:game"]
        assert state.failed["recompute"].startswith("executed but value still failing: 1 == 0")
