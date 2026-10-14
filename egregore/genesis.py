"""Capability Genesis Loop: verified deficit -> diagnosis -> discovery -> ladder-ordered
candidates -> shadow trial -> dossier -> human-ratified binding -> reusable genome.

Canonical UNIIMENTE morphogenesis in the INTENT-0030 sense: functional capability
formation in response to a *verified* discrepancy, with no digital cells, tissues or
developmental fields. Each stage reuses an existing kernel mechanism; the loop connects
them and owns only case state.

    DeficitDetector     reads recorded CognitionCycles and emits content-addressed
                        CapabilityDeficits. A deficit may carry the lineage of the goal
                        it blocks; that goal stays paused, never closed.
    diagnosis           before anyone proposes a replacement, the loop attributes the
                        deficit to the proposal, the evidence, a permission, the
                        infrastructure, the resources, policy, or the evaluator. A
                        Guardian vetoing bad proposals is working; it is not replaced.
    discovery           candidate leads are gathered cheapest rung first: retained
                        genomes, parts already described for the slot, the audited
                        open-source catalog, an optional search service, and the
                        existing commissioning path (ChangeProposal). Every lead keeps
                        source, license, compatibility and resource notes.
    ladder admission    a rung may hold a candidate only when every cheaper rung has a
                        recorded, evidence-bearing outcome. "searched_none" must cite a
                        discovery record of this case that found nothing for that rung.
                        A later rung may be preferred over a cheaper candidate through a
                        recorded, evidence-bearing exception: the ladder is a prior.
    PartsBoard          shadow trials and the eventual binding, each through the
                        Consequence Gate with a single-action grant. Part identity is
                        bound to the executable artifact digest.
    trial acceptance    attempts, successes and typed failure classes are counted apart.
                        Readiness needs successful evaluations on distinct cycles and
                        evidence against the deficit's target effect; failures stay
                        evidence and never count as success.
    dossier             the Capability Genesis contract fields, content-addressed.
    ratification        evolution.capsule verifier tiers: hypothesis-only tiers cannot
                        retain; where the target effect is not measured mechanically a
                        strong independent tier is required. Three successes show a
                        narrow mechanism restoring one function, never general model
                        superiority, and the dossier says so.
    stop                regress, kill and close stop the case's shadow execution through
                        the board's grant-free stop, resume the paused goal with the
                        outcome, and keep every record.
    GenomeRegistry      a retained part becomes a CapabilityGenome and the cheapest lead
                        for later deficits; goal runtimes unblock on genome registration.

Authority is unchanged. Observe, diagnose, discover, propose, aggregate, regress,
kill, close, resume and verify grant nothing and need no grant. Shadow and retain pass
the Gate exactly as any other PartsBoard change.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from capabilities.genome import (
    CONSEQUENCE_CLASSES,
    AuthorityEnvelope,
    CapabilityGenome,
    GenomeRegistry,
)
from closure.whole_body import Loop, LoopEvidence, WholeBodyClosureController
from evolution.capsule import RetainRegressKill, RetainRegressKillDecision, VerifierRecord

from .contracts import ChangeProposal, ContractError, canonical_copy, digest, require_hash, require_text
from .failures import classify_record
from .parts import ACTIVE, SHADOW, SLOT_PATTERN, PartsBoard
from .runtime import CognitionCycle, CycleStatus

# Resourcefulness ladder, in order, from docs/FOUNDER_EFFECT_COMPILER.md. A decision
# prior: later rungs may win on recorded evidence (see ``propose(..., exceptions=)``).
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
RUNG_OUTCOMES = ("candidate", "searched_none", "not_applicable", "skipped_with_reason")
_EVIDENCE_REQUIRED = ("searched_none", "not_applicable", "skipped_with_reason")

# Verifier tiers strong enough to retain when the target effect is not measured mechanically.
STRONG_VERIFIERS = ("formal_proof", "external_outcome", "cryptographic_receipt", "qualified_human_review")

DEFICIT_KINDS = (
    "component_failure",   # one proposer/evaluator keeps raising
    "budget_refusal",      # one component keeps exhausting the resource governor
    "refusal_streak",      # cycles end REFUSED: candidates exist, none survives
    "silence_streak",      # cycles end SILENT: nothing is proposed at all
    "veto_streak",         # one evaluator vetoes in cycle after cycle
)
# Deficits whose target effect a shadow trial can measure mechanically: the shadow
# produces output in cycles where the active part produced none.
_RESTORATION_KINDS = ("component_failure", "budget_refusal", "silence_streak")
RUNTIME_SCOPE = "runtime"

RESPONSIBLE = ("proposal", "evidence", "permission", "infrastructure", "resources", "policy",
               "evaluator", "component", "missing_slot", "unknown")

DEFAULT_CATALOG = Path(__file__).resolve().parent.parent / "docs" / "open-source" / "repositories-2026-09-30.json"


def _scope(value: str) -> str:
    value = require_text("scope", value)
    if value != RUNTIME_SCOPE and not SLOT_PATTERN.match(value):
        raise ContractError("scope must be a slot ('proposer:<role>'/'evaluator:<role>') or 'runtime'")
    return value


def _texts(name: str, values: Any) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple)):
        raise ContractError(f"{name} must be a list of text")
    return [require_text(f"{name}[]", v) for v in values]


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
            for role in {a.role for a in cycle.assessments if a.veto}:
                hit("veto_streak", f"evaluator:{role}", cycle.cycle_id)

        deficits = []
        for (kind, scope), cycle_ids in sorted(hits.items()):
            distinct = sorted(set(cycle_ids))
            if len(distinct) >= self.min_occurrences:
                deficits.append(CapabilityDeficit(kind=kind, scope=scope, evidence_cycle_ids=tuple(distinct),
                                                  observed=len(distinct), window=len(recent)))
        return deficits


def diagnose(deficit: CapabilityDeficit, cycles: Sequence[CognitionCycle],
             bound_slots: Mapping[str, Mapping[str, str | None]] | None = None) -> dict[str, Any]:
    """Attribute a deficit before proposing a replacement. Deterministic, recorded, a prior.

    A refusal can be legitimate: a Guardian vetoing under-evidenced or unacceptable
    proposals is doing its job. Replacing an evaluator is warranted only when its vetoes
    carry no objections while peer evaluators approve the same candidates.
    """
    cited = {c.cycle_id: c for c in cycles if c.cycle_id in deficit.evidence_cycle_ids}
    if not cited:
        raise ContractError("diagnosis needs the cycles the deficit cites")
    basis: dict[str, Any] = {"cycles": len(cited), "failure_classes": {}, "vetoes": 0,
                             "vetoes_with_objections": 0, "peer_approved_vetoed": 0,
                             "under_evidenced_candidates": 0, "candidates": 0}
    for cycle in cited.values():
        for failure in cycle.failures:
            if deficit.scope in (RUNTIME_SCOPE, failure.get("component")):
                klass = classify_record(failure)
                basis["failure_classes"][klass] = basis["failure_classes"].get(klass, 0) + 1
        basis["candidates"] += len(cycle.candidates)
        for candidate in cycle.candidates:
            if not candidate.evidence_refs or candidate.confidence < 0.5:
                basis["under_evidenced_candidates"] += 1
            by_role = {a.role: a for a in cycle.assessments if a.candidate_id == candidate.candidate_id}
            for veto in [a for a in by_role.values() if a.veto]:
                if deficit.kind == "veto_streak" and f"evaluator:{veto.role}" != deficit.scope:
                    continue
                basis["vetoes"] += 1
                if veto.objections:
                    basis["vetoes_with_objections"] += 1
                peers = [a for a in by_role.values() if not a.veto and a.score >= 0.5 and a.confidence >= 0.5]
                if not veto.objections and peers:
                    basis["peer_approved_vetoed"] += 1

    classes = basis["failure_classes"]
    responsible, legitimate = "unknown", False
    if deficit.kind in ("component_failure", "budget_refusal"):
        dominant = max(classes, key=classes.get) if classes else None
        responsible = {
            "transient": "infrastructure", "budget_exceeded": "resources", "capability_missing": "permission",
            "doctrinal_refusal": "policy", "executor_error": "component", None: "component",
        }[dominant]
        legitimate = responsible == "policy"
    elif deficit.kind == "silence_streak":
        bound = bound_slots or {}
        has_proposer = any(s.startswith("proposer:") and b.get(ACTIVE) for s, b in bound.items())
        responsible = "proposal" if has_proposer else "missing_slot"
    elif deficit.kind in ("refusal_streak", "veto_streak"):
        if classes.get("capability_missing"):
            responsible = "permission"
        elif basis["vetoes"] and basis["peer_approved_vetoed"] == basis["vetoes"]:
            responsible = "evaluator"
        elif basis["candidates"] and basis["under_evidenced_candidates"] == basis["candidates"]:
            responsible, legitimate = "evidence", True
        elif basis["vetoes_with_objections"]:
            responsible, legitimate = "proposal", True
        elif classes.get("transient"):
            responsible = "infrastructure"
    replace_slots: list[str] = []
    if responsible in ("component", "missing_slot") or (responsible == "proposal" and deficit.scope == RUNTIME_SCOPE):
        replace_slots = [deficit.scope] if deficit.scope != RUNTIME_SCOPE else ["proposer:*"]
    elif responsible == "evaluator":
        replace_slots = [deficit.scope] if deficit.scope != RUNTIME_SCOPE else ["evaluator:*"]
    return {
        "responsible": responsible,
        "legitimate_refusal": legitimate,
        "replacement_warranted": bool(replace_slots),
        "replace_slots": replace_slots,
        "basis": basis,
        "method": "deterministic attribution over cited cycles; a prior for the human, not a verdict",
    }


class CaseState(str, Enum):
    OPEN = "open"
    TRIALING = "trialing"
    READY = "ready_for_ratification"
    RETAINED = "retained"
    REGRESSED = "regressed"
    KILLED = "killed"
    LAPSED = "lapsed"


_TERMINAL = {CaseState.RETAINED, CaseState.REGRESSED, CaseState.KILLED, CaseState.LAPSED}


# -- discovery sources ---------------------------------------------------------------
class DiscoverySource:
    """Protocol: ``rungs`` names the ladder rungs this source covers; ``leads(slot, case)``
    returns lead dicts for one slot. Leads are evidence of a search, not candidates."""

    name = "source"
    rungs: tuple[str, ...] = ()

    def leads(self, slot: str, case: Mapping[str, Any]) -> list[dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError


class RetainedGenomeSource(DiscoverySource):
    name, rungs = "retained_genomes", ("existing_capability",)

    def __init__(self, genesis: "CapabilityGenesis"):
        self.genesis = genesis

    def leads(self, slot, case):
        rows = []
        for row in self.genesis.reuse_candidates(slot):
            rows.append({**row, "source": self.name, "license": "inherited from the part's provenance",
                         "compatibility": "same slot; already governed", "resources": "as retained",
                         "evidence": [f"genesis:retained:{row['part_id']}"]})
        for genome in self.genesis.genomes.matching(f"egregore.{slot}"):
            rows.append({"source": self.name, "rung": "existing_capability", "slot": slot,
                         "genome": f"{genome.name}@{genome.version}", "license": "see provenance",
                         "compatibility": f"envelope {genome.authority.max_consequence_class}",
                         "resources": f"budget ceiling {genome.authority.budget_ceiling_usd}",
                         "evidence": [f"genome:{genome.name}@{genome.version}"]})
        return rows


class BoardSpecsSource(DiscoverySource):
    name, rungs = "board_specs", ("reconfigure_compose",)

    def __init__(self, board: PartsBoard):
        self.board = board

    def leads(self, slot, case):
        active = self.board.bindings().get(slot, {}).get(ACTIVE)
        rows = []
        for spec in self.board.specs_for(slot):
            if spec.part_id == active:
                continue
            rows.append({"source": self.name, "rung": "reconfigure_compose", "slot": slot,
                         "part_id": spec.part_id, "resolved": self.board.resolved(spec.part_id),
                         "license": spec.notes or "see provenance", "compatibility": "described for this slot",
                         "resources": "unknown", "evidence": [f"part:{spec.part_id}"]})
        target = self.board.rollback_target(slot)
        if target:
            rows.append({"source": self.name, "rung": "reconfigure_compose", "slot": slot, "part_id": target,
                         "resolved": self.board.resolved(target), "license": "see provenance",
                         "compatibility": "previous active part", "resources": "as before",
                         "evidence": [f"rollback:{slot}:{target}"]})
        return rows


class OpenSourceCatalogSource(DiscoverySource):
    """The audited catalog in docs/open-source (license, stars, archived, pushed_at)."""

    name, rungs = "open_source_catalog", ("open_source",)

    def __init__(self, path: Path | str = DEFAULT_CATALOG, *, search: Any = None, query: str | None = None):
        self.path = Path(path)
        self.search = search      # optional object with .search(query) -> {"sources": [...]}
        self.query = query

    def leads(self, slot, case):
        rows = []
        if self.path.exists():
            data = json.loads(self.path.read_text())
            for entry in data.get("repositories", []):
                if entry.get("archived"):
                    continue
                rows.append({"source": self.name, "rung": "open_source", "slot": slot, "repo": entry["repo"],
                             "license": entry.get("license", "unknown"), "stars": entry.get("stars"),
                             "pushed_at": entry.get("pushed_at"),
                             "compatibility": "unknown; needs an adapter and a part registration",
                             "resources": "unknown; see repository",
                             "evidence": [f"catalog:{self.path.name}:{entry['repo']}"]})
        if self.search is not None and self.query:
            result = self.search.search(self.query)
            for src in result.get("sources", []):
                rows.append({"source": f"{self.name}:search", "rung": "open_source", "slot": slot,
                             "title": src.get("title"), "url": src.get("url"), "license": "unknown",
                             "compatibility": "unknown", "resources": "unknown",
                             "evidence": [f"search:{src.get('source_id', src.get('url'))}"]})
        return rows


class CommissionSource(DiscoverySource):
    """The existing commissioning path: a ChangeProposal awaiting external review."""

    name, rungs = "commission", ("small_utility", "coding_agent_team")

    def leads(self, slot, case):
        return [{"source": self.name, "rung": rung, "slot": slot,
                 "route": "CapabilityGenesis.commission(case_id, ChangeProposal) -> runtime.propose_change",
                 "license": "to be declared in the proposal", "compatibility": "built against the slot contract",
                 "resources": "coding effort; declared in the proposal",
                 "evidence": [f"route:commission:{rung}"]} for rung in self.rungs]


class CapabilityGenesis:
    """Governed formation cases for one standing-cognition PartsBoard."""

    DEFICIT_RECORD = "egregore.deficit_observed"
    DIAGNOSIS_RECORD = "egregore.genesis_diagnosis"
    DISCOVERY_RECORD = "egregore.genesis_discovery"
    CANDIDATES_RECORD = "egregore.genesis_candidates"
    COMMISSION_RECORD = "egregore.genesis_commissioned"
    TRIAL_RECORD = "egregore.genesis_trial"
    DECISION_RECORD = "egregore.genesis_decision"
    CLOSE_RECORD = "egregore.genesis_closed"
    MISSION_PAUSE_RECORD = "egregore.mission_paused_for_deficit"
    MISSION_RESUME_RECORD = "egregore.mission_resumed"
    OUTCOME_RECORD = "egregore.genesis_outcome"

    def __init__(self, *, ledger: Any, board: PartsBoard, genomes: GenomeRegistry | None = None,
                 min_trial_samples: int = 3, sources: Sequence[DiscoverySource] | None = None):
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
        self.sources: list[DiscoverySource] = list(sources) if sources is not None else [
            RetainedGenomeSource(self), BoardSpecsSource(board), OpenSourceCatalogSource(), CommissionSource(),
        ]
        self._cases: dict[str, dict[str, Any]] = {}
        self._retained: dict[str, list[str]] = {}  # slot -> part_ids retained by this loop
        self._hydrate()

    # -- persistence -----------------------------------------------------------
    def _hydrate(self) -> None:
        for record in getattr(self.ledger, "records", ()):
            payload = record.payload
            if payload.get("source") != self.source:
                continue
            try:
                kind = record.record_type
                if kind == self.DEFICIT_RECORD:
                    case_id = self._apply_observe(CapabilityDeficit.from_dict(payload["deficit"]))
                    if payload.get("mission"):
                        self._apply_mission(self._cases[case_id], payload["mission"])
                    self._cases[case_id]["metrics"]["ledger_records"] += 1
                    continue
                case = self._cases[payload["case_id"]]
                case["metrics"]["ledger_records"] += 1
                if kind == self.DIAGNOSIS_RECORD:
                    case["diagnosis"] = dict(payload["diagnosis"])
                elif kind == self.DISCOVERY_RECORD:
                    case["discovery"].append({"hash": record.hash, **canonical_copy(payload["discovery"])})
                    case["metrics"]["rungs_searched"] = len(
                        {r for d in case["discovery"] for r in d.get("rungs", {})})
                elif kind == self.CANDIDATES_RECORD:
                    case["ladder"] = dict(payload["ladder"])
                    case["exceptions"] = dict(payload.get("exceptions", {}))
                    case["candidates"] = {c["part_id"]: dict(c) for c in payload["candidates"]}
                    case["proposed_by"] = payload.get("proposed_by")
                    case["metrics"]["candidates_considered"] = len(case["candidates"])
                    case["metrics"]["reused_capability"] = any(
                        c["rung"] == LADDER[0] for c in case["candidates"].values())
                elif kind == self.COMMISSION_RECORD:
                    case["commissions"].append(payload["change_id"])
                elif kind == self.TRIAL_RECORD:
                    case["trials"][payload["part_id"]] = dict(payload["aggregate"])
                    self._advance_after_trial(case, payload["part_id"])
                elif kind == self.DECISION_RECORD:
                    self._apply_decision_record(payload)
                elif kind == self.CLOSE_RECORD:
                    if CaseState(case["state"]) not in _TERMINAL:
                        case["state"] = payload["outcome"]
                elif kind == self.MISSION_RESUME_RECORD:
                    for mission in case["missions"]:
                        if mission.get("goal_id") == payload.get("goal_id"):
                            mission["resumed_with"] = payload.get("outcome")
                elif kind == self.OUTCOME_RECORD:
                    case["outcome"] = canonical_copy(payload["outcome"])
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
                "state": CaseState.OPEN.value, "diagnosis": None, "discovery": [], "ladder": {},
                "exceptions": {}, "candidates": {}, "commissions": [], "trials": {},
                "proposed_by": None, "decision": None, "missions": [], "outcome": None,
                "metrics": {"ledger_records": 0, "rungs_searched": 0, "candidates_considered": 0,
                            "trial_attempts": 0, "trial_successes": 0, "cycles_to_ready": None,
                            "reused_capability": False},
            }
        else:
            case["recurrence"] += 1
        return case_id

    @staticmethod
    def _apply_mission(case: dict[str, Any], mission: Mapping[str, Any]) -> None:
        if not any(m.get("goal_id") == mission.get("goal_id") for m in case["missions"]):
            case["missions"].append(canonical_copy(dict(mission)))

    def _record(self, record_type: str, case: dict[str, Any], payload: dict[str, Any]):
        record = self.ledger.append(record_type, {"source": self.source, "case_id": case["case_id"], **payload})
        case["metrics"]["ledger_records"] += 1
        return record

    # -- views -------------------------------------------------------------------
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
        """Parts this loop already retained for ``slot``. The compounding path.

        Retained parts whose code is not registered in this process are reported as
        unresolved instead of being guessed.
        """
        return [{"part_id": part_id, "slot": slot, "rung": LADDER[0],
                 "resolved": self.board.resolved(part_id),
                 "rationale": "retained by an earlier genesis for this slot"}
                for part_id in self._retained.get(slot, [])]

    # -- stage 1: observe --------------------------------------------------------
    def observe(self, deficit: CapabilityDeficit, *, mission: Mapping[str, Any] | None = None) -> str:
        """Open a case or count a recurrence. Grants nothing.

        ``mission`` links the goal the deficit blocks (``goal_id``, ``objective``,
        optional ``parent_trigger_id``); the goal is paused, not closed, and resumes
        when the case ends.
        """
        if not isinstance(deficit, CapabilityDeficit):
            raise ContractError("observe requires a CapabilityDeficit")
        clean_mission = None
        if mission is not None:
            clean_mission = {"goal_id": require_text("mission.goal_id", mission["goal_id"]),
                             "objective": require_text("mission.objective", mission["objective"]),
                             "parent_trigger_id": mission.get("parent_trigger_id")}
        case_id = self._apply_observe(deficit)
        case = self._cases[case_id]
        self._record(self.DEFICIT_RECORD, case, {
            "deficit": deficit.to_dict(), "recurrence": case["recurrence"], "mission": clean_mission,
            "disposition": "observed_not_authorized",
        })
        if clean_mission is not None:
            self._apply_mission(case, clean_mission)
            self.ledger.append(self.MISSION_PAUSE_RECORD, {
                "source": self.source, "case_id": case_id, **clean_mission,
                "disposition": "goal_paused_not_closed; resumes when the case ends",
            })
        return case_id

    # -- stage 2: diagnose ----------------------------------------------------------
    def diagnose_case(self, case_id: str, cycles: Sequence[CognitionCycle]) -> dict[str, Any]:
        case = self._live_case(case_id)
        result = diagnose(CapabilityDeficit.from_dict(case["deficit"]), cycles, self.board.bindings())
        case["diagnosis"] = result
        self._record(self.DIAGNOSIS_RECORD, case, {"diagnosis": canonical_copy(result)})
        return canonical_copy(result)

    # -- stage 3: discover ------------------------------------------------------------
    def discover(self, case_id: str, slots: Sequence[str] | None = None) -> str:
        """Gather leads per rung from the configured sources. Records the search itself."""
        case = self._live_case(case_id)
        targets = [_scope(s) for s in slots] if slots else self._target_slots(case)
        rungs: dict[str, dict[str, Any]] = {}
        for src in self.sources:
            for rung in src.rungs:
                entry = rungs.setdefault(rung, {"consulted": [], "leads": []})
                entry["consulted"].append(src.name)
                for slot in targets:
                    for lead in src.leads(slot, case):
                        if lead.get("rung", rung) != rung:
                            continue  # a multi-rung source files each lead under its own rung
                        entry["leads"].append(canonical_copy(lead))
        discovery = {"slots": targets, "rungs": rungs, "sources": [s.name for s in self.sources]}
        record = self._record(self.DISCOVERY_RECORD, case, {"discovery": discovery})
        case["discovery"].append({"hash": record.hash, **discovery})
        case["metrics"]["rungs_searched"] = len({r for d in case["discovery"] for r in d.get("rungs", {})})
        return record.hash

    def _target_slots(self, case: Mapping[str, Any]) -> list[str]:
        scope = case["deficit"]["scope"]
        if scope != RUNTIME_SCOPE:
            return [scope]
        wanted = (case.get("diagnosis") or {}).get("replace_slots", [])
        kinds = {w.split(":", 1)[0] for w in wanted if w.endswith(":*")}
        slots = [s for s in self.board.bindings() if s.split(":", 1)[0] in kinds]
        return slots or [w for w in wanted if not w.endswith(":*")] or sorted(self.board.bindings())

    def commission(self, case_id: str, change: ChangeProposal) -> str:
        """Record a build request through the existing path (ChangeProposal, no self-apply)."""
        case = self._live_case(case_id)
        if not isinstance(change, ChangeProposal):
            raise ContractError("commission requires a ChangeProposal")
        record_hash = self.board.runtime().propose_change(change)
        case["commissions"].append(change.change_id)
        self._record(self.COMMISSION_RECORD, case, {"change_id": change.change_id, "record_hash": record_hash,
                                                    "disposition": "awaiting_external_review"})
        return record_hash

    # -- stage 4: candidates in ladder order ------------------------------------------
    def propose(self, case_id: str, *, ladder: Mapping[str, Any], candidates: Sequence[Mapping[str, Any]],
                proposed_by: str, exceptions: Mapping[str, Mapping[str, Any]] | None = None,
                override: Mapping[str, Any] | None = None) -> str:
        case = self._live_case(case_id)
        if case["diagnosis"] is None:
            raise ContractError("diagnose the case before proposing replacements")
        clean_ladder = self._clean_ladder(case, ladder)
        clean_exceptions = {}
        for rung, exc in (exceptions or {}).items():
            if rung not in LADDER:
                raise ContractError(f"unknown ladder rung {rung!r}")
            clean_exceptions[rung] = {"reason": require_text("exception.reason", exc["reason"]),
                                      "evidence": _texts("exception.evidence", exc.get("evidence", []))}
            if not clean_exceptions[rung]["evidence"]:
                raise ContractError(f"a ladder exception for {rung!r} needs evidence")
        clean_override = None
        if override is not None:
            clean_override = {"reason": require_text("override.reason", override["reason"]),
                              "evidence": _texts("override.evidence", override.get("evidence", []))}
            if not clean_override["evidence"]:
                raise ContractError("a diagnosis override needs evidence")

        clean_candidates: dict[str, dict[str, Any]] = {}
        for raw in candidates:
            part_id = require_hash("candidate part_id", raw["part_id"])
            slot = _scope(raw["slot"])
            if slot == RUNTIME_SCOPE:
                raise ContractError("a candidate must name a concrete slot")
            if case["deficit"]["scope"] != RUNTIME_SCOPE and slot != case["deficit"]["scope"]:
                raise ContractError("candidate slot does not match the deficit's scope")
            self._check_diagnosis_allows(case, slot, clean_override)
            rung = raw["rung"]
            if rung not in LADDER:
                raise ContractError(f"unknown ladder rung {rung!r}")
            if clean_ladder.get(rung, {}).get("outcome") != "candidate":
                raise ContractError(f"ladder must record {rung!r} as 'candidate'")
            self._check_admissible(rung, clean_ladder, clean_exceptions)
            spec = self.board.spec(part_id)
            if spec is None:
                raise ContractError("candidate part is not registered on the board")
            if spec.slot != slot:
                raise ContractError(f"part is registered for {spec.slot}, not {slot}")
            clean_candidates[part_id] = {"part_id": part_id, "slot": slot, "rung": rung,
                                         "rationale": require_text("rationale", raw.get("rationale", ""))}
        for rung, entry in clean_ladder.items():
            if (entry["outcome"] == "candidate" and rung != "escalate_or_abstain"
                    and not any(c["rung"] == rung for c in clean_candidates.values())):
                raise ContractError(f"ladder marks {rung!r} as 'candidate' but no candidate was supplied for it")
        if not clean_candidates and "escalate_or_abstain" not in clean_ladder:
            raise ContractError("no candidates: record 'escalate_or_abstain' or supply at least one")
        case["ladder"], case["exceptions"], case["candidates"] = clean_ladder, clean_exceptions, clean_candidates
        case["proposed_by"] = require_text("proposed_by", proposed_by)
        case["metrics"]["candidates_considered"] = len(clean_candidates)
        case["metrics"]["reused_capability"] = any(c["rung"] == LADDER[0] for c in clean_candidates.values())
        record = self._record(self.CANDIDATES_RECORD, case, {
            "ladder": clean_ladder, "exceptions": clean_exceptions, "override": clean_override,
            "candidates": sorted(clean_candidates.values(), key=lambda c: c["part_id"]),
            "proposed_by": case["proposed_by"], "disposition": "proposed_not_bound",
        })
        return record.hash

    def _clean_ladder(self, case: Mapping[str, Any], ladder: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        clean: dict[str, dict[str, Any]] = {}
        discoveries = {d["hash"]: d for d in case["discovery"]}
        for rung, raw in ladder.items():
            if rung not in LADDER:
                raise ContractError(f"unknown ladder rung {rung!r}")
            entry = {"outcome": raw} if isinstance(raw, str) else dict(raw)
            outcome = entry.get("outcome")
            if outcome not in RUNG_OUTCOMES:
                raise ContractError(f"rung outcome must be one of {RUNG_OUTCOMES}")
            evidence = _texts(f"ladder[{rung}].evidence", entry.get("evidence", []))
            if outcome in _EVIDENCE_REQUIRED and not evidence:
                raise ContractError(f"{rung!r}: '{outcome}' needs evidence (a discovery record hash or a source)")
            if outcome == "searched_none":
                cited = [discoveries[ref] for ref in evidence if ref in discoveries]
                if not cited:
                    raise ContractError(f"{rung!r}: 'searched_none' must cite a discovery record of this case")
                for found in cited:
                    if rung not in found.get("rungs", {}):
                        raise ContractError(f"the cited discovery did not search {rung!r}")
                    if found["rungs"][rung]["leads"]:
                        raise ContractError(f"discovery found leads for {rung!r}; record 'candidate', "
                                            "'skipped_with_reason' or 'not_applicable', not 'searched_none'")
            clean[rung] = {"outcome": outcome, "evidence": evidence}
        return clean

    @staticmethod
    def _check_admissible(rung: str, ladder: Mapping[str, Mapping[str, Any]],
                          exceptions: Mapping[str, Mapping[str, Any]]) -> None:
        cheaper = LADDER[:LADDER.index(rung)]
        missing = [r for r in cheaper if r not in ladder]
        if missing:
            raise ContractError(f"{rung!r} needs an outcome recorded for every cheaper rung; missing {missing}")
        if rung == "new_architecture":
            cheaper_candidates = [r for r in cheaper if ladder[r]["outcome"] == "candidate"]
            if cheaper_candidates and rung not in exceptions:
                raise ContractError("new_architecture needs a recorded, evidence-bearing exception when a "
                                    f"cheaper rung holds a candidate ({cheaper_candidates})")

    @staticmethod
    def _check_diagnosis_allows(case: Mapping[str, Any], slot: str, override: Mapping[str, Any] | None) -> None:
        if override is not None:
            return
        diag = case["diagnosis"]
        if not diag["replacement_warranted"]:
            raise ContractError(f"diagnosis attributes the deficit to {diag['responsible']!r}; replacement is not "
                                "warranted (supply override={'reason','evidence'} to proceed anyway)")
        kind = slot.split(":", 1)[0]
        if not any(w == slot or w == f"{kind}:*" for w in diag["replace_slots"]):
            raise ContractError(f"diagnosis warrants replacing {diag['replace_slots']}, not {slot}; "
                                "a legitimate refusal is not a broken evaluator")

    # -- stage 5: shadow trial -------------------------------------------------------------
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
        """Aggregate PartsBoard shadow results for one candidate.

        Attempts, successes and typed failures are counted apart; a failed attempt is
        evidence and never a success.
        """
        case = self._live_case(case_id)
        candidate = case["candidates"].get(part_id)
        if candidate is None:
            raise ContractError("part is not a candidate of this case")
        prev = case["trials"].get(part_id, {})
        seen = set(prev.get("record_hashes", []))
        agg = {
            "attempts": prev.get("attempts", 0), "successes": prev.get("successes", 0),
            "failures": prev.get("failures", 0), "failure_classes": dict(prev.get("failure_classes", {})),
            "success_cycles": sorted(prev.get("success_cycles", [])),
            "restorations": prev.get("restorations", 0),
            "identical": prev.get("identical", 0),
            "assessments": prev.get("assessments", 0), "veto_agreements": prev.get("veto_agreements", 0),
            "consequence_classes": sorted(prev.get("consequence_classes", [])),
            "record_hashes": sorted(seen),
        }
        success_cycles = set(agg["success_cycles"])
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
            agg["attempts"] += 1
            if payload.get("failure"):
                agg["failures"] += 1
                klass = classify_record(payload["failure"])
                agg["failure_classes"][klass] = agg["failure_classes"].get(klass, 0) + 1
                continue
            comparison = payload.get("comparison", {})
            produced = False
            if "identical" in comparison:  # proposer slot
                shadow_candidates = comparison.get("shadow_candidates", [])
                produced = bool(shadow_candidates)
                agg["identical"] += 1 if comparison["identical"] else 0
                if produced and not comparison.get("active_candidate_ids"):
                    agg["restorations"] += 1
                for shadow_candidate in shadow_candidates:
                    klass = shadow_candidate.get("consequence_class")
                    if klass not in CONSEQUENCE_CLASSES:
                        raise ContractError("shadow candidate carries an unknown consequence class")
                    classes.add(klass)
            rows = comparison.get("assessments", [])
            if rows:  # evaluator slot
                produced = True
                agg["assessments"] += len(rows)
                agg["veto_agreements"] += sum(1 for row in rows if row.get("veto_agrees"))
                if any(row.get("active") is None for row in rows):
                    agg["restorations"] += 1
            if produced:
                agg["successes"] += 1
                success_cycles.add(payload["cycle_id"])
        agg["success_cycles"] = sorted(success_cycles)
        agg["consequence_classes"] = sorted(classes)
        agg["record_hashes"] = sorted(seen)
        agg["target_evidence"] = self._target_evidence(case, agg)
        case["trials"][part_id] = agg
        case["metrics"]["trial_attempts"] = sum(t["attempts"] for t in case["trials"].values())
        case["metrics"]["trial_successes"] = sum(t["successes"] for t in case["trials"].values())
        self._advance_after_trial(case, part_id)
        self._record(self.TRIAL_RECORD, case, {"part_id": part_id, "aggregate": canonical_copy(agg),
                                               "disposition": "no_influence"})
        return canonical_copy(agg)

    def _target_evidence(self, case: Mapping[str, Any], agg: Mapping[str, Any]) -> dict[str, Any]:
        kind = case["deficit"]["kind"]
        if kind in _RESTORATION_KINDS:
            met = agg["restorations"] >= self.min_trial_samples
            return {"kind": kind, "mechanical": True, "met": met,
                    "measure": f"{agg['restorations']} shadow outputs in cycles where the active part produced none "
                               f"(need {self.min_trial_samples})"}
        return {"kind": kind, "mechanical": False, "met": False,
                "measure": "shadow trials cannot measure acceptance of proposals; retain requires a strong "
                           f"independent verifier tier ({', '.join(STRONG_VERIFIERS)})"}

    def _ready(self, agg: Mapping[str, Any]) -> bool:
        # Distinct successful cycles subsume the success count (one success per cycle at most).
        target = agg.get("target_evidence", {})
        return (len(agg.get("success_cycles", [])) >= self.min_trial_samples
                and (bool(target.get("met")) or not target.get("mechanical", True)))

    def _advance_after_trial(self, case: dict[str, Any], part_id: str) -> None:
        if CaseState(case["state"]) in _TERMINAL:
            return
        agg = case["trials"].get(part_id, {})
        if self._ready(agg):
            case["state"] = CaseState.READY.value
            case["metrics"]["cycles_to_ready"] = len(agg.get("success_cycles", []))
        else:
            case["state"] = CaseState.TRIALING.value

    # -- stage 6: dossier ------------------------------------------------------------------
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
            "missions": case["missions"],
            "diagnosis": case["diagnosis"],
            "target_effect": f"{case['deficit']['kind']} in {case['deficit']['scope']} stops recurring "
                             f"with {slot} served by {part_id}",
            "acceptance": {
                "min_successful_distinct_evaluations": self.min_trial_samples,
                "target_evidence": trial.get("target_evidence"),
                "no_doctrinal_refusal": True,
                "verifier": "may_authorize_promotion; strong tier when target evidence is not mechanical",
                "scope": "narrow mechanism: shadow successes against this one deficit; "
                         "not evidence of general model superiority",
            },
            "discovery": [d["hash"] for d in case["discovery"]],
            "ladder": case["ladder"],
            "ladder_exceptions": case["exceptions"],
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
                "detach": "PartsBoard.change(part_id=None) under a Gate grant; shadows stop without a grant",
                "rollback_target": self.board.rollback_target(slot),
            },
            "lifecycle_state": case["state"],
            "metrics": case["metrics"],
            "owner": "alfonso_lopez",
            "review_and_kill": ["kill on any doctrinal_refusal in trial",
                                "regress when the active part still wins on the recorded comparisons",
                                f"lapse when the deficit stops recurring for {self.min_trial_samples} windows"],
        }
        body["dossier_hash"] = digest({"kind": "egregore-dossier", **body})
        return body

    # -- stage 7: ratify -----------------------------------------------------------------------
    def ratify(self, case_id: str, part_id: str, *, decision: str, reason: str, verifier: VerifierRecord,
               reviewed_dossier_hash: str, actor: str, gate: Any = None,
               grant: Mapping[str, Any] | None = None) -> str:
        """Record retain/regress/kill. Retain binds through the Gate; regress/kill stop shadows."""
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

        binding_hash = genome_key = evaluation = None
        if decision == RetainRegressKill.RETAIN:
            trial = case["trials"].get(part_id, {})
            if not self._ready(trial):
                raise ContractError(f"retain needs at least {self.min_trial_samples} successful evaluations on "
                                    "distinct cycles and the deficit's target evidence; attempts and failures "
                                    "do not count")
            if trial.get("failure_classes", {}).get("doctrinal_refusal"):
                raise ContractError("retain refused: the candidate met a doctrinal refusal in trial")
            if not trial["target_evidence"]["mechanical"] and verifier.level not in STRONG_VERIFIERS:
                raise ContractError("retain refused: the target effect was not measured mechanically, so a "
                                    f"strong independent verifier is required ({', '.join(STRONG_VERIFIERS)})")
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
        case["metrics"]["ledger_records"] += 1
        self._apply_decision_record(payload)
        if decision != RetainRegressKill.RETAIN:
            self._stop_shadows(case, actor, f"{decision}: {rrk.reason}")
        self._resume_missions(case, outcome=decision, genome=genome_key)
        return record.hash

    def close(self, case_id: str, *, actor: str, reason: str, outcome: CaseState = CaseState.LAPSED) -> str:
        """Close a case without a decision. Stops its shadows; needs no grant."""
        case = self._live_case(case_id)
        if outcome not in (CaseState.LAPSED, CaseState.KILLED):
            raise ContractError("close outcome must be lapsed or killed")
        record = self._record(self.CLOSE_RECORD, case, {
            "outcome": outcome.value, "actor": require_text("actor", actor), "reason": require_text("reason", reason),
        })
        case["state"] = outcome.value
        self._stop_shadows(case, actor, f"{outcome.value}: {reason}")
        self._resume_missions(case, outcome=outcome.value, genome=None)
        return record.hash

    def _stop_shadows(self, case: dict[str, Any], actor: str, reason: str) -> list[str]:
        """Stop every shadow this case started. Active parts and safeguards are untouched."""
        stopped = []
        bindings = self.board.bindings()
        for part_id, candidate in case["candidates"].items():
            slot = candidate["slot"]
            if bindings.get(slot, {}).get(SHADOW) == part_id:
                record_hash = self.board.stop_shadow(slot, actor=actor, reason=reason)
                if record_hash:
                    stopped.append(record_hash)
        return stopped

    def _resume_missions(self, case: dict[str, Any], *, outcome: str, genome: str | None) -> None:
        for mission in case["missions"]:
            if mission.get("resumed_with"):
                continue
            mission["resumed_with"] = outcome
            self.ledger.append(self.MISSION_RESUME_RECORD, {
                "source": self.source, "case_id": case["case_id"], "goal_id": mission["goal_id"],
                "objective": mission["objective"], "parent_trigger_id": mission.get("parent_trigger_id"),
                "outcome": outcome, "genome": genome,
                "disposition": "goal_resumes; capability discoverable via genome registry when retained",
            })

    # -- stage 8: verify the outcome against reality --------------------------------------------
    def verify_outcome(self, case_id: str, cycles_after: Sequence[CognitionCycle],
                       detector: DeficitDetector | None = None) -> dict[str, Any]:
        """Re-scan cycles recorded after the decision for the same deficit.

        This is internal verification by re-observation (the deficit no longer recurs);
        it is not external verification and is labelled as such.
        """
        case = self._cases.get(case_id)
        if case is None:
            raise ContractError("unknown genesis case")
        if CaseState(case["state"]) not in _TERMINAL:
            raise ContractError("verify_outcome needs a decided case")
        detector = detector or DeficitDetector()
        deficit = case["deficit"]
        recurred = [d for d in detector.scan(cycles_after)
                    if d.kind == deficit["kind"] and d.scope == deficit["scope"]]
        outcome = {
            "state": case["state"], "cycles_checked": len(cycles_after), "recurred": bool(recurred),
            "verification": "internal re-observation; not externally verified",
            "evidence_cycle_ids": [c.cycle_id for c in cycles_after],
        }
        case["outcome"] = outcome
        self._record(self.OUTCOME_RECORD, case, {"outcome": canonical_copy(outcome)})
        return canonical_copy(outcome)

    # -- helpers -------------------------------------------------------------------------------------
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
                         f"{case['case_id'][7:19]} against {case['deficit']['kind']}; "
                         f"artifact {spec.artifact_digest}"),
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
        cheaper_recorded = all(r in ladder for r in LADDER[:LADDER.index(candidate["rung"])])
        classes = trial.get("failure_classes", {})
        harmful = sum(n for klass, n in classes.items() if klass != "transient")
        target = trial.get("target_evidence", {})
        return self.whole_body.applicable(
            f"genesis:{case['case_id']}",
            {
                Loop.STRATEGIC: LoopEvidence(True, cheaper_recorded and case["diagnosis"] is not None,
                                             "diagnosis recorded; cheaper ladder rungs recorded with evidence"),
                Loop.AUTONOMY: LoopEvidence(trial.get("successes", 0) >= self.min_trial_samples,
                                            verifier.may_authorize_promotion,
                                            f"{trial.get('successes', 0)} successful shadow evaluations; "
                                            f"verifier {verifier.level}"),
                Loop.EXECUTION: LoopEvidence(trial.get("attempts", 0) > 0,
                                             bool(target.get("met")) or verifier.level in STRONG_VERIFIERS,
                                             target.get("measure", "no trial")),
                Loop.CONTINUITY: LoopEvidence(True, self.board.resolved(part_id),
                                              "part code registered, so rollback and restart can resolve it"),
                Loop.REGENERATIVE: LoopEvidence(True, harmful == 0, f"{harmful} non-transient trial failures"),
                Loop.META_IMPROVEMENT: LoopEvidence(True, True, "deficit, diagnosis, discovery, ladder, trials and "
                                                                "dossier ledgered"),
            },
            applicable={Loop.STRATEGIC, Loop.AUTONOMY, Loop.EXECUTION, Loop.CONTINUITY, Loop.REGENERATIVE,
                        Loop.META_IMPROVEMENT},
        )
