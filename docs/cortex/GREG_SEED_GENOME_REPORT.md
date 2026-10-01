# GREG seed genome: the Competency Compiler on the mission path

Cortex 0.2.1 · branch `claude/greg-seed-genome-build-y43kmg` (stacked on PR #137, with #140 and #141) ·
2026-10-01 · decision **EXPERIMENT** · authority change **none** · VEPMC **0 → 0**

Source: [`GREG-SEED-GENOME-DIRECTIVE-2026-10-01-source.md`](../intent/sources/GREG-SEED-GENOME-DIRECTIVE-2026-10-01-source.md).
Decision record: [`ADR-20261001-greg-seed-genome.md`](../decisions/ADR-20261001-greg-seed-genome.md).

## What GREG can do now that it could not before

Inside a founder-signed mission, GREG takes a bounded problem and returns typed, independently
checked computation:

- a formal model (feasibility, entailment, optimization), solved by Z3 or CP-SAT. Each returned
  assignment is re-checked against the source model by a verifier that shares no solver, and an
  optimum is certified by the other engine;
- an estimate with units, ranges, dependencies and sensitivity;
- a causal question, answered only when identification is declared and refutations pass;
- evidence for a claim, options behind hard gates, a lawful deterrence question;
- **a schedule written in controlled words**. It is extracted and audited by a token scan independent
  of the extractor, then solved to a certified optimum, shown back as a reverse translation, and
  handed to the Gate for any action.

The receipt creates no authority. It settles competence exactly once, across `kill -9` and restart,
and only from appraised, re-observed outcomes. Before this branch, GREG's own cognition path could
not express disjunctive scheduling, options or claims: on the fresh held-out set it abstained on
918 of 1,200 problems.

## Entry

From the founder console (Chromebook browser; iPhone through the remote interface), type the schedule
in the controlled language, review the proposal, sign. No model is needed:

```text
Shift: 10 hours. Job J takes 3 hours. Job K takes 2 hours. Job L takes 4 hours. J before L.
One machine; one job at a time. Minimize total completion time. The machine is free all shift.
```

The same from a terminal, and any cortex problem as a signed mission:

```bash
greg mission new schedule-in-words --text "Shift: 10 hours. Job J takes 3 hours. ..." --key founder.pem
greg cognition mission --request problem.json --id m:plan --field output.answer.objective --equals 7 --key founder.pem
```

`problem.json` takes `{"problem_id", "problem": {"question", "payload"}}`. Both create a read-only
mission whose step is `cognition.solve`. The receipt for the words above is
`docs/cortex/examples/receipt-schedule-composition.json`; a full mission with an approval-gated write
and `kill -9` is `tests/integration/test_greg_cortex_rehearsal.py`.

## Four states, kept apart

| State | Holds? | Evidence |
| --- | --- | --- |
| IMPLEMENTED | yes, for the seed classes, verifier, composition, settlement and instrument | `cortex/`, `greg/cognition/bridge.py` |
| INTEGRATED | yes: one entry, one registry, one receipt envelope, one settlement | `tests/integration/test_greg_cortex_mission.py` |
| VERIFIED IN THE TESTED ENVIRONMENT | yes, in a Linux container with Python 3.11.15, z3-solver 5.1.0.0, ortools 9.15.6755 and supervisord 4.3.0 standing in for the systemd unit | `tests/evidence/greg-cortex-rehearsal/`, `tests/evidence/greg-crossgeo-v0.3/` |
| AUTHORIZED / VERIFIED FOR LIVE USE | **no**: no founder run, no Chromebook, no founder-selected model | — |

## The frozen comparison

Five arms, a loss declared before any run (`cortex/evaluation/crossgeo_loss.py`), 200 held-out items
per stratum (1,200, sized by the selection split's power plan: about 1,109 needed for a 10% effect),
and a separate adversarial suite. Gold answers come from brute force, planted values and stated
rules.

**v0.2 — `GAIN_ABSENT`.** One hard failure: a problem declared `internal_write`, whose harm vector
said high financial harm ("releases a vendor payment"), was recommended. The static router failed it
the same way. Kept as evidence: `tests/evidence/greg-crossgeo-v0.2/results.json`.

**Fix (0.2.1):** a declared harm vector may now raise the consequence class but never lower it.

**v0.3 — `GAIN_VERIFIED_AGAINST_RUN_BASELINES`**, on fresh held-out and adversarial samples:

| Arm | Held-out mean loss (95% CI) | Hard failures |
| --- | --- | --- |
| routed_greg (proposed) | 0.0187 (0.0137–0.0239) | 0 |
| static_router (strongest that ran) | 0.0251 (0.0198–0.0305) | 0 |
| existing_greg (#140 path, declared adapter) | 0.3180 (0.2998–0.3368) | 0 |
| always_abstain (reference) | 0.3430 | 0 |
| always_llm, tool_llm | `NOT_RUN`: no founder-selected loopback model; downloads egress-blocked | — |

Paired gain over the static router: **0.0064 (0.0044–0.0084), 25.6% relative**. All six
misclassification variants were handed off.

**Read this number narrowly.** A post-hoc decomposition (not part of the frozen rule) puts about all of
the gain in one family: incomparable option trade-offs go to the founder (handoff) where the static
router abstains. Excluding that family, the routed system is slightly *worse* (−0.00042), because the
isolated worker costs a median 0.22 s against 0.013 s. Without the latency term the two routers are
outcome-identical elsewhere. The cortex's other mechanisms (engine fallback, certificates, the
verifier, the budget controller) changed no held-out outcome: the shared organs already answered those
problems correctly. They show their value where the held-out set does not reach:
- the injected Z3 outage, now answered by CP-SAT (`tests/evidence/cortex-seed-v0.2.0/`);
- the lying-engine and mutation tests;
- the budget defect caught on selection.

No superiority over a model is claimed.

## Real versus simulated

| Real | Not real here |
| --- | --- |
| Z3 and CP-SAT solves; brute-force oracles; the supervised body, `kill -9`, signed founder commands, separate-process appraisal | the founder's key and machine (per-test key, container); any language model (the semantic route and the model arms abstain or are `NOT_RUN`) |

## Requirement coverage

All 141 requirements in the requirement map carry 18 fields. They are the 122 crosswalk rows of
Appendix A, the 8 section-2 ambiguities and the 11 section-21 completion conditions.

- Lifecycle: 72 implemented, 28 active, 38 deferred, 2 exploratory, 1 needs evidence (the routing-gain
  claim against a model).
- Implementation: 56 verified in the tested environment, 2 integrated, 4 implemented, 28 partial,
  6 reserved and disabled, 23 horizons, 22 records.

## Negative evidence kept

- v0.2 `GAIN_ABSENT`.
- Two mutants that survived the first mutation run.
- The budget defect found on selection (SIGXCPU).
- A gold-label error (high privacy harm marked gate-failing against the declared policy).
- The token audit's over-abstention on a sentence-initial "We".
- The audit's disclosed blind spot.
- A stale system-level map embedded in the frozen v0.2 suites.

## Unresolved dissent and founder decisions

- Should high privacy harm be a hard gate? (SG-012)
- No superiority claim until the model arms run on the frozen v0.3 suite.
- Merge and promotion: `NEEDS_FOUNDER_DECISION`.

## Residual risks

- The suites are self-authored.
- The engines and the verifier share one parser (disclosed; brute-force oracles in the tests).
- Outcome feedback is local appraisal only, with no external outcome.
- The suite files add about 4 MB.

## Rollback

`greg detach cognition.cortex` (founder-signed) withholds the router immediately. Reverting the branch
removes it. #140 requests and retained receipts stay valid without it.

## Bottleneck and next step

The project bottleneck is unchanged: **VEPMC 0 → 1** on the founder's Chromebook (`greg path`, N1).
Only Alfonso's run moves it.

The cognition workstream's next step is to run the frozen v0.3 suite's `always_llm` and `tool_llm`
arms once a founder-selected local model answers on Body 1
(`greg model set --route ollama --local-model <name> --key <founder key>`).
That is the one comparison that can tell whether routing beats a model.
