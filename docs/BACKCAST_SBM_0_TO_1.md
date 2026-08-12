# Backcast GPS: Clean Verified Outcome Count, 0 → 1

Produced with the `backcast-gps` skill on 2026-08-12, against the evidence this
branch actually computes. Companion to `docs/BACKCAST_GPS.md` (2026-07, stage-gated
build plan) — that document routes to *capability*; this one routes to the *Single
Bottleneck Metric*. Where they disagree, the SBM wins, because the Egregore v1
program names Clean Verified Outcome Count as the single bottleneck.

**This is a route, not an authorization.** Every node terminates at a founder
decision or an external party. Nothing here may execute.

---

## Reasoning Summary

**Current reality, from executed evidence rather than prose.** `python -m blueprint`
awards 10 of 55 technologies PROVEN, 21 EXERCISED, and **0 HARDENED** — HARDENED
requires a reconciled external outcome and the institution has none. The Consequence
Gate (#30) is PROVEN and *has never executed a real external effect*: every recorded
traversal terminates in a test executor. Payments (#38), double-entry (#39) and the
Regenerative Treasury (#55) are EXERCISED but `SIMULATED`. There is no kernel HTTP
surface (#31, BLUEPRINT), so organs deliver through tests rather than through an
endpoint.

**Control layer — and this is the finding that reorders the plan.** The blueprint's
frontier ranks **#4 Databases** (leverage 28), **#7 PKI** (23) and **#26 zero-trust**
(10) as the highest-leverage *unblocked technologies*. That ranking is correct and it
is **not** the route to the SBM. Every technical path already terminates at a gate
that is built, tested and green. What the gate cannot obtain is a **named legal
principal holding a payment account, transacting with a consenting counterparty**.

> The deepest constraint is not capability. It is that no lawful commercial identity
> exists for the institution to act through, so the one component designed to produce
> an external consequence has nothing it is permitted to do.

Building #4 and #7 makes 28 and 23 downstream technologies *eligible to advance a
rung*. Neither moves the SBM by one. Optimising the technical frontier while the
controlling layer is unchanged is exactly the failure this skill exists to refuse.

**Strongest counterexample to my own diagnosis.** If the first verified outcome is
non-commercial — a free, consented, externally observable deliverable — then no
payment account is needed and the control layer is *consent plus observability*, not
legal identity. That is a materially cheaper route and it is why Route F below wins
the tournament. The counterexample survives: it is not refuted, it is adopted.

**Selected route:** Fast (F) — one free, consented, externally verifiable
deliverable to one real recipient, through the real Gate, producing a reconciled
outcome record. Commercial closure follows as Node 5+, not as a precondition.

---

## GPS Lock

| | |
|---|---|
| **Destination** | `VERIFIED_OUTCOME_COUNT = 1`: one externally observable consequence, produced through the canonical Consequence Gate under a named legal principal, accepted by a real counterparty, reconciled, and recorded as an outcome the ledger can replay. |
| **Current position** | 0 verified outcomes. Gate PROVEN but never fired externally. 5 organ manifests, 8 identity registrations, 2 of the 5 manifests unregistered. No HTTP surface. No payment rail. Suite 575 passed / 20 failed (CONTRADICTION-0001). |
| **Active node** | **N0 — Constitutional ratification and legal principal.** |
| **Active gate** | Permission. `identity/organ-registry.yaml` and the Constitution are unratified; no legal principal is authorised to bear consequence. Recorded as an unresolved row in the kernel manifest since Phase Zero. |
| **Gate-crossing evidence** | A signed founder ratification recorded on the evidence ledger, naming (a) the ratified Constitution version hash, and (b) at least one legal principal permitted to bear an `external_contact` consequence. |
| **Active SBM** | **Ratified authority artifacts = 0 → 2** (constitution hash + one legal principal). |
| **Baseline** | 0. `docs/intent/INTENT-0001` records UNIIMENTE-as-legal-principal as **PROHIBITED**, so the principal must be a human or a real entity. |
| **Target** | 2. |
| **Resource budget** | Zero machine spend. Founder attention only: one review session. No code is required to clear N0 — building more is the standing temptation and it is not the gate. |
| **Three-step system** | Select one unratified artifact → present it in its smallest reviewable form → record the decision on the ledger. |
| **Review cadence** | On any founder decision, or 14 days, whichever is first. |

**If N0 does not clear, nothing downstream is rational.** Every later node
presupposes an accountable principal. This is why the technical frontier, however
well computed, is not the active node.

---

## Critical Assumption Register

| # | Assumption | Confidence | Supporting | Contradicting | Cheapest decisive test | If false |
|---|---|---|---|---|---|---|
| A1 | A verified outcome does not require money to change hands. | Medium-high | The Egregore program's closure list requires "a real buyer **or enforceable economic commitment**"; §5.5 says payment alone is not closure. | Wave 6 names a *paid* IVIO/OBVIO outcome as the birth threshold. | Ask the founder to rule: does a free consented deliverable count toward the SBM? One sentence. | Route F collapses; the route becomes Resilient (R) and N0 gains "payment account" as a third ratified artifact. |
| A2 | A human legal principal can be named without forming an entity. | Medium | `authority/legal-principals.yaml` exists and `alfonso_lopez` is already the declared legal operator on every manifest. | Consequence class `financial` may require an entity for liability reasons. | Founder confirms whether he will personally bear an `external_contact` consequence. | N0 grows an entity-formation sub-node with legal-advice dependency and a multi-week horizon. |
| A3 | The Gate will execute correctly on first real contact. | Medium | 12 adversarial gate cases pass; the full pipeline reaches `RECORDED` in test. | It has never run against a real executor; the executor has always been a fixture. | A shadow run: real recipient, real Gate, executor writes to a local file instead of the world. | Node 3 gains a hardening cycle before any real effect. |
| A4 | An external observer can verify the outcome without privileged access. | Medium-low | Nothing in the kernel produces an externally checkable artifact today. | No HTTP surface (#31), no public receipt format. | Draft the receipt an outsider would need and show it to one non-participant. | Node 4 must build a public verification artifact before the outcome counts. |
| A5 | CONTRADICTION-0001 does not block the route. | High | It affects only the Package 3 repair suite; no node here depends on it. | A permanently red suite may block merging any supporting change. | Already known: 20 red, all one cause. | Route unaffected; merge friction only. |

**A1 is the highest-value question in this document.** One founder sentence
determines whether the route is 4 nodes or 7.

---

## Route Tournament

| Route | Description | P(success) | Time to proof | Capital eff. | Reversibility | Downside | Dependency conc. | Optionality | Durability | Stakeholder value | Ethical risk | **Total** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **F — Free consented deliverable** | One real recipient receives one useful artifact through the Gate; they confirm receipt and usefulness. | 8 | 9 | 10 | 9 | 9 | 6 | 7 | 6 | 7 | 9 | **80** |
| **R — Paid IVIO/OBVIO closure** | The Wave 6 birth threshold: real buyer, accepted deliverable, reconciled payment. | 3 | 2 | 4 | 4 | 5 | 3 | 9 | 10 | 9 | 7 | **56** |
| **L — Build the technical frontier first** | Clear #4, #7, #26, then #27/#29, then attempt an outcome. | 5 | 3 | 5 | 8 | 8 | 8 | 8 | 8 | 3 | 9 | **65** |

**F wins on risk-adjusted score and on the only axis that matters now: time to
proof.** It is the shortest path that produces a *real* external consequence.

**Why R loses today.** It is the strongest destination and the wrong next node. It
requires a payment account, a customer, a delivery capability and a reconciliation
path — four external dependencies compounding. Its 9s and 10s on optionality and
durability are real, which is why it is Node 5+, not Node 1.

**Why L loses.** It is the seductive one, because the blueprint ranks it and the work
is entirely within my control. Building #4 and #7 makes 51 technologies *eligible* to
advance and moves the SBM by exactly **zero**. Capability without a counterparty is
the status quo with better tooling. Its 3 on stakeholder value is the tell.

---

## G — Backcasted Success State

**Final state.** One external consequence exists that UNIIMENTE caused, a named legal
principal is accountable for it, a real person outside the institution received and
confirmed it, the Consequence Gate authorised it at commit time, and the evidence
ledger can replay the full chain: evidence → policy → grant → witness → execution →
receipt → acceptance → reconciliation → outcome.

**Time horizon.** 3–10 weeks, dominated entirely by N0 and N2 (both founder-gated).
Machine work is days. **This is a range under founder-controlled uncertainty, not a
promise.**

**Completion conditions.** All must hold: a signed ratification on the ledger; a
named non-UNIIMENTE legal principal; a consenting recipient with recorded consent; a
Gate traversal whose executor produced a real effect; a receipt an outsider can check
without kernel access; a reconciliation record with no unresolved obligation; an
outcome record whose `verification_strength` is not self-report.

**Constraints.** `INTENT-0001` — UNIIMENTE may never be the legal principal. No
external effect outside the Gate. Recipient consent must be informed and revocable.
No payment without a real account. No claim of verification from a self-report.

**Superiority test.** Against "publish something publicly": that produces an
observable event but no accountable counterparty and no acceptance, so it cannot
close the loop §5.5 requires. Against "run the pipeline against a mock": produces a
green test and zero institutional truth. G is superior because it is the *smallest*
state that makes every one of the nine gate conditions real simultaneously.

**Entrenchment map.** Clearing G leaves: a ratified constitution hash (reusable by
every future action), a named legal principal (reusable), the first real Gate
receipt (a template for all subsequent ones), a reconciliation procedure that has run
once, a causal episode in memory with real rather than fixture outcomes, and the
first technology eligible for **HARDENED** — which unlocks the top rung for the whole
ladder.

**Ethical asymmetric advantages.** Consent obtained before capability is built.
Proof produced before trust is requested. A free deliverable creates no financial
exposure for the recipient and no liability for the principal, so the first real
action is also the safest one the institution will ever take.

**Warnings.** The prestige trap here is building the Foundry, the Composer or the
knowledge graph's outcome tail — all interesting, none of which move the SBM. The
false shortcut is declaring a simulated outcome "verified". The fragile dependency is
a single founder decision gating everything.

**Falsification.** G becomes irrational if the founder declines to ratify or to be
named principal, and no delegated human accepts either. At that point the
institution is a governed capability set with no lawful way to act, and the honest
response is to say so rather than to keep building.

---

## P — Stage-Gated Plan

**Six nodes.** Fewer would merge a permission gate with a capability gate; more would
split transitions that share a gate and a system.

### N0 — Ratified authority *(ACTIVE)*
- **Outcome:** the Constitution is ratified and one non-UNIIMENTE legal principal is authorised for `external_contact`.
- **Gate:** permission. **SBM:** ratified artifacts 0 → 2.
- **Entry:** already met.
- **Exit evidence:** a ledger record carrying the constitution hash, the principal, the scope, and a founder signature.
- **Entrenchment:** every later node and every future action reuses both artifacts.
- **Duration:** one founder session. **Accelerator:** present the smallest reviewable form. **Delay risk:** presenting the whole Constitution instead of the ratification decision.
- **Kill:** founder declines and names no delegate → G is falsified; report and stop.

### N1 — Consent and counterparty
- **Outcome:** one real person outside the institution has agreed to receive one specific artifact and to confirm receipt.
- **Gate:** trust and access. **SBM:** recorded consents 0 → 1.
- **Entry:** N0 clear (a principal must exist before anyone is asked to rely on one).
- **Exit evidence:** informed, revocable, recorded consent naming the artifact and the confirmation method.
- **Kill:** three approaches decline → the artifact is not wanted; reroute to what is.

### N2 — Deliverable defined and produced
- **Outcome:** the artifact exists and is useful to that person.
- **Gate:** capability. **SBM:** artifact accepted in draft, 0 → 1.
- **Entry:** N1 clear. **Exit evidence:** recipient confirms the draft would be useful *before* the Gate is involved.
- **Note:** this is deliberately ordinary work, not institutional machinery.

### N3 — Real Gate traversal (shadow first)
- **Outcome:** the Gate authorises the delivery and a real executor performs it.
- **Gate:** operational readiness. **SBM:** shadow traversals with a real executor, 0 → 1, then live 0 → 1.
- **Entry:** N2 clear. **Exit evidence:** a commit witness binding the exact effect, and a receipt.
- **Accelerator:** run shadow with a file-writing executor first (tests A3 at zero external risk).
- **Kill:** the Gate refuses for a reason that is correct → fix the request, not the Gate.

### N4 — External verification
- **Outcome:** someone who is not a participant can confirm the consequence occurred.
- **Gate:** proof. **SBM:** independent confirmations 0 → 1.
- **Entry:** N3 clear. **Exit evidence:** a receipt checkable without kernel access.
- **Entrenchment:** this artifact is the template for every future outcome, and it is what tests A4.

### N5 — Reconciliation and outcome record
- **Outcome:** obligations closed, outcome recorded, causal memory updated, **SBM = 1**.
- **Gate:** settlement. **SBM:** unresolved obligations → 0.
- **Exit evidence:** an outcome record with non-self-report verification strength; `CausalMemory.ancestry` reconstructs the chain over real records.
- **Entrenchment:** the first technology becomes eligible for HARDENED.

**Only N0 is active.** N1–N5 are provisional and will be recalculated from N0's
actual evidence.

---

## S — Three-Step System for N0

### Execution card

**1. Select**
- **Tiny Yes:** get one ratification decision recorded — not the whole Constitution reviewed.
- **Target:** Alfonso Lopez.
- **Expected evidence:** a yes, a no, or a named condition, written to the ledger.
- **Resource ceiling:** one page presented; 15 minutes of founder attention.

**2. Execute**
- **Trigger:** the next founder session.
- **Exact action:** present exactly two questions. *(i)* "Do you ratify constitution version `<hash>` as binding?" *(ii)* "Do you authorise `<principal>` to bear an `external_contact` consequence, scoped to one free consented deliverable?"
- **Quantity:** two questions. Not three.
- **Quality standard:** each answerable without opening another document.
- **Stop condition:** if the founder needs to read more first, that reading *is* the next Tiny Yes — do not press.

**3. Evidence**
- **Record:** the decision, verbatim, on the evidence ledger with its date.
- **Update:** ratified artifacts count.
- **Decision:** **repeat** if partial; **refine** if the questions were unclear; **reroute** to a delegated human if the founder declines personally; **retire** if he declines and names no delegate.

### Operating range
- **Bad day:** ask question (i) only.
- **Standard:** both questions, decision recorded.
- **Maximum useful:** both plus the scope sentence for N1's consent request.

### Measurement and control
- **Leading:** founder has the one-page artifact in hand.
- **Lagging:** ratified artifacts = 2.
- **Failure signal:** a third code artifact gets built while N0 is unclear.
- **Adjustment trigger:** 14 days with no decision → the presentation is wrong, not the founder.
- **Completion evidence:** ledger record with constitution hash and named principal.

---

## Adversarial Defense

**Where an opponent would attack.** Not the technology — the sequencing. The most
effective attack on this route is to make building feel like progress. Fifty-five
technologies with a computed frontier is an almost perfect machine for generating
legitimate-looking work that moves the SBM by zero. **The frontier is a trap for this
particular goal and should be read as one.**

**Single dependency that collapses the route.** One founder decision gates all six
nodes. Mitigation: A2 identifies a delegated human as the fallback principal;
`authority/reserved-matters.yaml` should be checked for whether ratification itself
is delegable.

**Evidence that could be lost.** Recipient consent, if obtained verbally. Record it
before N2 begins.

**Hardest commitment to reverse.** N3's live traversal — the first real external
effect cannot be unsent. Mitigation: the shadow run in N3 is mandatory, not optional.

**Success creating a new failure mode.** One verified outcome will make HARDENED
reachable and create pressure to claim it broadly. HARDENED is per-technology and
requires *that technology's* outcome; the ladder enforces this, and the enforcement
must not be relaxed under that pressure.

---

## Probability Update

- **N0 clearance:** 60–85%. Wide because it depends entirely on founder availability and appetite, neither of which I can observe.
- **Full path to SBM = 1:** 35–60%, conditional on N0. A1 moves this most: a "yes, free counts" answer pushes toward the top; "no, it must be paid" drops it toward 20–35% and lengthens the horizon by months.
- **Timing confidence:** low on calendar, high on ordering. I am confident about *what comes next*; I have no basis for predicting *when*.
- **Evidence moving the estimate:** that the Gate is PROVEN with 12 passing adversarial cases raises N3 confidence materially. That it has never met a real executor keeps it below high.

**Command: CONTINUE** — with the active node reassigned from technology to permission.

---

## Exact Next Actions

| # | Action | Owner | Trigger | Expected evidence | Gate weakened |
|---|---|---|---|---|---|
| 1 | Answer A1: does a free consented deliverable count toward the SBM? | Founder | Next session | One sentence | Route selection |
| 2 | Answer A2: will you personally be the named legal principal? | Founder | Next session | One sentence | N0 permission |
| 3 | Produce the one-page ratification artifact (2 questions, constitution hash) | Claude | After 1 and 2 | A reviewable page | N0 friction |
| 4 | Record the ratification decision on the evidence ledger | Claude | After 3 | Ledger record | N0 exit |
| 5 | Identify three candidate recipients for a free deliverable | Founder | After N0 | Three names | N1 access |
| 6 | Check `authority/reserved-matters.yaml`: is ratification delegable? | Claude | Now | Yes/no | Dependency concentration |

Action 6 is the only one not gated on the founder and is worth doing first, because
it may widen the single dependency this whole route hangs on.

---

## Immediate Execution Card

- **Do today:** answer A1 and A2. Two sentences.
- **Record:** both answers, verbatim, in this document's revision.
- **Stop doing:** advancing technologies on the blueprint frontier as though they were the route to the SBM. They advance *capability*. They are not the gate.
- **Review trigger:** any founder decision, or 14 days.
- **Evidence required to advance:** a ledger record carrying a ratified constitution hash and a named legal principal.

---

## Process Quality Gate

Scored honestly. **90/100.**

| # | Category | Score | Note |
|---|---|---|---|
| 1 | Reality grounding | 10 | Every current-state number is executed output, not recollection. |
| 2 | Control-layer diagnosis | 10 | Named the permission layer beneath the visible capability problem, and stated that the computed frontier is the wrong route for this goal. |
| 3 | Assumptions and decisive tests | 10 | Five registered; A1 and A2 are one-sentence tests. |
| 4 | Power and incentives | 8 | Founder, principal and Claude are mapped. **The recipient side is not** — no candidate counterparty exists yet, so the beneficiary/buyer/veto map for N1 is genuinely unknown. |
| 5 | Superior falsifiable G | 10 | Nine conditions, all observable; falsification stated. |
| 6 | Route tournament | 10 | Three materially different routes scored; the seductive one (L) rejected with its reason. |
| 7 | Node gates and exit evidence | 10 | Six nodes, one SBM each, objective exits. |
| 8 | Three-step SOP | 10 | Two questions, one page, bad-day version. |
| 9 | Measurement and kill controls | 10 | Kill criteria at every node; probability ranges honest about their width. |
| 10 | Ethics and immediate action | 8 | Consent-first, no coercion, next action is a two-sentence founder answer. **Held back**: recipient welfare cannot be fully assessed before a recipient exists. |

**Missing 10 points, stated rather than papered over:** categories 4 and 10 both
depend on a counterparty who does not yet exist. They cannot reach 10 until N1 has a
name in it. Scoring them 10 now would be certainty theater.
