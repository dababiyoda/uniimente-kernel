# Verifier index (append-only)

## v1 — 2026-07-19T14:51:37.654209Z
Measures: presence and machine-validity of the Section XXVI canonical artifact set (C1), JSON Schema validity of the 9 shared contracts (C2), YAML parseability of policy/registry files (C3), UCL structural sanity (C4), constitutional doctrine presence (C5), doctrine test-suite coverage dirs (C6), repo docs (C7), Phase-1 module placeholders (C8).
First version; no prior baseline.

## v2 — 2026-07-19T15:30:13.178493+00:00
Measures everything v1 measures (C1-C8), plus C9: sdk-python compiles and its stdlib unittest suite passes (run by `verifier/verify_sdk.py`). Added when the first extracted kernel module (decision ledger, Phase 2) entered the tree. v1 remains the acceptance record for the canonical artifact layer; v2 governs the tree from the extraction PR onward.

## v3 — 2026-07-19T16:02:48.411078+00:00
Measures everything v2 measures (C1-C9), plus C10: sdk-python pip-installs and imports with all exported symbols (run by `verifier/verify_pkg.py`). Added when the SDK became an installable package (pyproject.toml) so organs can depend on it via git URL.

## v4 — 2026-07-19T16:53:26.156683+00:00
Measures everything v3 measures, with C1/C2 extended to the two Phase 3 wire contracts (`venture-signal`, `signal-assessment`), plus C11: parity between `uniimente_kernel.contracts` and the wire schema files (enums, schema_version consts, requires_human_approval const, institutional verdict enum), run by `verifier/verify_contracts.py`. Added when the mirrored organ protocol modules were unified into the kernel SDK (v0.5.0).
