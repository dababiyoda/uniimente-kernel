# Mission D / G / H canonical-path defects — merge record (2026-10-15)

Source directive: `docs/intent/sources/OPUS-MAXIMUS-MASTER-EXECUTION-DIRECTIVE-2026-10-13-source.md`,
whole-machine acceptance Missions D (multi-worker handoff), G (commerce and settlement) and H (fault
recovery). Base: `19bbdcb` (PR #173 line). Local branch `mission-defects`, landed on the PR #173 branch `claude/greg-full-machine-convergence-20261013`.

**Completion boundary.** This record closes the nine defects below on the canonical in-process and
real-process paths, at the **SANDBOX** evidence tier: per-test Ed25519 founder keys (not Alfonso's), test
doubles and a loopback Stripe emulator in test mode, no network, no external system of record. Missions D,
G and H as a whole are **not** externally verified. No defect fix adds, widens or self-grants authority.

## Defects, evidence and fixes

Each defect was first reproduced by a probe on `19bbdcb`. Each regression test fails on `19bbdcb` with the
failure quoted and passes on this branch.

| ID | Defect observed on 19bbdcb | Fix | Regression (fails before) |
| --- | --- | --- | --- |
| H1 | A RECONCILIATION request was keyed by mission, kind and scope, so a single `reconcile_not_executed` was reused for every later UNCERTAIN dispatch of the same scope. Each tick redispatched with no new ask. UNCERTAIN spend was booked as $0. | Requests are bound to one dispatch (attempt, proposal, grant). The signed cap of an unknown dispatch is reserved until that dispatch is reconciled. `committed_usd` (spent plus reserved) is what the cone admits and what the Gate sees. | `tests/unit/test_greg_mission_reconciliation.py`: 12 adapter calls instead of 2; 8 instead of 2 |
| H2 | A retry-safe capability that kept returning UNCERTAIN was dispatched on every tick, with no cap, no backoff and no ask. | At most 3 consecutive unknowns per strategy, with exponential backoff. The streak is folded from the ledger, so it survives restart. After that, the mission replans, or makes exactly one NO_STRATEGY ask. | `tests/unit/test_greg_mission_retry_bound.py`: 40 calls in 40 ticks instead of 3 |
| G1 | `Rail.charge` and `Storefront.redeem` honoured any grant-shaped dict. | A grant is honoured only if it is held, unaltered, in the governing Gate's registry. It must be unrevoked, unused and unexpired, and bound to this objective, action, counterparty and effect. The charge or delivery itself runs through that Gate. | `tests/unit/test_mission_g_grants.py`: "DID NOT RAISE"; `KeyError 'settle_forged_grant'` |
| G2 | A stub `CommercialLoop` evaluated to CLOSED, and `outcome_bridge` emitted `externally_verified=True`. | Synthetic is the default label. A customer is observed only through an external system-of-record observation. Money is observed only through a live, non-emulator processor observation on the Gate's receipt. Only observed cases close externally. | `tests/unit/test_mission_g_synthetic_labels.py`: all 8 fail |
| D1 | A `bind` edge set a worker's `max_budget_usd` to $20 against a $0.50 signed cost. The mission booked $0.50 of a reported $15 and closed inside a $1 cone. | Bind edges onto protected params are refused at registration and at dispatch. A worker's budget is capped at the signed cost. An over-cap provider report is booked at the reported amount. | `tests/integration/test_greg_mission_d_handoffs.py` (D1): six registration cases did not raise; `{'b': 20.0}` budget |
| D2 | A consumer consumed a producer output that independent appraisal had REJECTED, spent $0.30 and was ACCEPTED. | A typed handoff from an appraised producer (`worker.commission`) waits for this mission to observe an ACCEPTED appraisal later than the receipt. A rejection holds the consumer with the verdict, and leads to one ask. A handoff from such a producer with no appraising check is refused at registration. | same file (D2): `['a', 'b'] != ['a']` for bind and inline |
| D3 | An inline `$from_action` consumer listed before its producer was chosen first and raised PendingInput. A self-clearing blocker recurred for 6 ticks; the producer never ran and no one was asked. | Inline inputs are resolved during selection. A pending consumer is held with its reason, so the producer runs. With nothing runnable, the mission makes one NO_STRATEGY ask naming what each held strategy waits on. Unknown and self references are refused at registration. | same file (D3): BLOCKED every tick; 0 asks instead of 1; "DID NOT RAISE" |
| H3 | A Body SIGKILLed after the Gate claimed a non-retry-safe dispatch, and before the receipt, left no `mission.action`. On restart the mission observed first and could close over an unreconciled dispatch. | A write-ahead `mission.dispatching` record carries the exact proposal id. On every tick, `_recover_dispatch` settles each unrecorded intent from the Gate's own record before observation: a receipt is reused; a claim without a receipt becomes UNCERTAIN, bound to the grant, with its cap reserved and one RECONCILIATION. | `tests/integration/test_greg_body_midflight_kill.py` (real OS process, SIGKILL, `greg decide` in a separate process): no reconciliation request; no grant on the record |
| H3b | H3 also pre-empted observation for a **free read-only** dispatch. The cognition SIGKILL test (`test_cli_composition_survives_sigkill_without_duplicate_computation[cognition.receipt]`) failed 2 of 9 runs at `11b22d5`, against 0 of 6 at `19bbdcb`: an answerable mission blocked on a needless RECONCILIATION. | A claim without a receipt on a `read_only` capability with zero signed cost is left to observation, since it cannot have changed the world or the budget. Paid read-only dispatches and every `internal_write`-or-higher dispatch keep H3's recover-first guarantee. Receipts are always settled. | `tests/unit/test_greg_recover_dispatch_boundary.py` (deterministic, in-process): the free read-only case fails without the fix; a mutant that skips all read-only dispatches fails the paid case |

## Verification performed

- The suites for every fix are listed above. The H3 real-process kill test passed 2/2. The cognition process
  test passed 8/8 after H3b, and the former reproducer passed 8/8. Together these are 16 kill-path runs with
  0 failures, against 2 of 9 failing before H3b.
- The full suite, the static CI checks (schema refs, authority singleton, sealed developmental), the mutant
  checks and the v2 verifier were run on the branch head before landing. The results are recorded in the
  PR #173 body for the landing commit.

## Residual limitations (named, not fixed here)

1. `AuthorityOffice.act`'s own retained-receipt path reports any retained receipt as DONE, whatever its
   `result_class`. The write-ahead recovery runs first and does distinguish positive from negative
   results, so the canonical restart path is correct. A direct caller of `act` with a retained negative
   receipt is not.
2. A paid, retry-safe UNCERTAIN dispatch keeps its reservation until it is settled. This conservative
   reservation can block a later dispatch that the real spend would have allowed. This is accepted:
   under-booking unknown spend is the worse failure.
3. G1's "unaltered" comparison relies on the Gate registry's stored grant record. On this branch the
   `GrantIssuer` returns live records. The sealed-record hardening comes with the security line (ports
   follow-up `05d2866`) and must be carried when that line lands.
4. Every evidence item here is SANDBOX tier. No real customer, processor, worker provider or founder key
   is involved. The G2 labels make that boundary machine-readable: nothing here can be reported as an
   external close.

## Authority statement

None of these changes grants, widens or self-authorizes any capability. Each one narrows what the
machine will honour: forged or foreign grants, reused reconciliation answers, unbounded retries,
over-cap budgets, unappraised handoffs and unreconciled consequential dispatches. Alfonso remains root
authority. Merging to `main` and any live activation remain his decisions.
