# MC-0003 — A corrected reading stops earning credit

Status: **built and tested on a real body, in a cloud container, with test keys. No founder device. VEPMC 0.**
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
- a compilation that ended in a capability deficit is not a failed replication. No method ran.

**Deliberately not transplanted:**

- no justification network is stored. The index is still derived from the journal each tick. There is no second ledger;
- no assumption-based labels and no parallel contexts (de Kleer's ATMS);
- no dependency-directed backtracking. GREG does not pick a culprit or search for a consistent set. A contradiction goes to the founder as an ask;
- no automatic re-run of dependents. A build system recomputes what is red. GREG asks (EVIDENCE_CORRECTION) and waits for a signed mission;
- no credit withheld downstream of the reading. A mission that acted on a contained reading has its claim marked and is no evidence for a procedure, but its own sensor's settled outcome stays: its method answered the input it was given;
- nothing that touches permission. Relabelling IN writes no capability state, approval or grant.

## Mutation

The donors relabel beliefs inside one reasoner. Here the label crosses from the evidence layer into three credit projections, and it is selective:

- only a failed replication and a founder rejection contain credit. No appraisal sees them. A refuted appraisal impugns the measurement too, but settlement and SOP already read each closure's appraisal and restore what it withdrew when a later appraisal verifies the closure, so it is left to them. A source that moved on marks the claim and leaves the method as competent as before;
- containment is scored as neither success nor failure, as a disputed world outcome already is;
- the unit is the reading, not the mission. A two-check mission keeps the check nobody impugned.

## Preserved invariant

- History is append-only. A withheld outcome keeps its original record; the withholding and its lifting are later records.
- `corrections`, `settlement`, `sop` and `precedents` write no grant, approval or capability state. Requalification never restores permission.
- One authority path. Nothing here runs, attaches or dispatches anything.

## New interaction

A founder's signed rejection, or a failed replication, now changes what the compiler selects on (`compiler._settled_counts`), what the disposition review counts, what conditional competence and learned routing read, which procedures are proposed or ratified, and which missions are precedents. Neither source did this alone: corrections computed a label nobody read, and settlement credited by appraisal only.

## Expected benefit (measured, one container run each)

| Scenario on a real body | #196 `8d205324` | This change |
|---|---|---|
| founder rejects one of two verified cognition closures | credit (2, 2) | credit (1, 1); one invalidated record naming the cause |
| founder rejects one of three note-writing closures | SOP proposed from all three | no proposal; proposed later from three clean runs |
| founder rejects one of two closures that used `fs.write` | both are precedents | one precedent |
| the only fitting method is detached and the question is signed again | REPLICATION_FAILED and an ask | no cause, no ask, credit kept |

## New failure

- A false cause now costs credit. One was found and fixed (the capability deficit). Other abstentions were not examined.
- Listing a refuted appraisal as containing was tried first and regressed `tests/integration/test_cognition_multi_claim_settlement.py`: credit stayed withheld after the closure was verified again, until the next propagation. It was removed (`corrections.APPRAISED`).
- A founder rejection is never requalified by evidence, so that claim's credit stays withheld. A later founder critique that accepts the same closure does not lift it either: `corrections` reads rejections only.
- REPLICATION_FAILED is keyed by the signed sensor, not by the method. A later failing answer from another method withholds the first method's credit until a passing reading requalifies it.
- A proposal already recorded with a mission that is later contained cannot be ratified, and the same procedure is not proposed again (`sop.proposed` is keyed by procedure). The same held before for a mission later refuted.
- In a mission that closed unmet and was later achieved, a verified failure of the same claim is withheld with a contained achievement reading. It needs one signed claim that failed and later passed on the same input and method.
- The construction path of settlement shares the one containment decision. No test in this container exercises it on a construction (networkx and scipy are absent here). `settlement.awaiting_realization` still offers a construction claim whose reading is contained; a report on it is recorded and settles nothing while the cause stands.
- Cost: one more read of the correction records for each `measured_outcomes` call (one record kind on a body with no correction, three otherwise). The test file went from about 3 s to about 50 s in this container, and its mutation gate from 41 to 50 mutants.

## Simpler comparator

"Withhold everything a touched mission ever settled." Built as a test-local function in `test_withholding_follows_the_reading_not_the_mission_and_no_earlier_reading_earns_it_back`. On a two-check mission with one rejected reading it drops the unimpugned check as well. This change keeps it.

## Decisive experiment

`test_a_contained_reading_is_withheld_from_settled_competence` fails on `8d205324` with `{'cognition.swarm': (2, 2)} == {'cognition.swarm': (1, 1)}` and passes here. The ablation is the gate's mutant "settlement ignores containment": with the filter removed that test fails again.

## Disposition

RETAIN on the integration line, for review. Not founder-used. The remaining half of S43.A4 is open: a corrected claim does not yet hold a later mission that consumes its output.
