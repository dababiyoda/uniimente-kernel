# Browser method gate and protected step program (WU-10), 2026-10-30

Branch `claude/browser-method-gate-20261030`, base `a6c29bbd40c1` (#196 head). Reality level: **INTEGRATION-TESTED**
(a real Chromium driven by Playwright against loopback HTTP servers on this container). The new CI workflow was not
executed. Nothing was tested on a founder device or behind the confined relay.

Two rounds:

1. The first implementation, `50f8231c`..`7b7ea61e`.
2. A review round on top of it. Two adversarial reviews of `7b7ea61e`, by separate agents of this session, reported
   16 findings (F1-F10, WU10-R1..R6).
   The review round is described in "Review round" below. Where it corrects a first-round claim, the
   correction is stated there.

## What changed (first round)

1. **The computer-use suite runs.**
   - `greg/computer.py` `chromium()` looked only for `chromium-*/chrome-linux/chrome`. The preinstalled build here is
     `/opt/pw-browsers/chromium-1243/chrome-linux64/chrome` (Chrome for Testing 153.0.8010.12). So
     `tests/unit/test_greg_computer.py` skipped as a whole module even with Playwright installed. The glob now
     matches both layouts.
   - `requirements-computer.txt` pins `playwright==1.63.0`. That wheel's `browsers.json` pins chromium revision 1243.
2. **Browser requirement hook.** With `GREG_REQUIRE_BROWSER=1`, the root `conftest.py` turns
   `pytest.importorskip("playwright")` into a failure. Other optional imports still skip.
3. **Method gate in `browser.session`.**
   - Inside the signed origins, only reads leave the browser. Any other request, and any WebSocket, is aborted and
     counted in `blocked_methods`.
   - The exception is a signed `read_methods` entry naming that method, origin and exact path.
   - A step during which a refused write is seen ends the session with `AUTHORITY_BOUNDARY`.
4. **Protected step program in `greg/pipeline.py`.** `op`, `selector`, `secret`, `consequential` and `read_methods`
   join `PROTECTED`. A `$from_action` placed at the `steps` list, or at a whole step, is refused. A fill's `value`
   stays bindable.
5. **CI and mutation checks.**
   - `.github/workflows/computer-use.yml` (new).
   - `scripts/ci/check_browser_method_gate_mutants.py` (new).

## Review round

All 16 findings were reproduced on `7b7ea61e` with the reviewers' own probes; WU10-R6's second half was confirmed by
reading `greg/capabilities.py`.

### Where the gate now sits

Measured with Playwright 1.63 and Chromium 1243 in scratch probes, then pinned in the tests below.

**What page routing missed.** Playwright's `context.route` never saw:

- a keepalive fetch or `sendBeacon` sent from `pagehide` or `visibilitychange`, at navigation or at session close (F1, R1);
- a shared worker's requests (F3);
- any redirect hop (F4, R2).

**Browser-target interception sees all three.** CDP `Fetch` enabled on the browser target, before the context
exists, pauses every request of every page, frame and worker until GREG answers it:

- the unload-time requests;
- the shared worker's POST;
- each redirect hop, with `redirectedRequestId`.

A request that was paused but never answered when the browser closed was not delivered. **Fix:** HTTP is now
decided only there, against both the origin bound and the method gate. `context.route` is no longer used.

**What no interception sees.** Neither layer sees a WebSocket. Playwright's routed WebSocket is a page-script mock
that a dedicated worker's WebSocket and `WebSocketStream` bypass (F2). WebTransport (QUIC) and `RTCPeerConnection`
(UDP) are outside HTTP interception too (F10).

Two mechanisms were measured and rejected:

- `Network.setBlockedURLs` did not block WebSockets.
- A `worker-src 'none'` CSP header injected at the response stage was enforced for blob workers but not for
  `new Worker('/w.js')` or service-worker registration.

**Fix:**

- `--disable-blink-features=WebSocketStream,SharedWorker` turns both off in the engine.
- An init script deletes `Worker`, `SharedWorker`, `WebSocketStream`, `WebTransport`, `RTCPeerConnection`,
  `webkitRTCPeerConnection` and `Navigator.prototype.serviceWorker`. It runs in every frame before page scripts,
  including dynamically created `about:blank` frames (measured).

Pages that need a worker lose it.

### Status rules

- A refused write always decides: whenever `blocked_methods` is non-empty the status is `AUTHORITY_BOUNDARY`, with
  the original stop kept in the reason (F6).
- A write first seen after the last step, or while the session closes, is recorded as a final `close` trace record.
- A read carries no body: OPTIONS with a body is a refused write (F7b). A `WEBSOCKET` exception passes only a
  WebSocket, never an HTTP request whose method token is `WEBSOCKET` (F7a).
- A malformed URL in `read_methods` or the start URL is a `CapabilityError`, not a `ValueError` (F9).

### `greg/pipeline.py`

- A `$from_action` that is a capability's whole params is refused (F5, R3). `pipeline.inspect` wraps its reference
  under a key to keep working.
- The step-program rule applies only to a bound `array` or `object`, so a solver's integer `steps` binds again (F8).
- `op`, `selector` and `secret` stay globally protected, as before this round. This is a recorded behaviour change
  from the base: for example, `foundry_bridge`'s `op` can no longer be an earlier action's output.

### Other changes

- `tests/integration/test_greg_confined_egress.py`: its "allowlist removed" parameter now switches off the
  browser-target interception, so it still tests the relay alone. Not run here (no bubblewrap).
- `requirements-computer.txt`: its comment is corrected. Only `browser.session` uses Playwright (R6).

### Corrections to first-round claims

- "Inside the signed origins only GET, HEAD and OPTIONS leave the browser" and "an exception cannot widen the network
  bound" were false: unload-time requests and redirect hops escaped both (F1, F4, R1, R2).
- The first round's README said its channel coverage was "pinned in the tests". `<a ping>` and a service worker's POST
  were seen only in a scratch probe (R5). `<a ping>` is now a test case. Service workers can no longer be registered
  (tested).

## Commands and results

Environment:

- Python 3.11 at `/home/user/venv311`, pytest 9.2.0;
- `playwright==1.63.0`; no browser was downloaded;
- runs as root, so the Chromium OS sandbox is off;
- no bubblewrap.

Every run used `PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider`.

### Fail-before, first round

A temporary detached worktree of `a6c29bbd`, with the new test files copied in, then removed:

- **10 failed, 2 passed, 1 skipped.** `test_greg_computer.py` skipped as a module.
- On the base plus `50f8231c`'s browser discovery only, `test_greg_computer.py` gave **10 failed, 8 passed**: the
  server received every write the gate tests send.

### Fail-before, review round

A temporary detached worktree of `7b7ea61e`, with the round's `test_greg_computer.py` and
`test_greg_pipeline_protected.py` copied in, then removed. Result: **20 failed, 27 passed**.

The failures, and what the server or listener received on the pre-fix head:

- Navigate away (`goto` and link click), session close, and a SCOPE stop followed by close: the server received the
  pagehide and keepalive POSTs.
- Unsigned unload beacon: the beacon reached the listener.
- Redirects:
  - signed POST then 307: the server received `POST /order`;
  - signed POST then 307 cross-origin, and GET then 302 cross-origin: the listener received `POST /collect` and
    `GET /collect`.
- F6: status `EXPECTATION_FAILED`.
- F7: the server received the `WEBSOCKET` request and the OPTIONS body.
- Prelude: the APIs exist.
- Malformed `read_methods` (2 cases).
- Pipeline:
  - whole params resolved;
  - integer `steps` refused;
  - a string item under `steps` refused;
  - the additive check.

Three of the 20 fail only for a structural reason: `PAGE_PRELUDE` does not exist on the old head. These are the
two layer tests and the worker-without-prelude test.

Two tests passed before and are coverage only:

- `<a ping>` (R5);
- the deferred last-step write (R4).

The post-loop charge R4 found untested was removed. The close-time accounting now covers its case, under the
mutant "a write at the close is dropped".

### Review probes

The reviewers' probes (`review-browser-method-gate-attack/p*.py`), run against the fixed tree:

| Probe | Result after the fix |
| --- | --- |
| p3, navigate away | `AUTHORITY_BOUNDARY`; four unload POSTs blocked; server writes `[]` |
| p3, session close | `AUTHORITY_BOUNDARY`; server writes `[]` |
| p3b (unsigned beacon) | `blocked_requests {'127.0.0.1': 1}`; unsigned origin saw `[]` |
| p1, p8b, p2, p9 (worker and WebSocketStream channels) | The page cannot construct the APIs; every server saw `[]` |
| p4, 307 same origin | `AUTHORITY_BOUNDARY`; blocked `POST /order` |
| p4, 307 to unsigned | Unsigned origin saw `[]` |
| p5 | Both writes blocked; server writes `[]` |
| p6 | `AUTHORITY_BOUNDARY`, with the expectation failure in the reason |
| p10 | Whole params refused; integer `steps` resolves |
| p13 | WebTransport, WebSocketStream, SharedWorker and RTCPeerConnection are all `undefined` |
| p11 (registration) | Still accepts whole-params; refused at `resolve`. `greg/missions.py` is out of scope |

### Pass-after

- **Required browser.** With `GREG_REQUIRE_BROWSER=1`: `test_greg_computer.py` (35), `test_greg_browser_required.py`
  (3), `test_greg_pipeline_protected.py` (12), `tests/integration/test_greg_pipeline.py` (2) and the confined
  browser test gave **52 passed, 2 skipped**. The skips are the confined test's two parameters: no bubblewrap.
- **Repeats.** `test_greg_computer.py` (31 tests at the time) was repeated 3 times: 31/31 each time, while other
  test runs shared the machine.
- **Binding suites: 190 passed, 4 skipped.** These were `test_greg_mission_d_handoffs`,
  `test_greg_mcp_secret_files_review`, `test_greg_pipeline`, `test_greg_goal_gravity`, `test_greg_bind_from_check`,
  `test_greg_pipeline_protected`, `test_greg_appraisal_closure`, `test_greg_closure_integrity`,
  `test_greg_goal_gravity_merge`, `test_greg_bindings`, `test_greg_sop_compounding` and `test_greg_reconciliation`.
- **Related suites: 48 passed, 11 skipped.** Eight skips need bubblewrap. The other three are `browser.render`
  tests that find no browser through `capabilities.chrome_binary()` (the R6 follow-up). These were
  `test_greg_capabilities`, `test_greg_adversarial_machine`, `test_greg_browser`, `test_greg_packaging` and
  `test_greg_confined_egress`.
- The full suite was not run (too slow on this machine).

### Mutants

- `python -B scripts/ci/check_browser_method_gate_mutants.py`: **26/26 caught**, rc 0. Every catching test passed
  unmutated first.
  - The round adds 14 mutants. Among them: page routing instead of browser-target interception; a redirect hop not
    decided; a write at the close dropped; the prelude not installed; WebSocketStream left on in the engine; whole
    params bindable.
  - Each of the two layers that remove channels is mutated alone and caught by a test of that layer alone.
- The existing `scripts/ci/check_pipeline_mutants.py`: **3/3 caught**, rc 0.

## Limitations

- **GET with side effects.** The gate sees methods, not effects. A logout or unsubscribe link, or a state-changing
  GET API, on a signed origin cannot be detected. The same holds for data a page puts in a GET's query to a signed
  origin.
- **Page-script-level removals.** The removal of `Worker`, service-worker registration, `WebTransport` and
  `RTCPeerConnection` is page-script level. It is as strong as Playwright's own WebSocket mock and no stronger. It
  was verified for the page and for dynamically created `about:blank` frames. A realm the init script does not
  reach would reopen those channels. `WebSocketStream` and `SharedWorker` are also off in the engine.
- **WebTransport** was not exercised end to end: there is no HTTP/3 server here.
- **Pages that need a worker lose it.** A page that sends telemetry writes ends the session at the boundary unless
  the founder signs that exact endpoint, including at close.
- **The interception's fail-safe default is not mutation-tested.** A request whose decision raises is refused, but
  no page could make the decision raise.
- **Confined bodies.** The relay checks origins only. The confined browser test, edited to switch off the new
  interception, was not run here (no bubblewrap).
- **Registration still accepts whole-params.** `greg/missions.py` registration (`validate_mission`, `inline_refs`)
  still accepts a whole-params `$from_action`. It is refused at `resolve`, so it never dispatches; end-to-end
  dispatch was not run. The bind-edge route (`protected_param`) still accepts `steps` or `steps.N`. A step's `key`
  and a `mouse` step's `x` and `y` stay bindable.
- **Second browser discovery glob.** `greg/capabilities.py` `chrome_binary()` still globs only `chrome-linux/` (R6).
  `capabilities.py` is edited by open PRs.
- **CI workflow not run.** `computer-use.yml` was not executed here; it is checked only as YAML.
- **Chromebook.** Nothing ran on the Chromebook. `install.sh` and `doctor.py` are changed by open PR #211.
