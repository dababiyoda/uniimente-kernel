# Phase 3D — Mechanism Cards, Candidate Architectures, and Mutation Lineage

Governing licence: extract primitive mechanisms from Build-Your-Own-X, mutate
them, recombine them, invent upward. Connecting unchanged components is
integration, not invention. Every selected mechanism below carries at least
three material mutations, at least one of which changes information geometry,
authority, identity, selection, resource allocation, development, recovery,
proof, or consequences.

---

## 1. Mechanism cards

### M1 — Sequence numbers (network protocol / TCP)

**Primitive as found.** A sender stamps each message with a monotonically
increasing integer from a counter it owns. The receiver suppresses duplicates by
`(sender, seq)`.

**Why it fails here.** A developmental cell emits *several* downstream demands in
one transition. One counter per sender cannot distinguish them, so branches
collide. This is defect A, reproduced in `test_a_v1_branch_identity_collision_is_real`:
a cell emitting two roles produced 2 distinct keys for 3 signals, and the
downstream cell deduped a live branch away.

**Mutations.**
1. *Identity geometry* — replace the scalar counter with a **path**: a tuple of
   local emission indices accumulated along the causal chain. Uniqueness stops
   being a property anyone owns and becomes a property of the route.
2. *Ownership* — no cell needs to know a global counter, only its own emission
   index within its own transition. The identity is bounded-local by
   construction rather than by convention.
3. *Duplicate semantics split from branch semantics* — `child()` extends the
   lineage (new branch), `relay()` preserves it (same branch, another route).
   One primitive now expresses two different things that the scalar counter
   conflated.

**Changed dimension:** information geometry and identity.

---

### M2 — Keyed join (relational database / stream processing)

**Primitive as found.** A join operator holds a buffer keyed by join attribute
and emits when all sides have arrived. The operator is a separate component that
sees all inputs.

**Why it fails here.** A join operator is a coordinator. Handing one to the
substrate reintroduces the central planner that Phase 3 exists to eliminate.

**Mutations.**
1. *Ownership inversion* — the join is owned by the **consuming cell**, not by an
   operator above it. There is no component that sees both sides.
2. *Evidence, not delivery* — the receptor binds on **locally observed
   neighbour state** ("that neighbour has become what I need"), not on message
   arrival. A message can be lost; the binding still forms if the neighbour is
   visible.
3. *Monotonic close with an explicit death exception* — bindings are first-wins
   and never withdrawn by duplicates or reordering, which is what makes
   formation order-independent. The single thing that reopens a closed join is
   `release()`, on an **observed death**. Reordering is not death.
4. *Quorum as a first-class close condition* — ALL-of and any-k-of-n are the
   same mechanism with one parameter, so partial-redundancy structures need no
   new machinery.

**Changed dimension:** authority (no coordinator exists) and development.

---

### M3 — Capability refusal (operating-system capability security)

**Primitive as found.** A reference monitor checks a request against a policy and
denies it. The check sits *outside* the operation.

**Why it failed in PR #59.** The check ran outside the transition: the runner
evaluated a proposal, logged a refusal, wrote `Tri.HOLD`, then ran development,
where `ACTIVATE` overwrote `HOLD`. Sixty-two refusals proved sixty-two
classifications and zero preventions.

**Mutations.**
1. *Relocation into the transition* — the constraint is evaluated inside
   `_try_differentiate`, between the decision and the commit. A refusal returns
   `False` and no state changes.
2. *Counter semantics* — `blocked_attachments` increments only when a commit was
   actually prevented, so the number means prevention rather than observation.
3. *Channel separation* — the constraint never touches the role-demand channel.
   Refusing a *configuration* of a role must not make the *role* unreachable;
   `test_c_refusal_does_not_make_the_role_unreachable` pins the PR #59 defect.

**Changed dimension:** consequences and proof.

---

### M4 — Lateral inhibition (developmental biology, via Phase 3)

**Primitive as inherited.** Balanced ternary signalling: `+1` recruit, `0` hold,
`-1` filled-stop. Redundancy is measured to decide whether another cell of the
same role is wanted.

**Mutations.**
1. *Scope* — redundancy is counted over the cell's **own neighbours only**. v1
   scanned every cell in the tissue, which is a global read wearing a local
   name. `GLOBAL_SCAN_COUNTER` records any whole-tissue read during formation
   and the experiment asserts it stays at zero.
2. *Per-cell receptors* — each cell owns its receptors instead of sharing one,
   so one cell's constraint history cannot silently condition another's.

**Changed dimension:** information geometry.

---

### M5 — Content addressing (Git / content-addressable storage)

**Primitive as found.** An artifact's identity is the hash of its contents.

**Mutation, applied to execution output.** A tissue's output is derived from the
**cells that actually carry the work**, not from the set of role names. This is
not decoration: a value hashed from role names is byte-identical before and
after damage, which is precisely how PR #59 "observed" a loss that had not
happened. Under the mutated form, damage that changes the carriers changes the
value, and damage that breaks a join yields `None`.
`test_f_output_depends_on_the_cells_that_carry_it` pins it.

**Changed dimension:** proof.

---

## 2. Candidate architectures considered

Twelve, with the reason each was kept or rejected. Rejections are evidence and
are retained.

| # | Candidate | Disposition |
|---|---|---|
| 1 | Global emission counter per tissue | **Rejected.** Fixes collisions by introducing the shared mutable authority the phase exists to remove. |
| 2 | UUID per emitted signal | **Rejected.** Distinctness bought by making every copy unique, which destroys duplicate suppression — a relayed signal arriving twice would be processed twice. |
| 3 | Lineage of local emission indices | **Selected (M1).** Uniqueness from the path; `relay()` preserves identity so genuine duplicates still suppress. |
| 4 | `attached_to_many: list[str]` | **Rejected.** The prompt names this explicitly. Widening a field is not a join: it records who attached without expressing what is *required*, so nothing can refuse a premature commit. |
| 5 | Central join operator | **Rejected.** Reintroduces a coordinator; the planner by the back door. |
| 6 | Dependency receptor owned by the consumer | **Selected (M2).** |
| 7 | Factor-graph constraint propagation | **Rejected** (carried over from Phase 3C). Correct, but requires a component holding the factor graph. |
| 8 | Quorum as a separate cell type | **Rejected.** Duplicates the join machinery; folded into M2 as one parameter instead. |
| 9 | Constraint as a pre-pass filter over cells | **Rejected.** This is PR #59's architecture: a check outside the transition that a later phase overwrites. |
| 10 | Constraint inside the attachment transition | **Selected (M3).** |
| 11 | Retrograde recruitment — an unsatisfied receptor emits demand for its own missing arm | **Not built. Named as the phase's primary open bottleneck** (§3). |
| 12 | Resource-coupling reported by measurement rather than constant | **Not built. Named as the phase's second open bottleneck** (§3). |

Candidates 11 and 12 were identified *from the experiment's failures*, after the
hold-out was fixed. They are recorded rather than implemented, because the
addendum manifest committed before the run states that a failing held-out
structure is reported and not tuned away.

---

## 3. What the experiment proved, and what it did not

The pre-registered run **failed both gates**. That result stands.

### Bottleneck 1 — recruitment is forward-only

`diamond_reconverge` never formed in any of its 6 episodes. The cause is exact
and reproducible:

```
filled: ['arm_a', 'ingest']
join receptor bindings: {'arm_a': 'arm_a'}
join unresolved: ('arm_b',)
join pending demands: 1
arm_b ever demanded: False
```

The join cell *knows precisely what it is missing* and is holding a live pending
demand, but a cell can only be recruited by an upstream `emits`. An unsatisfied
receptor has no way to emit demand for its own unmet requirement. Fan-in is
therefore **expressible but not self-recruiting** — defect B is half removed.

This is the honest boundary of Phase 3D: the substrate can *represent* a join,
*refuse* a premature one, and *close* one on local evidence, but it cannot
*grow* the arm it lacks.

### Bottleneck 2 — the readout cannot express the prohibited dimension

Gate G failed 6 of 6 `shared_resource_exhaustion` episodes and passed 5 of 5
episodes of every other class. `diagnose.py` enumerates every form
`Tissue2.precipitate()` can emit and finds **zero** that escape that motif,
because `precipitate()` reports a constant `resource_allocation: "static"`. The
certificate prohibits a dimension the successor has no way to vary.

Those 6 failures are therefore not a substrate that failed to escape. They are
the same defect class this phase was convened to remove — a readout reporting a
constant instead of a measurement — surviving in a different field.

### What did hold

| Property | Result |
|---|---|
| Premature join differentiations | 0 |
| Global redundancy scans during formation | 0 |
| Solution leakage from certificates | 0 |
| Observed output loss where damage was felt | 43 / 43 |
| Restoration through a different route | 43 |
| Distinct causally valid forms | 38 |
| Reproducibility across `PYTHONHASHSEED` | byte-identical |

Gate F recovered **11 of 11** valid held-out episodes — a perfect rate on every
episode that was actually a test — but only 11 of 16 episodes were valid, so the
pre-registered threshold of 13 is not met. Carrier-targeted injection
(`diagnose.py` D1) raises that to 12 valid and 11 recovered, still short. The
gate failure is **not** an artifact of the instrument alone.

---

## 4. Defects found in this phase's own work

Recorded because they were found after results existed and both changed the
numbers.

1. **Non-reproducibility.** The first run was not reproducible: `neighbours` is a
   `set`, receptor binding is first-wins, and set iteration order over strings
   varies with `PYTHONHASHSEED`, so which upstream a join bound changed between
   runs. Fixed by sorting every neighbour view. Verified byte-identical across
   three hash seeds.

2. **Partition in name only.** A partitioned edge blocked message delivery but
   still permitted *binding*, because neighbour visibility ignored the partition
   set. A cell was taking evidence from something it could not reach. This is
   the same defect that made PR #59's Gate F meaningless. Caught by
   `test_h_partition_blocks_its_edge_and_forces_another_route`, which was written
   before the run and had been passing only by accident of hash ordering.

Both fixes correct the *measurement*, and both were justified by expectations
that predate the results. Neither was aimed at a gate outcome, and neither
flipped a gate: both gates failed before and after.

---

## 5. Hold-out integrity

`EVALUATION_MANIFEST.json` pre-registered fork-join, asymmetric-depth join,
local quorum and nested branch as held out. Those four were then executed as
probes while building the substrate, and two substrate defects were found and
fixed as a direct result. The substrate was therefore developed **with sight of
them**, so their hold-out is spent and they are demoted to development in
`EVALUATION_MANIFEST_2.json`.

Six structures never executed before that commit took their place:
`diamond_reconverge`, `cross_family_join`, `deep_chain_join`,
`dual_quorum_series`, `partitioned_nested_branch`, `combined_causal_failure`.
One of them — `diamond_reconverge` — failed outright, and is reported rather
than repaired.

`scripts/ci/check_phase3d_preregistration.py` proves from git ancestry that each
manifest commit contains the manifest and nothing else, precedes every commit
touching the implementation and the results, and that neither manifest has been
edited since. A manifest recording its own hash proves nothing; ancestry is the
only tamper-evident ordering available in-repo.
