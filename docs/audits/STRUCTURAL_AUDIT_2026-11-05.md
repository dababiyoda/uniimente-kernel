# Structural audit — 2026-11-05

**Scope:** `uniimente-kernel`, the egregore control plane. The two
organs it governs (WealthMachineIntelligence and DALEOBANKS) were read for
duplication only and not changed.
**Classification:** maintenance. Advances INTENT-0027 ("find the canonical
owner, avoid duplication … leave a clean handoff"), whose success measure is
that a qualified agent can find canonical owners and duplications in under 30
minutes from in-repo records.
**Constraint:** nothing deleted; no sealed artifact touched; no authority, gate,
policy or contract behavior changed.
**Evidence:** the suite was 648 passed and 4 skipped before this change. It is
664 passed and 4 skipped after: the same tests plus the 16 new ones in
`tests/unit/test_common.py` and `tests/unit/test_repository_map.py`. Verifier
V2–V5 PASS. CI guard scripts 2/3/4 PASS. `ruff check .` is clean.

## Reference practice

The navigation layer follows conventions from mature open-source projects:

- a short root `ARCHITECTURE`-style codemap with invariants and cross-cutting
  concerns (matklad, *ARCHITECTURE.md*, 2021; rust-analyzer);
- documentation separated by purpose (Diátaxis: explanation, reference, how-to)
  with one index;
- root `CONTRIBUTING.md` for setup and conventions, separate from the agent
  contract;
- tool configuration in `pyproject.toml` (`[tool.pytest.ini_options]`,
  `[tool.ruff]`) and one command per CI job (`Makefile`);
- mechanical rules enforced by tests rather than by reviewer memory.

## Findings

| ID | Finding | Severity | Disposition |
|---|---|---|---|
| F-1 | `compiler/ucl_compiler.py` parses Alfonso's `reserved_authority` powers from `sovereignty.ucl` into `alfonso_powers` and never validates or emits them. A Constitution that dropped or altered those powers would still compile. | **material** (law compilation) | **Not fixed. Needs a founder decision.** Fixing it changes what the Constitution compiler accepts. Marked in source with `noqa` and a pointer here. Suggested check: `alfonso_powers ⊇ {shutdown, amendment ratification, grant revocation, reserved matters}`, mirroring `authority/authority-matrix.yaml`. |
| F-2 | The same `"sha256:" + sha256(json.dumps(sort_keys, separators))` digest was written inline 12 times across `foundry/`, `omnimorph/`, `loom/` and `capabilities/`. | maintainability | **Consolidated** into `common.sha256_ref`. The byte form is pinned by `tests/unit/test_common.py`. Each call site's `default=` is kept, so fail-closed sites still refuse non-JSON values. |
| F-3 | Fifteen private `_now()` copies, in two output shapes (`datetime` and ISO `Z` string). | maintainability | **Consolidated** in six non-sealed modules to `common.utc_now` / `utc_now_iso`, bound to the old private name so monkeypatch points survive. The other copies are in sealed or boundary code and were left on purpose (see `common/README.md`). |
| F-4 | Four copies of the `sha256:` reference shape check (prefix plus length 71). | maintainability | **Consolidated** into the `common.is_sha256_ref` predicate. Each module keeps its own error message, which tests match. |
| F-5 | There are two canonical-JSON forms. Most code uses `ensure_ascii=True`; `egregore/contracts.py` uses `ensure_ascii=False, allow_nan=False`. They produce different digests for non-ASCII text. | latent integrity risk | **Documented, not unified.** Unifying them would re-hash history. Recorded in `common/README.md` and in the `docs/ARCHITECTURE.md` cross-cutting conventions. |
| F-6 | 13 of the 40 top-level directories had no README, including `constitution/`, `authority/`, `contracts/` and `tests/`. The root README Layout table omitted 13 directories, among them `foundry/`, `egregore/`, `linker/` and `verifier/`. | navigation | **Fixed.** Every directory now has a README. The Layout table is complete and grouped by layer. `tests/unit/test_repository_map.py` prevents drift. |
| F-7 | `docs/` had 22 top-level documents and no index. Overlapping orders (`BUILD_ORDER.md`, `UNIIMENTE_FINAL_BUILD_ORDER.md`, `CANONICAL_EXECUTION_ORDER.md`) gave no precedence. | navigation | **Fixed.** `docs/README.md` indexes every document, assigns a status and states precedence. `BUILD_ORDER.md` is marked historical as an ordering source. Nothing was moved. |
| F-8 | The sealed artifacts were known only by reading frozen experiment specs. An innocent edit fails tests with no explanation. | contributor safety | **Fixed.** A "Sealed artifacts" list now sits in `docs/ARCHITECTURE.md`, `CONTRIBUTING.md` and the `constitution/` and `authority/` READMEs. |
| F-9 | In a shallow clone, two frozen-continuity tests fail with a bare `CalledProcessError`. | contributor friction | **Fixed.** The `conftest.py` report header warns and names `git fetch --unshallow`. The tests still fail, which is correct. |
| F-10 | The root README hard-coded "172 unit tests green". The real count is 660+. | stale claim | **Fixed.** The README now points to the commands that produce current evidence. |
| F-11 | The repo had no lint configuration. 62 pyflakes/bugbear findings, mostly unused imports, plus one useless expression (`url.port`). | hygiene | Unused stdlib imports were removed from non-sealed modules. The useless expression was made explicit (`_ = url.port`; the side effect is intended). A correctness-only ruff baseline is in `pyproject.toml`. Its per-file ignores document why each exception exists (sealed source, intentional re-exports, closure probes, test fixtures). |
| F-12 | Verifier V2 runs `tests/unit` only. CI job 1 runs the full suite, including `tests/integration`. | clarity | Documented in `tests/README.md`. No change: V2 is labelled "unit tests". |
| F-13 | The organs consume the Kernel through the pinned `uniimente-kernel-boundaries` package (both pin `4999acf`). Neither vendors the Gate. DALEOBANKS keeps its own hash-chained `services/ledger.py` (`DecisionLedger`, `KillSwitch`). | cross-repo | No action in this repo. This is the second ledger implementation named in the Final Build Order §9 ("multiple ledger designs"). It should be registered as an organ-local capability rather than merged. That is a DALEOBANKS-side item. |

## Deliberately not changed

- **Sealed bytes:** `constitution/`, `authority/`, `identity/*.yaml`,
  `policy/consequence_gate.py`, `events.spine.DurableWorkflow`/`WorkflowStep`,
  `evolution/repair/`, `evolution/migration/`.
- **Boundary distribution:** `adapters/`, `contracts/`, `events/`,
  `provenance/`. It gained no dependency on `common/`.
- **Directory moves:** none. Paths are referenced by release records,
  evidence patches and consumer pins. Moving them would break lineage.
- **CI workflow:** unchanged. Adding `make lint` as CI job 6 is recommended
  but changes the required-check set, so it is left for review.

## Recommended next steps (owner decision required)

1. F-1: add the reserved-powers check to the UCL compiler, with a failing
   fixture first.
2. Add `ruff check .` to Canonical CI so the clean baseline holds.
3. Ratify `docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml`. It is still
   PROPOSED, and it is the record that answers "who owns this concern".
4. Pick one canonical-JSON form for *new* record types (F-5) and record the
   choice as an ADR in `docs/decisions/`.
5. Split `closure/kernel_registry.py` (1,002 lines, 13 modules' closures in
   one file) into one registry file per module behind the same
   `build_registry()` entry point. This is a pure move, but it touches the
   verifier's V3 path, so it is best as its own reviewed PR.

## Five-role summary (protocol §1, compressed)

- **Builder:** the smallest change that makes ownership and sealed boundaries
  discoverable, plus deduplication where the byte form can be pinned.
- **Adversary:** the main risk is digest drift from a "harmless" helper. It is
  mitigated by pinning the byte form in tests and by keeping each caller's
  `default=`. A second risk is that docs rot. It is mitigated by the drift
  test.
- **Operator:** one `make` target per CI job, and a clear failure for shallow
  clones.
- **Beneficiary:** contributors and agents get an onboarding path and a list
  of files they must not edit.
- **Constitutional reviewer:** no authority, policy, grant or effect path
  changed. F-1 is escalated, not self-resolved.

**Decision:** `retain` (maintenance). **Rollback:** revert the single commit.
No data migration is involved, and no digest changes.
