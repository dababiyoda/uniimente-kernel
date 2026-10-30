# Directive completion contract (MW-B), 2026-10-30

The founder wrote on 2026-10-30: "That is done when we completely build the prompt"
(`INTENT-20261030-BUILD-BEFORE-DEVICE-RUN`). The prompt is the 77-section directive in
`docs/intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md`. Before this change nothing computed
that sentence, so the path's node depth could be read as "the prompt is built" while whole sections stayed open.

Base: `feb531d2` (the branch that records the directive and the correction). Reality level: UNIT-TESTED (the checker
and its tests), with the static map computed from cited evidence and a LOCAL run of the nodes the met asks rest on
(below). Nothing here is founder-used, live or externally verified. It grants, attaches and activates nothing.

## What changed

| File | What |
| --- | --- |
| `acceptance/directive-sections.json` | One record per section 1-77: the source's exact heading, the section's testable asks (paraphrase, verbatim excerpt, owner paths, evidence, required tier, computed tier, coverage, blocker), and a units table of the gap-map units with their dependencies. |
| `acceptance/directive-sections.schema.json` | JSON Schema 2020-12 for it. |
| `acceptance/directive.py` | Parses the source's first copy, computes each ask's tier and status by the harness's rules, the section statuses and the two verdicts, and validates the map. Reuses `acceptance/__init__.py` (report, node resolution, real-process reading); no parallel framework. |
| `acceptance/__main__.py` | `check` also validates the map and prints its counts; new `directive` command (`--collect`, `--outcomes`, `--out`). |
| `acceptance/README.md` | The rules, and what is not checked mechanically. |
| `tests/unit/test_directive_sections.py` | 19 tests: the map is sound, and each failure class on a broken copy. |
| `docs/evidence/directive-completion-contract-2026-10-30/local-run-met-asks.json` | The LOCAL run below, per ask. |
| `scripts/ci/check_directive_sections_mutants.py` | 29 mutants, one per safeguard. |
| `.github/workflows/directive-completion.yml` | Runs `directive --collect` and the mutant gate (the full suite already runs the static check). |

Rules (full text in `acceptance/README.md`): an ask's tier is the least-verified of the requirements, contract
functions and pytest nodes it cites, never declared above it; tests reach at most BODY_VERIFIED; an ask is met only at
its required tier and covered; a section is DONE only when every ask is met. "Completely built" is false while any ask
is BUILDABLE_NOT_BUILT or an UNGUARDED PRINCIPLE; "every section DONE" also needs founder and external records.

## Result on this tree (static ceilings: what the cited evidence could establish if every cited test passed)

| Sections | Count |
| --- | --- |
| DONE | 3 (13, 15, 69) |
| PARTIAL | 51 |
| OPEN | 23 (11, 18, 21, 22, 26, 27, 32, 33, 35, 36, 37, 38, 39, 42, 43, 51, 52, 55, 59, 65, 70, 73, 74) |

| Asks | Count |
| --- | --- |
| total | 258 |
| met | 69 |
| open, BUILDABLE_NOT_BUILT | 127 |
| open, FOUNDER_ONLY | 32 |
| open, EXTERNAL | 20 |
| open, PRINCIPLE guarded by named tests | 10 |
| open, PRINCIPLE UNGUARDED | 0 |

Prompt completely built: **NO** (127 buildable asks open). Every section DONE: **NO**.

A unit built on another branch does not count here: its asks move only when it is in this tree and the map cites its
tests (the check then recomputes the section).

## BUILDABLE_NOT_BUILT asks in dependency order

Printed by `python -m acceptance directive`. Units come from the session's gap map against #196 head `4ec00605` and
its review (MU-*, MW-*); ids such as `S14-A` label residuals the gap map named without an id. Units with no open ask
here (MW-A, MU-A, MU-G) still order the others.

| # | Unit | What | Depends on | Asks |
| --- | --- | --- | --- | --- |
| 1 | MW-C | Canonical-owner guard: a function-to-canonical-module registry whose test fails when a new module re-implements a registered function | - | S52.A1, S76.A2 |
| 2 | WU-01 | Build frontier beside the acceptance frontier on `greg path` (the 2026-10-30 correction as a route placement) | - | S12.A3, S68.A4 |
| 3 | WU-02 | One-command whole-path rehearsal `greg rehearse --path`: every built node reached in sequence on one throwaway ledger | WU-01, MW-A, MU-A | S61.A1, S71.A1, S77.A2 |
| 4 | WU-03 | `worker.team`: one signed action fields a role-scoped temporary worker organization in parallel under one grant | MW-C | S23.A3, S38.A2, S39.A1 |
| 5 | WU-04 | Organization-vs-simpler gate with an N5 ledger predicate, and a receipted AI-worker contribution in the N6 closure | WU-01, WU-03 | S39.A2, S58.A3, S68.A2, S72.A3 |
| 6 | WU-05 | Compute bottleneck measured, quantified and verified: optimization first, benchmark before and after | - | S48.A2, S71.A2 |
| 7 | MU-C | Credential handles: audited, target-bound, expiring, with a host-native (libsecret) backend | - | S33.A1, S33.A2, S33.A3 |
| 8 | WU-06 | Enrolled nodes that work: NODE_REVOKE, node-signed receipts admitted only inside the node's cone, an N8 predicate | WU-01, WU-05, MU-C | S48.A3, S49.A2, S58.A4, S68.A3, S72.A2 |
| 9 | WU-07 | Case after-life: refunds, chargebacks and retention or termination netted out of verified revenue | - | S43.A2, S46.A1 |
| 10 | WU-08 | Business whole-loop as section 58 defines it, with an N3 whole-loop predicate | WU-01, WU-07 | S43.A1, S58.A1 |
| 11 | WU-09 | Earned autonomy per (capability, action class, target pattern, budget band) with immediate regression | MW-C | S59.A1 |
| 12 | WU-10 | Browser hands that run: Playwright install and CI, a method-level consequence gate, the action program protected from $from_action | - | S31.A3, S34.A3 |
| 13 | WU-11 | Genesis ATTACK stage before registration, and a per-function failure corpus every later candidate must pass | - | S17.A1, S22.A2, S35.A3 |
| 14 | WU-12 | Night shift closes on a running body (signed TRIBUNAL_REVIEWED); critiques carry executable fail-before/pass-after checks | MW-C | S30.A2, S30.A3 |
| 15 | WU-13 | Cathedral detector and reality-ladder inflation guard computed from git, the ledger and machine-readable claims | WU-01, MW-C | S1.A2, S55.A1, S56.A1, S67.A4 |
| 16 | WU-14 | Consistent backups from a running body on a founder-signed cadence, each proven by a restore drill | - | S47.A2 |
| 17 | MU-B | Capability readiness ladder `greg capabilities --readiness` (KNOWN .. VERIFIED), values never shown | - | S26.A3, S32.A1, S32.A2 |
| 18 | MU-D | Evidence-plane bypass detector: every effectful call site in greg/ and foundry/systems on a justified allowlist | - | S37.A2 |
| 19 | MU-E | Typed blocker projection: every blocker with why, reconsider_when, required_evidence, required_authority, next_move | - | S29.A3 |
| 20 | MU-F | Machine-readable intent and horizon ledger with a continuity guard (sections 8, 11, 54) | - | S6.A3, S8.A2, S11.A1, S54.A2 |
| 21 | MU-H | Canonical-owner records for the duplicated functions, with a live-import guard against retired alternates | MW-C | S52.A2, S66.A2 |
| 22 | S5-A | One disposition index: every material path has exactly one current section-5 disposition | - | S5.A1 |
| 23 | S3-A | Repository-wide AST check for the one authority path (replaces the filename-only and top-level-greg-only guards) | S5-A | S3.A1, S23.A2, S51.A1, S67.A1 |
| 24 | S7-A | Guard the re-issued directive's section-7 capability wording on the path | - | S7.A2 |
| 25 | S11-B | Founder words are append-only: verbatim sources and recorded quotations can never be edited or deleted | - | S11.A2 |
| 26 | S14-A | Succession edges on the path: each node names the durable asset it leaves and the later node it makes easier | - | S14.A3 |
| 27 | S19-A | Unacceptable outcomes and constraints become checked guarantees (ENFORCED, CONTRADICTED or ADVISORY) | - | S19.A2 |
| 28 | S20-A | Executable emergence gate: a recombination must beat its own stated baseline on frozen cases or is refused as integration | - | S20.A2 |
| 29 | S21-A | Acquire before building: qualify project-history sources and installed tools against the frozen contract before any builder | WU-11 | S18.A2, S21.A1, S21.A2 |
| 30 | S22-B | Post-outcome disposition review RETAIN / REPAIR / REGRESS / REMOVE for every formed capability, proposed, never self-applied | - | S22.A4 |
| 31 | S24-A | Embodiment-change detection and re-designation after a body move | - | S24.A4 |
| 32 | S26-A | Download-and-verify install bundle (PACKAGED tier) | - | S26.A1 |
| 33 | S26-B | Setup journey: the eleven install-to-run steps as one founder-mode checklist | S26-A | S26.A2 |
| 34 | S27-A | Converse with GREG: questions answered from evidence on console, CLI and phone | MU-E | S27.A2 |
| 35 | S28-A | Founder alerts: one ledger-derived alert policy delivered to the phone and the local desktop | - | S28.A4 |
| 36 | S28-C | Voice on the remote interface through on-device platform speech | S27-A | S28.A6 |
| 37 | S29-A | Idle-discipline guard: no autonomous busywork (the second half of the gap map's section-29 residual) | - | S29.A4 |
| 38 | D31-C | browser.act: founder-approved consequential browser steps through the Gate | WU-10, MU-C | S31.A4 |
| 39 | D31-D | Linux desktop OS-automation route (window list, keyboard and pointer, screenshot, accessibility read) | - | S31.A5 |
| 40 | D34-A | Plane-separation conformance test across every ingress channel | WU-10 | S34.A2 |
| 41 | D35-A | Dependency inspection and static checks on worker patches before acceptance | - | S35.A2 |
| 42 | D36-A | Asymmetrically signed ledger checkpoints with a founder-device countersignature | - | S36.A3 |
| 43 | S40-A | SOP-first planning: a ratified procedure answers the founder's words with zero model calls | - | S40.A4 |
| 44 | S40-B | Complete the section-40 meters in the SOP trend: worker calls, failure rate, recovery burden, human minutes | - | S40.A3 |
| 45 | S40-C | From a compounding SOP to a callable capability, and to an organ proposal | S40-A | S17.A2, S38.A3, S40.A2 |
| 46 | S41-A | Multi-person work fabric: roster, role routing, working hours, cross-person dependencies, overdue-blocker detection | - | S41.A2 |
| 47 | S42-A | Community claims become institutional learning only through a tested settlement | - | S42.A2 |
| 48 | S42-B | Goal Gravity counts community intake by independent sources, not by volume | - | S42.A1 |
| 49 | S43-A | Regulated-domain screen that routes consequential deliverables to a licensed professional before closure | - | S43.A3, S45.A5 |
| 50 | S45-A | Correction watch: re-verify delivered informational outputs and record append-only corrections | - | S43.A4, S45.A3 |
| 51 | S45-B | Separate fact from labelled interpretation, and let source quality decide acceptance, in the restatement contract | - | S45.A2 |
| 52 | S44-A | Venture objective vector with trust floors: no compounding claim on revenue that trust did not hold | WU-07, S45-A | S44.A2 |
| 53 | S46-A | Surplus-to-capability-investment asks with a pre-declared effect and a measured RETAIN/REGRESS | WU-07 | S46.A2 |
| 54 | S47-B | Black-start recovery core: read-only obligation inventory and safe shutdown when GREG's runtime cannot start | - | S47.A4 |
| 55 | S50-A | Qualify a newly selected model route before mission use (MODEL_ROUTE_SET skips qualification) | - | S50.A3 |
| 56 | S51-A | Organ consequence seams verify a Kernel gate decision instead of an organ-local approximation | - | S51.A2 |
| 57 | S53-A | Place every currently open PR from live state, not a hard-coded list | - | S53.A1, S53.A2 |
| 58 | S60-A | Bottleneck attribution across missions, with the asks 'a human is the bottleneck' and a build-versus-buy estimate | WU-09 | S60.A2 |
| 59 | S62-A | Recurring-bottleneck detector and organizational-form comparison ask (cheapest sufficient form first) | S60-A | S62.A1 |
| 60 | S63-A | Per-venture wedge-ladder position and participant-friction trend, derived from the ledger | - | S63.A2 |
| 61 | S65-A | Validate every deliberation record against the two-pass protocol | - | S65.A1 |
| 62 | S70-A | Answer the required question from evidence: capability delta between two commits | WU-01 | S70.A1 |
| 63 | S73-A | Compute the 40-item final report from evidence, marking prose-only items | WU-01, WU-13 | S73.A1 |
| 64 | - | No gap-map unit. Each ask's blocker states the residual; most name a missions.json requirement that is partial at its tier, or its open gap | - | S1.A3, S2.A1, S4.A1, S4.A2, S4.A4, S10.A1, S17.A4, S18.A1, S22.A1, S22.A3, S27.A1, S29.A2, S35.A1, S35.A4, S36.A2, S36.A5, S37.A1, S38.A1, S45.A4, S47.A1, S50.A1, S50.A4, S67.A2 |

## Commands and results

| Command | Result |
| --- | --- |
| Fail-before: `pytest tests/unit/test_directive_sections.py` (final, 19 tests) in a detached worktree of `feb531d2` | 1 error at collection (`cannot import name 'directive' from 'acceptance'`); 0 of 19 run |
| Fail-before: on `feb531d2`, a map claiming all 77 sections DONE, with section 40 removed and section 13's heading changed, then `python -m acceptance check` | exit 0, "sound": nothing refused the false completion |
| The same broken map against this head (`directive_problems`) | 75 problems: section 40 missing, the heading, and 73 "DONE is claimed with an open ask" |
| `pytest tests/unit/test_directive_sections.py` | 19 passed in 17.1 s |
| `pytest tests/unit/test_directive_sections.py tests/unit/test_acceptance_harness.py tests/unit/test_founder_correction_20261030.py` | 79 passed in 221 s (19 new, 56 harness, 4 correction) |
| `python -m acceptance check` | exit 0: "sound: 12 missions, 85 requirements, 374 distinct test nodes, 18 contract functions" and the directive summary line |
| `python -m acceptance directive --collect` | exit 0: all 103 distinct cited nodes collect. Its first run failed on `tests/unit/test_greg_computer.py`, which skips at module level without Playwright and collects nothing here; that citation was dropped and S31.A3 now cites nothing (OPEN, WU-10) |
| `python scripts/ci/check_directive_sections_mutants.py` | 29/29 caught (run twice; the second on the final tree), exit 0 |
| LOCAL run, `pytest -p acceptance._plugin` over the 58 nodes the 60 met asks that cite only their own tests rest on (`PATH` with supervisord) | 610 passed, 26 skipped, 0 failed in 1324 s; 54 of the 60 asks are met in the run, 6 fall short on skips (`local-run-met-asks.json`) |

All commands ran with `PYTHONDONTWRITEBYTECODE=1 python -B` and `-p no:cacheprovider`.

## Limitations

- The map is a reviewed reading of the directive. Mechanically checked: section count and order, headings, that each
  excerpt is verbatim in its section, that every cited node resolves (and, with `--collect`, collects), that every
  cited contract function, requirement and unit exists, computed tiers, coverage caps, blockers and statuses. Not
  checked: whether a paraphrase is faithful, whether a required tier is what the words ask, SANDBOX against UNIT for
  an ask's own nodes, whether `covered` is honest within what its citations allow, and whether a blocker class is the
  true reason.
- Exhortations no test can observe ("Think deeply", "Do not flatter Alfonso") are not asks.
- Statuses are static ceilings. A run can only lower them: `directive --outcomes` recomputes from recorded outcomes,
  where a failure, error, skip or empty collection leaves an ask unmet. The LOCAL run above covers only the 60 met asks
  resting on their own nodes; the 9 met asks that cite mission requirements rest on the acceptance run's BODY tests,
  which were not re-run here.
- Six met asks rest on tests that skip in this container: S28.A2 and S72.A1 (phone end-to-end: Chromium), S31.A1
  and S50.A2 (bubblewrap namespaces), S45.A1 (a DALEOBANKS checkout, bubblewrap), S60.A1 (Chromium). They are met
  statically; a run here leaves them unmet, and a host that has those tools decides.
- The gap map was drawn against `4ec00605`; this base adds only the directive and correction records.
- The new workflow has not run in CI yet.
