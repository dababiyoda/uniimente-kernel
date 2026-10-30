# Browser method gate and protected step program (WU-10), 2026-10-30

Branch `claude/browser-method-gate-20261030`, base `a6c29bbd40c1` (#196 head). Reality level: **INTEGRATION-TESTED**
(a real Chromium driven by Playwright against loopback HTTP servers on this container). The new CI workflow was not
executed. Nothing was tested on a founder device or behind the confined relay.

## What changed

1. **The computer-use suite runs.**
   - `greg/computer.py` `chromium()` looked only for `chromium-*/chrome-linux/chrome`. The preinstalled build here is
     `/opt/pw-browsers/chromium-1243/chrome-linux64/chrome` (Chrome for Testing 153.0.8010.12). So even with
     Playwright installed, the capability found no browser and `tests/unit/test_greg_computer.py` skipped as a
     module. The glob now matches both layouts.
   - `requirements-computer.txt` pins `playwright==1.63.0`. That wheel's `browsers.json` pins chromium revision 1243,
     the build preinstalled here; 1.64.1 pins 1248.
2. **Browser requirement hook.** With `GREG_REQUIRE_BROWSER=1`, the root `conftest.py` turns
   `pytest.importorskip("playwright")` into a failure, including in `test_greg_confined_egress.py`. Other optional
   imports still skip. `test_greg_computer.py` also fails, instead of skipping, when no Chromium is found.
3. **Method gate in `browser.session`.**
   - Inside the signed origins, only GET, HEAD and OPTIONS leave the browser. Every other method, and every
     WebSocket, is aborted and counted in `blocked_methods` as `METHOD host:port/path`.
   - The exception is a signed `read_methods` entry, for example `"POST https://shop.example/search"`. It names one
     method, one signed origin and one exact path, so it cannot widen the network bound. Each use is counted in
     `read_methods_used`.
   - A step during which a refused write is seen ends the session with `AUTHORITY_BOUNDARY`. Opening the start page
     counts as step 0. A step that fails after attempting a write is also reported as that write.
   - The trace's `method_gate` field, and the module docstring, state the GET residual.
4. **Protected step program in `greg/pipeline.py`.**
   - `op`, `selector`, `secret`, `consequential` and `read_methods` join `PROTECTED` through a union, so the
     original set literal and the existing mutant anchors stay byte-identical.
   - A `$from_action` placed at the `steps` list itself, or at a whole step, is refused.
   - Binding a fill's `value` still resolves.
5. **CI and mutation checks.**
   - `.github/workflows/computer-use.yml` (new) installs `requirements-computer.txt` and the Chromium that the driver
     pins, into `/opt/pw-browsers`. It then runs the computer-use suites with `GREG_REQUIRE_BROWSER=1`, followed by
     the mutation check.
   - `scripts/ci/check_browser_method_gate_mutants.py` (new) runs 12 mutants.

Measured channel coverage with Playwright 1.63 and Chromium 1243 (scratch probe, then pinned in the tests): Playwright
routing sees each of these:

- a POST form submitted by a click;
- a POST form submitted by Enter;
- a page `fetch` PUT or DELETE;
- `navigator.sendBeacon`;
- `<a ping>`;
- a dedicated worker's POST;
- a service worker's POST.

## Commands and results

Environment:

- Python 3.11 at `/home/user/venv311`, pytest 9.2.0;
- `playwright==1.63.0`, installed from its manylinux wheel; no browser was downloaded;
- runs as root, so the Chromium OS sandbox is off, as before this change;
- no bubblewrap.

Every run used `PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider`.

**Fail-before** (a temporary detached worktree of `a6c29bbd`, with the three new or changed test files copied in, then
removed):

- On the base, the three new test files gave **10 failed, 2 passed, 1 skipped**.
  - Skipped: `test_greg_computer.py`, the whole module, "no Chromium installed", although Playwright was installed.
  - Failed: both browser-required cases, and 8 of 9 pipeline cases.
  - Passed: the fill-value case, which must pass both before and after, and the "other imports still skip" case.
- On the base plus only commit `50f8231c`'s `greg/computer.py` (browser discovery, no gate),
  `test_greg_computer.py` gave **10 failed, 8 passed**. The 8 pre-existing tests passed and all 10 gate tests failed.
  The server received `POST /order` (by click and by Enter), `PUT /api/cart`, `POST /api/worker`, the WebSocket
  handshake to `/live`, the load-time `PUT` and `DELETE /api/state` and `POST /beacon`, and `POST /order` alongside
  the signed `POST /search`.
- A direct probe of an unmarked POST-form click, followed by an extract:

  | Tree | Status | Extracted | Server `POST /order` | `blocked_methods` |
  | --- | --- | --- | --- | --- |
  | Base + discovery | `COMPLETED` | `"Ordered"` | 1 | none |
  | Head | `AUTHORITY_BOUNDARY` | nothing | 0 | `{"POST 127.0.0.1:<port>/order": 1}` |

**Pass-after** (head `0b0c2bbc` code; this README and the workflow were added later):

- The four test files `test_greg_computer.py` (18), `test_greg_browser_required.py` (3),
  `test_greg_pipeline_protected.py` (9) and `tests/integration/test_greg_pipeline.py` (2), together with the
  confined-egress browser test, gave **32 passed, 2 skipped**. The skips are the confined-egress browser test's two
  parameters: no bubblewrap network namespaces here.
- The same three unit files with `GREG_REQUIRE_BROWSER=1` gave **30 passed**.
- `test_greg_computer.py` was run five times in a row: 17 of 17 passed each time, before the 18th test was added.
- Related suites gave **132 passed, 6 skipped**: `test_greg_mission_d_handoffs`, `test_greg_mcp_secret_files_review`,
  `test_greg_reconciliation`, `test_greg_closure_integrity`, `test_greg_appraisal_closure`,
  `test_greg_goal_gravity_merge`, `test_greg_sop_compounding`, `test_greg_browser` and `test_greg_packaging`.
  `tests/unit/test_greg_capabilities.py` and `tests/integration/test_greg_adversarial_machine.py` gave
  **36 passed**. The full suite was not run (too slow on this machine).

**Mutants:**

- `python -B scripts/ci/check_browser_method_gate_mutants.py`: **12/12 caught**. Every catching test passed
  unmutated first.
- The existing `scripts/ci/check_pipeline_mutants.py`: 3/3 caught.
- The existing residual mutant "an earlier output chooses the credential file" (anchored on the unchanged
  `PROTECTED` literal) still fails its test when applied (1 failed; 1 passed unmutated).

## Limitations and follow-ups

- **GET with side effects.** The gate sees methods, not effects. A logout or unsubscribe link, or a state-changing
  GET API, on a signed origin cannot be detected.
- **Confined bodies.** On a confined body the relay checks origins only, so the method gate exists only in the
  browser's routing. The confined-egress test that removes in-browser routing shows the relay still holds origins,
  not methods. It was not run here (no bubblewrap).
- **Telemetry stops a session.** A page that writes to its own origin while loading or after a step (for example,
  first-party telemetry) now ends the session at the boundary unless the founder signs that exact endpoint in
  `read_methods`. An attempt is charged to the step during which it is first seen.
- **Bind edges.** The signed `bind`-edge route in `greg/missions.py` (`protected_param`) now refuses
  `steps.N.op/selector/secret/consequential`. It still accepts a bind edge onto `steps` or `steps.N`, a whole program
  or step. Follow-up: an additive check there; that file is edited by open PRs.
- **Mouse coordinates.** A `mouse` step's `x` and `y` remain bindable through `$from_action`. Protecting them globally
  would refuse unrelated data keys. The method gate still bounds what any click can send.
- **CI workflow not run.** `computer-use.yml` was not executed here; it is checked only as YAML. Whether Chromium's
  OS sandbox starts as a non-root user on the hosted runner is unverified.
- **Follow-up: install on the Chromebook and report doctor readiness.** `greg/chromebook/install.sh` should install
  `requirements-computer.txt` from binary wheels without blocking Body 1. `greg/doctor.py` should report
  browser_session as ready or missing, with the fix, and state the GET residual. Both files are changed by open PR
  #211, so they are untouched here.
