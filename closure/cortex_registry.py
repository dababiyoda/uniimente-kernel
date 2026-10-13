"""Five-closure extension for the Polyintelligence Cortex seed (cortex 0.1.6).

Registered through ``closure/integration_registry.py`` so verifier V3 and
``tests/unit/test_closure.py`` cover the seed like every other organ. The checks
run the real cortex on fixed problems; they grant nothing.
"""
from __future__ import annotations

from closure.framework import ClosureRegistry, ModuleClosures

FORMAL = {"problem_id": "closure-formal", "question": "Is the pair schedulable?", "payload": {
    "formal_model": {"requirement": "x + y <= 4",
                     "variables": [{"name": "x", "sort": "int", "lo": 0, "hi": 4},
                                   {"name": "y", "sort": "int", "lo": 0, "hi": 4}],
                     "obligations": [{"id": "R1", "text": "x + y at most 4"}],
                     "constraints": [{"id": "C1", "covers": ["R1"], "expr": ["<=", ["+", "x", "y"], 4]}]},
    "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}}
EMPTY = {"problem_id": "closure-empty", "question": "What should we do?", "payload": {
    "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}}
HARMFUL = {"problem_id": "closure-harm", "question": "Is the pair schedulable?", "payload": {
    **FORMAL["payload"], "declared": {"consequence_class": "internal_write", "reversibility": "reversible",
                                      "harm": {"physical": "high"}}}}


def _cortex():
    from cortex.routing import Cortex
    return Cortex(clock=lambda: "2026-10-13T00:00:00Z")


def register_cortex_closures(registry: ClosureRegistry) -> ClosureRegistry:
    def technical():
        try:
            import z3  # noqa: F401
        except ModuleNotFoundError:
            r = _cortex().run(FORMAL)
            return (r["output"]["state"] == "DEPENDENCY_UNAVAILABLE" and r["disposition"]["kind"] == "abstain",
                    "solver absent: the formal route abstains with DEPENDENCY_UNAVAILABLE instead of guessing")
        r = _cortex().run(FORMAL)
        a = _cortex().run(EMPTY)
        return (r["output"]["state"] == "OK" and r["disposition"]["kind"] == "recommend"
                and r["output"]["answer"].get("feasible") is True and r["coverage"] == "complete"
                and a["disposition"]["kind"] == "abstain",
                "geometry routes a formal payload to the solver and abstains on an empty one")

    def authority():
        from cortex.schemas import validate
        r = _cortex().run(FORMAL)
        validate(r, "cortex-receipt")
        h = _cortex().run(HARMFUL)
        src = open(__import__("cortex.routing", fromlist=["x"]).__file__, encoding="utf-8").read()
        return (r["authority_created"] is False and r["execution_authority"] == "none"
                and h["disposition"]["kind"] == "handoff" and h["geometry"]["consequence_class"] == "financial"
                and "consequence_gate" not in src and "adapters" not in src.split('"""', 2)[-1],
                "receipts create no authority; declared harm raises the consequence class and hands off; "
                "the router imports no gate or adapter")

    def evidence():
        from cortex.contracts import digest
        r1, r2 = _cortex().run(FORMAL), _cortex().run(FORMAL)
        body = dict(r1); rid = body.pop("receipt_id")

        def stable(v):   # measured expenditure (seconds, per route too) differs between runs by design
            if isinstance(v, dict):
                return {k: stable(x) for k, x in v.items() if k not in ("receipt_id", "expenditure", "seconds")}
            if isinstance(v, list):
                return [stable(x) for x in v]
            return v
        return (bool(stable(r1) == stable(r2) and digest(body) == rid
                     and r1["accountability"]["falsification_conditions"]
                     and r1["route"]["part_geometries"] and r1["outcome_link"]["memory_keys"]),
                "receipts are content-addressed, deterministic apart from measured expenditure, and carry "
                "falsifiers and per-part memory keys")

    def economic():
        from cortex.contracts import ResourceLimits
        tight = {**FORMAL, "problem_id": "closure-budget",
                 "payload": {**FORMAL["payload"], "resources": {"max_solver_calls": 0}}}
        r = _cortex().run(tight)
        full = _cortex().run(FORMAL)
        return (r["output"]["state"] == "BUDGET_EXHAUSTED" and r["expenditure"]["solver_calls"] == 0
                and full["expenditure"]["usd"] <= ResourceLimits().max_cost_usd,
                "budget is refused before spending; a run stays inside the declared cost ceiling")

    def regenerative():
        from cortex.memory import CompetenceLedger
        r = _cortex().run(FORMAL)
        ledger = CompetenceLedger()
        key = r["route"]["selected"][0]
        method, version = key.split("@")
        try:
            ledger.settle(receipt=r, method=method, method_version="0.0.0", outcome_status="verified_success",
                          provenance={"kind": "external_observation", "validation_status": "externally_verified"},
                          attribution=[{"method": method, "role": "final_answer", "uncertainty": "low"}])
            wrong_version_refused = False
        except ValueError:
            wrong_version_refused = True
        try:
            ledger.settle(receipt=r, method=method, method_version=version, outcome_status="verified_success",
                          provenance={"kind": "prediction", "validation_status": "externally_verified"},
                          attribution=[{"method": method, "role": "final_answer", "uncertainty": "low"}])
            prediction_refused = False
        except ValueError:
            prediction_refused = True
        head = ledger.head
        ledger.settle(receipt=r, method=method, method_version=version, outcome_status="verified_success",
                      provenance={"kind": "external_observation", "validation_status": "externally_verified"},
                      attribution=[{"method": method, "role": "final_answer", "uncertainty": "low"}])
        return (wrong_version_refused and prediction_refused and ledger.records()
                and ledger.rollback(head).records() == [],
                "competence settles only on verified outcomes for the exact method that ran, and rolls back")

    registry.register(ModuleClosures("cortex", {
        "technical": technical, "authority": authority, "evidence": evidence,
        "economic": economic, "regenerative": regenerative,
    }))
    return registry
