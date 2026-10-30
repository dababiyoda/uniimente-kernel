# Cathedral detector and reality-claim guard (WU-13), 2026-10-30

Directive 2026-10-28, sections 10, 55, 56, 67, 70 and 73. Founder correction of 2026-10-30
(`INTENT-20261030-BUILD-BEFORE-DEVICE-RUN`). Branch `claude/cathedral-detector-20261030`, based on `44b3df96`
(#236 head, WU-01 build frontier). Review round 1 (two reviewers, 16 findings) was fixed on top of `65f91d2f`.

**Reality level: UNIT-TESTED.** Synthetic git repositories and real test-key and passphrase-protected test bodies,
all in this Linux container. Nothing here is founder-used, live or externally verified, and the detector has never
read the founder's body.

## What it is

- `greg/cathedral.py` evaluates the first clause of the constitution's `cathedral` kill condition ("activity rises
  while external outcomes remain unchanged"), read through `compiler/ucl_compiler.py`, over a window `[since, until)`
  (default 30 days).
  - **Activity** comes from git objects on HEAD: commits by committer time, PR-like merges (more than one parent, or
    a GitHub merge subject), and the files those commits added (`.md`, `.py`, evidence READMEs). Renames are not new
    files. Replace refs are ignored (`GIT_NO_REPLACE_OBJECTS=1`), so `git replace --graft` cannot cut the history.
  - **Outcomes** are founder-tier only, on the founder's designated body only, read on the ledger at `since` and at
    `until` (an in-memory, re-verified prefix of the append-only ledger):
    - closures of missions signed at the founder tier and registered after a founder-signed `BODY_DESIGNATE`
      (`first_founder_body`) was accepted, as VEPMC's `founder_body` condition reads it;
    - VEPMC `founder_tier_count`;
    - nodes achieved on the founder's path (`greg.path.position`).
  - **Vertical progress** (build frontier, newly built nodes, structural depth, closures not counted) is reported
    beside the outcomes and never counted as one.
  - **Verdicts:**
    - `CATHEDRAL`: activity reached its floor while no outcome moved;
    - `NOT_CATHEDRAL`: an outcome moved, or activity stayed under every floor;
    - `INSUFFICIENT_HISTORY`: git cannot show the window in full (shallow clone, with its depth and no counts; a
      grafts file; no repository), or no body ledger was read, or the ledger does not cover the window as the
      founder's body. That last case covers three situations: the ledger begins after the window ends, it carries
      no founder-signed designation, or the designation came after the window started and nothing moved. An outcome
      that moved inside the covered part still decides `NOT_CATHEDRAL`.
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

  - It reads 13 claim fields (`reality`, `reality_status`, `current_reality`, `tier`, `status`, `validation_status`
    and others), in any case and in camelCase. It also reads any string a list or record under such a field holds.
    Text is NFKC-normalised; Unicode dashes and spaces become `-` and ` `; zero-width characters are removed. It
    scans JSON and YAML under `docs/` and under any directory named `evidence` (including `foundry/evidence/`), JSON
    under `acceptance/`, `greg/path.json` and `foundry/completion.yaml`.
  - It fails on any of these:
    - a claim above its declared `evidence_kind`;
    - a founder-device or external claim whose `evidence_ref` is not a ledger digest (`sha256:` plus 64 hex digits,
      not all zeros) or an existing repository file other than the record itself;
    - such a claim whose record describes a container, rehearsal, test-key, fixture or test run anywhere (pytest,
      CI, GitHub Actions, simulated and similar);
    - a claim above BODY_VERIFIED with no declared kind;
    - an unreadable scanned file;
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

**Pass-after** (this head):

| Command | Result |
| --- | --- |
| `pytest tests/unit/test_cathedral_detector.py tests/unit/test_reality_claims.py` | 135 passed (30 + 105) |
| `test_ucl_compiler`, `test_governance_integrity`, `test_path_build_frontier`, `test_greg_founder_tier`, `test_greg_closure_integrity`, `test_founder_correction_20261030`, `test_greg_packaging`, `test_acceptance_harness`, `test_greg_mission_control_costs`, `test_vpl_metrics` | 210 passed |
| `python -m acceptance check` | sound (12 missions, 85 requirements) |
| `scripts/ci/check_authority_singleton.py` | exactly one source of authority |
| `python scripts/ci/check_cathedral_detector_mutants.py` (scratch copy, `python -B`, bytecode purged before each mutant) | 108/108 caught, unmutated PASS, exit 0 (run on an exact copy of `16801b8d`) |
| `python -m acceptance.claims` on this tree | PASS: 5064 claims in 503 files, 0 violations, 1 allowlisted (the cortex example), 0 unreadable |
| `python -m greg --home <undesignated test body> cathedral --body` on this tree | INSUFFICIENT_HISTORY (shallow clone, 1491 commits reachable; and no founder designation). Nothing in the body changed. |

**Mutant history.**

- Original unit: the first run caught 43 of 45. One survivor was an equivalent mutant; the other was the
  parenthesis hole, which was fixed. The final run caught 47 of 47.
- Review round: the first full run (on the tree that became `3065ba56` and `343cd68e`; its copy differed only in two
  docstring hunks of `acceptance/claims.py`) caught 105 of 107. Both survivors were unpinned checks, not equivalent
  mutants:
  - a ref to a file that exists outside the tree (the test used a path that did not exist);
  - a status word inside a parenthesis ("FOUNDER-USED (blocked list cleared)" is now a fixture).

  Each now has a test, and an absolute-path mutant was added. The final run is in the table above.

## Limitations (negatives kept)

- **Untested at the founder tier.** The outcome side has been measured only on test-key and passphrase-protected
  test bodies in a container. A real founder-tier body has never been read. The founder tier is the key holder's
  claim of custody (`greg.metrics.CUSTODY_CLAIM`), and the detector inherits that residual.
- **This checkout cannot be judged.** It is a shallow clone, so the detector gives no verdict on this repository.
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
- **A ledger younger than its window cannot show "unchanged".** This includes a ledger designated within the
  window. Such a ledger gives `INSUFFICIENT_HISTORY` unless an outcome moved, so a new body has no `CATHEDRAL`
  verdict until its designation is older than the window.
- **The claim guard reads words, not meaning.**
  - It can still be phrased around. Known shapes that still pass:
    - a negator and a labelling verb with no comma or conjunction between them ("not a container run labelled
      FOUNDER-USED");
    - other key names (`level`, `claimed_level`);
    - boolean label keys (`"founder_used": true`);
    - lowercase `founder-device` inside text;
    - word orders such as "verified externally".
  - These were left unread deliberately. Each would flag existing honest records:
    - `"founder_accepted": true` is a VEPMC condition in three test-body summaries;
    - a lowercase "Founder-device/identity proof ... is not addressed" sits in a claim field.
  - Prose (`.md`) is not scanned.
- **Over-reporting has a cost.** "Container" also names the Chromebook's own Linux container (Crostini). A real
  founder-device record that describes its environment that way will be flagged. It then needs an allowlist entry
  with a reason and owner, or different wording.
- **Untested against real records.** No existing record declares `evidence_kind`, so the declared-kind rules are
  exercised only by fixtures.
- **Not wired into Canonical CI.** `.github/workflows/canonical-ci.yml` is owned by other open PRs. The guard runs in
  CI only as the unit test `test_the_repository_claims_stay_within_their_evidence`, and the mutant gate is not wired
  in.
- **Not done here:** a morning-report line, folding the guard into MW-B's contract audit, and the section 70 delta
  and section 73 40-item report (separate units, which can read this verdict and these ceilings).
