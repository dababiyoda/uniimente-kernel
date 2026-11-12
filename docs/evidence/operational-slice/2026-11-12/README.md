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

## Results

Filled from the runs of this unit; see the handoff for the commands and the printed result lines.
