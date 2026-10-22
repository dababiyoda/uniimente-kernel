# Shadow versus static routing, v0.1 (P4 exit test)

`freeze.json` was committed (270a0c5) before `results.json` was produced. Reproduce:

```
python -m greg.cognition.routing_eval run      # refuses a suite that differs from freeze.json
```

**Verdict: NO_GAIN.** 60 held-out schedules (35 optimization, 25 feasibility), exact brute-force truth.

| | mean loss |
| --- | --- |
| fixed policy | 0.0959 |
| learned (competence ledger trained on 30 development problems, both engines) | 0.0959 |
| hindsight best single engine | 0.0511 |

Both engines answered every held-out problem correctly, so every ledger cell estimated 0.9909 on 9
weighted outcomes and the learned order never differed from the fixed one. No hard failures.

**Diagnosis.**

1. The ledger learns from success and failure only. It cannot see that Z3 was faster than CP-SAT on all
   60 held-out problems (median 0.25 s against 0.65 s), so equal correctness can never move a default.
2. The hindsight headroom is partly illusory. Only the fixed CP-SAT-first optimization route carries a
   second, independent optimality certificate (Z3 re-proves CP-SAT's optimum). Either engine pinned
   alone returns none. The loss above prices latency but not that fault diversity.

**Decision: no cost-aware rule now.** Putting Z3 first on optimization would buy about 0.36 s per problem by
giving up the cross-engine certificate: a gain in the declared loss and a loss in proof. The next bounded
test must price the certificate in the loss (declared before running) and measure whether a Z3-first
route can still obtain a CP-SAT certificate. Until then the fixed policy stays.

Limits: one run in a container; latency varies with load; synthetic schedules only.
