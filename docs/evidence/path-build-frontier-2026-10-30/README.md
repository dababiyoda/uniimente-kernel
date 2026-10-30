# The build frontier beside the acceptance frontier (2026-10-30)

**Intent:** `INTENT-20261030-BUILD-BEFORE-DEVICE-RUN`. Founder, verbatim: "Continue building and doing the prompt
verbatim. No real Chromebook run is needed. That is done when we completely build the prompt". The changed axes are
sequence and timing. VEPMC, its nine conditions and the founder tier are unchanged.

**Base:** `feb531d2` (the commit that records the correction). **Branch:** `claude/path-build-frontier-20261030`.

**Product delta:** `greg path --build` now answers, from the body's own ledger, how far the path is built. Before,
`greg path` stopped at N1 in every container, so build progress could only be claimed in prose. The founder's path
still moves only at the founder tier. The new view reports structure and never counts it as acceptance.

## What changed

1. **`greg/path.py`**
   - `build_status(journal)` gives each node one of three statuses:
     - `STRUCTURALLY_BUILT`: the node's predicate is structurally met on this ledger. A repository node counts
       when its attestation says ACHIEVED.
     - `BUILD_OPEN`: the node has a predicate that is not structurally met.
     - `NO_PREDICATE`: the node has no ledger predicate (N5, N8, N9, N10).
   - Each node row also carries `mutation_guarded`, `counted` and `operationally_primary`.
   - The function also reports:
     - `build_frontier`: the first node that is not built. A node without a predicate stops it.
     - `acceptance_frontier`: `position()`'s active node, with the status "founder acceptance pending (final step)".
     - `achieved`, unchanged.
     - `built_ahead`: nodes built past the frontier, reported but never counted.
     - `structural_depth`: consecutive predicate nodes that are built and mutation-guarded.
   - `position()`'s loop moved into `_walk()`, which both readers share. `position()`'s output is unchanged.
   - `mutation_guarded()` parses the gate's `MUTANTS` list with `ast.literal_eval`, without importing or running it.
     An install without the gate guards nothing.
   - `validate()` checks only the shape of the new `rehearsal` field. Whether the tests it names exist is checked by
     a unit test, because `greg path` must load on installs that ship without `tests/`.
2. **`greg/cli.py`**: `greg path --build`. It cannot be combined with `--node`. The plain `greg path` view is
   unchanged.
3. **`greg/path.json`**
   - The correction's id is added to the path's `intent` list.
   - N1-N4, N6 and N7 each gain `rehearsal`: the pytest node that builds that node's structure.
   - No existing text was rewritten.
4. **`docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json`**: placement
   `n1.vepmc_is_final_acceptance_not_build_gate`.
   - Class: SUPERSEDED_IMPLEMENTATION_ASSUMPTION. Node: N1.
   - Changed axes: sequence, timing and immediate_priority. The intended effect stays active.
   - It answers all nine inheritance questions.
5. **`scripts/ci/check_path_predicate_mutants.py`**: 14 mutants.
   - Seven weaken a node predicate: N1, N2, N3, N4, N6, and N7 twice.
   - Seven weaken the build frontier itself: a structural row sets `met`; a structural node joins `achieved`; a
     node without a predicate counts as built; a node past the frontier is counted; an unmeasured node counts as
     built; the depth counts an unguarded node; a missing gate guards every node.
   - Each mutant runs in a scratch copy, under `python -B` with `PYTHONDONTWRITEBYTECODE=1`, after every
     `__pycache__` is purged.
   - The named tests must pass unmutated before any mutant runs. A collection or import error never counts as a
     catch.
   - The gate also fails if any predicate node has no mutant.
6. **Tests**
   - New: `tests/unit/test_path_build_frontier.py`, 11 tests.
   - `tests/integration/test_greg_chromebook_rehearsal.py` now runs `greg path --build` through the installed
     command twice: after N1, and after the two genesis closures.

`greg/tribunal.py` and `position()`'s output are untouched. Nothing grants, widens or moves authority.

## Commands and results

All runs used `/home/user/venv311/bin/python -B` with `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`.

| Run | Result |
|---|---|
| Fail-before, unit: `tests/unit/test_path_build_frontier.py` on a detached worktree at `feb531d2` | **10 failed, 1 passed** (see note 1) |
| Fail-before, integration: the extended rehearsal on `feb531d2` | **1 failed**: `greg: error: unrecognized arguments: --build` |
| Pass-after: `tests/unit/test_path_build_frontier.py` | **11 passed** |
| Related suites (21 files, see note 2) | **510 passed** in 863.62 s |
| `tests/integration/test_greg_chromebook_rehearsal.py` and `tests/integration/test_greg_vepmc_path.py`, with supervisord on `PATH` | **4 passed** in 110.57 s (see note 3) |
| `python -B scripts/ci/check_path_predicate_mutants.py` | **14/14 caught**, exit 0, 78 s |
| Negative control: a copy of the gate with an equivalent mutant and a syntax-error mutant | **0/2 caught**, exit 1 (see note 4) |

Notes:

1. Eight fail-before failures are `AttributeError` (no `build_status` or `mutation_guarded`). The other two are the
   missing placement and the missing rehearsal references. The test that passes on the base,
   `test_n7_needs_a_transplant_that_was_faster_or_cheaper`, pins existing N7 behaviour so the N7 mutant has a test
   that catches it; it does not reproduce a defect.
2. The 21 files: test_path_build_frontier, test_developmental_inheritance, test_greg_founder_tier,
   test_frontier_backcasts, test_founder_correction_20261030, test_greg_business_case, test_greg_closure_integrity,
   test_greg_goal_gravity, test_greg_goal_gravity_authority, test_greg_mind_convergence,
   test_greg_protected_evolution, test_greg_shared_work, test_greg_sop_compounding, test_greg_venture_books,
   test_greg_verify_download, test_mind_status, test_organ_pr_placements, test_greg_platform,
   test_greg_seed_genome_records, test_mind_coverage_record and test_seed_genome_continuity.
3. Without supervisord on `PATH`, all four integration tests skip.
4. The equivalent mutant swaps the operands of `structural and passed`. The negative control shows that the gate
   reports a survivor and does not count a broken import as a catch.

**Measured on the rehearsal ledger.** This is one body, driven only through the installed `greg` command, with a
`--no-passphrase` key.
- After N1: the build frontier is N2. `built` is N0 and N1, and `achieved` is N0 only.
- After the two genesis closures:
  - the build frontier is N3 and `structural_depth` is 2;
  - the acceptance frontier is N1 (STRUCTURAL_CANDIDATE, "founder acceptance pending (final step)");
  - `achieved` is N0 only, and VEPMC `founder_tier_count` is 0.

## Limitations and negatives

- **The gate is not in CI.** It is not wired into `canonical-ci.yml`, which is a hot file on other open PRs and the
  repository's single official workflow. Until it is wired there, `mutation_guarded` means "the gate lists a
  weakening mutant for this node", and it is evidenced only where the gate is run, as here.
- **One mutant per predicate is not exhaustive.** At least one weakening per predicate is caught. That does not
  show that every weakening is.
- **`structural_depth` is the build-phase depth only on one body driven through the CLI.**
  - Today that body reaches N2.
  - N3, N4, N6 and N7 are structurally met only on separate unit-test bodies, which do not add up.
  - The one-body rehearsal of the whole path is later work.
- **N5 and N8 still have no predicate,** so the build frontier cannot pass N5.
- **Reality level: UNIT-TESTED and INTEGRATION-TESTED.** The integration run is the installed CLI under supervisord,
  in a container.
  - It is not FOUNDER-USED, not device-verified, not live and not externally verified.
  - Nothing here moves N1, `achieved` or VEPMC.
