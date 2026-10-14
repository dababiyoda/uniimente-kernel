"""Directive sections 12 and 28: a favorable intersection becomes one quantified, prepared opportunity package."""
from __future__ import annotations

from egregore.goals import GoalSpec, OpportunityFactor
from tests.unit.test_goal_gravity import (  # noqa: F401  (stack is a fixture)
    T0, T1, T2, governor, make_loop, obs, robotics_goal, signal, stack,
)


def baselined_goal(threshold=2.5):
    base = robotics_goal(wake_threshold=5.0)
    factors = [
        OpportunityFactor.build(factor_id="cheap-actuator", domain="hardware", subject="actuator", attribute="cost_usd",
                                direction="lte", threshold=500, weight=1.0, effect="cost_down", baseline=800),
        OpportunityFactor.build(factor_id="open-vision", domain="software", subject="vision_model", attribute="open_source_quality",
                                direction="gte", threshold=0.8, weight=1.0, effect="feasibility_up", baseline=0.5),
        OpportunityFactor.build(factor_id="talent", domain="talent", subject="engineers", attribute="available",
                                direction="gte", threshold=5, weight=1.0, effect="feasibility_up"),
    ]
    body = {**base.to_dict(), "opportunity_factors": [f.to_dict() for f in factors], "intersection_threshold": threshold}
    body.pop("goal_id")
    return GoalSpec.from_dict(body)


def weak_signals(at=T1, *, actuator_source="feed://hardware-prices"):
    return [signal("a", source=actuator_source, domain="hardware", observations=[obs("actuator", "cost_usd", 400)], observed_at=at),
            signal("v", source="feed://model-hub", domain="software", observations=[obs("vision_model", "open_source_quality", 0.9)], observed_at=at),
            signal("t", source="feed://layoffs", domain="talent", observations=[obs("engineers", "available", 9)], observed_at=at)]


def packages(loop):
    return [r.payload for r in loop.ledger.by_type(loop.opportunity.PACKAGE_RECORD)]


def test_a_favorable_intersection_is_quantified_against_baselines_and_nothing_executes(stack):
    loop = make_loop(stack)
    spec = baselined_goal()
    goal_id = loop.registry.authorize(spec, now=T0)
    turn = loop.turn(trigger_id="t1", now=T1, signals=weak_signals(), resources=governor(), evidence_confidence=0.9)
    assert turn.woken == (goal_id,) and turn.executed == ()
    [package] = packages(loop)
    q = {s["factor_id"]: s["quantified"] for s in package["satisfied"]}
    assert q["cheap-actuator"]["relative_improvement"] == round((800 - 400) / 800, 6)
    assert q["open-vision"]["relative_improvement"] == round((0.9 - 0.5) / 0.5, 6)
    assert q["talent"] is None   # no baseline declared: observed, not quantified
    assert all(s["evidence_ref"] and loop.ledger.find(s["evidence_ref"]) for s in package["satisfied"])
    assert {o["intervention_id"] for o in package["options"]} == {"compile-brief", "contact-engineers"}
    assert all(o["without_a_grant"] != "EXECUTE_AUTONOMOUSLY" for o in package["options"])
    assert package["position"]["active_node_id"] == "N1" and package["disposition"].startswith("prepared_not_executed")
    info = [i for i in turn.routing["immediate"] + turn.routing["batched"] if i["title"].endswith("favorable intersection")]
    assert info and "cheap-actuator +50%" in info[0]["question"] and info[0]["kind"] == "information"
    assert turn.processed[0]["opportunity_package"] == package["package_id"]


def test_one_package_per_factor_set_and_contested_factors_are_kept_out(stack):
    loop = make_loop(stack)
    loop.registry.authorize(baselined_goal(), now=T0)
    loop.turn(trigger_id="t1", now=T1, signals=weak_signals(), resources=governor(), evidence_confidence=0.9)
    loop.turn(trigger_id="t1-replay", now=T1, signals=weak_signals(), resources=governor(), evidence_confidence=0.9)
    assert len(packages(loop)) == 1
    other = make_loop(stack, ledger=type(loop.ledger)(stack[0].constitution_hash))
    other.registry.authorize(baselined_goal(threshold=1.5), now=T0)   # two clean factors suffice here
    disputed = weak_signals() + [signal("a2", source="feed://other-prices", domain="hardware",
                                        observations=[obs("actuator", "cost_usd", 950)])]
    other.turn(trigger_id="t1", now=T1, signals=disputed, resources=governor(), evidence_confidence=0.9)
    assert other.world.belief("actuator", "cost_usd").contradicted
    [pk] = packages(other)
    assert [c["factor_id"] for c in pk["contested"]] == ["cheap-actuator"]
    assert sorted(pk["contested"][0]["alternatives"] + [pk["contested"][0]["retained_value"]]) == [400, 950]
    assert "cheap-actuator" not in {s["factor_id"] for s in pk["satisfied"]}
