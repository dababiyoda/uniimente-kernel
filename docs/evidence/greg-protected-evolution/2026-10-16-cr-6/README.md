# P8 cycle 6: constraint-release search policy, cover/1, 120/240 split (2026-10-21): RETAIN

Every number below is copied from `cycle-cr-6.json`. Nothing was re-run. The directory carries the date of the
design's first commit (2026-10-16); the cycle ran on 2026-10-21.

## Protocol

| Item | Value |
|---|---|
| Pre-registration | `PREREGISTRATION.md` and the two design pilots in `pilot/`. Freeze and seals committed at `70bb77d`, before the run. |
| Run | once, through the clean room (`fresh detached checkout of 70bb77d20e4c5e0123050307e7adebeaa4bfba56`), pinned to one core, exit 0 (`cycle-cr-6.log`); 2026-10-21T12:21:33Z to 12:30:35Z |
| Freeze check | `sha256:9378b56e91ba266f...` matched; `source_dirty` []. `freeze.commit` reads "unknown: a shallow clone's history may not reach the commit that added it", as in cycle 5; the freeze was committed at `70bb77d`. |
| Confinement | Landlock ABI 7, arbitrary source refused, repository listing denied, one thread |
| Search | cover/1, lhs 0, 5 generations, population 8, search seed 20261021; 51 configurations evaluated; selection unchanged (lowest train mean) |
| Split | `cycle-6`: train 7880-7999 (120), held-out 8060-8299 (240) |

## Result

| Stage | Outcome |
|---|---|
| Trigger | 49.2% of train items failed against random restart (threshold 25%): **triggered** |
| Train | candidate `cfg-4398ea71018f` mean loss 0.004205 against the incumbent's 0.008153: **48.4% better** |
| Changed keys | `p_restart` 0.0 → 0.807; `p_extra_mutation_recombined` 0.5 → 0.55 |
| Adversarial | every output verified. `lean` 0.009947 → 0.006105 (−38.6%); `fewval` 0.010704 → 0.008258 (−22.9%): **passed** |
| Held-out (one look, n = 240) | wins 105, losses 73, one-sided sign p = **0.009946**; mean loss 0.005784 against 0.008221 (**29.6% lower**) |
| Decision | **RETAIN**: `PROPOSED_NOT_APPLIED`. `authority_created` false. |

## Reading

- **Protected evolution has kept an improvement for the first time.** It took six cycles and the previous five were
  REJECTs. The improvement was found by the trusted parent's search, checked by the adversarial gate and verified on
  a held-out split the candidate could not see or alter.
- **Multiple-testing corrections, as pre-registered:**
  - **It survives** the four-attempt threshold on this target: p = 0.009946 < 0.05/4 = 0.0125.
  - **It does not survive** the programme-wide threshold: 0.009946 > 0.05/6 = 0.00833 (six P8 cycles). Read across
    the whole programme, this RETAIN could be the one chance success in six tries at alpha 0.05.
- **The pilot's prediction held.** Pilot 2 gave P(RETAIN) about 0.63 at alpha 0.05 and about 0.50 at 0.0125. The
  candidate is restart-heavy (`p_restart` 0.807), as the pilots and cycle 5's pool said retaining candidates are.
- **The candidate does not beat the target's own baseline.** The record reports random restart, not part of the
  rule: on held-out, the candidate beats it 80 times and loses 89 times (one-sided p = 0.78). Random restart's mean
  loss is 0.005070, lower than the candidate's 0.005784. The improvement is real against the shipped configuration,
  but the plain baseline algorithm is still at least as good. That agrees with admission v2 and v3, where random
  restart beat the genome 15-5 and 13-10, and with cycle 4's errata. The adoption decision should weigh this
  configuration against swapping the genome's search for random restart outright.
- **What the design pilots did and did not contribute.** They refuted a selection-rule change before the freeze
  (`pilot/README.md`). What changed from cycle 5 was power: 120 train items and 240 held-out items, on a fresh split
  and seed. Train size had no clear effect in either pilot. This record cannot separate the effect of the larger
  held-out set from a lucky train draw; pilot 1 showed the draw dominates.

## What RETAIN does and does not do

- **Proposed, not applied.** The proposal is in the record: change `CR_DEFAULT_CONFIG` in
  `greg/cognition/genomes/developmental.py` to the candidate. Rollback is the incumbent `cfg-111751096c0d`.
  Activation is "a reviewed change adopting the configuration; founder decision".
- **Adoption needs a canary first:** re-admit `develop_constraint_release` with the proposed configuration on fresh
  seeds, and keep comparing it with the incumbent and random restart. Adoption would bump the genome's version and
  its pin in `EVOLVABLE_CONFIG_PINS`, and its admission verdict would route as stale until re-admitted.
- **Section 31 item 7 is met at the proposal level**, at alpha 0.05 and at the target's four-attempt correction. It
  is not met under the programme-wide correction, and no improvement is in use until the founder adopts one.
- **The cycle-6 held-out split (8060-8299) is spent.**
