# A fail-closed build instrument, and rehearsal bodies that never reach the founder tier (2026-10-30)

**Work unit:** MW-A of the 2026-10-28 OPUS MAXIMUS build directive (sections 56, 64, 70 and 73). **Intent:**
`INTENT-20261030-BUILD-BEFORE-DEVICE-RUN` ("Continue building and doing the prompt verbatim. No real Chromebook run is
needed. That is done when we completely build the prompt"). **Base:** `44b3df96` (#236 head, the WU-01 build
frontier). **Branch:** `claude/fail-closed-build-instrument-20261030`.

**Product delta:**

- A run that must exercise the supervised rehearsals can no longer pass by skipping them.
- A body made by `greg rehearse` can no longer move `greg path` by having its own throwaway key attest the founder
  tier.
- The path-predicate mutation gate now has a CI workflow that runs it on every pull request.

Nothing grants, widens or moves authority.

## What changed

1. **Fail-closed supervisor requirement.**
   - `tests/supervisor_requirement.py` holds the decision: with `GREG_REQUIRE_SUPERVISOR=1`, a missing `supervisord`
     fails each test with one exact message (`MISSING`); unset, or any other value, it skips as before.
   - `tests/integration/test_greg_chromebook_rehearsal.py` and `test_greg_vepmc_path.py` call it from an autouse fixture
     in place of their `skipif` marks, so every test in both modules is covered. `conftest.py` is untouched.
   - Under the requirement a missing supervisord reports as a setup **error** carrying the message (pytest's outcome
     for a failing fixture), not a skip. `GREG_REQUIRE_WORKER_ISOLATION` reports the same way.
2. **Rehearsal bodies stay below the founder tier (read side).**
   - `greg/rehearsal.py` `mark_body` writes `"rehearsal": {...}` into the new body's `body.json`, right after
     `init_body` and before the throwaway key is generated or enrolled. It writes a new 0600 file and replaces
     `body.json` with it. `greg/body.py` is not edited.
   - `greg/metrics.py` adds `REHEARSAL_MARK`, `REHEARSAL_BODY` and `rehearsal_body(journal)`. The mark is read from
     `body.json` beside the journal's ledger. These read as unmarked: no ledger file, or no `body.json` there. A
     `body.json` that exists but cannot be read as a JSON object reads as marked.
   - `founder_tier` gives every mission of a marked body `STRUCTURAL_CANDIDATE`, with `why_not` set to
     `REHEARSAL_BODY`, whatever is signed. Everything it feeds follows: the N1-N7 predicates, `achieved`, the acceptance
     frontier and VEPMC's `evidence_level`. The build frontier still counts the structure.
   - `tier_status` (shown by `greg status`) now says `rehearsal_body: true` with that reason, instead of advising
     `greg founder attest`.
   - An unmarked body is unchanged, including the residual that a direct self-attestation reaches the tier
     (`test_greg_closure_integrity.py`).
3. **`.github/workflows/build-frontier.yml`** (new; `canonical-ci.yml` is not edited). On every pull request it:
   - installs `requirements-dev.txt` (it provides `supervisor>=4.2`) and `requirements-cognition.txt`, as Canonical CI
     job 1 does;
   - runs `scripts/ci/check_path_predicate_mutants.py`, which nothing in CI ran before;
   - runs this unit's mutant gate;
   - runs both rehearsal modules with `GREG_REQUIRE_SUPERVISOR=1`.

   The AppArmor user-namespace restriction is not lifted, because no step needs user namespaces:
   - bubblewrap is not installed;
   - the installer then reports that it cannot confine the network;
   - the rehearsal asserts what the installer reports (it passes here, where bubblewrap is absent);
   - the gates run plain pytest in a scratch copy.
4. **`scripts/ci/check_fail_closed_build_instrument_mutants.py`** (new, modelled on `check_pipeline_mutants.py`): 20
   mutants. Each runs in a scratch copy under `python -B` with `PYTHONDONTWRITEBYTECODE=1` and every `__pycache__`
   purged. The named tests must pass unmutated first. A failure on a syntax or import error, or a collection error,
   is INVALID, never caught. The 20 mutants:
   - 7 on `metrics.py`: the tier rule, the mark read, the fail-closed reads, two over-reach guards, and the status
     advice;
   - 3 on `rehearsal.py`: no mark, the mark written after enrolment, and `body.json` left readable by others;
   - 3 on the helper;
   - 3 on the module wiring;
   - 4 on the workflow.

   The path-predicate gate was not extended: its node mutants must sit inside `greg/path.py` predicates, and these
   safeguards live in `metrics.py`, `rehearsal.py`, the tests and the workflow.
5. **Tests:** `tests/unit/test_require_supervisor.py` (3), `tests/unit/test_greg_rehearsal_founder_tier.py` (3),
   `tests/unit/test_build_frontier_workflow.py` (2). The `greg/README.md` founder-tier table gains one row.

## Commands and results

All runs used `/home/user/venv311/bin/python -B` with `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`, from the
worktree root unless stated.

| Run | Result |
|---|---|
| Reproduce: both rehearsal modules with the default `PATH` (supervisord only in `/home/user/venv311/bin`) | **4 skipped** |
| Fail-before: the three new test files, plus the helper, on a detached worktree at `44b3df96` | **4 failed, 2 passed** in 21.5 s (note 1) |
| Probe on `44b3df96`: `greg rehearse` body, self-signed `FOUNDER_TIER`, then a MISSION, VEPMC rows stubbed | tier `FOUNDER_TIER`, `achieved` `['N0', 'N1']`, active `N2` |
| The same probe after the change | tier `STRUCTURAL_CANDIDATE`, `achieved` `['N0']`, active `N1`; `body.json` carries the mark |
| Pass-after: `test_require_supervisor.py`, `test_greg_rehearsal_founder_tier.py` | **6 passed** in 22.4 s |
| Pass-after: `test_build_frontier_workflow.py` | **2 passed** |
| Both rehearsal modules, supervisord hidden, `GREG_REQUIRE_SUPERVISOR=1` | **4 errors**, each with the exact message, in 0.47 s |
| The same, variable unset | **4 skipped** |
| Both rehearsal modules, supervisord on `PATH`, `GREG_REQUIRE_SUPERVISOR=1` | **4 passed** in 129.7 s, none skipped |
| `scripts/ci/check_fail_closed_build_instrument_mutants.py` | **20/20 caught**, exit 0, 229 s |
| Negative control: a copy of that gate with an equivalent mutant and a syntax-breaking mutant | **0/2 caught**, exit 1: `SURVIVED_OR_INVALID`, `INVALID ... SyntaxError` |
| `scripts/ci/check_path_predicate_mutants.py` (the gate the new workflow runs) | **33/33 caught**, exit 0, 138 s |
| Related suites, 19 files (note 2) | **218 passed** in 296.9 s |

Notes:

1. The fail-before failures:
   - `test_required_and_missing_every_supervised_rehearsal_fails_with_the_message` failed behaviourally: under
     `GREG_REQUIRE_SUPERVISOR=1` the base reported `4 skipped`, exit 0.
   - `test_a_rehearsal_body_never_reaches_the_founder_tier_and_achieved_does_not_move` failed behaviourally:
     `'FOUNDER_TIER' == 'STRUCTURAL_CANDIDATE'`.
   - `test_a_body_that_is_not_marked_is_unchanged_residual_included` passed its tier and `achieved` assertions on the
     base, and then failed only at its first use of the new `metrics.rehearsal_body`.
   - The reader test failed on that missing name too.
   - The two passes are the unset-skip test and the helper test. They pass on the base because the base already
     skips, and the helper was copied in.
2. The 19 files:
   - the eight new tests: test_require_supervisor, test_greg_rehearsal_founder_tier, test_build_frontier_workflow;
   - every reader of the founder tier: test_path_build_frontier, test_developmental_inheritance,
     test_greg_founder_tier, test_greg_closure_integrity, test_greg_command_record_shape, test_greg_business_case,
     test_greg_shared_work, test_greg_sop_compounding, test_greg_venture_books;
   - the rest: test_founder_correction_20261030, test_greg_chromebook_install, test_greg_packaging (the owned-source
     inventory), test_sources_parse, test_greg_founder_and_scope, test_greg_mission_control_costs and
     test_vpl_metrics.

   `check_cortex_mutants.py` mutates three texts in `greg/metrics.py`; each still occurs exactly once (checked, not
   run).

## Limitations

- **Write side open.** The body still accepts a `FOUNDER_TIER` attestation, and a `first_founder_body` designation,
  from a rehearsal key. Refusing them at write time needs a `greg/body.py` edit, which waits for #221; it is a
  follow-up.
- **The mark is not tamper-proof.** It guards against promoting a rehearsal by accident. An operator who edits
  `body.json`, or who makes a body by hand without `greg rehearse`, is not stopped. The founder tier itself remains
  the key holder's unverified claim of custody.
- **Only `greg rehearse` writes the mark.** The `--no-passphrase` installer path used by the Chromebook rehearsal does
  not; that body stays below the tier only because its key never attests through the CLI.
- **Other supervisord tests still skip silently.** `GREG_REQUIRE_SUPERVISOR` covers only the two rehearsal modules
  named in the scope. `test_greg_body_supervised.py`, `test_greg_product_path.py` and the others keep their plain
  skips.
- **Two named suites do not exist.** The scope's `test_greg_metrics*.py` and `test_greg_vepmc*.py` patterns match no
  unit file at this base. The integration `test_greg_vepmc_path.py` was run.
- **The workflow is checked as YAML only.** It was parsed and its steps checked by `test_build_frontier_workflow.py`.
  It has not run on GitHub Actions; its first pull-request run is its first execution.
- **Run times.** Timings come from a 4-core container shared with other agents' test runs.

**Reality level:** UNIT-TESTED and INTEGRATION-TESTED in a Linux container (real supervisord, real `greg rehearse`
bodies, test keys). Nothing here is founder-used, device-verified or externally verified. VEPMC stays 0.
