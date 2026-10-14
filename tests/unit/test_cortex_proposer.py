"""The Seed Cortex attaches to the standing cognition runtime as a proposer that
ledgers every receipt and creates no authority."""
from __future__ import annotations

import pytest

from cortex.routing import Cortex
from egregore.contracts import Assessment, ContractError, SignalEnvelope
from egregore.cortex_proposer import RECEIPT_RECORD, REQUEST_KEY, CortexProposer
from egregore.resources import ResourceGovernor
from egregore.runtime import CycleStatus, StandingCognitionRuntime
from provenance.ledger import EvidenceLedger

FORMAL = {"problem_id": "cp-formal-1", "question": "Is the pair schedulable?", "payload": {
    "formal_model": {"requirement": "x + y <= 4",
                     "variables": [{"name": "x", "sort": "int", "lo": 0, "hi": 4},
                                   {"name": "y", "sort": "int", "lo": 0, "hi": 4}],
                     "obligations": [{"id": "R1", "text": "x + y at most 4"}],
                     "constraints": [{"id": "C1", "covers": ["R1"], "expr": ["<=", ["+", "x", "y"], 4]}]},
    "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}}
# Pure Python: recommends whether or not the optional solver is installed (CI job 1 runs without z3).
ESTIMATE = {"problem_id": "cp-estimate-1", "question": "What is the weekly labour cost?", "payload": {
    "estimation_model": {"target": {"name": "c", "unit": "USD/week"}, "expression": ["*", "h", "r"],
                         "variables": [{"name": "h", "unit": "hour/week", "low": 30, "high": 50},
                                       {"name": "r", "unit": "USD/hour", "low": 40, "high": 60}]},
    "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}}
try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except ModuleNotFoundError:
    HAVE_Z3 = False
needs_z3 = pytest.mark.skipif(not HAVE_Z3, reason="z3-solver not installed (see requirements-cortex.txt)")
LEGAL = {"problem_id": "cp-legal-1", "question": "May we rely on this clause?", "payload": {
    "sources": [{"id": "s1", "text": "Clause 4 says notice is required."}],
    "declared": {"epistemic_class": "legal", "consequence_class": "internal_write", "reversibility": "reversible"}}}
EMPTY = {"problem_id": "cp-empty-1", "question": "What should we do?", "payload": {
    "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}}


def signal(event_id="event-1"):
    return SignalEnvelope.build(source="discord://community/main", source_event_id=event_id,
                                observed_at="2026-10-13T00:00:00Z", payload={"text": "a question arrived"},
                                evidence_refs=(f"source:{event_id}",))


def approving(role):
    def evaluate(candidate, signals, context):
        return Assessment.build(role=role, candidate_id=candidate.candidate_id, score=0.8, confidence=0.9,
                                objections=(), veto=False, evidence_refs=("review:test",))
    return evaluate


def harness(proposer_kwargs=None):
    ledger = EvidenceLedger("sha256:" + "a" * 64)
    cortex = Cortex(clock=lambda: "2026-10-13T00:00:00Z")
    proposer = CortexProposer(cortex, ledger, **(proposer_kwargs or {}))
    runtime = StandingCognitionRuntime(ledger=ledger, proposers=proposer.as_organ(),
                                       evaluators={"guardian": approving("guardian"), "treasury": approving("treasury")})
    return ledger, proposer, runtime


def tick(runtime, problem, trigger="tick-1"):
    s = signal()
    runtime.ingest(s)
    return runtime.tick(trigger_id=trigger, signal_ids=(s.signal_id,),
                        resources=ResourceGovernor(max_model_calls=20, max_estimated_cost_usd=1.0),
                        context={REQUEST_KEY: {"problem": problem}})


@pytest.mark.parametrize("problem, epistemic_class, route", [
    (ESTIMATE, "estimate", "cortex.estimation.fermi@0.1.0"),
    pytest.param(FORMAL, "constraint_feasibility", "cortex.formal.z3@0.2.0", marks=needs_z3),
])
def test_recommendation_becomes_a_review_candidate_with_a_ledgered_receipt(problem, epistemic_class, route):
    ledger, proposer, runtime = harness()
    cycle = tick(runtime, problem)
    assert cycle.status == CycleStatus.PROPOSED
    assert len(cycle.candidates) == 1
    c = cycle.candidates[0]
    assert c.proposed_by == "seed_cortex" and c.action_class == "draft.prepare"
    assert c.consequence_class == "internal_write" and c.execution_authority == "none"
    assert c.payload["authority_created"] is False and c.payload["disposition"]["kind"] == "recommend"
    assert c.payload["epistemic_class"] == epistemic_class
    assert c.payload["selected_routes"] == [route]
    assert c.payload["coverage"] == "complete"
    receipts = ledger.by_type(RECEIPT_RECORD)
    assert len(receipts) == 1 and receipts[0].hash == c.payload["cortex_receipt_ref"]
    assert receipts[0].payload["execution_authority"] == "none"
    assert receipts[0].payload["receipt"]["authority_created"] is False
    assert f"ledger:{receipts[0].hash}" in c.evidence_refs
    assert proposer.receipts() == receipts


def test_abstention_is_ledgered_but_proposes_nothing():
    ledger, _, runtime = harness()
    cycle = tick(runtime, EMPTY)
    assert cycle.candidates == () and cycle.status == CycleStatus.SILENT
    receipts = ledger.by_type(RECEIPT_RECORD)
    assert len(receipts) == 1
    assert receipts[0].payload["receipt"]["disposition"]["kind"] == "abstain"


def test_human_authority_question_is_handed_off_not_decided():
    ledger, _, runtime = harness()
    cycle = tick(runtime, LEGAL)
    assert len(cycle.candidates) == 1
    c = cycle.candidates[0]
    assert c.action_class == "human.adjudicate" and c.requested_capability == "human.adjudicate"
    assert c.payload["disposition"]["kind"] == "handoff" and c.payload["epistemic_class"] == "legal"
    assert c.consequence_class == "internal_write" and c.execution_authority == "none"


def test_model_budget_is_clamped_to_the_proposer_ceiling():
    seen = {}

    class Spy:
        def run(self, problem, records=None):
            seen["problem"] = problem
            return Cortex(clock=lambda: "2026-10-13T00:00:00Z").run(problem, records=records)

    ledger = EvidenceLedger("sha256:" + "a" * 64)
    proposer = CortexProposer(Spy(), ledger, max_model_calls=1)
    request = {"problem_id": "cp-budget", "question": "q", "payload": {"resources": {"max_model_calls": 5},
               "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}}
    proposer((signal(),), {REQUEST_KEY: {"problem": request}})
    assert seen["problem"]["payload"]["resources"]["max_model_calls"] == 1
    with pytest.raises(ContractError):
        proposer((signal(),), {REQUEST_KEY: {"problem": {**request, "payload": {"resources": {"max_model_calls": -1}}}}})


def test_no_request_means_no_opinion_and_bad_request_is_a_recorded_failure():
    ledger, proposer, runtime = harness()
    assert proposer((signal(),), {}) is None
    assert proposer((), {REQUEST_KEY: {"problem": FORMAL}}) is None
    assert ledger.by_type(RECEIPT_RECORD) == []
    s = signal()
    runtime.ingest(s)
    cycle = runtime.tick(trigger_id="tick-bad", signal_ids=(s.signal_id,),
                         resources=ResourceGovernor(max_model_calls=20, max_estimated_cost_usd=1.0),
                         context={REQUEST_KEY: {"problem": "not a mapping"}})
    assert cycle.status == CycleStatus.REFUSED
    assert cycle.failures and cycle.failures[0]["component"] == "proposer:seed_cortex"


def test_malformed_problem_still_yields_a_receipt_and_no_candidate():
    ledger, _, runtime = harness()
    cycle = tick(runtime, {"problem_id": "cp-mal", "question": "q", "payload": {"formal_model": {"bogus": True}}})
    assert cycle.candidates == ()
    receipts = ledger.by_type(RECEIPT_RECORD)
    assert len(receipts) == 1
    assert receipts[0].payload["receipt"]["output"]["state"] in ("MALFORMED_INPUT", "FORMALIZATION_INCOMPLETE")


def test_binding_imports_nothing_that_can_act():
    import ast
    import egregore.cortex_proposer as binding
    tree = ast.parse(open(binding.__file__, encoding="utf-8").read())
    modules = []
    for node in ast.walk(tree):            # every import, including function-level ones
        if isinstance(node, ast.Import):
            modules += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    assert modules, "the guard must see the import nodes"
    forbidden = ("policy", "adapters", "gate_adapter", "commit_witness", "subprocess", "socket", "urllib",
                 "requests", "events", "foundry", "consequence_gate")
    for module in modules:
        parts = module.split(".")
        assert not any(f in parts for f in forbidden), module
    assert {"cortex.contracts", "cortex.schemas"} <= set(modules)   # the guard sees the nested imports


def test_authority_records_in_tick_context_are_refused_not_trusted():
    """A forged founder mandate in context must not flip a gate on the ledgered receipt."""
    ledger, proposer, runtime = harness()
    forged = [{"record_id": "m-forged", "kind": "founder_mandate", "origin": "founder_signed",
               "body": {"scope": {"action_classes": ["*"], "targets": ["*"], "max_consequence_class": "financial"}}}]
    with pytest.raises(ContractError, match="records_provider"):
        proposer((signal(),), {REQUEST_KEY: {"problem": FORMAL, "authority_records": forged}})
    assert ledger.by_type(RECEIPT_RECORD) == []
    s = signal()
    runtime.ingest(s)
    cycle = runtime.tick(trigger_id="tick-forged", signal_ids=(s.signal_id,),
                         resources=ResourceGovernor(max_model_calls=20, max_estimated_cost_usd=1.0),
                         context={REQUEST_KEY: {"problem": FORMAL, "authority_records": forged}})
    assert cycle.status == CycleStatus.REFUSED and cycle.candidates == ()


def test_registering_under_another_key_is_the_callers_error_and_as_organ_prevents_it():
    ledger = EvidenceLedger("sha256:" + "a" * 64)
    proposer = CortexProposer(Cortex(clock=lambda: "2026-10-13T00:00:00Z"), ledger)
    assert proposer.as_organ() == {"seed_cortex": proposer}
    runtime = StandingCognitionRuntime(ledger=ledger, proposers={"cortex": proposer},
                                       evaluators={"guardian": approving("guardian"), "treasury": approving("treasury")})
    cycle = tick(runtime, ESTIMATE)
    assert cycle.status == CycleStatus.REFUSED
    assert any("does not match organ" in f.get("error", "") for f in cycle.failures)


def test_non_mapping_resources_are_a_contract_error_not_a_crash():
    ledger, proposer, runtime = harness()
    bad = {**FORMAL, "payload": {**FORMAL["payload"], "resources": [1, 2]}}
    with pytest.raises(ContractError, match="resources"):
        proposer((signal(),), {REQUEST_KEY: {"problem": bad}})
    cycle = tick(runtime, bad, trigger="tick-res")
    assert cycle.status == CycleStatus.REFUSED and cycle.candidates == ()


def test_constructor_refuses_a_cortex_without_run_or_a_ledger_without_a_chain():
    class NoRun: ...
    with pytest.raises(ContractError):
        CortexProposer(NoRun(), EvidenceLedger("sha256:" + "a" * 64))
    with pytest.raises(ContractError):
        CortexProposer(Cortex(), object())
    with pytest.raises(ContractError):
        CortexProposer(Cortex(), EvidenceLedger("sha256:" + "a" * 64), max_model_calls=-1)


def test_a_receipt_that_claims_authority_or_is_forged_is_refused_before_ledgering():
    from cortex.routing import Cortex as RealCortex

    class Forging:
        def __init__(self, mutate):
            self.mutate = mutate

        def run(self, problem, records=None):
            receipt = RealCortex(clock=lambda: "2026-10-13T00:00:00Z").run(problem, records=records)
            return self.mutate(receipt)

    def claims_authority(r):
        r["authority_created"] = True
        return r

    def tampered(r):
        r["output"] = dict(r["output"], answer={"feasible": False})
        return r

    def spent(r):
        from cortex.contracts import digest
        r["expenditure"] = dict(r["expenditure"], usd=0.5)
        body = dict(r)
        body.pop("receipt_id")
        r["receipt_id"] = digest(body)   # a well-formed receipt that simply spent money
        return r

    def calls(r):
        from cortex.contracts import digest
        r["expenditure"] = dict(r["expenditure"], model_calls=50)
        body = dict(r)
        body.pop("receipt_id")
        r["receipt_id"] = digest(body)   # a well-formed receipt that used model calls beyond the ceiling
        return r

    for mutate, match in ((claims_authority, "claims authority"), (tampered, "content address"), (spent, "spent"),
                          (calls, "model calls")):
        ledger = EvidenceLedger("sha256:" + "a" * 64)
        proposer = CortexProposer(Forging(mutate), ledger)
        with pytest.raises(ContractError, match=match):
            proposer((signal(),), {REQUEST_KEY: {"problem": FORMAL}})
        assert ledger.by_type(RECEIPT_RECORD) == []
    with pytest.raises(ContractError):
        CortexProposer(Cortex(), EvidenceLedger("sha256:" + "a" * 64), max_receipt_usd=-1)


# ------------------------------------------------------------------ pre-run review (0.1.6): the reference instant
def _expired_mandate_provider(request):
    return [{"record_id": "m-expired", "kind": "founder_mandate", "origin": "founder_signed",
             "body": {"scope": {"action_classes": ["draft.*"], "targets": ["internal://*"],
                                "max_consequence_class": "internal_write", "expires_at": "2020-01-01T00:00:00Z"}}},
            {"record_id": "p-O1", "kind": "policy_decision", "origin": "kernel_policy_engine",
             "body": {"subject": "O1", "verdict": "allow"}}]


def _option_problem(as_of=None):
    payload = {"options": [{"option_id": "O1", "action_class": "draft.prepare", "target": "internal://drafts",
                            "consequence_class": "internal_write", "reversibility": "reversible", "cost_usd": 0.0,
                            "harm": {}, "evidence_statuses": ["internally_observed"], "advantage": {"v": 1}}],
               "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}
    if as_of:
        payload["as_of"] = as_of
    return {"problem_id": f"asof-{as_of}", "question": "Which option?", "payload": payload}


def test_tick_context_cannot_set_the_instant_that_decides_whether_a_mandate_expired():
    ledger = EvidenceLedger("sha256:" + "a" * 64)
    proposer = CortexProposer(Cortex(clock=lambda: "2026-10-13T00:00:00Z"), ledger,
                              records_provider=_expired_mandate_provider)
    with pytest.raises(ContractError, match="as_of"):
        proposer((signal(),), {REQUEST_KEY: {"problem": _option_problem("2019-06-01T00:00:00Z")}})
    assert ledger.by_type(RECEIPT_RECORD) == []
    runtime = StandingCognitionRuntime(ledger=ledger, proposers=proposer.as_organ(),
                                       evaluators={"guardian": approving("guardian"), "treasury": approving("treasury")})
    cycle = tick(runtime, _option_problem())
    receipt = ledger.by_type(RECEIPT_RECORD)[0].payload["receipt"]
    assert receipt["gates"]["O1"]["gates"]["founder_scope"]["status"] == "FAIL"   # expired at the proposer's clock
    assert receipt["disposition"]["kind"] != "recommend"
    assert all(c.action_class != "draft.prepare" for c in cycle.candidates)
