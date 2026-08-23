"""Dependency-aware technology composition for the Advantage Foundry.

A Composition Plan is a reversible design and evidence contract. It is not
an Advantage Genome and carries no execution authority. The Composer selects
the smallest feasible technology dependency closure, binds registered
Capability Genomes, emits attachment and detachment plans, and defines the
smallest bounded validation experiment.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from capabilities.genome import CapabilityGenome, CONSEQUENCE_CLASSES
from .arsenal import ARSENAL, TechnologySpec
from .evidence_rank import (
    BUILDABLE_FLOOR,
    disagreement_notes,
    evidence_for,
    evidence_table,
    rung_map,
    selection_rank,
)

ALLOWED_CONTROL_SURFACES = frozenset(
    surface for spec in ARSENAL.values() for surface in spec.control_surfaces
)
ALLOWED_METRICS = frozenset({
    "revenue", "contribution_margin", "conversion_rate", "time_to_payment",
    "retention_rate", "reliability", "customer_acquisition_cost",
    "founder_minutes", "error_rate", "dispute_rate", "evidence_quality",
    "authorized_completion_rate", "state_continuity", "security_incidents",
    "clean_verified_outcome_count", "time_to_validated_genome",
})
#: Preserved, and no longer the primary selection key. `status` is a written
#: claim; `evidence_rank.selection_rank` is what resolves against the tree. The
#: word is retained as a subordinate ranked term rather than deleted (FBO §9,
#: §12), so a tie on evidence still breaks toward the more confident design.
_STATUS_RANK = {"executable": 0, "partial": 1, "target": 2}
_LOWER_IS_BETTER = frozenset({
    "customer_acquisition_cost", "dispute_rate", "error_rate", "founder_minutes",
    "security_incidents", "time_to_payment", "time_to_validated_genome",
})


class CompositionRefused(ValueError):
    """The requested composition cannot be produced inside its bounds."""


@dataclass(frozen=True)
class CompositionRequest:
    market_failure: str
    beneficiaries: tuple[str, ...]
    payer: str
    control_surfaces: tuple[str, ...]
    desired_metrics: tuple[str, ...]
    legal_principal: str = "alfonso_lopez"
    max_budget_usd: float = 0.0
    reversible_required: bool = True
    requested_technology_ids: tuple[int, ...] = ()
    prohibited_technology_ids: tuple[int, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    kill_conditions: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.market_failure.strip():
            problems.append("market_failure is required")
        if not self.beneficiaries:
            problems.append("at least one beneficiary is required")
        if not self.payer.strip():
            problems.append("payer is required")
        unknown_surfaces = sorted(set(self.control_surfaces) - ALLOWED_CONTROL_SURFACES)
        if unknown_surfaces:
            problems.append(f"unknown control surfaces: {unknown_surfaces}")
        if not self.control_surfaces:
            problems.append("at least one control surface is required")
        unknown_metrics = sorted(set(self.desired_metrics) - ALLOWED_METRICS)
        if unknown_metrics:
            problems.append(f"unknown desired metrics: {unknown_metrics}")
        if not self.desired_metrics:
            problems.append("at least one desired metric is required")
        if self.legal_principal == "UNIIMENTE":
            problems.append("UNIIMENTE is never a legal principal")
        if self.max_budget_usd < 0:
            problems.append("max_budget_usd may not be negative")
        overlap = set(self.requested_technology_ids) & set(self.prohibited_technology_ids)
        if overlap:
            problems.append(f"technologies cannot be requested and prohibited: {sorted(overlap)}")
        bad_ids = sorted(
            technology_id
            for technology_id in set(self.requested_technology_ids + self.prohibited_technology_ids)
            if not 1 <= technology_id <= 55
        )
        if bad_ids:
            problems.append(f"technology ids must be within 1..55: {bad_ids}")
        if not self.kill_conditions:
            problems.append("at least one kill condition is required")
        if not self.evidence_refs:
            problems.append("composition requires source evidence references")
        return problems


@dataclass(frozen=True)
class AttachmentStep:
    order: int
    technology_id: int
    operation: str
    consequence_class: str
    requires_human: bool
    reversible: bool
    rollback: str
    acceptance_evidence: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceExperiment:
    hypothesis: str
    prediction: str
    metric: str
    baseline: float | None
    threshold: float
    direction: str
    budget_usd: float
    observation_window: str
    reversible: bool
    rollback: str
    success_next_decision: str
    failure_next_decision: str

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.metric not in ALLOWED_METRICS:
            problems.append(f"unsupported metric {self.metric!r}")
        if self.direction not in ("gte", "lte"):
            problems.append("direction must be gte or lte")
        if self.budget_usd < 0:
            problems.append("budget may not be negative")
        if not self.reversible:
            problems.append("Foundry v1 refuses irreversible validation experiments")
        if not all((self.hypothesis, self.prediction, self.observation_window, self.rollback)):
            problems.append("experiment fields may not be empty")
        return problems


@dataclass(frozen=True)
class CompositionPlan:
    plan_id: str
    request_hash: str
    market_failure: str
    control_surfaces: tuple[str, ...]
    selected_technology_ids: tuple[int, ...]
    selected_capability_genomes: tuple[str, ...]
    implementation_status: dict[int, str]
    consequence_class: str
    budget_ceiling_usd: float
    requires_human: bool
    attachment_plan: tuple[AttachmentStep, ...]
    detachment_plan: tuple[AttachmentStep, ...]
    experiment: EvidenceExperiment
    kill_conditions: tuple[str, ...]
    legal_principal: str
    created_at: str
    notes: tuple[str, ...] = ()
    #: What the evidence ladder awarded each selected technology, beside the
    #: `implementation_status` claim above. Two signals, never merged.
    evidence_rungs: dict[int, str] = field(default_factory=dict)
    #: Every place the written status and the resolved evidence conflict. Empty
    #: is a real answer; a populated tuple is not a warning to be skimmed.
    evidence_disagreements: tuple[str, ...] = ()
    schema_version: str = "1.0.0"

    def canonical_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("plan_id", None)
        return payload

    def verify_id(self) -> bool:
        return self.plan_id == plan_id_for(self.canonical_payload())

    @property
    def implementation_ready(self) -> bool:
        """Every selected technology *claims* to be executable.

        Deliberately unchanged. `closure/advantage_registry.py` and
        `omnimorph/engine.py` both read this, and quietly redefining a property
        two other modules depend on would be the silent weakening §12 forbids.
        It means what it always meant: the written status says executable.
        """
        return all(status == "executable" for status in self.implementation_status.values())

    @property
    def evidence_ready(self) -> bool:
        """Every selected technology has code a named test actually exercises.

        The evidence counterpart to `implementation_ready`. A plan can be
        implementation-ready and not evidence-ready — that is precisely the
        condition worth being able to see, and it is why both exist.
        """
        if not self.evidence_rungs:
            return False
        strengths = {"BLUEPRINT": 0, "SKETCHED": 1, "BUILT": 2,
                     "EXERCISED": 3, "PROVEN": 4, "HARDENED": 5}
        return all(strengths.get(rung, -1) >= BUILDABLE_FLOOR
                   for rung in self.evidence_rungs.values())


def request_hash(request: CompositionRequest) -> str:
    raw = json.dumps(asdict(request), sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def plan_id_for(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "plan:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class FoundryComposer:
    """Compile a market failure into a non-executing Composition Plan."""

    def __init__(
        self,
        *,
        arsenal: Mapping[int, TechnologySpec] | None = None,
        capability_genomes: Mapping[str, CapabilityGenome] | None = None,
        technology_capabilities: Mapping[int, tuple[str, ...]] | None = None,
    ) -> None:
        self.arsenal = dict(arsenal or ARSENAL)
        self.capability_genomes = dict(capability_genomes or {})
        self.technology_capabilities = {
            int(key): tuple(value) for key, value in (technology_capabilities or {}).items()
        }
        if set(self.arsenal) != set(range(1, 56)):
            raise CompositionRefused("arsenal must contain exactly technologies 1..55")
        for technology_id, spec in self.arsenal.items():
            problems = spec.validate()
            if technology_id != spec.id or problems:
                raise CompositionRefused(
                    f"invalid arsenal entry {technology_id}: id={spec.id}, problems={problems}"
                )

    def compose(
        self,
        request: CompositionRequest,
        *,
        experiment: EvidenceExperiment | None = None,
    ) -> CompositionPlan:
        problems = request.validate()
        if problems:
            raise CompositionRefused(f"invalid composition request: {problems}")

        prohibited = set(request.prohibited_technology_ids)
        selected = set(request.requested_technology_ids)
        if selected & prohibited:
            raise CompositionRefused("requested technologies include prohibited technologies")

        # One ladder read per composition. The table describes this repository;
        # a caller supplying a synthetic arsenal still gets the real evidence,
        # and any id the ladder does not cover is reported UNKNOWN rather than
        # assumed sound.
        evidence = evidence_table()
        unbuilt_surfaces: list[str] = []

        for surface in sorted(set(request.control_surfaces)):
            if any(surface in self.arsenal[technology_id].control_surfaces for technology_id in selected):
                continue
            covering = self._best_for_surface(surface, prohibited, evidence)
            selected.add(covering)
            unbuilt = self._unbuilt_surface_note(surface, covering, evidence)
            if unbuilt:
                unbuilt_surfaces.append(unbuilt)

        ordered_ids = self._topological_order(selected, prohibited)
        consequence_class = max(
            (self.arsenal[technology_id].consequence_class for technology_id in ordered_ids),
            key=CONSEQUENCE_CLASSES.index,
        )
        if request.reversible_required and consequence_class == "irreversible":
            raise CompositionRefused("Foundry v1 refuses irreversible compositions")

        bound_capabilities, capability_human = self._bind_capabilities(ordered_ids)
        requires_human = (
            CONSEQUENCE_CLASSES.index(consequence_class)
            >= CONSEQUENCE_CLASSES.index("financial")
            or capability_human
        )
        evidence_experiment = experiment or self._default_experiment(request)
        experiment_problems = evidence_experiment.validate()
        if experiment_problems:
            raise CompositionRefused(f"invalid evidence experiment: {experiment_problems}")
        if evidence_experiment.budget_usd > request.max_budget_usd:
            raise CompositionRefused(
                f"experiment budget ${evidence_experiment.budget_usd} exceeds request ceiling ${request.max_budget_usd}"
            )

        attachment_plan = tuple(
            self._attachment_step(order, technology_id, request)
            for order, technology_id in enumerate(ordered_ids, start=1)
        )
        detachment_plan = tuple(
            self._detachment_step(order, technology_id)
            for order, technology_id in enumerate(reversed(ordered_ids), start=1)
        )
        notes: list[str] = [
            "plan_only: no infrastructure or external effect has been created",
            "execution_requires_consequence_gate",
            "promotion_requires_external_outcome_evidence",
        ]
        for technology_id in ordered_ids:
            spec = self.arsenal[technology_id]
            if spec.status == "target":
                notes.append(f"deployment_blocker: technology {technology_id} ({spec.name}) is target architecture")
            elif spec.status == "partial":
                notes.append(f"implementation_gap: technology {technology_id} ({spec.name}) is partial")

        evidence_rungs = rung_map(ordered_ids, evidence)
        conflicts = disagreement_notes(ordered_ids, evidence, self.arsenal)
        notes.extend(conflicts)
        notes.extend(unbuilt_surfaces)

        draft = CompositionPlan(
            plan_id="",
            request_hash=request_hash(request),
            market_failure=request.market_failure,
            control_surfaces=tuple(sorted(set(request.control_surfaces))),
            selected_technology_ids=tuple(ordered_ids),
            selected_capability_genomes=tuple(bound_capabilities),
            implementation_status={technology_id: self.arsenal[technology_id].status for technology_id in ordered_ids},
            consequence_class=consequence_class,
            budget_ceiling_usd=request.max_budget_usd,
            requires_human=requires_human,
            attachment_plan=attachment_plan,
            detachment_plan=detachment_plan,
            experiment=evidence_experiment,
            kill_conditions=request.kill_conditions,
            legal_principal=request.legal_principal,
            created_at=utc_now(),
            notes=tuple(notes),
            evidence_rungs=evidence_rungs,
            evidence_disagreements=conflicts,
        )
        return replace(draft, plan_id=plan_id_for(draft.canonical_payload()))

    def _best_for_surface(self, surface: str, prohibited: set[int],
                          evidence: dict) -> int:
        """Choose the technology covering `surface`, on evidence before claim.

        The primary key is what resolves against the real tree; `status` is the
        second term, so a tie on evidence still breaks toward the more confident
        design. Before this seam existed the written word was primary, which on
        this repository would prefer #31 (written executable, evidence
        BLUEPRINT) over technologies that are genuinely built.
        """
        candidates: list[tuple[tuple[int, int, int, int, int], int]] = []
        for technology_id, spec in self.arsenal.items():
            if technology_id in prohibited or surface not in spec.control_surfaces:
                continue
            try:
                closure = self._dependency_closure(technology_id, prohibited)
            except CompositionRefused:
                continue
            score = (
                selection_rank(evidence_for(technology_id, evidence, spec.status)),
                _STATUS_RANK[spec.status], len(closure),
                CONSEQUENCE_CLASSES.index(spec.consequence_class), technology_id,
            )
            candidates.append((score, technology_id))
        if not candidates:
            raise CompositionRefused(f"no feasible technology covers control surface {surface!r}")
        return sorted(candidates)[0][1]

    def _unbuilt_surface_note(self, surface: str, technology_id: int,
                              evidence: dict) -> str | None:
        """Say so when the best available cover for a surface is not built.

        Discovered by a test that expected #31 never to win: on the
        `distribution` surface every one of the eight candidates resolves to
        BLUEPRINT, so the strongest choice is still a design. Selecting the best
        of several unbuilt options is correct behaviour and a plan that does not
        mention it reads as though the surface were covered.
        """
        best = evidence_for(technology_id, evidence,
                            self.arsenal[technology_id].status)
        if best.strength >= BUILDABLE_FLOOR:
            return None
        return (
            f"unbuilt_surface: control surface {surface!r} is covered by "
            f"technology {technology_id} ({self.arsenal[technology_id].name}), whose "
            f"evidence is {best.awarded or 'nothing'}; no technology covering this "
            "surface has code a named test exercises"
        )

    def _dependency_closure(self, root: int, prohibited: set[int]) -> set[int]:
        closure: set[int] = set()
        visiting: set[int] = set()

        def visit(technology_id: int) -> None:
            if technology_id in prohibited:
                raise CompositionRefused(
                    f"technology {technology_id} is prohibited but required as a dependency"
                )
            if technology_id not in self.arsenal:
                raise CompositionRefused(f"unknown technology dependency {technology_id}")
            if technology_id in visiting:
                raise CompositionRefused(f"technology dependency cycle at {technology_id}")
            if technology_id in closure:
                return
            visiting.add(technology_id)
            for dependency in self.arsenal[technology_id].dependencies:
                visit(dependency)
            visiting.remove(technology_id)
            closure.add(technology_id)

        visit(root)
        return closure

    def _topological_order(self, roots: set[int], prohibited: set[int]) -> list[int]:
        ordered: list[int] = []
        complete: set[int] = set()
        visiting: set[int] = set()

        def visit(technology_id: int) -> None:
            if technology_id in prohibited:
                raise CompositionRefused(
                    f"technology {technology_id} is prohibited but required by the composition"
                )
            if technology_id not in self.arsenal:
                raise CompositionRefused(f"unknown technology {technology_id}")
            if technology_id in visiting:
                raise CompositionRefused(f"technology dependency cycle at {technology_id}")
            if technology_id in complete:
                return
            visiting.add(technology_id)
            for dependency in sorted(self.arsenal[technology_id].dependencies):
                visit(dependency)
            visiting.remove(technology_id)
            complete.add(technology_id)
            ordered.append(technology_id)

        for root in sorted(roots):
            visit(root)
        return ordered

    def _bind_capabilities(self, ordered_ids: list[int]) -> tuple[list[str], bool]:
        selected: list[str] = []
        requires_human = False
        for technology_id in ordered_ids:
            spec = self.arsenal[technology_id]
            for key in self.technology_capabilities.get(technology_id, ()):
                genome = self.capability_genomes.get(key)
                if genome is None:
                    raise CompositionRefused(
                        f"technology {technology_id} references unregistered capability {key!r}"
                    )
                problems = genome.validate()
                if problems:
                    raise CompositionRefused(f"invalid capability genome {key!r}: {problems}")
                if CONSEQUENCE_CLASSES.index(spec.consequence_class) > CONSEQUENCE_CLASSES.index(
                    genome.authority.max_consequence_class
                ):
                    raise CompositionRefused(
                        f"capability {key!r} authority envelope does not cover technology {technology_id} consequence class {spec.consequence_class}"
                    )
                requires_human = requires_human or genome.authority.requires_human
                selected.append(key)
        return sorted(set(selected)), requires_human

    def _attachment_step(
        self, order: int, technology_id: int, request: CompositionRequest
    ) -> AttachmentStep:
        spec = self.arsenal[technology_id]
        bound = self.technology_capabilities.get(technology_id, ())
        bound_human = any(
            self.capability_genomes[key].authority.requires_human
            for key in bound if key in self.capability_genomes
        )
        requires_human = (
            CONSEQUENCE_CLASSES.index(spec.consequence_class)
            >= CONSEQUENCE_CLASSES.index("financial")
            or bound_human
        )
        return AttachmentStep(
            order=order,
            technology_id=technology_id,
            operation=f"attach:{self._slug(spec.name)}",
            consequence_class=spec.consequence_class,
            requires_human=requires_human,
            reversible=spec.consequence_class != "irreversible",
            rollback=f"detach technology {technology_id} and restore its prior snapshot",
            acceptance_evidence=(f"technology:{technology_id}:acceptance", *request.evidence_refs),
        )

    def _detachment_step(self, order: int, technology_id: int) -> AttachmentStep:
        spec = self.arsenal[technology_id]
        return AttachmentStep(
            order=order,
            technology_id=technology_id,
            operation=f"detach:{self._slug(spec.name)}",
            consequence_class="internal_write",
            requires_human=False,
            reversible=True,
            rollback=f"reattach technology {technology_id} from the verified prior version",
            acceptance_evidence=(f"technology:{technology_id}:detached",),
        )

    @staticmethod
    def _default_experiment(request: CompositionRequest) -> EvidenceExperiment:
        metric = request.desired_metrics[0]
        direction = "lte" if metric in _LOWER_IS_BETTER else "gte"
        return EvidenceExperiment(
            hypothesis=f"The composed advantage repairs: {request.market_failure}",
            prediction=f"The observed {metric} moves in the required {direction} direction",
            metric=metric,
            baseline=None,
            threshold=0.0,
            direction=direction,
            budget_usd=0.0,
            observation_window="one bounded validation cycle",
            reversible=True,
            rollback="detach all selected technologies in reverse dependency order",
            success_next_decision="submit external outcome evidence for retain review",
            failure_next_decision="regress or kill; preserve the negative evidence",
        )

    @staticmethod
    def _slug(value: str) -> str:
        return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())
