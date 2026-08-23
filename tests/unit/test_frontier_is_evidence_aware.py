"""The build frontier must not recommend work the ladder calls impossible.

`blueprint/ladder.py` states that HARDENED requires an externally observable,
reconciled consequence and is "currently unreachable by construction" while the
Single Bottleneck Metric stands at zero. `critical_path.frontier` selected on
`can_advance`, which is purely a dependency test, and so listed a PROVEN
technology with a clear ceiling under the heading "unblocked work".

Two components of one package disagreeing is worse than either being wrong
alone, because the frontier is what directs the next build.
"""
import ast
import os

from blueprint.critical_path import compute
from blueprint.ladder import EvidenceKind, Rung, required_evidence
from blueprint.registry import Owner

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- the contradiction, pinned ----------------------------------------------

def test_the_frontier_never_recommends_a_rung_needing_external_reality():
    """The defect this file exists for, stated as the property."""
    report = compute()

    for status in report.frontier:
        assert not report.needs_external_reality(status), (
            f"#{status.technology_id} {status.name} is on the frontier but its "
            f"next rung needs a reconciled external consequence")


def test_hardened_still_requires_an_external_outcome():
    """The ladder half of the contradiction, so the fix cannot be undone by
    quietly relaxing what HARDENED means instead."""
    assert EvidenceKind.EXTERNAL_OUTCOME in required_evidence(Rung.HARDENED)


def test_nothing_is_dropped_silently():
    """A technology excluded from the frontier must appear somewhere else.

    Removing it from the frontier without saying where it went would trade one
    misleading report for another.
    """
    report = compute()

    frontier = {s.technology_id for s in report.frontier}
    waiting = {s.technology_id for s in report.awaiting_external_reality}
    advanceable = {s.technology_id for s in report.statuses.values() if s.can_advance}

    assert frontier | waiting == advanceable
    assert frontier & waiting == set()


def test_the_technology_actually_held_back_is_reported_with_its_owner():
    """Concrete, because an abstract guarantee would pass on an empty list."""
    report = compute()
    waiting = report.awaiting_external_reality

    assert waiting, "expected at least one technology awaiting external reality"
    ids = {s.technology_id for s in waiting}
    assert 1 in ids, "#1 Interpreters and compilers sits at PROVEN with a clear ceiling"

    tech = next(s for s in waiting if s.technology_id == 1)
    assert tech.target_rung is Rung.HARDENED
    assert tech.owner is Owner.CLAUDE


# --- the determination is derived, not hardcoded -----------------------------

def test_the_block_is_computed_from_declared_evidence_not_a_rung_name():
    """If HARDENED's requirements ever change, this must follow rather than
    keep excluding it by name."""
    path = os.path.join(ROOT, "blueprint", "critical_path.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "needs_external_reality")
    source = ast.unparse(fn)

    assert "EXTERNAL_OUTCOME" in source
    assert "HARDENED" not in source, (
        "the check must read the rung's declared evidence, not name the rung")


def test_a_technology_holding_the_evidence_would_not_be_excluded():
    """The self-correcting half: exclusion is about *missing* evidence.

    `needs_external_reality` is false whenever the technology already satisfies
    EXTERNAL_OUTCOME, so the first real reconciled outcome returns it to the
    frontier with nothing edited here. Asserted through the same
    `missing_for` contract the implementation uses rather than by faking a
    resolution, which would only prove the fake.
    """
    from blueprint.ladder import missing_for

    everything = frozenset(EvidenceKind)
    assert EvidenceKind.EXTERNAL_OUTCOME not in missing_for(Rung.HARDENED, everything)

    nothing = frozenset()
    assert EvidenceKind.EXTERNAL_OUTCOME in missing_for(Rung.HARDENED, nothing)


# --- the report says where the work went -------------------------------------

def test_the_cli_prints_the_awaiting_section_rather_than_hiding_it():
    path = os.path.join(ROOT, "blueprint", "__main__.py")
    with open(path, encoding="utf-8") as fh:
        source = fh.read()

    assert "awaiting_external_reality" in source
    assert "AWAITING EXTERNAL REALITY" in source


def test_an_empty_frontier_does_not_suppress_the_awaiting_section():
    """The early `return` on an empty frontier would have hidden this section
    exactly when it matters most — a frontier emptied *by* external blocking."""
    path = os.path.join(ROOT, "blueprint", "__main__.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_print_frontier")
    returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]

    assert returns == [], (
        "_print_frontier must fall through to the awaiting section, not return early")


# --- one definition, not two -------------------------------------------------

def test_the_snapshot_and_the_report_agree_on_what_the_frontier_is():
    """`blueprint/cycle.py` reimplemented the frontier as `can_advance` alone.

    Two definitions of one concept is the defect class, not a detail: the cycle
    frontier feeds the stall detector, so a technology parked there permanently
    would inflate "available work" and mask the stall the detector exists to
    catch. The first fix to `critical_path` made them disagree, and the cycle's
    own test caught it — this holds them equal from now on.
    """
    from blueprint.cycle import take

    report = compute()
    snapshot = take("0" * 40)

    assert snapshot.frontier == frozenset(s.technology_id for s in report.frontier)


def test_historical_snapshots_still_load_and_are_not_rewritten():
    """The field defaults so snapshots written before the distinction existed
    still load, keeping the frontier they actually recorded at that commit.

    Rewriting them to match a later instrument would destroy the comparison the
    snapshots exist to support.
    """
    import json
    from blueprint.cycle import Snapshot

    directory = os.path.join(ROOT, "blueprint", "snapshots")
    files = sorted(f for f in os.listdir(directory) if f.endswith(".json"))
    assert files, "expected committed snapshots to compare against"

    for name in files:
        with open(os.path.join(directory, name), encoding="utf-8") as fh:
            payload = json.load(fh)
        snapshot = Snapshot.from_obj(payload)
        assert snapshot.readings
        # None of the historical records carry the field; they load regardless.
        assert all(not r.awaiting_external for r in snapshot.readings)
