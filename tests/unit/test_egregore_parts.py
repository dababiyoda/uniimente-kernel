"""Detachable standing-cognition parts: shadow, bind, detach, rollback, restart.

Synthetic workload authority, not authenticated founder enrollment.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from compiler.ucl_compiler import compile_constitution
from egregore.contracts import Assessment, CandidateProposal, ContractError, SignalEnvelope
from egregore.model_parts import Envelope, extract_json, openai_compatible_proposer
from egregore.parts import PartSpec, PartsBoard
from egregore.resources import ResourceGovernor
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate, GrantIssuer
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = Path(__file__).resolve().parents[2]


def signal(event_id="event-1"):
    return SignalEnvelope.build(
        source="discord://community/main", source_event_id=event_id,
        observed_at="2026-09-27T00:00:00Z", payload={"text": "community asks for a status update"},
        evidence_refs=(f"source:{event_id}",),
    )


def rule_proposer(objective):
    def propose(signals, context):
        s = signals[0]
        return CandidateProposal.build(
            proposed_by="strategist", objective=objective, action_class="community_update",
            requested_capability="social.publish.draft", target="discord://community/main",
            consequence_class="external_contact", payload={"text": objective},
            evidence_refs=s.evidence_refs, confidence=0.8, estimated_cost_usd=0.0,
            expected_outcome="a reviewed update", source_signal_ids=(s.signal_id,))
    return propose


def evaluator(role, score=0.8, veto=False):
    def evaluate(candidate, signals, context):
        return Assessment.build(role=role, candidate_id=candidate.candidate_id, score=score,
                                confidence=0.9, veto=veto, evidence_refs=("review:test",))
    return evaluate


def spec(slot, name, open_weights=None):
    return PartSpec(slot=slot, implementation=name, version="1", provenance="tests", open_weights=open_weights)


class World:
    def __init__(self, tmp_path):
        self.compiled = compile_constitution(str(ROOT))
        self.path = str(tmp_path / "ledger")
        self.ledger = EvidenceLedger(self.compiled.constitution_hash, self.path)
        self.passports = PassportRegistry()
        self.grants = GrantIssuer()
        self.actor = self.passports.issue(
            kind="agent", creator="synthetic-test", owner_organ="kernel", legal_principal="alfonso_lopez",
            declared_capabilities=["cognition.rebind"], budget_ceiling_usd=0,
            consequence_class="internal_write").passport_id
        self.board = PartsBoard(ledger=self.ledger)

    @property
    def gate(self):
        return ConsequenceGate(compiled=self.compiled, ledger=self.ledger, passports=self.passports,
                               grants=self.grants, signer=WitnessSigner(env="development"))

    def grant_for(self, slot, part_id, mode="active"):
        proposal = self.board.change_proposal(actor=self.actor, slot=slot, part_id=part_id, mode=mode)
        return self.grants.issue_single_action(proposal=proposal, policy_version="1.0.0")

    def change(self, slot, part_id, mode="active"):
        return self.board.change(actor=self.actor, slot=slot, part_id=part_id, mode=mode,
                                 gate=self.gate, grant=self.grant_for(slot, part_id, mode))

    def reopen(self):
        self.ledger.close()
        self.ledger = EvidenceLedger(self.compiled.constitution_hash, self.path)
        self.board = PartsBoard(ledger=self.ledger)


def base(world):
    ids = {
        "guardian": world.board.register(spec("evaluator:guardian", "rules/guardian"), evaluator("guardian")),
        "treasury": world.board.register(spec("evaluator:treasury", "rules/treasury"), evaluator("treasury")),
        "old": world.board.register(spec("proposer:strategist", "rules/strategist"), rule_proposer("old plan")),
    }
    for slot, key in (("evaluator:guardian", "guardian"), ("evaluator:treasury", "treasury"),
                      ("proposer:strategist", "old")):
        world.change(slot, ids[key])
    return ids


def tick(runtime, s, trigger="tick-1"):
    runtime.ingest(s)
    return runtime.tick(trigger_id=trigger, signal_ids=(s.signal_id,),
                        resources=ResourceGovernor(max_model_calls=20, max_estimated_cost_usd=1.0))


def test_registration_grants_nothing_and_runtime_needs_required_slots(tmp_path):
    world = World(tmp_path)
    world.board.register(spec("proposer:strategist", "rules/strategist"), rule_proposer("plan"))
    assert world.board.bindings() == {}
    with pytest.raises(ContractError, match="required slots"):
        world.board.runtime()


def test_swap_part_changes_behavior_and_rollback_restores_it(tmp_path):
    world = World(tmp_path)
    ids = base(world)
    first = tick(world.board.runtime(), signal("e1"), "t1")
    assert world.board.runtime().selected_candidate(first).objective == "old plan"

    new = world.board.register(spec("proposer:strategist", "llm/qwen3.6", open_weights=True),
                               rule_proposer("new plan"))
    world.change("proposer:strategist", new)
    second = tick(world.board.runtime(), signal("e2"), "t2")
    assert world.board.runtime().selected_candidate(second).objective == "new plan"

    assert world.board.rollback_target("proposer:strategist") == ids["old"]
    world.change("proposer:strategist", ids["old"])
    third = tick(world.board.runtime(), signal("e3"), "t3")
    assert world.board.runtime().selected_candidate(third).objective == "old plan"
    assert world.board.rollback_target("proposer:strategist") is None


def test_bind_without_gate_or_with_wrong_grant_is_refused(tmp_path):
    world = World(tmp_path)
    base(world)
    new = world.board.register(spec("proposer:strategist", "llm/new"), rule_proposer("new plan"))
    with pytest.raises(ContractError, match="Gate"):
        world.board.change(actor=world.actor, slot="proposer:strategist", part_id=new)
    other = world.board.register(spec("proposer:strategist", "llm/other"), rule_proposer("other"))
    wrong = world.grant_for("proposer:strategist", other)
    with pytest.raises(ContractError, match="refused"):
        world.board.change(actor=world.actor, slot="proposer:strategist", part_id=new,
                           gate=world.gate, grant=wrong)
    assert world.board.bindings()["proposer:strategist"]["active"] != new


def test_grant_cannot_be_replayed_after_slot_moves(tmp_path):
    world = World(tmp_path)
    ids = base(world)
    new = world.board.register(spec("proposer:strategist", "llm/new"), rule_proposer("new plan"))
    stale = world.grant_for("proposer:strategist", new)
    world.change("proposer:strategist", new)
    world.change("proposer:strategist", ids["old"])
    with pytest.raises(ContractError, match="refused"):
        world.board.change(actor=world.actor, slot="proposer:strategist", part_id=new,
                           gate=world.gate, grant=stale)


def test_required_slot_cannot_be_detached_but_optional_can(tmp_path):
    world = World(tmp_path)
    base(world)
    with pytest.raises(ContractError, match="required"):
        world.board.change_proposal(actor=world.actor, slot="evaluator:guardian", part_id=None)
    world.change("proposer:strategist", None)
    assert world.board.bindings()["proposer:strategist"]["active"] is None
    cycle = tick(world.board.runtime(), signal())
    assert cycle.candidates == ()


def test_part_for_another_slot_or_unregistered_is_refused(tmp_path):
    world = World(tmp_path)
    ids = base(world)
    with pytest.raises(ContractError, match="registered for"):
        world.board.change_proposal(actor=world.actor, slot="evaluator:guardian", part_id=ids["old"])
    with pytest.raises(ContractError, match="not registered"):
        world.board.change_proposal(actor=world.actor, slot="proposer:strategist",
                                    part_id="sha256:" + "c" * 64)


def test_shadow_runs_without_influence_and_records_comparison(tmp_path):
    world = World(tmp_path)
    base(world)
    trial = world.board.register(spec("proposer:strategist", "llm/trial"), rule_proposer("trial plan"))
    strict = world.board.register(spec("evaluator:guardian", "llm/strict"), evaluator("guardian", veto=True))
    world.change("proposer:strategist", trial, mode="shadow")
    world.change("evaluator:guardian", strict, mode="shadow")

    s = signal()
    runtime = world.board.runtime()
    cycle = tick(runtime, s)
    assert runtime.selected_candidate(cycle).objective == "old plan"  # shadows had no say

    hashes = world.board.shadow_run(cycle, [s], resources=ResourceGovernor(max_model_calls=5,
                                                                           max_estimated_cost_usd=1.0))
    records = [world.ledger.find(h).payload for h in hashes]
    by_slot = {r["slot"]: r for r in records}
    assert all(r["disposition"] == "no_influence" for r in records)
    assert by_slot["proposer:strategist"]["comparison"]["identical"] is False
    assert by_slot["proposer:strategist"]["comparison"]["shadow_candidates"][0]["objective"] == "trial plan"
    row = by_slot["evaluator:guardian"]["comparison"]["assessments"][0]
    assert row["veto_agrees"] is False and row["shadow"]["veto"] is True

    world.change("proposer:strategist", trial)  # promotion clears the shadow binding
    assert world.board.bindings()["proposer:strategist"] == {"active": trial, "shadow": None}


def test_failing_shadow_is_isolated_and_budget_bounded(tmp_path):
    world = World(tmp_path)
    base(world)

    def broken(signals, context):
        raise RuntimeError("model server down")

    bad = world.board.register(spec("proposer:strategist", "llm/broken"), broken)
    world.change("proposer:strategist", bad, mode="shadow")
    s = signal()
    cycle = tick(world.board.runtime(), s)
    [h] = world.board.shadow_run(cycle, [s], resources=ResourceGovernor(max_model_calls=5,
                                                                        max_estimated_cost_usd=1.0))
    assert world.ledger.find(h).payload["failure"]["error_type"] == "RuntimeError"
    [h] = world.board.shadow_run(cycle, [s], resources=ResourceGovernor(max_model_calls=0,
                                                                        max_estimated_cost_usd=1.0))
    assert world.ledger.find(h).payload["failure"]["disposition"] == "budget_refusal"


def test_bindings_survive_restart_and_unregistered_code_is_reported(tmp_path):
    world = World(tmp_path)
    ids = base(world)
    new = world.board.register(spec("proposer:strategist", "llm/new"), rule_proposer("new plan"))
    world.change("proposer:strategist", new)
    world.reopen()
    assert world.board.bindings()["proposer:strategist"]["active"] == new
    assert world.board.rollback_target("proposer:strategist") == ids["old"]
    assert "proposer:strategist:active" in world.board.unresolved()
    with pytest.raises(ContractError, match="not registered in this process"):
        world.board.runtime()
    for s, fn in ((spec("evaluator:guardian", "rules/guardian"), evaluator("guardian")),
                  (spec("evaluator:treasury", "rules/treasury"), evaluator("treasury")),
                  (spec("proposer:strategist", "llm/new"), rule_proposer("new plan"))):
        world.board.register(s, fn)
    assert world.board.unresolved() == []
    world.board.runtime()


def test_forged_binding_record_is_ignored_on_restart(tmp_path):
    world = World(tmp_path)
    ids = base(world)
    evil = world.board.register(spec("proposer:strategist", "llm/evil"), rule_proposer("evil"))
    world.ledger.append(PartsBoard.BINDING_RECORD, {
        "source": world.board.source, "slot": "proposer:strategist", "mode": "active",
        "part_id": evil, "prior_head": "none", "objective": "sha256:" + "d" * 64,
        "authorization_hash": "sha256:" + "e" * 64})
    world.reopen()
    assert world.board.bindings()["proposer:strategist"]["active"] == ids["old"]


# ---------------------------------------------------------------------------
# Model-backed parts: any OpenAI-compatible endpoint, authority fixed by code
# ---------------------------------------------------------------------------
ENVELOPE = Envelope(action_class="community_update", requested_capability="social.publish.draft",
                    target="discord://community/main", consequence_class="external_contact")


def fake_endpoint(content, seen):
    def transport(url, headers, body, timeout):
        seen.append({"url": url, "headers": dict(headers), "body": body})
        return {"choices": [{"message": {"content": content}}]}
    return transport


def test_model_part_builds_candidates_with_code_fixed_authority(monkeypatch):
    s = signal()
    reply = "<think>reasoning</think>```json\n" + json.dumps({"candidates": [
        {"objective": "post a status update", "expected_outcome": "members informed",
         "payload": {"text": "update"}, "confidence": 0.95, "source_signal_ids": [s.signal_id],
         "evidence_refs": ["source:event-1"], "consequence_class": "read_only",
         "target": "https://attacker.example"},
        {"objective": "invented", "expected_outcome": "x", "confidence": 0.9,
         "source_signal_ids": ["sha256:" + "f" * 64]},
    ]}) + "\n```"
    seen = []
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    part_spec, propose = openai_compatible_proposer(
        role="strategist", base_url="https://api.groq.com/openai/v1/", model="llama-3.3-70b-versatile",
        envelope=ENVELOPE, api_key_env="GROQ_API_KEY", open_weights=True,
        transport=fake_endpoint(reply, seen))

    [candidate] = propose((s,), {"goal": "keep community informed"})
    assert part_spec.slot == "proposer:strategist" and part_spec.open_weights is True
    assert seen[0]["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen[0]["headers"]["Authorization"] == "Bearer gsk-test"
    assert seen[0]["body"]["model"] == "llama-3.3-70b-versatile"
    assert candidate.consequence_class == "external_contact"
    assert candidate.target == "discord://community/main"
    assert candidate.confidence == 0.5 and candidate.payload["model_confidence"] == 0.95
    assert candidate.execution_authority == "none"


def test_model_part_plugs_into_board_as_shadow(tmp_path):
    world = World(tmp_path)
    base(world)
    s = signal()
    reply = json.dumps({"candidates": [{"objective": "model plan", "expected_outcome": "ok",
                                        "confidence": 0.7, "source_signal_ids": [s.signal_id]}]})
    part_spec, propose = openai_compatible_proposer(
        role="strategist", base_url="http://localhost:11434/v1", model="qwen3.6", envelope=ENVELOPE,
        open_weights=True, transport=fake_endpoint(reply, []))
    part = world.board.register(part_spec, propose)
    world.change("proposer:strategist", part, mode="shadow")
    cycle = tick(world.board.runtime(), s)
    [h] = world.board.shadow_run(cycle, [s], resources=ResourceGovernor(max_model_calls=5,
                                                                        max_estimated_cost_usd=1.0))
    shadow = world.ledger.find(h).payload["comparison"]["shadow_candidates"]
    assert shadow[0]["objective"] == "model plan"


def test_model_part_refuses_missing_key_and_bad_replies(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    _, propose = openai_compatible_proposer(
        role="strategist", base_url="https://openrouter.ai/api/v1", model="some/model:free",
        envelope=ENVELOPE, api_key_env="OPENROUTER_API_KEY", transport=fake_endpoint("{}", []))
    with pytest.raises(ContractError, match="OPENROUTER_API_KEY"):
        propose((signal(),), {})
    _, propose = openai_compatible_proposer(
        role="strategist", base_url="http://x/v1", model="m", envelope=ENVELOPE,
        transport=fake_endpoint("no json here", []))
    with pytest.raises(ContractError, match="no JSON"):
        propose((signal(),), {})
    assert extract_json('prefix {"candidates": []} suffix') == {"candidates": []}


def test_replayed_genuine_binding_record_is_ignored_on_restart(tmp_path):
    world = World(tmp_path)
    ids = base(world)
    new = world.board.register(spec("proposer:strategist", "llm/new"), rule_proposer("new plan"))
    genuine = world.ledger.find(world.change("proposer:strategist", new)).payload
    world.change("proposer:strategist", ids["old"])  # rolled back
    world.ledger.append(PartsBoard.BINDING_RECORD, dict(genuine))  # copy the old approved change
    world.reopen()
    assert world.board.bindings()["proposer:strategist"]["active"] == ids["old"]
