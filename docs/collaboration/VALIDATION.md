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
