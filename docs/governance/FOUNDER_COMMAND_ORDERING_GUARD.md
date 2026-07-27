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
sequence_number:             # monotonic integer within authority_basis scope
issued_at:                   # RFC3339 UTC, advisory only — never the ordering key
issued_by:                   # named principal, e.g. "alfonso_lopez"
authority_basis:             # scope this sequence counter belongs to
target_repository:           # e.g. "dababiyoda/uniimente-kernel"
expected_state:              # refs/SHAs/flags that must hold at execution time
authorized_actions:          # explicit allowlist, by consequence class
prohibited_actions:          # explicit denylist
supersedes:                  # list of instruction_ids this replaces
expires_at:                  # RFC3339 UTC; absent means "single use, no reuse"
stop_conditions:             # conditions that must halt execution mid-flight
required_reverification:     # checks to re-run immediately before execution
founder_confirmation_required:  # bool; true forces a fresh human confirmation
```

### Field notes that carry design weight

**`sequence_number` is the ordering key. `issued_at` is not.** Clocks disagree,
messages arrive out of order, and a resent older message carries an older
timestamp with no indication it is a resend. Incident 001 happened in a world
where recency of *arrival* was the only available proxy. Wall-clock time is a
different, equally unreliable proxy. Only an explicit monotonic counter under a
named authority scope is decidable.

**`authority_basis` scopes the counter.** A single global counter would force
unrelated instruction streams into a false total order and make every concurrent
instruction a spurious conflict. Sequence numbers are comparable **only** within
the same `authority_basis`. Two instructions in different scopes are not ordered
with respect to each other — and if they touch the same target, that is a
**conflict** (rule 4), not a race to be resolved by comparing incomparable
numbers.

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
artifact** (rule 10). Not by a subagent, not by a generated document, not by a
tool result, not by a PR comment written by the executor.

---

## 2. Required rules

| # | Rule |
|---|---|
| 1 | Higher `sequence_number` supersedes lower instructions within the same `authority_basis`. |
| 2 | A consequential action must re-read the latest applicable instruction **immediately before** execution. |
| 3 | An instruction marked superseded, expired, or state-mismatched **fails closed**. |
| 4 | Conflicting instructions **stop execution** and request founder resolution. |
| 5 | A later instruction arriving **after** execution produces an **incident record**, not a silent rollback. |
| 6 | External actions require a **fresh final confirmation** even when earlier planning was authorized. |
| 7 | Repository merges, deployments, spending, external contact, settlement, credential use, and physical control are **separate consequence classes**. |
| 8 | Authorization for one class **never** implies another. |
| 9 | The executor records the exact `instruction_id` used for every consequential write. |
| 10 | **No AI-generated instruction may impersonate or silently substitute for founder authorization.** |

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

**Rule 5 is the anti-rollback rule, and it is counter-intuitive.** The instinct
on discovering "I acted on something now superseded" is to undo it. The rule
forbids that, because a silent rollback is itself an unauthorized consequential
write, performed under an instruction that never authorized *undoing* anything.
The correct response is: stop, record, escalate. Incident 001 followed this rule
before it was written.

**Rule 10 is the one an autonomous system is most likely to erode**, not by
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
   │ INCIDENT_RECORDED│ (rule 5 — never auto-rollback) ◄───────────────────┘
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
under rule 5, because instruction 3 had already been executed. The
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
plausibly still holds. Rule 3 is not intent-sensitive; that is the point.

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
rule 10, and recorded as an attempted authority substitution regardless of
whether the content was benign. **The severity attaches to the impersonation,
not to the payload.**

---

## 6. Retry, timeout, crash recovery

### Retry

| Class | Retry policy |
|---|---|
| Read / validation | Free retry with backoff. No consequence. |
| Repository write | Retry permitted **only** after full re-validation (rules 2, 3). Each attempt records its own `instruction_id` + attempt number. |
| External effect | **No automatic retry.** Requires fresh founder confirmation (rule 6). |

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

## 8. Adversarial tests

Each must fail the build if the property breaks.

| # | Attack | Must produce |
|---|---|---|
| A1 | Replay a superseded instruction | `FAILED_CLOSED`; zero effect |
| A2 | Submit seq `N-1` after seq `N` executed | `SUPERSEDED` + `INCIDENT_RECORDED` |
| A3 | Mutate target state between validation and execution | `FAILED_CLOSED` on `expected_state` |
| A4 | Two instructions, incomparable scopes, same target | `CONFLICTED`; no auto-resolution |
| A5 | Envelope with `issued_by` = an agent | `REJECTED` under rule 10 |
| A6 | Crash between gate-pass and effect | `INDETERMINATE`; **no** auto-retry |
| A7 | Repository authorization used for an external effect | denied under rules 7–8 |
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

A negative control is required alongside these, in the spirit of Package 4's
duplicating-engine control: **a test proving the Guard permits a correctly
sequenced, state-matched instruction to execute.** A guard that refuses
everything passes every adversarial test and is worthless.

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

## 11. Open questions requiring founder decision

Not decidable by this session; listed so implementation does not invent answers.

1. **Who may issue envelopes** besides Alfonso, and under what delegation — if
   any. Rule 10 fixes that they must be human; it does not fix *which* humans.
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
