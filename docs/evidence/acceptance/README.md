# Acceptance runs

`python -m acceptance run --out <file>` records what each Mission A–L requirement and each completion-contract function reached on one head. A requirement reaches its declared tier only when every cited test passes. A skip is not a pass, and nothing above BODY_VERIFIED can be reached by a test.

| Run | Head | Result |
| --- | --- | --- |
| `2026-10-15-7cfa0bc.json` | 7cfa0bc | 81/85 requirements at their declared tier. E.R2–R4 and G.R2 fall short because their proof is the real-organ tests (RailScout, WealthMachine and DALEOBANKS checkouts), which skip here. Their status is IMPLEMENTED, and that is truthful. |

An earlier run at 2a73452 (not retained) reached 80/85: the same four, plus L.L3, which had no test yet.
