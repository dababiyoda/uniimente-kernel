# Founder vocabulary and mechanism neutrality

Founder correction 2026-08-09, sharpened 2026-09-09 (`INTENT-0030`, relayed on
PR #68). Standing interpretation rule for every session.

## The binding rule

> **Preserve the intended effect. Do not literalize the metaphor. Search
> reality before inventing architecture.**

Biological and science-fiction language — morphogenesis, organism, organ,
self-healing, Jarvis, embodiment — is an **effect specification and a mechanism
mine**, never mandatory implementation geometry. A biological or organizational
structure earns adoption only if it causally improves the measured effect.

## The mistake this corrects

Alfonso's vocabulary is biological. Sessions sometimes treated the metaphor as
the specification and built things that *looked like* the metaphor, instead of
asking what machinery would produce the behavior the metaphor described.

> "cells" → literal software cells, local signaling, tissue formation
> "self-healing" → elaborate cell-like regeneration
> "morphogenesis" → decentralized cell formation as the goal in itself

The question was never "what is the biological analogue of this?" It was
always:

**What behavior is Alfonso trying to create, and what is the simplest or
strongest mechanism that produces it?**

The project's own evidence exposed the error: some biologically inspired
experiments were beaten by simpler conventional methods. That does not make
them worthless. It makes them **candidate mechanisms that lost a comparison** —
which is precisely what §9 says to do with them. The failure was privileging
them because they sounded closer to biology.

## The interpretation table

| Founder word | Means (behavior) | Does NOT mean (mechanism) |
|---|---|---|
| Egregore | the final coordinated behavior | any particular coordination technology |
| Morphogenesis | **resourceful functional capability formation or reconfiguration after a VERIFIED `CapabilityDeficit`** (canonical, 2026-09-09) | decentralized cell formation |
| Organ | a bounded functional structure | a biological simulation |
| Genome | reproducible capability specification and lineage | DNA-like encoding |
| Self-healing | restore function after failure | cell-like regeneration |
| Mechanistically alive | continuously sense, regulate, adapt, build, repair, learn, preserve continuity | literal metabolism |

Alfonso specifies behavior. **Engineering decides how to achieve it.** That is
his explicit delegation, and it cuts both ways: a session may not hide behind
"he said cells" to justify a weaker mechanism, and may not refuse a biological
mechanism that genuinely wins a comparison.

## The test to apply before building anything

1. State the behavior in one sentence, with no metaphor in it.
2. List at least two mechanisms that would produce it, one of them the boring
   conventional option.
3. Name what would decide between them, and measure it.
4. If the metaphor-shaped mechanism wins, use it — because it won, not because
   it rhymes with the word.

A design that cannot survive step 1 is not yet a design.

## Worked example: "self-healing"

Behavior, stated without metaphor:

> Detect a lost function → find or create another way to perform it → test the
> replacement → restore the function → preserve what was learned.

**"Find" precedes "create."** The mechanisms that satisfy this are, in rough
order of cost:

1. route to a preserved alternative implementation already in the registry
   (§9 competing implementations, §4.3 SUPERSEDED-means-retained);
2. recompose the function from existing Capability Genomes (§4.3, §10);
3. fall back to a specialized or degraded implementation;
4. generate a novel candidate and evaluate it.

Only (4) is the evolutionary metaphor. It is the most expensive and the least
proven, and it is the one the plan had promoted to the default. Under this
correction it competes; it does not preside.

The P3 seam is neutral on this by construction: `TopologyProvider` is a
behavior interface, and closure condition 7 asks whether the runtime routes
work through the replacement — never where the replacement came from.

## The resolution ladder — search before you invent

Any planning derived from a metaphor starts at the target effect or
`CapabilityDeficit` and walks this ladder in order. New architecture is the
last rung, never the first. Implemented as
`capabilities.deficit.RESOLUTION_LADDER`, with one routable
`capabilities.router.ORIGINS` value per rung — an enum that cannot name an
option cannot route to it, which is itself a bias toward inventing.

| Rung | Routable origin |
|---|---|
| 1 existing capability | `CANONICAL`, `RETRIEVED` |
| 2 conventional workflow | `CONVENTIONAL` |
| 3 commodity / open source / API / CLI tool / computer use | `ACQUIRED` |
| 4 mechanism recombination | `RECOMPOSED` |
| 5 new architecture | `GENERATED` |

## Baseline and challenger

The **conventional durable runtime is the primary comparator**; developmental
work is the **challenger**. A developmental proof is not selected because it
looks more organism-like. It must show UNIIMENTE can discover, acquire, compose
or build a genuinely missing capability *and resume a persistent mission better
than a simpler route* — with the simpler route actually run, not described.

`runtime/mission.py` runs both arms against the same loss. Measured result:
both complete the mission and both resume from checkpoint rather than
restarting; the baseline needs **1** external intervention, the challenger **0**.
The challenger's cost is recorded alongside its win — its replacement discards
the linker's unresolved-question and overlapping-authority analysis, and it
only wins at all because a preserved alternative existed. With nothing to find
it degrades exactly to the baseline.

## Verification precedes reconfiguration

Morphogenesis is authorized only after a deficit is **verified** on three
independent facts, each with evidence: something depends on the capability, a
concrete invocation actually failed, and no registered implementation can
serve. `CapabilityDeficit.morphogenesis_authorized()` takes no override
argument — a `force` flag would make the precondition decorative. A failure
while a healthy implementation still exists is not a deficit, and reconfiguring
there would treat a symptom.

## The three buckets

Not new machinery. A lifecycle question the Capability Genome Registry
(§4.3) already answers.

| Bucket | Contents | Registry disposition |
|---|---|---|
| 1 — core machinery | kernel authority, evidence, Capability Genomes, Foundry, OMNIMORPH, causal memory, repair contracts, specialized organs, tests, provenance | `ACTIVE` / `CANONICAL` |
| 2 — useful but over-promoted | MICA/CDPE variants, local cell formation, decentralized repair, "physiology" concepts | `SPECIALIZED` / `FALLBACK` / `EXPERIMENTAL` — **must compete**, never privileged |
| 3 — experiment scaffolding | code proving one narrow analogy or benchmark | `HISTORICAL` — retained as failure corpus, benchmark opponent, regression oracle |

Nothing here is deleted. §12 still governs. Bucket 2's correction is not
removal, it is **losing its privilege**: these mechanisms enter the Capability
Router as competitors and are selected on measured fit, not on resemblance.

> The diagnosis is wrong topology and sequencing, not absence of useful work.
> A large laboratory of mechanisms was built; the experiments were sometimes
> mistaken for the organism. UNIIMENTE sits *above* those mechanisms and uses
> whichever combination best produces the intended behavior.

## What this does not license

This is a rule about **mechanism selection**, not about authority, evidence or
consequence. It does not weaken: the twelve closure conditions; evaluator
sovereignty; the evidence standard; the preservation rule; or Alfonso's
ultimate lawful authority. "Simplest mechanism that produces the behavior" is
never an argument for a weaker proof.
