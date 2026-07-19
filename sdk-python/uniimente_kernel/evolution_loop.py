"""Fast Capability Evolution: the automated fast loop.

Phase 3 of the Final Plan. Where `evolution` provides the eight cycle
primitives executed by hand, this module automates the loop around them:

    bottleneck -> candidate generation (all eleven archetypes, validated
    identically whether the proposer is a template, a model, or a human)
    -> isolated testing (each branch measured in a scrubbed subprocess:
    fresh working directory, empty environment, hard timeout)
    -> failure analysis (every failure classified and ledgered; negative
    results are first-class)
    -> comparison against the baseline (strict, directional; a tie is
    not beating)
    -> an ImprovementProposal addressed to the human gate.

Sovereignty rules, mechanical:

- The proposal has no apply path. `applied` is fixed False and no method
  on any class here mutates the institution. Applying a proposal means a
  capability grant crossing the ConsequenceGate with founder authority.
- An injected proposer may be a model. Its output passes through exactly
  the same validation as a hand-written template: eleven archetypes, all
  required branch fields, JSON-safe entries. The proposer's confidence
  changes nothing.
- RETAIN still requires a verifier at levels 1-5, enforced downstream by
  the EvolutionCapsule. The loop cannot talk itself into promotion.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from uniimente_kernel.evolution import (
    BRANCH_ARCHETYPES,
    EvolutionCapsule,
    EvolutionError,
    ExperimentSpec,
    SpiderWebAudit,
    StrategyBranch,
    StrategyTree,
    VerifierRecord,
)
from uniimente_kernel.ledger import DecisionLedger

FAILURE_CLASSES = ("exception", "timeout", "nonzero_exit", "invalid_outcome")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json_safe(value: Any, owner: str) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise EvolutionError(f"{owner} must be JSON-serializable: {exc}") from exc


# --- Branch generation --------------------------------------------------- #

@dataclass
class BranchCandidate:
    """One archetype's branch fields plus its isolated experiment entry.

    `branch_fields` holds every StrategyBranch content field except the
    archetype itself. `entry` names the callable that measures this
    branch's configuration inside the isolated runner:
    {"module": dotted path, "function": name, "kwargs": {...}} with an
    optional "pythonpath" prepended to the subprocess environment.
    """

    archetype: str
    branch_fields: Dict[str, Any]
    entry: Dict[str, Any]

    def validate(self) -> "BranchCandidate":
        if self.archetype not in BRANCH_ARCHETYPES:
            raise EvolutionError(
                f"archetype must be one of {list(BRANCH_ARCHETYPES)}"
            )
        _json_safe(self.branch_fields, f"BranchCandidate({self.archetype}).branch_fields")
        _json_safe(self.entry, f"BranchCandidate({self.archetype}).entry")
        if not isinstance(self.entry.get("module"), str) or not self.entry["module"]:
            raise EvolutionError("entry.module is required")
        if not isinstance(self.entry.get("function"), str) or not self.entry["function"]:
            raise EvolutionError("entry.function is required")
        if not isinstance(self.entry.get("kwargs", {}), dict):
            raise EvolutionError("entry.kwargs must be a dict")
        if "pythonpath" in self.entry and not isinstance(self.entry["pythonpath"], str):
            raise EvolutionError("entry.pythonpath must be a string")
        # The branch fields must assemble into a valid StrategyBranch now,
        # so a malformed candidate fails at generation, not mid-cycle.
        try:
            StrategyBranch(archetype=self.archetype, **self.branch_fields).validate()
        except TypeError as exc:
            raise EvolutionError(
                f"BranchCandidate({self.archetype}) branch fields invalid: {exc}"
            ) from exc
        return self

    def to_branch(self, *, bottleneck: str) -> StrategyBranch:
        branch = StrategyBranch(archetype=self.archetype, **self.branch_fields)
        branch.bottleneck = bottleneck
        return branch


class BranchGenerator:
    """Produces and validates the eleven-archetype candidate set.

    The proposer callable receives (bottleneck=..., context=...) and
    returns eleven candidate dicts. Whether it is a deterministic
    template, a model, or a human changes nothing: every candidate is
    validated the same way, and the full archetype set is required.
    """

    def __init__(
        self,
        proposer: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    ) -> None:
        self.proposer = proposer

    def propose(self, *, bottleneck: str, context: Dict[str, Any]) -> List[BranchCandidate]:
        if not bottleneck:
            raise EvolutionError("bottleneck is required")
        raw = (
            self.proposer(bottleneck=bottleneck, context=context)
            if self.proposer is not None
            else context.get("candidates")
        )
        if not isinstance(raw, list) or not raw:
            raise EvolutionError("proposer must return a non-empty candidate list")
        candidates: List[BranchCandidate] = []
        seen: set = set()
        for item in raw:
            if not isinstance(item, dict):
                raise EvolutionError("each candidate must be a dict")
            candidate = BranchCandidate(
                archetype=item.get("archetype", ""),
                branch_fields=item.get("branch_fields", {}),
                entry=item.get("entry", {}),
            ).validate()
            if candidate.archetype in seen:
                raise EvolutionError(f"duplicate archetype: {candidate.archetype}")
            seen.add(candidate.archetype)
            candidates.append(candidate)
        missing = [a for a in BRANCH_ARCHETYPES if a not in seen]
        if missing:
            raise EvolutionError(f"archetypes not generated: {missing}")
        return candidates


# --- Isolated testing ----------------------------------------------------- #

@dataclass
class IsolatedResult:
    ok: bool
    outcome: Optional[Dict[str, float]]
    failure_class: Optional[str]
    detail: str
    duration_seconds: float


class IsolatedRunner:
    """Runs one experiment entry in a scrubbed subprocess.

    Isolation properties: the child starts with an empty environment
    (only PATH plus the declared pythonpath), a fresh temporary working
    directory, and a hard timeout. No credentials, tokens, or parent
    state can leak into an experiment. The child prints exactly one
    JSON result line; anything else is an invalid outcome.
    """

    def __init__(self, *, timeout_seconds: float = 30.0, python: str = sys.executable) -> None:
        if timeout_seconds <= 0:
            raise EvolutionError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds
        self.python = python

    def run(self, entry: Dict[str, Any]) -> IsolatedResult:
        started = time.monotonic()
        workdir = tempfile.mkdtemp(prefix="uniimente_iso_")
        request_path = os.path.join(workdir, "request.json")
        with open(request_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "module": entry["module"],
                    "function": entry["function"],
                    "kwargs": entry.get("kwargs", {}),
                },
                handle,
            )
        package_parent = str(Path(__file__).resolve().parent.parent)
        pythonpath = os.pathsep.join(
            p for p in [entry.get("pythonpath", ""), package_parent] if p
        )
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": pythonpath,
        }
        try:
            proc = subprocess.run(
                [self.python, "-m", "uniimente_kernel._isolated_worker", request_path],
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return IsolatedResult(
                ok=False,
                outcome=None,
                failure_class="timeout",
                detail=f"exceeded {self.timeout_seconds}s",
                duration_seconds=time.monotonic() - started,
            )
        finally:
            _rmtree(workdir)
        duration = time.monotonic() - started
        if proc.returncode != 0:
            return IsolatedResult(
                ok=False,
                outcome=None,
                failure_class="nonzero_exit",
                detail=(proc.stderr or "")[-500:],
                duration_seconds=duration,
            )
        lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
        try:
            result = json.loads(lines[-1]) if lines else None
        except json.JSONDecodeError:
            result = None
        if not isinstance(result, dict) or "ok" not in result:
            return IsolatedResult(
                ok=False,
                outcome=None,
                failure_class="invalid_outcome",
                detail="worker did not emit a final JSON result line",
                duration_seconds=duration,
            )
        if not result["ok"]:
            return IsolatedResult(
                ok=False,
                outcome=None,
                failure_class="exception",
                detail=str(result.get("error", "unknown exception"))[:500],
                duration_seconds=duration,
            )
        outcome = result.get("outcome")
        if not isinstance(outcome, dict) or not outcome:
            return IsolatedResult(
                ok=False,
                outcome=None,
                failure_class="invalid_outcome",
                detail="outcome must be a non-empty metric dict",
                duration_seconds=duration,
            )
        for name, value in outcome.items():
            if not isinstance(name, str) or not isinstance(value, (int, float)) or isinstance(value, bool):
                return IsolatedResult(
                    ok=False,
                    outcome=None,
                    failure_class="invalid_outcome",
                    detail=f"metric {name!r} must map to a number",
                    duration_seconds=duration,
                )
        return IsolatedResult(
            ok=True,
            outcome={k: float(v) for k, v in outcome.items()},
            failure_class=None,
            detail="",
            duration_seconds=duration,
        )


def _rmtree(path: str) -> None:
    import shutil

    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass  # cleanup failure never masks the experiment result


# --- Failure analysis ----------------------------------------------------- #

@dataclass
class FailureRecord:
    branch_id: str
    archetype: str
    failure_class: str
    detail: str
    recorded_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return dict(vars(self))


class FailureAnalyzer:
    """Classifies isolated-run failures. Negative results are evidence."""

    def classify(
        self,
        *,
        branch_id: str,
        archetype: str,
        result: IsolatedResult,
    ) -> Optional[FailureRecord]:
        if result.ok:
            return None
        failure_class = result.failure_class or "invalid_outcome"
        if failure_class not in FAILURE_CLASSES:
            failure_class = "invalid_outcome"
        return FailureRecord(
            branch_id=branch_id,
            archetype=archetype,
            failure_class=failure_class,
            detail=result.detail,
        )

    def summarize(self, records: List[FailureRecord]) -> Dict[str, Any]:
        by_class: Dict[str, int] = {}
        for record in records:
            by_class[record.failure_class] = by_class.get(record.failure_class, 0) + 1
        return {
            "total": len(records),
            "by_class": by_class,
            "records": [r.to_dict() for r in records],
        }


# --- Comparison ----------------------------------------------------------- #

class OutcomeComparator:
    """Ranks branch outcomes against the baseline, strict and directional.

    Margin is the worst-case directional improvement ratio across the
    experiment's metrics: for "higher", (outcome - base) / scale; for
    "lower", (base - outcome) / scale, with scale = |base| or 1. Ranking
    is deterministic: beating branches first by margin descending, then
    branch id ascending. A tie with the baseline never counts as beating.
    """

    def rank(
        self,
        *,
        experiment: ExperimentSpec,
        outcomes: Dict[str, Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        experiment.validate()
        rows: List[Dict[str, Any]] = []
        for branch_id, outcome in outcomes.items():
            beats = experiment.beats_baseline(outcome)
            margin = self._margin(experiment, outcome)
            rows.append({
                "branch_id": branch_id,
                "beats_baseline": beats,
                "margin": margin,
            })
        rows.sort(key=lambda r: (not r["beats_baseline"], -r["margin"], r["branch_id"]))
        return rows

    @staticmethod
    def _margin(experiment: ExperimentSpec, outcome: Dict[str, float]) -> float:
        margins: List[float] = []
        for name, direction in experiment.metrics.items():
            if name not in outcome:
                return float("-inf")
            base = experiment.baseline[name]
            scale = abs(base) or 1.0
            observed = outcome[name]
            if direction == "higher":
                margins.append((observed - base) / scale)
            else:
                margins.append((base - observed) / scale)
        return min(margins) if margins else float("-inf")


# --- Improvement proposal ------------------------------------------------- #

@dataclass
class ImprovementProposal:
    """The loop's output: an evidenced proposal to the human gate.

    There is deliberately no apply path. `applied` is fixed False and no
    method here mutates anything. Adoption requires a capability grant
    crossing the ConsequenceGate under founder authority.
    """

    proposal_id: str
    bottleneck: str
    selected_branch_id: str
    selected_archetype: str
    decision: str
    capsule_id: str
    outcome: Dict[str, float]
    evidence_refs: List[str]
    verifier_level: int
    summary: str
    recorded_at: str = field(default_factory=_now)
    applied: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return dict(vars(self))


# --- The loop ------------------------------------------------------------- #

class EvolutionLoop:
    """One automated cycle: generate, isolate, analyze, compare, propose."""

    def __init__(
        self,
        ledger: DecisionLedger,
        *,
        generator: Optional[BranchGenerator] = None,
        runner: Optional[IsolatedRunner] = None,
        analyzer: Optional[FailureAnalyzer] = None,
        comparator: Optional[OutcomeComparator] = None,
    ) -> None:
        self.ledger = ledger
        self.generator = generator or BranchGenerator()
        self.runner = runner or IsolatedRunner()
        self.analyzer = analyzer or FailureAnalyzer()
        self.comparator = comparator or OutcomeComparator()

    def run_cycle(
        self,
        *,
        bottleneck: str,
        context: Dict[str, Any],
        experiment: ExperimentSpec,
        audit_sides: Dict[str, str],
        mechanism_map: Dict[str, Optional[str]],
        requirements: Dict[str, bool],
        verifier: VerifierRecord,
        decider: str,
        rationale: str,
        outcome_evidence_refs: List[str],
        internal_metric_met: bool = True,
        external_consequence_met: bool = True,
    ) -> ImprovementProposal:
        experiment.validate()
        verifier.validate()
        self.ledger.record("evolution_loop_started", {
            "bottleneck": bottleneck,
            "experiment_id": experiment.experiment_id,
        })

        # 1. Generate + validate candidates into the strategy tree.
        candidates = self.generator.propose(bottleneck=bottleneck, context=context)
        tree = StrategyTree(self.ledger, bottleneck=bottleneck)
        entries: Dict[str, Dict[str, Any]] = {}
        archetypes: Dict[str, str] = {}
        for candidate in candidates:
            branch = tree.add(candidate.to_branch(bottleneck=bottleneck))
            entries[branch.branch_id] = candidate.entry
            archetypes[branch.branch_id] = branch.archetype
            self.ledger.record("branch_candidate_generated", {
                "bottleneck": bottleneck,
                "branch_id": branch.branch_id,
                "archetype": branch.archetype,
                "entry": {
                    "module": candidate.entry["module"],
                    "function": candidate.entry["function"],
                },
            })

        # 2. Isolated testing of every branch.
        results: Dict[str, IsolatedResult] = {}
        for branch_id, entry in entries.items():
            result = self.runner.run(entry)
            results[branch_id] = result
            self.ledger.record(
                "isolated_run_completed" if result.ok else "isolated_run_failed",
                {
                    "bottleneck": bottleneck,
                    "branch_id": branch_id,
                    "archetype": archetypes[branch_id],
                    "failure_class": result.failure_class,
                    "outcome": result.outcome,
                    "duration_seconds": result.duration_seconds,
                },
            )

        # 3. Failure analysis: every failure classified and preserved.
        failures = [
            record
            for record in (
                self.analyzer.classify(
                    branch_id=branch_id,
                    archetype=archetypes[branch_id],
                    result=result,
                )
                for branch_id, result in results.items()
            )
            if record is not None
        ]
        failed_ids = {record.branch_id for record in failures}
        self.ledger.record("failure_analysis_completed", {
            "bottleneck": bottleneck,
            **self.analyzer.summarize(failures),
        })

        # 4. Comparison against baseline over successful outcomes only.
        outcomes = {
            branch_id: result.outcome
            for branch_id, result in results.items()
            if result.ok and result.outcome is not None
        }
        ranking = self.comparator.rank(experiment=experiment, outcomes=outcomes)
        self.ledger.record("comparison_completed", {
            "bottleneck": bottleneck,
            "ranking": ranking,
        })

        # 5. Select on evidence. If nothing beats baseline, the honest
        # selection is do_nothing and the capsule will record regress.
        winner_row = next((r for r in ranking if r["beats_baseline"]), None)
        if winner_row is not None:
            winner_id = winner_row["branch_id"]
            winner_outcome = outcomes[winner_id]
            selection_rationale = rationale
        else:
            winner_id = next(
                branch_id
                for branch_id, archetype in archetypes.items()
                if archetype == "do_nothing"
            )
            winner_outcome = dict(experiment.baseline)
            selection_rationale = (
                "no candidate beat the baseline under strict directional "
                "comparison; preserving the incumbent configuration"
            )

        winner_margin = winner_row["margin"] if winner_row else None
        loss_reasons: Dict[str, str] = {}
        for branch_id in archetypes:
            if branch_id == winner_id:
                continue
            if branch_id in failed_ids:
                record = next(r for r in failures if r.branch_id == branch_id)
                loss_reasons[branch_id] = (
                    f"isolated run failed ({record.failure_class})"
                )
            elif branch_id in outcomes and not experiment.beats_baseline(outcomes[branch_id]):
                loss_reasons[branch_id] = "did not beat baseline"
            else:
                loss_reasons[branch_id] = (
                    f"beat baseline with smaller margin than "
                    f"{archetypes[winner_id]} ({winner_margin:.6f})"
                )
        tree.select(
            winner_id,
            decider=decider,
            rationale=selection_rationale,
            loss_reasons=loss_reasons,
        )

        # 6. Audit + capsule: the cycle closes under the same gates as a
        # hand-run cycle, including verifier-level authorization.
        audit = SpiderWebAudit(
            branch_id=winner_id,
            sides=audit_sides,
            mechanism_map=mechanism_map,
            requirements=requirements,
        )
        capsule = EvolutionCapsule(self.ledger).complete_cycle(
            bottleneck=bottleneck,
            tree=tree,
            selected_branch_id=winner_id,
            audit=audit,
            experiment=experiment,
            outcome=winner_outcome,
            outcome_evidence_refs=outcome_evidence_refs,
            verifier=verifier,
            internal_metric_met=internal_metric_met,
            external_consequence_met=external_consequence_met,
            rationale=selection_rationale,
        )

        # 7. Emit the proposal. It has no apply path by construction.
        proposal = ImprovementProposal(
            proposal_id=str(uuid.uuid4()),
            bottleneck=bottleneck,
            selected_branch_id=winner_id,
            selected_archetype=archetypes[winner_id],
            decision=capsule["decision"]["decision"],
            capsule_id=capsule["capsule_id"],
            outcome=winner_outcome,
            evidence_refs=outcome_evidence_refs,
            verifier_level=verifier.level,
            summary=capsule["decision"]["rationale"],
        )
        self.ledger.record("improvement_proposal_emitted", proposal.to_dict())
        return proposal


__all__ = [
    "BranchCandidate",
    "BranchGenerator",
    "EvolutionLoop",
    "FAILURE_CLASSES",
    "FailureAnalyzer",
    "FailureRecord",
    "ImprovementProposal",
    "IsolatedResult",
    "IsolatedRunner",
    "OutcomeComparator",
]
