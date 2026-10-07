"""P4 conditional competence: GREG learns where each formal engine works, with hierarchical fallback.

Records are settled through the real ``CompetenceLedger`` on real cortex receipts (Z3 / CP-SAT in
this process); the routing memory only ever permutes the eligible engines it is given.
"""
from types import SimpleNamespace

import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from cortex.genome import seed_registry  # noqa: E402
from cortex.memory import CompetenceLedger  # noqa: E402
from cortex.routing import CPSAT, FORMAL, Cortex  # noqa: E402
from greg.cognition.conditional_competence import ConditionalCompetence, conditions, features  # noqa: E402
from greg.cognition.learned_routing import PROVENANCE  # noqa: E402

DECL = {"consequence_class": "read_only", "reversibility": "reversible"}
FEAS = SimpleNamespace(epistemic_class="constraint_feasibility")


def model(variables, constraints, budget=1.0):
    return {"formal_model": {"requirement": "r", "variables": variables, "obligations": [{"id": "R", "text": "t"}],
                             "constraints": [{"id": f"C{i}", "covers": ["R"], "expr": e}
                                             for i, e in enumerate(constraints)]},
            "resources": {"max_latency_s": budget}, "declared": DECL}


def binpack(n=6, bins=2):
    v = [{"name": f"b{i}_{k}", "sort": "int", "lo": 0, "hi": 1} for i in range(n) for k in range(bins)]
    cons = [["=", ["+", *[f"b{i}_{k}" for k in range(bins)]], 1] for i in range(n)]
    cons += [["<=", ["+", *[["*", 5, f"b{i}_{k}"] for i in range(n)]], 15] for k in range(bins)]
    return model(v, cons)


def knapsack(n=6):
    v = [{"name": f"x{i}", "sort": "int", "lo": 0, "hi": 1} for i in range(n)]
    return model(v, [["<=", ["+", *[["*", 3 + i, f"x{i}"] for i in range(n)]], 12],
                     [">=", ["+", *[["*", 2 + i, f"x{i}"] for i in range(n)]], 8]])


def led(payload, lead):
    registry = seed_registry()
    registry.withhold(CPSAT if lead == FORMAL else FORMAL, "founder pin")
    receipt = Cortex(registry, clock=lambda: "2026-10-07T00:00:00Z").run(
        {"problem_id": f"p-{lead}", "question": "q", "payload": payload})
    assert receipt["route"]["selected"] == [lead]
    return receipt


def settle(ledger, payload, lead, status, n):
    receipt, method = led(payload, lead), lead.partition("@")
    for _ in range(n):
        ledger.settle(receipt=receipt, method=method[0], method_version=method[2], outcome_status=status,
                      provenance=PROVENANCE, conditions=conditions(features(payload)),
                      attribution=[{"method": method[0], "role": "final_answer", "uncertainty": "medium"}])


def test_features_separate_the_sub_geometries_that_share_one_epistemic_class():
    a, b = features(binpack()), features(knapsack())
    assert a["kind"] == b["kind"] == "feasibility" and a["domain"] == b["domain"] == "bool"
    assert a["ops"] == "=" and b["ops"] != "="
    assert features({"formal_model": None}) == {}


def test_each_sub_geometry_gets_its_own_order_where_a_class_pool_would_pick_one():
    ledger = CompetenceLedger()
    settle(ledger, binpack(), FORMAL, "observed_failure", 6)       # Z3 times out on tight packing
    settle(ledger, binpack(), CPSAT, "verified_success", 6)
    settle(ledger, knapsack(), FORMAL, "verified_success", 6)      # Z3 decides knapsack feasibility
    settle(ledger, knapsack(), CPSAT, "observed_failure", 6)
    memory = ConditionalCompetence(ledger.records())
    assert memory.bind(features(binpack())).reorder([FORMAL, CPSAT], FEAS) == [CPSAT, FORMAL]
    assert memory.bind(features(knapsack())).reorder([FORMAL, CPSAT], FEAS) == [FORMAL, CPSAT]
    # The class-level ledger sees the pooled class as a tie and keeps the fixed policy for both.
    pooled = CompetenceLedger([r.__class__(**{**r.__dict__, "conditions": ()}) for r in ledger.records()])
    assert pooled.reorder([FORMAL, CPSAT], FEAS) == [FORMAL, CPSAT]


def test_a_sparse_exact_cell_falls_back_to_its_parents():
    ledger = CompetenceLedger()
    settle(ledger, binpack(), FORMAL, "observed_failure", 6)
    settle(ledger, binpack(), CPSAT, "verified_success", 6)
    bigger = binpack(n=40, bins=4)                                 # same kind/ops/domain, other size
    info = ConditionalCompetence(ledger.records()).bind(features(bigger)).explain([FORMAL, CPSAT],
                                                                                  "constraint_feasibility")
    assert info["decision_level"] in ("kind+ops+domain+budget", "kind+ops+domain", "kind+ops", "kind", "class")
    assert ConditionalCompetence(ledger.records()).bind(features(bigger)).reorder([FORMAL, CPSAT], FEAS) == \
        [CPSAT, FORMAL]


def test_memory_only_permutes_what_it_is_given():
    ledger = CompetenceLedger()
    settle(ledger, binpack(), CPSAT, "verified_success", 6)
    memory = ConditionalCompetence(ledger.records()).bind(features(binpack()))
    assert memory.reorder([FORMAL], FEAS) == [FORMAL]               # a detached engine never returns
    assert ConditionalCompetence(ledger.records()).reorder([FORMAL, CPSAT], FEAS) == [FORMAL, CPSAT]  # unbound
    assert ConditionalCompetence([]).bind(features(binpack())).reorder([FORMAL, CPSAT], FEAS) == [FORMAL, CPSAT]
