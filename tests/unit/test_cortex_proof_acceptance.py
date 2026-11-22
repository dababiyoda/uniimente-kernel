"""Cortex 0.2.3: what the cortex accepts as proof of an optimum, and what counts as a second engine's confirmation.

Findings 4 and 5 of the independent convergence review on #196 (comment 6934260821, 2026-11-17):

* 4. The adversarial verifier accepted a solver's own native OPTIMAL status as sufficient proof of optimality, and the
  separate Z3 optimality certificate carried nothing binding it to the problem and answer it was computed for. Now:
  an optimum is independently certified only by the formal engine's own UNSAT proof or by a CERTIFIED Z3 certificate
  bound to this model, this objective value and this sense. Native OPTIMAL alone stays acceptable but is reported as
  uncertified (a major, non-blocking finding); a certificate that does not bind the answer is a critical finding.
* 5. A second engine's matching answer was recorded as confirmation whatever its state, and an engine that returned
  nothing was labelled a disagreement. Now only a conclusive second answer (state OK or WORLD_UNVERIFIED) confirms or
  contests; anything else is recorded as inconclusive and leaves the lead verdict unconfirmed. One exception keeps the
  safer direction: an inconclusive engine's feasibility witness that the solver-independent evaluator accepts still
  refutes an impossibility verdict.
"""
import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from cortex.contracts import OrganResult, digest  # noqa: E402
from cortex.evaluation.build_suites import schedule  # noqa: E402
from cortex.organs import adversarial  # noqa: E402
from cortex.organs import cpsat as C  # noqa: E402
from cortex.routing import CPSAT, FORMAL, Cortex  # noqa: E402
from cortex.schemas import validate  # noqa: E402

CLOCK = lambda: "2026-11-21T00:00:00Z"  # noqa: E731
DECL = {"consequence_class": "internal_write", "reversibility": "reversible"}
OPT = {"kind": "optimize", "sense": "minimize", "objective": ["+", "s_A", "s_B", "s_C"]}


def run_cortex(model, cortex=None, **payload):
    payload.setdefault("declared", DECL)
    r = (cortex or Cortex(clock=CLOCK)).run({"problem_id": "t", "question": "q",
                                             "payload": {"formal_model": model, **payload}})
    validate(r, "cortex-receipt")
    for proof in r["proof_artifacts"]:
        validate(proof, "cortex-proof-artifact")
    return r


def recheck(model, result):
    findings = []
    adversarial._recheck_formal_answers({"formal_model": model}, [result],
                                        lambda sev, kind, detail, target=None: findings.append((sev, kind)))
    return findings


def optimum(model):
    """The true optimum, from the real CP-SAT organ, as a CP-SAT result with only its native OPTIMAL status."""
    r = run_cortex(model)
    answer = r["output"]["answer"]
    assert answer["optimal"] is True
    return answer


def cpsat_result(answer, **proof):
    return OrganResult(organ_id=CPSAT, organ_version="0.2.3", state="OK", answer=dict(answer),
                       proof={"proof_class": "formal", "scope": "valid_given_encoding",
                              "native_status": "OPTIMAL", "solver": {"status": "OPTIMAL"}, **proof},
                       origin="solver")


MODEL, _, _ = schedule([("A", 3), ("B", 4), ("C", 2)], 10, query=OPT)


class TestFinding4OptimalityProof:
    def test_the_z3_certificate_binds_model_value_and_sense(self):
        answer = optimum(MODEL)
        cert = C.z3_optimality_certificate(MODEL, answer["objective"])
        assert cert["status"] == "CERTIFIED"
        assert cert["binding"] == {"model_digest": digest(MODEL), "value": answer["objective"],
                                   "sense": "minimize"}
        unrun = C.z3_optimality_certificate(MODEL, answer["objective"], timeout_ms=1)
        assert "binding" in unrun          # every outcome, certified or not, names what it was computed for

    def test_native_optimal_alone_is_reported_as_not_independently_certified(self):
        findings = recheck(MODEL, cpsat_result(optimum(MODEL)))
        assert ("major", "optimality_not_independently_certified") in findings
        assert not any(sev == "critical" for sev, _ in findings)   # non-blocking: a mature solver's claim stands

    def test_a_bound_certified_certificate_is_independent_proof(self):
        answer = optimum(MODEL)
        cert = C.z3_optimality_certificate(MODEL, answer["objective"])
        assert recheck(MODEL, cpsat_result(answer, certificate=cert)) == []

    def test_a_certificate_for_another_value_does_not_bind_this_answer(self):
        answer = optimum(MODEL)
        stale = C.z3_optimality_certificate(MODEL, answer["objective"] + 1)   # certifies a different claim
        findings = recheck(MODEL, cpsat_result(answer, certificate=stale))
        assert ("critical", "certificate_does_not_bind_answer") in findings

    def test_a_certificate_for_another_model_does_not_bind_this_answer(self):
        answer = optimum(MODEL)
        other, _, _ = schedule([("A", 3), ("B", 4), ("C", 3)], 10, query=OPT)
        cert = C.z3_optimality_certificate(other, answer["objective"])
        findings = recheck(MODEL, cpsat_result(answer, certificate=cert))
        assert ("critical", "certificate_does_not_bind_answer") in findings

    def test_a_certificate_with_no_binding_is_not_independent_proof(self):
        answer = optimum(MODEL)
        bare = {"status": "CERTIFIED", "engine": "z3"}                      # a forged or pre-0.2.3 certificate
        findings = recheck(MODEL, cpsat_result(answer, certificate=bare))
        assert ("critical", "certificate_does_not_bind_answer") in findings

    def test_the_real_route_still_certifies_and_recommends(self):
        r = run_cortex(MODEL)
        proof = r["proof_artifacts"][0]
        assert proof["certificate"]["status"] == "CERTIFIED"
        assert proof["certificate"]["binding"]["model_digest"] == digest(MODEL)
        kinds = {f["kind"] for f in r["verifier"]["findings"]}
        assert "optimality_not_independently_certified" not in kinds
        assert r["disposition"]["kind"] == "recommend"

    def test_without_a_certificate_the_route_says_so(self):
        c = Cortex(clock=CLOCK)
        real = c.organs[FORMAL]

        class NoZ3:
            organ_id = FORMAL

            def run(self, *a):
                return real.run(*a)

        c.organs[FORMAL] = NoZ3()
        real_cert = C.z3_optimality_certificate
        try:
            C.z3_optimality_certificate = lambda model, value, timeout_ms=5000: {
                "status": "NOT_RUN", "engine": "z3", "why": "z3-solver is not installed",
                "binding": {"model_digest": digest(model), "value": value, "sense": model["query"]["sense"]}}
            r = run_cortex(MODEL, c)
        finally:
            C.z3_optimality_certificate = real_cert
        kinds = {f["kind"]: f["severity"] for f in r["verifier"]["findings"]}
        assert kinds.get("optimality_not_independently_certified") == "major"
        assert r["verifier"]["blocking"] is False


class _Fixed:
    def __init__(self, organ_id, state, answer):
        self.organ_id, self.state, self.answer = organ_id, state, answer

    def run(self, problem, geometry, budget):
        return OrganResult(organ_id=self.organ_id, organ_version="0.2.3", state=self.state,
                           answer=None if self.answer is None else dict(self.answer),
                           proof={"proof_class": "formal", "scope": "valid_given_encoding",
                                  "failure": "fixed for the test"}, origin="solver")


INFEASIBLE, _feasible, _ = schedule([("A", 4), ("B", 4), ("C", 3)], 10)


class TestFinding5SecondEngine:
    def second(self, state, answer):
        c = Cortex(clock=CLOCK)
        c.organs[CPSAT] = _Fixed(CPSAT, state, answer)
        return run_cortex(INFEASIBLE, c)

    def test_a_conclusive_matching_answer_confirms(self):
        r = run_cortex(INFEASIBLE)
        assert r["proof_artifacts"][0]["confirmed_by"] == {"engine": CPSAT, "state": "OK"}

    @pytest.mark.parametrize("state", ["INCONCLUSIVE", "CONTESTED"])   # the non-conclusive states that carry answers
    def test_a_matching_answer_from_an_inconclusive_engine_does_not_confirm(self, state):
        r = self.second(state, {"feasible": False})
        proof = r["proof_artifacts"][0]
        assert "confirmed_by" not in proof
        assert proof["confirmation_inconclusive"] == {"engine": CPSAT, "state": state}
        assert r["output"]["state"] != "CONTESTED"
        whys = [a["why"] for a in r["route"]["attempts"] if a["organ_id"] == CPSAT]
        assert whys == ["inconclusive"]

    def test_no_answer_is_inconclusive_not_a_disagreement(self):
        r = self.second("TIMEOUT", None)
        whys = [a["why"] for a in r["route"]["attempts"] if a["organ_id"] == CPSAT]
        assert whys == ["inconclusive"]
        assert "engine_disagreement" not in r["proof_artifacts"][0]

    def test_an_unchecked_inconclusive_disagreement_does_not_contest(self):
        r = self.second("INCONCLUSIVE", {"feasible": True})      # says feasible, offers no witness
        assert r["output"]["state"] != "CONTESTED"
        assert "engine_disagreement" not in r["proof_artifacts"][0]

    def test_an_inconclusive_engines_false_witness_does_not_contest(self):
        r = self.second("INCONCLUSIVE", {"feasible": True, "model": {"s_A": 0, "s_B": 0, "s_C": 0}})
        assert r["output"]["state"] != "CONTESTED"

    def test_a_conclusive_disagreement_still_contests(self):
        r = self.second("OK", {"feasible": True, "model": {"s_A": 0, "s_B": 0, "s_C": 0}})
        assert r["output"]["state"] == "CONTESTED"
        assert "engines_disagree" in {f["kind"] for f in r["verifier"]["findings"]}


def test_an_inconclusive_engines_checked_witness_refutes_an_impossibility_verdict():
    """The safer direction survives: a witness the evaluator accepts outweighs a lead engine's 'infeasible'."""
    feasible_model, feasible, _ = schedule([("A", 3), ("B", 4)], 10)
    assert feasible is True
    c = Cortex(clock=CLOCK)

    class LyingLead:
        organ_id = FORMAL

        def run(self, problem, geometry, budget):
            return OrganResult(organ_id=FORMAL, organ_version="0.2.3", state="OK", answer={"feasible": False},
                               proof={"proof_class": "formal", "scope": "valid_given_encoding",
                                      "failure": "lying lead"}, origin="solver")

    real = c.organs[CPSAT]

    class InconclusiveWitness:
        organ_id = CPSAT

        def run(self, problem, geometry, budget):
            out = real.run(problem, geometry, budget)
            assert out.answer and out.answer.get("feasible") is True
            return OrganResult(organ_id=CPSAT, organ_version="0.2.3", state="INCONCLUSIVE", answer=out.answer,
                               proof=out.proof, origin="solver")

    c.organs[FORMAL] = LyingLead()
    c.organs[CPSAT] = InconclusiveWitness()
    r = run_cortex(feasible_model, c)
    assert r["output"]["state"] == "CONTESTED"
    assert r["proof_artifacts"][0]["engine_disagreement"]["witness_checked"] is True
