"""Admission before edits (scripts/participation.py): the serialized decision, the hook, resume and handoff.

Each test replays issue comments offline. These cases are the adversarial cases that trial 3 predeclares:
simultaneous conflicting claims, incomplete data, stale resume, a revoked holder, and an unacknowledged handoff.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import participation as P  # noqa: E402

REPO = P.REPO
A, B, C = "session_01AAAAAAAAAAAAAAAAAAAAAA", "session_01BBBBBBBBBBBBBBBBBBBBBB", "session_01CCCCCCCCCCCCCCCCCCCCCC"


def checkin(cid, session, task, exclusive, shared="", depends="nothing", accepts="", heading="work"):
    lines = [P.CHECKIN, f"## Check-in: {heading}", f"- Session: {session} (test)", f"- Task: {task}",
             f"- Concern (exclusive): {exclusive}"]
    if shared:
        lines.append(f"- Concern (shared): {shared}")
    lines.append(f"- Depends on: {depends}")
    if accepts:
        lines.append(f"- Accepts handoff: {accepts}")
    return {"id": cid, "body": "\n".join(lines), "created_at": "2026-11-22T15:00:00Z",
            "html_url": f"https://github.com/{REPO}/issues/500#issuecomment-{cid}", "user": {"login": "x"}}


def other(cid, marker, *lines):
    return {"id": cid, "body": "\n".join([marker, *lines]), "created_at": "2026-11-22T15:00:00Z",
            "html_url": f"https://github.com/{REPO}/issues/500#issuecomment-{cid}", "user": {"login": "x"}}


def source(task_comments, index_comments=(), extra=None):
    data = {f"{REPO}#500": list(task_comments), f"{REPO}#96": list(index_comments)}
    data.update(extra or {})
    return P.Source(data)


@pytest.fixture()
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "AGENTS.md").write_text("guide\n")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "a.py").write_text("x\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "i"],
                   check=True)
    return tmp_path


def edit(path, cwd):
    return P.gate({"tool_name": "Edit", "tool_input": {"file_path": str(path)}, "cwd": str(cwd)})


def bash(command, cwd):
    return P.gate({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)})


# ---------------------------------------------------------------- root cause 1: participation before the first edit

def test_an_edit_in_a_worktree_without_admission_is_denied_and_one_outside_git_is_not(repo, tmp_path_factory):
    ok, why = edit(repo / "scripts" / "a.py", repo)
    assert not ok and "No admission" in why
    outside = tmp_path_factory.mktemp("scratch") / "note.md"
    assert edit(outside, outside.parent)[0]


def test_admission_then_allows_edits_inside_the_claim_and_denies_edits_outside(repo):
    P.admit((REPO, 500), 1000001, source([checkin(1000001, A, "T-1/a", "`scripts/`")]), cwd=str(repo))
    assert edit(repo / "scripts" / "a.py", repo)[0]
    assert edit(repo / "scripts" / "new.py", repo)[0]            # a new file inside a claimed directory
    ok, why = edit(repo / "AGENTS.md", repo)
    assert not ok and "outside claim" in why


def test_commit_and_push_are_withheld_until_admission_but_other_shell_commands_are_not(repo):
    assert not bash("git commit -m x", repo)[0]
    assert not bash("cd . && git -c core.x=1 push origin HEAD", repo)[0]
    assert bash("ls && git status && python scripts/participation.py admit --issue 500 --claim 1", repo)[0]
    P.admit((REPO, 500), 1000001, source([checkin(1000001, A, "T-1/a", "`scripts/`")]), cwd=str(repo))
    assert bash("git commit -m x", repo)[0]


def test_a_github_write_tool_is_withheld_until_admission(repo):
    event = {"tool_name": "mcp__github__push_files", "tool_input": {}, "cwd": str(repo)}
    assert not P.gate(event)[0]
    P.admit((REPO, 500), 1000001, source([checkin(1000001, A, "T-1/a", "`scripts/`")]), cwd=str(repo))
    assert P.gate(event)[0]
    assert P.gate({"tool_name": "mcp__github__issue_read", "tool_input": {}, "cwd": str(repo)})[0]


def test_unreadable_hook_input_blocks(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("not json"))
    assert P.hook_main() == 2


# ---------------------------------------------------------------- simultaneous conflicting claims

def test_of_two_conflicting_exclusive_claims_the_one_github_numbered_first_is_admitted_on_both_sides(repo):
    comments = [checkin(1000002, B, "T-2/b", "`scripts/a.py`"), checkin(1000001, A, "T-1/a", "`scripts/`")]
    first = P.admit((REPO, 500), 1000001, source(comments), cwd=str(repo), write=False)
    assert first["later_conflicts"][0]["claim"] == 1000002
    with pytest.raises(P.Refused, match="held by session_01AAAA"):
        P.admit((REPO, 500), 1000002, source(comments), cwd=str(repo), write=False)


def test_claims_on_unrelated_concerns_are_both_admitted(repo):
    comments = [checkin(1000001, A, "T-1/a", "`scripts/a.py`"), checkin(1000002, B, "T-2/b", "`docs/b.md`")]
    for cid in (1000001, 1000002):
        assert P.admit((REPO, 500), cid, source(comments), cwd=str(repo), write=False)["later_conflicts"] == []


def test_shared_concerns_never_conflict_and_a_path_prefix_is_not_a_name_prefix(repo):
    comments = [checkin(1000001, A, "T-1/a", "`scripts/a`", shared="`AGENTS.md`"),
                checkin(1000002, B, "T-2/b", "`scripts/ab.py`", shared="`AGENTS.md`")]
    assert P.admit((REPO, 500), 1000002, source(comments), cwd=str(repo), write=False)


def test_a_conflicting_claim_on_another_task_issue_named_in_the_index_is_found(repo):
    index = [other(9000001, P.INDEX, "- Task record: #501", "- Task: T-1")]
    extra = {f"{REPO}#501": [checkin(1000001, A, "T-1/a", "`scripts/`")]}
    with pytest.raises(P.Refused, match="claim 1000001"):
        P.admit((REPO, 500), 1000002, source([checkin(1000002, B, "T-2/b", "`scripts/a.py`")], index, extra),
                cwd=str(repo), write=False)


def test_a_claim_that_names_no_session_holds_nothing_and_is_reported(repo):
    bad = checkin(1000001, A, "T-1/a", "`scripts/`", heading="handoff of the parser")   # the map's rule: nobody
    comments = [bad, checkin(1000002, B, "T-2/b", "`scripts/a.py`")]
    with pytest.raises(P.Refused, match="names no session .handoff"):
        P.admit((REPO, 500), 1000001, source(comments), cwd=str(repo), write=False)
    rec = P.admit((REPO, 500), 1000002, source(comments), cwd=str(repo), write=False)
    assert rec["unresolved_overlaps"][0]["claim"] == 1000001


# ---------------------------------------------------------------- incomplete data is never "clear"

def test_an_unreadable_index_or_task_record_refuses_admission_and_status_says_incomplete(repo):
    src = P.Source({f"{REPO}#500": [checkin(1000001, A, "T-1/a", "`scripts/`")]})          # #96 missing
    with pytest.raises(P.Refused, match="incomplete"):
        P.admit((REPO, 500), 1000001, src, cwd=str(repo), write=False)
    answer = P.status((REPO, 500), P.Source({f"{REPO}#500": []}), "T-1", [])
    assert answer["coverage"] == "incomplete" and answer["claims"] == []


def test_a_truncated_read_is_incomplete(monkeypatch):
    monkeypatch.setattr(P, "MAX_PAGES", 2)
    monkeypatch.setattr(P, "_get", lambda path: ([{"id": 1, "body": ""}] * P.PAGE, "fake"))
    with pytest.raises(P.Refused, match="truncated"):
        P.Source().comments(REPO, 500)


# ---------------------------------------------------------------- release, handoff and a revoked former holder

def test_a_released_claim_cannot_be_revived_and_frees_its_concern(repo):
    comments = [checkin(1000001, A, "T-1/a", "`scripts/`"), checkin(1000002, B, "T-2/b", "`scripts/a.py`"),
                other(1000003, P.RELEASE, "- Claim: 1000001", f"- Session: {A}")]
    with pytest.raises(P.Refused, match="released"):
        P.admit((REPO, 500), 1000001, source(comments), cwd=str(repo), write=False)
    assert P.admit((REPO, 500), 1000002, source(comments), cwd=str(repo), write=False)


def test_a_release_by_another_session_releases_nothing(repo):
    comments = [checkin(1000001, A, "T-1/a", "`scripts/`"), other(1000002, P.RELEASE, "- Claim: 1000001",
                                                                 f"- Session: {B}")]
    assert P.admit((REPO, 500), 1000001, source(comments), cwd=str(repo), write=False)


def test_an_accepted_handoff_moves_the_claim_and_its_place_and_the_former_holder_cannot_resume_it(repo):
    comments = [checkin(1000001, A, "T-1/a", "`scripts/`"),
                checkin(1000002, C, "T-3/c", "`scripts/a.py`"),                  # posted after A, before B
                other(1000003, P.HANDOFF, "- Claim: 1000001", f"- From: {A}", f"- To: {B}"),
                checkin(1000004, B, "T-1/a", "`scripts/`", accepts="1000003")]
    rec = P.admit((REPO, 500), 1000004, source(comments), cwd=str(repo), write=False)
    assert rec["order"] == 1000001                                               # inherits A's place, ahead of C
    with pytest.raises(P.Refused, match="transferred"):
        P.admit((REPO, 500), 1000001, source(comments), cwd=str(repo), write=False)
    with pytest.raises(P.Refused, match="held by session_01BBBB"):
        P.admit((REPO, 500), 1000002, source(comments), cwd=str(repo), write=False)


def test_an_unaccepted_handoff_stays_pending_and_the_receiver_waits(repo):
    comments = [checkin(1000001, A, "T-1/a", "`scripts/`"),
                other(1000002, P.HANDOFF, "- Claim: 1000001", f"- From: {A}", f"- To: {B}"),
                checkin(1000003, B, "T-1/a", "`scripts/`")]                      # no Accepts handoff line
    with pytest.raises(P.Refused, match="held by session_01AAAA"):
        P.admit((REPO, 500), 1000003, source(comments), cwd=str(repo), write=False)


def test_a_handoff_accepted_by_someone_else_than_its_receiver_moves_nothing(repo):
    comments = [checkin(1000001, A, "T-1/a", "`scripts/`"),
                other(1000002, P.HANDOFF, "- Claim: 1000001", f"- From: {A}", f"- To: {B}"),
                checkin(1000003, C, "T-1/a", "`scripts/`", accepts="1000002")]
    with pytest.raises(P.Refused, match="held by session_01AAAA"):
        P.admit((REPO, 500), 1000003, source(comments), cwd=str(repo), write=False)


def test_check_after_a_transfer_revokes_the_local_admission(repo, monkeypatch):
    first = [checkin(1000001, A, "T-1/a", "`scripts/`")]
    P.admit((REPO, 500), 1000001, source(first), cwd=str(repo))
    later = first + [other(1000002, P.HANDOFF, "- Claim: 1000001", f"- From: {A}", f"- To: {B}"),
                     checkin(1000003, B, "T-1/a", "`scripts/`", accepts="1000002")]
    path = repo / "replay.json"
    path.write_text(json.dumps({f"{REPO}#500": later, f"{REPO}#96": []}))
    monkeypatch.chdir(repo)
    assert P.main(["check", "--comments-json", str(path)]) == 1
    ok, why = edit(repo / "scripts" / "a.py", repo)
    assert not ok and "refresh" in why


# ---------------------------------------------------------------- stale resume and refresh before publication

def test_a_resumed_session_must_refresh_before_its_next_edit(repo, monkeypatch):
    comments = [checkin(1000001, A, "T-1/a", "`scripts/`")]
    P.admit((REPO, 500), 1000001, source(comments), cwd=str(repo))
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("{}"))
    assert P.resume_main() == 0
    assert not edit(repo / "scripts" / "a.py", repo)[0]
    path = repo / "replay.json"
    path.write_text(json.dumps({f"{REPO}#500": comments, f"{REPO}#96": []}))
    monkeypatch.chdir(repo)
    assert P.main(["check", "--comments-json", str(path)]) == 0
    assert edit(repo / "scripts" / "a.py", repo)[0]


def test_a_push_needs_a_check_newer_than_the_freshness_window(repo, monkeypatch):
    P.admit((REPO, 500), 1000001, source([checkin(1000001, A, "T-1/a", "`scripts/`")]), cwd=str(repo))
    assert bash("git push", repo)[0]
    later = P.now() + timedelta(minutes=P.FRESH_MINUTES + 1)
    monkeypatch.setattr(P, "now", lambda: later)
    ok, why = bash("git push", repo)
    assert not ok and "Refresh before publishing" in why
    assert bash("git commit -m x", repo)[0]                                      # committing is not publishing


def test_each_worktree_needs_its_own_admission(repo, tmp_path_factory):
    P.admit((REPO, 500), 1000001, source([checkin(1000001, A, "T-1/a", "`scripts/`")]), cwd=str(repo))
    second = tmp_path_factory.mktemp("wt") / "w2"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", str(second)], check=True)
    assert not edit(second / "scripts" / "a.py", second)[0]


# ---------------------------------------------------------------- root causes 2, 4 and 5: matching and dependencies

def test_status_matches_by_task_subtask_concern_and_dependency_with_counts():
    comments = [checkin(1000001, A, "T-1/a", "`scripts/a.py`"), checkin(1000002, B, "T-2/b", "`docs/`",
                                                                     depends="T-1/a at abc123"),
                checkin(1000003, C, "T-3/c", "`greg/`")]
    answer = P.status((REPO, 500), source(comments), "T-1/a", ["docs/x.md"])
    by_claim = {c["claim"]: c["matched"] for c in answer["claims"]}
    assert by_claim[1000001] == ["same parent task and subtask"]
    assert "depends on this task" in by_claim[1000002] and "concern docs" in by_claim[1000002]
    assert 1000003 not in by_claim
    assert answer["coverage"] == "complete" and answer["counts"]["matched"] == 2


def test_a_dependency_is_pending_until_the_producer_acknowledges_it_and_both_sides_see_it(repo):
    producer = checkin(1000001, A, "T-1/a", "`scripts/a.py`")
    dependent = checkin(1000002, B, "T-2/b", "`docs/`", depends="T-1/a provisional: parse() returns a dict")
    rec = P.admit((REPO, 500), 1000002, source([producer, dependent]), cwd=str(repo), write=False)
    assert rec["dependencies"]["depends_on"][0]["state"] == "pending"
    seen = P.admit((REPO, 500), 1000001, source([producer, dependent]), cwd=str(repo), write=False)
    assert seen["dependencies"]["dependents"] == [{"claim": 1000002, "session": B, "task": "T-2/b",
                                                   "acknowledged": False}]
    ack = other(1000003, P.ACK, "- Dependency of: 1000002", "- Contract: parse() returns a dict", f"- Session: {A}")
    rec = P.admit((REPO, 500), 1000002, source([producer, dependent, ack]), cwd=str(repo), write=False)
    assert rec["dependencies"]["depends_on"][0] == {"depends_on": "T-1/a", "producers": [1000001],
                                                    "state": "acknowledged",
                                                    "contract": "parse() returns a dict"}


def test_an_acknowledgment_from_someone_other_than_the_producer_does_not_count(repo):
    producer = checkin(1000001, A, "T-1/a", "`scripts/a.py`")
    dependent = checkin(1000002, B, "T-2/b", "`docs/`", depends="T-1/a")
    ack = other(1000003, P.ACK, "- Dependency of: 1000002", "- Contract: x", f"- Session: {C}")
    rec = P.admit((REPO, 500), 1000002, source([producer, dependent, ack]), cwd=str(repo), write=False)
    assert rec["dependencies"]["depends_on"][0]["state"] == "pending"


# ---------------------------------------------------------------- contribution acceptance (unsupported clients)

def test_contribution_check_passes_only_for_the_claims_own_active_session():
    comments = [checkin(1000001, A, "T-1/a", "`scripts/`")]
    ref = f"https://github.com/{REPO}/issues/500#issuecomment-1000001"
    assert P.contribution(ref, A, source(comments))["result"] == "pass"
    assert P.contribution(ref, B, source(comments))["result"] == "fail"
    assert P.contribution(ref, A, P.Source({}))["result"] == "not_run"
    assert P.contribution("https://example.com/x", A, source(comments))["result"] == "fail"


def test_the_committed_hook_settings_match_the_gate(tmp_path):
    settings = json.loads((Path(__file__).resolve().parents[2] / ".claude" / "settings.json").read_text())
    pre = settings["hooks"]["PreToolUse"]
    hooks = [h for entry in pre for h in entry["hooks"]]
    assert all(h.get("onFailure") == "block" and "participation.py" in h["command"] and h["command"].endswith(" hook")
               for h in hooks)
    matchers = " ".join(entry["matcher"] for entry in pre)
    for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "mcp__github__push_files"):
        assert tool in matchers
    resume = settings["hooks"]["SessionStart"][0]
    assert resume["matcher"] == "resume|compact" and resume["hooks"][0]["command"].endswith(" resume")


def test_a_handoff_from_someone_other_than_the_holder_moves_nothing(repo):
    comments = [checkin(1000001, A, "T-1/a", "`scripts/`"),
                other(1000002, P.HANDOFF, "- Claim: 1000001", f"- From: {C}", f"- To: {B}"),
                checkin(1000003, B, "T-1/a", "`scripts/`", accepts="1000002")]
    with pytest.raises(P.Refused, match="held by session_01AAAA"):
        P.admit((REPO, 500), 1000003, source(comments), cwd=str(repo), write=False)
    assert P.admit((REPO, 500), 1000001, source(comments), cwd=str(repo), write=False)


# ---------------------------------------------------------------- trial 3, round 1: the released-claim receipt defect

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "participation" / "issue346-trial3-round1.json"
T3A = "session_01Kucyfjt8XHfrtVsjVHMCLu"
REF = f"https://github.com/{REPO}/issues/346#issuecomment-"
WORK = ["docs/collaboration/PARTICIPATION.md", "docs/collaboration/INDEX.md"]


def replay():
    return P.Source(json.loads(FIXTURE.read_text()))


def test_the_trial_receipt_cites_authority_that_held_when_its_work_was_committed():
    """#348 cites claim 7080533127, released at 14:30:44 after its commit at 14:29:26 (the real #346 record).
    Before this fix the check failed it; it now passes as historical authority, kept apart from a current one."""
    out = P.contribution(REF + "7080533127", T3A, replay(), WORK, "2026-11-22T14:29:26Z")
    assert out["result"] == "pass" and out["assurance"] == "admitted-historical"
    assert out["lineage"][0] == {"claim": 7080533127, "state": "released", "created_at": "2026-11-22T14:25:26Z",
                                 "ended_at": "2026-11-22T14:30:44Z", "ended_by": 7080598136}
    assert [o["claim"] for o in out["lineage"]] == [7080533127, 7080595521]
    assert out["holders_now"]["docs/collaboration/INDEX.md"] == ["session_01Kucyfjwzh7cBh5aQbGwEYe"]


def test_a_released_claim_still_admits_nothing_now(repo):
    with pytest.raises(P.Refused, match="released"):
        P.admit(("dababiyoda/uniimente-kernel", 346), 7080533127, replay(), cwd=str(repo), write=False)


def test_work_committed_after_the_claim_ended_or_without_a_time_shows_no_authority():
    late = P.contribution(REF + "7080533127", T3A, replay(), WORK, "2026-11-22T14:31:00Z")
    assert late["result"] == "fail" and late["assurance"] == "none"
    untimed = P.contribution(REF + "7080533127", T3A, replay(), WORK, None)
    assert untimed["result"] == "fail"


def test_a_file_the_lineage_no_longer_covered_fails_even_while_another_claim_is_active():
    out = P.contribution(REF + "7080595521", T3A, replay(), WORK, "2026-11-22T14:35:00Z")
    assert out["result"] == "fail"
    assert out["uncovered"] == [{"file": "docs/collaboration/INDEX.md", "committed_at": "2026-11-22T14:35:00Z"}]


def test_a_receipt_repointed_at_the_narrowed_claim_still_finds_the_authority_of_its_predecessor():
    """T3-A repointed #348's receipt at its narrowed claim 7080595521, posted after the commit. The lineage
    (same session, same task and subtask) still shows the original claim covering both files at 14:29:26."""
    out = P.contribution(REF + "7080595521", T3A, replay(), WORK, "2026-11-22T14:29:26Z")
    assert out["result"] == "pass" and out["assurance"] == "admitted-historical"
    assert out["covered_by"] == {f: 7080533127 for f in WORK}


def test_another_sessions_claim_on_the_same_task_is_not_lineage():
    out = P.contribution(REF + "7080539656", T3A, replay(), WORK[1:], "2026-11-22T14:35:00Z")
    assert out["result"] == "fail" and "not session_01Kucyfjt8" in out["reason"]


def test_the_current_claim_covering_its_files_is_current_assurance():
    out = P.contribution(REF + "7080595521", T3A, replay(), WORK[:1], "2026-11-22T14:35:00Z")
    assert out["result"] == "pass" and out["assurance"] == "admitted-current"


def test_a_legacy_check_in_is_declared_coordination_not_admission():
    legacy = {"id": 6000001, "created_at": "2026-11-01T00:00:00Z", "user": {"login": "x"},
              "html_url": f"https://github.com/{REPO}/issues/96#issuecomment-6000001",
              "body": "\n".join([P.CHECKIN, "## Check-in: old work", f"- Session: {A} (test)",
                                 "- Files / interfaces: `scripts/a.py`"])}
    out = P.contribution(f"https://github.com/{REPO}/issues/96#issuecomment-6000001", A,
                         P.Source({f"{REPO}#96": [legacy]}), ["scripts/a.py"], "2026-11-02T00:00:00Z")
    assert out["result"] == "pass" and out["assurance"] == "legacy-declared"


def test_pr_contribution_judges_each_commit_and_leaves_a_stacked_dependency_to_its_own_pr(monkeypatch):
    receipt = {"version": 2, "coordination": {"task_ref": REF + "7080533127", "session_id": T3A}}
    body = "x\n<!-- uniimente:receipt -->\n```json\n" + json.dumps(receipt) + "\n```\n<!-- /uniimente:receipt -->\n"
    objects = {"repos/r/pulls/348": {"body": body, "head": {"sha": "bbb"}, "base": {"ref": "cand"}},
               "repos/r/commits/bbb": {"parents": [{}], "commit": {"committer": {"date": "2026-11-22T14:29:26Z"}},
                                       "files": [{"filename": f} for f in WORK]}}
    lists = {"repos/r/pulls/348/commits?per_page=100": [{"sha": "aaa"}, {"sha": "bbb"}],
             "repos/r/pulls?state=open&base=cand&per_page=100": [{"number": 340, "head": {"sha": "aaa"}}]}
    monkeypatch.setattr(P, "_get_obj", lambda path: (objects.get(path), "fake"))
    monkeypatch.setattr(P, "_get", lambda path: (lists.get(path), "fake"))
    out = P.pr_contribution("r", 348, replay())
    assert out["result"] == "pass" and out["assurance"] == "admitted-historical"
    assert out["attributed_to"] == {"aaa": 340}
    monkeypatch.setattr(P, "_get", lambda path: (None, "fake"))
    assert P.pr_contribution("r", 348, replay())["result"] == "not_run"
