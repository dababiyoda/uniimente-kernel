"""Snapshot appraisal fixtures do not represent model execution or world truth."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from greg.appraisal import _revalidate_semantic
from greg.body import Body
from greg.capabilities import BUILTINS
from greg.cognition.contracts import digest
from greg.cognition.cortex import reason, registry_view
from greg.cognition.settlement import competence, measured_outcomes
from tests.greg_fixtures import drop, make_body, mission, signed
from provenance.commit_witness import sha256_obj


def fixture_semantic(data, geometry, model_config):
    """Typed stand-in used only to prepare retained evidence; no inference call."""
    source = data["sources"][0]
    claims = [{"text": source["text"], "source_id": source["id"], "quote": source["text"], "kind": "extracted"}]
    provenance = {"requested": "fixture:semantic", "served": "fixture:semantic", "weight_digest": "a" * 64,
                  "provider": "ollama", "license": "test fixture, no real weight evidence"}
    return {"output": {"claims": claims}, "proof": {
        "sources": [{"id": s["id"], "digest": digest(s["text"])} for s in data["sources"]],
        "claims": claims, "contradictions": [], "uncertainty": "quoted source can be false; fixture is not model evidence",
        "model_provenance": provenance}, "status": "ANSWER", "formal_validity": "NOT_APPLICABLE",
        "empirical_validity": "WORLD_UNVERIFIED", "missing_information": []}


def semantic_params():
    return {"problem_id": "appraisal:semantic", "operation": "interpret",
            "data": {"sources": [{"id": "snapshot", "text": "The supplied source says the moon is made of cheese."}]}}


def check_for(params, capability="cognition.solve"):
    return {"check_id": "quote", "description": "retain the exact quoted source, without certifying its truth",
            "sensor": {"capability": capability, "target": "cognition:source-snapshot", "params": params},
            "predicate": {"op": "equals", "field": "output.claims.0.text", "value": params["data"]["sources"][0]["text"]}}


def expected_payload(check):
    sensor = check["sensor"]
    return sha256_obj({"capability": sensor["capability"], "params": sensor["params"],
                      "manifest_digest": BUILTINS[sensor["capability"]][0].digest()})


@pytest.fixture
def snapshot(monkeypatch):
    monkeypatch.setattr("greg.cognition.cortex._semantic", fixture_semantic)
    params = semantic_params()
    check = check_for(params)
    answer = reason(params, registry=registry_view())
    record = SimpleNamespace(payload={"result": {"output": answer}, "witness_id": "w1"})
    witness = SimpleNamespace(payload={"witness_id": "w1", "capability": "cognition.solve",
                                      "target": check["sensor"]["target"], "evidence_refs": ["signed-mission"],
                                      "payload_hash": expected_payload(check), "constitution_hash": "fixture-constitution"})
    journal = SimpleNamespace(ledger=SimpleNamespace(constitution_hash="fixture-constitution",
                                                     by_type=lambda kind: [witness] if kind == "witness" else []))
    return check, record, witness, journal


def rehash(answer):
    answer.pop("receipt_id", None)
    answer["receipt_id"] = digest(answer)


def test_snapshot_appraisal_never_calls_a_model_or_asserts_source_truth(snapshot, monkeypatch):
    def forbidden_model_call(*args, **kwargs):
        pytest.fail("retained semantic appraisal must not invoke inference")
    monkeypatch.setattr("greg.models.OllamaRoute.complete", forbidden_model_call)
    check, record, witness, journal = snapshot
    result = _revalidate_semantic(check, record, journal, "signed-mission")
    assert result["empirical_validity"] == "WORLD_UNVERIFIED"
    assert result["current_world_observation"] is False and result["model_reexecuted"] is False
    assert result["outcome_credit"] is False


@pytest.mark.parametrize("mutation", ["forged_digest", "wrong_provenance", "missing_provenance", "wrong_source", "refused", "refuted", "wrong_input", "wrong_witness", "wrong_witness_payload", "wrong_constitution"])
def test_semantic_snapshot_counterexamples_fail_closed(snapshot, mutation):
    check, record, witness, journal = snapshot
    answer = record.payload["result"]["output"]
    if mutation == "forged_digest":
        answer["receipt_id"] = "sha256:" + "0" * 64
    elif mutation == "wrong_provenance":
        answer["model_provenance"]["served"] = "another:model"
        answer["proof_artifact"]["model_provenance"]["served"] = "another:model"
        rehash(answer)
    elif mutation == "wrong_source":
        answer["proof_artifact"]["sources"][0]["digest"] = "sha256:" + "0" * 64
        rehash(answer)
    elif mutation == "missing_provenance":
        answer["model_provenance"] = None
        rehash(answer)
    elif mutation == "refused":
        answer.update(abstention_state="ABSTAIN", reason_code="POLICY_REFUSAL", outcome_state="ABSTAIN",
                      output=None, proof_type=None, proof_artifact=None)
        rehash(answer)
    elif mutation == "refuted":
        answer["evaluator_result"]["verdict"] = "REFUTED"
        rehash(answer)
    elif mutation == "wrong_input":
        check["sensor"]["params"]["data"]["sources"][0]["text"] = "A substituted source"
    elif mutation == "wrong_witness":
        witness.payload["capability"] = "fs.read"
    elif mutation == "wrong_witness_payload":
        witness.payload["payload_hash"] = "sha256:" + "0" * 64
    else:
        witness.payload["constitution_hash"] = "foreign-constitution"
    with pytest.raises(ValueError):
        _revalidate_semantic(check, record, journal, "signed-mission")


def test_expiry_is_rechecked_without_model_execution(snapshot):
    check, record, witness, journal = snapshot
    check["sensor"]["params"]["evidence_expires_at"] = "2030-01-01T00:00:00Z"
    answer = record.payload["result"]["output"]
    answer["input_digest"] = digest(check["sensor"]["params"])
    witness.payload["payload_hash"] = expected_payload(check)
    rehash(answer)
    with pytest.raises(ValueError, match="stale"):
        _revalidate_semantic(check, record, journal, "signed-mission", now=datetime(2031, 1, 1, tzinfo=timezone.utc))


@pytest.mark.parametrize("capability", ["cognition.solve", "cognition.semantic"])
def test_signed_semantic_mission_has_scoped_separate_process_appraisal_without_outcome_credit(tmp_path, monkeypatch, capability):
    # Real mission/witness/appraiser processes, synthetic local-model reply only.
    monkeypatch.setattr("greg.cognition.cortex._semantic", fixture_semantic)
    home, key, body_id, _ = make_body(tmp_path)
    params = semantic_params(); check = check_for(params, capability)
    spec = mission("m:semantic-snapshot", checks=[check], strategies=[], capabilities=[capability],
                   targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        assert appraisal["checks"]["world_reobserved"] is False
        assert appraisal["checks"]["applicable_observations_revalidated"] is True
        assert appraisal["semantic_snapshot_verification"][0]["model_reexecuted"] is False
        assert "no fresh-world truth" in appraisal["limits"]
        assert competence(body.journal) == {} and measured_outcomes(body.journal) == []
        assert body.journal.replay("cognition.settled") == []
        again = body.appraise(spec["mission_id"])
        assert again["verdict"] == "VERIFIED" and again["checks"]["world_reobserved"] is False
