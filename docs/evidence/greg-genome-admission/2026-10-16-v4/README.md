# Genome admission v4 (2026-10-16): grid_dijkstra 1.1.0 is DEFAULT_FOR_GEOMETRY

Generated from `results.json` by script. Nothing was re-run.

- **Pre-registration:** `PREREGISTRATION.md` (committed at `483a3cf`), with `freeze.json` committed at `3da09c0` before any held-out instance was generated.
- **Run:** once, at `3da09c0`, in a clean detached worktree, pinned to one core; exit 0 (`run.log`).
- **Seeds:** held-out 1300-1329.
- **Host load:** start {'1m': 0.12, '5m': 0.39, '15m': 1.0, 'runnable': 1, 'entities': 106}, end {'1m': 0.19, '5m': 0.4, '15m': 1.0, 'runnable': 1, 'entities': 106} (diagnostic only).

| Family | Version | Status | Candidate correct/wrong/abstain | vs baseline W-L-T | vs competitor W-L-T | Median s (candidate / baseline / competitor) | Baseline/candidate (wall) | Baseline/candidate (CPU, diagnostic) |
|---|---|---|---|---|---|---|---|---|
| `flow_capacity_plan` | 1.0.3 | **COMPOSITION_ONLY** | 30/0/0 | 30-0-0 | 30-0-0 | 0.000101 / 0.000001 / 0.000000 | 0.01x | 0.03x |
| `flow_reinforce_greedy` | 1.0.2 | **SUPERSEDED** | 20/10/0 | 30-0-0 | 0-10-20 | 0.001211 / 0.000047 / 0.004493 | 0.04x | 0.04x |
| `grid_dijkstra` | 1.1.0 | **DEFAULT_FOR_GEOMETRY** | 30/0/0 | 0-0-30 | 0-0-30 | 0.000839 / 0.002178 / 0.009821 | 2.60x | 2.55x |

## Reading

- **The grid shortest-path geometry now has an admitted genome.** `grid_dijkstra` 1.1.0 ties both arms on quality, and its latency clears the rule's 1.25x against the A* baseline. The prediction was DEFAULT, near 1.9-2.4x.
- **The flow genomes replicate v3** at their new versions: `flow_reinforce_greedy` is SUPERSEDED and `flow_capacity_plan` is COMPOSITION_ONLY. The parallel-edge refusal changed nothing on the admission generators' inputs, as predicted.
- **Nothing is attached;** attaching is the founder's decision.
- **The evidence index** is rebuilt from this file in the same commit.
