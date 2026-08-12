"""The ladder must refuse. Every test here is a refusal the blueprint has to make.

There is no test that the blueprint "works". A blueprint that awards rungs
generously works perfectly and is worthless. What has to hold is that it cannot
be talked into a rung it has no evidence for.
"""
from __future__ import annotations

import os

import pytest

from blueprint.critical_path import CycleError, compute, topological_order
from blueprint.evidence import (
    EvidenceError,
    EvidenceRef,
    declared_capability_ids,
    known_contracts,
    registered_closure_modules,
    resolve,
)
from blueprint.ladder import (
    RUNG_ORDER,
    EvidenceKind,
    Reality,
    Rung,
    highest_supported_rung,
    missing_for,
    required_evidence,
)
from blueprint.registry import (
    BINDINGS,
    Owner,
    TechnologyBinding,
    audit,
    require_honest,
    validate_binding,
)
from foundry.arsenal import ARSENAL


# --------------------------------------------------------------------- ladder
def test_rungs_are_cumulative_and_hardened_needs_an_external_outcome():
    for lower, higher in zip(RUNG_ORDER, RUNG_ORDER[1:]):
        assert required_evidence(lower) < required_evidence(higher), (
            f"{higher.value} must require strictly more than {lower.value}"
        )
    assert EvidenceKind.EXTERNAL_OUTCOME in required_evidence(Rung.HARDENED)
    assert EvidenceKind.EXTERNAL_OUTCOME not in required_evidence(Rung.PROVEN)


def test_eleven_of_twelve_is_eleven_of_twelve():
    """A rung is awarded on the full requirement set or not at all."""
    full = required_evidence(Rung.PROVEN)
    for dropped in full:
        partial = frozenset(full - {dropped})
        awarded = highest_supported_rung(partial)
        assert awarded is None or awarded is not Rung.PROVEN, (
            f"PROVEN was awarded while missing {dropped.value}"
        )


def test_no_technology_reaches_hardened_because_none_has_an_external_outcome():
    """The top rung is currently unreachable, and that is the honest state."""
    report = compute()
    hardened = [s.technology_id for s in report.statuses.values()
                if s.awarded_rung is Rung.HARDENED]
    assert hardened == [], (
        f"technologies {hardened} claim HARDENED, but the verified external "
        "outcome count is 0"
    )


# ------------------------------------------------------------------- evidence
def test_an_unresolvable_reference_is_refused():
    for ref, why in [
        (EvidenceRef(EvidenceKind.IMPLEMENTATION_PATH, "does/not/exist.py"), "missing file"),
        (EvidenceRef(EvidenceKind.TEST_NODE, "tests/unit/test_events.py::test_no_such_test"),
         "undefined test"),
        (EvidenceRef(EvidenceKind.CONTRACT_SCHEMA, "not-a-contract"), "absent schema"),
        (EvidenceRef(EvidenceKind.MANIFEST_CAPABILITY, "kernel.invented"), "undeclared capability"),
        (EvidenceRef(EvidenceKind.CLOSURE_MODULE, "not_registered"), "unregistered module"),
        (EvidenceRef(EvidenceKind.SPEC_DOCUMENT, "docs/ARCHITECTURE.md#no such anchor"),
         "absent anchor"),
    ]:
        assert not resolve(ref).ok, f"{why} resolved when it should not have"


def test_no_external_outcome_resolves_anywhere():
    """The one rung nothing can currently reach must actually be unreachable."""
    ref = EvidenceRef(EvidenceKind.EXTERNAL_OUTCOME, "docs/PHASE_ZERO_REPORT.md")
    resolution = resolve(ref)
    assert not resolution.ok
    assert "reconciled" in resolution.detail


def test_a_locator_may_not_escape_the_repository():
    with pytest.raises(EvidenceError):
        EvidenceRef(EvidenceKind.IMPLEMENTATION_PATH, "/etc/passwd")
    assert not resolve(
        EvidenceRef(EvidenceKind.IMPLEMENTATION_PATH, "../../../etc/passwd")
    ).ok


def test_an_empty_locator_is_refused():
    with pytest.raises(EvidenceError):
        EvidenceRef(EvidenceKind.IMPLEMENTATION_PATH, "   ")


def test_the_binder_reads_real_registries():
    assert "kernel.consequence_gate" in declared_capability_ids()
    assert "consequence_gate" in registered_closure_modules()
    assert "organ-manifest" in known_contracts()


# ------------------------------------------------------------------ registry
def test_over_claiming_a_rung_is_refused_and_named():
    """The failure mode this whole package exists to prevent."""
    liar = TechnologyBinding(
        technology_id=9,                 # Containers: a specification and nothing else
        claimed_rung=Rung.PROVEN,
        reality=Reality.IMPLEMENTED,
        evidence=(EvidenceRef(EvidenceKind.SPEC_DOCUMENT,
                              "docs/UNIIMENTE_FINAL_BUILD_ORDER.md"),),
        gaps=(),
        owner=Owner.CHATGPT,
    )
    result = validate_binding(liar)
    assert result.awarded_rung is Rung.BLUEPRINT, "the claim was not lowered to evidence"
    assert result.over_claimed
    assert any("claimed PROVEN but evidence supports only BLUEPRINT" in p
               for p in result.problems)
    for kind in ("IMPLEMENTATION_PATH", "TEST_NODE", "CLOSURE_MODULE",
                 "CONTRACT_SCHEMA", "MANIFEST_CAPABILITY"):
        assert any(kind in p for p in result.problems), f"{kind} not named as missing"


def test_claiming_nothing_is_permitted_and_is_not_a_violation():
    """Technology #14 has no specification anywhere. Silence is honest."""
    result = validate_binding(BINDINGS[14])
    assert BINDINGS[14].claimed_rung is None
    assert result.awarded_rung is None
    assert not result.over_claimed
    assert result.problems == ()


def test_every_committed_binding_is_honest():
    """The registry checked into this repository must not over-claim."""
    require_honest()


def test_bindings_cover_the_arsenal_exactly():
    assert set(BINDINGS) == set(ARSENAL)
    assert len(BINDINGS) == 55


def test_reality_is_independent_of_rung():
    """Neither axis may be derivable from the other, or one of them is decoration."""
    results = audit()
    pairs = {(a.awarded_rung, a.reality) for a in results}
    by_rung: dict = {}
    for rung, reality in pairs:
        by_rung.setdefault(rung, set()).add(reality)
    assert any(len(v) > 1 for v in by_rung.values()), (
        "every rung maps to exactly one reality; the axes are not independent"
    )


def test_missing_for_names_exactly_what_is_absent():
    have = frozenset({EvidenceKind.SPEC_DOCUMENT, EvidenceKind.IMPLEMENTATION_PATH})
    assert missing_for(Rung.BUILT, have) == frozenset({EvidenceKind.TEST_NODE})


# -------------------------------------------------------------- critical path
def test_the_dependency_graph_is_acyclic_and_covers_every_technology():
    order = topological_order()
    assert len(order) == 55
    seen: set[int] = set()
    for tech_id in order:
        for dep in ARSENAL[tech_id].dependencies:
            assert dep in seen, (
                f"#{tech_id} was ordered before its dependency #{dep}"
            )
        seen.add(tech_id)


def test_the_constrained_rung_never_exceeds_the_weakest_dependency():
    """A capability may not be read as stronger than the floor beneath it."""
    from blueprint.ladder import rung_index
    report = compute()
    for status in report.statuses.values():
        if status.constrained_rung is None:
            continue
        assert rung_index(status.constrained_rung) <= rung_index(status.ceiling), (
            f"#{status.technology_id} {status.name} is read at "
            f"{status.constrained_rung.value} above a ceiling of {status.ceiling.value}"
        )
        for dep in ARSENAL[status.technology_id].dependencies:
            dep_rung = report.statuses[dep].constrained_rung
            if dep_rung is None:
                continue
            assert rung_index(status.constrained_rung) <= rung_index(dep_rung), (
                f"#{status.technology_id} stands above its dependency #{dep}"
            )


def test_evidence_outrunning_its_foundation_is_reported_not_hidden():
    """When awarded > ceiling the report says so instead of averaging it away."""
    report = compute()
    for status in report.standing_above_foundation:
        assert status.awarded_rung is not None
        assert status.constrained_rung == status.ceiling
        assert status.constrained_rung != status.awarded_rung


def test_the_frontier_is_nonempty_and_every_member_can_actually_advance():
    report = compute()
    assert report.frontier, "nothing is unblocked; the institution cannot move"
    for status in report.frontier:
        assert status.can_advance
        assert status.awarded_rung is not Rung.HARDENED


def test_blocked_technologies_name_the_dependency_holding_them_down():
    report = compute()
    for status in report.blocked:
        assert status.blocked_by, "a blocked technology must name what blocks it"
        for dep in status.blocked_by:
            assert dep in ARSENAL


def test_the_report_grants_nothing():
    report = compute()
    assert not hasattr(report, "authorize")
    assert not hasattr(report, "activate")


def test_every_gap_is_a_sentence_not_a_word():
    """'Partial' is not a gap. A gap names what is absent and why it matters."""
    for tech_id, b in sorted(BINDINGS.items()):
        for gap in b.gaps:
            assert len(gap.split()) >= 6, (
                f"#{tech_id} gap is too vague to act on: {gap!r}"
            )


def test_owners_partition_the_work_and_chatgpts_scope_is_real():
    report = compute()
    owned = {o: report.owned_by(o) for o in Owner}
    assert sum(len(v) for v in owned.values()) == 55
    chatgpt_ids = {s.technology_id for s in owned[Owner.CHATGPT]}
    # The scope the founder assigned to ChatGPT must actually be owned by it.
    for tech_id in (9, 10, 11, 28):        # containment tiers and MCP
        assert tech_id in chatgpt_ids, f"#{tech_id} is not owned by CHATGPT"


def test_cli_runs_and_reports_without_authorizing():
    from blueprint.__main__ import main
    assert main([]) == 0
    assert main(["--json"]) == 0
