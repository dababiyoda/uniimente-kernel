# Continuation package — 2026-10-15

This is where the next session, or Alfonso, picks up. Source directive:
`docs/intent/sources/OPUS-MAXIMUS-MASTER-EXECUTION-DIRECTIVE-2026-10-13-source.md`.
Executable truth is in `acceptance/` (`python -m acceptance check|run`). This file only points to it.

## Completion boundary

This line holds the **currently achievable developmental machine**, and it is **not complete**. In
`acceptance/completion-contract.json`, 3 of the 15 current-machine conditions are met, 11 are partly met and
1 is not met: buildable gaps remain open. No evidence anywhere exceeds `BODY_VERIFIED`. Every founder key in
every test is a per-test key, so nothing is `FOUNDER_ACCEPTED`, `AUTHORIZED_LIVE`, `EXTERNALLY_VERIFIED` or
`COMMERCIAL_OUTCOME_VERIFIED`.

## Where things are

| Item | Where | State |
| --- | --- | --- |
| Converged GREG lineage | PR #173, `claude/greg-full-machine-convergence-20261013` | Draft. Not merged to `main`; merging is Alfonso's decision |
| Gate hardening (#55 CASE 27, #21, #12) | Draft PR #182, `claude/greg-gate-hardening-20261015` | Waits on Alfonso's key enrollment and INTEGRITY_AUTHORIZE; CI job 3 is red by design until then |
| Merge records | `docs/collaboration/MISSION-DEFECTS-2026-10-15.md`, `INSTALLED-BODY-CONVERGENCE-2026-10-14.md`, `SECURITY-PORTS-2026-10-15.md` | Each names its residuals |
| Acceptance missions A–L | `acceptance/missions.json` | 85 obligations, 359 test nodes, 24 gaps closed; 16 test files registered as real Body processes |
| Completion contract | `acceptance/completion-contract.json` | 18 functions; tiers and coverage are computed from the acceptance run; 0 rest only on requirements that cover their whole obligation |
| Verifier | `verifier/runs/` | PASS V1–V5 at 0655f13 |
| Acceptance run | `docs/evidence/acceptance/2026-10-15-7cfa0bc.json` | 81/85 under the earlier rules, which ignored coverage and never checked BODY_VERIFIED against the cited tests. Under the current rules (`acceptance-report/3`), this tree's 359 cited nodes give 80/85 at their declared tier (800 passed, 4 skipped). Of those 80, 15 cover the whole obligation and 65 only part: a coverage audit lowered 22 requirements to partial, and a requirement covers its whole obligation only when it reaches its tier. J.J1b (coverage gap) does not count, though its failing tests would fail the run. 9/9 trace links reach their tier. The 4 short (E.R2–R4, G.R2) need the real organ checkouts, which skip here |

## Open gaps (from `acceptance/missions.json`)

**Buildable now (45).** Highest leverage first:

1. **I.G7:** the appraisal executes the worker's code inside the acceptance process and reads its exit code, so a
   change built to subvert the test process itself can still pass. Hold the expectations in a parent the code under
   test cannot reach. (I.G6 closed on 2026-10-15: commissioned workers are now Landlock-confined and a substituted
   evaluator is refused; see `tests/unit/test_greg_worker_containment.py`.)
2. **H.G7:** interrupt the separate appraiser, the console or remote service, and the Genesis builder mid-operation.
   **H.G4:** interrupt a paid `worker.commission` inside a Body process.
3. **D.G8:** run a multi-worker mission in a real Body process. **D.G4, D.G6, D.G7:** cumulative budget,
   cancellation, and lease coherence over time.
4. **G.G1, G.G5:** drive the business loop through the Body end to end.
5. **C.G1, C.G3–C.G5, C.G7–C.G12:** Capability Genesis honesty and reach (no prewritten answer, real search, route
   order, oracle ordering, hostile attach, appraiser audit, the package route at
   BODY tier, routing gravity deficits into Genesis, license provenance).
6. **E.G1–E.G7:** cross-organ work with real organs. This needs the organ checkouts in CI (E.G4), which is an
   environment step, not a founder act.
7. **J.G1–J.G8, J.G10:** compounding learning (counterfactuals, ablations, acquired capability and SOP
   compounding), and Mission J on a real Body process (J.G10 needs no founder act: BODY_VERIFIED uses a
   per-test key).
8. **B.G3–B.G6, B.G9, A.G3, A.G4, F.G3, H.G10, I.G5.**

**Blocked (23).**

- **Founder (13):** everything above BODY_VERIFIED; the gate signature (I.G1); arming the evidence register
  (I.G4); standing approval (F.G4); adopting protected evolution (J.G9); live irreversible effects (H.G8).
- **Technical (5):** the phone test toolchain, a local model for the LLM baseline and for unstructured geometry,
  live model creation, and the browser composition.
- **External (3):** an external red team, and the real organ checkouts.
- **Credential (2):** real frontier workers, and Stripe test mode.

## Founder decisions waiting

1. Merging PR #173 into `main`.
2. Signing or rejecting PR #182, the gate hardening. Until it is signed, the ratified gate still admits the
   CASE 27 commit-window escalation, and the GrantIssuer hands out its live records.
3. Whether N1 may count on the founder-tier claim plus inspection, or must wait for #138's authenticated
   external verification.
4. The `e2440a6` ledger trade-off.
5. Standing approval for goal asks (F.G4).
6. The System 35 media policy. Also #46, #52, #53, #54 and #56 (see the #173 description).

## Also outstanding

- **Port waves not yet applied:** #73 containment floor, #71 PKI, #19/#22, #18, the #64 residual, #23/#25,
  #20, #57.
- **Organ propagation:** WMI #42 and DALEOBANKS #85/#89 have dispositions only.
- **Independent adversarial review by separate reviewer agents** is owed for this session's commits. The
  subagent weekly limit blocked it until 2026-10-21. Every change here carries fail-before tests and
  mutation checks, but no second reviewer has attacked them.

## How to resume

```
python -m acceptance check                      # static soundness of the manifest and contract
python -m acceptance run --out report.json      # ~8 min; exits 1 while any requirement or trace link falls short or any cited test fails
python -m governance.integrity --check          # 0 on #173; 1 on #182 until Alfonso signs
python verifier/v2/verify.py                    # needs a clean tracked tree
```

When you close a gap, add its test to the requirement in `acceptance/missions.json` and mark the gap
`CLOSED` with what closed it. Run a mutant that removes the mechanism, and confirm the test fails. Never
raise a tier without a passing test, and never cite a test that skips here as attained. A requirement is
`BODY_VERIFIED` only with a cited test from a file in `body_process_tests` in which an argv that starts a real
Body process statically reaches a process-spawning call; an in-process Body is `SANDBOX_VERIFIED` at most.
Raise `coverage` only when the cited tests show every clause of the obligation at the declared tier, and a
requirement counts as covering its whole obligation only when it also reaches that tier in the run; a `gap`
requirement declares no tier, but its failing tests still fail the run.
