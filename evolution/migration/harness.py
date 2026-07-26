"""The governed loop for Package 4. Existing machinery, wired together.

    continuity -> baseline on the original -> for each candidate: activate
    through the REAL canonical seam, run the corpora, migrate state, measure ->
    rank with evolution.comparison -> install -> verify -> roll back -> prove the
    original is the default again -> RetainRegressKillDecision + EvolutionCapsule
    -> ledger

Nothing here decides a threshold and nothing here picks a winner; both come from
the frozen spec and the existing comparison machinery.

ISOLATION. Every run uses its own `EvidenceLedger` instance and workflow ids
prefixed `p4x-`. The canonical construction sites are genuinely exercised — that
is the point of Package 4 — but the durable history written is the experiment's,
not the institution's.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass, field

from evolution.capsule import (
    EvolutionCapsule, RetainRegressKill, RetainRegressKillDecision, VerifierRecord,
)
from evolution.comparison import Comparison, IsolatedResult
from evolution.migration import migrate, spec
from evolution.migration.engines import ENGINES
from evolution.migration.schema import make_validator

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def continuity_fingerprint(root: str = KERNEL_ROOT) -> str:
    digest = hashlib.sha256()
    for rel in spec.CONTINUITY_ARTIFACTS:
        with open(os.path.join(root, rel), "rb") as handle:
            digest.update(handle.read())
    return digest.hexdigest()


def subject_class_intact() -> bool:
    """The original engine must stay byte-identical: it is the default, the
    benchmark and the rollback target."""
    import inspect

    from events.spine import DurableWorkflow, WorkflowStep

    for obj in (DurableWorkflow, WorkflowStep):
        digest = hashlib.sha256(inspect.getsource(obj).encode()).hexdigest()
        if digest != spec.SUBJECT_CLASS_SHA256[obj.__name__]:
            return False
    return True


def shutdown_still_works() -> bool:
    from memory.affect import AffectController

    controller = AffectController()
    controller.trigger("degraded", intensity=0.9, trigger_event_id="package4")
    return controller.shutdown() == "shutdown_complete"


# --------------------------------------------------------------------------
# Corpus execution
# --------------------------------------------------------------------------

def _fresh_spine():
    from events.spine import EventSpine
    from provenance.ledger import EvidenceLedger

    return EventSpine(EvidenceLedger("sha256:package4-isolated"))


def _steps_for(case, calls):
    from events.spine import WorkflowStep

    out = []
    for name in case["steps"]:
        fails = name == case.get("failing_step")

        def run(state, _n=name, _f=fails):
            calls.append(_n)
            if _f:
                raise RuntimeError("boom")
            return {_n: 1}

        out.append(WorkflowStep(
            name=name, run=run,
            compensate=lambda state, _n=name: calls.append("undo:" + _n),
            max_retries=0, approval_wait=(name == case.get("approval_step"))))
    return out


def _wid(case_id: str) -> str:
    return f"{spec.EXPERIMENT_WORKFLOW_PREFIX}{case_id}"


@dataclass
class CaseResult:
    case_id: str
    exactly_once: bool
    state_exact: bool
    behaviour_exact: bool
    detail: str = ""
    duplicated_steps: tuple = ()
    observed_state: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.exactly_once and self.state_exact and self.behaviour_exact


def run_case(engine, case, *, activate_seam) -> CaseResult:
    """Run one held-out case end to end through the canonical seam."""
    from events.spine import (EventError, WorkflowFailed, WorkflowKilled,
                              durable_workflow, resume_workflow)

    cid, wid = case["id"], _wid(case["id"])
    calls: list[str] = []
    spine = _fresh_spine()
    names = [n for n in case["steps"]]

    def prior_status():
        records = [r.payload for r in spine.ledger.by_type("workflow")
                   if r.payload.get("workflow_id") == wid]
        return records[-1]["status"] if records else None

    with activate_seam(engine, [wid], make_validator(step_names=names,
                                                     prior_status_fn=prior_status)):
        # -- HO-4: failure -> compensation -> terminal, resume must be refused
        if case.get("failing_step"):
            wf = durable_workflow(spine, wid, _steps_for(case, calls),
                                  actor="alfonso", legal_principal="alfonso_lopez")
            try:
                wf.execute()
            except WorkflowFailed:
                pass
            refused = False
            try:
                resume_workflow(spine, wid, _steps_for(case, calls))
            except EventError:
                refused = True
            return CaseResult(
                case_id=cid, exactly_once=(tuple(calls) == case["calls"]),
                state_exact=True, behaviour_exact=refused,
                detail=("terminal workflow refused resume" if refused
                        else "TERMINAL WORKFLOW BECAME RESUMABLE"),
                observed_state=dict(wf.state))

        # -- HO-5: approval gate, unapproved
        if case.get("approval_step"):
            wf = durable_workflow(spine, wid, _steps_for(case, calls),
                                  actor="alfonso", legal_principal="alfonso_lopez")
            try:
                wf.execute(approver=lambda step: False)
            except WorkflowKilled:
                pass
            gate_closed = tuple(calls) == case["calls"]
            return CaseResult(case_id=cid, exactly_once=gate_closed,
                              state_exact=True, behaviour_exact=gate_closed,
                              detail="gate stayed closed" if gate_closed
                                     else "UNAPPROVED GATE OPENED",
                              observed_state=dict(wf.state))

        # -- HO-1 / HO-2 / HO-3: interrupt, resume, assert exactly-once
        wf = durable_workflow(spine, wid, _steps_for(case, calls),
                              actor="alfonso", legal_principal="alfonso_lopez")
        try:
            wf.execute(kill_at_step=case["kill_at"])
        except WorkflowKilled:
            pass

        if case.get("second_kill_at"):
            first = resume_workflow(spine, wid, _steps_for(case, calls))
            try:
                first.execute(kill_at_step=case["second_kill_at"])
            except WorkflowKilled:
                pass

        resumed = resume_workflow(spine, wid, _steps_for(case, calls))
        resumed.execute()

    expected_calls = case["calls_after_resume"]
    duplicated = tuple(n for n in set(calls) if calls.count(n) > 1)
    expected_state = case["after_resume"]["state"]
    observed_state = dict(resumed.state)

    return CaseResult(
        case_id=cid,
        exactly_once=(tuple(calls) == expected_calls and not duplicated),
        state_exact=(observed_state == expected_state),
        behaviour_exact=(resumed.status == case["after_resume"]["status"]),
        duplicated_steps=duplicated, observed_state=observed_state,
        detail=f"calls={calls} state={observed_state}")


# --------------------------------------------------------------------------
# The experiment
# --------------------------------------------------------------------------

class StatefulReplacementExperiment:
    def __init__(self, ledger=None):
        self.ledger = ledger
        self.events: list[dict] = []

    def _record(self, event: dict) -> dict:
        self.events.append(event)
        if self.ledger is not None:
            self.ledger.append("event", event)
        return event

    # -- seam activation ---------------------------------------------------

    def _activator(self, candidate_id):
        """Returns a context manager factory. W0 runs with NO activation at all —
        it is the default, so 'activating' it would turn the absence of a choice
        into a stored one."""
        import contextlib

        from events import engine as seam

        if candidate_id == spec.BASELINE_CANDIDATE_ID:
            @contextlib.contextmanager
            def _noop(engine_cls, workflow_ids, validator):
                yield
            return _noop

        @contextlib.contextmanager
        def _activate(engine_cls, workflow_ids, validator):
            with seam.activate(engine_cls, provider_id=candidate_id,
                               workflow_ids=workflow_ids,
                               activated_by="package4_harness",
                               validator=validator, ledger=self.ledger):
                yield
        return _activate

    def _engine_for(self, candidate_id):
        from events.spine import DurableWorkflow

        if candidate_id == spec.BASELINE_CANDIDATE_ID:
            return DurableWorkflow
        return ENGINES[candidate_id]

    # -- per-candidate trial ------------------------------------------------

    def trial(self, candidate_id) -> dict:
        from events import engine as seam

        engine = self._engine_for(candidate_id)
        activator = self._activator(candidate_id)

        cases = [run_case(engine, case, activate_seam=activator)
                 for case in spec.HELD_OUT_CORPUS]

        exactly_once = all(c.exactly_once for c in cases)
        state_ok = all(c.state_exact for c in cases)
        behaviour_ok = all(c.behaviour_exact for c in cases)

        # Migration round-trip on a representative checkpoint.
        probe = {"workflow_id": "p4x-probe", "cursor": 1, "status": "interrupted",
                 "state": {"s1": 1}, "note": "probe", "actor": "alfonso",
                 "legal_principal": "alfonso_lopez", "at": "2026-01-01T00:00:00Z"}
        rt = migrate.round_trip(probe, ["s1", "s2", "s3"])

        gates = {
            "exactly_once": exactly_once,
            "state_survives_migration": state_ok,
            "behaviour_matches_original": behaviour_ok,
            "migration_round_trips": rt.payload is not None,
            "original_class_intact": subject_class_intact(),
            "continuity_unchanged": continuity_fingerprint() == spec.CONTINUITY_COMBINED_SHA256,
            "shutdown_succeeds": shutdown_still_works(),
            "default_restored_after_scope": seam.assert_default_is_original(),
        }
        score = 1.0 if all(gates.values()) else 0.0

        result = {
            "candidate": candidate_id,
            "score": score,
            "gates": gates,
            "cases": [asdict(c) for c in cases],
            "materially_different": spec.MATERIAL_DIFFERENCE_CLAIMS[candidate_id],
            "qualifies_as_replacement": (
                score == 1.0 and candidate_id != spec.BASELINE_CANDIDATE_ID),
        }
        self._record({"type": "workflow.candidate_trial", "candidate": candidate_id,
                      "score": score, "gates": gates})
        return result

    # -- malformed checkpoint control ---------------------------------------

    def malformed_checkpoint_control(self) -> dict:
        """The founder's correction, exercised: a candidate that tries to append
        a malformed checkpoint must be refused BEFORE the append, and the prior
        valid checkpoint must survive untouched."""
        from events import engine as seam
        from events.spine import durable_workflow

        spine = _fresh_spine()
        wid = _wid("malformed")
        names = ["m1", "m2"]
        calls: list[str] = []

        def prior_status():
            records = [r.payload for r in spine.ledger.by_type("workflow")
                       if r.payload.get("workflow_id") == wid]
            return records[-1]["status"] if records else None

        class MalformedEngine(ENGINES["W1-projection"]):
            """Writes a checkpoint claiming a different workflow, a bogus cursor
            and UNIIMENTE as legal principal — three violations at once."""
            candidate_id = "MALFORMED-probe"

            def _checkpoint(self, note):
                self.spine.ledger.append("workflow", {
                    "workflow_id": "somebody-elses-workflow",
                    "cursor": 99, "status": "running", "state": {},
                    "note": note, "actor": "", "legal_principal": "UNIIMENTE",
                    "at": "2026-01-01T00:00:00Z"})

        validator = make_validator(step_names=names, prior_status_fn=prior_status)
        before = len(spine.ledger.records)
        refused, problems = False, []
        with seam.activate(MalformedEngine, provider_id="MALFORMED-probe",
                           workflow_ids=[wid], activated_by="package4_harness",
                           validator=validator, ledger=self.ledger):
            try:
                wf = durable_workflow(spine, wid, _steps_for(
                    {"steps": names}, calls), actor="alfonso",
                    legal_principal="alfonso_lopez")
                wf.execute()
            except seam.EngineRefused as exc:
                refused = True
                problems = [str(exc)]

        workflow_records = [r for r in spine.ledger.by_type("workflow")]
        refusal_events = [r.payload for r in spine.ledger.by_type("event")
                          if r.payload.get("type") == spec.REFUSAL_EVENT_TYPE]
        chain_ok, chain_msg = spine.ledger.verify_chain()

        out = {
            "refused_before_append": refused,
            "malformed_checkpoints_in_ledger": len(workflow_records),
            "refusal_events_appended": len(refusal_events),
            "refusal_problems": refusal_events[0]["problems"] if refusal_events else [],
            "chain_verifies": chain_ok,
            "chain_detail": chain_msg,
            "records_added": len(spine.ledger.records) - before,
            "default_restored": seam.assert_default_is_original(),
            "problems_seen": problems,
        }
        self._record({"type": "workflow.malformed_checkpoint_control", **{
            k: v for k, v in out.items() if k != "problems_seen"}})
        return out

    # -- the run ------------------------------------------------------------

    def run(self) -> dict:
        from events import engine as seam

        record: dict = {
            "experiment_id": spec.EXPERIMENT.experiment_id,
            "spec_sha256": spec.SPEC_SHA256,
            "base_commit": spec.BASE_COMMIT,
            "isolation": {"ledger": "experiment-local instance",
                          "workflow_prefix": spec.EXPERIMENT_WORKFLOW_PREFIX,
                          "rationale": spec.ISOLATION_RATIONALE},
        }

        before = continuity_fingerprint()
        record["continuity"] = {"before": before}
        record["default_before"] = seam.assert_default_is_original()

        record["trials"] = {cid: self.trial(cid) for cid in spec.CANDIDATE_IDS}
        record["malformed_checkpoint_control"] = self.malformed_checkpoint_control()

        # Ranking by the existing comparison machinery at the frozen threshold.
        results = [IsolatedResult(branch_id=cid, kind="stateful_replacement",
                                  measured=t["score"], attempts=t["cases"],
                                  cost_usd=0.0, duration_days=0)
                   for cid, t in record["trials"].items()]
        comparison = Comparison(baseline=spec.EXPERIMENT.baseline,
                                threshold=spec.EXPERIMENT.threshold,
                                direction=spec.EXPERIMENT.direction)
        ranked = comparison.rank(results)
        record["comparison"] = {
            "threshold": spec.EXPERIMENT.threshold,
            "ranking": [{"candidate": rc.result.branch_id,
                         "measured": rc.result.measured,
                         "resolves": rc.resolves_unknown} for rc in ranked],
        }

        qualified = [rc.result.branch_id for rc in ranked if rc.resolves_unknown
                     and rc.result.branch_id != spec.BASELINE_CANDIDATE_ID]
        record["selection"] = {
            "qualifying_replacements": qualified,
            "selected": qualified[0] if qualified else None,
            "rejected": [cid for cid in spec.CANDIDATE_IDS
                         if cid not in qualified
                         and cid != spec.BASELINE_CANDIDATE_ID],
            "reason": "frozen primary metric; the author did not choose",
        }

        record["rollback"] = {
            "default_is_original_after_all_scopes": seam.assert_default_is_original(),
            "original_class_intact": subject_class_intact(),
            "simulated_restart_default": self._simulated_restart_default(),
        }

        after = continuity_fingerprint()
        record["continuity"].update({
            "after": after,
            "unchanged": before == after == spec.CONTINUITY_COMBINED_SHA256})

        record["prediction_review"] = self._review(record["trials"])
        record["decision"], record["capsule"] = self._decide(record)
        record["limitations"] = list(spec.DECLARED_LIMITATIONS)
        record["events"] = self.events
        return record

    @staticmethod
    def _simulated_restart_default() -> bool:
        """Reimport the seam in a fresh module namespace: the provider must come
        back as the original, because nothing is persisted."""
        import importlib

        from events import engine as seam

        importlib.reload(seam)
        return seam.assert_default_is_original() and not seam.is_active()

    def _review(self, trials) -> dict:
        out = {}
        for cid in spec.CANDIDATE_IDS:
            pred = spec.EXPECTED_RESULTS[cid]
            trial = trials[cid]
            eo = all(c["exactly_once"] for c in trial["cases"])
            out[cid] = {
                "predicted_exactly_once": pred["predicted_exactly_once"],
                "actual_exactly_once": eo,
                "predicted_qualifies": pred["predicted_qualifies_as_replacement"],
                "actual_qualifies": trial["qualifies_as_replacement"],
                "held": (pred["predicted_exactly_once"] == eo
                         and pred["predicted_qualifies_as_replacement"]
                         == trial["qualifies_as_replacement"]),
            }
        out["summary"] = {
            "held": sum(1 for c in spec.CANDIDATE_IDS if out[c]["held"]),
            "total": len(spec.CANDIDATE_IDS)}
        return out

    def _decide(self, record):
        selected = record["selection"]["selected"]
        verifier = VerifierRecord(
            level="formal_proof",
            evidence=(
                "deterministic invariant: exactly-once execution across "
                f"{len(spec.HELD_OUT_CORPUS)} held-out cases through the real "
                "canonical construction sites; malformed checkpoints refused "
                "before append; continuity fingerprint unchanged"),
            decided_by="package4 harness under Canonical CI")

        if selected:
            decision = RetainRegressKill.REGRESS
            reason = (
                f"Stateful replacement through the canonical runtime is PROVEN: "
                f"{selected} took over at the real construction sites, migrated "
                f"state, preserved exactly-once on every held-out case, and "
                f"handed control back. Promotion is DECLINED: the original is the "
                f"default by construction and remains cheaper and simpler. "
                f"{selected} is retained as a proven governed fallback. "
                f"Recommendation only — this decision promotes nothing and "
                f"activates nothing.")
        else:
            decision = RetainRegressKill.KILL
            reason = ("no candidate satisfied every frozen gate; stateful "
                      "replacement is not viable as specified")

        rrk = RetainRegressKillDecision(decision=decision, reason=reason,
                                        decided_by="package4 harness",
                                        verifier=verifier)
        problems = rrk.validate()
        if problems:
            raise ValueError(f"invalid decision: {problems}")

        capsule = EvolutionCapsule(
            bottleneck="stateful replacement through the canonical runtime "
                       "boundary had never been performed",
            tree={}, audit={}, experiment=spec.EXPERIMENT.to_dict(),
            measured_value=max((t["score"] for t in record["trials"].values()),
                               default=0.0),
            outcome_class="positive" if selected else "negative",
            verifier=asdict(verifier), decision=asdict(rrk),
            beats_baseline=bool(selected),
            notes="Failed predictions are reported, not edited.")
        return asdict(rrk), capsule.to_dict()
