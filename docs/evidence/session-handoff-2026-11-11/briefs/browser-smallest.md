# Brief: the smallest browser.render repair that passes the declared requirements

Work only in the worktree named in the message that sent you here. Commit locally. Push nothing. Post nothing.

## The founder's decision (verbatim, 2026-11-12)

"Browser repair: compare the minimal reorder with the larger browser check under the relevant supported conditions.
Recommend the smallest implementation that passes the declared requirements. Show any remaining compatibility
boundary."

## Context

Draft #293 (`32ca8de7`, branch `claude/browser-render-qualified-binary-20261111`, base `8d205324`) repairs
`browser.render`: on the base, `chrome_binary()` returns `/usr/bin/google-chrome`, which never returns from a
one-shot headless render in this container, while the headless shell beside it renders in half a second. Read
`docs/evidence/greg-browser-binary/2026-11-11/README.md` on that branch first: it separates a four-line reorder (the
"baseline") from the larger change (#293 judges each installed browser by a trial render, remembers the result, and
falls through to the next), and it lists what holds with or without the trial render.

Its own measurement: with the real browsers of this container the four-line reorder does everything #293 does. The
larger check is shown to matter only with stand-in browsers (shell scripts), and it has costs (up to 45 s per browser
that never returns, a memory that can go stale, helper processes left behind).

## Declared requirements (the test of "passes")

R1. On a body with an installed browser that renders, `browser.render` renders through a signed mission and the
    separate appraiser verifies the closure.
R2. On a body with no browser, the capability is UNAVAILABLE by name; no test counts that as a pass
    ("Do not count a missing browser dependency as a passing test").
R3. `GREG_CHROMIUM` naming a working browser is honoured, and a closure made with it is VERIFIED by the appraiser's
    separate process (the manifest must not name a binary fixed at import).
R4. `GREG_CHROMIUM` naming nothing executable is refused by name; nothing else is run in its place.
R5. A build directory replaced while the body runs does not make the capability unavailable.
R6. A render that does not finish is a timeout, recorded as such, never a rendered page and never a measured failure
    of the page's content.
R7. On a confined-egress body no browser is started outside the namespace.

## What to do

1. Create branch `claude/browser-render-smallest-20261112` from `8d205324` in the worktree. Build the **small
   variant**: the candidate-order change (headless shell first, both spellings of the build directory) plus exactly
   the parts of #293 that R1 to R7 need and that do not depend on the trial render, its memory or the fall-through
   (the evidence note's section "What does not depend on the check" is the starting list; verify each against the
   code, do not take the note's word). Port #293's tests for those requirements; drop only tests that test the trial
   render itself.
2. Run the same requirement tests against three trees: `8d205324`, the small variant, and #293 (`32ca8de7`). Use real
   browsers where this container has them, with `GREG_REQUIRE_BROWSER=1` so nothing skips. Conditions to run for each
   tree where it can be run here: both browsers present; the headless shell hidden (only the full browser, which
   never returns here); no browser; `GREG_CHROMIUM` right; `GREG_CHROMIUM` wrong; a build directory replaced mid-run;
   the appraiser as a separate process. Record for every cell: passed / failed / timed out / could not be run here
   (and why). Record wall time per cell.
3. For each stand-in case in #293's evidence note, say whether any R1 to R7 requires it. A case no requirement needs,
   and that no real machine has shown, counts as cost, not as a pass.
4. Count the two diffs against `8d205324` (product lines, test lines, new moving parts such as caches and timeouts).
5. Write `docs/evidence/greg-browser-binary/2026-11-12/COMPARISON.md`: the requirement table (three trees by seven
   requirements by condition), the costs, and one recommendation: the smallest tree that passes R1 to R7. State the
   remaining compatibility boundary plainly: what is not known because it could not be run here (macOS, the founder's
   Chromebook, a GitHub runner, a body with bubblewrap, a non-root user whose Chrome refuses its sandbox), and the one
   observed condition under which the small variant behaves worse than #293, if there is one, with its measured cost.
   If the small variant fails a requirement, say which, and recommend the smallest addition that fixes it.
6. A mutation gate for the small variant's decision points, in the repository's style, if the variant is recommended.

## Rules

- Never edit `constitution/*.ucl`, `authority/*.yaml`, `identity/*.yaml`, `policy/consequence_gate.py`,
  `governance/integrity/*`.
- Python: `/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/venv/bin/python`. Never
  `pip install`; never run `playwright install`. Chromium is under `/opt/pw-browsers`.
- One pytest process at a time. Kill only pids you started, never by name: other workers run browsers too. Clean up
  every browser process and temp profile you start.
- A browser that hangs costs 45 s per call: plan runs so the whole comparison stays under about 40 minutes.
- Do not lower a requirement after seeing a result. Read every number from output. Write plainly. No model name in
  any file or commit. Commit trailer, exactly:
  `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01Kucyfm9exT5imDVYvHTYSv`
- Before the final commit run `stale_anchor_scan.py` and `gates_for_changes.py` from
  `/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/` against `8d205324`, and RUN the gates
  the second lists.

## Report (raw facts)

The commit SHA; the requirement table; the two diff sizes; the recommendation in one sentence; the compatibility
boundary; every cell you could not run and why; anything that contradicts the 2026-11-11 evidence note.
