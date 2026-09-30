"""Morning engineering brief: GREG's first useful bounded mission.

Alfonso runs several repositories and many agent-authored pull requests. The brief
answers from real sources only: what state each local checkout is in, which pull
requests are open, which have failing checks or are going stale, and what needs his
decision. Nothing is changed in any repository.

It is a deterministic render of the inputs retained in the receipt. The independent
appraiser therefore re-renders the brief from the receipt and byte-compares it with
the delivered file: the brief cannot claim anything its recorded sources did not say.

Sources (read-only)
    local Git     fixed read commands through egregore.repository_audit.git_read
                  (scrubbed environment, no fetch, bounded output)
    GitHub REST   open pull requests and their check runs from api.github.com only;
                  an optional ``github_token`` credential handle raises the rate limit
Effect (internal_write)
    one markdown file under the body's delivery root, never overwriting another file

Mechanism lineage: #101/#112 repository audit (exact Git reads), #112 source-bound
morning brief (what changed / blocker / next action), #113 appraiser re-derivation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

from greg.capabilities import CapabilityError, InvocationContext, _inside

RENDERER = "greg.briefs.render/1"
API = "api.github.com"
FAILING = {"failure", "timed_out", "cancelled", "action_required", "startup_failure"}
MAX_REPOS, MAX_PULLS, MAX_CHECKED_PULLS = 12, 30, 10
TITLE_LIMIT = 90


# -- injectable edges (tests replace these; production uses the real world) --------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _https_json(url: str, token: str | None) -> tuple[int, object]:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname != API:
        raise CapabilityError(f"egress to {parts.hostname!r} not allowed")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "uniimente-greg/0.2"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as response:  # noqa: S310
            body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise CapabilityError("GitHub response exceeds read ceiling")
            return response.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        return exc.code, None


NOW = _utcnow
FETCH = _https_json


# -- gathering ----------------------------------------------------------------------

def _git(path: Path, *args) -> str | None:
    from egregore.repository_audit import git_read
    try:
        return git_read(str(path), *args).decode("utf-8", errors="replace").strip()
    except Exception:  # absence of a ref or a failed read is data, recorded as a gap
        return None


def gather_local(name: str, path: Path) -> dict:
    head = _git(path, "rev-parse", "HEAD")
    if head is None:
        return {"name": name, "path": str(path), "readable": False}
    origin = _git(path, "rev-parse", "--verify", "-q", "refs/remotes/origin/main")
    counts = _git(path, "rev-list", "--left-right", "--count", "HEAD...refs/remotes/origin/main") if origin else None
    ahead, behind = (int(x) for x in counts.split()) if counts and len(counts.split()) == 2 else (None, None)
    status = _git(path, "status", "--porcelain")
    log = _git(path, "log", "-5", "--format=%h%x09%cs%x09%s") or ""
    return {"name": name, "path": str(path), "readable": True, "head": head,
            "branch": _git(path, "rev-parse", "--abbrev-ref", "HEAD"), "origin_main": origin,
            "ahead": ahead, "behind": behind,
            "uncommitted": None if status is None else len([l for l in status.splitlines() if l.strip()]),
            "recent": [dict(zip(("sha", "date", "subject"), line.split("\t", 2))) for line in log.splitlines()
                       if line.count("\t") >= 2]}


def gather_github(repos: list[str], *, token: str | None, max_pulls: int = MAX_PULLS,
                  max_checked: int = MAX_CHECKED_PULLS) -> dict:
    result, calls, limited = {}, 0, False
    for repo in repos[:MAX_REPOS]:
        if limited:
            result[repo] = {"fetched": False, "gap": "not fetched: GitHub rate limit reached earlier"}
            continue
        status, pulls = FETCH(f"https://{API}/repos/{repo}/pulls?state=open&per_page={max_pulls}", token)
        calls += 1
        if status in (403, 429):
            limited = True
            result[repo] = {"fetched": False, "gap": f"GitHub refused ({status}); rate limit or access"}
            continue
        if status != 200 or not isinstance(pulls, list):
            result[repo] = {"fetched": False, "gap": f"GitHub returned {status}"}
            continue
        rows = []
        for index, pull in enumerate(pulls[:max_pulls]):
            row = {"number": pull["number"], "title": str(pull.get("title", ""))[:200],
                   "draft": bool(pull.get("draft")), "author": (pull.get("user") or {}).get("login"),
                   "created_at": pull.get("created_at"), "updated_at": pull.get("updated_at"),
                   "head_sha": (pull.get("head") or {}).get("sha"), "base": (pull.get("base") or {}).get("ref"),
                   "checks": None}
            if index < max_checked and row["head_sha"] and not limited:
                code, runs = FETCH(f"https://{API}/repos/{repo}/commits/{row['head_sha']}/check-runs?per_page=100",
                                   token)
                calls += 1
                if code in (403, 429):
                    limited = True
                elif code == 200 and isinstance(runs, dict):
                    tally = {"passed": 0, "failing": 0, "pending": 0, "other": 0, "failing_names": []}
                    for run in runs.get("check_runs", [])[:100]:
                        if run.get("status") != "completed":
                            tally["pending"] += 1
                        elif run.get("conclusion") in FAILING:
                            tally["failing"] += 1
                            tally["failing_names"].append(str(run.get("name", ""))[:80])
                        elif run.get("conclusion") in ("success", "neutral", "skipped"):
                            tally["passed"] += 1
                        else:
                            tally["other"] += 1
                    tally["failing_names"].sort()
                    row["checks"] = tally
            rows.append(row)
        result[repo] = {"fetched": True, "open": len(rows), "pulls": rows,
                        "truncated": len(pulls) >= max_pulls}
    return {"repos": result, "api_calls": calls, "rate_limited": limited,
            "authenticated": bool(token)}


# -- deterministic render -------------------------------------------------------------

def _age_days(stamp: str | None, now: datetime) -> int | None:
    if not stamp:
        return None
    return max(0, (now - datetime.fromisoformat(stamp.replace("Z", "+00:00"))).days)


def _cell(text: str) -> str:
    text = " ".join(str(text).split()).replace("|", "\\|")
    return text if len(text) <= TITLE_LIMIT else text[:TITLE_LIMIT - 1] + "…"


def _checks(checks: dict | None) -> str:
    if checks is None:
        return "not fetched"
    parts = [f"{checks['passed']} pass"]
    if checks["failing"]:
        parts.append(f"**{checks['failing']} FAIL**")
    if checks["pending"]:
        parts.append(f"{checks['pending']} pending")
    if not (checks["passed"] or checks["failing"] or checks["pending"]):
        return "no checks"
    return ", ".join(parts)


# What the brief flags for the founder: GREG-owned presentation policy inside the signed mission.
# It never changes the signed parameters (stale_days, repositories), the capability, its target or
# its consequence class; greg.improvement may replace it only after a held-out gain on founder labels.
ATTENTION_BASELINE = {"idle_includes_drafts": True, "flag_pending_after_days": None,
                      "flag_behind_commits": None, "uncommitted_min": 1}
ATTENTION_SPACE = {"idle_includes_drafts": (True, False), "flag_pending_after_days": (None, 1, 3, 7),
                   "flag_behind_commits": (None, 1, 10, 50), "uncommitted_min": (1, 5, 20)}


def attention_policy(inputs: dict) -> dict:
    return {**ATTENTION_BASELINE, **(inputs.get("attention_policy") or {})}


def attention(inputs: dict, policy: dict | None = None) -> list[dict]:
    """Decision-sized list: failing checks one by one, idle pull requests grouped per repository.

    Each item carries ``keys``: the atomic things it flags (``owner/repo#N``, ``local:name``), which
    is what a founder's attention label refers to."""
    policy = attention_policy(inputs) if policy is None else {**ATTENTION_BASELINE, **policy}
    now = datetime.fromisoformat(inputs["generated_at"].replace("Z", "+00:00"))
    stale = inputs["stale_days"]
    pending_days = policy["flag_pending_after_days"]
    items = []
    for repo, data in sorted(inputs["github"]["repos"].items()):
        idle = []
        for pull in data.get("pulls", []):
            checks, age = pull["checks"], _age_days(pull["updated_at"], now)
            key = f"{repo}#{pull['number']}"
            if checks and checks["failing"]:
                items.append({"rank": 0, "ref": key, "sort": -checks["failing"], "keys": [key],
                              "why": f"checks failing: {', '.join(checks['failing_names'])}", "title": pull["title"]})
            elif (pending_days is not None and checks and checks["pending"] and age is not None
                  and age >= pending_days):
                items.append({"rank": 1, "ref": key, "sort": -age, "keys": [key],
                              "why": f"{checks['pending']} check(s) still pending after {age} days", "title": pull["title"]})
            elif age is not None and age >= stale and (policy["idle_includes_drafts"] or not pull["draft"]):
                idle.append((age, pull["number"]))
        if idle:
            idle.sort(reverse=True)
            numbers = ", ".join(f"#{n}" for _, n in idle[:12]) + (" …" if len(idle) > 12 else "")
            items.append({"rank": 2, "ref": repo, "sort": -len(idle), "keys": [f"{repo}#{n}" for _, n in idle],
                          "why": f"{len(idle)} open pull request(s) idle for {stale}+ days (oldest {idle[0][0]} days): "
                                 f"{numbers}", "title": "merge, close or re-scope them"})
    for local in inputs["local"]:
        key = f"local:{local['name']}"
        if not local.get("readable"):
            items.append({"rank": 3, "ref": local["name"], "why": "not a readable Git repository",
                          "title": local["path"], "sort": 0, "keys": [key]})
            continue
        reasons = []
        if local.get("uncommitted") and local["uncommitted"] >= policy["uncommitted_min"]:
            reasons.append(f"{local['uncommitted']} uncommitted change(s) on {local.get('branch')}")
        behind = policy["flag_behind_commits"]
        if behind is not None and local.get("behind") is not None and local["behind"] >= behind:
            reasons.append(f"{local['behind']} commit(s) behind cached origin/main")
        if reasons:
            items.append({"rank": 3, "ref": local["name"], "why": "; ".join(reasons), "title": local["path"],
                          "sort": 0, "keys": [key]})
    return sorted(items, key=lambda i: (i["rank"], i["sort"], i["ref"]))


def flagged_keys(inputs: dict, policy: dict | None = None) -> set[str]:
    return {key for item in attention(inputs, policy) for key in item["keys"]}


def render(inputs: dict) -> str:
    now = datetime.fromisoformat(inputs["generated_at"].replace("Z", "+00:00"))
    github = inputs["github"]
    lines = [f"# GREG engineering brief — {inputs['generated_at'][:10]}", "",
             f"Generated {inputs['generated_at']} from read-only sources. GREG changed nothing in any repository. "
             "Pull request titles are untrusted external text.", ""]
    items = attention(inputs)
    lines += [f"## Needs your attention ({len(items)})", ""]
    lines += [f"- **{i['ref']}** — {i['why']} — {_cell(i['title'])}" for i in items] or ["- Nothing flagged."]
    lines += ["", "## Open pull requests", ""]
    for repo, data in sorted(github["repos"].items()):
        if not data.get("fetched"):
            lines += [f"### {repo}", "", f"_{data['gap']}_", ""]
            continue
        drafts = sum(p["draft"] for p in data["pulls"])
        more = " (first page only)" if data["truncated"] else ""
        lines += [f"### {repo} — {data['open']} open{more}, {drafts} draft", ""]
        if data["pulls"]:
            lines += ["| PR | Title | Draft | Idle | Checks |", "|---|---|---|---|---|"]
            for p in data["pulls"]:
                idle = _age_days(p["updated_at"], now)
                lines.append(f"| #{p['number']} | {_cell(p['title'])} | {'yes' if p['draft'] else 'no'} | "
                             f"{'?' if idle is None else f'{idle}d'} | {_checks(p['checks'])} |")
        lines.append("")
    lines += ["## Local checkouts", "", "| Repo | Branch | HEAD | vs cached origin/main | Uncommitted |",
              "|---|---|---|---|---|"]
    for local in inputs["local"]:
        if not local.get("readable"):
            lines.append(f"| {local['name']} | — | — | not readable | — |")
            continue
        relation = ("no cached origin/main" if local["origin_main"] is None else
                    f"+{local['ahead']} / -{local['behind']}")
        lines.append(f"| {local['name']} | {_cell(local['branch'] or '?')} | {local['head'][:10]} | {relation} | "
                     f"{local['uncommitted']} |")
    for local in inputs["local"]:
        if local.get("recent"):
            lines += ["", f"Recent commits — {local['name']}:"]
            lines += [f"- {c['sha']} {c['date']} {_cell(c['subject'])}" for c in local["recent"]]
    gaps = [f"{repo}: {data['gap']}" for repo, data in sorted(github["repos"].items()) if not data.get("fetched")]
    gaps += [f"{repo}: check runs fetched for the first {MAX_CHECKED_PULLS} pull requests only"
             for repo, data in sorted(github["repos"].items()) if data.get("open", 0) > MAX_CHECKED_PULLS]
    if github["rate_limited"]:
        gaps.append("GitHub rate limit reached; later check runs were not fetched")
    gaps += [f"{l['name']}: no cached origin/main; no fetch was performed" for l in inputs["local"]
             if l.get("readable") and l["origin_main"] is None]
    lines += ["", "## Gaps in this brief", ""] + ([f"- {g}" for g in gaps] or ["- None detected."])
    lines += ["", "## Evidence", "",
              f"- inputs digest: `{inputs_digest(inputs)}`",
              f"- renderer: `{RENDERER}`; GitHub calls: {github['api_calls']} "
              f"({'authenticated' if github['authenticated'] else 'unauthenticated'})",
              "- local Git read without fetch; the receipt retains every input used above"]
    if inputs.get("attention_policy"):
        lines.append(f"- attention policy: `{json.dumps(inputs['attention_policy'], sort_keys=True)}` "
                     "(learned; kept only after beating the previous policy on later briefs you labelled)")
    lines.append("")
    return "\n".join(lines)


def inputs_digest(inputs: dict) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# -- delivery -------------------------------------------------------------------------

def _deliver_dir(ctx: InvocationContext) -> Path:
    if ctx.deliver_root is None:
        raise CapabilityError("this body has no delivery root configured")
    folder = Path(ctx.deliver_root).resolve() / "briefs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def deliver(text: str, ctx: InvocationContext, *, kind: str, day: str) -> Path:
    """Write once, atomically, under the delivery root; never overwrite a different file."""
    folder = _deliver_dir(ctx)
    data = text.encode("utf-8")
    base = f"{day}-{kind}-brief"
    for suffix in [""] + [f"-{n}" for n in range(2, 100)]:
        target = folder / f"{base}{suffix}.md"
        if target.exists():
            if target.read_bytes() == data:
                return target
            continue
        temporary = folder / f".{target.name}.{os.getpid()}.tmp"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.link(temporary, target)   # fails if another writer won the name: never clobbers
        temporary.unlink()
        return target
    raise CapabilityError("too many briefs for one day")


# -- capability adapters ----------------------------------------------------------------

def _token(ctx: InvocationContext) -> str | None:
    if "github_token" not in ctx.manifest.credentials or ctx.secrets is None:
        return None
    try:
        return ctx.secret("github_token")
    except CapabilityError:
        return None  # public repositories remain readable at the unauthenticated rate


def _repos(params) -> list[str]:
    repos = params.get("github", [])
    if not isinstance(repos, list) or len(repos) > MAX_REPOS or not all(
            isinstance(r, str) and r.count("/") == 1 and all(p and p.replace("-", "").replace("_", "")
                                                             .replace(".", "").isalnum() for p in r.split("/"))
            for r in repos):
        raise CapabilityError("github must be a list of owner/name repositories")
    return repos


def github_pulls(params, ctx: InvocationContext) -> dict:
    return gather_github(_repos(params), token=_token(ctx))


def engineering_brief(params, ctx: InvocationContext) -> dict:
    local = params.get("local", [])
    if not isinstance(local, list) or len(local) > MAX_REPOS:
        raise CapabilityError("local must be a list of {name, path}")
    now = NOW()
    inputs = {"generated_at": now.isoformat().replace("+00:00", "Z"), "renderer": RENDERER,
              "stale_days": int(params.get("stale_days", 14)),
              **({"attention_policy": dict(policy)} if (policy := (ctx.learned or {}).get("brief.attention"))
                 and policy != ATTENTION_BASELINE else {}),
              "local": [gather_local(str(r["name"]), _inside(Path(r["path"]), ctx.read_roots)) for r in local],
              "github": gather_github(_repos(params), token=_token(ctx))}
    text = render(inputs)
    path = deliver(text, ctx, kind="engineering", day=inputs["generated_at"][:10])
    return {"path": str(path), "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode()),
            "inputs": inputs, "inputs_digest": inputs_digest(inputs), "attention": len(attention(inputs))}


def brief_freshness(params, ctx: InvocationContext) -> dict:
    kind = params.get("kind", "engineering")
    if kind not in ("engineering",):
        raise CapabilityError("unknown brief kind")
    folder = _deliver_dir(ctx)
    found = sorted(folder.glob(f"*-{kind}-brief*.md"), key=lambda p: (p.stat().st_mtime, p.name))
    if not found:
        return {"kind": kind, "count": 0, "latest": None, "age_hours": None}
    latest = found[-1]
    age = (NOW().timestamp() - latest.stat().st_mtime) / 3600
    return {"kind": kind, "count": len(found), "latest": latest.name, "age_hours": round(max(age, 0.0), 3),
            "sha256": hashlib.sha256(latest.read_bytes()).hexdigest()}


def verify_delivery(output: dict, deliver_root: Path | None) -> tuple[bool, str]:
    """Appraiser check: the delivered file is exactly the render of the receipted inputs."""
    if not isinstance(output, dict) or "inputs" not in output:
        return False, "receipt does not retain the brief inputs"
    if inputs_digest(output["inputs"]) != output.get("inputs_digest"):
        return False, "retained inputs do not match their digest"
    expected = render(output["inputs"]).encode("utf-8")
    if hashlib.sha256(expected).hexdigest() != output.get("sha256"):
        return False, "receipt digest is not the render of its inputs"
    path = Path(output["path"])
    if deliver_root is None or Path(deliver_root).resolve() not in path.resolve().parents:
        return False, "delivered file is outside the delivery root"
    if not path.is_file() or path.read_bytes() != expected:
        return False, "delivered file differs from the render of the receipted inputs"
    return True, "delivered file equals the render of the receipted inputs"
