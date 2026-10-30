# Effect-call allowlist (MU-D)

Founder directive of 2026-10-28 (OPUS MAXIMUS build), unit MU-D, items S37 and S67. Base: `b1950be2` (#196 head).
Round 1 was `78e986bb`..`f4028f3d`. Round 2 answers the fourteen findings of two independent reviews (below).

## What changed

Before this change, nothing in the tree listed where `greg/` and `foundry/systems/` start processes, open
connections or listen. A new spawn or connection that bypassed the capability manifests, the Gate, the worker envelope
or the #26 relay could only be noticed by a reviewer reading the diff.

- `tests/unit/test_effect_call_allowlist.py` parses every `.py` file under `greg/` and `foundry/systems/` with `ast`
  and finds each effect site:
  - child processes: `subprocess.run|Popen|call|check_call|check_output|getoutput|getstatusoutput`,
    `os.system|popen|fork|forkpty|startfile|spawn*|exec*|posix_spawn*` (`posix.*` keyed as `os.*`),
    `asyncio.create_subprocess_exec|shell` (also from `asyncio.subprocess`), `pty.spawn|fork`,
    `multiprocessing.Process|Pool`, `concurrent.futures.ProcessPoolExecutor`, `webbrowser.open*|get`;
  - outbound connections: `urllib.request.urlopen|urlretrieve`, `urllib.request.build_opener|OpenerDirector` and the
    `.open` of the opener they build (called, held as a value, or reached through `getattr`, including through an
    opener factory in another module), `http.client.HTTP(S)Connection`, `socket.socket|create_connection`,
    `asyncio.open_connection|open_unix_connection`, the stdlib SMTP/FTP/POP3/IMAP/XML-RPC clients, and the I/O entry
    points (request functions, sessions, clients, pools, transports) of `requests`, `httpx`, `httpx2`, `urllib3` and
    `aiohttp`, not their exceptions or constants;
  - inbound listeners: `socket.create_server`, `asyncio.start_server|start_unix_server`,
    `http.server.HTTPServer|ThreadingHTTPServer` and the `socketserver` servers;
  - an event loop's `subprocess_exec|subprocess_shell|create_connection|create_server|...` on a receiver the scan
    cannot name.

  `os.kill` is excluded.
- Names are resolved through every binding a module makes: `import x as y`, `from x import y as z`, `sp = subprocess`,
  `RUN = subprocess.run` (walrus and tuple pairs too), `importlib.import_module("…")`, `__import__` with or without
  `fromlist`, `sys.modules["…"]`, `getattr(x, "literal")`, and a name another scanned module imported or bound,
  followed module to module. A bare reference (`runner=subprocess.run`, `send = opener.open`) counts like a call.
  A star import fails the check and cannot be listed. Annotations are read where Python 3.11 evaluates them
  (parameter, return, module and class level, in a module without `from __future__ import annotations`); in a type
  position (an evaluated annotation, an `except` clause, isinstance's class argument, a `case` class pattern) only a
  call counts. An attribute of an effect callable (`subprocess.run.__doc__`) is not a site; `.__call__` is.
- **Wrappers.** The allowlist's `wrappers` section names in-tree functions that pass an effect on with no check of their
  own: `greg.egress.send` and `greg.egress.opener` (no https or allowlist check), `run_isolated` when `isolate_network`
  is not `True`, its private `_spawn` and `_launch`, and `greg.workers.supervised_run`. Every call or reference to a
  wrapper is a site, keyed by the wrapper's dotted name, so a new caller of `egress.send` fails CI like a new
  `urlopen`. `exempt_when` is checked against the function's signature: the keyword must be keyword-only with that
  literal as its default.
- Each site is keyed by (module path, enclosing qualname, callee) with an occurrence count, never by line number.
- `tests/security/effect-call-allowlist.json`: 92 keys and 105 occurrences across 27 `greg/` and 14 `foundry/systems/`
  modules (round 1: 67 keys, 79 occurrences); 6 wrappers.
  - 90 `allowed` entries. Each names what it serves as `kind:detail`: `capability:` (checked against
    `greg.capabilities.BUILTINS`), `confinement:`, `egress:`, `supervised-worker:`, `model-route:`, `founder-command:`,
    `operator:` (a command a person runs) or `installer:`, plus a justification taken from the code.
  - 2 `known_unmediated` entries (findings, below). Each must serve `body-loop:<the schedule that reaches it>`;
    `body-loop:` is refused under `allowed`. (Round 1's `mission-appraisal:` kind is replaced by it.)
  - Listing a site authorizes nothing.
- The test fails on an unlisted site (with a ready-to-paste entry, the `known_unmediated` alternative and the
  `wrappers` advice), a star import, a stale entry or wrapper, a count mismatch, and malformed entries (unknown serves
  kind, capability id not in BUILTINS, duplicate key, `body-loop` in the wrong section, a justification under six
  words, an `exempt_when` whose default does not match).
- `scripts/ci/check_effect_call_allowlist_mutants.py` runs the mutants.

No source module changed.

**Why `tests/security/`.** `governance/integrity/` holds founder-signed records (its `authorizations.json` changes only
by an Ed25519 `INTEGRITY_AUTHORIZE` envelope), so an unsigned list there would read as an authorization. `contracts/`
holds wire schemas; `tests/data/` does not exist. `tests/security/` already holds the security suite's data
(`security-tests.yaml`); this file is the same kind of thing: an oracle a test reads, with no authority.

## Findings (real, not fixed here: no source behaviour changes in this unit)

- **known_unmediated `greg/body.py :: Body.appraise :: subprocess.run`.** The body runs `python -m greg.appraisal` on
  its own schedule whenever a mission closes. No manifest, Gate or worker envelope stands behind it, and the child has
  no network or filesystem confinement. It re-runs only the read-only `REOBSERVABLE` sensors.
- **known_unmediated `greg/compute.py :: memory_bytes :: subprocess.run`** (round 2, MUD-5/F4). On macOS `Body.run`
  spawns `/usr/sbin/sysctl -n hw.memsize` every `telemetry_every` active ticks through `record_telemetry`, with no
  person-run command behind it. Fixed, read-only argv. Reproduced: a body run for two ticks with the platform set to
  `darwin` recorded `['/usr/sbin/sysctl', '-n', 'hw.memsize']`.
- **`greg/cognition/bridge.py :: run_worker`** (MUD-4/F3). With a founder-selected Ollama model and a problem that has
  sources or a schedule request, it calls `run_isolated(isolate_network=False)`, so the cortex worker runs with full
  network, not loopback only. Reproduced: `run_isolated(..., isolate_network=False)` let a child create a socket;
  `True` gave `PermissionError`. Round 1's `_launch` justification ("every in-tree caller keeps isolate_network=True")
  was false and is corrected; the call is now a listed `run_isolated` site.
- `greg/mcp_login.py :: login` and `register_token` run httpx2 clients in the founder's own CLI process, not behind
  the relay (founder-run `greg mcp login` / `greg mcp token`).
- Observations kept from round 1: `greg/organs.py :: _snapshot` runs `git status` without `read_only_git`'s hardening;
  `greg/cognition/genomes/admission.py :: source_dirty` runs `git hash-object`, which applies configured clean filters.

Reachability of the operator-only entries was re-audited with a reverse search over callers by terminal name across
`greg/`, `foundry/` and `cortex/`, then each hit was checked by hand: only `memory_bytes` is reached by the body loop.

## Review findings and dispositions (round 2)

| Id | Disposition |
| --- | --- |
| MUD-1 | fixed: wrappers (`egress.send`, `egress.opener`, …), `.open` held as a value, `getattr(opener, "open")` |
| MUD-2 | fixed: names followed through every scanned module's bindings; the import binding itself is not recorded (it runs nothing; the call in the importing module is) |
| MUD-3, F2 | fixed: canonical homes, the added stdlib callees, star imports fail, `sys.modules`, `fromlist`, rebinding by assignment |
| MUD-4, F3 | fixed: `_launch` justification corrected; `run_isolated` with `isolate_network` other than `True` is a wrapper site |
| MUD-5, F4 | fixed: `memory_bytes` is `known_unmediated` under `body-loop:` |
| MUD-6 | fixed: evaluated annotations are read |
| MUD-7 | fixed: HTTP entry points only; type positions and attributes of effect callables are not sites |
| F1 | fixed: httpx2 (and urllib3, aiohttp); four sites listed |
| F5 | not a code defect; the claim is withdrawn (see limitations) |
| F6 | fixed: `mission-appraisal:` replaced by `body-loop:`, restricted to `known_unmediated` |
| F7 | fixed: listeners are scanned; eight sites listed |

## Commands and results

All runs used `PYTHONDONTWRITEBYTECODE=1 /home/user/venv311/bin/python -B -m pytest -q -p no:cacheprovider` unless
stated. Round 2's fail-before ran in a detached worktree at `f4028f3d` (round 1's head), removed afterwards.

| Step | Where | Result |
| --- | --- | --- |
| R1 | `b1950be2`, round 1's test only | 2 failed, 4 passed (no inventory at base) |
| R1 | `b1950be2` + `subprocess.run` appended to `greg/compute.py`, existing `test_greg_platform.py` and `test_greg_founder_asks.py` | 69 passed: nothing noticed |
| R1 | same, with round 1's test | 1 failed: `UNLISTED … greg/compute.py :: _unreviewed_probe :: subprocess.run` |
| R2 | `f4028f3d` scanner + round 2's six new self-tests | **6 failed**: missed forms (socket 2/3, opener `.open` 2/5, urlopen 3/4, …), 7 false positives (`requests.codes.ok`, `httpx.HTTPStatusError`, …), re-exports missed, no wrapper support (`TypeError`), star import missed, `body-loop` unchecked |
| R2 | `f4028f3d` tree + round 2's test, round 1's allowlist | **2 failed**: 12 `UNLISTED` (4 httpx2, 8 listeners) and `mission-appraisal` malformed |
| R2 | `f4028f3d` tree, round 2's mutants script against round 1's test and allowlist | **all 14 new source mutants SURVIVE** (rebinding, re-export, star import, `sys.modules`, `asyncio.subprocess`, `urlretrieve`, `open_connection`, httpx2, listener, annotation, `.open` held, `getattr(opener, "open")`, `egress.send` caller, `run_isolated(isolate_network=False)`); round 1's 9 source, 6 allowlist and 3 scanner mutants are caught; the other 19 need round-2 structures and do not apply (18/51) |
| R2 | a scratch copy of this branch with both halves of the 8bdca11f `browser.session` fix reverted (F5) | 9 passed: not caught, as the limitations say |

Pass-after on this branch:

- `tests/unit/test_effect_call_allowlist.py`: **9 passed**. `tests/unit/test_greg_egress.py` and
  `tests/unit/test_founder_effect_doctrine.py` with it: **30 passed**. `python scripts/ci/check_authority_singleton.py`:
  "exactly one source of authority for each governed artifact".
- `python scripts/ci/check_effect_call_allowlist_mutants.py` at `5c6116a2`: **51/51 caught**, exit 0, 6m25s (round 1: 20/20). Each mutant must fail its named test with
  output naming the expected site; the unmutated scratch copy passes first.
  - 23 source mutants: a new call; a new socket module; `from subprocess import run as r`; `import subprocess as sp`;
    `sp = subprocess`; a name re-exported by another scanned module; a star import; `sys.modules`; `getattr`; an
    injected default; a call moved into a new function; a second occurrence; `asyncio.subprocess`; `urlretrieve`;
    `asyncio.open_connection`; `httpx2.post`; a `ThreadingHTTPServer`; an effect in an evaluated return annotation;
    `egress.opener().open`; `.open` held as a value; `getattr(opener, "open")`; a new `egress.send` caller; a new
    `run_isolated(isolate_network=False)`.
  - 10 allowlist mutants: an entry removed; each `known_unmediated` entry removed; a `body-loop` finding filed as
    allowed; a stale entry; a wrong count; an unknown capability; a justification emptied; a wrapper undeclared; an
    `exempt_when` that disagrees with the signature.
  - 18 scanner mutants, each disabling one rule so the self-tests stay load-bearing.
- `ruff check --line-length 120` on both changed Python files (one-line imports in the script, as in its siblings):
  clean. The tree scan takes about 10 s on this shared 4-core machine.

## Limitations

The scan is static and reads only `greg/` and `foundry/systems/`. It does not see:
- effects inside third-party libraries (model SDKs, the MCP SDK, Playwright, Chromium). The `browser.session` WebSocket
  bypass fixed in 8bdca11f lived there and in the `CONFINED_EGRESS` policy set; reverting that fix leaves this check
  green. Round 1's product statement that it now catches that class was wrong;
- code run from a string in a child (`python -c`); the spawn that runs it is listed;
- names imported from modules outside the scanned tree (a `cortex/` helper re-exporting `subprocess.run` is matched
  only as `x.subprocess.run`), `importlib.import_module` or `getattr` with a non-literal name, `ctypes` calls,
  `multiprocessing.get_context(...)` objects, and `socket.fromfd` (it wraps an existing descriptor);
- callers of functions that wrap an effect but are not declared wrappers: the reachability claims in those entries'
  justifications ("exercise() only", "reached only from …") come from reading code and are not machine-checked.

Name binding is flow-insensitive, so a reused local name may over-report. The mutants script is not a step in
`.github/workflows/canonical-ci.yml` (outside this unit's scope); the test itself runs in CI job 1's full pytest run.

## Reality level

UNIT-TESTED: static analysis plus mutation testing on scratch copies. Two runtime probes reproduced findings
(`run_isolated` network; the body loop's `sysctl` spawn, with the spawn intercepted). No runtime effect was blocked,
nothing ran on a founder device, and no authority, capability or behaviour changed.

Rollback: revert the commits. The three files have no dependents.
