# Section IX: the nine scenarios on one combined tree; section X recombinations

Directive of 2026-10-22, sections IX and X, re-issued 2026-10-30. Session `session_01KucyfnPRxLT4YY1UibJ3Ee`.

**Reality tier: SANDBOX.** Runs use in-process bodies with per-test founder keys, real files, the real installed
`pdftotext` and the real separate-process appraiser. Founder-device acceptance is not part of this run (founder
instruction of 2026-10-30: "Full machine NOT NESESARY"), and VEPMC stays 0. That acceptance is outstanding,
not dropped.

## The tree

No branch was pushed for a combined tree. Each one is a local merge, so no second integration trunk exists. Merge
commits carry local timestamps, so the tree, not the commit, is what a rebuild reproduces.

**The final tree, `0a3e410d`,** joins the four heads after the independent review's fixes:

```
git worktree add --detach combo 76ce1b40      # #229 (contains #228 a7990bc1 and #209); its later head adds only READMEs
git -C combo merge 3358d660                    # #230, the #201 licensing child (contains #201 9977ae26 and #196 b1950be2)
git -C combo merge ef6049dd                    # #231, acceptance report
git -C combo merge c301a84d                    # #232, organ-exchange verdict: one conflict, below
git -C combo rev-parse HEAD^{tree}             # 0a3e410df762b502ce357a5eab5643e87ae2b931
```

One merge conflicted: CI job 8's test list in `.github/workflows/canonical-ci.yml`. #209's line added
`test_combined_construction_outcome.py` and #232 added `test_greg_organ_exchange_verdict.py`; the resolution runs both.

**The first tree, `edfa37f7`,** joined the heads before the review: #229 `ca5dd7e5`, #230 `56e69410`, #231 `be3f0c31`
and #232 `99d79d47`. Each of those merges was clean. Its results are kept below beside the final tree's. An earlier run
of this README's scenarios, on a tree joined from #229 `a2ede855`, #196 `a6c29bbd` and #230 `22371155`, gave the same
51 passed as `edfa37f7`.

**Environment:**

- Ubuntu 24.04.5 LTS;
- Python 3.11.17 (`/home/user/venv311`'s own interpreter; see Limits for why not a venv that links its packages);
- poppler-utils 24.02.0-1ubuntu9.11 (dpkg; `pdftotext` 24.02.0);
- 4 cores;
- the organ checkouts at CI job 8's pins, DALEOBANKS `664ac98c` and WealthMachine `0e80582d`, with `UNIIMENTE_REQUIRE_ORGANS=1`.

## Scenarios

Command: `python -m pytest -p no:cacheprovider -rA <the tests below>`.

- **On the final tree `0a3e410d`: 62 passed, 0 failed, 0 skipped.** That is 17 scenario tests (the held-license test
  runs three licenses, and #229's review added the ten-minute cadence test) and the 45 model-license tests (#230's
  review fix added 10).
- On the first tree `edfa37f7`: 51 passed (16 scenario tests and 35 model-license tests).

| # | Section IX scenario | Test (file::name) | Lives on | Result on `0a3e410d` and `edfa37f7` |
|---|---|---|---|---|
| 1 | A founder-authorized PDF fact mission using an installed, legally qualified `pdftotext` | `tests/unit/test_greg_document_text.py::test_a_mission_checks_a_fact_inside_a_pdf_by_acquiring_installed_software` | #201 | passed: deficit opened, `pdftotext` qualified on 8 oracle cases, its DEP-5 license read (GPL-2+, cleared with obligations), attached under the signed read-only scope, mission ACHIEVED |
| 2 | A long non-PDF output whose required phrase appears after the retained preview | `tests/unit/test_greg_whole_output_judgment.py::test_a_required_phrase_past_16_kib_closes_the_mission_without_asking_and_is_verified`; `tests/unit/test_greg_text_query.py::test_a_large_log_is_proved_clean_and_the_appraiser_agrees` | #209; #229 | passed (both) |
| 3 | A long output in which a forbidden phrase appears after the preview | `tests/unit/test_greg_whole_output_judgment.py::test_a_forbidden_phrase_past_16_kib_is_decided_failing_not_asked`; `tests/unit/test_greg_text_query.py::test_a_fault_deep_in_a_large_log_keeps_the_mission_open` | #209; #229 | passed (both): decided failing, `NO_STRATEGY`, never a sensor question |
| 4 | An incomplete observation that is safely replayed after obtaining complete evidence | `tests/unit/test_greg_whole_output_judgment.py::test_an_incomplete_observation_is_kept_and_a_restarted_body_decides_the_next_one` | #209 | passed: the prefix-only reading is kept undecided; a restarted body decides the next, complete one |
| 5 | A held or unknown-license component that cannot be silently attached | `tests/integration/test_greg_section_ix_acquisition_scenarios.py::test_a_reader_whose_package_declares_a_held_license_waits_for_the_founder` (AGPL-3+, Llama-2-Community, CC-BY-NC-4.0); `tests/unit/test_greg_model_license.py` (model weights: 45 on `0a3e410d`, 35 on `edfa37f7`) | licensing child PR | passed: no attach, `deficit.awaiting_attach` names the license. The Llama-2 case fails on `083c91ea`. |
| 6 | A known compatible component that is reused without unnecessary reconstruction | `tests/integration/test_greg_section_ix_acquisition_scenarios.py::test_a_second_pdf_mission_reuses_the_reader_the_first_acquired` | licensing child PR | passed: no second deficit, qualification or attach; every reading by `acquired.document.text.pdftotext` |
| 7 | A failed capability that produces a truthful, resumable handoff rather than a false success | `tests/integration/test_greg_section_ix_text_scenarios.py`, four scenario 7 tests (three on `edfa37f7`) | #229 | passed: a broken sensor asks once and is read hourly, not on every tick; a fixed world closes the same signed mission without a founder answer, verified; a failing world becomes `NO_STRATEGY` |
| 8 | A mission whose evidence is technically valid but insufficient for the requested claim | `tests/integration/test_greg_section_ix_text_scenarios.py::test_evidence_that_is_valid_but_too_narrow_never_proves_an_absence` | #229 | passed: an authentic 64 KiB reading of a 2.4 MiB log never proves an absence |
| 9 | A mission involving a scanned PDF that is explicitly classified as unsupported or incomplete | `tests/unit/test_greg_document_text.py::test_a_scanned_page_never_proves_a_phrase_absent`, `::test_a_stamped_scan_never_proves_a_phrase_absent` | #201 | passed: a scanned or stamped page leaves absence undecided |

**Integration sweep.** These test files were run together on each tree:

- every mission-engine file;
- whole-output judgment, incomplete evidence and unmeasured-not-failed;
- text query and faithful text;
- every document, licensing and model-license file;
- the appraisal files;
- genesis restore, binary failure types, open-source genesis and the binary policy options;
- both section IX files;
- egress and confined egress;
- the acceptance report (#231) and its harness;
- the organ suites (#232): organs, the verdict tests, staffing figures, and the fifteen-step mission;
- packaging.

Result on the final tree `0a3e410d`: **2721 passed, 3 skipped, 1 xfailed** in 13 min 52 s. On the first tree `edfa37f7`:
2696 passed, 3 skipped, 1 xfailed in 13 min 45 s. On both, the skips are no runnable browser here (1) and Playwright not
installed (2). The xfail is `test_greg_binary_policy_options.py::test_under_p4c_a_license_hold_on_one_candidate_does_not_end_self_repair`,
a strict xfail that records a measured defect under policy P4c, which is not the active policy: a license hold on one
candidate ends self-repair instead of trying the next, cleared candidate. (An earlier version of this README called it
a recorded P0 hold; that was wrong.)
`tests/unit/test_greg_organ_exchange.py` (the memo path) needs `python-dotenv`, which this interpreter lacks, so it ran
with the kernel venv: 13 passed on each tree.

**Mutation gates.** On the final tree `0a3e410d`: `scripts/ci/check_whole_output_mutants.py`, 117 mutants, 0 survived
or stale; `scripts/ci/check_acceptance_mutants.py`, 8 mutants, 0 survived, stale or invalid. On the first tree
`edfa37f7`: 110 of 110 and 7 of 7.

**Defects the scenarios found.** Two were found and fixed before this run, both on #229, with three tests that fail
on the old engine:

- a directory where a log should be was read as an absent file;
- a sensor-failure block was never read again, even after the world was fixed.

**Defects an independent review found after this run.** A separate session reviewed #229, #230, #231 and #232
(`session_01KucyfkkShSidkrRCoz2UGK`). It is the same model family and was commissioned by this session, so it is an
independent process, not an independent operator. Two findings were blocking. Both are fixed with tests that fail on
the reviewed heads. The first tree, `edfa37f7`, preceded the fixes; the final tree, `0a3e410d`, includes them.

- **#229, the planner (`18c4cc4b`).** The planner read a phrase's polarity over the whole request, quoted phrase
  included. *mentions "connection not established"* drafted a check that the file never mentions it, and the
  apostrophe in "doesn't" opened a quote. Polarity is now read outside the quotes, and unclear wording becomes a
  question. 10 of 11 new tests fail before the fix.
- **#229, the sensing watch (`76ce1b40`).** The review asked which third test fails without the watch. On the
  engine before `0319d97b` all three scenario 7 tests fail; the hourly test fails because the broken path is never
  read again. A mutant that removes only the watch's own hourly schedule, however, survived all three: the hourly test
  ticks at the cadence, so it cannot tell a re-read at the cadence from a re-read on every tick. A fourth test ticks
  every ten minutes for six hours. With the schedule removed the broken path is read 36 times; with it, 6. On
  `76ce1b40` the whole-output gate catches 117 of 117, the planner and cadence mutants included.
- **#230, licensing (`40520bcb`).** Terms written into a copyright notice cleared a model's weights. A copyright
  notice beside Apache or MIT terms now holds only a notice. 5 new tests fail before the fix, and the metabolism group
  catches 105 of 105.

The two non-blocking findings changed code too:

- **#231 (`ef6049dd`):** a process that started after the heartbeat was written no longer counts as its writer.
- **#232 (`c301a84d`):** CI job 8 now runs the verdict test where the organs are required.

## The loop each scenario walks (section IX, steps 1 to 13)

| Step | Evidence | State |
| --- | --- | --- |
| 1. Founder intent in the persistent intent ledger | Missions are founder-signed. The 2026-10-30 correction is proposed for the ledger in the #96 handoff; the shared ledger file is not edited here. | PARTIAL: test missions do not cite ledger entries |
| 2. Compiled into an authorized mission | the planner route `template:file-search` (#229); signed MISSION envelopes | MET |
| 3. The mission names the required fact | checks with predicates and fields | MET |
| 4. Genesis discovers or forms the capability | scenario 1 (deficit → installed `pdftotext`) | MET |
| 5. Legal, technical and operational qualification recorded separately | license assessment, oracle report and ceilings on the card; scenarios 1 and 5 | MET |
| 6. Authorization checked before attach and execution | scenario 5; the signed read-only scope | MET |
| 7. Execution under bounded controls | memory, output and time ceilings; `fs.search` byte and time limits | MET |
| 8. Evidence complete, authenticated and sufficient | whole outputs kept, `read_sha256`; scenarios 4 and 8 | MET |
| 9. Independent appraisal | the separate-process appraiser in scenarios 2, 3 and 7 | MET (separate process, same code base: not an independent operator) |
| 10. Closes only when every condition is proven | scenarios 3, 4, 8 and 9 | MET |
| 11. The outcome becomes competence memory | routing learns from appraised outcomes of acting capabilities | PARTIAL: sensors and acquired sensors are not in routing's competence memory (X5) |
| 12. Future missions reuse without bypassing controls | scenario 6 | MET |
| 13. Failures, uncertainty and founder decisions stay visible | scenarios 5 and 7: the reason is named on every ask | MET |

## Section X: recombinations, judged by what they produce

A recombination counts here only when it produces a useful, repeatable improvement that someone else can check. Each row names its sources, what it does that they did not, why the simpler route falls short, its authority boundary, evidence contract, failure behaviour, acceptance test and owner. Status is one of BUILT (on a branch with tests), INTEGRATION (existing parts joined, nothing new invented) or PROPOSED (not built).

### X1. Document extraction + bounded streaming predicates + mission evidence — BUILT for files (#229); PDF streaming offered to #201's owner

- **Sources:** #201's `document.text` phrase question (whole extraction in memory); item 1's text form and faithful decoding (#228); the incomplete-observation contract (`complete`/`decided`, #201 and J8); #209's judge.
- **Residual problem:** a question about a source larger than a receipt keeps (1 MiB) asked the founder; #201 buffered `pdftotext` output to 4 MiB and refused past it.
- **New capability:** a verdict about a large source (up to 4 GiB and 60 s per query by default, lowered per mission) that a receipt can hold whole (a few hundred bytes), stating its own coverage: bytes read, their digest, encoding, `complete`, `stopped`. A stopped reading proves only what it found.
- **Why simpler fails:** raising `fs.read`'s ceiling grows memory with the file and the receipt still cuts at 16 KiB. `grep`/`rg` give no normalization, no faithful decoding and no coverage statement. Keeping larger artifacts in the store moves bytes, not proof.
- **Authority boundary:** read-only, inside the permitted roots; no new capability class.
- **Evidence contract:** `read_sha256` is the digest of exactly the bytes read (checked by scenario 8); the appraiser re-reads the file.
- **Failure and rollback:** a limit stops the reading and says so; an unreadable byte leaves every answer open with the reason. Revert the commit; nothing persists.
- **Acceptance test:** `tests/unit/test_greg_text_query.py` (30) and `tests/integration/test_greg_section_ix_text_scenarios.py` (4), 34 collected on `edfa37f7`; 20 mutants in the whole-output gate, which caught 110 of 110 on #229 `ca5dd7e5` and again on `edfa37f7`, and 117 of 117 on `76ce1b40`. Streaming `pdftotext` stdout through the same `Query` changes `greg/documents.py`, which is #201's owner's; it is offered there, not built here.
- **Owner and destination:** this session; #229 into #228, then the #196 integrator.

### X2. Source provenance + legal assessment + operational confinement — BUILT (#201, its fix lanes, and the model-weight gate)

- **Sources:** #201's acquisition of the installed `pdftotext` (dpkg provenance, DEP-5 copyright file), the licensing lane's one expression tree (SPDX and DEP-5, `AND`/`OR`/`WITH`), #201's memory and output ceilings for acquired binaries.
- **Residual problem:** an acquired binary's licence was read by a parser that let an unknown name mask a restrictive one, and a held licence could be attached.
- **New capability:** an acquired tool is attached only when its recorded provenance, its licence verdict and its confinement all hold at attach time, and each is shown separately to the founder. Extended to model weights: an installed Ollama model's own license layers are read from its content-addressed store, classified by their terms (not their title), and bound to the weight digests, so `licensing.ollama_model` holds a model under Llama, Gemma, OpenRAIL or research-only terms, and a changed weight changes the qualification. It is not yet wired into the model route (`OllamaRoute`, the models lane's), so a configured model still runs without consulting it, and it was tested against Ollama's recorded store format, not a live store.
- **Why simpler fails:** `packaging.licenses` canonicalizes SPDX but does not read DEP-5 stanzas or classify restrictions; a single verdict string hides which fact failed.
- **Authority boundary:** a licence verdict never attaches anything; unknown and restrictive declarations go to the founder.
- **Evidence contract:** the qualification report states the ceilings applied; the licence assessment lists the terms and the files each covers.
- **Failure and rollback:** a changed licence fact after the verdict refuses the attach (GATE-3, gates lane). Detach restores the prior state.
- **Second-order evidence (2026-10-30):** a text-form split remains between this source group and the judge. `document.text` folds NFKC while the judge compares NFC, so a ligature phrase reads `found: True` in the receipt and absent to a `contains` check on the same receipt. It is measured and offered on #230 (comment 6520537954, item 3); a draft judge change honouring a receipt's declared phrase rules is preserved on `claude/oss-201-fix-documents`.
- **Acceptance test:** the licensing lane's tests (1,750 oracle cases plus named cases, each failing on `a1d2abfb`); `tests/unit/test_greg_model_license.py` (35, all failing on `083c91ea`); section IX scenario 5 on the mission path (the Llama-2 case fails on `083c91ea`: the binary attached silently); measured on 121 installed license texts with no false clear.
- **Owner and destination:** `greg/licensing.py` is this session's under the #201 split; offered to #201's owner as a child PR. Wiring `ollama_model` into `OllamaRoute` is the models lane's re-seal (`greg/models.py` is pinned by `freeze-v12`).

### X3. Failure appraisal + mutation testing + institutional memory — INTEGRATION

- **Sources:** the separate-process appraiser (#178 lineage), the whole-output mutation gate (#209), evidence READMEs that keep negative results.
- **What it does:** every safeguard added on #209/#228/#229 has a mutant that removes it and a named test that must fail; the gate runs in CI on every head, so a later change that silently removes a safeguard turns CI red.
- **Honest label:** this joins existing parts; it invents nothing. Its measured value this session:
  - two mutants survived and exposed weak tests (item 1's BOM mutant; item 2's appraiser subtraction), both fixed;
  - on #230, CI job 6 caught a survivor ("Elastic-2.0 in free text is not read") that a partial local re-run had missed. A later fix (`059c734c`) had made the rider's tests redundant without anyone noticing. Fixed in `376889d0`; the whole group then read 101 of 101 caught. The lesson is procedural: after a fix, re-run the whole group, not only the mutants the fix names.
- **Acceptance test:** `scripts/ci/check_whole_output_mutants.py`, 110 mutants on #229's head `ca5dd7e5` and on `edfa37f7`, and 117 on `76ce1b40`, all killed, each by its named test in a separate copy; `scripts/ci/check_acceptance_mutants.py` (#231), 7 of 7 on `be3f0c31` and 8 of 8 on `ef6049dd`; the metabolism group of `scripts/ci/check_cortex_mutants.py` on #230, 101 of 101, then 105 of 105 on `40520bcb`.

### X4. Mission replay + evidence invalidation + safe re-execution — BUILT on #229 (sensing watch); the rest INTEGRATION

- **Sources:** #209's reading of a cut observation from the artifact store after a restart; the appraiser's re-observation ("world no longer matches"); the NO_STRATEGY block's watch, which re-reads at the mission's cadence and withdraws a moot ask (`_watch_while_blocked`); the SENSOR_FAILURE block.
- **Residual problem (measured):** after the third failed round GREG stopped reading and waited for the founder, even once the world was fixed: 60 ticks, ten simulated hours, no further reading.
- **New capability:** a SENSOR_FAILURE block is watched like a NO_STRATEGY block, with one mutation: it is lifted when the sensor reads again, whatever the reading says. After its one question, a fixed world closes the same signed mission with no founder answer; a sensor that reads again on a failing world turns the question into the right one (NO_STRATEGY); a sensor that stays broken keeps its one question and is read only at the mission's cadence.
- **Why simpler fails:** re-reading every tick spends reads on a broken sensor; waiting only on the founder keeps a transient failure as a question; lifting the block only when the check passes would leave a readable-but-failing world asked about as a broken sensor.
- **Authority boundary:** the re-read is the mission's own signed, read-only sensor; the withdrawal is a body event and is never the founder's answer; a recurrence opens a new ask (a new epoch), never revives the withdrawn one.
- **Evidence contract:** `decision.withdrawn` records why and the evidence of the re-read; earlier failed observations stay on the record unchanged.
- **Failure and rollback:** revert the commit; blocks return to waiting on the founder.
- **Acceptance test:** `tests/integration/test_greg_section_ix_text_scenarios.py`, four scenario 7 tests. The first three fail without the change (the hourly test too: zero re-reads). The fourth, added after the review of #229, ticks every ten minutes: with the watch's own schedule removed the broken path is read 36 times in six hours, against 6. Gate mutants remove the watch, widen what counts as unread, and remove the schedule.
- **Owner and destination:** this session; #229, then the #196 integrator, who owns the engine. Proposed to them on #96 with the commit.

### X5. Founder intent compilation + capability discovery + competence memory — PARTIAL, gap recorded

- **What runs:** the planner turns "never mentions" into an `fs.search` mission (#229); Genesis discovers and attaches `pdftotext` for `document.text` (#201); routing learns from appraised outcomes of acting capabilities (`greg/routing.py`).
- **Gap (Gate E):** sensors and acquired sensor capabilities are not in routing's competence memory, so a reader that keeps failing is not demoted by its record. Recorded, not built.

### X6. Two governed Bridge A implementations, one binding rule — INTEGRATION (#232)

- **Sources:** the memo path's `binding_verdict` (`greg/organ_exchange.py`, a score may not outrun unevidenced canonical fields); the mission path's `organ.exchange` receipt (`greg/organs.py`); the Kernel adapters that map DALEOBANKS's wire packet to canonical fields.
- **Residual problem (measured):** on the research lane's 27 mission-path exchanges, 6 reported WealthMachine's "go" where the memo path's own rule caps to `needs_more_evidence`.
- **What it does:** the mission-path receipt states the memo path's verdict beside the engine's; unreadable wire messages leave every field unevidenced.
- **Honest label:** one existing rule applied in a second place; nothing invented. Its value is that the two paths cannot tell the founder different things.
- **Acceptance test:** `tests/unit/test_greg_organ_exchange_verdict.py`, 5 failing on `b1950be2`, passing on `99d79d47`; 3 mutants caught; the live test on the CI job-8 organ pins.

### X7. Founder-tier signature + heartbeat freshness + the acceptance report — INTEGRATION (#231)

- **Sources:** `greg.metrics.founder_tier` (the rule that gates N1 in `greg path`); the console's 180-second heartbeat freshness; `greg acceptance`'s reality label and `supervised_runtime` property.
- **What it does:** the report the founder sends with their judgment labels a run FOUNDER-DEVICE only at the founder tier, and calls a body running only when a live process wrote its heartbeat within three minutes.
- **Honest label:** existing rules applied where the report had its own weaker reading. It prepares the founder-device run, which the founder wrote on 2026-10-30 is not needed for this build; it is outstanding, not dropped.
- **Acceptance test:** `tests/unit/test_greg_acceptance_reality.py`, 9 failing on `b1950be2` (8 behavioural), and 2 more on `be3f0c31` after the review's reused-pid finding; `scripts/ci/check_acceptance_mutants.py`, 8 of 8 on `ef6049dd`.

## Limits

- One container, SANDBOX tier, per-test keys; no founder device.
- The combined trees are local. Each component PR carries its own CI. No CI ran on `edfa37f7` or `0a3e410d` itself.
- **Reproducing the mission-path tests needs a self-contained interpreter.** GREG re-runs a worker's tests inside its
  bubblewrap envelope, which shows the running interpreter's own prefix and nothing linked from outside it. A venv whose
  packages come through a `.pth` file pointing outside its prefix reads `No module named pytest` inside the envelope, and
  the fifteen-step and one-machine tests then fail on any revision. This is the host, not the code; CI's interpreter is
  self-contained.
- Real Llama, Gemma and Qwen license texts and a live Ollama store could not be reached (network policy).
- Scenario 1's license reading depends on dpkg. On a body without it, the card says the license was not readable,
  as #201 designed.
