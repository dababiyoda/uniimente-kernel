# GOVERNANCE INCIDENT 001 — Conflicting Founder Instruction Execution Order

**Classification:** `COMMAND_ORDERING_AND_STALENESS_CONTROL_FAILURE`
**Severity:** `PROCESS_CONTROL_HIGH / CONSEQUENCE_LOW`
**Disposition:** `RETAIN_WITH_CORRECTIVE_SYSTEM_UPDATE`
**Recorded:** 2026-07-27
**Subject commit:** `8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1` (current `main`)

This record is permanent institutional evidence. It is not a postmortem to be
closed and archived. It is the reason the Founder Command Ordering Guard exists.

---

## 1. Known facts

Stated without minimizing and without inflating. Each is independently checkable
from the repository or from GitHub.

| # | Fact | Verifiable by |
|---|---|---|
| F1 | A founder instruction authorizing ratification and merge of PR #47 was recorded and executed. | Founder Ratification Record, PR #47 discussion |
| F2 | A later-arriving instruction told the executor to keep PR #47 a draft and not merge. | This conversation's message sequence |
| F3 | The later instruction reached the executor **after** the merge had already occurred. | Merge timestamp `2026-07-26T22:30:31Z` vs. instruction arrival |
| F4 | The merge was therefore valid under one instruction stream and inconsistent with the sequencing expected by another. | F1 + F2 + F3 |
| F5 | The merge commit has the correct parents. | `git log -1 --format=%P 8cb3074` |
| F6 | Post-merge CI passed. | Canonical CI run `30223271691`, four jobs `success` |
| F7 | No external consequence occurred. | `external_effects=0`, enforced out-of-process |
| F8 | No Venture Cell was activated. | `ivio_nemt` `ACTIVE=False`, `ATTACHED=False` |
| F9 | No deployment, spending, external contact, settlement, production-credential use, or real-world data action occurred. | Consequence Gate records; no such path executed |

### The parents, stated exactly

```
8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1
  parent 1  3d9b5779a7093d6ddd07f225c8329ead6d0c6393   frozen pre-release main
  parent 2  526e320475d7b1175c546d48147f9f49f53831e1   certified release head
```

### What the executor did and did not do at the moment of divergence

It did **not** notice the conflict before merging, because the conflicting
instruction did not yet exist from its vantage point. That is precisely the
defect: the executor had no mechanism that could have detected a *future*
instruction, and equally no mechanism that would have detected a *stale* one had
the arrival order been reversed. The failure is symmetric, and only one half of
it happened to fire here.

When the stale instruction did arrive, the executor did **not** silently comply
with it, did not quietly revert, and did not proceed as though the conflict were
absent. It stopped, stated the conflict, refused to un-merge without explicit
instruction, and completed only the non-destructive remainder. That response was
correct and is the reason this incident is `CONSEQUENCE_LOW` rather than a
history-rewrite event.

---

## 2. Root cause

**`COMMAND_ORDERING_AND_STALENESS_CONTROL_FAILURE`**

Founder instructions carried no sequence number, no issue timestamp usable for
ordering, no explicit supersession pointer, and no expiry. The executor
therefore had no way to answer the only question that mattered before a
consequential write:

> *Is the instruction I am about to act on still the latest applicable
> instruction for this authority scope?*

Absent that, "most recently received" was used as a proxy for "currently
authoritative." Those two coincide right up until they don't.

### Explicitly NOT the root cause

The following classifications are **rejected**, each with the evidence that
rejects it:

| Rejected classification | Why it does not apply |
|---|---|
| Code corruption | Merge tree `39afd414…` equals the certified release head's tree exactly. No content was altered by the merge. |
| Unauthorized authority expansion | The merge was authorized by an actual founder instruction. No capability, grant, or authority ceiling changed. Audit claim 11 still passes: no `set_default()`, provider resolves to the original. |
| External-effect failure | Zero external effects. The Consequence Gate was never asked to authorize one. |
| Malicious behavior | The executor surfaced the conflict unprompted, at cost to its own apparent success, rather than concealing it. |
| Repository permission failure | Every operation used permissions already granted. The one permission genuinely absent — tag push — was reported as absent and worked around by founder action, not circumvented. |

Naming what this is *not* matters as much as naming what it is. A process
defect misfiled as a security event distorts every future risk assessment built
on this record.

---

## 3. Severity

**`PROCESS_CONTROL_HIGH / CONSEQUENCE_LOW`**

The two halves are independent and both are load-bearing.

**Why `CONSEQUENCE_LOW`.** The blast radius was a reviewed, CI-certified merge
into a repository branch, whose exact content had already been certified green,
whose rollback target is preserved in three places (frozen `main` parent,
`archive/main-2026-07-19` branch, and the remote archive tag), and which
produced no effect outside version control.

**Why `PROCESS_CONTROL_HIGH`.** The defect is in the ordering discipline, not in
the merge. The same discipline governs deployment, spending, external
communication, settlement, credential use, and physical control. A stale
instruction that lands a redundant merge is an inconvenience. A stale
instruction that lands a payment, an email to a customer, a credential
provisioning, or an actuator command is not recoverable by `git revert`.

**The severity is set by the class of action the defect could reach, not by the
action it happened to reach.** Rating this `LOW` outright because "it was only a
merge" would be exactly the outcome-based reasoning that Objection 2 below
warns against.

---

## 4. Corrective decision

1. **The merge stands.** `main` remains `8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1`.
2. **No revert is required or performed.**
3. **This incident remains permanent evidence.** It is not superseded, closed,
   or removed by any later success.
4. **Future consequential writes require explicit command-order verification**,
   specified in `docs/governance/FOUNDER_COMMAND_ORDERING_GUARD.md`.

### Why not revert — the reasoning, so it can be attacked later

A revert would add a second consequential commit to `main`, create genuine
ambiguity about which commit is canonical-v1, force a manifest and certification
re-run, and **still not erase the ordering error**, which is a fact about the
message sequence rather than about the repository. The error is not stored in
`main`; it is stored here. Reverting would trade a valid release for a
performance of correction.

This reasoning is only sound because F5–F9 hold. If the merge had produced a
wrong tree, an unauthorized authority change, or any external effect, retention
would not have been available, and this section would read differently.

---

## 5. Preserved dissent — the strongest case for reverting

Recorded because the decision went the other way. A decision whose opposing case
is not written down cannot be re-examined honestly later.

### Objection 1 — Sequence integrity matters independently of technical correctness

An authorization system's value lies in the *guarantee* that nothing
consequential happens outside the authorized sequence, not in the average
quality of outcomes it produces. A system that reaches correct results through
an unsound ordering process has not demonstrated authorization control; it has
demonstrated luck plus competence. Under this view the merge should be reverted
and re-executed in proper sequence, so that the canonical release is the product
of a sound process and not merely a sound result.

**Why it does not currently justify a revert.** Re-executing would not restore
sequence integrity retroactively. The out-of-order execution is a fact about the
instruction stream, already permanent. A revert-then-remerge would produce a
`main` whose history contains the same ordering defect *plus* two additional
commits performed for appearance. The guarantee cannot be recovered by repeating
the action; it can only be established going forward.

**What future evidence would change this.** If it emerged that the merged
content differed in any respect from what the founder ratified — a different
tree, an unreviewed commit reachable from the release head, or an authority
change not present at `526e320` — then the merge would not be "the right result
by an unsound path" but simply the wrong result, and revert would be mandatory.
The tree equality check (`39afd414…`) is the specific evidence currently ruling
this out, and it should be re-verified rather than assumed if this objection is
revisited.

**Safeguard preventing recurrence.** Guard rules 1–4: sequence numbering,
mandatory re-read immediately before execution, fail-closed on superseded or
expired instructions, and hard stop on conflict pending founder resolution.

### Objection 2 — Accepting a result after an ordering violation creates precedent for outcome-based rationalization

The reasoning "the merge was fine, therefore retain it" is structurally
identical to "the deployment worked, therefore the approval gap was immaterial."
Once an institution accepts that a good outcome can retroactively cure a process
violation, the process constraint has been converted into a preference. This is
the more dangerous objection of the two, because it does not depend on anything
being wrong with this particular merge — it is a claim about what the *decision*
teaches the system.

**Why it does not currently justify a revert.** Reverting would not defeat the
precedent; it would establish a different and arguably worse one — that
process violations are answered with symbolic remediation rather than structural
fixes. The precedent is set by what is *built* in response, not by whether the
artifact is undone. The corrective here is a mandatory guard on every future
consequential write, which is a structural constraint. Retention paired with
`RETAIN_WITH_CORRECTIVE_SYSTEM_UPDATE` and a permanent incident record is a
materially different precedent from retention paired with silence.

**What future evidence would change this.** A second retention decision on
ordering grounds — particularly one where the guard existed and was bypassed,
or where the affected consequence class was higher than repository state —
would confirm that a rationalization pattern is forming rather than a
one-time judgment. **A second `RETAIN` on these grounds should be treated as
evidence that the safeguard failed, regardless of that incident's own merits.**

**Safeguard preventing recurrence.** Guard rules 5 and 9: a later instruction
arriving after execution must produce an incident record rather than a silent
rollback, and the exact instruction ID must be recorded for every consequential
write. Together these make the ordering question auditable rather than a matter
of recollection.

### Objection 3 — Repository-only consequences are not evidence that the process is safe for financial or physical effects

The containment here was environmental, not architectural. Nothing in the
executor's design prevented a higher-consequence action; the instruction simply
happened to concern a merge. Treating `CONSEQUENCE_LOW` as reassurance
generalizes from a sample of one, drawn from the lowest-stakes class available.

**Why it does not currently justify a revert.** This objection argues against
*complacency*, not for reversion — reverting `main` would do nothing to make
financial or physical actions safer. It is answered by scope, not by undoing
the merge.

**What future evidence would change this.** Any ordering ambiguity arising in a
higher consequence class — spending, external contact, settlement, credential
use, physical control — should trigger immediate suspension of that class
pending guard implementation, not another retention judgment.

**Safeguard preventing recurrence.** Guard rules 6, 7 and 8: external actions
require a fresh final confirmation even when earlier planning was authorized;
consequence classes are separated explicitly; and authorization in one class
never implies another. This incident's containment becomes a designed property
rather than an accident of what was asked.

### Dissent that is *not* preserved here

No objection was raised on the grounds that the merged content was wrong,
unauthorized, or unreviewed — and none is recorded, because none is supported.
Manufacturing a content objection to make the dissent section look more balanced
would corrupt the record. The dissent is entirely about process, which is
precisely where the defect is.

---

## 6. Verification at time of recording

Re-confirmed without rerunning CI, because no repository code changed.

```
main                            8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1  ✓
  parent 1 (frozen rollback)    3d9b5779a7093d6ddd07f225c8329ead6d0c6393  ✓
  parent 2 (certified release)  526e320475d7b1175c546d48147f9f49f53831e1  ✓
release/canonical-v1            526e320475d7b1175c546d48147f9f49f53831e1  ✓ unmoved
archive/main-2026-07-19         3d9b5779a7093d6ddd07f225c8329ead6d0c6393  ✓ unmoved
tag main-pre-canonical-v1-…     3d9b5779a7093d6ddd07f225c8329ead6d0c6393  ✓ unmoved
post-merge CI run 30223271691   success, four jobs                        ✓
Venture Cells active                                                       0
unauthorized external effects                                              0
Clean Verified Outcomes                                                    0
branches deleted                                                        none
```

Manifest-branch changes do not alter `main`: this document lives on
`release/canonical-v1-manifest` and is not reachable from `main`.

---

## 7. Standing obligations created by this incident

1. Every consequential write records the exact instruction ID that authorized it.
2. Conflicting instructions stop execution and escalate; they are never resolved
   by recency heuristics.
3. A later instruction arriving after execution produces an incident record.
4. This incident is cited in the Guard document as its originating evidence.
5. Guard implementation is a prerequisite for any action in a consequence class
   above repository state — specifically before CVO-001 execution.

**The architectural phase closed with a process defect on the record. That is a
better starting position than closing it with an unexamined clean sheet.**
