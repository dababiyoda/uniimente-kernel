# Acceptance runs

`python -m acceptance run --out <file>` records what each Mission A–L requirement and each completion-contract function reached on one head. A requirement reaches its declared tier only when every cited test passes. A skip is not a pass, and nothing above BODY_VERIFIED can be reached by a test.

| Run | Head | Result |
| --- | --- | --- |
| `2026-10-15-7cfa0bc.json` | 7cfa0bc | 81/85 requirements at their declared tier. E.R2–R4 and G.R2 fall short because their proof is the real-organ tests (RailScout, WealthMachine and DALEOBANKS checkouts), which skip here. Their status is IMPLEMENTED, and that is truthful. |

An earlier run at 2a73452 (not retained) reached 80/85: the same four, plus L.L3, which had no test yet.

The 7cfa0bc run is an `acceptance-report/1` record, made before three rules existed: a requirement whose coverage is `gap` attains nothing, `BODY_VERIFIED` needs a cited test that drives a real Body process, and each Mission L trace link's tier is computed from its own proofs. Its 81/85 counted J.J1b (coverage `gap`) as attained, and it read G.R1, G.R5, G.R6 and G.R11 at `BODY_VERIFIED` on in-process tests. Its outcomes remain a true record of what passed at 7cfa0bc. The commit that introduced those rules ran its own cited nodes (two more than 7cfa0bc's) under them (`acceptance-report/2`): 80/85 requirements reach their declared tier, 37 of them covering the whole obligation and 43 only part. The same four fall short for the same reason, and 9/9 trace links reach their declared tier. That run is not retained here.
