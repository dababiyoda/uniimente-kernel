"""Scratch experiment (not repository code): G on a real Body, unchanged integration head.

G1: three weak, relevant intake items from three independent sources, each below the goal's wake threshold.
G2: one relevant sentence repeated by four sources on four ticks, each alone at the wake threshold."""
import json, sys, tempfile
from pathlib import Path
from egregore.goals import GoalSpec, PlanNode, WakeCondition
from greg import dataplane, goal_gravity as gg
from greg.body import Body
import tests.unit.test_greg_goal_gravity as T

Body._close_out = lambda self, now: None      # as the tests' ``fast`` fixture: skip the separate appraiser


def goal(threshold):
    spec = GoalSpec.build(
        founder_intent="keep the watch healthy and ship d", desired_state="d shipped", priority=2,
        authority={"authorized_by": "x", "authorization_ref": "x", "legal_principal": "alfonso_lopez",
                   "max_consequence_class": "internal_write"}, time_horizon="weeks",
        plan=[PlanNode.build(node_id="ship", outcome="d shipped", gate="founder decides", sbm=f"{T.MID}.d",
                             sbm_direction="eq", sbm_target=True, interventions=(T.ship_move(),))],
        wake_conditions=(WakeCondition.build(kind="subject", match=T.MID, weight=1.0),),
        wake_threshold=threshold, review_cadence_seconds=7 * 86400)
    body = {k: v for k, v in spec.to_dict().items() if k not in gg.DERIVED_GOAL_FIELDS}
    return {"goal": body, "missions": [T.MID], "max_consequence_class": "internal_write"}


def pulls(world):
    return len([e for e in world.events("mission.schedule") if "cause" in e])


def ingest(world, source, text):
    with world.body() as b:
        return dataplane.ingest(b.journal, source=source, content=text, channel="ops")


out = {}
base = Path(tempfile.mkdtemp(dir=sys.argv[1]))
# G1 --------------------------------------------------------------------------------------------------------
(base / "g1").mkdir(); (base / "g2").mkdir()
w = T.World(base / "g1")
gid, _ = w.start(goal(2.0))
w.tick(4)
before = pulls(w)
for i, text in enumerate(["the watch file c.txt looks stale", "someone reports c.txt is wrong", "c.txt differs from yesterday"]):
    ingest(w, f"feed://independent-{i}", text)
turns = w.tick(2)
out["G1_three_weak_independent_sources_threshold_2"] = {
    "woken": [t.get("gravity", {}).get("woken", []) for t in turns], "pulls_added": pulls(w) - before}
# G2 --------------------------------------------------------------------------------------------------------
w = T.World(base / "g2")
gid, _ = w.start(goal(1.0))
w.tick(4)
before, woken = pulls(w), []
for i in range(4):
    ingest(w, f"feed://copy-{i}", "c.txt looks broken")          # the same sentence, four sources
    woken.append(w.tick()[0].get("gravity", {}).get("woken", []))
with w.body() as b:
    ev = dataplane.community_evidence(b.journal, "ops")
out["G2_same_sentence_from_four_sources_threshold_1"] = {
    "woken_per_tick": woken, "pulls_added": pulls(w) - before,
    "community_evidence_distinct_claims": ev["distinct_claims"],
    "community_evidence_flags": ev["coordination_flags"]}
print(json.dumps(out, indent=1, default=str))
