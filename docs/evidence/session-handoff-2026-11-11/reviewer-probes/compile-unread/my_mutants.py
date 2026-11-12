"""Reviewer's own mutants of the decision points the change adds; same harness, same test file. cwd irrelevant."""
import sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "scripts" / "ci"))
from mutation_harness import run
MISSIONS = "greg/missions.py"; COMPILER = "greg/cognition/compiler.py"; CORTEX = "greg/cognition/cortex.py"
BRIDGE = "greg/cognition/bridge.py"; BUDGET = "greg/cognition/budget.py"; SETTLEMENT = "greg/cognition/settlement.py"
HOST = '                if isinstance(host, dict) and host.get("failure_class") in ("transient", "budget_exceeded"):'
M = [
    (MISSIONS, "R01 a transient host stop is read as the Mind declining (only budget_exceeded retried)",
     HOST, HOST.replace('("transient", "budget_exceeded")', '("budget_exceeded",)')),
    (MISSIONS, "R02 a budget stop is recorded with failure_class transient",
     '                    failure_class = host["failure_class"]\n', '                    failure_class = "transient"\n'),
    (MISSIONS, "R03 a transient stop is recorded with failure_class budget_exceeded",
     '                    failure_class = host["failure_class"]\n', '                    failure_class = "budget_exceeded"\n'),
    (MISSIONS, "R04 a host-stopped reading keeps a measured detail (no 'sensor inconclusive' prefix)",
     '                    failure_class = host["failure_class"]\n                    detail = f"sensor inconclusive ({failure_class}): {detail}"\n',
     '                    failure_class = host["failure_class"]\n'),
    (MISSIONS, "R05 a declined reading keeps a measured detail (no prefix): its strategy is blamed",
     '                    detail = f"sensor inconclusive ({why}): {detail}"\n                    unread.add(check["check_id"])',
     '                    unread.add(check["check_id"])'),
    (MISSIONS, "R06 ANSWERED is dropped from the answered set",
     'COMPILE_ANSWERS = ("ANSWERED", "WORLD_UNVERIFIED", "HUMAN_JUDGMENT_RECORDED")',
     'COMPILE_ANSWERS = ("WORLD_UNVERIFIED", "HUMAN_JUDGMENT_RECORDED")'),
    (MISSIONS, "R07 a declined round ends the streak only if it was also measured (and for or)",
     '                if measured(obs) or obs.get("declined"):', '                if measured(obs) and obs.get("declined"):'),
    (MISSIONS, "R08 declined is recorded for every unanswered reading, a host-stopped one included",
     '            if declined is not None:\n                data["declined"] = declined\n',
     '            if declined is not None or (failure_class in ("transient", "budget_exceeded") and "host_stop" in (outcome.output or {})):\n'
     '                data["declined"] = declined or "host"\n'),
    (MISSIONS, "R09 a non-dict output is read as unanswered",
     '    if not isinstance(output, dict):\n        return None\n    if isinstance(output.get("schema"), str)',
     '    if not isinstance(output, dict):\n        return "not a receipt"\n    if isinstance(output.get("schema"), str)'),
    (MISSIONS, "R10 PLANNED and REFUTED need a result to count as decided",
     '        if state in COMPILE_DECIDED or (state in COMPILE_ANSWERS and output.get("result") is not None):',
     '        if (state in COMPILE_DECIDED or state in COMPILE_ANSWERS) and output.get("result") is not None:'),
    (COMPILER, "R11 the last noted stop is reported instead of the first",
     '        return {"failure_class": "transient", **noted[0]}', '        return {"failure_class": "transient", **noted[-1]}'),
    (COMPILER, "R12 a named TIMEOUT is typed budget_exceeded",
     '        return {"failure_class": "transient", "cause": "timeout"}', '        return {"failure_class": "budget_exceeded", "cause": "timeout"}'),
    (COMPILER, "R13 a named BUDGET_EXHAUSTED is typed transient",
     '        return {"failure_class": "budget_exceeded", "cause": "budget"}\n', '        return {"failure_class": "transient", "cause": "budget"}\n'),
    (COMPILER, "R14 a refused required step is typed transient",
     '        return {"failure_class": "budget_exceeded", "cause": "budget", "step": refused[-1]}',
     '        return {"failure_class": "transient", "cause": "budget", "step": refused[-1]}'),
    (COMPILER, "R15 the first refused step is named instead of the last",
     '"step": refused[-1]}', '"step": refused[0]}'),
    (COMPILER, "R16 a noted worker stop is typed budget_exceeded",
     '        return {"failure_class": "transient", **noted[0]}', '        return {"failure_class": "budget_exceeded", **noted[0]}'),
    (COMPILER, "R17 a receipt that carries a result has no host_stop key at all",
     '               "selected_receipt": None, "host_stop": None}', '               "selected_receipt": None}'),
    (COMPILER, "R18 the schema stays 0.2 though receipts carry host_stop",
     'SCHEMA = "greg-competency-compilation/0.3"', 'SCHEMA = "greg-competency-compilation/0.2"'),
    (BUDGET, "R19 an unknown cause is accepted",
     '    if cause not in HOST_STOP_CAUSES:\n        raise CognitionError(f"unknown host stop cause {cause!r}")\n', ''),
    (BUDGET, "R20 the collector is not restored after a decision",
     '        _HOST_STOPS.reset(token)', '        pass'),
    (BUDGET, "R21 the return code is not kept on the note",
     '**({} if returncode is None else {"returncode": returncode})', ''),
    (BUDGET, "R22 no note is ever written",
     '        log.append({"cause": cause, "process": process, **({} if returncode is None else {"returncode": returncode})})',
     '        pass'),
    (BUDGET, "R23 a nested collector also feeds the outer one",
     '    log: list = []\n    token = _HOST_STOPS.set(log)', '    log: list = [] if _HOST_STOPS.get() is None else _HOST_STOPS.get()\n    token = _HOST_STOPS.set(log)'),
    (CORTEX, "R24 the solver's timeout is noted as a worker exit",
     '        note_host_stop("timeout", process="solver")', '        note_host_stop("worker_exit", process="solver")'),
    (CORTEX, "R25 the verifier's abnormal exit is noted as the solver's",
     '        note_host_stop("worker_exit", process="verifier", returncode=proc.returncode)',
     '        note_host_stop("worker_exit", process="solver", returncode=proc.returncode)'),
    (BRIDGE, "R26 the cortex worker's timeout is noted as a worker exit",
     '        note_host_stop("timeout", process="cortex")', '        note_host_stop("worker_exit", process="cortex")'),
    (SETTLEMENT, "R27 _compiled keeps reading both versions but decisions_to_recheck reads only 0.2",
     '                and r.payload["result"]["output"].get("schema") in COMPILE_SCHEMAS]',
     '                and r.payload["result"]["output"].get("schema") == COMPILE_SCHEMAS[0]]'),
]
only = set(sys.argv[2:]) 
M = [m for m in M if not only or m[1].split()[0] in only]
raise SystemExit(run(M, "tests/unit/test_greg_compile_unanswered.py", "rcu-my-mutants-", root=ROOT))
