"""usage (cwd = tree): untyped.py isolation|refuted|direct_timeout|direct_crash [strategy]"""
import sys, json
from rcu_common import *
SC = sys.argv[1]; STRAT = len(sys.argv) > 2
host = Host()
real = host.real
def solve_strategy(params):
    return {"action_id": "compile", "capability": "cognition.solve", "target": "cognition:bb", "params": params, "advances": ["good"], "rationale": "compile"}
print("==", SC, "strategy" if STRAT else "sensor-only")
with Run() as run:
    check = fitness_check()
    if SC == "isolation":
        def launch(argv, *a, **k):
            if any("worker.py" in str(x) for x in argv):
                raise caps.CapabilityError("network isolation unavailable; command refused", failure_class="transient")
            return real(argv, *a, **k)
        caps.run_isolated = launch
    elif SC == "refuted":
        def launch(argv, *a, **k):
            proc = real(argv, *a, **k)
            if "verify" in argv:
                from greg.cognition.contracts import canonical
                out = json.loads(proc.stdout); out["verdict"] = "REFUTED"; out.setdefault("dissent", []).append("probe")
                return subprocess.CompletedProcess(argv, 0, canonical(out).encode(), b"")
            return proc
        caps.run_isolated = launch
    elif SC.startswith("direct"):
        params = {"problem_id": "real:q", "operation": "swarm_minimize", "data": dict(SPHERE)}
        check = {"check_id": "good", "description": "fitness bound", "sensor": {"capability": "cognition.solve", "target": "cognition:bb", "params": params},
                 "predicate": {"op": "lte", "field": "output.fitness", "value": 1e6}}
        host.stall("timeout" if SC.endswith("timeout") else "crash")
    strategies = [solve_strategy(check["sensor"]["params"])] if STRAT else []
    run.sign("MISSION", question("m:nbr", check, strategies=strategies))
    states = [run.tick("m:nbr") for _ in range(8)]
    print("  states(31s):", states)
    run.report("m:nbr")
    o = run.output(run.events("mission.observed", "m:nbr")[0])
    print("  first reading:", {k: str(o.get(k))[:120] for k in ("schema", "state", "abstention_state", "reason_code", "host_stop", "missing_information", "method")})
