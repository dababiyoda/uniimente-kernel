# Infinite Goal Chase — recompute, 2026-08-23

> ## UPDATE 2026-08-24 — §3.1's bottleneck was built; the next one is named
>
> `runtime/InstitutionalRuntime.boot(state_dir)` exists and passes the exact
> falsification §3.1 specified — run a governed action, discard every object,
> boot again from the same directory, find the witness, chain and inbox intact.
> `tests/unit/test_institutional_runtime.py`, 18 tests.
>
> **It is adopted, not merely built.** `runtime/session.py` is a composition
> root: `python -m runtime <dir> --rehearse` runs a full Bridge A traversal
> across three organs over the durable ledger, and a second process reads the
> four events, their causal ancestry and the verified chain back out. Building a
> durable runtime and booting through one are different facts and only the
> second is progress — the distinction `identity/pki/` was held to a day
> earlier — so the second was done in the same change.
>
> **All three bridges now have a composition root**, and `A → B → C` runs as
> one pathway into one durable chain: A's assessment feeds B, B's compiled
> experiment feeds C, the Gate records a receipt, and a second process finds the
> receipt and the verified chain intact. Asserted by
> `test_the_whole_chain_is_still_there_after_a_restart`, and the correspondence
> — not a count — is pinned by
> `test_every_bridge_that_takes_a_ledger_has_a_composition_root`.
>
> **§3.1 below is still left standing rather than rewritten**, and the Alpha
> bottleneck is still not closed: what exists is one internally-running pathway
> whose evidence accumulates. `clean_verified_outcomes` is still 0, the
> whole-body verdict is still FALSELY_CLOSED, and a fixture traversal is a
> rehearsal — `proves_external_reality` is a literal `False`.
>
> **Correction to this very update, kept visible.** Its first version said the
> backlog was *six modules* and called the work "mechanical". Checking each
> module individually showed both were wrong: `closure/{kernel,advantage,
> commercial}_registry.py` are the verification harness and must *not* read
> accumulated state, and `bridges/closure_verdict.py` deliberately runs the
> chain it assesses — an earlier author already fixed the empty-ledger version
> of it. The real backlog is three libraries needing two more composition roots,
> which is smaller, different, and not mechanical. The adoption probe has been
> re-pointed twice in one day, both times for the reason
> `_asymmetric_identity_is_only_one_edge_deep` exists.
>
> **The bottleneck is now composition roots for Bridges B and C**, and beyond
> that §4 item 2 — widening identity adoption from 1/6 trust edges.
>
> Composing the runtime surfaced three defects, none reachable while the gate
> and spine sat on separate in-memory ledgers, each demonstrated before it was
> fixed: the transactional **outbox** did not survive a restart; a durable chain
> **silently adopted a different constitution**; and `EventSpine.replay()`
> **raised `KeyError: 'source'`** on Gate lifecycle records — pre-existing on
> unmodified `main`, and unreachable until one ledger carried both writers.
>
> §4 item 1 said "port WP-04's mechanism rather than writing a third one".
> WP-04's Postgres backend was **not** ported and is not in this change; the
> JSONL path is what satisfies Alpha, and gap #24 stays open. See
> `runtime/README.md`.


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
| — | Witness v2 emitted by the live Gate | ❌ | ✅ | `governance.gap_audit._witness_v2_is_not_emitted` reports closed; 1234 tests |
| — | Two confidences distinguishable in the durable record | ❌ | ✅ | `provenance/witness_v2.py` `CONFIDENCE_FIELDS`; `tests/unit/test_two_confidences.py` |
| — | Live constitutional-integrity mechanism | ❌ | ✅ | `python -m governance.integrity` exit 0, 12 artifacts, 1 authorised amendment |
| — | `no_silent_amendment` executable rather than prose | ❌ | ✅ | replayed chain refuses a forged or rewritten record; 16 tests |
| 7 | Isolated workload identity adopted (kernel side) | 🟡 | 🟡→ | `_asymmetric_identity_is_not_adopted` closed; **1/6 trust edges, 2/2 declared hops** (leg 3 adopted 2026-08-24) |
| 26 | Mutual TLS called by something real | ❌ | 🟡 | `bridges/signal_to_venture.py` via `identity/mesh.py`, on both peer boundaries |
| — | Peer-repository transport parity | ❌ | 🟡 | DALEOBANKS PR #74, WMI PR #32 — proposed, unmerged |
| — | Replay protection survives a restart | ❌ | ✅ | defect found and fixed; `tests/unit/test_restart_resume.py` |
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
| Isolated workload identities *adopted* | **1/6 files, 2/2 hops** | Bridge A only, and now on **both** its peer boundaries — leg 3 authenticated WealthMachine on 2026-08-24, having passed a literal until then. The other five files have no peer that is a declared internal service (see the correction under §4 item 2), so the file count is not a path to 6/6 |
| No parallel constitutional authority | **near** | one Gate, one policy engine; DUP-1/DUP-2 (evolution loop, event spine) remain open per the Kimi reconciliation |
| Cross-organ workflow | **partial** | Bridge A runs end to end on fixtures; SIMULATED by construction |
| Peer-repository parity | **proposed** | two draft PRs; unmerged, so parity is not yet a fact |
| Standing bounded mandates | **blocked** | `autonomy/` A0–A9 ladder exists and correctly refuses A5: no external outcomes, no calibrated prediction. Blocked on the missing outsider, not on state. Until 2026-08-24 the ladder could be skipped entirely via `issue(level=8)` — see §4 item 3 |
| Reserved decisions escalate | **done** | `governance.decisions` AWAITING_FOUNDER=0, reserved matters route to human |
| Persistent state / restart-resume | **partial** | see §3.1 — corrected after checking the claim against the code |
| Founder Cockpit | **absent** | no module. `shell/` is a pipeline runner, not a command surface |
| Genuine reasoning / refinery organ | **absent** | WMI is a peer repo, not an attached organ; RailScout is PRs #72/#76/#77, unmerged |

### 3.1 The bottleneck — corrected, and sharper than the first draft

**This section's first draft said "nothing persists across processes; the ledger
is in-memory". That was wrong, and checking it is what found the real defect.**

`EvidenceLedger` has carried optional JSONL persistence with
reload-and-reverify for some time, and `closure/kernel_registry.py::ledger_evidence`
already proved it. `CausalMemory` and `EventSpine.replay()` are *views over the
ledger*, so they rebuild for free once it reloads. Considerably more of
restart/resume existed than the snapshot implied.

What did not survive a restart was one thing, and it was the dangerous one:

> **`EventSpine._seen_ids` — the idempotent inbox — started empty at
> construction.** Replay protection lived only in process memory. A reloaded
> ledger came back with a spine that had never seen anything, so a
> byte-identical peer event was accepted a second time and written to the chain
> again. The hash chain over the duplicate verifies exactly as well as the chain
> over the original, so nothing downstream would have noticed.

Demonstrated before it was fixed (ingest → reload → ingest → two records), then
fixed by deriving the inbox from the ledger like every other view, and pinned by
`tests/unit/test_restart_resume.py`. A standing mandate resuming after a crash
would otherwise have re-ingested every fact it had already processed.

**So the bottleneck is not "build persistence". It is "compose a durable
runtime that uses the persistence that exists."** Every entry point still
constructs a fresh in-memory `EvidenceLedger("sha256:" + "0" * 64)`. Nothing
boots the institution from a state directory.

Under that constraint:

- a **standing mandate** has nothing to stand in;
- a **cockpit** would command a body that forgets between commands;
- a reasoning organ's outputs would not accumulate into anything.

**Smallest falsifiable next step:** an `InstitutionalRuntime.boot(state_dir)`
that composes a durable ledger with the gate, spine and causal memory, and a
test that runs a governed action, discards every object, boots again from the
same directory, and finds the witness, the chain and the inbox intact.

Prior art to reuse rather than reinvent: **PR #78 (WP-04)** built a Postgres
spine backend and a rebuild-from-spine drill, and DUP-2 in the Kimi
reconciliation recommends porting it behind main's existing spine interface.
The JSONL path already satisfies the Alpha requirement; Postgres is the
scale-up, not the prerequisite.

**Method note.** The correction is left visible rather than edited away. The
first draft's error was the ordinary kind — restating a plausible snapshot claim
instead of running the code — and the recompute only earned its keep at the
moment it was checked.

---

## 4. Ordered next work

1. **Durable ledger + restart/resume.** The bottleneck above. Port WP-04's
   mechanism rather than writing a third one.
2. **Widen identity adoption** from 1/6 to 6/6 trust edges. Mechanical now that
   `identity/mesh.py` exists; each edge is a small, independently testable change.

   > **CORRECTED 2026-08-24. "Mechanical" and "6/6" were both wrong**, and the
   > original wording is left standing above so the correction is legible.
   >
   > Examining the five remaining edges one at a time — rather than trusting the
   > sentence — found that **none of them has a peer that is a declared internal
   > service**. `bridges/reality_to_learning.py` receives an outside observer's
   > claim; `embassy/gate.py` admits foreign MCP/A2A agents; `venture_to_experiment`,
   > `experiment_to_reality` and `workflow_to_capability` have no peer hop at all,
   > operating on data already inside the institution. The internal mesh is not
   > the mechanism for any of them, so **6/6 is not reachable by mesh adoption**
   > and the goal as written could never close. A gap that cannot close by the
   > means named is mis-specified, not merely open.
   >
   > What the examination *did* find was a sixth hop nobody had counted.
   > **Bridge A has two peer boundaries and only one authenticated.** Leg 3,
   > commented "the second organ, same discipline", handed the adapter the
   > literal string `"wealthmachine"` while leg 2 passed a certificate-derived
   > organ. `bridge_wealthmachine` was already declared and the mesh could
   > already authenticate it. Now fixed: Bridge A is 2/2 hops.
   >
   > **The file-level count stays 1/6 and deliberately did not move** —
   > strengthening an already-counted file is not widening adoption. But the
   > probe was over-reporting, because a file with two boundaries and one
   > handshake imports the mesh exactly as hard as a file with two. The unit
   > moved from the file to the hop (`_TRUST_HOPS`), which is the third time
   > this probe has been sharpened for the same reason.
   >
   > **The real next question is not mechanical**: it is whether external peers
   > — an outcome observer, a foreign agent — get an attestation mechanism at
   > all, and what it is. That is a trust-model decision, not an adoption task.
3. **Standing bounded mandate**, once state persists — one A5/A6 mandate that
   runs, refuses correctly, and is revocable.

   > **CORRECTED 2026-08-24. This is not unblocked by state persistence.**
   > State now persists (`runtime/`), so the stated precondition is met and the
   > item still cannot proceed: `AutonomyAuthority.promote` refuses A5 because
   > `repeated_successful_external_outcomes` is false (CVO is 0) and
   > `calibrated_prediction` is false (no pair has ever come from reality), and
   > the weakest-link rule means all ten criteria or nothing. Verified by
   > running it, not by reading the docstring.
   >
   > **A standing A5/A6 mandate is blocked by the same missing outsider that
   > holds CVO at 0 and the calibration join empty.** That is one blocker
   > wearing three faces, and it is the honest shape of the graph: several
   > "next" items are the same item.
   >
   > Asking the question found something worse than a blocked item.
   > `issue(subject, tuple_, level=8)` returned an **A8 license against an empty
   > ledger** — production environment, $10,000 budget, external target. The
   > promotion path enforced ten criteria and the constructor enforced none, so
   > the ladder was optional. Fixed: autonomy above A0 now needs a named human
   > authorizer, never UNIIMENTE, recorded on the ledger. The fix creates no
   > second promotion path — `authorized_by` buys a starting position, never a
   > promotion.
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
