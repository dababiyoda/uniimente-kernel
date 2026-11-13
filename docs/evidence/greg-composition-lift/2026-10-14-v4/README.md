# P6 v4 composition lift: a natural graph-allocation family on real backbones, 2026-10-14

- **Runner:** `cortex/evaluation/composition_lift/run_v4.py`.
- **Pre-registration:** `cortex/evaluation/composition_lift/prereg-v4.json`, committed in `888003c` before the held-out partition was generated. It passes `vpl_metrics.validate_preregistration`, so it is the first P6 family pre-registered with all of the following: a static arm that must decide, a compiled arm, practitioner pipelines and a latency rule.
- **Suite:** `cortex/evaluation/composition_lift/suite-v4.json` (`dbc0643`): 50 development items on 5 networks and 200 held-out items on 20 networks. No item was out of scope.
- **Freeze:** `cortex/evaluation/composition_lift/freeze-v4.json`, committed in `14ec7a6` before any held-out arm ran. It hashes 114 files: the import closure of the runner and the isolated worker (all of `greg/cognition`, `vpl_metrics.py`, the flow genomes and the sandbox filter), the suite, the pre-registration, the SNDlib data and its build script, plus the requirement pins and dependency versions.
- **Run:** once, in a clean worktree at `14ec7a6`, with two processes each pinned to its own core (`--workers 2 --cores 0,1`). Each item runs whole on one process. `run.log` is the console output (exit 0).
- **Path:** every GREG arm runs through `greg.cognition.cortex.reason`, with isolated workers and an independent verifier per stage. Four families are attached in an evaluation-only registry view: `flow_maxflow`, `flow_capacity_plan`, `flow_reinforce_greedy` and `optimization`. On the body they stay as they are.
- **`development-v4.json`:** the builder-only development run at `dbc0643`. It is not part of any verdict; `greg/cognition` and `run_v4.py` are byte-identical to the freeze.

## Why F7

The two earlier natural families were both "forecast, then decide": F5 (M4 demand -> newsvendor) did not lift, and F6 (bank arrivals -> Erlang C) did. The graph-allocation recipe `graph_then_allocate` had lifted only on generated networks (F3, 11-0). F7 asks whether that lift survives real topologies.

## Data and provenance

- **Source:** the SNDlib 1.0 networks (Orlowski, Wessaely, Pioro, Tomaszewski, *Networks* 55:276-286, 2010), as bundled by TopoHub 1.5.1 (PyPI wheel sha256 `331dd0da...cdbb`). The bundle holds the real nodes, links with haversine length, the real demand matrix, and every link's directional load under ECMP shortest-path routing of that demand.
- **Committed extract:** `cortex/evaluation/data/sndlib_networks.json.gz` (sha256 `f9b1d3d4...fc47`, `9434224`). It holds 25 networks of at most 120 nodes, the 20 largest demand pairs each, and both link loads. `build_sndlib_networks.py` rebuilds it byte for byte from the wheel and refuses any other digest.
- **Terms (founder-reviewable item):**
  - The TopoHub conversion is MIT.
  - SNDlib publishes no open licence. Its site says the data is meant for research use, and it asks for the citation above.
  - Here the data is used for evaluation only; redistributing it beyond research is Alfonso's decision.
  - The SNDlib page could not be fetched from this environment; the terms are taken from a search summary of its privacy and data-use page.

## Design, frozen before any held-out arm ran

- **Item:** one real (network, demand pair), the pair's demand surging. Lease extra capacity within a budget to maximise the surge's s -> t throughput.
- **Declared planning layer** (not SNDlib's own capacities or costs, which TopoHub does not carry):
  - **Free capacity:** modules of 10 units at no more than 80% utilisation; free capacity per direction is the module headroom over the real ECMP load.
  - **Admissible paths:** the 4 shortest loop-free paths by length.
  - **Lease price:** 1 + round(km / 100) per unit.
  - **Arc limit:** at most 20 units per arc.
  - **Budget:** 20 times the price of the cheapest admissible path.
- **Truth:** the exact optimum by parametric min-cost flow (NetworkX network simplex with bisection). That algorithm is different from the composition's CP-SAT.
- **What is natural:** the instances (topology, lengths, demand pairs, loads). **What is not:** the outcome. The truth is the exact optimum of a declared problem, so F7 tests optimisation quality on real structure, not prediction against reality as F5 and F6 do.
- **Arms:**
  - **Constituents:** graph intelligence alone (`reinforce_min_cut`) and the optimiser alone on a flow-blind model, as in F3.
  - **GREG compositions:** static and routed composition `graph_then_allocate`, plus the Competency Compiler arm.
  - **Practitioner pipelines** (in process, outside GREG): an end-to-end upgrade along the cheapest path, and parametric min-cost flow. The second is the truth algorithm, so it is optimal by construction.
- **Rule** (verbatim from `results-v4.json`):

> F7 (natural instances, exact truth): routed optimal > best constituent optimal, routed wrong <= best constituent wrong, one-sided exact sign test over discordant held-out items p < 0.05, routed median latency <= 60 s and <= 10x the best constituent's median. Best constituent chosen on held-out results (most optimal, then fewest wrong). Practitioner, compiled-arm and per-network comparisons reported, not part of the rule. VPL = families meeting their rule.

## Results (scripted from `results-v4.json`)

- **Source commit:** `14ec7a6`; manifest sha256 `f965222d8f9df5a2...`; 2 pinned workers; Python 3.13.16.
- **Development selection:** static recipe `graph_then_allocate`; development optimal counts by recipe {"bayes_then_voi": null, "estimate_then_optimize": null, "forecast_then_allocate": null, "forecast_then_staff": null, "graph_then_allocate": 50, "identify_then_optimize": null}.
- **Held-out items:** 200 on 20 networks; out of scope: 0.

| Arm | optimal | suboptimal | wrong | no decision | throughput shortfall vs optimum | median s |
|---|---:|---:|---:|---:|---:|---:|
| graph intelligence alone: cheapest edge of the current min cut, repeated (constituent) (**best constituent**) | 108 | 92 | 0 | 0 | 329 | 0.2426 |
| optimiser alone on a flow-blind model (constituent) | 19 | 181 | 0 | 0 | 2839 | 0.6519 |
| practitioner: lease end to end along the cheapest path (in process) | 70 | 130 | 0 | 0 | 1018 | 0.0002 |
| practitioner: parametric min-cost flow = the truth algorithm (in process) | 200 | 0 | 0 | 0 | 0 | 0.0043 |
| static composition (recipe chosen on development items) | 200 | 0 | 0 | 0 | 0 | 1.2842 |
| **routed composition** (compile -> CP-SAT -> max-flow cross-check) | 200 | 0 | 0 | 0 | 0 | 1.2892 |
| Competency Compiler (`{compile: ...}`) | 200 | 0 | 0 | 0 | 0 | 1.2816 |

Routed composition against every other arm (one-sided exact sign test over discordant items; a win is an item the routed arm decides optimally and the other does not):

| Against | wins | losses | sign test p |
|---|---:|---:|---:|
| graph intelligence alone: cheapest edge of the current min cut, repeated (constituent) | 92 | 0 | <1e-6 |
| optimiser alone on a flow-blind model (constituent) | 181 | 0 | <1e-6 |
| practitioner: lease end to end along the cheapest path (in process) | 130 | 0 | <1e-6 |
| practitioner: parametric min-cost flow = the truth algorithm (in process) | 0 | 0 | 1.000000 |
| static composition (recipe chosen on development items) | 0 | 0 | 1.000000 |
| Competency Compiler (`{compile: ...}`) | 0 | 0 | 1.000000 |

Latency rule (pre-registered): routed median 1.2892 s = 5.314x the best constituent's; limit 10.0x and 60 s; met: True.
Per-network (secondary): routed has more optimal items than the best constituent on 19 networks, fewer on 0, sign test p = 2e-06.

**Verdict under the frozen rule: LIFT.** Best constituent `graph_alone_greedy`; routed 92 wins, 0 losses, sign test p = < 1e-6; translation failures 0.0, composition failures 0.0; model calls 0, money $0.0.

**VPL v4 = 1 of 1 families.**

Per network (optimal items, routed / best constituent):

| Network | routed | best constituent |
|---|---:|---:|
| atlanta | 10 | 7 |
| cost266 | 10 | 5 |
| dfn-bwin | 10 | 6 |
| dfn-gwin | 10 | 3 |
| france | 10 | 2 |
| geant | 10 | 3 |
| germany50 | 10 | 1 |
| giul39 | 10 | 7 |
| janos-us | 10 | 6 |
| janos-us-ca | 10 | 10 |
| newyork | 10 | 8 |
| nobel-eu | 10 | 3 |
| nobel-us | 10 | 6 |
| norway | 10 | 8 |
| pdh | 10 | 8 |
| pioro40 | 10 | 6 |
| sun | 10 | 7 |
| ta1 | 10 | 6 |
| ta2 | 10 | 3 |
| zib54 | 10 | 3 |

Descriptive (computed from `results-v4.json`, not part of the rule):
- Over the 200 items, greedy fell short of the optimum by 1.6 units on average (2.9% of throughput); the largest shortfall was 14 units.
- The median admissible corridor has 9 arcs (maximum 16).
- Leasing raises the median optimum by 23 units over the free capacity alone.

## Negative evidence and limits

- **A single exact algorithm ties the composition.** The practitioner's parametric min-cost flow, which is the truth algorithm, is optimal on all 200 items: composition wins 0 and loses 0 against it.
  - It ran in 4.3 ms per item, in process. The composition ran in 1.29 s through isolated workers, so these latencies are not comparable.
  - The lift is therefore over GREG's own repertoire. The strongest standalone graph intelligence GREG has for this geometry is greedy min-cut reinforcement, which admission v1 already recorded as SUPERSEDED by this composition. The lift is not over what a competent operations-research practitioner would write.
  - The residual capability is plain: a budgeted min-cost-flow expansion genome (min-cost flow plus bisection, with its own certificate) would be a single intelligence matching the composition at far lower latency. Once one exists, F7's lift should be expected to disappear against it.
- **Routing adds nothing within the family.** Routed equals static equals compiled on all 200 items: identical answers, recipe chosen on development. The compiler arm confirms only that Layer 5 selects the composition for this request.
- **Latency is not free:** the routed median is 5.3x the greedy constituent's. It meets the pre-registered 10x rule.
- **The decision layer is declared, not observed.** Module size, utilisation target, admissible paths, prices, the arc limit and the budget are a standard planning formulation, not an operator's real costs.
- **Items within one network share its topology.** The item-level sign test treats them as independent. The per-network test (19 networks favour the composition, 0 favour greedy, 1 tied; p = 2e-06) is the more conservative reading, and it agrees.
- **What was looked at before the run:**
  - the development networks, where greedy was optimal on 23 of 50;
  - the corridor sizes of all networks, from topology alone.
  No parameter was changed after the development look.
- One container; latency is this machine's. No model was called and no money was spent.

## Section 16 accounting (POST_HOC, `vpl_metrics.py` at `ae396d2`)

| Measure | Value |
|---|---|
| Latency | routed 1.289 s vs greedy 0.243 s: 5.31x, +1.05 s |
| Routed vs static | 0 wins, 0 losses, 200 ties; static decides every item; identical answers 200 |
| vs shortest-path upgrade (practitioner) | 130 wins, 0 losses, 70 ties (p < 1e-6) |
| vs parametric min-cost flow (practitioner) | 0 wins, 0 losses, 200 ties |
| False answers / abstentions vs best constituent | 0 / 0 |

## Effect on the cumulative record

- **VPL** (families meeting their frozen rule, all runs): F1, F2R, F3, F4, F6, F7 lift; F2 (v1) and F5 do not. Natural families are now **2 of 3**: F5 no, F6 yes, F7 yes, with F7's natural-instances caveat.
- **Practitioner pipelines:** F7 is the first family where composition significantly beats a declared practitioner pipeline (the shortest-path upgrade). It does not beat the exact practitioner algorithm, which ties it.
- **Layers:** the lift uses Layer 3 genomes only. Layers 1, 2 and 4 still contribute to no VPL family.
