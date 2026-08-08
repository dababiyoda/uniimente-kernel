# P3 inspection — measured before any construction

Per the continuation order: inspect before building. No P3 runtime code was
written. Three findings, all obtained by grep/inspection at `433c7c5`, decide
the geometry.

## Finding 1 — `MISSING_SEAM: contract_to_runtime_event_binding` (CONFIRMED)

Organ manifests declare `consumes` / `produces` by **contract name**:

```yaml
consumes: [wire-venture-assessment]
produces: [wire-opportunity-packet, context-packet]
```

`EventSpine.subscribe(type_prefix, handler)` routes by **event-type prefix**.

These are different namespaces and **no mapping between them exists anywhere in
the repository.** The only `event_type` usages are `omnimorph/engine.py`
(its own `omnimorph.*` namespace) and `evolution/migration/spec.py`
(a single refusal event). Neither binds an institutional contract to a runtime
event type.

The order's instruction applies exactly: do not invent a mapping from string
similarity. `wire-opportunity-packet` is not evidence for an event type named
`wire.opportunity_packet` or anything else.

## Finding 2 — `REAL_CONSUMER_IMPLEMENTATION_ABSENT`

No organ manifest declares a handler. `grep -c handler organs/*.yaml` returns
**0** for all three. What manifests do declare is `implementation_path`:

```yaml
implementation_path: services/wealthmachine_client.py
implementation_path: services/constitution.py
```

Those paths are **in other repositories.** `services/` does not exist in the
kernel; these are DALEOBANKS paths. The kernel can prove the edge exists and
cannot execute either end of it.

So the four proven edges are proofs *about* code that lives elsewhere. There is
no consumer implementation for the kernel runtime to route a message to.

## Finding 3 — `EventSpine` has zero non-test subscribers

`grep -rn "\.subscribe(" --include=*.py . | grep -v tests/` returns **nothing.**
The event spine is as orphaned as `adapters/` — built, tested, and wired to no
runtime path. Nothing in the kernel subscribes to anything.

## What this means for the geometry

The proposed causal path was:

```
manifests + schemas → InstitutionalLinker → LinkReport → proven edges
  → routing plan → EventSpine subscriptions → real consumer receives message
```

The first four arrows work today. The last two have no material to work with:
there is no contract→event binding to materialize a subscription *from*, and no
in-kernel consumer to deliver *to*.

This is not a reason to manufacture one. A `test_consumer` bound by a
string-normalization rule would satisfy the shape of conditions 2 and 7 while
violating their intent, and the order forbids exactly that.

## Honest disposition

`P3_PARTIAL` — not falsified, not proven.

The geometry is not disproven, because nothing about it is structurally
impossible; it is **unbuilt at two specific, named, bounded places.** The
distinction matters: `P3_GEOMETRY_FALSIFIED` would assert that proven topology
*cannot* control runtime routing here, and the evidence does not support that
claim. It supports the weaker, more useful one — two primitives are genuinely
absent, and they are the first real absences this programme has found after
repeatedly discovering that things merely looked absent.

## The open question the next session must answer first

Whether an in-kernel consumer can exist at all, or whether every real consumer
necessarily lives in another repository.

If the latter, the four-state counterfactual cannot run inside the kernel alone,
and the correct target capability for the first developmental closure may not be
`institutional.cross_organ_edge_resolution` — because its consumers are, by
construction, cross-repository. That would be a genuine finding about the
*choice of first deficit*, not a failure of the developmental thesis.

Do not resolve this by inventing an in-kernel consumer.
