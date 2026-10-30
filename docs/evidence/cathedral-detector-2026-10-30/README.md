# Cathedral detector and reality-claim guard (WU-13), 2026-10-30

Directive 2026-10-28, sections 10, 55, 56, 67, 70 and 73. Founder correction of 2026-10-30
(`INTENT-20261030-BUILD-BEFORE-DEVICE-RUN`). Branch `claude/cathedral-detector-20261030`, based on `44b3df96`
(#236 head, WU-01 build frontier).

**Reality level: UNIT-TESTED.** Synthetic git repositories and real test-key and passphrase-protected test bodies,
all in this Linux container. Nothing here is founder-used, live or externally verified, and the detector has never
read the founder's body.

## What changed

- `greg/cathedral.py` evaluates the first clause of the constitution's `cathedral` kill condition, read through
  `compiler/ucl_compiler.py`, over a window `[since, until)`. The window defaults to 30 days.
  - **Activity** comes from git objects on HEAD: commits by committer time, PR-like merges (more than one parent,
    or a GitHub merge subject), and the files those commits added (`.md`, `.py`, and evidence READMEs). Renames are
    detected and not counted as new files.
  - **Outcomes** are read at the founder tier only, on the body's ledger as it stood at `since` and at `until`
    (an in-memory, re-verified prefix of the append-only ledger). Three measures count:
    - closures of missions signed at the founder tier (`greg.metrics.founder_tier`);
    - VEPMC `founder_tier_count`;
    - nodes achieved on the founder's path (`greg.path.position`).
  - **Vertical progress** is reported beside the outcomes and never counted as one: the build frontier, newly
    built nodes and the structural depth (`greg.path.build_status`), plus closures below the founder tier.
  - **Verdicts:**
    - `CATHEDRAL`: activity reached a floor while no outcome moved;
    - `NOT_CATHEDRAL`: an outcome moved, or activity stayed under every floor;
    - `INSUFFICIENT_HISTORY`: a shallow clone (reported with its depth and no counts), no git repository, or no body
      ledger read (outcomes unmeasured, never assumed flat).
  - Every threshold is in one `THRESHOLDS` table: a 30-day window; activity floors of 20 commits, 5 PR-like merges,
    10 new `.md`, 10 new `.py` and 3 evidence READMEs.
  - The detector is read-only. It writes no history, raises no founder ask and grants nothing.
- `greg cathedral [--repo R] [--days N | --since T] [--until T] [--body [HOME]]` prints the module's report as JSON.
  `--body` alone reads the body at `--home`, read-only.
- `acceptance/claims.py` (`python -m acceptance.claims`) is the reality-claim inflation guard. It adds no new ladder.
  - The ladder it uses is the acceptance harness's `LADDER`, which `foundry.completion.EVIDENCE_TIERS` shares (tested).
  - Three crosswalks map onto that ladder and are tested total and monotone: the directive's 17 section-56 levels
    (parsed from the directive source), `greg.mission_control.REALITY`, and the `greg.metrics` levels.
  - One `CEILINGS` table gives the highest rung each evidence kind can establish, with the rule each comes from:

    | Evidence kind | Ceiling |
    | --- | --- |
    | `unit_test` | SANDBOX_VERIFIED |
    | `integration_container` | BODY_VERIFIED |
    | `rehearsal_key` | BODY_VERIFIED |
    | `founder_device_run` | FOUNDER_ACCEPTED |
    | `external_verification` | EXTERNALLY_VERIFIED |

  - The scan reads claim fields (`reality`, `reality_status`, `current_reality`, `evidence_level`, `tier` and others)
    in evidence JSON under `docs/` and `tests/evidence/`, in `acceptance/*.json`, `greg/path.json` and
    `foundry/completion.yaml`. It fails on any of these:
    - a claim above its declared `evidence_kind`;
    - a founder-device or external claim with no `evidence_ref`, or one whose text describes a container, rehearsal,
      test-key or fixture run;
    - a claim above BODY_VERIFIED, what tests establish, with no declared kind;
    - a crosswalk that is not total and monotone;
    - a stale allowlist entry.
  - A label named under a negation is not a claim: "not FOUNDER-USED", "may not be labelled ...",
    "FOUNDER-USED: pending".
- The guard was first placed in `governance/`. `tests/unit/test_governance_integrity.py` forbids that package from
  importing `greg`, so it moved to `acceptance/`, beside the ladder it reuses.
- `scripts/ci/check_cathedral_detector_mutants.py` is the mutant gate for both guards.
- `foundry/owned-source.json` lists the two new modules (`scripts/refresh_owned_source.py`).

## Commands and results

Python 3.11 venv (`/home/user/venv311`). Every pytest run used `PYTHONDONTWRITEBYTECODE=1 python -B -m pytest -q -p no:cacheprovider`.

**Fail-before.** Run in a detached worktree of `44b3df96` with the two new test files copied in:

- `tests/unit/test_cathedral_detector.py` and `tests/unit/test_reality_claims.py`: 2 collection errors (no
  `greg.cathedral`; no claim guard).
- `python -m greg cathedral`: exit 2, "invalid choice: 'cathedral'".
- With `docs/evidence/zz-inflated/run.json` = `{"reality": "FOUNDER-USED (Linux container rehearsal, test key)"}`
  added to that tree, nothing caught it:
  - `python -m acceptance check`: exit 0;
  - `tests/unit/test_founder_correction_20261030.py` and `tests/unit/test_acceptance_harness.py`: 60 passed.

**Pass-after** (head of this branch):

| Command | Result |
| --- | --- |
| `pytest tests/unit/test_cathedral_detector.py tests/unit/test_reality_claims.py` | 42 passed (16 + 26) |
| Related suites: `test_ucl_compiler`, `test_governance_integrity`, `test_path_build_frontier`, `test_greg_founder_tier`, `test_greg_closure_integrity`, `test_founder_correction_20261030`, `test_greg_packaging`, plus the two new files | 185 passed |
| `test_acceptance_harness`, `test_greg_mission_control_costs`, `test_vpl_metrics` | 67 passed |
| `python -m acceptance check` | sound (12 missions, 85 requirements) |
| `scripts/ci/check_authority_singleton.py` | exactly one source of authority |
| The other mutant gates' `greg/cli.py` mutants (`check_cortex_mutants.py`) | their text still occurs exactly once |
| `python scripts/ci/check_cathedral_detector_mutants.py` (scratch copy, `python -B`, bytecode purged before each mutant) | 47/47 mutants caught, unmutated PASS, exit 0 |

**The mutant gate's first full run caught 43 of 45 mutants** (exit 1). Both survivors were kept as findings and fixed:

- "The directive's first level is dropped" (`[begin + 2:end]`) was an equivalent mutant: the line it dropped is the
  blank line after "Use levels such as:". It now drops the first level itself.
- "A negated container marker contradicts a founder-device claim" survived because its fixture,
  `FOUNDER-USED (not a container run)`, was read as no claim at all: the after-label negation reached inside the
  parenthesis and hid the label. That is a real under-reporting hole. Fixed: a negating word after a label counts only
  when it follows directly, never from inside a parenthesis. The text is now an inflated fixture, and the
  founder-device fixture reads `FOUNDER-USED on the Chromebook; never a container`.
- Two mutants were added after that run: a missing git crashing the detector, and the parenthesis hole.

**Recorded runs on this repository** (not asserted by any test). The cathedral run was at `dad4dc81`; the claim scan was
repeated at the final head with the same result:

- `python -m greg --home <scratch body> cathedral --body`: **INSUFFICIENT_HISTORY**.
  - This checkout is a shallow clone: 1489 commits are reachable from HEAD, so no activity count is given.
  - The scratch body (a `--no-passphrase` test key, enrolled only, not the founder's body) reads outcomes flat:
    0 founder-tier closures, VEPMC founder-tier 0, achieved `[N0]`, build frontier N1.
  - The gap map's figure ("1,177 commits since 2026-10-01") came from this same shallow history. The detector
    refuses to present it as complete.
- `python -m acceptance.claims`: PASS. 5043 claims in 449 files, 0 violations, 0 allowlisted, 0 unreadable.
  - Every beyond-test label in a claim field was examined (9 occurrences). Each is negated: "not FOUNDER-USED",
    "not founder-used", "no externally verified VEPMC".
  - A broader key rule (any key containing reality/tier/status/level/claim/attained) was also tried. It would flag 5
    strings, none of them a reality claim, so those keys are not read:
    - vocabulary lists in `docs/collaboration/MIND-COVERAGE-2026-10-21.json`;
    - concept-map prose in `docs/collaboration/goal-gravity-concept-map-2026-10-13.json`;
    - an example `validation_status` in `docs/cortex/examples/routing-memory-verified-success.json`.
  - There is no existing violation, so the allowlist is empty.

## Limitations (negatives kept)

- **Untested at the founder tier.** The outcome side is measured only on test-key and passphrase-protected test
  bodies in a container. A real founder-tier body has never been read. The founder tier is the key holder's claim
  of custody (`greg.metrics.CUSTODY_CLAIM`), and the detector inherits that residual.
- **The cost clause is not computed.** The kill condition's second clause ("the Kernel adds more cost than
  control") is out of scope.
- **Activity floors are declared priors, not measurements.** Activity is HEAD's history only. PRs are counted from
  merge shapes, not from the GitHub API.
- **The claim guard is lexical.**
  - It reads labels in declared claim fields, in capitals for one-word and informal labels.
  - A negation phrased outside its rules reads as a claim, which over-reports.
  - One shape can hide a claim: an unrelated negator plus a labelling verb in the same clause.
  - Prose (`.md`) is not scanned.
  - No existing record declares `evidence_kind`, so the ceilings of declared kinds are exercised only by fixtures.
- **Not wired into Canonical CI.** Neither the mutant gate nor a guard step is wired into
  `.github/workflows/canonical-ci.yml`, which other open PRs own. In CI the guard runs only as the unit test
  `test_the_repository_claims_stay_within_their_evidence`.
- **Not done here:**
  - the morning-report line the critique suggested;
  - folding the guard into MW-B's contract audit;
  - mapping `mission_control.REALITY` through the guard on the console surface.
- **Commit history.** The first commit put the guard under `governance/`, which fails
  `test_governance_integrity`. The second commit moves it.
- **Sections 70 and 73 are served only in part.** The capability-delta report (`greg path --build --since`) and the
  computed 40-item final report are separate units. This unit supplies the cathedral verdict and the claim ceilings
  they would read (item 35).
