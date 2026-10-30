# Effect-call allowlist (MU-D)

Founder directive of 2026-10-28 (OPUS MAXIMUS build), unit MU-D, items S37 and S67. Base: `b1950be2` (#196 head).

## What changed

Before this change, nothing in the tree listed where `greg/` and `foundry/systems/` start processes or open
network connections. A new `subprocess.run` or `urlopen` that bypassed the capability manifests, the Gate, the
worker envelope or the #26 relay could only be noticed by a reviewer reading the diff. The `browser.session`
bypass was found that way.

- `tests/unit/test_effect_call_allowlist.py` parses every `.py` file under `greg/` and `foundry/systems/` with
  `ast` and finds each effectful call site:
  - child processes: `subprocess.run|Popen|call|check_call|check_output|getoutput|getstatusoutput`,
    `os.system|popen|fork|forkpty|spawn*|exec*|posix_spawn*`, `asyncio.create_subprocess_exec|shell`;
  - network: `urllib.request.urlopen`, `urllib.request.build_opener` and the `.open` of the opener it builds
    (including through a factory function in another module, such as `greg.egress.opener()`),
    `http.client.HTTPConnection|HTTPSConnection`, `socket.socket|create_connection`, `requests.*` and `httpx.*`.
  - `os.kill` is excluded.

  Imports are resolved, so all of these count:
  - `import subprocess as sp` and `from subprocess import run as r`;
  - `from urllib import request`, and a module re-exported through another module;
  - `importlib.import_module("…")` or `__import__("…")` bound to a name;
  - `getattr(subprocess, "run")`;
  - a bare reference such as `runner=subprocess.run`, since that is how an effect is injected.

  Annotations are not read. Each site is keyed by (module path, enclosing qualname, callee) with an occurrence
  count, and never by line number. Moving a call within its function changes nothing; a new call, an extra
  occurrence, or a call moved into another function does change the key or the count.
- `tests/security/effect-call-allowlist.json` was seeded from the base tree. It holds 67 keys and 79 occurrences
  across 21 `greg/` modules and 12 `foundry/systems/` modules.
  - Each `allowed` entry names what the site serves as `kind:detail`. Kinds are `capability:` (checked against
    `greg.capabilities.BUILTINS`), `confinement:`, `egress:`, `supervised-worker:`, `model-route:`,
    `founder-command:`, `operator:` (a command a person runs) and `installer:`. Each entry also has a one-line
    justification taken from the code.
  - `known_unmediated` holds sites that have no capability manifest, Gate, supervised worker or person-run
    command behind them. Each has a `reason`.
  - The file's `rule` field states this policy. Listing a site authorizes nothing.
- The test fails in three cases, and each message names the exact entry to add or fix and what to justify:
  - an unlisted site (with a ready-to-paste entry, or advice to file it under `known_unmediated` instead);
  - a stale entry;
  - a count mismatch.

  It also fails on malformed entries: an unknown serves kind, a capability id not in BUILTINS, a duplicate key,
  or a justification of fewer than six words. The full suite (`python -m pytest -q`, Canonical CI job 1) collects
  it.
- `scripts/ci/check_effect_call_allowlist_mutants.py` runs the mutants (see the results below).

No source module changed.

**Why `tests/security/`.** The candidates were `governance/integrity/`, `contracts/` and `tests/data/`.
- `governance/integrity/` holds founder-signed records: its `authorizations.json` changes only by an Ed25519
  `INTEGRITY_AUTHORIZE` envelope. An unsigned list placed there would read as an authorization.
- `contracts/` holds JSON Schemas for canonical wire contracts.
- `tests/data/` does not exist.
- `tests/security/` already holds the security suite's data (`security-tests.yaml`, for example
  `sandbox_escape`). This file is the same kind of thing: an oracle a test reads, with no authority.

## Findings

- **known_unmediated (1): `greg/body.py :: Body.appraise :: subprocess.run`.** The body runs
  `python -m greg.appraisal` on its own schedule whenever a mission closes (`Body._appraise_closure`).
  - No manifest, Gate or worker envelope stands behind the spawn.
  - The child runs reviewed GREG code with a scrubbed environment and a timeout, but it has no network or
    filesystem confinement.
  - It re-runs only the read-only `REOBSERVABLE` sensors, which exclude `http.get` and the browser.
  - Candidate fix (not made here): run it through `run_isolated` with the no-network filter.
- Every other site has one of the listed paths behind it:
  - 29 are reached only from person-run commands: `greg foundry run` / `python -m foundry.completion --audit`
    exercises, the P8 and admission harnesses, `greg doctor --chromebook`, `greg run --builder claude-code`, and the
    status views behind the console, the phone and `greg acceptance` (the macOS memory query);
  - the rest are capability adapters, the confinement they run behind, the supervised worker path, the
    founder-signed model routes, or anchoring to the founder-signed `ANCHOR_CONFIGURE` TSA.
- Observations made while grounding justifications. They are outside this unit and no behaviour was changed:
  - `greg/organs.py :: _snapshot` runs `git status` on the organ checkouts without `read_only_git`'s hardening
    (`core.fsmonitor=false`, blanked filter drivers). A planted fsmonitor in an organ checkout's config would
    run.
  - `greg/cognition/genomes/admission.py :: source_dirty` runs `git hash-object` on paths, which applies
    configured clean filters. This is in the kernel's own checkout and only in an operator-run harness.

## Commands and results

All runs used `PYTHONDONTWRITEBYTECODE=1 /home/user/venv311/bin/python -B -m pytest -q -p no:cacheprovider`
unless stated.

Fail-before was run in a detached worktree at `b1950be2`, removed afterwards:

| Step | What was in the worktree | Result |
| --- | --- | --- |
| 1 | the new test file only | **2 failed, 4 passed**: `test_allowlist_is_well_formed` and `test_every_effect_call_site_is_listed` raise `FileNotFoundError`, because the base keeps no inventory. The scanner self-tests pass. |
| 2 | the test file and the allowlist, source unchanged | 6 passed |
| 3 | `def _unreviewed_probe(): return subprocess.run(["true"])` appended to `greg/compute.py` | the existing `tests/unit/test_greg_platform.py` and `tests/unit/test_greg_founder_asks.py` (both import `greg.compute`): **69 passed**. Nothing notices the call. |
| 4 | the same call, with the new test | **1 failed, 5 passed**: `UNLISTED effect call site greg/compute.py :: _unreviewed_probe :: subprocess.run (1 call). Add to tests/security/effect-call-allowlist.json under "allowed": {…}` |

Searching the base's `tests/unit` for tests that parse source and mention an allowlist or effects turned up four
files. Each runs `subprocess` for its own purposes; none inventories effect calls.

Pass-after on this branch:

- `tests/unit/test_effect_call_allowlist.py`: **6 passed**.
  - The scanner's positive controls cover every import form and call shape above.
  - Its negative controls cover `os.kill`, annotations, `subprocess.TimeoutExpired`/`PIPE`, a local `run`, a
    local variable named `requests` and an effect named inside a string.
  - Cross-module opener factories are followed.
  - Each comparison message is checked.
  - Against the tree: the allowlist is well formed and every site is listed.
- Related suites: `tests/unit/test_greg_egress.py` (16) and `tests/unit/test_founder_effect_doctrine.py` (5),
  together with the new file: **27 passed**. `python scripts/ci/check_authority_singleton.py`: "exactly one
  source of authority for each governed artifact".
- `python scripts/ci/check_effect_call_allowlist_mutants.py` copies the tree to a scratch directory and runs with
  `-B` and `PYTHONDONTWRITEBYTECODE=1`, purging `__pycache__` before each mutant. The unmutated copy passes first.
  Result: **20/20 caught**. Each mutant must fail its named test, and the output must name the expected site.
  - Nine source mutants:
    - a new call in a listed module;
    - a new module that opens a socket;
    - `from subprocess import run as r`;
    - `import subprocess as sp`;
    - `getattr(subprocess, "run")`;
    - an injected `runner=subprocess.run`;
    - the `sysctl` call moved from `memory_bytes` into a new `_sysctl()`;
    - a second occurrence in `memory_bytes` (COUNT MISMATCH);
    - `egress.opener().open(...)` added to `greg/anchor.py`, around `open_checked`'s allowlist.
  - Six allowlist mutants:
    - an `allowed` entry removed;
    - the `known_unmediated` entry removed;
    - a stale entry;
    - a wrong count;
    - an unknown capability id;
    - a justification emptied.
  - Five mutants of the scanner itself, so the self-tests stay load-bearing. Each disables one of:
    - alias handling;
    - bare references;
    - opener `.open`;
    - suffix matching for re-exported modules;
    - annotation skipping.

Timing: the tree scan takes about 8 s on this shared 4-core machine (load average 4 to 5). The mutants script took
2m18s, and 2m13s on a second run after lint-only edits, again 20/20. The new files pass
`ruff check --line-length 120`, except for the one-line imports, which match the sibling mutant scripts.

## Limitations

The scan is static, and it reads only `greg/` and `foundry/systems/`. It does not see:
- code held in a string and run in a child (`python -c`, for example the relay door program or the seccomp
  probe); the spawn that runs it is listed;
- effects inside third-party libraries (the model SDKs in `greg/model_child.py`, the MCP SDK, Playwright's
  browser launch in `browser.session`);
- `ctypes` calls into libc;
- HTTP listeners (`http.server`), which are not in the scoped list;
- `getattr` with a non-literal name;
- a chain of opener factories more than one module deep;
- callers of a wrapper: `egress.open_checked` and `run_isolated` are listed once, where the primitive is, not at
  each call site.

A local name that shadows an import is resolved conservatively and may over-report. Reachability claims in the
justifications ("exercise() only", "reached only from…") were established by reading the code and by grepping
callers across `greg/`, `foundry/`, `scripts/` and `cortex/`. They are not machine-checked; a new caller can make
one false without changing the key.

The mutants script is not yet a step in `.github/workflows/canonical-ci.yml`, which was outside this unit's
scope. The test itself runs in CI job 1.

## Reality level

UNIT-TESTED. This is static analysis plus mutation testing on a scratch copy of the tree. No runtime effect was
observed or blocked, nothing ran on a founder device, and no authority, capability or behaviour changed.

Rollback: revert the commits. The three new files have no dependents.
