# PR #155 lineage: Dawid-Skene vs the one-step weighted vote on sparse multi-class crowds, 2026-10-14

Runner `cortex/evaluation/pr155_crowd_sparse/run.py` (lineage-unique path, founder decision a832c73); freeze
`freeze-v1.json` committed and pushed before the run (`85ce275`); results `results.json` (every seed kept).
Seeds 3001-3040; 100-200 items, 4-6 classes, 8-15 observers each covering U(.10, .30) of items; experts,
average observers, systematic confusers (c -> c+1 with probability .6) and spammers.

| Arm | mean item error |
|---|---:|
| Dawid-Skene (candidate, shipped settings) | 0.417 |
| majority vote (baseline) | 0.394 |
| **one-step agreement-weighted vote (competitor)** | **0.338** |
| oracle Bayes posterior with true confusion matrices (reference, not deployable) | 0.197 |

Dawid-Skene vs majority 17/22 (p = 0.83); vs one-step 8/32 (**the one-step vote is better, p = 9.1e-5**);
the oracle beats it on 40/40. Frozen status (v1 rule): **EXPERIMENTAL**. Earns its complexity over the
one-step vote: **no**.

## Reading

- With sparse data each observer contributes 10-60 labels while Dawid-Skene estimates a k x k confusion
  matrix per observer (16-36 cells, Laplace pseudo-count 1 each); the smoothing pulls every observer toward
  uniform and the model loses even the information the one-step vote keeps. Admission v2 (dense crowds)
  already showed a tie with the one-step vote. Across both geometries the simpler method is at least as good
  and here decisively better.
- Disposition: `cognition.crowd` is not recommended for attachment as a default; the one-step agreement-
  weighted vote (a few lines, no iteration) is the acquisition target for collective labelling and must be
  admitted against majority and Dawid-Skene before use. The oracle's 0.197 shows how much headroom remains for
  a method that can learn structured confusion from sparse data (for example a hierarchical prior shared
  across observers); not built.
- This supersedes the attach recommendation made earlier on 2026-10-14 in the PR #155 status report.
