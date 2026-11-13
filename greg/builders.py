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
import os
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
import builtins, json, resource, sys, time
# The candidate's own CPU is bounded here: a loop dies by SIGXCPU and is judged as the candidate's failure.
# A wall-clock timeout is the host's only when the host cannot run an isolated no-op either (verify).
resource.setrlimit(resource.RLIMIT_CPU, (8, 9))
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
    started = time.process_time()
    try:
        value = run(text)
        json.dumps(value)
        out.append({"ok": True, "value": value, "cpu": round(time.process_time() - started, 4)})
    except Exception as exc:
        out.append({"ok": False, "error": type(exc).__name__, "cpu": round(time.process_time() - started, 4)})
sys.stdout.write(json.dumps(out))
'''


class BuildError(RuntimeError):
    """A build attempt produced no candidate. ``cost_usd`` is what the attempt was still billed (a withheld
    substituted answer, a reply without source), so Genesis books it against the signed build budget."""

    def __init__(self, message: str = "", *, cost_usd=None):
        super().__init__(message)
        self.cost_usd = cost_usd


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
    # Supervised: the wrapper and the harness it starts share one process group, killed when the run ends or
    # times out, so a candidate that hangs leaves nothing running behind it.
    return run_isolated(wrapped, cwd=cwd, isolate_network=True, timeout=timeout, stop_check=lambda: False)


def isolation_ready(timeout: int = RUN_TIMEOUT) -> None:
    """Raise a transient CapabilityError when the isolated runtime that judges built code cannot run now,
    so a host outage defers formation before any paid build attempt instead of failing the candidate."""
    with tempfile.TemporaryDirectory(prefix="greg-built-probe-") as tmp:
        try:
            proc = run_isolated([sys.executable, "-I", "-S", "-c", "pass"], cwd=Path(tmp), timeout=timeout)
        except subprocess.TimeoutExpired:
            raise CapabilityError("the isolated build verifier did not start in time",
                                  failure_class="transient") from None
    if proc.returncode:
        raise CapabilityError(f"the isolated build verifier exited {proc.returncode}", failure_class="transient")


def verify(source_path: Path, vectors: list[dict], *, timeout: int = RUN_TIMEOUT) -> tuple[bool, dict]:
    """Judge a candidate against frozen vectors it never saw. Returns (passed, report).

    A host outage (isolation unavailable, the whole run timing out) is no verdict on the candidate: it is
    raised as a transient CapabilityError. The candidate's own CPU is bounded by the harness."""
    try:
        results = execute(source_path, [v["input_text"] for v in vectors], timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # The candidate's CPU is bounded by the harness, but it can block without using any (a lock taken
        # twice). If the host still runs an isolated no-op, the hang is the candidate's; else the host's.
        isolation_ready()
        return False, {"cases": len(vectors), "isolation": "separate no-network interpreter",
                       "failures": [{"error": f"did not finish within {exc.timeout}s while the host was healthy"}]}
    except CapabilityError as exc:
        if exc.failure_class == "transient":
            raise
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


# -- attack stage (directive S22.A2, S35.A3): a candidate that passed the frozen oracle is attacked before it counts --
# One input's own CPU share. The harness kills a whole run at 8 s of CPU, so a candidate that spends more than this on
# one input would starve the rest of a mission's inputs; it is judged slow, never given the benefit of the doubt.
ATTACK_CPU_SECONDS = 2.0
_ATTACK_SPAN = MAX_INPUT // 2


def _kind(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "integer" if isinstance(value, int) else "number"
    return {str: "string", list: "array", dict: "object"}.get(type(value), "other")


def attack_inputs(examples: list[dict]) -> list[tuple[str, str]]:
    """Hostile inputs no frozen vector covers, as (label, text). Labels name the shape, never the founder's data.

    Generic shapes (empty, whitespace, control characters, decode-replacement characters, mixed scripts and bidi
    marks, one huge line, many blank lines) plus shapes derived from the contract's own public examples (CRLF and
    NUL-joined, without a trailing newline, and repeated to near the input ceiling). Deterministic: the same contract
    always yields the same attack."""
    seeds = [e["input_text"] for e in examples if isinstance(e.get("input_text"), str)]
    joined = "\n".join(seeds)
    attacks = [("empty", ""), ("whitespace only", " \t\n \n\t "), ("one newline", "\n"), ("NUL", "\x00"),
               ("control characters", "".join(chr(c) for c in range(1, 32)) * 4),
               ("decode-replacement characters", "�" * 64),
               ("mixed scripts, emoji and bidi marks", "é 漢字 🙂 ‮​  Ω"),
               ("one line at half the input ceiling", "a" * _ATTACK_SPAN),
               ("many blank lines", "\n" * 20_000)]
    if joined:
        attacks += [("examples joined with CRLF", "\r\n".join(seeds)),
                    ("examples joined with NUL", "\x00".join(seeds)),
                    ("examples without the trailing newline", joined.rstrip("\n")),
                    ("examples repeated to half the input ceiling",
                     (joined + "\n") * max(1, _ATTACK_SPAN // (len(joined) + 1)))]
    return attacks


def attack(source_path: Path, examples: list[dict], *, timeout: int = RUN_TIMEOUT) -> dict:
    """Attack a built candidate in the same isolated interpreter as verification, before it registers.

    It fails when, on any attack input, it raises, returns a value whose JSON kind the contract's examples never
    return, gives a different answer on a second run, or spends more than ``ATTACK_CPU_SECONDS`` of CPU. A host
    outage is no verdict (a transient CapabilityError), exactly as in ``verify``."""
    attacks = attack_inputs(examples)
    kinds = {_kind(e["expected"]) for e in examples if "expected" in e}
    if "number" in kinds:
        kinds.add("integer")                             # an integral float is still a number
    report = {"inputs": len(attacks), "failures": [], "wrong_kind": [], "nondeterministic": [], "slow": []}
    batch, size = [], 0

    def judge(batch):
        texts = [text for _, text in batch]
        try:
            first, second = execute(source_path, texts, timeout=timeout), execute(source_path, texts, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            isolation_ready()                            # raises (no verdict) only when the host cannot run either
            for label, _ in batch:
                report["slow"].append({"input": label, "error": f"did not finish within {exc.timeout}s"})
            return
        except CapabilityError as exc:
            if exc.failure_class == "transient":
                raise
            for label, _ in batch:
                report["failures"].append({"input": label, "error": str(exc)[:200]})
            return
        for (label, _), a, b in zip(batch, first, second):
            if not a.get("ok"):
                report["failures"].append({"input": label, "error": a.get("error")})
            elif kinds and _kind(a.get("value")) not in kinds:
                report["wrong_kind"].append({"input": label, "returned": _kind(a.get("value")),
                                             "expected": sorted(kinds)})
            if (a.get("ok"), a.get("value"), a.get("error")) != (b.get("ok"), b.get("value"), b.get("error")):
                report["nondeterministic"].append({"input": label})
            if max(float(a.get("cpu") or 0), float(b.get("cpu") or 0)) > ATTACK_CPU_SECONDS:
                report["slow"].append({"input": label, "cpu_seconds": max(a.get("cpu") or 0, b.get("cpu") or 0)})

    for label, text in attacks:
        if batch and size + len(text) > MAX_INPUT:
            judge(batch)
            batch, size = [], 0
        batch.append((label, text))
        size += len(text)
    if batch:
        judge(batch)
    report["passed"] = not (report["failures"] or report["wrong_kind"] or report["nondeterministic"]
                            or report["slow"])
    return report


def attack_feedback(report: dict) -> str:
    """What the builder learns from a failed attack: the shapes and failure classes, never an input's text."""
    parts = [f"raised {f['error']} on {f['input']}" for f in report["failures"][:4]]
    parts += [f"returned {w['returned']} (expected {'/'.join(w['expected'])}) on {w['input']}"
              for w in report["wrong_kind"][:2]]
    parts += [f"answered differently on a second run of {n['input']}" for n in report["nondeterministic"][:2]]
    parts += [f"was too slow on {s['input']}" for s in report["slow"][:2]]
    return ("your candidate passes the examples but fails adversarial input: " + "; ".join(parts)
            + ". Handle any text, including empty, huge and unusual input, deterministically and quickly")


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


def _billed_source(reply: str, cost_usd) -> str:
    try:
        return extract_source(reply)
    except BuildError as exc:   # a reply without source was still paid for
        raise BuildError(str(exc), cost_usd=cost_usd) from exc


class ClaudeCodeBuilder:
    """The installed Claude Code CLI as a coding agent: no tools, no disk, bounded spend.

    ``egress`` is set by a body with confined egress (#26): the CLI then runs in a network namespace whose only way
    out is the relay door, allowlisted for the Anthropic API host, like the ``claude-code`` model route."""

    def __init__(self, binary: str | None = None, *, model: str | None = None, max_budget_usd: float = 1.00,
                 timeout: int = 300, runner=subprocess.run, egress=None):
        self.binary = binary or shutil.which("claude")
        if not self.binary:
            raise BuildError("Claude Code CLI is not installed")
        self.model, self.max_budget_usd, self.timeout, self.runner = model, max_budget_usd, timeout, runner
        self.egress = egress
        self.identity = "claude-code" + (f":{model}" if model else "")

    def build(self, request: dict, feedback: list[str] | None = None) -> dict:
        prompt = build_prompt(request, feedback)
        argv = [self.binary, "-p", "--output-format", "json", "--tools", "", "--no-session-persistence",
                "--strict-mcp-config", "--max-budget-usd", f"{self.max_budget_usd:.2f}"]
        if self.model:
            argv += ["--model", self.model]
        from greg.models import CLI_NO_MODEL_FALLBACK, cli_authors, cli_cost, cli_reason, cli_report
        with tempfile.TemporaryDirectory(prefix="greg-builder-") as empty:  # nothing to read, nothing to write
            try:
                proc = (self.runner(argv, input=prompt, capture_output=True, text=True, timeout=self.timeout,
                                    cwd=empty, env={**os.environ, **CLI_NO_MODEL_FALLBACK})
                        if self.egress is None else self._behind_door(argv, prompt, empty))
            except subprocess.TimeoutExpired:
                # Killed at the timeout after it may have spent up to its cap: booked, never as zero.
                raise BuildError(f"Claude Code timed out after {self.timeout}s", cost_usd=self.max_budget_usd) from None
        result = cli_report(proc)        # printed with what the run cost even when the CLI exits 1 (every is_error)
        if result is None:
            if proc.returncode:
                raise BuildError(f"Claude Code exited {proc.returncode}: {(proc.stderr or proc.stdout)[-300:]}")
            raise BuildError("Claude Code produced unreadable output")
        cost = cli_cost(result, self.max_budget_usd)     # unknown spend books the cap, never zero
        if result.get("is_error") or proc.returncode or result.get("stop_reason") == "refusal":
            exited = f" (exit {proc.returncode})" if proc.returncode else ""
            raise BuildError(f"Claude Code reported an error{exited}: {cli_reason(result)[:300]}", cost_usd=cost)
        authors = cli_authors(result)
        if self.model and any(self.model not in a for a in authors):
            raise BuildError(f"Claude Code: requested {self.model}, the report names {authors}"[:300], cost_usd=cost)
        return {"source": _billed_source(str(result.get("result", "")), cost), "builder": self.identity,
                "prompt_sha256": "sha256:" + hashlib.sha256(prompt.encode()).hexdigest(),
                "cost_usd": cost}


    def _behind_door(self, argv: list, prompt: str, scratch: str):
        """The same confinement as ``models.ClaudeCodeRoute`` (its namespace and per-call relay), as its own identity."""
        import sys
        import urllib.parse
        from foundry.systems.relay_door import Door, door_argv
        from greg import model_child
        from greg.models import CLI_NO_MODEL_FALLBACK, RouteError, _namespace, _scoped_relay, cli_home
        env, runtime = cli_home(scratch)
        try:
            namespace = _namespace(scratch, readonly=(str(Path(self.binary).resolve().parent), *runtime))
        except RouteError as exc:
            raise BuildError(str(exc)) from None
        host = urllib.parse.urlsplit(model_child.BASE_URLS["anthropic"]).hostname
        with Door(_scoped_relay(self.egress, "genesis.claude-code", host), "genesis.claude-code") as door:
            return self.runner(namespace + door_argv(sys.executable, door.fd, argv), input=prompt, capture_output=True,
                               text=True, timeout=self.timeout, cwd=scratch, pass_fds=[door.fd],
                               env={**env, **CLI_NO_MODEL_FALLBACK})


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
        except RouteError as exc:   # a withheld (e.g. substituted) answer was still billed: carry the spend
            spent = (getattr(self.router, "last", None) or {}).get("cost_usd") or 0.0
            raise BuildError(f"no model route produced a candidate: {exc}"[:300] + (f" (spent ${spent:.4f})"
                                                                                  if spent else ""),
                             cost_usd=spent or None) from exc
        return {"source": _billed_source(result["text"], result.get("cost_usd")),
                "builder": "model:" + result["route"],
                "served_model": result.get("served_model"), "requested_model": result.get("requested_model"),
                "substituted": result.get("substituted"),   # None: the route did not or could not check
                "model_digest": result.get("model_digest"),
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
