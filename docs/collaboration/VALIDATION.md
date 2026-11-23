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
