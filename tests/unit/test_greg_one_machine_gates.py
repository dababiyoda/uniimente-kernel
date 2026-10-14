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
