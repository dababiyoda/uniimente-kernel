# Founder Intent Coverage Matrix

Deliverable B. Each active intention maps to the module that serves it, the code path, the strongest proof tier reached on this branch, what is still missing, the owner, the blocker and the next test that could falsify the claim. Proof tiers, weakest to strongest: CLAIMED (prose only), UNIT (unit tests), INTEGRATION (multi-module or multi-process tests), SANDBOX-WHOLE-MACHINE (one supervised body crossing Body, Mind, Hands, Genesis, two organs and the Gate), FOUNDER-DEVICE (VEPMC), EXTERNAL (an outside party accepted a real outcome). No row on this branch reaches FOUNDER-DEVICE or EXTERNAL.

## 1. Active intentions

| Intent | Canonical module and code path | Proof tier | Missing behavior | Owner | Blocker | Next falsification test |
|---|---|---|---|---|---|---|
| Full-machine completion boundary, BODY + ORGANS + MIND (`INTENT-20261001-FULL-MACHINE-COMPLETION`) | `greg/body.py` loop over `greg/missions.py`, `greg/cognition/`, `greg/genesis.py`, `greg/organs.py`, `greg/workers.py` | SANDBOX-WHOLE-MACHINE twice: the ten-step proof (required confinement) and #178's one-mission test (supervised confinement) | The same chain on a founder-designated device with Alfonso's key | Alfonso; Kernel maintainers | Founder device and key | Run `tests/integration/test_one_machine_ten_steps.py` from a clean clone on the designated device; it must pass with the founder's key |
| Effect, not metaphor (`INTENT-0030`) | Applied in every design record; morphogenesis is `greg/genesis.py`, not a cell simulation | UNIT and INTEGRATION for the mechanisms; the doctrine itself is not testable code | None at the doctrine level | All contributors | None | A PR that adds a literal biological runtime without beating a simpler baseline must be refused in review |
| Build the real product (`INTENT-2026-09-26-REAL-PRODUCT-METABOLISM`) | This branch's product deltas: worker confinement setting, standing reconciliation, Goal Gravity merged with #178's ordering | INTEGRATION | Founder use | Alfonso | Founder use | The founder runs one mission end to end on the console without editing JSON |
| Spider-Web compounding (`INTENT-2026-09-25-SPIDER-WEB-COMPOUNDING`) | `greg/capabilities.py` registration rule; `greg/routing.py` learned routing; `greg/improvement.py` | UNIT; the ten-step proof step 10 shows one founder correction changing a later decision | Compounding across real missions | Alfonso | Real missions | A capability that declares no control point must still be refused at registration (`tests/unit/test_greg_spiderweb.py`) |
| Egregore ecology, shutdown always wins (`INTENT-2026-09-25-EGREGORE-ECOLOGY`) | `greg/body.py` STOP path (mid-tick STOP ingest, `_stop_now`), `greg/lightcone.py` | INTEGRATION; signed STOP in the ten-step proof | None for STOP | Alfonso | None | A signed STOP delivered while a worker runs must stop it within one poll and record no completed action |
| First body and persistent product (`INTENT-2026-09-22-FIRST-BODY`; Chromebook correction 2026-09-26) | `greg/service.py` (supervisord, systemd user service), `greg/doctor.py` Chromebook probe | INTEGRATION under supervisord in a container | Real Chromebook run, reboot survival | Alfonso | Hardware in hand, founder action | `greg doctor` on the Chromebook reports `ready_for_linux_service`, then a reboot keeps the mission |
| Foundry 55 numbered systems (`INTENT-2026-09-27-FOUNDRY-55`) | `foundry/completion.yaml`, `foundry/systems/` | Mixed; partial items #9, #10, #26, #28, #52 as reported on #173 | Item-level completion evidence for every partial item | Alfonso | Engineering time | `foundry/completion.yaml` must never list an item COMPLETE without a test path that exists and passes |
| Asks with evidence, no manipulation (`INTENT-2026-09-30-MASTER-BUILD-DIRECTIVE` section 60) | `greg/asks.py` | UNIT | None | Alfonso | None | An ask without alternatives, costs or uncertainty must be refused by `asks.py` |
| Developmental inheritance (`INTENT-2026-09-30-DEVELOPMENTAL-INHERITANCE`) | `greg/path.json`, `greg/path.py` | UNIT (`tests/unit/test_developmental_inheritance.py`) | None | Alfonso | None | Removing a lineage node without a placement must fail the inheritance test |
| Polyintelligence Mind and Verified Polyintelligence Lift (`INTENT-20261001-greg-seed-genome`, `INTENT-20261007-*`) | `greg/cognition/` Competency Compiler, genomes, settlement | UNIT and frozen evaluations; VPL 3 of 4 families | Lift on a new natural family (P6 v3) | Alfonso; Mind maintainers | Engineering time | P6 v3 on a fresh natural family must show lift net of cost, or VPL stays where it is |
| RECOMBINE: Genesis constructs new capabilities (`INTENT-20261013-FRONTIER-LEAP-RECOMBINE`) | `greg/recombine.py`, `greg/genesis.py` construction rung | SANDBOX-WHOLE-MACHINE (#178 stage 3: `assignment.staffing` constructed over `graph.max_flow`) | Construction for a non-reduction function | Alfonso | Research | A construction whose engine lies must be quarantined and re-formed (existing test) |
| Goal Gravity (`INTENT-20261013-GOAL-GRAVITY`) | `egregore/gravity.py` loop bound to the body by `greg/goal_gravity.py` (#175); mission ordering by `greg/gravity.py` `select` (#178) | UNIT and INTEGRATION (128 tests on this branch) | Founder-signed goals in real use | Alfonso | Founder use | A forged unsigned goal record must never be admitted (`test_greg_goal_gravity_authority.py`) |
| One-machine corrective directive A-H (2026-10-14) | See section 2 | See section 2 | See section 2 | Alfonso | See section 2 | See section 2 |
| FABLE 5.1 OPUS MAXIMUS (`INTENT-20261014-FABLE-OPUS-MAXIMUS`) | This branch | INTEGRATION and SANDBOX-WHOLE-MACHINE | Founder review and merge decision | Alfonso | Founder decision | Section 12 of the prompt: the ten steps rerun from a clean setup |
| VEPMC (`greg/metrics.py`) | `metrics.vepmc` | Computed 0 | A founder-device closure | Alfonso | Device, key, acceptance | `metrics.vepmc` must stay 0 for any run signed with a test key (asserted in both whole-machine tests) |

## 2. The 2026-10-14 directive's eight capability areas

| Area | Where it runs | Proof tier | What is missing |
|---|---|---|---|
| A. Persistent self-directed goal pursuit | Missions survive restarts (`greg/missions.py` fold from the ledger); Goal Gravity goals; night shift and morning tribunal (`greg/tribunal.py`) | SANDBOX-WHOLE-MACHINE | Long unattended runs on the founder body |
| B. Polyintelligence | `greg/cognition/`; CP-SAT with a Z3 certificate in the ten-step proof | INTEGRATION | Human experts as routed workers; multi-model disagreement on real models |
| C. Real Hands | Filesystem, git, CLI workers, `browser.render` behind the relay | INTEGRATION | Visual desktop control; remote execution; physical bodies |
| D. Functional morphogenesis | Genesis and RECOMBINE | SANDBOX-WHOLE-MACHINE | Builder route against real paid workers (not authorized) |
| E. Economic and institutional organs | `organ.exchange`, `venture.assess`, FIXTURE venture rehearsal | INTEGRATION with real organ code | A real buyer, real settlement |
| F. Community and institutional feedback | Untrusted data plane (`greg/dataplane.py`); community pages behind the owner gate | UNIT | Real community input |
| G. Resilience and regeneration | Reconciliation, standing reconciliation, governed half-open recovery, STOP | SANDBOX-WHOLE-MACHINE | Backup and secure migration rehearsed on the founder body |
| H. Long-horizon expansion | Interfaces only (capability genomes, node enrollment) | CLAIMED | Everything in section 4 marked FRONTIER or SCIENCE-FICTION |

## 3. Golden 5 and Maturity Gates

The Golden 5 are evaluated per mission on this branch, as domain evaluations and not a second Kernel:

| Control | What answers it on this branch | Status |
|---|---|---|
| Performance | Mission checks close; the appraiser re-derives them | Met in sandbox |
| Money | Signed budgets, booked spend, the signed cap on unknown spend | Met in sandbox; no real money |
| Floor | Gate refusals, protected surfaces, confinement setting, confined egress | Met in sandbox |
| Proof | Separate-process appraiser; #178's independent verifier | Met in sandbox |
| Future | Held-out learning, Genesis repair, reproducible clean-setup proofs | Met in sandbox |

The master prompt names "Maturity Gates A-H" without defining them. The founder's 2026-10-14 directive, section 15 ("Institutional maturity and graduation"), lists eight gates numbered 1 to 8. This matrix maps A-H to those eight in order. **That mapping is an inference, not a founder statement.** The directive's rule governs: "Do not represent an incomplete gate as cleared. No agent may graduate itself into higher consequential autonomy."

| Gate | Directive wording | Evidence on this branch | Cleared? |
|---|---|---|---|
| A | Authority continuity | One founder key path, device delegation, key rotation, STOP; tested | No: needs founder-device proof and succession |
| B | Epistemic integrity | Typed receipts, separate-process appraisal, negative results kept | No: needs external verification |
| C | Workload and supply-chain trust | Worker envelope, confinement setting, protected surfaces, SHA-pinned dependencies where pinned; organ pin unhashed | No |
| D | Incident response and operational continuity | Reconciliation, recovery, STOP, supervisord | No: no rehearsed incident on the founder body |
| E | Participant and data rights | Untrusted data plane, consent rules in DALEOBANKS | No: no real participants |
| F | Legal and economic accountability | Founder as legal principal; FIXTURE commerce only | No |
| G | Goal and portfolio governance | Signed missions and goals, Goal Gravity narrowing controls | No: not in real use |
| H | Human and physical institutional integration | None | No |

## 4. Horizon ledger

| Capability | Label | Missing dependency | Falsifiable milestone |
|---|---|---|---|
| One supervised body running Body, Mind, Hands, Genesis, two organs and the Gate | BUILDABLE (done in sandbox) | Founder device | VEPMC 0 to 1 |
| Standing reconciliation of consequence-inert interruptions | BUILDABLE (done) | None | Ten-step 7b with the opt-in asks no founder question and completes once |
| Per-organ keys in the organs | BUILDABLE | Founder pin decision | Organ messages verify only under their own organ key |
| A first real Venture Cell transaction | EXPERIMENTAL | Buyer, payment rail, founder authorization | One accepted delivery with a reconciled payment |
| Verified Polyintelligence Lift on every admitted family | EXPERIMENTAL | Research | P6 v3 lift on a new natural family |
| Multibody GREG across several founder-owned devices | FRONTIER | Node enrollment in real use, network trust | Two enrolled nodes complete one mission with one ledger |
| Autonomous laboratories, robotics, physical bodies | FRONTIER | Hardware, safety cases, law | A bounded physical action through the Gate with an independent witness |
| Civilizational scientific and economic infrastructure | SCIENCE-FICTION for now | Decades of verified outcomes | None claimable today |
| Immortal operation, conscious life, metaphysical access | SCIENCE-FICTION | Not engineering claims | Never claimed |
