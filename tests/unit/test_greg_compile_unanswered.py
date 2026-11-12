"""A Competency Compiler receipt that did not answer is no reading of a failure, and a host stop is retried.

``greg.missions.unanswered`` tells the engine and the separate appraiser that a cognitive receipt abstained. It read
only ``abstention_state``, which a cortex receipt carries. A compile receipt carries ``state`` and ``result``
instead, so every compile receipt looked answered: a signed question whose solver worker the host stopped was
recorded as a measured failure. A question with no strategy asked the founder for one at the first stall and then
waited a whole cadence; a question with a strategy had it dispatched, blamed and closed as a failure.

What these tests pin:

- the one reader gives a compile receipt the answer it gives a cortex receipt, by the receipt's typed fields;
- the compile receipt says in a typed field (``host_stop``) when the host, not the Mind, ended the decision: a worker
  that timed out, exited abnormally or could not be launched, or an exhausted compute budget, each with the failure
  class of the fact; a signed budget too small for any step is the Mind declining, not a stop;
- the engine re-observes such a reading with a back-off and asks once after three unmeasured rounds, as it does for a
  construction the host stopped; an abstention that is not a host stop keeps the treatment of an abstaining cortex
  receipt (pursued, never certified as failed);
- a reading the host stopped is unmeasured on either side of its predicate: it fails no check and passes none;
- a real negative (a refuted receipt, an answer whose predicate is false) stays a measured failure;
- the separate appraiser certifies no failure on a compile receipt that did not answer, and no success on one the
  host stopped;
- a reading the Mind declined is not booked as a failure of the method that read it.

Each test here runs a real Body through the real office and Gate. The host stop is injected where the solver
worker process is launched (``greg.capabilities.run_isolated``): nothing downstream of the launch is replaced.
In-process Body, a test clock and a per-test founder key, not Alfonso's (SANDBOX). The reader, the receipt's typed
field and the launch sites are pinned on their own in tests/unit/test_greg_compile_host_stop.py. The tests a
mutation of the engine needs come first, so that the gate judges each mutant in a few seconds.
"""
from __future__ import annotations

import signal
import subprocess
from datetime import datetime

import pytest

import greg.capabilities as caps
import greg.missions
from greg import appraisal, routing
from greg.body import Body
from greg.missions import MissionEngine, unanswered
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
    """The place a solver or verifier worker process is launched. ``stall`` makes every such launch give no result:
    ``timeout`` (the worker does not finish inside its limit), ``crash`` (it exits 137), ``ceiling`` (its CPU
    ceiling kills it: SIGXCPU), ``refuse`` (the launcher refuses, typed transient: isolation unavailable) or
    ``refuse_untyped`` (the launcher refuses the request itself, with no failure class)."""

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
                if self.mode == "refuse":
                    raise caps.CapabilityError("network isolation unavailable; command refused",
                                               failure_class="transient")
                if self.mode == "refuse_untyped":
                    raise caps.CapabilityError("argv must be a non-empty list of strings")
                return subprocess.CompletedProcess(argv, -signal.SIGXCPU if self.mode == "ceiling" else 137, b"", b"")
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


# -- a reading the host stopped is unmeasured on either side of its predicate ---------------------------------------

def no_counterexample(check_id="clean"):
    """A check an empty receipt satisfies: the claim holds when the result names no counterexample."""
    return {"check_id": check_id, "description": "the claim has no counterexample",
            "sensor": {"capability": "cognition.solve", "target": "cognition:bb", "params": compile_params()},
            "predicate": {"op": "absent", "field": "result.counterexample"}}


@pytest.mark.parametrize("op", ["absent", "equals"])
def test_a_reading_the_host_stopped_never_passes_a_check(tmp_path, host, op):
    """Unreadable evidence stays unknown. Before, a predicate an empty receipt satisfies passed on a reading the
    host had stopped, and the mission closed ACHIEVED on a question no method had answered."""
    predicate = {"absent": {"op": "absent", "field": "result.counterexample"},
                 "equals": {"op": "equals", "field": "result", "value": None}}[op]
    check = {**no_counterexample(), "predicate": predicate}
    with Run(tmp_path) as run:
        host.stall("timeout")
        run.sign("MISSION", question("m:empty", check))
        assert [run.tick("m:empty") for _ in range(2)] == ["SENSOR_RETRY", "SENSOR_RETRY"]   # before: ACHIEVED
        observed = run.events("mission.observed", "m:empty")
        assert all(o["passed"] is False and o["failure_class"] == "transient" for o in observed), observed
        assert all(o["detail"].startswith("sensor inconclusive (transient): ") for o in observed)
        assert run.mission("m:empty").status != "ACHIEVED" and run.events("mission.achieved") == []
        assert run.events("mission.appraised") == [] and run.events("decision.requested") == []


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


# -- an abstention that is not a host stop: the treatment of an abstaining cortex receipt ----------------------------

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
        assert [a["kind"] for a in run.events("decision.requested")] == ["CAPABILITY_ATTACH"]    # nothing more asked


def test_a_signed_budget_too_small_for_any_step_is_declined_and_never_retried(tmp_path):
    """The signed question declares a thinking budget below the smallest step that can solve and verify. The
    required step is refused, and it would be refused the same way on every repeat, whatever the host does. That
    is the Mind declining the request as signed, not a stop: the founder is asked at the first pass, as for any
    abstention, and the mission does not spend three rounds re-reading what cannot change."""
    tight = fitness_check(geometry={"geometry": "optimization", "latency_budget": 0.01})
    with Run(tmp_path) as run:
        run.sign("MISSION", question("m:tight", tight))
        assert [run.tick("m:tight") for _ in range(4)] == ["BLOCKED", "WAITING", "WAITING", "WAITING"]
        observed = run.events("mission.observed", "m:tight")
        assert all(o["declined"] == "ABSTAIN" and "failure_class" not in o for o in observed), observed
        assert all(o["detail"].startswith("sensor inconclusive (ABSTAIN): ") for o in observed)
        assert run.output(observed[0])["host_stop"] is None
        assert [a["kind"] for a in run.events("decision.requested")] == ["NO_STRATEGY"]


def test_a_receipt_that_reads_its_own_declined_state_still_passes(tmp_path):
    """Only a stop is kept from passing. A check may read a receipt's own state: "the Mind refuses this act" is
    satisfied by the PROHIBITED receipt, which names no stop."""
    refuses = {"check_id": "refused", "description": "the Mind refuses an unlawful act",
               "sensor": {"capability": "cognition.solve", "target": "cognition:bb",
                          "params": compile_params(consequence={"lawful": False})},
               "predicate": {"op": "equals", "field": "state", "value": "PROHIBITED"}}
    with Run(tmp_path, attach=()) as run:
        run.sign("MISSION", question("m:refuses", refuses))
        assert run.tick("m:refuses") == "ACHIEVED"
        [read] = run.events("mission.observed", "m:refuses")
        assert read["passed"] is True and "declined" not in read and "failure_class" not in read


def test_a_reading_the_mind_declined_is_not_booked_as_the_methods_failure(tmp_path, host):
    """Routing sorts an observation method whose latest reading failed after the others. A prohibition or a named
    deficit is the method working, not failing; a reading the host stopped did fail to measure, as before."""
    with Run(tmp_path) as run:
        run.sign("MISSION", question("m:alone", fitness_check(consequence={"lawful": False})))
        run.tick("m:alone")
        [declined] = run.events("mission.observed", "m:alone")
        assert declined["declined"] == "PROHIBITED" and not routing.observation_method_failed(declined)
        assert routing.observation_competence(run.body.journal) == {"cognition.solve": {"method_failed": False}}
        host.stall("timeout")
        run.sign("MISSION", question("m:stalled", fitness_check(problem="real:other")))
        run.tick("m:stalled")
        [stopped] = run.events("mission.observed", "m:stalled")
        assert routing.observation_method_failed(stopped)
        assert routing.observation_competence(run.body.journal) == {"cognition.solve": {"method_failed": True}}
    # a cortex receipt's abstention carries no ``declined`` mark and is read as before
    assert routing.observation_method_failed({"detail": "sensor inconclusive (TIMEOUT): field 'x' absent"})
    assert not routing.observation_method_failed({"detail": "1 == 0"})


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


def test_the_appraiser_certifies_no_success_on_a_receipt_the_host_stopped(tmp_path, host, monkeypatch):
    """Defence in depth, where the appraiser re-derives a success closure from the retained receipt. The engine is
    made to close as it did before this change (it no longer reads the stop); the separate appraiser reads the
    receipt's own ``host_stop`` and refuses the closure, though its own re-run of the sensor answers."""
    monkeypatch.setattr(greg.missions, "host_stop", lambda output: None)
    with Run(tmp_path) as run:
        host.stall("timeout")
        run.sign("MISSION", question("m:empty", no_counterexample()))
        assert run.tick("m:empty") == "ACHIEVED"
        assert run.output(run.events("mission.observed", "m:empty")[0])["host_stop"]["failure_class"] == "transient"
        [appraised] = run.events("mission.appraised", "m:empty")
        assert appraised["verdict"] == "REFUTED"                               # before: VERIFIED
        assert appraised["checks"]["checks_rederived_from_receipts"] is False
        assert appraised["checks"]["world_reobserved"] is True
        assert any(f.startswith("clean: the host stopped the receipt's read (transient), so it proves no success")
                   for f in appraised["findings"]), appraised["findings"]


def test_the_appraiser_does_not_take_its_own_stopped_reread_for_the_world(tmp_path, host):
    """Where the appraiser re-observes the world. The mission closed on a real answer; the appraiser's own host
    then stops its re-run of the sensor. An empty re-reading satisfies the predicate and measured nothing, so the
    closure is not verified. The appraiser runs in this process here so that its launches can be stopped."""
    with Run(tmp_path) as run:
        run.sign("MISSION", question("m:empty", no_counterexample()))
        assert run.tick("m:empty") == "ACHIEVED"
        request = run.body.appraisal_request("m:empty")
        assert appraisal.appraise(request)["verdict"] == "VERIFIED"
        host.stall("timeout")
        verdict = appraisal.appraise(request)
        assert verdict["verdict"] != "VERIFIED" and verdict["checks"]["world_reobserved"] is False   # before: VERIFIED
        assert verdict["checks"]["checks_rederived_from_receipts"] is True
        assert any(f.startswith("clean: the world could not be re-measured") for f in verdict["findings"])


# -- the engine: a host stop is retried, not asked about at once ------------------------------------------------------

STOPS = {"timeout": ("transient", "timeout"), "crash": ("executor_error", "worker_exit"),
         "ceiling": ("budget_exceeded", "worker_exit"), "refuse": ("transient", "launch_refused")}


@pytest.mark.parametrize("mode", sorted(STOPS))
def test_a_question_the_host_stopped_is_read_again_within_the_back_off_and_nobody_is_asked(tmp_path, host, mode):
    typed, cause = STOPS[mode]
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
            assert observation["passed"] is False and observation["failure_class"] == typed
            assert "declined" not in observation
            assert observation["detail"].startswith(f"sensor inconclusive ({typed}): ")
            assert run.output(observation)["host_stop"]["cause"] == cause
        assert read["passed"] is True
        # read again inside the back-off (60 s after the second round), not a whole cadence later
        assert 0 <= run.offset(read["at"]) - recovered <= 60 < CADENCE
        assert run.events("decision.requested") == [] and run.events("decision.withdrawn") == []
        assert run.mission("m:quest").status == "ACHIEVED"


def test_the_question_about_a_stalled_host_is_withdrawn_once_the_sensor_reads_again(tmp_path, host):
    """After three unmeasured rounds the founder has one SENSOR_FAILURE question. When the host is back, the next
    read at the cadence answers; the body withdraws the question itself and the mission closes."""
    with Run(tmp_path) as run:
        host.stall("timeout")
        run.sign("MISSION", question("m:quest", fitness_check()))
        assert [run.tick("m:quest") for _ in range(4)][-1] == "BLOCKED"
        host.recover()
        run.clock.advance(CADENCE)
        assert "ACHIEVED" in [run.tick("m:quest") for _ in range(3)]
        assert [a["kind"] for a in run.events("decision.requested")] == ["SENSOR_FAILURE"]
        assert len(run.events("decision.withdrawn")) == 1


def test_the_check_passes_once_a_method_has_answered(tmp_path, host):
    with Run(tmp_path) as run:
        host.stall("timeout")
        run.sign("MISSION", question("m:empty", no_counterexample()))
        assert run.tick("m:empty") == "SENSOR_RETRY"
        host.recover()
        assert "ACHIEVED" in [run.tick("m:empty") for _ in range(3)]
        read = run.events("mission.observed", "m:empty")[-1]
        assert read["passed"] is True and run.output(read)["state"] == "ANSWERED"
        [appraised] = run.events("mission.appraised", "m:empty")
        assert appraised["verdict"] == "VERIFIED", appraised["findings"]


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
        assert all(o["detail"].startswith("sensor inconclusive (executor_error): ")
                   for o in run.events("mission.observed", mid))


def test_a_strategy_is_not_dispatched_into_a_host_that_refuses_to_launch(tmp_path, host):
    """Isolation is unavailable, so no worker can start. Before, the receipt named no stop: the strategy was
    dispatched into the same refusal and marked failed, and the founder was asked for another strategy."""
    spec = compiled_question(problem_id="sphere-3", data=dict(SPHERE))
    mid = spec["mission_id"]
    with Run(tmp_path) as run:
        host.stall("refuse")
        run.sign("MISSION", spec)
        assert [run.tick(mid) for _ in range(2)] == ["SENSOR_RETRY", "SENSOR_RETRY"]   # before: ACTED, BLOCKED
        assert run.events("mission.action", mid) == [] and run.mission(mid).failed == {}
        assert run.events("decision.requested") == []                          # before: NO_STRATEGY
        host.recover()
        assert "ACHIEVED" in [run.tick(mid) for _ in range(3)]
        assert run.events("decision.requested") == [] and run.events("mission.action", mid) == []


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
