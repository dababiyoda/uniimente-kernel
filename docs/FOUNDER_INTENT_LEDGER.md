> Continuity companion: `docs/PROJECT_COGNITION_CONTINUITY.md` defines continuous source ingestion, agent context checksum, propagation receipts, repository ecology, and the anti-context-loss test.

# Founder Intent Ledger

## Build the whole prompt first; the device run is its acceptance — 2026-10-30

Founder message in session `session_01Kucyfm6YBHMTjaiC1M9hqD`, verbatim: "Continue building and doing the prompt verbatim. No real Chromebook run is needed. That is done when we completely build the prompt". It answered a report that listed the first Chromebook run (VEPMC 0 to 1) as remaining work. It is intent evidence, not founder authentication.

| Required field | INTENT-20261030-BUILD-BEFORE-DEVICE-RUN |
| --- | --- |
| statement | Continue building and doing the prompt verbatim. No real Chromebook run is needed. That is done when we completely build the prompt |
| source_refs | [verbatim source](intent/sources/FOUNDER-CORRECTION-2026-10-30-source.md); [record](intent/INTENT-20261030-BUILD-BEFORE-DEVICE-RUN.json); the prompt it refers to, `INTENT-20261028-OPUS-MAXIMUS-REISSUE` |
| owner | Alfonso Lopez decides; the integration owner and implementing sessions on board #96 build |
| state | active |
| binding_scope | sequencing of work on the integration line (#196 and its children); reversible implementation and draft review only |
| constitutional_constraints | changed axis: sequence and timing only. The final effect, the evidence ladder (directive section 56) and the authority envelope are unchanged. Nothing built in a container is labelled founder-used, live or externally verified |
| success_evidence | later directive nodes land as draft PRs with fail-before/pass-after tests while VEPMC stays 0; `tests/unit/test_founder_correction_20261030.py` |
| failure_evidence | a container run reported as founder-used; a test key or rehearsal that moves VEPMC or `greg path` N1 |
| dependencies | `INTENT-20261001-FULL-MACHINE-COMPLETION` (VEPMC already stops no unrelated software work) |
| conflicts | `opus-maximus/NEXT_WAVE_AND_HORIZONS.md` §1 names the device run the single bottleneck metric; directive §58 warns against jumping to later nodes. Both resolved by founder sequencing: the metric is kept for device acceptance, and §56's evidence labels apply to every later node |
| next_review_trigger | the founder declares the prompt built, runs the device acceptance, or corrects the sequence again |
| supersedes | reading VEPMC 0 to 1 as the gate in front of the directive's later nodes (sequencing only) |
| superseded_by | none |
| implementation_refs | `greg/metrics.py` (unchanged: nine conditions, founder tier), `opus-maximus/NEXT_WAVE_AND_HORIZONS.md` (dated note) |

## The 77-section master build directive, re-issued with a preamble — 2026-10-28

`INTENT-20261028-OPUS-MAXIMUS-REISSUE` ([record](intent/INTENT-20261028-OPUS-MAXIMUS-REISSUE.json), [complete verbatim text](intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md)): the founder re-sent the 2026-09-30 OPUS MAXIMUS master build directive in full, given twice, behind a new preamble.

The preamble:
- asks for one persistent GREG whose unified agency emerges from an ecology of computational, institutional, economic and human systems and "Different forms of intelligence as described by levin";
- asks that the public community influence GREG while GREG helps it;
- asks for an architecture that absorbs future technology toward "Jarvis/self-driving-car level of mechanistic aliveness", "without confusing that appearance with biological consciousness or allowing operational autonomy to erase legitimate human shutdown authority".

Every section the 2026-09-30 source kept is word for word the same (tested). INTENT-0030 governs the reading: Levin's forms of intelligence compile to the existing multiscale Mind and governed workers, community influence enters as evidence through the untrusted data plane, and "survival" is continuity of function, never a right to survive (section 47). State: active. Authority delta: none. VEPMC: 0.

## Organ pins upgraded — 2026-10-23

Founder message in the #196 session, verbatim: "All organs should have upgraded pins". It is not founder authentication; it settles the open "organ pin upgrade" decision.

| Required field | INTENT-20261023-ORGAN-PINS-UPGRADED |
| --- | --- |
| statement | All organs should have upgraded pins |
| source_refs | #196 session, 2026-10-23; `opus-maximus/NEXT_WAVE_AND_HORIZONS.md` item 3; `opus-maximus/ORGAN_MAP.md` defect 4 |
| owner | Alfonso Lopez decides; the #196 integration owner implements |
| state | implemented on organ branches; organ `main` merges open |
| binding_scope | `uniimente-kernel-boundaries` pins in DALEOBANKS and WealthMachineIntelligence; their CI's cross-organ pin; Canonical CI jobs 7 and 8; `greg/organs.py` keys |
| constitutional_constraints | no merge to any `main`; no new authority; keys exist per invocation only and are never written |
| success_evidence | `tests/unit/test_greg_organs.py` (wrong-organ key and shared scope refused; 5 tests fail without the change); DALEOBANKS 387/387; WealthMachine 126/128 locally (the 2 need port 5000 and fail identically on the old pin); 15-step mission step 9 asserts the certified answer in the packet evidence |
| failure_evidence | WealthMachine holds DALEOBANKS's key in order to verify it, and HMAC lets a verifier forge; WealthMachine counts evidence items but does not read figures; the archive pin is unhashed |
| dependencies | DALEOBANKS #96, WealthMachineIntelligence #44, uniimente-kernel #196 (`e7dc0cbc`) |
| conflicts | the frozen local proof mission and the repository guardian expect `4999acff`/0.1.2 on the organs' `main`; they stay right until the founder merges |
| next_review_trigger | organ CI on #44; founder merge of #96/#44 |
| supersedes | the "organ pin upgrade" open decision |
| superseded_by | none |
| implementation_refs | `greg/organs.py`, `greg/organ_bridge.py`, DALEOBANKS `services/idea_refinery.py`, both organs' `docs/KERNEL_PIN_UPGRADE_2026-10-23.md` |

## Seed Cortex 0.2.2 on GREG's path, stacked on #184 — 2026-10-21

Faithful summary, not verbatim and not founder authentication. Repetition adds no authority.

| Required field | INTENT-20261021-seed-cortex-on-greg-path |
| --- | --- |
| statement | Bring the Seed Cortex 0.1.6 repairs (#167) onto GREG's mission path, verify every further finding independently, and leave the line sound for the first measured capability dividend |
| source_refs | 2026-10-13 founder directive (sha256 `de5db69c...`, preserved on #167); `INTENT-20261019-UPWARD-ASCENT` (#190); the "Resume" of 2026-10-21 |
| owner | Alfonso Lopez; cortex and GREG cognition maintainers implement |
| state | active |
| binding_scope | `cortex/` 0.2.2, `greg/cognition/` bridge, compiler, seed path and evaluation harnesses; draft PR stacked on #184 |
| constitutional_constraints | cognition proposes and never authorizes; no new authority, spend, contact or merge; one authority, many governed capabilities; preserve every superseded freeze and result |
| success_evidence | `tests/unit/test_cortex_seed_ports.py`, `tests/unit/test_greg_seed_port_paths.py` (fail on `900c6ae`; the adversarial review's 19 findings each fail on `1f1e688`); 65 new mutants caught; held-out routed quality 0.964 with 0 critical errors unchanged; crossgeo development and selection dispositions unchanged; seed replay 120/120 at `freeze-v12.json` |
| failure_evidence | none of the repairs shows a gain on the frozen suites (they close failure classes the suites do not contain); model baselines not run (no local model) |
| dependencies | #184 (base); #167 (source lineage); the capability dividend PR that follows |
| conflicts | a contradicted declaration: Genesis deficit here, abstention in 0.1.6; a deficit verified within one receipt here, by recurrence in 0.1.6 (founder decisions, recorded in `docs/cortex/SEED_CORTEX_PORT_0.2.2.md`) |
| next_review_trigger | founder review of the draft PR; the dividend PR's pre-registered run |
| supersedes | none (0.2.1 and `freeze-v11.json` kept as lineage) |
| superseded_by | none |
| implementation_refs | `docs/cortex/SEED_CORTEX_PORT_0.2.2.md`, `docs/cortex/seed-cortex-port-0.2.2.json` |

## Mind to its maximum: successor pilot, evaluator audit, five layers — 2026-10-21

`INTENT-20261021-MIND-MAXIMUM-CONTINUATION` ([record](intent/INTENT-20261021-MIND-MAXIMUM-CONTINUATION.json), [verbatim source](intent/sources/MIND-MAXIMUM-CONTINUATION-2026-10-21-source.md)): continue the complete five-layer Mind to its maximum defensible capability. "Do not stop at P8."

**Kept as recorded:** the NOT_VIABLE immune cycle-7 verdict, its draft and its seeds.

**Authorized:**
- a successor pilot on a narrower immune space, under its own identity and with declared bounds, an exposure audit and stopping rules;
- a survey of second targets among licensed targets already available;
- an independent audit of the 32246ee stress-gate repair and its claim that historical decisions are unchanged;
- a reconstruction of five-layer and section-31 coverage;
- composition, metacognition and Genesis work;
- organ integration through canonical contracts.

**Kept separate, for the founder:** the shared RULE, adoption of cycle 6, genome attachment, data rights, protected merges, spending and live activation.

State: active. Authority delta: none.

Progress 2026-10-21 (measured; negative results kept):

- **Evaluator audit** ([evidence](evidence/greg-protected-evolution/2026-10-21-stress-gate-audit/README.md)) by an independent reviewer.
  - All six past P8 decisions hold on reproduced item-level stress data. Each cycle was re-run at its source commit, on train items only.
  - Two defects were fixed: the gate passed values it could not rank (fail-open) and paired items by position.
  - Six policy items go to the founder.
- **The authorized immune successor (immune-8)** ([decision](evidence/greg-protected-evolution/2026-10-21-immune-8/DECISION.md)) is NOT_VIABLE: best simulated P(RETAIN) 0.000. No third immune pilot. The next step is `develop_repair`.
- **Coverage** ([record](collaboration/MIND-COVERAGE-2026-10-21.md)): section 31 has 9 conditions met, 8 partly met, 0 unmet.
- **Whole-machine trace** ([evidence](evidence/greg-whole-machine-trace/2026-10-21/README.md)): one consequence-inert mission ran all nine steps on the canonical path, with eight gaps recorded. Signed with a test key; VEPMC 0.
- **Natural family on GREG's own dependency graph** ([evidence](evidence/greg-natural-ops-2026-10-21/README.md)): the frozen verdict is LIFT 5-0. That lift is an input-size artefact, and the exact in-process method beats every GREG arm.
- **Data-exposure ledger across both lineages** ([ledger](evidence/greg-data-exposure-ledger.json)): 352 exposure records at this head.
- **Six new withheld genomes**, with development numbers only.
- **Founder decisions prepared:** [D1-D5](collaboration/FOUNDER-DECISIONS-2026-10-21.md).
- **Genome admission v5** ([evidence](evidence/greg-genome-admission/2026-10-21-v5/README.md)): 11 new families on fresh seeds 1400-1429. It was pre-registered at `2046b744`, frozen at `b8061a21` and run once on a quiet machine.
  - **DEFAULT (7):** MaxSAT, bin packing, Louvain communities, multistart L-BFGS-B, weighted-vote crowd, exact node cut, token-bucket admission.
  - **NICHE (2):** QP reconciliation, NLMS.
  - **SUPERSEDED:** the auction.
  - **REJECTED:** graph diffusion.
  - **Caveats:**
    - Differential evolution wins 15-7 against the DEFAULT multistart genome, not significant under the rule. The proposed routing for multimodal objectives is DE.
    - The node-cut genome's wins are bounds coverage only.
  - 44 of 58 genomes are admitted; none is attached.
- **`develop_repair` as a second P8 target:** a declared pilot was NOT_VIABLE because the trigger can never fire (the genome beats its no-repair baseline on 640 of 640). The measured deficit against the replanner is a mechanism, a hybrid of central plan and local fallback, not a configuration.
- **`develop_repair_hybrid` 1.0.0** ([evidence](evidence/greg-repair-hybrid/2026-10-21-exploratory/README.md)), registered and withheld. It composes the existing replanner with a local audit and a dormant local standby.
  - The declared exploratory emergence test (640 fresh items, seeds 4000-4639, one run) is **PARTIAL**: mean quality 0.9835 with 0 false claims, against the replanner's 0.7451 with 37.
  - It fails E2b, losing 37-126 to the replanner on stale controllers, as its declaration warned: the woken standby's message cost is already paid when the planner recovers.
  - Ablations show that the audit removes the false claims and that the fallback restores function.
  - A blocked repair mission resumed on the founder-attached hybrid through Capability Genesis, and its answer was verified (test key). This is exploratory evidence, not admission; admission v6 is drafted for seeds 1500-1529 and not frozen.
- **Genome admission v6** ([evidence](evidence/greg-genome-admission/2026-10-21-v6/README.md)): pre-registered at `b33fd678`, frozen at `f33cb2a9` and run once on seeds 1500-1529.
  - `develop_repair` 1.1.2 is NICHE_CAPABILITY and replicates v2: 7-23 against the replanner.
  - `develop_repair_hybrid` 1.0.0 is NICHE_CAPABILITY:
    - 23-7 against the local rules;
    - 7-7, with 16 ties, against the replanner, with 0 wrong answers against the replanner's 3;
    - not DEFAULT because it is about 92x slower than the replanner;
    - the stale-controller weakness replicates (3-7).
  - 45 of 59 genomes are admitted, every one with current-version evidence. None is attached.
- **Genome admission v7** ([evidence](evidence/greg-genome-admission/2026-10-21-v7/README.md)): nine new genomes from three parallel lanes, each built for an ABSENT coverage item. Pre-registered at `b1ee3f97`, frozen at `568c4b7b`, run once on seeds 1600-1629.
  - **DEFAULT (5):**
    - IDA\* (under a declared memory budget);
    - NEH-insertion beam search (beats warm-started CP-SAT 14-3; Iterated Greedy was not compared);
    - MAP-Elites (against a competitor weak by construction);
    - exact top-k betweenness (ties NetworkX, faster);
    - local-rule CA regeneration (0-2 against Z3 entailment, not significant, at 1/40 the latency).
  - **EXPERIMENTAL (2):**
    - the GA: 19-10 against hill climbing, not significant. It wins rugged NK 15-0 and loses deceptive traps 0-15 against CP-SAT.
    - MCTS: it ties flat Monte Carlo 28 of 30.
  - **SUPERSEDED (2):**
    - property-based search: Z3 finds every counterexample;
    - Hopfield recall: exact nearest neighbour is the ceiling.
  - 50 of 68 genomes are admitted. None is attached.
- **Genome admission v8** ([evidence](evidence/greg-genome-admission/2026-10-22-v8/README.md)): fifteen genomes from five parallel lanes, built for the ABSENT coverage items left after v7. Pre-registered at `28e29538`, frozen at `bc966a18`, run once on seeds 1700-1729.
  - **DEFAULT (8):**
    - role differentiation (beats a centralised MIS on rounds, 20-8);
    - novelty search (16-1 against MAP-Elites on deceptive mazes);
    - scenario fans (29-1 against Monte Carlo);
    - resolution proofs (Z3 decides as well, and the win is the declared value of a checkable proof);
    - MDL (ties BIC);
    - repeated games (ties simulation, faster);
    - Stackelberg commitment (ties HiGHS multiple LPs);
    - CUSUM (Shiryaev–Roberts is at least as good).
  - **NICHE (4):**
    - convex QP with a duality certificate: 30/30 and 20-0 against SciPy, but demoted because GREG's 64 KiB request limit refused a held-out instance (an integration defect, recorded);
    - Hamming correction (the Bayes decoder is better on noisy blocks);
    - the hyper-heuristic (no significant edge over random selection);
    - isotonic recalibration (superseded in substance, 2-28 against Platt scaling; the rule calls any win NICHE, a policy question).
  - **EXPERIMENTAL (2):** robust tube MPC; judgmental pooling (14-16 against the mean; dev did not replicate).
  - **SUPERSEDED:** Nash bargaining (SLSQP ties and is faster).
  - Merge review before the freeze: replaced a Stackelberg competitor weak by construction, and fixed a CUSUM benchmark that every detector failed.
  - 62 of 83 genomes are admitted. None is attached.
- **Request transport fix and genome admission v9** ([evidence](evidence/greg-genome-admission/2026-10-22-v9/README.md)).
  - **Fix (`93bf43a3`):** cognitive requests reach the solver and verifier on stdin instead of one argv string, which Linux caps at 128 KiB. The request ceiling is now 1 MiB.
  - **Admission v9:** pre-registered at `ce760f7a`, frozen at `11a8e318` and run once on seeds 1800-1829. It re-admits `convex_qp_dual` 1.0.0 as **DEFAULT** (13-1-16 against the baseline, 23-0-7 against trust-constr). The smoke passes on a 92.5 KB request, which the old limit refused.
  - 62 of 83 are admitted: 45 DEFAULT and 17 NICHE. None is attached.

## FABLE 5.1 OPUS MAXIMUS: one GREG, stacked on #178 — 2026-10-15

`INTENT-20261014-FABLE-OPUS-MAXIMUS` ([record](intent/INTENT-20261014-FABLE-OPUS-MAXIMUS.json), [verbatim prompt](intent/sources/FABLE-5-1-MASTER-BUILD-PROMPT-2026-10-14-source.md)): the greatest technically defensible realization of BODY + ORGANS + MIND on one canonical reviewable trunk, with no parallel GREG. Deliverables A-L are in [`opus-maximus/`](opus-maximus/). Convergence decision: [stack on #178](collaboration/deliberation-opus-maximus-converge-on-178-20261015.json) instead of running a second trunk.

- **Merged:** #178 (one-machine trunk, through `baf630d`: its second review and the Goal Gravity merge fixes), #175 `0ae4c94` (Goal Gravity bound to the body), the Track B Mind line at #181 `79c38f8` (with #179 and #180: #155 and #158 converged, the venture case on real organs) and #169 at `ebfc5f7` (confined egress by default; paid routes, `browser.session`, anchoring and the DALEOBANKS bridge behind the relay; MCP tools, read-only by construction or writing only what the founder approves, local or hosted, by login or plain token, with a credential a server reads from a file, and from the founder's words; device acceptance read from the body's relay journal; Foundry #52 repairing a copied source tree inside the worker envelope). #178's mission ordering and #175's persistent goals both run. #169's confined model child now keeps #178's model policy: only the founder's priced allowlist, never the provider-chosen `default`.
- **Defects found by the merged suites and fixed:** a Goal Gravity name collision (86 failing tests); a reconciliation that left an interrupted attempt's signed cap held, which stalled #178's whole-machine test, and booked it twice when "executed"; resilience dropping reconciled interruptions; three of #178's attack tests failing since the #178 merge; an organ exchange that kept the body's network on a confined body and whose appraisal the #169 merge broke; #178's independent verifier omitting the body's worker posture, which CI found on a host without bubblewrap.
- **An adversarial review of this branch, fixed:** 12 findings, each reproduced by a separate skeptic. A body killed between an uncertain run's record and its question no longer retries it blind on restart; supervision now covers only workers the envelope cannot confine at all; a workspace acceptance script runs inside the envelope; the confined organ exchange gets no network on the mission path; a receipt states supervision only when it happened; and a goal's ask for a paid move, or for an `mcp.act` call, is exactly the ask the mission would make, reach shown. Four were fixed by #178's second review (two of them carried here onto the confined model path); each of the rest has a test that fails without its fix.
- **A second adversarial review, of those fixes and merges, fixed:** 14 findings, 13 confirmed by a separate skeptic, 1 rejected. A kill in the uncertain window during Goal Gravity preparation, or behind another blocker, no longer leads to a blind retry; a crash between a reconciliation's record and its unblock no longer crash-loops; a founder's answer to a question from before #178's per-attempt salting is kept; provider binaries cannot be shadowed by a file in the worker's clone; a supervised Mac body's appraisal re-runs acceptance. A goal keeps its ask, its signed reject and its evidence when the mission spends, and says that a paid approve funds one run (#157), not a standing one; it no longer asks about a move its body cannot run. A Claude Code CLI failure is booked at what it cost, and its refusal is final, as the real CLI exits 1 on both (Seed Genome freeze-v10). Each has a test that fails without its fix.
- **A third adversarial review, fixed:** 12 findings, 9 confirmed by a separate skeptic. One paid approval now funds exactly one run, even a run that books $0; a paid ask the mission's spend has overtaken is withdrawn and asked again, so every open ask is one an approve can run; a goal no longer takes a used-up approve as the founder's answer. Claude Code's verbose output, unknown costs, built-in model fallback and error reasons are handled (Seed Genome freeze-v11).
- **A fourth adversarial review, of the Track B merge and #169's secret files, fixed:** 16 findings, 15 confirmed by a separate skeptic, 1 rejected. An attached construction now meets every compile route's rules: a high-consequence answer needs a formal model and stays conditional, and its call draws on the decision's thinking budget. The compile and chain routes carry the caller's grant window. A venture memo answers only the mission whose economics it was computed from. A mission held by a host outage resumes when the founder attaches a mechanism during the back-off. A credential handed to an MCP server as a file never reaches the ledger or a readable workspace, and an earlier action's output cannot choose it. Each has a test that fails without its fix.
- **A fifth adversarial review, of #169's `ebfc5f7` merge, fixed in two rounds:** 8 findings in #169's newest code (6 reproduced by a separate skeptic, 2 here, 1 refuted), then 9 in the fixes (4 reproduced by a skeptic, 5 confirmed here, 2 refuted, 3 accepted and recorded). What code under repair leaves behind (a FIFO, a socket, a link, a flood of sparse files, a rewritten report) can no longer hang, steer or stall Foundry #52's repair; its recorded evidence reproduces again and no record claims a CI re-run its row does not get. The device acceptance report counts only what its properties claim, names who made the connections, and survives a torn or damaged relay journal line; a page on another tenant or address is never labelled the service's own; the acceptance procedure points to the steps that produce its evidence, including installing Chromium in the Linux container. Each has a test that fails without its fix.
- **The Mind joined to the machine (Track B):** one tree now carries the converged Mind and the one-machine trunk, both whole-machine proofs pass on it with the real organs, and every mutation gate catches all its mutants. Track B's code binding keeps four operation verdicts (control, game, information, probabilistic) UNEVALUATED until they are re-admitted on the merged code; nothing was weakened to make them pass.
- **Founder decision made executable with a safe default:** worker confinement is the founder's `greg init` choice, `required` by default, `supervised` by opt-in.
- **Invention (field B):** proof-carrying standing reconciliation. A founder-signed mission may let GREG settle an interruption it can prove was consequence-inert (the script worker: no network, no credentials, no paid route, writes only inside a discarded clone), at most twice per action. Measured on a real in-flight SIGKILL: founder questions 1 to 0, duplicate consequences 0 (ten-step proof steps 7b and 7c).
- **Proof:** the ten-step proof and #178's one-mission test both pass on one tree with real DALEOBANKS and WealthMachine code.
- **Next-wave items 2 and 7 (2026-10-21):** #155's four operation verdicts were re-measured once on the merged solvers, pre-registered at `462bd98` on fresh seeds 2600-2629: control, game and information route DEFAULT again; probabilistic did not replicate and is EXPERIMENTAL, out of routing (`evidence/greg-genome-admission/2026-10-21-operations/`). A `decision.answered` row now moves a mission only as the record re-derived from a founder-signed DECISION at its own acceptance; a three-lens review of that change found 16 defects, all fixed with tests, among them a refused answer that could be revived by a backdated acceptance and an unsigned ask that could redirect the founder's approve (ADR-GOAL-GRAVITY-002).
- **Founder correction of 2026-10-19 (#190, `INTENT-20261019-UPWARD-ASCENT`, on #190's branch):** convergence is incomplete until every material overlap is recombined into a measured capability on GREG's path; the full vision is the acceptance floor. Applied here: #173's head `27a57cb` was inspected against this tree (about 100 commits not contained, not 20 as recorded; the convergence map is corrected). Seven defects it fixed exist on this branch's path and are ported first. The first capability dividend selected is a worker-independent acceptance check that recombines #173's evaluator freeze, #178's independent re-derivation and this branch's appraiser. Second is graduated worker confinement, with #173's Landlock grants as the floor under `supervised`. Each comes with a pre-declared threshold, floors and an ablation.
- **Open founder decisions:** VEPMC device and acceptance; organ pin upgrade (decided 2026-10-23, see the entry at the top; organ `main` merges open); the canonical Goal Gravity runtime; contacting brokers for the freight proof-of-delivery cell; merge of this branch.
- State: active. Reality: INTEGRATION and SANDBOX-WHOLE-MACHINE. VEPMC 0. No authority, spending, publication, contact or merge.

## Convergence of the two Mind lineages — 2026-10-14

`INTENT-20261014-MIND-LINEAGE-CONVERGENCE` ([record](intent/INTENT-20261014-MIND-LINEAGE-CONVERGENCE.json), [verbatim source](intent/sources/MIND-LINEAGE-CONVERGENCE-2026-10-14-source.md), [source-location manifest](collaboration/MIND-LINEAGE-SOURCE-MANIFEST-2026-10-14.json)): two sessions implemented the 2026-10-07 directive in parallel (PR #158 and PR #155) and froze different evaluations at eight identical paths. Neither session is the winner; both contribute to one GREG Mind.

- **Track A:** restore CI on #158 by retargeting it to a branch pinned at its original base `92bc6e3`. Both lineages are snapshotted at full SHAs. Every frozen artifact keeps its identity as (source commit, original path, sha256) and is never renamed or rewritten. CI on the pinned base is evidence for that lineage only.
- **Track B:** build the converged Mind now, in a dedicated draft PR on the latest verified #155 head. Inventory both lineages and disposition every conflict. Select canonical mechanisms by evidence. Keep unresolved alternatives isolated and withheld, with one cognition entry point, one authority system and one evolution controller. Run five review responsibilities and exactly two strengthening passes, and pre-register a fresh freeze for every integrated evaluation.
- **Coordination:** neither session overwrites, regenerates, renames or supersedes the other's frozen evidence, and new evaluations use uniquely identified paths.

State: active. Authority delta: none.

Track B execution, 2026-10-14 (draft PR from `claude/greg-mind-lineage-convergence` into #155's head; record:
[reconciliation](collaboration/MIND-LINEAGE-RECONCILIATION-2026-10-14.md), [map](collaboration/MIND-LINEAGE-RECONCILIATION-MAP-2026-10-14.json)):

- **Scope:** #155 `ef5f078` and #158 (through `202b932`, the F8 freeze) merged. Every one of the 185 changed files has a disposition, and
  the eight frozen-path collisions are archived byte-identical in both versions.
- **Canonical by evidence:** #158's evolution controller, frozen benchmark and Lawful Leverage Foundry; one
  Landlock grant path; one evidence index that both the compiler and the inventory read.
- **Retained, isolated:** #155's routing-genome evolution.
- **One intervention generator (2026-10-15):**
  - The Foundry is the one generator. It now holds the seven #155 operator classes it lacked under one
    evidentiary standard, and prior-only routes are labelled.
  - Accountability is four legal channels that need a human-established lawful basis. Consent gates only
    publication, and no channel executes.
  - Consent is purpose-bound and revocable.
  - #155's operator library is a pinned historical view.
- **Admission binding (2026-10-15):** positive operation verdicts are bound to the solver's dependency closure,
  not only its entry function.
- **Negative evidence now routes:** #155's held-out REJECTED and SUPERSEDED verdicts change compiler routing.
- **Replications across lineages** (corrected after the review of #179, H1): #155's P4 and F2b runs re-measured
  subsets of #158's instances, so they show reproducibility, not replication. F2 to F2R is the one replicated
  lift. Four P8 REJECTs; no replicated Layer 4 advantage.
- **F7 independently audited:** CONFIRMED (200 of 200), and parametric min-cost flow ties F7. Recommended:
  `flow_expansion_mcf` becomes canonical for capacity expansion once admitted at its exact version.
- **Horizon added:** `immune_function`.
- **Release blocker:** third-party data rights (SNDlib, M4, fpp3, and the F8 NYC TLC/FiveThirtyEight Uber
  extract) are uncleared in a public repository.

Authority delta: none.

Track B update, 2026-10-15 (founder review of #179 and the independent review; record sections 5, 8, 9, 12 and 17):
- **Foundry:** #155's seven operator classes run through the canonical Foundry. They carry surface-instance
  identity and purpose-bound, revocable consent. Accountability is split into four legal channels that end in a
  legal-review request and never unlock execution.
- **Code binding:** positive operation admission binds the code closure it measured.
- **Re-merge:** #158 is merged at `f8e8fd2`. Its pre-registered admission v3 makes `flow_expansion_mcf` the routed
  default for budgeted capacity expansion; attaching it is the founder's.
- **Release guard:** uncleared third-party data cannot ship in a release (CI check). The distribution question
  stays with the founder and counsel.

Authority delta: none.

Track B update, 2026-10-16 (record sections 1, 3, 7 and 8): #158 is merged at `10fdbab`.
- **Verifier:** #158's independent Z3 certificates for OPTIMAL, FEASIBLE, INFEASIBLE and UNSAT claims.
- **F7 with the genome:** a declared re-use of v4's exposed items. `flow_expansion_mcf` MATCHES the composition on
  200 of 200 at about a quarter of the latency, and F7's lift is **NO_LIFT** once the genome is a constituent.
  v4's frozen verdict is unchanged.
- **Admission v4:** `grid_dijkstra` 1.1.0 is DEFAULT_FOR_GEOMETRY, and the flow genomes replicate.
- **P8 cycle 5:** REJECTED. Protected evolution has still never kept an improvement.
- **Release guard:** 26 uncleared paths, including F7 v6's SNDlib-derived files.
- **Operation re-admission (review M17):** a live, pre-registered harness re-admits #155's operation families on
  this tree. Its first run, on fresh seeds 5001-5040, replicates 14 of 17 rows. `graph` falls to EXPERIMENTAL
  (4-0, too few discordant items), `robust_pattern` rises to DEFAULT, and `collective` reads EXPERIMENTAL, as its
  erratum said (record section 18).

Track B update, 2026-10-21 (round-2 re-verification by the #158 session; record section 19):
- **Crowd verifier:** it re-runs EM, so a claimed non-convergence no longer skips the check. This was a high finding.
- **One status on every surface:** organ labels, recipe lifts and #155's lineage verdicts are notes, not admissions.
  41 labels are rule-admitted.
- **Release check:** it blocks by digest, path suffix or data marker, inside nested archives.
- **Closure binding:** it follows scopes, guarded definitions, star imports and constant dynamic imports. Code
  it cannot follow binds nothing positive. Recipes bind at the measured tree and stop at `cortex.reason`.
- **Merge:** #158 is merged at `463a9d0`.

Authority delta: none.

Track B update, 2026-10-21 (round-3 re-verification; record sections 1 and 20):
- **Recipe binding:** recipe verdicts also bind their stage genomes.
- **Runtime dispatch:** a disagreeing runtime dispatch binds nothing.
- **Release check:** it blocks recompressed and reformatted copies. Re-encoded copies are a stated limit.
- **Crowd verifier:** abstentions must match the declared threshold.
- **Seeds:** operation admission seeds 5001-5040 are spent.
- **Merge:** #158 is merged at `050c1b2`. P8 cycle 6 RETAINed on held-out data, and random restart is at least as
  good. It is PROPOSED_NOT_APPLIED, and who adopts it is a live founder decision.

Track B update, 2026-10-21 (composition and metacognition lane; record section 22):
- **Converged recipe lifts** ([evidence](evidence/greg-composition-lift/2026-10-21-converged/README.md)): P6
  converged v1 was pre-registered, frozen and run once on fresh seeds, against the strongest single available.
  **Converged VPL is 2 of 4 synthetic families.**
  - F2R lifts 16-2; F4 lifts 15-0.
  - F1 is NO_LIFT: 35-0 on correctness, but one false answer that the conservative single does not make.
  - F3 is NO_LIFT: tied by `flow_expansion_mcf` at about a fifth of the latency.
  - The natural-family recipes stay UNEVALUATED on the converged code.
- **Compiler:**
  - an organ answering a relaxation of a routed recipe is rejected (found by the development check, fixed
    before the freeze);
  - settled outcomes alone can change the choice between eligible fits (Fisher exact test, Holm, n >= 10);
  - a formed mechanism's compile receipt carries its competence basis and dissent.

Authority delta: none.

## Whole-machine convergence and the Founder's First Mission — 2026-10-14

The founder's OPUS MAXIMUS continuation directive is implemented on draft branch `claude/greg-whole-machine-convergence`; see `collaboration/WHOLE-MACHINE-CONVERGENCE-2026-10-14.md`. The section 16 handoff (nine items, with a recorded mission trace) is `collaboration/WHOLE-MACHINE-HANDOFF-2026-10-14.md`.

- The Mind line is the canonical base. #160 and #132 are joined, and #132's Foundry modules keep the Mind-line modules as registered alternates behind one dispatch rule.
- #159 is ported.
- #157's worker isolation is extracted (increment 4):
  - workers and their acceptance tests run in bubblewrap envelopes or not at all;
  - GREG's git never runs a worker-planted hook or filter;
  - an interrupted worker is reconciled as UNCERTAIN.
- The console signs only for its owner (increment 5). Before, any local process, including a worker with provider networking, could get a MISSION signed with the founder's key; this was reproduced, and is now refused.
- The executable Founder's First Mission and the five-question Mission Control are on the one mission path. `greg rehearse` runs both without credentials.
- Increment 3 adds:
  - discovery by intention;
  - an opt-in confined `http.get` behind the #26 relay;
  - money kept in separate columns;
  - recovery evidence on the Proof view;
  - a section 13 attack map covering all 14 classes, with three new integrated attacks: disagreeing intelligences, network loss and interrupted construction.
- Increments 6 and 7 bring the last three section 13 classes onto signed missions: stale community state, a profitable action that violates participant rights, and a local gain that damages the whole. Two were real holes on the mission path:
  - an offer with pressured copy for unlicensed content could be published straight onto Foundry #54, around the company's editorial constitution; it is now refused at publication and at sale;
  - the engine oscillated forever between a strategy that broke safety and one that broke throughput; it now blames the one that broke a passing check and asks the founder to decide the trade-off.
- Increment 8 puts the browser (`browser.render`) and coding workers behind the #26 relay. They run in a bubblewrap network namespace whose only way out is a door to the relay, and every request is allowlisted and journaled. #26 stays PARTIAL: `browser.session`, the paid model routes, anchoring and the DALEOBANKS bridge remain outside, and confinement is opt-in.
- Increment 10 puts the Playwright `browser.session` behind the same relay. On the way it found and closed two leaks in the unconfined browser: a page's WebSocket bypassed the allowlist, and the allowlist ignored ports. #26 stays PARTIAL: the paid model routes, anchoring and the DALEOBANKS bridge remain outside, and confinement is opt-in.
- Increment 11 puts the paid model routes behind the same relay. On a confined body, the Anthropic and OpenAI SDKs, which hold the founder's key, run in a network namespace that reaches only their provider. The Claude Code CLI runs behind its own door. The builder and the console both receive the relay. #26 stays PARTIAL: anchoring and the DALEOBANKS bridge remain outside, and confinement is opt-in.
- Increment 12 puts anchoring and the DALEOBANKS bridge behind the relay. On a confined body every mission-path egress now crosses the relay or has none. DALEOBANKS's real organ runs inside the namespace. #26 stays PARTIAL only because confinement is opt-in.
- Increment 13 corrects increment 12. The venture organs, the appraiser's re-run of them and the Claude Code Genesis builder were still outside the relay; they are now confined. The founder's installer creates the body confined whenever the machine can, and says so. On the way, `git.inspect` was found running repository-configured code, and that is now prevented. #26 stays PARTIAL until this is observed on the founder's Chromebook.
- Increment 14 ports #168's third runbook defect: a person's step now says which file and folder GREG reads, and stays on every surface after an answer until the work is seen.
- Increment 15 tests two recovery paths end to end that had been tested only in parts. A body killed in the middle of a self-repair, including one killed during a ledger append, finishes the repair exactly once after restart. When one model vendor is down, Genesis builds through the other over the real SDKs, the original mission closes, and the outage survives a restart as routing evidence. No code changed; each test fails against a mutant of the recovery it covers.
- Increment 16 closes a path to the founder's authority root. Every confined program (browser, model SDK child, Claude Code CLI, DALEOBANKS, venture organs) could read the founder's signing key and the body's secrets and ledger, and the Claude Code routes had the founder's home writable. The one namespace now hides the founder's home, every body home and the repository's `.git`, showing again only GREG's runtime and the paths each caller names; the CLI gets a private home holding only its login. Seed Genome freeze-v7 records the `greg/models.py` change; the evaluation is unchanged.
- Increment 17 gives GREG the MCP ecosystem's tools without rebuilding them: a signed mission can call a tool on any stdio MCP server the founder installs (`mcp.call`). The server runs in the hardened namespace with no network and a read-only filesystem, so the call cannot change anything whatever the server claims; the official time and git servers ran through it, and the git server's commit was refused by the operating system. Servers that need the network, consequential tools and remote transport remain open (#28 PARTIAL).
- Increment 18 puts those tools within the founder's words: GREG finds the MCP servers installed under its read roots, lists their tools confined, and turns "use the git server to show the status of ~/src/kernel" into one read-only mission, asking instead of guessing whatever the words do not settle. Mission Control shows the installed servers, their tools and the latest answers as untrusted data with receipts.
- Increment 19 extends those tools to npm-installed servers (the official filesystem server read through a signed mission and could not write), lets the founder give a server launch arguments in `greg-mcp.json`, and fixes a gateway defect that recorded a server's own structured answer as nothing.
- Increment 20 lets those tools change things, inside exactly what the founder approves. A tool that writes or reaches the network runs as `mcp.act` (class external_contact): the mission stops for the founder's decision, the request shows the folders it may write, the hosts it may reach through the relay and the credential handles it receives, and only that scope runs. Everything else stays read-only, every other host is refused, and a credential's value never enters GREG's records. The official filesystem server wrote an approved folder and was refused elsewhere by the operating system. Remote transport, other credential forms and words-to-act proposals remain open (#28 PARTIAL).
- Increment 21 puts those changes within the founder's words: *Use the notes server to append "ship the wedge" to ~/src/notes/plan.md* becomes one `mcp.act` proposal that may write that file's folder and nothing else, with no network and no credentials. It waits for the founder's approval, which Mission Control now shows with its exact scope, and closes only when GREG reads the file itself and finds the text. On the way, the signing summary stopped reading unknown capabilities as read-only.
- Increment 22 reaches remote MCP servers by URL, the way most hosted services now offer their tools. Every remote call is an approved `mcp.act`, since GREG cannot make a call on someone else's machine read-only. The decision shows the server, its one host and the credential handle. GREG's own client runs confined, its only way out a relay allowing that host, with the token by handle in its environment and in nothing GREG records. OAuth flows, discovery and proposals from words remain open (#28 PARTIAL).
- Increment 23 lets the founder log GREG in to a hosted MCP server with OAuth (`greg mcp login`): the official SDK runs the flow, the founder approves at the service, and the tokens stay in the body's secret broker. Approved calls use the login; an expired one renews once inside the approved call, only at the server's host or a host the approval names, and the rotated tokens never enter GREG's records. Not yet tried against a real hosted service.
- Increment 24 shows the founder, in Mission Control's Authority view, every credential GREG holds: by name and kind, for a login the server, renewal host and expiry, and how to revoke each. Values never leave the secret broker.
- Increment 25 tests a model vendor that is slow, cuts its answer off or refuses the key, over real HTTP through the real SDKs: the mission closes through the vendor that answers each time. It found that a refused key was retried like an outage forever; a refused key is now benched until the founder stores a new one, and Mission Control says which key and what to run.
- Increment 26 shows, in Mission Control, the hosted servers GREG is logged in to and the tools each listed at login, as the server's claim, without contacting it again.
- Increment 27 extends the refused-key bench to the console: drafting a mission no longer sends a refused key to its vendor, and when no other model is available the console says which key to replace.
- Increment 28 lets the founder register a hosted MCP server that uses a plain token (`greg mcp token`): GREG keeps the token only if the server accepts it, records the server and the tools it listed, shows them in Mission Control, and sends the token only inside an approved call to that server.
- Increment 29 puts those hosted servers within the founder's words: *Use the notes service to add "ship the wedge", then check https://…/board* becomes one approved `mcp.act` by URL, its tool chosen from the list the service gave at login so drafting contacts nobody, and the mission closes only when GREG renders the named page and finds the text. Whatever the words do not settle is asked.
- Increment 30 serves MCP servers that read their credential from a file (a service-account key, a kubeconfig): `greg secret set mcp:<name> --from-file <path>` keeps the whole file in the secret broker, and an approved `mcp.act` naming it in `secret_files` gives the server a private 0600 file, shown read-only, at the path in the named variable, removed when the call ends. The approval names it as a file.
- State: active. Reality: integration-tested and browser-tested locally. VEPMC remains 0. No authority, spending, publication or merge.

## CONTRADICTION-0002 Option A: historical reproducibility apart from live constitutional integrity — ruling 2026-08-23, implemented 2026-10-14

Source, preserved verbatim:
[FOUNDER-RULING-2026-08-23](deliberations/FOUNDER-RULING-2026-08-23-infinite-goal-chase.md)
(byte-identical to the file on #87; its header and "How this ruling is
discharged" table were written by the #87 agent and describe #87's tree). The
file is a record of what the founder wrote. It authenticates nothing and
carries no authority beyond its own text; in particular it is not an
authorization for any artifact change, which only a signature by an enrolled
founder key can be.

| Required field | INTENT-CONTRADICTION-0002-A |
| --- | --- |
| statement | "Separate historical reproducibility from live constitutional integrity. Freeze byte-identical historical copies of the twelve continuity artifacts used by the sealed experiment. ... Create a separate live constitutional-integrity mechanism whose purpose is to detect unauthorized changes to constitutional/authority artifacts. Do not use the historical experiment as the live tripwire. ... Do not update an old historical hash merely to make current implementation pass." |
| source_refs | FOUNDER-RULING-2026-08-23 (file above); #87 a70905c (first implementation, path-string authorization); verifier verdict on #87 (re-home governance/integrity; Ed25519 founder envelope, never a path or caller string) |
| owner | Alfonso (ratification); Kernel evolution owners (history); Kernel governance owners (live check) |
| state | active |
| binding_scope | Package 3 continuity readings and the live constitutional-integrity check; no grant, policy or Gate behaviour |
| constitutional_constraints | Only a signature by Alfonso's enrolled founder key authenticates him; no pinned historical hash is re-measured; the two mechanisms do not import each other |
| success_evidence | `evolution/repair/continuity/` reproduces FROZEN, SR-001 and SR-002 and the sealed Package 3 evidence record; `python -m governance.integrity --check` names every unauthorized artifact; tests `test_repair_continuity_history.py`, `test_governance_integrity.py` |
| failure_evidence | A tampered frozen copy, a forged/replayed/unsigned authorization, an unenrolled signer, a changed committed genesis or a removed/reordered committed record must fail (tested); no founder key enrolled yet, so nothing can be authorized today |
| dependencies | Alfonso enrolls his own public key (his commit) before any authorization exists |
| conflicts | #87's `Amendment.authorization` path string is superseded by signed envelopes; #87's per-path frozen copies would trip `check_authority_singleton`, so the store is content-addressed |
| next_review_trigger | First founder enrollment, or the first founder-signed `INTEGRITY_AUTHORIZE` |
| supersedes | The SR-002 subject binding as live tripwire (the 13 SR002 dependent tests now read history) |
| superseded_by | None |
| implementation_refs | `evolution/repair/continuity/`, `evolution/repair/subjects.py`, `evolution/repair/harness.py`, `governance/integrity/`, Canonical CI job 3 |

## Frontier leap, continued: portfolio under a spending cap — 2026-10-21

Same intent. "Spend at most N." now turns a portfolio question into `selection.budgeted`. GREG solves it with a branch-and-bound whose every node is a `selection.closure` problem answered by the qualified max-flow engine. It accepts the plan only when its own check of the whole search tree, from the original items, proves that no plan within the cap earns more.

Matched baseline: trimming the uncapped plan is wrong in 11.9% of 2,000 capped shared-cost portfolios and leaves 8.6% of the profit behind.

Evidence: [README](evidence/greg-budgeted-selection/2026-10-21/README.md). State: active. Authority delta: none. VEPMC: 0.

## Frontier leap, continued: portfolio questions in plain words — 2026-10-21

Same intent, read against `INTENT-20261019-UPWARD-ASCENT`. The founder types which offers earn what, which cost what, and which need which. GREG reads it without a model, constructs `selection.closure` over a max-flow engine the founder attaches, and answers with what to take, the profit, and what was left out and why, under its own certificate.

Matched baseline: on shared-fixed-cost portfolios a standalone greedy rule is wrong in 38% of 2,000 instances and leaves 38.6% of the profit behind. On uniform random portfolios it is wrong in 1.6%.

Evidence: [README](evidence/greg-portfolio-words/2026-10-21/README.md). State: active. Authority delta: none. VEPMC: 0.

## Frontier leap, continued: a goal asks for the capability its plan requires — 2026-10-15

Same intent. A founder-signed goal whose plan node requires `<function>@function` that GREG lacks now asks Capability Genesis to form it under the goal's signed mission. This is formation only: each verified result waits for your signed attach, no builder is commissioned, no mission is blocked, and the goal's deficit closes when an attached implementation serves it.

Evidence: [README](evidence/greg-goal-formation/2026-10-15/README.md). State: active. Authority delta: none. VEPMC: 0.

## Frontier leap, continued: portfolio decisions and capability perception — 2026-10-15

Same intent (`INTENT-20261013-FRONTIER-LEAP-RECOMBINE`; the directive was re-issued verbatim and its founder instructions A–D stay preserved in that record). Built:

- `selection.closure`: which projects or offers to take when some require others, constructed over the max-flow engine with a funding proof checked from the original items.
- Goal Gravity now perceives capability formation, recovery, attachment and quarantine as observations about the missions waiting on them, so a blocked goal wakes when what it waits on changes. Timing only.

Evidence: [README](evidence/greg-selection/2026-10-15/README.md). State: active. Authority delta: none. VEPMC: 0.

## Frontier leap: Capability Genesis constructs new capabilities (RECOMBINE) — 2026-10-13

`INTENT-20261013-FRONTIER-LEAP-RECOMBINE` ([record](intent/INTENT-20261013-FRONTIER-LEAP-RECOMBINE.json), [full directive, verbatim](intent/sources/FRONTIER-LEAP-DIRECTIVE-2026-10-13-source.md)): stop treating Capability Genesis as part replacement and make it construct new, integrated capabilities from harvested mechanisms, on GREG's one path. Founder instructions A-D are preserved verbatim in the record's `founder_quotations` and in the source file. They are read under INTENT-0030. "Meniscus", "impermeable shield" and "systemic dominance" keep the 2026-10-07 executable interpretation. They authorize no crossing of legal boundaries, no coercion and no immunity from shutdown.

What was built:

- **Construction route.** `greg/recombine.py` adds certificate-carrying reductions. `greg/genesis.py` gains a `constructed` rung between `verified_detached` and `builder`. A function with no catalog entry is reduced onto an engine GREG already qualifies (maximum flow, LP). The engine is itself acquired by the same ladder when missing. Every answer is re-proved in the original problem's terms.
- **First functions.** `assignment.staffing` (with a Hall/Koenig bottleneck), `assignment.matching` (chained through staffing) and `project.crash` (time-cost LP; an impossible deadline is proved without any engine).
- **Mechanism Cards.** Every reduction carries a card with all twenty directive fields, searchable and deduplicated by content digest.
- **Authority.** Constructions are read-only. They attach only by founder command or a signed read-only `auto_attach`. They stop when their engine is detached or quarantined, are quarantined when their reduction code changes, and are re-formed over a different engine when the engine lies.

Reconciliation: no third mission engine, router or genesis was created. Kernel PR #129's `egregore/genesis.py` is the standing-cognition-slot loop (proposer/evaluator parts). `greg/genesis.py` stays the canonical mission-capability genesis. Convergence of the two is recorded as open work, and nothing was deleted.

Evidence: [README](evidence/greg-recombine/2026-10-13/README.md). State: active. Authority delta: none. VEPMC: 0.

Progress 2026-10-14 ([evidence](evidence/greg-mind-constructs/2026-10-14/README.md)). The Mind and Capability Genesis now close one loop on the canonical path:

1. The Competency Compiler recognizes a problem whose inputs fit a reduction. Its deficit names that constructible function, not an unbuildable geometry label.
2. Genesis constructs it under the mission's signed scope.
3. The Mind answers with the construction's certificate.
4. The independent appraiser re-derives the answer through a read-only restore and returns VERIFIED.
5. A construction that faults while the Mind uses it is repaired by the same two-strike mechanism.

Unsigned missions ask first for the engine, then for the construction, and never self-attach. Authority delta: none.

Progress 2026-10-14, second entry ([evidence](evidence/greg-recovery/2026-10-14/README.md), [card](mechanisms/MC-0002-governed-half-open-recovery.md)): governed recovery. A real REA run on opossum 10.0.0 (Apache-2.0) extracted the circuit breaker's half-open re-admission. It was mutated so that:

- the probe runs in the sandbox on a fresh frozen-oracle seed;
- success restores eligibility, never authority;
- the wait backs off exponentially, and flapping stops recovery;
- engines are probed before the constructions built on them.

A function lost to transient faults now returns, and its mission closes without founder attention. The same work fixed a pre-existing crash, reproduced on #173: a de-duplicated re-escalation, then a repeated qualification fact, crashed every later tick. Authority delta: none.

## Full Polyintelligence Mind + lawful asymmetric advantage continuation — 2026-10-07

`INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION` ([record](intent/INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION.json), [verbatim source](intent/sources/POLYINTELLIGENCE-MIND-CONTINUATION-DIRECTIVE-2026-10-07-source.md)): continue past P4/P6/P8 to the complete currently achievable five-layer Mind on GREG's one cognition path. Order: falsify or close the P6 lift gate (including one natural family), one pre-registered decisive P4 retest (demote if the static policy wins), P8 protected evolution against a sealed evaluator, an executable IntelligenceGenome library with an admission rule across Layers 1-4, the Layer 5 Competency Compiler, a lawful intervention search above the repertoire, and the Goal Gravity connection. Four earlier founder quotations are preserved verbatim with an executable interpretation: "meniscus" is the frontier of the verified envelope with explicit margins, "impermeable shield" is layered prevention and recovery (never claimed literally), "systemic dominance" is superior lawful capability and never control over people, deterrence is lawful only, victim protection is first-class, and collateral harm stays a vector. High consequence raises proof and authority requirements; it does not route the world to SMT. State: active. Authority delta: none. VEPMC: 0.

Progress 2026-10-08 (measured, frozen, negative results kept):

- **P6 v2:** VPL is 3 of 4. F2R, F3 and F4 lift; the natural M4 family F5 does not (8.5% cheaper, not significant).
- **P4 decisive retest:** REGRESSION, 160 vs 162. All discordant items used identical orders, so this is timing noise. Conditional routing is demoted and the shadow default stays.
- **P8 cycle 1:** REJECT. The overfit was caught under a sealed evaluator.
- **Built:**
  - Competency Compiler with 15 typed mental-model operators, including executable sensitivity analysis;
  - frozen-evidence routing;
  - Lawful Leverage Foundry, hardened after an adversarial review;
  - Goal Gravity (`greg gravity`).
- **Backcast GPS:** nine frontier backcasts added.

Progress 2026-10-13 (measured, frozen, negative results kept):

- **P8 cycle 2** (negative-selection detector): REJECT on a genuine scarce-sample fragility.
- **Genome admission** ([evidence](evidence/greg-genome-admission/2026-10-13-v1/README.md)): 31 executable genomes across L1-L4 on held-out seeds, pre-registered at `496c85b`:
  - 12 DEFAULT_FOR_GEOMETRY, 8 NICHE_CAPABILITY, 6 SUPERSEDED, 3 COMPOSITION_ONLY, 2 EXPERIMENTAL, 0 REJECTED;
  - none attached; attaching any is the founder's decision.
- **Admitted:** 20 of the 31 (DEFAULT or NICHE): L1 5, L2 2, L3 11, L4 2. SUPERSEDED genomes are excluded from routing, not kept as fallbacks; `collective_market` is SUPERSEDED only against an oracle competitor, which leaves the market geometry unroutable (see the evidence erratum).
- **Verifiers hardened before the freeze:** a mutation audit (an uncommitted five-seed sweep) found over 1,000 accepted or crashing corruptions of valid answers. After the fix no non-equivalent mutant survives on dev seeds 0-9; equivalent ones (raised non-binding bounds) are accepted by design.
- **Second Foundry/Gravity/resilience review, by the building agent:** 9 defects plus a cortex abstention crash, fixed with regression tests. They included a consent gap, a hidden-bottleneck map, a lookalike legal operator, paused-mission authority and stale asks.
- **Independent review (2026-10-13):** five lenses by separate agents found verifier, Gravity, Foundry, resilience, community-evidence and cortex defects, each reproduced and fixed with a regression test that fails on the old code (`4d99fb0`, `ed0f00b`, `9a799ed`). The evidence lens confirmed the admission evidence and corrected its prose (erratum in the admission README).
- **Next gate:** P6 v3, VPL re-measured with the admitted genomes on a new natural family.

Progress 2026-10-14 (measured, frozen, negative results kept):

- **P6 v3** ([evidence](evidence/greg-composition-lift/2026-10-14-v3/README.md)): the natural call-centre family F6 (real bank arrivals, forecast quantile -> Erlang C staffing) **lifts**: 74-16 against the best constituent, 6.1% cheaper, no infeasible plan. Natural families are now 1 of 2.
  - The lift is composition, not routing: the router chose the static recipe on all 90 days.
  - Composition does not beat the weekly-mean practitioner pipeline on day count (40-50).
- **Genome admission v2** ([evidence](evidence/greg-genome-admission/2026-10-14-v2/README.md)): ten families re-measured on fresh seeds 1100-1129. Six replicated.
  - `basal_pid` is SUPERSEDED (0-30); `develop_constraint_release` fell to NICHE (5-15 against random restart).
  - New: `basal_bayes_filter` is DEFAULT (13-1-2 under high noise).
  - `forecast_quantile`'s held-out series had been used by P8. The seeds were fresh, the data were not; this is recorded in an erratum, and the harness now checks data identity.
  - 21 of 32 genomes are admitted. None is attached.
- **Independent review of `bb65d6f..8e37cd8`:** 15 reproduced defects, all fixed with regression tests.
  - High severity: any signed founder answer to any request decided a human-judgment question. Human judgment is now bound to its own recorded question, and only the founder's signed answer to that request decides.
  - The "miscalibrated" forecast claim was a multiple-testing artefact; it is corrected.
- **Product delta:** forecast calibration is live through a founder-signed `greg realize`, and `greg cognition calibration` reports it.
- **After the directive audit:**
  - The Competency Compiler now reaches the cortex organs (Z3, CP-SAT, Fermi, evidence/causal, semantic).
  - It records its attach and human-judgment asks on the body, once each.
  - It demotes methods whose settled outcomes on the body are significantly poor.
  - It reports the geometry a request's inputs imply.
- **P8 cycle 3** ([evidence](evidence/greg-protected-evolution/2026-10-14/README.md)) targeted the constraint-release search policy. It was **REJECTED** at the adversarial gate: the candidate was 20% better on training, but 6.3% worse when validation was cut to four cases. Protected evolution has still never kept an improvement.
- **VPL accounting** ([post hoc](evidence/greg-composition-lift/2026-10-14-accounting/README.md)):
  - every lift costs latency (1.5-5.2x);
  - routing adds nothing within a family;
  - no practitioner pipeline was beaten where one was measured.
- **P6 v4** ([evidence](evidence/greg-composition-lift/2026-10-14-v4/README.md)): F7 was pre-registered with every section-16 element (`888003c`, checked by `validate_preregistration`) and frozen at `14ec7a6`. It is surge capacity leasing on 20 held-out SNDlib backbones with real topologies, lengths, demand pairs and ECMP loads.
  - **It lifts:** the composition was optimal on 200 of 200 items against greedy's 108 (92-0), at 5.3x the latency inside the declared 10x. It also beat the shortest-path-upgrade practitioner 130-0, the first practitioner pipeline beaten in any run.
  - **It was tied:** parametric min-cost flow, the truth algorithm, ties it on every item. The lift is over GREG's repertoire, not over an OR practitioner. Routed, static and compiled answers were identical.
  - **The residual capability is built:** `flow_expansion_mcf`, one certified intelligence, registered and withheld.
  - Natural families are now 2 of 3. F7's truth is a computed optimum, not a realised outcome.
- **Layer 5 defects fixed, each with a regression test that fails on the old code:**
  - the compiler answered a capacity-expansion request with `max_flow`, which ignores the budget; relaxations are now rejected;
  - compiled requests never settled; they now credit the executed method through its own receipt, and outcome links are projected;
  - a Goal Gravity turn recorded an ask on the body; it now writes nothing and reports measured trust.
- **Next gate:**
  - one pre-registered admission v3 on fresh seeds 1200-1229 for every new or version-bumped genome (promoted competitors, Layer 3 packs A-C, `flow_expansion_mcf`, the Layer 2 native regimes, `basal_bayes_filter` 1.0.1, `develop_constraint_release` 1.2.0);
  - a composition family that uses an admitted Layer 1 or Layer 2 genome;
  - new data before any further forecast admission.

Progress 2026-10-15 (measured, frozen, negative results kept):

- **P6 v5** ([evidence](evidence/greg-composition-lift/2026-10-14-v5/README.md)): the natural family F8 (real NYC 2015 pickups; basal Kalman tracker -> Erlang C staffing) **lifts** over the best single intelligence, 8.6% cheaper (1589-204 items, 120-2 days). The EWMA-ratio-plus-quantile ablation is cheaper still: it costs 4.5% less than routed (routed costs 4.7% more than it), and all of that comes from the tracker's fallbacks. Natural families are now 3 of 4. The data's redistribution terms are unverified (release blocker).
- **Genome admission v3** ([evidence](evidence/greg-genome-admission/2026-10-15-v3/README.md)), pre-registered at `878f76c` on fresh seeds 1200-1229, measured 24 families: 15 new, 5 version-bumped and the 4 Layer 2 genomes on their native regimes.
  - `flow_expansion_mcf` is DEFAULT against the F7 composition twin, with equal quality on all 30 instances at about one seventh of the latency. Both were measured on 30 synthetic capacity-expansion instances (seeds 1200-1229); the genome was not run on F7's SNDlib items. On that capacity-expansion geometry the single exact method is canonical, which answers the founder's audit question at an exact version.
  - Eight DEFAULT verdicts tie their competitor on all 30 instances and rest on being no slower than 1.25x its median latency. Two of them (`game_lp_dual`, `knapsack_bnb`) also tie their baseline and pass only by being at least 1.25x cheaper than it.
  - `bootstrap_ci` is REJECTED.
  - Grid shortest paths have no admitted genome: `grid_dijkstra` is EXPERIMENTAL at 1.22x its baseline's speed, short of 1.25x.
  - `basal_bayes_filter` fell to NICHE and `develop_constraint_release` rose to DEFAULT. Both crossed a rule boundary, recorded as a replication finding.
  - All 47 genomes carry current-version evidence: 34 admitted, none attached.
- **P8 integrity and cycle 4** ([evidence](evidence/greg-protected-evolution/2026-10-15-cr-4/README.md)):
  - A cycle that writes a record now has to match a committed freeze. The freeze holds the trusted-code digests, the rule, the settings, the split and both seals.
  - The parent checks the method each sandbox imported, and confinement is scoped.
  - Cycle 4 is the first cycle run under the freeze. It targeted the constraint-release search policy on a fresh split and was REJECTED at the held-out gate.
    - On train the candidate was 23.7% better and improved on both stress sets.
    - On held-out it lost 26-37 (p = 0.94) and its mean loss was 46% worse.
    - Random restart had lower loss than the incumbent on 53% of train items, beat the candidate 46-22 on held-out and had the lowest held-out mean loss (0.0045 against 0.0062 and 0.0091). The record compares it with no other searched configuration.
    - The search did try restart: its three configurations with `p_restart` above 0 (0.064, 0.156 and 0.339) were all worse than the incumbent on train.
  - Protected evolution has still never kept an improvement: 4 cycles, 4 REJECTs.
- **Fix rounds merged after independent verification:** packs B and C, Capability Genesis (five rounds) and the solo compiler work (three rounds).
- **Independent review of PR #179** posted, plus a review of its closure binding. A family re-pointed to another solver keeps a positive verdict after an index rebuild (confirmed).
- **Records corrected after the independent evidence review:** the F8 percentage base, the scope of the `flow_expansion_mcf` result, the explanation of the eight DEFAULT verdicts and the random-restart comparison above. The v3 admission, P8 cycle-4 and P6 v5 READMEs carry errata that quote the original wording. `scripts/mind_status.py` now reports a status change across a declared regime change (`collective_quorum`, `collective_immune`) apart from a rule-boundary flip, and the admission harness records `source_dirty` for future runs.
- **Independent review of this day's work** (five lenses, each finding re-run by a second agent): 33 findings plus 9 the verifiers added, all confirmed or partly confirmed. Each was fixed with a regression test that fails on the old code and independently re-checked:
  - **P8 integrity v2.** The freeze now covers the full import closure, and executed code is checked in both processes. A recorded cycle runs only through a clean room (a fresh checkout, a source-only entry, no bytecode, git hooks off). Held-out data is looked at once, and only by a recorded run. This took four rounds of independent checking. It defends a record against a dirty or stale tree, not against whoever controls the machine.
  - **Competency Compiler and Genesis:** a wrapped request now gets one ask, recipe demotion is scoped to the request, and demotion labels are truthful.
  - **Optimisation verifier:** OPTIMAL, INFEASIBLE and UNSAT claims are now certified independently by Z3 ("proven" only when certified). Objectives are compared exactly at large magnitudes, and parallel edges are refused in capacity expansion.
  - **Records:** errata quote the original wording.
- **Blocked by the environment:** fresh NYC TLC data for F8's next evaluation. The network policy refuses `data.cityofnewyork.us` and the TLC CDN.

Progress 2026-10-16 (measured, frozen, negative results kept):

- **F7 with `flow_expansion_mcf`** ([evidence](evidence/greg-composition-lift/2026-10-16-f7-mcf/README.md)): **MATCH.**
  - It is a declared re-use of v4's 200 held-out SNDlib items, which had been looked at twice before.
  - The admitted single genome, through `cortex.reason`, is optimal on 200/200, as is the composition, at 0.26x its median latency.
  - The independent rescoring (SciPy max flow plus a HiGHS MILP, no code shared) agrees on every item, and the compiler selected the genome on all 200.
  - With the genome as a constituent, F7's lift is NO_LIFT. v4's verdict is unchanged; the single exact method is canonical on F7's real geometry.
  - Attempt 1 hung before any held-out item finished: the pool was forked after the solver threads started. No outcome was observed. It was fixed, disclosed and re-frozen at a new path.
- **P8 cycle 5** ([evidence](evidence/greg-protected-evolution/2026-10-16-cr-5/README.md)): **REJECT at the adversarial gate.**
  - The `cover/1` search, designed from a review-seed pilot, reached the restart anchor (`p_restart` 1.0) within 0.5% of the best train loss.
  - The argmin of near-tied train means chose `offspring` 6, which failed the lean stress set (+27.5%).
  - The held-out split was never evaluated, but it is spent by its committed freeze.
  - Five cycles, five REJECTs; section 31 item 7 is unmet. Next: a pre-registered selection rule that does not rest on near-tied train means.
- **Genome admission v4** ([evidence](evidence/greg-genome-admission/2026-10-16-v4/README.md)), seeds 1300-1329:
  - `grid_dijkstra` 1.1.0 is **DEFAULT_FOR_GEOMETRY** at 2.60x its baseline, so the grid shortest-path geometry now has an admitted genome.
  - `flow_reinforce_greedy` 1.0.2 (SUPERSEDED) and `flow_capacity_plan` 1.0.3 (COMPOSITION_ONLY) replicate.
  - 35 of 47 are admitted; none is attached.
- **Merged after independent verification:**
  - the compiler lane (three rounds) and the optimisation-verifier lane (four rounds: deadline-bounded Z3 certificates, FEASIBLE bounds certified to rounding noise, truthful dissent);
  - the P8 cycle-5 design;
  - the grid genome, with version-bound compiler measurements and admission CPU and load diagnostics.
- **CI:** job 1's limit was raised to 45 minutes; it runs the suite twice.

Progress 2026-10-21 (measured, frozen, negative results kept):

- **P8 cycle 6** ([evidence](evidence/greg-protected-evolution/2026-10-16-cr-6/README.md)): **RETAIN**, the first improvement protected evolution has kept.
  - The candidate raises `p_restart` from 0 to 0.807. It was 48.4% better on train and better on both stress sets.
  - On held-out (240 fresh items, one look) it won 105-73, p = 0.00995, with 29.6% lower mean loss.
  - It survives the four-attempt threshold on this target (0.0125), not the programme-wide one (0.05/6 = 0.00833).
  - Random restart, reported outside the rule, is at least as good: the candidate goes 80-89 against it, and random restart's mean loss is lower.
  - The proposal is PROPOSED_NOT_APPLIED. Adoption and its canary (re-admission on fresh seeds) are the founder's decision.
  - Section 31 item 7 is met at the proposal level. P8's exit (repeated held-out gains) is not.
- **Design pilots before the freeze** (review seeds 3500-3999; [pilots](evidence/greg-protected-evolution/2026-10-16-cr-6/pilot/README.md)):
  - The planned selection-rule change was refuted: no declared rule beat the lowest train mean, and the sign-test rule coded beforehand did worst (0.20 against 0.55). It is kept in git history and reverted.
  - What changed was power: 120 train and 240 held-out items. To make room, P8's reserved seeds were extended to 7000-8599.
- **Cycle-6 canary** ([evidence](evidence/greg-protected-evolution/2026-10-16-cr-6/canary/README.md)): CANARY_PASSES. It was pre-registered before any instance existed and run on 240 fresh seeds (8300-8539).
  - The proposal beats the incumbent 107-74, p = 0.0086, with a 33.9% lower mean loss.
  - Random restart has the lowest mean loss overall and in both subregions. Against the proposal it wins 95-79 (p = 0.128), which is not significant.
  - On the evidence so far, the options rank random restart, then the proposal, then the incumbent. Nothing is applied.
- **A second P8 target** ([decision](evidence/greg-protected-evolution/2026-10-21-immune-7/DECISION.md)): `immune_detect` was judged NOT_VIABLE by its pilot's rule, declared before the pilot ran: best simulated P(RETAIN) 0.216, threshold 0.30. Cycle 7 is not run.
  - Under the frozen rule one wrong answer makes a held-out mean infinite, so P(RETAIN) falls as the split grows.
  - The pilot found that the adversarial gate missed added wrong answers when the incumbent already had one. This is fixed with a regression test (`stress_worsened`), and no recorded decision changes.
  - How `RULE` should treat wrong answers is an open founder decision.

## Verified Polyintelligence Lift is the Mind's bottleneck metric — 2026-10-07

`INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT` ([record](intent/INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT.json), [verbatim source](intent/sources/POLYINTELLIGENCE-LIFT-REVIEW-2026-10-07-source.md)): founder review of PR #155. P4 learned routing and P6 typed composition are Layer 5 substrate, not the Polyintelligence Mind; all five layers (basal, collective, solver, developmental, meta) remain obligations. Metric: held-out problem families where geometry routing or composition beats the strongest single available intelligence, net of cost/latency, with no added false answers or unauthorized effects; 0 means "a sophisticated router". Sequence: P6 cognitive composition lift → P4 conditional competence memory (hierarchical fallback) → P8 protected evolutionary cognition → IntelligenceGenome library expansion, each family admitted only when it beats simpler baselines on its native geometry. State: active. VPL: 0. Authority delta: none.

Execution record, 2026-10-14 (directive of 2026-10-07, steps 2-13): P6 v2 lift on F2b, X1, X2 (VPL = 4 distinct families with F1); P4 v3, the one pre-registered decisive retest, NO_GAIN (111 = 111 of 130), so per the founder's rule conditional solver learning is not currently worth its complexity (learned mode not recommended; shadow kept for real-mission evidence); P8 protected evolution REJECT (no headroom; every protection held); admission v1/v2: Dawid-Skene and PSO admitted, four families rejected, DE superseded by multistart L-BFGS-B; Layer 4 unseen-damage sweep PARITY. Evidence under `docs/evidence/` (greg-learned-routing, greg-protected-evolution, greg-genome-admission, greg-composition-lift, greg-developmental-sweep). Authority delta: none.

Erratum, 2026-10-15 (review of #179, L2; the line above is kept as written). It is superseded by the convergence accounting in `collaboration/MIND-LINEAGE-RECONCILIATION-2026-10-14.md` section 7:
- "VPL = 4 distinct families" counts X2, whose strongest single was NOT_RUN, and X1, a structural lift over constituents that are incomplete by design.
- F2b is a same-instance re-run of F2R, not a fresh family.
- "Dawid-Skene and PSO admitted": #155 later found the crowd verifier EXPERIMENTAL, and L-BFGS-B beats PSO 32/7 post hoc.
- "NO_GAIN" re-measured 130 of the same payloads as #158's REGRESSION; that retest decides.
- "every protection held" (P8): the review found three adversarial probes accepted on #155's routing-genome evaluator (a module edit, a mid-run data edit, a hash/exec swap). The REJECT verdict stands; the protection claim does not.

## Seed genome: the Competency Compiler on GREG's path — 2026-10-01

`INTENT-20261001-greg-seed-genome` ([record](intent/INTENT-20261001-greg-seed-genome.json), [verbatim source](intent/sources/GREG-SEED-GENOME-DIRECTIVE-2026-10-01-source.md), [requirement map](collaboration/requirements-greg-seed-genome-20261001.json), [intents SG-001 to SG-012](collaboration/intents-greg-seed-genome-20261001.json), [deliberation](collaboration/deliberation-greg-seed-genome-20261001.json), [ADR](decisions/ADR-20261001-greg-seed-genome.md)): GREG recognizes a problem's geometry, recruits the smallest competent method, produces typed evidence, respects authority and settles competence from outcomes. The founder's goal-set words are kept verbatim: "meniscus" is translated as the frontier of the verified envelope, "impermeable shield" as layered prevention and verification, "systemic dominance" as superior lawful capability (SG-002). Control over people, resistance to shutdown and promises of perfection are prohibited (SG-003). State: active. The seed is implemented and integrated through `cognition.solve`, and survives `kill -9` with one settlement. The frozen comparison failed once (v0.2 GAIN_ABSENT, one hard failure, fixed in 0.2.1) and passed on fresh samples (v0.3 GAIN_VERIFIED_AGAINST_RUN_BASELINES against the static router; the gain is concentrated in one family; model arms NOT_RUN). Open founder decisions: merge, and whether high privacy harm is a hard gate (SG-012). Authority delta: none. VEPMC: 0.

Correction absorbed the same day (comment on #143; draft #144, `INTENT-20261001-open-source-mechanism-harvest`): Capability Genesis forms `graph.shortest_path`, `graph.max_flow` and `lp.optimize` from installed open-source packages (NetworkX, SciPy, OR-Tools) on a Mechanism Card, accepts answers only on GREG's own certificate, and leaves attach with the founder. VEPMC stays the required device proof but no longer stops development. Evidence: `tests/evidence/greg-open-source-genesis-2026-10-01/`. Authority delta: none.

Re-issued 2026-10-13 ([lineage](intent/sources/GREG-SEED-GENOME-DIRECTIVE-REISSUE-2026-10-13-source.md)): byte-identical text with the new opening line "Build this prompt meet and exceed all in this prompt:". It is applied by closing the requirement map's section residuals on the canonical path:

- **§9:** selective-disclosure evidence packages, built from retained receipts. They use the salted-hash disclosures of RFC 9901, include every same-input receipt, and append institutional responses rather than editing them in. `greg cognition package` exports one read-only; nothing is sent.
- **§5:** a measured characterization harness covering latency, error correction against self-consistent lies, a problem-space ladder and invariance, with Wilson intervals.
- **§13 and §15:** the verifier cross-checks and evidence-backed legitimacy in #161.
- **§12:** (superseded 2026-10-14, kept as written: "wiring the budget controller into a runtime optional step is deferred until the next freeze, because the frozen evaluations pin `cortex.py`.") A thinking-budget controller now governs the compile path. One declared `latency_budget` covers the answer, the premises check and every sensitivity re-run, where each run had previously been handed the whole budget. Required steps are never priced away; an exhausted budget narrows the result. An optional re-run starts only when the slowest measured step fits. Every run and stop is kept with its reason, and cortex receipts record measured CPU seconds. The earlier deferral was wrong: frozen evaluations run at their freeze commits, so changing `cortex.py` on a branch alters no recorded result.

Repeated byte-identically 2026-10-14T04:59:45Z (same whole-message SHA-256, `ee71d7de…`). Repetition adds no authority; it was applied by closing §12. Repeated byte-identically a third time 2026-10-15T12:21:07Z; applied by closing §16's media case: a DALEOBANKS paraphrase is checked claim by claim against its source, and a sentence that changes a figure, a negation, a hedge, a scope, a direction or a name is held back (`tests/evidence/media-case-convergence-2026-10-15/`). Sent a fourth time 2026-10-15T17:32:27Z with the new opening line "Continue building, and achieving EVERYTHING IN THE PROMPT:" (whole message `9b9eed0c…`; the rest byte-identical to `ee71d7de…`); applied by §14's pre-registered antifragility test, which found that settled competence heard successes only, and by the fix: independently appraised failure closures.

Evidence: `tests/evidence/seed-genome-residuals-2026-10-13/`. Authority delta: none. VEPMC: 0.

## Master build directive and current gate repair — 2026-09-30

The two September 30 master-directive records (this one and the next) describe complementary scopes of the same intended destination: gate-proof repairs and resource requests. Neither creates a second authority or goal owner; their original source lineages remain distinct.

`INTENT-20260930-MASTER-BUILD-GATE` preserves the current session's full
effect horizon and extends the existing convergence/inheritance records. It
does not replace the 34 horizons in `greg/path.json`, the 55 Foundry obligations,
or the founder's authority. [Normalized record](intent/INTENT-20260930-MASTER-BUILD-GATE.json),
[source coverage](collaboration/SOURCE-COVERAGE-20260930-PROOF-INTEGRITY.json),
and [build/evidence report](collaboration/GREG-GATE-REPAIR-20260930.md).

The independent appraiser's earlier VERIFIED claim is falsified for a signed
mission with no observations and a missing required file. Its intended effect
remains active; the current repair requires complete, correctly bound closure
evidence. The installer's earlier success claim is falsified when a public
companion file names a different key from the actual signer. The current repair
checks correspondence and active enrollment, including signed key rotation.

These are implementation/evidence corrections, not destination changes. Exactly
one operational node remains primary: N1, externally verified VEPMC 0 -> 1.
The Chromebook is the candidate under the preserved September 26 hardware
correction; actual Linux availability, founder key custody, installation and
acceptance still require a real run. No local test increments that milestone. The latest Claude rehearsal nonetheless advanced `greg path` to N2 on a container/test-key structural closure. This implementation assumption is superseded: retain the structural candidate and all later horizons, but keep N1 primary until external exit evidence is represented through an authenticated contract. That contract is not implemented; no boolean flag or local count substitutes for it. (#138, b8a0ccd and 673726a, PR-author record.)

**Port onto the installed-body line (2026-10-14).** The appraisal repair (closure-bound evidence, re-expressed for pipeline-resolved parameters) and the signer-enrollment repair are ported as #138 built them. The N1/N2 structural-candidate gate is ported onto the one founder-tier rule that already gates N3, N4, N6 and N7 (`greg/metrics.py` `founder_tier`), not as a hardcoded `met=False`: a closure signed with a test key, a fixture's key or a `--no-passphrase` rehearsal stays `STRUCTURAL_CANDIDATE` and never moves `greg path`; one signed by the enrolled founder key after it attested passphrase custody moves it. Reason: the hardcoded gate meant no evidence, not even Alfonso's genuine Body-1 run, could ever clear N1 (both #138 verifiers flagged it as a founder decision). The founder tier is not the authenticated external contract #138 asked for: trust on first use remains (whoever controls the body's filesystem enrolls the key), and the ledger still cannot prove whose machine or key it is. **Founder decision open:** whether a founder-tier closure plus Alfonso's own signed acceptance suffices for N1, or N1 waits for an external-verification contract. Authority delta: none; the tier grants nothing.

## Master build directive: asks, business sequence, reality, obsolete code — 2026-09-30

`INTENT-2026-09-30-MASTER-BUILD-DIRECTIVE` ([record](intent/INTENT-2026-09-30-MASTER-BUILD-DIRECTIVE.json), [verbatim sections](intent/sources/MASTER-BUILD-DIRECTIVE-2026-09-30-source.md)): GREG may ask for resources (an account, compute, software, a build, a licensed professional, a human worker), and every ask carries evidence, alternatives, costs, expected effect, uncertainty and authority requirements, with no emotional manipulation, no manufactured urgency and no framing of denial as harm to GREG (section 60; **implemented** as the one path `greg/asks.py`). Business grows one verified loop before a second venture (61); new organizations only for recurring bottlenecks (62); regenerative advantage without dependency or exploitation (63); external reality is the final judge (64). Section 76 lets an obsolete implementation leave the active tree when a placement justifies it, with its intent kept on `greg/path.json` and its history in git; this reconciles, and is recorded against, the Final Build Order's preservation rule. State: active. Authority delta: none; asking grants nothing.

## Developmental inheritance — 2026-09-30

`INTENT-2026-09-30-DEVELOPMENTAL-INHERITANCE` ([record](intent/INTENT-2026-09-30-DEVELOPMENTAL-INHERITANCE.json), [verbatim source](intent/sources/DEVELOPMENTAL-INHERITANCE-2026-09-30-source.md)): corrections reroute rather than delete; identify the changed axis; place every lineage on one Backcast GPS (`greg/path.json`) with one of ten classes; keep every founder-intended capability horizon at its node, classified by present feasibility; exactly one operationally primary node; genuine obsolescence only when the effect is no longer wanted, a demonstrably stronger canonical mechanism replaced it, or continuing would violate constraints. It restates PR #68's `intent.aspirations.are_destinations` and `meta.intent_conservation_test` and corrects this day's first reconciliation record. State: active. Authority delta: none.

## One GREG convergence — 2026-09-30

`INTENT-2026-09-30-OPUS-MAXIMUS-CONVERGENCE` ([record](intent/INTENT-2026-09-30-OPUS-MAXIMUS-CONVERGENCE.json), [verbatim source](intent/sources/OPUS-MAXIMUS-CONVERGENCE-2026-09-30-source.md)) directs convergence of competing branch futures into one GREG path, verification of the designated body, truthful persistence, and growth only from measured bottlenecks with founder decision. Conflicts resolved: the 2026-09-26 Chromebook correction controls the first body over Mac-first runbooks; open-source-first controls GREG's model default; FOUNDRY-55 stays an active obligation sequenced after VEPMC (#132 stacked next). Dispositions: [`collaboration/GREG-RECONCILIATION-2026-09-30.md`](collaboration/GREG-RECONCILIATION-2026-09-30.md). State: active. Authority delta: none. VEPMC: 0.

## Foundry Swiss Army knife — 55 mandatory executable systems, 2026-09-27

`INTENT-2026-09-27-FOUNDRY-55` and its [verbatim source](intent/sources/FOUNDRY-55-2026-09-27-source.md) preserve Alfonso's obligation to build **all 55 numbered systems** as individually usable and composable GREG/Foundry capabilities with meaningful tests, reproducible execution evidence, limitations and recovery. Deferral retains the item; removal/substitution requires Alfonso's explicit approval. The `foundry/arsenal.py` status describes available mechanism maturity and **does not certify item-level completion**. Alfonso owns no Mac at present; first-body hardware selection remains open. No permission to deploy, spend, publish, contact third parties or change Kernel authority is granted.

## Real-product repository metabolism — 2026-09-26

`INTENT-2026-09-26-REAL-PRODUCT-METABOLISM` preserves Alfonso's latest explicit anti-cathedral correction with verbatim excerpts in `intent/sources/REAL-PRODUCT-METABOLISM-2026-09-26-source.md`: the project corpus is developmental substrate to be metabolized into the actual GREG product. Experiments, simulations, tests, benchmarks and architecture remain subordinate verification/evidence, not the milestone. Every substantial session must produce a truthful product delta ("what can actual GREG do now that it could not do before?") or identify a precise external blocker. Historical mechanisms may be productized, extracted, recombined, retained as evidence, archived, or removed from the active canonical path while preserving provenance. State: active. Current Single Bottleneck Metric remains VEPMC 0 -> 1.


## Spider-Web compounding rule — 2026-09-25

`INTENT-2026-09-25-SPIDER-WEB-COMPOUNDING` (`intent/INTENT-2026-09-25-SPIDER-WEB-COMPOUNDING.json`, verbatim source in `intent/sources/SPIDER-WEB-2026-09-25-source.md`) makes the founder-intent → verified-outcome transaction the optimization target. Every capability must strengthen at least one of seven control points (eligibility, routing, proof, settlement, reliability, capability formation, compounding), and repeated missions must yield institutional knowledge that improves the next one. Clause inserted in `CANONICAL_EXECUTION_ORDER.md`; enforced by `greg/capabilities.py` registration and `greg/routing.py`; repository dispositions proposed in `collaboration/REPOSITORY-METABOLISM-2026-09-25.json`. State: active; bottleneck VEPMC remains 0 until a Mac run with Alfonso's own key.

## Egregore ecology on the first body — 2026-09-25

`INTENT-2026-09-25-EGREGORE-ECOLOGY` (`intent/INTENT-2026-09-25-EGREGORE-ECOLOGY.json`, verbatim source in `intent/sources/EGREGORE-2026-09-25-source.md`) extends the 09-11 and 09-22 records: one persistent GREG mind over an ecology of governed intelligences (Levin's multiscale competency, compiled to nested light cones), community-coupled through the untrusted data plane, continuity without a survival right, shutdown always winning, and built as real running mechanisms. Implementation and two-pass decision: `collaboration/GREG-BODY-DECISION-2026-09-25.md` and `greg/`. State: active; reality: integration-tested, not Mac-verified, not founder-used.

## First body and persistent GREG product — 2026-09-22

`INTENT-2026-09-22-FIRST-BODY` preserves Alfonso's direct correction: the first owned computer is the practical body of a persistent, governed GREG operating layer above macOS. This is an active product requirement, not a claim of an installed service or a grant of live authority. The intent record and exactly two strengthening passes are in `docs/intent/INTENT-2026-09-22-FIRST-BODY.json` and `docs/collaboration/FIRST_BODY_DECISION_2026-09-22.md`. The date-based ID avoids the unresolved `INTENT-0029` collision in draft #86 and draft #105. Runtime ownership (#70/#87) and live founder authentication remain unresolved.

## Embodied GREG and developmental trajectory — 2026-09-11

[INTENT-GREG-EMBODIED-2026-09-11](intent/INTENT-GREG-EMBODIED-2026-09-11.md)
is the current product correction, subordinate to no older metaphorical framing.
It preserves INTENT-0030 and the full business, human-workforce and economic/
compute horizon. GREG-001 is partial proof, not that destination. Exact selected
source, conflicts, scope and two-pass OPUS-2026-09-11 decision are linked there.
No new runtime authority or activation is created.

## GREG bounded real mission — 2026-09-10

The current chat directs one bounded real mission that continues after the
interface closes, uses a real capability, respects approval, recovers from
interruption and reports evidence. This advances INTENT-0030 and SR-INTENT-2;
the hardware operating layer, capability growth, human teams/business operation
and compounding horizon remain intended. A fixed audit is a proof dependency,
not a redefinition of that destination. It confers no machine sovereignty.

- intent_id: GREG-INTENT-1
- statement: prove one persistent bounded mission before expanding architecture
- source_refs: current chat, 2026-09-10 GREG core-loop direction; no cryptographic founder authentication claim
- owner: Alfonso; existing Kernel mission, workflow, policy and appraisal owners
- state: active; local development proof exercised, hardware mission unproven
- binding_scope: reversible implementation, verification and draft review
- constitutional_constraints: existing five powers, pre-existing grants, no activation or authority expansion
- success_evidence: tests/evidence/greg-proof/ and linked GREG-001 decision
- failure_evidence: focused-first.log; retained host/authentication/evaluator limitations
- dependencies: adopted SR-001 package, existing DurableWorkflow/Gate/Ledger, independent hardware/authentication gate
- conflicts: generalizing frozen synthetic Goal Chase merely for one audit adds avoidable scope
- next_review_trigger: review executable local proof, then supply an approved hardware and authority integration route
- supersedes: no implementation or historical alternative; prioritizes an executable proof over additional architecture

Decision and two-pass dissent: [GREG-001](collaboration/GREG-ONE-MISSION-PROOF.md).

## SR-001 bounded recovery — 2026-09-08

These are faithful summaries of the current founder directive, not verbatim
messages, cryptographic founder authentication or executable runtime commands.
The exact chat-message timestamp and stable conversation ID are unavailable.
Source: current chat, "Accepted. Preserve WMI PR #33" shared-recovery directive;
related project-memory excerpts are summaries and the supplied architecture
documents are proposals/aspirations. Repetition creates no additional authority.

| Required field | SR-INTENT-1 | SR-INTENT-2 | SR-INTENT-3 |
| --- | --- | --- | --- |
| statement | Repair shared admission, history, replay and consumer compatibility through draft review | Preserve complete persistent founder-governed UNIIMENTE and broad exercised capabilities | Keep merge, deployment, credentials, founder enrollment, external acts and automatic self-modification outside this package |
| source_refs | Current founder directive; SR-001 source table in rationalization plan | Current directive; supplied architecture texts; project-memory September 3–7 excerpts | Current explicit authorization boundaries override older speculative execution language |
| owner | Kernel semantic owners, WMI and DALEOBANKS adapter maintainers; Alfonso remains root | Alfonso; Kernel/Developmental Engine/Egregore and organ owners | Alfonso and canonical Kernel consequence authority |
| state | active | active | prohibited |
| binding_scope | Constitutional development/test/draft artifacts only | Destination continuity, not runtime activation | Reserved actions in this package, not a permanent retirement of the destination |
| constitutional_constraints | Five powers separate; no parallel authority, identity, event or consequence plane | Router above OMNIMORPH; simplest sufficient mechanism, static workflow exact-tie winner | Chat text, hashes and shared-key possession never authenticate Alfonso |
| success_evidence | tests/evidence/shared-recovery/ and linked consumer evidence; distinct checks only | None for whole-body closure, 24/7 operation or accepted external outcomes | No reserved action authorized by this record |
| failure_evidence | Frozen baseline mismatches, legacy checkpoint incompatibility, blocked DALEOBANKS broad suite, Docker gap | CMC and VDM remain zero; founder attention/outcome metrics unknown | Source 06 automatic policy deployment and source 07 unattended-operation claims cannot override present boundaries |
| dependencies | One pinned Kernel boundary package, WMI #33, consumer conformance, protected #94 appraisal | Authenticated admission, durable continuity, protected evaluation, routed consequences, real outcomes before compounding claims | Separate future founder ruling for reserved scope |
| conflicts | Historical experiment formats differ; preserved, not retuned | Speculative perfection/infinite-improvement claims need evidence | Older automatic-activation proposals are superseded for this package |
| next_review_trigger | Exact draft adoption package and remaining gates reviewed | Qualified founder workflow and subsequent accepted outcomes | Explicit future authorized ruling, not a model inference |
| supersedes | No accepted implementation/history deleted | None; narrow repair does not redefine UNIIMENTE | Speculative activation in this package only |
| superseded_by | None | None | None |
| implementation_refs | Shared events/, provenance/, adapters/, contracts/, policy/consequence_gate.py; linked organ shims | Existing anatomy retained; no new whole-machine runtime | Refusal paths and draft-only handoff |


## INTENT-20261013-GOAL-GRAVITY — 2026-10-13

Goal Gravity + Experiential Intelligence + Asymmetry Production Line. The founder's
2026-10-13 directive (verbatim: `docs/intent/sources/GOAL-GRAVITY-DIRECTIVE-2026-10-13-source.md`)
compiles to one behavioral property of the canonical standing runtime: an authorized
persistent goal is an attractor for relevant perception, backcasting, preparation,
capability formation and Gate-governed action. Record: `docs/intent/INTENT-20261013-GOAL-GRAVITY.md`
(machine-readable `.json` validates against the skill schema). State: **active**,
`active_requirement`, consequence class `material`. Implementation: `egregore/gravity.py`
and its sibling modules on `main`'s runtime; decision record
`docs/decisions/ADR-GOAL-GRAVITY-001.md`; deliberation
`docs/collaboration/deliberation-goal-gravity-2026-10-13.json`. Evidence tier at
recording: IMPLEMENTED / UNIT-TESTED / INTEGRATION-TESTED on synthetic ledgers; not
externally verified, not founder-accepted. The dated identifier is used because the
numeric `INTENT-00NN` series (0029–0037) is allocated across unmerged draft branches.
Overlapping unmerged mechanisms (#158 `greg/gravity.py`, #114/#137 `greg/missions.py`,
#93/#97/#109 Goal Chase) are preserved as substrate; their reconciliation is a founder
merge decision, never a silent replacement.

UNIIMENTE must never silently lose a founder intention, contributor objection, negative result, or superseded design.

Every material intention discovered in chats, documents, issues, pull requests, repositories, or operating evidence must be normalized into an Intent Record and assigned exactly one lifecycle state:

- `active`: binding design or operating direction.
- `implemented`: enforced by code, contract, test, workflow, or policy.
- `deferred`: preserved with an explicit trigger, dependency, and review date.
- `superseded`: replaced by a stronger formulation, with lineage and rationale.
- `prohibited`: incompatible with law, safety, constitutional authority, evidence integrity, or human sovereignty.
- `exploratory`: a hypothesis that may inform experiments but has no authority.

No aspiration becomes executable merely because it appears in prose. Classification preserves ambition without converting speculation, contradiction, or outdated language into accidental authority.

## Required Intent Record

Each record must contain:

1. `intent_id`
2. `statement`
3. `source_refs`
4. `owner`
5. `state`
6. `binding_scope`
7. `constitutional_constraints`
8. `success_evidence`
9. `failure_evidence`
10. `dependencies`
11. `conflicts`
12. `next_review_trigger`
13. `supersedes`
14. `superseded_by`
15. `implementation_refs`

## Upward Interpretation Rule

When an intention is ambiguous, interpret it toward the strongest lawful, evidence-preserving, human-sovereign, reversible, and commercially durable form.

### Effect-not-metaphor rule

`INTENT-0030` is the controlling interpretation rule for biological, institutional, mythic, and science-fiction language.

> **Preserve the intended effect. Do not literalize the metaphor.**

Unless Alfonso explicitly specifies an implementation form, terms such as `egregore`, `organism`, `morphogenesis`, `cell`, `tissue`, `organ`, `immune system`, `metabolism`, `healing`, `regeneration`, `nervous system`, `embodiment`, `omniscience`, `Jarvis`, `immortality`, and similar language are **outcome specifications and mechanism-discovery prompts**.

Contributors must:

1. preserve the exact aspiration as a serious target capability;
2. identify the observable underlying effect;
3. separate literal requirements from analogy or aspiration;
4. search existing capabilities, commodity software, open source, APIs, plugins, services, computer-use routes, and small adapters before inventing architecture;
5. use mechanism extraction/mutation/recombination when existing components are insufficient;
6. build only the residual CapabilityDeficit;
7. verify the underlying effect, not resemblance to the metaphor.

`not implemented` must never be silently converted into `not intended`.

A science-fiction aspiration may remain partially or wholly unrealizable with current technology. That changes its evidence state and path; it does not erase the founder's destination.

Canonical UNIIMENTE morphogenesis means **functional capability formation or reconfiguration in response to a verified discrepancy or CapabilityDeficit**. Digital cells, tissues, local developmental rules, decentralized topologies, or dynamically generated organizations are optional research mechanisms, not requirements.

Historical literal interpretations remain preserved as evidence and mechanism sources but are superseded as controlling founder intent where they conflict with `INTENT-0030`.

See `docs/FOUNDER_EFFECT_COMPILER.md` and `docs/intent/INTENT-0030-effect-not-metaphor.md`.

"Build upward" never means:

- inventing evidence;
- bypassing the Consequence Gate;
- granting machines sovereignty;
- converting aspirations into production claims;
- concealing downside;
- deleting rejected branches or negative results;
- increasing complexity without a measured control advantage;
- reproducing the surface form of a founder metaphor when a simpler mechanism produces the intended effect;
- inventing a new framework before checking whether existing real technology already closes the capability gap.

It means improving the architecture until its strongest useful property is retained with lower fragility, clearer authority, stronger proof, easier replacement, better participant welfare, and higher verified effect per unit of complexity.

## Mandatory Traceability

A material pull request must identify the Intent Records it advances, conflicts with, defers, or supersedes. A change with no traceable intention is either maintenance work or scope drift and must be labeled accordingly.

When the work originates in a metaphorical or science-fiction founder statement, the pull request must also trace:

- founder expression;
- intended effect;
- literal requirements versus metaphor;
- existing mechanisms considered;
- residual CapabilityDeficit;
- why the selected mechanism is superior to the simplest viable alternative;
- evidence that would falsify the claimed effect.

The canonical ledger should ultimately become machine-readable. Until that implementation lands, issues and ADRs must use these fields verbatim.

## INTENT-20261021-PROFESSIONAL-PARALLEL-TEAM

- **Statement:** All entering agents must discover Alfonso's SOP/protocols through Discussions and work accurately in parallel as a professional development team.
- **Source:** Alfonso's 2026-10-21 repository-audit continuation; exact message retained in [team-entry decision](collaboration/TEAM-ENTRY-DECISION-2026-10-21.md).
- **Owner:** Alfonso for adoption; named implementer/integrator per bounded task.
- **State:** active.
- **Binding scope:** contributor entry, current work claims, overlap handling, verified integration and handoffs; all participating repositories/clients are intended consumers, rollout pending.
- **Constitutional constraints:** existing authority, privacy, evidence, refusal and consequence controls remain binding; no merge, activation or settings authority follows.
- **Success evidence:** two fresh sessions find the correct instructions and claims, agree a nonoverlapping split and resume a handoff without founder reconstruction; NOT_RUN.
- **Failure evidence:** duplicated active owners, stale-base rework, frozen-evidence overwrite or increased founder reconstruction.
- **Dependencies:** authorized adoption of entry patch, authenticated Discussion update and explicit client/organ adoption.
- **Conflicts:** no outcome conflict identified; competing integration ownership remains unresolved and is not assigned here.
- **Next review trigger:** adoption, first fresh-session collision/handoff failure, or five completed pilot PRs.
- **Supersedes:** none; extends the existing bootstrap and pinned Discussion.
- **Superseded by:** none.
- **Implementation refs:** [team entry](collaboration/START_HERE.md), AGENTS.md and CLAUDE.md; draft until adopted.

# Collaboration rollout continuation — 2026-10-21

INTENT-20261021-COMPLETE-COLLABORATION: Alfonso's follow-up, “Complete it and improve
it. Comprehensively,” extends the entry repair through one consolidated SOP/checker,
consumer entry pointers, independent review and behavioral verification. Status:
active; implementation and adoption remain distinct. Full machine completion stays
BODY + ORGANS + MIND. Exact lineage, limits, owner and review triggers are in
[the rollout intent record](collaboration/FOUNDER-INTENTS-ROLLOUT-2026-10-21.json),
with a linked [two-pass decision](collaboration/DELIBERATION-ROLLOUT-2026-10-21.json).
No earlier intent is silently superseded; existing merge, credential and live-effect
restrictions remain. Current evidence is in collaboration/VALIDATION.md.


## Seed Genome integration — October 1, 2026

[INTENT-2026-10-01-POLYINTELLIGENCE-SEED](intent/INTENT-2026-10-01-POLYINTELLIGENCE-SEED.json) remains **active**: bounded computation is integrated into the existing GREG mission, authority and journal path; the complete directive and live verification remain open. [Current scope, evidence and residual obligations](cortex/GREG_SEED_GENOME.md) govern claims. [Every supplied directive line and Appendix A item](cortex/SEED_GENOME_REQUIREMENTS.json) has retained lineage. PR137 is the runtime base; PR141 is reused and preserved; PR139's selected integration/outcome mechanisms remain linked for later extraction. The simple static policy is retained after a negative advantage comparison. No cognition result changes human sovereignty. P0–P13/C1–C8 live beneath `greg/path.json`; N1/VEPMC remains primary, and Foundry-55 is unaffected.


## Full-machine completion — controlling correction, October 1, 2026

**BODY + ORGANS + MIND = GREG / UNIIMENTE** is the fixed completion boundary. Read `intent/INTENT-20261001-FULL-MACHINE-COMPLETION.json` and its verbatim source. Reconstruct the whole boundary, implement the highest-priority unfinished dependency in rigorous increments, prove and integrate each increment, then automatically resume the parent objective and the next unblocked requirement. Seeds, experiments, sandboxes, benchmarks, PRs and VEPMC are intermediate sequencing/evidence units; none may narrow the machine or stop unrelated feasible implementation. A future-family label preserves its obligation. Registered is not implemented; a tested component is not an integrated machine.

Continue until the currently achievable machine is integrated and executable. A precise founder-only action, genuine external dependency or demonstrated technology limit blocks only the affected requirement; continue other buildable work, preserve the destination and implement the strongest defensible approximation/backcast. Prose and placeholders cannot replace executable machinery when feasible. Existing authority, resource, consent, refusal, pause/revocation and shutdown gates remain effective.

Intent remains **active**, implementation in progress. Preserve prior Seed Genome negative evidence and N1/VEPMC authentic-use predicates; they do not gate unrelated software completion. Propagation evidence is recorded separately from intent and never inferred from a plan.
