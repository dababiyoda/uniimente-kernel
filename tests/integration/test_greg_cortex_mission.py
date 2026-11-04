"""A cortex problem as an ordinary signed GREG mission (directive section 16).

initiate (signed MISSION) -> classify (cortex geometry) -> execute heterogeneous computation
(CP-SAT in the bounded worker, Z3 certificate) -> verify (adversarial verifier + independent
re-evaluation) -> persist (Gate receipt on the canonical ledger) -> close only on re-observed
evidence -> separate-process appraisal -> settlement -> restart without duplicate settlement ->
later refutation removes competence without rewriting history.

The founder key is a per-test key (see tests/greg_fixtures.py); nothing here is founder use.
"""
import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from cortex.evaluation.build_suites import schedule  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.cognition.cells import cells  # noqa: E402
from greg.cognition.settlement import competence  # noqa: E402
from tests.greg_fixtures import drop, make_body, mission, signed  # noqa: E402


def cortex_params():
    model, _, _ = schedule([("A", 3), ("B", 4), ("C", 2)], 10,
                           query={"kind": "optimize", "sense": "minimize", "objective": ["+", "s_A", "s_B", "s_C"]})
    return {"problem_id": "cortex:schedule", "problem": {
        "question": "Earliest start times for jobs A, B, C on one machine within a 10h shift",
        "payload": {"formal_model": model, "declared": {"consequence_class": "internal_write",
                                                        "reversibility": "reversible"}}}}


def cortex_mission(mid="m:cortex", params=None):
    params = params or cortex_params()
    step = {"capability": "cognition.solve", "target": "cognition:schedule", "params": params}
    return mission(mid, checks=[{
        "check_id": "optimal-schedule", "description": "a certified optimal schedule with objective 7",
        "sensor": step, "predicate": {"op": "equals", "field": "output.answer.objective", "value": 7}}],
        strategies=[{"action_id": "solve", **step, "advances": ["optimal-schedule"],
                     "rationale": "compute the schedule through the cortex"}],
        capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")


def cognitive_receipts(body):
    out = []
    for r in body.ledger.by_type("receipt"):
        value = r.payload["result"].get("output")
        if isinstance(value, dict) and value.get("proof_type") == "cortex_receipt":
            out.append(value)
    return out


def test_cortex_mission_closes_on_reobserved_evidence_and_settles_once(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", cortex_mission()))
    with Body(home) as body:
        body.boot()
        outcome = body.tick()
        assert outcome["missions"][0]["state"] == "ACHIEVED", outcome
        receipts = cognitive_receipts(body)
        assert receipts, "the Gate receipt must retain the cortex receipt"
        r = receipts[-1]
        assert r["method"] == "cognition.cortex.optimization.cpsat" and r["authority_created"] is False
        assert r["proof_artifact"]["proof_artifacts"][0]["certificate"]["status"] == "CERTIFIED"
        assert r["outcome"]["outcome"] == "ANSWERED_WITHIN_SCOPE"
        appraised = body.journal.replay("mission.appraised")[-1].payload
        assert appraised["verdict"] == "VERIFIED", appraised
        rows = competence(body.journal)
        assert len(rows) == 1 and next(iter(rows))[0] == "cognition.cortex.optimization.cpsat"
        assert len(body.journal.replay("cognition.settled")) == 1
        cell = cells(body.journal, body.registry)[0]
        assert cell["reasoner"]["capability_id"] == "cognition.cortex.optimization.cpsat"
        count = len(body.ledger.by_type("receipt"))
    with Body(home) as body:          # restart: replay, no duplicate action, no duplicate settlement
        body.boot()
        body.tick()
        assert len(body.ledger.by_type("receipt")) == count
        assert len(body.journal.replay("cognition.settled")) == 1
        assert next(iter(competence(body.journal).values()))["count"] == 1
        body.journal.record("mission.appraised", {"mission_id": "m:cortex", "verdict": "REFUTED", "checks": {}},
                            key="later-independent-refutation")
        assert competence(body.journal) == {}          # credit withdrawn; history retained
        assert len(body.journal.replay("cognition.settled")) == 1


def test_detached_cpsat_reroutes_the_same_mission_to_z3_under_the_same_signature(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "cognition.cortex.optimization.cpsat"}))
    drop(home, signed(key, body_id, "MISSION", cortex_mission("m:detached")))
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        r = cognitive_receipts(body)[-1]
        assert r["method"] == "cognition.cortex.formal.z3"
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"


def test_an_unanswerable_problem_never_closes_the_mission(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    params = cortex_params()
    params["problem"]["payload"]["declared"]["epistemic_class"] = "legal"
    drop(home, signed(key, body_id, "MISSION", cortex_mission("m:legal", params)))
    with Body(home) as body:
        body.boot()
        state = body.tick()["missions"][0]["state"]
        assert state != "ACHIEVED"
        r = cognitive_receipts(body)[-1]
        assert r["abstention_state"] == "HUMAN_REVIEW_REQUIRED" and r["outcome"]["outcome"] == "ESCALATE"
        assert not body.journal.replay("mission.achieved")
