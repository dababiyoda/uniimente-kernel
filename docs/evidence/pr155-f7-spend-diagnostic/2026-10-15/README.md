# F7 spend at equal throughput: diagnostic (2026-10-15)

Produced by `python -m cortex.evaluation.pr155_f7_spend_diagnostic.probe` at commit `0f51b26` (clean tree).
It answers finding M11 of the independent review of PR #179.

**Scope.** These are F7 development items only: the 100 (network, demand pair) items on the development
partition of `run_v4.partition()`. No held-out item was read. This is a diagnostic, not a generalisation
claim, and it changes no frozen verdict.

**Question.** The frozen F7 scorer measures throughput only. When the `graph_then_allocate` composition (run on
GREG's path) and parametric min-cost flow (PMCF) reach the same throughput, does the composition lease capacity
it does not need? PMCF's min-cost flow at that volume is the cheapest plan for it, so any excess spend carries
no extra flow.

**Result** (`results.json`):

| measure | value |
|---|---|
| items | 100 |
| equal throughput | 100 |
| composition spends more than PMCF | 46 |
| PMCF spends more | 0 |
| identical plans | 44 |
| mean excess, where the composition spends more | 7.6% of budget |
| maximum excess | 55.8% of budget |

At equal throughput the exact method weakly dominates the composition. The review measured a different idle-spend
definition on 50 items (17/50, mean 2.8%, max 23.9%). The direction agrees; the magnitudes differ by
definition and item set.

**Next.** Admission v3 of `flow_expansion_mcf` and any F7 re-measurement should pre-register spend at equal
throughput as a declared secondary measure. The data-rights status of the SNDlib extract that this probe reads
is set out in section 12 of the reconciliation record.
