# Pre-registration: natops-2026-10-21, dependency control points in GREG's own repository

Status: committed BEFORE the freeze manifest and BEFORE any held-out instance is scored. Evidence label for
everything this run produces: **NATURAL repository data** (this repository's own import graphs, read from git
history), **consequence-inert** (reads committed blobs, executes none of them, contacts nothing), **exact
mathematical truth**, **not external validation**.

Directive: `docs/intent/sources/MIND-MAXIMUM-CONTINUATION-2026-10-21-source.md` section 6 ("Demand genuine cognitive
advantage over the strongest competitor"; dependency analysis as an operating need). Coverage plan:
`docs/collaboration/MIND-COVERAGE-2026-10-21.md`, build list items 4 and 5; this run is item 5 (B05).

## Why this family (not evidence-claim reconciliation, item 4)

Both are natural. Item 5 was chosen for evaluability: its truth is computed exactly and independently of every arm,
and an admitted genome (`flow_maxflow`, DEFAULT_FOR_GEOMETRY at 1.0.1) and the Competency Compiler both have a
genuine fit through `cortex.reason`. For item 4, truth requires mapping each README sentence to a JSON field; that
mapping is the method under test, so an independent truth would need hand labels, no admitted genome fits, and no
local model exists for the semantic organ. Item 4 stays open.

## Question

For an instance (commit, entry module S, module T) of the repository-internal Python import graph: return a
minimum set of intermediate modules whose removal leaves no import path from S to T (a minimum S-T vertex cut,
"control points"; size 1 = a single point of failure).

## Instance selection rule (code: `cortex/evaluation/natural_ops/extract.py`)

- Base commit `9a6b3330ef5bcfbd617d9a50b183077238204750`; every 12th first-parent commit from the base, at most 22.
- Nodes: tracked `*.py` outside `tests/`; edges: every resolved repository-internal import anywhere in the file
  (lazy imports included); parent-package `__init__` execution is not modelled.
- Sources: `greg.cli`, `greg.missions`, `greg.body`, `greg.gravity`, `greg.remote`, `greg.console` (when present).
- Targets: every module reachable from S, not S, not imported by S directly. `target_class` marks organ/evidence
  targets (top-level `adapters`, `organs`, `provenance`, `events`, `loom`, `embassy`, or the GREG organ bridges and
  evidence writers listed in the extractor) for a secondary slice.
- Input: the relevant subgraph (descendants of S that are ancestors of T). Deduplicated across commits by
  (S, T, subgraph digest); the commit nearest the base keeps it.
- Pool at the base: 1,972 instances. Aggregate size statistics of the pool (node counts, how many fit the genome's
  declared bounds) were looked at before the split to choose the sources; no truth or arm output was.

## Split

`development` iff `int(instance_id, 16) % 10 < 3` (545 instances), else `heldout` (1,427). The id is a hash of
(S, T, subgraph digest). Development was used to (a) check the arms run, (b) choose the composition's first stage.
Held-out instances are scored once, by the confirmatory run below.

## Truth (code: `truth.py`, imports nothing from any arm, no NetworkX)

Menger: unit-capacity augmenting paths on the node-split graph, certificate cut checked by separation; and an
integer program by HiGHS (`scipy.optimize.milp`, gap 0). Both must agree; a disagreement is reported as
TRUTH_DISAGREEMENT and the instance is excluded from scoring (count reported). Scoring: CORRECT iff the arm's cut is
a set of intermediate modules of the instance, separates S from T, and has size k; any other returned cut is WRONG
(a false answer); no cut is ABSTAIN. A receipt the independent verifier REFUTED is WRONG.

## Arms (code: `arms.py`)

| Arm | Path | Role |
|---|---|---|
| `degree_greedy` | in process, **bypasses `reason`** | simple baseline (degree rank, delete until separated, prune) |
| `betweenness_greedy` | in process, **bypasses `reason`** | simple baseline (S-T betweenness rank); the stronger baseline on development (496 vs 395 of 545) |
| `flow_maxflow` | `cortex.reason`, operation `max_flow`, node-split translation | best single admitted genome |
| `composition` | stage 1 `betweenness_greedy` in process (**bypasses `reason`**); stage 2 `flow_maxflow` through `reason` | stage 1 is accepted only when its cut has one module (k >= 1 because direct edges are excluded, so a separating single module is optimal) |
| `compiled` | `cortex.reason({"compile": ...})`, read-only geometry | GREG's own routing; the selected method is recorded |
| `practitioner` | `networkx.minimum_node_cut`, in process, **bypasses `reason`** | what an engineer would call |

The first development run (`development-v1-degree-stage1.json`) used `degree_greedy` as the composition's first
stage; on development `betweenness_greedy` was stronger, so the composition and the constituent set were changed to
it before this pre-registration. `development.json` is the re-run with the frozen arms.

Reported for every arm: correct, wrong (false answers), abstentions split into out-of-genome-bounds (justified by a
declared limit) and in-bounds (unjustified), translation failures (input bounds, request rejected, output not
mappable), refutations, arm exceptions, median and p90 wall latency, total CPU seconds (self + children), money
(0), worker subprocesses, Wilson 95% intervals on correct rates. Latencies of in-process arms are not comparable
with `reason` arms' (isolated worker + independent verifier, two subprocesses per call); both are reported.

## Decision rule (primary, one hypothesis)

Constituents of the composition: `betweenness_greedy`, `flow_maxflow`. The best single constituent is the one with
the most CORRECT on held-out (ties: fewer WRONG, then lower median latency). Paired on held-out items:

- **REGRESSION** if the composition is worse (one-sided exact sign test on items where exactly one is CORRECT,
  p < 0.05) or has more WRONG than the best constituent;
- **LIFT** (counts toward VPL) if the composition is better (sign test p < 0.05), has no more WRONG, and its median
  latency is at most 1.25x the constituent's;
- **EFFICIENCY_ONLY** (does not count toward VPL) if not significantly better, no more WRONG, median latency ratio
  at most 1/1.25 and the paired latency sign test p < 0.05;
- otherwise **NO_LIFT**.

This is `run.decide`. Latency ratio intervals: paired percentile bootstrap, 2,000 resamples, seed 20261021.

## Multiple testing

One primary test at alpha 0.05. Secondary comparisons (`composition` vs `practitioner`, `flow_maxflow` vs
`practitioner`, `degree_greedy` vs `flow_maxflow`, `compiled` vs `flow_maxflow`, `betweenness_greedy` vs
`degree_greedy`, `betweenness_greedy` vs `flow_maxflow`; both directions) are Holm-adjusted as one family and are
descriptive. Programme-wide, this is one more VPL family among those already run (P6 v1-v6); a single LIFT here is
not evidence of general superiority and is not admission or adoption. Items are correlated (the same modules recur
across sources and commits); the sign test treats items as independent, so p-values are optimistic. The number of
distinct commits contributing items is reported.

## Pre-declared interpretations

- If `practitioner` or `flow_maxflow` decides every in-bounds item correctly and the composition's only gains are on
  items beyond the genome's size bounds, the result says the genome's bound, not cognition, decides the comparison,
  and the proposed routing for this geometry is the exact method (in process where the call is consequence-inert).
- Directive item 5 falsifier: "the degree heuristic matches the exact cut on most instances" is evaluated on
  held-out and reported as met or not.

## Freeze and run commands (exact)

```
taskset -c 1 python -I cortex/evaluation/natural_ops/run.py --freeze      # writes freeze.json; scores nothing
git add docs/evidence/greg-natural-ops-2026-10-21/freeze.json && git commit   # the freeze commit
git status --porcelain --untracked-files=no                                 # must be empty
taskset -c 1 python -I cortex/evaluation/natural_ops/run.py --heldout     # once; refuses unless the freeze holds
```

`freeze.json` holds the held-out ids with their subgraph digests, the pool digest, sha256 of every file in
`run.FROZEN_FILES` (the family's code, the canonical cognition path it calls, the genome, the evidence index and
this file), the Python / NetworkX / SciPy / NumPy versions and the decision constants. `--heldout` refuses (before
reading any held-out instance's truth or arm output) if any of these differ, the tree is dirty, or the freeze is not
committed; it re-checks the inputs after the look. The run writes `results.json` and `run.log`; `README.md` reports
them, negative results included.
