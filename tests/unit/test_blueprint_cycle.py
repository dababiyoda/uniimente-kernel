"""The cycle audit must be able to indict the session that wrote it.

An instrument whose worst possible reading is "all clear" measures nothing. The
tests here are mostly about the audit's capacity to return an unflattering
answer and its inability to be talked out of one:

1. A reading that is not anchored to a commit cannot be recorded, because it
   cannot be reproduced.
2. The past cannot be amended — only appended to.
3. Counts are derived from readings, so a snapshot cannot carry a number that
   disagrees with itself.
4. A technology *leaving* the frontier is not progress. This is the whole
   subtlety: reaching a ceiling looks like movement in every summary statistic
   and is the opposite of it.
5. The verdict logic may not be tuned to flatter the author. The one real
   CEREMONY_SUSPECTED cycle on record is asserted to stay that way.
"""
from __future__ import annotations

import json
import os

import pytest

from blueprint.cycle import (
    SNAPSHOT_DIR,
    SCHEMA_VERSION,
    Snapshot,
    SnapshotError,
    TechnologyReading,
    Verdict,
    compare,
    consecutive_ceremony,
    head_commit,
    history,
    kill_condition_fired,
    load_all,
    save,
    take,
)
from blueprint.evidence import KERNEL_ROOT

# Synthetic 40-hex anchors, distinguishable by their first seven characters
# because that is what a snapshot filename carries.
A = "a" * 7 + "1" * 33
B = "b" * 7 + "2" * 33
C = "c" * 7 + "3" * 33
D = "d" * 7 + "4" * 33


def _snap(commit: str, rows, provenance: str = "live") -> Snapshot:
    return Snapshot(
        commit=commit,
        taken_at="2026-01-01T00:00:00+00:00",
        provenance=provenance,
        readings=tuple(TechnologyReading(*row) for row in rows),
    )


# ------------------------------------------------------------------- anchoring
@pytest.mark.parametrize("commit", ["", "   ", "HEAD", "main", "zzzzzzz", "abc"])
def test_a_snapshot_without_a_commit_anchor_is_refused(commit):
    with pytest.raises(SnapshotError) as exc:
        _snap(commit, [(1, "BUILT", "HARDENED", True)])
    assert "anchored" in str(exc.value)


def test_a_snapshot_with_no_readings_is_refused():
    with pytest.raises(SnapshotError):
        _snap(A, [])


def test_a_snapshot_may_not_read_a_technology_twice():
    with pytest.raises(SnapshotError) as exc:
        _snap(A, [(1, "BUILT", "HARDENED", True), (1, "PROVEN", "HARDENED", True)])
    assert "once, not twice" in str(exc.value)


def test_a_reading_that_is_not_a_rung_is_refused():
    with pytest.raises(SnapshotError):
        _snap(A, [(1, "NEARLY_DONE", "HARDENED", True)])
    with pytest.raises(SnapshotError):
        _snap(A, [(1, "BUILT", "PRETTY_GOOD", True)])


def test_an_unknown_provenance_is_refused():
    """A reconstruction may not pass as a contemporaneous observation."""
    with pytest.raises(SnapshotError):
        _snap(A, [(1, "BUILT", "HARDENED", True)], provenance="probably_fine")


# --------------------------------------------------------------------- storage
def test_counts_are_derived_and_never_stored():
    """A serialized snapshot has no field in which to carry a flattering total."""
    snap = _snap(A, [(1, "BUILT", "HARDENED", True), (2, None, "BLUEPRINT", True)])
    assert "rung_counts" not in Snapshot.__dataclass_fields__
    assert set(snap.to_obj()) == {"schema_version", "commit", "taken_at",
                                  "provenance", "readings"}
    assert snap.rung_counts["BUILT"] == 1
    assert snap.rung_counts["UNSUPPORTED"] == 1


def test_save_and_load_round_trip_is_lossless(tmp_path):
    snap = _snap(A, [(1, "BUILT", "HARDENED", True), (2, None, "BLUEPRINT", False)])
    save(snap, str(tmp_path))
    loaded = load_all(str(tmp_path))
    assert len(loaded) == 1
    assert loaded[0].to_obj() == snap.to_obj()


def test_save_refuses_a_second_reading_of_a_commit_already_on_record(tmp_path):
    """Two readings of one tree must agree, so a second one is an amendment."""
    rows = [(1, "BUILT", "HARDENED", True)]
    save(_snap(A, rows), str(tmp_path))
    with pytest.raises(SnapshotError) as exc:
        save(_snap(A, [(1, "PROVEN", "HARDENED", True)]), str(tmp_path))
    assert "appended to, not amended" in str(exc.value)


def test_snapshots_are_numbered_in_the_order_they_were_appended(tmp_path):
    save(_snap(A, [(1, "BUILT", "HARDENED", True)]), str(tmp_path))
    save(_snap(B, [(1, "BUILT", "HARDENED", True)]), str(tmp_path))
    names = sorted(os.listdir(tmp_path))
    assert names == ["0001-aaaaaaa.json", "0002-bbbbbbb.json"]
    assert [s.commit for s in load_all(str(tmp_path))] == [A, B]


def test_a_snapshot_from_an_unknown_schema_version_is_refused(tmp_path):
    path = tmp_path / "0001-aaaaaaa.json"
    obj = _snap(A, [(1, "BUILT", "HARDENED", True)]).to_obj()
    obj["schema_version"] = SCHEMA_VERSION + 1
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(SnapshotError) as exc:
        load_all(str(tmp_path))
    assert "schema version" in str(exc.value)


# -------------------------------------------------------------------- verdicts
def test_an_unchanged_ladder_reads_as_no_change():
    rows = [(1, "BUILT", "HARDENED", True)]
    assert compare(_snap(A, rows), _snap(B, rows)).verdict is Verdict.NO_CHANGE


def test_raising_a_rung_that_unlocks_nothing_is_ceremony_suspected():
    """The failure mode PR #71 named against its own instrument."""
    before = _snap(A, [(1, None, "EXERCISED", True), (2, "BUILT", "BUILT", False)])
    after = _snap(B, [(1, "EXERCISED", "EXERCISED", False), (2, "BUILT", "BUILT", False)])
    result = compare(before, after)
    assert result.verdict is Verdict.CEREMONY_SUSPECTED
    assert result.rungs_raised == ((1, "UNSUPPORTED", "EXERCISED"),)
    assert not result.unlocked


def test_a_technology_leaving_the_frontier_does_not_count_as_movement():
    """Reaching a ceiling shrinks the frontier. That is not progress downstream."""
    before = _snap(A, [(1, "BUILT", "EXERCISED", True)])
    after = _snap(B, [(1, "EXERCISED", "EXERCISED", False)])
    result = compare(before, after)
    assert result.frontier_left == (1,)
    assert result.frontier_entered == ()
    assert result.verdict is Verdict.CEREMONY_SUSPECTED


def test_raising_a_rung_that_raises_a_ceiling_is_substantive():
    before = _snap(A, [(1, None, "HARDENED", True), (2, "BLUEPRINT", "BLUEPRINT", False)])
    after = _snap(B, [(1, "EXERCISED", "HARDENED", True),
                      (2, "BLUEPRINT", "EXERCISED", True)])
    result = compare(before, after)
    assert result.verdict is Verdict.SUBSTANTIVE
    assert result.ceilings_raised == ((2, "BLUEPRINT", "EXERCISED"),)
    assert result.frontier_entered == (2,)


def test_an_external_outcome_is_substantive_on_its_own():
    before = _snap(A, [(1, "PROVEN", "HARDENED", True)])
    after = _snap(B, [(1, "HARDENED", "HARDENED", False)])
    result = compare(before, after)
    assert result.outcomes_gained == 1
    assert result.verdict is Verdict.SUBSTANTIVE


def test_a_lowered_rung_outranks_every_other_reading():
    """A lost rung is the most alarming signal and may not be averaged away."""
    before = _snap(A, [(1, "PROVEN", "HARDENED", True), (2, "BLUEPRINT", "BLUEPRINT", False)])
    after = _snap(B, [(1, "BUILT", "HARDENED", True), (2, "EXERCISED", "EXERCISED", False)])
    result = compare(before, after)
    assert result.rungs_raised and result.rungs_lowered
    assert result.verdict is Verdict.REGRESSION


def test_a_technology_added_to_the_arsenal_is_reported_not_diffed():
    before = _snap(A, [(1, "BUILT", "HARDENED", True)])
    after = _snap(B, [(1, "BUILT", "HARDENED", True), (2, None, "BLUEPRINT", True)])
    result = compare(before, after)
    assert result.appeared == (2,)
    assert result.rungs_raised == ()


# --------------------------------------------------------------- kill condition
#: Two technologies, neither with dependents, each climbing to its own ceiling in
#: turn. Every statistic moves; nothing is unlocked. This is the firing shape.
_CEREMONY_RUN = (
    _snap(A, [(1, None, "EXERCISED", True), (2, None, "EXERCISED", True),
              (3, "BLUEPRINT", "BLUEPRINT", False)]),
    _snap(B, [(1, "EXERCISED", "EXERCISED", False), (2, None, "EXERCISED", True),
              (3, "BLUEPRINT", "BLUEPRINT", False)]),
    _snap(C, [(1, "EXERCISED", "EXERCISED", False),
              (2, "EXERCISED", "EXERCISED", False),
              (3, "BLUEPRINT", "BLUEPRINT", False)]),
)


def test_two_consecutive_ceremony_cycles_fire_the_declared_kill_condition():
    comparisons = history(_CEREMONY_RUN)
    assert [c.verdict for c in comparisons] == [Verdict.CEREMONY_SUSPECTED] * 2
    assert consecutive_ceremony(comparisons) == 2
    assert kill_condition_fired(comparisons)


def test_the_ceremony_run_resets_on_a_substantive_cycle():
    """One cycle that actually opens headroom clears the run, and must."""
    substantive = _snap(
        D,
        [(1, "EXERCISED", "EXERCISED", False), (2, "EXERCISED", "EXERCISED", False),
         (3, "EXERCISED", "EXERCISED", True)],       # ceiling BLUEPRINT -> EXERCISED
    )
    comparisons = history(_CEREMONY_RUN + (substantive,))
    assert comparisons[-1].verdict is Verdict.SUBSTANTIVE
    assert comparisons[-1].ceilings_raised == ((3, "BLUEPRINT", "EXERCISED"),)
    assert consecutive_ceremony(comparisons) == 0
    assert not kill_condition_fired(comparisons)


# ------------------------------------------------------------------ real ladder
def test_take_derives_every_field_from_the_real_ladder():
    from blueprint.critical_path import compute

    report = compute()
    snapshot = take(head_commit(), root=KERNEL_ROOT)
    assert len(snapshot.readings) == len(report.statuses)
    assert snapshot.frontier == frozenset(s.technology_id for s in report.frontier)
    for status in report.statuses.values():
        reading = snapshot.by_id[status.technology_id]
        assert reading.awarded == (
            status.awarded_rung.value if status.awarded_rung else None
        )
        assert reading.ceiling == status.ceiling.value


def test_head_commit_resolves_this_repository():
    commit = head_commit()
    assert len(commit) == 40 and all(c in "0123456789abcdef" for c in commit)


def test_the_committed_history_is_internally_consistent():
    snapshots = load_all()
    assert snapshots, "the audit has no history; it cannot detect a trend"
    commits = [s.commit for s in snapshots]
    assert len(set(commits)) == len(commits), "a commit is on record twice"
    for snap in snapshots:
        assert len(snap.readings) == 55


def test_the_recorded_shell_cycle_stays_recorded_as_ceremony_suspected():
    """The verdict logic may not be retuned to flatter the session that wrote it.

    `310b0c8` raised technology #14 from UNSUPPORTED to EXERCISED. Nothing in
    the arsenal depends on #14, so no ceiling rose and nothing entered the
    frontier. The shell has independent value; that cycle still did not advance
    the critical path, and the audit is required to keep saying so.
    """
    ceremony = [c for c in history() if c.verdict is Verdict.CEREMONY_SUSPECTED]
    assert any(
        any(tech_id == 14 for tech_id, _, _ in c.rungs_raised) for c in ceremony
    ), "the #14 cycle is no longer reported as unlocking nothing"


def test_the_cycle_audit_grants_nothing():
    import blueprint.cycle as cycle

    for name in ("authorize", "activate", "promote", "kill", "schedule", "apply"):
        assert not hasattr(cycle, name), f"the cycle audit grew {name}"
    for name in ("authorize", "activate", "promote", "kill"):
        assert not hasattr(Snapshot, name)


def test_cli_reports_history_without_recording_anything():
    from blueprint.cycle import main

    before = sorted(os.listdir(SNAPSHOT_DIR))
    assert main(["history"]) == 0
    assert sorted(os.listdir(SNAPSHOT_DIR)) == before
