"""Mission L (whole-machine comprehension): one founder-signed mission traced through all nine links in one run.

Directive 2026-10-13 section 33, Mission L: "From the founder interface, trace a single mission through:
Goal -> Mind -> Organs -> Body -> Action -> Evidence -> Outcome -> Learning -> Updated Goal." The per-link owners,
code paths and proofs are in acceptance/missions.json (Mission L trace). This test runs them as one chain:

- Goal: a founder-signed GOAL is admitted onto the Body ledger and binds the mission;
- Mind: the mission's `think` step runs bounded formal cognition (cognition.seed.solve) and its receipt answers;
- Organs: its `assess` step runs RailScout and WealthMachine through venture.assess (the stand-in organs of
  tests/unit/test_greg_ventures.py, with the real organs' entry points) and delivers one memo;
- Body and Action: every step is dispatched by the one mission engine through the one Consequence Gate, and
  the out-of-cone ship waits for the founder's signed approve;
- Evidence: every action is receipted on the hash-chained ledger;
- Outcome: the separate-process appraiser verifies the mission's closure;
- Learning: the mission's own outcomes become routing knowledge for each capability it used;
- Updated Goal: after the outcome, the goal's active node is recalculated;
- and `greg foundry trace --mission` (the founder interface) shows the chain.

In-process Body with a deterministic clock (SANDBOX tier); the founder key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

import json

from greg import cli, goal_gravity as gg, routing
from greg.body import Layout
from tests.unit.test_greg_cognition_seed_path import estimation, problem
from tests.unit.test_greg_goal_gravity import MID, World, expected_w2_request
from tests.unit.test_greg_ventures import organs  # noqa: F401  (pytest fixture: stand-in organs under data/)
from tests.greg_fixtures import mission, note_check, write_strategy

PID = "whole-machine"


class WholeWorld(World):
    """The Mission F world, whose mission also thinks (Mind) and assesses a venture (Organs)."""

    def __init__(self, tmp, organ_params):
        super().__init__(tmp)
        self.organ_params = organ_params

    def mission_spec(self, **kw):
        cognition_target = "cognition:" + PID
        think = {"action_id": "think", "capability": "cognition.seed.solve", "target": cognition_target,
                 "params": {"problem": problem("estimation", estimation(), name=PID)}, "advances": ["answered"],
                 "rationale": "smallest eligible bounded method, typed proof, independent checks"}
        assess = {"action_id": "assess", "capability": "venture.assess", "params": dict(self.organ_params),
                  "target": "deliver:ventures", "advances": ["assessed"],
                  "rationale": "run both organs read-only on source bytes; deliver one memo"}
        checks = [
            {"check_id": "answered", "description": "the bounded computation is answered",
             "sensor": {"capability": "cognition.status", "target": cognition_target, "params": {"problem_id": PID}},
             "predicate": {"op": "equals", "field": "answered", "value": True}},
            {"check_id": "assessed", "description": "a venture memo exists for this signal",
             "sensor": {"capability": "venture.status", "target": "deliver:ventures",
                        "params": {"manifest": self.organ_params["manifest"]}},
             "predicate": {"op": "equals", "field": "assessed", "value": True}},
            note_check("c", self.ws / "c.txt", "ok"), note_check("d", self.ws / "d.txt", "shipped")]
        return mission(MID, checks=checks,
                       strategies=[think, assess, write_strategy("w", "c.txt", "ok", ["c"]),
                                   write_strategy("w2", "d.txt", "shipped", ["d"])],
                       capabilities=["fs.read", "fs.write", "cognition.seed.solve", "cognition.status",
                                     "venture.assess", "venture.status"],
                       targets=("fs:*", "workspace:c.txt", cognition_target, "deliver:ventures"),
                       closure={"kind": "infinite", "ladder": [["answered", "assessed", "c"], ["d"]],
                                "cadence_seconds": 86400}, **kw)


def test_one_signed_mission_runs_goal_to_updated_goal_and_the_founder_can_trace_it(tmp_path, organs, capsys):
    world = WholeWorld(tmp_path, organs)
    gid, _ = world.start()                                              # Goal: signed GOAL + MISSION admitted
    rid, _ = expected_w2_request(world)
    world.tick(8)
    actions = {a["action_id"]: a for a in world.events("mission.action") if a["status"] == "DONE"}
    assert {"think", "assess", "w"} <= set(actions), sorted(actions)
    assert actions["think"]["capability"] == "cognition.seed.solve"         # Mind
    assert actions["assess"]["capability"] == "venture.assess"              # Organs
    assert list((Layout(world.home).home / "deliveries" / "ventures").glob("venture-*.md"))
    assert [a["request_id"] for a in world.w2_requests()] == [rid]           # Body: the out-of-cone move asks
    world.submit("DECISION", {"request_id": rid, "answer": "approve", "reason": "ship it"})
    world.tick(4)
    assert (world.ws / "d.txt").read_text() == "shipped"                     # Action, after the signed approve

    with world.body() as b:                                                  # Evidence: receipts on the chain
        assert b.ledger.verify_chain()[0]
        done = [a for a in (e.payload for e in b.journal.replay("mission.action")) if a["status"] == "DONE"]
        assert all(b.ledger.find(a["receipt"]).record_type == "receipt" for a in done)
        assert gg.ledger_closure(b.journal)["ok"]
        verdicts = [e.payload["verdict"] for e in b.journal.replay("mission.appraised")
                    if e.payload["mission_id"] == MID]
        knowledge = {r["capability"]: r for r in routing.routing_knowledge(b.journal)}
    assert verdicts and verdicts[-1] == "VERIFIED", verdicts                  # Outcome: separate appraiser
    for capability in ("cognition.seed.solve", "venture.assess", "fs.write"):  # Learning: routing knowledge
        assert knowledge[capability]["done"] >= 1, knowledge.get(capability)

    world.ingest("ops", "check the watch after shipping")
    world.tick(2)
    assert world.registry().state(gid).active_node_id == "n1"                # Updated Goal: bottleneck moved

    capsys.readouterr()
    assert cli.main(["--home", str(world.home), "foundry", "trace", "--mission", MID]) == 0
    trace = json.dumps(json.loads(capsys.readouterr().out))                  # the founder interface's trace
    for capability in ("cognition.seed.solve", "venture.assess", "fs.write"):
        assert capability in trace
    assert rid in trace
