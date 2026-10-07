# One GREG — reconciliation and build record (2026-09-30)

> October 2 controlling correction: this is historical evidence. Any after-VEPMC/N1 deferral below applies only to its dependent live use, promotion or founder decision; it never pauses unrelated reversible Body + Organs + Mind implementation. Follow [the active continuation intent](../intent/INTENT-20261002-FULL-MACHINE-CONTINUATION.json).

Intent: `INTENT-2026-09-30-OPUS-MAXIMUS-CONVERGENCE` ([source](../intent/sources/OPUS-MAXIMUS-CONVERGENCE-2026-09-30-source.md)).
Machine-readable dispositions, source coverage and conflicts: [`GREG-RECONCILIATION-2026-09-30.json`](GREG-RECONCILIATION-2026-09-30.json).
Supersedes the "canonical frontier" claim of [`ONE-GREG-FRONTIER-2026-09-27.md`](ONE-GREG-FRONTIER-2026-09-27.md) by convergence;
that record's rules and evidence stand.

## What was wrong

- **No GREG on main.** The product (`greg/`, ~7.6k lines, 950+ tests) lived only in ~20 draft PRs.
- **Two canonical futures.** On 2026-09-26 the Chromebook line (#125 → #134) forked from #122 at `73355d0`.
  #122 continued with 11 repairs (learning held-out independence, unreachable GitHub as a brief gap, runbook);
  #128 and #132 were built on #122. Neither line carried the other's work, and main separately gained
  the 2026-09-30 open-source-first stack.
- **The founder's runbook pointed at a stale branch** (`codex/chromebook-first-body`) missing nine later
  commits of its own line and all #122 repairs.
- **Paid cognition by default.** `greg/models.py` fell back to Anthropic → OpenAI → Claude Code when no
  founder selection existed, contradicting INTENT-20260930-open-source-first.
- **Persistence overstated on the real body.** ChromeOS stops Linux at sign-out, never restarts it at sign-in,
  and suspends it with the lid; the morning report never said whether GREG was present.

## What this branch does (`claude/uniimente-greg-reconciliation-39syff`)

1. **Converges** main + the Chromebook line + #122's post-fork repairs + #128 into one branch (additive merges;
   no history rewritten; 20 PR heads are now ancestors). Conflicts: two additive doc conflicts; #128 vs the
   Chromebook line in `greg/appraisal.py` and `greg/capabilities.py`, resolved by union.
2. **Open-source-first routing** (`476d6cc`): no model route unless the founder selects one; paid routes only by name.
3. **Measured presence** (`a0fb215`, `greg/presence.py`): bounded absences between processes (heartbeat carried
   into `body.booted`), host sleep from wall/monotonic divergence, founder stops excluded, late mission work,
   and one `BODY_AVAILABILITY` decision when a shortfall makes missions late. Morning report asks `q0` first.
4. **Chromebook doctor/runbook**: `python3-venv` gap named with its fix, Crostini detected from markers,
   runbook points at this branch and explains what "persistent" means on a Chromebook.

**Product delta:** GREG now tells Alfonso truthfully whether it was actually running and what its absence cost,
and escalates a measured availability shortfall as one founder decision instead of silently implying
continuous operation; and it cannot bill a paid model unless Alfonso's own signed selection names it.

## Canonical owner per function

| Function | Canonical | Alternatives / notes |
|---|---|---|
| Body, lifecycle, supervision | `greg/body.py`, `greg/service.py` | #70 runtime spine: evidence |
| Infinite Goal Chase | `greg/missions.py` | #93/#97/#109 sandbox goal chase: evidence |
| Authority / effects | `greg/authority.py` → Kernel `ConsequenceGate` | none on the GREG path |
| Model routing | `greg/models.py` `ModelRouter` | `egregore/local_model.py` is ADE-1's loopback proposer; transport convergence is a port candidate |
| Capability Genesis / repair | `greg/genesis.py`, `greg/builders.py` | #129 `egregore/parts.py`: port shadow-trial-before-swap later |
| Independent proof | `greg/appraisal.py` (separate process), `greg/anchor.py` | #94 lineage: evidence |
| Learning | `greg/improvement.py` | #119 superseded, #121 deferred to VEPMC = 1 |
| Presence / availability | `greg/presence.py` | new |
| Multi-organ standing deliberation | `egregore/runtime.py` (ADE-1, proposal-only) | not wired to GREG missions |

## Lineage placements (re-expressed under developmental inheritance)

Each lineage is placed on the developmental path in `greg/path.json` with one of ten classes, a node and the axis
that changed: [`DEVELOPMENTAL-INHERITANCE-2026-09-30.json`](DEVELOPMENTAL-INHERITANCE-2026-09-30.json), enforced by
`tests/unit/test_developmental_inheritance.py`. The first pass of this record (commit `2d602bf`) used terminal labels
such as "superseded" and "archive"; the founder's 2026-09-30 correction replaced them.

- **ALREADY_ACHIEVED_NODE (N0):** #101 #102 #108 #109 #110 #111 #113 #114 #118 #120 #122 #125 #126 #127 #128 #130 #131 #133 #134, #115's anchor, #95.
- **NEXT_NODE_INPUT (N2/N3):** #132 Foundry-55 (stacks next), #94 protected evaluation, WMI.
- **PORTABLE_MECHANISM:** #85 run-record binding (ported now), #129 shadow trial, #122's Mac runbook repairs (ported into the Chromebook installer), build-your-own-x.
- **REQUIRES_ADAPTATION:** mac.notify to Body 1, Body 1 credential store, #105, #124, #86's 198-item backlog, #79/#81, `egregore/local_model.py`.
- **TEMPORARILY_DEFERRED:** #121 until N1 exits.
- **FUTURE_NODE_CAPABILITY:** Mac body mechanisms and multi-body (N8), #71's canary (N3), RailScout/DALEOBANKS/RESEARCH-IN (N3), PumpStation (N7), gods-eye-view (N9), #73 (N2), #78 (N8), #88–#92 mechanisms (N5).
- **SUPERSEDED_IMPLEMENTATION_ASSUMPTION** (with the nine-question test): the first-Mac assumption (hardware, sequence), #63/#64/#66 and #88/#90/#92 literal framing, #68's node order, #70's runtime ownership, the synthetic local console.
- **GENUINELY_OBSOLETE** (only two, each with a founder-given basis): #119's second learning engine (replaced by the stronger canonical engine) and GREG's paid default route order (violates open-source-first). Both intended effects remain active.
- **HISTORICAL_EVIDENCE:** #83, #87 (rulings still to be verified as carried), #93/#97, #115's arsenal docs.

No PR was closed, retargeted or merged to main. Those are founder decisions.

## Reality ladder for this session's claims

| Claim | Strongest truthful level |
|---|---|
| One converged branch, suite green | INTEGRATION-TESTED in a Linux container: 1096 passed / 6 skipped / 1 known sibling-dependent failure; verifier V1–V5 PASS under CI-equivalent conditions |
| No paid route without founder selection | UNIT-TESTED, mutation-tested |
| Presence: process death bounded by heartbeat | INTEGRATION-TESTED (real SIGKILLed body process) |
| Presence: host sleep detection | UNIT-TESTED with injected clocks; not observed on a suspending Chromebook |
| Phone interface | SANDBOXED (desktop Chromium, iPhone profile, passes here); Safari 17+ supports Ed25519 WebCrypto per WebKit/MDN, untested on iOS |
| Chromebook body | DOCUMENTED + doctor-probed in a Linux container; not run on ChromeOS |
| VEPMC | **0** |

## Negative evidence

- `test_greg_console.py::test_review_comparison_changes_later_task_and_regression_reverts` fails identically on the
  untouched #134 and #122 heads whenever sibling `daleobanks/` and `wmi/` checkouts exist; CI skips it without them,
  so the failure was invisible. It asserts on live organ state in the superseded `egregore.local_console` path.
- Two branches served as "the" GREG path for four days; convergence by merge was needed, not a new frontier.
- ChromeOS offers no supported Linux autostart at sign-in; the only workaround found (ChromeOS-AutoStart, GPL-3,
  89 stars) depends on a private extension API and is not adopted.

## Bottleneck, next move, founder decisions

VEPMC 0 → 1 remains the Single Bottleneck Metric. Challenged and kept: an availability-weighted metric was
considered, but presence is an honesty guard on VEPMC's `persistent_runtime`, not a replacement; VEPMC is still
non-gameable by agent activity. Every remaining VEPMC condition requires Alfonso.

1. **Alfonso:** on the Chromebook, open Settings → About ChromeOS → Developers and check whether Linux can be
   turned on. If yes, follow `greg/CHROMEBOOK_FIRST_MISSION.md` on this branch. If not (managed device),
   decide on another body. GREG may research candidates; purchase or migration is your call.
2. **Alfonso:** review this draft PR; decide whether it becomes the base for #132 and whether the converged
   PRs listed above may be closed as merged-into-this-branch.
3. **Next agent:** stack #132 on this branch (union-resolve `greg/capabilities.py` and `greg/cli.py`); port #129's
   shadow trial into Genesis replacement; converge `egregore/local_model.py` transport onto `greg/models.OllamaRoute`.
