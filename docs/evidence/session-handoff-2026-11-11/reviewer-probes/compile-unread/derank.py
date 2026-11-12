import sys
from rcu_common import *
from greg.routing import observation_competence
with Run() as run:
    run.sign("MISSION", question("m:nbr", fitness_check(consequence={"lawful": False})))
    run.tick("m:nbr")
    print("  after one PROHIBITED reading: observation_competence =", observation_competence(run.body.journal))
