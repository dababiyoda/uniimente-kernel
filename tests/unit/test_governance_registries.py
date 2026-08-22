"""The register of registries must stay a map, not become a fifth copy.

Its whole value is that it points at where decisions live without restating
them. The tests that matter are the ones that stop it drifting into a rival
catalogue, and the one that stops a contributor's records going quietly missing.
"""
from __future__ import annotations

import ast
import os

import pytest

from governance.registries import (
    KNOWN_CONTESTED,
    KNOWN_REGISTRIES,
    Owner,
    Registry,
    contested_concerns,
    namespace_conflicts,
    render,
    unmerged,
    unreachable,
)

MODULE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "governance", "registries.py")


# ------------------------------------------------- pointers, never contents
def test_the_register_holds_pointers_not_content():
    """No decision text may live here. Checked against the AST, not by eye.

    The failure this forbids is the tempting one: copying KIMI's open questions
    into this file so `python -m governance.registries` prints a complete list.
    That would produce a fifth registry of the same decisions, which is the
    defect the module exists to report. A row may name a path, an owner and a
    concern; it may not carry a verdict, an option or an approval status.
    """
    with open(MODULE, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    forbidden = {"NEEDS_FOUNDER_DECISION", "approval_status", "authorized_by",
                 "do_nothing_option", "alternatives", "dissent", "RETAIN",
                 "REGRESS", "KILL"}
    found = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        for token in [node.value]
        if token in forbidden
    }
    assert not found, (
        f"decision content leaked into the register: {sorted(found)}. "
        "The register maps where records live; it does not restate them."
    )


def test_no_registry_row_carries_a_decision_verdict():
    """Structural echo of the AST guard, at the data level."""
    for registry in KNOWN_REGISTRIES:
        blob = " ".join([registry.canonical_for, registry.note]).lower()
        assert "needs_founder_decision" not in blob
        assert not blob.startswith("option ")


# ------------------------------------------- a registry cannot go missing
def test_an_unreachable_registry_is_reported_not_dropped(tmp_path):
    """Durable, committed and invisible is still invisible.

    KIMI's reconciliation names local-only artifacts as the trail-failure mode.
    This is the harder version: the artifact is committed and pushed, and every
    other contributor still cannot see it, because it sits on an unmerged
    branch. Silence here would reproduce exactly that.
    """
    missing = unreachable(KNOWN_REGISTRIES, str(tmp_path))
    assert len(missing) == len(KNOWN_REGISTRIES), (
        "against an empty tree every registry is unreachable"
    )
    text = render(str(tmp_path))
    for registry in KNOWN_REGISTRIES:
        assert registry.registry_id in text
        assert registry.ref in text


def test_kimis_catalogue_is_now_merged_and_readable():
    """The register's first real job, and the row it already caught going stale.

    KIMI's records lived on `kimi/collaboration-reconciliation-2026-08-22` and
    this branch could not see them. PR #82 merged them to main on 2026-08-21,
    and this test failed on the next run — the row still pinned the branch. That
    is the guard working: the instruction it carried was to update the row
    rather than relax the assertion, and that is what happened.
    """
    by_id = {r.registry_id: r for r in KNOWN_REGISTRIES}
    kimi = by_id["REG-COLLAB-KIMI"]
    assert kimi.owner is Owner.KIMI
    assert kimi.merged, "PR #82 landed these records on main"
    assert kimi not in unreachable(), (
        "after merging main this branch holds KIMI's records; if this fails "
        "again the branch has drifted behind main, not the row"
    )


def test_every_contributor_with_records_appears(): 
    """A register that lists only convenient contributors is worse than none."""
    owners = {r.owner for r in KNOWN_REGISTRIES}
    assert Owner.KIMI in owners
    assert Owner.CLAUDE in owners
    assert Owner.FOUNDER in owners


# ------------------------------------------------------ contested ownership
def test_the_known_ownership_contest_is_pinned_and_not_silently_resolved():
    """One canonical owner per concern is the standard; today one is contested.

    Pinned rather than fixed, for two reasons. The contest is real — KIMI's
    catalogue spans three repositories and mine spans the kernel — and choosing
    between them is an ownership ruling, which the protocol reserves for the
    founder. A module that resolved it by declaring itself canonical would be
    doing the thing the whole register exists to detect.
    """
    contested = contested_concerns()
    assert tuple(sorted(contested)) == KNOWN_CONTESTED, (
        f"the set of contested concerns changed: {sorted(contested)}. "
        "A new contest is a new defect and needs a founder ruling, not a "
        "widened assertion."
    )
    owners = {r.owner for r in contested["open founder decisions"]}
    assert owners == {Owner.CLAUDE, Owner.KIMI}


def test_a_new_contest_breaks_the_pin():
    """The guard must bite, checked on a constructed set rather than trusted."""
    rows = KNOWN_REGISTRIES + (
        Registry(registry_id="REG-TEST", owner=Owner.CHATGPT,
                 canonical_for="founder intent, machine-readable",
                 repository="dababiyoda/uniimente-kernel", path="nowhere",
                 ref="agent/whatever", id_namespace="X-*"),
    )
    contested = contested_concerns(rows)
    assert "founder intent, machine-readable" in contested
    assert tuple(sorted(contested)) != KNOWN_CONTESTED


def test_conflicting_id_schemes_are_reported_rather_than_reconciled():
    """Both namespaces survive. Neither is renamed to match the other.

    The protocol's rule for conflicting sources is to preserve both and name the
    cheapest decisive clarification — here, a founder ruling on which registry
    owns the concern. Renaming one scheme to the other would destroy the
    lineage of whichever lost.
    """
    conflicts = dict(namespace_conflicts())
    assert "open founder decisions" in conflicts
    assert "DEC-OM-00N" in conflicts["open founder decisions"]
    assert "DELIB-KIMI-*" in conflicts["open founder decisions"]


# ----------------------------------------------------------- visibility
def test_most_records_are_invisible_to_other_contributors():
    """The measured state, not a complaint: three of four sit on branches."""
    detached = unmerged()
    assert len(detached) == 2, "KIMI's two rows merged via PR #82; mine have not"
    assert all(not r.merged for r in detached)
    assert {r.owner for r in detached} == {Owner.CLAUDE}, (
        "the only unmerged registries left are mine, which is now the honest "
        "asymmetry: KIMI landed theirs and this branch has not landed its own"
    )


def test_render_names_every_registry_and_its_ref():
    text = render()
    for registry in KNOWN_REGISTRIES:
        assert registry.registry_id in text
        assert registry.canonical_for in text
    assert "founder decision" in text


@pytest.mark.parametrize("registry", KNOWN_REGISTRIES, ids=lambda r: r.registry_id)
def test_every_row_is_locatable(registry):
    """A row that cannot name repository, path and ref cannot be verified."""
    assert "/" in registry.repository
    assert registry.path
    assert registry.ref
    assert registry.id_namespace


def test_a_shared_directory_does_not_make_another_contributor_present(tmp_path):
    """The bug this module shipped with, pinned so it cannot return.

    Writing one CLAUDE handoff into KIMI's `docs/collaboration/` created that
    directory on this branch. A directory-existence probe then reported KIMI's
    catalogue reachable while none of KIMI's records were there — a contributor
    made to look present by a neighbour's file. Sharing the directory was the
    right call; the probe was wrong, so the probe changed.
    """
    shared = tmp_path / "docs" / "collaboration"
    shared.mkdir(parents=True)
    (shared / "COLLAB-HANDOFF-CLAUDE-001.yaml").write_text("collaboration_record: {}\n")

    by_id = {r.registry_id: r for r in KNOWN_REGISTRIES}
    kimi = by_id["REG-COLLAB-KIMI"]
    assert kimi.probe != kimi.path, "the probe must be more specific than the folder"
    assert not kimi.reachable(str(tmp_path)), (
        "a directory containing only someone else's file is not this registry"
    )

    (shared / "ARCHITECTURE-OWNERSHIP-MAP.yaml").write_text("x: 1\n")
    assert kimi.reachable(str(tmp_path)), "with KIMI's own record present, reachable"


def test_every_registry_probes_for_a_real_artifact():
    """A row whose probe is a bare directory can be faked by any neighbour."""
    for registry in KNOWN_REGISTRIES:
        assert registry.probe, registry.registry_id
        if registry.probe == registry.path:
            assert "." in os.path.basename(registry.path), (
                f"{registry.registry_id} probes a directory; name a file instead"
            )
