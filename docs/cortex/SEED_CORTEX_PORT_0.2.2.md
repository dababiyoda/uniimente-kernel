# Cortex 0.2.2: the Seed Cortex 0.1.6 repairs on GREG's path

Status: **draft, stacked on PR #184** (`claude/opus-maximus-one-greg-20261014` at `b915085`; the evidence below was
taken on `900c6ae`, and the two later commits change no file a seal here hashes). Consequence-inert. Nothing
here grants authority, attaches a capability, spends, contacts anyone or merges anything.

Machine-readable record: [`seed-cortex-port-0.2.2.json`](seed-cortex-port-0.2.2.json) (every port, every verified
finding, its verdict, disposition and regression test).

## Why this exists

The founder correction of 2026-10-19 (`INTENT-20261019-UPWARD-ASCENT`, #190): convergence is incomplete until every
material overlap is recombined into a measured capability on GREG's own path, and cataloguing or relabelling is not
completion. The Seed Cortex (#167, cortex 0.1.6, based on `main`) and this line's cortex (0.2.1, from the same #141
ancestor) diverged. An independent read of this line found that 17 repairs #167 made were missing here, on the path
`python -m greg run` -> Body.tick -> MissionEngine -> AuthorityOffice.act -> ConsequenceGate -> `greg.cognition.solve`
-> the cortex. This change ports them by mechanism (never a merge: the two routers differ), so the capability dividend
that follows is measured on a sound base, not on receipts that misstate what ran.

This is the prerequisite, not the dividend. The dividend selected under #190's rule (abstention-to-resolution routing:
an abstaining receipt says what would resolve it, and GREG routes exactly one existing kind of ask) is the next
stacked PR, with a pre-registered held-out suite, a matched baseline named before testing, a threshold and ablations.

## Founder-effect compilation

- **Founder expression:** the 2026-10-13 directive (verbatim, sha256 `de5db69c...`, preserved on #167) and its
  translation rules: "impermeable shield" is layered prevention, bounded failure and independent verification;
  "systemic dominance" is superior lawful capability with accepted proof. The 2026-10-19 correction makes the measured
  capability on GREG's path the acceptance floor.
- **Intended effect:** every cortex receipt on GREG's path tells the truth about what ran, what was answered, under
  which authority and at which instant and consequence; competence moves only on real observations of methods that
  ran; and an evaluation never reports a gain over a baseline that did not run.
- **Literal requirements:** none beyond the effect. No metaphor is implemented.
- **Mechanisms reused:** #167's tested rules and regression tests; this line's own content addresses, `code_closure`
  rule, freeze manifests, mutation gate (`scripts/ci/check_cortex_mutants.py`) and owned-source refresh tool.
- **Residual deficit built here:** only the adaptations this line needs (its formal slot's fallback attempts, its
  schedule composition, its host-withheld registry, its signed-mission adapter), and one rule found while porting.
- **Falsification:** each repair has a test that fails on `900c6ae`; each guard has a mutant that the tests catch;
  routed behaviour on the frozen suites must not regress.

## What changed

Ported from 0.1.6 (adapted where this line differs):

| Id | Defect on this line | Repair |
|---|---|---|
| D1 | Settlement accepted any version of a selected method's name | exact `method@version` that was selected |
| PRR-13 | A selected route that never ran could settle competence | must have run: `per_route` or this line's `route.attempts` |
| PRR-14 | A tampered receipt could settle | content address checked first |
| PRR-15 | One receipt could settle a method many times | once per (receipt, method, version); callers rewritten to one decision per observation |
| D2 | Composed routes settled and reordered under the whole problem's class | `route.part_geometries`; settle, reorder and GREG's shadow summary read the part's class |
| D3 | A route the composition cap dropped was called "not required" | `route.dropped_by_cap`, `coverage`, and never recommended around (item 2) |
| PRR-02 | A part with no eligible route was recommended around | abstains `NO_ELIGIBLE_METHOD` with `unanswered_parts` |
| PRR-05 | Options and records were parsed after the organs spent | parsed first; a late rejection reports what ran and spent |
| PRR-00 | An eligible route without its input was called a capability gap | `INSUFFICIENT_EVIDENCE`; on the compiler, narrowed to an empty request |
| PRR-01 | No typed deficit on the cortex receipt | `capability_deficit`, `verified: false`, disabled and host-withheld families named |
| D4, PRR-11 | An expiring mandate passed with no `as_of`; a caller's past `as_of` decided expiry | fails closed; the signed-mission adapter judges expiry at the body clock; direct callers keep their declared instant |
| PRR-16 | A worker could report more model calls than the serving ceiling | refused at `check_receipt` |
| PRR-06, -07, -09, -10 | Evaluation integrity: errored baselines counted as run; the held-out freeze hashed 19 of the 53 modules a scored run loads; a manifest re-read after the run; a repeated arm ran twice | each fixed; a reported run that loaded unfrozen code is `INCONCLUSIVE` |

Found while porting, present in 0.1.6 as well: a payload part whose only reader is withheld was reported as "the
payload carries none of their inputs". It is now a capability gap naming the withheld route.

## The 28 further findings

Each was given to an independent skeptic that had to reproduce it on `900c6ae` (and on #167's `dba14ac` where it
claimed both lineages) or refute it. Result: 26 confirmed, 2 confirmed in a different or stronger form, none refuted.
Twenty-two are fixed here with a fail-before test (two more in part: items 8 and 26); five of them are in both lineages (cap-dropped parts, malformed
records, mandate weights from an expired or out-of-scope mandate, an option's own harm not raising its class, and the
withheld-reader wording above). They are recorded on #167 rather than fixed there: #167's frozen 0.1.6 result, decisive-test counts and transcript replay are bound to its code, and #190's correction lands new work on this integration line, not on a second trunk. The rest are deferred with a reason:

- **7, 8 (ask wording), 10 (GREG ask):** the consumer that turns a cortex abstention into the right founder ask is the
  subject of the capability dividend PR, where it is measured.
- **9:** a read-only CLI's explanatory text that becomes false only under a future evidence index; fix recorded.
- **21:** a signed `bind` or `$from_action` edge can fill a cognition step's `records` from a prior action's output, so
  a machine-written "policy engine allowed" can reach the law gate. The fix belongs in mission binding validation
  (`greg/missions.py`, `greg/pipeline.py`), which the integration owner is changing; recorded for them.
- **24:** the sealed v3 `loss()` crashes when a natively expected claim abstains (fail-closed: no report). Changing a
  pre-registered loss needs its own re-seal decision.
- **26:** the refusing freeze gates are correct; the adjacent hole (re-freezing an observed held-out in place) is
  closed; freeze provenance (source commits, `reproducible_at`) is a recorded follow-up.

## Adversarial review of the port (19 findings, all fixed)

Four lenses reviewed this diff (cortex rules, GREG's path, evaluation integrity, records and the cost of caution);
each finding then went to an independent skeptic that had to reproduce it or refute it. Every finding was also
reproduced here before its fix, and each fix has a test that fails on the reviewed head (`1f1e688`). The worst two
were defects this port introduced:

| Finding | Severity | Fix |
|---|---|---|
| Two checks with one cortex sensor share one receipt; the new once-per-receipt guard raised inside every ledger rebuild, so every later cortex request on that body abstained | high | the claims on one receipt collapse to one decision (a failure on any of them decides); a refused claim is skipped, never raised |
| A schedule whose formal engines were all withheld was recommended, coverage "complete", with no solver run | high | the schedule part is unanswered: `NO_ELIGIBLE_METHOD`, the withheld engines named |
| The body clock reached only direct `problem` requests; compose, compile and chain kept the declared instant | high | one signed-path context set by `cognition.solve` and `cognition.compose`; direct callers unchanged |
| The body clock replaced the payload's `as_of`, flipping evidence freshness | medium | authority expiry is judged at `authority_as_of` (disclosed on the receipt); `as_of` still dates the question |
| A part another part masked (`schedule_request` beside `formal_model`) ran organs the compile never selected | medium | the cortex's own route policy is re-read until only the selected organ is routed; fail closed otherwise |
| A pinned organ's mission reported the other organs' parts as a capability gap | medium | parts outside the pin are not sent, and the receipt says so |
| Any compile harm >= 0.5 was forwarded as class "financial" | medium | the harm reaches the organ as the cortex's own harm levels; its own rule decides the class |
| The extractor's model call was not planned, so an honest worker exceeded the serving ceiling | medium | planned before any organ spends; over budget is `BUDGET_EXHAUSTED` up front |
| Malformed mandate weights, scope, purposes or record ids escaped `Cortex.run` | medium | rejected as records (`MALFORMED_INPUT`) |
| A dominated option under another authority removed the founder's weights | medium | weights are judged over the Pareto front only |
| A lead that timed out could settle a success; the engine that answered could not | low | success needs the method's own answer; a superseded lead settles only its failure |
| Engines that ran were listed as "not required"; a deficit named only one part's families | low | truthful alternatives; every part's withheld and disabled families |
| Evaluation: a truncated reply counted as a run baseline, a malformed one as unrun; an in-checkout venv made every run INCONCLUSIVE; the guard dropped the real reasons; the report dropped INCOMPLETE rows | medium, low | failures inside the call are unreached, malformed replies are scored failures (both runners); installed dependencies skipped; prior verdict kept; rows reported |
| The records said five fixes were made on #167 too | low | corrected: recorded on #167, not fixed there |

One pinned integration test changed with its reason: a financial compile now escalates at the organ (item 19), so the
test of "a world-unverified compile settles nothing" uses a reputation harm of 0.6 that keeps its scenario.

`freeze-v0.2.2.json` was regenerated once, before publication, because the review changed frozen files; the first
manifest (`sha256:62588f5b...`) and its held-out run stay in this branch's history (`78e6846`). The held-out set has
been observed since 0.1.x, so both runs are regression checks: no item's disposition, state or score changed.

## Two lineage conflicts left for the founder

- **A declaration its inputs contradict.** This line makes it a Genesis deficit with dissent (audit 2026-10-14; 16 tests
  encode it); 0.1.6 makes it an abstention that asks for the declaration to be corrected. Porting 0.1.6's rule would
  have reversed a deliberate design and was not done. The dividend PR measures which routing closes more requests.
- **One receipt and a "verified" deficit.** This line's compiler marks a deficit verified within one observation; 0.1.6
  requires recurrence across cycles. The cortex's own deficit here is unverified; the compiler's is unchanged.

## Evidence

- `tests/unit/test_cortex_seed_ports.py` and `tests/unit/test_greg_seed_port_paths.py`: 110 tests; on `900c6ae` the
  repairs' tests fail (the few that pass there guard against an over-strict port), and the review's tests fail on
  `1f1e688`.
- Mutation gate, new group "seed ports": 65 mutants, each removing one guard, all caught (150 in the whole gate; one retired as equivalent, with its reason).
- Frozen held-out (`heldout-v0.1`, 42 items, already observed: a regression check, not a fresh claim): routed quality
  0.964 with 0 critical errors under 0.2.1, the first 0.2.2 freeze and the reviewed one; no item's disposition, state
  or score changed (`tests/evidence/cortex-seed-v0.2.2/`, manifest `sha256:f2ddf5ca...`). The declared model baselines did not run (no local model), so the exit is
  `INCONCLUSIVE`, as for 0.2.1.
- Crossgeo development (24 items) and selection (36 items) partitions, routed, existing, static and abstain arms on
  both trees: no disposition or outcome changed, no hard failure. The repairs close failure classes the frozen suites do
  not contain; their proof is the targeted fail-before tests, not a suite score.
- Seed Genome re-sealed as `freeze-v12.json` (inputs changed: `cortex/contracts.py`, `greg/cognition/seed_path.py`,
  the runner's pointer); the seed replay is valid, 120 of 120; the seed evaluation matches 100 of 100 on both arms with
  0 hard failures.
- No admitted genome's code binding includes a changed file; every recipe lift was already stale on `900c6ae`, so
  GREG's routing among genomes and recipes is unchanged.
- `foundry/owned-source.json` refreshed with the repository's tool (it also adds the base head's own new
  `run_operations.py`, which the inventory test flagged on `900c6ae`).

## Rollback

Revert the stacked commits. `freeze-v0.2.1.json` and `freeze-v11.json` are kept unchanged; the 0.2.1 evidence stays
where it is.
