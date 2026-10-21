# immune-8 step B: data-exposure audit (2026-10-21)

**Question.** Which instances of the P8 immune generator (`collective.immune_gaussian_instance`) have ever been generated, anywhere, and which review seeds are genuinely unused? Different seed numbers alone are not an independence argument, so the generator's seeding is audited too.

**Answer.** Review seeds **4000-4999** are declared for the immune-8 pilot. No committed code, test, pilot, admission, freeze or evidence file in either Mind lineage generates an immune instance from them. Nothing in the repository makes a different seed number produce the same, or an overlapping, Gaussian immune instance.

`scripts/p8_immune8_pilot.py` (`forbidden_seeds`, `guard`) and `tests/unit/test_p8_immune8_pilot.py` enforce this.

## Sources searched

| Source | Ref | How |
|---|---|---|
| This branch | `design/p8-immune8` at `239a87f`, then with the stress-gate audit merged (`09555108`) | `git grep` of `*.py`, `*.json` and `*.md` for `immune_gaussian_instance`, `immune_instance(`, `collective_immune`, `immune_detect` and for the seed ranges 4000-6999; `git log -S` over the full history |
| PR #179 lineage | `origin/claude/greg-mind-lineage-convergence` at `0067be6` (fetched 2026-10-21) | the same searches, plus every `freeze*.json` and `prereg*.json` under `cortex/evaluation/` |
| Every other remote branch | 194 refs, fetched 2026-10-21 | `git grep` for the two generator entry points under `scripts/`, `cortex/` and `tests/` |
| Admission freezes | `docs/evidence/greg-genome-admission/2026-10-1{3,4,5,6}-v*/freeze.json` | each freeze's held-out seeds and whether it includes `collective_immune` |
| P8 freezes and splits | `evolution.IMMUNE_SPLITS`, `CR_SPLITS`, `CR_CANARY_SEEDS`, every `freeze.json` under `docs/evidence/greg-protected-evolution/` | the seeds each split or freeze declares |

**Not available:** uncommitted runs in other sessions or worktrees. A builder measurement that left no commit cannot be audited; the immune-7 pilot README records one (native regimes, review seeds 3000-3059), and that range stays excluded.

## Immune instances ever generated

| Seeds | By | Generator path |
|---|---|---|
| 0-9 | unit tests, admission development seeds | Gaussian generator directly, and `immune_instance` (regime `seed % 4`) |
| 1000-1029 | admission v1 (2026-10-13), held out | `immune_instance`; before `BENCHMARK_REVISION` every seed was Gaussian |
| 1200-1229 | admission v3 (2026-10-15), held out | `immune_instance`; seeds `% 4 == 0` are Gaussian |
| 1100-1129, 1300-1329 | admissions v2 and v4 | `collective_immune` was **not** measured; reserved anyway |
| 3000-3011, 3000-3059 | native-regime tests; builder measurement (`65b9acc`, recorded by immune-7) | `immune_instance` |
| 3100-3999 | immune-7 pilot | Gaussian generator |
| 7000-7039, 8000-8059 | P8 cycle 2: train looked at; held-out generated when the evaluator was sealed, never scored | Gaussian generator |
| 8600-8839 | immune-7's registered cycle-7 split | never generated; reserved, and not used here |

PR #179's own admission harnesses (`cortex/evaluation/genome_admission/run*.py`, seeds 1001-1040, 2001-2040 and 5001-5040) have a `collective` family, but it is a different benchmark in `greg/cognition/solvers.py`. None of them calls the immune generator. PR #179's `cortex/evaluation/evolution/` evolves routing policy on frozen routing results and draws no immune instance.

## Can a different seed reproduce or overlap an exposed instance?

`immune_gaussian_instance(seed)` draws everything from `random.Random(7_400_000 + seed)` and `numpy.random.default_rng(7_400_000 + seed)`.

- **No modulo or aliasing inside the generator.** The seed only offsets the two RNG seeds. Distinct seeds give distinct integer RNG seeds, so the instances are independent draws.
- **Regime aliasing through `immune_instance`.** `immune_instance(s)` with `s % 4 == 0` *is* `immune_gaussian_instance(s)`. Admission seeds `% 4 == 0` therefore count as exposed Gaussian instances (see the table). No admission ever used 4000-4999.
- **Other generators that share an RNG stream.** Every integer-offset RNG in both lineages was listed:
  - immune native regimes at 7_410_000, 7_420_000 and 7_430_000;
  - physarum at 7_300_000 and 7_310_000;
  - flock at 7_600_000, 7_610_000 and 7_620_000;
  - 7_500_000, 7_100_000, 7_110_000, 7_200_000, 9_000_000, 5_500_000, 4_400_000, 3_300_000, 2_200_000 and 1_700_000;
  - small offsets 910_000-980_000 and 1000-4000.

  For a collision, a generator with offset `c` would need a used seed of `7_404_000 - c` to `7_404_999 - c`. For the immune native regimes that is a negative seed. For every other offset it is a seed above 94,000. No range in either lineage reaches that high (searched: `range(` with five or more digits). String-seeded RNGs (`f"constraint_release:{seed}"` and the like) hash their seed differently and cannot collide with an integer seed.
- **Python and numpy streams.** A Python `Random` and a numpy `default_rng` seeded with the same integer produce unrelated streams. Nothing in the repository seeds the immune generator's numpy stream otherwise.

## Declared pilot data

| Use | Seeds | Size |
|---|---|---|
| Train T1, T2, T3 | 4000-4119, 4120-4239, 4240-4359 | 120 each |
| Look pool | 4360-4999 | 640 |

## Confirmatory seeds (for a later freeze; not generated by this pilot)

Free P8-reserved seeds were computed at this commit. They are seeds in `admission.P8_RESERVED` (7000-9199) that are not in any immune or constraint-release split, canary, freeze or admission:

- 7040-7199, 7260-7299, 7390-7399, 7460-7499, 7590-7599, 7660-7699, 8540-8599, 8840-9199;
- 720 seeds in all.

8600-8839 stay registered to immune-7's cycle-7 split. They are not proposed here, because no valid pre-registration authorizes their use.
