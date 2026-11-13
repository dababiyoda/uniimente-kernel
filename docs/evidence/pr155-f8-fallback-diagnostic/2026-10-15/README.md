# F8 fallback diagnostic, 2026-10-15 (diagnostic on exposed data, not a claim)

**Question.** F8 (#158, frozen at `202b932`) met its pre-registered rule against the best constituent. Its total
modelled cost was still 4.7% above the simpler EWMA-quantile ablation. Would a stronger fallback close that gap?

**Method.** `cortex/evaluation/pr155_f8_fallback_diagnostic/diagnose.py` recombines F8's frozen per-item rows.
It runs nothing new and leaves F8's files unchanged; the source digest is in `results.json`.

| arm | total modelled cost | vs ablation | coverage without fallback | p95 / p99 / max excess over hindsight |
|---|---:|---:|---:|---|
| unchanged (standing-plan fallback) | 656,324 | +4.7% | 90.8% | 233 / 537 / 14,529 |
| simpler ablation (EWMA ratio + quantile) | 626,736 | 0 | 100% | 324 / 568 / 1,508 |
| proposed (EWMA-quantile when the tracker abstains) | 608,686 | -2.9% | 100% | 249 / 518 / 2,088 |

Fallback reasons for the 203 abstentions, inferred from stages run (the frozen run recorded
`STAGE_ABSTAINED`, not the reason):
- 118 had too few usable measurements (no stage ran);
- 85 were the tracker's own refusals (one stage ran).

**What this does not show.**
- The proposed fallback was suggested by these same held-out rows, so its 2.9% is biased in its favour.
- Its worst single item is worse than the ablation's (2,088 against 1,508).
- Latency is not comparable: the ablation runs in process.
- These are modelled costs on 2015 demand under F8's declared staffing model, not realised savings.

**Next.** One owner adopts `prereg-draft.json` and freezes it under a new path. Every abstention records an
explicit reason. The run uses fresh held-out data, once its terms are read (record section 12). The report
says plainly if the simpler ablation wins.
