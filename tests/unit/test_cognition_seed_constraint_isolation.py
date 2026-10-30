"""The seed gate's constraint mutant needs a violation no other check refutes.

Kept apart from test_cognition_seed_gates.py, whose bytes are frozen lineage evidence
(MIND-LINEAGE-RECONCILIATION-MAP-2026-10-14.json, greg-data-exposure-ledger.json).
"""
from dataclasses import asdict
from greg.cognition.contracts import ProblemGeometry
from greg.cognition.verification import verify
from greg.cognition.solvers import optimization


def test_verifier_refutes_a_constraint_violation_alone():
    # x breaks x>=3 while the objective (min y), bound and gap stay honest, so only constraint_substitution can refute;
    # test_verifier_refutes_integer_violation's case also fails the bound checks, so it cannot catch that mutant
    d={"variables":{"x":[0,8],"y":[0,8]},"constraints":[{"coefficients":{"x":1},"op":">=","rhs":3}],
       "objective":{"coefficients":{"y":1},"sense":"min"}}
    a=optimization(d,asdict(ProblemGeometry())); assert a["output"]["solver_status"]=="OPTIMAL"
    a["output"]["solution"]["x"]=0
    r=verify("optimization",d,a,"optimization_certificate")
    assert r["verdict"]=="REFUTED" and [k for k,ok in r["checks"].items() if not ok]==["constraint_substitution"]
