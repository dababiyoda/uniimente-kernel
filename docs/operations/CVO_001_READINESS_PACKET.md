# CVO-001 Readiness Packet

**Status: PLAN ONLY.** No activation, no contact, no data, no spending, no
deployment. IVIO-NEMT remains `ACTIVE=False`, `ATTACHED=False`.

**Single Bottleneck Metric: Clean Verified Outcome Count, 0 → 1.**

**Planning base:** `main` @ `8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1`

---

## 0. The one thing that must not be misread

The repository already contains a complete, coherent, professional-looking
commercial model for IVIO-NEMT:

```python
buyer="facility CFO", beneficiary="patient", pain_owner="case management",
budget_owner="facility CFO", trapped_value_usd=250000.0,
accepted_artifact="Request-Accept-Evidence packet", …
```

**Every one of those values is a test fixture.** `ventures/ivio_nemt/fixtures.py`
says so in its own docstring: it preserves "the healthcare-specific closure
example that was previously hardcoded as the DEFAULT." It is a worked example
retained for continuity, not a market finding. No customer said any of it. No
facility CFO was interviewed. The $250,000 figure has no source.

This packet therefore classifies **every** commercial fact as `INFERRED` or
`UNCERTAIN` unless the repository or an external record independently
establishes it. The `KNOWN` column is almost entirely constitutional and legal
constraints — because that is genuinely the only thing that is known.

**No simulated fixture may be counted as a CVO.** A fixture that flows through
the entire pipeline and produces a green result is a test passing, not a
customer served. The distinction is the whole reason the CVO count is 0 and not
1 today.

---

## 1. Classification key

| Class | Meaning |
|---|---|
| **KNOWN** | Established by repository contents, a recorded verifier run, or an external record. Checkable now. |
| **INFERRED** | A reasonable reading of fixtures, architecture docs, or domain logic. Not evidence. |
| **UNCERTAIN** | Genuinely unknown. No basis in the repository. Must be resolved externally. |
| **PROHIBITED** | Forbidden by the Constitution, the legal-principal registry, or standing founder instruction. |
| **FOUNDER DECISION** | Cannot be resolved by any build session. Requires Alfonso. |

---

## 2. The required identifications

| Item | Class | Content and basis |
|---|---|---|
| **Exact buyer** | **UNCERTAIN** | Fixture says `facility CFO`. That is a *role*, not a buyer. No named facility, no named person, no confirmed budget authority. A CVO requires a specific counterparty. |
| **Beneficiary** | **INFERRED** | Fixture says `patient`. Domain-plausible: NEMT exists to move patients. But whether the patient is the beneficiary *of the evidence service* — as opposed to the facility, whose reimbursement risk it addresses — is unresolved and changes the ethics review. |
| **Pain owner** | **INFERRED** | Fixture says `case management`. Plausible: discharge delays land there. Unverified. |
| **Budget owner** | **UNCERTAIN** | Fixture puts buyer and budget owner both at `facility CFO`. In real facilities these commonly diverge, and a CVO fails if the person who agrees cannot authorize payment. |
| **Legal operator** | **KNOWN, with a blocking gap** | `IVIO_NEMT_LLC`, `status: proving_ground`, `jurisdiction: to_be_confirmed_by_founder`. The registry states: *"Founder must confirm exact registered name and jurisdiction before any external contractual effect."* Contracting is currently **blocked at the registry level**. |
| **Jurisdiction requiring confirmation** | **FOUNDER DECISION** | `to_be_confirmed_by_founder`. Determines HIPAA posture, NEMT licensing, state Medicaid rules, and whether a BAA is even the right instrument. **Nothing external may proceed until this is a real jurisdiction.** |
| **Smallest bounded transaction** | **INFERRED** | Plausibly: one discharge transport, one evidence packet, one payer-acceptable artifact, one payment. Deliberately small — one transaction, one facility, one patient, one payment. Not yet validated as something anyone buys. |
| **Accepted deliverable** | **INFERRED** | Fixture: `Request-Accept-Evidence packet`. Whether any payer or facility accepts this format is **UNCERTAIN** and is the core commercial risk. |
| **Independently verifiable external outcome** | **UNCERTAIN** | Must be observable by someone who is not UNIIMENTE and not Alfonso. Candidates: a payer remittance, a facility AP record, a signed acceptance. **Self-generated artifacts do not qualify** — that is the VMEE/CVO line. |
| **Payment or enforceable commitment** | **UNCERTAIN** | No payment account, no processor, no invoicing entity. Depends entirely on the legal-operator gap. |
| **Reconciliation standard** | **INFERRED, partly KNOWN** | Architecture exists: outbox/inbox, receipts, reconciliation workers (Final Build Order §4.8). The *commercial* standard — what counts as a matched, accepted, paid outcome — is undefined. |
| **BAA / privacy boundary** | **FOUNDER DECISION + PROHIBITED until resolved** | Fixture assumes `BAA plus fair-market-value evidence service`. Whether PHI is touched at all is the pivotal design question. The registry rule `regulated_activity: requires_compliance_signoff_before_first_effect` applies. **A design that touches zero PHI is strictly preferable and should be attempted first.** |
| **Authority required for contact** | **FOUNDER DECISION** | External contact is a distinct consequence class (Guard rules 7–8). No grant exists. Requires a capability grant naming target, channel, content class, and duration. |
| **Authority required for data** | **FOUNDER DECISION** | Real-world data processing is currently prohibited by standing instruction. Any patient-adjacent data additionally requires the compliance signoff above. |
| **Authority required for service delivery** | **FOUNDER DECISION** | Requires an active legal operator with confirmed jurisdiction. Blocked by the registry gap. |
| **Authority required for payment** | **FOUNDER DECISION** | Spending and receiving are separate. Receiving payment requires a legal entity, an account, and tax treatment — none of which exist. |
| **Kill conditions** | **INFERRED, proposed** | See §4. |
| **Seven-day validation action** | **INFERRED, proposed** | See §5. |
| **Conventional non-morphogenetic baseline** | **KNOWN as a requirement** | See §6. |
| **Should IVIO remain the first wedge** | **FOUNDER DECISION** | See §7 — argued both ways. |

---

## 3. What is actually KNOWN

Short list, deliberately. Everything here is checkable today.

1. `ivio_nemt`: `ACTIVE=False`, `ATTACHED=False`.
2. `IVIO_NEMT_LLC` is `proving_ground` with jurisdiction `to_be_confirmed_by_founder`
   and may not produce external contractual effect.
3. `UNIIMENTE` is `type: not_a_legal_actor`, `status: prohibited` — it may
   **never** be named as legal principal.
4. `unknown_principal: hard_refusal`; `cross_principal_credentials: prohibited`;
   `regulated_activity: requires_compliance_signoff_before_first_effect`.
5. Clean Verified Outcome count is **0**. The one recorded external consequence
   (PR #26) is a **Verified Mediated External Effect**, not a CVO.
6. The IVIO commercial model in the repository is a preserved **fixture**, by its
   own documentation.
7. No payment account, processor, credential, or external channel is configured.

**That is the complete list.** Everything a commercial plan would normally rest
on — buyer, willingness to pay, accepted format, price — is absent.

---

## 4. Proposed kill conditions

Set before contact, not after. Each must be falsifiable and pre-committed.

| # | Kill condition |
|---|---|
| K1 | Jurisdiction cannot be confirmed, or confirmation reveals licensing UNIIMENTE cannot lawfully satisfy. |
| K2 | The smallest transaction cannot be executed without touching PHI, **and** no compliant PHI path is authorized. |
| K3 | No named buyer with confirmed budget authority is identified within the validation window. |
| K4 | The deliverable is rejected by the first two independent evaluators as not payer-acceptable. |
| K5 | The only achievable "outcome" is self-generated or Alfonso-attested — i.e. a VMEE, not a CVO. |
| K6 | Delivery requires a standing external credential or continuous operation that cannot be scoped, budgeted, and revoked. |
| K7 | The Founder Command Ordering Guard is not implemented when an external action becomes due. |

**K5 is the one most likely to be rationalized away**, because a VMEE will feel
like success and will produce artifacts that look like a CVO. It should be
enforced by someone other than the party declaring the outcome.

**K7 is a hard prerequisite** created by Governance Incident 001. External
consequence classes may not be exercised while the ordering defect is unmitigated.

---

## 5. Proposed seven-day validation action

**No contact, no data, no spending, no activation.** The blocking constraints
are legal and evidentiary, not technical — so the first week buys information,
not code.

| Day | Action | Consequence class |
|---|---|---|
| 1 | Founder confirms jurisdiction and exact registered entity name, or states it cannot yet be confirmed. | founder decision |
| 2 | Determine whether a **zero-PHI** version of the deliverable exists. If yes, the entire HIPAA surface may vanish. | analysis only |
| 3 | Define the CVO acceptance test in advance: what artifact, from whom, verifiable how, by whom. Written before any outreach. | analysis only |
| 4 | Identify the conventional baseline (§6) and its real cost. | analysis only |
| 5 | Produce a named-buyer list with an explicit evidence standard for "has budget authority." No contact. | analysis only |
| 6 | Draft the smallest bounded transaction as a written offer. Not sent. | analysis only |
| 7 | Founder go/no-go on **contact authority specifically** — a separate decision from every prior authorization. | founder decision |

**Day 3 is the load-bearing day.** Defining the CVO acceptance test *before*
outreach is what prevents a VMEE from being reclassified as a CVO after the fact
by an author motivated to count it. Written first, or it is not a test.

---

## 6. Conventional non-morphogenetic baseline

Required by the standing evidence discipline: a governed evolutionary system
must be compared against the boring alternative, or its value is unmeasured.

**The baseline:** a competent operations person with a spreadsheet, a phone, a
document template, and an email account, serving the same facility for the same
transaction.

Baseline questions that must be answered honestly before claiming institutional
value:

1. Could that person produce the same accepted deliverable? *Probably yes.*
2. Faster, for the first transaction? *Almost certainly yes.*
3. What does UNIIMENTE add? Only one defensible answer: **the proof, provenance,
   and reusability of the pathway** — a Capability Genome that makes transaction
   two and venture two cheaper. It adds nothing to transaction one.
4. Is that worth more than the setup cost? **Unknown, and it is the real
   question.**

**If CVO-001 is achieved only by a human doing the work manually while the
Kernel records it, that is a real CVO and must be counted** — but it must be
recorded as *human-executed, Kernel-witnessed*, not as institutional autonomy.
Conflating those two would be exactly the unsupported-claim failure the
execution order forbids.

---

## 7. Should IVIO-NEMT remain the first CVO wedge?

Argued both directions, because this is a founder decision and a one-sided case
would be advocacy rather than analysis.

### Reasons it should remain

1. It is the only venture with **any** preserved structure — a legal principal
   entry, a first-cell setpoint, closure fixtures, recorded lineage.
2. The domain has genuine, well-documented reimbursement friction. The pain is
   real even though this articulation of it is unverified.
3. NEMT transactions are naturally **small, discrete, and bounded** — a good
   shape for a first CVO.
4. It is already the designated proving ground; switching discards the only
   accumulated commercial context that exists.

### Reasons it should not

1. **Healthcare is the worst possible regulatory environment for a first
   external effect.** HIPAA, state NEMT licensing, and Medicaid billing rules
   mean the first CVO carries maximal legal downside for a system that has never
   produced one.
2. **The legal operator is blocked at the registry level.** Jurisdiction is
   unconfirmed. Every other candidate would face the same requirement, but few
   would face it under HIPAA.
3. **Every commercial fact is fixture data.** The apparent head start is
   `INFERRED` throughout — the model is detailed enough to feel validated while
   resting on nothing.
4. **The beneficiary is a patient.** A first-ever external effect from an
   unproven governed system landing near patient care is a poor risk trade when
   the goal is *any* verified outcome, not a healthcare outcome specifically.
5. A lower-stakes wedge — one with no regulated data, no licensing, and a
   business buyer — could produce CVO-001 faster and safer, and the resulting
   Capability Genome would transfer to IVIO later. **Bridge G exists precisely
   so the first venture need not be the important one.**

### Recommendation, stated as a recommendation

**Do not commit IVIO-NEMT as the first wedge before Day 2 of §5 resolves the PHI
question.** If a zero-PHI deliverable exists, most of objection 1 dissolves and
IVIO becomes a reasonable first wedge. If it does not, the correct move is to
prove CVO-001 somewhere with no regulated data and transplant the capability
into IVIO afterwards.

This is a recommendation, not a decision. The founder decides.

---

## 8. Prohibited — not proposed, not scheduled

- Activating IVIO-NEMT or any Venture Cell.
- Naming `UNIIMENTE` as legal principal, in any document or transaction.
- Acting through another principal's credentials.
- Processing real-world or patient data.
- External contact of any kind.
- Spending, settlement, wallets, or blockchain execution.
- Production credential use.
- Deployment.
- Counting any simulated fixture, self-generated artifact, or founder-attested
  result as a CVO.

---

## 9. Founder decisions required before any external action

In dependency order. Each is genuinely blocking; none can be supplied by a build
session.

1. **Jurisdiction and exact registered entity name** for `IVIO_NEMT_LLC`.
2. **PHI posture** — is a zero-PHI deliverable acceptable, or is PHI required?
3. **Compliance signoff** for regulated activity, if PHI is in scope.
4. **Wedge confirmation** — IVIO first, or a lower-regulation wedge first.
5. **Contact authority** — a capability grant naming target, channel, content
   class, and duration.
6. **Payment infrastructure** — receiving entity, account, tax treatment.
7. **CVO acceptance standard** — founder ratifies what counts, in advance.
8. **Guard prerequisite** — confirm the Founder Command Ordering Guard must be
   implemented before any external consequence class is exercised (K7).

---

## 10. Position of this packet

This is a readiness assessment, and the honest finding is that **the system is
not blocked on technology.** Nothing in §9 is an engineering task. Every blocker
is a legal decision, an authorization, or a piece of external evidence that no
build session can manufacture.

That is the correct result for an institution that has just closed its
architectural phase. The next threshold is not another module. It is one real,
clean, externally verified outcome — and the distance to it is measured in
founder decisions, not commits.
