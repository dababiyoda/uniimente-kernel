# tests/

| Path | Kind | Run by |
|---|---|---|
| `unit/` | executable pytest suites (365 files) | `python -m pytest` (Canonical CI tests job), verifier V2 |
| `integration/` | cross-organ executable tests | `python -m pytest`; organ jobs |
| `authority/` `capital/` `constitutional/` `provenance/` `recovery/` `security/` | governance test *specifications* (YAML given/when/then) | read by humans and the verifier, not pytest |
| `fixtures/`, `*_fixtures.py`, `one_machine_*.py`, `greg_proof_*.py`, `fake_web.py` | shared fixtures and drivers | imported by tests |
| `evidence/` | preserved evidence: CI logs, patches, inventories | never executed, never edited |

The full suite takes about 90 minutes in CI. While iterating, run the files that
import what you changed (`git grep -l "from <module>" tests/`). Frozen-history
tests need full git history (`git fetch --unshallow`). Several test files are
named in release and freeze records: add tests, do not rewrite historical
assertions.
