"""EvolutionCycle — the ClosureLoop engine (WP-05, SPEC-WP05 3.2).

One manual, machine-recorded improvement cycle in eight stages:

    propose_tree -> audit (per branch) -> select -> register_experiment ->
    run_experiment (the ONLY gated side effect) -> verify -> decide
    (per branch) -> seal_capsule

Hard Rules enforced here:
1. Experiment execution goes through the gate (``Gate.run``) with a founder
   approval — the manual cycle honors the gate, it does not bypass it
   (ADR-2). The engine never invokes an adapter itself.
4. Every refusal raises ``CycleError`` and appends NOTHING — fail closed;
   a refused step leaves the spine byte-identical.
5. Determinism: no wall-clock values enter any measured fact; selection is a
   pure function of the sealed branches and audits.

ADR-8 seal order (SPEC-WP05 3.1): the ClosureLoop and EvolutionCapsule models
are BOTH pre-constructed in memory — ``ClosureLoop.capsule_id`` carries the
capsule model's id, ``EvolutionCapsule.loop_id`` carries the loop model's id —
then the loop is appended, then the capsule. No placeholder fields, no
mutation. ``EvolutionCapsule.sealed_head_hash`` is the spine head after the
ClosureLoop seal append — i.e. exactly the capsule record's ``prev_hash`` on
the spine, which any observer can verify. (The head AFTER BOTH seal appends
is the capsule record's own hash, which cannot be embedded in its own payload
— a sha256 self-reference — so the honest, verifiable binding is the loop-seal
head. The capsule file documents the head before the seal appends, the loop
record hash, and this note.)
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable

from ..authority.approvals import ApprovalService
from ..contracts.action import ActionIntent
from ..contracts.evolution import (
    AuditFinding,
    ClosureLoop,
    EvolutionCapsule,
    ExperimentSpec,
    RetainRegressKillDecision,
    SpiderWebAudit,
    StrategyBranch,
    StrategyTree,
    VerifierRecord,
)
from ..contracts.execution import DecisionEpisode
from ..contracts.institutional import InstitutionalEvent
from ..crypto.hashing import canonical_json, content_hash, sha256_hex
from ..spine import GENESIS_HASH

EVOLUTION_ACTION_TYPE = "evolution_experiment"
EVOLUTION_CONSEQUENCE_CLASS = "C2"  # REQUIRE_HUMAN per the WP-02 UCL defaults

# Selection-rule thresholds (SPEC-WP05 3.2 step 3), mirrored in prose in
# StrategyTree.selection_rule.
MAX_RISK = 0.3
MIN_REVERSIBILITY = 0.8


class CycleError(Exception):
    """Raised when the evolution cycle refuses a step (fail closed)."""


def _loop_id() -> str:
    return uuid.uuid4().hex


class EvolutionCycle:
    """One evolution cycle over a gate + spine + founder authority."""

    def __init__(
        self,
        gate,
        spine,
        authority: ApprovalService,
        *,
        actor_id: str,
        organ_id: str,
        cycle_index: int = 1,
    ):
        self._gate = gate
        self._spine = spine
        self._authority = authority
        self._actor_id = actor_id
        self._organ_id = organ_id
        self._cycle_index = int(cycle_index)
        # The loop's pre-declared uuid (ADR-8): fixed up front so the capsule
        # contract can reference it before either is sealed.
        self.loop_id = _loop_id()
        self._tree: StrategyTree | None = None
        self._branches: dict[str, StrategyBranch] = {}
        self._audits: dict[str, SpiderWebAudit] = {}
        self._selected: StrategyBranch | None = None
        self._specs: dict[str, int] = {}  # spec.id -> spine seq (sealed)
        self._spec: ExperimentSpec | None = None
        self._experiment: dict[str, Any] | None = None
        self._verifier: VerifierRecord | None = None
        self._decisions: list[RetainRegressKillDecision] = []

    # ------------------------------------------------------------ internals

    def _append(self, model, *, kind: str, refs: dict[str, Any] | None = None):
        return self._spine.append(model, kind=kind, refs=refs)

    def _event(self, event_type: str, model, refs: dict[str, Any]) -> None:
        """Record a status transition as an InstitutionalEvent (ADR-1)."""
        event = InstitutionalEvent(
            event_type=event_type,
            actor_id=self._actor_id,
            organ_id=self._organ_id,
            payload_hash=content_hash(model),
        )
        self._append(event, kind=event_type, refs=refs)

    def _find_record(self, kind: str, payload_id: str) -> dict[str, Any] | None:
        for rec in self._spine.iter():
            if rec["kind"] == kind and rec["payload"].get("id") == payload_id:
                return rec
        return None

    def _head(self) -> tuple[int, str]:
        """(next_seq, head_hash) of the spine; GENESIS when empty."""
        records = list(self._spine.iter())
        if not records:
            return 0, GENESIS_HASH
        return int(records[-1]["seq"]) + 1, str(records[-1]["record_hash"])

    # -------------------------------------------------------- 1. propose

    def propose_tree(
        self,
        root_objective: str,
        horizon: str,
        selection_rule: str,
        branches: list[StrategyBranch],
        *,
        created_by: str | None = None,
    ) -> StrategyTree:
        """Seal the branch drafts (tree_id assigned) then the tree itself."""
        if not branches:
            raise CycleError("a strategy tree needs at least one branch")
        for branch in branches:
            if not isinstance(branch, StrategyBranch):
                raise CycleError("propose_tree accepts StrategyBranch drafts only")
            if branch.tree_id != "":
                raise CycleError(
                    "branch drafts must arrive with tree_id='' (already-sealed "
                    "branches are refused; ambiguity fails closed)"
                )
        tree = StrategyTree(
            root_objective=root_objective,
            horizon=horizon,
            selection_rule=selection_rule,
            branch_ids=[b.id for b in branches],
            created_by=created_by or self._actor_id,
        )
        sealed: list[StrategyBranch] = []
        for branch in branches:
            sealed_branch = branch.model_copy(update={"tree_id": tree.id})
            self._append(sealed_branch, kind="StrategyBranch", refs={"tree_id": tree.id})
            sealed.append(sealed_branch)
        self._append(tree, kind="StrategyTree", refs={"cycle_index": self._cycle_index})
        self._tree = tree
        self._branches = {b.id: b for b in sealed}
        return tree

    # ---------------------------------------------------------- 2. audit

    def audit(
        self,
        branch_id: str,
        auditor_id: str,
        findings: list[AuditFinding],
    ) -> SpiderWebAudit:
        """Seal one adversarial audit; record AUDIT_KILLED/AUDIT_PASSED."""
        if branch_id not in self._branches:
            raise CycleError(f"unknown branch {branch_id!r}; propose the tree first")
        if not findings or not all(isinstance(f, AuditFinding) for f in findings):
            raise CycleError("an audit needs at least one AuditFinding")
        overall = "fail" if any(f.result == "fail" for f in findings) else "pass"
        try:
            audit = SpiderWebAudit(
                branch_id=branch_id,
                auditor_id=auditor_id,
                findings=list(findings),
                overall=overall,
            )
        except ValueError as exc:
            raise CycleError(f"audit refused: {exc}") from exc
        self._append(audit, kind="SpiderWebAudit", refs={"branch_id": branch_id})
        self._event(
            "AUDIT_KILLED" if overall == "fail" else "AUDIT_PASSED",
            audit,
            {"branch_id": branch_id, "audit_id": audit.id},
        )
        self._audits[branch_id] = audit
        return audit

    # --------------------------------------------------------- 3. select

    def select(self, tree: StrategyTree, audits: list[SpiderWebAudit]) -> StrategyBranch:
        """Pick the winning branch per the pre-registered selection rule.

        A branch whose audit overall is "fail" is NEVER eligible (killed
        branches are sealed memory, not candidates); a branch with no audit
        is ambiguity and fails closed. Among audit-passing branches: max
        scores["expected_value"] subject to scores["risk"] <= 0.3 and
        scores["reversibility"] >= 0.8; ties break to lower scores["cost"]
        (then to the lower branch id, for total determinism).
        """
        if self._tree is None or tree.id != self._tree.id:
            raise CycleError("unknown tree; propose it through this cycle first")
        audit_by_branch = {a.branch_id: a for a in audits}
        eligible: list[StrategyBranch] = []
        for branch_id in tree.branch_ids:
            branch = self._branches[branch_id]
            audit = audit_by_branch.get(branch_id)
            if audit is None:
                raise CycleError(f"branch {branch_id!r} has no audit; fail closed")
            if audit.overall == "fail":
                continue  # killed: never eligible, never deletable
            missing = {"expected_value", "risk", "reversibility", "cost"} - set(branch.scores)
            if missing:
                raise CycleError(
                    f"branch {branch_id!r} lacks score keys {sorted(missing)}; fail closed"
                )
            if (
                branch.scores["risk"] <= MAX_RISK
                and branch.scores["reversibility"] >= MIN_REVERSIBILITY
            ):
                eligible.append(branch)
        if not eligible:
            raise CycleError("no selectable branch: every candidate is killed or out of bounds")
        winner = min(
            eligible,
            key=lambda b: (-b.scores["expected_value"], b.scores["cost"], b.id),
        )
        self._event(
            "STRATEGY_SELECTED",
            winner,
            {"tree_id": tree.id, "branch_id": winner.id, "loop_id": self.loop_id},
        )
        self._selected = winner
        return winner

    # --------------------------------------------- 4. register experiment

    def register_experiment(self, spec: ExperimentSpec) -> dict[str, Any]:
        """Seal the pre-registered ExperimentSpec BEFORE any execution."""
        if not isinstance(spec, ExperimentSpec):
            raise CycleError("register_experiment accepts an ExperimentSpec only")
        if spec.branch_id not in self._branches:
            raise CycleError(f"unknown branch {spec.branch_id!r} for experiment spec")
        record = self._append(
            spec, kind="ExperimentSpec", refs={"branch_id": spec.branch_id}
        )
        self._specs[spec.id] = int(record["seq"])
        self._spec = spec
        return record

    # -------------------------------------------------- 5. run experiment

    def run_experiment(
        self,
        intent: ActionIntent,
        adapter,
        approval,
    ) -> DecisionEpisode:
        """The ONLY gated side effect of the cycle (ADR-2).

        The intent must be a C2 ``evolution_experiment`` referencing an
        ExperimentSpec ALREADY sealed on this spine (ordering enforced via
        spine seq numbers: the spec record must precede the intent record).
        REQUIRE_HUMAN approval is enforced by the gate, not by trust.
        """
        if not isinstance(intent, ActionIntent):
            raise CycleError("run_experiment requires an ActionIntent")
        if intent.action_type != EVOLUTION_ACTION_TYPE:
            raise CycleError(
                f"action_type {intent.action_type!r} refused: the cycle runs "
                f"{EVOLUTION_ACTION_TYPE!r} intents only"
            )
        if intent.consequence_class != EVOLUTION_CONSEQUENCE_CLASS:
            raise CycleError(
                f"consequence_class {intent.consequence_class!r} refused: "
                f"evolution experiments are {EVOLUTION_CONSEQUENCE_CLASS} (REQUIRE_HUMAN)"
            )
        spec_id = intent.payload.get("experiment_spec_id")
        if spec_id not in self._specs:
            raise CycleError(
                "experiment spec is not registered on the spine; "
                "register_experiment MUST seal it before execution (fail closed)"
            )
        spec_seq = self._specs[spec_id]
        episode = self._gate.run(intent, adapter=adapter, approval=approval)
        if not (episode.closed and episode.close_reason == "completed"):
            raise CycleError(f"gate episode did not complete: {episode.close_reason!r}")
        intent_record = self._find_record("ActionIntent", intent.id)
        if intent_record is None or int(intent_record["seq"]) <= spec_seq:
            raise CycleError(
                "spine order violated: the experiment spec must precede the intent"
            )
        receipt_record = self._find_record("ExecutionReceipt", episode.receipt_id or "")
        if receipt_record is None or not receipt_record["payload"].get("external_id"):
            raise CycleError("no signed receipt facts on the spine; fail closed")
        try:
            facts = json.loads(receipt_record["payload"]["external_id"])
        except (TypeError, ValueError) as exc:
            raise CycleError(f"receipt facts are unparseable: {exc!r}") from exc
        self._experiment = {"spec_id": spec_id, "episode": episode, "facts": facts}
        return episode

    # --------------------------------------------------------- 6. verify

    def verify(
        self,
        spec: ExperimentSpec,
        rerun: Callable[[], tuple[float, float]],
        *,
        verifier_id: str,
        tests_green: bool,
    ) -> VerifierRecord:
        """Independent re-execution of both harnesses, checked against the
        adapter-attested receipt facts (mismatch -> CycleError, fail closed).
        """
        if self._experiment is None or self._experiment["spec_id"] != spec.id:
            raise CycleError("no gated execution on record for this spec; fail closed")
        baseline_value, measured_value = rerun()
        baseline_value = float(baseline_value)
        measured_value = float(measured_value)
        facts = self._experiment["facts"]
        if facts.get("workload_id") != spec.workload_id or facts.get("metric") != spec.metric_id:
            raise CycleError("receipt facts do not match the pre-registered workload/metric")
        if baseline_value != float(facts.get("baseline_value")) or measured_value != float(
            facts.get("candidate_value")
        ):
            raise CycleError(
                "verifier re-run contradicts the adapter-attested receipt facts "
                f"(rerun=({baseline_value}, {measured_value}), facts={facts!r})"
            )
        if baseline_value != spec.baseline_value:
            raise CycleError(
                f"re-measured baseline {baseline_value} != pre-registered "
                f"{spec.baseline_value}; the pre-registration is broken"
            )
        if baseline_value == 0.0:
            raise CycleError("baseline is zero; improvement ratio undefined")
        if spec.direction == "decrease":
            improvement_ratio = (baseline_value - measured_value) / baseline_value
        else:
            improvement_ratio = (measured_value - baseline_value) / baseline_value
        threshold_met = improvement_ratio >= spec.threshold_improvement
        record = VerifierRecord(
            experiment_spec_id=spec.id,
            verifier_id=verifier_id,
            baseline_value=baseline_value,
            measured_value=measured_value,
            improvement_ratio=improvement_ratio,
            threshold_met=threshold_met,
            reran_tests_green=bool(tests_green),
        )
        self._append(
            record,
            kind="VerifierRecord",
            refs={"experiment_spec_id": spec.id, "branch_id": spec.branch_id},
        )
        self._verifier = record
        return record

    # --------------------------------------------------------- 7. decide

    def decide(
        self,
        branch: StrategyBranch,
        *,
        decision: str,
        rationale: str,
        threshold_met: bool = False,
        revert_plan: str = "",
        decided_by: str | None = None,
    ) -> RetainRegressKillDecision:
        """Seal one terminal per-branch decision. ``retain`` REQUIRES
        threshold_met True (else CycleError, spine untouched); killed branches
        get first-class kill decisions — negative knowledge is sealed memory.
        """
        if not isinstance(branch, StrategyBranch) or branch.id not in self._branches:
            raise CycleError("unknown branch; decide operates on sealed branches only")
        if decision == "retain" and not threshold_met:
            raise CycleError(
                "retain requires threshold_met=True; an unproven branch is "
                "never retained (fail closed)"
            )
        try:
            record = RetainRegressKillDecision(
                branch_id=branch.id,
                loop_id=self.loop_id,
                decision=decision,
                rationale=rationale,
                decided_by=decided_by or self._authority.approver_id,
                revert_plan=revert_plan,
            )
        except ValueError as exc:
            raise CycleError(f"decision refused: {exc}") from exc
        self._append(
            record,
            kind="RetainRegressKillDecision",
            refs={"branch_id": branch.id, "loop_id": self.loop_id},
        )
        self._decisions.append(record)
        return record

    # ---------------------------------------------------- 8. seal capsule

    def seal_capsule(
        self,
        capsule_path: str | Path,
        verdict: str,
        *,
        capsule_ref: str | None = None,
    ) -> tuple[ClosureLoop, EvolutionCapsule]:
        """Write the proof capsule, then seal loop + capsule (ADR-8 order).

        The capsule FILE is written and hashed BEFORE the two seal appends;
        it records the spine head captured before the seal, every pre-seal
        record hash, and the ClosureLoop record hash (predicted with the
        frozen WP-01 formula, then asserted against the actual append). The
        EvolutionCapsule contract's ``sealed_head_hash`` is that same
        loop-seal head — verifiable on-chain as the capsule record's
        ``prev_hash``.
        """
        if (
            self._tree is None
            or self._selected is None
            or self._spec is None
            or self._verifier is None
            or not self._decisions
        ):
            raise CycleError("cycle is incomplete; refusing to seal a capsule")
        if verdict == "baseline_beaten" and not self._verifier.threshold_met:
            raise CycleError("verdict baseline_beaten requires threshold_met (fail closed)")
        if verdict == "baseline_held" and self._verifier.threshold_met:
            raise CycleError("verdict baseline_held contradicts threshold_met (fail closed)")
        if verdict not in ("baseline_beaten", "baseline_held"):
            raise CycleError(f"verdict {verdict!r} refused for a completed cycle")

        seq, head = self._head()
        records = list(self._spine.iter())
        chain_ok = bool(self._spine.verify_chain())
        experiment = self._experiment or {}
        episode = experiment.get("episode")
        episode_closed = bool(
            episode is not None and episode.closed and episode.close_reason == "completed"
        )
        ok = bool(chain_ok and episode_closed)

        decision_by_branch = {d.branch_id: d for d in self._decisions}
        branches_doc = []
        for branch_id in self._tree.branch_ids:
            branch = self._branches[branch_id]
            audit = self._audits.get(branch_id)
            decision = decision_by_branch.get(branch_id)
            branches_doc.append(
                {
                    "branch_id": branch_id,
                    "title": branch.title,
                    "audit_id": audit.id if audit else "",
                    "audit_overall": audit.overall if audit else "",
                    "decision_id": decision.id if decision else "",
                    "decision": decision.decision if decision else "",
                }
            )

        # ADR-8: pre-construct BOTH models in memory. The capsule id is
        # pre-declared so the loop model can reference it before either seal.
        capsule_id = uuid.uuid4().hex
        loop = ClosureLoop(
            cycle_index=self._cycle_index,
            tree_id=self._tree.id,
            selected_branch_id=self._selected.id,
            audit_ids=[a.id for a in self._audits.values()],
            experiment_spec_id=self._spec.id,
            verifier_record_id=self._verifier.id,
            decision_ids=[d.id for d in self._decisions],
            capsule_id=capsule_id,
            baseline_ref=self._spec.id,
            status="completed",
        )
        # Predict the loop record hash with the FROZEN WP-01 formula; the
        # actual append below is asserted against this prediction.
        loop_refs = {"cycle_index": self._cycle_index, "loop_id": self.loop_id}
        loop_body = {
            "seq": seq,
            "prev_hash": head,
            "kind": "ClosureLoop",
            "refs": loop_refs,
            "payload": loop.model_dump(mode="json"),
        }
        loop_record_hash = sha256_hex(canonical_json(loop_body).encode("utf-8"))

        capsule_doc = {
            "capsule_schema": "wp05-evolution-capsule/1.0",
            "ok": ok,
            "verdict": verdict,
            "cycle_index": self._cycle_index,
            "loop_id": self.loop_id,
            "baseline_value": self._verifier.baseline_value,
            "measured_value": self._verifier.measured_value,
            "improvement_ratio": self._verifier.improvement_ratio,
            "threshold_met": self._verifier.threshold_met,
            "metric": {
                "metric_id": self._spec.metric_id,
                "metric_unit": self._spec.metric_unit,
                "direction": self._spec.direction,
                "baseline_value": self._spec.baseline_value,
                "threshold_improvement": self._spec.threshold_improvement,
                "harness_ref": self._spec.harness_ref,
                "workload_id": self._spec.workload_id,
            },
            "experiment": {
                "experiment_spec_id": self._spec.id,
                "verifier_record_id": self._verifier.id,
                "episode_id": episode.id if episode else "",
                "episode_closed": episode_closed,
                "reran_tests_green": self._verifier.reran_tests_green,
                "receipt_facts": experiment.get("facts", {}),
            },
            "tree": {
                "tree_id": self._tree.id,
                "root_objective": self._tree.root_objective,
                "horizon": self._tree.horizon,
                "selection_rule": self._tree.selection_rule,
                "selected_branch_id": self._selected.id,
            },
            "branches": branches_doc,
            "decisions": [
                {
                    "decision_id": d.id,
                    "branch_id": d.branch_id,
                    "outcome": d.decision,
                    "rationale": d.rationale,
                    "decided_by": d.decided_by,
                }
                for d in self._decisions
            ],
            "spine": {
                # Captured BEFORE the two seal appends (spec 3.2 step 8).
                "head_before_seal": head,
                "record_count_before_seal": len(records),
                "record_hashes_before_seal": [r["record_hash"] for r in records],
                "chain_verified_before_seal": chain_ok,
                "closure_loop_record_hash": loop_record_hash,
                "sealed_head_hash": loop_record_hash,
                "sealed_head_note": (
                    "sealed_head_hash is the spine head after the ClosureLoop "
                    "seal append — on-chain it equals the EvolutionCapsule "
                    "record's prev_hash. The head after BOTH seal appends is "
                    "the capsule record's own hash, which cannot be embedded "
                    "in its own payload (sha256 self-reference)."
                ),
            },
        }
        path = Path(capsule_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        capsule_text = json.dumps(capsule_doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        path.write_text(capsule_text, encoding="utf-8")
        capsule_hash = sha256_hex(capsule_text.encode("utf-8"))

        capsule = EvolutionCapsule(
            id=capsule_id,
            loop_id=self.loop_id,
            cycle_index=self._cycle_index,
            capsule_path=capsule_ref or str(path),
            capsule_hash=capsule_hash,
            sealed_head_hash=loop_record_hash,
            verdict=verdict,
        )
        loop_record = self._append(loop, kind="ClosureLoop", refs=loop_refs)
        if loop_record["record_hash"] != loop_record_hash:
            raise CycleError("loop seal hash drifted from the frozen formula; fail closed")
        self._append(
            capsule,
            kind="EvolutionCapsule",
            refs={"loop_id": self.loop_id, "cycle_index": self._cycle_index},
        )
        return loop, capsule

    def seal_aborted(self, reason: str) -> ClosureLoop:
        """Seal an aborted cycle: a ClosureLoop with status="aborted" and
        capsule_id="" (the ONLY honest empty capsule_id, ADR-8) — and NO
        EvolutionCapsule contract, ever.
        """
        loop = ClosureLoop(
            cycle_index=self._cycle_index,
            tree_id=self._tree.id if self._tree else "",
            selected_branch_id=self._selected.id if self._selected else "",
            audit_ids=[a.id for a in self._audits.values()],
            experiment_spec_id=self._spec.id if self._spec else "",
            verifier_record_id=self._verifier.id if self._verifier else "",
            decision_ids=[d.id for d in self._decisions],
            capsule_id="",
            baseline_ref="",
            status="aborted",
        )
        self._append(
            loop,
            kind="ClosureLoop",
            refs={"cycle_index": self._cycle_index, "loop_id": self.loop_id},
        )
        self._event(
            "CYCLE_ABORTED",
            loop,
            {"loop_id": self.loop_id, "reason": reason},
        )
        return loop
