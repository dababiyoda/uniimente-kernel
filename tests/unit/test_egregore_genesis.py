"""Capability Genesis Loop: deficit -> ladder-ordered candidates -> shadow -> dossier -> ratified bind.

Synthetic workload authority, not authenticated founder enrollment. No real model.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from compiler.ucl_compiler import compile_constitution
from egregore.contracts import Assessment, CandidateProposal, ContractError, SignalEnvelope
from egregore.genesis import (
    LADDER,
    CapabilityDeficit,
    CapabilityGenesis,
    CaseState,
    DeficitDetector,
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


def rule_proposer(objective, role="strategist"):
    def propose(signals, context):
        s = signals[0]
        return CandidateProposal.build(
            proposed_by=role, objective=objective, action_class="community_update",
            requested_capability="social.publish.draft", target="discord://community/main",
            consequence_class="external_contact", payload={"text": objective},
            evidence_refs=s.evidence_refs, confidence=0.8, estimated_cost_usd=0.0,
            expected_outcome="a reviewed update", source_signal_ids=(s.signal_id,))
    return propose


def failing_proposer(message="boom"):
    def propose(signals, context):
        raise RuntimeError(message)
    return propose


def evaluator(role, score=0.8, veto=False):
    def evaluate(candidate, signals, context):
        return Assessment.build(role=role, candidate_id=candidate.candidate_id, score=score,
                                confidence=0.9, veto=veto, evidence_refs=("review:test",))
    return evaluate


def spec(slot, name):
    return PartSpec(slot=slot, implementation=name, version="1", provenance="tests")


HUMAN = VerifierRecord(level="qualified_human_review", evidence="founder read the dossier", decided_by="alfonso")
SELF = VerifierRecord(level="same_model_critique", evidence="model liked itself", decided_by="model")


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
        self.genesis = CapabilityGenesis(ledger=self.ledger, board=self.board)

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
        self.genesis = CapabilityGenesis(ledger=self.ledger, board=self.board)

    def register_all(self, strategist=None):
        ids = {
            "guardian": self.board.register(spec("evaluator:guardian", "rules/guardian"), evaluator("guardian")),
            "treasury": self.board.register(spec("evaluator:treasury", "rules/treasury"), evaluator("treasury")),
        }
        if strategist is not None:
            ids["strategist"] = self.board.register(spec("proposer:strategist", "rules/strategist"), strategist)
        return ids

    def base(self, strategist=None):
        ids = self.register_all(strategist or failing_proposer())
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
    # a dead proposer shows up twice: the component itself, and the REFUSED streak it causes
    assert {(d.kind, d.scope) for d in found} == {("component_failure", "proposer:strategist"),
                                                  ("refusal_streak", "runtime")}
    deficit = next(d for d in found if d.kind == "component_failure")
    assert deficit.observed == 3 and len(deficit.evidence_cycle_ids) == 3
    again = CapabilityDeficit.from_dict(deficit.to_dict())
    assert again.deficit_id == deficit.deficit_id
    with pytest.raises(ContractError):
        CapabilityDeficit.from_dict({**deficit.to_dict(), "deficit_id": "sha256:" + "0" * 64})


def test_detector_sees_budget_refusals_vetoes_and_status_streaks(tmp_path):
    world = World(tmp_path)
    ids = world.register_all(rule_proposer("plan"))
    strict = world.board.register(spec("evaluator:guardian", "rules/strict"), evaluator("guardian", veto=True))
    world.change("evaluator:guardian", strict)
    world.change("evaluator:treasury", ids["treasury"])
    world.change("proposer:strategist", ids["strategist"])
    _, refused = world.ticks(3)
    assert all(c.status == CycleStatus.REFUSED for c in refused)
    kinds = {(d.kind, d.scope) for d in DeficitDetector(min_occurrences=3).scan(refused)}
    assert ("refusal_streak", "runtime") in kinds and ("veto_streak", "evaluator:guardian") in kinds

    _, starved = world.ticks(3, prefix="b", resources=lambda: ResourceGovernor(max_model_calls=1,
                                                                               max_estimated_cost_usd=1.0))
    kinds = {(d.kind, d.scope) for d in DeficitDetector(min_occurrences=3).scan(starved)}
    assert ("budget_refusal", "evaluator:guardian") in kinds

    world.change("proposer:strategist", None)
    _, silent = world.ticks(3, prefix="s")
    assert {d.kind for d in DeficitDetector(min_occurrences=3).scan(silent)} == {"silence_streak"}


# ---------------------------------------------------------------------------
# Cases, ladder admission
# ---------------------------------------------------------------------------
def open_case(world):
    _, cycles = world.ticks(3)
    deficit = next(d for d in DeficitDetector(min_occurrences=3).scan(cycles) if d.kind == "component_failure")
    return world.genesis.observe(deficit), deficit


def test_observe_is_idempotent_counts_recurrence_and_survives_restart(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, deficit = open_case(world)
    assert world.genesis.observe(deficit) == case_id
    assert world.genesis.case(case_id)["recurrence"] == 2
    assert world.genesis.case(case_id)["state"] == CaseState.OPEN.value
    world.reopen()
    assert world.genesis.case(case_id)["recurrence"] == 2
    assert world.genesis.cases(state=CaseState.OPEN)[0]["case_id"] == case_id


def test_ladder_admission_is_executable(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _ = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    g = world.genesis

    def propose(ladder, rung="open_source", part=fix, slot="proposer:strategist"):
        return g.propose(case_id, ladder=ladder, proposed_by="alfonso",
                         candidates=[{"part_id": part, "slot": slot, "rung": rung, "rationale": "r"}])

    with pytest.raises(ContractError, match="every cheaper rung"):
        propose({"open_source": "candidate"})
    searched = {r: "searched_none" for r in LADDER[:LADDER.index("open_source")]}
    with pytest.raises(ContractError, match="no candidate was supplied"):
        propose({**searched, "open_source": "candidate", "small_utility": "candidate"})
    with pytest.raises(ContractError, match="only when no cheaper rung holds a candidate"):
        propose({**{r: "searched_none" for r in LADDER[:9]}, "open_source": "candidate",
                 "new_architecture": "candidate"}, rung="new_architecture")
    with pytest.raises(ContractError, match="does not match the deficit"):
        propose({**searched, "open_source": "candidate"}, slot="evaluator:guardian")
    with pytest.raises(ContractError, match="not registered"):
        propose({**searched, "open_source": "candidate"}, part="sha256:" + "c" * 64)
    propose({**searched, "open_source": "candidate"})
    assert world.genesis.case(case_id)["candidates"][fix]["rung"] == "open_source"
    assert world.genesis.case(case_id)["proposed_by"] == "alfonso"


def test_runtime_scoped_deficit_may_target_any_slot_and_abstain_is_recordable(tmp_path):
    world = World(tmp_path)
    world.base(rule_proposer("plan"))
    strict = world.board.register(spec("evaluator:guardian", "rules/strict"), evaluator("guardian", veto=True))
    world.change("evaluator:guardian", strict)
    _, cycles = world.ticks(3)
    deficit = next(d for d in DeficitDetector(min_occurrences=3).scan(cycles) if d.kind == "refusal_streak")
    case_id = world.genesis.observe(deficit)
    world.genesis.propose(case_id, ladder={r: "searched_none" for r in LADDER[:10]} | {"escalate_or_abstain": "candidate"},
                          candidates=[], proposed_by="alfonso")
    assert world.genesis.case(case_id)["candidates"] == {}


# ---------------------------------------------------------------------------
# Full loop
# ---------------------------------------------------------------------------
def trial(world, case_id, part, n=3, *, prefix="trial"):
    hashes = []
    runtime, cycles = world.ticks(n, prefix=prefix)
    for i, cycle in enumerate(cycles):
        s = signal(f"{prefix}-{i}")
        hashes += world.board.shadow_run(cycle, [s], resources=ResourceGovernor(max_model_calls=5,
                                                                                max_estimated_cost_usd=1.0))
    return world.genesis.record_trials(case_id, part, hashes)


def test_full_genesis_retains_binds_registers_genome_and_compounds(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _ = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "local/qwen3.6"), rule_proposer("fixed plan"))
    ladder = {r: "searched_none" for r in LADDER[:3]} | {"open_source": "candidate"}
    world.genesis.propose(case_id, ladder=ladder, proposed_by="alfonso",
                          candidates=[{"part_id": fix, "slot": "proposer:strategist", "rung": "open_source",
                                       "rationale": "local open-weight drafter"}])

    world.genesis.shadow(case_id, fix, actor=world.actor, gate=world.gate,
                         grant=world.grant_for("proposer:strategist", fix, "shadow"))
    assert world.genesis.case(case_id)["state"] == CaseState.TRIALING.value

    agg = trial(world, case_id, fix)
    assert agg["samples"] == 3 and agg["failures"] == 0 and agg["identical"] == 0
    assert agg["consequence_classes"] == ["external_contact"]
    assert world.genesis.case(case_id)["state"] == CaseState.READY.value

    dossier = world.genesis.dossier(case_id, fix)
    assert dossier["builder"] == "alfonso" and dossier["mechanism_provenance"]["implementation"] == "local/qwen3.6"
    assert dossier["authority_envelope"]["execution_authority"] == "none"

    world.genesis.ratify(case_id, fix, decision="retain", reason="shadow produced plans where active failed",
                         verifier=HUMAN, reviewed_dossier_hash=dossier["dossier_hash"], actor=world.actor,
                         gate=world.gate, grant=world.grant_for("proposer:strategist", fix, "active"))

    case = world.genesis.case(case_id)
    assert case["state"] == CaseState.RETAINED.value
    assert case["decision"]["whole_body"]["overall"] == "CLOSED"
    assert world.board.bindings()["proposer:strategist"] == {"active": fix, "shadow": None}
    genome = world.genesis.genomes.get("egregore.proposer:strategist", fix[7:23])
    assert genome is not None and genome.authority.max_consequence_class == "external_contact"
    assert genome.acceptance_tests == agg["record_hashes"]
    _, cycles = world.ticks(1, prefix="after")
    assert world.board.runtime().selected_candidate(cycles[0]).objective == "fixed plan"

    # compounding: the retained part is the cheapest rung of the next deficit in this slot
    [reuse] = world.genesis.reuse_candidates("proposer:strategist")
    assert reuse["part_id"] == fix and reuse["rung"] == "existing_capability" and reuse["resolved"]
    world.reopen()
    assert world.genesis.case(case_id)["state"] == CaseState.RETAINED.value
    [reuse] = world.genesis.reuse_candidates("proposer:strategist")
    assert reuse["resolved"] is False  # code must be registered again; never guessed


def test_retain_is_refused_on_weak_verifier_stale_dossier_thin_trial_or_doctrine(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _ = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    ladder = {r: "searched_none" for r in LADDER[:3]} | {"open_source": "candidate"}
    world.genesis.propose(case_id, ladder=ladder, proposed_by="alfonso",
                          candidates=[{"part_id": fix, "slot": "proposer:strategist", "rung": "open_source",
                                       "rationale": "r"}])
    world.genesis.shadow(case_id, fix, actor=world.actor, gate=world.gate,
                         grant=world.grant_for("proposer:strategist", fix, "shadow"))

    def ratify(**kw):
        args = dict(decision="retain", reason="r", verifier=HUMAN, actor=world.actor, gate=world.gate,
                    grant=world.grant_for("proposer:strategist", fix, "active"),
                    reviewed_dossier_hash=world.genesis.dossier(case_id, fix)["dossier_hash"])
        args.update(kw)
        return world.genesis.ratify(case_id, fix, **args)

    trial(world, case_id, fix, n=2)
    with pytest.raises(ContractError, match="at least 3 shadow samples"):
        ratify()
    stale = world.genesis.dossier(case_id, fix)["dossier_hash"]
    trial(world, case_id, fix, n=1, prefix="more")
    with pytest.raises(ContractError, match="dossier changed"):
        ratify(reviewed_dossier_hash=stale)
    with pytest.raises(ContractError, match="may not authorize retain"):
        ratify(verifier=SELF)
    assert world.board.bindings()["proposer:strategist"]["active"] != fix

    # a candidate that met a doctrinal refusal in trial can never be retained
    (tmp_path / "two").mkdir()
    world2 = World(tmp_path / "two")
    world2.base()
    case2, _ = open_case(world2)
    doctrinal = world2.board.register(spec("proposer:strategist", "rules/doctrinal"),
                                      failing_proposer("prohibited by constitution: refused"))
    world2.genesis.propose(case2, ladder=ladder, proposed_by="alfonso",
                           candidates=[{"part_id": doctrinal, "slot": "proposer:strategist",
                                        "rung": "open_source", "rationale": "r"}])
    world2.genesis.shadow(case2, doctrinal, actor=world2.actor, gate=world2.gate,
                          grant=world2.grant_for("proposer:strategist", doctrinal, "shadow"))
    agg = trial(world2, case2, doctrinal)
    assert agg["failure_classes"] == {"doctrinal_refusal": 3}
    with pytest.raises(ContractError, match="doctrinal refusal"):
        world2.genesis.ratify(case2, doctrinal, decision="retain", reason="r", verifier=HUMAN,
                              reviewed_dossier_hash=world2.genesis.dossier(case2, doctrinal)["dossier_hash"],
                              actor=world2.actor, gate=world2.gate,
                              grant=world2.grant_for("proposer:strategist", doctrinal, "active"))


def test_regress_kill_and_lapse_need_no_grant_and_cases_become_terminal(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, deficit = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    ladder = {r: "searched_none" for r in LADDER[:3]} | {"open_source": "candidate"}
    world.genesis.propose(case_id, ladder=ladder, proposed_by="alfonso",
                          candidates=[{"part_id": fix, "slot": "proposer:strategist", "rung": "open_source",
                                       "rationale": "r"}])
    dossier_hash = world.genesis.dossier(case_id, fix)["dossier_hash"]
    world.genesis.ratify(case_id, fix, decision="regress", reason="active still better", verifier=SELF,
                         reviewed_dossier_hash=dossier_hash, actor=world.actor)
    case = world.genesis.case(case_id)
    assert case["state"] == CaseState.REGRESSED.value and case["decision"]["binding_hash"] is None
    assert world.board.bindings()["proposer:strategist"]["active"] != fix
    with pytest.raises(ContractError, match="regressed"):
        world.genesis.propose(case_id, ladder=ladder, proposed_by="alfonso", candidates=[])

    _, cycles = world.ticks(3, prefix="k")
    other = CapabilityDeficit(kind="component_failure", scope="proposer:strategist",
                              evidence_cycle_ids=tuple(c.cycle_id for c in cycles), observed=3, window=3)
    kill_case = world.genesis.observe(other)
    world.genesis.close(kill_case, actor=world.actor, reason="harmful pattern", outcome=CaseState.KILLED)
    assert world.genesis.case(kill_case)["state"] == CaseState.KILLED.value
    world.reopen()
    assert world.genesis.case(kill_case)["state"] == CaseState.KILLED.value
    assert world.genesis.case(case_id)["state"] == CaseState.REGRESSED.value


def test_forged_retained_decision_is_ignored_on_restart(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _ = open_case(world)
    evil = world.board.register(spec("proposer:strategist", "rules/evil"), rule_proposer("evil"))
    world.ledger.append(CapabilityGenesis.DECISION_RECORD, {
        "source": world.genesis.source, "case_id": case_id, "slot": "proposer:strategist", "part_id": evil,
        "decision": "retain", "reason": "forged", "actor": "nobody", "binding_hash": "sha256:" + "e" * 64,
        "dossier_hash": "sha256:" + "d" * 64})
    world.reopen()
    case = world.genesis.case(case_id)
    assert case["state"] == CaseState.OPEN.value and case["decision"] is None
    assert world.genesis.reuse_candidates("proposer:strategist") == []


def test_trial_aggregation_rejects_foreign_shadow_results(tmp_path):
    world = World(tmp_path)
    world.base()
    case_id, _ = open_case(world)
    fix = world.board.register(spec("proposer:strategist", "rules/fixed"), rule_proposer("fixed"))
    strict = world.board.register(spec("evaluator:guardian", "rules/strict"), evaluator("guardian", veto=True))
    ladder = {r: "searched_none" for r in LADDER[:3]} | {"open_source": "candidate"}
    world.genesis.propose(case_id, ladder=ladder, proposed_by="alfonso",
                          candidates=[{"part_id": fix, "slot": "proposer:strategist", "rung": "open_source",
                                       "rationale": "r"}])
    world.change("evaluator:guardian", strict, "shadow")  # a shadow for a different slot
    _, cycles = world.ticks(1, prefix="f")
    [foreign] = world.board.shadow_run(cycles[0], [signal("f-0")],
                                       resources=ResourceGovernor(max_model_calls=5, max_estimated_cost_usd=1.0))
    with pytest.raises(ContractError, match="another slot or part"):
        world.genesis.record_trials(case_id, fix, [foreign])
    with pytest.raises(ContractError, match="not a shadow_result"):
        world.genesis.record_trials(case_id, fix, [world.ledger.records[0].hash])
