# Open-source genesis qualification — 2026-10-13

Reproduce: `python scripts/qualify_open_source_engines.py tests/evidence/greg-open-source-genesis-2026-10-13`
(seed 20261001). Every installed candidate in Capability Genesis's catalog ran in a no-network interpreter
against GREG's frozen oracle and a scale probe; each answer was accepted only on GREG's own certificate.

New since 2026-10-01:

| Function | Engines | GREG's certificate | Oracle |
| --- | --- | --- | --- |
| `assignment.optimize` | SciPy `linear_sum_assignment`, OR-Tools `SimpleLinearSumAssignment` | no negative cycle in the residual graph (exact integers); "no full assignment" proved by Hall's condition | brute force over every assignment |
| `flow.min_cost` | NetworkX network simplex, OR-Tools `SimpleMinCostFlow` | capacities, balances and no negative residual cycle (exact integers); "no plan" proved by Gale's condition | brute force over every whole-number flow |
| `graph.spanning_tree` | NetworkX Kruskal, SciPy csgraph | cycle property via binary lifting (exact fractions) | brute force over every edge subset |

Result: 12 of 12 engine/function pairs QUALIFIED (`qualification.json`).

Negative evidence kept: on the graph probes the plain local implementations (Dijkstra, Edmonds-Karp,
Kruskal) still match or beat the packages; on the 120 x 120 assignment probe and the 300-site delivery probe the packages are 3-8x faster
than plain-Python Hungarian and successive-shortest-path implementations. Two runner defects were designed out before qualification: OR-Tools'
simple assignment needs a perfect matching (GREG pads free columns with zero-cost rows), and SciPy's
csgraph reads a zero weight as "no edge" (GREG shifts every weight by one constant; a tree's edge count is
fixed, so the optimum is unchanged).
