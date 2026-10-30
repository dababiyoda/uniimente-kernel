"""The constitution's cathedral kill condition, computed (directive 2026-10-28 sections 55 and 67).

constitution/constitution.ucl: "activity rises while external outcomes remain unchanged ... then
suspend_expansion_and_escalate(alfonso)". Activity is read from git objects in synthetic repositories built here;
outcomes from a real body's ledger, at the founder tier only. No test reads this repository's own history.
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess

import pytest

from events.spine import EventSpine
from greg import cathedral, cli
from greg.body import Body, Layout, observe
from greg.journal import Journal
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import (TEST_PASSPHRASE, Clock, attest_founder_tier, drop, make_body, mission, note_check,
                                 signed, workspace, write_strategy)

DAY = timedelta(days=1)


def git(repo: Path, *args: str, when: datetime | None = None) -> str:
    stamp = (when or datetime(2026, 1, 1, tzinfo=timezone.utc)).isoformat()
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp,
           "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(repo.parent)}
    return subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
                          check=True, capture_output=True, text=True, env=env).stdout


def commit(repo: Path, when: datetime, files: dict, subject: str = "work") -> None:
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", subject, when=when)


def new_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    return repo


def busy_repo(tmp: Path, until: datetime) -> Path:
    """Twelve documents, twelve modules and three evidence READMEs (fifteen .md files) added in the 30 days to ``until``."""
    repo = new_repo(tmp)
    commit(repo, until - 40 * DAY, {"README.md": "old"}, "before the window")
    for i in range(4):
        commit(repo, until - (20 - i) * DAY, {**{f"docs/d{i}_{j}.md": "x" for j in range(3)},
                                               **{f"pkg/m{i}_{j}.py": "x = 1\n" for j in range(3)}})
    commit(repo, until - 5 * DAY, {f"docs/evidence/run{k}/README.md": "r" for k in range(3)})
    return repo


def founders_body(tmp: Path, monkeypatch=None, *, designate: bool = True, attest: bool = False) -> tuple:
    """A body whose test founder key signed the first-body designation (``designate``) and, with ``attest``, whose
    passphrase-protected test key claimed the founder tier. Neither makes the key Alfonso's. Returns
    (home, key, body_id, clock); every record of the setup is older than the next ``datetime.now``."""
    home, key, body_id, _ = make_body(tmp, passphrase=TEST_PASSPHRASE if attest else None)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
    if designate:
        drop(home, signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}, now=clock.now))
    if attest:
        attest_founder_tier(home, tmp / "founder.pem", TEST_PASSPHRASE, monkeypatch)
    with Body(home, clock=clock) as body:
        body.tick()
    with observe(home) as journal:
        assert (cathedral.founder_body(journal) is not None) is designate
    return home, key, body_id, clock


def opening() -> dict:
    """A 30-day window that opens now, after every record a body set up so far wrote (ledger time is real time)."""
    since = datetime.now(timezone.utc)
    return {"since": since, "until": since + 30 * DAY}


def later() -> datetime:
    """A window end after every ledger record a test writes (ledger timestamps are real time)."""
    return datetime.now(timezone.utc) + timedelta(minutes=30)


def ledger_digest(home: Path) -> str:
    return hashlib.sha256(Layout(home).ledger.read_bytes()).hexdigest()


def close_mission(home: Path, key, body_id: str, mid: str, clock: Clock) -> None:
    ws = workspace(home, mid)
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[note_check("c", ws / "c.txt", "ok")], strategies=[write_strategy("w", "c.txt", "ok", ["c"])],
        capabilities=["fs.read", "fs.write"], targets=("fs:*", "workspace:c.txt")), now=clock.now))
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(6):
            body.tick()
            clock.advance(1)
            if any(e.payload["mission_id"] == mid for e in body.journal.replay("mission.achieved")):
                return
    raise AssertionError(f"{mid} did not close")


def detect(repo: Path, home: Path | None, **kw) -> dict:
    if home is None:
        return cathedral.detect(repo, **kw)
    with observe(home) as journal:
        return cathedral.detect(repo, journal=journal, body=str(home), **kw)


def test_activity_rising_while_outcomes_stay_flat_is_cathedral_and_the_detector_writes_nothing(tmp_path):
    home, *_ = founders_body(tmp_path)
    span = opening()
    repo = busy_repo(tmp_path, span["until"])
    before, head = ledger_digest(home), git(repo, "rev-parse", "HEAD")
    report = detect(repo, home, **span)
    assert report["verdict"] == cathedral.CATHEDRAL
    assert report["activity"]["counts"] == {"commits": 5, "pr_like_merges": 0, "new_md": 15, "new_py": 12,
                                            "new_evidence_readmes": 3}
    assert sorted(report["activity"]["floors_reached"]) == ["new_evidence_readmes", "new_md", "new_py"]
    assert report["outcomes"]["moved"] is False and report["outcomes"]["moved_by"] == []
    assert report["outcomes"]["end"] == {"founder_tier_closures": [], "vepmc_founder_tier_count": 0,
                                         "achieved_nodes": ["N0"]}
    assert report["outcomes"]["coverage"]["covers_window"] is True and report["outcomes"]["decides"] is True
    assert "stop horizontal expansion" in report["finding"]
    assert report["kill_condition"]["then"] == "suspend_expansion_and_escalate(alfonso)"
    assert "raises no founder ask" in report["acts"]
    # read-only: the ledger is byte-identical, no ask was raised, the repository is untouched
    assert ledger_digest(home) == before
    with observe(home) as journal:
        assert journal.replay("decision.requested") == []
    assert git(repo, "rev-parse", "HEAD") == head and git(repo, "status", "--porcelain") == ""


def test_test_key_closures_stay_cathedral_and_show_only_as_vertical_progress(tmp_path):
    home, key, body_id, clock = founders_body(tmp_path)              # a test key: never the founder tier
    span = opening()
    repo = busy_repo(tmp_path, span["until"])
    close_mission(home, key, body_id, "m:test-key", clock)
    report = detect(repo, home, **span)
    assert report["verdict"] == cathedral.CATHEDRAL
    assert report["outcomes"]["grew"] == {"founder_tier_closures": [], "vepmc_founder_tier_count": 0,
                                          "achieved_nodes": []}
    assert report["vertical_progress"]["closures_not_counted_in_window"] == ["m:test-key"]
    assert report["vertical_progress"]["counted_as_outcome"] is False


def test_a_founder_tier_closure_in_the_window_moves_the_outcome(tmp_path, monkeypatch):
    home, key, body_id, clock = founders_body(tmp_path, monkeypatch, attest=True)
    span = opening()
    repo = busy_repo(tmp_path, span["until"])
    close_mission(home, key, body_id, "m:founder", clock)
    report = detect(repo, home, **span)
    assert report["verdict"] == cathedral.NOT_CATHEDRAL
    assert report["outcomes"]["moved_by"] == ["founder_tier_closures"]
    assert report["outcomes"]["grew"]["founder_tier_closures"] == ["m:founder"]
    assert "finding" not in report


def test_a_founder_tier_closure_on_a_body_never_designated_is_not_the_founders(tmp_path, monkeypatch):
    """A passphrase-protected test key claims the founder tier and closes a mission, but no founder-signed
    BODY_DESIGNATE named this body: its closures are not counted and its outcomes are not the founder's."""
    home, key, body_id, clock = founders_body(tmp_path, monkeypatch, designate=False, attest=True)
    span = opening()
    repo = busy_repo(tmp_path, span["until"])
    close_mission(home, key, body_id, "m:founder", clock)
    report = detect(repo, home, **span)
    assert report["verdict"] == cathedral.INSUFFICIENT_HISTORY
    assert report["outcomes"]["grew"]["founder_tier_closures"] == [] and report["outcomes"]["moved"] is False
    assert report["vertical_progress"]["closures_not_counted_in_window"] == ["m:founder"]
    assert report["outcomes"]["coverage"]["founder_body"] is None
    assert "not the founder's designated body" in report["insufficient"][0]


def test_a_closure_registered_before_the_designation_does_not_count(tmp_path, monkeypatch):
    home, key, body_id, clock = founders_body(tmp_path, monkeypatch, designate=False, attest=True)
    span = opening()
    repo = busy_repo(tmp_path, span["until"])
    close_mission(home, key, body_id, "m:before-designation", clock)
    drop(home, signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}, now=clock.now))
    with Body(home, clock=clock) as body:
        body.tick()
    report = detect(repo, home, **span)
    assert report["outcomes"]["end"]["founder_tier_closures"] == []
    assert report["vertical_progress"]["closures_not_counted_in_window"] == ["m:before-designation"]
    assert report["verdict"] == cathedral.INSUFFICIENT_HISTORY          # designated inside the window, nothing moved
    assert "after the window starts" in report["insufficient"][0]


def test_an_outcome_before_the_window_does_not_count_in_it(tmp_path, monkeypatch):
    """The founder-tier closure happened before ``since``: the ledger at the window's start already holds it."""
    home, key, body_id, clock = founders_body(tmp_path, monkeypatch, attest=True)
    close_mission(home, key, body_id, "m:earlier", clock)
    since = datetime.now(timezone.utc) + timedelta(minutes=1)          # after every record of this ledger
    repo = busy_repo(tmp_path, since + 30 * DAY)                       # its window commits fall in [since, since+30d)
    report = detect(repo, home, since=since, until=since + 30 * DAY)
    assert report["outcomes"]["start"]["founder_tier_closures"] == ["m:earlier"]
    assert report["outcomes"]["grew"]["founder_tier_closures"] == []
    assert report["verdict"] == cathedral.CATHEDRAL and report["outcomes"]["moved"] is False
    quiet = detect(repo, home, since=since, until=since + 2 * DAY)     # no commit in the first two days
    assert quiet["activity"]["counts"]["commits"] == 0 and quiet["verdict"] == cathedral.NOT_CATHEDRAL


def test_a_window_that_ends_before_the_ledger_begins_is_insufficient(tmp_path):
    home, *_ = founders_body(tmp_path)
    until = datetime.now(timezone.utc) - 60 * DAY                      # 60 days before this body existed
    repo = busy_repo(tmp_path, until)
    report = detect(repo, home, since=until - 30 * DAY, until=until)
    assert report["activity"]["rose"] is True
    assert report["verdict"] == cathedral.INSUFFICIENT_HISTORY and report["outcomes"]["decides"] is False
    assert report["outcomes"]["coverage"]["covers_window"] is False
    assert "at or after the window ends" in report["insufficient"][0]


def test_a_body_designated_inside_the_window_cannot_show_unchanged_but_a_moved_outcome_decides(tmp_path, monkeypatch):
    until = later()
    (tmp_path / "flat").mkdir()
    home, *_ = founders_body(tmp_path / "flat")
    repo = busy_repo(tmp_path / "flat", until)
    flat = detect(repo, home, since=until - 30 * DAY, until=until)      # the window opened before the body existed
    assert flat["activity"]["rose"] is True and flat["outcomes"]["moved"] is False
    assert flat["verdict"] == cathedral.INSUFFICIENT_HISTORY and "after the window starts" in flat["insufficient"][0]
    (tmp_path / "moved").mkdir()
    home, key, body_id, clock = founders_body(tmp_path / "moved", monkeypatch, attest=True)
    close_mission(home, key, body_id, "m:founder", clock)
    moved = detect(repo, home, since=until - 30 * DAY, until=until)
    assert moved["outcomes"]["coverage"]["covers_window"] is False and moved["outcomes"]["decides"] is True
    assert moved["verdict"] == cathedral.NOT_CATHEDRAL and moved["outcomes"]["moved_by"] == ["founder_tier_closures"]


def synthetic(tmp_path: Path) -> Journal:
    return Journal(EventSpine(EvidenceLedger("sha256:" + "3" * 64, path=str(tmp_path / "l.jsonl"))),
                   actor="spiffe://uniimente.internal/test/cathedral")


def test_only_a_founder_signed_first_body_designation_names_the_founders_body(tmp_path):
    """As greg.metrics.vepmc reads founder_body: the command was accepted as signed by the founder key."""
    journal = synthetic(tmp_path)
    journal.record("command.accepted", {"kind": "BODY_DESIGNATE", "signer": "device:phone", "digest": "d0"}, key="a")
    journal.record("body.designated", {"command_digest": "d0", "body_id": "b1", "purpose": "first_founder_body"},
                   key="b")
    journal.record("command.accepted", {"kind": "BODY_DESIGNATE", "signer": "founder", "digest": "d1"}, key="c")
    journal.record("body.designated", {"command_digest": "d1", "body_id": "b1", "purpose": "another"}, key="d")
    assert cathedral.founder_body(journal) is None                      # a delegate's, then another purpose
    accepted = journal.record("command.accepted", {"kind": "BODY_DESIGNATE", "signer": "founder", "digest": "d2"},
                              key="e")
    journal.record("body.designated", {"command_digest": "d2", "body_id": "b1", "purpose": "first_founder_body"},
                   key="f")
    found = cathedral.founder_body(journal)
    record = next(r for r in journal.ledger.by_type("event") if r.payload.get("event_id") == accepted.event_id)
    assert found == {"body_id": "b1", "seq": record.seq, "at": record.ts_utc}


def test_the_ledger_at_a_moment_holds_only_what_came_before_it(tmp_path):
    journal = synthetic(tmp_path)
    for i in range(3):
        journal.record("mission.registered", {"mission_id": f"m:{i}"}, key=[f"m:{i}"])
    records = journal.ledger.records
    moment = cathedral._at(records[2].ts_utc)                          # exactly the third record's time
    assert cathedral.as_of(journal, moment).ledger.records == records[:2]
    assert cathedral.as_of(journal, moment - timedelta(days=1)).ledger.records == records[:1]   # genesis is kept
    assert len(journal.ledger.records) == len(records)                  # nothing was written


def _fake_ends(monkeypatch, start: dict, end: dict) -> None:
    """``outcomes`` measured on two stand-in ledger states (start and end) without a body."""
    monkeypatch.setattr(cathedral, "as_of", lambda journal, moment: "start" if moment == journal["since"] else "end")
    monkeypatch.setattr(cathedral, "measure", lambda state: {"start": start, "end": end}[state])


LONG_AGO = "2026-01-01T00:00:00Z"


def state(closures=(), vepmc=0, achieved=("N0",), frontier="N1", built=("N0",), depth=0, below=()) -> dict:
    return {"outcomes": {"founder_tier_closures": list(closures), "vepmc_founder_tier_count": vepmc,
                         "achieved_nodes": list(achieved)},
            "vertical": {"build_frontier": frontier, "built": list(built), "structural_depth": depth,
                         "closures_not_counted": list(below)},
            "founder_body": {"body_id": "b", "seq": 3, "at": LONG_AGO}, "ledger_begins": LONG_AGO}


@pytest.mark.parametrize("end, moved_by", [
    (state(closures=["m:f"]), ["founder_tier_closures"]),
    (state(vepmc=1), ["vepmc_founder_tier_count"]),
    (state(achieved=["N0", "N1"]), ["achieved_nodes"]),
    (state(closures=["m:f"], vepmc=1, achieved=["N0", "N1"]),
     ["founder_tier_closures", "vepmc_founder_tier_count", "achieved_nodes"]),
])
def test_each_founder_tier_measure_alone_moves_the_outcome(monkeypatch, end, moved_by):
    since = datetime(2026, 10, 1, tzinfo=timezone.utc)
    _fake_ends(monkeypatch, state(), end)
    outcome, _ = cathedral.outcomes({"since": since}, since, since + DAY)
    assert outcome["moved"] is True and outcome["moved_by"] == moved_by


def test_vertical_progress_and_a_shrinking_count_never_move_the_outcome(monkeypatch):
    since = datetime(2026, 10, 1, tzinfo=timezone.utc)
    _fake_ends(monkeypatch, state(closures=["m:old"], vepmc=2),
               state(closures=["m:old"], vepmc=1, frontier="N3", built=["N0", "N1", "N2"], depth=2, below=["m:t"]))
    outcome, vertical = cathedral.outcomes({"since": since}, since, since + DAY)
    assert outcome["moved"] is False and outcome["grew"]["vepmc_founder_tier_count"] == 0
    assert vertical["build_frontier"] == {"start": "N1", "end": "N3"}
    assert vertical["structural_depth"] == {"start": 0, "end": 2}
    assert vertical["newly_built"] == ["N1", "N2"] and vertical["closures_not_counted_in_window"] == ["m:t"]
    assert vertical["counted_as_outcome"] is False and "never counted as one" in vertical["rule"]


def test_vertical_progress_alone_never_lifts_the_verdict(tmp_path, monkeypatch):
    """A test key built N1 and N2 inside the window; the founder's outcomes did not move: still CATHEDRAL."""
    until = later()
    repo = busy_repo(tmp_path, until)
    _fake_ends(monkeypatch, state(), state(frontier="N3", built=["N0", "N1", "N2"], depth=2, below=["m:t"]))
    report = cathedral.detect(repo, journal={"since": until - 30 * DAY}, since=until - 30 * DAY, until=until)
    assert report["vertical_progress"]["newly_built"] == ["N1", "N2"]
    assert report["verdict"] == cathedral.CATHEDRAL


def test_activity_under_every_floor_is_not_cathedral(tmp_path):
    home, *_ = founders_body(tmp_path)
    span = opening()
    repo = new_repo(tmp_path)
    commit(repo, span["until"] - 3 * DAY, {"a.md": "x", "b.py": "x"})
    report = detect(repo, home, **span)
    assert report["verdict"] == cathedral.NOT_CATHEDRAL
    assert report["activity"]["rose"] is False and report["activity"]["floors_reached"] == []


def test_the_floors_scale_with_a_longer_window_so_steady_activity_never_reads_as_risen(tmp_path):
    assert cathedral.floors(30) == cathedral.floors(7) == cathedral.THRESHOLDS["activity_floor"]
    assert cathedral.floors(90)["commits"] == 60 and cathedral.floors(365)["commits"] == 244
    until = datetime(2026, 10, 30, tzinfo=timezone.utc)
    repo = new_repo(tmp_path)
    for i in range(21):                                                # one commit a fortnight for ten months
        git(repo, "commit", "-q", "--allow-empty", "-m", f"c{i}", when=until - (14 * i + 1) * DAY)
    for days in (30, 90, 365):
        steady = cathedral.activity(repo, until - days * DAY, until)
        assert steady["rose"] is False and steady["floors_applied"] == cathedral.floors(days), days
    assert cathedral.activity(repo, until - 365 * DAY, until)["counts"]["commits"] == 21
    burst = tmp_path / "burst"
    burst.mkdir()
    burst = new_repo(burst)
    for i in range(60):                                                # sixty commits in ninety days: risen
        git(burst, "commit", "-q", "--allow-empty", "-m", f"b{i}", when=until - (i * 1.5 + 1) * DAY)
    assert cathedral.activity(burst, until - 90 * DAY, until)["floors_reached"] == ["commits"]


def test_activity_counts_only_git_objects_inside_the_window(tmp_path, monkeypatch):
    until = datetime(2026, 10, 30, tzinfo=timezone.utc)
    repo = new_repo(tmp_path)
    commit(repo, until - 31 * DAY, {"old.md": "x", "old.py": "x"}, "before the window")
    commit(repo, until - 10 * DAY, {"docs/evidence/a/README.md": "r", "docs/evidence/a/run.json": "{}",
                                    "docs/README.md": "x", "docs/a.md": "x", "x.py": "x"}, "fix (#12)")
    git(repo, "mv", "old.py", "renamed.py")
    commit(repo, until - 9 * DAY, {}, "a rename is not a new file")
    git(repo, "rm", "-q", "x.py")
    commit(repo, until - 8 * DAY, {}, "remove")
    commit(repo, until - 7 * DAY, {"x.py": "again"}, "a path added twice counts once")
    git(repo, "checkout", "-q", "-b", "side")
    commit(repo, until - 6 * DAY, {"side.md": "x"}, "on a branch")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "-m", "merge side", "side", when=until - 5 * DAY)
    commit(repo, until + DAY, {"future.md": "x"}, "after the window")
    counts = cathedral.activity(repo, until - 30 * DAY, until)["counts"]
    assert counts == {"commits": 6, "pr_like_merges": 2, "new_md": 4, "new_py": 1, "new_evidence_readmes": 1}
    assert cathedral.activity(tmp_path / "nowhere", until - DAY, until)["complete"] is False
    monkeypatch.setenv("PATH", str(tmp_path / "no-git-here"))                  # git missing: incomplete, no crash
    assert cathedral.activity(repo, until - DAY, until)["complete"] is False
    monkeypatch.undo()
    empty = tmp_path / "empty"
    empty.mkdir()
    git(empty, "init", "-q")
    assert cathedral.activity(empty, until - DAY, until)["counts"]["commits"] == 0


def test_a_path_that_is_not_utf8_is_counted_not_a_crash(tmp_path):
    until = datetime(2026, 10, 30, tzinfo=timezone.utc)
    repo = new_repo(tmp_path)
    commit(repo, until - 3 * DAY, {"a.md": "x"})
    with open(os.path.join(os.fsencode(repo), b"caf\xe9.md"), "wb") as handle:     # Latin-1, not UTF-8
        handle.write(b"x")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "a Latin-1 name", when=until - 2 * DAY)
    report = cathedral.activity(repo, until - 30 * DAY, until)
    assert report["complete"] is True and report["counts"]["new_md"] == 2 and report["counts"]["commits"] == 2
    json.dumps(report)


def test_a_graft_cannot_cut_the_history_counted(tmp_path):
    until = datetime(2026, 10, 30, tzinfo=timezone.utc)
    repo = new_repo(tmp_path)
    for i in range(30):
        commit(repo, until - (25 - i * 0.5) * DAY, {f"d{i}.md": "x"}, f"c{i}")
    full = cathedral.activity(repo, until - 30 * DAY, until)
    assert full["counts"]["commits"] == 30 and full["counts"]["new_md"] == 30 and full["replace_refs_ignored"] == 0
    git(repo, "replace", "--graft", "HEAD~2")                          # HEAD~2 now looks like a root commit
    replaced = cathedral.activity(repo, until - 30 * DAY, until)
    assert replaced["complete"] is True and replaced["counts"] == full["counts"]
    assert replaced["replace_refs_ignored"] == 1
    git(repo, "replace", "-d", git(repo, "rev-parse", "HEAD~2").strip())
    (repo / ".git" / "info" / "grafts").write_text(git(repo, "rev-parse", "HEAD~2"))
    grafted = cathedral.activity(repo, until - 30 * DAY, until)
    assert grafted["complete"] is False and grafted["counts"] is None and "grafts file" in grafted["why"]
    report = cathedral.detect(repo, since=until - 30 * DAY, until=until)
    assert report["verdict"] == cathedral.INSUFFICIENT_HISTORY and "grafts file" in report["insufficient"][0]


def test_a_shallow_clone_is_insufficient_history_with_its_depth_and_no_counts(tmp_path):
    home, *_ = founders_body(tmp_path)
    span = opening()
    repo = busy_repo(tmp_path, span["until"])
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "2", f"file://{repo}", str(shallow)], check=True,
                   capture_output=True)
    report = detect(shallow, home, **span)
    assert report["verdict"] == cathedral.INSUFFICIENT_HISTORY
    assert report["activity"]["shallow"] is True and report["activity"]["depth"] == 2
    assert report["activity"]["counts"] is None and "rose" not in report["activity"]
    assert "shallow clone: only 2 commits" in report["insufficient"][0]
    assert detect(repo, home, **span)["verdict"] == cathedral.CATHEDRAL                # the full clone decides


def test_without_a_body_ledger_outcomes_are_unmeasured_not_flat(tmp_path):
    until = later()
    repo = busy_repo(tmp_path, until)
    report = detect(repo, None, since=until - 30 * DAY, until=until)
    assert report["verdict"] == cathedral.INSUFFICIENT_HISTORY
    assert report["outcomes"] == {"measured": False, "decides": False, "why": cathedral.NO_LEDGER}
    assert report["activity"]["complete"] is True and report["activity"]["rose"] is True


def test_the_window_is_declared_and_checked():
    now = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
    assert cathedral.window(now=now) == (now - 30 * DAY, now)
    assert cathedral.window(days=7, now=now) == (now - 7 * DAY, now)
    assert cathedral.window(since="2026-10-01", until="2026-10-02T00:00:00Z") == (
        datetime(2026, 10, 1, tzinfo=timezone.utc), datetime(2026, 10, 2, tzinfo=timezone.utc))
    for bad in ({"since": "2026-10-03", "until": "2026-10-02"}, {"days": 0}, {"since": "yesterday"},
                {"since": "2026-10-01", "days": 3}, {"days": float("nan")}):
        with pytest.raises(cathedral.CathedralError):
            cathedral.window(**bad)
    assert cathedral.THRESHOLDS["window_days"] == 30


@pytest.mark.parametrize("bad", [{"days": float("inf")}, {"days": 1e6}, {"days": 1e9},
                                 {"since": "0001-01-01T00:00:00+14:00", "until": "2026-10-30"},
                                 {"until": "9999-12-31T23:59:59-05:00"}])
def test_a_window_past_the_calendar_is_refused_not_a_traceback(bad):
    with pytest.raises(cathedral.CathedralError, match="outside the representable calendar"):
        cathedral.window(**bad)


def greg(*argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main([str(a) for a in argv])
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def test_the_cli_prints_what_the_module_computes(tmp_path):
    home, *_ = founders_body(tmp_path)
    since = (datetime.now(timezone.utc) + timedelta(seconds=1)).replace(microsecond=0)
    until = since + 30 * DAY
    repo = busy_repo(tmp_path, until)
    expected = detect(repo, home, since=since, until=until)
    span = ["--repo", repo, "--since", since.isoformat(), "--until", until.isoformat()]
    code, out, _ = greg("--home", tmp_path / "elsewhere", "cathedral", *span, "--body", home)
    assert code == 0 and json.loads(out) == expected
    code, out, _ = greg("--home", home, "cathedral", *span, "--body")          # --body alone reads --home
    assert code == 0 and json.loads(out) == expected and expected["verdict"] == cathedral.CATHEDRAL
    code, out, _ = greg("--home", home, "cathedral", *span)                    # without --body: unmeasured
    assert code == 0 and json.loads(out) == detect(repo, None, since=since, until=until)
    code, _, err = greg("--home", tmp_path / "none", "cathedral", *span, "--body")
    assert code == 2 and "no body ledger" in err
    code, _, err = greg("cathedral", "--repo", repo, "--since", "soon")
    assert code == 2 and "ISO 8601" in err
    code, _, err = greg("cathedral", "--since", "2026-10-01", "--days", "3")
    assert code == 2 and "not allowed with" in err
    for days in ("1e6", "inf"):                                                 # refused, never a traceback
        code, _, err = greg("--home", tmp_path / "none", "cathedral", "--repo", repo, "--days", days)
        assert code == 2 and "outside the representable calendar" in err
