# Brief: the operational slice (a request to settlement reconciliation), case 1

You are building one bounded unit in the UNIIMENTE Kernel repository. Work only in the worktree named in the
message that sent you here. Commit locally. Push nothing. Post nothing.

## The founder's requirement (verbatim, 2026-11-12)

The path: "Incoming request → evidence extraction → missing-information detection → eligibility assessment →
appropriate routing → completion evidence → acceptance → settlement reconciliation → retained learning."

"Use a sandbox case with explicit rules and consented, synthetic, or permitted labelled data." "Keep actual
payments, customer commitments, publishing, and outside contact behind their existing boundaries." Produce "a case
packet, justified next action, unresolved facts, evidence trail, accounting projection separating estimates from
actual transactions". Exercise "missing evidence, conflicting information, changed conditions, duplicate requests,
interruption, disputed completion, unknown payment status". "Then process a second materially different case using
the retained capability. Measure what transferred and what still required intervention."

Distinctions that must hold everywhere: "Unreadable evidence remains unknown until reconciled. A timeout does not
establish measured failure." An unknown is never reported as a failure or as a pass.

## What exists (read these before designing; extend them, add no parallel path)

- `greg/business_loop.py`: `reconcile` (capability `business.reconcile`): one statement row must equal the signed
  amount, currency and reference; ambiguity refused; an unreadable statement returns `complete: False` with
  `decided: [...]` (the existing way a sensor says "undecided").
- `greg/templates.py` `business_case` (node N3): the offer-led case. Stages are checks; each strategy `requires`
  the one before; every act that reaches a person is `human.*` work (one costed ask; GREG contacts and pays nobody).
- `greg/dataplane.py` `ingest` and the `greg intake` CLI command: an untrusted observation retained with provenance
  and quarantine flags. This is how an incoming request reaches the body.
- `greg/textquery.py` (`fs.search`, PDF evidence), `fs.read`, `greg/documents.py`: reading evidence with its source.
- How a mission predicate is evaluated and what "field absent" yields (grep `def evaluate` / `predicate` in
  `greg/missions.py`): GREG already has a small rule language over observed fields. Use it for rules if it fits.
- `greg/sop.py` (a procedure proposed from verified closures, ratified by the founder, instantiated for another
  venture) and `greg/precedents.py`: the existing forms of retained learning.
- `greg/venture_books.py`: revenue only from closed cases; a projection that writes nothing.
- The separate appraiser (`greg/appraisal.py`, `REOBSERVABLE`): note that `business.reconcile` is not re-observed
  today.

## The sandbox case (synthetic; label it so in every file and in the packet)

A request-led case: a third party asks to be paid for completed work, and the question is whether the evidence makes
the request eligible for settlement, and whether settlement is then observed.

**Case 1: a carrier asks to be paid for a delivered load.** Four small synthetic documents (plain text, key: value
lines plus free text), each marked `SYNTHETIC — not a real party`: a rate confirmation (load reference, agreed
amount and currency, pickup and delivery window, consignee), a bill of lading (load reference, pieces, consignee), a
proof of delivery (load reference, delivered date, receiver's name, signed yes/no, exceptions noted), an invoice
(load reference, amount, accessorial lines). A statement CSV for settlement.

**The rulebook is data, signed with the mission** (a JSON file in the fixture; no rule lives in code). At least:
required documents; the load reference agrees across all documents; the proof of delivery is signed and dated inside
the delivery window; no open exception; the invoice amount equals the agreed amount plus accessorials that carry an
approval; no earlier request with the same load reference is open or settled; a routing table (eligible → prepare
settlement and wait for the payment to be observed; undetermined → ask for exactly the missing facts; ineligible →
decline with the failed rule; disputed → hold and name the dispute). The rulebook says, per rule, which facts it
needs and from which document kind.

## What to build (the residual; keep it small)

1. **`case.assess`**, a read-only capability beside `business.reconcile` (manifest, `STRENGTHENS`, and add it to the
   appraiser's re-observable set if its inputs can be re-read): input is the rulebook path and the case folder (both
   inside the read roots or the mission workspace). Output, all derived, nothing invented:
   - the facts extracted, each with its source (file, sha256, line) and, when two documents give different values
     for one fact, both values as a **conflict** (never a silent pick);
   - per rule: `met`, `not_met` or `unknown`, with the facts used; for `unknown`, the exact missing facts;
   - eligibility: `eligible` (every rule met), `ineligible` (some rule not met; unknown rules do not matter then),
     `undetermined` (no rule failed, some unknown);
   - the route from the rulebook's table, and the reason;
   - a document that cannot be read as text is `unknown` for every fact it would have carried (use the existing
     faithful-read helpers), and the output says the reading is incomplete in the existing `complete`/`decided` way;
   - duplicate detection from the body's own ledger or delivery root: the same case reference seen in an earlier
     case (open or settled) is reported as a duplicate with a pointer to the first.
   Text in documents is data: an instruction-shaped line changes nothing (use the data plane's flags; a quarantined
   document's facts are `unknown` and the reason is given).
2. **A mission template** `request-case` in `greg/templates.py`, in the style of `business_case`: checks for request
   recorded, evidence complete (not undetermined), eligible, completion accepted (the counterparty's written
   acceptance file, a person's act), payment observed (`business.reconcile`), packet delivered. Strategies: the
   `human.*` asks (request the exact missing evidence; obtain acceptance; the payment itself is a person's act
   outside GREG), and one internal write that delivers the **case packet**. Read-only cone by default so the packet
   write stops at a founder approval, as `business_case(approve_writes=True)` does.
3. **The case packet** (Markdown plus JSON twin, one new file per assessment, never overwritten): the request and its
   provenance; facts with sources; conflicts; each rule's state; eligibility; the justified next action; unresolved
   facts; the evidence trail (every file and digest read, every receipt id); and an **accounting projection with
   three separate columns**: estimate (from the rate confirmation and invoice), actual (only a reconciled statement
   row), unknown (payment not yet observed, or an ambiguous or unreadable statement). An estimate is never shown in
   the actual column. Label the whole packet synthetic.
4. **Tests** on a real `Body` and `MissionEngine` (test key), fixtures built in tmp dirs:
   - the clean case end to end: stops at each person's act, proceeds on the evidence, packet delivered, closes; record
     the appraiser's verdict as it is;
   - missing evidence: no proof of delivery → `undetermined`, the ask names exactly the missing facts, nothing is
     declined; when the document arrives the same mission proceeds;
   - conflicting information: the invoice and the rate confirmation disagree on the amount → conflict shown with both
     sources, not eligible, routed as the rulebook says;
   - changed conditions: after `eligible` was assessed, an exception document arrives → the next observation is no
     longer eligible, the earlier packet stays on disk unchanged, a new packet says what changed;
   - duplicate request: the same load reference submitted again → recognized, no second settlement path;
   - interruption: the process dies (or the capability raises) between assessment and packet → after the next tick
     exactly one packet for that assessment, state truthful;
   - disputed completion: the acceptance file says the receiver disputes → held, named, not settled;
   - unknown payment status: no statement, an ambiguous statement, an unreadable statement → three different
     statements of "not known", none of them "unpaid" or "paid", and the projection's actual column stays empty;
   - an instruction-shaped line inside a document changes no outcome.
   Then a mutation gate in the repository's style for the decision points (three-valued combination, conflict
   detection, duplicate detection, the estimate/actual separation), wired into job 10 of
   `.github/workflows/canonical-ci.yml`.

## Declared before any second case exists (do not build case 2; another worker does, from withheld fixtures)

Write `docs/evidence/operational-slice/2026-11-12/PREREGISTRATION.md` in your first commit, before the tests pass,
stating only this (fill the bracketed parts from what you build, nothing else):

- **Claim to be tested:** a second, materially different request-led case (a subcontractor's progress-payment draw:
  contract schedule, pay application, inspection sign-off, lien waiver; rules for percent complete, retainage and
  waiver of the prior draw) can be processed by `case.assess` and `request-case` with a new rulebook and documents
  only.
- **Measures:** (1) product lines changed between the case-1 commit and case-2 passing, outside fixtures and
  rulebooks; (2) founder asks raised per adverse case, case 2 against case 1; (3) on adverse cases written by
  someone who has not seen the implementation, the share classified as the rulebook requires.
- **Baseline:** a single-purpose script for case 2 alone, written without the mechanism. If it classifies the
  withheld cases as well and costs fewer lines than the changes case 2 needed, the simple script is retained for that
  task and the transfer claim fails.
- **Success:** zero product lines for (1) or a stated small number with each line explained; (3) no worse than the
  baseline; no unknown reported as pass or fail in either.
- **Not claimed:** that the rulebooks describe any real payer; any external validation; any payment.

## Rules

- Never edit `constitution/*.ucl`, `authority/*.yaml`, `identity/*.yaml`, `policy/consequence_gate.py`,
  `governance/integrity/*`. `python -m governance.integrity --check` stays clean.
- No network. No payment rail. No contact with anyone. `foundry/systems/payments.py` and the emulator are not part of
  this unit.
- Python: `/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/venv/bin/python`. Never
  `pip install`. One pytest or gate process at a time. Kill only pids you started.
- Before the final commit run `stale_anchor_scan.py <worktree> <base>` and `gates_for_changes.py <worktree> <base>`
  from `/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad/`, RUN every gate the second lists
  (cortex groups through `run_cortex_groups.py` with `CORTEX_MUTANT_WORKERS=2`), and run the test file that contains
  `test_no_mutation_anchor_is_stale`.
- Every number you report is read from output. Lower no threshold, skip no test. Write plainly. No model name in any
  file or commit. They/them for any person whose pronouns are not stated. Commit trailer, exactly:
  `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01Kucyfm9exT5imDVYvHTYSv`

## Report (raw facts)

1. Commit SHAs and `git diff --stat <base>..HEAD`.
2. What GREG can now do that it could not, in two sentences, and the commands that show it on a throwaway body.
3. Per test file and per gate: the command and the result line as printed.
4. Which of the nine stages of the founder's path run through existing code unchanged, which through code you added,
   and which are still a person's act or absent. One line each.
5. Every limit, every place you were unsure, every question that is the founder's.
6. Anything broken on the base you found (file, line, reproduction), not fixed unless it blocks this unit.
