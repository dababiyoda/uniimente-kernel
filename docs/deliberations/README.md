# Deliberation records

The machine-readable record of a decision that has been through
[`docs/RECURSIVE_COLLABORATION_PROTOCOL.md`](../RECURSIVE_COLLABORATION_PROTOCOL.md).
The protocol defines the process; these files are the proof it happened.

One file per material decision: `D-NNN-slug.json`. The human-readable form for
approval lives in [`docs/adr/`](../adr).

## What is enforced

`tests/unit/test_governance_records.py`, in the ordinary suite, so it runs in CI:

| Rule | Refuses |
|---|---|
| Five roles | a record missing any of the canonical five |
| Exactly two passes | a `pass_3`, or a missing pass |
| No silent omission | a Pass-1 disadvantage with no disposition in Pass 2 |
| No manufactured consensus | `dissent.present` contradicting its entries |
| No unattacked design | empty `residual_risks` |
| Internal consistency | `decision` contradicting `pass_2.recommendation` |
| Real lineage | a `founder_intent_refs` entry not in the ledger |
| **No self-approval** | a constitutional decision resolving to anything but `NEEDS_FOUNDER_DECISION` without a named approver |

The last one is the point. A record cannot grant itself the authority it is
asking for.

## Roles

The canonical five, from protocol section 1: **Builder**, **Adversary**,
**Operator**, **Beneficiary Representative**, **Constitutional Reviewer**.

Roles may recommend against the final decision. `D-001` has all five
recommending `RETAIN` and resolves to `NEEDS_FOUNDER_DECISION` — merit and
authority are different questions.

## Relationship to the external protocol skill

The record structure and the `NEEDS_FOUNDER_DECISION` state were adapted from an
external founder-intent collaboration protocol. Its **role vocabulary was not
adopted**: this repository already had five roles, `.github/pull_request_template.md`
already uses them, and swapping a working vocabulary for an imported one would
destroy institutional memory to gain nothing.

So the external `validate_deliberation.py` reports exactly one error against
`D-001` — missing its own role names — and nothing else. The record is
structurally complete.

The external `validate_intent_ledger.py` likewise rejects
`docs/intent/ledger.json`, because those records use this repository's field
vocabulary (the 15 names in `docs/FOUNDER_INTENT_LEDGER.md`, already used by
`INTENT-0001`) rather than the skill's. Same trade, same reason.

Both divergences are deliberate and recorded in `D-001`'s `counterevidence`.
What was adopted from the skill is its **rules** and its
`NEEDS_FOUNDER_DECISION` state — not its names.

Neither is authoritative. The checks in `tests/` are, and they depend on nothing
outside this repository — a fresh clone validates without hidden workspace
state, which is one of the Golden Kernel conditions applied to governance
itself.

## Index

| ID | Title | Level | Decision |
|---|---|---|---|
| [D-001](D-001-intent-record-canonicalization.json) | One canonical Intent Record, with authority level | Constitutional | `NEEDS_FOUNDER_DECISION` — [ADR-001](../adr/ADR-001-intent-record-canonicalization.md) |
