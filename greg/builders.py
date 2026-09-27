"""Capability Genesis, builder route: a coding agent writes the residual capability.

When no attached, detached or installed capability can perform a function a mission
needs, and the founder-signed mission declares that function's contract, GREG may
commission a builder. The contract is deliberately narrow and testable:

    run(text: str) -> JSON value        (one text file in, one derived value out)

Order of trust, from least to most:

1. **Builder** (untrusted): sees the description, signature and *public* examples only.
   ``ClaudeCodeBuilder`` runs the founder's installed Claude Code CLI headless with
   every tool disabled and a spend cap. It returns source text; it never touches disk.
2. **Static screen**: imports from a small pure-computation allow-list; no ``open``,
   ``eval``, ``exec``, ``__import__``, ``compile``, dunder attribute access or globals.
3. **Isolated execution**: every run of built code (verification *and* later use) is a
   separate ``python3 -I -S`` process with no network (seccomp / sandbox-exec), a
   scrubbed environment, a timeout and only the input text on stdin. Built code never
   runs inside the body, so it cannot reach the ledger, keys, secrets or grants.
4. **Frozen oracle**: public examples plus held-out vectors the founder signed into
   the mission before any candidate existed. Passing all of them is required.

A verified capability is registered VERIFIED with provenance (builder, model, prompt
digest, source digest, oracle digest, report) and is attached only by the existing
Genesis rule: founder-signed read-only ``auto_attach`` inside the cone, or a founder
CAPABILITY_ATTACH. The original mission then resumes. Building != attaching.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from greg.capabilities import CapabilityError, InvocationContext, _inside, run_isolated

ALLOWED_IMPORTS = {"re", "json", "math", "collections", "itertools", "string", "statistics", "unicodedata",
                   "functools", "operator", "datetime", "textwrap", "hashlib"}
FORBIDDEN_NAMES = {"open", "eval", "exec", "compile", "__import__", "globals", "locals", "vars", "input",
                   "breakpoint", "getattr", "setattr", "delattr", "memoryview", "help", "exit", "quit"}
MAX_SOURCE = 20_000
MAX_INPUT = 256 * 1024
RUN_TIMEOUT = 10

HARNESS = r'''
import builtins, json, sys
sys.setrecursionlimit(2000)
ALLOWED = set(json.loads(sys.argv[2]))
real_import = builtins.__import__
def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    if level or name.split(".")[0] not in ALLOWED:
        raise ImportError("import not allowed: " + name)
    return real_import(name, globals, locals, fromlist, level)
safe = {k: getattr(builtins, k) for k in dir(builtins) if k not in {
    "open", "eval", "exec", "compile", "__import__", "globals", "locals", "vars", "input", "breakpoint",
    "getattr", "setattr", "delattr", "memoryview", "help", "exit", "quit", "__loader__", "__spec__"}}
safe["__import__"] = guarded_import
source = open(sys.argv[1], encoding="utf-8").read()
namespace = {"__name__": "candidate", "__builtins__": safe}
exec(compile(source, "candidate.py", "exec"), namespace)
run = namespace.get("run")
payload = json.loads(sys.stdin.read())
out = []
for text in payload["inputs"]:
    try:
        value = run(text)
        json.dumps(value)
        out.append({"ok": True, "value": value})
    except Exception as exc:
        out.append({"ok": False, "error": type(exc).__name__})
sys.stdout.write(json.dumps(out))
'''


class BuildError(RuntimeError):
    pass


def screen(source: str) -> list[str]:
    """Static screen of candidate source. Returns problems (empty = admissible)."""
    problems = []
    if len(source) > MAX_SOURCE:
        return [f"source longer than {MAX_SOURCE} characters"]
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"syntax error: {exc.msg} at line {exc.lineno}"]
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run"]
    if len(functions) != 1 or len(functions[0].args.args) != 1:
        problems.append("must define exactly one top-level run(text) function")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                if name.split(".")[0] not in ALLOWED_IMPORTS:
                    problems.append(f"import of {name!r} is not allowed")
        elif isinstance(node, ast.Name) and (node.id in FORBIDDEN_NAMES or node.id.startswith("__")):
            problems.append(f"use of {node.id!r} is not allowed")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            problems.append(f"dunder attribute {node.attr!r} is not allowed")
        elif isinstance(node, (ast.Global, ast.Nonlocal, ast.AsyncFunctionDef, ast.Await)):
            problems.append(f"{type(node).__name__} is not allowed")
    return sorted(set(problems))


def execute(source_path: Path, inputs: list[str], *, timeout: int = RUN_TIMEOUT) -> list[dict]:
    """Run built code in a fresh isolated interpreter (no network, scrubbed env)."""
    with tempfile.TemporaryDirectory(prefix="greg-built-") as tmp:
        tmp = Path(tmp)
        (tmp / "harness.py").write_text(HARNESS)
        shutil.copyfile(source_path, tmp / "candidate.py")
        payload = json.dumps({"inputs": inputs})
        if len(payload) > MAX_INPUT * 4:
            raise CapabilityError("input exceeds the built-capability ceiling")
        proc = _run_with_stdin([sys.executable, "-I", "-S", str(tmp / "harness.py"), str(tmp / "candidate.py"),
                                json.dumps(sorted(ALLOWED_IMPORTS))],
                               cwd=tmp, data=payload.encode(), timeout=timeout)
    if proc.returncode:
        raise CapabilityError(f"built capability exited {proc.returncode}: "
                              f"{proc.stderr.decode('utf-8', 'replace')[-300:]}")
    try:
        results = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CapabilityError("built capability produced unreadable output") from exc
    if not isinstance(results, list) or len(results) != len(inputs):
        raise CapabilityError("built capability produced the wrong number of results")
    return results


def _run_with_stdin(argv, *, cwd: Path, data: bytes, timeout: int) -> subprocess.CompletedProcess:
    # run_isolated forbids stdin; built code needs its input, so pipe it through a file.
    stdin_file = cwd / "stdin.json"
    stdin_file.write_bytes(data)
    wrapped = [sys.executable, "-I", "-S", "-c",
               "import subprocess,sys;f=open(sys.argv[1],'rb');"
               "r=subprocess.run(sys.argv[2:],stdin=f,capture_output=True);"
               "sys.stdout.buffer.write(r.stdout);sys.stderr.buffer.write(r.stderr);sys.exit(r.returncode)",
               str(stdin_file), *argv]
    return run_isolated(wrapped, cwd=cwd, isolate_network=True, timeout=timeout)


def verify(source_path: Path, vectors: list[dict]) -> tuple[bool, dict]:
    """Judge a candidate against frozen vectors it never saw. Returns (passed, report)."""
    try:
        results = execute(source_path, [v["input_text"] for v in vectors])
    except (CapabilityError, subprocess.TimeoutExpired) as exc:
        return False, {"cases": len(vectors), "failures": [{"error": f"{type(exc).__name__}: {exc}"[:300]}],
                       "isolation": "separate no-network interpreter"}
    failures = []
    for index, (vector, result) in enumerate(zip(vectors, results)):
        if not result.get("ok"):
            failures.append({"case": index, "error": result.get("error")})
        elif result["value"] != vector["expected"]:
            failures.append({"case": index, "got": str(result["value"])[:80]})
    return not failures, {"cases": len(vectors), "failures": failures,
                          "isolation": "separate python -I -S process, no network, scrubbed env, timeout"}


def built_adapter(function_spec: dict, source_path: Path, source_sha256: str):
    """Adapter for a verified built capability: path in the read roots -> isolated run."""
    field = function_spec["output_field"]

    def adapter(params, ctx: InvocationContext):
        path = _inside(Path(params["path"]), ctx.read_roots + (ctx.workspace,))
        if not source_path.is_file() or hashlib.sha256(source_path.read_bytes()).hexdigest() != source_sha256:
            raise CapabilityError("built capability source changed since verification; quarantine required")
        data = path.read_bytes()
        if len(data) > MAX_INPUT:
            raise CapabilityError("file exceeds the built-capability input ceiling")
        result = execute(source_path, [data.decode("utf-8", errors="replace")])[0]
        if not result.get("ok"):
            raise CapabilityError(f"built capability raised {result.get('error')}")
        return {field: result["value"], "path": str(path)}
    return adapter


# -- builders -----------------------------------------------------------------------------

def build_prompt(request: dict, feedback: list[str] | None = None) -> str:
    lines = [f"Write a Python module that defines exactly one function: def run(text: str).",
             f"It implements the function `{request['function']}`: {request['description']}",
             f"It must return a JSON-serializable value ({request.get('returns', 'a value')}).",
             f"Allowed imports only: {', '.join(sorted(ALLOWED_IMPORTS))}. No file, network, process or eval "
             "access; no dunder attributes; no global statements. Pure computation on `text`.",
             "Examples (input -> expected):"]
    for example in request["examples"]:
        lines.append(f"- {json.dumps(example['input_text'])} -> {json.dumps(example['expected'])}")
    if feedback:
        lines.append("Your previous candidate failed these public checks; fix them:")
        lines.extend(f"- {item}" for item in feedback)
    lines.append("Reply with only the module source inside one ```python fenced block.")
    return "\n".join(lines)


def extract_source(reply: str) -> str:
    match = re.search(r"```(?:python)?\s*\n(.*?)```", reply, re.S)
    if not match:
        raise BuildError("builder reply contained no fenced source block")
    return match.group(1).strip() + "\n"


class ClaudeCodeBuilder:
    """The installed Claude Code CLI as a coding agent: no tools, no disk, bounded spend."""

    def __init__(self, binary: str | None = None, *, model: str | None = None, max_budget_usd: float = 1.00,
                 timeout: int = 300, runner=subprocess.run):
        self.binary = binary or shutil.which("claude")
        if not self.binary:
            raise BuildError("Claude Code CLI is not installed")
        self.model, self.max_budget_usd, self.timeout, self.runner = model, max_budget_usd, timeout, runner
        self.identity = "claude-code" + (f":{model}" if model else "")

    def build(self, request: dict, feedback: list[str] | None = None) -> dict:
        prompt = build_prompt(request, feedback)
        argv = [self.binary, "-p", "--output-format", "json", "--tools", "", "--no-session-persistence",
                "--strict-mcp-config", "--max-budget-usd", f"{self.max_budget_usd:.2f}"]
        if self.model:
            argv += ["--model", self.model]
        with tempfile.TemporaryDirectory(prefix="greg-builder-") as empty:  # nothing to read, nothing to write
            proc = self.runner(argv, input=prompt, capture_output=True, text=True, timeout=self.timeout, cwd=empty)
        if proc.returncode:
            raise BuildError(f"Claude Code exited {proc.returncode}: {(proc.stderr or proc.stdout)[-300:]}")
        result = json.loads(proc.stdout)
        if result.get("is_error"):
            raise BuildError(f"Claude Code reported an error: {str(result.get('result'))[:300]}")
        return {"source": extract_source(str(result.get("result", ""))), "builder": self.identity,
                "prompt_sha256": "sha256:" + hashlib.sha256(prompt.encode()).hexdigest(),
                "cost_usd": result.get("total_cost_usd")}


BUILDER_SYSTEM = ("You write one small, pure Python function to an exact contract. You have no tools. "
                  "Reply with only the module source in one fenced python block.")


class ModelBuilder:
    """A coding agent reached through ``greg.models.ModelRouter``: any vendor, same frozen contract.

    Source only comes back; screening, the held-out oracle and the isolated runtime judge it
    exactly as they judge the Claude Code builder. ``max_budget_usd`` is set by Genesis to what
    remains of the founder-signed build budget, and every API route bounds its worst-case spend
    to it (a route whose cost cannot be bounded is skipped). The identity names the true author.
    """

    def __init__(self, router, *, max_budget_usd: float = 1.00):
        self.router, self.max_budget_usd = router, max_budget_usd
        self.identity = "models"

    def build(self, request: dict, feedback: list[str] | None = None) -> dict:
        from greg.models import RouteError
        prompt = build_prompt(request, feedback)
        try:
            result = self.router.complete(BUILDER_SYSTEM, prompt, budget_usd=self.max_budget_usd)
        except RouteError as exc:
            spent = (getattr(self.router, "last", None) or {}).get("cost_usd") or 0.0
            raise BuildError(f"no model route produced a candidate: {exc}"[:300] + (f" (spent ${spent:.4f})"
                                                                                  if spent else "")) from exc
        return {"source": extract_source(result["text"]), "builder": "model:" + result["route"],
                "served_model": result.get("served_model"),
                "prompt_sha256": "sha256:" + hashlib.sha256(prompt.encode()).hexdigest(),
                "cost_usd": result.get("cost_usd"), "routes_tried": result.get("tried", [])}


class StaticBuilder:
    """Deterministic builder for tests and for a human-supplied implementation."""

    def __init__(self, *sources: str, identity: str = "static"):
        self.sources, self.identity, self.calls = list(sources), identity, []

    def build(self, request: dict, feedback: list[str] | None = None) -> dict:
        self.calls.append({"request": request, "feedback": feedback})
        if not self.sources:
            raise BuildError("static builder has no more candidates")
        source = self.sources.pop(0)
        return {"source": source, "builder": self.identity,
                "prompt_sha256": "sha256:" + hashlib.sha256(build_prompt(request, feedback).encode()).hexdigest(),
                "cost_usd": 0.0}
