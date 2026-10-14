"""#51 Commissioning: coding agents write code, tests and docs in isolated branches against a frozen contract, and
only a change that passes CI becomes a proposal.

The Kernel already had the trust order for built code (greg/builders.py: untrusted builder, static screen,
isolated execution, frozen oracle) and the deficit loop that calls it (greg/genesis.py) — for one pure function
at a time, never touching disk. This extends the same order to a repository change:

  contract   frozen before any candidate exists: what to build, where it may write (the write cone), the public
             acceptance tests the agent sees, the held-out tests it does not (only their hash is published), the
             documentation it must leave, and the CI commands that decide. The contract's hash is the proposal's
             lineage
  branch     every commission works in its own git worktree on its own branch, cut from the repository head; the
             main checkout is never written to, and the branch is kept whether the commission succeeds or fails
  builder    pluggable: the Claude Agent SDK (adopted; runs the founder's authenticated Claude Code with a tool
             allow-list that excludes shells and the network, inside the worktree, under a turn and spend cap),
             the Claude Code CLI, or a static builder for tests. The builder returns files; it never runs them
  screen     the files are refused before CI if any lies outside the write cone or names a shell, socket,
             environment or dynamic-execution primitive; a refused round resets the worktree
  ci         the held-out tests are revealed into the worktree only now, then each CI command runs as a separate
             process with a scrubbed environment (no secret reaches an agent's CI), a timeout and the worktree as
             its only ground. Red CI returns the failing test names, not their bodies, as feedback for one more
             round; the number of rounds is bounded by the contract
  proposal   green CI produces a proposal: the branch, the patch (content-addressed, #36), the CI report, the
             revealed held-out tests (hash-matched to the contract) and a body rendered from the repository's own
             pull-request template. Nothing here merges: merging is a human act on the proposal

The exercise commissions against a temporary repository so it is deterministic and leaves this repository's
branches alone; the same engine takes any repository path.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from foundry.systems import cas

FORBIDDEN = {"subprocess": r"\bsubprocess\b", "socket": r"\bsocket\b", "os.system": r"\bos\.system\b",
             "os.environ": r"\bos\.environ\b|\bgetenv\b", "eval/exec": r"\b(eval|exec)\s*\(", "__import__": r"__import__",
             "urllib/requests": r"\b(urllib|requests|http\.client)\b", "ctypes": r"\bctypes\b"}
GIT_ENV = {"GIT_AUTHOR_NAME": "commission", "GIT_AUTHOR_EMAIL": "commission@uniimente.invalid", "GIT_COMMITTER_NAME": "commission",
           "GIT_COMMITTER_EMAIL": "commission@uniimente.invalid", "GIT_AUTHOR_DATE": "2026-10-13T12:00:00Z",
           "GIT_COMMITTER_DATE": "2026-10-13T12:00:00Z", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
CI_TIMEOUT = 120
PASSTHROUGH_ENV = ("PATH", "LANG", "LC_ALL", "PYTHONIOENCODING")


class CommissionError(RuntimeError):
    pass


def _canon(v) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":")).encode()


def _sha(v) -> str:
    return "sha256:" + hashlib.sha256(_canon(v)).hexdigest()


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env={**os.environ, **GIT_ENV})
    if check and proc.returncode:
        raise CommissionError(f"git {' '.join(args)}: {proc.stderr.strip()[:200]}")
    return proc.stdout


def screen(files: dict[str, str], cone: list[str]) -> list[str]:
    """Why these files may not even reach CI: outside the write cone, or naming a primitive the cone forbids."""
    problems = []
    for path, text in files.items():
        norm = Path(path).as_posix()
        if norm.startswith("/") or ".." in Path(norm).parts or norm not in cone:
            problems.append(f"{norm}: outside the write cone {cone}")
            continue
        if norm.endswith(".py"):
            for label, pattern in FORBIDDEN.items():
                if re.search(pattern, text):
                    problems.append(f"{norm}: names {label}")
    return problems


def scrubbed_env() -> dict:
    return {k: v for k, v in os.environ.items() if k in PASSTHROUGH_ENV}


class Commission:
    def __init__(self, root: Path, repo: Path):
        self.root, self.repo = Path(root), Path(repo).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if not (self.repo / ".git").exists():
            raise CommissionError(f"{self.repo} is not a git repository")

    def _state(self) -> dict:
        p = self.root / "commissions.json"
        return json.loads(p.read_text()) if p.exists() else {"contracts": {}, "commissions": {}}

    def _save(self, s: dict) -> None:
        (self.root / "commissions.tmp").write_text(json.dumps(s, sort_keys=True))
        (self.root / "commissions.tmp").replace(self.root / "commissions.json")

    # -- the contract is frozen first ----------------------------------------------------------
    def freeze(self, *, contract_id: str, purpose: str, write_cone: list[str], public_tests: dict[str, str],
               held_out_tests: dict[str, str], docs_required: list[str], ci: list[list[str]], max_rounds: int = 2) -> dict:
        s = self._state()
        if contract_id in s["contracts"]:
            raise CommissionError(f"contract {contract_id} is frozen already; a contract is never edited after freezing")
        if not ci or not write_cone or not held_out_tests:
            raise CommissionError("a contract needs a write cone, held-out tests and at least one CI command")
        for path in list(public_tests) + list(held_out_tests):
            if path not in write_cone and not path.startswith("tests/held_out/"):
                raise CommissionError(f"test path {path} is neither in the write cone nor under tests/held_out/")
        sealed = cas.put(self.root / "sealed", _canon(held_out_tests))
        contract = {"contract_id": contract_id, "purpose": purpose, "write_cone": sorted(write_cone), "public_tests": public_tests,
                    "held_out_sha256": sealed, "docs_required": docs_required, "ci": ci, "max_rounds": max_rounds,
                    "base": git(self.repo, "rev-parse", "HEAD").strip()}
        contract["contract_sha256"] = _sha(contract)
        s["contracts"][contract_id] = contract
        self._save(s)
        return {"contract_id": contract_id, "contract_sha256": contract["contract_sha256"], "held_out_sha256": sealed}

    def _worktree(self, contract: dict) -> tuple[Path, str]:
        branch = f"commission/{contract['contract_id']}"
        path = self.root / "worktrees" / contract["contract_id"]
        if path.exists():
            shutil.rmtree(path)
            git(self.repo, "worktree", "prune")
        if branch in git(self.repo, "branch", "--list", branch):
            git(self.repo, "branch", "-D", branch)
        git(self.repo, "worktree", "add", "-b", branch, str(path), contract["base"])
        return path, branch

    def _ci(self, worktree: Path, contract: dict, held_out: dict[str, str]) -> dict:
        for path, text in held_out.items():        # revealed only now, never shown to the builder
            target = worktree / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        report = {"commands": [], "docs": [], "green": True}
        for doc in contract["docs_required"]:
            file_, _, needle = doc.partition("#")
            ok = (worktree / file_).exists() and (needle == "" or needle in (worktree / file_).read_text())
            report["docs"].append({"requirement": doc, "ok": ok})
            report["green"] &= ok
        for argv in contract["ci"]:
            try:
                proc = subprocess.run(argv, cwd=worktree, env=scrubbed_env(), capture_output=True, text=True, timeout=CI_TIMEOUT)
                out, code = (proc.stdout + proc.stderr), proc.returncode
            except subprocess.TimeoutExpired:
                out, code = "timed out", 124
            failing = sorted(set(re.findall(r"FAILED (\S+)", out)))
            report["commands"].append({"argv": argv, "exit": code, "failing_tests": failing, "tail": out.strip()[-400:]})
            report["green"] &= code == 0
        return report

    def _proposal_body(self, contract: dict, branch: str, report: dict, builder: str) -> str:
        template = self.repo / ".github" / "pull_request_template.md"
        body = template.read_text() if template.exists() else "## Purpose\n\n## Reality status\n\n- [ ] Sandbox\n"
        fills = {"## Purpose": f"## Purpose\n\n{contract['purpose']}\n\nCommission `{contract['contract_id']}` "
                               f"(contract `{contract['contract_sha256']}`), built by `{builder}` on branch `{branch}`.",
                 "- Intent IDs or source references:": f"- Intent IDs or source references: contract {contract['contract_sha256']}",
                 "- [ ] Sandbox": "- [x] Sandbox"}
        for key, value in fills.items():
            body = body.replace(key, value, 1)
        body += ("\n\n## CI before proposal\n\n" + "\n".join(f"- `{' '.join(c['argv'])}` → exit {c['exit']}" for c in report["commands"])
                 + "\n" + "\n".join(f"- docs: `{d['requirement']}` → {'ok' if d['ok'] else 'missing'}" for d in report["docs"])
                 + "\n\nHeld-out tests revealed at CI time match the frozen contract hash. Merging is a human act.\n")
        return body

    # -- the commission -------------------------------------------------------------------------
    def run(self, contract_id: str, *, builder) -> dict:
        s = self._state()
        contract = s["contracts"].get(contract_id)
        if contract is None:
            raise CommissionError(f"no frozen contract {contract_id}")
        held_out = json.loads(cas.get(self.root / "sealed", contract["held_out_sha256"]))
        worktree, branch = self._worktree(contract)
        main_before = git(self.repo, "rev-parse", "HEAD").strip()
        rounds, feedback, status, report = [], None, "abandoned", None
        for n in range(1, contract["max_rounds"] + 1):
            built = builder.build({"contract": {k: v for k, v in contract.items() if k != "held_out_sha256"} |
                                   {"held_out_sha256": contract["held_out_sha256"]}, "worktree": str(worktree)}, feedback)
            files = built["files"]
            problems = screen(files, contract["write_cone"])
            if problems:
                git(worktree, "checkout", "--", ".")
                git(worktree, "clean", "-fdq")
                rounds.append({"round": n, "builder": built["builder"], "outcome": "refused_before_ci", "problems": problems})
                feedback = problems
                continue
            for path, text in files.items():
                (worktree / path).parent.mkdir(parents=True, exist_ok=True)
                (worktree / path).write_text(text)
            git(worktree, "add", "-A")
            git(worktree, "commit", "-q", "-m", f"commission {contract_id} round {n} by {built['builder']}")
            report = self._ci(worktree, contract, held_out)
            git(worktree, "checkout", "--", ".")   # the revealed held-out tests never become part of the proposal's diff
            git(worktree, "clean", "-fdq")
            failing = sorted({t for c in report["commands"] for t in c["failing_tests"]})
            rounds.append({"round": n, "builder": built["builder"], "outcome": "green" if report["green"] else "red",
                           "failing_tests": failing, "docs_missing": [d["requirement"] for d in report["docs"] if not d["ok"]]})
            if report["green"]:
                status = "proposed"
                break
            feedback = [f"held-out or public test failed: {t.split('::')[-1]}" for t in failing] + \
                       [f"documentation missing: {d['requirement']}" for d in report["docs"] if not d["ok"]]
        main_after = git(self.repo, "rev-parse", "HEAD").strip()
        record = {"contract_id": contract_id, "branch": branch, "status": status, "rounds": rounds,
                  "main_untouched": main_before == main_after == contract["base"], "ci": report}
        if status == "proposed":
            patch = git(self.repo, "format-patch", "--stdout", f"{contract['base']}..{branch}")
            record["proposal"] = {"patch_sha256": cas.put(self.root / "patches", patch.encode()),
                                  "diffstat": git(self.repo, "diff", "--stat", contract["base"], branch).strip().splitlines()[-1],
                                  "files": sorted(git(self.repo, "diff", "--name-only", contract["base"], branch).split()),
                                  "held_out_revealed_sha256": cas.put(self.root / "sealed", _canon(held_out)),
                                  "body": self._proposal_body(contract, branch, report, rounds[-1]["builder"]), "merged": False}
        s["commissions"][contract_id] = record
        self._save(s)
        return record


class StaticFilesBuilder:
    """Deterministic builder: a scripted sequence of file sets, one per round."""

    def __init__(self, *rounds: dict[str, str], identity: str = "static-agent"):
        self.rounds, self.identity, self.calls = list(rounds), identity, []

    def build(self, request: dict, feedback) -> dict:
        self.calls.append({"contract_sha256": request["contract"]["contract_sha256"], "feedback": feedback})
        if not self.rounds:
            raise CommissionError("static builder has no more rounds")
        return {"files": self.rounds.pop(0), "builder": self.identity}


class AgentSDKBuilder:
    """The Claude Agent SDK as the coding agent, confined to the worktree with no shell and no network.

    Runs the founder's authenticated Claude Code through ``claude_agent_sdk.query`` with ``cwd`` set to the
    commission's worktree, a tool allow-list of file tools only, a turn cap and a spend cap. The files it wrote
    are read back from the worktree and judged exactly like any other builder's. It needs the Claude Code CLI
    and the founder's own login; neither is read from the environment here, so ``available()`` says whether it
    can run at all.
    """

    identity = "claude-agent-sdk"
    ALLOWED_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]
    DISALLOWED_TOOLS = ["Bash", "WebFetch", "WebSearch", "Task", "NotebookEdit"]

    def __init__(self, *, model: str | None = None, max_turns: int = 12, max_budget_usd: float = 2.0, cli_path: str | None = None):
        self.model, self.max_turns, self.max_budget_usd, self.cli_path = model, max_turns, max_budget_usd, cli_path

    def options(self, worktree: str):
        from claude_agent_sdk import ClaudeAgentOptions
        return ClaudeAgentOptions(cwd=worktree, allowed_tools=list(self.ALLOWED_TOOLS), disallowed_tools=list(self.DISALLOWED_TOOLS),
                                  permission_mode="acceptEdits", max_turns=self.max_turns, max_budget_usd=self.max_budget_usd,
                                  model=self.model, cli_path=self.cli_path, env={},
                                  system_prompt="You implement exactly one frozen contract inside this worktree. Write only the files the "
                                                "contract allows. Do not run commands. Leave the documentation the contract requires.")

    @staticmethod
    def prompt(contract: dict, feedback) -> str:
        lines = [f"Contract {contract['contract_id']} ({contract['contract_sha256']}): {contract['purpose']}",
                 f"You may write only these paths: {contract['write_cone']}.",
                 f"Documentation required: {contract['docs_required']}.", "Public acceptance tests (held-out tests also exist; their hash is "
                 f"{contract['held_out_sha256']}):"]
        lines += [f"--- {p}\n{t}" for p, t in contract["public_tests"].items()]
        if feedback:
            lines += ["Your previous round failed:"] + [f"- {f}" for f in feedback]
        return "\n".join(lines)

    def available(self) -> bool:
        return bool(self.cli_path or shutil.which("claude"))

    def build(self, request: dict, feedback) -> dict:
        import asyncio
        from claude_agent_sdk import query
        if not self.available():
            raise CommissionError("Claude Code CLI is not installed; the SDK route cannot run here")
        worktree = Path(request["worktree"])
        before = {p.relative_to(worktree).as_posix(): p.read_bytes() for p in worktree.rglob("*") if p.is_file() and ".git" not in p.parts}

        async def _run():
            async for _ in query(prompt=self.prompt(request["contract"], feedback), options=self.options(str(worktree))):
                pass
        asyncio.run(_run())
        files = {}
        for p in worktree.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                rel = p.relative_to(worktree).as_posix()
                if before.get(rel) != p.read_bytes():
                    files[rel] = p.read_text()
        return {"files": files, "builder": self.identity + (f":{self.model}" if self.model else "")}


def _store(root: Path) -> dict:
    p = Path(root) / "commissions.json"
    return json.loads(p.read_text()) if p.exists() else {"contracts": {}, "commissions": {}}


QUERY_OPS = {"contracts": lambda a, r: {"contracts": [{k: c[k] for k in ("contract_id", "contract_sha256", "held_out_sha256", "write_cone")}
                                                      for _, c in sorted(_store(r)["contracts"].items())]},
             "commissions": lambda a, r: {"commissions": [{k: c[k] for k in ("contract_id", "branch", "status", "main_untouched")}
                                                          for _, c in sorted(_store(r)["commissions"].items())]},
             "proposal": lambda a, r: {"proposal": _store(r)["commissions"].get(a["contract_id"], {}).get("proposal")}}
APPLY_OPS: dict = {}      # freezing a contract and running an agent are founder-authorized acts on a repository, not free ops


def _template_lead(repo: Path) -> str:
    """First line of the repository's pull-request template (the proposal body must start with it)."""
    template = Path(repo) / ".github" / "pull_request_template.md"
    lines = template.read_text().splitlines() if template.exists() else []
    return lines[0] if lines else "## Purpose"


def seed_repository(path: Path) -> Path:
    """A small project with a package, a passing test, a README and the Kernel's own PR template."""
    path.mkdir(parents=True)
    (path / "pkg").mkdir(); (path / "tests").mkdir(); (path / ".github").mkdir()
    (path / "pkg" / "__init__.py").write_text("")
    (path / "pkg" / "pricing.py").write_text("def price(units: int, unit_cents: int) -> int:\n    return units * unit_cents\n")
    (path / "tests" / "test_pricing.py").write_text("from pkg.pricing import price\n\n\ndef test_price():\n    assert price(3, 250) == 750\n")
    (path / "README.md").write_text("# demo\n\n## Pricing\n\n`price(units, unit_cents)` multiplies.\n")
    template = Path(__file__).resolve().parents[2] / ".github" / "pull_request_template.md"
    (path / ".github" / "pull_request_template.md").write_text(template.read_text() if template.exists() else "## Purpose\n")
    (path / "conftest.py").write_text("")
    git(path, "init", "-q", "-b", "main")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "seed")
    return path


VAT_TESTS_PUBLIC = {"tests/test_vat.py": "from pkg.tax import vat\n\n\ndef test_vat_whole():\n    assert vat(10000, 2000) == 2000\n\n\n"
                                         "def test_vat_zero():\n    assert vat(0, 2000) == 0\n"}
VAT_TESTS_HELD_OUT = {"tests/held_out/test_vat_rounding.py": "from pkg.tax import vat\n\n\ndef test_half_rounds_up():\n    assert vat(1, 5000) == 1\n\n\n"
                                                             "def test_negative_rate_refused():\n    import pytest\n    with pytest.raises(ValueError):\n        vat(100, -1)\n"}
VAT_WRONG = "def vat(amount_cents: int, rate_bps: int) -> int:\n    return round(amount_cents * rate_bps / 10000)\n"
VAT_RIGHT = ("def vat(amount_cents: int, rate_bps: int) -> int:\n    \"\"\"VAT in integer cents, half rounded up.\"\"\"\n"
             "    if rate_bps < 0:\n        raise ValueError('rate must be non-negative')\n"
             "    return (amount_cents * rate_bps + 5000) // 10000\n")
README_WITH_TAX = "# demo\n\n## Pricing\n\n`price(units, unit_cents)` multiplies.\n\n## Tax\n\n`vat(amount_cents, rate_bps)` rounds half up.\n"


def exercise(root) -> dict:
    import sys
    root = Path(root)
    repo = seed_repository(root / "project")
    engine = Commission(root / "engine", repo)
    pytest_cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]
    secret_check = [sys.executable, "-c", "import os, sys; sys.exit(1 if 'FOUNDRY_SECRET' in os.environ else 0)"]
    os.environ["FOUNDRY_SECRET"] = "would-leak-if-ci-saw-the-parent-environment"
    try:
        cone = ["pkg/tax.py", "tests/test_vat.py", "README.md"]
        frozen = engine.freeze(contract_id="vat", purpose="Add VAT computation in integer cents with half-up rounding",
                               write_cone=cone, public_tests=VAT_TESTS_PUBLIC, held_out_tests=VAT_TESTS_HELD_OUT,
                               docs_required=["README.md### Tax"], ci=[pytest_cmd, secret_check], max_rounds=2)
        refusals = {}

        def refused(label, fn):
            try:
                fn()
                refusals[label] = None
            except CommissionError as exc:
                refusals[label] = str(exc)[:80]
        refused("refreeze", lambda: engine.freeze(contract_id="vat", purpose="x", write_cone=cone, public_tests={}, held_out_tests=VAT_TESTS_HELD_OUT,
                                                  docs_required=[], ci=[pytest_cmd]))
        refused("contract_without_held_out", lambda: engine.freeze(contract_id="nope", purpose="x", write_cone=cone, public_tests={},
                                                                    held_out_tests={}, docs_required=[], ci=[pytest_cmd]))
        refused("run_unfrozen", lambda: engine.run("ghost", builder=StaticFilesBuilder({})))

        # round 1 passes the public tests but not the held-out rounding test; round 2 passes everything
        agent = StaticFilesBuilder({"pkg/tax.py": VAT_WRONG, **VAT_TESTS_PUBLIC, "README.md": README_WITH_TAX},
                                   {"pkg/tax.py": VAT_RIGHT, **VAT_TESTS_PUBLIC, "README.md": README_WITH_TAX})
        vat = engine.run("vat", builder=agent)

        # an agent that reaches outside its cone, one that names a shell, one that skips the docs
        engine.freeze(contract_id="cone", purpose="Same contract, different agent", write_cone=cone, public_tests=VAT_TESTS_PUBLIC,
                      held_out_tests=VAT_TESTS_HELD_OUT, docs_required=["README.md### Tax"], ci=[pytest_cmd], max_rounds=1)
        cone_breach = engine.run("cone", builder=StaticFilesBuilder({"pkg/tax.py": VAT_RIGHT, "pkg/pricing.py": "def price(u, c):\n    return 0\n",
                                                                    ".github/workflows/ci.yml": "on: push\n"}, identity="greedy-agent"))
        engine.freeze(contract_id="shell", purpose="Same contract, different agent", write_cone=cone, public_tests=VAT_TESTS_PUBLIC,
                      held_out_tests=VAT_TESTS_HELD_OUT, docs_required=["README.md### Tax"], ci=[pytest_cmd], max_rounds=1)
        shell = engine.run("shell", builder=StaticFilesBuilder({"pkg/tax.py": "import subprocess\n" + VAT_RIGHT, **VAT_TESTS_PUBLIC,
                                                                "README.md": README_WITH_TAX}, identity="shelly-agent"))
        engine.freeze(contract_id="nodocs", purpose="Same contract, different agent", write_cone=cone, public_tests=VAT_TESTS_PUBLIC,
                      held_out_tests=VAT_TESTS_HELD_OUT, docs_required=["README.md### Tax"], ci=[pytest_cmd], max_rounds=1)
        nodocs = engine.run("nodocs", builder=StaticFilesBuilder({"pkg/tax.py": VAT_RIGHT, **VAT_TESTS_PUBLIC}, identity="terse-agent"))
    finally:
        os.environ.pop("FOUNDRY_SECRET", None)
    sdk = AgentSDKBuilder(max_turns=8, max_budget_usd=1.5)
    options = sdk.options(str(root / "project"))
    branches = sorted(b.strip("*+ ") for b in git(repo, "branch", "--list", "commission/*").splitlines())
    main_tree = sorted(git(repo, "ls-tree", "-r", "--name-only", "main").split())
    held_out_revealed = json.loads(cas.get(root / "engine" / "sealed", vat["proposal"]["held_out_revealed_sha256"]))
    return {"frozen": {"held_out_sha256": frozen["held_out_sha256"]},
            "vat": {"status": vat["status"], "rounds": [(r["round"], r["outcome"], r["failing_tests"]) for r in vat["rounds"]],
                    "feedback_named_tests_not_bodies": agent.calls[1]["feedback"],
                    "proposal_files": vat["proposal"]["files"], "diffstat": vat["proposal"]["diffstat"], "merged": vat["proposal"]["merged"],
                    "held_out_matches_contract": vat["proposal"]["held_out_revealed_sha256"] == frozen["held_out_sha256"]
                    and held_out_revealed == VAT_TESTS_HELD_OUT,
                    "held_out_not_in_proposal": not any(f.startswith("tests/held_out/") for f in vat["proposal"]["files"]),
                    "secret_scrubbed_from_ci": all(c["exit"] == 0 for c in vat["ci"]["commands"]),
                    # built from the repository's own template (its first line, whatever the template's current
                    # lead section is) with the purpose filled and the CI and debate sections kept
                    "body_from_repo_template": vat["proposal"]["body"].startswith(_template_lead(repo))
                    and "## Purpose" in vat["proposal"]["body"] and "## CI before proposal" in vat["proposal"]["body"]
                    and "## Five-role debate" in vat["proposal"]["body"]},
            "cone_breach": {"status": cone_breach["status"], "problems": cone_breach["rounds"][0]["problems"]},
            "shell": {"status": shell["status"], "problems": shell["rounds"][0]["problems"]},
            "nodocs": {"status": nodocs["status"], "docs_missing": nodocs["rounds"][0]["docs_missing"], "tests_green": nodocs["rounds"][0]["failing_tests"] == []},
            "branches_kept": branches, "main_untouched": all(c["main_untouched"] for c in (vat, cone_breach, shell, nodocs)),
            "main_tree_unchanged": main_tree == [".github/pull_request_template.md", "README.md", "conftest.py", "pkg/__init__.py", "pkg/pricing.py",
                                                 "tests/test_pricing.py"],
            "agent_sdk": {"configured": options.cwd == str(root / "project") and "Bash" in options.disallowed_tools and "Bash" not in options.allowed_tools,
                          "allowed_tools": options.allowed_tools, "permission_mode": options.permission_mode, "max_turns": options.max_turns,
                          "max_budget_usd": options.max_budget_usd, "live_route_run": False},
            "refusals": refusals}
