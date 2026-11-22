# Recovering when admission fails

What `scripts/participation.py` does in each case, and the step that gets you admitted again. Each case was run against the script at `272af40`. Admission coordinates work and grants nothing. Never write or edit `<git dir>/uniimente/admission.json` by hand: run `admit` again, and it replaces the record in one step.

## 1. The GitHub API is unavailable

- **What happens.** `admit` reads the task issue, board #96 and every task issue #96 indexes, first with `gh api`, then with `curl` against `api.github.com`. If both fail, or a read is cut off after 3,000 comments, it prints `refused: incomplete: could not read <repo>#<n> (...)` and exits 1. Nothing is written. A read it could not finish is never treated as "no conflict".
- **`check` while the API is down** fails the same way. It also sets `refresh_required` on your existing record, so the hook denies every edit, commit and push in that worktree until a `check` succeeds.
- **Recover.** Find the failing read in the message, then check `gh auth status` and whether `curl -sS https://api.github.com/repos/dababiyoda/uniimente-kernel/issues/96` answers through your proxy. Once it does, run `check`, or `admit --issue <N> --claim <id>` if you have no record yet. `--comments-json` replays a saved file for tests. It does not replace a live read.

## 2. The admission record is malformed

- **What happens.** The hook reads `<git dir>/uniimente/admission.json`. With no record, edits, `git commit`, `git push` and GitHub write tools are denied with `No valid admission in <worktree>`.
- **A record of the wrong shape** is denied the same way, with exit 2 and the reason named: `malformed (missing or wrong fields: [...])` or `malformed (the record is not a JSON object)`. This covers `{}`, `"x"`, and a record missing `claim`, `task_record`, `exclusive`, `shared` or `checked_at`. `check` refuses with `no admission here`. Before `deefd0f`, such a record crashed the hook with exit 1.
- **A commit or push is judged in the worktree it targets** (`git -C <dir>`, or the last `cd <dir>` before `git`), not in the shell's cwd. Admit in the worktree you commit from.
- **Recover.** Run `python scripts/participation.py admit --issue <task issue> --claim <your check-in comment id>` in that worktree. Each worktree needs its own record.

## 3. python3 is missing

- **What happens.** `.claude/settings.json` runs the hook as `python3 "$CLAUDE_PROJECT_DIR/scripts/participation.py" hook`. Without `python3` on the PATH the command exits 127. `onFailure: "block"` asks the client to withhold the tool call; this run did not test whether the client honours it. The resume hook has no such setting. If it fails, your record is not marked stale after a resume.
- **Recover.**
  1. Install Python 3 or put it on the PATH as `python3`. The script uses only the standard library, `git`, and `gh` or `curl`.
  2. Run `check` yourself after any resume, since the resume hook may not have run.
  3. Do not change the hook command to suit your machine; that file is another claim's concern.

## 4. The claim was released or handed off

- **What happens.** `admit` and `check` refuse with `claim <id> is released (...)` or `is transferred (handed off by <h>, accepted by <c>)`, adding "a former holder cannot revive it". A failed `check` sets `refresh_required`, so an old admission stops allowing edits and pushes. Edits made before that `check` are not caught.
- **Recover, former holder.** Stop. To work again, post a new check-in on the task issue and admit it. It is ordered after every claim posted before it.
- **Recover, receiver.** Post a check-in that keeps the same concerns and adds `- Accepts handoff: <handoff comment id>`. The handoff must name you in `To:` and your predecessor in `From:`, and your check-in must be posted after the handoff; an earlier one does not accept it. Then admit your new check-in. It keeps the original claim's place in the order.
- **Keep the heading plain.** A check-in whose heading says "handoff", "review" or "reassignment" is refused as `names no session`. Name the work instead ("continue RECOVERY.md"), and keep the word for the `Accepts handoff:` line.
- **The holder went silent.** Only a maintainer session (`MAINTAINER_SESSIONS`, today the integrator) can end the claim, with a `<!-- uniimente:recovery -->` comment, and only once the claim's own `Recheck` time is more than 24 hours past. A claim with no Recheck time is never stale. Recovery admits nobody: post your own check-in and admit it. Until then, ask the holder for a handoff on the task issue.
