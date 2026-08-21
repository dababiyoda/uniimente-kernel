"""Comparison + improvement proposal (WP-06, SPEC-WP06 3.4).

Pure functions over the sealed tree and the verifier-confirmed measurement
matrix — no spine access, no wall clock, fully deterministic (same inputs ->
byte-identical canonical content; ids/created_at are the only fresh fields).

``build_report`` ranks every branch of the tree:

- improvement per direction (decrease: (baseline - value) / baseline);
- ``below_threshold`` if improvement < threshold;
- the threshold-meeting entries are ranked by measured improvement
  descending (ties break to the lower branch id, for total determinism):
  rank 1 is ``best``, the rest are ``beaten``;
- unmeasured branches (killed pre-experiment) get ``not_measured`` with
  measured_value=baseline_value, improvement_ratio=0.0, ranked last.

No threshold-meeting branch -> no winner -> CycleError (fail closed).

``spec_map`` binds each tree branch_id to its sealed StrategyBranch draft;
the branch's generator-embedded ``variant_config`` (see
``kernel/evolution/audit_rules.parse_variant_config``) carries the variant
identity the measurement matrix is keyed by — the mechanical branch<->variant
binding, since the frozen WP-05 ExperimentSpec shape has no variant field.

``build_proposal`` turns the report into a pending ImprovementProposal; the
contract itself never self-ratifies (ADR-6).
"""
from __future__ import annotations

from ..contracts.evolution import (
    ComparisonEntry,
    ComparisonReport,
    ImprovementProposal,
    StrategyBranch,
    StrategyTree,
)
from .audit_rules import parse_variant_config
from .cycle import CycleError

RANKING_RULE = (
    "improvement per direction over the pre-registered baseline; "
    "below_threshold if improvement < threshold; threshold-meeting entries "
    "ranked by measured improvement descending (ties: lower branch id); "
    "best = rank 1 among threshold-meeting; beaten = measured, met threshold, "
    "not rank 1; unmeasured (killed pre-experiment) branches rank last"
)


def _improvement(direction: str, baseline: float, value: float) -> float:
    if direction == "decrease":
        return (baseline - value) / baseline
    return (value - baseline) / baseline


def build_report(
    loop_id: str,
    tree: StrategyTree,
    spec_map: dict[str, StrategyBranch],
    measured: dict[str, float],
    baseline_value: float,
    threshold: float,
    direction: str,
    *,
    metric_unit: str,
) -> ComparisonReport:
    """Build the deterministic ComparisonReport for one cycle.

    ``measured`` maps variant_id -> measured value (the verifier-confirmed
    matrix). Every tree branch must appear in ``spec_map``; every measured
    variant must bind to a tree branch — anything else is a CycleError.
    """
    if not isinstance(tree, StrategyTree):
        raise CycleError("build_report needs the sealed StrategyTree")
    if direction not in ("decrease", "increase"):
        raise CycleError(f"direction {direction!r} refused")
    baseline_value = float(baseline_value)
    if baseline_value == 0.0:
        raise CycleError("baseline is zero; improvement ratio undefined")
    if not tree.branch_ids:
        raise CycleError("the tree has no branches; nothing to compare")

    rows: list[dict] = []
    metric_id: str | None = None
    for branch_id in tree.branch_ids:
        branch = spec_map.get(branch_id)
        if not isinstance(branch, StrategyBranch):
            raise CycleError(f"branch {branch_id!r} missing from the branch map")
        config = parse_variant_config(branch)
        if config is None:
            raise CycleError(
                f"branch {branch_id!r} carries no parseable variant_config; "
                "fail closed"
            )
        variant_id = config["variant_id"]
        if metric_id is None:
            metric_id = branch.metric_id
        elif branch.metric_id != metric_id:
            raise CycleError("branches disagree on metric_id; ambiguity fails closed")
        if variant_id in measured:
            value = float(measured[variant_id])
            improvement = _improvement(direction, baseline_value, value)
            rows.append(
                {
                    "branch_id": branch_id,
                    "variant_id": variant_id,
                    "measured_value": value,
                    "improvement_ratio": improvement,
                    "measured": True,
                    "met": improvement >= threshold,
                }
            )
        else:
            rows.append(
                {
                    "branch_id": branch_id,
                    "variant_id": variant_id,
                    "measured_value": baseline_value,
                    "improvement_ratio": 0.0,
                    "measured": False,
                    "met": False,
                }
            )
    unknown = set(measured) - {row["variant_id"] for row in rows}
    if unknown:
        raise CycleError(
            f"measured variants {sorted(unknown)} do not bind to any tree branch; "
            "fail closed"
        )
    if not any(row["measured"] and row["met"] for row in rows):
        raise CycleError(
            "no measured branch met the threshold; a comparison without a "
            "winner is never sealed (fail closed)"
        )

    # Rank measured entries by improvement descending (ties: lower branch id);
    # unmeasured entries rank last, ordered by branch id for determinism.
    measured_rows = sorted(
        (row for row in rows if row["measured"]),
        key=lambda row: (-row["improvement_ratio"], row["branch_id"]),
    )
    unmeasured_rows = sorted(
        (row for row in rows if not row["measured"]), key=lambda row: row["branch_id"]
    )
    entries: list[ComparisonEntry] = []
    for rank, row in enumerate(measured_rows + unmeasured_rows, start=1):
        if not row["measured"]:
            disposition = "not_measured"
        elif not row["met"]:
            disposition = "below_threshold"
        elif rank == 1:
            disposition = "best"
        else:
            disposition = "beaten"
        entries.append(
            ComparisonEntry(
                branch_id=row["branch_id"],
                variant_id=row["variant_id"],
                measured_value=row["measured_value"],
                improvement_ratio=row["improvement_ratio"],
                rank=rank,
                disposition=disposition,
            )
        )
    winner_branch_id = entries[0].branch_id  # rank 1 is always threshold-meeting
    try:
        return ComparisonReport(
            loop_id=loop_id,
            tree_id=tree.id,
            metric_id=metric_id or "",
            metric_unit=metric_unit,
            baseline_value=baseline_value,
            ranking_rule=RANKING_RULE,
            entries=entries,
            winner_branch_id=winner_branch_id,
        )
    except ValueError as exc:
        raise CycleError(f"comparison report refused: {exc}") from exc


def build_proposal(
    report: ComparisonReport,
    loop_id: str,
    patch_summary: str,
) -> ImprovementProposal:
    """The sealed PENDING proposal recommending the report's winner.

    Ratification is a separate gated founder act (an InstitutionalEvent);
    this contract never self-ratifies.
    """
    if not isinstance(report, ComparisonReport):
        raise CycleError("build_proposal needs a sealed ComparisonReport")
    if report.loop_id != loop_id:
        raise CycleError("proposal loop_id must bind to the report's loop")
    try:
        return ImprovementProposal(
            report_id=report.id,
            loop_id=loop_id,
            recommended_branch_id=report.winner_branch_id,
            patch_summary=patch_summary,
            authority_class="C2",
        )
    except ValueError as exc:
        raise CycleError(f"improvement proposal refused: {exc}") from exc
