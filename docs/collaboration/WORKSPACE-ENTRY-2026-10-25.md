# Workspace entry installation — October 25, 2026

Founder request: improve the protocol so everyone entering the workspace knows how to work inside it. Completion boundary remains BODY + ORGANS + MIND. This change improves contributor discovery, not GREG's runtime authority.

## Existing mechanism and missing seam

Kernel AGENTS.md/CLAUDE.md already route to START_HERE, Discussion #89 and board #96. #193 owns the shared protocol; its ROLLOUT/VALIDATION records preserve consumer entry drafts and real Claude-session evidence. #197/#199 and the fresh-receiver record already prove a bounded handoff example. They must not be duplicated or reset to NOT_RUN.

The current shared workspace, above the repositories, lacked entry files. Opening that directory did not expose the repository-level team front door. scripts/workspace_entry.py fills that gap by installing pointers for AGENTS.md, CLAUDE.md, .github/copilot-instructions.md and an always-apply Cursor rule. Each points to one existing local Kernel guide and the live work board, retaining target-repository and nested engineering rules.

The entry checklist makes the first action concrete: identify source revision, repo/branch/head, intended outcome, actual task identity, scope, overlapping claims, next action and blocker. It routes material decisions to the existing five-role/two-pass process and handoffs to the existing v2 receipt. It explicitly forbids fabricated review or acknowledgment. No second SOP or authority plane is created.

## Installation and use

From the reviewed Kernel checkout:

```sh
python scripts/workspace_entry.py --workspace /absolute/workspace --install
python scripts/workspace_entry.py --workspace /absolute/workspace
```

Use --kernel /absolute/kernel-checkout when the script and desired guide live in different checkouts. Generated pointers contain absolute local paths; regenerate for a new machine or directory. The installer never edits repository branches or existing instructions. It refuses conflicting files, including locally modified generated files, rather than overwriting them. Check mode writes nothing. Symlinked destination files and parent directories are refused. It makes no network calls and handles no credentials.

An install preflights all destinations. Exclusive creation prevents overwriting a file created after preflight. This is not a filesystem transaction or a hostile-host security boundary: concurrent directory changes or a write failure can leave a partial install; inspect and rerun the check. Do not run competing installers on the same workspace.

Installed locally in /workspace/scratch/a60f90b8f5e5, pointing to the reviewed workspace-entry checkout. The follow-up check reports matching pointers. This is local installation evidence, not default-branch adoption.

## Exactly two strengthening passes

Five explicit self-review perspectives, all from the one Codex implementer:

| Role | Position / concern |
| --- | --- |
| Founder-Intent Steward | Improve actual entry discoverability while preserving the full machine, not adding another protocol catalog. |
| Systems Architect | Reuse START_HERE and existing consumer rollout; root pointers do not supersede local rules or create authority. |
| Adversarial Reviewer | Existing instructions and local additions must survive; check must not write; reject link-based path redirection. |
| Operator and Maintainer | One stdlib command installs and checks pointers; explicit session check-in and handoff reduce reconstruction. |
| Evidence and Welfare Guardian | File presence does not prove reading, client enrollment, comprehension or successful collaboration. Preserve the real-session evidence and current limits. |

**Pass 1.** Baseline: repository pointers exist but the shared workspace entry does not. Do nothing leaves that gap. Simplest alternative is manually copying full SOP text; rejected because it drifts. Strongest competitor is client-specific managed settings plus mandatory acknowledgment gates, which needs access to each client and broader policy decisions. Selected reversible approach: local pointer installation and drift check, using supported instruction filenames without changing client settings.

Advantages: clear first action, one guide, no copied policy, no dependencies or background service. Downside D1: overwriting local instructions; redesign: create missing files only and preflight all destinations. D2: false universal-enforcement claim; redesign: explicitly distinguish discovery, adoption and observed behavior. D3: absolute paths become stale; redesign: non-writing check plus explicit relocation instructions.

**Pass 2.** Attack the safeguards: an edited managed file could lose local additions; test refusal even when its marker remains. A directory symlink could redirect output; refuse symlink path components. Process inflation could create a second SOP; keep pointers short and route exact details to the existing protocol. A partial/racing install could look complete; make check the final acceptance step and document that multi-file installation is not transactional.

| Downside | Disposition | Owner / review trigger |
| --- | --- | --- |
| D1 | Resolved for ordinary conflicts: no existing differing instruction is replaced; tests cover preservation | Workspace maintainer; rerun after local changes |
| D2 | Accepted limit: clients can ignore instructions; no universal compliance claimed | Integrator; actual first-run/resume test in each client |
| D3 | Accepted: location-bound pointers are deliberate, and check detects disagreement with the chosen source | Workspace maintainer; relocation or source checkout replacement |

Dissent: managed client configuration could provide stronger enrollment than instruction files. Preserve that alternative; revive when the user authorizes access to those actual settings and client-specific tests. No independent reviewer or receiving session has acknowledged this change. Decision: **EXPERIMENT** — installed in this authorized workspace; wider adoption remains draft.

## Validation and remaining work

Five stdlib tests pass: read-only missing check, repeatable install, conflicting-file preflight, modified-file preservation, symlink refusal and absent-guide refusal (some combined in one case). Existing collaboration-receipt suite: 49 tests pass. Workspace install and subsequent check both succeeded. No actual new client session was launched, and no claim of agent comprehension is made.

Opening a repository separately may stop parent-instruction discovery at the repository boundary. Existing consumer AGENTS/CLAUDE rollout remains necessary; this change does not claim those pending PRs are merged. Clients that ignore these filenames need their normal startup prompt/settings pointed to START_HERE. Private chats, user-device configuration, global skills and external-client settings are not modified.

Claim: board #96 comment 6398846416. Actual implementer: Codex /root, workspace a60f90b8f5e5, task workspace-entry. Base #196 fa80ace79eb1ac2cc4bf745918baf5587e1ae3f6; own child branch. Integration owner session_01FBS4KNJR59nSbdGbxo8Mbx; independent reviewer unassigned; receiver acknowledgment pending. No owner branch edits, merge, deployment, spending or activation authority.

Rollback: remove only generated workspace pointers after confirming they still match expected content; preserve any local additions. Revert this component commit if not adopted. Kill the installer if it overwrites user content, duplicates the canonical SOP, weakens authority, or claims file presence is proof of collaboration. Next owner action: exact-head review and client-specific entry/resume evidence before claiming wider adoption.
