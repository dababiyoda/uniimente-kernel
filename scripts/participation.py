"""Participation before edits: admission, a task answer, and a hook that withholds mutations until admission.

The task's work issue is the authoritative record (founder directive of 2026-11-22, policy A). A session posts a
check-in comment on it. The comment's ``Task:`` line names a parent task key and a subtask, and its
``Concern (exclusive):`` line names the files, directories or interfaces only it may change. Board #96 holds only
index comments (``<!-- uniimente:index -->``) that point at task issues.

``admit`` re-reads the task issue and every task issue the index names. It then decides:
- Two active claims conflict when their exclusive concerns overlap and their sessions differ.
- The claim GitHub numbered first wins. Comment ids increase with creation, so every session that reads the same
  comments reaches the same answer. This makes it a serialized decision, not a lock.
- A losing claim is refused and admits nothing.
- A released claim, or one handed off and accepted, cannot be admitted again by its former holder.
- Data that cannot be read, or that comes back truncated, is "incomplete" and refuses admission. It is never
  read as "clear".

On success ``admit`` writes ``<git dir>/uniimente/admission.json`` for the worktree it runs in. Each worktree
needs its own record.

``hook`` is a Claude Code PreToolUse hook (`.claude/settings.json`). It runs in two modes.

Without admission, it denies:
- Edit, Write, MultiEdit and NotebookEdit on a file inside a git worktree;
- Bash commands that run ``git commit`` or ``git push``;
- the GitHub MCP tools that write to a repository.

After admission:
- an edit outside the admitted exclusive and shared concerns is denied;
- a push, or a GitHub write tool, is denied unless ``check`` refreshed the claim within ``FRESH_MINUTES``.

``resume`` (a SessionStart hook on resume and compact) marks the record stale, so edits wait for ``check``.

Limits, stated, not solved:
- A shell command that writes files directly is not prevented. Only ``git commit`` and ``git push`` are withheld.
- The hook acts only in clients that load the repository's `.claude/settings.json`. Claude Code's documentation
  says cloud sessions with several repositories, and project threads, do not load it. There the rule is guidance,
  and it is detected when the contribution is accepted (``contribution``).
- A declared session id is not an authenticated principal.
- A claim created while another is still invisible to the API can be admitted on both sides. ``check`` detects
  this on the next read.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "dababiyoda/uniimente-kernel")
INDEX_ISSUE = 96
FRESH_MINUTES = 30
PAGE = 100
MAX_PAGES = 30          # 3,000 comments per issue; more is reported as truncated

CHECKIN = "<!-- uniimente:checkin -->"
INDEX = "<!-- uniimente:index -->"
RELEASE = "<!-- uniimente:release -->"
HANDOFF = "<!-- uniimente:handoff -->"
ACK = "<!-- uniimente:ack -->"
RECOVERY = "<!-- uniimente:recovery -->"
RECOVERY_GRACE = timedelta(hours=24)   # a claim is stale only this long after its own Recheck time
# Sessions whose recovery comment ends a stale claim. Recovery admits nobody and transfers nothing. A session id is
# declared, not authenticated. Changing this set is the integrator's and the founder's decision (#346, Decision A).
MAINTAINER_SESSIONS = frozenset({"session_01FBS4KNJR59nSbdGbxo8Mbx"})

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
GITHUB_WRITES = re.compile(r"^mcp__github__(push_files|create_or_update_file|delete_file|create_pull_request|"
                           r"create_branch|merge_pull_request|update_pull_request_branch)$")
GIT_WRITE = re.compile(r"(?:^|[;&|(`\s])git(?:\s+-[cC]\s+\S+)*\s+(commit|push)\b")
GIT_PUSH = re.compile(r"(?:^|[;&|(`\s])git(?:\s+-[cC]\s+\S+)*\s+push\b")

_LABEL = r"^[ \t]*[-*][ \t]+(?:\*\*)?{0}(?:\*\*)?:?(?:\*\*)?[ \t]*(?P<v>.*)$"
TASK_RE = re.compile(_LABEL.format(r"Task"), re.M | re.I)
EXCL_RE = re.compile(_LABEL.format(r"Concern \(exclusive\)"), re.M | re.I)
SHARED_RE = re.compile(_LABEL.format(r"Concern \(shared\)"), re.M | re.I)
DEPENDS_RE = re.compile(_LABEL.format(r"Depends on"), re.M | re.I)
CLAIM_RE = re.compile(_LABEL.format(r"Claim"), re.M | re.I)
FROM_RE = re.compile(_LABEL.format(r"From"), re.M | re.I)
TO_RE = re.compile(_LABEL.format(r"To"), re.M | re.I)
ACCEPTS_RE = re.compile(_LABEL.format(r"Accepts handoff"), re.M | re.I)
SESSION_RE = re.compile(_LABEL.format(r"Session"), re.M | re.I)
RECORD_RE = re.compile(_LABEL.format(r"Task record"), re.M | re.I)
RECHECK_RE = re.compile(_LABEL.format(r"Recheck \(UTC\)"), re.M | re.I)
DEPENDENCY_OF_RE = re.compile(_LABEL.format(r"Dependency of"), re.M | re.I)
CONTRACT_RE = re.compile(_LABEL.format(r"Contract"), re.M | re.I)
ID_RE = re.compile(r"session_[A-Za-z0-9]{8,}")
KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)(?:/([a-z0-9][a-z0-9._-]*))?\b")
ISSUE_RE = re.compile(r"(?:(?P<repo>[\w.-]+/[\w.-]+))?#(?P<n>\d+)")
TICKS = re.compile(r"`([^`]+)`")


class Refused(Exception):
    """Admission refused, with the reason a worker can act on."""


# ---------------------------------------------------------------- reading

def _first(rx: re.Pattern, body: str) -> str:
    m = rx.search(body or "")
    return m["v"].strip() if m else ""


def concerns(value: str) -> list[str]:
    """Backticked items of a concern line, or comma-separated items when none is backticked."""
    items = TICKS.findall(value) or [p for p in re.split(r"[,;]", value)]
    out = []
    for item in items:
        item = item.strip().strip("*").strip()
        if not item or item.casefold() in {"none", "nothing", "-"}:
            continue
        out.append(norm(item))
    return out


def norm(path: str) -> str:
    path = path.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.rstrip("/") or "."


def overlap(a: str, b: str) -> bool:
    a, b = norm(a), norm(b)
    return a == b or a == "." or b == "." or b.startswith(a + "/") or a.startswith(b + "/")


def task_key(value: str) -> tuple[str, str] | None:
    m = KEY_RE.search(value or "")
    return (m[1], m[2] or "") if m else None


def session_of(body: str) -> tuple[str | None, str]:
    """(session, reason) of a check-in, by the work map's exact rule (``work_map.checkin_verdict``)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import work_map  # one reader of check-in blocks
    verdict = work_map.checkin_verdict(body)
    return verdict["author"], verdict.get("reason") or ""


def parse(comment: dict, issue: str) -> dict:
    body = comment.get("body") or ""
    head = body.lstrip().splitlines()[0].strip() if body.strip() else ""
    item = {"id": int(comment["id"]), "issue": issue, "url": comment.get("html_url", ""),
            "created_at": comment.get("created_at", ""), "login": (comment.get("user") or {}).get("login", "")}
    if head == CHECKIN:
        key = task_key(_first(TASK_RE, body))
        who, why = session_of(body)
        item.update(kind="claim", session=who, session_reason=why, task=key[0] if key else None,
                    subtask=key[1] if key else None, exclusive=concerns(_first(EXCL_RE, body)),
                    shared=concerns(_first(SHARED_RE, body)), depends=_first(DEPENDS_RE, body),
                    accepts=_ids(_first(ACCEPTS_RE, body)),
                    recheck=(re.search(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", _first(RECHECK_RE, body)) or [None])[0])
    elif head == RELEASE:
        item.update(kind="release", claims=_ids(_first(CLAIM_RE, body)),
                    session=_one(_first(SESSION_RE, body)))
    elif head == HANDOFF:
        item.update(kind="handoff", claims=_ids(_first(CLAIM_RE, body)), frm=_one(_first(FROM_RE, body)),
                    to=_one(_first(TO_RE, body)))
    elif head == INDEX:
        item.update(kind="index", records=[(m["repo"] or REPO, int(m["n"]))
                                           for m in ISSUE_RE.finditer(_first(RECORD_RE, body))],
                    task=(task_key(_first(TASK_RE, body)) or (None,))[0])
    elif head == RECOVERY:
        item.update(kind="recovery", claims=_ids(_first(CLAIM_RE, body)), session=_one(_first(SESSION_RE, body)))
    elif head == ACK:
        item.update(kind="ack", of=_ids(_first(DEPENDENCY_OF_RE, body)), contract=_first(CONTRACT_RE, body),
                    session=_one(_first(SESSION_RE, body)))
    else:
        item.update(kind="other")
    return item


def _ids(value: str) -> list[int]:
    return [int(n) for n in re.findall(r"(?:issuecomment-|\b)(\d{6,})\b", value or "")]


def _one(value: str) -> str | None:
    ids = set(ID_RE.findall(value or ""))
    return ids.pop() if len(ids) == 1 else None


# ---------------------------------------------------------------- the GitHub source

class Source:
    """Issue comments from the public REST API (``gh`` when authenticated, else ``curl``), or from a file."""

    def __init__(self, offline: dict | None = None):
        self.offline = offline
        self.reads: list[dict] = []

    def comments(self, repo: str, number: int) -> list[dict]:
        if self.offline is not None:
            key = f"{repo}#{number}"
            if key not in self.offline:
                self.reads.append({"issue": key, "status": "unavailable", "how": "offline file"})
                raise Refused(f"incomplete: {key} is not in the offline file")
            data = self.offline[key]
            self.reads.append({"issue": key, "status": "complete", "how": "offline file", "count": len(data)})
            return data
        out: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            path = f"repos/{repo}/issues/{number}/comments?per_page={PAGE}&page={page}"
            batch, how = _get(path)
            if batch is None:
                self.reads.append({"issue": f"{repo}#{number}", "status": "unavailable", "how": how})
                raise Refused(f"incomplete: could not read {repo}#{number} ({how})")
            out.extend(batch)
            if len(batch) < PAGE:
                self.reads.append({"issue": f"{repo}#{number}", "status": "complete", "how": how,
                                   "count": len(out)})
                return out
        self.reads.append({"issue": f"{repo}#{number}", "status": "truncated", "how": "page limit",
                           "count": len(out)})
        raise Refused(f"incomplete: {repo}#{number} has more than {len(out)} comments; read was truncated")


def _get(path: str) -> tuple[list | None, str]:
    for how, cmd in (("gh api", ["gh", "api", path]),
                     ("public REST API", ["curl", "-fsS", "--max-time", "20", f"https://api.github.com/{path}"])):
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if done.returncode == 0:
            try:
                data = json.loads(done.stdout)
            except ValueError:
                continue
            if isinstance(data, list):
                return data, how
    return None, "gh api and the public REST API both failed"


# ---------------------------------------------------------------- the decision

def board(source: Source, task_issue: tuple[str, int], index: tuple[str, int] | None) -> list[dict]:
    """Every parsed comment of the task issue, the index and each task issue the index names."""
    issues = [task_issue]
    items: list[dict] = []
    if index:
        idx = [parse(c, f"{index[0]}#{index[1]}") for c in source.comments(*index)]
        items.extend(i for i in idx if i["kind"] == "index")
        for i in idx:
            for rec in i.get("records", []):
                if rec not in issues:
                    issues.append(rec)
    for repo, number in issues:
        items.extend(parse(c, f"{repo}#{number}") for c in source.comments(repo, number))
    return items


def resolve(items: list[dict]) -> dict[int, dict]:
    """Active claims by comment id, each with its holder and the id that orders it (its chain's first claim)."""
    claims = {i["id"]: dict(i, holder=i["session"], order=i["id"], state="active", why="")
              for i in items if i["kind"] == "claim"}
    handoffs = {i["id"]: i for i in items if i["kind"] == "handoff"}
    for event in sorted((i for i in items if i["kind"] in {"release", "handoff"}), key=lambda i: i["id"]):
        for cid in event["claims"]:
            c = claims.get(cid)
            if not c or c["state"] != "active":
                continue
            if event["kind"] == "release" and event["session"] and event["session"] == c["holder"]:
                c.update(state="released", why=f"released by comment {event['id']}", ended_at=event["created_at"],
                         ended_by=event["id"])
    maintainers = _maintainers()
    for event in sorted((i for i in items if i["kind"] == "recovery"), key=lambda i: i["id"]):
        if event["session"] not in maintainers:
            continue          # recorded, ineffective: only a listed maintainer session may recover a claim
        for cid in event["claims"]:
            c = claims.get(cid)
            if c and c["state"] == "active" and c["id"] < event["id"] and _claim_stale(c, event["created_at"]):
                c.update(state="recovered", ended_at=event["created_at"], ended_by=event["id"],
                         why=f"recovered as stale by maintainer {event['session']} in comment {event['id']}")
    for c in sorted(claims.values(), key=lambda c: c["id"]):
        for hid in c.get("accepts") or []:
            h = handoffs.get(hid)
            if not h or h["to"] != c["session"] or h["id"] > c["id"]:
                continue
            for cid in h["claims"]:
                prior = claims.get(cid)
                if prior and prior["state"] == "active" and h["frm"] == prior["holder"] and prior["id"] < h["id"]:
                    prior.update(state="transferred", why=f"handed off by {h['id']}, accepted by {c['id']}",
                                 ended_at=c["created_at"], ended_by=c["id"])
                    c["order"] = min(c["order"], prior["order"])
    return claims


def _maintainers() -> frozenset[str]:
    return MAINTAINER_SESSIONS


def _claim_stale(claim: dict, at: str) -> bool:
    """A claim is stale when ``at`` is more than RECOVERY_GRACE past its own Recheck time; no Recheck, never."""
    try:
        due = datetime.strptime(claim.get("recheck") or "", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        when = datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return when - due > RECOVERY_GRACE


def decide(claims: dict[int, dict], mine: int) -> dict:
    """Admission for claim ``mine``: refused, with the reason, or admitted, with the claims it was compared to."""
    me = claims.get(mine)
    if not me:
        raise Refused(f"comment {mine} is not a check-in on the task record")
    if me["state"] != "active":
        raise Refused(f"claim {mine} is {me['state']} ({me['why']}); a former holder cannot revive it")
    if not me["session"]:
        raise Refused(f"claim {mine} names no session ({me.get('session_reason') or 'no Session line'}); "
                      "post a corrected check-in as a new comment, keeping this one, and admit that")
    if not me["task"]:
        raise Refused(f"claim {mine} has no Task line with a task key (PARENT-KEY/subtask)")
    if not me["exclusive"] and not me["shared"]:
        raise Refused(f"claim {mine} names no concern")
    blockers, parallel, unresolved = [], [], []
    for other in claims.values():
        if other["id"] == mine or other["state"] != "active" or other["holder"] == me["holder"]:
            continue
        if not other["holder"] or not other["task"]:
            # A claim that names no session or task can never be admitted, so it holds nothing; it is reported.
            if any(overlap(o, m) for o in other["exclusive"] for m in me["exclusive"]):
                unresolved.append({"claim": other["id"], "reason": other.get("session_reason") or "no task key"})
            continue
        clash = sorted({o for o in other["exclusive"] for m in me["exclusive"] if overlap(o, m)})
        if not clash:
            continue
        (blockers if other["order"] < me["order"] else parallel).append(
            {"claim": other["id"], "session": other["holder"], "task": other["task"], "concerns": clash,
             "url": other["url"]})
    if blockers:
        b = blockers[0]
        raise Refused(f"exclusive concern {', '.join(b['concerns'])} is held by {b['session']} under claim "
                      f"{b['claim']} ({b['url']}), posted first. Narrow your claim, ask for a split or a "
                      "handoff on the task record, or wait.")
    return {"claim": mine, "later_conflicts": parallel, "unresolved_overlaps": unresolved}


def dependencies(items: list[dict], claims: dict[int, dict], mine: int) -> dict:
    """What my claim depends on, who depends on me, and which dependencies are acknowledged."""
    me = claims[mine]
    acks = [i for i in items if i["kind"] == "ack"]
    mine_deps = []
    for ref in KEY_RE.finditer(me.get("depends") or ""):
        producers = [c for c in claims.values() if c["state"] == "active" and c["task"] == ref[1]
                     and (not ref[2] or c["subtask"] == ref[2])]
        acked = [a for a in acks if mine in a["of"] and any(p["holder"] == a["session"] for p in producers)]
        mine_deps.append({"depends_on": ref[0], "producers": [p["id"] for p in producers],
                          "state": "acknowledged" if acked else ("pending" if producers else "no active producer"),
                          "contract": acked[-1]["contract"] if acked else ""})
    dependents = [{"claim": c["id"], "session": c["holder"], "task": f"{c['task']}/{c['subtask']}",
                   "acknowledged": any(c["id"] in a["of"] and a["session"] == me["holder"] for a in acks)}
                  for c in claims.values() if c["state"] == "active" and c["id"] != mine and me["task"]
                  and re.search(rf"\b{re.escape(me['task'])}(?:/{re.escape(me['subtask'] or '')})?\b",
                                c.get("depends") or "")]
    return {"depends_on": mine_deps, "dependents": dependents}


# ---------------------------------------------------------------- local record

def git(*args: str, cwd: str | Path = ".") -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def worktree_of(path: str | Path) -> tuple[Path, Path] | None:
    """(top level, git dir) of the worktree holding ``path``, or None outside git."""
    p = Path(path).absolute()
    while not p.exists() and p != p.parent:
        p = p.parent
    d = p if p.is_dir() else p.parent
    try:
        top, gd = git("rev-parse", "--show-toplevel", "--absolute-git-dir", cwd=d).splitlines()
    except (subprocess.CalledProcessError, OSError, ValueError):
        return None
    return Path(top), Path(gd)


def record_path(gitdir: Path) -> Path:
    return gitdir / "uniimente" / "admission.json"


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def admit(task_issue: tuple[str, int], claim: int, source: Source, cwd: str = ".",
          index: tuple[str, int] | None = (REPO, INDEX_ISSUE), write: bool = True) -> dict:
    items = board(source, task_issue, index)
    claims = resolve(items)
    verdict = decide(claims, claim)
    me = claims[claim]
    where = worktree_of(cwd)
    if not where:
        raise Refused(f"{cwd} is not inside a git worktree")
    top, gitdir = where
    head = git("rev-parse", "HEAD", cwd=top)
    try:
        guide = git("rev-parse", "HEAD:AGENTS.md", cwd=top)
    except subprocess.CalledProcessError:
        guide = None
    rec = {"version": 1, "task_record": f"{task_issue[0]}#{task_issue[1]}", "claim": claim,
           "claim_url": me["url"], "claim_created_at": me["created_at"], "session": me["holder"],
           "task": me["task"], "subtask": me["subtask"], "exclusive": me["exclusive"], "shared": me["shared"],
           "order": me["order"], "worktree": str(top), "head_at_admission": head,
           "protocol": {"AGENTS.md blob at HEAD": guide}, "admitted_at": iso(now()), "checked_at": iso(now()),
           "refresh_required": False, "reads": source.reads, "later_conflicts": verdict["later_conflicts"],
           "unresolved_overlaps": verdict["unresolved_overlaps"],
           "dependencies": dependencies(items, claims, claim),
           "note": "a declared session, not an authenticated principal; admission coordinates and grants nothing"}
    if write:
        path = record_path(gitdir)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rec, indent=2) + "\n")
        os.replace(tmp, path)
    return rec


REQUIRED = {"claim": int, "task_record": str, "exclusive": list, "shared": list, "checked_at": str}


def load(gitdir: Path) -> dict | None:
    """The worktree's admission record; None when absent or unreadable; ``{"malformed": reason}`` when its shape is
    wrong, so the hook denies with a reason rather than crashing (a crash exits 1, not the 2 that denies)."""
    try:
        rec = json.loads(record_path(gitdir).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict):
        return {"malformed": "the record is not a JSON object"}
    bad = [k for k, t in REQUIRED.items() if not isinstance(rec.get(k), t) or isinstance(rec.get(k), bool)]
    return {"malformed": f"missing or wrong fields: {bad}"} if bad else rec


# ---------------------------------------------------------------- the hook

def _log(gitdir: Path | None, entry: dict) -> None:
    if not gitdir:
        return
    try:
        path = gitdir / "uniimente" / "gate.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(dict(entry, at=iso(now()))) + "\n")
    except OSError:
        pass


HOW = ("Post your check-in on the task's work issue (the block `python scripts/work_map.py` prints, plus "
       "`- Task: PARENT-KEY/subtask` and `- Concern (exclusive): `paths``), then run "
       "`python scripts/participation.py admit --issue <task issue> --claim <comment id>` in this worktree.")


def gate(event: dict) -> tuple[bool, str]:
    """(allowed, reason) for one PreToolUse event."""
    tool = event.get("tool_name", "")
    data = event.get("tool_input") or {}
    cwd = event.get("cwd") or os.getcwd()
    if tool in EDIT_TOOLS:
        target = data.get("file_path") or data.get("notebook_path") or ""
        if not target:
            return True, "no path"
        target = target if os.path.isabs(target) else os.path.join(cwd, target)
        where = worktree_of(target)
        if not where:
            return True, "outside git"
        top, gitdir = where
        rec = load(gitdir)
        if not rec:
            return _deny(gitdir, tool, target, f"No admission in {top}. {HOW}")
        if "malformed" in rec:
            return _deny(gitdir, tool, target, f"The admission record in {top} is malformed ({rec['malformed']}); "
                         "run `python scripts/participation.py admit` again. Never edit it by hand.")
        if rec.get("refresh_required"):
            return _deny(gitdir, tool, target, "This session resumed; refresh first: "
                         "`python scripts/participation.py check`.")
        rel = norm(os.path.relpath(os.path.realpath(target), os.path.realpath(top)))
        scope = rec.get("exclusive", []) + rec.get("shared", [])
        if not any(overlap(c, rel) and (c == "." or rel == c or rel.startswith(c + "/")) for c in scope):
            return _deny(gitdir, tool, target, f"{rel} is outside claim {rec['claim']}'s concerns {scope}. "
                         "Widen the claim on the task record and admit again.")
        _log(gitdir, {"tool": tool, "target": rel, "decision": "allow", "claim": rec["claim"]})
        return True, "admitted"
    if tool == "Bash" or GITHUB_WRITES.match(tool):
        command = data.get("command", "") if tool == "Bash" else ""
        if tool == "Bash" and not GIT_WRITE.search(command):
            return True, "not a commit or push"
        where = worktree_of(cwd)
        if not where:
            return True, "outside git"
        top, gitdir = where
        rec = load(gitdir)
        if not rec or "malformed" in rec:
            return _deny(gitdir, tool, command or tool,
                         f"No valid admission in {top} ({(rec or {}).get('malformed', 'none')}). {HOW}")
        publishing = tool != "Bash" or GIT_PUSH.search(command)
        if rec.get("refresh_required") or (publishing and _stale(rec)):
            return _deny(gitdir, tool, command or tool, f"Refresh before publishing: "
                         f"`python scripts/participation.py check` (last check {rec.get('checked_at')}).")
        _log(gitdir, {"tool": tool, "target": command[:200] or tool, "decision": "allow", "claim": rec["claim"]})
        return True, "admitted"
    return True, "not gated"


def _stale(rec: dict) -> bool:
    try:
        checked = datetime.strptime(rec["checked_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        return True
    return now() - checked > timedelta(minutes=FRESH_MINUTES)


def _deny(gitdir: Path | None, tool: str, target: str, reason: str) -> tuple[bool, str]:
    _log(gitdir, {"tool": tool, "target": str(target)[:200], "decision": "deny", "reason": reason[:300]})
    return False, reason


def hook_main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        print("participation gate: unreadable hook input; refusing", file=sys.stderr)
        return 2
    allowed, reason = gate(event)
    if allowed:
        return 0
    print(f"participation gate: {reason}", file=sys.stderr)
    return 2


def resume_main() -> int:
    """SessionStart on resume/compact: require a refresh before the next edit in every admitted worktree."""
    roots = {os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()}
    try:
        roots.add(json.load(sys.stdin).get("cwd") or "")
    except ValueError:
        pass
    for root in filter(None, roots):
        where = worktree_of(root)
        if not where:
            continue
        try:
            listing = git("worktree", "list", "--porcelain", cwd=where[0])
        except subprocess.CalledProcessError:
            continue
        for line in listing.splitlines():
            if not line.startswith("worktree "):
                continue
            wt = worktree_of(line[9:])
            rec = wt and load(wt[1])
            if rec and "malformed" not in rec:
                rec["refresh_required"] = True
                record_path(wt[1]).write_text(json.dumps(rec, indent=2) + "\n")
                print(f"participation: claim {rec['claim']} in {wt[0]} needs `python scripts/participation.py "
                      "check` before the next edit (this session resumed).")
    return 0


# ---------------------------------------------------------------- commands

def _issue(text: str) -> tuple[str, int]:
    m = ISSUE_RE.fullmatch(text) or (re.fullmatch(r"\d+", text) and ISSUE_RE.fullmatch(f"#{text}"))
    if not m:
        raise SystemExit(f"--issue takes N or owner/repo#N, not {text!r}")
    return (m["repo"] or REPO, int(m["n"]))


def _source(args) -> Source:
    return Source(json.loads(Path(args.comments_json).read_text()) if args.comments_json else None)


def status(task_issue, source: Source, task: str | None, concern: list[str]) -> dict:
    """The task-specific answer: coverage, claims matching the task, subtask, concern or a dependency."""
    out = {"coverage": "complete", "reads": None, "claims": [], "unresolved": []}
    try:
        items = board(source, task_issue, (REPO, INDEX_ISSUE))
    except Refused as exc:
        out.update(coverage="incomplete", reason=str(exc), reads=source.reads)
        return out
    out["reads"] = source.reads
    claims = resolve(items)
    want = task_key(task) if task else None
    for c in sorted(claims.values(), key=lambda c: c["id"]):
        why = []
        if want and c["task"] == want[0]:
            why.append("same parent task" + (" and subtask" if want[1] and c["subtask"] == want[1] else ""))
        if want and re.search(rf"\b{re.escape(want[0])}\b", c.get("depends") or ""):
            why.append("depends on this task")
        hits = sorted({e for e in c["exclusive"] + c["shared"] for q in concern if overlap(e, q)})
        if hits:
            why.append("concern " + ", ".join(hits))
        if not (want or concern):
            why.append("on the record")
        if why:
            out["claims"].append({"claim": c["id"], "state": c["state"], "session": c["holder"],
                                  "task": f"{c['task']}/{c['subtask']}" if c["task"] else None,
                                  "exclusive": c["exclusive"], "depends": c["depends"], "matched": why,
                                  "url": c["url"]})
        if c["kind"] == "claim" and (not c["session"] or not c["task"]):
            out["unresolved"].append({"claim": c["id"], "missing": [k for k in ("session", "task") if not c[k]]})
    out["counts"] = {"claims": len(claims), "active": sum(c["state"] == "active" for c in claims.values()),
                     "matched": len(out["claims"]), "unresolved": len(out["unresolved"])}
    return out


def _covers(scope: list[str], path: str) -> bool:
    path = norm(path)
    return any(c == "." or path == c or path.startswith(c + "/") for c in scope)


ASSURANCE = {
    "admitted-current": "the cited claim is active now and its concerns cover every changed file",
    "admitted-historical": "the cited claim covered every changed file and was active when the work was committed; it "
                           "ended later (released or handed off), so it is evidence of past authority, not current admission",
    "legacy-declared": "the task_ref is a check-in without a Task line (board #96 format before 2026-11-22); "
                       "it is accepted as declared coordination, not as an admitted claim",
    "none": "no claim covered the work",
}


def contribution(task_ref: str, session: str, source: Source, files: list[str] | None = None,
                 worked_at: str | None = None, changes: list[tuple[str | None, list[str]]] | None = None) -> dict:
    """At contribution acceptance: what authorized the work when it was done, and what holds it now.

    ``changes`` lists (commit time, files) pairs, one per commit; ``files`` and ``worked_at`` are the single-commit
    form. The cited claim (``task_ref``) names a lineage: the citing session's claims on the same task and subtask.
    A narrowed or renewed claim belongs to the same lineage as the one it replaced. Each file of each commit must be
    covered by a claim of that lineage that was active at the commit's time. Commit times are declared values, the
    committer dates.
    - ``admitted-current``: every file is held now by an active claim of the lineage.
    - ``admitted-historical``: every file was covered when it was committed, and some covering claim has since
      ended (released or handed off). That is evidence of past authority, not a current admission.
    A later release never rewrites the earlier evidence. Work outside every covering claim's life is ``none``."""
    m = re.search(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)#issuecomment-(\d+)", task_ref or "")
    if not m:
        return {"result": "fail", "assurance": "none", "reason": "task_ref is not an issue comment URL"}
    cid = int(m[3])
    try:
        items = board(source, (m[1], int(m[2])), (REPO, INDEX_ISSUE))
    except Refused as exc:
        return {"result": "not_run", "assurance": "none", "reason": str(exc)}
    claims = resolve(items)
    c = claims.get(cid)
    if not c:
        return {"result": "fail", "assurance": "none", "reason": f"comment {cid} is not a check-in on {m[1]}#{m[2]}"}
    if not c["task"] or not c["session"]:
        if c["session"] and c["session"] == session:
            return {"result": "pass", "assurance": "legacy-declared", "claim": cid, "reason": ASSURANCE["legacy-declared"]}
        return {"result": "fail", "assurance": "none",
                "reason": f"claim {cid} names no session or task ({c.get('session_reason') or 'no Task line'})"}
    if c["session"] != session:
        return {"result": "fail", "assurance": "none", "reason": f"claim {cid} was posted by {c['session']}, not {session}"}
    lineage = sorted((o for o in claims.values() if o["session"] == session and o["task"] == c["task"]
                      and o["subtask"] == c["subtask"]), key=lambda o: o["id"])
    if changes is None:
        changes = [(worked_at, files or [])]
    per_file, uncovered, historical = {}, [], False
    for when, paths in changes:
        for f in paths:
            ok = [o for o in lineage if _covers(o["exclusive"] + o["shared"], f) and o["holder"] == session
                  and when and o["created_at"] <= when and (o["state"] == "active" or when < (o.get("ended_at") or ""))]
            if not ok:
                uncovered.append({"file": f, "committed_at": when})
                continue
            per_file[f] = ok[-1]["id"]
            historical |= all(o["state"] != "active" for o in ok) or not any(
                o["state"] == "active" and _covers(o["exclusive"] + o["shared"], f) for o in lineage)
    out = {"claim": cid, "lineage": [{"claim": o["id"], "state": o["state"], "created_at": o["created_at"],
                                      "ended_at": o.get("ended_at"), "ended_by": o.get("ended_by")} for o in lineage],
           "covered_by": per_file, "uncovered": uncovered,
           "holders_now": {f: sorted({o["holder"] for o in claims.values() if o["state"] == "active" and o["holder"]
                                      and _covers(o["exclusive"] + o["shared"], f)})
                           for _, paths in changes for f in paths}}
    if uncovered:
        return dict(out, result="fail", assurance="none",
                    reason="no claim of this session's lineage covered these files when they were committed")
    kind = "admitted-historical" if historical else "admitted-current"
    return dict(out, result="pass", assurance=kind, reason=ASSURANCE[kind])


def pr_contribution(repo: str, number: int, source: Source) -> dict:
    """``contribution`` for a pull request: its receipt's task_ref and session, and its own commits.

    Each commit is judged at its committer time with its own files. A commit that is also the head, or an
    ancestor of the head, of another open PR into the same base belongs to that PR: a stacked dependency. It is
    listed under ``attributed_to`` and checked there, not here."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import repo_review  # the one receipt reader
    pr, _ = _get_obj(f"repos/{repo}/pulls/{number}")
    commits, _ = _get(f"repos/{repo}/pulls/{number}/commits?per_page=100")
    if pr is None or commits is None:
        return {"result": "not_run", "assurance": "none", "reason": f"could not read {repo}#{number} or its commits"}
    receipt = repo_review.receipt_of(pr.get("body"))
    if not receipt:
        return {"result": "fail", "assurance": "none", "reason": "no readable receipt in the PR body"}
    others, _ = _get(f"repos/{repo}/pulls?state=open&base={pr['base']['ref']}&per_page=100")
    shas = [c["sha"] for c in commits]
    attributed = {}
    for other in others or []:
        if other["number"] == number or other["head"]["sha"] not in shas:
            continue
        for sha in shas[: shas.index(other["head"]["sha"]) + 1]:
            attributed.setdefault(sha, other["number"])
    changes = []
    for c in commits:
        if c["sha"] in attributed:
            continue
        detail, _ = _get_obj(f"repos/{repo}/commits/{c['sha']}")
        if detail is None:
            return {"result": "not_run", "assurance": "none", "reason": f"could not read commit {c['sha']}"}
        if len(detail.get("parents") or []) > 1:
            continue        # a merge brings others' reviewed work; its own resolution edits are a stated limit
        changes.append((detail["commit"]["committer"]["date"], [f["filename"] for f in detail.get("files") or []]))
    coord = receipt.get("coordination") or {}
    out = contribution(coord.get("task_ref", ""), coord.get("session_id", ""), source, changes=changes)
    return dict(out, pr=number, head=pr["head"]["sha"],
                attributed_to={sha[:8]: n for sha, n in attributed.items()})


def _get_obj(path: str) -> tuple[dict | None, str]:
    for cmd in (["gh", "api", path], ["curl", "-fsS", "--max-time", "20", f"https://api.github.com/{path}"]):
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if done.returncode == 0 and isinstance(data := json.loads(done.stdout), dict):
                return data, cmd[0]
        except (OSError, subprocess.TimeoutExpired, ValueError):
            continue
    return None, "unavailable"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("admit", "check", "status", "contribution"):
        p = sub.add_parser(name)
        p.add_argument("--comments-json", help="offline replay: {\"owner/repo#N\": [comments]}")
        if name == "admit":
            p.add_argument("--issue", required=True)
            p.add_argument("--claim", required=True, type=int)
        if name == "status":
            p.add_argument("--issue", required=True)
            p.add_argument("--task")
            p.add_argument("--concern", action="append", default=[])
        if name == "contribution":
            p.add_argument("--task-ref")
            p.add_argument("--session")
            p.add_argument("--files", nargs="*")
            p.add_argument("--worked-at", help="the work's commit time, ISO 8601 UTC")
            p.add_argument("--pr", type=int, help="read task_ref, session, files and commit time from this PR")
    sub.add_parser("hook")
    sub.add_parser("resume")
    args = ap.parse_args(argv)
    if args.cmd == "hook":
        return hook_main()
    if args.cmd == "resume":
        return resume_main()
    source = _source(args)
    if args.cmd == "status":
        print(json.dumps(status(_issue(args.issue), source, args.task, args.concern), indent=2))
        return 0
    if args.cmd == "contribution":
        out = (pr_contribution(REPO, args.pr, source) if args.pr else
               contribution(args.task_ref, args.session, source, args.files, args.worked_at))
        print(json.dumps(out, indent=2))
        return 0 if out["result"] == "pass" else (2 if out["result"] == "not_run" else 1)
    try:
        if args.cmd == "admit":
            rec = admit(_issue(args.issue), args.claim, source)
        else:
            where = worktree_of(os.getcwd())
            prior = where and load(where[1])
            if not prior or "malformed" in prior:
                raise Refused(f"no admission here. {HOW}")
            rec = admit(_issue(prior["task_record"]), prior["claim"], source)
            rec["admitted_at"] = prior["admitted_at"]
            record_path(where[1]).write_text(json.dumps(rec, indent=2) + "\n")
    except Refused as exc:
        where = worktree_of(os.getcwd())
        if args.cmd == "check" and where and (load(where[1]) or {}).get("claim"):
            rec = load(where[1])
            rec["refresh_required"] = True
            record_path(where[1]).write_text(json.dumps(rec, indent=2) + "\n")
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: rec[k] for k in ("claim", "session", "task", "subtask", "exclusive", "shared",
                                           "later_conflicts", "dependencies", "reads")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
