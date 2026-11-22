"""Measure competing branch futures: which open drafts build on the converged base, which are tips,
how far the tips have diverged from each other, and which files would conflict if merged.

One GREG (INTENT-2026-09-30-OPUS-MAXIMUS-CONVERGENCE) needs this measured, not asserted. Input is a
JSON list of {"number", "sha"} (for example from the GitHub pulls API); the commits must already be
fetched. Output is JSON on stdout. Read-only: it never checks out, merges or pushes anything.

    python scripts/lineage_map.py --base <sha> --prs prs.json
    python scripts/lineage_map.py --base <destination sha> --prs prs.json --intake

--intake answers the integrator's question instead: which of each head's commits outside the destination's
history still carry text the destination lacks (equivalent patch, hunk presence, test identity, superseded in
source).

--close judges one closed PR against section 53 (run by .github/workflows/pr-close-extraction.yml):

    python scripts/lineage_map.py --base <canonical head> --close closed.json --record <placements> --inheritance <record>
"""
from __future__ import annotations

import argparse
import functools
import re
from itertools import combinations
import json
import subprocess
import sys


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def is_ancestor(a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], capture_output=True).returncode == 0


def conflicts(a: str, b: str) -> list[str]:
    """Files git would leave conflicted when merging b into a (git >= 2.38 merge-tree)."""
    out = subprocess.run(["git", "merge-tree", "--write-tree", "--name-only", "--no-messages", a, b],
                         capture_output=True, text=True)
    if out.returncode not in (0, 1):
        raise RuntimeError(out.stderr.strip())
    return [line for line in out.stdout.splitlines()[1:] if line.strip()]


def measure(base: str, prs: list[dict]) -> dict:
    shas = {int(p["number"]): p["sha"] for p in prs}
    rows = {n: {"number": n, "sha": s[:12], "contains_base": is_ancestor(base, s),
                "ahead_of_base": int(git("rev-list", "--count", f"{base}..{s}"))} for n, s in shas.items()}
    tips = sorted(n for n, s in shas.items() if not any(m != n and s != t and is_ancestor(s, t)
                                                      for m, t in shas.items()))
    pairs, unrelated = [], []
    for x, y in combinations(tips, 2):
        found = subprocess.run(["git", "merge-base", shas[x], shas[y]], capture_output=True, text=True)
        if found.returncode:                       # no common history: not a merge, a second root
            unrelated.append([x, y])
            continue
        files = conflicts(shas[x], shas[y])
        pairs.append({"tips": [x, y], f"only_{x}": int(git("rev-list", "--count", f"{shas[y]}..{shas[x]}")),
                      f"only_{y}": int(git("rev-list", "--count", f"{shas[x]}..{shas[y]}")),
                      "merge_base": found.stdout.strip()[:12],
                      "conflicting_files": len(files), "sample": files[:8]})
    return {"base": base[:12], "prs": [rows[n] for n in sorted(rows, reverse=True)], "tips": tips,
            "not_on_base": sorted(n for n, r in rows.items() if not r["contains_base"]),
            "divergent_tip_pairs": [p for p in pairs if p["conflicting_files"]],
            "unrelated_tip_pairs": unrelated,
            "reality": "measured from git objects at the given SHAs; titles, intent and quality are not judged"}


# --- Intake: is a source head's behaviour already in the destination? -----------------------------------
# Ancestry alone cannot answer this (issue #96: "do not count ancestry alone as proof that ported behavior is
# missing"). An integrator cherry-picks, hand-ports and resolves merges, so a commit outside the destination's
# history may still be fully present. Each source commit is judged on its own patch, then on its own hunks.

TRIVIAL_LINE = 4           # shorter stripped lines ("}", "),", "];") are layout, not content
MIN_HUNK_CHARS = 8          # a hunk whose added text is shorter than this ("}", "pass") proves nothing either way


@functools.lru_cache(maxsize=None)
def _blob_lines(rev: str, path: str) -> tuple[str, ...] | None:
    out = subprocess.run(["git", "show", f"{rev}:{path}"], capture_output=True)
    if out.returncode:
        return None                                # the file does not exist at that revision
    return tuple(line.strip() for line in out.stdout.decode("utf-8", "replace").splitlines())


def _has_block(haystack: tuple[str, ...], block: list[str]) -> bool:
    """True when the block's substantive lines appear in order and contiguously among the haystack's.

    Blank lines and bare punctuation ("}", "),", "else:") are dropped from both sides: they move freely when an
    integrator re-wraps code, and they carry no behaviour a reader could attribute to the source commit."""
    needle = [line for line in block if len(line) >= TRIVIAL_LINE]
    hay = [line for line in haystack if len(line) >= TRIVIAL_LINE]
    if not needle:
        return False
    first, size = needle[0], len(needle)
    return any(hay[i:i + size] == needle for i, line in enumerate(hay) if line == first)


def _hunks(sha: str) -> list[dict]:
    """The first-parent diff of one commit, as hunks of stripped added and removed lines (no context)."""
    raw = subprocess.run(["git", "diff", "-U0", "--no-renames", "--no-color", "--no-ext-diff", f"{sha}^", sha],
                         capture_output=True).stdout.decode("utf-8", "replace")
    hunks, path, current = [], None, None
    for line in raw.splitlines():
        if line.startswith("diff --git "):
            path, current = None, None
        elif line.startswith("--- ") and current is None:
            path = None if line == "--- /dev/null" else line[6:]       # a deleted file keeps its old name
        elif line.startswith("+++ ") and current is None:
            path = line[6:] if line != "+++ /dev/null" else path
        elif line.startswith("@@"):
            current = {"path": path, "added": [], "removed": []}
            hunks.append(current)
        elif current is not None and line[:1] in "+-" and not line.startswith(("+++ ", "--- ")):
            current["added" if line[0] == "+" else "removed"].append(line[1:].strip())
        elif line.startswith("Binary files") and path is None:
            hunks.append({"path": line.split(" and ")[-1].removeprefix("b/").removesuffix(" differ"),
                          "added": [], "removed": [], "binary": True})
    return [h for h in hunks if h.get("path")]


def _patch_ids(rev_range: str) -> dict[str, str]:
    """patch-id --stable -> commit, for every non-merge commit in a range."""
    log = subprocess.run(["git", "log", "-p", "--no-merges", "--no-color", "--no-ext-diff", rev_range],
                         capture_output=True).stdout
    ids = subprocess.run(["git", "patch-id", "--stable"], input=log, capture_output=True).stdout.decode()
    return {pid: commit for pid, commit in (line.split() for line in ids.splitlines() if line.strip())}


def _judge_hunk(hunk: dict, source: str, dest: str) -> str:
    if hunk.get("binary"):
        return "undecidable"
    added = [line for line in hunk["added"] if line]
    if sum(len(line) for line in added) >= MIN_HUNK_CHARS:
        if not _has_block(_blob_lines(source, hunk["path"]) or (), added):
            return "superseded"                    # the source itself rewrote this later: its head is the claim
        dest_lines = _blob_lines(dest, hunk["path"])
        if dest_lines is None:
            return "missing"
        return "present" if _has_block(dest_lines, added) else "missing"
    removed = [line for line in hunk["removed"] if line]
    if not added and sum(len(line) for line in removed) >= MIN_HUNK_CHARS:
        # A deletion is evidence only when its block still stands in the destination and is gone at the source
        # head. Its absence from the destination proves nothing: the block may never have been there.
        dest_lines = _blob_lines(dest, hunk["path"])
        if dest_lines is not None and _has_block(dest_lines, removed) and not _has_block(
                _blob_lines(source, hunk["path"]) or (), removed):
            return "missing"
    return "undecidable"


_TEST_DEF = re.compile(r"^\+\s*(?:async\s+)?def\s+(test_\w+)", re.M)


@functools.lru_cache(maxsize=None)
def _test_names(rev: str) -> frozenset[str]:
    """Every pytest function name defined anywhere in a revision's tree."""
    out = subprocess.run(["git", "grep", "-h", "-o", "-E", r"def test_[A-Za-z0-9_]+", rev, "--", "*.py"],
                         capture_output=True, text=True).stdout
    return frozenset(line.split()[-1] for line in out.splitlines())


def _added_tests(sha: str) -> set[str]:
    diff = subprocess.run(["git", "diff", "--no-color", "--no-ext-diff", f"{sha}^", sha, "--", "*.py"],
                          capture_output=True).stdout.decode("utf-8", "replace")
    return set(_TEST_DEF.findall(diff))


def intake(dest: str, source: str) -> dict:
    """Which of `source`'s commits outside `dest`'s history still carry behaviour `dest` lacks."""
    dest, source = git("rev-parse", dest), git("rev-parse", source)
    found = subprocess.run(["git", "merge-base", dest, source], capture_output=True, text=True)
    if found.returncode:
        return {"source": source[:12], "dest": dest[:12], "verdict": "UNRELATED", "commits": []}
    base = found.stdout.strip()
    if is_ancestor(source, dest):
        return {"source": source[:12], "dest": dest[:12], "merge_base": base[:12], "verdict": "CONTAINED_BY_ANCESTRY",
                "commits": [], "merges_not_judged": 0}
    dest_ids = _patch_ids(f"{base}..{dest}")
    candidates = git("rev-list", "--reverse", "--no-merges", f"{dest}..{source}").split()
    merges = int(git("rev-list", "--count", "--merges", f"{dest}..{source}"))
    source_ids = {commit: pid for pid, commit in _patch_ids(f"{dest}..{source}").items()}
    commits = []
    for sha in candidates:
        row = {"sha": sha[:12], "subject": git("log", "-1", "--format=%s", sha)[:100]}
        if source_ids.get(sha) in dest_ids:
            row.update(verdict="EQUIVALENT_PATCH", dest_commit=dest_ids[source_ids[sha]][:12])
            commits.append(row)
            continue
        judged = [(h["path"], _judge_hunk(h, source, dest)) for h in _hunks(sha)]
        tally = {k: sum(1 for _, v in judged if v == k) for k in ("present", "missing", "superseded", "undecidable")}
        added_tests = _added_tests(sha)
        present_tests = added_tests & _test_names(dest)
        if tally["missing"] and added_tests and present_tests == added_tests:
            # Second, independent signal: the text was rewritten, yet every test the commit added exists at the
            # destination under its own name. A port that kept its tests; the integrator confirms the behaviour.
            verdict = "TESTS_PRESENT"
        elif tally["missing"] and tally["present"]:
            verdict = "PARTIAL"
        elif tally["missing"]:
            verdict = "MISSING"
        elif tally["present"]:
            verdict = "CONTENT_PRESENT"
        elif tally["superseded"]:
            verdict = "SUPERSEDED_IN_SOURCE"
        else:
            verdict = "UNDECIDABLE"
        row.update(verdict=verdict, hunks=tally, tests={"added": len(added_tests), "present": len(present_tests)},
                   missing_files=sorted({p for p, v in judged if v == "missing"})[:12])
        commits.append(row)
    unported = [c["sha"] for c in commits if c["verdict"] in ("MISSING", "PARTIAL")]
    return {"source": source[:12], "dest": dest[:12], "merge_base": base[:12],
            "verdict": "UNPORTED_DELTA" if unported else "BEHAVIOUR_CONTAINED",
            "unported": unported, "merges_not_judged": merges, "commits": commits,
            "reality": "textual presence of each hunk's added lines, and of each added test by name, at the destination; "
                       "equal text is not proof of "
                       "equal behaviour, and a missing hunk may have been deliberately replaced. A lead for the "
                       "integrator, not a disposition"}


# --- Placement: every open PR gets one of section 53's twelve dispositions, from live state ----------------
# Directive 2026-10-28 section 53: "Do not rely on hard-coded PR numbers without verifying current state." The
# open-PR list comes from the caller (live `gh api`), never from a constant. A disposition is derived when the
# facts decide it, inherited from the reviewed developmental-inheritance placement, or recorded with the head it
# was decided at. Recorded judgments are revalidated against the live facts every run.

DISPOSITIONS = ("CANONICAL ACTIVE", "STACKED NEXT", "PORT MECHANISM", "REBASE", "RESTACK", "MERGE CANDIDATE",
                "FUTURE NODE", "EVIDENCE ONLY", "SUPERSEDED IMPLEMENTATION", "DEFERRED", "HISTORICAL",
                "NEEDS FOUNDER DECISION")
# "Before closing or superseding a PR, extract:" the nine items of section 53, in its order.
NINE = ("founder_intention", "intended_effect", "useful_mechanisms", "evidence", "negative_evidence",
        "remaining_capability_gap", "canonical_owner", "developmental_node", "prerequisites")
CLOSING = {"SUPERSEDED IMPLEMENTATION", "HISTORICAL", "EVIDENCE ONLY"}
# The reviewed inheritance record's ten classes, read as section-53 dispositions.
FROM_CLASS = {"ALREADY_ACHIEVED_NODE": "HISTORICAL", "CURRENT_NODE_IMPLEMENTATION": "PORT MECHANISM",
              "NEXT_NODE_INPUT": "FUTURE NODE", "FUTURE_NODE_CAPABILITY": "FUTURE NODE",
              "PORTABLE_MECHANISM": "PORT MECHANISM", "REQUIRES_ADAPTATION": "RESTACK",
              "TEMPORARILY_DEFERRED": "DEFERRED", "SUPERSEDED_IMPLEMENTATION_ASSUMPTION": "SUPERSEDED IMPLEMENTATION",
              "GENUINELY_OBSOLETE": "HISTORICAL", "HISTORICAL_EVIDENCE": "EVIDENCE ONLY"}
# A PR holding several lineages takes its most active one: closing it must not drop work still owed.
ACTIVITY = ("NEEDS FOUNDER DECISION", "PORT MECHANISM", "RESTACK", "REBASE", "MERGE CANDIDATE", "STACKED NEXT",
            "FUTURE NODE", "DEFERRED", "SUPERSEDED IMPLEMENTATION", "EVIDENCE ONLY", "HISTORICAL")
CONTAINED = ("CONTAINED_BY_ANCESTRY", "BEHAVIOUR_CONTAINED")


def _id(value):
    """A PR number, or 'branch:<name>' for a branch that has no open PR."""
    return int(value) if str(value).isdigit() else str(value)


def _order(value):
    return (isinstance(value, str), str(value).zfill(8) if isinstance(value, int) else value)


def _stacked_on(pr: dict, canonical_ref: str, by_ref: dict, verdicts: dict | None = None,
                judged: set | frozenset = frozenset()) -> str | None:
    """How ``pr`` reaches the canonical branch through its bases, or None.

    Each base is an open PR, or (given ``verdicts``) a branch whose head the canonical head already carries:
    a parent that was merged leaves its child stacked on what the canonical head holds. A base in ``judged``
    (a recorded or inherited placement) ends the walk: a child is not next while its parent awaits a judgment."""
    verdicts = verdicts or {}
    seen, current = set(), pr
    while current["base"] != canonical_ref:
        if current["number"] in seen or current["base"] not in by_ref:
            return None
        seen.add(current["number"])
        current = by_ref[current["base"]]
        if current["number"] in judged:
            return None
        if verdicts.get(current["number"]) in CONTAINED:
            return f"based on {current['ref']}, whose head {canonical_ref} already carries"
    return f"based, directly or through open PRs, on {canonical_ref}"


def _inherited(inheritance: dict) -> dict[int, dict]:
    found: dict[int, list] = {}
    for placement in inheritance.get("placements", []):
        for item in placement.get("lineage", []):
            match = re.match(r"^#(\d+)", item)
            if match:
                found.setdefault(int(match.group(1)), []).append(placement)
    result = {}
    for number, placements in found.items():
        ranked = sorted(placements, key=lambda p: ACTIVITY.index(FROM_CLASS[p["classification"]]))
        top = ranked[0]
        answers = top.get("inheritance_test") or {}
        result[number] = {"disposition": FROM_CLASS[top["classification"]], "basis": f"inherited: {top['id']} "
                          f"({top['classification']}) in the reviewed developmental-inheritance record",
                          "intended_effect": top.get("intended_effect", ""),
                          "nine_extracted": sum(1 for v in answers.values() if str(v).strip()) >= len(NINE),
                          "lineages": sorted(p["id"] for p in placements)}
    return result


def place(live: list[dict], canonical_ref: str, verdicts: dict, inheritance: dict, record: dict,
          covered_by: dict | None = None) -> dict:
    """Place every live open PR, and report what keeps the placement from being true or a close from being lawful.

    `live` is the open-PR list as read now ({number, sha, ref, base, title}); `verdicts` maps a PR to its
    `intake` verdict against the canonical head; `record` holds judgments the facts cannot make. A branch
    with no open PR (``number`` 'branch:<name>', no ``base``) whose head an open PR contains takes that PR's
    placement: ``covered_by`` maps it to those PRs."""
    by_ref = {p["ref"]: p for p in live}
    open_numbers = {p["number"] for p in live}
    inherited = _inherited(inheritance)
    recorded = {_id(r["number"]): r for r in record.get("placements", [])}
    placements, violations = [], []
    for number in sorted(recorded, key=_order):
        if number not in open_numbers:
            violations.append({"pr": number, "kind": "stale_record", "detail": "recorded PR is not open"})
    covered_by = covered_by or {}
    for pr in sorted(live, key=lambda p: _order(p["number"])):
        n, verdict = pr["number"], verdicts.get(pr["number"], "NOT_AUDITED")
        derived = None
        if pr["ref"] == canonical_ref:
            derived = ("CANONICAL ACTIVE", "head of the canonical integration branch")
        elif verdict in CONTAINED:
            derived = ("EVIDENCE ONLY", f"every commit is carried by the canonical head ({verdict})")
        elif pr.get("base") and (route := _stacked_on(pr, canonical_ref, by_ref)):
            derived = ("STACKED NEXT", route)
        elif covered_by.get(n):
            derived = ("FOLLOWS", f"its head is contained in open #{min(covered_by[n])}; placed with that PR")
        row = {"pr": n, "head": pr["sha"][:12], "title": pr.get("title", "")[:100], "intake": verdict}
        entry = recorded.get(n)
        if derived:
            row.update(disposition=derived[0], source="derived", basis=derived[1])
            if entry and entry["disposition"] != derived[0]:
                violations.append({"pr": n, "kind": "contradicted", "detail":
                                   f"recorded {entry['disposition']}, live facts say {derived[0]}: {derived[1]}"})
        elif entry:
            row.update(disposition=entry["disposition"], source="recorded", basis=entry["basis"])
            if entry.get("head_sha", "")[:12] != pr["sha"][:12]:
                violations.append({"pr": n, "kind": "moved", "detail":
                                   f"decided at {entry.get('head_sha', '')[:12]}, head is now {pr['sha'][:12]}"})
            if entry["disposition"] not in DISPOSITIONS:
                violations.append({"pr": n, "kind": "unknown_disposition", "detail": entry["disposition"]})
            if entry["disposition"] in ("CANONICAL ACTIVE", "STACKED NEXT"):
                violations.append({"pr": n, "kind": "contradicted", "detail":
                                   f"recorded {entry['disposition']}, but it is neither the canonical head nor on it"})
            if entry["disposition"] in ("PORT MECHANISM", "REBASE", "RESTACK") and verdict == "BEHAVIOUR_CONTAINED":
                violations.append({"pr": n, "kind": "contradicted", "detail": "nothing left to port: contained"})
            if entry["disposition"] == "FUTURE NODE" and not str(entry.get("node", "")).strip():
                violations.append({"pr": n, "kind": "incomplete", "detail": "FUTURE NODE names no node"})
            if entry["disposition"] == "NEEDS FOUNDER DECISION" and not str(entry.get("decision", "")).strip():
                violations.append({"pr": n, "kind": "incomplete", "detail": "names no founder decision"})
        elif n in inherited:
            row.update(disposition=inherited[n]["disposition"], source="inherited", basis=inherited[n]["basis"])
        elif pr.get("base") and (route := _stacked_on(pr, canonical_ref, by_ref, verdicts,
                                                     set(recorded) | set(inherited))):
            # Last resort, below every judgment: a stack whose merged parent left only a branch the canonical
            # head carries. A recorded or inherited placement of an older stack is never overridden by this.
            row.update(disposition="STACKED NEXT", source="derived", basis=route)
        else:
            row.update(disposition=None, source="unplaced", basis="")
            violations.append({"pr": n, "kind": "unplaced", "detail": "no fact, inherited or recorded placement"})
        nine = (entry or {}).get("nine") or {}
        filled = [k for k in NINE if str(nine.get(k, "")).strip()]
        row["close_ready"] = len(filled) == len(NINE) or (row["source"] == "inherited"
                                                           and inherited[n]["nine_extracted"])
        if entry and entry.get("closing") and not row["close_ready"]:
            violations.append({"pr": n, "kind": "close_without_extraction",
                               "detail": "missing: " + ", ".join(k for k in NINE if k not in filled)})
        placements.append(row)
    by_number = {p["pr"]: p for p in placements}
    for row in placements:                       # a covered branch takes its PR's placement, now that it is known
        if row["disposition"] == "FOLLOWS":
            owner = by_number[min(covered_by[row["pr"]])]
            row.update(disposition=owner["disposition"], basis=row["basis"] + f" ({owner['source']}: {owner['basis']})",
                       close_ready=False)
    counts = {d: sum(1 for p in placements if p["disposition"] == d) for d in DISPOSITIONS}
    return {"canonical": canonical_ref, "open": len(live), "placements": placements, "counts": counts,
            "closing_not_extracted": sorted((p["pr"] for p in placements
                                            if p["disposition"] in CLOSING and not p["close_ready"]), key=_order),
            "violations": violations,
            "reality": "placement from the open-PR list given and git facts at the canonical head; recorded and "
                       "inherited dispositions are human judgments, revalidated but not re-made here"}


def close_check(pr: dict, canonical_head: str, record: dict, inheritance: dict) -> dict:
    """Judge one closed PR: was it closed lawfully under section 53 ("Before closing or superseding a PR, extract")?

    `pr` is the closed PR as GitHub reports it ({number, sha, merged}). A merge is intake into its base, not a close.
    An unmerged close is lawful when nothing is lost (its head is in the canonical head) or when the nine items were
    extracted at the head that was closed. GitHub cannot refuse a close, so a failing verdict is detection on the
    closed PR, never prevention."""
    n, sha = _id(pr["number"]), pr["sha"]
    if pr.get("merged"):
        return {"pr": n, "verdict": "MERGED", "lawful": True, "detail": "merged into its base: intake, not a close"}
    if is_ancestor(sha, canonical_head):
        return {"pr": n, "verdict": "CONTAINED", "lawful": True,
                "detail": f"head {sha[:12]} is in the canonical head {canonical_head[:12]}: nothing is lost"}
    entry = {_id(r["number"]): r for r in record.get("placements", [])}.get(n)
    if entry:
        nine = entry.get("nine") or {}
        missing = [k for k in NINE if not str(nine.get(k, "")).strip()]
        if entry.get("head_sha", "")[:12] != sha[:12]:
            return {"pr": n, "verdict": "MOVED_SINCE_EXTRACTION", "lawful": False,
                    "detail": f"extracted at {entry.get('head_sha', '')[:12]}, closed at {sha[:12]}; "
                              "the commits after the extraction are unaccounted for"}
        if not missing:
            return {"pr": n, "verdict": "EXTRACTED", "lawful": True,
                    "detail": f"recorded {entry['disposition']} with all nine items at {sha[:12]}"}
    else:
        missing = list(NINE)
    inherited = _inherited(inheritance).get(n)
    if inherited and inherited["nine_extracted"]:
        return {"pr": n, "verdict": "EXTRACTED_INHERITED", "lawful": True,
                "detail": f"the developmental-inheritance record answers all nine for #{n}"}
    return {"pr": n, "verdict": "CLOSED_WITHOUT_EXTRACTION", "lawful": False,
            "detail": "missing: " + ", ".join(missing) + ". Reopen the PR, or record its nine items in "
                      "docs/collaboration/KERNEL-PR-PLACEMENTS.json at this head"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True)
    parser.add_argument("--prs", help="JSON file: [{number, sha}, ...]")
    parser.add_argument("--intake", action="store_true",
                        help="judge each PR head's commits for behaviour missing from --base (the destination)")
    parser.add_argument("--place", action="store_true",
                        help="place every PR in --prs (read live: number, sha, ref, base, title) by section 53")
    parser.add_argument("--canonical-ref", help="--place: the canonical integration branch")
    parser.add_argument("--record", type=argparse.FileType(), help="--place: recorded placements")
    parser.add_argument("--inheritance", type=argparse.FileType(), help="--place: developmental inheritance record")
    parser.add_argument("--intake-json", type=argparse.FileType(),
                        help="--place: a saved --intake run against --base, instead of recomputing it")
    parser.add_argument("--close", help="judge one closed PR: JSON file {number, sha, merged}; --base is the "
                                        "canonical head; uses --record and --inheritance")
    args = parser.parse_args(argv)
    if args.close:
        with open(args.close) as handle:
            closed = json.load(handle)
        result = close_check(closed, git("rev-parse", args.base), json.load(args.record) if args.record else {},
                             json.load(args.inheritance) if args.inheritance else {})
        json.dump(result, sys.stdout, indent=1)
        print()
        return 0 if result["lawful"] else 1
    if not args.prs:
        parser.error("--prs is required unless --close is given")
    with open(args.prs) as handle:
        prs = json.load(handle)
    base = git("rev-parse", args.base)
    if args.place:
        if args.intake_json:
            saved = json.load(args.intake_json)
            if git("rev-parse", saved["dest"]) != base:
                raise SystemExit("--intake-json was computed against another head")
            verdicts = {_id(p["number"]): p["verdict"] for p in saved["prs"]}
        else:
            verdicts = {_id(p["number"]): intake(base, p["sha"])["verdict"] for p in prs}
        # A branch entry ('branch:<name>') with no open PR is placed with any open PR that contains its head.
        heads = [(p["number"], p["sha"]) for p in prs if not str(p["number"]).startswith("branch:")]
        covered = {p["number"]: [n for n, sha in heads if is_ancestor(p["sha"], sha)]
                   for p in prs if str(p["number"]).startswith("branch:")
                   and verdicts.get(_id(p["number"])) not in CONTAINED}          # contained branches are derived
        result = place(prs, args.canonical_ref, verdicts, json.load(args.inheritance) if args.inheritance else {},
                       json.load(args.record) if args.record else {}, covered)
        json.dump({"base": base[:12], **result}, sys.stdout, indent=1)
        print()
        return 1 if result["violations"] else 0
    if args.intake:
        result = {"dest": base[:12], "prs": [{"number": _id(p["number"]), **intake(base, p["sha"])} for p in prs]}
    else:
        result = measure(base, prs)
    json.dump(result, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
