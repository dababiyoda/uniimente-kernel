"""Kill window during Goal Gravity preparation (Mission F): an UNCERTAIN in-cone repair dispatched by ``_prepare``
while the mission waits on an open APPROVAL, with the body killed before its reconciliation question (or the block
on it) is durable. The restarted body must ask, not dispatch the next attempt blind, and the founder's answer must
release the interrupted attempt's held cap.

Real Body, real Ed25519 test founder key (NOT Alfonso's), signed MISSION/GOAL/DECISION commands, data-plane ingest.
"""
from __future__ import annotations

import pytest

from egregore.goals import GoalSpec, InterventionSpec, PlanNode, WakeCondition
from greg import capabilities, dataplane, goal_gravity as gg
from greg.body import Body
from greg.missions import MissionBook, MissionEngine
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

MID = "m:watch"


class Killed(BaseException):
    """SIGKILL, as far as the mission loop can tell: nothing after it runs."""


def _kill_once(monkeypatch, method, matches):
    real = getattr(MissionEngine, method)
    armed = {"on": True}

    def dies(self, m, *args, **kwargs):
        if armed["on"] and matches(*args, **kwargs):
            armed["on"] = False
            raise Killed(method)
        return real(self, m, *args, **kwargs)
    monkeypatch.setattr(MissionEngine, method, dies)


def _goal():
    ship = InterventionSpec.build(
        intervention_id="ship", description="write d.txt (outside the mission's cone)", action_class="greg.fs.write",
        requested_capability="fs.write", consequence_class="internal_write", target="workspace:d.txt",
        expected_outcome="d.txt says shipped", payload={"mission_id": MID, "action_id": "w2"})
    spec = GoalSpec.build(
        founder_intent="keep the watch healthy and ship d", desired_state="d shipped", priority=2,
        authority={"authorized_by": "x", "authorization_ref": "x", "legal_principal": "alfonso_lopez",
                   "max_consequence_class": "internal_write"}, time_horizon="weeks",
        plan=[PlanNode.build(node_id="ship", outcome="d shipped", gate="founder decides the out-of-cone write",
                             sbm=f"{MID}.d", sbm_direction="eq", sbm_target=True, interventions=(ship,))],
        wake_conditions=(WakeCondition.build(kind="subject", match=MID), WakeCondition.build(kind="domain", match="ops")),
        review_cadence_seconds=7 * 86400)
    body = {k: v for k, v in spec.to_dict().items() if k not in gg.DERIVED_GOAL_FIELDS}
    return {"goal": body, "missions": [MID], "max_consequence_class": "internal_write"}


class World:
    def __init__(self, tmp, repair):
        self.home, self.key, self.body_id, _ = make_body(tmp)
        self.clock = Clock()
        self.ws = workspace(self.home, MID)
        self.repair = repair

    def submit(self, kind, body, name=None):
        drop(self.home, signed(self.key, self.body_id, kind, body, now=self.clock.now), name)

    def tick(self, n=1, step=1.0):
        with Body(self.home, clock=self.clock) as b:          # every call is a fresh Body rebuilt from disk
            for _ in range(n):
                b.tick()
                self.clock.advance(step)

    def ingest(self, channel, content):
        with Body(self.home, clock=self.clock) as b:
            dataplane.ingest(b.journal, source=f"feed://{channel}", content=content, channel=channel)

    def events(self, prefix):
        with Body(self.home, clock=self.clock) as b:
            return [e.payload for e in b.journal.replay(prefix)]

    def mission(self):
        with Body(self.home, clock=self.clock) as b:
            return MissionBook(b.journal).missions[MID]

    def start(self, *, budget=0.0, extra_caps=(), extra_targets=()):
        spec = mission(MID, checks=[note_check("c", self.ws / "c.txt", "ok"), note_check("d", self.ws / "d.txt", "shipped")],
                       strategies=[self.repair, write_strategy("w2", "d.txt", "shipped", ["d"])],
                       capabilities=["fs.read", "fs.write", *extra_caps],
                       targets=("fs:*", "workspace:c.txt", *extra_targets), budget=budget,
                       closure={"kind": "infinite", "ladder": [["c"], ["d"]], "cadence_seconds": 86400})
        self.submit("MISSION", spec, "a-mission.json")         # inbox order: the mission before the goal binding it
        self.submit("GOAL", _goal(), "b-goal.json")
        self.tick(7)
        m = self.mission()
        assert m.blocker and m.blocker.get("action_id") == "w2", m.blocker   # waiting on the out-of-cone APPROVAL
        assert not [e for e in self.events("command.rejected")], self.events("command.rejected")


def _reconciliations(world):
    return [r for r in world.events("decision.requested") if r["kind"] == "RECONCILIATION"]


def test_kill_before_the_question_during_preparation_does_not_redispatch_blind(tmp_path, monkeypatch):
    world = World(tmp_path, write_strategy("w", "c.txt", "ok", ["c"]))
    manifest, real = capabilities.BUILTINS["fs.write"]
    assert not manifest.retry_safe
    armed = {"on": False}
    calls = []

    def write(params, ctx):
        if params.get("relative_path") == "c.txt":
            calls.append(armed["on"])
            if armed["on"]:
                raise RuntimeError("power lost mid-effect")
        return real(params, ctx)
    monkeypatch.setitem(capabilities.BUILTINS, "fs.write", (manifest, write))
    world.start()
    (world.ws / "c.txt").write_text("damaged")
    armed["on"] = True
    _kill_once(monkeypatch, "_request", lambda **kw: kw.get("kind") == "RECONCILIATION")
    world.ingest("ops", "c.txt looks broken")                 # the goal pulls the mission: _prepare repairs c
    with pytest.raises(Killed):
        world.tick(3, step=30.0)
    armed["on"] = False
    m = world.mission()
    assert m.blocker["action_id"] == "w2" and "w" in m.uncertain and _reconciliations(world) == []
    interrupted = len(calls)
    world.tick(3, step=30.0)                                  # restart
    assert len(calls) == interrupted, "a non-retry-safe act was dispatched again with no founder answer"
    assert [r["action_id"] for r in _reconciliations(world)] == ["w"], "the lost question was never asked"


def test_kill_before_the_block_during_preparation_priced_hold_released_by_the_answer(tmp_path, monkeypatch):
    commission = {"action_id": "w", "capability": "worker.commission", "target": "work:c",
                  "params": {"order": "o1", "objective": "x", "acceptance": {}, "allowed_paths": ["a"],
                             "max_budget_usd": 0.05},
                  "cost_usd": 0.05, "advances": ["c"], "rationale": "commission"}
    world = World(tmp_path, commission)
    manifest, _ = capabilities.BUILTINS["worker.commission"]
    armed = {"on": False}
    calls = []

    def worker(params, ctx):
        calls.append(armed["on"])
        if armed["on"]:
            return {"status": "UNCERTAIN", "changed_files": [], "patch_sha256": "", "greg_tests_passed": False,
                    "worker": {"interrupted": True}}
        world.ws.mkdir(parents=True, exist_ok=True)
        (world.ws / "c.txt").write_text("ok")
        return {"status": "DONE", "changed_files": ["c.txt"], "patch_sha256": "", "greg_tests_passed": True,
                "worker": {}, "provider_reported_usd": 0.01}
    monkeypatch.setitem(capabilities.BUILTINS, "worker.commission", (manifest, worker))
    world.start(budget=0.20, extra_caps=("worker.commission",), extra_targets=("work:*",))
    (world.ws / "c.txt").write_text("damaged")
    armed["on"] = True
    _kill_once(monkeypatch, "_block", lambda blocker: blocker.get("type") == "reconciliation")
    world.ingest("ops", "c.txt looks broken")
    with pytest.raises(Killed):
        world.tick(3, step=30.0)
    armed["on"] = False
    [question] = _reconciliations(world)                      # asked, but the block on it was lost
    paid = len(calls)
    world.tick(3, step=30.0)                                  # restart
    assert len(calls) == paid, f"a second paid dispatch ran with no founder answer: {calls}"
    world.submit("DECISION", {"request_id": question["request_id"], "answer": "reconcile_not_executed"})
    world.tick(3, step=30.0)
    m = world.mission()
    held = [slot for slot in m.reserved if slot[0] == "w"]
    assert not held, f"the founder's reconcile_not_executed answer never released the held cap: {m.reserved}"
