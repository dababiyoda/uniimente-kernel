"""Capability Genesis Loop: verified deficit -> cheapest candidates -> shadow trial
-> dossier -> human-ratified binding -> reusable genome.

This is canonical UNIIMENTE morphogenesis in the INTENT-0030 sense: functional
capability formation in response to a *verified* discrepancy, with no digital
cells, tissues or developmental fields. Every stage reuses an existing kernel
mechanism; the loop only connects them:

    DeficitDetector      reads recorded CognitionCycles and emits content-addressed
                         CapabilityDeficits (repeated component failures, budget
                         refusals, refusal/silence/veto streaks).
    ladder admission     candidates are admissible only in resourcefulness-ladder
                         order (docs/FOUNDER_EFFECT_COMPILER.md): a rung may hold a
                         candidate only when every cheaper rung records an outcome,
                         and "new_architecture" only when all cheaper rungs were
                         searched. The anti-literalization gate, made executable.
    PartsBoard           shadow trials and the eventual binding, each through the
                         Consequence Gate with a single-action grant.
    trial aggregation    shadow_result records become sample counts, agreement
                         rates, observed consequence classes and failure classes
                         (evolution.failure_analysis).
    dossier              the Capability Genesis contract fields, content-addressed,
                         so what a human reviewed is exactly what gets bound.
    ratification         evolution.capsule verifier tiers: hypothesis-only
                         verifiers (same-model critique, intrinsic confidence)
                         cannot retain; retain needs the minimum sample, no
                         doctrinal refusal in trial, and a whole-body closure that
                         is not FALSELY_CLOSED.
    GenomeRegistry       a retained part becomes a CapabilityGenome and a rung-1
                         ("existing_capability") candidate for later deficits, so
                         each genesis makes the next one cheaper.

Authority is unchanged: observing a deficit, proposing candidates, aggregating
trials and recording regress/kill/lapse grant nothing and need no grant (stopping
is always free). Shadowing and retaining pass the Gate exactly as any other
PartsBoard change. The loop has no path that binds anything without a grant.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from capabilities.genome import (
    CONSEQUENCE_CLASSES,
    AuthorityEnvelope,
    CapabilityGenome,
    GenomeRegistry,
)
from closure.whole_body import Loop, LoopEvidence, WholeBodyClosureController
from evolution.capsule import RetainRegressKill, RetainRegressKillDecision, VerifierRecord
from evolution.failure_analysis import classify

from .contracts import ContractError, canonical_copy, digest, require_hash, require_text
from .parts import ACTIVE, SHADOW, SLOT_PATTERN, PartsBoard
from .runtime import CognitionCycle, CycleStatus

# Resourcefulness ladder, in order, from docs/FOUNDER_EFFECT_COMPILER.md.
LADDER = (
    "existing_capability",
    "reconfigure_compose",
    "commodity_infrastructure",
    "open_source",
    "api_plugin_service",
    "authorized_computer_use",
    "small_utility",
    "coding_agent_team",
    "omnimorph_org_design",
    "new_architecture",
    "escalate_or_abstain",
)
RUNG_OUTCOMES = ("candidate", "searched_none", "not_applicable")

DEFICIT_KINDS = (
    "component_failure",   # one proposer/evaluator keeps raising
    "budget_refusal",      # one component keeps exhausting the resource governor
    "refusal_streak",      # cycles end REFUSED: candidates exist, none survives
    "silence_streak",      # cycles end SILENT: nothing is proposed at all
    "veto_streak",         # one evaluator vetoes in cycle after cycle
)
RUNTIME_SCOPE = "runtime"


def _scope(value: str) -> str:
    value = require_text("scope", value)
    if value != RUNTIME_SCOPE and not SLOT_PATTERN.match(value):
        raise ContractError("scope must be a slot ('proposer:<role>'/'evaluator:<role>') or 'runtime'")
    return value


@dataclass(frozen=True)
class CapabilityDeficit:
    """A content-addressed, evidence-bearing statement that a function is failing."""

    kind: str
    scope: str
    evidence_cycle_ids: tuple[str, ...]
    observed: int
    window: int
    note: str = ""

    def __post_init__(self) -> None:
        if self.kind not in DEFICIT_KINDS:
            raise ContractError(f"unknown deficit kind {self.kind!r}")
        object.__setattr__(self, "scope", _scope(self.scope))
        ids = tuple(require_hash("evidence_cycle_ids[]", c) for c in self.evidence_cycle_ids)
        if not ids:
            raise ContractError("a deficit must cite at least one recorded cycle")
        object.__setattr__(self, "evidence_cycle_ids", tuple(sorted(set(ids))))
        if not isinstance(self.observed, int) or isinstance(self.observed, bool) or self.observed < 1:
            raise ContractError("observed must be a positive integer")
        if not isinstance(self.window, int) or isinstance(self.window, bool) or self.window < self.observed:
            raise ContractError("window must be an integer >= observed")
        if not isinstance(self.note, str):
            raise ContractError("note must be text")

    @property
    def deficit_id(self) -> str:
        return digest({"kind": "egregore-deficit", "deficit_kind": self.kind, "scope": self.scope,
                       "evidence_cycle_ids": list(self.evidence_cycle_ids)})

    def to_dict(self) -> dict[str, Any]:
        return {"deficit_id": self.deficit_id, "kind": self.kind, "scope": self.scope,
                "evidence_cycle_ids": list(self.evidence_cycle_ids), "observed": self.observed,
                "window": self.window, "note": self.note}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CapabilityDeficit":
        deficit = cls(kind=value["kind"], scope=value["scope"],
                      evidence_cycle_ids=tuple(value["evidence_cycle_ids"]),
                      observed=int(value["observed"]), window=int(value["window"]),
                      note=value.get("note", ""))
        if "deficit_id" in value and value["deficit_id"] != deficit.deficit_id:
            raise ContractError("persisted deficit_id does not match its content")
        return deficit


class DeficitDetector:
    """Pure function over recorded cycles. Emits nothing below its thresholds."""

    def __init__(self, *, min_occurrences: int = 3, window: int = 10):
        if min_occurrences < 1 or window < min_occurrences:
            raise ContractError("window must be >= min_occurrences >= 1")
        self.min_occurrences = min_occurrences
        self.window = window

    def scan(self, cycles: Sequence[CognitionCycle]) -> list[CapabilityDeficit]:
        recent = list(cycles)[-self.window:]
        if not recent:
            return []
        hits: dict[tuple[str, str], list[str]] = {}

        def hit(kind: str, scope: str, cycle_id: str) -> None:
            hits.setdefault((kind, scope), []).append(cycle_id)

        for cycle in recent:
            if not isinstance(cycle, CognitionCycle):
                raise ContractError("scan requires CognitionCycle values")
            for failure in cycle.failures:
                component = failure.get("component", "")
                if component.startswith("shadow:") or not SLOT_PATTERN.match(component):
                    continue
                kind = "budget_refusal" if failure.get("disposition") == "budget_refusal" else "component_failure"
                hit(kind, component, cycle.cycle_id)
            if cycle.status == CycleStatus.REFUSED:
                hit("refusal_streak", RUNTIME_SCOPE, cycle.cycle_id)
            elif cycle.status == CycleStatus.SILENT:
                hit("silence_streak", RUNTIME_SCOPE, cycle.cycle_id)
            vetoing = {a.role for a in cycle.assessments if a.veto}
            for role in vetoing:
                hit("veto_streak", f"evaluator:{role}", cycle.cycle_id)

        deficits = []
        for (kind, scope), cycle_ids in sorted(hits.items()):
            distinct = sorted(set(cycle_ids))
            if len(distinct) >= self.min_occurrences:
                deficits.append(CapabilityDeficit(kind=kind, scope=scope, evidence_cycle_ids=tuple(distinct),
                                                  observed=len(distinct), window=len(recent)))
        return deficits


class CaseState(str, Enum):
    OPEN = "open"
    TRIALING = "trialing"
    READY = "ready_for_ratification"
    RETAINED = "retained"
    REGRESSED = "regressed"
    KILLED = "killed"
    LAPSED = "lapsed"


_TERMINAL = {CaseState.RETAINED, CaseState.REGRESSED, CaseState.KILLED, CaseState.LAPSED}


class CapabilityGenesis:
    """Governed formation cases for one standing-cognition PartsBoard."""

    DEFICIT_RECORD = "egregore.deficit_observed"
    CANDIDATES_RECORD = "egregore.genesis_candidates"
    TRIAL_RECORD = "egregore.genesis_trial"
    DECISION_RECORD = "egregore.genesis_decision"
    CLOSE_RECORD = "egregore.genesis_closed"

    def __init__(self, *, ledger: Any, board: PartsBoard, genomes: GenomeRegistry | None = None,
                 min_trial_samples: int = 3):
        if not isinstance(board, PartsBoard) or board.ledger is not ledger:
            raise ContractError("genesis needs the PartsBoard that shares its ledger")
        if min_trial_samples < 1:
            raise ContractError("min_trial_samples must be positive")
        self.ledger = ledger
        self.board = board
        self.source = board.source
        self.genomes = genomes if genomes is not None else GenomeRegistry(ledger=ledger)
        self.min_trial_samples = min_trial_samples
        self.whole_body = WholeBodyClosureController()
        self._cases: dict[str, dict[str, Any]] = {}
        self._retained: dict[str, list[str]] = {}  # slot -> part_ids retained by this loop
        self._hydrate()

    # -- persistence -----------------------------------------------------
    def _hydrate(self) -> None:
        for record in getattr(self.ledger, "records", ()):
            payload = record.payload
            if payload.get("source") != self.source:
                continue
            try:
                if record.record_type == self.DEFICIT_RECORD:
                    self._apply_observe(CapabilityDeficit.from_dict(payload["deficit"]))
                elif record.record_type == self.CANDIDATES_RECORD:
                    case = self._cases[payload["case_id"]]
                    case["ladder"] = dict(payload["ladder"])
                    case["candidates"] = {c["part_id"]: dict(c) for c in payload["candidates"]}
                    case["proposed_by"] = payload.get("proposed_by")
                elif record.record_type == self.TRIAL_RECORD:
                    case = self._cases[payload["case_id"]]
                    case["trials"][payload["part_id"]] = dict(payload["aggregate"])
                    self._advance_after_trial(case, payload["part_id"])
                elif record.record_type == self.DECISION_RECORD:
                    self._apply_decision_record(payload)
                elif record.record_type == self.CLOSE_RECORD:
                    case = self._cases[payload["case_id"]]
                    if CaseState(case["state"]) not in _TERMINAL:
                        case["state"] = payload["outcome"]
            except (KeyError, ValueError, TypeError, ContractError):
                continue  # malformed history is retained as history, never applied

    def _apply_decision_record(self, payload: Mapping[str, Any]) -> None:
        case = self._cases[payload["case_id"]]
        decision = payload["decision"]
        if decision == RetainRegressKill.RETAIN:
            # A retained label is applied only when the ledger holds the authorized
            # binding it claims; a forged decision record cannot mark a part retained.
            binding = self.ledger.find(payload.get("binding_hash"))
            if (binding is None or binding.record_type != PartsBoard.BINDING_RECORD
                    or binding.payload.get("slot") != payload["slot"]
                    or binding.payload.get("part_id") != payload["part_id"]
                    or binding.payload.get("mode") != ACTIVE):
                return
            case["state"] = CaseState.RETAINED.value
            self._retained.setdefault(payload["slot"], []).append(payload["part_id"])
        elif decision == RetainRegressKill.REGRESS:
            case["state"] = CaseState.REGRESSED.value
        elif decision == RetainRegressKill.KILL:
            case["state"] = CaseState.KILLED.value
        case["decision"] = canonical_copy(dict(payload))

    def _apply_observe(self, deficit: CapabilityDeficit) -> str:
        case_id = deficit.deficit_id
        case = self._cases.get(case_id)
        if case is None:
            self._cases[case_id] = {
                "case_id": case_id, "deficit": deficit.to_dict(), "recurrence": 1,
                "state": CaseState.OPEN.value, "ladder": {}, "candidates": {}, "trials": {},
                "proposed_by": None, "decision": None,
            }
        else:
            case["recurrence"] += 1
        return case_id

    # -- views -----------------------------------------------------------
    def case(self, case_id: str) -> dict[str, Any]:
        if case_id not in self._cases:
            raise ContractError("unknown genesis case")
        return canonical_copy(self._cases[case_id])

    def cases(self, *, state: CaseState | None = None) -> list[dict[str, Any]]:
        rows = [canonical_copy(c) for c in self._cases.values()]
        if state is not None:
            rows = [r for r in rows if r["state"] == state.value]
        return sorted(rows, key=lambda r: r["case_id"])

    def reuse_candidates(self, slot: str) -> list[dict[str, Any]]:
        """Parts this loop already retained for ``slot`` that are registered now.

        This is the compounding path: a past genesis is the cheapest rung of the
        next one. Retained parts whose code is not registered in this process are
        reported as unresolved instead of being guessed.
        """
        rows = []
        for part_id in self._retained.get(slot, []):
            rows.append({"part_id": part_id, "slot": slot, "rung": LADDER[0],
                         "resolved": self.board.resolved(part_id),
                         "rationale": "retained by an earlier genesis for this slot"})
        return rows

    # -- stage 1: observe ----------------------------------------------------
    def observe(self, deficit: CapabilityDeficit) -> str:
        """Open a case or count a recurrence. Grants nothing."""
        if not isinstance(deficit, CapabilityDeficit):
            raise ContractError("observe requires a CapabilityDeficit")
        case_id = self._apply_observe(deficit)
        self.ledger.append(self.DEFICIT_RECORD, {
            "source": self.source, "deficit": deficit.to_dict(),
            "recurrence": self._cases[case_id]["recurrence"], "disposition": "observed_not_authorized",
        })
        return case_id

    # -- stage 2: candidates in ladder order ---------------------------------
    def propose(self, case_id: str, *, ladder: Mapping[str, str],
                candidates: Sequence[Mapping[str, Any]], proposed_by: str) -> str:
        case = self._live_case(case_id)
        clean_ladder = {}
        for rung, outcome in ladder.items():
            if rung not in LADDER:
                raise ContractError(f"unknown ladder rung {rung!r}")
            if outcome not in RUNG_OUTCOMES:
                raise ContractError(f"rung outcome must be one of {RUNG_OUTCOMES}")
            clean_ladder[rung] = outcome
        clean_candidates: dict[str, dict[str, Any]] = {}
        for raw in candidates:
            part_id = require_hash("candidate part_id", raw["part_id"])
            slot = _scope(raw["slot"])
            if slot == RUNTIME_SCOPE:
                raise ContractError("a candidate must name a concrete slot")
            if case["deficit"]["scope"] != RUNTIME_SCOPE and slot != case["deficit"]["scope"]:
                raise ContractError("candidate slot does not match the deficit's scope")
            rung = raw["rung"]
            if rung not in LADDER:
                raise ContractError(f"unknown ladder rung {rung!r}")
            if clean_ladder.get(rung) != "candidate":
                raise ContractError(f"ladder must record {rung!r} as 'candidate'")
            self._check_admissible(rung, clean_ladder)
            spec = self.board.spec(part_id)
            if spec is None:
                raise ContractError("candidate part is not registered on the board")
            if spec.slot != slot:
                raise ContractError(f"part is registered for {spec.slot}, not {slot}")
            clean_candidates[part_id] = {"part_id": part_id, "slot": slot, "rung": rung,
                                         "rationale": require_text("rationale", raw.get("rationale", ""))}
        if not clean_candidates and "escalate_or_abstain" not in clean_ladder:
            raise ContractError("no candidates: record 'escalate_or_abstain' or supply at least one")
        for rung, outcome in clean_ladder.items():
            if (outcome == "candidate" and rung != "escalate_or_abstain"
                    and not any(c["rung"] == rung for c in clean_candidates.values())):
                raise ContractError(f"ladder marks {rung!r} as 'candidate' but no candidate was supplied for it")
        case["ladder"] = clean_ladder
        case["candidates"] = clean_candidates
        case["proposed_by"] = require_text("proposed_by", proposed_by)
        record = self.ledger.append(self.CANDIDATES_RECORD, {
            "source": self.source, "case_id": case_id, "ladder": clean_ladder,
            "candidates": sorted(clean_candidates.values(), key=lambda c: c["part_id"]),
            "proposed_by": require_text("proposed_by", proposed_by), "disposition": "proposed_not_bound",
        })
        return record.hash

    @staticmethod
    def _check_admissible(rung: str, ladder: Mapping[str, str]) -> None:
        index = LADDER.index(rung)
        cheaper = LADDER[:index]
        missing = [r for r in cheaper if r not in ladder]
        if missing:
            raise ContractError(f"{rung!r} needs an outcome recorded for every cheaper rung; missing {missing}")
        if rung == "new_architecture":
            unsearched = [r for r in cheaper if ladder[r] == "candidate"]
            if unsearched:
                raise ContractError("new_architecture is admissible only when no cheaper rung holds a candidate")

    # -- stage 3: shadow trial --------------------------------------------------
    def shadow(self, case_id: str, part_id: str, *, actor: str, gate: Any, grant: Mapping[str, Any]) -> str:
        case = self._live_case(case_id)
        candidate = case["candidates"].get(part_id)
        if candidate is None:
            raise ContractError("part is not a candidate of this case")
        record_hash = self.board.change(actor=actor, slot=candidate["slot"], part_id=part_id,
                                        mode=SHADOW, gate=gate, grant=grant)
        if CaseState(case["state"]) == CaseState.OPEN:
            case["state"] = CaseState.TRIALING.value
        return record_hash

    def record_trials(self, case_id: str, part_id: str, shadow_record_hashes: Sequence[str]) -> dict[str, Any]:
        """Aggregate PartsBoard shadow results for one candidate into its trial record."""
        case = self._live_case(case_id)
        candidate = case["candidates"].get(part_id)
        if candidate is None:
            raise ContractError("part is not a candidate of this case")
        previous = case["trials"].get(part_id, {})
        seen = set(previous.get("record_hashes", []))
        agg = {
            "samples": previous.get("samples", 0),
            "failures": previous.get("failures", 0),
            "failure_classes": dict(previous.get("failure_classes", {})),
            "identical": previous.get("identical", 0),
            "veto_agreements": previous.get("veto_agreements", 0),
            "assessments": previous.get("assessments", 0),
            "consequence_classes": sorted(previous.get("consequence_classes", [])),
            "record_hashes": sorted(seen),
        }
        classes = set(agg["consequence_classes"])
        for raw_hash in shadow_record_hashes:
            record_hash = require_hash("shadow_record_hashes[]", raw_hash)
            if record_hash in seen:
                continue
            record = self.ledger.find(record_hash)
            if record is None or record.record_type != PartsBoard.SHADOW_RESULT_RECORD:
                raise ContractError("hash is not a shadow_result record")
            payload = record.payload
            if (payload.get("source") != self.source or payload.get("slot") != candidate["slot"]
                    or payload.get("shadow_part_id") != part_id):
                raise ContractError("shadow result belongs to another slot or part")
            seen.add(record_hash)
            agg["samples"] += 1
            if payload.get("failure"):
                agg["failures"] += 1
                klass = classify(payload["failure"])
                agg["failure_classes"][klass] = agg["failure_classes"].get(klass, 0) + 1
                continue
            comparison = payload.get("comparison", {})
            if "identical" in comparison:
                agg["identical"] += 1 if comparison["identical"] else 0
                for shadow_candidate in comparison.get("shadow_candidates", []):
                    klass = shadow_candidate.get("consequence_class")
                    if klass not in CONSEQUENCE_CLASSES:
                        raise ContractError("shadow candidate carries an unknown consequence class")
                    classes.add(klass)
            for row in comparison.get("assessments", []):
                agg["assessments"] += 1
                agg["veto_agreements"] += 1 if row.get("veto_agrees") else 0
        agg["consequence_classes"] = sorted(classes)
        agg["record_hashes"] = sorted(seen)
        case["trials"][part_id] = agg
        self._advance_after_trial(case, part_id)
        self.ledger.append(self.TRIAL_RECORD, {
            "source": self.source, "case_id": case_id, "part_id": part_id,
            "aggregate": canonical_copy(agg), "disposition": "no_influence",
        })
        return canonical_copy(agg)

    def _advance_after_trial(self, case: dict[str, Any], part_id: str) -> None:
        state = CaseState(case["state"])
        if state in _TERMINAL:
            return
        samples = case["trials"].get(part_id, {}).get("samples", 0)
        case["state"] = (CaseState.READY if samples >= self.min_trial_samples else CaseState.TRIALING).value

    # -- stage 4: dossier -------------------------------------------------------
    def dossier(self, case_id: str, part_id: str) -> dict[str, Any]:
        """The Capability Genesis contract for one candidate, content-addressed."""
        case = self.case(case_id)
        candidate = case["candidates"].get(part_id)
        if candidate is None:
            raise ContractError("part is not a candidate of this case")
        spec = self.board.spec(part_id)
        trial = case["trials"].get(part_id, {})
        slot = candidate["slot"]
        body = {
            "case_id": case_id,
            "deficit": case["deficit"],
            "recurrence": case["recurrence"],
            "target_effect": f"{case['deficit']['kind']} in {case['deficit']['scope']} stops recurring "
                             f"with {slot} served by {part_id}",
            "acceptance": {"min_trial_samples": self.min_trial_samples,
                           "no_doctrinal_refusal": True, "verifier_may_authorize_promotion": True},
            "ladder": case["ladder"],
            "candidate": candidate,
            "mechanism_provenance": None if spec is None else spec.to_dict(),
            "license": "unresolved: record in PartSpec.notes or provenance before external use",
            "builder": case["proposed_by"],
            "permissions": "declared by the part's implementation; the loop grants none",
            "cost_ceiling": "shadow calls bounded by the ResourceGovernor passed to shadow_run",
            "authority_envelope": {"execution_authority": "none",
                                   "consequence_classes_observed": trial.get("consequence_classes", [])},
            "sandbox_evidence": trial,
            "independent_verification": "absent until a ratification verifier record is attached",
            "known_failures": trial.get("failure_classes", {}),
            "attach_detach_rollback": {
                "attach": "PartsBoard.change(mode='active') under a Gate grant",
                "detach": "PartsBoard.change(part_id=None) under a Gate grant",
                "rollback_target": self.board.rollback_target(slot),
            },
            "lifecycle_state": case["state"],
            "owner": "alfonso_lopez",
            "review_and_kill": ["kill on any doctrinal_refusal in trial",
                                "regress when the active part still wins on the recorded comparisons",
                                f"lapse when the deficit stops recurring for {self.min_trial_samples} windows"],
        }
        body["dossier_hash"] = digest({"kind": "egregore-dossier", **body})
        return body

    # -- stage 5: ratify ------------------------------------------------------------
    def ratify(self, case_id: str, part_id: str, *, decision: str, reason: str, verifier: VerifierRecord,
               reviewed_dossier_hash: str, actor: str, gate: Any = None,
               grant: Mapping[str, Any] | None = None) -> str:
        """Record retain/regress/kill. Retain binds the part through the Gate."""
        case = self._live_case(case_id)
        candidate = case["candidates"].get(part_id)
        if candidate is None:
            raise ContractError("part is not a candidate of this case")
        if not isinstance(verifier, VerifierRecord):
            raise ContractError("ratify requires an evolution VerifierRecord")
        current = self.dossier(case_id, part_id)
        if require_hash("reviewed_dossier_hash", reviewed_dossier_hash) != current["dossier_hash"]:
            raise ContractError("dossier changed since review; re-read it before ratifying")
        rrk = RetainRegressKillDecision(decision=decision, reason=require_text("reason", reason),
                                        decided_by=require_text("actor", actor), verifier=verifier)
        problems = rrk.validate()
        if problems:
            raise ContractError("decision invalid: " + "; ".join(problems))

        binding_hash = None
        genome_key = None
        evaluation = None
        if decision == RetainRegressKill.RETAIN:
            trial = case["trials"].get(part_id, {})
            if trial.get("samples", 0) < self.min_trial_samples:
                raise ContractError(f"retain needs at least {self.min_trial_samples} shadow samples")
            if trial.get("failure_classes", {}).get("doctrinal_refusal"):
                raise ContractError("retain refused: the candidate met a doctrinal refusal in trial")
            genome = self._genome_for(case, candidate, trial, part_id)
            problems = genome.validate()
            if problems:
                raise ContractError("genome invalid: " + "; ".join(problems))
            evaluation = self._whole_body(case, candidate, trial, verifier, part_id)
            if evaluation.falsely_closed or evaluation.open_loops:
                raise ContractError("retain refused: whole-body closure is "
                                    f"{evaluation.overall} ({evaluation.required_actions})")
            binding_hash = self.board.change(actor=actor, slot=candidate["slot"], part_id=part_id,
                                             mode=ACTIVE, gate=gate, grant=grant)
            self.genomes.register(genome)
            genome_key = f"{genome.name}@{genome.version}"

        payload = {
            "source": self.source, "case_id": case_id, "slot": candidate["slot"], "part_id": part_id,
            "decision": decision, "reason": rrk.reason, "actor": rrk.decided_by,
            "verifier": {"level": verifier.level, "evidence": verifier.evidence, "decided_by": verifier.decided_by},
            "dossier_hash": current["dossier_hash"], "binding_hash": binding_hash, "genome": genome_key,
            "whole_body": None if evaluation is None else evaluation.to_dict(),
            "disposition": "ratified_through_gate" if binding_hash else "stop_direction_no_authority_needed",
        }
        record = self.ledger.append(self.DECISION_RECORD, payload)
        self._apply_decision_record(payload)
        return record.hash

    def close(self, case_id: str, *, actor: str, reason: str, outcome: CaseState = CaseState.LAPSED) -> str:
        """Close a case without a decision. Stopping needs no grant."""
        case = self._live_case(case_id)
        if outcome not in (CaseState.LAPSED, CaseState.KILLED):
            raise ContractError("close outcome must be lapsed or killed")
        record = self.ledger.append(self.CLOSE_RECORD, {
            "source": self.source, "case_id": case_id, "outcome": outcome.value,
            "actor": require_text("actor", actor), "reason": require_text("reason", reason),
        })
        case["state"] = outcome.value
        return record.hash

    # -- helpers ------------------------------------------------------------------------
    def _live_case(self, case_id: str) -> dict[str, Any]:
        case = self._cases.get(case_id)
        if case is None:
            raise ContractError("unknown genesis case")
        if CaseState(case["state"]) in _TERMINAL:
            raise ContractError(f"case is {case['state']}; open a new case for a new deficit")
        return case

    def _genome_for(self, case: Mapping[str, Any], candidate: Mapping[str, Any],
                    trial: Mapping[str, Any], part_id: str) -> CapabilityGenome:
        spec = self.board.spec(part_id)
        if spec is None or not self.board.resolved(part_id):
            raise ContractError("candidate part code is not registered in this process")
        slot = candidate["slot"]
        kind, role = slot.split(":", 1)
        observed = trial.get("consequence_classes", []) or ["internal_write"]
        max_class = max(observed, key=CONSEQUENCE_CLASSES.index)
        outputs = {"candidates": "CandidateProposal[]"} if kind == "proposer" else {"assessment": "Assessment"}
        return CapabilityGenome(
            name=f"egregore.{slot}",
            version=part_id[7:23],
            description=(f"{spec.implementation} {spec.version} for {slot}; retained by genesis case "
                         f"{case['case_id'][7:19]} against {case['deficit']['kind']}"),
            interface={"inputs": {"signals": "SignalEnvelope[]", "context": "object"}, "outputs": outputs},
            contracts=["evidence"],
            authority=AuthorityEnvelope(max_consequence_class=max_class, budget_ceiling_usd=0.0,
                                        requires_human=max_class in ("financial", "irreversible")),
            acceptance_tests=list(trial.get("record_hashes", [])),
            failure_modes=sorted(trial.get("failure_classes", {})) or ["none observed in shadow trial"],
            recovery_path=f"PartsBoard rollback of {slot} to {self.board.rollback_target(slot) or 'prior part'}",
        )

    def _whole_body(self, case, candidate, trial, verifier, part_id):
        ladder = case["ladder"]
        classes = trial.get("failure_classes", {})
        harmful = sum(n for klass, n in classes.items() if klass != "transient")
        cheaper_recorded = all(r in ladder for r in LADDER[:LADDER.index(candidate["rung"])])
        return self.whole_body.applicable(
            f"genesis:{case['case_id']}",
            {
                Loop.STRATEGIC: LoopEvidence(True, cheaper_recorded, "cheaper ladder rungs recorded"),
                Loop.AUTONOMY: LoopEvidence(trial.get("samples", 0) >= self.min_trial_samples,
                                            verifier.may_authorize_promotion,
                                            f"{trial.get('samples', 0)} shadow samples; verifier {verifier.level}"),
                Loop.CONTINUITY: LoopEvidence(True, self.board.resolved(part_id),
                                              "part code registered, so rollback and restart can resolve it"),
                Loop.REGENERATIVE: LoopEvidence(True, harmful == 0,
                                                f"{harmful} non-transient trial failures"),
                Loop.META_IMPROVEMENT: LoopEvidence(True, True, "deficit, ladder, trials and dossier ledgered"),
            },
            applicable={Loop.STRATEGIC, Loop.AUTONOMY, Loop.CONTINUITY, Loop.REGENERATIVE, Loop.META_IMPROVEMENT},
        )
