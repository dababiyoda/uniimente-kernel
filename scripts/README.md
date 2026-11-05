# scripts/

`ci/` holds the guard scripts behind the Canonical CI jobs. Each is standalone
(`python scripts/ci/<name>.py`) and has a `make` target.

| Script | CI job | `make` |
|---|---|---|
| `check_schema_refs.py` | 2 · contract schema references resolve | `make contracts` |
| `check_authority_singleton.py` | 3 · one source of authority | `make authority` |
| `check_sealed_developmental.py` | 4 · developmental work stays sealed | `make sealed` |
