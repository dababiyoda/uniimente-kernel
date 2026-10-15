"""Review findings on the one-machine path: each gate guarantees what its label claims.

* The worker is handed an answer labelled CERTIFIED only when the mission gate guarantees a
  problem-level certificate, not merely that some method answered.
* The sandbox whole-machine diagnostic reads each stage from the capability it names.
"""
from __future__ import annotations

from types import SimpleNamespace as NS

from events.spine import EventSpine
from greg import metrics, templates
from greg.cognition import compiler
from greg.journal import Journal
from greg.missions import evaluate_predicate
from provenance.ledger import EvidenceLedger

ORGANS = {"daleobanks_root": "/r/d", "daleobanks_python": "/r/d/py", "wealthmachine_root": "/r/w",
          "wealthmachine_python": "/r/w/py"}
DATA = {"workers": [{"id": "Ana", "skills": ["a"], "capacity": 1}], "orders": [{"id": "O", "skill": "a", "demand": 1}]}


def answered_check():
    spec = templates.one_machine(problem_id="p", data=DATA, sandbox_repo="/tmp", organs=ORGANS, seed="s")
    return next(c for c in spec["success_checks"] if c["check_id"] == "answered")


def test_the_answered_gate_admits_only_a_certified_answer():
    predicate = answered_check()["predicate"]
    certified = {"state": "ANSWERED", "confidence_type": compiler.CERTIFIED, "result": {"staffed": 1}}
    for weaker in ("composition of typed stage evidence", "search_trace", "bounded_estimate", "cortex_receipt"):
        assert evaluate_predicate(predicate, {**certified, "confidence_type": weaker})[0] is False, weaker
    assert evaluate_predicate(predicate, certified)[0] is True


def test_a_construction_without_a_certificate_is_never_labelled_certified():
    manifest = NS(capability_id="composed.x", consequence_class="read_only", provider="composed:x", provenance={})
    registry = NS(manifests={"composed.x": manifest}, adapters={"composed.x": lambda request, ctx: {"certified": False}})
    receipt = {"abstentions": [], "resource_use": {}, "dissent": []}
    out = compiler._run_constructed({"method": "composed.x", "inputs": []}, {}, "p", registry, receipt,
                                    lambda state, result=None: {**receipt, "state": state})
    assert out["state"] == "ABSTAIN" and out.get("confidence_type") != compiler.CERTIFIED


def test_sandbox_stages_are_bound_to_the_capability_they_name(tmp_path):
    """A venture verdict string 'ACCEPTED' and a compilation-shaped output from a non-cognition
    sensor (or a failing observation) must not mark worker_accepted or mind_certified_without_model."""
    journal = Journal(EventSpine(EvidenceLedger("sha256:" + "2" * 64, path=str(tmp_path / "l.jsonl"))),
                      actor="spiffe://uniimente.internal/test/metrics")
    mid = "m:lookalike"
    journal.record("mission.registered", {"mission_id": mid, "spec": {"strategies": [], "success_checks": [
        {"check_id": "venture", "sensor": {"capability": "venture.status"}},
        {"check_id": "mind", "sensor": {"capability": "fs.read"}},
        {"check_id": "thought", "sensor": {"capability": "cognition.solve"}}]}}, key=[mid])
    compilation = {"schema": "greg-competency-compilation/0.1", "state": "ANSWERED",
                   "confidence_type": compiler.CERTIFIED, "cost": {"model_calls": 0}}
    for check, output, passed in (("venture", {"verdict": "ACCEPTED"}, True), ("mind", compilation, True),
                                  ("thought", compilation, False)):
        receipt = journal.ledger.append("receipt", {"result": {"output": output}}).hash
        journal.record("mission.observed", {"mission_id": mid, "check_id": check, "passed": passed,
                                            "receipt": receipt}, key=[mid, check])
    journal.record("mission.achieved", {"mission_id": mid}, key=[mid, "achieved"])
    [row] = metrics.sandbox_whole_machine(journal)["missions"]
    assert row["worker_accepted"] is False and row["mind_certified_without_model"] is False



def test_a_function_named_sensor_counts_through_the_capability_the_engine_resolved(tmp_path):
    """Second review (measurement 2): stages were read from the spec's ``capability`` key only, so a
    sensor naming a function (work.appraise, resolved to worker.appraise) never counted. The engine
    now records the resolved capability on the observation, and that is what the stage reads."""
    journal = Journal(EventSpine(EvidenceLedger("sha256:" + "3" * 64, path=str(tmp_path / "l.jsonl"))),
                      actor="spiffe://uniimente.internal/test/metrics")
    mid = "m:function-named"
    journal.record("mission.registered", {"mission_id": mid, "spec": {"strategies": [], "success_checks": [
        {"check_id": "appraised", "sensor": {"function": "work.appraise"}}]}}, key=[mid])
    receipt = journal.ledger.append("receipt", {"result": {"output": {"verdict": "ACCEPTED"}}}).hash
    journal.record("mission.observed", {"mission_id": mid, "check_id": "appraised", "passed": True,
                                        "receipt": receipt, "capability": "worker.appraise"}, key=[mid, "observed"])
    journal.record("mission.achieved", {"mission_id": mid}, key=[mid, "achieved"])
    [row] = metrics.sandbox_whole_machine(journal)["missions"]
    assert row["worker_accepted"] is True

def closure(journal, mid, output):
    """A synthetic closure meeting all nine VEPMC conditions, with one receipted observation."""
    designation = journal.record("command.accepted", {"kind": "BODY_DESIGNATE", "signer": "founder", "digest": "d1"},
                                 key=["designate"])
    journal.record("body.designated", {"command_digest": "d1", "body_id": "b1", "platform": "Linux",
                                       "purpose": "first_founder_body"}, key=["designated"])
    assert designation
    journal.record("mission.registered", {"mission_id": mid, "spec": {"strategies": [], "success_checks": []}},
                   key=[mid, "registered"])
    journal.record("body.recovered", {"at": "x"}, key=[mid, "recovered"])
    receipt = journal.ledger.append("receipt", {"result": {"output": output}}).hash
    journal.record("mission.observed", {"mission_id": mid, "check_id": "c", "passed": True, "receipt": receipt},
                   key=[mid, "observed"])
    achieved = journal.record("mission.achieved", {"mission_id": mid}, key=[mid, "achieved"])
    journal.record("mission.closure_context", {"mission_id": mid, "hosted": True, "body_id": "b1",
                                               "platform": "Linux"}, key=[mid, "context"])
    journal.record("mission.appraised", {"mission_id": mid, "verdict": "VERIFIED", "checks": {
        "founder_signature_verified": True, "arrived_via_inbox": True, "approval_boundary_encountered": True,
        "approval_boundaries_honored": True}}, key=[mid, "appraised"])
    journal.record("critique.recorded", {"verdict": "accept", "target_event_id": achieved.event_id},
                   key=[mid, "accepted"])


def test_fixture_evidence_never_moves_vepmc_even_when_every_condition_holds(tmp_path):
    """Founder rule: VEPMC must not change through simulation. A closure meeting all nine conditions
    counts; the same closure whose receipt carries fixture-mode output (a fixture sale) does not, and
    the nine conditions themselves are unchanged."""
    def ledger_with(output, name):
        journal = Journal(EventSpine(EvidenceLedger("sha256:" + "3" * 64, path=str(tmp_path / f"{name}.jsonl"))),
                          actor="spiffe://uniimente.internal/test/vepmc")
        closure(journal, "m:closure", output)
        return metrics.vepmc(journal)
    real = ledger_with({"verdict": "ACCEPTED"}, "real")
    assert real["VEPMC"] == 1 and real["conditions"] == list(metrics.CONDITIONS) and len(metrics.CONDITIONS) == 9
    fixture = ledger_with({"result": {"order": {"mode": "fixture", "id": "fixture-order-1"}}}, "fixture")
    [row] = fixture["missions"]
    assert fixture["VEPMC"] == 0 and row["fixture_evidence"] is True and row["missing"] == ["no_fixture_evidence"]
