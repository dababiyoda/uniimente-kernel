# Collaboration rollout validation

Scope: contributor entry, declaration checks and handoffs. No product runtime test
or claim of actual external Claude-session enrollment is included.

## Evidence trajectory

1. Independent read-only review of #95 at 8d62edf0fa4744d45e7a750ced2f539d387ffaa4
   reproduced all 24 original checker tests. It confirmed missing session/scope/
   overlap declarations and accepted stale AGENTS revisions. These negative probes
   motivated v2; their acceptance is retained here, not erased by the improvement.
2. A separate implementation worker upgraded the single inline workflow and tests:
   46 passing tests, including v2 claim, overlap, revision and handoff cases.
3. Independent reviewer /root/verify_rollout reproduced all 46. It found nested
   triple-backtick fences in RECEIPT.md hid the closing marker in rendered output.
   Coordinator corrected the outer fence to four backticks. Reviewer also showed
   traversal/absolute file claims and obvious session placeholders were accepted.
   Two regression tests and validation closed those declaration-quality gaps.
4. Fresh /root/fresh_entry entered through the local CLAUDE/AGENTS guide, read live
   #96/#193, detected the coordinator's claimed documentation scope and agreed a
   read-only split before work. Discussion API retrieval returned HTTP 400; it
   explicitly retained the source as unread. No overlapping edits occurred.
5. Fresh /root/handoff_receiver acknowledged REHEARSAL-HANDOFF.md and resumed its
   task without founder reconstruction. It independently ran all 48 then-current
   tests and confirmed corrected fences, split/blocked and receiver examples.
   It found receiver placeholders were still accepted; coordinator fixed that
   asymmetry and added the 49th test.

Final command: `python3 tests/unit/test_collaboration_receipt.py` — 49 tests pass
in the local partial package. No repository runtime imported; tests exercise the
exact Python embedded in the workflow, not a second validator implementation.
Independent runs cover the preceding 46/48-test snapshots; the final one-line
receiver hardening and regression were rerun by the coordinator.

Founder-intent and deliberation JSON were validated using the invoked protocol's
`validate_intent_ledger.py` and `validate_deliberation.py`: valid, five perspectives
and exactly two strengthening passes. The five decision perspectives are parent
self-review, distinct from the independent workers identified above.

## 2026-10-22: two real Claude Code cloud sessions (#197)

Issue #197 handed two real defects to two fresh Claude Code cloud sessions. They were started by the integration
owner `session_01FBS4KNJR59nSbdGbxo8Mbx`, with the candidate checked out at `9478aaf8`. Each prompt named only its
task on #197 and said "follow the repository's own entry instructions". Neither prompt mentioned #89, #96,
START_HERE or the other session.

- **Task A** (`session_01CcMMcMVNb28chWHspMfCEj`): the Mac runbook (`greg/FIRST_MISSION.md`) installed #122's
  stale branch.
- **Task B** (`session_01YY3PSpQdRnfUWNam2cUwzf`): the review-branch drift guard covered only the Chromebook
  surfaces.

The two tasks overlap. B's test has to fail on the file A fixes.

Observed, from the #197 comments and the sessions' tool calls:

| Measure | Result |
|---|---|
| Found Discussion #89 unaided | both, through the public REST API line now in START_HERE. The 2026-10-21 sandbox got HTTP 400 at this step. |
| Found START_HERE and board #96 unaided | both |
| Detected the overlap before editing | both. Each claim named the other task's file and proposed the same split: A owns the runbook, B owns the test. |
| Claim race | the claims landed 22 s apart (02:49:30Z, 02:49:52Z), so B's claim says no A claim existed. B stated its own time wrongly (02:55Z) and corrected both points in its handoff after re-reading the thread before committing. Advisory claims are not atomic, as START_HERE says. |
| Scope discovered beyond the task | B found a third stale surface (`docs/opus-maximus/MISSION_CONTROL_OPERATIONS.md`) and left it unassigned for the integrator. The integrator assigned it to A, and A acknowledged and fixed it. |
| Duplicate edits | 0 |
| Founder interventions | 0. The integrator posted one decision (split acknowledged, third surface assigned, intake order) and sent one peer message pointing A to it. |
| Handoffs | both complete: product delta, base/head, commands and results, limits, next owner, claim released. A also added a v2 receipt to #198 after its first receipt check failed. |
| Receiver resume | the integrator resumed both handoffs. #198 (`162e388b`), then #199 (`70b1f21a`), merged into the candidate as `4a435ee2` / `ba4253e3`. `tests/unit/test_greg_chromebook_install.py`: 18 passed. #199 was red by design until #198 landed, as both handoffs said. |

Limits:
- The receiver was the integrator session, not a third fresh session. The 2026-10-21 sandbox covered a fresh receiver.
- Both tasks were small and documentation/test only.
- Two sessions are one data point for the five-PR pilot.
- No client outside Claude Code cloud sessions was tested.

## 2026-11-13: three cloud sessions against the prepared one-entrance instructions (#319, draft #316)

Status: **prepared instructions tested; entry by default-branch discovery not tested** (the default branch is still
`main`). Issue #319 holds two real fixes to `scripts/README.md` from the entry audit. Each session was given only
"Do Task X of #319. Follow the repository's own entry instructions." Three independent scorers, an adjudicator and a
skeptic read the full event logs (workflow `wf_372a2fca-9b4`); the observer's first notes had four errors, corrected
below.

- **A** (`session_01KucyfniBpkBo8sonG3iuJB`), started in the Kernel on #316's branch at `da99b8b4`, Task A.
- **B** (`session_01KucyfkNkDU5AhXbYNJvLhm`), started in RESEARCH-IN on its entry draft at `ba4ec858`, Task B,
  concurrently with A.
- **C** (`session_01KucyfornmpcogcwSAf5Fhk`), started in the Kernel on #316's branch at `edbe8963`, Task B, launched by
  the observer after B stopped.

| Measure | A | B | C |
|---|---|---|---|
| Found the integration branch and board #96 | yes (AGENTS.md and START_HERE read, newest #96 page read, line fetched) | branch from the organ pointer; never read #96 | yes |
| Check-in with the new fields, before editing | **no**: all fields, but posted at 11:12:46, after its edit (11:10:56), push and PR #320 | **no**: none posted; it edited first | partly: posted 11:31:00, before its first edit (11:31:15); no `Depends on`, overlap status, head or handoff condition |
| Overlap detected and split recorded | partly: detected #316 before editing; split recorded only after | **no** | yes, against A's posted claim (sequential, not concurrent); no acknowledgment sought |
| Handoff resumed by another session | none was due | **no**: B's work never left its container | **no**: C redid Task B from scratch |
| Founder interventions needed | 0 | **1, not given** | 0 |

What happened to B: the session's GitHub scope was RESEARCH-IN only (`issue_read` on the Kernel refused at 11:10:07),
the automatic permission check refused adding the Kernel with push (11:10:10), and the proxy refused the public REST
read (11:10:25). B still edited and committed locally (a tested fix and a coverage test), then stopped asking the
founder for access. Its work is invisible to everyone else; C duplicated it, and B's coverage test was lost. B was told
afterwards that #321 holds the task and not to push.

The only concurrent pair, A and B, editing the same file between 11:10:56 and 11:11:30, never saw each other. A and C
produced draft PRs #320 and #321, which merge cleanly with each other and with #316. Totals: found branch and board
2 of 3; check-in before editing 0 of 3 fully; overlap and split 1 of 3; handoff resumed 0; founder interventions 1.
Under identical entry files, A posted late and C on time with A's posted check-in in front of it: the example on the
board, more than the instructions, carried the protocol.

Root causes and the fixes in this PR:
- **The check-in asked for facts that exist only after the edit** (head, PR number, results), and `--paths`, the only
  command A ran before editing, never printed the block. Now: entry lines say "before any edit, commit or push" with
  `pending` for head and PR; the block is fillable before the edit; `--paths` and `--unit` end their answer with it (the `checkin` key).
- **The map missed PRs it had not fetched** (#307 and #268 change the file; A's map did not list them). Now: with
  `--github` it reads each open PR's changed files from the API and says when it cannot.
- **An organ-started session had no stop rule.** A one-sentence stop rule goes on the 12 consumer drafts as a second
  forward commit: "Do not edit files in dababiyoda/uniimente-kernel unless this session can read and post on the
  Kernel's work board (dababiyoda/uniimente-kernel#96), read the open pull requests that touch those files, and open a
  pull request to that repository; if it cannot, stop before editing and say what is missing (for example, a session
  started in the Kernel)." The board is named in full because DALEOBANKS has a pull request #96 of its own. An
  independent review (workflow `wf_f4d14d72-2c0`) rejected a second sentence that would have moved the claim into a
  consumer pull request: it placed the claim after the first commit and, in VoiceStudio, would have put session
  identifiers into pull request descriptions, which that repository's attribution rule forbids.
- Hand-overs, not edits: START_HERE (#206) for where a claim goes, when an acknowledgment is needed and what a session
  that cannot publish does; AGENTS.md step 1 (integrator) for a line of its own for the before-edit rule.

Limits:
- The observer wrote the tasks and holds a claim on the same file; the trial tests the prepared instructions only.
- A and C started on #316's own branch, the only place the new lines, block and map exist. Entry from `main` or the
  line was not tested.
- Three sessions on one model; one concurrent pair; C's overlap test was sequential.
- The fixes above are untested. Falsifier for a re-run: a Kernel-started session whose first #96 comment is later than
  its first edit or commit, or an organ-started session that edits Kernel files without having posted on #96.
- Whether an organ-started session may be given Kernel push access is a founder permission decision.
- Open, not fixed: a cloud session started only in a consumer repository may be unable to read or post on #96 at all,
  even for work on that repository's own files, so the pointer's "post a bounded claim on that board" cannot always be
  followed. Where such a session's claim should go is handed to START_HERE's owner (#206) and the founder. No session
  in this trial did consumer-repository work, but the gap was observed the same day outside it: a session working on
  WealthMachineIntelligence #43 (`session_012idQXWUrVAMHPo3iZpSfmv`) could not reach #96 and asked this session to
  relay its claim (relayed as #96 comment 6853656353, verified against GitHub).

## 2026-11-22: three cloud sessions against #316's fixed instructions (#343)

Status: **#316's fixed entry instructions were tested on #316's own branch. Falsifier F1 fired: one of the two Kernel-started sessions posted its check-in after its first edit. F2 did not fire. Entry from `main` or the line was not tested.**

Issue #343 holds two real fixes. The observer, `session_01KucyfnCuSTnjx5Fa6T4A3d`, opened it at 12:06:34Z.
- **Task A** doubles the backslashes in two mutant anchors of `scripts/ci/check_cortex_mutants.py` (lines 866 and 868). The text the anchors match must not change.
- **Task B** adds a fast test that fails on any invalid escape sequence in a tracked `.py` file, and runs it in Canonical CI.

B's test fails on the line until A lands. Ten other open PRs into the line also change `check_cortex_mutants.py`.

Each session was given only "Do Task X of dababiyoda/uniimente-kernel#343. Follow the repository's own entry instructions." Three scorers, an adjudicator and a skeptic read:
- the full event logs (K1 110 events, K2 128, O1 36);
- the #96 and #343 threads;
- #344 and #345.

The skeptic's corrections to the adjudication are applied below.

- **K1** (`session_01KucyfmgnCagqw44soJL3ov`), Task A. It started at 12:06:53Z in the Kernel, on #316's branch `claude/structural-review-live` at `a10ffcfe`.
- **K2** (`session_01KucyfmMHC6osPhLgwU2vHU`), Task B. It started at 12:06:55Z on the same branch, concurrently with K1.
- **O1** (`session_01KucyfnNVA4DL9hnhoAunt9`), Task B. It started at 12:06:58Z in RAILSCOUT, on entry draft #6 at `adcf90f8`, which carries the stop rule added after #319.

| Measure | K1 | K2 | O1 |
|---|---|---|---|
| Found the integration branch and board #96 | yes: read START_HERE, #89 and the newest #96 page (12:07:28); fetched the line at `9b931994`; worktree on a new branch from the line head | yes: read START_HERE, #89 and the newest #96 page (12:08:34); fetched the line; worktree on a new branch from the line head | the branch only: a read-only clone at `9b931994`; never read #96 |
| Check-in with the new fields, before editing | **no**: every template line filled, but posted at 12:10:50 (7078930000). That is 159 to 162 s after its first edit (12:08:08.8) and before its commit (12:11:03), push and PR | **yes**: posted at 12:09:31 (7078914853), 15 to 16 s before its first edit (12:09:47); every template line filled | n/a: no check-in and no repository edit |
| Overlap detected and split recorded | partly: named 6 of 10 into-line PRs on the file, copied from #340's board claim, and opened none of them; never saw K2's check-in, posted 79 s before its own; split one-sided, taken from the issue text | partly: named 3 of 12 into-line PRs on `canonical-ci.yml` (plus #312, which is not into the line) from a truncated map answer; never saw K1, which posted after K2's only board read; split one-sided; dependency on Task A stated | **no** |
| Handoff resumed by another session | none due from K1, which is the dependency; it recorded no dependent | **no**, although one was due: #345 is red until Task A lands. #344 existed from 12:12:22; K2 never found it, linked it or stacked on it | **no**: its draft stayed in its container, and K2 duplicated it |
| Founder interventions needed | 0 | 0 | **1, not given** |

**What happened**

- **K1:**
  - It read #343, the first 120 lines of START_HERE, #89 and the last six comments of #96. It then fetched the line and ran `work_map.py --github --paths` through `tail -60`. That kept the claims and the check-in block, and cut the per-path PR list.
  - At 12:07:39 it wrote "I'll check the work map and open PRs on that file before editing". At 12:08:08 it edited in its new worktree without listing open PRs.
  - It spent about 2.5 minutes verifying: constants, the stale check, and the two mutant catches. It caught its own false "CAUGHT", which a missing dependency had caused.
  - It then wrote "Next I'll post the check-in on board #96, then commit, push and open the draft PR", and posted at 12:10:50. The check-in's acceptance evidence was its finished results.
  - It validated its receipt locally and opened draft #344 at 12:12:22.
- **K2:**
  - It ran the map four times, read the last eight comments of #96 and listed the ten newest PRs.
  - It scanned 1,135 tracked files in a new worktree, with the scan script kept outside the worktree.
  - It wrote "Posting the check-in on board #96 before editing.", posted at 12:09:31, and wrote the test at 12:09:47.
  - It confirmed the fail-before on 3.11, 3.12 and 3.13. For the pass-after it doubled the two backslashes in a temporary detached worktree (12:10:50); it removed the worktree at 12:11:00 and committed nothing there.
  - It opened draft #345 at 12:13:02.
- **Neither Kernel session re-read** #96, #343 or the PR list after its first read. That covers posting, opening its PR, updating its check-in (12:12:34 and 12:13:13), and its scheduled 13:04Z turn.
  - Neither log contains the other session's id, check-in id, branch or PR number.
  - K2's update kept the line "No claim or PR names #343", which was false by then.
- **O1:**
  - It read RAILSCOUT's AGENTS.md, which carries the stop rule.
  - At 12:07:16 the auto-mode classifier refused its request to attach the Kernel with push access.
  - It cloned the line read-only and read #343 through a logged-out page fetch.
  - It wrote a Task B test in its scratchpad and confirmed the Kernel clone was unchanged.
  - It stopped at 12:08:30 and said what was missing. It had no GitHub tools, and it did not try a public REST read of #96 or the PRs.
- **The two PRs:**
  - #344 (K1): base `claude/greg-full-machine-completion-whgiee` at `9b931994`, head `b580cda5`, 1 file, +2/−2.
  - #345 (K2): the same base, head `e4f15752`, 2 files, +64.
- **Their receipts:**
  - Both are v2 receipts whose `coordination.task_ref` is the session's own check-in URL.
  - The line's validator (`collaboration-receipt.yml` at `9b931994`), run on the live bodies, accepts #344. It refuses #345 with "invalid validation result": #345 uses 'failed' and 'passed' instead of fail and pass. With those two words corrected, #345 passes.
  - Both receipts declare `AGENTS.md` as read at the head; neither session read it.
  - K1's receipt also lists six PRs as inspected that K1 never opened.
  - Neither START_HERE pin is the commit where the guide was read (`a10ffcfe`): K1 pinned its head, K2 the base. The file is identical at all three commits.
- **Correctness, checked independently:**
  - At `9b931994` the file fails `compile` at line 866 with warnings as errors.
  - At `b580cda5` it compiles. All 1,941 AST constants (1,930 of them strings) are unchanged, and each anchor occurs exactly once in `greg/licensing.py`.
  - #345's tests fail on exactly lines 866 and 868 under Python 3.11.18, 3.12.3 and 3.13.18, and pass on all three with #344 merged. The planted-defect test passes on all three.
  - #344 and #345 merge cleanly. No into-line PR changes the two anchor lines or #345's insertion point.
  - #344's text calls the 1,941 constants "string constants".
  - Not run: the full 459-mutant gate, the full suite and remote CI.
- **CI and the thread:**
  - All 15 checks on both heads were still queued at 13:40Z. The board had reported runner starvation at 08:33Z.
  - On #345 alone, the new step will stop job 1 before the full suite, because no later step in that job runs after a failure.
  - As of 13:49Z there is no comment or review on #343, #344 or #345, and the integrator has not posted on #96 since 08:33Z.

**Totals:**
- found the branch and board: 2 of 3;
- check-in with the new fields before editing: 1 of 3 (1 of 2 Kernel-started);
- overlap detected and split recorded: 0 of 3 fully, 2 partly;
- the concurrent pair detected each other: 0 times;
- handoff resumed: 0 of 1 due;
- founder interventions: 1.

**Against #319:**
- Finding the branch and board stays at 2 of 3.
- Check-in timing among Kernel-started sessions is unchanged at 1 of 2: in #319 A was late and C on time; here K1 was late and K2 on time.
- What improved:
  - both check-ins now carry every field (C lacked four);
  - K1's late post came before its commit, where A's came after push and PR;
  - no organ-started session edited (in #319, B did).
- Overlap and split fell from 1 of 3 (C, against A's posted claim) to 0 of 3 fully.
- Concurrent detection stays at 0, handoffs resumed at 0, and founder interventions at 1.
- In #319 the example check-in on the board looked like what carried the protocol. Here both sessions had check-in examples in front of them, and one still posted late.

**Root causes**

1. **Nothing holds an edit until the check-in is posted, and K1's own plan left the check-in out.**
   - Both sessions read the rule. CLAUDE.md says "Before any edit, commit or push, post your check-in", and START_HERE has "Before editing: establish a real work claim".
   - Both saw the check-in block; K1's `tail -60` kept it.
   - K1 planned "the work map and open PRs ... before editing", then treated the check-in as a pre-commit step.
   - Nothing refuses an edit or a commit without a check-in. The receipt check runs only at PR time, in CI that was not running.
2. **Overlap is looked up by file, and only once.**
   - Each Kernel session read #96 once, before the other had posted.
   - The A–B dependency crosses files: A touches `check_cortex_mutants.py`, B a new test and `canonical-ci.yml`. Neither session's `--paths` query could therefore show the other's claim, and the check-in block has no issue or task key the map can match.
   - START_HERE does ask for re-reads: "Refresh competing claims immediately before an overlapping edit", "Recheck heads and relevant claims before handoff", "On resume, reread the board, heads and handoff". Neither session did any of these, including in its 13:04Z scheduled turn.
   - No rule ties a re-read to posting the check-in or opening the PR.
3. **The two entry surfaces name different places for the claim.**
   - CLAUDE.md says to post the check-in on #96. START_HERE says "Post one bounded claim on the existing relevant work item and link it from #96".
   - Both sessions followed CLAUDE.md. Neither posted on #343, the one surface both of them read.
4. **The sessions cut the map's answers short.**
   - K1 kept the last 60 lines and took its PR list from #340's board claim. K2 kept the first 1,500 characters.
   - The resulting PR lists covered 6 of 10 and 3 of 12 PRs. The 'clear' conclusions happened to be right.
   - The #319 fix, under which `--github` reads each PR's changed files, was therefore not seen in full by either session.
5. **A recorded dependency has no follow-through rule.**
   - K2 wrote "Depends on: Task A" and "integrator takes Task A first". Nothing asks a session to find and link the dependency's PR or check-in, stack on it, or tell its owner.
   - K2's recheck looked only at whether the base had moved. K1 recorded no dependent.
   - Both handed off to an integrator who had not posted since 08:33Z.
6. **The receipt guidance reached the sessions from the line, not from #316.**
   - Edits happen in a worktree from the line head, as instructed, and both sessions read `RECEIPT.md` there, at `9b931994`. That version lacks #316's 2026-11-13 convention that the guide is pinned at the commit actually read.
   - The `task_ref` convention also appears in CLAUDE.md, and both followed it. The pin convention appears only in RECEIPT.md, and neither followed it.
   - The same file shows only `"not_run"` as a result value and never lists the allowed values. K2 used 'failed' and 'passed', and never ran the validator. CI would have caught the error, but CI had not run.
7. **A required receipt field produces a declaration, not a read.**
   - The validator requires an `AGENTS.md` entry at the PR head. RECEIPT.md says to reread AGENTS.md after each push and never to invent a source read. START_HERE step 2 says to read it.
   - Neither session read it, and both filled the entry. The validator cannot tell the difference.
8. **The organ stop rule held; the access gap is unchanged.**
   - The classifier refused O1's request for Kernel push access, O1 had no GitHub tools, and O1 stopped as the rule says.
   - It did not test a public REST read of #96. Its work stayed private, and K2 duplicated it.
   - Whether an organ-started session may get Kernel write access remains the founder's decision.

**Limits**

- **Timestamps:** times are event `created_at` values. For an edit this is the tool-call time; the write itself ran before the tool result, within 2 s. Board and PR times are GitHub `created_at` values, which have 1 s resolution. K1's gap (159 to 162 s) and K2's margin (15 to 16 s) are both well outside that error.
- **Motives:** only K1 has thinking blocks with text, 4 of 20. K2's 24 and O1's 7 are empty. Motives are inferred from visible text.
- **Context:** the sessions' system context is not in the logs. The finding that neither read AGENTS.md rests on two facts: no tool call reads it, and CLAUDE.md at `a10ffcfe` does not @-import it.
- **Overlap ground truth:** it comes from the GitHub API at 13:15 to 13:45Z, not at 12:07Z, and each patch is relative to its PR's own base. 29 further open PRs into other bases also change `check_cortex_mutants.py`; they do not bear on the line.
- **Design and sample:**
  - The observer wrote the tasks and assigned Task B twice.
  - K1 and K2 started on #316's branch, so entry from `main` or from the line was not tested.
  - The sample is one concurrent Kernel pair and one organ session.
  - All three main loops ran on claude-opus-5-5. O1's issue read was done by a claude-haiku-5-5 subagent.
- **Judgment calls:**
  - "Overlap" includes same-issue and dependency work, not only shared lines.
  - K2's "or now if you'd rather I take Task A here" is counted as an offer made after finishing, not an intervention.
  - K2's uncommitted pass-after edit in a temporary worktree counts as a repository edit, but it came after K2's check-in.
- **Window:** observation ends at about 13:50Z. K1 and K2 resume on PR events, and the integrator may still act.

**Falsifier outcomes**

- **F1, a Kernel-started session whose first #96 comment is later than its first edit or commit: fired.**
  - K1's first #96 comment (7078930000, 12:10:50Z) is later than its first edit (12:08:08.8Z), which changed `scripts/ci/check_cortex_mutants.py` in worktree `/tmp/claude-0/wt-taskA`. It is earlier than K1's first commit (`b580cda5`, 12:11:03Z).
  - K2 did not trigger it: comment at 12:09:31Z, first edit at 12:09:47Z, commit at 12:12:29Z.
  - The #319 fix to the entry lines did not prevent a late check-in.
- **F2, an organ-started session that edits Kernel files without having posted on #96: did not fire.**
  - O1 edited no Kernel file. Its clone's status was empty at 12:08:18Z, and its one write-capable command there was `mkdir -p` on a directory that is already tracked.
  - It posted nothing and stopped, citing the rule.
  - The cost was one founder intervention, not given, and private work that K2 then duplicated.

**Proposed next fixes** (from the root causes above; proposals, not built in #316):

- Root cause 1: make the check-in the first numbered step of the entry lines, and say "before your first edit, not before your commit". The lines are `CLAUDE.md` and `AGENTS.md` here, and `START_HERE.md` through its owner, #206.
- Root causes 2 and 4: give the check-in block a task key (the issue it works on). `--paths` and `--unit` would then list other check-ins that cite the same issue, and would print the per-path PR list and its count before the block, so a cut answer still shows them.
- Root causes 2 and 5: tie a re-read of #96, the issue and the PR list to opening the PR and to every resume. Link a dependency's PR or check-in from the dependent's check-in.
- Root cause 3: settle where a claim goes, on #96 or on the relevant work item linked from #96. This is a hand-over to #206 and the integrator.
- Root cause 6: list the receipt's allowed `result` values in `RECEIPT.md`.
- Root cause 8: an organ-started session's Kernel access remains the founder's decision.

## What the evidence proves

Unit tests demonstrate metadata parsing and refusal behavior: exact event refs,
current-head AGENTS declaration, pinned guide and integration refs, actual-shaped
session/file declarations, recorded overlap search/split, no self-accepted handoff,
and preservation of fail/not_run results. Hostile shell-like strings stay data.
Workflow inspection shows permissions:{}, no checkout, no secrets, no network,
and no interpolation of PR text into executable code.

Sandbox rehearsal demonstrates entry routing, explicit overlap acknowledgment,
separate reviewer scope and successful receiver resume. It is not a Claude Code
process, a global client installation, an atomic file lock or verified real-world
team productivity. Some linked sources were unavailable and were not claimed read.

## Remaining acceptance and operational limits

- Actual GitHub Actions execution at the newly published commit is checked and
  reported in PR #193; local test success does not predict hosted availability.
- All default-branch and consumer adoption remains pending until authorized merge.
- Discussion #89 update requires authenticated access; prior secure sign-in was
  rejected by automatic approval review. No credentials were submitted or bypassed.
- Existing product sessions must acknowledge source pins, scope and integration
  destination; a posted coordination notice is not acknowledgment.
- Actual external Claude startup/resume and five-PR benefit measurement remain
  NOT_RUN / NOT_MEASURED. Private chats, local uncommitted work and user-device
  client settings are unavailable here.
- False declarations, fabricated URLs, semantic duplication, expired notices and
  PR-authored workflow changes still require actual review. No enforcement claim.

Source provenance: #95 workflow/tests and six SOPs; #193 initial routing and intent
decision; current default entry files; source pins in REPOSITORY-SNAPSHOT.json.
No original failure, previous decision or unrelated runtime is deleted.
