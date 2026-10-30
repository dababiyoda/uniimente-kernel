"""The effect-call allowlist (MU-D) must fail on every way an unreviewed effect can enter greg/ or foundry/systems/.

Each mutant edits a scratch copy of the tree: a source module (a new effect call, an aliased import, a call moved
into a new function, an extra occurrence, an opener built around greg.egress's checks), the allowlist (an entry
removed, a stale or miscounted entry, an unknown capability), or the scanner itself (so its self-tests stay
load-bearing). A mutant is CAUGHT only when the named test fails and its output names the expected site.

    python scripts/ci/check_effect_call_allowlist_mutants.py
"""
from pathlib import Path
import json, os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
TEST = "tests/unit/test_effect_call_allowlist.py"
ALLOWLIST = "tests/security/effect-call-allowlist.json"
TREE, FORMED = f"{TEST}::test_every_effect_call_site_is_listed", f"{TEST}::test_allowlist_is_well_formed"
FORMS = f"{TEST}::test_every_import_form_and_call_shape_is_resolved"
QUIET = f"{TEST}::test_what_is_not_an_effect_is_not_listed"
FACTORY = f"{TEST}::test_an_opener_factory_in_another_module_is_followed"
SYSCTL = 'out = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)'


def append(text):
    return lambda source: source + text


def replace(*pairs):
    def mutate(source):
        for old, new in pairs:
            if source.count(old) != 1:
                raise LookupError(f"anchor not found exactly once: {old[:60]!r}")
            source = source.replace(old, new)
        return source
    return mutate


def allowlist(edit):
    def mutate(source):
        document = json.loads(source)
        edit(document)
        return json.dumps(document, indent=1)
    return mutate


def drop(section, module, qualname):
    def edit(document):
        kept = [e for e in document[section] if (e["module"], e["qualname"]) != (module, qualname)]
        if len(kept) == len(document[section]):
            raise LookupError(f"no {section} entry {module} :: {qualname}")
        document[section] = kept
    return edit


def entry(module, qualname, change):
    def edit(document):
        for e in document["allowed"]:
            if (e["module"], e["qualname"]) == (module, qualname):
                change(e)
                return
        raise LookupError(f"no allowed entry {module} :: {qualname}")
    return edit


# (name, file, mutation, test node, text the failure output must contain)
MUTANTS = [
    # -- an unreviewed effect enters the source ---------------------------------------------------------
    ("new effect call in a listed module", "greg/compute.py",
     append('\n\ndef _mutant_probe():\n    return subprocess.run(["true"])\n'),
     TREE, "UNLISTED effect call site greg/compute.py :: _mutant_probe :: subprocess.run"),
    ("new module with a network call", "greg/_mutant_new.py",
     lambda _: 'import socket\n\n\ndef dial():\n    return socket.create_connection(("example.org", 443))\n',
     TREE, "UNLISTED effect call site greg/_mutant_new.py :: dial :: socket.create_connection"),
    ("aliased from-import (from subprocess import run as r)", "greg/presence.py",
     append('\n\nfrom subprocess import run as r  # noqa: E402\n\n\ndef _mutant_alias():\n    return r(["true"])\n'),
     TREE, "UNLISTED effect call site greg/presence.py :: _mutant_alias :: subprocess.run"),
    ("aliased module import (import subprocess as sp)", "greg/presence.py",
     append('\n\nimport subprocess as sp  # noqa: E402\n\n\n'
            'def _mutant_module_alias():\n    return sp.Popen(["true"])\n'),
     TREE, "UNLISTED effect call site greg/presence.py :: _mutant_module_alias :: subprocess.Popen"),
    ("dynamic getattr on the module", "greg/compute.py",
     append('\n\ndef _mutant_getattr():\n    return getattr(subprocess, "run")(["true"])\n'),
     TREE, "UNLISTED effect call site greg/compute.py :: _mutant_getattr :: subprocess.run"),
    ("injected runner default", "greg/compute.py",
     append('\n\ndef _mutant_inject(runner=subprocess.run):\n    return runner(["true"])\n'),
     TREE, "UNLISTED effect call site greg/compute.py :: _mutant_inject :: subprocess.run (1 reference)"),
    ("effect call moved into a new function", "greg/compute.py",
     replace(("def memory_bytes() -> int | None:",
              ('def _sysctl():\n    return subprocess.run(["/usr/sbin/sysctl", "-n", "hw.memsize"], '
               'capture_output=True, text=True, timeout=5)\n\n\ndef memory_bytes() -> int | None:')),
             (SYSCTL, "out = _sysctl()")),
     TREE, "UNLISTED effect call site greg/compute.py :: _sysctl :: subprocess.run"),
    ("second occurrence in the same function", "greg/compute.py",
     replace((SYSCTL, SYSCTL + "\n            " + SYSCTL)),
     TREE, "COUNT MISMATCH greg/compute.py :: memory_bytes :: subprocess.run"),
    ("opener built around greg.egress's allowlist check", "greg/anchor.py",
     append("\n\ndef _mutant_unchecked(req):\n    return egress.opener().open(req, timeout=5)\n"),
     TREE, "UNLISTED effect call site greg/anchor.py :: _mutant_unchecked :: urllib.request.build_opener().open"),
    # -- the allowlist loses or misstates an entry --------------------------------------------------------
    ("allowed entry removed", ALLOWLIST, allowlist(drop("allowed", "greg/egress.py", "send")),
     TREE, "UNLISTED effect call site greg/egress.py :: send :: urllib.request.build_opener().open"),
    ("known_unmediated entry removed", ALLOWLIST, allowlist(drop("known_unmediated", "greg/body.py", "Body.appraise")),
     TREE, "UNLISTED effect call site greg/body.py :: Body.appraise :: subprocess.run"),
    ("stale entry", ALLOWLIST,
     allowlist(lambda d: d["allowed"].append({**d["allowed"][0], "qualname": "gone"})),
     TREE, "STALE allowed entry foundry/systems/build.py :: gone :: subprocess.run"),
    ("wrong count", ALLOWLIST, allowlist(entry("greg/organs.py", "_snapshot", lambda e: e.update(count=2))),
     TREE, "COUNT MISMATCH greg/organs.py :: _snapshot :: subprocess.run"),
    ("unknown capability served", ALLOWLIST,
     allowlist(entry("greg/workers.py", "appraise", lambda e: e.update(serves=["capability:worker.anything"]))),
     FORMED, "names no capability in greg.capabilities.BUILTINS"),
    ("justification emptied", ALLOWLIST,
     allowlist(entry("greg/workers.py", "appraise", lambda e: e.update(justification="ok"))),
     FORMED, "must say, in words grounded in the code"),
    # -- the scanner itself is weakened -------------------------------------------------------------------
    ("scanner ignores `import x as y`", TEST,
     replace(("self.names[alias.asname].add(alias.name)", "pass")), FORMS, "subprocess"),
    ("scanner ignores bare references", TEST,
     replace(("if isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load):", "if False:")),
     FORMS, "injected"),
    ("scanner ignores an opener's .open", TEST,
     replace(('if isinstance(func, ast.Attribute) and func.attr == "open" and self.builds_opener(func.value):',
              "if False:")), FACTORY, "build_opener().open"),
    ("scanner drops suffix matching (re-exported modules)", TEST,
     replace(("for start in range(len(parts)):", "for start in range(1):")), FORMS, "subprocess.run"),
    ("scanner reads annotations", TEST,
     replace(("if isinstance(node, ast.arg):", "if False:")), QUIET, "socket.socket"),
]


def purge_bytecode(repo: Path) -> None:
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def run(repo: Path, node: str) -> subprocess.CompletedProcess:
    purge_bytecode(repo)
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "--tb=short",
                           node], cwd=repo, env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=600, check=False)


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-effect-call-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        baseline = run(repo, TEST)
        if baseline.returncode != 0:
            print("BASELINE_FAILS", baseline.stdout[-2000:])
            return 1
        print("BASELINE passes")
        for name, relative, mutate, node, expected in MUTANTS:
            path = repo / relative
            original = path.read_text() if path.exists() else None
            try:
                path.write_text(mutate(original))
            except LookupError as exc:
                print("STALE", name, exc)
                invalid += 1
                continue
            try:
                result = run(repo, node)
            finally:
                path.write_text(original) if original is not None else path.unlink()
            caught = (result.returncode == 1 and f"FAILED {node}" in result.stdout and expected in result.stdout
                      and "ERROR collecting" not in result.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
