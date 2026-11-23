# P8 cycle 4: constraint-release search policy (2026-10-15) — REJECT at the held-out gate

**What this is:** the fourth protected-evolution cycle, and the first run under the committed-freeze rule. Every number below is copied from `cycle-cr-4.json` by script. Nothing was re-run.

> **Errata:** an independent review on 2026-10-15 corrected two statements in this README. The original wording is kept below, and each correction is listed under *Errata (2026-10-15 independent review)* at the end. The frozen files are unchanged.

## Protocol

| Item | Value |
|---|---|
| Pre-registration | `PREREGISTRATION.md` and `freeze.json`, committed in `2cbb43d` before the cycle ran |
| Freeze check | the record names the freeze (`sha256:83f5285e89323f3c...`). The trusted code, rule, constants, settings, split and both seals matched at the start, before every evaluation and before the record was written. `source_dirty` is empty. |
| Run | once, in a clean worktree at `2cbb43d`, pinned to one core, exit 0 (`cycle-cr-4.log`); 2026-10-15T13:35:37 to 13:39:28 UTC |
| Confinement | Landlock ABI 7; repository listing denied; signals scoped to the domain. The parent probed on every run that the sandbox could not read the evaluator's module, and checked the method module each sandbox imported against the freeze. |
| Split | train 60 (seeds 7400-7459), held-out 90 (seeds 7500-7589), 350 identities excluded |

## Result

| Stage | Outcome |
|---|---|
| Trigger | 53.3% of train items failed against random restart (threshold 25%): **triggered** |
| Search | 39 configurations evaluated in the closed space |
| Train | candidate `cfg-afdb92cb42e7` mean loss 0.006082 against the incumbent's 0.007975: **23.7% better**, past the 1% bar |
| Changed keys | `offspring` 4 → 2, `p_extra_mutation_recombined` 0.5 → 0.756 |
| Adversarial | every output verified: True. `fewval` 0.014268 → 0.011466; `lean` 0.010061 → 0.008762. **Both stress sets improved; passed.** |
| Held-out (one look) | candidate wins 26, losses 37 of 90; one-sided sign test p = 0.935041; mean loss 0.006233 → 0.009114 (-46.2%) |
| Decision | **REJECT**. No proposal; nothing applied. |
| Reported, not in the rule | candidate against random restart on held-out: 22-46 (p = 0.998907); random restart's mean loss 0.00449 |

## Reading

- **The candidate fit the training split and failed on the held-out split.**
  - It was 23.7% better on 60 train instances and better on both derived stress sets.
  - Then it lost 26-37 on 90 fresh instances, with 46% worse mean loss.
  - The adversarial gate could not catch this, because its stress sets are derived from the same train items.
  - The single held-out look did catch it. This is the case the rule exists for.
- **Read against the pre-registered two-attempt threshold:** the held-out p-value is 0.935, far from both 0.05 (the rule) and 0.025 (the Bonferroni threshold for a second attempt on this target).
- **The headroom is real, but this closed space does not reach it.** Random restart beat the incumbent on 53% of train items and has a lower held-out mean loss than either configuration (0.0045 against 0.0062 and 0.0091). The search space varies only the evolutionary operator's parameters (`p_restart` is in the space, but the search did not move it).
  - Whether a restart-heavy configuration would win is a hypothesis for a new pre-registered cycle with a fresh split, not a conclusion of this one.
- **Protected evolution has still never kept an improvement:** four cycles, four REJECTs.
  - Cycle 1: an overfit.
  - Cycle 2: a scarce-sample fragility.
  - Cycle 3: a validation-stress loss.
  - Cycle 4: a held-out loss.
  - Section 31 item 7 remains unmet.

## Reproduce

```
git worktree add /tmp/p8c4 2cbb43d && cd /tmp/p8c4
PYTHONPATH=. taskset -c 1 python -m greg.cognition.evolution --target constraint_release \
  --freeze docs/evidence/greg-protected-evolution/2026-10-15-cr-4/freeze.json --out /tmp/cycle-cr-4.json
```

The cycle refuses to run unless every frozen input matches, and it refuses a dirty tree.

## Errata (2026-10-15 independent review)

Each item quotes the original wording, which stays in place above, and states the correction. The record's numbers were recomputed from `cycle-cr-4.json`; the protocol's seed ranges and settings were checked against `freeze.json` and `CR_SPLITS` in `greg/cognition/evolution.py`, which the record does not hold. No frozen file was changed, and nothing was re-run.

1. **"By script".** Original: "Every number below is copied from `cycle-cr-4.json` by script."
   - No script is committed for this README. The directory holds only `PREREGISTRATION.md`, `README.md`, `cycle-cr-4.json`, `cycle-cr-4.log` and `freeze.json`.
   - The review recomputed the *Result* table from the record and checked the *Protocol* table against the record, `freeze.json` and `CR_SPLITS` (the seed ranges are not in the record); they match.
   - The *Reading* section is hand-written. Item 2 corrects one of its claims.
2. **The search did move `p_restart`.** Original: "**The headroom is real, but this closed space does not reach it.**" and "(`p_restart` is in the space, but the search did not move it)".
   - Three of the 39 evaluated configurations set `p_restart` above 0:
     - `cfg-c0b27b4df69e` at 0.064 (generation 1);
     - `cfg-2272322885e9` at 0.156 (generation 1);
     - `cfg-0e070b72573f` at 0.339 (generation 5).
   - All three had a worse train mean loss than the incumbent's 0.007975: 0.011097, 0.008155 and 0.007983. The last was worse only marginally.
   - The space allows `p_restart` up to 1.0 (`CR_CONFIG_SPACE` at `2cbb43d`). Nothing above 0.339 was tried.
   - The record therefore shows that this search did not reach the headroom, not that the closed space cannot. The restart settings it tried lost on train, and a restart-heavy configuration remains untested. Any hypothesis for the next cycle has to start from that.
3. **Note on the random-restart comparison.** The sentence "Random restart beat the incumbent on 53% of train items and has a lower held-out mean loss than either configuration (0.0045 against 0.0062 and 0.0091)" is accurate as written.
   - The record compares random restart with two configurations only:
     - the incumbent, on the train failure rate (32 of 60 items, 53.3%) and on held-out mean loss;
     - the candidate, on held-out mean loss and the paired held-out count (46-22 in random restart's favour).
   - The other 37 lineage entries record only `train_mean_loss`.
   - `greg/path.json` stretched the sentence to "every configuration it searched". The Founder Intent Ledger's "beat both configurations on held-out" rests, for the incumbent, on mean loss alone, with no paired test. Both records are corrected.
