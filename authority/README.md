# authority/

Who may do what, on whose behalf.

| File | Defines |
|---|---|
| `authority-matrix.yaml` | sovereignty ranks and what each authority may and may not authorize (deny by default) |
| `legal-principals.yaml` | the real legal persons accountable for external effects |
| `reserved-matters.yaml` | matters that are permanently non-delegable |

**Consumed by:** `policy/` (Consequence Gate), `compiler/`, `verifier/`.

**Integrity-protected** by `governance/integrity/manifest.json` (see
`constitution/README.md`); a new unauthorized `.yaml` here is an
`UNGOVERNED_ADDITION`. CI also fails on a second authority matrix or legal
principal registry anywhere (`scripts/ci/check_authority_singleton.py`).
