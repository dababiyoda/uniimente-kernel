"""A Competency Compiler receipt that did not answer is no reading of a failure, and a host stop is retried.

``greg.missions.unanswered`` tells the engine and the separate appraiser that a cognitive receipt abstained. It read
only ``abstention_state``, which a cortex receipt carries. A compile receipt carries ``state`` and ``result``
instead, so every compile receipt looked answered: a signed question whose solver worker the host stopped was
recorded as a measured failure. A question with no strategy asked the founder for one at the first stall and then
waited a whole cadence; a question with a strategy had it dispatched, blamed and closed as a failure.

What these tests pin:

- the one reader gives a compile receipt the answer it gives a cortex receipt, by the receipt's typed fields;
- the compile receipt says in a typed field (``host_stop``) when the host, not the Mind, ended the decision: a worker
  that timed out or exited abnormally, or an exhausted compute budget;
- the engine re-observes such a reading with a back-off and asks once after three unmeasured rounds, as it does for a
  construction the host stopped; an abstention that is not a host stop keeps the treatment of an abstaining cortex
  receipt (pursued, never certified as failed);
- a real negative (a refuted receipt, an answer whose predicate is false) stays a measured failure;
- the separate appraiser certifies no failure on a compile receipt that did not answer.

Each mission test runs a real Body through the real office and Gate. The host stop is injected where the solver
worker process is launched (``greg.capabilities.run_isolated``): nothing downstream of the launch is replaced.
In-process Body, a test clock and a per-test founder key, not Alfonso's (SANDBOX).
"""
from __future__ import annotations

import subprocess
from datetime import datetime
from types import SimpleNamespace

import pytest

import greg.capabilities as caps
from greg.body import Body
from greg.cognition import bridge, budget, compiler, settlement
from greg.cognition.contracts import CognitionError, digest
from greg.cognition.cortex import reason, registry_view
from greg.missions import COMPILATION, MissionEngine, unanswered
from greg.templates import compiled_question
from tests.greg_fixtures import Clock, make_body, mission, note_check, signed, write_strategy

METHOD = "cognition.swarm"
SPHERE = {"function": "sphere", "bounds": [[-5.12, 5.12]] * 3, "budget": 300, "shift": [0.5, -0.25, 1.0], "seed": 3}
STEP = 31.0                    # seconds between ticks
CADENCE = 3600                 # the default cadence of a bounded mission


def compile_params(problem="real:q", **compile_extra):
    return {"problem_id": problem, "compile": {"geometry": {"geometry": "optimization"}, "data": dict(SPHERE),
                                               **compile_extra}}


def fitness_check(check_id="good", *, value=1e6, **compile_extra):
    return {"check_id": check_id, "description": "fitness bound",
            "sensor": {"capability": "cognition.solve", "target": "cognition:bb",
                       "params": compile_params(**compile_extra)},
            "predicate": {"op": "lte", "field": "result.fitness", "value": value}}


def question(mid, *checks, strategies=(), capabilities=("cognition.solve",), targets=("cognition:*",),
             ceiling="read_only"):
    return mission(mid, checks=list(checks), strategies=list(strategies), capabilities=list(capabilities),
                   targets=targets, ceiling=ceiling)


class Host:
    """The place a solver or verifier worker process is launched. ``stall`` makes the host stop every such worker:
    ``timeout`` (it does not finish inside its limit) or ``crash`` (it exits 137, as a killed process reports)."""

    def __init__(self, monkeypatch):
        self.real, self.mode, self.only, self.after, self.calls = caps.run_isolated, None, None, 0, 0
        monkeypatch.setattr(caps, "run_isolated", self.launch)

    def stall(self, mode, *, only=None, after=0):
        self.mode, self.only, self.after, self.calls = mode, only, after, 0

    def recover(self):
        self.mode = None

    def launch(self, argv, *args, **kwargs):
        worker = any("worker.py" in str(a) for a in argv)
        if worker and self.mode and (self.only is None or self.only in argv):
            self.calls += 1
            if self.calls > self.after:
                if self.mode == "timeout":
                    raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 5))
                return subprocess.CompletedProcess(argv, 137, b"", b"killed")
        return self.real(argv, *args, **kwargs)


@pytest.fixture
def host(monkeypatch):
    return Host(monkeypatch)


class Run:
    """One real Body with the swarm method attached by a signed founder command."""

    def __init__(self, tmp_path, *, attach=(METHOD,)):
        self.home, self.key, self.body_id, self.data = make_body(tmp_path)
        self.clock = Clock()
        self.start = self.clock()
        self.body = Body(self.home, clock=self.clock).open()
        self.body.boot()
        for cid in attach:
            self.sign("CAPABILITY_ATTACH", {"capability_id": cid})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.body.close()

    def sign(self, kind, payload):
        return self.body.apply(signed(self.key, self.body_id, kind, payload))

    def tick(self, mid):
        """One tick, then the clock moves on; returns this mission's state."""
        row = next((r for r in self.body.tick()["missions"] if r.get("mission_id", mid) == mid), None)
        self.clock.advance(STEP)
        return row["state"] if row else None

    def events(self, kind, mid=None):
        return [e.payload for e in self.body.journal.replay(kind)
                if mid is None or e.payload.get("mission_id") == mid]

    def offset(self, at=None):
        when = self.clock() if at is None else datetime.fromisoformat(at.replace("Z", "+00:00"))
        return (when - self.start).total_seconds()

    def output(self, observation):
        return self.body.journal.ledger.find(observation["receipt"]).payload["result"]["output"]

    def mission(self, mid):
        return self.body.engine.book.missions[mid]


# -- the one reader ---------------------------------------------------------------------------------------------------

def compiled(state, result=None, **extra):
    return {"schema": compiler.SCHEMA, "state": state, "result": result, **extra}


def test_the_reader_knows_the_schema_the_compiler_writes():
    assert compiler.SCHEMA.startswith(COMPILATION) and compiler.SCHEMA in settlement.COMPILE_SCHEMAS
    assert "greg-competency-compilation/0.2" in settlement.COMPILE_SCHEMAS       # retained receipts still settle


def test_a_compile_receipt_is_read_by_its_own_typed_fields():
    # an answer, a conditional answer, the founder's recorded decision: measurements
    assert unanswered(compiled("ANSWERED", {"fitness": 0.1})) is None
    assert unanswered(compiled("WORLD_UNVERIFIED", {"fitness": 0.1})) is None
    assert unanswered(compiled("HUMAN_JUDGMENT_RECORDED", {"decision": {"verdict": "reject"}})) is None
    # a refutation is a real negative result; a plan is the whole of what ``execute: false`` asked for
    assert unanswered(compiled("REFUTED")) is None
    assert unanswered(compiled("PLANNED")) is None
    # everything else answered nothing, and the reason is the receipt's own state
    for state in ("ABSTAIN", "UNKNOWN", "CAPABILITY_DEFICIT", "PROHIBITED", "HUMAN_JUDGMENT_REQUIRED",
                  "FORMALIZATION_INCOMPLETE", "EVIDENCE_EXPIRED", "UNIDENTIFIED", "STAGE_ABSTAINED",
                  "TRANSLATION_FAILED", "NO_RECIPE", "TIMEOUT", "HUMAN_REVIEW_REQUIRED"):
        assert unanswered(compiled(state)) == state, state
    # the judgment packet of a question still waiting for the founder is a result, and no answer
    assert unanswered(compiled("HUMAN_JUDGMENT_REQUIRED", {"awaiting": "the founder"})) == "HUMAN_JUDGMENT_REQUIRED"
    # a state that answers, without the answer, did not answer (WORLD_UNVERIFIED is also an abstention's state)
    assert unanswered(compiled("WORLD_UNVERIFIED")) == "WORLD_UNVERIFIED"
    assert unanswered(compiled("ANSWERED")) == "ANSWERED"
    # a receipt an older compiler wrote is read the same way
    assert unanswered({"schema": "greg-competency-compilation/0.2", "state": "UNKNOWN", "result": None}) == "UNKNOWN"
    assert unanswered({"schema": "greg-competency-compilation/0.2", "state": "ANSWERED", "result": {"x": 1}}) is None
    # a cortex receipt and any other output are read as before
    assert unanswered({"abstention_state": "UNKNOWN", "reason_code": "TIMEOUT", "output": None}) == "TIMEOUT"
    assert unanswered({"abstention_state": "REFUTED", "output": None}) is None
    assert unanswered({"state": "UNKNOWN", "result": None}) is None and unanswered({"schema": 7, "state": "X"}) is None


# -- the compile receipt's typed host stop ----------------------------------------------------------------------------

@pytest.fixture
def registry():
    view = registry_view()
    view.set_state(METHOD, "ATTACHED")
    return view


def test_a_worker_the_host_stopped_is_named_in_a_typed_field(registry, host):
    answered = reason(compile_params(), registry=registry)
    assert answered["state"] == "ANSWERED" and answered["host_stop"] is None and unanswered(answered) is None
    host.stall("timeout")
    timed_out = reason(compile_params(), registry=registry)
    assert timed_out["state"] == "UNKNOWN" and timed_out["result"] is None
    assert timed_out["host_stop"] == {"failure_class": "transient", "cause": "timeout", "process": "solver"}
    host.stall("crash")
    crashed = reason(compile_params(), registry=registry)
    assert crashed["state"] == "ABSTAIN"
    assert crashed["host_stop"] == {"failure_class": "transient", "cause": "worker_exit", "process": "solver",
                                    "returncode": 137}
    # nothing typed named the abnormal exit before: the executed method's own receipt reports it like bad input
    assert crashed["selected_receipt"]["reason_code"] == "INSUFFICIENT_EVIDENCE"
    host.stall("crash", only="verify")
    unverified = reason(compile_params(), registry=registry)
    assert unverified["result"] is None
    assert unverified["host_stop"] == {"failure_class": "transient", "cause": "worker_exit", "process": "verifier",
                                       "returncode": 137}
    host.stall("timeout", only="verify")
    assert reason(compile_params(), registry=registry)["host_stop"] == {
        "failure_class": "transient", "cause": "timeout", "process": "verifier"}


def test_an_exhausted_budget_is_a_host_stop_and_the_mind_declining_is_not(registry):
    # a required step the thinking budget refused: nothing ran, and nothing was decided about the question
    broke = reason(compile_params(geometry={"geometry": "optimization", "latency_budget": 0.01}), registry=registry)
    assert broke["state"] == "ABSTAIN" and broke["result"] is None
    assert broke["host_stop"] == {"failure_class": "budget_exceeded", "cause": "budget", "step": "answer"}
    # the Mind declines: no retry changes these, so they name no host stop
    prohibited = reason(compile_params(consequence={"lawful": False}), registry=registry)
    assert prohibited["state"] == "PROHIBITED" and prohibited["host_stop"] is None
    lacking = reason({"problem_id": "p", "compile": {"geometry": {"geometry": "optimization"},
                                                     "data": {"function": "sphere"}}}, registry=registry)
    assert lacking["state"] in ("ABSTAIN", "CAPABILITY_DEFICIT") and lacking["host_stop"] is None
    planned = reason(compile_params(execute=False), registry=registry)
    assert planned["state"] == "PLANNED" and planned["host_stop"] is None and unanswered(planned) is None


def test_an_answer_names_no_host_stop_even_when_a_later_step_was_stopped(registry, host):
    """The sensitivity re-runs are optional steps after the answer. The host stopping them leaves the answer
    standing, so the receipt names no host stop."""
    host.stall("timeout", after=2)                  # the answer's solver and verifier run; every later worker stops
    geometry = {"geometry": "optimization", "consequence_class": "financial",
                "deterministic_or_stochastic": "stochastic"}
    receipt = reason(compile_params(geometry=geometry), registry=registry)
    assert receipt["state"] == "WORLD_UNVERIFIED" and isinstance(receipt["result"], dict)
    assert host.calls > 2 and receipt["sensitivity"]["inputs"]         # later workers were launched, and stopped
    assert receipt["host_stop"] is None and unanswered(receipt) is None


def test_a_host_stop_is_read_from_typed_facts_in_order():
    spent = budget.Controller(1.0)
    stub = lambda *stops: SimpleNamespace(stops=lambda: list(stops))  # noqa: E731
    receipt = lambda state="UNKNOWN", code=None: {"state": state, "selected_receipt":  # noqa: E731
                                                  {"reason_code": code} if code else None}
    stop = compiler._host_stop
    # a deadline or a ceiling the executed method's own receipt names, with no process killed
    assert stop(receipt(code="TIMEOUT"), [], spent) == {"failure_class": "transient", "cause": "timeout"}
    assert stop(receipt(code="BUDGET_EXHAUSTED"), [], spent) == {"failure_class": "budget_exceeded",
                                                                  "cause": "budget"}
    # the same two named among the receipt's outcome reasons: an engine that ran out of its signed budget inside
    # the cortex worker, which returns normally and carries no reason code (measured on the problem route)
    def reasons(*named):
        return {"state": "UNKNOWN", "selected_receipt": {"outcome": {"reasons": list(named)}}}

    assert stop(reasons("TIMEOUT", "SOLVER_UNKNOWN"), [], spent) == {"failure_class": "transient", "cause": "timeout"}
    assert stop(reasons("BUDGET_EXHAUSTED"), [], spent) == {"failure_class": "budget_exceeded", "cause": "budget"}
    assert stop(reasons("SOLVER_UNKNOWN"), [], spent) is None and stop(reasons(), [], spent) is None
    # a chain that overran its limit
    assert stop(receipt("TIMEOUT"), [], spent) == {"failure_class": "transient", "cause": "timeout"}
    # the method's own reasons for having no answer are the Mind's, not the host's
    for code in ("INSUFFICIENT_EVIDENCE", "SOLVER_UNKNOWN", "POLICY_REFUSAL", "CAPABILITY_UNAVAILABLE",
                 "MODEL_INVALID", "HUMAN_JUDGMENT_REQUIRED"):
        assert stop(receipt(code=code), [], spent) is None, code
    assert stop(receipt("STAGE_ABSTAINED"), [], spent) is None
    # a worker the launcher saw stop comes first: it says which process and how
    noted = [{"cause": "worker_exit", "process": "solver", "returncode": -9},
             {"cause": "timeout", "process": "verifier"}]
    assert stop(receipt(code="TIMEOUT"), noted, spent) == {"failure_class": "transient", "cause": "worker_exit",
                                                            "process": "solver", "returncode": -9}
    # only a required step the budget refused counts: an optional step is skipped after an answer, never instead of one
    optional = {"step": "sensitivity:x", "required": False, "decision": "STOP", "reason": "STOP: ..."}
    required = {"step": "answer", "required": True, "decision": "STOP", "reason": "BUDGET_EXHAUSTED: ..."}
    assert stop(receipt("ABSTAIN"), [], stub(optional)) is None
    assert stop(receipt("ABSTAIN"), [], stub(optional, required)) == {"failure_class": "budget_exceeded",
                                                                      "cause": "budget", "step": "answer"}


def test_the_launchers_note_only_inside_a_compiled_decision(host):
    """A note is a fact about one compiled decision. Outside one nobody collects it; a nested collector keeps its
    own; an unknown cause is refused where it is written."""
    budget.note_host_stop("timeout", process="solver")                     # no collector: dropped, no error
    with budget.host_stops() as outer:
        with budget.host_stops() as inner:
            budget.note_host_stop("worker_exit", process="solver", returncode=1)
        budget.note_host_stop("timeout", process="verifier")
    assert inner == [{"cause": "worker_exit", "process": "solver", "returncode": 1}]
    assert outer == [{"cause": "timeout", "process": "verifier"}]
    with pytest.raises(CognitionError):
        budget.note_host_stop("the solver said no", process="solver")
    # the cortex-contract worker (the problem route) notes the same two facts
    problem = {"question": "q", "payload": {}}
    for mode, note in (("crash", {"cause": "worker_exit", "process": "cortex", "returncode": 137}),
                       ("timeout", {"cause": "timeout", "process": "cortex"})):
        host.stall(mode)
        with budget.host_stops() as noted:
            with pytest.raises((CognitionError, subprocess.TimeoutExpired)):
                bridge.run_worker(problem, [], withheld_organs={}, semantic_model=None, cpu_seconds=1,
                                  created_at="2026-11-12T00:00:00Z")
        assert noted == [note]


# -- the engine: a host stop is retried, not asked about at once ------------------------------------------------------

@pytest.mark.parametrize("mode", ["timeout", "crash"])
def test_a_question_the_host_stopped_is_read_again_within_the_back_off_and_nobody_is_asked(tmp_path, host, mode):
    with Run(tmp_path) as run:
        host.stall(mode)
        run.sign("MISSION", question("m:quest", fitness_check()))
        assert run.tick("m:quest") == "SENSOR_RETRY"            # before: BLOCKED on a NO_STRATEGY question
        assert run.events("decision.requested") == []
        assert run.tick("m:quest") == "SENSOR_RETRY"            # the second unmeasured round, 31 s later
        host.recover()
        recovered = run.offset()
        states = [run.tick("m:quest") for _ in range(4)]
        assert "ACHIEVED" in states, states
        stopped, read = run.events("mission.observed", "m:quest")[:2], run.events("mission.observed", "m:quest")[2]
        for observation in stopped:
            assert observation["passed"] is False and observation["failure_class"] == "transient"
            assert "declined" not in observation
            assert observation["detail"].startswith("sensor inconclusive (transient): ")
            assert run.output(observation)["host_stop"]["cause"] == {"timeout": "timeout", "crash": "worker_exit"}[mode]
        assert read["passed"] is True
        # read again inside the back-off (60 s after the second round), not a whole cadence later
        assert 0 <= run.offset(read["at"]) - recovered <= 60 < CADENCE
        assert run.events("decision.requested") == [] and run.events("decision.withdrawn") == []
        assert run.mission("m:quest").status == "ACHIEVED"


def test_a_host_that_never_recovers_is_asked_about_once_after_three_unmeasured_rounds(tmp_path, host):
    with Run(tmp_path) as run:
        host.stall("timeout")
        run.sign("MISSION", question("m:quest", fitness_check()))
        states = []
        while "BLOCKED" not in states and len(states) < 8:
            states.append(run.tick("m:quest"))
        # rounds at 0 s and 31 s, the 60 s back-off, then the third round, which asks
        assert states == ["SENSOR_RETRY", "SENSOR_RETRY", "WAITING", "BLOCKED"], states
        assert [a["kind"] for a in run.events("decision.requested")] == ["SENSOR_FAILURE"]   # before: NO_STRATEGY
        unmeasured = run.events("mission.observed", "m:quest")
        assert len(unmeasured) == 3 and all(o["failure_class"] == "transient" for o in unmeasured)
        assert run.mission("m:quest").blocker["sensing"] is True
        assert [run.tick("m:quest") for _ in range(4)] == ["WAITING"] * 4
        # it waits, re-reading at the cadence; nothing more is asked and nothing is withdrawn while the host is down
        run.clock.advance(CADENCE)
        assert run.tick("m:quest") == "WAITING"
        assert [a["kind"] for a in run.events("decision.requested")] == ["SENSOR_FAILURE"]
        assert run.events("decision.withdrawn") == []
        assert run.events("mission.unmet") == [] and run.events("routing.outcome") == []
        # once the sensor reads again the question is moot: withdrawn by the body, and the mission closes
        host.recover()
        run.clock.advance(CADENCE)
        later = [run.tick("m:quest") for _ in range(3)]
        assert "ACHIEVED" in later, later
        assert len(run.events("decision.withdrawn")) == 1


def test_an_exhausted_budget_is_retried_and_typed_as_a_resource_ceiling(tmp_path):
    """The signed question declares a thinking budget below the smallest step that can solve and verify, so the
    required answer step is refused and nothing runs. That says nothing about the question: the reading is
    unmeasured, typed ``budget_exceeded``, and takes the retry path; three such rounds ask the founder once."""
    tight = fitness_check(geometry={"geometry": "optimization", "latency_budget": 0.01})
    with Run(tmp_path) as run:
        run.sign("MISSION", question("m:tight", tight))
        states = [run.tick("m:tight") for _ in range(4)]
        assert states == ["SENSOR_RETRY", "SENSOR_RETRY", "WAITING", "BLOCKED"], states       # before: BLOCKED at once
        observed = run.events("mission.observed", "m:tight")
        assert [o["failure_class"] for o in observed] == ["budget_exceeded"] * 3
        assert all(o["detail"].startswith("sensor inconclusive (budget_exceeded): ") for o in observed)
        assert run.output(observed[0])["host_stop"] == {"failure_class": "budget_exceeded", "cause": "budget",
                                                        "step": "answer"}
        assert [a["kind"] for a in run.events("decision.requested")] == ["SENSOR_FAILURE"]


def test_an_engine_out_of_its_signed_budget_inside_the_cortex_worker_is_retried_too(tmp_path):
    """The problem route's form of a stalled host: nothing kills the cortex worker. The formal engine runs out of
    the latency the signed question allows (11 pigeons, 10 holes, 0.3 s), the worker returns normally, and the
    executed method's receipt names TIMEOUT among its outcome reasons and carries no reason code. Needs Z3
    (requirements-cortex.txt); without it this test is skipped, and the unit test of the typed facts stands alone."""
    pytest.importorskip("z3")
    import itertools
    holes = 10
    model = {"requirement": "every pigeon in a distinct hole",
             "variables": [{"name": f"p{k}", "sort": "int", "lo": 1, "hi": holes} for k in range(holes + 1)],
             "obligations": [{"id": "R", "text": "distinct"}],
             "constraints": [{"id": f"C{a}_{b}", "covers": ["R"], "expr": ["!=", f"p{a}", f"p{b}"]}
                             for a, b in itertools.combinations(range(holes + 1), 2)]}
    data = {"formal_model": model, "resources": {"max_latency_s": 0.3},
            "declared": {"consequence_class": "read_only", "reversibility": "reversible"}}
    decided = {"check_id": "decided", "description": "the infeasibility is decided",
               "sensor": {"capability": "cognition.solve", "target": "cognition:pigeonhole",
                          "params": {"problem_id": "ph10", "compile": {"geometry": {}, "data": data}}},
               "predicate": {"op": "equals", "field": "result.answer.feasible", "value": False}}
    with Run(tmp_path, attach=()) as run:
        run.sign("MISSION", question("m:hard", decided))
        assert run.tick("m:hard") == "SENSOR_RETRY"                       # before: BLOCKED on a NO_STRATEGY question
        [observation] = run.events("mission.observed", "m:hard")
        output = run.output(observation)
        assert output["state"] == "UNKNOWN" and output["host_stop"]["failure_class"] == "transient"
        assert observation["failure_class"] == "transient" and run.events("decision.requested") == []


def test_a_strategy_is_not_run_blamed_or_closed_on_for_a_host_stop(tmp_path, host):
    """The same stall when the question has a strategy (``greg.templates.compiled_question``). Before: the strategy
    was dispatched into the stalled host, marked failed, booked as an ineffective route, and the mission closed as
    a failure naming the check."""
    spec = compiled_question(problem_id="sphere-1", data=dict(SPHERE))
    mid = spec["mission_id"]
    with Run(tmp_path) as run:
        host.stall("crash")
        run.sign("MISSION", spec)
        states = [run.tick(mid) for _ in range(8)]
        assert states[0] == "SENSOR_RETRY" and "BLOCKED" in states, states
        assert run.events("mission.action", mid) == []                    # before: [("compile", "DONE")]
        assert run.mission(mid).failed == {}                             # before: {"compile": "executed but ..."}
        assert run.events("routing.outcome") == []                       # before: compile "ineffective"
        assert run.events("mission.unmet") == []                         # before: failing_checks ["answered"]
        assert [a["kind"] for a in run.events("decision.requested")] == ["SENSOR_FAILURE"]
        assert all(o["detail"].startswith("sensor inconclusive (transient): ")
                   for o in run.events("mission.observed", mid))


def test_a_round_the_mind_declined_does_not_count_toward_the_three_unmeasured_rounds(tmp_path, host):
    """The method is not attached, so the first reading is a deficit the Mind names, and the founder is asked to
    attach it. Once it is attached the host stalls. The deficit was no failed measurement: the stall starts its own
    run of unmeasured rounds, so its first back-off is 30 s and the next tick, 31 s later, reads again. Counted with
    the deficit, the first stalled round would be the second, wait 60 s, and bring the founder's question a round
    sooner."""
    spec = compiled_question(problem_id="sphere-2", data=dict(SPHERE))
    mid = spec["mission_id"]
    with Run(tmp_path, attach=()) as run:
        run.sign("MISSION", spec)
        assert [run.tick(mid) for _ in range(3)] == ["BLOCKED", "WAITING", "WAITING"]
        [deficit] = run.events("mission.observed", mid)
        assert deficit["declined"] == "CAPABILITY_DEFICIT" and "failure_class" not in deficit
        assert deficit["detail"].startswith("sensor inconclusive (CAPABILITY_DEFICIT): ")
        assert [a["kind"] for a in run.events("decision.requested")] == ["CAPABILITY_ATTACH"]
        host.stall("timeout")
        run.sign("CAPABILITY_ATTACH", {"capability_id": METHOD})
        assert [run.tick(mid) for _ in range(3)] == ["SENSOR_RETRY", "SENSOR_RETRY", "WAITING"]
        stalled = [o for o in run.events("mission.observed", mid) if o.get("failure_class") == "transient"]
        assert len(stalled) == 2 and run.offset(stalled[1]["at"]) - run.offset(stalled[0]["at"]) == STEP
        host.recover()
        assert "ACHIEVED" in [run.tick(mid) for _ in range(2)]
        assert [a["kind"] for a in run.events("decision.requested")] == ["CAPABILITY_ATTACH"]    # nothing more asked


def test_a_check_the_host_stopped_is_not_pursued_beside_a_measured_failure(tmp_path, host):
    """Beside a check that truly fails, the host-stopped check's own strategy stays undispatched (a later read may
    answer it), the real failure is pursued, and the failure closure names the stopped check as unmeasured."""
    with Run(tmp_path) as run:
        status = run.data / "status.txt"
        status.write_text("not yet")
        spec = question("m:beside", fitness_check("q"), note_check("status", status, "shipped"),
                        strategies=[write_strategy("nudge", "nudge.txt", "nudged", ["status"]),
                                    write_strategy("recompute", "q.txt", "again", ["q"])],
                        capabilities=("fs.read", "fs.write", "cognition.solve"),
                        targets=("fs:*", "workspace:*", "cognition:*"), ceiling="internal_write")
        host.stall("timeout")
        run.sign("MISSION", spec)
        for _ in range(6):
            run.tick("m:beside")
        actions = [(a["action_id"], a["status"]) for a in run.events("mission.action", "m:beside")]
        assert ("nudge", "DONE") in actions and "recompute" not in [a for a, _ in actions], actions
        [unmet] = run.events("mission.unmet", "m:beside")
        assert unmet["failing_checks"] == ["status"] and unmet["unmeasured_checks"] == ["q"]
        assert "recompute" not in run.mission("m:beside").failed


# -- a real negative stays one ----------------------------------------------------------------------------------------

def test_an_answer_whose_predicate_is_false_is_a_measured_failure_as_before(tmp_path):
    """The method answered; the answer does not meet the signed bound. The strategy ran and changed nothing: it is
    blamed, the mission closes as a failure naming the check, and the separate appraiser certifies that failure."""
    impossible = fitness_check("good", value=-1.0)
    recompute = {"action_id": "recompute", "capability": "cognition.solve", "target": "cognition:bb",
                 "params": compile_params(), "advances": ["good"], "rationale": "solve it again"}
    with Run(tmp_path) as run:
        run.sign("MISSION", question("m:neg", impossible, strategies=[recompute]))
        for _ in range(6):
            run.tick("m:neg")
        observed = run.events("mission.observed", "m:neg")
        assert observed and all(o["passed"] is False and not o["detail"].startswith("sensor ") for o in observed)
        assert all(run.output(o)["state"] == "ANSWERED" for o in observed)
        assert [(o["action_id"], o["verdict"]) for o in run.events("routing.outcome")] == [("recompute", "ineffective")]
        [unmet] = run.events("mission.unmet", "m:neg")
        assert unmet["failing_checks"] == ["good"] and "unmeasured_checks" not in unmet
        [appraised] = run.events("mission.appraised", "m:neg")
        assert appraised["verdict"] == "VERIFIED_UNMET", appraised["findings"]


def test_a_refuted_compile_receipt_is_a_measured_failure_as_before(tmp_path, monkeypatch):
    """The independent verifier refuted the method's answer (its verdict is injected at the verifier's boundary).
    That is a negative result, not an abstention: the reading is a measured failure and the retry path is not taken."""
    import greg.cognition.cortex as cortex
    monkeypatch.setattr(cortex, "independent_verify",
                        lambda *a, **k: {"verdict": "REFUTED", "dissent": ["the claimed minimum is not one"]})
    with Run(tmp_path) as run:
        run.sign("MISSION", question("m:refuted", fitness_check()))
        assert run.tick("m:refuted") == "BLOCKED"
        [observation] = run.events("mission.observed", "m:refuted")
        output = run.output(observation)
        assert output["state"] == "REFUTED" and output.get("host_stop") is None and unanswered(output) is None
        assert observation["passed"] is False and not observation["detail"].startswith("sensor ")
        assert "failure_class" not in observation
        assert [a["kind"] for a in run.events("decision.requested")] == ["NO_STRATEGY"]


# -- an abstention that is not a host stop: the treatment of an abstaining cortex receipt ------------------------------

def declined_mission(data):
    """The compile form of test_greg_unmeasured_not_failed's ``_abstaining``: the Mind declines q (the signed
    request declares the act unlawful, so the constitutional pre-filter refuses it before any method runs)."""
    status = data / "status.txt"
    status.write_text("not yet")
    return question("m:declined", fitness_check("q", consequence={"lawful": False}),
                    note_check("status", status, "shipped"),
                    strategies=[write_strategy("nudge", "nudge.txt", "nudged", ["status"]),
                                write_strategy("recompute", "q.txt", "again", ["q"])],
                    capabilities=("fs.read", "fs.write", "cognition.solve"),
                    targets=("fs:*", "workspace:*", "cognition:*"), ceiling="internal_write")


def run_declined(tmp_path):
    run = Run(tmp_path, attach=())
    run.sign("MISSION", declined_mission(run.data))
    for _ in range(10):
        run.body.tick()
        run.clock.advance(600.0)
    return run


def test_a_declined_compile_question_is_pursued_but_never_certified_as_failed(tmp_path):
    with run_declined(tmp_path) as run:
        observed = [o for o in run.events("mission.observed", "m:declined") if o["check_id"] == "q"]
        assert observed and all(o["detail"].startswith("sensor inconclusive (PROHIBITED): ") for o in observed)
        assert all("failure_class" not in o and run.output(o)["host_stop"] is None for o in observed)
        assert all(o["declined"] == "PROHIBITED" for o in observed)        # typed: the Mind declined, no host stop
        actions = [(a["action_id"], a["status"]) for a in run.events("mission.action", "m:declined")]
        assert ("recompute", "DONE") in actions                           # pursued: its cadence is unchanged
        assert not [o for o in run.events("routing.outcome") if o["action_id"] == "recompute"]   # and never blamed
        [unmet] = run.events("mission.unmet", "m:declined")
        assert unmet["failing_checks"] == ["status"] and unmet["unmeasured_checks"] == ["q"]   # before: ["q", "status"]
        [appraised] = run.events("mission.appraised", "m:declined")
        assert appraised["verdict"] == "VERIFIED_UNMET", appraised["findings"]


def test_a_declined_compile_question_with_no_strategy_is_asked_about_at_once(tmp_path):
    """An abstention the host did not cause is not retried: no later read changes what the Mind declined. A question
    with no strategy asks the founder at the first pass, as an abstaining cortex receipt does."""
    with Run(tmp_path, attach=()) as run:
        run.sign("MISSION", question("m:alone", fitness_check(consequence={"lawful": False})))
        assert run.tick("m:alone") == "BLOCKED"
        assert [a["kind"] for a in run.events("decision.requested")] == ["NO_STRATEGY"]
        [observation] = run.events("mission.observed", "m:alone")
        assert observation["detail"].startswith("sensor inconclusive (PROHIBITED): ")


def test_an_abstaining_cortex_receipt_is_recorded_as_it_was(tmp_path):
    """A cortex receipt has no field that says whether the host stopped it. Its abstention is recorded as before:
    unmeasured, pursued, and without the ``declined`` mark that takes a compile receipt's abstention out of the
    count of unmeasured rounds."""
    abstains = {"check_id": "q", "description": "game value is 0",
                "sensor": {"capability": "cognition.solve", "target": "cognition:game",
                           "params": {"problem_id": "qualified:game", "operation": "nonexistent_op", "data": {}}},
                "predicate": {"op": "equals", "field": "output.value", "value": 0}}
    with Run(tmp_path, attach=()) as run:
        run.sign("MISSION", question("m:cortex", abstains))
        assert run.tick("m:cortex") == "BLOCKED"
        [observation] = run.events("mission.observed", "m:cortex")
        assert "abstention_state" in run.output(observation) and "host_stop" not in run.output(observation)
        assert observation["detail"].startswith("sensor inconclusive (")
        assert "declined" not in observation and "failure_class" not in observation
        assert [a["kind"] for a in run.events("decision.requested")] == ["NO_STRATEGY"]


# -- the separate appraiser -------------------------------------------------------------------------------------------

def test_the_appraiser_certifies_no_failure_on_a_compile_receipt_that_did_not_answer(tmp_path, monkeypatch):
    """Defence in depth, at both places the appraiser asks ``unanswered``. A closure that still names the declined
    check (the engine before this change) is refuted: the retained receipt abstained, so it proves no failure, and
    the appraiser's own re-run of the sensor abstains again, so the world was not re-measured."""
    original = MissionEngine._pursue

    def forget_unread(self, m, now, failing, evidence, **kw):
        self.unread = set()
        return original(self, m, now, failing, evidence, **kw)

    monkeypatch.setattr(MissionEngine, "_pursue", forget_unread)
    with run_declined(tmp_path) as run:
        [unmet] = run.events("mission.unmet", "m:declined")
        assert unmet["failing_checks"] == ["q", "status"]
        [appraised] = run.events("mission.appraised", "m:declined")
        assert appraised["verdict"] == "REFUTED"                    # before: VERIFIED_UNMET
        assert any(f.startswith("q: the receipt abstained (PROHIBITED)") for f in appraised["findings"]), \
            appraised["findings"]
        assert any(f.startswith("q: the world could not be re-measured") for f in appraised["findings"])


# -- retained receipts of the earlier schema version ------------------------------------------------------------------

def retained(schema, **fields):
    value = {"schema": schema, "state": "ANSWERED", "authority_created": False,
             "selected_receipt": {"receipt_id": "sha256:inner"}, "intermediate_receipts": ["sha256:inner"], **fields}
    return {**value, "receipt_id": digest(value)}


def test_receipts_of_both_schema_versions_settle_and_are_listed_for_recheck(monkeypatch):
    """0.3 adds ``host_stop``. A body keeps the 0.2 receipts it wrote before: they still settle, and a decision
    made on evidence a resolution later rejected is still listed, whichever version wrote it."""
    for schema in ("greg-competency-compilation/0.2", compiler.SCHEMA):
        assert settlement._compiled(retained(schema)) is not None, schema
    assert settlement._compiled(retained("greg-competency-compilation/0.1")) is None

    fact = SimpleNamespace(event_id="f1", occurred_at="2026-11-01T00:00:00Z",
                           payload={"kind": "objective", "method": "cognition.swarm"})
    resolution = SimpleNamespace(event_id="r1", occurred_at="2026-11-03T00:00:00Z",
                                 payload={"resolves": ["f1", "f2"], "accept": "f2"})
    decisions = [SimpleNamespace(hash=f"h{i}", ts_utc="2026-11-02T00:00:00Z", payload={"result": {"output": {
        "schema": schema, "problem_id": f"p{i}", "methods_considered": ["cognition.swarm"],
        "method_or_composition_selected": "cognition.swarm"}}})
        for i, schema in enumerate(("greg-competency-compilation/0.2", compiler.SCHEMA))]
    journal = SimpleNamespace(replay=lambda kind: [fact] if kind == "cognition.realization" else [],
                              ledger=SimpleNamespace(by_type=lambda kind: decisions))
    monkeypatch.setattr(settlement, "_resolutions", lambda journal, signed=None: [resolution])
    assert [row["receipt"] for row in settlement.decisions_to_recheck(journal)] == ["h0", "h1"]
