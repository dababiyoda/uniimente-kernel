"""usage (cwd = tree): neighbours.py <scenario>"""
import sys
from rcu_common import *
SC = sys.argv[1]
host = Host()
DECLINES = {
    "prohibited": dict(consequence={"lawful": False}),
    "human": dict(geometry={"geometry": "optimization", "human_judgment_required": True}),
    "formal_incomplete": dict(geometry={"geometry": "optimization", "consequence_class": "financial"}),
    "budget": dict(geometry={"geometry": "optimization", "latency_budget": 0.01}),
}
def run_ticks(run, mid, n=10, slow=4):
    states = [run.tick(mid) for _ in range(n)]
    slow_states = [run.tick(mid, step=3700) for _ in range(slow)]
    print("  states(31s):", states); print("  states(3700s):", slow_states)
    run.report(mid)

def solve_strategy(aid="compile", problem="real:q", advances=("good",), **extra):
    return {"action_id": aid, "capability": "cognition.solve", "target": "cognition:bb", "params": compile_params(problem, **extra),
            "advances": list(advances), "rationale": "compile"}

print("==", SC)
if SC in ("fail_beside_stall_strategy", "fail_beside_stall_nostrategy", "fail_beside_decline_strategy", "fail_beside_decline_nostrategy"):
    attach = (METHOD,)
    with Run(attach=attach) as run:
        note = run.data / "note.txt"; note.write_text("nothing yet")
        extra = DECLINES["prohibited"] if "decline" in SC else {}
        if "stall" in SC: host.stall("timeout")
        strategies = [write_strategy("write", "out.txt", "hello", ["note"])] if SC.endswith("_strategy") else []
        # the note check reads a file the strategy does NOT write: a real failure that persists
        spec = question("m:nbr", note_check("note", note, "hello"), fitness_check(**extra), strategies=strategies,
                        capabilities=("cognition.solve", "fs.read", "fs.write"), targets=("cognition:*", "fs:*", "workspace:*"), ceiling="internal_write")
        run.sign("MISSION", spec)
        run_ticks(run, "m:nbr")
elif SC == "refused_beside_stall":
    with Run() as run:
        host.stall("timeout")
        outside = Path("/etc/hostname-not-in-roots")
        spec = question("m:nbr", note_check("note", outside, "hello"), fitness_check(),
                        capabilities=("cognition.solve", "fs.read"), targets=("cognition:*", "fs:*"))
        run.sign("MISSION", spec)
        run_ticks(run, "m:nbr")
elif SC.startswith("retry_answers"):
    with Run() as run:
        host.stall("timeout")
        strategies = [solve_strategy()] if SC.endswith("strategy") else []
        run.sign("MISSION", question("m:nbr", fitness_check(), strategies=strategies))
        s = [run.tick("m:nbr")]
        host.recover()
        print("  first:", s)
        run_ticks(run, "m:nbr", n=6, slow=2)
elif SC.startswith("decline_"):
    _, kind, strat = SC.split("_", 2) if SC.count("_") >= 2 else (*SC.split("_"), "sensor")
    kind = {"formal": "formal_incomplete"}.get(kind, kind)
    attach = () if kind == "deficit" else (METHOD,)
    extra = DECLINES.get(kind, {})
    with Run(attach=attach) as run:
        strategies = [solve_strategy(**extra)] if strat == "strategy" else []
        run.sign("MISSION", question("m:nbr", fitness_check(**extra), strategies=strategies))
        run_ticks(run, "m:nbr", n=10, slow=4)
        o = run.events("mission.observed", "m:nbr")[0]
        out = run.output(o)
        print("  first reading:", {k: str(out.get(k))[:100] for k in ("schema", "state", "host_stop", "abstentions")})
