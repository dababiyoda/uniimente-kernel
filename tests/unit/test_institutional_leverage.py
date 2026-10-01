from copy import deepcopy
from pathlib import Path

import pytest

from compiler.ucl_compiler import compile_constitution
from egregore import (
    Assessment, ContractError, ResourceGovernor, SignalEnvelope,
    StandingCognitionRuntime, propose_institutional_leverage,
)
from egregore.gate_adapter import bind_for_gate, submit_through_gate
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

HASH = "sha256:" + "a" * 64
ROOT = str(Path(__file__).resolve().parents[2])


def node(key, *, gap=0, kind="actor"):
    return dict(id=key, kind=kind, label=key, gap=gap, evidence_refs=[HASH])


def link(key, source, target, *, strength=1, confidence=1):
    return dict(id=key, source=source, target=target, mechanism="coordination",
                strength=strength, confidence=confidence, evidence_refs=[HASH])


def intervention(key, target, **changes):
    result = dict(
        id=key, node=target, mechanism="rule", effect=0.8, confidence=0.9,
        harm=0, cost_usd=10, effort_hours=0, delay_days=0,
        action=dict(action_class="draft.publish", requested_capability="draft.publish",
                    target="sandbox:outbox", consequence_class="external_contact",
                    payload={"text": "Propose a reusable eligibility checklist"}),
        expected_outcome="reviewers accept the checklist",
        success_measure="accepted records per hour rises from 10 to 15",
        rollback="restore the prior checklist",
        counterargument="reviewers may not adopt the checklist",
        evidence_refs=[HASH],
    )
    result.update(changes)
    return result


def model():
    return dict(
        nodes=[node("chair"), node("rule", kind="rule"), node("coordinator"),
               node("eligibility", gap=0.9, kind="process"),
               node("delivery", kind="outcome"), node("unrelated", gap=1)],
        links=[link("rule-coordinator", "rule", "coordinator", strength=0.9, confidence=0.9),
               link("coordinator-eligibility", "coordinator", "eligibility"),
               link("eligibility-delivery", "eligibility", "delivery"),
               link("chair-eligibility", "chair", "eligibility", strength=0.1)],
        interventions=[intervention("change-rule", "rule"),
                       intervention("ask-chair", "chair", mechanism="direct"),
                       intervention("direct-work", "eligibility", mechanism="direct", cost_usd=80)],
    )


def signal(data=None, *, event="map-1", observed_at="2026-09-23T09:00:00Z"):
    return SignalEnvelope.build(
        source="test:institutional-observations", source_event_id=event,
        observed_at=observed_at, payload={"institutional_map": data if data is not None else model()},
        evidence_refs=[HASH],
    )


def context(**changes):
    request = dict(objective="improve accepted delivery throughput", outcome_node="delivery",
                   as_of="2026-09-23T10:00:00Z", max_evidence_age_seconds=7200, budget_usd=100)
    request.update(changes)
    return {"institutional_leverage": request}


def routes(data=None, **changes):
    return propose_institutional_leverage((signal(data),), context(**changes))


def trace(candidate):
    return candidate.payload["institutional_leverage"]


def review(role, *, veto=False):
    def evaluate(candidate, signals, context):
        return Assessment.build(
            role=role, candidate_id=candidate.candidate_id,
            score=trace(candidate)["route"]["score"], confidence=0.9,
            objections=("route still needs external outcome evidence",), veto=veto,
            evidence_refs=[HASH],
        )
    return evaluate


def runtime(ledger, **changes):
    args = dict(ledger=ledger, proposers={},
                evaluators={"guardian": review("guardian"), "treasury": review("treasury")})
    args.update(changes)
    return StandingCognitionRuntime(**args)


def tick(subject, source, **changes):
    args = dict(trigger_id="leverage-1", signal_ids=[source.signal_id], context=context(),
                resources=ResourceGovernor(max_model_calls=30, max_estimated_cost_usd=1))
    args.update(changes)
    return subject.tick(**args)


def test_real_control_path_beats_visible_hierarchy_and_expensive_direct_work():
    candidates = routes()
    chosen = trace(candidates[0])
    assert chosen["bottleneck"]["node"] == "eligibility"
    assert chosen["route"]["controlling_node"] == "rule"
    assert chosen["route"]["path"] == ["rule-coordinator", "coordinator-eligibility", "eligibility-delivery"]
    assert chosen["route"]["score"] == pytest.approx(0.8 * 0.9 * 0.81 * 0.9 / 1.1)
    assert candidates[0].confidence == pytest.approx(0.81)
    assert candidates[0].payload["text"] == "Propose a reusable eligibility checklist"
    assert candidates[0].execution_authority == "none"
    assert chosen["estimate_status"] == "input_estimates_not_verified_outcomes"
    assert chosen["baseline"]["score"] == 0
    assert len(chosen["alternatives"]) == 3


@pytest.mark.parametrize("mechanism", ["direct", "rule", "incentive", "frame", "doctrine", "coordination"])
def test_every_mechanism_produces_a_concrete_gate_compatible_action(mechanism):
    data = model()
    action = intervention("route", "eligibility", mechanism=mechanism)
    if mechanism in {"frame", "doctrine"}:
        action["narrative"] = dict(
            audience="review coordinators", frame="consistent criteria reduce repeated work",
            message="Use the shared checklist to evaluate each submission.",
            desired_action="adopt the checklist",
            claims=[dict(text="the observed bottleneck is eligibility", evidence_refs=[HASH])],
        )
        action["action"]["payload"]["text"] = action["narrative"]["message"]
    data["interventions"] = [action]
    candidate = routes(data)[0]
    bound = bind_for_gate(candidate, actor="test:actor", legal_principal="alfonso_lopez")
    assert trace(candidate)["route"]["mechanism"] == mechanism
    assert bound.payload == candidate.payload
    assert bound.requested_capability == action["action"]["requested_capability"]
    if "narrative" in action:
        assert trace(candidate)["narrative"] == action["narrative"]


def test_cycles_and_duplicate_paths_do_not_multiply_influence():
    data = model()
    baseline = trace(routes(data)[0])["route"]["score"]
    data["links"] += [link("duplicate", "rule", "coordinator", strength=0.9, confidence=0.9),
                      link("cycle", "coordinator", "rule"), link("self", "rule", "rule")]
    chosen = trace(routes(data)[0])
    assert chosen["route"]["score"] == baseline
    assert "cycle" not in chosen["route"]["path"]
    assert "self" not in chosen["route"]["path"]


def test_order_independent_identity_and_no_mutation():
    data = model()
    original = deepcopy(data)
    one = routes(data)
    assert data == original
    for records in data.values():
        records.reverse()
    two = routes(data)
    assert [item.candidate_id for item in one] == [item.candidate_id for item in two]


def test_budget_and_total_hop_limit_filter_routes_without_erasing_alternatives():
    candidates = routes(budget_usd=10, max_hops=2)
    assert trace(candidates[0])["route"]["intervention_id"] == "ask-chair"
    rejected = {row["intervention_id"]: row["reason"] for row in trace(candidates[0])["alternatives"]}
    assert rejected["change-rule"] == "no_evidenced_path_to_bottleneck_within_horizon"
    assert rejected["direct-work"] == "over_budget"


def test_do_nothing_wins_over_net_harm():
    data = model()
    for item in data["interventions"]:
        item["harm"] = 1
    with pytest.raises(ContractError, match="retain current state"):
        routes(data)


def test_unrelated_gap_never_becomes_the_bottleneck():
    assert all(row["node"] != "unrelated" for row in trace(routes()[0])["bottlenecks_considered"])


@pytest.mark.parametrize("date", ["2026-09-22T00:00:00Z", "2026-09-24T00:00:00Z"])
def test_stale_or_future_map_cannot_support_a_route(date):
    with pytest.raises(ContractError, match="no fresh institutional evidence"):
        propose_institutional_leverage((signal(observed_at=date),), context())


def test_stale_signal_exclusion_is_retained_and_not_cited_as_support():
    fresh = signal()
    stale = signal(event="old", observed_at="2026-09-21T00:00:00Z")
    candidate = propose_institutional_leverage((fresh, stale), context())[0]
    assert candidate.source_signal_ids == (fresh.signal_id,)
    assert trace(candidate)["ignored_signals"] == [{"signal_id": stale.signal_id, "reason": "future_or_stale"}]


def test_conflicting_maps_fail_closed_instead_of_last_writer_wins():
    changed = model()
    changed["nodes"][0]["gap"] = 1
    with pytest.raises(ContractError, match="conflicting institutional map record"):
        propose_institutional_leverage((signal(), signal(changed, event="contradiction")), context())


@pytest.mark.parametrize("mutation", [
    lambda data: data["links"][0].update(target="missing"),
    lambda data: data["links"][0].update(confidence=True),
    lambda data: data["links"][0].update(strength=float("nan")),
    lambda data: data["nodes"][0].update(evidence_refs=["invented"]),
    lambda data: data["interventions"][0].update(mechanism="doctrine"),
    lambda data: data["interventions"][0]["action"]["payload"].update(institutional_leverage={}),
    lambda data: data["interventions"][0].update(cost_usd=-1),
    lambda data: data["interventions"][0].update(node="missing"),
])
def test_invalid_or_unsupported_inputs_refused(mutation):
    data = model()
    mutation(data)
    with pytest.raises(ContractError):
        routes(data)


def test_narrative_claim_must_cite_the_actual_signal():
    data = model()
    data["interventions"][0]["narrative"] = dict(
        audience="reviewers", frame="reduce rework", message="Use the checklist",
        desired_action="adopt", claims=[dict(text="unsupported claim", evidence_refs=["invented"])])
    with pytest.raises(ContractError, match="outside its source signal"):
        routes(data)


def test_missing_measured_gap_is_not_replaced_with_invented_bottleneck():
    data = model()
    for record in data["nodes"]:
        record["gap"] = 0
    with pytest.raises(ContractError, match="no evidenced bottleneck"):
        routes(data)


def test_aggregate_limits_hold_across_many_small_signals():
    signals = tuple(signal(dict(nodes=[node(f"n{i}")], links=[], interventions=[]), event=str(i))
                    for i in range(129))
    with pytest.raises(ContractError, match="total nodes limit"):
        propose_institutional_leverage(signals, context())


def test_builtin_runtime_path_persists_replays_and_keeps_evaluator_dissent(tmp_path):
    source = signal()
    path = str(tmp_path / "ledger.jsonl")
    ledger = EvidenceLedger(HASH, path=path)
    subject = runtime(ledger)
    subject.ingest(source)
    cycle = tick(subject, source)
    assert cycle.status.value == "proposed"
    assert trace(subject.selected_candidate(cycle))["route"]["intervention_id"] == "change-rule"
    assert all(item.objections for item in cycle.assessments)
    head = ledger.head
    ledger.close()
    restored_ledger = EvidenceLedger(HASH, path=path, expected_head=head)
    restored = runtime(restored_ledger, evaluators={})
    assert tick(restored, source).to_dict() == cycle.to_dict()
    assert restored_ledger.head == head
    assert restored_ledger.verify_chain()[0]
    restored_ledger.close()


@pytest.mark.parametrize("evaluators", [{}, {"guardian": review("guardian", veto=True), "treasury": review("treasury")}])
def test_builtin_cannot_bypass_missing_review_or_veto(evaluators):
    subject = runtime(EvidenceLedger(HASH), evaluators=evaluators)
    source = signal()
    subject.ingest(source)
    cycle = tick(subject, source)
    assert cycle.candidates
    assert cycle.status.value == "refused"
    assert cycle.selected_candidate_id is None


def test_no_request_consumes_no_builtin_budget_and_zero_budget_hibernates():
    subject = runtime(EvidenceLedger(HASH))
    source = signal()
    subject.ingest(source)
    cycle = tick(subject, source, context={})
    assert cycle.status.value == "silent"
    assert cycle.resource_snapshot["used_model_calls"] == 0
    empty = ResourceGovernor(max_model_calls=0, max_estimated_cost_usd=0)
    cycle = tick(subject, source, trigger_id="empty", resources=empty)
    assert cycle.status.value == "hibernating"
    assert not cycle.candidates


def test_no_viable_route_is_a_recorded_failure_in_existing_runtime():
    subject = runtime(EvidenceLedger(HASH))
    source = signal()
    subject.ingest(source)
    cycle = tick(subject, source, context=context(budget_usd=0))
    assert cycle.status.value == "refused"
    assert "retain current state" in cycle.failures[0]["error"]


@pytest.mark.parametrize("cost", [0, 10])
def test_route_reaches_real_gate_and_only_explicit_grant_reaches_executor(cost):
    compiled = compile_constitution(ROOT)
    ledger = EvidenceLedger(compiled.constitution_hash)
    passports = PassportRegistry()
    actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                            legal_principal="alfonso_lopez", declared_capabilities=["draft.publish"],
                            budget_ceiling_usd=100, consequence_class="external_contact")
    gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                           signer=WitnessSigner(env="development"))
    subject = runtime(ledger)
    data = model()
    for item in data["interventions"]:
        item["cost_usd"] = cost
    source = signal(data)
    subject.ingest(source)
    candidate = subject.selected_candidate(tick(subject, source))
    executed = []

    def executor(proposal):
        executed.append(proposal.payload)
        return {"observed_outcome": "synthetic checklist draft queued", "result_class": "positive"}

    args = dict(actor=actor.passport_id, legal_principal="alfonso_lopez", executor=executor)
    denied = submit_through_gate(gate, candidate, **args)
    assert denied.state == "refused"
    assert executed == []
    bound = bind_for_gate(candidate, actor=actor.passport_id, legal_principal="alfonso_lopez")
    # Test-only grant, issued outside the planner. No real outreach or deployment.
    grant = gate.grants.issue_single_action(proposal=bound, policy_version="1.0.0")
    completed = submit_through_gate(gate, candidate, standing_grant=grant, **args)
    assert completed.state == "recorded"
    assert executed == [candidate.payload]
    assert completed.receipt_hash
    assert ledger.verify_chain()[0]
