# Antifragility v3: condition-specific competence. Pre-registration

**Status: pre-registered.** This file is committed together with `workload.json`, which holds the workload digest,
the sha256 of #189's harness and the sha256 of the mechanism, its two call sites and this harness. That commit
comes before any stress mission or holdout instance of this experiment is run. `experiment.py` refuses to run if
any of them differs.

**Base:** the integration owner's final joined head `9e12b9a6` on `claude/greg-full-machine-completion-whgiee`
(#196: #189 `93badaff`, #179 `866d4770`, #168, the operation re-admission, P6 joined v1, #201's evidence-soundness
patch), named for this freeze by the owner on 2026-10-22, merged into `claude/antifragility-v3-condition-competence`.

- **Intent:** `INTENT-20261001-greg-seed-genome` §14, which requires "bounded stress, coupled to a verified learning
  mechanism, produces a subsequent measurable improvement relative to an appropriate control, after counting stress
  and repair costs".
- **What this targets:** residual 3 of #189: competence is summed across strata.
- **Assigned by:** the integration owner on #96, and accepted there. Option (B) was approved with four conditions in
  issuecomment-6331678761, and they are written in below.
- **Prior work:** #189's author handed over the harness facts and a deliberation in issuecomment-6331383087. Their
  shuffled-condition ablation and their dissent (DEFER if no alternative is admissible by a declared rule) are
  adopted.

## 1. Same stress, larger stress, fresh holdout

| Item | Value |
|---|---|
| Generator, objectives, τ, strata | **Byte-identical to #189** (`tests/evidence/antifragility-2026-10-15/experiment.py`, sha256 `f51d8799…`). The harness imports `instance`, `FUNCTIONS`, `TOLERANCE` and `STRATA` from that file, and the freeze records its digest. |
| τ | sphere 0.5, ackley 2.0, griewank 0.3, rosenbrock 200, rastrigin 60, in both strata. Unchanged. |
| Strata | LOW: 10 dimensions, budget 5,000. HIGH: 20 dimensions, budget 10,000. Unchanged. |
| Stress | **36 HIGH-stratum signed missions.** #189's seeds 500-511 come first, in their original order and cycling the five functions, followed by fresh seeds 6010-6033 continuing the cycle. #189's 12 are a strict prefix. |
| Holdout | **Fresh: seeds 6000-6009 × 5 functions × 2 strata = 100 instances.** They are disjoint from the pilot (0-5), the stress (500-511, 6010-6033), #189's holdout (1000-1005) and the failure-closure tests (0-10, 99). The fresh bands come from 6000-6999, which the integration owner assigned on the joined tree, and avoid #179's 6501-6840. Each exposure is recorded in `docs/evidence/greg-data-exposure-ledger.json`. |
| Already seen, disclosed | Seeds 0-5 informed τ (#189). They also gave this design's feasibility pilot and power analysis (`pilot_seeds_0_5.json`, `power_from_pilot.txt`). Seeds 500-511 and 1000-1005 were run by #189. |

## 2. The learning mechanism under test

The mechanism is new functions in `greg/cognition/condition_competence.py`. It is reached through these edits to
existing code, and nothing else:
- `compiler.py`: one hook after the runnable fits are known (`compile_hook`);
- `compiler.py`: one line that runs an adapted request when the alternative is chosen;
- `compiler.py`: one line that renames its answer (`answer`);
- `compiler.py`: one `selection_level` label, `preferred_by_condition_evidence`;
- `settlement.py`: one field merge (`settlement_fields`).

It does three things.

**(c) The condition key, declared now.** A request's cell is `(geometry, dimension band)`. The dimension is
`len(shift)`, a property the request already carries. The bands are `≤ 10` and `11-30`. The key is declared before
any run. #189's author warned that keying on scale is chosen with hindsight, so the shuffled-condition ablation
(§4) tests that choice.

**(b) A bounded, inert shadow trial.**
- **Trigger:** a mission's compile served by the incumbent, in a cell where the incumbent has at least one settled
  `VERIFIED_UNMET` outcome on this body **from another problem**. A request is never shadowed because of its own
  failure, so the failure that triggers shadowing never enters the paired evidence as a known discordant pair. This
  was found and fixed in a plumbing smoke on the disclosed pilot seeds 0-5.
- **What runs:** the next fit in that cell that is **founder-attached** and admitted. The only such fit here is
  `blackbox_multistart_lbfgsb` 1.0.0. It runs in shadow through a declared input adapter:
  - function → objective;
  - bounds → box;
  - budget → evaluations;
  - dimension = len(shift).
- **Inert:**
  - the shadow answer is verified by the genome's own independent verifier;
  - it is recorded on the receipt;
  - it never becomes the mission's answer.
- **Bounds:**
  - at most 36 shadow trials per cell, and none once the cell's preference has fired (a decided cell spends no more);
  - each one gets at most the request's own evaluation budget;
  - every shadow evaluation and second is counted as repair cost, read from every retained compile receipt;
  - a re-observation of the same claim reuses its seeded, deterministic shadow record instead of re-running it, and a
    reused record costs nothing again. In the smoke, this took 17 trials for 5 claims down to 5.
- **Pairing:** at settlement, the shadow result is judged by the same signed check predicate as the incumbent's
  result, and recorded as one paired observation per claim identity.

**(a) The cell preference.**
- **Test:** a one-sided exact sign test on the cell's discordant pairs (alternative passes and incumbent fails,
  against the reverse).
- **Firing:** it fires when p < 0.05 and there are at least 5 discordant pairs.
- **Effect when it fires:** the compiler ranks the alternative first in that cell only.
- **Receipt:** the basis is named: "live paired evidence in cell (optimization, 11-30 d); outside the admitted
  envelope (2-10 d); not a re-admission".
- **Unchanged:**
  - the frozen admission index;
  - `_settled_inhibition` and `_settled_preference`;
  - every other cell.

**Conditions written in (integration owner, 2026-10-22):**
1. **Envelope.** Multistart reaches 20 d only on the cell's own paired evidence. The receipt says so. No admission
   verdict is rewritten. The HIGH result is a live-evidence extension of the envelope, not a re-admission.
2. **Shadows are bounded and inert.** The ceilings are as above. A shadow never changes a returned answer before the
   preference fires. Its cost is counted in LEARN and in B1.
3. **Founder attach.** Both fits are attached with the per-run test key in every arm. Nothing attaches through the
   adapter.
4. **Kill rules are fixed in advance.** See §5.

## 3. Arms (holdout: 100 instances; the same frozen evaluator and τ in every arm)

| Arm | Journal | Mechanism |
|---|---|---|
| PRE | none (pre-stress) | on |
| LEARN | the 36-mission stress body | on |
| CONTROL | the same stressed journal | off (no cell preference, no shadow pairing read) |
| A, pooled | the same stressed journal | on, with a single cell for all dimensions |
| S, shuffled condition | the same stressed journal | on. When the evidence is read, each stress mission's settled pair is assigned to a band by a seeded fair coin (seed `antifragility-v3-shuffle`), independent of its dimension. Holdout requests are still keyed by their true dimension. All 36 stress missions are HIGH, so permuting their identical keys would be vacuous; the coin is the real test of whether the key carries the signal. |
| B1, compute-matched | none | off. The incumbent's evaluation budget on every HIGH holdout instance is raised to ⌊(LEARN's measured holdout evaluations, shadows included, + the stress shadow evaluations from the ledger − 50 × the LOW budget) / 50⌋, so B1's declared total equals LEARN's measured total |
| B2, best-of-both | none | off. Both fits on every instance, and the better verified answer kept. A 2× compute reference, not a kill rule |

Holdout instances are compiled directly, so holdout outcomes never feed learning (as in #189). The arms run in this
order on one machine: PRE, LEARN, CONTROL, A, S, B1, B2. One stressed journal serves LEARN, CONTROL, A and S: every
stress mission is HIGH, so the pooled and keyed cells receive identical pairs and identical shadow triggers.

**Measured per arm and per cell:**
- passes;
- median fitness;
- median wall time;
- the method selected.

**Measured from the stress:**
- missions failed (damage);
- shadow trials run, with their evaluations and seconds;
- the mission index at which the cell preference first fired (recovery cost).

## 4. Why each arm exists
- **CONTROL** separates learning from simply having been stressed.
- **A** separates condition-specific competence from pooled competence. The pilot predicts A is about neutral at LOW (−1), so a small A–LEARN difference is expected and will be reported as measured.
- **S** tests whether the condition key carries the signal or was chosen with hindsight.
- **B1** separates learning from extra compute at equal total evaluations.
- **B2** bounds what any choice between the two fits could buy.

## 5. Verdict rule (fixed at the freeze)

Evaluated in this order.

1. **REGRESSION** if LEARN passes fewer LOW-stratum holdout instances than PRE (the LOW floor is 0), or fewer
   holdout instances in total than CONTROL.
2. **NO_GAIN** if the cell preference never fired during the 36 stress missions, or LEARN's total passes are not
   above both PRE and CONTROL.
3. **NO_GAIN (compute-attributed)** if LEARN's total passes are not above B1.
4. **NO_GAIN (condition not causal)** if LEARN's total passes are not above S.
5. **GAIN** if all of the following hold:
   - LEARN's total passes are above PRE, CONTROL, B1 and S;
   - no stratum × function cell passes fewer instances under LEARN than under PRE;
   - a one-sided exact sign test on the LEARN vs CONTROL holdout discordant pairs gives p < 0.05.
6. **INCONCLUSIVE** if the counts satisfy 5 but the sign test does not.
7. **NO_GAIN** otherwise: the totals pass 2-4 but some stratum × function cell passes fewer instances under LEARN
   than under PRE.

The stress damage, shadow cost, recovery cost and latency are reported beside every verdict. NO_GAIN is kept if that is the result. No rule, seed, τ or ceiling changes after a run.

## 6. Verification of the mechanism before the freeze

- 24 unit and hook tests. The hook tests drive the real compile path:
  - routing switches only in the fired cell;
  - routing never switches to an unattached or unadmitted alternative;
  - CONTROL reads no evidence;
  - a shadow is inert and its answer is never returned;
  - the shadow ceiling holds;
  - settlement pairs a shadow under the signed check;
  - a request's own failure never makes its shadow due.
- 12 mutants of the mechanism, all caught.
- The existing compiler and failure-closure tests pass on the joined head with the hooks in place (108).
- **Plumbing smoke** on the disclosed pilot seeds 0-5, HIGH:
  - 6 missions, 5 failed;
  - 5 paired claims and 5 shadow trials;
  - the preference did not fire at 6 missions, as the power analysis expects.

## 7. Declared before the run

- **Power** (simulated from the pilot rates, `power_from_pilot.txt`): about 0.89-0.93 that the cell preference
  fires within 36 HIGH missions. The simulation assumes independent pairs within a function.
- **Expected direction** (not part of the rule): HIGH gains on sphere, griewank and rosenbrock, and loses on
  ackley. That is the pilot's 10 → 20 of 30. LOW is unchanged by construction, because no LOW stress exists.
- **Limits:**
  - one learning mechanism and two methods;
  - synthetic objectives, with no external outcome;
  - 10 seeds per cell;
  - every key is a per-run test key, not Alfonso's.
- **Authority:** none created. A cell preference can only reorder founder-attached, admitted fits. Nothing is sent,
  spent or activated. VEPMC: 0.
