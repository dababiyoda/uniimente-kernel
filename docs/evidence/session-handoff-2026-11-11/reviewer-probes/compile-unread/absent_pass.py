"""A check an empty receipt satisfies ("no counterexample in the result"), read while the host stops the solver. cwd = tree."""
import sys
from rcu_common import *
host = Host()
for label, pred in (("absent result.counterexample", {"op": "absent", "field": "result.counterexample"}),
                    ("state != ANSWERED-style: equals result None", {"op": "equals", "field": "result", "value": None})):
    with Run() as run:
        host.stall("timeout")
        check = {"check_id": "good", "description": "the claim has no counterexample",
                 "sensor": {"capability": "cognition.solve", "target": "cognition:bb", "params": compile_params()}, "predicate": pred}
        try:
            run.sign("MISSION", question("m:nbr", check))
        except Exception as e:
            print("==", label, "refused at signing:", str(e)[:120]); continue
        states = [run.tick("m:nbr") for _ in range(3)]
        obs = run.events("mission.observed", "m:nbr")
        out = run.output(obs[0])
        print("==", label, "| states:", states, "| observed:", [(o["passed"], o["detail"][:50]) for o in obs],
              "| reading: state", out["state"], "result", out["result"], "host_stop", out.get("host_stop", "<no key>"),
              "| status:", run.mission("m:nbr").status, "| appraised:", [(a["verdict"], a.get("findings")) for a in run.events("mission.appraised")])
    host.recover()
