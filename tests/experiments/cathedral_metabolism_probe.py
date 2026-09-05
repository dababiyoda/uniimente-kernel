"""CMC-002 SIMULATION ONLY. No actual runtime or founder-command acceptance.

The source audit invokes real Linker code; the mission, logical identities,
lease and continuation are synthetic fixtures. No InstitutionalRuntime, Gate,
passport, grant, model, daemon or organization is instantiated. The only store
is the existing EventSpine's EvidenceLedger. Do not import this into production.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from uuid import NAMESPACE_URL, uuid5

from egregore.contracts import Assessment, CandidateProposal, SignalEnvelope
from egregore.resources import ResourceGovernor
from egregore.runtime import StandingCognitionRuntime
from events.spine import DurableWorkflow, Event, EventSpine, WorkflowStep
from events.task_fabric import TaskFabric
from linker.linker import InstitutionalLinker
from linker.manifest import load_manifest
from omnimorph.organization_compiler import content_digest
from provenance.ledger import EvidenceLedger
from routing.mission_resolution import MissionResolutionRouter, ResolutionFacts
from verifier.mission_audit import appraise, LIMITATION, PIN_DISSENT

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "docs/organizational-morphogenesis/phase4"
PREFIX = "spiffe://uniimente.internal/test/cmc/"
COORDINATOR, WORKER, EVALUATOR = (PREFIX + n for n in ("coordinator", "worker", "verifier"))
TASK_ID = "3d96d99e-fb77-49a5-a213-d5505e404444"
LEASE_ID = "65c1ea2e-9a66-498e-bf03-2180ab859444"
TRIGGER = "CMC-SYNTHETIC-TRIGGER-001"
AT = "2026-09-04T18:00:00Z"
PHASE_FIELDS = {
    "ADMITTED": {"mission", "snapshot", "code_digest", "scenario", "trigger"},
    "COGNIZED": {"cycle"}, "ROUTED": {"decision"},
    "EXECUTED": {"result", "result_event_id"}, "EVALUATED": {"assessment"},
    "AWAITING_DIRECTION": {"question", "exception_digest"},
    "DIRECTED": {"command"}, "CLOSED": {"learning", "closure_receipt"},
}
PHASES = tuple(PHASE_FIELDS)


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def snapshot_sources():
    corpus = load_fixture("input.json")
    texts = {path: (ROOT / path).read_text(encoding="utf-8")
             for path in corpus["source_hashes"]}
    if {p: "sha256:" + sha256(t.encode()).hexdigest() for p, t in texts.items()} != corpus["source_hashes"]:
        raise ValueError("frozen input drift: refuse, do not refresh")
    return {"corpus": corpus, "source_texts": texts}


def code_digest():
    paths = ["tests/experiments/cathedral_metabolism_probe.py", "routing/mission_resolution.py",
             "verifier/mission_audit.py", "events/spine.py", "events/task_fabric.py",
             "egregore/runtime.py", "linker/linker.py", "linker/manifest.py",
             "contracts/organ-manifest.schema.json", "omnimorph/organization_compiler.py"]
    return content_digest({p: sha256((ROOT / p).read_bytes()).hexdigest() for p in paths})


def hypotheses(signals, context):
    common = dict(proposed_by="audit_reasoner", action_class="read_only_audit",
                  requested_capability="linker.typed_route_audit", target="frozen-route",
                  consequence_class="internal_read", evidence_refs=(content_digest(context),),
                  confidence=0.5, estimated_cost_usd=0,
                  source_signal_ids=tuple(s.signal_id for s in signals))
    return [
        CandidateProposal.build(**common, objective="Inspect the declared typed route",
            payload={"hypothesis": "declaration_can_support_a_bounded_audit"},
            expected_outcome="A typed declaration can be reported without executing organs."),
        CandidateProposal.build(**common, objective="Preserve current-main uncertainty",
            payload={"hypothesis": "declaration_does_not_prove_current_main_compatibility"},
            expected_outcome="An old source pin may be intentional; do not silently upgrade."),
    ]


def assess_hypothesis(candidate, signals, context):
    return Assessment.build(role="independent_audit", candidate_id=candidate.candidate_id,
                            score=0.5, confidence=0.5, objections=(LIMITATION, PIN_DISSENT),
                            evidence_refs=tuple(s.signal_id for s in signals))


class Simulation:
    """Test composition only, consuming the canonical event protocol."""
    def __init__(self, spine: EventSpine):
        if not spine.ledger.verify_chain()[0]:
            raise ValueError("corrupt evidence")
        self.spine = spine
        self.fabric = TaskFabric(spine, source_identity=COORDINATOR)
        self.mission = load_fixture("mission.json")

    def events(self):
        events = list(self.spine.replay("test.cmc.transition"))
        previous = None
        for index, event in enumerate(events):
            if index >= len(PHASES):
                raise ValueError("too many mission transitions")
            p = event.payload
            if set(p) != {"phase", "data", "mission_id", "evidence_mode", "digest"}:
                raise ValueError("unknown mission transition fields")
            if (p["phase"] != PHASES[index] or p["mission_id"] != self.mission["mission_id"]
                    or p["evidence_mode"] != "SIMULATION" or event.causal_parent != previous):
                raise ValueError("mission phase/lineage/evidence-mode mismatch")
            if set(p["data"]) != PHASE_FIELDS[p["phase"]]:
                raise ValueError("unknown phase fields")
            if p["digest"] != content_digest(p, excluding=("digest",)):
                raise ValueError("corrupt mission transition")
            previous = event.event_id
        if events:
            admitted = events[0].payload["data"]
            if (admitted["mission"] != self.mission or admitted["code_digest"] != code_digest()
                    or admitted["snapshot"] != snapshot_sources()):
                raise ValueError("mission/input/code changed: migration not authorized")
        return events

    def data(self, phase):
        return next(e.payload["data"] for e in self.events() if e.payload["phase"] == phase)

    @property
    def phase(self):
        events = self.events()
        return events[-1].payload["phase"] if events else "NEW"

    def emit(self, phase, data):
        events = self.events()
        if len(events) >= len(PHASES) or phase != PHASES[len(events)] or set(data) != PHASE_FIELDS[phase]:
            raise ValueError("invalid mission transition")
        if len(self.spine.ledger.records) >= 100:
            raise ValueError("CMC record ceiling exhausted")
        payload = {"phase": phase, "data": data, "mission_id": self.mission["mission_id"],
                   "evidence_mode": "SIMULATION"}
        payload["digest"] = content_digest(payload)
        self.spine.emit(Event(type="test.cmc.transition", source=COORDINATOR,
            actor=EVALUATOR if phase == "EVALUATED" else COORDINATOR,
            legal_principal=self.mission["legal_principal"], payload=payload,
            event_id=str(uuid5(NAMESPACE_URL, self.mission["mission_id"] + phase)),
            causal_parent=events[-1].event_id if events else None))

    def admit(self, scenario="direct", trigger=TRIGGER):
        if scenario not in {"direct", "static"} or trigger != TRIGGER:
            raise ValueError("unregistered synthetic scenario or trigger")
        if self.phase != "NEW":
            if self.data("ADMITTED")["scenario"] != scenario:
                raise ValueError("conflicting trigger replay")
            return
        MissionResolutionRouter().route(self.mission, ResolutionFacts())
        self.emit("ADMITTED", {"mission": self.mission, "snapshot": snapshot_sources(),
            "code_digest": code_digest(), "scenario": scenario, "trigger": trigger})

    def cognize(self):
        runtime = StandingCognitionRuntime(ledger=self.spine.ledger,
            proposers={"audit_reasoner": hypotheses}, evaluators={"independent_audit": assess_hypothesis},
            required_evaluators=("independent_audit",))
        signal = SignalEnvelope.build(source="frozen_repository_audit", source_event_id=TRIGGER,
            observed_at=AT, payload={"snapshot_digest": content_digest(self.data("ADMITTED")["snapshot"])},
            evidence_refs=(self.events()[0].event_id,), trust_level="untrusted")
        signal_id = runtime.ingest(signal)
        cycle = runtime.tick(trigger_id=TRIGGER, signal_ids=[signal_id],
            resources=ResourceGovernor(max_model_calls=5, max_estimated_cost_usd=1),
            context={"mission_digest": content_digest(self.mission)})
        if len(cycle.candidates) != 2 or len(cycle.assessments) != 2:
            raise ValueError("required cognition/evaluation missing")
        self.emit("COGNIZED", {"cycle": cycle.to_dict()})

    def route(self):
        decision = MissionResolutionRouter().route(self.mission, ResolutionFacts())
        self.emit("ROUTED", {"decision": decision})

    def audit(self):
        manifests = [load_manifest(str(ROOT / p)) for p in (
            "organs/daleobanks.manifest.yaml", "organs/wealthmachine.manifest.yaml")]
        corpus = self.data("ADMITTED")["snapshot"]["corpus"]
        route = corpus["expected_route"]
        report = InstitutionalLinker(manifests, str(ROOT / "contracts")).link()
        return {"route": route, "declared_route_present": any(
                    e.producer == route["producer"] and e.consumer == route["consumer"]
                    and e.contract == route["contract"] for e in report.edges),
            "revisions": [{"repository": m.repository, "manifest_pin": m.raw["source"]["commit"],
                "observed_main": corpus["observed_main_revisions"][m.repository],
                "matches": m.raw["source"]["commit"] == corpus["observed_main_revisions"][m.repository]}
                for m in manifests],
            "source_digests": corpus["source_hashes"], "actual_organ_execution": False}

    def _execute(self, interrupt=False):
        task_state = self.fabric.tasks().get(TASK_ID)
        results = list(self.spine.replay("test.cmc.audit_result"))
        if task_state is None:
            envelope = task_envelope(self.mission)
            self.fabric.create_task(envelope, transition_key="create")
            for state in ("ADMITTED", "QUEUED"):
                self.fabric.transition(TASK_ID, state, actor=COORDINATOR, transition_key=state)
            self.fabric.issue_lease(worker_lease(self.mission), transition_key="lease")
            self.fabric.transition(TASK_ID, "RUNNING", actor=WORKER, worker_identity=WORKER,
                lease_id=LEASE_ID, observed_at=AT, transition_key="run")
            result = self.audit()
            event = Event(type="test.cmc.audit_result", source=WORKER, actor=WORKER,
                legal_principal=self.mission["legal_principal"],
                payload={"result": result, "task_id": TASK_ID, "evidence_mode": "SIMULATION"},
                causal_parent=self.events()[-1].event_id)
            self.spine.emit(event)
            self.fabric.transition(TASK_ID, "SUBMITTED", actor=WORKER, worker_identity=WORKER,
                lease_id=LEASE_ID, result_digest=content_digest(result), evidence_refs=(event.event_id,),
                tool_refs=("linker.InstitutionalLinker.link",), transition_key="submit",
                resource_usage={"cost_usd": 0, "compute_used": 1, "model_calls": 0},
                consequence_status="not_attempted")
            if interrupt:
                os._exit(75)  # deliberately bypass finalizers; OS releases CLI lock
        elif task_state == "SUBMITTED" and len(results) == 1:
            event = results[0]
            result = event.payload["result"]
            if self.fabric.receipts(TASK_ID)[-1].result_digest != content_digest(result):
                raise ValueError("corrupt result receipt; reconciliation refused")
        else:
            raise ValueError("unexpected worker loss/state: explicit reconciliation required")
        self.emit("EXECUTED", {"result": result, "result_event_id": event.event_id})
        return {"result_digest": content_digest(result)}

    def execute(self, interrupt=False):
        if self.data("ADMITTED")["scenario"] == "direct":
            return self._execute(interrupt)
        steps = [WorkflowStep("audit", lambda state: self._execute(interrupt), max_retries=0)]
        existing = [r for r in self.spine.ledger.records
                    if r.record_type == "workflow" and r.payload.get("workflow_id") == "cmc-static"]
        workflow = (DurableWorkflow.resume(self.spine, "cmc-static", steps) if existing else
                    DurableWorkflow(self.spine, "cmc-static", steps, actor=COORDINATOR,
                                    legal_principal=self.mission["legal_principal"]))
        workflow.execute()

    def evaluate(self):
        assessment = appraise(self.data("ADMITTED")["snapshot"], self.data("EXECUTED")["result"])
        if not assessment["accepted"]:
            self.fabric.transition(TASK_ID, "QUARANTINED", actor=EVALUATOR,
                transition_key="poison", evidence_refs=(assessment["digest"],))
            raise ValueError("independent evaluation failed; output quarantined")
        self.fabric.transition(TASK_ID, "VERIFIED", actor=EVALUATOR, transition_key="verify",
            assessment_refs=(assessment["digest"],), dissent_refs=tuple(assessment["dissent"]),
            dissent_preserved=True)
        self.fabric.transition(TASK_ID, "CLOSED", actor=COORDINATOR, transition_key="close-task")
        self.emit("EVALUATED", {"assessment": assessment})

    def pause(self):
        question = ("SIMULATION: declared route exists; both manifest pins differ from observed main. "
                    "Keep the pins and record current-main compatibility as unverified?")
        self.emit("AWAITING_DIRECTION", {"question": question,
            "exception_digest": content_digest({"assessment": self.data("EVALUATED"), "question": question})})

    def synthetic_continue(self, command):
        """Only a synthetic fixture; never accepts manual direction records."""
        expected = {"evidence_mode": "SYNTHETIC_TEST_FIXTURE", "decision": "retain_pins_close_audit",
            "mission_digest": content_digest(self.mission),
            "exception_digest": self.data("AWAITING_DIRECTION")["exception_digest"],
            "source_text": "SYNTHETIC FIXTURE ONLY; not a founder message or authorization."}
        if command != expected:
            raise ValueError("only the exact synthetic fixture is accepted; real commands refused")
        if self.phase == "CLOSED":
            if self.data("DIRECTED")["command"] != command:
                raise ValueError("conflicting synthetic replay")
            return
        if self.phase != "AWAITING_DIRECTION":
            raise ValueError("simulation is not awaiting direction")
        self.emit("DIRECTED", {"command": command})
        self.close()

    def close(self):
        report = appraise(self.data("ADMITTED")["snapshot"], self.data("EXECUTED")["result"])
        if (not report["accepted"] or report != self.data("EVALUATED")["assessment"]
                or self.fabric.tasks().get(TASK_ID) != "CLOSED"):
            raise ValueError("protected evaluator or closed task missing")
        ready, reasons = self.fabric.dissolution_readiness(self.mission["mission_id"])
        if not ready:
            raise ValueError(str(reasons))
        self.fabric.dissolve_mission(self.mission["mission_id"], actor=COORDINATOR,
            transition_key="dissolve", evidence_refs=(report["digest"],))
        self.emit("CLOSED", {"learning": {"observation": LIMITATION, "dissent": report["dissent"],
            "weight_updates": 0, "authority_created": 0},
            "closure_receipt": {"evidence_mode": "SIMULATION", "actual_mission_closure": False,
                "mission_digest": content_digest(self.mission), "task_id": TASK_ID,
                "assessment_digest": report["digest"], "founder_accepted": False}})

    def advance(self, *, interrupt=False, one_step=False):
        operations = {"ADMITTED": self.cognize, "COGNIZED": self.route,
            "ROUTED": lambda: self.execute(interrupt), "EXECUTED": self.evaluate,
            "EVALUATED": self.pause, "DIRECTED": self.close}
        started = time.monotonic()
        while self.phase in operations:
            if time.monotonic() - started > 120:
                raise ValueError("active process time ceiling exceeded")
            operations[self.phase]()
            if one_step:
                break

    def summary(self):
        events = self.events()
        return {"evidence_mode": "SIMULATION", "phase": self.phase,
            "actual_mission_closures": 0, "authenticated_founder_commands": 0,
            "ledger_records": len(self.spine.ledger.records), "mission_events": len(events),
            "audit_invocations": len(list(self.spine.replay("test.cmc.audit_result"))),
            "task_states": self.fabric.tasks(), "model_calls": 0,
            "required_runtime_authentication": "NOT_IMPLEMENTED_COMMANDS_REFUSED",
            "exception": self.data("AWAITING_DIRECTION")["question"] if len(events) >= 6 else None}


def task_envelope(mission):
    return {"schema_version": "1.0", "task_id": TASK_ID, "mission_id": mission["mission_id"],
        "founder_intent_ref": mission["founder_intent_ref"], "subgoal_ref": "synthetic:route-audit",
        "parent_task_id": None, "idempotency_key": "cmc-audit-task", "objective": mission["objective"],
        "required_capability": "linker.typed_route_audit", "created_by": COORDINATOR,
        "legal_principal": mission["legal_principal"], "authority_refs": ["synthetic:test-only-no-grant"],
        "consequence_class": "internal_read", "external_effect_policy": "none",
        "resource_budget": {"budget_ceiling_usd": 1, "compute_ceiling": 10, "model_call_ceiling": 5},
        "context_policy": {"permitted_data_classes": ["public"],
            "context_refs": ["CMC-EXP-001"], "prohibited_context": ["credentials"]},
        "tool_policy": {"permitted_tools": ["linker.InstitutionalLinker.link"], "prohibited_tools": ["network"]},
        "evidence_requirements": ["frozen source", "independent appraisal"],
        "prohibited_actions": mission["prohibited_actions"], "sensitivity": "internal", "created_at": AT,
        "acceptance_authority_ref": "synthetic:test-fixture", "independent_evaluation_required": True,
        "authority_invariants": {"organization_may_create_authority": False,
            "worker_may_inherit_authority": False, "consequence_gate_bypass_permitted": False}}


def worker_lease(mission):
    envelope = task_envelope(mission)
    return {"schema_version": "1.0", "lease_id": LEASE_ID, "task_id": TASK_ID,
        "mission_id": mission["mission_id"], "worker_identity": WORKER, "issued_by": COORDINATOR,
        "capability": "linker.typed_route_audit", "capability_grant_ref": "synthetic:no-real-grant",
        "authority_refs": envelope["authority_refs"], "permitted_tools": envelope["tool_policy"]["permitted_tools"],
        "permitted_data_classes": ["public"], "context_refs": ["CMC-EXP-001"],
        "resource_budget": envelope["resource_budget"], "issued_at": AT,
        "expires_at": "2026-09-04T18:05:00Z", "consequence_ceiling": "internal_read",
        "output_contract_ref": "CMC-EXP-001:route-audit", "heartbeat_interval_seconds": 30,
        "termination_condition": "test task terminal or lease expired", "replaces_lease_id": None,
        "one_task_only": True, "authority_inheritance": False}


@contextmanager
def open_simulation(directory):
    """Single-writer test adapter, not a production boot/runtime implementation."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "cmc-test.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            ledger = EvidenceLedger(content_digest({"test_contract": "CMC-002", "mode": "SIMULATION"}),
                                    path=str(directory / "ledger.jsonl"))
            yield Simulation(EventSpine(ledger))
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulation-only", action="store_true", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--scenario", choices=("direct", "static"), default="direct")
    parser.add_argument("--interrupt-after-submit", action="store_true")
    parser.add_argument("--synthetic-continue", action="store_true")
    args = parser.parse_args()
    with open_simulation(args.state_dir) as simulation:
        simulation.admit(args.scenario)
        simulation.advance(interrupt=args.interrupt_after_submit)
        if args.synthetic_continue:
            simulation.synthetic_continue({"evidence_mode": "SYNTHETIC_TEST_FIXTURE",
                "decision": "retain_pins_close_audit", "mission_digest": content_digest(simulation.mission),
                "exception_digest": simulation.data("AWAITING_DIRECTION")["exception_digest"],
                "source_text": "SYNTHETIC FIXTURE ONLY; not a founder message or authorization."})
        print(json.dumps(simulation.summary(), sort_keys=True))


if __name__ == "__main__":
    main()
