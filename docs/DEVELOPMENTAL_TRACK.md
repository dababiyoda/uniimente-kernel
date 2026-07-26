# The Two Tracks

**Track A — institutional capability. Track B — morphogenetic runtime. They converge only after each has independently passed its own tests.**

Status: Track A is a research artifact (`docs/DISRUPTIVE_CONFIGURATIONS.md`). Track B Stage 1 is executable and green; **Stage 2 has been run and does not pass** (`morphogenesis/`, 20 tests). The Stage 2 result is the substantive content of this document.

---

## The correction this document encodes

The fourteen-rung ladder in `DISRUPTIVE_CONFIGURATIONS.md` is a sound economic and operational spine. Built alone it produces a governed, self-improving, venture-producing institutional operating system. That is a real thing and worth having.

It is not an organism, and one passage in an earlier draft claimed otherwise. That draft described a "venture cell" differentiating along a "morphogen gradient," where the gradient was a global environment vector read by a central planner. That is configuration wearing a biology costume.

### The invariant, corrected

An earlier version of this document stated the rule as *"if any component reads global state, there is no morphogenesis."* **That was wrong — too absolute.** It would have disqualified the Bicoid gradient spanning an entire *Drosophila* embryo, Wolpert positional information, Spemann organiser boundary cues, and Levin's long-range bioelectric coupling. That is to say: most of actual development.

The correct invariant is narrower and sharper:

> **No cell may access the complete target structure, receive a centrally assigned final fate, or use privileged omniscient state.**

**Legitimate developmental inputs, explicitly permitted:** local morphogen fields sampled at the cell's own location; tissue-scale gradients from diffusion and boundary sources; accumulated signals; boundary conditions and organiser regions; long-range signalling including electrical coupling.

**Prohibited:** reading a stored target morphology; having a fate written by anything other than the cell's own dynamics; unbounded input arity — seeing the tissue rather than sampling it.

**The distinction is not range. It is omniscience and assignment.** A gradient spanning the whole embryo is fine. A lookup table from address to fate is not.

Encoded as three independently checkable clauses in `morphogenesis/invariant.py`, and test T1d asserts the *permission* explicitly — a long-range gradient is established, shown to measurably change development, and shown not to violate the invariant. Without T1d this would be the old over-strict rule under a new name.

Track A remains legitimately top-down. Every mechanism in it is about constraint: what may not happen. Correct for governance, wrong for development.

So: two tracks, separate proofs, late convergence.

---

## Why they must be separate

This is not project hygiene. Merging early fails in one specific, predictable direction.

**Governance strangles emergence.** The Consequence Gate admits nothing without recognized identity, valid principal, current grant, sufficient evidence, applicable policy, budget authorization, commit-time revalidation, provenance, and outcome obligation. A novel morphology has, by definition, no precedent, no prior evidence, and no grant naming it. Put Track B under the gate during development and every emergent pattern is refused at birth. What survives is the set of morphologies someone pre-approved — which is a configuration system, which is the exact substitution this document exists to prevent.

**And the mirror failure is worse.** Give Track B authority before it is understood and you have an unbounded, self-modifying, structure-generating system with real external effects. That is precisely the thing the Kernel was built to make impossible.

Both failures resolve the same way:

> **Track B is permitted to be ungoverned because it is inert.** It runs sealed, with provably zero external effect. It earns governance rather than being born under it.

That is enforced two ways, neither of them a promise. Statically, the invariant checker rejects any import of `policy`, `authority`, `capital`, `provenance`, or `constitution`. Dynamically, `test_inertness.py` runs the whole pipeline in a subprocess under audit hooks and rlimits and asserts a clean log **from the parent process** — because source separation is not absence of effect.

---

## Track A — institutional capability

Preserved unchanged. Fourteen rungs, each converting a class of failure from unlikely to structurally impossible: durable work, non-rotting memory, statistically-costed plans, affine authority, verified policy hooks, JIT-tiered cost decay, congestion-controlled action rate, generational venture collection, cheap institutional forking, deterministic governance simulation, proofs to strangers, hermetic reconstitution, machine-checked doctrine, federated proof.

**What it produces alone:** an institution that cannot lose work, cannot double-commit, cannot outrun its own verification, cannot keep dead ventures alive, and can prove any of that to a counterparty who distrusts it.

**What it cannot produce alone:** an organ nobody designed. Every capability on that ladder is a capability someone specified. Rung 6's tool synthesis comes closest and still only writes tools to fill gaps a human-defined workflow encountered. Track A's ceiling is the imagination of its authors, which is a high ceiling and a ceiling.

**Track A may not depend on Track B for anything on its ladder.** All fourteen rungs must stand on their own. If a rung needs morphogenesis to work, it is misspecified.

---

## Track B — morphogenetic runtime

Seven stages. Each has falsifiable tests, and a property that cannot fail is not being claimed.

### Stage 1 — Cell and local signalling · **executable, green**

`morphogenesis/` — invariant, dynamics, and inertness.

| Test | Property |
|---|---|
| T1a/b/c | The three invariant clauses, checked by AST |
| T1d | Long-range signalling is **permitted** and measurably changes development |
| T2 | Structure emerges from a uniform substrate + undirected noise |
| T3 | Cell types are attractors, not assignments |
| T4 | **Local pattern reconstitution after perturbation** |

#### T4 is deliberately not called regeneration

Gray–Scott re-forms spatial texture under local rules. That is real evidence of pattern recovery and it is **not** regeneration: no identity is restored, no function is restored, and no remembered target morphology is involved. Calling it regeneration would claim a Stage 4 result from a Stage 1 experiment. The rename is not modesty — it is the difference between what was measured and what was wanted.

#### Measured as a distribution, against null baselines

24 trials: 6 seeds × 4 wound geometries (square, strip, wide, scattered multi-lesion), with ±3% feed-parameter jitter.

```
INTACT SUBSTRATE          24/24 patterned
  texture ratio  median 1.005   mean 1.017   min 0.000   max 1.791
  >70% recovery: 88%      >90% recovery: 75%
  by wound   square 1.020 · strip 1.111 · wide 0.932 · scatter 1.184

NULL BASELINES
  shuffled neighbours   0/4 patterned  →  cannot reconstitute
  no diffusion          0/4 patterned  →  cannot reconstitute
```

Both nulls fail to pattern at all, which is what makes the intact result attributable to local spatial dynamics rather than to the reaction terms alone.

**Two honest blemishes in that table.** `min = 0.000` — one trial failed to reconstitute entirely. `max = 1.791` — one trial finished with *more* texture than its own baseline, which means the baseline had not fully converged at 3,000 ticks and the denominator is soft. Neither is fatal; both mean the median is the number to quote and the mean is not.

**What Stage 1 does not establish.** A regular lattice, chosen because reaction-diffusion is best understood there, which is what makes the stage falsifiable. It is not a claim that institutional cells are spatially arranged.

#### Inertness is tested at runtime, not by imports

An earlier version claimed inertness from an AST import check. **That was insufficient** — static analysis proves source separation, not absence of effects; a module can still reach out through `__import__`, `eval`, `ctypes`, or a transitive dependency's socket.

`morphogenesis/tests/test_inertness.py` runs the full Stage 1 pipeline in a subprocess under denial, and the **parent** makes the assertion:

- `sys.addaudithook` installed before any morphogenesis import, recording network, subprocess, file-write, native-load, and Kernel-import events
- `RLIMIT_FSIZE = 0` — writes fail at the kernel, not at the hook's discretion
- `RLIMIT_CPU`, `RLIMIT_NPROC` — bounded compute, no process spawning
- a companion test **deliberately performs a network call and a file write** and requires both to be caught; a denial harness that never reports anything is indistinguishable from a broken one

**A false positive found and fixed by this test:** the first version watched `exec`/`compile` as dynamic-code signals. Those audit events fire from CPython's own import machinery — 12 events from importing `json`, `statistics`, and `random` alone — so they cannot discriminate and produced a spurious violation. Dynamic code execution is a risk factor, not an external effect; the effects that matter are network, filesystem, subprocess, and native loading, all of which remain watched and rlimit-enforced.

### Stage 2 — Institutional topology · **run, and it does not pass**

Stage 2 was named as the crux and the most likely point of failure. It was run before expanding the theory. This is the result.

#### The definitions it commits to

**What an institutional cell represents.** A service instance holding exactly one role and processing work items. Chosen over "a venture" or "a commitment" because it is the smallest unit that can exist in multiples, change what it does, be destroyed and replaced, and have a function measurable without interpretation.

**What the tissue's function is.** Work items must traverse `INTAKE → VERIFY → SETTLE` end to end. Function is completed items per tick — the shape of essentially every institutional pipeline, failing in a way you can count.

**Candidate adjacency graphs.** `lattice` (regular degree, control) · `smallworld` (Watts–Strogatz: mostly-local handoffs with a few long ties) · `scalefree` (Barabási–Albert: hub-heavy, which is what counterparty and capital-flow graphs actually look like).

**What damage means.** Hub-targeted cell removal — the largest partner fails, the busiest team leaves. Targeted rather than random, because random removal on a hub-heavy graph mostly deletes leaves and proves little.

**What successful functional recovery means.** Throughput returns to ≥90% of pre-injury baseline within 400 ticks, by cells changing their own role from local signals. No central planner, no prewritten repair path.

**The local rule.** Delta–Notch-style lateral inhibition plus integrated local demand sensing.

#### HFRR — Held-Out Functional Recovery Rate

Parameters were tuned on topology seed 1 and graph seeds 101–137. Every seed reported below (211–251) is disjoint from that set.

```
topology     deg cv   HFRR@10%  @20%   @30%   post-injury largest component @20%
lattice       0.00      100%    100%     0%              1.00
smallworld    0.24      100%      0%     0%              0.91
scalefree     1.03        0%      0%     0%              0.07

local rule vs nulls, pooled across injury fractions:
lattice      local 66.7%   frozen 41.7%   random  0.0%
smallworld   local 33.3%   frozen  4.2%   random  0.0%
scalefree    local  0.0%   frozen  0.0%   random  0.0%
                   median recovery 0.559 vs 0.272 vs 0.206
```

#### The verdict

**HFRR degrades monotonically with degree heterogeneity, and reaches zero on the topology institutions actually have.**

Local differentiation does real work — it beats frozen roles at every topology, roughly doubling median recovery on scale-free. It clears the 90% bar on homogeneous-degree topology and fails on hub-heavy topology.

**One interpretation trap, closed.** The 20% and 30% scale-free figures say nothing about differentiation: hub-targeted removal *shatters* a Barabási–Albert graph, leaving a largest component of 7% of survivors. No mechanism can route work through a disconnected substrate. The interpretable datapoint is 10% injury, where the graph remains 73% connected — and HFRR is still 0%, at a median of 0.85. A test exists specifically to stop anyone later citing the 20–30% numbers as evidence about the rule.

#### Two measured pathologies, and what they cost

**The first Stage 2 build was non-discriminating and the null baselines caught it.** HFRR came out at 100% for the local rule, *and* 100% for frozen roles, *and* 100% for random reassignment. Differentiation was doing nothing. Diagnosis: items random-walked with unbounded hops, so a connected graph is effectively fully connected given time, and any role placement eventually works. Fixed by adding per-cell capacity, a hop budget (TTL), and load in the binding regime. Without the frozen-roles control this would have shipped as a success.

**The local rule thrashed.** With instantaneous queue sensing, cells switched ~0.32 times per cell per tick and the role census collapsed to INTAKE = 1 of 196 under load. Fixed by having cells integrate demand over time rather than chase instantaneous concentration — biologically motivated, since real cells integrate morphogen exposure. Switching fell ~8× and the census balanced to 67/70/59.

#### What this means for UNIIMENTE

Stage 2 was the gate. On its own criterion, **Track B does not currently earn entry.**

But the failure is specific rather than general, and that makes it actionable. The blocker is not "local rules cannot restore function" — they demonstrably can, on homogeneous-degree topology. The blocker is **hub dependence**. Which reframes the question from a code question into an organisational-design one: *can institutional topology be made less hub-dependent?* Deliberately maintaining redundant mid-degree paths instead of routing everything through a few dominant counterparties is a real strategic choice with an independent business case — and it is the precondition for anything in Track B ever working.

That is the finding. Not "morphogenesis works." Not "morphogenesis fails." **Morphogenesis requires a topology you would have to choose on purpose.**

### Stage 3 — Structural adaptation *(blocked behind Stage 2)*

The topology itself changes under load. Physarum flux reinforcement: strengthen high-flux edges, prune low-flux ones, and near-optimal transport networks emerge with no designer.

**Test.** Given a load distribution, the network self-optimizes toward a computable optimum. Change the load; it re-optimizes with no rebuild instruction. Falsifiable against the known optimum, so "it adapted" is a number rather than an impression.

### Stage 4 — Bioelectric pattern memory *(blocked behind Stage 2)*

Levin's central finding: target morphology is stored non-genomically and can be rewritten without touching the genome.

**Test.** Two substrates with byte-identical rule code settle into *different* stable morphologies from different signalling histories — and each regenerates to **its own** morphology after damage. This separates "the rules imply one attractor" from "the tissue remembers which attractor is its own," and only the second is pattern memory.

### Stage 5 — Learned local rules *(blocked behind Stage 2)*

Replace hand-designed chemistry with a learned update rule. [Growing Neural Cellular Automata](https://distill.pub/2020/growing-ca/) (Mordvintsev, Randazzo, Niklasson, and Levin) demonstrated a learned local rule that grows a target from a seed and regenerates from damage **it was not trained on**.

**Test.** Regeneration from a damage distribution held out of training entirely. Training on damage would make recovery a learned response — which is a supervision tree with more parameters.

**Open.** Published results are on uniform cell-state vectors in a grid. Whether learned local rules survive heterogeneous, typed, non-numeric cell state is unknown.

### Stage 6 — Division, apoptosis, homeostasis *(blocked behind Stage 2)*

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
