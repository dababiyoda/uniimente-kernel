# scripts/

| Path | What lives here | Run by |
|---|---|---|
| `ci/check_*.py` | guards and mutation gates (24) | Canonical CI jobs; see each job in `.github/workflows/canonical-ci.yml` |
| `check_release_exclusions.py` | uncleared third-party data never ships | CI tests job and tags |
| `refresh_owned_source.py`, `build_mind_*.py`, `data_exposure_ledger.py`, `lineage_map.py` | regenerate tracked records | by hand after a change; re-run rather than hand-edit |
| `p8_*`, `*_pilot.py`, `*_eval.py`, `qualify_*.py` | evidence builders and pilots for frozen evaluations | by hand, under a pre-registration |
| `mind_status.py`, `mission_trace.py`, `verify_one_machine.py` | status and proof reports | by hand; some imported by tests |
| `repo_review.py` | the recurring structural review (`docs/REVIEW_CADENCE.md`) | weekly workflow `repository-review.yml`; tests |

Known gap (2026-11-05): `ci/check_seed_mutants.py` is run by no workflow.
