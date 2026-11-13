"""A mission whose only route waits on a precondition the world must satisfy resumes when the world satisfies it.

Before: every remaining strategy was held by a failing ``requires`` check that no strategy advances, so the engine
raised one NO_STRATEGY ask and blocked. Its watcher then waited for every failing check to pass on its own, but the
checks the held strategy advances can pass only after it runs: the mission stayed blocked for good, even after the
precondition was observed passing (found by tests/integration/test_one_mission_fifteen_steps.py). Now the ask is
withdrawn as moot once observation says the precondition passes, and the held strategy runs. Timing, scope and
authority are unchanged: the precondition is still only observed, never acted on.

The second half locks the other direction (founder's minimum test for proof-bearing plans, 2026-11-11: "change a
decisive prerequisite between planning and dispatch; the stale action is withheld and unrelated valid work continues.
Preserve exactly-once claims only where the underlying protocol supports them."). A precondition that passed when the
action was planned, and stops passing before the founder's approval arrives, holds the approved action. The behaviour
existed on #196 and no test asserted it; these tests add no product code. Reality tier: an in-process Body in a cloud
container, a test clock, a per-test founder key, no founder device.

Not locked here: a change inside one pass. The hold reads the pass's own observation of the precondition. A change
after that reading and before the same pass dispatches is not seen; nothing re-reads a mission precondition at the
Gate's commit. Measured on 8d205324 with a scratch probe: the action ran, and the appraiser called it honoured.
"""
import pytest

from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

MID = "m:gated"
CADENCE = 3600


def spec(home, data):
    ws = workspace(home, MID)
    return mission(MID, checks=[note_check("gate", data / "request.txt", "go"), note_check("out", ws / "out.txt", "done")],
                   strategies=[write_strategy("work", "out.txt", "done", ["out"], requires=["gate"])],
                   capabilities=["fs.read", "fs.write"], closure={"kind": "bounded", "cadence_seconds": CADENCE})


def run(tmp_path, *, request: str | None):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", spec(home, data)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            body.tick()
            clock.advance(31)
        assert [e.payload["kind"] for e in body.journal.replay("decision.requested")] == ["NO_STRATEGY"]
        if request is not None:
            (data / "request.txt").write_text(request)
        clock.advance(CADENCE + 1)                       # the mission's own cadence: no goal, no pull
        states = []
        for _ in range(4):
            states.append(body.tick()["missions"][0]["state"])
            clock.advance(31)
        events = {k: [e.payload for e in body.journal.replay(k)]
                  for k in ("decision.requested", "decision.withdrawn", "mission.action", "mission.achieved")}
    return states, events


def test_the_held_strategy_runs_once_its_precondition_is_observed_passing(tmp_path):
    states, events = run(tmp_path, request="go")
    assert events["mission.achieved"], states
    [withdrawn] = events["decision.withdrawn"]
    assert "the precondition that held work now passes" in withdrawn["why"]
    assert [(a["action_id"], a["status"]) for a in events["mission.action"]] == [("work", "DONE")]
    assert [r["kind"] for r in events["decision.requested"]] == ["NO_STRATEGY"]       # nothing new was asked


def test_a_precondition_still_failing_keeps_the_mission_waiting_without_a_second_ask(tmp_path):
    states, events = run(tmp_path, request="not yet")
    assert not events["mission.achieved"] and not events["mission.action"] and not events["decision.withdrawn"]
    assert [r["kind"] for r in events["decision.requested"]] == ["NO_STRATEGY"]
    assert set(states) <= {"WAITING", "BLOCKED"}, states


# -- a precondition that passed at planning and stops passing before dispatch ----------------------------------------
STALE = "m:stale-plan"
TICK = 61                                        # one second past the mission's cadence: every tick re-observes


def _record(body, home, calls, states):
    """What the body's own records say now. Gate records are read per action through the proposal each write-ahead
    intent names, so a second dispatch of the same action at another attempt would be counted too."""
    journal, ledger, ws = body.journal, body.ledger, workspace(home, STALE)
    replay = lambda kind: [e.payload for e in journal.replay(kind)]                  # noqa: E731
    intents = replay("mission.dispatching")
    issued = [r.payload for r in ledger.by_type("event") if r.payload.get("type") == "greg.authority.grant_issued"]
    gate = {}
    for action in ("work", "late"):
        proposals = [i["proposal_id"] for i in intents if i["action_id"] == action]
        claims = [c.payload for p in proposals for c in ledger.select("grant_dispatch", proposal_id=p)]
        gate[action] = {"scopes": {i["scope_digest"] for i in intents if i["action_id"] == action},
                        "claims": claims,
                        "grants": [g for g in issued if g["proposal_id"] in proposals],
                        "receipts": [r.payload for c in claims
                                     for r in ledger.select("receipt", grant_id=c["grant_id"])]}
    return {"states": list(states), "asks": replay("decision.requested"), "answers": replay("decision.answered"),
            "withdrawn": replay("decision.withdrawn"), "actions": replay("mission.action"),
            "achieved": replay("mission.achieved"), "appraised": replay("mission.appraised"),
            "observed": replay("mission.observed"), "gate": gate, "writes": list(calls),
            "approved_scopes": set(body.engine.book.missions[STALE].approved_scopes),
            "files": {name: (ws / name).read_text() if (ws / name).exists() else None
                      for name in ("out.txt", "late.txt")}}


@pytest.fixture(scope="module")
def stale(tmp_path_factory):
    """One run of the founder's minimum test, recorded after each of its four moments.

    ``work`` writes out.txt, requires the signed check ``gate`` (request.txt says go) and lies outside the signed
    cone, so it needs the founder's approval. ``late`` is unrelated work with its own precondition, inside the cone.

    1. planned:  gate passes; GREG selects ``work`` and asks for its approval. Nothing runs.
    2. held:     request.txt changes to "halt" (and late.txt to "go"), then the founder approves ``work``.
    3. returned: request.txt says "go" again. Nobody answers anything.
    4. again:    more ticks after the mission closed.

    The fixture asserts nothing, and raises nothing under the two mutants scripts/ci/check_whole_output_mutants.py
    aims at this file: each test below fails on its own clause."""
    home, key, body_id, data = make_body(tmp_path_factory.mktemp("stale"))
    ws = workspace(home, STALE)
    (data / "request.txt").write_text("go")
    (data / "late.txt").write_text("not yet")
    drop(home, signed(key, body_id, "MISSION", mission(
        STALE,
        checks=[note_check("gate", data / "request.txt", "go"), note_check("out", ws / "out.txt", "done"),
                note_check("late-gate", data / "late.txt", "go"), note_check("late", ws / "late.txt", "ok")],
        strategies=[write_strategy("work", "out.txt", "done", ["out"], requires=["gate"]),
                    write_strategy("late", "late.txt", "ok", ["late"], requires=["late-gate"])],
        capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:late.txt"),   # out.txt is outside the cone
        closure={"kind": "bounded", "cadence_seconds": 60})))
    clock, story = Clock(), {}
    with Body(home, clock=clock) as body:
        real, calls = body.registry.adapters["fs.write"], []

        def counted(params, ctx):                # the registered adapter itself, counted: every real write passes here
            calls.append(params["relative_path"])
            return real(params, ctx)
        body.registry.adapters["fs.write"] = counted

        def ticks(n):
            states = []
            for _ in range(n):
                states.append(body.tick()["missions"][0]["state"])
                clock.advance(TICK)
            return states

        body.boot()
        story["planned"] = _record(body, home, calls, ticks(3))
        approval = next((a for a in story["planned"]["asks"] if a["kind"] == "APPROVAL"), None)
        # The decisive prerequisite changes after the plan and before the approval that would dispatch it.
        (data / "request.txt").write_text("halt")
        (data / "late.txt").write_text("go")
        if approval is not None:
            drop(home, signed(key, body_id, "DECISION", {"request_id": approval["request_id"], "answer": "approve",
                                                         "reason": "approved as planned"}))
        story["held"] = _record(body, home, calls, ticks(5))
        (data / "request.txt").write_text("go")                      # the world, not GREG, restores the prerequisite
        story["returned"] = _record(body, home, calls, ticks(4))
        story["again"] = _record(body, home, calls, ticks(3))
    return story


def _ran(record, action):
    return [(a["status"], a["attempt"]) for a in record["actions"] if a["action_id"] == action]


def _gate_seen(record):
    return [o["passed"] for o in record["observed"] if o["check_id"] == "gate"]


def test_the_action_was_planned_on_a_precondition_measured_passing_and_nothing_ran(stale):
    planned = stale["planned"]
    assert _gate_seen(planned) and all(_gate_seen(planned))          # measured, with a receipt, and passing
    assert all(o["receipt"] for o in planned["observed"] if o["check_id"] == "gate")
    [ask] = planned["asks"]                                          # the plan: this exact action, awaiting approval
    assert (ask["kind"], ask["action_id"]) == ("APPROVAL", "work")
    assert {ask["scope_digest"]} == planned["gate"]["work"]["scopes"]
    assert planned["actions"] == [] and planned["writes"] == []
    assert planned["gate"]["work"] == {"scopes": {ask["scope_digest"]}, "claims": [], "grants": [], "receipts": []}


def test_an_approved_action_whose_precondition_stopped_passing_is_never_dispatched(stale):
    planned, held = stale["planned"], stale["held"]
    # Withheld before the Gate: no action record, no dispatch claim, no grant, no receipt, no adapter call, no file.
    assert _ran(held, "work") == []
    assert held["gate"]["work"]["claims"] == [] and held["gate"]["work"]["grants"] == []
    assert held["gate"]["work"]["receipts"] == []
    assert "out.txt" not in held["writes"] and held["files"]["out.txt"] is None
    assert held["achieved"] == []
    # The approval arrived and still stands unused: the precondition, not a missing approval, withholds the action.
    [approval] = planned["asks"]
    assert [(a["request_id"], a["answer"]) for a in held["answers"]] == [(approval["request_id"], "approve")]
    assert approval["scope_digest"] in held["approved_scopes"]
    assert _gate_seen(held)[len(_gate_seen(planned)):] == [False] * 5        # every pass since measured it failing


def test_unrelated_valid_work_in_the_same_mission_runs_while_the_stale_action_is_withheld(stale):
    held = stale["held"]
    assert _ran(held, "late") == [("DONE", 0)] and held["files"]["late.txt"] == "ok"
    assert held["writes"] == ["late.txt"]                            # the one write of this phase, and not out.txt
    assert len(held["gate"]["late"]["claims"]) == len(held["gate"]["late"]["receipts"]) == 1
    assert held["states"][0] == "ACTED"                              # in the first pass after the change


def test_the_ask_raised_meanwhile_names_the_precondition_that_holds_the_action(stale):
    held = stale["held"]
    assert [a["kind"] for a in held["asks"]] == ["APPROVAL", "NO_STRATEGY"]          # no second approval is asked
    blocked = held["asks"][1]
    assert blocked["evidence"].get("held_by_precondition") == {"work": ["gate"]}
    assert "gate" in blocked["why_now"]
    assert blocked["evidence"]["failed"] == {} and blocked["evidence"]["excluded"] == {}    # nothing was tried and lost
    assert held["withdrawn"] == [] and set(held["states"][1:]) <= {"BLOCKED", "WAITING"}, held["states"]


def test_the_standing_approval_admits_the_action_without_a_new_ask_once_the_precondition_returns(stale):
    held, returned = stale["held"], stale["returned"]
    assert returned["asks"] == held["asks"]                          # nothing new was asked
    assert returned["answers"] == held["answers"]                    # and the founder answered nothing more
    assert _ran(held, "work") == [] and _ran(returned, "work") == [("DONE", 0)]      # it ran only now
    assert returned["files"]["out.txt"] == "done"
    assert [(w["request_id"], "the precondition that held work now passes" in w["why"])
            for w in returned["withdrawn"]] == [(held["asks"][1]["request_id"], True)]   # GREG withdrew its own ask
    assert [(g["founder_approved_scope"], g["scope_digest"]) for g in returned["gate"]["work"]["grants"]] == \
        [(True, held["asks"][0]["scope_digest"])]                    # admitted by the approval given at planning
    assert returned["achieved"] and "ACHIEVED" in returned["states"], returned["states"]


def test_the_withheld_action_then_ran_exactly_once(stale):
    """Exactly once is claimed only for what this protocol supports: a write to the body's own workspace through
    the body's own Gate. One proposal per (scope, attempt), one dispatch claim, one receipt, and the registered
    adapter counted in this process. Nothing here speaks for an effect on another system."""
    for moment in ("returned", "again"):                             # and later passes do not run it again
        record = stale[moment]
        assert record["writes"] == ["late.txt", "out.txt"], moment
        assert _ran(record, "work") == [("DONE", 0)] and _ran(record, "late") == [("DONE", 0)], moment
        for action in ("work", "late"):
            gate = record["gate"][action]
            assert len(gate["scopes"]) == len(gate["claims"]) == len(gate["grants"]) == len(gate["receipts"]) == 1
            assert gate["receipts"][0]["result"]["result_class"] == "positive"
    assert stale["again"]["asks"] == stale["returned"]["asks"]


def test_the_separate_appraiser_rederives_that_the_precondition_and_the_approval_were_honoured(stale):
    assert [a["verdict"] for a in stale["again"]["appraised"]] == ["VERIFIED"]
    appraisal = stale["again"]["appraised"][0]
    assert appraisal["findings"] == []
    for check in ("preconditions_honored", "approval_boundaries_honored", "approval_boundary_encountered",
                  "exactly_once"):
        assert appraisal["checks"][check] is True, check
