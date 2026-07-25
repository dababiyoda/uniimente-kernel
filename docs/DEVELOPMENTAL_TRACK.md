# The Two Tracks

**Track A — institutional capability. Track B — morphogenetic runtime. They converge only after each has independently passed its own tests.**

Status: Track A is a research artifact (`docs/DISRUPTIVE_CONFIGURATIONS.md`). Track B Stage 1 is executable and green (`morphogenesis/`, 8 tests).

---

## The correction this document encodes

The fourteen-rung ladder in `DISRUPTIVE_CONFIGURATIONS.md` is a sound economic and operational spine. Built alone it produces a governed, self-improving, venture-producing institutional operating system. That is a real thing and worth having.

It is not an organism, and one passage in an earlier draft claimed otherwise. That draft described a "venture cell" differentiating along a "morphogen gradient," where the gradient was a global environment vector read by a central planner. That is configuration wearing a biology costume. The tell is precise and worth stating so it cannot recur:

> **If any component reads global state, there is no morphogenesis.** A cell that can see the whole tissue is a worker executing a plan. The entire interest of development is that structure arises from agents that cannot see the structure.

Track A is legitimately top-down. Every mechanism in it — affine authority, verified policy hooks, congestion control, generational collection — is about constraint: what may not happen. That is correct for governance and wrong for development. Morphogenesis is bottom-up, local, and unscripted, and it cannot be reached by adding biological vocabulary to a control plane.

So: two tracks, separate proofs, late convergence.

---

## Why they must be separate

This is not project hygiene. Merging early fails in one specific, predictable direction.

**Governance strangles emergence.** The Consequence Gate admits nothing without recognized identity, valid principal, current grant, sufficient evidence, applicable policy, budget authorization, commit-time revalidation, provenance, and outcome obligation. A novel morphology has, by definition, no precedent, no prior evidence, and no grant naming it. Put Track B under the gate during development and every emergent pattern is refused at birth. What survives is the set of morphologies someone pre-approved — which is a configuration system, which is the exact substitution this document exists to prevent.

**And the mirror failure is worse.** Give Track B authority before it is understood and you have an unbounded, self-modifying, structure-generating system with real external effects. That is precisely the thing the Kernel was built to make impossible.

Both failures resolve the same way:

> **Track B is permitted to be ungoverned because it is inert.** It runs sealed, with provably zero external effect. It earns governance rather than being born under it.

That is enforced, not promised. `morphogenesis/__init__.py` may not import `policy`, `authority`, `capital`, `provenance`, or `constitution`, and test T1 verifies it by parsing the source rather than trusting convention.

---

## Track A — institutional capability

Preserved unchanged. Fourteen rungs, each converting a class of failure from unlikely to structurally impossible: durable work, non-rotting memory, statistically-costed plans, affine authority, verified policy hooks, JIT-tiered cost decay, congestion-controlled action rate, generational venture collection, cheap institutional forking, deterministic governance simulation, proofs to strangers, hermetic reconstitution, machine-checked doctrine, federated proof.

**What it produces alone:** an institution that cannot lose work, cannot double-commit, cannot outrun its own verification, cannot keep dead ventures alive, and can prove any of that to a counterparty who distrusts it.

**What it cannot produce alone:** an organ nobody designed. Every capability on that ladder is a capability someone specified. Rung 6's tool synthesis comes closest and still only writes tools to fill gaps a human-defined workflow encountered. Track A's ceiling is the imagination of its authors, which is a high ceiling and a ceiling.

**Track A may not depend on Track B for anything on its ladder.** All fourteen rungs must stand on their own. If a rung needs morphogenesis to work, it is misspecified.

---

## Track B — morphogenetic runtime

Seven stages. Each has falsifiable tests, and a property that cannot fail is not being claimed.

### Stage 1 — Cell and local signaling · **executable, green**

`morphogenesis/` — 8 tests, ~50s.

| Test | Property | Method |
|---|---|---|
| T1 | A cell cannot read global state | AST inspection of `cell.py`: no import of substrate or any Kernel module; `step()` accepts no positional/index argument |
| T2 | Structure emerges where none was placed | Gray-Scott reaction-diffusion from uniform substrate + undirected noise |
| T3 | Cell types are attractors, not assignments | Hopfield-style regulatory network; imprinted types are fixed points, survive perturbation, and naive cells differentiate into them |
| T4 | Unanticipated damage repairs itself | Random excision, no repair code anywhere, unmodified local rules |

**Measured, not asserted:**

```
t=0      interface=0.0339   expressed=0.0169     uniform + noise
t=4000   interface=0.1259   expressed=0.2539     pattern, from nothing placed

wound: 15×15 at (24,12) — 225 cells, 10% of tissue, position and size drawn at test time
post-excision   interface(wound)=0.0122
t=+4000         interface(wound)=0.1044   expressed(wound)=0.2178

recovery: texture 83% of baseline · density delta 0.036
GRN: naive cells reaching a named type 145/200 = 72% (spurious 28%)
```

Two design decisions carry the weight:

**Texture, not just density.** `interface_density` counts neighbour pairs straddling a phenotype boundary. A wound that refilled uniformly would score on expression fraction and fail here. Recovery has to come back with the right *length scale*, which is the thing the local rules generate and nobody encoded.

**Spurious attractors are measured, not hidden.** 28% of naive cells settle into a stable state that is no named type. That is a real Hopfield property with a real biological counterpart — a stable cell state that is not any intended tissue. Reporting the rate is the honest move; asserting it away would make T3 decorative.

**What Stage 1 does *not* establish.** A 2-D torus is used because reaction-diffusion is best understood there, which is what makes the stage falsifiable. It is not a claim that institutional cells are spatially arranged. That claim has to be earned in Stage 2, and it is the hardest thing on this page.

### Stage 2 — Non-spatial topology · **the crux**

Reaction-diffusion needs a neighbourhood metric. Institutions do not have one.

Candidate topologies, each a different theory of what adjacency means: the shared-counterparty graph, the capital-flow graph, the evidence-dependency graph. The choice determines whether anything above Stage 1 transfers.

**Test.** Identical local rules must produce stable differentiated structure on a graph with heterogeneous degree, and regenerate after node removal. Network Turing instability is established theory (Othmer–Scriven), but degree heterogeneity changes the behaviour substantially, and a scale-free topology may not pattern at all.

**Honest risk.** This is where the track most plausibly dies. If pattern formation requires near-regular degree and real institutional graphs are heavily skewed, Stage 1's result is a pretty lattice demo and nothing more. Run this stage early and cheaply, before investing in Stages 3–6.

### Stage 3 — Structural adaptation

The topology itself changes under load. Physarum flux reinforcement: strengthen high-flux edges, prune low-flux ones, and near-optimal transport networks emerge with no designer.

**Test.** Given a load distribution, the network self-optimizes toward a computable optimum. Change the load; it re-optimizes with no rebuild instruction. Falsifiable against the known optimum, so "it adapted" is a number rather than an impression.

### Stage 4 — Bioelectric pattern memory

Levin's central finding: target morphology is stored non-genomically and can be rewritten without touching the genome.

**Test.** Two substrates with byte-identical rule code settle into *different* stable morphologies from different signalling histories — and each regenerates to **its own** morphology after damage. This separates "the rules imply one attractor" from "the tissue remembers which attractor is its own," and only the second is pattern memory.

### Stage 5 — Learned local rules

Replace hand-designed chemistry with a learned update rule. [Growing Neural Cellular Automata](https://distill.pub/2020/growing-ca/) (Mordvintsev, Randazzo, Niklasson, and Levin) demonstrated a learned local rule that grows a target from a seed and regenerates from damage **it was not trained on**.

**Test.** Regeneration from a damage distribution held out of training entirely. Training on damage would make recovery a learned response — which is a supervision tree with more parameters.

**Open.** Published results are on uniform cell-state vectors in a grid. Whether learned local rules survive heterogeneous, typed, non-numeric cell state is unknown.

### Stage 6 — Division, apoptosis, homeostasis

Cells divide and die on local signals alone.

**Test.** Population homeostasis with no population controller, and recovery of stable population after mass ablation. If a global count appears anywhere, the stage has failed.

### Stage 7 — Convergence readiness

All of Stages 1–6 green, while inertness remains provable.

---

## The convergence gate

Convergence is permitted when, and only when:

1. Track A rungs 1–10 are operating with their own tests green.
2. Track B Stages 1–6 are green, each independently.
3. Track B's inertness is still statically provable — no Kernel imports, no external effect path.
4. Neither track has borrowed a guarantee from the other to pass its own tests.

**What convergence actually is** — and it is smaller and safer than it sounds:

> Track B's morphology becomes a **proposal**. Track A's gate still decides.

The Kernel's founding invariant is that the model *proposes* and the gate *decides*. The morphogenetic runtime becomes a second kind of proposer at the same seam. It proposes structure — this organ should differentiate here, this connection should strengthen, this cell should die — and every consequential effect still passes the nine conditions.

This is the resolution that preserves both tracks. Track B keeps its freedom, because proposing is free. Track A keeps its authority, because nothing external happens without it. And the architecture already has the right shape to admit this, which is the one genuinely fortunate thing about the Kernel's existing design.

**What convergence is not.** It is not Track B gaining the ability to act. It is not Track A adopting biological vocabulary. It is not a merge of the two codebases.

---

## Open problems, named so they can be tracked

1. **Topology (Stage 2).** The crux. Everything transfers or fails here.
2. **What is an institutional cell?** A process, a venture, a commitment, a counterparty relationship? Undecided, and the answer determines every other stage. Stage 1 deliberately does not assume one.
3. **Heterogeneous state.** Morphogenesis models assume commensurable cell state. Institutional state is typed, sparse, and mostly incomparable.
4. **Time-scale mismatch.** Stage 1 needs 4,000 ticks to pattern. Institutional signals arrive over days. A morphogenetic process that needs ten thousand institutional cycles to converge is not a runtime, it is a geological process.
5. **Whether regeneration transfers at all.** Reaction-diffusion regenerates because the wound is surrounded by tissue running the same rules. Institutional damage — a market closing, a key person leaving, a regulator moving — may be categorically novel in a way that defeats local repair. This is the question the whole track exists to answer, and it is genuinely open.

---

## The discipline that keeps this honest

The failure this document corrects was not a coding error. It was a vocabulary error: calling a global environment vector a morphogen gradient. The guard against recurrence is a rule, not a good intention.

**Track A may not use developmental language for anything that reads global state.** If a mechanism has a central reader, it is scheduling, allocation, or routing — call it that. "Cell," "gradient," "differentiation," "apoptosis," and "regeneration" are reserved for Track B, where each has a test that can fail.

The vocabulary is load-bearing or it is decoration. Test T1 exists to keep it load-bearing.

---

## Sources

[Growing Neural Cellular Automata](https://distill.pub/2020/growing-ca/) — Mordvintsev, Randazzo, Niklasson, Levin · [Regenerating Soft Robots through Neural Cellular Automata](https://arxiv.org/pdf/2102.02579) · [BraiNCA: brain-inspired neural cellular automata and morphogenesis](https://arxiv.org/pdf/2604.01932) · [Conditional Morphogenesis via Neural Cellular Automata](https://arxiv.org/pdf/2512.08360) · [build-your-own-x](https://github.com/codecrafters-io/build-your-own-x)
