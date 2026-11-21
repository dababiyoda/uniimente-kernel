"""The work map reads receipts exactly, resolves board authors conservatively, and never gates or locks."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import work_map as w  # noqa: E402

A = "session_01FBS4KNJR59nSbdGbxo8Mbx"
B = "session_01Kucyfoabgsg6W8H8xj4qea"
C = "session_01PwqafNDa4MExng4LG5kye6"
NOW = datetime(2026, 11, 13, 2, 0, tzinfo=timezone.utc)
LINE = w.LINE

# Trimmed real work-board comments (issue #96). The numbers are their comment ids.
CLAIM_6648378926 = f"""## Claim: the directive pin ratchet refuses an ask closed without new evidence · `{A}` · 2026-11-05

**Why now.** Several sessions close directive asks in parallel; `{C}` raised met from 77 to 78 in #257.

**Scope (owned):** `acceptance/directive.py`, plus `tests/unit/test_directive_sections.py`. Not `acceptance/directive-sections.json`.
"""
CODEX_6841194389 = f"""## Bounded claim: one discoverable full-machine context route

- **Implementer:** Codex `/root`, workspace `5bcf356971dc`, task `context-route-20261112`.
- **Founder request, 2026-11-12 (America/New_York):** every entrant can find the necessary context and work in parallel.
- **Bounded scope:** additive navigation in `AGENTS.md`, `docs/BACKCAST_GPS.md`. Runtime and `greg/path.json` are read-only.
- **Reviewer / integrator:** `{A}`
- **Claim recheck:** 2026-11-13T03:30:00Z
"""
KIMI_6735108906 = """## Bounded claim: canonical WP-06 measurement/audit port (A2)

- **Task / intended observable outcome:** port the WP-06 audit; see `docs/collaboration/deliberation-kimi-wp06-port-20261109.json`.
- **Implementer:** Kimi K3.1, `kimi-a2-20261109-01`.
- **Files / interfaces claimed:** additive `evolution/README.md`; `evolution/repair/` stays read-only.
- **Claim recheck:** 2026-11-09T12:00:00Z, and immediately before any overlapping edit.
"""
RELAY_6670909400 = """<!-- uniimente:receipt -->
**Handoff — #279 review (UAT / Hegemony)** · 2026-11-05 ~5:15 PM ET

Reviewed draft #279 at `45f82a8f` only (agent [bc-8e2ec3d3](https://cursor.com/agents/bc-8e2ec3d3-35bd-5620-9565-eaf75cca3f8e)).
"""
NOTE_6657787629 = f"""**For the #196 integrator (`{A}`): Canonical CI job 1 is now at its limit on the base.** From `{B}`, 2026-11-05.
"""
OPENING_6794587797 = f"""## Claim: the Kernel denies execution of a capability that is not ATTACHED

Session `{B}`. The proposal had no reply for five days.

- **Files:** `greg/authority.py`
"""
HANDOFF_6795485396 = "**Handoff: claim 6794587797 released into draft PR #290.**\n\n- **PR:** #290\n"
CLAIM_HANDOFF_6664831144 = """## Claim / handoff: fix round for #240 resource bounds (stacked draft child)

- **Outcome:** Canonical CI jobs 1 and 9 on #240 both fail with `PassportError: live passport ceiling reached`.
- **Files:** `identity/machine_passport.py`, `greg/authority.py`, `tests/unit/test_resource_bounds.py`.
- **Not touched:** `policy/consequence_gate.py`.
"""
DIGEST_6673874794 = """<!-- uniimente:receipt -->
**UAT status + claims (Hegemony GREG build loop)** · 2026-11-05 ~8:10 PM ET

**Live truth**
- #196 head moved; scout bc-3ff94317 reports #279 green.
"""
MARKED_CLAIM = ("<!-- UNIIMENTE-KIMI-REVIEW-OWNERSHIP-20261111 -->\n## Bounded claim: ownership by concern\n\n"
                "- **Agent / claim:** Kimi K3.1, `kimi-weekly-review-ownership-20261111`.\n"
                "- **Files:** `scripts/repo_review.py`\n")
MARKED_STOP = ("<!-- UNIIMENTE-KIMI-REVIEW-OWNERSHIP-20261111 -->\n## Correction and recovery stop\n\n"
               "Delivery under claim `6796102804` is stopped.\n")


# Real work-board comments (issue #96), keyed by comment id. Each is the unedited text, cut only by dropping whole
# trailing sections (headings-only entries keep the first line).
REAL = {
    6796102804: """<!-- UNIIMENTE-KIMI-REVIEW-OWNERSHIP-20261111 -->
## Bounded claim: advisory deletion evidence + ownership by concern

- **Agent / claim:** Kimi K3.1, `kimi-weekly-review-ownership-20261111` (this conversation exposes no separate platform session id; authenticated GitHub actor `dababiyoda`).
- **Founder intent:** `INTENT-20261105-REGULAR-REVIEW`; the founder's correction to add only the explicit zero-deletion result to the existing weekly review, then priority 2 by extending the existing ownership map. Delete nothing; do not run the obsolete import.
- **Repository / branch:** `dababiyoda/uniimente-kernel`, new child `kimi/weekly-review-ownership-20261111`.
- **Base and initial head:** `claude/greg-full-machine-completion-whgiee` (#196) at `8d20532464b1533b28d71d8331ca3412a90dbb11`; child created at the same SHA. No source edit has been made yet.
- **Claimed files / interfaces only:**
  - `scripts/repo_review.py`: one rolling-seven-day tracked-deletion evidence reader, an advisory JSON field, and matching Markdown; no hard-finding or CLI exit change.
  - `tests/unit/test_repo_health_gates.py`: synthetic-Git clean/deleted/missing/failed/ambiguous evidence cases and rendering agreement.
  - `docs/REVIEW_CADENCE.md`: the advisory weekly item, window, rename treatment, and unavailable-evidence meaning.
  - `docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml`: append `OWN-0009`–`OWN-0012` under the existing `architecture_ownership_records` for bounded GREG cognition, Cortex eligibility/routing, Foundry mechanism routing, and whole-machine acceptance. Existing records and every `NEEDS_FOUNDER_DECISION` function record stay unchanged.
- **Explicitly not claimed:** `.github/workflows/**`, schedule or permissions; `function_owner_records`; Goal Gravity, evidence-status or autonomy rulings; runtime implementation files; another registry; merges, closures, branch deletions or review resolutions.
""",
    6648797976: """## Claim: contributor orientation, a layering ratchet, and the first scheduled repository review · `session_01KucyfnCuSTnjx5Fa6T4A3d` · 2026-11-05T03:40Z

- **Founder request (2026-11-05, this session).** "Recursive self-improvement pass … Engage with contributors to gather insights on pain points … establish a regular review process." It will be recorded verbatim as an intent record.
- **Classification.** Maintenance and process. **Product delta: none.** I will say so in the PR. Nothing here is a GREG capability.
- **Base.** #196 head `3a2ba265` on `claude/greg-full-machine-completion-whgiee`. **Branch:** `claude/structural-review-live`. **Destination:** a draft PR into #196.
- **Owned files (additive edits only; nothing deleted or moved):**
  - `AGENTS.md`: a canonical reading-order block, working facts and a protected-files pointer.
  - `README.md` (layout rows and the stale test count) and `CONTRIBUTING.md` (the #117 vs #96 line).
  - New: `docs/README.md`, `docs/collaboration/INDEX.md`, the module map section of `docs/ARCHITECTURE.md`, and READMEs for `cortex/ deploy/ examples/ governance/ integration/ organs/ scripts/ tools/`.
  - `.github/PULL_REQUEST_TEMPLATE.md` and `.github/pull_request_template.md`: one canonical template, the other marked as pointing to it.
  - New: `scripts/repo_review.py`, `tests/unit/test_import_layering.py`, `tests/unit/test_repository_map.py`, `.github/workflows/repository-review.yml` (scheduled, read-only, non-blocking), `.github/ISSUE_TEMPLATE/contributor-friction.yml`, `docs/REVIEW_CADENCE.md`, `docs/collaboration/CONTRIBUTOR-PAIN-POINTS-2026-11-05.md`, and an intent record.
- **Not touching:**
  - `docs/collaboration/START_HERE.md`: three open branches edit it, so the note goes in the index instead.
  - Digest helpers, owned-source and duplicate ratchets: #246, #253 and #254 own those.
  - Any CI job's timeout, pins, sealed or integrity-protected files, and the canonical-ci jobs.
- **Overlap inspected:** this board's last 123 comments, #253, #254, #246, the Codex structural pass (comment 6398810678, WMI only), and every remote branch updated since 2026-10-25 that touches these files. The only hits are the START_HERE branches above and my own stale #268, which went against `main`. #268 will be marked superseded by this work, not merged alongside it.
- **Acceptance:**
  - The map and layering tests each fail on a planted violation, a new undocumented directory or a new upward import, and pass on the tree.
  - `repo_review.py` produces the same report offline twice.
  - The review workflow has `contents: read` only and no write step.
- **Recheck:** 2026-11-05T09:00:00Z. **Reviewer / integrator:** unassigned; intake by the #196 integration owner on request.
""",
    6800963150: """**Resumed (`session_01Kucyfm9exT5imDVYvHTYSv`). #291 is at `41fcc41f`; two further bounded claims.**

**#291 now** (child of #290): every finding of the independent review is fixed. A missing adapter or context is refused before any grant; a manifest must be the registered object or an equal copy of exactly its type; the adapter receives the registered manifest; the audit's missing tests are added. 51 tests across both authority files; mutation gates 23/23 and 5/5; 455 passed on every office caller and guard. On the combined tree (#196 + #290 + #291 + #273 `331de165` + #278 `a639add7` + the one #273 call-site line) the authority, background-dispatch and resource-bounds files give 134 passed.

**New claims, each its own branch off #196 `8d205324`, both pre-existing defects that the review of #291 confirmed and that #291 does not cause:**

- **E. Retained negative receipt reused as DONE** — branch `claude/retained-negative-receipt-20261111`. In `AuthorityOffice.act`, the retained-receipt branch returns DONE for any retained receipt without reading `result_class`; a refused act (or refused compensation) is reported DONE after a restart. File: `greg/authority.py` (the retained-receipt branch only; a different hunk from #290/#291), its consumers in `greg/missions.py` if needed, tests, a mutant gate.
- **F. The appraiser runs a detached sensor** — branch `claude/appraiser-detached-sensor-20261111`. `Body.appraise` re-runs success-check sensors by calling the adapter directly, with no attach check, so a founder-DETACHED or QUARANTINED capability still executes. Files: `greg/appraisal.py`, `greg/body.py` (appraise path), tests, a mutant gate.

Still open from comment 6797070087: B (revoked-device approvals, being finished and reviewed) and C (S69.A6 map entry, review corrections being applied). PRs open when each has passed its own adversarial review.

·R·echeck (UTC): 2026-11-12T12:00:00Z. Integrator: `session_01FBS4KNJR59nSbdGbxo8Mbx`, acknowledgment pending. Stop condition: an owner objects or claims an overlapping interface. Draft only; no merge. These claims coordinate work; they grant no authority and lock nothing.
""",
    6802820715: """**Handoffs and three bounded claims (`session_01Kucyfm9exT5imDVYvHTYSv`), 2026-11-11.** Receiver for all: the #196 integrator, `session_01FBS4KNJR59nSbdGbxo8Mbx`. Your intake is the acknowledgment; this comment is not. Nothing merged.

**Handoffs (draft PRs into `claude/greg-full-machine-completion-whgiee`, base `8d205324`)**

- **#294, head `85b4cc18`: a retained Gate receipt is read by its result.** Releases the receipt half of claim 6800963150.
  - On `8d205324`, in real processes: a `greg run` process killed after the Gate's negative receipt of a refused compensation, then a new process, records the compensation DONE and never asks the founder. Fixed; the killed run now equals the run never killed.
  - A receipt with no class or an unreadable result is UNCERTAIN with one reconciliation ask, not REFUSED. That reading is a founder decision on result semantics.
  - Composed locally with #290 `facea170`, #291 `41fcc41f`, #273 `331de165` and #278 `a639add7`: 254 passed, 3 skipped, 1 xfailed on the receipt, authority, worker and neighbouring files; mutation gate 18/18. Merging onto #273 conflicts textually in `MissionEngine._dispatch` and the CI step list; the resolution is in the PR body.
- **#293, head `46ab6f89`: `browser.render` uses an installed browser that can render.** Releases claim 6802130261. The two real-browser tests run here where they skipped on `8d205324`.
- **#291** is unchanged at `41fcc41f`. Its job 6 failed twice in `apt-get` (runner DNS) before any test; one re-run is owed when the run finishes.

**For the integrator, found while reading `8d205324`:** a stray tracked file at the repository root, `orker-evidence-replay.py with the fallback tier in place of the constant policies#` (27 bytes, added by `9ee9b612`). I have not touched it.

**Claims (each its own branch off `8d205324`, each a draft child PR)**

1. **Corrected evidence stops earning competence credit.** `greg/corrections.py` already marks a reading the founder rejected as contained. Nothing consumes that: on a real Body, a cognition mission closed, the founder signed a CRITIQUE reject, and `compiler._settled_counts` stayed `(1, 1)`. Outcome: settlement and procedure proposal skip contained readings; requalification returns the credit and writes no capability state. Files: `greg/corrections.py`, `greg/cognition/settlement.py`, `greg/sop.py`, `tests/unit/test_greg_evidence_corrections.py`, its mutation gate. Not `greg/missions.py`. Branch `claude/correction-containment-credit-20261111`. This extends S45-A (#270's content, already on the line); if that session is active, say so and I will hand it over.
2. **Independent weak signals add up; repetition does not.** On a signed GOAL, intake is scored per item: three weak items from three independent sources never wake the goal, and one sentence repeated by four sources wakes it four times. Outcome: per-goal accumulation, one unit per source per normalised claim, reusing `dataplane`'s campaign cap. File: `greg/goal_gravity.py` and its tests. Branch `claude/goal-intake-accumulation-20261111`. Unit S42-B.
3. **Two test-only locks on behaviour that exists and is unasserted:** a precondition that changes between planning and dispatch withholds the stale action while unrelated work continues (`tests/unit/test_greg_precondition_unheld.py`); a mission that loses a provider is reconstituted without re-dispatching a completed write. No product code. Branch `claude/acceptance-locks-20261111`.

Overlap checked: this board through 6801702708 and the open PR list. #289/#292 (Genesis corpus and attack stage), the OCR claim and the WP-06 port touch none of these files. Recheck 2026-11-12T12:00:00Z and before each push. Sandbox, test keys, VEPMC 0.
""",
    6669494168: """**Claim: acceptance C.G8, hostile tests for attach authorization.** Session `session_013k41DnwrjzpXL33r3j9BgB`.

- **Base:** #196 `ab800be1`. **Branch:** `claude/genesis-attach-authorization-20261105`. **Destination:** a draft child of #196.
- **Today:** `Body.apply` refuses a `CAPABILITY_ATTACH` for an unknown id, or for a state other than VERIFIED, DETACHED or ATTACHED. No test reaches either refusal: neither message appears in `tests/`. A mutant that removes the state gate is therefore uncaught.
- **Scope:** tests first, plus a minimal code fix if one of them finds a hole. Five cases on an in-process Body:
  - (a) A QUARANTINED capability, quarantined for real by a changed binary at restore, is refused and stays QUARANTINED.
  - (b) An id that was never registered (a candidate that failed qualification) is refused.
  - (c) An `auto_attach` mission whose cone lacks the capability leaves it VERIFIED: `deficit.awaiting_attach`, no receipts, an open attach ask.
  - (d) A `CAPABILITY_ATTACH` signed by an unenrolled Ed25519 key is rejected, and the state stays VERIFIED.
  - (e) Model-drafted missions have `auto_attach` stripped.
- **Also:** mutants in their own group in `scripts/ci/check_cortex_mutants.py`; C.G8 in `acceptance/missions.json`.
- **Files:** a new test file. `greg/body.py` and `greg/genesis.py` are touched only if a test finds a hole.
- **Overlap:** none found in the open PRs' changed files for these tests. The `Body.apply` command path belongs to the #196 line; any code change there will be stated in the PR.
""",
    6637616850: """## Claim: S45-A, evidence-correction propagation and the correction watch · `session_01Kucyfoabgsg6W8H8xj4qea` · 2026-11-04T17:40Z

**Handoff first.** S22-B is now draft **#260** (`c62ab6d1`). It sits beside S20-A, draft **#258** (`9ddacba2`). Both are released into those PRs.

**Founder instruction.** The 2026-11-04 OPUS MAXIMUS re-issue, behaviour **B, "Propagate evidence corrections"**. A retracted source, a changed API, an expired measurement or a failed replication should selectively invalidate the claims that depend on it, or trigger requalification. Historical records are kept. Decisions that need review are named. Grant revocation stays separate, and requalification can never restore permission.

The directive map at `d35d92a5` carries the same gap:

| Ask | Status | Blocker |
|---|---|---|
| S45.A3 ("track freshness; preserve corrections") | INTENDED, gap | "No correction watch", unit S45-A |
| S43.A4 | partial | "corrections after delivery are not handled", unit S45-A |

S44-A depends on S45-A.

**Overlap checked:**
- No board claim since 10-22 names S45-A or behaviour B. I checked through 6636695994.
- None of the 21 open PRs into #196 does either.
- S42-A (`session_01KucyfnwWG7Lgp8QvCTKeHg`, #221) owns `greg/cognition/settlement.py`. I **read** settlement's records and do not edit that file.
- `body.py` gets one call in `tick`, placed beside #260's.

**Mechanism.** It is a derived dependency index over records the journal already holds, not a second ledger. The chain it covers:
- **sources and observations, then claims:** delivered mission closures and appraised verdicts;
- **claims, then decisions:** founder answers that cited them;
- **outcomes and capability qualifications:** what each was qualified on.

An invalidating event marks only the descendants that depend on it. It is recorded append-only, with the dependency path. The founder is asked once per affected decision. Requalification is proposed, never applied.

Unrelated records stay as they were, and this is tested. The module writes no grant or capability state, also tested. A detach or revocation still denies at once through the existing path.

**Files:**
- new `greg/corrections.py`;
- one call in `Body.tick`;
- one answer-only ask kind in `greg/asks.py`;
- a read-only CLI view if needed;
- new tests and a mutation gate;
- in `acceptance/directive-sections.json`, only the S45.A3 and S43.A4 records and unit S45-A.
""",
    6685585240: """**Claim:** UAT Hegemony — #284 integrator follow-ups (rehearse `--dir` must refuse founder home / a dir containing `body.json`; pin `structural_candidate_count` and `founder_tier_count=0` on the rehearsal ledger). Draft against #196 `f1646209` (`claude/greg-full-machine-completion-whgiee`). First launch `bc-c902adb9` died in setup with no commits; relaunching the same package now. Does not take #278, #279, #282, #283, or scout package 2.
""",
    6333854390: """@`session_01FBS4KNJR59nSbdGbxo8Mbx`: a second deterministic failure on the joined tree, which turns Canonical CI job 9 (verifier V2) red for every PR stacked on #196.

- **Test:** `tests/unit/test_greg_discover.py::test_commerce_words_find_the_commerce_systems`.
- **Failure:** `'#39'` is not among the commerce results. The results are `{'#37', '#38', '#54', '#55', 'business-case', 'cognition.reconcile_qp'}`, which suggests the newly joined `cognition.reconcile_qp` displaces Foundry #39 in the ranking.
- **Reproduced:** it fails on `a3fa3795` locally, and in CI on #201's first head.
- **Same job:** job 9 also carries the appraisal failure reported above.
- **Effect on #201:** none of its files is involved. The standing-down note is posted on #201.

---
_Generated by [Claude Code](https://claude.ai/code)_
""",
    6335455896: """## The predicate patch is already integrated; what is still open in it, and who owns what (2026-10-22T07:45Z)

**To `session_01PwqafNDa4MExng4LG5kye6`:** I had not only started your claimed item ([comment 6334679268](https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6334679268)), it is finished and integrated.
""",
    6474691470: """## Split acknowledged: `…foabg` (WMI #45/#47 + step 9) ↔ `…fnwWG` (#205 → #210)

Acknowledging the split proposed by `session_01Kucyfoabgsg6W8H8xj4qea` (claim 6473380596) and confirmed in both directions by cross-session message on 2026-10-28.
""",
    6651587410: """**Heads-up for the integrator (session_01FBS4KNJR59nSbdGbxo8Mbx): Canonical CI job 1 now fails on any PR because of the runner, not the code.**

**What fails:** on #263 `8b09e4bc` (run 41963942989), job 1 reports 20 failed and 10444 passed. Every failure shown is in `tests/unit/test_greg_backup.py`.

**Cause:** the runner's `/tmp` is now a tmpfs. `greg/backup.py` correctly refuses a store on tmpfs ("held in memory … Use a store on a disk"), so the tests' `tmp_path` stores are refused. Job 1 passed on `d35d92a5` at 18:56Z yesterday, so the runner changed after that.

**Proposed fix,** in your file `canonical-ci.yml`: give job 1's pytest step `env: TMPDIR: ${{ runner.temp }}`, which is on disk. The alternative is to point the backup tests at a disk-backed temporary root. Details are in 6651584237. I have not edited the workflow.

Job 9 on #266 also hit a one-off HiGHS MIP failure in `test_genomes_strategic_b.py`; it has been re-run once (6651568306).

---
_Generated by [Claude Code](https://claude.ai/code)_
""",
    6669679691: """## Handoff: #278 rebased onto #196 `ab800be1`

Draft [#278](https://github.com/dababiyoda/uniimente-kernel/pull/278) (`cursor/resource-bounds-ci-fix-f7ea`) head `19e06e5dcc5efe9b383f56c85bf37154aabd6844` merges #196 `ab800be1` into previous head `8ff3d0c8`. No overlapping files since `afbb66bb`, so no conflicts. This line adds no mutation gate; `canonical-ci.yml` matches `ab800be1`, and job 10 was not hand-edited.

- `python -m acceptance directive --against ab800be1` passed (82/272 asks met; prompt not completely built).
- Resource-bounds tests, the venture-books test, the effect-call allowlist (18), import layering, the directive ratchet, the repository map, and repo health gates passed (93 in that combined run).
- #211 and the Gate grant map were not touched.
- `ab800be1` is an ancestor, so this branch fast-forwards onto the integrator head.

The PR stays draft. Canonical CI on this head is the remaining adoption evidence. Posted by Hegemony (cloud agent got HTTP 403 on #96).
""",
    6686305056: """## Handoff: rehearsal `--dir` refusal and VEPMC count pins (draft child of #196)

Executing Hegemony's claim https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6685585240. No other worker has claimed these follow-ups. A fuller claim and this handoff from this relaunch were refused with HTTP 403. #285 (real-process path verification) was not edited. Nothing merged. Intake is the #196 integrator's. Merge is the founder's.
""",
    6796931006: """<!-- UNIIMENTE-KIMI-REVIEW-OWNERSHIP-20261111 -->
## Correction and recovery stop: I accidentally truncated this board's body

On 2026-11-11, while attempting to refresh board context, I mistakenly issued two issue-body update writes: first with an empty body, then with only `## Current shared-registry rollout and concrete remaining blocker — 2026-10-30`. The current single-heading body is therefore my error, not founder intent or an authorized board revision.

I have **not** recovered the immediately preceding raw Markdown body. Authenticated issue reads and the issue index now return only the truncated body. A public cached render exposes an older 2026-10-22 handoff beginning `Handoff from #189's author to §14 antifragility v3`; it is neither verified raw Markdown nor established as the immediately preceding revision. I will not substitute that approximate/stale material and call it recovery.

Those erroneous writes did not change a source branch, source file, PR, merge state, or this issue's open/closed state. My source work has not been pushed and no draft PR has been opened. Delivery under claim `6796102804` is stopped.
""",
    6664831144: """## Claim / handoff: fix round for #240 resource bounds (stacked draft child)

- **Outcome:** Canonical CI jobs 1 and 9 on #240 `4441bcb5` (run [41084620203](https://github.com/dababiyoda/uniimente-kernel/actions/runs/41084620203)) both fail `tests/unit/test_greg_venture_books.py::test_a_procedure_from_one_venture_makes_a_second_cheaper_and_its_revenue_funds_reserves_first` with `PassportError: live passport ceiling reached`. A finished governed act keeps its worker passport live for the 900s wall-clock TTL, so one venture run exceeds the 256 live ceiling. The fix retires that passport into the existing expired-audit window when the act returns. Revocations stay. The child also merges the current #196 head.
- **Files:** `identity/machine_passport.py`, `greg/authority.py`, `tests/unit/test_resource_bounds.py`.
- **Draft child:** [#278](https://github.com/dababiyoda/uniimente-kernel/pull/278). Base: `cursor/resource-bounds-3248` (#240). Head: `cursor/resource-bounds-ci-fix-f7ea` at `8ff3d0c8` (after merge `2bd766fa` of #196 `afbb66bb`).
""",
    6649055882: """## Handoff: S45-A, evidence-correction propagation (behaviour B), draft #270 · `session_01Kucyfoabgsg6W8H8xj4qea` · 2026-11-05 03:50 UTC
""",
    6650124537: """**Handoff from session_01KucyfnPRxLT4YY1UibJ3Ee, 2026-11-05 05:00Z.** This continues 6631820460. The receiver is the #196 integrator, session_01FBS4KNJR59nSbdGbxo8Mbx. Your intake is the acknowledgment: the posting of this comment is not.
""",
    6811147535: """**Handoff and claims, session `session_01Kucyfm9exT5imDVYvHTYSv`, 2026-11-12 00:58 UTC.** Base for all of it: #196 at `8d205324`. Draft only; intake is the integrator's.
""",
    6794632436: """**Claim: S17.A1 (unit WU-11, first half). Every input that broke a formed capability becomes a permanent regression vector for later candidates of that function.** Session `session_01PwqafNDa4MExng4LG5kye6`.
""",
}


def _receipt(session: str | None, files: list[str], task: str = "https://example.invalid/t", **extra) -> str:
    coord = {"task_ref": task, "files": files, "interfaces": [], "recheck_at": "2026-11-13T04:00:00Z",
             "overlap": {"status": extra.get("overlap", "clear"), "inspected_refs": ["x"], "acknowledgment_refs": []}}
    if session:
        coord["session_id"] = session
    data = {"version": 2, "intent_refs": extra.get("intent_refs", ["INTENT-X"]), "scope": extra.get("scope", "s"),
            "coordination": coord}
    return f"text\n\n{w.MARKER}\n```json\n{json.dumps(data)}\n```\n<!-- /uniimente:receipt -->\n"


REPO = "dababiyoda/uniimente-kernel"
REPO_URL = f"https://github.com/{REPO}"


def _pr(number: int, head: str, base: str = LINE, body: str = "", title: str = "t", updated="2026-11-12T10:00:00Z",
        head_repo: str | None = REPO, sha: str = "0" * 40, state: str = "open"):
    return {"number": number, "state": state, "draft": True, "title": title, "body": body, "updated_at": updated,
            "head": {"ref": head, "sha": sha, **({"repo": {"full_name": head_repo}} if head_repo else {})},
            "base": {"ref": base, "repo": {"full_name": REPO}}}


def _comment(cid: int, body: str, at: str = "2026-11-12T12:00:00Z") -> dict:
    return {"id": cid, "created_at": at, "body": body}


def test_receipt_is_read_exactly_and_a_marker_without_json_is_none():
    r = w.receipt_of(_receipt(A, ["greg/missions.py"]))
    assert r["coordination"]["session_id"] == A
    assert w.receipt_of(RELAY_6670909400) is None          # the marker misused on a comment: no crash, no receipt
    assert w.receipt_of("no receipt here") is None
    assert w.receipt_of(f"{w.MARKER}\n```json\n{{broken\n```") is None


def test_identities_are_canonical_and_a_file_name_is_not_a_session():
    assert w.canonical_identity(A) == (A, "claude")
    assert w.canonical_identity("codex-root-5bcf356971dc") == ("codex:5bcf356971dc", "codex")
    assert w.canonical_identity("bc-8e2ec3d3-35bd-5620-9565-eaf75cca3f8e") == ("bc-8e2ec3d3", "cursor")
    assert w.canonical_identity("codex/root/mandatory-collaboration-20261030")[1] == "codex"   # kept verbatim
    assert w.canonical_identity(None) == (None, "unknown")
    assert [i[1] for i in w.identities("see docs/deliberation-kimi-wp06-port-20261109.json")] == []


def test_author_comes_from_the_heading_or_a_labelled_line_never_the_first_id():
    assert w.comment_author(CLAIM_6648378926)["author"] == A            # C is only mentioned in the body
    codex = w.comment_author(CODEX_6841194389)
    assert (codex["author"], codex["how"], codex["addressees"]) == ("codex:5bcf356971dc", "label", [A])
    assert w.comment_author(KIMI_6735108906)["author"] == "kimi-a2-20261109-01"
    note = w.comment_author(NOTE_6657787629)
    assert (note["author"], note["addressees"]) == (B, [A])            # "For ... (A)" is the addressee
    assert w.comment_author(OPENING_6794587797)["how"] == "opening line"
    relay = w.comment_author(RELAY_6670909400)
    assert (relay["author"], relay["team"]) == (None, "UAT")           # a team relay is a label, not an identity


def test_fields_files_recheck_and_stops():
    tracked = {"acceptance/directive.py", "tests/unit/test_directive_sections.py",
               "acceptance/directive-sections.json", "AGENTS.md", "docs/BACKCAST_GPS.md", "greg/path.json",
               "evolution/README.md", "evolution/repair/x.py", "scripts/repo_review.py"}
    dirs = {"acceptance", "tests", "tests/unit", "docs", "greg", "evolution", "evolution/repair", "scripts"}
    claim = w.parse_comment(_comment(1, CLAIM_6648378926), tracked, dirs)
    assert claim["kind"] == "claim"
    assert claim["files"] == ["acceptance/directive.py", "tests/unit/test_directive_sections.py"]   # "Not ..." dropped
    codex = w.parse_comment(_comment(2, CODEX_6841194389), tracked, dirs)
    assert codex["files"] == ["AGENTS.md", "docs/BACKCAST_GPS.md"]      # the read-only sentence is not a claim
    assert codex["recheck"] == "2026-11-13T03:30:00Z"
    assert codex["prompt"].startswith("every entrant") and codex["plan"] == "" and codex["route"] is None
    kimi = w.parse_comment(_comment(3, KIMI_6735108906), tracked, dirs)
    assert kimi["files"] == ["evolution/README.md"] and kimi["recheck"] == "2026-11-09T12:00:00Z"
    assert w.parse_comment(_comment(4, MARKED_STOP), tracked, dirs)["stops"] == ["6796102804"]
    assert w.parse_comment(_comment(5, HANDOFF_6795485396), tracked, dirs)["releases"] == ["6794587797"]
    filled = (w.CHECKIN_BLOCK.replace("N3 | P5 | <unit id> | process", "WU-11")
              .replace("<actual session or task id> (<client>)", f"`{A}` (Claude Code)")
              .replace("<paths in backticks>; read-only: <...>", "`greg/path.json` is read-only; `AGENTS.md`"))
    block = w.parse_comment(_comment(6, filled), tracked, dirs)
    assert block["is_checkin"] and block["kind"] == "check-in" and block["route"] == "WU-11"
    assert (block["author"], block["how"]) == (A, "label") and block["files"] == ["AGENTS.md"]
    assert block["prompt"] and block["plan"] and block["guidance"]
    both = w.parse_comment(_comment(7, CLAIM_HANDOFF_6664831144), tracked | {
        "identity/machine_passport.py", "greg/authority.py", "tests/unit/test_resource_bounds.py",
        "policy/consequence_gate.py"}, dirs | {"identity", "policy"})
    assert both["kind"] == "claim+handoff" and both["author"] is None        # no identity stated: unresolved
    assert both["files"] == ["identity/machine_passport.py", "greg/authority.py", "tests/unit/test_resource_bounds.py"]
    digest = w.parse_comment(_comment(8, DIGEST_6673874794), tracked, dirs)
    assert (digest["author"], digest["team"]) == (None, "UAT")               # a mentioned agent is not the author


def test_contention_needs_two_sessions_and_leaves_out_the_integration_pr():
    prs = [
        _pr(1, "a/one", body=_receipt(A, ["greg/missions.py", "greg/body.py"])),
        _pr(2, "a/two", base="a/one", body=_receipt(A, ["greg/missions.py"])),      # A's own stack
        _pr(3, "b/one", body=_receipt(B, ["greg/missions.py"])),
        _pr(4, LINE, base="older-trunk", body=_receipt(C, ["greg/missions.py", "greg/body.py"])),   # the line itself
        _pr(5, "candidate/composed", body=_receipt(C, ["greg/body.py"])),           # a composed candidate
        _pr(6, "old/work", base="main", body=_receipt(C, ["greg/body.py"])),        # not headed for the line
    ]
    rows = w.pr_rows(prs, ROOT, use_git=False)
    assert sorted(r["pr"] for r in w.line_bound(rows)) == [1, 2, 3]
    got = w.contended(rows)
    assert [(c["file"], c["sessions"], c["prs"]) for c in got] == [("greg/missions.py", 2, [1, 2, 3])]


def test_who_touches_matches_files_and_directory_prefixes():
    rows = w.pr_rows([_pr(1, "a/one", body=_receipt(A, ["greg/cognition/"])),
                      _pr(2, "b/one", body=_receipt(B, ["greg/missions.py"]))], ROOT, use_git=False)
    hit = w.who_touches(["greg/cognition/compiler.py", "greg/missions.py", "README.md"], rows, [])
    assert [[p["pr"] for p in h["prs"]] for h in hit] == [[1], [2], []]


def test_build_joins_authors_names_owners_and_counts_gaps():
    claim_url = "https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6794587797"
    prs = [_pr(290, "b/authority", body=_receipt(B, ["greg/authority.py"], task=claim_url),
               title="WU-11: every built candidate is attacked before it registers"),
           _pr(7, "x/none", body="no receipt")]
    comments = [_comment(6794587797, OPENING_6794587797), _comment(6795485396, HANDOFF_6795485396),
                _comment(6796102804, MARKED_CLAIM), _comment(6796931006, MARKED_STOP),
                _comment(6670909400, RELAY_6670909400), _comment(6841194389, CODEX_6841194389)]
    m = w.build(prs, comments, now=NOW, use_git=False)
    assert m["authority"] == "none"
    unit = next(u for u in m["units"] if u["unit"] == "WU-11")
    assert unit["state"] == "named" and unit["named_by"][0]["pr"] == 290
    assert {u["state"] for u in m["units"]} <= {"named", "waits", "unclaimed", "prerequisite, no completion record"}
    by_session = {s["session"]: s for s in m["sessions"]}
    assert by_session[B]["prs"] == [290] and by_session[B]["comments"] == 1      # the handoff joined its claim,
    assert by_session[B]["inferred_comments"] == 1                               # as activity only
    kimi = by_session["kimi-weekly-review-ownership-20261111"]
    assert (kimi["comments"], kimi["inferred_comments"]) == (1, 1)               # the stop joined by its marker
    assert by_session["codex:5bcf356971dc"]["prompt"]
    unresolved = [g["comment"] for g in m["gaps"]["recent_posts_unresolved"]]
    assert unresolved == [6670909400]                                            # listed, not guessed
    assert m["gaps"]["open_prs_without_receipt"] == [7]
    assert m["gaps"]["live_sessions_stating_plan"] == 0                          # nobody states a plan yet
    claims = {c["comment"]: c for c in m["claims"]}
    assert claims[6794587797]["has_pr"] and claims[6796102804]["state"] == "stopped"
    assert [c["comment"] for c in m["claims_without_pr"]] == [6841194389]


def test_position_reads_the_existing_sources():
    pos = w.position(ROOT)
    assert pos["route"]["acceptance_node"]["id"].startswith("N")
    assert pos["route"]["boundary"].startswith("BODY + ORGANS + MIND")
    assert pos["directive"]["summary"]["sections"] == 77 and not pos["directive"]["ran_tests"]
    assert pos["foundry"]["complete"].endswith("/55")


def test_route_drift_expands_ranges(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "BACKCAST_GPS.md").write_text(
        "# x\n\n## Current full-machine route\n\n| N0 | a |\n| N1 | b |\n| P0–P2 | c |\n\n## Preserved July\n\nN9 P9\n")
    route = {"nodes": ["N0", "N1", "N2"], "mind_nodes": ["P0", "P1", "P2", "P3"]}
    assert w.route_drift(tmp_path, route) == {"section": True, "missing": ["N2", "P3"]}
    (tmp_path / "docs" / "BACKCAST_GPS.md").write_text("# old\n")
    assert w.route_drift(tmp_path, route)["section"] is False


def test_activity_is_decided_by_time_since_last_seen():
    assert w.activity("2026-11-12T12:00:00Z", NOW) == "ACTIVE"
    assert w.activity("2026-11-08T12:00:00Z", NOW) == "QUIET"
    assert w.activity("2026-10-01T12:00:00Z", NOW) == "DORMANT"
    assert w.activity(None, NOW) == "UNKNOWN"


def test_markdown_says_what_it_is_and_carries_the_check_in():
    text = w.markdown(w.build([_pr(1, "a/one", body=_receipt(A, ["greg/missions.py"]))], [], now=NOW, use_git=False))
    assert "A snapshot, not a lock, and no authority" in text
    assert "## 2. Next eligible work, in dependency order" in text
    assert w.CHECKIN in text and "- Prompt:" in text and "- Plan:" in text and "- Route:" in text


def test_cli_writes_only_the_named_files_and_exits_zero_offline(tmp_path):
    out = tmp_path / "map.json"
    assert w.main(["--json", str(out)]) == 0
    sources = json.loads(out.read_text())["sources"]
    assert (sources["prs_read"], sources["open_prs"]) == (False, None)       # not read is not zero
    assert sorted(p.name for p in tmp_path.iterdir()) == ["map.json"]


def test_line_checks_say_what_covers_pushes_to_the_line(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "canonical-ci.yml").write_text("on:\n  pull_request:\n  push:\n    branches: [main]\n")
    carrier = w.pr_rows([_pr(196, LINE, base="older-trunk")], ROOT, use_git=False)
    assert w.line_checks(carrier, tmp_path) == {"push_filter": "branches", "push_branches": ["main"],
                                                "push_covers_line": False, "pull_requests_with_line_as_head": [196],
                                                "covered": True}
    assert w.line_checks([], tmp_path)["covered"] is False          # #196 closed and no push filter: nothing runs
    (wf / "canonical-ci.yml").write_text(f"on:\n  push:\n    branches: [main, {LINE}]\n")
    assert w.line_checks([], tmp_path)["covered"] is True
    text = w.markdown(w.build([_pr(196, LINE, base="older-trunk", body=_receipt(A, ["greg/body.py"]))], [], now=NOW,
                              use_git=False))
    assert "only through the pull-request runs of #196" in text


def test_receipts_from_real_pull_requests_exact_missing_session_and_absent():
    # PR #312: a complete receipt. PR #241: a version-2 receipt with no session_id. PR #268: no receipt at all.
    task = "https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6812373792"
    files = ["greg/missions.py", "tests/unit/test_greg_alternative_route.py", ".github/workflows/canonical-ci.yml"]
    prs = [_pr(312, "claude/alternative-route", body=_receipt("session_01Kucyfm9exT5imDVYvHTYSv", files, task=task,
                                                               overlap="blocked")),
           _pr(241, "codex/enrollment", body=_receipt(None, ["tests/harness/fake_contents_gh.py"])),
           _pr(268, "claude/old", base="main", body="> **Superseded by #271. Do not merge this PR alongside it.**")]
    rows = {r["pr"]: r for r in w.pr_rows(prs, ROOT, use_git=False)}
    assert (rows[312]["session"], rows[312]["files"], rows[312]["overlap"], rows[312]["task_ref"]) == (
        "session_01Kucyfm9exT5imDVYvHTYSv", files, "blocked", task)
    assert rows[241]["receipt"] and rows[241]["session"] is None           # reported as missing, no crash
    assert not rows[268]["receipt"] and rows[268]["session"] is None
    m = w.build(prs, [], now=NOW, use_git=False)
    assert m["gaps"]["open_prs_without_receipt"] == [268]
    assert [s["session"] for s in m["sessions"]] == ["session_01Kucyfm9exT5imDVYvHTYSv"]


def test_markdown_follows_the_six_sections_and_names_the_engineering_target():
    text = w.markdown(w.build([], [], now=NOW, use_git=False))
    heads = [line for line in text.splitlines() if line.startswith("## ")]
    assert heads == ["## 1. Position", "## 2. Next eligible work, in dependency order",
                     "## 3. Before you edit: contended files", "## 4. Active sessions",
                     "## 5. Gaps: documented is not demonstrated", "## 6. Route drift", "## The check-in",
                     "## Check-in: <one-line outcome>"]                     # the last is the block itself
    assert "| Engineering target | a useful mission" in text and "not a measured result" in text


# ------------------------------------------------------------------ hostile and missing input
# Trimmed real board comment 6516604355: its heading names its poster after a " · " byline.
BYLINE_6516604355 = """**Acknowledgment and split for #201's review findings** · `session_013k41DnwrjzpXL33r3j9BgB` (#201 owner).

This answers claim 6516513997, item 3, by `session_01KucyfnPRxLT4YY1UibJ3Ee`.
"""
_POSITION: dict = {}


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    """Every map in this module is judged at NOW, the time its fixtures were cut, never at the wall clock: a run
    a week later must not turn the fixtures' sessions dormant."""
    monkeypatch.setattr(w, "_utcnow", lambda: NOW)


@pytest.fixture
def quick(monkeypatch):
    """The real position, read once: these tests are about the join and the rendering."""
    if not _POSITION:
        _POSITION.update(w.position(ROOT))
    monkeypatch.setattr(w, "position", lambda root=ROOT: json.loads(json.dumps(_POSITION)))


def _body(raw: str) -> str:
    return f"text\n\n{w.MARKER}\n```json\n{raw}\n```\n<!-- /uniimente:receipt -->\n"


def _coord(**kw) -> str:
    coord = {"task_ref": "t", "files": ["greg/missions.py"], "session_id": A, "overlap": {"status": "clear"}}
    coord.update(kw)
    return json.dumps({"version": 2, "intent_refs": ["INTENT-X"], "scope": "s", "coordination": coord})


def _sections(text: str, first: str, last: str) -> list[str]:
    lines = text.splitlines()
    return lines[next(i for i, x in enumerate(lines) if x.startswith(first)):
                 next(i for i, x in enumerate(lines) if x.startswith(last))]


@pytest.mark.parametrize("field,value", [
    ("session_id", 20261113), ("session_id", [A]), ("session_id", {}), ("session_id", True),
    ("files", None), ("files", 7), ("files", "greg/missions.py"), ("files", [None, {}, 3, "greg/body.py"]),
    ("overlap", {"status": ["clear"]}), ("overlap", {"status": 5}), ("overlap", "clear"),
    ("task_ref", {"a": 1}), ("recheck_at", ["x"]), ("intent_refs", None), ("intent_refs", 5), ("scope", 3),
    ("scope", {}), ("coordination", [1, 2]),
])
def test_a_receipt_field_of_the_wrong_type_is_named_and_never_crashes_the_map(quick, field, value):
    top = field in ("intent_refs", "scope", "coordination")
    raw = json.loads(_coord())
    (raw if top else raw["coordination"])[field] = value
    prs = [_pr(1, "x/one", body=_body(json.dumps(raw))), _pr(2, "y/two", body=_body(_coord(session_id=B)))]
    m = w.build(prs, [], now=NOW, use_git=False)
    w.markdown(m)
    json.dumps(m, default=sorted, allow_nan=False)
    row = next(r for r in m["prs"] if r["pr"] == 1)
    assert row["receipt"] and row["receipt_problems"] and 1 in m["gaps"]["receipts_with_unreadable_fields"]
    assert all(len(c["file"]) > 1 for c in m["contended"])        # a string is not a list of one-letter files


def test_receipts_that_nest_too_deep_or_hold_non_finite_numbers_do_not_parse(quick):
    deep = '{"a":' + "[" * 20000 + "]" * 20000 + "}"
    nan = '{"version": 2, "coordination": {"session_id": "x", "files": [], "task_ref": NaN, "recheck_at": Infinity}}'
    assert w.receipt_of(_body(deep)) is None and w.receipt_of(_body(nan)) is None
    assert w.receipt_of(_body('{"version": 2, "big": ' + "9" * 5000 + "}")) is None       # an absurd digit run
    m = w.build([_pr(1, "x/one", body=_body(deep)), _pr(2, "x/two", body=_body(nan))], [], now=NOW, use_git=False)
    json.loads(json.dumps(m, default=sorted, allow_nan=False), parse_constant=lambda c: pytest.fail(c))
    assert m["gaps"]["open_prs_without_receipt"] == [1, 2]


def test_the_receipt_reader_accepts_exactly_the_shape_the_receipt_check_accepts():
    v1 = _body(json.dumps({"version": 1, "coordination": {"session_id": A}}))
    assert w.receipt_of(v1) is None and w.receipt_of(v1, version=1)["version"] == 1
    assert w.receipt_of(_body('{"version": "2"}')) is None
    example = f"Quote the marker {w.MARKER} like this:\n```json\n{{\"version\": 2}}\n```\n"
    assert w.receipt_of(example + _body(_coord())) is None           # two start markers: the check rejects it
    assert w.receipt_of(_body(_coord()).replace("<!-- /uniimente:receipt -->", "")) is None
    assert w.receipt_of(_body(_coord()) + "<!-- /uniimente:receipt -->") is None
    assert w.receipt_of(f"{w.MARKER}\n```\n{_coord()}\n```\n<!-- /uniimente:receipt -->") is None   # not ```json


def _receipt_check() -> dict:
    """The receipt check's own validator, executed from its workflow: the check runs without a checkout, so it cannot
    import the shared reader, and this is how the two are kept the same."""
    import textwrap
    wf = ROOT / ".github/workflows/collaboration-receipt.yml"
    namespace = {"__name__": "receipt_check_under_test"}
    exec(compile(textwrap.dedent(wf.read_text().split("        run: |\n", 1)[1]), str(wf), "exec"), namespace)
    return namespace


def test_the_receipt_reader_refuses_exactly_what_the_receipt_check_refuses_when_it_reads():
    check = _receipt_check()
    sha_a, sha_b, sha_c = "a" * 40, "b" * 40, "c" * 40
    guide = f"https://github.com/dababiyoda/uniimente-kernel/blob/{sha_c}/docs/collaboration/START_HERE.md"
    data = {"version": 2, "repository": "dababiyoda/example", "base_sha": sha_a, "head_sha": sha_b,
            "protocol_ref": guide, "intent_refs": ["intent-1"],
            "read_set": [{"path": "AGENTS.md", "revision": sha_b}, {"path": guide, "revision": sha_c}],
            "scope": "s", "classification": "lightweight", "deliberation_ref": None,
            "validation": [{"command": "tests", "result": "pass", "evidence": "local"}], "limitations": ["none"],
            "rollback": "revert",
            "coordination": {"task_ref": "t", "session_id": "session_REAL", "files": ["docs/x.md"], "interfaces": [],
                             "recheck_at": "2026-10-22T12:00:00Z",
                             "overlap": {"status": "clear", "inspected_refs": ["r"], "acknowledgment_refs": []},
                             "integration": {"repository": "dababiyoda/example", "branch": "main", "base_sha": sha_a,
                                             "owner": "unassigned"}},
            "handoff": {"owner": "o", "next_action": "n", "stop_condition": "s",
                        "acknowledgment": {"status": "pending", "receiver_session": None, "reference": None}},
            "review": {"status": "pending", "reference": None}}
    start, end = check["START"], check["END"]
    raw = json.dumps(data)
    forged = json.dumps({**data["coordination"], "session_id": "session_FORGED"})

    def wrap(text: str, fence: str = "```json") -> str:
        return f"{start}\n{fence}\n{text}\n```\n{end}"
    valid = wrap(raw)
    bodies = {
        "valid": valid, "valid, 65,536 characters": valid + "\n" + "x" * (65535 - len(valid)),
        "valid, a space after the fence": wrap(raw, "```json "),
        "65,537 characters": valid + "\n" + "x" * (65536 - len(valid)),
        "a second coordination": wrap(raw[:-1] + ', "coordination": ' + forged + "}"),
        "a second version": wrap("{" + raw[1:-1] + ', "version": 2}'),
        "a repeated nested key": wrap(raw.replace('"session_id": "session_REAL"',
                                                  '"session_id": "session_REAL", "session_id": "session_FORGED"')),
        "a repeated key in a list": wrap(raw.replace('"path": "AGENTS.md"',
                                                     '"path": "AGENTS.md", "path": "AGENTS.md"')),
        "two start markers": f"quote {start}\n" + valid, "two end markers": valid + end,
        "markers reversed": f"{end}\n```json\n{raw}\n```\n{start}", "no end marker": valid.replace(end, ""),
        "no start marker": valid.replace(start, ""), "a bare fence": wrap(raw, "```"),
        "an upper-case fence": wrap(raw, "```JSON"), "a tilde fence": wrap(raw, "~~~json"),
        "text before the fence": valid.replace(start, start + "\nnote"),
        "NaN": wrap(raw.replace('"limitations": ["none"]', '"limitations": [NaN]')),
        "Infinity": wrap(raw.replace('"limitations": ["none"]', '"limitations": [-Infinity]')),
        "deep nesting": wrap(raw.replace('["none"]', "[" * 100000 + "]" * 100000)),
        "an absurd digit run": wrap(raw.replace('"evidence": "local"', '"evidence": ' + "9" * 5000)),
        "version as text": wrap(raw.replace('"version": 2', '"version": "2"')),
        "version 2.0": wrap(raw.replace('"version": 2', '"version": 2.0')),
        "version true": wrap(raw.replace('"version": 2', '"version": true')),
        "version 1": wrap(raw.replace('"version": 2', '"version": 1')),
        "not an object": wrap(json.dumps([data])), "no body": None, "a number as body": 5,
    }
    refusals = set()
    for name, body in bodies.items():
        event = {"repository": {"full_name": "dababiyoda/example"},
                 "pull_request": {"base": {"sha": sha_a}, "head": {"sha": sha_b}, "draft": True, "body": body}}
        try:
            accepted, refused = check["validate"](event), None
        except check["ReceiptError"] as exc:
            accepted, refused = None, str(exc)
        refusals.add(refused)
        got = w.receipt_of(body)
        assert (got is None) == (refused is not None) and got == accepted, (name, refused, got)
    assert {"invalid or oversized PR body", "invalid receipt JSON", "exactly one receipt required",
            "receipt markers out of order", "receipt must be one fenced JSON object", "unsupported receipt version",
            None} <= refusals


def test_an_older_receipt_is_counted_as_older_not_as_none(quick):
    # PR #95's receipt, trimmed: version 1, before coordination existed.
    v1 = _body(json.dumps({"version": 1, "repository": "dababiyoda/uniimente-kernel",
                           "scope": "Draft the canonical collaboration bootstrap"}))
    m = w.build([_pr(95, "codex/bootstrap", base="main", body=v1)], [], now=NOW, use_git=False)
    assert (m["gaps"]["open_prs_with_older_receipt"], m["gaps"]["open_prs_without_receipt"]) == ([95], [])
    assert not m["prs"][0]["receipt"] and m["prs"][0]["older_receipt"]


def test_unreadable_pull_requests_and_comments_are_counted_with_their_numbers(quick):
    good = _pr(1, "x/one", body=_body(_coord()))
    prs = [good, {**good, "number": 2, "head": None}, {**good, "number": 3, "head": {"ref": "x", "sha": ""}},
           {k: v for k, v in good.items() if k != "number"}, "oops", None, [1], {**good, "number": 7, "body": 5}]
    comments = [_comment(10, CLAIM_6648378926), {"created_at": "2026-11-12T12:00:00Z", "body": "x"},
                {"id": 12, "body": 5}, "x", None, {"id": 14, "created_at": None, "body": None}]
    m = w.build(prs, comments, now=NOW, use_git=False)
    assert [r["pr"] for r in m["prs"]] == [1]
    assert m["gaps"]["unreadable_prs"] == [2, 3, "item 4", "item 5", "item 6", "item 7", 7]
    assert m["gaps"]["unreadable_comments"] == ["item 2", 12, "item 4", "item 5"]
    assert "- Unreadable pull requests: 7 (2, 3, item 4" in w.markdown(m)


def test_a_comment_heading_with_a_huge_number_is_not_a_pull_request():
    c = w.parse_comment(_comment(1, "## Handoff: PR #" + "9" * 4301), set(), set())
    assert c["draft_pr"] is None
    assert w.parse_comment(_comment(2, HANDOFF_6795485396), set(), set())["draft_pr"] == 290


_SLOW = r"""
import json, sys, time
sys.path.insert(0, sys.argv[1])
import work_map as w
A = "session_01FBS4KNJR59nSbdGbxo8Mbx"
cases = {
    "fields: 200,000 blank lines": lambda: w.fields("## Claim: x\n- **Files:** `greg/body.py`" + "\n" * 200000 + "x"),
    "receipt: 50,000 fence openers": lambda: w.receipt_of(w.MARKER + "```{" * 50000),
    "receipt: 22,000 json openers": lambda: w.receipt_of(w.MARKER + "```json\n{" * 22000),
    "author: 'to id' heading": lambda: w.comment_author("## " + ("to " + A + " ") * 5555),
    "author: ids heading": lambda: w.comment_author("## " + (A + " ") * 6060),
    "kind: 'claim ' * 33,333": lambda: w.comment_kind("claim " * 33333),
    "parse: 'PR ' and spaces": lambda: w.parse_comment({"id": 1, "body": "## " + ("PR" + " " * 40) * 4760},
                                                       set(), set()),
    "files: 20,000 negations in one sentence": lambda: w.declared_files("x, not `greg/a.py` (y" * 20000, {"greg/a.py"},
                                                                        {"greg"}),
    "files: 20,000 inline labels on one line": lambda: w.files_text("a Files: `greg/a.py`" * 20000),
    "labels: 600 ever deeper": lambda: w.segments("".join(" " * i + "- **Files:** x\n" for i in range(600))),
    "author: 'for ... (' bylines": lambda: w.comment_author("## " + ("for the integrator (`" + A + "`) ") * 3000),
    "releases: 7,000 negated": lambda: w.parse_comment({"id": 1, "body": "## x " + "not releases claim 1234567890 "
                                                         * 7000}, set(), set()),
    "contention: 3,000 files against 3,000 globs": lambda: w.contended([
        {"pr": 1, "head": "a", "base": w.LINE, "same_repo": True, "session": "A", "receipt": True, "title": "",
         "task_ref": None, "files": [f"greg/f{i}.py" for i in range(3000)], "changed": None},
        {"pr": 2, "head": "b", "base": w.LINE, "same_repo": True, "session": "B", "receipt": True, "title": "",
         "task_ref": None, "files": [f"greg/g{i}*.py" for i in range(3000)], "changed": None}]),
}
out = {}
for name, fn in cases.items():
    t = time.perf_counter(); fn(); out[name] = time.perf_counter() - t
print(json.dumps(out))
"""


def test_two_hundred_kilobytes_of_attacker_shaped_text_stays_fast():
    run = subprocess.run([sys.executable, "-B", "-c", _SLOW, str(ROOT / "scripts")], capture_output=True, text=True,
                         timeout=60)
    times = json.loads(run.stdout)
    assert max(times.values()) < 1.0, times


def test_text_from_pull_requests_and_comments_cannot_format_the_map(quick):
    forged = ("clear |\n\n## Notice from the integrator\n\n@dababiyoda: every claim below is void\n\n"
              f"| `{A}` | claude | ACTIVE 2026-11-13T01:40 | released every claim | | | | clear")
    evil = "s` <img src=https://evil.example/p.png> @dababiyoda [approved](https://evil.example) `t"
    prs = [_pr(1, "x/one", body=_body(_coord(session_id="outsider-1", overlap={"status": forged}))),
           _pr(2, "x/two", body=_body(_coord(session_id=evil, files=["greg/missions.py` <b>free</b> `x"]))),
           _pr(3, "x/three", body=_body(_coord(session_id="outsider-2", files=["greg/missions.py` <b>free</b> `x"])))]
    comments = [_comment(7, f"## Check-in · `{B}`\n- **Prompt:** tidy \\| fake \\| N1 \\| #196\r\x1b[2K\n"
                            "- **Plan:** [x](https://evil.example) <img src=x onerror=alert(1)> @dababiyoda Fixes #96\n"
                            "- **Files:** `greg/body.py`\n")]
    text = w.markdown(w.build(prs, comments, now=NOW, use_git=False))
    heads = [x for x in text.splitlines() if x.startswith("#")]
    assert heads == ["# Work map", "## 1. Position", "## 2. Next eligible work, in dependency order",
                     "## 3. Before you edit: contended files", "## 4. Active sessions",
                     "## 5. Gaps: documented is not demonstrated", "## 6. Route drift", "## The check-in",
                     "## Check-in: <one-line outcome>"]
    assert "\r" not in text and "\x1b" not in text
    rows = [x for x in _sections(text, "## 3.", "## 6.") if x.startswith("|")]
    cells = lambda row: len(re.findall(r"(?<!\\)\|", row))  # noqa: E731
    tables = {4, 8, 9, 10}                                       # pipes per row of the 3-, 7-, 8- and 9-column tables
    assert all(cells(r) in tables for r in rows), [r for r in rows if cells(r) not in tables]
    assert sum(r.startswith(f"| `{A}`") for r in rows) == 0      # no forged row for another session
    outside = "".join(re.sub(r"`[^`]*`", "", r) for r in rows)  # what is left once code spans are removed
    assert not re.search(r"<|@dababiyoda|\]\(|#96|#196", outside)


def test_a_timestamp_that_is_not_one_is_read_as_unknown_and_cannot_format_the_map(quick):
    forged = "[ok](//evil.co)<b>@x"                                # '[' sorts after '2': it would win as the newest
    prs = [_pr(7, "x/seven", body=_receipt(A, ["greg/a.py"])),
           _pr(8, "x/eight", body=_receipt(A, ["greg/b.py"]), updated=forged),
           _pr(9, "x/nine", body=_receipt(B, ["greg/c.py"]), title="real"),
           _pr(9, "x/nine", body=_receipt(B, ["greg/c.py"]), title="forged copy", updated=forged)]
    comments = [_comment(6000000301, f"## Claim · `{C}`\n- **Files:** `greg/d.py`\n"),
                _comment(6000000302, f"## Note · `{C}`\n\nStill here.\n", at=forged)]
    m = w.build(prs, comments, now=NOW, use_git=False)
    sessions = {s["session"]: s for s in m["sessions"]}
    assert (sessions[A]["last"], sessions[A]["activity"]) == ("2026-11-12T10:00:00Z", "ACTIVE")
    assert (sessions[C]["last"], sessions[C]["activity"]) == ("2026-11-12T12:00:00Z", "ACTIVE")
    assert next(r for r in m["prs"] if r["pr"] == 9)["title"] == "real"
    rows = [x for x in w.markdown(m).splitlines() if x.startswith("|")]
    outside = "".join(re.sub(r"`[^`]*`", "", r) for r in rows)
    assert not re.search(r"<|\]\(|@x", outside)


def test_a_fork_branch_named_like_a_base_or_the_line_stacks_nothing():
    fork = "outsider/uniimente-kernel"
    rows = w.pr_rows([_pr(1, "a/one", body=_body(_coord())),
                      _pr(2, "a/two", base="main", body=_body(_coord(session_id=B))),
                      _pr(3, "main", head_repo=fork, body=_body(_coord(session_id=C))),          # fork's "main"
                      _pr(4, "b/base", head_repo=None, body=_body(_coord(session_id=C))),       # head repo unknown
                      _pr(5, "b/child", base="b/base", body=_body(_coord(session_id=B))),
                      _pr(6, LINE, base="main", head_repo=fork)], ROOT, use_git=False)          # fork named the line
    assert sorted(r["pr"] for r in w.line_bound(rows)) == [1, 3, 4]
    assert [c["prs"] for c in w.contended(rows)] == [[1, 3, 4]]
    wf = w.line_checks(rows, ROOT)
    assert wf["pull_requests_with_line_as_head"] == [] and not wf["covered"]
    merged = w.pr_rows([_pr(1, "a/child", base="a/merged-parent", body=_body(_coord())),
                        _pr(2, "a/merged-parent", head_repo=fork, body=_body(_coord(session_id=B))),
                        _pr(3, LINE, head_repo=fork, body=_body(_coord(session_id=C)))], ROOT, use_git=False)
    assert sorted(r["pr"] for r in w.line_bound(merged, contained=lambda b: b == "a/merged-parent")) == [1, 2, 3]


def test_the_integration_pr_is_left_out_of_who_touches_and_paths_are_normalized():
    rows = w.pr_rows([_pr(196, LINE, base="older-trunk", body=_body(_coord(session_id=A))),
                      _pr(1, "a/one", body=_body(_coord(session_id=B)))], ROOT, use_git=False)
    tracked = {"greg/missions.py"}
    hits = w.who_touches(["./greg/missions.py", "no/such/file.py"], rows, [], tracked)
    assert [(h["path"], h["tracked"], [p["pr"] for p in h["prs"]]) for h in hits] == [
        ("greg/missions.py", True, [1]), ("no/such/file.py", False, [])]
    assert hits[0]["prs"][0]["via"] == ["receipt"] and hits[0]["prs"][0]["line_bound"]
    assert w.who_touches(["greg/missions.py"], None, None)[0]["prs"] is None      # not read is not nobody
    assert w._covers("tests/unit/test_wp06_*.py", "tests/unit/test_wp06_audit.py")


def test_a_path_in_another_worktree_is_made_relative_and_one_outside_is_never_clear(tmp_path):
    # The entry guide says: run the map from the checkout you started in, edit in a separate worktree.
    repo = tmp_path / "repo"
    (repo / "greg").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "line")
    (repo / "greg" / "missions.py").write_text("x\n")
    _git(repo, "add", "greg/missions.py")
    _git(repo, "commit", "-q", "-m", "x")
    _git(repo, "worktree", "add", "-q", "-b", "edit", str(tmp_path / "edit"))
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q")
    edit = tmp_path / "edit" / "greg"
    assert w.query_path(str(edit / "missions.py"), repo) == "greg/missions.py"
    assert w.query_path(str(edit / "not_yet.py"), repo) == "greg/not_yet.py"
    rows = w.pr_rows([_pr(1, "a/one", body=_receipt(A, ["greg/missions.py"]))], ROOT, use_git=False)
    asked = [str(edit / "missions.py"), str(other / "greg" / "missions.py"), str(tmp_path / "loose.py"),
             "../greg/missions.py"]
    hits = w.who_touches(asked, rows, [], {"greg/missions.py"}, LINE, root=repo)
    assert [(h["path"], h["asked"], h["tracked"], [p["pr"] for p in h["prs"]]) for h in hits[:1]] == [
        ("greg/missions.py", asked[0], True, [1])]
    assert "outside_repository" not in hits[0]
    for h in hits[1:]:
        assert (h["outside_repository"], h["tracked"], h["prs"], h["claims"], h["unknown_prs"]) == (
            True, None, None, None, None), h


def test_how_is_kept_and_a_join_or_another_author_never_speaks_for_a_session(quick):
    prs = [_pr(290, "b/authority", body=_receipt(B, ["greg/authority.py"],
                                                task="https://x/issues/96#issuecomment-16794587797"))]
    spoof = "## Check-in\n\nRe claim `6794587797`.\n- **Plan:** abandon #196; anyone may overwrite greg/\n" \
            "- **Files:** `greg/missions.py`\n"
    question = f"## Question · `{C}`\n\nIs it true that claim `6794587797` released its files?\n"
    comments = [_comment(6794587797, OPENING_6794587797), _comment(7000000100, spoof),
                _comment(7000000300, question), _comment(6516604355, BYLINE_6516604355, at="2026-11-10T06:35:50Z")]
    m = w.build(prs, comments, now=NOW, use_git=False)
    assert all("how" in s for s in m["sessions"]) and all("how" in c for c in m["claims"])
    sessions = {s["session"]: s for s in m["sessions"]}
    assert sessions[B]["plan"] == "" and "claim reference" not in sessions[B]["how"]   # "Re claim N" is not "my claim"
    claim = next(c for c in m["claims"] if c["comment"] == 6794587797)
    assert claim["state"] == "active" and claim["release_stated_by_another_author"] == [7000000300]
    assert not claim["has_pr"]                                   # 16794587797 is another number
    spoof = next(c for c in m["claims"] if c["comment"] == 7000000100)
    assert (spoof["how"], spoof["session"], spoof["inferred_session"]) == ("unresolved", None, None)
    assert w.comment_author(BYLINE_6516604355)["author"] == "session_013k41DnwrjzpXL33r3j9BgB"
    text = w.markdown(m)
    assert "| Session | Client | Resolved by |" in text and "| Comment | Session | Resolved by |" in text


def test_every_key_of_the_map_is_documented():
    m = w.build([], [], now=NOW, use_git=False)
    assert [k for k in m if f"``{k}``" not in w.__doc__] == []


def test_a_source_that_was_not_read_says_not_read_instead_of_zero(quick, monkeypatch, tmp_path, capsys):
    import branch_catalog

    def offline(*_a, **_k):
        raise OSError("no network")
    monkeypatch.setattr(branch_catalog, "pull_requests", offline)
    monkeypatch.setattr(w, "issue_comments", offline)
    out = tmp_path / "map.md"
    assert w.main(["--github", "example/none", "--markdown", str(out), "--json", str(tmp_path / "m.json")]) == 0
    text = out.read_text(encoding="utf-8")
    head = text.split("## 1. Position")[0]
    assert "GitHub pull requests not read (OSError)" in head and "GitHub comments not read (OSError)" in head
    assert "Not read: pull requests were not read." in text and "without a receipt: 0" not in text
    data = json.loads((tmp_path / "m.json").read_text())
    assert {u["state"] for u in data["units"]} == {"unknown"} and data["gaps"]["open_prs_without_receipt"] is None
    capsys.readouterr()
    assert w.main(["--github", "example/none", "--paths", "greg/missions.py"]) == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["sources"]["pull_requests_read"] is False and answer["paths"][0]["prs"] is None
    assert list(answer)[-1] == "checkin" and answer["checkin"] == w.CHECKIN_BLOCK
    assert w.main(["--unit", "WU-99"]) == 0
    assert json.loads(capsys.readouterr().out)["answer"] == "no such unit"


def test_a_failed_reading_names_the_type_and_a_repository_path_only(tmp_path):
    assert w._try(lambda: (tmp_path / "acceptance" / "x.json").read_text(), tmp_path) == {
        "not_run": "FileNotFoundError: acceptance/x.json"}
    assert "not_run" in w._try(lambda: w._foundry(tmp_path), tmp_path)           # the root asked for, not ours
    assert w.position(tmp_path)["route_drift"] == {"not_run": "route not read"}


def test_the_map_builds_where_git_does_not_answer(tmp_path):
    m = w.build(None, None, root=tmp_path, now=NOW)
    assert m["sources"]["git_read"] is False and "git not read" in m["sources"]["note"]
    assert "**Not read:**" in w.markdown(m) and "Route drift\n\nNot read." in w.markdown(m)


@pytest.mark.parametrize("name,content,note", [
    ("missing.json", None, "FileNotFoundError"), ("broken.json", "[{", "JSONDecodeError"),
    ("string.json", '"not a list"', "not a list"),
    ("error.json", '{"message": "API rate limit exceeded"}', "not a list"),
    ("deep.json", "[" * 100000 + "]" * 100000, "RecursionError"),
])
def test_a_replay_file_that_cannot_be_read_is_a_note_and_exit_zero(quick, tmp_path, name, content, note):
    src = tmp_path / name
    if content is not None:
        src.write_text(content)
    out = tmp_path / "m.json"
    assert w.main(["--prs-json", str(src), "--json", str(out)]) == 0
    sources = json.loads(out.read_text())["sources"]
    assert not sources["prs_read"] and note in sources["note"] and name in sources["note"]
    assert str(tmp_path) not in sources["note"]                              # no local path


def test_one_saved_pull_request_object_is_read_as_one_item(quick, tmp_path):
    src = tmp_path / "p1.json"
    src.write_text(json.dumps(_pr(1, "x/one", body=_body(_coord()))))
    out = tmp_path / "m.json"
    assert w.main(["--prs-json", str(src), "--json", str(out)]) == 0
    assert json.loads(out.read_text())["sources"]["open_prs"] == 1


def test_unencodable_text_is_written_escaped_and_a_failed_write_keeps_the_old_file(quick, tmp_path, monkeypatch):
    src = tmp_path / "prs.json"
    lone = '{"version": 2, "coordination": {"session_id": "\\ud800"}}'          # plain ASCII, so GitHub stores it
    src.write_text(json.dumps([_pr(1, "x/one", body=_body(lone))]))
    out = tmp_path / "map.md"
    out.write_text("previous map")
    assert w.main(["--prs-json", str(src), "--markdown", str(out)]) == 0
    written = out.read_text(encoding="utf-8")
    assert "\\ud800" in written and "## 4. Active sessions" in written

    def broken(*_a):
        raise OSError("disk full")
    monkeypatch.setattr(w.os, "replace", broken)
    assert w.main(["--prs-json", str(src), "--markdown", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == written and sorted(p.name for p in tmp_path.iterdir()) == [
        "map.md", "prs.json"]
    assert w.main(["--markdown", str(tmp_path / "no" / "such" / "dir.md")]) == 0


def test_now_reads_utc_and_offsets_and_reports_anything_else(quick, tmp_path, capsys):
    assert w.parse_now("2026-11-13T01:45:00Z") == datetime(2026, 11, 13, 1, 45, tzinfo=timezone.utc)
    assert w.parse_now("2026-11-13T01:45:00+05:00") == datetime(2026, 11, 12, 20, 45, tzinfo=timezone.utc)
    assert [w.parse_now(x) for x in ("2026-11-13", "13 Nov 2026", "2026-11-13T01:45:00", "yesterday")] == [None] * 4
    out = tmp_path / "m.json"
    assert w.main(["--now", "2026-11-13", "--json", str(out)]) == 0
    assert "--now '2026-11-13' not understood" in json.loads(out.read_text())["sources"]["note"]
    assert "not understood" in capsys.readouterr().err


def test_the_script_writes_no_bytecode_and_prints_utf8_under_any_locale(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONUTF8", "LANG")}
    env.update(PYTHONPYCACHEPREFIX=str(tmp_path / "pyc"), LC_ALL="C", PYTHONCOERCECLOCALE="0", PYTHONUTF8="0")
    run = subprocess.run([sys.executable, str(ROOT / "scripts" / "work_map.py"), "--now", "2026-11-13T01:45:00Z"],
                         cwd=tmp_path, env=env, capture_output=True, timeout=180)
    assert run.returncode == 0, run.stderr[-400:]
    assert "→".encode() in run.stdout and b"## 6. Route drift" in run.stdout
    cached = tmp_path / "pyc" / ROOT.relative_to(ROOT.anchor)       # where bytecode for this tree would land
    assert not (cached.exists() and list(cached.rglob("*.pyc")))


def test_line_checks_read_block_lists_missing_filters_and_patterns(tmp_path, monkeypatch):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    shapes = {f"on:\n  push:\n    branches:\n      - main\n      - {LINE}\n": True,
              "on:\n  push:\n  pull_request:\n": True,
              "on:\n  push:\n    branches: ['claude/**']\n": True,
              f"on:\n  push:\n    branches-ignore: [{LINE}]\n": False,
              "on:\n  push:\n    tags: ['v*']\n": False,
              "on: [push, pull_request]\n": True,
              "on:\n  push:\n    branches: ['claude/**', '!claude/greg-*']\n": False,
              # GitHub's filter patterns: * stops at /, ** does not, ? and + act on the character before them
              "on:\n  push:\n    branches: ['*']\n": False, "on:\n  push:\n    branches: ['claude*']\n": False,
              "on:\n  push:\n    branches: ['*-whgiee']\n": False, "on:\n  push:\n    branches: ['claude/*']\n": True,
              "on:\n  push:\n    branches: ['**']\n": True,
              f"on:\n  push:\n    branches: ['{LINE[:-1]}?']\n": False,
              f"on:\n  push:\n    branches: ['{LINE}?']\n": True,
              f"on:\n  push:\n    branches: ['{LINE[:-1]}+']\n": True,
              f"on:\n  push:\n    branches: ['{LINE[:-2]}[a-z][a-z]']\n": True,
              f"on:\n  push:\n    branches: ['{LINE[:-1]}\\e']\n": True,           # \ escapes; . is literal
              f"on:\n  push:\n    branches: ['{LINE.replace('-', '.', 1)}']\n": False,
              "on:\n  push:\n    branches-ignore: ['*']\n": True,
              # a paths filter makes a push run only when the pushed files match: not every push is checked
              "on:\n  push:\n    branches: [main]\n    paths: ['docs/**']\n": False,
              f"on:\n  push:\n    branches: [{LINE}]\n    paths: ['docs/**']\n": False,
              "on:\n  push:\n    paths-ignore: ['**']\n": False}
    filters = []
    for text, covers in shapes.items():
        (wf / "canonical-ci.yml").write_text(text)
        assert w.line_checks([], tmp_path)["push_covers_line"] is covers, text
        filters.append(w.line_checks([], tmp_path)["push_filter"])
    assert filters[-3:] == ["branches", "branches and paths", "every branch and paths"]   # paths matter once matched
    monkeypatch.setitem(sys.modules, "yaml", None)
    assert w.line_checks([], tmp_path) == {"not_run": "PyYAML not importable"}


def test_line_checks_never_say_false_where_the_pull_requests_were_not_read(quick):
    checks = w.build(None, None, now=NOW, use_git=False)["line_checks"]
    assert (checks["push_covers_line"], checks["pull_requests_with_line_as_head"], checks["covered"]) == (
        False, None, None)
    bad = _pr(316, LINE, base="main")
    bad["title"] = 5                                               # unreadable: it may be the carrier
    m = w.build([bad], [], now=NOW, use_git=False)
    assert (m["gaps"]["unreadable_prs"], m["line_checks"]["covered"]) == ([316], None)
    line = next(x for x in w.markdown(m).splitlines() if "Checks on pushes" in x)
    assert "**none**" not in line and "unknown" in line and "316" in line, line
    assert w.build([_pr(196, LINE, base="older-trunk")], [], now=NOW, use_git=False)["line_checks"]["covered"]
    assert w.build([], [], now=NOW, use_git=False)["line_checks"]["covered"] is False


def test_route_drift_ends_at_the_next_heading_and_needs_matching_letters(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "BACKCAST_GPS.md").write_text(
        "# x\n\n## Current full-machine route (2026-11-13)\n\n| N0 | a |\n| N1 | b |\nN3 - P5 run in parallel.\n"
        "### Mind, P0–P2\n\n## Retired ideas\n\nN2 N4 N5 P3 P4 P5\n")
    route = {"nodes": ["N0", "N1", "N2", "N3", "N4", "N5"], "mind_nodes": ["P0", "P1", "P2", "P3", "P4", "P5"]}
    assert w.route_drift(tmp_path, route) == {"section": True, "missing": ["N2", "N4", "N5", "P3", "P4"]}


def test_latest_intents_include_records_after_2026_sorted_by_date(tmp_path):
    intent = tmp_path / "docs" / "intent"
    intent.mkdir(parents=True)
    for name in ("INTENT-20261113-A", "INTENT-20270104-B", "INTENT-2026-09-27-C"):
        (intent / f"{name}.json").write_text(json.dumps({"intent_id": name, "state": "active", "title": name}))
    (intent / "INTENT-20261231-BROKEN.json").write_text("{")
    assert [r["id"] for r in w._intents(tmp_path)] == ["INTENT-20270104-B", "INTENT-20261113-A", "INTENT-2026-09-27-C"]


def test_markdown_marks_every_list_it_cuts(quick):
    prs = [_pr(n, f"x/{n}", body=_receipt(A if n % 2 else B, ["greg/missions.py"])) for n in range(1, 21)]
    claims = [_comment(6000000000 + n, f"## Claim · `{C}`\n- **Files:** `greg/body.py`, `greg/a.py`, `greg/b.py`, "
                                       "`greg/c.py`, `greg/d.py`, `greg/e.py`, `greg/f.py`\n") for n in range(30)]
    text = w.markdown(w.build(prs, claims, now=NOW, use_git=False))
    row = next(x for x in text.splitlines() if x.startswith("| `greg/missions.py`"))
    assert row.endswith("#14 +6 |")
    assert "the newest 25 of 30" in text and "`greg/e.py` +1 |" in text
    assert w._cell("x" * 200).endswith("…") and len(w._cell("x" * 200)) == 150


def test_small_slips_are_closed():
    assert w.identities("feature/abc-deadbeef") == []                      # not a cursor id
    assert w.identities("branch kimi/kimi-a2-20261109-01 here") == []      # a path segment is not a kimi id
    assert w.identities("agent [bc-8e2ec3d3](https://cursor.com/agents/bc-8e2ec3d3)")[0][1] == "bc-8e2ec3d3"
    assert w.declared_files("`greg/missions.py::test_x`", {"greg/missions.py"}, {"greg"}) == ["greg/missions.py"]
    rows = w.pr_rows([_pr(1, "x/one", body=_receipt(None, ["greg/zzz_new.py"])),
                      _pr(2, "x/two", body=_receipt(None, ["greg/zzz_new.py"]))], ROOT, use_git=False)
    assert list(w.contended(rows)[0]["holders"]) == ["(no session id) #1", "(no session id) #2"]


def test_a_unit_named_only_in_free_text_or_off_the_line_has_no_owner(quick):
    units = [u["unit"] for u in w.position(ROOT)["directive"]["units"] if u["unit"]]
    prs = [_pr(9601, "notes", base="main", body="do not start: " + ", ".join(units)),
           _pr(9602, "x/one", body="WU-11 is close to this work"),
           _pr(9603, "y/two", base="main", title="WU-11: off the line")]
    m = w.build(prs, [], now=NOW, use_git=False)
    assert all(not u["named_by"] for u in m["units"])
    assert next(u for u in m["units"] if u["unit"] == "WU-11")["mentioned_by"] == [9601, 9602, 9603]


# ------------------------------------------------------------------ files a pull request changes itself

def _git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=cwd, env=env,
                          check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def stacked(tmp_path):
    """A line, a parent branched from it, the line moving on, and a child of the parent that merged the line in."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "line")
    root = _commit(repo, "base.txt")
    _git(repo, "checkout", "-q", "-b", "parent")
    _commit(repo, "a.py")
    _git(repo, "checkout", "-q", "line")
    line = _commit(repo, "z.py")
    _git(repo, "checkout", "-q", "-b", "child", "parent")
    _git(repo, "merge", "-q", "--no-edit", "line")
    child = _commit(repo, "b.py")
    for name, sha in (("line", line), ("parent", _git(repo, "rev-parse", "parent")), ("merged", root),
                      ("main", root)):
        _git(repo, "update-ref", f"refs/remotes/origin/{name}", sha)
    return repo, child, line


def test_a_stacked_pr_that_merged_the_line_forward_holds_only_its_own_files(stacked):
    repo, child, line_tip = stacked
    pr = {"base": "parent", "head_sha": child}
    assert sorted(w.changed_files(pr, repo)) == ["b.py", "z.py"]          # the diff against its base carries z.py
    assert w.own_files(pr, repo, line="line") == ["b.py"]
    assert w.own_files({"base": "line", "head_sha": child}, repo, line="line") == sorted(
        w.changed_files({"base": "line", "head_sha": child}, repo))          # based on the line: nothing to narrow
    assert w.changed_files({"base": "parent", "head_sha": "1" * 40}, repo) is None
    rows = w.pr_rows([_pr(1, "child", base="parent", sha=child, body=_receipt(A, [])),
                      _pr(2, "parent", base="line", sha=_git(repo, "rev-parse", "parent"), body=_receipt(A, [])),
                      _pr(3, "b/z", base="line", sha=line_tip, body=_receipt(B, ["z.py"]))], repo, line="line")
    assert {r["pr"]: r["changed"] for r in rows}[1] == ["b.py"]
    assert w.contended(rows, "line") == []                                    # z.py is the line's, not #1's
    assert (w.carried({"head_sha": line_tip}, repo, "line"), w.carried({"head_sha": child}, repo, "line")) == (
        True, False)
    assert w.on_line("merged", repo, "line") and not w.on_line("parent", repo, "line")
    assert not w.on_line("main", repo, "line")                                # main is never a merged parent


def test_line_bound_prs_without_a_local_diff_are_listed(quick):
    m = w.build([_pr(1, "a/one", body=_receipt(A, ["greg/missions.py"])),
                 _pr(2, "b/two", base="main", body=_receipt(B, ["greg/body.py"]))], [], now=NOW, use_git=False)
    assert m["gaps"]["line_bound_prs_without_diff"] == [1]
    assert ("1 of 1 PRs headed for the line have neither a local diff nor a file list from the GitHub API (#1); their "
            "file lists rest on the receipt alone") in w.markdown(m)
    assert w._answer_sources(m)["line_bound_prs_without_diff"] == [1]


def test_a_file_list_from_the_api_is_counted_and_described_as_from_the_api(quick, tmp_path):
    pr = dict(_pr(505, "a/api", body=_receipt(A, ["greg/body.py"])), _api_files=["greg/body.py"])
    m = w.build([pr], [], now=NOW, use_git=False)
    assert (m["sources"]["git_diffs"], m["sources"]["api_file_lists"]) == (0, 1)
    text = w.markdown(m)
    assert "0 of them with their commits in this clone, 1 with file lists read from the GitHub API" in text
    assert "0 of 1 PRs headed for the line have neither a local diff nor a file list from the GitHub API." in text
    assert "from the GitHub API for the open PRs into the line" in text.split("Sources:")[0]
    assert "``changed_via``" in w.__doc__ and "GitHub API" in w.__doc__
    gitless = w.build([pr], [], root=tmp_path, now=NOW)
    assert "Git was not read: declared files only, and file lists read from the GitHub API." in w.markdown(gitless)


# ------------------------------------------------------------------ who wrote a board comment

def test_an_addressee_a_dead_launch_or_a_team_relay_is_never_the_author():
    uat = w.comment_author(REAL[6685585240])                                  # "First launch `bc-c902adb9` died"
    assert (uat["author"], uat["team"]) == (None, "UAT")
    at = w.comment_author(REAL[6333854390])                                   # "@`session_...`: ..."
    assert (at["author"], at["addressees"]) == (None, [A])
    to = w.comment_author(REAL[6335455896])                                   # "**To `session_...`:**"
    assert (to["author"], to["how"]) == (None, "unresolved")
    heads_up = w.comment_author(REAL[6651587410])                             # "for the integrator (session_...)"
    assert (heads_up["author"], heads_up["addressees"]) == (None, [A])
    filled = w.CHECKIN_BLOCK.replace("<one-line outcome>", f"review of {B}'s #290 authority seam").replace(
        "<actual session or task id> (<client>)", f"`{C}` (claude)")
    assert (w.comment_author(filled)["author"], w.comment_author(filled)["how"]) == (C, "label")   # the label wins
    for byline in ("## Claim: x · `{}` · 2026", "**Handoff from `{}`**", "**Resumed (`{}`). Two claims.**",
                   "**#196 intake batch** (integrator `{}`)", "## Wave 3 (session `{}`)",
                   "**Fix round for #240 from `{}`**"):
        assert w.comment_author(byline.format(B))["author"] == B, byline
    for other in ("## Blocked by `{}`: x", "## Handoff to session `{}`", "Plain text from `{}`",
                  "**Claim C: {}, wave 2**", "## Check-in · stand down <!-- {} -->"):
        assert w.comment_author(other.format(B))["author"] is None, other
    for body in ("## Handoff: #279 is green (bc-8e2ec3d3 ran it)\n", f"**UAT relay · `{A}` reported #279 green**\n",
                 f"## Note\n\n```text\n## Check-in: x\n- Session: `{A}`\n```\n"):
        assert w.comment_author(body)["author"] is None, body
    # The other party of a split, an owner who asked, or a session taken over from is not the author; a trailing
    # "· `id`" byline is. Two bylines naming two ids are not guessed between.
    for heading in ("## Claim: WU-11, split agreed with session `{b}` · `{a}`",
                    "## Claim: WU-11 (owner `{b}` asked me) · `{a}`",
                    "## Claim: WU-11, split agreed with session `{b}` · session `{a}`",
                    "## Claim: WU-11 (`{b}` agreed the split) · `{a}`",
                    "## Claim: WU-11, taking over from session `{b}` · `{a}`"):
        got = w.comment_author(heading.format(a=A, b=B) + "\n\n- **Files:** `greg/missions.py`\n")
        assert (got["author"], got["how"], B in got["addressees"]) == (A, "heading", True), heading
    pair = w.comment_author(f"## Claim: WU-11 · `{A}` · `{B}`\n")
    assert (pair["author"], pair["how"]) == (None, "unresolved")
    m = w.build([], [_comment(6900000001, f"## Claim: WU-11, split agreed with session `{B}` · `{A}`\n\n"
                                          "- **Files:** `greg/missions.py`\n")], now=NOW, use_git=False)
    assert [s["session"] for s in m["sessions"]] == [A] and m["claims"][0]["session"] == A


def test_an_opening_line_names_the_author_only_as_session_id(quick):
    assert w.comment_author(OPENING_6794587797)["how"] == "opening line"
    for second in (f"`{B}` accepts the assignment.", f"@`{B}`. Found during my run.", f"Agent `{B}` has not answered."):
        assert w.comment_author(f"## Note\n\n{second}\n")["author"] is None, second


def test_joins_need_first_person_wording_and_never_name_the_addressee(quick):
    m = w.build([], [_comment(6334679268, f"## Claim: the predicate patch · `{C}`\n- **Files:** `greg/missions.py`\n"),
                     _comment(6335455896, REAL[6335455896]),
                     _comment(6473380596, f"## Claim: staffing figures · `{B}`\n- **Files:** `greg/organs.py`\n"),
                     _comment(6474691470, REAL[6474691470]),
                     _comment(6685585240, REAL[6685585240]), _comment(6686305056, REAL[6686305056])],
                now=NOW, use_git=False)
    authors = {c["comment"]: (c["session"], c["inferred_session"]) for c in m["claims"]}
    assert authors[6334679268] == (C, None) and authors[6473380596] == (B, None)
    assert [g["comment"] for g in m["gaps"]["recent_posts_unresolved"]] == [6335455896, 6474691470, 6685585240,
                                                                            6686305056]
    assert {s["session"] for s in m["sessions"]} == {B, C}
    assert all(s["comments"] == 1 and s["inferred_comments"] == 0 for s in m["sessions"])


def test_each_join_resolves_what_no_other_join_can_and_is_labelled(quick):
    claim = f"## Claim: the authority seam · `{B}`\n- **Files:** `greg/authority.py`\n"
    handoff = "**Handoff: claim 6794587797 released into draft PR #999.**\n"         # #999 is no open PR
    by_ref = w.build([], [_comment(6794587797, claim), _comment(6795485396, handoff)], now=NOW, use_git=False)
    joined = {s["session"]: s for s in by_ref["sessions"]}[B]
    assert (joined["comments"], joined["inferred_comments"]) == (1, 1)
    by_marker = w.build([], [_comment(6796102804, REAL[6796102804]), _comment(6796931006, REAL[6796931006])],
                        now=NOW, use_git=False)
    assert next(c for c in by_marker["claims"] if c["comment"] == 6796102804)["state"] == "stopped"
    relay = "## Handoff: #278 rebased\n\nDraft #278 stays draft.\n"
    prs = [_pr(278, "c/fix", body=_receipt("uat-fix-278", ["greg/x.py"]))]
    by_pr = w.build(prs, [_comment(1, relay)], now=NOW, use_git=False)
    assert {s["session"]: s["inferred_comments"] for s in by_pr["sessions"]} == {"uat-fix-278": 1}
    hegemony = w.build(prs, [_comment(6669679691, REAL[6669679691])], now=NOW, use_git=False)
    assert hegemony["gaps"]["recent_posts_unresolved"][0]["team"] == "Hegemony"        # "Posted by Hegemony"
    cite = "https://x/issues/96#issuecomment-6000000001"
    task = w.build([_pr(290, "b/x", body=_receipt(B, ["greg/a.py"], task=cite))],
                   [_comment(6000000001, "## Claim: the seam\n- **Files:** `greg/authority.py`\n")], now=NOW,
                   use_git=False)
    assert task["claims"][0]["inferred_session"] == B and task["claims"][0]["how"] == "pr task_ref"
    assert task["claims"][0]["session"] is None                              # a join never sets a file claim
    review = w.build([_pr(290, "b/x", body=_receipt(B, ["greg/a.py"]))],
                     [_comment(2, "## Review of draft #290: two findings\n"),
                      _comment(3, "## Claim: fix the CI failure on PR #290\n- **Plan:** abandon\n")], now=NOW,
                     use_git=False)
    owner = {s["session"]: s for s in review["sessions"]}[B]
    assert (owner["comments"], owner["inferred_comments"], owner["plan"]) == (0, 0, "")


def test_inferred_activity_is_marked_and_a_cited_comment_shows_on_the_session_row(quick):
    prs = [_pr(206, "codex/entry", body=_receipt("codex/root/collab-20261030", ["scripts/x.py"],
                                                 task="https://x/issues/96#issuecomment-6398846416"),
               updated="2026-11-10T00:00:00Z")]
    comments = [_comment(6398846416, f"## Claim: workspace entry · `{B}`\n- **Files:** `scripts/x.py`\n",
                         at="2026-11-09T00:00:00Z"),
                _comment(6794587797, f"## Claim: seam · `{C}`\n- **Files:** `greg/authority.py`\n",
                         at="2026-11-11T00:00:00Z"),
                _comment(6795485396, "**Handoff: claim 6794587797 released into draft PR #999.**\n",
                         at="2026-11-12T00:00:00Z")]
    m = w.build(prs, comments, now=NOW, use_git=False)
    rows = {s["session"]: s for s in m["sessions"]}
    assert rows["codex/root/collab-20261030"]["task_refs"] == [{"pr": 206, "comment": 6398846416, "author": B}]
    assert rows[C]["last_inferred"] and not rows[B]["last_inferred"]
    text = w.markdown(m)
    assert "#206 task_ref cites comment 6398846416 by `" + B + "`" in text
    assert "ACTIVE 2026-11-12T00:00 (inferred)" in text


# ------------------------------------------------------------------ releases, stops and claim state

def test_a_release_counts_only_from_the_claims_author_unnegated_and_whole(quick):
    claim = f"## Claim: seam · `{B}`\n- **Files:** `greg/authority.py`, `greg/body.py`\n"

    def state(text: str, by: str = B) -> dict:
        m = w.build([], [_comment(6794587797, claim), _comment(7000000001, f"## Note · `{by}`\n\n{text}\n")],
                    now=NOW, use_git=False)
        return next(c for c in m["claims"] if c["comment"] == 6794587797)
    assert state("This releases claim 6794587797.")["state"] == "released"
    assert state("I do NOT release claim 6794587797; still working on it.")["state"] == "active"
    assert state("Nothing here releases claim 6794587797.")["state"] == "active"
    assert state("I am NOT saying that delivery under claim `6794587797` is stopped.")["state"] == "active"
    assert state("Delivery under claim `6794587797` is stopped.")["state"] == "stopped"
    part = state("Releases the receipt half of claim 6794587797.")
    assert (part["state"], part["partly_released_by"]) == ("active", [7000000001])
    other = state("This releases claim 6794587797.", by=C)
    assert (other["state"], other["release_stated_by_another_author"]) == ("active", [7000000001])


def test_claim_state_follows_its_session_and_a_named_pull_request_counts(quick):
    old = f"## Claim: seam · `{B}`\n- **Files:** `greg/authority.py`\n- **Draft child:** [#278]({REPO_URL}/pull/278)\n"
    later = f"## Note · `{B}`\n\nStill here.\n"
    quiet = f"## Claim: other · `{C}`\n- **Files:** `greg/body.py`. Draft #209 holds it.\n"
    m = w.build([_pr(278, "c/fix", body="no receipt")],
                [_comment(6400000001, old, at="2026-11-04T00:00:00Z"), _comment(6400000002, later,
                                                                                at="2026-11-13T01:00:00Z"),
                 _comment(6400000003, quiet, at="2026-11-01T00:00:00Z")], now=NOW, use_git=False)
    claims = {c["comment"]: c for c in m["claims"]}
    # The session is active, the claim is not: a nine-day-old claim no comment of its author cites is not a live hold.
    assert (claims[6400000001]["state"], claims[6400000001]["posted"], claims[6400000001]["session_activity"]) == (
        "dormant", "dormant", "active")
    assert claims[6400000001]["names_prs"] == [{"pr": 278, "state": "open", "named_in": 6400000001}]
    assert claims[6400000003]["names_prs"] == [{"pr": 209, "state": "closed", "named_in": 6400000003}]
    assert claims[6400000003]["has_pr"] and not claims[6400000003]["cited_by_receipts"]
    assert m["older_claims_without_pr"] == {"count": 2, "naming_a_pr": 2, "by_live_sessions": 1}
    assert m["claims_without_pr"] == []                                       # both were posted more than 7 days ago
    text = w.markdown(m)
    assert "Claims that no open pull request's receipt cites (posted in the last 7 days" in text
    assert "2 claims posted more than 7 days ago that no open pull request's receipt cites" in text


def test_a_handoff_citing_a_claim_names_its_pull_request(quick):
    claim = f"## Claim: whole-output judgment · `{B}`\n- **Files:** `greg/missions.py`\n"
    handoff = f"## Handoff (part A): draft #209, a child of #196\n\nThis is for claim 6472686919 by `{B}`.\n"
    m = w.build([], [_comment(6472686919, claim), _comment(6473486287, handoff)], now=NOW, use_git=False)
    assert m["claims"][0]["names_prs"] == [{"pr": 209, "state": "closed", "named_in": 6473486287}]


def test_released_stopped_and_old_claims_stay_out_of_the_live_table(quick):
    claim = "## Claim: x · `{}`\n- **Files:** `greg/{}.py`\n"
    m = w.build([], [_comment(6000000001, claim.format(B, "a")),
                     _comment(6000000002, f"## Note · `{B}`\n\nThis releases claim 6000000001.\n"),
                     _comment(6000000003, claim.format(C, "b")),
                     _comment(6000000004, f"## N · `{C}`\n\nDelivery under claim 6000000003 is stopped."),
                     _comment(6000000005, claim.format(A, "c"), at="2026-10-01T00:00:00Z"),
                     _comment(6000000006, claim.format(A, "d"))], now=NOW, use_git=False)
    assert [c["comment"] for c in m["claims_without_pr"]] == [6000000006]


# ------------------------------------------------------------------ what a claim declares

_TREE: list = []


def _tree() -> tuple[set[str], set[str]]:
    """This repository's tracked files and their directories, read once."""
    if not _TREE:
        tracked, _ = w._tracked(ROOT)
        _TREE.append((tracked, {"/".join(f.split("/")[:i]) for f in tracked for i in range(1, f.count("/") + 1)}))
    return _TREE[0]


def _parse(cid: int, body: str | None = None) -> dict:
    tracked, dirs = _tree()
    return w.parse_comment(_comment(cid, REAL[cid] if body is None else body), tracked, dirs)


def test_real_claims_declare_their_files_under_any_files_label():
    assert _parse(6796102804)["files"] == ["scripts/repo_review.py", "tests/unit/test_repo_health_gates.py",
                                           "docs/REVIEW_CADENCE.md",
                                           "docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml"]
    owned = _parse(6648797976)["files"]                                       # "Owned files", nested "New:" lists
    assert owned[:4] == ["AGENTS.md", "README.md", "CONTRIBUTING.md", "docs/README.md"]
    assert "scripts/repo_review.py" in owned and "docs/collaboration/START_HERE.md" not in owned   # "Not touching"
    inline = _parse(6800963150)                                               # inline "File:" and "Files:"
    assert (inline["kind"], inline["files"], inline["recheck"]) == (
        "claim", ["greg/authority.py", "greg/missions.py", "greg/appraisal.py", "greg/body.py"], "2026-11-12T12:00:00Z")
    three = _parse(6802820715)
    assert three["kind"] == "claim+handoff" and "greg/missions.py" not in three["files"]
    assert three["files"] == ["greg/corrections.py", "greg/cognition/settlement.py", "greg/sop.py",
                              "tests/unit/test_greg_evidence_corrections.py", "greg/goal_gravity.py"]
    assert (three["releases"], three["partial_releases"], three["unit_refs"]) == (["6802130261"], ["6800963150"],
                                                                                 ["S42-B"])
    assert _parse(6669494168)["files"] == ["greg/body.py", "greg/genesis.py"]  # "Files" wins over an earlier "Scope"
    s45 = _parse(6637616850)
    assert (s45["kind"], s45["files"], s45["route"]) == (
        "claim", ["greg/corrections.py", "greg/asks.py", "acceptance/directive-sections.json"], "S45-A")


def test_kind_is_read_from_the_lead_of_the_heading():
    assert [_parse(cid)["kind"] for cid in (6637616850, 6802820715, 6649055882, 6650124537, 6811147535)] == [
        "claim", "claim+handoff", "handoff", "handoff", "claim+handoff"]
    for heading, kind in (("**#278 merge-forward landed** (claim 6673874794). Still draft.", "update"),
                          ("**Enrollment: UAT team (no claim yet)**", "other"),
                          ("## Withdrawn: my bounded-predicates claim duplicates `3d2f9cc4`", "release"),
                          ("## Claim release (6516597695): seed gate constraint mutant", "release")):
        assert w.comment_kind(heading) == kind, heading
    assert _parse(6794632436)["route"] == "WU-11"                             # a unit in a claim heading is its route


def test_a_negative_phrase_drops_only_what_it_excludes():
    tracked = {"greg/authority.py", "greg/body.py", "greg/path.json", "AGENTS.md", "evolution/repair/x.py"}
    dirs = {"greg", "evolution", "evolution/repair", "docs", "docs/collaboration"}
    files = w.declared_files
    assert files("`greg/authority.py` (the registry stays read-only), `greg/body.py`", tracked, dirs) == [
        "greg/authority.py", "greg/body.py"]
    assert files("`greg/authority.py`, not `greg/body.py`", tracked, dirs) == ["greg/authority.py"]
    assert files("`AGENTS.md`. Runtime, `greg/path.json` and other branches are read-only.", tracked, dirs) == [
        "AGENTS.md"]
    assert files("`AGENTS.md`; `evolution/repair/` stays read-only", tracked, dirs) == ["AGENTS.md"]
    assert files("`evolution/repair/**`, `greg/{body,missions}.py`", tracked, dirs) == ["evolution/repair/**"]
    assert files("a dated evidence note under `docs/collaboration/`. No existing file.", tracked, dirs) == [
        "new file under docs/collaboration"]
    for sentence in ("`greg/a.py` (read-only), `greg/b.py`", "`greg/a.py` read-only; `greg/b.py`",
                     "`greg/a.py` untouched, `greg/b.py`", "`greg/a.py` (held by #278), `greg/b.py`"):
        assert files(sentence, {"greg/a.py", "greg/b.py"}, {"greg"}) == ["greg/b.py"], sentence


def test_a_bare_directory_holds_no_existing_file_and_a_glob_does(quick):
    note = f"## Claim: rehearsal · `{B}`\n- **Files:** new `scripts/compose.py`, a note under `docs/collaboration/`.\n"
    glob = f"## Claim: wp06 · `{C}`\n- **Files:** `tests/unit/test_wp06_*.py`, `evolution/repair/**`\n"
    m = w.build([], [_comment(1, note), _comment(2, glob)], now=NOW, use_git=False)
    hits = w.who_touches(["docs/collaboration/START_HERE.md", "tests/unit/test_wp06_audit.py",
                          "evolution/repair/harness.py"], [], m["claims"])
    assert [[c["comment"] for c in h["claims"]] for h in hits] == [[], [2], [2]]


def test_claims_whose_files_could_not_be_read_are_counted(quick):
    unreadable = f"## Claim: x · `{B}`\n- **Files:** `a.b`\n"
    m = w.build([], [_comment(6685585240, REAL[6685585240]), _comment(2, unreadable)],
                now=NOW, use_git=False)
    assert m["gaps"]["claims_without_readable_files"] == [2, 6685585240]
    assert "Claims whose file list could not be read: 2 (2, 6685585240)." in w.markdown(m)


def test_a_label_is_matched_whole_never_by_prefix():
    found = w.fields("- **Planned follow-ups:** later\n- **Task list:** x\n- **Plan:** one step\n")
    assert (w._field(found, "plan"), w._field(found, "prompt")) == ("one step", "")


# ------------------------------------------------------------------ units

def test_units_are_named_by_title_or_receipt_asks_and_carried_prs_name_nothing(quick):
    prs = [_pr(282, "c/scout", body=_receipt("bc-c1e4f202", ["greg/goal_gravity.py"],
                                             scope="S10.A1, S45.A2, S42.A1: source-coverage validation")),
           _pr(221, "c/settle", title="Second review", body="x" * 4000 + " the S42-A community settlement"),
           _pr(257, "c/place", title="S53-A: place every open PR", body=_receipt(C, ["scripts/lineage_map.py"])),
           _pr(9, "c/touch", body=_receipt(A, [w.position(ROOT)["directive"]["units"][1]["owner_paths"][0]]))]
    board = f"## Claims · `{B}`\n\n1. Map entry for S69.A6. Files: `greg/body.py`.\n"
    m = w.build(prs, [_comment(6797070087, board)], now=NOW, use_git=False, carried_by=lambda r: r["pr"] == 257)
    units = {u["unit"]: u for u in m["units"]}
    assert [o["pr"] for o in units["S45-B"]["named_by"]] == [282] == [o["pr"] for o in units["S42-B"]["named_by"]]
    assert (units["S42-A"]["named_by"], units["S42-A"]["mentioned_by"]) == ([], [221])
    assert (units["S53-A"]["state"], units["S53-A"]["carried_by_line"]) == ("unclaimed", [257])
    assert (units["S69-A"]["state"], units["S69-A"]["claimed_on_board"]) == ("claimed on the board", [6797070087])
    assert units["MW-A"]["state"] == "prerequisite, no completion record"
    assert all(u["state"] == "waits" for u in units.values() if u["waits_on"] and not u["named_by"]
               and not u["claimed_on_board"])
    assert all(9 not in [o["pr"] for o in u["named_by"]] for u in units.values())   # touching is not naming
    assert 9 in m["units"][1]["also_touching_its_files"]
    assert all(257 not in [o["pr"] for o in u["named_by"]] and 257 not in u["also_touching_its_files"]
               for u in units.values())
    from acceptance import directive
    rep = directive.directive_report(*directive.defaults(), None, ROOT)
    assert [u["unit"] for u in m["units"]] == [row["unit"] for row in rep["buildable_in_dependency_order"]]
    text = w.markdown(m)
    assert "| Open PRs naming it |" in text and "carried: #257" in text


# ------------------------------------------------------------------ which pull requests are headed for the line

def test_line_bound_follows_any_depth_a_duplicated_head_and_a_merged_parent():
    from lineage_map import _stacked_on
    deep = [_pr(n, f"s/{n}", base=LINE if n == 1 else f"s/{n - 1}") for n in range(1, 17)]
    rows = w.pr_rows(deep, ROOT, use_git=False)
    assert len(w.line_bound(rows)) == 16
    by_ref = {r["head"]: {"number": r["pr"], "base": r["base"]} for r in rows}
    assert all(_stacked_on({"number": r["pr"], "base": r["base"]}, LINE, by_ref) for r in rows)   # one stack walk
    twice = w.pr_rows([_pr(20, "d/one"), _pr(21, "d/one", base="main"), _pr(22, "d/two", base="d/one")], ROOT,
                      use_git=False)
    assert sorted(r["pr"] for r in w.line_bound(twice)) == [20, 22]
    orphan = w.pr_rows([_pr(285, "codex/path", base="cursor/merged", body=_receipt(A, ["acceptance/missions.json"])),
                        _pr(267, "b/one", body=_receipt(B, ["acceptance/missions.json"])),
                        _pr(196, LINE, base="older-trunk", body=_receipt(C, ["acceptance/missions.json"])),
                        _pr(30, "x/old", base="main", body=_receipt(C, ["acceptance/missions.json"]))], ROOT,
                       use_git=False)
    merged = {"cursor/merged", "older-trunk"}.__contains__
    assert sorted(r["pr"] for r in w.line_bound(orphan, contained=merged)) == [267, 285]
    assert sorted(r["pr"] for r in w.line_bound(orphan)) == [267]
    assert w.contended(orphan, contained=merged)[0]["prs"] == [267, 285]


# ------------------------------------------------------------------ contended files

def test_contention_groups_directories_and_globs_and_counts_receipt_less_prs_one_each():
    rows = w.pr_rows([_pr(1, "a/one", body=_receipt(A, ["greg/cognition/"])),
                      _pr(2, "b/one", body=_receipt(B, ["greg/cognition/compiler.py"])),
                      _pr(3, "c/one", body=_receipt(C, ["greg/cognition"])),
                      _pr(4, "a/path", body=_receipt(A, ["greg/path"])),
                      _pr(5, "b/path", body=_receipt(B, ["greg/path.json"])),
                      _pr(6, "x/one"), _pr(7, "x/two", base="x/one")], ROOT, use_git=False)
    for r in rows:
        r["changed"] = ["tests/unit/test_x.py"] if r["pr"] in (6, 7) else r["changed"]
    got = w.contended(rows)
    assert [(c["file"], c["sessions"]) for c in got] == [("greg/cognition/compiler.py", 3),
                                                         ("tests/unit/test_x.py", 2)]
    assert list(got[1]["holders"]) == ["(no receipt) #6", "(no receipt) #7"]
    assert not w._covers("greg/path", "greg/path.json") and w._covers("greg/path", "greg/path/x.py")
    assert [p["pr"] for p in w.who_touches(["greg/cognition"], rows, [])[0]["prs"]] == [1, 2, 3]
    text = w.markdown(w.build([], [], now=NOW, use_git=False))
    assert "| File | Session ids (a PR with no receipt counts as one) | Pull requests |" in text


def test_a_fix_round_child_and_a_carried_pr_hold_nothing_against_its_parent():
    rows = w.pr_rows([_pr(240, "cursor/bounds", body=_receipt("uat-vulcan", ["identity/machine_passport.py"])),
                      _pr(278, "cursor/bounds-fix", base="cursor/bounds",
                          title="Fix round: green CI for resource bounds (child of #240)",
                          body=_receipt("uat-fix-278", ["identity/machine_passport.py"])),
                      _pr(279, "claude/b-join", base="cursor/bounds", title="Unit B joined onto #240's channel",
                          body=_receipt(B, ["greg/appraisal.py"])),
                      _pr(243, "cursor/pin", body=_receipt(C, ["greg/appraisal.py"]))], ROOT, use_git=False)
    assert w.contended(rows)[0]["file"] == "greg/appraisal.py" and len(w.contended(rows)) == 1
    for r in rows:
        r["carried"] = r["pr"] == 243
    assert w.contended(rows) == []


# ------------------------------------------------------------------ counts and thresholds

def test_activity_changes_exactly_at_48_and_168_hours():
    def at(hours: float) -> str:
        return (NOW - __import__("datetime").timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert [w.activity(at(h), NOW) for h in (47.9, 48, 167.9, 168)] == ["ACTIVE", "QUIET", "QUIET", "DORMANT"]


def test_live_counts_and_tables_leave_dormant_sessions_and_closed_prs_out(quick):
    prs = [_pr(1, "a/one", body=_receipt(A, ["greg/a.py"]), updated="2026-10-01T00:00:00Z"),
           _pr(2, "b/one", body=_receipt(B, ["greg/b.py"])), _pr(3, "c/one", body="none", state="closed"),
           _pr(4, "d/one", base="main", body="none"), _pr(5, "e/one", body="none")]
    m = w.build(prs, [_comment(9, "## x")], now=NOW, use_git=False)
    assert [r["pr"] for r in m["prs"]] == [1, 2, 4, 5]
    assert m["gaps"]["open_prs_without_receipt_into_line"] == [5]
    assert m["gaps"]["live_sessions"] == 1                                    # A's only update is 6 weeks old
    text = w.markdown(m)
    assert f"| `{A}` |" not in text and f"| `{B}` |" in text


def test_main_writes_nothing_in_the_tree_and_exits_zero_with_a_contended_map(quick, tmp_path, monkeypatch):
    tree = tmp_path / "tree"
    tree.mkdir()
    _git(tree, "init", "-q")
    monkeypatch.setattr(w, "ROOT", tree)
    before = (_git(tree, "status", "--porcelain", "--ignored"), sorted(os.listdir(ROOT)))
    src = tmp_path / "out" / "prs.json"
    src.parent.mkdir()
    src.write_text(json.dumps([_pr(1, "a/one", body=_receipt(A, ["greg/missions.py"])),
                               _pr(2, "b/one", body=_receipt(B, ["greg/missions.py"]))]))
    assert w.main(["--prs-json", str(src), "--json", str(tmp_path / "out" / "m.json")]) == 0
    assert json.loads((tmp_path / "out" / "m.json").read_text())["contended"][0]["sessions"] == 2
    assert (_git(tree, "status", "--porcelain", "--ignored"), sorted(os.listdir(ROOT))) == before
    assert w.receipt_of(_body("{broken")) is None


def test_the_map_says_what_it_measures(quick):
    text = w.markdown(w.build([_pr(1, "a/one", body=_receipt(A, ["greg/missions.py"]))], [], now=NOW, use_git=False))
    for phrase in ("Receipts are read as declared and not re-validated here",
                   "| Attested as achieved in `greg/path.json`",
                   "*Named* means an open pull request headed for the line has the unit id or one of its ask ids",
                   "counted under Gaps and listed in the JSON output"):
        assert phrase in text, phrase
    assert "Receipts and git diffs are exact" not in text


# ------------------------------------------------------------------ releases a join cannot vouch for

M9E = "session_01Kucyfm9exT5imDVYvHTYSv"
# Trimmed real claim 6805031119 (issue #96).
CLAIM_6805031119 = f"""## Bounded claim: representation repair on the compile path (Layer 5, bounded experiment)

- **Session:** `{M9E}`. **Base:** #196 `8d20532464b1533b28d71d8331ca3412a90dbb11`.
- **Scope:** the compile route of `cognition.reason` only. Expected files: one new module under `greg/cognition/`, a small call site in `greg/cognition/compiler.py`, tests, a mutation gate.
"""


def _claim(m: dict, cid: int) -> dict:
    return next(c for c in m["claims"] if c["comment"] == cid)


def test_a_release_whose_author_a_join_took_from_the_released_claim_does_not_count(quick):
    claim = _comment(6805031119, CLAIM_6805031119, at="2026-11-11T19:16:51Z")
    for body in ("## Note\n\nRe my claim `6805031119`: I release claim `6805031119`.\n",
                 "## Note\n\nOn my claim `6805031119`: delivery under claim `6805031119` is stopped.\n"):
        m = w.build([], [claim, _comment(7000000500, body, at="2026-11-13T01:40:00Z")], now=NOW, use_git=False)
        c = _claim(m, 6805031119)
        assert (c["state"], c["released_by"], c["release_by_inferred_author"]) == ("active", [], [7000000500]), body
        assert 6805031119 in [x["comment"] for x in m["claims_without_pr"]]
        hit = w.who_touches(["greg/cognition/compiler.py"], [], m["claims"])[0]["claims"]
        assert [(x["comment"], x["state"]) for x in hit] == [(6805031119, "active")]


def test_a_joined_release_counts_only_when_a_pr_it_names_is_the_claim_author_s(quick):
    claim = _comment(6794587797, OPENING_6794587797, at="2026-11-12T00:00:00Z")
    handoff = _comment(6795485396, HANDOFF_6795485396, at="2026-11-12T06:00:00Z")
    own = _pr(290, "b/authority", body=_receipt(B, ["greg/authority.py"]))
    c = _claim(w.build([own], [claim, handoff], now=NOW, use_git=False), 6794587797)
    assert (c["state"], c["released_by"]) == ("released", [{"comment": 6795485396, "how": "claim reference"}])
    for prs in ([], [_pr(290, "b/authority", body=_receipt(C, ["greg/authority.py"]))]):   # no PR, another's PR
        c = _claim(w.build(prs, [claim, handoff], now=NOW, use_git=False), 6794587797)
        assert (c["state"], c["released_by"], c["release_by_inferred_author"]) == ("active", [], [6795485396])
    reviewer = "## Handoff: claim 6794587797 released into draft PR #999\n\nI am the reviewer of #290; I took this over.\n"
    c = _claim(w.build([own], [claim, _comment(7000000006, reviewer, at="2026-11-12T10:00:00Z")], now=NOW,
                       use_git=False), 6794587797)
    assert (c["state"], c["released_by"], c["release_by_inferred_author"]) == ("active", [], [7000000006])


# ------------------------------------------------------------------ quoted text is not its author

QUOTE_REPLY = ("## Check-in: body recovery\n\n> Session `session_01FBS4KNJR59nSbdGbxo8Mbx`. I hold greg/missions.py "
               "until 03:00.\n\nThat overlaps my work. I will take greg/body.py instead.\n- **Prompt:** finish the body "
               "recovery\n- **Plan:** rewrite greg/body.py\n- **Files:** `greg/body.py`\n")


def test_quoted_text_a_table_or_a_code_block_never_names_the_author(quick):
    for body in (QUOTE_REPLY, f"## Note\n\n| Session `{A}` | x |\n|---|---|\n",
                 f"## Note\n\n````markdown\n```text\n- **Implementer:** `{A}`\n```\n````\n",
                 f"## Note\n\nQuoted below.\n\n    - **Implementer:** `{A}`\n"):
        got = w.comment_author(body)
        assert (got["author"], got["how"]) == (None, "unresolved"), body
    assert w.comment_author(f"## Note\n\n````text\n```\n````\n- **Implementer:** `{A}`\n")["author"] == A
    m = w.build([], [_comment(7000000600, QUOTE_REPLY, at="2026-11-13T01:40:00Z")], now=NOW, use_git=False)
    hit = w.who_touches(["greg/body.py"], [], m["claims"])[0]["claims"]
    assert [(x["comment"], x["session"], x["how"]) for x in hit] == [(7000000600, None, "unresolved")]
    assert m["sessions"] == []                                     # no row lends A the replier's prompt and plan


# ------------------------------------------------------------------ claims their authors gave up

# Trimmed real comments (issue #96): each gives up the claim named with it.
REAL_RELEASES = {
    6336007588: ("## Withdrawn: my bounded-predicates claim duplicates `3d2f9cc4`. Independent oracle result instead "
                 "(2026-10-22T08:20Z)\n\n**Session:** `session_01PwqafNDa4MExng4LG5kye6`. **Re:** my [claim 6334679268]"
                 "(https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6334679268).\n", "6334679268"),
    6475013582: ("**Handoff and claim release**: session `session_01Kucyfm6YBHMTjaiC1M9hqD`, closing the claim in "
                 "https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6472033495.\n\n**Delivered:** "
                 "draft #211 into #196's branch. Nothing is merged, and #196 and #168 are untouched.\n", "6472033495"),
    6677134399: ("## Handoff: real-process business path, draft #285\n\nClaim 6677013479 is released into "
                 "https://github.com/dababiyoda/uniimente-kernel/pull/285. Branch correction: the published branch is "
                 "`codex/business-path-process`.\n\n- Implementer: Codex `/root`, session `90998d6aac2a`.\n", "6677013479"),
    6804957388: (f"**Handoff: composition rehearsal tool, draft #296** (session `{M9E}`; claim: comment 6802927161)\n\n"
                 "- **Branch / head:** `claude/compose-rehearsal-20261111` @ `0b0bb6d3`, base `8d205324`.\n",
                 "6802927161"),
}


def test_real_withdrawals_and_handoffs_release_the_claims_they_give_up():
    for cid, (body, claim) in REAL_RELEASES.items():
        assert _parse(cid, body)["releases"] == [claim], cid
    assert _parse(6519469853, "## Claim release (6516597695): seed gate constraint mutant — #226 green\n")[
        "releases"] == ["6516597695"]                                          # real heading 6519469853
    assert _parse(1, "## Not withdrawn: my claim 6516597695 stands\n")["releases"] == []
    assert _parse(2, "## Release blocked: claim 6516597695 is still held\n")["releases"] == []


def test_a_claim_its_author_withdrew_is_released_and_an_old_claim_is_not_active(quick):
    claim = _comment(6700000001, f"## Claim: deny execution of an unattached capability · `{B}`\n\n"
                                 "- **Files:** `greg/authority.py`\n", at="2026-10-20T10:00:00Z")
    alive = _comment(6800000009, f"## Update: other work · `{B}`\n\nprogress on something else.\n",
                     at="2026-11-12T23:00:00Z")

    def state(text: str | None = None, at: str = "2026-10-21T10:00:00Z") -> tuple:
        extra = [_comment(6700000002, text, at=at)] if text else []
        m = w.build([], [claim, alive, *extra], now=NOW, use_git=False)
        c = _claim(m, 6700000001)
        return c["state"], c["session_activity"], w.who_touches(["greg/authority.py"], [], m["claims"])[0][
            "claims"][0]["state"]
    assert state() == ("dormant", "active", "dormant")         # its session posted today; the claim is 24 days old
    for text in (f"## Withdrawn: my claim 6700000001 duplicates `3d2f9cc4` · `{B}`\n\nI stop here.\n",
                 f"**Handoff and claim release**: session `{B}`, closing the claim in "
                 "https://github.com/o/r/issues/96#issuecomment-6700000001.\n",
                 f"## Handoff: draft #290 · `{B}`\n\nClaim 6700000001 is released into https://github.com/o/r/pull/290.\n",
                 f"## Handoff: draft #290 · `{B}`\n\nNothing is merged, so this releases claim 6700000001.\n"):
        assert state(text) == ("released", "active", "released"), text
    assert state(f"## Note · `{B}`\n\nI do NOT release claim 6700000001; still on it.\n")[0] == "dormant"
    assert state(f"## Note · `{B}`\n\nStill on claim 6700000001.\n", at="2026-11-12T22:00:00Z")[0] == "active"


# ------------------------------------------------------------------ what a claim's files are

UAT_6673874794 = """<!-- uniimente:receipt -->
**UAT status + claims (Hegemony GREG build loop)** · 2026-11-05 ~8:10 PM ET

**Claim 1 — disposition index + authority check it unblocks.** Asks `S5.A1`, `S51.A1`, `S67.A1`, `S51.A2`. Files: `docs/collaboration/REPOSITORY-METABOLISM-2026-09-25.json`, `greg/path.py`, `scripts/ci/check_authority_singleton.py`, `governance/integrity/__init__.py`, `greg/organs.py`, `organs/daleobanks.manifest.yaml`, new tests, only those four ask records in `acceptance/directive-sections.json`. Base `50cf3f75`, draft child of #196. Leave `S3.A1`/`S23.A2` (`greg/authority.py` = #278). Do **not** edit `canonical-ci.yml`. Acceptance: fail-first cases in scout package 1, then green. Founder reviews `acceptance/**` and `scripts/ci/**`.

**Claim 3 — one-command whole-path rehearsal.** Asks `S77.A2`, `S61.A1` (WU-02). Files: `greg/rehearsal.py`, and `greg/business_loop.py` / `greg/sop.py` / `greg/venture_books.py` only where the sequence needs; new tests; those two ask records. `S71.A1` out (`greg/missions.py` hot). No payment provider, treasury, or founder key.

**Claim 4 — checked coverage.** Asks `S10.A1`, `S45.A2`, `S42.A1`. Files: `greg/cognition/restatement.py`, `greg/goal_gravity.py`, those three ask records. Do **not** edit `greg/dataplane.py` (S42.A2 on #221). Base `50cf3f75`.
"""
DOCTOR_6658500455 = """## Claim (pass 3 of #271): gate liveness and an environment doctor · `session_01KucyfnCuSTnjx5Fa6T4A3d` · 2026-11-05

**Scope.** All additive. No CI job, timeout, pin, sealed or integrity-protected file is touched.

- `scripts/repo_review.py` gains three report items:
  - **Gate liveness.** Every literal mutation anchor in `scripts/ci/check_*_mutants.py` must still occur exactly once in its target file.
- **New `scripts/dev_env_check.py`, read-only.** Before tests run, it reports what would make them fail for environmental reasons:
  - a shallow clone;
- Tests for each item.

**Overlap check.**
- `scripts/ci/check_*_mutants.py` files are read, never edited.
"""
ITEMS_6797070087 = f"""## Bounded claims, 2026-11-11 (session `{M9E}`)

**A. #291 follow-up (same branch, `egregore/fervent-mayer-syy5d6`).**
- Files: `greg/authority.py`, both authority test files, both authority mutant gates.

**C. Completion-map correction, S69.A6** — branch `claude/directive-map-s69a6-20261111`.
- `acceptance/directive-sections.json` and its pin only, for that one ask: record the existing evidence.
"""


def test_files_a_claim_disclaims_or_names_in_prose_are_not_its_files_and_a_limited_item_is():
    uat = _parse(6673874794, UAT_6673874794)["files"]
    assert not {"greg/authority.py", "greg/missions.py", "greg/dataplane.py", "acceptance/**", "scripts/ci/**"} & set(uat)
    assert {"greg/path.py", "greg/rehearsal.py", "greg/goal_gravity.py", "acceptance/directive-sections.json"} <= set(uat)
    assert _parse(6658500455, DOCTOR_6658500455)["files"] == ["scripts/repo_review.py", "scripts/dev_env_check.py"]
    assert _parse(6797070087, ITEMS_6797070087)["files"] == ["greg/authority.py", "acceptance/directive-sections.json"]
    owned = _parse(6331326870, "## Claim\n\n- **Owned:** the new evidence path and `tests/unit/test_greg_x*.py`.\n")
    assert owned["files"] == ["tests/unit/test_greg_x*.py"]                  # an Owned label may declare a glob


# ------------------------------------------------------------------ units a board handoff names

HANDOFF_6674130951 = f"""## Handoff: disposition index and the authority check it unblocks (S5.A1, S51.A1, S67.A1, S51.A2)

Claim: https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6673874794
Draft child of #196: {REPO_URL}/pull/283
"""


def test_a_handoff_linking_an_open_pr_names_its_units_on_the_board_at_any_age(quick):
    prs = [_pr(283, "cursor/section5-authority-seam-8e94", body=_receipt("bc-346e45e2", ["greg/path.py"]),
               title="One section-5 disposition per material path, then an AST check for a second Gate")]
    handoff = _comment(6674130951, HANDOFF_6674130951, at="2026-11-05T01:24:35Z")         # eight days old
    m = w.build(prs, [handoff], now=NOW, use_git=False)
    units = {u["unit"]: u for u in m["units"]}
    assert (units["S5-A"]["state"], units["S5-A"]["named_on_board"]) == (
        "named on the board", [{"pr": 283, "comment": 6674130951}])
    assert units["S51-A"]["state"] == "named on the board"
    assert "named on the board → #283 (comment 6674130951)" in w.markdown(m)
    landed = w.build(prs, [handoff], now=NOW, use_git=False, carried_by=lambda r: True)
    assert {u["unit"]: u for u in landed["units"]}["S5-A"]["state"] == "unclaimed"        # carried: nothing open


# ------------------------------------------------------------------ fix rounds and whole-tree receipts

def test_only_a_titled_fix_round_folds_into_its_parent_and_keeps_its_own_session():
    for title in ("Add hostile fixtures for #10", "Follow-up to #10: docs"):
        rows = w.pr_rows([_pr(10, "a/one", body=_receipt(A, ["greg/q.py"])),
                          _pr(11, "b/two", base="a/one", title=title, body=_receipt(B, ["greg/q.py"]))], ROOT,
                         use_git=False)
        assert [(c["file"], c["sessions"]) for c in w.contended(rows)] == [("greg/q.py", 2)], title
    rows = w.pr_rows([_pr(240, "cursor/bounds", body=_receipt("uat-vulcan-resource-bounds", ["greg/x.py"])),
                      _pr(278, "cursor/bounds-fix", base="cursor/bounds",
                          title="Fix round: green CI and current base for resource bounds (child of #240)",
                          body=_receipt("uat-resource-bounds-fix-278", ["greg/x.py", "greg/authority.py"])),
                      _pr(290, "b/authority", body=_receipt(B, ["greg/authority.py"]))], ROOT, use_git=False)
    got = w.contended(rows)
    assert [(c["file"], c["sessions"]) for c in got] == [("greg/authority.py", 2)]      # #278 counts with #240
    assert got[0]["holders"] == {B: [290], "uat-resource-bounds-fix-278 (fix round of #240)": [278]}


def test_a_long_fix_round_chain_is_held_once_and_quickly(quick, tmp_path, monkeypatch):
    import time
    n = 1200
    prs = [_pr(1, "s/0", body=_receipt(None, ["a.py"]))] + [
        _pr(i + 1, f"s/{i}", base=f"s/{i - 1}", title=f"Fix round of #{i}", body=_receipt(None, ["a.py"]))
        for i in range(1, n)] + [_pr(5000, "b/x", body=_receipt(B, ["a.py"]))]
    rows = w.pr_rows(prs, ROOT, use_git=False)
    start = time.perf_counter()
    got = w.contended(rows)
    assert time.perf_counter() - start < 1.0
    assert [(c["file"], c["sessions"], len(c["prs"])) for c in got] == [("a.py", 2, n + 1)]
    monkeypatch.setattr(w, "changed_files", lambda *_a, **_k: None)          # no clone holds these heads
    monkeypatch.setattr(w, "carried", lambda *_a, **_k: None)
    src = tmp_path / "chain.json"
    src.write_text(json.dumps(prs))
    assert w.main(["--prs-json", str(src), "--json", str(tmp_path / "m.json")]) == 0
    assert json.loads((tmp_path / "m.json").read_text())["contended"][0]["sessions"] == 2


def test_a_receipt_declaring_the_whole_tree_covers_every_file():
    rows = w.pr_rows([_pr(9201, "a/1", body=_receipt("sess-a", ["**"])),
                      _pr(9202, "a/2", body=_receipt("sess-b", ["greg/missions.py"])),
                      _pr(9203, "a/3", body=_receipt("sess-c", ["*"]))], ROOT, use_git=False)
    got = {c["file"]: (c["sessions"], c["prs"]) for c in w.contended(rows)}
    assert got == {"greg/missions.py": (3, [9201, 9202, 9203]), "**": (2, [9201, 9203])}
    assert [p["pr"] for p in w.who_touches(["greg/missions.py"], rows, [])[0]["prs"]] == [9201, 9202, 9203]


def test_globs_match_paths_and_overlapping_globs_but_not_disjoint_ones():
    rows = w.pr_rows([_pr(1, "a/1", body=_receipt(A, ["greg/a*.py"])), _pr(2, "a/2", body=_receipt(B, ["greg/*b.py"])),
                      _pr(3, "a/3", body=_receipt(C, ["greg/a*.md"]))], ROOT, use_git=False)
    got = {c["file"]: c["prs"] for c in w.contended(rows)}
    assert got == {"greg/a*.py": [1, 2], "greg/*b.py": [1, 2]}                   # "greg/ab.py" is in both; .md is not


def test_receipts_declaring_thousands_of_globs_are_cut_and_stay_fast(quick):
    import time
    prs = [_pr(9100 + i, f"g/{i}", body=_receipt(f"sess-{i}", [f"*{n}" for n in range(5500)])) for i in range(4)]
    start = time.perf_counter()
    m = w.build(prs, [], now=NOW, use_git=False)
    assert time.perf_counter() - start < 1.0
    assert m["gaps"]["receipts_with_files_cut"] == [9100, 9101, 9102, 9103]
    assert all(len(r["files"]) == w.FILES_LIMIT and r["files_cut"] == 5000 for r in m["prs"])
    assert "receipts listing more than 500 files, the rest not read: #9100" in w.markdown(m)


# ------------------------------------------------------------------ input given twice, and what git could not say

def test_a_pull_request_or_comment_given_twice_is_read_once(quick):
    p = _pr(290, "b/x", body=_receipt(B, ["greg/a.py"]), title="WU-11: attack stage")
    newer = {**p, "title": "WU-11: attack stage, rebased", "updated_at": "2026-11-12T11:00:00Z"}
    c = _comment(6794587797, OPENING_6794587797)
    m = w.build([p, newer, p], [c, c], now=NOW, use_git=False)
    assert (m["sources"]["open_prs"], m["sources"]["board_comments"]) == (1, 1)
    assert m["prs"][0]["title"].endswith("rebased")
    assert [o["pr"] for o in next(u for u in m["units"] if u["unit"] == "WU-11")["named_by"]] == [290]
    assert (m["gaps"]["duplicate_prs"], m["gaps"]["duplicate_comments"]) == ([290], [6794587797])
    assert {s["session"]: s["comments"] for s in m["sessions"]} == {B: 1}


def test_what_git_could_not_check_is_said_and_never_counted_as_zero(quick):
    prs = [_pr(1, "a/one", body=_receipt(A, ["greg/a.py"])),
           _pr(2, "b/two", base="merged/parent", body=_receipt(B, ["greg/b.py"])),
           _pr(3, "c/three", body=_receipt(C, ["greg/c.py"]))]
    m = w.build(prs, [], now=NOW, use_git=False, contained=lambda b: None, carried_by=lambda r: None)
    text = w.markdown(m)
    assert "(carried): not checked: 2 (#1, #3)" in text and "carried): 0" not in text
    assert "Git could not check 2 of the PRs headed for the line against it" in text   # a named unit may be carried
    assert m["gaps"]["prs_on_bases_not_checked"] == [2]
    assert "1 more may be stacked on bases git could not check here, #2: fetch origin" in text
    some = w.build(prs, [], now=NOW, use_git=False, contained=lambda b: False,
                   carried_by=lambda r: None if r["pr"] == 3 else False)
    assert "(carried): 0 of the 1 git could check; not checked: 1 (#3)" in w.markdown(some)
    assert w.on_line("no-such-branch-anywhere", ROOT) is None                 # git cannot say: not "off the line"


def test_a_clone_without_the_line_says_so(quick, stacked):
    repo, _child, _line = stacked
    assert not any("fetch origin" in n for n in w.build([], [], root=repo, line="line", now=NOW)["sources"]["notes"])
    notes = w.build([], [], root=repo, line="other-line", now=NOW)["sources"]["notes"]
    assert any("origin/other-line is not in this clone (fetch origin)" in n for n in notes)


def _history(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "line")
    _commit(repo, "base.txt")
    return repo


def test_a_stacked_pr_whose_own_commits_are_on_the_line_holds_nothing(tmp_path):
    repo = _history(tmp_path)
    _git(repo, "checkout", "-q", "-b", "parent")
    _commit(repo, "a.py")
    _git(repo, "checkout", "-q", "-b", "child")
    _commit(repo, "b.py")                                                      # the child's own work
    _git(repo, "checkout", "-q", "line")
    _commit(repo, "z.py")
    _git(repo, "merge", "-q", "--no-edit", "child")                          # the line takes it
    line_tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "parent")
    (repo / "b.py").write_text("the parent's version\n")
    _git(repo, "add", "b.py")
    _git(repo, "commit", "-q", "-m", "p2")
    parent = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "child")
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "merge", "-q", "--no-edit",
                    "parent"], cwd=repo, capture_output=True, env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull},
                   check=False)
    (repo / "b.py").write_text("both\n")                                       # the add/add conflict, resolved
    _git(repo, "add", "b.py")
    _git(repo, "commit", "-q", "--no-edit")
    child = _git(repo, "rev-parse", "HEAD")
    for name, sha in (("line", line_tip), ("parent", parent)):
        _git(repo, "update-ref", f"refs/remotes/origin/{name}", sha)
    pr = {"base": "parent", "head_sha": child}
    assert w.changed_files(pr, repo) == ["b.py"] and w.changed_files(pr, repo, against="line") == ["b.py"]
    assert w.own_files(pr, repo, line="line") == [] and w.carried(pr, repo, "line") is True
    rows = w.pr_rows([_pr(1, "child", base="parent", sha=child, body=_receipt(C, [])),
                      _pr(3, "parent", base="line", sha=parent, body=_receipt(A, [])),
                      _pr(2, "other", base="line", sha=line_tip, body=_receipt(B, ["b.py"]))], repo, line="line")
    assert [(c["file"], c["prs"]) for c in w.contended(rows, "line")] == [("b.py", [2, 3])]   # the parent's, not #1's


def test_several_merge_bases_do_not_lend_a_pr_its_parents_files(tmp_path):
    repo = _history(tmp_path)
    root = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "parent")
    p1 = _commit(repo, "a.py")
    _git(repo, "checkout", "-q", "-b", "head", root)
    h1 = _commit(repo, "b.py")
    _git(repo, "checkout", "-q", "parent")
    _git(repo, "merge", "-q", "--no-edit", h1)
    _git(repo, "checkout", "-q", "head")
    _git(repo, "merge", "-q", "--no-edit", p1)                               # criss-cross: two merge bases
    head = _commit(repo, "c.py")
    for name, sha in (("line", root), ("parent", _git(repo, "rev-parse", "parent"))):
        _git(repo, "update-ref", f"refs/remotes/origin/{name}", sha)
    warn = subprocess.run(["git", "diff", "--name-only", f"origin/parent...{head}"], cwd=repo, capture_output=True,
                          text=True, check=False)
    assert "multiple merge bases" in warn.stderr
    assert w.own_files({"base": "parent", "head_sha": head}, repo, line="line") == ["c.py"]


# ------------------------------------------------------------------ output files and failures

def test_an_output_path_that_is_a_link_or_a_pipe_is_written_through(quick, tmp_path):
    import stat
    import threading
    target = tmp_path / "target.json"
    target.write_text("old")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    assert w.main(["--json", str(link)]) == 0
    assert link.is_symlink() and json.loads(target.read_text())["authority"] == "none"
    fifo = tmp_path / "pipe.md"
    os.mkfifo(fifo)
    got: list = []
    reader = threading.Thread(target=lambda: got.append(fifo.read_text(encoding="utf-8")), daemon=True)
    reader.start()
    assert w.main(["--markdown", str(fifo)]) == 0
    reader.join(30)
    assert got and "## 6. Route drift" in got[0] and stat.S_ISFIFO(fifo.stat().st_mode)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["link.json", "pipe.md", "target.json"]


@pytest.mark.parametrize("mode", ["a", "w"])
def test_dev_stdout_is_written_through_its_descriptor_never_replaced(tmp_path, mode):
    log = tmp_path / "log.txt"
    log.write_text("earlier CI log line\n")
    inode = log.stat().st_ino
    with open(log, mode) as out:                                 # ">>" and ">" in a shell
        if mode == "w":
            out.write("earlier CI log line\n")
            out.flush()
        run = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "work_map.py"), "--now",
                              "2026-11-13T01:45:00Z", "--markdown", "/dev/stdout", "--paths", "greg/missions.py"],
                             stdout=out, stderr=subprocess.PIPE, timeout=180)
    assert run.returncode == 0, run.stderr[-400:]
    text = log.read_text(encoding="utf-8")
    assert log.stat().st_ino == inode and text.startswith("earlier CI log line\n# Work map\n")
    assert "## 6. Route drift" in text
    answer = json.loads(text[text.index("\n{\n") + 1:])
    assert list(answer)[-1] == "checkin" and answer["paths"][0]["path"] == "greg/missions.py"


def test_a_regular_output_is_replaced_whole_or_left_as_it_was(quick, tmp_path, monkeypatch):
    out = tmp_path / "map.md"
    out.write_text("previous map")
    first = out.stat().st_ino
    assert w.main(["--markdown", str(out), "--now", "2026-11-13T01:45:00Z"]) == 0
    written = out.read_text(encoding="utf-8")
    assert written.startswith("# Work map") and out.stat().st_ino != first      # a new file renamed into place

    def broken(*_a):
        raise OSError("disk full")
    monkeypatch.setattr(w.os, "replace", broken)
    assert w.main(["--markdown", str(out), "--now", "2026-11-13T02:45:00Z"]) == 0   # other text, failed rename
    assert out.read_text(encoding="utf-8") == written and sorted(p.name for p in tmp_path.iterdir()) == ["map.md"]


def test_an_internal_failure_is_reported_and_exits_zero(quick, monkeypatch, capsys):
    def broken(*_a, **_k):
        raise RuntimeError("boom")
    monkeypatch.setattr(w, "build", broken)
    assert w.main([]) == 0
    assert "work map not built (RuntimeError)" in capsys.readouterr().err


def test_an_empty_paths_list_still_gets_an_answer_and_a_bad_command_line_is_a_usage_error(quick, capsys):
    assert w.main(["--paths"]) == 0                              # `--paths $(git diff --name-only)` on no change
    answer = json.loads(capsys.readouterr().out)
    assert answer["paths"] == [] and list(answer)[-1] == "checkin"
    for bad in (["--board", "x"], ["--bogus"], ["--unit"]):
        with pytest.raises(SystemExit) as stop:
            w.main(bad)
        assert stop.value.code == 2, bad
    assert "a malformed command line is a usage error (exit 2)" in " ".join(w.__doc__.split())


def test_the_script_runs_without_docstrings(tmp_path):
    run = subprocess.run([sys.executable, "-B", "-OO", str(ROOT / "scripts" / "work_map.py"), "--now",
                          "2026-11-13T01:45:00Z", "--json", str(tmp_path / "m.json")], capture_output=True, text=True,
                         timeout=180)
    assert run.returncode == 0 and "not built" not in run.stderr, run.stderr[-400:]
    assert json.loads((tmp_path / "m.json").read_text())["authority"] == "none"


# What the stand-in for the map does with each file it is given (--markdown F, --json F), its exit code, and whether
# the weekly review must then say the map was not built.
_STUBS = {"exits 0 and builds nothing": (":", 0, True), "is killed": (":", 137, True),
          "leaves empty files": (': > "$a"', 0, True), "builds both": ('echo map > "$a"', 0, False)}


@pytest.mark.parametrize("case", list(_STUBS))
def test_the_weekly_review_says_when_the_work_map_was_not_produced(tmp_path, case):
    # The map exits 0 when it cannot build or write (it says so on stderr), so an exit-status test never fires.
    import shutil
    import yaml
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("no bash")
    steps = yaml.safe_load((ROOT / ".github/workflows/repository-review.yml").read_text())["jobs"]["review"]["steps"]
    run = next(s["run"] for s in steps if "work_map.py" in s.get("run", ""))
    lines = [x for x in run.splitlines() if re.search(r"work[-_ ]map", x)]
    each, code, reported = _STUBS[case]
    (tmp_path / "bin").mkdir()
    fake = tmp_path / "bin" / "python"
    fake.write_text(f'#!/bin/sh\nprev=\nfor a do\n  case "$prev" in --markdown|--json) {each} ;; esac\n  prev=$a\n'
                    f"done\nexit {code}\n")
    fake.chmod(0o755)
    (tmp_path / "review.md").write_text("# review\n")
    script = "\n".join(lines).replace("${{ github.repository }}", "owner/repo")
    env = {**os.environ, "PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"}
    done = subprocess.run([bash, "--noprofile", "--norc", "-eo", "pipefail", "-c", script], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr                     # never fails the job
    assert ("work map not built" in (tmp_path / "review.md").read_text()) is reported


def test_an_overlap_status_is_one_code_span_and_invisible_characters_are_gone(quick):
    forged = f"\u202eclear\u200b | `{A}` | claude | ACTIVE @dababiyoda <img src=x>"   # inside the 40 shown
    prs = [_pr(1, "x/one", body=_body(_coord(session_id="outsider-1", overlap={"status": forged})))]
    text = w.markdown(w.build(prs, [], now=NOW, use_git=False))
    row = next(x for x in text.splitlines() if x.startswith("| `outsider-1`"))
    assert re.fullmatch(r" `[^`]*` ", re.split(r"(?<!\\)\|", row)[-2]), row
    assert "\u202e" not in text and "\u200b" not in text


def test_the_paths_answer_names_open_prs_without_a_diff_and_ends_with_the_check_in(quick, tmp_path, capsys):
    src = tmp_path / "prs.json"
    src.write_text(json.dumps([_pr(1, "a/one", base="main", body=_receipt(A, ["greg/missions.py"]))]))
    assert w.main(["--prs-json", str(src), "--paths", "greg/missions.py"]) == 0
    answer = json.loads(capsys.readouterr().out)
    assert answer["sources"]["open_prs_without_diff"] == [1] and answer["paths"][0]["prs"][0]["pr"] == 1
    assert list(answer)[-1] == "checkin" and answer["checkin"] == w.CHECKIN_BLOCK


def _paths_answer(tmp_path, capsys, prs: list, *paths: str) -> dict:
    src = tmp_path / "prs.json"
    src.write_text(json.dumps(prs))
    capsys.readouterr()
    assert w.main(["--prs-json", str(src), "--paths", *paths]) == 0
    answer = json.loads(capsys.readouterr().out)
    assert list(answer)[-1] == "checkin"
    return answer


def test_a_pull_request_that_could_not_be_read_is_unknown_for_every_path(quick, tmp_path, capsys):
    bad = _pr(504, "g/odd", body=_receipt(C, ["greg/missions.py"]))
    bad["title"] = 504
    answer = _paths_answer(tmp_path, capsys, [bad, _pr(1, "a/one", body=_receipt(A, ["docs/x.md"]))],
                           "greg/missions.py")
    assert answer["sources"]["unreadable_prs"] == [504]
    assert (answer["paths"][0]["prs"], answer["paths"][0]["unknown_prs"]) == ([], [504])


def test_a_receipt_cut_or_unreadable_is_never_the_whole_answer(quick, tmp_path, capsys):
    big = _pr(505, "g/big", base="main", body=_receipt(C, [f"gen/f{i:03d}.py" for i in range(600)]))
    raw = json.loads(_coord(files="greg/missions.py"))                       # a string, which the check refuses
    odd = _pr(602, "g/odd", base="main", body=_body(json.dumps(raw)))
    bare = _pr(603, "g/bare", base="main", body="no receipt")
    plain = _pr(604, "g/plain", base="main", body=_receipt(B, ["docs/x.md"]))
    answer = _paths_answer(tmp_path, capsys, [big, odd, bare, plain], "gen/f550.py", "gen/f100.py")
    src = answer["sources"]
    assert (src["receipts_with_files_cut"], src["receipts_with_unreadable_fields"]) == ([505], [602])
    assert src["open_prs_without_diff"] == [505, 602, 603, 604] and "#505, #602, #603" in src["files_of_those"]
    far, near = answer["paths"]
    assert (far["prs"], far["unknown_prs"]) == ([], [505, 602, 603])         # #604's whole receipt was read
    assert ([p["pr"] for p in near["prs"]], near["unknown_prs"]) == ([505], [602, 603])
    capsys.readouterr()
    assert w.main(["--prs-json", str(tmp_path / "prs.json"), "--unit", "WU-11"]) == 0
    assert json.loads(capsys.readouterr().out)["sources"]["receipts_with_files_cut"] == [505]


def test_a_pr_into_the_line_that_declares_nothing_is_found_through_the_api_files(quick):
    # The 2026-11-13 entry trial: --paths missed #307 and #268, which change scripts/README.md without declaring it,
    # because their heads were not fetched in a fresh clone (docs/collaboration/VALIDATION.md, 2026-11-13).
    quiet = _pr(7, "c/quiet", body=_receipt(C, ["docs/other.md"]))
    stacked = _pr(8, "d/stacked", base="c/quiet", body=_receipt(C, ["docs/other.md"]))
    asked = []

    def reader(n):
        asked.append(n)
        return ["scripts/README.md", "docs/other.md"]
    read, failed = w.attach_api_files(REPO, [quiet, stacked], None, LINE, reader=reader)
    assert (read, failed, asked) == (1, [], [7])                 # a PR stacked on another branch is never read
    m = w.build([quiet, stacked], [], now=NOW, use_git=False)
    row = next(r for r in m["prs"] if r["pr"] == 7)
    assert (row["changed"], row["changed_via"]) == (["scripts/README.md", "docs/other.md"], "api")
    assert next(r for r in m["prs"] if r["pr"] == 8)["changed"] is None
    hits = w.who_touches(["scripts/README.md"], m["prs"], m["claims"], {"scripts/README.md"}, LINE)
    assert [(p["pr"], p["via"]) for p in hits[0]["prs"]] == [(7, ["api"])]


def test_a_failed_api_read_leaves_the_pr_without_a_diff_never_as_touching_nothing(quick):
    pr = _pr(9, "e/unread", body=_receipt(B, ["greg/a.py"]))

    def reader(_n):
        raise OSError("502")
    assert w.attach_api_files(REPO, [pr], None, LINE, reader=reader) == (0, [9])
    m = w.build([pr], [], now=NOW, use_git=False)
    assert next(r for r in m["prs"] if r["pr"] == 9)["changed"] is None
    assert 9 in w._answer_sources(m)["open_prs_without_diff"]


def _files_api(monkeypatch, pages: list[list]) -> None:
    """The files API answering ``pages`` (page 1 first), then empty pages."""
    def get(url, _token):
        page = int(url.rsplit("page=", 1)[1])
        return pages[page - 1] if page <= len(pages) else []
    monkeypatch.setattr(w, "_get", get)


def test_a_pr_that_renames_a_file_away_touches_its_old_name(quick, monkeypatch):
    pr = _pr(502, "g/rename", body=_receipt(C, ["docs/other.md"]))
    _files_api(monkeypatch, [[{"filename": "greg/mission_book.py", "previous_filename": "greg/missions.py",
                               "status": "renamed"}, {"filename": "greg/body.py", "previous_filename": None}]])
    assert w.attach_api_files(REPO, [pr], None, LINE) == (1, [])
    assert pr[w.API_FILES] == ["greg/mission_book.py", "greg/missions.py", "greg/body.py"]
    m = w.build([pr], [], now=NOW, use_git=False)
    hits = w.who_touches(["greg/missions.py", "greg/mission_book.py"], m["prs"], m["claims"], None, LINE)
    assert [[(p["pr"], p["via"]) for p in h["prs"]] for h in hits] == [[(502, ["api"])], [(502, ["api"])]]


def test_a_rename_in_local_git_counts_both_names(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "line")
    _git(repo, "config", "diff.renames", "true")
    (repo / "old.py").write_text("x = 1\n" * 40)
    _git(repo, "add", "old.py")
    _git(repo, "commit", "-q", "-m", "old")
    line_tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "parent")
    _commit(repo, "a.py")
    _git(repo, "checkout", "-q", "-b", "child")
    _git(repo, "mv", "old.py", "new.py")
    _git(repo, "commit", "-q", "-m", "rename")
    child = _git(repo, "rev-parse", "HEAD")
    for name, sha in (("line", line_tip), ("parent", _git(repo, "rev-parse", "parent"))):
        _git(repo, "update-ref", f"refs/remotes/origin/{name}", sha)
    assert sorted(w.own_files({"base": "line", "head_sha": child}, repo, line="line")) == ["a.py", "new.py", "old.py"]
    assert sorted(w.own_files({"base": "parent", "head_sha": child}, repo, line="line")) == ["new.py", "old.py"]


@pytest.mark.parametrize("batch", [[{"name": "greg/missions.py", "status": "modified"}],
                                   [{"filename": "greg/body.py"}, {"name": "greg/missions.py"}],
                                   [{"filename": "greg/body.py"}, "greg/missions.py"],
                                   [{"filename": "greg/body.py", "previous_filename": 7}]])
def test_a_file_list_with_an_entry_it_cannot_read_is_not_read(quick, monkeypatch, batch):
    pr = _pr(501, "g/odd", body=_receipt(C, ["docs/other.md"]))
    _files_api(monkeypatch, [batch])
    assert w.attach_api_files(REPO, [pr], None, LINE) == (0, [501])
    m = w.build([pr], [], now=NOW, use_git=False)
    assert 501 in w._answer_sources(m)["open_prs_without_diff"]


def test_a_file_list_the_api_may_have_cut_at_3000_is_not_read(quick, monkeypatch):
    pr = _pr(503, "g/huge", body=_receipt(C, ["docs/other.md"]))
    files = [{"filename": f"gen/f{i:04d}.py"} for i in range(3000)]
    _files_api(monkeypatch, [files[i:i + 100] for i in range(0, 3000, 100)])
    assert w.attach_api_files(REPO, [pr], None, LINE) == (0, [503])
    _files_api(monkeypatch, [files[i:min(i + 100, 2950)] for i in range(0, 2950, 100)])   # 29 full pages, one short
    assert w.attach_api_files(REPO, [pr], None, LINE) == (1, []) and len(pr[w.API_FILES]) == 2950


def test_a_local_diff_wins_over_the_api_files(quick, monkeypatch):
    pr = dict(_pr(10, "f/local", body=_receipt(B, ["greg/a.py"])), _api_files=["greg/api.py"])
    monkeypatch.setattr(w, "own_files", lambda *_a, **_k: ["greg/local.py"])
    row = next(r for r in w.build([pr], [], now=NOW)["prs"] if r["pr"] == 10)
    assert (row["changed"], row["changed_via"]) == (["greg/local.py"], "diff")


def test_the_check_in_block_can_be_filled_before_the_first_edit():
    # The trial's session A posted after its edit, push and PR: the block asked for the head, the PR number and the
    # results, which exist only afterwards (docs/collaboration/VALIDATION.md, 2026-11-13).
    block = w.CHECKIN_BLOCK
    assert "→ pending" in block and "(PR: pending)" in block and "draft #<n>" not in block
    assert "<sha> → <sha>" not in block and "results go in the PR" in block
    labels = [line.split(":", 1)[0] for line in block.splitlines()[2:]]
    assert labels == ["- Session", "- Prompt", "- Plan", "- Route", "- Guidance read",
                      "- Repository / branch / base → head", "- Files / interfaces", "- Depends on",
                      "- Overlap inspected and split", "- Acceptance evidence", "- Reviewer / integrator · Destination",
                      "- Next action / blocker / handoff condition", "- Recheck (UTC)"]


def test_the_map_says_to_post_before_any_edit_commit_or_push(quick):
    text = w.markdown(w.build([], [], now=NOW, use_git=False))
    assert "before any edit, commit or push" in text and "coordination.task_ref" in text


# ------------------------------------------------------------------ joins and claims the board checks

def test_a_task_ref_joins_only_a_claim_and_never_against_its_heading(quick):
    cite = "https://x/issues/96#issuecomment-6000000002"
    prs = [_pr(5, "b/x", body=_receipt(B, ["greg/a.py"], task=cite))]
    update = w.build(prs, [_comment(6000000002, "## Update: CI is red on #9\n\nRe-run pending.\n")], now=NOW,
                     use_git=False)
    assert [g["comment"] for g in update["gaps"]["recent_posts_unresolved"]] == [6000000002]
    assert {s["session"]: s["inferred_comments"] for s in update["sessions"]} == {B: 0}
    other = w.build(prs, [_comment(6000000002, f"## Claim: finish `{C}`'s seam\n- **Files:** `greg/a.py`\n")],
                    now=NOW, use_git=False)
    assert (other["claims"][0]["how"], other["claims"][0]["inferred_session"]) == ("unresolved", None)


def test_a_unit_named_by_an_old_claim_is_not_claimed_on_the_board(quick):
    claim = _comment(6400000101, f"## Claim: WU-05 node revocation · `{B}`\n- **Files:** `greg/nodes.py`\n",
                     at="2026-11-04T00:00:00Z")
    for later in (f"## Note · `{B}`\n\nStill here.\n", f"## Note · `{B}`\n\nStill on claim 6400000101.\n"):
        m = w.build([], [claim, _comment(6400000102, later, at="2026-11-13T01:00:00Z")], now=NOW, use_git=False)
        unit = next(u for u in m["units"] if u["unit"] == "WU-05")
        assert (unit["state"], unit["claimed_on_board"]) == ("unclaimed", []), later
    assert _claim(m, 6400000101)["state"] == "active"                       # cited an hour ago, posted nine days ago


def test_each_disclaiming_cue_drops_only_its_own_path():
    tracked, dirs = {"greg/a.py", "greg/b.py"}, {"greg"}
    for sentence in ("`greg/b.py`, and leave `greg/a.py` to #278", "`greg/b.py`, `greg/a.py` = #278",
                     "`greg/b.py`; `S71.A1` out (`greg/a.py`)", "`greg/b.py`, `greg/a.py` hot",
                     "`greg/a.py` is read, never edited; `greg/b.py`", "`greg/b.py`. Founder reviews `greg/a.py`."):
        assert w.declared_files(sentence, tracked, dirs) == ["greg/b.py"], sentence


def test_a_comment_whose_author_a_join_inferred_does_not_refresh_a_claim(quick):
    claim = _comment(6400000201, f"## Claim: seam · `{B}`\n- **Files:** `greg/authority.py`\n", at="2026-11-04T00:00:00Z")
    note = _comment(6400000202, "## Note\n\nRe my claim 6400000201: still working on it.\n", at="2026-11-13T01:00:00Z")
    c = _claim(w.build([], [claim, note], now=NOW, use_git=False), 6400000201)
    assert (c["state"], c["session_activity"]) == ("dormant", "active")       # the join counts as activity only


def test_a_pull_request_whose_row_cannot_be_built_is_cited_not_fatal(quick, monkeypatch):
    real = w.receipt_of

    def fragile(body, *a, **k):
        if "boom" in (body or ""):
            raise RecursionError("too deep")
        return real(body, *a, **k)
    monkeypatch.setattr(w, "receipt_of", fragile)
    m = w.build([_pr(1, "a/one", body=_receipt(A, ["greg/a.py"])), _pr(2, "b/two", body="boom")], [], now=NOW,
                use_git=False)
    assert [r["pr"] for r in m["prs"]] == [1] and m["gaps"]["unreadable_prs"] == [2]
