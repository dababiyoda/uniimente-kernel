# Venture Cell Spider-Web Record: proof-of-delivery acceptance for small freight brokers

Deliverables E (Spider-Web part) and I. Status: **PROPOSAL**. Nothing here is a business, a customer, a transaction or a revenue figure. No broker, shipper, carrier or factor was contacted. The origin signal is a FIXTURE written into the ten-step proof; it was processed by the real organ code. The `@spider-web-hegemony` skill was not invoked in this session; its discipline from master prompt sections 8 and 14 was applied by hand.

## 1. Origin and evidence tier

| Stage | What ran | Result | Tier |
|---|---|---|---|
| Signal | Ten-step proof step 6 fixture: "Small freight brokers lose invoices because proof of delivery arrives as photos nobody can verify. According to the broker, chargebacks take 40 days." | Operator thought, not field evidence | FIXTURE |
| DALEOBANKS | Real `build_packet` (DALEOBANKS `667439f`) produced an OpportunityPacket 1.1 with risk flag "evidence_needed: claims without a cited source" | Signed, verified at the kernel on one mission trace | Real organ code, sandbox |
| WealthMachine | Real assessment (WMI `ec82b80`) | `go_no_go: go`, `opportunity_score: 0.72`, `market_alignment: 0.49`, `risk_level: low`; bear case "demand asserted, not shown"; `recommended_next_action: validate`; `requires_human_approval: true` | Real organ code, sandbox |
| Validation step | WMI's plan: "Find one independent source for: According to the broker, chargebacks take 40 days." Desk research on 2026-10-15 | Partial. Payment cycles of roughly 33 to 45 days, gated on a complete invoice with signed proof of delivery, appear consistently, but in vendor guides ([O Trucking](https://otrucking.com/resources/guides/broker-days-to-pay-explained/), [Peakflo](https://peakflo.co/blog/proof-of-delivery-capture-billing-evidence-chain)) and one survey report ([DC Velocity](https://www.dcvelocity.com/editorial/featured/report-freight-markets-turn-a-corner): 48% of brokers report shippers paying in three to four weeks, 30% a month or more, 79% using factoring) whose sample and date were not confirmed. No independent source for the 40-day chargeback figure or for the share of disputes caused by unverifiable proof of delivery | Directional external evidence |

The organ verdict is "validate", not "build". This record says what validation would have to show.

## 2. The cell

| Field | Definition | Status |
|---|---|---|
| Actor | A small freight brokerage | Hypothesis |
| Recurring transaction | Every delivered load: carrier invoices broker; broker bills shipper; payment is released on a complete invoice with signed proof of delivery | Supported directionally (section 1) |
| Buyer | The broker's owner or controller | Hypothesis |
| Payer | The broker, per accepted proof packet. Alternative payer: the factor, which carries the risk of an unverifiable delivery | Hypothesis |
| Pain and mandate owner | Broker accounts receivable; the carrier waits for its pay | Hypothesis |
| Beneficiaries | Carriers (faster pay), brokers (shorter collection, fewer disputes), shippers (fewer disputes to work) | Hypothesis |
| Accepted artifact | A proof-of-delivery packet the payer accepts without dispute: receiver signature, time and place of capture, matched to the bill of lading and rate confirmation, with a digest anyone can re-check | Designed, not built |
| Verifier | The shipper's accounts payable (accepts or disputes) and the factor's underwriter; the three-way match is their existing check ([Ash Conversions](https://www.ashconversions.com/blog/logistics-document-management/freight-invoice-bill-of-lading-and-proof-of-delivery-how-the-three-way-match-reduces-billing-disputes/)) | External; not engaged |
| Money flow | A per-load fee for an accepted packet. GREG never holds, advances or moves money | Hypothesis |
| Capital needs | Software only. Advancing money would make it factoring, which is excluded | Bounded |
| Liabilities | Location and signature data of drivers and receivers; liability for a falsified packet; contract disputes | Named, not priced |
| Exclusions | No advance of funds; no token; no tracking of drivers outside consented capture at delivery; no contact with any party without founder authorization | Fixed |
| Cheapest falsification test | With founder authorization, five brokers share their last twenty disputed or delayed invoices. If fewer than one in five turn on proof of delivery, kill the cell | Not run: needs founder authorization to contact anyone |

## 3. Unit economics, as formulas with unknowns marked

No number below is a measurement.

```text
value per load to the broker  =  invoice_amount x (days_saved / 365) x cost_of_capital
                                 + P(dispute | today) x (dispute_loss + dispute_handling_cost)
                                 - P(dispute | packet) x (dispute_loss + dispute_handling_cost)
fee ceiling                   <  value per load to the broker
cell gross margin             =  fee - capture_and_storage_cost - verification_cost
```

Unknowns: `days_saved`, `P(dispute | today)`, `P(dispute | packet)`, `dispute_loss`, `dispute_handling_cost`, the broker's `cost_of_capital`. Known only directionally: today's payment cycle (33 to 45 days, section 1). Gross revenue, net revenue, realized profit, participant distribution, reserves and financing cost are all zero today because there is no transaction.

## 4. Eight sides

| Side | Finding | Design response |
|---|---|---|
| 1. Failure geometry | Payment waits on a document; a photo nobody can verify starts a dispute | Make the packet the thing the payer already checks, with a re-checkable digest |
| 2. Participant and power geometry | Shippers hold the money and the right to dispute; carriers are the weakest party; factors price the risk | The carrier and broker gain only if the shipper accepts; design for the payer's acceptance first |
| 3. Eligibility and permission | Who may issue a packet (the carrier at delivery) and who may accept it (the shipper's payables) | Carrier identity checked against public operating authority records; acceptance stays the shipper's act |
| 4. Default routing | Today packets travel by email and portal | Route the packet into the payer's existing three-way match, never a new portal it must adopt |
| 5. Proof, truth, reputation | Capture can be faked; a digest proves integrity, not truth | Signature plus time and place at capture, matched to the bill of lading; disputes and their outcomes kept as evidence about each issuer |
| 6. Settlement and capital physics | Payment release belongs to the shipper; factoring advances money at a discount | Shorten the release time; never advance money |
| 7. Distribution and counter-position | Electronic proof-of-delivery features already exist in transportation software (the vendor articles in section 1 sell them) | Counter-position on acceptance by the payer, not on capture: incumbents sell capture to carriers and brokers; the cell must be paid only when a payer accepts |
| 8. Reliability, governance, regeneration | A wrong acceptance moves real money | Every acceptance and dispute is a retained record; the cell's own error rate is published to its participants |

## 5. Four control supernodes

```text
Eligibility (carrier authority, broker authority, receiver signature)
  -> Routing (the packet enters the payer's existing three-way match)
  -> Proof/Truth (capture attestations + document match + dispute history)
  -> Settlement (the payer releases payment; GREG and the cell never touch the money)
```

No supernode is claimed as a standard or a non-bypassable rail. That claim needs an independent consequential actor, a shipper or factor, to accept packets as sufficient. None has.

## 6. Five outcomes

| Outcome | Metric | Evidence today |
|---|---|---|
| Commercial | Accepted packets per month; fee per accepted packet | None |
| Strategic | Share of a broker's loads routed through accepted packets | None |
| Regenerative | Days a carrier waits for pay, before and after | None |
| Institutional | Disputes per thousand loads, before and after, measured by the payer | None |
| Capital | Days of receivables freed for the broker | None |

## 7. Nine event-level adversaries

| Adversary | Attack | Response |
|---|---|---|
| Incumbent bundling | A transportation-software vendor bundles capture for free | The cell is paid on acceptance, not capture; if the bundle gets equal acceptance, the cell should not exist |
| Venture-funded copy | A funded copy prices below cost | No capital moat claimed; the durable asset is the payer's acceptance record, which a copy must earn again |
| Regulatory response | Location and signature data rules tighten | Capture only at delivery with consent; data minimized to what the payer checks |
| Buyer multi-homing | Brokers use several tools | Accept that; route into the payer's match regardless of which tool captured |
| Supplier coalition | Carriers refuse another app | Carriers capture with what they already use; the cell verifies and routes |
| Capital shock | Freight downturn stretches payments | Value per load rises when payment slows; no balance-sheet exposure because no money is advanced |
| Technology commoditization | Capture and signing become free everywhere | Expected; the cell's value is acceptance and dispute evidence |
| Security, scandal, litigation | A forged packet is accepted | Each packet keeps its capture attestations; a forged packet is traceable to its issuer; the cell's liability is named before any pilot |
| Founder failure | The founder stops | Records and keys follow the constitution's succession path; no participant's money is held, so nothing is stranded |

## 8. Actor-perspective audit

| Actor | Question they would ask | Current answer |
|---|---|---|
| Buyer CFO | How many days of receivables does it free, measured on my loads? | Unknown until a pilot |
| Regulator | Does it collect location or biometric data beyond need? | Designed not to; untested |
| Auditor | Can I re-check an acceptance later? | Yes by design: digest, capture attestations, document match |
| Insurer | Who pays for a forged packet that was accepted? | Not decided; must be before any pilot |
| Worker (driver) | Am I tracked? | Only at delivery, with consent |
| Privacy and security expert | Where are signatures stored and who can read them? | Not built |
| Skeptical customer | My TMS already does this | Then the test in section 2 should kill the cell |
| Successor | Can someone else run it without the founder? | Only after the governance path for succession exists |
| Critic | Is this a demand claim with no demand evidence? | Yes, today. The organ said so ("demand asserted, not shown") |

## 9. Two strengthening passes

**Pass 1, structural inversion.** The advantage is not capture, which incumbents sell, but acceptance by the payer, which nobody can buy outright. Converted: price per accepted packet, so the cell earns only when the payer's behaviour changes. The disadvantage, no demand evidence, becomes the gate: the falsification test in section 2 runs before any build.

**Pass 2, adversarial compounding.** Pricing per acceptance invites gaming: a broker and a friendly shipper could inflate acceptances. Response: acceptance counts only from payers that are not affiliated with the issuer, and disputes after acceptance reverse the fee. A new concentration risk appears: a few large payers decide everything. Accepted as a named risk; the cell does not claim a rail until independent payers accept.

**Dissent preserved.** The strongest case against the cell: the problem may be payment-term leverage by shippers, not proof quality. If so, better proof changes nothing and the cell dies at the falsification test. This record does not resolve that; only field evidence can.

**Legitimacy check.** The design depends on no coercion, no surveillance beyond consented capture, no deception and no bypass of anyone's authority. It passes on paper.

## 10. Decision

`NEEDS_FOUNDER_DECISION`. Payload: whether to authorize the falsification test (contacting five brokers under a founder-approved script). Safe default: desk research only; no contact, no build, no spend. The cell is one of several candidates; the PumpStation venture shape remains a separate founder decision.

## 11. The governed commerce loop it would run on

`greg rehearse` runs the existing FIXTURE commerce loop (`greg/venture_rehearsal.py`): charter, offer, a fixture buyer's signed order, delivery, signed acceptance bound to the delivery receipt, and books that balance to the cent, with `money_moved` false. Its run on this branch is recorded in `docs/evidence/one-machine-ten-steps/2026-10-15/rehearse.json`. It shows the pieces cooperate on a transaction; it is not evidence that anyone would buy.
