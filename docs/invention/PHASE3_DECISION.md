# Phase 3 Decision — Constraint-Gated Diffusion

**Gate F is OPEN at 6/10 held-out (threshold 7).** The reason is a structural
finding, not a tuning shortfall, and it was not tuned around.

## The hidden assumption rejected

My own Gate E `CandidateFormer` holds a `CapabilityPool` and enumerates
assignments across it. That embodies:

> a candidate topology must be **constructed** by a component that can **see**
> the capabilities it is composing.

Rejected. Here **no component ever holds a topology.** The topology is only
implicit in which cells attached to which neighbours. A candidate is not
designed; it is *precipitated*, then read out by an observer that took no part
in forming it.

## The reciprocal transformation

| Mechanism | Normally | Mutated |
|---|---|---|
| Dependency resolution (package managers, linkers) | a solver holds the whole graph, computes a closure | **strip the solver** — unify interfaces pairwise, immediate neighbours only |
| Reaction-diffusion / morphogen gradients | continuous fields, no discrete admissibility | **gate diffusion on type compatibility** — the gradient propagates only where attachment is structurally possible |

Neither alone works: dependency resolution without a solver stalls; diffusion
without types converges on garbage. Together: **a viable dependency closure
forms without any component holding the dependency graph.** That is the
capability neither had. It is not "add gossip to the planner" — the planner is
deleted.

## Why ternary is not decoration

A cell must distinguish three states about a role, and two cannot:

```
+1  unfilled near me, recruiting        0  unresolved, holding
-1  filled near me, stop (lateral inhibition)
```

With binary, "not recruiting" collapses *hold* and *satisfied*, and several
cells fill the same role because nobody can say "done". Measured: 3,079
inhibition signals sent; 73 redundant attachments remain across 21 recoveries —
inhibition reduces over-recruitment without eliminating it.

## Result

```
30 episodes (20 development, 10 held out), 4 damage classes
21/30 recovered      6/10 held out  (threshold 7 — NOT MET)
9 distinct valid forms (threshold 3 — met)
0 inherited authority   0 unauthorized external effects
old certificate refused every recovery   old identity refused every recovery
```

Held-out uses a genuinely **unseen capability family** (`gamma`), which is
stronger than Gate E's unused-random-seed notion of held-out.

| Strategy | / 30 | needs global state |
|---|---:|---|
| do nothing | 0 | — |
| restart / identical replica | 0 | yes |
| hardcoded backup | 15 | yes |
| conventional orchestration | 15 | yes |
| **global planner (ceiling)** | **30** | **yes** |
| **local developmental** | **21** | **no** |

## The structural finding

**8 of the 9 failures were admission refusals, not formation failures.** The
tissue formed a viable, fully role-filled structure in 29 of 30 episodes. It was
then refused with `topology_not_materially_different`.

A locally-bounded substrate has **no pressure to be different, only to be
viable.** The predecessor's shape is often the most easily reachable one, so the
tissue rebuilds an equivalent and governance correctly refuses it.

Making the tissue avoid that shape would require telling cells about the
predecessor topology — **exactly the global knowledge Gate F exists to
forbid.** This is a real tension between bounded local knowledge and mandated
novelty. I did not resolve it and did not paper over it.

## Surviving attacks

- **Gate F does not close.** 6/10 held-out.
- **Communication cost is severe:** ~318 messages per recovery against a
  planner's single query.
- **The neighbourhood graph is seeded by the harness**, not grown. Real
  morphogenesis would grow its own adjacency.
- **Lateral inhibition is imperfect** — 73 redundant attachments.
- **The local architecture loses to the planner on rate** (21 vs 30). Its only
  structural advantage is needing no global state; whether that is worth 9 lost
  recoveries is unproven.
