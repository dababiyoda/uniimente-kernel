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
     - `acceptance_frontier`: `position()`'s active node, with its build state and a status derived from it:
       "founder acceptance pending (final step)" only when that node is built; "build open; acceptance follows the
       build" when it is not; "no ledger predicate yet; cannot be accepted" when it has no predicate.
     - `achieved`, unchanged.
     - `built_ahead`: nodes built past the frontier, reported but never counted.
     - `structural_depth`: consecutive predicate nodes that are built and mutation-guarded.
     - `mutation_guard`: what `mutation_guarded` means, printed with every `greg path --build`.
   - `position()`'s loop moved into `_walk()`, which both readers share. `position()`'s output is unchanged.
   - `mutation_guarded()` parses the gate's `MUTANTS` list with `ast.literal_eval`, without importing or running it.
     A node counts only for a **live** mutant (`mutant_problems()` says why any mutant is not live):
     - its text occurs exactly once in its file, and its replacement differs;
     - its named test is one pytest would collect, found in the parsed test module (not a `def` in a docstring, a
       nested function or a helper);
     - for a node-tagged mutant, its text sits in `greg/path.py` inside that node's predicate or a function the
       predicate calls (review round 2).
     The list counts only when the gate binds `MUTANTS` once and names it nowhere else, and the gate runs exactly
     this read. An install without the gate, or a `MUTANTS` literal that is not a list, guards nothing and never
     crashes. The read shows a mutant is listed and live, never that it is caught: only a run of the gate shows that.
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
   - It answers all nine inheritance questions. q9 cites the unit test for the frontiers (VEPMC rows stubbed there)
     and the integration rehearsal for `founder_tier_count` 0 on a real one-body ledger.
5. **`scripts/ci/check_path_predicate_mutants.py`**: 33 mutants.
   - Seven weaken a node predicate: N1, N2, N3, N4, N6, and N7 twice.
   - Twenty-six weaken the build frontier, its read of the gate, or the gate's own rule for a catch:
     - a structural row sets `met`; a structural node joins `achieved`;
     - a node without a predicate counts as built; a node past the frontier is counted; an unmeasured node counts
       as built; a repository node counts as built whatever its attestation;
     - the depth counts an unguarded node; every node reads as guarded whatever the gate lists;
     - a stale, a no-op, or an untested mutant still guards its node;
     - an unhashable literal crashes the read; a literal that is not a list is read as one;
     - the acceptance status ignores the acceptance node's build;
     - review round 2: a gate that names its list again is still read; the gate runs its own list, or a mutant
       the read would not count; a mutant off its node's predicate, in another file at a matching line, in a helper
       its predicate calls (helpers dropped) or in any function (every function counted); a `def` in a docstring,
       a helper or a nested function counts as a test; a mutated module that does not import is run and counted;
       a test that fails on an import error counts as a catch.
   - The gate runs exactly the list `greg.path` reads (`_mutant_liveness`). A mutant that read would not count is
     reported `NOT_LIVE` and not run, and coverage counts only live mutants.
   - Each mutant runs in a scratch copy, under `python -B` with `PYTHONDONTWRITEBYTECODE=1`, after every
     `__pycache__` is purged.
   - The named tests must pass unmutated before any mutant runs. A mutant counts as caught only when its test fails
     on behaviour. These are `INVALID`, never caught:
     - a mutated Python file that does not import under its dotted name (checked before its test runs);
     - a test that fails on a `SyntaxError`, `ImportError` or `ModuleNotFoundError`, including one raised by a
       module the test imports lazily;
     - a collection error.
   - The gate also fails if any predicate node has no live mutant.
6. **Tests**
   - New: `tests/unit/test_path_build_frontier.py`, 20 tests (11, plus 4 from the first review round and 5 from the
     second).
   - `tests/integration/test_greg_chromebook_rehearsal.py` now runs `greg path --build` through the installed
     command twice: after N1, and after the two genesis closures.

`greg/tribunal.py` and `position()`'s output are untouched. Nothing grants, widens or moves authority.

## Commands and results

All runs used `/home/user/venv311/bin/python -B` with `PYTHONDONTWRITEBYTECODE=1 -p no:cacheprovider`.

First round, at `76853dfc` (the review round below supersedes the unit-test count and the mutant count):

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

### Review round (2026-10-30)

Two reviewers reported seven findings against `76853dfc`. Each was reproduced here before it was fixed; the
reproduction logs stay with the session and are not committed.

| Finding | Reproduced | Disposition |
|---|---|---|
| WU01-F1 (medium): `mutation_guarded` certified itself. A stale or no-op mutant kept its node guarded and counted toward `structural_depth`, and nothing runs the gate | yes: a gate with N3 stale and N4 a no-op still returned all six nodes | **fixed**: a mutant guards only while live (above), and the output says that a catch is shown only by a gate run. Not fixed: whether the named test catches the mutant. That still needs a gate run, and the gate is not in CI |
| F1 (low): the docstring said "a test catches"; the CLI output carried no caveat | yes: N3's mutant aimed at a test that cannot catch it; the gate failed 0/1 while N3 stayed guarded | **fixed** as a wording overclaim (docstring and `mutation_guard`). The scenario itself stays true until the gate runs (see the limitation) |
| WU01-F2 (low): the acceptance status was always "final step" | yes: an N5 NO_PREDICATE frontier and a fresh N1 BUILD_OPEN both said "final step" | **fixed**: the status follows the node's build state |
| WU01-F3 (low): `MUTANTS = None`, `5` or `{[1]: 2}` raised TypeError out of `greg path --build` | yes: all three crash | **fixed**: these read as nothing, and the CLI exits 0 |
| WU01-F4 and F3 (low): the repository-node rule had no test or mutant | yes: the mutant survived (34 passed) | **fixed**: a new test and a gate mutant, now caught |
| F2 (low): `founder_tier_count == 0` in the unit test was vacuous (VEPMC there has no rows) | yes: it stays 0 even with every mission forced to the founder tier | **fixed**: the assertion was removed and the docstring and placement q9 relabelled. The integration rehearsal carries the real assertion |

| Review-round run | Result |
|---|---|
| Fail-before: the new `tests/unit/test_path_build_frontier.py` on a detached worktree at `76853dfc` | **6 failed, 9 passed** (see note 5) |
| Pass-after: `tests/unit/test_path_build_frontier.py` and `tests/unit/test_developmental_inheritance.py` | **38 passed** |
| `python -B scripts/ci/check_path_predicate_mutants.py` | **21/21 caught**, exit 0, 63 s |
| Negative control (copy of the gate): equivalent, syntax-error, no-op and stale mutants, with no predicate mutant | **0/4 caught**, exit 1: `SURVIVED_OR_INVALID` ×2, `NO_OP`, `STALE`, and six `UNCOVERED` |
| Related suites (the 21 files of note 2, plus test_developmental_inertness and test_evidence_bundle_digests) | **520 passed** in 634.11 s |
| Integration: rehearsal and VEPMC path, supervisord on `PATH` | **4 passed** in 84.05 s, none skipped |

5. The two behavioural fail-befores:
   - the stale and no-op gate guarded `{N1, N2, N3, N4, N6}` where `{N6}` is right;
   - `MUTANTS = None` raised `TypeError`.

   The fresh-body test fails on the missing acceptance `build` key. The other three fail on names that did not exist
   yet: `mutant_problems`, `ACCEPTANCE_STATUS`, `ACCEPTANCE_AFTER_BUILD`.

   The repository rule was already correct at `76853dfc`, so its test is a guard, not a defect reproduction. That
   finding's evidence is its mutant: it survived there and is caught now.

### Review round 2 (2026-10-30)

Two reviewers reported three findings against `66745a89`. Each was reproduced here before it was fixed. The
reproduction scripts and logs stay in the session scratchpad and are not committed.

| Finding | Reproduced | Disposition |
|---|---|---|
| WU01-ATK-1 (low): the gate counted a mutant that broke a lazily imported module as caught. The test FAILED rather than ERRORed at collection, so the "never on an import error" rule did not apply | yes: a copy of the gate holding only a syntax-error mutant on `greg/venture_books.py` (imported inside the N7 test) printed `CAUGHT`, `1/1 caught` | **fixed**: the mutated Python file must import under its dotted name before its test runs, and a test that fails on a syntax or import error is `INVALID`. In a copy of the fixed gate, the reviewer's exact mutant is `NOT_LIVE` (off target), the same edit untagged is `INVALID` (`SyntaxError`), and an equivalent mutant survives: 0/3 caught, exit 1 |
| WU01-ATK-2 (low): the static read could disagree with what the gate runs or counts | yes, all three cases: (a) `MUTANTS = [...]` followed by `MUTANTS = []` or `MUTANTS.clear()` read as `{N3}`; (b) a README line tagged N3 read as `{N3}` with no problem; (c) a `def test_gone():` inside a docstring made the test defined | **fixed**: (a) the gate runs exactly the read, which counts a list only when `MUTANTS` is bound once and named nowhere else; (b) a node-tagged mutant must sit in `greg/path.py`, inside its node's predicate or a function the predicate calls; (c) a test is found in the parsed module, as pytest collects it. The rehearsal-reference check uses the same lookup. Not fixed: the gate is still not in CI (see limitations) |
| WU01-FID-1 (low): the round-1 implementer report was stale against the branch (head, commit count, mutant and test counts, the unconditional "final step") | yes: the head was `66745a89`, five commits past `feb531d2`, with 21 mutants and 15 tests | **fixed in the report**: this README was already accurate. The unit's report is regenerated from it at this round's head |

| Review-round-2 run | Result |
|---|---|
| Fail-before: the new `tests/unit/test_path_build_frontier.py` on a detached worktree at `66745a89` | **6 failed, 14 passed** (see note 6) |
| Pass-after: `tests/unit/test_path_build_frontier.py` | **20 passed** |
| `python -B scripts/ci/check_path_predicate_mutants.py` at `c7908b8e` | **33/33 caught**, exit 0, 167 s |
| Negative control (copy of the fixed gate): the reviewer's mutant, the same edit untagged, an equivalent mutant | **0/3 caught**, exit 1: `NOT_LIVE`, `INVALID`, `SURVIVED_OR_INVALID`, and six `UNCOVERED` |
| Related suites (note 2's 21 files, plus test_developmental_inertness, test_evidence_bundle_digests and test_greg_goal_gravity_founder_effect) | **539 passed** in 1038.93 s (see note 7) |
| `tests/unit/test_path_build_frontier.py` and `tests/unit/test_developmental_inheritance.py` at `c7908b8e` | **43 passed** |
| Integration: rehearsal and VEPMC path, supervisord on `PATH`, at `c7908b8e` | **4 passed** in 134.70 s, none skipped |
| `scripts/ci/check_authority_singleton.py` | exit 0 |

6. The five new tests each fail on the defect:
   - a reassigned list still reads as `{N1}`;
   - off-target mutants guard N1, N3 and N4;
   - a docstring-only test counts as defined;
   - the gate prints `4/4 caught` for three import-breaking mutants and `2/2 caught` with the off-target mutant
     run.

   The sixth failure is the rehearsal-reference test, which now calls the new `_test_defined`. It is a refactor, not
   a defect reproduction.
7. The related run imported `greg/path.py` before two small read fixes in `c7908b8e`: an attribute store to
   `MUTANTS` reads as nothing, and a malformed path node reads as no predicate rather than raising. Every file that
   calls the changed functions, the gate and the integration rehearsal were re-run at `c7908b8e` (rows above).

**Measured on the rehearsal ledger.** This is one body, driven only through the installed `greg` command, with a
`--no-passphrase` key.
- After N1: the build frontier is N2. `built` is N0 and N1, and `achieved` is N0 only.
- After the two genesis closures:
  - the build frontier is N3 and `structural_depth` is 2;
  - the acceptance frontier is N1 (STRUCTURALLY_BUILT, STRUCTURAL_CANDIDATE, "founder acceptance pending (final step)");
  - `achieved` is N0 only, and VEPMC `founder_tier_count` is 0.

## Limitations and negatives

- **The gate is not in CI.** It is not wired into `canonical-ci.yml`, which is a hot file on other open PRs and the
  repository's single official workflow.
  - `mutation_guarded` means "the gate lists a live weakening mutant for this node, inside its predicate". That is
    checked on every read, and the gate runs exactly that read.
  - "Its test catches it" is evidenced only where the gate is run, as here. A mutant whose named test exists but
    cannot catch it stays guarded until the gate runs (review F1's scenario).
  - Considered and deferred: a gate-written receipt, keyed to source hashes, that `mutation_guarded` would require.
    Every edit to `greg/path.py` or to a named test, by any PR, would drop `structural_depth` to 0 until the gate was
    re-run. Wiring the gate into CI is the cheaper fix.
- **One mutant per predicate is not exhaustive.** At least one weakening per predicate is caught. That does not
  show that every weakening is.
- **What the gate's read and its catch rule still cannot see (review round 2):**
  - A node's mutant counts only inside `greg/path.py`. A weakening in a module a predicate delegates to (for
    example `greg/metrics.py` or `greg/venture_books.py`) is refused as `NOT_LIVE` when tagged with the node, and
    when untagged it runs but guards no node. All seven node mutants today are in `greg/path.py`. The N5 and N8 predicates must follow this, or extend the target rule in the
    same PR.
  - A predicate's reach is every module-level function of `greg/path.py` it names, transitively. A helper it names
    but never calls still counts as part of it.
  - The read is static. It refuses any second naming of `MUTANTS`, but code that reaches the list without naming it
    (built strings run with `exec`) is out of its view. The gate runs the read, so a run of the gate cannot diverge
    from it.
  - A catch is refused for a mutated file that does not import, and for a test failing on a syntax or import error.
    A mutant that makes some other module raise a different exception while it is imported lazily (a
    `RuntimeError` at its top level, say) would still count as caught.
- **`structural_depth` is the build-phase depth only on one body driven through the CLI.**
  - Today that body reaches N2.
  - N3, N4, N6 and N7 are structurally met only on separate unit-test bodies, which do not add up.
  - The one-body rehearsal of the whole path is later work.
- **N5 and N8 still have no predicate,** so the build frontier cannot pass N5.
- **Reality level: UNIT-TESTED and INTEGRATION-TESTED.** The integration run is the installed CLI under supervisord,
  in a container.
  - It is not FOUNDER-USED, not device-verified, not live and not externally verified.
  - Nothing here moves N1, `achieved` or VEPMC.
