"""A compile receipt that did not answer is no reading of a failure, and a host stop is retried: each part removed.

    python scripts/ci/check_compile_unanswered_mutants.py

The rule, each part mutated in a scratch copy of the repository (never the working tree):

- ``greg.missions.unanswered`` reads a Competency Compiler receipt by its own typed fields (``schema``, ``state``,
  ``result``), and ``greg.missions.host_stop`` reads the receipt's word on why it carries no answer, only when it
  carries none;
- ``greg.cognition.compiler`` names in ``host_stop`` a decision the host, not the Mind, ended without an answer: a
  worker its launcher saw time out, exit or fail to start (``greg.cognition.budget.note_host_stop``, written in
  ``cortex.py`` and ``bridge.py``, which also fixes the failure class), a deadline or compute ceiling the executed
  method's own receipt names, a chain that overran, a required step the thinking budget refused; a signed budget
  below the smallest step names no stop;
- ``MissionEngine._observe`` records a reading with a host stop as unmeasured and typed whatever its predicate made
  of it, so it passes no check, the pass re-observes with a back-off and the founder is asked once after three
  unmeasured rounds; an abstention without one keeps the treatment of an abstaining cortex receipt and ends the run
  of unmeasured rounds (``declined``); a fault the Mind named, or a construction the host stopped, is still handled
  first and recorded once;
- the appraiser certifies no success on a receipt the host stopped, read from the ledger or re-read by itself;
- a predicate on the answer of a receipt that holds none (``reads_answer``) is unmeasured, at the engine and the
  appraiser; a cortex receipt names a host stop in its own ``reason_code`` (TIMEOUT, BUDGET_EXHAUSTED); a process
  the host cannot start (EAGAIN, ENOMEM, EMFILE, ENFILE) is a launch refused, typed transient; a worker its memory
  ceiling stopped exits ``MEMORY_CEILING_EXIT``, typed budget_exceeded;
- routing does not book a reading the Mind declined as the method's failure.

The shared loop judges one test file per run. The first file holds the unit-level tests, so most mutants are judged
in a few seconds; the second runs real Bodies; the third builds constructions, so it needs networkx and scipy
(requirements-cognition.txt), and without them its tests are skipped and its mutants would be reported as surviving.
A mutant is caught only when a test FAILS (an import or collection error does not count). Exit status 1 if any
mutant survives or no longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
MISSIONS = "greg/missions.py"
APPRAISAL = "greg/appraisal.py"
ROUTING = "greg/routing.py"
COMPILER = "greg/cognition/compiler.py"
BUDGET = "greg/cognition/budget.py"
CORTEX = "greg/cognition/cortex.py"
BRIDGE = "greg/cognition/bridge.py"
SETTLEMENT = "greg/cognition/settlement.py"
WORKER = "greg/cognition/worker.py"
CAPABILITIES = "greg/capabilities.py"
READS = "        if state in COMPILE_DECIDED or (state in COMPILE_ANSWERS and output.get(\"result\") is not None):"
ANSWERS = 'COMPILE_ANSWERS = ("ANSWERED", "WORLD_UNVERIFIED", "HUMAN_JUDGMENT_RECORDED")'
CLASSES = 'HOST_STOP_CLASSES = ("transient", "budget_exceeded", "executor_error")'
SCHEMAS = 'COMPILE_SCHEMAS = ("greg-competency-compilation/0.2", "greg-competency-compilation/0.3")'
NAMED = '        named = {inner.get("reason_code"), *((inner.get("outcome") or {}).get("reasons") or ())}'
REFUSED = "    if refused and not budget.never_enough:"
HALTED = "                    passed, failure_class = False, halted\n"
UNIT = ("tests/unit/test_greg_compile_host_stop.py", [
    # review of 1c4a758c (N1, N2, N3 and the low items)
    (MISSIONS, "a compile receipt's result is read as its own state",
     'ANSWER_FIELDS = {"compile": ("result", "confidence_type", "selected_receipt"),',
     'ANSWER_FIELDS = {"compile": ("confidence_type", "selected_receipt"),'),
    (MISSIONS, "a cortex receipt's output is read as its own state",
     '                 "cortex": ("output", "proof_type", "proof_artifact", "uncertainty")}',
     '                 "cortex": ("proof_type", "proof_artifact", "uncertainty")}'),
    (MISSIONS, "every field of a receipt with no answer is read as its state",
     '    return _canon(path.split(".", 1)[0]) in {_canon(name) for name in ANSWER_FIELDS[shape]}',
     "    return False"),
    (MISSIONS, "an empty path, the whole receipt, is read as its state",
     "    if not isinstance(output, dict) or not path:\n        return True\n    shape",
     "    if not isinstance(output, dict) or not path:\n        return False\n    shape"),
    (MISSIONS, "a cortex receipt's TIMEOUT names no host stop",
     'CORTEX_STOP_CODES = {"TIMEOUT": "transient", "BUDGET_EXHAUSTED": "budget_exceeded"}',
     'CORTEX_STOP_CODES = {"BUDGET_EXHAUSTED": "budget_exceeded"}'),
    (MISSIONS, "a cortex receipt's spent budget names no host stop",
     'CORTEX_STOP_CODES = {"TIMEOUT": "transient", "BUDGET_EXHAUSTED": "budget_exceeded"}',
     'CORTEX_STOP_CODES = {"TIMEOUT": "transient"}'),
    (MISSIONS, "a reason code overrides a compile receipt's own word on its stop",
     '    if "abstention_state" in output and "host_stop" not in output:', "    if True:"),
    (MISSIONS, "a compile receipt with no state is read as the text None",
     '        return str(state) if isinstance(state, str) and state else "NO_STATE"', "        return str(state)"),
    (BUDGET, "a worker its memory ceiling stopped is typed as one that died on its own",
     "CEILING_EXITS = (*CEILING_SIGNALS, MEMORY_CEILING_EXIT)", "CEILING_EXITS = CEILING_SIGNALS"),
    (WORKER, "the worker's memory ceiling is a traceback's exit 1",
     "        os._exit(MEMORY_CEILING_EXIT)", "        raise"),
    (CAPABILITIES, "the host's exhaustion at launch passes as a raw OSError",
     "HOST_EXHAUSTED = (errno.EAGAIN, errno.ENOMEM, errno.EMFILE, errno.ENFILE)", "HOST_EXHAUSTED = ()"),
    (CAPABILITIES, "a missing executable is typed as the host's exhaustion",
     "        if exc.errno not in HOST_EXHAUSTED:\n            raise", "        if False:\n            raise"),
    (MISSIONS, "a compile receipt is read as answered whatever its state: a host stop is a measured failure again",
     READS, "        if True:"),
    (MISSIONS, "a refuted compile receipt is read as an abstention",
     'COMPILE_DECIDED = ("REFUTED", "PLANNED")', 'COMPILE_DECIDED = ("PLANNED",)'),
    (MISSIONS, "a plan, the whole of what execute:false asked for, is read as an abstention",
     'COMPILE_DECIDED = ("REFUTED", "PLANNED")', 'COMPILE_DECIDED = ("REFUTED",)'),
    (MISSIONS, "a conditional answer is read as an abstention",
     ANSWERS, 'COMPILE_ANSWERS = ("ANSWERED", "HUMAN_JUDGMENT_RECORDED")'),
    (MISSIONS, "the founder's recorded decision is read as an abstention",
     ANSWERS, 'COMPILE_ANSWERS = ("ANSWERED", "WORLD_UNVERIFIED")'),
    (MISSIONS, "a state that answers is believed without its answer",
     READS, "        if state in COMPILE_DECIDED or state in COMPILE_ANSWERS:"),
    (MISSIONS, "only the current schema version is recognised: a retained 0.2 receipt always looks answered",
     '    if isinstance(output.get("schema"), str) and output["schema"].startswith(COMPILATION):',
     '    if output.get("schema") == "greg-competency-compilation/0.3":'),
    (MISSIONS, "an output that is no receipt at all is read as an abstention",
     '    if not isinstance(output, dict):\n        return None\n    if isinstance(output.get("schema"), str)',
     '    if not isinstance(output, dict):\n        return "no receipt"\n    if isinstance(output.get("schema"), str)'),
    (MISSIONS, "a stop is read from a receipt that answered, or from an output that is no receipt",
     '    if not unanswered(output):\n        return None\n    stop = output.get("host_stop")',
     '    if not isinstance(output, dict):\n        return None\n    stop = output.get("host_stop")'),
    (MISSIONS, "a worker that died on its own is not a stop: its question is the Mind declining",
     CLASSES, 'HOST_STOP_CLASSES = ("transient", "budget_exceeded")'),
    (ROUTING, "a reading the Mind declined is booked as the method's failure",
     '.startswith("sensor ") and not observation.get("declined")', '.startswith("sensor ")'),
    (SETTLEMENT, "receipts of the new schema version settle nothing",
     SCHEMAS, 'COMPILE_SCHEMAS = ("greg-competency-compilation/0.2",)'),
    (SETTLEMENT, "retained 0.2 receipts no longer settle",
     SCHEMAS, 'COMPILE_SCHEMAS = ("greg-competency-compilation/0.3",)'),
    (SETTLEMENT, "a decision is listed for recheck only when the current schema version wrote it",
     '                and r.payload["result"]["output"].get("schema") in COMPILE_SCHEMAS]',
     '                and r.payload["result"]["output"].get("schema") == COMPILE_SCHEMAS[-1]]'),
    (COMPILER, "the schema stays 0.2 though receipts carry host_stop",
     'SCHEMA = "greg-competency-compilation/0.3"', 'SCHEMA = "greg-competency-compilation/0.2"'),
    (COMPILER, "every compile receipt without an answer claims a host stop: the Mind declining is retried",
     '"cause": "budget", "step": refused[-1]}\n    return None',
     '"cause": "budget", "step": refused[-1]}\n    return {"failure_class": "transient", "cause": "timeout"}'),
    (COMPILER, "a worker its launcher saw stop is not reported",
     "    if noted:\n        return dict(noted[0])", "    if False:\n        return dict(noted[0])"),
    (COMPILER, "a deadline the executed method's own receipt names is not a host stop",
     '    if "TIMEOUT" in named or receipt["state"] == "TIMEOUT":', '    if receipt["state"] == "TIMEOUT":'),
    (COMPILER, "a chain that overran its limit is not a host stop",
     '    if "TIMEOUT" in named or receipt["state"] == "TIMEOUT":', '    if "TIMEOUT" in named:'),
    (COMPILER, "a compute ceiling the executed method's own receipt names is not a host stop",
     '    if "BUDGET_EXHAUSTED" in named:', "    if False:"),
    (COMPILER, "the executed method's reason code is not read: a deadline the operation route names is lost",
     NAMED, '        named = set((inner.get("outcome") or {}).get("reasons") or ())'),
    (COMPILER, "the executed method's outcome reasons are not read: an engine out of budget inside the cortex "
               "worker is the Mind declining",
     NAMED, '        named = {inner.get("reason_code")}'),
    (COMPILER, "a required step the thinking budget refused is not a host stop", REFUSED, "    if False:"),
    (COMPILER, "a signed budget too small for any step is a stop: three rounds re-read what cannot change",
     REFUSED, "    if refused:"),
    (COMPILER, "an optional step the budget skipped after an answer counts as a host stop",
     '    refused = [stop["step"] for stop in budget.stops() if stop["required"]]',
     '    refused = [stop["step"] for stop in budget.stops()]'),
    (COMPILER, "the first refused step is named, not the one that ended the decision",
     '"step": refused[-1]}', '"step": refused[0]}'),
    (COMPILER, "an answer names a host stop when a later optional step was stopped",
     '        if result is None:\n            receipt["host_stop"]',
     '        if True:\n            receipt["host_stop"]'),
    (COMPILER, "the compiled decision collects no notes: every worker stop is lost",
     "        return _compile(params, noted, registry=registry,",
     "        return _compile(params, [], registry=registry,"),
    (BUDGET, "a worker its CPU ceiling killed is typed as one that died on its own",
     "CEILING_SIGNALS = (-signal.SIGXCPU, -signal.SIGKILL)", "CEILING_SIGNALS = ()"),
    (BUDGET, "a worker that died on its own is typed transient",
     'if returncode in CEILING_EXITS else "executor_error"', 'if returncode in CEILING_EXITS else "transient"'),
    (BUDGET, "a refusal the launcher did not type is noted as a stop",
     '    elif failure_class not in ("transient", "budget_exceeded"):\n        return\n', ""),
    (BUDGET, "any budget below the smallest step counts as never enough, declared or not",
     "        return self.declared and self.requested < MIN_STEP_SECONDS",
     "        return self.requested < MIN_STEP_SECONDS"),
    (BUDGET, "the collector is not restored after a decision: an outer one loses its notes",
     "        _HOST_STOPS.reset(token)", "        pass"),
    (CORTEX, "the solver's abnormal exit is not noted",
     '        note_host_stop("worker_exit", process="solver", returncode=proc.returncode)\n', ""),
    (CORTEX, "the solver's timeout is not noted",
     '        note_host_stop("timeout", process="solver")\n', "        pass\n"),
    (CORTEX, "a refused launch of the solver is not noted",
     '        note_host_stop("launch_refused", process="solver", failure_class=exc.failure_class)\n', ""),
    (CORTEX, "the verifier's abnormal exit is not noted",
     '        note_host_stop("worker_exit", process="verifier", returncode=proc.returncode)\n', "        pass\n"),
    (CORTEX, "the verifier's timeout is not noted",
     '        note_host_stop("timeout", process="verifier")\n', "        pass\n"),
    (CORTEX, "a refused launch of the verifier is not noted",
     '        note_host_stop("launch_refused", process="verifier", failure_class=exc.failure_class)\n', ""),
    (BRIDGE, "the cortex worker's abnormal exit is not noted",
     '        note_host_stop("worker_exit", process="cortex", returncode=proc.returncode)\n', ""),
    (BRIDGE, "the cortex worker's timeout is not noted",
     '        note_host_stop("timeout", process="cortex")\n', "        pass\n"),
    (BRIDGE, "a refused launch of the cortex worker is not noted",
     '        note_host_stop("launch_refused", process="cortex", failure_class=exc.failure_class)\n', ""),
])
BODY = ("tests/unit/test_greg_compile_unanswered.py", [
    # review of 1c4a758c (N1, N8): a predicate on the answer of a receipt with none; a fault read twice
    (MISSIONS, "a predicate on the answer of a receipt that holds none passes: a declined question closes ACHIEVED",
     "                if passed and unanswered(outcome.output) \\\n",
     "                if False and unanswered(outcome.output) \\\n"),
    (APPRAISAL, "the appraiser certifies a success read from the answer of a retained receipt that holds none",
     '            elif passed and unanswered(receipt.payload["result"].get("output")) \\\n',
     '            elif False and unanswered(receipt.payload["result"].get("output")) \\\n'),
    (APPRAISAL, "the appraiser takes its own re-reading with no answer for the world",
     '                    if now_ok and unanswered(output) and reads_answer(',
     '                    if False and unanswered(output) and reads_answer('),
    (MISSIONS, "a construction the host stopped is read a second time as the Mind declining (unit test)",
     "                why = None if passed or stopped or halted else unanswered(outcome.output)",
     "                why = None if passed or halted else unanswered(outcome.output)"),
    (MISSIONS, "a host stop is read as the Mind declining: the founder is asked for a strategy at the first stall",
     "                if halted:\n", "                if False:\n"),
    (MISSIONS, "a reading the host stopped still passes a check an empty receipt satisfies",
     HALTED, "                    failure_class = halted\n"),
    (MISSIONS, "a host-stopped reading carries no failure class",
     HALTED, "                    passed, failure_class = False, None\n"),
    (MISSIONS, "a host-stopped reading is not among the pass's sensor errors: the block on it is withdrawn while "
               "the host is still down",
     '                    sensor_errors.add(check["check_id"])\n'
     '                    inconclusive.add(check["check_id"])\n                views = disagreement',
     '                    inconclusive.add(check["check_id"])\n                views = disagreement'),
    (MISSIONS, "a host-stopped check is pursued beside a real failure: its strategy runs into the stalled host",
     '                    sensor_errors.add(check["check_id"])\n'
     '                    inconclusive.add(check["check_id"])\n                views = disagreement',
     '                    sensor_errors.add(check["check_id"])\n                views = disagreement'),
    (MISSIONS, "an abstention the host did not cause is not marked unread: a failure closure names it as failing",
     '                    detail = f"sensor inconclusive ({why}): {detail}"\n'
     '                    unread.add(check["check_id"])',
     '                    detail = f"sensor inconclusive ({why}): {detail}"'),
    (MISSIONS, "a round the Mind declined counts among the unmeasured rounds: a stall after a deficit waits 60 s "
               "and reaches the founder a round sooner",
     '                if measured(obs) or obs.get("declined"):', "                if measured(obs):"),
    (MISSIONS, "a reading the Mind declined is not recorded as declined",
     '                data["declined"] = declined\n', "                pass\n"),
    (MISSIONS, "a cortex receipt's abstention is recorded as declined, though it cannot say the host did not stop it",
     '                    if "host_stop" in outcome.output:\n', "                    if True:\n"),
    (APPRAISAL, "the appraiser certifies a success on a retained receipt the host stopped",
     '            elif passed and host_stop(receipt.payload["result"].get("output")):', "            elif False:"),
    (APPRAISAL, "the appraiser takes its own stopped re-reading for the world",
     "                    if host_stop(output):", "                    if False:"),
])
FIRST = ("tests/integration/test_greg_mind_constructs_capability.py", [
    (MISSIONS, "a fault the Mind named is read a second time as an abstention: its recorded detail no longer "
               "begins with the fault",
     "                why = None if passed or stopped or halted else unanswered(outcome.output)",
     "                why = None if passed or halted else unanswered(outcome.output)"),
])


def main() -> int:
    status = 0
    for tests, mutants in (UNIT, BODY, FIRST):
        status |= run(mutants, tests, "greg-compile-unanswered-mutants-", root=ROOT)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
