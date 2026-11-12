"""The typed facts behind "a compile receipt that did not answer": the reader, the receipt's ``host_stop``, the notes.

The unit-level half of tests/unit/test_greg_compile_unanswered.py, which runs the same rules on a real Body. Kept
apart so that a mutation of the reader, the compiler or a launch site is judged in seconds:

- ``greg.missions.unanswered`` reads a Competency Compiler receipt by its own typed fields, and ``host_stop`` reads
  the receipt's word on why it carries no answer, only when it carries none;
- the compiler names in ``host_stop`` a decision the host ended: a worker that timed out, exited or could not be
  launched (noted where it is launched, with the failure class of the fact), a deadline or ceiling the executed
  method's receipt names, a chain that overran, a required budget step refused; a signed budget too small for any
  step names no stop;
- settlement reads receipts of both schema versions, and routing does not book a declined reading as the method's
  failure.

The compiles here are real (``cognition.reason`` with the swarm method attached in a registry view); a stop is
injected where the worker process is launched (``greg.capabilities.run_isolated``).
"""
from __future__ import annotations

import signal
import subprocess
import time
from types import SimpleNamespace

import pytest

import greg.capabilities as caps
from greg import routing
from greg.cognition import bridge, budget, compiler, cortex, settlement
from greg.cognition.contracts import CognitionError, ProblemGeometry, digest
from greg.cognition.cortex import reason, registry_view
from greg.missions import COMPILATION, host_stop, unanswered
from tests.unit.test_greg_compile_unanswered import METHOD, Host, compile_params


@pytest.fixture
def host(monkeypatch):
    return Host(monkeypatch)


# -- the one reader ---------------------------------------------------------------------------------------------------

def compiled(state, result=None, **extra):
    return {"schema": compiler.SCHEMA, "state": state, "result": result, **extra}


def test_the_reader_knows_the_schema_the_compiler_writes():
    assert compiler.SCHEMA.startswith(COMPILATION) and compiler.SCHEMA in settlement.COMPILE_SCHEMAS
    assert "greg-competency-compilation/0.2" in settlement.COMPILE_SCHEMAS       # retained receipts still settle
    # a 0.2 receipt had no ``host_stop``; a receipt that carries the field says so in its version
    assert compiler.SCHEMA == "greg-competency-compilation/0.3"


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
    # an output that is no receipt at all (text, a list, nothing) abstained from nothing
    for output in (None, "ABSTAIN", ["UNKNOWN"], 0):
        assert unanswered(output) is None and host_stop(output) is None, output


def test_a_host_stop_is_read_only_from_a_receipt_that_did_not_answer():
    stopped = {"failure_class": "transient", "cause": "timeout", "process": "solver"}
    assert host_stop(compiled("UNKNOWN", host_stop=stopped)) == "transient"
    assert host_stop(compiled("ABSTAIN", host_stop={"failure_class": "budget_exceeded", "cause": "budget"})) \
        == "budget_exceeded"
    assert host_stop(compiled("ABSTAIN", host_stop={"failure_class": "executor_error", "cause": "worker_exit",
                                                    "process": "solver", "returncode": 1})) == "executor_error"
    # the Mind declined, or an answer stands: no stop, whatever else the output carries
    assert host_stop(compiled("PROHIBITED", host_stop=None)) is None
    assert host_stop(compiled("ANSWERED", {"fitness": 0.1}, host_stop=stopped)) is None
    assert host_stop(compiled("UNKNOWN", host_stop={"failure_class": "doctrinal_refusal"})) is None
    assert host_stop(compiled("UNKNOWN", host_stop="transient")) is None
    # an output that is not a cognitive receipt cannot claim one
    assert host_stop({"host_stop": stopped, "text": "from a file"}) is None


def test_a_reading_the_mind_declined_is_not_the_methods_failure():
    """Routing sorts an observation method whose latest reading failed after the others. A reading the Mind
    declined carries the "sensor" marker so that nobody is blamed for it, but the method ran and answered as it
    should. A reading the host stopped, and a cortex receipt's abstention (which cannot say), count as before."""
    declined = {"detail": "sensor inconclusive (PROHIBITED): field 'result.fitness' absent", "declined": "PROHIBITED"}
    stopped = {"detail": "sensor inconclusive (transient): field 'result.fitness' absent",
               "failure_class": "transient"}
    assert not routing.observation_method_failed(declined)
    assert routing.observation_method_failed(stopped)
    assert routing.observation_method_failed({"detail": "sensor inconclusive (TIMEOUT): field 'x' absent"})
    assert not routing.observation_method_failed({"detail": "1 == 0"})


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


# -- the compile receipt's typed host stop ----------------------------------------------------------------------------

@pytest.fixture
def registry():
    view = registry_view()
    view.set_state(METHOD, "ATTACHED")
    return view


def test_a_host_stop_is_read_from_typed_facts_in_order():
    spent = budget.Controller(1.0)
    stub = lambda *stops, never_enough=False: SimpleNamespace(stops=lambda: list(stops),  # noqa: E731
                                                              never_enough=never_enough)
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
    noted = [{"failure_class": "budget_exceeded", "cause": "worker_exit", "process": "solver", "returncode": -9},
             {"failure_class": "transient", "cause": "timeout", "process": "verifier"}]
    assert stop(receipt(code="TIMEOUT"), noted, spent) == noted[0]
    # only a required step the budget refused counts: an optional step is skipped after an answer, never instead of one
    optional = {"step": "sensitivity:x", "required": False, "decision": "STOP", "reason": "STOP: ..."}
    required = {"step": "answer", "required": True, "decision": "STOP", "reason": "BUDGET_EXHAUSTED: ..."}
    assert stop(receipt("ABSTAIN"), [], stub(optional)) is None
    assert stop(receipt("ABSTAIN"), [], stub(optional, required)) == {"failure_class": "budget_exceeded",
                                                                      "cause": "budget", "step": "answer"}
    # the step named is the refusal that ended the decision, the last one
    earlier = {**required, "step": "formed:first"}
    assert stop(receipt("ABSTAIN"), [], stub(earlier, required))["step"] == "answer"
    assert stop(receipt("ABSTAIN"), [], stub(required, earlier))["step"] == "formed:first"
    # a declared budget below the smallest step is refused the same way on every repeat: the Mind declines
    assert stop(receipt("ABSTAIN"), [], stub(required, never_enough=True)) is None
    assert budget.Controller(0.01).never_enough and not budget.Controller(0.01, declared=False).never_enough
    assert not budget.Controller(budget.MIN_STEP_SECONDS).never_enough


def test_the_launchers_note_only_inside_a_compiled_decision(host):
    """A note is a fact about one compiled decision. Outside one nobody collects it; a nested collector keeps its
    own; an unknown cause is refused where it is written."""
    budget.note_host_stop("timeout", process="solver")                     # no collector: dropped, no error
    with budget.host_stops() as outer:
        with budget.host_stops() as inner:
            budget.note_host_stop("worker_exit", process="solver", returncode=1)
        budget.note_host_stop("timeout", process="verifier")
    assert inner == [{"failure_class": "executor_error", "cause": "worker_exit", "process": "solver",
                      "returncode": 1}]
    assert outer == [{"failure_class": "transient", "cause": "timeout", "process": "verifier"}]
    with pytest.raises(CognitionError):
        budget.note_host_stop("the solver said no", process="solver")
    # the class is decided from the fact: only the CPU ceiling's two signals are a resource ceiling
    with budget.host_stops() as exits:
        for code in (-signal.SIGXCPU, -signal.SIGKILL, -signal.SIGSEGV, 1, 137):
            budget.note_host_stop("worker_exit", process="solver", returncode=code)
        for typed in ("transient", "budget_exceeded", "executor_error", "doctrinal_refusal", None):
            budget.note_host_stop("launch_refused", process="solver", failure_class=typed)
        budget.note_host_stop("timeout", process="solver", failure_class="executor_error")   # the fact decides
    assert [(n["cause"], n.get("returncode"), n["failure_class"]) for n in exits] == [
        ("worker_exit", -signal.SIGXCPU, "budget_exceeded"), ("worker_exit", -signal.SIGKILL, "budget_exceeded"),
        ("worker_exit", -signal.SIGSEGV, "executor_error"), ("worker_exit", 1, "executor_error"),
        ("worker_exit", 137, "executor_error"),
        ("launch_refused", None, "transient"), ("launch_refused", None, "budget_exceeded"),
        ("timeout", None, "transient")]
    # each place a worker is launched notes what it saw: the solver and the verifier of the operation route...
    geometry = ProblemGeometry(epistemic_class="optimization", latency_limit=5.0)
    launches = {"solver": lambda: cortex._numeric("swarm", {}, geometry),
                "verifier": lambda: cortex.independent_verify("swarm", {}, {}, "collective_trace", geometry)}
    for process, launch in launches.items():
        for mode, note in (
                ("crash", {"failure_class": "executor_error", "cause": "worker_exit", "returncode": 137}),
                ("ceiling", {"failure_class": "budget_exceeded", "cause": "worker_exit",
                             "returncode": -signal.SIGXCPU}),
                ("timeout", {"failure_class": "transient", "cause": "timeout"}),
                ("refuse", {"failure_class": "transient", "cause": "launch_refused"})):
            host.stall(mode)
            with budget.host_stops() as noted:
                with pytest.raises((CognitionError, subprocess.TimeoutExpired, caps.CapabilityError)):
                    launch()
            assert noted == [{**note, "process": process}], (process, mode)
        host.stall("refuse_untyped")
        with budget.host_stops() as noted:
            with pytest.raises(caps.CapabilityError):
                launch()
        assert noted == [], process
    # ...and the cortex-contract worker of the problem route
    problem = {"question": "q", "payload": {}}
    for mode, note in (
            ("crash", {"failure_class": "executor_error", "cause": "worker_exit", "process": "cortex",
                       "returncode": 137}),
            ("timeout", {"failure_class": "transient", "cause": "timeout", "process": "cortex"}),
            ("refuse", {"failure_class": "transient", "cause": "launch_refused", "process": "cortex"})):
        host.stall(mode)
        with budget.host_stops() as noted:
            with pytest.raises((CognitionError, subprocess.TimeoutExpired)):
                bridge.run_worker(problem, [], withheld_organs={}, semantic_model=None, cpu_seconds=1,
                                  created_at="2026-11-12T00:00:00Z")
        assert noted == [note]


def test_a_worker_the_host_stopped_is_named_in_a_typed_field(registry, host):
    host.stall("timeout")
    timed_out = reason(compile_params(), registry=registry)
    assert timed_out["state"] == "UNKNOWN" and timed_out["result"] is None
    assert timed_out["host_stop"] == {"failure_class": "transient", "cause": "timeout", "process": "solver"}
    host.stall("crash")
    crashed = reason(compile_params(), registry=registry)
    assert crashed["state"] == "ABSTAIN"
    # a worker that exits on its own is the executor's failure, typed as greg.mechanisms.run types a runner's exit
    assert crashed["host_stop"] == {"failure_class": "executor_error", "cause": "worker_exit", "process": "solver",
                                    "returncode": 137}
    # nothing typed named the abnormal exit before: the executed method's own receipt reports it like bad input
    assert crashed["selected_receipt"]["reason_code"] == "INSUFFICIENT_EVIDENCE"
    host.stall("ceiling")                                   # the worker's CPU ceiling killed it: a resource ceiling
    assert reason(compile_params(), registry=registry)["host_stop"] == {
        "failure_class": "budget_exceeded", "cause": "worker_exit", "process": "solver",
        "returncode": -signal.SIGXCPU}
    host.recover()
    answered = reason(compile_params(), registry=registry)
    assert answered["state"] == "ANSWERED" and answered["host_stop"] is None and unanswered(answered) is None
    host.stall("crash", only="verify")
    unverified = reason(compile_params(), registry=registry)
    assert unverified["result"] is None
    assert unverified["host_stop"] == {"failure_class": "executor_error", "cause": "worker_exit",
                                       "process": "verifier", "returncode": 137}
    host.stall("timeout", only="verify")
    assert reason(compile_params(), registry=registry)["host_stop"] == {
        "failure_class": "transient", "cause": "timeout", "process": "verifier"}


def test_a_launch_the_host_refused_is_a_stop_and_a_refused_request_is_not(registry, host):
    """``run_isolated`` types "isolation unavailable" transient where it raises it. Before, the compile kept only
    the words, so the receipt named no stop and the mission asked for a strategy at the first refusal."""
    host.stall("refuse")
    refused = reason(compile_params(), registry=registry)
    assert refused["state"] == "ABSTAIN" and refused["result"] is None
    assert refused["host_stop"] == {"failure_class": "transient", "cause": "launch_refused", "process": "solver"}
    host.stall("refuse", only="verify")
    assert reason(compile_params(), registry=registry)["host_stop"] == {
        "failure_class": "transient", "cause": "launch_refused", "process": "verifier"}
    # a refusal the launcher did not type is a refusal of the request: the same on every repeat, so no stop
    host.stall("refuse_untyped")
    untyped = reason(compile_params(), registry=registry)
    assert untyped["state"] == "ABSTAIN" and untyped["host_stop"] is None


def test_an_exhausted_budget_is_a_host_stop_and_the_mind_declining_is_not(registry):
    # the dispatch's deadline leaves no room for the required step: nothing ran, and a later dispatch may have room
    broke = reason(compile_params(), registry=registry, shared_deadline=time.monotonic() + 0.05)
    assert broke["state"] == "ABSTAIN" and broke["result"] is None
    assert broke["host_stop"] == {"failure_class": "budget_exceeded", "cause": "budget", "step": "answer"}
    # the signed question's own budget is below the smallest step: the same refusal on every repeat, so no stop
    tight = reason(compile_params(geometry={"geometry": "optimization", "latency_budget": 0.01}), registry=registry)
    assert tight["state"] == "ABSTAIN" and tight["result"] is None and tight["host_stop"] is None
    assert tight["resource_use"]["budget"]["stopped"][0]["step"] == "answer"
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
