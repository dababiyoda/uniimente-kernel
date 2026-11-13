# Independent review of draft PR #179: convergence of the two GREG Mind lineages (Track B)

> **Scope.** This independent review covers draft PR #179 at head `ccd38a2`. It was produced by the PR #158 session (`session_01GRT2jX7cQXwvMkn64ZgvLk`), which holds the Adversarial Reviewer and Evidence/Welfare Guardian roles. Six separate lenses ran from 2026-10-14 21:15 to 2026-10-15 02:34 UTC: evidence guardian, routing/authority adversary, evolution adversary, F7 cross-audit, composition, and operator/founder-intent steward. Their reports were synthesised into this text. Probes and scratch scripts are cited by their paths in the review container; they are not committed.
>
> **Later #179 commits, checked by commit message only, not by a lens:**
> - `c7a7ad5` binds #155's operation-family verdicts to the source digest of the measured solver function. This addresses the operation half of H5 at function level; the #179 session reports a static dependency-closure binding is coming. Recipe verdicts remain unbound.
> - `e19226a` merges #158 `41a8538`, which narrows M18. The remaining #158 fix branches (genesis, pack B, pack C and the solo compiler work) are not merged yet.
>
> No lens tested `c7a7ad5` or `e19226a`.


**Verdict: not ready to leave draft. It does not yet meet the founder's acceptance gates.** The preservation work is sound:
- every frozen result is byte-identical to its lineage commit;
- both lineages can be recovered from git and from the byte-identical archive;
- at runtime there is exactly one solver dispatch table and one P8 evolution controller;
- attach stays founder-only, and no rejected P8 configuration is shipped;
- the restart and no-duplicate tests pass;
- canonical CI was green at `ccd38a2`.

Six independent review lenses found 47 distinct defects after deduplication: 5 high, 20 medium and 22 low. The defects fall in four groups:
- **Founder gates not met.** Three gates fail:
  - Genome admission is not bound to the exact tested version for #155's operation families or for recipes (G11).
  - Strong standalone and practitioner baselines are missing where relevant (G10).
  - Not every conflict has a disposition, because #158 has moved 13 commits past the base this PR reconciled (G3).
- **The data-rights clause is not met.** Frozen suites, results and logs carry the same third-party data as the three listed extracts, and nothing executable keeps them out of a release.
- **The independent-verification requirement fails.** The directive requires every retained intelligence to run through independent verification, but a Dawid-Skene crowd answer that is wrong on 24-30 of 30 items still verifies.
- **The evidence is described wrongly in two places that change decisions:**
  - The cross-lineage "replications" of P4 and F2 re-measure the same instances, and under "latest run decides" the smaller re-run now decides each row.
  - Capability Genesis offers families the index marks REJECTED or SUPERSEDED to the founder as UNEVALUATED attach candidates.

The builder's record marks G11 and several directive items as met. The lenses disagree, and the evidence is below.

## Findings

| ID | Severity | Title | Location | Gate | Lenses |
|---|---|---|---|---|---|
| H1 | high | The P4 and F2 "replications" re-measure the same instances; the smaller run now decides each row | `docs/collaboration/MIND-LINEAGE-RECONCILIATION-2026-10-14.md:124,154`; `scripts/build_mind_evidence_index.py:37-43` | T5, G2 (meaning), no fabricated progress | EG, CO |
| H2 | high | Capability Genesis offers REJECTED and SUPERSEDED operation families as UNEVALUATED attach candidates | `greg/genesis.py:754` | G6 (decision surface), G3 | AR |
| H3 | high | The crowd (Dawid-Skene) verifier accepts a total forgery | `greg/cognition/verification.py:171-188` | T7 (independent verification), G4 (security) | AR |
| H4 | high | "36 admitted" mixes provenance; #155 DEFAULT verdicts route at rank 0 without competitors or git pre-registration | `greg/cognition/genome_library.py:84-93`; record `:122` | G10, R | EG |
| H5 | high | Operation and recipe verdicts route with no binding to the measured code; the gate is marked "met" | `greg/cognition/compiler.py:387-392`; record `:369` | G11 | EG, AR, OS, CO |
| M1 | medium | Attach asks for operation families cite no evidence; SUPERSEDED rows name no acquisition candidate | `greg/cognition/compiler.py:670-674` | G6 (informed decision) | EG, AR |
| M2 | medium | The #155 mission ask hook recommends attaching COMPOSITION_ONLY genomes | `greg/missions.py:992` | G6, G5 | AR |
| M3 | medium | collective's REJECTED verdict comes from a loss to an oracle baseline and is misdescribed | `cortex/evaluation/genome_admission/run.py:168` | G10 | AR |
| M4 | medium | The robust_pattern verifier skips the flag check when MAD == 0 | `greg/cognition/verification.py:167` | T7 | AR |
| M5 | medium | swarm/blackbox verification is common-mode with the solver; an under-reported evaluation count verifies | `greg/cognition/verification.py:189-196` | T7 | AR |
| M6 | medium | The optimize verifier checks feasibility only; the chain drops solver status | `greg/cognition/verification.py:83-97`; `greg/cognition/composition.py:209,222` | T7 | F7 |
| M7 | medium | The Layer-5 compiler cannot reach #155's derived chains (it plans Fermi; executed, it abstains with no deficit) | `greg/cognition/compiler.py:424-426` | T7 (single interface), G5 | AR, CO |
| M8 | medium | derive() overrides the ambiguity refusal and silently drops an operation recipe's geometry | `greg/cognition/composition.py:372-374` | G3, G4 | CO |
| M9 | medium | Dataflow derivation has no executable test coverage | `greg/cognition/composition.py:113-123` | G4 | CO |
| M10 | medium | Admitting flow_expansion_mcf cannot make it canonical for F7-shaped requests | `greg/cognition/compiler.py:393,426` | T7, T5 | F7 |
| M11 | medium | The F7 tie is on throughput only; the composition spends budget on idle leases | `cortex/evaluation/composition_lift/run_v4.py:224-238` | G10, T5 | F7 |
| M12 | medium | "About 300x faster" compares non-comparable latencies and credits the wrong mechanism | `docs/evidence/pr155-f7-audit/2026-10-14/README.md:66`; record `:195` | G9 (lift accounting) | F7, CO |
| M13 | medium | The F4 lift is listed without its caveats; worlds.py misstates its truth basis | `greg/cognition/worlds.py:91`; record `:171` | C, G10 | CO |
| M14 | medium | The canonical P8 controller kept #158's integrity gaps and did not take over #155's freeze mechanism | `greg/cognition/evolution.py:289-301,397-400` | G7, FZ | AE |
| M15 | medium | "No rejected P8 configuration promoted" is untested; a promotion keeps its admitted status | `tests/unit/test_greg_protected_evolution.py:39-40`; `greg/cognition/genome_library.py:160-164` | G8, G11 | AE |
| M16 | medium | Admission truth is still plural (mind_status, ORGAN_ADMISSION, the SUPERSEDED mapping) | `scripts/mind_status.py:262-266`; `greg/cognition/genome_library.py:81-91` | G3, R | EG, AR |
| M17 | medium | Two executable-intelligence contracts; no live harness can re-measure the routing operation families | `greg/cognition/repertoire.py:261`; `greg/cognition/genomes/admission.py:261` | G11, one canonical Mind | OS |
| M18 | medium | The reconciliation is pinned to #158 `047549f`; #158 is 13 commits ahead with 5 textual conflicts | `docs/collaboration/MIND-LINEAGE-RECONCILIATION-MAP-2026-10-14.json:5` | G3 | OS, CO |
| M19 | medium | The release blocker lists three extracts, but frozen files embed the same data and nothing enforces exclusion | record `:337-356` | D | EG |
| M20 | medium | #155's frozen P8 runner was edited at its original path; two "kept" dispositions are false | `cortex/evaluation/evolution/run.py:29-30`; map `:195-199` | G2, G3 | EG, AE, OS |
| L1 | low | #155 evidence directories point at collided paths; the archive has no README; the manifest is stale | `docs/evidence/greg-learned-routing/2026-10-07/README.md:83-85` | G1 | EG |
| L2 | low | Merged ledger text and the VPL headline overstate lift | `docs/FOUNDER_INTENT_LEDGER.md:103`; record `:179` | G9, C | EG, OS |
| L3 | low | Map inaccuracies, a seed-namespace hazard and a misleading `pr155-` prefix | map `:531-535` | G3 | EG |
| L4 | low | A second attached cognition entry (`cognition.seed.solve`) has no disposition; 22 capabilities are attached, not 8 | `greg/cognition/catalog.py:52-54` | G5, G3 | AR |
| L5 | low | Confinement leaks: signals to any process, repo listing and stat, regenerable truth | `greg/isolation.py:62,120` | G7 | AE |
| L6 | low | Target.validate accepts bool and float for int choices; a TypeError aborts a cycle | `greg/cognition/evolution.py:86-91` | closed mutation spaces | AE |
| L7 | low | The single-controller AST test misses two importer forms | `tests/unit/test_greg_mind_convergence.py:54-61` | G6 | AE |
| L8 | low | Integrity overclaims in live records | `greg/path.json:1650,1661` | no fabricated progress | AE |
| L9 | low | The P8 adoption path relative to the Kernel evolution loop is not escalated | `greg/cognition/evolution.py:1-3` | G13 | AE |
| L10 | low | PMCF's audited F7 result is credited to flow_expansion_mcf, which was never run on F7 | record `:194-196`; `greg/cognition/genomes/flow.py:684-686` | G11 | F7 |
| L11 | low | The index recipe row records F7 as VPL_LIFT with no tie note, and the compiler ranks that status first | `docs/evidence/greg-mind-evidence-index.json:1467` | G9 | F7 |
| L12 | low | The F7 scorer accepts fractional plans; the audit coerces them with int() (latent) | `cortex/pr155_f7_audit/audit.py:197` (see section) | T7 | F7 |
| L13 | low | The latency range is stale; the audit freeze pins no solver versions | record `:182`; `cortex/evaluation/pr155_f7_audit/freeze.json` | DL | F7 |
| L14 | low | The map never classifies the three exact capacity-expansion implementations against each other | map `:839` | G3 | F7 |
| L15 | low | F3 is listed with no tie caveat; the exact single genome ties it | record `:170` | G10 | CO |
| L16 | low | P6 v1's freeze-before-run ordering cannot be verified from git | `docs/evidence/greg-composition-lift/2026-10-07/results.json` | G1, FZ | CO |
| L17 | low | No procedure is given for reproducing the frozen P6 runs | record `:86` | DL | CO |
| L18 | low | The rollback instructions do not work as written | record `:374-385` | DL | OS |
| L19 | low | The map reports 0 "unresolved" while the record calls the generators' merit unresolved; the alternative CLI is unlabelled | map `:706`; `greg/cli.py:109` | G3 | OS |
| L20 | low | Five review responsibilities and two passes are met in form, not substance | record `:223,275-330` | RV | OS |
| L21 | low | The "still unverified" account is incomplete; one escalation can be decided by engineering evidence | record `:386-404` | DL | OS |
| L22 | low | #155's developmental-sweep runner still runs and would overwrite a historical result unchecked | `cortex/evaluation/developmental_sweep/run.py:114-133` | G2 | OS |

**Ranking rule:** each finding is ranked at the highest severity any lens gave it. Where lenses differ, the section shows each lens's rating.

**Lens key:**
- EG: Evidence/Welfare Guardian
- AR: Adversary (routing)
- AE: Adversary (evolution)
- F7: F7 cross-check
- CO: Composition
- OS: Operator/Founder-Intent Steward

**Gate key.** The founder's acceptance gates, in the founder's order:
- G1: lineages recoverable and inspectable
- G2: frozen results unaltered
- G3: every conflict has a disposition
- G4: the branch passes its own CI, contract, integration, security and regression tests
- G5: one canonical cognition entry point
- G6: alternative engines cannot silently assume live authority
- G7: the protected evaluator cannot be modified by its candidates
- G8: no rejected P8 configuration promoted
- G9: no NO_GAIN result presented as lift
- G10: strong standalone and practitioner baselines
- G11: genome admission bound to the exact tested version
- G12: restart does not duplicate consequential actions
- G13: Kernel, event spine, authority, shutdown and founder boundaries preserved
- G14: no live deployment

Further requirements from the founder's directive:
- D: third-party data rights flagged and kept out of a release
- T5: Track B item 5, mechanisms selected by evidence
- T7: Track B item 7, every retained intelligence runs through the single interface and independent verification
- R: distinguish inventoried, implemented, independently verified, admitted, attached and exercised
- C: no composition-superiority claim over deliberately incomplete constituents
- FZ: a fresh freeze before every held-out execution
- RV: five review responsibilities and exactly two strengthening passes
- DL: deliverables (reproducible commands, rollback, unverified account)

---

## High

### H1. The cross-lineage "replications" of P4 and F2 re-measure the same instances, and the smaller run now decides each row

- **Severity:** high (EG high, CO high).
- **Gates:** T5 (selection by evidence, not recency); G2 (the meaning of frozen results); the directive's "without fabricating progress".
- **Location:**
  - `docs/collaboration/MIND-LINEAGE-RECONCILIATION-2026-10-14.md:124,150,154,169,287` (Pass 1)
  - `docs/FOUNDER_INTENT_LEDGER.md:24`
  - `greg/cognition/worlds.py:88`
  - `greg/path.json:1271`
  - `scripts/build_mind_evidence_index.py:37-43`
  - `docs/evidence/greg-mind-evidence-index.json`: rows `recipes.identify_then_optimize` and `routing.conditional_competence`

**Evidence.**
- **F2.** Both runners call `cortex/evaluation/composition_lift/run.py:f2(seed)`. That file is byte-identical at `07350d4` and `6e3f35d` (sha256 `e64f2d1c...`) and seeds `random.Random(2000+seed)`. #155's F2b seeds 25-72 are a subset of #158's F2R held-out seeds 25-88.
  - Per-item outcomes match on 48 of 48 shared items: routed 43 correct, 3 wrong, 2 no decision; association 35/13; identical plans.
  - The failures repeat too: F2b-27, -37 and -41 fail exactly as F2R-27, -37 and -41 do.
- **P4 v3.** All 130 of #155's held-out payloads are byte-identical to items among #158's 191, and both runs trained on the same `suite-v2.json` development partition.
- **How the records describe this:**
  - The record calls F2, F2R and F2b "an independent replication" and the two P4 runs "retests on different suites".
  - The ledger says "P4 no gain twice; F2 lift twice".
  - `worlds.py` and `path.json` call F2b "fresh seeds".
  - Pass 1 cites the cross-lineage replication as a reason to keep #155.
- **What now decides each row.** Under the finish-time ("latest run decides") rule, the deciding rows cite strict subsets of the earlier runs:
  - F2b (11-3, n = 48) replaced F2R (13-4, n = 64) for `identify_then_optimize`;
  - #155's 130-item P4 run replaced #158's 191-item run;
  - the P4 deciding row has also lost its predeclared consequence (`consequence: null`).
- The lift/no-lift signs are unchanged. The damage is to the evidence base and to the stated independence.
- Probe: `/tmp/claude-0/conv/review/evidence_guardian/probes/replication_overlap.py`.

**Minimal fix.**
1. Keep the superset runs (F2R, and #158's P4 v3) as the deciding rows, or record an `overlap_with` field in history.
2. Relabel F2b and #155's P4 v3 as same-instance re-runs. They are evidence of reproducibility and of timing noise, not replications.
3. Correct the cited record lines, ledger line 24, `worlds.py:88` and `path.json:1271`.
4. Make the index builder compare instance identity (generator digest plus seed set, or payload digests, as #158's `instance_key` does). It should refuse to let a contained run replace its superset or count as a replication.

**Lens notes.** Both lenses support the builder's own dissent that the finish-time rule should go to the founder. CO adds that the Founder-Intent Steward's claim that "no current verdict depends on" the rule is wrong: the `identify_then_optimize` deciding row is exactly that failure mode.

### H2. Capability Genesis offers REJECTED and SUPERSEDED operation families to the founder as UNEVALUATED attach candidates

- **Severity:** high (AR).
- **Gates:** G6 (the founder decision surface); G3 (one admission truth).
- **Location:** `greg/genesis.py:754` (`_genome_library`); it interacts with `greg/cognition/compiler.py:55-59,391`.

**Evidence.**
- For every non-genome family, `_genome_library` hard-codes status `UNEVALUATED` and never reads the index's new `operations` section. The `status in compiler.EXCLUDED` check therefore cannot trigger, although its docstring says the compiler's frozen negative evidence applies.
- Reproduction on a scratch #179 body (`/tmp/claude-0/conv/review/adversary_routing/probe_genesis.py`):
  - A signed mission compiles an observations-only request. It ends in the deficit #179 intends, but Genesis then journals `deficit.awaiting_attach` for `cognition.collective` and `cognition.pattern`, both REJECTED in the index, each labelled UNEVALUATED.
  - A blackbox-shaped request makes Genesis offer `cognition.blackbox` (SUPERSEDED) as UNEVALUATED.
- #179 introduced the inconsistency. It taught only the compiler the operation verdicts, and it added the blackbox, swarm and crowd input signatures to `NATIVE_INPUTS`. On #158 `047549f` the same offers were consistent with #158's index.
- The PR's headline routing change is undone one step downstream, and the body's durable journal mislabels frozen negative evidence.

**Minimal fix.**
1. In `_genome_library`, read the same index row the compiler uses: `evidence.get('operations', {}).get(family, {}).get('status', 'UNEVALUATED')`. Better, give the compiler, Genesis, inventory and `mind_status` one shared status function (see M16).
2. Add integration tests: an observations-only deficit offers no REJECTED family, and a blackbox-shaped deficit does not offer `cognition.blackbox`.

### H3. The crowd (Dawid-Skene) verifier accepts a total forgery

- **Severity:** high (AR).
- **Gates:** T7 (every retained intelligence operates through independent verification); G4 (security tests).
- **Location:** `greg/cognition/verification.py:171-188`.

**Evidence.**
- The check is internal consistency only:
  - posteriors are normalised;
  - labels are the argmax of the posteriors;
  - every decidable item is answered;
  - the EM objective trace it checks is supplied by the answer itself.

  Nothing ties a label or posterior to the observers' votes.
- Reproduction on #179 (`/tmp/claude-0/conv/review/adversary_routing/probe_verify2.py`, generator seeds 0-9):
  - Flipping every label, with one-hot posteriors, gives STRUCTURALLY_VERIFIED on 10 of 10 seeds.
  - The forged answers are wrong on 24-30 of 30 items; the honest ones are wrong on 0-6.
  - A single-item flip, found in this session's earlier inventory, also still verifies (10/10).
- #179 makes `crowd_label` routable. The compiler picks it as the withheld best method and prepares an attach ask, and the mission hook recommends attaching it.
- The record does not mention the gap. Its Adversarial Reviewer role lists two defects and omits this one and the two in M4 and M5.

**Minimal fix.**
1. Make the verifier recompute from the data:
   - the artifact carries the final confusion matrices and class priors;
   - the verifier runs one independent E-step from them and the raw labels;
   - it checks that the posteriors match within tolerance;
   - it checks that the parameters are a fixed point of one M-step.
2. At minimum, refute any label that contradicts a unanimous or strict-majority vote among independent groups unless the artifact's confusion matrices justify it.
3. Add the total-flip forgery as a regression test.

### H4. "36 admitted" mixes rule-admitted genomes with weaker labels; #155's DEFAULT verdicts route at rank 0 without competitors or git pre-registration

- **Severity:** high (EG).
- **Gates:** G10; R (distinguish inventoried, implemented, independently verified, admitted, attached and exercised).
- **Location:** record `:73,122`; `greg/cognition/genome_library.py:84-93,206-210`; `greg/cognition/compiler.py:36,391`.

**Evidence.** The 36 break down as follows (computed from `genome_library.inventory()`).
- **19 genomes** from #158, admitted under the pre-registered rule.
- **9 #155 operation families:** micro, exact, graph, probabilistic, control, information, game, sequential and swarm.
  - Admission v1 was not pre-registered in git. `freeze-v1.json`, `run.py` and `results.json` were all added in `5063599`, frozen at 11:12:59 and finished at 11:13:08. The results' `source_commit` `6e3f35d` does not contain `run.py`.
  - micro, sequential, graph and exact are DEFAULT with competitor `None`, against strawman baselines: fewest-hops BFS, binary floating point, a greedy one-step policy and a single-threshold reflex.
  - swarm is DEFAULT although L-BFGS-B beats it 32/7 post hoc.
- **2 hand-coded cortex-organ labels:** z3 is DEFAULT "from P4 v2", which was INCONCLUSIVE; cpsat is NICHE.
- **6 recipes** labelled DEFAULT or NICHE on lift over their own constituents only:
  - `graph_then_allocate` is DEFAULT although parametric min-cost flow ties it on 200/200 items (for the latency comparison, see M12);
  - `forecast_then_staff` is DEFAULT although it loses 40-50 on day count to the weekly-mean practitioner.

Record line 122 calls the operation verdicts "held-out runs against stated competitors", which is false for 4 of the 9 DEFAULT families. These DEFAULTs route at rank 0: `/tmp/claude-0/conv/review/evidence_guardian/probes/rank_ops.py` shows `cognition.micro` and `cognition.graph` as DEFAULT_FOR_GEOMETRY.

**Minimal fix.**
1. Report admitted counts by provenance:
   - 19 rule-admitted at the current version;
   - lineage operation verdicts, which are not version-bound, flagged where they have no competitor or no git pre-registration;
   - recipe lifts, which are not admissions;
   - hand-coded organ labels, which are not admissions.
2. Route #155 operation DEFAULTs that have no competitor as UNEVALUATED until they are re-admitted under #158's rule.
3. Correct line 122.
4. Label `graph_then_allocate` and `forecast_then_staff` with their practitioner ties and losses in `greg genomes`.

**Related findings:**
- M3: collective's privileged baseline.
- M17: no harness can re-admit the operation families.
- L16: the same freeze-ordering pattern in P6 v1.

### H5. Operation-family and recipe verdicts route with no binding to the code they measured; the record marks the gate met

- **Severity:** high (EG); medium (AR, OS); low (CO, recipe part).
- **Gate:** G11.
- **Location:**
  - `greg/cognition/compiler.py:387-392` (operation branch of `candidates()`) and `:426-438` (recipe status)
  - `scripts/build_mind_evidence_index.py:49,136-151`
  - the `operations` and `recipes` rows of `docs/evidence/greg-mind-evidence-index.json`
  - `greg/cognition/composition.py:57` (`SCHEMA`)
  - record `:369`: the gate row says "met", against `:311` (Pass 2 "(b) resolved") and section 15, which lists "version binding for operation families" as not done

**Evidence.**
- **The rows carry nothing to bind to.** Operation rows hold only `{evidence, history, measured, raw_status, status}`, with no version or code digest. Nine positive operation verdicts route on them: control, exact, game, graph, information, micro, probabilistic, sequential and swarm.
- **#155's own freezes report the code has changed.** Admission v1, v2 and crowd-sparse each report changed pinned inputs at this head: `solvers.py` moved from `c670271c` (v1) and `11447b68` (v2 and crowd-sparse) to `b7f610eb`.
  - The v1 runner refuses with FROZEN_INPUT_CHANGED, yet its 8 DEFAULT and 4 REJECTED verdicts route with no stale marker.
  - Those freezes also pinned only 2-4 files, not the import closure (EG, `/tmp/claude-0/conv/review/evidence_guardian/probes/operation_binding.py`).
- **There is no identity to bind to.** Every builtin cognition manifest carries the constant version `0.2.0` (AR).
- **A broken solver keeps its verdict (OS reproduction).** In an archive of `ccd38a2`, `repertoire.swarm_minimize` was replaced with a stub that raises. `candidates()` for a sphere request still returns `{'status': 'DEFAULT_FOR_GEOMETRY', 'rejected': None, 'stale_evidence': None}` (`/tmp/claude-0/conv/review/operator_steward/probe_opbind.py`).
- **Recipes have the same gap (CO).** Recipe `VPL_LIFT` rows rank 0, like DEFAULT, and carry no version or digest. `composition.py` changed after every recipe measurement: derive() was added in #179, and #158's schema 0.4 (`6576b12`) changed `staffing_quantile` for `forecast_then_staff`. `SCHEMA` is still `greg-composition/0.3` although routing behaviour differs.
- **No live mis-route today.** The measured functions in `solvers.py` and `repertoire.py` are textually unchanged (`repertoire.py` equals `b99daba`'s digest). The gap is structural.
- **The live head is not verified.** The builder's later commit `c7a7ad5` digests solver entry functions only and records helpers as uncovered. No lens verified it.

**Minimal fix.**
1. Carry each run's pinned code digests, ideally the import closure, into its index row.
2. In the compiler and inventory, treat a positive operation or recipe status as UNEVALUATED, flagged `stale_evidence`, when the current digest differs, mirroring the genome rule.
3. Store per-recipe digests covering the recipe function, its `RECIPES` entry and shared helpers, and bump `SCHEMA`.
4. Add a regression test that edits a helper, not only the entry function.
5. Change the gate row to "met for #158 genomes only" until a version-bound re-admission has been run.

**Lens disagreement.** All four lenses agree the gate is not met as claimed. They differ on severity:
- EG rates it high: verdicts route at rank 0, nothing would detect drift, and #155's own harness refuses to report at this head.
- AR and OS rate it medium, because no live mis-route exists today.
- CO rates the recipe part low.

AE (M15) adds that even genome binding is to a version string, not to code.

---

## Medium

### M1. Attach asks for operation families state a status but cite no evidence; SUPERSEDED operation verdicts name no acquisition candidate

- **Severity:** medium (EG, AR).
- **Gates:** G6 (an informed founder attach decision); the section 60 ask contract (every ask carries its evidence).
- **Location:** `greg/cognition/compiler.py:670-674` (`attach_ask` reads only `evidence['genomes']`) and `:412-421` (`superseded_by` is genome-only); record `:413` (section 16).

**Evidence.**
- In `/tmp/claude-0/conv/review/adversary_routing/route179.json`, every operation-family withheld-best ask has only the evidence keys `admission_status`, `current_state` and `registered`: no admission evidence, raw status or version.
  - Affected: `cognition.swarm`, `crowd`, `control`, `game`, `graph`, `information`, `probabilistic` and `sequential`.
  - Genome asks such as `basal_kalman` do carry `admission_evidence` and `measured_version`.
- What the founder would not see (`/tmp/claude-0/conv/review/evidence_guardian/probes/attach_ask_ops.py`):
  - The crowd ask carries only `{admission_status: EXPERIMENTAL}`. It omits the crowd-sparse finding that the one-step weighted vote wins 32/8 (p = 9e-5) and that crowd should not be attached as default.
  - The swarm ask carries only DEFAULT_FOR_GEOMETRY. It omits that this DEFAULT means only "beats random search", and that L-BFGS-B beats PSO 32/7.
- blackbox is SUPERSEDED by multistart L-BFGS-B (26-8), but no acquisition candidate is named, so blackbox-shaped requests go to PSO. On admission v2, PSO's mean error was 14.97 against DE's 2.72 (sign test 18-21, not significant).
- Before #179 these families were UNEVALUATED, so there was nothing to cite. Section 16 now claims GREG reports every family's true measured admission in its attach asks.

**Minimal fix.**
1. In `attach_ask`, fall back to `evidence['operations'][family]` for evidence, raw status and history, and include the `genome_library.NOTES` caveats.
2. For SUPERSEDED operation rows, populate `superseded_by` from the frozen result's competitor field, so the compiler lists it under acquisition candidates.
3. Add a test that an operation-family ask cites its frozen evidence file.

### M2. The #155 mission ask hook recommends attaching COMPOSITION_ONLY genomes, which the direct path would then run standalone

- **Severity:** medium (AR).
- **Gates:** G6 (the founder decision surface); G5 (one routing rule).
- **Location:** `greg/missions.py:992` (`order` includes COMPOSITION_ONLY); the standalone check exists only at `greg/cognition/compiler.py:380`.

**Evidence.**
- `/tmp/claude-0/conv/review/adversary_routing/probe_ask.py` runs `MissionEngine._cognition_ask` on #179 with a stub `_request`. Plain receipts for `compile_newsvendor`, `preposterior_scenarios` and `compile_capacity_expansion` each yield "attach cognition.<family> (native-benchmark admission: COMPOSITION_ONLY) with: greg attach ...".
- The compiler rejects the same families as "composition stage only (no standalone decision)".
- `cortex.reason`'s candidate selection has no standalone check, so after such an attach a plain request gets an intermediate representation as its answer.
- #179 caused this: `inventory()` now feeds #158's genome statuses into #155's hook. The builder's "two hooks with disjoint outputs on one asks contract" is true of their outputs, but the two hooks apply different recommendation rules.

**Minimal fix.**
1. Build the hook's admissible set from `compiler.EXCLUDED`, dropping COMPOSITION_ONLY.
2. Make cortex candidate selection treat a non-standalone genome as ineligible outside a composition stage.
3. Add the `compile_newsvendor` case to `test_greg_cognition_mission`.

### M3. cognition.collective's REJECTED verdict comes from a loss to an oracle baseline and is misdescribed

- **Severity:** medium (AR).
- **Gates:** G10 (baselines must be deployable); evidence accuracy.
- **Location:** `cortex/evaluation/genome_admission/run.py:155-171` (line 168); record section 5, "Routing deltas"; commit message of `49b2d58`.

**Evidence.**
- The `results.json` collective row:
  - against the baseline it scores 5-16 (p = 0.013), and this is what makes it REJECTED;
  - against the competitor, simple majority, it scores 7-11 (p = 0.24), which is not significant.
- The baseline is `votes[argmax acc]`: the observer with the highest true accuracy. The generator knows that accuracy; the quorum (all weights 1) does not.
- The record and the commit say "REJECTED 7-11 against simple majority".
- Because of this verdict, real quorum requests (dict observations with choices) now end in a deficit even with every family attached. Yet the only deployable comparison is a tie.
- #158's ledger already flagged the same oracle-competitor class for `collective_market`.

**Minimal fix.**
1. Correct the record and commit-derived text to: "REJECTED 5-16 against the most-accurate-observer baseline, which uses hidden true accuracies; tied 7-11 with simple majority".
2. Add an erratum that flags the privileged baseline, as #158 did for `collective_market`.
3. Until a pre-registered comparison against deployable baselines exists, either route collective as EXPERIMENTAL or escalate the decision.

**Note.** AR checked the other REJECTED verdicts and found them defensible (see "Checked and sound").

### M4. The robust_pattern verifier skips the flag check when MAD == 0, so forged anomaly lists verify

- **Severity:** medium (AR).
- **Gate:** T7 (independent verification).
- **Location:** `greg/cognition/verification.py:159-170` (line 167, `if mad > 0:`).

**Evidence.**
- When MAD == 0 the solver falls back to a mean-absolute-deviation scale (proof scale "median/mean-absolute-deviation"). For the observations `[0]*9 + [50, -40, 0.1]` it flags `[9, 10]`.
- The forged lists `[]` and `[0]` (an inlier) both return STRUCTURALLY_VERIFIED on #179.
- Control: with MAD > 0, the same forged `[]` is REFUTED (`/tmp/claude-0/conv/review/adversary_routing/probe_verify2.py`).

**Minimal fix.**
1. When MAD == 0, re-derive the flags with the solver's documented fallback scale, implemented independently in `verification.py`.
2. If no fallback scale can be recomputed, refute the answer or require ABSTAIN.
3. Add the MAD == 0 forgery as a regression test.

### M5. swarm/blackbox verification is common-mode with the solver, and an under-reported evaluation count verifies

- **Severity:** medium (AR).
- **Gate:** T7.
- **Location:** `greg/cognition/verification.py:189-196`.

**Evidence.**
- The verifier recomputes fitness with the same `greg.cognition.repertoire.objective` code the solver uses.
- With `OBJECTIVES['sphere']` patched to return 0, the swarm returns claimed fitness 0.0 and the verifier says STRUCTURALLY_VERIFIED. The returned point's true sphere fitness is 16.28; the honest run reaches 0.031.
- An answer claiming `evaluations=1` also verifies, because the check only tests count <= budget (`/tmp/claude-0/conv/review/adversary_routing/probe_verify2.py`).

**Minimal fix.**
1. Write the five closed-form test functions independently in `verification.py` (a few lines each, with shift handling) and compare against them.
2. Check the evaluation count against the artifact's trace length, not only against the budget.

### M6. The composition's optimality is unverified: the optimize verifier checks feasibility only, and the chain drops the solver status

- **Severity:** medium (F7).
- **Gates:** T7 (formal and independent verification); certificate strength as a basis for canonical selection.
- **Location:**
  - `greg/cognition/verification.py:83-97`: objective is never compared with bound.
  - `greg/cognition/composition.py:209`: accepts FEASIBLE.
  - `composition.py:222`: the final answer omits solver status and gap.
  - `composition.py:187-191`: `_op_summary` keeps no status.

**Evidence.**
- `/tmp/claude-0/conv/review/f7_crosscheck/cert_probe.out`, development item F7-abilene-2 (optimum 58):
  - The greedy plan (throughput 55) was written as a solution of the compiled model and labelled `solver_status OPTIMAL`. Its proof still carried bound 58.0 against objective 55.0.
  - `verify('optimization', ...)` returned STRUCTURALLY_VERIFIED with every check passing.
  - The max-flow cross-check would also pass, since it confirms only that the plan carries the flow it claims.
- A CP-SAT FEASIBLE (time-limited) result likewise comes back ANSWERED, indistinguishable from OPTIMAL.
- On the same suboptimal plan, `flow_expansion_mcf`'s verifier returns `optimal_by_dual_bound False`.
- F7's 200/200 "optimal" was established by the external truth, not by the composition's own evidence.

**Minimal fix.**
1. For optimisation answers labelled OPTIMAL, have the verifier require bound == objective (gap 0).
2. Carry `solver_status` and `optimality_gap` into the composition's answer and receipt.
3. Label FEASIBLE as "feasible, optimality unproven", or abstain.
4. Record the difference in certificate strength in the mechanism-selection record.

### M7. The Layer-5 Competency Compiler cannot reach #155's derived chains

- **Severity:** medium (AR, CO).
- **Gates:** T7 (every retained intelligence runs through the single canonical interface); G5.
- **Location:** `greg/cognition/compiler.py:424-426`. Candidate selection uses `route()` only and never calls `derive()`, and the relaxation check runs before organ rows are added. Record `:71` says "Both lineages' families run through it".

**Evidence.** The two lenses observed two modes of the same defect.
- **Planning mode (AR).** Take a payload with `estimation_model`, `causal_studies` and `formal_template`.
  - `composition.route()` returns None, and `derive()` returns `('estimate', 'identify', 'optimize')`.
  - `compiler.run` returns PLANNED with `cognition.cortex.estimation.fermi`, no rejections, and `"agrees": True`: it would answer only the estimate.
  - #158 `047549f` behaves the same, so the defect predates #179. But #179 claims both composition mechanisms are integrated on the one entry, and this is the same wrong-question class #179 fixed for observations-only quorum requests.
- **Execution mode (CO).** `compile({data: <#155 run_v3.f3 seed-0 payload>, execute: True})`:
  - the only candidate is Fermi, in state ABSTAIN ("unknown payload keys: [causal_studies, formal_template]");
  - `capability_deficit` is null.
- **Scale (CO).** Over 40 development and review items, compile abstains on 40/40, while `reason({chain})` answers through `derived:estimate+identify+optimize` with 39 correct and 1 suboptimal.
- `composition.derived` is counted as admitted NICHE_CAPABILITY (`genome_library.py:230`), but geometry routing can never select it.
- The two observations are consistent: in planning mode the compiler picks a relaxation, and when executed that relaxation abstains without raising a deficit.

**Minimal fix.**
1. In `compiler.candidates`, when `route(data)` is None and `derive(data)` is not, add a `composition:derived:<stages>` row whose status comes from the `composition.derived` inventory entry (NICHE, from P6 v3).
2. Run that row through `reason({'chain': ...})` without a recipe, and adapt `_usable` and the high-consequence formalisation check to derived stages.
3. Give organ rows their payload part as inputs, and run `_reject_relaxations` after the organ rows are added.
4. Add a regression test: compiling a `run_v3.f3` development payload answers with `routed_by 'dataflow'`.

### M8. derive() overrides the ambiguity refusal and silently drops an operation recipe's geometry

- **Severity:** medium (CO).
- **Gates:** G3; G4.
- **Location:** `greg/cognition/composition.py:372-374`; `tests/integration/test_greg_cognitive_composition.py:28`; record `:91` and the map entry for `greg/cognition/composition.py`.

**Evidence** (`/tmp/claude-0/conv/review/composition/scripts3/precedence_probe.py`, development payloads):
- **Mixed payload** (v1 `f1(1)` plus #158's F3-1 `capacity_network`):
  - on #158 it gives NO_RECIPE ("no single composition recipe matches");
  - on #179, `route()` is None and `derive()` gives (estimate, optimize), so the answer is ANSWERED `derived:estimate+optimize`;
  - `capacity_network` is never read, and the receipt records no unused input.
- **f1 + f2 merged.** The test asserts that `route()` is None, with the comment "ambiguous: no composition". Yet on #179, `run()` answers `derived:identify+optimize` and ignores `estimation_model`. The test passes only because it checks `route()`, not `run()`.
- The record's "operation recipes dispatch before dataflow derivation" is false for ambiguous geometries.

**Minimal fix.**
1. In `run()`, derive only when no recipe's requires-set matched. With two or more matches, return NO_RECIPE naming them.
2. Record payload keys the chain never read, for example `receipt['unconsumed_inputs']`.
3. Add a `run()`-level test for the mixed payload, and make the line-28 test assert the intended `run()` behaviour.

### M9. Dataflow derivation has no executable test coverage

- **Severity:** medium (CO).
- **Gate:** G4.
- **Location:** `greg/cognition/composition.py:113-123`. No test references `composition.derive`, `dataflow` or `derived:`.

**Evidence.**
- In a mutant tree where `derive()` returns None unconditionally, these all pass (133 passed, 3 skipped):
  - all 10 test files that exercise chains;
  - `test_greg_mind_convergence`, `test_greg_cognition_process`, `test_greg_cognition_mission` and `test_greg_genome_library`.
- #155 never had a derive unit test. Its only exercise was the frozen `run_v3`, which refuses at HEAD (FROZEN_INPUT_CHANGED).

**Minimal fix.**
1. Add unit tests for `derive()`: an estimate+identify template gives a three-stage chain; a root with no producer gives None; no template gives None.
2. Add one integration test that runs a #155 `run_v3.f3` development seed (0-9) through `reason({'chain'})` and asserts `routed_by 'dataflow'` and a correct score. The derive() mutant must then fail.

### M10. Admitting flow_expansion_mcf cannot make it canonical for F7-shaped requests, because the compiler selects by payload shape

- **Severity:** medium (F7).
- **Gates:** T7; G5; T5 (mechanisms chosen by evidence, not by payload shape).
- **Location:** `greg/cognition/compiler.py:393` (genome rows require `set(required_inputs) <= top-level payload keys`) and `:426` (recipe rows via `composition.route`); record `:194-210`.

**Evidence** (`/tmp/claude-0/conv/review/f7_crosscheck/route_probe.out`, development item F7-abilene-0, `flow_expansion_mcf` attached):
- **Recipe-shaped payload** `{capacity_network: ...}`: `methods_considered` is `['composition:graph_then_allocate']` only. This holds under the current index and also under a hypothetical index that gives `flow_expansion_mcf` 1.0.0 DEFAULT_FOR_GEOMETRY.
- **Flat payload:** selects `flow_expansion_mcf`.
- **Payload carrying both shapes:** the composition wins under the current index (VPL_LIFT rank 0 beats UNEVALUATED rank 2). `flow_expansion_mcf` wins only under the hypothetical admission.
- So the F7 compiled arm, and any `capacity_network` request, would still run the three-stage composition after admission. The record's sole condition, "a pre-registered admission", is not sufficient.

**Minimal fix.**
1. Before the admission v3 freeze, let genome candidates match the inner `capacity_network` payload: either unwrap the recipe's single required key in `candidates()`, or let `flow_expansion_mcf` declare `composition_inputs ('network',)` and match on it.
2. Add a regression test: with the genome DEFAULT, a `capacity_network` payload selects `cognition.flow_expansion_mcf`.
3. State this compiler dependency in record section 8.

### M11. The F7 "tie" with parametric MCF is on throughput only; the composition's plans spend budget on leases that carry no flow

- **Severity:** medium (F7).
- **Gates:** G10; T5 (selection by measured performance).
- **Location:** `cortex/evaluation/composition_lift/run_v4.py:224-238` (the scorer measures throughput only); record `:174` and section 8; `docs/evidence/pr155-f7-audit/2026-10-14/README.md`.

**Evidence** (`/tmp/claude-0/conv/review/f7_crosscheck/spend_probe.out`). "Idle" means spend above the cheapest plan that reaches the same throughput within the plan's own leases.
- **Development items (n = 50):**
  - composition plans carry idle spend on 17/50 items (mean 2.8% of budget, max 23.9%);
  - PMCF and `flow_expansion_mcf` have none on 50/50;
  - greedy idles on 32/50 and SP-upgrade on 28/50;
  - the composition's plan is identical to PMCF's on only 21/50.
- **Held-out recorded rows (no instance data used):**
  - the composition's plan equals PMCF's on 103/200;
  - it leases more units than PMCF on 59/200 items (up to +50 units) and fewer on 5.
- CP-SAT maximises flow with no secondary cost objective.
- Neither #158's README nor the builder's audit reports this.

**Minimal fix.**
1. Record this as negative evidence: throughput is equal, but the composition can waste budget, so the single exact method weakly dominates it.
2. Pre-register spend at equal throughput (or idle lease units) as a declared secondary measure in admission v3 and in the F7 re-measurement.
3. Optionally, add a lexicographic min-spend stage to `graph_then_allocate` if it is kept as an alternative.

### M12. The "about 300x faster" claim compares figures the frozen evidence declares not comparable, and credits them to the wrong mechanism

- **Severity:** medium (F7); low (CO).
- **Gates:** G9 (honest lift accounting); evidence accuracy.
- **Location:** `docs/evidence/pr155-f7-audit/2026-10-14/README.md:66`; record `:173-174,195-196`; `docs/intent/INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION.json:92` ("at a fraction of its latency").

**Evidence.**
- **Where 300x comes from.** 1.2842 s / 0.0043 s = 298.7. The first figure is the composition through three isolated-worker stages; the second is PMCF run in process. The frozen v4 README and the `results-v4.json` limits both say these latencies are not comparable.
- **Like-for-like, F7 lens** (`/tmp/claude-0/conv/review/f7_crosscheck/dev_probe.json`, 50 development items, core 0):
  - in process: the composition twin (compile + CP-SAT) takes 3.46 ms and PMCF 3.59 ms, a per-item median ratio of 0.96x; `flow_expansion_mcf` takes 0.27 ms;
  - on GREG's path, both through isolated workers and interleaved: chain 2.85 s against the `flow_expansion_mcf` op at 0.76 s, a per-item median of 3.7x;
  - the cores were under contention, and the recorded development medians suggest about 4-5x unloaded.
- **Like-for-like, CO lens** (`/tmp/claude-0/conv/review/composition/scripts3/f7_latency.py`, 20 sequential development runs): composition 1.43 s; `flow_expansion_mcf` through `cognition.reason` 0.27 s (5.4x faster); PMCF in process 0.0044 s (328x).
- **Misattribution.** Record section 8 credits the 300x to `flow_expansion_mcf` ("That intelligence is #158's flow_expansion_mcf"). The audit README correctly attributes it to the in-process algorithm.

**Minimal fix.**
1. Replace the 300x statements with like-for-like figures, or with "not comparable (in-process vs isolated workers)". For example: "on GREG's path, a one-stage exact genome is about 4-5x faster than the three-stage chain; in process, the composition and PMCF are equally fast".
2. Correct the record and the next intent update, and add an erratum beside the frozen audit. Leave the frozen v4 README unchanged.

**Lens disagreement.** On the magnitude on GREG's path, F7 measured 3.7x per item under contention and CO measured 5.4x on sequential medians. Both reject the 300x figure and its attribution.

### M13. The F4 lift is listed without its caveats; the ledger misstates its truth basis

- **Severity:** medium (CO).
- **Gates:** C (no superiority claim over deliberately incomplete constituents); G10.
- **Location:** `greg/cognition/worlds.py:91` ("truth is the generator's hidden parameter"), which `scripts/mind_status.py` surfaces; record `:171` (F4 "yes", no caveat).

**Evidence.**
- `run_v2.f4` (`07350d4:170-195`) sets `truth.optimal_actions` to the Bayes-optimal action under the declared Beta(1,1) posterior, not the hidden theta. The composition therefore computes the truth function itself.
- Under theta, `results-v2` reports `summary.F4.mean_realised_value` of -55.4 for the routed composition against -20.3 for `voi_uninformed`: the composition is worse in the world. #158's own README says so.
- The best constituent was the same two genomes run on an uninformed prior. Given the conjugate-updated prior inline (no `beta_update` stage), they tie the composition on development items: 8/8 correct, same mean value 171.58.

**Minimal fix.**
1. Correct `worlds.P6_FAMILIES['F4']` to say the truth is the declared-model Bayes action, and that realised value is -55.4 for the composition against -20.3 for the constituent.
2. Add the caveats to record section 7 and to `mind_status`'s basis: the lift is over a constituent that was denied the observed evidence, and the composition is worse on realised value.

### M14. The canonical P8 controller kept #158's integrity gaps and did not take over #155's freeze mechanism

- **Severity:** medium (AE).
- **Gates:** G7; FZ.
- **Location:**
  - `greg/cognition/evolution.py:289-301` (`_compute_seal`/`check`)
  - `greg/cognition/evolution.py:397-400` (record `source_commit` and `evaluator_seals`)
  - `greg/cognition/evolution_sandbox.py:39-51`

**Evidence.** `evolution.py` is byte-identical to #158's file (`ac4657ed`). Probe outputs are in `/tmp/claude-0/conv/review/adversary_evolution/out/probe179_canonical.json`.
- **Probe 2d: a pre-run evaluator edit is accepted.** An edit of `SealedEvaluator.losses` that returns 0.0 for every output goes through. The seal changes from `sha256:08649ce6...` to `sha256:cab15ef7...`, but no code compares it with a pre-registered value: `evaluator_seals` is only written (line 400).
- **Probe 2c: an edited candidate method runs.** An on-disk edit of `developmental.constraint_release_solve_with` leaves `seal.check()` passing, and the next sandbox ran the edited method ("ValueError: EDITED METHOD"). The seal covers only the `SealedEvaluator` class and the score function (line 290).
- **The recorded commit can be wrong.** The record stores `git rev-parse HEAD` (line 399) with no dirty-tree check, so a run from an edited tree records a clean SHA.
- **#155's stronger pieces were not ported.** #155's engine had a freeze manifest that refuses changed inputs before the run and before reporting, an output-contract check, and bool-excluding typing.
  - The founder asked to "compare and combine the strongest mechanisms ... evaluator integrity".
  - `path.json` names a further P8 cycle as the smallest next experiment, so that cycle would run without a machine-checked freeze.

**Minimal fix.** Port #155's freeze into `cycle()`:
1. Require a pre-registration manifest: the sha256 of the trusted closure (`evolution.py`, `evolution_sandbox.py`, `isolation.py`, `capabilities.py`, `tools/offline_test.py`, the target's genome module, `genomes/contract.py`, `cognition/contracts.py`, `improvement.py`), plus `RULE`, settings and seed ranges.
2. Refuse to run if the manifest differs. Re-check it before every `evaluate()` and before `_finish()`, and refuse a dirty tree for the closure.
3. Have the sandbox report the sha256 of the method module it imported (read before confinement); the parent compares it with the manifest.
4. Add regression tests that fail on the current code for probes 2c and 2d.

**Lens note.** AE agrees that #158's controller is the right canonical controller. The objection is that nothing was combined into it.

### M15. "No rejected P8 configuration is promoted" holds today, but nothing tests it, and a promotion keeps its admitted status

- **Severity:** medium (AE).
- **Gates:** G8; G11.
- **Location:** `tests/unit/test_greg_protected_evolution.py:39-40` (the incumbent test is tautological); `greg/cognition/genome_library.py:160-164` (admission bound to a version string only); record `:366` (gate marked met).

**Evidence.** Two promotions were tried in a scratch clone.
- **Cycle 1.** The REJECTED forecasting candidate (fit_window 156, origins 156, interval_scale 0.943) was shipped as `forecasting.DEFAULT_CONFIG`:
  - `genome_library.admission_of('forecast_quantile')` still returns DEFAULT_FOR_GEOMETRY at version 1.1.0;
  - the cited gate tests (`test_greg_protected_evolution`, `test_greg_mind_convergence`, `test_frontier_backcasts`) pass, 42 of them.
- **Cycle 3.** The rejected constraint-release candidate (p_recombine 0.13, p_extra_mutation 0.259) was shipped as `CR_DEFAULT_CONFIG`:
  - 67 tests pass, including `test_mind_status`;
  - `test_genomes_developmental` and `test_mind_evidence_index` pass, 70 tests.
- The builder cites "nothing attached; P8 exit_met false" as the evidence for this gate, but no test would detect a promotion.
- The proposed test `test_no_rejected_p8_candidate_is_shipped_and_the_incumbent_is_unchanged`, in `/tmp/claude-0/conv/review/adversary_evolution/proposed_tests/test_p8_review_regressions.py`, passes on HEAD and fails on the promoted tree.

**Minimal fix.**
1. Add that test. For every frozen cycle record with decision REJECT, the shipped constant must equal the record's incumbent and differ from every rejected candidate and lineage configuration.
2. Bind genome admission to a digest of the genome's default configuration or its source, not only its version string. A changed `DEFAULT_CONFIG` then reads EXPERIMENTAL until it is re-admitted.

### M16. Admission truth is still plural: mind_status, the hard-coded organ table and the label mapping disagree with the index the compiler routes on

- **Severity:** medium (EG); low (AR).
- **Gates:** G3; R.
- **Location:** `scripts/mind_status.py:262-266`; `greg/cognition/genome_library.py:51-52,81-91` (`ORGAN_ADMISSION`) and `:167-169`.

**Evidence.**
- **mind_status is wrong about every family.** It labels every catalog family BUILT with the basis "no family-level frozen held-out verdict in the evidence index". That is false: the index has 25 operation rows, including REJECTED for pattern, collective, evolutionary and simulation, and DEFAULT for micro, graph, exact and swarm.
  - So negative verdicts are invisible in the reality ledger, while the compiler routes the DEFAULT ones at rank 0 and `greg genomes` counts them as admitted.
  - Outputs: `/tmp/claude-0/conv/review/evidence_guardian/mind_status.json` and `/tmp/claude-0/conv/review/adversary_routing/mind_status.json`.
- **Structural labels become SUPERSEDED.** `genome_library` maps SUPERSEDED_BY_CANONICAL_ORGAN and ALIAS to SUPERSEDED for formal, optimization, estimation and search. Three of those are attached by default; the compiler routes them as UNEVALUATED and selects `cognition.formal` for a constraints request.
- **Organ labels come from a hard-coded table.** The inventory labels `cortex.estimation.fermi@0.1.0` COMPOSITION_ONLY and `cortex.formal.z3` DEFAULT_FOR_GEOMETRY. The index has no `organs` section, so the compiler routes every organ as UNEVALUATED and sends an `estimation_model`-only request standalone to Fermi.
- **The "one index" resolution is partial.** The builder's Pass 2 (a), "resolved: one index", covers only genomes and operation families in the inventory. Genesis is a fourth surface (H2).

**Minimal fix.**
1. Give the compiler, Genesis, inventory and `mind_status` one status function over one index.
2. Move `ORGAN_ADMISSION` into an index `organs` section.
3. Report structural labels as UNEVALUATED together with their raw label.
4. Add a test that all surfaces agree for every catalog family.

**Lens note.** AR's checks found that SUPERSEDED_BY_CANONICAL_ORGAN families never outrank their organs on the same payload, because they read different keys. The label mismatch is therefore a reporting defect, not a routing one; this is why AR rates it low.

### M17. Two executable-intelligence contracts are active, and no live harness can re-measure the operation families that now route

- **Severity:** medium (OS).
- **Gates:** G11; one canonical Mind (no duplicate active implementation without a disposition).
- **Location:**
  - `greg/cognition/repertoire.py:261` (`REPERTOIRE`, unversioned) against `greg/cognition/genomes/library.py` (versioned `Executable` contract)
  - `greg/cognition/genomes/admission.py:261` (admits only `library.executables()`)
  - `cortex/evaluation/genome_admission/run.py` and `run_v2.py` (#155's harnesses)

**Evidence.**
- #155's admission runners and the crowd-sparse runner refuse at HEAD with FROZEN_INPUT_CHANGED on `.code.greg/cognition/solvers.py` (`/tmp/claude-0/conv/review/operator_steward/freeze_refusal_probe.py`).
- #158's harness enumerates only `library.executables()`.
- So the 25 indexed operation verdicts (9 of them positive and routing), plus the 4 repertoire families, cannot be re-admitted anywhere in the converged tree.
- The record lists "version-bound re-admission of the operation families" as a remaining falsification test (section 11, item 4), but no harness exists to run it.
- The map marks `repertoire.py` and the genome library "complementary/kept", with no plan for one contract.

**Minimal fix.**
1. Wrap the repertoire families and the measured operation families as genome `Executable`s with a version and a certificate, carrying #155's competitors as admission competitors, so that `admission.py` is the only harness.
2. Until then, label operation routes as legacy in the inventory, and name the missing harness in the "not done" list.

### M18. The reconciliation is pinned to #158 `047549f` while #158 has moved 13 commits ahead, including verified defect fixes

- **Severity:** medium (OS); low (CO).
- **Gates:** G3; "shared live-code conflicts must be resolved through the dedicated convergence PR".
- **Location:** `docs/collaboration/MIND-LINEAGE-RECONCILIATION-MAP-2026-10-14.json:5` (`'pr158': 047549f`); `tests/unit/test_greg_mind_convergence.py:178` (the coverage test pins the SHAs written in the map).

**Evidence.**
- **The drift (OS).** #158's branch head is `41a8538`, and `git diff 047549f..41a8538` touches 29 files.
- **Trial merge (OS).** `git merge-tree --write-tree ccd38a2 41a8538` in a scratch clone gives 5 textual conflicts:
  - `docs/evidence/greg-mind-evidence-index.json`
  - `foundry/owned-source.json`
  - `greg/path.json`
  - `scripts/build_mind_evidence_index.py`
  - `tests/unit/test_mind_evidence_sources.py`

  It auto-merges `compiler.py`, `composition.py` and `worlds.py` (`/tmp/claude-0/conv/review/operator_steward/mergetree_41a8538.txt`).
- **Missing even from the live head (OS).** `c7a7ad5` merged #158 only up to `202b932`, so these are missing from it as well as from `ccd38a2`:
  - the promoted-competitor and `game_lp_dual` review fixes (`810881f`, `df122d0`, `d072e90`, `182fbb9`, via `6576b12`);
  - the F8 evidence (`2259c08`);
  - the path update (`41a8538`).
- **Shared code changes (CO).** The 12 commits after `047549f` add `track_then_staff`, staffing-plan checks and composition `SCHEMA` 0.4.
  - `git merge-file` of `composition.py`, `compiler.py` and `vpl_metrics.py` at `6576b12` is clean.
  - But derive()'s precedence is untested against the new recipe (M8).
  - Record section 7 omits F8, which lifts over its best single but loses 4.7% to the EWMA-quantile ablation and loses on item count to two practitioners.
- **No detection.** The coverage test diffs only the SHAs written in the map, so it cannot detect this drift.

**Minimal fix.**
1. Before #179 leaves draft, re-merge the current #158 head.
2. Extend the map with the new paths and dispositions, update the record's lineage table, and re-run the map test and the precedence tests.
3. Add F8 to section 7, with its ablation and practitioner results.
4. Add a checklist item, or a CI step given the #158 SHA as input, asserting that the latest #158 head is an ancestor of the PR head.

### M19. The release-blocker scope lists three extracts, but frozen suites, results and logs embed the same third-party data, and nothing executable keeps them out of a release

- **Severity:** medium (EG).
- **Gate:** D.
- **Location:** record `:337-356` (section 12).

**Evidence.**
- **M4 series** histories (W289 and others, with values) appear in `cortex/evaluation/composition_lift/suite-v2.json` and in `docs/evidence/greg-composition-lift/2026-10-08/results-v2.json` (the F5 "actual" arrays).
- **Raw half-hourly fpp3 `bank_calls` counts** appear in `suite-v3.json` and `docs/evidence/greg-composition-lift/2026-10-14-v3/results-v3.json`.
- **SNDlib** network, arc and demand data appear in:
  - `suite-v4.json`, `freeze-v4.json` and `prereg-v4.json`;
  - `results-v4.json`, `development-v4.json` and `run.log` under `2026-10-14-v4`;
  - the F7 audit's `results.json`.

  None of those 2026-10-14-v4 files, and not the F7 audit's `results.json`, is in the section 12 table.
- The proposed remedy, "move the extracts out of the tree and rebuild them on demand", would leave all these files in place, and frozen files cannot be rewritten.
- EG checked that `pyproject` packages only `adapters`, `contracts`, `events` and `provenance`, so no Python package release carries the data today. The only guard is prose.
- OS notes that the live head adds an Uber/TLC 2015 extract, which is also flagged.

**Minimal fix.**
1. List every file that carries third-party-derived values in the release-blocker record and in a machine-readable release-exclusion list.
2. Add a CI check that fails any release or tag artifact containing those paths until the founder or legal clears them.
3. Keep the files in git as frozen evidence; their identity is (commit, path, sha).
4. Keep the founder/legal escalation.

### M20. #155's frozen P8 runner was edited at its original path, and two "kept" dispositions are false

- **Severity:** medium (EG); low (AE, OS).
- **Gates:** G2; G3.
- **Location:** `cortex/evaluation/evolution/run.py:4,29-30`; `docs/collaboration/MIND-LINEAGE-RECONCILIATION-MAP-2026-10-14.json:195-199`; the source manifest's own entry.

**Evidence.**
- **The edit.** Commit `2d1ddd3` changed the import from `greg.cognition.evolution` to `greg.cognition.evolution_routing`. The blob changed from `7a2e50e` to `cffac2e`, and the file sha256 from `e8ce3540...` at `ef5f078` to `33becc5a...` at HEAD.
- **It is the only one.** Of the 73 "historical evidence" map entries, it is the only one that differs from its lineage head (AE).
- **Stale and misdirected.** The docstring at line 4 still names `greg.cognition.evolution.evolve`, which in #179 is #158's module. The edited runner still hashes `evolution.py` (now #158's controller) and `suite-v3.json` (now #158's suite), so it imports one module while pinning another. It refuses with FROZEN_INPUT_CHANGED, so no result is affected.
- **Undetected and unarchived.** #155's P8 freeze does not hash `run.py`, so nothing detects the edit. The original bytes have no archival copy (EG).
- **A second false "kept" (OS).** OS checked every map entry against git blobs. A second "kept" entry differs from its lineage head: `MIND-LINEAGE-SOURCE-MANIFEST-2026-10-14.json`, where HEAD ≠ `047549f` because archival-copy labels were appended.
- The coverage test never compares dispositions with the tree. Record line 252 says no frozen file changed.

**Minimal fix.**
1. Restore the original bytes of `run.py`; it refuses at this head either way. Alternatively, archive the original under `lineage-archive/pr155-ef5f078/` and set the disposition to "modified: import retargeted", citing the original sha.
2. Set the manifest entry's disposition to "extended".
3. Extend the coverage test: "kept" and "selected:<lineage>" entries must equal that lineage's blob, and "merged", "extended" and "modified" entries must differ from it.

**Lens disagreement.** EG rates this medium under the frozen-evidence rule. AE and OS rate it low, because the change is benign and the runner fails closed.

---

## Low

### L1. #155 evidence directories point at collided paths; the P8 disclosure is displaced; the archive has no README; the manifest is stale

- **Lens:** EG.
- **Gate:** G1.
- **Location:**
  - `docs/evidence/greg-learned-routing/2026-10-07/README.md:83-85`
  - `docs/evidence/greg-composition-lift/2026-10-14/README.md:3,34`
  - `docs/evidence/greg-protected-evolution/2026-10-14/`
  - `docs/collaboration/lineage-archive/`
  - the manifest's `evidence_directories`

**Evidence.**
- #155's in-tree READMEs name runner, freeze and suite paths that now hold #158's files.
- #155's P4 results record `manifest_sha256` `2c8df0ee`; the freeze in the tree is `2edd3d1a`.
- #155's P8 `results.json` sits beside #158's README, which never mentions it, and #155's held-out smoke-run disclosure is reachable only through the archive.
- `lineage-archive/` has no README.
- The manifest names #155's head as `ba8d990` and omits `docs/evidence/pr155-crowd-sparse/2026-10-14`, which now drives crowd's routing status.

**Minimal fix.**
1. Add a non-colliding pointer file, such as `LINEAGE-POINTER.md`, in each of the three directories, giving (commit, path, sha) and the archive location.
2. Add a README to `lineage-archive/` stating that its contents are byte-identical archival copies.
3. Update the manifest's #155 head and `evidence_directories`.

### L2. Merged ledger text and the VPL headline overstate lift

- **Lenses:** EG, OS.
- **Gates:** G9; C.
- **Location:** `docs/FOUNDER_INTENT_LEDGER.md:103`; record `:179`.

**Evidence.**
- **Ledger line 103 (EG).** This line, merged from #155, says "VPL = 4 distinct families with F1".
  - The count includes X2, whose strongest single intelligence was NOT_RUN, and X1, a structural lift against constituents that are incomplete by design.
  - The same line says "Dawid-Skene and PSO admitted". #155 itself later found crowd EXPERIMENTAL, "do not attach as default", and PSO beaten 32/7.
- **Record line 179 (OS).** "Nine distinct families lift over the best single constituent they were measured against" includes:
  - F7, which the builder's own CONFIRMED audit shows is tied on every item by an available exact single method;
  - X2.
- **Added false answers (EG).** The founder's VPL metric requires "no added false answers". Per item, the composition was wrong or abstained where the single method was right on F2R-27, -37, -41 and -87, and on F2b-27, -37 and -41.

**Minimal fix.**
1. Add a dated erratum beside ledger line 103, marking it superseded by the convergence accounting; leave the historical text.
2. Lead section 7 with the count under the founder's definition, and list F7 and X2 as pending rather than as lifts.
3. Report per-item added wrong answers in the VPL table.

**Lens disagreement on the defensible count.** The lenses do not agree on one number.
- OS gives 7: F1, F2, F3, F4, F6, X1 and the derived chains.
- EG excludes X2 and flags X1 as structural.
- CO's evidence would lower OS's count further: F3 is tied on development items by the exact genome (L15), F4's constituent was denied the evidence (M13), and X1 is structural.

### L3. Map inaccuracies, a seed-namespace hazard and a misleading prefix

- **Lens:** EG.
- **Gate:** G3.
- **Location:** `MIND-LINEAGE-RECONCILIATION-MAP-2026-10-14.json:531-535`; `docs/evidence/pr155-crowd-sparse`; `docs/evidence/pr155-f7-audit`.

**Evidence.**
- **Map note.** The note on the index says "genome, recipe and routing rows unchanged; operations and three sources added". In fact `recipes.identify_then_optimize` and `routing.conditional_competence` changed, and six sources were added (8 to 14).
- **Seed hazard.** #155's crowd-sparse held-out seeds 3001-3040 and P6 v3's RNG seeds 3101-3148 lie inside 3000-3999, the range reviewers and #158's builder use for review and development work.
- **Prefix.** The Track B audit is filed under a `pr155-` prefix although it is convergence work, not #155 lineage work.

**Minimal fix.**
1. Correct the map note.
2. Add a cross-lineage seed and data-identity registry that the freeze tools consult.
3. Name convergence evaluations with a `trackb-` or run-id prefix.

### L4. A second attached cognition entry (`cognition.seed.solve`) has no disposition, and the attached count is understated

- **Lens:** AR.
- **Gates:** G5; G3.
- **Location:** `greg/cognition/catalog.py:52-54`; `greg/capabilities.py:872-897`; `greg/cognition/seed_path.py:148-166`.

**Evidence.**
- `registry_view()` attaches 22 cognition capabilities by default, not the 8 the record states:
  - the 8 seed families;
  - solve, compose and knowledge;
  - the cortex router and 7 organs;
  - `cognition.seed.solve`, `cognition.status` and `cognition.settle`.
- `cognition.seed.solve` runs `cortex.seed` methods on its own worker (`greg.cognitive_worker`), with its own verifier and its own `cognition.receipt` journal type, outside the compiler's evidence routing.
- It is a pre-existing #142 governed alternative, but it appears neither in the map nor in the "one canonical cognition entry point: met" claim.

**Minimal fix.**
1. Give it a disposition in the map and record as a registered alternative entry, not a second canonical Mind entry.
2. Either withhold it by default or state why it stays attached.
3. Correct "8 attached by default" to "8 of 72 catalog families".

### L5. Confinement leaks: signals to any process, repo listing and stat, and truth regeneration

- **Lens:** AE.
- **Gate:** G7 (held-out isolation at the information level).
- **Location:**
  - `greg/isolation.py:62` (`code: READ_DIR`) and `:120` (`_Rules` sets only `handled_access_fs`; no Landlock scope)
  - `greg/cognition/genomes/collective.py:2051` (`seed` in the immune data)
  - `greg/cognition/evolution_sandbox.py:45-75` (the sandbox reports its own confinement)

**Evidence** (`/tmp/claude-0/conv/review/adversary_evolution/out/probe2.json`, `.../out/probe179_canonical.json`). Inside the confinement:
- **Signals.** `os.kill(pid, 0)` is allowed for the parent cycle process, PID 1 and the grandparent, and `pidfd_open(parent)` is allowed. The sandbox runs as root here, so a code-level candidate could kill or stop the cycle or any host process.
- **Listing and stat.** `listdir` of the repo root (56 entries) and of `greg/cognition` is allowed, as is `stat` of `m4_weekly.json.gz` (1186460 bytes).
- **Truth regeneration.**
  - Immune labels can be regenerated from `data['seed']`, matching the parent's digest `589054f2...`.
  - Constraint-release truth can be regenerated by matching inputs over development seeds 0-9, matching digest `cd7aa09a...`.
- Today's candidates are data and the methods are reviewed, so these are latent channels, not exploits.

**Minimal fix.**
1. On Landlock ABI 6 or later, set `scoped = LANDLOCK_SCOPE_SIGNAL | LANDLOCK_SCOPE_ABSTRACT_UNIX_SOCKET`.
2. Drop the code-root `READ_DIR` grant for the P8 sandbox.
3. Strip regenerable identity (the seed) from sandbox requests.
4. Have the parent check the confinement itself rather than trusting the child's report.
5. Make all four steps a stated precondition before any code-level candidate space is allowed.

### L6. Target.validate accepts bool and float for int choices; a TypeError aborts a whole cycle

- **Lens:** AE.
- **Gate:** closed mutation spaces (the founder's P8 list).
- **Location:** `greg/cognition/evolution.py:86-91`; `greg/cognition/evolution_sandbox.py:66`.

**Evidence.**
- `tournament=True`, `mu=2.0`, `fit_window=156.0` and `detectors=1000.0` are all accepted, and `config_id(mu=2.0)` differs from `config_id(mu=2)`.
- Downstream, the constraint-release and immune genomes refuse these values (GenomeError). The forecasting genome raises a TypeError that line 66 does not catch, so the sandbox exits 1 and the cycle aborts.
- The proposed tests `test_int_choices_refuse_bool_and_float[*]` fail 4 of 4 on HEAD.
- There is no route to this through `cycle()` today: mutate and crossover draw only declared values.

**Minimal fix.**
1. Compare choices type-strictly: equal value and identical type, with bool excluded for int.
2. Catch exceptions per problem in the sandbox, so an error is recorded per item.

### L7. The single-controller AST test misses two importer forms

- **Lens:** AE.
- **Gates:** G6; no two independent evolution controllers.
- **Location:** `tests/unit/test_greg_mind_convergence.py:54-61`.

**Evidence.** In a scratch clone, AE added two importers:
- `evolution/p8_shadow_probe.py`, a static import of `evolution_routing` in a top-level package the test does not scan;
- `greg/p8_dynamic_probe.py`, which loads it with `importlib.import_module('greg.cognition.' + 'evolution_routing')`.

`test_one_evolution_controller_is_reachable_from_runtime` still passed, and the dynamic module returned `evolve`. No such importer exists today; AE verified this by grep across the tree.

**Minimal fix.**
1. Scan every top-level package except tests, docs and `lineage-archive`.
2. Fail on any non-test source that contains the string `evolution_routing` outside `cortex/evaluation/evolution/run.py`.

### L8. Integrity overclaims in live records

- **Lens:** AE.
- **Gate:** the directive's "without fabricating progress".
- **Location:** `greg/path.json:1650` (P8 reality), `greg/path.json:1661` (`pr155_lineage`); `docs/FOUNDER_INTENT_LEDGER.md:103`.

**Evidence.**
1. **The canonical seal.** `path.json` says "sealed evaluator (digest of code, outcomes, inputs, rule)". But "code" covers only the `SealedEvaluator` class and the score function, and the seal is never compared with a frozen value (M14).
2. **The #155 alternative.** `pr155_lineage` says "adversarial probes refused". On #179's code, `/tmp/claude-0/conv/review/adversary_evolution/out/probe179_routing.json` shows three probes ACCEPTED:
   - an edit of the imported `conditional_competence.py` (development correct falls from 57 to 35);
   - a mid-run edit of the development data (57/0 becomes 52/5);
   - a swap between hash and exec (a forged 64/64).

   Its evaluator context is unconfined (WRITE_OK, READ_OK), a non-string key crashes it (AttributeError), and `{}` is accepted and filled from `BASELINE`.
3. **Partition handling.** Any partition other than "dev" runs the held-out branch (`evaluator.py:95`).
4. **The ledger.** The historical ledger text at line 103 says "every protection held".

**Minimal fix.**
1. Correct the two live `path.json` reality strings to say what the probes show.
2. Leave the historical ledger text unchanged and add a dated erratum beside it.
3. List these defects in record section 9 as preconditions before the routing alternative could ever be revived.

### L9. The P8 adoption path relative to the Kernel's evolution loop and `greg/improvement.py` is not escalated

- **Lens:** AE.
- **Gate:** G13.
- **Location:** record sections 5 and 9 (no mention); `greg/cognition/evolution.py:1-3`.

**Evidence.**
- Three mechanisms in the tree can decide improvements:
  - the Kernel's `evolution/loop.py` ClosureLoop (Retain/Regress/Kill);
  - `greg/improvement.py`, which auto-retains the `brief.attention` lever;
  - P8, which emits PROPOSED_NOT_APPLIED proposals, with adoption described only as "a reviewed change; founder decision".
- There is no apply function (verified), so there is no current risk.
- The record does not say which decider would adopt a P8 RETAIN, and `evolution.py:3` calls P8 "the only route by which GREG's cognition may change itself". This session's earlier analysis had flagged the question for the Systems Architect and a founder decision.

**Minimal fix.**
1. Record the decision as an escalation: P8 only proposes; adoption is a reviewed change, recorded as an EvolutionCapsule with a founder decision.
2. Add an integration test that a synthetic RETAIN record changes no shipped constant.

### L10. PMCF's audited F7 result is credited to flow_expansion_mcf, a different algorithm never run on F7

- **Lens:** F7.
- **Gate:** G11.
- **Location:** record `:194-196` ("exact on every audited item, a single certified intelligence ... That intelligence is #158's flow_expansion_mcf"); `greg/cognition/genomes/flow.py:684-686` (`known_strengths`).

**Evidence.**
- **The audited arm** is `run_v4.parametric_min_cost_flow`: bisection plus NetworkX network simplex, with no certificate.
- **`flow_expansion_mcf` 1.0.0** (`aa23c8a`, committed at 05:19, after the F7 run at 05:11) is successive shortest paths with Bellman-Ford and a dual or cut certificate.
- The two share the formulation, not the algorithm. `flow_expansion_mcf` has no F7 or admission evidence at any version.
- The record calls the audited method "certified"; PMCF is not.

**Minimal fix.**
1. Reword: "PMCF (the same split-arc formulation, a different algorithm, uncertified) tied the composition 200/200. `flow_expansion_mcf` 1.0.0, which carries its own certificate, has development evidence only."
2. Set the genome's `known_strengths` to "not yet measured on F7".

### L11. The index recipe row records F7 as VPL_LIFT with no tie note, and the compiler ranks that status first

- **Lens:** F7.
- **Gate:** G9.
- **Location:** `docs/evidence/greg-mind-evidence-index.json:1467` (`recipes.graph_then_allocate`); `greg/cognition/compiler.py:36,523`.

**Evidence.**
- The row has status VPL_LIFT, wins 92, `prefer` null, and no tie field.
- `STATUS_RANK` makes VPL_LIFT 0, above UNEVALUATED 2.
- With both payload shapes present, the composition is selected over the attached exact genome (`/tmp/claude-0/conv/review/f7_crosscheck/route_probe.out`).

**Minimal fix.**
1. Have `build_mind_evidence_index` carry the practitioner and exact-single ties from the frozen summary, for example `tied_by: parametric_min_cost_flow`.
2. Once `flow_expansion_mcf` is admitted, re-derive the recipe's status against it.

### L12. The F7 scorer accepts fractional plans, and the builder's audit coerces them with int() (latent)

- **Lens:** F7.
- **Gate:** T7 (scorer integrity for future runs).
- **Location:** `cortex/evaluation/composition_lift/run_v4.py:224-238` and `greg/cognition/genomes/flow.py:307-313` (no integrality or exceeds-optimum check); `cortex/evaluation/pr155_f7_audit/audit.py:197` (`int(x)` truncates).

**Evidence** (`/tmp/claude-0/conv/review/f7_crosscheck/frac_probe.out`, development item F7-abilene-2):
- An LP-relaxation plan with throughput 58.957, against an integer optimum of 58, is scored "suboptimal", not "wrong".
- The audit would truncate the same plan to integers rather than refuse it.
- `flow_expansion_mcf`'s verifier refuses it (`output_well_formed False`).
- The recorded results contain 0 non-integer increments, so no verdict changes.

**Minimal fix.** In the next harness and admission versions, not the frozen ones:
1. Reject non-int or bool increments.
2. Score a throughput above the optimum as "wrong".
3. Have the audit refuse non-integers instead of coercing them.

### L13. The latency range is stale, and the audit freeze pins no solver versions

- **Lens:** F7.
- **Gate:** DL (reproducible results).
- **Location:** record `:182`; `cortex/evaluation/pr155_f7_audit/freeze.json`.

**Evidence.**
- "Every lift costs latency (1.5-5.2x)" sits under a table that includes F7, whose frozen ratio is 5.314x.
- The audit freeze hashes 3 files but records no SciPy, HiGHS or NetworkX versions; `run_v4`'s freeze records them.

**Minimal fix.**
1. Say "1.5-5.3x (F7 5.31x)".
2. Record the dependency versions in an audit erratum or in the next audit freeze.

### L14. The map never classifies the three exact implementations of budgeted capacity expansion against each other

- **Lens:** F7.
- **Gate:** G3.
- **Location:** map `:839` (`greg/cognition/genomes/flow.py`: "complementary", "present in one lineage only").

**Evidence.**
- `graph_then_allocate`, `flow_expansion_mcf` and `expansion_truth` (which `run_v4`'s PMCF duplicates) are interchangeable for one geometry.
- The founder asked specifically whether the simpler exact method should become canonical. The answer exists only in prose (section 8), not as a map disposition.

**Minimal fix.** Add a mechanism-level map entry:
- classification: interchangeable implementation;
- disposition: unresolved, pending admission v3 and the compiler fix (M10);
- `flow_expansion_mcf` recommended canonical;
- the composition kept as a registered alternative or fallback.

### L15. F3 (generated networks) is listed with no tie caveat, though the exact single genome ties it

- **Lens:** CO.
- **Gate:** G10.
- **Location:** record `:170`.

**Evidence.**
- On #179, using #158's F3 development items F3-1 to F3-8: `flow_expansion_mcf` alone (operation `expand_capacity_mcf`, same isolated worker and verifier) is 8/8 correct, the same as the composition; greedy is 5/8.
- The frozen 11-0 was measured against greedy before the exact genome existed.
- Section 7 attaches the tie caveat to F7 only, although both families run the same recipe.

**Minimal fix.** Add to F3's row: the lift is over greedy; the exact single genome ties it on development data; an admission of `flow_expansion_mcf` followed by a re-measurement decides both F3 and F7.

### L16. P6 v1's freeze-before-run ordering cannot be verified from git; #158's v3 README misstates how v1 was run

- **Lens:** CO.
- **Gates:** G1; FZ.
- **Location:** `docs/evidence/greg-composition-lift/2026-10-07/results.json` (`source_commit` `1521bd1`); commit `e450218`; `docs/evidence/greg-composition-lift/2026-10-14-v3/README.md` ("each ran in a clean worktree at its freeze commit").

**Evidence.**
- `freeze-v1.json`, `run.py` and `results.json` were all added in the same commit, `e450218`.
- The recorded `source_commit` `1521bd1` contains neither `run.py` nor `composition.py`, so the held-out run used an uncommitted working tree.
- The pins do match `e450218`, and the development stage reproduces there exactly ({8, 8}). The pre-registration ordering rests only on the README's word.
- EG found the same pattern for #155's admission v1 (H4).

**Minimal fix.** Add an erratum to the source manifest, not to the frozen files: v1's freeze and results were committed together; the run's `source_commit` lacks the runner; the development stage reproduces at `e450218`.

### L17. No procedure is given for reproducing the frozen P6 runs; the record names only #155's runners as refusing at HEAD

- **Lens:** CO.
- **Gate:** DL (reproducible test commands).
- **Location:** record `:86`; source manifest (retrieval is per-file `git show` only).

**Evidence.**
- All six P6 runners fail their freeze check at HEAD, including #158's v1-v4, not just #155's.
- Reproduction needs the full tree at the freeze commit. CO reproduced the v1 and v2 #158 development stages exactly from a `git archive` of the freeze commit; per-file `git show` cannot do this.

**Minimal fix.**
1. Document the procedure: `git archive <freeze-commit> | tar -x -C <dir>`, check that `runner.inputs()` equals the manifest, then run the development stage.
2. State that every P6 runner, from both lineages, refuses at HEAD.

### L18. The rollback instructions do not work as written

- **Lens:** OS.
- **Gate:** DL (rollback instructions).
- **Location:** record `:374-385` (section 14; unchanged at the live head `c7a7ad5`).

**Evidence.** OS ran trial reverts in a scratch worktree at `ccd38a2`:
- `git revert 49b2d58` conflicts in `test_greg_mind_convergence.py` (modify/delete) and `test_mind_evidence_sources.py`.
- `git revert 8bbd3b8` conflicts in the map (modify/delete) and in `test_greg_mind_convergence.py`.
- `git revert e21bb5b` fails: it is a merge and no `-m` is given.
- `git revert 6e62b59` applies cleanly.

The core merge `2d1ddd3` is not listed, nor are the later commits `8a43e70`, `4b445db` and `c7a7ad5`. Closing the draft PR, the primary rollback, does work.

**Minimal fix.**
1. State that per-step rollback means reverting in reverse order, from `6e62b59` back to `49b2d58`, with `git revert -m 1` for merge commits. Alternatively, give a branch-reset recipe: reset to `ef5f078` plus a cherry-pick list.
2. Cover `2d1ddd3` and every later commit, and test the recipe once.

### L19. The map reports 0 "unresolved" while the record calls the intervention generators' merit unresolved; the alternative is an unlabelled founder-facing CLI command

- **Lens:** OS.
- **Gates:** G3; dissent preserved; alternatives isolated.
- **Location:** map `:706` (`advantage.py`: interchangeable / alternative:isolated); record `:70` ("0 unresolved") and `:315` ("(f) kept: unresolved merit"); `greg/cli.py:109`; `greg/cognition/advantage.py:219`.

**Evidence.**
- The founder's classification list includes "unresolved architectural decision", and the Systems Architect dissent says the two generators are kept "because their relative merit is unmeasured". Yet the map has no "unresolved" entry.
- `greg cognition advantage` returns schema `greg-advantage-compiler/0.1` with candidates and `authority_created False`. Nothing in the output says it is a non-canonical alternative to `foundry.lawful_leverage`, and the CLI help reads like a first-class compiler.

**Minimal fix.**
1. Classify `advantage.py` as "unresolved" in the map, with the deciding experiment in its note.
2. Add an alternative status and a pointer to `foundry.lawful_leverage` in the command's output and help, or move the command behind an explicit `--alternative` flag.

### L20. The five review responsibilities and the two strengthening passes are met in form but not in substance

- **Lens:** OS.
- **Gate:** RV.
- **Location:** record `:223` (the builder performed all five roles) and `:275-330` (Pass 1 and Pass 2).

**Evidence.**
- At `ccd38a2` the builder performed all five roles itself, and agrees this is not independent review. This session supplies independent Adversarial, Evidence/Welfare, Operator and Founder-Intent review, but no independent Systems Architect is named.
- Pass 1 lists no performance weakness (latency and maintenance cost appear only in section 7), and it compares only "#158 alone" as the simpler alternative, never "#155 alone".
- Pass 2 is a disposition table rather than a re-attack. It marked (b) "resolved" while operation verdicts were still unbound (H5), which the builder itself later addressed in `c7a7ad5`.

**Minimal fix.**
1. Name an independent Systems Architect reviewer, or record that role as not independently reviewed.
2. In Pass 2, record the new attacks attempted and their outcomes, and reopen (b), citing `c7a7ad5`.
3. Add performance weaknesses to Pass 1: latency, CI time and the cost of the lineage-specific index table.

### L21. The "still unverified" account is incomplete, and one escalation can be decided by engineering evidence

- **Lens:** OS.
- **Gates:** DL; "escalate only genuinely unresolved founder-authority, legal or material architectural choices".
- **Location:** record `:386-404` (section 15).

**Evidence.**
- The account omits:
  - the #158 drift after `047549f` (M18);
  - the missing live harness for operation families (M17);
  - the role not reviewed independently (L20);
  - an "independently verified" count. The founder asked to distinguish inventoried, implemented, independently verified, admitted, attached and exercised, but `GenomeEntry` (`genome_library.py:95`) has no such field.
- Escalation 3, whether `flow_expansion_mcf` becomes canonical, can be decided by its pre-registered admission rule. Attaching it is already covered by escalation 4.

**Minimal fix.**
1. Add the omitted items to the unverified list.
2. Add an `independently_verified` field to the inventory, backed by verifier-mutation evidence.
3. Replace escalation 3 with a pre-registered decision rule: "DEFAULT_FOR_GEOMETRY at admission v3 makes it the routed default; attach remains founder-only".

**Lens disagreement.** F7 and CO both recommend making `flow_expansion_mcf` canonical after pre-registered evidence and the compiler fix (M10). They do not say whether that decision needs the founder. OS says it does not; the builder escalates it.

### L22. #155's developmental-sweep runner can still run at HEAD and would overwrite a historical result unchecked

- **Lens:** OS.
- **Gate:** G2 ("historical measurements must not be rewritten").
- **Location:** `cortex/evaluation/developmental_sweep/run.py:114-133`.

**Evidence.**
- The hash-only probe reports "WOULD RUN": the frozen inputs are unchanged at `ccd38a2`.
- `main()` writes `args.out` with no existence guard. A rerun pointed at `docs/evidence/greg-developmental-sweep/2026-10-14/results.json` would replace its `source_commit` and `finished_at`.
- That result is not a digested source in the evidence index or the lineage manifest, so CI would not detect the rewrite.

**Minimal fix.** Without editing the frozen runner, add the committed results file and its sha256 to the lineage source manifest or the index sources, so a rewrite fails `test_mind_lineage_manifest` or `test_mind_evidence_sources`.

---

## Acceptance gates

### Founder acceptance gates

| Gate | Builder's record | This review | Basis | Findings |
|---|---|---|---|---|
| G1 Both lineages recoverable, evidence independently inspectable | met | **Met** | Archives byte-identical and equal to `git show`; 16 archival copies match their manifest digests (EG, OS, AE). Development stages reproduce at the freeze commits (CO). | L1, L16, L17 (inspectability gaps) |
| G2 Frozen results not altered | met | **Met at byte level; contested on description** | Every frozen result is byte-identical to its lineage commit (EG, AE, OS, F7). One #155 runner was edited in place; a runner can still overwrite a result; replications are mislabelled. | M20, L22, H1 |
| G3 All conflicts have explicit dispositions | met | **Not met** | Coverage is sound up to #158 `047549f` (OS). But #158 is now at `41a8538` with 5 textual conflicts; two "kept" dispositions are false; several items are undispositioned or mislabelled resolved; admission sources are plural. | M18, M20, L4, L14, L19, M16, H2 |
| G4 Branch passes its own CI, contract, integration, security and regression tests | see PR body | **Met at `ccd38a2` for the tests that exist** | Six canonical-ci jobs succeeded on `ccd38a2` (17:03-17:19 UTC). Locally: 641 passed, 4 skipped, 10 deselected under the review rules (OS); every lens's subset passed. But derive() has zero coverage, verifier forgeries pass, and a P8 promotion passes. | M9, H3, M4, M5, M6, M15 |
| G5 One canonical cognition entry point | met | **Met for runtime dispatch, with qualifications** | One `SOLVERS` table at runtime; every request shape re-enters `cortex.reason` (AR). `cognition.seed.solve` is an undispositioned second attached entry; derived chains cannot be reached from the compiler. | L4, M7, M10 |
| G6 Alternative engines cannot silently assume live authority | met | **Met for authority; the founder decision surface is defective** | Founder-only attach, VERIFIED defaults, no runtime importer of `evolution_routing`, `authority_created` false (AR, AE, OS). But Genesis offers REJECTED families, attach asks omit evidence, the mission hook recommends COMPOSITION_ONLY genomes, and the AST test can be bypassed. | H2, M1, M2, L7 |
| G7 Protected evaluator cannot be modified by its candidates | met | **Met for today's data-only candidates; not established for code-level candidates** | AE: no file or network escape. The seal misses method code and pre-run edits and is never checked against a pre-registered value; latent confinement channels remain. | M14, L5 |
| G8 No rejected P8 configuration promoted | met | **Met (untested)** | Every shipped default equals its incumbent (AE). A promotion would pass every cited test. | M15 |
| G9 No NO_GAIN result presented as positive lift | met | **Met for NO_GAIN verdicts; lift accounting overstated** | No NO_GAIN verdict is shown as lift on any surface checked (EG, F7, CO). Headline counts, an index row and the latency claims overstate. | L2, L11, M12, M13 |
| G10 Strong standalone and practitioner baselines included when relevant | met where measured | **Not met** | Strawman or missing competitors, an oracle baseline, a throughput-only tie, a constituent denied the evidence, an unstated exact-genome tie. | H4, M3, M11, M13, L15 |
| G11 Genome admission bound to the exact tested version | met | **Not met** | Operation and recipe verdicts are unbound (EG, AR, OS, CO); genome binding is to a version label only (AE); no live harness exists for re-admission; a verdict is credited to the wrong genome. | H5, M15, M17, L10 |
| G12 Mission interruption and restart do not duplicate consequential actions | met in tests | **Met in tests** | SIGKILL no-duplicate, detachment-restart and multi-claim settlement tests pass; keys are deterministic (AR, OS). No body or reboot evidence. | none |
| G13 Kernel, event spine, authority, shutdown and founder boundaries preserved | met | **Met for authority and founder decisions; event spine and shutdown unverified** | `check_authority_singleton.py` passes; `authority_created` false on every receipt path checked; attach is founder-only (AR, OS). No lens examined the event spine or shutdown. The P8 adoption decider is unescalated. | L9 |
| G14 No live deployment or external consequence authorized | met | **Met** | Nothing deploys, attaches or contacts anyone (OS). | none |

### Directive requirements outside the gate list

| Requirement | This review | Findings |
|---|---|---|
| D: Third-party data rights flagged and kept out of a release | **Not met**: flagged, but the scope is incomplete and nothing executable enforces exclusion | M19 |
| T7: Every retained intelligence runs through independent verification | **Not met** | H3, M4, M5, M6, L12 |
| T7: Every retained intelligence runs through the single canonical interface | **Not met** for derived chains, and for `flow_expansion_mcf` on `capacity_network` requests | M7, M10 |
| T5: Canonical mechanisms selected by evidence, not recency | **Not met** for the P4 and `identify_then_optimize` deciding rows | H1, M11 |
| R: Distinguish inventoried, implemented, independently verified, admitted, attached and exercised | **Not met** | H4, M16, L21 |
| C: No composition-superiority claim over deliberately incomplete constituents | **Met for general claims** (CO searched 196 files); per-family caveats missing | M13, L15, L2 |
| Independent F7 audit against parametric min-cost flow | **Met procedurally** (EG, F7, OS); conclusions need correction | M10, M11, M12, L10 |
| FZ: Fresh freeze before held-out execution for new evaluations | **Met for the F7 audit**; not machine-enforced for future P8 cycles | M14, L16 |
| RV: Five review responsibilities; exactly two strengthening passes | **Not met in substance**; no independent Systems Architect | L20 |
| DL: Reproducible commands, rollback, precise unverified account | **Partially met**: rollback does not work as written; reproduction procedure missing; unverified list incomplete | L13, L17, L18, L21 |

### Unverified by any lens

- CI and behaviour at the later heads `4b445db` and `c7a7ad5`, including `c7a7ad5`'s operation-binding change. The F7 lens checked that `ccd38a2..4b445db` changes no F7, flow, compiler or verification file. Nobody tested `c7a7ad5`.
- The 10 deselected tests that build held-out or P8-reserved partitions, and the recomputation of #158's P8 seals. Both are forbidden by the review's seed rules.
- The event-spine and shutdown boundaries under G13.
- Landlock confinement on GitHub runners and macOS.
- F7 held-out truth. The lenses re-derived truth on development items only (50/50 against an independent MILP) and rely on the builder's audit for held-out items.
- Restart on a real body, reboot persistence, VEPMC (0).
- Legal clearance of the SNDlib, M4, fpp3 and Uber/TLC data (founder or legal).

---

## Checked and sound

**Frozen evidence and lineage recovery**
- **The eight collision paths.**
  - Each original path's tree bytes equal #158's commit and match the manifest's sha256 and byte count.
  - #155's versions are byte-identical in `docs/collaboration/lineage-archive/pr155-ef5f078/` and equal to `git show`; all 16 archival copies match their digests (EG).
  - The collided paths are byte-identical at `a832c73`, `77b61a1`, `047549f` and `41a8538` (OS).
- **Every other changed evidence file is intact.** Every other file under `docs/evidence`, `cortex/evaluation`, `verifier/runs` and `docs/intent` that either lineage changed is byte-identical to its lineage head: 39 #155 paths at `ef5f078`, 58 #158 paths at `047549f`. The exceptions are the rebuilt evidence index and #155's P8 runner (M20) (EG).
  - No file of either lineage head is missing from #179 (OS).
  - All nine `greg-protected-evolution` files are byte-identical to their source commits, and both colliding READMEs are archived byte-identical (AE).
- **Disclosures preserved.** Negative and contamination disclosures survive byte-for-byte: the M4 reuse erratum, #155's P8 smoke-run disclosure, the crowd-sparse "do not attach" README, and every REJECT, PARITY and NO_LIFT record (EG).
- **Freeze refusals and P6 reproduction.**
  - #155's frozen runners refuse at HEAD with FROZEN_INPUT_CHANGED: `genome_admission/run.py`, `run_v2.py`, `pr155_crowd_sparse` and `evolution` (OS, AE).
  - At their freeze commits, all six P6 freezes' pins match. The P6 v1 (`e450218`) and v2 #158 (`07350d4`) development stages reproduce exactly (CO).
- **F7 frozen artifacts.** Each was committed once. The 200-row held-out summary recomputes exactly: counts, medians, latency ratio 5.314, 92-0 against the best constituent, 19-0 per network. Routed, static and compiled answers are identical on 200/200 (F7).
- **Map coverage up to #158 `047549f`.** 185 entries, no duplicates, all 22 shared paths present, lineage fields consistent with git, no renames (OS).

**Authority, attach and controllers**
- **One solver dispatch.** At runtime only `greg/cognition/worker.py:86` calls `SOLVERS[family]`.
  - The compile, chain and problem request shapes all re-enter `cortex.reason`.
  - Genome answers run in the network-denied worker and are checked in a separate verify process.
  - Repertoire and genome family names are disjoint (AR).
- **Default states.** 64 of 72 catalog families start VERIFIED (registered and withheld), and the 8 seed families start ATTACHED (EG, AR, OS).
  - Attach happens only through a founder-signed `CAPABILITY_ATTACH` (`body.py:292-300`), and Genesis never attaches a cognition capability (`genesis.py:1043-1053`).
  - `authority_created` is false on every receipt path checked (AR).
- **One evolution controller.** `greg/cognition/evolution.py` and `evolution_sandbox.py` are byte-identical to #158's, and every P8 dependency is byte-identical to `047549f`.
  - `evolution_routing` is imported only by the historical runner and its own test, and no apply function exists (AR, AE, OS).
- **Gravity writes nothing.** A Goal Gravity turn uses a read-only journal; the attach ask comes back PREPARED_NOT_RECORDED (AR).
- **Landlock.** There is one grant path, and #179 adds an ancestor guard (AR). AE found no file or network escape: writes, reads of held-out data, `/proc/<ppid>/environ` and `mem`, `process_vm_readv` and the network are all denied.
- **Canonical P8 engine.** It refuses out-of-schema keys, NaN, bool-for-float and code strings, and raises EVALUATOR_TAMPERED for in-memory and on-disk score-source edits (AE).
- **No P8 promotion today.** Every shipped default equals its record's incumbent, and no rejected candidate id appears in code (AE, EG).
- **Scripts and consequences.** `check_authority_singleton.py` and `check_schema_refs.py` pass; nothing deploys, attaches or contacts anyone (OS).

**Routing behaviour**
- **Independent 68-signature routing diff.** AR compared `047549f` with `ccd38a2` under the default and the all-attached registries.
  - Only anomalies, quorum and simulate change.
  - `crowd_label`, `swarm_minimize` and `evolve_blackbox` are new, and blackbox is rejected.
  - Every other selected and withheld-best method is identical, which confirms the builder's claim.
- **Organ-superseded families.** SUPERSEDED_BY_CANONICAL_ORGAN families never outrank their organs on the same payload (AR).
- **REJECTED verdicts.** The simulation and evolutionary REJECTED verdicts compare against closed forms from each operation's own inputs, and pattern's REJECTED (6-23 against IQR fences, 1-24 against median/MAD) is sound (AR).
- **P4 drives nothing.** The P4 NO_GAIN verdict drives no runtime choice; conditional memory stays shadow and is labelled as demoted (AR, EG).
- **No overclaims found:**
  - no surface shows a NO_GAIN verdict as lift (EG);
  - no document presents F7 as lift over an OR practitioner (F7);
  - none of the 196 changed files claims superior general intelligence (CO).

**Restart and tests**
- **Restart.** The SIGKILL no-duplicate, detachment-restart and multi-claim settlement tests pass on #179, and the mission, compiler and Genesis keys are deterministic (AR, OS).
- **Test runs.** All pinned to core 0, read-only:
  - OS: 641 passed, 4 skipped, 10 deselected;
  - AR: 139 unit, 12 integration and 41 convergence/evidence tests;
  - AE: 64 passed, 6 deselected;
  - EG: 69;
  - F7: 38;
  - CO: 23 passed, 2 skipped.
- **CI.** All six canonical-ci jobs succeeded on `ccd38a2` (OS).
- **Test edits.** Track B's edits to two #158 tests strengthen them, and no skip or xfail was added to hide a defect (OS).
- **Record counts reproduce** (OS):
  - 72 families; 126 inventoried, 97 implemented, 93 integrated;
  - DEFAULT 27, NICHE 9, COMPOSITION_ONLY 7, SUPERSEDED 12, REJECTED 4, EXPERIMENTAL 40, FRONTIER_HORIZON 27;
  - `genome_library.check() == []`.

**Composition**
- **Clean merge.** The merge of `composition.py` is a clean union, about 47 added lines. Every operation-recipe body is byte-identical to #158's.
- **No behaviour change for #158's families.** derive() returns None on all 39 F3-F6 development payloads, so F5 and F6 behave as on #158, and #158's F2R, F3 and F4 development items score 8/8 routed and pinned (CO).
- **How the two mechanisms relate.** derive() reproduces both v1 template recipes exactly and cannot express any operation recipe. So derive() subsumes the two template recipes, while the operation recipes and derive() are complementary (CO).
- **Derived chains vs the fixed recipe (development and review seeds).** Derived chains beat the fixed estimate recipe 9-0 (one-sided p = 0.002). This suggests a pre-registered re-measurement is worthwhile; it does not replace the frozen NICHE verdict (CO).

**F7**
- **Truth.** F7's truth is exact for the declared model (convex, non-decreasing cost; total unimodularity at fixed flow). PMCF uses the same formulation as `expansion_truth` (F7).
- **Development cross-check (50 items).**
  - `expansion_truth` equals an independent HiGHS MILP on 50/50.
  - PMCF, `flow_expansion_mcf`, the composition twin, the routed chain and the one-stage op are each optimal on 50/50; greedy on 23/50.
  - CP-SAT reported OPTIMAL on 50/50 (F7).
- **`flow_expansion_mcf`'s certificate.**
  - It verifies on 50/50 development items, 41 by dual bound and 9 by cut.
  - It refuses a suboptimal plan that carries a borrowed certificate.
  - The dual bound is valid weak duality.
  - At the 400-edge ceiling (review seeds 3000-3002) it matches PMCF and is 14-47x faster (F7).
- **The builder's F7 audit.** Its MILP is correct, and the freeze precedes the run (frozen 16:23:41, committed 16:24:06, finished 16:24:12). The verdict rule was frozen, it imports nothing from `run_v4` or the flow genome, and the development-only smoke run is disclosed (EG, F7, OS).
- **No parallel links.** The SNDlib extract has no parallel links, so the load overwrite in `corridor()` is harmless (F7).

**Data and reality labels**
- **Data rights.** The SNDlib, M4 and fpp3 extracts are flagged as a release blocker, and `pyproject` packages no evidence data today (EG, F7, OS).
- **Reality statements.** The section 2 statements are accurate: not founder-used, not reboot-verified, VEPMC 0, nothing attached by any evaluation (EG).
- **Seed hygiene.** #155's admission seeds do not overlap P8's reserved 7000-8059 (AE).

---

## Disagreements preserved

### With the builder's record

| Builder's claim | Lens position |
|---|---|
| F2, F2R and F2b are "an independent replication"; P4 "no gain twice" on "different suites" (section 5 `:124`, section 6 `:154`, ledger `:24`) | EG, CO disagree: F2b and #155's P4 v3 are same-instance subsets of #158's runs (H1). Only F2 to F2R is a replication. |
| Steward's dissent: "no current verdict depends on" latest-run-decides | CO partly disagrees: the `identify_then_optimize` deciding row is a strict-subset re-run that replaced its superset (H1). EG and CO both endorse escalating the rule to the founder. |
| G11 "genome admission bound to the exact tested version: met" | EG, AR, OS, CO disagree for operation families and recipes (H5); AE adds that genomes bind only to a version string (M15). The record's own section 15 concedes this. |
| "36 admitted"; operation verdicts are "held-out runs against stated competitors" (`:73`, `:122`) | EG disagrees: 19 are admitted under a pre-registered, version-bound rule; 4 of 9 DEFAULT operation families had no competitor; admission v1 was not pre-registered in git (H4). |
| "(a) one index: resolved" | AR, EG disagree: Genesis, `attach_ask`, `ORGAN_ADMISSION` and `mind_status` still read other sources (H2, M1, M16). |
| collective "REJECTED 7-11 against simple majority" | AR disagrees: REJECTED comes from 5-16 against an oracle-informed baseline; 7-11 against majority is not significant (M3). |
| The Adversarial Reviewer role found and fixed two defects | AR disagrees: three repertoire verifier gaps are unmentioned and reproduce on #179 (H3, M4, M5). |
| No frozen file changed; the P8 runner is "kept" | EG, AE, OS disagree: it was edited at its original path, and the manifest entry also differs (M20). |
| Release blocker scoped to three extracts | EG disagrees: frozen suites, results and logs embed the same data, with no executable guard (M19). |
| Attach asks report each family's true measured admission (section 16) | EG, AR disagree for #155 families (M1). |
| "64 of 72 VERIFIED; the 8 attached are the seed families"; one entry point | AR: 22 cognition capabilities are attached by default, including the undispositioned `cognition.seed.solve` (L4). |
| Two Goal Gravity hooks "with disjoint outputs on one asks contract" | AR: the outputs are disjoint, but the rules diverge; the #155 hook recommends COMPOSITION_ONLY genomes (M2). |
| "Both lineages' families run through" the compiler; "operation recipes dispatch first" | AR, CO disagree: derived chains are unreachable from the compiler (M7), and derive() overrides the ambiguity refusal (M8). |
| PMCF "about 300 times faster"; "that intelligence is #158's flow_expansion_mcf"; a "certified" method | F7, CO disagree on the comparison and the attribution (M12, L10). |
| A pre-registered admission alone makes `flow_expansion_mcf` canonical | F7 disagrees: a compiler change is also required (M10). |
| The F7 tie is complete | F7 disagrees: the tie is on throughput only; the composition wastes budget (M11). |
| The protected evaluator "met" because sealed-evaluator tampering is refused | AE agrees only for data-only candidates: the seal misses method code and pre-run edits (M14). |
| "No rejected P8 configuration promoted: met" because nothing is attached | AE agrees it is met today, but the cited evidence would not detect a promotion (M15). |
| Every conflict has a disposition (185 entries) | OS agrees as of `047549f`, but not for the PR as it stands (#158 at `41a8538`) (M18). |
| "0 unresolved" | OS disagrees: the intervention generators' merit is called unresolved in the record (L19). |
| Rollback by per-commit revert | OS disagrees: the reverts conflict or fail as written (L18). |
| Nine families lift; P6 lifts listed without caveats for F3 and F4 | OS, EG, CO disagree on the headline (L2), and CO on the missing per-family caveats (M13, L15). |
| `#155`'s frozen runners refuse at HEAD (only #155's are named) | CO: every P6 runner from both lineages refuses; no reproduction procedure is given (L17). |

Points where the lenses agree with the builder:
- the selection of #158's evolution controller;
- one Landlock grant path;
- the evidence index as the admission source in principle;
- archive handling of the 8 collided paths;
- the F7 audit procedure;
- the data-rights flag as a release blocker;
- "every other top choice unchanged" (AR's independent 68-signature diff);
- the read-only Gravity turn;
- no runtime importer of `evolution_routing`;
- founder-only attach;
- the restart tests;
- the F7 conclusion that the exact min-cost-flow genome should be admitted and F7 re-measured;
- that self-performed review roles are not independent.

### Between lenses

- **Severity of H5 (version binding).** EG: high. AR and OS: medium. CO: low for the recipe part. All agree the gate is not met.
- **Severity of M20 (P8 runner edit).** EG: medium. AE and OS: low.
- **Severity of M16 (plural admission surfaces).** EG: medium. AR: low, because routing is unaffected and only reporting is wrong.
- **Severity of M12 (latency claim) and M18 (#158 drift).** F7 and OS: medium. CO: low.
- **Latency on GREG's path.** F7: 3.7x per-item median under contention, about 4-5x unloaded. CO: 5.4x on sequential medians. Both reject the 300x figure.
- **Derived chains in the compiler (M7).** AR observed PLANNED with Fermi at `execute: False`; CO observed ABSTAIN with no deficit at `execute: True`. These are two modes of one defect, not a contradiction.
- **Defensible VPL count (L2).** OS: 7. EG would exclude X2 and flag X1 as structural. CO's per-family evidence would lower the count further. No single number is agreed.
- **Escalating the canonical choice for capacity expansion (L21).** OS: decidable by a pre-registered admission rule. F7 and CO: recommend `flow_expansion_mcf` after pre-registered evidence and the compiler fix, without taking a position on escalation. The builder: escalates it to the founder.

---

## Scope and method

- **What was reviewed.** PR #179 at `ccd38a2`, from read-only copies.
  - Lineage snapshots: `/tmp/claude-0/claude-0/lin155` and `/tmp/claude-0/lin158` (`ba8d990` and `a832c73`); #158 was also checked at `047549f` and `41a8538`.
  - `/tmp/claude-0/pr179`, `/tmp/claude-0/lin155` and `/tmp/claude-0/lin158` were not modified.
  - Nothing was committed, pushed or posted to GitHub.
- **The six lenses:**
  - Evidence/Welfare Guardian
  - Adversary (routing)
  - Adversary (evolution)
  - F7 cross-check
  - Composition
  - Operator/Founder-Intent Steward
- **Constraints.** Every process was pinned to core 0 with `PYTHONDONTWRITEBYTECODE=1`. Probes used development seeds 0-9 and review seeds 3000-3999 only. No frozen held-out evaluation was run, and no instance with a reserved seed was generated.
- **Later heads.** The PR head has since moved to `4b445db` and `c7a7ad5`:
  - the F7 lens confirmed that `ccd38a2..4b445db` changes no F7, flow, compiler or verification file;
  - `c7a7ad5` (operation-binding digests on entry functions, and a #158 merge only up to `202b932`) was not verified by any lens.
- **Where the probes are.** Probe scripts and outputs are under `/tmp/claude-0/conv/review/<lens>/`. This session's earlier analysis is in `/tmp/claude-0/conv/inventory-analyses.json`; it was used as leads and re-checked against #179.
