# scripts/

| Path | What lives here | Run by |
|---|---|---|
| `ci/check_*.py` | 39 scripts (count of 2026-11-13): 3 guards (`check_schema_refs.py`, `check_authority_singleton.py`, `check_sealed_developmental.py`) and 36 mutation gates (`*_mutants.py`, `*_mutant.py`) | guards: Canonical CI jobs 2, 3 and 4. Mutation gates: Canonical CI jobs 10 (12 gates) and 10b (16 gates), which run in parallel; job 6 (3 cortex and cognition gates); job 8 (2); `directive-completion.yml` (`check_directive_sections_mutants.py`); `build-frontier.yml` (`check_fail_closed_build_instrument_mutants.py`); `check_seed_mutants.py` by no workflow (known gap below). Each step is in `.github/workflows/canonical-ci.yml` or the workflow named |
| `check_release_exclusions.py` | uncleared third-party data never ships | CI tests job and tags |
| `refresh_owned_source.py`, `build_mind_*.py`, `data_exposure_ledger.py`, `lineage_map.py` | regenerate tracked records | by hand after a change; re-run rather than hand-edit |
| `p8_*`, `*_pilot.py`, `*_eval.py`, `qualify_*.py` | evidence builders and pilots for frozen evaluations | by hand, under a pre-registration |
| `mind_status.py`, `mission_trace.py`, `verify_one_machine.py` | status and proof reports | by hand; some imported by tests |
| `repo_review.py` | the recurring structural review: map, layering, mutation-gate liveness, lint trend (`docs/REVIEW_CADENCE.md`) | weekly workflow `repository-review.yml`; tests |
| `docs_catalog.py` | generates `docs/CATALOG.md`: every document and record once, by area, kind and date; `--check` reports staleness | by hand at intake; weekly workflow (report only) |
| `branch_catalog.py` | classifies every remote branch: finished (on the line), open PR, merged elsewhere, closed, or unclaimed commits | weekly workflow artifact; dated snapshots in `docs/collaboration/BRANCH-CATALOG-*.md` |
| `compose_rehearsal.py` | rehearses an intake: each head's own tests on its own tree and on the merged tree; reports what passes alone and fails merged, with its cause. Read-only: merges in memory, exports to a scratch directory | by hand before an intake; `tests/unit/test_compose_rehearsal.py`; first runs in `docs/collaboration/COMPOSE-REHEARSAL-2026-11-11.md` |
| `ci/mutation_harness.py` | the shared loop for mutation gates (scratch copy, STALE check, FAILED-only catch). New gates call `run(MUTANTS, TESTS, prefix=...)` and keep their literal `MUTANTS` list | three gates so far; `tests/unit/test_mutation_harness.py` |
| `dev_env_check.py` | environment doctor: what will fail because of this machine | by hand before tests; read-only |

Known gap (2026-11-05): `ci/check_seed_mutants.py` is run by no workflow. It is the one entry in `repo_review.py`'s shrink-only `KEPT_UNWIRED_GATES`; any new unwired gate fails `tests/unit/test_repo_health_gates.py`.
