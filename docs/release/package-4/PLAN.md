# Package 4 — Plan Only. NOT AUTHORIZED FOR IMPLEMENTATION.

**Base:** `release/canonical-v1` @ `5e02e47f604770fdee2c05b25418ef003f5b2b92`
(the verified Package 3 merge commit)

**The question Package 4 tests:**

> Can UNIIMENTE replace a **stateful**, non-authority specialist through its
> **actual canonical runtime boundary** while preserving required state,
> contracts, evidence, rollback, shutdown, and institutional continuity?

**Single Bottleneck Metric:**
`Successful stateful replacements through the canonical runtime: 0 → 1`

This is a **governed stateful-replacement experiment**. It is not autonomous
regeneration and not open-ended self-repair.

---

## 0. What Package 3 did not prove, stated first

Package 3 proved stateless functional replacement **inside an isolated
experiment registry**. Its own evidence record says so: *"installation registers
the winner in this experiment's own provider registry. It does NOT rewrite the
kernel's live import path."* `closure/kernel_registry.py` never called a
replacement, and the replaced component held no durable state.

Package 4 exists to close exactly that gap, and it therefore **cannot be purely
additive**. Packages 1–3 added files and modified nothing. Package 4 must open a
governed seam in the canonical construction path. That is a change in kind and
§21 asks for explicit founder approval of it.

---

## 1. Selected component: `DurableWorkflow` (`events/spine.py`)

The durable workflow execution engine — a step sequence checkpointed on the
evidence ledger, resumable after interruption, compensating in reverse on
failure.

### 1.1 Exact state

Two layers, both already explicit today.

**Durable** — ledger records of type `workflow`, schema measured on the base
commit:

```
{workflow_id: str, cursor: int, status: str, state: dict,
 note: str, actor: str, legal_principal: str, at: iso8601}
```

**In-memory** — `cursor: int` (next step index), `state: dict` (accumulated step
outputs), `status: str` in `running | completed | interrupted | failed |
compensated`.

Measured on the base commit, a 3-step workflow killed before step `b`:

```
checkpoints written : 3
last checkpoint     : {"cursor": 1, "status": "interrupted", "state": {"a": 1},
                       "note": "killed_before:b", "actor": "alfonso",
                       "legal_principal": "alfonso_lopez",
                       "workflow_id": "wf-demo"}
calls before resume : ['a']
calls after  resume : ['a', 'b', 'c']      <-- 'a' NOT re-executed
final               : status=completed cursor=3 state={'a':1,'b':1,'c':1}
ledger chain        : intact, 9 records
```

**The behavioural function to preserve is exactly-once execution across an
interruption.** `calls == ['a','b','c']`, never `['a','a','b','c']`. That is a
hard integer property, not a judgement call — the same discipline that made the
linker a good Package 3 subject, now with state attached.

### 1.2 Why this component is safer than the alternatives

| Candidate | State | Verdict |
|---|---|---|
| **`DurableWorkflow`** | cursor + state dict, checkpointed to ledger | **selected** |
| `capital/treasury.py` `RegenerativeTreasury` | `_postings`, `_balances`, `_debts` | **excluded** — it *is* accounting authority |
| `provenance/ledger.py` `EvidenceLedger` | hash-chained evidence | **excluded** — a memory module may not gain the ability to alter evidence; it is also the store this experiment audits against |
| `memory/affect.py` `AffectController` | affect condition | **excluded** — `shutdown()` is a shutdown path |
| `capabilities/genome.py` `GenomeRegistry` | `_genomes` dict | rejected — `may_instantiate()` is a bounded-authority check; authority-adjacent |
| `events/spine.py` `EventSpine` | `_seen_ids`, `_outbox` | rejected — the nervous system itself; far larger blast radius than the engine sitting on top of it |
| `twins/`, `autonomy/` | thresholds, ladder level | rejected — tiny state, and the autonomy ladder is authority-adjacent |

`DurableWorkflow` satisfies every stated safety criterion:

- **deterministic** — cursor plus a dict of step outputs; replay is exact
- **clear schema** — already a fixed-key JSON payload, already serialised
- **safely copyable** — copying a checkpoint is reading a ledger record
- **independently verifiable** — exactly-once is checkable by counting calls, from
  outside the engine
- **bounded failure** — no external effect; failures compensate in reverse and
  every attempt is ledgered
- **exact rollback** — the ledger is append-only, so the prior valid checkpoint
  is *still there* and cannot be destroyed by a bad migration

And critically: **it holds no authority.** It refuses `legal_principal ==
"UNIIMENTE"` (`events/spine.py`), which the replacement must keep refusing.

### 1.3 The residual risk, named

`DurableWorkflow` **writes to the evidence ledger**. A defective replacement
could append malformed checkpoints. It cannot rewrite or delete existing ones —
the chain is append-only and verified — so the failure mode is bounded to
"garbage appended", detectable by `verify_chain()` plus schema validation, and
recoverable by resuming from the last valid checkpoint with the original engine.
That is the single most important adversarial test (§18).

---

## 2. Baseline function and test corpus

**Measurement corpus** — the live canonical paths that already exercise the
engine:

| Source | What it asserts |
|---|---|
| `closure/kernel_registry.py::events_evidence` | killed workflow resumes from checkpoint; finished steps never re-executed |
| `closure/kernel_registry.py::events_regenerative` | failure compensated in reverse; failure + compensation kept as negative evidence |
| `loom/weaver.py::Weaver.weave` | patterns compile to a working durable workflow |
| `tests/unit/test_events.py` (7 workflow tests) | resume, terminal-state refusal, approval gate, UNIIMENTE refusal |
| `tests/unit/test_loom.py` (2 resume tests) | pattern-level resume |

**Held-out corpus** — frozen before candidates, inputs *and* expected outputs
derived by hand from the contract, sharing no workflow id with the live corpus:

| Case | What it isolates |
|---|---|
| HO-1 | interrupt at step 1 of 1 — cursor 0, empty state, resume runs exactly one step |
| HO-2 | interrupt at the **last** step — cursor n-1; off-by-one in migration shows here or nowhere |
| HO-3 | resume a workflow that was **already resumed once** — checkpoint chains, not a single hop |
| HO-4 | failure → compensation → terminal `compensated`; resume must be *refused*, not silently restarted |
| HO-5 | approval-gated step, unapproved — `interrupted` with the gate still closed after migration |

HO-4 is the one that matters most: a replacement that happily resumes a
terminal workflow has lost a safety property while looking functional.

---

## 3. The canonical runtime boundary being exercised

Package 3's boundary was a private registry. Package 4's is the real one.

`DurableWorkflow` has exactly three non-test construction sites, all measured:

```
closure/kernel_registry.py:341, 347, 370   (verifier V3 runs these closures)
loom/weaver.py:62                          (the Loom compiles patterns onto it)
```

**The seam.** A new `events/engine.py` holds the active workflow-engine
provider, defaulting to the original class. `events/spine.py` gains a factory
that resolves through it. The three construction sites call the factory instead
of the class. Direct `DurableWorkflow(...)` construction stays legal and
unchanged, so nothing outside is broken and the original remains reachable.

Substitution is therefore **real**: with a replacement active, verifier V3's
`events` closures and the Loom both run on the replacement. If it is wrong,
canonical CI goes red. That is the point — Package 3 could not fail this way.

---

## 4. State schemas and the migration

**Original (W0):** `cursor: int` — position by index.

**Replacement (W2, the schema-changing candidate):**
`completed_steps: [str]` + `next_step: str | null` — position by name.

**Migration W0 → W2:** `cursor` → `steps[:cursor]` names, `next_step =
steps[cursor].name` or `null` at the end.
**Reverse W2 → W0:** `cursor = index(next_step)`, or `len(steps)` when null.

Declared explicitly, per the adapter rules in the build order §8:

- **information added:** step *names* (recoverable from the step list, not from
  the old state alone)
- **information lost on reverse:** none for unique names
- **assumption:** step names are unique within a workflow. **If names repeat, the
  reverse migration is ambiguous and must refuse, not guess.** An adversarial
  test asserts the refusal (§18).
- **failure behavior:** fail closed — a migration that cannot validate leaves the
  original checkpoint untouched and does not activate

---

## 5. Candidates

All four preserved permanently, whatever the result.

| ID | Mechanism | State shape |
|---|---|---|
| `W0-original` | the existing engine, re-enabled — **permanent benchmark, strongest conventional repair, rollback target** | `cursor: int` |
| `W1-projection` | no snapshot: cursor/state **derived** by folding the checkpoint stream | none stored |
| `W2-token` | explicit transition table; position by **step name** | `completed_steps`, `next_step` |
| `W3-journal` | forward journal + explicit **undo stack** carried in state | `cursor`, `undo: [str]` |

Materially different in data flow and decision structure, not naming — W1 stores
no position at all, W2 changes the state schema and forces a real migration, W3
carries compensation state the original recomputes. Only W2 exercises the full
migration path, which is why it is the one the experiment is really about; W1 and
W3 exist so W2 is not the only datapoint.

**Prediction, to be frozen before implementation:** W0 cheapest again; W2 the
most likely to expose a real migration defect; W1 at risk on HO-3 (chained
resumes make folding expensive and order-sensitive). Predictions get recorded so
being wrong stays visible — Package 3's R3 prediction was wrong and that was the
most informative result in it.

---

## 6. Compatibility, activation, thresholds, rollback

**Compatibility rules.** A candidate may activate only if: it implements the
engine protocol; its state schema validates against a declared JSON Schema; the
migration round-trips on every corpus case; and it preserves the
`legal_principal != "UNIIMENTE"` refusal.

**Bounded activation.** Scoped context manager, allowlisted workflow ids, auto-
revert on exit, no persistence of the active provider across processes.
Activation never survives a crash — the default is always the original.

**Failure thresholds — any one fails the candidate:** a completed step
re-executes; final `state` differs; a status transition differs; a terminal
workflow becomes resumable; the ledger chain fails to verify; any pre-existing
record changes; migration silently guesses; the replacement touches authority.

**Rollback.** Restore the original provider (one step, it is the default) and
resume from the last valid checkpoint. Because the ledger is append-only, the
pre-migration checkpoint is still present by construction.

**State-loss detection.** Independent of the engine: fold the checkpoint stream,
assert every `step_completed` note in the pre-migration record is still
represented post-migration, and assert re-execution count for those steps is
zero.

---

## 7. Continuity, shutdown, isolation, cost

Unchanged from Package 3 and re-used directly: the 12-artifact continuity
fingerprint `c1d621a8…140e63aa`; shutdown enforceable at every stage **including
mid-migration**; zero unauthorized external effects enforced out-of-process by
the Package 2 harness repointed at the engines, with kernel-reach a violation;
the same frozen repair-cost formula and weights, extended with two terms —
`state_records_migrated` and `migration_steps` — frozen before implementation.

---

## 8. Adversarial tests

1. **Malformed checkpoint append** — a candidate writing a bad record must be
   caught by schema validation and `verify_chain()`, and the original must still
   resume from the last valid checkpoint.
2. **Duplicate step names** — reverse migration must refuse, not guess.
3. **Terminal-state resume** (HO-4) — must stay refused after migration.
4. **Mid-migration kill** — interrupt between export and import; the original
   checkpoint must be untouched and the workflow still resumable.
5. **Silent partial migration** — a candidate migrating 3 of 4 records must be
   detected as state loss, not reported as success. (Package 3's control 3,
   ported to state.)
6. **Authority reach** — a candidate importing `policy`/`authority` fails
   out-of-process.
7. **`UNIIMENTE` as legal principal** — must still be refused.

---

## 9. Evidence artifacts

`docs/release/package-4/` — `EXPERIMENT_SPEC.md` (frozen, self-sealing hash),
`RESULTS.md`, `EVIDENCE_RECORD.json`; ledgered events for provider substitution,
state export, migration, activation, verification, rollback; the failed
candidates and negative results preserved.

---

## 10. Exact files expected to change

**New:** `events/engine.py` · `evolution/migration/{spec,export,migrate,compat,activate,rollback}.py`
· `evolution/migration/w0..w3_*.py` · `tests/unit/test_migration_*.py` ·
`docs/release/package-4/`.

**Modified — the part that needs approval:**

| File | Change | Risk |
|---|---|---|
| `events/spine.py` | add a factory resolving the engine provider; **class kept unchanged** | low — additive within the file |
| `closure/kernel_registry.py` | 3 construction sites call the factory | **medium** — this is the canonical path verifier V3 runs |
| `loom/weaver.py` | 1 construction site calls the factory | low |

**Untouched:** Constitution, authority, identity, legal principals, Consequence
Gate, shutdown, `provenance/ledger.py`, `linker/`, `ventures/`, contracts.

---

## 11. Freeze discipline and preservation

The complete immutable `ExperimentSpec` lands in the **first commit, before any
candidate**, self-sealed by hash, exactly as Package 3 did. `DurableWorkflow`
itself is never deleted or rewritten — it becomes the default provider, the
benchmark and the rollback target, asserted byte-identical on every CI run.

The replacement **must not self-promote**. Selection is the frozen comparison;
`RetainRegressKillDecision` may recommend and may not promote or activate.

---

## 12. Success threshold

Passes only when: all required state migrates; no required record lost or
duplicated; behavioural function restored exactly (**exactly-once preserved, zero
re-executions**); the replacement differs materially from the original; **the
canonical runtime actually uses it** (verifier V3 exercises it); rollback
restores both the original provider and a prior valid state; Constitution,
identity, authority, legal-principal registry, Gate and shutdown intact;
institutional evidence still available and chain-verifying; unauthorized external
effects zero.

---

## 13. Known limitations, recorded before the result

1. Candidates authored in one session by one author — as in Package 3.
2. State is process-local plus an in-memory ledger. This is not a distributed or
   crash-consistent migration, and must not be described as one.
3. The seam is authored by the same author as the candidates.
4. No external effect, so the strongest available verifier remains a
   deterministic invariant.
5. **The most likely honest outcome is again that the original wins on cost**,
   with a replacement proven viable as a governed fallback. That is a result, not
   a failure.

---

**Status: PLAN ONLY. Implementation requires explicit founder approval —
specifically including approval to modify the three canonical files in §10.**
