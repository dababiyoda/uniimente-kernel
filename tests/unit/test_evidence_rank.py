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
    """The detector still reports every conflict between word and evidence.

    UPDATED 2026-08-22, and the reason is worth reading rather than skipping.
    This test used to name #31 as the standing example: written `executable`,
    evidence BLUEPRINT, nothing built. FOUNDER-RULING-2026-08-22 ruling 5 built
    the inert application half, so #31 now genuinely has code a named test
    exercises and correctly stops being an *evidence* over-claim.

    It has not stopped being an over-claim. `application/` is half a web server
    and cannot serve a request. What changed is the KIND of over-claim — from
    "no code" to "half the technology" — and `evidence_rank` cannot see the
    second, because it measures evidence strength and is blind to scope. That
    limitation is now recorded in the module and in #31's gaps rather than left
    to be rediscovered.

    So this asserts the mechanism, not one example of it: whatever disagrees
    must be reported, in both directions.
    """
    table = evidence_table()
    assert len(table) == 55
    flagged = [e for e in table.values() if e.disagreement]
    assert flagged, "the detector reports nothing at all; it has stopped working"

    # Both directions must be detectable, not only over-claims.
    over = [e for e in table.values()
            if e.claimed_status == "executable" and e.disagreement]
    under = [e for e in table.values()
             if e.claimed_status == "target" and e.disagreement]
    assert over or under, "no disagreement of either kind is being reported"


def test_evidence_rank_is_blind_to_scope_and_says_so():
    """The limitation #31 exposed, asserted so it cannot quietly disappear.

    A technology can be BUILT — real code, real tests — and still be a fraction
    of what its name claims. #31 is exactly that: the application half exists
    and the transport half is founder-gated, so "Web servers" is satisfied in
    evidence and not in scope. A reader who trusts the disagreement column alone
    would conclude the institution has a web server.
    """
    import foundry.evidence_rank as module

    assert "scope" in (module.__doc__ or "").lower(), (
        "the module must record that it measures evidence strength, not scope"
    )

    from blueprint.registry import BINDINGS
    gaps = " ".join(BINDINGS[31].gaps)
    assert "not a web server" in gaps.lower()


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
    and correctly: every technology covering that surface resolved to BLUEPRINT,
    so the choice was between designs and the preserved `status` tiebreak picks
    among equals.

    UPDATED 2026-08-22. The property is unchanged; the example moved. #31 is now
    BUILT, so the `unbuilt_surface` note is correctly absent for it — asserting
    the note here would demand a warning about something that is built. The
    invariant asserted instead applies to EVERY technology, which is what it
    always should have been: a winner must never be worse-evidenced than a
    rival, and any surface whose winner is unbuilt must say so.
    """
    composer = FoundryComposer()
    table = evidence_table()

    surfaces = sorted({s for spec in ARSENAL.values()
                       for s in spec.control_surfaces})
    checked = 0
    for surface in surfaces:
        try:
            chosen = composer._best_for_surface(surface, set(), table)
        except Exception:
            continue
        checked += 1
        winner = evidence_for(chosen, table, ARSENAL[chosen].status)
        rivals = [evidence_for(tid, table, spec.status).strength
                  for tid, spec in ARSENAL.items()
                  if surface in spec.control_surfaces and tid != chosen]
        assert all(r <= winner.strength for r in rivals), (
            f"#{chosen} won {surface!r} over a better-evidenced rival"
        )
        note = composer._unbuilt_surface_note(surface, chosen, table)
        if winner.buildable:
            assert note is None, (
                f"{surface!r} is covered by a built technology yet warns it is not"
            )
        else:
            assert note, (
                f"{surface!r} is covered by an unbuilt technology and must say so"
            )
    assert checked > 1, "the sweep covered no surfaces; it is asserting nothing"


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
