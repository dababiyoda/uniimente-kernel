# GREG Body 1 — founder-intent reconciliation and bounded build decision

Decision `GREG-BODY-2026-09-25` · constitutional scope · **EXPERIMENT (implemented, integration-tested)** ·
owner Alfonso Lopez · intent `INTENT-2026-09-25-EGREGORE-ECOLOGY` (extends `INTENT-2026-09-22-FIRST-BODY`,
`INTENT-GREG-EMBODIED-2026-09-11`, `INTENT-0030`). Five perspectives below are one contributor's analysis,
not independent reviewers. No merge, deployment, credential, spend or external effect is authorized here.

## 1. Source coverage manifest (honest, not complete)

| Source family | Coverage | Founder intent / claims extracted | Evidence tier |
|---|---|---|---|
| Kernel doctrine (`AGENTS.md`, `CLAUDE.md`, 20 `docs/*.md`, 4 intent records, ownership map, integration manifest, founder-loop gate) | inspected (full for governing docs; targeted for release/evidence packets) | effect-not-metaphor; preservation; one authority; first-body product; SR-001 limits | repository text |
| Kernel code used by GREG (ledger, spine, gate, policy engine, passports, witness, genome registry, closure, verifier) | inspected at API level | canonical owners and their contracts | executed |
| Kernel open PRs (~60 listed); bodies read: #53, #70, #101–#102 (via branches), #108, #109, #110, #111; issue #33 | partial | GREG lineage, runtime ownership conflict (#70/#87), CVO-001 | PR text + executed merges |
| DALEOBANKS (README, AGENTS, EXPERIMENT_001, IDEA_REFINERY, constitution, services list) | partial; broad suite executed (324 pass, no network) | media/distribution organ; draft-first; human arming | executed |
| WealthMachineIntelligence (README, AGENTS, Instructions, Phase 6/7, treasury; PR #37 body) | partial; suite executed (126 pass, 2 socket-denied) | venture assessment; regenerative waterfall; transaction-infrastructure doctrine | executed |
| RailScout (README, AGENTS, issue #1 LIVE PLAYER doctrine) | full (repo is one README) | research refinery; wedge → rail → OS; exactly one next action | repository text |
| PumpStation, RESEARCH-IN, build-your-own-x | README/AGENTS + file inventories | Web3 cell stub; research monorepo skeleton; mechanism atlas | repository text |
| Project conversations, uploaded PDFs/texts, exports, Replit runtime, closed-PR discussions, most older PR bodies | **unavailable in this session** | not reconstructed; not claimed | — |

## 2. Founder correction chronology (latest wins; nothing erased)

2026-07-19 Kernel/backcast (cathedral risk named) → 2026-07-20 Phase Zero bridges → 2026-08-19 RailScout LIVE PLAYER →
2026-08-22 organize around existing work (INTENT-0027/28) → 2026-09-08 SR-001 shared recovery → 2026-09-09 effect-not-metaphor
(INTENT-0030) → 2026-09-10 one bounded GREG mission → 2026-09-11 embodied GREG → 2026-09-13 IVIO-NEMT retired as active venture →
2026-09-22 first body (Mac) → **2026-09-25 egregore ecology: one mind over many governed intelligences, built for real,
community-coupled, continuity without survival right, shutdown always wins.**

## 3. Intent conflict matrix

| Original / older statement | Later clarification | Intended effect | Current implementation | Correction |
|---|---|---|---|---|
| Morphogenesis as cells/tissues (developmental/, #58–#66) | INTENT-0030; 09-22/09-25 "morphology is the new functional capability" | acquire the missing function and resume the goal | `greg/genesis.py` (real acquisition + independent verification) | developmental/ stays research; GREG imports none of it (guardrail test) |
| "Build the metaphors literally" (09-25) | INTENT-0030 | effects must be real and running, not simulations | GREG body runs as a real supervised process | effect-literal, not surface-literal; **founder confirmation requested** |
| Functional survival mechanisms (09-25) | §33 no right to survive | continuity of missions across failure | durable ledger + supervisor restart; exit 0 never restarted | shutdown/STOP/SIGKILL always win (integration test) |
| Increasingly self-directed (09-25) | intelligence never creates authority | chooses next move, waits, replans, acquires capability | light-cone containment + Gate | self-direction only inside founder-signed scope |
| Founder cockpit = dashboard (ownership map OWN-0007) | 09-11/09-22 GREG is the face of a persistent institution | one interface over a running body | `python -m greg` CLI + inbox IPC; native shell pending | cockpit reclassified as GREG shell over the body |
| GoalChase sandbox as the goal engine (#93/#97/#109) | first-body decision: sandbox mechanism, not the product runtime | durable general goals | `egregore/goal_chase*` (sealed, SIMULATED) + `greg/missions.py` (product) | GoalChase retained as sealed experiment/benchmark; not unsealed |
| Synthetic HMAC founder envelopes | SR-001: chat text/hashes never authenticate Alfonso | real founder authentication | Ed25519 envelopes, TOFU enrollment, nonce retention | real crypto; key custody ceremony remains a founder step |
| Build every Phase Zero registry/bridge first | 09-11 sequencing correction | usable mission before catalog completeness | GREG built on existing owners only | followed |

## 4. What was built (exact, labeled)

`greg/` package: founder (Ed25519), lightcone (Levin-style bounded competency), capabilities (broker, secret handles,
isolated CLI, Mac adapters), authority (cone → Kernel grant → Gate), missions (Infinite Goal Chase controller),
genesis (Capability Genesis), tribunal (morning report + critique), dataplane (untrusted intake), compute (telemetry,
recommendation, node enrollment), sop (procedure compounding), body (persistent host), service (launchd/systemd/
supervisord), cli; `contracts/greg-mission.schema.json`; `closure/greg_registry.py` (five closures);
`greg/mac/verify_mac_body.sh`; tests (unit + real-process supervised integration); evidence `tests/evidence/greg-body/`.

Reality gradient: IMPLEMENTED · UNIT TESTED · INTEGRATION TESTED (real processes, commodity supervisor, SIGKILL,
signed stop) · **not** PACKAGED · **not** MAC-VERIFIED · **not** FOUNDER-USED · **not** LIVE · no external outcome.

## 5. Residual CapabilityDeficit and mechanisms searched

| Needed effect | Searched first | Chosen | Residual built |
|---|---|---|---|
| founder authentication | GoalChase HMAC (synthetic), WMI JWT (workload), Kernel witness HMAC | commodity Ed25519 (`cryptography`) | envelope binding + nonce retention (~150 lines) |
| persistent host | #101 finite host, #109 slot host | OS supervisors (launchd/systemd/supervisord) | body loop with exit-code contract |
| action authority | Gate, GrantIssuer, policy engine | reused unchanged | cone containment + grant-first evaluation |
| goal pursuit | GoalChase (sealed), DurableWorkflow | event-sourced mission projection on the spine | discrepancy controller, ladder, surprise, blockers |
| missing capability | genome registry, #57 regeneration experiments (fixed candidates) | installed commodity tools + frozen oracles | search/verify/attach pipeline |
| isolation | Kernel seccomp launcher | reused; macOS `sandbox-exec` | cross-platform wrapper |

## 6. Alternatives (Pass 1 — steelman, strengthen the winner)

| Option | Founder fidelity | Time to value | Security | Ceiling | Verdict |
|---|---|---|---|---|---|
| A current trajectory (more drafts/doctrine) | medium | none | ok | high | converge instead |
| B chatbot | low | fast | weak persistence | low | interface only |
| C cloud autonomous agent | medium | fast | vendor/control risk | medium | replaceable worker |
| D desktop assistant | medium | medium | UI-bound | medium | shell layer |
| E local-first operating layer | high | medium | strong | high | host pattern adopted |
| F custom OS | low | very slow | fragile | none extra | regress |
| G **hybrid embodied institution** (Kernel authority, local body, rented cognition) | **highest** | medium | strong with Gate | highest | **selected** |
| H human-AI company OS | high later | slow | depends | highest | destination after first business loop |
| do nothing | — | — | — | — | loses: zero usable mission |

Pass-1 strengthening: body owns lifecycle only; every effect through Gate; missions event-sourced on the one ledger;
commodity supervisors; founder commands as signed files so interfaces are disposable; Genesis prefers installed tools
before builders; light-cone containment encodes "capability may be copied, authority may not".

| Role | Strongest case | Disadvantage → conversion |
|---|---|---|
| Founder-Intent Steward | first real persistent body that keeps working with every UI closed | CLI is not the Mac app → shipped the Mac verification package and supervisor configs |
| Systems Architect | zero new authority plane; reuses Gate/ledger/spine | spine refresh is O(n) per emit → recorded as resource limit; compaction is future work |
| Adversarial Reviewer | forged/replayed/tampered/out-of-scope all refuse in tests | TOFU enrollment is only as strong as physical access → labeled; Secure Enclave ceremony future |
| Operator / Maintainer | one process, one writer, exit-code contract | single writer blocks CLI writes → inbox file-drop IPC |
| Evidence / Welfare Guardian | morning report separates founder judgment from objective failure | metrics could flatter → nulls instead of zeros; surprises reported |

## 7. Pass 2 — attack the strengthened design

| Attack | Finding | Resolution / owner / threshold |
|---|---|---|
| Overengineering | 13 small modules | each maps to a founder-named effect and has a test; kill any without a test by next review (Kernel maintainer) |
| Privilege concentration | body holds witness key and ledger | witness key is body-local, not founder; founder key never enters the body |
| Security theater | seccomp/sandbox-exec could be absent | isolation absence refuses the command (fail closed), tested |
| Prompt injection | external text reaching planners | only signed envelopes are commands; injection quarantined (tested); no LLM planner yet |
| Credential theft | secrets file in body | per-handle resolution, never ledgered (tested); Keychain lookup on macOS; vault encryption future |
| Model dependence | none today (0 model calls) | router proposed; any model output enters as data |
| Excessive autonomy | acts inside cone without asking | cone is founder-signed, bounded by horizon/budget/ceiling; financial/irreversible never delegable |
| Insufficient autonomy / founder interruption | out-of-scope asks | exactly one request per scope; waits silently (tested) |
| False completion | worker success ≠ goal | closure only on re-observed checks; surprises reported |
| Mac lock-in / cloud lock-in | macOS adapters | portable core runs on Linux; hardware replaceable from ledger |
| Packaging cannot ship | no .app yet | Swift shell + SMAppService agent is the next step; Python core unchanged |
| Financial waste / business fantasy | none claimed | CMC/VDM unchanged at 0; first business loop is a separate milestone |
| Legal | UNIIMENTE never a principal | all effects attach to `alfonso_lopez` via existing registry |

**Material dissent retained:** (1) the Ed25519 envelope proves key possession, not that Alfonso is at the keyboard;
(2) mission strategies are founder- or author-supplied — autonomous strategy *generation* (model planner) is not built;
(3) the builder route of Genesis is an interface without a connected coding agent; (4) the supervised proof ran on
Linux with supervisord, not macOS launchd.

## 8. Open-PR reconciliation (verified state 2026-09-25)

| PR | Disposition |
|---|---|
| Kernel #101, #102, #110 | **MERGE CANDIDATE** — composed into this branch with their commits; full suite green |
| Kernel #108, #109 | **MERGE CANDIDATE** — composed (ledger conflict resolved keeping both sections); GoalChase stays sealed SIMULATED |
| Kernel #111 | **MERGE CANDIDATE** — composed; leverage proposer not yet wired to GREG missions |
| Kernel #93, #97 | **CLOSE AFTER MIGRATION** — content carried by #109 (founder approval required to close) |
| Kernel #94 | **PRESERVE AS EXPERIMENT** — protected appraisal; porting an independent appraiser into GREG closure is the next evidence upgrade |
| Kernel #88, #90, #92 | **PRESERVE AS EXPERIMENT** — organizational-morphogenesis research; subordinate to mission resolution |
| Kernel #86, #105 | **NEEDS_FOUNDER_DECISION** — both claim INTENT-0029; #105 content feeds the future model router |
| Kernel #70 vs #87 | **NEEDS_FOUNDER_DECISION** — runtime ownership; GREG composes neither; #70 is conflicted against main |
| Kernel #57, #58–#66 | **PRESERVE AS EXPERIMENT** — regeneration/developmental research, mechanism substrate for Genesis |
| Kernel #53 | **NEEDS_FOUNDER_DECISION** — first venture (IVIO-NEMT retired 09-13) |
| Kernel #11–#26 (non-draft July phase PRs) | **UNVERIFIED** — likely superseded by canonical-v1; inspect individually before any close |
| DALEOBANKS #71/#74, WMI #31/#32 | **CLOSE AFTER MIGRATION** candidates — transport parity superseded by merged SR-001 (#77/#35); verify diff first |
| DALEOBANKS #58–#61/#73 | **NEEDS_FOUNDER_DECISION** — SDK-shim stack (DUP-4) |
| WMI #37 | **RETAIN (draft)** — regenerative transaction doctrine feeds the future business runtime |

## 9. Single Bottleneck Metric

**Verified Embodied Persistent Mission Closures (VEPMC): 0 → 1** on founder-owned hardware, counting only a mission
that (a) is signed with Alfonso's own enrolled key, (b) is submitted from an interface that then closes, (c) advances
under the OS supervisor without founder prompting, (d) uses ≥1 real capability, (e) stops at ≥1 approval boundary,
(f) survives an interruption with reconciliation exactly once, (g) closes only on re-observed evidence and (h) is
reviewed in a morning tribunal. Current value: **0** (the Linux supervised run satisfies (b)–(g) with a test key;
(a) and (h) with Alfonso and macOS remain). It cannot be gamed by activity: actions, ticks and documents do not count.

## 10. Milestones (dependency order, verified against the 09-11 correction)

1. Alfonso runs `greg/mac/verify_mac_body.sh`, then enrolls his own key → **VEPMC 1**.
2. Native shell: SwiftUI app + SMAppService agent wrapping `python -m greg run`; phone = authenticated client of the body.
3. Model router (Anthropic/OpenAI/local) whose outputs enter as data-plane proposals; strategy generation for missions.
4. First business whole-loop (content → QA → founder-approved publish via DALEOBANKS gateway → analytics → owned relationship).
5. Verified novel capability via a connected coding-agent builder (Genesis builder route) with frozen oracle.
6. Human + AI team closure; 7. infrastructure scaling closure (compute recommendation → founder purchase → node enrollment).

## 11. Falsification, rollback, kill criteria

Falsified if: an action executes outside a founder-signed cone without an exact approval; a forged/replayed command is
applied; a crash duplicates a consequence; STOP fails; a mission closes without re-observed evidence; a secret appears
in the ledger. Rollback: leave this PR unmerged or revert `greg/` and the closure registration; retained ledgers are
never rewritten. Kill/regress if: a second policy plane appears; founder effort rises without outcome gain;
architecture count grows without VEPMC; any module self-authorizes or optimizes self-preservation.

## 12. Decision

**EXPERIMENT** — retain as the product runtime candidate; founder decisions listed in the final report are required
before merge, live enrollment and any live capability beyond the local filesystem.

## 13. Addendum — Spider-Web compounding and repository alchemy (2026-09-25/26)

Founder input: `INTENT-2026-09-25-SPIDER-WEB-COMPOUNDING` (verbatim source
`docs/intent/sources/SPIDER-WEB-2026-09-25-source.md`) and the Repository Alchemy directive. One contributor's
analysis; the five roles below are perspectives, not five reviewers.

**Target effect.** Each closure makes the next mission more likely to close, with evidence, and a capability that
strengthens nothing cannot enter. Falsified if: a capability with no super-node registers; one mission's
failure or refuted closure leaves the next mission's routing unchanged; VEPMC is awarded without ledger facts;
the appraiser shares the body's process or trusts the body's claims.

**Built (vertical, on the existing body; no new authority plane).** Super-node validation at registration;
`routing.py` (ledger-derived reliability, routing decision recorded with alternatives); `appraisal.py`
(separate-process appraiser over a read-only head-pinned ledger); `metrics.py` (VEPMC from nine ledger
conditions); `templates.py` (`repo-guardian`, `workspace-note`); `repo.pin_audit` (extracted from
`egregore/repository_audit.py`, #101); Proof→Routing edge (appraiser refutation of the effect lowers
reliability; mechanism from `memory/causal.py`); `STRATEGY_SUPER_NODES` translation to `evolution/spider_web.py`;
`closure_event_id` on the product surface; `FIRST_MISSION.md`.

**Alternatives.**

| Alternative | Benefit | Liability | Disposition |
|---|---|---|---|
| Do nothing (founder-authored strategy order) | simplest | no institutional learning; violates the rule's knowledge clause | baseline in tests (first mission uses cost order) |
| Posterior-mean routing from the ledger (chosen) | deterministic, replayable, auditable | never explores; a recovered capability stays penalized until drift re-enables it | retain |
| DALEOBANKS `services/bandit.py` Thompson sampling | explores; handles non-stationary tools | in-memory state, unseeded randomness: not replayable, weak for exactly-once audit | benchmark; seeded-draw recombination proposed |
| External model-based planner/router | richer choices | model output is not evidence; cost; vendor dependence | deferred until a mission lacks strategies |
| Rewrite `evolution/spider_web.py` to seven nodes | one vocabulary | destroys history; strategy tribunal ≠ capability rule | rejected; translation map instead |

**Pass 1 — structural inversion.** Routing knowledge is a proprietary asset only if it survives model and
hardware replacement: it lives in the ledger, not in process memory, so it passes to any future body. It becomes
a liability if it overfits to one bad night, so penalties are counted, never permanent exclusions (only a founder
critique excludes). The appraiser becomes a proof moat only if it is independent: separate process, re-derivation
from receipt bytes, and re-observation of the world; its stated limit is that it shares reviewed Kernel code. The
rule could become a vanity checkbox: a capability declares a super-node without strengthening it. Bound: the
declaration is necessary, not sufficient; the metabolism record requires GREG-path evidence for bucket A.

**Pass 2 — adversarial compounding.** (1) A hostile or buggy appraiser could poison routing by refuting
everything. Bound: only effect-related appraiser checks move routing, the appraiser is replay-reproducible from a
pinned head, and its verdicts are ledgered for audit. Accepted residual, owner: Kernel maintainers; kill if
appraiser false-refutation is observed. (2) Routing knowledge could leak across missions with different targets.
Accepted: reliability is per capability, not per target; revisit when target-level history exists. (3)
Metabolism dispositions could be read as authority to archive or kill. Bound: the record is `PROPOSED`, a
guardrail forbids delete dispositions, and termination remains a founder decision. (4) The Proof→Routing edge
counts the same refutation against every capability that acted, including sensors. Accepted: only DONE actions
are counted, and read-only sensors are not actions.

**Five roles (condensed).** Builder: every addition sits on the running body and changes a measurable number.
Adversary: the three hostile cases (forged closure, changed world, foreign-fault refutation) are tests, and two
mutations of the routing rule are caught. Operator: `greg vepmc`, `greg routing` and `closure_event_id` make the
metric inspectable without the journal. Beneficiary: Alfonso's effort is the runbook's ~30 minutes, and nothing
here spends or publishes. Constitutional: no module grants itself anything; `founder_accepted` and `mac_body` are
unreachable by the machine.

**Decision.** EXPERIMENT, continuing §12. VEPMC stays 0 until Alfonso runs `greg/FIRST_MISSION.md` on his Mac.
