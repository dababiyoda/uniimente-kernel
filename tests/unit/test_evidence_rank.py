"""The Foundry must choose what it built, not what it described confidently.

`TechnologySpec.status` is a hand-written word bound to no proof, and it was the
Composer's primary selection key. On this repository that meant #31 Web servers
— written `executable`, evidence BLUEPRINT, nothing built — outranked
technologies that genuinely run. These tests hold the new ordering to evidence
and hold the old signal in place beside it rather than deleted.
"""
from __future__ import annotations

import ast
import os

import pytest

from foundry.arsenal import ARSENAL
from foundry.composition import CompositionRequest, FoundryComposer
from foundry.evidence_rank import (
    UNKNOWN,
    UNSUPPORTED,
    TechnologyEvidence,
    UnknownTechnology,
    evidence_for,
    evidence_table,
    selection_rank,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _ev(tid=1, status="partial", awarded=None, constrained=None, ceiling=None):
    return TechnologyEvidence(technology_id=tid, claimed_status=status,
                              awarded=awarded, constrained=constrained,
                              ceiling=ceiling)


# ------------------------------------------------------------------- strength
def test_a_weak_foundation_outranks_a_strong_claim_about_the_thing_itself():
    """#25's real shape: awarded EXERCISED, standing on a BLUEPRINT dependency.

    Selecting it to attach would be selecting something whose foundation is not
    there, however good its own evidence is, so the constrained rung governs.
    """
    standing_on_sand = _ev(awarded="EXERCISED", constrained="BLUEPRINT")
    solid = _ev(awarded="BUILT", constrained="BUILT")
    assert standing_on_sand.strength < solid.strength
    assert selection_rank(solid) < selection_rank(standing_on_sand)


def test_awarded_is_used_when_nothing_constrains_it():
    assert _ev(awarded="PROVEN").strength > _ev(awarded="BUILT").strength


def test_the_absence_of_a_rung_sorts_below_every_rung():
    assert _ev(awarded=None).strength == UNSUPPORTED
    assert _ev(awarded=None).strength < _ev(awarded="BLUEPRINT").strength


def test_an_unknown_technology_is_never_assumed_sound():
    unknown = evidence_for(999, {}, "executable")
    assert isinstance(unknown, UnknownTechnology)
    assert unknown.strength == UNKNOWN
    assert unknown.strength < UNSUPPORTED, "unknown must not outrank unsupported"
    assert "unverifiable" in unknown.disagreement


# --------------------------------------------------------------- disagreement
def test_executable_with_nothing_built_is_reported_as_an_over_claim():
    over = _ev(status="executable", awarded="BLUEPRINT", constrained="BLUEPRINT")
    assert "claims it runs" in over.disagreement


def test_target_that_already_runs_is_reported_as_an_under_claim():
    under = _ev(status="target", awarded="EXERCISED", constrained="EXERCISED")
    assert "already runs" in under.disagreement


@pytest.mark.parametrize("status,rung", [
    ("executable", "EXERCISED"), ("partial", "BUILT"), ("target", "BLUEPRINT"),
])
def test_agreement_produces_no_note(status, rung):
    assert _ev(status=status, awarded=rung, constrained=rung).disagreement is None


def test_the_real_arsenal_disagreements_are_surfaced_not_swallowed():
    table = evidence_table()
    assert len(table) == 55
    flagged = [e for e in table.values() if e.disagreement]
    assert flagged, "the known #31 over-claim must still be reported"
    assert any(e.technology_id == 31 for e in flagged), (
        "#31 is written executable with BLUEPRINT evidence and must be flagged"
    )


# ------------------------------------------------------- selection, for real
def test_selection_never_moves_to_weaker_evidence():
    """The property that matters, checked across every control surface.

    Not a pinned list of six: if the tree changes, the guarantee is still that
    the evidence key never picks something worse-evidenced than the status key.
    """
    from capabilities.genome import CONSEQUENCE_CLASSES
    from foundry.composition import _STATUS_RANK

    composer = FoundryComposer()
    table = evidence_table()

    def pick(surface, use_evidence):
        candidates = []
        for tid, spec in composer.arsenal.items():
            if surface not in spec.control_surfaces:
                continue
            try:
                closure = composer._dependency_closure(tid, set())
            except Exception:                       # noqa: BLE001 - infeasible
                continue
            base = (_STATUS_RANK[spec.status], len(closure),
                    CONSEQUENCE_CLASSES.index(spec.consequence_class), tid)
            score = ((selection_rank(evidence_for(tid, table, spec.status)),) + base
                     if use_evidence else base)
            candidates.append((score, tid))
        return sorted(candidates)[0][1] if candidates else None

    surfaces = sorted({s for spec in ARSENAL.values() for s in spec.control_surfaces})
    for surface in surfaces:
        old, new = pick(surface, False), pick(surface, True)
        if old == new:
            continue
        old_strength = evidence_for(old, table, ARSENAL[old].status).strength
        new_strength = evidence_for(new, table, ARSENAL[new].status).strength
        assert new_strength >= old_strength, (
            f"surface {surface!r} moved from #{old} ({old_strength}) to "
            f"#{new} ({new_strength}), which is weaker evidence"
        )


def test_a_technology_with_nothing_built_never_beats_one_that_is_built():
    """The true property. My first version of this test was too strong.

    It asserted #31 could never win any surface. It still wins `distribution`,
    and correctly: every one of the eight technologies covering that surface
    resolves to BLUEPRINT, so the choice is between designs and the preserved
    `status` tiebreak picks among equals. What must never happen is #31 beating
    something better evidenced — and a surface with nothing built must say so.
    """
    composer = FoundryComposer()
    table = evidence_table()
    weak = evidence_for(31, table, ARSENAL[31].status).strength
    for surface in sorted(set(ARSENAL[31].control_surfaces)):
        chosen = composer._best_for_surface(surface, set(), table)
        if chosen != 31:
            continue
        rivals = [evidence_for(tid, table, spec.status).strength
                  for tid, spec in ARSENAL.items()
                  if surface in spec.control_surfaces and tid != 31]
        assert all(r <= weak for r in rivals), (
            f"#31 won {surface!r} over a better-evidenced rival"
        )
        assert composer._unbuilt_surface_note(surface, 31, table), (
            f"{surface!r} is covered by an unbuilt technology and must say so"
        )


# ------------------------------------------------------------ the plan record
@pytest.fixture(scope="module")
def real_plan():
    return FoundryComposer().compose(CompositionRequest(
        market_failure="participants cannot prove an outcome to a payer",
        beneficiaries=("participants",),
        payer="payer",
        control_surfaces=("customer", "distribution"),
        desired_metrics=("clean_verified_outcome_count",),
        evidence_refs=("docs/BACKCAST_SBM_0_TO_1.md",),
        kill_conditions=("no verified outcome within one cycle",),
    ))


def test_the_plan_carries_both_signals_without_merging_them(real_plan):
    assert real_plan.implementation_status, "the written claim must survive"
    assert real_plan.evidence_rungs, "the resolved evidence must be recorded"
    assert set(real_plan.evidence_rungs) == set(real_plan.selected_technology_ids)


def test_a_disagreement_reaches_the_plan_rather_than_a_log(real_plan):
    for note in real_plan.evidence_disagreements:
        assert note in real_plan.notes, "a conflict must be visible in the notes too"


def test_evidence_ready_and_implementation_ready_are_different_questions():
    """Both must exist, because a plan can satisfy one and fail the other."""
    from foundry.composition import CompositionPlan

    assert hasattr(CompositionPlan, "implementation_ready")
    assert hasattr(CompositionPlan, "evidence_ready")
    src = CompositionPlan.implementation_ready.fget.__doc__ or ""
    assert "unchanged" in src.lower(), (
        "implementation_ready must keep its original meaning for its two readers"
    )


def test_evidence_ready_is_false_when_nothing_was_measured():
    from foundry.composition import CompositionPlan
    import dataclasses

    fields = {f.name for f in dataclasses.fields(CompositionPlan)}
    assert {"evidence_rungs", "evidence_disagreements"} <= fields


# ------------------------------------------------------------------ structure
def test_evidence_rank_imports_blueprint_lazily():
    """Regression guard: a module-level import here closes an import ring.

    `blueprint.critical_path` imports `foundry.arsenal`, which runs
    `foundry/__init__`, which imports `foundry.composition`, which imports this
    module. Hoisting the blueprint import to the top would deadlock the package.
    """
    path = os.path.join(ROOT, "foundry", "evidence_rank.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    for node in tree.body:                       # module level only
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""])
            for name in names:
                assert not name.startswith("blueprint"), (
                    f"blueprint imported at module level ({name}); the ring returns"
                )


def test_the_ranker_grants_nothing():
    import foundry.evidence_rank as module

    for name in ("authorize", "activate", "select", "attach", "execute", "grant"):
        assert not hasattr(module, name), f"the ranker grew {name}"
