"""Cathedral detector: the constitution's "cathedral" kill condition, computed from git history and the ledger.

constitution/constitution.ucl, kill_condition "cathedral": "activity rises while external outcomes remain unchanged,
or the Kernel adds more cost than control", then "suspend_expansion_and_escalate(alfonso)". The compiler parses it
(compiler/ucl_compiler.py ``kill_conditions``); until now nothing evaluated it. Directive 2026-10-28 section 55: when
architectures, documents, PRs and subsystems grow while founder usability, verified mission closures, external effect
and real business loops stay flat, STOP HORIZONTAL EXPANSION and converge.

This computes the first clause over one window [since, until):

* activity, from git objects only, never from what markdown says: the commits on HEAD whose committer time falls in
  the window, the PR-like merges among them, and the files they added (.md, .py, evidence READMEs). A rename is not a
  new file. Replace refs are ignored, so a graft cannot cut the history counted;
* outcomes, from a body's ledger only, at the founder tier only, on the founder's designated body only: closures of
  missions signed at the founder tier (greg/metrics.py ``founder_tier``) and registered after a founder-signed
  BODY_DESIGNATE named the body the first founder body (VEPMC's ``founder_body`` condition), VEPMC's
  ``founder_tier_count`` and the nodes achieved on the founder's path (greg/path.py ``position``). Each is read on the
  ledger as it stood at ``since`` and at ``until`` (a prefix of the append-only ledger) and the two are compared;
* vertical progress, beside the outcomes and never counted as one: the build frontier, the nodes built and the
  structural depth (greg/path.py ``build_status``) at both ends. A test key, a fixture or a rehearsal moves the build
  frontier and never an outcome (``greg.path.BUILD_RULE``).

Verdicts: CATHEDRAL when activity reached its floor (``THRESHOLDS``, scaled to the window by ``floors``) while no
outcome moved; NOT_CATHEDRAL when an outcome moved or activity stayed under every floor; INSUFFICIENT_HISTORY when
either history cannot decide:

* git cannot show the window in full: a shallow clone (reported with its depth and no counts), a grafts file, no
  repository;
* no body ledger was read: the outcomes are unmeasured, never assumed flat;
* the ledger does not cover the window as the founder's body: it begins after the window ends, it carries no
  founder-signed designation, or the designation came after the window started and no outcome moved since (outcomes
  before it are on no ledger read here, so "unchanged" is not shown for the whole window). An outcome that moved
  inside the covered part decides NOT_CATHEDRAL.

Not computed here: the second clause ("the Kernel adds more cost than control"), and the section-55 outcomes outside
the founder's ledger: real business loops beyond the path's nodes (venture revenue in greg/venture_books.py is not
read), external effect, and founder usability beyond the nodes achieved.

Read-only and inert: the ledger is read through the caller's read-only journal (``greg.body.observe``) and copied into
memory for the window's start; git is only read. It writes no history, raises no founder ask, pauses nothing and
grants nothing. The constitutional response it names is the founder's to take.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import os
from pathlib import Path
import re
import subprocess

from greg import metrics
from greg import path as devpath
from greg.journal import Journal

KERNEL_ROOT = Path(__file__).resolve().parents[1]
CATHEDRAL, NOT_CATHEDRAL, INSUFFICIENT_HISTORY = "CATHEDRAL", "NOT_CATHEDRAL", "INSUFFICIENT_HISTORY"

# Every declared threshold, in one place. Activity rose when any one measure reaches its floor inside the window;
# an outcome moved when any one founder-tier measure grew between the window's start and its end.
THRESHOLDS = {
    "window_days": 30,
    "activity_floor": {"commits": 20, "pr_like_merges": 5, "new_md": 10, "new_py": 10, "new_evidence_readmes": 3},
    "floor_scaling": "each floor is per window_days; a longer window scales it up by days / window_days (rounded up), "
                     "a shorter one keeps it, so a longer window never makes steady activity read as risen",
    "outcome_moved_when_any_grew": ["founder_tier_closures", "vepmc_founder_tier_count", "achieved_nodes"],
}
ACTIVITY_RULE = ("git objects only: commits on HEAD with committer time in [since, until); a PR-like merge has more "
                 "than one parent or a GitHub merge subject ('Merge pull request #N', '... (#N)'); new files are paths "
                 "the window's commits added (renames detected, so a move is not new), counted once each; an evidence "
                 "README is a README.md under a directory named evidence")
OUTCOME_RULE = ("founder tier only, on the founder's designated body only, read on the body's ledger at the window's "
                "start and end: a closure counts when its mission was signed at the founder tier "
                "(greg.metrics.founder_tier) and registered after a founder-signed BODY_DESIGNATE named this body the "
                "first founder body (VEPMC's founder_body condition); VEPMC counts founder_tier_count; the founder's "
                "path counts its achieved nodes (greg.path.position). Test-key, fixture and rehearsal closures never "
                "count. The founder tier is the key holder's claim of passphrase custody (greg.metrics.CUSTODY_CLAIM), "
                "so this inherits that residual")
COVERAGE_RULE = ("the outcomes cover the window from the founder-signed designation on: a ledger that begins after the "
                 "window ends or carries no designation measures nothing of the founder's, and one designated after "
                 "the window starts cannot show 'unchanged' for the whole window (an outcome that moved still decides)")
VERTICAL_RULE = ("reported beside the outcomes and never counted as one: " + devpath.BUILD_RULE)
NO_LEDGER = ("no body ledger was read, so founder-tier closures, VEPMC and the founder's path are unmeasured and never "
             "assumed flat: pass --body (the body at --home) or --body HOME")
INERT = ("this report writes nothing, raises no founder ask, pauses nothing and grants nothing; the constitutional "
         "response is the founder's")
PR_SUBJECT = re.compile(r"^Merge pull request #\d+|\(#\d+\)\s*$")


class CathedralError(ValueError):
    pass


def floors(days: float) -> dict:
    """The activity floors for a window of ``days``: see THRESHOLDS["floor_scaling"]."""
    scale = max(1.0, days / THRESHOLDS["window_days"])
    return {k: math.ceil(round(floor * scale, 9)) for k, floor in THRESHOLDS["activity_floor"].items()}


def kill_condition(root: Path = KERNEL_ROOT) -> dict:
    """The constitution's own words for the condition, read through the compiler that parses them."""
    from compiler.ucl_compiler import compile_constitution
    compiled = compile_constitution(str(root))
    return {"name": "cathedral", **compiled.kill_conditions["cathedral"], "source": "constitution/constitution.ucl",
            "evaluated_here": "the first clause (activity against founder-tier outcomes); not the cost-control clause"}


def window(*, since: datetime | str | None = None, until: datetime | str | None = None, days: float | None = None,
           now: datetime | None = None) -> tuple[datetime, datetime]:
    """[since, until) in UTC. ``until`` defaults to now, ``since`` to ``until`` minus ``days`` (default 30)."""
    def moment(value, name):
        if value is None or isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                raise CathedralError(f"--{name} is not an ISO 8601 time: {value!r}") from None
        if parsed is not None and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return None if parsed is None else parsed.astimezone(timezone.utc)
    if days is not None and since is not None:
        raise CathedralError("give --since or --days, not both")
    try:                    # a moment or a span past the calendar's range is refused, never a traceback
        end = moment(until, "until") or (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        start = moment(since, "since")
        if start is None:
            span = THRESHOLDS["window_days"] if days is None else days
            if not span > 0:
                raise CathedralError("--days must be positive")
            start = end - timedelta(days=span)
    except (OverflowError, ValueError) as exc:
        if isinstance(exc, CathedralError):
            raise
        raise CathedralError(f"the window is outside the representable calendar: {exc}") from None
    if not start < end:
        raise CathedralError("the window must start before it ends")
    return start, end


# -- activity, from git objects -----------------------------------------------------------------------

def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    # GIT_OPTIONAL_LOCKS=0: a status-like read must not refresh the index or take a lock. GIT_NO_REPLACE_OBJECTS=1: a
    # replace ref (git replace --graft) cannot cut or rewrite the history counted. A path that is not UTF-8 is read
    # with surrogate escapes. A missing git or a read that times out is a failed read (returncode 127), reported as
    # incomplete history, never a crash.
    argv = ["git", "-C", str(repo), "-c", "core.quotepath=off", "-c", "log.showSignature=false", *args]
    try:
        return subprocess.run(argv, capture_output=True, encoding="utf-8", errors="surrogateescape", timeout=300,
                              env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C",
                                   "GIT_NO_REPLACE_OBJECTS": "1"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 127, "", f"{type(exc).__name__}: {exc}")


def activity(repo: Path | str, since: datetime, until: datetime) -> dict:
    """What the window's commits on HEAD did, from git objects; ``complete`` False (and no counts) when git cannot
    show the window in full."""
    repo = Path(repo)
    out = {"repository": str(repo), "rule": ACTIVITY_RULE}
    if _git(repo, "rev-parse", "--is-inside-work-tree").returncode != 0:
        return {**out, "complete": False, "counts": None,
                "why": f"{repo} is not a git repository, or git could not be run there"}
    if _git(repo, "rev-parse", "--is-shallow-repository").stdout.strip() == "true":
        depth = _git(repo, "rev-list", "--count", "HEAD").stdout.strip()
        return {**out, "complete": False, "shallow": True, "depth": int(depth) if depth.isdigit() else None,
                "counts": None,
                "why": f"shallow clone: only {depth or 'an unknown number of'} commits are reachable from HEAD, so the "
                       "window's activity cannot be counted in full and no count is given"}
    grafts = _git(repo, "rev-parse", "--git-path", "info/grafts").stdout.strip()
    if grafts and (repo / grafts).is_file():                    # git honours it even with replace refs ignored
        return {**out, "complete": False, "shallow": False, "grafts": str(repo / grafts), "counts": None,
                "why": f"a grafts file ({grafts}) rewrites the parents git shows, so the window's history is not the "
                       "repository's and no count is given"}
    replaced = _git(repo, "for-each-ref", "--format=%(refname)", "refs/replace/").stdout.split()
    head = _git(repo, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if head.returncode != 0:                                    # a repository with no commit yet: nothing happened
        commits = []
        added = {}
    else:
        listing = _git(repo, "log", "--no-color", "--format=%H%x1f%P%x1f%ct%x1f%s", "HEAD")
        files = _git(repo, "log", "-z", "--no-color", "--no-ext-diff", "-M", "--diff-filter=A", "--name-status",
                     "--format=%x1e%H", "HEAD")
        if listing.returncode != 0 or files.returncode != 0:
            return {**out, "complete": False, "counts": None,
                    "why": f"git log failed: {(listing.stderr or files.stderr).strip()[:300]}"}
        low, high = since.timestamp(), until.timestamp()
        commits = []
        for line in listing.stdout.splitlines():
            sha, parents, stamp, subject = (line.split("\x1f", 3) + ["", "", "", ""])[:4]
            if stamp.isdigit() and low <= int(stamp) < high:
                commits.append({"sha": sha, "parents": len(parents.split()), "subject": subject})
        inside = {c["sha"] for c in commits}
        added = {}
        for chunk in files.stdout.split("\x1e")[1:]:
            tokens = chunk.split("\0")
            sha, rest = tokens[0].strip(), tokens[1:]
            if sha not in inside:
                continue
            for status, path in zip(rest[0::2], rest[1::2]):
                if status.strip() == "A" and path:
                    added.setdefault(path, sha)
    paths = sorted(added)
    counts = {
        "commits": len(commits),
        "pr_like_merges": sum(c["parents"] > 1 or bool(PR_SUBJECT.search(c["subject"])) for c in commits),
        "new_md": sum(p.endswith(".md") for p in paths),
        "new_py": sum(p.endswith(".py") for p in paths),
        "new_evidence_readmes": sum(Path(p).name == "README.md" and "evidence" in Path(p).parts[:-1] for p in paths),
    }
    applied = floors((until - since).total_seconds() / 86400)
    crossed = [k for k, floor in applied.items() if counts[k] >= floor]
    return {**out, "complete": True, "shallow": False, "replace_refs_ignored": len(replaced),
            "head": head.stdout.strip() if head.returncode == 0 else None,
            "counts": counts, "floors_applied": applied, "rose": bool(crossed), "floors_reached": crossed}


# -- outcomes and vertical progress, from the ledger ----------------------------------------------------

def _at(stamp: str) -> datetime:
    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).astimezone(timezone.utc)


def as_of(journal: Journal, moment: datetime) -> Journal:
    """The ledger as it stood at ``moment``: its records before the first one retained at or after it, in memory.

    The ledger is append-only and hash-chained, so a prefix is a verified history of its own (it is re-verified
    here). The genesis record is always kept; it is no outcome. Nothing is written anywhere."""
    from events.spine import EventSpine
    from provenance.ledger import EvidenceLedger
    records = journal.ledger.records
    cut = next((i for i, r in enumerate(records) if _at(r.ts_utc) >= moment), len(records))
    snapshot = EvidenceLedger(journal.ledger.constitution_hash)
    snapshot.records = records[:max(cut, 1)]
    return Journal(EventSpine(snapshot), actor=journal.actor)


def founder_body(journal: Journal) -> dict | None:
    """The founder-signed first-body designation on this ledger, as greg.metrics.vepmc reads it: a body.designated
    record for first_founder_body whose BODY_DESIGNATE command was accepted as signed by the founder key. ``seq`` and
    ``at`` are those of the command's acceptance. None when the ledger carries none."""
    records = {r.payload.get("event_id"): r for r in journal.ledger.by_type("event")}
    accepted = {e.payload.get("digest"): records[e.event_id] for e in journal.replay("command.accepted")
                if e.payload.get("kind") == "BODY_DESIGNATE" and e.payload.get("signer") == "founder"}
    for event in journal.replay("body.designated"):
        record = accepted.get(event.payload.get("command_digest"))
        if event.payload.get("purpose") == "first_founder_body" and record is not None:
            return {"body_id": event.payload.get("body_id"), "seq": record.seq, "at": record.ts_utc}
    return None


def measure(journal: Journal) -> dict:
    """The founder-tier outcomes on the founder's designated body and the build position, on one ledger state."""
    tiers = metrics.founder_tier(journal)
    seq = {r.payload.get("event_id"): r.seq for r in journal.ledger.by_type("event")}
    registered = {e.payload["mission_id"]: seq[e.event_id] for e in journal.replay("mission.registered")}
    body = founder_body(journal)
    closed = sorted({e.payload.get("mission_id") for e in journal.replay("mission.achieved")} - {None})
    counted = [m for m in closed if (tiers.get(m) or {}).get("tier") == metrics.FOUNDER_TIER
               and body is not None and body["seq"] < registered.get(m, -1)]
    build = devpath.build_status(journal)
    return {
        "outcomes": {
            "founder_tier_closures": counted,
            "vepmc_founder_tier_count": metrics.vepmc(journal)["founder_tier_count"],
            "achieved_nodes": list(devpath.position(journal)["achieved"]),
        },
        "vertical": {
            "build_frontier": (build["build_frontier"] or {}).get("id"),
            "built": list(build["built"]),
            "structural_depth": build["structural_depth"],
            "closures_not_counted": [m for m in closed if m not in counted],
        },
        "founder_body": body,
        "ledger_begins": journal.ledger.records[0].ts_utc if journal.ledger.records else None,
    }


def outcomes(journal: Journal, since: datetime, until: datetime) -> tuple[dict, dict]:
    """(outcomes, vertical progress) between the ledger at ``since`` and at ``until``."""
    start, end = measure(as_of(journal, since)), measure(as_of(journal, until))
    a, b = start["outcomes"], end["outcomes"]
    grew = {
        "founder_tier_closures": sorted(set(b["founder_tier_closures"]) - set(a["founder_tier_closures"])),
        "vepmc_founder_tier_count": max(0, b["vepmc_founder_tier_count"] - a["vepmc_founder_tier_count"]),
        "achieved_nodes": [n for n in b["achieved_nodes"] if n not in a["achieved_nodes"]],
    }
    moved = [k for k in THRESHOLDS["outcome_moved_when_any_grew"] if grew[k]]
    va, vb = start["vertical"], end["vertical"]
    vertical = {
        "build_frontier": {"start": va["build_frontier"], "end": vb["build_frontier"]},
        "structural_depth": {"start": va["structural_depth"], "end": vb["structural_depth"]},
        "newly_built": [n for n in vb["built"] if n not in va["built"]],
        "closures_not_counted_in_window": sorted(set(vb["closures_not_counted"]) - set(va["closures_not_counted"])),
        "counted_as_outcome": False,
        "rule": VERTICAL_RULE,
    }
    begins, body = end["ledger_begins"], end["founder_body"]
    if begins is None or _at(begins) >= until:
        gap = (f"the body's ledger begins at {begins}, at or after the window ends at {until.isoformat()}: it holds "
               "nothing of the window" if begins else "the body's ledger is empty")
    elif body is None:
        gap = ("no founder-signed first-body designation (BODY_DESIGNATE, first_founder_body) is on the body's ledger "
               "by the window's end: it is not the founder's designated body, so its outcomes are not the founder's")
    elif _at(body["at"]) > since:
        gap = (f"the body was designated the founder's at {body['at']}, after the window starts at {since.isoformat()}: "
               "founder-tier outcomes before then are on no ledger read here, so 'unchanged' is not shown for the "
               "whole window")
    else:
        gap = None
    coverage = {"ledger_begins": begins, "founder_body": body, "covers_window": gap is None, "rule": COVERAGE_RULE}
    return ({"measured": True, "start": a, "end": b, "grew": grew, "moved": bool(moved), "moved_by": moved,
             "coverage": coverage, "decides": gap is None or bool(moved), **({"why": gap} if gap else {}),
             "rule": OUTCOME_RULE}, vertical)


# -- the verdict ----------------------------------------------------------------------------------------

def detect(repo: Path | str = KERNEL_ROOT, *, journal: Journal | None = None, since: datetime | None = None,
           until: datetime | None = None, body: str | None = None) -> dict:
    """The cathedral verdict over [since, until); see the module docstring. ``journal`` is a body's read-only view."""
    since, until = window(since=since, until=until)
    act = activity(repo, since, until)
    if journal is None:
        outcome, vertical = {"measured": False, "decides": False, "why": NO_LEDGER}, None
    else:
        outcome, vertical = outcomes(journal, since, until)
        outcome["read_from"] = body or "the given journal (read-only)"
    insufficient = ([act["why"]] if not act["complete"] else []) + ([] if outcome["decides"] else [outcome["why"]])
    if insufficient:
        verdict = INSUFFICIENT_HISTORY
    elif act["rose"] and not outcome["moved"]:
        verdict = CATHEDRAL
    else:
        verdict = NOT_CATHEDRAL
    report = {
        "verdict": verdict,
        "window": {"since": since.isoformat(), "until": until.isoformat(),
                   "days": round((until - since).total_seconds() / 86400, 6)},
        "kill_condition": kill_condition(),
        "thresholds": THRESHOLDS,
        "activity": act,
        "outcomes": outcome,
        "vertical_progress": vertical,
        "acts": INERT,
    }
    if insufficient:
        report["insufficient"] = insufficient
    if verdict == CATHEDRAL:
        report["finding"] = ("activity reached " + ", ".join(act["floors_reached"]) + " while no founder-tier outcome "
                             "moved: stop horizontal expansion and converge (directive section 55)")
    return report
