# ADR-001: One canonical Intent Record, with authority level

- **Decision ID:** D-001
- **Status:** proposed
- **Date:** 2026-07-27
- **Decision owner:** alfonso_lopez
- **Deliberation level:** Constitutional
- **Founder intent references:** `INTENT-0004`, `INTENT-0003`, `INTENT-0005`, `INTENT-0021`
- **Supersedes:** —
- **Superseded by:** —
- **Full record:** [`docs/deliberations/D-001-intent-record-canonicalization.json`](../deliberations/D-001-intent-record-canonicalization.json) — five-role review, both passes, dissent, kill criteria.

## What you are approving

One change to one file, plus the tests that make it mean something. Nothing has been applied.

## Problem

**Observation.** Installing the founder-intent collaboration protocol brings a second Intent Record schema. `contracts/intent.schema.json` already exists, was added earlier the same day, and is read by `traceability/` as link 1 of the Single Bottleneck Metric. Two active schemas for one institutional object is the condition Final Build Order §3 forbids.

**The surface question** is which schema wins. **The controlling one is different:** the kernel contract has no field separating a founder's aspiration from a binding requirement. Nothing structural stops a brainstorm from becoming an executable requirement by being written down and later marked `implemented`.

That gap is concrete right now. `docs/intent/ledger.json` contains `INTENT-0008` — a product idea with no buyer, no evidence, and nothing built. Under the current contract, changing its state to `implemented` and pointing it at a README is a valid record.

**Proposed action.** Extend the kernel contract rather than replace it, and make the distinction executable.

## Baseline and evidence

| Claim | Class | Evidence tier | Source | Finding | Limitation |
|---|---|---|---|---|---|
| The kernel contract is load-bearing for the metric | observation | unit_test | `tests/unit/test_traceability.py::TestIntentContract` | 4 tests assert its 15 fields and 6 states against the founder's own document | Replacing the schema fails these |
| The kernel cannot express the aspiration/authority distinction | observation | primary_source | `contracts/intent.schema.json` | No `authority_level` field exists | — |
| The protocol's coupling rule closes exactly that gap | observation | primary_source | `validate_intent_ledger.py:212-219` | `status ∈ {active, implemented}` with `authority_level ∈ {aspiration, exploratory, advisory, unknown}` is an error | Self-assigned; see dissent |
| Both designs independently require `implementation_refs` for `implemented` | inference | primary_source | `validate_intent_ledger.py:202`; `traceability/chain.py` | Two implementations written without knowledge of each other converged on the same false-completion check | Weak corroboration, not proof |
| The protocol schema is a template, not an institutional artifact | observation | primary_source | its `$id` | `https://example.invalid/...` | Argues against wholesale adoption; not against borrowing its rule |

## Alternatives

- **Current baseline** — 15 fields, 6 states. Cannot express authority level.
- **Do nothing** — two schemas diverge silently; the metric eventually reads a schema describing half the ledger.
- **Simplest viable** — keep the kernel schema, ignore the protocol's. Cheapest, and loses the only mechanism that stops a brainstorm becoming a requirement.
- **Strongest competitor** — adopt the protocol schema wholesale. More complete, validator already written. Loses because it breaks the Single Bottleneck Metric the day it shipped and swaps founder vocabulary for a template's.
- **Reversible experiment** — add the fields as optional first. Rejected on merit: an optional `authority_level` is exactly as strong as none, since any record can omit it and escape the rule.

Revival evidence for each is recorded in the JSON.

## Five-role review

All five recommend the change on its merits. The decision is still `NEEDS_FOUNDER_DECISION`, for the reason in **Authority impact**.

| Role | Position | Recommendation |
|---|---|---|
| Constitutional Reviewer | Extend, don't replace — the 15 field names are the founder's vocabulary; but the ledger must be able to say "brainstorm" | RETAIN |
| Builder | One schema in `contracts/`. The adapter option would have to fabricate `authority_level` | RETAIN |
| Adversary | Worth having, but do not oversell: `authority_level` is self-assigned | RETAIN |
| Operator | 21 fields is real friction; acceptable only because the ledger is small and rarely written | RETAIN |
| Beneficiary Representative | This is the executable form of "no aspiration becomes executable merely because it appears in prose" | RETAIN |

Roles are the five canonical ones from `docs/RECURSIVE_COLLABORATION_PROTOCOL.md` §1. The external protocol skill names its roles differently; that vocabulary was deliberately not adopted (§7.2).

## Pass 1

**Intended outcome.** One canonical contract carrying the founder's vocabulary plus the two fields that make aspiration-versus-authority checkable.

**Advantages.** One mechanism for one object (A1). Aspiration cannot silently become authority (A2). The coupling rule is corroborated by an implementation written in ignorance of this one — the external protocol and this kernel independently arrived at the same two refusals, which is weak but real evidence both are load-bearing (A3). `conflicted` and `needs_evidence` let the ledger hold an open question honestly — the Golden Kernel import record can name its missing archive instead of being forced into `active` (A4).

**On A3, precisely:** the corroboration is in the *rules*, not the tooling. The external validators reject both artifacts here — the deliberation on role names, the ledger on field names — because this repository kept its own vocabulary from `docs/RECURSIVE_COLLABORATION_PROTOCOL.md` §1 and `docs/FOUNDER_INTENT_LEDGER.md`. That trade is deliberate and is recorded in the JSON's `counterevidence`.

**Disadvantages and redesigns.** X1 reclassification churn → all 21 records classified in the same change, so no record is ever valid-but-unclassified. X2 two validators drift → the in-repo test is authoritative, the external one advisory. X3 misclassification is undetectable by schema → bounded to the one case that matters, and stated rather than papered over. X4 two places claim implementation → same rule at source and at audit, deliberately.

## Pass 2

**Attack.** Three fronts: does this centralize governance so far that an organ cannot express an unanticipated intent; is the coupling rule theatre given self-assignment; and does the repo now depend on a validator living outside version control.

**New weaknesses.** W1 bureaucracy — 21 fields may suppress recording. W2 gaming — self-assigned authority. W3 dependency — CI reaching outside the repo. W4 centralization — one contract for all organs.

**W3 is the one that changed the design.** Validating in CI with a script under `~/.claude/skills` would make a fresh clone unable to reproduce the build. Refused. The authoritative check is a test inside `tests/`, over the kernel's own contract. The protocol's validator is an optional external conformance tool. This is the Golden Kernel clean-reproducibility condition applied to governance itself.

W4 is intended: intent is constitutional, and an organ needing a different shape is evidence of a constitutional gap, not a reason to fork the schema.

**Residual risks.** `authority_level` binds to no external grant. 19 fields may suppress recording — no data either way. The ledger covers one session plus two build-order doctrines; DALEOBANKS and WealthMachineIntelligence history is not extracted, so absence from the ledger is not absence of intent. **All 21 records were classified by the author of this change, not by you.**

## The exact change

Two required properties added to `contracts/intent.schema.json`:

```jsonc
"authority_level": {
  "type": "string",
  "enum": ["aspiration", "exploratory", "advisory", "active_requirement",
           "delegated_authority", "constitutional_invariant",
           "external_constraint", "unknown"],
  "description": "What this intention is permitted to bind. Recording an intent grants no authority; this field states how much authority the intent claims, and the coupling rule refuses claims the state cannot support."
},
"consequence_class": {
  "type": "string",
  "enum": ["low", "bounded", "material", "constitutional"]
}
```

Two lifecycle states added to `state`: `conflicted`, `needs_evidence`.

Three rules enforced by a new test in `tests/unit/test_traceability.py`:

1. `state ∈ {active, implemented}` with `authority_level ∈ {aspiration, exploratory, advisory, unknown}` → invalid.
2. `state == conflicted` with empty `conflicts` → invalid.
3. `state == needs_evidence` with empty `unresolved_questions` → invalid.

Rule 1 is the one that matters. The other two stop the new states being used as a shrug.

## Dissent

Two entries, both recorded and neither blocking. Full text in the JSON.

**Adversarial Reviewer:** the coupling rule should not be described as preventing aspiration from becoming authority. It prevents an accident, not an actor. Anyone who wants `implemented` can raise `authority_level` in the same edit. Calling it a control invites the institution to trust it more than it has earned. — *Accepted. The claim is narrowed everywhere it appears: this converts silent self-authorization into a visible two-field edit in a reviewable diff. That is the whole of it.*

**Operator and Maintainer:** 19 required fields is past the point where a contributor writes a record willingly, and mechanical compliance is more dangerous than none because it looks real. — *Accepted with a standing bar: no further field without a deliberation naming the failure it prevents.*

## Authority impact

- **Changes authority:** no. It adds a classification and a refusal. It makes authority harder to claim, never easier.
- **Authorized-human approval required:** yes — this amends a shared constitutional contract.
- **Approval state:** pending.
- **Approver:** alfonso_lopez.

## Decision

`NEEDS_FOUNDER_DECISION`

All five roles recommend the change. It is not applied, because it amends a constitutional contract and you have not approved it. Recording approval that did not happen would fabricate authorization — the failure this protocol exists to prevent, committed by the protocol's own installation. The gate is doing its job by stopping the person who installed it.

**To approve:** say so, and the change lands in one commit — contract, 21 records already classified, three tests.
**To reject:** the ledger and deliberation stay; `contracts/intent.schema.json` is untouched and the gap stays open and named.

## Migration, rollback, and kill criteria

- **Migration.** One commit. No staging: nothing in production emits intent records, so there is no data to migrate and no consumer to coordinate with. The 21 records in `docs/intent/ledger.json` already carry both fields and validate today.
- **Rollback.** Revert the commit; remove the six added fields from the 21 records. `traceability/` is unaffected either way — it never reads `authority_level`.
- **Kill criteria.** A record reaches `main` whose `authority_level` was raised in the same commit as its state, purely to satisfy the rule. A build package completes with implementation but no recorded intent. The two validators disagree on a genuinely valid record. An organ demonstrates a legitimate intent shape the contract cannot express.
- **Material items intentionally unchanged.** `contracts/intent.schema.json` (pending this decision). `docs/FOUNDER_INTENT_LEDGER.md` keeps its prose and its 6 documented states until the contract changes, so the two cannot disagree in the interim. `traceability/` — the walker does not read authority level and is not proposed to.
- **Review trigger.** Your approval or rejection.
