# Whole-machine trace: one consequence-inert mission end to end, 2026-10-21

Directive 2026-10-21 section 8 (verbatim source: `docs/intent/sources/MIND-MAXIMUM-CONTINUATION-2026-10-21-source.md`),
sections 7 and 10, and `INTENT-20261001-FULL-MACHINE-COMPLETION`. This is a trace of the integrated machine, not a
benchmark. It makes no Polyintelligence-lift (VPL) claim, no commercial claim and no founder-use claim.
**VEPMC stays 0.**

| | |
|---|---|
| Script | `scripts/greg_whole_machine_trace.py` |
| Test | `tests/integration/test_greg_whole_machine_trace.py` (6 tests) |
| Trace | `trace.json`: 9 steps, hash-chained (`prev_step_hash` -> `step_hash`, head `sha256:6261f6af…`). Each step's evidence cites ledger `seq` and record `hash` |
| Source commit | `605c11ef` (clean tree at generation) |
| Run time | 25.5 s on Linux, Python 3.13.16, SciPy 1.18.1, NetworkX 3.7, OR-Tools 9.15.6755, Z3 5.1.0.0 |
| Reproduce | `python scripts/greg_whole_machine_trace.py --out <dir>` |
| Verify a trace | `python scripts/greg_whole_machine_trace.py --verify trace.json` |

**Reproducibility.** Two runs produced the same `reproducible_digest` (`sha256:7cedf0ca…`). The digest covers the
answers, the selected methods, the mission-2 and control routing states, the nine statuses and the input digests.
Ledger hashes, event ids, pids and timestamps differ per run. They come from a fresh temporary body and a fresh
test key. The temporary ledger is deleted after the run, so its `seq`/`hash` references can only be checked during
the run or with `--keep-state`. They cannot be checked from this file alone.

## The mission (GREG's own operating need, natural data)

`m:ci-plan-cognition` is a founder-signed MISSION signed with a **per-run test Ed25519 key, not Alfonso's**. It
validates against `contracts/greg-mission.schema.json`. Its light cone is `cognition.solve` on `cognition:*`,
ceiling `read_only`, $0. It has two checks, and both must be ANSWERED by the Competency Compiler:

- **A. Critical path.** The input is the top-level import graph of `greg/cognition`: 29 modules and 27 edges, read
  with `ast` from this checkout. It is posed as an integer schedule: a module starts after every module it imports
  finishes, and the solver minimises the makespan.
  - Answer: **22 stages** (chain `contracts` -> `compiler`).
  - PROXY: duration = ceil(lines/100).
- **B. CI shard assignment.** Four test-file groups of this repository go one-to-one onto five jobs of
  `.github/workflows/canonical-ci.yml`. The cost is each group's share of the job's `timeout-minutes`, plus 1000 when
  the job does not install a requirement the group's tests import.
  - Group sizes, timeouts and installed requirements are natural data.
  - SYNTHETIC: 400 test lines per CI minute (no CI timing data offline). The one-group-per-job form and the penalty
    are modelling choices.
  - Answer: total **1100**. `greg-cognition-unit` -> `tests`, `cortex-unit` -> `cortex_seed`,
    `greg-integration` -> `sealed`, `contracts-adapters` -> `contracts`.
  - Finding: the optimum still pays one missing-requirement penalty. Only two jobs install `requirements-cognition`,
    and three groups need it. This is a real constraint of the current workflow under the stated model; it is not
    a recommendation to change CI.

Mission 2, `m:ci-plan-body`, has the same class and new natural data:

- **Critical path:** the `greg` package (47 modules, 53 edges). Answer: **53 stages**, chain `capabilities` ->
  `artifacts` -> `genesis` -> `missions` -> `body` -> `cli` -> `__main__`.
- **Assignment:** three groups onto four jobs, including `ade1-standing-cognition.yml:verify`. Total **169**.

Nothing is applied to CI. The plan is computed and verified; acting on it would be a separate founder decision.

## Step by step

Ledger sequence numbers are from the recorded run.

| # | Claim | Evidence in `trace.json` | Reality tier |
|---|---|---|---|
| 1 | **Goal persistence.** The mission was created from a founder-signed command in a temporary state directory. It survived two SIGKILLs of the body process and closed in a third process | `mission.registered`; five `body.booted` (pids of three killed workers, then two in-process boots); four `body.recovered`; `mission.achieved` seq 85; schema errors `[]` | INTEGRATED (local process, test key) |
| 2 | **Method selection by frozen evidence.** The compiler characterised A (geometry `optimization`, inputs derived as `constraint_feasibility/deductive/optimization`, agreeing with the declaration) and selected `cognition.optimization` (CP-SAT) at `selection_level: admission_status`. Rejected: `cognition.formal` (native geometry excludes optimisation) and `cognition.milp_optimize` (frozen status SUPERSEDED, `docs/evidence/greg-genome-admission/2026-10-15-v3/results.json#genomes.milp_optimize`) | compile receipt at seq 69 (the post-restart observation); `frozen_entries_of_rejected_methods`; Z3 certificate in dissent; NetworkX topological DP agrees (22) | INTEGRATED |
| 3 | **Missing-capability resolution.** B's first compile returned `CAPABILITY_DEFICIT` (`cognition.optimization:assignment`). The one Genesis loop then ran its search, qualified the installed SciPy (DEPEND card, BSD, nothing downloaded or installed) and asked the founder. The founder's signed attach came through the inbox; the ORIGINAL mission resumed; the answer carries GREG's dual certificate | Genesis search: verified-detached none, genome library none, `cognition.optimization` and `cognition.assignment_lsa` explained, NetworkX "same engine". Qualification: 19 frozen-oracle cases, 0 failures, no-network interpreter. Ledger order, strictly increasing: deficit 41 < `genesis.verified` 47 < ask 52 < attach 57 < resume 60 < answered compile 81 < achieved 85. Exhaustive enumeration of 120 maps agrees (1100) | INTEGRATED (installed open-source engine) |
| 4 | **Governed execution.** All 11 Gate receipts have a grant and a witness (policy 1.0.0). Every grant ceiling was `read_only`, and every target was under `cognition:`. A CAPABILITY_ATTACH signed by a non-enrolled key was refused | `gate_receipts` 11, `receipts_without_grant_and_witness` `[]`, `external_targets` `[]`; `command.rejected` seq 56 ("founder key not enrolled or revoked") | INTEGRATED. There was no external effect to govern; everything stayed local and sandboxed |
| 5 | **Interruption recovery.** SIGKILL #1 hit while the mission was blocked on the founder ask. SIGKILL #2 hit after `mission.achieved` and before the separate-process appraisal and settlement. Afterwards there was exactly one qualification, one ask, one appraisal and one settlement per check, and no repeated action | Counts at kill #1, after restart and after kill #2 (`gate_receipts` 5 -> 5, `cognition.settled` 0 -> 2, `genesis.verified` 1 -> 1, `decision.requested` 1 -> 1, `mission.action DONE` 1 -> 1) | INTEGRATED (real SIGKILL on Linux; not the founder's device) |
| 6 | **Appraisal and settlement.** The separate-process appraiser returned VERIFIED: the founder signature, inbox arrival, an intact chain, checks re-derived from receipt bytes, re-observation of the world and exactly-once all hold. `cognition.settled` credited `cognition.optimization@0.2.0` and the SciPy mechanism `@1.18.1`, once each. Competence and routing knowledge are projected from the journal | `mission.appraised`: 11 of 12 checks true, and the 12th, `approval_boundary_encountered`, is false because no approval boundary was met; settlements at seq 90 and 91 | INTEGRATED. The appraiser shares reviewed Kernel code ("not an independent implementation") |
| 7 | **A later decision changed by retained evidence.** Mission 2's assignment compile (seq 116) went straight to the formed SciPy mechanism (`selection_level: formed_by_capability_genesis`) with no deficit, Genesis search or founder ask. The identical mission on a fresh control body returned `CAPABILITY_DEFICIT` and asked. Cause: mission 1's retained qualification (`genesis.verified`) and the founder's attach. Mission 1's settled outcomes appear in mission 2's competence basis (`cognition.optimization` 0.6667, SciPy 0.6667) but did not themselves change a choice | `before_mission_1_first_compile` (seq 25), `after_mission_2_first_compile`, `control_fresh_body_first_compile`, `control_counts`, `causes`; mission 2 VERIFIED and settled twice | INTEGRATED |
| 8 | **Organ coordination through canonical contracts.** The linker resolves DALEOBANKS -`wire-opportunity-packet`-> WealthMachine and -> Kernel from `organs/*.manifest.yaml`. A wire OpportunityPacket was validated against its schema and HMAC-verified on transport protocol 2; a replayed nonce, a tampered body and a forged identity were each refused. `adapters/daleobanks_opportunity.py` reports `unresolved: [budget_owner, governing_bottleneck]`, 9 fields lost, 2 added and its assumptions, and it refuses an anonymous resolution. A wire VentureAssessment was adapted and validated against `venture-assessment.schema.json` (`requires_human_approval` true, `execution_authority` false) | `evidence` of step 8 | IMPLEMENTED: contract and adapter only. **DALEOBANKS and WealthMachine code is not in this repository; no organ process ran; both wire payloads are SYNTHETIC fixtures; the HMAC key is a per-run test key** |
| 9 | **Dissent and uncertainty preserved.** Kept in the trace: the compiler's counterargument ("Formal encoding may omit a material condition…"), the Z3 cross-engine certificate statement, conditional uncertainty (`conditional_on_input`, world confidence null; the assignment is "exact for the declared inputs; whether they describe the world is not verified") and the appraiser's limits. A normative question ("drop the slowest group?") returned `HUMAN_JUDGMENT_REQUIRED` and recorded one HUMAN_JUDGMENT ask; that mission never closed (`mission.achieved` 0) | `abstention` (compile seq 177), `independent_rescoring` (both agree) | INTEGRATED |

## Gaps (precise; nothing here was patched around)

1. **Settled outcomes did not change a decision on their own.** The change in step 7 comes from retained capability
   formation plus the founder's attach. Settled competence orders fits only within one admission status
   (`greg/cognition/compiler.py` `_rank`). Each geometry here has exactly one fit. Demotion on live outcomes needs at
   least 10 settled outcomes (`SETTLED_MIN_N`) with a Wilson upper bound below 0.5. A single mission therefore
   cannot move the compiler's choice. Missing: a canonical case with two admitted fits of equal status on one
   geometry, so that one settled outcome reorders them; or a founder-approved lower threshold.
2. **The formed-mechanism receipt carries no competence basis.** On the formed route the compile receipt reports
   `conditional_competence_basis: null` and empty `dissent` (step 7, `after_mission_2_first_compile`). Settled credit
   for the SciPy mechanism is visible only through other receipts and `competence()`.
3. **No GREG mission output reached an organ.** Step 8 exercises the organ boundary, but the packet is a fixture and
   is not derived from the mission. The live organ route (`greg/ventures.py`, `venture.assess`) needs RailScout and
   WealthMachine checkouts inside the body's read roots. It was not run, because this trace is limited to local
   fixtures with no live organs. Missing: a canonical contract carrying a GREG mission outcome to an organ (for
   example, an outcome or DecisionEpisode into Kernel causal memory, consumed by WealthMachine).
4. **The WealthMachine adapter has no `INFORMATION_ADDED` declaration.** `adapters/wealthmachine_assessment.py`
   declares `FIELD_MAPPING` and `INFORMATION_LOST`, but its additions (`assessed_by` from transport, constant
   `requires_human_approval`/`execution_authority`) appear only inside `FIELD_MAPPING`. Not changed here: it is the
   shared, pinned organ boundary.
5. **The clock is accelerated and the worker is not the CLI.** The body runs the canonical
   `Body.boot()`/`Body.tick()` loop in its own OS process, with a clock that advances 31 s per tick and persists
   across restarts. Without this, the 30-60 s waiting cadences would make the trace take minutes. `greg run`
   (`greg/body.py` `Body.run`) has no injectable clock, so the CLI process itself was not used.
6. **Kill #2 is timed opportunistically.** The observer polls the ledger every 5 ms for the window between closure
   and appraisal. The recorded run hit the window. If a run misses it, the trace says so (`kill_2.hit: false`) and the
   claim text changes. Exactly-once is still asserted either way.
7. **Some independence is limited.** The appraiser shares reviewed Kernel code. "Correct" in settlement means the
   answer was certified within the declared model, not that it was verified in the world. The independent rescoring
   (NetworkX DP, exhaustive enumeration) is run by the trace script, not by a separate party.
8. **Proxies and fixtures.** Durations (lines/100), the CI minutes-per-line constant, the one-to-one assignment form,
   the penalty and both organ wire payloads are labelled synthetic modelling choices.
9. **Founder, device and outcome are all absent.** The key is a test key, the host is a Linux container rather than
   the founder's body, nothing was used by Alfonso, and there is no external outcome, revenue or acceptance.
   VEPMC = 0.

## What this adds to GREG

Before this trace, each mechanism was shown in its own test. The trace runs them as one machine on one signed
mission, using GREG's own repository as data, with the evidence linked back to the ledger:

- the Mind's method selection;
- Capability Genesis from an installed open-source engine, under the founder's attach;
- the Gate;
- SIGKILL recovery;
- separate appraisal;
- settlement;
- a second mission that inherits the formed capability;
- the organ contract boundary.

It is reproducible by one command and checked in CI by `tests/integration/test_greg_whole_machine_trace.py`.
