# Package 4 — Results

**Experiment:** `package4-stateful-canonical-replacement-v1`
**Frozen spec seal:** `24643845becdcbd2cbedc192aad73bf990c28c189fb162795a0b6098ac4df44b`
**Base:** `release/canonical-v1` @ `5e02e47f604770fdee2c05b25418ef003f5b2b92`
**Machine-readable:** `EVIDENCE_RECORD.json` (`python -m evolution.migration`)

**Single Bottleneck Metric: successful stateful replacements through the
canonical runtime, 0 → 1. Met.**

---

## The result

| Candidate | Score | Qualifies | Failing gate |
|---|---|---|---|
| `W0-original` | 1.0 | no — *is* the original | — |
| `W1-projection` | 1.0 | **yes** | — |
| `W2-token` | 1.0 | **yes** | — |
| `W3-journal` | **0.0** | no | `state_survives_migration` |

**Selected: `W1-projection`.** Chosen by the frozen comparison on the frozen
threshold, not by hand. **Decision: `regress`** — the original remains the
default (it is the default by construction), and the qualifying replacements are
retained as proven governed fallbacks. The decision promotes nothing.

## Canonical runtime substitution — the thing Package 3 could not do

Package 3 substituted inside a private registry; `closure/kernel_registry.py`
never called a replacement. Package 4's substitution happens at the **real
construction sites**, asserted by AST:

```
closure/kernel_registry.py:342, 348, 371   -> durable_workflow / resume_workflow
loom/weaver.py:62                          -> durable_workflow
```

No canonical site constructs `DurableWorkflow` directly any more.
`test_verifier_v3_closures_run_through_the_seam_and_still_pass` runs the actual
`events` closures — the ones **verifier V3 executes** — through the seam. A
broken replacement now turns canonical CI red. That failure mode did not exist
in Package 3.

## Exactly-once

Preserved by W0, W1 and W2 on **all five held-out cases**, including the two
that matter most:

- **HO-3** (resumed twice): `calls == ['a1','a2','a3']`, never a repeat.
- **HO-4** (compensated terminal): resume **refused** — `nothing to resume`.

The duplicating-engine control (adversarial test 8) proves the measurement can
fail: an engine that forgets its cursor produces `['d1','d1','d2']` and is
caught.

## State migration — `cursor: int` ↔ `completed_steps + next_step`

Round-trips **exactly at every boundary**, `cursor` 0 through 3 including
`cursor == len(steps)`, the off-by-one boundary. Duplicate step names are
**refused, not guessed**, in both directions — forward refuses too, so the
ambiguous state never exists to be reversed.

Rollback after partial replacement (test 13) is the full loop: W2 runs half the
workflow in its own schema, the scope exits, the state is reverse-migrated to
`cursor: 1`, and **the original resumes and finishes without re-running
anything**.

## Malformed-checkpoint protection — the founder's correction

Refused **before** append, not detected after.

```
refused_before_append          : True
malformed_checkpoints_in_ledger: 0
refusal_events_appended        : 1
records_added                  : 1     (the refusal only)
chain_verifies                 : True
```

A single probe checkpoint carrying five simultaneous violations — wrong workflow
identity, `cursor 99` out of range, empty actor, `UNIIMENTE` as legal principal,
schema failure — was caught with all five named, and **nothing entered the
chain**. `test_1b` proves the guard is not simply refusing everything.

The guard is structural, not advisory: a replacement engine is handed a
`GuardedLedger` by the seam and has no unguarded append path.

## Rollback and restart

```
default_is_original_after_all_scopes : True
original_class_intact                : True
simulated_restart_default            : True
```

The original is the default because `_ACTIVE is None` **means** "the original" —
the default is the absence of a choice, not a stored one. Nothing is persisted,
so a restart cannot restore a replacement. There is deliberately no
`set_default()`, asserted by AST, so no replacement can install itself.

## Continuity

`c1d621a80671d1f39f75e3d525561b45795a978d7d15b1eee7d43546140e63aa`, unchanged
before and after, across all 12 artifacts. Shutdown returns `shutdown_complete`
**while a replacement is active**, and the Constitution still compiles with
`deny_by_default`. Zero unauthorized external effects, enforced out-of-process.

## Predictions: 3 of 4 held. W3 was wrong, and usefully so.

I froze `W3-journal` as expected to qualify. **It scored 0.0.**

W3 preserved exactly-once perfectly — its execution is correct — but its frozen
claim was that the undo stack lives *in state*, and it does. That stack is
therefore visible in the checkpointed `state` namespace the exactness gate
compares. **Correct execution is not the same as a preserved state contract.**

That is the frozen design's real consequence, implemented faithfully rather than
quietly relocated after seeing the gate. It is the most useful finding here: the
state-loss detection catches *pollution*, not just loss, and an engine can be
functionally perfect while still breaking the contract it inherited.

## Limitations — carried forward, not trimmed

1. All candidates and the seam authored in one session by one author.
2. State is process-local over an in-memory ledger. **Not a distributed or
   crash-consistent migration** and must not be described as one.
3. Candidate set fixed in advance — **not unscripted morphogenesis, not
   open-ended self-repair**.
4. The experiment uses an **isolated ledger instance** and the `p4x-` workflow
   namespace. The provider substitution at the canonical sites is real; the
   durable history written is not the institution's own.
5. No external effect, deployment, spending or real-world data. Strongest
   verifier available is a deterministic invariant.
6. Activation is scoped and temporary by construction: this demonstrates
   **governed replacement, not sustained operation** of a replacement.
7. `provenance` is deliberately not watched by the inertness harness, unlike
   Packages 2–3 — checkpointing to the evidence ledger *is* this component's
   contract. What must not happen is *altering* evidence, enforced by the
   append-only chain plus pre-append validation. Watching the import would have
   been the easy check, not the real one.
