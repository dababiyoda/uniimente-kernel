# P6 v2: cognitive composition lift on three more held-out families, 2026-10-14

Runner `cortex/evaluation/composition_lift/run_v2.py`; freeze `freeze-v2.json` committed before the held-out
run (`git log` shows the freeze commit precedes this result). Results: `results-v2.json`.

| Family | n | Routed: correct / wrong / no decision | Best constituent: correct / wrong / no decision | Wins / losses | p (one-sided) | Lift |
|---|---:|---|---|---|---:|---|
| F2b identify -> optimize (fresh seeds 25-72) | 48 | 43 / **3** / 2 | association optimiser: 35 / **13** / 0 | 11 / 3 | 0.029 | yes |
| X1 crossgeo `composition` (estimate + feasibility) | 48 | 48 / 0 / 0 | estimate only: 0 / 48 / 0 (formal only the same) | 48 / 0 | < 1e-14 | yes |
| X2 crossgeo `schedule_words` (words -> model -> solver) | 57 | 57 / 0 / 0 | formal only: 0 / 0 / 57; extraction only: 0 / 57 / 0 | 57 / 0 | < 1e-17 | yes |

Median latency: F2b routed 1.36 s (association 0.79 s); X1 0.23 s (estimate only 0.21 s); X2 0.03 s.

**VPL across all measured families (v1 + v2): 4 distinct families with lift** - F1 estimate -> optimise
(v1, p = 0.00012), F2/F2b identify -> optimise (v1 underpowered, p = 0.0625; v2 at n = 48, p = 0.029),
X1, X2. The v1 F2 result is kept as recorded.

## How strong this is

- **F2b is the substantive result**: composition cut wrong funding allocations from 13 to 3 of 48 at a
  pre-registered sample size; 3 routed failures (`F2b-37`, `F2b-59`, `F2b-62`) and 2 abstentions remain.
- **X1 and X2 are structural lift.** Each item asks for two answers (X1) or gives only words (X2); a single
  organ cannot produce the whole answer, so its partial "recommend" output is scored wrong by the suite's own
  gold. This shows GREG's routing assembles the right organs without error on independently written items;
  it does not show that composition beats a strong end-to-end single method.
- **Strongest single intelligence for X2 not run**: a language model reading the request could attempt the
  whole task alone; no founder-selected local model is configured here, so that baseline is NOT_RUN.
- **Not a natural task distribution**: X1/X2 were authored by the agent that built the router (for the
  cross-geometry evaluation, frozen in `freeze-crossgeo-v0.3.json`) before this module existed. Natural-task
  evidence needs founder-used missions (VEPMC = 0).

## P6 v3: a chain no recipe lists, derived by dataflow (2026-10-14)

Runner `cortex/evaluation/composition_lift/run_v3.py`; freeze `freeze-v3.json` committed before the run
(`b99daba`); results `results-v3.json`. Mechanism: `greg/cognition/composition.py` `derive()` - when no single
recipe fits, every `$param` root in the formal template must be produced by a stage whose input the payload
carries, so a template needing `estimate.low` and `effect.*` yields estimate + identify -> optimize, a chain in
no recipe list. Family F3 (48 held-out items, seeds 101-148): fund two confounded programs within a money
budget and within volunteer-hour capacity available with 95 % probability. wrong = commits hours above the
true 5th percentile; correct = within capacity and >= 0.95 x the true optimum; else suboptimal.

| Arm | correct | wrong | suboptimal | no decision | median s |
|---|---:|---:|---:|---:|---:|
| estimate alone | 0 | 0 | 0 | 48 | 0.52 |
| identify alone | 0 | 0 | 0 | 48 | 0.58 |
| optimiser on raw association at median capacity (best single) | 4 | **44** | 0 | 0 | 0.85 |
| fixed recipe estimate_then_optimize (association effects) | 43 | 0 | 5 | 0 | 1.38 |
| fixed recipe identify_then_optimize (median capacity) | 5 | **40** | 0 | 3 | 1.44 |
| **routed: derived estimate + identify -> optimize** | **45** | **0** | 0 | 3 | 1.98 |

**Verdicts (frozen):**
- vs the strongest single intelligence: **lift** (41 wins / 0 losses, p < 1e-12). F3 is the fifth distinct
  VPL family (F1, F2/F2b, X1, X2, F3).
- vs the best fixed recipe: **no lift** (4 wins / 2 losses, p = 0.34). The derived chain removed the fixed
  recipe's 5 suboptimal plans but abstained on 3 items where causal identification abstained
  (`STAGE_ABSTAINED`); the fixed recipe answered 2 of those correctly by trusting raw association.

Reading: dataflow derivation works (every routed item took the derived chain, zero wrong answers), and it
beats every single intelligence decisively; whether it beats the simpler fixed recipe is not shown on this
family, so `composition.derived` is NICHE_CAPABILITY in the genome library, not DEFAULT. F3 is constructed to
need both stages; it is not a natural task distribution.
