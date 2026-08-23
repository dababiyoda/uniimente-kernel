# Infinite Goal Chase — recompute, 2026-08-23

**Trigger:** `FOUNDER-RULING-2026-08-23`, which requires the whole graph be
recomputed after each capability lands rather than a flat checklist be ticked.

**Baseline:** the 198-item snapshot in
`docs/INFINITE_GOAL_CHASE_CANONICAL_BACKLOG.md` (ChatGPT, PR #86, unmerged),
dated 2026-08-22: ✅ 26 · 🟡 66 · ❌ 109 · 🚫 13 · ⏳ 2.

---

## 1. What this recompute does and does not claim

It recomputes **only the items this session produced evidence for**, and states
the evidence. Every other item carries its 2026-08-22 snapshot status,
unrecomputed.

That restraint is the point. A recompute that restated 198 statuses from a
session that verified a dozen of them would be exactly the "model fluency as
evidence" failure the protocol forbids — and it would be indistinguishable, to a
later reader, from a real audit. **Unrecomputed is a status. It is not ❌ and it
is not ✅.**

The snapshot's own header says the same thing: *"not permanent truth. Before
consequential use, recompute current status from repository and external
evidence."*

---

## 2. Items that moved, with evidence

| # | Item | Was | Now | Evidence |
|---|---|---|---|---|
| — | Witness v2 emitted by the live Gate | ❌ | ✅ | `governance.gap_audit._witness_v2_is_not_emitted` reports closed; 1227 tests |
| — | Two confidences distinguishable in the durable record | ❌ | ✅ | `provenance/witness_v2.py` `CONFIDENCE_FIELDS`; `tests/unit/test_two_confidences.py` |
| — | Live constitutional-integrity mechanism | ❌ | ✅ | `python -m governance.integrity` exit 0, 12 artifacts, 1 authorised amendment |
| — | `no_silent_amendment` executable rather than prose | ❌ | ✅ | replayed chain refuses a forged or rewritten record; 16 tests |
| 7 | Isolated workload identity adopted (kernel side) | 🟡 | 🟡→ | `_asymmetric_identity_is_not_adopted` closed; **1/6 trust edges** |
| 26 | Mutual TLS called by something real | ❌ | 🟡 | `bridges/signal_to_venture.py` via `identity/mesh.py` |
| — | Peer-repository transport parity | ❌ | 🟡 | DALEOBANKS PR #74, WMI PR #32 — proposed, unmerged |
| 5 | Golden Kernel canonical authority root | 🟡 | 🟡 | unchanged; the Gate no longer self-grants externally, which narrows it |

**Nothing moved to HARDENED. CVO remains 0.** Every item above is internal and
consequence-inert. `python -m bridges.closure_verdict` still reports
FALSELY_CLOSED on all seven loops, and that is correct.

---

## 3. The Alpha dependency graph, recomputed

The founder's Alpha definition, each component against current repository
evidence rather than against intent.

| Component | State | Evidence / what is missing |
|---|---|---|
| Canonical Witness v2 / action history | **done** | Gate emits all four v2 facts; v1 signatures still verify |
| Auditable lineage | **done** | evidence ledger + causal memory + amendment chain |
| Causal memory | **done** | `memory/causal.py`, exercised by Bridge A |
| Automatic refusal / kill | **done** | Gate fails closed on 9 classes; shutdown policy enforceable |
| Isolated workload identities *adopted* | **1/6** | Bridge A only. `venture_to_experiment`, `experiment_to_reality`, `reality_to_learning`, `workflow_to_capability`, `embassy/gate.py` still unauthenticated |
| No parallel constitutional authority | **near** | one Gate, one policy engine; DUP-1/DUP-2 (evolution loop, event spine) remain open per the Kimi reconciliation |
| Cross-organ workflow | **partial** | Bridge A runs end to end on fixtures; SIMULATED by construction |
| Peer-repository parity | **proposed** | two draft PRs; unmerged, so parity is not yet a fact |
| Standing bounded mandates | **partial** | `autonomy/` A0–A9 ladder exists; no mandate is actually issued and running |
| Reserved decisions escalate | **done** | `governance.decisions` AWAITING_FOUNDER=0, reserved matters route to human |
| Persistent state / restart-resume | **absent** | nothing persists across processes. `InternalMesh` dies with the process; the ledger is in-memory |
| Founder Cockpit | **absent** | no module. `shell/` is a pipeline runner, not a command surface |
| Genuine reasoning / refinery organ | **absent** | WMI is a peer repo, not an attached organ; RailScout is PRs #72/#76/#77, unmerged |

### The current bottleneck

**Persistent state.** Not the cockpit, and not the reasoning organ.

Everything above that says "done" is done *within one process*. The ledger, the
mesh, the causal memory and the witness history all vanish on exit. Under that
constraint:

- a **standing mandate** cannot stand — there is nothing for it to survive in;
- a **cockpit** would command a body that forgets between commands;
- **restart/resume** is not a feature to add, it is the precondition;
- and a reasoning organ's outputs would not accumulate into anything.

Alpha's remaining five components are all downstream of one missing capability.
That is the shape a dependency graph is supposed to reveal, and it is why the
recompute is worth doing before building the most visible thing next.

**Smallest falsifiable next step:** make the evidence ledger survive a process
restart with its hash chain intact, and prove it by writing a witness, killing
the process, restarting, and re-verifying the chain from disk. Falsifiable in
one test. Unlocks mandates, cockpit and resume.

Prior art to reuse rather than reinvent: **PR #78 (WP-04)** already built a
Postgres spine backend and a rebuild-from-spine drill. DUP-2 in the Kimi
reconciliation recommends porting it behind main's existing spine interface.
This is the same bottleneck, already partly solved on an unmerged branch —
which is exactly the recombination the founder's "one institution, not competing
architectures" rule asks for.

---

## 4. Ordered next work

1. **Durable ledger + restart/resume.** The bottleneck above. Port WP-04's
   mechanism rather than writing a third one.
2. **Widen identity adoption** from 1/6 to 6/6 trust edges. Mechanical now that
   `identity/mesh.py` exists; each edge is a small, independently testable change.
3. **Standing bounded mandate**, once state persists — one A5/A6 mandate that
   runs, refuses correctly, and is revocable.
4. **Founder Cockpit** over a body that remembers.
5. **Attach a reasoning organ.** WMI is the fastest working path per the ruling;
   RailScout's research-refinery intent stays preserved and subsequently built,
   not silently replaced.
6. **CANARY-0001 GO/NO-GO** — founder-reserved. Internal prerequisites are now
   closed (see §5).

---

## 5. CANARY-0001 status change, for the founder's attention

The canary's two **internal** blockers are gone, and neither was removed by
relaxing anything:

- the confidence floor is unchanged at 0.70, the sealed prediction unchanged at
  0.55, and they are simply no longer compared to each other;
- witness v2 emits, so a run would produce a calibratable record.

The Consequence Gate now **admits the consequence-inert rehearsal**. It does not
authorise the canary: `authorized_by` is `None` with no code path that sets it,
`proves_external_reality` returns a literal `False`, the rehearsal target must
carry a `rehearsal:` prefix, and the module contains no network primitive.

Remaining blockers are all founder-reserved or external: authorization, a live
platform credential, a public network surface.

**This is surfaced rather than buried because it is a state change in the item
the founder reserved.** Gate admission is not permission, and the GO/NO-GO
remains Alfonso's.

---

## 6. Long-horizon items — preserved, not recomputed

Developmental machinery, autonomous capability construction, real self-repair,
alternative-form regeneration, MICA/CDPE research, PumpStation/MANO/MANA,
Venture Cells, economic self-sustainability, private compute, scientific
institutions, laboratories, embodiments, IoT, robotics, manufacturing,
infrastructure, governed descendants, distributed institutional nodes and
regenerative civilization-scale systems all remain on the horizon at their
2026-08-22 status.

None was recomputed this session, because none had evidence move. They are
listed here so their absence from §2 reads as *unrecomputed* rather than as
*retired* — `not implemented ≠ not intended`, and neither does
*not mentioned this week*.

The nearest enabling capability for most of them is the same one §3 names:
state that survives a process.
