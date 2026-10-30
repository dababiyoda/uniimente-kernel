# Effect-call allowlist (MU-D)

Founder directive of 2026-10-28 (OPUS MAXIMUS build), unit MU-D, items S37 and S67. Base: `b1950be2` (#196 head).
Round 1 was `78e986bb`..`f4028f3d`. Round 2 answers the fourteen findings of two independent reviews (below).
The branch has since merged #196 three times, at `4dc0d581`, `638457a4` and `a986fc74`; the merges and the one site
the base added are under "Merges of the PR base" below.

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
- `tests/security/effect-call-allowlist.json`: 93 keys and 106 occurrences across 28 `greg/` and 14 `foundry/systems/`
  modules (round 2: 92 keys, 105 occurrences, 27 `greg/` modules; round 1: 67 keys, 79 occurrences); 6 wrappers.
  - 90 `allowed` entries. Each names what it serves as `kind:detail`: `capability:` (checked against
    `greg.capabilities.BUILTINS`), `confinement:`, `egress:`, `supervised-worker:`, `model-route:`, `founder-command:`,
    `operator:` (a command a person runs) or `installer:`, plus a justification taken from the code.
  - 3 `known_unmediated` entries (findings, below; round 2 had 2, the third came with the base's licensing code).
    Each must serve `body-loop:<the schedule that reaches it>`; `body-loop:` is refused under `allowed`. (Round 1's
    `mission-appraisal:` kind is replaced by it.)
  - Listing a site authorizes nothing.
- The test fails on an unlisted site (with a ready-to-paste entry, the `known_unmediated` alternative and the
  `wrappers` advice), a star import, a stale entry or wrapper, a count mismatch, and malformed entries (unknown serves
  kind, capability id not in BUILTINS, duplicate key, `body-loop` in the wrong section, a justification under six
  words, an `exempt_when` whose default does not match).
- `scripts/ci/check_effect_call_allowlist_mutants.py` runs the mutants.

No source module changed, in any round or merge.

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
- **known_unmediated `greg/licensing.py :: system_binary :: subprocess.run`** (base merge, details below). Genesis
  runs `dpkg-query -S <binary>` from the body's own tick to read an installed tool's DEP-5 license. The argv, the 5 s
  timeout and the scrubbed environment are fixed; the executable is found on the body's ambient PATH and runs
  unconfined with the body's privileges. A recorded finding, not an approval: being listed does not make the spawn
  acceptable, it stops it growing unseen.
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
That audit was of round 2's tree (`b1950be2`); `system_binary` arrived later with the base and is filed above.
`a986fc74` added `fs.search` to `greg/appraisal.py`'s `REOBSERVABLE` set. It is a read-only, streamed file read, so
the `Body.appraise` reason ("it re-runs only the read-only `REOBSERVABLE` sensors") still holds.

## Merges of the PR base

| Merge | Base merged | Conflicts | New effect sites | Result |
| --- | --- | --- | --- | --- |
| `275e9d86` | #196 at `4dc0d581` (66 base commits since `b1950be2`, 95 files) | none: no file changed on both sides | 1: `greg/licensing.py :: system_binary :: subprocess.run` | committed with the scan red on that site, left unlisted pending this classification |
| `10d8fafa` | #196 at `638457a4` (#209's whole-output judgment adopted; 25 commits, 19 files) | none: no file changed on both sides; `foundry/owned-source.json` was not touched by either side, so `refresh_owned_source.py` was not run | 0 | `system_binary` is still the only unlisted site |
| `640e6eb9` | #196 at `a986fc74` (#228's faithful text and #229's section IX adopted; 29 commits, 19 files) | none: no file changed on both sides; only the base changed `foundry/owned-source.json` (2 lines), so there was no conflict to resolve. `refresh_owned_source.py`, run on a scratch checkout of the merge, added and removed nothing | 0 | the scan passes with the `system_binary` entry from `77d5e9b8`; no stale entry, no count mismatch |

**`638457a4` (#209).** It changes five scanned modules: `greg/appraisal.py`, `greg/authority.py`,
`greg/goal_gravity.py`, `greg/missions.py` and `greg/pipeline.py`. The diff was read for each. What it adds is
judgment logic and imports of other `greg` modules (`greg.missions`, `greg.authority`) and of `math`; it starts no
process, opens no connection, listens nowhere and calls no declared wrapper. The scan agrees: before the licensing
entry it reported the same single unlisted site as at `4dc0d581`, with no stale entry and no count mismatch.

**`a986fc74` (#228, #229).** It changes eight scanned modules: `greg/appraisal.py`, `greg/business_loop.py`,
`greg/capabilities.py`, `greg/missions.py`, `greg/planner.py` and `greg/templates.py`, and adds `greg/textform.py`
and `greg/textquery.py`. The diff was read for each. What it adds:
- file reads: `capabilities.bounded_read` and `textquery`'s streamed read open a path with
  `os.open(O_RDONLY | O_NONBLOCK | O_NOFOLLOW)` and check the descriptor is a regular file. Reading a file is not an
  effect under this unit's rule (a child process, a connection or a listener);
- decoding and normalization (`faithful_text`, `textform.canon`), and the cut and undecided fields that `run_cli`,
  `http_get`, `browser_render` and `fs.read` now return. Their spawns and connections are the ones already listed,
  with unchanged counts;
- a new read-only capability, `fs.search`, its planner route and its mission template; judge changes in
  `greg/missions.py`; and a watched sensing block. The watch re-reads a blocked mission's sensors through the
  existing `_observe` and returns (WAITING or RESUMED) before the self-repair branch, so it opens no new path to
  `Genesis` or `system_binary`. No added line calls `_form`, `genesis`, `licensing` or `_self_repair`.

It starts no process, opens no connection, listens nowhere and calls no declared wrapper. The scan agrees: with the
entries from `77d5e9b8`, **9 passed** on the merged tree, so nothing is unlisted or stale and no count changed.
No new site was classified, and no entry was added.

**`4dc0d581`: the licensing site.** The base added it in `bd7e3f9e` (#201/#230, 2026-10-22, "GREG reads PDFs on the
mission path; acquired system binaries carry their DEP-5 license"); that commit is not in `b1950be2`, where this
unit was seeded, and reached #196 with the #201/#230 adoption before `4dc0d581`. Line numbers below are from the
merged tree at `10d8fafa`. `a986fc74` changed none of `greg/licensing.py`, `greg/genesis.py`, `greg/body.py` or
`greg/goal_gravity.py`, so their numbers hold at `640e6eb9`; `greg/missions.py` grew, and its numbers at `640e6eb9`
are `_step` :2008 (`_form` at :2113), `_deficit` :2732 (:2741) and `_after_outage` :2856 (:2871).

- The call. `system_binary` (greg/licensing.py:679) resolves `dpkg = shutil.which("dpkg-query")` (:684) on the body
  process's own PATH and runs `subprocess.run([dpkg, "-S", real], capture_output=True, text=True,
  timeout=DPKG_TIMEOUT, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})` (:689; `DPKG_TIMEOUT = 5`, :564). It is plain
  `subprocess.run`, not `run_isolated`, and no capability manifest, Gate decision, worker envelope or person-run
  command stands behind it.
- Who reaches it: the body, on its own schedule.
  - Missions: `Body.tick` (greg/body.py:947, `engine.tick` at :965) -> `MissionEngine._step` (missions.py:1920,
    `_form` at :2025), `_deficit` (:2626, `_form` at :2635) or `_after_outage` (:2750, `_form` at :2765) ->
    `Genesis.resolve` (genesis.py:1238; installed-software rung, `_manifest_for` at :1331) -> `_manifest_for`
    (:1992, which calls both at :2012) -> `_binary_license` (:665, calling `system_binary` at :667) and `_companions`
    (:673, `_binary_license` at :680) -> `system_binary`.
  - Goal Gravity: `Body.tick` -> `goal_gravity.tick` (body.py:962; goal_gravity.py:1361) -> `_tick` (:1384) ->
    `_form_requested` (:1243, called at :1411) -> `Genesis.form_for_goal` (goal_gravity.py:1270) -> `resolve`
    (genesis.py:1234) -> the same chain. It runs only when a founder-signed goal record exists.
  - A second path, `catalog_adapter` -> `licensing.requalify_binary` (genesis.py:607, licensing.py:1195), returns at
    once while `ACTIVE_BINARY_POLICY` is `"P0"` (licensing.py:980); only the draft `"P4c"` would reach the spawn.
  - Runtime trace on `10d8fafa` (a scratch pytest plugin wrapping `subprocess.run`, not committed):
    `tests/unit/test_greg_missions.py::test_capability_genesis_acquires_installed_tool_and_resumes_mission` passed and
    recorded one spawn, `['/usr/bin/dpkg-query', '-S', '/usr/bin/sha256sum']` with env
    `{PATH: /usr/bin:/bin, LC_ALL: C}`, from `body.py:965 tick -> missions.py:1665 tick -> :2038 _step -> :2330
    _observe -> :2635 _deficit -> :2655 _form -> genesis.py:1331 resolve -> :2012 _manifest_for -> :667
    _binary_license -> licensing.py:689 system_binary`.
  - The same trace on `640e6eb9` recorded the same single spawn, argv and env, from `body.py:965 tick ->
    missions.py:1753 tick -> :2126 _step -> :2421 _observe -> :2741 _deficit -> :2761 _form -> genesis.py:1331
    resolve -> :2012 _manifest_for -> :667 _binary_license -> licensing.py:689 system_binary`.
- What is bounded and what is not. The argv shape, the 5 s timeout and the child's scrubbed environment are fixed.
  The choice of executable and its confinement are not. `installed_binary` (greg/capabilities.py:1290) searches only
  `/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin`; `system_binary` searches whatever PATH the body inherited. With a
  builder, the launchd plist puts `~/.local/bin` first on the body's PATH (greg/service.py:38); systemd and
  supervisord pass on their manager's PATH. A Mac has no system `dpkg-query`, so any `dpkg-query` on that PATH is the
  one that runs.
- Probe on `10d8fafa` (scratch directory, deleted afterwards): with a script named `dpkg-query` placed first on PATH,
  `licensing.system_binary('/usr/bin/sha256sum')` ran it, and it wrote "planted dpkg-query ran as root with args -S
  /usr/bin/sha256sum" in this container (the body's user here is root); `capabilities.installed_binary('dpkg-query')`
  still returned `/usr/bin/dpkg-query`. The integration step's probe at `275e9d86` gave the same result, and so did
  a re-run at `640e6eb9` (the planted script exited 1, and `system_binary` returned `None`).
- Classification. Under this unit's rule the site is `known_unmediated`, with two `body-loop:` serves naming the
  mission and Goal Gravity schedules and a reason that says the above. The precedents are `Body.appraise` and
  `compute.memory_bytes`: the body reaches each on its own with nothing governing the spawn. It is a recorded finding,
  not an approval, and listing it authorizes nothing.
- The fix is outside this unit, which changes no source module. A fix that pins the executable to a trusted,
  root-owned system path is proposed on branch `claude/licensing-binary-pin-20261030` as a separate child PR of #196
  (when this record was written the branch existed at `638457a4` with no commits of its own, and it still had none
  when the record was updated for `640e6eb9`). The entry stays `known_unmediated` after that fix: pinning the path
  decides which binary runs, but the spawn is still unconfined and still on the body loop. Removing the finding needs
  the spawn behind confinement (for example `run_isolated`) or behind a governed path, and a re-classification.

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

On the merged tree (`10d8fafa`, #196 at `638457a4`, plus the `system_binary` entry):

| Check | Result |
| --- | --- |
| `tests/unit/test_effect_call_allowlist.py`, before the entry | **1 failed, 8 passed**: `UNLISTED … greg/licensing.py :: system_binary :: subprocess.run (1 call)`, the only problem reported (same as at `275e9d86`) |
| the same, after the entry | **9 passed** |
| `scripts/ci/check_effect_call_allowlist_mutants.py` | BASELINE passes, **52/52 caught**, exit 0, 5m57s. The one new mutant drops the `system_binary` entry and must fail `test_every_effect_call_site_is_listed` naming that site, so "each `known_unmediated` entry removed" still covers every entry (allowlist mutants: 11) |
| `tests/unit/test_greg_packaging.py`, `test_greg_platform.py`, `test_developmental_inheritance.py` | 3, 19 and 23 passed |
| `test_greg_license_expressions.py`, `test_greg_license_qualification.py`, `test_greg_license_use_context.py`, `test_greg_model_license.py` and the traced Genesis mission test | 1982 passed |
| `scripts/ci/check_authority_singleton.py` | rc 0, "exactly one source of authority for each governed artifact" |
| `scripts/ci/check_schema_refs.py` | rc 0, 27 schemas, 130 local refs, all resolve |
| test files of modules changed on both sides | none: the unit changes four files of its own and no source module, and neither merge had a file changed on both sides |
| `ruff check --line-length 120` on the two Python files | only the script's one-line stdlib import (E401, or I001 under the import-sort rules), identical to the committed file |

On the merged tree `640e6eb9` (#196 at `a986fc74`). Each check ran in a clean detached worktree of that commit, so
nothing uncommitted was read:

| Check | Result |
| --- | --- |
| `tests/unit/test_effect_call_allowlist.py` | **9 passed**: no unlisted site, no stale entry, no count mismatch |
| `scripts/ci/check_effect_call_allowlist_mutants.py` | BASELINE passes, **52/52 caught**, 0 survived, 0 stale, exit 0, 6m51s |
| `tests/unit/test_greg_packaging.py`, `test_greg_platform.py`, `test_developmental_inheritance.py` | 3, 19 and 23 passed |
| `scripts/ci/check_authority_singleton.py` | rc 0, "exactly one source of authority for each governed artifact" |
| `scripts/ci/check_schema_refs.py` | rc 0, 27 schemas, 130 local refs, all resolve |
| `scripts/refresh_owned_source.py` | added nothing, removed nothing; the committed inventory already matches |
| runtime trace of `test_capability_genesis_acquires_installed_tool_and_resumes_mission` | 1 passed; the one `dpkg-query -S` spawn, from `Body.tick` (stack above) |
| planted `dpkg-query` probe | the planted script ran as root; `installed_binary` still returned `/usr/bin/dpkg-query` |
| test files of modules changed on both sides | none: this merge, like the two before it, had no file changed on both sides, and the unit changes no source module |

Counts at `640e6eb9` are the same as at `77d5e9b8`: 93 keys and 106 occurrences across 28 `greg/` and 14
`foundry/systems/` modules, 90 `allowed`, 3 `known_unmediated` and 6 wrappers.

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

The `system_binary` entry's body-loop paths were traced at runtime only for the mission path (one test, the
installed-software rung); the Goal Gravity path is read from the code. The planted-binary probe ran in this Linux
container as root; it was not run on a Mac or under launchd, systemd or supervisord, so the PATH each service manager
hands the body is read from `greg/service.py`, not observed.

**Commit identity.** The six commits on this branch made before 17:55Z on 2026-10-30 (`78e986bb`, `f4028f3d`,
`f0b5d1a2`, `5c6116a2`, `eca2f86a` and the merge `275e9d86`) carry the placeholder author and committer
`combined-check <combined-check@local>`. It leaked from a shared git configuration that another workflow of the same
session had set; worktrees share one config file. History is not rewritten, because these shas are cited as evidence
here and in the unit's review records. Later commits carry `Claude <noreply@anthropic.com>`. This is a limitation of
the record, not a defect of the code.

## Reality level

UNIT-TESTED: static analysis plus mutation testing on scratch copies. Three runtime probes reproduced findings
(`run_isolated` network; the body loop's `sysctl` spawn, with the spawn intercepted; the body loop's `dpkg-query`
spawn, traced from `Body.tick`, and a planted `dpkg-query` earlier on PATH that it ran). The `dpkg-query` trace and
probe were re-run at `640e6eb9`. No runtime effect was blocked, nothing ran on a founder device, and no authority,
capability or behaviour changed. The `system_binary` entry is a recorded finding, not an approval.

Rollback: revert the commits. The three files have no dependents.
