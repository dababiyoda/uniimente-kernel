# scripts/

| Path | What lives here | Run by |
|---|---|---|
| `ci/check_*.py` | guards and mutation gates (24) | Canonical CI jobs; see each job in `.github/workflows/canonical-ci.yml` |
| `check_release_exclusions.py` | uncleared third-party data never ships | CI tests job and tags |
| `refresh_owned_source.py`, `build_mind_*.py`, `data_exposure_ledger.py`, `lineage_map.py` | regenerate tracked records | by hand after a change; re-run rather than hand-edit |
| `p8_*`, `*_pilot.py`, `*_eval.py`, `qualify_*.py` | evidence builders and pilots for frozen evaluations | by hand, under a pre-registration |
| `mind_status.py`, `mission_trace.py`, `verify_one_machine.py` | status and proof reports | by hand; some imported by tests |
| `repo_review.py` | the recurring structural review: map, layering, mutation-gate liveness, lint trend (`docs/REVIEW_CADENCE.md`) | weekly workflow `repository-review.yml`; tests |
| `docs_catalog.py` | generates `docs/CATALOG.md`: every document and record once, by area, kind and date; `--check` reports staleness | by hand at intake; weekly workflow (report only) |
| `branch_catalog.py` | classifies every remote branch: finished (on the line), open PR, merged elsewhere, closed, or unclaimed commits | weekly workflow artifact; dated snapshots in `docs/collaboration/BRANCH-CATALOG-*.md` |
| `compose_rehearsal.py` | rehearses an intake: each head's own tests on its own tree and on the merged tree; reports what passes alone and fails merged, with its cause. Read-only: merges in memory, exports to a scratch directory | by hand before an intake; `tests/unit/test_compose_rehearsal.py`; first runs in `docs/collaboration/COMPOSE-REHEARSAL-2026-11-11.md` |
| `ci/mutation_harness.py` | the shared loop for mutation gates (scratch copy, STALE check, FAILED-only catch). New gates call `run(MUTANTS, TESTS, prefix=...)` and keep their literal `MUTANTS` list | four gates so far; `tests/unit/test_mutation_harness.py` pins what counts as caught, and `ci/check_gate_rules_mutants.py` removes each clause of that rule |
| `dev_env_check.py` | environment doctor: what will fail because of this machine | by hand before tests; read-only |

Known gap (2026-11-05, corrected 2026-11-11): `ci/check_seed_mutants.py` is run by no workflow, and with its solver packages installed it exits 1 with 6 of 7 mutants caught (register S-3, dated correction). It is the one entry in `repo_review.py`'s `KEPT_UNWIRED_GATES`; any new unwired gate fails `tests/unit/test_repo_health_gates.py`, and so does adding one to that list, whose contents the same file pins.
