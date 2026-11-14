# P8 cycle 6 canary (2026-10-21): CANARY_PASSES; random restart is still at least as good

Every number below is copied from `canary.json`. Nothing was re-run.

- **Protocol:** the pre-registration (`PREREGISTRATION.md`) and its rules were committed at `82bb645` and pushed at
  `8f3de21` before any canary instance existed. The run was made once at `82bb645` from a clean tree, pinned to
  one core: 148 s, exit 0 (`canary.log`).
- **Seeds:** 8300-8539 (240 fresh instances).
- **Nothing was applied:** `CR_DEFAULT_CONFIG` and the genome version are unchanged.

| | Mean loss | vs incumbent (W-L-T, one-sided sign p) |
|---|---:|---|
| incumbent `cfg-111751096c0d` (`p_restart` 0) | 0.011135 | |
| proposal `cfg-4398ea71018f` (`p_restart` 0.807) | 0.007357 | **107-74-59, p = 0.00857**, 33.9% lower mean |
| random restart | **0.006393** | 116-62-62, p = 3.2e-05 |

| Further check | Result |
|---|---|
| Proposal vs random restart | 79-95-66. Random restart has a 15.1% lower mean loss; its one-sided sign p is 0.128, not significant |
| Stress, incumbent → proposal | lean 0.012516 → 0.007727; fewval 0.014605 → 0.010025; every answer verified |
| By subregion (mean loss: incumbent / proposal / random restart) | loose due dates (119): 0.017768 / 0.010921 / 0.009126; tight due dates (121): 0.004612 / 0.003851 / 0.003706 |

## Reading

- **The proposal replicates.** On 240 new instances it beats the incumbent with nearly the same strength as cycle 6's
  held-out look (107-74 here, 105-73 there).
- **Random restart is the strongest arm on every measurement so far.**
  - In this canary it has the lowest mean loss overall and in both subregions. Against the incumbent it wins
    116-62.
  - Head to head with the proposal it is not significant here (p = 0.128), nor in cycle 6's record (89-80).
  - Admission v2 and v3 (15-5 and 13-10) and cycle 4's held-out point the same way.
- **For the founder's adoption decision, the evidence ranks the options as:**
  1. random restart;
  2. the proposal;
  3. the incumbent.

  The gap between 1 and 2 is consistent but not significant on either head-to-head measurement. Adopting random
  restart would mean replacing the evolutionary search inside `develop_constraint_release` with its own
  competitor. That would be a different change from the one P8 proposed, and it would need its own reviewed change
  and re-admission.
- **Nothing is applied by this verdict.**
