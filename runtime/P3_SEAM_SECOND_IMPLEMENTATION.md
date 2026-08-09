# P3-B, second implementation — `runtime/seam/`

> **Not the canonical seam.** Two sessions built P3-B concurrently and both
> landed on this branch. `runtime/contract_events.py` +
> `runtime/probes/route_b_counterfactual.py` (commits `af82717`, `59ed076`)
> arrived first and the resume packet points at them. This is an independent
> second implementation, registered under Final Build Order §9 — governed
> implementation pluralism, not uncontrolled duplication. Deleting it would
> violate §12; promoting it silently would violate §3.
>
> **Open founder decision:** which seam is canonical, and what role the other
> keeps (comparator, counterfactual twin, regression oracle, or superseded).
> Nothing here claims that answer.

## Why an independent replication is worth keeping

The two implementations were written without knowledge of each other, against
the same frozen contract, and reached the same verdict: the route holds, the
four states discriminate, and `WealthMachineClient` must never be on the
decisive path. That is a genuine independent replication of the P3 finding,
which is stronger evidence than either run alone.

They are not redundant. Each proves something the other does not:

| | canonical (`contract_events.py`) | this one (`runtime/seam/`) |
|---|---|---|
| bypass rejection | declared `handler_ref` provenance | **profiler: which files actually executed** |
| network denial | `socket` subclass tripwire | not enforced (relies on inertness of the path) |
| organ pinning | schema sha256 + both git revisions | repository-root shadow check only |
| deliberation record | ADR + two-pass + intent ledger | none |
| runs in default suite | no — needs `TRACK_A_DALEOBANKS_DIR` | **yes — discovers sibling checkouts** |
| write containment | not measured | **cwd containment + organ writes counted** |

The two rows in bold are the ones worth transplanting into whichever seam wins:
a declared `handler_ref` says where a call was *supposed* to go, while the
execution witness records where it *went*; and the containment work found two
real inertness escapes (below) that a declaration-based check cannot see.

## What this implementation measured


`P3_INSPECTION.md` named two absences. This closes the first one and answers
the open question it left. Run it yourself:

```
python -m runtime.seam.episode --out /tmp/p3.json
python -m pytest tests/unit/test_seam_router.py tests/integration/test_p3_counterfactual.py
```

Recorded run: `runtime/evidence/P3_EPISODE.json`.

## What was built

One seam, in three separated layers, because collapsing any two is how this
kind of experiment turns into theatre:

| Layer | Component | What it may assert |
|---|---|---|
| Structure | `InstitutionalLinker` (existing, unmodified) | this edge exists |
| Semantics | `runtime/seam/binding.py` | this code receives that contract |
| Authority | *nobody here* | — |

A route materialises only when structure **and** semantics both hold. Missing
either fails closed as `ROUTE_NOT_ESTABLISHED`.

**Geometry B.** One event type — `institution.contract_delivery` — for every
contract. The contract name travels in the payload as data and never becomes an
identifier. The rejected alternative was deriving an event type per contract by
normalising the contract string, which would have manufactured a namespace out
of nothing and let `wire-opportunity-packet` masquerade as evidence for an
event called `wire.opportunity_packet`. Handlers therefore filter on payload
data. That is what keeping contract names as data costs, and it is cheap.

## The measured result

```
DALEOBANKS  IdeaRefinery._opportunity_from()  ->  OpportunityPacket
            venture_protocol.packet_to_wire()
KERNEL      InstitutionalLinker proves daleobanks --wire-opportunity-packet--> wealthmachine
            ContractRouter materialises one route
            EventSpine emits institution.contract_delivery
WMI         OpportunityIntakeService.evaluate_packet()  ->  NetworkWealthEngine
            VentureAssessment(go_no_go="go", requires_human_approval=True)
```

| State | Topology | Routes | Assessment |
|---|---|---|---|
| A healthy | real linker | 1 | **yes** |
| B damaged | edge resolution unavailable | 0 | no — `ROUTE_NOT_ESTABLISHED` |
| C repaired | real linker | 1 | **yes** |
| D rolled back | edge resolution unavailable | 0 | no |

Healthy and damaged are behaviourally different in the way that matters: with a
proven edge the packet reaches intake and an assessment exists; without one the
packet is never routed and no assessment is produced. **That is a lost function,
not a failing probe** — which is exactly what disqualified Route A, where
disabling edge resolution would only have made a health check report unhealthy.

The damage is the *capability* going away, not the data being falsified. No
manifest was edited. `DisabledEdgeResolution.resolve_edges()` raises, because an
empty topology and an absent capability are different facts and a caller that
treated "no edges" as "nothing to route" would launder the second into the first.

## Why this is not a mock

Three witnesses, none of which can be claimed — only performed:

1. **Repository check.** The resolved consumer module must live under the
   declared repository root. DALEOBANKS and WMI are separate checkouts with
   overlapping top-level package names; without this, a shadowed import would
   satisfy the binding while being something else entirely.
2. **Execution witness.** A profiler records which files actually ran during
   delivery. STATE A executed **13 files inside WealthMachineIntelligence**. A
   delivery where nothing in the consumer's repository ran is rejected as
   `VACUOUS_DELIVERY` regardless of what it returned.
3. **Bypass detection.** `services/wealthmachine_client.py` is named as the
   forbidden path on both bindings. It executed in neither decisive state.

`WealthMachineClient` never appears in the decisive path. Its credential-free
default mode is `mock`, where DALEOBANKS computes the `VentureAssessment`
itself via `_evaluate_mock`. An episode routed through it would have produced a
perfectly valid-looking assessment while WMI was never invoked — edge
resolution could have been disabled and the assessment would still have
appeared, and the counterfactual would have silently proven nothing.

## The controls, and one instrument that was broken

Without live controls, the four states above are worth nothing.

* **`binding_without_proven_edge`** — a binding for an organ with no proven
  edge must be refused. It is. If it ever routes, the router is matching on
  something other than the linker's edges and every STATE A result is void.
* **`bypass_binding_detected`** — a binding pointed *into* `WealthMachineClient`
  is deliberately run all the way to execution, and must be caught. It is:
  `BYPASS_DETECTED: the delivery executed
  ['/…/DALEOBANKS/services/wealthmachine_client.py']`.

The second control found a real defect in the first version of this seam, which
is preserved here rather than quietly edited away.

The original bypass check refused any binding while a forbidden module sat in
`sys.modules` — that is, it tested **importability**, not **execution**. Two
things were wrong with it. DALEOBANKS is checked out beside the kernel, so its
client is permanently importable and the seam could never have routed in any
real workspace. And the bypass control imports that client by design, so running
the control poisoned every state after it: the first full run produced
`A=yes, B=no, C=no, D=no` — a false repair failure, caused entirely by the
instrument.

**A control that poisons the experiment is a broken control.** The check now
measures what ran. Importable is not used, and only execution can produce a
result. `tests/unit/test_seam_router.py::test_importable_bypass_alone_does_not_block_a_route`
keeps the regression from returning.

## Two inertness escapes, found by running it

`CONSEQUENCE_CLASS = INERT` was a claim until the episode ran. It ran, and it
was not inert. Both escapes are recorded rather than quietly patched, because
"we imported another repository and nothing happened" is exactly the kind of
assumption this programme keeps discovering to be false.

1. **Importing the organs rewrote them.** The first run modified nineteen
   tracked `.pyc` files inside WealthMachineIntelligence — a declared read-only
   repository. A byte written into a read-only organ is a write, whatever its
   contents. Fixed by setting `sys.dont_write_bytecode` across organ imports in
   `OrganEntryPoint.resolve()`; the modified files were restored with
   `git checkout`.
2. **The consumer wrote into the kernel.** WMI's agent store resolves
   `data/agent_store.jsonl` against the *current working directory*, so running
   the episode from the kernel root deposited a JSONL file in this repository.
   Containing only the delivery was not enough — the write happens at **import**
   time, during `materialise()`, before any payload moves. Containment now
   wraps the whole episode including the producer, and the files the organs
   create in the scratch directory are counted onto the receipt.

Both are guarded: `test_the_episode_writes_nothing_into_the_kernel_repository`
and `test_organ_side_effects_were_contained_and_counted`. The second is the
non-vacuity half — a containment check that passes because nothing was ever
written would certify an episode in which the consumer never ran.

## What this does NOT establish

`VERIFIED_DEVELOPMENTAL_CLOSURES` remains **0**. No condition should be read as
satisfied beyond what is written here.

| Condition | Status |
|---|---|
| 2 — the target function is actually consumed by a running process | **satisfied for the seam**: a real consumer exists and its loss is measurable |
| 7 — the runtime routes work through the replacement | **NOT satisfied**: there is no replacement. No candidate has been generated |
| 1 — a running process detects the loss | partial: the router records `ROUTE_NOT_ESTABLISHED`; the whole-body closure controller is not yet invoked |
| 3, 4, 5, 6, 10, 11, 12 | untouched — evaluator not frozen, no candidates, no experimental attachment, no restart proof |

What changed is narrow and load-bearing: the consumer whose absence made
conditions 2 and 7 unsatisfiable *by construction* now exists, is real
institutional work, and is proven consumed. The remaining conditions are now
reachable. They are not met.

## Standing constraints, unchanged

No merge, deploy, publication, money movement, external contact, production
credential or physical effect. `CONSEQUENCE_CLASS = INERT` throughout: the
episode runs in-process with no network and no credentials, and both organ
repositories were read and executed but never written. PR #66 remains untouched
at `a6f14d3`. The linker, event spine and registries were invoked, not
reimplemented.
