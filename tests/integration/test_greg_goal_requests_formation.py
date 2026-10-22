"""A goal can ask for a capability, not only wake on one (LEAP A joined to Capability Genesis).

A founder-signed goal's plan node requires ``selection.closure@function``: any usable implementation of
portfolio selection under prerequisites. Its bound mission (an unrelated, standing note mission) never
needs that function, so no mission step would ever report the deficit. When the goal wakes and its plan
reads the function missing, GREG asks Genesis to form it under the goal's signed mission: formation only.
Nothing is attached by the goal, no builder is commissioned and no mission is blocked; each verified
result waits for the founder's signed CAPABILITY_ATTACH, and the goal's deficit closes once one serves.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from egregore.goals import GoalSpec, PlanNode, WakeCondition  # noqa: E402
from greg import goal_gravity as gg  # noqa: E402
from greg.body import Body  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, \
    write_strategy  # noqa: E402

ENGINE = "acquired.graph.max_flow.networkx"
NEEDS = "selection.closure@function"


def note_mission(home):
    mid = "m:standing-note"
    path = workspace(home, mid) / "note.txt"
    return mission(mid, checks=[note_check("noted", path, "portfolio")],
                   strategies=[write_strategy("write", "note.txt", "portfolio review", ["noted"])],
                   # Adversarial: the mission's own signed read-only auto_attach covers both capabilities, and
                   # still a goal's request attaches neither.
                   capabilities=["fs.read", "fs.write", "acquired.graph.max_flow.*", "composed.selection.closure.*"],
                   closure={"kind": "infinite"}, auto_attach=True)


def goal_for(mid, requires=(NEEDS,)):
    spec = GoalSpec.build(
        founder_intent="decide which offers to build", desired_state="certified portfolio decisions", priority=2,
        authority={"authorized_by": "x", "authorization_ref": "x", "legal_principal": "alfonso_lopez",
                   "max_consequence_class": "read_only"}, time_horizon="weeks",
        plan=[PlanNode.build(node_id="decide", outcome="portfolio decisions GREG can certify", gate="none",
                             sbm=f"{mid}.portfolio-decided", sbm_direction="eq", sbm_target=True,
                             interventions=(), requires_capabilities=requires)],
        wake_conditions=(WakeCondition.build(kind="subject", match=mid),), review_cadence_seconds=7 * 86400)
    return {"goal": {k: v for k, v in spec.to_dict().items() if k not in gg.DERIVED_GOAL_FIELDS},
            "missions": [mid], "max_consequence_class": "read_only"}


def settle(body, clock, n=3):
    out = []
    for _ in range(n):
        out.append(body.tick())
        clock.advance(3600)
    return out


def goal_deficits(body):
    return [e.payload for e in body.journal.replay("deficit.opened") if e.payload.get("requested_by_goal")]


def composed(body):
    return [c for c in body.registry.manifests if c.startswith("composed.selection.closure.")]


def test_a_goal_asks_genesis_to_form_the_function_its_plan_requires_and_never_attaches_it(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = note_mission(home)
    mid = spec["mission_id"]
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        settle(body, clock, 1)
    drop(home, signed(key, body_id, "GOAL", goal_for(mid)))
    with Body(home, clock=clock) as body:
        body.boot()
        ticks = settle(body, clock, 3)
        [goal_id] = gg.binding_for(body).loop.registry.goals()
        asked = [f for t in ticks for f in t["gravity"].get("formation_requested", [])]
        assert asked and asked[0] == {"goal_id": goal_id, "function": "selection.closure", "mission_id": mid,
                                      "serving": None}
        # The construction needs its engine attached first: Genesis acquired the engine, and it waits for you.
        assert body.registry.state[ENGINE] == "VERIFIED" and composed(body) == []
        opened = {d["function"]: d for d in goal_deficits(body)}
        assert set(opened) == {"selection.closure", "graph.max_flow"}
        assert {d["requested_by_goal"] for d in opened.values()} == {goal_id}
        waiting = [e.payload for e in body.journal.replay("deficit.awaiting_attach")]
        assert [w["capability_id"] for w in waiting] == [ENGINE] and "your signed CAPABILITY_ATTACH" in waiting[0]["why"]
        routes = [e.payload for e in body.journal.replay("genesis.route")
                  if e.payload["deficit_id"] == opened["graph.max_flow"]["deficit_id"]]
        assert not any(r["route"] == "builder" and "commissions" not in r["result"] for r in routes)
        m = body.engine.book.missions[mid]
        assert m.blocker is None or m.blocker.get("type") != "capability"     # the mission is never blocked by it
        assert NEEDS in gg.binding_for(body).loop.registry.state(goal_id).missing_capabilities

    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": ENGINE}))
    with Body(home, clock=clock) as body:
        body.boot()
        [woke] = settle(body, clock, 1)
        assert woke["gravity"]["woken"] == [goal_id]                    # perceived the engine you attached
        [construction] = composed(body)
        assert body.registry.state[construction] == "VERIFIED"          # formed over it, and not attached by it
        assert NEEDS in gg.binding_for(body).loop.registry.state(goal_id).missing_capabilities

    drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": construction}))
    with Body(home, clock=clock) as body:
        body.boot()
        ticks = settle(body, clock, 2)
        closed = [d for t in ticks for d in t["gravity"].get("formations_closed", [])]
        assert opened["selection.closure"]["deficit_id"] in closed
        resolved = {e.payload["deficit_id"]: e.payload for e in body.journal.replay("deficit.resolved")}
        assert resolved[opened["selection.closure"]["deficit_id"]]["capability_id"] == construction
        assert resolved[opened["selection.closure"]["deficit_id"]]["resume"] == f"goal {goal_id}"
        assert NEEDS not in gg.binding_for(body).loop.registry.state(goal_id).missing_capabilities


class _FakeGenesis:
    def __init__(self):
        self.calls = []

    @staticmethod
    def formable(function):
        return function in ("selection.closure", "graph.max_flow", "human.outreach")   # formable, but a person's

    def form_for_goal(self, **kw):
        self.calls.append((kw["goal_id"], kw["function"], kw["mission"].mission_id))
        return None


def _fake(*, missing, missions, stopped=False, revoked=(), admitted=True):
    spec = SimpleNamespace(authority={"missions": list(missions)})
    state = SimpleNamespace(missing_capabilities=list(missing), active_node_id="decide",
                            preferences={"revoked_capabilities": list(revoked)})
    reg = SimpleNamespace(state=lambda gid: state, get=lambda gid: spec)
    facts = SimpleNamespace(admitted={"g1": "d"} if admitted else {},
                            stopped=lambda gid: {"kind": "stop_pushing"} if stopped else None)
    genesis = _FakeGenesis()
    body = SimpleNamespace(genesis=genesis, engine=SimpleNamespace(book=SimpleNamespace(missions=missions)))
    return body, reg, facts, genesis


def test_only_an_admitted_unstopped_goal_asks_and_only_for_formable_machine_work_under_an_open_mission():
    m = lambda mid, status="ACTIVE", paused=False: SimpleNamespace(mission_id=mid, status=status,  # noqa: E731
                                                                   paused=paused)
    open_ = {"m:a": m("m:a", paused=True), "m:b": m("m:b"), "m:c": m("m:c", "ACHIEVED")}
    asks = ["selection.closure@function", "lp.optimize@1.0", "unknown.thing@function",
            "human.outreach@function"]
    body, reg, facts, genesis = _fake(missing=asks, missions=open_)
    out = gg._form_requested(body, reg, facts, ["g1"], at=None)
    assert genesis.calls == [("g1", "selection.closure", "m:b")]       # the paused and achieved missions skipped
    assert out == [{"goal_id": "g1", "function": "selection.closure", "mission_id": "m:b", "serving": None}]
    for kw in ({"stopped": True}, {"admitted": False}, {"revoked": ["selection.closure@function"]}):
        body, reg, facts, genesis = _fake(missing=asks, missions=open_, **kw)
        assert gg._form_requested(body, reg, facts, ["g1"], at=None) == [] and genesis.calls == []
    body, reg, facts, genesis = _fake(missing=asks, missions={"m:c": m("m:c", "ACHIEVED")})
    assert gg._form_requested(body, reg, facts, ["g1"], at=None) == []   # no open mission to form under
    body, reg, facts, genesis = _fake(missing=asks, missions=open_)
    assert gg._form_requested(body, reg, facts, [], at=None) == []       # a goal that did not wake asks nothing


def test_a_function_requirement_reads_present_only_when_an_implementation_is_usable():
    manifest = SimpleNamespace(capability_id="composed.selection.closure.x", version="1.0")
    usable = {"composed.selection.closure.x": False}
    registry = SimpleNamespace(by_function=lambda f: [manifest] if f == "selection.closure" else [],
                               usable=lambda cid: (usable[cid], ""), manifests={})
    genomes = gg._Genomes(registry)
    assert genomes.get("selection.closure", gg.FUNCTION_VERSION) is None
    usable["composed.selection.closure.x"] = True
    assert genomes.get("selection.closure", gg.FUNCTION_VERSION) is manifest
    assert genomes.get("graph.max_flow", gg.FUNCTION_VERSION) is None


def test_a_goals_formation_request_never_commissions_a_builder_or_spends_a_build_budget(tmp_path):
    from datetime import datetime, timezone
    home, _, _, _ = make_body(tmp_path)
    used = []

    class Builder:                       # attached, with budget: what a mission's own deficit could commission
        max_budget_usd = 5.0

        def __getattr__(self, name):
            used.append(name)
            raise AttributeError(name)

    contract = {"function": "text.title_case", "description": "title-case a string", "returns": "a string",
                "examples": [{"input": "a b", "output": "A B"}], "held_out": [{"input": "x y", "output": "X Y"}],
                "build_budget_usd": 5.0}
    m = SimpleNamespace(mission_id="m:contract", spec={"capability_specs": [contract]})
    with Body(home, clock=Clock()) as body:
        body.boot()
        body.genesis.builder = Builder()
        found = body.genesis.form_for_goal(goal_id="sha256:" + "0" * 64, mission=m, function="text.title_case",
                                           purpose="a goal requires it", now=datetime.now(timezone.utc))
        assert found is None and used == []
        routes = [e.payload for e in body.journal.replay("genesis.route")]
        assert [r["result"] for r in routes if r["route"] == "builder"] == [
            "goal sha256:0000000000000000 asked for formation: a goal never commissions a builder or spends a "
            "build budget"]
        assert body.journal.replay("genesis.built") == []
        assert body.genesis._form_only is None                     # restored for the mission's own deficits
