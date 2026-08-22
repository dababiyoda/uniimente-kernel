# Founder Intent Ledger

UNIIMENTE must never silently lose a founder intention, contributor objection, negative result, or superseded design.

Every material intention discovered in chats, documents, issues, pull requests, repositories, or operating evidence must be normalized into an Intent Record and assigned exactly one lifecycle state:

- `active`: binding design or operating direction.
- `implemented`: enforced by code, contract, test, workflow, or policy.
- `deferred`: preserved with an explicit trigger, dependency, and review date.
- `superseded`: replaced by a stronger formulation, with lineage and rationale.
- `prohibited`: incompatible with law, safety, constitutional authority, evidence integrity, or human sovereignty.
- `exploratory`: a hypothesis that may inform experiments but has no authority.

No aspiration becomes executable merely because it appears in prose. Classification preserves ambition without converting speculation, contradiction, or outdated language into accidental authority.

## Required Intent Record

Each record must contain:

1. `intent_id`
2. `statement`
3. `source_refs`
4. `owner`
5. `state`
6. `binding_scope`
7. `constitutional_constraints`
8. `success_evidence`
9. `failure_evidence`
10. `dependencies`
11. `conflicts`
12. `next_review_trigger`
13. `supersedes`
14. `superseded_by`
15. `implementation_refs`

## Upward Interpretation Rule

When an intention is ambiguous, interpret it toward the strongest lawful, evidence-preserving, human-sovereign, reversible, and commercially durable form.

"Build upward" never means:

- inventing evidence;
- bypassing the Consequence Gate;
- granting machines sovereignty;
- converting aspirations into production claims;
- concealing downside;
- deleting rejected branches or negative results;
- increasing complexity without a measured control advantage.

It means improving the architecture until its strongest useful property is retained with lower fragility, clearer authority, stronger proof, easier replacement, and better participant welfare.

### Infinite Goal Chase interpretation

`INTENT-0029` adds a binding clarification to this rule:

> Every unfinished active founder intention remains part of the Infinite Goal Chase unless explicitly implemented, superseded, prohibited, deferred with a trigger, conflicted pending founder resolution, or lawfully retired. `Not implemented` must never be silently interpreted as `not intended`.

The complete dated reconciliation snapshot is preserved in `docs/INFINITE_GOAL_CHASE_CANONICAL_BACKLOG.md`. Its status fields are evidence snapshots, not permanent truth. They must be recomputed from current evidence before consequential use.

Long-horizon aspirations remain preserved even when current science, capital, hardware, infrastructure, or law cannot yet support them. Contributors must translate them into prerequisites, testable mechanisms, evidence thresholds, and staged paths rather than deleting or pretending to have achieved them.

The permanent boundary is:

> **Capability may recursively expand. Authority may not recursively expand.**

Dedicated compute, revenue, stronger models, new organs, credentials, wallets, machines, or embodiments do not grant new external authority. Consequential action remains governed by explicit founder-authorized standing authority and the Consequence Gate.

## Active constitutional intent additions

| Intent | Title | State | Canonical record |
|---|---|---|---|
| `INTENT-0029` | Convert every unfinished founder intention into the Infinite Goal Chase living goal graph | active | `docs/intent/INTENT-0029-infinite-goal-chase-living-goal-graph.md` |

## Mandatory Traceability

A material pull request must identify the Intent Records it advances, conflicts with, defers, or supersedes. A change with no traceable intention is either maintenance work or scope drift and must be labeled accordingly.

The canonical ledger should ultimately become machine-readable. Until that implementation lands, issues and ADRs must use these fields verbatim.