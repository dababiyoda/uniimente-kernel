"""A formed construction faults (its engine lies) beside a second compile check that is host-stopped or declined.
usage (cwd = tree): fault_beside.py stall|decline"""
import sys
from rcu_common import *
from greg.cognition import network
from greg.templates import compiled_question
MODE = sys.argv[1]
STAFFING = {"workers": [{"id": "Ana", "capacity": 2, "skills": ["forklift"]}, {"id": "Ben", "capacity": 4, "skills": ["packing", "forklift"]},
                        {"id": "Cy", "capacity": 3, "skills": ["packing"]}],
            "orders": [{"id": "Dock1", "demand": 4, "skill": "forklift"}, {"id": "Dock2", "demand": 3, "skill": "forklift"},
                       {"id": "Line", "demand": 2, "skill": "packing"}]}
LIE = "def solve(req):\n    return {'flows': [], 'value': 0}\ndef _honest(req):"
host = Host()
spec = compiled_question(problem_id="staff-x", data=STAFFING, allow_construction=True)
spec["light_cone"]["capabilities"] += [METHOD]
extra = dict(consequence={"lawful": False}) if MODE == "decline" else {}
spec["success_checks"].append(fitness_check(**extra))
mid = spec["mission_id"]
with Run() as run:
    if MODE == "decline":
        pass
    else:
        host.stall("timeout")     # only cortex worker.py launches stall: the construction's own runner is untouched
    run.sign("MISSION", spec)
    first = []
    for _ in range(6):
        first.append(run.tick(mid))
        if any(c.startswith("composed.") and s == "ATTACHED" for c, s in run.body.registry.state.items()): break
    print("== fault beside", MODE, "| until the construction serves:", first)
    real = network.RUNNERS["networkx.max_flow"]
    network.RUNNERS["networkx.max_flow"] = real.replace("def solve(req):", LIE, 1)      # the engine now lies in service
    states = [run.tick(mid) for _ in range(8)] + [run.tick(mid, step=3700) for _ in range(2)]
    print("  states after the engine starts lying (8 x 31 s, 2 x 3700 s):", states)
    obs = run.events("mission.observed", mid)
    print("  observed:", [(run.offset(o["at"]), o["check_id"], o["passed"], o.get("declined"), o.get("failure_class"), o["detail"][:48]) for o in obs][-16:])
    print("  asks:", [(run.offset(a["created_at"]), a["kind"], a.get("authority_requested")) for a in run.events("decision.requested")])
    print("  withdrawn:", [(run.offset(w["at"]), w["why"][:50]) for w in run.events("decision.withdrawn")])
    print("  repairs:", [(e.payload.get("capability_id") or e.payload.get("replaced"), ) for e in run.body.journal.replay("capability.quarantined")][:4],
          "| constructions:", sorted((c, s) for c, s in run.body.registry.state.items() if c.startswith("composed.")))
    m = run.mission(mid)
    print("  failed:", {k: v[:90] for k, v in m.failed.items()}, "| routing.outcome:", [(o["action_id"], o["verdict"]) for o in run.events("routing.outcome")],
          "| unmet:", [(u["failing_checks"], u.get("unmeasured_checks")) for u in run.events("mission.unmet")])
    print("  status:", m.status, "| blocker:", (m.blocker or {}).get("why"), (m.blocker or {}).get("failing_checks"))
    network.RUNNERS["networkx.max_flow"] = real
