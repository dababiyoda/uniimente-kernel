"""Automated branch generation (WP-06, SPEC-WP06 3.2).

A ``BranchGenerator`` mechanically enumerates a declared ``MutationSpace``
into StrategyBranch DRAFTS — one per non-control variant — so no operator
hand-authors branch content (that was WP-05's manual mode). Title and
hypothesis come from deterministic templates naming the variant and its
axes; scores come from the pre-registered rubric the generator is
constructed with.

Hard Rule 4 (fail closed): a variant in the space without pre-registered
scores is a ``CycleError`` — no unscored branch is ever proposed. Malformed
rubrics, missing audit declarations, and invalid agent drafts are refused
the same way.

Injection point (SPEC-WP06 3.2 / ADR-4): ``generate(space,
agent_callable=...)`` — when provided, the callable receives the space and
returns ADDITIONAL drafts; each is validated (must be a StrategyBranch with
``tree_id=""`` carrying the full score rubric). The shipped default is no
callable; this is where a future LLM agent plugs in WITHOUT contract
changes.

The variant's audit declaration (``modifies`` / ``touches`` /
``new_dependencies`` / ``commit_strategy``) rides INSIDE the draft
hypothesis as a canonical-JSON ``variant_config`` block — the frozen WP-05
StrategyBranch shape is never edited, and the WP-06 audit rules parse the
block back out mechanically (``kernel/evolution/audit_rules.py``).
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from pydantic import model_validator

from ..contracts.base import KernelModel
from ..contracts.evolution import StrategyBranch
from ..crypto.hashing import canonical_json
from .cycle import CycleError

# The pre-registered score rubric every proposed branch must carry (the
# WP-05 selection rule reads exactly these four keys).
SCORE_KEYS = ("expected_value", "risk", "reversibility", "cost")

# The audit declaration every generated draft carries (SPEC-WP06 3.3).
DECLARATION_KEYS = ("modifies", "touches", "new_dependencies", "commit_strategy")

# Honest minimal declaration for a sandboxed, harness-local candidate: no
# production edits, no frozen-surface touches, no new dependencies, and
# commit-after-read transaction semantics. Used only when the generator is
# constructed without an explicit declarations map.
DEFAULT_DECLARATION: dict[str, Any] = {
    "modifies": [],
    "touches": [],
    "new_dependencies": [],
    "commit_strategy": "commit_after",
}

CONFIG_MARKER = "\nvariant_config="


class MutationSpace(KernelModel):
    """The declared space a BranchGenerator enumerates (SPEC-WP06 3.2).

    ``axes`` maps axis name -> declared variant values (>= 1 axis, >= 1 value
    each); ``control_variant`` is the baseline identity and MUST appear among
    the axis values — the generator emits one draft per NON-control variant.
    """

    objective: str
    metric_id: str
    axes: dict[str, list[str]]
    control_variant: str

    @model_validator(mode="after")
    def _axes_valid(self):
        if not self.axes:
            raise ValueError("a mutation space needs at least one axis")
        for axis, values in self.axes.items():
            if not isinstance(values, list) or not values:
                raise ValueError(f"axis {axis!r} needs at least one value")
            if any(not isinstance(v, str) or not v for v in values):
                raise ValueError(f"axis {axis!r} carries a blank variant value")
        flat = [v for values in self.axes.values() for v in values]
        if self.control_variant not in flat:
            raise ValueError(
                f"control_variant {self.control_variant!r} must appear among the "
                "axis values; ambiguity fails closed"
            )
        return self


class BranchGenerator:
    """Mechanical enumerator of a MutationSpace into StrategyBranch drafts.

    ``scoring`` maps variant_id -> the pre-registered rubric
    (``expected_value``, ``risk``, ``reversibility``, ``cost``) plus
    ``expected_delta``. ``declarations`` (optional) maps variant_id -> the
    honest audit declaration (``modifies``, ``touches``,
    ``new_dependencies``, ``commit_strategy``); when omitted, every variant
    carries DEFAULT_DECLARATION. Deterministic content; ids are uuid4.
    """

    def __init__(
        self,
        scoring: dict[str, dict[str, float]],
        *,
        declarations: dict[str, dict[str, Any]] | None = None,
    ):
        if not isinstance(scoring, dict) or not scoring:
            raise ValueError("the generator needs a non-empty scoring map (fail closed)")
        for variant, rubric in scoring.items():
            if not isinstance(rubric, dict):
                raise ValueError(f"scoring[{variant!r}] must be a rubric dict")
        self._scoring = {v: dict(r) for v, r in scoring.items()}
        self._declarations = (
            None
            if declarations is None
            else {v: dict(d) for v, d in declarations.items()}
        )

    # ------------------------------------------------------------ internals

    def _rubric(self, variant: str) -> dict[str, float]:
        rubric = self._scoring.get(variant)
        if rubric is None:
            raise CycleError(
                f"variant {variant!r} has no pre-registered scores; no unscored "
                "branch is ever proposed (fail closed)"
            )
        missing = (set(SCORE_KEYS) | {"expected_delta"}) - set(rubric)
        if missing:
            raise CycleError(
                f"scoring[{variant!r}] lacks rubric keys {sorted(missing)}; fail closed"
            )
        return rubric

    def _declaration(self, variant: str) -> dict[str, Any]:
        if self._declarations is None:
            return dict(DEFAULT_DECLARATION)
        declaration = self._declarations.get(variant)
        if declaration is None:
            raise CycleError(
                f"variant {variant!r} has no audit declaration; fail closed"
            )
        missing = set(DECLARATION_KEYS) - set(declaration)
        if missing:
            raise CycleError(
                f"declaration for {variant!r} lacks keys {sorted(missing)}; fail closed"
            )
        for key in ("modifies", "touches", "new_dependencies"):
            if not isinstance(declaration[key], list) or any(
                not isinstance(item, str) for item in declaration[key]
            ):
                raise CycleError(
                    f"declaration {key} for {variant!r} must be a list of strings"
                )
        if not isinstance(declaration["commit_strategy"], str):
            raise CycleError(
                f"declaration commit_strategy for {variant!r} must be a string"
            )
        return declaration

    @staticmethod
    def _variants_of(space: MutationSpace) -> list[tuple[str, dict[str, str]]]:
        """(variant, {axis: variant}) per non-control variant, deterministic
        order: axes sorted, values in declared order, first occurrence wins."""
        seen: dict[str, dict[str, str]] = {}
        for axis in sorted(space.axes):
            for value in space.axes[axis]:
                if value == space.control_variant or value in seen:
                    continue
                seen[value] = {
                    a: value for a, values in space.axes.items() if value in values
                }
        return list(seen.items())

    def _draft(self, space: MutationSpace, variant: str, axes_of: dict[str, str]) -> StrategyBranch:
        rubric = self._rubric(variant)
        declaration = self._declaration(variant)
        axes_text = ", ".join(f"{axis}={variant}" for axis in sorted(axes_of))
        config = {
            "variant_id": variant,
            "axes": axes_of,
            "modifies": list(declaration["modifies"]),
            "touches": list(declaration["touches"]),
            "new_dependencies": list(declaration["new_dependencies"]),
            "commit_strategy": declaration["commit_strategy"],
        }
        title = (
            f"Variant {variant} ({axes_text}) vs control {space.control_variant}"
        )
        hypothesis = (
            f"Objective: {space.objective}. Variant {variant} on axes "
            f"{axes_text} is expected to move {space.metric_id} by "
            f"{rubric['expected_delta']} relative to the "
            f"{space.control_variant} control."
            f"{CONFIG_MARKER}{canonical_json(config)}"
        )
        return StrategyBranch(
            title=title,
            hypothesis=hypothesis,
            metric_id=space.metric_id,
            expected_delta=float(rubric["expected_delta"]),
            scores={key: float(rubric[key]) for key in SCORE_KEYS},
        )

    # -------------------------------------------------------------- generate

    def generate(
        self,
        space: MutationSpace,
        agent_callable: Callable[[MutationSpace], Iterable[StrategyBranch]] | None = None,
    ) -> list[StrategyBranch]:
        """Enumerate ``space`` into drafts; optionally merge agent drafts.

        Every generated draft is validated against the pre-registered rubric
        and declaration maps (fail closed on any gap). When ``agent_callable``
        is provided it receives the space and returns ADDITIONAL drafts; each
        must be a StrategyBranch with ``tree_id=""`` carrying the full score
        rubric — anything else is a CycleError (fail closed).
        """
        if not isinstance(space, MutationSpace):
            raise CycleError("generate accepts a MutationSpace only")
        drafts = [
            self._draft(space, variant, axes_of)
            for variant, axes_of in self._variants_of(space)
        ]
        if agent_callable is not None:
            extra = agent_callable(space)
            if extra is None:
                raise CycleError("agent_callable returned None; fail closed")
            for draft in extra:
                if not isinstance(draft, StrategyBranch):
                    raise CycleError(
                        "agent drafts must be StrategyBranch instances; fail closed"
                    )
                if draft.tree_id != "":
                    raise CycleError(
                        "agent drafts must arrive with tree_id='' (drafts only)"
                    )
                missing = set(SCORE_KEYS) - set(draft.scores)
                if missing:
                    raise CycleError(
                        f"agent draft {draft.title!r} lacks score keys "
                        f"{sorted(missing)}; fail closed"
                    )
                drafts.append(draft)
        return drafts
