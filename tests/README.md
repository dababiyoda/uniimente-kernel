# tests/

| Path | Kind | Run by |
|---|---|---|
| `unit/` | executable pytest suites, one file per module or experiment | `make unit`, verifier V2 |
| `integration/` | cross-organ executable tests (Phase Zero connection) | `make test` |
| `authority/` `capital/` `constitutional/` `provenance/` `recovery/` `security/` | governance test *specifications* (YAML): given / when / then | read by humans and the verifier; not pytest |
| `evidence/` | preserved evidence: CI logs, patches, inventories, adoption records | never executed; never edited |

`python -m pytest` from the root collects `tests/` (`pyproject.toml`).
Frozen-experiment tests (`test_repair_spec_frozen.py`,
`test_migration_spec_frozen.py`) need full git history; in a shallow clone run
`git fetch --unshallow` first.

Test files are evidence too: several are named in release records
(`docs/release/`). Add new tests rather than rewriting historical assertions.
