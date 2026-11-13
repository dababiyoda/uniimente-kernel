"""The work map reads receipts exactly, resolves board authors conservatively, and never gates or locks."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import work_map as w  # noqa: E402

A = "session_01FBS4KNJR59nSbdGbxo8Mbx"
B = "session_01Kucyfoabgsg6W8H8xj4qea"
C = "session_01PwqafNDa4MExng4LG5kye6"
NOW = datetime(2026, 11, 13, 2, 0, tzinfo=timezone.utc)
LINE = w.LINE

# Trimmed real work-board comments (issue #96). The numbers are their comment ids.
CLAIM_6648378926 = f"""## Claim: the directive pin ratchet refuses an ask closed without new evidence · `{A}` · 2026-11-05

**Why now.** Several sessions close directive asks in parallel; `{C}` raised met from 77 to 78 in #257.

**Scope (owned):** `acceptance/directive.py`, plus `tests/unit/test_directive_sections.py`. Not `acceptance/directive-sections.json`.
"""
CODEX_6841194389 = f"""## Bounded claim: one discoverable full-machine context route

- **Implementer:** Codex `/root`, workspace `5bcf356971dc`, task `context-route-20261112`.
- **Founder request, 2026-11-12 (America/New_York):** every entrant can find the necessary context and work in parallel.
- **Bounded scope:** additive navigation in `AGENTS.md`, `docs/BACKCAST_GPS.md`. Runtime and `greg/path.json` are read-only.
- **Reviewer / integrator:** `{A}`
- **Claim recheck:** 2026-11-13T03:30:00Z
"""
KIMI_6735108906 = """## Bounded claim: canonical WP-06 measurement/audit port (A2)

- **Task / intended observable outcome:** port the WP-06 audit; see `docs/collaboration/deliberation-kimi-wp06-port-20261109.json`.
- **Implementer:** Kimi K3.1, `kimi-a2-20261109-01`.
- **Files / interfaces claimed:** additive `evolution/README.md`; `evolution/repair/` stays read-only.
- **Claim recheck:** 2026-11-09T12:00:00Z, and immediately before any overlapping edit.
"""
RELAY_6670909400 = """<!-- uniimente:receipt -->
**Handoff — #279 review (UAT / Hegemony)** · 2026-11-05 ~5:15 PM ET

Reviewed draft #279 at `45f82a8f` only (agent [bc-8e2ec3d3](https://cursor.com/agents/bc-8e2ec3d3-35bd-5620-9565-eaf75cca3f8e)).
"""
NOTE_6657787629 = f"""**For the #196 integrator (`{A}`): Canonical CI job 1 is now at its limit on the base.** From `{B}`, 2026-11-05.
"""
OPENING_6794587797 = f"""## Claim: the Kernel denies execution of a capability that is not ATTACHED

Session `{B}`. The proposal had no reply for five days.

- **Files:** `greg/authority.py`
"""
HANDOFF_6795485396 = "**Handoff: claim 6794587797 released into draft PR #290.**\n\n- **PR:** #290\n"
CLAIM_HANDOFF_6664831144 = """## Claim / handoff: fix round for #240 resource bounds (stacked draft child)

- **Outcome:** Canonical CI jobs 1 and 9 on #240 both fail with `PassportError: live passport ceiling reached`.
- **Files:** `identity/machine_passport.py`, `greg/authority.py`, `tests/unit/test_resource_bounds.py`.
- **Not touched:** `policy/consequence_gate.py`.
"""
DIGEST_6673874794 = """<!-- uniimente:receipt -->
**UAT status + claims (Hegemony GREG build loop)** · 2026-11-05 ~8:10 PM ET

**Live truth**
- #196 head moved; scout bc-3ff94317 reports #279 green.
"""
MARKED_CLAIM = ("<!-- UNIIMENTE-KIMI-REVIEW-OWNERSHIP-20261111 -->\n## Bounded claim: ownership by concern\n\n"
                "- **Agent / claim:** Kimi K3.1, `kimi-weekly-review-ownership-20261111`.\n"
                "- **Files:** `scripts/repo_review.py`\n")
MARKED_STOP = ("<!-- UNIIMENTE-KIMI-REVIEW-OWNERSHIP-20261111 -->\n## Correction and recovery stop\n\n"
               "Delivery under claim `6796102804` is stopped.\n")


def _receipt(session: str | None, files: list[str], task: str = "https://example.invalid/t", **extra) -> str:
    coord = {"task_ref": task, "files": files, "interfaces": [], "recheck_at": "2026-11-13T04:00:00Z",
             "overlap": {"status": extra.get("overlap", "clear"), "inspected_refs": ["x"], "acknowledgment_refs": []}}
    if session:
        coord["session_id"] = session
    data = {"version": 2, "intent_refs": extra.get("intent_refs", ["INTENT-X"]), "scope": "s", "coordination": coord}
    return f"text\n\n{w.MARKER}\n```json\n{json.dumps(data)}\n```\n<!-- /uniimente:receipt -->\n"


def _pr(number: int, head: str, base: str = LINE, body: str = "", title: str = "t", updated="2026-11-12T10:00:00Z"):
    return {"number": number, "state": "open", "draft": True, "title": title, "body": body, "updated_at": updated,
            "head": {"ref": head, "sha": "0" * 40}, "base": {"ref": base}}


def _comment(cid: int, body: str, at: str = "2026-11-12T12:00:00Z") -> dict:
    return {"id": cid, "created_at": at, "body": body}


def test_receipt_is_read_exactly_and_a_marker_without_json_is_none():
    r = w.receipt_of(_receipt(A, ["greg/missions.py"]))
    assert r["coordination"]["session_id"] == A
    assert w.receipt_of(RELAY_6670909400) is None          # the marker misused on a comment: no crash, no receipt
    assert w.receipt_of("no receipt here") is None
    assert w.receipt_of(f"{w.MARKER}\n```json\n{{broken\n```") is None


def test_identities_are_canonical_and_a_file_name_is_not_a_session():
    assert w.canonical_identity(A) == (A, "claude")
    assert w.canonical_identity("codex-root-5bcf356971dc") == ("codex:5bcf356971dc", "codex")
    assert w.canonical_identity("bc-8e2ec3d3-35bd-5620-9565-eaf75cca3f8e") == ("bc-8e2ec3d3", "cursor")
    assert w.canonical_identity("codex/root/mandatory-collaboration-20261030")[1] == "codex"   # kept verbatim
    assert w.canonical_identity(None) == (None, "unknown")
    assert [i[1] for i in w.identities("see docs/deliberation-kimi-wp06-port-20261109.json")] == []


def test_author_comes_from_the_heading_or_a_labelled_line_never_the_first_id():
    assert w.comment_author(CLAIM_6648378926)["author"] == A            # C is only mentioned in the body
    codex = w.comment_author(CODEX_6841194389)
    assert (codex["author"], codex["how"], codex["addressees"]) == ("codex:5bcf356971dc", "label", [A])
    assert w.comment_author(KIMI_6735108906)["author"] == "kimi-a2-20261109-01"
    note = w.comment_author(NOTE_6657787629)
    assert (note["author"], note["addressees"]) == (B, [A])            # "For ... (A)" is the addressee
    assert w.comment_author(OPENING_6794587797)["how"] == "opening line"
    relay = w.comment_author(RELAY_6670909400)
    assert (relay["author"], relay["team"]) == (None, "UAT")           # a team relay is a label, not an identity


def test_fields_files_recheck_and_stops():
    tracked = {"acceptance/directive.py", "tests/unit/test_directive_sections.py",
               "acceptance/directive-sections.json", "AGENTS.md", "docs/BACKCAST_GPS.md", "greg/path.json",
               "evolution/README.md", "evolution/repair/x.py", "scripts/repo_review.py"}
    dirs = {"acceptance", "tests", "tests/unit", "docs", "greg", "evolution", "evolution/repair", "scripts"}
    claim = w.parse_comment(_comment(1, CLAIM_6648378926), tracked, dirs)
    assert claim["kind"] == "claim"
    assert claim["files"] == ["acceptance/directive.py", "tests/unit/test_directive_sections.py"]   # "Not ..." dropped
    codex = w.parse_comment(_comment(2, CODEX_6841194389), tracked, dirs)
    assert codex["files"] == ["AGENTS.md", "docs/BACKCAST_GPS.md"]      # the read-only sentence is not a claim
    assert codex["recheck"] == "2026-11-13T03:30:00Z"
    assert codex["prompt"].startswith("every entrant") and codex["plan"] == "" and codex["route"] is None
    kimi = w.parse_comment(_comment(3, KIMI_6735108906), tracked, dirs)
    assert kimi["files"] == ["evolution/README.md"] and kimi["recheck"] == "2026-11-09T12:00:00Z"
    assert w.parse_comment(_comment(4, MARKED_STOP), tracked, dirs)["stops"] == ["6796102804"]
    assert w.parse_comment(_comment(5, HANDOFF_6795485396), tracked, dirs)["releases"] == ["6794587797"]
    filled = (w.CHECKIN_BLOCK.replace("N3 | P5 | <unit id> | process", "WU-11")
              .replace("<actual session or task id> (<client>)", f"`{A}` (Claude Code)")
              .replace("<paths in backticks>; read-only: <...>", "`greg/path.json` is read-only; `AGENTS.md`"))
    block = w.parse_comment(_comment(6, filled), tracked, dirs)
    assert block["is_checkin"] and block["kind"] == "check-in" and block["route"] == "WU-11"
    assert (block["author"], block["how"]) == (A, "label") and block["files"] == ["AGENTS.md"]
    assert block["prompt"] and block["plan"] and block["guidance"]
    both = w.parse_comment(_comment(7, CLAIM_HANDOFF_6664831144), tracked | {
        "identity/machine_passport.py", "greg/authority.py", "tests/unit/test_resource_bounds.py",
        "policy/consequence_gate.py"}, dirs | {"identity", "policy"})
    assert both["kind"] == "claim+handoff" and both["author"] is None        # no identity stated: unresolved
    assert both["files"] == ["identity/machine_passport.py", "greg/authority.py", "tests/unit/test_resource_bounds.py"]
    digest = w.parse_comment(_comment(8, DIGEST_6673874794), tracked, dirs)
    assert (digest["author"], digest["team"]) == (None, "UAT")               # a mentioned agent is not the author


def test_contention_needs_two_sessions_and_leaves_out_the_integration_pr():
    prs = [
        _pr(1, "a/one", body=_receipt(A, ["greg/missions.py", "greg/body.py"])),
        _pr(2, "a/two", base="a/one", body=_receipt(A, ["greg/missions.py"])),      # A's own stack
        _pr(3, "b/one", body=_receipt(B, ["greg/missions.py"])),
        _pr(4, LINE, base="older-trunk", body=_receipt(C, ["greg/missions.py", "greg/body.py"])),   # the line itself
        _pr(5, "candidate/composed", body=_receipt(C, ["greg/body.py"])),           # a composed candidate
        _pr(6, "old/work", base="main", body=_receipt(C, ["greg/body.py"])),        # not headed for the line
    ]
    rows = w.pr_rows(prs, ROOT, use_git=False)
    assert sorted(r["pr"] for r in w.line_bound(rows)) == [1, 2, 3]
    got = w.contended(rows)
    assert [(c["file"], c["sessions"], c["prs"]) for c in got] == [("greg/missions.py", 2, [1, 2, 3])]


def test_who_touches_matches_files_and_directory_prefixes():
    rows = w.pr_rows([_pr(1, "a/one", body=_receipt(A, ["greg/cognition/"])),
                      _pr(2, "b/one", body=_receipt(B, ["greg/missions.py"]))], ROOT, use_git=False)
    hit = w.who_touches(["greg/cognition/compiler.py", "greg/missions.py", "README.md"], rows, [])
    assert [[p["pr"] for p in h["prs"]] for h in hit] == [[1], [2], []]


def test_build_joins_authors_names_owners_and_counts_gaps():
    claim_url = "https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6794587797"
    prs = [_pr(290, "b/authority", body=_receipt(B, ["greg/authority.py"], task=claim_url),
               title="WU-11: every built candidate is attacked before it registers"),
           _pr(7, "x/none", body="no receipt")]
    comments = [_comment(6794587797, OPENING_6794587797), _comment(6795485396, HANDOFF_6795485396),
                _comment(6796102804, MARKED_CLAIM), _comment(6796931006, MARKED_STOP),
                _comment(6670909400, RELAY_6670909400), _comment(6841194389, CODEX_6841194389)]
    m = w.build(prs, comments, now=NOW, use_git=False)
    assert m["authority"] == "none"
    unit = next(u for u in m["units"] if u["unit"] == "WU-11")
    assert unit["state"] == "claimed" and unit["owners"][0]["pr"] == 290
    assert {u["state"] for u in m["units"]} <= {"claimed", "waits", "unclaimed"}
    by_session = {s["session"]: s for s in m["sessions"]}
    assert by_session[B]["prs"] == [290] and by_session[B]["comments"] == 2      # the handoff joined its claim
    assert by_session["kimi-weekly-review-ownership-20261111"]["comments"] == 2  # the stop joined by its marker
    assert by_session["codex:5bcf356971dc"]["prompt"]
    unresolved = [g["comment"] for g in m["gaps"]["recent_posts_unresolved"]]
    assert unresolved == [6670909400]                                            # listed, not guessed
    assert m["gaps"]["open_prs_without_receipt"] == [7]
    assert m["gaps"]["live_sessions_stating_plan"] == 0                          # nobody states a plan yet
    claims = {c["comment"]: c for c in m["claims"]}
    assert claims[6794587797]["has_pr"] and claims[6796102804]["state"] == "stopped"
    assert [c["comment"] for c in m["claims_without_pr"]] == [6841194389]


def test_position_reads_the_existing_sources():
    pos = w.position(ROOT)
    assert pos["route"]["acceptance_node"]["id"].startswith("N")
    assert pos["route"]["boundary"].startswith("BODY + ORGANS + MIND")
    assert pos["directive"]["summary"]["sections"] == 77 and not pos["directive"]["ran_tests"]
    assert pos["foundry"]["complete"].endswith("/55")


def test_route_drift_expands_ranges(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "BACKCAST_GPS.md").write_text(
        "# x\n\n## Current full-machine route\n\n| N0 | a |\n| N1 | b |\n| P0–P2 | c |\n\n## Preserved July\n\nN9 P9\n")
    route = {"nodes": ["N0", "N1", "N2"], "mind_nodes": ["P0", "P1", "P2", "P3"]}
    assert w.route_drift(tmp_path, route) == {"section": True, "missing": ["N2", "P3"]}
    (tmp_path / "docs" / "BACKCAST_GPS.md").write_text("# old\n")
    assert w.route_drift(tmp_path, route)["section"] is False


def test_activity_is_decided_by_time_since_last_seen():
    assert w.activity("2026-11-12T12:00:00Z", NOW) == "ACTIVE"
    assert w.activity("2026-11-08T12:00:00Z", NOW) == "QUIET"
    assert w.activity("2026-10-01T12:00:00Z", NOW) == "DORMANT"
    assert w.activity(None, NOW) == "UNKNOWN"


def test_markdown_says_what_it_is_and_carries_the_check_in():
    text = w.markdown(w.build([_pr(1, "a/one", body=_receipt(A, ["greg/missions.py"]))], [], now=NOW, use_git=False))
    assert "A snapshot, not a lock, and no authority" in text
    assert "## 2. Next eligible work, in dependency order" in text
    assert w.CHECKIN in text and "- Prompt:" in text and "- Plan:" in text and "- Route:" in text


def test_cli_writes_only_the_named_files_and_exits_zero_offline(tmp_path):
    out = tmp_path / "map.json"
    assert w.main(["--json", str(out)]) == 0
    assert json.loads(out.read_text())["sources"]["open_prs"] == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["map.json"]


def test_line_checks_say_what_covers_pushes_to_the_line(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "canonical-ci.yml").write_text("on:\n  pull_request:\n  push:\n    branches: [main]\n")
    carrier = w.pr_rows([_pr(196, LINE, base="older-trunk")], ROOT, use_git=False)
    assert w.line_checks(carrier, tmp_path) == {"push_branches": ["main"], "pull_requests_with_line_as_head": [196],
                                                "covered": True}
    assert w.line_checks([], tmp_path)["covered"] is False          # #196 closed and no push filter: nothing runs
    (wf / "canonical-ci.yml").write_text(f"on:\n  push:\n    branches: [main, {LINE}]\n")
    assert w.line_checks([], tmp_path)["covered"] is True
    text = w.markdown(w.build([_pr(196, LINE, base="older-trunk", body=_receipt(A, ["greg/body.py"]))], [], now=NOW,
                              use_git=False))
    assert "only through the pull-request runs of #196" in text


def test_receipts_from_real_pull_requests_exact_missing_session_and_absent():
    # PR #312: a complete receipt. PR #241: a version-2 receipt with no session_id. PR #268: no receipt at all.
    task = "https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6812373792"
    files = ["greg/missions.py", "tests/unit/test_greg_alternative_route.py", ".github/workflows/canonical-ci.yml"]
    prs = [_pr(312, "claude/alternative-route", body=_receipt("session_01Kucyfm9exT5imDVYvHTYSv", files, task=task,
                                                               overlap="blocked")),
           _pr(241, "codex/enrollment", body=_receipt(None, ["tests/harness/fake_contents_gh.py"])),
           _pr(268, "claude/old", base="main", body="> **Superseded by #271. Do not merge this PR alongside it.**")]
    rows = {r["pr"]: r for r in w.pr_rows(prs, ROOT, use_git=False)}
    assert (rows[312]["session"], rows[312]["files"], rows[312]["overlap"], rows[312]["task_ref"]) == (
        "session_01Kucyfm9exT5imDVYvHTYSv", files, "blocked", task)
    assert rows[241]["receipt"] and rows[241]["session"] is None           # reported as missing, no crash
    assert not rows[268]["receipt"] and rows[268]["session"] is None
    m = w.build(prs, [], now=NOW, use_git=False)
    assert m["gaps"]["open_prs_without_receipt"] == [268]
    assert [s["session"] for s in m["sessions"]] == ["session_01Kucyfm9exT5imDVYvHTYSv"]


def test_markdown_follows_the_six_sections_and_names_the_engineering_target():
    text = w.markdown(w.build([], [], now=NOW, use_git=False))
    heads = [line for line in text.splitlines() if line.startswith("## ")]
    assert heads == ["## 1. Position", "## 2. Next eligible work, in dependency order",
                     "## 3. Before you edit: contended files", "## 4. Active sessions",
                     "## 5. Gaps: documented is not demonstrated", "## 6. Route drift", "## The check-in",
                     "## Check-in: <one-line outcome>"]                     # the last is the block itself
    assert "| Engineering target | a useful mission" in text and "not a measured result" in text
