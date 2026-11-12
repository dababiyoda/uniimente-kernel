"""A real failure, its strategy runs, then the host stalls at the re-observation; then the host recovers. cwd = tree."""
import sys
from rcu_common import *
host = Host()
with Run() as run:
    check = fitness_check(value=1e-9)              # the answer's fitness is 0.0204: a measured failure
    strat = {"action_id": "compile", "capability": "cognition.solve", "target": "cognition:bb", "params": compile_params(), "advances": ["good"], "rationale": "compile"}
    run.sign("MISSION", question("m:nbr", check, strategies=[strat]))
    print("  tick1 (host up):", run.tick("m:nbr"))
    host.stall("timeout")
    st = [run.tick("m:nbr") for _ in range(3)]
    print("  3 ticks stalled:", st, "| failed:", dict(run.mission("m:nbr").failed), "| routing:", [(o["action_id"], o["verdict"]) for o in run.events("routing.outcome")])
    host.recover()
    st = [run.tick("m:nbr") for _ in range(4)]
    print("  4 ticks recovered:", st)
    run.report("m:nbr")
    from greg.routing import observation_competence
    print("  observation_competence:", observation_competence(run.body.journal))
