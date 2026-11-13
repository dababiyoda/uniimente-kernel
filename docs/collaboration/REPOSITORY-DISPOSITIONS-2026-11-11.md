# Dispositions of what was inspected on 2026-11-11

Session `session_01Kucyfm9exT5imDVYvHTYSv`, written 2026-11-11 23:22 UTC (read from the clock) against the integration line #196 at
`8d20532464b1533b28d71d8331ca3412a90dbb11`.

The founder's resume message of 2026-11-11 (message D in
[the source file](../intent/sources/ABSOLUTE-OPUS-MAXIMUS-2026-11-11-source.md)) asks that "every substantial
component inspected should receive a documented disposition: integrate, extract useful parts, consolidate, preserve
for a justified future use, or reject with reasons." This file is that record for one session's day. It uses those
five words and no others.

What it is not: a merge decision, a review of pull requests this session did not read, or evidence that anything
below runs on the founder's device. Everything was run in a cloud container with test keys. VEPMC is 0. Intake is
the integration owner's and merges are the founder's.

How each row was inspected is stated, because the depth differs:

- **read**: the diff or the files were read.
- **run**: its tests or a probe were executed here, with the result seen.
- **rehearsed**: `scripts/compose_rehearsal.py` (#296) ran the tests each head changed, on its own tree and merged.
  A rehearsal checks only those tests. It is not a review.
- **reviewed**: a separate agent, given the code and not the author's conclusion, tried to refute it. That is a
  second process on the same model, not an independent operator.

## 1. Other sessions' open pull requests

| Component | Inspected | Disposition | Reason and evidence | What is still owed |
|---|---|---|---|---|
| #290 `facea170`, authority identity base | read, run, rehearsed | integrate | #291 is built on it. Its 9 changed tests pass on the merged tree | #291 reverses one of its choices (an office without a registry "keeps its earlier behaviour"). That is the founder's to settle |
| #273 `331de165`, background dispatch | read, run, rehearsed | integrate, with one call-site line | 13 of its tests pass alone and fail merged with #291: it hands the office a wrapped adapter and #291's office runs only the registered one. With `adapter=adapter, around=wrap` at its one call site the merged tree passes | Its owner or the integrator applies the line at intake |
| #278 `a639add7`, the fix round of #240 | rehearsed | integrate, in place of #240 | The business-path process test of #285 passes merged with #278 and fails merged with #240 | 46 of its tests need solver packages; they were not re-run in the solver environment here |
| #240 `4441bcb5` | rehearsed | consolidate into #278 | #278 is its fix round and carries the behaviour #285 needs | Close or supersede it when #278 lands; its owner's call |
| #285, business path in one body process | rehearsed | integrate after #278 | Passes merged with #278 | Not read line by line here |
| #214, self-repair incidents | rehearsed | preserve; not ready to integrate | Three tests of `tests/unit/test_greg_self_repair_incident.py` pass on its own tree and fail when it alone is merged onto `8d205324`. The line moved under it | Its owner rebases. One of the three (`test_beside_a_measured_failure_the_same_incident_is_still_repaired_once`) covers the same situation as this session's replay fix (section 2), so the two must be rehearsed together before either is taken |
| #233, browser session path | read (one function), rehearsed | integrate | It and #293 both changed `chromium()` in `greg/computer.py` for the same stale path | #293 now leaves that file to #233 |
| #283, #288 | rehearsed | integrate (owner's call) | No behavioural conflict among the tests they changed, in the Engine and Hands set | Not read here. A clean rehearsal is weak evidence |
| Genesis set #267, #276, #280, #281, #289, #292 | rehearsed | integrate as one set (owner's call) | No textual conflict; 83 changed tests pass merged | Not read here. This session deferred building Genesis's own method search because #289 and #292 hold those files |
| `origin/codex/business-path-process` `650de5e5` | read by a reader agent | extract | It already holds a real-process test of N3, N4 and N7 with a short-payment refusal and a restart. Building that again would duplicate it | Its relation to #285 was not established here. Whoever builds on the business path starts from it |

## 2. This session's units

| Component | State | Disposition | Reason and evidence | What is still owed |
|---|---|---|---|---|
| #291 `41fcc41f`, a detached capability cannot run or be receipted under another's identity | draft, all ten CI jobs passed | integrate | 51 tests in the two authority files; gates 23/23 and 5/5; composed with #290, #273, #278 | Intake |
| #294, a retained Gate receipt is read by its result | draft; fix round running | integrate after the fix round | Reviewed: behaviour held in every variant; 11 of 16 extra mutants survived, so coverage was thin | The fix round's result; a new CI run |
| The compensation-receipt reader in the revoked-device fix round (`_dispatched_compensation`, uncommitted, kept at `checkpoint/revoked-device-fix-wip-20261111`) | read | consolidate | It reads a Gate receipt three ways inline. #294 made `AuthorityOffice.outcome_of` the one reader. Two readers of one fact is the defect class #294 exists to remove | Built once in #294, covering a revoked approval and a detached or unavailable capability. The device branch then drops its copy |
| Revoked-device approvals `f35b7986` | built; reviewed | integrate after four fixes | Reviewed: the rule held under a 160-seed fuzz. Four findings, one a regression (a compensation completed before the revocation is asked again) | Restack on #294's new head; finish the fixes; 16 of 18 extra mutants survived |
| #293 `da2aff57`, browser.render uses a browser that can render | draft, all ten CI jobs passed; fix round running | integrate after the fix round | Reviewed: the claim holds on the production path (refused after 45.4 s on the line, ACHIEVED and VERIFIED on the branch). Five medium findings | The fix round's result |
| A four-line candidate-order change for the same browser defect (the reviewer's baseline) | run by the reviewer | preserve, as the comparison | It closes the same real-browser tests in this container. The check and its memory are shown to matter only with stand-in browsers | #293's fix round states the comparison where a reader of the code will see it |
| #296 `scripts/compose_rehearsal.py` | draft | integrate | `git merge-tree` and `scripts/branch_catalog.py` already say what merges cleanly. Neither runs anything. On sets it was not designed on it found three behavioural conflicts `merge-tree` does not report | One CI job failed at artifact upload after its tests ran; re-run requested |
| #297, a test read a clock at collection | draft | integrate | The same defect and the same fix as `58a2fad1` for its twin file, plus a guard test over the whole file | CI |
| #295, the founder's messages kept verbatim | draft | integrate | Intent record; no runtime change | This file and message D are added to it |
| Appraiser runs no detached sensor `bf8e4b9f` | built; diff read | integrate after review | A closure waiting for appraisal is recorded UNAVAILABLE when its capability is detached and appraised again on re-attach. Gate 26/26 by its builder | Independent review; a draft pull request |
| Corrected evidence stops earning credit `b01d319f` | built; diff read | integrate after review | `corrections.contained_receipts` existed on the line with no production reader. Settlement, procedure proposal and precedents now read it. Ablation by its builder: with the reader removed the credit returns | Independent review. Solver-dependent tests were skipped by its builder and must be run |
| Goal intake counted by independent source `1106795d` | built; diff read | preserve as an experiment; not ready to integrate | On its builder's 16 scenarios: 16 right wakes, 3 false alerts, 1 miss, against 10, 10 and 7 for the per-item rule. Three scenarios are worse than the baseline. The scenarios are the builder's own, not withheld | A withheld scenario set written by someone else; its Mechanism Card is renumbered MC-0004 |
| Two acceptance locks `1f4bf62d` (test only) | built; run | integrate after review | Lock C holds. Lock H found a real defect on the line: a completed write is dispatched again | Review running |
| Replay fix `e917a0db` | built; run; review running | integrate after review | Reproduced on `1f4bf62d`. A check a faulted capability could not read is no longer pursued, and a mission with only such checks looks again. With the first half alone the mission was stranded, which a probe showed before the second half was written | Review; rehearsal with #214 |
| S69.A6 map corrections `a69f5b72` | built | integrate after review | Five built units were recorded as missing; the seed gate catches 6 of 7, not 7 of 7 | Review |

## 3. Designs and findings that are not code on a branch

| Component | Disposition | Reason and evidence | What is still owed |
|---|---|---|---|
| Representation repair, design "one seam" (test the chosen reading's assumptions, run one relaxed reading under the thinking budget) | extract | Its pilot: an always-general rule may match it (49 to 30 over 360 pilot items, borderline), and its unique-suspect rule fires rarely. Its own strongest objection: the experiment plants the violations its tests were written to find | Use its seam (one call in the compile route) and its baselines. No build before a pre-registration with thresholds fixed first |
| Representation repair, design "intervention signatures" | extract | Its pilot: in one family a hand-built robust rule beat repair (4192 against 4906) | Keep its robust rule as the simple baseline the experiment must beat. The founder's minimum test asks for an improvement "against a simple fixed-representation baseline", and neither pilot shows one yet |
| The third design, both attacks and the synthesis | none | They did not run: the account's usage limit stopped them | Redo the adversary and the synthesis before any build |
| Business path, as read at `8d205324` | extract | Four paths exist and no code joins them: the N3 case mission, a fixture commerce mission, a sandbox loop and the signal and assessment missions. `greg rehearse --path` already runs offer to settlement and reports no money figure. Not found anywhere under `greg/`: refunds, costs in venture books, a reinvestment ask, a regulated-domain screen | The third reader and the synthesis did not run. No build there until they do |
| `acceptance/directive-sections.json` at `8d205324` | consolidate | Two entries lag the tree (WU-09 and MW-C cite no evidence that exists). The S69.A6 unit corrects five more | Fold into the map unit or a successor |
| The unwired mutation gates, `check_seed_mutants.py` among them | preserve | The seed gate catches 6 of 7 with its solver packages installed, so wiring it as is would turn CI red | The founder's decision S-3 |
| The recurring conflict in `.github/workflows/canonical-ci.yml` | consolidate | Every pull request that adds a mutation gate adds a step at the same place, so any two conflict | Proposed, not made: one step that runs every `scripts/ci/check_*_mutants.py` |
| The tracked root file `orker-evidence-replay.py with the fallback tier in place of the constant policies#` (27 bytes, from `9ee9b612`) | reject | Its whole content is `POLICIES = ("fallback",)`. The name is a fragment of a shell command. Nothing imports it | Removing it is the integrator's or the founder's. Not done here |
| Capability scout's three reproductions (evidence to credit, goal intake twice) | integrate | Each became a built unit above | None |

## 4. What this record does not cover

- Pull requests and branches this session did not open, read or rehearse. 181 pull requests were open on
  2026-11-11; this file names 21 of them.
- Organ repositories. None was changed today. The staffing distinction reproduced earlier in the day is on the
  evidence branch.
- Anything in Project conversations that is not in a repository.

## 5. Skills named in the directive that were not applied, and why

Counterpositioning and the venture half of the control-point analysis need a venture decision, and none was made.
The built-in browser tools need the desktop app attached, and it was not; the container's Chromium was used to
verify the browser route.
