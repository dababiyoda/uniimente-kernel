# GREG body evidence — 2026-09-25 (refreshed 2026-09-26: Spider-Web; then reconciliation, phone, browser)

Environment: Linux container, Python 3.11, cryptography 41.0.7, supervisor 4.3.0, libseccomp present.
Not macOS. The founder key in every run is a per-test Ed25519 key, never Alfonso's.

| File | What it shows |
|---|---|
| `full-suite.log` | `python -m pytest -q`: 819 passed (739 before GREG, 788 first GREG commit, 800 Spider-Web; 0 regressions) |
| `greg-unit-offline.log` | 74 GREG unit tests under `tools/offline_test.py` (seccomp: socket creation denied). `test_greg_browser.py` is excluded because it needs loopback sockets. |
| `supervised-repeat.log` | real-process supervised test repeated (9/9 passes across the session incl. these 3) |
| `supervised-run-ledger.jsonl`, `supervised-run-summary.json` | retained history of one supervised run: 2 boots, `body.recovered` after SIGKILL, exactly 1 decision request, exactly 1 receipted action, supervisor `EXITED` after the signed stop |
| `vepmc-path-summary.json`, `vepmc-path-ledger.jsonl` | first-VEPMC acceptance path through the product CLI under supervisord: signed template mission, interface exits, approval boundary, SIGKILL while waiting, autonomous restart + `body.recovered`, signed approval, one receipted write, separate-process appraiser VERIFIED, closure id read from `greg vepmc`, signed acceptance. VEPMC conditions met 8/9; missing only `mac_body` (Linux). VEPMC = 0 |
| `vepmc-path-repeat.log` | the VEPMC path test repeated 5/5 |
| `phone-e2e-summary.json`, `phone-e2e-repeat.log` | phone path with real processes and a real browser engine: supervisord body plus `greg serve` plus Chromium 141 with an iPhone 13 profile running `greg/phone/`. The page makes a non-extractable Ed25519 key (export refused), the founder delegates it, a tap approves a real approval boundary (`device:iphone`, Spanish reason intact), the appraiser returns VERIFIED, and a tap stops the body, which supervisord leaves `EXITED`. 6/6 after the fix below. **Not iOS Safari.** |
| `browser-render.log` | `browser.render` through a founder-signed mission on real Chromium: JavaScript-only text observed through the Gate; a hostile beacon (by hostname and by IP literal) received nothing; a target not naming the contacted host is refused |
| `integration-watch-real.json` | `integration-watch` on the real Kernel/DALEOBANKS/WMI clones: one founder decision carrying exact source evidence for the stop-bypass on kernel `main` (`egregore/runtime.py:496`, fixed on this branch) and DALEOBANKS' reflection outcome gap |
| `ci-and-verifier.log` | schema refs, authority singleton, sealed-developmental, verifier V1–V5 PASS (V3 includes `greg_body`) |

Negative evidence retained in the session record (fixed before commit, preserved here as lineage):
genome validator rejected a capability without inputs; sensor-identity collision refused by the spine
(event id reused with different content); surprise loop (ineffective action repeated) caught by test;
paid strategies refused because policy was pre-evaluated without the grant; acquired tool ran in a missing
workspace; missing file misclassified as sensor failure; signal handler installation outside the main thread.

Spider-Web commit negative evidence: the Proof→Routing test first carried a vacuous `or` assertion
(caught on self-review and tightened); two mutations of the routing rule (penalty removed; foreign faults
penalized) each fail the test. A runbook dry run with a mistyped repository path was correctly refused by
`fs` root containment; the corrected run observed the real Kernel/DALEOBANKS/WMI repositories consistent.

Reconciliation/phone/browser session negative evidence (all reproduced before fixing):
1. **Stop bypass (pre-existing on `main` and #113):** a fabricated `sha256:000…` hash resumed
   suspended standing cognition, and a forged resume record cleared a stop on replay. The old test
   asserted this behavior. Fixed by porting PR #112.
2. **Lost approvals (pre-existing on #113):** the phone end-to-end test failed 3 of 4 times. Tracing
   showed the book rebuilt before the request existed, and commands applied before the next rebuild.
   A plain `greg decide` without a restart failed 2 of 3 times. My first deterministic test ticked
   between request and answer and wrongly passed; it was rewritten to reproduce the exact timing.
3. **Blind NO_STRATEGY watcher:** the healed world was never re-observed (found when the
   integration-watch test's second half failed).
4. **Browser egress claim was false at first:** DNS rules alone let an IP-literal beacon through.
5. **Weak controls caught on self-review:** an export check that also "passed" when the key was
   missing; a raw-HTML control that matched the script source; a vacuous assertion. All rewritten.
6. Mutation checks: JS key sort removed → compatibility test fails; dead proxy removed → beacon
   test fails.
