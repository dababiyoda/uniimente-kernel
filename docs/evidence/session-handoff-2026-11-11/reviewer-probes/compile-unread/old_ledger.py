"""Phase 1 (cwd = base tree): old_ledger.py write <dir>   -> a body whose ledger holds 0.2 compile receipts.
   Phase 2 (cwd = head tree): old_ledger.py read <dir>    -> the same body opened by this tree."""
import sys, json, pickle
from rcu_common import *
from greg.founder import load_founder_key
from greg.missions import unanswered
from greg.cognition import settlement
MODE, D = sys.argv[1], Path(sys.argv[2])
def solve_strategy(aid="compile"):
    return {"action_id": aid, "capability": "cognition.solve", "target": "cognition:bb", "params": compile_params(), "advances": ["good"], "rationale": "compile"}
def dump(body, clock0):
    j = body.journal
    ev = lambda k: [e.payload for e in j.replay(k)]
    for mid in ("m:answered", "m:stalled", "m:stalledq"):
        m = body.engine.book.missions[mid]
        print(f"  {mid}: status={m.status} blocker={(m.blocker or {}).get('why')} failing={(m.blocker or {}).get('failing_checks')} failed={ {k: v[:70] for k, v in m.failed.items()} }")
        print("     observed:", [(o["passed"], o.get("declined"), o.get("failure_class"), o["detail"][:45], (j.ledger.find(o["receipt"]).payload["result"]["output"] or {}).get("schema", "")[-3:]) for o in ev("mission.observed") if o["mission_id"] == mid])
    print("  asks:", [(a["mission_id"], a["kind"]) for a in ev("decision.requested")], "withdrawn:", [(w["mission_id"], w["why"][:50]) for w in ev("decision.withdrawn")])
    print("  unmet:", [(u["mission_id"], u["failing_checks"], u.get("unmeasured_checks")) for u in ev("mission.unmet")])
    print("  appraised:", [(a["mission_id"], a["verdict"], [f[:100] for f in a.get("findings") or []][:2]) for a in ev("mission.appraised")])
    print("  routing.outcome:", [(o["mission_id"], o["action_id"], o["verdict"]) for o in ev("routing.outcome")])
    outs = [r.payload["result"]["output"] for r in j.ledger.by_type("receipt") if isinstance((r.payload.get("result") or {}).get("output"), dict) and str(r.payload["result"]["output"].get("schema", "")).startswith("greg-competency")]
    print("  compile receipts on the ledger [schema, state, unanswered(), settlement._compiled is not None]:",
          [(o["schema"][-3:], o["state"], unanswered(o), settlement._compiled(o, states=("ANSWERED", "UNKNOWN", "ABSTAIN")) is not None) for o in outs])
    try:
        print("  settlement.decisions_to_recheck:", len(settlement.decisions_to_recheck(j)))
    except Exception as e:
        print("  decisions_to_recheck raised", type(e).__name__, e)
host = Host()
if MODE == "write":
    D.mkdir(parents=True, exist_ok=True)
    home, key, body_id, data = make_body(D)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        sign = lambda kind, payload: body.apply(signed(key, body_id, kind, payload))
        sign("CAPABILITY_ATTACH", {"capability_id": METHOD})
        sign("MISSION", question("m:answered", fitness_check(problem="real:a"), strategies=[]))
        body.tick(); clock.advance(31); body.tick(); clock.advance(31)
        host.stall("timeout")
        sign("MISSION", question("m:stalled", fitness_check(problem="real:s"), strategies=[solve_strategy()]))
        sign("MISSION", question("m:stalledq", fitness_check(problem="real:t")))
        for _ in range(4):
            body.tick(); clock.advance(31)
        print("written by", Path(".").resolve().name); dump(body, None)
    (D / "state.json").write_text(json.dumps({"home": str(home), "body_id": body_id, "now": clock().isoformat()}))
else:
    st = json.loads((D / "state.json").read_text())
    key = load_founder_key(D / "founder.pem", None)
    clock = Clock(datetime.fromisoformat(st["now"]))
    with Body(Path(st["home"]), clock=clock) as body:
        body.boot()
        print("opened by", Path(".").resolve().name, "(host still stalled)")
        host.stall("timeout")
        states = []
        for step in (31, 31, 3700, 3700):
            states.append([(r.get("mission_id"), r["state"]) for r in body.tick()["missions"]]); clock.advance(step)
        print("  ticks:", states); dump(body, None)
        host.recover()
        states = []
        for step in (3700, 31, 31):
            states.append([(r.get("mission_id"), r["state"]) for r in body.tick()["missions"]]); clock.advance(step)
        print("  after the host recovers:", states); dump(body, None)
