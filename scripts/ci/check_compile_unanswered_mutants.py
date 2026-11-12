"""A compile receipt that did not answer is no reading of a failure, and a host stop is retried: each part removed.

    python scripts/ci/check_compile_unanswered_mutants.py

The rule, in three places, each mutated in a scratch copy of the repository (never the working tree):

- ``greg.missions.unanswered`` reads a Competency Compiler receipt by its own typed fields (``schema``, ``state``,
  ``result``): an answer, a conditional answer, a recorded human decision, a refutation and a plan are readings;
  every other state answered nothing;
- ``greg.cognition.compiler`` names in ``host_stop`` a decision the host, not the Mind, ended without an answer: a
  worker its launcher saw time out or exit abnormally (``greg.cognition.budget.note_host_stop``, written in
  ``cortex.py`` and ``bridge.py``), a deadline or compute ceiling the executed method's own receipt names (its
  reason code or its outcome reasons), a chain that overran, a required step the thinking budget refused;
- ``MissionEngine._observe`` records a reading with a host stop as unmeasured and typed, so the pass re-observes
  with a back-off and the founder is asked once after three unmeasured rounds; an abstention without one keeps the
  treatment of an abstaining cortex receipt, and, being no failed measurement, ends the run of unmeasured rounds
  (``declined`` on the observation); a fault the Mind named, or a construction the host stopped, is still handled
  first and recorded once.

The shared loop judges one test file per run. The second file builds constructions, so it needs networkx and scipy
(requirements-cognition.txt); without them its tests are skipped and its mutant would be reported as surviving.
A mutant is caught only when a test FAILS (an import or collection error does not count). Exit status 1 if any
mutant survives or no longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
MISSIONS = "greg/missions.py"
COMPILER = "greg/cognition/compiler.py"
CORTEX = "greg/cognition/cortex.py"
BRIDGE = "greg/cognition/bridge.py"
SETTLEMENT = "greg/cognition/settlement.py"
READS = "        if state in COMPILE_DECIDED or (state in COMPILE_ANSWERS and output.get(\"result\") is not None):"
HOST = '                if isinstance(host, dict) and host.get("failure_class") in ("transient", "budget_exceeded"):'
RULE = ("tests/unit/test_greg_compile_unanswered.py", [
    (MISSIONS, "a compile receipt is read as answered whatever its state: a host stop is a measured failure again",
     READS, "        if True:"),
    (MISSIONS, "a compile receipt is never read as answered: an answer whose predicate is false blames nobody",
     READS, "        if False:"),
    (MISSIONS, "a refuted compile receipt is read as an abstention",
     'COMPILE_DECIDED = ("REFUTED", "PLANNED")', 'COMPILE_DECIDED = ("PLANNED",)'),
    (MISSIONS, "a plan, the whole of what execute:false asked for, is read as an abstention",
     'COMPILE_DECIDED = ("REFUTED", "PLANNED")', 'COMPILE_DECIDED = ("REFUTED",)'),
    (MISSIONS, "a conditional answer is read as an abstention",
     'COMPILE_ANSWERS = ("ANSWERED", "WORLD_UNVERIFIED", "HUMAN_JUDGMENT_RECORDED")',
     'COMPILE_ANSWERS = ("ANSWERED", "HUMAN_JUDGMENT_RECORDED")'),
    (MISSIONS, "the founder's recorded decision is read as an abstention",
     'COMPILE_ANSWERS = ("ANSWERED", "WORLD_UNVERIFIED", "HUMAN_JUDGMENT_RECORDED")',
     'COMPILE_ANSWERS = ("ANSWERED", "WORLD_UNVERIFIED")'),
    (MISSIONS, "a state that answers is believed without its answer: an abstention marked WORLD_UNVERIFIED reads "
               "as answered",
     READS, "        if state in COMPILE_DECIDED or state in COMPILE_ANSWERS:"),
    (MISSIONS, "a question still waiting for the founder's judgment is read as answered",
     'COMPILE_ANSWERS = ("ANSWERED", "WORLD_UNVERIFIED", "HUMAN_JUDGMENT_RECORDED")',
     'COMPILE_ANSWERS = ("ANSWERED", "WORLD_UNVERIFIED", "HUMAN_JUDGMENT_RECORDED", "HUMAN_JUDGMENT_REQUIRED")'),
    (MISSIONS, "only the current schema version is recognised: a retained 0.2 receipt always looks answered",
     '    if isinstance(output.get("schema"), str) and output["schema"].startswith(COMPILATION):',
     '    if output.get("schema") == "greg-competency-compilation/0.3":'),
    (MISSIONS, "a host stop is read as the Mind declining: the founder is asked for a strategy at the first stall",
     HOST, "                if False:"),
    (MISSIONS, "a stop for an exhausted budget is read as the Mind declining",
     HOST, HOST.replace('("transient", "budget_exceeded")', '("transient",)')),
    (MISSIONS, "a host-stopped reading carries no failure class",
     '                    failure_class = host["failure_class"]\n'
     '                    detail = f"sensor inconclusive ({failure_class}): {detail}"',
     '                    detail = f"sensor inconclusive ({host[\'failure_class\']}): {detail}"'),
    (MISSIONS, "a host-stopped reading is not among the pass's sensor errors: the block on it is withdrawn while "
               "the host is still down",
     '                    sensor_errors.add(check["check_id"])\n'
     '                    inconclusive.add(check["check_id"])\n                elif why:',
     '                    inconclusive.add(check["check_id"])\n                elif why:'),
    (MISSIONS, "a host-stopped check is pursued beside a real failure: its strategy runs into the stalled host",
     '                    sensor_errors.add(check["check_id"])\n'
     '                    inconclusive.add(check["check_id"])\n                elif why:',
     '                    sensor_errors.add(check["check_id"])\n                elif why:'),
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
    (COMPILER, "every compile receipt without an answer claims a host stop: the Mind declining is retried",
     "        return {\"failure_class\": \"budget_exceeded\", \"cause\": \"budget\", \"step\": refused[-1]}\n"
     "    return None",
     "        return {\"failure_class\": \"budget_exceeded\", \"cause\": \"budget\", \"step\": refused[-1]}\n"
     "    return {\"failure_class\": \"transient\", \"cause\": \"timeout\"}"),
    (COMPILER, "a worker its launcher saw stop is not reported: an abnormal exit is the Mind declining",
     "    if noted:\n        return {\"failure_class\": \"transient\", **noted[0]}",
     "    if False:\n        return {\"failure_class\": \"transient\", **noted[0]}"),
    (COMPILER, "a deadline the executed method's own receipt names is not a host stop",
     '    if "TIMEOUT" in named or receipt["state"] == "TIMEOUT":', '    if receipt["state"] == "TIMEOUT":'),
    (COMPILER, "a chain that overran its limit is not a host stop",
     '    if "TIMEOUT" in named or receipt["state"] == "TIMEOUT":', '    if "TIMEOUT" in named:'),
    (COMPILER, "a compute ceiling the executed method's own receipt names is not a host stop",
     '    if "BUDGET_EXHAUSTED" in named:', "    if False:"),
    (COMPILER, "the executed method's reason code is not read: a deadline the operation route names is lost",
     '        named = {inner.get("reason_code"), *((inner.get("outcome") or {}).get("reasons") or ())}',
     '        named = set((inner.get("outcome") or {}).get("reasons") or ())'),
    (COMPILER, "the executed method's outcome reasons are not read: an engine out of budget inside the cortex "
               "worker is the Mind declining",
     '        named = {inner.get("reason_code"), *((inner.get("outcome") or {}).get("reasons") or ())}',
     '        named = {inner.get("reason_code")}'),
    (COMPILER, "a required step the thinking budget refused is not a host stop",
     '    if refused:\n        return {"failure_class": "budget_exceeded"',
     '    if False:\n        return {"failure_class": "budget_exceeded"'),
    (COMPILER, "an optional step the budget skipped after an answer counts as a host stop",
     '    refused = [stop["step"] for stop in budget.stops() if stop["required"]]',
     '    refused = [stop["step"] for stop in budget.stops()]'),
    (COMPILER, "an answer names a host stop when a later optional step was stopped",
     '        if result is None:\n            receipt["host_stop"]',
     '        if True:\n            receipt["host_stop"]'),
    (COMPILER, "the compiled decision collects no notes: every worker stop is lost",
     "        return _compile(params, noted, registry=registry,",
     "        return _compile(params, [], registry=registry,"),
    (CORTEX, "the solver's abnormal exit is not noted",
     '        note_host_stop("worker_exit", process="solver", returncode=proc.returncode)\n', ""),
    (CORTEX, "the solver's timeout is not noted",
     '        note_host_stop("timeout", process="solver")\n', "        pass\n"),
    (CORTEX, "the verifier's abnormal exit is not noted",
     '        note_host_stop("worker_exit", process="verifier", returncode=proc.returncode)\n', "        pass\n"),
    (CORTEX, "the verifier's timeout is not noted",
     '        note_host_stop("timeout", process="verifier")\n', "        pass\n"),
    (BRIDGE, "the cortex worker's abnormal exit is not noted",
     '        note_host_stop("worker_exit", process="cortex", returncode=proc.returncode)\n', ""),
    (BRIDGE, "the cortex worker's timeout is not noted",
     '        note_host_stop("timeout", process="cortex")\n', "        pass\n"),
    (SETTLEMENT, "receipts of the new schema version settle nothing",
     'COMPILE_SCHEMAS = ("greg-competency-compilation/0.2", "greg-competency-compilation/0.3")',
     'COMPILE_SCHEMAS = ("greg-competency-compilation/0.2",)'),
    (SETTLEMENT, "retained 0.2 receipts no longer settle",
     'COMPILE_SCHEMAS = ("greg-competency-compilation/0.2", "greg-competency-compilation/0.3")',
     'COMPILE_SCHEMAS = ("greg-competency-compilation/0.3",)'),
    (SETTLEMENT, "a decision is listed for recheck only when the current schema version wrote it",
     '                and r.payload["result"]["output"].get("schema") in COMPILE_SCHEMAS]',
     '                and r.payload["result"]["output"].get("schema") == COMPILE_SCHEMAS[-1]]'),
])
FIRST = ("tests/integration/test_greg_mind_constructs_capability.py", [
    (MISSIONS, "a fault the Mind named is read a second time as an abstention: its recorded detail no longer "
               "begins with the fault",
     "                why = None if passed or stopped else unanswered(outcome.output)",
     "                why = None if passed else unanswered(outcome.output)"),
    (MISSIONS, "a fault the Mind named is not marked as already recorded",
     '                        self.mind_faults.add(check["check_id"])\n                        stopped = True\n',
     '                        self.mind_faults.add(check["check_id"])\n'),
    (MISSIONS, "a construction the host stopped is read again as declined: it ends the run of unmeasured rounds, "
               "and a construction that faults every other pass never reaches the founder",
     '                        inconclusive.add(check["check_id"])\n                        stopped = True\n',
     '                        inconclusive.add(check["check_id"])\n'),
])


def main() -> int:
    status = 0
    for tests, mutants in (RULE, FIRST):
        status |= run(mutants, tests, "greg-compile-unanswered-mutants-", root=ROOT)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
