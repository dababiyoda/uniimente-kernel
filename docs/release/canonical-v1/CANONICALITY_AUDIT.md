# canonical-v1 — Canonicality Audit

**Release commit:** `526e320475d7b1175c546d48147f9f49f53831e1`
**Verdict: PASS — 12 of 12 claims.** Every claim computed from repository
contents at the release commit, not asserted.

| # | Claim | Result | Evidence |
|---|---|---|---|
| 1 | exactly one Constitution | PASS | 1 × `constitution/constitution.ucl` |
| 2 | exactly one authority matrix | PASS | `authority/authority-matrix.yaml`, sole match repo-wide |
| 3 | exactly one legal-principal registry | PASS | `authority/legal-principals.yaml`, sole match |
| 4 | exactly one canonical Consequence Gate | PASS | `policy/consequence_gate.py`, sole match |
| 5 | no Venture Cell active | PASS | `ivio_nemt`: `ACTIVE=False`, `ATTACHED=False` |
| 6 | no Venture Cell defines core authority | PASS | no authority-matrix / grant / reserved-matter definitions under `ventures/` |
| 7 | core imports no venture implementation | PASS | AST scan of 17 core packages: **0 offenders** |
| 8 | all contract references resolve | PASS | `scripts/ci/check_schema_refs.py` — every document-local `$ref` resolves |
| 9 | external-effect paths remain gated | PASS | one importable canonical gate; no second gate exists |
| 10 | shutdown succeeds | PASS | `AffectController.shutdown() == "shutdown_complete"` from a degraded state |
| 11 | Packages 3 & 4 are governed experiments, not self-activation | PASS | no `set_default()` exists in the seam; provider resolves to the original |
| 12 | original linker and `DurableWorkflow` remain rollback defaults | PASS | linker importable and byte-identical; `DurableWorkflow` **is** `engine.original_engine()` |

## What claims 11 and 12 mean concretely

Package 3's replacement lived in a private registry and could never have been
reached by the kernel. Package 4's *can* be reached — that was the point — so
the safety property moved from "structurally impossible" to "structurally
governed":

- `_ACTIVE is None` **means** the original, so the default is the absence of a
  choice rather than a stored one.
- Nothing is persisted, so a process restart cannot restore a replacement.
- There is deliberately no `set_default()`; a candidate has no API with which to
  install itself.
- Activation is a context manager, allowlisted per workflow id, and refuses
  nesting, empty allowlists, self-activation, and a missing validator.

## What this audit does not claim

It certifies the **Kernel**, not a venture, and not an external consequence. The
release contains zero Clean Verified Outcomes. Nothing here has been deployed,
spent, or contacted.

---

## Archive anchor verification (recorded 2026-07-26)

| | |
|---|---|
| Tag | `main-pre-canonical-v1-2026-07-19` |
| Type | **lightweight** — `git cat-file -t` resolves to `commit`, and `ls-remote` emits no `^{}` record |
| Resolves to | `3d9b5779a7093d6ddd07f225c8329ead6d0c6393` ✓ |
| GitHub Release | exists, id `360089207`, target `3d9b5779…`, not draft, not prerelease |
| `main` | `3d9b5779…` unchanged ✓ |
| archive branch | `3d9b5779…` unchanged ✓ |

```
$ git ls-remote --tags origin "refs/tags/main-pre-canonical-v1-2026-07-19*"
3d9b5779a7093d6ddd07f225c8329ead6d0c6393	refs/tags/main-pre-canonical-v1-2026-07-19
```

**Terminology, stated accurately.** This is the **remote pre-release archive
anchor**. It is not described as absolutely immutable: GitHub's own release
object reports `immutable: false`, and no branch- or tag-protection rule
preventing deletion or movement was observed. The anchor is real and
independently verifiable by anyone with repository access — that is what it
provides, and it is not the same thing as being undeletable.
