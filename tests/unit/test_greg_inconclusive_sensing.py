"""An abstaining cognitive sensor did not measure the world.

Under host load a budget-bounded solve may return a receipt with no answer
(TIMEOUT, BUDGET_EXHAUSTED, ...). Reading its missing field as a negative
observation booked routing.outcome "ineffective" against the executed
strategy's capability, lowering its reliability for every future mission.
The observation is now labelled inconclusive and never blames the strategy.
The mission keeps its retry cadence: learned routing settles the lead
engine's resource failure from those retries (a real signal at that layer).
"""
from greg.body import Body
from greg.missions import MissionBook, blames_strategy, unanswered
from tests.greg_fixtures import make_body, mission, signed

PARAMS = {"problem_id": "qualified:game", "operation": "minimax", "data": {"payoffs": [[1, -1], [-1, 1]]}}


def test_unanswered_separates_abstention_from_answers_and_refutations():
    assert unanswered(None) is None and unanswered({"value": 0}) is None
    assert unanswered({"abstention_state": "NONE", "output": {"value": 0}}) is None
    assert unanswered({"abstention_state": "REFUTED", "output": None}) is None, "a refutation is a real negative result"
    assert unanswered({"abstention_state": "UNKNOWN", "reason_code": "TIMEOUT", "output": None}) == "TIMEOUT"
    assert unanswered({"abstention_state": "CAPABILITY_DEFICIT", "output": None}) == "CAPABILITY_DEFICIT"


def test_only_a_measured_unchanged_world_blames_the_strategy():
    assert blames_strategy("executed but value still failing: 1 == 0")
    assert not blames_strategy("executed but value still failing: sensor inconclusive (TIMEOUT): field 'output.value' absent")
    assert not blames_strategy("executed but value still failing: sensor UNAVAILABLE: adapter down")
    assert not blames_strategy("capability refused: outside cone")


def test_an_unmeasured_world_keeps_the_retry_cadence_but_books_no_blame(tmp_path):
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
        # cadence unchanged: the mission replans and retries as before...
        assert state.failed["recompute"].startswith("executed but value still failing: sensor inconclusive")
        # ...but the reason never counts against the capability's routing reliability
        assert not blames_strategy(state.failed["recompute"])
