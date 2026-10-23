# GREG Mind coverage against the founder's specification, 2026-10-21

Base commit `239a87f` (#158's line). Compared with PR #179 (`claude/greg-mind-lineage-convergence` at `0067be6`, merge base `463a9d0`). Machine-readable record: [`MIND-COVERAGE-2026-10-21.json`](MIND-COVERAGE-2026-10-21.json). Checked by `tests/unit/test_mind_coverage_record.py`.

The standard is the founder's text, not a summary of it:

- `docs/intent/sources/POLYINTELLIGENCE-MIND-CONTINUATION-DIRECTIVE-2026-10-07-source.md`
- `docs/intent/sources/POLYINTELLIGENCE-MIND-CONTINUATION-REISSUE-2026-10-13-source.md`
- `docs/intent/sources/MIND-MAXIMUM-CONTINUATION-2026-10-21-source.md`
- `docs/cortex/SEED_GENOME_REQUIREMENTS.json`

This record changes no code, routing, rule or authority. It attaches nothing.

## Status ladder

Each requirement gets one highest-attained status, backed by a file:line or an evidence path.

| Status | Meaning |
|---|---|
| ABSENT | a stated code search found no mechanism; named only by the directive |
| INVENTORIED | named in a repository registry, reserved-family record or backcast; nothing executes it |
| IMPLEMENTED | executable code exists |
| INTEGRATED | reachable through GREG's one cognition path (cognition.reason / the Competency Compiler) |
| BENCHMARKED | a frozen evaluation exists (any verdict, including SUPERSEDED, REJECTED, COMPOSITION_ONLY, EXPERIMENTAL) |
| ADMITTED | DEFAULT_FOR_GEOMETRY or NICHE_CAPABILITY under the admission rule at its current version |
| ATTACHED | founder-attached (none: seed families and cortex organs are attached at registration by code, which is recorded separately) |
| EXERCISED | used inside a GREG mission run on the durable mission path with a recorded receipt |

- An item's status is the highest status of its direct mechanisms; precursors are listed and never raise it.
- Rungs are not cumulative: an EXERCISED organ need not be ADMITTED (none is); a BENCHMARKED genome may have been refuted.
- Lineage 'both' means the cited code or evidence exists at the merge base of #158's line and #179; '#158' only on this line; '#179' only on PR #179.
- Evidence written git:<sha>:<path>:<line> lives on PR #179's branch and is not in this tree.
- mind_status at this commit was run read-only to read every genome's frozen admission; its labels are quoted in notes.

**ATTACHED is empty.** Seed families (micro, exact, estimation, formal, optimization, causal, evidence, semantic) and the cortex organs are attached at registration by `catalog.initial_state`. No founder CAPABILITY_ATTACH exists for any genome.

**EXERCISED is narrow.** One recorded body mission uses cognition: `m:cortex-rehearsal` (2026-10-01, `tests/evidence/greg-cortex-rehearsal/`). It ran the cortex router, schedule extraction and CP-SAT through kill -9, restart, approval and one settlement. It used a per-test key, not Alfonso's, on a Linux container. No genome has run inside a recorded mission.

## Counts by layer

| Layer (source label) | ABSENT | INVENTORIED | IMPLEMENTED | INTEGRATED | BENCHMARKED | ADMITTED | ATTACHED | EXERCISED | items |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1: PRIMITIVE / BASAL INTELLIGENCE | 5 | 1 |  |  |  | 17 |  |  | 23 |
| 2: DISTRIBUTED / COLLECTIVE INTELLIGENCE |  |  |  | 1 |  | 7 |  |  | 8 |
| 3: SOLVER / MACRO-COGNITIVE INTELLIGENCE | 21 | 1 |  | 7 | 13 | 45 |  | 6 | 93 |
| 3.mental_models: Section 6 mental models as executable operators |  |  | 19 | 14 |  |  |  |  | 33 |
| 4: DEVELOPMENTAL / MORPHOGENETIC INTELLIGENCE | 3 | 1 |  | 1 | 1 | 14 |  | 1 | 21 |
| 5: META-INTELLIGENCE / INSTITUTIONAL COLLECTIVE COGNITION |  |  | 6 | 19 | 8 | 2 |  | 1 | 36 |

Where the two lineages differ, the item's `lineage` names the one that holds its status. #179 alone holds ADMITTED for nine items, all through its operation-family admission v3: deterministic reflexes, rule-based classification, flock (PSO beats random search only), human collective (Dawid-Skene, dense crowds only), nonlinear optimisation, dynamic programming, decision analysis, tree search and value of information. On #158 those operation families have no frozen row, so `mind_status` labels them BUILT.

## Section 31: the 17 conditions

Met 9, partly met 8, unmet 0.

| # | Condition (verbatim) | Verdict | Attained | Remaining gap |
|---:|---|---|---|---|
| 1 | The five layers are represented by real executable mechanisms, not merely documents. | **PARTLY_MET** | Every layer has executable mechanisms: L1 6 genomes + micro; L2 6 genomes (+ crowd, swarm on #179); L3 33 genomes plus the catalog operation families (21 catalog families across layers) and 8 cortex organs; L4 develop_repair, develop_constraint_release, P8, Genesis; L5 the compiler. | Directive-named families with no executor: associative microcircuits/networks, small local learners, rate control, beam/MCTS/iterative deepening, GA/QD/novelty/hyperheuristics, MDL, repeated games/bargaining/commitment, theorem proving, robust control, centrality, community/topology analysis, convex optimization, judgmental and scenario forecasting, global workspace, active inference, ecology bidding, differentiation, cellular automata, graph diffusion. |
| 2 | The major present-day mathematical/computational intelligence families are registered and benchmarked. | **PARTLY_MET** | 47 genomes benchmarked under the admission rule (35 admitted); cortex Fermi/Z3/CP-SAT benchmarked in cross-geometry v0.3; #179 benchmarked 16 operation families. | Unbenchmarked major families: semantic (no model, NOT_RUN), SAT, convex/nonlinear optimization, packing, centrality, community analysis, beam/MCTS, GA/QD/novelty, MDL, repeated games/bargaining, theorem proving, robust control, judgmental/scenario forecasting, probabilistic programming, digital twins. Most Layer 1, 2 and 4 admissions are on simulated worlds. |
| 3 | Problem geometry selects methods based on actual competence. | **PARTLY_MET** | The compiler ranks candidates by frozen admission status, subregion evidence and settled outcomes; tests check it routes exactly on fresh positive evidence. | No genome is attached, so on a real body the compiler issues attach asks and routes to fallbacks; no competence has been settled from real founder missions; within a family, geometry routing added nothing in any P6 run (the router chose the static recipe). |
| 4 | Multiple intelligences can compose through typed evidence and receipts. | **MET** | Typed translation between stage receipts; compilation receipts carry intermediate receipts; schedule extraction -> CP-SAT ran on the supervised body. | Composition has been exercised on a body only for the cortex extraction -> CP-SAT pipeline, with a test key. |
| 5 | Composition produces repeated VPL across materially different held-out problem families. | **PARTLY_MET** | Six recipes show VPL_LIFT on held-out families (F1, F2R, F4, F6, F7, F8); natural families lift 3 of 4 (F6, F7, F8). | Lift is composition over GREG's own repertoire: F7 is NO_LIFT once flow_expansion_mcf is a constituent and ties the OR practitioner; F8's EWMA ablation is cheaper; F6 loses to the weekly-mean practitioner on day count; routing adds nothing within a family; every lift costs 1.5-5.2x latency; F8 data rights unverified. No family drawn from GREG's own operating needs. |
| 6 | Conditional competence can either demonstrate useful lift or be truthfully demoted if the static policy wins. | **MET** | Decisive pre-registered P4 retest: REGRESSION (160 vs 162); conditional routing demoted, static default kept. | None for the condition; conditional competence may be retested only with a new pre-registration. |
| 7 | Protected evolution can improve nonconstitutional cognition against an evaluator it cannot alter. | **PARTLY_MET** | Cycle 6 RETAIN under a sealed, clean-room evaluator: held-out 105-73, p = 0.00995, mean loss 29.6% lower; canary passes. | One kept improvement in seven designs; it misses the programme-wide threshold 0.00833; random restart is at least as good (80-89); the proposal is not applied (founder adoption); no second target (cycle 7 NOT_VIABLE); the stress-gate repair's historical-equivalence claim is unverified (its test exercises the fallback path). |
| 8 | Collective/swarm mechanisms demonstrate native competence on appropriate geometries. | **PARTLY_MET** | ACO DEFAULT and Physarum NICHE on mathematical instances; market DEFAULT, quorum and immune NICHE on simulated worlds. | Flock SUPERSEDED; PSO and Dawid-Skene beat only weak baselines (#179); no collective mechanism admitted on natural data; immune tolerance, ecology bidding and PSO (on #158) have no executor. |
| 9 | Developmental/morphogenetic mechanisms remain safely separated from biological claims and demonstrate at least bounded structural adaptation in simulation. | **MET** | develop_repair NICHE (simulated lattice) and develop_constraint_release DEFAULT (mathematical instances); worlds.py and the frontier backcasts keep biological claims out. | Generalized repair did not replicate (12-3, then 7-8); MICA ties a central replanner (#179); no capability-topology assembly. |
| 10 | Human/expert intelligence is a legitimate typed route where machine methods are insufficient. | **MET** | Typed human route with role, competence domain, conflicts, refusal and question-bound founder decision. | No real qualified-human judgment has been recorded; only the founder role can decide. |
| 11 | No cognition mechanism creates authority. | **MET** | Every receipt carries authority_created false and EXISTING_KERNEL_GATE_REQUIRED; P8 decisions PROPOSED_NOT_APPLIED. | A universal negative is tested, not proven; it holds for the paths the tests cover. |
| 12 | Receipts preserve how conclusions were obtained. | **MET** | All 29 section-12 fields. | Proof artifacts are typed, but later_appraisal and outcome_link are filled only after settlement, which has no real founder outcomes. |
| 13 | Negative evidence changes future routing. | **MET** | SUPERSEDED/REJECTED/COMPOSITION_ONLY genomes are excluded; NO_LIFT recipes ranked last; P4 demoted; settled outcomes inhibit after 10. | On-body inhibition has never fired on real outcomes. |
| 14 | Missing competence can trigger Capability Genesis. | **MET** | A compiler CAPABILITY_DEFICIT enters Genesis: withheld genome, then an installed package qualified on a frozen oracle, then the founder; the original mission closes after attach. | Exercised only on test-key tmp bodies; the recorded live Genesis run (2026-09-26) built a non-cognition function. |
| 15 | The Mind remains one component of the complete Body + Organs + Mind GREG. | **PARTLY_MET** | One cognition entry on the capability/mission path; no second registry, router, ledger or authority. | VEPMC = 0 (mac_body missing); organs (DALEOBANKS, WMI) do not consume cognition receipts; Goal Gravity never ran on a real founder goal. |
| 16 | All speculative descendants remain preserved in the Backcast GPS horizon. | **MET** | 13 frontier backcasts, each with nearest falsifiable experiment and buildability. | None missing; precursors for most are untested. |
| 17 | The project can state exactly what is built, simulated, experimentally supported, externally verified, unresolved, or frontier. | **PARTLY_MET** | mind_status labels every mechanism BUILT/SIMULATED/HELDOUT_SUPPORTED/EXTERNALLY_VERIFIED/UNRESOLVED/FRONTIER. | #158's index has no rows for #179's operation-family admissions (mind_status labels those families BUILT while #179 holds frozen DEFAULT verdicts); 'exercised on a mission' is not a label; no all-lineage data-exposure ledger. |

## Layer 1: PRIMITIVE / BASAL INTELLIGENCE

| Requirement | Status | Lineage | Mechanisms | Evidence | Note / search |
|---|---|---|---|---|---|
| deterministic reflexes | ADMITTED | #179 | family:micro | `greg/cognition/catalog.py:10`<br>`greg/cognition/cortex.py:157` | ternary set-point reflex (#158: INTEGRATED; #179: ADMITTED) |
| state-machine intelligence | ADMITTED | both | genome:basal_breaker | `greg/cognition/genomes/basal.py:1975`<br>`greg/cognition/genomes/library.py:97` | Precursors: genome:basal_hysteresis. |
| local sensing | ABSENT | n/a |  |  | no Layer-1 sensing primitive; estimators consume supplied signals Search: grep -i 'sensor|sensing' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): only greg/gravity.py typed situations and greg/dataplane.py; worlds.py states GREG has no physical sensors Precursors: genome:basal_kalman, genome:basal_bayes_filter, community. |
| threshold control | ADMITTED | both | family:micro, genome:basal_hysteresis | `greg/cognition/catalog.py:10`<br>`greg/cognition/cortex.py:157`<br>`greg/cognition/genomes/basal.py:1854` |  |
| homeostatic controllers | ADMITTED | both | genome:pid_simopt, genome:basal_pid, family:control | `greg/cognition/genomes/competitors.py:1122`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/basal.py:1766` |  |
| anomaly response | ADMITTED | both | genome:basal_breaker, family:pattern, family:robust_pattern | `greg/cognition/genomes/basal.py:1975`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/catalog.py:24` |  |
| associative microcircuits | INVENTORIED | both |  | `greg/cognition/reserved.py:101` | reserved cortex.developmental.molecular_micro has no executor Precursors: family:micro. |
| simple adaptive filters | ADMITTED | both | genome:basal_bayes_filter, genome:basal_kalman | `greg/cognition/genomes/basal.py:1898`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/basal.py:1818` |  |
| local error correction | ABSENT | n/a |  |  | Search: grep -i 'error.correct' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): hits only forecasting residual text and benchmark wording, no primitive Precursors: genome:develop_repair, genome:basal_hysteresis. |
| rule-based classification | ADMITTED | #179 | family:pattern, family:robust_pattern | `greg/cognition/catalog.py:24`<br>`greg/cognition/cortex.py:157`<br>`git:0067be6:greg/cognition/catalog.py:31` | Precursors: genome:collective_immune. (#158: INTEGRATED; #179: ADMITTED) |
| feedback control | ADMITTED | both | genome:pid_simopt, family:control, genome:control_mpc | `greg/cognition/genomes/competitors.py:1122`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/catalog.py:19` |  |
| bounded memory | ADMITTED | both | genome:basal_breaker | `greg/cognition/genomes/basal.py:1975`<br>`greg/cognition/genomes/library.py:97` | sliding failure window Precursors: genome:basal_hysteresis. |
| hysteresis | ADMITTED | both | genome:basal_hysteresis | `greg/cognition/genomes/basal.py:1854`<br>`greg/cognition/genomes/library.py:97` |  |
| rate control | ABSENT | n/a |  |  | Search: grep -i 'token.bucket|rate.limit|rate_control' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match Precursors: genome:basal_breaker. |
| resource regulation | ADMITTED | both | genome:basal_bandit | `greg/cognition/genomes/basal.py:1943`<br>`greg/cognition/genomes/library.py:97` | Precursors: genome:collective_market. |
| evaluate PID | ADMITTED | both | genome:basal_pid, genome:pid_simopt, family:control | `greg/cognition/genomes/basal.py:1766`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/competitors.py:1122` | basal_pid SUPERSEDED (0-30 vs SIMC competitor); pid_simopt DEFAULT (simulated plants) |
| evaluate finite-state control | ADMITTED | both | genome:basal_breaker | `greg/cognition/genomes/basal.py:1975`<br>`greg/cognition/genomes/library.py:97` |  |
| evaluate simple Bayesian filters | ADMITTED | both | genome:basal_bayes_filter | `greg/cognition/genomes/basal.py:1898`<br>`greg/cognition/genomes/library.py:97` |  |
| evaluate exponential smoothing | ADMITTED | both | genome:forecast_quantile | `greg/cognition/genomes/forecasting.py:466`<br>`greg/cognition/genomes/library.py:97` | damped-trend exponential smoothing with quantiles (a Layer-3 genome; the only natural-data admission) |
| evaluate Kalman-family estimators | ADMITTED | both | genome:basal_kalman | `greg/cognition/genomes/basal.py:1818`<br>`greg/cognition/genomes/library.py:97` |  |
| evaluate lightweight bandits | ADMITTED | both | genome:basal_bandit | `greg/cognition/genomes/basal.py:1943`<br>`greg/cognition/genomes/library.py:97` |  |
| evaluate associative networks | ABSENT | n/a |  |  | Search: grep -i 'associat|hopfield|hebb' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): only reserved.py text and evidence_causal 'association' claims |
| evaluate small local learners | ABSENT | n/a |  |  | Search: grep -i 'online learn|perceptron|local learner|LMS' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match Precursors: genome:basal_bandit. |

## Layer 2: DISTRIBUTED / COLLECTIVE INTELLIGENCE

| Requirement | Status | Lineage | Mechanisms | Evidence | Note / search |
|---|---|---|---|---|---|
| Hive / quorum intelligence (alternatives, evidence accumulation, recruitment, cross-inhibition, threshold) | ADMITTED | both | genome:collective_quorum, family:collective | `greg/cognition/genomes/collective.py:2970`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/catalog.py:28` | simulated world; catalog quorum EXPERIMENTAL on #179 |
| Ant / stigmergic intelligence (route search, exploration, workflow routing, path discovery) | ADMITTED | both | genome:collective_aco | `greg/cognition/genomes/collective.py:3041`<br>`greg/cognition/genomes/library.py:97` | MAX-MIN ant system on symmetric TSP (mathematical instances); adaptive workflow routing not built |
| Slime-mold / adaptive-network intelligence | ADMITTED | both | genome:collective_physarum | `greg/cognition/genomes/collective.py:3084`<br>`greg/cognition/genomes/library.py:97` |  |
| Flock / local-coordination intelligence | ADMITTED | #179 | genome:collective_flock, family:swarm | `greg/cognition/genomes/collective.py:3272`<br>`greg/cognition/genomes/library.py:97`<br>`git:0067be6:greg/cognition/catalog.py:33` | flock local rules SUPERSEDED; PSO (#179) beats random search only, loses to multistart L-BFGS-B post hoc (#158: BENCHMARKED; #179: ADMITTED) |
| Immune intelligence (recognition, tolerance, decoupling, quarantine, challenge, incident memory, recoupling) | ADMITTED | both | genome:collective_immune, resilience | `greg/cognition/reserved.py:90`<br>`greg/cognition/genomes/collective.py:3158`<br>`greg/cognition/genomes/library.py:97` | negative selection NICHE on a simulated world; decoupling warning in resilience.py; no anomaly-tolerance family Precursors: genesis. |
| Ecological intelligence (diversity, niches, succession, extinction, rare-niche preservation) | INTEGRATED | both | settlement | `greg/cognition/reserved.py:95`<br>`greg/cognition/settlement.py:1`<br>`greg/cognition/compiler.py:1190` | admission statuses NICHE/SUPERSEDED act as niche and extinction; methods do not bid; no ecology executor Precursors: genome:collective_market. |
| Market / resource-allocation intelligence | ADMITTED | both | genome:collective_market | `greg/cognition/genomes/collective.py:3233`<br>`greg/cognition/genomes/library.py:97` | clock auction DEFAULT on a simulated world |
| Human collective intelligence (typed human sources, no majority vote) | ADMITTED | #179 | human_route, community, family:crowd | `greg/cognition/human.py:1`<br>`greg/cognition/compiler.py:34`<br>`greg/dataplane.py:87` | Precursors: eval:crowd_sparse. (#158: INTEGRATED; #179: ADMITTED) |

## Layer 3: SOLVER / MACRO-COGNITIVE INTELLIGENCE

| Requirement | Status | Lineage | Mechanisms | Evidence | Note / search |
|---|---|---|---|---|---|
| Semantic intelligence (LLM interpretation, hypotheses, translation, synthesis, ontology, qualitative) | INTEGRATED | both | organ:cognition.cortex.semantic, family:semantic | `cortex/organs/semantic.py:1`<br>`greg/cognition/catalog.py:60`<br>`greg/cognition/catalog.py:26` | no local model configured: every semantic arm NOT_RUN |
| Fermi / reference-class estimation | BENCHMARKED | both | organ:cognition.cortex.estimation.fermi, recipe:estimate_then_optimize | `cortex/organs/estimation.py:1`<br>`greg/cognition/catalog.py:60`<br>`greg/cognition/composition.py:72` |  |
| Bayesian intelligence (priors, likelihood, posterior, calibration, sequential evidence) | ADMITTED | both | genome:bayes_interval, family:probabilistic, genome:basal_bayes_filter, calibration | `greg/cognition/reserved.py:82`<br>`greg/cognition/genomes/solvers_b.py:1366`<br>`greg/cognition/genomes/library.py:97` | no probabilistic-programming executor |
| Causal intelligence (DAGs, confounding, intervention, counterfactual, identification, discriminating evidence) | ADMITTED | both | genome:causal_backdoor, organ:cognition.cortex.evidence_causal, recipe:identify_then_optimize | `greg/cognition/genomes/solvers_c.py:2712`<br>`greg/cognition/genomes/library.py:97`<br>`cortex/organs/evidence_causal.py:1` |  |
| Monte Carlo | ADMITTED | both | genome:mc_expectation, family:simulation | `greg/cognition/genomes/stochastic.py:1613`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/catalog.py:21` |  |
| bootstrap | BENCHMARKED | both | genome:bootstrap_ci | `greg/cognition/genomes/stochastic.py:1692`<br>`greg/cognition/genomes/library.py:97` | REJECTED |
| scenario simulation | BENCHMARKED | #179 | family:simulation | `greg/cognition/reserved.py:85`<br>`greg/cognition/catalog.py:21`<br>`greg/cognition/cortex.py:157` | iid Bernoulli Monte Carlo REJECTED on #179; no twin (#158: INTEGRATED; #179: BENCHMARKED) |
| uncertainty propagation | BENCHMARKED | both | organ:cognition.cortex.estimation.fermi | `cortex/organs/estimation.py:1`<br>`greg/cognition/catalog.py:60` | Gaussian-copula range propagation |
| stochastic processes | ADMITTED | both | genome:queue_erlang | `greg/cognition/genomes/solvers_b.py:1332`<br>`greg/cognition/genomes/library.py:97` | Precursors: genome:basal_bayes_filter. |
| rare-event estimation | ADMITTED | both | genome:mc_importance | `greg/cognition/genomes/solvers_b.py:1285`<br>`greg/cognition/genomes/library.py:97` |  |
| SMT | BENCHMARKED | both | organ:cognition.cortex.formal.z3, family:formal | `cortex/organs/formal.py:21`<br>`greg/cognition/catalog.py:60`<br>`greg/cognition/catalog.py:13` |  |
| SAT | ABSENT | n/a |  |  | Search: grep 'pysat|SAT solver|CNF' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match; SAT is reached only through Z3 and CP-SAT Precursors: organ:cognition.cortex.formal.z3, organ:cognition.cortex.optimization.cpsat. |
| CP-SAT | EXERCISED | both | organ:cognition.cortex.optimization.cpsat | `cortex/organs/cpsat.py:1`<br>`greg/cognition/catalog.py:60` |  |
| CSP | EXERCISED | both | organ:cognition.cortex.optimization.cpsat, family:optimization | `cortex/organs/cpsat.py:1`<br>`greg/cognition/catalog.py:60`<br>`greg/cognition/catalog.py:14` |  |
| integer programming | EXERCISED | both | genome:milp_optimize, organ:cognition.cortex.optimization.cpsat | `greg/cognition/genomes/stochastic.py:1757`<br>`greg/cognition/genomes/library.py:97`<br>`cortex/organs/cpsat.py:1` |  |
| mixed-integer optimization | BENCHMARKED | both | genome:milp_optimize | `greg/cognition/genomes/stochastic.py:1757`<br>`greg/cognition/genomes/library.py:97` |  |
| exact or bounded combinatorial solvers | ADMITTED | both | genome:knapsack_bnb, genome:mechanism_check | `greg/cognition/genomes/competitors.py:908`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/strategic.py:2333` |  |
| linear optimization | INTEGRATED | both | family:optimization | `greg/cognition/linear.py:3`<br>`greg/cognition/catalog.py:14`<br>`greg/cognition/cortex.py:157` | Precursors: genesis. |
| nonlinear optimization | ADMITTED | #179 | family:swarm, family:blackbox | `greg/cognition/genomes/competitors.py:887`<br>`git:0067be6:greg/cognition/catalog.py:33`<br>`git:0067be6:greg/cognition/repertoire.py:10` | black-box only (#179); multistart L-BFGS-B exists only as a competitor arm (#158: None; #179: ADMITTED) |
| convex optimization | ABSENT | n/a |  |  | Search: grep 'cvxpy|convex optim|SLSQP' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): only competitors.py L-BFGS arm; no convex solver family Precursors: family:optimization. |
| integer optimization | EXERCISED | both | organ:cognition.cortex.optimization.cpsat, genome:milp_optimize | `cortex/organs/cpsat.py:1`<br>`greg/cognition/catalog.py:60`<br>`greg/cognition/genomes/stochastic.py:1757` |  |
| assignment | BENCHMARKED | both | genome:assignment_lsa | `greg/cognition/assignment.py:1`<br>`greg/cognition/genomes/graph_or.py:1440`<br>`greg/cognition/genomes/library.py:97` | Precursors: genesis. |
| matching | ADMITTED | both | genome:graph_matching | `greg/cognition/genomes/graph_or.py:1480`<br>`greg/cognition/genomes/library.py:97` |  |
| knapsack | ADMITTED | both | genome:knapsack_bnb, genome:dp_knapsack | `greg/cognition/genomes/competitors.py:908`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/solvers_b.py:1213` |  |
| packing | ABSENT | n/a |  |  | Search: grep -i 'bin.pack|packing' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no packing family Precursors: organ:cognition.cortex.optimization.cpsat, genome:knapsack_bnb. |
| scheduling | EXERCISED | both | organ:cognition.cortex.optimization.cpsat, organ:cognition.cortex.extraction.schedule, genome:develop_constraint_release | `cortex/organs/cpsat.py:1`<br>`greg/cognition/catalog.py:60`<br>`cortex/organs/schedule_extraction.py:1` |  |
| routing | ADMITTED | both | genome:collective_aco, genome:grid_dijkstra | `greg/cognition/genomes/collective.py:3041`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/competitors.py:968` |  |
| resource allocation | ADMITTED | both | genome:collective_market, genome:basal_bandit, recipe:graph_then_allocate | `greg/cognition/genomes/collective.py:3233`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/basal.py:1943` |  |
| shortest path | ADMITTED | both | genome:grid_dijkstra, family:graph | `greg/cognition/genomes/competitors.py:968`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/catalog.py:15` |  |
| min-cut / max-flow | ADMITTED | both | genome:flow_maxflow | `greg/cognition/genomes/flow.py:635`<br>`greg/cognition/genomes/library.py:97` |  |
| centrality | ABSENT | n/a |  |  | Search: grep -i 'centrality' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match |
| reachability | ADMITTED | both | genome:verify_modelcheck | `greg/cognition/network.py:5`<br>`greg/cognition/genomes/solvers_c.py:2607`<br>`greg/cognition/genomes/library.py:97` |  |
| matching (graph) | ADMITTED | both | genome:graph_matching | `greg/cognition/genomes/graph_or.py:1480`<br>`greg/cognition/genomes/library.py:97` |  |
| community / topology analysis | ABSENT | n/a |  |  | Search: grep -i 'louvain|community detection|modularity' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): only unrelated prose in flow.py/graph_or.py Precursors: genome:collective_physarum. |
| control-point and dependency analysis | ADMITTED | both | genome:flow_maxflow, operators | `greg/cognition/genomes/flow.py:635`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/compiler.py:206` |  |
| DAG reasoning | ADMITTED | both | genome:critical_path | `greg/cognition/genomes/graph_or.py:1535`<br>`greg/cognition/genomes/library.py:97` |  |
| critical path | ADMITTED | both | genome:critical_path | `greg/cognition/genomes/graph_or.py:1535`<br>`greg/cognition/genomes/library.py:97` |  |
| dynamic programming | ADMITTED | #179 | genome:dp_knapsack, family:sequential | `greg/cognition/genomes/solvers_b.py:1213`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/catalog.py:25` | dp_knapsack SUPERSEDED by branch and bound; backward induction DEFAULT on #179 (#158: BENCHMARKED; #179: ADMITTED) |
| queueing | ADMITTED | both | genome:queue_erlang | `greg/cognition/genomes/solvers_b.py:1332`<br>`greg/cognition/genomes/library.py:97` |  |
| scheduling (OR) | EXERCISED | both | organ:cognition.cortex.optimization.cpsat | `cortex/organs/cpsat.py:1`<br>`greg/cognition/catalog.py:60` |  |
| inventory | BENCHMARKED | both | genome:newsvendor_compile | `greg/cognition/genomes/forecasting.py:494`<br>`greg/cognition/genomes/library.py:97` | COMPOSITION_ONLY |
| capacity | ADMITTED | both | genome:flow_expansion_mcf | `greg/cognition/genomes/flow.py:676`<br>`greg/cognition/genomes/library.py:97` |  |
| allocation | ADMITTED | both | genome:graph_matching, genome:collective_market | `greg/cognition/genomes/graph_or.py:1480`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/collective.py:3233` |  |
| network optimization | ADMITTED | both | genome:min_cost_flow, genome:flow_expansion_mcf | `greg/cognition/genomes/graph_or.py:1576`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/flow.py:676` |  |
| stochastic optimization | BENCHMARKED | both | genome:newsvendor_compile, recipe:estimate_then_optimize | `greg/cognition/genomes/forecasting.py:494`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/composition.py:72` |  |
| decision analysis | ADMITTED | #179 | family:information, genome:decision_preposterior | `greg/cognition/catalog.py:20`<br>`greg/cognition/cortex.py:157`<br>`greg/cognition/genomes/decision.py:119` |  (#158: BENCHMARKED; #179: ADMITTED) |
| feedback control (L3) | ADMITTED | both | genome:pid_simopt | `greg/cognition/genomes/competitors.py:1122`<br>`greg/cognition/genomes/library.py:97` |  |
| model-predictive control | ADMITTED | both | genome:control_mpc | `greg/cognition/genomes/solvers_c.py:2643`<br>`greg/cognition/genomes/library.py:97` |  |
| state estimation | ADMITTED | both | genome:basal_kalman, genome:basal_bayes_filter | `greg/cognition/genomes/basal.py:1818`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/basal.py:1898` |  |
| robust control | ABSENT | n/a |  |  | Search: grep -i 'robust control|robust MPC|H-infinity|tube' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match Precursors: genome:control_mpc. |
| branch and bound | ADMITTED | both | genome:knapsack_bnb | `greg/cognition/genomes/competitors.py:908`<br>`greg/cognition/genomes/library.py:97` |  |
| beam search | ABSENT | n/a |  |  | Search: grep -i 'beam' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match |
| A* | BENCHMARKED | both | genome:search_astar | `greg/cognition/genomes/solvers_b.py:1250`<br>`greg/cognition/genomes/library.py:97` | SUPERSEDED by grid_dijkstra |
| tree search | ADMITTED | #179 | family:sequential | `greg/cognition/catalog.py:25`<br>`greg/cognition/cortex.py:157` | finite-horizon backward induction (#158: INTEGRATED; #179: ADMITTED) |
| Monte Carlo tree search | ABSENT | n/a |  |  | Search: grep -i 'mcts|monte carlo tree' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match |
| heuristic search | ADMITTED | both | genome:search_astar, genome:collective_aco | `greg/cognition/genomes/solvers_b.py:1250`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/collective.py:3041` |  |
| iterative deepening | ABSENT | n/a |  |  | Search: grep -i 'iterative deepening|IDA' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match |
| genetic algorithms | ABSENT | n/a |  |  | Search: grep -i 'genetic algorithm' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match; P8 uses mutation + crossover over closed configuration spaces Precursors: p8_evolution, genome:develop_constraint_release. |
| evolutionary strategies | BENCHMARKED | #179 | family:evolutionary, family:blackbox | `greg/cognition/catalog.py:29`<br>`greg/cognition/cortex.py:157`<br>`git:0067be6:greg/cognition/catalog.py:34` | differential evolution: REJECTED on a quadratic (v1), SUPERSEDED on its native geometry (#179) (#158: INTEGRATED; #179: BENCHMARKED) |
| program mutation | ADMITTED | both | genome:synth_cegis | `greg/cognition/genomes/solvers_c.py:2678`<br>`greg/cognition/genomes/library.py:97` | template-parameter synthesis; P8 never evolves code Precursors: p8_evolution. |
| quality-diversity | ABSENT | n/a |  |  | Search: grep -i 'quality.diversity|MAP-Elites' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match |
| novelty search | ABSENT | n/a |  |  | Search: grep -i 'novelty search' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match |
| hyperheuristics | ABSENT | n/a |  |  | Search: grep -i 'hyperheuristic' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match; constraint release recombines pipeline operators (nearest) Precursors: genome:develop_constraint_release. |
| entropy | ADMITTED | both | genome:info_experiment | `greg/cognition/genomes/solvers_c.py:2751`<br>`greg/cognition/genomes/library.py:97` |  |
| mutual information | ADMITTED | both | genome:info_experiment | `greg/cognition/genomes/solvers_c.py:2751`<br>`greg/cognition/genomes/library.py:97` |  |
| information gain | ADMITTED | both | genome:info_experiment | `greg/cognition/genomes/solvers_c.py:2751`<br>`greg/cognition/genomes/library.py:97` |  |
| value of information | ADMITTED | #179 | family:information, genome:decision_preposterior, recipe:bayes_then_voi | `greg/cognition/catalog.py:20`<br>`greg/cognition/cortex.py:157`<br>`greg/cognition/genomes/decision.py:119` |  (#158: BENCHMARKED; #179: ADMITTED) |
| compression / minimum description | ABSENT | n/a |  |  | Search: grep -i 'description length|MDL|compression' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match |
| experiment selection | ADMITTED | both | genome:info_experiment | `greg/cognition/genomes/solvers_c.py:2751`<br>`greg/cognition/genomes/library.py:97` |  |
| strategic interaction / best responses / equilibrium | ADMITTED | both | genome:bimatrix_nash, genome:game_lp_dual, family:game | `greg/cognition/genomes/strategic.py:2270`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/competitors.py:1063` |  |
| repeated games | ABSENT | n/a |  |  | Search: grep -i 'repeated game' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match |
| bargaining models | ABSENT | n/a |  |  | Search: grep -i 'bargain|nash bargaining' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match |
| credible commitment analysis | ABSENT | n/a |  |  | Search: grep -i 'commitment|stackelberg' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match |
| mechanism-design intelligence | ADMITTED | both | genome:mech_vcg, genome:mechanism_check | `greg/cognition/genomes/solvers_c.py:2562`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/strategic.py:2333` |  |
| theorem proving / proof assistants | ABSENT | n/a |  |  | Search: grep -i 'theorem prov|Lean|Coq|Isabelle' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match Precursors: organ:cognition.cortex.formal.z3. |
| model checking | ADMITTED | both | genome:verify_modelcheck | `greg/cognition/genomes/solvers_c.py:2607`<br>`greg/cognition/genomes/library.py:97` |  |
| temporal logic | ADMITTED | both | genome:verify_liveness | `greg/cognition/genomes/strategic.py:2377`<br>`greg/cognition/genomes/library.py:97` | fair-SCC liveness; no general LTL/CTL |
| type-level guarantees | INVENTORIED | both |  | `greg/cognition/contracts.py:94` | strict typed contracts guard inputs; no type-level proof family |
| property-based testing | ABSENT | n/a |  |  | Search: grep 'hypothesis.' in greg/cognition and tests: no property-based testing library use |
| exhaustive state exploration | ADMITTED | both | genome:verify_modelcheck, genome:mechanism_check | `greg/cognition/genomes/solvers_c.py:2607`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/strategic.py:2333` |  |
| counterexamples / falsification | ADMITTED | both | verifier, genome:synth_cegis | `greg/cognition/verification.py:1`<br>`tests/evidence/cortex-mutants-2026-10-01`<br>`greg/cognition/genomes/solvers_c.py:2678` |  |
| strongest opposing case / steelman | INTEGRATED | both | operators, receipt | `greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305`<br>`greg/cognition/compiler.py:1242` |  |
| red-team / abuse-case / exploit-path search | INTEGRATED | both | adversarial_organ, foundry | `cortex/organs/adversarial.py:1`<br>`foundry/lawful_leverage.py:1` | rule-based verifier and Foundry hard filters; no generative red-team search family |
| assumption attacks | INTEGRATED | both | adversarial_organ, operators | `cortex/organs/adversarial.py:1`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` |  |
| counterfactual decisions / policies / sequences | BENCHMARKED | both | composition, foundry | `greg/cognition/composition.py:509`<br>`docs/evidence/greg-composition-lift/2026-10-14-accounting/README.md`<br>`foundry/lawful_leverage.py:1` | ablation and do-nothing arms; a counterfactual family is not routable |
| alternative architectures and stress scenarios | BENCHMARKED | both | p8_evolution | `greg/cognition/evolution.py:1`<br>`docs/evidence/greg-protected-evolution/2026-10-16-cr-6/README.md` | P8 stress sets |
| time-series forecasting | ADMITTED | both | genome:forecast_quantile | `greg/cognition/genomes/forecasting.py:466`<br>`greg/cognition/genomes/library.py:97` |  |
| judgmental forecasting | ABSENT | n/a |  |  | Search: grep -i 'judgmental' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match Precursors: human_route. |
| reference-class forecasts | INTEGRATED | both | operators | `greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | reference_class operator re-routes to Bayesian families; no forecast family |
| probabilistic event forecasts | ADMITTED | both | genome:bayes_interval, family:probabilistic | `greg/cognition/genomes/solvers_b.py:1366`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/catalog.py:17` |  |
| scenario forecasts | ABSENT | n/a |  |  | Search: grep -i 'scenario forecast' in greg/cognition, cortex/organs, cortex/seed, foundry/lawful_leverage.py, greg/*.py (and #179's greg/cognition): no match Precursors: organ:cognition.cortex.estimation.fermi. |
| forecast calibration | ADMITTED | both | calibration, genome:forecast_quantile | `greg/cli.py:108`<br>`greg/cognition/genomes/forecasting.py:466`<br>`greg/cognition/genomes/library.py:97` |  |
| Human/expert adjudication: THIS REQUIRES QUALIFIED HUMAN JUDGMENT | INTEGRATED | both | human_route | `greg/cognition/human.py:1`<br>`greg/cognition/compiler.py:34` |  |

## Layer 3.mental_models: Section 6 mental models as executable operators

| Requirement | Status | Lineage | Mechanisms | Evidence | Note / search |
|---|---|---|---|---|---|
| first principles | IMPLEMENTED | both |  | `greg/cognition/compiler.py:325` | carried by: CompetencyGeometry: the problem is restated as typed fields before any method is chosen |
| inversion | INTEGRATED | both | operators | `greg/cognition/compiler.py:247`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| reference classes | INTEGRATED | both | operators | `greg/cognition/compiler.py:251`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| Bayesian updating | IMPLEMENTED | both |  | `greg/cognition/compiler.py:326` | carried by: cognition.probabilistic (beta_update) and the forecasting/decision genomes |
| Fermi decomposition | IMPLEMENTED | both |  | `greg/cognition/compiler.py:327` | carried by: cognition.cortex.estimation.fermi |
| sensitivity analysis | INTEGRATED | both | operators | `greg/cognition/compiler.py:239`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| expected value | IMPLEMENTED | both |  | `greg/cognition/compiler.py:328` | carried by: foundry.lawful_leverage Monte Carlo means and the information family |
| value of information | INTEGRATED | both | operators | `greg/cognition/compiler.py:50`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| opportunity cost | IMPLEMENTED | both |  | `greg/cognition/compiler.py:329` | carried by: foundry.lawful_leverage direct-labour and do-nothing baselines |
| optionality | IMPLEMENTED | both |  | `greg/cognition/compiler.py:310` | carried by: foundry.lawful_leverage defer-to-trigger and staged variants (option_value) |
| reversibility | INTEGRATED | both | operators | `greg/cognition/compiler.py:213`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| anti-ruin boundaries | INTEGRATED | both | operators | `greg/cognition/compiler.py:218`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| premortem | INTEGRATED | both | operators | `greg/cognition/compiler.py:235`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| counterfactuals | IMPLEMENTED | both |  | `greg/cognition/compiler.py:311` | carried by: do-nothing and direct-labour arms in every Foundry comparison; ablation arms in P6 |
| steelmanning | IMPLEMENTED | both |  | `greg/cognition/compiler.py:311` | carried by: every Foundry candidate and genome carries its strongest counterargument |
| falsification | INTEGRATED | both | operators | `greg/cognition/compiler.py:280`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| constraint analysis | IMPLEMENTED | both |  | `greg/cognition/compiler.py:333` | carried by: the constraints and optimization families; Foundry hard eligibility gates |
| bottleneck analysis | INTEGRATED | both | operators | `greg/cognition/compiler.py:225`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| systems thinking | IMPLEMENTED | both |  | `greg/cognition/compiler.py:339` | carried by: egregore.leverage strongest-path propagation over the institutional map |
| second-order effects | INTEGRATED | both | operators | `greg/cognition/compiler.py:287`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| feedback loops | INTEGRATED | both | operators | `greg/cognition/compiler.py:271`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| game theory | INTEGRATED | both | operators | `greg/cognition/compiler.py:258`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| mechanism design | INTEGRATED | both | operators | `greg/cognition/compiler.py:265`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| control-point analysis | IMPLEMENTED | both |  | `greg/cognition/compiler.py:334` | carried by: bottleneck operator (max_flow) and the Foundry control-point rule |
| dependency analysis | IMPLEMENTED | both |  | `greg/cognition/compiler.py:335` | carried by: foundry dependency surface and the dependency_capture harm dimension |
| backcasting | IMPLEMENTED | both |  | `greg/cognition/compiler.py:317` | carried by: greg.path Backcast GPS and frontier_backcasts |
| weakest-link reasoning | IMPLEMENTED | both |  | `greg/cognition/compiler.py:337` | carried by: Foundry path_support (every link must be real) and min-cut |
| marginal analysis | IMPLEMENTED | both |  | `greg/cognition/compiler.py:338` | carried by: Foundry staged pilots and value of information |
| Pareto analysis | INTEGRATED | both | operators | `greg/cognition/compiler.py:294`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` | executable typed operator; no effect benchmark |
| power-law reasoning | IMPLEMENTED | both |  | `greg/cognition/compiler.py:340` | carried by: anti_ruin tail requirement; only where tails are measured |
| portfolio/concentration reasoning | IMPLEMENTED | both |  | `greg/cognition/compiler.py:341` | carried by: dependency_capture harm ceiling and multi-candidate Pareto frontier |
| asymmetry analysis | IMPLEMENTED | both |  | `greg/cognition/compiler.py:342` | carried by: Foundry benefit and cost/harm vectors; control point only when it dominates |
| regenerative-impact analysis | IMPLEMENTED | both |  | `greg/cognition/compiler.py:343` | carried by: second_order_effects operator; participant_benefit in the Foundry vector |

## Layer 4: DEVELOPMENTAL / MORPHOGENETIC INTELLIGENCE

| Requirement | Status | Lineage | Mechanisms | Evidence | Note / search |
|---|---|---|---|---|---|
| local competent units | ADMITTED | both | genome:develop_repair, mica_lab | `greg/cognition/genomes/developmental.py:1271`<br>`greg/cognition/genomes/library.py:97`<br>`developmental/mica.py:1` |  |
| bounded membranes | INVENTORIED | both |  | `greg/isolation.py:1` | isolation is process/Landlock confinement, not a developmental membrane Precursors: genome:develop_repair. |
| local signaling | ADMITTED | both | genome:develop_repair, mica_lab | `greg/cognition/genomes/developmental.py:1271`<br>`greg/cognition/genomes/library.py:97`<br>`developmental/mica.py:1` |  |
| shared target states | ADMITTED | both | genome:develop_repair, mica_lab | `greg/cognition/genomes/developmental.py:1271`<br>`greg/cognition/genomes/library.py:97`<br>`developmental/mica.py:1` |  |
| error gradients | ADMITTED | both | genome:develop_repair | `greg/cognition/genomes/developmental.py:1271`<br>`greg/cognition/genomes/library.py:97` |  |
| distributed repair | ADMITTED | both | genome:develop_repair, mica_lab | `greg/cognition/genomes/developmental.py:1271`<br>`greg/cognition/genomes/library.py:97`<br>`developmental/mica.py:1` | NICHE on a simulated lattice; MICA PARITY with an adaptive central replanner; generalized repair not replicated (12-3 then 7-8) |
| differentiation | ABSENT | n/a |  |  | Search: grep -i 'differentiat' in greg/cognition/genomes/developmental.py and developmental/: no executable mechanism |
| tissue/organ formation | INTEGRATED | both | genesis | `greg/genesis.py:1`<br>`greg/cognition/compiler.py:44` | Precursors: genome:develop_repair. |
| topology change | ADMITTED | both | genome:develop_constraint_release, genome:collective_physarum | `greg/cognition/genomes/developmental.py:1343`<br>`greg/cognition/genomes/library.py:97`<br>`greg/cognition/genomes/collective.py:3084` |  |
| alternative-path recovery | ADMITTED | both | genome:develop_repair, mica_lab | `greg/cognition/genomes/developmental.py:1271`<br>`greg/cognition/genomes/library.py:97`<br>`developmental/mica.py:1` |  |
| constraint-release experimentation | ADMITTED | both | genome:develop_constraint_release | `greg/cognition/genomes/developmental.py:1343`<br>`greg/cognition/genomes/library.py:97` |  |
| evolutionary recombination | ADMITTED | both | p8_evolution, genome:develop_constraint_release | `greg/cognition/evolution.py:1`<br>`docs/evidence/greg-protected-evolution/2026-10-16-cr-6/README.md`<br>`greg/cognition/genomes/developmental.py:1343` |  |
| capability formation | EXERCISED | both | genesis, genesis_live_function | `greg/genesis.py:1`<br>`greg/cognition/compiler.py:44`<br>`tests/evidence/greg-product/genesis-live-claude-code.json` |  |
| developmental lineage | BENCHMARKED | both | p8_evolution | `greg/cognition/evolution.py:1`<br>`docs/evidence/greg-protected-evolution/2026-10-16-cr-6/README.md` | P8 lineage records and freezes |
| unscripted but bounded structural search | ADMITTED | both | genome:develop_constraint_release | `greg/cognition/genomes/developmental.py:1343`<br>`greg/cognition/genomes/library.py:97` |  |
| computational target fields | ADMITTED | both | mica_lab, genome:develop_repair | `developmental/mica.py:1`<br>`git:0067be6:docs/evidence/greg-developmental-sweep/2026-10-14/README.md:15`<br>`greg/cognition/genomes/developmental.py:1271` |  |
| cellular automata | ABSENT | n/a |  |  | Search: grep -i 'cellular automat' in greg/ and developmental/: lattice rules in develop_repair only, no CA family Precursors: genome:develop_repair. |
| graph diffusion | ABSENT | n/a |  |  | Search: grep -i 'diffusion' in greg/cognition and developmental/: no graph-diffusion family; cross_substrate backcast proposes one Precursors: mica_lab. |
| evolutionary topology search | ADMITTED | both | genome:develop_constraint_release | `greg/cognition/genomes/developmental.py:1343`<br>`greg/cognition/genomes/library.py:97` |  |
| simulated repair | ADMITTED | both | genome:develop_repair | `greg/cognition/genomes/developmental.py:1271`<br>`greg/cognition/genomes/library.py:97` |  |
| alternative structural pathways | ADMITTED | both | genome:develop_constraint_release, mica_lab | `greg/cognition/genomes/developmental.py:1343`<br>`greg/cognition/genomes/library.py:97`<br>`developmental/mica.py:1` |  |

## Layer 5: META-INTELLIGENCE / INSTITUTIONAL COLLECTIVE COGNITION

| Requirement | Status | Lineage | Mechanisms | Evidence | Note / search |
|---|---|---|---|---|---|
| observe discrepancy -> characterize geometry -> decompose epistemic requirements -> uncertainty -> consequence class | INTEGRATED | both | compiler, geometry | `greg/cognition/compiler.py:1233`<br>`greg/cognition/cortex.py:158`<br>`greg/cognition/compiler.py:59` |  |
| recruit candidates -> compose complementary intelligences | BENCHMARKED | both | compiler, composition | `greg/cognition/compiler.py:1233`<br>`greg/cognition/cortex.py:158`<br>`greg/cognition/composition.py:509` |  |
| preserve independent first-pass outputs | INTEGRATED | both | metaconsensus | `greg/cognition/cortex.py:287`<br>`greg/cognition/verification.py:391` |  |
| inhibit weak routes | INTEGRATED | both | compiler, settlement | `greg/cognition/compiler.py:38`<br>`greg/cognition/compiler.py:1233`<br>`greg/cognition/cortex.py:158` |  |
| preserve dissent | INTEGRATED | both | receipt, metaconsensus | `greg/cognition/compiler.py:1242`<br>`greg/cognition/contracts.py:363`<br>`greg/cognition/verification.py:391` |  |
| select evaluators -> produce typed evidence | BENCHMARKED | both | verifier, receipt | `greg/cognition/verification.py:1`<br>`tests/evidence/cortex-mutants-2026-10-01`<br>`greg/cognition/compiler.py:1242` |  |
| compare alternatives | INTEGRATED | both | compiler | `greg/cognition/compiler.py:1233`<br>`greg/cognition/cortex.py:158` |  |
| request authority where required -> act through existing Gate | EXERCISED | both | compiler, organ:cognition.cortex.optimization.cpsat | `greg/cognition/compiler.py:17`<br>`greg/cognition/compiler.py:1233`<br>`greg/cognition/cortex.py:158` |  |
| observe real outcome -> attribute credit and error -> update competence | INTEGRATED | both | settlement, calibration | `greg/cognition/settlement.py:1`<br>`greg/cognition/compiler.py:1190`<br>`greg/cli.py:108` | settlement replays receipts and appraisals; real-world outcomes settled only in the cortex rehearsal (test key) |
| detect residual gap -> build/acquire -> test independently -> add to repertoire | INTEGRATED | both | genesis | `greg/genesis.py:1`<br>`greg/cognition/compiler.py:44` |  |
| machine-readable ProblemGeometry (section 9) | INTEGRATED | both | geometry | `greg/cognition/compiler.py:59` |  |
| epistemic routing separate from authority routing (section 10) | INTEGRATED | both | compiler, receipt | `greg/cognition/compiler.py:1233`<br>`greg/cognition/cortex.py:158`<br>`greg/cognition/compiler.py:1242` |  |
| high consequence raises requirements; never routes to SMT (section 11) | INTEGRATED | both | operators | `greg/cognition/compiler.py:207`<br>`greg/cognition/compiler.py:206`<br>`greg/cognition/compiler.py:305` |  |
| cognitive receipts with the 29 section-12 fields | INTEGRATED | both | receipt | `greg/cognition/compiler.py:1242`<br>`greg/cognition/contracts.py:363` |  |
| Step A: P6 composition lift with a natural family | BENCHMARKED | both | composition, recipe:forecast_then_staff, recipe:track_then_staff | `greg/cognition/composition.py:509`<br>`docs/evidence/greg-composition-lift/2026-10-14-accounting/README.md`<br>`greg/cognition/composition.py:90` |  |
| Step B: one decisive P4 retest | BENCHMARKED | both | p4_conditional | `greg/cognition/conditional_competence.py:1`<br>`docs/evidence/greg-learned-routing/2026-10-08/README.md` |  |
| Step C: P8 protected evolutionary cognition | BENCHMARKED | both | p8_evolution, p8_routing_alt_179 | `greg/cognition/evolution.py:1`<br>`docs/evidence/greg-protected-evolution/2026-10-16-cr-6/README.md`<br>`git:0067be6:greg/cognition/evolution_routing.py:1` |  |
| Section 14: executable IntelligenceGenome library | ADMITTED | both |  | `greg/cognition/genomes/contract.py:1`<br>`greg/cognition/genomes/library.py:25`<br>`docs/evidence/greg-genome-admission/2026-10-16-v4/README.md` | 47 executable genomes on #158; 35 ADMITTED (DEFAULT or NICHE); #179 adds 4 operation families and an inventory |
| Section 15: admission rule with seven outcomes | BENCHMARKED | both |  | `greg/cognition/genomes/admission.py:1`<br>`docs/evidence/greg-genome-admission/2026-10-16-v4/README.md` | FRONTIER_HORIZON is a status the compiler excludes; no genome currently holds it |
| Section 16: Verified Polyintelligence Lift and its tracked metrics | BENCHMARKED | both | composition, vpl_metrics | `docs/evidence/greg-composition-lift/2026-10-14-accounting/README.md`<br>`greg/cognition/composition.py:509`<br>`docs/evidence/greg-composition-lift/2026-10-14-accounting/README.md` | VPL_LIFT recipes 6 of 7 on the index (F1, F2R, F4, F6, F7, F8; F5 NO_LIFT); natural 3 of 4 (F6, F7, F8); routing adds nothing within a family; every lift costs latency 1.5-5.2x; F7 NO_LIFT once flow_expansion_mcf is a constituent |
| Section 17: lawful asymmetric advantage compiler (generation, not only ranking) | INTEGRATED | both | foundry, advantage_179 | `foundry/lawful_leverage.py:1`<br>`git:0067be6:greg/cognition/advantage.py:1` |  |
| Section 18: eligibility gates before a vector objective | INTEGRATED | both | foundry | `foundry/lawful_leverage.py:1` |  |
| Section 19: Goal Gravity / Infinite Goal Chase | INTEGRATED | both | gravity, mission_cognition_ask_179 | `greg/gravity.py:1`<br>`tests/unit/test_greg_gravity.py`<br>`git:0067be6:greg/missions.py:1061` |  |
| Section 20: every closed cycle leaves a durable asset | INTEGRATED | both | foundry, gravity | `foundry/lawful_leverage.py:1`<br>`greg/gravity.py:1`<br>`tests/unit/test_greg_gravity.py` |  |
| Section 21: resilience and evidence-gated antifragility | IMPLEMENTED | both | resilience | `greg/resilience.py:1` |  |
| Section 22: truthful immune system (drift, scope, privilege pressure, quarantine, recoupling, decoupling) | ADMITTED | both | resilience, genome:collective_immune | `greg/resilience.py:1`<br>`greg/cognition/genomes/collective.py:3158`<br>`greg/cognition/genomes/library.py:97` | Precursors: genesis. |
| Section 23: community intelligence through typed evidence | IMPLEMENTED | both | community | `greg/dataplane.py:87` |  |
| Section 24: generate new intelligence when necessary | INTEGRATED | both | genesis | `greg/genesis.py:1`<br>`greg/cognition/compiler.py:44` | the recorded live Genesis run formed a non-cognition function; cognition deficits are covered by tests only Precursors: genesis_live_function. |
| Section 25: BUILDABLE_NOW / EXPERIMENTAL_NOW / FRONTIER_RESEARCH / SCIENCE_FICTION_DESCENDANT | IMPLEMENTED | #179 | path_frontier, genome_library_179 | `greg/path.json:1791`<br>`git:0067be6:greg/cognition/genome_library.py:1` |  (#158: INVENTORIED; #179: IMPLEMENTED) |
| Section 27: VPL and VEPMC kept distinct | IMPLEMENTED | both | mind_status | `tests/evidence/greg-product/product-path-summary.json`<br>`scripts/mind_status.py:1` | VEPMC row missing mac_body: VEPMC = 0 |
| Section 31.17 reality ledger | IMPLEMENTED | both | mind_status, worlds | `scripts/mind_status.py:1`<br>`greg/cognition/worlds.py:8` |  |
| Section 2: meniscus as the verified-envelope frontier with margins | INTEGRATED | both | foundry | `foundry/lawful_leverage.py:1` | harm ceilings and margins in the Foundry hard filter |
| Section 2: impermeable shield as layered prevention/recovery | BENCHMARKED | both | resilience, verifier | `greg/resilience.py:1`<br>`greg/cognition/verification.py:1`<br>`tests/evidence/cortex-mutants-2026-10-01` |  |
| Section 2: lawful deterrence only | INTEGRATED | both | organ:cognition.cortex.deterrence.accountability, protection | `cortex/organs/deterrence.py:1`<br>`greg/cognition/catalog.py:60`<br>`greg/cognition/protection.py:1` |  |
| Section 2: victim protection first-class | IMPLEMENTED | both | protection | `greg/cognition/protection.py:1` |  |
| Section 2: collateral harm as a vector, hard constraints first | INTEGRATED | both | protection, foundry | `greg/cognition/protection.py:1`<br>`foundry/lawful_leverage.py:1` |  |

## Frontier destinations

All are preserved; none is claimed to exist.

| Destination | Buildability | Nearest falsifiable precursor |
|---|---|---|
| `generalized_morphogenetic_repair`: a function lost to unseen damage recovers through a materially different organization, across domains, without scripted restoration and under preserved authority | EXPERIMENTAL_NOW | measured twice (v1 seeds 1000-1029: 12-3 under an unreliable controller; v2 seeds 1100-1129: 7-8, not replicated); next: a predeclared unreliable-controller-only admission with a larger held-out set |
| `automatic_invention_of_intelligence_families`: when no registered intelligence solves a residual geometry, GREG searches, composes, mutates and generates a bounded candidate intelligence, evaluates it against a sealed held-out benchmark and registers it only if it wins | EXPERIMENTAL_NOW | a second P8 cycle on a different target with fresh held-out data |
| `substrate_adaptive_cognition`: the same typed cognition contracts execute on different substrates (CPU bodies, GPU, remote solver services, and later analog or quantum devices when mature) with verified equivalence | FRONTIER_RESEARCH | run the frozen cognition suite on a second enrolled machine and compare receipts |
| `reliable_multi_body_agency`: one GREG across several bodies with one ledger and one authority path, surviving the loss of a body | BUILDABLE_NOW | enroll a second body in a test environment and kill -9 the first one mid-mission |
| `advanced_robotic_embodiment`: bounded physical actuation under the Gate, with the same receipts and refusal as digital acts | FRONTIER_RESEARCH | a simulated actuator contract whose Gate refusals are tested |
| `persistent_spatial_ecology`: a persistent, lawful, consented model of the physical spaces that matter to missions, updated from devices and public data | EXPERIMENTAL_NOW | a typed adapter from the HUD repository into the data plane with freshness checks |
| `large_scale_human_machine_coordination`: human and AI participants coordinate through typed contracts, evidence and settlement at institutional scale | BUILDABLE_NOW | one human-work ask through greg.asks with an observed deliverable |
| `jarvis_environmental_awareness`: GREG notices relevant changes early, keeps dormant goals, prepares lawful options and asks only the minimum decision | EXPERIMENTAL_NOW | run Goal Gravity turns on retained situations and measure founder-accepted asks per turn |
| `self_financed_research_infrastructure`: verified surplus funds research programs that produce verified capability | FRONTIER_RESEARCH | the N3 first business whole loop |
| `robust_unscripted_organ_formation`: a recurring verified deficit yields a bounded, persistent specialist organ (contracts, state, tests, lifecycle, shutdown) assembled from validated components without a scripted blueprint, robustly across unrelated deficits, and retained only while it beats simpler baselines | EXPERIMENTAL_NOW | freeze a set of recurring deficits from the body's ledger and compare local assembly from validated capabilities (develop_repair's local rules lifted to capability topology) with greg.genesis scripted acquisition on held-out deficits |
| `cross_substrate_developmental_compilation`: one developmental specification (target function, local rules, signals, repair objective) compiles to materially different substrates and restores the same verified target function on each, with no per-substrate re-implementation | EXPERIMENTAL_NOW | state TARGET_FORM_001's transport target once, compile it to the lattice (develop_repair) and to a graph-diffusion substrate, and compare restored function on the same held-out damage seeds |
| `open_ended_cognitive_organization_generation`: GREG reliably and open-endedly generates entirely new cognitive organizations (topologies of methods, communication and resource rules) found in no library, each admitted only when it beats the strongest existing organization on its geometry and replicates independently | FRONTIER_RESEARCH | a first P9 cycle: recombine admitted genomes' operators under altered rules (develop_constraint_release's search) on a frozen task and compare with the best library composition on held-out seeds |
| `substrate_independent_developmental_intelligence`: extremely general substrate-independent developmental intelligence with the reliability, generality, embodiment flexibility, and autonomy implied by the strongest Levin-inspired vision (the founder's words); preserved as a descendant, never claimed to exist | SCIENCE_FICTION_DESCENDANT | none of its own; the nearest falsifiable step is cross_substrate_developmental_compilation's lattice-versus-graph experiment |
| `cortex.meta.global_workspace`: module competition and selective broadcast | EXPERIMENTAL_NOW | a broadcast-arbitration arm against the compiler's static ranking on a frozen multi-geometry suite |
| `cortex.meta.active_inference`: generative-model policy selection | EXPERIMENTAL_NOW | expected-free-energy policy vs greedy EIG (info_experiment) on its own held-out admission geometry |

## Prioritized build list

buildable now with no RULE change, no attachment, no data-rights clearance, no network evasion and no spending; ranked by information value and by relevance to GREG's real capability deficits.

### 1. `B01.stress_gate_history_audit`

- **Closes:** 31.7, directive-2026-10-21 section 3
- **Scope:** Independently re-derive every recorded P8 adversarial-gate decision (cycles 1-6) under the old worsened() and the new stress_worsened(). The cycle records keep only per-set means (e.g. cycle-cr-6.json adversarial: {lean, fewval}: incumbent/candidate means), so the audit must regenerate item-level stress outputs from each cycle's seeded stress sets, frozen configuration and source commit in a clean checkout (stress sets are not held-out data). Finite recorded means imply zero wrong answers in both arms, so the only route to a changed decision is the new both-answered restriction when abstentions occurred; report that case explicitly. Cover paired alignment, equal/fewer errors, empty sets, NaN/inf/malformed values, and the documented rule text. Where regeneration is impossible, record UNRESOLVED, never equivalent.
- **Files:** `greg/cognition/evolution.py`, `scripts/audit_stress_gate_history.py (new)`, `tests/unit/test_stress_gate_history.py (new)`, `docs/evidence/greg-protected-evolution/2026-10-21-stress-gate-audit/ (new)`
- **Acceptance test:** For each cycle, a row {cycle, regenerated: bool, old_decision, new_decision, wrong_counts, both_answered_n}; the test fails if any row claims equivalence without item-level outputs, and passes hostile cases (3 vs 2 wrong; equal wrong with worse answered mean; empty set; NaN).
- **Falsifier:** Any recorded cycle decision differs under the new function, or a cycle cannot be regenerated (then the 'no recorded decision changes' claim in b7b1ed9 is unsupported for it).
- **Effort:** S-M (0.5-1 day; single core)
- **Evidence kind:** re-derivation of recorded synthetic stress sets

### 2. `B02.all_lineage_data_exposure_ledger`

- **Closes:** 31.17, directive-2026-10-21 section 2
- **Scope:** One machine-readable ledger of every seed range, data file (sha256), split, pilot, admission, P6 family, P8 cycle and test fixture across #158's tree and PR #179 (read through git show), with the generator code digest that produced each item and whether its outcomes were looked at. Flags: overlapping seeds, the same data file under different seeds (the forecast_quantile/P8 M4 erratum pattern), and the same generator with different seeds (not independent by seed number alone). Read-only; changes no split.
- **Files:** `scripts/data_exposure_ledger.py (new)`, `tests/unit/test_data_exposure_ledger.py (new)`, `docs/evidence/greg-data-exposure/2026-10-21/ledger.json (new)`
- **Acceptance test:** Every freeze.json, PREREGISTRATION.md seed declaration, pilot record and admission run in both lineages is parsed (count reported and checked against a glob); #179's seeds 1001-1040, 2001-2040, 3001-3040, 5001-5040 and #158's 1000-1329, 7000-9199 appear; the successor pilot's review seeds are shown unused.
- **Falsifier:** A seed or data item later found used by a committed artifact but missing from the ledger; or two evaluations sharing a data file digest reported as independent.
- **Effort:** M (1 day)
- **Evidence kind:** audit of repository artifacts

### 3. `B03.successor_immune_pilot`

- **Closes:** 31.7, directive-2026-10-21 sections 1-2 (authorized option 2)
- **Scope:** New target identity (e.g. immune_detect_narrow) with explicit lineage to the cycle-7 NOT_VIABLE pilot; the narrowed space is justified causally (the frozen search chose high alarm_fraction configurations that win paired items but add 4-6 false-alarm violations per 540) and its bounds are declared before any new outcome; fresh unused review seeds from the exposure ledger; arms: incumbent, random restart, the strongest simple baseline, and fixed configurations informed by cycle 2's record (labelled as informed); predeclared resource limits, stopping, viability rule, selection rule and multiple-attempt accounting. Shared RULE unchanged. If VIABLE, freeze the trusted implementation and run the confirmatory cycle once; otherwise preserve NOT_VIABLE.
- **Files:** `greg/cognition/evolution.py`, `docs/evidence/greg-protected-evolution/2026-10-21-immune-8/ (new: PREREGISTRATION.md, pilot/)`, `tests/unit/test_greg_protected_evolution.py`
- **Acceptance test:** Pilot rules committed before any pilot instance exists (commit order checked by test); verdict computed by the declared rule; reserved cycle-7 seeds untouched.
- **Falsifier:** Pilot NOT_VIABLE (best mean simulated P(RETAIN) below the declared threshold), or a confirmatory REJECT; either is recorded as the result.
- **Effort:** M-L (2-3 days; depends on B01 and B02)
- **Evidence kind:** synthetic (seeded negative-selection instances)

### 4. `B04.evidence_claim_reconciliation_family`

- **Closes:** 31.5, 31.2, directive-2026-10-21 section 6 (evidence reconciliation)
- **Scope:** A consequence-inert cognition family drawn from GREG's own operating need: check every numeric claim in evidence READMEs (W-L counts, p-values, percentages, statuses) against the results file it cites, and flag mismatches. Native competitor arms: no-check baseline, regex-extraction-plus-exact-recomputation genome, and (when a local model exists) the semantic organ; composition semantic extract -> exact recompute is the P6 candidate.
- **Files:** `greg/cognition/genomes/evidence_check.py (new)`, `greg/cognition/genomes/library.py`, `greg/cognition/worlds.py`, `cortex/evaluation/claim_reconciliation/ (new prereg, freeze, run)`, `tests/unit/test_genomes_evidence_check.py (new)`
- **Acceptance test:** Pre-registered admission on held-out READMEs (split by directory, decided before reading); recall on the natural positives (claims later corrected by the 26 READMEs that carry errata quoting the original wording) and false-flag rate on claims the recomputation confirms.
- **Falsifier:** The genome misses errata-recorded misstatements at a rate not better than the baseline, or false-flags exceed the declared ceiling.
- **Effort:** M-L (2 days)
- **Evidence kind:** NATURAL: the README claim population of both lineages and the errata as labelled positives; truth by exact recomputation from the cited JSON. Any injected corruptions are SYNTHETIC and reported separately.

### 5. `B05.repository_dependency_control_points`

- **Closes:** 31.5, 31.8, directive-2026-10-21 section 6 (dependency analysis, organ coordination)
- **Scope:** Natural-input problem family: the Python import graph of this repository at K historical commits (git show, no network). Questions: minimum vertex/edge cut between the mission engine and each organ adapter or evidence writer (single points of failure), and the longest dependency chain. Arms: flow_maxflow and critical_path genomes, degree-centrality heuristic baseline, exact networkx truth; P6 candidate: bottleneck detection -> min_cost_flow allocation of a hardening budget.
- **Files:** `cortex/evaluation/dependency_family/ (new: build.py, prereg, freeze, run)`, `greg/cognition/worlds.py`, `tests/unit/test_dependency_family.py (new)`
- **Acceptance test:** Instances built only from commits declared before the run; truth independently computed; VPL accounting (false answers, latency, cost) against the strongest single genome.
- **Falsifier:** Composition ties or loses to flow_maxflow alone (the F7 pattern), or the degree heuristic matches the exact cut on most instances.
- **Effort:** M (1-1.5 days)
- **Evidence kind:** NATURAL inputs (GREG's own repository history), MATHEMATICAL truth computed from each instance; the hardening-budget values are SYNTHETIC unless taken from recorded incident counts.

### 6. `B06.exercised_label_and_lineage_rows`

- **Closes:** 31.17, 31.15
- **Scope:** Extend scripts/mind_status.py with an EXERCISED projection read from retained mission ledgers (cognition receipts with method, version, mission id, key provenance) and lineage-tagged rows for #179's operation-family admissions read from a pinned commit, without merging code or changing routing. Today only the cortex rehearsal (test key) exercises cognition.cortex, extraction.schedule and optimization.cpsat.
- **Files:** `scripts/mind_status.py`, `tests/unit/test_mind_status.py`
- **Acceptance test:** mind_status reports the three exercised organs with the rehearsal ledger as evidence and marks the key as non-founder; #179 rows appear with source commit 0067be6 and never alter the compiler's routing (existing compiler-consistency test still passes).
- **Falsifier:** A mission receipt the ledger scan misses (checked against a grep of retained ledgers), or #179 rows changing a routed status.
- **Effort:** S-M (0.5-1 day)
- **Evidence kind:** n/a (records)

### 7. `B07.one_step_weighted_vote_genome`

- **Closes:** 31.8, L2.human_collective
- **Scope:** The acquisition target #179's sparse-crowd test named: the one-step agreement-weighted (Nitzan-Paroush) vote as a Layer-2 genome; admit against majority vote and Dawid-Skene on fresh seeds on both dense and sparse crowds.
- **Files:** `greg/cognition/genomes/collective.py`, `greg/cognition/genomes/admission.py`, `greg/cognition/worlds.py`, `tests/unit/test_genomes_collective.py`
- **Acceptance test:** Pre-registered admission on unused seeds from the exposure ledger; v1 status rule unchanged.
- **Falsifier:** It does not beat majority vote on the sparse geometry, or it ties Dawid-Skene on dense crowds and loses on neither (then COMPOSITION_ONLY/EXPERIMENTAL).
- **Effort:** S-M (1 day)
- **Evidence kind:** SYNTHETIC (simulated crowds); the oracle gap 0.197 vs 0.338 states the headroom

### 8. `B08.multistart_lbfgsb_genome`

- **Closes:** 31.2, L3.opt.nonlinear, L3.opt.convex
- **Scope:** Commodity SciPy multistart L-BFGS-B as the nonlinear/smooth black-box genome (#179 measured it beating PSO 32-7 post hoc and DE 26-8); pre-registered admission against PSO and DE, plus a noisy/discontinuous objective menu where gradient-free methods may regain ground.
- **Files:** `greg/cognition/genomes/competitors.py`, `greg/cognition/genomes/admission.py`, `greg/cognition/worlds.py`, `tests/unit/test_genomes_competitors.py`
- **Acceptance test:** Admission on fresh seeds with the evaluation budget equalised in function evaluations.
- **Falsifier:** It loses to PSO or DE on the declared noisy/discontinuous menu (then NICHE for smooth objectives only).
- **Effort:** S-M (1 day)
- **Evidence kind:** MATHEMATICAL instances (declared objectives)

### 9. `B09.operator_effect_ablation`

- **Closes:** 31.3, section 6
- **Scope:** Measure whether each of the 15 typed operators changes a compiled answer, method choice or requirement on a frozen set of compiler requests (existing test geometries plus the P6 families), against the compiler with that operator removed; operators that never alter an answer are recorded as such (the directive: recruit them when the geometry indicates they can alter the answer).
- **Files:** `cortex/evaluation/operator_ablation/ (new)`, `greg/cognition/compiler.py`, `tests/unit/test_greg_competency_compiler.py`
- **Acceptance test:** Per operator: count of requests where its removal changes selected method, requirements or result; frozen before running.
- **Falsifier:** An operator with zero effect on every request in its declared signature, which then becomes a rule annotation rather than an operator.
- **Effort:** M (1 day)
- **Evidence kind:** mixed: P6 natural families (F6-F8 inputs) and synthetic compiler requests, labelled per request

### 10. `B10.dynamic_damage_coordinator_loss`

- **Closes:** 31.9, L4.distributed_repair, frontier.generalized_morphogenetic_repair
- **Scope:** The next Layer-4 test both lineages name: damage arriving during transport and loss of the central coordinator, against a central replanner that replans every k ticks; develop_repair and MICA arms on the same seeds; pre-registered, simulated world.
- **Files:** `greg/cognition/genomes/developmental.py`, `cortex/evaluation/developmental_dynamic/ (new)`, `tests/unit/test_genomes_developmental.py`
- **Acceptance test:** Pre-registered sign test on delivered throughput across unseen dynamic-damage seeds; ties reported as PARITY.
- **Falsifier:** PARITY or loss against the periodic replanner (then the distributed mechanism has no measured advantage beyond coordinator independence).
- **Effort:** M (1-2 days)
- **Evidence kind:** SYNTHETIC (simulated lattices)

### 11. `B11.ci_sharding_family`

- **Closes:** 31.5, directive-2026-10-21 section 6 (planning, resource allocation)
- **Scope:** Record per-test durations once from a local single-core run of this repository's suite (consequence-inert), then build makespan instances (k CI workers) from them; arms: CP-SAT (the exercised organ), LPT greedy practitioner, knapsack/BnB-based bin assignment; truth: proven CP-SAT optimum. Relevant to the real CI limit raised to 45 minutes.
- **Files:** `cortex/evaluation/ci_sharding/ (new)`, `cortex/evaluation/data/ci_durations.json.gz (new, recorded locally)`, `greg/cognition/worlds.py`
- **Acceptance test:** Pre-registered: instances drawn from recorded durations with k declared; certificate of optimality per item.
- **Falsifier:** LPT within 1% of optimal on nearly every instance (no lift worth the latency).
- **Effort:** M (1 day plus one full-suite recording run, which exceeds light compute and must be scheduled)
- **Evidence kind:** NATURAL inputs (GREG's own test durations), MATHEMATICAL truth

### 12. `B12.centrality_community_genomes`

- **Closes:** 31.2, L3.graph.centrality, L3.graph.community_topology
- **Scope:** NetworkX betweenness/approximate centrality and modularity community detection as genomes, admitted only where decision-relevant: on SNDlib topologies and B05's import graphs, does centrality predict the exact min-cut control points better than degree?
- **Files:** `greg/cognition/genomes/graph_or.py`, `greg/cognition/genomes/admission.py`, `greg/cognition/worlds.py`
- **Acceptance test:** Pre-registered admission against degree and against the exact cut.
- **Falsifier:** Centrality never beats degree at identifying exact cut vertices (then REJECTED: not decision-relevant).
- **Effort:** S-M (1 day)
- **Evidence kind:** NATURAL inputs (SNDlib, repository graphs), MATHEMATICAL truth

### Section 6 candidates considered and set aside

- forecasting GREG's own commit or evidence arrivals: 28 active commit days (2026-07-19 to 2026-10-21): too short for a held-out forecasting family.
- organ coordination over greg/path.json nodes: 11 nodes: too few instances for a held-out family.
- recovery from retained mission ledgers: a handful of recovery episodes in tests/evidence/greg-usable/retained-state; record and wait for more body history.

## Seed-genome requirement crosswalk

Each of the 122 crosswalk items in `docs/cortex/SEED_GENOME_REQUIREMENTS.json` is mapped to coverage items. Its status is the weakest status among them. Counts: ABSENT 3, INVENTORIED 1, IMPLEMENTED 13, INTEGRATED 36, BENCHMARKED 24, ADMITTED 45.

| Source id | Requirement | Coverage items | Status |
|---|---|---|---|
| A00 | Governing competency-selection thesis and biology-to-mechanism rule | L5.problem_geometry | INTEGRATED |
| A01 | Five scales, selective recruitment | L5.loop.recruit_compose | BENCHMARKED |
| A02 | Microintelligence, ternary state, cheap local checks | L1.deterministic_reflexes | ADMITTED |
| A03 | Competency cells, light cone, control, online learning, active inference | L1.eval.bandits, L5.loop.observe_outcome_credit | INTEGRATED |
| A04 | Broad specialized repertoire beyond the initial organs | L5.genome_library | ADMITTED |
| A04.1 | Semantic reasoning and replaceable models | L3.semantic | INTEGRATED |
| A05 | Fermi and broader estimation methods | L3.fermi | BENCHMARKED |
| A06 | Probabilistic intelligence | L3.bayesian | ADMITTED |
| A07 | Causal intelligence and consequence memory | L3.causal | ADMITTED |
| A08 | Formal validity, empirical validity, authority | L5.epistemic_vs_authority | INTEGRATED |
| A09 | Optimization, operations research, meaningful solver states | L3.or.network_optimization, L3.con.cpsat | ADMITTED |
| A10 | Graph and search | L3.graph.shortest_path, L3.search.bnb | ADMITTED |
| A11 | Continuous control intelligence | L3.ctl.mpc | ADMITTED |
| A12 | Information acquisition and VOI | L3.info.voi | ADMITTED |
| A13 | Simulation/counterfactual intelligence | L3.cf.decisions_policies | BENCHMARKED |
| A14 | Games and mechanism design | L3.game.strategic, L3.mechanism_design | ADMITTED |
| A15 | Statistical, structural, institutional patterns | L1.anomaly_response | ADMITTED |
| A16 | Program synthesis and algorithm discovery | L3.evo.program_mutation | ADMITTED |
| A17 | Collective/developmental portfolio and hive | L2.hive_quorum | ADMITTED |
| A18 | Ant/stigmergy | L2.ant_stigmergy | ADMITTED |
| A19 | Flock/PSO, with physical/numerical distinction | L2.flock | ADMITTED |
| A20 | Slime-mold adaptive networks | L2.slime_mold | ADMITTED |
| A21 | Immune containment and tolerance | L2.immune | ADMITTED |
| A22 | Ecological diversity and non-correlated methods | L2.ecological | INTEGRATED |
| A23 | Cognitive allocation market | L2.market | ADMITTED |
| A24 | Evolutionary search | L3.evo.es, L5.p8_protected_evolution | BENCHMARKED |
| A25 | Human collective intelligence | L2.human_collective | ADMITTED |
| A26 | Shared workspace/ensemble coordination | L5.loop.independent_first_pass | INTEGRATED |
| A27 | Unscripted functional morphogenesis | L4.organ_formation | INTEGRATED |
| A28 | Constraint-release laboratory | L4.constraint_release | ADMITTED |
| A29 | Associative microcircuits as research | L1.associative_microcircuits | INVENTORIED |
| A30 | Metacognitive institutional loop | L5.loop.observe_outcome_credit | INTEGRATED |
| A31 | Epistemic type system | L5.cognitive_receipts | INTEGRATED |
| A32 | Formalization coverage and WORLD_UNVERIFIED | L5.high_risk_rule | INTEGRATED |
| A33 | Typed proof-carrying cognition | L5.cognitive_receipts | INTEGRATED |
| A34 | Cognitive Spider-Web | L5.loop.recruit_compose | BENCHMARKED |
| A35 | Algorithm-portfolio precedent | L5.genome_library | ADMITTED |
| A36 | Failure-diverse cognition | L5.loop.dissent | INTEGRATED |
| A37 | Competency characterization harness | L5.admission_rule | BENCHMARKED |
| A38 | Cognitive metabolism and attention | L5.loop.recruit_compose | BENCHMARKED |
| A39 | Outcome-based credit and attribution limits | L5.loop.observe_outcome_credit | INTEGRATED |
| A40 | Offline consolidation | L5.p8_protected_evolution | BENCHMARKED |
| A41 | Keep/reject audit reconciled | L5.admission_rule | BENCHMARKED |
| A42 | Challenge-resistant proof without compelled acceptance | L5.loop.evaluators_typed_evidence | BENCHMARKED |
| A43 | Multidimensional harm | L5.interp.collateral_vector | INTEGRATED |
| A44 | Metaphors compiled to mechanisms | L5.reality_ledger | IMPLEMENTED |
| A45 | Canonical architecture without destructive erasure | L5.epistemic_vs_authority | INTEGRATED |
| A46 | Buildable repertoire without implementation claims | L5.buildability | IMPLEMENTED |
| A47 | Buildable experiments need comparative proof | L5.admission_rule | BENCHMARKED |
| A48 | Frontier capability preservation | L5.buildability | IMPLEMENTED |
| A49 | Future substrates and model-family distinctions | L5.buildability | IMPLEMENTED |
| A50 | Global VEPMC and subordinate cognition bottleneck | L5.metrics_distinct | IMPLEMENTED |
| A51 | C1-C8 backcast preserved and reconciled | L5.buildability | IMPLEMENTED |
| A52 | Complete problem-to-outcome cycle | L5.loop.observe_to_geometry, L5.loop.observe_outcome_credit | INTEGRATED |
| A53 | Seed scope with full abstraction horizon | L5.genome_library | ADMITTED |
| B00 | Revised cortex thesis and recovered context | L5.problem_geometry | INTEGRATED |
| B01 | Executable genomes, source reconstruction, missing cortex | L5.genome_library | ADMITTED |
| B02 | Epistemic finality correction | L5.epistemic_vs_authority | INTEGRATED |
| B03 | Primitive intelligence | L1.deterministic_reflexes | ADMITTED |
| B04 | Bounded cells and CognitiveCapability profile | L5.genome_library | ADMITTED |
| B05 | Broad specialized families | L5.genome_library | ADMITTED |
| B06 | Exact symbolic intelligence | L3.con.exact_combinatorial | ADMITTED |
| B07 | Formal logical intelligence | L3.con.smt, L3.formal.model_checking | BENCHMARKED |
| B08 | Operations research | L3.or.queueing, L3.or.network_optimization | ADMITTED |
| B09 | Graph intelligence and structural analysis | L3.graph.mincut_maxflow, L3.graph.centrality | ABSENT |
| B10 | Fermi/estimation | L3.fermi | BENCHMARKED |
| B11 | Probabilistic intelligence | L3.bayesian | ADMITTED |
| B12 | Causal intelligence | L3.causal | ADMITTED |
| B13 | Search and valid transition models | L3.search.astar, L3.search.mcts | ABSENT |
| B14 | Control and stability | L3.ctl.feedback, L3.ctl.robust | ABSENT |
| B15 | Sequential decisions and active inference | L3.search.tree | ADMITTED |
| B16 | Pattern and mechanism recognition | L1.anomaly_response | ADMITTED |
| B17 | Information intelligence | L3.info.information_gain | ADMITTED |
| B18 | Games and incentive design | L3.game.strategic, L3.mechanism_design | ADMITTED |
| B19 | Independent adversarial intelligence | L3.adv.counterexamples | ADMITTED |
| B20 | Simulation with reality-validation limits | L3.sim.scenario | BENCHMARKED |
| B21 | Collective mechanisms as coordination topologies | L2.hive_quorum, L2.ant_stigmergy | ADMITTED |
| B22 | Ensembles, quorum, stigmergy, ecology, allocation | L2.ecological, L2.market | INTEGRATED |
| B23 | Evolutionary intelligence | L3.evo.es | BENCHMARKED |
| B24 | Program synthesis/Capability Genesis | L5.new_intelligence | INTEGRATED |
| B25 | Constraint-release discovery | L4.constraint_release | ADMITTED |
| B26 | Morphogenetic recovery | L4.distributed_repair | ADMITTED |
| B27 | Meta-intelligence | L5.loop.recruit_compose | BENCHMARKED |
| B28 | Mental models as transformation operators | L5.high_risk_rule | INTEGRATED |
| B29 | Rich ProblemGeometry | L5.problem_geometry | INTEGRATED |
| B30 | Jurisdiction-aware metaconsensus | L5.loop.dissent | INTEGRATED |
| B31 | Unified cortex topology | L5.loop.recruit_compose | BENCHMARKED |
| B32 | Eligibility, routing, typed proof | L5.epistemic_vs_authority | INTEGRATED |
| B33 | Geometry-specific settlement | L5.loop.observe_outcome_credit | INTEGRATED |
| B34 | Expanded CognitiveReceipt | L5.cognitive_receipts | INTEGRATED |
| B35 | Proof-bearing accountability | L5.cognitive_receipts | INTEGRATED |
| B36 | Lawful deterrence geometry | L5.interp.deterrence | INTEGRATED |
| B37 | Victim-protection geometry | L5.interp.victim_protection | IMPLEMENTED |
| B38 | Harm vector and hard constraints | L5.interp.collateral_vector | INTEGRATED |
| B39 | Constrained leverage objective without false precision | L5.asymmetric_objective | INTEGRATED |
| B40 | Buildable mechanism inventory | L5.genome_library | ADMITTED |
| B41 | Metaphor translation | L5.reality_ledger | IMPLEMENTED |
| B42 | Avoid redundant animal-branded systems | L5.genome_library | ADMITTED |
| B43 | Experimental methods retained with proof gates | L5.admission_rule | BENCHMARKED |
| B44 | Frontier scope retained | L5.buildability | IMPLEMENTED |
| B45 | Science-fiction destination retained without present claims | L5.buildability | IMPLEMENTED |
| B46 | Levin inspiration with epistemic limits | L4.distributed_repair | ADMITTED |
| B47 | Competency Compiler | L5.loop.recruit_compose | BENCHMARKED |
| B48 | Final five layers | L5.genome_library | ADMITTED |
| B49 | Operational SBM and subordinate development | L5.metrics_distinct | IMPLEMENTED |
| B50 | P1 cognitive contract | L5.problem_geometry | INTEGRATED |
| B51 | P2 four-class seed and independent verifier | L5.loop.evaluators_typed_evidence | BENCHMARKED |
| B52 | P3 cognitive proof ledger | L5.cognitive_receipts | INTEGRATED |
| B53 | P4 cognitive Spider-Web | L5.p4_retest | BENCHMARKED |
| B54 | P5 demand-led expansion | L5.genome_library | ADMITTED |
| B55 | P6 heterogeneous tissues and measured lift | L5.p6_composition_gate | BENCHMARKED |
| B56 | P7 capability genesis | L5.new_intelligence | INTEGRATED |
| B57 | P8 evolutionary cognition | L5.p8_protected_evolution | BENCHMARKED |
| B58 | P9 constraint-release discovery | L4.constraint_release | ADMITTED |
| B59 | P10 functional morphogenesis | L4.distributed_repair | ADMITTED |
| B60 | P11 open ecology; competence never creates authority | L5.epistemic_vs_authority | INTEGRATED |
| B61 | P12 substrate-plural execution | L5.buildability | IMPLEMENTED |
| B62 | P13 poly-embodied institution | L5.buildability | IMPLEMENTED |
| B63 | Eight corrections to v0.1 | L5.high_risk_rule | INTEGRATED |
| B64 | Seed Genome pitch and full phenotype horizon | L5.genome_library | ADMITTED |
| BFIRST | Final proposed build list | L5.cognitive_receipts, L5.p6_composition_gate | INTEGRATED |
| BTEST | Decisive cross-geometry experiment | L5.p6_composition_gate | BENCHMARKED |

## Unavailable context

- Project sources outside the repository (raw ChatGPT conversations) were not inspected.
- Organ repositories (DALEOBANKS, WealthMachineIntelligence) were not inspected for cognition consumers. Section 31 item 15 records that no organ consumption is evidenced in this repository.
- PR #179 was read at `0067be6` through `git show` only, and none of its runs were re-executed. `mind_status` was run once, read-only, at the base commit.
