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
| PR #158 head | `050c1b2` (merged in this PR); earlier merges at `77b61a1`, `047549f`, `202b932`, `41a8538`, `f8e8fd2` (review of #179 M18), `10fdbab` and `463a9d0` | changed files classified in section 3 |
| shared paths | 22 | 8 are frozen-path collisions |

Convergence commits:

- `2d1ddd3` merged #158 at `77b61a1`. Its message names `a832c73`; the actual parent is `77b61a1`, which is
  `a832c73` plus the graph_or review fix `99e6d83`.
- `49b2d58`, `8bbd3b8` and `6e62b59` are Track B work.
- `e21bb5b` merges #158 `047549f`.
- `8a43e70` records the institutional verifier run (PASS, bound to `ccd38a2`).
- A later merge brings #158 to `202b932`: the F8 (P6 v5) pre-registration, freeze, suite and data. F8's held-out
  arms had not run at that merge.
- A further merge brings #158 to `41a8538`: F8's frozen result, verified fixes to the promoted competitor genomes,
  and the Backcast GPS record of F8.
- The last merge brings #158 to `f8e8fd2` (review of #179, M18). It adds genome admission v3, which was
  pre-registered at `878f76c`, and P8 cycle cr-4, run under a committed freeze. It also adds #158's own fixes for
  review findings M14, L5 and L6 (`af258bf`), and its compiler's part-addressed rows.
  - **P8 files:** this branch had fixed the same findings in parallel (`1da022a`). #158's versions of
    `evolution.py`, `evolution_sandbox.py`, `isolation.py` and their tests are selected, because cr-4's freeze
    binds those bytes. This branch's variant is history only.
  - **Compiler:** #158's part rows replace this branch's wrapped-key matching for M10. The one status function
    over the index (#155's operation verdicts, code binding), the derived chains and the practitioner-tie fields
    are re-applied on top.
  - **Map:** the map pinned `f8e8fd2` at that merge.
- The latest merge (`6eaccfa`) brings #158 to `10fdbab`. It adds:
  - #158's verifier with an independent Z3 certificate for OPTIMAL, FEASIBLE, INFEASIBLE and UNSAT claims
    (its check key `optimal_objective_meets_its_bound` replaces this branch's `optimality_bound_met`; one test
    follows the new name);
  - `grid_dijkstra` 1.1.0 and genome admission v4, pre-registered on fresh seeds 1300-1329 (1.1.0 is
    DEFAULT_FOR_GEOMETRY; the flow genomes replicate);
  - P8 cycle 5 (search policy `cover/1`), REJECTED at the adversarial gate; its held-out split was never
    evaluated;
  - F7 with `flow_expansion_mcf`, a declared re-use of v4's 200 held-out items: the genome MATCHES the truth
    algorithm on every item, and F7 with the genome as a constituent is NO_LIFT. Section 8's recommendation
    is therefore measured, not projected; it is still diagnostic for generalization because the items were
    already exposed;
  - version-bound compiler measurements, which this branch combines with its own code-drift check (section 5).
  - **Resolved conflicts:** `composition.py`, `flow.py` and `worlds.py` take #158's bytes. `verification.py`
    takes #158's certified-bound hunk and keeps both import sets. `isolation.py` keeps this branch's one grant
    path, plus #158's venv grant and thread refusal. `compiler.py` keeps #158's demotion block, family status
    and measurements block, with this branch's derived rows, stale-measurement fields and code-drift check
    re-applied. `greg/path.json` takes #158's status line and re-inserts #155's lineage segment.
  - **Release exclusions:** the five new F7 files that carry SNDlib-derived data are added (26 paths).
  - **Map:** the map pinned `10fdbab` at that merge, and a test asserts it is an ancestor of this branch.
- Later merges bring #158 to `463a9d0` (`0e30b59`; manifest post-decision block, `known_strengths` cite F7) and to
  `050c1b2` (`020be11`), both clean:
  - **P8 cycle 6:** RETAIN on held-out data (105-73, p = 0.00995). Random restart is at least as good, and the
    canary passes (CANARY_PASSES). The proposal stays PROPOSED_NOT_APPLIED; who adopts it is the founder decision
    already escalated in section 9, and it is now live.
  - **Seed reservations:** `P8_RESERVED` is now 7000-8599, and `CR_CANARY_SEEDS` excludes the canary range.
    Operation admission v3's seeds 5001-5040 are spent and never overlap that reservation (test).
  - **Map:** the map pins `050c1b2`, and a test asserts it is an ancestor of this branch.

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
| file | 253 files changed by either lineage (#158 at `10fdbab`). Classified: 111 complementary, 127 historical evidence, 8 semantic incompatibility (the frozen-path collisions), 4 interchangeable, 2 duplicate, 1 unresolved (`advantage.py`, review L19). Each disposition is checked against git: "kept" and "selected" mean the lineage's bytes, while "extended", "merged" and "modified" mean they differ (review M20). |
| interface | One cognition entry: `greg.cognition.cortex.reason` / `solve` -> catalog -> `SOLVERS` -> isolated worker -> independent verifier -> receipt. One Layer 5 entry above it: the Competency Compiler (`greg/cognition/compiler.py`). Both lineages' families run through it. |
| contract | One catalog projection (`catalog.FAMILIES`, 72 families). The genome contract is `greg/cognition/genomes/contract.py`. Proof classes: #155's family checks plus #158's `genome_certificate`, on one verifier. |
| genome | 127 inventoried; 98 implemented; 94 integrated; 41 labelled DEFAULT_FOR_GEOMETRY (30) or NICHE_CAPABILITY (11); 4 COMPOSITION_ONLY; 10 SUPERSEDED; 4 REJECTED; 41 EXPERIMENTAL or unevaluated; 27 FRONTIER_HORIZON (measured 2026-10-21 on the tree that merges #158 at `463a9d0`). Every surface reads the compiler's routed status (round-2 review, N2), so all 41 labels are **rule-admitted**: #158's pre-registered genome admissions at the current version, plus the six operation families that operation admission v3 (pre-registered, section 18) admitted against a competitor. #155's lineage operation verdicts, recipe lifts and hand-coded organ labels are reported beside an entry as notes and no longer appear as admissions (0 each). `genome_library.admitted_by_provenance()` reports this split. 8 of the 72 catalog families are attached by default, and 0 are attached by any evaluation. Counting every cognition capability, 22 are attached by default (review L4). One of them, `cognition.seed.solve` (#142), runs `cortex.seed` methods on its own worker, with its own verifier and receipts, outside the compiler's evidence routing. It is a registered alternative entry, not a second canonical Mind entry; it stays attached because a shipped mission template (`greg/templates.py`) names it as its compute strategy, and `greg/capabilities.py` registers it as the benchmark twin and fallback, never as a second authority. Withholding it by default would break that template; that change is left for a decision. On a body, actually exercised is 0 (VEPMC 0); exercised in tests and frozen evaluations only. |
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
| operation-family verdicts | #155's frozen admission runs, through the index | held-out runs, not pre-registered in git (freeze, runner and results land in one commit, review H4); four DEFAULTs had no competitor and route as UNEVALUATED (review H4); collective's REJECTED is corrected by an erratum to EXPERIMENTAL (review M3); structural labels kept but non-routing | n/a |
| P4 deciding row | #158's REGRESSION (191 items) | review of #179 (H1): #155's NO_GAIN re-measured 130 of the same payloads, so it is a same-instance re-run and cannot decide. Both are negative; the default stays shadow | #155's NO_GAIN in `history`, labelled same-instance re-run |
| identify_then_optimize deciding family | #158's F2R (64 items) | review of #179 (H1): F2b used the same generator on seeds 25-72, a subset of F2R's 25-88, so it is a same-instance re-run. F2 to F2R shares no instance and is the one genuine replication | F2 and F2b in `history` |
| lawful intervention generation | #158 `foundry/lawful_leverage.py`, extended with #155's seven uncovered operator classes | See the note below the table. | #155's `compile_map`: superseded as a generator; read-only structural view (CLI), `authority_created` false |
| founder-effect backcasts | `greg/path.json` horizons | the developmental-inheritance rule: one Backcast GPS | `advantage.DESTINATIONS` becomes a live buildability view naming its horizon (tested) |
| composition | both | #158's operation recipes and #155's dataflow derivation answer different request shapes; derived chains are NICHE (they lift over singles, not over the fixed recipe) | n/a |

Evolution controller evidence: candidates are confined, the evaluator is sealed (with a tamper test), there is a
recurring-failure trigger, and three targets have each been REJECTED. #155's routing-genome search has a
narrower target with one REJECT.

Lawful intervention evidence: #158's generator has consent, harm-ceiling and eligibility gates, Monte Carlo
estimates with falsifiers, and an independent five-lens review whose defects were fixed. #155's generator
emits only UNESTIMATED candidates, which the ranker drops. Neither has outcome evidence.

How the two generators were reconciled (2026-10-15, revised after the founder's review the same day):

- **Crosswalk.** Each of #155's twelve operators was matched to the Foundry library by mechanism, not by
  name (`advantage.FOUNDRY_MECHANISM`, tested).
  - Five had an equivalent primary: receipts, a published eligibility standard, milestone escrow, a second
    source, and evidence-based triage.
  - Seven had none: incumbent integration, counter-positioning, verified compliance as a qualification, a
    consented supply pool, accountability, a regenerative participant benefit, and step removal (via negativa).
- **The seven classes are in the Foundry library** (`lawful_leverage.PORTED_FROM`), so they pass the Foundry's
  gates and estimator instead of staying unestimated.
  - Accountability became four legal channels (below).
  - #155's `compile_map` is a historical, read-only view. Its operator table is pinned by digest, so it cannot
    evolve as a second generator.
- **One evidentiary standard for every template, whatever its lineage.** Each template, reviewed or ported,
  carries a weak template prior.
  - A route whose estimate rests on priors alone is labelled (`selection_basis`, `selection_basis_note`).
  - It ranks after any defensible route with observed evidence.
  - It cannot win the "dominates the direct-labour baseline" branch. Prior-drawn samples show what a template
    assumed, not what the route does.
  - **Superseded attempts:**
    - The first port changed the default test problem's selected route to step removal, on priors alone.
    - The second gave ported templates a floor prior, which restored the old winner. That was tuning for an
      expected result, so it was removed.
  - On that problem, the old winner (receipts plus eligibility) and the new one (step removal plus an internal
    tool) both rest on priors alone. Neither has defensible observed evidence there. The new selection is
    labelled `PRIOR_ONLY`, and the next step is its staged pilot or evidence keyed to it.
  - A ported template backed by evidence keyed to its own id is selected (tested).
- **Mechanism identity, made explicit now that a surface holds more than one mechanism.**
  - Recombination pairs every recombinable mechanism across complementary surfaces. Pairs that existed before
    the port come first and unchanged (tested against `_recombine` without the added templates). On `e19226a`,
    `_recombine` keyed a dict by surface, so a second mechanism on a surface overwrote the first.
  - Each component keeps its own surface record, evidence keys and consent check.
  - Surface-keyed evidence was recorded when each surface had one mechanism, so it informs only that
    surface's primary. An intervention cites only the evidence its estimate used.
- **Contract ceiling (64 candidates): evidence first, nothing silently starved.**
  - The pool admits direct labour, then every candidate whose every channel has observed evidence, then the
    rest (reviewed templates before added ones).
  - Each candidate over the ceiling is listed in `generated.deferred` with its reason (`OVER_CEILING_PRIOR_ONLY`
    or `OVER_CEILING`) and a bounded sandbox route, `evaluate_deferred`. That route compiles the candidate on its
    own surfaces only and executes nothing.
  - With every surface declared, an evidence-backed ported template is evaluated (tested).
  - Without such evidence, the reviewed library's evaluated set and the selection are identical to the
    pre-port Foundry (checked against the `e19226a` tree).
- **Consent is purpose-bound and never a wildcard.**
  - A non-primary mechanism needs a consent record that names it (`for_mechanisms`). Writing the tests showed
    an accountability record would otherwise clear the gate on the payers' agreement to a receipts pilot.
  - A consent naming a mechanism on another surface is refused.
  - A revoked record (`revoked_at`) clears nothing, for primaries, mutations and combinations alike.
  - Both fields are optional additions to the problem contract.
- **Consent, lawful basis and execution authority are separate.**
  - Accountability is four channels, each with its own access restriction and evidence standard
    (`LEGAL_CHANNELS`): private evidence preservation, confidential counsel review, submission to an
    appropriate authority, and public publication.
  - Only publication is gated on the affected parties' consent. A subject's refusal does not remove
    preservation, review or authority submission.
  - That rule is not a universal claim either way. Some regimes protect reporting without the reported
    party's approval. Under Rule 21F-17(a), SEC orders treat a requirement to obtain company approval before
    contacting the Commission as impeding a whistleblower
    (https://www.sec.gov/enforcement-litigation/whistleblower-program/whistleblower-protections). That rule is
    scoped to information flowing to the Commission and clears no other disclosure. Each channel still needs its
    own applicable basis.
  - No channel is ever recombined with a commercial lever.
  - Every channel's authority state is `LEGAL_BASIS_REVIEW_REQUIRED`. The Foundry establishes no lawful basis,
    and a problem cannot assert one (the contract refuses the field).
  - Each eligible channel yields a review request for a licensed professional through the existing ask path
    (`legal_review_packets`; Goal Gravity validates, screens and prepares them, unrecorded). Its disposition is
    `LEGAL_REVIEW`, never `EXECUTE_THROUGH_GATE`.
  - These controls govern GREG's actions only. They do not limit anyone's own right to report.
- **One governed path, tested end to end** through Goal Gravity: problem, generation, eligibility, estimation,
  the institutional-leverage ranker, CandidateProposals for the Gate, and a receipt. Consent and evidence stay
  scoped to each mechanism throughout. Nothing is written or executed.
- **Not measured:** whether the added classes produce better outcomes. No real institutional map with settled
  outcomes exists in the repository. The crosswalk decides coverage, not merit.

**Routing deltas the convergence makes** (one request per input signature):

- A request carrying only observations used to reach `cognition.collective`, a quorum vote. Its frozen
  REJECTED reading came from a loss to an oracle baseline (review M3); against deployable majority it tied
  7-11, and operation admission v3 reads it EXPERIMENTAL (section 18). It routes as EXPERIMENTAL on every surface
  (round-2 review, N2); this delta is no longer a refusal and was corrected after that review. The anomaly families share one input signature and
  one epistemic class, so the request cannot say which question it asks.
- `simulate`: `cognition.simulation` is excluded (REJECTED 0-40 against the exact analytic baseline on its
  benchmark geometry).
- `crowd_label` (EXPERIMENTAL), `swarm_minimize` (DEFAULT) and `evolve_blackbox` (SUPERSEDED, rejected with that
  reason) become reachable. `robust_anomalies` is reachable by its operation only.

## 6. Cognitive reconciliation: findings that replicate across lineages

- **P4.** #158's decisive retest found REGRESSION (160 vs 162). #155's NO_GAIN (111 = 111) re-measured 130 of
  the same 191 payloads after training on the same development partition. It is a same-instance re-run:
  evidence that the result reproduces, not an independent replication (corrected after the review of #179,
  H1). Conditional solver learning is not currently worth its complexity. Shadow observation stays.
  `scripts/mind_status.py` labelled NO_GAIN "UNRESOLVED"; it now labels it as the demotion it is.
- **P6.** The identify -> optimise lift replicated once: F2 (#158 v1) to F2R (#158 v2), with no shared
  instance. #155's F2b re-measured 48 of F2R's 64 instances and matched them item for item (43 correct, 3
  wrong, 2 no decision, the same failing seeds). That shows reproducibility, not replication.
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
| F3 graph -> allocate | #158 | constructed (generated networks) | yes (11-0, over greedy) | the exact single genome `flow_expansion_mcf` ties it on development items F3-1..8 (8/8 each, review L15); measured before that genome existed |
| F4 bayes -> voi | #158 | constructed | yes | truth is the declared-model Bayes action, not the hidden parameter; the best constituent was denied the observed evidence; on realised value the composition is worse (-55.4 against -20.3, review M13) |
| F5 forecast -> allocate | #158 | natural (M4) | **no** (8.5% cheaper, not significant) | |
| F6 forecast -> staff | #158 | natural (bank arrivals) | yes (74-16) | loses to the weekly-mean practitioner on day count (40-50) |
| F7 graph -> allocate | #158 | natural topology; computed truth | yes (92-0, over greedy) | tied on throughput on every item by parametric min-cost flow (PMCF); at equal throughput the composition spends more than PMCF on 46 of 100 development items (mean excess 7.6% of budget, max 55.8%) and never less (spend diagnostic, review M11), so the exact method weakly dominates it; the frozen latencies of the two are not comparable (review M12) |
| X1 | #155 | constructed | yes (48-0) | cortex multi-organ route, not a recipe |
| X2 | #155 | constructed | yes (57-0) | its strongest single (a local model) NOT_RUN |
| derived chains ("#155 F3") | #155 | constructed | yes (41-0) | **no** lift over the best fixed recipe (4-2) |
| F8 track -> staff | #158 | natural (NYC 2015 pickups; Layer 1 Kalman tracker as a stage) | yes, over the best single intelligence | 4.7% dearer in total than the simpler EWMA ratio + quantile ablation (the tracker's abstentions fall back to the standing plan); measured on #158's lineage at its freeze commit, not on the converged Mind |

**Count under the founder's definition** (review of #179, L2). The VPL metric counts held-out families where
composition beats the strongest single available intelligence, net of cost and latency, with no added false
answers. Under that definition no family is settled:
- **no lift against the strongest single:** F7 (NO_LIFT once the exact genome is a constituent, 2026-10-16,
  section 8);
- **pending, a stronger single exists or was not run:** F3 (the exact genome ties it on development data), X2
  (strongest single NOT_RUN);
- **lift over a constituent denied information or incomplete by design:** F4 (uninformed prior), X1 (structural,
  cortex multi-organ route);
- **added wrong answers or abstentions where a single was right:** F2R-27, -37, -41, -87 (two wrong, two no
  decision) and F2b-27, -37, -41 (one wrong, two no decision), recomputed here from the frozen rows;
- **beaten or tied by a practitioner on a natural family:** F6 (weekly mean wins day count 50-40), F8 (dearer in
  total than the EWMA-quantile ablation; loses on item count to the cumulative-ratio, EWMA-ratio and
  Kalman-median arms).

The weaker count, over the best constituent each family was measured against, is ten families (nine without
X2). The evidence index now carries each frozen run's practitioner arms as `tied_by` and `loses_to`, and the
compiler and `greg genomes` report them. #155's ledger line "VPL = 4 distinct families with F1" carries an
erratum.

Every lift costs latency (#158 accounting: 1.5-5.3x; F7 5.31x, review L13). Apart from F7's shortest-path-upgrade arm, no
practitioner pipeline was beaten where one was measured. This does not show composition has superior general
intelligence: several constituents are deliberately incomplete, as the founder warned.

## 8. F7 audit and the canonical genome for capacity expansion

`docs/evidence/pr155-f7-audit/2026-10-14/`, frozen at `49b2d58`: **CONFIRMED**.

- The 200 held-out instances were rebuilt by the audit's own code.
- The HiGHS optimum equals #158's recorded truth on 200 of 200.
- Every arm's recorded outcome and throughput reproduce under an independent max-flow.

**Should parametric min-cost flow be the canonical genome for this geometry?** Engineering answer: an exact
single method should be, conditionally. PMCF (the same split-arc formulation, a different algorithm, uncertified)
tied the composition on all 200 audited items and never spends more at equal throughput. #158's
`flow_expansion_mcf` 1.0.0 shares the formulation, not the algorithm (successive shortest paths with its own
dual or cut certificate). It had development evidence only when this audit ran (review L10); #158's admission
v3 and F7 v6 measured it since (below).

Latency (review M12, corrected): the earlier "about 300 times faster" divided PMCF run in process by the
composition through three isolated workers; the frozen v4 README says those figures are not comparable. Like for
like, the review measured the composition and PMCF equally fast in process (per-item median ratio 0.96x), and a
one-stage exact genome on GREG's path about 4-5x faster than the three-stage chain. An erratum sits beside the
frozen audit (`docs/evidence/pr155-f7-audit/2026-10-14/ERRATUM-2026-10-15.md`); its README is unchanged.

**Decided by pre-registered evidence, not escalated (review L21).** #158's admission v3 was pre-registered at
`878f76c` on fresh seeds 1200-1229. It admits `flow_expansion_mcf` 1.0.0 as DEFAULT_FOR_GEOMETRY against the
`graph_then_allocate` composition twin: equal quality on all 30 instances at about one seventh of the latency.
Under the frozen rule it is therefore the routed default for budgeted capacity expansion. The composition stays
a registered alternative. Attaching the genome remains the founder's decision.

On this tree, with the composition's stages attached and the genome withheld, a `capacity_network` request names
`flow_expansion_mcf` as the withheld best fit and records an attach ask, and the composition serves meanwhile.
Once the genome is attached, the compiler selects it. Both cases are tested.

**F7 with the genome, measured (#158, `docs/evidence/greg-composition-lift/2026-10-16-f7-mcf/`, freeze `91b826c`).**
This is a declared re-use of v4's 200 already-exposed held-out items, so it is a replication, not a new
generalization claim.
- **Rule:** MATCH. `flow_expansion_mcf` is optimal on 200 of 200 through `cortex.reason`, at a median 0.753 s
  against the composition's 2.866 s. The compiler selected the genome on all 200 items.
- **Secondary:** F7_LIFT_WITH_GENOME is **NO_LIFT**. With the exact single genome in the repertoire, F7's
  composition lift does not survive. v4's frozen verdict, over a repertoire that lacked the genome, is unchanged.
- **Spend:** not pre-registered as a secondary measure in v6. The development-data spend diagnostic in
  `docs/evidence/pr155-f7-spend-diagnostic/2026-10-15/` stays diagnostic.

**F8 and the converged tree.** F8's frozen harness, `run_v5.py`, refuses to report from this tree by design
(`FROZEN_INPUT_CHANGED`). Twelve files in its frozen code closure differ here, including the converged compiler,
catalog, solvers, verification and evidence index. F8's held-out result therefore measures #158's lineage at its
freeze commit.

Measuring the converged Mind on F8, including its compiled arm, needs a fresh pre-registered freeze on this
branch, under a lineage-unique path. It is listed with the remaining falsification tests.

## 9. Retained alternatives (isolated, registered, none live)

| alternative | where | state | what would decide it |
|---|---|---|---|
| routing-genome protected evolution (#155) | `greg/cognition/evolution_routing.py`, `tests/unit/test_greg_evolution_routing.py` | not imported or named by any non-test source outside its runner (AST and string test over every top-level tree); its frozen runner refuses changed inputs. Review L8 found three adversarial probes accepted on its evaluator (a module edit, a mid-run data edit, a hash/exec swap), an unconfined evaluator context, a crash on a non-string key, `{}` filled from BASELINE, and every non-dev partition running the held-out branch | a target where routing configurations, not method configurations, carry headroom; **and** those defects fixed first |
| typed mental-model operator library (#155) | `greg/cognition/advantage.py` | superseded as a generator: every operator maps to a Foundry mechanism, seven of them ported (section 5); `compile_map` stays a read-only CLI view (`greg cognition advantage`) | decided by the crosswalk (coverage). Merit needs real maps with outcomes |
| both lineages' colliding frozen files | `docs/collaboration/lineage-archive/` | byte-identical archival copies (tested against git and the manifest's digests) | n/a: evidence |
| #155's benchmark reconciliation table | git history at `ef5f078` | superseded | n/a |

**P8 controller integrity (review of #179, M14, L5 and L6).** The canonical controller is #158's at `f8e8fd2`,
whose `af258bf` combines #155's freeze mechanism into it:
- a cycle that writes a record must match a committed freeze (trusted-code digests, rule, settings, split and both
  evaluator seals), re-checked before every evaluation;
- the parent compares the method module each sandbox imported, and probes the sandbox's confinement itself;
- choices are type-strict;
- on Landlock ABI 6 or later, every confined worker is scoped for signals and abstract sockets.

Cycle cr-4 ran under such a freeze. This branch built the same fixes in parallel (`1da022a`); that variant is
history only, because cr-4's freeze binds #158's bytes. Two latent channels remain preconditions before any
code-level candidate space is allowed: generator seeds that let a candidate regenerate labels, and truth that can
be regenerated from public generator code.

**Who adopts a P8 RETAIN (review L9, escalated).** Three mechanisms in the tree can decide improvements: the
Kernel's `evolution/loop.py` ClosureLoop, `greg/improvement.py` (which auto-retains the `brief.attention`
lever), and P8. P8 only proposes (`PROPOSED_NOT_APPLIED`), and it has no apply function; a test checks that a
synthetic RETAIN record changes no shipped configuration. The proposed rule is that adoption is a reviewed code
change, recorded as an EvolutionCapsule with a founder decision. **Founder decision needed:** confirm that rule,
or name a different adopting decider.

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
   - **Remaining duplication:** none in generation. One intervention generator (the Foundry), carrying #155's
     seven uncovered operator classes; #155's `compile_map` is a read-only view.
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
  verdicts, repertoire, dataflow derivation, Goal Gravity attach ask, the P8 rejections and destination
  backcasts.
- **Simpler alternative:** #158 alone, with #155 archived. That loses:
  - four measured REJECTED verdicts that change routing;
  - one SUPERSEDED verdict;
  - two admitted repertoire families;
  - the same-instance re-runs of P4 and F2 (reproducibility, not replication);
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
| (f) | resolved (2026-10-15): one generator; the crosswalk found seven uncovered #155 classes, now ported at the floor prior with purpose-bound consent (section 5) |
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
3. Whether the ported operator classes improve outcomes. This needs real institutional maps with settled
   outcomes; the crosswalk settled coverage only.
4. Re-admission of any operation family whose solver code changes. Each verdict is now bound to its entry function's source digest; helper functions are not covered.
5. A natural family that uses an admitted Layer 1 or Layer 2 genome.
6. F8 re-measured on the converged Mind under a fresh pre-registered freeze (its #158 freeze refuses here).

## 12. Third-party data rights: an existing distribution question and a release blocker

This repository is **public** (verified 2026-10-15) and MIT-licensed. None of the four extracts is on `main`,
but each has been on public feature branches since it was first committed. Taking it off a branch tip would not
take it out of git history. So this is already a distribution question, not only a question about a future
release.

| file | first committed | public branches carrying it (2026-10-15) |
|---|---|---:|
| `cortex/evaluation/data/m4_weekly.json.gz` | `4e84d6f`, 2026-10-08 | 16 |
| `cortex/evaluation/data/bank_calls_halfhour.json.gz` | `dd9bccc`, 2026-10-13 | 14 |
| `cortex/evaluation/data/sndlib_networks.json.gz` | `9434224`, 2026-10-14 | 7 |
| `cortex/evaluation/data/uber_nyc_2015_halfhour.json.gz` | `53082f4`, 2026-10-14 | 4 |

The founder's approval does not grant a third party's rights. For each source, the table below gives what was
verified, the three ways to resolve it, and what needs a separate decision. Sites marked "unreachable" failed
DNS from this container; their terms are unverified, not absent.

| source | verified | (a) permission or terms | (b) permitted acquisition | (c) replacement |
|---|---|---|---|---|
| SNDlib 1.0 networks (via TopoHub 1.5.1) | TopoHub's code is MIT; its package states no terms for the bundled data. SNDlib's site says a licence applies to its data and format definitions, but the text was unreachable here. | Read SNDlib's licence (Poznan University of Technology) from an unrestricted network. If it does not allow redistribution, ask its maintainers. | Fetch the networks from SNDlib at evaluation time into an untracked cache. The builder already checks the source sha256, so frozen evaluations stay verifiable. | Another topology set whose licence is verified first. None is verified yet. |
| M4 weekly series (`Mcompetitions/M4-methods`) | The repository README describes the data and states no licence; no licence file was found. The series were sampled from the ForeDeCk database. | Ask the M4 organisers for terms. | Download from the repository at evaluation time; do not commit the extract. | A forecasting corpus under a verified open licence. None is verified yet. |
| fpp3 `bank_calls` | The package's own DESCRIPTION says `License: GPL-3` (primary source). Its documentation credits the data to Jonathan Weinberg (Weinberg, Brown and Stroud, JASA 2007). | GPL-3 terms appear to allow redistribution under GPL-3. This repository is MIT, so whether a GPL-3 derived extract may sit in it, and whether the original provider's rights are covered, is a question for counsel. | Install fpp3 from CRAN at evaluation time and derive the half-hour series locally. | Call-centre arrivals under a verified licence. |
| NYC TLC Uber pickups, January to June 2015 (FOIL release, `fivethirtyeight/uber-tlc-foil-response`) | That repository has no licence statement. FiveThirtyEight's CC BY 4.0 covers only its separate `data` repository. These are public records released under New York's FOIL. | Counsel can say whether public-records status is enough for redistribution with attribution. | Fetch from the source at evaluation time. | The TLC's own published High Volume For-Hire Vehicle trip records (2019 onwards). They hold later, independent periods, which also makes them the fresh held-out source for F8's follow-up (section 15). Their terms page was unreachable here, so they are adopted only after it is read. |

Each of these remediations needs a separate decision, and none is taken here:
- **Founder or counsel:** whether to rewrite public history to remove extracts already distributed. It is
  destructive across many branches, so it is not done by an agent.
- **Founder:** whether to make the repository private while terms are resolved.
- **Founder:** contacting SNDlib's maintainers or the M4 organisers for permission. Contacting third parties is
  outside development authority.
- **Founder:** any merge to `main` or any release that carries an uncleared extract.

**Release guard (review of #179, M19).** `docs/collaboration/RELEASE-EXCLUSIONS.json` lists all 21 tracked files that
carry values derived from the four uncleared sources. That covers the four extracts plus the suites, freezes,
results, development files and logs built from them. The extracts alone are only 4 of the 21. The files stay in
git as frozen evidence. Canonical CI runs `scripts/check_release_exclusions.py` on every change, checking that
the Python package ships none of them. On a tag, it also checks the tag's source archive and fails if any listed
path is present. A test finds any new tracked file carrying the same item markers that is missing from the list.

What an agent can do without those decisions:
- keep provenance and frozen evidence intact;
- add no further uncleared extract. F8's follow-up takes its fresh data from (c) only once its terms are read;
- move toward (b): build a fetch-at-evaluation path that the existing builders already make byte-reproducible.

## 13. Acceptance gates

| gate | status | evidence |
|---|---|---|
| both lineages recoverable, evidence inspectable | met | heads above; archives; manifest; `test_mind_lineage_manifest.py` |
| frozen results unaltered | met | digest tests; archives equal `git show`; #155 runners refuse (`FROZEN_INPUT_CHANGED`) |
| every conflict has a disposition | met | map JSON (209 entries; the coverage test checks the paths, the #158 head as an ancestor, and every disposition against git) |
| the branch passes its own CI, contract, integration, security and regression tests | see the PR body for the run on the final commit | full suite plus every CI script step |
| one canonical cognition entry point | met | section 3; one `SOLVERS` table |
| alternative engines cannot silently assume live authority | met | 64 of 72 families start VERIFIED (withheld); attach is founder-only (`test_greg_competency_compiler.py`, `test_greg_cognition_genesis.py`); `check_authority_singleton.py` passes; `evolution_routing` has no runtime importer |
| the protected evaluator cannot be modified by its candidates | met | `test_greg_protected_evolution.py` (sealed-evaluator tamper refused; Landlock probe DENIED); `test_greg_evolution_routing.py` (hash-pinned evaluator) |
| no rejected P8 configuration promoted | met | nothing attached; P8 `exit_met` false (`test_frontier_backcasts.py`) |
| no NO_GAIN presented as positive lift | met | P4 row and status label; `forecast_then_allocate` NO_LIFT demoted |
| strong standalone and practitioner baselines included | met where measured | F7 PMCF and SP-upgrade; F6 weekly mean; crowd-sparse one-step vote; F7 audit |
| genome admission bound to the exact tested version | met | genomes: compiler stale guard on the genome version. #155's operation families: each positive verdict is bound to the solver's static dependency closure at the run's source commit (`greg/cognition/code_binding.py`). The closure covers the function, the repository helpers, classes and module constants it reaches, repository names imported inside a function body, names declared `global`, dotted module chains, and every top-level statement that binds or mutates a name (so an edited literal that a later statement mutates still counts). Locals are computed per method. The bound function is the one `SOLVERS` dispatched the family to at the run's commit, resolved statically, never today's target (review of #179 closure-binding findings B1, B2). A changed member routes the family as UNEVALUATED and names the member; a verdict bound to the entry function only is not trusted; negative verdicts keep their scope. Helper and constant mutations are tested, and the closures are re-derived from git. Not covered: third-party package versions, dynamic dispatch by string, data files opened by path. Round-2 review (N4): locals are per scope (nested functions, lambdas, comprehensions), top-level compound statements (try/if/for/with/del) are hashed, star imports and constant `import_module` are followed, and a non-constant dynamic import or a non-literal update of the dispatch table binds nothing positive unless the run recorded its runtime dispatch and it agrees. Six operation verdicts route positive on this tree (control, game, information, probabilistic, robust_pattern, swarm), each bound to operation admission v3's closure at `dfdcfe9`. |
| interruption and restart do not duplicate consequential actions | met in tests | `test_greg_cognition_process.py::test_cli_composition_survives_sigkill_without_duplicate_computation`, `test_greg_cognition_mission.py::test_detachment_survives_restart...` |
| Kernel, event spine, authority, shutdown and founder boundaries preserved | met | no change to `policy/`, `provenance/`, `authority/`, `greg/founder.py` or the Gate |
| no live deployment or external consequence | met | draft PR only |

## 14. Rollback

- **Primary:** close the draft PR. Nothing outside the branch `claude/greg-mind-lineage-convergence` changed.
  #155's and #158's branches and their frozen evidence are untouched by this PR.
- **Branch reset (review L18; the per-commit list given earlier did not revert cleanly):** recreate the branch at
  #155's head and re-apply only what is wanted.

  ```sh
  git switch -c trackb-rollback ef5f078            # PR #155's head, the PR's base: #155's lineage alone
  git switch -c pr158-alone 463a9d0                # #158's lineage alone (its own branch head)
  ```

  Merging #158 onto #155's head is the convergence itself and conflicts on 21 paths (round-2 review, L18); it is
  not a rollback step.

  Track B's own commits, oldest first: `2d1ddd3` (first merge), `49b2d58`, `8bbd3b8`, `6e62b59`, `e21bb5b`
  (merge), `8a43e70`, `4b445db`, `c7a7ad5`, `d3a5abd`, `1346376`, and the review-of-#179 commits after them (see
  `git log ef5f078..HEAD --first-parent`).
- **Per-step revert:** revert in reverse order from the newest commit, with `git revert -m 1` for each merge
  commit. Then rebuild the index (`python scripts/build_mind_evidence_index.py`) and run `python -m pytest -q`.
  A revert of a single middle step is not supported, because later steps build on it.

## 15. Still unverified, and escalations

**Unverified:**
- the converged Mind on a body or with a founder (VEPMC 0);
- any real-mission settlement of an admitted genome;
- reboot persistence;
- the SNDlib, M4, fpp3 and NYC TLC data terms (section 12).

**Not done here:**
- an `independently_verified` field in the inventory, backed by verifier-mutation evidence (review L21);
- a cross-lineage seed and data-identity registry that the freeze tools consult (review L3). Known overlap:
  #155's crowd-sparse seeds 3001-3040 and P6 v3's 3101-3148 sit inside the 3000-3999 range used for review and
  development work;
- an independent Systems Architect review. The other four roles were reviewed independently by the #158
  session; that role was performed by the builder (review L20);
- binding of operation verdicts to third-party package versions, dynamic dispatch and data files (the closure
  covers repository code only);
- F8's fallback evaluation: proposed to the #158 session as its one owner. A diagnostic on the exposed rows and a
  draft pre-registration are in `docs/evidence/pr155-f8-fallback-diagnostic/2026-10-15/` and
  `cortex/evaluation/pr155_f8_fallback_diagnostic/`. A claim needs fresh held-out data whose terms are read.
- an outcome evaluation of the seven operator classes ported into the Foundry (coverage is decided; merit needs
  real maps with settled outcomes).

**Escalations (founder-only):**
1. Merge of this PR, and of #155 and #158.
2. Data rights (section 12): an existing public distribution and a release blocker. History rewriting,
   making the repository private, and contacting rights holders are separate founder decisions.
3. Attaching any family. `flow_expansion_mcf` is the routed default by admission v3; attaching it is the one
   attach this record recommends.
4. Who adopts a P8 RETAIN (section 9): confirm "a reviewed code change recorded as an EvolutionCapsule with a
   founder decision", or name another decider.
5. Whether a sign disagreement between lineages' frozen verdicts should go to the founder instead of the
   finish-time rule.
6. Any accountability channel beyond preparation: a lawful basis established by counsel, then a founder-signed
   decision and the Gate. The Foundry prepares the review request only.

## 16. Product delta

Compared with either lineage alone, GREG can now:

- refuse to answer with methods that lost on held-out data in either lineage;
- recruit #155's crowd and swarm families under their measured status;
- report every family's true measured admission in `greg genomes` and in its attach asks;
- route on one digest-checked index that holds both lineages' frozen evidence;
- generate, filter and estimate in Goal Gravity's Foundry the seven intervention classes that only #155's
  unestimated operator library had:
  - incumbent integration;
  - counter-positioning;
  - verified compliance;
  - a consented supply pool;
  - a regenerative participant benefit;
  - step removal;
  - accountability, as four legal channels that end in a legal-review request.
- hold every template to one evidentiary standard, with prior-only selections labelled;
- bind every positive operation verdict to the code closure it measured;
- route budgeted capacity expansion to the single exact genome that #158's pre-registered admission v3 admitted
  (`flow_expansion_mcf`), asking the founder to attach it while the composition serves;
- refuse a release that would carry uncleared third-party data.

#158's F7 result is independently verified. The immune-system destination is back on the one Backcast GPS.

## 17. Independent review of #179: dispositions

The review (#158 session, 2026-10-15; `docs/collaboration/reviews/PR179-INDEPENDENT-REVIEW-2026-10-15.md`)
found 5 high, 20 medium and 22 low defects. Each was reproduced and then fixed with a regression test, unless
the row says otherwise.

| findings | disposition |
|---|---|
| H1 | A same-instance re-run never decides and is labelled as one: F2R decides identify_then_optimize, and #158's REGRESSION decides P4. |
| H2, M1, M2, M16 | One status function (`compiler.family_status`) serves the compiler, Genesis, the inventory and `mind_status`. Attach asks cite evidence, SUPERSEDED operations name their competitor, and the mission hook drops COMPOSITION_ONLY. M2's second fix (cortex.reason refusing COMPOSITION_ONLY) is not taken: an explicit operation request asks for that output, and geometry routing already refuses it. |
| H3, M4, M5, M6, L12 | Verifiers recompute instead of trusting the answer. L12 is covered by #158's next harness version. |
| H4, M3 | Admitted labels are reported by provenance (41 rule-admitted after round 2). DEFAULTs without a competitor route as UNEVALUATED. collective is EXPERIMENTAL by erratum and by operation admission v3. |
| H5, M15 | Recipe lifts and genome configurations bind the code they measured. A test shows no rejected P8 configuration ships. |
| M7, M8, M9, M10 | Derived chains are reachable from Layer 5, only when unambiguous. M10 is resolved by #158's part rows, and admission v3 decides the canonical genome. |
| M11, M12, M13, L2, L10, L11, L13, L15 | Spend diagnostic; like-for-like latency in an erratum beside the frozen audit; F4, F3 and F7 caveats; practitioner ties in the index; ledger erratum. |
| M14, L5, L6 | #158's `af258bf` is selected (section 9). This branch's parallel fix is history only. |
| L7, L8, L9 | The single-controller test covers every tree and dynamic import by string. The path.json and ledger overclaims are corrected. The adopting decider is escalated. |
| M17 | Fixed: `cortex/evaluation/genome_admission/run_ops_v3.py` re-admits #155's operation families on this tree under a pre-registration and a freeze that binds each solver closure. Its first run, on fresh seeds 5001-5040, replicates 14 of 17 rows and disagrees on `graph`, `robust_pattern` and `collective` (section 18). |
| M18 | #158 is merged at `f8e8fd2` and later at `10fdbab`. The map pins `10fdbab`, and a test asserts it is an ancestor. |
| M19 | Release-exclusion list, CI check and test (section 12). |
| M20 | The original runner is archived; dispositions are checked against git. |
| L1 | Pointer files in the three #155 evidence directories, and an archive README. The source manifest's #155 head and `evidence_directories` are not edited (#158 owns that file). |
| L3 | Map note corrected. The seed registry is not built (section 15). Frozen `pr155-` prefixes keep their identity; new convergence evaluations here use the `pr155-` prefix only for work on #155's lineage. |
| L4 | `cognition.seed.solve` is dispositioned (section 3). |
| L14 | Mechanism-level map note on `genomes/flow.py`. |
| L16, L17 | Procedure in the pointer files: extract the tree at the freeze commit. Every frozen runner of both lineages refuses at this head. P6 v1's freeze and results landed in one commit (`e450218`), and the run's `source_commit` lacks the runner. |
| L18 | Rollback rewritten as a branch reset (section 14). |
| L19 | `advantage.py` is classified unresolved, and the CLI labels it a historical view. |
| L20 | The Systems Architect role is recorded as not independently reviewed (section 15). |
| L21 | Escalation 3 is replaced by the pre-registered admission verdict; the omitted items are added to section 15. |
| L22 | The developmental-sweep result is pinned by sha256 in a test. |

**Closure-binding review (#158 session, comment on #179, 2026-10-15).**

| finding | disposition |
|---|---|
| B1 (high) | Fixed. The builder resolves `SOLVERS[family]` statically at the run's commit, including `T[k] = f`, `T.update({...})`, an imported dict literal and `__import__(...).f`. It binds that function's closure. `operation_status` routes a family whose dispatch changed as UNEVALUATED. Regression: re-pointing `control` to `graph`, then rebuilding, no longer keeps the verdict (on PR #184's tree the regression re-points `swarm`, the positive verdict still in force there, section 24). |
| B2 (medium, latent) | Fixed, with all six cases as regressions: in-body imports, a later subscript mutation, `.update(...)`, `global`, dotted chains and per-method locals. |

**Consequence, stated rather than hidden.** With the complete closure, every recipe lift measured on a lineage's
freeze commit is stale on this converged tree. `track_then_staff` (F8) is now stale too, because the compiler,
composition and genesis it reaches have changed since #158's freeze. Recipe lifts therefore route as UNEVALUATED,
and `mind_status` reports them as BUILT, until a fresh pre-registered run measures the converged Mind. All nine
positive operation verdicts keep their status: their dispatch and closures are unchanged since their run.
Non-literal table updates (the genome comprehension) are counted, not resolved. They cannot rebind a literal key
they do not name.

## 18. Operation-family re-admission on the converged tree (review M17)

- **Harness:** `cortex/evaluation/genome_admission/run_ops_v3.py`. It imports v1's, v2's and the sparse-crowd
  benchmarks and v1's frozen status rule unchanged, and its freeze binds the static dependency closure of every
  family's dispatched solver. It refuses on a dirty tree or on any changed input.
- **Pre-registration and freeze:** `prereg-ops-v3.json` at `1213394`; `freeze-ops-v3.json` at `dfdcfe9`. It ran
  once, in a clean detached worktree at the freeze commit, under `python -I`, on seeds 5001-5040.
- **Evidence:** `docs/evidence/greg-operation-admission/2026-10-16-v3/`.
- **Result:** 14 of 17 rows replicate #155's statuses. Three disagree, and both readings are kept in history:
  - `graph`: DEFAULT became EXPERIMENTAL. Only 4 items are discordant, 4-0, p = 0.0625.
  - `robust_pattern`: EXPERIMENTAL became DEFAULT. It beats the baseline 14-5 and ties Rosner's ESD.
  - `collective`: EXPERIMENTAL, against the baseline that knows hidden accuracies. This agrees with the M3
    erratum.
- **Observation outside the rule:** on sparse crowds the one-step weighted vote beats Dawid-Skene 27-12
  (p = 0.012).
- **Routing:** the index appends the run after #155's three runs, so the latest reading routes. `graph` now
  routes as EXPERIMENTAL and `robust_pattern` as DEFAULT. Every positive reading is bound to the closure measured
  at `dfdcfe9`.
- **What it closes:** a drifted operation family can now be re-admitted, not only demoted. Re-running under a new
  freeze path is the procedure; nothing attaches.


## 19. Round-2 re-verification of #179 (from the #158 session, at `e413cae`): dispositions

The re-verification found the re-merge of #158 clean and all 333 frozen files byte-identical. Every new
defect was reproduced, then fixed with a regression test that fails on the old code, or answered.

| item | disposition |
|---|---|
| N1 (high) crowd verifier bypass by claiming non-convergence | Fixed. The verifier re-runs EM from the soft-majority start and compares iterations, posteriors and the fitted model. The forgery verified on 10 of 10 dev seeds before and is refuted on all now. |
| N2 (medium) collective, organ and derived-chain status differed by surface | Fixed. `admission_of`, the inventory, `greg genomes` and the mission hook read the compiler's routed status. Organ labels and `composition.derived` take the compiler's status and keep their lineage reading as a note. |
| N3 (medium) release check bypassed by renamed, nested, deep or wheel members | Fixed. Every listed file carries its sha256. A member is blocked by digest (also after gunzip), by path suffix or by a data marker, at any archive depth. Each bypass is a test. |
| N4 (low) closure gaps | Fixed. See section 13 (G11 row): per-scope locals, module-level compound statements, star imports and constant `import_module` are followed. Unresolved code binds nothing positive unless a recorded runtime dispatch confirms it. Eight regressions. |
| N5 (low) recipe binding too broad and repeating B1 | Fixed. `recipe_code` resolves `OPERATION_RECIPES` at the measured tree and stops at `cortex.reason` and `reason_cortex`. `track_then_staff` binds 20 members, not 568, and a docstring edit in `code_binding` no longer stales it. |
| N6 (low) "every frozen runner refuses" | Corrected in the three `LINEAGE-POINTER.md` files: `developmental_sweep/run.py` would run, and its result is pinned by sha256 (L22). |
| N7 (low) stale counts | Corrected (section 3, genome row; section 13, G11 row; section 17, H4 row). |
| L14 regressed in `6eaccfa` | Restored on `greg/cognition/genomes/flow.py`'s map entry, now citing F7 v6. |
| M5 residual: blackbox under-reported count | Fixed. The verifier re-runs the declared differential evolution from its seed on its own objective and compares count and fitness. |
| L7 residual: split string literal | Fixed. Constant-folded strings are scanned; three split forms are a test. |
| L9: cited test missing | Fixed. `test_a_synthetic_retain_record_changes_no_shipped_configuration` now exists. |
| L18: rollback merge conflicts | Corrected (section 14). |
| L10: "development evidence only" | Corrected (section 8). |
| L1, L8 (manifest, P8 backcast) | #158's own fixes (`ba1863d`, `463a9d0`), merged here at `463a9d0`. |
| L3 (seed registry), L5 (generator seed in sandbox data, latent for data-only candidates), L20 (no independent Systems Architect) | Open, as before. L5's channel is #158's P8 code and stays a precondition before any code-level candidate space. |
| M17 | Fixed (section 18). |

## 20. Round-3 re-verification of #179 (from the #158 session, at `65e20fa`): dispositions

The re-verification found N1-N7, L14, M5, L9 and M17 fixed and L7 fixed for the reported form. None of its
five new findings routes wrongly today. Each was reproduced and fixed with a regression test, or its limit is
stated.

| item | disposition |
|---|---|
| 1 (medium, latent): a recipe binding does not cover its stage genomes | Fixed. `recipe_code` now also binds `stage_closures`: the solve closure of every genome that can serve one of the recipe's stage operations, in the measured tree. An edit inside `erlang_solve` stales `track_then_staff` (test). All 7 recipe verdicts already route UNEVALUATED. |
| 2 (low, latent): a disagreeing runtime dispatch is ignored; several table mutations are read as resolved | Fixed. A runtime record that disagrees with the static dispatch binds nothing (`runtime_disagrees`). Any other module-level touch of the table counts as unresolved: a loop, an `if`-block, `\|=`, `pop`/`setdefault`, `__setitem__`, `del`, or a helper function that mutates it. Six forms are tests. |
| 3 (low): transformed copies pass the release check | Fixed for recompression and reformatting. Members are decompressed through gzip, xz and bz2, and JSON is compared by canonical digest under any extension. Markers are scanned in every member, so a minified copy under `.dat` and an xz or bz2 copy are blocked (tests). **Stated limit:** values re-encoded into another format (a Python literal, a CSV re-export, a subset of rows) are out of scope for an automatic check and need human review of what a release contains. |
| 4 (low): the crowd verifier accepts a total abstention | Fixed. An abstention is accepted only where the declared `min_posterior` threshold abstains; an honest thresholded abstention still verifies (tests on 10 dev seeds). |
| 5 (low, L3): operation-admission seeds are not spent | Fixed for the converged harness. `spent_seeds()` reads `freeze-ops-v*.json`, so 5001-5040 are refused by later admissions and P8 splits. #155's earlier operation ranges (1001-1040, 2001-2040, 3001-3040) are not registered. They used other generators, so no instance was reused, but registering them would contradict #158's existing genome and pilot seeds; the overlap stays recorded under L3. `admission.py` is #158's file, and this extension is proposed to #158 for adoption. |
| L7 residual (variables, `%`, slicing) | Stated as a limit of a static scan in the test. The guarantee checked is that no runtime module imports `evolution_routing` in any form that folds to a constant. |
| L9 weak (candidate equals incumbent) | Strengthened. The synthetic RETAIN now proposes a real configuration change (`p_restart`). |
| M17 note: the index binds closures recomputed at `dfdcfe9` with the current resolver, not the freeze's digests | Accepted and stated here. The freeze bound the closures under the resolver of that day; the index recomputes them under today's stricter resolver at the same commit. This is stricter than the pre-registration says. A verdict whose closure would differ under the old resolver is not admitted by this rule, never the reverse. |
| `swarm` vs competitor 17-21 recorded, 17-20 from 9-decimal `per_item` | A rounding near-tie in the recomputation; the frozen result is unchanged and the status does not depend on it. |

## 21. Round-4 re-verification of #179 (from the #158 session, at `0067be6`): dispositions

The re-verification found round 3's findings 2a, 4, 5, L7 and L9 fixed, and 2b and 3 fixed as reported. It found
finding 1 partly fixed. None of its new findings routes wrongly today.

| item | disposition |
|---|---|
| A (medium, latent; finding 1's residual): operation-family and organ stages outside the recipe binding | Fixed. `stage_closures` now also binds every `SOLVERS`-served family whose catalog operations a recipe stage uses (dispatched at the measured tree): `bayes_then_voi`'s `probabilistic` and `information`, and the `optimization` family under `graph_then_allocate` and `forecast_then_allocate`. It also binds the cortex organs that serve the template recipes' stage classes (`STAGE_ORGANS`). An unmapped class binds None, which fails closed. Every recipe's stages are bound and non-empty (test). An edit to `solvers.py::information` stales `bayes_then_voi` (test). Record section 20's earlier "fixed" covered genome stages only. |
| B (low, latent): further `dispatch()` mutation forms read as resolved | Fixed by failing closed. Any module-level statement outside the recognised literal forms that names the table counts as unresolved, except a plain read (`T[k]` in load context, the read-only methods, `k in T`, iteration). That covers the table as a name, an argument, an alias, `dict.update(T, ...)`, a string reaching `globals()`, a class body, a lambda and a list display. Twelve forms are tests. A positive binding then needs the run's recorded runtime dispatch to agree. |
| C (low): lzma-alone, zlib, base64 and UTF-16 copies pass the release check | Fixed. Up to six decoding layers are tried: gzip, xz, lzma-alone, bz2, zlib, base64 and UTF-16 (four tests). The stated limit now names every encoding not decoded. |
| D (low, regression, fails closed): the marker scan flags ordinary source | Fixed. Python source is exempt from the marker rule; a renamed data copy is still caught by digest. A tar of every tracked `.py` file passes (test). |
| #158 merge | #158 is merged at `050c1b2`: P8 cycle 6 RETAIN (PROPOSED_NOT_APPLIED) and its canary (section 1). |

## 22. Composition and metacognition lane (directive 2026-10-21): converged recipe lifts, credit and calibration

Lane agreement: #158 owns the evaluator audit, the P8 successor, the coverage reconstruction and the whole-machine
trace. This branch owns composition and metacognition and integrates both.

| item | disposition |
|---|---|
| Recipe verdicts carried over from lineage freezes | Re-measured. P6 converged v1 ([evidence](../evidence/greg-composition-lift/2026-10-21-converged/README.md)) measured F1, F2R, F3 and F4 on fresh held-out seeds against the strongest single available, under a freeze binding each recipe's complete code. It was pre-registered at `d90cd6fb`, frozen at `53d39d76` and run once. **Converged VPL is 2 of 4:** F2R lifts (16-2) and F4 lifts (15-0). F1 is NO_LIFT: 35-0 on correctness, but one false answer that the conservative single does not make. F3 is NO_LIFT, tied by `flow_expansion_mcf` at about a fifth of the latency. The index now routes these four recipes on these verdicts. The three natural-family recipes stay UNEVALUATED, because their held-out data were already looked at. |
| Compiler defect found by the development check | Fixed before the freeze. With every recipe UNEVALUATED, the Fermi organ tied `estimate_then_optimize` on status, won on the method name, ignored `formal_template` and abstained. `_reject_recipe_relaxations` is the fixed-recipe twin of the derived-chain rule: an organ or method reading a strict subset of a routed recipe's inputs is rejected, while admitted twin genomes still compete. A regression test covers it. |
| Trace gap 1 (from #158): settled outcomes alone never changed a decision | Fixed. `_settled_preference` compares the evidence-ranked first fit with each undemoted fit. It needs at least 10 settled outcomes on both sides and uses a one-sided Fisher exact test, Holm-adjusted p < 0.05; neither threshold is lowered. The receipt records the test, and the choice is labelled `preferred_by_settled_outcomes`, with dissent. Stated limit: outcomes are pooled over a method's versions and geometries, as the inhibition rule pools them. |
| Trace gap 2 (from #158): a formed mechanism's compile receipt lacked its basis | Fixed. The compile receipt now carries the settled outcomes of each formed mechanism considered (`conditional_competence_basis`) and the mechanism receipt's strongest counterargument as dissent. |
| Calibration | Unchanged and open. Forecast calibration is live (`greg cognition calibration`). Per-method confidence calibration on the compiler path has no settled data yet; it is not claimed. |
| Acquisition targets in the coverage record (one-step weighted vote, multistart L-BFGS-B) | Handed to #158's repertoire lane, with admission seeds from its reserved ranges. |

## 23. Round-5 re-verification of #179 (from the #158 session, at `a3106f6`): dispositions

The re-check found round 4's A, B and C fixed as reported and D partly fixed, with one regression. None of its new
findings routes wrongly today.

| item | disposition |
|---|---|
| N1 (low, regression): the `.py` exemption lets an edited data copy through | Fixed. Only a `.py` member byte-identical to a tracked Python source file is exempt from the marker rule. Parsing as Python was rejected as a test, because JSON parses as Python. The reviewer's repro (`suite-v4.json` plus one key, as `x.py`) is blocked again (test). |
| N2 (low): a data-free tag archive is blocked by the exclusion list's own markers | Fixed. The list itself, byte for byte, is exempt from the marker rule; an edited copy is still scanned. A tar of every tracked file minus the listed ones passes (test). |
| N3 (low): the committed index was not byte-reproducible, and nothing checked it | The index was rebuilt in `d873b64f` and again here. A test now rebuilds it into a temporary path and requires the committed bytes. |
| N4 (low, latent): variants of A | Fixed. Recipe bindings now also cover the genome-stage runtime adapter (`solvers._genome_solver`, `library.run`) and a digest of every module-level statement naming `SOLVERS` (`code_binding.table_statements`), so an appended comprehension stales the recipe. For template recipes, they cover the route policy (`cortex.routing._route_parts`) and every organ class `cortex.routing` imports, derived rather than hand-copied. Each named edit stales its recipe (test). The four P6 converged v1 verdicts still bind: the newly bound code is unchanged since their freeze. |
| N5 (low, latent): variants of B | Fixed. `dispatch()` counts as unresolved: `update` with keywords or extra arguments; a literal `T[k] = ...` whose value names the table or whose target reaches into an entry; a keyword or attribute named like the table (`globals().update(T=...)`, `sys.modules[__name__].T`); and any assignment or deletion whose target is rooted at the table outside the literal form (`T['k'].__code__ = ...`). Eight forms are tests. |
| N6 (informational): further encodings pass | Stated. The module docstring now names each encoding not decoded, and the six-layer cap. |
| #158 merge at `fa0d92a0` (green in CI, run 39648661029) | Brings the natural-ops family, L3 batch D and the one-step crowd vote (the coverage record's acquisition target), the exact node cut, the immune-8 NOT_VIABLE record, the data-exposure ledger, the founder decision packet and the whole-machine trace script. `foundry/owned-source.json` conflicted and was regenerated with `scripts/refresh_owned_source.py`. The map is pinned to `fa0d92a0`. The merge added two modules to the genome registry tuple `library.MODULES`, which N4 had just bound through `library.run`, and so staled every genome-stage recipe. The registry tuple is now excluded from the adapter digest (`compiler.ADAPTER_REGISTRY`). It decides only which genome serves a family, and each stage family is bound by its own solve closure, so a registry change that reaches a stage still stales the recipe. A change to `run` itself still stales it (test). The four P6 converged v1 verdicts bind on the merged tree. |
| #158's data-exposure ledger on the converged tree (4 failures after the `fa0d92a0` merge) | Fixed. Three changes: (1) The ledger tool read HEAD as #158's tree, so on #179's tree every #179 artifact counted as #158's and #179's newer runs were missed. Where the reconciliation map's `pr158` commit is an ancestor of HEAD, it now reads #158's tree at that commit and #179's at HEAD. Regenerated, all 13 ledger tests pass, and the P6 converged v1 seeds appear as #179 exposures. (2) `mind_status`'s `lineage_179` claimed "this line neither runs that code nor routes on #179's index", which is false on #179's own tree. Where this tree's index lists the run, it now reports `in_this_index` and adds no duplicate rows. (3) The ledger cites SNDlib network names (`abilene`), a release marker. The exclusion list gains `provenance_only`: a declared provenance record is exempt from the marker rule only byte-identical to its tracked file; an edited copy is scanned (test). Both tool changes should be adopted on #158 or replaced there. |
| #158 merge at `98a2ab0c` (green in CI, run 39693118401) | Brings admission v5-v7, the develop_repair P8 target and hybrid genome, and the formal, evo and search lanes. #158 adopted this branch's ledger and `mind_status` changes at `93667efc`; the conflicts differed only in a provenance comment and take #158's wording. The evidence index, owned-source inventory and exposure ledger are regenerated with their tools, and the map is pinned to `98a2ab0c`. Two follow-ups. (1) `scripts/admission_readme.py` used a Python 3.12 nested-quote f-string, which does not parse on CI's Python 3.11. It is fixed here and reported to #158; no freeze binds the script. (2) The provenance test recognised only admission directories dated `2026-10-1x` and now accepts any dated pre-registered genome admission. The four P6 converged v1 verdicts still bind. |

## 24. On PR #184's tree (2026-10-16): four operation verdicts await re-admission

**Numbering (merge of PR #189 into PR #192, 2026-10-22).** This section and the next were sections 18 and 19
on PR #184's tree, while the Track B line used 18 to 23 for the sections above. Both sets are kept; these two
are renumbered 24 and 25, and only their cross-references changed. Where
`docs/evidence/one-machine-ten-steps/2026-10-15/README.md` (items 14 and 15) and
`docs/intent/INTENT-20261014-FABLE-OPUS-MAXIMUS.json` cite this record's section 18 or 19 for the four operation
verdicts, they mean sections 24 and 25. On the joined tree two re-admission runs bear on control, game,
information and probabilistic: operation admission v3 (section 18, freeze `dfdcfe9`, measured on Track B's
solvers, seeds 5001-5040) and the 2026-10-21 run (section 25, `462bd98`, measured on #159's native-qualified
solvers, seeds 2600-2629). Which reading routes is decided by the code binding against the joined tree's
solvers in the regenerated evidence index, not by this record.

The sentence at the end of section 17 ("All nine positive operation verdicts keep their status") was true of
this lineage when it was written and is kept as written. PR #184 joined this lineage (Track B, #181 `79c38f8`
containing #179 `c6c4d74` and #180 `e4674f9`) with the one-machine trunk (#178, #175, #169), whose #159
native-qualified solvers changed the four solver functions in `greg/cognition/solvers.py` (`control`, `game`, `information`, `bayesian`). They also added
helpers (`_native_source`, `_request`, `_work`) that bring the unchanged `contracts.canonical`, `contracts.digest`
and (for control, game and information) `contracts.integer` into those closures. (Corrected after the fourth review,
R2: this paragraph first said the contracts functions changed; their digests are identical on both trees, and
`operation_status` now reports newly reached members apart from changed ones.) The code binding (`c6c4d74`)
therefore routes the control, game, information and probabilistic verdicts as UNEVALUATED on that tree, each naming
the changed solver function, the newly reached members and "needs re-admission"; swarm keeps DEFAULT_FOR_GEOMETRY, and the four baseline-only verdicts (micro, exact, graph,
sequential) stay UNEVALUATED as before. The binding was not weakened.
`tests/unit/test_greg_mind_convergence.py::test_the_pr184_merge_leaves_four_operation_verdicts_awaiting_re_admission`
records the state and fails once they are re-admitted. Re-admission is a new pre-registered genome-admission run on
fresh held-out seeds against the merged code (the 2026-10-15-v3 procedure); it has not been run.

## 25. Re-admission of the four operation verdicts on PR #184's tree (2026-10-21)

Section 24's "it has not been run" is kept as written; it was true on 2026-10-16. Next-wave item 2 built the live
harness section 15 said was missing: `cortex/evaluation/genome_admission/run_operations.py` wraps #155's four
generators and arms verbatim (dev-seed parity with #155's `BENCHMARKS` is a unit test), declares one change (compute
limit 100000, the merged native ceiling; #155's 200000 crashes every merged solver), scores every candidate output
through `greg.cognition.verification.verify`, and runs under the canonical genome-admission rule, with #155's
`status()` recorded beside it and never routed. A review of the runner found two defects before any held-out draw,
both fixed with tests in `1d37418`: a negative start aliased spent seeds (`random.Random(-s)` seeds as `s`), and a run
was not bound to a committed freeze. The run is refused unless its `freeze.json` is committed at HEAD unchanged and
the tree is clean outside its directory; the evidence index routes a run that was not pre-registered as UNEVALUATED.

Pre-registered at `462bd98` on fresh seeds 2600-2629 (1300-1329 was abandoned before any draw: seed 1311 is a frozen
cross-geometry item), run once at that commit pinned to one core
(`docs/evidence/greg-genome-admission/2026-10-21-operations/`):

| Family | Status (routes) | #155's rule | vs baseline | vs #155's competitor |
|---|---|---|---|---|
| control | DEFAULT_FOR_GEOMETRY | DEFAULT_FOR_GEOMETRY | 28-2-0 | 30-0-0 |
| game | DEFAULT_FOR_GEOMETRY | DEFAULT_FOR_GEOMETRY | 30-0-0 | 22-0-8 |
| information | DEFAULT_FOR_GEOMETRY | DEFAULT_FOR_GEOMETRY | 16-0-14 | 14-0-16 |
| probabilistic | **EXPERIMENTAL** | EXPERIMENTAL | 16-11-3 (p = 0.22) | 15-12-3 (p = 0.35) |

Control, game and information route again at the closure they were measured on. Probabilistic's 2026-10-14 DEFAULT
(seeds 1001-1040) did not replicate on fresh seeds; it leaves routing, an outcome the pre-registration put at about
0.20 and accepted in advance. The arms are #155's, weaker than the library's strongest competitors (`pid_simopt`,
`game_lp_dual`, `bayes_interval`), so the genome library labels these `operation_readmitted`, never `rule_admitted`.
The merged control and game solvers are about 50x and 1,600x slower than #155's competitors at the median; the
verdicts rest on quality. The binding test that recorded section 24's state is replaced by
`test_the_four_operation_verdicts_are_re_admitted_on_the_merged_solvers`, which also checks that the 2026-10-14
verdicts, read alone at the merged code, still need re-admission.

## 26. On the joined tree (#196, 2026-10-22): what routes, measured rather than inferred

Integration candidate 2 (draft #196) joins #192 (#178 and #184) with Track B (#189), #179 and #158. Sections 24 and
25 describe #184's tree and are kept as written; this section records what the joined code routes. Every line below
comes from a command run on the joined tree at `ea90b4b4` (`compiler.recipe_stale`, `scripts/mind_status.py`, the
rebuilt evidence index), compared with #179's own head `866d4770` where stated.

| Verdict | Recorded (index) | Routes on the joined tree | Why |
|---|---|---|---|
| control, game, information (2026-10-21 run, `462bd98`) | DEFAULT_FOR_GEOMETRY | **UNEVALUATED** | "cannot be bound to its code: 1 non-literal update(s) of the dispatch table at the run's commit, and the run recorded no runtime dispatch that confirms it" |
| probabilistic | EXPERIMENTAL | EXPERIMENTAL | section 25's non-replication |
| recipe lifts F2R `identify_then_optimize`, F4 `bayes_then_voi` (P6 converged v1) | VPL_LIFT | **stale (UNEVALUATED)** | "the recipe code has changed; needs re-measurement" |
| recipe lifts F6, F8 and the four NO_LIFT recipes | as recorded | stale | the same, and already stale on #179's head |

Section 25's sentence "Control, game and information route again at the closure they were measured on" held on
#184's tree. On the joined tree Track B's stricter binding (a run that recorded no runtime dispatch cannot vouch for a
dispatch table updated non-literally) applies to that run, and the binding was not weakened to keep them routing.

**Live VPL on the joined tree is 0.** On #179's head it is 2 (F2R and F4 bind live there). The join changed the code
those lifts were measured on: the grant-window guard in `cortex.reason` (#184's COG-5), the composition stages and the
information and probabilistic stage solvers (#159). This is a measured cost of the integration, kept as such.

Next, pre-registered and run once each on the joined code, with fresh held-out seeds (bands 4000-4999 and 5100-5999,
checked against `spent_seeds()`, every freeze and the exposure ledger): P6 joined v1 (the four synthetic families,
v1's procedure and rule unchanged) and an operation re-admission of control, game, information and probabilistic
that records the runtime dispatch the binding needs. Their verdicts, including any NO_LIFT or non-replication, are
added here when run.

Also observed on the joined tree: the body package `greg` (69 modules; 47 on #179's tree) exceeds
`cognition.optimization`'s declared 64-variable model ceiling, so the Mind abstains on its own body's critical path
(MODEL_INVALID). The whole-machine trace's mission 2 now plans the runtime package `egregore`, and the body package is
an abstain-never-wrong control. The admitted CPM genome `solver.or.critical_path` (DEFAULT_FOR_GEOMETRY, v3) has no
such ceiling, but it is withheld until the founder attaches it.

**P6 joined v1, run (2026-10-22).** Pre-registered at `aaaa1c26`, frozen at `8d81f342`, and run once on fresh
held-out seeds 4640-4902, with results in `docs/evidence/greg-composition-lift/2026-10-22-joined/`. The procedure and
rule are v1's, unchanged. Results:

| Family | Recipe | Verdict on the joined code |
|---|---|---|
| F1 | `estimate_then_optimize` | **LIFT**, 35-0 (0 wrong, 1 suboptimal). Converged v1 read NO_LIFT on one false answer. |
| F2R | `identify_then_optimize` | **LIFT**, 13-2. The composition made 4 wrong answers; the best single made 15. |
| F3 | `graph_then_allocate` | NO_LIFT. `flow_expansion_mcf` ties it on 40 of 40 at 0.234 s against 1.206 s. Converged v1 agreed. |
| F4 | `bayes_then_voi` | **LIFT**, 20-0 |

After the index rebuild, `compiler.recipe_stale` is None for all four recipes. **Live VPL on the joined tree is 3**:
it was 0 at `ea90b4b4`, and on #179's head it is 2. Converged v1's verdicts stay in each recipe's history, marked
stale. The natural-family recipes (F5-F8) are still stale on the joined code. The exposure ledger has 451 records,
with no overlap involving held-out data.

**Operation re-admission on the joined tree, run (2026-10-22).** Pre-registered at `244b652c` and frozen at `3520efe6`.
It ran once on fresh seeds 5920-5949, in a clean detached worktree. Results are in
`docs/evidence/greg-genome-admission/2026-10-22-joined-operations/`. The runner now records, per family, the solver
function every candidate call reached, and that dispatch equals the frozen closure for all four families.

| Family | Verdict | Against the baseline | Against the competitor |
|---|---|---|---|
| control | **DEFAULT_FOR_GEOMETRY** | 30-0 | 30-0 |
| game | **DEFAULT_FOR_GEOMETRY** | 30-0 | 21-0-9 |
| information | **DEFAULT_FOR_GEOMETRY** | 17-0-13 | 13-0-17 |
| probabilistic | NICHE_CAPABILITY | 17-6-7, p 0.017 | 13-10-7, p 0.34, and slower |

Control, game and information replicate and route again: the binding rule is satisfied, not loosened. On
2026-10-21 probabilistic read EXPERIMENTAL. Here it reads NICHE_CAPABILITY, which is a second reading, not a
replication, and it is kept as such. No candidate output was refuted.
