# Cathedral detector and reality-claim guard (WU-13), 2026-10-30

Directive 2026-10-28, sections 10, 55, 56, 67, 70 and 73. Founder correction of 2026-10-30
(`INTENT-20261030-BUILD-BEFORE-DEVICE-RUN`). Branch `claude/cathedral-detector-20261030`, based on `44b3df96`
(#236 head, WU-01 build frontier). Review round 1 (two reviewers, 16 findings) was fixed on top of `65f91d2f`; review
round 2 (20 findings) on top of `71342170`. The PR base was then merged in three times: `c5ee7f8a` at `849c7973`,
`954c6846` at `fbce94e5`, and `1cc6645d` at `d35d92a5`. The last merge came after `631b40ec`, which pins the mutant
gate's five survivors on top of `938f6523` (see the mutant history). The pass-after figures below are from `1cc6645d`.

**Reality level: UNIT-TESTED.** Synthetic git repositories and real test-key and passphrase-protected test bodies,
all in this Linux container. Nothing here is founder-used, live or externally verified, and the detector has never
read the founder's body.

## What it is

- `greg/cathedral.py` evaluates the first clause of the constitution's `cathedral` kill condition ("activity rises
  while external outcomes remain unchanged"), read through `compiler/ucl_compiler.py`, over a window `[since, until)`
  (default 30 days).
  - **Activity** comes from git objects on HEAD: commits by committer time, PR-like merges (more than one parent, or
    a GitHub merge subject), and the files those commits added (`.md`, `.py`, evidence READMEs). Renames are not new
    files; a merge counts the files it added itself (new against every parent). Replace refs are ignored
    (`GIT_NO_REPLACE_OBJECTS=1`), so `git replace --graft` cannot cut the history. Git is read in the given
    repository only: the caller's `GIT_*` variables are dropped, and a directory inside another repository or a
    partial clone is refused.
  - **Outcomes** are founder-tier only, on the founder's designated body only, read on the ledger at `since` and at
    `until` (an in-memory, re-verified prefix of the append-only ledger, refused when record times run backwards
    across either edge):
    - closures whose VEPMC row shows `founder_body` (designated body and platform, registered after the designation),
      `appraised_verified` and no fixture evidence, of missions `greg.metrics.founder_tier` puts at the founder tier;
    - VEPMC `founder_tier_count`;
    - nodes achieved on the founder's path (`greg.path.position`).
  - **Vertical progress** (build frontier, newly built nodes, structural depth, closures not counted) is reported
    beside the outcomes and never counted as one.
  - **Verdicts:**
    - `CATHEDRAL`: activity reached its floor while no outcome moved;
    - `NOT_CATHEDRAL`: an outcome moved, or activity stayed under every floor;
    - `INSUFFICIENT_HISTORY`: git cannot show the window in full (shallow clone, with its first-parent depth, its
      reachable commits and no counts; a grafts file; a partial clone; no repository, or a path that is not its top),
      or no body ledger was read, or the ledger does not cover the window as the founder's body. That last case
      covers four situations: the ledger begins after the window ends, its record times run backwards across the
      window's edge, it carries no founder-signed designation, or the designation came after the window started and
      nothing moved. An outcome that moved inside the covered part still decides `NOT_CATHEDRAL`, unless the times
      run backwards.
    - **In the build phase every real run is `INSUFFICIENT_HISTORY`.** No founder-designated body exists yet, so no
      body ledger can show the founder's outcomes. When that is the only gap and activity rose with nothing moved,
      the report adds `conditional`: `CATHEDRAL` holds unless a founder-designated body exists outside the ledger
      read. The verdict itself does not change, so the detector does not yet stop horizontal expansion by itself.
  - Every threshold is in one `THRESHOLDS` table: a 30-day window and floors of 20 commits, 5 PR-like merges, 10 new
    `.md`, 10 new `.py` and 3 evidence READMEs. Floors are per 30 days: a longer window scales them up by days/30
    (rounded up), a shorter one keeps them (`floors`).
  - It writes nothing, raises no founder ask and grants nothing. `greg cathedral [--repo R] [--days N | --since T]
    [--until T] [--body [HOME]]` prints the module's report as JSON.
- `acceptance/claims.py` (`python -m acceptance.claims`) is the reality-claim inflation guard. It adds no new ladder.
  - It uses the acceptance harness's `LADDER`, which `foundry.completion.EVIDENCE_TIERS` shares (tested). Four
    crosswalks map onto it and are tested total and monotone: the directive's 17 section-56 levels (parsed from the
    directive source), `greg.mission_control.REALITY`, the `greg.metrics` levels, and the Outcome contract's
    `validation_status` (read from `contracts/outcome.schema.json`).
  - One `CEILINGS` table gives the highest rung each evidence kind can establish, with the rule it comes from:

    | Evidence kind | Ceiling |
    | --- | --- |
    | `unit_test` | SANDBOX_VERIFIED |
    | `integration_container` | BODY_VERIFIED |
    | `rehearsal_key` | BODY_VERIFIED |
    | `founder_device_run` | FOUNDER_ACCEPTED |
    | `external_verification` | EXTERNALLY_VERIFIED |

  - The ceiling table also gives each kind its highest section-56 level, so levels are not collapsed: `unit_test`
    UNIT-TESTED, `integration_container` and `rehearsal_key` PERSISTENT (a container cannot reboot its host),
    `founder_device_run` FOUNDER-USED, `external_verification` EXTERNALLY-VERIFIED. A fifth crosswalk reads the
    cognition SOP's reality labels (MAC-VERIFIED among them; tested total, since the SOP's list is no order), and
    device-verified labels such as CHROMEBOOK-VERIFIED map to FOUNDER_ACCEPTED. One label maps to one rung in every
    vocabulary (checked).
  - It reads 13 claim fields (`reality`, `reality_status`, `current_reality`, `tier`, `status`, `validation_status`
    and others), in any case and in camelCase. It also reads any string a list or record under such a field holds,
    against its nearest enclosing record. Text is NFKC-normalised; Unicode dashes and spaces become `-` and ` `;
    zero-width characters are removed. A label keeps a `-`/`_` suffix (`EXTERNALLY_VERIFIED_OUTCOME`), and `live`
    is read in any case where it opens a value or follows a colon. It scans JSON, JSON Lines and YAML (extension in
    any case) under `docs/`, `acceptance/` and any directory named `evidence`, plus `greg/path.json` and
    `foundry/completion.yaml`. A JSON Schema is told by its `$schema`, not its file name.
  - It fails on any of these:
    - a claim above its declared `evidence_kind`;
    - a founder-device or external claim whose `evidence_ref` is not a ledger digest (`sha256:` plus 64 hex digits,
      not all zeros) or an existing repository file other than the record itself;
    - such a claim whose record describes a container, rehearsal, test-key, fixture or test run anywhere (pytest,
      CI, GitHub Actions, simulated and similar);
    - a claim above BODY_VERIFIED with no declared kind;
    - a claim with no declared kind above the kind its own evidence names (the claim and its `evidence`, `how`,
      `run`, `runner`, `environment` or `host` fields): "LOCAL-REAL" from unit tests, "REBOOT-VERIFIED in a container";
    - an unreadable scanned file, nested too deep included;
    - a broken crosswalk;
    - a stale allowlist entry.
  - A declared kind is the record's own declaration. The guard checks only that the claim stays under that kind's
    ceiling, that the reference resolves and that the record describes no excluded run. It cannot verify that the
    referenced record proves the kind.
- `scripts/ci/check_cathedral_detector_mutants.py` is the mutant gate for both guards.

## Review round 1: findings and dispositions

All 16 findings were reproduced at `65f91d2f`, 15 by rerunning the reviewers' probes and the new regression tests in
a worktree of `65f91d2f` (below). WU13-F7 was reproduced by reading: the README named only the cost clause as
unmeasured. 15 are fixed in code and tests; WU13-F7 is fixed by disclosure.

| Finding | Disposition |
| --- | --- |
| F1, WU13-F1: a comma, dash, "as required" or "open" after a label hid the claim | Fixed. After a label, only a status saying the label is unmet counts ("pending", "not yet", "blocked" and similar), directly or after one colon. That rule does not hold when the record describes a container, rehearsal or test run. A comma or conjunction between a negator and a labelling verb breaks a prohibition. 17 fixtures. |
| F2, WU13-F2: a declared kind was checked only in its claim and ref | Fixed. Every string of the record is read for run markers, including nested ones, and test-run markers were added. |
| WU13-F3: any non-empty `evidence_ref` passed | Fixed (`ref_problem`). Placeholders, short or all-zero digests, missing files, self-references and paths outside the repository fail. |
| F3: `validation_status` was not read | Fixed. It is a claim field with its own crosswalk. `docs/cortex/examples/routing-memory-verified-success.json` is allowlisted with a reason and owner (generated by `cortex/examples.py`, not a run record) and still reported. |
| F4: a ledger that did not cover the window read as flat | Fixed. Ledger coverage and founder-body coverage are both checked (see the verdicts). |
| F5: a replace graft cut the history and was reported complete | Fixed. Replace refs are ignored and counted (`replace_refs_ignored`). A grafts file gives `INSUFFICIENT_HISTORY`. |
| F6: a non-UTF-8 path and windows outside the calendar crashed | Fixed. Git output is decoded with surrogate escapes, and overflow raises `CathedralError` (exit 2 from the CLI). |
| F7, WU13-F4: unreadable files passed the standalone guard | Fixed. They fail. A byte-order mark and multi-document YAML are read. |
| F8: lists, records, look-alike characters, key case and other founder-device wordings were not read | Fixed for every listed case, and for a whole value of `live` in any case. |
| F9: founder-tier closures counted on any body | Fixed. They count only on the founder-designated body, and the report shows the designation. The `CEILINGS` basis text was corrected. |
| WU13-F5: safeguards unpinned by tests | Fixed. Fixtures exist for every marker, ref rule, scanned location (parametrized), claim field (parametrized) and evidence-README rule, each with a mutant. |
| WU13-F6: floors were not scaled to the window | Fixed (`floors`). |
| WU13-F7: unmeasured section-55 outcomes were not disclosed | Disclosed in the module docstring and below. Not measured: venture revenue, external effect, founder usability beyond path nodes. |

## Review round 2: findings and dispositions

All 20 findings were reproduced at `71342170`: the reviewers' probes (`claims_probe*.py`, `p_neg.py`, `p_guard.py`)
were rerun before any fix, and every new regression test was run in a worktree of `71342170` (below). The partial
clone (A6) was reproduced by the new test. R2-6 and R2-7's second half are records, not code.

| Finding | Disposition |
| --- | --- |
| A1, R2-2: a negator reached a label across a comma, other labels and content words; "above" and "beyond" negated | Fixed (`_reaches`). A comma or conjunction ends a negation; another label needs "or", "nor" or "/"; content words never extend it, event words ("ran", "in") only before a place. "above" and "beyond" are no longer negators. |
| A2: MAC-VERIFIED, CHROMEBOOK-VERIFIED, suffixed labels and lowercase `live` unread | Fixed. SOP crosswalk, device-verified labels (slash lists read as one), suffixes, `live` opening a value. A test reads every label the SOP and both templates offer. |
| A3: a clock that ran ahead cut the ledger early and gave a false CATHEDRAL | Fixed (`inversion`). Times that run backwards across either edge give INSUFFICIENT_HISTORY; a move there does not decide. |
| A4: the caller's `GIT_DIR` pointed the read at another repository | Fixed. `GIT_*` variables are dropped; `log.showRoot` is fixed. |
| A5: a plain directory inside a repository was read as that repository | Fixed. `--show-toplevel` must be the given path. |
| A6: a blobless clone fetched blobs while being read | Fixed. A partial clone is refused before any log; `GIT_NO_LAZY_FETCH=1` is also set (a no-op on this git 2.43). |
| A7: an item under a claim field was checked against its parent's kind | Fixed (`_record`): nearest enclosing record, fields it lacks from the records around it; a sibling item is not its fact. |
| A8: deep nesting crashed the guard | Fixed. RecursionError and MemoryError make the file unreadable. |
| A9: a path holding U+001E hid its commit's files | Fixed (`_added`): NUL-only parsing. |
| A10: `.schema.json` names, `.JSON`, `.jsonl` and YAML under `acceptance/` were not read | Fixed. Extensions in any case; JSON Lines; YAML under `acceptance/`; schemas by content. |
| A11: no declared kind meant BODY_VERIFIED whatever the evidence said | Fixed for evidence that names its kind (`implied_kind`). The probe's own record ("pytest tests/unit/test_x.py in a sandbox") still passes by design: `tests/unit/` holds real-process tests in this repository, and a sandbox run can reach BODY_VERIFIED. |
| A12: files a merge added itself were never counted | Fixed (`-m`, counted only when new against every parent). |
| A13, R2-4: a closure counted without VEPMC's platform, appraisal and fixture checks | Fixed (`counts_as_outcome` reads VEPMC's own row). |
| R2-1: the build phase never shows the kill condition | Fixed by the `conditional` field and disclosed above: the verdict stays INSUFFICIENT_HISTORY. |
| R2-3: `Live` inside a longer value was unread | Fixed with A2. Lowercase `live` mid-sentence is still unread (below). |
| R2-5: declared ceilings collapsed section-56 levels | Fixed (`above`, directive ceiling per kind). |
| R2-6: the unit report described `65f91d2f` | Fixed by this README and the regenerated report, both at this head. |
| R2-7: `depth` was the reachable count; unmeasured activity measures undisclosed | Fixed: `depth` (first-parent) and `reachable_commits`; disclosed below. |

## Commands and results

Python 3.11 venv (`/home/user/venv311`). Every pytest run used
`PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider`.

**Fail-before.**

- Original unit, at base `44b3df96` with the then-new test files: 2 collection errors (no `greg.cathedral`, no claim
  guard). `python -m greg cathedral` exited 2 ("invalid choice"). An inflated record
  (`FOUNDER-USED (Linux container rehearsal, test key)`) passed `python -m acceptance check` and 60 existing tests.
- Review round, in a detached worktree of `65f91d2f`:
  - The reviewers' probes reproduced every finding. Results:
    - every case in `p03_guard_bypass.py` exited 0;
    - `p04_cathedral_edges.py` crashed with `UnicodeDecodeError` and `OverflowError`, and the graft dropped 30
      commits to 3;
    - the window in `p05` gave `CATHEDRAL` with outcomes measured;
    - `floors.py` reported the same steady activity as flat at 30 and 90 days and risen at 365.
  - The final test files copied into that worktree: **106 failed, 29 passed** (135): 79 of 105 in
    `test_reality_claims.py`, 27 of 30 in `test_cathedral_detector.py`. Some of those failures come from helpers and
    messages that did not exist yet (`founder_body`, `ref_problem`, the outcome crosswalk), not only from the
    defects.

- Review round 2, in a detached worktree of `71342170` with `938f6523`'s two test files: **78 failed, 117 passed**
  (195). Each finding's test fails on behaviour there, for example a false `CATHEDRAL` under clock skew (A3), the
  other repository's HEAD read under `GIT_DIR` (A4), `complete: True` for a plain directory and for a partial clone
  (A5, A6), `new_py` 0 for the separator path (A9) and `new_md` 2 instead of 14 for the merges (A12). Some failures
  come from helpers that did not exist yet (`inversion`, `scanned`, the `gap` field), not only from the defects.

**Pass-after** (this head):

| Command | Result |
| --- | --- |
| `pytest tests/unit/test_cathedral_detector.py tests/unit/test_reality_claims.py` | 202 passed (45 + 157) |
| merging the PR base into `ac78206b` (`849c7973`, then `fbce94e5`), then into `631b40ec` (`d35d92a5`, #249) | the first two merges had one conflict each in `greg/cli.py`, and both sides were kept: the `cathedral` and `blockers` parsers after `acceptance`, then the `greg cathedral` and `greg compute` usage lines. The third merge was clean. `foundry/owned-source.json` merged clean each time, and `scripts/refresh_owned_source.py` left it unchanged |
| `test_ucl_compiler`, `test_governance_integrity`, `test_path_build_frontier`, `test_greg_founder_tier`, `test_greg_closure_integrity`, `test_founder_correction_20261030`, `test_greg_packaging`, `test_acceptance_harness`, `test_greg_mission_control_costs`, `test_vpl_metrics` | 210 passed |
| `python -m acceptance check` | sound (12 missions, 85 requirements) |
| `scripts/ci/check_authority_singleton.py` | exactly one source of authority |
| `python scripts/ci/check_cathedral_detector_mutants.py` (scratch copy, `python -B`, bytecode purged before each mutant) | **160/160 caught, exit 0**; unmutated PASS, 0 stale, 0 invalid (39 minutes on a loaded machine). It also caught 160/160 on `631b40ec`'s code and tests before the merge (24 minutes). The run on `954c6846` caught 155/160 and exited 1 (mutant history) |
| `python -m acceptance.claims` on this tree | PASS: 5805 claims in 580 files, 0 crosswalk problems, 0 violations, 1 allowlisted (the cortex example), 0 stale, 0 unreadable |
| `python -m greg --home <no body> cathedral` on this tree | INSUFFICIENT_HISTORY: shallow clone, first-parent depth 358, 1688 commits reachable, no counts |

**Mutant history.**

- Original unit: the first run caught 43 of 45. One survivor was an equivalent mutant; the other was the
  parenthesis hole, which was fixed. The final run caught 47 of 47.
- Review round: the first full run (on the tree that became `3065ba56` and `343cd68e`; its copy differed only in two
  docstring hunks of `acceptance/claims.py`) caught 105 of 107. Both survivors were unpinned checks, not equivalent
  mutants:
  - a ref to a file that exists outside the tree (the test used a path that did not exist);
  - a status word inside a parenthesis ("FOUNDER-USED (blocked list cleared)" is now a fixture).

  Each now has a test, and an absolute-path mutant was added. That run caught 108 of 108.
- Review round 2: 16 mutants were re-targeted to the rewritten code, 3 removed and 55 added (160 in all, one or
  more per new safeguard). Removed:
  - "a body never designated counts", replaced by "a closure off the founder's designated body or platform counts";
  - "a closure registered before the designation counts": that check now lives in `greg.metrics.vepmc`, and the
    founder-body mutant covers the detector's reliance on it;
  - "a schema is read as claims", replaced by the three schema-by-content mutants.

  Not added: removing `GIT_NO_LAZY_FETCH`, a no-op on git 2.43 that would survive as an equivalent mutant.

  The final run (on `954c6846`) caught 155 of 160 and exits 1; the unmutated tests pass. The same five survived on
  `c5ee7f8a` (155 of 160), and alone on copies of `c5ee7f8a` and `ac78206b`, so neither merge caused them. None is
  equivalent: each mutant changes the guard's answer on an input that no test holds.
  - "a unit test beside an integration test holds the claim to UNIT-TESTED": `implied_kind` with both markers
    gives `unit_test` instead of `integration_container`;
  - "a negator reaches across a comma": "not yet, FOUNDER-USED" is no longer read as a FOUNDER-USED claim;
  - "a negator reaches across another label": in "not UNIT-TESTED FOUNDER-USED or EXTERNALLY-VERIFIED",
    EXTERNALLY-VERIFIED is no longer read as a claim;
  - "a whole value of 'live' is not LIVE": a whole value "founder-device" is no longer read as FOUNDER-DEVICE
    ("live" itself is still read, through the opening-`live` rule);
  - "a schema's enum and default values are claims": a schema whose `examples` or `default` hold records with
    claim fields gives 2 claims instead of 0.

  Pinning the five (on top of `938f6523`). Reproduced first: on a copy of `938f6523`, each of the five applied alone
  left all 150 tests of `test_reality_claims.py` passing. No safeguard, gate rule or existing assertion was removed or
  weakened. Added to `tests/unit/test_reality_claims.py`:
  - six inflated fixtures (`x1`-`x6`): "No, FOUNDER-USED" beside a container rehearsal and "not yet, FOUNDER-USED"
    (a comma ends a negation even when only filler sits before it); "not UNIT-TESTED FOUNDER-USED or
    EXTERNALLY-VERIFIED", which must be reported at EXTERNALLY-VERIFIED (a second label ends a negation unless "or"
    or "nor" joins them); a whole value "founder-device" and "Founder-Device" beside docker; "REBOOT-VERIFIED" whose
    evidence names unit and integration tests in a container, which must be held to `integration_container`;
  - one correct record, "LOCAL-REAL" from unit and integration tests in a container, which must pass;
  - `test_each_reading_rule_holds_on_its_own`, which checks `asserted` and `implied_kind` directly on those inputs;
  - in `test_correct_claims_pass_and_schemas_are_not_claims`, a schema whose `enum`, `const`, `default` and
    `examples` hold records with claim fields: it must give no claim, and the same records outside a schema must give
    violations at five named pointers.

  Each mutant was then applied alone to a scratch copy, with the gate's own old and new text, and
  `pytest -q -rf tests/unit/test_reality_claims.py` run there. It fails these tests and no others (157 run each
  time):

  | Mutant | Failing tests |
  | --- | --- |
  | unit test beside integration test | `x6`, `test_each_reading_rule_holds_on_its_own`, `test_correct_claims_pass_and_schemas_are_not_claims` (its correct record) |
  | negator across a comma | `x1`, `x2`, `test_each_reading_rule_holds_on_its_own` |
  | negator across another label | `x3`, `test_each_reading_rule_holds_on_its_own` |
  | whole value | `x4`, `x5`, `test_each_reading_rule_holds_on_its_own` |
  | schema values | `test_correct_claims_pass_and_schemas_are_not_claims` |

  The whole-value mutant was renamed "a whole value 'founder-device' in any case is not FOUNDER-DEVICE", and the
  comment on that line of `acceptance/claims.py` now says the rule covers both labels: for "live" the mutant is
  equivalent (the opening-`live` rule reads a whole "live" the same way), for "founder-device" it is not. Its old and
  new text are unchanged. The full gate then caught 160 of 160 and exited 0, with the five former survivors among
  the caught. After the third base merge it caught 160 of 160 again on `1cc6645d` and exited 0.

## Limitations (negatives kept)

- **Untested at the founder tier.** The outcome side has been measured only on test-key and passphrase-protected
  test bodies in a container. A real founder-tier body has never been read. The founder tier is the key holder's
  claim of custody (`greg.metrics.CUSTODY_CLAIM`), and the detector inherits that residual.
- **This checkout cannot be judged.** It is a shallow clone, so the detector gives no verdict on this repository.
- **The build phase gets no verdict.** Every body that exists is undesignated, so a real run with `--body` is
  `INSUFFICIENT_HISTORY` with a `conditional` CATHEDRAL beside it; nothing here pauses expansion.
- **Section-55 outcomes are only partly measured.** Measured: founder-tier closures, VEPMC and path nodes, which
  include the first business loop (N3) and multi-venture compounding (N7) once they are achieved. Not measured:
  - venture revenue (`greg/venture_books.py`);
  - external effect;
  - founder usability beyond the nodes achieved;
  - the kill condition's second clause, "the Kernel adds more cost than control".
- **Activity is approximate.**
  - Floors are declared priors, not measurements. "Rose" means the scaled floor was reached, not that activity
    grew against the window before it.
  - Activity is HEAD's history only.
  - PRs are inferred from merge shapes, not the GitHub API.
  - Section 55's own activity measures (architectures, agents, frameworks, subsystems) are not computed; the
    binding scope chose commits, merges and new `.md`, `.py` and evidence READMEs instead.
  - Ledger times are the writer's wall clock. Skew across the window's edges is refused; skew inside the window is
    not visible and does not change a cut.
- **A ledger younger than its window cannot show "unchanged".** This includes a ledger designated within the
  window. Such a ledger gives `INSUFFICIENT_HISTORY` unless an outcome moved, so a new body has no `CATHEDRAL`
  verdict until its designation is older than the window.
- **The claim guard reads words, not meaning.**
  - It can still be phrased around. Known shapes that still pass:
    - a negator and a labelling verb with no comma or conjunction between them ("not a container run labelled
      FOUNDER-USED");
    - a comma list after a prohibited labelling verb ("never labelled UNIT-TESTED, FOUNDER-USED");
    - other key names (`level`, `claimed_level`);
    - boolean label keys (`"founder_used": true`);
    - lowercase `founder-device` inside a longer value (a whole value is read in any case), and lowercase `live`
      mid-sentence ("the page went live in a container");
    - word orders such as "verified externally";
    - a record whose evidence names no kind, or names it outside the six evidence fields, is held only to
      BODY_VERIFIED ("LOCAL-REAL", evidence "pytest tests/unit/test_x.py in a sandbox", passes);
    - a file that names json-schema.org in `$schema` hides what it puts under `enum`, `const`, `default`,
      `examples` or a property name.
  - These were left unread deliberately. Each would flag existing honest records:
    - `"founder_accepted": true` is a VEPMC condition in three test-body summaries;
    - a lowercase "Founder-device/identity proof ... is not addressed" sits in a claim field.
  - Prose (`.md`) is not scanned.
- **Over-reporting has a cost.** "Container" also names the Chromebook's own Linux container (Crostini). A real
  founder-device record that describes its environment that way will be flagged. It then needs an allowlist entry
  with a reason and owner, or different wording.
- **Untested against real records.** No existing record declares `evidence_kind`, so the declared-kind rules are
  exercised only by fixtures. No record on this tree or on #196's head is held below BODY_VERIFIED by the inferred
  kind: the round-2 rules flagged nothing real.
- **Inferring a kind from the whole record over-reports.** A first attempt read every string of the record and
  flagged 47 honest records (acceptance requirements whose notes name in-process tests beside the process test
  that verifies them, `greg/path.json` P7 citing `tests/unit/` files that drive real processes). The rule now reads
  only the claim and its evidence fields, and a directory is not a kind.
- **Not wired into Canonical CI.** `.github/workflows/canonical-ci.yml` is owned by other open PRs. The guard runs in
  CI only as the unit test `test_the_repository_claims_stay_within_their_evidence`, and the mutant gate is not wired
  in.
- **Not done here:** a morning-report line, folding the guard into MW-B's contract audit, and the section 70 delta
  and section 73 40-item report (separate units, which can read this verdict and these ceilings).
