"""Deterministic Asymmetric Advantage Foundry Composer.

The Composer converts a validated market-failure request into a bounded,
reversible Advantage Genome. It selects the smallest feasible technology set,
resolves dependencies, binds available Capability Genomes, emits attach/detach
plans, and defines an evidence experiment.

It never deploys, spends, publishes, contacts external parties, or grants
itself authority. Every real effect remains behind the Consequence Gate.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from capabilities.genome import CapabilityGenome, CONSEQUENCE_CLASSES

from .arsenal import ARSENAL, TechnologySpec
from .genome import (
    AdvantageGenome,
    AdvantageRequest,
    AttachmentStep,
    EvidenceExperiment,
    genome_id_for,
    request_hash,
    utc_now,
)


_STATUS_RANK = {"executable": 0, "partial": 1, "target": 2}
_LOWER_IS_BETTER = frozenset({
    "customer_acquisition_cost",
    "dispute_rate",
    "error_rate",
    "founder_minutes",
    "security_incidents",
    "time_to_payment",
})


class FoundryRefused(ValueError):
    """A request could not be composed without violating Foundry bounds."""


class FoundryComposer:
    """Compile market failures into non-executable Advantage Genomes.

    ``capability_genomes`` is keyed by ``name@version``. The optional
    ``technology_capabilities`` map identifies which registered capability
    genomes implement each technology. Bindings are validated, but the
    Composer never instantiates them.
    """

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
            int(k): tuple(v) for k, v in (technology_capabilities or {}).items()
        }
        if set(self.arsenal) != set(range(1, 56)):
            raise FoundryRefused("arsenal must contain exactly technologies 1..55")
        for technology_id, spec in self.arsenal.items():
            problems = spec.validate()
            if technology_id != spec.id or problems:
                raise FoundryRefused(
                    f"invalid arsenal entry {technology_id}: id={spec.id}, problems={problems}"
                )

    def compose(
        self,
        request: AdvantageRequest,
        *,
        experiment: EvidenceExperiment | None = None,
    ) -> AdvantageGenome:
        problems = request.validate()
        if problems:
            raise FoundryRefused(f"invalid advantage request: {problems}")

        prohibited = set(request.prohibited_technology_ids)
        selected = set(request.requested_technology_ids)
        if selected & prohibited:
            raise FoundryRefused("requested technologies include prohibited technologies")

        for surface in sorted(set(request.control_surfaces)):
            if any(surface in self.arsenal[i].control_surfaces for i in selected):
                continue
            selected.add(self._best_for_surface(surface, prohibited))

        ordered_ids = self._topological_order(selected, prohibited)
        consequence_class = max(
            (self.arsenal[i].consequence_class for i in ordered_ids),
            key=CONSEQUENCE_CLASSES.index,
        )
        if request.reversible_required and consequence_class == "irreversible":
            raise FoundryRefused("Foundry v0 refuses irreversible compositions")

        bound_capabilities, capability_human = self._bind_capabilities(ordered_ids)
        requires_human = (
            CONSEQUENCE_CLASSES.index(consequence_class)
            >= CONSEQUENCE_CLASSES.index("financial")
            or capability_human
        )

        evidence_experiment = experiment or self._default_experiment(request)
        experiment_problems = evidence_experiment.validate()
        if experiment_problems:
            raise FoundryRefused(f"invalid evidence experiment: {experiment_problems}")
        if evidence_experiment.budget_usd > request.max_budget_usd:
            raise FoundryRefused(
                f"experiment budget ${evidence_experiment.budget_usd} exceeds request ceiling "
                f"${request.max_budget_usd}"
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
                notes.append(
                    f"deployment_blocker: technology {technology_id} ({spec.name}) is target architecture"
                )
            elif spec.status == "partial":
                notes.append(
                    f"implementation_gap: technology {technology_id} ({spec.name}) is partial"
                )

        created_at = utc_now()
        draft = AdvantageGenome(
            genome_id="",
            request_hash=request_hash(request),
            market_failure=request.market_failure,
            control_surfaces=tuple(sorted(set(request.control_surfaces))),
            selected_technology_ids=tuple(ordered_ids),
            selected_capability_genomes=tuple(bound_capabilities),
            implementation_status={i: self.arsenal[i].status for i in ordered_ids},
            consequence_class=consequence_class,
            budget_ceiling_usd=request.max_budget_usd,
            requires_human=requires_human,
            attachment_plan=attachment_plan,
            detachment_plan=detachment_plan,
            experiment=evidence_experiment,
            kill_conditions=request.kill_conditions,
            legal_principal=request.legal_principal,
            created_at=created_at,
            notes=tuple(notes),
        )
        return replace(draft, genome_id=genome_id_for(draft.canonical_payload()))

    def _best_for_surface(self, surface: str, prohibited: set[int]) -> int:
        candidates: list[tuple[tuple[int, int, int, int], int]] = []
        for technology_id, spec in self.arsenal.items():
            if technology_id in prohibited or surface not in spec.control_surfaces:
                continue
            try:
                closure = self._dependency_closure(technology_id, prohibited)
            except FoundryRefused:
                continue
            score = (
                _STATUS_RANK[spec.status],
                len(closure),
                CONSEQUENCE_CLASSES.index(spec.consequence_class),
                technology_id,
            )
            candidates.append((score, technology_id))
        if not candidates:
            raise FoundryRefused(
                f"no feasible technology covers control surface {surface!r}"
            )
        candidates.sort()
        return candidates[0][1]

    def _dependency_closure(self, root: int, prohibited: set[int]) -> set[int]:
        closure: set[int] = set()
        visiting: set[int] = set()

        def visit(technology_id: int) -> None:
            if technology_id in prohibited:
                raise FoundryRefused(
                    f"technology {technology_id} is prohibited but required as a dependency"
                )
            if technology_id not in self.arsenal:
                raise FoundryRefused(f"unknown technology dependency {technology_id}")
            if technology_id in visiting:
                raise FoundryRefused(f"technology dependency cycle at {technology_id}")
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
                raise FoundryRefused(
                    f"technology {technology_id} is prohibited but required by the composition"
                )
            if technology_id not in self.arsenal:
                raise FoundryRefused(f"unknown technology {technology_id}")
            if technology_id in visiting:
                raise FoundryRefused(f"technology dependency cycle at {technology_id}")
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
                    raise FoundryRefused(
                        f"technology {technology_id} references unregistered capability {key!r}"
                    )
                problems = genome.validate()
                if problems:
                    raise FoundryRefused(f"invalid capability genome {key!r}: {problems}")
                if CONSEQUENCE_CLASSES.index(spec.consequence_class) > CONSEQUENCE_CLASSES.index(
                    genome.authority.max_consequence_class
                ):
                    raise FoundryRefused(
                        f"capability {key!r} authority envelope does not cover technology "
                        f"{technology_id} consequence class {spec.consequence_class}"
                    )
                requires_human = requires_human or genome.authority.requires_human
                selected.append(key)
        return sorted(set(selected)), requires_human

    def _attachment_step(
        self, order: int, technology_id: int, request: AdvantageRequest
    ) -> AttachmentStep:
        spec = self.arsenal[technology_id]
        bound = self.technology_capabilities.get(technology_id, ())
        bound_human = any(
            self.capability_genomes[key].authority.requires_human
            for key in bound
            if key in self.capability_genomes
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
            acceptance_evidence=(
                f"technology:{technology_id}:acceptance",
                *request.evidence_refs,
            ),
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
    def _default_experiment(request: AdvantageRequest) -> EvidenceExperiment:
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


__all__ = ["FoundryComposer", "FoundryRefused"]
