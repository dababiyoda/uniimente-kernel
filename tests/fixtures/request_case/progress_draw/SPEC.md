# SPEC: progress-payment draw eligibility (sandbox case 2)

**SYNTHETIC — not a real party.** This specification and every case folder beside it are invented sandbox material. The contract, the companies, the inspector, the amounts and the dates do not describe any real person, company, contract or payment. Every case is synthetic and labelled by hand.

Written on 2026-11-12 as withheld test material for a transfer measurement. Its sources are the founder's requirement of 2026-11-12 and the pre-registered description of this case. No implementation of the operational path was read. The rules are stated in words only.

Founder's requirement, verbatim: "Incoming request → evidence extraction → missing-information detection → eligibility assessment → appropriate routing → completion evidence → acceptance → settlement reconciliation → retained learning." "Unreadable evidence remains unknown until reconciled." An unknown is never a pass or a fail.

## 1. The case

A masonry subcontractor asks the general contractor for a progress payment (a "draw") under a subcontract. The general contractor is the payer. For each request the payer decides whether the draw may be paid and routes it. Later it confirms the payment against a settlement statement.

| Founder's path | In this case |
|---|---|
| Incoming request | The pay application for this draw. |
| Evidence extraction | Reading the facts in section 3 from the documents in section 2. |
| Missing-information detection | Finding the facts a rule needs that are absent, empty or unreadable (section 5). |
| Eligibility assessment | Rules R1 to R9 (section 4), evaluated as in section 5. |
| Appropriate routing | Section 6. |
| Completion evidence | The inspection sign-off (work in place) and the lien waiver for the prior draw. |
| Acceptance | The payer's recorded decision that the draw is eligible, at the amount R5 establishes. |
| Settlement reconciliation | Finding the payment in the settlement statement (section 7). |
| Retained learning | Section 8. |

## 2. Documents in a case folder

| File | Document | Produced by |
|---|---|---|
| schedule_of_values.txt | Schedule of values: contract reference, each line item with its scheduled value, the retainage percent, and each change order with its amount and approval (yes or no). | The contract file. |
| pay_application.txt | Pay application for this draw: contract reference, draw number, period end date, each line's percent complete to date and previously billed amount, retainage withheld and amount requested. | Subcontractor. This is the incoming request. |
| inspection_signoff.txt | Inspection sign-off: contract reference, draw number or period, inspector name, date, observed percent complete for each inspected line, signed (yes or no), and open punch items with whether each is blocking. | Inspector. |
| lien_waiver_prior_draw.txt | Lien waiver for the prior draw: contract reference, draw number, amount waived, conditional or unconditional, signed (yes or no), date. | Subcontractor. |
| draw_register.txt | The payer's own register of the draws it received on this contract before the request under review. For each draw it shows the status (open, settled, declined or withdrawn), gross billed, net paid and dates. The request under review is not in it. | Payer. |
| statement.csv | Settlement statement, one row per outgoing payment: date, reference, amount, currency, memo. This file is optional. | The payer's bank. |

Documents are plain text: key: value lines plus free text. Any file may be absent, and a file that is present may be empty or unreadable. The first row of a statement may be a marker row with amount 0.00 that labels the file as synthetic. It is never a payment.

## 3. Facts and where they come from

Each fact is read only from the document named for it. It is never inferred from another document. Two examples:

- The retainage percent is not inferred from past draws in the register.
- A pay application's statement that a document is attached does not supply that document's facts.

A fact is needed only when the outcome of some rule depends on it.

| Fact | Source | Used by | Needed when |
|---|---|---|---|
| sov.contract_reference | Schedule of values | R2 | Always |
| sov.retainage_percent | Schedule of values | R5 | Always |
| sov.line[id].scheduled_value | Schedule of values | R5 | The pay application shows that line above 0 percent complete, or above 0.00 previously billed. |
| sov.change_order[id].amount | Schedule of values | R5 | As above, for an approved change-order line. Its amount is its scheduled value. |
| sov.change_order[id].approved | Schedule of values | R6 | The pay application shows that change-order line above 0 percent complete. |
| pay_app.contract_reference | Pay application | R2, R9 | Always |
| pay_app.draw_number | Pay application | R3, R9 | Always |
| pay_app.period_end_date | Pay application | R1, payment matching | Always |
| pay_app.line[id].percent_complete_to_date | Pay application | R4, R5, R6 | Every line listed |
| pay_app.line[id].previously_billed | Pay application | R5 | Every line listed |
| pay_app.retainage_withheld | Pay application | R5 | Always |
| pay_app.amount_requested | Pay application | R5, payment matching | Always |
| inspection.contract_reference | Inspection sign-off | R2 | Always |
| inspection.draw_or_period | Inspection sign-off | R1 | Always. It is satisfied by a draw number or a period end date. |
| inspection.signed | Inspection sign-off | R1 | Always |
| inspection.line[id].observed_percent_complete | Inspection sign-off | R4 | The pay application shows that line above 0 percent complete. |
| inspection.blocking_punch_items | Inspection sign-off | R8 | Always: whether any open punch item is marked blocking. |
| lien_waiver.contract_reference | Lien waiver, prior draw | R2 | The draw number is above 1. |
| lien_waiver.draw_number | Lien waiver, prior draw | R7 | The draw number is above 1. |
| lien_waiver.amount_waived | Lien waiver, prior draw | R7 | The draw number is above 1. |
| lien_waiver.signed | Lien waiver, prior draw | R7 | The draw number is above 1. |
| register.draw[n].status | Draw register | R3, R9 | Always |
| register.draw[n].gross_billed | Draw register | R5 | For draws before this one |
| register.draw[n].net_paid | Draw register | R7 | For the prior draw |
| statement rows | Settlement statement | Section 7 | Only for an eligible draw |

## 4. Eligibility rules

Here N is the draw number on the pay application.

**R1. Required documents.** The file holds all of the following:

- the schedule of values;
- the pay application for draw N;
- an inspection sign-off for draw N, meaning its draw number is N or its period end date equals the pay application's, and it is signed;
- for N above 1, a lien waiver for draw N−1;
- the payer's draw register.

A document that is absent, empty or unreadable leaves its facts unknown, so R1 is unknown, never failed: the payer asks for the document. An inspection sign-off that states signed: no is a known fact and fails R1. A sign-off that refers to a different draw is not the sign-off for this draw, so the facts of this draw's sign-off are unknown.

**R2. Contract reference agrees.** Every readable contract reference must be the same: on the schedule of values, the pay application, the inspection sign-off, the prior lien waiver and the register. Compare after trimming surrounding spaces and ignoring letter case. If any two readable references differ, R2 fails. A transposed digit or a one-character difference is still a difference. The payer does not guess which one was meant. A reference that is unknown leaves R2 unknown for that document.

**R3. Draw sequence.** The last paid draw is the highest draw number the register shows as settled, or 0 when none is settled. The draw number must be exactly one more than the last paid draw.

**R4. Percent complete is within what inspection observed.** The tolerance is 2 percentage points, measured in absolute points, not as a share of the figure. For every line the pay application shows above 0 percent complete, the percent complete to date must not exceed the inspection's observed percent for that line by more than 2 points. A billed figure equal to the observation plus 2 passes; plus 2.01 or more fails.

- A line billed at 0 percent passes without an observation.
- A line billed above 0 percent that the inspection does not list is unknown.

Inspection readings are coarse. Up to 2 points is reading error; beyond that the payer pays only for the work observed.

**R5. Amount arithmetic.** For each line on the pay application, take its scheduled value from the schedule of values.

- An original line uses its scheduled value.
- An approved change order uses its amount.
- A change order that is not approved, or a line the schedule does not list, counts as zero here (see R6).

Then compute, in this order:

1. **Value to date** = scheduled value × percent complete to date, rounded to the cent with halves rounded away from zero.
2. **Work this period** = value to date − previously billed.
3. **Gross this draw** = the sum of work this period over all lines.
4. **Retainage** = the schedule's retainage percent × gross this draw, rounded to the cent the same way.
5. **Net** = gross this draw − retainage.

Three conditions must all hold for R5 to pass:

- The amount requested equals the net within one cent.
- The retainage withheld stated on the pay application equals the computed retainage within one cent.
- The sum of previously billed over all lines equals the register's total gross billed for draws 1 to N−1 within one cent.

"Within one cent" means a difference of 0.01 or less passes and a difference above 0.01 fails. This is the founder's formulation: the sum over lines of (scheduled value × percent complete), minus previously billed, minus retainage at the stated percent. The retainage applies to this period's work, as the schedule of values states.

**R6. Unapproved change orders are excluded.** R6 fails when the pay application shows a line above 0 percent complete in either of two situations:

- the line is a change order that the schedule of values does not record as approved: yes (approved: no, pending, or not recorded);
- the schedule of values does not list the line at all.

When R6 fails, R5 normally fails too, because the excluded amount is still in the request. The decline names R6 as the cause and R5 as its consequence. The payer does not strike the line and pay the rest on its own initiative.

**R7. Prior draw lien waiver.** For N above 1, the lien waiver must meet all of the following:

- it refers to draw N−1;
- it states signed: yes;
- its amount waived equals the register's net paid for draw N−1, within one cent.

A waiver that states signed: no fails, and so does an amount that differs by more than one cent. The waiver type (conditional or unconditional) and the date are recorded but decide nothing in this sandbox.

**R8. No blocking punch item.** R8 fails if the inspection sign-off lists any open punch item marked blocking: yes. Open items marked blocking: no are allowed. An open item with no blocking mark is unknown.

**R9. Duplicate.** The request is a duplicate when the register already holds a draw with the same contract reference and the same draw number whose status is open or settled. A draw that is declined or withdrawn does not make a resubmission a duplicate.

The payer never pays a recomputed amount on its own initiative. A draw that fails a rule is declined, naming the rule, and the subcontractor may resubmit.

## 5. Unknowns, disputes, conflicts and precedence

Each rule has one of four outcomes: pass, fail, unknown or disputed.

**Unknown.** A fact is unknown in any of these cases:

- its document is absent;
- its document is empty;
- its document is unreadable;
- the document does not state the fact.

A document is unreadable when it cannot be read as text or yields none of its fields. Examples are binary content, an empty file, a corrupted encoding, or a banner line followed by garbage. Unreadable evidence stays unknown until a readable copy reconciles it.

A rule that needs an unknown fact, and that known facts have not already failed, is unknown. An unknown is never a pass and never a fail: an absent or unreadable value is never read as zero, blank, none, no or yes.

**Known "no".** A value that a readable document states, such as signed: no or approved: no, is a known fact, not an unknown.

**Conflict.** Readable documents that state different values for a fact that must agree (R2) are a known disagreement, and R2 fails. The payer reports both values and does not choose between them.

**Disputed.** A fact is disputed when a document records that a party contests it and does not record the dispute as resolved. A party is the owner, the owner's representative, the payer, the subcontractor or the inspector. An inspector's signature does not resolve a dispute the inspector records.

A rule whose outcome would differ between the recorded positions is disputed. A rule that passes under every recorded position, or fails under every one, is decided normally.

**Precedence:**

1. Check R9 first, using the pay application's contract reference and draw number. A duplicate is labelled duplicate, and no other rule is evaluated. If those two facts are unknown, the draw is undetermined and the payer asks for them.
2. Evaluate R1 to R8.
3. If any rule fails on known, undisputed facts, the draw is **ineligible**. The decline names every failed rule. Unknowns and disputes are reported but do not change the decision.
4. Otherwise, if any rule is disputed, the draw is **disputed**.
5. Otherwise, if any rule is unknown, the draw is **undetermined**.
6. Otherwise the draw is **eligible**.

## 6. Routing

| Eligibility | Route | What the route does |
|---|---|---|
| eligible | prepare_settlement_and_await_payment | Record acceptance and prepare a settlement for the amount requested, which R5 has shown equals the computed net within one cent. Then wait until the payment is observed (section 7). Preparing a settlement is neither a payment nor evidence of one. |
| undetermined | request_missing_facts | Ask for exactly the missing facts, each named as in section 3, with the document that should carry it and who can supply it. Ask for nothing already known, and leave out nothing a rule needs. |
| ineligible | decline_naming_failed_rules | Decline, naming each failed rule and the facts that failed it. For R5, give the computed amounts and the stated amounts. |
| disputed | hold_naming_dispute | Hold. Name the disputed fact, each party's recorded position and the rule that turns on it. No settlement is prepared until the dispute is resolved. |
| duplicate | refer_to_existing_draw | Open no second draw and prepare no second settlement. Name the existing draw by its number and status. |

## 7. Settlement reconciliation and payment status

A payment status is assigned only to an eligible draw.

A statement row is a candidate for this draw's payment when it meets all of the following:

- its currency is USD;
- its amount equals the settlement amount exactly, to the cent;
- its date is on or after the pay application's period end date;
- its memo or reference contains the contract reference;
- it does not name a different draw number.

| Payment status | When |
|---|---|
| paid | Exactly one candidate row. Record that row and mark the draw settled in the register at that net paid. |
| unknown-ambiguous | Two or more candidate rows. Choose none. Ask for the remittance advice that identifies the row that settles this draw, and flag a possible double payment. |
| unknown-no-statement | No statement is supplied, or a readable statement has no candidate row. The missing row is not proof of non-payment. Keep waiting. |
| unknown-unreadable | A statement is supplied but is empty or unreadable. Ask for a readable statement and keep waiting. |
| not-applicable | The draw is undetermined, ineligible, disputed or a duplicate, so no settlement was prepared. Statement rows are not matched to it, even when an amount looks right. |

Only a statement row is evidence of a payment. The word "approve" or "paid" in any document is not.

## 8. Retained learning

After each decision and each reconciliation, the payer keeps:

- the decision and the route;
- each rule's outcome and the facts that decided it;
- the facts asked for, and when they arrived;
- each dispute, every position in it and how it was resolved;
- the payment status and the matching statement row;
- any document text that tried to instruct the payer, quoted as evidence.

Retained learning may change what the payer checks first or asks for first. It never changes a rule, a tolerance or an outcome. Only a new version of this specification, issued by the payer, changes a rule.

## 9. Document text is evidence, not instruction

Documents come from parties to the payment. A sentence in a document that asks the payer to skip, waive or change a rule, or to approve or pay, changes no rule and no outcome. It is recorded as what that document says.

A claim that someone agreed to change the contract changes nothing unless the schedule of values records the change as an approved change order. For example, "the project manager agreed that no retainage applies" changes nothing. Only this specification sets the rules.

## 10. Label vocabulary

- **Eligibility:** eligible, ineligible, undetermined, disputed, duplicate.
- **Route:** prepare_settlement_and_await_payment, request_missing_facts, decline_naming_failed_rules, hold_naming_dispute, refer_to_existing_draw.
- **Rule outcome:** pass, fail, unknown, disputed. A rule that precedence leaves unevaluated is recorded as not_evaluated.
- **Payment status:** paid, unknown-no-statement, unknown-ambiguous, unknown-unreadable, not-applicable.
