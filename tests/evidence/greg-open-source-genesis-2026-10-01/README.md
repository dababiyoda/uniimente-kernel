# Open-source engines on GREG's genesis path — evidence, 2026-10-01

Founder correction (comment on #143, draft #144): open-source mechanisms are construction supply.
This directory holds what was run in the tested environment (Linux container, Python 3.11.15,
NetworkX 3.6.1, SciPy 1.17.1, NumPy 2.4.6, OR-Tools 9.15.6755). GREG installed nothing; the packages were already
present from `requirements-cognition.txt`.

| File | What it shows | Reproduce |
| --- | --- | --- |
| `qualification.json` | Mechanism Card and qualification report for each engine and function: frozen cases (GREG's Bellman-Ford, brute-force minimum cut, or vertex enumeration in exact fractions), GREG's certificate on each, and a scale probe against the simplest local implementation where one exists | `python scripts/qualify_open_source_engines.py tests/evidence/greg-open-source-genesis-2026-10-01` |
| `mutants.log` | Every safeguard removed one at a time; the tests must fail for each | `python scripts/ci/check_cortex_mutants.py` |

## Results

- 6 of 6 engine/function pairs qualified with 0 failures: NetworkX and SciPy for `graph.shortest_path`
  and `graph.max_flow`; SciPy HiGHS and OR-Tools GLOP for `lp.optimize` (500-variable probe certified
  by duality).
- A mission closed on a capability absent at its start: words, deficit, card, founder attach,
  certified answer, VERIFIED appraisal (`tests/unit/test_greg_open_source_genesis.py`).
- A lying engine was caught by the certificate, quarantined, not re-admitted, and replaced by the
  other package; no lie was accepted.

## Negative evidence

- **Reuse was not a speed win.** On the scale probes a plain-Python Dijkstra and Edmonds-Karp matched
  or beat the packages' solve time, and each isolated call also spends ~0.25 s starting an
  interpreter. The route's value is that GREG wrote no engine and trusts only its own certificate.
- **The oracle caught GREG's first NetworkX runner.** NetworkX lists every tied predecessor; across a
  zero-weight self-loop the source becomes its own predecessor. The runner now drops
  self-predecessors; a test pins the original defect.
- **A sparse matrix sums parallel edges.** The SciPy runner keeps the lightest; a mutant test shows
  the oracle refutes a runner that lets the matrix sum them.
- **#140's graph op dropped a cheaper parallel road** (NetworkX `add_edge` overwrote it), and its
  verifier checked path form but not optimality. Both fixed; the verifier now refutes a longer
  route and a false "no route" with GREG's own Dijkstra.
- **Unpinned files.** The card pins RECORD, the mechanism's files and shared dependencies' RECORD.
  A change to another file of the distribution without a RECORD change is not detected.
- **License from metadata**, not a legal review; the founder sees it before attaching.
- **"Infeasible" and "unbounded" are not proved.** Neither LP interface returns a Farkas certificate,
  so GREG reports the engine's claim and never closes a mission on it.
- **Shadow-price sign.** The first certificate reported prices with the wrong sign for maximization;
  a test caught it, and prices are now the change in the stated objective per unit of the stated
  limit (pinned for both `<=` and `>=` rows, both engines).
