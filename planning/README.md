# `planning/` — the UNIIMENTE super-planning compiler

**Status: `PLANNING` / `CONSEQUENCE-INERT`. Not runtime. Not authority.**

This package exists for one round: the whole-system super-planning reconciliation
recorded on branch `claude/super-planning-prompt-h8l0oj`. It holds a canonical
planning model (`graph/`) and deterministic generators (`compiler/`) that project
every required planning artifact out of that model.

## Why a compiler instead of ~40 documents

Forty hand-written planning documents drift against each other. One model with
forty projections cannot. When a decision changes, the change is made once in the
graph and every dependent artifact is regenerated. `planning/tests/` enforces this:
regeneration is idempotent, and the committed artifacts must reproduce byte-for-byte
from the committed graph.

The Founder-Horizon Override §27 is explicit that this compiler is an *instrument*,
not a new institution. `docs/planning/uniimente_v1/FINAL_DECISION.md` must return a
disposition for the compiler itself — retain, reduce to artifacts, absorb into the
future anatomy system, or kill.

## Inertness guarantees

These are asserted by `planning/tests/test_inertness.py`, not merely promised:

1. **No kernel package imports `planning`.** The dependency runs one way only.
2. **`planning` imports only pure kernel data structures** — `evolution.strategy_tree`,
   `evolution.spider_web`, `linker.linker`. Reuse, never reimplementation.
3. **No authority.** Nothing here registers a capability, opens a gate, writes a
   grant, or touches the Consequence Gate.
4. **Detachable.** Deleting `planning/`, `docs/planning/` and `artifacts/planning/`
   leaves the kernel byte-identical to `main` at `8cb3074`.
5. **No external effects.** No network, no credentials, no writes outside the three
   planning trees.

## Anti-fabrication invariant

Every node carries `evidence_refs` and an `evidence_status`:

| status | meaning |
|---|---|
| `verified_by_execution` | a command was run and its output recorded |
| `verified_by_inspection` | read directly from a named file at a named SHA |
| `asserted` | stated by a source document, not independently checked |
| `unresolved` | no evidence exists; the field is explicitly open |

A node with no `evidence_refs` **must** be `unresolved`. It may never be silently
promoted. This is the Final Build Order §4.1 compiler rule — *"never silently invent
missing authority, evidence, legal identity, permissions, or dependencies"* — applied
to the planning model itself.

## Instrument liveness

Per prompt §31, every validator here must assert its subject exists, carry a
non-vacuity witness, include a negative control that forces failure, exit nonzero on
failure, run from any working directory, and distinguish *not run* from *passed*.
A counter declared but never incremented is not evidence.

## Layout

```
graph/schema/   JSON Schema 2020-12 for each node kind
graph/nodes/    the canonical model, one YAML file per node kind
compiler/       model loader, renderers, validators
tests/          schema, evidence, inertness, idempotence, negative controls
```

Generated output lands in `docs/planning/uniimente_v1/` (human projections) and
`artifacts/planning/uniimente_v1/` (machine projections). Generated files carry a
provenance header naming the graph digest they came from and must never be
hand-edited — `test_idempotence.py` will catch it.
