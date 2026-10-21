# Integration of #178 into #184: handoff, 2026-10-21

Draft PR: #192 (`claude/greg-integration-178-184-20261021` into #184's branch). No merge, signature,
deployment, spending, publication, contact or activation is part of this work.

## Pinned heads and lineage

| Lineage | Head integrated | Notes |
|---|---|---|
| #184 `claude/opus-maximus-one-greg-20261014` | `900c6ae`, then `b9150857`, then `1d8fd4c2` | stacked on #178 |
| #178 `claude/greg-one-machine` | `28dad3a`, then `12f6aea5` | contains #173 through `a48e8fa` and the #137/#168/#138 lineage |
| Merge base | `baf630d9` | |
| Organs (CI pins) | DALEOBANKS `667439f`, WealthMachine `ec82b80` | unchanged |

Not integrated here: #187/#188/#191 (based on #175, absent from #184), #183/#185/#186/#189 (descendant Mind
increments), #190 (docs, already applied). Each is the next integration unit.

Rollback: close #192. #178 and #184 are untouched; every fix commit reverts independently.

## Conflict decisions (one authority path, both lineages' defenses)

| Seam | Canonical | Kept from the other lineage |
|---|---|---|
| Spend | #178 reservations: `spent_usd` booked, `reserved` holds signed caps, `committed_usd` binds the Gate | #184 `cost_reserved` records still read at their recorded figure |
| Metered "not executed" | #178 H.G4: the cap is booked either way and the ask says so first | #184's retry-after-release test now asserts the founder approval the retry needs (stricter rule; recorded for the founder) |
| Reconciliation | #184 `_settle_uncertain` / standing reconciliation / `_resume_unsettled` | #178 per-dispatch `instance`, `_recover_dispatch`, `_finish_withdrawal` (not for shared asks) |
| Answers | #184 verified fold: a row moves a mission only as re-derived from a signed DECISION | #178 appraiser re-verification; each guard pinned alone by test and mutant |
| Worker confinement | #184 bubblewrap envelope by default | #178 Landlock as the floor under `supervised` (workers and acceptance); reports name the floor that ran |
| Inbox | #178 contained-fault loop | #184 rejection record (body clock, digest, recorded once) |
| Paid scope digest | #184 binds spend state | #178 appraiser re-derives it, including booked metered settlements |

## Defects the joined suites found, all fixed with a test that fails without the fix

1. Write-ahead dispatch scope lacked the spend state, so pre-approvals never matched.
2. The appraiser refuted every honest paid closure until it re-derived the spend state.
3. Legacy `cost_reserved` records were reserved at the spec's current cost.
4. Envelope: the private `/tmp` hid every read path under `/tmp` (a provider binary could not start).
5. `run_tests` overwrote the founder's confinement setting after its first command.
6. An opaque provider's exception was recorded DONE instead of interrupted (now reconciled; a governed
   worker's launch failure stays FAILED).
7. The appraiser did not count a metered RECONCILED_NOT_EXECUTED's booked cap and refuted the rerun.
8. `_finish_withdrawal` swallowed a withdrawn shared ask, so its undecided candidates were never asked about.
9. Two appraiser guards in series: neither was load-bearing alone (mutation gate); now each is pinned.

Negative and environmental findings: under the envelope `/proc/<parent>/environ` is readable and holds only
the envelope's own variables (no canary, no keys); this sandbox's `SSL_CERT_FILE` points outside the system
roots, which the envelope refuses by design, so local runs unset the cert variables (recorded per run); CI's
runner cannot use bubblewrap, so worker-path tests take `supervised` there.

## Validation bound to `b9f6b404`

| Check | Where | Result |
|---|---|---|
| Unit suite | local, `/home/user/evidence-b9f6/unit.log` | 5369 passed, 0 failed, 16 skipped |
| Integration suite | local | see PR #192 comment |
| Both whole-machine proofs with real pinned organs, hostile cases | local organ job; CI job 8 | see PR #192 comment |
| Mutation gates, schema refs, authority singleton, sealed developmental, integrity, verifier | local; CI jobs 2-9 | see PR #192 comment |

Earlier candidates' results (`50cad3e1`, `6b0cbfff`) are historical evidence only.

## Requirement-to-evidence table (directive of 2026-10-21)

| # | Requirement | State | Evidence |
|---|---|---|---|
| 1 | Execute the complete intention; continue unblocked work; one requirement table | IN PROGRESS | this table; item 4 implemented; remaining lanes listed below |
| 2 | Preserve ambition, build the effect; acquire before inventing | MET for this increment | Landlock and bubblewrap reused, not rebuilt; no new framework |
| 3 | One integration candidate, bounded ownership, independent review | PARTIAL | one candidate (#192); reviews were adversarial by test and mutation gate, not by a separate agent this run |
| 4 | Resolve duplication upward | MET for the #178/#184 seams | conflict-decision table above; every retained alternative has a role |
| 5 | Prove on the exact tree; bind results; no weakened tests | IN PROGRESS | validation table; every test change is listed in the commits and states the stronger or equal assertion |
| 5 | Demonstrate goal pursuit through cognition, genesis, Hands, organs, interruption, appraisal, learning, changed decision | MET in sandbox | `test_one_machine_ten_steps.py` (steps 1-10, real organ checkouts); synthetic parts: test keys, scripted worker, fixture commerce |
| 6 | #182 reserved; #9/#10 restricted; device acceptance founder's; commerce inert | HELD | no change to #182 or integrity pins; no #9/#10 work; VEPMC 0 (`vepmc.json`: missing founder_accepted, founder_body) |
| 7 | Concrete handoff | THIS DOCUMENT | |

## What the machine can do now that it could not before

- One body runs both lineages' safety at once: spend reserved and booked on one rule, every forged approval
  stopped by the engine and, independently, by the appraiser, and every interrupted run reconciled.
- Workers run in the bubblewrap envelope by default and, under the founder's `supervised` setting on a host
  without it, under Landlock, including GREG's own acceptance runs; the evidence names the floor.
- `daleobanks.publish` forwards a DALEOBANKS grant the founder signed into the mission and reports
  DALEOBANKS's own gate reason (item 4).
- CI runs both whole-machine proofs against the pinned organs.

## Blockers and the smallest founder action

| Blocker | Dependency | Smallest founder action |
|---|---|---|
| #182 protected-artifact authorization | founder signature | sign the prepared authorization, or decline |
| #9/#10 | session safety restriction | none from this session; another authorized route if wanted |
| VEPMC 0 -> 1 | the designated device and personal acceptance | run the rehearsed mission on the device and accept it |
| Metered "not executed" books the cap | money semantics between lineages | confirm the stricter H.G4 rule, or ask for release-on-not-executed |
| Merge of #192 | review | review the draft |
