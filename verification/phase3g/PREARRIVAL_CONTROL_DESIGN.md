# PA-2 - Authenticated Pre-Arrival Parent Control Design

## Decision

`RETAIN`

Implement one bounded arrival state inside the existing per-edge canonical
lifecycle record. Authenticate the delivered `Terminal` against the
sender-created probe before marking it held. Apply that same retained object
exactly once, immediately after a context-valid canonical node adopts the same
edge. Do not add a pending dictionary, queue, scheduler rule, or new authority
surface.

Decision owner: Alfonso Lopez. Founder approval was given on 2026-08-03 after
the implementation plan was restated. This design remains draft-PR code with no
promotion, merge, deployment, Gate F/G, or R8 authority.

## Why this narrow mechanism serves the full egregore

The immediate defect is small: a valid parent command can arrive before the
receiver creates its canonical search node and is silently discarded. The
deeper control layer is not message ordering. It is whether the institution can
distinguish four facts without collapsing them:

1. a sender emitted a command;
2. a receiver actually received and authenticated it;
3. a context-valid node adopted the obligation;
4. the node applied the command and produced child-owned completion evidence.

That distinction is a prerequisite for the intended UNIIMENTE architecture:
one constitutional Kernel, bounded organs, durable consequence events,
proof-before-settlement, replayable evidence, and no external consequence based
on inference or model confidence. A developmental substrate that loses or
manufactures commands cannot safely support the later Verified Outcome Control
Plane, Founder Cockpit, Venture Cells, proof credentials, or settlement
adapters. This change earns one local correctness primitive; it does not claim
that those higher layers are complete.

## Inspection truth and intent lineage

The frozen addendum records the inspected corpus and hashes. The binding intent
sequence is:

`Doctrine -> constitutional human sovereignty -> PR #66 verified hold point ->
Issue #67 RESUME_WITH_NAMED_BOTTLENECK -> PA-0/PA-0B diagnosis -> PA-1 frozen
tests -> this PA-2 design`.

Older ADE-1 documents proposed sovereign intent, self-preservation, autonomous
wallets, self-modification, and on-chain action. Those ideas are preserved as
historical or exploratory expression. They are not executable authority because
the later and higher-authority project constitution requires: models reason,
agents propose, authorized humans decide, and only the Kernel may permit
external consequences. `UNAUTHORIZED_EXTERNAL_EFFECTS` remains zero.

## Existing facts

- `Organ.search_edge_lifecycle[edge_id]` is the canonical per-edge record.
- It already separates `accepted_control` from `accepted_outcome`.
- `_emit_terminal` records a control before appending it to the sender outbox.
  Therefore `accepted_control` proves emission, not delivery.
- The sender-created probe already binds edge ID, `SearchKey`, allocation,
  source, and destination before either message arrives.
- `deliver_terminal` currently looks up the canonical node before authenticating
  the sender. With no node, legitimate and forged inputs both increment
  `ORPHANED_SEARCH_EDGES` and disappear.
- The in-memory scheduler normally preserves sender outbox order. The defect
  boundary is reordered transport ingress, reproduced by capturing the real
  outbox objects and delivering them in reverse.

Evidence tier: source inspection plus executable PA-0/PA-0B sandbox diagnosis.
It proves this runtime behavior, not external business acceptance or commercial
effect.

## Canonical state and bounds

The lifecycle record gains one scalar field:

```python
"prearrival_control_state": None | "held" | "applied" | "rejected"
```

It does not gain another `Terminal`. The full retained command remains
`accepted_control`. The existing `controls` list contains at most that one
object. `control_conflicts` contains at most one SHA-256 fingerprint of the
first conflicting full command. Later conflicts and exact replays increment
counters but allocate no further retained objects.

The four live counters are:

- `PREARRIVAL_CONTROLS_HELD`
- `PREARRIVAL_CONTROLS_APPLIED`
- `PREARRIVAL_CONTROL_REPLAYS`
- `PREARRIVAL_CONTROL_CONFLICTS`

Authorization failures continue through
`UNAUTHENTICATED_TERMINAL_CONTROLS`; they create no lifecycle record and never
move the arrival state.

## Full command identity

Replay equality is dataclass equality over the complete canonical `Terminal`,
including kind, `SearchKey`, edge, refund, handling cost, claimed endpoints,
reason, proposal ID, and payload. A same-kind command with any changed field is
a conflict. Its bounded fingerprint is `sha256(_canon(terminal))`.

The live `Unit.step` path passes the original `Terminal` object into the new
internal handler so transport does not discard `reason` or `handling_cost`.
The public `Unit.deliver_terminal(...) -> None` signature remains unchanged and
constructs the equivalent default-valued object for direct callers.

## Admission algorithm

For a `Terminal` arriving before a node exists:

1. Reject nonterminal kinds as today.
2. Read only `search_edge_probes[terminal.edge_id]`.
3. Require a real immediate sender; the test-only harness capability cannot
   allocate pending state.
4. Require exact equality across probe edge, probe `SearchKey`, probe source,
   probe destination, immediate sender, claimed source, and claimed receiver.
5. Require a parent-control kind in the parent-to-child direction.
6. Only then compare the full command with `accepted_control`.
7. If no accepted command exists, retain this one. If the identical command was
   already recorded at sender emission, reuse it without a copy.
8. Move an unset arrival state to `held` and increment `HELD` once.
9. Exact replay increments `REPLAYS`. Conflict increments `CONFLICTS` and
   retains at most one fingerprint. Neither mutates node, credit, projection,
   or edge terminality.

## Adoption and application algorithm

`deliver_search` keeps sender-owned search admission and the complete
`SearchContext` gate first. When a held command exists, an invalid context
returns a fail-closed rejection object without consuming or terminalizing the
held command; a later valid delivery may still adopt it.

For a valid first arrival:

1. Create the canonical node with expansion disabled.
2. Revalidate that the held control still matches the node's adopted edge,
   key, parent sender, and receiver.
3. For `SearchCommitted`, also require a known, eligible proposal. Unknown or
   resolved proposals are rejected exactly as on the normal path.
4. Call the existing `_close_wave_from_parent` once.
5. Move lifecycle state from `held` to `applied` and increment `APPLIED` once.
6. Return before local proposal creation or child expansion.
7. Let the existing acknowledgement path produce child-owned completion and
   reconcile the incoming edge.

If no held control exists, behavior remains the current search path. A control
recorded at sender emission but never delivered has no arrival state and cannot
apply.

## Required internal seams

```python
ControlRecordResult = Literal["accepted", "replay", "conflict"]

Organ lifecycle record:
    accepted_control: Terminal | None
    prearrival_control_state: None | "held" | "applied" | "rejected"
    control_conflicts: list[str]  # length <= 1

Unit._record_control(terminal: Terminal) -> ControlRecordResult

Unit._admit_prearrival_parent_control(
    terminal: Terminal, *, sender: Any
) -> ControlRecordResult | Literal["rejected"]

Unit._apply_recorded_parent_control(
    node: dict[str, Any], *, edge_id: str
) -> bool

Unit._deliver_terminal_message(terminal: Terminal, *, sender: Any) -> None
```

## Five-role constitutional review

### Founder-Intent Steward

Position: retain. The design connects the narrow substrate fix to the full
egregore without pretending the full system is complete. It preserves old ADE
ambitions as history while keeping human sovereignty binding.

Concern: a local fix could become an excuse to optimize substrate indefinitely.
Review trigger: once this bottleneck and the remaining lifecycle inventory are
resolved, return to issue #67's upward roadmap rather than inventing unrelated
substrate features.

### Systems Architect

Position: retain. One lifecycle record remains canonical; emission, delivery,
adoption, application, and outcome stay distinct.

Concern: applying from `accepted_control` without a delivery marker would create
action-at-a-distance. The explicit arrival state is mandatory.

### Adversarial Reviewer

Position: retain only with frozen tests. Attacks include forged sender, wrong
key or destination, altered endpoint claims, child kind in parent direction,
same-kind conflicts, replay floods, conflict floods, emitted-but-undelivered
commands, cross-edge contamination, and failed context adoption.

Concern: conflict telemetry itself can become an unbounded denial-of-service
surface. Retain one fingerprint and count the rest.

### Operator and Maintainer

Position: retain. Four counters and one scalar state are observable without a
new queue, cleanup worker, or scheduler policy.

Concern: unresolved held records have no expiry. Accept temporarily because the
state is one object per authenticated edge; define retention only through a
separate preregistered decision after evidence of actual pressure.

### Evidence and Welfare Guardian

Position: retain. The design fails closed, preserves negative evidence, prevents
forged state allocation, and does not expand external authority.

Concern: passing tests prove runtime behavior only. They do not prove the
developmental substrate outperforms a conventional durable workflow engine,
improves participant welfare, or changes a real settlement decision. R8 and
the later live proof-to-settlement pilot remain separate evidence thresholds.

## Strengthening pass 1

Intended outcome: prevent legitimate reordered controls from disappearing
without allowing untrusted input to allocate receiver state.

Advantages:

- Uses the sender-owned probe available before node creation.
- Preserves one canonical lifecycle record.
- Avoids scheduler coupling and sender replay.
- Makes receiver arrival explicit and auditable.

Disadvantages and redesigns:

| ID | Disadvantage | Redesign |
|---|---|---|
| D1 | `accepted_control` already exists at emission and could be mistaken for arrival. | Add a scalar receiver-arrival state; emission alone never moves it. |
| D2 | Holding before authentication lets forged traffic allocate state. | Authenticate all probe and endpoint facts before lifecycle mutation. |
| D3 | A Unit-local pending map is easy but duplicates canonical truth. | Store no second command or registry; reuse the lifecycle record. |
| D4 | A held record can outlive its missing search. | Bound it to one object per authenticated edge; defer expiry until measured. |
| D5 | Applying after normal node processing may emit proposals or children first. | Create with expansion disabled and apply immediately after initialization. |

Comparison:

- Do nothing: preserves silent loss and unreconciled parent allocation.
- Simplest alternative, reorder scheduler: does not protect distributed ingress.
- Competing architecture, Unit-local pending queue: simpler lookup, duplicate
  truth, cleanup, and replay ambiguity.
- Reversible experiment: frozen direct and real-dispatch tests on one in-memory
  runtime, with no deployment or external effect.

## Strengthening pass 2

Attack: pass 1 can still mistake same-kind mutation for replay, retain unbounded
conflicts, apply across edges, consume state on invalid context, or double-apply
after replay.

New weaknesses and responses:

| ID | Category | Weakness | Response |
|---|---|---|---|
| W1 | gaming | Kind-only equality lets an attacker alter proposal, reason, or endpoints. | Compare the complete canonical `Terminal`. |
| W2 | fragility | Repeated conflicts grow lists without bound. | Retain one fingerprint, count every conflict. |
| W3 | centralization | Scanning lifecycle records could apply one edge's command to another. | Direct lookup by adopted edge only; no scan. |
| W4 | reversibility | A failed context delivery could terminalize the edge and destroy the only valid retry. | Preserve the hold while returning a non-mutating fail-closed rejection. |
| W5 | dependency | Shared sender-side recording can look like delivered state. | Require the receiver-owned state transition to `held`. |
| W6 | evidence | Aggregate counters can pass vacuously. | Pair forged and legitimate controls, real outbox reversal, negative controls, and exact retained-state assertions. |

Pass-1 disadvantage disposition:

- D1 resolved by receiver-arrival state.
- D2 resolved by pre-allocation probe authentication.
- D3 prohibited: no second registry may be introduced.
- D4 accepted temporarily; owner is the Kernel maintainer, review trigger is
  measured authenticated-edge retention pressure.
- D5 resolved by adoption-before-expansion ordering.

Residual risks:

- No garbage collection or durable persistence is introduced.
- A process crash between hold and adoption is not repaired by this in-memory
  change; durable workflow persistence remains a higher-layer requirement.
- Conventional durable workflow architecture still wins the available
  comparative evidence. This change establishes a correctness prerequisite,
  not R8 superiority.

Final recommendation: `RETAIN`.

## Rollback and kill criteria

Rollback is a revert of the runtime commit while preserving the addendum,
frozen tests, design, results, and negative evidence. Marker activation must be
reverted with the runtime if the behavior is withdrawn.

Kill or stop implementation if any of the following occurs:

- authentication must be delayed until adoption;
- unauthenticated input allocates lifecycle state;
- a second pending registry or queue is required;
- emission without delivery applies a command;
- context validation, command/outcome separation, or sender-owned ingress is
  weakened;
- conflicts or replays retain unbounded objects;
- credit, lifecycle, or projection diverges;
- any frozen assertion must be edited to make the runtime pass;
- any existing active test regresses.

## Explicitly unchanged

- Public `deliver_terminal` and `deliver_search` call signatures.
- Scheduler ordering.
- Existing Phase 3G evaluation manifest.
- Eleven pre-existing xfails and the existing skip.
- Gates F/G and R8.
- PR draft state, merge state, and deployment authority.
- Autonomous wallets, treasury, self-preservation, self-modification, public
  posting, and all other external-effect capabilities.
