# browser.render: which installed browser, and what the check adds over a four-line change

Draft PR #293. Measured 2026-11-11 in one cloud container: Linux, root, Chrome for Testing 153.0.8010.12 installed by
Playwright under `/opt/pw-browsers` (build 1243: the full browser and the headless shell), `/usr/bin/google-chrome` a
shell wrapper around the full browser. No bubblewrap, no Playwright for Python, no macOS, no founder device, test keys
only. Nothing here is founder-used or externally verified.

## The defect

On `8d205324`, `chrome_binary()` returns `/usr/bin/google-chrome`. That binary never returns from a one-shot
headless render in this container; the headless shell beside it renders in about half a second.

| Tree | `tests/unit/test_greg_browser.py` | A signed mission whose check is browser.render |
| --- | --- | --- |
| `8d205324` | 1 passed, 2 skipped in 92.17 s (both skips: "browser did not finish rendering within 45 seconds") | refused at 45 s per tick, never closes (reviewer's run) |
| `8d205324` + the four lines below | 3 passed in 6.34 s (`GREG_REQUIRE_BROWSER=1`) | ACHIEVED, appraised VERIFIED at tick 1 |
| this branch | 3 passed in 4.80 s (`GREG_REQUIRE_BROWSER=1`), 3 passed without it | ACHIEVED, appraised VERIFIED at tick 1 |

## The baseline: four changed lines

```diff
-    for candidate in (os.environ.get("GREG_CHROMIUM", ""), *CHROME_CANDIDATES,
-                      *sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))):
+    shells = sorted(glob.glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"),
+                    reverse=True)
+    for candidate in (os.environ.get("GREG_CHROMIUM", ""), *shells, "/usr/bin/chrome-headless-shell",
+                      *CHROME_CANDIDATES, *sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))):
```

It puts the headless shell first and matches both spellings of the build's OS directory. **With the real browsers
of this container it does everything the branch does**: the same three tests pass and the same mission closes. No
real-browser measurement here separates the branch from it.

## What the check, its memory and the rules around them handle, shown only with stand-in browsers

Stand-ins are shell scripts that write a page, never return, fail, or write nothing
(`tests/unit/test_greg_browser_binary.py`). The first and fourth rows were also run against the baseline tree, with
both trees' 45 second limit shortened to 2 seconds.

| Case | `8d205324` + four lines | This branch |
| --- | --- | --- |
| The first installed browser never returns, a later one renders | three calls, 2.0 s each, each refused; the browser that renders is never run | call 1 takes 2.0 s and renders with the later browser; calls 2 and 3 render with it in 0.0 s |
| No installed browser returns (real browsers, headless shell hidden) | 45 s on every call (not re-measured for the baseline; it is the unchanged tree's behaviour) | call 1: 90.9 s, refusal naming both; call 2: 0.0 s, the same refusal |
| A browser exits 0 without writing the page, or writes another page | it is used: each render is refused or returns that other page, and no later candidate is tried (read from the unchanged code, not run) | it is refused by name with the reason; the next candidate is tried |
| `GREG_CHROMIUM` names nothing executable | the first installed browser is run in its place, without a word | refused, naming the variable and its value; nothing else is run |
| No browser is installed | through the office, UNAVAILABLE from the precheck, naming a macOS path; `FileNotFoundError` from the adapter called directly (read from the unchanged code, not run) | through the office, UNAVAILABLE "no Chrome or Chromium is installed on this body"; `CapabilityError` with the same words from the adapter called directly |

A real machine where the first installed browser cannot render and a later one can was not found. Once the headless
shell is listed first here, it renders. So the fall-through is a property shown on stand-ins only.

## What the check costs

- One extra browser start per build of a binary (0.4 s for the headless shell here), outside any namespace, on an
  unconfined body only.
- Up to 45 s for each candidate that never returns, once per ten minutes. One call starts no check after 60 s of
  judging (`JUDGING_SECONDS`), so at most two such candidates are judged in one call; the rest are named as not
  judged and the next call starts with them.
- A memory that can go stale. It is keyed on the file the candidate path names, which here is a wrapper script: a
  real binary replaced behind the wrapper kept its success. A render that never returns, or cannot be started, now
  forgets it. A browser that passes the check and never returns from real pages is still not passed over.
- A timed-out browser leaves helper processes. In the first real run of this work, removing the check's profile
  raised `OSError: [Errno 39] Directory not empty` and that error replaced the check's answer; removal is now retried
  and never replaces the answer. In a later real run (two timed-out checks) two empty `greg-browser-check-*`
  directories were left in `/tmp`; in a third run (one timed-out check) the directory was removed at the first
  attempt. The browser's process group is not killed at the limit. The render's own profile has the same behaviour
  on `8d205324`.

The baseline has none of these costs, and none of the stand-in rows above.

## What does not depend on the check

These hold with or without it and would be needed with the baseline too:

- The manifest names no binary and `available()` asks what is installed each time. Before, the manifest named a path
  at import. With `GREG_CHROMIUM` naming a working browser other than the default, a true closure was appraised
  REFUTED on `8d205324` and on `46ab6f89` (reviewer's runs; reproduced here on `da2aff57`): the appraiser's process
  is started without the variable and derived another manifest digest. It is VERIFIED now. With a build directory replaced while the body ran, browser.render
  was UNAVAILABLE with a working browser installed (reviewer's simulation on `46ab6f89`, reproduced on `da2aff57`);
  the same replacement renders now. The baseline would have made the
  manifest name the versioned headless-shell path as well.
- On a confined-egress body nothing is judged: the first installed candidate is handed to the namespace, as on
  `8d205324`. The check is not run inside the namespace because no bubblewrap exists here to verify such a check.
- A build directory name that ends in a digit `int()` refuses no longer raises.

## Not checked

- The confined route with real bubblewrap: whether the headless shell renders inside the namespace. The tests that
  would show it skip here.
- A machine where Chrome refuses its own sandbox for an ordinary user (this container runs as root).
- macOS, the founder's Chromebook, a GitHub runner. Whether the full Chrome binary fails to return anywhere else is
  not known.
- `GREG_REQUIRE_BROWSER=1` is set by no workflow, so in CI the real-browser tests still skip where no browser
  renders.
