# `graph_node_cut_exact`: the exact minimum S-T vertex cut genome (DEVELOPMENT ONLY)

**Label: DEVELOPMENT ONLY.** These are exploratory measurements on the genome's own development seeds 0-9 and on the
natops-2026-10-21 development part (545 instances, already published). They are not confirmatory, not admission,
and not external validation. No admission held-out seed was generated, and no natops held-out instance was scored or
read; the natops evaluation was not re-run. The genome is registered and withheld (VERIFIED), and it is not attached.

- Code: `greg/cognition/genomes/node_cut.py`. Benchmark world: `greg/cognition/worlds.py`. Tests:
  `tests/unit/test_graph_node_cut_genome.py`.
- Measurement script: `scripts/node_cut_development.py`, run once under `taskset -c 1`. It wrote `latency.json`,
  `development.json` and `overhead.json`. `admission-dev-seeds.json` is the admission harness's own `--dev` output.
- Admission v5 draft entry: `docs/evidence/greg-genome-admission/2026-10-21-v5-draft-nodecut.md` (not frozen).

## The deficit it closes

natops-2026-10-21 (`docs/evidence/greg-natural-ops-2026-10-21/README.md`) asked for minimum S-T vertex cuts over
GREG's own import graph.

- GREG could answer only by hand-translating each instance into a node-split network for `flow_maxflow`. That
  genome's 120-node / 400-edge bounds made it abstain on 25 of the 1,427 held-out items.
- `networkx.minimum_node_cut` in process was exact on all 1,427.

The new genome takes the question in its native form, `{edges: [[u, v]], source, target}`. It answers it exactly
and returns a certificate that a separate verifier checks without trusting the engine.

## Genome and verifier

- **Solve:** NetworkX `minimum_st_node_cut` and `node_disjoint_paths`. Both use one shared auxiliary node-split network
  and one shared residual network. It returns `{cut, k}` and a certificate of k S-T paths.
  - It answers `UNKNOWN` if the engine's cut and path packing differ in size.
  - It abstains on a direct S->T edge, where no vertex cut exists.
  - It also abstains when the certificate would exceed receipt retention (1,000 items per list).
- **Verify:** `node_cut_verify` uses no NetworkX and shares nothing with solve.
  1. **Separation:** removing the cut leaves T unreachable from S, checked by its own BFS.
  2. **Minimality (Menger):** the certificate holds exactly k paths. Each must start at S, end at T, use input edges
     only, repeat no vertex and have an intermediate vertex. Their interiors must be pairwise disjoint. Any separating
     set takes a distinct vertex from each path, so none has fewer than k vertices.
  3. **Well-formedness:** `k == len(cut)`, the vertices are distinct and all are intermediate vertices of the graph.
- **Input limits from measured latency** (`latency.json`): 10,000 vertices and 10,000 edges. These were not copied
  from `flow_maxflow`.
  - **Probes:** graphs built to be slow for augmenting paths (dense, layered with k up to 99, long sparse, and the
    native dependency shape) at edge caps of 1,250, 2,500, 5,000 and 10,000.
  - **Result:** on one pinned core, the slowest solve plus verify took 0.35 CPU s at 10,000 edges (0.35 s wall at
    load about 2). That is under the 0.5 s target, which is a quarter of the worker's share of the default budget.
  - **Load sensitivity:** an earlier probe at load about 4 measured 0.84 s wall on `layered 70 wide x 3`. That is
    why the rule uses CPU time and records wall time beside it.
  - **What binds instead:** latency never bound below 10,000 edges, which is the cognition path's own input-list
    limit. Through `cortex.reason`, the 64 KiB request limit binds first, at about 1,000-1,300 edges for natural
    module names. The largest natops development item has 219 edges.

### Mutation tests (all refuted; `tests/unit/test_graph_node_cut_genome.py`)

| Corruption | Check that fails |
|---|---|
| cut too large (`k + 1` vertices, same k paths) | `certificate_has_k_paths` |
| ...padded with a (k+1)-th path that shares an interior vertex | `path_interiors_pairwise_disjoint` |
| ...padded with a path on a non-existent edge | `every_path_runs_s_to_t_on_input_edges` |
| cut that does not disconnect | `cut_separates_s_from_t` |
| wrong k (1, 3, 0, -1, `True`, `2.0`) | `output_well_formed` |
| overlapping paths (one path twice; two paths sharing a vertex) | `path_interiors_pairwise_disjoint` |
| non-simple path, truncated path, reversed path | `every_path_is_simple` / `..._on_input_edges` |
| missing certificate, certificate not a list | `certificate_well_formed` |
| malformed output (None, list, string, duplicate vertices, non-string vertex, missing k, extra key) | `output_well_formed` |
| S or an unknown vertex in the cut | `cut_vertices_are_intermediate` |
| sweep on dev seeds 0-9 (3 output mutants + 4 certificate mutants each, 70 total) | 0 survive |

A forged answer through `library.check` (the verifier as `cortex.reason` runs it) is also refuted.

## Development results

### natops development part (545 instances, already exposed; truth = natops Menger + HiGHS ILP)

| Arm | Path | Correct | Wrong | Abstain | Median s | p90 s |
|---|---|---:|---:|---:|---:|---:|
| `graph_node_cut_exact` (solve + verify) | in process | **545** | 0 | 0 | 0.0020 | 0.0032 |
| `graph_node_cut_exact` | `cortex.reason` | **545** | 0 | 0 | 0.342 | 0.713 |
| Competency Compiler (`{edges, source, target}`) | `cortex.reason` | **545** (selected the genome on every item) | 0 | 0 | 0.348 | 0.711 |
| `flow_maxflow` 1.0.1 (node-split) | `cortex.reason` | 535 | 0 | 10 (all beyond its bounds) | 0.344 | 0.721 |
| `flow_maxflow` 1.0.1 (node-split) | in process | 535 | 0 | 10 | 0.0053 | 0.0101 |
| ILP (`scipy.optimize.milp`, HiGHS) | in process | 545 | 0 | 0 | 0.0184 | 0.0344 |
| practitioner `networkx.minimum_node_cut` | in process | 545 | 0 | 0 | 0.0012 | 0.0017 |
| betweenness greedy (baseline) | in process | 496 | 49 | 0 | 0.0004 | 0.0008 |
| degree greedy | in process | 395 | 150 | 0 | 0.0002 | 0.0004 |

- **By subregion:** 535 of 545 fit inside `flow_maxflow`'s bounds. There the genome and `flow_maxflow` tie on every
  item. The genome's whole correctness edge is the 10 items beyond those bounds, where `flow_maxflow` abstains. This
  is bounds coverage, not better reasoning.
- **Latency:** through `reason` the two cost the same, about 0.34 s each. In process, the genome's solve plus verify
  (2.0 ms) is faster than `flow_maxflow`'s solve alone on the translation (5.3 ms). The practitioner call (1.2 ms,
  no certificate) is faster still.

### Genome dev seeds 0-9 (own generator)

- **Correctness:** the candidate, the ILP, the practitioner, the genome through `reason` and the compiler were
  correct on 10 of 10. `flow_maxflow` was correct on 8: it abstained on the 2 seeds beyond its bounds, both in
  process and through `reason`. Betweenness greedy was correct on 8 (2 wrong); degree greedy on 6 (4 wrong).
- **The admission harness's `--dev` mode** (`admission-dev-seeds.json`) reports "EXPERIMENTAL if held-out matched".
  - The candidate beats the baseline 2-0 (p = 0.25) and the competitor 2-0 (p = 0.25). Ten seeds cannot reach
    alpha 0.05.
  - Median wall time: candidate 1.0 ms, competitor 2.7 ms, baseline 0.25 ms. Median CPU time: 0.98, 0.88 and
    0.25 ms.
  - That is a statement about n = 10, not a prediction for v5.

## Where the ~0.35 s per `cortex.reason` call goes (`overhead.json`, quiet host, load about 0.5-2)

| Phase (median, dev seeds 0-9) | `graph_node_cut_exact` | `flow_maxflow` |
|---|---:|---:|
| whole `reason` call | 0.350 s | 0.355 s |
| solver worker process (spawn + seccomp + imports + solve) | 0.230 s | 0.224 s |
| independent verifier process (spawn + imports + verify) | 0.117 s | 0.111 s |
| parent (routing, receipt) | 0.003 s | 0.003 s |
| the actual solve + verify, in process | 0.0016 s | 0.0025 s |

- **Interpreter start:** about 0.024 s for `python -I -c pass` under the seccomp network filter.
- **Solver worker imports:** about 164 ms in all, measured with `-X importtime` on the real worker.
  - NetworkX: 87 ms.
  - `greg`: 59 ms. `greg.cognition.solvers` loads the whole catalog, and `library.catalog_families()` imports every
    genome module.
  - JSON, pathlib and the rest: about 15 ms.
- **Verifier imports:** the verifier pays the `greg` imports but not NetworkX; this genome's verifier never imports
  it.
- **Compute:** under 1% of the call.

Isolation and verification were not weakened, and no code on the `reason` path was changed.

### Proposal (written only; no existing reviewed mechanism supports any of these on the path)

1. **Warm forked workers inside the existing isolation contract (largest saving).**
   - **Mechanism:** one solver zygote and one verifier zygote, separate so the verifier stays independent. Each
     starts like today's worker: scrubbed environment, seccomp network filter, the same imports, single-threaded
     with the BLAS thread variables set before import. Each forks one fresh child per request. The child applies
     the per-request CPU and memory limits, runs one request, emits and exits. A zygote never runs a request, so no
     request state can carry over.
   - **Measured prototype** (outside the path, with no seccomp and no rlimits): 7 ms per request against about
     230 ms. That would take a `reason` call from about 0.35 s to about 0.02 s plus the verify child.
   - **Preconditions:**
     - P8's integrity freeze checks the code each process executes. A zygote must be started from the clean room,
       carry the code digests, and be restarted whenever any frozen file changes.
     - Python warns about fork in a multithreaded parent, as the prototype's parent was (it had imported
       SciPy/NumPy). The zygote must stay single-threaded until it forks.
     - Lifecycle, crash and shutdown semantics need their own review.
     - This changes the worker contract, so it needs an independent review and its own frozen evaluation.
2. **Import only the requested family in the worker.**
   - `solvers.py` and `catalog.py` import every genome module on every call through `library.catalog_families()`.
   - A worker that resolves one family lazily would save part of the 59 ms of `greg` imports, in both processes.
   - The saving is small (an estimated 0.05-0.1 s per call) and needs no new mechanism. But `worker.py`,
     `solvers.py`, `catalog.py` and `library.py` are in several evaluation freezes, so it must land as its own
     reviewed change.
3. **A batched request.** Many (S, T) pairs over one graph in one `reason` call would spread the fixed ~0.35 s cost
   over every pair. natops had 1,427 items from 12 commits. This needs a new operation contract (`min_vertex_cuts`,
   a list of pairs, one certificate per pair) and its own genome version and admission.

**Not proposed:** skipping the worker or the independent verifier for consequence-inert requests. That would weaken
isolation and verification, which this lane was told not to do. Through the existing `reason` path, the practitioner
call's 263x latency advantage stays.

## Limits

- **Small dev samples:** dev seeds 0-9 are only 10 instances, and the generator was designed after the deficit was
  known (disclosed in the v5 draft).
- **Correlated natops items:** the natops development part is natural but correlated, as the natops README notes.
  It was used for every development decision.
- **Shared host:** timing is from a shared 4-core host pinned to one core. Ratios are more reliable than absolute
  values.
- **Graph model:** the genome answers over the supplied graph only. An import graph is a model of runtime dependency.
