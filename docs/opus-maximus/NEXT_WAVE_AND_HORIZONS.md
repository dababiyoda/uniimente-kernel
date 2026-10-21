# Next Wave and Horizons

Deliverable K. The next wave is ordered by dependency: each item names what it needs first and the evidence that would close it. Horizons carry evidence gates, not dates that promise outcomes.

## 1. The next engineering wave

| # | Work unit | Depends on | Closing evidence | Who can do it |
|---:|---|---|---|---|
| 1 | **VEPMC 0 to 1 on the designated Chromebook.** Run `greg/CHROMEBOOK_FIRST_MISSION.md` end to end with Alfonso's own key, kill the body mid-mission, restart, appraise, and accept the closure | Founder hardware in hand; founder key; founder acceptance | `greg vepmc` reports 1 from that body's own ledger; the closure event is founder-accepted | Founder, with an agent on call |
| 2 | Re-admit the control, game, information and probabilistic operation verdicts on the merged code (Track B merged at `16f53f5`; this branch's #159 solvers changed the code those verdicts measured, so the code binding routes them as UNEVALUATED) | Nothing | A pre-registered genome-admission run on fresh held-out seeds (the 2026-10-15-v3 procedure) restores DEFAULT_FOR_GEOMETRY with evidence, or records a negative. **Done 2026-10-21** (`462bd98`, seeds 2600-2629): control, game and information DEFAULT again; probabilistic EXPERIMENTAL, a recorded negative (`docs/evidence/greg-genome-admission/2026-10-21-operations/`) | Agent |
| 3 | Organ pin upgrade to a boundary package with per-organ keys (#174) | Founder decision on the pin | An organ message signed with another organ's key is refused at the kernel; both organs' own suites pass on the new pin | Founder decides; agent implements in the organ repos |
| 4 | DALEOBANKS publish bridge: forward a DALEOBANKS grant and draft id from a founder-signed GREG grant, and report `publish_gated` truthfully | Nothing for the code; founder authorization for any live post | A dry run returns `publish_gated` with the true reason; no live post | Agent; founder for live |
| 5 | Land RailScout PR #9 on RailScout main, then pin `venture.assess` to it | RailScout maintainer review | `venture.assess` runs against RailScout main, not a draft branch | Agent |
| 6 | P6 v3: Verified Polyintelligence Lift on a new natural family with the admitted genomes | Nothing | Pre-registered evaluation; lift net of cost and latency, or a recorded negative | Agent |
| 7 | Fold-time re-verification of `decision.answered` on the mission side (#175 ADR known limitation). **Implemented 2026-10-16** (branch `conv-item7` on PR #184's `7418c82`; ADR-GOAL-GRAVITY-002 "Next-wave item 7"); `mission.registered` stays deferred | Nothing | An unsigned `decision.answered` written straight to the ledger no longer moves a mission: `tests/unit/test_greg_answer_reverification.py` fails on `7418c82` and passes here (targeted suites; the full suite and the proofs are run by the integrator) | Agent |
| 8 | First real Venture Cell pilot with escrowed order budgets (invention configuration 11) | Founder authorization, a real buyer, a payment rail, legal principal | One accepted delivery with a reconciled payment and an independent appraisal | Founder authorizes; agent builds |

Items 2, 4 (dry run), 5 and 6 need no founder decision and can start immediately; item 7 needed none and is implemented, awaiting integration. Item 1 is the single bottleneck metric.

## 2. 2026/27 horizon

| Capability | Label | Evidence gate |
|---|---|---|
| A founder-used GREG on the Chromebook, surviving reboots, with a weekly morning tribunal | BUILDABLE | VEPMC at least 1, then four consecutive weekly tribunals with founder critiques retained |
| The founder delegates routine engineering missions and intervention falls | BUILDABLE | Founder interventions per closed mission, measured from the ledger, falling over eight weeks with duplicate consequences at 0 |
| A second enrolled node (N2) finishing missions on the same ledger | EXPERIMENTAL | Two nodes, one ledger, one mission closed across both, appraised |
| One Venture Cell with a real recurring buyer-backed transaction | EXPERIMENTAL | Three accepted deliveries, reconciled payments, positive unit economics after the operator's time is priced |
| DALEOBANKS publishing through the Kernel gate under founder grants | EXPERIMENTAL | Live posts only under grants, each with a retained receipt and truthful telemetry |
| Verified Polyintelligence Lift on every admitted family | EXPERIMENTAL | Lift on each family, or the family demoted |

## 3. Ten-year horizon

| Capability | Label | Evidence gate |
|---|---|---|
| A portfolio of Venture Cells whose shared proof and settlement rail is used by outside participants because it is cheaper and more trustworthy | FRONTIER | An independent consequential actor (buyer, insurer, regulator, auditor) accepts GREG's proof as sufficient for a decision it would otherwise check itself |
| Multibody GREG across founder-owned devices and leased compute, with valid succession | FRONTIER | Succession rehearsal: a designated successor's key takes over a running institution under the constitution, witnessed |
| Autonomous laboratories, robotics and physical bodies under the Gate | FRONTIER | A bounded physical action with a safety case, an independent witness and a legal principal |
| Civilizational scientific and economic infrastructure | SCIENCE-FICTION today | No gate is claimable now; it stays on the path as a destination |

## 4. What never changes on any horizon

The founder remains the legal principal and root authority. STOP, revocation, refusal and downgrade hold under failure. No component authorizes its own promotion. VEPMC moves only on the founder's designated device with the founder's acceptance.
