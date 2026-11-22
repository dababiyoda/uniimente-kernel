# Participation: claim, admit, then edit

How-to for `scripts/participation.py`. The task's work issue is the record; board #96 holds only
`<!-- uniimente:index -->` lines (`- Task record: #N`, `- Task: KEY`) that point to it. A claim
coordinates work and grants nothing. Each block below is its own issue comment, its marker alone on line one.

## 1. Check in
Post the block `python scripts/work_map.py` prints, as a new comment on the task issue, plus:
- `- Session: session_…` first after the heading, one id, your own. The heading avoids handoff and review wording.
- `- Task: PARENT-KEY/subtask`, e.g. `COORD-20261122/trial`.
- ``- Concern (exclusive): `path` `` for what only you change; ``- Concern (shared): `path` `` for what others may too.
- Optional: `- Depends on: PARENT-KEY/subtask`, and `- Accepts handoff: <handoff comment id>`.
Never edit a posted claim. To correct it, post a new check-in and admit that one.

## 2. Admit
In the worktree you will edit: `python scripts/participation.py admit --issue <N> --claim <comment id>`.
- Two active claims whose exclusive concerns overlap conflict; the one GitHub numbered first wins.
- A losing claim is refused with the holder's session and claim URL. Narrow it, ask for a split or a handoff, or wait.
- An unreadable or truncated read is "incomplete" and refuses; it is never read as clear.
- Success writes `<git dir>/uniimente/admission.json`. Each worktree needs its own admission.

## 3. Work under the hook
Where `.claude/settings.json` loads, the PreToolUse hook logs to `<git dir>/uniimente/gate.jsonl` and:
- denies Edit/Write/MultiEdit/NotebookEdit, `git commit`, `git push` and GitHub write tools without admission;
- denies an edit outside your exclusive and shared concerns (widen the claim, then admit again);
- denies a push or GitHub write unless `check` ran within the last 30 minutes.
On resume or compaction every admitted worktree is marked stale until `check` runs.

## 4. Check
`python scripts/participation.py check` re-reads the board for the claim this worktree admitted and
refreshes the record. A refusal (a later conflict, a release, a handoff) leaves the record stale.

## 5. Status
`python scripts/participation.py status --issue <N> [--task KEY/sub] [--concern path ...]` lists the
claims matching that task, subtask, concern or dependency, with `coverage` complete or incomplete.

## 6. Release
The holder posts `<!-- uniimente:release -->`, then `- Claim: <claim id>` and `- Session: <own session id>`.
A released claim cannot be admitted again.

## 7. Handoff
The holder posts `<!-- uniimente:handoff -->`, then `- Claim: <claim id>`, `- From: <holder session id>`
and `- To: <receiver session id>`. The receiver posts a new check-in with
`- Accepts handoff: <handoff comment id>` and admits it. The receiver keeps the original claim's place
in order; the former holder cannot re-admit.

## 8. Acknowledge a dependency
A dependent claim names `- Depends on: <producer's task key>`. The producer posts
`<!-- uniimente:ack -->`, then `- Dependency of: <dependent claim id>`,
`- Contract: <the revision or provisional contract it may consume>` and `- Session: <producer session id>`.
Until then `admit` and `status` show the dependency as pending.

## Limits
A declared session is not an authenticated principal. Shell writes other than commit and push are not gated.
Clients that ignore `.claude/settings.json` (multi-repository cloud sessions) get guidance only; there
`python scripts/participation.py contribution --task-ref <check-in URL> --session <id>` checks at acceptance.
