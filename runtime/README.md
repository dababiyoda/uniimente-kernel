# `runtime/` — the institution as something that boots

One composition: a durable evidence ledger, the canonical Consequence Gate, the
event spine and causal memory, opened over a state directory.

```python
from runtime import InstitutionalRuntime

rt = InstitutionalRuntime.boot("var/institution")
print(rt.report.summary())
#   resumed from var/institution: 41 records, 12 events, inbox 12,
#   outbox 1, constitution 12 constitutional artifacts, all as authorised
rt.shutdown(sealed_by="alfonso", reason="end of session")
```

## Why this exists

The Infinite Goal Chase recompute (2026-08-23) named it:

> The bottleneck is not "build persistence". It is "compose a durable runtime
> that uses the persistence that exists." Every entry point still constructs a
> fresh in-memory `EvidenceLedger("sha256:" + "0" * 64)`. Nothing boots the
> institution from a state directory.

A standing mandate had nothing to stand in. A cockpit would command a body that
forgets between commands. A reasoning organ's output would not accumulate.
Three absent capabilities, one missing composition.

## Restored versus re-issued

The distinction this module is built around:

| | |
|---|---|
| **Evidence — restored** | the hash chain, witnesses, receipts, causal record, idempotent inbox, outstanding outbox |
| **Identity — re-issued** | `PassportRegistry` starts empty on every boot |

`PassportRegistry` caps passport TTL at one hour by construction. Carrying one
across a restart would use a process boundary to extend an authority the
institution deliberately made short-lived. So whoever wants to act after a
restart presents identity again, and
`test_an_action_by_a_pre_restart_identity_is_refused` asserts that the Gate
turns away an actor whose passport predates the boot.

Memory persists. Permission does not. That is
`capability may recursively expand; authority may not` expressed as a
constructor.

## Fail-closed boot

`boot` refuses rather than starting a degraded institution when:

1. the chain does not re-verify (`EvidenceLedger` checks every link on load);
2. the chain was written under a different constitution and no transition
   record explains the move (`ConstitutionMismatch`);
3. the live constitution does not match the baseline `governance.integrity`
   replays — a silent constitutional edit.

There is **no argument that skips check 3**, and
`test_boot_has_no_argument_that_skips_the_constitution_check` pins its absence
by inspecting the signature. A `verify_constitution=False` would be the
standing "exception because the check is inconvenient" the founder's ruling
prohibits. The lawful path past it is the one already exercised here: record
the amendment.

## Three defects this composition surfaced

None was reachable while the gate and the spine were built on separate
in-memory ledgers. Each was demonstrated before it was fixed.

**1. The transactional outbox did not survive a restart.** `_outbox` was a plain
list, so an event staged and not yet flushed was ledgered as owed and then
forgotten by the only object that could act on it. Now derived from the ledger,
like the inbox and causal memory already were. The subtle half: `outbox_flush`
*re-keeps* a refused event, so the rebuild must too — otherwise a restart
silently discharges everything the mediator ever declined.

**2. A durable chain silently adopted foreign law.** Opening a state directory
with a different constitution hash appended new records under law the chain had
never been checked against, while the genesis docstring claimed the chain was
"bound to the exact doctrine that authorized it". Now `ConstitutionMismatch`,
with `EvidenceLedger.adopt_constitution` as the recorded lawful path. An
in-memory ledger dies with its process and can never be reopened under
different law, which is why only a state directory made this reachable.

**3. `EventSpine.replay()` crashed on Gate records.** `record_type="event"` is a
shared namespace: `ConsequenceGate._transition` writes action-lifecycle records
into it with no `source` or `event_id`. `_seen_from_ledger` and
`CausalMemory._events` both guarded positively; `replay()` did not, and raised
`KeyError: 'source'` the first time one ledger carried both. Confirmed on
unmodified `main`. Fixed by giving all three views one shared discriminator
rather than renaming the Gate's records — those are already on disk in existing
chains, and changing what a historical record is called rewrites what it meant.

## Adoption, and the migration backlog

**Adopted.** `runtime/session.py` is a composition root that boots and does real
work: `python -m runtime <state_dir> --rehearse` runs a full Bridge A traversal
across three organs over the durable ledger, and a second process reads the four
events, their causal ancestry and the verified chain back out.

**All three bridges now have a composition root.**

```
bridges/signal_to_venture.py       Session.traverse_signal_to_venture
bridges/venture_to_experiment.py   Session.traverse_venture_to_experiment
bridges/experiment_to_reality.py   Session.traverse_experiment_to_reality
```

Each still falls back to an ephemeral ledger when nobody injects one, which is
correct for a library; what changed is that something injects a durable one.
A → B → C now runs as one pathway into one chain — A's assessment feeds B, B's
compiled experiment feeds C — and the whole thing survives a restart with the
Gate's receipt still findable.

`test_every_bridge_that_takes_a_ledger_has_a_composition_root` asserts the
correspondence rather than a count, so a fourth bridge that accepts a ledger
without getting a root fails there.

The session deliberately has **no method that produces a strategy tree or an
audit**. Those are the caller's analysis, and a composition root that generated
its own would be inventing the institutional judgement Bridge B exists to refuse
to proceed without.

### A correction, kept visible

The first version of this section said **six** modules and called the remaining
work "mechanical and independently testable". Both were wrong, and checking each
module individually is what showed it:

- `closure/{kernel,advantage,commercial}_registry.py` are the **verification
  harness**. A closure check must be self-contained and deterministic; one that
  read accumulated state would pass or fail depending on what happened earlier,
  which is the opposite of a check. These must *not* migrate.
- `bridges/closure_verdict.py` **runs the chain it then assesses**, deliberately
  — its docstring records that an earlier version assessed an empty ledger and
  printed OPEN, "which understates the finding in the flattering direction".
  Pointing it at a state directory would make the whole-body verdict depend on
  which directory you passed: a design change with a real trade-off, not a
  migration.

So the backlog was never six mechanical edits. It is three libraries needing two
more composition roots, and the difference is exactly the kind of thing a tidy
count hides.

The adoption probe has now been re-pointed twice — once because its first
version asked "does anything boot?" and `session.py` answered yes within hours,
and again for the miscount above. Both for the reason
`_asymmetric_identity_is_only_one_edge_deep` exists: a check that can never fail
again has stopped measuring anything.

"A durable runtime exists" is still not "the Alpha bottleneck is closed".

## Not ported: WP-04's Postgres backend

PR #78 built a Postgres spine backend and a rebuild-from-spine drill. It is
**not** in this change. The recompute's own reading holds — the JSONL path
satisfies the Alpha requirement and Postgres is the scale-up, not the
prerequisite — so gap #24 ("the event transport has no durable implementation")
stays open and correctly reports open.

## Buildability standard

- **Existing mechanism**: process supervision, append-only logs, transactional
  outbox, boot-time integrity attestation — all ordinary systems practice, no
  novel science.
- **Defined interface**: `InstitutionalRuntime.boot(state_dir, *, env)`,
  `.shutdown(sealed_by, reason)`, `.outstanding_deliveries`, `.report`
  (`BootReport`); refusal is `BootRefused`.
- **Bounded authority**: composes, never grants. It mints no passport, issues no
  capability grant, and calls no `issue_single_action` — asserted over the
  module source. The Consequence Gate it assembles remains the only path to
  external effect, unchanged.
- **Available dependencies**: Python 3 stdlib plus `compiler`, `events`,
  `governance.integrity`, `identity`, `memory`, `policy`, `provenance` — all
  in-repo.
- **Security model**: fails closed on three conditions (unverifiable chain,
  foreign constitution, unauthorised constitutional edit) with no argument that
  skips any of them; identities are re-issued rather than restored, so a restart
  cannot extend an expired authority.
- **Failure modes**: `BootRefused` (bad ground — refuses to start),
  `ConstitutionMismatch` from the ledger (chain written under other law),
  `ValueError` on a chain that fails re-verification. All refuse rather than
  degrade.
- **Acceptance tests**: `tests/unit/test_institutional_runtime.py` (18 tests),
  including the mutation check that each fix is load-bearing.
- **Recovery path**: `boot` against the same state directory — that *is* the
  recovery path; the chain re-verifies every link and every derived view
  rebuilds from it.
- **Resource ceiling**: one JSONL file per institution; boot cost is linear in
  chain length (parse plus one hash per record); no threads, no sockets, no
  background work.
- **Operating cost**: one ledger append per boot; otherwise the cost of the
  components it composes.
- **Legal operator**: Alfonso — the constitution it verifies names him, and a
  constitutional transition is refused unless a human authorizer is stated.
- **Handoff state**: the state directory is the entire handoff. A different
  process, machine or operator boots from it and gets the same institution.
- **Replaceable**: every component is constructed in one method and held as a
  plain attribute; a different ledger, spine, gate or memory can be swapped by
  replacing `boot` without touching any caller.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `runtime`.

## What this is not

No scheduler, daemon, server, or listener. It opens no socket and reaches
nothing outside its state directory;
`test_the_runtime_opens_no_socket_and_grants_nothing` asserts both the absent
imports and that the module never calls `issue_single_action` — authorising an
external act stays a separate, visible act by the caller.
