"""Capability Genesis Loop: deficit -> diagnosis -> discovery -> ladder -> shadow -> dossier -> ratify.

Synthetic workload authority, not authenticated founder enrollment. No real model.
Includes regression tests for the 2026-10-13 review: identity, trial acceptance,
effective stop, typed failures, legitimate refusal, discovery evidence, ladder exception,
mission link, and measured reuse.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from compiler.ucl_compiler import compile_constitution
from egregore.contracts import Assessment, CandidateProposal, ChangeProposal, ContractError, SignalEnvelope
from egregore.failures import DoctrinalRefusal
from egregore.genesis import (
    LADDER,
    BoardSpecsSource,
    CapabilityDeficit,
    CapabilityGenesis,
    CaseState,
    CommissionSource,
    DeficitDetector,
    OpenSourceCatalogSource,
    RetainedGenomeSource,
    diagnose,
)
from egregore.parts import PartSpec, PartsBoard
from egregore.resources import ResourceGovernor
from egregore.runtime import CycleStatus
from evolution.capsule import VerifierRecord
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate, GrantIssuer
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = Path(__file__).resolve().parents[2]


def signal(event_id="event-1"):
    return SignalEnvelope.build(
        source="discord://community/main", source_event_id=event_id,
        observed_at="2026-10-13T00:00:00Z", payload={"text": "community asks for a status update"},
        evidence_refs=(f"source:{event_id}",),
    )


def rule_proposer(objective, role="strategist", *, evidence=True, confidence=0.8):
    def propose(signals, context):
        s = signals[0]
        return CandidateProposal.build(
            proposed_by=role, objective=objective, action_class="community_update",
            requested_capability="social.publish.draft", target="discord://community/main",
            consequence_class="external_contact", payload={"text": objective},
            evidence_refs=s.evidence_refs if evidence else (), confidence=confidence, estimated_cost_usd=0.0,
            expected_outcome="a reviewed update", source_signal_ids=(s.signal_id,))
    return propose


def failing_proposer(exc=None):
    def propose(signals, context):
        raise exc or RuntimeError("boom")
    return propose


def evaluator(role, score=0.8, veto=False, objections=()):
    def evaluate(candidate, signals, context):
        return Assessment.build(role=role, candidate_id=candidate.candidate_id, score=score,
                                confidence=0.9, veto=veto, objections=objections, evidence_refs=("review:test",))
    return evaluate


def spec(slot, name):
    return PartSpec(slot=slot, implementation=name, version="1", provenance="tests")


HUMAN = VerifierRecord(level="qualified_human_review", evidence="founder read the dossier", decided_by="alfonso")
MODEL_REVIEW = VerifierRecord(level="independent_model_review", evidence="second model agreed", decided_by="model-b")
SELF = VerifierRecord(level="same_model_critique", evidence="model liked itself", decided_by="model")


class World:
    def __init__(self, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.compiled = compile_constitution(str(ROOT))
        self.path = str(tmp_path / "ledger")
        self.catalog = tmp_path / "catalog.json"
        self.catalog.write_text(json.dumps({"repositories": [
            {"repo": "example/local-drafter", "license": "MIT", "archived": False, "stars": 10,
             "pushed_at": "2026-09-01T00:00:00Z"},
            {"repo": "example/dead", "license": "MIT", "archived": True, "stars": 1},
        ]}))
        self.ledger = EvidenceLedger(self.compiled.constitution_hash, self.path)
        self.passports = PassportRegistry()
        self.grants = GrantIssuer()
        self.actor = self.passports.issue(
            kind="agent", creator="synthetic-test", owner_organ="kernel", legal_principal="alfonso_lopez",
            declared_capabilities=["cognition.rebind"], budget_ceiling_usd=0,
            consequence_class="internal_write").passport_id
        self._open()

    def _open(self):
        self.board = PartsBoard(ledger=self.ledger)
        self.genesis = CapabilityGenesis(ledger=self.ledger, board=self.board)
        self.genesis.sources = [RetainedGenomeSource(self.genesis), BoardSpecsSource(self.board),
                                OpenSourceCatalogSource(self.catalog), CommissionSource()]

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
        self._open()

    def register_all(self, strategist=None, guardian=None):
        ids = {
            "guardian": self.board.register(spec("evaluator:guardian", "rules/guardian"), guardian or evaluator("guardian")),
            "treasury": self.board.register(spec("evaluator:treasury", "rules/treasury"), evaluator("treasury")),
        }
        if strategist is not None:
            ids["strategist"] = self.board.register(spec("proposer:strategist", "rules/strategist"), strategist)
        return ids

    def base(self, strategist=None, guardian=None):
        ids = self.register_all(strategist or failing_proposer(), guardian)
        for slot, key in (("evaluator:guardian", "guardian"), ("evaluator:treasury", "treasury"),
                          ("proposer:strategist", "strategist")):
            self.change(slot, ids[key])
        return ids

    def ticks(self, n, *, prefix="t", resources=None):
        runtime = self.board.runtime()
        cycles = []
        for i in range(n):
            s = signal(f"{prefix}-{i}")
            runtime.ingest(s)
            cycles.append(runtime.tick(
                trigger_id=f"{prefix}-{i}", signal_ids=(s.signal_id,),
                resources=resources() if resources else ResourceGovernor(max_model_calls=20, max_estimated_cost_usd=1.0)))
        return runtime, cycles

    def shadow_and_trial(self, case_id, part, n=3, *, prefix="trial"):
        self.genesis.shadow(case_id, part, actor=self.actor, gate=self.gate,
                            grant=self.grant_for(self.genesis.case(case_id)["candidates"][part]["slot"], part, "shadow"))
        return self.trial(case_id, part, n, prefix=prefix)

    def trial(self, case_id, part, n=3, *, prefix="trial"):
        hashes = []
        _, cycles = self.ticks(n, prefix=prefix)
        for i, cycle in enumerate(cycles):
            hashes += self.board.shadow_run(cycle, [signal(f"{prefix}-{i}")],
                                            resources=ResourceGovernor(max_model_calls=5, max_estimated_cost_usd=1.0))
        return self.genesis.record_trials(case_id, part, hashes)

    def ratify(self, case_id, part, decision="retain", verifier=HUMAN, **kw):
        slot = self.genesis.case(case_id)["candidates"][part]["slot"]
        args = dict(decision=decision, reason="r", verifier=verifier, actor=self.actor,
                    reviewed_dossier_hash=self.genesis.dossier(case_id, part)["dossier_hash"])
        if decision == "retain":
            args.update(gate=self.gate, grant=self.grant_for(slot, part, "active"))
        args.update(kw)
        return self.genesis.ratify(case_id, part, **args)


def open_case(world, kind="component_failure", mission=None, prefix="t"):
    _, cycles = world.ticks(3, prefix=prefix)
    deficit = next(d for d in DeficitDetector(min_occurrences=3).scan(cycles) if d.kind == kind)
    case_id = world.genesis.observe(deficit, mission=mission)
    world.genesis.diagnose_case(case_id, cycles)
    return case_id, deficit, cycles


def searched(world, case_id, upto):
    """Ladder entries citing the case's discovery for every rung below ``upto``."""
    disc = world.genesis.case(case_id)["discovery"][-1]
    ladder = {}
    for rung in LADDER[:LADDER.index(upto)]:
        if rung in disc["rungs"] and not disc["rungs"][rung]["leads"]:
            ladder[rung] = {"outcome": "searched_none", "evidence": [disc["hash"]]}
        else:
            ladder[rung] = {"outcome": "not_applicable", "evidence": ["no source covers this rung in sandbox"]}
    return ladder


# ---------------------------------------------------------------------------
# Deficit detection
# ---------------------------------------------------------------------------
def test_detector_silent_below_threshold_and_content_addressed(tmp_path):
    world = World(tmp_path)
    world.base()
    _, cycles = world.ticks(2)
    assert DeficitDetector(min_occurrences=3, window=10).scan(cycles) == []
    _, more = world.ticks(1, prefix="u")
    found = DeficitDetector(min_occurrences=3, window=10).scan(cycles + more)
    assert {(d.kind, d.scope) for d in found} == {("component_failure", "proposer:strategist"),
                                                  ("refusal_streak", "runtime")}
    deficit = next(d for d in found if d.kind == "component_failure")
    assert CapabilityDeficit.from_dict(deficit.to_dict()).deficit_id == deficit.deficit_id
    with pytest.raises(ContractError):
        CapabilityDeficit.from_dict({**deficit.to_dict(), "deficit_id": "sha256:" + "0" * 64})


def test_detector_sees_budget_refusals_vetoes_and_status_streaks(tmp_path):
    world = World(tmp_path)
    world.base(rule_proposer("plan"), evaluator("guardian", veto=True))
    _, refused = world.ticks(3)
    assert all(c.status == CycleStatus.REFUSED for c in refused)
    kinds = {(d.kind, d.scope) for d in DeficitDetector(min_occurrences=3).scan(refused)}
    assert ("refusal_streak", "runtime") in kinds and ("veto_streak", "evaluator:guardian") in kinds
    _, starved = world.ticks(3, prefix="b", resources=lambda: ResourceGovernor(max_model_calls=1,
                                                                               max_estimated_cost_usd=1.0))
    assert ("budget_refusal", "evaluator:guardian") in {(d.kind, d.scope) for d in DeficitDetector().scan(starved)}
    world.change("proposer:strategist", None)
    _, silent = world.ticks(3, prefix="s")
    assert {d.kind for d in DeficitDetector().scan(silent)} == {"silence_streak"}


# ---------------------------------------------------------------------------
# Observe, diagnose (legitimate refusal vs functional failure)
# ---------------------------------------------------------------------------
def test_observe_is_idempotent_counts_recurrence_and_survives_restart(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, deficit, _ = open_case(world)
    assert world.genesis.observe(deficit) == case_id
    assert world.genesis.case(case_id)["recurrence"] == 2
    world.reopen()
    assert world.genesis.case(case_id)["recurrence"] == 2
    assert world.genesis.case(case_id)["diagnosis"]["responsible"] == "component"


def test_component_failure_is_attributed_by_typed_class_not_message(tmp_path):
    world = World(tmp_path)
    world.base(failing_proposer(ConnectionRefusedError("connection refused")))
    case_id, _, _ = open_case(world)
    diag = world.genesis.case(case_id)["diagnosis"]
    assert diag["responsible"] == "infrastructure" and not diag["replacement_warranted"]
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    world.genesis.discover(case_id)
    with pytest.raises(ContractError, match="replacement is not warranted"):
        world.genesis.propose(case_id, ladder={**searched(world, case_id, "reconfigure_compose"),
                                               "reconfigure_compose": "candidate"},
                              candidates=[{"part_id": fix, "slot": "proposer:strategist",
                                           "rung": "reconfigure_compose", "rationale": "r"}], proposed_by="alfonso")
    world2 = World(tmp_path / "policy")
    world2.base(failing_proposer(DoctrinalRefusal("prohibited by policy")))
    case2, _, _ = open_case(world2)
    diag2 = world2.genesis.case(case2)["diagnosis"]
    assert diag2["responsible"] == "policy" and diag2["legitimate_refusal"]


def test_guardian_vetoing_with_objections_is_working_and_is_not_replaced(tmp_path):
    world = World(tmp_path)
    world.base(rule_proposer("risky plan"), evaluator("guardian", veto=True, objections=("no evidence of consent",)))
    case_id, _, _ = open_case(world, kind="veto_streak")
    diag = world.genesis.case(case_id)["diagnosis"]
    assert diag["responsible"] == "proposal" and diag["legitimate_refusal"] is True
    assert diag["replacement_warranted"] is False  # scope is the evaluator; the proposal is at fault
    lenient = world.board.register(spec("evaluator:guardian", "rules/lenient"), evaluator("guardian"))
    world.genesis.discover(case_id)
    with pytest.raises(ContractError, match="not warranted"):
        world.genesis.propose(case_id, ladder={**searched(world, case_id, "reconfigure_compose"),
                                               "reconfigure_compose": "candidate"},
                              candidates=[{"part_id": lenient, "slot": "evaluator:guardian",
                                           "rung": "reconfigure_compose", "rationale": "r"}], proposed_by="alfonso")
    # an evidence-bearing override is the human's prerogative and is recorded
    world.genesis.propose(case_id, ladder={**searched(world, case_id, "reconfigure_compose"),
                                           "reconfigure_compose": "candidate"},
                          candidates=[{"part_id": lenient, "slot": "evaluator:guardian",
                                       "rung": "reconfigure_compose", "rationale": "r"}], proposed_by="alfonso",
                          override={"reason": "guardian rule is stale", "evidence": ["review:ADR-7"]})
    assert world.ledger.records[-1].payload["override"]["reason"] == "guardian rule is stale"


def test_unexplained_vetoes_against_peer_approval_point_at_the_evaluator(tmp_path):
    world = World(tmp_path)
    world.base(rule_proposer("sound plan"), evaluator("guardian", veto=True))  # vetoes without objections
    case_id, _, _ = open_case(world, kind="veto_streak")
    diag = world.genesis.case(case_id)["diagnosis"]
    assert diag["responsible"] == "evaluator" and diag["replace_slots"] == ["evaluator:guardian"]


def test_refusal_streak_from_under_evidenced_candidates_is_an_evidence_problem(tmp_path):
    world = World(tmp_path)
    world.base(rule_proposer("plan", evidence=False, confidence=0.3),
               evaluator("guardian", veto=True, objections=("cite evidence",)))
    case_id, _, _ = open_case(world, kind="refusal_streak")
    diag = world.genesis.case(case_id)["diagnosis"]
    assert diag["responsible"] == "evidence" and diag["legitimate_refusal"]


# ---------------------------------------------------------------------------
# Discovery and the evidence-bearing ladder
# ---------------------------------------------------------------------------
def test_discovery_records_leads_per_rung_with_source_and_license(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _, _ = open_case(world)
    h = world.genesis.discover(case_id)
    disc = world.ledger.find(h).payload["discovery"]
    assert disc["slots"] == ["proposer:strategist"]
    assert disc["rungs"]["existing_capability"]["leads"] == []
    assert disc["rungs"]["reconfigure_compose"]["leads"] == []  # only the active failing part is described
    repos = {l["repo"]: l for l in disc["rungs"]["open_source"]["leads"]}
    assert repos["example/local-drafter"]["license"] == "MIT" and "example/dead" not in repos
    assert {l["rung"] for l in disc["rungs"]["coding_agent_team"]["leads"]} == {"coding_agent_team"}
    assert world.genesis.case(case_id)["metrics"]["rungs_searched"] == 5


def test_searched_none_must_cite_a_discovery_that_found_nothing(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _, _ = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    cand = [{"part_id": fix, "slot": "proposer:strategist", "rung": "open_source", "rationale": "r"}]
    with pytest.raises(ContractError, match="needs evidence"):
        world.genesis.propose(case_id, ladder={"existing_capability": "searched_none"}, candidates=[], proposed_by="a")
    with pytest.raises(ContractError, match="must cite a discovery record"):
        world.genesis.propose(case_id, ladder={"existing_capability": {"outcome": "searched_none",
                                                                       "evidence": ["I looked"]}},
                              candidates=[], proposed_by="a")
    h = world.genesis.discover(case_id)  # finds the fix as a reconfigure_compose lead
    with pytest.raises(ContractError, match="found leads for 'reconfigure_compose'"):
        world.genesis.propose(case_id, ladder={
            "existing_capability": {"outcome": "searched_none", "evidence": [h]},
            "reconfigure_compose": {"outcome": "searched_none", "evidence": [h]},
            "commodity_infrastructure": {"outcome": "not_applicable", "evidence": ["n/a"]},
            "open_source": "candidate"}, candidates=cand, proposed_by="a")


def test_ladder_admission_and_documented_exception(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _, _ = open_case(world)
    world.genesis.discover(case_id)
    cheap = world.board.register(spec("proposer:strategist", "rules/cheap"), rule_proposer("cheap"))
    novel = world.board.register(spec("proposer:strategist", "arch/novel"), rule_proposer("novel"))
    base_ladder = searched(world, case_id, "new_architecture")
    base_ladder["reconfigure_compose"] = "candidate"  # discovery now lists `cheap`
    both = [{"part_id": cheap, "slot": "proposer:strategist", "rung": "reconfigure_compose", "rationale": "r"},
            {"part_id": novel, "slot": "proposer:strategist", "rung": "new_architecture", "rationale": "r"}]
    with pytest.raises(ContractError, match="every cheaper rung"):
        world.genesis.propose(case_id, ladder={"new_architecture": "candidate"}, candidates=both[1:], proposed_by="a")
    with pytest.raises(ContractError, match="evidence-bearing exception"):
        world.genesis.propose(case_id, ladder={**base_ladder, "new_architecture": "candidate"},
                              candidates=both, proposed_by="a")
    with pytest.raises(ContractError, match="needs evidence"):
        world.genesis.propose(case_id, ladder={**base_ladder, "new_architecture": "candidate"}, candidates=both,
                              proposed_by="a", exceptions={"new_architecture": {"reason": "faster"}})
    world.genesis.propose(case_id, ladder={**base_ladder, "new_architecture": "candidate"}, candidates=both,
                          proposed_by="a", exceptions={"new_architecture": {
                              "reason": "cheap part fails the latency floor", "evidence": ["bench:latency-2026-10"]}})
    case = world.genesis.case(case_id)
    assert set(case["candidates"]) == {cheap, novel}
    assert case["exceptions"]["new_architecture"]["evidence"] == ["bench:latency-2026-10"]


def test_commission_goes_through_the_existing_change_proposal_path(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _, _ = open_case(world)
    change = ChangeProposal.build(proposed_by="alfonso", base_state_hash=world.ledger.records[-1].hash,
                                  patch={"add": "proposer that reads the status board"}, rationale="no part exists",
                                  tests=["tests/unit/test_status_proposer.py"], rollback="unregister the part")
    h = world.genesis.commission(case_id, change)
    assert world.ledger.find(h).record_type == "egregore.change_proposed"
    assert world.genesis.case(case_id)["commissions"] == [change.change_id]


# ---------------------------------------------------------------------------
# Trial acceptance: failures are evidence, never success
# ---------------------------------------------------------------------------
def propose_fix(world, case_id, fix, rung="reconfigure_compose"):
    world.genesis.discover(case_id)
    ladder = searched(world, case_id, rung)
    ladder[rung] = "candidate"
    world.genesis.propose(case_id, ladder=ladder, proposed_by="alfonso",
                          candidates=[{"part_id": fix, "slot": "proposer:strategist", "rung": rung, "rationale": "r"}])


def test_three_timeouts_never_make_a_case_ready_or_retainable(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _, _ = open_case(world)
    slow = world.board.register(spec("proposer:strategist", "llm/slow"), failing_proposer(TimeoutError("read timeout")))
    propose_fix(world, case_id, slow)
    agg = world.shadow_and_trial(case_id, slow)
    assert agg["attempts"] == 3 and agg["successes"] == 0 and agg["failure_classes"] == {"transient": 3}
    assert agg["target_evidence"]["met"] is False
    assert world.genesis.case(case_id)["state"] == CaseState.TRIALING.value
    with pytest.raises(ContractError, match="successful evaluations"):
        world.ratify(case_id, slow)


def test_readiness_needs_distinct_successful_restorations(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _, _ = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    propose_fix(world, case_id, fix)
    world.shadow_and_trial(case_id, fix, n=2)
    assert world.genesis.case(case_id)["state"] == CaseState.TRIALING.value
    agg = world.trial(case_id, fix, n=1, prefix="more")
    assert agg["successes"] == 3 and agg["restorations"] == 3 and len(agg["success_cycles"]) == 3
    assert agg["target_evidence"] == {"kind": "component_failure", "mechanical": True, "met": True,
                                      "measure": "3 shadow outputs in cycles where the active part produced none (need 3)"}
    assert world.genesis.case(case_id)["state"] == CaseState.READY.value


def test_non_mechanical_target_needs_a_strong_verifier(tmp_path):
    world = World(tmp_path)
    world.base(rule_proposer("sound plan"), evaluator("guardian", veto=True))  # evaluator at fault
    case_id, _, _ = open_case(world, kind="veto_streak")
    fair = world.board.register(spec("evaluator:guardian", "rules/fair"), evaluator("guardian"))
    world.genesis.discover(case_id)
    ladder = searched(world, case_id, "reconfigure_compose") | {"reconfigure_compose": "candidate"}
    world.genesis.propose(case_id, ladder=ladder, proposed_by="alfonso",
                          candidates=[{"part_id": fair, "slot": "evaluator:guardian", "rung": "reconfigure_compose",
                                       "rationale": "r"}])
    agg = world.shadow_and_trial(case_id, fair)
    assert agg["successes"] == 3 and agg["target_evidence"]["mechanical"] is False
    assert world.genesis.case(case_id)["state"] == CaseState.READY.value
    with pytest.raises(ContractError, match="strong independent verifier"):
        world.ratify(case_id, fair, verifier=MODEL_REVIEW)
    world.ratify(case_id, fair, verifier=HUMAN)
    assert world.board.bindings()["evaluator:guardian"]["active"] == fair


def test_retain_is_refused_on_weak_verifier_stale_dossier_or_doctrine(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _, _ = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    propose_fix(world, case_id, fix)
    world.shadow_and_trial(case_id, fix)
    stale = world.genesis.dossier(case_id, fix)["dossier_hash"]
    world.trial(case_id, fix, n=1, prefix="more")
    with pytest.raises(ContractError, match="dossier changed"):
        world.ratify(case_id, fix, reviewed_dossier_hash=stale)
    with pytest.raises(ContractError, match="may not authorize retain"):
        world.ratify(case_id, fix, verifier=SELF)

    world2 = World(tmp_path / "two")
    world2.base()
    case2, _, _ = open_case(world2)
    doctrinal = world2.board.register(spec("proposer:strategist", "rules/doctrinal"),
                                      failing_proposer(DoctrinalRefusal("policy refused this class")))
    propose_fix(world2, case2, doctrinal)
    agg = world2.shadow_and_trial(case2, doctrinal)
    assert agg["failure_classes"] == {"doctrinal_refusal": 3}
    with pytest.raises(ContractError):  # never retainable: zero successes and a doctrinal refusal
        world2.ratify(case2, doctrinal)


# ---------------------------------------------------------------------------
# Stop is effective; records are safe
# ---------------------------------------------------------------------------
def test_kill_and_close_stop_shadow_execution_and_keep_safeguards(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _, _ = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    propose_fix(world, case_id, fix)
    world.shadow_and_trial(case_id, fix, n=1)
    assert world.board.bindings()["proposer:strategist"]["shadow"] == fix
    world.ratify(case_id, fix, decision="kill", verifier=SELF)
    assert world.board.bindings()["proposer:strategist"]["shadow"] is None
    assert world.board.bindings()["evaluator:guardian"]["active"] is not None
    assert world.ledger.records[-1].record_type == PartsBoard.SHADOW_STOP_RECORD
    _, [cycle] = world.ticks(1, prefix="after")
    assert world.board.shadow_run(cycle, [signal("after-0")],
                                  resources=ResourceGovernor(max_model_calls=5, max_estimated_cost_usd=1.0)) == []
    world.reopen()
    assert world.board.bindings()["proposer:strategist"]["shadow"] is None
    assert world.genesis.case(case_id)["state"] == CaseState.KILLED.value

    world2 = World(tmp_path / "close")
    world2.base()
    case2, _, _ = open_case(world2)
    fix2 = world2.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    propose_fix(world2, case2, fix2)
    world2.shadow_and_trial(case2, fix2, n=1)
    world2.genesis.close(case2, actor=world2.actor, reason="superseded")
    assert world2.board.bindings()["proposer:strategist"]["shadow"] is None


def test_forged_retained_decision_is_ignored_on_restart(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _, _ = open_case(world)
    evil = world.board.register(spec("proposer:strategist", "rules/evil"), rule_proposer("evil"))
    world.ledger.append(CapabilityGenesis.DECISION_RECORD, {
        "source": world.genesis.source, "case_id": case_id, "slot": "proposer:strategist", "part_id": evil,
        "decision": "retain", "reason": "forged", "actor": "nobody", "binding_hash": "sha256:" + "e" * 64,
        "dossier_hash": "sha256:" + "d" * 64})
    world.reopen()
    assert world.genesis.case(case_id)["state"] == CaseState.OPEN.value
    assert world.genesis.reuse_candidates("proposer:strategist") == []


def test_trial_aggregation_rejects_foreign_shadow_results(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _, _ = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    propose_fix(world, case_id, fix)
    strict = world.board.register(spec("evaluator:guardian", "rules/strict"), evaluator("guardian", veto=True))
    world.change("evaluator:guardian", strict, "shadow")
    _, [cycle] = world.ticks(1, prefix="f")
    [foreign] = world.board.shadow_run(cycle, [signal("f-0")],
                                       resources=ResourceGovernor(max_model_calls=5, max_estimated_cost_usd=1.0))
    with pytest.raises(ContractError, match="another slot or part"):
        world.genesis.record_trials(case_id, fix, [foreign])
    with pytest.raises(ContractError, match="not a shadow_result"):
        world.genesis.record_trials(case_id, fix, [world.ledger.records[0].hash])


# ---------------------------------------------------------------------------
# End to end: a mission pauses, a capability forms, the mission resumes; a second
# case reuses the capability with measurably less effort
# ---------------------------------------------------------------------------
def test_mission_pauses_capability_forms_mission_resumes_and_second_case_reuses_it(tmp_path):
    world = World(tmp_path)
    world.base()
    mission = {"goal_id": "goal-status-updates", "objective": "keep the community informed weekly",
               "parent_trigger_id": "temporal:goal:2026-10-13"}

    # Mission A: the strategist is dead; a new local drafter is adopted from the open-source rung.
    case_a, _, _ = open_case(world, mission=mission, prefix="a")
    assert world.ledger.by_type(CapabilityGenesis.MISSION_PAUSE_RECORD)[-1].payload["goal_id"] == mission["goal_id"]
    disc_a = world.genesis.discover(case_a)
    drafter = world.board.register(
        PartSpec(slot="proposer:strategist", implementation="example/local-drafter", version="0.1",
                 provenance="catalog.json:example/local-drafter", open_weights=True, notes="MIT"),
        rule_proposer("drafted plan"))
    ladder = {
        "existing_capability": {"outcome": "searched_none", "evidence": [disc_a]},
        "reconfigure_compose": {"outcome": "searched_none", "evidence": [disc_a]},
        "commodity_infrastructure": {"outcome": "not_applicable", "evidence": ["drafting is not infrastructure"]},
        "open_source": "candidate",
    }
    world.genesis.propose(case_a, ladder=ladder, proposed_by="alfonso",
                          candidates=[{"part_id": drafter, "slot": "proposer:strategist", "rung": "open_source",
                                       "rationale": "MIT drafter from the audited catalog"}])
    world.shadow_and_trial(case_a, drafter, prefix="trial-a")
    world.ratify(case_a, drafter)
    a = world.genesis.case(case_a)
    assert a["state"] == CaseState.RETAINED.value
    assert a["missions"][0]["resumed_with"] == "retain"
    resume = world.ledger.by_type(CapabilityGenesis.MISSION_RESUME_RECORD)[-1].payload
    assert resume["goal_id"] == mission["goal_id"] and resume["genome"] == a["decision"]["genome"]
    _, after = world.ticks(3, prefix="verify-a")
    outcome = world.genesis.verify_outcome(case_a, after)
    assert outcome["recurred"] is False and outcome["verification"].startswith("internal")
    assert world.board.runtime().selected_candidate(after[0]).objective == "drafted plan"

    # Mission B: the founder rolls back to the old part; it fails again; the retained
    # capability is now the cheapest lead and is reused.
    world.change("proposer:strategist", world.board.rollback_target("proposer:strategist"))
    case_b, _, _ = open_case(world, mission={**mission, "parent_trigger_id": "temporal:goal:2026-10-20"}, prefix="b")
    disc_b_hash = world.genesis.discover(case_b)
    leads = world.ledger.find(disc_b_hash).payload["discovery"]["rungs"]["existing_capability"]["leads"]
    assert any(l.get("part_id") == drafter and l["resolved"] for l in leads)
    world.genesis.propose(case_b, ladder={"existing_capability": "candidate"}, proposed_by="alfonso",
                          candidates=[{"part_id": drafter, "slot": "proposer:strategist",
                                       "rung": "existing_capability", "rationale": "retained by case A"}])
    world.shadow_and_trial(case_b, drafter, prefix="trial-b")
    world.ratify(case_b, drafter)
    b = world.genesis.case(case_b)
    assert b["state"] == CaseState.RETAINED.value and b["metrics"]["reused_capability"] is True

    # Measured: reuse lowers search depth and registration effort at equal reliability.
    depth = lambda c: LADDER.index(next(iter(c["candidates"].values()))["rung"])
    assert depth(b) < depth(a)
    assert b["metrics"]["ledger_records"] <= a["metrics"]["ledger_records"]
    assert b["metrics"]["trial_successes"] == b["metrics"]["trial_attempts"] == 3
    assert a["metrics"]["trial_successes"] == a["metrics"]["trial_attempts"] == 3
    registrations = [r for r in world.ledger.by_type(PartsBoard.REGISTER_RECORD)
                     if r.payload["part"]["part_id"] == drafter]
    assert len(registrations) == 1  # no new code was written or registered for case B

    world.reopen()
    assert world.genesis.case(case_b)["state"] == CaseState.RETAINED.value
    [reuse] = world.genesis.reuse_candidates("proposer:strategist")[:1]
    assert reuse["resolved"] is False  # code must be re-registered; never guessed


# ---------------------------------------------------------------------------
# Acceptance guards proven load-bearing (added after mutation testing)
# ---------------------------------------------------------------------------
def test_propose_requires_a_recorded_diagnosis(tmp_path):
    world = World(tmp_path)
    world.base()
    _, cycles = world.ticks(3)
    deficit = next(d for d in DeficitDetector().scan(cycles) if d.kind == "component_failure")
    case_id = world.genesis.observe(deficit)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    with pytest.raises(ContractError, match="diagnose the case"):
        world.genesis.propose(case_id, ladder={"existing_capability": "candidate"}, proposed_by="a",
                              candidates=[{"part_id": fix, "slot": "proposer:strategist",
                                           "rung": "existing_capability", "rationale": "r"}])


def test_attempts_are_not_successes_even_when_no_mechanical_target_exists(tmp_path):
    world = World(tmp_path)
    world.base(rule_proposer("sound plan"), evaluator("guardian", veto=True))
    case_id, _, _ = open_case(world, kind="veto_streak")

    def broken_guardian(candidate, signals, context):
        raise TimeoutError("read timeout")

    broken = world.board.register(spec("evaluator:guardian", "rules/broken"), broken_guardian)
    world.genesis.discover(case_id)
    ladder = searched(world, case_id, "reconfigure_compose") | {"reconfigure_compose": "candidate"}
    world.genesis.propose(case_id, ladder=ladder, proposed_by="alfonso",
                          candidates=[{"part_id": broken, "slot": "evaluator:guardian", "rung": "reconfigure_compose",
                                       "rationale": "r"}])
    agg = world.shadow_and_trial(case_id, broken)
    assert agg["attempts"] == 3 and agg["successes"] == 0
    assert world.genesis.case(case_id)["state"] == CaseState.TRIALING.value
    with pytest.raises(ContractError, match="successful evaluations"):
        world.ratify(case_id, broken)


def test_three_successes_on_one_cycle_are_one_evaluation(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _, _ = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    propose_fix(world, case_id, fix)
    world.genesis.shadow(case_id, fix, actor=world.actor, gate=world.gate,
                         grant=world.grant_for("proposer:strategist", fix, "shadow"))
    _, [cycle] = world.ticks(1, prefix="same")
    hashes = []
    for _ in range(3):
        hashes += world.board.shadow_run(cycle, [signal("same-0")],
                                         resources=ResourceGovernor(max_model_calls=5, max_estimated_cost_usd=1.0))
    agg = world.genesis.record_trials(case_id, fix, hashes)
    assert agg["successes"] == 3 and agg["success_cycles"] == [cycle.cycle_id]
    assert world.genesis.case(case_id)["state"] == CaseState.TRIALING.value
    with pytest.raises(ContractError, match="distinct cycles"):
        world.ratify(case_id, fix)


def test_successes_without_restoration_do_not_meet_a_restoration_target(tmp_path):
    world = World(tmp_path)
    ids = world.base()
    case_id, _, _ = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    propose_fix(world, case_id, fix)
    # the slot was meanwhile repaired another way: the active part produces output again
    working = world.board.register(spec("proposer:strategist", "rules/working"), rule_proposer("working"))
    world.change("proposer:strategist", working)
    agg = world.shadow_and_trial(case_id, fix)
    assert agg["successes"] == 3 and agg["restorations"] == 0
    assert agg["target_evidence"]["met"] is False
    assert world.genesis.case(case_id)["state"] == CaseState.TRIALING.value
    with pytest.raises(ContractError, match="target evidence"):
        world.ratify(case_id, fix)
