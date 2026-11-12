# Operational slice, case 1: a request to settlement reconciliation (2026-11-12)

**SYNTHETIC — not a real party.** Every document, rulebook, statement and person named in this unit is synthetic. No
payment rail, network or outside party was touched, and nothing here describes a real payer.

## The founder's requirement

"Incoming request → evidence extraction → missing-information detection → eligibility assessment → appropriate
routing → completion evidence → acceptance → settlement reconciliation → retained learning", on a sandbox case with
explicit rules, producing "a case packet, justified next action, unresolved facts, evidence trail, accounting
projection separating estimates from actual transactions", and exercising "missing evidence, conflicting information,
changed conditions, duplicate requests, interruption, disputed completion, unknown payment status". The second,
materially different case is pre-registered in [PREREGISTRATION.md](PREREGISTRATION.md) (first commit of this branch)
and is not built here. Its measured result, from withheld material, is in [RESULT-case-2.md](RESULT-case-2.md).

## What was built

| Piece | Where | What it does |
| --- | --- | --- |
| `case.assess` | `greg/cases.py` | Read-only. Reads a case folder against a rulebook signed with the mission by its sha256. Facts with file, sha256 and line; conflicts with both values; each rule met, not met or unknown with the exact facts it waits on; eligibility; the route from the rulebook's table; payment observed or not known (business.reconcile's own matching); a three-column accounting projection; the request from the data plane; earlier cases with the same reference from the body's ledger. Re-observed by the separate appraiser. |
| `case.packet` | `greg/cases.py` | Internal write. One new packet folder (Markdown and JSON twin) per assessment in the delivery root, saying what changed since the mission's previous packet. An existing packet is never overwritten; the pair appears at once. The appraiser re-renders every packet from its receipt. |
| `request-case` | `greg/templates.py`, `greg mission new request-case` | The mission: seven checks, one internal write, six `human.*` asks (one per rulebook route, including the decline). Read-only cone by default: the packet write stops once for the founder's approval of its exact scope. |
| Rulebook | `tests/fixtures/request_case/carrier_load/rulebook.json` | Case 1's rules as data: required documents, the load reference agreeing across documents and with the signed reference, a signed proof of delivery dated in the window, no open exception, the invoice equal to the agreed amount plus approved accessorials, no earlier open or settled case, a dispute condition, the acceptance condition, the settlement facts, the estimate column and the routing table. |
| Engine | `greg/missions.py`, `greg/authority.py` | A person's ask shows what the check it waits on last read (the exact missing facts); a person's ask whose step's precondition is measured failing is withdrawn and the mission re-plans (a sensor error, a timeout or an undecided reading lapses nothing). A refused receipt reused by a check that shares its sensor stays refused, never done with no output. |
| Statement row | `greg/business_loop.py` | A matched posting now returns the row's own values, so the actual column is read from the statement; a posting that names the reference only inside a longer one (LD-2401170 for LD-240117) is not matched; a statement without the signed columns says which it lacks. `reference_key` and `carries_reference` compare references wherever a case does (requests, earlier cases, postings). |
| Mutation gate | `scripts/ci/check_request_case_mutants.py`, Canonical CI job 10 | 51 decision points. |

## The nine stages

| Stage | Runs through |
| --- | --- |
| Incoming request | existing code, unchanged: `greg intake` -> `Body.ingest_intake` -> `greg/dataplane.py` `ingest` (provenance, instruction flags, quarantine). `case.assess` reads it from the ledger by channel and reference. |
| Evidence extraction | added: `greg/cases.py`, over the existing `bounded_read`, `faithful_text` and data-plane flags. |
| Missing-information detection | added: `unresolved`, and the person's ask shows it (`greg/missions.py` `_last_read`). |
| Eligibility assessment | added: the rulebook's rules, three-valued; the existing `complete`/`decided` judgment keeps an undetermined eligibility from deciding any check. |
| Appropriate routing | added: the rulebook's routing table, one `human.*` step per route (ask, decline, hold, settle); the existing engine raises the asks; a person's ask whose precondition is measured failing is withdrawn (added). |
| Completion evidence | a person saves the documents; GREG reads them (added). |
| Acceptance | a person's act (the counterparty's written acceptance); GREG reads it against the rulebook's acceptance condition (added). |
| Settlement reconciliation | existing `greg/business_loop.py` `reconcile`, with two added fields (the matched row's own values; the signed columns a statement lacks) and the reference matched as a whole. The payment itself is a person's act outside GREG. |
| Retained learning | existing `greg/sop.py`, unchanged: three verified closures propose a procedure, the founder ratifies it, and the fourth case runs from it without the packet approval. Also added: each packet says what changed, and earlier cases are read back from the ledger. |

## Results (case 1)

The test file `tests/unit/test_greg_request_case.py` runs on a real `Body` and `MissionEngine` with a test key (not the
founder's). What each test shows:

- **Clean case.** The packet write stops at the founder's approval; the mission then stops at the counterparty's
  acceptance and at the payment, each a person's act, and proceeds on the evidence. Three packets, none overwritten;
  the last one's actual column is read from the statement row. GREG's only completed action is `deliver-packet`. The
  separate appraiser's verdict, recorded as it was: VERIFIED, with `world_reobserved` and
  `deliveries_bound_to_evidence` true.
- **Missing evidence.** No proof of delivery: eligibility undetermined, route "ask"; the person's ask shows exactly the
  four missing facts; nothing is declined, no failure closure, and every observation of the `eligible` check is
  recorded as inconclusive. When the document arrives the same mission proceeds to acceptance.
- **Conflicting information.** The invoice restates the agreed amount as 2100.00 against 1850.00: both values with file
  and line, the rule that needs it unknown, not eligible, nothing reported missing, and routed "hold" as the rulebook's
  table says; the mission asks a person to settle the dispute and proceeds once the documents agree.
- **Changed conditions.** An exception notice arrives after eligible: the next observation is ineligible, the open
  acceptance ask is withdrawn ("a precondition ... no longer holds"), the earlier packet is byte-identical, and a new
  packet names the previous one and says what changed.
- **Duplicate request.** A second request for a settled load: the earlier case is named with its state, the rule fails,
  the route is "decline", the first case's posting is not counted again, and the one person's step is the decline;
  nobody is asked to accept or pay. A direct test checks that open and settled earlier cases count and abandoned and
  later ones do not, that a case a ratified procedure ran counts like a template's, and that a reference written with
  a non-breaking hyphen or full-width digits is the same reference while a longer one (LD-2401170) is another. The
  same load submitted again after a procedure-run case settled is declined as a duplicate.
- **Interruption.** A death after the assessment and before the packet's dispatch: after the next tick, exactly one
  packet and no question. A packet write interrupted inside its dispatch (the capability raises, or the process dies
  after writing): never a second packet nor a Markdown file without its twin; the engine records the outcome as
  UNCERTAIN and asks one reconciliation question; after the founder's answer, exactly one packet.
- **Disputed completion.** The acceptance file says the receiver disputes: held, the dispute named with its reason, no
  payment asked, not closed.
- **Unknown payment status.** No statement, an ambiguous statement and an unreadable one give three different "not
  known" reasons, none "paid" or "unpaid", and an empty actual column. Only "no statement exported yet" and "no
  posting names the case" are measured absences that ask a person to pay; an unreadable statement, two postings, a
  posting of another amount or currency, and a statement without the signed columns leave the payment check
  undecided, so nobody is asked to pay again on them (two postings that arrive while payment is asked for raise no
  second ask to pay; the founder is asked about the reading).
- **Text is data.** A role-marker line in the invoice is flagged and changes nothing; an instruction-pattern line makes
  the data plane quarantine the invoice, so its facts are unknown, the case is not eligible and no amount the line
  names appears; a case that fails a rule stays failed. An instruction-shaped request is recorded, quarantined, and
  changes no outcome.
- **Unreadable document.** Its facts are unknown with the reason, eligibility is left out of the decided fields, and
  the evidence check asks for a readable copy. A figure one document states unreadably ('2,100.00 USD') is waited on
  even when the rule reads it from another document, since it may disagree; a document silent on a fact (no line)
  makes no claim, and the estimate shows each document's own figure with its line.
- **Rules the facts cannot decide.** A division by zero, or an order on an optional document not on file, makes the
  rule unknown with its reason under `undecidable`; the evidence check is then undecided, not passed, and the packet
  names the rule. A rulebook comparing two kinds of value (a date against text, a yes/no fact against 'yes') is
  refused when it is signed, and such a comparison is never silently true or false.
- **Rulebook as written.** The approval filter is applied as written (an upper-case approval number), so 'approval
  pending' is no approval. Documents that disagree on a fact no rule reads (the consignee) are shown in the
  assessment, the route's reason and the packet; whether that holds a case is the rulebook's to say.
- **Sensing failures.** A timed-out or refused assessment while a person's ask is open measures nothing: the ask stays
  open, no check is judged a decided failure on an absent field, and nobody is asked again for the same act.
- **Ineligible.** The rulebook's decline route is a person's step (`human.decline`), not a generic no-strategy
  question. No acceptance on file is printed "not yet", never in the form of a refusal.

### Founder asks raised per case-1 scenario (the case-1 side of measure 2)

Counted from the ledger by [`count_asks.py`](count_asks.py) (`PYTHONPATH=. python
docs/evidence/operational-slice/2026-11-12/count_asks.py`), each scenario on its own throwaway body up to the step
shown (the first packet approved, then the scenario's event); every ask kind of the mission is counted:

| Scenario | Route | Asks | By kind |
| --- | --- | --- | --- |
| clean, to the first person's act | settle | 2 | APPROVAL 1, HUMAN_WORK 1 |
| missing proof of delivery | ask | 2 | APPROVAL 1, HUMAN_WORK 1 |
| unreadable proof of delivery | ask | 2 | APPROVAL 1, HUMAN_WORK 1 |
| conflicting agreed amount | hold | 2 | APPROVAL 1, HUMAN_WORK 1 |
| invoice total not allowed | decline | 2 | APPROVAL 1, HUMAN_WORK 1 |
| exception after eligible | decline | 3 | APPROVAL 1, HUMAN_WORK 2 |
| disputed completion | hold | 3 | APPROVAL 1, HUMAN_WORK 2 |
| ambiguous statement | settle | 4 | APPROVAL 1, HUMAN_WORK 2, SENSOR_FAILURE 1 |
| unreadable statement | settle | 4 | APPROVAL 1, HUMAN_WORK 2, SENSOR_FAILURE 1 |

A person's ask is withdrawn and asked again whenever the packet it rests on goes stale. Recounted in the 2026-11-12
fix round: a declined case now asks a person to decline (`human.decline`) where it raised a no-strategy question, and
two postings that arrive while payment is asked for leave the payment not known, so the founder is asked about the
reading (SENSOR_FAILURE) and nobody is asked to pay a second time.

## Limits

- Synthetic data only; no outside party, payer or payment. The appraiser is a separate process running reviewed Kernel
  code, not an independent implementation.
- An instruction-shaped line that quarantines a document makes the case undetermined rather than leaving its outcome
  unchanged: the brief's "a quarantined document's facts are unknown" was applied whole-document.
- An interrupted packet write is settled by the founder's reconciliation answer, not by GREG, although the write is
  content-addressed; a CapabilityError from the packet write is never retried (the engine's existing paths).
- The duplicate rule's fact (earlier open or settled cases) and the rule that a duplicate's posting is not counted are
  code concepts; the rulebook decides only what the count means.
- Duplicate detection replays the body's mission events on every observation; its cost on a large ledger is not
  measured.
- The evidence trail names every file and digest read, the intake events, the first observation receipt of the
  assessment and the previous packet's receipt; a packet's own receipt is on the ledger, since a file cannot name the
  receipt that records it.
- Beyond the brief's checks and asks, the template adds one check (no dispute) and three asks (forward the request
  through intake; settle a named dispute; decline with the failed rules), and every person's step requires a current
  packet.
- `greg/cases.py` holds the rulebook loader and its expression language (with its signing-time type check),
  extraction, the assessment, the packet renderer and the appraiser's re-render.

### Founder decisions this unit does not make (current behaviour stated)

- **Who wrote a document.** The requester's documents, the counterparty's acceptance and the founder's statement
  export share one case folder, and nothing ties a file to its author: an `acceptance.txt` saved with the requester's
  documents is read as the counterparty's acceptance, and a `statement.csv` saved there is read as the founder's
  export. How each party's documents reach GREG (separate places, intake channels with provenance, signatures) is
  the founder's decision.
- **The end of a declined case.** A declined case stays an open mission: its decline ask stays open until corrected
  documents make it eligible or the founder abandons it, and while it is open it counts as an earlier case for a new
  submission of the same reference (by reading the engine; the test runs to the decline ask).
- **Absence in a rule.** A fact of an optional document not on file is absence: equality reads it (no acceptance on
  file is "not yet accepted"; no exception notice is no open exception) and an order cannot (the rule is
  undecidable). A rule can therefore fail on a document that is simply not on file; the rulebook decides by marking a
  document required or optional.
- **A conflict no rule reads** is shown and does not hold the case.
- **Lookalike references.** Compatibility forms, dashes, invisible format characters and case are folded; letters of
  another script that look alike (a Cyrillic A for a Latin one) are not, since the standard library has no
  confusables table. Whether references must be plain ASCII is the founder's decision. `business.reconcile` still
  finds a posting by the reference in one normalization form (NFC) without folding dashes, so a posting written with
  a non-breaking hyphen reads "no posting carries the case reference" (by reading, not run).
- **A sensor that keeps failing while a person is asked** (a rulebook changed after signing) is re-read at the
  mission's cadence and not escalated while the person's ask is open (by reading `greg/missions.py`
  `_watch_while_blocked`, not run); the founder is asked about it once no person's ask is open.
