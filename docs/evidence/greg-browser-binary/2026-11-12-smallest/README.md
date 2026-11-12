# browser.render: the smallest repair that passes the declared requirements

The founder's instruction of 2026-11-12 (answer 3), verbatim: "Browser repair: compare the minimal reorder with the
larger browser check under the relevant supported conditions. Recommend the smallest implementation that passes the
declared requirements. Show any remaining compatibility boundary."

Branch `claude/browser-render-smallest-20261112`, off #196's `8d205324`. The larger implementation is draft #293
(`32ca8de7`); its evidence is `docs/evidence/greg-browser-binary/2026-11-11/README.md` on that branch. Every number
below was read from a run made for this record on 2026-11-12, in one cloud container or from Canonical CI logs of
draft #308. Nothing here is founder-used or externally verified; the founder keys are test keys.

## Recommendation

Take variant S: the four-line reorder plus four small changes, three that declared requirements need and one that
an inferred requirement needs; 54 added and 8 removed lines in one file (`greg/capabilities.py`), against #293's 258
added and 19 removed there and 15 added and 4 removed in `tests/security/effect-call-allowlist.json`. In this
container, the only condition where both were run, S passes every requirement #293 passes, and #293's tests that fail
on S assert its check (a browser that is installed but never returns is passed over for a later one, the memory of
what was judged, the judging budget), its build-number order or names S does not define; no declared requirement
names those behaviours. The check would earn its place on a supported machine where the first
installed browser cannot render and a later one can; none was found, and the boundary below lists what no available
condition exercised.

## 1. The declared requirements

| # | Requirement | Source |
| --- | --- | --- |
| R1 | browser.render is read_only and retry_safe; its target is `web:<host>`, and the signed target must name the host the URL contacts (`target_from="url"`, `network="target-host-only"`) | manifest, `greg/capabilities.py` lines 969-977 on `8d205324`; `AuthorityOffice.precheck`, `greg/authority.py` lines 69-86 |
| R2 | Every manifest validates | `CapabilityManifest.validate`, `greg/capabilities.py` line 105 |
| R3 | A body with no browser answers UNAVAILABLE at the office's precheck, before the adapter runs | `CapabilityManifest.available` (lines 174-181, through `binaries`) and `AuthorityOffice.precheck` (`greg/authority.py` lines 75-77) |
| R4 | `GREG_CHROMIUM` is the founder's choice of browser | `chrome_binary` docstring, line 662; #308's commit `72709e17`: "browser.render already honours it as the founder's choice" |
| R5 | Only the signed origin is reachable; https, or http on loopback only; a fresh profile, no extensions, no sync, no background networking | `browser_render` docstring and flags, lines 690-732 |
| R6 | A render that has not finished in 45 seconds is a refusal that names the limit | lines 737-738 |
| R7 | Chromium's own sandbox is asked for except as root on Linux and behind the relay, and the receipt says which (`os_sandboxed`) | lines 724-727 |
| R8 | On a confined-egress body the browser runs in a bubblewrap network namespace whose only way out is the relay; without namespaces nothing runs | `_render_behind_relay`, lines 759-775; `tests/integration/test_greg_confined_egress.py` line 357 |
| R9 | A signed mission observes text that exists only after the page's JavaScript ran, through the Gate with a retained receipt; the page's beacons are not reached; a target that does not name the host is refused; plain http beyond loopback is refused | `tests/unit/test_greg_browser.py` (three tests) |
| R10 | The separate appraiser re-derives the receipt's binding, the manifest digest included, in its own process, which `greg/body.py` starts without `GREG_CHROMIUM`; it answers VERIFIED or REFUTED, and a true closure is VERIFIED | `greg/appraisal.py` lines 126-200 (`manifest_digest`, line 177); `greg/body.py` lines 87-90 and 1104-1105 |
| R11 | A refusal of the capability is a `CapabilityError`; only `executor_error` counts against a capability; a timeout is `transient` | `CapabilityError` docstring, lines 55-63 |
| R12 | `browser_render` asks `chrome_binary()` (no arguments, returns a path) for its browser | `tests/unit/test_greg_faithful_text.py` line 244 patches exactly that |
| R13 | Every process browser.render starts is listed, with a pin, in `tests/security/effect-call-allowlist.json` | `tests/unit/test_effect_call_allowlist.py` |
| R14 | "Do not count a missing browser dependency as a passing test. Distinguish environment failures from code defects using comparable parent/head evidence." | founder message of 2026-11-11, section 12 (session record; the switch is `GREG_REQUIRE_BROWSER=1`, #293's and #308's test changes) |
| R15 | "Distinguish uncertainty, timeout, refusal, failure, and refutation." and "A timeout does not establish measured failure." | founder message of 2026-11-12, sections 1 and 11 (session record) |
| I1 | Inferred from R4: `GREG_CHROMIUM` naming no executable file is refused by name, not replaced by another browser | inference; no rule states it |
| I2 | Inferred from the persistent body: a browser build replaced while the body runs is found again without a restart | inference from R3 and `greg/body.py`'s persistent loop |

The order of candidates (headless shell first) is not a requirement. It is the means by which R9 holds under R14 in
this container.

## 2. Variant S, one commit per part

| Commit | Part | `greg/capabilities.py` | Requirement | Before, then after (measured here) |
| --- | --- | --- | --- | --- |
| `33e6c9d8` | The four-line reorder of #293's README, as written there | +4 -2 | R9 under R14 | `test_greg_browser.py` on `8d205324`: 1 passed, 2 skipped in 91.54 s (both "browser did not finish rendering within 45 seconds"); a signed mission refused at 45.68-45.82 s on each of 4 ticks and never closed. After: ACHIEVED at tick 1, VERIFIED |
| `bd028c0b` | The manifest names no binary; `available()` asks `browser_installed()` each time (`AVAILABLE_AT_CALL_TIME`); the paths are named constants a test can stand in for | +36 -9 | R10, R3, I2 | With the reorder alone and `GREG_CHROMIUM` naming the headless shell by another path: ACHIEVED, REFUTED ("rendered: receipt not bound to this closure and signed sensor"). After: ACHIEVED, VERIFIED |
| `b9dbeca5` | `GREG_CHROMIUM` set to anything but the absolute path of an executable file is refused by name and is the only candidate (#293's wording) | +17 -5 | I1 | Before: the variable was passed over and another browser ran. After: refused, UNAVAILABLE with the same words |
| `c32c3f7b` | No installed browser is a `CapabilityError` from the adapter | +3 -1 | R11, R15 | Last browser gone between precheck and render (simulated, `probes/vanished_probe.py`): "sensor UNCERTAIN: executor raised FileNotFoundError ...; outcome unknown", no receipt. After: "sensor REFUSED: capability refused: no Chrome or Chromium is installed on this body", with a receipt |
| `07d54258` | An installed browser the system cannot start is a `CapabilityError` (unconfined route) | +4 -1 | R11, R15 | `GREG_CHROMIUM` naming a script whose interpreter is missing (`probes/unstartable_probe.py`): "sensor UNCERTAIN: executor raised FileNotFoundError ..." no receipt. After: "sensor REFUSED: capability refused: browser could not be started (No such file or directory)", with a receipt. Found by running #293's tests on S |
| `9739b904` | `tests/unit/test_greg_browser_choice.py` (13 tests, stand-in browsers); `scripts/ci/check_browser_choice_mutants.py`; wired into Canonical CI job 10 | (tests) | all of the above | 13 passed; 15/15 mutants caught |

Not taken from #293, and why:

- The render check, its memory (`_render_judged`), its retry time, its judging budget and its profile class: no
  declared requirement needs them on any available condition (section 4).
- Numeric build ordering and its `int()` guard: S keeps the reorder's text order and has no `int()`, so the crash the
  guard prevents cannot occur. No requirement names the newest build.
- `_sandboxes_itself` and `_headless`: refactors shared with the check. S leaves the sandbox rule (R7) and the flags
  (R5) as they are on `8d205324`.
- `RENDER_SECONDS`: S keeps the literal 45 of `8d205324`.
- Allowlist changes: S adds no process and changes no pinned call; `tests/unit/test_effect_call_allowlist.py`, 18
  passed.
- `tests/unit/test_greg_browser.py`'s `GREG_REQUIRE_BROWSER` switch: #308 delivers it for this file and the other
  browser tests (`tests/browser_requirement.py`). S keeps `8d205324`'s file so the two do not conflict
  (`git merge-tree` of S's tests commit and #308's head: no conflict; with #293's head: conflicts in
  `greg/capabilities.py` and the workflow, as alternatives). Both versions of the file were run against S below.
- One reading, not a measured defect: #293's check remembers a check that did not finish in 45 seconds as "cannot
  render" and passes that browser over for `RENDER_RETRY_SECONDS` (600 s). R15 says a timeout does not establish a
  measured failure. S draws no conclusion from a timeout: each render that times out is refused as a timeout.

Line counts (`git diff --numstat 8d205324`): S changes `greg/capabilities.py` +54 -8 and `greg/README.md` +1 -1, and
adds 203 lines of tests, an 81-line gate and 2 lines of workflow. #293 changes `greg/capabilities.py` +258 -19,
`tests/security/effect-call-allowlist.json` +15 -4 and `greg/README.md` +1 -1, and adds 575 lines of tests (+6 -2 in
`test_greg_browser.py`), a 178-line gate and 2 lines of workflow.

## 3. The options in this container

Linux, root, Python 3.13.18, Chrome for Testing 153.0.8010.12 build 1243 under `/opt/pw-browsers` (the full browser
and the headless shell; the headless shell is a 198-byte shell wrapper around `chrome-headless-shell.real`),
`/usr/bin/google-chrome` a wrapper around the full browser, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`. Other
sessions ran in the same container (load average 4.3 on 4 CPUs at the start), so the seconds below are single runs
and noisy.

"Mission" is one founder-signed mission whose only check is browser.render on a local page, run by a real Body and
appraised by the separate appraiser process the Body starts (`probes/mission_probe.py`, run with `PYTHONPATH` the
tree under test and an environment of `PATH=/usr/bin:/bin`, `LANG`, `HOME`, `TMPDIR` and `PLAYWRIGHT_BROWSERS_PATH`).
"Chosen" is the same with `GREG_CHROMIUM` set, in the body's process only, to a link to the headless shell at another
path, as job 11 of #308 names its own headless shell.

| Option | `test_greg_browser.py` with `GREG_REQUIRE_BROWSER=1` | Mission | Mission, chosen |
| --- | --- | --- | --- |
| Do nothing (`8d205324`) | #293's file: 1 passed, 2 errors in 91.01 s ("browser did not finish rendering within 45 seconds") | REFUSED on 4 of 4 ticks, 45.68-45.82 s each; never closed | ACHIEVED, REFUTED ("rendered: receipt not bound to this closure and signed sensor") |
| Do nothing, set `GREG_CHROMIUM` instead (`8d205324` with #308's tests) | #308's file, chosen: 3 passed in 4.56 s | not applicable | ACHIEVED, REFUTED (row above) |
| Reorder alone (`33e6c9d8`) | not run separately | ACHIEVED at tick 1, VERIFIED | ACHIEVED, REFUTED (same finding) |
| S (`07d54258`) | #293's file: 3 passed in 3.46 s. #308's file: 3 passed in 3.32 s; with chosen: 3 passed in 3.93 s | ACHIEVED at tick 1 (1.53 s), VERIFIED | ACHIEVED at tick 1 (1.00 s), VERIFIED |
| #293 (`32ca8de7`) | #293's file: 3 passed in 7.13 s | ACHIEVED at tick 1 (3.19 s), VERIFIED | ACHIEVED at tick 1 (3.68 s), VERIFIED |

Setting `GREG_CHROMIUM` instead of changing code makes the tests pass (here, and on the GitHub runner, section 5),
and the separate appraiser still refutes the true closure.

A render that times out, on S with `GREG_CHROMIUM` naming the full browser: 3 of 3 refused "browser did not finish
rendering within 45 seconds" (45.3, 45.7, 45.2 s), each a `CapabilityError`. With the timeouts on `8d205324` above
(2 in each of its two `test_greg_browser.py` runs, 4 in its mission) that is 11 of 11. No browser process and no
`greg-browser-*` profile was left behind after any of them (each run's processes were looked for by the `HOME` of
the profiles under this record's own temporary directory). #293's README records, for its check's profile, one real
run in which removing the profile raised "Directory not empty" and replaced the answer; that did not happen to the
render's profile in these 11.

## 4. #293's tests on S

`tests/unit/test_greg_browser_binary.py` from `32ca8de7` (sha256
`e561ec12486cae45d0b619cfc9abee6b52c4e23f6fa5b4d22037af10c259fbe3`), copied unchanged onto S at `9739b904` and run;
not committed, since 37 of its 41 tests fail on S.

- Unchanged: "6 failed, 35 errors in 0.53s". Every error is the `machine` fixture's `setattr` of `RENDER_SECONDS`,
  which S does not define; the 6 failures call `_sandboxes_itself`, `_build` or `JUDGING_SECONDS`.
- With a measuring plugin that only gives `greg.capabilities` the two names #293's `machine` fixture patches and S
  does not define (`RENDER_SECONDS = 45`, which S does not read, and `_render_judged = {}`, the check's memory), so
  the fixture can set up: "37 failed, 4 passed in 67.36s". The plugin is
  `probes/browser_check_shim.py`; it supplies no name a test body calls.
- On #293's own tree: 41 passed in 24.03 s.

Readings: **req**, asserts a declared or inferred requirement and passes on S; **req-holds**, asserts a
requirement that S meets (its own test asserts the same values) and fails only on a name S does not define;
**req-name**, asserts the sandbox rule R7, which S leaves as on `8d205324`, through #293's helper name; **mixed**,
the requirement assertions pass on S and a later assertion asks for the check's behaviour or its names; **check**,
asserts only the check, its memory, its judging budget or its profile; **other**, #293's build-number order, which no
requirement names.

Totals: req 4, req-holds 7, req-name 4, mixed 5, check 19, other 2 (41). No test fails on S because S breaks a
requirement. One did before `07d54258`: `test_a_success_is_not_kept_when_the_browser_can_no_longer_be_started` failed
on S with `FileNotFoundError` where it expects a refusal, which is how that commit was found.

| Test | S (unchanged run) | S (fixture names supplied) | Where it fails on S | #293 | Reading |
| --- | --- | --- | --- | --- | --- |
| `test_a_directory_or_a_file_that_is_not_executable_is_not_a_candidate` | ERROR | PASSED |  | PASSED | req: what counts as installed |
| `test_behind_the_relay_no_browser_is_started_outside_the_namespace` | ERROR | PASSED |  | PASSED | req: R8 |
| `test_behind_the_relay_without_namespaces_nothing_runs_at_all` | ERROR | PASSED |  | PASSED | req: R8 |
| `test_the_manifest_names_no_binary_and_says_what_is_installed_each_time_it_is_asked` | ERROR | PASSED |  | PASSED | req: R10, R3, I2 |
| `test_the_headless_shell_comes_first_and_the_newest_build_by_number` | ERROR | FAILED | test_greg_browser_binary.py:98 AssertionError | PASSED | other: #293's build-number order (999 before 1243 on S); no requirement names it. Headless shells first holds on S |
| `test_a_browser_that_never_returns_is_passed_over_for_one_that_renders` | ERROR | FAILED | test_greg_browser_binary.py:107 AttributeError `installed_chrome` | PASSED | check: fall-through and memory |
| `test_a_failure_is_judged_again_only_after_the_retry_time` | ERROR | FAILED | test_greg_browser_binary.py:119 AssertionError | PASSED | check: memory, retry time |
| `test_a_build_that_rendered_is_not_run_again_until_the_binary_changes` | ERROR | FAILED | test_greg_browser_binary.py:126 AttributeError `RENDER_RETRY_SECONDS` | PASSED | check: memory |
| `test_only_a_binary_that_writes_the_page_it_was_given_renders[fails]` | ERROR | FAILED | test_greg_browser_binary.py:142 AttributeError `cannot_render` | PASSED | check: the check's judgement of a local page |
| `test_only_a_binary_that_writes_the_page_it_was_given_renders[silent]` | ERROR | FAILED | test_greg_browser_binary.py:142 AttributeError `cannot_render` | PASSED | check: the check's judgement of a local page |
| `test_only_a_binary_that_writes_the_page_it_was_given_renders[another-page]` | ERROR | FAILED | test_greg_browser_binary.py:142 AttributeError `cannot_render` | PASSED | check: the check's judgement of a local page |
| `test_only_a_binary_that_writes_the_page_it_was_given_renders[page-then-failure]` | ERROR | FAILED | test_greg_browser_binary.py:142 AttributeError `cannot_render` | PASSED | check: the check's judgement of a local page |
| `test_a_binary_that_cannot_be_started_is_a_reason_not_a_crash` | ERROR | FAILED | test_greg_browser_binary.py:153 AttributeError `cannot_render` | PASSED | check: cannot_render; the render's own refusal of the same binary holds on S (07d54258) |
| `test_the_founders_choice_is_the_only_browser_run` | ERROR | FAILED | test_greg_browser_binary.py:161 AttributeError `installed_chrome` | PASSED | mixed: only candidate (I1) holds on S; refusing a chosen browser that never returns is the check |
| `test_a_choice_that_names_no_browser_is_refused_by_name_and_nothing_else_is_run[a directory]` | ERROR | FAILED | test_greg_browser_binary.py:204 AttributeError `installed_chrome` | PASSED | req-holds: I1 and R3; fails on the name installed_chrome, which S does not define; S passes the same six values |
| `test_a_choice_that_names_no_browser_is_refused_by_name_and_nothing_else_is_run[a file that is not executable]` | ERROR | FAILED | test_greg_browser_binary.py:204 AttributeError `installed_chrome` | PASSED | req-holds: I1 and R3; fails on the name installed_chrome, which S does not define; S passes the same six values |
| `test_a_choice_that_names_no_browser_is_refused_by_name_and_nothing_else_is_run[a path with nothing at it]` | ERROR | FAILED | test_greg_browser_binary.py:204 AttributeError `installed_chrome` | PASSED | req-holds: I1 and R3; fails on the name installed_chrome, which S does not define; S passes the same six values |
| `test_a_choice_that_names_no_browser_is_refused_by_name_and_nothing_else_is_run[an unexpanded home directory]` | ERROR | FAILED | test_greg_browser_binary.py:204 AttributeError `installed_chrome` | PASSED | req-holds: I1 and R3; fails on the name installed_chrome, which S does not define; S passes the same six values |
| `test_a_choice_that_names_no_browser_is_refused_by_name_and_nothing_else_is_run[a relative path that resolves from the working directory]` | ERROR | FAILED | test_greg_browser_binary.py:204 AttributeError `installed_chrome` | PASSED | req-holds: I1 and R3; fails on the name installed_chrome, which S does not define; S passes the same six values |
| `test_a_choice_that_names_no_browser_is_refused_by_name_and_nothing_else_is_run[a working path with a newline after it]` | ERROR | FAILED | test_greg_browser_binary.py:204 AttributeError `installed_chrome` | PASSED | req-holds: I1 and R3; fails on the name installed_chrome, which S does not define; S passes the same six values |
| `test_no_installed_browser_is_a_refusal` | ERROR | FAILED | test_greg_browser_binary.py:225 AttributeError `installed_chrome` | PASSED | req-holds: R3, R11; fails on the name installed_chrome; S passes the same assertions |
| `test_a_render_runs_the_browser_that_passed_and_says_which` | ERROR | FAILED | capabilities.py:784 CapabilityError | PASSED | check: fall-through to the browser that passed |
| `test_the_check_contacts_no_one_and_runs_as_a_render_runs[sandboxes-itself]` | ERROR | FAILED | test_greg_browser_binary.py:242 AttributeError `_sandboxes_itself` | PASSED | check: the check's command line |
| `test_the_check_contacts_no_one_and_runs_as_a_render_runs[as-root-on-linux]` | ERROR | FAILED | test_greg_browser_binary.py:242 AttributeError `_sandboxes_itself` | PASSED | check: the check's command line |
| `test_only_root_on_linux_is_told_the_browser_cannot_sandbox_itself[linux-0-False]` | FAILED | FAILED | test_greg_browser_binary.py:272 AttributeError `_sandboxes_itself` | PASSED | req-name: R7, unchanged from 8d205324 on S; fails on #293's helper _sandboxes_itself |
| `test_only_root_on_linux_is_told_the_browser_cannot_sandbox_itself[linux-1000-True]` | FAILED | FAILED | test_greg_browser_binary.py:272 AttributeError `_sandboxes_itself` | PASSED | req-name: R7, unchanged from 8d205324 on S; fails on #293's helper _sandboxes_itself |
| `test_only_root_on_linux_is_told_the_browser_cannot_sandbox_itself[darwin-0-True]` | FAILED | FAILED | test_greg_browser_binary.py:272 AttributeError `_sandboxes_itself` | PASSED | req-name: R7, unchanged from 8d205324 on S; fails on #293's helper _sandboxes_itself |
| `test_only_root_on_linux_is_told_the_browser_cannot_sandbox_itself[darwin-501-True]` | FAILED | FAILED | test_greg_browser_binary.py:272 AttributeError `_sandboxes_itself` | PASSED | req-name: R7, unchanged from 8d205324 on S; fails on #293's helper _sandboxes_itself |
| `test_a_build_directory_without_a_plain_number_is_listed_last_and_breaks_nothing` | ERROR | FAILED | test_greg_browser_binary.py:292 AssertionError | PASSED | other: #293's build-number order; S has no int(), so nothing to break |
| `test_a_candidate_that_vanished_before_it_was_judged_is_a_reason_not_a_crash` | ERROR | FAILED | test_greg_browser_binary.py:298 AttributeError `cannot_render` | PASSED | check: cannot_render; a vanished browser at render time is a refusal on S (07d54258) |
| `test_a_build_is_its_size_its_modification_time_and_its_change_time` | FAILED | FAILED | test_greg_browser_binary.py:311 AttributeError `_build` | PASSED | check: memory key |
| `test_a_replacement_of_the_same_size_with_the_same_modification_time_is_judged_again` | ERROR | FAILED | test_greg_browser_binary.py:325 AttributeError `cannot_render` | PASSED | check: memory key |
| `test_a_render_that_never_returns_ends_at_the_limit_and_the_binary_is_judged_again` | ERROR | FAILED | test_greg_browser_binary.py:342 AssertionError | PASSED | check: 1 s limit (RENDER_SECONDS) and re-judging; R6 at 45 s holds on S (3 of 3 real timeouts) |
| `test_a_success_is_not_kept_when_the_browser_behind_a_wrapper_stops_rendering` | ERROR | FAILED | test_greg_browser_binary.py:357 AssertionError | PASSED | check: memory, fall-through |
| `test_a_success_is_not_kept_when_the_browser_can_no_longer_be_started` | ERROR | FAILED | capabilities.py:775 CapabilityError | PASSED | mixed: the refusal (R11, R15) holds on S after 07d54258; then falling through to another browser is the check |
| `test_failing_to_remove_a_profile_never_replaces_the_result` | ERROR | FAILED | test_greg_browser_binary.py:395 AttributeError `cannot_render` | PASSED | check: the check's profile removal |
| `test_the_longest_call_ends_before_the_body_is_taken_for_stopped` | FAILED | FAILED | test_greg_browser_binary.py:410 AttributeError `JUDGING_SECONDS` | PASSED | check: the judging budget |
| `test_one_call_judges_for_a_bounded_time_and_names_what_it_did_not_judge` | ERROR | FAILED | test_greg_browser_binary.py:420 AttributeError `JUDGING_SECONDS` | PASSED | check: the judging budget |
| `test_behind_the_relay_a_browser_is_not_refused_by_the_unconfined_sandbox_rule` | ERROR | FAILED | test_greg_browser_binary.py:480 AttributeError `_sandboxes_itself` | PASSED | mixed: R7/R8 unchanged on S; fails on the helper _sandboxes_itself; its last line asks the check |
| `test_a_running_body_renders_across_a_browser_upgrade` | ERROR | FAILED | test_greg_browser_binary.py:542 AttributeError `RENDER_CHECK_PAGE` | PASSED | mixed: I2, R3, R10 hold on S (all but the last line); the last line expects the check's own run |
| `test_a_closure_observed_with_the_founders_chosen_browser_is_verified` | ERROR | FAILED | test_greg_browser_binary.py:575 AttributeError `RENDER_CHECK_PAGE` | PASSED | mixed: R10 holds on S (ACHIEVED, VERIFIED); the last line expects the check's own run |

## 5. Conditions

**This container.** Section 3. bubblewrap is absent (`which bwrap` finds nothing), so
`test_greg_confined_egress.py::test_the_browser_renders_behind_the_relay_and_its_page_cannot_reach_anything_else`
skips on S: "no bubblewrap network namespaces here".

**A GitHub runner (read, not triggered).** Canonical CI on #308's head `a995c3ce` (run 43272525812), image
ubuntu-26.04 20261101.186.1, Python 3.11.18:

- Job 11 (job 131376162958): Playwright installed Chrome for Testing 153.0.8010.12 and Chrome Headless Shell
  153.0.8010.12 (v1243) under `/home/runner/work/_temp/pw-browsers`; `GREG_CHROMIUM` named that headless shell;
  `kernel.apparmor_restrict_unprivileged_userns = 0`; "bubblewrap namespaces: usable"; `GREG_REQUIRE_BROWSER: 1`;
  "38 passed in 77.81s". The 38 (collected here on #308's tree) include `test_greg_browser.py`'s three, the confined
  browser.render test and `test_greg_mcp_token.py`'s words-to-page test, which closes through browser.render.
- The same job on `106a8eb8` (run 43269912274, job 131363382083), before AppArmor's restriction was lifted: "6
  failed, 30 passed, 2 errors". The two errors are `test_greg_browser.py`'s fixture: "browser could not render the
  page: ... No usable sandbox" (the unconfined render, not root, asks for Chromium's own sandbox). By the progress
  line, the confined browser.render test passed there.
- What this exercises: `8d205324`'s browser.render (#308 does not change `greg/capabilities.py`) with the browser
  named by `GREG_CHROMIUM`. Not S, not #293, and not the default order. No job 11 test asserts the appraisal, so the
  REFUTED verdict that section 3 shows for a chosen browser would not be seen there (inferred: the appraiser's own
  lookup cannot find `$RUNNER_TEMP/pw-browsers`).
- Job 8 (job 131376163098): its test step's environment shows `PLAYWRIGHT_BROWSERS_PATH: ` and `GREG_CHROMIUM: `
  empty, because the step that writes them to `$GITHUB_ENV` reads `$shell`, which is set only in the step before.
  "127 passed". None of job 8's test files names browser.render. Job 8 says nothing about browser.render.

**Confined egress with bubblewrap.** Absent here. Exercised only on the runner, as above, with `8d205324`'s code and
`GREG_CHROMIUM` naming Playwright's headless shell. S changes nothing on that route except which browser is first
when `GREG_CHROMIUM` is unset.

**macOS, the founder's Chromebook.** Not available. Nothing was run on either.

## 6. The remaining compatibility boundary

What no available condition exercised:

1. S's default order outside this container. The runner names `GREG_CHROMIUM`; its Playwright builds sit under
   `$RUNNER_TEMP`, which neither S nor #293 searches (both search `/opt/pw-browsers` and the system paths, as
   `8d205324` did). On a body where Playwright installed to its default cache (`~/.cache/ms-playwright`, or
   `~/Library/Caches/ms-playwright` on macOS) only the system paths and `GREG_CHROMIUM` find a browser, in S and in
   #293 alike.
2. A machine where the first installed candidate cannot render and a later one can. There S refuses each render at
   45 seconds and #293 falls through to the later one. Not found: here the headless shell is first and renders; on
   the runner `GREG_CHROMIUM` decides. This is the condition that would revive the check (below).
3. Two headless-shell builds whose numbers differ in length (999 and 1243): S tries 999 first. No machine here has
   two builds; no requirement names the newest.
4. A non-root Linux whose AppArmor restricts unprivileged user namespaces (Ubuntu 23.10 and later): the unconfined
   render fails with "No usable sandbox" (`106a8eb8`, job 11). The same in `8d205324`, S and #293; job 11 lifts the
   restriction on the runner. A founder body with that restriction is unmeasured.
5. Whether a headless shell that is itself a shell wrapper (as here) starts inside the bubblewrap namespace, where
   only the binary's directory is bound read-only. The runner's headless shell is Playwright's own download; this
   container's wrapper was not run under bubblewrap anywhere.
6. Whether full Chrome returns from a one-shot `--headless=new --dump-dom` on macOS, on the Chromebook or on the
   runner. Measured only here, where it does not.
7. A render's profile that cannot be removed after a timeout, replacing the timeout with an `OSError` (an unknown
   outcome at the Gate). Not seen in 11 timeouts; #293 saw it once for its check's profile.

## 7. What would revive the check

A supported machine where, with `GREG_CHROMIUM` unset, the first installed candidate in S's order cannot render and
a later one can: `tests/unit/test_greg_browser.py` with `GREG_REQUIRE_BROWSER=1` failing on S and passing on #293
there, and a signed browser.render mission refused on S and VERIFIED on #293. Until then the founder can name the
working browser with `GREG_CHROMIUM` on such a machine, which S honours and the appraiser verifies. If no installed
browser renders, the check does not render either; it only names each candidate's reason, after up to two 45-second
checks per call.

## 8. Founder questions

1. I1 is inferred, not declared: keep the refusal of a `GREG_CHROMIUM` that names no executable file (`b9dbeca5`), or
   drop that commit and return to passing it over?
2. Is a body with Playwright installed to its default cache a supported condition? Neither S nor #293 finds it.
3. On a non-root Linux with AppArmor's user-namespace restriction, is lifting the restriction part of body setup (as
   job 11 does), or should the unconfined render take another route there?
4. #308's job 8 sets `GREG_CHROMIUM` and `PLAYWRIGHT_BROWSERS_PATH` to empty strings (above). That belongs to #308's
   owner.

## Reproduce

```
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers GREG_REQUIRE_BROWSER=1 python -m pytest -q tests/unit/test_greg_browser.py
python -m pytest -q tests/unit/test_greg_browser_choice.py
python scripts/ci/check_browser_choice_mutants.py
```
