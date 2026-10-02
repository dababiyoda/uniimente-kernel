"""Cortex 0.2.0 — two fault-diverse formal engines behind one contract (directive 7C, 7E, 12, 14).

What must hold:
* CP-SAT and Z3 agree with brute-force ground truth and with each other on the same model;
* FEASIBLE is never reported as OPTIMAL; native statuses are preserved;
* every returned assignment is re-checked against the problem's own source constraints, so a
  lying engine or a forged proof cannot produce a recommendation;
* an engine outage falls back to the other engine; both down yields DEPENDENCY_UNAVAILABLE;
* optional deeper cognition (certificates, confirmations) is logged with its reason, taken or not;
* L1 checks are four-valued; the directive outcome taxonomy is total and schema-valid.
"""
import itertools
from dataclasses import replace

import pytest

z3 = pytest.importorskip("z3")
pytest.importorskip("ortools")

from cortex import outcomes  # noqa: E402
from cortex.contracts import STATES, Expenditure, OrganResult, Problem  # noqa: E402
from cortex.evaluation.build_suites import schedule  # noqa: E402
from cortex.genome import seed_registry  # noqa: E402
from cortex.organs import cpsat as C  # noqa: E402
from cortex.organs import formal_eval  # noqa: E402
from cortex.organs.cpsat import CpSatOrgan  # noqa: E402
from cortex.organs.formal import FormalOrgan, Spec  # noqa: E402
from cortex.routing import CPSAT, FORMAL, Cortex  # noqa: E402
from cortex.schemas import validate  # noqa: E402

CLOCK = lambda: "2026-10-01T00:00:00Z"  # noqa: E731
DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}


def P(model, **payload):
    return Problem.from_dict({"problem_id": "t", "question": "q", "payload": {"formal_model": model, **payload}})


def run_cortex(model, cortex=None, **payload):
    payload.setdefault("declared", DECL)
    r = (cortex or Cortex(clock=CLOCK)).run({"problem_id": "t", "question": "q",
                                             "payload": {"formal_model": model, **payload}})
    validate(r, "cortex-receipt")
    for proof in r["proof_artifacts"]:
        validate(proof, "cortex-proof-artifact")
    return r


CASES = [
    ([("A", 3), ("B", 4), ("C", 2)], 10, []),
    ([("A", 4), ("B", 4), ("C", 3)], 10, []),
    ([("A", 2), ("B", 2), ("C", 2)], 6, [("A", "B"), ("B", "C")]),
    ([("A", 2), ("B", 3)], 4, []),
    ([("A", 1), ("B", 1), ("C", 1), ("D", 2)], 5, [("D", "A")]),
]


class TestParity:
    @pytest.mark.parametrize("jobs, shift, prec", CASES)
    def test_engines_agree_with_ground_truth_on_feasibility(self, jobs, shift, prec):
        model, feasible, _ = schedule(jobs, shift, prec)
        a, b = CpSatOrgan().run(P(model), None, None), FormalOrgan().run(P(model), None, None)
        assert a.state == b.state == "OK"
        assert a.answer["feasible"] is b.answer["feasible"] is feasible
        if feasible:
            for r in (a, b):
                assert formal_eval.check_assignment(Spec(model), r.answer["model"])["holds"]
        else:
            assert a.answer["unsat_core"] and a.proof["solver"]["core_kind"].startswith("sufficient")

    @pytest.mark.parametrize("jobs, shift, prec", [c for c in CASES if schedule(*c)[1]])
    def test_engines_agree_on_the_optimum(self, jobs, shift, prec):
        names = [j for j, _ in jobs]
        objective = ["+", *[f"s_{j}" for j in names]]
        model, _, _ = schedule(jobs, shift, prec, query={"kind": "optimize", "sense": "minimize",
                                                          "objective": objective})
        a, b = CpSatOrgan().run(P(model), None, None), FormalOrgan().run(P(model), None, None)
        dur = dict(jobs)
        best = min(sum(s) for s in itertools.product(range(shift + 1), repeat=len(names))
                   if all(s[i] + dur[n] <= shift for i, n in enumerate(names))
                   and all(s[i] + dur[x] <= s[k] or s[k] + dur[y] <= s[i]
                           for (i, x), (k, y) in itertools.combinations(enumerate(names), 2))
                   and all(s[names.index(q)] >= s[names.index(p)] + dur[p] for p, q in prec))
        assert a.answer["objective"] == b.answer["objective"] == best
        assert a.proof["proof_class"] == "optimization" and a.proof["native_status"] == "OPTIMAL"
        assert b.proof["proof_class"] == "formal" and b.proof["solver"]["certificate_check"] == "UNSAT"

    def test_entailment_parity(self):
        prec = [("A", "B"), ("B", "C")]
        jobs = [("A", 3), ("B", 4), ("C", 2)]
        for prop, expected in (([">=", "s_C", 7], True), (["=", "s_C", 7], False)):
            model, _, _ = schedule(jobs, 10 if expected is False else 9, prec,
                                   query={"kind": "entailment", "property": prop})
            a, b = CpSatOrgan().run(P(model), None, None), FormalOrgan().run(P(model), None, None)
            assert a.answer["entailed"] is b.answer["entailed"] is expected
            if not expected:
                assert formal_eval.evaluate(prop, a.answer["counterexample"], Spec(model).variables) is False


class TestFragmentAndStatuses:
    def test_real_and_unbounded_variables_are_outside_the_fragment(self):
        model, _, _ = schedule([("A", 2)], 4)
        real = dict(model, variables=[{"name": "s_A", "sort": "real", "lo": 0, "hi": 4}])
        unbounded = dict(model, variables=[{"name": "s_A", "sort": "int", "lo": 0}])
        assert any("real-valued" in r for r in C.unsupported(real))
        assert any("unbounded" in r for r in C.unsupported(unbounded))
        product = dict(model, constraints=[{"id": "C1", "covers": ["R_end_A"], "expr": ["<=", ["*", "s_A", "s_A"], 4]},
                                           *model["constraints"][1:]])
        assert any("non-linear" in r for r in C.unsupported(product))
        assert C.unsupported(model) == []

    def test_feasible_is_never_reported_optimal(self, monkeypatch):
        from ortools.sat.python import cp_model
        real_solver = cp_model.CpSolver

        class StoppedEarly(real_solver):
            """Reports FEASIBLE with a looser bound, as a time-limited search does."""
            def solve(self, model, *a, **k):
                status = super().solve(model, *a, **k)
                self._stopped = model.has_objective() and status == cp_model.OPTIMAL
                return cp_model.FEASIBLE if self._stopped else status

            @property
            def best_objective_bound(self):
                bound = real_solver.best_objective_bound.fget(self)
                return bound - 1 if getattr(self, "_stopped", False) else bound

            def status_name(self, status=None):
                return "FEASIBLE" if getattr(self, "_stopped", False) else super().status_name(status)

        monkeypatch.setattr(cp_model, "CpSolver", StoppedEarly)
        model, _, _ = schedule([("A", 2), ("B", 3)], 8, query={"kind": "optimize", "sense": "minimize",
                                                                "objective": ["+", "s_A", "s_B"]})
        r = CpSatOrgan().run(P(model), None, None)
        assert r.state == "INCONCLUSIVE" and r.answer["optimal"] is False and r.answer["gap"] == 1
        assert r.proof["native_status"] == "FEASIBLE" and r.proof["optimality"] == "not proven"


class LyingEngine:
    """Returns an assignment that violates the source model and claims it is optimal."""
    def __init__(self, organ_id=CPSAT, *, optimal_without_proof=False, wrong_objective=False):
        self.organ_id, self.optimal_without_proof, self.wrong_objective = organ_id, optimal_without_proof, \
            wrong_objective

    def run(self, problem, geometry, budget):
        names = [v["name"] for v in problem.payload["formal_model"]["variables"]]
        answer = {"feasible": True, "model": {n: 0 for n in names}}
        proof = {"proof_class": "formal", "scope": "valid_given_encoding", "failure": "forged",
                 "solver": {"status": "SAT"}}
        if self.optimal_without_proof or self.wrong_objective:
            spec = Spec(problem.payload["formal_model"])
            good = CpSatOrgan().run(problem, geometry, budget)
            value = good.answer["objective"] + (7 if self.wrong_objective else 0)
            answer = {"feasible": True, "optimal": True, "sense": spec.query["sense"], "objective": value,
                      "model": good.answer["model"]}
            proof = {"proof_class": "formal", "scope": "valid_given_encoding", "failure": "forged",
                     "solver": {"status": "SAT"}}
        return OrganResult(organ_id=self.organ_id, organ_version="9.9.9", state="OK", answer=answer,
                           proof=proof, expenditure=Expenditure(solver_calls=1), origin="solver",
                           dependencies=("solver:forged",))


def lying_cortex(**kw):
    c = Cortex(clock=CLOCK)
    c.organs[CPSAT] = LyingEngine(**kw)
    c.organs[FORMAL] = LyingEngine(FORMAL, **kw)
    return c


class TestIndependentRecheck:
    def test_a_lying_engine_cannot_produce_a_recommendation(self):
        model, _, _ = schedule([("A", 3), ("B", 4)], 10)
        r = run_cortex(model, lying_cortex())
        kinds = {f["kind"] for f in r["verifier"]["findings"]}
        assert "assignment_violates_source_constraints" in kinds
        assert r["disposition"]["kind"] != "recommend" and r["verifier"]["blocking"] is True

    def test_optimality_without_proof_and_wrong_objective_are_critical(self):
        model, _, _ = schedule([("A", 3), ("B", 4)], 10, query={"kind": "optimize", "sense": "minimize",
                                                                 "objective": ["+", "s_A", "s_B"]})
        r = run_cortex(model, lying_cortex(optimal_without_proof=True))
        assert "optimality_claim_without_proof" in {f["kind"] for f in r["verifier"]["findings"]}
        r = run_cortex(model, lying_cortex(wrong_objective=True))
        assert "objective_mismatch" in {f["kind"] for f in r["verifier"]["findings"]}
        assert r["disposition"]["kind"] != "recommend"

    def test_recheck_reads_the_problem_model_not_the_proof(self):
        # A forged proof that embeds a *different* model cannot vouch for the answer.
        model, _, _ = schedule([("A", 3), ("B", 4)], 10)
        c = lying_cortex()
        r = run_cortex(model, c)
        assert r["proof_artifacts"][0].get("structured_model") is None   # the forgery carried none
        assert r["verifier"]["blocking"] is True


class TestRouting:
    def test_optimization_goes_to_cpsat_and_z3_certifies(self):
        model, _, _ = schedule([("A", 3), ("B", 4), ("C", 2)], 10,
                               query={"kind": "optimize", "sense": "minimize", "objective": ["+", "s_A", "s_B", "s_C"]})
        r = run_cortex(model)
        assert r["route"]["selected"] == [CPSAT] and r["route"]["formal_plan"]["order"] == [CPSAT, FORMAL]
        proof = r["proof_artifacts"][0]
        assert proof["certificate"]["status"] == "CERTIFIED" and proof["certificate"]["engine"] == "z3"
        step = next(d for d in r["budget_controller"]["decisions"] if "certificate" in d["step"])
        assert step["taken"] is True and step["reason"]
        assert r["disposition"]["kind"] == "recommend" and r["outcome"]["outcome"] == "ANSWERED_WITHIN_SCOPE"

    def test_feasibility_goes_to_z3_and_declines_a_redundant_second_engine(self):
        model, _, _ = schedule([("A", 3), ("B", 4)], 10)
        r = run_cortex(model)
        assert r["route"]["selected"] == [FORMAL]
        d = r["budget_controller"]["decisions"]
        assert d and d[-1]["taken"] is False and "verified witness" in d[-1]["reason"]

    def test_z3_outage_falls_back_to_cpsat(self):
        model, _, _ = schedule([("A", 3), ("B", 4)], 10)
        r = run_cortex(model, faults={"solver_available": False})
        assert r["route"]["selected"] == [CPSAT]
        assert any("dependency unavailable" in x for x in r["route"]["formal_plan"]["excluded"][FORMAL])
        assert r["output"]["state"] == "OK" and r["disposition"]["kind"] == "recommend"

    def test_both_engines_down_is_dependency_unavailable_not_no_method(self):
        model, _, _ = schedule([("A", 3), ("B", 4)], 10)
        r = run_cortex(model, faults={"solver_available": False, "cpsat_available": False})
        assert r["output"]["state"] == "DEPENDENCY_UNAVAILABLE" and r["disposition"]["kind"] == "abstain"
        assert r["outcome"] == {"outcome": "ABSTAIN", "reasons": ["CAPABILITY_UNAVAILABLE"],
                                "taxonomy": outcomes.VERSION}

    def test_lead_engine_failure_is_recorded_and_superseded(self):
        model, _, _ = schedule([("A", 3), ("B", 4)], 10)
        c = Cortex(clock=CLOCK)

        class Down:
            organ_id = FORMAL

            def run(self, problem, geometry, budget):
                return OrganResult(organ_id=FORMAL, organ_version="0.2.0", state="TIMEOUT", answer=None,
                                   proof={"proof_class": "formal", "scope": "valid_given_encoding",
                                          "failure": "timeout"}, origin="solver")
        c.organs[FORMAL] = Down()
        r = run_cortex(model, c)
        assert r["route"]["attempts"][0]["organ_id"] == FORMAL and r["route"]["attempts"][0]["state"] == "TIMEOUT"
        assert r["output"]["per_route"][0]["organ_id"] == CPSAT
        assert any(d["step"].startswith("fallback") and d["taken"] for d in r["budget_controller"]["decisions"])

    def test_infeasibility_is_confirmed_by_the_second_engine(self):
        model, feasible, _ = schedule([("A", 4), ("B", 4), ("C", 3)], 10)
        r = run_cortex(model)
        assert feasible is False and r["output"]["answer"]["feasible"] is False
        assert r["proof_artifacts"][0]["confirmed_by"]["engine"] == CPSAT

    def test_engine_disagreement_is_contested_and_never_averaged(self):
        model, _, _ = schedule([("A", 4), ("B", 4), ("C", 3)], 10)
        c = Cortex(clock=CLOCK)

        class Contrarian:
            organ_id = CPSAT

            def run(self, problem, geometry, budget):
                return OrganResult(organ_id=CPSAT, organ_version="0.2.0", state="OK",
                                   answer={"feasible": True, "model": {"s_A": 0, "s_B": 0, "s_C": 0}},
                                   proof={"proof_class": "formal", "scope": "valid_given_encoding",
                                          "failure": "contrarian"}, origin="solver")
        c.organs[CPSAT] = Contrarian()
        r = run_cortex(model, c)
        assert r["output"]["state"] == "CONTESTED" and r["disposition"]["kind"] == "handoff"
        assert "engines_disagree" in {f["kind"] for f in r["verifier"]["findings"]}
        assert "CONTRADICTION" in r["outcome"]["reasons"]

    def test_detached_engine_is_never_selected(self):
        registry = seed_registry()
        key = CPSAT
        profile = registry._profiles[key]
        registry._profiles[key] = replace(profile, enabled=False, lifecycle="QUARANTINED")
        model, _, _ = schedule([("A", 3), ("B", 4)], 10, query={"kind": "optimize", "sense": "minimize",
                                                                 "objective": ["+", "s_A", "s_B"]})
        r = run_cortex(model, Cortex(registry, clock=CLOCK))
        assert r["route"]["selected"] == [FORMAL] and CPSAT in r["route"]["formal_plan"]["excluded"]

    def test_solver_budget_zero_takes_no_optional_step(self):
        model, _, _ = schedule([("A", 3), ("B", 4)], 10, query={"kind": "optimize", "sense": "minimize",
                                                                 "objective": ["+", "s_A", "s_B"]})
        r = run_cortex(model, resources={"max_solver_calls": 0})
        assert r["output"]["state"] == "BUDGET_EXHAUSTED" and r["outcome"]["outcome"] == "WAIT"
        # refused before spending, never after: no engine is invoked, so no engine artifact exists
        assert r["proof_artifacts"] == [] or all(p.get("proof_class") == "verifier_findings"
                                                 for p in r["proof_artifacts"]), r["proof_artifacts"]
        assert r["route"]["attempts"] == [] and r["expenditure"]["solver_calls"] == 0


class TestL1AndOutcomes:
    def test_l1_checks_are_four_valued_and_distinct(self):
        model, _, _ = schedule([("A", 3)], 10)
        r = run_cortex(model)
        values = {c["check"]: c["value"] for c in r["l1_checks"]}
        assert values["evidence_fresh"] == "not_applicable" and values["schema_valid"] == "pass"
        assert values["budget_declared"] == "unknown"
        assert set(values.values()) <= {"pass", "fail", "unknown", "not_applicable"}
        stale = {"id": "E1", "stance": "supports", "kind": "measurement", "validation_status": "externally_verified",
                 "observed_at": "2026-01-01", "max_age_days": 30, "source": "s"}
        r = run_cortex(model, evidence=[stale], as_of="2026-09-30")
        assert {c["check"]: c["value"] for c in r["l1_checks"]}["evidence_fresh"] == "fail"

    @pytest.mark.parametrize("state", STATES)
    @pytest.mark.parametrize("disposition", ["recommend", "abstain", "bounded_test", "handoff"])
    def test_taxonomy_is_total(self, state, disposition):
        for answer in (True, False):
            out = outcomes.classify_cortex(state, disposition, answer_present=answer)
            assert out["outcome"] in outcomes.OUTCOMES and set(out["reasons"]) <= set(outcomes.REASONS)

    def test_greg_abstention_states_all_map(self):
        from greg.cortex_engines.contracts import AbstentionClass
        for state in AbstentionClass:
            out = outcomes.classify_greg(state.value, has_output=False)
            assert out["outcome"] in outcomes.OUTCOMES and set(out["reasons"]) <= set(outcomes.REASONS)


class TestLatencyBudget:
    """Selection-split finding (crossgeo v0.2): with a 50 ms budget the Z3 organ still spent ~5 s
    because every diagnostic solve took a fresh timeout, and adding CP-SAT pushed the GREG worker
    past its CPU limit (SIGXCPU, a task failure). Every solve now draws on one deadline."""

    @staticmethod
    def pigeonhole(holes=12, budget=0.05):
        return {"problem_id": "t:budget", "question": "Distinct bays?", "payload": {
            "formal_model": {"requirement": f"{holes + 1} crews, {holes} bays, one crew per bay.",
                             "variables": [{"name": f"p{k}", "sort": "int", "lo": 1, "hi": holes}
                                           for k in range(holes + 1)],
                             "obligations": [{"id": "R", "text": "distinct bays"}],
                             "constraints": [{"id": f"C{a}_{b}", "covers": ["R"], "expr": ["!=", f"p{a}", f"p{b}"]}
                                             for a, b in __import__("itertools").combinations(range(holes + 1), 2)]},
            "resources": {"max_latency_s": budget},
            "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}}

    def test_the_cortex_stays_near_its_declared_latency(self):
        import time
        started = time.perf_counter()
        receipt = Cortex(clock=lambda: "2026-10-01T00:00:00Z").run(self.pigeonhole())
        elapsed = time.perf_counter() - started
        assert elapsed < 1.5, elapsed
        answer = receipt["output"]["answer"]
        assert receipt["disposition"]["kind"] != "recommend" or (answer or {}).get("feasible") is False
        skipped = [c for p in receipt["proof_artifacts"] for c in p.get("counterexample_search", [])
                   if c["result"] == "skipped: latency budget"]
        assert skipped, "diagnostics must yield to the budget"

    def test_the_greg_worker_is_never_killed_by_a_tight_budget(self):
        from greg.cortex_bridge import run
        p = self.pigeonhole()
        r = run({"dialect": "cortex", **p})
        assert r["cortex_receipt"]["schema"].startswith("cortex-receipt/")
        assert r["cortex_receipt"]["outcome"]["outcome"] in ("WAIT", "ABSTAIN", "ANSWERED_WITHIN_SCOPE")


class TestMisclassifiedConsequence:
    """crossgeo v0.2 hard failure (ADV-misclassified_high_consequence): a problem declared
    internal_write whose declared harm vector says high financial harm was recommended. From
    v0.2.1 the harm vector may raise the consequence class, never lower it."""

    @staticmethod
    def problem(harm):
        model, _, _ = schedule([("A", 3), ("B", 4)], 10)
        return {"problem_id": "t:misclassified", "question": "Feasible? (releases a payment automatically)",
                "payload": {"formal_model": model, "declared": {"consequence_class": "internal_write",
                                                                "reversibility": "reversible", "harm": harm}}}

    @pytest.mark.parametrize("harm", [{"financial": "high"}, {"financial": "critical"}, {"physical": "high"},
                                      {"rights": "high"}, {"irreversible_disclosure": "high"},
                                      {"privacy": "critical"}])
    def test_declared_harm_raises_the_consequence_and_forces_handoff(self, harm):
        r = Cortex(clock=lambda: "2026-10-01T00:00:00Z").run(self.problem(harm))
        assert r["disposition"]["kind"] == "handoff", r["disposition"]
        assert r["geometry"]["consequence_class"] == "financial"
        assert r["geometry"]["provenance"]["consequence_class"]["source"] == "raised_by_declared_harm"
        assert any(x["field"] == "consequence_class" and x["value"] == "internal_write"
                   for x in r["geometry"]["rejected_proposals"]), "the understated declaration is kept"
        assert "AUTHORITY_REQUIRED" in r["outcome"]["reasons"]

    def test_low_or_soft_harm_never_raises_and_never_lowers(self):
        r = Cortex(clock=lambda: "2026-10-01T00:00:00Z").run(self.problem({"privacy": "high", "financial": "low"}))
        assert r["geometry"]["consequence_class"] == "internal_write" and r["disposition"]["kind"] == "recommend"
        p = self.problem({"financial": "none"})
        p["payload"]["declared"]["consequence_class"] = "irreversible"
        r = Cortex(clock=lambda: "2026-10-01T00:00:00Z").run(p)
        assert r["geometry"]["consequence_class"] == "irreversible" and r["disposition"]["kind"] == "handoff"
