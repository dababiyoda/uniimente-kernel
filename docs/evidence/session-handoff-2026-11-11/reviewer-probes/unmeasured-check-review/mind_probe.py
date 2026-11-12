"""Probe: a construction that faults through the Mind. Run with cwd = a worktree.
usage: mind_probe.py <scenario> <nticks> [tick_seconds]
scenarios:
  nx_lie        only networkx lies always (the commit's own test)
  all_lie       networkx and scipy lie always (replacement fails qualification)
  instance_lie  both lie only on the mission's instance (replacement qualifies, then faults in service)
"""
import os, sys, tempfile, json
sys.path.insert(0, os.getcwd())
from pathlib import Path
from greg.body import Body
from greg.cognition import network
from greg.templates import compiled_question
from tests.greg_fixtures import Clock, drop, make_body, signed

STAFFING = {"workers": [{"id": "Ana", "capacity": 2, "skills": ["forklift"]},
                        {"id": "Ben", "capacity": 4, "skills": ["packing", "forklift"]},
                        {"id": "Cy", "capacity": 3, "skills": ["packing"]}],
            "orders": [{"id": "Dock1", "demand": 4, "skill": "forklift"},
                       {"id": "Dock2", "demand": 3, "skill": "forklift"},
                       {"id": "Line", "demand": 2, "skill": "packing"}]}
scenario, n = sys.argv[1], int(sys.argv[2])
step = int(sys.argv[3]) if len(sys.argv) > 3 else 31
tmp = Path(tempfile.mkdtemp(prefix="rv-mind-", dir=os.environ["RV_TMP"]))
home, key, body_id, _ = make_body(tmp)
spec = compiled_question(problem_id="staff-x", data=STAFFING, allow_construction=True)
drop(home, signed(key, body_id, "MISSION", spec))
clock = Clock()
ALWAYS = "def solve(req):\n    return {'flows': [], 'value': 0}\ndef _honest(req):"
INSTANCE = ("def solve(req):\n    if any('Dock1' in str(x) for x in req['nodes']):\n        return {'flows': [], 'value': 0}\n"
            "    return _honest(req)\ndef _honest(req):")
with Body(home, clock=clock) as body:
    body.boot()
    first = body.tick()["missions"][0]; clock.advance(step)
    print("tick0", first["state"])
    if scenario == "nx_lie":
        network.RUNNERS["networkx.max_flow"] = network.RUNNERS["networkx.max_flow"].replace("def solve(req):", ALWAYS, 1)
    elif scenario == "all_lie":
        for k in ("networkx.max_flow", "scipy.max_flow"):
            network.RUNNERS[k] = network.RUNNERS[k].replace("def solve(req):", ALWAYS, 1)
    elif scenario == "instance_lie":
        for k in ("networkx.max_flow", "scipy.max_flow"):
            network.RUNNERS[k] = network.RUNNERS[k].replace("def solve(req):", INSTANCE, 1)
    seen_asks = 0
    for i in range(1, n + 1):
        r = body.tick()["missions"][0]
        asks = [e.payload for e in body.journal.replay("decision.requested")]
        new = asks[seen_asks:]; seen_asks = len(asks)
        m = body.engine.book.missions[spec["mission_id"]]
        print(f"tick{i} t+{(i)*step}s state={r['state']}", {k: v for k, v in r.items() if k in ("checks", "until", "replaced", "by", "still_failing")},
              "blocker=" + str((m.blocker or {}).get("type")), "next_observe=" + str(m.next_observe_at)[11:19],
              "NEW_ASKS=" + str([(a["kind"], str(a.get("why") or a.get("question") or sorted(a))[:140]) for a in new]) if new else "")
        clock.advance(step)
    print("asks total:", [(a["kind"]) for a in body.journal.replay("decision.requested") for a in [a.payload]])
    print("withdrawn:", len(list(body.journal.replay("decision.withdrawn"))))
    print("actions:", [(a.payload["action_id"], a.payload["status"], a.payload["attempt"]) for a in body.journal.replay("mission.action")])
    obs = [e.payload for e in body.journal.replay("mission.observed")]
    print("observations:", len(obs)); 
    for o in obs[-3:]:
        print("  obs", o["passed"], o.get("failure_class"), o["capability"], repr(o["detail"][:160]))
    print("cap states:", [(e.payload["capability_id"][-28:], e.payload["state"]) for e in body.journal.replay("capability.state")])
    print("blocked events:", [(e.payload.get("blocker") or {}).get("type") for e in body.journal.replay("mission.blocked")])
    print("unmet:", [e.payload for e in body.journal.replay("mission.unmet")])
