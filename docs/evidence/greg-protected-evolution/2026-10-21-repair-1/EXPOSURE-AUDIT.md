# repair-1 step B: data-exposure audit (2026-10-21)

**Question.** Which instances of the repair generator (`developmental.repair_instance`, family `develop_repair`) have ever been generated, anywhere, in either Mind lineage? Which review seeds are genuinely unused for it? Different seed numbers alone are not an independence argument, so the generator's seeding is audited too.

**Answer.** No committed code, test, pilot, admission, freeze or evidence file in either lineage has generated a repair instance from any seed outside **0-9, 1000-1029 and 1100-1129**. Review seeds **3000-3999 are unused for this generator.** The pilot declares them in step C. Nothing in the repository makes a different seed produce the same, or an overlapping, repair instance.

Step A (`c4a8abf4`) generated nothing outside development seeds 0-9.

## Sources searched

| Source | Ref | How |
|---|---|---|
| The all-lineage ledger | `docs/evidence/greg-data-exposure-ledger.json` (rebuilt at `0f55549a`; PR #179 pinned at `a3106f6a`) | `exposed()` for the family `develop_repair` and for the generator `greg.cognition.genomes.developmental:repair_instance`, over seeds 0-99,999 and over the review ranges 3000-3999 and 4000-4999. Output: `exposure-query.json` |
| This branch | `design/p8-repair` from `6cb7c319` | `git grep` and `git log -S` for `repair_instance(` and `genome:develop_repair` |
| PR #179 lineage | `origin/claude/greg-mind-lineage-convergence` at `a3106f6a` | `git grep` for `develop_repair` and `repair_instance` |
| Every remote branch | 197 refs, fetched 2026-10-21 | `git grep` for `repair_instance(`, `"develop_repair").instance` and `repair_item(` in `*.py`; then every file that calls a generic `.instance(` (28 files), checked for the families and seeds it draws |
| Admission freezes | v1-v4 under `docs/evidence/greg-genome-admission/` | which freezes measure `develop_repair`, and on which seeds |
| Other Layer-4 evidence | `docs/evidence/greg-developmental-sweep/2026-10-14` (on `origin/claude/greg-integration-178-184-20261021` and two other branches) | its generator |

**Not available:** uncommitted runs in other sessions or worktrees. A measurement that left no commit cannot be audited.

## Repair instances ever generated

| Seeds | By | Role | Looked at |
|---|---|---|---|
| 0-9 | admission v1 and v2 development seeds; `tests/unit/test_genomes_developmental.py`; `test_genomes_library.py`'s first-answer loop; `test_greg_competency_compiler.py` (seed 0); this lane's step-A tests | dev | yes |
| 1000-1029 | admission v1 (2026-10-13), freeze `496c85b` | admission held-out | yes (results bind the freeze) |
| 1100-1129 | admission v2 (2026-10-14), freeze `8e37cd8` | admission held-out | yes |

These were checked and found **not** to touch the generator:

- **Admissions v3 (1200-1229) and v4 (1300-1329)** did not measure `develop_repair`. Neither freeze lists it, and the ledger records no exposure.
- **PR #179's admission and operation harnesses** have their own benchmark families, and none of them is `develop_repair`:
  - `cortex/evaluation/genome_admission/run*.py` uses seeds 1001-1040, 2001-2040, 3001-3040 and 5001-5040;
  - `run_operations.py`, on the integration branch, uses 9000-9029.
- **The developmental sweep** (2026-10-14, 40 seeds) drives `MICAField` and `simulate_transport` directly. It never calls `repair_instance`.
- **Other test files that call a generic `.instance(seed)`** draw their own families on development seeds, or on review seeds for other families (`mc_importance` 3002, `grid_dijkstra` 1, `critical_path` 3000-3199, `game_lp` 3000-3099 and others).

No P8 cycle, freeze, split or canary has ever drawn a repair instance. `REPAIR_SPLITS` is empty.

## Can a different seed reproduce or overlap an exposed instance?

`repair_instance(seed)` draws everything from `random.Random(f"genome:develop_repair:{seed}")`. The ledger records this as the generator's only PRNG seeding expression.

- **A string seed.** CPython seeds `Random` from a string through SHA-512 of its bytes. Distinct seeds give distinct strings, so they give unrelated streams. There is no modulo, offset or regime aliasing.
- **No other generator uses this string.** `git grep` across all 197 refs finds the prefix `genome:develop_repair:` only in this function. Every integer-offset generator in either lineage (the immune, physarum, flock and other streams, listed in immune-8's audit) seeds `Random` with an integer. An integer seed and a string seed never produce the same state.
- **No regime delegation.** The ledger's aliasing sample, run on development seeds 0-9, reports no equivalence and no cross-generator identity for this generator. Its overlap report names nothing for it.
- **The world itself is not seeded.** `MICAField(width, height)` builds the TARGET_FORM_001 lattice and tissues deterministically from the size alone. All variation (lattice size, damage, events, message loss and its RNG seed, controller condition) comes from the string-seeded stream above.
- **A residual, stated for completeness.** Each instance carries a message-loss RNG seed, `rng.randrange(2**31 - 1)`. Two instances could share it with probability about n²/2³². Sharing it would correlate only their loss draws, never their topology or damage.

## The stress derivations

The `late` derivation (step A) chooses its failed units with `random.Random(f"p8-repair-late:{key}")`, where `key` is the train item's id. It derives from train items already generated and draws no new instance.

## Declared pilot data (step C)

| Use | Seeds | Items |
|---|---|---|
| Train T1 / T2 / T3 | 3000-3119 / 3120-3239 / 3240-3359 | 120 each |
| Look pool (held-out resampling) | 3360-3999 | 640 |

Excluded from the pilot:

- **Every seed outside 3000-3999,** except development seeds 0-9, which only tests use.
- **These ranges in particular:** 1000-1029, 1100-1129, 1200-1399, 1400-1429, 5001-5040, 6501-6840, 7000-9199 and 9300-9339.

## Confirmatory seeds (for a later freeze; not generated by this pilot)

Free P8-reserved seeds for this generator lie in 8840-9199. That range is free of every registered immune, constraint-release and repair split and of every canary.

**One caution for any draft pre-registration.** `origin/claude/greg-integration-178-184-20261021` spends **9000-9029** as admission held-out seeds for its operation families. A different generator is involved, but `admission.spent_seeds()` will reserve those seeds once that branch merges. A draft split from 8840-9199 should therefore avoid 9000-9029.
