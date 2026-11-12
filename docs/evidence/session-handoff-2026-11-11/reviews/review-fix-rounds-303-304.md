# Independent review of the #303 and #304 fix rounds (2026-11-12, report read 15:44 UTC)

Reviewer: separate agent process, same model. Probes: scratchpad/rf-probes/p/, logs scratchpad/rf-probes/logs/,
merged probe tree scratchpad/rf-probes/merged (compose-cu 8044c4fc + 0a9a246f's test change). Every claimed fix of
both rounds reproduced before/after (listed in the report).

| id | unit | sev | defect |
|---|---|---|---|
| N1 | #304 | high | a declined compile receipt (deficit, budget below minimum step) passes `absent result.counterexample`: ACHIEVED, VERIFIED (q02_declined_pass.py); the budget shape lost host_stop in the F4 fix |
| N2 | #304 | high | direct cortex route: host TIMEOUT (reason_code TIMEOUT on the receipt) passes `absent`: ACHIEVED, VERIFIED (q09_direct_absent.py) |
| N3 | #304 | medium | OSError EAGAIN/ENOMEM at launch read as the Mind declining: NO_STRATEGY at 0 s; absent passes (q03_untyped_launch.py) |
| N4 | #303 | medium | a rejection reaches another mission's unrelated action that merely shared the computation (q04_scope.py overreach; control q11) |
| N5 | #303 | medium | relabelled problem_id escapes the rejection (q04_scope.py label) |
| N6 | both | medium | a REFUTED compile on another mission is booked REPLICATION_FAILED against an earlier verified answer (q08_refuted_replication.py) |
| N7 | composition | medium | #303 gate on the composed tree: 80/81, the interim-line mutant survives (redundant with #304's reader) |
| N8 | #304 | low | surviving mutant: `stopped` removed from `why = None if passed or stopped or halted` |
| N9 | #303 | low | surviving mutant: precedents withhold negative self-reports too; rule untested |
| N10 | #303 | low | a device key's CRITIQUE can lift the founder's rejection; the report names no signer |
Further low: memory-ceiling exit typed executor_error; genome wall-clock deadline -> SOLVER_UNKNOWN treated declined; unsigned evidence.correction rows still followed; reason text "None" for state None.
Founder questions: declined reading satisfying a check; problem_id label or question; rejection reach; REFUTED as failed replication; device lifting a rejection; host stall counted as failed observation method.
