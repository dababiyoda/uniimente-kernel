"""P4: GREG's cortex routing learns from GREG's own settled outcomes, without gaining authority.

* The competence ledger is a projection of signed missions' Gate receipts: one record per
  signed claim (retries do not multiply it), success only after a VERIFIED separate-process
  appraisal, failure when the router observed the lead engine return no decision, and a
  later refutation removes the credit on recomputation.
* ``shadow`` (default) executes the fixed policy and states the order memory would choose;
  ``learned`` (a signed request field) lets memory permute the eligible engines in the worker.
* Memory never makes an engine eligible, travels content-addressed and is refused if edited.

Real Z3/CP-SAT in the bounded worker; the founder key is a per-test key, not Alfonso's.
"""
import copy
import itertools

import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from cortex.genome import seed_registry  # noqa: E402
from cortex.memory import CompetenceLedger  # noqa: E402
from cortex.routing import CPSAT, FORMAL, Cortex  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.cognition import bridge, learned_routing  # noqa: E402
from greg.cognition.contracts import CognitionError, CognitiveReceipt  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402
from tests.greg_fixtures import drop, make_body, mission, signed  # noqa: E402
from tests.integration.test_greg_cortex_mission import cortex_mission  # noqa: E402

DECL = {"consequence_class": "read_only", "reversibility": "reversible"}


def pigeonhole(holes: int, budget: float, pid: str | None = None) -> dict:
    """holes+1 pigeons, pairwise distinct: infeasible, and hard for Z3 from about 9 holes."""
    return {"problem_id": pid or f"ph{holes}", "problem": {"question": "Distinct bays?", "payload": {"formal_model": {
        "requirement": "every pigeon in a distinct hole",
        "variables": [{"name": f"p{k}", "sort": "int", "lo": 1, "hi": holes} for k in range(holes + 1)],
        "obligations": [{"id": "R", "text": "distinct"}],
        "constraints": [{"id": f"C{a}_{b}", "covers": ["R"], "expr": ["!=", f"p{a}", f"p{b}"]}
                        for a, b in itertools.combinations(range(holes + 1), 2)]},
        "resources": {"max_latency_s": budget}, "declared": DECL}}}


def decided_mission(mid: str, params: dict) -> dict:
    step = {"capability": "cognition.solve", "target": "cognition:pigeonhole", "params": params}
    return mission(mid, checks=[{"check_id": "decided", "description": "the infeasibility is decided",
                                 "sensor": step, "predicate": {"op": "equals", "field": "output.answer.feasible",
                                                               "value": False}}],
                   strategies=[{"action_id": "solve", **step, "advances": ["decided"], "rationale": "decide"}],
                   capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")


def led_receipt(lead: str) -> dict:
    """A real cortex receipt for a feasibility question whose formal plan is led by ``lead``."""
    registry = seed_registry()
    other = CPSAT if lead == FORMAL else FORMAL
    registry.withhold(other, "test: the founder detached the other engine")
    receipt = Cortex(registry, clock=lambda: "2026-10-07T00:00:00Z").run(pigeonhole(4, 5.0)["problem"] |
                                                                           {"problem_id": f"lead-{lead}"})
    assert receipt["route"]["selected"] == [lead]
    return receipt


def trained_ledger(z3_status: str, cpsat_status: str, n: int = 9) -> CompetenceLedger:
    ledger = CompetenceLedger()
    for lead, status in ((FORMAL, z3_status), (CPSAT, cpsat_status)):
        receipt = led_receipt(lead)
        method, _, version = lead.partition("@")
        for _ in range(n):
            ledger.settle(receipt=receipt, method=method, method_version=version, outcome_status=status,
                          provenance=learned_routing.PROVENANCE,
                          attribution=[{"method": method, "role": "final_answer", "uncertainty": "medium"}])
    return ledger


def run_learned(params: dict, memory: CompetenceLedger, withheld=None) -> dict:
    _, problem, records = bridge._validate(params)
    return bridge.run_worker(problem, records, withheld_organs=withheld or {}, semantic_model=None, cpu_seconds=10,
                             created_at="2026-10-07T00:00:00Z",
                             memory_records=[r.to_dict() for r in memory.records()])


class TestProjectionFromSignedMissions:
    def test_success_after_appraisal_and_lead_failure_settle_once_per_claim(self, tmp_path):
        home, key, body_id, _ = make_body(tmp_path)
        drop(home, signed(key, body_id, "MISSION", cortex_mission("m:answered")))
        drop(home, signed(key, body_id, "MISSION", decided_mission("m:pigeonhole", pigeonhole(10, 1.0))))
        with Body(home) as body:
            body.boot()
            for _ in range(3):          # the hard claim is retried; retries must not multiply evidence
                body.tick()
            gate_receipts = [r for r in body.ledger.by_type("receipt")
                             if (r.payload["result"].get("output") or {}).get("proof_type") == "cortex_receipt"]
            assert len(gate_receipts) >= 3
            claims = learned_routing.settled_claims(body.journal)
            by_lead = {c["lead"]: c for c in claims}
            assert len(claims) == 2, [(c["lead"], c["status"]) for c in claims]
            assert by_lead[CPSAT]["status"] == "verified_success"
            assert by_lead[CPSAT]["provenance"]["appraisal_event"] is not None
            assert by_lead[FORMAL]["status"] == "observed_failure"
            assert by_lead[FORMAL]["attribution"][0]["role"] == "resource_consumption"
            ledger = learned_routing.ledger(body.journal)
            assert [r.outcome_status for r in ledger.records()] == [c["status"] for c in claims]
            assert {r.competence_update["weight"] for r in ledger.records()} == {0.6}
            assert all(r.outcome_provenance["kind"] == "internal_observation" for r in ledger.records())
            # Conditions come from the signed check's own problem (P4 conditional competence).
            conds = {r.method: dict(c.split("=", 1) for c in r.conditions) for r in ledger.records()}
            assert conds["cortex.optimization.cpsat"]["kind"] == "optimize"
            assert conds["cortex.formal.z3"]["ops"] == "!=" and conds["cortex.formal.z3"]["budget"] == "<=1s"
            # A later independent refutation withdraws the success on recomputation; history stays.
            body.journal.record("mission.appraised", {"mission_id": "m:answered", "verdict": "REFUTED",
                                                      "checks": {}}, key="later-refutation")
            after = learned_routing.ledger(body.journal)
            assert [(r.method, r.outcome_status) for r in after.records()] == [("cortex.formal.z3",
                                                                               "observed_failure")]

    def test_the_next_mission_receipt_states_what_memory_would_do(self, tmp_path):
        home, key, body_id, _ = make_body(tmp_path)
        drop(home, signed(key, body_id, "MISSION", cortex_mission("m:answered")))
        with Body(home) as body:
            body.boot()
            body.tick()
            r = reason(pigeonhole(4, 5.0, "next"), registry=body.registry, journal=body.journal)
            routing = r["routing"]
            assert routing["mode"] == "shadow" and routing["applies"] is True
            assert routing["settled_records"] == 1 and routing["executed_order"] == routing["static_order"]
            assert routing["static_order"] == [FORMAL, CPSAT]
            assert routing["authority_created"] is False


class TestModes:
    def test_shadow_is_the_default_and_never_changes_execution(self):
        r = reason(pigeonhole(4, 5.0), registry=registry_view())
        assert r["routing"]["mode"] == "shadow" and r["routing"]["changed_execution"] is False

    def test_static_mode_consults_no_memory(self):
        r = reason({**pigeonhole(4, 5.0), "routing": "static"}, registry=registry_view())
        assert r["routing"]["mode"] == "static" and r["routing"]["settled_records"] == 0

    def test_unknown_mode_is_refused_before_any_computation(self):
        with pytest.raises(CognitionError, match="routing must be one of"):
            reason({**pigeonhole(4, 5.0), "routing": "autonomous"}, registry=registry_view())

    def test_non_formal_problem_records_that_routing_memory_does_not_apply(self):
        model = {"target": {"name": "weekly_hours", "unit": "h"},
                 "variables": [{"name": "jobs", "unit": "1", "low": 20, "high": 30},
                               {"name": "hours_per_job", "unit": "h", "low": 1.5, "high": 2.5}],
                 "expression": ["*", "jobs", "hours_per_job"], "dependencies": [], "reference_class": None,
                 "seed": 7}
        r = reason({"problem_id": "est", "problem": {"question": "q", "payload": {
            "estimation_model": model, "declared": DECL}}}, registry=registry_view())
        assert r["method"] == "cognition.cortex.estimation.fermi"
        assert r["routing"]["applies"] is False and r["routing"]["executed_order"] == []


class TestLearnedRoutingInTheWorker:
    def test_learned_memory_permutes_eligible_engines_only(self):
        memory = trained_ledger("observed_failure", "verified_success")
        assert memory.reorder([FORMAL, CPSAT], type("G", (), {"epistemic_class": "constraint_feasibility"})) == \
            [CPSAT, FORMAL]
        params = {**pigeonhole(5, 5.0, "learned"), "routing": "learned"}
        receipt = run_learned(params, memory)
        plan = receipt["route"]["formal_plan"]
        assert plan["order"] == [CPSAT, FORMAL] and plan["policy_order"] == [FORMAL, CPSAT]
        assert receipt["route"]["selected"] == [CPSAT] and receipt["output"]["answer"]["feasible"] is False
        summary = learned_routing.summary("learned", memory, receipt)
        assert summary["changed_execution"] and summary["static_order"] == [FORMAL, CPSAT]
        learned_routing.check_summary(summary)
        # The same memory with CP-SAT detached by the founder cannot bring it back.
        detached = run_learned(params, memory, withheld={CPSAT: "founder detached"})
        assert detached["route"]["formal_plan"]["order"] == [FORMAL]
        assert CPSAT in detached["route"]["formal_plan"]["excluded"]

    def test_without_enough_evidence_memory_keeps_the_fixed_policy(self):
        memory = trained_ledger("observed_failure", "verified_success", n=4)    # 4 x 0.6 < 3 weighted outcomes
        receipt = run_learned({**pigeonhole(5, 5.0, "thin"), "routing": "learned"}, memory)
        assert receipt["route"]["formal_plan"]["order"] == [FORMAL, CPSAT]

    def test_an_edited_memory_record_refuses_the_run(self):
        memory = trained_ledger("observed_failure", "verified_success")
        records = [r.to_dict() for r in memory.records()]
        records[0] = {**records[0], "outcome_status": "verified_success"}       # not re-addressed
        _, problem, recs = bridge._validate(pigeonhole(4, 5.0))
        with pytest.raises(CognitionError, match="content address"):
            bridge.run_worker(problem, recs, withheld_organs={}, semantic_model=None, cpu_seconds=10,
                              created_at="2026-10-07T00:00:00Z", memory_records=records)


class TestReceiptInvariant:
    def receipt(self):
        return reason(pigeonhole(4, 5.0), registry=registry_view())

    def rebuild(self, receipt, routing):
        fields = copy.deepcopy(receipt)
        fields.pop("receipt_id")
        fields["routing"] = routing
        return CognitiveReceipt(**fields)

    def test_shadow_cannot_claim_a_changed_execution(self):
        r = self.receipt()
        forged = {**r["routing"], "executed_order": list(reversed(r["routing"]["static_order"]))}
        with pytest.raises(CognitionError, match="outside a signed learned mission"):
            self.rebuild(r, forged)

    def test_memory_cannot_add_an_engine(self):
        r = self.receipt()
        forged = {**r["routing"], "mode": "learned", "executed_order": r["routing"]["static_order"] + ["x@1"]}
        with pytest.raises(CognitionError, match="eligible"):
            self.rebuild(r, forged)

    def test_routing_cannot_claim_authority(self):
        r = self.receipt()
        with pytest.raises(CognitionError, match="authority"):
            self.rebuild(r, {**r["routing"], "authority_created": True})
