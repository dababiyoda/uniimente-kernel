"""Native Foundry appraisal binds original artifacts, never world acceptance."""
import pytest

from greg.body import Body
from greg.cognition.settlement import competence
from tests.greg_fixtures import drop, make_body, signed
from tests.integration.test_greg_foundry_extraction import _spec


def spec_for(case):
    if case == "calculation":
        return _spec("m:foundry-appraisal", 2, "run", {"language": "pricing", "source": "base_price * units",
                                                        "inputs": {"base_price": 12, "units": 3}}, "value", 36)
    if case == "journal":
        return _spec("m:foundry-appraisal", 44, "metrics", {}, "closures", 0)
    model = {"variables": {"n": [0, 1, 2]}, "initial": {"n": 0},
             "transitions": [{"name": "to1", "set": {"n": 1}}, {"name": "to2", "set": {"n": 2}}]}
    return _spec("m:foundry-appraisal", 43, "check", {"model": model, "max_states": 1}, "native_status", "UNKNOWN")


@pytest.mark.parametrize("case", ["calculation", "journal", "unknown"])
def test_foundry_scoped_snapshot_appraisal_is_separate_truthful_and_replayable(tmp_path, case):
    home, key, body_id, _ = make_body(tmp_path)
    spec = spec_for(case)
    with Body(home) as body:
        assert body.registry.state["foundry.query"] == "VERIFIED"
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "foundry.query"}))
        drop(home, signed(key, body_id, "MISSION", spec))
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED", appraisal
        assert appraisal["checks"]["world_reobserved"] is False
        assert appraisal["checks"]["applicable_observations_revalidated"] is True
        scope = appraisal["foundry_artifact_verification"][0]
        assert scope["verified"] and scope["current_world_observation"] is False
        assert scope["world_validity"] == "WORLD_UNVERIFIED" and scope["authority_created"] is False
        assert "same source implementation" in scope["shared_dependencies"]
        assert body.journal.replay("cognition.settled") == [] and competence(body.journal) == {}
        before = len(body.ledger.by_type("receipt"))
        # An observation after the original invocation cannot replace its
        # retained journal prefix during revalidation.
        body.journal.record("review.observation", {"mission_id": spec["mission_id"], "note": "later test observation"})
        assert body.appraise(spec["mission_id"])["verdict"] == "VERIFIED"
    with Body(home) as body:
        body.boot(); body.tick()
        assert len(body.ledger.by_type("receipt")) == before
        assert body.journal.replay("cognition.settled") == []


@pytest.mark.parametrize("case,attack", [
    ("calculation", "result"), ("calculation", "input"), ("calculation", "authority"),
    ("journal", "scope"), ("journal", "head"), ("unknown", "unknown_as_proof"),
])
def test_forged_foundry_artifact_cannot_hide_behind_a_passing_marker(tmp_path, case, attack):
    home, key, body_id, _ = make_body(tmp_path)
    spec = spec_for(case)
    # Keep a coarse marker true so only original-artifact appraisal detects
    # mutation, rather than the engine refusing its normal native predicate.
    spec["success_checks"][0]["predicate"] = {"op": "equals", "field": "system",
                                              "value": spec["success_checks"][0]["sensor"]["params"]["system"]}
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "foundry.query"}))
        original = body.registry.adapters["foundry.query"]

        def attacked(params, ctx):
            output = original(params, ctx)
            if attack == "result":
                output["result"]["value"] = 999
            elif attack == "input":
                output["input_digest"] = "sha256:" + "0" * 64
            elif attack == "authority":
                output["authority_created"] = True
            elif attack == "scope":
                output["scope_mission_id"] = "m:another-mission"
            elif attack == "head":
                output["journal_head"] = "sha256:" + "0" * 64
            else:
                output["result"].update(native_status="ENCODED_MODEL_EXHAUSTED", holds=True)
            return output

        body.registry.adapters["foundry.query"] = attacked
        drop(home, signed(key, body_id, "MISSION", spec))
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "REFUTED", appraisal
        assert appraisal["checks"]["world_reobserved"] is False
        assert appraisal["checks"]["applicable_observations_revalidated"] is False
        assert any("original Foundry artifact not verified" in finding for finding in appraisal["findings"])
        assert body.journal.replay("cognition.settled") == [] and competence(body.journal) == {}
