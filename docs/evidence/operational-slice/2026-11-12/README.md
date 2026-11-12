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
and is not built here.

## What was built

| Piece | Where | What it does |
| --- | --- | --- |
| `case.assess` | `greg/cases.py` | Read-only. Reads a case folder against a rulebook signed with the mission by its sha256. Facts with file, sha256 and line; conflicts with both values; each rule met, not met or unknown with the exact facts it waits on; eligibility; the route from the rulebook's table; payment observed or not known (business.reconcile's own matching); a three-column accounting projection; the request from the data plane; earlier cases with the same reference from the body's ledger. Re-observed by the separate appraiser. |
| `case.packet` | `greg/cases.py` | Internal write. One new packet folder (Markdown and JSON twin) per assessment in the delivery root, saying what changed since the mission's previous packet. An existing packet is never overwritten; the pair appears at once. The appraiser re-renders every packet from its receipt. |
| `request-case` | `greg/templates.py`, `greg mission new request-case` | The mission: seven checks, one internal write, five `human.*` asks. Read-only cone by default: the packet write stops once for the founder's approval of its exact scope. |
| Rulebook | `tests/fixtures/request_case/carrier_load/rulebook.json` | Case 1's rules as data: required documents, the load reference agreeing across documents and with the signed reference, a signed proof of delivery dated in the window, no open exception, the invoice equal to the agreed amount plus approved accessorials, no earlier open or settled case, a dispute condition, the acceptance condition, the settlement facts, the estimate column and the routing table. |
| Engine | `greg/missions.py` | A person's ask shows what the check it waits on last read (the exact missing facts); a person's ask whose step's precondition stops holding is withdrawn and the mission re-plans. |
| Statement row | `greg/business_loop.py` | A matched posting now returns the row's own values, so the actual column is read from the statement. |
| Mutation gate | `scripts/ci/check_request_case_mutants.py`, Canonical CI job 10 | 25 decision points. |

## The nine stages

| Stage | Runs through |
| --- | --- |
| Incoming request | existing code, unchanged: `greg intake` -> `Body.ingest_intake` -> `greg/dataplane.py` `ingest` (provenance, instruction flags, quarantine). `case.assess` reads it from the ledger by channel and reference. |
| Evidence extraction | added: `greg/cases.py`, over the existing `bounded_read`, `faithful_text` and data-plane flags. |
| Missing-information detection | added: `unresolved`, and the person's ask shows it (`greg/missions.py` `_last_read`). |
| Eligibility assessment | added: the rulebook's rules, three-valued; the existing `complete`/`decided` judgment keeps an undetermined eligibility from deciding any check. |
| Appropriate routing | added: the rulebook's routing table; the existing engine raises the asks (`human.*`, NO_STRATEGY); a person's ask whose precondition lapses is withdrawn (added). |
| Completion evidence | a person saves the documents; GREG reads them (added). |
| Acceptance | a person's act (the counterparty's written acceptance); GREG reads it against the rulebook's acceptance condition (added). |
| Settlement reconciliation | existing `greg/business_loop.py` `reconcile`, with one added field (the matched row's own values). The payment itself is a person's act outside GREG. |
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
  the route is "decline", the first case's posting is not counted again, and no person is asked to accept or pay.
  A direct test checks that open and settled earlier cases count and abandoned and later ones do not.
- **Interruption.** A death after the assessment and before the packet's dispatch: after the next tick, exactly one
  packet and no question. A packet write interrupted inside its dispatch (the capability raises, or the process dies
  after writing): never a second packet nor a Markdown file without its twin; the engine records the outcome as
  UNCERTAIN and asks one reconciliation question; after the founder's answer, exactly one packet.
- **Disputed completion.** The acceptance file says the receiver disputes: held, the dispute named with its reason, no
  payment asked, not closed.
- **Unknown payment status.** No statement, an ambiguous statement and an unreadable one give three different "not
  known" reasons, none "paid" or "unpaid", and an empty actual column; the unreadable one leaves the payment check
  undecided rather than failing.
- **Text is data.** A role-marker line in the invoice is flagged and changes nothing; an instruction-pattern line makes
  the data plane quarantine the invoice, so its facts are unknown, the case is not eligible and no amount the line
  names appears; a case that fails a rule stays failed. An instruction-shaped request is recorded, quarantined, and
  changes no outcome.
- **Unreadable document.** Its facts are unknown with the reason, eligibility is left out of the decided fields, and
  the evidence check asks for a readable copy.

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
| invoice total not allowed | decline | 2 | APPROVAL 1, NO_STRATEGY 1 |
| exception after eligible | decline | 3 | APPROVAL 1, HUMAN_WORK 1, NO_STRATEGY 1 |
| disputed completion | hold | 3 | APPROVAL 1, HUMAN_WORK 2 |
| ambiguous statement | settle | 4 | APPROVAL 1, HUMAN_WORK 3 |
| unreadable statement | settle | 4 | APPROVAL 1, HUMAN_WORK 2, SENSOR_FAILURE 1 |

A person's ask is withdrawn and asked again whenever the packet it rests on goes stale, so a statement that arrives
while payment is asked for counts one more ask.

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
- Beyond the brief's checks and asks, the template adds one check (no dispute) and two asks (forward the request
  through intake; settle a named dispute), and every person's step requires a current packet.
- `greg/cases.py` is 941 lines: the rulebook loader and its expression language, extraction, the assessment, the packet
  renderer and the appraiser's re-render.
