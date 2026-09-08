# Goal Chase continuation: decision evidence and founder attention

Status: **EXPERIMENT / SANDBOX ONLY**. Decision: `IGC-ATTENTION-2026-09-08`,
linked to `IGC-SANDBOX-V0` and draft PR #93. Current instruction: Alfonso,
2026-09-08, “continue with implementation and verification”, within the original
master prompt's development-branch, sandbox and draft-PR authorization.
This is a new bounded decision, not a third pass on the original experiment.

## Inspection truth

The recovered local #90-based branch had no implementation. Live inspection found
PR #93 at `21fb21ed803f43e47acb8e6420f6cdc4f74925cd`, with a complete candidate
loop on main `bcbb1ab4a0c42cda4a97aec42a11125753962762`. Its source, evaluator,
contracts, tests, inspection record and handoff were opened before changes.
Reuse that candidate, preserving the earlier #90-based branch. This continuation
depends on unmerged #93; it does not promote it to canonical authority.

All seven repositories were refreshed. Kernel #90 remains the experimental task
reducer; #92 remains design-only; #94 now contains a separate protected evidence
appraisal experiment with three reported baseline seam failures. #95 proposes a
collaboration bootstrap, not an adopted runtime. The new September 7 intent record
preserves persistent institutional work and leaves runtime ownership unresolved.
The default branches and their responsibility map in `GOAL-CHASE-V0.md` remain
the baseline. No organ, runtime stack, compiler, or governance proposal is adopted
by this repair. The two original named founder documents remain unavailable as
full files; the supplied quotations remain intent, not inspected documents.

## Frozen repair contract

The original evaluator, specification and seal remain unchanged. Extend the
acceptance controls, without changing what qualifies a sandbox outcome:

1. A new observation ID, timestamp or source-list ordering with identical source,
   kind, key and complete source records does not replace a still-fresh decision
   basis. Preserve its complete input as `goal.observation_reconfirmed` on the
   existing EventSpine, bound to the original observation digest.
2. The original exact request, scope and expiry remain unchanged. Reconfirmation
   grants no authority and extends neither evidence freshness nor decision expiry.
   When the basis expires, wait for new evidence received after expiry.
3. Any changed quote, eligibility, negative record, source, kind or key remains
   material. Existing exact-scope approval must not cover changed evidence.
4. Observation identities cannot be reused with different bytes across either
   event variant. An observation older than the most recently accepted intake for
   that key is rejected and retained as negative evidence, including after replay.
5. A reconfirmation inconsistent with its retained basis fails replay. An expired
   question is never delivered merely because its communication adapter recovers.
6. Four original paths, authenticated synthetic approval/rejection, interruption
   crash/replay and all original hostile controls must still pass.

## Ownership and exactly two strengthening passes

Five perspectives below are analyses by one coding agent, not independent human
review or delegated-agent consensus. Independent review remains pending.

| Role | Position | Concern and evidence |
| --- | --- | --- |
| Founder-Intent Steward | Repair redundant interruption inside the existing loop | Master prompt §11 allows renewed questions only for material change |
| Systems Architect | Extend only the GoalChase projection | #93 already composes EventSpine, DurableWorkflow, Gate and GenomeRegistry |
| Adversarial Reviewer | Never deduplicate authority by approximate similarity | Scope must retain exact evidence and expiration; negative facts count |
| Operator and Maintainer | Use explicit intake events, no new scheduler/cache | Replay must reconstruct dedupe and ordering from existing records |
| Evidence and Welfare Guardian | Preserve raw confirmations and adverse evidence | Attention savings in fixtures do not measure actual founder welfare |

### Pass 1 — structural strengthening

| Alternative | Benefit | Liability / disposition |
| --- | --- | --- |
| Baseline #93: every new observation replaces the basis | Exact byte binding | Metadata churn creates replacement questions; retain as counterexample |
| Do nothing | No maintenance cost | Leaves observed attention defect; revive if repair weakens authority |
| Simplest alternative: discard repeated intake | Very small patch | Erases source history; reject unless full provenance can be retained |
| Strongest competing design: materiality-aware request rebinding | Can extend freshness continuously | Would revise signed request scope and require new authority semantics; defer |
| Bounded repair: retain reconfirmations, keep fresh basis | Stable actionable question with full history | D1 stale basis, D2 reordered evidence, D3 extra event variant |

Strengthen once: D1 do not extend validity from confirmation; D2 compare all source
records including rejected records and origin, ignoring only identity/time/order;
D3 reuse the observation schema and existing EventSpine, deriving all intake state
from it. No new database, authority registry, workflow or scheduler.

### Pass 2 — adversarial strengthening

Attack: a late observation may roll evidence backward, a duplicate ID may cross
event variants, a dishonest reconfirmation may hide changed facts, and transport
recovery may deliver an already expired request.

- D1 **accepted**: conservative waiting on original basis expiry is explicit;
  new intake after expiry opens a new exact request. Owner: maintainer; trigger:
  a later reviewed continuous-observation policy.
- D2 **experiment**: test all material fields, ordering invariance and changed
  negative evidence. Owner: evidence reviewer; trigger: any observation-schema change.
- D3 **experiment**: validate basis binding during replay and preserve the latest
  intake time as a disposable projection. Owner: maintainer; trigger: replay drift.
- W1 late evidence: reject older intake using the replay-derived high-water mark;
  retain the rejected payload. This prevents silent rollback, not trusted-source
  authentication. Unknown live sources remain outside the sandbox.
- W2 evidence/identity gaming: compare exact typed records, enforce identity across
  both event variants, and reject false reconfirmations on replay.
- W3 hidden stale question: check message expiration at delivery selection.

Final material decision: **EXPERIMENT**. No additional strengthening pass.
Material dissent: keeping an older still-valid basis is intentionally conservative
and cannot prove current external truth. The trusted-host key, immutable-code and
local-lock assumptions of #93 remain. Do not promote the slice to production.

## Mechanism lineage, failure and recovery

This is a domain adaptation of event sourcing, expiring capabilities and change
filtering, not a novelty or patent claim. The existing mechanism map in
`GOAL-CHASE-V0.md` remains the source. The interacting adaptations are:

| Primitive | State and transition | Three adaptations | Proof / failure / recovery |
| --- | --- | --- | --- |
| Event intake | Accepted observation → repeated intake | Preserve raw history; separate material basis from intake identity; allocate founder attention to changed facts | Basis-bound reconfirmation; reject identity collision/late data; rebuild from one spine |
| Expiring decision | Exact request → validated response → bounded execution | Bind retained evidence; deny freshness extension by dedupe; suppress expired transport retries | Existing signed request and Gate receipts; stale basis waits; fresh intake needs its own decision |

Information retained: all source records, rejected sources, timestamps, input IDs,
and approvals. Resource conserved: synthetic founder interruptions; no real benefit
is inferred. Trust boundary: inputs cannot revise authority; equality is exact
over material fields. Selection: retain only a still-fresh basis. Failure behavior:
fail closed with retained negative evidence. Recovery: existing locked sandbox
session and durable replay, followed by new authorized intake when needed.

## Verification and handoff

Record execution evidence alongside this document before claiming repair success.
No production migration is necessary. Rollback: leave the draft unmerged or revert
the repair commits while retaining tests, failed runs and this decision. Historical
reconfirmation events require this reader; older code is not an approved reader
for histories produced by the repair. Preserve a pre-repair ledger when comparing.

Kill criteria: widened/expired approval executes; changed evidence is hidden;
duplicate simulated dispatch; repeated unchanged evidence causes another founder
interruption; negative evidence is lost; or a second institutional control plane
appears. Next bottleneck remains independent review and integration into the
founder-ratified runtime/application owner, after the sandbox proof passes.
