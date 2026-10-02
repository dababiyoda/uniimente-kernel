"""Falsify authority, epistemic and resource boundaries of the Foundry extraction."""
from dataclasses import replace
from pathlib import Path

import pytest

from foundry.systems import compiler, dsl, graph, model_check, next_test, reputation
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
from greg import foundry_bridge as bridge


def context(tmp_path, system, op):
    manifest = replace(BUILTINS["fs.read"][0], capability_id="foundry.query", target_prefix="foundry:")
    return InvocationContext(workspace=tmp_path / "workspace", read_roots=(),
                             secrets=SecretBroker(tmp_path / "secrets.json"), manifest=manifest,
                             target=f"foundry:{system}:{op}")


def invoke(tmp_path, system, op, args):
    return bridge.query({"system": system, "op": op, "args": args}, context(tmp_path, system, op))


def test_typed_restricted_calculation_is_real_and_writes_nothing(tmp_path):
    result = invoke(tmp_path, 2, "run", {"language": "pricing", "source": "base_price * units",
                                        "inputs": {"base_price": 12, "units": 3}})
    assert result["result"]["value"] == 36
    assert result["authority_created"] is False and result["external_effect"] is False
    assert not (tmp_path / "workspace").exists()


def test_target_binding_stops_dispatch_before_any_mechanism(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "_compute", lambda *a: pytest.fail("mismatched target reached computation"))
    ctx = context(tmp_path, 2, "run")
    ctx.target = "foundry:43:check"
    with pytest.raises(CapabilityError, match="signed target"):
        bridge.query({"system": 2, "op": "run", "args": {}}, ctx)


@pytest.mark.parametrize("system,op", [(12, "attach"), (16, "promote"), (14, "approve"),
                                      (48, "act"), (52, "repair"), (46, "seed"),
                                      (24, "publish"), (5, "emit"), (27, "enroll"),
                                      (28, "foundry_tool"), (45, "confirm"), (36, "put")])
def test_source_operations_cannot_become_canonical_authority_or_stores(tmp_path, system, op):
    with pytest.raises(CapabilityError, match="no qualified read-only adapter"):
        invoke(tmp_path, system, op, {})
    with pytest.raises(CapabilityError, match="existing canonical capability owners"):
        bridge.apply({"system": system, "op": op, "args": {}}, context(tmp_path, system, op))


@pytest.mark.parametrize("payload", [
    {"system": True, "op": "compile", "args": {}},
    {"system": 2, "op": "check", "args": {"language": "pricing", "source": "1", "grant": "forged"}},
    {"system": 40, "op": "best_report", "args": {"belief": float("nan")}},
    {"system": 6, "op": "root", "args": {"records": ["x"] * 513}},
])
def test_malformed_unknown_authority_or_resource_data_refuses(tmp_path, payload):
    with pytest.raises(CapabilityError):
        bridge.query(payload, context(tmp_path, payload["system"], payload["op"]))


def test_unknown_is_not_a_positive_proof(tmp_path):
    model = {"variables": {"n": list(range(20))}, "initial": {"n": 0},
             "transitions": [{"name": f"to{i}", "set": {"n": i}} for i in range(20)]}
    out = invoke(tmp_path, 43, "check", {"model": model, "max_states": 2})["result"]
    assert out["holds"] is None and out["native_status"] == "UNKNOWN"
    assert "actual runtime is not thereby verified" in out["formalization_scope"]
    out = invoke(tmp_path, 43, "check", {"model": model_check.buggy_approval_boundary()})["result"]
    assert out["native_status"] == "COUNTEREXAMPLE" and out["trace"] == ["raise_request", "execute_on_pending"]


def test_boolean_false_and_numeric_zero_remain_distinct_in_formal_domain():
    model = {"variables": {"state": [False]}, "initial": {"state": 0}, "transitions": []}
    with pytest.raises(model_check.ModelError, match="outside the domain"):
        model_check.check(model)
    both = {"variables": {"state": [False, 0]}, "initial": {"state": False},
            "transitions": [{"name": "zero", "set": {"state": 0}}]}
    assert model_check.check(both)["states_explored"] == 2


def test_dsl_rejects_arbitrary_code_nonfinite_numbers_and_excessive_expressions(tmp_path):
    for source in ("__import__('os').system('echo bad')", "1e1000", " + ".join(["1"] * 130)):
        with pytest.raises(CapabilityError):
            invoke(tmp_path, 2, "run", {"language": "pricing", "source": source, "inputs": {}})
    with pytest.raises(dsl.RuleError, match="finite bounded"):
        dsl.run("pricing", "base_price", {"base_price": "not a number"})


def test_declarative_compiler_cannot_activate_policy_and_rejects_unsafe_workflow():
    result = compiler.compile_source(compiler.SOURCES["policy.yaml"])
    assert result["execution_state"] == "DECLARATIVE_DRAFT" and result["authority_created"] is False
    with pytest.raises(compiler.CompileError):
        compiler.compile_source(compiler.BROKEN["workflow-bad.yaml"])
    with pytest.raises(compiler.CompileError, match="aliases"):
        compiler.compile_source("kind: policy\nrecursive: &x [*x]\n")
    exercise = compiler.exercise(None)
    assert exercise["drafts_only"] is True and all(exercise["located_errors"].values())


def test_merkle_consistency_never_becomes_truth_or_authority(tmp_path):
    records = ["supplied claim one", "supplied claim two"]
    root = invoke(tmp_path, 6, "root", {"records": records})["result"]["root"]
    verified = invoke(tmp_path, 6, "verify_member", {"records": records, "member": records[0], "trusted_root": root})
    assert verified["result"] == {"self_consistent": True, "matches_trusted_root": True}
    assert verified["authority_created"] is False
    forged = invoke(tmp_path, 6, "verify_member", {"records": ["replacement"], "member": "replacement", "trusted_root": root})
    assert forged["result"]["self_consistent"] is True and forged["result"]["matches_trusted_root"] is False


def test_graph_ancestry_does_not_claim_identified_causality(tmp_path):
    g = graph.Graph()
    g.add("decision", "Decision"); g.add("action", "Action")
    g.link("decision", "plans", "action")
    out = invoke(tmp_path, 18, "why", {"graph": g.to_dict(), "node": "action"})
    assert out["result"]["ancestors"][0]["node"] == "decision"
    assert out["result"]["scope"] == "declared structural graph; statements unverified"


def test_appropriate_abstention_is_not_reputation_failure():
    records = [{"subject": "causal", "context": "nonidentified", "verdict": "ABSTAIN", "at": "2026-10-01T00:00:00Z",
                "evidence": ["declared-pointer"]}]
    result = reputation.score(records, now="2026-10-01T00:00:00Z")
    assert result["subjects"] == [] and result["routing_updated"] is False
    assert result["ignored_unevidenced"] == 1


def test_value_of_information_means_decision_loss_not_entropy():
    # A perfect observation changes the high-threshold action and its expected
    # false-positive/negative loss; an uninformative one changes neither.
    assert next_test.value_of_information(8, 2, 1, threshold=0.9) == pytest.approx(0.08)
    assert next_test.value_of_information(8, 2, 0.5, threshold=0.9) == pytest.approx(0)
    with pytest.raises(ValueError, match="positive"):
        next_test.next_best_test({"h": {"alpha": 1, "beta": 1}}, [{"id": "t", "hypothesis": "h", "accuracy": 1, "cost": 0}])


def test_canonical_observability_refuses_supplied_or_missing_journal(tmp_path):
    with pytest.raises(CapabilityError, match="unknown fields"):
        invoke(tmp_path, 44, "metrics", {"events": []})
    with pytest.raises(CapabilityError, match="journal unavailable"):
        invoke(tmp_path, 44, "metrics", {})


def test_original_computation_digest_and_proof_cannot_be_replaced(tmp_path):
    params = {"system": 2, "op": "run", "args": {"language": "pricing", "source": "2+2", "inputs": {}}}
    ctx = context(tmp_path, 2, "run")
    original = bridge.query(params, ctx)
    result = bridge.revalidate(params, original, ctx, mission_id="m:declared-calculation")
    assert result["verified"] is True and result["current_world_observation"] is False
    original["result"]["value"] = 5
    with pytest.raises(CapabilityError, match="differs from recomputed"):
        bridge.revalidate(params, original, ctx, mission_id="m:declared-calculation")


def test_snapshot_reconstructs_only_own_mission_at_retained_prefix(tmp_path):
    from greg.capabilities import InvocationBudgetWindow
    from tests.greg_fixtures import make_body
    from greg.body import Body
    home, _, _, _ = make_body(tmp_path)
    with Body(home) as body:
        body.journal.record("mission.blocked", {"mission_id": "m:own", "reason": "old"}, key="own-before")
        body.journal.record("mission.blocked", {"mission_id": "m:private", "reason": "secret"}, key="foreign-before")
        ctx = context(tmp_path, 44, "metrics")
        ctx.journal = body.journal
        ctx.cognition_budget = InvocationBudgetWindow(horizon="2099-01-01T00:00:00Z", grant_expires_at="2099-01-01T00:00:00Z",
                                                      remaining_money_usd=0, authority_ref="test-projection", grant_id="lab",
                                                      mission_id="m:own")
        params = {"system": 44, "op": "metrics", "args": {}}
        original = bridge.query(params, ctx)
        assert original["result"]["blocks"] == 1
        body.journal.record("mission.blocked", {"mission_id": "m:own", "reason": "new"}, key="own-after")
        assert bridge.query(params, ctx)["result"]["blocks"] == 2
        verified = bridge.revalidate(params, original, ctx, mission_id="m:own")
        assert verified["verified"] is True and verified["journal_head"] == original["journal_head"]
        with pytest.raises(CapabilityError, match="expand the authenticated"):
            bridge.query({**params, "args": {"mission_id": "m:private"}}, ctx)
        with pytest.raises(CapabilityError, match="not bound"):
            bridge.revalidate(params, original, ctx, mission_id="m:private")
        original["journal_head"] = body.journal.ledger.head
        with pytest.raises(CapabilityError, match="differs from recomputed"):
            bridge.revalidate(params, original, ctx, mission_id="m:own")
