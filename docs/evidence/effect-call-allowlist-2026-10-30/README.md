# Effect-call allowlist (MU-D)

Founder directive of 2026-10-28 (OPUS MAXIMUS build), unit MU-D, items S37 and S67. Base: `b1950be2` (#196 head).
Round 1 was `78e986bb`..`f4028f3d`. Round 2 answers the fourteen findings of two independent reviews (below).
The branch has since merged #196 four times, at `4dc0d581`, `638457a4`, `a986fc74` and `d35d92a5`; the merges and the
two sites the base added are under "Merges of the PR base" below. Round 4 answers the thirteen findings of the third
review (attack and fidelity lenses, on `9b4bf062`); it is under "Round 4" below and changes the scan, the allowlist
and the mutant gate, still no source module.

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
- `tests/security/effect-call-allowlist.json`: after round 4, 108 keys and 124 occurrences across 32 `greg/`, 14
  `foundry/systems/`, 2 `egregore/` and 1 `tools/` modules; 8 wrappers; 33 path lookups (40 occurrences). The
  fourth merge (`7f179554`) added one allowed key: 109 keys and 125 occurrences across the same modules. Before
  round 4: 93 keys and 106 occurrences across 28 `greg/` and 14 `foundry/systems/` modules, 6 wrappers (round 2: 92
  keys, 105 occurrences, 27 `greg/` modules; round 1: 67 keys, 79 occurrences). The sub-bullets below give the
  round-2 numbers; round 4's are under "Round 4".
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
  acceptable. What the listing stops from going unseen (round 4, MUD-R4-2): a new spawn site, a changed count, a
  rewritten spawn or constant (the pin), and a new direct caller (`system_binary` is a declared wrapper, so
  `genesis._binary_license` and `licensing.requalify_binary` are findings of their own). It does not see a new route
  to an existing caller: `a986fc74` added one (below) and the scan stayed green. Routes are read from the code.
- **The envelope's own binary (round 4, MUD-ATK-1).** `worker_isolation._backend` and `relay_door.namespace_argv` take
  `bwrap` from `shutil.which` on the body's ambient PATH and run it unconfined. Every worker envelope and door namespace
  is whatever file of that name comes first there. The 14 allowed entries that rely on it now say so, and the test
  requires it while the lookup stays ambient. A pin is proposed on `claude/licensing-binary-pin-20261030`
  (`db09035e`, not merged here).
- **known_unmediated `tools/offline_test.py :: install_filter :: ctypes.util.find_library`** (round 4, MUD-ATK-8). The
  seccomp filter's loader runs `find_library("seccomp")` in each confined child, after fork and before the filter. It
  always runs `/sbin/ldconfig -p` (observed with an audit hook). When the ldconfig cache lacks libseccomp, it also
  runs `gcc` or `cc` and `ld` found on the body's PATH (the reviewer simulated this; this host's cache has the
  library). Genesis reaches it from the body loop through `_run_bounded` -> `run_isolated`. Loading the library by a
  fixed soname would remove the spawn; that source change is outside this unit.
- **git on the ambient PATH (round 4, MUD-ATK-6, MUD-ATK-7).** `egregore/repository_audit.git_read` (behind
  `brief.engineering`, `repo.pin_audit` and `repo.integration_audit`, whose manifests name `/usr/bin/git`) and
  `ventures._git_head` (no env at all, so every inherited `GIT_*` variable applies) run the first `git` on the body's
  PATH. A planted `git` ran in the reviewer's probes. `git_read` also applies the repository's own config: here,
  `briefs._git(path, "status", "--porcelain")` ran a `core.fsmonitor` command a scratch repository named, which
  `read_only_git` would have blanked. `git_read` is now a declared wrapper.
- **Genesis's acquired binaries (round 4, MUD-ATK-10, plausible).** `capabilities.installed_binary` searches
  `/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin` with no ownership check. Genesis runs what it finds from the body
  loop through `run_isolated(isolate_network=True)`, which confines the network only. With Homebrew on a Mac,
  `/usr/local/bin` and `/opt/homebrew/bin` can be user-writable. This was not run on a Mac. Earlier wording called these
  "fixed system roots"; that wording is gone.
- **System 52's string check (round 4, found while classifying `repair._trace_lines`).** `foundry_bridge._call`
  refuses a request whose `system`, at any depth, is the string `"52"`, but it compares strings. A nested `"052"`
  passes it, observed through `foundry.query` -> `mcp_gateway.foundry_tool`. The MCP tool then selects system 52 with
  `int()`. Inside GREG, the foundry worker's guard refused the `exec` of the caller's source (`PermissionError`,
  observed). Outside GREG, `mcp_gateway._query` with `"052"` ran the caller's source in the MCP server child
  (observed).
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
That audit was of round 2's tree (`b1950be2`); `system_binary` arrived later with the base and is filed above. Round
4 did not repeat it for the confinement and capability entries. Instead it records what their confinement rests on
(the `bwrap` lookups, the path lookups). Those entries are reached through a capability's adapter and the Gate.
`a986fc74` added `fs.search` to `greg/appraisal.py`'s `REOBSERVABLE` set. It is a read-only, streamed file read, so
the `Body.appraise` reason ("it re-runs only the read-only `REOBSERVABLE` sensors") still holds.

## Merges of the PR base

| Merge | Base merged | Conflicts | New effect sites | Result |
| --- | --- | --- | --- | --- |
| `275e9d86` | #196 at `4dc0d581` (66 base commits since `b1950be2`, 95 files) | none: no file changed on both sides | 1: `greg/licensing.py :: system_binary :: subprocess.run` | committed with the scan red on that site, left unlisted pending this classification |
| `10d8fafa` | #196 at `638457a4` (#209's whole-output judgment adopted; 25 commits, 19 files) | none: no file changed on both sides; `foundry/owned-source.json` was not touched by either side, so `refresh_owned_source.py` was not run | 0 | `system_binary` is still the only unlisted site |
| `640e6eb9` | #196 at `a986fc74` (#228's faithful text and #229's section IX adopted; 29 commits, 19 files) | none: no file changed on both sides; only the base changed `foundry/owned-source.json` (2 lines), so there was no conflict to resolve. `refresh_owned_source.py`, run on a scratch checkout of the merge, added and removed nothing | 0 | the scan passes with the `system_binary` entry from `77d5e9b8`; no stale entry, no count mismatch |
| `7f179554` | #196 at `d35d92a5` (#232, #235, #238, #239, #242, #246, #249, #251 and #252 adopted; 72 commits, 122 files) | none in git: no file changed on both sides. Only the base changed `foundry/owned-source.json`; `refresh_owned_source.py`, run on a scratch copy of the merge, added and removed nothing | 1: `greg/compute.py :: benchmark :: subprocess.run` | the merged tree failed the scan on that site alone; the merge commit itself lists it under `allowed` (below) |

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
  `greg/missions.py`; and a watched sensing block.

**Correction (round 4, MUD-R4-1).** The earlier version of this paragraph said the watched block "opens no new path
to `Genesis` or `system_binary`". That was false. It is true that no added line calls `_form`, `genesis`,
`licensing` or `_self_repair`. But `a986fc74` gives the sensor-failure blocker `failing_checks` and `sensing: True`.
That routes a sensing-blocked mission into `_watch_while_blocked` (missions.py:2070), which calls `_observe`
(:2534). When the sensor no longer resolves, `_observe` calls `_deficit` (:2421), and the chain continues through
`_form` (:2741), `Genesis.resolve`, `_manifest_for` and `_binary_license` to `system_binary`. The body reaches this
while the founder's SENSOR_FAILURE ask is still open, for example after the founder detaches the sensor as the ask
suggests. The fidelity reviewer reproduced it, and it was re-run here on the round-4 tree with a scratch copy of the
reviewer's probe: while sensing-blocked after the detach, the calls were `_deficit`, `Genesis.resolve('hash.sha256')`,
`system_binary('/usr/bin/sha256sum')` and `system_binary('/usr/bin/shasum')`. At `638457a4` the same scenario
recorded none. The route is now a `body-loop:` serve of the `system_binary` and `_binary_license` findings. It was
traced by hand and by one runtime probe; the scan does not check routes.

The diff starts no process, opens no connection, listens nowhere and calls no declared wrapper. The scan agrees: with
the entries from `77d5e9b8`, **9 passed** on the merged tree, so nothing is unlisted or stale and no count changed. No
new site was classified, and no entry was added at that merge.

**`d35d92a5` (#232, #235, #238, #239, #242, #246, #249, #251, #252).** The scan now reads 328 modules, against
325 at round 4. The base changed 34 of them, 3 of which are new: `greg/autonomy.py`, `greg/blockers.py` and
`provenance/digests.py`. The scan found the new site; the 34 diffs were not each read by hand. Those of four
modules with listed sites were read (`genesis.py`, `body.py`, `ventures.py`, `foundry/systems/repair.py`), and so
were `compute.py`'s new `benchmark` and `host_facts`.
- Before the entry, the scan reported one problem: `UNLISTED … greg/compute.py :: benchmark :: subprocess.run
  (1 call)` (**1 failed, 17 passed**). Every pin still matched, so no listed call, and no finding's definition,
  changed as parsed.
- The site. #238's `compute.benchmark` (greg/compute.py:476, the call at :492) runs `[sys.executable, "-I", "-c",
  "pass"]` once per run, to time one interpreter spawn, with `check=True`, `capture_output=True` and a 60 s timeout.
  The argv is fixed and takes nothing from the caller. Its only caller is `greg compute benchmark`
  (greg/cli.py:949), a command a person runs. A search of `greg/`, `foundry/`, `egregore/`, `tools/` and `scripts/`
  found no other. The merge commit lists it under `allowed` with that `operator:` serves; this was the only edit
  needed for the merged tree to pass.
- Routes. Genesis's installed-software rung now tries an acquired reader that already failed to measure after the
  others (#239). The candidates are the same, and so is the route from `_manifest_for` through `_binary_license` to
  `system_binary`, so the findings' serves stand. `Body.tick` now calls `autonomy.regress` first (#235); that module
  starts no process.
- Not in the inventory. On macOS, two person-run commands now also reach `memory_bytes`'s `sysctl` spawn:
  `greg compute benchmark` (through `host_facts`) and `greg compute status` (through `sample`). The finding's
  `operator:` serves still names only `greg.body.status`. The JSON was not changed for this.

On the merged tree `7f179554`:

| Check | Result |
| --- | --- |
| `tests/unit/test_effect_call_allowlist.py` | **18 passed** |
| `test_greg_egress.py`, `test_founder_effect_doctrine.py` | 16 and 5 passed |
| `test_greg_packaging.py`, `test_greg_platform.py`, `test_developmental_inheritance.py` | 3, 19 and 23 passed |
| `check_authority_singleton.py`, `check_schema_refs.py` | rc 0; 27 schemas, 130 local refs, all resolve |
| round 4's probes and the reviewers' scan probe | unchanged tree: 0 problems. Re-filing every finding: 14 problems (6 `FINDING RE-FILED`). Rewriting both spawns: 2 `PIN MISMATCH known_unmediated`. A new `system_binary` or `git_read` caller: `UNLISTED`. `_backend`'s round-2 text: `ENVELOPE CLAIM`. Probe forms found: 15 of 15 |
| `scripts/ci/check_effect_call_allowlist_mutants.py`, run once as a single process (not sharded) | BASELINE passes, **117/117 caught**, 0 survived, 0 stale, exit 0, 27m14s |
| `git merge-tree` against 22 sibling branches | 20 clean. 2 conflict, and each conflicts with `d35d92a5` alone too: `cursor/text-interpretation-contract-bddd` (`foundry/owned-source.json`, `greg/appraisal.py`, `greg/missions.py`) and `cursor/receipt-pinned-appraisal-ba20` (`greg/appraisal.py`) |
| the allowlist test on the merge with each clean sibling the base does not already contain (10) | 18 passed on each |
| counts | 103 `allowed`, 6 `known_unmediated`, 8 wrappers, 33 path lookups (40 occurrences) |

**`4dc0d581`: the licensing site.** The base added it in `bd7e3f9e` (#201/#230, 2026-10-22, "GREG reads PDFs on the
mission path; acquired system binaries carry their DEP-5 license"); that commit is not in `b1950be2`, where this
unit was seeded, and reached #196 with the #201/#230 adoption before `4dc0d581`. Line numbers below are from the
merged tree at `10d8fafa`. `a986fc74` changed none of `greg/licensing.py`, `greg/genesis.py`, `greg/body.py` or
`greg/goal_gravity.py`, so their numbers hold at `640e6eb9`. Two cited files grew. `greg/missions.py`'s numbers at
`640e6eb9` are `_step` :2008 (`_form` at :2113), `_deficit` :2732 (:2741) and `_after_outage` :2856 (:2871).
`greg/capabilities.py` changed by +115/-23 lines, so `installed_binary`, cited below at :1290 for `10d8fafa`, is at
:1382 at `640e6eb9` (round 4, MUD-R4-3).

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
- The fix is outside this unit, which changes no source module. A fix that pins the executable to a root-owned
  system file is proposed on branch `claude/licensing-binary-pin-20261030` as a separate child PR of #196. When this
  record was written the branch had no commits of its own, and it still had none at the `640e6eb9` update. At round
  4 it holds `db09035e`, which pins `dpkg-query` and both `bwrap` lookups. That commit is not merged here. The third
  review found that the pin checks only the final file, not the directories on its path or the symlink chain, and that
  it returns a path that is resolved again at exec (MUD-ATK-9). The entry stays `known_unmediated` after that fix:
  pinning the path decides which binary runs, but the spawn is still unconfined and still on the body loop. Removing
  the finding needs the spawn behind confinement (for example `run_isolated`) or behind a governed path, and a
  re-classification. When the pin merges, the `bwrap` and `dpkg-query` path lookups change and fail this check
  until they are re-listed. The texts that say "ambient PATH" must then be re-read by hand: the check requires those
  words while the lookup is ambient, but it does not remove them afterwards.

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

## Round 4: the third review's thirteen findings

A session interrupted at 22:05Z on 2026-10-30 left uncommitted changes to the three unit files, saved before that as
`mud-r3fix/uncommitted-at-2109Z.patch` in the session's scratch directory. Round 4 read them, kept what held, and
finished the rest: the allowlist had not been updated to match the scanner, and four tests failed.

### What changed

- **Scope.** The scan reads `greg/`, `foundry/systems/` and every repository module they import, followed import by
  import (`read_tree`). Imports are resolved from the repository root and from `tools/`, which
  `greg.capabilities._network_filter` and `segmentation` put on `sys.path`. `test_sys_path_roots_are_module_roots`
  keeps that list complete. On this tree it reads 325 modules, up from 216, including 18 under `egregore/` and
  `tools/offline_test.py`.
- **Effect table.** It now also counts these as effects:
  - stdlib calls that start a child themselves: `platform.platform|processor|architecture` (`uname -p`) and
    `ctypes.util.find_library` (`ldconfig -p`, then `gcc`/`ld` on PATH);
  - `multiprocessing.get_context|Manager`, `multiprocessing.pool.Pool` and the `multiprocessing.managers` managers;
  - the `urllib.request` handlers and legacy openers that connect, `socket.SocketType`, `ssl.create_connection`,
    `ssl.get_server_certificate`, `telnetlib` and `nntplib`;
  - name lookups (`socket.getaddrinfo|gethostbyname|gethostbyname_ex|gethostbyaddr|getnameinfo|getfqdn`), because a
    lookup sends the name to a resolver;
  - code run from a string in this process: `exec` and `eval` (where the module does not rebind the name) and
    `runpy.run_module|run_path`.
- **Names the scan cannot follow.**
  - An effect module (`subprocess`, `os`, `socket`, `urllib.request`, ...) used as a value is a "module reference"
    site: on an attribute or a class, as a default, as an argument (`vars(subprocess)`,
    `attrgetter("run")(subprocess)`), in a container, as a loop or `with` source, as a return value, or through its
    namespace (`__dict__`).
  - A loop method (`create_connection`, `subprocess_exec`, `getaddrinfo`, ...) counts on any receiver.
  - A rebound `isinstance` or `exec` is no longer read as the builtin.
- **Pins (MUD-ATK-4).** Every entry carries a `pin`.
  - A known_unmediated pin is the sha256 of its whole enclosing definition, parsed, plus every module-level constant
    it reads (`DPKG_TIMEOUT`, `ACTIVE_BINARY_POLICY`).
  - An allowed pin covers the calls recorded at its site (callee, arguments, keywords, in any order) and the constants
    they read.
  - A changed spawn fails until someone re-reads the text and re-pins it. A pin binds what runs, not who reaches it.
- **Findings stay findings (MUD-ATK-5).** `FINDINGS` in the test names the six known_unmediated keys. Moving one under
  `allowed`, with any serves, fails as `FINDING RE-FILED`. Filing a new one needs an edit of the test.
- **Wrappers (MUD-R4-2, MUD-ATK-6).** `greg.licensing.system_binary` and `egregore.repository_audit.git_read` are
  declared wrappers, so each caller is a site: `_binary_license` and `requalify_binary` are findings, and `capture`,
  `briefs._git` and `capabilities._repo_report` are allowed.
- **Path lookups (MUD-ATK-1, MUD-ATK-7, MUD-ATK-10).** `path_lookups` lists each place a program is chosen by name:
  `shutil.which` (its `path=`, else the ambient PATH), or an argv whose first item has no slash (the PATH of the env
  it is given: none means ambient, a literal is that string, an env without PATH means `os.defpath`, anything else is
  computed). Each entry has its count, what it searches and a note on who runs the file found, with what privileges
  and confinement. There are 33 lookups: 25 ambient, 6 `/usr/bin:/bin`, 1 `installed_binary`'s list and 1 computed.
  While `bwrap` is looked up on the ambient PATH, an allowed justification that relies on bubblewrap, a namespace or
  the envelope must say "ambient PATH".
- **Allowlist.**
  - 10 new allowed sites: 2 in `egregore/local_model.py`, `git_read` and its 3 callers, `repair._trace_lines`'s
    `exec`, `evolution_room`'s `runpy`, and 2 in `tools/offline_test.main`. The 2 `platform.platform` sites from the
    patch are kept.
  - 3 new known_unmediated entries: `_binary_license`, `requalify_binary` and `install_filter`.
  - The `_watch_while_blocked` route (MUD-R4-1) is added to the `system_binary` and `_binary_license` serves.
  - These justifications were rewritten: the 14 entries that rely on the namespace or the envelope (`_backend`
    among them), `ventures._git_head`, `repair._pytest` and `repair._Runner.run`'s reach claim.
  - Totals: 102 allowed, 6 known_unmediated, 8 wrappers and 33 path lookups.
- **Self-tests.** There are 9 new ones (18 in all): module references and the added callees, known_unmediated
  pins, allowed pins, findings re-filed, the round-3 forms, program lookups, envelope claims, import following, and
  the `sys.path` roots. Two existing ones were corrected for the new `pin` field. The envelope rule applies to
  allowed entries only: a known_unmediated reason names the envelope only to say it is absent.

### Dispositions

| Id | Disposition |
| --- | --- |
| MUD-ATK-1 | fixed in the inventory: the 14 entries that rely on the envelope say `bwrap` is found on the ambient PATH, the two `bwrap` lookups are listed, and the test requires the wording while the lookup is ambient. The source pin is LIC-PIN's (`db09035e`, not merged here) |
| MUD-ATK-2 | fixed: `platform.platform|processor|architecture` are effects; both sites are listed |
| MUD-ATK-3 | fixed: every form in the reviewer's probe is now a site (15 of 15; the round-3 scanner found 0) |
| MUD-ATK-4 | fixed: pins on every entry (whole definition for findings, the calls for allowed) |
| MUD-ATK-5 | fixed: `FINDINGS` in the test; re-filing with an operator serves fails |
| MUD-ATK-6 | fixed: imports are followed into `egregore/` and `tools/`; `git_read` is a wrapper and is listed with its callers and its lookup |
| MUD-ATK-7 | fixed in the inventory: the justification and the lookup say git comes from the ambient PATH with the inherited `GIT_*` variables. `greg/ventures.py` is held by another session, so the source is unchanged |
| MUD-ATK-8 | fixed in the inventory: `install_filter`'s `find_library` is a known_unmediated finding. Loading by a fixed soname is a source change outside this unit (deferred) |
| MUD-ATK-9 | deferred: it concerns LIC-PIN's pin (`greg/isolation.trusted_system_executable`), which is not on this branch. Recorded above for that PR |
| MUD-ATK-10 | fixed in the record: no text calls `installed_binary`'s directories trusted; its lookup is listed with a note that there is no ownership check. Not run on a Mac |
| MUD-R4-1 | fixed: the README paragraph is corrected, the route is a serve, and it was re-run on this tree |
| MUD-R4-2 | fixed: the wording is corrected, and `system_binary` is a wrapper, so a new caller fails |
| MUD-R4-3 | fixed: `installed_binary` is at :1382 at `640e6eb9` |

### Commands and results

Every run used `PYTHONDONTWRITEBYTECODE=1 /home/user/venv311/bin/python -B` (pytest with `-q -p no:cacheprovider`).

| Step | Where | Result |
| --- | --- | --- |
| fail-before | detached worktree of the unit base `a986fc74`, with round 4's test and round 3's allowlist (`9b4bf062`) | **2 failed, 16 passed**. `test_allowlist_is_well_formed`: 93 malformed (no pins, round-3 fields). `test_every_effect_call_site_is_listed`: 10 unlisted (`egregore/local_model` ×2, `git_read`, `repair._trace_lines`, both `platform.platform`, `evolution_room`, `tools/offline_test` ×3), 93 pin mismatches, 3 finding problems, 33 unlisted path lookups, 14 envelope claims |
| fail-before | the same worktree with round 3's test and allowlist, and the reviewers' probes | round 3's test: 9 passed. Scan probe: 15 of 15 forms `NO SITE`, and no `characterize.py` site. Re-filing all 3 findings as allowed: no problem. Rewriting both pinned spawns: no problem. A new `system_binary` caller: no problem. A new `git_read` caller: no problem. `egregore/` and `tools/` modules scanned: none |
| pass-after | this branch | `tests/unit/test_effect_call_allowlist.py`: **18 passed**. The same probes give 15 of 15 forms found. Re-filing gives 14 problems (6 `FINDING RE-FILED`). The rewrite gives 2 `PIN MISMATCH known_unmediated`. A new `system_binary` or `git_read` caller gives `UNLISTED`. Restoring `_backend`'s round-2 text gives `ENVELOPE CLAIM` |
| runtime | scratch copy of the fidelity reviewer's probe, removed after | sensing-blocked after a detach: `_deficit`, `Genesis.resolve`, `system_binary` ×2 (MUD-R4-1) |
| runtime | `briefs._git` on a scratch repository with `core.fsmonitor` set | its command ran |
| runtime | `foundry_bridge.query` and `mcp_gateway._query` with nested system `"052"` | the bridge passed it; GREG's foundry worker guard refused the `exec` (`PermissionError`); the gateway outside GREG ran the source |
| runtime | `ctypes.util.find_library("seccomp")` under an audit hook | `subprocess.Popen /sbin/ldconfig ['-p']` |
| mutants | `scripts/ci/check_effect_call_allowlist_mutants.py`, this branch | see "Mutant gate" below |
| other | `test_greg_packaging.py`, `test_greg_platform.py`, `test_developmental_inheritance.py` | 3, 19 and 23 passed |
| other | `check_authority_singleton.py`, `check_schema_refs.py` | rc 0; 27 schemas, 130 local refs, all resolve |
| lint | `ruff check --line-length 120` on both Python files | only the script's one-line stdlib import (I001), as in the committed file |

### Mutant gate

`scripts/ci/check_effect_call_allowlist_mutants.py` has **117 mutants**, up from 52. They break down as:
- 48 source mutants: round 2's 23, the round-3 patch's 14, and 11 added in round 4 (a new `git_read` caller, an effect in
  `egregore/`, a new module reached only through an import, an effect in `tools/offline_test.py`, `exec` of a literal,
  `multiprocessing.get_context`, a loop method on a class attribute, a new ambient lookup, a pinned git lookup moved to
  the ambient PATH, a rewritten allowed call and a constant it reads);
- 25 allowlist mutants: round 2's 11, the patch's 5 and round 4's 9 (a finding re-filed with an operator serves, a
  site filed as a finding without `FINDINGS`, the `install_filter` entry removed, `git_read` undeclared, an allowed
  pin dropped or stale, a lookup removed or misstated, an envelope claim without the ambient PATH);
- 44 scanner mutants: round 2's 18, the patch's 12 and round 4's 14.

The gate ran in three shards on the final tree. Each shard was a separate process that imported the script, kept
every third mutant and ran its own `main()`, with its own scratch copy and baseline, because the machine was shared.
The result: **BASELINE passes in each shard, 117/117 caught**, 0 survived, 0 stale, exit 0 in each, 741 s wall time.

The first full run (same split, before two fixes) caught 114 of 117. Two mutants made their test fail, but the
output did not name the expected site (an `IndexError`, and an assertion that printed only the problems found). The
five new tests now compare prefixes, so a failure prints the missing problem. The third mutant was equivalent: the
reference rule still recorded the loop call. That mutant now reverts both loop rules to round 3's. Every one of the
three was then run on its own and caught, before the clean full run.

## Limitations

The scan is static. It reads `greg/`, `foundry/systems/` and the repository modules they import. It does not see:
- effects inside third-party libraries (model SDKs, the MCP SDK, Playwright, Chromium). The `browser.session` WebSocket
  bypass fixed in 8bdca11f lived there and in the `CONFINED_EGRESS` policy set; reverting that fix leaves this check
  green. Round 1's product statement that it now catches that class was wrong;
- code run from a string in a child (`python -c`); the spawn that runs it is listed;
- `importlib.import_module` or `getattr` with a non-literal name, `ctypes` calls other than `find_library`,
  `socket.fromfd` (it wraps an existing descriptor), and stdlib modules that spawn internally and are not in the
  table (`uuid`'s command fallbacks among them);
- who reaches a site. A pin binds what runs; the routes in `serves` and the reachability claims in justifications
  ("exercise() only", "reached only from …") are read from the code and not machine-checked, except that a declared
  wrapper makes each caller a site. MUD-R4-1 shows a new route can arrive with the scan green;
- what a program found on the PATH is. `path_lookups` says where the file is searched for, not who owns that
  directory: a fixed list such as `installed_binary`'s is not an ownership check.

Name binding is flow-insensitive, so a reused local name may over-report. The envelope rule matches words
("bubblewrap", "namespace", "envelope"), so a justification that relies on the envelope in other words is not held to
it. The mutants script is not a step in `.github/workflows/canonical-ci.yml` (outside this unit's scope); the test
itself runs in CI job 1's full pytest run.

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

UNIT-TESTED: static analysis plus mutation testing on scratch copies. Runtime probes in this Linux container reproduced
these findings:
- `run_isolated` network;
- the body loop's `sysctl` spawn, with the spawn intercepted;
- the body loop's `dpkg-query` spawn, traced from `Body.tick`, and a planted `dpkg-query` earlier on PATH that it ran;
- in round 4: the watched-block route to `system_binary`, a repository's `core.fsmonitor` run by `briefs._git`, the
  system-52 string check passed by `"052"`, and `find_library` running `ldconfig`.

The third review's planted `bwrap`, `git` and `uname` probes are the reviewers' runs; they were not repeated here.
No runtime effect was blocked, nothing ran on a founder device or a Mac, and no authority, capability or behaviour
changed. Every known_unmediated entry is a recorded finding, not an approval.

Rollback: revert the commits. The three files have no dependents.
