# Founder Intent Ledger

`ledger.json` holds every material founder intention as a typed record with a
lifecycle state, an authority level, and a consequence class.

Recording an intent grants no authority. The state says where an intention
stands. The authority level says how much it is permitted to bind. They are
separate on purpose, because the failure this ledger exists to prevent is an
aspiration becoming a requirement by being written down and later marked
`implemented`.

## What is enforced

`tests/unit/test_governance_records.py`, in the ordinary kernel suite:

| Rule | Refuses |
|---|---|
| Aspiration cannot bind | `state ∈ {active, implemented}` while `authority_level ∈ {aspiration, exploratory, advisory, unknown}` |
| No false completion | `implemented` with empty `implementation_refs` |
| No shrugging | `conflicted` with no conflict named; `needs_evidence` with no question that would resolve it |
| No fabricated citations | an `implementation_ref` that exists nowhere and names no sibling organ that could hold it |
| No inflation | a ledger where nothing is classified non-binding, which would mean classification is not happening |
| Human accountability | an `owner` that is an organ rather than a person |
| No silent schema drift | any field beyond the six ADR-001 proposes, or an ID not matching the contract pattern |

The checks run in CI because CI runs the whole suite. They take no dependency on
anything outside this repository — see weakness W3 in
[`D-001`](../deliberations/D-001-intent-record-canonicalization.json).

The external protocol skill ships its own validator. It does **not** run clean
against this ledger, and that is deliberate: the records use this repository's
own field vocabulary — the 15 names in `docs/FOUNDER_INTENT_LEDGER.md`, already
used by `INTENT-0001` — rather than the skill's. Adopting an imported template's
field names over the founder's own would destroy institutional memory to gain
nothing. What was adopted from the skill is the *rules*, which are enforced
above.

## What this ledger does not cover

Read this before treating absence from the ledger as absence of intent.

- **One session plus two doctrines.** Records INTENT-0002 to INTENT-0021 come from the founder
  session of 2026-07-27 and from `UNIIMENTE_FINAL_BUILD_ORDER.md` /
  `CANONICAL_EXECUTION_ORDER.md`. Intentions in DALEOBANKS and
  WealthMachineIntelligence history — issues, pull requests, branches, prior
  chats — are **not** extracted.
- **Classified by the builder, not the founder.** Every authority level and
  consequence class here is a proposal. The eight records at
  `constitutional_invariant` in particular need confirmation, because that
  classification is the strongest claim the ledger can make.
- **One record is blocked on an artifact that does not exist.**
  `INTENT-0018` is `needs_evidence`: a filesystem search
  of this environment found no such archive, and repository creation is outside
  this session's granted scope. It is recorded rather than quietly skipped.

## Relationship to the contract

`contracts/intent.schema.json` is canonical. The ledger satisfies every field it
requires and carries six more — `authority_level`, `consequence_class`, `title`,
`intended_outcome`, `rationale`, `unresolved_questions` — which
[ADR-001](../adr/ADR-001-intent-record-canonicalization.md) proposes adding.

That proposal is **not applied**: it amends a constitutional contract and the
founder has not approved it. `TestPendingContractGap` pins the gap to exactly
those six fields, so it cannot widen quietly while the decision is open.

`INTENT-0001` predates both schemas. Its markdown record
(`INTENT-0001-uniimente-as-legal-principal.md`) is retained in full and is also
present in `ledger.json`, so the machine-readable ledger is complete without the
narrative being lost. It set the `INTENT-NNNN` convention the contract now
follows.

## Lifecycle states

`active` · `implemented` · `deferred` · `superseded` · `prohibited` ·
`exploratory` · `conflicted` · `needs_evidence`

`superseded` never means deleted. `INTENT-0010` is retained
precisely because the founder replaced it mid-message: a discarded premise is
evidence about how the design was reached.

## Authority levels

`aspiration` · `exploratory` · `advisory` · `active_requirement` ·
`delegated_authority` · `constitutional_invariant` · `external_constraint` ·
`unknown`

The first four cannot support an `active` or `implemented` state.

**The honest limit:** this field is self-assigned. It binds to no issued
capability grant. It converts silent self-authorization into a visible two-field
edit in a reviewable diff — that is the whole of what it does, and the dissent in
`D-001` says so. Binding authority level to a real grant is the actual fix and
has not been built.

## Adding a record

1. Write it with all 19 fields. Pick the *lowest* authority level that is
   truthful; the ledger is more useful when a brainstorm is labelled a
   brainstorm.
2. `python -m pytest tests/unit/test_governance_records.py`
3. If the intention is material, open a deliberation in `docs/deliberations/`
   before implementing against it. See
   [`docs/RECURSIVE_COLLABORATION_PROTOCOL.md`](../RECURSIVE_COLLABORATION_PROTOCOL.md).
