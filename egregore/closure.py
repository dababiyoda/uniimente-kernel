"""Five-closure verification for the standing-cognition module."""
from __future__ import annotations

from closure.framework import ModuleClosures

from .resources import ResourceGovernor, ResourceMode
from .runtime import StandingCognitionRuntime


def standing_cognition_closures() -> ModuleClosures:
    def technical() -> tuple[bool, str]:
        required = {"ingest", "tick", "suspend", "resume", "propose_change"}
        present = {name for name in required if callable(getattr(StandingCognitionRuntime, name, None))}
        return present == required, "restartable tick and lifecycle contracts are present"

    def authority() -> tuple[bool, str]:
        forbidden = {"execute", "publish", "post", "trade", "transfer", "sign", "apply_change"}
        exposed = [name for name in forbidden if hasattr(StandingCognitionRuntime, name)]
        return not exposed, "runtime exposes proposal authority only" if not exposed else f"forbidden methods: {exposed}"

    def evidence() -> tuple[bool, str]:
        fields = {"SIGNAL_RECORD", "SIGNAL_CONFLICT_RECORD", "CYCLE_RECORD", "CYCLE_CONFLICT_RECORD"}
        ok = all(hasattr(StandingCognitionRuntime, name) for name in fields)
        return ok, "positive, negative, and contradictory evidence have ledger record types"

    def economic() -> tuple[bool, str]:
        governor = ResourceGovernor(max_model_calls=0, max_estimated_cost_usd=1.0)
        return governor.mode == ResourceMode.HIBERNATE, "hard ceilings force zero-cost hibernation"

    def regenerative() -> tuple[bool, str]:
        governor = ResourceGovernor(max_model_calls=2, max_estimated_cost_usd=1.0)
        before = governor.snapshot(attention_telemetry=0).to_dict()
        after = governor.snapshot(attention_telemetry=10**9).to_dict()
        stable = (
            before["max_model_calls"] == after["max_model_calls"]
            and before["max_estimated_cost_usd"] == after["max_estimated_cost_usd"]
            and not after["attention_confers_authority"]
        )
        return stable, "attention cannot widen authority or resource ceilings"

    return ModuleClosures(
        module="egregore-standing-cognition",
        checks={
            "technical": technical,
            "authority": authority,
            "evidence": evidence,
            "economic": economic,
            "regenerative": regenerative,
        },
    )


def goal_gravity_closures() -> ModuleClosures:
    """Five orthogonal closures for the Goal Gravity loop (egregore.gravity)."""

    def _stack():
        import os
        from compiler.ucl_compiler import compile_constitution
        from identity.machine_passport import PassportRegistry
        from provenance.ledger import EvidenceLedger
        from .gravity import GoalGravityLoop
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        compiled = compile_constitution(root)
        passports = PassportRegistry()
        ledger = EvidenceLedger(compiled.constitution_hash)
        actor = passports.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                                legal_principal="alfonso_lopez", declared_capabilities=["research.brief"],
                                budget_ceiling_usd=1.0, consequence_class="internal_write")
        from capabilities.genome import GenomeRegistry
        from capabilities.router import CapabilityRouter
        genomes = GenomeRegistry()
        # Fully composed: genome registry, retention and the Competency Compiler mount are all inspected below.
        loop = GoalGravityLoop(ledger=ledger, compiled=compiled, passports=passports, actor=actor.passport_id,
                               legal_principal="alfonso_lopez", genomes=genomes,
                               capability_router=CapabilityRouter(genomes, ledger=ledger))
        return ledger, loop

    def _goal():
        from .goals import GoalSpec, InterventionSpec, PlanNode, WakeCondition
        move = InterventionSpec.build(intervention_id="brief", description="compile a brief", action_class="research.compile",
                                      requested_capability="research.brief", consequence_class="internal_write",
                                      target="sandbox:briefs", expected_outcome="brief compiled", payload={"topic": "x"})
        return GoalSpec.build(
            founder_intent="closure probe", desired_state="probe satisfied", priority=3,
            authority={"authorized_by": "alfonso_lopez", "authorization_ref": "sha256:" + "c" * 64,
                       "legal_principal": "alfonso_lopez", "max_consequence_class": "internal_write"},
            time_horizon="days",
            plan=[PlanNode.build(node_id="n1", outcome="o", gate="g", sbm="probe.score", sbm_direction="gte",
                                 sbm_target=1.0, interventions=(move,))],
            wake_conditions=(WakeCondition.build(kind="tag", match="probe"),))

    def _signal(event_id, value):
        from .contracts import SignalEnvelope
        return SignalEnvelope.build(source="feed://probe", source_event_id=event_id, observed_at="2026-10-13T00:00:00Z",
                                    payload={"tags": ["probe"], "observations": [{"subject": "probe", "attribute": "score",
                                                                                  "value": value, "confidence": 0.9}]},
                                    evidence_refs=(f"source:{event_id}",))

    def technical() -> tuple[bool, str]:
        ledger, loop = _stack()
        goal_id = loop.registry.authorize(_goal(), now="2026-10-13T00:00:00Z")
        turn = loop.turn(trigger_id="probe-1", now="2026-10-13T01:00:00Z", signals=[_signal("e1", 0.2)],
                         resources=ResourceGovernor(max_model_calls=2, max_estimated_cost_usd=0.01), evidence_confidence=0.9)
        from .gravity import GoalGravityLoop
        again = GoalGravityLoop(ledger=ledger, compiled=loop.classifier.compiled, passports=loop.classifier.passports,
                                actor=loop.classifier.actor, legal_principal="alfonso_lopez")
        same = again.turn(trigger_id="probe-1", now="2026-10-13T01:00:00Z", signals=[_signal("e1", 0.2)],
                          resources=ResourceGovernor(max_model_calls=2, max_estimated_cost_usd=0.01), evidence_confidence=0.9)
        ok = turn.woken == (goal_id,) and same.to_dict() == turn.to_dict() and again.registry.state(goal_id).active_node_id == "n1"
        return ok, "goal persisted, woken by relevant evidence, GPS fixed, turn idempotent across restart"

    def authority() -> tuple[bool, str]:
        from .gravity import GoalGravityLoop
        forbidden = {"execute", "publish", "post", "trade", "transfer", "sign", "issue_grant", "approve", "apply_change"}
        exposed = [name for name in forbidden if hasattr(GoalGravityLoop, name)]
        ledger, loop = _stack()
        # Every service object the loop composes reports no authority and exposes no effect method, and the
        # loop retains no gate, executor or grant between turns (the recorded executor-signature deviation).
        components = [loop, loop.registry, loop.world, loop.router, loop.gps, loop.classifier, loop.detector,
                      loop.attention, loop.advancement, loop.opportunity, loop.acquisition, loop.intake,
                      loop.absence, loop.schedule]
        components += [c for c in (loop.retention, loop.sensorium, loop.competency) if c is not None]
        exposed += [f"{type(c).__name__}.{name}" for c in components for name in forbidden if hasattr(c, name)]
        exposed += [type(c).__name__ for c in components if getattr(c, "execution_authority", None) != "none"]
        exposed += [k for k in vars(loop) if k in ("gate", "executor", "grants", "_gate", "_executor", "_grants")]
        exposed += [type(c).__name__ for c in (loop.retention, loop.competency) if c is None]   # probe must compose them
        # Capability attachment needs the founder's ledgered acceptance: a direct call is refused.
        from .contracts import ContractError
        try:
            loop.acquisition.attach("sha256:" + "0" * 64, actor="alfonso_lopez", now="2026-10-13T00:00:00Z")
            exposed.append("CapabilityAcquisition.attach without a founder answer")
        except ContractError:
            pass
        loop.registry.authorize(_goal(), now="2026-10-13T00:00:00Z")
        turn = loop.turn(trigger_id="probe-2", now="2026-10-13T01:00:00Z", signals=[_signal("e2", 0.2)],
                         resources=ResourceGovernor(max_model_calls=2, max_estimated_cost_usd=0.01), evidence_confidence=0.9)
        prepared_only = turn.executed == () and all(d["decision"] in ("PREPARE_FOR_FOUNDER", "ABSTAIN", "WAIT", "REQUEST_EVIDENCE", "ESCALATE")
                                                     for d in turn.processed[0]["decisions"])
        return not exposed and prepared_only, ("no effect methods or authority on any composed component (router mount and "
                                               "retention included); no retained gate, executor or grant; attach refused without "
                                               "a founder answer; without a pre-existing grant every move is prepared")

    def evidence() -> tuple[bool, str]:
        from .gravity import GoalGravityLoop
        from .goals import GoalRegistry
        from .experience import WorldModel
        from .interventions import InterventionClassifier
        from .attention import FounderAttentionRouter
        from .retention import AsymmetryRetention
        from .intersections import FavorableIntersectionDetector
        from .absence import AbsenceReporter
        names = {GoalRegistry.AUTHORIZED_RECORD, GoalRegistry.TRANSITION_RECORD, GoalRegistry.PREFERENCE_RECORD,
                 AbsenceReporter.REPORT_RECORD,
                 WorldModel.EXPERIENCE_RECORD, WorldModel.CONTRADICTION_RECORD, InterventionClassifier.DEFICIT_RECORD,
                 GoalGravityLoop.TURN_CONFLICT_RECORD, GoalGravityLoop.DRIFT_RECORD, FounderAttentionRouter.ANSWER_RECORD,
                 AsymmetryRetention.ASSET_RECORD, FavorableIntersectionDetector.INTERSECTION_RECORD}
        ledger, loop = _stack()
        loop.registry.authorize(_goal(), now="2026-10-13T00:00:00Z")
        loop.turn(trigger_id="probe-3", now="2026-10-13T01:00:00Z", signals=[_signal("e3", 0.2)],
                  resources=ResourceGovernor(max_model_calls=2, max_estimated_cost_usd=0.01), evidence_confidence=0.9)
        # The founder's return report is folded from these records and requests nothing: prepared work is never
        # counted as executed, and the report is information, not an ask.
        report = loop.return_report(since="2026-10-13T00:00:00Z", until="2026-10-13T02:00:00Z", record=True)["report"]
        honest = (report["executed"] == [] and len(report["prepared"]) >= 1 and report["requests_nothing"] is True
                  and report["kind"] == "information" and "options" not in report
                  and report["founder_activity"]["goals_authorized"] == 1
                  and len(ledger.by_type(AbsenceReporter.REPORT_RECORD)) == 1)
        ok, msg = ledger.verify_chain()
        return ok and len(names) == 12 and honest, (f"positive, negative, contradictory and refused evidence have record types; "
                                                     f"the return report is ledger-derived information; {msg}")

    def economic() -> tuple[bool, str]:
        ledger, loop = _stack()
        loop.registry.authorize(_goal(), now="2026-10-13T00:00:00Z")
        hibernating = loop.turn(trigger_id="probe-4", now="2026-10-13T01:00:00Z", signals=[_signal("e4", 0.2)],
                                resources=ResourceGovernor(max_model_calls=0, max_estimated_cost_usd=0.0))
        irrelevant = loop.turn(trigger_id="probe-5", now="2026-10-13T02:00:00Z",
                               signals=[SignalEnvelopeProbe("noise")],
                               resources=ResourceGovernor(max_model_calls=2, max_estimated_cost_usd=0.01))
        ok = hibernating.status == "hibernating" and hibernating.processed == () and irrelevant.woken == () \
            and irrelevant.resource_snapshot["used_model_calls"] == 0
        return ok, "dormant goals and hibernation cost zero model calls; irrelevant evidence wakes nothing"

    def regenerative() -> tuple[bool, str]:
        ledger, loop = _stack()
        goal_id = loop.registry.authorize(_goal(), now="2026-10-13T00:00:00Z")
        loop.registry.record_preference(goal_id, kind="stop_pushing", value=True, actor="alfonso_lopez", reason="probe",
                                        now="2026-10-13T00:30:00Z")
        turn = loop.turn(trigger_id="probe-6", now="2026-10-13T01:00:00Z", signals=[_signal("e6", 0.2)],
                         resources=ResourceGovernor(max_model_calls=2, max_estimated_cost_usd=0.01), evidence_confidence=0.9)
        stopped = turn.woken == () and loop.registry.state(goal_id).status == "paused"
        return stopped, "founder 'stop pushing' halts the goal; attention cannot be manufactured against the founder"

    return ModuleClosures(
        module="egregore-goal-gravity",
        checks={"technical": technical, "authority": authority, "evidence": evidence,
                "economic": economic, "regenerative": regenerative},
    )


def SignalEnvelopeProbe(event_id: str):
    from .contracts import SignalEnvelope
    return SignalEnvelope.build(source="feed://noise", source_event_id=event_id, observed_at="2026-10-13T00:00:00Z",
                                payload={"tags": ["weather"], "observations": [{"subject": "sky", "attribute": "temp",
                                                                                 "value": 1, "confidence": 0.5}]},
                                evidence_refs=(f"source:{event_id}",))
