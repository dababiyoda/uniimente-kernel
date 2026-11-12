"""FORMALIZATION_INCOMPLETE as a mission reading (sensor-only and with a strategy). cwd = tree."""
import itertools, sys
from rcu_common import *
DECL = {"consequence_class": "read_only", "reversibility": "reversible"}
def pigeonhole(holes, budget):
    return {"formal_model": {"requirement": "every pigeon in a distinct hole",
        "variables": [{"name": f"p{k}", "sort": "int", "lo": 1, "hi": holes} for k in range(holes + 1)],
        "obligations": [{"id": "R", "text": "distinct"}],
        "constraints": [{"id": f"C{a}_{b}", "covers": ["R"], "expr": ["!=", f"p{a}", f"p{b}"]} for a, b in itertools.combinations(range(holes + 1), 2)]},
        "resources": {"max_latency_s": budget}, "declared": DECL}
STRAT = len(sys.argv) > 1
params = {"problem_id": "ph4", "compile": {"geometry": {"consequence_class": "financial"}, "data": pigeonhole(4, 5.0)}}
check = {"check_id": "good", "description": "decided", "sensor": {"capability": "cognition.solve", "target": "cognition:bb", "params": params},
         "predicate": {"op": "exists", "field": "result.claim"}}
strategies = [{"action_id": "compile", "capability": "cognition.solve", "target": "cognition:bb", "params": params, "advances": ["good"], "rationale": "compile"}] if STRAT else []
with Run() as run:
    run.sign("MISSION", question("m:nbr", check, strategies=strategies))
    states = [run.tick("m:nbr") for _ in range(6)] + [run.tick("m:nbr", step=3700) for _ in range(3)]
    print("== formal_incomplete", "strategy" if STRAT else "sensor-only", "| states:", states)
    run.report("m:nbr")
    o = run.output(run.events("mission.observed", "m:nbr")[0])
    print("  first reading:", {k: str(o.get(k))[:120] for k in ("schema", "state", "host_stop", "abstentions")})
