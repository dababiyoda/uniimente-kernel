# MC-0003 — A corrected reading stops earning credit

Status: **built and tested on a real body, in a cloud container, with test keys. No founder device. VEPMC 0.**
Reviewed independently at `b01d319f` on 2026-11-12 (verdict: sound with fixes). The section "Rules after the review" says what changed; sentences the review found false or incomplete are corrected in place.
It runs on the body's tick path (`greg/body.py`: `corrections.propagate`, then `settlement.reconcile`, then `sop.propose`).
Founder lineage: directive section 45 (S45.A3, S43.A4), the 2026-11-04 re-issue (behaviour B), and extension B of the founder's directive of 2026-11-11 (kept verbatim under INTENT-20261111-ABSOLUTE-OPUS-MAXIMUS, on its own branch). Its minimum test: "retract one shared observation; only its dependent conclusions change. Requalification never restores revoked execution permission."
Tests: `tests/unit/test_greg_evidence_corrections.py`. Mutation gate: `scripts/ci/check_evidence_corrections_mutants.py`.
No tool was run on a donor artifact. The two donors are published algorithms. No code was copied.

## Residual CapabilityDeficit

Reproduced on #196's `8d205324` on a real body. A cognition mission closed and the separate appraiser VERIFIED it. The founder then signed a CRITIQUE reject. `greg/corrections.py` recorded FOUNDER_REJECTED, listed the receipt in `contained_receipts` and marked the claim NEEDS_REVIEW. Settled competence stayed `{"cognition.swarm": (1, 1)}` and no `cognition.settled` record was invalidated. `contained_receipts` and `claims` had no caller outside their own test and mutation gate. A label was computed and nothing read it.

## Source behaviour

1. **Truth-maintenance labelling** (Doyle, "A Truth Maintenance System", Artificial Intelligence 12, 1979). Every belief keeps the justifications it was derived from. A belief is IN only while one of its justifications is IN. When a premise goes OUT, the system relabels what depended on it. Nothing is deleted, so a premise that comes back IN brings its dependents back by relabelling.
2. **Early cutoff in incremental computation** (Mokhov, Mitchell and Peyton Jones, "Build Systems à la Carte", ICFP 2018; the red-green algorithm of Salsa and rustc). When an input is checked again and its fingerprint is unchanged, everything that depended on it is marked current without being run again.

## What already existed, what was added, what was not transplanted

**Already in `greg/corrections.py` on #196:**

- the justifications: `Index` and `descendants` derive, each tick, which claims, actions, decisions, settled outcomes and procedures rest on a reading;
- the labelling of delivered claims: `claims` reports CURRENT, EXPIRED or NEEDS_REVIEW, and a claim is NEEDS_REVIEW while an unrequalified correction lists it;
- the early cutoff for claims. A later reading of the same source with the same digest raises no cause (`Index.causes`), and `claims` takes it as a confirmation, so nothing downstream is touched. After a cause, `Index.requalified` accepts a later passing reading of the same signed sensor: the claim returns to CURRENT and no dependent mission is run again;
- the OUT set for credit: `contained_receipts`. It was computed and never read.

**Added here:**

- the OUT label now reaches the beliefs derived from the reading. `settlement.measured_outcomes` skips an observation whose receipt is contained, so every reader of settled competence follows it. `corrections.contained_missions` gives the same label per mission, and `sop.closed_procedures` and `precedents` read it;
- the relabelling is recorded. `settlement.reconcile` appends a `cognition.settled` revision that names the cause (`withheld_by`), and appends another when the cause is requalified. The early cutoff now reaches credit: a requalified cause returns the outcome without running the mission or its appraisal again;
- a claim is withheld as a whole. An earlier reading of the same claim does not earn the credit back;
- a reading that held no answer is not a failed replication: a capability deficit, a timeout (state UNKNOWN), a stopped worker (state ABSTAIN), an incomplete formalization. No method answered. One that answered and failed the check, or that REFUTED the claim, is a real negative (rule 3 below).

**Deliberately not transplanted:**

- no justification network is stored. The index is still derived from the journal each tick. There is no second ledger;
- no assumption-based labels and no parallel contexts (de Kleer's ATMS);
- no dependency-directed backtracking. GREG does not pick a culprit or search for a consistent set. A contradiction goes to the founder as an ask;
- no automatic re-run of dependents. A build system recomputes what is red. GREG asks (EVIDENCE_CORRECTION) and waits for a signed mission;
- no credit withheld downstream of the reading. A mission that acted on a contained reading has its claim marked and is no evidence for a procedure, but its own sensor's settled outcome stays: its method answered the input it was given;
- nothing that touches permission. Relabelling IN writes no capability state, approval or grant.

## Rules after the review of `b01d319f` (2026-11-12)

Each rule was reproduced as a defect on `b01d319f` first, on a real body where the review used one. The review, its probes and their output before and after are kept with the session, not in the repository.

The founder decided the rejected-answer question on 2026-11-12. His words, as the commissioning session relayed them to this unit (a relay in a working session, not founder authentication, and not yet an entry in the Founder Intent Ledger):

> Rejected-answer credit: withhold unsupported success credit. Scope rejection history to the relevant answer, evidence, task conditions, and version. Permit explicit requalification when justified; avoid turning one rejection into an unexplained permanent prohibition across unrelated missions.

Rules 1 and 2 withhold the unsupported credit and set the scope; rule 7 is the explicit requalification; rule 8 is the stated reason.

1. **A founder rejection withholds the answer, not one receipt of it** (review F1). While a rejection stands on any reading of a claim, every reading of that claim that carries the same answer is contained with it, whichever receipt it has: an earlier reading the closure does not cite, a standing mission's own next cadence read. A later reading with a different answer is a new answer and settles on its own merits. Before: a standing mission's next read gave the rejected answer its credit back, and when the mission had already read the claim again, credit never dropped.
2. **The same rule holds across missions, for GREG's own computations, and it stops at the answer** (review F2; the founder's decision of 2026-11-12: "withhold unsupported success credit. Scope rejection history to the relevant answer, evidence, task conditions, and version"). A rejection withholds the answer, identified by what was asked (the signed sensor: instrument, input and predicate, without its labels) and what was answered (method, method version, answer digest), not by the mission that asked. **Labels** are the check's id and description and the sensor params in `corrections.LABEL_PARAMS`: today only `problem_id`, a cognition request's name for its question, which the receipt repeats and nothing computes from. Every other param is part of the question. The identical question signed again as a new mission, under any problem_id, earns nothing while it delivers the rejected answer (review of `0a9a246f`, N5: a relabelled re-signing escaped), and that mission's claim is marked NEEDS_REVIEW and is no evidence for a procedure or a precedent. Its own runs keep their credit (rule 9). It does not reach a different question (another predicate on the same input), different inputs, another version of the method, or an unrelated mission; a world reading (a file, a URL) is the same claim only within its own mission. Tests: the review's reproduction in `test_a_contained_reading_is_withheld_from_settled_competence` (on `b01d319f` credit went from (1, 1) to (2, 2)), and the four cases it must not reach in `test_a_rejection_does_not_reach_another_question_other_inputs_another_version_or_an_unrelated_mission`.
3. **A reading that held no answer is no failed replication, and one reader says which those are** (review F3). On `b01d319f` a host stall on a later mission (a solver timeout, or the worker killed with exit 137) was recorded REPLICATION_FAILED against a correct first answer, withheld its credit and asked the founder. Whether a reading answered is the question of one canonical reader, `greg.missions.unanswered`, and `corrections.held_no_answer` asks it: a reading it calls unanswered is not blamed on an earlier answer, requalifies nothing and carries no answer to compare (`test_a_reading_the_canonical_reader_calls_unanswered_is_neither_blamed_nor_credited`). That reader, as it stands on this branch, reads only `abstention_state`, and a compile receipt carries `state`: the engine itself counts such a reading as measured and asks NO_STRATEGY. It is being extended on another branch (`greg/missions.py` is not changed here). Until then `held_no_answer` has one interim half, marked for deletion: a compilation whose `state` is itself an abstention class (UNKNOWN, ABSTAIN, CAPABILITY_DEFICIT and the like) is put to the same reader as that abstention. Every other state is the canonical reader's alone. The narrower question "which answer does this reading carry" is `corrections.answer_digest`; "is credit earned for this receipt" stays settlement's (ANSWERED compilations and methods' own receipts with no abstention).
4. **Containment does not depend on tick order** (review F4 and F8). It is derived from the journal each time it is read. A founder rejection counts from the acceptance of its signed command: a reject and an SOP_RATIFY read in one inbox tick refuse the ratification, and a compile decision made before the next tick already reads the lowered credit. A dependent that appears after a correction was recorded (a mission that binds a contained reading, a later reading of a rejected answer) is contained when it exists. The `affected` list a correction stored is history and the basis of its ask; it is not the projection.
5. **A rejection reaches the claim through any record of it** (review F5): its closure, its appraisal (everything the judged closure cites), any reading of it (cited by the closure or not) and its settled outcome. A rejected failure closure (`mission.unmet`) contains the failing readings it closed on, so a failure the founder disputes stops counting against the method, by the same mechanism in the other direction; it contains no mission, because it delivered nothing. A rejection of any other event (a registration, an ask) names no reading: it is kept, it changes no credit, and the result of the command says so (`credit_effect` in the accepted command's result; the morning report lists it under `founder_rejections.changed_no_credit`).
6. **A rejection only lowers the other credit readers** (review F6). In routing reliability (`routing.track_record`), the earned-autonomy report and precedent action evidence, a completed run of a mission a standing founder rejection contains is counted apart (`founder_rejected`) and never as a success or a verified run. Its failures and a refutation of its closure count as before; in precedents a negative self-report of such a run stays (pinned by a test since the review of `0a9a246f`, N9). Neither change can raise a score or a level, and neither withdraws an approval or changes what may run.
7. **Only a signed critique counts, and the founder can requalify what he rejected** (review F7; the founder's decision of 2026-11-12: "Permit explicit requalification when justified; avoid turning one rejection into an unexplained permanent prohibition across unrelated missions").
   - A `critique.recorded` row is followed only when an accepted signed CRITIQUE command with its digest, naming the same target and the same verdict, stands behind it. That holds for a rejection and for an acceptance.
   - **Who can requalify, and how.** Whoever can sign a CRITIQUE (the founder key, and today a delegated device key: see the open decisions below): a later signed CRITIQUE with verdict accept (`greg accept EVENT_ID`) that names the closure, the appraisal, a reading or the settled outcome of the rejected answer lifts the withholding for that answer, from the acceptance of the command on. It lifts that answer and no other: a rejection of another answer on the same body stays. A rejection signed after the acceptance stands again.
   - **How it is recorded.** The next propagation writes `evidence.requalified` for the cause, naming the accepting critique and the digest of the command it came from. The settled outcome that returns names the correction it was restored after (`restored_after`). The acceptance's own command result lists the causes it requalified, and the morning report lists the rejection under `founder_rejections.requalified`.
   - **What lifts nothing.** A later passing reading (evidence alone never overrules a founder rejection), an acceptance row nobody signed, and a bare `evidence.requalified` record (the forgery the review showed): the lift is derived from the signed critiques each time and that record is never trusted on its own.
8. **Every withholding states its reason.** Wherever credit is missing, the record says which cause, for a founder rejection which critique and which answer identity, and what lifts it: in the `withheld_by` of the invalidated `cognition.settled` row and in its `reason`, in `greg cognition knowledge` (`withheld`, beside the competence it was taken from), in the result of the rejecting command (`credit_effect`), in the morning report (`founder_rejections.standing`), in a refused SOP ratification (the mission and its correction are named), and in the counters `founder_rejected` (routing, earned autonomy) and `withheld_by_founder_rejection` (precedents).

## Rules after the review of `0a9a246f` (2026-11-12)

9. **A rejection reaches the runs the rejected closure rests on, not another mission's runs beside a shared computation** (N4). A reading of the rejected answer in another mission is contained (its settled competence is the answer's) and that mission's claim is NEEDS_REVIEW and no evidence for a procedure or a precedent. Its claim is reached by the answer only (`answer_only` in the correction's `affected.claims`), so `rejected_missions` leaves it out: its own runs keep their routing reliability, earned level and precedent action evidence. A mission whose run bound the rejected answer does rest on it and is withheld in full. On `0a9a246f` another mission's unrelated file write was counted `founder_rejected` and its earned level fell to SHADOW. The command result names both sets (`missions_withheld`, `runs_withheld`).
10. **A later run whose own answer the verifier refuted is no failed replication** (N6). A compilation in state REFUTED with no result, or a method receipt the verifier REFUTED, says its own candidate was wrong, not that an earlier verified answer to the same question was (`corrections.refuted_own_answer`). On `0a9a246f` it was booked REPLICATION_FAILED, withheld the earlier credit and asked the founder. A compilation that refutes the claim with a counterexample in its result is an answer and stays a real negative. This is a replication rule and does not change the canonical reader: whether the engine counts a REFUTED reading as a measured failure of its own check is `greg.missions.unanswered`'s, and is an open founder question on the compile-unread unit.
11. **A recorded correction withholds credit only while the readings still produce it.** `_standing` runs `Index.causes`, the rule `propagate` records causes by, on the ledger as it is, and follows a recorded REPLICATION_FAILED (or any recorded cause that impugns the measurement) only when it is re-derived. A row written by anything else is kept as history and still marks its claims NEEDS_REVIEW, but withholds no credit. On `0a9a246f` a bare row with no failing reading behind it took a mission's credit. Requalification by evidence is decided the same way: the requalifying reading becomes the basis and the cause is no longer produced; a bare `evidence.requalified` row that names no reading on the ledger lifts nothing, and does not keep `propagate` from recording the real one beside it. Cost: a cause whose trigger reading has since left the ledger stops withholding.
12. **The morning report names the signers** (N10): each rejection's `signed_by` and each requalification's `requalified_by_signer`, `founder` or `device:<label>`. Whether a device may sign a requalification is unchanged and stays a founder decision.

## What these rules leave open (founder decisions)

- **A procedure ratified before the rejections stays ratified and runnable.** Rejecting every run a procedure was learned from changes nothing about a ratification the founder already signed: `sop.instantiate` still builds a mission from it and its baseline still shows the rejected runs. This unit does not change what a ratified procedure may do.
- **A delegated device key may sign a CRITIQUE today** (`greg/founder.py`, `DEVICE_KINDS`; read, not run, and not changed by this unit). So a device the founder delegated can withhold credit, can requalify what the founder rejected, and by rejecting a failure closure can stop a failure from counting against a method. This unit follows every accepted CRITIQUE alike and does not tell the two signers apart. Whether requalification should need the founder key itself is his to decide.
- Every signed acceptance of a rejected answer lifts the rejection, including a routine morning acceptance of a delivery he rejected earlier. The acceptance's result says which rejections it lifted; nothing asks him to confirm first.
- Rejecting an achievement withholds the whole claim, including a failure of the same claim that the appraiser verified under an earlier unmet closure of that mission.
- A procedure whose recorded proposal includes a mission rejected later is not proposed again from clean runs (`sop.proposed` is keyed by procedure).
- When a new mission delivers an answer the founder already rejected, its claim is marked NEEDS_REVIEW and earns nothing, and no new ask is raised: the ask of a correction is decided when the correction is recorded.
- A mission that only asked the rejected computation keeps its runs' credit (rule 9) but is no precedent and no evidence for a procedure while the rejection stands: `precedents` leaves it out of `locally_appraised_missions`. Whether that mission-level withholding should also stop at the answer is his to decide.
- A label is only `problem_id`. Other params that name rather than change a question (a natural-language `objective` in a compile geometry) are treated as part of the question, so a re-signing that rewords one escapes a rejection.
- A requalification by evidence is also re-derived (rule 11): a bare `evidence.requalified` row that names no reading on the ledger lifts nothing. One that names a real later reading moves the claim's basis to it, as `propagate` would; whether that reading passes is not checked again.

## Mutation

The donors relabel beliefs inside one reasoner. Here the label crosses from the evidence layer into three credit projections, and it is selective:

- only a failed replication and a founder rejection contain credit. No appraisal sees them. A refuted appraisal impugns the measurement too, but settlement and SOP already read each closure's appraisal and restore what it withdrew when a later appraisal verifies the closure, so it is left to them. A source that moved on marks the claim and leaves the method as competent as before;
- containment is scored as neither success nor failure, as a disputed world outcome already is;
- the unit is the reading, not the mission. A two-check mission keeps the check nobody impugned. For a founder rejection the unit is the answer the reading carries (rules 1 and 2 below "Rules after the review").

## Preserved invariant

- History is append-only. A withheld outcome keeps its original record; the withholding and its lifting are later records.
- `corrections`, `settlement`, `sop` and `precedents` write no grant, approval or capability state. Requalification never restores permission. The readers the review added (`routing.track_record`, `autonomy.report`) write nothing; `autonomy.regress`, which withdraws a standing approval on failure evidence, does not read rejections.
- One authority path. Nothing here runs, attaches or dispatches anything.

## New interaction

A founder's signed rejection, or a failed replication, now changes what the compiler selects on (`compiler._settled_counts`), what the disposition review counts, what conditional competence and learned routing read, which procedures are proposed or ratified, and which missions are precedents. A founder's rejection also lowers routing reliability, the earned-autonomy report and precedent action evidence. A rejection takes effect when its signed command is accepted, with no tick in between (on `b01d319f` a ratification read in the same inbox tick as the rejection was still accepted). Neither source did this alone: corrections computed a label nobody read, and settlement credited by appraisal only.

## Expected benefit (measured, one container run each)

| Scenario on a real body | #196 `8d205324` | This change |
|---|---|---|
| founder rejects one of two verified cognition closures | credit (2, 2) | credit (1, 1); one invalidated record naming the cause |
| founder rejects one of three note-writing closures | SOP proposed from all three | no proposal; proposed later from three clean runs |
| founder rejects one of two closures that used `fs.write` | both are precedents | one precedent |
| the only fitting method is detached and the question is signed again | REPLICATION_FAILED and an ask | no cause, no ask, credit kept |

Measured on `b01d319f` and after the review's fixes (one container run each):

| Scenario on a real body | `b01d319f` | After the fixes |
|---|---|---|
| founder rejects a standing mission's hold; the mission reads again | credit (1, 1) again, or never dropped | credit stays withheld |
| the rejected question is signed again as a new mission, same answer | credit (1, 1) -> (2, 2) | (1, 1); the new claim NEEDS_REVIEW |
| a later mission's solver times out or is killed on the same question | REPLICATION_FAILED, credit withheld, an ask | no cause, no ask, credit kept |
| a reject and an SOP_RATIFY in one inbox tick | ratified | ratification refused |
| founder rejects the earlier, uncited reading of a claim | no cause, credit (2, 2) | credit (1, 1), claim NEEDS_REVIEW |
| founder rejects an unmet closure | no cause, credit (2, 1) | credit (1, 1) |
| founder rejects a registration event | nothing said | the result says it changed no credit |
| founder rejects every run `fs.write` reliability was earned on | reliability 0.8, level RECOMMENDER | 0.5, SHADOW |

## New failure

- A false cause now costs credit. Two were found and fixed: a capability deficit, and (review F3) a compilation that held no answer, a host timeout or a killed worker among them. Which readings held no answer is decided by the canonical reader `greg.missions.unanswered` (rule 3).
- Listing a refuted appraisal as containing was tried first and regressed `tests/integration/test_cognition_multi_claim_settlement.py`: credit stayed withheld after the closure was verified again, until the next propagation. It was removed (`corrections.APPRAISED`).
- A founder rejection is never requalified by evidence. On `b01d319f` this card said "that claim's credit stays withheld", which was false: a later reading of the same answer under a new receipt settled the claim again (review F1). Now the rejected answer stays withheld on every reading that carries it, a different answer to the same claim settles, and only a signed acceptance lifts the rejection (rule 7).
- "The same answer" is the digest of the method, its version and its answer. An answer that embeds something that differs per run (a timestamp, a sampled value from an unseeded method) is a different answer each time, and a rejection of one run does not withhold the next.
- A rejected failure closure raises its method's share of successes (the failure no longer counts). That is the intended direction of rule 5, and it is the one place where a rejection can raise settled credit.
- REPLICATION_FAILED is keyed by the signed sensor, not by the method. A later failing answer from another method withholds the first method's credit until a passing reading requalifies it.
- A proposal already recorded with a mission that is later contained cannot be ratified, and the same procedure is not proposed again (`sop.proposed` is keyed by procedure). The same held before for a mission later refuted.
- In a mission that closed unmet and was later achieved, a verified failure of the same claim is withheld with a contained achievement reading. It needs one signed claim that failed and later passed on the same input and method.
- The construction path of settlement shares the one containment decision. No test in this container exercises it on a construction (networkx and scipy are absent here). `settlement.awaiting_realization` still offers a construction claim whose reading is contained; a report on it is recorded and settles nothing while the cause stands.
- Cost: on a body with no correction and no rejection, each read of containment replays two record kinds and builds nothing. On a body with one, containment builds the index of readings once per ledger head (it is kept until the ledger grows) and derives the dependents of each standing cause. Routing reliability and the earned-autonomy report now read containment too. The test file has 47 tests (22 on #196) and takes about 90 s in an idle 4-CPU container (about 3 s on #196, about 50 s at `b01d319f`). Its mutation gate has 81 mutants (41 on #196, 50 at `b01d319f`) and took 6 min 59 s there (3 min 17 s at `b01d319f`); it runs in CI job 8, which has a 30-minute limit, and that cost is not yet timed in CI. Sixteen further mutants were run once and caught, then left out of the gate to keep it short; the tests that caught them stay.

## Simpler comparator

"Withhold everything a touched mission ever settled." Built as a test-local function in `test_withholding_follows_the_reading_not_the_mission_and_no_earlier_reading_earns_it_back`. On a two-check mission with one rejected reading it drops the unimpugned check as well. This change keeps it.

## Decisive experiment

`test_a_contained_reading_is_withheld_from_settled_competence` fails on `8d205324` with `{'cognition.swarm': (2, 2)} == {'cognition.swarm': (1, 1)}` and passes here. The ablation is the gate's mutant "settlement ignores containment": with the filter removed that test fails again.

## Disposition

RETAIN on the integration line, for review. Not founder-used. The remaining half of S43.A4 is open: a corrected claim does not yet hold a later mission that consumes its output.
