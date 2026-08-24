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

## Adoption: 0 of 6

**The runtime exists and nothing uses it.** Six modules still construct their
own in-memory ledger:

```
bridges/closure_verdict.py        bridges/venture_to_experiment.py
bridges/experiment_to_reality.py  closure/advantage_registry.py
bridges/signal_to_venture.py      closure/commercial_registry.py
```

`closure/kernel_registry.py` does boot the runtime — inside the `runtime`
closures, which is the module being *exercised*, not a caller having *adopted*
it. It is excluded from both columns by name, because counting a module's own
verification as its adoption would inflate the number using the very test
written to measure it.

This is the same state `identity/pki/` was in the day before Bridge A adopted
it, and it is recorded the same way — counted by
`test_runtime_adoption_is_counted_not_asserted`, which fails in both directions
so that migrating an entry point forces the count and the recompute to move
together.

"A durable runtime exists" is not "the Alpha bottleneck is closed". Migration is
the next step, and it is mechanical and independently testable per entry point.

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
