# Founder Command Ordering Guard — Design

**Status: PLAN ONLY.** Nothing here is implemented. This document changes no
runtime authority and no production code.

**Originating evidence:** `docs/release/canonical-v1/GOVERNANCE_INCIDENT_001.md`
(on `release/canonical-v1-manifest`) — `COMMAND_ORDERING_AND_STALENESS_CONTROL_FAILURE`,
`PROCESS_CONTROL_HIGH / CONSEQUENCE_LOW`.

**Planning base:** `main` @ `8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1`

---

## 0. What this is, and what it must never become

The Guard answers exactly one question, immediately before any consequential
write:

> *Is the instruction I am about to act on still the latest applicable
> instruction for this authority scope, and does the world still look the way
> that instruction expected?*

**It creates no authority.** It is a *precondition* on acting, never a source of
permission. An instruction that passes the Guard is not thereby authorized; it
is merely not stale. Authorization continues to come from the Constitution, the
authority matrix, the legal-principal registry, and the Consequence Gate — all
of which remain singular.

Per Final Build Order §3 and canonicality audit claims 1–4, this design
introduces:

- **no** second Constitution
- **no** second authority matrix
- **no** second identity system
- **no** second Consequence Gate

The Guard sits *in front of* the existing Consequence Gate for external-effect
classes, and in front of the merge/commit path for repository classes. It can
only ever **subtract** permission — turn a "yes" into a "stop". It has no code
path that turns a "no" into a "yes". That asymmetry is the single most important
property in this document and every test below exists to defend it.

---

## 1. The command envelope

```yaml
instruction_id:              # stable unique id, e.g. "fi-2026-07-27-001"
sequence_number:             # monotonic integer, comparable ONLY within `scope`
issued_at:                   # RFC3339 UTC, advisory only — never the ordering key
issued_by:                   # named HUMAN principal, e.g. "alfonso_lopez"
authority_basis:             # which authority permits this at all (constitutional cite)
scope:                       # the ordering domain the sequence counter belongs to
target_repository:           # e.g. "dababiyoda/uniimente-kernel"
target_branch:               # e.g. "main"; absent = no branch-targeted action
expected_state:              # refs/SHAs/CI/permissions that must hold at execution
authorized_actions:          # explicit allowlist
prohibited_actions:          # explicit denylist
supersedes:                  # list of instruction_ids this replaces
expires_at:                  # RFC3339 UTC; absent means "single use, no reuse"
stop_conditions:             # conditions that must halt execution mid-flight
required_reverification:     # checks to re-run immediately before execution
consequence_class:           # exactly one, from the enum in §2a
founder_confirmation_required:  # bool; true forces a fresh human confirmation
```

### Field notes that carry design weight

**`sequence_number` is the ordering key. `issued_at` is not.** Clocks disagree,
messages arrive out of order, and a resent older message carries an older
timestamp with no indication it is a resend. Incident 001 happened in a world
where recency of *arrival* was the only available proxy. Wall-clock time is a
different, equally unreliable proxy. Only an explicit monotonic counter under a
named authority scope is decidable.

**`scope` and `authority_basis` are deliberately two fields, not one.**
`authority_basis` answers *what permits this at all* — a constitutional citation.
`scope` answers *which ordering domain this sequence counter lives in*. Merging
them was the first draft and it was wrong: two instructions can share a
constitutional basis while belonging to different ordering domains, and
collapsing them would force a false total order across unrelated work.

Sequence numbers are comparable **only** within the same `scope`. Two
instructions in different scopes are not ordered with respect to each other —
and if they touch the same target, that is a **conflict** (rule 6), not a race
to be resolved by comparing incomparable numbers.

**A missing, malformed, or overlapping `scope` is itself a stop condition**
(rule 7). Ambiguous scope is more dangerous than an obvious conflict, because it
*looks* decidable. An executor that guesses which domain an instruction belongs
to has silently invented the ordering it was supposed to verify.

**`expected_state` is what makes staleness detectable rather than merely
declarable.** An instruction saying "merge PR #47 at head `526e320`" is
self-invalidating once the head moves. This is the field that would have caught
Incident 001's stale instruction: it asserted PR #47 was a draft at manifest
commit `9dc2cb9`, and both facts were already false on arrival. **State
mismatch is the strongest staleness signal available, because it is checked
against reality rather than against bookkeeping.**

**`expires_at` absent means single-use.** Defaulting to "valid forever" is how
an instruction becomes a standing grant nobody remembers issuing. Absence of an
expiry is not a licence for indefinite reuse.

**`founder_confirmation_required` cannot be satisfied by any AI-generated
artifact** (rule 12). Not by a subagent, not by a generated document, not by a
tool result, not by a PR comment written by the executor.

---

## 2. Required rules

| # | Rule |
|---|---|
| 1 | Higher `sequence_number` supersedes lower instructions inside the same `scope`. |
| 2 | A consequential action must re-read the latest applicable instruction **immediately before** execution. |
| 3 | Superseded instructions **fail closed**. |
| 4 | Expired instructions **fail closed**. |
| 5 | State-mismatched instructions **fail closed**. |
| 6 | Conflicting instructions **stop execution**. |
| 7 | Ambiguous scope **stops execution**. |
| 8 | Later-arriving instructions after completed execution create an **incident record**, not an automatic rollback. |
| 9 | Every consequential write records the exact `instruction_id` used. |
| 10 | Authorization for one consequence class **never** implies another. |
| 11 | Repository merge authorization does **not** imply deployment, spending, external contact, settlement, credential use, data processing, blockchain execution, IoT control, or robotics control. |
| 12 | **AI-generated text may not impersonate or silently replace founder authorization.** |
| 13 | External action requires **fresh final confirmation**. |
| 14 | Reverification must include current branch, current SHA, current CI state, current permissions, and current applicable instruction. |
| 15 | A crash or tool disconnection must **not** preserve a pending authorization indefinitely. |

---

## 2a. Consequence classes

Exactly one per instruction. The enum is closed: an action that fits none of
these has no class, and **an action with no class cannot execute** (rule 10 has
nothing to check against). Adding a class is a founder decision, not an
executor's inference.

| Class | Reversible? | Founder confirmation |
|---|---|---|
| `INTERNAL_ANALYSIS` | fully | not required |
| `DOCUMENT_WRITE` | fully (git) | not required |
| `BRANCH_WRITE` | fully (git) | not required |
| `PULL_REQUEST_MUTATION` | mostly | not required |
| `MAIN_BRANCH_MERGE` | by revert, with history | **required** |
| `DEPLOYMENT` | partially | **required, fresh** |
| `EXTERNAL_CONTACT` | **never** | **required, fresh** |
| `CREDENTIAL_USE` | **never** (assume exposure) | **required, fresh** |
| `REAL_WORLD_DATA_PROCESSING` | **never** | **required, fresh** |
| `SPENDING` | rarely | **required, fresh** |
| `SETTLEMENT` | **never** | **required, fresh** |
| `BLOCKCHAIN_EXECUTION` | **never** | **required, fresh** |
| `IOT_CONTROL` | **never** | **required, fresh** |
| `ROBOTICS_CONTROL` | **never** | **required, fresh** |

**The ordering of this table is not a severity ranking, and must not be read as
one.** It is grouped by reversibility. `EXTERNAL_CONTACT` sits above `SPENDING`
because an email cannot be unsent while a payment can sometimes be clawed back —
not because contact matters more than money. An executor that treats the list as
a ladder and reasons "I was authorized for class N, so N−1 is implied" has
violated rule 10. **There is no ladder. Every class is a separate lock.**

Incident 001 was `MAIN_BRANCH_MERGE`. Nothing about that authorization touched
any class below it in this table, and the incident record says so explicitly.

### Why `CREDENTIAL_USE` is marked irreversible

A credential that has been used has been transmitted, logged somewhere outside
UNIIMENTE's control, and possibly cached. Rotation limits future damage; it does
not undo the use. Marking it "reversible because we can rotate" would be the
same category error as calling an email reversible because a correction can be
sent.

---

## 2b. Founder confirmation flow

Applies to every class marked *required* above. "Fresh" means obtained **after**
the final reverification, not carried forward from planning.

```
1. Executor completes reverification (rule 14): branch, SHA, CI state,
   permissions, applicable instruction — all re-read now, none cached.
2. Executor presents an UNAMBIGUOUS confirmation request stating:
     - the exact action, in one sentence
     - the consequence class
     - the instruction_id being acted under
     - what was reverified, and what each check returned
     - what is IRREVERSIBLE about it
     - what happens if the executor is wrong
3. Founder responds with an explicit affirmative.
4. Executor re-reads the applicable instruction ONE more time (rule 2).
5. Execute. Record instruction_id + confirmation reference (rule 9).
```

**Silence is not confirmation. Absence of objection is not confirmation. A prior
approval of a similar action is not confirmation.** An affirmative that does not
name the action is not confirmation of *that* action.

**The confirmation must not be solicited in a form that makes "yes" the path of
least resistance.** A request that buries the irreversible consequence beneath
reassurance is a defective request even if the founder says yes. Step 2's
"what is irreversible" line is mandatory and must not be softened.

**Step 4 is not redundant with step 1.** The founder's deliberation takes real
time, and that time is a window in which the applicable instruction can change.
Skipping step 4 because step 1 already passed reintroduces exactly the staleness
gap this Guard exists to close.

### Rules that are easy to state and easy to get wrong

**Rule 2 — "immediately before" is a real constraint, not a figure of speech.**
There is always a window between the check and the write. The design goal is to
make that window as small as the transport allows and to *record its size*,
never to claim it is zero. Incident 001's merge used exactly this pattern
manually — re-read head, merge, verify parent — and the manifest records it as
"a narrow-window check, not an atomic precondition." The Guard must preserve
that honesty. Where the underlying API offers a genuine atomic precondition
(a compare-and-swap ref update, an `expected_head_sha` parameter), the Guard
**must** use it and record that it did. Where none exists, it must record the
weaker guarantee rather than describing the window away.

**Rule 8 is the anti-rollback rule, and it is counter-intuitive.** The instinct
on discovering "I acted on something now superseded" is to undo it. The rule
forbids that, because a silent rollback is itself an unauthorized consequential
write, performed under an instruction that never authorized *undoing* anything.
The correct response is: stop, record, escalate. Incident 001 followed this rule
before it was written.

**Rule 12 is the one an autonomous system is most likely to erode**, not by
forging an instruction but by *treating its own inference as one* — "the founder
would clearly want X," "the plan implies Y." The Guard's answer: an instruction
exists only if it carries an envelope traceable to `issued_by` as a named human
principal. There is no inference path to authorization. This is the ordering
counterpart of the standing rule that **intelligence never creates authority**.

---

## 3. State machine

```
                    ┌──────────┐
                    │ RECEIVED │
                    └────┬─────┘
                         │ parse envelope
              ┌──────────┴──────────┐
              │                     │ malformed / unparseable
              ▼                     ▼
        ┌───────────┐         ┌──────────┐
        │ REGISTERED│         │ REJECTED │ (terminal, recorded)
        └─────┬─────┘         └──────────┘
              │ compare sequence_number within authority_basis
      ┌───────┼────────────────┬─────────────────┐
      │       │                │                 │
      ▼       ▼                ▼                 ▼
┌─────────┐ ┌──────────┐ ┌───────────┐   ┌──────────────┐
│ CURRENT │ │SUPERSEDED│ │  EXPIRED  │   │  CONFLICTED  │
└────┬────┘ └────┬─────┘ └─────┬─────┘   └──────┬───────┘
     │           │             │                 │
     │           └─────────────┴─────────────────┘
     │                         │
     │                         ▼
     │                  ┌─────────────┐
     │                  │ FAILED_CLOSED│ (terminal; escalate to founder)
     │                  └─────────────┘
     │ consequential action requested
     ▼
┌──────────────┐   re-read latest (rule 2)   ┌──────────────┐
│ PRE_EXECUTION├────────────────────────────►│ REVALIDATING │
└──────────────┘                             └──────┬───────┘
                                                    │
                        ┌───────────────────────────┼──────────────────────┐
                        │ still CURRENT             │ no longer CURRENT    │
                        │ + expected_state holds    │ OR state mismatch    │
                        ▼                           ▼                      │
                 ┌─────────────┐            ┌──────────────┐               │
                 │  EXECUTING  │            │ FAILED_CLOSED│               │
                 └──────┬──────┘            └──────────────┘               │
                        │                                                  │
         ┌──────────────┼──────────────┐                                   │
         │ success      │ failure      │ crash / timeout                   │
         ▼              ▼              ▼                                   │
   ┌──────────┐  ┌──────────┐   ┌──────────────┐                           │
   │ EXECUTED │  │  FAILED  │   │  INDETERMINATE│──► reconcile (§7)         │
   └────┬─────┘  └──────────┘   └──────────────┘                           │
        │                                                                  │
        │ later instruction arrives contradicting an EXECUTED write        │
        ▼                                                                  │
   ┌──────────────────┐                                                    │
   │ INCIDENT_RECORDED│ (rule 8 — never auto-rollback) ◄───────────────────┘
   └──────────────────┘
```

**`INDETERMINATE` is the state most designs omit and most need.** A crash
between "gate passed" and "effect confirmed" leaves the executor unable to say
whether the effect happened. Treating that as failure and retrying is how one
authorized payment becomes two. §7 handles it.

**There is no transition from `FAILED_CLOSED` back to `EXECUTING`.** Recovery
requires a *new* instruction with a higher `sequence_number`. An executor cannot
argue its way out of a closed failure.

---

## 3a. Conflict-resolution state

`CONFLICTED` is a **terminal state pending founder input**, not a transient one.
There is no automatic exit.

```
CONFLICTED
  ├── founder issues a new instruction with a higher sequence_number
  │     in an unambiguous scope                          → RESOLVED → REGISTERED
  ├── founder explicitly withdraws one instruction        → RESOLVED → REGISTERED
  └── no founder response                                 → remains CONFLICTED
                                                             (nothing executes)
```

**Deadlock is the correct behavior, not a bug to be engineered around.** An
executor that cannot determine which instruction is current must not act. The
cost of a stalled pipeline is a delay; the cost of guessing is an unauthorized
consequential write. Any future pressure to add a tie-breaker — "prefer the more
specific scope", "prefer the more recent arrival", "prefer the more restrictive
instruction" — should be read as a request to reintroduce Incident 001.

The one apparent exception is not an exception: **`prohibited_actions` beats
`authorized_actions` within a single envelope** (case C3). That is not conflict
resolution between instructions, it is precedence inside one, and even then the
envelope is rejected rather than silently narrowed — because a self-contradictory
instruction means the author's intent is unknown.

While `CONFLICTED`, the executor may still perform `INTERNAL_ANALYSIS`. It may
not perform any other class, including `DOCUMENT_WRITE`, if the document would
assert a resolution the founder has not made.

---

## 4. Stale-command examples

### S1 — Incident 001, exactly (the resent instruction)

```yaml
instruction_id: fi-2026-07-26-002
sequence_number: 2
authority_basis: uniimente-kernel/release
expected_state:
  pull_request_47_draft: true
  manifest_branch_head: 9dc2cb9
authorized_actions: [record_archive_proof, update_pr_body]
prohibited_actions: [merge_pull_request, mark_ready_for_review]
```

Arrives when `sequence_number: 3` (the release gate) has already executed.
**Two independent detections fire:**

1. **Sequence:** `2 < 3` within the same `authority_basis` → `SUPERSEDED`.
2. **State:** PR #47 is not a draft; manifest head is `c6a4ddc`, not `9dc2cb9`
   → state mismatch.

Result: `FAILED_CLOSED` for the prohibited actions, plus `INCIDENT_RECORDED`
under rule 8, because instruction 3 had already been executed. The
non-conflicting authorized actions may proceed **only** under a fresh
instruction — not salvaged from the stale envelope.

**Two independent detections is the design target, not redundancy.** Sequence
checking fails if the founder forgets to increment. State checking fails if the
instruction omits `expected_state`. Either alone is a single point of failure.

### S2 — Expired standing authorization

```yaml
instruction_id: fi-2026-07-20-004
sequence_number: 4
expires_at: 2026-07-21T00:00:00Z
authorized_actions: [external_contact]
```

Invoked 2026-07-27. → `EXPIRED` → `FAILED_CLOSED`. Even though nothing
superseded it and no state changed, and even though the founder's *intent*
plausibly still holds. Rule 4 is not intent-sensitive; that is the point.

### S3 — Silent state drift with no competing instruction

Instruction authorizes merging PR #47 at head `526e320`. Between issuance and
execution a commit lands on the branch. Sequence check **passes** — nothing
superseded it. `expected_state` check **fails**. → `FAILED_CLOSED`.

This is the case where sequence numbering alone would wave through a write
against content the founder never reviewed. **S3 is the argument for
`expected_state` being mandatory rather than optional on any consequential
instruction.**

### S4 — Replayed instruction with no expiry

An instruction with no `expires_at` is submitted a second time after successful
execution. Single-use default applies: the `instruction_id` is already in
`EXECUTED`. → `REJECTED`, recorded. No idempotent "re-run" path exists for
consequential classes.

---

## 5. Conflicting-command examples

### C1 — Cross-scope conflict, same target

Two instructions, `authority_basis: uniimente-kernel/release` seq 7 and
`authority_basis: uniimente-kernel/operations` seq 2, both targeting `main`.
Sequence numbers are **not comparable** across scopes. → `CONFLICTED` → stop,
escalate to founder. The executor must not pick the higher raw integer, the more
recent arrival, or the more specific-sounding scope.

### C2 — Same scope, same sequence number, different content

A duplicate or transmission error. Neither supersedes the other. → `CONFLICTED`
→ stop. Never "last write wins."

### C3 — Contradictory actions in the same envelope

`authorized_actions: [merge_pull_request]` with
`prohibited_actions: [merge_pull_request]`. → `REJECTED` at parse time.
**Prohibition always wins over authorization within an envelope**; but the
envelope is still rejected rather than silently narrowed, because a
self-contradictory instruction indicates the author's intent is unknown.

### C4 — Chained supersession with a gap

Instruction 9 declares `supersedes: [7]`, but 8 exists and is unaccounted for.
→ `CONFLICTED`. A supersession chain with a hole means the executor cannot
establish what is current. It does not assume 8 was withdrawn.

### C5 — An AI-generated envelope

Any envelope whose `issued_by` resolves to a non-human principal, or which
arrives via a path that cannot be traced to a named human, → `REJECTED` under
rule 12, and recorded as an attempted authority substitution regardless of
whether the content was benign. **The severity attaches to the impersonation,
not to the payload.**

---

## 6. Retry, timeout, crash recovery

### Retry

| Class | Retry policy |
|---|---|
| Read / validation | Free retry with backoff. No consequence. |
| Repository write | Retry permitted **only** after full re-validation (rules 2-5, 14). Each attempt records its own `instruction_id` + attempt number. |
| External effect | **No automatic retry.** Requires fresh founder confirmation (rule 13). |

A retry is a **new execution attempt**, not a continuation. It re-enters
`PRE_EXECUTION` and re-reads. An executor that caches "I already validated this"
across a retry has reintroduced exactly the staleness window the Guard exists to
close.

### Timeout

Every consequential action declares a maximum execution window. On expiry the
action moves to `INDETERMINATE`, **not** `FAILED`. The distinction matters: a
timed-out payment may well have succeeded. Only reconciliation against the
external system may resolve `INDETERMINATE`.

### Crash recovery

On restart the executor must, before any new consequential action:

1. Load all instructions in non-terminal states.
2. Resolve every `INDETERMINATE` record by reconciling against the actual target
   system — the repository, the payment processor, the mail log — never by
   inference from local state.
3. Re-run supersession and expiry checks against the *current* instruction set.
4. Fail closed on anything unresolvable, and escalate.

**Nothing about the Guard's own state may be inferred from a stored default.**
This mirrors the Package 4 seam property: the default is the *absence* of a
choice, not a persisted one. An executor that restarts and finds no explicit
current instruction has **no** authorization — not "the last one it remembers."

---

## 7. Audit record

One record per consequential write attempt, append-only, chained:

```json
{
  "record_id": "…",
  "instruction_id": "fi-2026-07-26-003",
  "sequence_number": 3,
  "authority_basis": "uniimente-kernel/release",
  "consequence_class": "repository_merge",
  "action": "merge_pull_request(47, method=merge)",
  "expected_state_asserted": {"pr_47_head": "526e320…"},
  "expected_state_observed":  {"pr_47_head": "526e320…"},
  "revalidated_at": "2026-07-26T22:30:29Z",
  "executed_at":    "2026-07-26T22:30:31Z",
  "revalidation_window_ms": 2000,
  "atomic_precondition_available": false,
  "atomic_precondition_note": "merge_pull_request exposes no expected-head SHA parameter",
  "outcome": "EXECUTED",
  "result_reference": "8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1",
  "post_verification": {"parent_2": "526e320…", "matched": true},
  "prev_record_hash": "…",
  "record_hash": "…"
}
```

`revalidation_window_ms` and `atomic_precondition_available` are mandatory. They
are what let a future auditor distinguish a genuine precondition from a narrow
check described as one. Incident 001's merge would produce exactly the record
above, with `atomic_precondition_available: false` — an honest record of a real
weakness rather than an implied guarantee.

Audit records go to the **existing** evidence ledger through the existing
append-only chain with pre-append validation. No new ledger.

---

## 8. Tests

### 8a. Hostile tests

An adversary — or a confused executor — actively trying to get an unauthorized
write through. Each must fail the build if the property breaks.

| # | Attack | Must produce |
|---|---|---|
| A1 | Replay a superseded instruction | `FAILED_CLOSED`; zero effect |
| A2 | Submit seq `N-1` after seq `N` executed | `SUPERSEDED` + `INCIDENT_RECORDED` |
| A3 | Mutate target state between validation and execution | `FAILED_CLOSED` on `expected_state` |
| A4 | Two instructions, incomparable scopes, same target | `CONFLICTED`; no auto-resolution |
| A5 | Envelope with `issued_by` = an agent | `REJECTED` under rule 12 |
| A6 | Crash between gate-pass and effect | `INDETERMINATE`; **no** auto-retry |
| A7 | Repository authorization used for an external effect | denied under rules 10-11 |
| A8 | Instruction attempting to widen its own `authorized_actions` | `REJECTED` |
| A9 | Guard asked to turn a Gate denial into an approval | **structurally impossible** — no such code path exists |
| A10 | Expired instruction whose intent is obviously still valid | `FAILED_CLOSED` — intent is not a bypass |
| A11 | Clock skew makes `issued_at` newer on the older instruction | ordering unaffected; `sequence_number` decides |
| A12 | Supersession chain with a gap | `CONFLICTED`, not "assume withdrawn" |
| A13 | Duplicate `instruction_id`, different content | `REJECTED` |
| A14 | Guard disabled or bypassed by config | consequential writes **refuse**; absence of the Guard is not permission |

**A9 and A14 are the load-bearing ones.** A9 defends the subtract-only property.
A14 defends against the failure mode where a safety component's absence is read
as "unconstrained" rather than "not authorized" — the same principle as
`deny_by_default` in the Constitution.

### 8b. Negative tests — the Guard must also say yes

In the spirit of Package 4's duplicating-engine control. **A guard that refuses
everything passes every hostile test in §8a and is worthless.** These prove the
measurement can succeed, not only fail.

| # | Case | Must produce |
|---|---|---|
| N1 | Correctly sequenced, state-matched, unexpired instruction | **executes**, `instruction_id` recorded |
| N2 | Two instructions, different scopes, different targets | both execute; no spurious conflict |
| N3 | Supersession chain 1→2→3 with no gaps | instruction 3 executes; 1 and 2 fail closed |
| N4 | `INTERNAL_ANALYSIS` with no founder confirmation | **executes** — confirmation is not required for this class |
| N5 | Reverification passes on all five of rule 14's checks | proceeds without escalation |
| N6 | Instruction with `expires_at` in the future | executes; expiry is not treated as "present therefore suspect" |

**N2 and N4 are the ones most likely to break in a real implementation**, because
the natural defensive reflex is to widen conflict detection and to demand
confirmation everywhere. Both reflexes are failures: N2 turns unrelated work into
a deadlock, and N4 trains the founder to approve reflexively, which destroys the
value of confirmation in the classes that actually need it.

### 8c. Race-condition tests

The window between check and write is real (rule 2). These characterize it rather
than pretend it away.

| # | Race | Must produce |
|---|---|---|
| R1 | Target SHA changes between reverification and write | write **fails**; where the API offers an atomic precondition it must be used, and its absence recorded |
| R2 | Superseding instruction arrives during the confirmation wait | step 4's re-read catches it → `FAILED_CLOSED`, no execution |
| R3 | Superseding instruction arrives *during* the write | `INCIDENT_RECORDED` (rule 8); **no auto-rollback** |
| R4 | Two executors act on the same instruction concurrently | at most one write; the second fails closed on single-use |
| R5 | CI transitions green→red between reverification and write | write fails; CI state is part of rule 14 |
| R6 | Crash between gate-pass and effect-confirm | `INDETERMINATE`; reconcile against the real system, never retry blind |
| R7 | Pending authorization outstanding when the tool disconnects | authorization **expires**; it must not survive the disconnection (rule 15) |

**R3 is the case Incident 001 would have hit** had the conflicting instruction
arrived seconds earlier. The required outcome is an incident record, not a
rollback — the same discipline the incident itself followed.

**R7 is the rule-15 test and the easiest to omit.** A pending confirmation that
survives a disconnection is a standing authorization nobody is watching. It must
decay.

---

## 9. Smallest implementation seam

Following the Package 4 precedent — a narrow governed seam at real call sites,
not a parallel control plane.

**Proposed:** one module, `governance/ordering_guard.py`, exposing:

```python
def check(instruction_id: str, consequence_class: str, expected_state: dict) -> Verdict
def record(verdict: Verdict, outcome: str, result_reference: str) -> None
```

Call sites, all of which already exist as chokepoints:

| Consequence class | Seam |
|---|---|
| repository write | the merge/push path |
| external effect | immediately **before** `policy/consequence_gate.py`, never inside it |

**The Guard must not be placed inside the Consequence Gate.** Two reasons: the
Gate is the single canonical authority for external effects and must not acquire
a second responsibility (audit claims 4 and 9); and the Guard must also cover
repository writes, which never reach the Gate at all.

Deliberately **absent** from the API, mirroring the Package 4 seam's missing
`set_default()`:

- no `override()`
- no `disable()`
- no `set_current_instruction()` callable by an executor
- no path by which a checked action registers its own authorization

An executor can *ask* the Guard and *record* the answer. It cannot change the
answer.

---

## 10. Rollback design

The Guard is additive and subtract-only, so rollback is removal of a
precondition — never restoration of a permission.

| Property | Design |
|---|---|
| Default when absent | consequential writes **refuse** (test A14) |
| Enable/disable | not a runtime flag; presence of the seam is structural |
| Removal | delete the call sites; the underlying Gate and authority path are unchanged and still enforce everything they enforced before |
| State on rollback | audit records are **retained** — they are evidence, not Guard-local state |
| Preservation | per Final Build Order §12, a superseded Guard version is marked `SUPERSEDED`, never deleted |

**Rolling back the Guard cannot grant anything.** Before it exists, external
effects require the Consequence Gate; after removal, they require the
Consequence Gate. The only thing lost is the staleness check — which is a
reduction in safety and must be recorded as one, not presented as neutral.

---

## 10a. Protocol review — how strong should the Guard be?

Applying the Recursive Founder-Intent Collaboration Protocol to the one decision
everything else follows from: **where the Guard sits and how much it blocks.**

### Positions

**Builder.** Put the Guard in front of every consequential write, with the full
envelope. It closes Incident 001's defect at the root and generalizes to
spending, contact, and physical control. The seam is narrow and mirrors the
Package 4 provider seam, which is already proven at the canonical boundary.

**Adversary.** The Guard is a new *unimplemented* dependency sitting on the
critical path of every write. Three attacks. First, the envelope depends on the
founder correctly assigning `sequence_number` and `scope` — a human process step
that will be skipped under time pressure, and then the Guard degrades to
`expected_state` alone. Second, a Guard that blocks too much trains everyone to
route around it. Third, and worst: **the Guard makes the system *feel* safe for
external actions when the actual protection is still the Consequence Gate.** A
false sense of coverage is more dangerous than no Guard.

**Operator.** The confirmation flow adds a human round-trip to every merge to
`main`. At current velocity that is several interruptions per session. If it
becomes tedious, the founder will pre-approve in bulk, which is exactly the
standing-grant failure `expires_at` exists to prevent.

**Beneficiary representative.** No external participant is affected today — no
customer, no patient, no counterparty exists. The beneficiary is *future*: the
first real customer, whose data or money is exposed to the first genuine
ordering error. That beneficiary cannot advocate now, which is precisely why the
protection must be built before they exist rather than after the first incident
involving them.

**Constitutional reviewer.** The Guard is admissible **only** because it is
subtract-only and creates no authority. If any version acquired the ability to
approve, it would become a second authority path and violate audit claims 1–4
and 9. The design must be re-reviewed against those claims at implementation, not
only at design.

### Alternatives

| # | Option | Verdict |
|---|---|---|
| 1 | **Strongest proposed** — full envelope, all 15 rules, all 14 classes, Guard before every consequential write | high coverage; highest unimplemented surface; slowest |
| 2 | **Simplest viable** — `expected_state` precondition only, no sequence numbers, no envelope | catches Incident 001 (S1 state check) and case S3; misses C1/C2/C4 conflicts entirely; ~10% of the work |
| 3 | **Strongest conventional competitor** — branch protection + required reviews + CODEOWNERS + signed commits, all off-the-shelf GitHub features | genuinely strong for repository classes; **zero** coverage for spending, contact, credentials, or physical control; costs nothing to run |
| 4 | **Reversible experiment** — Guard in *observe-only* mode: evaluates, records a verdict, blocks nothing | measures how often it would have fired, at zero deadlock risk; produces evidence instead of assumptions |
| 5 | **Do nothing** — rely on the incident record and executor discipline | free; the executor already behaved correctly under Incident 001 without a Guard; but that is one sample, and discipline is not a control |

**The conventional competitor is stronger than it first appears and must not be
dismissed.** Branch protection with required checks would have made Incident 001
*structurally* harder, using mature infrastructure, with no code to write and no
new failure mode. Its gap is that it protects exactly one consequence class.

### Upward pass 1 — remove, bound, reverse, observe, convert each disadvantage

| Disadvantage | Treatment |
|---|---|
| Unimplemented surface on the critical path (Adversary 1) | **Bound**: implement classes in reverse order of reversibility — `EXTERNAL_CONTACT` and above first, `BRANCH_WRITE` last. The classes that need it most are also the rarest, so the critical path is barely touched. |
| Human sequence-numbering will be skipped (Adversary 1) | **Convert**: make `expected_state` mandatory and treat sequence numbering as the *secondary* check. Degradation then lands on the stronger signal, not the weaker one. |
| People route around a Guard that blocks too much (Adversary 2) | **Remove**: no confirmation for `INTERNAL_ANALYSIS`, `DOCUMENT_WRITE`, `BRANCH_WRITE`, `PULL_REQUEST_MUTATION` — test N4 enforces this. Friction is spent only where reversibility is absent. |
| False sense of coverage (Adversary 3) | **Observe**: audit records carry `atomic_precondition_available`; §0 states the Guard adds nothing to the Gate's authority. The claim is bounded in writing. |
| Operator round-trips (Operator) | **Bound**: confirmation required only for `MAIN_BRANCH_MERGE` and above — a handful of events, not a per-commit tax. |
| Bulk pre-approval drift (Operator) | **Reverse**: `expires_at` absent ⇒ single-use, so bulk approval is not expressible in the envelope at all. |
| Second-authority risk (Constitutional reviewer) | **Remove**: no `override()`, no `disable()`, no `set_current_instruction()`; test A9 asserts no approve-path exists. |
| Conventional competitor's coverage gap (Alt 3) | **Convert into a dependency, not a rival**: adopt branch protection *as well*, for the repository classes. The Guard then only needs to cover what GitHub cannot see. |

**Strengthened design: alternatives 3 + 4 + 1, in that order.** Branch protection
now (free, mature, covers `MAIN_BRANCH_MERGE`); Guard in observe-only mode next
(evidence, no deadlock); full blocking Guard for irreversible classes only when
one of those classes is actually about to be exercised.

### Upward pass 2 — attack the strengthened design

1. **Observe-only mode may never graduate.** A Guard that has run for months
   without blocking becomes furniture, and switching it to blocking will feel
   like a regression. *Response:* the graduation trigger is not a date or a
   confidence level — it is the **first instruction carrying a class of
   `EXTERNAL_CONTACT` or above**. Kill condition K7 in the CVO packet already
   binds it.
2. **Branch protection could lock out the only operator.** If required reviews
   are configured on a single-maintainer repository, the founder may be unable to
   merge at all. *Response:* configure required *status checks* rather than
   required *reviewers*. Checks are already green and already gate correctly.
3. **Two mechanisms mean two places to be wrong.** *Response:* accepted, and it
   is the right trade. They fail independently: GitHub enforces server-side and
   cannot be talked out of it; the Guard enforces semantically and covers classes
   GitHub cannot see. Correlated failure would require both to break at once.
4. **Reverse-order implementation means the most-used classes are unguarded
   longest.** *Response:* correct, and deliberate. Those classes are reversible.
   Spending the first implementation effort on `BRANCH_WRITE` would protect the
   thing `git revert` already protects.
5. **The strengthened design still rests on rule 12, which rests on a procedural
   identity binding.** *Response:* unresolved. Recorded in §11 as a founder
   decision. **No amount of ordering discipline substitutes for knowing who
   issued the instruction**, and this design does not claim otherwise.

### Preserved dissent

**The Adversary's third attack is not fully answered.** Documenting that the
Guard adds no authority does not stop a future reader from treating its presence
as evidence that external actions are safe. Documentation is a weak control
against a strong cognitive bias. The only real mitigations are that the Guard
*blocks* rather than merely advises in the irreversible classes, and that
`atomic_precondition_available` makes weak checks legible. Neither eliminates the
risk.

**The "do nothing" option retains a genuine argument.** Under Incident 001 the
executor stopped, disclosed, and refused to auto-rollback — with no Guard
present. One sample is not a control, but it is evidence that the failure mode
was detection, not response. A cheaper intervention aimed only at detection
(mandatory `expected_state` in instructions, nothing else) might capture most of
the value. This is not the recommendation, but it is not foolish.

### Founder-reserved decisions from this review

1. Enable branch protection with required status checks on `main` — an
   administrative action this session cannot perform.
2. Approve or reject the reverse-order (irreversible-first) implementation order.
3. Approve observe-only as the initial mode, with graduation bound to K7.
4. Decide the signing question in §11 item 3, on which rule 12's strength depends.

---

## 11. Open questions requiring founder decision

Not decidable by this session; listed so implementation does not invent answers.

1. **Who may issue envelopes** besides Alfonso, and under what delegation — if
   any. Rule 12 fixes that they must be human; it does not fix *which* humans.
2. **How `authority_basis` scopes are named and bounded.** Wrong granularity
   produces either false conflicts (too fine) or false ordering (too coarse).
3. **Whether a cryptographic signing mechanism will exist.** Every ratification
   to date, including canonical-v1's, is operator-recorded rather than signed.
   The Guard's rule-10 check is only as strong as the identity binding beneath
   it, and today that binding is procedural.
4. **Sequence-number assignment in practice** — manual, or issued by tooling
   the founder controls. Manual numbering will be skipped or reused eventually;
   `expected_state` is the backstop, which is why it is mandatory.
5. **Whether Guard implementation blocks CVO-001**, or runs in parallel with
   plan-only commercial preparation. This document's position: it must block any
   *external* action, and need not block planning.

---

## 12. Relationship to existing canonical components

| Component | Relationship |
|---|---|
| Constitution | unchanged; the Guard adds no rule to it |
| Authority matrix | unchanged; the Guard grants nothing |
| Legal-principal registry | unchanged; the Guard reads identity, never writes it |
| Consequence Gate | unchanged; the Guard runs strictly before it and cannot override it |
| Evidence ledger | reused; the Guard appends audit records through the existing chain |
| Identity system | unchanged |

Canonicality audit claims 1, 2, 3, 4 and 9 must continue to pass **unchanged**
after implementation. If any of them requires modification to accommodate the
Guard, the design is wrong and must be revised rather than the audit relaxed.
