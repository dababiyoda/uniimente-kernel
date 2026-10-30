# Directive completion contract (MW-B), 2026-10-30

The founder wrote on 2026-10-30: "That is done when we completely build the prompt"
(`INTENT-20261030-BUILD-BEFORE-DEVICE-RUN`). The prompt is the 77-section directive in
`docs/intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md`. Before this change nothing computed
that sentence, so the path's node depth could be read as "the prompt is built" while whole sections stayed open.

Base: `feb531d2` (the branch that records the directive and the correction). Round 1: `4a4facc6`..`b909b516`. Round 2
(two reviews, 18 findings): `74214dd8`, `5d10433e` and the commit that records this file. Reality level: UNIT-TESTED (the
checker, its tests and its mutant gate), with the static map computed from cited evidence and LOCAL runs of the nodes
the met asks and the principles rest on (below). Nothing here is founder-used, live or externally verified. It
grants, attaches and activates nothing.

## What changed

| File | What |
| --- | --- |
| `acceptance/directive-sections.json` | One record per section 1-77: the source's exact heading, the section's testable asks (paraphrase, verbatim excerpt, the listed lines it answers, owner paths, evidence, required tier, computed tier, coverage, blocker with its record), optional `not_asks`, and a units table of gap-map units with their dependencies. |
| `acceptance/directive-asks.pin.json` (+ schema) | Round 2. Every ask id issued, with the blocker class it may claim while open besides BUILDABLE_NOT_BUILT. |
| `acceptance/directive-sections.schema.json` | JSON Schema 2020-12 for the map. |
| `acceptance/directive.py` | Parses the source, computes each ask's tier and status, the section statuses and the two verdicts, and validates the map and its pin. Reuses `acceptance/__init__.py` (report, node resolution, real-process reading); no parallel framework. |
| `acceptance/__main__.py` | `check` also validates the map and prints its counts; `directive` command (`--collect`, `--outcomes`, `--against`, `--out`). |
| `acceptance/README.md` | The rules, and what is not checked mechanically. |
| `tests/unit/test_directive_sections.py` | 35 tests: the map is sound, and each failure class on a broken copy. |
| `tests/unit/test_greg_path_cli.py` | Round 2. `greg path` reports all five fields section 15 names, with and without a body. |
| `scripts/ci/check_directive_sections_mutants.py` | 85 mutants of `acceptance/directive.py` and `acceptance/__main__.py`. |
| `.github/workflows/directive-completion.yml` | Read-only token; installs dev, cognition and Playwright; runs `directive --collect` (and `--against` the PR base) and the mutant gate. |
| `local-run-met-asks.json` | Round 1's LOCAL run, per ask. `local-run-round2.json`: round 2's supplementary run and the merged counts. |

Rules (full text in `acceptance/README.md`):
- An ask's tier is the least-verified of the requirements (capped by Mission L's trace when it cites Mission L),
  contract functions and pytest nodes it cites, never declared above it. Tests reach at most BODY_VERIFIED.
- An ask is met only at its required tier and covered. A section is DONE only when every ask is met and every listed
  line (each bullet, and each line starting "Do not" or "Never") is answered by an ask or set aside with a reason.
- "Completely built" is false while any ask is BUILDABLE_NOT_BUILT, an unguarded PRINCIPLE (or one whose guard fell
  short in a run), open with no blocker named, or while any listed line is unaccounted for. "Every section DONE" also
  needs founder and external records.
- The asks are pinned: an ask is retired, never deleted, and an open ask's blocker moves only to BUILDABLE_NOT_BUILT.
  `directive --against <base>` refuses a pin edited in the same change.

## Result on this tree (static ceilings: what the cited evidence could establish if every cited test passed)

`python -m acceptance check` prints:

    directive: 77 sections (DONE 1, PARTIAL 53, OPEN 23); 73/272 asks met at the static ceiling (no test ran);
    134 open asks building can still close; 655 listed lines no ask answers yet; prompt completely built: NO;
    every section done: NO

| Sections | Count |
| --- | --- |
| DONE | 1 (13) |
| PARTIAL | 53 |
| OPEN | 23 (11, 18, 21, 22, 26, 27, 32, 33, 35, 36, 37, 38, 39, 42, 43, 51, 52, 55, 59, 65, 70, 73, 74) |

| Asks | Count |
| --- | --- |
| total (pinned) | 272 |
| met at the static ceiling | 73 |
| open, BUILDABLE_NOT_BUILT | 134 |
| open, FOUNDER_ONLY | 32 |
| open, EXTERNAL | 20 |
| open, PRINCIPLE guarded by named tests | 13 |
| open, PRINCIPLE UNGUARDED | 0 |
| listed lines no ask answers yet (in 55 sections) | 655 |

Round 1 reported DONE 3 (13, 15, 69). Sections 15 and 69 were DONE on too few asks (findings MWB-2, F2): section 69
had one ask for twelve bullets and four prohibitions. Both now carry asks for every listed line and compute PARTIAL.
Section 13 stays DONE with all 13 of its distinct listed lines answered.

Met in a run, not only statically: see the LOCAL runs row under "Commands and results" (58 of the 64 own-node met
asks). Six statically met asks rest on tests that skipped on every host this map was checked on (S28.A2, S60.A1 and S72.A1 need Playwright with Chromium; S31.A1 and S50.A2 bubblewrap;
S45.A1 a DALEOBANKS checkout); each carries a note saying so.

A unit built on another branch does not count here until it is in this tree and the map cites its tests.

## BUILDABLE_NOT_BUILT asks in dependency order

Printed by `python -m acceptance directive`. Each unit comes after its prerequisites; a prerequisite that no ask names
itself (MW-A, MU-A, S38-A) is listed with "prerequisite; no ask of its own". Units come from the session's gap map
against #196 head `4ec00605` and its review (MU-*, MW-*); ids such as `S14-A` label residuals the gap map named
without an id, and S15-A and S69-A come from this map's round-2 review.

| # | Unit | What | Depends on | Asks |
| --- | --- | --- | --- | --- |
| 1 | MW-A | Fail-closed build instrument: a skipped rehearsal fails under GREG_REQUIRE_SUPERVISOR=1, and a rehearsal body refuses FOUNDER_TIER | - | prerequisite; no ask of its own |
| 2 | MW-C | Canonical-owner guard: a function-to-canonical-module registry whose test fails when a new module re-implements a registered function | - | S52.A1, S69.A3, S76.A2 |
| 3 | MU-A | Per-node path-predicate mutation gate: a weakening mutant per predicate (N4, N6, N7 now) | - | prerequisite; no ask of its own |
| 4 | WU-01 | Build frontier beside the acceptance frontier on `greg path` (the 2026-10-30 correction as a route placement) | - | S12.A3, S68.A4, S69.A5 |
| 5 | WU-02 | One-command whole-path rehearsal `greg rehearse --path`: every built node reached in sequence on one throwaway ledger | WU-01, MW-A, MU-A | S61.A1, S71.A1, S77.A2 |
| 6 | WU-05 | Compute bottleneck measured, quantified and verified: optimization first, benchmark before and after | - | S48.A2, S71.A2 |
| 7 | MU-C | Credential handles: audited, target-bound, expiring, with a host-native (libsecret) backend | - | S33.A1, S33.A2, S33.A3 |
| 8 | WU-06 | Enrolled nodes that work: NODE_REVOKE, node-signed receipts admitted only inside the node's cone, an N8 predicate | WU-01, WU-05, MU-C | S48.A3, S49.A2, S58.A4, S68.A3, S72.A2 |
| 9 | WU-07 | Case after-life: refunds, chargebacks and retention or termination netted out of verified revenue | - | S43.A2, S46.A1 |
| 10 | WU-08 | Business whole-loop as section 58 defines it, with an N3 whole-loop predicate | WU-01, WU-07 | S43.A1, S58.A1 |
| 11 | WU-09 | Earned autonomy per (capability, action class, target pattern, budget band) with immediate regression | MW-C | S59.A1 |
| 12 | WU-10 | Browser hands that run: Playwright install and CI, a method-level consequence gate, the action program protected from $from_action | - | S31.A3, S34.A3 |
| 13 | WU-11 | Genesis ATTACK stage before registration, and a per-function failure corpus every later candidate must pass | - | S17.A1, S22.A2, S35.A3 |
| 14 | WU-12 | Night shift closes on a running body (signed TRIBUNAL_REVIEWED); critiques carry executable fail-before/pass-after checks | MW-C | S30.A2, S30.A3 |
| 15 | WU-13 | Cathedral detector and reality-ladder inflation guard computed from git, the ledger and machine-readable claims | WU-01, MW-C | S1.A2, S55.A1, S56.A1, S67.A4, S69.A9 |
| 16 | WU-14 | Consistent backups from a running body on a founder-signed cadence, each proven by a restore drill | - | S47.A2 |
| 17 | MU-B | Capability readiness ladder `greg capabilities --readiness` (KNOWN .. VERIFIED), values never shown | - | S26.A3, S32.A1, S32.A2 |
| 18 | MU-D | Evidence-plane bypass detector: every effectful call site in greg/ and foundry/systems on a justified allowlist | - | S37.A2 |
| 19 | MU-E | Typed blocker projection: every blocker with why, reconsider_when, required_evidence, required_authority, next_move | - | S29.A3 |
| 20 | MU-F | Machine-readable intent and horizon ledger with a continuity guard (sections 8, 11, 54) | - | S6.A3, S8.A2, S11.A1, S54.A2 |
| 21 | MU-H | Canonical-owner records for the duplicated functions, with a live-import guard against retired alternates | MW-C | S52.A2, S66.A2 |
| 22 | S5-A | One disposition index: every material path has exactly one current section-5 disposition | - | S5.A1 |
| 23 | S3-A | Repository-wide AST check for the one authority path (replaces the filename-only and top-level-greg-only guards) | S5-A | S3.A1, S23.A2, S51.A1, S67.A1 |
| 24 | S7-A | Guard the re-issued directive's section-7 capability wording on the path | - | S7.A2 |
| 25 | S11-B | Founder words are append-only: verbatim sources and recorded quotations can never be edited or deleted | - | S11.A2 |
| 26 | S14-A | Succession edges on the path: each node names the durable asset it leaves and the later node it makes easier | - | S14.A3 |
| 27 | S19-A | Unacceptable outcomes and constraints become checked guarantees (ENFORCED, CONTRADICTED or ADVISORY) | - | S19.A2 |
| 28 | S20-A | Executable emergence gate: a recombination must beat its own stated baseline on frozen cases or is refused as integration | - | S20.A2 |
| 29 | S21-A | Acquire before building: qualify project-history sources and installed tools against the frozen contract before any builder | WU-11 | S18.A2, S21.A1, S21.A2 |
| 30 | S22-B | Post-outcome disposition review RETAIN / REPAIR / REGRESS / REMOVE for every formed capability, proposed, never self-applied | - | S22.A4 |
| 31 | S24-A | Embodiment-change detection and re-designation after a body move | - | S24.A4 |
| 32 | S26-A | Download-and-verify install bundle (PACKAGED tier) | - | S26.A1 |
| 33 | S26-B | Setup journey: the eleven install-to-run steps as one founder-mode checklist | S26-A | S26.A2 |
| 34 | S27-A | Converse with GREG: questions answered from evidence on console, CLI and phone | MU-E | S27.A2 |
| 35 | S28-A | Founder alerts: one ledger-derived alert policy delivered to the phone and the local desktop | - | S28.A4 |
| 36 | S28-C | Voice on the remote interface through on-device platform speech | S27-A | S28.A6 |
| 37 | S29-A | Idle-discipline guard: no autonomous busywork (the second half of the gap map's section-29 residual) | - | S29.A4 |
| 38 | D31-C | browser.act: founder-approved consequential browser steps through the Gate | WU-10, MU-C | S31.A4 |
| 39 | D31-D | Linux desktop OS-automation route (window list, keyboard and pointer, screenshot, accessibility read) | - | S31.A5 |
| 40 | D34-A | Plane-separation conformance test across every ingress channel | WU-10 | S34.A2 |
| 41 | D35-A | Dependency inspection and static checks on worker patches before acceptance | - | S35.A2 |
| 42 | D36-A | Asymmetrically signed ledger checkpoints with a founder-device countersignature | - | S36.A3 |
| 43 | S38-A | Non-blocking worker dispatch: a long worker must not freeze every other mission | - | prerequisite; no ask of its own |
| 44 | WU-03 | `worker.team`: one signed action fields a role-scoped temporary worker organization in parallel under one grant | MW-C, S38-A | S23.A3, S38.A2, S39.A1 |
| 45 | WU-04 | Organization-vs-simpler gate with an N5 ledger predicate, and a receipted AI-worker contribution in the N6 closure | WU-01, WU-03 | S39.A2, S58.A3, S68.A2, S72.A3 |
| 46 | MU-G | Founder final-acceptance procedure for every predicated node, one driver for rehearsal and device | WU-02, WU-04, WU-06, WU-08 | S57.A4 |
| 47 | S40-A | SOP-first planning: a ratified procedure answers the founder's words with zero model calls | - | S40.A4 |
| 48 | S40-B | Complete the section-40 meters in the SOP trend: worker calls, failure rate, recovery burden, human minutes | - | S40.A3 |
| 49 | S40-C | From a compounding SOP to a callable capability, and to an organ proposal | S40-A | S17.A2, S38.A3, S40.A2 |
| 50 | S41-A | Multi-person work fabric: roster, role routing, working hours, cross-person dependencies, overdue-blocker detection | - | S41.A2 |
| 51 | S42-A | Community claims become institutional learning only through a tested settlement | - | S42.A2 |
| 52 | S42-B | Goal Gravity counts community intake by independent sources, not by volume | - | S42.A1 |
| 53 | S43-A | Regulated-domain screen that routes consequential deliverables to a licensed professional before closure | - | S43.A3, S45.A5 |
| 54 | S45-A | Correction watch: re-verify delivered informational outputs and record append-only corrections | - | S43.A4, S45.A3 |
| 55 | S45-B | Separate fact from labelled interpretation, and let source quality decide acceptance, in the restatement contract | - | S45.A2 |
| 56 | S44-A | Venture objective vector with trust floors: no compounding claim on revenue that trust did not hold | WU-07, S45-A | S44.A2 |
| 57 | S46-A | Surplus-to-capability-investment asks with a pre-declared effect and a measured RETAIN/REGRESS | WU-07 | S46.A2 |
| 58 | S47-B | Black-start recovery core: read-only obligation inventory and safe shutdown when GREG's runtime cannot start | - | S47.A4 |
| 59 | S50-A | Qualify a newly selected model route before mission use (MODEL_ROUTE_SET skips qualification) | - | S50.A3 |
| 60 | S51-A | Organ consequence seams verify a Kernel gate decision instead of an organ-local approximation | - | S51.A2 |
| 61 | S53-A | Place every currently open PR from live state, not a hard-coded list | - | S53.A1, S53.A2, S69.A4 |
| 62 | S60-A | Bottleneck attribution across missions, with the asks 'a human is the bottleneck' and a build-versus-buy estimate | WU-09 | S60.A2 |
| 63 | S62-A | Recurring-bottleneck detector and organizational-form comparison ask (cheapest sufficient form first) | S60-A | S62.A1 |
| 64 | S63-A | Per-venture wedge-ladder position and participant-friction trend, derived from the ledger | - | S63.A2 |
| 65 | S65-A | Validate every deliberation record against the two-pass protocol | - | S65.A1 |
| 66 | S70-A | Answer the required question from evidence: capability delta between two commits | WU-01 | S70.A1 |
| 67 | S73-A | Compute the 40-item final report from evidence, marking prose-only items | WU-01, WU-13 | S73.A1 |
| 68 | S15-A | Admit off-node work only for one of section 15's five reasons, checked on every placement | WU-01 | S15.A3 |
| 69 | S69-A | Every mutant gate in scripts/ci runs in a workflow, and every safeguard names the test that fails without it | - | S69.A6 |
| 70 | - | No gap-map unit. Each ask's blocker states the residual; most name a missions.json requirement that is partial at its tier, or its open gap | - | S1.A3, S2.A1, S4.A1, S4.A2, S4.A4, S10.A1, S17.A4, S18.A1, S22.A1, S22.A3, S27.A1, S29.A2, S35.A1, S35.A4, S36.A2, S36.A5, S37.A1, S38.A1, S45.A4, S47.A1, S50.A1, S50.A4, S67.A2 |

## Round 2: review findings and dispositions

| Finding | Disposition | Regression test (fails on `b909b516`) |
| --- | --- | --- |
| MWB-1 asks could be deleted unseen | Fixed: pin file, retirement kept in the map, `--against` ratchet | `test_a_deleted_or_relabelled_ask_is_refused`, `test_the_pin_ratchets_against_a_base`, `test_an_ask_is_retired_never_deleted` |
| MWB-2 / F2 section 69 (and 15) DONE on too few asks | Fixed: listed-line accounting gates DONE and "completely built"; asks added for sections 13, 15, 69 | `test_a_done_section_answers_every_listed_line` |
| MWB-3 helper node masked by a wholesale-cited file | Fixed: every distinct node and guard collected; a non-test name refused statically | `test_a_helper_inside_a_wholesale_cited_file_is_not_evidence` |
| MWB-4 failed guard still guarded | Fixed: in a run, a guard that fell short leaves the principle unguarded | `test_a_guard_that_fell_short_in_a_run_leaves_its_principle_unguarded` |
| MWB-5 Mission L citation not capped by its trace | Fixed: trace links cap tier and coverage. S2.A1, S2.A4, S27.A1, S36.A5, S37.A1, S71.A1 now compute UNIT_VERIFIED (all were already open) | `test_a_mission_l_requirement_is_capped_by_its_trace` |
| MWB-6 / F4 surviving mutants | Fixed: a test per safeguard; the gate grew from 29 to 85 mutants, CLI included | `test_the_map_keeps_its_own_structure`, `test_a_run_reopened_ask_with_no_blocker_counts_against_the_build`, `test_the_cli_collects_every_cited_node_and_ratchets_the_pin`, and others |
| MWB-7 blocker relabelling closed the verdict | Fixed: pinned classes move only to BUILDABLE_NOT_BUILT; founder and external blockers on test-reachable tiers cite a record (8 asks now do); guards must be the ask's own evidence | `test_a_founder_or_external_blocker_a_test_could_reach_cites_its_record`, `test_a_principle_guard_is_resolved_and_among_its_evidence` |
| MWB-8 wrong source crashed | Fixed: the source is pinned; an unfenced or empty source is reported | `test_the_source_is_the_directive_and_a_wrong_one_is_reported_not_raised` |
| MWB-9 prerequisites dropped from the order | Fixed: prerequisites listed first, marked "no ask of its own" | `test_prerequisites_are_listed_before_the_units_that_need_them` |
| MWB-10 workflow without permissions | Fixed: `permissions: contents: read` (effective default scope was not checked) | none (workflow file) |
| F1 workflow fails on a clean dev install | Reproduced (dev-only venv: 6 files collect nothing, exit 2). Fixed: the workflow installs cognition and Playwright; a clean venv with exactly that install collects all 129 nodes | none (workflow file; verified by the clean-venv run below) |
| F3 three met asks never ran anywhere | Fixed as far as this host allows: the summary labels static counts as ceilings, the run counts are reported apart, and the six asks met only statically carry a note. CI collects but does not run them | `test_the_cli_prints_counts_and_refuses_an_unsound_map` (the label assertion was added after the fail-before run; the old summary line has no label) |
| F5 "103 nodes" | Fixed: `--collect` prints the count it checked (now 129 distinct nodes and guards) | `test_the_cli_collects_every_cited_node_and_ratchets_the_pin` |
| F6 orphan units MU-G, S38-A | Fixed: MU-G closes the new S57.A4; S38-A is a prerequisite of WU-03; an orphan or a closed-but-named unit fails the check | `test_every_unit_is_attached_to_an_open_ask_or_closed` |
| F7 wrong skip reason | Fixed: S31.A3's reason now says no Chromium here, no Playwright in CI. Commit `bd5794d0`'s message is left as written | none (text) |
| F9 S15.A1 citation did not cover its fields | Fixed: `tests/unit/test_greg_path_cli.py` checks all five fields through `greg path`, with and without a body; S15.A1 cites it. The behaviour already existed, so these two tests pass on `b909b516` too | `test_greg_path_cli.py` (evidence, not a code fix) |

## Commands and results

| Command | Result |
| --- | --- |
| Round 1 fail-before: `pytest tests/unit/test_directive_sections.py` (19 tests) in a detached worktree of `feb531d2` | 1 error at collection (`cannot import name 'directive' from 'acceptance'`) |
| Round 1 fail-before: on `feb531d2`, a map claiming all 77 sections DONE, section 40 removed, section 13's heading changed, then `python -m acceptance check` | exit 0, "sound" |
| Round 2 fail-before: the round-2 `test_directive_sections.py` and `test_greg_path_cli.py` in a detached worktree of `b909b516` | 15 failed, 22 passed. The 15 are the new failure classes. Of the 22, 2 are the `greg path` evidence tests (behaviour existed), 2 add coverage for safeguards that existed (structure, contract cap: caught by mutants instead), 18 are round 1's |
| Reviewer probes against this head | S16.A3 deletion refused (`pin: S16.A3 is pinned and missing`); helper node refused (`_authority is not a test pytest collects`); EGREGORE source reported, not raised; MW-A and MU-A listed before WU-02 |
| `pytest tests/unit/test_directive_sections.py tests/unit/test_greg_path_cli.py tests/unit/test_acceptance_harness.py tests/unit/test_founder_correction_20261030.py tests/unit/test_developmental_inheritance.py` | 120 passed in 254 s (35 + 2 + 56 + 4 + 23), run beside the mutant gate |
| `pytest tests/unit/test_directive_sections.py tests/unit/test_greg_path_cli.py` on the final tree | 37 passed in 36 s |
| `python -m acceptance check` | exit 0: "sound: 12 missions, 85 requirements, 374 distinct test nodes, 18 contract functions" and the directive line above |
| `python -m acceptance directive --collect --against HEAD` (before the round-2 commit) | exit 0: "no pin at HEAD: nothing to ratchet against", "all 129 distinct cited nodes collect at least one test" |
| `directive --against 74214dd8` in a scratch worktree where S16.A3 was deleted and S1.A3 relabelled EXTERNAL in the map and the pin together | `check` exits 0 (the in-tree pin was edited too); `--against` exits 2: "S1.A3 was pinned BUILDABLE_NOT_BUILT at the base; it may move only to BUILDABLE_NOT_BUILT, not to EXTERNAL" and "S16.A3 was pinned at the base and is gone" |
| `directive --collect` in a clean venv with `pip install -r requirements-dev.txt -r requirements-cognition.txt playwright==1.63.0` (the workflow's install) | exit 0, all 129 nodes collect |
| The same in a clean venv with `requirements-dev.txt` only (F1) | exit 2: 6 files collect nothing |
| `TMPDIR=<scratchpad> python -B scripts/ci/check_directive_sections_mutants.py` | 85/85 caught, exit 0, in 30 min, on the tree at `5d10433e`. The first run, on `74214dd8`, caught 84/85: "Mission L's trace does not cap the coverage" survived because the test cited only a partial requirement; `5d10433e` added a covered one. The commit after it only adds two label assertions |
| LOCAL runs with `-p acceptance._plugin`: round 1's 58 nodes (610 passed, 26 skipped, `local-run-met-asks.json`) merged with round 2's 15 (238 passed, 3 skipped, `local-run-round2.json`) | 58 of the 64 statically met asks that cite only their own nodes are met in the run; the 6 above fall short on skips; the 9 that cite mission requirements were not run. Principle S31.A6's guard skipped (bubblewrap), so in this run it counts unguarded. `directive --outcomes` on the merged run: "DONE 1, PARTIAL 46, OPEN 30; 58/272 asks met in this run; 150 open asks building can still close" (the 150 include asks whose mission evidence was not run) |

All commands ran with `PYTHONDONTWRITEBYTECODE=1 python -B` and `-p no:cacheprovider`.

## Limitations

- The map is a reviewed reading of the directive. Mechanically checked: section count and order, headings, that each
  excerpt and each named line is verbatim in its section, that every cited node and guard resolves to a test (and,
  with `--collect`, collects), that every cited contract function, requirement, gap, unit and record exists, computed
  tiers, coverage caps, blockers, records, statuses, listed-line accounting and the pin. Not checked: whether a
  paraphrase is faithful, whether a required tier is what the words ask, SANDBOX against UNIT for an ask's own nodes,
  whether `covered` is honest within what its citations allow, whether a blocker class is the only reason (a record
  shows the blocker exists), and whether a line set aside is truly not an ask.
- The in-tree pin can be edited together with the map; only `--against` a base (CI on pull requests) refuses that.
  A push to `main` or a local run without `--against` does not ratchet.
- 655 listed lines in 55 sections have no ask yet (10 sections have every listed line accounted for and 12 list
  none): the map was audited line by line only for sections 13, 15 and 69.
  Until they are mapped, "completely built" stays NO for that reason too, and other sections may hide asks.
- Statuses are static ceilings. A run can only lower them. The LOCAL runs cover the own-node asks and the principles'
  guards; the 9 met asks that cite mission requirements rest on the acceptance run's BODY tests, not re-run here. The
  CI workflow collects but does not run the Playwright tests.
- Exhortations no test can observe ("Think deeply", "Do not flatter Alfonso") are not asks.
- The gap map was drawn against `4ec00605`. S15-A and S69-A are new residual labels from this review.
- The workflow has not run in CI; its install was checked in a clean local venv only.
- Reality level: UNIT-TESTED for the checker; LOCAL runs for the nodes behind the met asks and the guards. Nothing is
  founder-used, live or externally verified.
