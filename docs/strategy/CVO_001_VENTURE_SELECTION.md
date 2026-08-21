# CVO-001 Venture Selection

> **IVIO is preserved as historical evidence but is not an active candidate for CVO-001.**

**Status: PLAN ONLY.** Selection is not activation. Nothing here authorizes
company formation, deployment, sales contact, email, social posting, spending,
payment collection, real-world data processing, wallet creation, token launch,
smart-contract deployment, settlement, or customer onboarding.

**Planning base:** `main` @ `8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1`
**Supersedes:** `docs/operations/CVO_001_READINESS_PACKET.md` (IVIO-centric;
preserved, marked `PRESERVED_HISTORICAL / INACTIVE / NOT_SELECTED`)

---

## 0. Single Bottleneck Metric

**Clean Verified Outcome Count: 0 → 1.**

A Clean Verified Outcome requires **all nine**, with no partial credit:

1. a real external buyer or contracting counterparty;
2. a bounded accepted deliverable;
3. a real payment or enforceable economic commitment;
4. an independently checkable external result;
5. closed reconciliation;
6. attributable legal operator;
7. no critical authority violation;
8. no material participant harm;
9. no simulated fixture represented as reality.

The current count is **0**. The single recorded external consequence (PR #26 —
a real HTTPS GET with receipt `05d804016bee…`) is a **Verified Mediated External
Effect**. It fails conditions 1, 2, 3 and 5. It is not a CVO and is never
counted as one.

**The failure mode this document is written against.** Every candidate below
could be made to produce something that *resembles* a CVO within a week: a
demo, a pilot, a letter of intent, a founder-attested result. Nine conditions
exist so that resemblance is not enough. Condition 9 is doing the most work.

---

## 1. Method and its limits

Candidates were drawn from the repository, the 21 open PRs, the three organ
manifests, and the doctrine. Scoring is 1–10 across 20 criteria, weighted.

**What this scoring is not.** It is one author's judgment applied consistently,
not market research. No buyer was contacted. No price was tested. Scores for
*time to first paid outcome*, *budget proximity* and *founder access* are the
least reliable and the most decision-relevant — a bad guess there changes the
ranking. They are marked as the primary falsification targets in §7.

**Weights**, chosen before scoring to avoid fitting them to a preferred answer:

| Weight | Criteria | Why |
|---|---|---|
| **×3** | time to first paid outcome; founder access to customers; legal simplicity; downside containment | These decide whether CVO-001 happens at all this quarter |
| **×2** | identifiable buyer; painful recurring problem; budget proximity; accepted deliverable clarity; external outcome measurability; data-access simplicity; reversibility | These decide whether the outcome is *clean* |
| **×1** | identifiable beneficiary; reconciliation simplicity; capital required; founder hours; recurring revenue; proof-to-settlement leverage; defensibility; wedge-to-OS potential; doctrine fit | Real, but they matter at venture two, not at outcome one |

**The weighting encodes a judgment worth stating plainly: for CVO-001,
*speed to a real payment* and *legal simplicity* dominate *defensibility* and
*compounding potential*.** A defensible compounding business that never reaches
its first paid outcome scores zero on the only metric that currently matters. If
the founder disagrees with that, the ranking changes and should be recomputed —
the weights are the argument, not the scores.

---

## 2. A. Candidate inventory

Every candidate found, including weak ones. Nothing omitted for being
unflattering.

| ID | Candidate | Type | Source |
|---|---|---|---|
| **C1** | **Agent/AI governance evidence service** — audit-grade decision records, consequence gating, and provenance for organizations deploying AI agents | software-enabled service | Kernel capabilities: `consequence_gate`, `evidence_ledger`, `commit_witness`, `machine_passports`, `autonomy_ladder` |
| **C2** | **Adversarial underwriting / diligence-as-a-service** — structured opportunity assessment with recorded reasoning and calibration | software-enabled service | `wealthmachine.adversarial_underwriting`, `decision_engine`, `risk_management` |
| **C3** | **Compliance evidence software** — productized proof capsules and reconciliation for regulated workflows | software product | Kernel `proof`, `provenance`, `evidence_ledger` |
| **C4** | **Trust rail for agent-to-agent transactions** — identity, passports, proof-to-settlement infrastructure | infrastructure / trust rail | PR #35 `proof-to-settlement-trust-rail`; `machine_passports`; `agent_embassy` |
| **C5** | **DALEOBANKS media and distribution** — owned audience, narrative production, context packets | media / distribution | `organs/daleobanks.manifest.yaml` |
| **C6** | **PumpStation** — Web3 trading/custody venture cell | Web3-native | PR #46 (proposal only, `INACTIVE`, `$0`, autonomy 0) |
| **C7** | **Foundry-as-a-service** — compose capability genomes into bespoke advantage for a client | software-enabled service | Final Build Order §10, `foundry`, `genome_registry` |
| **C8** | **Institutional workflow product** — durable workflows with exactly-once semantics and audit trails | software product | `events/spine.py`, Package 4 `DurableWorkflow` |
| **C9** | **Software integration / implementation services** — conventional contract engineering, founder-delivered | conventional cash business | Founder skill; no repository dependency |
| **C10** | **Fractional AI-governance consulting** — founder-delivered advisory, artifacts drawn from Kernel doctrine | conventional cash business | Founder skill + doctrine |
| **C11** | **Do nothing** — preserve capital, delay selection, continue internal work | — | — |
| C12 | *IVIO-NEMT* | — | **EXCLUDED — `PRESERVED_HISTORICAL / INACTIVE / NOT_SELECTED` by founder direction. Not scored, not ranked, not recommended.** |

### Weak candidates, recorded rather than hidden

- **C6 PumpStation.** Requires trading, custody, or token mechanics — every one
  of which is a prohibited consequence class today (`SETTLEMENT`,
  `BLOCKCHAIN_EXECUTION`, `SPENDING`). Its own proposal PR sets capital
  authorization to `$0` and autonomy to `0`. It cannot produce a CVO under any
  currently permitted action. Retained as the required Web3-native option and
  scored honestly.
- **C5 DALEOBANKS.** Depends on live platform credentials (X/LinkedIn/Mastodon)
  which are external dependencies, and its lane policy hard-prohibits the
  engagement tactics that make media monetize quickly. Audience-building is a
  6–18 month path to revenue. Real, but not a first-CVO instrument.
- **C8 Institutional workflow product.** The technology is genuine (Package 4
  proved exactly-once through the canonical runtime). But Temporal, Airflow,
  Step Functions and Camunda are mature, free-to-start, and better documented.
  Selling against them with a one-author implementation is a losing wedge.

---

## 3. Scoring

Raw scores, 1–10. Low scores shown.

| # | Criterion | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 | C10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | identifiable buyer | 7 | 6 | 7 | 3 | 3 | 2 | 4 | 5 | 9 | 8 |
| 2 | identifiable beneficiary | 7 | 6 | 8 | 4 | 5 | 2 | 5 | 6 | 8 | 7 |
| 3 | painful recurring problem | 8 | 5 | 8 | 4 | 4 | 3 | 4 | 5 | 8 | 7 |
| 4 | budget proximity | 6 | 5 | 7 | 2 | 2 | 1 | 3 | 4 | 9 | 7 |
| 5 | **time to first paid outcome** | 5 | 6 | 4 | 1 | 2 | 1 | 3 | 3 | **9** | **8** |
| 6 | **legal simplicity** | 7 | 8 | 5 | 2 | 6 | **1** | 7 | 7 | **9** | **8** |
| 7 | data-access simplicity | 5 | 7 | 3 | 4 | 6 | 3 | 6 | 6 | 7 | 8 |
| 8 | **founder access to customers** | 4 | 4 | 3 | 2 | 5 | 2 | 3 | 3 | **8** | 6 |
| 9 | accepted deliverable clarity | 6 | 7 | 6 | 3 | 4 | 2 | 3 | 5 | 9 | 7 |
| 10 | external outcome measurability | 7 | 6 | 7 | 5 | 4 | 6 | 4 | 6 | 8 | 6 |
| 11 | reconciliation simplicity | 7 | 8 | 6 | 3 | 5 | 4 | 5 | 6 | 9 | 8 |
| 12 | capital required *(10 = none)* | 8 | 9 | 7 | 3 | 6 | 2 | 7 | 7 | 10 | 10 |
| 13 | founder hours *(10 = few)* | 5 | 6 | 4 | 2 | 3 | 3 | 4 | 4 | 3 | 5 |
| 14 | reversibility | 8 | 9 | 7 | 4 | 6 | 2 | 7 | 7 | 9 | 9 |
| 15 | **downside containment** | 7 | 9 | 6 | 3 | 6 | **1** | 7 | 7 | **9** | **9** |
| 16 | recurring revenue potential | 8 | 5 | 8 | 7 | 6 | 5 | 4 | 7 | 4 | 5 |
| 17 | proof-to-settlement leverage | 9 | 6 | 8 | 9 | 3 | 5 | 6 | 6 | 2 | 4 |
| 18 | defensibility | 7 | 5 | 6 | 8 | 5 | 3 | 6 | 4 | 2 | 3 |
| 19 | wedge-to-OS potential | 9 | 6 | 7 | 9 | 6 | 4 | 7 | 6 | 3 | 6 |
| 20 | doctrine fit | 9 | 8 | 8 | 9 | 6 | 3 | 8 | 6 | 4 | 7 |

### Weighted totals

| Rank | Candidate | Weighted | Raw |
|---|---|---|---|
| **1** | **C9** Software integration / implementation services | **268** | 139 |
| **2** | **C10** Fractional AI-governance consulting | **252** | 138 |
| **3** | **C1** Agent/AI governance evidence service | **232** | 139 |
| **4** | **C2** Adversarial underwriting service | **230** | 131 |
| **5** | **C3** Compliance evidence software | **206** | 125 |
| 6 | C8 Institutional workflow product | 188 | 110 |
| 7 | C7 Foundry-as-a-service | 174 | 103 |
| 8 | C5 DALEOBANKS media | 160 | 93 |
| 9 | C4 Trust rail | 128 | 87 |
| 10 | C6 PumpStation | 84 | 55 |

*Totals recomputed from the raw table and the §1 weights. An earlier draft of
this document carried arithmetic that did not survive recomputation; the values
above are the checked ones, and the correction changed the order of C7 and C8.*

**Note the divergence between weighted and raw — it is the finding of this
document.** C9 and C1 have **identical raw totals (139 each)**. C9 wins by 36
weighted points, and **30 of those 36 come from exactly three criteria** —
5 (time to first paid outcome), 6 (legal simplicity) and 8 (founder access to
customers), where C9 scores 9/9/8 against C1's 5/7/4, each at ×3.

**C1 is plausibly the better *business*. C9 is the better *first outcome*.**
Collapsing that distinction would be the error. So would over-reading the gap:
36 points on identical raw totals is a narrow result that rests entirely on
three estimates, and those three are the least reliable numbers in the table.

---

## 4. B. Top-five ranking, with adversarial interrogation

### 1. C9 — Software integration / implementation services

*Conventional contract engineering or AI-integration work, delivered personally
by Alfonso under a simple services agreement.*

| Question | Answer |
|---|---|
| Who pays? | A company with a named budget holder — engineering or ops leader |
| Why now? | Backlog and hiring cost; contract work is the standing solution |
| Proof accepted? | Working software, merged code, a passing acceptance test |
| What changes? | A capability the buyer lacked now exists; money moves |
| Reachable in 7 days? | **Yes** — the only candidate where this is plainly true |
| Regulatory barrier? | Essentially none; a standard services agreement |
| Data required? | Whatever the client grants; can be scoped to non-sensitive |
| Liability? | Ordinary professional liability, bounded by contract |
| Ordinary software cheaper? | **This *is* ordinary software.** No claim of novelty |
| Speculative tech? | No |
| Hidden burden? | **Yes — it consumes the founder's hours, the scarcest input** |
| Compounding rail? | **No. It is a service company.** Honest answer |
| Falsifier? | No buyer responds in 14 days, or the rate is below opportunity cost |
| Fastest signal? | A paid scoping engagement — small, bounded, real money |

### 2. C10 — Fractional AI-governance consulting

*Advisory on agent governance, approval design, and evidence standards, using
the doctrine as the artifact.*

| Question | Answer |
|---|---|
| Who pays? | A company deploying AI agents without a governance model |
| Why now? | Agent deployment is outrunning controls; the pain is current |
| Proof accepted? | A written governance assessment; a policy they adopt |
| What changes? | Buyer's control posture changes; money moves |
| Reachable in 7 days? | Plausibly — narrower network than C9 |
| Regulatory barrier? | None for advisory. **Do not stray into legal advice** |
| Data required? | Minimal; can be entirely non-sensitive |
| Liability? | Advisory liability; manageable with scope limits |
| Ordinary software cheaper? | Not applicable — it is judgment, not software |
| Speculative tech? | No |
| Hidden burden? | Positioning credibility with no public track record |
| Compounding rail? | **Weakly.** Each engagement is a genuine input into C1 |
| Falsifier? | Three qualified conversations produce no budget |
| Fastest signal? | A paid governance assessment, fixed fee, one week |

### 3. C1 — Agent/AI governance evidence service

*Audit-grade decision records, consequence gating, provenance for organizations
running AI agents. The Kernel's actual capability, sold.*

| Question | Answer |
|---|---|
| Who pays? | Compliance, risk, or platform owner at a company deploying agents |
| Why now? | Agent autonomy is expanding faster than auditability |
| Proof accepted? | An auditor or regulator accepting the evidence artifact — **unvalidated** |
| What changes? | Buyer can demonstrate control they previously could not |
| Reachable in 7 days? | **Unlikely.** Enterprise compliance buying is slow |
| Regulatory barrier? | Indirect but real — the product's value depends on standards |
| Data required? | The buyer's agent decision logs — potentially sensitive |
| Liability? | **Significant.** Selling evidence that must withstand scrutiny |
| Ordinary software cheaper? | Partly — logging plus a SIEM covers some of it |
| Speculative tech? | No, but it depends on a market that is still forming |
| Hidden burden? | Enterprise sales cycle; security review; procurement |
| Compounding rail? | **Yes — the strongest of any candidate.** Genuine rail |
| Falsifier? | No compliance buyer will pay before a regulation names the requirement |
| Fastest signal? | A paid design partnership — but realistically 60–90 days |

### 4. C2 — Adversarial underwriting / diligence-as-a-service

| Question | Answer |
|---|---|
| Who pays? | Angel investor, small fund, or corp-dev evaluating opportunities |
| Why now? | Diligence is expensive; adversarial structure is differentiating |
| Proof accepted? | A written assessment they act on |
| Reachable in 7 days? | Possibly, if the founder's network includes investors |
| Regulatory barrier? | **Must not become investment advice.** Real constraint |
| Compounding rail? | Weak — a service with reusable structure |
| Falsifier? | Investors treat diligence as in-house and unpurchasable |
| Fastest signal? | One paid assessment at a fixed fee |

### 5. C3 — Compliance evidence software

| Question | Answer |
|---|---|
| Who pays? | Regulated-industry compliance function |
| Why now? | Audit burden is permanent and growing |
| Proof accepted? | A passed audit — **long feedback loop, possibly annual** |
| Reachable in 7 days? | No |
| Regulatory barrier? | High; the product lives inside regulated processes |
| Compounding rail? | Yes, but slowly |
| Falsifier? | Incumbents already own the workflow |
| Fastest signal? | Paid pilot, 90+ days |

---

## 5. C. Strongest conventional baseline

**Alfonso sells his own engineering or advisory time under a plain services
agreement, delivers manually, invoices, and gets paid.**

No platform. No Kernel dependency. No venture cell. No company formation beyond
what invoicing requires. A laptop, an agreement template, and an invoice.

This baseline satisfies all nine CVO conditions on its own: real counterparty,
bounded deliverable, real payment, independently checkable result (the client
confirms delivery), closed reconciliation (invoice paid), attributable legal
operator, no authority violation, no participant harm, nothing simulated.

**Every platform candidate must beat this, and at CVO-001 none of them do.** The
baseline's weakness is that it does not compound — which is a real objection to
it as a *strategy* and no objection at all to it as a *first outcome*.

---

## 6. D. Recommended CVO-001 candidate

**Recommendation: C9 — a bounded, paid software integration or AI-implementation
engagement, delivered personally by Alfonso, with the Kernel used only to
*witness* the outcome.**

Selected on the evidence, not on preference. The evidence is that CVO-001 is
gated by *access to a paying counterparty*, and C9 is the only candidate where
the founder can plausibly reach one inside a week.

| Field | Specification |
|---|---|
| **Exact buyer** | A named engineering or operations leader with discretionary budget, in Alfonso's existing network. **The specific name is a founder input — this document cannot supply it, and inventing one would violate condition 9.** |
| **Exact offer** | A fixed-scope, fixed-fee engagement: one clearly defined deliverable, completed within two weeks |
| **Exact deliverable** | Working software or a completed integration, accepted against a written acceptance criterion agreed before work starts |
| **Price hypothesis** | **$2,000–$7,500** fixed fee. Deliberately small: large enough to be real money and require genuine approval, small enough to clear without procurement. **A hypothesis, not a validated price.** |
| **Exact external result** | Buyer confirms acceptance in writing **and** the payment settles into an account attributable to a real legal operator |
| **Exact reconciliation rule** | CVO closes when **all three** hold: (a) written acceptance referencing the pre-agreed criterion; (b) payment cleared and observable in a statement; (c) a Kernel outcome record whose evidence references (a) and (b). **Missing any one leaves it open — no partial credit** |
| **Exact seven-day action** | Days 1–2: founder names three candidate buyers and one deliverable each. Day 3: write the acceptance criterion and reconciliation rule **before** contact. Day 4: founder decision gate (§8). Days 5–7: contact **only if `APPROVE_CVO_001_VALIDATION` is given** |
| **Founder authority required** | `EXTERNAL_CONTACT` grant naming target, channel, content class and duration; a legal operator able to contract and invoice; `SPENDING`/receiving authority for the account; ratification of the reconciliation rule **in advance** |
| **Kill condition** | **K1** no written acceptance criterion agreed before work begins. **K2** no payment cleared within 30 days of acceptance. **K3** the only available "outcome" is founder-attested — a VMEE, not a CVO. **K4** delivery requires a consequence class not granted. **K5** the Ordering Guard is not in place when `EXTERNAL_CONTACT` becomes due. **K6** the engagement expands beyond fixed scope — scope creep converts a bounded first outcome into an unbounded obligation |

### What this recommendation deliberately gives up

C9 is **not** a compounding rail, and this document does not pretend otherwise.
It scores 2/10 on defensibility and 3/10 on wedge-to-OS potential. It is
recommended precisely because CVO-001 is not a strategy decision — **it is proof
that the institution can produce a real, clean, externally verified outcome at
all.**

The strategic sequence: **C9 produces CVO-001. C10 is the natural second
engagement and begins building governance credibility. C1 is the actual
business** — and by Bridge G, the Capability Genome extracted from CVO-001
transfers to it. Selecting C9 first does not choose against C1; it removes the
excuse that the institution has never closed a loop.

---

## 7. E. Do-nothing verdict

**The do-nothing option is NOT stronger, but it is closer than the ranking
suggests, and it wins outright on one condition.**

**Why do-nothing loses.** The architectural phase closed with zero Clean
Verified Outcomes. Every subsequent internal package increases the amount of
unvalidated machinery. There is no internal work remaining whose absence blocks
CVO-001 — §9's blockers are legal decisions and authorizations, not code.
Delaying does not de-risk; it accumulates. Capital preservation is not the
binding constraint, because C9 requires approximately **zero capital**.

**Where do-nothing wins.** If the founder cannot commit sustained hours to
delivery, do-nothing is strictly better than a half-delivered engagement. A
failed first engagement is worse than no first engagement: it produces a real
counterparty with a real grievance, and condition 8 — no material participant
harm — would be violated by the institution's first external act.

**Verdict: proceed with C9, conditional on the founder confirming capacity to
deliver.** If that capacity is absent, `PAUSE_VENTURE_SELECTION` is the correct
choice and is not a failure.

---

## 8. Protocol review of the recommendation

**Builder.** C9 converts the only real blocker — buyer access — into the
selection criterion. Zero capital, days not quarters, all nine conditions
satisfiable.

**Adversary.** This is not a venture. It is Alfonso freelancing while the Kernel
watches. It proves the founder can sell his time, which was never in doubt, and
proves almost nothing about the institution. Worse, it risks the founder
mistaking a consulting income for validated strategy and never returning to C1.

**Operator.** Delivery consumes the scarcest resource — founder hours — with no
leverage. Two weeks of delivery is two weeks of no institutional development.

**Beneficiary representative.** The buyer gets working software they wanted at a
price they agreed. Low harm potential, bounded scope, no sensitive data
required. **Of all candidates this has the cleanest participant story** — C1 and
C3 involve buyers relying on evidence artifacts whose external acceptance is
unproven.

**Constitutional reviewer.** Admissible only with a real legal operator.
`UNIIMENTE` may never be the contracting party — the registry marks it
`not_a_legal_actor / prohibited`. `IVIO_NEMT_LLC` is unavailable (unconfirmed
jurisdiction, and now `NOT_SELECTED`). **The contracting entity is therefore
Alfonso personally or a new entity — a founder-reserved decision and a hard
blocker.**

### Alternatives

| # | Option | Verdict |
|---|---|---|
| 1 | **Strongest proposed** — C9 fixed-fee engagement | fastest credible path to all nine conditions |
| 2 | **Simplest viable** — a single paid scoping call, $250–500, one hour | satisfies all nine at minimal scale; proves the loop closes; almost no delivery risk |
| 3 | **Strongest conventional competitor** — Alfonso takes a contract through an existing marketplace or agency | fastest of all; buyer access solved by the intermediary; margin and relationship ownership sacrificed |
| 4 | **Reversible experiment** — C10 paid governance assessment, fixed fee, one week | tests the governance thesis *and* closes a CVO; smaller delivery surface than C9 |
| 5 | **Do nothing** | see §7 |

### Upward pass 1

| Disadvantage | Treatment |
|---|---|
| Consumes founder hours with no leverage (Operator) | **Bound**: fixed scope, fixed fee, two-week cap; K6 kills on scope creep |
| Proves nothing institutional (Adversary) | **Convert**: mandate a Capability Genome extracted from the engagement, per Bridge G. The *pathway* is the institutional output, not the code |
| Founder mistakes consulting for strategy (Adversary) | **Observe**: CVO-001 is explicitly labelled a proof of loop-closure, not a strategy selection. C1 remains the stated business |
| No legal operator (Constitutional reviewer) | **Escalate**: hard blocker, §9 item 1. Cannot be treated |
| Failed delivery harms a real counterparty (§7) | **Reverse**: alternative 2 — shrink to a one-hour paid scoping call. Delivery risk approaches zero and all nine conditions still hold |
| Buyer name cannot be supplied here | **Escalate**: founder input; inventing one violates condition 9 |

**Strengthened recommendation: C9 with alternative 2 as the entry point.** Begin
with a **paid scoping engagement** — one hour, $250–500, written summary
delivered. It satisfies all nine CVO conditions at the smallest possible scale,
carries near-zero delivery risk, and either converts into the fixed-fee
engagement or ends cleanly having already closed CVO-001.

### Upward pass 2 — attack the strengthened design

1. **Is a $250 scoping call a "real" CVO, or a technicality?** It satisfies all
   nine conditions literally. But if the intent is to prove the institution can
   produce economically meaningful outcomes, $250 proves the *mechanism* and not
   the *magnitude*. *Response:* accepted and recorded. CVO-001 should be
   explicitly labelled a **mechanism proof**. Magnitude is CVO-002's job. What
   must not happen is the $250 being reported as evidence of commercial
   viability.
2. **Does anyone pay for a scoping call?** Many buyers expect scoping free.
   *Response:* real, and it is precisely the test. A buyer unwilling to pay
   anything is a buyer, and payment resistance at $250 is a strong early signal
   about the whole thesis.
3. **Does this bypass the Ordering Guard prerequisite?** No. `EXTERNAL_CONTACT`
   is required regardless of engagement size. K5 stands at any price.
4. **Does starting small train the institution to stay small?** Genuine risk. A
   sequence of tiny engagements can substitute for building C1. *Response:*
   bound it — **CVO-002 must be materially larger or structurally different, or
   the wedge is failing.**
5. **Is the ranking itself an artifact of the weights?** Yes, and stated in §1.
   With defensibility and compounding weighted ×3 instead, C1 wins. **The weights
   are the real decision and belong to the founder**, which is why they are
   listed as a founder-reserved item.

---

## 9. F. Preserved dissent — the strongest objection to C9

**The strongest objection is the Adversary's: C9 is not a venture, and selecting
it may be a category error.**

CVO-001 was framed as venture selection. C9 is not a venture — it is the founder
selling labour. Choosing it means the institution's first verified outcome
demonstrates nothing the institution does. Every one of C9's nine conditions
would be satisfied identically if the Kernel did not exist. The Kernel is a
*witness*, not a participant.

A serious reading of this objection says: **select C1, accept 60–90 days, and
produce a first outcome that actually exercises the institution.** The evidence
would then mean something. A CVO that any freelancer could produce is a CVO that
says nothing about whether the architecture was worth building.

**Why it does not currently change the recommendation.** The counter is not that
the objection is wrong — it is that C1 has never been tested against a buyer at
all. Its proof-acceptance row reads *unvalidated*, its 7-day-reach row reads
*unlikely*, and its entire commercial thesis rests on a market that is still
forming. Selecting C1 as CVO-001 risks 90 days producing a *second* zero. The
institution has had enough unvalidated machinery; what it lacks is one closed
loop of any kind.

**What would change the decision.** If the founder already has a warm compliance
or risk buyer for C1, the calculus inverts immediately — C1's fatal weakness is
buyer access, and a warm buyer removes it. That fact is known only to the
founder. **If it exists, C1 should be selected instead**, and this
recommendation should be discarded without ceremony.

**Second preserved objection.** The scoring is one author's judgment presented in
a table. Numeric scores confer an appearance of rigour that the underlying
evidence does not support. The weighted totals are arithmetic performed on
estimates. They should be read as *a structured argument*, not a measurement —
and the 36-point gap between C9 and C1 — on **identical** raw totals — rests
almost entirely on three estimates (criteria 5, 6, 8) that no one has tested
against a real buyer.

---

## 10. Part 4 — Selection is not activation

**Selected candidate status: `PROPOSED_NOT_EXECUTED`.**

This document does **not** authorize: company formation · deployment · sales
contact · email · social posting · spending · payment collection · real-world
data processing · wallet creation · token launch · smart-contract deployment ·
settlement · customer onboarding.

### Founder decision gate

Choose exactly one:

| Choice | Meaning |
|---|---|
| **`APPROVE_CVO_001_VALIDATION`** | Proceed with C9, entering via the paid scoping engagement. Requires the §9 blockers resolved first |
| **`RETURN_CVO_001_FOR_REVISION`** | The candidate is right, the specification is not. State exactly what must change |
| **`REJECT_CVO_001_CANDIDATE`** | C9 is wrong. Selection returns to the ranking |
| **`SELECT_DIFFERENT_CANDIDATE`** | Name it. **If a warm C1 buyer exists, this is the correct choice** |
| **`PAUSE_VENTURE_SELECTION`** | Preserve capital and hours; revisit later. Correct if delivery capacity is uncertain (§7) |

### Blockers requiring founder resolution before any validation action

1. **Legal operator.** `UNIIMENTE` may never contract (`not_a_legal_actor /
   prohibited`). `IVIO_NEMT_LLC` is unavailable. **Alfonso personally, or a new
   entity — this is a hard blocker and cannot be worked around.**
2. **Buyer identity.** Three named candidates. Cannot be supplied by this session.
3. **`EXTERNAL_CONTACT` authority** — target, channel, content class, duration.
4. **Payment/receiving authority** — account and tax treatment.
5. **Reconciliation rule ratified in advance** — before contact, per §6.
6. **Ordering Guard prerequisite** — confirm K5 binds `EXTERNAL_CONTACT`.
7. **Delivery capacity** — confirm hours are genuinely available (§7).
8. **The weights in §1** — the founder owns them, and they decide the ranking.

---

## 11. IVIO exclusion — recorded

IVIO-NEMT was **excluded from active consideration** throughout this document,
per founder direction of 2026-07-27. It is not scored, not ranked, not
recommended, and not revived.

All IVIO material is **preserved**: `ventures/ivio_nemt/` (code, fixtures,
`LINEAGE.md`), the `IVIO_NEMT_LLC` legal-principal entry, PR #45, and
`docs/operations/CVO_001_READINESS_PACKET.md` — the last now carrying a
`SUPERSEDED` banner rather than deletion.

Status: **`PRESERVED_HISTORICAL / INACTIVE / NOT_SELECTED`.**

The analytical content of the IVIO packet survives and is reused here: the
finding that its commercial model was entirely fixture data directly informed
§1's warning about scoring rigour, and its kill condition K5 became K3 in §6.
**A rejected candidate that produced reusable analysis is exactly what the
preservation doctrine is for.**
