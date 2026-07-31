# Phase 3G — 2D handoff: sender-owned ingress closed, live repair still open

Written at the end of the session that implemented 2D. Every number here was
produced by running the suite, not by reading a prior description. Where this
document and an older description disagree, this one was measured.

---

## A. Verified resumption record

| | |
|---|---|
| Repository | `dababiyoda/uniimente-kernel` |
| Base | `main` = `8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1` |
| Resumed from | `agent/event-driven-local-repair-v1` = `4bb0460bf56a73c1063c7004e5ae6723a192bcaf` (PR #65 head) |
| This branch | `claude/uniimente-repo-audit-jpytcy`, branched at `4bb0460` |
| This PR | **#66**, draft, base `main` |
| Worktree at start | clean |
| Merge base | `8cb3074` — `4bb0460` is 60+ commits above `main` |

**The handoff facts were verified before any edit**, and all held:
`main` = `8cb3074`, PR #65 head = `4bb0460`.

Baseline at `4bb0460`, reproduced exactly before touching anything:

```
758 passed · 43 xfailed · 47 XPASS(strict) · 0 skipped
```

All 47 "failures" confirmed `XPASS(strict)` — zero real failures.

**Environment note.** The suite could not run as shipped: the system
`cryptography` package raised `PanicException: Python API call failed` on
import because `_cffi_backend` was missing, erroring out collection of six
`tests/unit` files. `pip install cffi` fixes it. `requirements-dev.txt` does not
pin `cffi`, so a fresh environment hits this. Recorded because it costs a
session's first twenty minutes otherwise.

Final state of this branch:

```
local  823 passed ·  2 skipped(0) · 25 xfailed · 0 failed   (848 collected)
CI     821 passed ·  2 skipped    · 25 xfailed · 0 failed   (848 collected)
verifier V1 PASS · V2 PASS · V3 PASS · V4 PASS · V5 PASS
```

The 2 CI-only skips are the pre-registration ancestry guards, which skip on
GitHub's shallow checkout: `821 + 2 = 823`. V2 runs only `tests/unit` and sees
`800 + 2 + 25 = 827`.

---

## B. Branch and PR discrepancy report

### `#66` — resolved, and then made self-referential

The handoff recorded a dangling reference: PR descriptions mentioned `#66`, but
a direct pull-request fetch did not resolve it. Investigated **before** this
PR existed:

- `GET /repos/dababiyoda/uniimente-kernel/issues/66` → **404**. GitHub numbers
  issues and pull requests from one sequence, so a 404 on the issues endpoint
  rules out both.
- **`#65` was the highest number ever allocated** in the repository.
- `#61` is missing from the pull-request list because it is an **issue** — the
  "blockchain-backed Reality Commitment Layer" RFC. That explains the `#61`
  gap, not the `#66` one.
- `grep` across the branch content at `4bb0460` finds no `#66` in any tracked
  file.

**Conclusion: `#66` was a forward reference to a number that had never been
assigned** — a documentation error, not a deleted, inaccessible, or
cross-repository item.

**It then became true.** The pull request opened for this branch was assigned
number 66. Recorded explicitly, because a future reader who finds `#66` in a
description written before 2026-07-31 would otherwise conclude it always meant
this PR. It did not. Any such reference points at nothing.

### Open pull requests against `main`

`#65` `#64` `#63` `#62` `#60` `#59` `#58` `#57` `#56` `#55` `#54` `#53` `#52`
`#46` `#45` `#44` `#35`, plus this one.

`#57`–`#65` are the Phase 3-series developmental line: successive attempts at
the same gate, each preserved as a separate draft rather than force-pushed over
its predecessor. That is the intended shape — negative evidence stays visible —
but it means **nine open drafts share one lineage**, and only the newest
(`#65`, continued by this PR) carries the current runtime.

### Branch ancestry and canonical classification

- **Canonical line:** `main` ← `release/canonical-v1` (merged as `8cb3074`).
- **Current developmental head:** `agent/event-driven-local-repair-v1`
  (`4bb0460`), continued here.
- Four branches sit at `3d9b5779`, the pre-canonical `main`
  (`agent/iconoclastic-integrity-kernel`, `agent/introduce-railscout-refinery`,
  `agent/technology-anatomy-substrate`, `doctrine/governed-evidence-loop`), and
  the tag `main-pre-canonical-v1-2026-07-19` anchors that point. They are
  historical, not competing heads.
- `founder-intent/six-month-revision-gate` is exactly `main`.

### Why this PR is not on PR #65's branch

The session was directed to develop on `claude/uniimente-repo-audit-jpytcy`.
That branch was cut from `4bb0460` rather than from `main`, so the work
continues PR #65's lineage without pushing to a branch this session was not
authorized to move. **PR #65's branch is byte-identical to how the session
found it.** Merging #66 subsumes #65's content; #65 should be closed as
superseded, not merged separately, and that is Alfonso's call.

---

## C. What was implemented, and what each commit is for

One epistemic purpose per commit, in dependency order.

| commit | kind | purpose |
|---|---|---|
| `c77b6f8` | tests only | 2D harness migration — 21 call sites classified |
| `1f54d28` | **runtime only** | 2D enforcement — ingress, emission, eligibility, sealing |
| `cb4b657` | tests only | instrument correction (a defect in my own spec) |
| `2282c8f` | markers only | 65 specifications activated |

### The migration was classified, not marked

A blanket `transport=HARNESS_DELIVERY` across the 21 sites would have left every
2D specification green while the ingress gate did nothing — indistinguishable
from success in the test report. Sites were classified by **the layer they exist
to test**:

- **Authenticated** (build sender-owned evidence, exercise the real path):
  echo test D (duplicate arrival — a *plain* test that previously passed no
  sender at all); `provenance.py::_relay`, already a real transport simulator
  and left untouched; the admission specs themselves.
- **Harness** (deliberately another layer): the 12 live-path candidate-refusal
  and context-gate specs, whose receivers are selected by capability and never
  by adjacency; the context-gate negative case; three relay-node structure
  builders.

Verified by the property a tests-only commit must hold: the strict-XPASS set was
**byte-identical** before and after.

### The ordering is the security property

`_admit_search` runs first, ahead of terminal-edge replay, the cycle response,
the closed-Need response, duplicate coalescing, the context gate and the node
lookup. Each of those either returns a refund or reveals whether this unit holds
a given SearchKey, so an unauthenticated caller must not reach even a zero-value
replay echo before proving its route.

A refusal writes nothing but its counter. It is deliberately not routed through
`_emit_terminal`, because recording a terminal flips `terminal_status` and
writes organ-wide evidence — refusing an arrival would mutate exactly the
records it failed to justify, and on a fabricated edge would create them.

---

## D. Defects found, including in my own work

**In the runtime (the four the 2D specs targeted).** `sender or
key.origin_unit` reading absence as the origin; `_record_delivery` creating the
probe it was supposed to check against; `_may_emit` admitting unknown edges and
comparing neither key nor destination; `_knows_proposal` treating a *rejected*
proposal as commit-eligible; `_seal` walking past the source's own
`local_candidate` and leaving `eligible_offer` set.

**In my own specification, caught by the specification itself.**
`test_the_harness_bypass_is_counted_and_never_taken_by_live_delivery` claims to
measure a live run's delivery history. It patched `Organ._deliver` and asserted
`seen` was non-empty before drawing any conclusion. That guard fired.

`Organ._pump` is a **second, independent delivery path**: it steps units, drains
outboxes into destination inboxes and increments `messages`, without ever
calling `_deliver`. Measured on the fixture:

```
messages via _pump     1012
messages via _deliver     0
organ.messages         1012
```

The instrument observed nothing, and would have observed nothing whatever the
runtime did. Without that guard it would have reported a clean quarantine result
from an empty list — a passing security test measuring a path that carries no
traffic. Corrected in `cb4b657` to record arrivals instead; it now observes 1012
against `organ.messages == 1012`.

**Recorded as a general finding: `Organ` has two delivery routines.** Any future
instrument, audit or interception that assumes `_deliver` is the only one will
be blind on exactly the fixtures that matter.

---

## E. Accepted residuals — not resolved, deliberately

1. **`_edge_record` still creates on the `_record_delivery` path.** Unreachable
   for a non-harness arrival because the gate now runs first, and the harness
   path depends on creation. *Kill condition:* any future caller reaching
   `_record_delivery` without passing `_admit_search`.
2. **`_may_emit` permits an empty destination** to record without delivering.
   That is how commit and cancellation close an edge whose target is no longer
   tracked. Named destinations are validated.
3. **A probe record is creatable by any unit for any edge id.** Bounded by
   adjacency plus endpoint agreement, so a forged probe only lets a real
   neighbour lie about an edge it could have opened anyway.

---

## F. Continuation handoff

### Exact state

```
branch  claude/uniimente-repo-audit-jpytcy
head    2282c8f
PR      #66 (draft, base main, CI green, verifier V1-V5 PASS)
suite   823 passed · 25 xfailed · 0 failed
```

### The next task, unchanged and precisely located

**Commit 3 — live repair canonical-root migration.**

```
REPAIR_REOPENS_WITH_CANONICAL_ROOT = 0     target: == REPAIR_REOPENS
LEGACY_REPAIR_NEED_MESSAGES        > 0     target: 0
DUAL_REPAIR_SEARCHES               = 0     target: 0 (must stay)
```

**The decisive fact for whoever continues: `SearchKey.build` is never called
from `substrate/v5.py`.** There is no root-origination path in the runtime at
all. Single-Flight has a complete *relay and receiver* implementation and no
*originator*. Commit 3 is a from-scratch build, not a rewiring.

Exact sites:

- `substrate/v5.py` `_emit_need` — the one place a repair search is opened. It
  currently allocates a legacy `_search` ledger and calls `_send_to_frontier`.
  This is where a canonical root must be opened instead.
- `substrate/v5.py` `C.incr("REPAIR_REOPENS")` — the one reopen site, already
  counted, so the denominator is real rather than asserted.
- `substrate/v5.py` `_send_to_frontier` — increments
  `LEGACY_REPAIR_NEED_MESSAGES`. Reached only from a repair reopen or its
  widening, which is exactly why it is the denominator to drive to zero.

What must be built: a `SearchContext` assembled from the unit's own local state
(refused sources, sibling must-differ set, cost ceiling, cooldown set,
constraint generation, policy snapshot); the `SearchKey`; the root node with an
allocation; proposal return routing into `settle_search_offer`; exhaustion;
credit closure through acknowledgements; and retirement of the legacy path **for
repair only** — formation keeps `Need` unchanged, and
`test_formation_still_uses_the_legacy_need_path_unchanged` is a plain test that
pins it.

### Known traps

- **Formation must not move.** It is pinned at exactly **16 events, 1012
  messages** in three files. Any change to that number is a regression, not a
  result.
- **`DUAL_REPAIR_SEARCHES` is the migration hazard**, already wired in
  `_emit_need`: the legacy wave and a canonical root both hunting one slot, each
  unaware the other may settle it. It must stay at 0 — which means the legacy
  path is *replaced* for repair, not run alongside.
- **`TOTAL_CANONICAL_SEARCH_ADOPTIONS` is 0 on an undamaged formation run**, and
  correctly so. The Single Bottleneck Metric must be measured on the scheduler
  path. A `if total:` guard makes it pass vacuously.
- **No global provider index.** A source-level guard already refuses it, and it
  caught a docstring during 2A.
- Every prior cycle surfaced a defect in its own first attempt that only
  measurement caught: a `_may_emit` rule that broke test D, an acknowledgement
  replay guard that made violations invisible rather than refused, a rejection
  guard that made rejections unroutable at the one node obliged to act.

### Forbidden shortcuts

- Do not mark the remaining 25 xfails. They fail because the behaviour does not
  exist.
- Do not weaken an acceptance test because the straightforward implementation
  fails it. Determine first whether the test or the runtime is wrong, and
  preserve both findings.
- Do not combine a runtime change with a test change.
- Do not reuse the retired contaminated held-out draw, and do not read prior
  Phase 3E/3F data as R8.

### After Commit 3

Marker activation for the newly satisfied specs (separate commit) → fresh R8
pre-registration, **manifest committed alone** so ordering is provable by Git
ancestry → development cohort → **untouched** held-out cohort → honest Gate F
and Gate G disposition.

---

## G. Decision dossier

**What now works, with evidence.** Sender-owned evidence is structurally
required at ingress; a receiver cannot manufacture a sender's probe on the
governed path; adjacency, endpoints, key, allocation, direction and identity are
bound; unknown-edge, wrong-key and wrong-destination emissions are refused; a
rejected proposal cannot later be committed while an exact replay of the
accepted one stays inert; a source's own candidate is dispositioned and
deactivated. 65 specifications are active requirements. Formation unchanged. All
violation counters zero on a healthy run.

**What remains unproven.** Everything the experiment is actually about. Gates F
and G are **UNMEASURED**. R8 has not run. No development or held-out cohort has
been executed. The live repair path does not exist, so no claim about repair
without global topology knowledge, alternative-form restoration, or resilience
under partition is supported by anything in this branch.

**Strongest simpler competitor.** A conventional durable workflow engine —
supervisor, static dependency graph, explicit state, targeted retries,
amplification near one. It still appears more reliable and cheaper on the tested
repair problem. **This branch is not evidence against it.** A security boundary
was closed; no capability unavailable to the baseline was demonstrated.

**Actual measured advantage of the developmental architecture: none yet.** That
is the honest reading, and it should stay written down.

**Cost.** Roughly 215 net lines of runtime, seven checks on the ingress path,
and a permanent obligation to keep two delivery paths in mind.

**Remaining bottleneck.** Unchanged and now unblocked:
`REPAIR_REOPENS_WITH_CANONICAL_ROOT: 0 → 1`.

**Disposition: `CONTINUE_WITH_NAMED_BOTTLENECK`.** Not `PROMOTE` — no gate was
measured, and tests passing is not promotion evidence. Not `REGRESS`, `KILL` or
`DEFER` — the named bottleneck is unblocked for the first time, and the 2D
boundary it depends on is now enforced rather than declared.

---

## H. Cross-track integration note

Track B (this developmental substrate) must eventually submit candidates to the
Track A Golden Kernel **without inheriting authority**. The shape that follows
from what now exists:

- A completed wave already produces the raw material for a **candidate**: a
  derived `proposal_id` (SHA-256 over the canonical serialization of the
  complete immutable payload), the accepted proposal's identity, its supplier
  and derivation chain, and a per-edge credit accounting that closes.
- The **proof obligation** would be the wave's evidence: which node adopted
  under which `SearchKey`, which arrivals were admitted and which refused, and
  the violation counters at zero.
- A **function-continuity record** is the restoration claim — a function
  previously served by a failed supplier now served by a different one, with the
  lineage that got there.

The constitutional constraint is already structural here and must stay that way:
**a successful structure proposes; it authorizes nothing.** A wave that commits
has selected a supplier inside a bounded local search — it has not created a
capability grant, widened an authority ceiling, or produced an external effect.
The Kernel would revalidate identity, contract, policy, evidence, authority,
freshness, target and budget on receipt, exactly as any organ's message is
revalidated. Nothing on this branch issues authority, and nothing should.

---

## I. Blockers requiring Alfonso

None for Commit 3 — it is unblocked engineering.

Standing decisions that no build session can supply: whether `#65` is closed as
superseded by `#66`; constitutional ratification; and the six-month
founder-guided revision period, which no amount of green CI can substitute for.
