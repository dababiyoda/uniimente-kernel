# P8 protected evolutionary cognition: first run, 2026-10-14

Code: `greg/cognition/evolution.py` (closed data-only genome schema, mutation, `ProtectedEvaluator`,
elitist search); evaluator `cortex/evaluation/evolution/evaluator.py`; runner
`cortex/evaluation/evolution/run.py`; freeze `freeze-v1.json` committed before the run (`b99daba`) pinning
the evaluator source, its data (P4 v2 training runs, P4 v3 held-out results and suite, the conditional
memory and the evolution module) and the settings (12 generations x 8, seed 20261007). Results:
`results.json`.

What may mutate: the conditional-competence routing genome only - `min_evidence`, `margin`, `shrink` and
the ordered feature list - validated against a closed schema. What may not: any key naming authority,
approval, consequence, credentials, budget, shutdown, scope, evaluator, evidence, acceptance threshold,
gate, constitution, founder or grant is refused as an unauthorized mutation attempt; the evaluator is a
separate process whose SHA-256 is re-checked before and after every call; its output is restricted to a
score contract.

| | dev correct / wrong / none (n = 64) | held-out correct / wrong / none (n = 130) |
|---|---|---|
| baseline genome (P4 v2/v3 settings) | 57 / 0 / 7 | 112 / 0 / 18 |
| champion after 12 generations | 57 / 0 / 7 (the baseline itself) | 112 / 0 / 18 |

97 candidates evaluated (84 tied the baseline on dev, 5 reached 55, 8 reached 49); none improved on it, so
the elitist search kept the baseline (ties keep the earlier, simpler genome). Held-out: 0 wins, 0 losses.
**Verdict (frozen rule): REJECT** - no candidate is retained; routing is unchanged.

Adversarial checks against the live machinery (all refused):
- a candidate carrying `approval_threshold` -> "unauthorized mutation attempt";
- a feature outside the frozen vocabulary -> refused;
- an evaluator edited after pinning -> `EVALUATOR_CHANGED`, the run stops.

## Reading

- The protection machinery works as specified; the search target has no exploitable headroom. That is
  consistent with P4 v3: the static policy is within timing noise of the best fixed order on this
  two-engine repertoire, so no routing genome can show a held-out gain here.
- P8's exit ("repeated held-out gains without evaluator gaming") is **not met**. The next honest P8 target
  needs a search space with real headroom (for example a multi-engine repertoire, or composition recipes
  scored on F-family development data) - not more generations on this one.
- Disclosure: before the freeze, the evaluator was smoke-run once on the held-out partition with the
  baseline genome (112/130) to validate its data paths. The settings had already been declared in the
  runner and did not change; the search itself used development scores only.
