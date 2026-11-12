"""Intake recommendation: given selected open changes, say what to take, in what order, and what is not proven.

The founder's first mission for GREG's own development (2026-11-12): "Given selected open changes, produce an
evidence-backed intake recommendation, identify behavioral conflicts, prepare a reversible composition, execute the
relevant checks, and explain what remains unproven."

One capability, ``brief.intake``, and one read-only sensor, ``brief.intake_status``, which counts only a
recommendation ``brief.intake`` delivered under a receipt on the canonical ledger:

    repository + base + ordered units {name, full sha}      (signed in the mission; nothing is fetched)
      -> ancestry             which heads contain the base and each other (``git merge-base --is-ancestor``)
      -> greg.intake_rehearsal.rehearse
                              the merge in memory, the exports, each head's changed tests on its own tree and on
                              the merged tree, the cause of each behavioural conflict by leave-one-out
      -> claims               the author's claims and check results, supplied as data, matched to what ran here
      -> render               one Markdown file, a deterministic function of the inputs kept in the receipt
      -> deliver              that file and its JSON twin, as ``brief.engineering`` delivers: never overwriting

What it touches: Git objects of exactly the named repository are read (``_pinned``: no upward search, nothing
outside the read roots); the merge's new objects are written under the mission workspace, never into
the repository (``intake_rehearsal.scratch_objects``); the trees are exported under the mission workspace and removed
afterwards; two files are written under the delivery root. No ref, index or working tree changes. No network.

Running the heads' tests runs code from those heads. It runs only through the envelope GREG already uses for a
worker's acceptance tests (``greg.workers.run_tests``): private filesystem, PID and network namespaces where the host
has bubblewrap; on a host without it, refused under the body's ``required`` setting, and under ``supervised`` run with
the network denied and, where the kernel has Landlock, reading only the runtime and writing only the exported tree.
There is no third posture. A check that was refused is reported as not run, for every unit, and no unit is ``ready``.

Five words, never merged, for every test file on every tree: ``passed``, ``failed`` (measured), ``timed out`` (no
measurement), ``not run`` (with the reason), ``errored`` (pytest reached no test).

The recommendation approves nothing. Composing heads for development and approving a protected merge are separate
boundaries; this capability stays on the first side of the first one: it composes in scratch and writes a file.

The appraiser re-renders the file from the receipt and byte-compares (``verify_delivery``). It does not run the
tests again: that would run the heads' code in the appraiser.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import time

from greg import intake_rehearsal as rehearsal
from greg.capabilities import READ_ONLY_GIT_ENV, CapabilityError, InvocationContext, _inside

# /2: an own-head failure in the envelope is not checked, not held. /3 (review of 885b7b7a): a head containing a held
# head is held; an order-dependent textual conflict is said on both units; checks are read per name and in a hosting
# service's words; a contradicted claim keeps a unit from ready; the composed tree is named as an identity only.
RENDERER = "greg.intake.render/3"
KIND = "intake"
SHA = re.compile(r"[0-9a-f]{40}")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,40}")
TRACKED = re.compile(r"[A-Za-z0-9_.][A-Za-z0-9_./-]{0,199}")
TEST_IN_TEXT = re.compile(r"tests/[A-Za-z0-9_./-]+\.py")
SUMMARY = re.compile(r"\d+ (passed|failed|skipped|errors?|xfailed|xpassed|deselected|warnings?)\b.* in \d+(\.\d+)?s")
MAX_UNITS, MAX_TESTS, MAX_UNION, MAX_CLAIMS, MAX_NODES, MAX_SKIPPED = 12, 40, 20, 40, 60, 60
TEXT, NODE_TEXT, WHY_TEXT = 240, 300, 200
MAX_TWIN_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT, MAX_TIMEOUT = 300, 3600
# One invocation's budget across every test file it runs (each file's own timeout bounds only that file): never more
# than the longest single file may take. A file that would start after it is spent is not run, and says so.
MAX_INVOCATION_SECONDS = MAX_TIMEOUT
_monotonic = time.monotonic
DEFAULT_MAX_AGE_HOURS = 48

PASSED, FAILED, TIMED_OUT, NOT_RUN, ERRORED = "passed", "failed", "timed out", "not run", "errored"
STATES = (PASSED, FAILED, TIMED_OUT, NOT_RUN, ERRORED)
# A check conclusion that is a failure, in GitHub's check-run vocabulary. ``cancelled`` is not one: the check stopped
# before it said anything (it reads as no result, like ``skipped``, ``neutral`` and ``stale``).
FAILING = ("failure", "timed_out", "action_required", "startup_failure")
# A check status that is not a conclusion yet: the check is still running.
UNFINISHED = ("in_progress", "queued", "pending", "waiting", "requested")
MIN_SHA_PREFIX = 12          # a claim's or a check's head names this unit when it is a prefix of its SHA this long

READY, AFTER, HOLD, NOT_CHECKED = "ready to take", "take after", "hold", "not checked"
SAME, DIFFERENT = "re-executed here: same result", "re-executed here: DIFFERENT result"
NOT_REEXECUTED, NO_CLAIMS = "claimed, not re-executed here", "no claims supplied"
UNREADABLE = "claimed result is not a pass or a fail"
NO_RESULT, OTHER_HEAD = "no result for this exact head", "result is for another head (stale)"
CHECK_FAILED, RUNNING, CHECK_PASSED = "failed", "still running", "passed"
BOUNDARY = ("This file recommends. It approves nothing. Composing these heads for development and approving a "
            "protected merge are separate boundaries: protected integration needs the founder's approval and the "
            "integrator's approval, and nothing in this file grants either.")


# -- the request: validated once, the same way by the template, the capability and the sensor ------------------

def _text(value, label: str, limit: int = TEXT) -> str:
    """One line of untrusted text, bounded. It is shown; it is never run and never used as a path."""
    if not isinstance(value, str):
        raise CapabilityError(f"{label} must be text")
    text = " ".join("".join(ch if ch.isprintable() else " " for ch in value).split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _sha(value, label: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise CapabilityError(f"{label} must be a full 40-character commit SHA, not a branch name or a short SHA: "
                              "the recommendation is about exact revisions")
    return value


def _tracked(value, label: str) -> str:
    if not isinstance(value, str) or not TRACKED.fullmatch(value) or value.startswith(("-", "/")) \
            or any(part in ("", ".", "..") for part in value.split("/")):
        raise CapabilityError(f"{label} must be a repository-relative file path")
    return value


def _claims(record, name: str) -> dict:
    """A unit's claims record, as collaboration receipt v2 names its fields (``head_sha``, ``validation`` entries
    with ``command``, ``result``, ``evidence``) plus ``tests`` and ``checks`` (``name``, ``head_sha``,
    ``conclusion``, as a hosting service names a check run). Every string is data; a field not named here is never
    read."""
    if not isinstance(record, dict) or set(record) - {"head_sha", "validation", "checks"}:
        raise CapabilityError(f"claims for {name} must be an object with head_sha, validation and checks")
    validation, checks = record.get("validation", []), record.get("checks", [])
    if not isinstance(validation, list) or not isinstance(checks, list) \
            or len(validation) > MAX_CLAIMS or len(checks) > MAX_CLAIMS:
        raise CapabilityError(f"claims for {name}: validation and checks must be lists of at most {MAX_CLAIMS}")
    out = {"head_sha": _text(record.get("head_sha", ""), f"claims for {name}: head_sha", 80), "validation": [],
           "checks": []}
    for entry in validation:
        if not isinstance(entry, dict):
            raise CapabilityError(f"claims for {name}: a validation entry must be an object")
        tests = entry.get("tests")
        if tests is not None and (not isinstance(tests, list) or len(tests) > MAX_TESTS):
            raise CapabilityError(f"claims for {name}: tests must be a list of at most {MAX_TESTS}")
        row = {"command": _text(entry.get("command", entry.get("claim", "")), f"claims for {name}: command"),
               "result": _text(entry.get("result", ""), f"claims for {name}: result", 40),
               "evidence": _text(entry.get("evidence", ""), f"claims for {name}: evidence")}
        if tests is not None:
            row["tests"] = [_text(t, f"claims for {name}: tests") for t in tests]
        out["validation"].append(row)
    for entry in checks:
        if not isinstance(entry, dict):
            raise CapabilityError(f"claims for {name}: a check must be an object")
        conclusion = entry.get("conclusion")
        out["checks"].append({"name": _text(entry.get("name", ""), f"claims for {name}: check name", 80),
                              "head_sha": _text(entry.get("head_sha", ""), f"claims for {name}: check head_sha", 80),
                              "conclusion": None if conclusion is None else
                              _text(conclusion, f"claims for {name}: conclusion", 40)})
    return out


def request(params) -> dict:
    """The validated request. A pure function of ``params`` (no file is opened), and its own fixed point, so the
    mission template, the capability and the sensor all derive the same digest from the same signed parameters."""
    if not isinstance(params, dict) or set(params) - {"repository", "base", "units", "union", "claims",
                                                      "timeout_seconds"}:
        raise CapabilityError("intake request takes repository, base, units, union, claims and timeout_seconds")
    repository = params.get("repository")
    if not isinstance(repository, str) or not repository.startswith("/") or "\x00" in repository:
        raise CapabilityError("repository must be an absolute path")
    units = params.get("units")
    if not isinstance(units, list) or not 1 <= len(units) <= MAX_UNITS:
        raise CapabilityError(f"units must be an ordered list of 1 to {MAX_UNITS} entries {{name, sha}}")
    rows = []
    for unit in units:
        if not isinstance(unit, dict) or set(unit) - {"name", "sha", "tests"} \
                or not isinstance(unit.get("name"), str) or not NAME.fullmatch(unit["name"]):
            raise CapabilityError("each unit is {name, sha}; a name is letters, digits, dot, dash or underscore")
        row = {"name": unit["name"], "sha": _sha(unit.get("sha"), f"unit {unit['name']}")}
        if unit.get("tests") is not None:
            tests = unit["tests"]
            if not isinstance(tests, list) or not 1 <= len(tests) <= MAX_TESTS:
                raise CapabilityError(f"unit {unit['name']}: tests must name 1 to {MAX_TESTS} files")
            row["tests"] = [_tracked(t, f"unit {unit['name']}: a test") for t in tests]
        rows.append(row)
    # names become scratch directory names: one per unit, on a file system that ignores case too
    if len({r["name"].lower() for r in rows}) != len(rows) or len({r["sha"] for r in rows}) != len(rows):
        raise CapabilityError("each unit name and each unit revision may appear once")
    union = params.get("union") or []
    if not isinstance(union, list) or len(union) > MAX_UNION:
        raise CapabilityError(f"union must be a list of at most {MAX_UNION} file paths")
    claims = params.get("claims") or {}
    if not isinstance(claims, dict) or set(claims) - {r["name"] for r in rows}:
        raise CapabilityError("claims must be an object keyed by unit name")
    timeout = params.get("timeout_seconds", DEFAULT_TIMEOUT)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= MAX_TIMEOUT:
        raise CapabilityError(f"timeout_seconds must be a whole number from 1 to {MAX_TIMEOUT}")
    return {"repository": repository, "base": _sha(params.get("base"), "base"), "units": rows,
            "union": sorted({_tracked(p, "a union path") for p in union}),
            "claims": {name: _claims(record, name) for name, record in sorted(claims.items())},
            "timeout_seconds": timeout}


def digest(value) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def request_digest(params) -> str:
    return digest(request(params))


# -- reading the repository ---------------------------------------------------------------------------------

def _pinned(repo: Path, roots) -> dict:
    """``GIT_DIR`` for exactly the named repository, after checking that everything git would read for it is inside
    the read roots: its git directory (a ``.git`` directory, or the one a ``.git`` file names), the repository a
    linked worktree belongs to (``commondir``), and every alternate object store, followed as git follows them.
    git's search upward from a plain directory is never used, and a configuration that includes another file is
    refused (git would read that file)."""
    def inside(path: Path, what: str) -> Path:
        try:
            return _inside(path, roots)
        except CapabilityError:
            raise CapabilityError(f"{what} is outside the read roots ({str(path)[:200]}); git would read it there, so "
                                  "the request is refused") from None

    def text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:65536]
        except OSError as exc:
            raise CapabilityError(f"not a git repository: {path.name} cannot be read ({type(exc).__name__})") from None
    dot = repo / ".git"
    if dot.is_dir():
        gitdir = dot
    elif dot.is_file():
        named = text(dot).strip()
        if not named.startswith("gitdir:"):
            raise CapabilityError("not a git repository: its .git file names no gitdir")
        gitdir = Path(named[len("gitdir:"):].strip())
        gitdir = gitdir if gitdir.is_absolute() else repo / gitdir
    elif (repo / "HEAD").is_file() and (repo / "objects").is_dir():
        gitdir = repo                                    # a bare repository
    else:
        raise CapabilityError(f"not a git repository: {str(repo)[:200]} holds no .git (git's search upward from a "
                              "directory is not used)")
    gitdir = inside(gitdir, "its git directory")
    common = gitdir
    if (gitdir / "commondir").is_file():
        common = inside(gitdir / text(gitdir / "commondir").strip(), "the repository this worktree belongs to")
    stores, seen = [common / "objects"], set()
    while stores:
        store = inside(stores.pop(), "an alternate object store")
        if store in seen:
            continue
        seen.add(store)
        if len(seen) > 6:
            raise CapabilityError("alternate object stores nest deeper than git follows them; refused")
        listing = store / "info" / "alternates"
        if listing.is_file():
            for line in text(listing).splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith('"'):
                    raise CapabilityError("an alternate object store is named in quotes; refused")
                stores.append(Path(line) if Path(line).is_absolute() else store / line)
    return {"GIT_DIR": str(gitdir), "GIT_CEILING_DIRECTORIES": str(repo.parent)}


def _git_environment(repo: Path, scratch: Path, roots=None) -> dict:
    """The environment the rehearsal's git runs in: scrubbed, with no system or user configuration, no lazy fetch,
    new objects written under ``scratch``, and nothing the repository's own configuration names ever run. A filter
    driver is blanked, as ``capabilities.read_only_git`` does (git skips an empty filter command, so ``git archive``
    exports the stored bytes). A merge driver cannot be blanked without changing what the merge produces, so a
    repository that configures one is refused."""
    home = scratch / "home"
    home.mkdir(parents=True, exist_ok=True)
    env = {**READ_ONLY_GIT_ENV, "HOME": str(home), **(_pinned(repo, roots) if roots is not None else {})}
    config = [("core.fsmonitor", "false"), ("core.hooksPath", "/dev/null")]
    with rehearsal.git_environment(env):
        listed = rehearsal.git(repo, "config", "-z", "--name-only", "--get-regexp",
                               r"^(filter\..*\.(clean|process|smudge)|merge\..*\.driver)$", check=False)
        if listed.returncode not in (0, 1):
            raise CapabilityError("not a git repository")
        included = rehearsal.git(repo, "config", "--no-includes", "-z", "--name-only", "--get-regexp",
                                 r"^include(if\..*)?\.path$", check=False)
        if included.returncode == 0 and included.stdout.strip(b"\x00"):
            raise CapabilityError("this repository's configuration includes another file; git would read that file "
                                  "wherever it is, so the request is refused")
        for key in dict.fromkeys(k for k in listed.stdout.decode("utf-8", "replace").split("\x00") if k):
            if key.startswith("merge."):
                raise CapabilityError(f"this repository configures a merge driver ({key[:80]}); the rehearsal runs no "
                                      "program a repository's configuration names, so it is refused")
            config.append((key, ""))
        env |= rehearsal.scratch_objects(repo, scratch / "objects")
    env["GIT_CONFIG_COUNT"] = str(len(config))
    for index, (key, value) in enumerate(config):
        env[f"GIT_CONFIG_KEY_{index}"], env[f"GIT_CONFIG_VALUE_{index}"] = key, value
    with rehearsal.git_environment(env):
        # A git too old to read configuration from its environment would ignore every line above and say nothing.
        if rehearsal.git(repo, "config", "--get", "core.hooksPath", check=False).stdout.decode().strip() != "/dev/null":
            raise CapabilityError("this git does not take configuration from its environment, so the repository's "
                                  "own hooks and filters could not be switched off; refused")
    return env


def _is_ancestor(repo: Path, older: str, newer: str) -> bool:
    proc = rehearsal.git(repo, "merge-base", "--is-ancestor", older, newer, check=False)
    if proc.returncode not in (0, 1):
        raise rehearsal.RehearsalError(f"git merge-base --is-ancestor {older[:10]} {newer[:10]} failed")
    return proc.returncode == 0


def ancestry(repo: Path, base: str, units: list[dict]) -> dict:
    """Which heads contain the base, how far behind it the others are, and which heads contain which."""
    out = {"contains_base": {}, "behind_base": {}, "contains": {}}
    for unit in units:
        out["contains_base"][unit["name"]] = _is_ancestor(repo, base, unit["sha"])
        out["behind_base"][unit["name"]] = int(rehearsal.git(
            repo, "rev-list", "--count", f"{unit['sha']}..{base}").stdout.decode().strip() or 0)
        out["contains"][unit["name"]] = [other["name"] for other in units if other["name"] != unit["name"]
                                         and _is_ancestor(repo, other["sha"], unit["sha"])]
    return out


def _changed_test_names(repo: Path, base: str, sha: str) -> list[str]:
    """Every test file the head changed, by its real name. ``intake_rehearsal.changed_tests`` reads git's default
    listing, in which a name with unusual bytes is quoted and so never matches: this is how such a file is found and
    reported as not run, instead of going missing."""
    fork = rehearsal.git(repo, "merge-base", base, sha, check=False).stdout.decode().strip() or base
    listed = rehearsal.git(repo, "diff", "--name-only", "-z", *rehearsal.CHANGED, fork, sha, "--", "tests").stdout
    names = [n.decode("utf-8", "replace") for n in listed.split(b"\x00") if n]
    return sorted(n for n in names if Path(n).name.startswith("test_") and n.endswith(".py"))


# -- running the heads' tests: only through the worker envelope ------------------------------------------------

class ConfinedRunner:
    """Runs test files inside an exported tree through ``greg.workers.run_tests``, one file at a time, and says for
    each file which of the five things happened. It never runs anything itself."""

    def __init__(self, ctx: InvocationContext):
        self.ctx, self.modes, self.filesystems, self.runs = ctx, [], [], 0
        self.deadline = _monotonic() + MAX_INVOCATION_SECONDS

    def stopped(self) -> None:
        if self.ctx.stop_check is not None and self.ctx.stop_check():
            raise CapabilityError("stop requested; the rehearsal ended before any recommendation was written")

    def __call__(self, tree: Path, files: list[str], timeout: int) -> dict:
        from greg import workers
        from greg.worker_isolation import host_has_envelope
        present = [f for f in files if (tree / f).is_file()]
        missing = sorted(set(files) - set(present))
        states = {f: {"state": NOT_RUN, "measured": False, "why": "the file does not exist in this tree"}
                  for f in missing}
        failed, counts = [], {}
        for file in present:
            self.stopped()
            left = int(self.deadline - _monotonic())
            if left < 1:
                states[file] = {"state": NOT_RUN, "measured": False, "why": f"the invocation's time budget of "
                                f"{MAX_INVOCATION_SECONDS}s was spent before it started"}
                continue
            limit = min(timeout, left)
            [result] = workers.run_tests([["python", *rehearsal.PYTEST, "--tb=no", file]], tree, timeout=limit,
                                         stop_check=self.ctx.stop_check, confinement=self.ctx.worker_confinement)
            self.runs += 1
            if result["confinement"] not in self.modes:
                self.modes.append(result["confinement"])
            if result.get("filesystem") and result["filesystem"] not in self.filesystems:
                self.filesystems.append(result["filesystem"])
            state, nodes, seen = classify(result, file, limit, envelope=host_has_envelope)
            states[file] = state
            failed += nodes
            for kind, n in seen.items():
                counts[kind] = counts.get(kind, 0) + n
        return {"failed": sorted(failed), "counts": counts, "missing": missing, "ran": bool(present), "tail": "",
                "states": states}


def classify(result: dict, file: str, timeout: int, *, envelope=lambda: True) -> tuple[dict, list[str], dict]:
    """One ``workers.run_tests`` result for one test file -> (its state, the failing node ids pytest named, the
    counts pytest printed). ``measured`` is True only when the output decides how the file behaved: a pass, or a
    failure whose every failing test is named."""
    tail = str(result.get("tail") or "")
    if result.get("confinement") == "refused":
        reason = " ".join(tail.removeprefix("acceptance confinement refused: ").split())[:WHY_TEXT]
        # Two ends of a run that did start (greg.workers.supervised_run, on the envelope and on the supervised floor
        # alike) arrive with the same "refused" label: neither is an envelope that was unavailable.
        if reason.startswith("stop requested; worker"):
            return {"state": NOT_RUN, "measured": False, "why": "interrupted by a stop request; no result"}, [], {}
        if reason.startswith("worker exceeded the bounded stdout/stderr ceiling"):
            return {"state": ERRORED, "measured": False,
                    "why": "stopped when its output passed the output ceiling; no result was read"}, [], {}
        return {"state": NOT_RUN, "measured": False,
                "why": ("envelope unavailable: " if not envelope() else "refused before it ran: ") + reason}, [], {}
    if result.get("returncode") == -1 and tail == f"timed out after {timeout}s":
        return {"state": TIMED_OUT, "measured": False, "why": f"no result within {timeout}s"}, [], {}
    _, _, lines = rehearsal.read_pytest(tail)
    # pytest's own last line, wherever it sits: the kept output is stdout followed by stderr, so a test that writes
    # to stderr puts its text after it.
    summary = next((line for line in reversed(lines) if SUMMARY.search(line)), "")
    counts = {kind.rstrip("s") if kind == "errors" else kind: int(n) for n, kind in rehearsal.COUNT.findall(summary)}
    kinds = {m.group(2): m.group(1) for m in map(rehearsal.RESULT.match, tail.splitlines())
             if m and rehearsal.node_file(m.group(2)) == file}       # another file's name in this output is noise
    named = sorted(kinds)
    bad = counts.get("failed", 0) + counts.get("error", 0)
    last = " ".join((summary or (lines[-1] if lines else "no output")).split())[:WHY_TEXT]
    if bad or named:
        whole = bool(counts) and len(named) >= bad and len(named) <= MAX_NODES \
            and all(len(n) <= NODE_TEXT for n in named)
        nothing_ran = not counts.get("passed") and not counts.get("failed") and "FAILED" not in kinds.values()
        state = {"state": ERRORED if nothing_ran else FAILED, "measured": whole}
        if not whole:
            state["why"] = f"{bad} failing, {len(named)} named in the kept output"
        return state, [n[:NODE_TEXT] for n in named[:MAX_NODES]], counts
    if counts.get("passed") and result.get("returncode") == 0:
        return {"state": PASSED, "measured": True}, [], counts
    if counts.get("passed"):
        return {"state": ERRORED, "measured": False,
                "why": f"pytest exited {result.get('returncode')} after reporting no failure"}, [], counts
    if counts or summary or "no tests ran" in " ".join(lines[-2:]):   # e.g. every test deselected or skipped
        return {"state": NOT_RUN, "measured": False, "why": "no test in the file ran to a result: " + last}, [], counts
    return {"state": ERRORED, "measured": False, "why": "pytest printed no result: " + last}, [], counts


# -- the capability ------------------------------------------------------------------------------------------

def intake_recommendation(params, ctx: InvocationContext) -> dict:
    from greg import briefs
    asked = request(params)
    repo = _inside(Path(asked["repository"]), ctx.read_roots)
    workspace = Path(ctx.workspace).resolve()
    scratch = workspace / "intake-scratch"
    shutil.rmtree(scratch, ignore_errors=True)        # an interrupted earlier attempt's exports; never a result
    scratch.mkdir(parents=True)
    runner = ConfinedRunner(ctx)
    try:
        with rehearsal.git_environment(_git_environment(repo, scratch, ctx.read_roots)):
            for label, sha in [("base", asked["base"])] + [(f"unit {u['name']}", u["sha"]) for u in asked["units"]]:
                if rehearsal.git(repo, "cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode:
                    raise CapabilityError(f"{label}: revision {sha} is not in this repository (nothing is fetched)")
            units, skipped = [], {}
            for unit in asked["units"]:
                named = unit.get("tests")
                tests = named or rehearsal.changed_tests(repo, asked["base"], unit["sha"])
                left = [] if named else [
                    {"file": _text(f, "a file name"), "why": "git quotes this file name, so the rehearsal does not run it"}
                    for f in _changed_test_names(repo, asked["base"], unit["sha"]) if f not in tests]
                left += [{"file": f, "why": f"over the limit of {MAX_TESTS} test files for one unit"}
                         for f in tests[MAX_TESTS:]]
                if len(left) > MAX_SKIPPED:
                    left = left[:MAX_SKIPPED] + [{"file": f"({len(left) - MAX_SKIPPED} more test files)",
                                                  "why": "not run, and not listed one by one"}]
                skipped[unit["name"]] = left
                units.append(rehearsal.Unit(unit["name"], unit["sha"], tests=tests[:MAX_TESTS]))
            facts: dict = {}
            report = rehearsal.rehearse(repo, asked["base"], units, [], asked["timeout_seconds"], scratch / "trees",
                                        tuple(asked["union"]), run=runner, facts=facts)
            lineage = ancestry(repo, asked["base"], asked["units"])
    except rehearsal.RehearsalError as exc:
        raise CapabilityError(f"the rehearsal could not be carried out: {str(exc)[:300]}") from None
    except OSError as exc:      # scratch could not be written (a full disk, a path that is not a repository): nothing
        raise CapabilityError(  # was delivered and the repository is untouched, so this is a refusal, not an unknown
            f"the rehearsal could not be carried out: {type(exc).__name__}: {str(exc)[:200]}",
            failure_class="transient") from None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    runner.stopped()          # nothing is delivered after a STOP, even one that ended or arrived during the last run
    inputs = {"renderer": RENDERER, "generated_on": briefs.NOW().date().isoformat(), "request": asked,
              "request_digest": digest(asked), "ancestry": lineage, "rehearsal": report,
              "composed_tree": facts.get("composed_tree"), "skipped_tests": skipped,
              "confinement": {"body_setting": _setting(ctx), "modes": runner.modes,
                              "filesystem": runner.filesystems, "runs": runner.runs}}
    from greg.authority import bounded
    if bounded(inputs) != inputs:        # a receipt would cut it, and the appraiser could then re-render nothing
        raise CapabilityError("the rehearsal's result is larger than a receipt keeps; name fewer units or tests")
    text = render(inputs)
    path = briefs.deliver(text, ctx, kind=KIND, day=inputs["generated_on"])
    twin = _deliver_twin(path, twin_bytes(inputs, text, path.name))
    judged = assess(inputs)
    return {"path": str(path), "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode()),
            "twin": str(twin), "inputs": inputs, "inputs_digest": digest(inputs),
            "request_digest": inputs["request_digest"], "checks": judged["checks"], "counts": judged["counts"],
            "recommendations": {u["name"]: u["recommendation"] for u in judged["units"]}}


def _setting(ctx: InvocationContext) -> str:
    from greg.workers import confinement_mode
    return confinement_mode(ctx.worker_confinement)


def twin_bytes(inputs: dict, text: str, name: str) -> bytes:
    """The JSON twin: the same inputs the Markdown was rendered from, the assessment derived from them, and the
    digests that tie the two files together."""
    twin = {"renderer": RENDERER, "markdown": name, "markdown_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "request": inputs["request"], "request_digest": inputs["request_digest"], "inputs": inputs,
            "inputs_digest": digest(inputs), "assessment": assess(inputs)}
    return (json.dumps(twin, sort_keys=True, indent=1) + "\n").encode()


def _deliver_twin(markdown: Path, data: bytes) -> Path:
    """Write the twin beside its Markdown, atomically, never over a different file. The twin is written last: a
    Markdown file without one was interrupted before it was finished, and the sensor does not count it."""
    target = markdown.with_suffix(".json")
    if target.exists():
        if target.read_bytes() == data:
            return target
        raise CapabilityError(f"{target.name} already exists with different content; nothing was overwritten")
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        os.link(temporary, target)     # fails if another writer won the name: never clobbers
    finally:
        temporary.unlink()
    return target


# -- the assessment: a pure function of the receipted inputs ----------------------------------------------------

def _order(names: list[str], contains: dict) -> list[str]:
    """A topological order of the units: a head comes after every head it contains; ties keep the given order."""
    placed, order = set(), []
    while len(order) < len(names):
        ready = [n for n in names if n not in placed and all(a in placed for a in contains.get(n, []))]
        nxt = ready[0] if ready else next(n for n in names if n not in placed)   # mutual containment cannot happen
        placed.add(nxt)
        order.append(nxt)
    return order


def _claim_tests(row: dict) -> list[str]:
    return row["tests"] if "tests" in row else sorted(set(TEST_IN_TEXT.findall(row["command"])))


PASS_WORDS = ("pass", "passed", "passes", "success", "succeeded", "successful", "ok", "green")
FAIL_WORDS = ("fail", "failed", "fails", "failure", "error", "errored", "red")


def _claimed(result: str) -> str | None:
    """A claimed result as "pass" or "fail", in the words people and test runners write it ("success", "1 passed",
    "3 passed, 1 failed in 0.2s"), or None when it says neither."""
    text = " ".join(result.strip().lower().split())
    if text in PASS_WORDS:
        return "pass"
    if text in FAIL_WORDS:
        return "fail"
    parts = re.sub(r" in \d+(\.\d+)?s$", "", text).split(", ")
    counts = [re.fullmatch(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?)", p)
              for p in parts]
    if not text or not all(counts):
        return None
    if any(int(m.group(1)) for m in counts if m.group(2) in ("failed", "error", "errors")):
        return "fail"
    return "pass" if any(int(m.group(1)) for m in counts if m.group(2) == "passed") else None


def _names_head(claimed: str, sha: str) -> bool | None:
    """Whether a claim's or a check's head names this unit: its full SHA, or a prefix of it of at least
    ``MIN_SHA_PREFIX`` hex digits. None when it names no head at all."""
    if not claimed:
        return None
    claimed = claimed.lower()
    return len(claimed) >= MIN_SHA_PREFIX and bool(SHA_PREFIX.fullmatch(claimed)) and sha.startswith(claimed)


SHA_PREFIX = re.compile(r"[0-9a-f]{1,40}")


def _short(claimed: str, sha: str) -> str:
    return (f", shorter than {MIN_SHA_PREFIX} hex digits, so it is not read as this one"
            if claimed and SHA_PREFIX.fullmatch(claimed.lower()) and sha.startswith(claimed.lower()) else "")


def _match_claims(unit: dict, record: dict | None, alone: dict) -> tuple[list[dict], list[dict]]:
    """A unit's claims and check results, each given exactly one of the stated readings. Each check carries
    ``this_head`` (whether it names this revision), so the assessment can decide check by check name."""
    if record is None:
        return [{"claim": "", "status": NO_CLAIMS, "detail": ""}], \
               [{"name": "", "status": NO_RESULT, "detail": "nothing was supplied for this unit", "this_head": False}]
    claims = []
    for row in record["validation"]:
        tests = _claim_tests(row)
        named = _names_head(record["head_sha"], unit["sha"])
        if named is None:
            status, detail = f"stale: the claim names no head; this unit is {unit['sha']}", ""
        elif not named:
            status, detail = f"stale: the claim names head {record['head_sha']}, this unit is " \
                             f"{unit['sha']}", _short(record["head_sha"], unit["sha"]).removeprefix(", ")
        elif not tests or any(not alone.get(t, {}).get("measured") for t in tests):
            status = NOT_REEXECUTED
            detail = "it names no test file" if not tests else "its tests were not among those run and measured here: " \
                + ", ".join(t for t in tests if not alone.get(t, {}).get("measured"))
        else:
            here = "pass" if all(alone[t]["state"] == PASSED for t in tests) else "fail"
            said = _claimed(row["result"])
            status = UNREADABLE if said is None else SAME if said == here else DIFFERENT
            detail = f"claimed {row['result'] or '(nothing)'}; here {here}"
        claims.append({"claim": row["command"], "claimed_result": row["result"], "tests": tests, "status": status,
                       "detail": detail})
    checks, exact = [], False
    for row in record["checks"]:
        named, conclusion = _names_head(row["head_sha"], unit["sha"]), row["conclusion"]
        if named is None:
            status, detail = NO_RESULT, "it names no head"
        elif not named:
            status, detail = OTHER_HEAD, f"it names head {row['head_sha']}" + _short(row["head_sha"], unit["sha"])
        elif conclusion is None or conclusion.lower() in UNFINISHED:
            status, detail, exact = RUNNING, f"status {conclusion}" if conclusion else "", True
        elif conclusion.lower() == "success":
            status, detail, exact = CHECK_PASSED, "", True
        elif conclusion.lower() in FAILING:
            status, detail, exact = CHECK_FAILED, f"concluded {conclusion}", True
        else:
            status, detail = NO_RESULT, f"concluded {conclusion}, which is not a result"
        checks.append({"name": row["name"], "status": status, "detail": detail, "this_head": bool(named),
                       "conclusion": conclusion})
    if not exact:
        checks.append({"name": "", "status": NO_RESULT, "detail": "no check result was supplied for this revision",
                       "this_head": False})
    return claims, checks


def assess(inputs: dict) -> dict:
    """Everything the recommendation says, derived from the receipted inputs and nothing else."""
    asked, report, lineage = inputs["request"], inputs["rehearsal"], inputs["ancestry"]
    names = [u["name"] for u in asked["units"]]
    order = _order(names, lineage["contains"])
    by_name = {u["name"]: u for u in report["units"]}
    conflicts = report["behavioural_conflicts"]
    tally = {state: 0 for state in STATES}
    units = []
    for unit in asked["units"]:
        name, entry = unit["name"], by_name[unit["name"]]
        states = entry.get("states") or {"alone": {}, "merged": None}
        alone, merged = states["alone"], states["merged"]
        skipped = inputs["skipped_tests"].get(name, [])
        tests = []
        for file in entry["tests"]:
            own = alone.get(file, {"state": NOT_RUN, "measured": False, "why": "no result was recorded"})
            if merged is None:
                both = {"state": NOT_RUN, "measured": False,
                        "why": "the unit was left out of the merge for a textual conflict"}
            else:
                both = merged.get(file, {"state": NOT_RUN, "measured": False, "why": "no result was recorded"})
            tests.append({"file": file, "alone": own, "merged": both})
            tally[own["state"]] += 1
            tally[both["state"]] += 1
        for item in skipped:
            tests.append({"file": item["file"], "alone": {"state": NOT_RUN, "measured": False, "why": item["why"]},
                          "merged": {"state": NOT_RUN, "measured": False, "why": item["why"]}})
            tally[NOT_RUN] += 2
        claims, checks = _match_claims(unit, asked["claims"].get(name), alone)

        hold, unchecked, notes = [], [], []
        if name in report["textual_conflicts"]:
            hold.append("textual conflict with what was merged before it, in "
                        + ", ".join(report["textual_conflicts"][name]))
        # A test that fails on its own head ran inside the envelope (no socket, a temporary directory inside the
        # tree, a scrubbed environment), and nothing here separates the head's code from that confinement: on
        # 2026-11-12 five such failures on twelve real heads all passed outside it. Only a difference measured
        # inside one envelope (own head against the merge) holds a unit; this is left not checked, never ready.
        broken = [t["file"] for t in tests if t["alone"]["state"] == FAILED]
        if broken:
            unchecked.append("its own test fails on its own head inside the test envelope (" + ", ".join(broken)
                             + "); a failure there is not separated from the confinement")
        for conflict in conflicts:
            cause = ", ".join(conflict["caused_by"]) or "no single head"
            if conflict["unit"] == name:
                hold.append(f"behavioural conflict: its test {conflict['test']} passes on its own head and fails on "
                            f"the merged tree (cause: {cause})")
            elif name in conflict["caused_by"]:
                hold.append(f"behavioural conflict: merging it breaks {conflict['unit']}'s test {conflict['test']}")
        if any(c["status"].startswith("stale") for c in claims):
            hold.append("stale: its claims name another head or none")
        # Check by check name: a check whose every result is for another head is stale, whatever other checks say.
        current = {c["name"] for c in checks if c.get("this_head")}
        for check in dict.fromkeys(c["name"] for c in checks if c["status"] == OTHER_HEAD and c["name"] not in current):
            hold.append(f"stale: check {check} has results only for another head")
        if any(c["status"] == CHECK_FAILED for c in checks):
            hold.append("a check failed for this revision")

        if not tests:
            unchecked.append("no test changed, and none was named for it")
        for t in tests:
            for where, state in (("its own head", t["alone"]), ("the merged tree", t["merged"])):
                if state["state"] in (TIMED_OUT, NOT_RUN, ERRORED) or (state["state"] == FAILED
                                                                        and not state["measured"]):
                    unchecked.append(f"{t['file']} {state['state']} on {where}"
                                     + (f" ({state['why']})" if state.get("why") else ""))
        if any(item["unit"] == name for item in report.get("not_measured", [])):
            unchecked.append("a test failed on one tree and gave no result on the other")
        if any(c["status"] == RUNNING for c in checks):
            unchecked.append("a check is still running for this revision")
        mine = [c for c in checks if c.get("this_head")]
        if mine and all(c["status"] == NO_RESULT for c in mine):
            unchecked.append("every check supplied for this revision concluded without a result ("
                             + ", ".join(str(c.get("conclusion")) for c in mine) + ")")
        for claim in claims:
            if claim["status"] in (DIFFERENT, UNREADABLE):
                unchecked.append(f"a claim's result differs from what ran here: \"{claim['claim']}\" "
                                 f"({claim['detail']})")

        if name in report["kept_both_sides"]:
            notes.append("the merge keeps both sides' lines in " + ", ".join(report["kept_both_sides"][name])
                         + "; nobody reviewed that resolution")
        if not lineage["contains_base"][name]:
            notes.append(f"its head does not contain the base ({lineage['behind_base'][name]} commit(s) behind)")
        arrives = [other for other in names if name in lineage["contains"].get(other, [])]
        if arrives:
            notes.append("arrives with " + ", ".join(arrives))
        after = [n for n in order if n in lineage["contains"].get(name, [])]
        # Which of two heads that conflict textually is left out depends on the listed order: the one merged first
        # says so, beside whatever it is recommended.
        blocks = [other for other, heads in (report.get("textual_conflicts_with") or {}).items() if name in heads]
        if blocks:
            notes.append(f"{', '.join(blocks)}, listed after it, conflicts with it textually and was left out of the "
                         "merge: which of them is left out depends on the listed order")
        units.append({"name": name, "sha": unit["sha"], "hold": hold, "not_checked": unchecked, "notes": notes,
                      "tests": tests, "claims": claims, "checks": checks, "arrives_with": arrives, "after": after,
                      "blocks": blocks})
    # In dependency order, so a contained head is decided before every head that contains it: taking a head takes the
    # heads it contains, so one that contains a held head is held too.
    decided = {u["name"]: u for u in units}
    for name in order:
        unit = decided[name]
        unit["hold"] += [f"it contains {inner}, which is held ({decided[inner]['hold'][0]}); taking it takes that code"
                         for inner in unit["after"] if decided[inner]["kind"] == HOLD]
        if unit["hold"]:
            recommendation, kind = f"{HOLD}: {unit['hold'][0]}", HOLD
        elif unit["not_checked"]:
            recommendation, kind = f"{NOT_CHECKED}: {unit['not_checked'][0]}", NOT_CHECKED
        elif unit["after"]:
            recommendation, kind = f"{AFTER} {', '.join(unit['after'])}", AFTER
        else:
            recommendation, kind = READY, READY
        if kind in (READY, AFTER) and unit["blocks"]:
            recommendation += (f" (in the listed order; {', '.join(unit['blocks'])}, listed after it, conflicts with "
                               "it textually and is held)")
        unit["recommendation"], unit["kind"] = recommendation, kind
    kinds = [u["kind"] for u in units]
    refused = [w for u in units for t in u["tests"] for w in (t["alone"], t["merged"])
               if w["state"] == NOT_RUN and str(w.get("why", "")).startswith("envelope unavailable")]
    ran = tally[PASSED] + tally[FAILED] + tally[ERRORED] + tally[TIMED_OUT]
    checks = {"ran": bool(ran), "why": None if ran else (
        "not run: envelope unavailable" if refused else "not run: no test file was run")}
    return {"order": order, "units": units, "checks": checks,
            "counts": {"units": len(units), "ready": kinds.count(READY), "take_after": kinds.count(AFTER),
                       "hold": kinds.count(HOLD), "not_checked": kinds.count(NOT_CHECKED),
                       "textual_conflicts": len(report["textual_conflicts"]),
                       "behavioural_conflicts": len(conflicts),
                       "test_runs": {state.replace(" ", "_"): n for state, n in tally.items()}}}


# -- the render: deterministic, from the receipted inputs only ---------------------------------------------------

def _shown(text, limit: int = TEXT) -> str:
    """Untrusted text made safe to sit inside one Markdown line: one line, no backtick, no table bar."""
    text = " ".join("".join(ch if ch.isprintable() else " " for ch in str(text)).split())
    text = text.replace("`", "'").replace("|", "\\|")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _state(state: dict) -> str:
    extra = []
    if state["state"] == FAILED and not state["measured"]:
        extra.append("not every failing test is named")
    if state.get("why"):
        extra.append(_shown(state["why"], WHY_TEXT + 40))
    return state["state"] + (f" ({'; '.join(extra)})" if extra else "")


def recipe(asked: dict) -> str:
    """The command that repeats this composition and these tests by hand."""
    argv = ["python", "scripts/compose_rehearsal.py", "--repo", asked["repository"], "--base", asked["base"]]
    for unit in asked["units"]:
        argv += ["--unit", f"{unit['name']}={unit['sha']}"]
    for unit in asked["units"]:
        if unit.get("tests"):
            argv += ["--tests", f"{unit['name']}={','.join(unit['tests'])}"]
    for path in asked["union"]:
        argv += ["--union", path]
    return " ".join(shlex.quote(a) for a in argv + ["--timeout", str(asked["timeout_seconds"])])


def render(inputs: dict) -> str:
    asked, report, lineage = inputs["request"], inputs["rehearsal"], inputs["ancestry"]
    judged = assess(inputs)
    by_name = {u["name"]: u for u in judged["units"]}
    confinement = inputs["confinement"]
    lines = [f"# Intake recommendation: {len(asked['units'])} unit(s) on base `{asked['base'][:10]}`", "",
             BOUNDARY, "",
             f"Written {inputs['generated_on']} from Git objects in `{_shown(asked['repository'])}`. Nothing was "
             "fetched, merged, pushed or edited. Claims, check names and file names are untrusted text, shown as "
             "data.", ""]
    if not judged["checks"]["ran"]:
        lines += [f"**The checks were NOT run ({judged['checks']['why'].removeprefix('not run: ')}).** Nothing below "
                  "is a test result, and no unit is ready.", ""]
    lines += ["## Recommendation", "", "| Unit | Revision | Recommendation |", "|---|---|---|"]
    lines += [f"| {name} | `{by_name[name]['sha']}` | {_shown(by_name[name]['recommendation'], 400)} |"
              for name in judged["order"]]
    lines.append("")
    beside = []
    for name in judged["order"]:
        unit = by_name[name]
        more = unit["hold"][1:] if unit["kind"] == HOLD else unit["not_checked"][1:] if unit["kind"] == NOT_CHECKED \
            else []
        also = (unit["not_checked"] if unit["kind"] == HOLD else []) + unit["notes"]
        beside += [f"- **{name}** also: {_shown(reason, 400)}" for reason in more + also]
    lines += beside + ([""] if beside else []) + ["## 1. Exact revisions", "", f"- base: `{asked['base']}`"]
    for unit in asked["units"]:
        name = unit["name"]
        base = "contains the base" if lineage["contains_base"][name] else \
            f"does NOT contain the base ({lineage['behind_base'][name]} commit(s) of the base are missing from it)"
        inside = lineage["contains"][name]
        lines.append(f"- {name}: `{unit['sha']}`; {base}; "
                     + ("contains " + ", ".join(inside) if inside else "contains no other unit"))
    lines += ["", "## 2. Dependency order", ""]
    for index, name in enumerate(judged["order"], 1):
        unit = by_name[name]
        lines.append(f"{index}. {name}" + (f" (arrives with {', '.join(unit['arrives_with'])})"
                                           if unit["arrives_with"] else "")
                     + (f" (after {', '.join(unit['after'])})" if unit["after"] else ""))
    given = [u["name"] for u in asked["units"]]
    lines += ["", "The order above follows ancestry only: a head comes after every head it contains."
              + ("" if given == judged["order"] else " The mission listed the units as " + ", ".join(given)
                 + "; the composition below was made in that listed order.")]
    lines += ["", "## 3. Textual conflicts", ""]
    if not report["textual_conflicts"] and not report["kept_both_sides"]:
        lines.append("None: every unit merged onto what came before it.")
    lines += [f"- **{name}** was left out of the merged tree: it conflicts with what was merged before it"
              + rehearsal._directly(report, name) + " in " + ", ".join(f"`{_shown(f)}`" for f in files)
              for name, files in report["textual_conflicts"].items()]
    lines += [f"- **{name}**: both sides' lines were kept in " + ", ".join(f"`{_shown(f)}`" for f in files)
              + " (asked for by the mission for these files only; nobody reviewed the result)"
              for name, files in report["kept_both_sides"].items()]
    lines += ["", f"Merged, in this order: {', '.join(report['merge_order']) or 'nothing'}.",
              "", "## 4. Behavioural conflicts a clean merge does not reveal", ""]
    if not report["behavioural_conflicts"]:
        lines.append("None was measured in the tests that ran." if judged["checks"]["ran"]
                     else "None could be measured: no test ran.")
    for conflict in report["behavioural_conflicts"]:
        cause = ", ".join(conflict["caused_by"]) or "no single head"
        lines.append(f"- `{_shown(conflict['test'], NODE_TEXT)}`, a test of **{conflict['unit']}**: passes on its own "
                     f"head, fails on the merged tree. Cause: **{cause}**; {_shown(conflict['note'], 400)}.")
    if report["failing_before_the_merge"]:
        lines += ["", "Failing on their own head before the merge, inside the test envelope (not a composition problem, "
                  "and not separated from the confinement: run them outside it before reading them as defects):"]
        lines += [f"- `{_shown(item['test'], NODE_TEXT)}` (from {item['unit']})"
                  + (f": {_shown(item['note'])}" if item.get("note") else "")
                  for item in report["failing_before_the_merge"]]
    if report.get("not_measured"):
        lines += ["", "Seen failing on one tree with no result on the other (neither a conflict nor cleared):"]
        lines += [f"- `{_shown(item['test'], NODE_TEXT)}` (from {item['unit']}): {_shown(item['note'])}"
                  for item in report["not_measured"]]
    lines += ["", "Every test file, on the unit's own head and on the merged tree:", "",
              "| Unit | Test file | Own head | Merged tree |", "|---|---|---|---|"]
    rows = [f"| {name} | `{_shown(t['file'])}` | {_state(t['alone'])} | {_state(t['merged'])} |"
            for name in judged["order"] for t in by_name[name]["tests"]]
    lines += rows or ["| (none) | no test file was named or changed | not run | not run |"]
    lines += ["", "## 5. Claims matched to executed evidence", ""]
    for name in judged["order"]:
        for claim in by_name[name]["claims"]:
            if claim["status"] == NO_CLAIMS:
                lines.append(f"- **{name}**: {NO_CLAIMS}.")
                continue
            lines.append(f"- **{name}**: \"{_shown(claim['claim'])}\" (claimed: {_shown(claim['claimed_result'], 40) or 'nothing'}): "
                         f"**{_shown(claim['status'], 200)}**" + (f" ({_shown(claim['detail'], 400)})" if claim["detail"] else "") + ".")
        if asked["claims"].get(name) is not None and not asked["claims"][name]["validation"]:
            lines.append(f"- **{name}**: a claims record was supplied with no validation entry.")
    lines += ["", "## 6. Missing or stale appraisals", ""]
    for name in judged["order"]:
        for check in by_name[name]["checks"]:
            label = f"check \"{_shown(check['name'], 80)}\"" if check["name"] else "appraisal"
            lines.append(f"- **{name}**: {label}: **{check['status']}**"
                         + (f" ({_shown(check['detail'], 200)})" if check["detail"] else "") + ".")
    lines += ["", "## 7. Reproducible recipe", "", "```", recipe(asked), "```", "",
              f"Composed tree id: `{inputs['composed_tree']}`. Its objects were written only to the mission's "
              "scratch, which was removed: nothing in the repository holds them, so it cannot be fetched. The id "
              "names the merged content: the same merge, made again by the command above, has the same tree id.",
              "The command repeats the composition and the tests as you, outside GREG's confinement, with its "
              "timeout applied to a whole unit's test run. It prints its own report.",
              "", "## 8. What remains unproven", ""]
    lines += [f"- {limit}" for limit in report["limits"]]
    lines += [f"- **{name}**: {_shown(reason, 400)}" for name in judged["order"]
              for reason in by_name[name]["not_checked"]]
    lines += [f"- **{name}**: {_shown(claim['status'], 200)}" + (f": \"{_shown(claim['claim'])}\"" if claim["claim"] else "")
              for name in judged["order"] for claim in by_name[name]["claims"]
              if claim["status"] in (NOT_REEXECUTED, NO_CLAIMS, DIFFERENT, UNREADABLE)]
    lines += [f"- **{name}**: {_shown(note, 400)}" for name in judged["order"] for note in by_name[name]["notes"]
              if "nobody reviewed" in note or "does not contain the base" in note or "listed order" in note]
    modes = "; ".join(confinement["modes"]) or "no test was started"
    lines += [f"- the tests ran under: {modes} (body setting: {confinement['body_setting']}); a test that opens any "
              "socket (even to localhost), reaches the network, reads a file outside its tree or expects its "
              "temporary directory outside its tree fails here on both trees alike, which is why a failure on a "
              "head's own tree is reported as not checked, not as a defect of the head",
              "- a head's tests are that head's code: a head that forges its own test output is not detected here",
              "- all units' tests ran in one exported copy of the merged tree, one after another: a test that "
              "rewrites that copy can change a later result",
              "- the independent appraiser re-renders this file from its receipt and compares the bytes; it does not "
              "run the tests again",
              "- claims and check results were supplied by the mission's author; none was read from a hosting "
              "service here",
              "", "## 9. Approval boundaries", "", BOUNDARY, "",
              "## Evidence", "", f"- request digest: `{inputs['request_digest']}`",
              f"- inputs digest: `{digest(inputs)}`", f"- renderer: `{RENDERER}`; test files started: "
              f"{confinement['runs']}", ""]
    return "\n".join(lines)


# -- the sensor and the appraiser's check ---------------------------------------------------------------------

def _delivered(ledger, asked: str) -> dict:
    """Every recommendation for the request ``asked`` that GREG itself delivered, by the Markdown path each names:
    what ``brief.intake`` returned under a Consequence Gate receipt (its Commit Witness names the capability). Read
    from the canonical ledger, never from the delivery folder, which anything on the machine can write."""
    witnesses = {r.payload.get("witness_id") for r in ledger.by_type("witness")
                 if r.payload.get("capability") == "brief.intake"}
    found = {}
    for record in ledger.by_type("receipt"):
        result = record.payload.get("result") or {}
        output = result.get("output") if isinstance(result, dict) else None
        if record.payload.get("witness_id") in witnesses and result.get("result_class") == "positive" \
                and isinstance(output, dict) and output.get("request_digest") == asked:
            try:
                found[Path(str(output.get("path"))).resolve()] = output
            except (OSError, ValueError):
                continue
    return found


def intake_status(params, ctx: InvocationContext) -> dict:
    """How many intact, recent recommendations for exactly this request, delivered by GREG, are in the delivery
    folder. A file about other heads has another request digest and is not counted, however new it is. A file GREG
    did not deliver (no ``brief.intake`` receipt on the canonical ledger names it) is not counted, however exactly it
    resembles one: it is counted apart, as ``not_delivered_by_greg``. A delivered file counts only while it is still
    exactly what its receipt renders: the appraiser's own check (:func:`verify_delivery`) decides that, here too."""
    from greg import briefs
    asked = params.get("request_digest")
    if not isinstance(asked, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", asked):
        raise CapabilityError("request_digest must be sha256:<64 hex>")
    limit = params.get("max_age_hours", DEFAULT_MAX_AGE_HOURS)
    if isinstance(limit, bool) or not isinstance(limit, (int, float)) or limit <= 0:
        raise CapabilityError("max_age_hours must be a positive number")
    if getattr(ctx.journal, "ledger", None) is None:
        raise CapabilityError("brief.intake_status reads the canonical ledger: only a recommendation GREG delivered "
                              "under a receipt counts, and without the ledger none can be told from a planted file")
    delivered = _delivered(ctx.journal.ledger, asked)
    folder = briefs._deliver_dir(ctx)
    now = briefs.NOW().timestamp()
    matching, others, unusable, stale, planted, latest = 0, 0, 0, 0, 0, None
    for path in sorted(folder.glob(f"*-{KIND}-brief*.json"), key=lambda p: (p.stat().st_mtime, p.name)):
        try:
            if path.stat().st_size > MAX_TWIN_BYTES:
                raise ValueError("too large")
            twin = json.loads(path.read_bytes())
            markdown = path.with_suffix(".md")
            intact = (isinstance(twin, dict) and twin.get("markdown") == markdown.name and markdown.is_file()
                      and hashlib.sha256(markdown.read_bytes()).hexdigest() == twin.get("markdown_sha256")
                      and digest(twin.get("request")) == twin.get("request_digest"))
            receipt = delivered.get(markdown.resolve()) if intact else None
        except (OSError, ValueError):
            intact = False
        if not intact:
            unusable += 1
        elif twin["request_digest"] != asked:
            others += 1
        elif receipt is None:
            planted += 1
        elif not verify_delivery(receipt, ctx.deliver_root)[0]:
            unusable += 1
        elif (age := max(now - markdown.stat().st_mtime, 0.0) / 3600) > limit:
            stale += 1
        else:
            matching += 1
            latest = {"latest": markdown.name, "age_hours": round(age, 3), "sha256": twin["markdown_sha256"]}
    return {"kind": KIND, "request_digest": asked, "matching": matching, "for_other_requests": others,
            "too_old": stale, "unusable": unusable, "not_delivered_by_greg": planted,
            **(latest or {"latest": None, "age_hours": None})}


def verify_delivery(output: dict, deliver_root: Path | None, ledger=None, *, confined: bool = False) -> tuple[bool, str]:
    """Appraiser check: the delivered Markdown is exactly the render of the receipted inputs, and its twin is exactly
    the twin of those inputs. It opens no network and runs no test: ``confined`` and ``ledger`` (shared with the
    other delivering capabilities) change nothing here."""
    if not isinstance(output, dict) or not isinstance(output.get("inputs"), dict):
        return False, "receipt does not retain the recommendation's inputs"
    inputs = output["inputs"]
    if digest(inputs) != output.get("inputs_digest"):
        return False, "retained inputs do not match their digest"
    try:
        if digest(request(inputs["request"])) != output.get("request_digest") \
                or inputs.get("request_digest") != output.get("request_digest"):
            return False, "the receipted request does not match its digest"
        if inputs.get("renderer") != RENDERER:
            return False, (f"rendered by {inputs.get('renderer')!s:.40}; this appraiser renders {RENDERER}: the "
                           "file is not re-derivable here, so a fresh recommendation is needed, not a verdict on it")
        text = render(inputs)
    except (CapabilityError, KeyError, TypeError, ValueError, AttributeError) as exc:
        return False, f"the receipted inputs cannot be rendered ({type(exc).__name__})"
    expected = text.encode("utf-8")
    if hashlib.sha256(expected).hexdigest() != output.get("sha256"):
        return False, "receipt digest is not the render of its inputs"
    path = Path(str(output.get("path")))
    if deliver_root is None or Path(deliver_root).resolve() not in path.resolve().parents:
        return False, "delivered file is outside the delivery root"
    if not path.is_file() or path.read_bytes() != expected:
        return False, "delivered file differs from the render of the receipted inputs"
    twin = path.with_suffix(".json")
    if not twin.is_file() or twin.read_bytes() != twin_bytes(inputs, text, path.name):
        return False, "the JSON twin differs from the receipted inputs"
    return True, "delivered file and its twin equal the render of the receipted inputs"
