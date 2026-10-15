# Mind lineage reconciliation (Track B): one GREG Mind from PR #155 and PR #158

Decision source: `INTENT-20261014-MIND-LINEAGE-CONVERGENCE`, with the verbatim text in
`docs/intent/sources/MIND-LINEAGE-CONVERGENCE-2026-10-14-source.md`. This creates no runtime authority. It is
not founder authentication, and it does not merge, deploy, publish, spend, contact anyone or attach a
capability.

- **Branch:** `claude/greg-mind-lineage-convergence`.
- **Draft PR target:** the latest verified #155 head (`claude/greg-one-mind-converged`).
- **Machine-readable map:** `MIND-LINEAGE-RECONCILIATION-MAP-2026-10-14.json`, with one entry per file.
- **Source-location manifest:** `MIND-LINEAGE-SOURCE-MANIFEST-2026-10-14.json`, written by #158. This PR adds
  only the labelled `archival_copies` entry.

## 1. Lineages reconciled

| | commit (full) | role |
|---|---|---|
| common base | `92bc6e31e0baa8fd507833e0f272b4a5e532e4d3` | P4 v2 result |
| PR #155 head | `ef5f078013b549a51458dc9f6b5f34b324ea70b0` | 60 files changed since the base |
| PR #158 head | `202b932` (merged in this PR); earlier merges at `77b61a1` and `047549f352c74ac5f098ec04762b8095f44c9fde` | 154 files changed since the base |
| shared paths | 22 | 8 are frozen-path collisions |

Convergence commits:

- `2d1ddd3` merged #158 at `77b61a1`. Its message names `a832c73`; the actual parent is `77b61a1`, which is
  `a832c73` plus the graph_or review fix `99e6d83`.
- `49b2d58`, `8bbd3b8` and `6e62b59` are Track B work.
- `e21bb5b` merges #158 `047549f`.
- `8a43e70` records the institutional verifier run (PASS, bound to `ccd38a2`).
- A later merge brings #158 to `202b932`: the F8 (P6 v5) pre-registration, freeze, suite and data. F8's held-out
  arms had not run at merge time.

The eight collided frozen files are byte-identical at `a832c73`, `77b61a1` and `047549f`.

## 2. Context reconstruction (SOP section 3)

**Founder intent.** The founder directive reads: "I am not selecting either coding session as the winner ...
build one stronger canonical GREG Mind". Selection is by tests, adversarial inspection, founder intent,
maintenance cost, safety, measured performance and integration compatibility. It is never by branch ownership,
recency, code volume or benchmark counts. The intended effect is one cognition entry point, one authority
system and one evolution controller, with every useful capability retained and every frozen result intact.

**Current reality:**
- IMPLEMENTED, INTEGRATED and TESTED in a development container.
- Not founder-used, not REBOOT-VERIFIED, not on a body. VEPMC is 0.
- No capability is attached by this work: 64 of 72 cognition families start VERIFIED, meaning registered and
  withheld. The 8 attached by default are the seed families: causal, estimation, evidence, exact, formal,
  micro, optimization and semantic.

**Source coverage (inspected):**
- both lineage heads and their merge base;
- every file either lineage changed;
- #158's source manifest, evidence index, builder and tests;
- #155's frozen runs;
- the founder source above;
- the Founder Effect Compiler;
- `greg/path.json`.

**Unavailable:**
- Raw ChatGPT Project conversations.
- SNDlib's own terms page and CRAN: SNDlib failed DNS from this container and CRAN returned 403 at the proxy
  (see section 12).

**Contradictions resolved here:**
- "latest frozen run decides" now applies across lineages (section 5);
- experiment labels that collide between lineages (section 4);
- the immune-system effect was missing from the Backcast GPS (section 6).

## 3. Inventory at each level

| level | finding |
|---|---|
| file | 185 files changed by either lineage. Classified: 97 complementary, 73 historical evidence, 8 semantic incompatibility (the frozen-path collisions), 5 interchangeable, 2 duplicate, 0 unresolved. |
| interface | One cognition entry: `greg.cognition.cortex.reason` / `solve` -> catalog -> `SOLVERS` -> isolated worker -> independent verifier -> receipt. One Layer 5 entry above it: the Competency Compiler (`greg/cognition/compiler.py`). Both lineages' families run through it. |
| contract | One catalog projection (`catalog.FAMILIES`, 72 families). The genome contract is `greg/cognition/genomes/contract.py`. Proof classes: #155's family checks plus #158's `genome_certificate`, on one verifier. |
| genome | 126 inventoried; 97 implemented; 93 integrated; 36 admitted (27 DEFAULT_FOR_GEOMETRY, 9 NICHE_CAPABILITY); 7 COMPOSITION_ONLY; 12 SUPERSEDED; 4 REJECTED; 40 EXPERIMENTAL or unevaluated; 27 FRONTIER_HORIZON. 8 are attached by default and 0 are attached by any evaluation. On a body, actually exercised is 0 (VEPMC 0); exercised in tests and frozen evaluations only. |
| evaluation | One evidence index (`docs/evidence/greg-mind-evidence-index.json`) carries every frozen admission, P6 and P4 run of both lineages. `tests/unit/test_mind_evidence_sources.py` re-derives every row from the file it cites. |
| behaviour | Measured on one request per input signature. The compiler now refuses methods that lost on held-out data in either lineage (section 5); every other top choice is unchanged. |

A larger genome count is not a larger admitted repertoire. The inventory distinguishes all of these per
entry: `greg genomes` (or `python -m greg.cognition.genome_library`).

## 4. Reconciliation map: shared paths and colliding labels

The full map is the JSON file. The 22 paths both lineages changed are below.

| path | class | disposition |
|---|---|---|
| 7 runner/freeze/suite files under `cortex/evaluation/{composition_lift,learned_routing}/` and `docs/evidence/greg-protected-evolution/2026-10-14/README.md` | semantic incompatibility | Two different frozen artifacts share one path. Both are kept byte-identical under `lineage-archive/{pr155-ef5f078,pr158-a832c73}/`. #158's file holds the original path because #158's live tests import those runners: a dependency fact, not a ranking. #155's frozen P6/P4/P8 runners now refuse to re-run here (`FROZEN_INPUT_CHANGED`), as their freezes intend. |
| `greg/cognition/evolution.py` | interchangeable | #158's controller selected (section 5). #155's moved to `evolution_routing.py`. |
| `greg/cognition/benchmark.py` | interchangeable | #158's version-pinned `frozen-suite-v2.json` selected; #155's evaluation-view table superseded. |
| `tests/unit/test_greg_protected_evolution.py` | interchangeable | #158's file at the path; #155's moved to `test_greg_evolution_routing.py`. |
| `greg/isolation.py` | duplicate | Two fixes of one CI defect (#158 `1ea2209`, #155 `bfb9c04`). One grant path: #155's superset plus its ancestor guard covers #158's glibc list (tested). |
| `greg/cognition/{catalog,solvers,verification,composition}.py`, `greg/cli.py`, `greg/missions.py` | complementary | Both kept on one table or path. Names are disjoint (tested). Operation recipes dispatch before dataflow derivation. Goal Gravity has two hooks with disjoint outputs on one asks contract. |
| `greg/path.json` | complementary | Live fields carry #158's values; #155's records sit under `pr155_lineage` on P4, P5, P6, P8 and P10; the `immune_function` horizon is added. |
| `docs/FOUNDER_INTENT_LEDGER.md`, `foundry/owned-source.json`, `tests/integration/test_greg_cognition_mission.py` | complementary | Merged; the owned-source inventory regenerated with its script. |

Single-lineage duplicates and overlaps:

- `docs/intent/sources/FULL-POLYINTELLIGENCE-MIND-CONTINUATION-2026-10-07-source.md` (#155) is a 90-line excerpt
  of the same directive whose complete verbatim text is #158's 1,954-line
  `POLYINTELLIGENCE-MIND-CONTINUATION-DIRECTIVE-2026-10-07-source.md`. #158's is canonical; #155's is kept as
  history.
- `greg/cognition/advantage.py` (#155) overlaps `foundry/lawful_leverage.py` (#158). See sections 5 and 7.

**Experiment labels that collide.** Cite a run by lineage and commit, never by its short name.

| label | PR #155 | PR #158 |
|---|---|---|
| P4 v3 | `greg-learned-routing/2026-10-07/results-v3.json`: NO_GAIN 111 = 111 of 130, finished 2026-10-14 | `greg-learned-routing/2026-10-08/results-v3.json`: REGRESSION 160 vs 162 |
| P6 v2 | `greg-composition-lift/2026-10-14/results-v2.json` (F2b, X1, X2) | `greg-composition-lift/2026-10-08/results-v2.json` (F2R, F3, F4, F5) |
| P6 v3 | `greg-composition-lift/2026-10-14/results-v3.json`: derived chains, which the #155 README calls "F3" | `greg-composition-lift/2026-10-14-v3/results-v3.json` (F6) |
| F3 | derived estimate + identify -> optimise (constructed) | `graph_then_allocate` on generated networks |
| admission v2 | `greg-genome-admission/2026-10-14/results-v2.json` (operation families) | `greg-genome-admission/2026-10-14-v2/results.json` (genomes) |
| P8 | routing-genome search, `2026-10-14/results.json` | cycles 1-3, `2026-10-0{8,9}/`, `2026-10-14/cycle-cr-3.json` |

## 5. Mechanism selection record (evidence, not ownership)

| question | selected | evidence | alternative kept as |
|---|---|---|---|
| protected evolution controller | #158 `greg.cognition.evolution` | See the note below the table. | `evolution_routing.py`: isolated, not a controller, imported only by its historical runner (AST test) |
| frozen cognition benchmark | #158 `frozen-suite-v2.json` | version-pinned suite with v1 kept; #155's fix reconciled a drifting view of the same suite | git history at `ef5f078` |
| Landlock grants | one path: #155's superset | superset of both lineages' libraries, never user-site or an ancestor of repository or store; probe and confined-worker tests pass | none (exact duplicate fixed twice) |
| admission source of truth | the Mind evidence index | #158's index is digest-checked and re-derived by test; #155's inventory had misreported #158's 47 genome families as unbenchmarked | none: `genome_library` now reads the index |
| operation-family verdicts | #155's frozen admission runs, through the index | held-out runs against stated competitors; structural labels kept but non-routing | n/a |
| P4 deciding row | #155's NO_GAIN (later run) | #158's own rule: the latest frozen run decides. Both runs are negative, so the default stays shadow | #158's REGRESSION in the row's `history` |
| identify_then_optimize deciding family | #155's F2b (later run) | #158's own rule; F2, F2R and F2b form an independent replication of the lift | F2 and F2R in `history` |
| lawful intervention generation | #158 `foundry/lawful_leverage.py` | See the note below the table. | #155's typed-operator library in `advantage.py`: registered alternative, CLI only, `authority_created` false |
| founder-effect backcasts | `greg/path.json` horizons | the developmental-inheritance rule: one Backcast GPS | `advantage.DESTINATIONS` becomes a live buildability view naming its horizon (tested) |
| composition | both | #158's operation recipes and #155's dataflow derivation answer different request shapes; derived chains are NICHE (they lift over singles, not over the fixed recipe) | n/a |

Evolution controller evidence: candidates are confined, the evaluator is sealed (with a tamper test), there is a
recurring-failure trigger, and three targets have each been REJECTED. #155's routing-genome search has a
narrower target with one REJECT.

Lawful intervention evidence: #158's generator has consent, harm-ceiling and eligibility gates, Monte Carlo
estimates with falsifiers, and an independent five-lens review whose defects were fixed. #155's generator
emits only UNESTIMATED candidates. Neither has outcome evidence.

**Routing deltas the convergence makes** (one request per input signature):

- A request carrying only observations used to reach `cognition.collective`, a quorum vote that was REJECTED
  7-11 against simple majority on held-out seeds. That answered an anomaly question with a vote. It now
  reaches no operation fit and ends in an honest deficit. The anomaly families share one input signature and
  one epistemic class, so the request cannot say which question it asks.
- `simulate`: `cognition.simulation` is excluded (REJECTED 0-40 against the exact analytic baseline on its
  benchmark geometry).
- `crowd_label` (EXPERIMENTAL), `swarm_minimize` (DEFAULT) and `evolve_blackbox` (SUPERSEDED, rejected with that
  reason) become reachable. `robust_anomalies` is reachable by its operation only.

## 6. Cognitive reconciliation: findings that replicate across lineages

- **P4.** Two independently pre-registered decisive retests on different suites both found no gain: #158
  REGRESSION 160 vs 162, and #155 NO_GAIN 111 = 111. Conditional solver learning is not currently worth its
  complexity. Shadow observation stays. `scripts/mind_status.py` labelled NO_GAIN "UNRESOLVED"; it now labels
  it as the demotion it is.
- **P6.** The identify -> optimise lift replicated on fresh seeds in both lineages (F2R; F2b at 11-3).
- **P8.** Four protected-evolution runs (three #158 cycles and #155's routing search) were REJECTED. No
  rejected configuration is promoted. Protected evolution has never kept an improvement.
- **Layer 4.** #155's MICA/CDPE unseen-damage sweep found PARITY with adaptive central replanning. #158's
  `develop_repair` unreliable-controller win did not replicate (12-3, then 7-8). Neither lineage shows a
  replicated developmental advantage.
- **Backcast GPS.** The Founder Effect Compiler's immune-system example had no horizon. `immune_function` is
  added at N2, BUILDABLE_AFTER_PREREQUISITE. Its activation evidence: a replayed incident is detected,
  contained and recovered, and legitimate novelty is not quarantined.

## 7. Converged VPL accounting (post hoc summary of frozen runs; no new evaluation)

| family | lineage | data | lift vs best single | caveat |
|---|---|---|---|---|
| F1 estimate -> optimise | shared base | constructed | yes (p = 0.00012) | |
| F2 identify -> optimise | both | constructed | yes (F2R; F2b 11-3) | v1 underpowered |
| F3 graph -> allocate | #158 | constructed (generated networks) | yes | |
| F4 bayes -> voi | #158 | constructed | yes | |
| F5 forecast -> allocate | #158 | natural (M4) | **no** (8.5% cheaper, not significant) | |
| F6 forecast -> staff | #158 | natural (bank arrivals) | yes (74-16) | loses to the weekly-mean practitioner on day count (40-50) |
| F7 graph -> allocate | #158 | natural topology; computed truth | yes (92-0) | tied on every item by parametric min-cost flow, about 300x faster |
| X1 | #155 | constructed | yes (48-0) | cortex multi-organ route, not a recipe |
| X2 | #155 | constructed | yes (57-0) | its strongest single (a local model) NOT_RUN |
| derived chains ("#155 F3") | #155 | constructed | yes (41-0) | **no** lift over the best fixed recipe (4-2) |

Nine distinct families lift over the best single constituent they were measured against. Eight remain if X2
is set aside because its strongest single was not run. Two of three natural families lift.

Every lift costs latency (#158 accounting: 1.5-5.2x). Apart from F7's shortest-path-upgrade arm, no
practitioner pipeline was beaten where one was measured. This does not show composition has superior general
intelligence: several constituents are deliberately incomplete, as the founder warned.

## 8. F7 audit and the canonical genome for capacity expansion

`docs/evidence/pr155-f7-audit/2026-10-14/`, frozen at `49b2d58`: **CONFIRMED**.

- The 200 held-out instances were rebuilt by the audit's own code.
- The HiGHS optimum equals #158's recorded truth on 200 of 200.
- Every arm's recorded outcome and throughput reproduce under an independent max-flow.

**Should parametric min-cost flow be the canonical genome for this geometry?** Engineering answer: yes,
conditionally. It is exact on every audited item, a single certified intelligence, and about 300 times faster
than the three-stage composition. That intelligence is #158's `flow_expansion_mcf`, version 1.0.0.

- It is UNEVALUATED in the index: no frozen admission at its exact version.
- The compiler already routes a flat capacity-expansion request to it as the only fit; it is withheld, so the
  route ends in an attach ask.
- A recipe-shaped payload still reaches `graph_then_allocate`.

The condition is a pre-registered admission of `flow_expansion_mcf` 1.0.0 with the composition as competitor
on items F7 never used. This PR does not run that admission:
- #158's ledger already schedules admission v3 for this genome;
- a second session admitting the same genome would create another verdict collision.

The founder's VPL definition says "beats the strongest single available intelligence". Once
`flow_expansion_mcf` is admitted, F7 should be re-measured with it as a constituent. A tie at higher latency
would remove F7's lift. That is an expectation, not evidence.

**F8 and the converged tree.** F8's frozen harness, `run_v5.py`, refuses to report from this tree by design
(`FROZEN_INPUT_CHANGED`). Twelve files in its frozen code closure differ here, including the converged compiler,
catalog, solvers, verification and evidence index. F8's held-out result therefore measures #158's lineage at its
freeze commit.

Measuring the converged Mind on F8, including its compiled arm, needs a fresh pre-registered freeze on this
branch, under a lineage-unique path. It is listed with the remaining falsification tests.

## 9. Retained alternatives (isolated, registered, none live)

| alternative | where | state | what would decide it |
|---|---|---|---|
| routing-genome protected evolution (#155) | `greg/cognition/evolution_routing.py`, `tests/unit/test_greg_evolution_routing.py` | not imported by any runtime module (AST test); its frozen runner refuses changed inputs | a target where routing configurations, not method configurations, carry headroom |
| typed mental-model operator library (#155) | `greg/cognition/advantage.py` | CLI only (`greg advantage`); emits UNESTIMATED candidates that the existing ranker drops without estimates | a frozen comparison: does it add lawful candidates the Foundry's library misses on the same problems? |
| both lineages' colliding frozen files | `docs/collaboration/lineage-archive/` | byte-identical archival copies (tested against git and the manifest's digests) | n/a: evidence |
| #155's benchmark reconciliation table | git history at `ef5f078` | superseded | n/a |

## 10. Five review responsibilities

This PR's builder performed all five as separate passes, which is not independent review. Dissent is preserved,
not averaged.

Independent review is pending. The PR #158 session (`session_01GRT2jX7cQXwvMkn64ZgvLk`) has taken the
Adversarial Reviewer and Evidence/Welfare Guardian roles on these commits, from outside the builder role. From
read-only snapshots it is building:

- its own inventory and reconciliation map;
- its own F7 audit against parametric min-cost flow;
- P8 adversarial probes against both evolution engines.

Its findings, posted on the PR, take precedence over roles 3 and 5 below wherever they differ. The two F7
audits are deliberately independent: agreement between them is evidence, and disagreement is a finding.

1. **Founder-Intent Steward.** The directive's requirements map to code or to a named residual (sections 13 and 15).
   - The founder's six effect examples all sit on the one Backcast GPS.
   - No metaphor became architecture. The immune-system horizon is compiled to detection, containment,
     recovery and learning, not to simulated biology.
   - **Dissent:** the "latest run decides" rule is chronological, so a later underpowered run could displace a
     stronger earlier one. It is #158's accepted rule and no current verdict depends on it. A sign
     disagreement between lineages should go to the founder, not be settled by finish time.
2. **Systems Architect.**
   - One entry point, one Layer 5 compiler, one evolution controller, one evidence index, one Landlock grant
     path, one Backcast GPS.
   - **Remaining duplication:** two intervention generators, kept because their relative merit is
     unmeasured.
   - **Dissent:** `greg/path.json` now carries `pr155_lineage` records on five nodes, which raises reading
     cost. Fold them into the live fields once the founder decides the merge.
3. **Adversarial Reviewer.** Attacks tried, each with its outcome:
   - Did a frozen file change? No: tested digests, plus each run's own `FROZEN_INPUT_CHANGED` refusal.
   - Did #155's verdicts inflate any route? No: only measured verdicts route; ALIAS and similar labels route as
     UNEVALUATED (tested).
   - Is any NO_GAIN shown as lift? No: P4 is labelled demoted and shadow.
   - Can a stale positive verdict route? No: the inventory applies the compiler's version rule (tested).
   - Can F7's truth and scorer be co-wrong? Audited independently: CONFIRMED.
   - Two defects were found and fixed:
     - the observations-only quorum route;
     - a corruption test that had silently stopped testing anything (it popped "the last source", which
       became one of #155's files).
4. **Operator/Maintainer.**
   - Every CI step was run locally (commands and results in the PR body).
   - Evidence directories are shared, so `results.json` names are unique only by directory. The completeness
     test now lists non-recipe families explicitly, so a new label cannot slip past.
   - **Cost:** the evidence-index builder now carries a lineage-specific `OPERATION_RUNS` table.
5. **Evidence/Welfare Guardian.**
   - Negative results and contamination disclosures are intact.
   - The P8 pre-freeze smoke run disclosure stands (#155 P8).
   - Third-party data rights are unresolved and are flagged as a release blocker (section 12).
   - Nothing here contacts, spends, publishes or attaches.

## 11. Exactly two strengthening passes

**Pass 1: the strongest combination against the simpler alternatives.**

The three options compared:

- **Strongest combination:** #158's canonical stack (compiler, genome library, evidence index, sealed
  evolution, Lawful Leverage Foundry, worlds and status ledger), plus #155's measured operation-family
  verdicts, repertoire, dataflow derivation, Goal Gravity attach ask, P4/P8/P6 replications and destination
  backcasts.
- **Simpler alternative:** #158 alone, with #155 archived. That loses:
  - four measured REJECTED verdicts that change routing;
  - one SUPERSEDED verdict;
  - two admitted repertoire families;
  - the cross-lineage replication of P4 and F2;
  - the derived-chain mechanism;
  - a stronger Landlock grant set.
- **Do nothing (two Minds):** two admission truths, two evolution controllers, and a compiler that ignores
  half of the negative evidence.

Weaknesses found:

- (a) The inventory and the compiler read different admission sources.
- (b) Rejected operation families were still routable.
- (c) Evidence labels collided.
- (d) Founder-effect destinations sat outside the GPS.
- (e) The immune-system horizon was missing.
- (f) Two intervention generators existed.
- (g) Two isolation fixes existed.
- (h) F7 was unaudited.
- (i) Data rights were unresolved.
- (j) Path records mixed lineages in live fields.

**Pass 2: adversarial attack on the combination.** Each weakness's disposition:

| weakness | disposition |
|---|---|
| (a) | resolved: one index |
| (b) | resolved: routing reads measured verdicts |
| (c) | resolved: lineage-qualified table, non-recipe list, unique paths |
| (d) | resolved: horizons named and tested |
| (e) | resolved: horizon added |
| (f) | kept: unresolved merit, isolated, with the deciding experiment named |
| (g) | resolved: one path |
| (h) | resolved: audit CONFIRMED |
| (i) | escalated: legal / founder |
| (j) | resolved: `pr155_lineage` convention, tested by #158's record checks |

Complexity removed:

- duplicate grant loops;
- the inventory's direct reads of frozen files;
- the second destination list as a source of truth;
- the second benchmark table.

Remaining falsification tests:

1. Pre-registered admission of `flow_expansion_mcf` 1.0.0 against the composition on items F7 never used.
2. F7 VPL re-measured with that genome as a constituent.
3. A frozen comparison of #155's operator library against the Foundry library on the same problems.
4. Version-bound re-admission of the operation families (they carry no version).
5. A natural family that uses an admitted Layer 1 or Layer 2 genome.
6. F8 re-measured on the converged Mind under a fresh pre-registered freeze (its #158 freeze refuses here).

## 12. Third-party data rights: release blocker

This repository is **public**. Four extracts were committed by #158 on a public feature branch (not `main`)
and are carried by this PR:

| file | source | terms verified this session | status |
|---|---|---|---|
| `cortex/evaluation/data/sndlib_networks.json.gz` | SNDlib 1.0 networks via TopoHub 1.5.1 | TopoHub is MIT. Its PyPI page states no terms for the bundled datasets. SNDlib's site could not be reached (DNS failure), so the builder's note ("research purposes only, no open licence") is **unverified**. | uncleared |
| `cortex/evaluation/data/m4_weekly.json.gz` | M4 competition, `Mcompetitions/M4-methods` | the GitHub repository has **no licence file or statement** (verified) | uncleared |
| `cortex/evaluation/data/bank_calls_halfhour.json.gz` | fpp3 `bank_calls` (credited to Weinberg, Brown and Stroud 2007) | no dataset-specific licence found; the package is listed GPL-3; CRAN was unreachable (403) | uncleared |
| `cortex/evaluation/data/uber_nyc_2015_halfhour.json.gz` (F8, merged from #158 `202b932`) | NYC TLC Uber pickups, January to June 2015, released under a Freedom of Information Law request and published in `fivethirtyeight/uber-tlc-foil-response` | That repository has **no licence statement** (verified). FiveThirtyEight's CC BY 4.0 statement covers only its `data` repository. The builder's own note says neither the TLC nor FiveThirtyEight states an open licence. | uncleared (public records; lower risk, not cleared) |

Founder or legal decision, before any merge to `main` or any release:
- obtain permission (SNDlib maintainers at Poznan University of Technology; the M4 organisers); or
- move the extracts out of the tree and rebuild them on demand from source (each builder already verifies a
  source sha256); or
- substitute openly licensed data.

Removal from a branch does not remove the files from public history; this PR does not attempt that.

## 13. Acceptance gates

| gate | status | evidence |
|---|---|---|
| both lineages recoverable, evidence inspectable | met | heads above; archives; manifest; `test_mind_lineage_manifest.py` |
| frozen results unaltered | met | digest tests; archives equal `git show`; #155 runners refuse (`FROZEN_INPUT_CHANGED`) |
| every conflict has a disposition | met | map JSON (185 entries, coverage test against git) |
| the branch passes its own CI, contract, integration, security and regression tests | see the PR body for the run on the final commit | full suite plus every CI script step |
| one canonical cognition entry point | met | section 3; one `SOLVERS` table |
| alternative engines cannot silently assume live authority | met | 64 of 72 families start VERIFIED (withheld); attach is founder-only (`test_greg_competency_compiler.py`, `test_greg_cognition_genesis.py`); `check_authority_singleton.py` passes; `evolution_routing` has no runtime importer |
| the protected evaluator cannot be modified by its candidates | met | `test_greg_protected_evolution.py` (sealed-evaluator tamper refused; Landlock probe DENIED); `test_greg_evolution_routing.py` (hash-pinned evaluator) |
| no rejected P8 configuration promoted | met | nothing attached; P8 `exit_met` false (`test_frontier_backcasts.py`) |
| no NO_GAIN presented as positive lift | met | P4 row and status label; `forecast_then_allocate` NO_LIFT demoted |
| strong standalone and practitioner baselines included | met where measured | F7 PMCF and SP-upgrade; F6 weekly mean; crowd-sparse one-step vote; F7 audit |
| genome admission bound to the exact tested version | met | compiler stale guard; inventory applies the same rule (`test_greg_mind_convergence.py`) |
| interruption and restart do not duplicate consequential actions | met in tests | `test_greg_cognition_process.py::test_cli_composition_survives_sigkill_without_duplicate_computation`, `test_greg_cognition_mission.py::test_detachment_survives_restart...` |
| Kernel, event spine, authority, shutdown and founder boundaries preserved | met | no change to `policy/`, `provenance/`, `authority/`, `greg/founder.py` or the Gate |
| no live deployment or external consequence | met | draft PR only |

## 14. Rollback

- Close the draft PR. Nothing outside the branch `claude/greg-mind-lineage-convergence` changed. #155's and
  #158's branches and their frozen evidence are untouched by this PR.
- To undo a single integration step on this branch, revert its commit:
  - `49b2d58`: index operations, compiler and inventory;
  - `8bbd3b8`: audit result, horizon and manifest label;
  - `e21bb5b`: merge of #158 `047549f`;
  - `6e62b59`: map.
- Then rebuild the index with `PYTHONPATH=. python scripts/build_mind_evidence_index.py` and run
  `python -m pytest -q`.

## 15. Still unverified, and escalations

**Unverified:**
- the converged Mind on a body or with a founder (VEPMC 0);
- any real-mission settlement of an admitted genome;
- reboot persistence;
- the SNDlib and fpp3 data terms.

**Not done here:**
- `flow_expansion_mcf` admission and F7 re-measurement (left to #158's scheduled admission v3; see section 8);
- version binding for operation families;
- an evaluation of #155's operator library against the Foundry.

**Escalations (founder-only):**
1. Merge of this PR, and of #155 and #158.
2. Data rights (section 12): a release blocker.
3. Whether `flow_expansion_mcf` becomes canonical for capacity expansion once admitted (recommended).
4. Attaching any family (none recommended by this PR).
5. Whether a sign disagreement between lineages' frozen verdicts should go to the founder instead of the
   finish-time rule.

## 16. Product delta

Compared with either lineage alone, GREG can now:

- refuse to answer with methods that lost on held-out data in either lineage;
- recruit #155's crowd and swarm families under their measured status;
- report every family's true measured admission in `greg genomes` and in its attach asks;
- route on one digest-checked index that holds both lineages' frozen evidence.

#158's F7 result is independently verified. The immune-system destination is back on the one Backcast GPS.
