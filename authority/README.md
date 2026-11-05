# authority/

Who may do what, on whose behalf.

| File | Defines |
|---|---|
| `authority-matrix.yaml` | sovereignty ranks and what each authority may and may not authorize (deny by default) |
| `legal-principals.yaml` | the real legal persons accountable for external effects |
| `reserved-matters.yaml` | matters that are permanently non-delegable |

**Consumed by:** `policy/` (Consequence Gate), `compiler/`, `verifier/`.

**Sealed.** All three files are byte-pinned by the frozen experiment records
(see `constitution/README.md`). CI fails if a second authority matrix or legal
principal registry appears (`scripts/ci/check_authority_singleton.py`).
