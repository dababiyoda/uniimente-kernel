# Acceptance runs

`python -m acceptance run --out <file>` records what each Mission A–L requirement and each completion-contract function reached on one head. A requirement reaches its declared tier only when every cited test passes. A skip is not a pass, and nothing above BODY_VERIFIED can be reached by a test.

| Run | Head | Result |
| --- | --- | --- |
| `2026-10-15-7cfa0bc.json` | 7cfa0bc | 81/85 requirements at their declared tier. E.R2–R4 and G.R2 fall short because their proof is the real-organ tests (RailScout, WealthMachine and DALEOBANKS checkouts), which skip here. Their status is IMPLEMENTED, and that is truthful. |
| `2026-10-15-18efa0d.json` | 18efa0d | `acceptance-report/3`, the current record: 825 cited tests passed, 4 skipped, none failed. 80/85 requirements at their declared tier, 13 of them covering the whole obligation and 67 only part; 9/9 trace links at their tier; 0/18 contract functions rest only on whole-obligation requirements. The same four fall short for the same reason. |
| `2026-10-15-8a1daa2.json` | 8a1daa2 | `acceptance-report/3`, after the review fixes and the coverage audit: 821 cited tests passed, 4 skipped, none failed. 80/85 requirements at their declared tier, 14 of them covering the whole obligation and 66 only part; 9/9 trace links at their tier; 0/18 contract functions rest only on whole-obligation requirements. The same four fall short for the same reason. |

An earlier run at 2a73452 (not retained) reached 80/85: the same four, plus L.L3, which had no test yet.

The 7cfa0bc run is an `acceptance-report/1` record, made before three rules existed: a requirement whose coverage is `gap` attains nothing, `BODY_VERIFIED` needs a cited test that drives a real Body process, and each Mission L trace link's tier is computed from its own proofs. Its 81/85 counted J.J1b (coverage `gap`) as attained, and it read G.R1, G.R5, G.R6 and G.R11 at `BODY_VERIFIED` on in-process tests. Its outcomes remain a true record of what passed at 7cfa0bc. The commit that introduced those rules (082facb) ran its own cited nodes under them (`acceptance-report/2`). That was 359 distinct minimal nodes, 14 more than 7cfa0bc's 345 (`acceptance.__main__._nodes`). The result: 80/85 requirements reached their declared tier, 37 of them counted as covering the whole obligation and 43 only part. The same four fell short for the same reason, and 9/9 trace links reached their declared tier. That run is not retained here.

A second review found three more ways that report could read stronger than its evidence:

- the whole-obligation flag followed declared coverage, whether or not the tier was reached;
- a failing test cited only by a `gap` requirement did not fail the run;
- a short trace link did not lower Mission L.

The commit that fixed those (`acceptance-report/3`) also ran a coverage audit, which lowered 22 requirements from `covered` to `partial`. It then ran the same 359 nodes on its tree: 800 passed and 4 skipped. 80/85 requirements reach their declared tier, 15 of them covering the whole obligation and 65 only part. No cited test failed, errored or collected nothing, and 9/9 trace links reach their declared tier. 0/18 contract functions rest only on requirements that cover their whole obligation. The same four (E.R2–R4, G.R2) fall short because their real-organ tests skip here. That run is not retained here either.

The retained `2026-10-15-8a1daa2.json` is the run of the integrated line after both review rounds. Between it and the unretained run above, A.R4 and G.R7 went from `covered` to `partial` (each one's own notes show a clause only in-process or only in components), L.L3 went back to `covered` (both nine-link runs now assert the credit only a VERIFIED appraisal gives, and in-process a REFUTED appraisal of the same acts lowers routing reliability; an audit then found this too strong, see below), L.L1 went from `SANDBOX_VERIFIED` to `BODY_VERIFIED` and stays `partial` (the real-process trace now shows the decision, the outcomes and `greg foundry why`; costs are $0 there), and the round-2 runtime tests were cited. It ran 821 cited tests.

The retained `2026-10-15-18efa0d.json` supersedes it as the current record. An audit of the integration found that 8a1daa2 held L.L3 to a weaker standard than A.R4: on the real Body process the Learning link is a tally (`routing.reliability` never reads the verified credit, and the refuted-verdict contrast runs only in-process), so L.L3 is `partial` again, and the completion contract's LOOP-COMPREHENSION entry, which still described L1 and L3 as they stood before the review fixes, now names what remains. The run also includes the four round-4 inbox tests. It ran 825 cited tests.
