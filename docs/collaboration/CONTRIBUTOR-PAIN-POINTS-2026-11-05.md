# Contributor pain points — register, 2026-11-05

Dated record (`docs/collaboration/INDEX.md`). The next monthly review writes a
new dated file and keeps this one (`docs/REVIEW_CADENCE.md`).

**Sources, and their limits:**

- The repository's own records at #196 head `3a2ba265`: 1,690 commits, the
  collaboration records, the CI workflow comments and the `.github` templates.
- A survey on board #96 (comment 6648797976). It invites every contributing
  session to confirm, correct or add.
- Mining was done by read-only sub-agents of session
  `session_01KucyfnCuSTnjx5Fa6T4A3d`. Three citations were re-checked by hand:
  `canonical-ci.yml:49-53`, commit `31a9abe3` and `VALIDATION.md:61`.
- Recurrence counts are keyword and record counts, not measured time.
- Discussion #89 and replies to the survey are not yet folded in.

**Status words:**

- **fixed here**: this PR changes it.
- **marked**: made visible; the decision belongs elsewhere.
- **proposed**: a fix is named; the owner is unassigned until claimed on #96.
- **founder**: needs Alfonso.

## P: friction reported in contributors' own records

| ID | Pain point | Evidence (short) | Recurrence | Who | Status and smallest fix |
|---|---|---|---|---|---|
| P-1 | Generated records re-recorded after nearly every merge: exposure ledger, `foundry/owned-source.json`, evidence indexes, step maps | commits `98a2ab0c`, `ea90b4b4`, `a5d642c9`; 39 commit subjects say regenerate, re-record or refresh | ~56 commits | agents, CI | **proposed:** generate in CI and commit only through a `--check`ed script, or stop tracking derived files. Touches other owners' surfaces, so it needs a split |
| P-2 | Canonical job 1 at or over its time limit | `canonical-ci.yml:49-53`: "86 minutes … cancelled at 90 … Raised to 120"; jobs 6 and 9 also raised | limit 30→45→75→90→120 | CI, every PR | **proposed:** shard the full suite (matrix or `pytest-xdist`). Job 9 (verifier V2) re-runs `tests/unit`, a second full-suite cost. CI-owner decision |
| P-3 | Merge conflicts in generated manifests | `31a9abe3` "owned-source.json conflicted on adjacent entries and was regenerated"; `4b445db8`, `937d4c75` | 5+ commits | agents | **proposed:** a `.gitattributes` merge driver that reruns `scripts/refresh_owned_source.py`; same owner split as P-1 |
| P-4 | Not knowing which branch is live (`main` vs #196) | `INTEGRATION-196-HANDOFF-2026-10-22.md:61-63`; `START_HERE.md`: "searching only main already caused a duplicate compiler"; this session's first pass also went to stale `main` (#268) | 5+ | agents, founder | **fixed here** (AGENTS.md working facts and reading order step 1). Still **founder:** `main` itself names no live branch, and a `main`-only reader never sees this file |
| P-5 | Entry files disagree on reading order | six files, five orders (AGENTS, CLAUDE, README, CONTRIBUTING, START_HERE, SOP §2); CONTRIBUTING named #117 | 4+ | agents | **fixed here:** one canonical order in AGENTS.md, which the others defer to; `test_repository_map.py` enforces it |
| P-6 | Mutation-gate anchors go stale when code moves | `5ad39868` "CI job 6 STALE"; `a7990bc1`, `80a3eeb5` | ~6 repairs in 52 mutant commits | CI, agents | **proposed:** anchor on symbols (AST) instead of exact text |
| P-7 | Receipts bound to a moving head SHA | `collaboration-receipt.yml:97`; `INTEGRATION-196-HANDOFF:168` "every push … needs a fresh receipt" | 4 | agents | **proposed:** bind the receipt to the base SHA plus the AGENTS.md blob hash. Receipt-owner decision |
| P-8 | Environment-sensitive tests: shallow clones, bubblewrap, load-sensitive SIGKILL tests, missing optional dependencies | `b0b89071`; `ONE-MACHINE-TRUNK-2026-10-14.md:49`; `HANDOFF-2026-10-21.md:152`. Reproduced this session: three test files and two seed mutants failed until `requirements-dev.txt` and `requirements-cognition.txt` were installed | 6+ | agents, CI | **marked** (AGENTS.md working facts); **proposed:** pytest markers that skip with a stated reason when an optional dependency is missing |
| P-9 | Egress-blocked hosts in cloud sandboxes | `FOUNDER-ACTIONS-2026-10-22.md:30`; ledger "network policy refuses data.cityofnewyork.us" | 4+ | agents | **proposed:** a documented fixture mirror |
| P-10 | Two different PR templates (`PULL_REQUEST_TEMPLATE.md`, `pull_request_template.md`) | edited separately (`a4bf4f9e` vs `4ff2f044`) | 2 files, ~9 commits | everyone | **marked:** the uppercase file names the canonical one. **founder:** merging them changes bytes that `foundry/systems/commissioning.py` copies into fixture repos |
| P-11 | Advisory claim races | `VALIDATION.md:61` "claims landed 22 s apart … not atomic" | 3 | agents | **proposed:** keep (START_HERE already says claims are notices), or use a label as the lock |
| P-12 | Copy-pasted digest helpers that hash differently | `DIGEST-RULE-CONSOLIDATION-2026-10-30.md` | systemic | agents | **owned by #246 (merged) and #254 (open)**, not touched here |
| P-13 | Integration stack too large to review | `INTEGRATION-196-HANDOFF:181` "Alfonso cannot review a 1000-commit stack" | 2 | founder | **founder:** merge green intermediate heads to `main` more often |

## D: documentation gaps for humans and agents (orientation audit)

| ID | Gap | Status |
|---|---|---|
| D-1 | No docs index; 28 top-level docs | **fixed here:** `docs/README.md`, guarded |
| D-2 | ~170 collaboration records with no current-vs-historical signal | **fixed here:** `docs/collaboration/INDEX.md` (by pattern, so it never needs regenerating) |
| D-3 | 13 directories without a README; 16 missing from the README layout | **fixed here**, guarded |
| D-4 | `docs/ARCHITECTURE.md` predates `greg/`, `cortex/`, `governance/` and `acceptance/` | **fixed here:** § Current module map |
| D-5 | No entry file names the protected-file manifest | **fixed here:** AGENTS.md task table, `ARCHITECTURE.md`, `governance/README.md` |
| D-6 | Test, verifier and integrity commands appear in one file only | **fixed here:** AGENTS.md working facts |
| D-7 | Stale "172 unit tests green" in README | **fixed here:** marked historical; points to the commands |
| D-8 | `START_HERE.md` says the SOP is "absent from main" | **marked** in `collaboration/INDEX.md`; START_HERE itself is left alone because three open branches edit it |
| D-9 | `ARCHITECTURE-OWNERSHIP-MAP.yaml` still PROPOSED (2026-08-22) and missing the new packages | **founder:** ratify or replace |
| D-10 | The copilot instructions say VEPMC is the bottleneck, against the 2026-10-30 sequencing | **fixed here:** annotated |

## S: structural risks found by measurement

| ID | Finding | Evidence | Status |
|---|---|---|---|
| S-1 | 9 two-way dependencies between top-level packages (for example `greg`↔`cortex`, `greg`↔`foundry`, `closure`↔`foundry`) | `python scripts/repo_review.py` | **fixed here as a ratchet:** no new pair; the list can only shrink |
| S-2 | `provenance/witness.py:capability_genome()` imports `capabilities.genome`, which is not in the published boundary distribution, so a consumer install raises ImportError if it is called | `pyproject.toml` packages; `provenance/witness.py` | **ratcheted and recorded.** **proposed:** move `capability_genome()` registration out of the boundary package. Boundary-owner decision, needs a version bump |
| S-3 | `scripts/ci/check_seed_mutants.py` is run by no workflow | `.github/workflows/*` | **proposed:** add it to the `cortex_seed` job. Local run: 7/7 mutants caught with the dependencies installed, 5/7 without `rfc3161_client`, so a gate outside CI can break silently |
| S-4 | No lint configuration and no lint in CI | `pyproject.toml` | **proposed:** a correctness-only ruff baseline (pyflakes and bugbear). It is in draft #268 against `main`, to be ported once the integration line takes it |
| S-5 | `greg/` is about 87k of 170k lines; 12 files exceed 1,500 lines (`greg/missions.py` 3,683) | weekly size profile | **marked:** tracked as a trend in the weekly report, not a rule |
| S-6 | F-1: `compiler/ucl_compiler.py:147-153` parses Alfonso's `reserved_authority` powers and never validates them | source | **founder:** a fix changes what the Constitution compiler accepts |

Answer from the PR's product-delta question: **none.** GREG can do nothing new
because of this register. It removes orientation blockers and makes the
remaining ones owned or visible.

## Addendum, pass 3 (same day): board evidence and two instruments

**Survey replies:** none yet, on #96 or through the `contributor-friction` form.
Contributors independently posted the following on #96 after the survey (comments
6651587410, 6655711782, 6657787629):

| ID | Update | Status |
|---|---|---|
| P-2 | Confirmed by four more sessions. Job 1 was cancelled at exactly 120 minutes on #221, #260, #264, #265, #266, #270 and #271, each time inside the late mutation steps with every completed step green. #196's own job 1 took 99 minutes on `75a8fdf4` and 1:59:49 on another run. Session `session_01Kucyfoabgsg6W8H8xj4qea` proposes moving the mutation steps into a separate job "1b · Mutation gates" (about 25 min) instead of raising the limit | **proposed by a contributor:** the split in 6657787629. Integrator decision |
| P-14 (new) | **Environment-only failures.** A runner whose `/tmp` was tmpfs made 20 `test_greg_backup.py` tests fail on #263, because `greg/backup.py` correctly refuses volatile stores. Locally, missing `rfc3161_client`, `scipy`, `networkx` and Python Playwright failed or emptied test files, and failed 2 of 7 seed mutants | **fixed here (diagnosis):** `scripts/dev_env_check.py` names each cause before tests run. **proposed:** `TMPDIR: ${{ runner.temp }}` on job 1 (6651587410). CI-owner decision |
| P-6 | Stale mutation anchors | **fixed here (early detection):** `repo_review.py` gate liveness, 614 literal anchors in about 3 s, a hard finding in the unit suite. Verified against history: on `5ad39868~1` it names the anchor CI job 6 reported STALE. Six gates with non-literal anchors are listed as not statically checkable |
| S-3 | `check_seed_mutants.py` unwired | **ratcheted:** the only `KEPT_UNWIRED_GATES` entry; a second unwired gate now fails a unit test |
| S-4 | No lint | **measured:** `repo_review.py --lint` baseline is 447 ruff F/E9 findings (F811 249, F401 167, F841 24, F541 6, F402 1). A trend in the weekly report, never a gate |

**Later the same day, 13:00Z:** the #196 integrator adopted the contributor proposal for P-2. Base `6a96e020` runs the mutation gates as Canonical CI job "10 · Mutation gates" (26 min on #271's run 42031832471), separate from job 1's full suite. P-2's status is **addressed upstream (split landed)**. Whether job 1 alone now fits its limit is measured by the next runs, not assumed here.

**2026-11-06, S-2 (boundary import):** fixed without breaking callers.
- `provenance/witness.py` now declares its genome as plain data (`GENOME_SPEC`), and the kernel builds it with `capabilities.specs.genome_from_spec`.
- `capability_genome()` is kept as a deprecated wrapper. In a boundary-only install it fails with an ImportError that names `GENOME_SPEC`, where before it failed with a bare `ModuleNotFoundError`.
- `tests/unit/test_import_layering.py::test_boundary_distribution_works_installed_alone` installs only the four published packages and imports every module. It fails on the old code and passes now.
- The wrapper is the last boundary import. Removing it needs a boundary version bump, which is the boundary owner's decision, so the `KEPT_BOUNDARY` entry stays with its new reason.
- `capabilities/genome.py` is untouched because frozen evaluations pin it by digest.
