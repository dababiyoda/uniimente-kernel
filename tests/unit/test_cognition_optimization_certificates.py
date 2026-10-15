"""Optimisation and formal verifier certificates (independent review of 2026-10-15, verifier lane V1-V7).

The verifier's own bound check is self-consistency of one untrusted answer: an optimality or infeasibility claim is
certified only by a different engine (Z3 against CP-SAT) finding no strictly better, or no feasible, assignment.
Every forgery here is injected into an honest answer; the canonical-path cases forge only the solver worker's output,
and the real verifier still runs in its own worker."""
import copy

import pytest

pytest.importorskip("ortools")
pytest.importorskip("z3")

from cortex.evaluation.composition_lift import run_v2 as R  # noqa: E402
from greg.cognition import cortex, verification  # noqa: E402
from greg.cognition.catalog import FAMILIES  # noqa: E402
from greg.cognition.contracts import CognitionError  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402
from greg.cognition.genomes import flow, library  # noqa: E402
from greg.cognition.genomes.contract import GenomeError  # noqa: E402
from greg.cognition.solvers import SOLVERS  # noqa: E402
from greg.cognition.verification import verify  # noqa: E402

OPT, FORMAL = FAMILIES["optimization"][3], FAMILIES["formal"][3]
SMALL = {"variables": {"x": [0, 5], "y": [0, 5]},
         "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": "<=", "rhs": 4}],
         "objective": {"coefficients": {"x": 1, "y": 1}, "sense": "max"}}
# x in [0, 100000], y in [0, 100], max 1e6 x + y: the optimum 100000000100 is near 1e11, where rel_tol=1e-9 is 100 units
BIG = {"variables": {"x": [0, 100000], "y": [0, 100]}, "constraints": [],
       "objective": {"coefficients": {"x": 1000000, "y": 1}, "sense": "max"}}
MIN = {"variables": {"x": [0, 9], "y": [0, 9]},
       "constraints": [{"coefficients": {"x": 1, "y": 1}, "op": ">=", "rhs": 4}],
       "objective": {"coefficients": {"x": 2, "y": 3}, "sense": "min"}}


def solve(data):
    return SOLVERS["optimization"](data, {"latency_limit": 10})


def failed(result):
    return sorted(k for k, ok in result["checks"].items() if not ok)


def plan(answer, solution, objective, **proof):
    forged = copy.deepcopy(answer)
    forged["output"].update(solution=solution, objective_value=objective)
    forged["proof"].update(solution=solution, **proof)
    return forged


@pytest.fixture
def registry():
    r = registry_view()
    for cid in R.EVAL_ATTACH:
        r.set_state(cid, "ATTACHED")
    return r


def forge_worker(monkeypatch, change):
    """Rewrite one solver-worker answer at the cortex boundary; the real verifier worker still judges it."""
    real = cortex._numeric

    def forged(family, data, geometry):
        answer = real(family, data, geometry)
        return change(family, data, copy.deepcopy(answer)) or answer
    monkeypatch.setattr(cortex, "_numeric", forged)


def test_a_plan_100_units_short_of_an_optimum_near_1e11_is_refuted():
    """V1: with rel_tol=1e-9 both forgeries verified; the family is integer, so the reported objective and bound must
    round to the solution's exact objective."""
    honest = solve(BIG)
    assert honest["output"]["objective_value"] == 100000000100.0
    assert verify("optimization", BIG, honest, OPT)["verdict"] == "STRUCTURALLY_VERIFIED"
    short = plan(honest, {"x": 100000, "y": 0}, 100000000000.0)          # the honest bound kept
    assert "optimal_objective_meets_its_bound" in failed(verify("optimization", BIG, short, OPT))
    claims = plan(honest, {"x": 100000, "y": 0}, 100000000100.0)         # objective_value claims the optimum
    assert "objective_substitution" in failed(verify("optimization", BIG, claims, OPT))
    one_short = plan(honest, {"x": 100000, "y": 99}, 100000000100.0)     # one unit is enough
    assert "objective_substitution" in failed(verify("optimization", BIG, one_short, OPT))


def test_cp_sat_rounding_noise_in_an_honest_integer_objective_is_not_a_refutation():
    """Review seed 3082: CP-SAT reported -172467568588.00003 for the integer optimum -172467568588; exact equality
    would refute this honest answer."""
    data = {"variables": {"x0": [797468, 858069], "x1": [-990161, 362846], "x2": [-970030, -953616],
                          "x3": [-973731, -969755], "x4": [-941285, 258128], "x5": [-873899, -368058]},
            "constraints": [{"coefficients": {"x1": 560043}, "op": ">=", "rhs": -906120},
                            {"coefficients": {"x3": -10125, "x1": -366480, "x5": -556536, "x0": -817863,
                                              "x4": -643645}, "op": "==", "rhs": 332990}],
            "objective": {"coefficients": {"x4": 711494}, "sense": "max"}}
    honest = solve(data)
    assert honest["output"]["solver_status"] == "OPTIMAL"
    result = verify("optimization", data, honest, OPT)
    assert result["verdict"] == "STRUCTURALLY_VERIFIED", failed(result)
    noisy = plan(honest, honest["output"]["solution"], -172467568588.00003, bound=-172467568588.00003)
    assert verify("optimization", data, noisy, OPT)["verdict"] == "STRUCTURALLY_VERIFIED"


@pytest.mark.parametrize("data,solution,objective", [(SMALL, {"x": 1, "y": 2}, 3.0), (MIN, {"x": 0, "y": 5}, 15.0)])
def test_a_suboptimal_plan_whose_bound_is_forged_to_its_objective_is_refuted_by_a_better_witness(data, solution,
                                                                                                  objective):
    """V2: the bound check compares two numbers from the same untrusted answer; Z3 (a different engine) finds a
    strictly better assignment, and the witness really is feasible and better."""
    honest = solve(data)
    certified = verify("optimization", data, honest, OPT)
    assert certified["verdict"] == "STRUCTURALLY_VERIFIED" and certified["certificate"]["status"] == "CERTIFIED"
    assert certified["certificate"]["independence"].startswith("different engine")
    assert any("independently certified" in d for d in certified["dissent"])
    forged = plan(honest, solution, objective, bound=objective, optimality_gap=0.0)
    result = verify("optimization", data, forged, OPT)
    assert failed(result) == ["no_strictly_better_assignment_found"]
    witness = result["certificate"]["witness"]
    assert result["certificate"]["status"] == "REFUTED"
    better = sum(c * witness[n] for n, c in data["objective"]["coefficients"].items())
    assert (better > objective) if data["objective"]["sense"] == "max" else (better < objective)
    witnessed = plan(honest, witness, float(better), bound=float(better))
    assert not {"bounded_solution", "constraint_substitution"} & set(failed(verify("optimization", data, witnessed,
                                                                                   OPT)))


def test_the_certificate_dissent_reads_as_a_sentence():
    """Receipts carry this text: it read 'finds no an assignment' (independent review of the fix, 2026-10-15)."""
    infeasible = {**SMALL, "constraints": SMALL["constraints"] + [{"coefficients": {"x": 1}, "op": ">=", "rhs": 6}]}
    forged = plan(solve(SMALL), {"x": 1, "y": 2}, 3.0, bound=3.0, optimality_gap=0.0)
    said = {name: verify("optimization", data, answer, OPT)["dissent"]
            for name, data, answer in (("optimal", SMALL, solve(SMALL)), ("infeasible", infeasible, solve(infeasible)),
                                       ("refuted", SMALL, forged))}
    assert ("OPTIMAL independently certified: Z3, a different engine from CP-SAT, finds no assignment within the "
            "bounds and constraints with objective > 4.") in said["optimal"]
    assert ("INFEASIBLE independently certified: Z3, a different engine from CP-SAT, finds no assignment within the "
            "bounds and constraints.") in said["infeasible"]
    assert any(d.startswith("Z3 found an assignment within the bounds and constraints with objective > 3: ")
               for d in said["refuted"])
    assert not [d for ds in said.values() for d in ds if " no an " in d or " an an " in d]


def test_an_inconclusive_certificate_is_never_a_refutation_and_says_so(monkeypatch):
    """Unknown (the deterministic resource limit) leaves an honest claim uncertified, not refuted."""
    monkeypatch.setattr(verification, "Z3_RLIMIT", 1)
    result = verify("optimization", SMALL, solve(SMALL), OPT)
    assert result["verdict"] == "STRUCTURALLY_VERIFIED" and result["certificate"]["status"] == "UNKNOWN"
    assert any("not independently certified" in d for d in result["dissent"])
    infeasible = {**SMALL, "constraints": SMALL["constraints"] + [{"coefficients": {"x": 1}, "op": ">=", "rhs": 6}]}
    result = verify("optimization", infeasible, solve(infeasible), OPT)
    assert result["verdict"] == "STRUCTURALLY_VERIFIED" and result["certificate"]["status"] == "UNKNOWN"
    assert any("not conclusive" in d for d in result["dissent"])


def test_one_process_asking_again_gets_the_same_certificate(monkeypatch):
    """The resource count is what makes the certificate deterministic, but in Z3's shared default context the work on
    one question depends on what the process asked before: one answer re-verified in one process was CERTIFIED,
    CERTIFIED, then UNKNOWN (found re-measuring the calibration after the fix's independent review, 2026-10-15).
    Each check now has a fresh context."""
    import z3
    work, check = [], z3.Solver.check

    def counted(solver, *args):
        def used():
            stats = solver.statistics()
            return stats.get_key_value("rlimit count") if "rlimit count" in stats.keys() else 0
        before = used()
        status = check(solver, *args)
        work.append(used() - before)
        return status
    monkeypatch.setattr(z3.Solver, "check", counted)
    knapsack = {"variables": {f"x{i}": [0, 3] for i in range(6)},
                "constraints": [{"coefficients": {f"x{i}": 3 + 2 * i for i in range(6)}, "op": "<=", "rhs": 40}],
                "objective": {"coefficients": {f"x{i}": 5 + 3 * i - i * i // 2 for i in range(6)}, "sense": "max"}}
    # INFEASIBLE (review seed 3050's model): in the shared context its check took 3076, 6579, 4689, 6579 units
    equalities = {"variables": {"x0": [-1, 18], "x1": [5, 18], "x2": [-15, -5], "x3": [1, 19], "x4": [-9, 16]},
                  "constraints": [{"coefficients": {"x0": -1, "x1": -3, "x2": -6, "x4": -7}, "op": "==", "rhs": 26},
                                  {"coefficients": {"x0": 1, "x2": 6, "x3": -3, "x4": 6}, "op": "<=", "rhs": 38},
                                  {"coefficients": {"x0": -5, "x1": 3, "x3": 8, "x4": 7}, "op": ">=", "rhs": 45},
                                  {"coefficients": {"x0": -6, "x1": 6, "x2": -1, "x4": -7}, "op": "==", "rhs": -58}],
                  "objective": {"coefficients": {f"x{i}": 0 for i in range(5)}, "sense": "min"}}
    answers = [(data, solve(data)) for data in (knapsack, equalities, MIN)]
    assert [answer["output"]["solver_status"] for _, answer in answers] == ["OPTIMAL", "INFEASIBLE", "OPTIMAL"]

    def statuses():
        return [verify("optimization", data, answer, OPT)["certificate"]["status"]
                for _ in range(3) for data, answer in answers]
    assert statuses() == ["CERTIFIED"] * 9
    assert all(len(set(work[k::3])) == 1 for k in range(3)), work
    # so a limit just above the work of the first check certifies every later one too; in the shared context a later
    # check needed more and stopped UNKNOWN
    monkeypatch.setattr(verification, "Z3_RLIMIT", work[1] + 1)
    assert statuses()[1::3] == ["CERTIFIED"] * 3


def test_a_false_infeasible_and_a_false_unsat_are_refuted_and_honest_ones_are_certified():
    """Missed by the review: a negative claim verified on artifact coherence alone."""
    honest = solve(SMALL)
    false = copy.deepcopy(honest)
    false["output"] = {"solver_status": "INFEASIBLE", "solution": {}, "objective_value": None}
    false["proof"].update(solver_status="INFEASIBLE", solution={}, bound=None, optimality_gap=None)
    result = verify("optimization", SMALL, false, OPT)
    assert failed(result) == ["no_feasible_assignment_found"] and result["certificate"]["status"] == "REFUTED"
    witness = result["certificate"]["witness"]
    assert witness["x"] + witness["y"] <= 4 and 0 <= witness["x"] <= 5 and 0 <= witness["y"] <= 5
    infeasible = {**SMALL, "constraints": SMALL["constraints"] + [{"coefficients": {"x": 1}, "op": ">=", "rhs": 6}]}
    answer = solve(infeasible)
    assert answer["output"]["solver_status"] == "INFEASIBLE"
    result = verify("optimization", infeasible, answer, OPT)
    assert result["verdict"] == "STRUCTURALLY_VERIFIED" and result["certificate"]["status"] == "CERTIFIED"
    assert any("INFEASIBLE independently certified" in d for d in result["dissent"])

    formal = {"variables": {"x": [0, 2.5], "y": [0, 1]},
              "constraints": [{"coefficients": {"x": 1, "y": 0.5}, "op": "<", "rhs": 1}]}
    sat = SOLVERS["formal"](formal, {"latency_limit": 10, "compute_limit": 100000})
    assert sat["output"]["solver_status"] == "SAT"
    unsat = copy.deepcopy(sat)
    unsat["output"] = {"solver_status": "UNSAT", "solution": {}}
    unsat["proof"].update(solver_status="UNSAT", unsat_core=["constraint_0"])
    result = verify("formal", formal, unsat, FORMAL)
    assert failed(result) == ["no_feasible_assignment_found"] and result["certificate"]["status"] == "REFUTED"
    impossible = {**formal, "constraints": formal["constraints"] + [{"coefficients": {"x": 1}, "op": ">", "rhs": 1}]}
    answer = SOLVERS["formal"](impossible, {"latency_limit": 10, "compute_limit": 100000})
    assert answer["output"]["solver_status"] == "UNSAT"
    result = verify("formal", impossible, answer, FORMAL)
    assert result["verdict"] == "STRUCTURALLY_VERIFIED" and result["certificate"]["status"] == "CERTIFIED"
    # the formal family's solver is Z3 too: a re-check, never called an independent infeasibility certificate
    assert result["certificate"]["independence"].startswith("same engine")
    assert any("no independent infeasibility certificate" in d for d in result["dissent"])


def test_a_false_infeasible_through_the_canonical_path_is_refuted(monkeypatch):
    def infeasible(family, data, answer):
        answer["output"] = {"solver_status": "INFEASIBLE", "solution": {}, "objective_value": None}
        answer["proof"].update(solver_status="INFEASIBLE", solution={}, bound=None, optimality_gap=None)
        return answer
    forge_worker(monkeypatch, infeasible)
    r = reason({"problem_id": "false-infeasible", "operation": "optimize", "data": SMALL,
                "geometry": {"latency_limit": 10}}, registry=registry_view())
    assert r["abstention_state"] == "REFUTED" and r["evaluator_result"]["verdict"] == "REFUTED"
    assert r["evaluator_result"]["certificate"]["status"] == "REFUTED"


def test_a_reported_gap_must_be_the_distance_to_the_bound_and_a_feasible_bound_lies_beyond_its_objective():
    """V5: a forged gap verified, and a FEASIBLE claim's bound direction was unchecked."""
    honest = solve(SMALL)
    gap7 = copy.deepcopy(honest)
    gap7["proof"]["optimality_gap"] = 7.0
    assert failed(verify("optimization", SMALL, gap7, OPT)) == ["optimality_gap_recomputed"]
    # an honest time-limited run: a feasible plan, its bound above it (max), the gap between them
    feasible = plan(honest, {"x": 1, "y": 2}, 3.0, solver_status="FEASIBLE", bound=4.0, optimality_gap=1.0)
    feasible["output"]["solver_status"] = "FEASIBLE"
    result = verify("optimization", SMALL, feasible, OPT)
    assert result["verdict"] == "STRUCTURALLY_VERIFIED" and "certificate" not in result
    assert any("FEASIBLE claims a verified feasible assignment only" in d for d in result["dissent"])
    below = plan(feasible, {"x": 1, "y": 2}, 3.0, bound=2.0, optimality_gap=1.0)
    assert failed(verify("optimization", SMALL, below, OPT)) == ["feasible_bound_beyond_its_objective"]
    minimise = solve(MIN)
    above = plan(minimise, {"x": 0, "y": 5}, 15.0, solver_status="FEASIBLE", bound=16.0, optimality_gap=1.0)
    above["output"]["solver_status"] = "FEASIBLE"
    assert failed(verify("optimization", MIN, above, OPT)) == ["feasible_bound_beyond_its_objective"]


def test_an_objective_range_above_the_receipt_ceiling_is_refused_with_its_reason():
    """V7: an honest 2e12 optimum used to end ABSTAIN with 'invalid independent verification contract'."""
    big = {"variables": {"x": [0, 1000000], "y": [0, 1000000]}, "constraints": [],
           "objective": {"coefficients": {"x": 1000000, "y": 1000000}, "sense": "max"}}
    with pytest.raises(CognitionError, match="objective range .* exceeds the receipt's 1e12 number ceiling"):
        solve(big)
    r = reason({"problem_id": "big", "operation": "optimize", "data": big, "geometry": {"latency_limit": 10}},
               registry=registry_view())
    assert r["abstention_state"] == "ABSTAIN" and "objective range" in r["missing_information"][0]
    edge = {"variables": {"x": [-1000000, 0]}, "constraints": [],                      # range exactly 1e12: answered
            "objective": {"coefficients": {"x": 1000000}, "sense": "min"}}
    assert verify("optimization", edge, solve(edge), OPT)["certificate"]["status"] == "CERTIFIED"
    wide = {"variables": {"x": [-1000000, 1000000]}, "constraints": [],               # values fit, the gap might not
            "objective": {"coefficients": {"x": 1000000}, "sense": "max"}}
    with pytest.raises(CognitionError, match="objective range"):
        solve(wide)


def test_graph_then_allocate_is_proven_only_by_the_certificate(registry, monkeypatch):
    """V2/V6: a suboptimal plan claimed OPTIMAL with bound = objective was answered 'proven'; it is now refuted at the
    optimize stage. An honest optimum whose certificate is inconclusive says what was checked instead."""
    item = R.f3(3)
    honest = reason({"problem_id": "f3", "chain": {"payload": item["payload"], "recipe": "graph_then_allocate"}},
                    registry=registry)
    assert honest["state"] == "ANSWERED" and honest["answer"]["optimality"] == "proven"
    assert honest["answer"]["flow_value"] == item["truth"]["optimum"]

    def third_of_the_budget(family, data, answer):
        if family != "optimization":
            return None
        restricted = copy.deepcopy(data)
        for c in restricted["constraints"]:
            if c.get("requirement_id") == "budget":
                c["rhs"] //= 3
        worse = solve(restricted)["output"]
        return plan(answer, worse["solution"], worse["objective_value"], bound=worse["objective_value"],
                    optimality_gap=0.0)
    forge_worker(monkeypatch, third_of_the_budget)
    r = reason({"problem_id": "f3-forged", "chain": {"payload": item["payload"], "recipe": "graph_then_allocate"}},
               registry=registry)
    assert r["state"] == "STAGE_ABSTAINED" and r["answer"] is None
    assert [s["verifier"] for s in r["stages"] if s["stage"] == "optimize"] == ["REFUTED"]
    monkeypatch.undo()

    real = cortex.independent_verify

    def inconclusive(*a, **k):
        out = real(*a, **k)
        if "certificate" in out:
            out["certificate"] = {**out["certificate"], "status": "UNKNOWN"}
        return out
    monkeypatch.setattr(cortex, "independent_verify", inconclusive)
    r = reason({"problem_id": "f3-unknown", "chain": {"payload": item["payload"], "recipe": "graph_then_allocate"}},
               registry=registry)
    assert r["state"] == "ANSWERED" and r["answer"]["solver_status"] == "OPTIMAL"
    assert r["answer"]["optimality"].startswith("solver-reported") and "not independently certified" in \
        r["answer"]["optimality"]


def test_a_feasible_optimize_stage_is_labelled_unproven_and_its_summary_keeps_the_status(registry, monkeypatch):
    """V6: an honest time-limited stage (FEASIBLE, its bound beyond its objective) is answered, never as proven."""
    def time_limited(family, data, answer):
        if family != "optimization" or answer["output"]["solver_status"] != "OPTIMAL":
            return None
        answer["output"]["solver_status"] = answer["proof"]["solver_status"] = "FEASIBLE"
        answer["proof"].update(bound=answer["proof"]["bound"] + 2, optimality_gap=2.0)
        return answer
    forge_worker(monkeypatch, time_limited)
    item = R.f3(3)
    r = reason({"problem_id": "f3-feasible", "chain": {"payload": item["payload"], "recipe": "graph_then_allocate"}},
               registry=registry)
    assert r["state"] == "ANSWERED" and r["answer"]["solver_status"] == "FEASIBLE"
    assert r["answer"]["optimality"].startswith("unproven") and r["answer"]["optimality_gap"] == 2.0
    assert r["stages"][1]["stage"] == "optimize" and r["stages"][1]["solver_status"] == "FEASIBLE"
    assert r["stages"][1]["verifier"] == "STRUCTURALLY_VERIFIED"


def test_forecast_then_allocate_reports_each_weeks_status_and_the_weakest_certificate(registry, monkeypatch):
    """V3: its answer dropped the optimiser's status, so a time-limited week could not be told from a proven one."""
    item = R.f5(0)
    weeks = item["payload"]["newsvendor"]["weeks"]
    honest = reason({"problem_id": "f5", "chain": {"payload": item["payload"], "recipe": "forecast_then_allocate"}},
                    registry=registry)
    assert honest["state"] == "ANSWERED"
    assert honest["answer"]["solver_status"] == ["OPTIMAL"] * weeks and honest["answer"]["optimality"] == "proven"
    calls = []

    def second_week_time_limited(family, data, answer):
        if family != "optimization":
            return None
        calls.append(family)
        if len(calls) != 2:
            return None
        answer["output"]["solver_status"] = answer["proof"]["solver_status"] = "FEASIBLE"
        answer["proof"].update(bound=answer["proof"]["bound"] - 3, optimality_gap=3.0)        # minimisation
        return answer
    forge_worker(monkeypatch, second_week_time_limited)
    r = reason({"problem_id": "f5-feasible", "chain": {"payload": item["payload"], "recipe": "forecast_then_allocate"}},
               registry=registry)
    assert r["state"] == "ANSWERED"
    assert r["answer"]["solver_status"] == ["OPTIMAL", "FEASIBLE"] + ["OPTIMAL"] * (weeks - 2)
    assert r["answer"]["optimality"].startswith("unproven")


# A network with two parallel s->a edges (review 2026-10-15): the compiled model bought each its own increment, the
# decoded plan kept one and the reinforced cross-check doubled it, so the recipe answered an over-budget plan as proven.
PARALLEL = {"edges": [["s", "a", 1], ["s", "a", 1], ["a", "t", 3]], "source": "s", "sink": "t",
            "unit_cost": {"s->a": 1, "a->t": 1}, "max_increment": 5, "budget": 1}


@pytest.mark.parametrize("family", ["flow_reinforce_greedy", "flow_capacity_plan", "flow_expansion_mcf"])
def test_parallel_edges_are_refused_by_every_capacity_expansion_genome(family):
    genome = library.executables()[family]
    with pytest.raises(GenomeError, match="parallel edges"):
        genome.solve(PARALLEL, None)
    with pytest.raises(GenomeError, match="parallel edges"):
        genome.verify(PARALLEL, {"increments": {}, "flow_value": 0, "spent": 0, "model": {}, "decode": {}}, {})
    with pytest.raises(GenomeError, match="parallel edges"):
        flow.expansion_value(PARALLEL, {"s->a": 1})
    merged = {**PARALLEL, "edges": [["s", "a", 2], ["a", "t", 3]]}           # the same capacity, merged: answered
    assert genome.solve(merged, None)["status"] == "ANSWER"


@pytest.mark.parametrize("field, value, error", [("unit_cost", "bad", "unit_cost maps"),
                                                 ("max_increment", -1, "max_increment: integer"),
                                                 ("budget", "x", "budget: integer")])
def test_flow_expansion_mcf_keeps_its_1_0_0_error_order_on_parallel_edges(field, value, error):
    """mcf stays at 1.0.0, so moving the parallel-edge refusal into the shared validation must not change which error
    it raises: it checked parallel edges after every other field (independent review of the fix, 2026-10-15)."""
    mcf = library.executables()["flow_expansion_mcf"]
    with pytest.raises(GenomeError, match=error):
        mcf.solve({**PARALLEL, field: value}, None)
    with pytest.raises(GenomeError, match=error):
        mcf.verify({**PARALLEL, field: value}, {"increments": {}}, {})


@pytest.mark.parametrize("network", [
    PARALLEL,
    {**PARALLEL, "edges": [["s", "a", 1], ["s", "a", 1], ["a", "t", 10]]},
    {**PARALLEL, "edges": [["s", "a", 1], ["s", "a", 1], ["a", "t", 4]], "budget": 2}])
def test_graph_then_allocate_never_answers_a_network_with_parallel_edges(registry, network):
    r = reason({"problem_id": "parallel", "chain": {"payload": {"capacity_network": network},
                                                    "recipe": "graph_then_allocate"}}, registry=registry)
    assert r["state"] == "STAGE_ABSTAINED" and r["answer"] is None and r["reason"].startswith("compile")
