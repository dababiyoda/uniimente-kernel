"""Probe 2: a construction that faults through the Mind, in mission shapes around it. cwd = a worktree.
usage: mind_probe2.py <scenario> <nticks> [tick_seconds]
"""
import os, sys, tempfile, json
sys.path.insert(0, os.getcwd())
from pathlib import Path
from greg.body import Body
from greg.capabilities import CapabilityError
from greg.cognition import network
from greg.templates import compiled_question
from tests.greg_fixtures import Clock, drop, make_body, signed, note_check, write_strategy

STAFFING = {"workers": [{"id": "Ana", "capacity": 2, "skills": ["forklift"]},
                        {"id": "Ben", "capacity": 4, "skills": ["packing", "forklift"]},
                        {"id": "Cy", "capacity": 3, "skills": ["packing"]}],
            "orders": [{"id": "Dock1", "demand": 4, "skill": "forklift"},
                       {"id": "Dock2", "demand": 3, "skill": "forklift"},
                       {"id": "Line", "demand": 2, "skill": "packing"}]}
scenario, n = sys.argv[1], int(sys.argv[2])
step = int(sys.argv[3]) if len(sys.argv) > 3 else 31
tmp = Path(tempfile.mkdtemp(prefix="rv-mind2-", dir=os.environ["RV_TMP"]))
home, key, body_id, data = make_body(tmp)
spec = compiled_question(problem_id="staff-y", data=STAFFING, allow_construction=True)
MID = spec["mission_id"]
cone = spec["light_cone"]
def widen():
    cone["capabilities"] += ["fs.read", "fs.write"]; cone["targets"] += ["fs:*", "workspace:*"]
    cone["max_consequence_class"] = "internal_write"
status = data / "status.txt"; status.write_text("shipped")
outside = tmp / "outside.txt"; outside.write_text("x")
if scenario in ("beside_real", "beside_real_nostrategy"):
    widen()
    spec["success_checks"].append(note_check("status", status, "shipped"))
    if scenario == "beside_real":
        spec["strategies"].append(write_strategy("nudge", "nudge.txt", "nudged", ["status"]))
elif scenario == "beside_refused":
    widen()
    spec["success_checks"].append(note_check("r", outside, "y"))
    spec["strategies"].append(write_strategy("maker", "r.txt", "y", ["r"]))
elif scenario == "beside_refused2":
    widen()
    rfile = data / "r.txt"; rfile.write_text("y")
    spec["success_checks"].append(note_check("r", rfile, "y"))
    spec["strategies"].append(write_strategy("maker", "r.txt", "y", ["r"]))
elif scenario == "beside_refused_curable":
    widen()
    from tests.greg_fixtures import workspace
    wfile = workspace(home, MID) / "r.txt"
    spec["success_checks"].append(note_check("r", wfile, "y"))
    spec["strategies"].append(write_strategy("maker", "r.txt", "y", ["r"]))
elif scenario == "trunc":
    # a signed check that names the whole expected answer; its judged detail is long
    spec["success_checks"][0]["predicate"] = {"op": "equals", "field": "abstentions", "value": []}
    spec["success_checks"].append({"check_id": "answered2", "description": "x", "sensor": spec["success_checks"][0]["sensor"],
                                   "predicate": {"op": "equals", "field": "state", "value": "ANSWERED"}})
elif scenario == "longcheck":
    want = sys.argv[4] if len(sys.argv) > 4 else "state"
    spec["success_checks"][0]["predicate"] = {"op": "contains", "field": "assumptions", "value": "the declared geometry is honest and every worker listed is available for the whole shift named in the order book, " * 3}
drop(home, signed(key, body_id, "MISSION", spec))
clock = Clock()
ALWAYS = "def solve(req):\n    return {'flows': [], 'value': 0}\ndef _honest(req):"
with Body(home, clock=clock) as body:
    body.boot()
    out = body.tick()
    if not out["missions"]:
        print("NO MISSION", out["commands"]); raise SystemExit(2)
    print("tick0", out["missions"][0]["state"]); clock.advance(step)
    for j in range(4):
        if any(c.startswith("composed.") and st == "ATTACHED" for c, st in body.registry.state.items()):
            break
        print("warm", j, body.tick()["missions"][0]["state"]); clock.advance(step)
    if scenario == "achieve_first":
        pass
    if scenario == "alternate":
        calls = {"n": 0}
        for cid in [c for c in body.registry.adapters if c.startswith("composed.")]:
            def flaky(params, ctx, _cid=cid):
                calls["n"] += 1
                if calls["n"] % 2 == 1:
                    raise CapabilityError(f"capability refused: composed engine acquired.graph.max_flow.networkx faulted: package output failed its certificate")
                raise CapabilityError("capability refused: the runner did not finish within 30s", failure_class="transient")
            body.registry.adapters[cid] = flaky
    else:
        network.RUNNERS["networkx.max_flow"] = network.RUNNERS["networkx.max_flow"].replace("def solve(req):", ALWAYS, 1)
    if scenario.startswith("beside_real"):
        status.write_text("not yet")
    if scenario == "beside_refused_curable":
        print("r.txt before:", repr(wfile.read_text()[:20]))
        wfile.write_text("z" * (300 * 1024))   # someone grew the file past the read ceiling: the read is refused
    if scenario == "beside_refused2":
        rfile.unlink(); rfile.mkdir()          # the read is now refused: not a regular file
    seen = 0
    for i in range(1, n + 1):
        r = body.tick()["missions"][0]
        asks = [e.payload for e in body.journal.replay("decision.requested")]
        new = asks[seen:]; seen = len(asks)
        m = body.engine.book.missions[MID]
        print(f"tick{i} t+{i*step}s state={r['state']}", {k: v for k, v in r.items() if k in ("checks", "action", "replaced", "still_failing", "still_unread")},
              "blocker=" + str((m.blocker or {}).get("type")), "failed=" + str({k: v[:60] for k, v in m.failed.items()}),
              ("NEW_ASKS=" + str([(a["kind"], json.dumps({k: a.get(k) for k in ("why_now", "reason", "summary", "evidence")}, default=str)[:420]) for a in new])) if new else "")
        clock.advance(step)
    ev = lambda k: [e.payload for e in body.journal.replay(k)]
    print("asks total:", [a["kind"] for a in ev("decision.requested")], "withdrawn:", len(ev("decision.withdrawn")))
    print("actions:", [(a["action_id"], a["status"], a["attempt"]) for a in ev("mission.action")])
    obs = ev("mission.observed")
    print("observations:", len(obs))
    for o in obs[-4:]:
        print("  obs", o["check_id"], o["passed"], o.get("failure_class"), len(o["detail"]), repr(o["detail"][:330]))
    print("cap states:", [(s["capability_id"][-28:], s["state"]) for s in ev("capability.state")])
    if scenario == "beside_refused_curable":
        print("r.txt size now:", wfile.stat().st_size)
    print("unmet:", [(u["failing_checks"], u.get("unmeasured_checks")) for u in ev("mission.unmet")])
    print("appraised:", [(a.get("verdict"), a.get("findings")) for a in ev("mission.appraised")])
    print("routing.outcome:", [(o["action_id"], o["capability"], o["verdict"], o["reason"][:90]) for o in ev("routing.outcome")])
    if scenario == "dump":
        recs = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt") if isinstance(r.payload["result"].get("output"), dict)
                and str(r.payload["result"]["output"].get("schema", "")).startswith("greg-competency-compilation/")]
        for k, v in recs[-1].items():
            print("   ", k, "=", repr(v)[:230])
